# 0d — Lint Results

## Linter configuration

No ruff.toml, .flake8, pyproject.toml, mypy.ini, or setup.cfg found.
No third-party linter is installed (`ruff` not on PATH).

Makefile `lint` target runs `python -m py_compile` on all production scripts,
then runs `python scripts/validate_anchors.py`.

## Syntax check (`py_compile`)

All 19 production scripts compile cleanly:

- `scripts/` (12 files): validate_config.py, sprint_init.py, sprint_teardown.py,
  commit.py, sync_backlog.py, manage_epics.py, manage_sagas.py, sprint_analytics.py,
  team_voices.py, test_coverage.py, traceability.py, validate_anchors.py
- `skills/sprint-setup/scripts/` (3): bootstrap_github.py, populate_issues.py, setup_ci.py
- `skills/sprint-run/scripts/` (2): sync_tracking.py, update_burndown.py
- `skills/sprint-monitor/scripts/` (1): check_status.py
- `skills/sprint-release/scripts/` (1): release_gate.py

**Result: 0 syntax errors**

## Anchor validation (`validate_anchors.py`)

**Exit code: 1** — issues found:

### Unreferenced anchors (6, info-level)

These anchors are defined but nothing links to them:
- `§populate_issues._safe_compile_pattern`
- `§sprint-run.state_management`
- `§validate_config.TABLE_ROW`
- `§validate_config._yaml_safe`
- `§validate_config.frontmatter_value`
- `§validate_config.short_title`

### Broken references (23, error-level)

**Unknown namespace `kanban`** (10 refs in CLAUDE.md + CHEATSHEET.md):
References to `§kanban.*` functions that don't exist as a namespace. These
were likely left over from a script that was refactored or renamed.
Broken refs: TRANSITIONS, validate_transition, check_preconditions,
do_transition, do_assign, do_sync, do_status, find_story, atomic_write_tf, main.

**Stale sync_tracking anchors** (4 refs in CHEATSHEET.md):
- `§sync_tracking.slug_from_title` — anchor not found
- `§sync_tracking.TF` — anchor not found
- `§sync_tracking.read_tf` — anchor not found
- `§sync_tracking.write_tf` — anchor not found

These were likely removed or renamed during a sync_tracking.py refactor.

## Summary

| Check | Result |
|---|---|
| py_compile (syntax) | PASS — 0 errors |
| validate_anchors (unreferenced) | 6 info items (non-blocking) |
| validate_anchors (broken refs) | 23 broken references (exit 1) |
| ruff / flake8 / mypy | not configured |
