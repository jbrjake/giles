# Recon Summary — Pass 37

**Baseline:** 1178 tests, all passing, 17.15s. 83% coverage (5305 stmts, 916 missed).
**No code changes since pass 36** (HEAD = 356cef1). Clean-slate full audit.

## Critical Finding

**Duplicate test class `TestWriteBurndown`** in `tests/test_sprint_runtime.py` — defined at both line ~1546 and ~2365. Python silently overwrites the first with the second, so the first class's tests never run. This is a real coverage gap.

## Audit Priorities

### 1. Shadowed test class (HIGH)
- `TestWriteBurndown` duplicate → unknown number of tests silently lost
- Need to check what the first class tested vs the second

### 2. Low-coverage production files
- `assign_dod_level.py` — 35% coverage (worst in project)
- `smoke_test.py` — 57%
- `sprint_analytics.py` — 63%
- `test_categories.py` — 64%
- `history_to_checklist.py` — 65%
- `gap_scanner.py` — 67%
- `commit.py` — 68%

### 3. High-churn files (bug magnets)
- `validate_config.py` — 23 fix-commit touches, 57 total
- `kanban.py` — 13-14 fix touches, 27 total
- `sync_tracking.py` — 7-14 fix touches, 43 total
- Hooks subsystem (review_gate, commit_gate, session_context, verify_agent_output) — 6-10 each

### 4. Lint issues worth fixing
- 6 unused imports in production scripts
- Dead f-prefix in release_gate.py:547
- ~50 unused imports/vars in test files (auto-fixable)

### 5. Test assertion quality
- After 36 passes of fixes, tests may have been weakened to make them pass
- Need adversarial check: are assertions testing real behavior or just structure?

## Not Bugs
- 76 E402 violations — all from sys.path.insert pattern (by design)
- `self.skipTest()` in test_golden_run.py — intentional golden-file handling
- Zero skipped/disabled tests otherwise
