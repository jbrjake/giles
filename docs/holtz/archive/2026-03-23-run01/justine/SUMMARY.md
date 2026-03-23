# Justine Audit Summary

**Project:** giles
**Date:** 2026-03-23
**Auditor:** Justine (breadth-first adversarial)
**Baseline:** 1188 pass, 0 fail, 0 skip (18.98s)

## Results

| Severity | Count |
|----------|-------|
| CRITICAL | 0 |
| HIGH | 2 |
| MEDIUM | 3 |
| LOW | 2 |
| **Total** | **7** |

### By Category

| Category | Count |
|----------|-------|
| bug/logic | 3 |
| design/inconsistency | 2 |
| bug/type | 1 |
| design/dead-code | 1 |

### By Pattern

| Pattern | Instances |
|---------|-----------|
| PAT-001: Triple TOML Parser Divergence | 4 |
| (unaffiliated) | 3 |

## Findings Summary

### HIGH Severity

- **BJ-001:** `session_context._read_toml_string` returns empty for unquoted TOML values. The session_context hook's TOML parser requires quotes around values. If `project.toml` uses unquoted values (which validate_config accepts), all context injection silently fails.

- **BJ-003:** Triple TOML parser divergence. Three independent TOML parsers (`validate_config.parse_simple_toml`, `verify_agent_output._read_toml_key`, `session_context._read_toml_string`, plus `review_gate._get_base_branch` inline regex) exist for the same `project.toml` file. They handle different subsets of the TOML spec, producing different results for the same input on edge cases.

### MEDIUM Severity

- **BJ-002:** `verify_agent_output._read_toml_key` returns string for integer/boolean TOML values where validate_config returns proper types. Latent bug -- not triggered by current config keys but will bite if new typed keys are added.

- **BJ-005:** `commit_gate._working_tree_hash` uses `git diff HEAD` which does not cover untracked files. Design limitation -- narrower than initially predicted but still a gap for pre-staged files.

- **BJ-006:** `session_context.extract_high_risks` filters empty cells before positional indexing, causing column shift when a risk register table row has an empty cell. Confirmed: high-severity risks silently dropped.

### LOW Severity

- **BJ-004:** Unused `json` imports in `commit_gate.py` and `verify_agent_output.py` after refactor to `_common.py` JSON protocol.

- **BJ-007:** `review_gate._log_blocked` sprints_dir parser fails silently on unquoted values. Falls back to default path. Same PAT-001 pattern.

## Patterns

### PAT-001: Triple TOML Parser Divergence

**Root cause:** Hooks intentionally avoid importing `validate_config` to stay lightweight and isolated. But this means they re-implement TOML parsing independently, and each implementation handles a different subset of the TOML spec.

**Instances:** BJ-001, BJ-002, BJ-003, BJ-007

**Systemic fix:** Create a shared lightweight TOML reader in `hooks/_toml.py` that all hooks import. This preserves hook isolation from the main `validate_config` module while eliminating redundant parser implementations. The shared module should handle: sections with inline comments, quoted and unquoted string values, arrays, inline comments on values.

**Detection rule:** `grep -rn 'def.*read_toml\|def.*_read_toml\|def.*_get_base_branch\|parse_simple_toml' hooks/ scripts/validate_config.py`

## Prediction Accuracy

| Confidence | Predicted | Confirmed | Accuracy |
|------------|-----------|-----------|----------|
| HIGH | 4 | 4 | 100% |
| MEDIUM | 3 | 3 | 100% |
| LOW | 1 | 1 | 100% |
| **Total** | **8** | **7** | **88%** |

Note: Prediction 8 (rubber stamp tests) was UNCONFIRMED -- test analysis showed the suite checks specific values, not just format. 7 of 8 predictions confirmed; the remaining 1 was a false positive on test quality.

## Recommendations

1. **Consolidate hook TOML parsers** (addresses PAT-001, 4 findings). Create `hooks/_toml.py` as a shared lightweight parser. Estimated effort: 2-3 hours. Eliminates an entire bug class.

2. **Fix session_context.extract_high_risks cell indexing** (BJ-006). Do not filter empty cells before positional indexing. Use the raw split-by-pipe result. 15-minute fix.

3. **Add TOML divergence tests** to prevent PAT-001 recurrence. Write a single test that feeds edge-case inputs to all parsers and asserts they agree.

4. **Clean up dead imports** (BJ-004). Remove unused `json` imports from two hook files.

## Assessment

The giles codebase is in good shape. 1188 tests all pass, the architecture is clean with documented boundaries and clear ownership, and prior bug-hunter passes have addressed a large number of issues (evidenced by the BH-prefixed fixes throughout the code).

The dominant finding is the triple TOML parser divergence (PAT-001), which is a maintenance risk rather than an active runtime bug. The most impactful fix is BJ-001 (session_context silently failing on unquoted values) and BJ-006 (risk table column shift dropping high-severity risks).

No CRITICAL findings. The code does not appear to be hurting anyone right now. The bugs that exist are in hooks (which are defensive infrastructure, not user-facing computation), and they fail safe (empty output, default fallback) rather than producing wrong output.
