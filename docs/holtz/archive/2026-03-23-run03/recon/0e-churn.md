# 0e: Churn Analysis (Run 3)

Top files by change frequency (last 50 commits):

| Changes | File | Notes |
|---------|------|-------|
| 19 | tests/test_hooks.py | Highest churn — hooks are the most-evolved subsystem |
| 10 | hooks/commit_gate.py | Security-critical hook |
| 9 | scripts/kanban.py | State machine — complex logic |
| 9 | hooks/session_context.py | Recently refactored (BJ-010) |
| 8 | tests/test_verify_fixes.py | Regression tests |
| 8 | tests/test_new_scripts.py | New script coverage |
| 8 | skills/sprint-run/scripts/sync_tracking.py | Reconciliation path |
| 8 | hooks/review_gate.py | Security-critical hook |
| 7 | tests/test_kanban.py | State machine tests |
| 5 | scripts/validate_config.py | Hub module |
| 5 | scripts/sprint_init.py | Config generator |
| 5 | scripts/manage_epics.py | Epic CRUD |
| 5 | skills/sprint-monitor/scripts/check_status.py | CI/PR monitoring |

**Assessment:** Hooks subsystem has the highest churn (3 of top 10 files). However, Run 2 specifically audited and hardened hooks. The session_context changes since Run 2 are a refactoring of format_context (BJ-010 truncation).
