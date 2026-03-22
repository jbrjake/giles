# Phase 2: Test Quality Audit — BH38

**Date:** 2026-03-21
**Scope:** 14 test files affected by ruff cleanup (commit 65636ca), prioritized by churn.
**Baseline:** 1182 tests passing, 83% coverage.

## Summary

| Category | Count |
|----------|-------|
| Findings total | 12 |
| HIGH severity | 1 |
| MEDIUM severity | 6 |
| LOW severity | 5 |
| Ruff-weakened tests | 0 |

### Ruff Cleanup Verdict

The ruff commit (65636ca) removed unused imports and variables from 14 test files. **No test was weakened.** Every removed import was genuinely unused (not referenced in any assertion or setup). The removed variables (`changes`, `config`, `fake`, `fake_gh`, `call_count`, `title_idx`) were all return values captured but never checked — the assertions in those tests operate on other state (file contents, tf attributes, mock call_args). The ruff cleanup was safe.

---

## Findings

### BH38-100 — Tautological assertion: `assertTrue(len(output) >= 0)`
**Severity:** HIGH
**File:** tests/test_verify_fixes.py:1255
**Phase:** Phase 2 (test quality)
**Description:** `self.assertTrue(len(output) >= 0)` is always true — `len()` can never return a negative number. This assertion provides zero signal. The comment says "at minimum, no crash" but the test would already fail with an exception if the code crashed. The follow-up assertion `assertNotIn("Traceback", output)` provides some value but is also weak — it only checks for Python tracebacks, not other error types. This test (`TestTeamVoicesMainHappyPath.test_runs_with_no_voices`) should assert something meaningful about the output content.

### BH38-101 — Weak assertion pattern: `assertTrue(result)` on bool returns
**Severity:** MEDIUM
**File:** tests/test_kanban.py (lines 438, 536, 565, 608, 622, 636, 751, 822, 969, 984, 1005, 1030, 1057), tests/test_release_gate.py (lines 706, 929, 1173, 1318), tests/test_new_scripts.py:339, tests/test_pipeline_scripts.py (lines 386, 2038)
**Phase:** Phase 2 (test quality)
**Description:** Twenty-one tests use `self.assertTrue(result)` to check a bool return value. While not incorrect (these functions return True/False), `self.assertIs(result, True)` is strictly more precise — `assertTrue` passes for any truthy value including non-empty strings, non-zero integers, or non-empty lists. In most cases the tests also check other state (file contents, mock calls), so this is a style issue rather than a correctness risk. The kanban tests are the worst offenders with 13 instances.

### BH38-102 — Weak assertions: `assertTrue(len(x) > 0)` instead of assertGreater
**Severity:** LOW
**File:** tests/test_verify_fixes.py (lines 84, 144, 620, 2022, 2041), tests/test_sprint_runtime.py (lines 75, 161, 1176, 1311, 1329, 1386, 1534, 1560), tests/test_gh_interactions.py (lines 368, 388)
**Phase:** Phase 2 (test quality)
**Description:** Fifteen tests use `assertTrue(len(x) > 0)` or `assertTrue(len(x) >= 1)` where `assertGreater(len(x), 0)` or `assertGreaterEqual(len(x), 1)` would produce better failure messages. The current form shows "AssertionError: False is not true" on failure instead of "AssertionError: 0 not greater than 0". This makes debugging harder. Note: `test_verify_fixes.py:1255` is the special case (BH38-100 above) where the assertion is always true.

### BH38-103 — Assertion-light lock tests rely only on "no exception"
**Severity:** MEDIUM
**File:** tests/test_kanban.py:278-296
**Phase:** Phase 2 (test quality)
**Description:** `test_lock_story_acquires_and_releases` and `test_lock_sprint_acquires_and_releases` each acquire a lock, execute `pass`, release, and re-acquire. The only assertion is implicit: "no deadlock occurred." While this is a valid behavioral test (the test would hang if locking failed), there is no positive assertion — no check that the lock file was created, no check that concurrent access is serialized (that test exists separately at line 306), and no check that the lock file is cleaned up after release. The companion test `test_lock_sprint_creates_lock_file` (line 298) covers lock file existence, but cleanup verification is missing entirely.

