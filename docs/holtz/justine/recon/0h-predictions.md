# 0h: Predictions (Run 6)

## Prediction 1
**Target:** `tests/test_check_lint_inventory.py:104-124` (TestMain.test_main_returns_one_when_missing)
**Predicted Issue:** Bogus test — mocks function under test, never verifies return code
**Confidence:** HIGH
**Basis:** Code review during recon — mock.patch.object with wraps=None replaces main, test body calls component functions instead
**Lens:** component
**Graph Support:** test_check_lint_inventory -> check_lint_inventory:main edge noted as bogus
**Outcome:** CONFIRMED (BJ-001)

## Prediction 2
**Target:** `scripts/check_lint_inventory.py:70-78` (stale entry handling in main())
**Predicted Issue:** Untested code path — stale entries return 0 (success) with no test coverage
**Confidence:** HIGH
**Basis:** Grep for "stale" in test file returns zero matches; code path exits 0 on stale-only
**Lens:** component
**Graph Support:** —
**Outcome:** CONFIRMED (BJ-002)

## Prediction 3
**Target:** `scripts/check_lint_inventory.py:25` (extract_lint_files regex)
**Predicted Issue:** Regex matches py_compile in Makefile comments (false positives)
**Confidence:** MEDIUM
**Basis:** Regex `py_compile\s+(\S+\.py)` has no line-level filtering; tested with comment prefix
**Lens:** data-flow
**Graph Support:** —
**Outcome:** CONFIRMED (BJ-003)
