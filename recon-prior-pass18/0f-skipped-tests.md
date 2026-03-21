# 0f - Skipped / Disabled Tests

**Date:** 2026-03-16
**Total tests collected:** 750 (via `pytest --collect-only`)
**Test files:** 16

## Decorator-Based Skips

No instances found of:
- `@unittest.skip` / `@unittest.skipIf` / `@unittest.skipUnless`
- `@pytest.mark.skip` / `@pytest.mark.skipif`
- `@unittest.expectedFailure`
- `@pytest.mark.xfail`
- Any pytest markers at all (no `@pytest.mark.*` usage anywhere in tests)

## Conditional Runtime Skips (self.skipTest)

Two instances found, both are conditional on environment availability:

### 1. `tests/test_sprint_runtime.py:1173`

```python
def test_jq_filters_merge_commits(self):
    """With jq available, merge commits (2+ parents) are excluded."""
    if not FakeGitHub._check_jq():
        self.skipTest("jq package not installed")
```

**Assessment:** Skips when `jq` is not installed. This is a legitimate environment-gated test. The `jq` dependency is optional (only needed for FakeGitHub fidelity). The test exercises the merge-commit filtering path which only runs when jq is available.

### 2. `tests/test_golden_run.py:116`

```python
self.skipTest(
    f"Golden recordings absent for {phase_name} — "
    "run GOLDEN_RECORD=1 to create them"
)
```

**Assessment:** Skips when golden recordings are missing. This is a data-dependent skip -- the test requires pre-recorded golden files that must be generated with `GOLDEN_RECORD=1`. A warning is emitted before the skip. This is standard practice for golden/snapshot testing.

## Commented-Out Tests

No instances found of `# def test_` patterns.

## Empty / No-Assert Tests

No instances found of:
- Test methods with only `pass` or `...` as body
- Test methods with only a docstring and no assertions
- Tautological assertions (`assert True`, `assert 1`) -- the two hits were inside test fixture data (strings being written to temp files as mock test content, not actual test assertions)

## TODO/FIXME/HACK in Test Files

Found in `tests/test_pipeline_scripts.py` only:
- Line 724, 736-737: Tests for unsupported language (Haskell) verify that setup_ci generates a `TODO` comment rather than crashing. These are testing that production code emits a TODO, not marking test work as incomplete.
- Line 383: Tests that `US-XXXX` placeholder appears in output -- testing template behavior.

No `FIXME`, `HACK`, `XXX`, or `WORKAROUND` markers found in test files.

## Summary

The test suite is clean. Out of 750 tests:
- **0** are decorator-skipped or xfail'd
- **2** have conditional runtime skips (both legitimate environment gates)
- **0** are commented out or empty
- **0** have tautological assertions

No evidence of tests being silenced to hide failures.
