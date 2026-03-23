# 0a: Project Overview

**Project:** giles — Claude Code plugin for agile sprints with persona-based development
**Language:** Python 3.10+ (stdlib-only at runtime)
**Size:** 31 production scripts (~11,400 LOC), 19 test files (~21,000 LOC)
**Test framework:** pytest + hypothesis
**Baseline:** 1224 tests passing, 0 failures, 0 skips (excl. 1 conditional skipTest in golden_run)

## Architecture

- **Foundation layer:** `validate_config.py` (1247 LOC) — TOML parser, config loading, shared helpers
- **Business logic:** `kanban.py` (826 LOC), `sprint_init.py` (1027 LOC), `manage_epics.py`, `manage_sagas.py`, etc.
- **Skill scripts:** setup (bootstrap_github, populate_issues, setup_ci), run (sync_tracking, update_burndown), monitor (check_status), release (release_gate)
- **Hooks:** independent subsystem — `_common.py` + 4 hooks (commit_gate, review_gate, session_context, verify_agent_output)
- **Two-path state management:** kanban.py (mutation, local-first) vs sync_tracking.py (reconciliation, GitHub-first)
- **Cross-skill coupling:** sync_backlog imports from sprint-setup scripts (documented, intentional)

## High-Churn Files (last 50 commits)

1. test_hooks.py (13 changes)
2. test_verify_fixes.py (9 changes)
3. kanban.py (7 changes)
4. commit_gate.py in hooks (7 changes)
5. sync_tracking.py (6 changes)
6. kanban-protocol.md (6 changes)
7. review_gate.py (6 changes)
8. session_context.py (5 changes)
9. check_status.py (5 changes)
10. sprint_init.py (5 changes)

## Prior Audit History

- **Run 1:** 11 findings (3 HIGH, 6 MEDIUM, 2 LOW) — compound bypass, TOML parser gaps, missing lint entries
- **Run 2:** 2 findings (2 MEDIUM) — TOML consolidation, unquoted base_branch
- **Run 3:** 5 findings (3 MEDIUM, 2 LOW) — TOML escape alignment, pipe splitting, rubber stamps
- **Run 4 (targeted):** 4 findings (4 LOW) — custom lenses found semantic-fidelity/temporal-protocol issues
- **Total resolved across runs:** 22 findings

## Pattern History

- PAT-001: Batch addition without full wiring (3 instances)
- PAT-002: Inconsistent security hardening across parallel hooks (2 instances)
- PAT-003: Triple TOML parser divergence (resolved in run 2)
- PAT-004: Dual parser divergence hooks vs scripts (resolved in run 3)

## Lint Status

- validate_anchors.py: 0 broken refs (19 defined-but-unreferenced, info level)
- Makefile lint: py_compile on all scripts

## Architecture Drift

- No new drift detected. Baseline from run 1 remains accurate. Run 2 resolved bidirectional hook imports. Run 3 corrected 3 baseline omissions.
