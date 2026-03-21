# Test Audit Report

**Date:** 2026-03-20
**Files audited:**
- `tests/test_hooks.py` (837 lines)
- `tests/test_kanban.py` (1337 lines)
- `tests/test_sprint_runtime.py` (~1600 lines)
- `tests/test_bugfix_regression.py` (~1475 lines)

---

## Summary

| Severity | Count |
|----------|-------|
| HIGH     | 5     |
| MEDIUM   | 12    |
| LOW      | 7     |

The test suite is strong in several areas: the kanban state machine tests are thorough,
the FakeGitHub infrastructure is well-designed, and the MonitoredMock / patch_gh pattern
prevents the "mock-returns-what-you-assert" anti-pattern. The main issues cluster around
(a) tests that use `_state_override` / direct mocking where they should test real behavior,
(b) tests with names that promise something the assertion doesn't check, and
(c) missing negative and boundary tests for several features.

---

## HIGH Severity Issues

### FINDING-1: _state_override bypasses the real commit gate state machine
**File:** test_hooks.py
**Test:** TestCommitGate.test_blocks_commit_when_unverified (line 439)
**Severity:** HIGH
**Issue type:** mock-hiding-bug
**Description:** The first three commit gate tests (`test_blocks_commit_when_unverified`,
`test_allows_commit_when_verified`, `test_allows_non_commit_commands`) all use the
`_state_override` parameter to hardcode the verification state. This means they never
exercise `needs_verification()`, the state file, or the hash comparison logic. The tests
would pass even if the hash comparison in `needs_verification()` was completely broken.

Later tests (`test_mark_verified_then_commit_allowed` at line 484, `test_stale_hash_blocks_commit`
at line 503) do exercise the real state machine, which is good. But the first three tests
are misleading because they appear to be the primary commit gate tests yet test nothing
beyond regex matching + an if-statement on a boolean parameter.

**Evidence:**
```python
result = check_commit_allowed("git commit -m 'fix'", _state_override=True)
self.assertEqual(result, "blocked")
```
`_state_override=True` means "pretend verification is needed" -- so the test asserts
`blocked`, but the actual verification logic is never invoked.

---

### FINDING-2: TestCheckStatusImportGuard never actually triggers the import guard
**File:** test_bugfix_regression.py
**Test:** TestCheckStatusImportGuard.test_import_guard_uses_import_error (line 65)
**Severity:** HIGH
**Issue type:** setup-bypass
**Description:** This test claims to verify that check_status degrades correctly when
sync_backlog is unavailable. But it never makes sync_backlog unavailable. It just checks
`hasattr(check_status, 'sync_backlog_main')` and `callable(check_status.check_ci)`. These
assertions are always true in the test environment (where sync_backlog IS available). The
`if check_status.sync_backlog_main is not None` guard on line 76 means the "unavailable"
path is never tested.

**Evidence:**
```python
self.assertTrue(hasattr(check_status, 'sync_backlog_main'))
if check_status.sync_backlog_main is not None:
    self.assertTrue(callable(check_status.sync_backlog_main))
# Core functions must always be available regardless
self.assertTrue(callable(check_status.check_ci))
```
All four assertions are tautological in this environment. To actually test the import guard,
you would need to temporarily remove sync_backlog from sys.modules and re-import check_status,
or mock the import mechanism.

---

### FINDING-3: sync_one tests mutate in-memory TF but never verify disk persistence
**File:** test_sprint_runtime.py
**Test:** TestSyncOne.test_closed_issue_updates_status (line 1318) and several siblings
**Severity:** HIGH
**Issue type:** weak-assertion
**Description:** Most TestSyncOne tests (lines 1318-1376) check that `tf.status` and
`tf.pr_number` are updated on the in-memory TF object, but never write to disk and read
back. Since `sync_one()` only mutates the in-memory TF (the caller is responsible for
calling `write_tf(tf)`), these tests don't verify that the changes actually survive
serialization.

The exception is `test_sync_one_roundtrip_to_disk` (line 1379) which does the full
write-read cycle -- but the other 5 tests in the class operate entirely in-memory, and
one of them (`test_pr_number_updated` line 1338) uses `path=Path("/tmp/test.md")` which
would fail if it tried to write.

