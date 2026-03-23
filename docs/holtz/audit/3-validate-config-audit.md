# Prediction 4: validate_config.py Adversarial Code Audit

Audited: `scripts/validate_config.py` (1245 LOC)
Hub module imported by 20+ scripts. Focus: TOML parser edge cases, subprocess wrappers, tracking file I/O, kanban helpers, API functions.

---

## Findings

### VC-001: write_tf() is not atomic — readers can see partial files

**Severity:** Medium
**Category:** Data integrity / race condition
**Location:** `write_tf()`, line 1165

**Problem:** `write_tf()` uses `tf.path.write_text()` (direct write) rather than the `atomic_write_text()` utility defined 33 lines above it. If a reader (another script, `read_tf()`) opens the file during a `write_tf()` call, it can see a partially-written tracking file. This is exactly the scenario `atomic_write_text()` was built to prevent — its own docstring says "prevents readers from seeing partially-written files."

**Evidence:**
```python
# Line 1131 — exists for this purpose:
def atomic_write_text(path: Path, content: str) -> None:
    """Write content atomically using temp-then-rename (BH31: shared utility)."""

# Line 1165 — doesn't use it:
def write_tf(tf: "TF") -> None:
    ...
    tf.path.write_text("\n".join(lines), encoding="utf-8")
```

Tracking files are the most concurrently accessed files in the system — `kanban.py` writes them, `sync_tracking.py` writes them, `update_burndown.py` reads them, `sprint-monitor` reads them. Non-atomic writes here are a real data corruption path.

---

### VC-002: find_milestone() only queries open milestones

**Severity:** Medium
**Category:** API correctness / silent data loss
**Location:** `find_milestone()`, line 1176–1177

**Problem:** The GitHub Milestones API defaults to `state=open`. The query URL does not include `state=all`:
```python
milestones = gh_json([
    "api", "repos/{owner}/{repo}/milestones?per_page=100", "--paginate",
])
```

When a milestone is closed (normal end-of-sprint flow), `find_milestone()` returns `None`. This silently breaks `sync_tracking.py` (can't reconcile issues), `update_burndown.py` (can't build burndown), `sprint_analytics.py` (can't compute velocity), and `check_status.py` (can't check milestone progress). All callers handle `None` return by skipping work, so there's no crash — just silently stale data.

**Evidence:** GitHub API docs: "Lists milestones for a repository. `state` - Filter milestones by state. Default: `open`."

**Fix:** Add `&state=all` to the query URL or pass `?state=all&per_page=100`.

---

### VC-003: read_tf() crashes on non-numeric sprint values

**Severity:** Low
**Category:** Unhandled exception
**Location:** `read_tf()`, line 1122

**Problem:** `tf.sprint = int(v("sprint") or "0")` will raise `ValueError` if the sprint field contains a non-integer string (e.g., `"1.5"`, `"one"`, `"sprint-3"`). The `safe_int()` function exists at line 34 specifically for defensive integer extraction but is not used here.

**Evidence:**
```python
# Line 34 — defensive version:
def safe_int(value: str) -> int:
    m = re.match(r'(\d+)', str(value).strip())
    return int(m.group(1)) if m else 0

# Line 1122 — bare int():
tf.sprint = int(v("sprint") or "0")
```

A manually edited or corrupted tracking file with `sprint: two` would crash every script that calls `read_tf()` on it.

---

### VC-004: gh() does not catch FileNotFoundError when gh CLI is missing

**Severity:** Low
**Category:** Error handling gap
**Location:** `gh()`, line 68–78

**Problem:** When the `gh` CLI is not installed, `subprocess.run(["gh", ...])` raises `FileNotFoundError`. The function catches `TimeoutExpired` and checks `returncode`, but `FileNotFoundError` propagates unhandled. Callers that catch `RuntimeError` (e.g., `list_milestone_issues` at line 1201, `kanban.py` lines 412/479) will not catch this.

**Evidence:**
```python
def gh(args: list[str], timeout: int = 60) -> str:
    try:
        r = subprocess.run(["gh", *args], ...)
    except subprocess.TimeoutExpired:
        raise RuntimeError(...)  # Only TimeoutExpired caught
    # FileNotFoundError from missing 'gh' binary propagates uncaught
```

