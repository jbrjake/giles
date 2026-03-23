# Step 0g: Recon Summary

**Project:** giles — Claude Code plugin for agile sprints with persona-based development
**Date:** 2026-03-23
**Python 3.10+, stdlib-only runtime, 25 production scripts (~10k LOC), 1188 tests passing**

## Critical Facts for Audit

1. **Test baseline:** 1188 pass, 0 fail, 0 skip, 19.37s. Clean starting point.
2. **Lint:** All py_compile pass. **21 broken anchor references** in CLAUDE.md — 6 scripts missing `§` anchor comments.
3. **Churn hotspots (production):** sync_tracking.py (9), kanban.py (9), check_status.py (5), sprint_init.py (5), manage_epics.py (5)
4. **Hooks relocated:** Recent refactor moved hooks from `.claude-plugin/hooks/` to `hooks/` at plugin root with JSON output protocol. hooks.json references `${CLAUDE_PLUGIN_ROOT}/hooks/` paths. **Verify all references updated.**
5. **Impact graph:** 31 nodes, 30 import edges. validate_config is the hub (20 dependents).
6. **Prior audit context:** 39 bug-hunter passes converged the codebase. Patterns found: missing API limits, doc/code drift, dedup inconsistency. All seams verified clean.
7. **Cross-skill coupling:** sync_backlog imports from bootstrap_github + populate_issues (documented, intentional).

## Test File Locations

- `tests/test_pipeline_scripts.py` — validate_config, TOML parser
- `tests/test_kanban.py` — kanban state machine
- `tests/test_sprint_runtime.py` — sprint_init, check_status
- `tests/test_hooks.py` — hook system (highest churn: 18 changes)
- `tests/test_verify_fixes.py` — regression tests for bug-hunter fixes
- `tests/test_bugfix_regression.py` — earlier regression tests
- `tests/test_release_gate.py` — release gates
- `tests/test_new_scripts.py` — smoke_test, gap_scanner, test_categories, risk_register, etc.

## Key Risk Areas

1. **Broken anchor references** — 21 broken refs, 6 scripts missing anchors. Known doc/code drift.
2. **Hooks relocation** — recent structural change. Verify hooks.json, plugin.json, test mocking paths all consistent.
3. **validate_config.py (1245 LOC)** — hub module. Any subtle bug cascades everywhere.
4. **Two-path state management** — kanban.py vs sync_tracking.py. High churn on both (9 changes each).
5. **Makefile lint incomplete** — ruff not installed, Makefile lint uses py_compile only (no type/style checking). 6 scripts missing from py_compile list in Makefile.
