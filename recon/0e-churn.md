# Phase 0e — Git Churn Analysis

## Top 30 Files by Commit Frequency (last 50 commits)

| Commits | File |
|---------|------|
| 21 | tests/test_hooks.py |
| 12 | scripts/kanban.py |
| 11 | tests/test_new_scripts.py |
| 11 | BUG-HUNTER-STATUS.md |
| 10 | skills/sprint-run/scripts/sync_tracking.py |
| 10 | BUG-HUNTER-PUNCHLIST.md |
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
| 4 | scripts/gap_scanner.py |
| 4 | recon/0c-test-baseline.md |
| 4 | recon/0a-project-overview.md |
| 3 | tests/test_property_parsing.py |
| 3 | skills/sprint-release/scripts/release_gate.py |
| 3 | scripts/validate_config.py |
| 3 | scripts/history_to_checklist.py |
| 3 | recon/0g-recon-summary.md |

## Hotspot Analysis

**Primary hotspot: `tests/test_hooks.py`** — 21 commits. Massive churn from iterative bug-fix passes. Risk of accumulated cruft, duplicate tests, or weakened assertions from repeated edits.

**Secondary hotspots:**
- `scripts/kanban.py` (12 commits) — core state machine, complex mutation logic
- `skills/sprint-run/scripts/sync_tracking.py` (10 commits) — reconciliation path, dual-write complexity
- `.claude-plugin/hooks/` (review_gate 10, verify_agent_output 9, session_context 8, commit_gate 8) — hook layer has been heavily iterated

**Test files with high churn** (test_hooks 21, test_new_scripts 11, test_kanban 8) should be checked for test quality degradation from repeated patching.
