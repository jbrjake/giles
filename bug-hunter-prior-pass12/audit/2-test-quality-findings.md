# Bug Hunter Punchlist — Phase 2: Test Quality Audit

Audit date: 2026-03-15
Auditor: Claude Opus 4.6 (adversarial mode)
Scope: All 12 test files in `tests/`, plus `fake_github.py` test infra

---

### BH-P11-050 — Assertion-free smoke test in update_sprint_status
- **Severity:** High
- **Category:** assertion-free
- **Location:** `tests/test_gh_interactions.py:1548`
- **Problem:** `test_skips_missing_file` calls `update_burndown.update_sprint_status()` but has zero assertions. The comment says "Should not raise" but any codepath that does not crash passes this test — including one that silently corrupts data or returns wrong values. A function that accidentally writes to `/tmp` or creates an unexpected file would pass.
- **Acceptance Criteria:** Assert that (a) no file was created in the tmpdir, (b) the function returns None or a specific sentinel, and (c) no side effects occurred (directory listing unchanged).
- **Validation:** `python -m pytest tests/test_gh_interactions.py::TestUpdateSprintStatus::test_skips_missing_file -v`
- **Status:** Open

---

### BH-P11-051 — Golden run silently degrades to no-op when recordings absent
- **Severity:** High
- **Category:** assertion-free
- **Location:** `tests/test_golden_run.py:101-109`
- **Problem:** When golden recording files are absent (which is the default in a fresh clone), `_check_or_record` issues `warnings.warn()` and continues without performing any snapshot comparison. The test passes with full green while providing zero regression coverage. In CI, this means the "golden run" test name creates false confidence — it sounds like it validates output fidelity but actually checks nothing beyond basic count assertions.
- **Acceptance Criteria:** Either (a) check golden recordings into the repo and fail when they're missing, or (b) mark the test as `skipTest("Golden recordings not found")` so CI clearly reports the coverage gap instead of hiding it behind a warning.
- **Validation:** `python -m pytest tests/test_golden_run.py -v -W error::UserWarning`
- **Status:** Open

---

### BH-P11-052 — gate_stories uses mock-returns-what-you-assert pattern
- **Severity:** High
- **Category:** mock-abuse
- **Location:** `tests/test_gh_interactions.py:294-298`
- **Problem:** `TestGateStories.test_all_closed` patches `gh_json` to return `[]` (empty list), then asserts `gate_stories` returns `ok=True`. The test only proves that an empty list triggers the "all closed" path — it never verifies that the function correctly queries for the right milestone or interprets real issue data. If the function's query were completely wrong (e.g., querying the wrong milestone, wrong state filter), this test would still pass because the mock bypasses the query entirely.
- **Acceptance Criteria:** Use FakeGitHub with actual milestone and closed issues, call `gate_stories` through the real query path, and verify it correctly reports "all closed" when all issues are truly closed and "N open" when some are open.
- **Validation:** `python -m pytest tests/test_gh_interactions.py::TestGateStories -v`
- **Status:** Open

---

### BH-P11-053 — gate_ci uses mock-returns-what-you-assert pattern
- **Severity:** High
- **Category:** mock-abuse
- **Location:** `tests/test_gh_interactions.py:312-335`
- **Problem:** `TestGateCI` patches `gh_json` at the function level to return pre-shaped data, then asserts on the result. The mock bypasses the actual query construction (API path, --json fields, --limit). If `gate_ci` constructs its query incorrectly, these tests still pass. The `validate_gates` integration test (test_release_gate.py:146) does exercise `gate_ci` through FakeGitHub, but the unit tests for gate_ci in isolation provide false security.
- **Acceptance Criteria:** Either (a) replace direct `gh_json` mocks with FakeGitHub-backed tests that verify the full query path, or (b) add assertions on `mock_gh.call_args` to verify the correct API arguments were passed.
- **Validation:** `python -m pytest tests/test_gh_interactions.py::TestGateCI -v`
- **Status:** Open

---

