# Recon 0c: Test Baseline

**Date:** 2026-03-16
**Runner:** pytest
**Python:** 3.10.15

## Results
- **696 tests collected, 696 passed** (0 fail, 0 skip, 0 xfail)
- **Runtime:** 10.61s (14.15s with coverage)
- **Overall coverage:** 83% (4105 stmts, 690 missed)

## Coverage by File (sorted by coverage, ascending — worst first)

| File | Stmts | Miss | Cover |
|------|-------|------|-------|
| bootstrap_github.py | 179 | 81 | 55% |
| update_burndown.py | 105 | 39 | 63% |
| test_coverage.py | 96 | 34 | 65% |
| populate_issues.py | 290 | 84 | 71% |
| sprint_teardown.py | 297 | 83 | 72% |
| manage_sagas.py | 153 | 31 | 80% |
| manage_epics.py | 241 | 43 | 82% |
| traceability.py | 106 | 17 | 84% |
| commit.py | 73 | 10 | 86% |
| sync_backlog.py | 130 | 17 | 87% |
| check_status.py | 250 | 32 | 87% |
| setup_ci.py | 160 | 21 | 87% |
| validate_anchors.py | 171 | 21 | 88% |
| sprint_init.py | 626 | 72 | 88% |
| team_voices.py | 56 | 7 | 88% |
| sprint_analytics.py | 131 | 14 | 89% |
| release_gate.py | 378 | 40 | 89% |
| validate_config.py | 467 | 33 | 93% |
| sync_tracking.py | 196 | 11 | 94% |

## Red Flags
1. **bootstrap_github.py at 55%** — nearly half the code untested. This creates GitHub resources.
2. **update_burndown.py at 63%** — large blocks of uncovered code (lines 125-141, 198-233)
3. **test_coverage.py at 65%** — the tool that checks test coverage is itself poorly covered (ironic)
4. **populate_issues.py at 71%** — creates GitHub issues, lots of untested paths
5. **sprint_teardown.py at 72%** — destructive operations with significant gaps
