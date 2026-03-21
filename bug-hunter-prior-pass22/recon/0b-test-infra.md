# 0b — Test Infrastructure

## Framework and runner

- **Framework**: pytest 9.0+
- **Runner**: `python -m pytest tests/ -v` (Makefile target: `make test`)
- **Plugins**: hypothesis 6+, pytest-cov 6+
- **Config**: no pytest.ini or pyproject.toml — all config is implicit; rootdir auto-detected as repo root

## Dev dependencies (`requirements-dev.txt`)

```
pytest>=9.0
pytest-cov>=6.0
jq>=1.11          # required for FakeGitHub jq-filter fidelity (enforced in conftest.py)
hypothesis>=6     # property-based testing
```

## conftest.py

`tests/conftest.py` does two things:
1. Adds all script directories to `sys.path` once (so tests don't each need `sys.path.insert`).
   Paths added: `tests/`, `scripts/`, `skills/*/scripts/` (setup, run, monitor, release).
2. Enforces `jq` package availability at collection time — raises `ImportError` if missing.

## Test file naming

All test files match `test_*.py`. 16 files:

| File | Focus |
|---|---|
| test_bugfix_regression.py | Regression guards for specific bug fixes |
| test_fakegithub_fidelity.py | FakeGitHub self-tests (flag parsing, jq) |
| test_gh_interactions.py | gh/gh_json call validation (unit) |
| test_golden_run.py | Golden snapshot replay |
| test_hexwise_setup.py | Integration: sprint-setup pipeline |
| test_kanban.py | Kanban state machine transitions |
| test_lifecycle.py | End-to-end sprint lifecycle (real git) |
| test_pipeline_scripts.py | Individual script unit tests |
| test_property_parsing.py | Hypothesis property tests for parsers |
| test_release_gate.py | Release gate validation logic |
| test_sprint_analytics.py | Velocity/workload metric computation |
| test_sprint_runtime.py | Sprint execution runtime behaviors |
| test_sprint_teardown.py | Teardown safety and classification |
| test_sync_backlog.py | Backlog auto-sync debounce/throttle |
| test_validate_anchors.py | Anchor reference validation |
| test_verify_fixes.py | Targeted fix verification tests |

## Key test helpers

**`fake_github.py`** — `FakeGitHub`: in-memory GitHub state machine that intercepts
`subprocess.run` calls to `gh`. Supports labels, milestones, issues, PRs, runs,
releases, timeline events, comparisons, commits. Strict mode (default) warns when
a flag is accepted but not evaluated. Uses Python `jq` package for filter fidelity.
`make_patched_subprocess()` creates the `subprocess.run` replacement.

**`gh_test_helpers.py`** — `MonitoredMock` / `patch_gh`: wraps `unittest.mock.patch`
to warn when a mock is called but `call_args` is never inspected (prevents mock
asserting mock behavior). Also provides `populate_test_issues()` shared helper.

**`mock_project.py`** — `MockProject`: creates a minimal Rust project in a temp dir
with personas, backlog, milestone file, RULES.md, DEVELOPMENT.md. Supports
`real_git=True` for tests that need an actual git repo.

## Fixtures and golden data

- `tests/fixtures/hexwise/` — fixture project files for integration tests
- `tests/golden/recordings/` — golden snapshot recordings for replay tests
- `tests/golden_recorder.py` / `tests/golden_replay.py` — record/replay helpers
