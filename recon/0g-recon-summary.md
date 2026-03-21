# Recon Summary — Pass 36

**Baseline:** 1178 tests, all passing, 17.43s. Pass 35 modified 10 files.
**Focus:** Verify pass 35 fixes, search for siblings, convergence check.

## Audit Targets

### 1. assign_dod_level.py still uses lock_story (BH35-001 sibling)
- `scripts/assign_dod_level.py:50` — uses `lock_story` when writing tracking files
- kanban.py main() now uses `lock_sprint` for all mutations
- Same race condition class as BH35-001: assign_dod_level vs sync_tracking

### 2. traceability.py STORY_HEADING uses \s* (BH35-015 sibling)
- `scripts/traceability.py:23` — `\s*` after colon, like the old manage_epics pattern
- populate_issues uses `\s+` — same inconsistency

### 3. sprint_init.py unescaped TOML values (BH35-024 siblings)
- Lines 651, 653: cheatsheet and architecture values not passed through `_esc()`
- All other user-derived values use `esc()` correctly

### 4. lock_story now only used by assign_dod_level.py
- kanban.py defines it but no longer calls it from main()
- The docstring at kanban.py:331 references lock_story as caller requirement
- sync_tracking.py:15 has a stale comment saying it uses lock_story (it uses lock_sprint)

### 5. review_gate ALL-positionals false positive
- Remote named same as base branch (e.g., "main") would cause false block
- LOW severity — false blocks are safe, and remotes named "main" are extremely rare
