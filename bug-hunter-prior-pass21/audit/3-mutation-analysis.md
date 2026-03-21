# Mutation Survival Analysis

Systematic analysis of 8 high-risk production functions. For each function,
specific mutations were evaluated against all test coverage to identify
mutations that would survive (tests still pass with broken code).

---

### 1. parse_simple_toml() -- Mutation Survival Analysis

**Production code:** `scripts/validate_config.py:117-190`

**Tests examined:**
- `tests/test_property_parsing.py::TestParseSimpleToml` (11 property-based tests + 5 explicit)
- `tests/test_bugfix_regression.py::TestBH008NestedArrays`, `TestBH023HyphenatedTomlKeys`
- `tests/test_pipeline_scripts.py` (parses hexwise project.toml)
- `tests/test_lifecycle.py` (parses generated project.toml)

**Mutations that WOULD be caught:**
- Dropping a key entirely from the result dict: `test_single_kv_roundtrip` catches (asserts `key in result` and value equality)
- Returning wrong type for booleans: `test_single_kv_roundtrip` asserts `result[key] is value` for bools
- Returning wrong type for integers: same test asserts `result[key] == value`
- Breaking string escaping (`\\n`, `\\"`, `\\\\`): `test_single_kv_roundtrip` with string values would catch (hypothesis generates strings with special chars)
- Breaking section nesting: `test_section_nesting` asserts nested dict structure
- Breaking array parsing: `test_string_array` and `test_multiline_array` roundtrip arrays
- Removing comment stripping for `#` at start of line: `test_comments_only` asserts `{}` result
- Breaking hyphenated keys: `TestBH023HyphenatedTomlKeys` asserts `base-branch` parses

**Mutations that would SURVIVE:**
1. **Silently dropping inline comments (not stripping `# comment` after values):** No test has `key = "value" # comment` and asserts the value is `"value"` not `"value" # comment`. The `_strip_inline_comment` function is only indirectly tested through property tests that don't generate inline comments. If `_strip_inline_comment` were changed to be a no-op, the property tests would still pass because their generated TOML doesn't include inline comments.
2. **Breaking `_has_closing_bracket` for quoted brackets:** If `]` inside a quoted string were treated as a closing bracket, multiline arrays with values containing `]` would break. No test generates array values with literal `]` characters.
3. **Corrupting `_set_nested` to silently overwrite instead of setdefault:** If `_set_nested` used `target[part] = {}` instead of `target.setdefault(part, {})`, keys in the same section written before a subsection would be lost. The property test `test_multiple_sections_independent` uses different section names, not subsections.
4. **Removing the unterminated multiline array error:** If the `ValueError` for missing closing `]` were silently swallowed (returning partial data), tests would still pass because no test explicitly checks that unterminated arrays raise. The fuzz test `test_random_text_returns_dict_or_raises_valueerror` accepts both dict and ValueError, so removing the raise would pass.

**Worst surviving mutation:** #1 -- inline comments not stripped. In production, `check_commands = ["pytest"] # CI check` would parse as `["pytest"] # CI check` (invalid), silently corrupting CI configuration.

**Severity:** HIGH -- inline comments are a common TOML pattern in user-written config files, and the parser's comment handling is untested at the value level.

---

### 2. do_release() -- Mutation Survival Analysis

**Production code:** `skills/sprint-release/scripts/release_gate.py:428-687`

**Tests examined:**
- `tests/test_release_gate.py::TestDoRelease` (7 tests, all mock-based)
- `tests/test_lifecycle.py` (tests release notes + version write, not do_release itself)
- `tests/test_gh_interactions.py::TestGateStories`, `TestGateCI`, `TestGatePRs`, `TestGenerateReleaseNotes`
- `tests/test_release_gate.py::TestValidateGates` (FakeGitHub-backed)

