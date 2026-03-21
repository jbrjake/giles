# 0b - Test Infrastructure Recon

## Test Framework

- **Primary**: `unittest` (stdlib) -- used by 14 of 15 test files
- **Secondary**: `pytest` -- used as the test runner; also used natively by `test_property_parsing.py` (plain classes, no `unittest.TestCase`)
- **Property testing**: `hypothesis` -- used in `test_property_parsing.py` with `@given` / `@settings` decorators (24 property tests with `max_examples` ranging 100-500)
- **Runner**: `python -m pytest tests/`

## Dev Dependencies

File: `/Users/jonr/Documents/non-nitro-repos/giles/requirements-dev.txt`

```
pytest>=9.0
pytest-cov>=6.0
jq>=1.11
hypothesis>=6
```

No `pyproject.toml`, `setup.cfg`, or `.coveragerc` found -- coverage is configured purely via CLI flags (`--cov=scripts --cov=skills`).

## Test Files (15 test modules)

| File | Classes | Tests | Focus |
|------|---------|-------|-------|
| `test_sprint_runtime.py` | 39 | 162 | check_status, bootstrap, populate, sync_tracking, burndown, kanban, extract_sp, helpers |
| `test_pipeline_scripts.py` | 16 | 137 | team_voices, traceability, test_coverage, manage_epics, manage_sagas, TOML parser, CI gen, scanner |
| `test_verify_fixes.py` | 39 | 97 | Config gen, CI gen, agent frontmatter, evals, load_config, teardown, validate_anchors, build_rows |
| `test_bugfix_regression.py` | 42 | 91 | FakeGitHub flags, BH-series regressions, sync_tracking, check_status integration, patch_gh helper |
| `test_release_gate.py` | 14 | 56 | Version calc, gate_stories/ci/prs/tests/build, validate_gates, do_release, find_latest_semver_tag |
| `test_gh_interactions.py` | 8 | 40 | commit validation, atomicity check, determine_bump, write_version_to_toml, gate functions, release notes |
| `test_property_parsing.py` | 5 | 36 | Hypothesis property tests for extract_story_id, extract_sp, _yaml_safe, parse_simple_toml, _parse_team_index |
| `test_sprint_teardown.py` | 10 | 32 | classify_entries, collect_directories, symlink ops, remove_generated, full teardown flow, git dirty check |
| `test_validate_anchors.py` | 5 | 25 | namespace resolution, find_anchor_defs/refs, check_anchors, fix_missing_anchors |
| `test_hexwise_setup.py` | 2 | 25 | ProjectScanner, ConfigGenerator, full setup pipeline (labels, milestones, issues, CI) |
| `test_sync_backlog.py` | 5 | 18 | hash_milestone_files, state file, check_sync debounce/throttle, do_sync, main integration |
| `test_sprint_analytics.py` | 6 | 15 | extract_persona, compute_velocity, compute_review_rounds, compute_workload, format_report, main |
| `test_lifecycle.py` | 1 | 13 | End-to-end pipeline: init -> bootstrap -> populate -> release -> monitoring |
| `test_fakegithub_fidelity.py` | 3 | 10 | jq expression correctness, search predicate warnings, milestone counters |
| `test_golden_run.py` | 2 | 4 | Golden-run replay pipeline, assert_files_match adversarial cases |

**Totals**: 197 test classes, 761 test functions across 15 files.

## Test Helpers / Utilities (6 files)

### `tests/conftest.py`
Shared pytest configuration. Adds all script directories to `sys.path` so test files can import production modules directly without per-file path hacking.

### `tests/fake_github.py` -- FakeGitHub test double
**968 lines.** In-memory simulation of GitHub API for `gh` CLI calls.

What it mocks:
- **Labels**: `gh label create` -- stores in `self.labels` dict
- **Milestones**: `gh api .../milestones` -- POST (create), PATCH (update state), GET (list)
- **Issues**: `gh issue create/list/edit/close` -- full CRUD with milestone counter tracking
- **PRs**: `gh pr create/list/review/merge` -- with review state tracking
- **Releases**: `gh release create/view` -- with tag/notes
- **Runs**: `gh run list` -- with branch/status filtering
- **API endpoints**: `/compare/`, `/commits`, `/issues/{N}/timeline`
- **Auth**: `gh auth` (no-op)
- **Version**: `gh --version` (fake)

Key design features:
- **Dispatch-based routing**: `_DISPATCH` dict maps commands to handler methods
- **Flag enforcement**: `_KNOWN_FLAGS`, `_IMPLEMENTED_FLAGS`, `_ACCEPTED_NOOP_FLAGS` -- unknown flags raise `NotImplementedError`, known-but-unimplemented flags warn in strict mode
- **jq support**: Real `jq` package evaluation when available, falls back to pre-filtered data
- **Milestone counter tracking**: `open_issues` / `closed_issues` updated on issue create/close (BH-002)
- **Label auto-creation**: Mirrors real `gh` behavior of auto-creating labels on `issue create --label` (BH-009)
- **Search predicate support**: `milestone:"X"` extracted from `--search` strings
- **State dump**: `dump_state()` returns all internal state for assertions

Integration: `make_patched_subprocess(fake_gh)` creates a `subprocess.run` replacement that intercepts `gh` calls and routes them to FakeGitHub, passing all other calls to real `subprocess.run`.

### `tests/mock_project.py` -- MockProject
Creates a minimal mock Rust project in a temp directory with:
- `Cargo.toml` (language detection)
- Persona files (alice, bob, optionally carol)
- Backlog with milestone
- Rules and dev guide
- Optional real git init or fake `.git/config`

### `tests/gh_test_helpers.py` -- MonitoredMock + patch_gh
Anti-pattern detection for mock-based tests:
- `MonitoredMock`: Proxy that tracks whether test code inspects `call_args`
- `patch_gh()`: Context manager that warns if a mock was called but `call_args` was never checked (prevents "mock returns what you assert" anti-pattern, BH-P11-201)
- `populate_test_issues()`: Shared issue-population helper for pipeline tests

### `tests/golden_recorder.py` -- GoldenRecorder
Records state snapshots (FakeGitHub state + file tree) at named phases for golden-run regression testing.

### `tests/golden_replay.py` -- GoldenReplayer
Loads recorded golden snapshots and compares against current state. Checks labels (including colors), milestones (including descriptions), issues (including labels + milestones), and file trees (including content).

## Golden Test Data

Directory: `tests/golden/recordings/`

5 phase snapshots from a "hexwise" project pipeline run:
1. `01-setup-init.json`
2. `02-setup-labels.json`
3. `03-setup-milestones.json`
4. `04-setup-issues.json`
5. `05-setup-ci.json`

## Hypothesis Database

`.hypothesis/` directory exists (gitignored), containing cached examples from property-based test runs.

## Coverage

`.coverage` file exists from a previous run. No persistent coverage configuration file -- coverage is run ad-hoc via `--cov` flags.
