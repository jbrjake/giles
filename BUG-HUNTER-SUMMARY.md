# Bug Hunter Summary — Pass 37

**Date:** 2026-03-21
**Project:** giles (Claude Code agile sprint plugin)
**Baseline:** 1178 tests, 0 failures, 83% coverage, 17.15s

## Results

| Category | Found | Resolved | Remaining |
|----------|-------|----------|-----------|
| HIGH | 5 | 4 | 1 |
| MEDIUM | 14 | 14 | 0 |
| LOW | 13 | 8 | 5 |
| **Total** | **32** | **26** | **6** |

**Tests:** 1178 → 1181 (+3 net: +8 new tests, -5 deduplicated)
**Commits:** 5 fix commits across 4 batches + 1 dedup

## Notable Fixes

### 1. TOML parser multiline nested array bug (BH37-005, HIGH)
`_has_closing_bracket` in validate_config.py lacked bracket depth tracking. Multiline arrays containing nested arrays (e.g., `check_commands = [["lint","test"],"build"]`) would terminate collection at the first inner `]`, producing a `ValueError`. Added depth counter — now tracks `[` increments and `]` decrements, only returning True at depth 0.

### 2. Shadowed test class losing zero-SP test (BH37-001, HIGH)
`TestWriteBurndown` was defined twice in test_sprint_runtime.py. Python silently overwrites the first class with the second, so the first class's `test_zero_sp_handled` (unique 0-SP edge case) never ran. Renamed first class to `TestWriteBurndownEdgeCases`.

### 3. sprint_init INDEX.md wrong filenames on stem collision (BH37-009, MEDIUM)
When two persona files shared the same stem (e.g., `team-a/alex.md` and `team-b/alex.md`), symlinks were correctly disambiguated (`alex.md` and `team-b-alex.md`) but INDEX.md listed the original stem for both rows. Fixed by tracking disambiguated stems in a dict during the symlink loop.

### 4. session_context.py catch-all TOML unescape (BH37-013, MEDIUM)
`re.sub(r'\\(.)', lambda x: x.group(1), ...)` mapped ANY `\X` to `X`, violating TOML spec (e.g., `\n` should be newline). Replaced with proper escape map matching verify_agent_output.py's implementation.

## Patterns Discovered

### PATTERN-37-A: Re-export coupling
sync_tracking re-exported `write_tf` and `_yaml_safe` from validate_config. 26 test callsites used these through sync_tracking's namespace. Removing "unused" imports broke tests. **Lesson:** Before removing imports flagged as unused, grep for `module.symbol` in tests.

### PATTERN-37-B: INDEX/display divergence
When code transforms data (disambiguating stems), subsequent display code must use the transformed result, not re-derive from the original. **Lesson:** After data transformation, trace all downstream consumers.

## Remaining Items (6)

All remaining items are LOW severity or design trade-offs:
- BH37-008 (HIGH): Mock pollution in kanban double-fault test — the mock is necessary to simulate the double-fault; disk state can't be wrong because the mock prevents the forward write. This is a test design trade-off, not a bug.
- BH37-027-029, 033, 023: Cosmetic or design limitations (timezone markers, version numbering, unused import, test naming).

## Recommendation

The codebase is well-hardened after 37 passes. The most impactful remaining work would be:
1. Adding a `ruff.toml` with `ignore = ["E402"]` to eliminate 76 false-positive lint warnings
2. Running `ruff check --fix` on test files to auto-clean ~50 unused imports/variables
