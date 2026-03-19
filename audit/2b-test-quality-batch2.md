# Test Quality Audit — Batch 2

Adversarial review of five test files. Findings organized per-file, then cross-cutting.

---

## 1. tests/test_gh_interactions.py

### 1.1 Inspector Clouseau: TestGateStories verifies mock call_args instead of behavior

**Lines 299-325.** Both `test_all_closed` and `test_open_issues` spend most of their assertion budget verifying `mock_gh.call_args` — checking that `"--milestone"`, `"Sprint 1"`, and `"--state"` appear in the arguments. These are contract tests on how `gate_stories` talks to `gh_json`, not tests of what `gate_stories` does with the response. The actual behavioral assertions (`assertTrue(ok)`, `assertIn("closed", detail.lower())`) are thin.

The same pattern appears in `TestGateCI` (lines 336-339, 349-350) and `TestGatePRs` (lines 367-368). Half the test body is call_args verification.

**Severity:** Low. The call_args checks were added intentionally (BH-P11-052/053 tags). They provide value as contract tests, but they make the tests fragile to refactoring (e.g., if someone reorders CLI arguments, tests break even though behavior is correct).

### 1.2 Happy Path Tourist: gate_prs missing edge cases

**Lines 360-401.** `TestGatePRs` has four tests but misses:
- PR with `milestone: None` (null milestone, not missing key) — real GitHub returns `null` for PRs without milestones.
- PR with `milestone: {"title": ""}` — empty title edge case.
- The truncation test (line 392) returns 500 PRs with `milestone: None`, but never tests the case where the 500-limit truncation hides a milestone-matching PR that would have been caught if the query returned more results. The current test just checks that the gate fails on truncation, not that the error message is actionable.

**Severity:** Low. The truncation gate is conservative (fails on 500), so false-passes are unlikely.

### 1.3 Mockingbird: TestCheckAtomicity never runs real git

**Lines 81-138.** Every `check_atomicity` test mocks `subprocess.run`. The function under test has exactly one interesting behavior: parsing `git diff --cached --name-only` output and counting directories. The mock provides perfectly formatted output, so the test never verifies that the function correctly handles real git output (trailing newlines, empty lines between filenames, git error output in stderr with non-zero returncode).

**Severity:** Low. The function is simple enough that the mocks are probably fine, but there is no integration test that runs `check_atomicity` against a real git repo.

### 1.4 Green Bar Addict: test_valid_fix_with_scope doesn't check err

**Line 40-41.** `test_valid_fix_with_scope` asserts `ok` is `True` but never checks that `err` is empty. If the function returned `(True, "some warning")`, this test would pass. Compare with `test_valid_feat` (line 35-37) which correctly asserts both `ok` and `err`.

**Severity:** Negligible. The function only returns `err=""` on success, but the test is less thorough than its neighbors.

### 1.5 Happy Path Tourist: TestDetermineBump has no test for empty commits list

**Lines 144-188.** What happens when `determine_bump([])` is called with no commits? Looking at the source (release_gate.py line 88), it returns `"patch"` because `bump` starts at `"patch"` and the loop never runs. This default behavior is never tested. The caller (`calculate_version`, line 130) returns early with `bump_type == "none"` when no commits exist, but the separate unit test doesn't exercise the empty-list path.

**Severity:** Low. The edge case is handled by the caller, but `determine_bump` itself lacks coverage.

### 1.6 Fragile: TestGenerateReleaseNotes depends on git tag existence

**Lines 403-425.** `test_basic_notes` creates commits and passes `"0.1.0"` as `prev_version`, but the test environment has no `v0.1.0` git tag. The function then falls through to the "initial release" path (`tag_check.returncode != 0`). The test asserts `assertIn("## Full Changelog", notes)` which passes for both the compare-link path AND the initial-release path. The comment on line 415 acknowledges this: "In test env the prior tag doesn't exist, so we get initial release text." This means the test is not actually verifying the compare-link generation path at all.