**Evidence:**
```python
def test_closed_issue_updates_status(self):
    tf = sync_tracking.TF(path=Path("/tmp/test.md"), story="US-0001",
                          status="dev", sprint=1)
    issue = {"state": "closed", "labels": [], "closedAt": "2026-03-10T12:00:00Z", "number": 1}
    changes = sync_tracking.sync_one(tf, issue, None, 1)
    self.assertEqual(tf.status, "done")  # in-memory only
```
If write_tf() silently corrupts the status field during serialization, these tests won't catch it.

---

### FINDING-4: test_verification_passed tests use shell builtins, not portable commands
**File:** test_hooks.py
**Test:** TestVerifyAgentOutput.test_verification_passed_all_exit_zero (line 252)
**Severity:** HIGH
**Issue type:** setup-bypass
**Description:** Three verification tests use bare shell commands (`true`, `false`,
`bash -c 'echo badness >&2; exit 1'`) which are POSIX-only. While the project targets
macOS/Linux, these tests would silently pass or fail differently on other platforms.
More critically, the `true` / `false` commands test subprocess execution, not the
actual verification logic. The test `run_verification(["true"])` only proves that
a command returning exit code 0 produces "VERIFICATION PASSED" -- it doesn't test
with real check commands like `python -m pytest`.

**Evidence:**
```python
report, passed = run_verification(["true"])
self.assertTrue(passed)
self.assertIn("VERIFICATION PASSED", report)
```

---

### FINDING-5: _read_toml_key escaped-quote test has wrong expected value
**File:** test_hooks.py
**Test:** TestVerifyAgentOutput.test_read_toml_key_inline_comment_after_escaped_quote (line 338)
**Severity:** HIGH
**Issue type:** weak-assertion
**Description:** The test provides input `'echo \\"hello\\"'` and expects the output
to be `'echo \\"hello\\"'` -- the literal backslash-escaped string. But this means
the function is NOT unescaping the backslashes. If the TOML spec says `\"` inside a
double-quoted string should produce a literal `"`, then the expected value should be
`'echo "hello"'`. The test is asserting the current (possibly wrong) behavior rather
than the correct behavior.

**Evidence:**
```python
toml = '[ci]\nsmoke_command = "echo \\"hello\\"" # a comment\n'
result = _read_toml_key(toml, "ci", "smoke_command")
self.assertEqual(result, 'echo \\"hello\\"')
```
If the function correctly unescaped `\"` to `"`, this test would fail. The test may be
documenting a known limitation, but the assertion matches the bug rather than the spec.

---

## MEDIUM Severity Issues

### FINDING-6: format_context line count check is too loose
**File:** test_hooks.py
**Test:** TestSessionContext.test_format_context_under_60_lines (line 418)
**Severity:** MEDIUM
**Issue type:** weak-assertion
**Description:** The test asserts `line_count < 60` but the actual output with 3 action
items, 1 DoD addition, and 2 risks is probably around 15 lines. The threshold of 60 is
so generous that it would pass even if the function doubled its output. The test also
doesn't verify the markdown structure (section headers like "### Retro Action Items").
A function that concatenated all strings on one line would pass.

**Evidence:**
```python
line_count = len(output.strip().splitlines())
self.assertLess(line_count, 60)
```

---

### FINDING-7: WIP limit warning test doesn't verify any warning text
**File:** test_kanban.py
**Test:** TestStatusCommand.test_status_wip_limit_warning (line 1255)
**Severity:** MEDIUM
**Issue type:** name-mismatch
**Description:** The test is named `test_status_wip_limit_warning` and the docstring says
"4+ stories in DEV triggers WIP limit context." But the assertion only checks that the
stories appear under DEV in the output -- it never verifies any WIP warning text. Looking
at the `do_status` implementation, it doesn't actually emit WIP warnings (it just lists
stories by state). The test name promises a feature that doesn't exist in the code.

**Evidence:**
```python
def test_status_wip_limit_warning(self):
    """BH23-126: 4+ stories in DEV triggers WIP limit context."""
    ...
    output = do_status(sprints_dir, 1)
    self.assertIn("DEV", output)
    for i in range(4):
        self.assertIn(f"US-{i:04d}", output)
```
No assertion for any warning text.

---

### FINDING-8: do_update "no changes" test doesn't verify no write occurred
**File:** test_kanban.py
**Test:** TestUpdateCommand.test_update_no_changes (line 1160)
**Severity:** MEDIUM
**Issue type:** weak-assertion
**Description:** The docstring says "When values match current state, no write is performed."
The test only checks `ok == True`. It doesn't verify the file's mtime was unchanged or
that `atomic_write_tf` was not called. The "no write" optimization claim is untested.

