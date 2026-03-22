# Phase 0e — Git Churn Analysis (Pass 38)

## Top 20 Files by Commit Frequency (last 50 commits)

| Commits | File |
|---------|------|
| 21 | tests/test_hooks.py |
| 12 | scripts/kanban.py |
| 11 | tests/test_new_scripts.py |
| 10 | skills/sprint-run/scripts/sync_tracking.py |
| 10 | .claude-plugin/hooks/review_gate.py |
| 9 | .claude-plugin/hooks/verify_agent_output.py |
| 8 | tests/test_kanban.py |
| 8 | .claude-plugin/hooks/session_context.py |
| 8 | .claude-plugin/hooks/commit_gate.py |
| 7 | tests/test_verify_fixes.py |
| 7 | skills/sprint-monitor/scripts/check_status.py |
| 6 | tests/test_sprint_runtime.py |
| 6 | tests/test_pipeline_scripts.py |
| 6 | scripts/smoke_test.py |
| 5 | tests/test_bugfix_regression.py |
| 5 | scripts/sprint_init.py |
| 5 | scripts/risk_register.py |
| 5 | scripts/manage_epics.py |
| 5 | scripts/assign_dod_level.py |
| 4 | scripts/manage_sagas.py |

## Top 20 Files by Lines Changed (last 50 commits)

| Insertions | Deletions | File |
|------------|-----------|------|
| 992 | 29 | tests/test_hooks.py |
| 520 | 575 | BUG-HUNTER-PUNCHLIST.md |
| 331 | 321 | BUG-HUNTER-STATUS.md |

(Remaining top entries are docs/plans/recon files — not source code)

## Hotspot Analysis

**Primary hotspot: `tests/test_hooks.py`** — 21 commits, 992 lines inserted. Massive churn, likely from iterative bug-fix passes. High risk of accumulated cruft, duplicate tests, or weakened assertions from repeated edits.

**Secondary hotspots:**
- `scripts/kanban.py` (12 commits) — core state machine, complex mutation logic
- `skills/sprint-run/scripts/sync_tracking.py` (10 commits) — reconciliation path, dual-write complexity
- `.claude-plugin/hooks/` (review_gate 10, verify_agent_output 9, session_context 8, commit_gate 8) — hook layer has been heavily iterated

**Test files with high churn** (test_hooks 21, test_new_scripts 11, test_kanban 8) should be checked for test quality degradation from repeated patching.
