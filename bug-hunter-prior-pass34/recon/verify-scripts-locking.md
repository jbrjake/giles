# Verification: Scripts Locking & Atomicity Findings

**Date:** 2026-03-21
**Scope:** FINDING-44, FINDING-45, FINDING-1, DA-021/022, FINDING-20, FINDING-21, FINDING-29, FINDING-30

---

## 1. FINDING-44: 5 scripts use non-atomic Path.write_text()

**Verdict: PARTIALLY FIXED**

- `scripts/risk_register.py` -- **FIXED.** Now has `_atomic_write()` (lines 34-39) using temp+rename. All writes go through it (lines 55, 112, 136).
- `scripts/manage_epics.py` -- **STILL OPEN.** Uses bare `Path(path).write_text()` at lines 230, 268, 341, 365.
- `scripts/manage_sagas.py` -- **STILL OPEN.** Uses bare `Path(path).write_text()` at lines 175, 236, 269.
- `scripts/sprint_analytics.py` -- **STILL OPEN.** Uses `analytics_path.write_text()` at line 268 and `open(..., "a")` append at line 280. The initial file creation (write_text) is non-atomic. The append is inherently non-atomic but less risky.
- `scripts/smoke_test.py` -- **STILL OPEN.** Uses `history_path.write_text()` at line 79 (initial creation) and `open(..., "a")` append at line 86. Same pattern as sprint_analytics.

**Evidence:** Only `risk_register.py` has been converted to atomic writes. The other four scripts still use `Path.write_text()` directly.

---

## 2. FINDING-45: manage_epics.py and manage_sagas.py have no file locking

**Verdict: STILL OPEN**

Neither `scripts/manage_epics.py` nor `scripts/manage_sagas.py` imports or uses any locking mechanism (fcntl, filelock, or the `lock_story`/`lock_sprint` helpers from `kanban.py`). Concurrent writes to the same epic or saga file can cause data loss.

**Evidence:** Grep for `fcntl|filelock|lockf|flock|lock_story|lock_sprint` across `scripts/` only matches `kanban.py` and `assign_dod_level.py`. manage_epics and manage_sagas are absent.

---

## 3. FINDING-1: resolve_risk legacy row corruption

**Verdict: FIXED**

The `resolve_risk()` function (line 116) now uses `_split_table_row(line, unescape=False)` to preserve escaped pipes when splitting, and explicitly escapes `|` in the resolution text (line 130: `resolution.replace("|", "\\|")`). The row is reconstructed with `" | ".join(cells)` (line 132) from the raw (un-unescaped) cells, so previously escaped content is preserved.

**Evidence:** Lines 124, 130-132 show the correct pattern: split without unescaping, escape resolution text, rejoin.

---

## 4. DA-021 + DA-022: risk_register pipe escaping asymmetry

**Verdict: FIXED**

- `resolve_risk()` now escapes `|` in resolution text (line 130: `resolution_escaped = resolution.replace("|", "\\|")`).
- `_split_table_row()` (line 68) splits on unescaped pipes via `re.split(r'(?<!\\)\|', line)` and optionally unescapes `\\|` to `|` when `unescape=True` (line 81).
- `_parse_rows()` (line 85) calls `_split_table_row(line)` with default `unescape=True`, so parsed data contains clean `|` characters.
- `resolve_risk()` calls `_split_table_row(line, unescape=False)` for write-back, preserving escaping.
- `add_risk()` (line 109) escapes title: `title.replace("|", "\\|")`.

The read/write symmetry is correct: escaped pipes survive round-trips through parse and resolve.

**Evidence:** Lines 68-82 (split with regex and unescape flag), line 109 (add_risk escapes), line 124+130 (resolve_risk uses unescape=False and escapes resolution).

---

## 5. FINDING-20: manage_epics reorder_stories walk-back eats header blanks

**Verdict: FIXED**

The `reorder_stories()` function (line 273) walk-back loop at line 288 walks backward over blank lines and `---` separators. Previously this could consume header content separators. Now the function has been restructured:

