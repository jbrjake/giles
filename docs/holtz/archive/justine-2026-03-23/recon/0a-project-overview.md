# 0a: Project Overview

**Project:** giles -- Claude Code plugin for agile sprints with persona-based development
**Language:** Python 3.10+ (stdlib-only at runtime, dev deps for tests)
**Framework:** No web framework. CLI scripts orchestrated by Claude Code skills.
**Test Framework:** pytest + unittest + hypothesis (property-based)
**Lines of Code:** ~25 production scripts, ~18 test files, 1205 tests all passing

## Architecture Summary

- **Foundation layer:** `validate_config.py` (1248 LOC) -- TOML parser, config validation, all shared helpers
- **State management:** `kanban.py` (mutations, local-first) + `sync_tracking.py` (reconciliation, GitHub-first)
- **Hooks subsystem:** 4 hooks (_common.py base) -- commit gate, review gate, session context, verify agent output
- **Skills:** 5 skill entry points (SKILL.md) backed by scripts in `skills/*/scripts/`
- **Cross-skill coupling:** sync_backlog.py imports from sprint-setup scripts

## Key Seams Identified

1. **Dual TOML parsers:** `_common.py:read_toml_key` (hooks) vs `validate_config.py:parse_simple_toml` (scripts). Different implementations, different escape handling.
2. **Two-path state management:** kanban.py validates transitions, sync_tracking.py accepts any state. Different authority models converging on the same files.
3. **Cross-skill imports:** sync_backlog imports bootstrap_github + populate_issues from a different skill.
4. **sys.path manipulation:** Every script does sys.path.insert. conftest.py centralizes for tests but production scripts each wire their own.
