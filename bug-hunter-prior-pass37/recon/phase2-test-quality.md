# Phase 2: Test Quality Audit — Bug Hunter Pass 37

Audited: test_sprint_runtime.py, test_pipeline_scripts.py, test_verify_fixes.py, test_kanban.py, test_hooks.py, test_new_scripts.py, test_bugfix_regression.py

---

## HIGH Severity

### H1: Assertion-free tests rely on "no exception" as success criterion

**File:** `tests/test_verify_fixes.py:1987`
**Anti-pattern:** Assertion-free test / false confidence
**Test:** `TestTeardownDryRunOutput.test_dry_run_with_symlinks_and_generated`

The test calls `sprint_teardown.print_dry_run()` and only checks that no exception is raised (comment on line 2017: "If we get here without exception, the test passes"). It does not assert anything about the output. The function could silently produce empty output, skip symlinks, or misclassify files, and this test would still pass. Should capture stdout and assert it mentions the symlink, the generated file count, and the expected classification.

**File:** `tests/test_verify_fixes.py:2021`
**Anti-pattern:** Assertion-free test / false confidence
**Test:** `TestTeardownDryRunOutput.test_dry_run_empty_lists`

Same pattern as above. Calls `print_dry_run()` with all-empty arguments and asserts nothing about output. If print_dry_run crashes only on non-empty input, this test adds no value.

---

### H2: Assertion-free happy-path test for team_voices.main()

**File:** `tests/test_verify_fixes.py:1248`
**Anti-pattern:** Assertion-free test / false confidence
**Test:** `TestTeamVoicesMainHappyPath.test_runs_with_no_voices`

Calls `team_voices.main()` and has zero assertions. The docstring says "runs without error" but it does not verify that main() produced any output, returned successfully, or handled the no-voices case correctly. This test will pass even if main() silently does nothing or swallows errors. Should at minimum capture stdout and assert it contains expected output.

---

### H3: Mock pollution — do_transition double-fault test mocks away disk writes, never verifies disk state

**File:** `tests/test_kanban.py:471-486`
**Anti-pattern:** Mock pollution / false confidence
**Test:** `TestTransitionCommand.test_transition_double_fault_restores_tf_status`

This test patches `kanban.atomic_write_tf` with a side_effect list `[None, OSError("disk full")]`. The first `None` means the initial write (the optimistic write of the new state) is silently mocked away — no file is ever written. The test only verifies `tf.status` is restored in memory (`self.assertEqual(tf.status, "todo")`), but since the disk write was mocked, it never tests the actual double-fault scenario on disk. The file on disk still has the *original* state from `_make_tf()`, so even if the in-memory rollback code were broken, the disk read would still show "todo". The test name says "restores tf.status" which is technically accurate, but the real double-fault concern (can the user recover from both GitHub and disk failure?) is only verified at the in-memory level. Adding `loaded = read_tf(tf.path); self.assertEqual(loaded.status, "todo")` would reveal that the file was never actually written to the new state in the first place.

---

### H4: Weakened assertion — assertTrue(len(...) > 0) instead of specific value checks

**File:** `tests/test_sprint_runtime.py:77`
**Anti-pattern:** Weakened assertion
**Test:** `TestCheckCI.test_failing_run`

After setting up a failing CI run with specific data (name "CI", branch "feat/x", databaseId 42), the test only checks `assertTrue(len(actions) > 0)`. It does not verify that the action item references the correct failing run, the branch name, or the run ID. The action could contain garbage and this test would pass. Should verify the action content mentions "feat/x" or "CI".

**File:** `tests/test_sprint_runtime.py:157`
**Anti-pattern:** Weakened assertion
**Test:** `TestCheckPRs.test_mixed_review_states`

Three PRs are set up with different states (APPROVED, needs-review, CHANGES_REQUESTED). The test checks `assertTrue(len(actions) > 0)` for the actions, but does not verify which PR generated the action. The action could reference the wrong PR number and this test would pass. Should verify the action mentions PR #3 (the changes-requested one).

---

## MEDIUM Severity

### M1: Contract tests verify element presence but not argument ordering

**File:** `tests/test_sprint_runtime.py:58-64`
**Anti-pattern:** Weak contract test
**Test:** `TestCheckCI.test_queries_run_endpoint_with_json`

Asserts `assertIn("run", call_args)` and `assertIn("--json", call_args)` on the gh_json argument list. While this correctly verifies the elements exist in the list, it does not verify argument ordering. The function could call `gh_json(["--json", "run", ...])` (invalid CLI syntax) and this test would still pass. For a contract test intended to verify the API call shape, should assert that `call_args[0] == "run"` and `call_args[1] == "list"` or use `assertEqual(call_args[:2], ["run", "list"])`.

**File:** `tests/test_sprint_runtime.py:115-117`
**Anti-pattern:** Weak contract test
**Test:** `TestCheckPRs.test_approved_pr` (the contract assertion portion)

Same pattern: asserts `assertIn("pr", call_args)` and `assertIn("--json", call_args)` but does not verify the subcommand (should be `"pr", "list"` in order).

---

### M2: Missing negative tests for check_milestone SP calculation

**File:** `tests/test_sprint_runtime.py:1833-1846`
**Anti-pattern:** Missing negative test
**Test:** `TestCheckMilestone.test_happy_path_with_sp`

Tests that 3 closed + 2 open shows "3/5" and mentions "SP", but never tests that the SP summation is actually correct. The test does not verify "10 SP done" vs "23 SP planned" or any specific SP number. The SP calculation could be completely wrong (summing incorrectly) and this test would pass as long as the string "SP" appears somewhere. Should assert specific SP totals in the report.

