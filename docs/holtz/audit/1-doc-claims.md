# Phase 1: Doc-to-Implementation Claims

**Run:** 6
**Date:** 2026-03-23

## Predicted Areas (checked first)

### Claim 1: check_lint_inventory.py exits non-zero when scripts are missing (Prediction 1 target)
**Source:** Docstring line 6: "Exits non-zero if any script is missing from the lint target."
**Test:** `test_main_returns_one_when_missing` (test_check_lint_inventory.py:104)
**Result:** FAIL — test does NOT actually call `main()`. Uses `mock.patch.object(check_lint_inventory, "main", wraps=None)` which replaces main with a mock, then never calls it. The test body manually calls `extract_lint_files()` and `discover_scripts()` and asserts on the `missing` set — which is already tested by `TestDiscoverScripts`. The error exit path of `main()` (lines 65-78 of source) is untested.
**Punchlist:** BH-001

### Claim 2: extract_lint_files matches only py_compile entries (Prediction 4 target)
**Source:** Function docstring: "Extract file paths from py_compile lines"
**Test:** `test_ignores_non_py_compile_lines` (test_check_lint_inventory.py:29)
**Result:** PASS — the regex `r"py_compile\s+(\S+\.py)"` correctly ignores non-py_compile lines. Current Makefile has py_compile only in the lint target.
**Prediction 4:** UNCONFIRMED

### Claim 3: code-fence-unaware parsing in extract_sp (Prediction 2 target)
**Source:** validate_config.py:865-875
**Test:** Multiple tests across test_property_parsing.py and test_verify_fixes.py
**Result:** LOW RISK — extract_sp operates on GitHub issue bodies. These are structured data (metadata tables, user stories). Code fences with fake SP tables are theoretically possible but extremely unlikely in practice. The first match wins, and the real SP is always at the top of the body.
**Prediction 2:** UNCONFIRMED

### Claim 4: code-fence-unaware parsing in milestone parsing (Prediction 3 target)
**Source:** populate_issues.py:164-174
**Test:** Multiple integration tests
**Result:** LOW RISK — milestone files are structured data files in sprint-config/, not user-authored documentation. Code fences are not expected.
**Prediction 3:** UNCONFIRMED

## CLAUDE.md Claims (spot-checked)

### Claim 5: check_lint_inventory documented in script table
**Source:** CLAUDE.md line 72
**Result:** PASS — correctly lists extract_lint_files, discover_scripts, main with anchors

### Claim 6: 32 production scripts
**Source:** Makefile lint target has 32 py_compile lines
**Result:** PASS — confirmed by lint output
