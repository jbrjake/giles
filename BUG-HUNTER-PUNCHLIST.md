# Bug Hunter Punchlist — Pass 15
> Generated: 2026-03-16 | Project: giles | Baseline: 691 pass (post-P14) → 696 pass

## Summary
| Severity | Open | Resolved | Deferred |
|----------|------|----------|----------|
| CRITICAL | 0 | 1 | 0 |
| HIGH | 0 | 3 | 0 |
| MEDIUM | 0 | 4 | 0 |
| LOW | 0 | 3 | 0 |
| **Total** | **0** | **11** | **0** |

## Patterns

### Pattern: PAT-001: BH-014 regression cascade
**Instances:** P15-001
**Root Cause:** Moving code inside a conditional without checking all downstream effects. The TOML parse was moved inside `if _config is None` but the section/key validation loops were in the same block and got inadvertently gated.
**Systemic Fix:** Code movement refactors must trace all code paths through the modified block.
**Detection Rule:** `python -c "from validate_config import load_config, ConfigError; ..."` with incomplete TOML — must raise ConfigError.

### Pattern: PAT-002: Mutation-surviving test gaps
**Instances:** P15-003, P15-004, P15-005
**Root Cause:** Tests assert structural properties (counts, key existence) where exact values are deterministic and should be asserted. Enables mutations to survive because the wrong value still passes the structural check.
**Systemic Fix:** For deterministic test inputs, use assertEqual on computed values, not assertIn/assertGreater on structural properties.

---

## Items

### P15-001: validate_project skips section/key checks when _config provided
**Severity:** CRITICAL
**Category:** `bug/logic`
**Location:** `scripts/validate_config.py:439-466`
**Status:** ✅ RESOLVED

**Problem:** BH-014 moved TOML parsing inside `if _config is None` but left the "Required sections" and "Required keys" loops inside the same block. When `load_config()` called `validate_project(_config=config)`, all TOML validation was bypassed. A project.toml missing `[ci]` silently passed.

**Resolution:** Commit `6d07d3c`. Section/key checks now run when `toml_path.is_file() or _config is not None`.

---

### P15-002: _fm_val in update_burndown.py missing backslash unescape
**Severity:** LOW
**Category:** `bug/logic`
**Location:** `skills/sprint-run/scripts/update_burndown.py:151`
**Status:** ✅ RESOLVED

**Resolution:** Commit `6d07d3c`. Added `.replace('\\\\', '\\')` to match read_tf behavior.

---

### P15-003: sync_one never verifies tf.completed is populated
**Severity:** HIGH
**Category:** `test/missing`
**Location:** `tests/test_sprint_runtime.py:TestSyncOne`
**Status:** ✅ RESOLVED

**Problem:** Mutation analysis showed removing the `tf.completed = d` line would not be caught by any test.

**Resolution:** Commit `5915ff4`. Added `test_closed_issue_sets_completed_date`.

---

### P15-004: sync_one sprint mismatch untested
**Severity:** HIGH
**Category:** `test/missing`
**Location:** `tests/test_sprint_runtime.py:TestSyncOne`
**Status:** ✅ RESOLVED

**Resolution:** Commit `5915ff4`. Added `test_sprint_mismatch_updates_sprint`.

---

### P15-005: create_issue body never verified after creation
**Severity:** HIGH
**Category:** `test/shallow`
**Location:** `tests/test_lifecycle.py:test_06_populate_creates_issues`
**Status:** ✅ RESOLVED

**Problem:** Mutation analysis showed removing `format_issue_body()` call (empty issue bodies) would survive all tests.

**Resolution:** Commit `5915ff4`. Added body length and `"Story"` content assertions.

---

### P15-006: assert_files_match has no adversarial test
**Severity:** MEDIUM
**Category:** `test/missing`
**Location:** `tests/golden_replay.py`
**Status:** ✅ RESOLVED

**Problem:** The golden replay assertion function itself was never tested. `assert_files_match` could return `[]` unconditionally and all golden tests would pass.

**Resolution:** Commit `5915ff4`. Added TestAssertFilesMatchAdversarial with 3 tests: content mismatch detection, identical content (no diff), missing file detection.

---

### P15-007: FakeGitHub strict warnings never fail tests
**Severity:** MEDIUM
**Category:** `test/shallow`
**Location:** `tests/test_lifecycle.py:67`, `tests/test_hexwise_setup.py:330`
**Status:** ✅ RESOLVED

**Problem:** BH-011 fix printed strict warnings to stderr but never called `self.fail()`.

**Resolution:** Commit `aba1921`. tearDown now calls `self.fail()` on strict warnings.

---

### P15-008: reorder_stories duplicates separators on repeated reorders
**Severity:** MEDIUM
**Category:** `bug/logic`
**Location:** `scripts/manage_epics.py:325-336`
**Status:** ✅ RESOLVED

**Problem:** Raw section lines include trailing blank lines and `---` separators from parsing. Reassembly injects NEW separators, so each reorder accumulates 3 extra lines per section boundary.

**Resolution:** Commit `aba1921`. Strip trailing blank/separator lines from sections before reassembly.

---

### P15-009: _format_story_section allows newlines in headings
**Severity:** MEDIUM
**Category:** `bug/logic`
**Location:** `scripts/manage_epics.py:167-174`
**Status:** ✅ RESOLVED

**Problem:** Story ID and title from `json.loads` are interpolated into `### {sid}: {title}` with no sanitization. A newline in the title corrupts the heading.

**Resolution:** Commit `aba1921`. Strip `\n` and `\r` from sid and title.

---

### P15-010: Dead code in _parse_workflow_runs
**Severity:** LOW
**Category:** `design/dead-code`
**Location:** `scripts/sprint_init.py:217-220`
**Status:** ✅ RESOLVED

**Resolution:** Commit `aba1921`. Removed dead `if cmd in (">", ">-"): pass` block.

---

### P15-011: TOML _esc misses carriage return
**Severity:** LOW
**Category:** `bug/logic`
**Location:** `scripts/sprint_init.py:579-586`
**Status:** ✅ RESOLVED

**Resolution:** Commit `aba1921`. Added `.replace('\r', '\\r')`.
