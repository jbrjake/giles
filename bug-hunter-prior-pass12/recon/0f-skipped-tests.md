# 0f -- Skipped, Disabled, and Neutered Tests

**Audit date:** 2026-03-15
**Pass:** 12
**Scope:** All 12 test files + 2 test helpers under `tests/` (excluding `.venv/`)
**Test count:** 634 tests collected (via `pytest --co -q`)

## Summary

The test suite is clean. There are **zero** explicit skips, **zero** commented-out tests, **zero** xfails, **zero** empty test bodies, and **zero** broad exception swallowing. Two minor findings carry over from prior passes: one assertion-free "no-crash" test, and golden snapshot comparisons that silently degrade when recordings are absent.

**Test file inventory** (12 test files + 2 helpers):

| File | Approx tests | Notes |
|------|-------------|-------|
| `tests/test_gh_interactions.py` | ~257 | Largest file; tests for all GitHub-facing scripts |
| `tests/test_pipeline_scripts.py` | ~137 | Script unit tests |
| `tests/test_release_gate.py` | ~46 | Release flow tests |
| `tests/test_verify_fixes.py` | ~43 | Regression tests for bug-hunter fixes |
| `tests/test_property_parsing.py` | ~30 | Hypothesis property-based tests (26 `@given` tests) |
| `tests/test_hexwise_setup.py` | ~25 | Integration: project scanning |
| `tests/test_validate_anchors.py` | ~25 | Anchor validation tests |
| `tests/test_sprint_teardown.py` | ~28 | Teardown classification tests |
| `tests/test_sync_backlog.py` | ~18 | Backlog sync tests |
| `tests/test_sprint_analytics.py` | ~15 | Metrics computation tests |
| `tests/test_lifecycle.py` | ~13 | End-to-end lifecycle tests |
| `tests/test_golden_run.py` | 1 | Multi-phase golden recording replay |
| `tests/fake_github.py` | -- | Test double (FakeGitHub) |
| `tests/gh_test_helpers.py` | -- | MonitoredMock / patch_gh utilities |

---

## 1. Explicit Skips

**None found.** Searched for all standard skip mechanisms:

- `@pytest.mark.skip` / `@pytest.mark.skipIf` / `@pytest.mark.skipUnless` -- 0 hits
- `@unittest.skip` / `@unittest.skipIf` / `@unittest.skipUnless` -- 0 hits
- `pytest.skip()` / `self.skipTest()` -- 0 hits
- `@pytest.mark.xfail` / `@unittest.expectedFailure` -- 0 hits

---

## 2. Commented-Out Tests

**None found.** Searched for:

- `# def test_` -- 0 hits
- `# assert` / `# self.assert` -- 0 hits

---

## 3. Tautological Assertions

**None found.** Searched for:

- `assertTrue(True)` -- 0 hits
- `assert True` -- 1 hit, but it is inside fixture content written to a temp file (`test_pipeline_scripts.py:977` writes `"def test_create_widget():\n    assert True\n"` as test fixture data for the test_coverage script), not in an actual test method
- `assertEqual(x, x)` with same variable on both sides -- 0 hits
- `assert 1 == 1` -- 0 hits
- `assert not False` -- 0 hits

---

## 4. Empty Test Bodies

**None found.** Searched for:

- `def test_...: pass` (test method with only `pass`) -- 0 hits
- `def test_...: """docstring""" pass` (docstring + pass only) -- 0 hits

Note: `pass` appears in test files only inside fixture content (test data written to temp files) and inside properly structured except clauses.

---

## 5. Tests with No Assertions

**1 found.**

### `test_gh_interactions.py` -- `TestUpdateSprintStatus.test_skips_missing_file`

```python
def test_skips_missing_file(self):
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        rows = [{"story_id": "X", "short_title": "X", "sp": 0,
                  "status": "todo", "closed": ""}]
        # Should not raise
        update_burndown.update_sprint_status(1, rows, Path(tmpdir))
```

This test verifies only that the function does not crash when `SPRINT-STATUS.md` is absent. It makes no assertion about return value, side effects, or file state. While "no-crash" tests have some value, this one could be strengthened by asserting that no file was created or that the function returns a specific value.

**Severity:** Low. The comment "Should not raise" documents the design intent, but any exception-free codepath passes this test.

Two other "Should not raise" comments exist (`test_gh_interactions.py:531` and `:543`) but those tests do follow up with `mock_gh.assert_called_once()` and similar, so they have real assertions.

---

## 6. Broad Exception Swallowing

**None found in test assertions.** Searched for:

