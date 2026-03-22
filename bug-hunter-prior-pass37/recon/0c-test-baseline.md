# 0c — Test Baseline

**Date:** 2026-03-21
**Pass:** Bug Hunter 37, Phase 0c

## Test Framework

| Item | Value |
|------|-------|
| Runner | pytest 9.0.2 |
| Python | 3.10.15 |
| Plugins | hypothesis 6.151.9, pytest-cov 7.0.0 |
| Dev deps | `requirements-dev.txt` (pytest, pytest-cov, jq, hypothesis) |
| Venv | `.venv/` managed via Makefile |
| Config | `tests/conftest.py` (sys.path setup, jq import guard) |
| No `pyproject.toml`, `tox.ini`, `setup.cfg`, or `pytest.ini` | Makefile is the sole runner config |

## Makefile Targets

| Target | Scope |
|--------|-------|
| `make test` | `pytest tests/ -v` (all) |
| `make test-unit` | `test_gh_interactions.py` only |
| `make test-integration` | `test_lifecycle.py`, `test_hexwise_setup.py` |
| `make test-golden` | `test_golden_run.py` |
| `make test-golden-record` | `GOLDEN_RECORD=1` re-record snapshots |
| `make lint` | `py_compile` on 19 scripts + `validate_anchors.py` run |

## Full Suite Results

| Metric | Value |
|--------|-------|
| Total collected | 1178 |
| Passed | 1178 |
| Failed | 0 |
| Skipped | 0 |
| Errors | 0 |
| Subtests passed | 19 |
| Runtime (no cov) | 17.15s |
| Runtime (with cov) | 20.32s |

## Coverage Summary

| Metric | Value |
|--------|-------|
| Total statements | 5305 |
| Missed statements | 916 |
| Overall coverage | 83% |

### Per-File Coverage

| File | Stmts | Miss | Cover |
|------|-------|------|-------|
| `scripts/validate_config.py` | 604 | 32 | 95% |
| `scripts/sprint_init.py` | 649 | 67 | 90% |
| `scripts/traceability.py` | 105 | 11 | 90% |
| `scripts/sprint_analytics.py` | 131 | 14 | 89% |
| `skills/sprint-release/scripts/release_gate.py` | 386 | 42 | 89% |
| `skills/sprint-run/scripts/sync_tracking.py` | 152 | 16 | 89% |
| `scripts/validate_anchors.py` | 174 | 21 | 88% |
| `scripts/team_voices.py` | 57 | 7 | 88% |
| `scripts/commit.py` | 73 | 10 | 86% |
| `scripts/sync_backlog.py` | 143 | 20 | 86% |
| `scripts/manage_sagas.py` | 160 | 23 | 86% |
| `skills/sprint-setup/scripts/setup_ci.py` | 165 | 23 | 86% |
| `scripts/kanban.py` | 402 | 66 | 84% |
| `scripts/manage_epics.py` | 235 | 46 | 80% |
| `skills/sprint-setup/scripts/bootstrap_github.py` | 196 | 39 | 80% |
| `skills/sprint-setup/scripts/populate_issues.py` | 321 | 71 | 78% |
| `skills/sprint-monitor/scripts/check_status.py` | 350 | 84 | 76% |
| `scripts/sprint_teardown.py` | 311 | 75 | 76% |
| `skills/sprint-run/scripts/update_burndown.py` | 98 | 25 | 74% |
| `scripts/test_coverage.py` | 96 | 31 | 68% |
| `scripts/test_categories.py` | 103 | 34 | 67% |
| `scripts/gap_scanner.py` | 94 | 31 | 67% |
| `scripts/risk_register.py` | 135 | 49 | 64% |
| `scripts/history_to_checklist.py` | 57 | 22 | 61% |
| `scripts/smoke_test.py` | 60 | 26 | 57% |
| `scripts/assign_dod_level.py` | 48 | 31 | 35% |

## Test Files (by test count, descending)

| File | Tests |
|------|-------|
| `tests/test_sprint_runtime.py` | 194 |
| `tests/test_pipeline_scripts.py` | 169 |
| `tests/test_verify_fixes.py` | 162 |
| `tests/test_hooks.py` | 113 |
| `tests/test_bugfix_regression.py` | 97 |
| `tests/test_kanban.py` | 85 |
| `tests/test_release_gate.py` | 74 |
| `tests/test_new_scripts.py` | 50 |
| `tests/test_gh_interactions.py` | 41 |
| `tests/test_property_parsing.py` | 38 |
| `tests/test_sprint_teardown.py` | 32 |
| `tests/test_validate_anchors.py` | 27 |
| `tests/test_hexwise_setup.py` | 27 |
| `tests/test_sync_backlog.py` | 19 |
| `tests/test_sprint_analytics.py` | 16 |
| `tests/test_lifecycle.py` | 15 |
| `tests/test_fakegithub_fidelity.py` | 15 |
| `tests/test_golden_run.py` | 4 |
| **Total** | **1178** |

## Low-Coverage Files (below 70%)

| File | Cover | Notes |
|------|-------|-------|
| `scripts/assign_dod_level.py` | 35% | `main()` and `assign_levels()` mostly untested |
| `scripts/smoke_test.py` | 57% | `main()` loop untested |
| `scripts/history_to_checklist.py` | 61% | `generate_checklists()` and `main()` untested |
| `scripts/risk_register.py` | 64% | CLI dispatch and `escalate_overdue()` untested |
| `scripts/gap_scanner.py` | 67% | `main()` and multi-sprint scan untested |
| `scripts/test_categories.py` | 67% | `main()` and report formatting untested |
| `scripts/test_coverage.py` | 68% | `main()` and project scan untested |
