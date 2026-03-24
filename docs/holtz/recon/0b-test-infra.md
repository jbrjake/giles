# Step 0b: Test Infrastructure

**Run:** 6
**Date:** 2026-03-23

## Framework

- **Runner:** pytest
- **Property testing:** hypothesis (via `tests/test_property_parsing.py`)
- **Mock system:** `tests/fake_github.py` — subprocess-level mock of `gh` CLI
- **Fixtures:** `tests/conftest.py` — shared fixtures
- **Golden testing:** `tests/golden_recorder.py`, `tests/golden_replay.py`
- **Build system:** Makefile with `test`, `lint`, `ci` targets

## Test Types

| Type | Files | Description |
|------|-------|-------------|
| Unit | test_kanban, test_pipeline_scripts, test_new_scripts, test_sprint_analytics, test_sprint_teardown, test_property_parsing, test_validate_anchors, test_check_lint_inventory | Direct function testing |
| Integration | test_lifecycle, test_gh_interactions, test_hexwise_setup, test_golden_run, test_sync_backlog | End-to-end with fake GitHub |
| Regression | test_bugfix_regression, test_verify_fixes | Specific bug reproductions |
| Hook | test_hooks | Hook behavior testing |
| Release | test_release_gate | Release gate testing |
| Runtime | test_sprint_runtime | Sprint execution paths |
| Fidelity | test_fakegithub_fidelity | Mock accuracy testing |

## Commands

- `make test` — full test suite
- `make lint` — py_compile on all production scripts
- `make ci` — lint + test
