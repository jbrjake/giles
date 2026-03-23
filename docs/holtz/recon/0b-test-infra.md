# 0b: Test Infrastructure

**Framework:** pytest 9.0.2 + hypothesis (property-based testing)
**Runner:** `python -m pytest tests/`
**Build:** Makefile with `make test`, `make lint`
**venv:** `.venv/` with requirements-dev.txt (pytest, hypothesis)

## Test Files (19)

| File | LOC | Focus |
|------|-----|-------|
| test_verify_fixes.py | 3141 | Regression tests for all prior bug-hunter fixes |
| test_sprint_runtime.py | 2548 | Sprint execution, ceremony, context recovery |
| test_pipeline_scripts.py | 2290 | Pipeline script integration |
| test_release_gate.py | 2102 | Release gating logic |
| test_bugfix_regression.py | 1529 | Bug-fix regression coverage |
| test_kanban.py | 1488 | Kanban state machine |
| test_hooks.py | 1383 | Hook subsystem |
| test_new_scripts.py | 642 | Newer script coverage |
| test_sprint_teardown.py | 638 | Teardown safety |
| test_property_parsing.py | 534 | Property-based TOML/config parsing |
| test_hexwise_setup.py | 510 | Deep-doc setup integration |
| test_lifecycle.py | 494 | Full lifecycle integration |
| test_sprint_analytics.py | 453 | Analytics calculations |
| test_validate_anchors.py | 392 | Anchor validation |
| test_gh_interactions.py | 326 | GitHub API interactions |
| test_sync_backlog.py | 315 | Backlog sync |
| test_golden_run.py | 274 | Golden snapshot replay |
| test_fakegithub_fidelity.py | 200 | Fake GitHub fidelity |

## Test Helpers

- `conftest.py` — shared fixtures
- `fake_github.py` (991 LOC) — mock GitHub CLI
- `gh_test_helpers.py` — GitHub test utilities
- `golden_recorder.py` / `golden_replay.py` — snapshot testing
- `mock_project.py` — project scaffolding for tests

## Skipped Tests

1 conditional skip: `test_golden_run.py:116` — skipTest when golden snapshots not recorded
No `@pytest.mark.skip` or `@unittest.skip` decorators
