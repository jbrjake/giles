# Recon 0b: Test Infrastructure Analysis

**Date:** 2026-03-15
**Repo:** giles (Claude Code plugin for agile sprints)

## Test Framework and Runner

- **Framework:** `unittest` (Python stdlib). No pytest, no external deps.
- **Runner:** `python -m unittest tests.<module> -v` (per-file invocation).
- **Config files:** None. No `pytest.ini`, `setup.cfg`, `tox.ini`, or `pyproject.toml`.
- **Coverage tools:** None configured. No `.coveragerc` or coverage dependencies.
- **Linters:** None configured at plugin level. CI is generated per-project.
- **Fixture system:** Manual `tempfile.mkdtemp()` + `setUp/tearDown` cleanup. One shared fixture at `tests/fixtures/hexwise/` (a realistic Rust project with deep docs).
- **Golden test infrastructure:** `golden_recorder.py` and `golden_replay.py` capture/compare FakeGitHub state + file-tree snapshots. Recordings stored at `tests/golden/recordings/` (5 JSON snapshots exist).

## Test File Inventory

| File | Test Count | Assertion Count | Avg Asserts/Test | Role |
|------|-----------|----------------|-----------------|------|
| `test_gh_interactions.py` | 196 | 344 | 1.8 | Main unit test file: commit, release_gate, check_status, bootstrap, populate, sync_tracking, burndown, FakeGitHub self-tests |
| `test_pipeline_scripts.py` | 131 | 233 | 1.8 | team_voices, traceability, test_coverage, manage_epics, manage_sagas, TOML parser, CI generation, scanner heuristics, validate_project negative tests |
| `test_release_gate.py` | 43 | 114 | 2.7 | release_gate orchestration: calculate_version, validate_gates, gate_tests, gate_build, do_release (happy path, error paths, rollback, dry run) |
| `test_sprint_teardown.py` | 28 | 83 | 3.0 | classify_entries, collect_directories, remove_symlinks, remove_generated, remove_empty_dirs, main() dry-run/execute |
| `test_hexwise_setup.py` | 25 | 68 | 2.7 | Hexwise fixture e2e: scanner, config generation, validation, full setup pipeline |
| `test_validate_anchors.py` | 25 | 32 | 1.3 | Anchor namespace resolution, definition scanning, reference scanning, check mode, fix mode |
| `test_verify_fixes.py` | 19 | 45 | 2.4 | Regression tests for specific prior bugs (config generation, CI generation, frontmatter, evals, load_config errors, team index parsing) |
| `test_sync_backlog.py` | 18 | 36 | 2.0 | hash_milestone_files, state persistence, check_sync (debounce/throttle), do_sync, main() lifecycle |
| `test_lifecycle.py` | 15 | 48 | 3.2 | Full lifecycle e2e: init -> bootstrap -> populate -> version -> release notes -> burndown -> monitoring |
| `test_sprint_analytics.py` | 11 | 29 | 2.6 | compute_velocity, compute_review_rounds, compute_workload, format_report |
| `test_golden_run.py` | 1 | 7 | 7.0 | Golden snapshot regression: records/replays 5-phase pipeline against hexwise |
| **TOTAL** | **512** | **1,039** | **2.0** | |

## Test Infrastructure Files (Not Tests)

| File | Purpose |
|------|---------|
| `fake_github.py` | FakeGitHub mock: in-memory GitHub state, dispatches `gh` CLI args to handlers |
| `golden_recorder.py` | Captures FakeGitHub state + file tree at phase boundaries |
| `golden_replay.py` | Loads golden snapshots and diffs against current state |

## FakeGitHub Mock Analysis

### What It Intercepts

FakeGitHub intercepts `subprocess.run` calls where `args[0] == "gh"` via `make_patched_subprocess()`. It handles:

- **`gh label create`** -- creates labels in memory
- **`gh api repos/.../milestones`** -- create, list, PATCH (close) milestones
- **`gh api repos/.../compare/...`** -- branch divergence comparison
- **`gh api repos/.../commits`** -- commit listing (for direct push detection)
- **`gh api repos/.../issues/N/timeline`** -- linked PR lookup
- **`gh issue create/list/edit/close`** -- full issue CRUD
- **`gh run list/view`** -- CI run queries
- **`gh pr list/create/review/merge`** -- PR lifecycle
- **`gh release create/view`** -- release management
- **`gh auth`** -- always returns success
- **`gh --version`** -- returns fake version string