### BH-P11-054 — check_ci and check_prs mock at gh_json level, bypassing query construction
- **Severity:** Medium
- **Category:** mock-abuse
- **Location:** `tests/test_gh_interactions.py:404-471`
- **Problem:** `TestCheckCI` and `TestCheckPRs` patch `check_status.gh_json` to return fixture data, then verify report formatting. The actual gh CLI arguments (--json fields, --limit, --branch) that `check_ci()` and `check_prs()` construct are never validated. There are FakeGitHub-backed tests for `check_branch_divergence` and `check_direct_pushes` (lines 1250-1365), but no equivalent FakeGitHub-backed tests for `check_ci` or `check_prs`.
- **Acceptance Criteria:** Add FakeGitHub-backed tests for `check_ci()` and `check_prs()` that populate `fake_gh.runs` and `fake_gh.prs`, then verify the report output. This ensures the query construction is correct, not just the report formatting.
- **Validation:** `python -m pytest tests/test_gh_interactions.py::TestCheckCI tests/test_gh_interactions.py::TestCheckPRs -v`
- **Status:** Open

---

### BH-P11-055 — create_label test asserts call was made but not that label was created
- **Severity:** Medium
- **Category:** fixture-shaped
- **Location:** `tests/test_gh_interactions.py:480-489`
- **Problem:** `TestCreateLabel.test_creates_label` mocks `bootstrap_github.gh` to return empty string, calls `create_label()`, then only asserts `mock_gh.assert_called_once()` and checks the args contain "label" and "create". It never verifies that a label was actually created in any state — it only verifies that the function called `gh()` with the right subcommand. The FakeGitHub-backed version in `test_lifecycle.py:197-205` does this correctly.
- **Acceptance Criteria:** Use FakeGitHub to verify the label appears in `fake_gh.labels` with the correct name, color, and description.
- **Validation:** `python -m pytest tests/test_gh_interactions.py::TestCreateLabel -v`
- **Status:** Open

---

### BH-P11-056 — Duplicate test logic between test_lifecycle and test_hexwise_setup
- **Severity:** Low
- **Category:** duplicate
- **Location:** `tests/test_lifecycle.py:370-422` and `tests/test_hexwise_setup.py:341-407`
- **Problem:** `test_lifecycle.test_13_full_pipeline` and `test_hexwise_setup.test_full_setup_pipeline` run the same init -> labels -> milestones -> issues pipeline with different fixtures but nearly identical orchestration code (same FakeGitHub setup, same subprocess patching, same ms_numbers/ms_titles construction). The docstrings explain the distinction (minimal vs. rich fixture, loose vs. exact assertions), and `test_golden_run` adds a third variant. While the differentiation is documented, the boilerplate is repeated three times with the same bug surface.
- **Acceptance Criteria:** Extract shared pipeline orchestration into a helper (e.g., `_run_full_pipeline(config, fake_gh)`) that all three tests call, keeping test-specific assertions separate. This reduces the risk of fixing a pipeline bug in one test but not the others.
- **Validation:** `python -m pytest tests/test_lifecycle.py::TestLifecycle::test_13_full_pipeline tests/test_hexwise_setup.py::TestHexwisePipeline::test_full_setup_pipeline tests/test_golden_run.py -v`
- **Status:** Open

---

### BH-P11-057 — No tests for check_status.main() beyond --help flag
- **Severity:** Medium
- **Category:** error-path-gap
- **Location:** `tests/test_gh_interactions.py:1958-1965`
- **Problem:** `TestCheckStatusMainArgParsing` only tests the `--help` flag. There is no test for `check_status.main()` actually running with valid arguments (e.g., a sprint number), loading config, calling check functions, and producing output. The sprint_analytics.main() has comprehensive integration tests (lines 292-414), but check_status.main() — a more complex orchestrator that calls check_ci, check_prs, check_milestone, check_branch_divergence, and check_direct_pushes — has none.
- **Acceptance Criteria:** Add an integration test that patches load_config/detect_sprint and subprocess.run (via FakeGitHub), calls `check_status.main()` with a valid sprint number, and verifies the output includes CI status, PR status, and milestone progress.
- **Validation:** `python -m pytest tests/test_gh_interactions.py::TestCheckStatusMainArgParsing -v`
- **Status:** Open

---