- Line 288: `while stories_start > 0 and lines[stories_start - 1].strip() in ("", "---")`
- The walk-back only skips blank lines and `---` separators, which cannot be header *content* (headers are `| Field | Value |` table rows or `# Heading` lines).
- The comment at line 284 explains the intent: "Strip all separator lines and re-emit them consistently to ensure idempotency."
- All stories are re-emitted with consistent separators (lines 330-333), so even if the walk-back removes extra blanks between header and first story, the output is correct.

However, the walk-back has **no explicit lower bound** beyond `stories_start > 0`. If the header itself ends with blank lines (which is normal for markdown), those blanks will be consumed. This is actually correct behavior here because the function re-emits separators before each story (line 330-332). The header content (table rows, headings) won't match `strip() in ("", "---")` so they are safe.

**Verdict: FIXED** -- the walk-back cannot eat header content because it only matches empty lines and `---` separators. Header table rows and headings don't match those patterns.

---

## 6. FINDING-21: manage_epics renumber_stories replaces inside code blocks

**Verdict: STILL OPEN**

The `renumber_stories()` function (line 345) skips `### ` headings (line 360) but applies `re.sub` to all other lines (line 364), including lines inside fenced code blocks (` ``` `). A story ID like `US-0102` appearing in a code example would be incorrectly replaced.

**Evidence:** Lines 359-364:
```python
for line in lines:
    if line.startswith("### "):
        new_lines.append(line)
    else:
        new_lines.append(re.sub(rf'\b{re.escape(old_id)}\b', lambda m: replacement, line))
```
No check for fenced code block context.

---

## 7. FINDING-29: gap_scanner git diff fails silently for deleted branches

**Verdict: STILL OPEN**

The `story_touches_entry_point()` function (line 56) runs `git diff --name-only HEAD...{branch}` and catches all exceptions with a bare `except Exception: pass` (lines 81-82). If the branch has been deleted, `git diff` returns a non-zero exit code, and `result.returncode != 0` causes the function to skip the diff check silently. The function returns `None` (no match), which could cause a false gap detection.

**Evidence:** Lines 71-82:
```python
try:
    result = subprocess.run(
        ["git", "diff", "--name-only", f"HEAD...{branch}"],
        capture_output=True, text=True, timeout=10,
    )
    if result.returncode == 0:
        changed_files = result.stdout
        for ep in entry_points:
            if ep in changed_files
                return ep
except Exception:
    pass
```
No logging or warning when git diff fails.

---

## 8. FINDING-30: gap_scanner entry point substring matching

**Verdict: STILL OPEN**

The `story_touches_entry_point()` function uses plain substring matching (`if ep in body` at line 67, `if ep in changed_files` at line 79). This means:
- An entry point `"main.py"` would match `"domain.py"` (because `"main.py"` is a substring of `"domain.py"` -- actually no, but `"main"` as entry point would match `"domain"`).
- More realistically, entry point `"src/app"` would match `"src/app_test.py"` or `"src/application/utils.py"`.
- In the git diff output (line 79), `changed_files` is a newline-separated list of paths, so `ep in changed_files` does substring matching across the entire output string, not per-line matching.

**Evidence:** Lines 65-67 and 77-79 use plain `in` operator for substring checks rather than path-aware or line-by-line matching.

---

## Summary

| Finding | Status |
|---------|--------|
| FINDING-44 (non-atomic writes) | PARTIALLY FIXED -- only risk_register.py converted; manage_epics, manage_sagas, sprint_analytics, smoke_test still use Path.write_text() |
| FINDING-45 (no file locking) | STILL OPEN -- manage_epics.py and manage_sagas.py have no locking |
| FINDING-1 (resolve_risk row corruption) | FIXED |
| DA-021/022 (pipe escaping asymmetry) | FIXED |
| FINDING-20 (reorder walk-back eats headers) | FIXED |
| FINDING-21 (renumber replaces in code blocks) | STILL OPEN |
| FINDING-29 (git diff silent failure) | STILL OPEN |
| FINDING-30 (entry point substring matching) | STILL OPEN |

**Score: 3 fixed, 1 partially fixed, 4 still open.**
