# Test Theater Audit

Systematic review of every `tests/test_*.py` file for tests that look like they
test something but do not actually catch bugs.

---

## Anti-pattern 1: Mock-Returns-What-You-Assert

Tests that mock a function to return X, then assert the result is X.
This tests the mock wiring, not the production code.

### MonitoredMock / patch_gh Effectiveness Assessment

The `gh_test_helpers.MonitoredMock` + `patch_gh` context manager is a clever
countermeasure. It warns when a mock is called but `call_args` is never
inspected. However:

- **It only emits a warning, not a failure.** Unless the test runner is
  configured with `warnings.simplefilter("error")`, these warnings scroll
  past silently. The tests in `test_bugfix_regression.py::TestPatchGhHelper`
  verify the warning mechanism works, but nothing enforces it suite-wide.
- **Adoption is extremely low.** `patch_gh` is used in exactly 6 test methods
  (all in `test_bugfix_regression.py`). The other ~30 `@patch("...gh_json")`
  call sites across `test_sprint_runtime.py`, `test_gh_interactions.py`, and
  `test_release_gate.py` use raw `unittest.mock.patch` with no call-args
  verification. The tool exists but nobody uses it.
- **Severity: MEDIUM.** The mechanism is sound in theory but effectively
  inert. A bug in how `gh_json` is called (wrong args, wrong flags) would
  not be caught by most tests.

### Specific Instances

#### 1. `test_sprint_runtime.py::TestCheckCI::test_no_runs`
- **Lines 41-45.** Mocks `check_status.gh_json` to return `[]`, then asserts
  the report contains "no recent runs". The test verifies the empty-list
  display path works but does not verify the mock was called with the right
  arguments (e.g., correct `--json` fields, correct `run list` subcommand).
  `call_args` is only checked in the `test_all_passing` sibling (line 57-59)
  but not here.
- **Bug that survives:** If `check_ci()` queried the wrong endpoint
  (e.g., `pr list` instead of `run list`), this test would still pass
  because the mock intercepts all calls.
- **Severity: LOW** -- the happy-path sibling does check call_args.

#### 2. `test_sprint_runtime.py::TestCheckPRs::test_no_prs`
- **Line 79-82.** Mocks `gh_json` to return `[]`, asserts "none open".
  No call_args verification.
- **Severity: LOW** -- same pattern, sibling tests do verify.

#### 3. `test_gh_interactions.py::TestGateCI::test_no_runs`
- **Lines 344-348.** `mock_gh.return_value = []`, then `ok, detail = gate_ci(...)`,
  then `self.assertFalse(ok)`. The mock returns empty list, the function says
  "no CI runs found" and returns False. This is testing the interpretation of
  an empty list, which is fine. But no call_args check on this specific test.
  The sibling `test_passing` (line 319-329) does check call_args, so the
  coverage gap is narrow.
- **Severity: LOW.**

#### 4. `test_sprint_runtime.py::TestFindMilestoneTitle::test_finds_sprint`
- **Lines 461-465.** Mocks `find_milestone` to return a dict with
  `title: "Sprint 1: Walking Skeleton"`, then asserts the result is that
  exact title string. `find_milestone_title()` is a thin pass-through wrapper,
  so this literally tests `return result["title"]`. The mock returns a dict,
  the function extracts `["title"]`, the test asserts it matches.
- **Bug that survives:** If `find_milestone_title` had a typo like
  `result["titl"]` it would fail, so it does catch *something*. But the
  coverage is paper-thin -- it cannot catch bugs in query construction
  because `find_milestone` is fully mocked.
- **Severity: LOW** -- it's testing a one-line wrapper.

---

## Anti-pattern 2: Tautological Assertions

### 5. `test_hexwise_setup.py::TestHexwiseSetup::test_scanner_finds_rules_and_dev`
- **Lines 103-104.** `self.assertIsNotNone(self.scan.rules_file.value)` and
  `self.assertIsNotNone(self.scan.dev_guide.value)`. These test that the
  scanner found *something*, but the fixture always has these files. The
  lines 106-107 (added by BH-013) do check the actual path content, which
  redeems this somewhat.
- **Severity: LOW** -- the follow-up assertions add real value.

### 6. `test_hexwise_setup.py::TestHexwiseSetup::test_scanner_detects_hexwise_deep_docs`
- **Lines 166-170.** Five `assertIsNotNone` checks on scan results. These
  are structural existence checks that will always pass as long as the fixture
  is intact. Lines 172-174 (BH-013) add path content checks, but only for 3
  of the 5 fields. `test_plan_dir` and `story_map` are only checked for
  not-None.
- **Bug that survives:** If the scanner returned a bogus path for
  `test_plan_dir`, the assertIsNotNone would still pass.
- **Severity: LOW** -- the fixture is the real source of truth here.