### BH-P11-058 — No tests for check_status.write_log()
- **Severity:** Medium
- **Category:** error-path-gap
- **Location:** `skills/sprint-monitor/scripts/check_status.py` (write_log function)
- **Problem:** `check_status.write_log()` writes monitor output to a log file. It is listed in CLAUDE.md as a key function but has no direct test. If the function fails to write, truncates output, or uses wrong encoding, no test catches it.
- **Acceptance Criteria:** Test write_log with a tmpdir, verify file is created, contains expected content, handles empty input, and appends (not overwrites) on subsequent calls.
- **Validation:** `grep -n "write_log" tests/test_gh_interactions.py` (should return results after fix)
- **Status:** Open

---

### BH-P11-059 — FakeGitHub --jq not evaluated, creating fidelity gap
- **Severity:** High
- **Category:** fixture-shaped
- **Location:** `tests/fake_github.py:113-119`
- **Problem:** FakeGitHub accepts `--jq` flags but does not evaluate them. Instead, it returns pre-shaped data that "matches what production jq filters would produce." This means tests using jq-dependent endpoints (timeline API, commits API) verify the fixture shape, not the actual jq filter correctness. If production code changes its `--jq` filter, the test data won't change and tests will still pass — but production will break. The timeline endpoint (line 308-326) returns pre-filtered data assuming `| first` semantics, and commits endpoint returns pre-shaped `{sha, message, author, date}` objects.
- **Acceptance Criteria:** Document this as a known limitation in FakeGitHub (already partially done at line 113-119). Consider adding a `_JQ_FILTERS` registry that maps endpoint -> expected jq expression, and fail loudly if production sends a different jq filter than the one the test data was shaped for.
- **Validation:** Manual review of `fake_github.py` jq handling
- **Status:** Open

---

### BH-P11-060 — FakeGitHub pr_list does not implement --search flag filtering
- **Severity:** Medium
- **Category:** incomplete-setup
- **Location:** `tests/fake_github.py:107` and `tests/fake_github.py:564-593`
- **Problem:** The `_KNOWN_FLAGS` registry for `pr_list` includes `"search"` as a known flag, so FakeGitHub won't raise NotImplementedError when production code passes `--search`. However, `_pr_list` never reads or filters by the search value — it silently ignores it. If production code adds `--search "milestone:Sprint 1"` to narrow PR results, tests would pass with unfiltered data, masking bugs where the search query is malformed.
- **Acceptance Criteria:** Either implement basic search filtering in `_pr_list` (at minimum, milestone title matching) or remove `"search"` from `_KNOWN_FLAGS` so that any use of `--search` immediately raises NotImplementedError until it's properly implemented.
- **Validation:** `python -c "from tests.fake_github import FakeGitHub; f=FakeGitHub(); f.handle(['pr','list','--search','milestone:Sprint 1'])"`
- **Status:** Open

---

### BH-P11-061 — No boundary tests for extract_sp with very large values
- **Severity:** Low
- **Category:** boundary-gap
- **Location:** `tests/test_gh_interactions.py:950-998`
- **Problem:** `TestExtractSP` has 12 tests covering labels, body text, priorities, and word boundaries. But there are no tests for boundary values: `sp:0`, `sp:999`, `sp:-1`, `sp:0.5`, or extremely long body text. If extract_sp uses uncapped regex matching, a malformed input like `sp:99999999999999` could cause unexpected behavior.
- **Acceptance Criteria:** Add tests for `sp:0` (valid), `sp:-1` (should return 0), `sp:999` (valid), and a body with `SP: 99999` to verify no integer overflow or performance issues.
- **Validation:** `python -m pytest tests/test_gh_interactions.py::TestExtractSP -v`
- **Status:** Open

---

### BH-P11-062 — No negative test for parse_simple_toml with deeply nested sections
- **Severity:** Low
- **Category:** boundary-gap
- **Location:** `tests/test_pipeline_scripts.py:493-673`
- **Problem:** `TestParseSimpleToml` has excellent edge-case coverage (empty input, malformed quotes, multiline arrays, single quotes, escaped quotes, nested sections, duplicate sections). But there is no test for deeply nested section headers like `[a.b.c.d.e]` or section headers with special characters. The custom TOML parser could fail on deeply nested paths due to recursive dict construction.
- **Acceptance Criteria:** Add tests for `[a.b.c.d]` (4 levels deep), `[a.b]` followed by `[a.c]` (sibling sections), and verify all produce correct nested dicts.
- **Validation:** `python -m pytest tests/test_pipeline_scripts.py::TestParseSimpleToml -v`
- **Status:** Open

---