### BH38-104 — Test isolation: 101 os.chdir calls across 10 test files
**Severity:** MEDIUM
**File:** tests/test_hooks.py (31), tests/test_verify_fixes.py (29), tests/test_release_gate.py (13), tests/test_sprint_teardown.py (6), tests/test_sync_backlog.py (6), tests/test_hexwise_setup.py (5), tests/test_bugfix_regression.py (4), tests/test_lifecycle.py (3), tests/test_sprint_analytics.py (2), tests/test_golden_run.py (2)
**Phase:** Phase 2 (test quality)
**Description:** Many tests use `os.chdir()` to set up CWD-dependent behavior, protected by try/finally blocks to restore the original directory. This is a shared-state pattern that creates test isolation risk — if a test crashes before the finally block (e.g., due to a KeyboardInterrupt or segfault), subsequent tests run in the wrong directory. Most files handle this correctly with try/finally or setUp/tearDown, but test_hooks.py has 31 chdir calls spread across individual test methods rather than consolidated in setUp/tearDown. The production code's CWD dependency (hooks that call `_find_project_root()`) forces this pattern, so it's not easily fixable without refactoring the hooks themselves.

### BH38-105 — Three full-pipeline tests with documented overlap
**Severity:** LOW
**File:** tests/test_lifecycle.py:288, tests/test_hexwise_setup.py:398, tests/test_golden_run.py:121
**Phase:** Phase 2 (test quality)
**Description:** Three separate test files each run the full setup pipeline (init -> labels -> milestones -> issues). The test docstrings explicitly document how they differ: test_lifecycle uses a minimal synthetic project with loose assertions, test_hexwise_setup uses the hexwise fixture with exact counts, and test_golden_run uses the hexwise fixture with snapshot regression. This is well-documented intentional overlap, not accidental duplication. However, the three tests together take the most wall-clock time of any test category due to FakeGitHub setup overhead. No action needed, but worth noting for CI optimization.

### BH38-106 — `assertTrue(result)` masks return type on do_release
**Severity:** MEDIUM
**File:** tests/test_release_gate.py (lines 706, 929, 1173, 1318)
**Phase:** Phase 2 (test quality)
**Description:** Four `do_release()` integration tests check `self.assertTrue(result)` where `result` is the return value of `do_release()`. The function is documented to return a bool, but if it ever returned a truthy non-bool (e.g., a string like "released"), `assertTrue` would pass silently. Using `self.assertIs(result, True)` would catch type drift. More importantly, these are integration tests that mock subprocess extensively — the `assertTrue(result)` is the only assertion checking overall success. The tests do verify side effects (tags, releases, version files), but the primary success signal is weak.