---

### M3: Missing boundary tests for branch divergence thresholds

**File:** `tests/test_sprint_runtime.py:1039-1080`
**Anti-pattern:** Missing negative tests / missing boundary tests
**Test:** `TestCheckBranchDivergence` class

The production code uses thresholds `>20` for HIGH and `>10` for MEDIUM (check_status.py:414,422). Tests use values 3, 15, and 25, which are well within each band. No test verifies the exact boundaries: behind_by=10 should produce no report (below MEDIUM threshold), behind_by=11 should produce MEDIUM, behind_by=20 should still be MEDIUM (not HIGH), and behind_by=21 should trigger HIGH. A threshold change from `>10` to `>=10` would silently change behavior without any test catching it.

---

### M4: Redundant test — duplicate kanban_from_labels tests across two files

**File:** `tests/test_sprint_runtime.py:1674-1712` and `tests/test_pipeline_scripts.py:1641-1676`
**Anti-pattern:** Weakened assertions / redundancy
**Tests:** `TestKanbanFromLabels` in both test_sprint_runtime.py and test_pipeline_scripts.py

The class `TestKanbanFromLabels` exists in both files with overlapping test cases (e.g., both test valid state returned, invalid state fallback, no kanban label). This is not a bug per se, but it suggests tests were added defensively across multiple passes without checking for duplication, which inflates test counts without adding coverage. One should be removed to avoid false confidence in test count metrics.

---

### M5: assertIn on stringified mock.call_args is fragile and can produce false positives

**File:** `tests/test_kanban.py:466-468`
**Anti-pattern:** Weakened assertion
**Test:** `TestTransitionCommand.test_transition_reverts_on_github_failure`

Uses `self.assertIn("42", str(mock.call_args))` and `self.assertIn("kanban:design", str(mock.call_args))`. Stringifying call_args and doing substring matching is fragile — "42" could match anything (like a line number in the repr), not just the issue number. Should inspect `mock.call_args[0][0]` directly and check the args list contains "42" and "kanban:design" as distinct elements.

**File:** `tests/test_sprint_runtime.py:89`
**Anti-pattern:** Weakened assertion
**Test:** `TestCheckCI.test_failing_run_log_uses_database_id`

Same pattern: `assertIn("42", str(mock_gh.call_args))`. The string "42" is extremely common and could match repr artifacts.

---

### M6: assertTrue(len(...) == 1) instead of assertEqual

**File:** `tests/test_new_scripts.py:368`
**Anti-pattern:** Weakened assertion
**Test:** `TestRiskRegister.test_add_risk_sanitizes_pipes`

Uses `self.assertTrue(len(data_lines) == 1)` instead of `self.assertEqual(len(data_lines), 1)`. The `assertTrue` form produces an unhelpful failure message ("False is not True") while `assertEqual` would show the actual and expected values. This pattern appears to be a result of fixing passes where assertions were loosened.

---

## LOW Severity

### L1: Test name promises behavior the assertion doesn't verify

**File:** `tests/test_verify_fixes.py:2036-2057`
**Anti-pattern:** False confidence
**Test:** `TestTeardownDryRunOutput.test_dry_run_with_unknown_files`

The docstring says "print_dry_run() reports unknown files that would be skipped." The test verifies that `classify_entries` returns 1 unknown file, but does not capture the output of `print_dry_run()` to verify the unknown file is actually reported in the output. The classification is tested; the reporting is not.

---

### L2: Redundant duplicate assertion

**File:** `tests/test_verify_fixes.py:87-92`
**Anti-pattern:** Redundant assertion
**Test:** `TestConfigGeneration.test_generated_toml_has_required_keys`

Line 87: `self.assertIn("build_command", config["ci"])` and line 92: `self.assertIn("build_command", config["ci"])` — the exact same assertion appears twice. The second one was likely left behind during a prior fix pass.

---

### L3: Contract tests check substring presence in lists, not list position

**File:** `tests/test_sprint_runtime.py:172-178`
**Anti-pattern:** Weakened assertion
**Test:** `TestCreateLabel.test_creates_label`

Asserts `assertIn("label", call_args)`, `assertIn("create", call_args)`, etc. While functionally correct, these assertions would pass even if the arguments were reordered (e.g., `["create", "label", ...]` instead of the expected gh CLI syntax `["label", "create", ...]`). For a contract test, asserting argument positions or at least relative ordering would be stronger.

---

### L4: Boolean-ish assertion on report line content

**File:** `tests/test_sprint_runtime.py:1845`
**Anti-pattern:** Weakened assertion
**Test:** `TestCheckMilestone.test_happy_path_with_sp`

Uses `self.assertTrue(any("3/5" in line for line in report))` which is a correct but brittle pattern. If the report format changes from "3/5 stories" to "3 of 5 stories", the test silently passes via the `any()` on other lines. A direct `assertIn("3/5", report_text)` after joining would be clearer and fail more informatively.

---

### L5: assertTrue(result) on non-boolean return value

**File:** `tests/test_sprint_runtime.py:408`
**Anti-pattern:** Weakened assertion
**Test:** `TestCreateIssueMissingMilestone.test_missing_milestone_still_creates_issue`

`self.assertTrue(result)` where `result` is the return value of `create_issue()`. If `create_issue` returns a truthy string URL, this passes. But the test name says "still creates issue" — it should verify the return value is a URL string (e.g., `assertIn("github.com", result)`), not just that it's truthy.
