# 0b: Test Infrastructure

## Test Framework

- **pytest** >= 9.0, run via `python -m pytest tests/ -v`
- **hypothesis** >= 6 for property-based testing (fuzz/invariant tests on parsers and regex)
- **pytest-cov** >= 6.0 listed in dev deps (coverage reporting)
- **jq** >= 1.11 (Python bindings) -- required by conftest.py; FakeGitHub uses it for full-fidelity jq filter evaluation
- **unittest** is the dominant test-class style (`unittest.TestCase` subclasses); hypothesis tests use bare pytest-style classes

No pyproject.toml, setup.cfg, tox.ini, or pytest.ini -- zero pytest configuration beyond conftest.py.

## Python Version

- `.python-version` specifies 3.10
- CI matrix: 3.10, 3.11, 3.12, 3.13

## Test File Locations and Naming

All tests live in `tests/` (flat, no subdirectories for test files):

| File | Lines | Focus |
|------|-------|-------|
| `test_verify_fixes.py` | 114,888 | BH-series fix verification (largest file) |
| `test_pipeline_scripts.py` | 98,433 | Pipeline script unit tests |
| `test_sprint_runtime.py` | 101,591 | Sprint runtime module tests |
| `test_release_gate.py` | 83,308 | Release gate unit tests |
| `test_bugfix_regression.py` | 64,082 | Arg-parsing, FakeGitHub infra, BH regressions |
| `test_kanban.py` | 64,543 | Kanban state machine tests |
| `test_hooks.py` | 47,870 | Hook tests |
| `test_sprint_teardown.py` | 24,165 | Teardown safety tests |
| `test_property_parsing.py` | 21,146 | Hypothesis property tests for 5 parsing hotspots |
| `test_hexwise_setup.py` | 21,231 | Integration test with hexwise fixture project |
| `test_lifecycle.py` | 20,774 | End-to-end lifecycle integration |
| `test_new_scripts.py` | 18,414 | New script unit tests |
| `test_sprint_analytics.py` | 17,490 | Sprint analytics tests |
| `test_gh_interactions.py` | 15,490 | Commit/release helper unit tests |
| `test_sync_backlog.py` | 13,967 | Backlog sync tests |
| `test_fakegithub_fidelity.py` | 11,900 | FakeGitHub self-tests |
| `test_golden_run.py` | 10,978 | Golden snapshot record/replay |
| `test_validate_anchors.py` | 11,337 | Anchor validation tests |

**Total: ~18,500 lines, ~1,165 test methods across 18 test files.**

## Key Test Utilities (non-test modules in `tests/`)

| File | Purpose |
|------|---------|
| `conftest.py` | Adds all script dirs to sys.path; enforces `jq` package availability |
| `fake_github.py` | In-memory GitHub API simulator (~990 lines). Intercepts `subprocess.run` for `gh` CLI calls. Dispatch-based routing for label/issue/pr/run/release/api commands. Strict mode warns on unimplemented flag usage. |
| `mock_project.py` | Creates a temp Rust project with personas, backlog, and optional real git repo. Shared by lifecycle and regression tests. |
| `gh_test_helpers.py` | `MonitoredMock` wrapper that detects when tests don't inspect `call_args` (anti-pattern guard). `patch_gh` context manager. `populate_test_issues` shared helper. |
| `golden_recorder.py` | Captures FakeGitHub state + file tree at named phases for snapshot testing |
| `golden_replay.py` | Loads golden snapshots and asserts labels/milestones/issues/files match |

## Fixture Data

- `tests/fixtures/hexwise/` -- a complete mock Rust project ("hexwise" color utility) with Cargo.toml, personas, milestones, epics, sagas, PRD, test plan, and story map
- `tests/golden/recordings/` -- 5 golden snapshot JSON files (setup phases 01-05) plus manifest

## Build / CI

- **Makefile** is the build system entry point
- Targets: `test` (all), `test-unit`, `test-integration`, `test-golden`, `test-golden-record`, `lint`, `venv`, `clean`
- Venv created in `.venv/` with `requirements-dev.txt`
- **CI**: `.github/workflows/ci.yml` -- GitHub Actions, runs on push/PR to main
  - Matrix: Python 3.10-3.13 on ubuntu-latest
  - Steps: checkout, setup-python, create venv + install deps, `make lint`, `make test`
  - Uses actions/checkout@v6 and actions/setup-python@v6

## Linting / Type Checking

- **No dedicated linter** (no ruff, flake8, mypy, pylint)
- `make lint` uses `python -m py_compile` on each script file (syntax-only check)
- Also runs `scripts/validate_anchors.py` (checks doc anchor references)
- No type checking configured (no mypy.ini, no pyright config)

## Mocking Approach

Two mocking strategies coexist:

1. **FakeGitHub + subprocess patching** (integration tests): `make_patched_subprocess(fake_gh)` returns a `subprocess.run` replacement that intercepts `gh` CLI calls and routes them to the in-memory FakeGitHub simulator. Real git commands pass through to actual git.

2. **unittest.mock.patch** (unit tests): Standard `@patch("module.gh_json")` for isolating individual functions. `patch_gh` context manager adds call-arg inspection enforcement.

## Configuration Quirks

- No pytest config file at all -- defaults everywhere
- conftest.py does heavy sys.path manipulation (6 directories) so test files can import production scripts directly by name
- FakeGitHub has a strict mode (default on) that warns when tests pass flags that aren't actually evaluated -- prevents false confidence
- Golden tests are mode-switched via `GOLDEN_RECORD=1` env var
- The `jq` Python package is enforced at import time in conftest.py (hard failure if missing)
- Several test files are extremely large (100K+ lines) -- likely generated or accumulated from many bug-hunter passes
