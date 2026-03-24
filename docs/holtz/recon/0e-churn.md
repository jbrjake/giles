# Step 0e: Churn Analysis

**Run:** 6
**Date:** 2026-03-23

## Top 20 Most-Changed Files (all commits)

| Revisions | File | Notes |
|-----------|------|-------|
| 26 | tests/test_hooks.py | Most-changed test file; hooks subsystem refactored twice |
| 13 | scripts/kanban.py | State machine — most complex component |
| 12 | hooks/session_context.py | Moved from .claude-plugin/hooks/ |
| 12 | hooks/commit_gate.py | Moved from .claude-plugin/hooks/ |
| 11 | tests/test_new_scripts.py | Test file for newer scripts |
| 11 | hooks/review_gate.py | Moved from .claude-plugin/hooks/ |
| 10 | tests/test_kanban.py | Kanban state machine tests |
| 10 | skills/sprint-run/scripts/sync_tracking.py | Two-path state sync |
| 10 | hooks/verify_agent_output.py | Moved from .claude-plugin/hooks/ |
| 9 | tests/test_verify_fixes.py | Regression tests (largest test file) |
| 7 | tests/test_sprint_runtime.py | Runtime path tests |
| 7 | skills/sprint-monitor/scripts/check_status.py | CI/PR monitor |
| 6 | tests/test_pipeline_scripts.py | Pipeline script tests |
| 6 | scripts/smoke_test.py | Smoke test runner |
| 5 | scripts/validate_config.py | Hub module (most LOC) |
| 5 | scripts/sprint_init.py | Project scanner/generator |
| 5 | scripts/manage_epics.py | Epic CRUD |

## Observations

- Hook files have high churn from the `.claude-plugin/` → `hooks/` move + TOML parser consolidation.
- kanban.py (13 revisions) is the most-changed production script — state machine semantics have been refined across multiple audits (entry guards, forced-done warnings, integration entry).
- No new production scripts since the lint inventory check (`ce946e0`).
- Mutation scan: skipped (no mutation testing tool configured).
