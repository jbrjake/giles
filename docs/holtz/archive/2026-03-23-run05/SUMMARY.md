# Holtz Audit Summary (Run 5 — Full Fresh)

**Date:** 2026-03-23
**Project:** giles (Claude Code agile sprint plugin)
**Mode:** Full fresh audit (runs 1-4 archived, all 8 lenses applied)
**Baseline:** 1224 tests, 0 failures, lint clean, 17.37s
**Final:** 1224 tests, 0 failures, lint clean, 17.11s

## Results

| Severity | Found | Resolved | Deferred |
|----------|-------|----------|----------|
| CRITICAL | 0 | 0 | 0 |
| HIGH | 0 | 0 | 0 |
| MEDIUM | 1 | 1 | 0 |
| LOW | 1 | 1 | 0 |
| **Total** | **2** | **2** | **0** |

**Tests:** 1224 (unchanged — fixes were Makefile and docs)
**Lint:** clean (with 5 new hook entries in Makefile lint)
**Convergence:** 1 iteration

## Fixes

### BH-001: Makefile lint target missing 5 hook scripts (MEDIUM)
The hooks subsystem (`hooks/_common.py`, `hooks/commit_gate.py`, `hooks/review_gate.py`, `hooks/session_context.py`, `hooks/verify_agent_output.py`) was moved to the plugin root in commit `2dc773d` but the Makefile `lint` target was not updated. Added all 5 hook scripts to the py_compile lint target. This is a PAT-001 instance (batch addition without full wiring) — the same pattern that affected 6 scripts in run 1.

### BH-002: Architecture baseline invariant overly absolute (LOW)
The architecture baseline claimed "All `gh` CLI calls go through wrappers" but `populate_issues.check_prerequisites()` calls `gh auth status` directly (pre-config auth check). Qualified the invariant to document the exception.

## Prediction Accuracy

| Confidence | Predicted | Confirmed | Accuracy |
|------------|-----------|-----------|----------|
| HIGH | 2 | 0 | 0% |
| MEDIUM | 5 | 0 | 0% |
| LOW | 1 | 0 | 0% |
| **Total** | **8** | **0** | **0%** |

0% accuracy is expected for a codebase that has been through 4 prior converged Holtz audits + 39 bug-hunter passes. The predicted areas (regex on body content, TOML parsing, CI output parsing, state machine semantics, temporal ordering) were all well-defended by prior fixes. The two actual findings were in areas no prediction targeted: Makefile wiring (infrastructure) and architecture baseline text (documentation).

## Assessment

This codebase is mature. Five Holtz runs (22 findings total, all resolved) and 39 bug-hunter passes have addressed every major bug class: TOML parser divergence (runs 1-3), security hardening (run 1), state machine semantics (run 4), and now infrastructure wiring (run 5). The test suite is thorough (1224 tests, 1.8:1 test-to-production LOC ratio), all high-churn subsystems have been hardened, and the architecture is well-documented.

The only recurring pattern across runs is PAT-001 (batch addition without full wiring), which has produced 4 instances across 2 runs. A CI check that validates the Makefile lint list against the actual script inventory would prevent future instances. This was recommended in run 1 and remains the only tactical recommendation.

## Recommendation

**Tactical:** Add a CI check (or Makefile target) that verifies the lint py_compile list matches the actual inventory of production Python scripts. This would catch PAT-001 instances (like the hooks gap) automatically. Something like:

```bash
# Count production .py files (excluding __init__.py, tests, venv)
expected=$(find scripts/ hooks/ skills/*/scripts/ -name "*.py" ! -name "__init__.py" | wc -l)
actual=$(grep -c "py_compile" Makefile)
[ "$expected" -eq "$actual" ] || echo "MISMATCH: $expected scripts, $actual in Makefile"
```

**Strategic:** The codebase is converged and well-defended. No new strategic recommendations.
