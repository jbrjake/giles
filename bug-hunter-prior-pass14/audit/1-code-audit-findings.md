# Phase 1-3: Manual Code Audit Findings (Pass 14)

## Source: Deep-read of all 19 production scripts

---

### F-001: release_gate.py — Local tag orphaned on push failure
**Severity:** CRITICAL
**Location:** `skills/sprint-release/scripts/release_gate.py:581-583`
**Bug:** When `git push origin main v{new_ver}` fails at line 581, only `_rollback_commit()` is called. The local tag created at line 566-573 is NOT deleted because `_rollback_tag()` is defined at line 587 — AFTER the push step. It's a nested function defined inside the else block, but too late in the code flow to be available when push fails.

**Impact:** Next release attempt fails with "tag already exists." Manual intervention required (`git tag -d v{ver}`). P12-001 fixed the rollback logic for the GitHub Release failure path but missed the push failure path.

**Evidence:** `_rollback_tag()` defined at line 587, but called only at line 636. Line 582 only calls `_rollback_commit()`. No `git tag -d` happens on push failure.

---

### F-002: release_gate.py — Partial push leaves ambiguous state
**Severity:** HIGH
**Location:** `skills/sprint-release/scripts/release_gate.py:577-584`
**Bug:** `git push origin main v{new_ver}` pushes BOTH branch+tag. If it returns non-zero after partially pushing (e.g., branch succeeded but tag didn't), `pushed_to_remote` stays False and `_rollback_commit()` does `git reset --hard`, creating local/remote divergence with no warning.

**Impact:** Silent local/remote divergence. Next push fails. Git requires `git pull --rebase` or force-push to resolve.

---

### F-003: validate_config.py — load_config() parses TOML twice
**Severity:** LOW
**Location:** `scripts/validate_config.py:601,610`
**Bug:** `validate_project()` at line 437 parses the TOML file. Then `load_config()` at line 610 parses it AGAIN. If the file is modified between the two reads (TOCTOU), validation applies to old content while config loads new content.

**Impact:** Negligible in practice (files don't change mid-call), but architecturally unclean. Could matter in concurrent tool invocations.

---

### F-004: setup_ci.py — _yaml_safe_command silently truncates multiline
**Severity:** MEDIUM
**Location:** `skills/sprint-setup/scripts/setup_ci.py:100-102`
**Bug:** If a TOML multiline string produces `check_commands` with embedded newlines, `_yaml_safe_command` silently keeps only the first line. No warning is emitted. The user gets a CI workflow that runs a partial command.

**Evidence:** Lines 100-102:
```python
if "\n" in command or "\r" in command:
    command = command.split("\n")[0].split("\r")[0]
```
No warning to stderr. No test for this truncation behavior.

---

### F-005: populate_issues.py — build_milestone_title_map silently overwrites
**Severity:** MEDIUM
**Location:** `skills/sprint-setup/scripts/populate_issues.py:310-337`
**Bug:** If two milestone files both contain `### Sprint 1:` sections, the `result[int(n)] = title` at line 332 silently overwrites the first title with the second. No warning. Issues created for Sprint 1 could get assigned to the wrong milestone title.

---

### F-006: sprint_init.py — deep doc TOML paths not escaped
**Severity:** LOW
**Location:** `scripts/sprint_init.py:632-642`
**Bug:** `generate_project_toml()` uses `esc()` for most values but not for deep doc paths (lines 632-642). A path containing quotes or backslashes would produce invalid TOML. Currently mitigated by hardcoded string values, but inconsistent.

---

### F-007: manage_sagas.py — duplicate section updates target wrong section
**Severity:** LOW
**Location:** `scripts/manage_sagas.py:143-147,255`
**Bug:** `_find_section_ranges` deduplicates headings with counter suffix (e.g., "Team Voices (2)"). But `update_team_voices()` looks for "Team Voices" exactly, so updates only affect the first section. The P12-035 fix prevents crashes but doesn't prevent silent data loss in duplicate sections.

---

### F-008: validate_config.py — 2 unreferenced anchors in CLAUDE.md
**Severity:** LOW
**Location:** Project-wide
**Finding:** `validate_anchors.py` reports 2 defined-but-unreferenced anchors:
- `§populate_issues._most_common_sprint`
- `§update_burndown.build_rows`
These were added as fixes to prior-pass issues but never wired into the CLAUDE.md or CHEATSHEET.md index.