The lifecycle test `test_09b_release_notes_compare_link` (test_lifecycle.py line 247) does cover this with a real tag, so the gap has been filled elsewhere. But this test gives a false sense of coverage.

**Severity:** Low. Coverage exists elsewhere but the test title and assertions are misleading about what path is exercised.

---

## 2. tests/test_sprint_runtime.py

### 2.1 Inspector Clouseau: TestCheckCI.test_failing_run_log_uses_database_id

**Lines 81-89.** `test_failing_run_log_uses_database_id` asserts `self.assertIn("42", str(mock_gh.call_args))`. This checks that the string "42" appears somewhere in the stringified call_args. If the mock was called with any argument containing "42" (e.g., a URL with "42" in it, or a limit of "42"), this would also pass. The test is nominally tagged BH23-102 as a "contract test" but it uses `str()` conversion which is fragile and imprecise.

**Severity:** Low-Medium. A more robust assertion would check the actual positional arguments list for the expected run ID.

### 2.2 Happy Path Tourist: TestCreateLabel.test_label_error_handled — no error path diversity

**Lines 180-192.** The "error handled" test only tests one error message: `"already exists"`. The `create_label` function catches `RuntimeError` and prints a warning. But what about:
- `gh()` raising a different `RuntimeError` (e.g., "auth failed", "network timeout")?
- Does the function re-raise or truly swallow all errors?

The test verifies the specific case but doesn't test that ALL errors are gracefully handled — it only tests `RuntimeError`. If `gh()` raised `OSError` or `subprocess.CalledProcessError`, the behavior is unknown.

**Severity:** Low. The function only catches `RuntimeError` from `gh()`, which is the only exception type that `gh()` raises (confirmed by reading `validate_config.gh()`).

### 2.3 Green Bar Addict: TestCheckBranchDivergence tests don't verify report content precisely

**Lines 1026-1103.** `test_medium_divergence` checks `assertIn("MEDIUM", report[0])` and `assertIn("15", report[0])` but doesn't verify the branch name appears in the report. `test_high_divergence` checks `assertIn("HIGH", report[0])` but the action assertion is `assertIn("25 behind", actions[0])` — never checks that the branch name is included in the action. If the code dropped the branch name from the action message, these tests would still pass.

Similarly, `test_api_error_handled` (line 1082) checks `assertIn("skipped", report[0])` and `assertIn("feat/broken", report[0])` but doesn't verify the error message is included. The source (check_status.py line 297) includes `{exc}` in the output.

**Severity:** Low. The assertions are reasonable for regression testing but leave room for information-loss regressions.

### 2.4 Rubber Stamp: TestSyncOne.test_no_changes_when_in_sync

**Lines 1348-1355.** The "no changes" test creates a TF with `status="todo"` and an issue with `state="open"` and no labels. It asserts `changes == []`. But this only works because `kanban_from_labels` returns `"todo"` when there are no kanban labels on an open issue. The test implicitly relies on this default behavior without documenting it. If someone added a default label logic, this test would break for the wrong reason.

More importantly: the test doesn't verify that the TF fields are UNCHANGED after sync. It only checks that `changes` is empty. If `sync_one` had a bug that mutated `tf.status` but forgot to add it to `changes`, this test would pass.

**Severity:** Medium. The test should assert `tf.status == "todo"` AND `tf.sprint == 1` AND `tf.issue_number == "5"` after sync to verify no mutation occurred.

### 2.5 Time Bomb: TestHours and TestAge patching strategy is fragile

**Lines 1715-1781.** These tests patch `check_status.datetime` with a `FakeDatetime` class. The patching strategy replaces the entire `datetime` class in the `check_status` module. This works because `check_status._hours()` uses `datetime.now(timezone.utc)`. However, the patch replaces `datetime` globally in the module, which means if `_hours()` also calls `datetime.fromisoformat()`, the FakeDatetime must also support that method. Since `FakeDatetime` inherits from `datetime`, this works. But if any code in `check_status` does `from datetime import datetime` at module level (import-time binding), the patch would have no effect.

