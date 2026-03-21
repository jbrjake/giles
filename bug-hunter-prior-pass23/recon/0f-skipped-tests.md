# 0f — Skipped / Disabled Tests

**Date:** 2026-03-18
**Suite size:** 864 test methods across 16 test files

## Summary

The test suite is clean. There are zero decorator-based skips, zero xfail markers, zero commented-out tests, and zero empty test stubs. The only mechanisms that reduce effective coverage are one conditional runtime skip and one meta-test exemption list (currently empty).

| Category | Count |
|----------|-------|
| `@pytest.mark.skip` / `@unittest.skip` decorators | 0 |
| `@pytest.mark.xfail` / `@unittest.expectedFailure` | 0 |
| `pytest.skip()` calls | 0 |
| `self.skipTest()` calls | 1 (conditional) |
| `skipIf` / `skipUnless` decorators | 0 |
| `# def test_` (commented-out tests) | 0 |
| `def _test_` / `def xtest_` (disabled by rename) | 0 |
| `def test_...: pass` (empty body stubs) | 0 |
| `_KNOWN_UNTESTED` exemption entries | 0 (frozenset is empty) |

---

## 1. Conditional Skip: Golden Recordings Absent

**File:** `tests/test_golden_run.py:116`
**Method:** `_check_or_record()` (called by `test_golden_full_setup_pipeline`)

```python
if os.environ.get("CI"):
    self.fail("Golden recordings absent for {phase_name} in CI — ...")
else:
    warnings.warn("GOLDEN COVERAGE GAP: recordings absent for ...")
    self.skipTest("Golden recordings absent for {phase_name} — run GOLDEN_RECORD=1 to create them")
```

**Behavior:** In CI, missing recordings fail hard. Locally, the test skips with a warning. This means a fresh clone without golden recordings will silently skip the 4 golden-run phases. The `warnings.warn()` helps visibility but unittest does not surface it prominently.

**Risk:** LOW. The skip only activates when recordings are not present, which is a known bootstrapping condition. CI enforces hard failure, preventing silent regression in the pipeline that matters.

---

## 2. `_KNOWN_UNTESTED` Exemption Mechanism

**File:** `tests/test_verify_fixes.py:1256`

```python
_KNOWN_UNTESTED = frozenset()
```

This is a meta-test gate: `test_every_script_main_has_test` scans all scripts that define `main()` and verifies that a corresponding `<module>.main()` call exists in the test source. Any script not covered must be added to `_KNOWN_UNTESTED` or the test fails. The set is currently empty, meaning every script with `main()` has test coverage.

A companion test `test_known_untested_not_stale` (line 1302) ensures entries don't linger after tests are added. Together they form a ratchet: coverage can only increase.

**Status:** SATISFIED. The frozenset is empty and both meta-tests pass.

---

## 3. Tests That Are Effectively No-Ops

### Lock acquire-and-release tests (implicit "didn't crash" assertion)

**File:** `tests/test_kanban.py`

| Line | Method | Body |
|------|--------|------|
| 241 | `test_lock_story_acquires_and_releases` | Two `with lock_story(p): pass` blocks |
| 252 | `test_lock_sprint_acquires_and_releases` | Two `with lock_sprint(sprint_dir): pass` blocks |

These tests verify that context-manager locks can be acquired and released twice without deadlock. The `pass` bodies are intentional: the assertion is "no exception raised." This is a legitimate pattern for lock/resource tests, but it means a broken lock that silently fails to acquire would still pass.

**Note:** `test_lock_sprint_creates_lock_file` (line 261) does the same acquire but additionally asserts the sentinel file exists, providing a stronger check. No equivalent exists for `lock_story`.

---

## 4. Exception Catches Without Assertions

### 4a. Fuzz test: ValueError is acceptable

**File:** `tests/test_property_parsing.py:305`

```python
def test_random_text_returns_dict_or_raises_valueerror(self, text: str):
    try:
        result = parse_simple_toml(text)
        assert isinstance(result, dict)
    except ValueError:
        pass  # Unterminated multiline arrays raise ValueError -- that's fine
```

This is a Hypothesis property test. The `except ValueError: pass` is correct: the test verifies that random input either parses to a dict or raises ValueError (never a different exception or a crash). The pattern is standard for fuzz tests.

### 4b. SystemExit guard

**File:** `tests/test_verify_fixes.py:251`

```python
def test_config_error_does_not_raise_system_exit(self):
    try:
        load_config("nonexistent-dir")
    except SystemExit:
        self.fail("load_config raised SystemExit instead of ConfigError")
    except ConfigError:
        pass  # expected
```

This is a specific negative test: it verifies that `load_config` does NOT call `sys.exit()`. The `except ConfigError: pass` is correct because the companion test `test_config_error_is_value_error` (line 246) already asserts ConfigError is raised.

---

## 5. Meta-Test Gates

| Test | File:Line | Purpose | Satisfied? |
|------|-----------|---------|------------|
| `test_every_script_main_has_test` | `test_verify_fixes.py:1258` | Every `main()` script has a test calling `module.main()` | YES (empty `_KNOWN_UNTESTED`) |
| `test_known_untested_not_stale` | `test_verify_fixes.py:1302` | No stale entries in `_KNOWN_UNTESTED` | YES (frozenset is empty, nothing to go stale) |

Both gates form a coverage ratchet. If a new script with `main()` is added without a test, CI fails. If a test is added for a previously exempted script but the exemption isn't removed, CI also fails.

---

## 6. Other Observations

- **No `TODO`/`FIXME`/`HACK`/`XXX` comments in test code** that indicate deferred testing work. The `TODO` hits found are all in assertion strings (testing that generated output contains the word "TODO"), not meta-comments about missing tests.
- **No `assertTrue(True)` or trivially-true assertions** found anywhere.
- **No `@unittest.expectedFailure`** markers.
- **No tests disabled by renaming** (`_test_*`, `xtest_*`).
