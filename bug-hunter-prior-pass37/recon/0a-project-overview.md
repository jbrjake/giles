# BH37 — Project Overview

## What this is

Claude Code plugin that runs agile sprints with persona-based development. Orchestrates GitHub issues, PRs, CI, kanban tracking, and sprint ceremonies via fictional team personas. 5 skills, ~25 Python scripts, all stdlib-only.

## State since last audit (pass 36, commit 356cef1)

No code changes since pass 36. HEAD is 356cef1. The only delta is deleted recon/audit artifacts from prior passes. This means pass 37 is a fresh-eyes audit of the full codebase as it stands after 36 passes of fixes.

## Pass 36 fixes (the most recent code changes)

| ID | File | Fix |
|----|------|-----|
| BH36-001 | `scripts/assign_dod_level.py` | Switched from `lock_story` to `lock_sprint` for consistency with kanban.py/sync_tracking.py |
| BH36-002 | `scripts/sprint_init.py` | Added `esc()` for TOML-safe quoting on cheatsheet/architecture paths |
| BH36-003 | `scripts/traceability.py` | `STORY_HEADING` regex: `\s*` to `\s+` for required space after colon |
| (doc) | `scripts/kanban.py`, `sync_tracking.py` | Updated docstrings re: lock_sprint vs lock_story |

## Hottest files (modification count across passes 27-36)

These files have been touched most heavily by bug-hunter fixes and are the most likely to have accumulated regression or inconsistency:

| Touches | File | Risk |
|---------|------|------|
| 57 | `scripts/validate_config.py` | Central shared library. Every script imports it. Regex, TOML parser, helpers. |
| 43 | `skills/sprint-run/scripts/sync_tracking.py` | Locking rework (lock_story -> lock_sprint), TOCTOU fixes, PR linkage. |
| 35 | `skills/sprint-setup/scripts/populate_issues.py` | Story parsing, milestone mapping, regex alignment. |
| 31 | `skills/sprint-monitor/scripts/check_status.py` | Compound commands, smoke checks, integration debt. |
| 30 | `skills/sprint-release/scripts/release_gate.py` | Version calc, gate logic, exception handling. |
| 27 | `scripts/kanban.py` | State machine, locking, transition log, WIP limits. |
| 27 | `scripts/sprint_init.py` | Scanner, config generation, TOML escaping. |
| 25 | `scripts/manage_epics.py` | Story CRUD, renumbering, section parsing. |

## Areas most likely to harbor bugs

1. **Locking consistency** — Multiple passes rewired lock_story to lock_sprint. Any script that still uses lock_story for writes (or fails to lock at all) is a concurrency bug. Check: assign_dod_level, kanban.py, sync_tracking.py, any other write path.

2. **Regex alignment across scripts** — Story ID patterns, table row patterns, and heading patterns have been individually patched across traceability.py, populate_issues.py, manage_epics.py, and validate_config.py. Drift between them means silent parse failures.

3. **TOML parser edge cases** — The custom `parse_simple_toml()` has had multiple fixes (backslash escapes, comment handling, unescape). It's the most likely place for a parsing bug that silently corrupts config values.

4. **Hooks subsystem** — `.claude-plugin/hooks/` scripts (commit_gate, review_gate, verify_agent_output, session_context) have been heavily patched. They have their own lightweight TOML parser and path resolution logic separate from validate_config.py.

5. **Test quality** — 40+ test file touches suggest tests were patched to match code changes. Tests that were weakened to pass (assertion relaxation, mock broadening) may no longer catch real regressions.

6. **Cross-script import chain** — Scripts in `skills/*/scripts/` do `sys.path.insert(0, ...)` to reach shared code. Any refactor that moved or renamed functions in validate_config.py could break downstream imports that haven't been updated.
