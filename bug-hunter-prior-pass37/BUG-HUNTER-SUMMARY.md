# Bug Hunter Summary — Pass 37

**Date:** 2026-03-21
**Project:** giles (Claude Code agile sprint plugin)
**Baseline:** 1178 tests, 0 failures, 83% coverage, 17.15s

## Results

| Category | Found | Resolved | Remaining |
|----------|-------|----------|-----------|
| HIGH | 5 | 5 | 0 |
| MEDIUM | 14 | 14 | 0 |
| LOW | 13 | 13 | 0 |
| **Total** | **32** | **32** | **0** |

**Tests:** 1178 → 1182 (+4 net: +9 new tests, -5 deduplicated)
**Commits:** 7 fix commits across 6 batches

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

## Additional Fixes (Batch 5-6)

### 5. Double-fault test with real forward write (BH37-008, HIGH)
Added a complementary test that lets `atomic_write_tf` run for real on the first call (forward write) but fails on the second (rollback). Verifies both that disk retains the forward state ("design") and memory is restored ("todo"). This proves the in-memory recovery code works even when the file is stuck in an intermediate state.

### 6. First release version fix (BH37-028, LOW)
`calculate_version()` now returns the base version (0.1.0) without bumping when no semver tags exist, using bump_type "initial". Previously, the first release was always bumped to at least 0.1.1.

### 7. Smoke test timezone markers (BH37-027, LOW)
`write_history()` now writes timestamps with `Z` suffix (`2026-03-21 14:30Z`) to make UTC explicit. Parser updated to handle both old (no Z) and new (Z) formats via `Z?` in regex.

## Recommendation

The codebase is fully converged after 37 passes with 0 open items. The most impactful next work would be:
1. Adding a `ruff.toml` with `ignore = ["E402"]` to eliminate 76 false-positive lint warnings
2. Running `ruff check --fix` on test files to auto-clean ~50 unused imports/variables
