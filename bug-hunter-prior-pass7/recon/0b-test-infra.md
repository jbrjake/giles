# Phase 0b: Test Infrastructure Audit

## Test Framework

- **Framework**: `unittest` (stdlib). No pytest, no external test dependencies.
- **Mocking**: `unittest.mock.patch` used extensively for subprocess and gh CLI interception.
- **No conftest.py, pytest.ini, setup.cfg, or pyproject.toml** with test config.
- **No `tests/__init__.py`** -- tests are run as scripts or via `python -m unittest tests.<module>`.
- **Run convention**: Each file has `if __name__ == "__main__": unittest.main()` and documents its run command in the module docstring (e.g., `python -m unittest tests.test_lifecycle -v`).

## Test Helpers / Fixtures

### `tests/fake_github.py` (716 lines)
Core test double: an in-memory GitHub state machine that intercepts `gh` CLI calls via subprocess patching.

**Key components:**
- `FakeGitHub` class: Simulates labels, milestones, issues, PRs, reviews, releases, CI runs, timeline events, branch comparisons, and commits.
- `_DISPATCH` dict: Routes top-level gh commands (label, api, issue, run, pr, release, auth, --version).
- `_KNOWN_FLAGS` registry: Whitelists accepted flags per handler. Unknown flags raise `NotImplementedError` to prevent silent pass-through (BH-008 pattern).
- `_ACCEPTED_NOOP_FLAGS`: Flags accepted but ignored (e.g., `--paginate`, `--notes-file`).
- `_parse_flags()`: Parses `--flag value` and `-f value` pairs from args.
- `_check_flags()`: Validates flags against the registry.
- `_filter_json_fields()`: Filters JSON output to match `--json` field selection.
- `dump_state()`: Returns full state dict for assertions and golden snapshots.
- `make_patched_subprocess(fake_gh, verbose=False)`: Factory that creates a `subprocess.run` replacement intercepting `gh` calls while passing other commands through to the real `subprocess.run`.

**Supported operations:**
- Labels: create (with --force)
- API: milestones (create/list/close), compare, commits, timeline
- Issues: create, list (with state/milestone/label/json/limit filters), edit (add-label/remove-label/milestone), close
- Runs: list (with branch/json/limit/status filters), view
- PRs: list (with json/state/limit), create, review (approve/request-changes), merge (squash/merge/rebase)
- Releases: create (positional tag + flags), view
- Auth: no-op success
- Version: returns fake version string

### `tests/golden_recorder.py` (103 lines)
Records state snapshots at pipeline phase boundaries for golden-run regression testing.

- `GoldenRecorder.snapshot(phase_name)`: Captures FakeGitHub state + file tree (sprint-config/, sprints/, docs/sprints/, docs/dev-team/sprints/) as JSON.
- `GoldenRecorder.write_manifest()`: Writes `manifest.json` summarizing recorded phases.
- Output directory: `tests/golden/recordings/`

### `tests/golden_replay.py` (176 lines)
Loads recorded golden snapshots and asserts consistency against current state.

- `GoldenReplayer.assert_labels_match()`: Set comparison of label names.
- `GoldenReplayer.assert_milestones_match()`: Sorted title comparison.
- `GoldenReplayer.assert_issues_match()`: Count and title set comparison.
- `GoldenReplayer.assert_files_match()`: File tree set comparison.

### Golden Recordings (present)
`tests/golden/recordings/` contains 5 phase snapshots + manifest:
- `01-setup-init.json`
- `02-setup-labels.json`
- `03-setup-milestones.json`
- `04-setup-issues.json`
- `05-setup-ci.json`
- `manifest.json`

### Test Fixture: `tests/fixtures/hexwise/`
A complete mock Rust project (Hexwise color toolkit) with:
- `Cargo.toml`, `src/lib.rs`, `src/main.rs`
- 3 persona files (rusti, palette, checker) + giles + team topology + INDEX
- 3 milestones, 2 sagas, 6 epics
- PRD directory with 3 sections
- Test plan with 4 documents
- Story map
- RULES.md, DEVELOPMENT.md

Used by: `test_hexwise_setup.py`, `test_golden_run.py`, `test_pipeline_scripts.py`

### Inline MockProject (in test_lifecycle.py and test_verify_fixes.py)
Minimal synthetic Rust project created in a temp directory with:
- Cargo.toml, .git setup, 2 persona files (alice, bob), 1 milestone, RULES.md, DEVELOPMENT.md
- Used for pipeline integration tests with loose assertions

## Test Organization

### File-by-file summary