### Fidelity Gaps and Known Weaknesses

1. **`--jq` is not executed.** FakeGitHub accepts `--jq` on `api` and `release view` handlers but does NOT actually execute jq filtering. Tests that rely on `--jq` shaping data must pre-shape it (e.g., `commits_data` stores post-jq shape). This creates a **silent correctness gap**: if production code changes its `--jq` expression, the test data shape becomes stale and the test still passes with wrong data.

2. **`--paginate` is a no-op.** FakeGitHub returns all data at once. Tests never exercise pagination edge cases (truncation, incomplete pages).

3. **No rate limiting simulation.** FakeGitHub never returns 403/429 errors. Production retry/backoff paths are untested.

4. **No authentication failure simulation.** `_handle_auth()` always succeeds. Auth-related error paths in production are untested.

5. **Non-gh subprocess calls pass through to real subprocess.run.** This is by design (git commands run against real temp repos), but it means tests DO make real git calls. If the test environment has unusual git configs, tests may behave differently.

6. **`release view` returns a static structure** regardless of whether the release exists. Production code that checks release existence may get false positives in tests.

7. **Issue/PR numbering is globally sequential** starting at 1, regardless of milestones. Real GitHub numbers issues and PRs from a single sequence, but the monotonic counters in FakeGitHub don't reset, which could mask bugs that depend on specific number ranges.

### FakeGitHub Self-Defense Mechanism

Good: `_check_flags()` raises `NotImplementedError` on unrecognized flags, preventing silent test passage when production code starts sending new flags. This is explicitly tested in `TestFakeGitHubFlagEnforcement` (4 tests). `_KNOWN_FLAGS` registry covers all handlers. Unhandled API paths also fail loudly (line 300).

## Production Files Coverage Map

### Production Files WITH Test Coverage

