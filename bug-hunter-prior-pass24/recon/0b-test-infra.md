# 0b - Test Infrastructure

## Test Framework

- **Runner**: pytest 9.0.2
- **Python**: 3.10.15 (via pyenv)
- **Plugins**: hypothesis 6.151.9, pytest-cov 7.0.0
- **No pytest.ini, setup.cfg, pyproject.toml, or tox.ini** -- pytest runs with default configuration, no custom settings file
- **No .coveragerc** -- coverage is not pre-configured; must be invoked manually via `--cov` flags
- **Dev dependencies** (`requirements-dev.txt`): pytest>=9.0, pytest-cov>=6.0, jq>=1.11, hypothesis>=6

## conftest.py

Single conftest at `tests/conftest.py` (34 lines). It does two things:

1. **sys.path setup**: Adds 6 script directories to `sys.path` so test files can import production modules without per-file path manipulation:
   - `tests/`, `scripts/`, `skills/sprint-setup/scripts/`, `skills/sprint-run/scripts/`, `skills/sprint-monitor/scripts/`, `skills/sprint-release/scripts/`

2. **jq enforcement**: Imports `jq` at conftest load time and raises `ImportError` with install instructions if missing. This prevents FakeGitHub from silently degrading jq-dependent tests (BH21-002).

No pytest fixtures are defined in conftest.py. Fixtures are inline in individual test files.

## Test Support Files (not test files themselves)

| File | Lines | Purpose |
|------|-------|---------|
| `tests/conftest.py` | 34 | sys.path setup + jq enforcement |
| `tests/fake_github.py` | 991 | In-memory GitHub state double for `gh` CLI calls |
| `tests/gh_test_helpers.py` | 154 | `MonitoredMock` + `patch_gh` to prevent mock-returns-what-you-assert anti-pattern; `populate_test_issues` shared helper |
| `tests/golden_recorder.py` | 102 | Records FakeGitHub state snapshots at named phases |
| `tests/golden_replay.py` | 247 | Loads recorded golden snapshots and asserts consistency |
| `tests/mock_project.py` | 147 | Creates minimal mock Rust project in tmp dir (real or fake git) |

Golden recordings stored in `tests/golden/recordings/` (6 JSON files covering setup pipeline phases).

## Test Files Inventory

| File | Lines | Test Functions | Test Classes | Notes |
|------|------:|---------------:|-------------:|-------|
| `test_bugfix_regression.py` | 1474 | 93 | 42 | Regression tests for specific bug fixes (BH-series) |
| `test_verify_fixes.py` | 2460 | 135 | 58 | Verification tests for fixes (main/arg-parsing/happy-path) |
| `test_sprint_runtime.py` | 2102 | 175 | 39 | Sprint runtime operations (ceremony, tracking, sync) |
| `test_release_gate.py` | 1810 | 59 | 15 | Release gate validation, versioning, do_release integration |
| `test_pipeline_scripts.py` | 1568 | 136 | 16 | Pipeline script unit tests (bootstrap, populate, CI gen) |
| `test_kanban.py` | 989 | 62 | 14 | Kanban state machine transitions, locking, assign |
| `test_sprint_teardown.py` | 638 | 32 | 10 | Teardown classification, dry-run, execution |
| `test_property_parsing.py` | 527 | 38 | 5 | Hypothesis property-based tests for TOML, YAML, regex |
| `test_sprint_analytics.py` | 454 | 16 | 6 | Velocity, review rounds, workload metrics |
| `test_hexwise_setup.py` | 456 | 25 | 2 | End-to-end setup for "hexwise" sample project |
| `test_lifecycle.py` | 448 | 13 | 1 | Full lifecycle integration (setup through teardown) |
| `test_gh_interactions.py` | 428 | 41 | 8 | gh/gh_json call-argument contract tests |
| `test_sync_backlog.py` | 315 | 19 | 5 | Backlog sync with debounce/throttle |
| `test_fakegithub_fidelity.py` | 314 | 15 | 5 | FakeGitHub fidelity (label ops, release, multi-label) |
| `test_validate_anchors.py` | 299 | 26 | 5 | Anchor validation and fix-missing-anchors |
| `test_golden_run.py` | 272 | 4 | 2 | Golden-run recording and replay |

**Total**: 16 test files, 15,228 lines of test code, 889 test functions, ~233 test classes

## Test Architecture Patterns

- **unittest.TestCase** is the primary base class (not pytest-native classes)
- **FakeGitHub** (`fake_github.py`) is the central test double -- 991 lines of in-memory GitHub simulation that intercepts `subprocess.run` calls meant for `gh` CLI
- **MockProject** (`mock_project.py`) scaffolds realistic project structures in tmp dirs
- **MonitoredMock / patch_gh** (`gh_test_helpers.py`) wraps `unittest.mock.patch` to warn when tests don't verify mock call arguments (anti-pattern detection)
- **GoldenRecorder / GoldenReplayer** record and replay pipeline state snapshots for regression testing
- **Hypothesis** used in `test_property_parsing.py` for property-based testing of TOML parsing, YAML safety, regex extraction, and story ID parsing
- No pytest fixtures in conftest; test setup is done via `setUp()` methods in TestCase subclasses and context managers