The comment "BH23-106: Uses a fixed reference time to avoid wall-clock flakiness" confirms this was a known concern. The fix is sound but the strategy is brittle — any refactoring of imports in `check_status.py` could silently break the time-patching.

**Severity:** Low. The current implementation works, and the BH23-106 fix was intentional.

### 2.6 Happy Path Tourist: TestGetLinkedPr lacks test for timeline returning a single dict

**Lines 615-661.** `get_linked_pr` has a check at line 75-76 of sync_tracking.py: `if isinstance(linked, dict): linked = [linked]`. This normalizes a single dict response into a list. None of the tests exercise this path — all timeline test data returns lists. The FakeGitHub handler (fake_github.py line 473) returns a single dict via `self._ok(json.dumps(src))` in the fallback path, but the jq-enabled path returns a list. The normalization code is dead in tests.

**Severity:** Medium. The `isinstance(linked, dict)` path exists to handle a real GitHub API quirk and is never tested.

### 2.7 Potential false-pass: TestSyncOneGitHubAuthoritative spy doesn't verify subprocess args correctly

**Lines 1405-1451.** The spy function `spy_subprocess` checks `args[0] == "gh"` to detect gh CLI calls. But `sync_one()` never calls `subprocess.run` directly — it only mutates the in-memory TF object. The spy would only catch calls if `sync_one()` internally invoked `gh()` or `gh_json()`, which call `subprocess.run`. Since `sync_one()` does NOT call `gh()` (confirmed by reading the source), the spy will never capture any calls, and the assertion `gh_edit_calls == []` is tautologically true. The test LOOKS like it's verifying sync_one doesn't call GitHub, but it would pass even if you replaced `spy_subprocess` with a no-op.

**Severity:** Medium-High. The test claims to verify that `sync_one()` doesn't push state to GitHub, but the assertion is vacuously true because `sync_one()` has no code path that calls `subprocess.run`. The test should at minimum verify `mock_gh.assert_not_called()` on a patched `sync_tracking.gh` or `sync_tracking.gh_json` instead. As written, it passes BECAUSE of how the code is structured, not because it's actually testing the claimed property.

### 2.8 Fragile: TestCollectSprintNumbers.test_filename_fallback relies on temp file naming

**Lines 324-334.** `test_filename_fallback` creates a temp file with `prefix="milestone-5-"` and expects `_collect_sprint_numbers` to extract `5` from the filename. But `tempfile.NamedTemporaryFile` appends random characters to the prefix, producing names like `milestone-5-abc123.md`. The regex in the production code must be robust enough to find `5` in such a name. This is fine for testing, but the test assertion documents that the production code uses a particular regex pattern — if the pattern changes to be more strict (e.g., requiring `milestone-5.md` exactly), this test would fail even though the production use case is correct.

**Severity:** Low. The test is valid for current behavior.

### 2.9 Missing coverage: TestCheckMilestone never tests warn_if_at_limit path

**Lines 1788-1858.** `check_milestone` calls `gh_json` to get issues, then calls `warn_if_at_limit(issues, 500)`. None of the tests verify what happens when 500+ issues are returned. The `warn_if_at_limit` function is a shared helper, so it's presumably tested elsewhere, but the integration of the warning into `check_milestone` is not exercised.

**Severity:** Low. The warning is informational, not behavioral.

---

## 3. tests/test_lifecycle.py

### 3.1 Green Bar Addict: test_01 only checks boolean result, not content

**Lines 86-91.** `test_01_init_generates_valid_config` calls `validate_project()` and asserts `ok` is `True`. It never inspects what was actually generated. If `sprint_init.py` generated a valid but empty config (e.g., all required keys present but with wrong values), this test would pass. The follow-up `test_02_config_has_required_keys` partially addresses this but only checks three keys out of the many required.

**Severity:** Low. Tests 01 and 02 together provide reasonable coverage.

### 3.2 Happy Path Tourist: No error-path tests in the entire file

