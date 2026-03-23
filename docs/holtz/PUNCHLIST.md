# Holtz Punchlist
> Generated: 2026-03-23 | Project: giles | Baseline: 1224 pass, 0 fail, 0 skip

## Summary
| Severity | Open | Resolved | Deferred |
|----------|------|----------|----------|
| CRITICAL | 0 | 0 | 0 |
| HIGH | 0 | 0 | 0 |
| MEDIUM | 0 | 1 | 0 |
| LOW | 0 | 1 | 0 |
| **Total** | **0** | **2** | **0** |

## Patterns

(none new — BH-001 is PAT-001 instance from run 1)

## Items

### BH-001: Makefile lint target missing 5 hook scripts
**Severity:** MEDIUM
**Category:** design/inconsistency
**Location:** `Makefile:29-56`
**Status:** RESOLVED
**Pattern:** PAT-001 (batch addition without full wiring)
**Lens:** component

**Problem:** The Makefile `lint` target py_compiles 25 of 31 production Python files. The 5 hook scripts (`hooks/_common.py`, `hooks/commit_gate.py`, `hooks/review_gate.py`, `hooks/session_context.py`, `hooks/verify_agent_output.py`) are missing. These were moved to the plugin root in commit `2dc773d` but the Makefile was not updated.

**Evidence:** `grep "py_compile" Makefile | wc -l` = 26 (before fix). `ls hooks/*.py | wc -l` = 6 (includes empty __init__.py). 5 non-empty hook files missing from lint.

**Discovery Chain:** Makefile lint entry count (26) < total production scripts (32) → 6 missing → hooks dir not present in Makefile → PAT-001 instance

**Acceptance Criteria:**
- [x] All 5 hook scripts appear in `make lint`
- [x] `make lint` passes with the new entries

**Validation Command:**
```bash
grep -c "hooks/" Makefile
```

**Resolution:** Added 5 py_compile entries for hooks/_common.py, hooks/commit_gate.py, hooks/review_gate.py, hooks/session_context.py, hooks/verify_agent_output.py to Makefile lint target. All compile successfully. 1224 tests still passing.

### BH-002: Architecture baseline invariant overly absolute about gh wrappers
**Severity:** LOW
**Category:** doc/drift
**Location:** `docs/holtz/architecture-baseline.md:40`
**Status:** RESOLVED
**Lens:** contract

**Problem:** Architecture baseline invariant stated "All `gh` CLI calls go through `validate_config.gh()` or `validate_config.gh_json()` wrappers." However, `populate_issues.check_prerequisites()` calls `subprocess.run(["gh", "auth", "status"])` directly. This is an auth check that runs before config is loaded.

**Evidence:** `grep -rn "subprocess.run.*gh" skills/ scripts/ hooks/` finds one hit at populate_issues.py:39.

**Discovery Chain:** Architecture baseline invariant "all gh calls use wrappers" → grep finds subprocess.run(["gh"]) in populate_issues.py:39 → invariant is overly absolute

**Acceptance Criteria:**
- [x] The invariant is qualified to document the exception
- [x] The exception is explained (pre-config auth check)

**Validation Command:**
```bash
grep "exception" docs/holtz/architecture-baseline.md
```

**Resolution:** Qualified the invariant to "All data/mutation `gh` CLI calls" with a parenthetical documenting the populate_issues.check_prerequisites() exception.
