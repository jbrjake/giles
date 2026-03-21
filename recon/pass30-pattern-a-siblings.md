# Pass 30 — Pattern A: Test Name/Docstring vs Assertion Gap

**Pattern:** Tests whose names or docstrings promise behavior that the
assertions don't actually verify. Sibling search of the fixed
`test_status_wip_limit_warning` bug in `test_kanban.py`.

**Scope:** All 17 test files in `tests/`.

---

## Findings

### 1. test_kanban.py:1222 — `test_update_no_changes`

- **Name/docstring promises:** "When values match current state, no write is performed"
- **What assertions check:** Compares `st_mtime` before and after `do_update()`
- **Gap:** The test actually does verify the no-write claim via mtime comparison. This is correct.
- **Severity:** N/A (false alarm — properly tested)

---

### 2. test_sprint_teardown.py:465 — `test_dry_run_preserves_files`

- **Name/docstring promises:** "Dry run should not remove any files"
- **What assertions check:** Verifies `SystemExit(0)` and that two files still exist
- **Gap:** None significant. The test checks what it claims. It could also verify stdout mentions "dry run" but the core promise is covered.
- **Severity:** N/A (adequately tested)

---

### 3. test_hooks.py:546 — `test_blocks_commit_when_unverified`

- **Name/docstring promises:** "Block git commit when source files modified but no check run"
- **What assertions check:** `assertEqual(result, "blocked")`
- **Gap:** The docstring says "source files modified" but no source file modification is set up — the test uses `_state_override=True` which bypasses the real state detection entirely. The test verifies the override pathway, not the actual "source files modified" detection logic.
- **Severity:** MEDIUM — The actual source-file-detection-triggers-block path is tested separately in `test_stale_hash_blocks_commit` (line 610) which writes a stale hash file. But the docstring on this test is misleading about what it exercises.

---

### 4. test_hooks.py:551 — `test_allows_commit_when_verified`

- **Name/docstring promises:** "Allow git commit when checks have been run"
- **What assertions check:** `assertEqual(result, "allowed")` with `_state_override=False`
- **Gap:** Similar to above — "checks have been run" implies the real verification flow, but `_state_override=False` bypasses it entirely. The real flow is tested in `test_mark_verified_then_commit_allowed` (line 591).
- **Severity:** MEDIUM — Misleading docstring; the override tests are useful unit tests but their docstrings describe integration behavior they don't exercise.

---

### 5. test_hooks.py:480 — `test_format_context_under_60_lines`

- **Name/docstring promises:** "Hook output stays compact"
- **What assertions check:** `assertLess(line_count, 60)`, checks `item1` and `risk1` are present
- **Gap:** The test only passes 3 action items, 1 DoD addition, and 2 risks — trivially small input. It doesn't test whether the output stays under 60 lines with a large number of items (the interesting edge case for a compactness claim).
- **Severity:** MEDIUM — The 60-line limit is only tested with minimal input, not adversarial input. If the function formats each item on 5 lines, 20 items would blow past 60 lines and this test wouldn't catch it.

---

### 6. test_new_scripts.py:281 — `test_escalate_overdue`

- **Name/docstring promises:** "escalate_overdue" (the function name implies the risk is escalated/marked)
- **What assertions check:** Verifies overdue list has 1 entry with `id == "R1"`
- **Gap:** The test checks that the risk is *detected* as overdue, but doesn't verify it was actually *escalated* (e.g., severity changed, notification logged, etc.). However, looking at the function signature, `escalate_overdue` returns a list of overdue risks — the function's job is detection, not mutation. The name is slightly misleading at the function level, but the test correctly tests the function's actual contract.
- **Severity:** LOW — The "escalate" naming is the function's problem, not the test's. The test matches the function's actual behavior.

---

### 7. test_sprint_runtime.py:1026 — `test_no_branches` (TestCheckBranchDivergence)

- **Name/docstring promises:** Tests `check_branch_divergence` with no branches
- **What assertions check:** Empty report, empty actions, `mock_gh.assert_not_called()`
- **Gap:** None. Correctly verifies the no-op case including that no API call was made.
- **Severity:** N/A

---

### 8. test_verify_fixes.py:165 — `test_no_duplicate_test_job`

- **Name/docstring promises:** "Test command should not appear in both check jobs and the test matrix job"
- **What assertions check:** Counts lines starting with `run: cargo test` and asserts exactly 1
- **Gap:** The check only looks at lines *starting with* `run: cargo test`. If the duplicate appears as `- run: cargo test` (with a dash prefix, common in YAML), it would be missed. The `l.strip().startswith("run: cargo test")` pattern excludes YAML list items.
- **Severity:** MEDIUM — The assertion methodology could miss duplicates formatted differently than expected. A broader search for all occurrences of `cargo test` as a command would be more robust.

---

### 9. test_bugfix_regression.py — `test_no_args_exits_2` (TestSyncTrackingMainArgParsing, line 43)

