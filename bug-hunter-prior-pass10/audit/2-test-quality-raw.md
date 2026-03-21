# Test Quality Audit — Pass 10 Raw Findings

Auditor: Adversarial test quality audit after 9 prior bug-hunter passes.
Date: 2026-03-15

---

## CRITICAL

### C-01: FakeGitHub `--search` flag silently ignored — `compute_review_rounds` test verifies mock routing, not production filtering

**Location:** `tests/test_sprint_analytics.py:134-164` + `tests/fake_github.py:541-570`
**Description:** Production `compute_review_rounds()` calls `gh pr list --search "milestone:Sprint 1"` (line 87 of `sprint_analytics.py`). FakeGitHub's `_pr_list` handler does NOT implement `--search` filtering — the `search` flag is listed in `_KNOWN_FLAGS["pr_list"]` (line 108) so it passes the flag check, but its value is silently discarded. The test at line 136 manually injects PRs with the correct milestone title into `self.gh.prs`, so `pr_list` returns them — but this tests FakeGitHub's milestone field, not the `--search` filtering that production relies on.

**Evidence:**
```python
# fake_github.py line 108 — search accepted but never used:
"pr_list": frozenset(("json", "state", "limit", "search")),

# fake_github.py _pr_list (lines 541-570) — no search implementation:
# Only filters on state and limit; search is accepted and dropped.
```

**Impact:** If production's `--search` parameter were malformed (e.g., wrong quoting), no test would catch it. The test gives a false green bar.

---

### C-02: `compute_review_rounds` test injects pre-computed `reviews` field that production receives from `--json reviews`

**Location:** `tests/test_sprint_analytics.py:136-153`
**Description:** The test manually adds a `reviews` key to PR dicts in `self.gh.prs`. In production, `--json number,title,labels,milestone,reviews` asks the GitHub API to include nested review objects. FakeGitHub's `_pr_create` does not store a `reviews` field on PRs — it's only added via `_pr_review`. The test bypasses the PR creation path entirely and injects the exact data shape the production code expects.

**Evidence:**
```python
# Test directly injects:
self.gh.prs.append({
    "number": 1, ...
    "reviews": [
        {"state": "CHANGES_REQUESTED"},
        {"state": "APPROVED"},
    ],
})
```
The test is verifying that the code correctly counts items in a list it was handed — it cannot detect if the real GitHub API returns reviews in a different shape (e.g., nested under `nodes`, different key names, etc.).

**Impact:** If `sprint_analytics.py` mishandled the real review response format, this test would not catch it.

---

### C-03: Golden run test silently skips all golden comparisons when recordings absent

**Location:** `tests/test_golden_run.py:93-109`
**Description:** When `GOLDEN_RECORD=1` is not set AND no golden recordings exist (the default state for CI and fresh clones), `_check_or_record` issues a `warnings.warn()` but **does not skip or fail**. This means all 5 golden snapshot assertions (lines 145-207) silently degrade to "just run the pipeline and check counts" — identical to what `test_hexwise_setup` already does.

**Evidence:**
```python
# test_golden_run.py lines 101-109:
else:
    # Don't skip — let the test continue so non-golden assertions
    # still provide value. Golden comparisons are simply skipped.
    import warnings
    warnings.warn(...)
```
The golden assertions are the unique value of this test; without them, it duplicates `test_hexwise_setup` exactly. There is no CI mechanism to ensure golden recordings are ever generated or validated.

**Impact:** The golden regression test provides zero regression-catching value unless someone manually runs `GOLDEN_RECORD=1` and commits the recordings. Since `tests/golden/recordings/` is not in the repo (no glob hits), this test has **never** performed a golden comparison.

---

## HIGH

### H-01: `TestComputeReviewRounds.test_counts_review_events` — FakeGitHub `pr list` does not filter by `--search`/milestone; test pre-loads exact matches

**Location:** `tests/test_sprint_analytics.py:134-164`
**Description:** (Expanded from C-01) Production calls `gh pr list --search "milestone:Sprint 1"`. FakeGitHub returns ALL PRs regardless of search. The test only inserts PRs with `milestone: {"title": "Sprint 1"}`, so the milestone filtering in `compute_review_rounds()` (lines 94-98 of sprint_analytics.py) never encounters a PR that should be excluded. If that filter were removed from production, the test would still pass.