| Production File | Tested By | Quality |
|----------------|-----------|---------|
| `scripts/validate_config.py` | test_gh_interactions, test_pipeline_scripts, test_verify_fixes, test_lifecycle, test_hexwise_setup | Good -- parse_simple_toml, validate_project, extract_sp, kanban_from_labels, find_milestone, detect_sprint, extract_story_id, get_base_branch, _split_array all directly tested |
| `scripts/sprint_init.py` | test_hexwise_setup, test_lifecycle, test_verify_fixes, test_pipeline_scripts | Good -- ProjectScanner and ConfigGenerator tested via hexwise fixture and synthetic projects |
| `scripts/commit.py` | test_gh_interactions, test_lifecycle | Good -- validate_message, check_atomicity tested. main() arg parsing tested. |
| `scripts/sprint_teardown.py` | test_sprint_teardown | Good -- classify_entries, collect_directories, remove_symlinks, remove_generated, remove_empty_dirs, resolve_symlink_target, main() all tested |
| `scripts/sync_backlog.py` | test_sync_backlog | Good -- hash_milestone_files, state persistence, check_sync, do_sync, main() all tested |
| `scripts/sprint_analytics.py` | test_sprint_analytics | Good -- compute_velocity, compute_review_rounds, compute_workload, format_report tested |
| `scripts/team_voices.py` | test_pipeline_scripts | Good -- extract_voices tested against hexwise fixture |
| `scripts/traceability.py` | test_pipeline_scripts | Good -- parse_stories, parse_requirements, build_traceability tested |
| `scripts/test_coverage.py` | test_pipeline_scripts | Good -- check_test_coverage, detect_test_functions for 4 languages tested |
| `scripts/manage_epics.py` | test_pipeline_scripts | Good -- parse_epic, add_story, remove_story, reorder_stories, renumber_stories tested |
| `scripts/manage_sagas.py` | test_pipeline_scripts | Good -- parse_saga, update_sprint_allocation, update_epic_index, update_team_voices tested |
| `scripts/validate_anchors.py` | test_validate_anchors | Good -- resolve_namespace, find_anchor_defs, find_anchor_refs, check_anchors, fix_missing_anchors tested |
| `skills/.../bootstrap_github.py` | test_gh_interactions, test_lifecycle, test_hexwise_setup | Partial -- create_label, create_static_labels, create_persona_labels, create_milestones_on_github, _collect_sprint_numbers tested. **Missing:** create_sprint_labels, create_saga_labels, create_epic_labels, _parse_saga_labels_from_backlog, check_prerequisites, main() |
| `skills/.../populate_issues.py` | test_gh_interactions, test_hexwise_setup, test_lifecycle | Good -- parse_milestone_stories, parse_detail_blocks, enrich_from_epics, format_issue_body, get_existing_issues, create_issue, _infer_sprint_number tested. **Missing:** check_prerequisites, _build_row_regex (only tested indirectly), get_milestone_numbers, build_milestone_title_map, main() |
| `skills/.../setup_ci.py` | test_pipeline_scripts, test_hexwise_setup, test_verify_fixes | Partial -- generate_ci_yaml tested for Rust/Python/Node/Go, _docs_lint_job tested. **Missing:** _generate_check_job, _generate_test_job, _generate_build_job, _job_name_from_command, _find_test_command, check_prerequisites, main() |
| `skills/.../check_status.py` | test_gh_interactions, test_lifecycle | Good -- check_ci, check_prs, check_milestone, check_branch_divergence, check_direct_pushes, _first_error, _hours, _age tested. **Missing:** write_log, _count_sp (tested only indirectly via check_milestone), main() (only --help tested) |
| `skills/.../release_gate.py` | test_gh_interactions, test_release_gate | Good -- determine_bump, bump_version, calculate_version, gate_stories, gate_ci, gate_prs, gate_tests, gate_build, validate_gates, write_version_to_toml, generate_release_notes, find_milestone_number, do_release tested. **Missing:** find_latest_semver_tag, parse_commits_since (always mocked), print_gate_summary, main() |
| `skills/.../sync_tracking.py` | test_gh_interactions, test_lifecycle | Good -- find_milestone_title, get_linked_pr, slug_from_title, TF, read_tf, write_tf, _yaml_safe, sync_one, create_from_issue, main() arg parsing tested. **Missing:** _fetch_all_prs (always mocked), _parse_closed |
| `skills/.../update_burndown.py` | test_gh_interactions, test_lifecycle | Good -- extract_sp, write_burndown, update_sprint_status tested. **Missing:** closed_date (tested only indirectly), load_tracking_metadata, _fm_val, main() |

### Production Functions WITHOUT Any Test Coverage

These functions have ZERO direct or indirect test coverage:

