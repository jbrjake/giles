# 0e: Churn Analysis

Top 20 most-changed files in last 50 commits:

| Changes | File |
|---------|------|
| 19 | tests/test_hooks.py |
| 10 | hooks/commit_gate.py |
| 9 | scripts/kanban.py |
| 9 | hooks/session_context.py |
| 8 | tests/test_verify_fixes.py |
| 8 | tests/test_new_scripts.py |
| 8 | skills/sprint-run/scripts/sync_tracking.py |
| 8 | hooks/review_gate.py |
| 7 | tests/test_kanban.py |
| 6 | tests/test_sprint_runtime.py |
| 6 | tests/test_pipeline_scripts.py |
| 5 | tests/test_bugfix_regression.py |
| 5 | skills/sprint-monitor/scripts/check_status.py |
| 5 | scripts/validate_config.py |
| 5 | scripts/sprint_init.py |
| 5 | scripts/manage_epics.py |
| 4 | skills/sprint-release/scripts/release_gate.py |
| 4 | scripts/smoke_test.py |
| 4 | scripts/manage_sagas.py |
| 4 | hooks/verify_agent_output.py |

## Analysis

- **test_hooks.py** is highest churn (19 changes in 50 commits) -- hooks are an active development area
- **commit_gate.py** at 10 -- many edge cases being patched
- **kanban.py** at 9 -- state machine has seen significant refinement
- **sync_tracking.py** at 8 -- the reconciliation path is evolving
- High churn in hooks subsystem overall (commit_gate + session_context + review_gate + verify_agent_output = 31 changes combined)
