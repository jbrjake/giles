# Holtz Audit Summary (Run 6 — Full Fresh)

**Date:** 2026-03-23
**Project:** giles (Claude Code agile sprint plugin)
**Mode:** Full fresh audit with adversarial self-play (Justine dispatched)
**Baseline:** 1232 tests, 0 failures, lint clean, 18.03s
**Final:** 1234 tests, 0 failures, lint clean, 18.06s

## Results

| Severity | Found | Resolved | Deferred |
|----------|-------|----------|----------|
| CRITICAL | 0 | 0 | 0 |
| HIGH | 1 | 1 | 0 |
| MEDIUM | 1 | 1 | 0 |
| LOW | 1 | 1 | 0 |
| **Total** | **3** | **3** | **0** |

**Tests:** 1232 → 1234 (+2 new tests for stale path and comment filtering)
**Lint:** clean
**Convergence:** 1 iteration

## Fixes

### BH-001: test_main_returns_one_when_missing is bogus (HIGH)
The test for `check_lint_inventory.main()` returning 1 used `mock.patch.object(main, wraps=None)` but never called `main()`. It tested helper functions already covered elsewhere. Refactored `main()` to accept optional `root` parameter (dependency injection); replaced broken mock test with direct `main(root=tmp_dir)` call that asserts return code 1. Found by both auditors.

### BH-002: Stale Makefile entries path untested (MEDIUM)
The code path for stale entries (Makefile references non-existent scripts) returned 0 with a warning but had no test coverage. Added `test_main_returns_zero_for_stale_only` to document and protect this behavior. Found by Justine only.

### BH-003: extract_lint_files matches py_compile in comments (LOW)
The regex `py_compile\s+(\S+\.py)` matched commented-out Makefile lines (`# py_compile scripts/old.py`), falsely inflating the "covered" set. Rewrote to process line-by-line, skipping comment lines. Added `test_ignores_commented_py_compile_lines`. Found by Justine only.

## Adversarial Self-Play

| Classification | Count |
|---------------|-------|
| Agreement | 1 (BH-001) |
| Holtz-only | 0 |
| Justine-only | 2 (BH-002, BH-003) |
| Severity disagreement | 1 (BH-001: Holtz=MEDIUM, Justine=HIGH) |
| Contradictory | 0 |

Justine's breadth-first audit caught 2 findings Holtz noted but did not escalate — the stale path and comment regex. The severity disagreement on BH-001 was resolved in Justine's favor (test/bogus is more accurate than test/shallow for a test that mocks the function under test).

## Prediction Accuracy

| Confidence | Predicted | Confirmed | Accuracy |
|------------|-----------|-----------|----------|
| HIGH | 1 | 1 | 100% |
| MEDIUM | 1 | 0 | 0% |
| LOW | 2 | 0 | 0% |
| **Total** | **4** | **1** | **25%** |

The HIGH prediction targeted the new test file's mock.patch issue — confirmed as BH-001. The MEDIUM and LOW predictions targeted edge cases in mature, well-tested code — unconfirmed as expected. On mature codebases, predictions are most valuable for new code.

## Assessment

Six Holtz runs have now resolved 25 findings total. This run's 3 findings were all in `check_lint_inventory.py` — the only new code since run 5. The existing codebase (9,700+ LOC across 31 scripts) produced zero findings from either auditor, confirming the convergence established in runs 1-5.

The persistent gap identified in runs 1 and 5 (Makefile lint inventory validation) is now fully automated and hardened. PAT-001 (batch addition without full wiring) is mitigated by the automated check.

## Recommendation

**Tactical:** None — the only recurring recommendation (lint inventory check) is now implemented and hardened.

**Strategic:** The codebase is mature and well-defended. Six converged Holtz audits + 39 bug-hunter passes have addressed every major bug class. Future audits should focus on new code additions — that's where the remaining value lies.