| Function | File | Risk |
|----------|------|------|
| `run_commit()` | scripts/commit.py | **HIGH** -- The actual commit execution function. Tests only validate messages and atomicity, never the subprocess invocation that actually runs `git commit`. |
| `_fetch_all_prs()` | sync_tracking.py | MEDIUM -- Always mocked away. The gh query construction and pagination are never tested. |
| `load_tracking_metadata()` | update_burndown.py | MEDIUM -- Reads YAML frontmatter from tracking files for burndown. Never tested directly. |
| `_fm_val()` | update_burndown.py | LOW -- Helper for frontmatter value extraction. Simple enough that bugs are unlikely. |
| `check_prerequisites()` | bootstrap_github.py, populate_issues.py, setup_ci.py | **HIGH** -- Three separate prerequisite check functions, none tested. These check for `gh` CLI, auth, git remote, Python version. If they fail with confusing messages or false positives, users will get stuck. |
| `_build_row_regex()` | populate_issues.py | MEDIUM -- Builds regex for parsing milestone story tables. Only tested indirectly through parse_milestone_stories. A bug here would silently skip stories. |
| `get_milestone_numbers()` | populate_issues.py | LOW -- Thin wrapper around gh_json. |
| `build_milestone_title_map()` | populate_issues.py | LOW -- Builds sprint-to-milestone mapping. |
| `_parse_saga_labels_from_backlog()` | bootstrap_github.py | LOW -- Parses saga IDs from backlog files for label creation. |
| `create_sprint_labels()` | bootstrap_github.py | MEDIUM -- Creates sprint:N labels. If numbering logic is wrong, sprints get misnamed. |
| `create_saga_labels()` | bootstrap_github.py | LOW -- Creates saga labels from backlog parsing. |
| `create_epic_labels()` | bootstrap_github.py | LOW -- Creates epic:E-NNNN labels from epic files. |
| `_generate_check_job()` | setup_ci.py | MEDIUM -- Individual CI job generators tested only through generate_ci_yaml integration. Edge cases in job naming, step ordering not tested. |
| `_generate_test_job()` | setup_ci.py | MEDIUM -- Same as above. |
| `_generate_build_job()` | setup_ci.py | MEDIUM -- Same as above. |
| `_job_name_from_command()` | setup_ci.py | LOW -- Converts commands to safe YAML job names. |
| `_find_test_command()` | setup_ci.py | LOW -- Finds test command in check_commands list. |
| `print_gate_summary()` | release_gate.py | LOW -- Console output only. |
| `write_log()` | check_status.py | LOW -- Writes monitor log to file. |
| `_count_sp()` | check_status.py | LOW -- Counts story points from issues. Tested indirectly through check_milestone. |
| `find_latest_semver_tag()` | release_gate.py | MEDIUM -- Parses git tags. Always mocked in tests. A regex bug here means wrong base version. |
| `parse_commits_since()` | release_gate.py | MEDIUM -- Parses git log output. Always mocked. Parsing bugs would cause wrong changelogs. |
| `_parse_closed()` | sync_tracking.py | LOW -- ISO date parsing for closed dates. |
| `closed_date()` | update_burndown.py | LOW -- Extracts close date from issue. Tested indirectly via lifecycle test. |
| `_indicator()`, `print_scan_results()`, `print_generation_summary()` | sprint_init.py | LOW -- Console output only. |
| `_print_errors()` | validate_config.py | LOW -- Console output only. |
| `list_milestone_issues()` | validate_config.py | LOW -- Thin wrapper around gh_json. |
| `warn_if_at_limit()` | validate_config.py | LOW -- Prints a warning. Tested once indirectly as a mock target. |
| `_is_throttled()` | sync_backlog.py | LOW -- Tested indirectly through check_sync throttle tests. |
| All `main()` functions | Various | MEDIUM -- Most main() functions only tested for --help/arg-error paths. The actual execution flow of main() is never tested for: sprint_init, bootstrap_github, populate_issues, setup_ci, update_burndown, release_gate, check_status (beyond --help). |

## Test Quality Flags

### Tests That Look Like Coverage but Test Little

1. **test_golden_run.py: `test_golden_full_setup_pipeline`** -- This test has 7 assertions, but they are gated behind `_check_or_record()` which skips the test entirely if golden recordings are absent AND `GOLDEN_RECORD=1` is not set. When recordings ARE present, the test runs, but the comparison method (`replayer.assert_*_match()`) only diffs titles/labels/counts, not issue bodies or detailed state. So even with recordings, the golden test provides coarse-grained regression detection.

2. **`test_api_error_handled` in TestCheckBranchDivergenceFakeGH (line 1215)** -- This test claims to test "API error handling" but FakeGitHub's compare endpoint returns a default `{behind_by: 0, ahead_by: 0}` for unknown branches, so no error is actually raised. The test verifies the default case (no drift), not error handling. The method name is misleading.

3. **`test_label_error_handled` (line 507)** -- Patches `print()` to verify the warning was printed, but does not verify the function's return value or whether the label was partially created. The test proves the exception is caught but not what happens after.

4. **`test_parse_milestone_stories_malformed_tables` (line 267)** -- The assertion is "it returned a list without crashing." This is a crash guard, not a correctness test. The comment even says "The key assertion is that it returns a list without raising." This test will pass even if the parser silently drops valid stories.

5. **`test_skips_missing_file` in TestUpdateSprintStatus (line 1472)** -- The only assertion is that the function "should not raise." No verification of any behavior. This is a pure crash guard.

### Tests That Test FakeGitHub Rather Than Production Code

The following test classes test the test infrastructure itself:

