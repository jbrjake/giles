# BH-37 Phase 0f: Skipped / Disabled Tests

**Date**: 2026-03-21
**Scope**: All `test_*.py` files (20 files in `tests/`, 2 in `scripts/`)

## Summary

The test suite is clean. No skipped, disabled, or stub tests found.

## Detailed Scan Results

| Pattern | Hits |
|---------|------|
| `@pytest.mark.skip` / `@unittest.skip` decorators | 0 |
| `pytest.skip()` calls | 0 |
| `@pytest.mark.xfail` markers | 0 |
| `skipIf` / `skipUnless` decorators | 0 |
| Commented-out `def test_` functions | 0 |
| Stub tests (body is just `pass`) | 0 |
| Tests with `return` as first statement (before assertions) | 0 |
| TODO/FIXME/HACK annotations in test files | 0 |

## One Conditional Skip (Intentional)

`tests/test_golden_run.py:116` -- `self.skipTest()` inside `_check_or_record()`.

This is a helper method (not a test itself) that conditionally skips golden snapshot comparisons when recording files are absent **and** the environment is not CI. In CI, it calls `self.fail()` instead, ensuring the skip never silently passes in automation. The golden recordings exist at `tests/golden/recordings/` (6 files), so this path is not normally exercised.

**Verdict**: Intentional and well-designed. Not a problem.

## Conclusion

No action needed. The test suite has no dead weight.
