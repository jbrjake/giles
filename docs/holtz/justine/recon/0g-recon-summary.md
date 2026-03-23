# 0g: Recon Summary

**Project:** giles (Claude Code plugin for agile sprints)
**Language:** Python 3.10+ (stdlib-only runtime)
**Test suite:** 1188 passed, 0 failed, 0 skipped (18.98s)
**Lint:** 2 unused imports in hooks (F401)

## Architecture Risk Map

### Critical Seams (Integration Audit Priority)

1. **Triple TOML Parser Divergence** -- THREE independent TOML parsers exist for the same `project.toml`:
   - `validate_config.parse_simple_toml()` -- full parser with escape handling, arrays, sections
   - `hooks/verify_agent_output._read_toml_key()` -- minimal key extractor, independent escape logic
   - `hooks/session_context._read_toml_string()` -- minimal string extractor, yet another escape impl
   - `hooks/review_gate._get_base_branch()` -- inline regex, simplest parser
   This DIRECTLY matches the "dual-parser-divergence" global pattern. With THREE parsers, divergence risk is tripled.

2. **Dual State Mutation Paths** -- kanban.py and sync_tracking.py both write to the same tracking files. Lock coordination via lock_sprint exists but the acceptance rules differ (kanban validates transitions, sync_tracking accepts any valid state).

3. **Hook Isolation vs. Config Access** -- Hooks intentionally do NOT import from validate_config to stay lightweight, but this means they re-implement TOML parsing with less coverage.

### High-Churn Areas

- `hooks/` (10-18 changes per file in 50 commits) -- recently refactored from .claude-plugin/hooks/
- `kanban.py` + `sync_tracking.py` (9 changes each)
- `test_hooks.py` (18 changes)

### Pattern Library Matches

- **dual-parser-divergence**: CONFIRMED match -- three parsers for project.toml
- **incomplete-layer-isolation**: CONFIRMED match -- validate_config provides parse_simple_toml but hooks bypass it with independent mini-parsers
- **missing-edge-case-handling**: Potential -- hooks parsers handle fewer edge cases than validate_config

### Test Risk Signals

- 1188 tests all pass -- need to check for rubber stamps (format-not-value checks)
- Heavy regression focus (test_verify_fixes.py at 124K, test_bugfix_regression.py at 65K) -- many tests were written to confirm prior fixes, not to test behavior
- Test suite is entirely offline (FakeGitHub mock) -- integration with real gh CLI untested
