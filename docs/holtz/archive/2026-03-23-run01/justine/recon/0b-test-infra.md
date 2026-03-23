# 0b: Test Infrastructure

**Framework:** pytest (via python -m pytest)
**Runner:** pytest + hypothesis (property-based), pyjq (JSON query in FakeGitHub)
**Build system:** Makefile (make test)
**Config:** conftest.py centralizes sys.path for all test files
**Dependencies:** requirements-dev.txt (hypothesis, pyjq, pytest)

## Test File Inventory (18 test files)

| File | Size | Focus |
|------|------|-------|
| test_verify_fixes.py | 124K | Regression for prior bug-hunter fixes |
| test_sprint_runtime.py | 106K | Sprint execution lifecycle |
| test_pipeline_scripts.py | 97K | All pipeline scripts |
| test_release_gate.py | 83K | Release gate checks |
| test_kanban.py | 67K | Kanban state machine |
| test_bugfix_regression.py | 65K | More regression tests |
| test_hooks.py | 54K | Hook functionality |
| test_sprint_teardown.py | 24K | Sprint teardown |
| test_hexwise_setup.py | 21K | Setup end-to-end |
| test_property_parsing.py | 21K | Property-based TOML/frontmatter tests |
| test_lifecycle.py | 21K | Lifecycle tests |
| test_new_scripts.py | 19K | New utility scripts |
| test_sprint_analytics.py | 17K | Analytics tests |
| test_gh_interactions.py | 15K | GitHub interaction tests |
| test_sync_backlog.py | 14K | Backlog sync tests |
| test_fakegithub_fidelity.py | 12K | FakeGitHub fidelity checks |
| test_validate_anchors.py | 11K | Anchor validation tests |
| test_golden_run.py | 11K | Golden path replay tests |

## Test Helpers

- `fake_github.py` (41K) -- mock gh CLI, handles JSON queries via jq
- `gh_test_helpers.py` (5K) -- GitHub test utilities
- `mock_project.py` (5K) -- sprint-config scaffolding
- `golden_recorder.py` / `golden_replay.py` -- golden path recording

## Observations

- conftest.py enforces jq availability (BH21-002)
- Heavy regression test focus (test_verify_fixes 124K, test_bugfix_regression 65K) -- prior audits drove this
- FakeGitHub at 41K is a substantial testing subsystem
