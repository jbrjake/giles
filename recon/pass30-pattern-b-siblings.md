# Pass 30 — Pattern B: Substring `in` false-positive siblings

**Pattern origin:** BH29-003 in `gap_scanner.py` where `if ep in body` matched
"main" inside "domain". Fixed to use `re.search(rf'\b{re.escape(ep)}\b', body)`.

Searched all `.py` files in `scripts/`, `.claude-plugin/hooks/`, and
`skills/*/scripts/` for uses of Python's `in` operator that do substring
matching on unstructured or semi-structured text where a short needle could
match inside a longer word.

---

## Findings

### 1. `gap_scanner.py:83` — entry point substring match on file paths

```python
if ep in changed_file:
```

**Context:** The body-text check on line 68 was fixed (BH29-003) to use
`re.search(rf'\b{re.escape(ep)}\b', body)`, but the file-path check six lines
later still uses `in`. Entry points are typically file paths like
`src/main.py`, but if configured as a bare name like `main`, it would match
`domain/main_handler.py` or `tests/containment.py`.

**False positive:** `entry_points = ["main"]` matches changed file
`src/domain/maintain.py`.

**Severity:** MEDIUM — entry points are typically full paths per the template
(`src/main.py`), so this is unlikely with well-configured projects but still
inconsistent with the body-text fix directly above it.

**File:** `/Users/jonr/Documents/non-nitro-repos/giles/scripts/gap_scanner.py`

---

### 2. `setup_ci.py:328` — `"type" in cmd_lower` matches substrings

```python
if "type" in cmd_lower or "mypy" in cmd_lower:
    return "Type Check"
```

**Context:** `_job_name_from_command()` derives a CI job name from a command
string. The word "type" is 4 characters and appears inside common words.

**False positive:** Command `npm run prototype` or `python typeset_docs.py`
would be named "Type Check". Command `cargo build --release-type=debug`
would also match.

**Severity:** LOW — cosmetic only (affects CI job display name, not behavior).
The function already uses `re.search(r'\btest\b', ...)` for "test" (BH24-037)
which shows awareness of this pattern, but "type" was not given the same
treatment.

**File:** `/Users/jonr/Documents/non-nitro-repos/giles/skills/sprint-setup/scripts/setup_ci.py`

---

### 3. `setup_ci.py:326` — `"lint" in cmd_lower` matches substrings

```python
if "lint" in cmd_lower:
    return "Lint"
```

**Context:** Same function. "lint" appears inside "splint", "flint", etc.

**False positive:** Command `flint check src/` would be labeled "Lint".

**Severity:** LOW — cosmetic. Less likely than "type" since "lint" rarely
appears as a substring in real CI commands. Note that "pylint", "eslint", and
"clippy" are checked first and short-circuit, so those specific cases are safe.

**File:** `/Users/jonr/Documents/non-nitro-repos/giles/skills/sprint-setup/scripts/setup_ci.py`

---

### 4. `setup_ci.py:335` — `"vet" in cmd_lower` matches substrings

```python
if "vet" in cmd_lower:
    return "Vet"
```

**Context:** Same function. "vet" is only 3 characters.

**False positive:** Command `go build -v ./...` won't match (no "vet"), but
a command like `prevent_regressions.sh` or `pivot_check` would. The most
realistic false positive is a path containing "veto" or "vetted".

**Severity:** LOW — cosmetic. The 3-char substring is concerning but "vet" in
a CI command string is unusual outside `go vet`.

**File:** `/Users/jonr/Documents/non-nitro-repos/giles/skills/sprint-setup/scripts/setup_ci.py`

---

### 5. `setup_ci.py:318` — `"fmt" in cmd_lower` matches substrings

```python
if "fmt" in cmd_lower or "format" in cmd_lower or "black" in cmd_lower:
    return "Format"
```

**Context:** Same function. "fmt" is only 3 characters.

**False positive:** A command with a path like `check_cfmt_output.sh` would
match. "format" could match `reformat_data.py` or `format_checker` (though
those are arguably formatting-related anyway).

**Severity:** LOW — cosmetic. "fmt" as a substring in non-formatting commands
is rare in practice.

**File:** `/Users/jonr/Documents/non-nitro-repos/giles/skills/sprint-setup/scripts/setup_ci.py`

---

### 6. `setup_ci.py:333` — `"audit" in cmd_lower` matches substrings

```python
if "audit" in cmd_lower:
    return "Audit"
```

**Context:** Same function. "audit" is 5 characters and unlikely to be a
substring of other words, but could match in paths or compound names.

**False positive:** Hard to construct a realistic one. Possibly `preaudit.sh`.

**Severity:** LOW — cosmetic and unlikely.

**File:** `/Users/jonr/Documents/non-nitro-repos/giles/skills/sprint-setup/scripts/setup_ci.py`

---

### 7. `session_context.py:114` — `"retro" in line.lower()` matches substrings

```python
if "retro" in line.lower() and (
    line.strip().startswith("-") or line.strip().startswith("*")
):
```

