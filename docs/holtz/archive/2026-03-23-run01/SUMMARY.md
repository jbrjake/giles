# Holtz Audit Summary

**Date:** 2026-03-23
**Project:** giles (Claude Code agile sprint plugin)
**Baseline:** 1188 tests, 0 failures, lint with 21 false broken refs, 19.37s
**Final:** 1193 tests, 0 failures, lint fully clean, 16.65s

## Results

| Severity | Found | Resolved | Deferred |
|----------|-------|----------|----------|
| CRITICAL | 0 | 0 | 0 |
| HIGH | 3 | 3 | 0 |
| MEDIUM | 6 | 6 | 0 |
| LOW | 2 | 1 | 1 |
| **Total** | **11** (+ 1 false positive rejected) | **10** | **1** |

**Tests:** 1188 → 1193 (+5 new)
**Lint:** 21 broken refs → 0

## Adversarial Self-Play

Holtz found 8 items; Justine found 7 items independently. After merge:
- **Agreements:** 2 (hooks doc gap, batch wiring — found by both)
- **Holtz-only:** 4 (compound bypass, crash-before-block, find_milestone, post_main string)
- **Justine-only:** 3 (unquoted TOML in session_context, column shift in extract_high_risks, dead imports)
- **False positives rejected:** 1 (VC-001: write_tf atomicity — all production callers use atomic wrapper)

## Notable Fixes

### 1. commit_gate compound command bypass (BH-005, HIGH)
`check_commit_allowed` checked `--dry-run` against the entire command string without splitting. `git stash --dry-run; git commit -m evil` bypassed the gate. Added compound command splitting matching review_gate. 5 new tests.

### 2. NAMESPACE_MAP missing 6 scripts (BH-001, HIGH)
validate_anchors.py's NAMESPACE_MAP had no entries for 6 scripts, causing 21 false broken refs. Added all 6.

### 3. session_context unquoted TOML values (BJ-001, HIGH — Justine)
`_read_toml_string` only handled quoted values. Unquoted values like `sprints_dir = sprints` returned empty string, silently disabling all context injection. Added unquoted value parsing.

### 4. Makefile lint missing 7 scripts (BH-002, MEDIUM)
py_compile checked 19/26 scripts. kanban.py (815 LOC) was among the 7 missing. Added all 7.

### 5. CLAUDE.md missing hooks documentation (BH-003, MEDIUM)
Hooks subsystem undocumented after refactor. Added complete hooks section to Plugin Structure.

### 6. review_gate crash-before-block (BH-006, MEDIUM)
`_log_blocked()` could raise OSError before `exit_block()`. Wrapped in try/except.

### 7. find_milestone missing state=all (BH-007, MEDIUM)
GitHub API defaults to open milestones only. Closed milestones invisible. Added `state=all`.

### 8. post_main string tool_output crash (BH-008, MEDIUM)
`tool_output.get()` assumed dict. Added isinstance guard.

### 9. extract_high_risks column shift (BJ-006, MEDIUM — Justine)
`cells = [c for c in cells if c]` filtered empty cells, shifting column positions. Empty title cell caused severity to be read from status column. Fixed to preserve positional indexing.

### 10. Dead json imports removed (BJ-004, LOW — Justine)
Unused `import json` in commit_gate.py and verify_agent_output.py. All JSON handling is in _common.py.

## False Positive Rejected

**VC-001:** Subagent flagged `write_tf()` as non-atomic. All production callers use `atomic_write_tf()` wrapper — only test setup calls `write_tf()` directly.

## Patterns Discovered

### PAT-001: Batch addition without full wiring
BH-001, BH-002, BH-004 all stem from 6 scripts added without updating all integration points (NAMESPACE_MAP, Makefile, tests). **Lesson:** New script checklist: NAMESPACE_MAP, Makefile lint, CHEATSHEET.md, test coverage.

### PAT-002: Inconsistent security hardening across parallel hooks
BH-005, BH-006 show commit_gate missing protections that review_gate had (compound splitting, crash safety). **Lesson:** When hardening one hook, audit all sibling hooks for the same class.

### PAT-003: Triple TOML parser divergence (Justine)
Three independent TOML parsers in the codebase: `validate_config.parse_simple_toml()` (full featured), `session_context._read_toml_string()` (quotes only), `verify_agent_output._read_toml_key()` (basic). Each handles a different subset of TOML syntax. **Lesson:** Hooks should import shared parsing from `_common.py` or delegate to validate_config.

## Prediction Accuracy

### Holtz Predictions
| Confidence | Predicted | Confirmed | Accuracy |
|------------|-----------|-----------|----------|
| HIGH | 2 | 2 | 100% |
| MEDIUM | 5 | 3 | 60% |
| LOW | 1 | 0 | 0% |
| **Total** | **8** | **5** | **63%** |

### Justine Predictions
| Confidence | Predicted | Confirmed | Accuracy |
|------------|-----------|-----------|----------|
| HIGH | 3 | 3 | 100% |
| MEDIUM | 3 | 3 | 100% |
| LOW | 2 | 1 | 50% |
| **Total** | **8** | **7** | **88%** |

## Recommendation

The codebase remains strong after 39 prior bug-hunter passes + this Holtz audit. Issues clustered in two areas: (1) batch-added scripts missing wiring points, (2) hooks subsystem with inconsistent hardening and divergent TOML parsers.

**Tactical:** Consider unifying the hooks' TOML reading into `_common.py`. Consider a CI check that validates the Makefile lint list matches actual script inventory.

**Strategic:** The hooks are the newest and least-tested subsystem. Future audits should weight hooks more heavily since they have the most moving parts and the highest security surface.
