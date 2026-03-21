# 0f - Skipped/Disabled Tests

**Pass:** P24
**Date:** 2026-03-19
**Scope:** All test files under `tests/`

## Search Methods

Searched for all standard skip/disable patterns:
- `@pytest.mark.skip` / `@pytest.mark.skipIf` -- **none found**
- `@unittest.skip` / `@unittest.skipIf` / `@unittest.skipUnless` -- **none found**
- `pytest.skip()` -- **none found**
- `@pytest.mark.xfail` -- **none found**
- `@unittest.expectedFailure` -- **none found**
- `self.skipTest()` -- **1 found** (see below)
- Commented-out test functions (`# def test_`) -- **none found**
- Test functions with `pass` as sole body -- **none found**
- Conditional skips based on environment/platform/version -- **none found** (beyond the 1 below)
- `@pytest.mark.parametrize` / `@pytest.mark.slow` / `@pytest.mark.flaky` -- **none found**

## Findings

### 1. Conditional skipTest in test_golden_run.py

**File:** `tests/test_golden_run.py`, line 116
**Pattern:** `self.skipTest(...)` inside a conditional branch
**Context:**

```python
# Line 95-119 of tests/test_golden_run.py
if RECORD_MODE:
    recorder.snapshot(phase_name)
elif replayer.has_recordings():
    snapshot = replayer.load_snapshot(phase_name)
    diffs = check_fn(snapshot)
    self.assertEqual(diffs, [], f"{phase_name} mismatch: {diffs}")
else:
    # BH-P11-051: Mark as skipped so it's visible in test output
    if os.environ.get("CI"):
        self.fail(
            f"Golden recordings absent for {phase_name} in CI — "
            "run GOLDEN_RECORD=1 to create them"
        )
    else:
        import warnings
        warnings.warn(...)
        self.skipTest(
            f"Golden recordings absent for {phase_name} — "
            "run GOLDEN_RECORD=1 to create them"
        )
```

**Reason given:** Golden recordings are absent for the test phase. In CI, this is a hard failure. Locally, it degrades to a skip with a warning.

**Risk assessment:** LOW. The golden recordings were committed in BH23-112 (commit 39174b6), so this skip path should not be hit in normal operation. The CI path correctly `self.fail()`s, so this only affects local runs where recordings have been deleted. This is a reasonable design -- it prevents false passes while allowing local development without recordings.

**Active in current codebase?** No -- since the recordings are committed to git (in `tests/golden/recordings/`), the `replayer.has_recordings()` branch should always be taken. The skipTest path is a safety net for when recordings are missing, not an active skip.

## Other Observations

### No Test Skip Debt

The codebase has zero permanently skipped or disabled tests. This is notable given the project has 854+ tests (per commit 7c2dc4e). Every test that exists is intended to run.

### Application-Level "skipped" (Not Test Skips)

One grep hit in `tests/test_verify_fixes.py` line 1758 references `gen.skipped` -- this is testing the application's ConfigGenerator skip list (for rejected symlinks), not a test skip mechanism. It is correctly verifying that the application records rejected operations.

## Summary

| Type | Count | Details |
|------|-------|---------|
| `@pytest.mark.skip` | 0 | -- |
| `@pytest.mark.skipIf` | 0 | -- |
| `@unittest.skip` variants | 0 | -- |
| `@pytest.mark.xfail` | 0 | -- |
| `self.skipTest()` | 1 | `test_golden_run.py:116` -- conditional, only when recordings missing locally |
| Commented-out tests | 0 | -- |
| Pass-only test bodies | 0 | -- |
| `@unittest.expectedFailure` | 0 | -- |
| **Total disabled/skipped** | **1** | Effectively 0 in practice (recordings are committed) |
