# 0b — Test Infrastructure

## Test Runner and Config

- **Runner**: pytest (>= 9.0), invoked via `make test` or `python -m pytest tests/ -v`
- **No pytest.ini / pyproject.toml / setup.cfg / tox.ini**: Zero configuration files for pytest. No markers, no custom settings, no coverage config, no test path config. Pytest relies entirely on default discovery in `tests/`.
- **Makefile targets**: `test`, `test-unit`, `test-integration`, `test-golden`, `test-golden-record`
- **CI**: GitHub Actions matrix on Python 3.10–3.13, runs `make lint` then `make test`
- **Lint**: Not a real linter — just `py_compile` on each script + `validate_anchors.py`. No ruff, flake8, mypy, or type checking.
- **Coverage**: `pytest-cov` is in requirements-dev.txt but no `.coveragerc`, no `--cov` flags in the Makefile, and no coverage reporting in CI. The `.coverage` file in the repo root suggests manual ad-hoc use.

## Test File Inventory (15 test files, 7 helpers/infra)

### Test files (`test_*.py`)

| File | Focus |
|------|-------|
| `test_lifecycle.py` | End-to-end: sprint_init → bootstrap → populate → version calc (real git + FakeGitHub) |
| `test_hexwise_setup.py` | Smoke: hexwise fixture through scanner → config → validate → bootstrap → populate |
| `test_golden_run.py` | Golden-run record/replay of full setup pipeline |
| `test_sprint_runtime.py` | check_status, bootstrap_github, populate_issues, sync_tracking, update_burndown |
| `test_gh_interactions.py` | commit.py validators and release_gate.py helpers (determine_bump, gate_stories, gate_ci, gate_prs) |
| `test_bugfix_regression.py` | BH-series regressions, arg-parsing, FakeGitHub infra tests, patch_gh tests |
| `test_kanban.py` | Kanban state machine: TF I/O, transitions, preconditions, atomic writes, locking, find_story, do_* commands |
| `test_sprint_analytics.py` | Sprint metrics: velocity, review rounds, workload, report formatting, main() integration |
| `test_release_gate.py` | calculate_version, validate_gates, gate_tests, gate_build, do_release |
| `test_pipeline_scripts.py` | team_voices, traceability, test_coverage, manage_epics, manage_sagas, setup_ci |
| `test_sprint_teardown.py` | classify_entries, remove_symlinks, remove_generated, remove_empty_dirs |
| `test_verify_fixes.py` | Config generation validation with MockProject (extra_personas variant) |
| `test_sync_backlog.py` | Backlog auto-sync: hashing, state file, debounce, throttle, do_sync |
| `test_validate_anchors.py` | Namespace resolution, anchor definitions, references |
| `test_property_parsing.py` | Hypothesis property-based tests for extract_story_id, extract_sp, _yaml_safe, _parse_team_index, parse_simple_toml |
| `test_fakegithub_fidelity.py` | Verifies jq expressions and search predicates match FakeGitHub behavior |

### Infrastructure files

| File | Purpose |
|------|---------|
| `conftest.py` | sys.path setup for all test files + enforces `jq` package availability |
| `fake_github.py` | `FakeGitHub` class + `make_patched_subprocess()` |
| `gh_test_helpers.py` | `MonitoredMock`, `patch_gh()`, `populate_test_issues()` |
| `mock_project.py` | `MockProject` — creates minimal Rust project in temp dir |
| `golden_recorder.py` | `GoldenRecorder` — captures state snapshots during pipeline execution |
| `golden_replay.py` | `GoldenReplayer` — loads recorded snapshots and asserts consistency |
| `fixtures/hexwise/` | Full Hexwise project fixture (Cargo.toml, personas, milestones, sagas, epics, PRD, test-plan) |

## Test Dependencies

From `requirements-dev.txt`:
```
pytest>=9.0
pytest-cov>=6.0
jq>=1.11
hypothesis>=6
```

The `jq` Python package is **hard-required** — `conftest.py` raises `ImportError` at collection time if it is missing. This is a C extension that requires system-level jq headers to compile (can be tricky on some platforms).

## Custom Test Doubles and Mock Patterns

### FakeGitHub (`fake_github.py`, ~992 lines)

The centerpiece of the test infrastructure. Simulates the entire `gh` CLI in-memory:

- **Dispatch-based**: Routes `gh` subcommands (label, api, issue, run, pr, release, auth, --version) to handler methods via `_DISPATCH` dict.
- **Full state tracking**: Maintains `labels`, `milestones`, `issues`, `prs`, `reviews`, `releases`, `runs`, `comparisons`, `commits_data`, `timeline_events`.
- **Shared counter**: Issues and PRs share `_next_number` (matches real GitHub behavior).
- **Flag parsing**: Custom `_parse_flags()` method handles `--flag value`, `--flag=value`, `-f value` short flags, and boolean bare flags.
- **Flag enforcement**: Three-tier system — `_KNOWN_FLAGS` (accepted), `_IMPLEMENTED_FLAGS` (actually evaluated), `_ACCEPTED_NOOP_FLAGS` (silently ignored). Unknown flags raise `NotImplementedError`.
- **Strict mode**: Default `strict=True` emits warnings when a known-but-unimplemented flag is passed, so tests don't silently ignore filter conditions.
- **jq support**: If the `jq` Python package is installed, `_maybe_apply_jq()` evaluates real jq expressions against the JSON data. Falls back to returning unfiltered data otherwise.
- **Milestone counter tracking**: Create, close, and edit operations maintain `open_issues`/`closed_issues` counts.
- **dump_state()**: Returns all state for golden-run snapshots.

