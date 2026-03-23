# 0a: Project Overview (Run 3)

**Project:** giles — Claude Code plugin for agile sprints with persona-based development
**Language:** Python 3.10+ (stdlib-only runtime)
**Structure:** 32 production files, 24 test files (56 total)
**Entry points:** 5 skills (sprint-setup, sprint-run, sprint-monitor, sprint-release, sprint-teardown)

## Production Code Layout

- `hooks/` (5 files): _common.py, commit_gate.py, review_gate.py, session_context.py, verify_agent_output.py
- `scripts/` (18 files): validate_config.py (hub, ~1245 LOC), kanban.py, sprint_init.py, and 15 others
- `skills/*/scripts/` (7 files): bootstrap_github.py, populate_issues.py, setup_ci.py, sync_tracking.py, update_burndown.py, check_status.py, release_gate.py
- `references/skeletons/` (20 .tmpl files): scaffold templates for sprint-config/

## Changes Since Run 2 (2 commits)

1. `commit_gate.py` — comment-only change documenting BJ-011 quoting limitation
2. `session_context.py` — refactored `format_context()` to use `_add_section()` helper with truncation (`_MAX_ITEMS_PER_SECTION = 10`) for BJ-010

**Assessment:** Minimal production changes. No new modules, no architectural shifts. Both changes are post-audit hardening.