- Bare `except:` clauses -- 0 hits
- `except Exception: pass` -- 0 hits

### Legitimate except-pass patterns found (not swallowing):

| Location | Pattern | Verdict |
|----------|---------|---------|
| `test_property_parsing.py:296-297` | `except ValueError: pass` | Correct: hypothesis test verifying unterminated arrays raise ValueError -- catching it is the test's point |
| `test_verify_fixes.py:239-242` | `except SystemExit: self.fail(...)` / `except ConfigError: pass` | Correct: explicitly asserts SystemExit is NOT raised and ConfigError IS expected |

### Exception handling in test infrastructure (not test methods):

| Location | Pattern | Verdict |
|----------|---------|---------|
| `fake_github.py:401-402` | `except (ValueError, TypeError): pass` | Legitimate: unparseable date filter falls back to returning all data |
| `fake_github.py:562,594,761,796` | `except ValueError: return self._fail(...)` | Legitimate: invalid number parsing returns an error response |
| `fake_github.py:104` | `except ImportError:` | Legitimate: pyjq availability detection |
| `golden_recorder.py:98` | `except (UnicodeDecodeError, OSError): continue` | Legitimate: skip binary/unreadable files during recording |

---

## 7. Silently Degraded Test Paths

### `test_golden_run.py` -- Golden snapshot comparisons silently skipped

```python
else:
    import warnings
    warnings.warn(
        f"Golden recordings absent for {phase_name} -- "
        "run GOLDEN_RECORD=1 to create them",
        stacklevel=2,
    )
```

When golden recording files are absent from `tests/golden/recordings/`, the test issues a `warnings.warn()` and continues without performing any snapshot comparison. The non-golden assertions (count checks) still execute, but per-field regression checks are silently skipped.

**Severity:** Medium. The design is intentional (golden recordings may not exist in a fresh clone), but CI could treat missing recordings as a failure or make the warning more prominent.

### `fake_github.py` strict mode warnings

FakeGitHub in strict mode (`strict=True`) emits `warnings.warn()` when tests use unimplemented flags. This is a test-quality enforcement mechanism, not a neutered test. Tests that use `warnings.catch_warnings()` + `warnings.simplefilter("error")` convert these to hard failures.

---

## 8. TODO/FIXME/HACK/XXX in Test Files

**No actionable items.** All occurrences are in test fixture data or assertions about expected content:

- `test_pipeline_scripts.py:383` -- asserts `"US-XXXX"` appears in output (test fixture data)
- `test_pipeline_scripts.py:724,736-737` -- tests that unsupported language produces a `TODO` comment in generated CI YAML (asserting on production behavior)
- `test_pipeline_scripts.py:1205` -- docstring mentions `HACKING.md` as an example filename

---

## 9. Mock Usage Analysis

**493 total mock-related references** across 11 files. The highest mock density is in `test_gh_interactions.py` (218 occurrences) which is expected given it tests GitHub CLI interactions.

The project has implemented two structural safeguards against mock abuse:
1. **`gh_test_helpers.MonitoredMock`** -- warns when a mock is called but its `call_args` are never inspected (added pass 11)
2. **`FakeGitHub` strict mode** -- warns when tests use CLI flags that the mock doesn't implement (added pass 11)

These are healthy signals that mock quality has been actively addressed.

---

## 10. Property-Based Tests

**26 `@given` tests** in `test_property_parsing.py` using hypothesis. These target the top 5 regex/parsing hotspots identified across 11 bug-hunter passes:

- `extract_story_id`
- `extract_sp`
- `_yaml_safe`
- `_parse_team_index` (via table-shaped text)
- `parse_simple_toml`

These provide strong coverage against the recurring "regex over/under-matching" theme from prior passes.

---

## Overall Assessment

| Category | Count | Severity |
|----------|-------|----------|
| Explicit skips | 0 | -- |
| Commented-out tests | 0 | -- |
| Tautological assertions | 0 | -- |
| xfail / expectedFailure | 0 | -- |
| Empty test bodies | 0 | -- |
| Tests with no assertions | 1 | Low |
| Broad exception swallowing | 0 | -- |
| Silently degraded paths | 1 | Medium |
| TODO/FIXME in test code | 0 | -- |

The test suite is well-maintained. The two findings are:

1. **One assertion-free "no-crash" test** (`test_skips_missing_file`) -- could be strengthened with an explicit assertion about return value or side effects.
2. **Golden snapshot comparisons silently degrade** to warnings when recordings are absent -- could mask regressions in CI.

Both findings carry over from prior passes and represent known, accepted risk rather than newly introduced problems.