**Mutations that WOULD be caught:**
- Removing pre-flight dirty-tree check: `test_happy_path` verifies git status is called first
- Removing version write: `test_happy_path` asserts `mock_write_toml.assert_called_once()`
- Removing git tag creation: `test_happy_path` verifies `git tag` in subprocess calls
- Removing git push: `test_happy_path` verifies `git push` in subprocess calls
- Removing rollback on tag failure: `test_tag_failure_returns_false` checks no gh calls
- Removing rollback on push failure: `test_push_tag_failure_resets_commit_and_deletes_tag` checks `git tag -d` and `git reset --hard`
- Removing rollback on GH release failure: `test_gh_release_failure_resets_commit` checks revert
- Skipping commit step: `test_happy_path` counts subprocess calls (would be fewer)
- Dry run doing mutations: `test_dry_run_no_mutations` asserts no write/gh calls

**Mutations that would SURVIVE:**
1. **Removing milestone closure (step 8):** `test_happy_path` checks `mock_gh.call_count >= 2` but uses `assertGreaterEqual` -- if milestone close were skipped, the release create + release view calls would still satisfy `>= 2`. The test DOES verify `milestones/7` in the gh call args, which would catch this. BUT: `find_milestone_number` is mocked to return 7 -- if you mutated `do_release` to skip the `if ms_num is not None` block, the `mock_gh` assertion for `milestones/7` would fail. **Actually caught** on closer inspection.
2. **Removing SPRINT-STATUS.md update (step 9):** The `test_happy_path` test explicitly checks `self.assertIn("v1.1.0", status)` and `self.assertIn("Released", status)`, so this IS caught. **Actually caught.**
3. **Swapping the release notes temp file cleanup (step 6-7):** If `notes_path.unlink(missing_ok=True)` were removed, temp files would leak. No test checks for temp file cleanup. The `finally` block is tested indirectly by `test_gh_release_failure_resets_commit`, which exercises the failure path but doesn't check temp file existence.
4. **Removing the `COMMIT_PY.exists()` pre-flight check:** If this guard were deleted, the code would proceed without commit.py and fail later at the `subprocess.run` call. No test specifically patches `COMMIT_PY.exists()` to test this path. The happy path test patches `calculate_version` so it never reaches this check in real code, and `mock_run` would just succeed for the commit.py invocation anyway.
5. **Mutating the release notes content:** `test_happy_path` never inspects the content of the release notes passed to `gh release create`. It only checks that `--notes-file` is present in the args. If `generate_release_notes` returned empty string, `do_release` would still create a release with blank notes. The separate `TestGenerateReleaseNotes` tests cover the notes content, but `do_release`'s integration with notes is not verified.
6. **Removing the git binary check (FileNotFoundError catch):** No test exercises the path where `git` is not installed (`FileNotFoundError`). Mock-based tests always succeed subprocess calls.

**Worst surviving mutation:** #5 -- release notes content could be silently empty/corrupted during do_release integration, and tests would still pass. Also #3 -- temp file leak in production.

**Severity:** MEDIUM -- the mock-heavy tests verify the command sequence rigorously, but integration gaps exist around error paths and file cleanup.

---

### 3. sync_one() -- Mutation Survival Analysis

**Production code:** `skills/sprint-run/scripts/sync_tracking.py:233-277`

**Tests examined:**
- `tests/test_sprint_runtime.py::TestSyncOne` (4 tests)
- `tests/test_sprint_runtime.py::TestSyncOneGitHubAuthoritative` (1 test)
- `tests/test_bugfix_regression.py::TestSyncTrackingMainIntegration` (3 tests)

**Mutations that WOULD be caught:**
- Not setting `tf.status = "done"` when issue closed: `test_closed_issue_updates_status` asserts `tf.status == "done"`
- Not syncing kanban label status: `test_label_sync_updates_status` asserts `tf.status == "review"`
- Not setting `tf.pr_number`: `test_pr_number_updated` asserts `tf.pr_number == "42"`
- Falsely reporting changes when in sync: `test_no_changes_when_in_sync` asserts `changes == []`

