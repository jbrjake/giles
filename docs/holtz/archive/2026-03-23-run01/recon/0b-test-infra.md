# Step 0b: Test Infrastructure

**Framework:** pytest 9.0+ with hypothesis 6+ for property-based testing
**Runner:** `make test` → `.venv/bin/python -m pytest tests/ -v`
**Build system:** Makefile with venv management
**Coverage tool:** pytest-cov (installed but no make target)
**Linter:** ruff (config exists at ruff.toml, not installed in venv; Makefile uses py_compile)
**Anchor validator:** `scripts/validate_anchors.py` (run as part of `make lint`)

## Test Categories

| Target | Command |
|--------|---------|
| All tests | `make test` |
| Unit only | `make test-unit` |
| Integration | `make test-integration` |
| Golden replay | `make test-golden` |
| Lint | `make lint` (py_compile + validate_anchors) |

## Test File Inventory (20 files)

| File | Focus |
|------|-------|
| test_pipeline_scripts.py | validate_config, TOML parser, shared helpers |
| test_kanban.py | Kanban state machine, transitions, sync |
| test_sprint_runtime.py | Sprint init, sprint detection, check_status |
| test_verify_fixes.py | Regression tests for bug-hunter fixes |
| test_bugfix_regression.py | Earlier regression tests |
| test_hooks.py | Hook JSON protocol, commit/review/session hooks |
| test_lifecycle.py | End-to-end lifecycle integration |
| test_hexwise_setup.py | Integration test with hexwise sample project |
| test_golden_run.py | Golden recording replay |
| test_release_gate.py | Release gate validation |
| test_sprint_analytics.py | Sprint analytics computation |
| test_sprint_teardown.py | Teardown safety |
| test_gh_interactions.py | GitHub interaction patterns |
| test_new_scripts.py | Newer scripts (smoke_test, gap_scanner, etc.) |
| test_property_parsing.py | Hypothesis property tests for parsing |
| test_sync_backlog.py | Backlog sync with debounce |
| test_validate_anchors.py | Anchor validation |
| test_fakegithub_fidelity.py | FakeGitHub test double fidelity |

## Test Helpers

| File | Purpose |
|------|---------|
| conftest.py | Shared fixtures |
| fake_github.py | FakeGitHub test double for `gh` CLI |
| gh_test_helpers.py | Helper functions for gh mocking |
| mock_project.py | Mock project scaffold for integration tests |
| golden_recorder.py | Record golden snapshots |
| golden_replay.py | Replay golden snapshots |

## Dev Dependencies (requirements-dev.txt)

```
pytest>=9.0
pytest-cov>=6.0
jq>=1.11        # jq expression evaluation in FakeGitHub
hypothesis>=6   # property-based testing
```
