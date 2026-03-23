# Step 0e: Git Churn Analysis

**Date:** 2026-03-23
**Window:** Last 50 commits

## Top 25 Most-Changed Files

| Changes | File | Category |
|---------|------|----------|
| 18 | tests/test_hooks.py | test |
| 12 | BUG-HUNTER-STATUS.md | audit artifact |
| 11 | BUG-HUNTER-PUNCHLIST.md | audit artifact |
| 10 | .claude-plugin/hooks/commit_gate.py | hooks (OLD path) |
| 9 | skills/sprint-run/scripts/sync_tracking.py | production |
| 9 | scripts/kanban.py | production |
| 9 | .claude-plugin/hooks/session_context.py | hooks (OLD path) |
| 8 | tests/test_kanban.py | test |
| 8 | .claude-plugin/hooks/review_gate.py | hooks (OLD path) |
| 7 | tests/test_verify_fixes.py | test |
| 7 | tests/test_sprint_runtime.py | test |
| 7 | tests/test_new_scripts.py | test |
| 7 | .claude-plugin/plugin.json | plugin manifest |
| 6 | tests/test_pipeline_scripts.py | test |
| 6 | .claude-plugin/hooks/verify_agent_output.py | hooks (OLD path) |
| 5 | tests/test_bugfix_regression.py | test |
| 5 | skills/sprint-monitor/scripts/check_status.py | production |
| 5 | scripts/sprint_init.py | production |
| 5 | scripts/manage_epics.py | production |
| 4 | skills/sprint-release/scripts/release_gate.py | production |
| 4 | scripts/validate_config.py | production |
| 4 | scripts/smoke_test.py | production |
| 4 | scripts/manage_sagas.py | production |

## Key Observations

1. **Hooks are highest churn** — but at OLD path `.claude-plugin/hooks/`. Most recent commit moved them to `hooks/` at project root. This is a structural change worth verifying.
2. **sync_tracking.py + kanban.py** — the two-path state management pair both have high churn (9 changes each). Seam bugs likely.
3. **check_status.py** — sprint monitor script with 5 changes, complex integration with GitHub APIs.
4. **Test files dominate** — natural for a project that's been through 39 bug-hunter passes.
5. **Hooks relocation:** Recent refactor moved hooks from `.claude-plugin/hooks/` to `hooks/`. Need to verify all references updated.
