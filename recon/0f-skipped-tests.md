# 0f — Skipped / Disabled Tests

## Summary

No `@pytest.mark.skip`, `@unittest.skip`, `pytest.skip()`, `xfail`, or commented-out `# def test_` patterns exist anywhere in the test suite (excluding `.venv`). The suite has one conditional skip and one _KNOWN_UNTESTED mechanism, both documented below.

## Conditional skip: golden recordings absent

**File:** `tests/test_golden_run.py:116`

```python
self.skipTest(
    f"Golden recordings absent for {phase_name} — "
    "run GOLDEN_RECORD=1 to create them"
)
```

Triggered when golden snapshot files don't exist locally and `CI` env var is not set. In CI, the same condition calls `self.fail()` instead (hard failure). Locally, recordings are present (`tests/golden/recordings/` has 5 phase files + manifest), so this skip is not currently active.

**Risk:** If a developer runs tests without recordings (fresh clone, recordings not committed), the golden test silently skips rather than failing. The `warnings.warn()` before the skip helps visibility but it's easy to miss.

## _KNOWN_UNTESTED mechanism

**File:** `tests/test_verify_fixes.py:1256`

```python
_KNOWN_UNTESTED = frozenset()
```

The set is **empty** — every discovered script is expected to have a test. The test class (`TestScriptCoverage`) enforces this: it scans all Python scripts under `scripts/` and `skills/*/scripts/`, then fails if any lack a corresponding test import. A companion test (`test_KNOWN_UNTESTED_no_stale_entries`) verifies the frozenset contains no phantom entries.

**Risk:** None currently — the set is empty and the enforcement is active. But it's a soft gate: a script added without tests would cause a CI failure, not a compile error.

## No other skips found

Searched across all files in `tests/` (`*.py`) for:
- `@pytest.mark.skip` — none
- `@unittest.skip` — none
- `pytest.skip(` — none
- `xfail` — none (only in `.venv` third-party packages)
- `# def test_` (commented-out tests) — none
- `_KNOWN_UNTESTED` with entries — none (frozenset is empty)

The "skip" keyword appears frequently in test names and docstrings (e.g., `test_skips_missing_file`, "silently skipping"), but these test the production code's skip behavior, not the tests themselves.

## Verdict

Test suite has no dead weight. The golden-run conditional skip is the only active skip mechanism, and it's guarded against CI silent failures. The _KNOWN_UNTESTED gate is clean. No coverage holes introduced by explicit test suppression.
