# 0g: Recon Summary

## Project State
- 1205 tests all passing, 0 failures, 0 skips
- Python 3.10+, stdlib-only runtime, dev deps for tests
- Clean git, main branch, 2 prior Holtz audit runs archived

## Architecture
- validate_config.py is the hub (imported by 20+ scripts)
- Two-path state management: kanban.py (local-first mutations) + sync_tracking.py (GitHub reconciliation)
- Hooks are independently wired subsystem with own TOML parser in _common.py
- Cross-skill import: sync_backlog -> sprint-setup scripts

## Key Risk Areas
1. **Dual TOML parser divergence (CONFIRMED):** _common.py's `_unescape_basic_string` handles 5 escape sequences. validate_config.py's `_unescape_toml_string` handles 9 (adds \b, \f, \uXXXX, \UXXXXXXXX). Any project.toml value using the extended escapes will be parsed differently by hooks vs scripts.

2. **Property tests check type but not always value:** Some hypothesis tests use `isinstance(result, str)` and `len(result) > 0` without checking correctness. These are structural assertions -- they confirm the function returns a string but not that it returns the RIGHT string. For property tests this is sometimes acceptable (crash-testing) but the pattern should be identified.

3. **Test file anti-patterns:** Several `assertIsNotNone` assertions in test_hexwise_setup.py and test_pipeline_scripts.py check existence but not correctness. These are rubber stamp candidates.

4. **No code coverage measurement:** The project has extensive tests but no coverage tool configured, so gaps are invisible.

## What Holtz Already Found (read-only)
Previous runs addressed: bidirectional hook imports, TOML parser consolidation in hooks, architecture baseline drift. The dual-parser between _common.py and validate_config.py was partially addressed (hooks consolidated to _common.py's reader) but the escape sequence divergence remains.