**Evidence:** Insert a PR with `milestone: {"title": "Sprint 2"}` into the test — it would be returned by FakeGitHub but filtered out by production code. The test never exercises this filtering branch.

---

### H-02: `TestCheckCI.test_failing_run` mocks both `gh_json` AND `gh` — the gh mock hides whether check_ci actually calls gh() correctly

**Location:** `tests/test_gh_interactions.py:425-436`
**Description:** The test patches both `check_status.gh_json` and `check_status.gh`. The `gh` mock returns `"error: something broke\nfatal: test failed"`, but the test never asserts what arguments `gh` was called with. If `check_ci()` changed how it fetches failure logs (different `gh run view` args), the test would still pass.

**Evidence:**
```python
@patch("check_status.gh")
@patch("check_status.gh_json")
def test_failing_run(self, mock_gh_json, mock_gh):
    mock_gh.return_value = "error: something broke\nfatal: test failed"
    # ... no assertion on mock_gh.call_args
```

---

### H-03: `test_golden_full_setup_pipeline` duplicates `test_full_setup_pipeline` in test_hexwise_setup when recordings are absent

**Location:** `tests/test_golden_run.py:111-209` vs `tests/test_hexwise_setup.py:341-407`
**Description:** Both tests: (1) copy hexwise fixture, (2) git init, (3) generate config, (4) bootstrap labels/milestones, (5) populate issues, (6) assert counts (labels > N, milestones == 3, issues == 17). The golden test's docstring explicitly acknowledges this overlap but relies on golden snapshots for differentiation — which, per C-03, never execute.

**Evidence:** The non-golden assertions in `test_golden_run.py` are:
- `self.assertGreater(len(self.fake_gh.labels), 10)` (vs `>= 17` in hexwise_setup)
- `self.assertEqual(len(self.fake_gh.milestones), 3)` (same)
- `self.assertEqual(len(self.fake_gh.issues), 17)` (same)
- `self.assertIn("cargo test", yaml_content)` (CI, also in hexwise_setup)

These are strictly weaker versions of the same assertions in `test_hexwise_setup`.

---

### H-04: `test_sprint_analytics.TestComputeWorkload.test_counts_per_persona` — issues lack required fields, testing FakeGitHub tolerance rather than production

**Location:** `tests/test_sprint_analytics.py:181-195`
**Description:** The test inserts issues with only `number`, `labels`, `milestone`, and `state` — missing `title`, `body`, and `closedAt`. Production's `gh issue list --json labels --limit 500` returns only the `labels` field (per the `--json` filter), so this works. However, FakeGitHub returns ALL fields on each issue dict. The test works by accident — it relies on the json_fields filtering in FakeGitHub. If FakeGitHub's `_filter_json_fields` had a bug, the missing fields could cause KeyErrors in production code that this test would never surface.

---

### H-05: `TestValidateGates.test_all_pass` — gate_tests and gate_build pass trivially because config has empty commands

**Location:** `tests/test_release_gate.py:146-163`
**Description:** The `config` passed has `"check_commands": []` and `"build_command": ""`. This means `gate_tests` and `gate_build` return `(True, "No check_commands configured")` and `(True, "No build_command configured")` respectively — they skip testing entirely. The assertion `self.assertTrue(all(r[1] for r in results))` passes because the gates trivially pass, not because they actually validated anything.

**Evidence:**
```python
config = {
    "project": {"base_branch": "main"},
    "ci": {"check_commands": [], "build_command": ""},
}
```

This test claims to verify "All gates pass" but two of the five gates are auto-pass due to empty config. There is no test that runs `validate_gates` end-to-end with non-trivial test/build commands through FakeGitHub.

---

### H-06: `check_status.check_milestone` test uses FakeGitHub but production calls `list_milestone_issues` which calls `gh_json`