**Evidence:**
```python
def test_update_no_changes(self):
    """When values match current state, no write is performed."""
    with tempfile.TemporaryDirectory() as td:
        tf = self._make_tf(td, pr_number="42")
        ok = do_update(tf, pr_number="42")
        self.assertTrue(ok)
```

---

### FINDING-9: Lock tests verify no deadlock but not actual mutual exclusion
**File:** test_kanban.py
**Test:** TestFileLocking.test_lock_story_acquires_and_releases (line 281)
**Severity:** MEDIUM
**Issue type:** weak-assertion
**Description:** The lock_story and lock_sprint tests verify that a lock can be acquired,
released, and re-acquired without deadlock. But they don't verify mutual exclusion -- that
two concurrent acquirers are actually serialized. The `test_concurrent_lock_serializes`
test (line 309) does test serialization, but it uses `time.sleep(0.2)` which makes it
timing-dependent and potentially flaky on slow CI machines.

**Evidence:**
```python
def test_lock_story_acquires_and_releases(self):
    with lock_story(p):
        pass
    with lock_story(p):
        pass  # second acquire must succeed
```
This only proves the lock is reentrant (or at least re-acquirable), not that it excludes
concurrent access.

---

### FINDING-10: check_ci contract test doesn't verify specific JSON fields
**File:** test_sprint_runtime.py
**Test:** TestCheckCI.test_queries_run_endpoint_with_json (line 58)
**Severity:** MEDIUM
**Issue type:** weak-assertion
**Description:** The test is labeled "BH23-102: Contract test" and claims to verify the
query includes correct fields. But it only checks that the call contains "run" and "--json".
It doesn't verify which JSON fields are requested (e.g., "status", "conclusion", "name",
"headBranch", "databaseId"). A contract test should pin the exact fields so that if the
caller starts omitting a field, the test catches it.

**Evidence:**
```python
def test_queries_run_endpoint_with_json(self, mock_gh):
    mock_gh.return_value = []
    check_status.check_ci()
    call_args = mock_gh.call_args[0][0]
    self.assertIn("run", call_args)
    self.assertIn("--json", call_args)
```

---

### FINDING-11: Mixed PR states test doesn't verify which PR generated the action
**File:** test_sprint_runtime.py
**Test:** TestCheckPRs.test_mixed_review_states (line 131)
**Severity:** MEDIUM
**Issue type:** weak-assertion
**Description:** The test creates 3 PRs (approved, needs review, changes requested)
and verifies the summary text. The assertion `self.assertTrue(len(actions) > 0)` only
checks that at least one action was generated, not that it was specifically the
CHANGES_REQUESTED PR that generated it. The action item content is never inspected.

**Evidence:**
```python
self.assertTrue(len(actions) > 0)
```
Should be `self.assertEqual(len(actions), 1)` and should verify the action mentions
PR #3 or "changes requested".

---

### FINDING-12: Failing CI run test doesn't verify log content mapping
**File:** test_sprint_runtime.py
**Test:** TestCheckCI.test_failing_run (line 67)
**Severity:** MEDIUM
**Issue type:** weak-assertion
**Description:** The test mocks both `gh_json` (for run data) and `gh` (for log fetching).
It verifies the report contains "1 failing" and that actions is non-empty, but it doesn't
verify that the mocked log content ("error: something broke") appears in the report or
actions. The log-fetching code path is exercised but its output is not verified.

**Evidence:**
```python
mock_gh.return_value = "error: something broke\nfatal: test failed"
report, actions = check_status.check_ci()
self.assertIn("1 failing", report[0])
self.assertTrue(len(actions) > 0)
# Never checks that "something broke" appears in actions/report
```

---

### FINDING-13: create_label error test mocks print but doesn't test real error path
**File:** test_sprint_runtime.py
**Test:** TestCreateLabel.test_label_error_handled (line 180)
**Severity:** MEDIUM
**Issue type:** mock-hiding-bug
**Description:** The test patches both `bootstrap_github.gh` AND `builtins.print`.
By patching print, it captures the warning output but also means that if the function's
error handling changed to use `sys.stderr.write()` or `logging.warning()`, the test
would silently stop verifying the warning was emitted. The test should verify behavior
(no exception raised, error is communicated) without relying on the specific output
mechanism.