The prerequisites checklist (`skills/sprint-setup/references/prerequisites-checklist.md`) checks for `gh` before any skill runs, so this is a "belt without suspenders" issue rather than a likely crash. But any script run outside the normal skill lifecycle would get an unhelpful traceback.

---

### VC-005: TOML parser crashes with unhelpful error on key-then-section conflicts

**Severity:** Low
**Category:** Parser robustness
**Location:** `_set_nested()` line 439–444, section header handling line 182–186

**Problem:** If a TOML file defines a key as a scalar and then tries to use it as a section header (or vice versa), the parser crashes with an `AttributeError` from `setdefault()` on a non-dict type, or a `TypeError` from item assignment on a string. The error message gives no context about the TOML conflict.

**Evidence:** Input that triggers it:
```toml
[project]
name = "foo"
[project.name]
x = 1
```
Line 185: `current_section = current_section.setdefault(part, {})` — when `current_section["name"]` is `"foo"` (a string), `.setdefault` returns `"foo"`, and the next iteration tries `.setdefault` on a string, raising `AttributeError: 'str' object has no attribute 'setdefault'`.

This is malformed TOML (the spec forbids it), so the parser is right to reject it. The issue is the error quality — a `ValueError` with a message like "key 'name' already defined as a value, cannot use as section" would be far more helpful than `AttributeError`.

---

### VC-006: atomic_write_text() leaks .tmp files on write failure

**Severity:** Low
**Category:** Resource leak
**Location:** `atomic_write_text()`, line 1138–1141

**Problem:** If `tmp.write_text()` raises (disk full, permission error, encoding error), the `.tmp` file is left on disk. There is no `try/finally` to clean up.

**Evidence:**
```python
def atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(content, encoding="utf-8")  # If this fails...
    os.rename(str(tmp), str(path))             # ...tmp file remains
```

Additionally, `path.with_suffix(".tmp")` replaces the existing suffix, so `foo.md` uses `foo.tmp`. If concurrent calls target different files with the same stem but different extensions (unlikely but possible), they'd collide on the same `.tmp` file.

---

### VC-007: _parse_value() silently misparses strings with interior unescaped quotes

**Severity:** Low
**Category:** TOML parser correctness
**Location:** `_parse_value()`, line 345–346

**Problem:** The string detection logic `raw.startswith('"') and raw.endswith('"')` does not verify that the opening and closing quotes are a matched pair. A malformed value like `"hello"world"` passes the check (starts and ends with `"`), and `raw[1:-1]` produces `hello"world` — silently dropping the structural error.

**Evidence:**
```python
# Line 345-346:
if len(raw) >= 2 and raw.startswith('"') and raw.endswith('"'):
    return _unescape_toml_string(raw[1:-1])
```

Input `"hello"world"` → `raw[1:-1]` = `hello"world` → unescaped as-is → returned as `hello"world`. The TOML spec would reject this as a syntax error (unescaped `"` inside a basic string).

In practice, this only matters if users manually edit `project.toml` with a typo. The parser is documented as "minimal subset" and this is consistent with its lenient philosophy, but it masks typos that a stricter parser would catch.

---

### VC-008: _unescape_toml_string() reports truncated \u as "unknown escape"

**Severity:** Informational
**Category:** Misleading diagnostics
**Location:** `_unescape_toml_string()`, line 301–314

**Problem:** When a `\u` escape appears at the end of a string without enough characters for the 4 hex digits (e.g., `\u00`), the condition `i + 6 <= len(s)` fails and execution falls through to the `else` branch at line 315, which warns about an "unknown TOML escape sequence `\u`". The escape isn't unknown — it's truncated. The diagnostic is misleading.

**Evidence:**
```python
elif nxt == 'u' and i + 6 <= len(s):  # Requires 4 hex digits after \u
    ...
elif nxt == 'U' and i + 10 <= len(s): # Requires 8 hex digits after \U
    ...
else:
    print(f"Warning: unknown TOML escape sequence '\\{nxt}' in string", ...)
```

A string ending in `\u00` triggers "unknown escape `\u`" instead of something like "truncated `\u` escape (need 4 hex digits, got 2)".

---

### VC-009: _split_array() applies backslash-escape logic outside string context