**Location:** `tests/test_lifecycle.py:548-555`
**Description:** The `check_milestone` function calls `list_milestone_issues()` which calls `gh_json()` which calls `gh()` which calls `subprocess.run`. The test patches `subprocess.run` with FakeGitHub. Production code constructs: `gh issue list --milestone "Sprint 1: Foundation" --state all --json number,title,labels,body,closedAt --limit 500`. FakeGitHub processes this via `_issue_list` which filters by milestone title. The pre-loaded issues all have `milestone: {"title": "Sprint 1: Foundation"}`. This works, but the assertion `self.assertIn("2/4", report_text)` checks a string format, not the underlying data. If `check_milestone` changed its formatting (e.g., from `2/4` to `2 of 4`), the test would fail for the wrong reason.

---

### H-07: Multiple tests assert only string containment on report output, not structured data

**Location:** Multiple files
**Description:** Many tests assert `self.assertIn("some substring", report_text)` on human-readable report strings rather than checking the structured return values. This makes tests brittle to formatting changes and can also pass when the substring appears in an unrelated context.

**Evidence examples:**
- `test_lifecycle.py:553`: `self.assertIn("2/4", report_text)` — could match any "2/4" string
- `test_lifecycle.py:554`: `self.assertIn("50%", report_text)` — same issue
- `test_lifecycle.py:556`: `self.assertIn("8/13 SP", report_text)` — more specific, better
- `test_gh_interactions.py:421`: `self.assertIn("1 passing", report[0])` — first element only
- `test_gh_interactions.py:458-459`: `self.assertIn("1 open", report[0])` and `self.assertIn("1 approved", report[0])` — both must be in the same string element

---

### H-08: `test_do_sync_idempotent` verifies idempotency via FakeGitHub issue count, not via get_existing_issues logic