**Evidence:**
```python
@patch("builtins.print")
@patch("bootstrap_github.gh")
def test_label_error_handled(self, mock_gh, mock_print):
    mock_gh.side_effect = RuntimeError("already exists")
    bootstrap_github.create_label("existing-label", "ff0000")
    mock_print.assert_called_once()
```

---

### FINDING-14: Duplicate testing of extract_sp across test files
**File:** test_sprint_runtime.py + test_bugfix_regression.py
**Test:** TestExtractSP (line 854) and TestBH011ExtractSpBoundary (line 442) and TestExtractSPWordBoundary (line 1002)
**Severity:** MEDIUM
**Issue type:** duplicate
**Description:** `extract_sp` is tested in three different test classes across two files.
TestExtractSP in test_sprint_runtime.py (12 tests), TestBH011ExtractSpBoundary in
test_bugfix_regression.py (5 tests), and TestExtractSPWordBoundary in
test_sprint_runtime.py (4 tests). Several test cases overlap:
- "bsp_does_not_match" appears in both TestBH011 and TestExtractSPWordBoundary
- "standalone_sp_matches" in TestBH011 overlaps with "standalone_sp_still_works" in TestExtractSPWordBoundary
- "sp_from_body" in TestExtractSP overlaps with "sp_with_equals" in TestExtractSPWordBoundary

The duplication makes it harder to know which tests are canonical and wastes CI time.

**Evidence:** Three separate classes test the same function with overlapping inputs.

---

### FINDING-15: FakeGitHub strict mode test verifies infrastructure, not production code
**File:** test_bugfix_regression.py
**Test:** TestFakeGitHubStrictMode (line 755) and TestFakeGitHubFlagEnforcement (line 125)
**Severity:** MEDIUM
**Issue type:** setup-bypass
**Description:** About 100 lines of test_bugfix_regression.py (classes TestFakeGitHubFlagEnforcement,
TestFakeGitHubShortFlags, TestFakeGitHubJqHandlerScoped, TestFakeGitHubIssueLabelFilter,
TestFakeGitHubStrictMode) are testing the test infrastructure itself (FakeGitHub), not
production code. While testing test infrastructure has value, these tests would pass
even if the production code they're meant to support was completely broken. They verify
that FakeGitHub correctly rejects unknown flags and handles strict mode warnings.

**Evidence:** These classes never import or exercise any production script. They only
exercise `FakeGitHub.handle()`.

---

### FINDING-16: MonitoredMock / patch_gh tests are test-infrastructure tests
**File:** test_bugfix_regression.py
**Test:** TestPatchGhHelper (line 843)
**Severity:** MEDIUM
**Issue type:** setup-bypass
**Description:** Similar to FINDING-15. The TestPatchGhHelper class (5 tests) and
TestGatePRsWithPatchGh (2 tests) primarily verify the behavior of the `patch_gh` helper
and `MonitoredMock` proxy. While the gate_prs tests do exercise production code, the
primary intent is demonstrating the helper infrastructure. These would be better placed
in a dedicated test_infrastructure.py file to keep the regression test file focused on
production code behavior.

**Evidence:**
```python
def test_warns_when_call_args_not_checked(self):
    with self.assertWarns(UserWarning) as cm:
        with patch_gh("release_gate.gh_json", return_value=[]) as mock:
            gate_prs("Sprint 1")  # production code, but assertion is on the helper
    self.assertIn("call_args was never inspected", str(cm.warning))
```

---

### FINDING-17: test_dev_to_integration_error_mentions_review has an unused mock
**File:** test_kanban.py
**Test:** TestTransitionCommand.test_dev_to_integration_error_mentions_review (line 608)
**Severity:** MEDIUM
**Issue type:** setup-bypass
**Description:** This test patches `kanban.gh` but the transition should be rejected by
`validate_transition()` before any GitHub call is made (since dev -> integration is
illegal). The mock is created but never called. The test also doesn't verify the error
message mentions "review" -- despite its name promising that.

