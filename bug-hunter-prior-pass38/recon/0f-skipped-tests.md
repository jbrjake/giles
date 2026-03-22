# Phase 0f: Skipped, Disabled, and xfail Tests

**Date:** 2026-03-21
**Scope:** `tests/` directory (18 test files + 1 helper module)

## Summary

| Category | Count |
|----------|-------|
| `@pytest.mark.skip` / `@pytest.mark.skipIf` | 0 |
| `@pytest.mark.xfail` | 0 |
| `@unittest.skip` / `@unittest.expectedFailure` | 0 |
| `pytest.skip()` calls | 0 |
| `pytest.importorskip()` | 0 |
| `self.skipTest()` (runtime conditional) | 1 |
| Commented-out test functions (`# def test_`) | 0 |
| Pass-only test functions | 0 |
| **Total test functions** | **1213** |

## Details

### Runtime Conditional Skip (1)

**`tests/test_golden_run.py:116`** — `self.skipTest()` inside `_check_or_record()` helper

This is a conditional skip, not a blanket decorator. It fires only when:
- Golden recordings are absent on disk, AND
- The test is NOT running in CI (in CI, it calls `self.fail()` instead)

Purpose: graceful degradation for local dev when golden recordings haven't been generated yet. The skip message instructs the developer to run `GOLDEN_RECORD=1` to create them.

**Verdict:** Intentional and well-documented (BH-P11-051). Not a hidden gap.

### Decorator-based Skips and xfail

None found. No uses of:
- `@pytest.mark.skip`
- `@pytest.mark.skipIf`
- `@pytest.mark.xfail`
- `@unittest.skip`
- `@unittest.expectedFailure`
- `pytest.importorskip()`

### Commented-out Tests

None found. No occurrences of `# def test_` or `#def test_` patterns.

### Pass-only Test Bodies

None found. Two `def test_...: pass` matches in `tests/test_new_scripts.py:240-243` are inside a `textwrap.dedent` string literal used as fixture input for `count_test_functions()` — they are test data, not actual test functions.

### False Positive in Grep Count

The raw `def test_` grep across `tests/` reports 1216 matches. Three are false positives:
- `tests/gh_test_helpers.py:11` — inside a module docstring usage example
- `tests/test_new_scripts.py:240,242` — inside a string literal (fixture data)

Adjusted total: **1213 actual test functions** across 18 test files.

## Test Function Distribution

| File | Count |
|------|-------|
| `test_sprint_runtime.py` | 202 |
| `test_verify_fixes.py` | 188 |
| `test_pipeline_scripts.py` | 166 |
| `test_hooks.py` | 113 |
| `test_bugfix_regression.py` | 98 |
| `test_kanban.py` | 86 |
| `test_release_gate.py` | 74 |
| `test_new_scripts.py` | 52 |
| `test_gh_interactions.py` | 41 |
| `test_property_parsing.py` | 38 |
| `test_sprint_teardown.py` | 32 |
| `test_validate_anchors.py` | 27 |
| `test_hexwise_setup.py` | 27 |
| `test_sync_backlog.py` | 19 |
| `test_sprint_analytics.py` | 16 |
| `test_lifecycle.py` | 15 |
| `test_fakegithub_fidelity.py` | 15 |
| `test_golden_run.py` | 4 |

## Conclusion

The test suite is clean. There are no skipped, disabled, xfail, commented-out, or placeholder tests. The single runtime `self.skipTest()` is an intentional graceful-degradation path for local development and fails hard in CI. No action needed.