**Mutations that would SURVIVE:**
1. **Never setting `tf.completed` date:** The `sync_one` function has a block that sets `tf.completed = d` when status is "done" and `closedAt` is present. `test_closed_issue_updates_status` passes `closedAt = "2026-03-10T12:00:00Z"` but NEVER checks `tf.completed`. The mutation `tf.completed = d` -> (remove line) would pass all tests.
2. **Never setting `tf.issue_number`:** The function updates `tf.issue_number` to match `str(issue["number"])`. The only test that passes `issue_number="1"` is `test_pr_number_updated`, but it only checks `tf.pr_number`. `test_no_changes_when_in_sync` sets `issue_number="5"` and `number=5`, so they already match -- but if the mutation were "never update issue_number", the test where they already agree would still pass. The test that WOULD catch this is the integration test `test_main_creates_tracking_files`, which writes files to disk and checks content, but it only checks that `US-0101` and `US-0102` appear in the text (story IDs), not `issue_number` values.
3. **Never setting `tf.sprint`:** The function updates `tf.sprint` when it disagrees with the passed sprint number. No unit test exercises this path with mismatched sprint numbers. The only test creating a TF with sprint=1 and passing sprint=1 -- they match, so no change is triggered.
4. **Generating wrong change descriptions:** Tests check `any("done" in c for c in changes)` which is very loose. The change message format could be completely wrong and still contain "done".

**Worst surviving mutation:** #1 -- never setting `tf.completed` means closed stories would lack completion dates. This would cascade to burndown charts showing incorrect timeline data.

**Severity:** HIGH -- the `completed` field drives burndown/velocity calculations, and no test verifies it is populated by `sync_one`.

---

### 4. get_linked_pr() -- Mutation Survival Analysis

**Production code:** `skills/sprint-run/scripts/sync_tracking.py:50-113`

**Tests examined:**
- `tests/test_sprint_runtime.py::TestGetLinkedPR` (2 tests, mock-based fallback path)
- `tests/test_sprint_runtime.py::TestGetLinkedPrTimeline` (5 tests, FakeGitHub timeline path)
- `tests/test_sprint_runtime.py::TestGetLinkedPrWordBoundary` (4 tests, fallback path)
- `tests/test_sprint_runtime.py::TestGetLinkedPrWarning` (1 test)

**Mutations that WOULD be caught:**
- Returning first PR instead of latest merged: `test_timeline_prefers_latest_merged_pr` asserts `result["number"] == 20` (the later-merged PR), not 10 (the earlier-merged)
- Substring matching instead of word-boundary: `test_pr_link_no_substring_match` and `test_pr_link_longer_id_no_false_positive` verify false positives are avoided
- Not returning merged flag: `test_timeline_returns_merged_pr` asserts `result["merged"] is True`
- Not falling back when timeline fails: `test_timeline_api_error_falls_back` and `test_timeline_no_match_falls_back`

**Mutations that would SURVIVE:**
1. **Removing the open PR priority (`break` on open state):** The timeline path has logic: if an open PR is found, it takes priority over merged PRs. No test exercises a scenario with BOTH an open PR and merged PRs in the timeline to verify the open one is preferred. `test_timeline_prefers_latest_merged_pr` only has merged PRs.
2. **Removing the `best = linked[-1]` default:** If the default were removed and only `open_pr` or `latest_merged` were checked, the case where all linked PRs are closed-but-not-merged (draft PRs, closed without merge) would return None instead of the last one. No test covers this edge case.
3. **Returning wrong `state` in the fallback branch-match path:** The fallback returns `"merged"` when `mergedAt` is truthy, else `pr["state"]`. But `test_matches_correct_story_id` checks `result["number"] == 20` but doesn't check `result["state"]`. The state value in the fallback is untested.

**Worst surviving mutation:** #1 -- if open PR priority were removed, a story with an open PR (still in review) and a previously merged+reverted PR would link to the old merged PR instead of the active one. This would cause the tracking file to point to stale PR data.

