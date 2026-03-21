# 0e — Git Churn Analysis (BH37)

Generated: 2026-03-21 | Scope: last 50 commits (all 50 are fix/chore commits)

## Overall churn — top 20 files (last 50 commits)

| Rank | Touches | File | Category |
|------|---------|------|----------|
| 1 | 23 | `tests/test_hooks.py` | test |
| 2 | 14 | `scripts/kanban.py` | source |
| 3 | 11 | `tests/test_new_scripts.py` | test |
| 4 | 10 | `.claude-plugin/hooks/verify_agent_output.py` | hook |
| 5 | 9 | `.claude-plugin/hooks/review_gate.py` | hook |
| 6 | 8 | `tests/test_kanban.py` | test |
| 7 | 8 | `.claude-plugin/hooks/session_context.py` | hook |
| 8 | 8 | `.claude-plugin/hooks/commit_gate.py` | hook |
| 9 | 7 | `skills/sprint-run/scripts/sync_tracking.py` | source |
| 10 | 6 | `skills/sprint-monitor/scripts/check_status.py` | source |
| 11 | 5 | `scripts/smoke_test.py` | source |
| 12 | 5 | `scripts/manage_epics.py` | source |
| 13 | 4 | `tests/test_pipeline_scripts.py` | test |
| 14 | 4 | `scripts/sprint_init.py` | source |
| 15 | 4 | `scripts/risk_register.py` | source |
| 16 | 4 | `scripts/gap_scanner.py` | source |
| 17 | 4 | `scripts/assign_dod_level.py` | source |
| 18 | 4 | `.claude-plugin/plugin.json` | config |
| 19 | 3 | `tests/test_verify_fixes.py` | test |
| 20 | 3 | `tests/test_bugfix_regression.py` | test |

## Source-only churn in fix: commits (last 50)

All 50 commits matched `fix:` or `chore:`. Source-only ranking:

| Rank | Touches | File |
|------|---------|------|
| 1 | 23 | `scripts/validate_config.py` |
| 2 | 14 | `skills/sprint-run/scripts/sync_tracking.py` |
| 3 | 13 | `scripts/kanban.py` |
| 4 | 12 | `scripts/manage_epics.py` |
| 5 | 10 | `skills/sprint-setup/scripts/populate_issues.py` |
| 6 | 7 | `skills/sprint-monitor/scripts/check_status.py` |
| 7 | 7 | `scripts/sprint_init.py` |
| 8 | 6 | `scripts/manage_sagas.py` |
| 9 | 6 | `.claude-plugin/hooks/review_gate.py` |
| 10 | 4 | `skills/sprint-release/scripts/release_gate.py` |
| 11 | 4 | `scripts/traceability.py` |
| 12 | 4 | `scripts/sync_backlog.py` |
| 13 | 4 | `.claude-plugin/hooks/session_context.py` |
| 14 | 4 | `.claude-plugin/hooks/commit_gate.py` |
| 15 | 3 | `skills/sprint-setup/scripts/bootstrap_github.py` |
| 16 | 3 | `skills/sprint-run/scripts/update_burndown.py` |
| 17 | 3 | `scripts/validate_anchors.py` |
| 18 | 3 | `scripts/sprint_teardown.py` |
| 19 | 3 | `scripts/sprint_analytics.py` |

## Repo-wide stats

- Total commits: 415
- Total fix commits: 164 (40% of all commits)
- Last 50 commits: 100% fix/chore (bug-hunter passes 30-36)

## Hotspot summary

The top churn cluster is clear:

1. **validate_config.py** (23 fix touches) — shared helper library, every bug-hunter pass touches it
2. **kanban.py** (13-14 touches) — state machine with lock/transition logic, repeated concurrency and edge-case fixes
3. **sync_tracking.py** (7-14 touches) — reconciliation path, TOCTOU and atomic-write fixes
4. **hooks subsystem** (4 files, 6-10 touches each) — review_gate, commit_gate, session_context, verify_agent_output
5. **manage_epics.py** (10-12 touches) — CRUD parsing, repeated regex/field fixes
6. **populate_issues.py** (8-10 touches) — milestone/story parsing edge cases
7. **check_status.py** (6-7 touches) — compound command handling, drift detection

These 7 areas account for the vast majority of bug-fix churn and are the highest-priority targets for BH37 scrutiny.
