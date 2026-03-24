# Step 0h: Predictive Recon

**Run:** 6
**Date:** 2026-03-23

## Input Sources

1. Pattern Brief: 4 patterns (PAT-001 through PAT-004), PAT-001 active, others resolved
2. Impact Graph: 32 nodes, 35 edges, no high-risk nodes (highest: hooks/_common.py at 0.4)
3. Git churn: no code changes since run 5 except check_lint_inventory.py
4. Prior runs: 22 findings across 5 runs, all resolved. Only PAT-001 recurred.
5. Global patterns: code-fence-unaware-parsing and regex-newline-leak had heuristic hits
6. Recon observations: 1 new unaudited script, otherwise mature/stable codebase

## Predictions

### Prediction 1
**Target:** `tests/test_check_lint_inventory.py:104-124` (`TestMain.test_main_returns_one_when_missing`)
**Predicted Issue:** test/shallow — test name claims to test `main()` returning 1, but the test body uses `mock.patch` as a no-op and tests the component functions directly instead of `main()`. The error exit path of `main()` is untested.
**Confidence:** HIGH
**Basis:** Code reading during recon. The mock.patch(wraps=None) replaces main() but the test body never calls main(). It manually calls extract_lint_files() and discover_scripts() which are already tested separately.
**Lens:** component
**Graph Support:** check_lint_inventory (risk_score: 0.0, audit_count: 1 — first audit)
**Outcome:** CONFIRMED — BH-001

### Prediction 2
**Target:** `scripts/validate_config.py:865-873` (`extract_sp` — regex on issue body)
**Predicted Issue:** bug/logic — code-fence-unaware parsing. The `re.search` patterns for story points match table-like content (`| SP | 5 |`) in the full issue body without stripping code fences. If an issue body contains a code block with example table rows, the regex could match the wrong number.
**Confidence:** LOW
**Basis:** Global pattern library match (code-fence-unaware-parsing.md). Issue bodies are GitHub markdown and can contain code fences. However, the first match wins (re.search returns first), so if the real SP is in the metadata table before any code fence, it would be correct.
**Lens:** data-flow
**Graph Support:** validate_config (risk_score: 0.2, audit_count: 5)
**Outcome:** UNCONFIRMED — edge case is theoretical, well-defended by match-first semantics

### Prediction 3
**Target:** `skills/sprint-setup/scripts/populate_issues.py:164-174` (milestone table parsing on `content`)
**Predicted Issue:** bug/logic — code-fence-unaware parsing. `row_re.finditer(content)` scans the entire milestone file content for table rows. If a milestone file contained a markdown code fence with example table rows, those would be matched.
**Confidence:** LOW
**Basis:** Global pattern library match (code-fence-unaware-parsing.md). However, milestone files are structured data files (not documentation) — code fences are unlikely.
**Lens:** data-flow
**Graph Support:** populate_issues (risk_score: 0.0, audit_count: 5)
**Outcome:** UNCONFIRMED — milestone files are structured data, code fences unlikely

### Prediction 4
**Target:** `scripts/check_lint_inventory.py:25` (`extract_lint_files` regex)
**Predicted Issue:** bug/logic — the regex `r"py_compile\s+(\S+\.py)"` matches any line containing "py_compile" followed by a .py path, not just lines in the `lint:` target. Comments or other Makefile targets with py_compile would produce false matches.
**Confidence:** MEDIUM
**Basis:** New unaudited code + regex applied to full file content without scope narrowing
**Lens:** component
**Graph Support:** check_lint_inventory (risk_score: 0.0, audit_count: 1 — first audit)
**Outcome:** UNCONFIRMED — current Makefile has py_compile only in lint target