**Lines 1-448.** The entire `TestLifecycle` class only tests happy paths. There are no tests for:
- `sprint_init` with a project missing `Cargo.toml` (no language detection).
- `bootstrap_github` with a FakeGitHub that returns errors.
- `populate_issues.create_issue` when FakeGitHub rejects the milestone.
- `sync_tracking.sync_one` when the issue is in an unexpected state.
- `update_burndown.build_rows` when issues have no story ID.

The file is explicitly an integration test ("end-to-end lifecycle"), so error paths may be out of scope. But the docstring says "End-to-end test" without qualifying that it only covers the happy path.

**Severity:** Medium. The file tests a full pipeline but provides no confidence about failure modes.

### 3.3 Fragile: test_06 makes assumptions about MockProject story count

**Lines 148-191.** `test_06_populate_creates_issues` asserts `len(stories) == 2`. This depends on the exact content of `MockProject.create()` writing exactly two story rows in `milestone-1.md`. If someone adds a third story to the mock, this test breaks. The assertion is load-bearing on fixture internals.

**Severity:** Low. The mock is co-maintained with the test.

### 3.4 Potential false-pass: test_13 label count assertion is lower-bounded, not exact

**Lines 289-326.** `test_13_full_pipeline` asserts `assertGreaterEqual(len(self.fake_gh.labels), 17)`. The comment explains the expected 19 labels, but the assertion allows 17 or more. If label creation silently broke and only created 17 labels, the test would pass. The test explicitly notes this is intentional ("assertions are intentionally loose"), but compare with `test_hexwise_setup.test_full_setup_pipeline` which uses exact assertions.

**Severity:** Low. Documented intentional looseness.

### 3.5 Coupling: test_14_monitoring_pipeline manually seeds FakeGitHub state

**Lines 329-444.** This test manually constructs `self.fake_gh.issues` and `self.fake_gh.milestones` rather than using the bootstrap pipeline. This means the FakeGitHub state may not match what the real pipeline would produce. For example, the manually constructed issues lack a `"body"` key for some items (line 369: `"body": ""`), and labels use a simplified structure. If the production code changed to expect additional fields on issues (e.g., `assignees`, `comments_count`), this test would need manual updating.

**Severity:** Low. This is a trade-off for test isolation, and the test tests the monitoring pipeline, not the bootstrap pipeline.

### 3.6 Green Bar Addict: test_14 phase 3 only checks 2 values in the report

**Lines 437-444.** Phase 3 (`check_milestone`) asserts `"2/4"` and `"50%"` and `"8/13 SP"` in the report text. These assertions verify the output format but don't verify the actual computation path — the test manually seeded 4 issues (2 closed, 2 open) with known SP values, so the expected output is just arithmetic on the test data. The test verifies formatting, not logic.

**Severity:** Low. The logic is simple enough that format verification is sufficient.

---

## 4. tests/test_golden_run.py

### 4.1 Silent degradation: _check_or_record silently skips when recordings are absent

**Lines 93-119.** When `replayer.has_recordings()` returns `False` and the test is not in CI, `_check_or_record` calls `self.skipTest()`. This means the golden run test contributes ZERO assertions when recordings are missing. The BH-P11-051 fix added `self.fail()` in CI, but locally the test silently skips. If a developer deletes the golden recordings directory, all golden assertions vanish and `pytest` reports skips, which are easy to miss.

**Severity:** Medium. The `warnings.warn()` call helps, but `skipTest` output can be buried in a long test run.

### 4.2 Green Bar Addict: Phase 2 assertion is just "more than 10 labels"

**Line 165.** `self.assertGreater(len(self.fake_gh.labels), 10)` — this is a sanity check, not a correctness check. The golden replay comparison (`assert_labels_match`) is the real assertion, but it only runs when recordings exist. So in record mode or when recordings are absent, the only assertion is "> 10 labels."

**Severity:** Low. The golden replay provides the real depth; the inline assertion is a safety net.

### 4.3 Fragile: TestAssertFilesMatchAdversarial tests the replayer, not the production code

