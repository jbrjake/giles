# 0f — Skipped, Disabled, and Neutered Tests

Adversarial audit of all test files under `tests/`.
Files examined: 16 test files, 1 conftest, 2 test helpers, CI config.

---

## 1. Explicit Skip / SkipTest

### 1a. Golden test silently skips all phases when recordings are absent (non-CI)

**File:** `tests/test_golden_run.py:102-119`

The `_check_or_record` method has a conditional skip: when golden recordings are absent
and `CI` env var is not set, all 5 snapshot comparisons in `test_golden_full_setup_pipeline`
are silently skipped via `self.skipTest()`. The test appears green but validates nothing.

In CI, recordings are present (committed at `tests/golden/recordings/`), so this is
low-severity. But any developer running locally without `GOLDEN_RECORD=1` first will see
the test pass without performing any actual regression check. The warning message is
emitted but easy to miss.

**Severity:** Low (CI has recordings; local dev is the gap)

### 1b. jq-dependent test skips when jq package is absent

**File:** `tests/test_sprint_runtime.py:1193-1196`

```python
def test_jq_filters_merge_commits(self):
    if not FakeGitHub._check_jq():
        self.skipTest("jq package not installed")
```

This test is the ONLY test verifying that jq filtering correctly excludes merge commits
from the direct-push detector. If `jq` (the Python package) is not installed, the test
is skipped. The CI `Makefile` does not install `jq`, and there is no `requirements-dev.txt`
or `pyproject.toml` specifying it as a dev dependency. This means **this test likely
always skips in CI**.

**Severity:** Medium. The feature being tested (merge commit filtering) degrades silently
when jq is unavailable, and the test for it also degrades silently.

---

## 2. Tests Invisible to CI (unittest discover cannot find them)

### 2a. ALL property-based tests are invisible to CI

**File:** `tests/test_property_parsing.py` (entire file, 499 lines, 26 test methods)

The CI runs `python -m unittest discover -s tests -v` (see `Makefile:13`).
All 5 test classes in this file use bare pytest-style classes (no `unittest.TestCase` base):

```
class TestExtractStoryId:       (line 37)
class TestExtractSp:            (line 102)
class TestYamlSafe:             (line 173)
class TestParseSimpleToml:      (line 293)
class TestParseTeamIndexProperties: (line 454)
```

`unittest discover` only finds classes that inherit from `unittest.TestCase`. These
26 hypothesis property tests (with ~7,200 total examples across all `max_examples`
settings) are only discovered by `pytest`. Since the CI uses `unittest discover`, **none
of these tests run in CI**.

This is the single most significant finding. These tests cover the 5 highest-risk
parsing hotspots (extract_story_id, extract_sp, _yaml_safe, parse_simple_toml,
_parse_team_index) and have historically found real bugs across 22 bug-hunter passes.

**Severity:** Critical. 26 tests covering the most bug-prone code are completely
invisible to CI.

---

## 3. Fuzz Test that Swallows Exceptions

### 3a. parse_simple_toml fuzz test accepts ValueError on any input

**File:** `tests/test_property_parsing.py:296-304`

```python
@given(st.text(max_size=500))
@settings(max_examples=300)
def test_random_text_returns_dict_or_raises_valueerror(self, text: str):
    """Random text either returns a dict or raises ValueError (fuzz test)."""
    try:
        result = parse_simple_toml(text)
        assert isinstance(result, dict)
    except ValueError:
        pass  # Unterminated multiline arrays raise ValueError -- that's fine
```

This test catches and discards ValueError on ANY random input. The docstring says
"unterminated multiline arrays," but the except clause is not scoped -- it would also
swallow ValueError from malformed escape sequences, invalid unicode, or any other
parsing failure. If `parse_simple_toml` regresses to throwing ValueError on valid input,
this test would not catch it.

The comment "that's fine" even acknowledges the gap. A companion test at line 310
(`test_valid_toml_never_raises`) partially compensates by testing well-formed TOML only,
but the fuzz test remains overly permissive.

**Severity:** Low-Medium. The fuzz test's entire value proposition is compromised by
the broad except clause. It can only detect crashes (non-ValueError exceptions), not
parsing errors.

---

## 4. FakeGitHub Silent Degradation (Not a Skipped Test, But Equivalent)

### 4a. FakeGitHub's jq fallback silently weakens all jq-dependent tests

**File:** `tests/fake_github.py:120-133`

```python
def _maybe_apply_jq(self, json_str, flags):
    ...
    if not self._check_jq():
        return json_str  # graceful fallback
```

When the `jq` Python package is not installed, `_maybe_apply_jq` returns unfiltered data.
This means ANY test that relies on `--jq` filtering through FakeGitHub is silently
testing against unfiltered data. Tests pass, but they are not testing the filtering logic.

Production code that uses `gh --jq '...'` will get filtered results from real GitHub.
Without the jq package installed, tests see the full unfiltered data, which may mask
bugs where jq expressions are wrong (e.g., a typo in a jq filter would not be caught).

The fidelity tests in `test_fakegithub_fidelity.py` import `jq` directly and would
fail to import if it's missing, so those tests would error out (not silently pass). But
the timeline-based tests that go through FakeGitHub would silently degrade.

**Severity:** Medium. The `jq` package is not listed as a CI dependency, so this
degradation likely applies to CI runs.

---

## 5. Commented-Out / Removed Tests