- **Name/docstring promises:** "sync_tracking.main() rejects bad args"
- **What assertions check:** Only checks `SystemExit` with code 2
- **Gap:** Doesn't verify the error *message* mentions the problem (e.g., "sprint number required"). Just checking exit code 2 proves argparse rejected something, not that the right thing was rejected.
- **Severity:** LOW — Exit code 2 is sufficient for "rejects bad args." The error message is an implementation detail.

---

### 10. test_pipeline_scripts.py:180 — `test_coverage_no_actual_tests`

- **Name/docstring promises:** "With no test implementations, all planned tests are missing"
- **What assertions check:** Verifies `len(implemented) == 0`, then checks `planned_ids == missing_ids`
- **Gap:** None. The test correctly verifies that planned and missing sets are identical when no tests exist.
- **Severity:** N/A

---

### 11. test_new_scripts.py:213 — `test_warning_zero_integration`

- **Name/docstring promises:** Tests that zero integration tests produce a WARNING
- **What assertions check:** `assertIn("WARNING", report)` and `assertIn("0 integration", report)`
- **Gap:** None meaningful. Checks the WARNING is present with the right context.
- **Severity:** N/A

---

### 12. test_kanban.py:1320 — `test_status_groups_multiple_dev_stories`

- **Name/docstring promises:** "Multiple stories in DEV appear grouped under DEV header"
- **What assertions check:** Checks all 4 story IDs appear in output and "DEV" appears
- **Gap:** The test verifies all stories and the DEV header are present but doesn't verify they are *grouped together* under the DEV header. They could be scattered throughout the output and the test would still pass. However, the board-view format is a table/section layout where grouping is structural, so in practice the assertion is sufficient.
- **Severity:** LOW — The test could be stronger by verifying ordering (DEV header appears before the story IDs), but the format makes this unlikely to fail silently.

---

### 13. test_hooks.py:156 — `test_no_log_without_project_toml`

- **Name/docstring promises:** "_log_blocked should not create directories when project.toml is missing"
- **What assertions check:** Calls `_log_blocked()` then asserts `sprint-config/` doesn't exist
- **Gap:** None. Correctly verifies no directory creation. Good negative test.
- **Severity:** N/A

---

### 14. test_kanban.py:912 — `test_assign_reverts_on_github_failure`

- **Name/docstring promises:** "RuntimeError from gh reverts local file to old personas"
- **What assertions check:** `result == False`, loaded implementer == "old-impl", and call involved "issue"
- **Gap:** The docstring says "old personas" (plural) but only checks implementer revert, not reviewer revert. However, the test only changes the implementer, so the scope is appropriate for the single-field case.
- **Severity:** LOW — Would be stronger if it also tested reviewer revert in the dual-assign failure case, but this isn't a gap in this specific test's promise.

---

### 15. test_sprint_runtime.py:1082 — `test_api_error_handled` (TestCheckBranchDivergence)

- **Name/docstring promises:** API error is handled (not silently swallowed)
- **What assertions check:** Report has 1 entry containing "skipped" and the branch name, empty actions
- **Gap:** None. Tests that the error is surfaced in the report, not silently dropped.
- **Severity:** N/A

---

## Summary

| # | File | Line | Test Name | Severity |
|---|------|------|-----------|----------|
| 3 | test_hooks.py | 546 | test_blocks_commit_when_unverified | MEDIUM |
| 4 | test_hooks.py | 551 | test_allows_commit_when_verified | MEDIUM |
| 5 | test_hooks.py | 480 | test_format_context_under_60_lines | MEDIUM |
| 8 | test_verify_fixes.py | 165 | test_no_duplicate_test_job | MEDIUM |
| 6 | test_new_scripts.py | 281 | test_escalate_overdue | LOW |
| 9 | test_bugfix_regression.py | 43 | test_no_args_exits_2 | LOW |
| 12 | test_kanban.py | 1320 | test_status_groups_multiple_dev_stories | LOW |
| 14 | test_kanban.py | 912 | test_assign_reverts_on_github_failure | LOW |

**4 MEDIUM findings, 4 LOW findings.**

### Analysis

Unlike the original `test_status_wip_limit_warning` bug (which was HIGH — the test name
promised WIP warning testing but tested grouping instead), none of these findings represent
tests that completely test the wrong thing. The MEDIUM findings fall into two categories:

1. **Misleading docstrings on override tests** (findings 3, 4): The commit_gate tests use
   `_state_override` to unit-test a single code path, but their docstrings describe the
   end-to-end behavior. The real integration behavior IS tested elsewhere in the same file.
   Not masking bugs, but could mislead someone reading only these tests.

2. **Weak assertion methodology** (findings 5, 8): The format_context compactness test
   uses trivially small input, and the CI duplicate test uses a narrow string match that
   could miss alternative formatting. These could allow regressions to slip through, but
   the risk is moderate.

The LOW findings are mostly cases where tests could be marginally stronger but aren't
actually masking behavioral gaps.