### BH-P11-063 — No test for sync_tracking.main() happy path (end-to-end)
- **Severity:** Medium
- **Category:** error-path-gap
- **Location:** `tests/test_gh_interactions.py:1920-1933`
- **Problem:** `TestSyncTrackingMainArgParsing` tests only error paths (no args, non-numeric args, --help). There is no test for `sync_tracking.main()` running successfully with a valid sprint number against a FakeGitHub-populated state. The lifecycle test (`test_lifecycle.py:494-500`) exercises `sync_tracking.create_from_issue()` directly, but never calls `main()` with a real argument and config.
- **Acceptance Criteria:** Add a test that patches load_config, find_milestone_title, and subprocess.run, calls `sync_tracking.main()` with `sys.argv = ["sync_tracking.py", "1"]`, and verifies tracking files were created and correct output was produced.
- **Validation:** `python -m pytest tests/test_gh_interactions.py::TestSyncTrackingMainArgParsing -v`
- **Status:** Open

---

### BH-P11-064 — test_label_error_handled asserts on mock internals, not behavior
- **Severity:** Medium
- **Category:** fixture-shaped
- **Location:** `tests/test_gh_interactions.py:491-503`
- **Problem:** `test_label_error_handled` patches `bootstrap_github.gh` to raise RuntimeError, then asserts on `mock_print.call_args[0][0]` to verify a warning message was printed. This tests the internal implementation detail (print call shape) rather than the observable behavior (label not created, no crash, warning emitted). If the function changes to use `logging.warning()` or `sys.stderr.write()`, the test breaks even though the behavior is identical.
- **Acceptance Criteria:** Assert on the behavioral outcome: (a) the function did not raise an exception, (b) the function returned a falsy/failure indicator, and (c) some form of warning was emitted (capture stderr or check logging).
- **Validation:** `python -m pytest tests/test_gh_interactions.py::TestCreateLabel::test_label_error_handled -v`
- **Status:** Open

---

### BH-P11-065 — do_release tests mock internal functions, masking integration bugs
- **Severity:** Medium
- **Category:** mock-abuse
- **Location:** `tests/test_release_gate.py:517-584`
- **Problem:** `TestDoRelease.test_happy_path` patches 5 internal functions: `calculate_version`, `write_version_to_toml`, `subprocess.run`, `find_milestone_number`, and `gh`. While each individual gate function has tests, the do_release test verifies only that the function calls its dependencies in the right order — not that the full pipeline produces correct artifacts. If `do_release` passes the wrong milestone title to `find_milestone_number` or constructs the wrong `gh release create` args, the mocks hide the bug.
- **Acceptance Criteria:** Add one integration test for do_release that only patches at system boundaries (subprocess.run for git commands, gh for GitHub API) without mocking internal functions. Use FakeGitHub + real file I/O on a tmpdir to verify the full pipeline.
- **Validation:** `python -m pytest tests/test_release_gate.py::TestDoRelease -v`
- **Status:** Open

---

### BH-P11-066 — No test for commit.main() happy path (successful commit)
- **Severity:** Medium
- **Category:** error-path-gap
- **Location:** `tests/test_gh_interactions.py:1968-1981`
- **Problem:** `TestCommitMainArgParsing` tests only error paths (no args, --help). The happy path — where `commit.main()` validates a message, checks atomicity, and executes `git commit` — is never tested end-to-end. Individual components (`validate_message`, `check_atomicity`) have unit tests, but the orchestration in `main()` is untested.
- **Acceptance Criteria:** Add a test that patches `subprocess.run`, calls `commit.main()` with `sys.argv = ["commit.py", "-m", "feat: add feature"]`, and verifies the commit was attempted with the correct message.
- **Validation:** `python -m pytest tests/test_gh_interactions.py::TestCommitMainArgParsing -v`
- **Status:** Open

---

### BH-P11-067 — TestComputeWorkload only checks count, not SP distribution
- **Severity:** Low
- **Category:** missing-negative
- **Location:** `tests/test_sprint_analytics.py:218-250`
- **Problem:** `TestComputeWorkload.test_counts_per_persona` verifies issue count per persona but doesn't test SP-weighted workload (if the function computes it). It also doesn't test the case where a single persona has all issues (workload imbalance) or where issues have mixed milestone assignments. The negative test (`test_no_persona_labels`) only verifies an empty dict is returned.
- **Acceptance Criteria:** Add tests for (a) persona with issues that have SP labels (verify SP is counted, not just issue count), (b) issues with mixed milestones to verify milestone filtering, and (c) an imbalanced workload where one persona has 80% of the work.
- **Validation:** `python -m pytest tests/test_sprint_analytics.py::TestComputeWorkload -v`
- **Status:** Open