**Context:** `extract_dod_retro_additions()` scans definition-of-done.md for
bullet items containing the word "retro" to find retro-driven DoD additions.

**False positive:** A bullet point containing "retroactive", "retrospective",
or "retro-compatibility" would be matched even if it's not a retro-driven
addition. For example, `- Ensure retroactive compatibility with v1 API` would
be extracted as a retro addition.

**Severity:** MEDIUM — affects what gets injected into session context as
"retro action items". A false positive injects a misleading DoD item into the
agent's prompt, potentially affecting behavior.

**File:** `/Users/jonr/Documents/non-nitro-repos/giles/.claude-plugin/hooks/session_context.py`

---

### 8. `session_context.py:90` — `"Action Items" in line` matches substrings

```python
if "Action Items" in line and line.startswith("#"):
```

**Context:** `_parse_action_items()` scans retro.md for the action items
section heading. The combined check with `line.startswith("#")` makes this
much safer — it would need to be a heading containing "Action Items" as a
substring.

**False positive:** A heading like `## Non-Action Items Discussion` or
`## Sprint Action Items Review` would trigger section parsing.

**Severity:** LOW — headings in retro files follow a predictable template
format, and the extra `startswith("#")` guard makes this unlikely.

**File:** `/Users/jonr/Documents/non-nitro-repos/giles/.claude-plugin/hooks/session_context.py`

---

### 9. `sprint_teardown.py:179` — `"sprints_dir" in line` on TOML text

```python
if "sprints_dir" in line and "=" in line:
```

**Context:** Quick TOML parsing to find the `sprints_dir` config value. The
line is a single line from `project.toml`.

**False positive:** A TOML comment like `# old_sprints_dir = "archive"` would
match. So would a key like `extra_sprints_dir = "..."`.

**Severity:** LOW — the fallback behavior is just adding one more candidate
directory to check, and if the directory doesn't exist, nothing happens.
Still, an incorrect path extraction could silently use the wrong sprints dir.

**File:** `/Users/jonr/Documents/non-nitro-repos/giles/scripts/sprint_teardown.py`

---

## Patterns examined and excluded

The following patterns were examined but are NOT vulnerable:

- **`review_gate.py:225`** — `"gh" in command and "pr" in command and "merge" in command` — This is a fast pre-filter before calling `check_merge()` which uses `re.search(r'gh\s+pr\s+merge...')`. A false positive from the pre-filter is harmless because the real check uses proper regex.

- **`review_gate.py:237`** — `"git" in command and "push" in command` — Same pattern; `check_push()` → `_check_push_single()` does `parts[0] != "git" or parts[1] != "push"` as a proper check.

- **`release_gate.py:93`** — `"BREAKING CHANGE:" in body` — The trailing colon makes this specific enough. This follows the conventional commits spec literally.

- **`check_status.py:356,361`** — `"SMOKE PASS" in text` — Multi-word uppercase phrase with a space; false positive in prose is essentially impossible.

- **`validate_config.py:363`** — `if meta in raw` — Single metacharacters (`=`, `[`, `]`, etc.) checked against a TOML value string. These are character checks, not word checks.

- **`test_categories.py:61`** — `if dirname in parts` — Checks against `path.parts` (a tuple of path components), not against a string. This is exact element membership, not substring.

- **`traceability.py:159`** — `any(s in all_story_ids for s in data["stories"])` — Set membership check, not substring.

- **`manage_sagas.py:126,152,194,248`** — `if heading in ranges`, `"Sprint Allocation" not in section_ranges` — Dict membership checks.

- **`bootstrap_github.py:290`** — `"already_exists" in msg` — Matches GitHub API error message; unlikely false positive since the error string is distinctive.

- **`commit.py:133`** — `"No staged changes" in warning` — Matches a specific error message generated by the same codebase.

---

## Summary

| # | File | Line | Expression | Severity |
|---|------|------|-----------|----------|
| 1 | gap_scanner.py | 83 | `ep in changed_file` | MEDIUM |
| 2 | setup_ci.py | 328 | `"type" in cmd_lower` | LOW |
| 3 | setup_ci.py | 326 | `"lint" in cmd_lower` | LOW |
| 4 | setup_ci.py | 335 | `"vet" in cmd_lower` | LOW |
| 5 | setup_ci.py | 318 | `"fmt" in cmd_lower` | LOW |
| 6 | setup_ci.py | 333 | `"audit" in cmd_lower` | LOW |
| 7 | session_context.py | 114 | `"retro" in line.lower()` | MEDIUM |
| 8 | session_context.py | 90 | `"Action Items" in line` | LOW |
| 9 | sprint_teardown.py | 179 | `"sprints_dir" in line` | LOW |

**2 MEDIUM, 7 LOW.** No HIGH-severity findings.

The two MEDIUM findings (#1 and #7) are the most actionable:
- #1 is an inconsistency with the fix that was just applied (body uses regex,
  file paths still use `in`)
- #7 could inject misleading DoD items into agent prompts
