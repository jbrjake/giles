# Phase 0f: Skipped/Disabled Tests

Audit date: 2026-03-14
Scope: all files in `tests/` (13 files, ~1400 lines of test methods)

## Explicitly Skipped

| File | Test | Skip Reason |
|------|------|-------------|
| (none) | | No `@unittest.skip`, `@pytest.mark.skip`, `skipIf`, `skipUnless`, `pytest.skip()`, or `xfail` decorators found anywhere in the test suite. |

## Conditionally Skipped (runtime)

| File | Test | Mechanism | Condition |
|------|------|-----------|-----------|
| `test_golden_run.py:102` | `test_golden_full_setup_pipeline` | `self.skipTest(...)` | Fires when `tests/golden/recordings/` directory has no golden snapshots. Currently **does not fire** because recordings exist (5 JSON files + manifest). |

## Conditionally Gated (environment variable)

| File | Line | Variable | Effect |
|------|------|----------|--------|
| `test_golden_run.py:43` | `RECORD_MODE = os.environ.get("GOLDEN_RECORD", "") == "1"` | `GOLDEN_RECORD` | When set to `"1"`, the golden test records new snapshots instead of replaying. In record mode, the `_check_or_record` method at :94 writes snapshots rather than comparing them, so **assertions on snapshot diffs are bypassed**. Without `GOLDEN_RECORD=1`, the test runs in replay mode with full assertions. |

## Effectively Disabled (assert nothing / catch-all / commented)

| File | Test | Issue |
|------|------|-------|
| (none) | | No commented-out `def test_*` methods found. |
| (none) | | No `def test_*` methods with `pass` as the only body found. |
| (none) | | No `def test_*` methods that assert only `True` or assert nothing found. All 360+ test methods contain at least one `self.assert*`, `self.assertRaises`, or `with self.assertRaises(...)` call. |
| (none) | | No `except: pass` or `except Exception: pass` patterns found inside test methods. All `except` clauses in `fake_github.py` and `golden_recorder.py` are in helper/utility code, not in test assertions, and they handle specific error types (`ValueError`, `UnicodeDecodeError`, `OSError`). |

## Observations

1. **Clean test suite.** Zero explicitly skipped or disabled tests. This is uncommon and suggests the codebase does not carry test debt in the form of dormant test methods.

2. **One conditional skip path exists but is inactive.** The golden test's `self.skipTest()` at `test_golden_run.py:102` is the only runtime skip mechanism. It fires only when golden recordings are absent. Since `tests/golden/recordings/` contains 5 snapshot files, this path does not execute in normal CI or local runs.

3. **Golden record mode weakens assertions.** When `GOLDEN_RECORD=1` is set, `test_golden_full_setup_pipeline` records snapshots rather than comparing them. In this mode, the test passes without verifying any snapshot diffs. This is by design (it's a recording workflow), but it means running tests with that env var set produces a false green signal for regression detection.

4. **No empty test stubs.** Every `def test_*` method has a meaningful body with assertions. No placeholder tests were found.

5. **No catch-all exception swallowing in tests.** All exception handling in the test infrastructure (`fake_github.py`, `golden_recorder.py`) catches specific exception types and either re-raises or takes appropriate action (returns error, skips binary files). No `except: pass` anti-patterns.

6. **Test helper files are not test classes.** `fake_github.py`, `golden_recorder.py`, and `golden_replay.py` contain no `def test_*` methods. They are pure test infrastructure.
