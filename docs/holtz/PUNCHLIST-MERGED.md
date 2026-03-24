# Holtz Punchlist — Run 6 (Merged)

**Project:** giles
**Date:** 2026-03-23
**Merge source:** Holtz PUNCHLIST.md (1 item) + Justine PUNCHLIST.md (3 items)

## Summary

| Severity | Open | Resolved | Deferred |
|----------|------|----------|----------|
| CRITICAL | 0 | 0 | 0 |
| HIGH | 0 | 1 | 0 |
| MEDIUM | 0 | 1 | 0 |
| LOW | 0 | 1 | 0 |

## Patterns

(none — all findings are in the same new file, no cross-codebase pattern)

## Items

### BH-001: test_main_returns_one_when_missing doesn't test main()
<!-- Was: Holtz BH-001 + Justine BJ-001 -->
**Severity:** HIGH
**Category:** test/bogus
**Location:** `tests/test_check_lint_inventory.py:104-124`
**Status:** RESOLVED
**Lens:** component
**Predicted:** Prediction 1 (confidence: HIGH)
**Found by:** both auditors
**Severity disagreement:** Holtz=MEDIUM, Justine=HIGH (using HIGH)

**Problem:** The test claimed to verify main() returning 1 but never called main(). Mock.patch replaced main with wraps=None, then the test called helper functions directly.

**Evidence:** See original punchlist entry above.

**Discovery Chain:** Prediction 1 flagged test quality → mock.patch(wraps=None) on main but never called → error exit path untested

**Acceptance Criteria:**
- [x] `main()` is actually called in the test and returns 1
- [x] The test exercises `main()` with a controlled root directory where scripts are missing
- [x] Test would fail if `main()` always returned 0

**Validation Command:**
```bash
.venv/bin/python -m pytest tests/test_check_lint_inventory.py::TestMain -v
```

**Resolution:** Refactored `main()` to accept optional `root` parameter (dependency injection). Replaced broken mock.patch test with direct `main(root=tmp_dir)` call that asserts return code is 1. Test now fails if main() always returns 0. 1234 tests pass, lint clean.

### BH-002: No test coverage for stale Makefile entries path
<!-- Was: Justine BJ-002 -->
**Severity:** MEDIUM
**Category:** test/missing
**Location:** `scripts/check_lint_inventory.py:70-74`
**Status:** RESOLVED
**Lens:** component
**Found by:** Justine only

**Problem:** The stale entries path (Makefile references non-existent scripts) was untested.

**Discovery Chain:** read main() logic → stale entries return 0 → grep test for "stale" → zero matches

**Acceptance Criteria:**
- [x] Test creates a temp filesystem + Makefile with py_compile entries for non-existent files
- [x] Test verifies main() returns 0 for stale-only case (documenting current behavior)

**Validation Command:**
```bash
.venv/bin/python -m pytest tests/test_check_lint_inventory.py::TestMain::test_main_returns_zero_for_stale_only -v
```

**Resolution:** Added `test_main_returns_zero_for_stale_only` test using the new `root` parameter. Test verifies stale-only case returns 0 (warning, not error). 1234 tests pass.

### BH-003: extract_lint_files regex matches py_compile in Makefile comments
<!-- Was: Justine BJ-003 -->
**Severity:** LOW
**Category:** bug/logic
**Location:** `scripts/check_lint_inventory.py:25`
**Status:** RESOLVED
**Determinism:** deterministic
**Lens:** data-flow
**Found by:** Justine only

**Problem:** The regex matched py_compile in comment lines, falsely counting commented-out entries as covered.

**Discovery Chain:** read regex → no line filtering → test with `#` prefix → comment content matches

**Acceptance Criteria:**
- [x] Pre-filtering excludes Makefile comment lines (lines where first non-whitespace is `#`)
- [x] Test verifies commented-out py_compile lines are not matched

**Validation Command:**
```bash
.venv/bin/python -m pytest tests/test_check_lint_inventory.py::TestExtractLintFiles::test_ignores_commented_py_compile_lines -v
```

**Resolution:** Rewrote `extract_lint_files` to process line-by-line, skipping lines where `lstrip().startswith("#")`. Added `test_ignores_commented_py_compile_lines` test. 1234 tests pass, lint clean.