---

### BH-P11-068 — FakeGitHub issue_create does not validate label existence
- **Severity:** Low
- **Category:** incomplete-setup
- **Location:** `tests/fake_github.py:349-390`
- **Problem:** FakeGitHub's `_issue_create` validates that the milestone exists (line 371-376) but does not validate that labels exist. Real GitHub silently accepts unknown labels in issue creation, so this matches production behavior. However, it means tests can pass with typo'd labels (e.g., `"kanban:tod"` instead of `"kanban:todo"`), and the test would show the wrong label propagating through the system without detection.
- **Acceptance Criteria:** This is a known limitation, not a bug. Add a comment in FakeGitHub documenting this intentional non-validation. Optionally, add a `strict_labels=True` mode that validates labels exist before creating issues.
- **Validation:** Manual review
- **Status:** Open

---

### BH-P11-069 — traceability tests depend on hexwise fixture content without pinning
- **Severity:** Low
- **Category:** flaky-test-patterns
- **Location:** `tests/test_pipeline_scripts.py:98-153`
- **Problem:** `TestTraceability` tests (`test_parse_stories_finds_all`, `test_traceability_no_gaps`, `test_traceability_prd_coverage`) assert exact counts (17 stories, 0 gaps) based on the current hexwise fixture. If someone adds a story to the fixture without updating test case links, `test_traceability_no_gaps` will fail with an obscure assertion error. The tests are not fragile per se, but the coupling between fixture content and test assertions is implicit rather than documented.
- **Acceptance Criteria:** Add a comment in the test documenting which fixture files these counts depend on (e.g., "17 stories from E-0101, E-0102, E-0103, E-0201, E-0202, E-0203 epic files"). Consider extracting expected story IDs as a test constant.
- **Validation:** `python -m pytest tests/test_pipeline_scripts.py::TestTraceability -v`
- **Status:** Open

---

### BH-P11-070 — No test for sprint_teardown.main() with unknown files (interactive path)
- **Severity:** Medium
- **Category:** error-path-gap
- **Location:** `tests/test_sprint_teardown.py:448-522`
- **Problem:** `TestTeardownMainDryRun` and `TestTeardownMainExecute` test dry-run and force modes. But there is no test for the case where unknown files exist and the user needs to be prompted. The `classify_entries` function correctly identifies unknown files (tested in `TestClassifyEntries`), but the `main()` path that handles unknown files in interactive mode is untested.
- **Acceptance Criteria:** Add a test for `main()` with `--force` flag and unknown files present, verifying that unknown files are preserved (not deleted). Also add a test with patched `input()` for the interactive unknown-file prompt.
- **Validation:** `python -m pytest tests/test_sprint_teardown.py -v`
- **Status:** Open

---

### BH-P11-071 — validate_anchors main() never tested
- **Severity:** Medium
- **Category:** error-path-gap
- **Location:** `tests/test_validate_anchors.py`
- **Problem:** The test file covers `resolve_namespace`, `find_anchor_defs`, `find_anchor_refs`, `check_anchors`, and `fix_missing_anchors` — but never tests `validate_anchors.main()`. The main() function parses CLI args (--fix, --check), discovers files, and orchestrates the check/fix flow. If main() has a bug in argument parsing or file discovery, no test catches it.
- **Acceptance Criteria:** Add tests for `main()` with `--check` mode (verify exit code on clean/broken refs) and `--fix` mode (verify anchors are inserted).
- **Validation:** `python -m pytest tests/test_validate_anchors.py -v`
- **Status:** Open

---

