# 0e: Git Churn Analysis

Top 20 most-changed files in last 50 commits:

| Changes | File |
|---------|------|
| 18 | tests/test_hooks.py |
| 12 | BUG-HUNTER-STATUS.md |
| 11 | BUG-HUNTER-PUNCHLIST.md |
| 11 | .claude-plugin/hooks/commit_gate.py (now hooks/commit_gate.py) |
| 10 | .claude-plugin/hooks/session_context.py (now hooks/session_context.py) |
| 9 | skills/sprint-run/scripts/sync_tracking.py |
| 9 | scripts/kanban.py |
| 9 | .claude-plugin/hooks/review_gate.py (now hooks/review_gate.py) |
| 8 | tests/test_kanban.py |
| 7 | tests/test_verify_fixes.py |
| 7 | tests/test_sprint_runtime.py |
| 7 | tests/test_new_scripts.py |
| 7 | .claude-plugin/plugin.json |
| 7 | .claude-plugin/hooks/verify_agent_output.py |
| 6 | tests/test_pipeline_scripts.py |
| 5 | tests/test_bugfix_regression.py |
| 5 | skills/sprint-monitor/scripts/check_status.py |
| 5 | scripts/sprint_init.py |
| 5 | scripts/manage_epics.py |

## Risk Assessment

- **Hooks are the hottest code**: 4 of top 10 files are hook files. Recent refactor moved them from .claude-plugin/hooks/ to hooks/. High churn = high risk of regression.
- **Kanban + sync_tracking**: Both highly churned (9 changes each). Dual-path state management is inherently fragile.
- **Test files churn with code**: Expected correlation -- fixes drive test additions.
