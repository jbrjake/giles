# Bug Hunter Summary — Pass 38

**Date:** 2026-03-21
**Project:** giles (Claude Code agile sprint plugin)
**Baseline:** 1182 tests, 0 failures, 83% coverage, 16.9s

## Results

| Category | Found | Resolved | Closed | Remaining |
|----------|-------|----------|--------|-----------|
| HIGH | 2 | 2 | 0 | 0 |
| MEDIUM | 11 | 8 | 3 | 0 |
| LOW | 13 | 5 | 8 | 0 |
| **Total** | **26** | **15** | **11** | **0** |

**Tests:** 1182 → 1184 (+2 new: lock cleanup verification, smoke error path)
**Lint:** 0 → 0 (stayed clean)

## Notable Fixes

### 1. commit_gate false-positive command verification (BH38-201, MEDIUM)
`_matches_check_command` only matched the first word of configured check commands. If `check_commands = ["python -m pytest"]`, any `python ...` invocation (even `python some_script.py`) would satisfy the gate, allowing untested commits. Fixed to match all command tokens in sequence.

### 2. kanban.py sync fails on first run (BH38-200, MEDIUM)
`kanban.py sync` called `lock_sprint(sprint_dir)` before the sprint directory existed. `lock_sprint` tries to `touch()` a lock file inside the directory, raising `FileNotFoundError`. Added `mkdir(parents=True, exist_ok=True)` before lock acquisition, matching how `sync_tracking.py` handles it.

### 3. Tautological assertion (BH38-100, HIGH)
`assertTrue(len(output) >= 0)` — `len()` can never return negative, so this always passed regardless of output. Replaced with `assertIsInstance(output, str)` which actually validates the return type.

### 4. sync_backlog "lazy imports" lie (BH38-006, HIGH)
Both the `do_sync()` docstring and CHEATSHEET claimed imports were lazy, but they happen at module level in a try/except (lines 27-35). Fixed docstring to accurately describe module-level import with graceful fallback.

### 5. sync_tracking implicit case assumption (BH38-205, MEDIUM)
Dict keys were built with `.upper()` but lookups used raw `sid` without `.upper()`. Worked only because `extract_story_id()` always returns uppercase. Added explicit `.upper()` to all lookups for defensive consistency.

### 6. session_context separator filter (BH38-206, MEDIUM)
Markdown table separator rows with alignment markers (`:---`, `---:`, `:---:`) were not filtered, causing them to appear as action items in session context. Added regex check for all separator variants.

## Patterns Discovered

### PATTERN-38-A: Doc/code semantic drift
3 items where documentation described historical behavior that code had since evolved. The code was correct; the docs were stale. **Lesson:** When modifying code behavior, grep docs for descriptions of the old behavior.

### PATTERN-38-B: First-token command matching
Matching commands by their first word (`python` from `python -m pytest`) loses specificity. **Lesson:** Preserve full command structure when matching — binary name alone is insufficient.

## Recommendation

The codebase is fully converged after 38 passes with 0 open items. Test count is up (+2) and lint stays clean. The remaining closed items are either architectural (os.chdir coupling, mock density) or extremely unlikely edge cases (triple stem collision, concurrent tracking writes). The most impactful next work would be adding type checking (mypy/pyright) — currently no type checker is configured, so type-level bugs are invisible to static analysis.
