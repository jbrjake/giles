# Phase 0c — Test Baseline

**Date:** 2026-03-21
**Commit:** 65636ca (main)

## Test Framework

- **Runner:** pytest 9.0.2
- **Python:** 3.10.15
- **Plugins:** hypothesis 6.151.9, cov 7.0.0
- **Config files:** None (no pytest.ini, pyproject.toml, setup.cfg, or tox.ini). Only `ruff.toml` exists for linting.
- **conftest.py:** Adds all script directories to sys.path; enforces `jq` Python package availability.

## Results Summary

| Metric       | Value    |
|-------------|----------|
| Total tests  | 1182     |
| Passed       | 1182     |
| Failed       | 0        |
| Skipped      | 0        |
| Errors       | 0        |
| Subtests     | 19 (all passed) |
| Warnings     | 0        |
| Runtime      | ~17s     |

**All 1182 tests pass. Zero failures, zero skips, zero warnings.**

## Coverage

**Overall: 83% (5314 statements, 914 missed)**

| Script | Stmts | Miss | Cover |
|--------|-------|------|-------|
| `scripts/validate_config.py` | 609 | 32 | 95% |
| `scripts/sprint_init.py` | 652 | 65 | 90% |
| `scripts/traceability.py` | 105 | 11 | 90% |
| `skills/sprint-release/scripts/release_gate.py` | 388 | 42 | 89% |
| `scripts/sprint_analytics.py` | 131 | 14 | 89% |
| `skills/sprint-run/scripts/sync_tracking.py` | 152 | 16 | 89% |
| `scripts/validate_anchors.py` | 174 | 21 | 88% |
| `scripts/team_voices.py` | 57 | 7 | 88% |
| `scripts/commit.py` | 73 | 10 | 86% |
| `scripts/sync_backlog.py` | 143 | 20 | 86% |
| `scripts/manage_sagas.py` | 160 | 23 | 86% |
| `skills/sprint-setup/scripts/setup_ci.py` | 165 | 23 | 86% |
| `scripts/kanban.py` | 402 | 66 | 84% |
| `skills/sprint-setup/scripts/bootstrap_github.py` | 196 | 39 | 80% |
| `scripts/manage_epics.py` | 235 | 46 | 80% |
| `skills/sprint-setup/scripts/populate_issues.py` | 321 | 71 | 78% |
| `skills/sprint-monitor/scripts/check_status.py` | 349 | 84 | 76% |
| `scripts/sprint_teardown.py` | 311 | 75 | 76% |
| `skills/sprint-run/scripts/update_burndown.py` | 98 | 25 | 74% |
| `scripts/test_coverage.py` | 96 | 31 | 68% |
| `scripts/gap_scanner.py` | 94 | 31 | 67% |
| `scripts/test_categories.py` | 103 | 34 | 67% |
| `scripts/risk_register.py` | 135 | 49 | 64% |
| `scripts/history_to_checklist.py` | 57 | 22 | 61% |
| `scripts/smoke_test.py` | 60 | 26 | 57% |
| `scripts/assign_dod_level.py` | 48 | 31 | 35% |

### Low-coverage scripts (below 70%)

- `scripts/assign_dod_level.py` — 35% (mainly `main()` and `assign_levels()` uncovered)
- `scripts/smoke_test.py` — 57% (end-to-end `main()` and `write_history()`)
- `scripts/history_to_checklist.py` — 61% (`generate_checklists()` and `main()`)
- `scripts/risk_register.py` — 64% (`main()` and most CLI subcommands)
- `scripts/gap_scanner.py` — 67% (`main()` and some scan logic)
- `scripts/test_categories.py` — 67% (`main()` and report formatting)
- `scripts/test_coverage.py` — 68% (`main()` and `check_test_coverage()`)

## Tests Per File

| Test file | Count |
|-----------|-------|
| `test_sprint_runtime.py` | 202 |
| `test_verify_fixes.py` | 163 |
| `test_pipeline_scripts.py` | 162 |
| `test_hooks.py` | 113 |
| `test_bugfix_regression.py` | 98 |
| `test_kanban.py` | 86 |
| `test_release_gate.py` | 74 |
| `test_new_scripts.py` | 50 |
| `test_gh_interactions.py` | 41 |
| `test_property_parsing.py` | 38 |
| `test_sprint_teardown.py` | 32 |
| `test_validate_anchors.py` | 27 |
| `test_hexwise_setup.py` | 27 |
| `test_sync_backlog.py` | 19 |
| `test_sprint_analytics.py` | 16 |
| `test_lifecycle.py` | 15 |
| `test_fakegithub_fidelity.py` | 15 |
| `test_golden_run.py` | 4 |

## Slowest Tests (>200ms)

| Test | Duration |
|------|----------|
| `test_safe_compile_rejects_non_a_backtracking` | 1.38s |
| `test_safe_compile_rejects_nested_quantifiers` | 1.33s |
| `test_redos_pattern_falls_back` | 1.32s |
| `test_smoke_timeout` | 1.00s |
| `test_multiple_sections_independent` (hypothesis) | 0.61s |
| `test_section_nesting` (hypothesis) | 0.50s |
| `test_single_kv_roundtrip` (hypothesis) | 0.47s |
| `test_valid_toml_never_raises` (hypothesis) | 0.46s |
| `test_standard_ids_extracted` (hypothesis) | 0.44s |
| `test_numeric_strings_always_quoted` (hypothesis) | 0.35s |
| `test_always_returns_int` (hypothesis) | 0.32s |
| `test_commit_failure_restores_toml` | 0.23s |
| `test_multiline_array` (hypothesis) | 0.22s |
| `test_concurrent_lock_serializes` | 0.21s |
| `test_every_script_main_has_test` | 0.20s |

Top 3 are ReDoS timeout tests (intentionally slow — they verify regex safety). The hypothesis property-based tests account for most of the remaining slow entries.

## Failing Tests

None. All 1182 tests pass.

## Notable Observations

1. **Zero warnings** — clean run with `-W all`.
2. **No test config file** — pytest runs with defaults; hypothesis uses default profile.
3. **19 subtests** — likely from `unittest.subTest()` usage inside some test methods.
4. **FakeGitHub** — tests use a custom GitHub CLI mock (`tests/fake_github.py`) rather than network calls.
5. **jq dependency enforced** — conftest.py raises `ImportError` if the `jq` Python package is missing (dev dependency only).
6. **Property-based tests** — hypothesis is used for TOML parsing, SP extraction, YAML safety, and story ID extraction.