**Evidence:**
```python
def test_dev_to_integration_error_mentions_review(self):
    """P0-KANBAN-1: dev->integration error mentions 'must pass through review'."""
    with tempfile.TemporaryDirectory() as td:
        tf = self._make_tf(td, status="dev", ...)
        with patch_gh("kanban.gh"):  # never called -- transition rejected before gh
            result = do_transition(tf, "integration")
        self.assertFalse(result)
        loaded = read_tf(tf.path)
        self.assertEqual(loaded.status, "dev")  # no check for "review" in error message
```

---

## LOW Severity Issues

### FINDING-18: Non-merge command test only tests one command variant
**File:** test_hooks.py
**Test:** TestCheckMerge.test_allowed_for_non_merge_commands (line 57)
**Severity:** LOW
**Issue type:** missing-negative
**Description:** Only tests `gh pr view 42`. Doesn't test `gh pr list`, `gh issue create`,
or non-gh commands like `git status`. The regex is simple enough that false positives are
unlikely, but a parameterized test would be more thorough.

**Evidence:**
```python
def test_allowed_for_non_merge_commands(self):
    result = check_merge("gh pr view 42", base="main")
    self.assertEqual(result, "allowed")
```

---

### FINDING-19: Push with colon refspec not tested
**File:** test_hooks.py
**Test:** TestCheckPush (line 88 area)
**Severity:** LOW
**Issue type:** missing-negative
**Description:** `check_push` handles `git push origin HEAD:main` (colon refspec targeting
base), but no test covers this case. The implementation extracts the target from the refspec
via `split(":")[-1]`, which should block it. Without a test, a refactoring could break this
path silently.

**Evidence:** No test for `git push origin HEAD:main` or `git push origin feature:main`.

---

### FINDING-20: _is_implementer_output tests are exhaustive but miss edge cases
**File:** test_hooks.py
**Test:** TestIsImplementerOutput (line 765)
**Severity:** LOW
**Issue type:** missing-negative
**Description:** The tests cover many keywords ("commit", "PR #", "pushed", "merged",
"branch", "tests pass") and reviewer false positives ("the commit looks good", "implementation
is solid"). But they don't test case sensitivity (e.g., "I COMMITTED the changes" vs
"I committed the changes") or partial word matches (e.g., "recommitted" or "unpushed").

**Evidence:** All test strings use lowercase action verbs. No uppercase or partial-match tests.

---

### FINDING-21: test_read_toml_key_escaped_quote_with_bracket doesn't verify first element
**File:** test_hooks.py
**Test:** TestVerifyAgentOutput.test_read_toml_key_escaped_quote_with_bracket (line 325)
**Severity:** LOW
**Issue type:** weak-assertion
**Description:** The test verifies `len(result) == 2` and `result[1] == "ruff check"` but
never checks `result[0]`. The first element should be `'pytest -k "test[param]"'` (with
the escaped quotes resolved), but this is never asserted. If the parser corrupted the first
element, this test would still pass.

**Evidence:**
```python
result = _read_toml_key(toml, "ci", "check_commands")
self.assertEqual(len(result), 2)
self.assertEqual(result[1], "ruff check")
# result[0] is never checked
```

---

### FINDING-22: TestBH001PaginatedJson.test_normal_json_still_works uses FakeGitHub instead of raw mock
**File:** test_bugfix_regression.py
**Test:** TestBH001PaginatedJson.test_normal_json_still_works (line 300)
**Severity:** LOW
**Issue type:** setup-bypass
**Description:** The test is supposed to verify that `gh_json` handles normal (single)
JSON arrays. But it routes through FakeGitHub which always produces clean JSON. The test
never actually exercises the concatenated-JSON parsing path that BH-001 was about. The
sibling test `test_concatenated_json_arrays` (line 310) correctly mocks subprocess directly
to produce concatenated output. The first test adds no value beyond what FakeGitHub-based
integration tests already provide.

**Evidence:**
```python
def test_normal_json_still_works(self):
    fake = FakeGitHub()
    fake.milestones = [{"number": 1, "title": "Sprint 1"}]
    with patch("subprocess.run", make_patched_subprocess(fake)):
        result = validate_config.gh_json([...])
    self.assertEqual(len(result), 1)
```
FakeGitHub produces clean `json.dumps()` output, so this never tests the edge case.

---