**Lines 215-268.** These tests verify that `GoldenReplayer.assert_files_match()` can detect mismatches. This is testing test infrastructure, not production code. While valuable, these tests are fragile in that they depend on the internal diff format of the replayer (e.g., `"Content mismatch"` string, `"recording but not on disk"` string). If the replayer changes its diff format, these tests break.

**Severity:** Low. Testing test infrastructure is a good practice; the string matching is the standard approach.

### 4.4 Missing coverage: No test that golden recordings are actually read and compared

There is no test that verifies the golden replay path produces meaningful diffs when the PRODUCTION CODE changes (as opposed to when the test INFRASTRUCTURE is broken). The adversarial tests (4.3 above) verify the replayer can detect synthetic mismatches, but there's no test that breaks a real production function and verifies the golden snapshot catches it.

**Severity:** Low-Medium. The golden replay concept relies on the assumption that `assert_files_match` / `assert_labels_match` / `assert_issues_match` are correct. The adversarial tests partially cover this.

### 4.5 Coupling: CI workflow assertions are hardcoded

**Lines 196-199.** The golden run asserts `"cargo test"`, `"cargo clippy"`, `"permissions:"`, and `"actions/checkout@v6"` in the generated CI YAML. These are correct for the hexwise fixture (a Rust project), but if the CI template changes (e.g., bumping to `@v7`), this test breaks even though the golden recording should catch the diff. The inline assertions duplicate what the golden snapshot would catch.

**Severity:** Negligible. Redundant assertions are harmless.

---

## 5. tests/test_fakegithub_fidelity.py

### 5.1 Green Bar Addict: TestTimelineJqExpression.test_jq_expression_filters_correctly doesn't verify field contents

**Lines 76-84.** The test verifies that the jq expression returns 2 results with numbers {42, 55}. But it doesn't verify that the returned objects have the correct structure (e.g., `state`, `pull_request` fields). The production code (sync_tracking.py line 96-102) accesses `.get("state")`, `.get("pull_request", {}).get("merged_at")`, and `.get("number")` on the results. If the jq expression returned objects with different structure, the test would pass but the production code would get `None` values.

**Severity:** Medium. The test verifies filtering but not the shape of the filtered results.

### 5.2 Rubber Stamp: TestSearchPredicateWarning.test_milestone_only_no_warning

**Lines 133-148.** This test checks that a milestone-only search produces no warnings. But it also asserts `result.returncode == 0`, which is trivially true because FakeGitHub._pr_list always returns `self._ok(...)`. The test should also verify that the returned data contains the matching PR (PR1 with milestone "Sprint 1"). Currently, the test could pass even if the search predicate was completely ignored and all PRs were returned unfiltered.

**Severity:** Medium. The test verifies warning behavior but not filtering behavior.

### 5.3 Happy Path Tourist: TestMilestoneCounters has no test for reopening issues

**Lines 170-233.** The tests cover create, close, and full lifecycle. But there's no test for reopening a closed issue. Real GitHub allows `gh issue reopen`. If FakeGitHub doesn't implement reopen (it doesn't — there's no `reopen` handler), then any production code that reopens issues would get an error. This is a missing FakeGitHub capability, not just a missing test.

**Severity:** Low. Reopening issues is not a common production code path in giles.

### 5.4 Missing: TestMilestoneCounters doesn't verify counter-after-edit-milestone

**Lines 170-233.** When an issue's milestone is changed via `issue edit --milestone "Sprint 2"`, the counters on both the old and new milestone should update. FakeGitHub implements this (fake_github.py lines 640-653), but there's no test for it. Only the `issue create` and `issue close` paths have counter tests.

**Severity:** Medium. The milestone reassignment counter logic (BH19-006) was implemented but has no dedicated test.

### 5.5 Green Bar Addict: TestReleaseCreateFidelity.test_release_create_returns_url

