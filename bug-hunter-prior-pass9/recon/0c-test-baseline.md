# Test Baseline Report

**Date:** 2026-03-15 (updated pass 9)
**Repo:** giles (Claude Code plugin for agile sprints)

## Test Run Results

**Prior live run (pass 8):** 508 tests, 0 failures, 0 errors, 0 skips, 2.729s.
**Current static count (pass 9):** 512 test methods across 11 files, 110 test classes.
**Delta:** +4 tests since pass 8 (all in `test_pipeline_scripts.py`: 127 -> 131).
**Live run needed:** Bash permission was denied during this recon pass. Run `python -m unittest discover tests/ -v` to confirm current pass/fail/error/skip counts and timing.

## Static Analysis Summary

| Metric | Pass 8 | Pass 9 (static) | Delta |
|--------|--------|-----------------|-------|
| Total test files | 11 | 11 | -- |
| Total test classes | 98 | 110 | +12 |
| Total test methods | 508 | 512 | +4 |
| Conditional skips | 1 | 1 | -- |
| Expected test time | ~3s | ~3s | -- |

## Test Count Per File

| File | Tests (pass 8) | Tests (pass 9) | Classes | Focus |
|------|------:|------:|--------:|-------|
| `test_gh_interactions.py` | 196 | 196 | 49 | Commit validation, version calc, gate validation, TOML writing, release notes, check_status, bootstrap_github, populate_issues, sync_tracking, update_burndown, FakeGitHub flag enforcement |
| `test_pipeline_scripts.py` | 127 | **131** | 16 | Team voices, traceability, test_coverage, manage_epics, manage_sagas, TOML parser, CI generation, ProjectScanner, validate_project, detect_sprint, kanban_from_labels |
| `test_release_gate.py` | 43 | 43 | 11 | calculate_version, validate_gates, gate_tests, gate_build, find_milestone_number, do_release, pre-flight checks, dry-run, find_latest_semver_tag, parse_commits_since |
| `test_sprint_teardown.py` | 28 | 28 | 9 | classify_entries, collect_directories, resolve_symlink_target, remove_symlinks, remove_generated, remove_empty_dirs, full teardown flow, main() dry-run/execute |
| `test_validate_anchors.py` | 25 | 25 | 5 | Namespace resolution, anchor defs, anchor refs, check mode, fix mode |
| `test_hexwise_setup.py` | 25 | 25 | 2 | Hexwise fixture scanning, config generation, pipeline (init -> labels -> milestones -> issues), CI generation, state dump |
| `test_verify_fixes.py` | 19 | 19 | 6 | Config generation correctness, CI generation, agent frontmatter, evals genericity, ConfigError, cell count warnings |
| `test_sync_backlog.py` | 18 | 18 | 5 | Hash milestone files, state persistence, debounce/throttle scheduling, do_sync, main() end-to-end |
| `test_lifecycle.py` | 15 | 15 | 1 | End-to-end lifecycle: init -> bootstrap -> populate -> version calc -> release notes -> monitoring pipeline |
| `test_sprint_analytics.py` | 11 | 11 | 5 | Persona extraction, velocity computation, review rounds, workload distribution, report formatting |
| `test_golden_run.py` | 1 | 1 | 1 | Golden snapshot regression: sequential pipeline with cumulative FakeGitHub state |

## New Tests Since Pass 8

5 commits landed between pass 8 and pass 9:
- `4da049b` chore: mark all 23 bug-hunter pass 8 punchlist items as resolved
- `027327f` fix: MEDIUM+LOW bugs -- golden test warning, test quality, multiline YAML, dead code
- `346de99` docs: fix broken anchors, remove phantom features, fill doc gaps
- `e1da676` fix: HIGH test mock bugs -- flag parsing, milestone validation in FakeGitHub
- `c226292` fix: HIGH code bugs -- empty labels, end_line semantics, quote stripping, config_dir, yaml_safe

The +4 tests in `test_pipeline_scripts.py` and +12 classes across all files came from these fix commits. The class count increase (98 -> 110) reflects new test classes added for FakeGitHub improvements and code bug fix verification.

## Scripts Under Test

| Script | Test File(s) |
|--------|-------------|
| `scripts/validate_config.py` | test_pipeline_scripts, test_verify_fixes, test_hexwise_setup, test_lifecycle, test_gh_interactions |
| `scripts/sprint_init.py` | test_hexwise_setup, test_verify_fixes, test_lifecycle, test_golden_run, test_pipeline_scripts |
| `scripts/sprint_teardown.py` | test_sprint_teardown |
| `scripts/sprint_analytics.py` | test_sprint_analytics |
| `scripts/sync_backlog.py` | test_sync_backlog |
| `scripts/commit.py` | test_gh_interactions, test_lifecycle |
| `scripts/validate_anchors.py` | test_validate_anchors |
| `scripts/team_voices.py` | test_pipeline_scripts |
| `scripts/traceability.py` | test_pipeline_scripts |
| `scripts/test_coverage.py` | test_pipeline_scripts |
| `scripts/manage_epics.py` | test_pipeline_scripts |
| `scripts/manage_sagas.py` | test_pipeline_scripts |
| `skills/sprint-setup/scripts/bootstrap_github.py` | test_lifecycle, test_hexwise_setup, test_golden_run, test_gh_interactions, test_sync_backlog |
| `skills/sprint-setup/scripts/populate_issues.py` | test_lifecycle, test_hexwise_setup, test_golden_run, test_gh_interactions, test_sync_backlog |
| `skills/sprint-setup/scripts/setup_ci.py` | test_verify_fixes, test_hexwise_setup, test_golden_run, test_pipeline_scripts |
| `skills/sprint-run/scripts/sync_tracking.py` | test_lifecycle, test_gh_interactions |
| `skills/sprint-run/scripts/update_burndown.py` | test_lifecycle, test_gh_interactions |
| `skills/sprint-monitor/scripts/check_status.py` | test_lifecycle, test_gh_interactions |
| `skills/sprint-release/scripts/release_gate.py` | test_release_gate, test_lifecycle, test_gh_interactions |

## Scripts NOT Under Test

These scripts have no dedicated test coverage discovered:

- `scripts/sprint_analytics.py` `main()` entry point (only metrics functions tested)
- `scripts/validate_anchors.py` `main()` entry point (only core functions tested, though main arg parsing tested for other scripts)

## Observations

1. **Heavy concentration in two files:** `test_gh_interactions.py` (196 tests) and `test_pipeline_scripts.py` (131 tests) account for 64% of all tests.
2. **Strong mock discipline:** FakeGitHub flag enforcement catches untested gh CLI flags, reducing risk of false passes.
3. **Three pipeline test variants:** `test_lifecycle.test_13_full_pipeline` (minimal/loose), `test_hexwise_setup.test_full_setup_pipeline` (hexwise/exact), and `test_golden_run.test_golden_full_setup_pipeline` (hexwise/snapshots). Each documented with scope/complement notes.
4. **No coverage measurement:** No coverage tool configured means there's no way to verify which code paths are actually exercised.
5. **No linting gate:** No linter configured at the plugin level, so style/type issues rely on manual review.
6. **Golden test may skip:** `test_golden_run` skips if no golden recordings exist (requires `GOLDEN_RECORD=1` to initialize).
7. **Test growth is modest:** +4 tests across 5 fix commits suggests most fixes were to existing code paths already covered by tests, not net-new functionality.