### 7. `test_bugfix_regression.py::TestCheckStatusImportGuard::test_import_guard_uses_import_error`
- **Lines 72-79.** Tests `hasattr(check_status, 'main')`,
  `hasattr(check_status, 'check_ci')`, `callable(check_status.main)`.
  These are tautologically true because `check_status` was already imported
  at line 34. If the import failed, the entire test module would fail to load.
  The BH-020 comment says this "replaced source-code inspection with
  behavioral test" but the behavioral test is vacuous -- it tests that the
  import succeeded, which is guaranteed by the test file's own import.
- **Bug that survives:** If the import guard caught `Exception` instead of
  `ImportError` (swallowing real bugs), this test would not detect it.
- **Severity: MEDIUM** -- this test creates false confidence about a real
  design decision (ImportError vs Exception).

---

## Anti-pattern 3: Missing Negative Tests

### 8. `test_sprint_analytics.py::TestComputeVelocity` -- no error path test
- Tests cover all-closed, partial-delivery, and malformed labels, but there
  is no test for what happens when `gh_json` raises a `RuntimeError` (e.g.,
  auth failure, network timeout). `compute_velocity` calls `gh_json` --
  does it let the exception propagate, or does it return a zeroed result?
  No test answers this question.
- **Severity: MEDIUM** -- a real runtime failure path is uncovered.

### 9. `test_sprint_analytics.py::TestComputeWorkload` -- no error path test
- Same gap: no test for `gh_json` failure during `compute_workload`.
- **Severity: LOW** -- less critical function.

### 10. `test_sprint_teardown.py::TestRemoveGenerated` -- no Permission Error test
- `remove_generated` deletes files. There is no test for what happens when
  a file is read-only or locked. The function presumably raises an OSError
  but there is no test proving it handles it gracefully or propagates it
  with a useful message.
- **Severity: LOW** -- edge case, unlikely in practice.

### 11. `test_sync_backlog.py::TestDoSync` -- no gh_json failure test
- `do_sync` calls `bootstrap_github` and `populate_issues` which both call
  `gh_json`. There is no test for partial failure (e.g., milestones created
  but issue creation fails). The BH-021 regression test
  (`TestBH021SyncBacklogPartialFailure`) exists but only tests state file
  persistence, not actual `do_sync` error propagation.
- **Severity: MEDIUM** -- partial sync failures are a real operational risk.

### 12. `test_release_gate.py::TestDoRelease` -- no `calculate_version` exception test
- Tests cover tag failure, commit failure, push failure, dry run. But there
  is no test for what happens when `calculate_version()` itself raises an
  exception (e.g., git not available). The function is mocked in every test,
  so the exception path through `do_release` is never exercised.
- **Severity: LOW** -- unlikely in practice, and the mock setup explicitly
  avoids this path.

---

## Anti-pattern 4: Coverage Without Conviction

### 13. `test_lifecycle.py::TestLifecycle::test_14_monitoring_pipeline` -- burndown content spot-check only
- **Lines 415-420.** Asserts `bd_path.exists()` and checks for "Sprint 1
  Burndown", "Completed: 8 SP", "Remaining: 5 SP" in the text. But it does
  NOT verify the table rows contain the actual story IDs (US-0101 through
  US-0104) or their individual statuses. A bug in `build_rows` that
  collapsed all stories into one row would pass this test.
- **Severity: MEDIUM** -- the burndown table structure is a real output
  artifact that should be verified.

### 14. `test_lifecycle.py::TestLifecycle::test_13_full_pipeline` -- count-only assertions
- **Lines 316-321.** Only asserts `>= 15 labels`, `== 1 milestone`,
  `== 2 issues`. As the docstring itself acknowledges, "assertions are
  intentionally loose." This cannot catch a regression where labels are
  created with wrong names, milestones get wrong titles, or issues get
  wrong bodies.
- **Severity: LOW** -- the docstring is honest about scope, and
  `test_hexwise_setup` and `test_golden_run` cover the same pipeline
  with stricter checks. This test is the "canary" version.

### 15. `test_sprint_runtime.py::TestCreateLabel::test_creates_label`
- **Lines 121-130.** Mocks `bootstrap_github.gh` to return `""`,
  calls `create_label(...)`, then asserts `mock_gh.assert_called_once()`
  and checks the call args contain "label", "create", and the label name.
  This is actually decent -- it verifies the correct gh command is
  constructed. But it does NOT verify the color or description arguments.
  A bug that dropped the color parameter would pass.
- **Severity: LOW** -- the FakeGitHub-backed tests in
  `TestBootstrapStaticLabelsIdempotent` provide deeper coverage.

### 16. `test_bugfix_regression.py::TestBH021SyncBacklogPartialFailure::test_state_not_updated_on_do_sync_failure`
- **Lines 1169-1181.** The test name says "state not updated on do_sync
  failure" but the test body never actually calls `do_sync` or triggers a
  failure. It just saves state, loads it back, and checks it roundtrips.
  This is a state file roundtrip test masquerading as a partial-failure test.