**Location:** `tests/test_sync_backlog.py:197-207`
**Description:** The test calls `do_sync` twice and checks that issue count doesn't change. But `do_sync` internally calls `populate_issues.get_existing_issues()` to check for duplicates, which calls `gh issue list`. FakeGitHub's `_issue_list` returns ALL issues in `self.issues`. So when `do_sync` runs the second time, `get_existing_issues` finds the issues from the first run (because they're in the flat list) and skips them. This works, but it's testing FakeGitHub's state persistence, not the actual idempotency mechanism.

If `get_existing_issues()` had a bug where it failed to parse issue titles to extract story IDs, the second `do_sync` call would try to create duplicate issues — and FakeGitHub would happily create them (it has no unique constraint on titles). The test would then fail, which is good. But the test would NOT catch a bug where `create_issue` succeeded but FakeGitHub returned the wrong URL format, causing `get_existing_issues` to miss the existing issue.

---

## MEDIUM

### M-01: `test_extract_voices_from_epics_returns_empty` asserts on fixture data rather than testing logic

**Location:** `tests/test_pipeline_scripts.py:48-54`
**Description:** This test asserts that Hexwise epic files have no team voice blocks. If someone added a voice block to the fixture, this test would fail — but that's a fixture change, not a code bug. The test name suggests it's testing the "returns empty" path of `extract_voices`, but it's actually testing the fixture.

---

### M-02: `TestParseSimpleToml.test_malformed_quotes` tests the parser's error handling but the expected behavior is ambiguous

**Location:** `tests/test_pipeline_scripts.py:501-507`
**Description:** The test asserts that `parse_simple_toml('key = "unterminated')` returns `{"key": '"unterminated'}`. This is the raw fallback behavior, not a documented contract. If the parser changed to raise `ValueError` on unterminated strings (arguably more correct), this test would break. The test documents current behavior but doesn't distinguish "intended" from "accidental."

---

### M-03: `test_coverage_no_actual_tests` — complex assertion chain that partially duplicates itself

**Location:** `tests/test_pipeline_scripts.py:165-186`
**Description:** The test checks:
1. `len(report["planned"]) > 0`
2. `len(report["implemented"]) == 0`
3. `planned_ids == missing_ids` (set equality)
4. `planned_ids` is truthy (redundant with #1)
5. Spot-check for TC-/GP- prefixed IDs
6. `len(report.get("matched", [])) == 0`

Step 3 (`planned_ids == missing_ids`) already implies steps 1 and 4 (planned is non-empty), making those assertions redundant. Step 6 is a valid addition but uses `.get("matched", [])` defensively, suggesting uncertainty about the return contract.

---

### M-04: `TestGateStories.test_all_closed` mocks `gh_json` to return `[]` — testing the "no open issues" interpretation

**Location:** `tests/test_gh_interactions.py:293-298`
**Description:** The test patches `release_gate.gh_json` to return `[]` (empty list). This is supposed to mean "all issues are closed" but it could also mean "the milestone doesn't exist" or "the API returned an error as empty list." The test doesn't distinguish between these cases. In production, `gate_stories` calls `gh_json(["issue", "list", "--milestone", ms_title, "--state", "open", ...])` — an empty result means no open issues, which is correct. But the mock bypasses the actual `--state open` filtering logic.

---

### M-05: `test_pr_for_different_milestone` passes because the mock returns a PR with Sprint 2 milestone

**Location:** `tests/test_gh_interactions.py:354-361`
**Description:** `gate_prs` calls `gh_json(["pr", "list", "--state", "open", ...])` and then filters by milestone title. The mock returns one PR with `milestone: {"title": "Sprint 2"}`. The test asserts `gate_prs("Sprint 1")` passes. This correctly tests the milestone filtering in `gate_prs`. However, since `gh_json` is fully mocked, the test doesn't verify that the actual `gh pr list` arguments would exclude PRs from other milestones. Production might send a `--search` filter that makes this server-side, in which case the client-side filter in `gate_prs` is defense-in-depth — the test only validates the defense layer, not the primary filter.

---

### M-06: `test_format_story_section_empty_dict` asserts on default values that are undocumented

**Location:** `tests/test_pipeline_scripts.py:379-384`
**Description:** `_format_story_section({})` is tested to produce "US-XXXX" and "Untitled". These defaults are implementation details. If someone changed the default story ID placeholder from "US-XXXX" to "STORY-XXXX", this test would catch the change — but it's testing a code smell (calling with empty dict), not a user-facing behavior.

---

### M-07: `test_parse_saga_malformed_file` asserts `result["title"]` equals the first line of prose

**Location:** `tests/test_pipeline_scripts.py:468-485`
**Description:** The test asserts `result["title"] == "This is just random text."`. This hardcodes the parser's behavior of treating the first line as the title, which is an implementation detail. If the parser changed to return `""` for files without `#`-prefixed headings, this test would break.

---

### M-08: `FakeGitHub._handle_api` for `/commits` endpoint returns ALL `commits_data` without filtering

**Location:** `tests/fake_github.py:276-279`
**Description:** The production code calls `gh api repos/{owner}/{repo}/commits -f sha={branch} -f since={iso}` with `--jq` filtering. FakeGitHub accepts the `-f` flags but doesn't use `sha` or `since` to filter results. Tests pre-load exactly the commits they want to find, so this doesn't cause failures — but it means the tests can't verify that production correctly passes the `since` date filter or `sha` branch filter.

**Evidence:**
```python
# fake_github.py line 276-279:
if path.endswith("/commits"):
    return self._ok(json.dumps(self.commits_data))
```

---

### M-09: `TestDoRelease.test_happy_path` asserts on subprocess call ordering by index — fragile to implementation changes

**Location:** `tests/test_release_gate.py:451-470`
**Description:** The test asserts `run_cmds[0][1] == "status"`, `run_cmds[1][1] == "rev-parse"`, `run_cmds[2][1] == "add"`, etc. If `do_release` added a new step (e.g., `git fetch` before status), all index-based assertions would break even though the logic is correct. This is a test maintenance burden.

---

### M-10: `TestCheckMilestone` indirectly tests through multiple layers with no unit test of the function itself

**Location:** `tests/test_lifecycle.py:548-555`
**Description:** `check_milestone(1)` calls `find_milestone(1)` -> `gh_json` -> `subprocess.run` -> FakeGitHub, then `list_milestone_issues()` -> `gh_json` -> same chain. The test exercises the full call chain with FakeGitHub, which is good for integration, but there is no isolated unit test of `check_milestone` with mocked `list_milestone_issues` and `find_milestone`. A bug in either helper could mask the behavior of `check_milestone` itself.

---

### M-11: `test_annotation_column_ref` typo in test class — named `TestFindAnchorRefs` but tests an `anchor_column_ref` pattern

**Location:** `tests/test_validate_anchors.py:115-120`
**Description:** Test method `test_anchor_column_ref` tests a `§` reference appearing in the first column of a markdown table. The test is correctly testing `find_anchor_refs()` but the name `anchor_column_ref` is slightly misleading — it tests when `§` IS the column content rather than being embedded in a backtick reference. Minor naming issue but could lead to confusion about test coverage.

---

### M-12: No test for `sprint_analytics.main()` entry point

**Location:** `scripts/sprint_analytics.py:191`
**Description:** The `main()` function in `sprint_analytics.py` is the CLI entry point that orchestrates `compute_velocity`, `compute_review_rounds`, `compute_workload`, and `format_report`. It is never called in any test. While the individual functions are tested, integration issues in `main()` (e.g., wrong argument passing, missing error handling) would not be caught.

---

### M-13: No test for `commit.run_commit()` or `commit.main()`

**Location:** `scripts/commit.py:93` and `scripts/commit.py:105`
**Description:** `run_commit()` is the function that actually runs `git commit` with the validated message. It is never tested. `main()` is the CLI entry point that ties `validate_message`, `check_atomicity`, and `run_commit` together. Neither is tested. Only `validate_message` and `check_atomicity` have coverage.

---

### M-14: No test for `check_status.write_log()` or `check_status.main()`

**Location:** `skills/sprint-monitor/scripts/check_status.py:309` and `:325`
**Description:** `write_log()` writes monitoring output to a file. `main()` orchestrates all check functions and writes the log. Neither is tested. Individual check functions (`check_ci`, `check_prs`, `check_milestone`, `check_branch_divergence`, `check_direct_pushes`) have coverage, but integration bugs in `main()` are uncovered.

---

### M-15: No test for `sync_tracking.sync_one()` — the primary sync function

**Location:** `skills/sprint-run/scripts/sync_tracking.py:217`
**Description:** `sync_one()` is the main function that syncs a single tracking file from GitHub state. It reads the existing tracking file, queries GitHub for the linked PR, and updates the file. Only `create_from_issue` (line 265) is tested in `test_lifecycle.py`. The `sync_one` update path is never tested — it's called in `test_lifecycle.py`'s monitoring pipeline test but only indirectly through `create_from_issue`.

---

### M-16: No test for `update_burndown.load_tracking_metadata()`

**Location:** `skills/sprint-run/scripts/update_burndown.py:118`
**Description:** `load_tracking_metadata()` reads YAML frontmatter from tracking files. It is used by `main()` but neither function is directly tested. `write_burndown` and `update_sprint_status` are tested in `test_lifecycle.py`.

---

## LOW

### L-01: `TestTeamVoices.test_continuation_lines_joined` assertion is weak

**Location:** `tests/test_pipeline_scripts.py:81-88`
**Description:** The test asserts `self.assertIn("compiler", rusti_s01[0]["quote"].lower())` to verify multi-line quotes are joined. The word "compiler" could appear even in a single-line quote. A stronger assertion would check that the quote contains content from multiple blockquote lines (e.g., checking for two distinct concepts that span lines).

---

### L-02: `test_parse_stories_finds_all` hardcodes expected count of 17

**Location:** `tests/test_pipeline_scripts.py:101-107`
**Description:** If the hexwise fixture is extended with new stories, this test will fail even though the parser is correct. This is a fixture-coupling issue, not a code quality issue. The count 17 is correct for the current fixture.

---

### L-03: `test_traceability_no_gaps` depends on fixture completeness

**Location:** `tests/test_pipeline_scripts.py:115-121`
**Description:** `self.assertEqual(report["stories_without_tests"], [])` passes because the hexwise fixture has complete test case links. If a new story were added to the fixture without test links, this test would fail. This is intentional (regression detection) but the test name doesn't communicate that it's testing the fixture, not the code.

---

### L-04: `test_all_mapped_files_exist` is a canary test that validates repo state, not code logic

**Location:** `tests/test_validate_anchors.py:40-43`
**Description:** This test iterates `NAMESPACE_MAP` and checks that all referenced files exist on disk. It will fail if a file is renamed without updating the map. This is useful as a repo-health check but it's testing configuration, not code behavior.

---

### L-05: Several temp files created with `delete=False` in `test_validate_anchors.py` are never cleaned up

**Location:** `tests/test_validate_anchors.py:56-98`, `tests/test_validate_anchors.py:108-141`
**Description:** Multiple `NamedTemporaryFile(delete=False)` calls create temp files that are never unlinked. While these are in `/tmp` and will eventually be cleaned by the OS, best practice is to clean up. The tests in `TestCheckAnchors` and `TestFixMode` use `tempfile.mkdtemp()` properly, but `TestFindAnchorDefs` and `TestFindAnchorRefs` do not.

---

### L-06: `test_valid_fix_with_scope` does not assert on `err`

**Location:** `tests/test_gh_interactions.py:65-66`
**Description:** The test checks `self.assertTrue(ok)` but doesn't verify `err == ""`. If the validation returned `ok=True` with a warning in `err`, the test would still pass. Minor inconsistency with `test_valid_feat` which asserts both.

---

### L-07: `test_all_valid_types` loops but a failure message doesn't identify which type failed

**Location:** `tests/test_gh_interactions.py:76-80`
**Description:** The loop iterates all valid types and uses `self.assertTrue(ok, f"Type '{t}' should be valid")`. This is actually good practice — the error message includes the type. However, only `ok` is asserted, not `err`. Minor.

---

### L-08: `TestScannerMinimalProject` and `TestScannerPythonProject` create real filesystem fixtures but don't test git remote detection

**Location:** `tests/test_pipeline_scripts.py:1095-1209` and `:933-1088`
**Description:** Both test classes create project directories without `.git/config`, so `detect_repo()` would return a low-confidence fallback. This is intentional (testing scanner behavior without git) but means the git-remote-parsing path of `ProjectScanner` is only tested via `test_hexwise_setup` and `test_lifecycle`.

---

### L-09: `test_limit_hit_fails_gate` patches `warn_if_at_limit` but doesn't verify it was called

**Location:** `tests/test_gh_interactions.py:363-373`
**Description:** The test patches `release_gate.warn_if_at_limit` as a no-op. The mock is available as `mock_warn` but `mock_warn.assert_called()` is never invoked. The test only checks that the gate returns `(False, ...)` with "truncated" in the detail. This is fine for verifying the gate logic but doesn't confirm that the warning function is actually triggered.

---

### L-10: `test_unknown_namespace_raises` only tests `KeyError`, not the error message

**Location:** `tests/test_validate_anchors.py:36-38`
**Description:** `self.assertRaises(KeyError)` without checking the exception message. Minor — the test correctly verifies the error type.

---

### L-11: `_make_subprocess_side_effect` in test_release_gate.py is shared test infrastructure that itself has no tests

**Location:** `tests/test_release_gate.py:344-384`
**Description:** This helper function builds complex conditional logic to simulate various failure modes. A bug in the helper (e.g., wrong detection of `git push` args) could cause test false positives. However, since it's test infrastructure, testing it would be recursive. Low priority.

---

## Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 3 |
| HIGH | 8 |
| MEDIUM | 16 |
| LOW | 11 |
| **Total** | **38** |

### Themes

1. **FakeGitHub fidelity gaps (C-01, C-02, H-01, H-04, M-08):** FakeGitHub accepts flags it doesn't implement (`--search`, `--jq`, `-f since=`). Tests pre-load exact data shapes, so the mock returns what the test expects regardless of whether production's query logic is correct. This is the single biggest class of quality issue.

2. **Golden test provides zero value (C-03, H-03):** The golden run test framework is architecturally sound but operationally inactive. No golden recordings exist in the repository, so the test degrades to a duplicate of `test_hexwise_setup` with weaker assertions.

3. **Missing coverage for orchestration functions (M-12 through M-16):** Individual helpers are well-tested but the `main()` and top-level orchestration functions in `sprint_analytics`, `commit`, `check_status`, `sync_tracking`, and `update_burndown` have no direct test coverage.

4. **String-based assertions on report output (H-07, M-09):** Many tests check for substrings in human-readable report text rather than structured return values. This makes tests fragile to formatting changes and can produce false positives when substrings match unintended content.

5. **Mock-at-wrong-boundary tests (H-02, M-04, M-05):** Several tests mock at `gh_json` level, which skips the argument construction in production code. If production passes wrong flags to `gh`, the mock never sees it. Tests using FakeGitHub (via `subprocess.run` patching) are generally better at catching this class of bug.