**Severity:** MEDIUM -- the most critical mutation (#1 returning first instead of latest merged) IS caught by the test. The surviving mutations are edge cases.

---

### 5. create_issue() -- Mutation Survival Analysis

**Production code:** `skills/sprint-setup/scripts/populate_issues.py:391-416`

**Tests examined:**
- `tests/test_lifecycle.py::TestLifecycle::test_06_populate_creates_issues` (creates 2 issues via FakeGitHub)
- `tests/test_lifecycle.py::TestLifecycle::test_13_full_pipeline` (2 issues)
- `tests/test_golden_run.py::TestGoldenRun::test_golden_full_setup_pipeline` (17 issues with golden snapshot)
- `tests/test_hexwise_setup.py` (17 issues)
- `tests/test_sync_backlog.py::TestDoSync` (2 issues)

**Mutations that WOULD be caught:**
- Dropping ALL labels: Golden run snapshot comparison (`assert_issues_match`) checks per-issue label sets. `test_golden_full_setup_pipeline` would catch missing labels.
- Changing issue title format: Golden snapshot and lifecycle test both check issue titles contain story IDs
- Dropping milestone assignment: Golden snapshot checks per-issue milestone assignment

**Mutations that would SURVIVE:**
1. **Dropping a single optional label (e.g., `saga:{story.saga}`):** The golden snapshot DOES compare labels, so this would be caught IF golden recordings exist. BUT: `test_lifecycle.py::test_06_populate_creates_issues` (the non-golden test) only counts issues -- `self.assertEqual(len(self.fake_gh.issues), 2)` -- and never inspects labels. `test_13_full_pipeline` also only counts. If golden recordings were absent (test skips), no test would catch a single dropped label.
2. **Silently dropping the `priority:` label specifically:** On the non-golden path (lifecycle test), no assertion inspects individual labels on created issues. This WOULD be caught by golden recording comparison.
3. **Dropping the `format_issue_body()` call (empty body):** `test_06_populate_creates_issues` and `test_13_full_pipeline` never inspect issue bodies. Golden snapshot `assert_issues_match` does NOT compare issue bodies (only titles, labels, milestones). So an empty body would survive ALL tests.
4. **Returning True even when `gh()` raises:** If the try/except were changed to `return True` on exception, the error would be silently swallowed. No test exercises the failure path of `create_issue`.

**Worst surviving mutation:** #3 -- `format_issue_body()` call removed, resulting in issues with empty bodies in production. User stories, acceptance criteria, dependencies, and test coverage references would all be missing from GitHub issues. No test at any level checks issue body content after creation.

**Severity:** CRITICAL -- empty issue bodies would mean developers implementing stories have no acceptance criteria, user stories, or dependency information. This is a total loss of the enrichment pipeline's output.

---

### 6. check_milestone() -- Mutation Survival Analysis

**Production code:** `skills/sprint-monitor/scripts/check_status.py:172-209`

**Tests examined:**
- `tests/test_sprint_runtime.py::TestCheckMilestone` (4 tests)
- `tests/test_lifecycle.py::TestLifecycle::test_14_monitoring_pipeline` (1 integration test)
- `tests/test_bugfix_regression.py::TestCheckStatusMainIntegration` (1 integration test)

**Mutations that WOULD be caught:**
- Always returning 0% progress: `test_happy_path_with_sp` asserts `3/5` and `SP` in report. `test_14_monitoring_pipeline` asserts `2/4` and `50%` and `8/13 SP`.
- Not handling missing milestone: `test_no_milestone_found` asserts `no milestone` in report
- Not handling API error: `test_api_error_graceful` asserts `could not query` in report
- Zero division on empty milestone: `test_zero_total_stories` asserts `0/0` and `0%`

**Mutations that would SURVIVE:**
1. **Removing SP (story points) calculation entirely:** `test_happy_path_with_sp` checks `any("SP" in line for line in report)` but the main progress line would still say "3/5 stories done (60%)" even without SP calculation. The SP part is in `sp_part` which is appended as `, 10/23 SP`. The test asserts `any("SP" in line for line in report)`. HOWEVER, the integration test `test_14_monitoring_pipeline` specifically asserts `8/13 SP` -- this WOULD catch removing SP calc. But `TestCheckMilestone::test_happy_path_with_sp` uses mocked `gh_json` where the second call returns issues with sp labels, and it asserts SP presence. The mock dispatch `_mock_gh_json` uses positional argument checking to route -- if the issue query returns `[]` (empty), no SP would be calculated but `SP` would not appear in the report, failing the assertion. So SP removal IS caught.
2. **Silently swallowing the SP calculation RuntimeError:** The `try/except RuntimeError: pass` around the SP issue fetch means if the API call fails, SP data is just omitted. If this except were broadened to catch ALL exceptions, it would still pass tests. But that's not a meaningful mutation.
3. **Using `open_issues` instead of `closed_issues` for the percentage:** If `pct = round(opened / total * 100)` were used instead of `closed / total * 100`, `test_happy_path_with_sp` has `open_issues=2, closed_issues=3`, so pct would be 40% instead of 60%. The test only checks `3/5` (which would still be present since `closed/total` is formatted separately). BUT: `test_14_monitoring_pipeline` checks for `50%` with `open_issues=2, closed_issues=2` -- where open/(open+closed) = 50% too! So this specific mutation with those specific test data would survive.
4. **Hardcoding `pct = 50`:** Would pass `test_zero_total_stories` (asserts `0%`, so would fail) and `test_14_monitoring_pipeline` (asserts `50%`, would pass) and `test_happy_path_with_sp` (would need `60%`, fail). So actually caught.

**Worst surviving mutation:** #3 -- using `opened` instead of `closed` for percentage. With the specific test data in `test_14_monitoring_pipeline` (2 open, 2 closed), both `opened/total` and `closed/total` yield 50%. The unit test data (2 open, 3 closed) would catch it at 40% vs 60%, but only because `test_happy_path_with_sp` implicitly checks the percentage via `3/5` pattern -- wait, it does NOT assert the percentage explicitly. Let me re-check.

Looking at `test_happy_path_with_sp`: it asserts `any("3/5" in line for line in report)` and `any("SP" in line for line in report)` but does NOT assert the actual percentage value. So `3/5 stories done (40%)` would still match `3/5`. The integration test checks `50%` which would pass either way with 2/4. So this mutation DOES survive.

**Worst surviving mutation (confirmed):** Using `opened` instead of `closed` for percentage calculation. With symmetric test data (2/4 = 50% either way) and non-percentage assertions in the unit test.

**Severity:** MEDIUM -- showing wrong percentage (inverted) would mislead sprint monitoring but wouldn't cause data corruption.

---

### 7. assert_files_match() -- Mutation Survival Analysis

**Production code:** `tests/golden_replay.py:194-247`

**Tests examined:**
- `tests/test_golden_run.py::TestGoldenRun::test_golden_full_setup_pipeline` (calls `assert_files_match` at phases 01 and 05)
- No dedicated unit tests for `assert_files_match` itself

**Mutations that WOULD be caught:**
- Returning non-empty diffs list falsely: The golden run test asserts `self.assertEqual(diffs, [], ...)` so false positives are caught
- Wrongly computing `missing` or `extra` file sets: Would produce non-empty diffs, caught by `assertEqual(diffs, [])`

**Mutations that would SURVIVE:**
1. **Silently skipping ALL content comparisons (not just unreadable files):** The content comparison loop (lines 235-245) catches `OSError` and `UnicodeDecodeError` with `continue`. If the `try/except` were broadened to `except Exception: continue`, ALL file comparisons would be skipped silently. No test verifies that content mismatches are detected. The golden run test uses `assert_files_match` only to confirm state MATCHES -- there is no test where content deliberately differs to verify the comparison works.
2. **Removing the content comparison entirely:** If lines 233-245 were deleted, `assert_files_match` would only check file presence (missing/extra), not content. Since the golden run creates files from the same code that generates the recording, content always matches. No test verifies that content differences produce diffs.
3. **Always returning `[]` (empty diffs):** The function is only called in the golden run test which asserts `diffs == []`. If `assert_files_match` always returned `[]`, the golden test would pass. The function's PURPOSE is to catch regressions, but its own correctness is never tested adversarially.

**Worst surviving mutation:** #3 -- function returns `[]` unconditionally. The golden run test, which is the sole consumer of this assertion function, would always pass regardless of actual file state. This makes the entire golden snapshot regression suite vacuous for file content -- it would catch label/milestone/issue regressions (different assertion functions) but never file content regressions.

**Severity:** CRITICAL -- this is a meta-testing failure. The assertion function itself is untested, meaning the golden snapshot's file comparison provides a false sense of security. A regression that changes file content (e.g., generated CI YAML, tracking file format) would be silently missed.

---

### 8. check_sync() -- Mutation Survival Analysis

**Production code:** `scripts/sync_backlog.py:115-152`

**Tests examined:**
- `tests/test_sync_backlog.py::TestCheckSync` (7 tests)
- `tests/test_sync_backlog.py::TestMain` (3 integration tests)

**Mutations that WOULD be caught:**
- Removing debounce (immediately syncing on first change): `test_first_change_triggers_debounce` asserts `status == "debouncing"` and `should_sync == False`
- Removing throttle check: `test_throttle_blocks_sync` asserts `status == "throttled"` when last sync was recent
- Not detecting revert: `test_revert_cancels_pending` asserts pending is cleared
- Not re-debouncing on continued changes: `test_still_changing_re_debounces` asserts re-debounce

**Mutations that would SURVIVE:**
1. **Removing the `pending is None` check on the `current == stored` path:** Line 129 checks `current_hashes == stored and pending is None`. If the `and pending is None` were removed, the function would return "no_changes" even when there's a pending sync (because the stored hashes happen to match). But wait -- `test_revert_cancels_pending` covers exactly this: `current == stored` with `pending != None`, and it expects `no_changes`. So this is actually the CORRECT behavior. The `pending is not None` check on line 133 handles this case. The two conditions together cover all cases where `current == stored`. Actually caught.
2. **Removing the re-debounce (`current != pending` check):** If `check_sync` always moved to sync when files differ from stored (regardless of whether they match pending), debounce would be reduced to a single check instead of two. `test_still_changing_re_debounces` passes `newest != pending`, expects `debouncing`. If this check were removed and the code fell through to the sync path, `should_sync` would be True, failing the assertion. **Actually caught.**
3. **Swapping `THROTTLE_FLOOR_SECONDS` to 0 (effectively removing throttle):** `test_throttle_blocks_sync` uses `timedelta(minutes=5)` as recent sync time. If `THROTTLE_FLOOR_SECONDS` were 0, `_is_throttled` would return False, and the test would get `sync` instead of `throttled`, failing. **Actually caught.**
4. **Not mutating state (not setting `pending_hashes` on first detection):** `test_first_change_triggers_debounce` asserts `state["pending_hashes"] == new`, so this IS caught.
5. **Breaking `_is_throttled` to always return True:** `test_stabilized_triggers_sync` has `last_sync_at=None`, so `_is_throttled` returns False. If it returned True, the test would get `throttled` instead of `sync`. **Actually caught.**
6. **Making `check_sync` a no-op that always returns "no_changes":** Multiple tests would fail. **Caught.**

The debounce/throttle logic is actually well-tested at the unit level. However:

7. **The integration between `check_sync` and `main()` skipping the `save_state` call:** In `main()`, `save_state(config_dir, state)` is called at the end regardless of result. If `save_state` were removed, the integration test `test_second_run_syncs` would still debounce on first call (state not persisted), but then on the second call it would debounce again (no prior state). The test asserts second call returns `"sync"`, so it would fail. **Actually caught.**
8. **Removing debounce entirely but keeping throttle:** If `check_sync` returned `SyncResult("sync", True, ...)` on first change detection (instead of debouncing), `test_first_change_triggers_debounce` catches this. `test_first_run_debounces` (integration) also catches it. **Caught.**

**Worst surviving mutation:** After careful analysis, the debounce/throttle state machine is thoroughly tested. The main gap is:

9. **`do_sync` integration not verified for partial failures:** If `do_sync` raised an exception partway through (e.g., milestones created but issues fail), `main()` would propagate the exception and the state would not be updated (no `save_state` call since it's after the sync block). On next run, it would re-sync, which is actually correct (idempotent). But if `do_sync` silently returned `{"milestones": 0, "issues": 0}` when it should have created resources, the state would be saved as if sync completed, and the real sync would never happen. `test_do_sync_creates_milestones_and_issues` checks counts, so an all-zeros return WOULD be caught at the do_sync level. But `main()` doesn't check the counts -- it just saves state.

**Worst surviving mutation (actual):** If `do_sync` returned `{"milestones": 0, "issues": 0}` on error instead of raising, `main()` would save state as synced, and subsequent runs would report `no_changes` even though nothing was created. This is a `do_sync` mutation, not a `check_sync` mutation.

**Severity:** LOW -- the check_sync state machine itself is well-tested. The gap is in error propagation from do_sync through main, not in the debounce/throttle logic.

---

## Summary: Surviving Mutations Ranked by Severity

| # | Function | Surviving Mutation | Severity |
|---|----------|--------------------|----------|
| 1 | `create_issue()` | Remove `format_issue_body()` call -- empty issue bodies | **CRITICAL** |
| 2 | `assert_files_match()` | Return `[]` unconditionally -- golden file comparison vacuous | **CRITICAL** |
| 3 | `sync_one()` | Never set `tf.completed` date | **HIGH** |
| 4 | `parse_simple_toml()` | Inline comment stripping removed | **HIGH** |
| 5 | `sync_one()` | Never update `tf.sprint` on mismatch | **HIGH** |
| 6 | `check_milestone()` | Use `opened` instead of `closed` for percentage | **MEDIUM** |
| 7 | `do_release()` | Release notes content not verified in integration | **MEDIUM** |
| 8 | `do_release()` | Temp file cleanup never verified | **MEDIUM** |
| 9 | `get_linked_pr()` | Open PR priority over merged not tested in combined scenario | **MEDIUM** |
| 10 | `check_sync()` | do_sync silent failure saves state as "synced" | **LOW** |

## Recommended Test Additions

1. **CRITICAL -- create_issue body verification:** Add a test that calls `create_issue` via FakeGitHub and asserts the created issue's `body` field contains acceptance criteria, user story, and story metadata. This catches both the `format_issue_body` removal and body formatting regressions.

2. **CRITICAL -- assert_files_match adversarial test:** Add a unit test for `assert_files_match` that deliberately introduces a content mismatch and asserts the diff list is non-empty. This validates the assertion function itself.

3. **HIGH -- sync_one completed date:** Add `self.assertEqual(tf.completed, "2026-03-10")` to `test_closed_issue_updates_status`.

4. **HIGH -- inline comment TOML test:** Add `result = parse_simple_toml('key = "value" # comment')` and assert `result["key"] == "value"`.

5. **HIGH -- sync_one sprint mismatch:** Add a test with `tf.sprint = 1` and `sync_one(tf, issue, None, sprint=2)`, assert `tf.sprint == 2`.

6. **MEDIUM -- check_milestone percentage:** Use asymmetric test data (e.g., 1 open, 4 closed) and assert the exact percentage string (e.g., `80%`).