| File | Test Classes | Test Methods | Focus Area |
|------|-------------|-------------|------------|
| `test_gh_interactions.py` | 55 | 177 | gh CLI interactions: commit validation, version calc, gates, CI/PR checks, sync_tracking, burndown, FakeGitHub validation |
| `test_pipeline_scripts.py` | 15 | 118 | Pipeline scripts: team_voices, traceability, test_coverage, manage_epics, manage_sagas, TOML parser, CI generation, scanner, validate_project |
| `test_release_gate.py` | 10 | 34 | Release gate: calculate_version, bump_version, validate_gates, gate_tests, gate_build, find_milestone_number, do_release (happy/error/dry-run/rollback) |
| `test_sprint_teardown.py` | 9 | 28 | Teardown: classify_entries, collect_directories, resolve_symlink_target, remove_symlinks, remove_generated, remove_empty_dirs, main() dry-run/execute |
| `test_hexwise_setup.py` | 2 | 25 | Hexwise fixture: scanner detection, config generation, validation, CI, full pipeline, FakeGitHub state dump |
| `test_validate_anchors.py` | 5 | 25 | Anchor system: namespace map, find_anchor_defs, find_anchor_refs, check_anchors, fix_missing_anchors |
| `test_verify_fixes.py` | 6 | 19 | Bug fix verification: config generation, CI generation, agent frontmatter, evals, load_config errors, team index parsing |
| `test_sync_backlog.py` | 5 | 18 | Backlog sync: hash_milestone_files, state persistence, debounce/throttle, do_sync, main() end-to-end |
| `test_lifecycle.py` | 1 | 15 | End-to-end lifecycle: init, config keys, labels, milestones, issues, idempotency, version calc, release notes, burndown, commit validation, full pipeline, monitoring pipeline |
| `test_sprint_analytics.py` | 5 | 11 | Sprint analytics: extract_persona, compute_velocity, compute_review_rounds, compute_workload, format_report |
| `test_golden_run.py` | 1 | 1 | Golden-run regression: full sequential pipeline with snapshot recording/replay |
| **TOTAL** | **114** | **471** | |

### Test Patterns and Conventions

1. **sys.path manipulation**: Every test file manually inserts paths to `scripts/`, `tests/`, and skill-specific script directories. No package imports.

2. **FakeGitHub as the primary mock**: Most tests that touch GitHub use `FakeGitHub` + `make_patched_subprocess` rather than mocking individual functions. Some older tests use `@patch("module.gh_json")` style mocking.

3. **Dual mocking approaches**: The codebase uses both:
   - `patch("subprocess.run", make_patched_subprocess(fake_gh))` -- FakeGitHub intercepts all gh calls (preferred for integration tests)
   - `@patch("module.gh_json")` / `@patch("module.gh")` -- direct function mocking (used for unit-level isolation)

4. **Temp directory pattern**: Tests use `tempfile.mkdtemp()` or `tempfile.TemporaryDirectory()` with manual cleanup in `tearDown`. Some use `setUpClass`/`tearDownClass` for shared fixtures (e.g., `TestHexwiseSetup`).

5. **os.chdir usage**: Several test classes change working directory in setUp and restore in tearDown. This is necessary because ConfigGenerator uses relative symlinks. Risk of pollution if tearDown fails.

6. **No test discovery config**: No pytest markers, no test runner config. Tests are expected to be run individually or via `python -m unittest discover tests/`.

7. **Verbose docstrings**: Most test methods have docstrings explaining the scenario and purpose, including bug-fix references (e.g., "P6-19:", "BH-004:", "P5-01:").

8. **Golden-run dual mode**: `test_golden_run.py` operates in record mode (`GOLDEN_RECORD=1`) or replay mode, controlled by environment variable. Replay mode skips if no recordings exist.

### Scripts Under Test

| Script | Tested In |
|--------|-----------|
| `scripts/validate_config.py` | test_gh_interactions, test_pipeline_scripts, test_verify_fixes, test_hexwise_setup, test_lifecycle |
| `scripts/sprint_init.py` | test_hexwise_setup, test_verify_fixes, test_lifecycle, test_golden_run, test_pipeline_scripts |
| `scripts/sprint_teardown.py` | test_sprint_teardown |
| `scripts/sync_backlog.py` | test_sync_backlog |
| `scripts/sprint_analytics.py` | test_sprint_analytics |
| `scripts/commit.py` | test_gh_interactions, test_lifecycle |
| `scripts/team_voices.py` | test_pipeline_scripts |
| `scripts/traceability.py` | test_pipeline_scripts |
| `scripts/test_coverage.py` | test_pipeline_scripts |
| `scripts/manage_epics.py` | test_pipeline_scripts |
| `scripts/manage_sagas.py` | test_pipeline_scripts |
| `scripts/validate_anchors.py` | test_validate_anchors |
| `skills/sprint-setup/scripts/bootstrap_github.py` | test_gh_interactions, test_hexwise_setup, test_lifecycle, test_golden_run |
| `skills/sprint-setup/scripts/populate_issues.py` | test_gh_interactions, test_hexwise_setup, test_lifecycle, test_golden_run |
| `skills/sprint-setup/scripts/setup_ci.py` | test_verify_fixes, test_hexwise_setup, test_golden_run, test_pipeline_scripts |
| `skills/sprint-run/scripts/sync_tracking.py` | test_gh_interactions, test_lifecycle |
| `skills/sprint-run/scripts/update_burndown.py` | test_gh_interactions, test_lifecycle |
| `skills/sprint-monitor/scripts/check_status.py` | test_gh_interactions, test_lifecycle |
| `skills/sprint-release/scripts/release_gate.py` | test_gh_interactions, test_release_gate, test_lifecycle |
