# 0g: Recon Summary (Run 2)

## Key Findings

### Run 1 Fixes: Solid
All 10 run 1 fixes are correctly implemented. The unquoted value handling in session_context (BJ-001), column index fix in extract_high_risks (BJ-006), compound command splitting in commit_gate (BH-005), and crash-before-block in review_gate (BH-006) all pass testing with edge cases.

### TOML Parser Divergence (PAT-003): Partially Resolved
Run 1 addressed the most acute symptom (unquoted values) across all three hook parsers. Remaining divergence:
- Boolean values: validate_config returns Python `True`/`False`, hooks return strings `"true"`/`"false"`. Latent -- no current boolean keys used by hooks.
- Array values: session_context._read_toml_string returns empty string for arrays. By design -- it's a string-only parser.
- The systemic recommendation (consolidate to shared parser) remains open as BH-009 on Holtz's punchlist.

### Bidirectional Dependency: Acceptable
commit_gate and verify_agent_output have deferred (function-level) imports of each other. Both are wrapped in try/except with graceful degradation. Python module caching handles the circularity correctly. Not a bug.

### New Edge Cases from Run 1 Fixes: One Finding
The BJ-001 fix in session_context uses `\S+` regex for unquoted values, which stops at the first space. This means unquoted values containing spaces would be silently truncated. In practice, TOML values with spaces should be quoted, so this matches TOML spec behavior. Not a bug, but the truncation is silent.

### format_context Line Count: Test Weakness
The test for format_context's "<50 lines target" uses exactly 40 items (producing 47 lines). With 100 items, output is 107 lines. The function does not truncate. The test is borderline rubber stamp -- it validates the claim only for the specific test input, not the general contract. However, the docstring says "target" not "guarantee."

## Risk Assessment

The hooks subsystem is in good shape after run 1. The remaining issues are:
1. BH-009 (TOML consolidation) -- design debt, not a runtime bug
2. format_context unbounded output -- LOW, cosmetic at worst
3. Compound command splitting doesn't respect shell quoting -- LOW, fails safe (blocks, never allows)
