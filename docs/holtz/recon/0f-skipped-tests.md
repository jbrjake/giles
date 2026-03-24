# Step 0f: Skipped Tests

**Run:** 6
**Date:** 2026-03-23

## Conditional Skips (2)

1. `tests/test_check_lint_inventory.py:83` — `self.skipTest("no Makefile")` — skips if Makefile is absent (integration guard)
2. `tests/test_golden_run.py:116` — `self.skipTest(...)` — conditional on golden recording state

## Unconditional Skips

None.

## Assessment

Both skips are conditional environment guards, not disabled tests. No test debt.