- **Bug that survives:** If `do_sync` updated `file_hashes` before throwing,
  this test would not detect it because it never calls `do_sync`.
- **Severity: HIGH** -- the test name and docstring promise failure-path
  coverage that does not exist. The BH-021 bug fix is effectively untested.

---

## Anti-pattern 5: Fixture Dependency

### 17. `test_hexwise_setup.py` -- entire class depends on fixture file counts
- `test_scanner_finds_personas`: asserts `len == 4` (3 devs + giles).
  `test_scanner_finds_milestones`: asserts `len == 3`.
  `test_config_has_three_milestones`: asserts `len(md_files) == 3`.
  `test_full_setup_pipeline`: asserts exactly 17 issues.
  All of these are hardcoded to the current hexwise fixture. Adding a
  4th milestone or 18th story to the fixture breaks these tests even
  though the code is correct.
- **Severity: LOW** -- fixture-coupled tests are normal for integration
  tests. The key question is whether the fixture is considered stable,
  and for hexwise it appears to be.

### 18. `test_golden_run.py` -- golden snapshot dependency
- The test skips if golden recordings are absent (non-CI) or fails if
  absent in CI. This is well-handled by the `_check_or_record` method.
  Not really theater, but worth noting: in local dev without `GOLDEN_RECORD=1`
  having been run, this test always skips, providing zero coverage.
- **Severity: LOW** -- by design, and the skip message is clear.

---

## Anti-pattern 6: Self-Fulfilling Prophecy Tests

### 19. `test_bugfix_regression.py::TestP17SyncTrackingWritePersistence::test_sync_writes_status_change_to_disk`
- **Lines 1223-1247.** Creates a tracking file with `status: dev`, creates
  an issue dict with `state: "closed"` and `labels: [kanban:done]`, calls
  `sync_one(tf, issue, ...)`, then calls `write_tf(tf)`, then reads back
  from disk and asserts `status: done`.
- This test IS valuable -- it verifies the write-to-disk path that a pure
  in-memory test would miss. The BH-002 annotation confirms this was a real
  bug (changes computed but not persisted). Not theater.
- **Severity: N/A** -- false positive, this is a good test.

### 20. `test_bugfix_regression.py::TestP17YamlSafeRoundtrip::test_title_with_colon_roundtrips`
- **Lines 1253-1263.** Writes a TF with a colon-containing title, reads it
  back, asserts the title matches. This tests the write/read roundtrip for
  YAML edge cases.
- This is valid -- it caught BH-003 where colons in titles corrupted the
  YAML. Not theater.
- **Severity: N/A** -- false positive, this is a good test.

### 21. `test_sprint_runtime.py::TestSyncOne::test_no_changes_when_in_sync`
- **Lines 1288-1295.** Creates a TF with `status: todo`, creates an issue
  with `state: "open"` and no kanban labels, calls `sync_one`, asserts
  `changes == []`. The test constructs a scenario where the TF and issue
  agree, then asserts no changes.
- This could be theater IF the function always returned `[]`. But the
  siblings (`test_closed_issue_updates_status`, `test_label_sync_updates_status`)
  prove the function does return changes in other cases. So this test
  is the "no-op path" test, which is valuable.
- **Severity: N/A** -- false positive.

---

## Summary by Severity

| Severity | Count | Key Findings |
|----------|-------|-------------|
| HIGH     | 1     | #16: BH-021 partial-failure test never calls do_sync |
| MEDIUM   | 4     | MonitoredMock adoption gap; missing gh_json error-path tests for velocity/backlog; burndown content not verified; import guard test vacuous |
| LOW      | 12    | Various call_args gaps covered by sibling tests; fixture coupling; assertIsNotNone on known-present values; count-only assertions |

## Recommendations (not fixes -- just observations)

1. **The biggest gap is #16** -- `TestBH021SyncBacklogPartialFailure` claims
   to test partial failure but does not exercise the failure path at all.
   Any confidence drawn from this test about BH-021 is false.

2. **MonitoredMock/patch_gh exists but is unused** by 80%+ of the mock-gh
   tests. Either adopt it suite-wide or accept that call-args verification
   is optional. The current state gives a false sense of protection.

3. **Error-path coverage for gh_json callers** is consistently missing.
   Functions like `compute_velocity`, `compute_workload`, and `do_sync` all
   call `gh_json` but no test verifies their behavior when `gh_json` raises
   RuntimeError.

4. **The test suite is actually quite good overall.** Most of what I flagged
   is LOW severity. The property-based tests (`test_property_parsing.py`)
   are exemplary. The FakeGitHub infrastructure is thorough. The regression
   tests have good bug-ID traceability. The real risk is concentrated in
   the few MEDIUM/HIGH items above.