### BH38-107 — Unused FakeGitHub instantiation after ruff cleanup
**Severity:** LOW
**File:** tests/test_sprint_runtime.py:2221
**Phase:** Phase 2 (test quality)
**Description:** After ruff removed the `fake = FakeGitHub()` assignment (changed to bare `FakeGitHub()`), the constructor call still executes but the instance is immediately discarded. The test then mocks `sync_tracking.gh_json` directly, bypassing FakeGitHub entirely. The `FakeGitHub()` call has no side effects on the test (it doesn't patch subprocess), so it's dead code. Not a correctness issue — just wasted computation.

### BH38-108 — Missing lock cleanup verification
**Severity:** MEDIUM
**File:** tests/test_kanban.py:275-304
**Phase:** Phase 2 (test quality)
**Description:** The `TestFileLocking` class verifies lock acquisition (test_lock_story_acquires_and_releases, test_lock_sprint_acquires_and_releases) and lock file creation (test_lock_sprint_creates_lock_file), but never verifies that the lock file is cleaned up after the context manager exits. If `lock_sprint` or `lock_story` leaked lock files, the tests would still pass. A test that checks `assertFalse(lock_file.exists())` after the `with` block exits would close this gap.

### BH38-109 — No error-path testing for smoke_test.run_smoke with invalid commands
**Severity:** LOW
**File:** tests/test_new_scripts.py:25-84
**Phase:** Phase 2 (test quality)
**Description:** `TestSmokeTest` covers pass, fail, skip, timeout, and history writing, but does not test what happens when the command itself is invalid (e.g., `run_smoke("nonexistent_binary_xyz")`). If `subprocess.run` raises `FileNotFoundError`, `run_smoke` should handle it gracefully. This is a missing error-path test, not a bug in existing tests.

### BH38-110 — `test_config_error_does_not_raise_system_exit` uses bare except-like pattern
**Severity:** LOW
**File:** tests/test_verify_fixes.py:263-270
**Phase:** Phase 2 (test quality)
**Description:** The test uses try/except with `except SystemExit: self.fail(...)` followed by `except ConfigError: pass`. While not technically a bare except, the pattern is fragile — if `load_config` raises a *subclass* of ConfigError that also inherits from SystemExit (unlikely but possible), the test would incorrectly fail. The test already has a companion (`test_config_error_is_value_error`) that verifies the exception hierarchy. A cleaner approach would be `assertRaises(ConfigError)` with a separate `assertNotRaises(SystemExit)` check, but the current implementation is functionally correct.

### BH38-111 — Mock-heavy do_release tests rely on subprocess patching fidelity
**Severity:** MEDIUM
**File:** tests/test_release_gate.py (TestDoRelease, TestDoReleaseDryRun, TestDoReleaseIntegration — lines ~650-1700)
**Phase:** Phase 2 (test quality)
**Description:** The `do_release()` test classes mock subprocess.run extensively, simulating git tag, git push, git commit, and gh release create. The mock implementations in `_make_side_effect()` and `_mock_subprocess_run()` are 30-50 lines each and replicate significant git behavior. If the mock diverges from real git behavior (e.g., git changes its exit code or output format), the tests pass while production breaks. This is the highest mock density in the test suite. The risk is partially mitigated by `TestDoReleaseIntegration` which runs with real git (only mocking gh), but the core `TestDoRelease` class is pure mock.

---

## Anti-Pattern Summary

| Anti-Pattern | Instances | Severity |
|---|---|---|
| Tautological assertion | 1 (BH38-100) | HIGH |
| Weak `assertTrue(result)` | 21 instances across 5 files (BH38-101) | MEDIUM |
| Weak `assertTrue(len(x) > 0)` | 15 instances across 4 files (BH38-102) | LOW |
| Assertion-light tests | 2 lock tests (BH38-103) | MEDIUM |
| Test isolation (os.chdir) | 101 calls in 10 files (BH38-104) | MEDIUM |
| Documented pipeline overlap | 3 tests (BH38-105) | LOW |
| Mock-heavy integration tests | ~6 do_release tests (BH38-111) | MEDIUM |
| Dead code after ruff cleanup | 1 instance (BH38-107) | LOW |
| Missing cleanup verification | 1 gap (BH38-108) | MEDIUM |
| Missing error-path test | 1 gap (BH38-109) | LOW |
| Fragile exception test | 1 instance (BH38-110) | LOW |
| `assertTrue` masking type | 4 do_release tests (BH38-106) | MEDIUM |

## What Was NOT Found

- **No assertion-free tests.** Every test has at least one assertion (or relies on `assertRaises`/implicit deadlock detection).
- **No bare except or overly broad try/except.** Grep for `except:` and `except Exception:` returned zero matches in test files.
- **No tautological `assertEqual(x, x)`.** The `assertEqual` calls all compare different variables.
- **No test execution order dependencies.** Tests use setUp/tearDown and tempdir isolation correctly.
- **No ruff-weakened tests.** All removed imports/variables were genuinely unused.