### make_patched_subprocess (`fake_github.py`)

Creates a `subprocess.run` replacement that intercepts `gh` CLI calls and delegates to `FakeGitHub.handle()`. Non-gh subprocess calls pass through to real `subprocess.run`. Optional `verbose=True` prints intercepted commands.

### MonitoredMock / patch_gh (`gh_test_helpers.py`)

Anti-pattern prevention: `patch_gh` wraps `unittest.mock.patch` with a `MonitoredMock` proxy that tracks whether test code inspects `call_args`. If the mock is called but `call_args` is never checked, a `UserWarning` fires on context exit. This prevents the "mock returns what you assert" pattern where tests pass by verifying the mock's return value instead of production behavior.

### MockProject (`mock_project.py`)

Creates a minimal Rust project in a temp directory with:
- `Cargo.toml` for language detection
- Persona files (alice, bob, optional carol with different role format)
- Backlog with milestone
- Rules and dev guide
- Optional real git init or fake `.git/config`

### Golden Recording/Replay (`golden_recorder.py`, `golden_replay.py`)

Record-then-replay pattern for the full setup pipeline:
- **Record mode** (`GOLDEN_RECORD=1`): Captures FakeGitHub state + file tree at named phases, writes JSON snapshots to `tests/golden/recordings/`.
- **Replay mode**: Loads snapshots, runs pipeline, compares labels (including colors), milestones (including descriptions), issues (including labels and milestone assignments), and file tree (including contents).
- 5 recorded phases: `01-setup-init`, `02-setup-labels`, `03-setup-milestones`, `04-setup-issues`, `05-setup-ci`.

### Hexwise Fixture (`tests/fixtures/hexwise/`)

A complete mock project directory used by integration tests. Contains:
- Rust project files (`Cargo.toml`, `src/`)
- Team personas (rusti, checker, palette, giles + history files)
- 3 milestones, 6 epics, 2 sagas
- PRD sections, test plan, story map
- Rules and development guide

## Test Patterns Observed

1. **`unittest.TestCase` dominant**: Almost all tests use `unittest.TestCase` style. Only `test_property_parsing.py` uses pytest-native classes (no `unittest.TestCase` base, uses `assert` statements).
2. **Manual sys.path manipulation**: Despite conftest.py centralizing path setup, several test files redundantly do their own `sys.path.insert()` calls. conftest.py handles this, but old patterns remain.
3. **Two mocking strategies**: Tests use either `make_patched_subprocess` (patches `subprocess.run` globally, intercepts `gh` calls) or `unittest.mock.patch` on specific module-level functions (`check_status.gh_json`, `kanban.gh`, etc.). The two approaches are not mixed within a single test class.
4. **setUp/tearDown with temp dirs**: Integration tests create temp directories, `os.chdir()` into them, and clean up in tearDown. This is fragile if a test fails mid-setup.
5. **Strict FakeGitHub tearDown check**: `test_lifecycle.py` asserts no strict warnings in tearDown, which can mask the actual test failure.

## Red Flags

1. **FakeGitHub is a large, complex test double (~992 lines)**: It reimplements significant gh CLI behavior including flag parsing, milestone counters, jq evaluation, timeline events, and strict mode warnings. This is a fidelity risk — bugs in FakeGitHub can mask bugs in production code, or FakeGitHub can diverge from real gh behavior without detection. The `test_fakegithub_fidelity.py` file partially addresses this but only covers jq expressions and search predicates.

2. **No pytest configuration**: No markers, no test categorization, no timeout settings. The `test-unit` Makefile target hardcodes a single file (`test_gh_interactions.py`) rather than using markers to select fast tests.

3. **Coverage reporting not wired**: `pytest-cov` is installed but never invoked in CI or Makefile. The `.coverage` file exists but is untracked and appears to be from manual runs.

4. **Redundant sys.path manipulation**: conftest.py centralizes this, but at least 6 test files still do their own `sys.path.insert()` calls. This works but is a maintenance smell.

5. **os.chdir in tests**: Multiple test classes change the working directory in setUp/tearDown. If a test errors before tearDown runs, subsequent tests can run in the wrong directory. Python 3.11+ `unittest` handles this, but it is still fragile.

6. **No type checking**: No mypy, pyright, or similar. Combined with the stdlib-only constraint and custom TOML parser, type-related bugs can only be caught at runtime.

7. **Mixed test framework styles**: Most tests use `unittest.TestCase` with `self.assert*`, but `test_property_parsing.py` uses bare `assert` with hypothesis/pytest. This works but is inconsistent.

8. **FakeGitHub flag parsing reimplements argument parsing**: The custom `_parse_flags()` method handles `--flag value`, `--flag=value`, short flags, and boolean flags. This is a parallel implementation to whatever the production code constructs as gh argument lists, creating a potential fidelity gap.
