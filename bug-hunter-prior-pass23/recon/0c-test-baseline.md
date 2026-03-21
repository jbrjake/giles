# 0c — Test Baseline

**Date:** 2026-03-18
**Python:** 3.10.15
**pytest:** 9.0.2 (plugins: hypothesis-6.151.9, cov-7.0.0)

---

## Test Results

| Metric | Value |
|--------|-------|
| **Passed** | 854 |
| **Failed** | 0 |
| **Skipped** | 0 |
| **Errors** | 0 |
| **Subtests passed** | 19 |
| **Time** | 13.95s (verbose) / 17.23s (with coverage) |

All 854 tests pass. Zero failures, zero errors, zero skips.

---

## Coverage Summary (scripts/ directory)

| File | Stmts | Miss | Cover |
|------|-------|------|-------|
| validate_config.py | 582 | 28 | **95%** |
| sprint_analytics.py | 129 | 13 | **90%** |
| sprint_init.py | 635 | 72 | **89%** |
| sync_backlog.py | 136 | 17 | **88%** |
| team_voices.py | 56 | 7 | **88%** |
| validate_anchors.py | 171 | 21 | **88%** |
| commit.py | 73 | 10 | **86%** |
| traceability.py | 105 | 17 | **84%** |
| kanban.py | 329 | 64 | **81%** |
| manage_epics.py | 224 | 42 | **81%** |
| manage_sagas.py | 140 | 31 | **78%** |
| sprint_teardown.py | 311 | 75 | **76%** |
| test_coverage.py | 96 | 31 | **68%** |
| **TOTAL** | **2987** | **428** | **86%** |

### Files Under 80% Coverage

| File | Cover | Notable gaps |
|------|-------|-------------|
| **test_coverage.py** | 68% | Lines 142-143, 158-181, 191-206, 210 — `scan_project_tests()` and `check_test_coverage()` main paths |
| **sprint_teardown.py** | 76% | Lines 112-113, 180-190, 222-279, 298-322, 351-388, 424-472, 487-497 — interactive confirmation, multi-file removal, empty-dir cleanup |
| **manage_sagas.py** | 78% | Lines 127-130, 261-291 — `update_team_voices()` and `main()` |

---

## Warnings

No pytest warnings were emitted during the test run.

---

## Failing / Erroring Tests

None.

---

## Notes

- The test suite is healthy: 100% pass rate, no flaky tests observed.
- Overall coverage at 86% is solid. Three files sit below 80%.
- `test_coverage.py` at 68% is the weakest — ironic for a coverage-checking script. The uncovered lines are the main scanning/reporting paths.
- `sprint_teardown.py` gaps are mostly in interactive/destructive code paths (confirmation prompts, actual file removal), which are harder to unit-test.
- `manage_sagas.py` gaps are in the `main()` CLI entry point and the `update_team_voices()` function.
