# 0e: Git Churn Analysis

Last 50 commits, production + test files ranked by change frequency.

## Top 20 Most-Changed Files

| Rank | File | Changes | Notes |
|------|------|---------|-------|
| 1 | tests/test_hooks.py | 13 | Highest churn — hook hardening |
| 2 | tests/test_verify_fixes.py | 9 | Regression test accumulator |
| 3 | scripts/kanban.py | 7 | Entry semantics, state machine |
| 4 | hooks/commit_gate.py | 7 | Security hardening |
| 5 | skills/sprint-run/scripts/sync_tracking.py | 6 | Two-path sync |
| 6 | skills/sprint-run/references/kanban-protocol.md | 6 | State machine docs |
| 7 | hooks/review_gate.py | 6 | Security hardening |
| 8 | tests/test_sprint_runtime.py | 6 | Runtime test updates |
| 9 | hooks/session_context.py | 5 | TOML + risk extraction |
| 10 | skills/sprint-monitor/scripts/check_status.py | 5 | Monitoring updates |
| 11 | scripts/sprint_init.py | 5 | Project scanning |
| 12 | tests/test_new_scripts.py | 5 | New script coverage |
| 13 | tests/test_kanban.py | 5 | Kanban test additions |
| 14 | tests/test_pipeline_scripts.py | 4 | Pipeline coverage |
| 15 | tests/test_bugfix_regression.py | 4 | Regression additions |
| 16 | skills/sprint-release/scripts/release_gate.py | 4 | Release gating |
| 17 | hooks/verify_agent_output.py | 3 | TOML consolidation |
| 18 | hooks/_common.py | 3 | Shared hook utils |
| 19 | scripts/validate_config.py | 3 | Foundation updates |
| 20 | scripts/validate_anchors.py | 3 | Namespace additions |

## High-Churn Hotspots

- **Hooks subsystem** (commit_gate, review_gate, session_context, _common): 4 files with 21 combined changes — most active subsystem
- **Kanban/sync path** (kanban.py, sync_tracking.py, kanban-protocol.md): 3 files with 19 combined changes
- **Test regression files** (test_verify_fixes, test_hooks, test_bugfix_regression): accumulate fixes