### BH-P11-072 — BH-001 concatenated JSON test verifies parsing logic inline instead of through gh_json
- **Severity:** Low
- **Category:** fixture-shaped
- **Location:** `tests/test_gh_interactions.py:2186-2206`
- **Problem:** `TestBH001PaginatedJson.test_concatenated_json_arrays` manually implements JSON parsing logic inline in the test (using `json.JSONDecoder().raw_decode()`) instead of testing the actual `gh_json()` function with concatenated input. The test proves that the JSON parsing algorithm works in isolation, but doesn't verify that `gh_json()` actually uses this algorithm when processing paginated output.
- **Acceptance Criteria:** Test `gh_json()` directly by mocking `subprocess.run` to return concatenated JSON arrays (simulating `--paginate` output) and verifying the merged result.
- **Validation:** `python -m pytest tests/test_gh_interactions.py::TestBH001PaginatedJson -v`
- **Status:** Open

---

### BH-P11-073 — No test for sync_backlog.main() with missing sprint-config
- **Severity:** Low
- **Category:** error-path-gap
- **Location:** `tests/test_sync_backlog.py:210-298`
- **Problem:** `TestMain` tests first-run (debounce), second-run (sync), and third-run (no_changes). But there's no test for `main()` when `sprint-config/` doesn't exist or when `load_config()` raises `ConfigError`. If `main()` doesn't handle this gracefully, it would crash with an uncaught exception.
- **Acceptance Criteria:** Add a test that calls `sync_backlog.main()` in a directory with no `sprint-config/` and verifies it either returns an error status or exits cleanly with a message.
- **Validation:** `python -m pytest tests/test_sync_backlog.py::TestMain -v`
- **Status:** Open

---

### BH-P11-074 — TestCheckMilestone uses hand-rolled call-count side_effect instead of FakeGitHub
- **Severity:** Low
- **Category:** fixture-shaped
- **Location:** `tests/test_gh_interactions.py:1666-1722`
- **Problem:** `TestCheckMilestone._mock_gh_json` implements a call-count-based side_effect that returns milestones on the first call and issues on the second. This is fragile: if `check_milestone()` adds a third gh_json call (e.g., for PR data), the test would return the wrong data for the new call without failing. FakeGitHub-backed tests would handle this naturally.
- **Acceptance Criteria:** Replace the hand-rolled call counter with FakeGitHub-backed tests. Populate `fake_gh.milestones` and `fake_gh.issues`, then call `check_milestone()` through the patched subprocess path.
- **Validation:** `python -m pytest tests/test_gh_interactions.py::TestCheckMilestone -v`
- **Status:** Open

---

## Summary

| Severity | Count |
|----------|-------|
| Critical | 0 |
| High | 4 |
| Medium | 10 |
| Low | 11 |

### Key Themes

1. **Mock-returns-what-you-assert (4 findings):** Several gate function tests (`gate_stories`, `gate_ci`, `gate_prs`) patch `gh_json` to return pre-shaped data, then assert on the result. This tests report formatting but not query construction. The `validate_gates` integration test in `test_release_gate.py` partially compensates but doesn't cover all paths.

2. **Missing main() integration tests (5 findings):** Most scripts have unit tests for individual functions but no tests for their `main()` entry points. `check_status.main()`, `sync_tracking.main()` happy path, `commit.main()` happy path, `validate_anchors.main()`, and `sync_backlog.main()` error path are all untested.

3. **FakeGitHub fidelity gaps (3 findings):** `--jq` not evaluated, `--search` silently ignored, and labels not validated. These gaps mean production code changes can go undetected when the FakeGitHub fixture doesn't faithfully simulate the real GitHub CLI behavior.

4. **Assertion-free or degraded tests (2 findings):** One test has zero assertions, and one test silently skips its primary purpose (golden snapshot comparison) when recordings are absent.

### What the Test Suite Does Well

- **Word-boundary testing is thorough:** `find_milestone`, `extract_sp`, `get_linked_pr`, `renumber_stories` all have adversarial word-boundary tests preventing substring false positives.
- **Error handling is tested:** API errors, missing files, malformed inputs, and edge cases are covered across most scripts.
- **FakeGitHub flag enforcement is excellent:** Unknown flags raise `NotImplementedError`, preventing silent green-bar on untested code paths.
- **Negative validation tests are comprehensive:** `validate_project` has tests for missing files, missing TOML keys, too few personas, empty rules, and no milestones.
- **TOML parser edge cases are well-covered:** Single/double quotes, escaped characters, multiline arrays, unterminated arrays, nested sections, duplicate sections, and hyphenated keys all have dedicated tests.
