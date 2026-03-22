# Recon 0f: Skipped, Disabled, and TODO Tests

**Date:** 2026-03-21
**Scope:** All test files in `tests/` (18 files)

## Summary

The test suite is clean. There are no `@pytest.mark.skip`, `@pytest.mark.xfail`,
`@unittest.skip`, commented-out test functions, empty test functions, or early-return
disabled tests anywhere in the codebase.

One conditional skip mechanism exists, and it is intentional and well-documented.

## Skipped / Conditionally Disabled Tests

### 1. Golden snapshot tests — conditional `skipTest` (intentional)

**File:** `tests/test_golden_run.py:116`
**Mechanism:** `self.skipTest(...)` inside `_assert_golden_phase()`
**Condition:** When golden recording files are absent and not running in CI.
In CI, the test *fails* instead of skipping (line 105).

This is a deliberate design — the helper method `_assert_golden_phase` serves
three modes:
- `GOLDEN_RECORD=1`: record golden snapshots
- Recordings present: replay and assert against snapshots
- Recordings absent (local): skip with warning; (CI): hard fail

**Verdict:** Working as intended. Not a coverage gap.

## TODO / FIXME / HACK Comments in Test Code

**None found.** All occurrences of "TODO", "HACK", and "XXX" in test files are
either:
- Assertions checking that production code emits "TODO" strings (e.g.,
  `test_pipeline_scripts.py:824` asserts unsupported languages produce a TODO
  comment in generated CI YAML)
- Literal data values in test assertions (e.g., "US-XXXX" placeholder patterns,
  "HACKED" as a rejected input string)
- Kanban status labels ("TODO" as a valid kanban state in output)

No actual TODO/FIXME/HACK annotations exist in test code.

## Empty Test Functions

**None found.** No test functions have `pass`, `...`, or docstring-only bodies.

## Commented-Out Test Functions

**None found.** No `# def test_` or `# async def test_` patterns exist.

## Other Skip Mechanisms Checked

| Mechanism | Found? |
|-----------|--------|
| `@pytest.mark.skip` / `skipIf` | No |
| `@pytest.mark.xfail` | No |
| `@unittest.skip` / `skipUnless` | No |
| `@unittest.expectedFailure` | No |
| `pytest.skip()` | No |
| `raise unittest.SkipTest` | No |
| Commented-out test classes | No |
| Early bare `return` in test body | No |
| `@disabled` / `@ignore` decorators | No |

## Conclusion

The test suite has no skipped, disabled, or incomplete tests. The single
conditional skip in `test_golden_run.py` is a well-designed recording/replay
mechanism, not a coverage gap.
