# 0c - Test Baseline

## Test Run Summary

```
platform darwin -- Python 3.10.15, pytest-9.0.2, pluggy-1.6.0
plugins: hypothesis-6.151.9, cov-7.0.0
============================= 750 passed in 8.88s ==============================
```

| Metric | Count |
|--------|-------|
| Passed | 750 |
| Failed | 0 |
| Skipped | 0 |
| Errors | 0 |
| Warnings | 0 |
| Duration | ~9s |

All 750 tests pass cleanly with zero warnings, zero deprecation notices.

## Previous Failures (from .pytest_cache/v/cache/lastfailed)

Five tests were failing in a prior run (now all pass -- these were likely fixed in recent commits):

1. `test_pipeline_scripts.py::TestParseSimpleToml::test_unterminated_array_eats_subsequent_keys`
2. `test_pipeline_scripts.py::TestExtractStoryId::test_no_colon_returns_full_title`
3. `test_gh_interactions.py::TestFakeGitHubStrictMode::test_strict_warns_on_release_view_jq`
4. `test_gh_interactions.py::TestFakeGitHubStrictMode::test_strict_warns_on_unimplemented_jq`
5. `test_gh_interactions.py::TestGetLinkedPrTimeline::test_timeline_prefers_first_merged_pr`

These appear to be tests that existed in an older version of the test suite but whose names or implementations changed. They are not currently in the collected test set (750 collected, 750 passed).

## Coverage Report

**Overall: 85% (4178 statements, 644 missed)**

| Module | Stmts | Miss | Cover | Notes |
|--------|-------|------|-------|-------|
| `scripts/validate_config.py` | 482 | 30 | **94%** | Core config module, best covered |
| `skills/sprint-run/scripts/sync_tracking.py` | 206 | 17 | **92%** | Main sync loop, well covered |
| `scripts/sprint_init.py` | 630 | 72 | **89%** | Large file, mostly covered |
| `scripts/sprint_analytics.py` | 131 | 14 | **89%** | Good coverage |
| `skills/sprint-release/scripts/release_gate.py` | 378 | 40 | **89%** | Release pipeline, well tested |
| `scripts/validate_anchors.py` | 171 | 21 | **88%** | Anchor validation |
| `scripts/team_voices.py` | 56 | 7 | **88%** | Small module |
| `skills/sprint-monitor/scripts/check_status.py` | 250 | 32 | **87%** | Monitor checks |
| `skills/sprint-setup/scripts/setup_ci.py` | 160 | 21 | **87%** | CI generation |
| `scripts/commit.py` | 73 | 10 | **86%** | Commit validation |
| `scripts/sync_backlog.py` | 136 | 22 | **84%** | Backlog sync |
| `scripts/traceability.py` | 106 | 17 | **84%** | Traceability mapping |
| `scripts/manage_epics.py` | 241 | 44 | **82%** | Epic CRUD |
| `scripts/manage_sagas.py` | 153 | 31 | **80%** | Saga management |
| `scripts/sprint_teardown.py` | 311 | 75 | **76%** | Teardown (interactive paths hard to test) |
| `skills/sprint-run/scripts/update_burndown.py` | 105 | 26 | **75%** | Burndown update |
| `skills/sprint-setup/scripts/populate_issues.py` | 299 | 77 | **74%** | Issue population |
| `skills/sprint-setup/scripts/bootstrap_github.py` | 194 | 57 | **71%** | GitHub bootstrap |
| `scripts/test_coverage.py` | 96 | 31 | **68%** | Test coverage checker (ironic) |

## Coverage Gaps to Note

Lowest-covered modules (potential audit targets):

1. **`test_coverage.py` (68%)** -- The test coverage checker itself has the lowest coverage. Missing: `scan_project_tests()` main loop, `check_test_coverage()` report formatting.

2. **`bootstrap_github.py` (71%)** -- Missing: `main()` function (lines 318-332), `check_prerequisites()` (lines 20-41), some error paths in `create_milestones_on_github()`.

3. **`populate_issues.py` (74%)** -- Missing: `main()` function (lines 445-493), `enrich_from_epics()` detail paths, `build_milestone_title_map()` edge cases.

4. **`update_burndown.py` (75%)** -- Missing: `main()` function (lines 198-233), some `write_burndown()` edge cases.

5. **`sprint_teardown.py` (76%)** -- Missing: interactive confirmation prompts, git-dirty-check paths, `main()` orchestration edges.

## Test Distribution by Category

| Category | Files | Tests |
|----------|-------|-------|
| Unit tests (module-level) | 8 | ~450 |
| Integration tests (multi-module) | 4 | ~200 |
| Property-based tests (hypothesis) | 1 | 36 |
| Regression tests (BH-series) | 1 | 91 |
| Golden-run / snapshot tests | 1 | 4 |
| Fidelity tests (FakeGitHub) | 1 | 10 |