- `TestFakeGitHubFlagEnforcement` (4 tests) -- Tests that FakeGitHub rejects unknown flags
- `TestFakeGitHubShortFlags` (4 tests) -- Tests FakeGitHub's `-f`/`-X` parsing
- `TestFakeGitHubJqHandlerScoped` (2 tests) -- Tests FakeGitHub's --jq handler scoping
- `TestFakeGitHubIssueLabelFilter` (4 tests) -- Tests FakeGitHub's label filtering
- `test_state_dump` in TestHexwisePipeline -- Tests FakeGitHub.dump_state()

**Total: 15 tests testing FakeGitHub, not production code.** These are legitimate infrastructure tests but inflate the test count without testing production behavior.

### Tests With Fewer Than 3 Assertions (Trivial Count)

Approximately 290 of 512 tests (57%) have fewer than 3 assertions. Many of these are legitimate focused unit tests (e.g., `test_valid_feat` -- one boolean check), but the high proportion suggests many tests verify only the happy path's most obvious output without checking for side effects or edge conditions.

### Source-Code Inspection Tests

- `TestCheckStatusImportGuard` (line 1866) -- Uses `inspect.getsource()` to verify the import block uses `except ImportError`, not `except Exception`. This is a valid structural test but is fragile: it will break if the surrounding code is refactored.

### Untested Error Recovery Paths

- **release_gate.py rollback paths** -- Well tested (commit failure rollback, tag push failure rollback, gh release failure rollback).
- **sync_tracking.py error paths** -- Tested for timeline API failures (falls back to branch matching). Good.
- **check_status.py error paths** -- API errors in check_branch_divergence and check_direct_pushes are tested. Good.

## Critical Coverage Gaps

### 1. No Integration Test for `sprint-run` Story Execution

The sprint-run skill is the core of the product (story execution, persona assignment, PR creation, review cycles). Yet there are ZERO tests for:
- The story execution loop
- Persona assignment logic (from `persona-guide.md`)
- Kanban state transitions through the full lifecycle
- Sprint kickoff/demo/retro ceremony orchestration

This is partly because these are orchestrated by the SKILL.md prompt, not scripts. But the `sync_tracking.sync_one()` function, which handles state transitions, is only tested for 4 scenarios.

### 2. `run_commit()` Is Never Tested

The function that actually executes `git commit` via subprocess is never called in any test. Tests validate message format and atomicity checks, then stop. The actual commit subprocess invocation, error handling, and return value parsing are untested.

### 3. `check_prerequisites()` Functions Are Never Tested (x3)

Three separate scripts have `check_prerequisites()` functions that verify the environment (gh CLI, auth, git remote, Python version). None are tested. These are the first thing users hit when setting up, and confusing failure messages here drive users away.

### 4. `find_latest_semver_tag()` and `parse_commits_since()` Always Mocked

These two functions interact with `git` to determine version history. They are always mocked in tests, so the actual git tag parsing regex and git log parsing logic are never exercised. Bugs in version detection would not be caught.

### 5. No Test for `sprint-monitor` or `sprint-release` Main Entry Points

The `main()` functions of `check_status.py` and `release_gate.py` are only tested for `--help` flag handling. The actual execution paths (load config, run checks, output results) are never tested through `main()`.

### 6. FakeGitHub `--jq` Gap

FakeGitHub accepts but ignores `--jq`. Production code in `check_direct_pushes()` and `get_linked_pr()` uses `--jq` to filter/reshape API responses. Tests pre-shape the mock data to match what `--jq` would produce. If a production `--jq` expression changes, the mock data shape becomes wrong, but FakeGitHub will still return the stale shape. Tests pass; production breaks.

## Summary Statistics

- **14 Python files** in tests/ (11 test files, 3 infrastructure files)
- **512 test methods** across 11 test files
- **1,039 assertions** total (2.0 avg per test)
- **19 production Python files** (12 in scripts/, 7 in skills/)
- **~25+ production functions** with zero direct test coverage
- **3 check_prerequisites() functions** completely untested
- **`run_commit()` never tested** (the actual commit execution)
- **15 tests** test FakeGitHub itself, not production code
- **~57% of tests** have fewer than 3 assertions
- **Golden test** may silently skip if recordings are absent
- **`--jq` never executed** in FakeGitHub, creating a silent fidelity gap