**Lines 292-301.** The test asserts `assertIsInstance(result.stdout, str)` and `assertIn("v1.0.0", result.stdout)`. It doesn't verify the URL format, that it contains the expected repo path, or that the returncode is 0. The `assertIsInstance(result.stdout, str)` is tautological — `subprocess.CompletedProcess.stdout` is always a string when `text=True` is used.

**Severity:** Low. The test is thin but the release create path is simple.

### 5.6 Missing: No test for FakeGitHub jq fallback behavior mismatch

The FakeGitHub has two code paths for jq handling: with-jq (line 466-468) and without-jq (lines 469-474). `test_fakegithub_jq_matches_manual_filter` (line 100) tests the with-jq path. But there's no test that verifies the WITHOUT-jq fallback path produces the same result. If jq is always available in the test environment, the fallback path is dead code.

**Severity:** Medium. The fallback path exists for environments without the `jq` package but is never tested because the test environment has `jq` installed (it's a dev dependency enforced by conftest.py).

---

## Cross-Cutting Findings

### C.1 Mockingbird pattern: gh_json mocks prevent FakeGitHub from running

Many tests in `test_sprint_runtime.py` use `@patch("module.gh_json")` to mock the JSON query layer. This means the FakeGitHub dispatch logic, flag parsing, response filtering, and JSON field filtering are all bypassed. Examples:
- `TestCheckCI` (lines 37-89) — 5 tests all mock `check_status.gh_json`
- `TestCheckPRs` (lines 92-157) — 4 tests mock `check_status.gh_json`
- `TestGateStories` in test_gh_interactions.py (lines 297-325)
- `TestGetLinkedPr` (lines 615-661) — mocks `sync_tracking.gh_json`

Meanwhile, a parallel set of tests (`TestCheckBranchDivergenceFakeGH`, `TestCheckDirectPushesFakeGH`) use FakeGitHub directly. The inconsistency means some code paths are tested with mocks (easy to fake, no fidelity) and some with FakeGitHub (harder to set up, better fidelity).

**Recommendation:** The codebase would benefit from migrating the `@patch("module.gh_json")` tests to use FakeGitHub where feasible, or at minimum documenting which tests use which approach and why.

**Severity:** Medium. The mock-based tests pass but don't exercise the FakeGitHub fidelity layer that was built specifically to catch these issues.

### C.2 No negative test for FakeGitHub returning something real gh would never return

Multiple tests seed FakeGitHub state by directly setting `self.fake_gh.issues = [...]` with hand-crafted dicts. These dicts may be missing fields that real GitHub always includes (e.g., `"assignees"`, `"comments"`, `"html_url"`, `"created_at"`, `"updated_at"`). If production code starts relying on these fields, the test would crash with a `KeyError` rather than gracefully failing — which is actually a good thing (fail-fast). But more subtly:

- FakeGitHub's `_issue_create` (fake_github.py line 533-541) creates issues with a specific shape that includes `"closedAt": None`. Real GitHub returns `"closed_at"` (snake_case), not `"closedAt"` (camelCase). But `gh --json` uses camelCase. So FakeGitHub is correct for the `gh --json` path but would be wrong for the REST API path. This is not tested.

- FakeGitHub's `_pr_create` returns `"state": "OPEN"` (uppercase), matching real `gh pr list --json state`. But real GitHub REST API returns `"state": "open"` (lowercase). FakeGitHub documents this (BH19-005 comments) but there's no fidelity test asserting the casing.

**Severity:** Low-Medium. The FakeGitHub is designed for `gh --json` usage, not REST API, and documents its conventions.

### C.3 Missing error state propagation tests

Across all five files, none test what happens when a mid-pipeline step fails:
- What if `create_milestones_on_github` succeeds but `populate_issues` fails? Is the state left consistent?
- What if `sync_one` raises partway through processing a list of issues?
- What if `write_burndown` succeeds but `update_sprint_status` raises?

These are resilience/atomicity concerns that integration tests should cover.

**Severity:** Medium. Pipeline failures in production would leave partial state.

### C.4 Test isolation: os.chdir side effect

Both `test_lifecycle.py` (line 63) and `test_golden_run.py` (line 79) call `os.chdir()` in setUp and restore in tearDown. If a test crashes before tearDown (e.g., unhandled exception in setUp after chdir), the working directory is corrupted for all subsequent tests. The `addCleanup` call in test_lifecycle.py (line 64) mitigates this for that file, but test_golden_run.py lacks `addCleanup` and relies solely on tearDown.

**Severity:** Low-Medium. If tearDown fails to run (e.g., due to KeyboardInterrupt), subsequent tests may fail with confusing errors.

### C.5 Missing: No test for FakeGitHub strict warning collection in test_lifecycle

`test_lifecycle.py` tearDown (lines 67-73) checks `self.fake_gh._strict_warnings` and fails the test if warnings were collected. This is good practice. However, `test_golden_run.py` does NOT check strict warnings in its tearDown. A FakeGitHub strict warning in the golden run pipeline would be silently swallowed.

**Severity:** Medium. The golden run test could pass while FakeGitHub emits warnings about unimplemented flags.

---

## Summary Table

| File | Finding | Anti-Pattern | Severity |
|------|---------|--------------|----------|
| test_gh_interactions.py | Gate tests spend most assertions on call_args | Inspector Clouseau | Low |
| test_gh_interactions.py | gate_prs missing null/empty milestone edge cases | Happy Path Tourist | Low |
| test_gh_interactions.py | check_atomicity always mocked | Mockingbird | Low |
| test_gh_interactions.py | test_valid_fix_with_scope skips err check | Green Bar Addict | Negligible |
| test_gh_interactions.py | determine_bump has no empty-list test | Happy Path Tourist | Low |
| test_gh_interactions.py | release notes test misleading about which path runs | Fragile | Low |
| test_sprint_runtime.py | database_id check uses imprecise str() matching | Inspector Clouseau | Low-Medium |
| test_sprint_runtime.py | TestSyncOne.test_no_changes doesn't assert TF unchanged | Rubber Stamp | Medium |
| test_sprint_runtime.py | TestSyncOneGitHubAuthoritative spy is vacuously true | Rubber Stamp | **Medium-High** |
| test_sprint_runtime.py | get_linked_pr dict normalization path untested | Happy Path Tourist | Medium |
| test_sprint_runtime.py | Time patching strategy fragile to import refactoring | Time Bomb | Low |
| test_lifecycle.py | test_01 only checks boolean, not content | Green Bar Addict | Low |
| test_lifecycle.py | No error-path tests in entire file | Happy Path Tourist | Medium |
| test_lifecycle.py | test_14 checks formatting, not computation | Green Bar Addict | Low |
| test_golden_run.py | Silent skipTest when recordings absent | Green Bar Addict | Medium |
| test_golden_run.py | Phase 2 assertion is just "> 10 labels" | Green Bar Addict | Low |
| test_fakegithub_fidelity.py | jq filter test doesn't verify result shape | Green Bar Addict | Medium |
| test_fakegithub_fidelity.py | search predicate test doesn't verify filtering | Rubber Stamp | Medium |
| test_fakegithub_fidelity.py | milestone reassignment counter untested | Happy Path Tourist | Medium |
| test_fakegithub_fidelity.py | jq fallback path is dead code in test env | Happy Path Tourist | Medium |
| Cross-cutting | gh_json mocks bypass FakeGitHub fidelity | Mockingbird | Medium |
| Cross-cutting | No mid-pipeline failure tests | Happy Path Tourist | Medium |
| Cross-cutting | golden_run.py lacks strict warning check in tearDown | Green Bar Addict | Medium |
| Cross-cutting | golden_run.py lacks addCleanup for os.chdir | Fragile | Low-Medium |

**Highest-severity finding:** `TestSyncOneGitHubAuthoritative` (2.7) has a spy that is vacuously true — the test claims to verify that `sync_one()` doesn't push state to GitHub, but the assertion passes trivially because `sync_one()` never calls `subprocess.run` in the first place. This is a test that LOOKS meaningful but provides zero verification value.
