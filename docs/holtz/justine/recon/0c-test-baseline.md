# 0c: Test Baseline (Run 6)

**Suite:** pytest + hypothesis
**Results:** 1232 passed, 0 failed, 0 skipped, 17.91s
**Coverage:** Not measured (no pytest-cov configured)

**New tests (since run 5):**
- `tests/test_check_lint_inventory.py` — 7 test methods across 4 classes

**Test file anti-pattern scan (new file only):**
- BJ-001: `test_main_returns_one_when_missing` is bogus — mocks function under test, never calls it
- No coverage of stale entry code path
- Remaining 6 tests are structurally sound (check values, not just types)