### 5a. Tests 11 and 12 removed from lifecycle

**File:** `tests/test_lifecycle.py:283-285`

```python
# Tests 11 (extract_sp) and 12 (commit validation) removed --
# comprehensive versions live in test_gh_interactions.py:
#   TestExtractSP (10 cases) and TestValidateMessage (9 cases).
```

The comment says replacements exist. Confirmed: `test_gh_interactions.py` has 10
`TestExtractSP` tests and 9 `TestValidateMessage` tests. This is clean consolidation,
not a coverage gap.

**Severity:** None (properly migrated)

### 5b. test_source_uses_replace_not_format removed

**File:** `tests/test_verify_fixes.py:618-620`

```python
# test_source_uses_replace_not_format removed (P12-028):
# The behavioral tests above (format specifiers don't crash, braces
# preserved) already verify the fix.  Inspecting source is brittle.
```

Confirmed: behavioral tests at lines 600-616 cover the same fix. Removal of source
inspection test is sound.

**Severity:** None (properly replaced)

---

## 6. Weak / Tautological Assertions

### 6a. Import guard test checks hasattr/callable instead of behavior

**File:** `tests/test_bugfix_regression.py:65-79`

```python
def test_import_guard_uses_import_error(self):
    self.assertTrue(hasattr(check_status, 'main'))
    self.assertTrue(hasattr(check_status, 'check_ci'))
    self.assertTrue(hasattr(check_status, 'check_prs'))
    self.assertTrue(callable(check_status.main))
```

These assertions test that the module imported successfully, not that the import guard
works when sync_backlog is unavailable. The test should mock `sync_backlog` as
unimportable and verify the module still loads. As written, these assertions always
pass regardless of whether the import guard exists.

The docstring even acknowledges this: "Replaced source-code inspection with behavioral
test" -- but the "behavioral" test is just checking attributes exist on an
already-imported module.

**Severity:** Low-Medium. The import guard it claims to test is not actually exercised.

---

## 7. Early Returns Reducing Test Coverage

### 7a. Property test exits early for standard IDs without checking slug safety

**File:** `tests/test_property_parsing.py:63-68`

```python
def test_result_is_safe_for_filenames(self, title: str):
    result = extract_story_id(title)
    if re.match(r"^[A-Z]+-\d+$", result):
        return  # <-- exits without checking anything
    assert re.match(r"^[a-z0-9_-]+$", result), ...
```

When the input happens to match a standard story ID format, the test returns immediately
without verifying that the ID is actually filename-safe. The early return assumes
`[A-Z]+-\d+` is always safe, but this is an unchecked assumption. If `extract_story_id`
ever returned something like `REALLY-LONG-PREFIX-999999999999`, the test would not
check the filename-safety invariant for it.

**Severity:** Very Low (the pattern [A-Z]+-\d+ is inherently filename-safe)

---

## 8. Hypothesis Settings

All hypothesis `@settings(max_examples=N)` values are reasonable:
- Range: 100 to 500
- No `suppress_health_check` anywhere
- No `max_examples=1` anywhere
- No `HealthCheck` imports or suppression

**Severity:** None

---

## 9. Conftest.py

**File:** `tests/conftest.py`

Clean -- only adds script directories to `sys.path`. No pytest plugins, no
`filterwarnings`, no `pytest_collection_modifyitems`, no failure suppression.

**Severity:** None

---

## 10. No pytest.ini / pyproject.toml Test Config

There is no `pytest.ini`, `pyproject.toml`, or `setup.cfg` with pytest configuration.
This means no `filterwarnings`, no `addopts = --ignore`, no `markers` that could be
hiding skip behavior. Clean.

**Severity:** None

---

## Summary Table

| # | Finding | File:Line | Severity |
|---|---------|-----------|----------|
| 2a | **26 property tests invisible to CI** (bare pytest classes + `unittest discover`) | `test_property_parsing.py:37-498` | **Critical** |
| 1b | jq-dependent test skips when jq not installed (likely always in CI) | `test_sprint_runtime.py:1193-1196` | Medium |
| 4a | FakeGitHub jq fallback silently weakens jq-dependent tests | `fake_github.py:120-133` | Medium |
| 3a | Fuzz test swallows ValueError broadly | `test_property_parsing.py:296-304` | Low-Medium |
| 6a | Import guard test checks hasattr, not actual import guard behavior | `test_bugfix_regression.py:65-79` | Low-Medium |
| 1a | Golden test skips locally when recordings absent | `test_golden_run.py:102-119` | Low |
| 7a | Property test early return skips assertion for standard IDs | `test_property_parsing.py:63-68` | Very Low |

### Not Found (Clean)

- No `@pytest.mark.skip`, `@pytest.mark.xfail`, `@pytest.mark.skipIf` decorators anywhere
- No `@unittest.expectedFailure` anywhere
- No test functions prefixed with `x` or `_` (disable pattern)
- No empty test functions (just `pass` or `...`) -- the `pass` hits in grep are inside
  test fixture data (temp files being written), not test bodies
- No `assert True` or `assert 1` tautologies in actual test assertions -- the grep
  hits are inside test fixture strings being written to temp files
- No tests that catch all exceptions and pass (the only except-pass is the fuzz test's
  `except ValueError`, which is scoped)
- No `suppress_health_check` or `HealthCheck` suppression
- No conftest plugins suppressing failures
- No pytest configuration files suppressing warnings
