# 0c - Test Baseline

## Summary

| Metric | Value |
|--------|-------|
| Total tests | 889 |
| Passed | 889 |
| Failed | 0 |
| Skipped | 0 |
| Errors | 0 |
| Warnings | 6 |
| Subtests passed | 19 |
| Wall time | ~15s |
| Overall coverage | **85%** (4576 stmts, 688 missed) |

All 889 tests pass. Zero failures, zero errors, zero skips.

## Warnings (6 total)

All 6 warnings come from `tests/test_kanban.py` via `patch_gh` mock monitoring:

- 4 from `TestTransitionCommand` (test_transition_design_to_dev, test_transition_double_fault_restores_tf_status, test_transition_review_to_dev_rejection_cycle, test_transition_review_to_integration): `Mock for 'kanban.gh' was called 1 time(s) but call_args was never inspected`
- 2 from `TestAssignCommand` (test_assign_fresh_issue_no_header, test_assign_skips_body_when_already_assigned): `Mock for 'kanban.gh_json' was called 1 time(s) but call_args was never inspected`

These are intentional anti-pattern detection warnings from the `MonitoredMock` system in `gh_test_helpers.py`, not production code warnings.

## Slowest Tests (top 20 by duration)

| Duration | Test | Notes |
|---------:|------|-------|
| 1.38s | `test_verify_fixes::TestBH025BuildRowRegexSafety::test_safe_compile_rejects_non_a_backtracking` | ReDoS detection timeout |
| 1.34s | `test_verify_fixes::TestBH025BuildRowRegexSafety::test_safe_compile_rejects_nested_quantifiers` | ReDoS detection timeout |
| 1.33s | `test_verify_fixes::TestBH025BuildRowRegexSafety::test_redos_pattern_falls_back` | ReDoS detection timeout |
| 0.58s | `test_property_parsing::TestParseSimpleToml::test_multiple_sections_independent` | Hypothesis |
| 0.50s | `test_property_parsing::TestParseSimpleToml::test_section_nesting` | Hypothesis |
| 0.45s | `test_property_parsing::TestParseSimpleToml::test_valid_toml_never_raises` | Hypothesis |
| 0.44s | `test_property_parsing::TestParseSimpleToml::test_single_kv_roundtrip` | Hypothesis |
| 0.43s | `test_property_parsing::TestExtractStoryId::test_standard_ids_extracted` | Hypothesis |
| 0.37s | `test_property_parsing::TestYamlSafe::test_numeric_strings_always_quoted` | Hypothesis |
| 0.32s | `test_property_parsing::TestExtractSp::test_always_returns_int` | Hypothesis |
| 0.25s | `test_property_parsing::TestParseSimpleToml::test_multiline_array` | Hypothesis |
| 0.22s | `test_release_gate::TestDoReleaseIntegration::test_commit_failure_restores_toml` | Git integration |
| 0.20s | `test_kanban::TestFileLocking::test_concurrent_lock_serializes` | Concurrency test |
| 0.20s | `test_property_parsing::TestExtractStoryId::test_never_returns_empty` | Hypothesis |
| 0.19s | `test_property_parsing::TestYamlSafe::test_frontmatter_value_roundtrip` | Hypothesis |
| 0.19s | `test_hexwise_setup::TestHexwiseSetup::test_config_generation_succeeds` (setup) | Fixture setup |
| 0.19s | `test_hexwise_setup::TestHexwisePipeline::test_ci_workflow_has_cargo` | Pipeline |
| 0.18s | `test_property_parsing::TestYamlSafe::test_dangerous_chars_get_quoted` | Hypothesis |
| 0.18s | `test_hexwise_setup::TestHexwisePipeline::test_state_dump` | Pipeline |
| 0.18s | `test_golden_run::TestGoldenRun::test_golden_full_setup_pipeline` | Golden run |

**Observation**: The 3 slowest tests (~1.3s each) are ReDoS regex safety tests that intentionally trigger timeout-based detection. The next tier (0.3-0.6s) is Hypothesis property-based tests doing many iterations. Everything else is under 0.25s.

## Coverage Per Module

| Module | Stmts | Miss | Cover |
|--------|------:|-----:|------:|
| `scripts/validate_config.py` | 597 | 33 | **94%** |
| `scripts/sprint_analytics.py` | 129 | 13 | 90% |
| `scripts/traceability.py` | 105 | 11 | 90% |
| `scripts/sprint_init.py` | 635 | 72 | 89% |
| `skills/sprint-release/scripts/release_gate.py` | 382 | 42 | 89% |
| `skills/sprint-monitor/scripts/check_status.py` | 270 | 29 | 89% |
| `scripts/sync_backlog.py` | 136 | 17 | 88% |
| `scripts/team_voices.py` | 56 | 7 | 88% |
| `scripts/validate_anchors.py` | 171 | 21 | 88% |
| `skills/sprint-run/scripts/sync_tracking.py` | 144 | 18 | 88% |
| `scripts/commit.py` | 73 | 10 | 86% |
| `skills/sprint-setup/scripts/setup_ci.py` | 161 | 22 | 86% |
| `scripts/kanban.py` | 330 | 59 | 82% |
| `scripts/manage_epics.py` | 224 | 42 | 81% |
| `scripts/manage_sagas.py` | 142 | 31 | 78% |
| `skills/sprint-setup/scripts/populate_issues.py` | 320 | 74 | 77% |
| `scripts/sprint_teardown.py` | 311 | 75 | 76% |
| `skills/sprint-run/scripts/update_burndown.py` | 98 | 25 | 74% |
| `skills/sprint-setup/scripts/bootstrap_github.py` | 196 | 56 | 71% |
| `scripts/test_coverage.py` | 96 | 31 | 68% |

**Lowest coverage modules** (under 80%):
- `scripts/test_coverage.py` at 68% -- ironic given its purpose
- `skills/sprint-setup/scripts/bootstrap_github.py` at 71% -- main() and prerequisite checks
- `skills/sprint-run/scripts/update_burndown.py` at 74%
- `scripts/sprint_teardown.py` at 76%
- `skills/sprint-setup/scripts/populate_issues.py` at 77%
- `scripts/manage_sagas.py` at 78%

**Highest coverage modules** (90%+):
- `scripts/validate_config.py` at 94% -- core config layer, well-tested
- `scripts/sprint_analytics.py` at 90%
- `scripts/traceability.py` at 90%

## Test File Order (pytest collection order)

Tests are collected alphabetically by file, then by class/method within each file:
1. `test_bugfix_regression.py` (93 tests)
2. `test_fakegithub_fidelity.py` (15 tests)
3. `test_gh_interactions.py` (41 tests)
4. `test_golden_run.py` (4 tests)
5. `test_hexwise_setup.py` (25 tests)
6. `test_kanban.py` (62 tests)
7. `test_lifecycle.py` (13 tests)
8. `test_pipeline_scripts.py` (136 tests)
9. `test_property_parsing.py` (38 tests)
10. `test_release_gate.py` (59 tests)
11. `test_sprint_analytics.py` (16 tests)
12. `test_sprint_runtime.py` (175 tests)
13. `test_sprint_teardown.py` (32 tests)
14. `test_sync_backlog.py` (19 tests)
15. `test_validate_anchors.py` (26 tests)
16. `test_verify_fixes.py` (135 tests)
