# 0c — Test Baseline

**Date:** 2026-03-16
**Suite:** `python -m pytest tests/ -v`
**Platform:** Python 3.10.15, pytest 9.0.2, hypothesis 6.151.9, pytest-cov 7.0.0, macOS Darwin 25.2.0

---

## Summary

| Metric | Value |
|--------|-------|
| Total tests | 773 |
| Passed | 773 |
| Failed | 0 |
| Skipped | 0 |
| Errors | 0 |
| Warnings | 0 (no pytest-level warnings emitted) |
| Wall time | 12.0s (without cov) / 15.2s (with cov) |
| Overall coverage | **85%** (635 of 4193 statements missed) |

All 773 tests pass. Zero failures, zero skips, zero collection warnings.

---

## Tests Per File

| File | Tests |
|------|------:|
| test_sprint_runtime.py | 168 |
| test_pipeline_scripts.py | 134 |
| test_verify_fixes.py | 104 |
| test_bugfix_regression.py | 93 |
| test_release_gate.py | 56 |
| test_gh_interactions.py | 40 |
| test_property_parsing.py | 36 |
| test_sprint_teardown.py | 32 |
| test_validate_anchors.py | 25 |
| test_hexwise_setup.py | 25 |
| test_sync_backlog.py | 18 |
| test_sprint_analytics.py | 15 |
| test_lifecycle.py | 13 |
| test_fakegithub_fidelity.py | 10 |
| test_golden_run.py | 4 |

---

## Coverage Report

| File | Stmts | Miss | Cover | Notes |
|------|------:|-----:|------:|-------|
| scripts/validate_config.py | 515 | 31 | 94% | Core library, well covered |
| scripts/sprint_init.py | 635 | 72 | 89% | Large file; gaps in scanner edge cases and deep-doc generation |
| scripts/sprint_analytics.py | 129 | 13 | 90% | `main()` and `format_report()` tails uncovered |
| scripts/commit.py | 73 | 10 | 86% | Some `run_commit` branches and `main()` exit paths |
| scripts/sync_backlog.py | 136 | 17 | 88% | Import fallback paths and `main()` CLI paths |
| scripts/team_voices.py | 56 | 7 | 88% | `main()` CLI path |
| scripts/validate_anchors.py | 171 | 21 | 88% | `main()` fix/check CLI branches |
| scripts/traceability.py | 105 | 17 | 84% | `format_report()` output and `main()` |
| scripts/manage_epics.py | 224 | 42 | 81% | `reorder_stories()`, `renumber_stories()`, some edge cases |
| scripts/manage_sagas.py | 140 | 31 | 78% | `update_epic_index()`, `update_team_voices()`, `main()` |
| scripts/sprint_teardown.py | 311 | 75 | 76% | Interactive confirmation paths, several `classify_entries` branches |
| scripts/test_coverage.py | 96 | 31 | **68%** | `check_test_coverage()` and `_parse_planned_tests()` internals |
| skills/sprint-run/scripts/sync_tracking.py | 203 | 17 | 92% | |
| skills/sprint-run/scripts/update_burndown.py | 102 | 25 | **75%** | `write_burndown()` and `update_sprint_status()` |
| skills/sprint-setup/scripts/bootstrap_github.py | 194 | 56 | **71%** | `create_persona_labels()`, `create_milestones_on_github()`, `main()` |
| skills/sprint-setup/scripts/populate_issues.py | 316 | 77 | **76%** | `create_issue()`, `format_issue_body()`, `main()` with live GH calls |
| skills/sprint-setup/scripts/setup_ci.py | 160 | 21 | 87% | |
| skills/sprint-monitor/scripts/check_status.py | 249 | 32 | 87% | `main()` and some `check_*` branches |
| skills/sprint-release/scripts/release_gate.py | 378 | 40 | 89% | `do_release()`, `write_version_to_toml()`, some gate internals |
| **TOTAL** | **4193** | **635** | **85%** | |

---

## Low-Coverage Files (below 80%)

These are the files with the weakest test coverage:

1. **`scripts/test_coverage.py`** — 68% (31 missed)
   - `check_test_coverage()` (lines 158-181) and main report formatting (lines 191-206) entirely uncovered.
   - The core logic that compares planned vs actual tests is untested end-to-end.

2. **`skills/sprint-run/scripts/update_burndown.py`** — 75% (25 missed)
   - `write_burndown()` file-writing logic (lines 198-233) and `update_sprint_status()` (line 240) uncovered.
   - `build_rows()` is well tested; the gap is the file I/O and sprint-status update path.

3. **`scripts/sprint_teardown.py`** — 76% (75 missed)
   - Interactive confirmation flows (lines 315-322, 351-388), safety-check branches for unknown file types, and the `main()` execution path.

4. **`skills/sprint-setup/scripts/populate_issues.py`** — 76% (77 missed)
   - `create_issue()` and `format_issue_body()` (which hit live GitHub), plus the `main()` entry point. Heavy reliance on mocked `gh` calls.

5. **`scripts/manage_sagas.py`** — 78% (31 missed)
   - `update_epic_index()`, `update_team_voices()`, and the CLI `main()` path.

6. **`skills/sprint-setup/scripts/bootstrap_github.py`** — 71% (56 missed)
   - `create_persona_labels()` (lines 20-41), `create_milestones_on_github()` (lines 318-332), and `main()`. These are the functions that make live `gh` API calls.

---

## Observations

1. **Clean baseline.** 773/773 pass with no warnings, no flaky tests, and no skips. The suite is deterministic and fast (12s).

2. **Coverage is solid at 85% overall.** The core library (`validate_config.py` at 94%) and the most complex runtime scripts (`sync_tracking.py` at 92%, `sprint_init.py` at 89%) are well covered.

3. **Coverage gaps concentrate in two patterns:**
   - **`main()` entry points** — many scripts have untested CLI dispatch. These are low-risk (argument parsing) but represent easy coverage wins.
   - **Live GitHub interaction code** — `bootstrap_github.py`, `populate_issues.py`, and `update_burndown.py` have functions that call `gh` directly. The test suite uses `FakeGitHub` mocking but doesn't exercise every code path through these functions.

4. **`scripts/test_coverage.py` at 68% is ironic** — the test-coverage checking tool has the lowest test coverage in the project. Its `check_test_coverage()` function (the main purpose of the script) is almost entirely untested.

5. **No property tests for the low-coverage files.** The `test_property_parsing.py` file (36 tests, using Hypothesis) covers TOML parsing well, but none of the low-coverage scripts have property-based tests.

6. **Test distribution is uneven.** `test_sprint_runtime.py` (168 tests) and `test_pipeline_scripts.py` (134 tests) account for 39% of all tests. Several scripts are tested only through integration-style tests in `test_verify_fixes.py`.