**Severity:** Informational
**Category:** Parser correctness (theoretical)
**Location:** `_split_array()`, line 409–415

**Problem:** When the parser is NOT inside a string and encounters a quote character, it checks for trailing backslashes in the accumulated buffer to decide whether the quote starts a new string. This is semantically wrong — backslash escaping only applies inside strings in TOML. If the buffer happens to end with a backslash from a previous (non-string) element, the quote would be incorrectly treated as escaped.

**Evidence:**
```python
if not in_str and ch in ('"', "'"):
    n_bs = _count_trailing_backslashes(current, len(current))
    if n_bs % 2 == 0:
        in_str = True
        quote_char = ch
    current += ch
```

In practice, array elements are always quoted strings, integers, or booleans. A bare backslash in an array outside a string is malformed TOML, so this edge case is unreachable with valid input.

---

### VC-010: frontmatter_value() unescape map has asymmetry with _yaml_safe()

**Severity:** Informational
**Category:** Roundtrip fidelity (minor)
**Location:** `frontmatter_value()` line 945, `_yaml_safe()` lines 1093–1094

**Problem:** `frontmatter_value()` recognizes `\b` (backspace) in its unescape map, but `_yaml_safe()` never produces `\b` — it only escapes `\\`, `\"`, `\n`, `\r`, and `\t`. Similarly, `_yaml_safe()` escapes `\t`, and `frontmatter_value()` correctly unescapes it. The asymmetry means a manually-inserted `\b` in a tracking file would be silently consumed on read, but a programmatic value containing a literal backspace (`\x08`) would be written unquoted as a raw control character (since `_yaml_safe` doesn't check for `\b` in its `needs_quoting` logic).

Not a practical issue — backspace in story titles is deeply unlikely — but the asymmetry indicates the two functions were maintained independently.

---

### VC-011: _yaml_safe() does not quote values containing bare control characters

**Severity:** Informational
**Category:** Defensive coding gap
**Location:** `_yaml_safe()`, lines 1075–1090

**Problem:** The `needs_quoting` check covers `\n`, `\r`, `\t`, and various YAML-sensitive patterns, but does not check for other control characters (U+0000–U+001F excluding the three handled). A value containing `\x00` (null), `\x1b` (escape), `\x0c` (form feed), or `\x08` (backspace) would be written unquoted, producing invalid YAML frontmatter.

Not a realistic concern for sprint tracking data, but a completeness gap in the defensive quoting logic.

---

## Summary

| ID | Severity | Category | One-liner |
|----|----------|----------|-----------|
| VC-001 | Medium | Data integrity | `write_tf()` does non-atomic writes despite `atomic_write_text()` existing |
| VC-002 | Medium | API correctness | `find_milestone()` only queries open milestones, misses closed ones |
| VC-003 | Low | Unhandled exception | `read_tf()` crashes on non-numeric sprint values |
| VC-004 | Low | Error handling | `gh()` doesn't catch `FileNotFoundError` for missing CLI |
| VC-005 | Low | Parser robustness | TOML key/section type conflicts produce unhelpful crash |
| VC-006 | Low | Resource leak | `atomic_write_text()` leaks `.tmp` on write failure |
| VC-007 | Low | Parser correctness | `_parse_value()` silently accepts malformed quoted strings |
| VC-008 | Info | Diagnostics | Truncated `\u` escape reported as "unknown" |
| VC-009 | Info | Parser correctness | `_split_array()` applies escape logic outside string context |
| VC-010 | Info | Roundtrip fidelity | `frontmatter_value()` / `_yaml_safe()` escape asymmetry |
| VC-011 | Info | Defensive coding | `_yaml_safe()` doesn't quote bare control characters |

**2 Medium / 5 Low / 4 Informational** across 1245 lines of hub infrastructure code.

The two medium findings are the actionable ones. VC-001 is a straightforward fix (swap `path.write_text` for `atomic_write_text` in `write_tf`). VC-002 needs `&state=all` appended to the milestones API URL. Both are one-line changes with no architectural implications.

The TOML parser is surprisingly solid given its "minimal subset" mandate. The string-matching leniency (VC-007) is a conscious design choice documented in the code. The escape handling (VC-008, VC-009) is theoretical — you'd need deliberately adversarial input to trigger either.