### FINDING-23: BH-005 sprint status test doesn't verify paragraph text is preserved
**File:** test_bugfix_regression.py
**Test:** TestBH005SprintStatusRegex.test_description_between_heading_and_table (line 372)
**Severity:** LOW
**Issue type:** weak-assertion
**Description:** The test verifies that old table rows are replaced and the "## Other"
section survives, but it doesn't verify that "Some description paragraph." (the text
between the heading and the table) is preserved. If `update_sprint_status` accidentally
deleted the description paragraph while replacing the table, this test wouldn't catch it.

**Evidence:**
```python
status_file.write_text(
    "## Active Stories\n\n"
    "Some description paragraph.\n\n"
    "| old | table | old | old |\n"
    ...
)
update_burndown.update_sprint_status(1, rows, Path(tmpdir))
content = status_file.read_text()
self.assertIn("NEW-001", content)
self.assertNotIn("OLD-001", content)
self.assertIn("## Other", content)
# Never checks: self.assertIn("Some description paragraph", content)
```

---

### FINDING-24: BH-004 vacuous truth test has unused FakeGitHub instance
**File:** test_bugfix_regression.py
**Test:** TestBH004VacuousTruth.test_in_progress_checks_not_green (line 334)
**Severity:** LOW
**Issue type:** setup-bypass
**Description:** The test creates a FakeGitHub instance but never uses it. The PR data is
passed directly via `patch.object(check_status, "gh_json", return_value=[pr])`. The
FakeGitHub creation is dead code that adds confusion.

**Evidence:**
```python
fake = FakeGitHub()  # created but never used
fake.prs.append(pr)  # data added but fake is never wired in
with patch.object(check_status, "gh_json", return_value=[pr]):
    report, actions = check_status.check_prs()
```

---

## Missing Test Categories

### MISSING-1: No negative test for check_merge with malformed commands
**Severity:** LOW
Commands like `gh pr merge abc` (non-numeric PR), `gh pr merge` with extra flags between
`merge` and the number, or commands with shell metacharacters are never tested.

### MISSING-2: No test for _log_blocked when audit log already exists
**Severity:** LOW
`test_log_written_with_project_toml` creates a fresh log. There's no test for appending
to an existing log file (verifying the existing content is preserved).

### MISSING-3: No integration test for the full hook entry points (main functions)
**Severity:** MEDIUM
The hooks have `main()` functions that read from stdin/cwd, but no test exercises this
end-to-end path. Tests exercise the component functions (`check_merge`, `check_push`,
`_is_implementer_output`) but not the wiring that connects them.

---

## What's Good

These are areas that don't need fixing -- calling them out to avoid wasted effort.

1. **patch_gh / MonitoredMock infrastructure** (`tests/gh_test_helpers.py`): Actively
   prevents the mock-returns-what-you-assert anti-pattern. Tests must inspect
   `mock.call_args` or get a warning. Well designed.

2. **Kanban transition table tests** (`test_kanban.py:96-167`): Exhaustive coverage of
   legal and illegal transitions including same-state noop, invalid state names, and
   specific error message content. Uses `subTest` for good error reporting.

3. **Kanban rollback tests** (`test_kanban.py:455-606`): Tests single-fault (GitHub API
   failure -> local rollback), double-fault (API + disk failure -> in-memory restore),
   and transition log rollback on failure. These exercise real failure paths.

4. **FakeGitHub integration tests** (test_sprint_runtime.py and test_bugfix_regression.py):
   The FakeGitHub tests for check_status.main() and sync_tracking.main() are genuine
   integration tests that wire multiple components together through mocked GitHub endpoints.

5. **Sync command tests** (`test_kanban.py:975-1122`): Good coverage of legal/illegal
   external transitions, closed issues, orphan detection, malformed titles, pruning,
   and multiple-match warnings.

6. **Preconditions tests** (`test_kanban.py:169-224`): Thorough coverage of all
   precondition gates including negative cases (missing implementer, branch, PR number,
   reviewer) and unchecked states.

7. **WIP limit tests** (`test_kanban.py:662-833`): Comprehensive tests for dev WIP (1
   per implementer), review WIP (2 per reviewer), integration WIP (3 team-wide), with
   both blocking and allowing scenarios, cross-persona independence, and force override.

8. **Tracking file round-trip tests** (`test_kanban.py:22-70`): Verify ALL fields survive
   write->read including edge cases like commas in titles and empty fields.

9. **Word-boundary matching tests** (test_sprint_runtime.py:782-825): Thorough coverage
   of PR branch matching to prevent substring false positives (US-01 not matching US-010).
