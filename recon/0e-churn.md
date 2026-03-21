# 0e — Git Churn Analysis

**Scope:** Last 50 commits on `main`
**Date:** 2026-03-21

## Top 20 Most-Changed Files

| Rank | Changes | File | Category |
|------|---------|------|----------|
| 1 | 22 | `tests/test_hooks.py` | test |
| 2 | 12 | `scripts/kanban.py` | **production** |
| 3 | 11 | `tests/test_new_scripts.py` | test |
| 4 | 9 | `.claude-plugin/hooks/verify_agent_output.py` | **production** |
| 5 | 8 | `tests/test_kanban.py` | test |
| 6 | 8 | `.claude-plugin/hooks/review_gate.py` | **production** |
| 7 | 8 | `BUG-HUNTER-STATUS.md` | docs |
| 8 | 7 | `.claude-plugin/hooks/session_context.py` | **production** |
| 9 | 7 | `.claude-plugin/hooks/commit_gate.py` | **production** |
| 10 | 6 | `skills/sprint-run/scripts/sync_tracking.py` | **production** |
| 11 | 6 | `skills/sprint-monitor/scripts/check_status.py` | **production** |
| 12 | 6 | `BUG-HUNTER-PUNCHLIST.md` | docs |
| 13 | 5 | `scripts/smoke_test.py` | **production** |
| 14 | 5 | `.claude-plugin/plugin.json` | config |
| 15 | 4 | `tests/test_pipeline_scripts.py` | test |
| 16 | 4 | `scripts/risk_register.py` | **production** |
| 17 | 4 | `scripts/manage_epics.py` | **production** |
| 18 | 4 | `scripts/gap_scanner.py` | **production** |
| 19 | 3 | `tests/test_verify_fixes.py` | test |
| 20 | 3 | `tests/test_bugfix_regression.py` | test |

## Modifications-Only View (top 10 production)

Filtering to `--diff-filter=M` (modifications, excluding adds/deletes) shifts the
picture slightly — files that were created once but modified many times rank higher:

| Changes | File |
|---------|------|
| 13 | `scripts/kanban.py` |
| 8 | `.claude-plugin/hooks/verify_agent_output.py` |
| 7 | `.claude-plugin/hooks/review_gate.py` |
| 6 | `.claude-plugin/hooks/session_context.py` |
| 6 | `.claude-plugin/hooks/commit_gate.py` |
| 6 | `skills/sprint-run/scripts/sync_tracking.py` |
| 6 | `skills/sprint-monitor/scripts/check_status.py` |
| 4 | `scripts/smoke_test.py` |
| 4 | `scripts/manage_epics.py` |
| 3 | `scripts/validate_config.py` |

## Production Files Ranked by Churn (audit priority)

These are the production files most likely to harbor bugs due to repeated modification:

1. **`scripts/kanban.py`** — 12-13 changes. The central state machine. Highest churn
   of any production file by a wide margin. Top audit priority.
2. **`.claude-plugin/hooks/verify_agent_output.py`** — 8-9 changes. Hook that validates
   agent output. Second highest.
3. **`.claude-plugin/hooks/review_gate.py`** — 7-8 changes. PR review gating hook.
4. **`.claude-plugin/hooks/session_context.py`** — 6-7 changes. Session context injection.
5. **`.claude-plugin/hooks/commit_gate.py`** — 6-7 changes. Commit validation hook.
6. **`skills/sprint-run/scripts/sync_tracking.py`** — 6 changes. Reconciles local
   tracking with GitHub state. Known two-path interaction with kanban.py.
7. **`skills/sprint-monitor/scripts/check_status.py`** — 6 changes. CI/PR/milestone
   monitoring.
8. **`scripts/smoke_test.py`** — 4-5 changes. Runs smoke commands, writes history.
9. **`scripts/manage_epics.py`** — 4 changes. Epic CRUD operations.
10. **`scripts/risk_register.py`** — 4 changes. Risk register CRUD.

## Observations

- **The hooks subsystem is a hotspot.** Four files under `.claude-plugin/hooks/` account
  for 28-30 changes combined. These are relatively new (added as part of plugin
  infrastructure) and have been repeatedly patched — classic bug-magnet pattern.
- **kanban.py dominates.** It is the single most-modified production file. Its role
  as the mutation path for story state makes bugs here high-impact.
- **sync_tracking.py + kanban.py** share responsibility for tracking state. The
  two-path architecture is documented as intentional, but churn in both files
  suggests ongoing friction at the boundary.
- **Test churn mirrors production churn.** `test_hooks.py` (22 changes) and
  `test_kanban.py` (8 changes) track their production counterparts closely, which
  is healthy — but high test churn can also indicate flaky or repeatedly-broken tests.
- **validate_config.py** has only 3 changes despite being the shared utility layer.
  This suggests it has stabilized. Lower audit priority.
