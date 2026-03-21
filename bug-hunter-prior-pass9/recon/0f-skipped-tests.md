# Recon 0f: Skipped/Disabled Tests & Code Quality Markers

**Date:** 2026-03-15
**Repo:** giles (Claude Code plugin for agile sprints)
**Method:** Grep for `skip`, `skipTest`, `skipIf`, `skipUnless`, `@unittest.skip`, `pytest.mark.skip`, `TODO`, `FIXME`, `HACK`, `XXX`, `WORKAROUND`, commented-out tests, and weak assertions (`assert True`, `assertTrue(True)`) across all test files.

---

## 1. Skipped Tests

### Conditional skips (runtime)

| File | Line | Mechanism | Condition |
|------|------|-----------|-----------|
| `test_golden_run.py` | 107 | `self.skipTest(...)` | Golden recordings absent (requires `GOLDEN_RECORD=1` env var) |

**No `@unittest.skip`, `skipIf`, `skipUnless`, or `pytest.mark.skip` decorators found anywhere.**

This is a clean result: only one conditional skip, and it is documented/intentional. The golden run test skips when snapshot recordings don't exist, which is correct behavior (the recordings must be explicitly generated).

---

## 2. TODO Markers in Test Code

| File | Line | Context |
|------|------|---------|
| `test_pipeline_scripts.py` | 673 | Docstring: "Unsupported language (e.g. Haskell) produces a TODO setup comment, not a crash." |
| `test_pipeline_scripts.py` | 685 | Comment: `# Should contain a TODO comment for the unsupported language` |
| `test_pipeline_scripts.py` | 686 | Assertion: `self.assertIn("TODO", yaml)` |

These are **not deferred work**. They test that the CI generator correctly emits a `TODO` comment for unsupported languages. The word "TODO" here is the expected output being verified, not a code quality marker.

---

## 3. FIXME / HACK / XXX / WORKAROUND Markers

**None found in any test file.** Zero instances of `FIXME`, `HACK`, `XXX`, or `WORKAROUND` in `tests/*.py`.

The only match for "HACK" was in a test docstring referencing `HACKING.md` (a filename, not a code quality marker):
- `test_pipeline_scripts.py:1137` -- docstring: "No DEVELOPMENT.md / CONTRIBUTING.md / HACKING.md -- value is None."

---

## 4. Commented-Out Tests

**None found.** Searched for `# *def test_` patterns across all test files. No test methods are commented out.

---

## 5. Weak Assertions

**None found.** The only `assert True` match is in `test_pipeline_scripts.py:909`, which is a fixture string being written to a file for testing (not an actual assertion):
```python
"def test_create_widget():\n    assert True\n", encoding="utf-8",
```
This creates a mock test file to verify the test coverage scanner can detect test functions.

No `assertTrue(True)` calls found.

---

## 6. `# noqa` Suppressions

| File | Lines | Suppression |
|------|-------|-------------|
| `test_hexwise_setup.py` | 23-25, 28-29 | `# noqa: E402` (5 instances) |
| `test_golden_run.py` | 30-31, 34-36, 39-41 | `# noqa: E402` (8 instances) |

All are `E402` suppressions (module-level import not at top of file). These are necessary because test files do `sys.path.insert()` before importing project modules, which requires the path manipulation to come before the imports. This is the standard pattern throughout the project and is architecturally intentional, not a code smell.

---

## 7. Test Methods Referencing "skip" in Names or Logic

Several test methods have "skip" in their names or assertions, but these are testing skip *behavior* in the production code, not skipping tests:

| File | Line | What it tests |
|------|------|---------------|
| `test_validate_anchors.py` | 246 | `test_fix_skips_existing_anchor` -- verifies fix mode doesn't duplicate existing anchors |
| `test_gh_interactions.py` | 1082, 1099, 1164, 1287 | Tests that monitor/check functions report "skipped" items correctly |
| `test_gh_interactions.py` | 1105 | Tests that list responses add warnings instead of silently skipping |
| `test_gh_interactions.py` | 1472 | `test_skips_missing_file` -- verifies graceful handling of missing files |
| `test_sync_backlog.py` | 46 | `test_missing_file_skipped` -- verifies missing milestone files are handled |
| `test_sync_backlog.py` | 137 | Tests debounce/throttle: recent sync causes skip |
| `test_release_gate.py` | 1084-1085 | `test_non_semver_tags_skipped` -- verifies non-semver tags are ignored |
| `test_sprint_teardown.py` | 309, 357, 395 | Tests that teardown skips certain files/dirs correctly |

---

## 8. Summary

| Category | Count | Risk |
|----------|------:|------|
| Runtime skips (`skipTest`) | 1 | Low -- intentional, documented |
| Decorator skips (`@skip`) | 0 | -- |
| TODO markers (actual deferred work) | 0 | -- |
| FIXME / HACK / XXX | 0 | -- |
| Commented-out tests | 0 | -- |
| Weak assertions | 0 | -- |
| `# noqa` suppressions | 13 | Low -- all E402, architecturally required |

**Verdict:** The test suite is remarkably clean. No deferred work, no disabled tests, no hacks. The only skip is intentional and well-documented. This is a positive signal for code quality -- any bugs that exist are likely logic errors or edge cases, not areas where testing was knowingly deferred.
