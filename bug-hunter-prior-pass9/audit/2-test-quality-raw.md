# Test Quality Audit -- Pass 9

Adversarial review of all test files in `tests/`. Each finding identifies a specific
anti-pattern, cites exact line numbers, and rates severity. This audit asks: "Could
a broken production function still pass these tests?"

---

## Summary Statistics

| File | Tests | Critical | High | Medium | Low |
|------|------:|:--------:|:----:|:------:|:---:|
| test_gh_interactions.py | ~95 | 1 | 3 | 5 | 3 |
| test_pipeline_scripts.py | ~80 | 1 | 2 | 5 | 4 |
| test_lifecycle.py | 14 | 0 | 2 | 3 | 2 |
| test_hexwise_setup.py | ~28 | 0 | 1 | 3 | 2 |
| test_golden_run.py | 1 | 1 | 1 | 2 | 0 |
| test_sprint_analytics.py | 11 | 0 | 1 | 2 | 1 |
| test_sprint_teardown.py | 17 | 0 | 0 | 2 | 1 |
| test_verify_fixes.py | ~18 | 0 | 1 | 2 | 2 |
| test_validate_anchors.py | ~20 | 0 | 0 | 2 | 1 |
| test_sync_backlog.py | ~17 | 0 | 1 | 2 | 1 |
| test_release_gate.py | ~25 | 0 | 1 | 3 | 1 |
| fake_github.py (support) | n/a | 1 | 1 | 0 | 0 |
| **TOTAL** | **~326** | **4** | **14** | **31** | **18** |

---

## File-by-File Findings

---

### 1. `tests/fake_github.py` (Support file, not a test)

**What it is:** In-memory GitHub simulator used by most tests. Not a test file itself, but mock fidelity problems here cascade into every test that uses it.

**736 lines, 0 test methods (support code)**

#### CRITICAL: FakeGitHub silently ignores `--jq` filtering (mock fidelity gap)

- **Lines 93-95, 113:** `--jq` is listed in `_ACCEPTED_NOOP_FLAGS` and `_KNOWN_FLAGS["api"]` but is never executed. Production code passes `--jq` expressions to filter/reshape JSON output. FakeGitHub returns raw unfiltered data. This means any production code that depends on `--jq` to reshape data (e.g., the timeline endpoint filtering, commits endpoint) gets a completely different data shape in tests than in production.
- **Impact:** Tests that exercise code paths using `--jq` are testing against a different data contract than production. The code in `check_direct_pushes` uses `--jq` to filter commits to 1-parent (direct push) commits and reshape to `{sha, message, author, date}`. FakeGitHub returns whatever is in `commits_data` unfiltered. Tests pre-shape the data to match what `--jq` would produce (line 1241 in test_gh_interactions.py acknowledges this with a comment), meaning the test is testing the mock's data shape, not the production jq filter.

#### HIGH: FakeGitHub `_issue_list` does not support `--paginate` semantically

- **Line 92-95:** `--paginate` is in `_ACCEPTED_NOOP_FLAGS`. In production, `--paginate` means "fetch all pages." FakeGitHub always returns all data regardless, so code that forgets `--paginate` would pass tests but silently truncate in production when there are >30 results. The `warn_if_at_limit` function was added to detect this, but FakeGitHub can never trigger it naturally.

---

### 2. `tests/test_gh_interactions.py`

**What it tests:** commit.py, release_gate.py (version/gates/notes), check_status.py, bootstrap_github.py, populate_issues.py, sync_tracking.py, update_burndown.py, validate_config utilities.

**~95 test methods across ~22 classes**

#### CRITICAL: `TestCheckBranchDivergenceFakeGH.test_api_error_handled` tests the mock default, not error handling (lines 1215-1222)

- **Lines 1215-1222:** This test claims to verify "Branch not in comparisons still returns default." But `FakeGitHub._handle_api` returns `{"behind_by": 0, "ahead_by": 0}` as a default for unknown branches (line 264 of fake_github.py). This means the test asserts `report == []` and `actions == []`, which is exactly what "no drift" looks like. It is **not** testing error handling -- it's testing the happy path of "no drift." A real API error (HTTP 404, network timeout) would raise an exception in production, which this test never exercises.
- **Severity:** Critical. The test name and docstring promise error handling coverage that does not exist.

#### HIGH: Duplicate tests across `TestCheckBranchDivergence` (mock-based) and `TestCheckBranchDivergenceFakeGH` (FakeGitHub-based)

- **Lines 1036-1113 vs 1173-1222:** These two classes test identical scenarios (high drift, medium drift, no drift, API error) -- one using `@patch("check_status.gh_json")` and the other using FakeGitHub. Both produce identical assertions. The FakeGitHub version adds zero additional coverage because FakeGitHub's compare endpoint is trivial (`self.comparisons.get(branch, default)`). This is copy-paste test inflation.
- **Same pattern for:** `TestCheckDirectPushes` (lines 1115-1165) vs `TestCheckDirectPushesFakeGH` (lines 1225-1288). Another full duplication.

#### HIGH: `TestCreateLabel.test_creates_label` tests mock call args, not behavior (lines 494-503)

- **Lines 494-503:** This test mocks `bootstrap_github.gh` and then asserts `mock_gh.assert_called_once()` and checks that `"label"`, `"create"`, and `"test-label"` appear in the call args. It is verifying that `create_label` forwards arguments to `gh()` -- testing implementation plumbing, not observable behavior. If `create_label` were refactored to use the GitHub REST API directly, this test would break even though behavior is identical.

#### HIGH: `TestCheckCI.test_failing_run` double-mocks obscure what is tested (lines 438-449)

- **Lines 438-449:** Mocks both `check_status.gh_json` and `check_status.gh`. The `gh` mock is for "log-failed" extraction. But the test only asserts `"1 failing" in report[0]` and `len(actions) > 0`. It never verifies the log content is actually included in the actions. The `gh` mock returns `"error: something broke\nfatal: test failed"` but no assertion checks these strings appear anywhere.

#### MEDIUM: `TestBumpVersion` (lines 205-220) -- no edge case for `"none"` bump type

- Tests patch, minor, major, and reset behaviors but never tests what happens when `bump_type="none"`. Production's `calculate_version` can return `"none"` bump, and `do_release` checks for it, but `bump_version` itself is never tested with it. If someone passes `"none"` to `bump_version`, behavior is undefined.

#### MEDIUM: `TestValidateMessage` (lines 57-104) -- no test for multi-line messages

- Tests single-line messages only. Production commit messages can have a body separated by `\n\n`. The `validate_message` function takes only the first line, but this assumption is never tested. If a multi-line string is passed, does it validate only the first line or crash?

#### MEDIUM: `TestGetExistingIssues.test_handles_gh_failure` (lines 653-657) -- tests for RuntimeError but production may raise different exceptions

- Line 655: `mock_gh.side_effect = RuntimeError("auth failed")`. But in production, `gh()` raises a `RuntimeError` wrapping stderr. The test verifies `get_existing_issues` propagates the exception, but never tests what happens when `gh()` returns malformed JSON (not a RuntimeError but a `json.JSONDecodeError`).

#### MEDIUM: `TestFormatIssueBody.test_minimal_story` (lines 593-604) -- does not verify SP or priority appear

- Line 599: Creates a minimal story with `sp=1, priority="low"` but only asserts `"US-0001"` and `"Stub"` are in the body and that AC/dependencies sections are absent. Does not verify SP or priority are rendered. A bug where minimal stories omit SP from the body would pass this test.

#### MEDIUM: `TestExtractSP` has 13 tests (lines 964-1012) but all follow the same pattern

- All 13 tests create an `issue` dict and call `extract_sp(issue)`. No test verifies behavior when `labels` key is missing entirely (KeyError path), when `body` is `None` instead of `""`, or when the issue dict is empty `{}`. These edge cases could crash production.

#### LOW: `TestGetLinkedPrTimeline` (lines 832-911) -- test_timeline_no_match_falls_back uses FakeGitHub but pre-shapes fallback data

- Lines 882-897: The test registers timeline events with no `pull_request` field, then provides `all_prs` with a matching branch name. This works, but the test doesn't verify that the timeline API was actually called and failed -- it just trusts the fallback works. The assertion that `result["number"] == 50` could pass even if the timeline code path was completely skipped.

#### LOW: `TestCheckPRs` only tests 3 scenarios (lines 452-484)

- No test for: PRs with failed CI checks, PRs older than N days (stale detection), PRs with conflicting labels, empty `statusCheckRollup` with `reviewDecision == "APPROVED"`.

#### LOW: `TestInferSprintNumber.test_content_parameter_passthrough` (line 700-705) -- tests that passing content prevents file I/O, but this is an implementation detail, not behavior. The real question is whether the sprint number is correctly extracted, which is already covered by other tests.

---

### 3. `tests/test_pipeline_scripts.py`

**What it tests:** team_voices, traceability, test_coverage, manage_epics, manage_sagas, parse_simple_toml, CI generation, validate_project negative cases, utility functions.

**~80 test methods across ~18 classes**

#### CRITICAL: `TestCoverage.test_coverage_no_actual_tests` is a tautology (lines 165-176)

- **Lines 174-175:** `self.assertEqual(report["missing"], report["planned"])`. When there are zero implementations, `missing` will always equal `planned` by definition. This assertion can never fail regardless of what `check_test_coverage` returns (as long as it returns any dict with `missing` and `planned` keys containing the same value). The real question should be: are specific planned test case IDs in the missing list? The test never checks specific IDs.
- **Line 176:** `self.assertEqual(len(report.get("matched", [])), 0)` -- also a tautology when there are no implementations.

#### HIGH: `TestValidateProjectNegative` tests are good but miss critical error paths (lines 1169-1279)

- Tests: missing project.toml, invalid TOML, too few personas, missing persona file, missing [ci], empty rules.md, no milestones. But does NOT test:
  - Missing `[project]` section (with valid [ci] and [paths])
  - Missing `project.name` key (section exists but key absent)
  - `check_commands` is not an array (is a string)
  - `team_dir` points to nonexistent directory
  - Circular symlinks in config
  - project.toml with BOM marker
- These are production error paths that could crash or behave unexpectedly.

#### HIGH: `TestScannerMinimalProject` has 16 tests that all assert `None` or empty (lines 1044-1158)

- Every test in this class asserts that a scanner method returns `None`, empty list, or zero confidence. While these verify graceful degradation, they all test the same code path (early return when no files match). 16 tests testing "nothing found" is significant inflation. A single parameterized test could cover all of these.

#### MEDIUM: `TestTeamVoices.test_extract_voices_from_epics_returns_empty` (lines 48-54) -- tests absence, not presence

- Asserts that Hexwise epics have no team voice blocks. This is a test of fixture data, not of the `extract_voices` function. If someone adds voices to the epic fixture, this test breaks for the wrong reason.

#### MEDIUM: `TestTraceability.test_traceability_no_gaps` (lines 115-121) -- fixture-dependent assertion

- Line 121: `self.assertEqual(report["stories_without_tests"], [])`. This passes only because the Hexwise fixture has complete traceability. It's testing the fixture, not the `build_traceability` function. A change to the fixture would break this test.

#### MEDIUM: `TestParseSimpleToml` has good edge cases but misses adversarial inputs (lines 442-621)

- Missing: deeply nested sections (`[a.b.c.d.e]`), extremely long values (>64KB), null bytes in strings, tab-separated key=value, Windows line endings (`\r\n`), section names with special characters (`[my-section]`, `[my.section.with.dots]` vs `[my].[section]`).

#### MEDIUM: `TestManageEpics.test_remove_story_nonexistent_id` (lines 320-334) -- correct test, but no error case for malformed epic file

- Tests removing a nonexistent story ID, which is good. But no test for: removing from a corrupted/empty file, removing when only one story exists (edge case: does the epic metadata update?), removing when the story has cross-references in other stories' Blocks/Blocked By fields.

#### MEDIUM: `TestRenumberStories.test_renumber_word_boundary` (lines 826-874) -- excellent adversarial test, but assertion is weak

- Line 871-873: `self.assertTrue(any("US-01a, US-01b" in l for l in blocked_by_lines))` -- uses `any()` which passes if at least one line matches. If there are multiple blocked-by lines and only one is correct while another is corrupted, the test still passes.

#### LOW: `TestCIGeneration` (lines 629-690) tests four languages but assertions are loose

- Lines 641-644: For Python CI, asserts `"pip install" in yaml`, `"pytest" in yaml`, `"python" in yaml`. These would pass even if the YAML is malformed (e.g., `pytest` appears in a comment). No structural YAML validation. No test that the generated YAML is actually valid YAML.

#### LOW: `TestScannerPythonProject` (lines 882-1036) -- tests scanner detection heuristics but confidence values are just checked for >=threshold, not exact values

- Line 959: `self.assertGreaterEqual(det.confidence, 1.0)`. If confidence suddenly jumps to 5.0 due to a bug, this test still passes. Should verify confidence is within expected range [0.0, 1.0].

#### LOW: `_split_array` tests (lines 585-621) test the private helper function directly

- These 8 tests directly test `_split_array`, a private function. If the implementation refactors to remove `_split_array`, all 8 tests break. Better to test the public API (`parse_simple_toml`) with inputs that exercise these code paths.

#### LOW: `TestParseWorkflowRuns` (lines 1388-1440) tests a private method `_parse_workflow_runs` directly, same concern as above.

---

### 4. `tests/test_lifecycle.py`

**What it tests:** End-to-end lifecycle: sprint_init -> bootstrap_github -> populate_issues -> version calculation -> monitoring pipeline.

**14 test methods in 1 class**

#### HIGH: Tests 01-13 run the same pipeline in slightly different permutations (test inflation)

- `test_01_init_generates_valid_config` (line 176): Generates config, validates. Same as `test_02_config_has_required_keys` (line 185) which generates config and checks keys. And same first step as `test_13_full_pipeline` (line 403) which does init -> bootstrap -> issues.
- The `_generate_config()` helper is called in tests 01, 02, 05, 06, 10, 13, and 14. Each time it runs `ProjectScanner` + `ConfigGenerator` from scratch. This is wasted work but also means a bug in config generation would cause 7 tests to fail simultaneously with the same root cause.

#### HIGH: `test_13_full_pipeline` and `test_14_monitoring_pipeline` are integration tests with loose assertions

- **Line 450:** `self.assertGreaterEqual(len(self.fake_gh.labels), 15)` -- "at least 15" is too loose. Production should create an exact number of labels. If label creation regresses from 25 to 16, this test still passes.
- **Line 573:** `self.assertIn("Completed: 8 SP", bd_text)` -- asserts specific SP count in burndown text. This is a good assertion but is fragile: it depends on exact formatting of `write_burndown`. If formatting changes from "Completed: 8 SP" to "Completed: 8 story points", the test breaks even though behavior is correct.

#### MEDIUM: `test_11_extract_sp` (lines 366-384) is a unit test inside an integration test file

- This test doesn't use the lifecycle infrastructure (MockProject, FakeGitHub) at all. It directly calls `update_burndown.extract_sp()`. It belongs in a unit test file, and duplicates tests already in `test_gh_interactions.py` (`TestExtractSP`).

#### MEDIUM: `test_12_commit_validation` (lines 388-399) is also a unit test misplaced in lifecycle

- Same issue: directly calls `validate_message()` without using the lifecycle setup. Duplicates coverage in `test_gh_interactions.py` (`TestValidateMessage`).

#### MEDIUM: `test_14_monitoring_pipeline` (lines 460-590) manually constructs issues instead of using create_issue

- Lines 485-522: Directly populates `self.fake_gh.issues` with hand-crafted dicts instead of using `populate_issues.create_issue()`. This means the test data shape may drift from what `create_issue` actually produces. If `create_issue` starts adding new fields, this test's hand-crafted data won't have them.

#### LOW: `MockProject` class is duplicated between `test_lifecycle.py` and `test_verify_fixes.py`

- Nearly identical `MockProject` classes exist in both files (lines 53-141 in test_lifecycle.py, lines 26-108 in test_verify_fixes.py). The one in test_lifecycle.py creates a real git repo; the one in test_verify_fixes.py creates a fake `.git/config`. Duplication increases maintenance burden.

#### LOW: No test for the monitoring pipeline when GitHub API is unreachable. All monitoring tests assume FakeGitHub responds correctly.

---

### 5. `tests/test_hexwise_setup.py`

**What it tests:** Scanner + ConfigGenerator + bootstrap + populate against the rich Hexwise fixture.

**~28 test methods across 2 classes**

#### HIGH: `TestHexwiseSetup` uses `setUpClass` shared state (test isolation failure)

- **Lines 37-78:** `setUpClass` runs `ProjectScanner.scan()` and `ConfigGenerator.generate()` once, storing results on `cls.scan` and `cls.config_dir`. All 20+ test methods in the class share this state. If any test mutates `self.scan` or writes to `self.config_dir`, it affects subsequent tests. While no test currently mutates, this is a fragile design. Adding a test that calls `gen.generate()` again would corrupt shared state.

#### MEDIUM: `test_giles_persona_has_required_sections` (lines 183-190) -- tests generated file content against hardcoded section names

- Line 188: Checks for `"## Vital Stats"`, `"## Origin Story"`, etc. in the generated Giles persona. If the Giles skeleton template is updated to rename sections, this test breaks. The test should verify structural completeness (has N sections, each non-empty) rather than exact section names.

#### MEDIUM: `test_populate_issues_parses_epic_stories` (lines 214-227) -- tests against fixture data that could change

- Line 227: `self.assertEqual(len(us0101.acceptance_criteria), 4)` -- asserts exactly 4 acceptance criteria. This is testing the fixture content, not parser behavior. If someone edits the Hexwise fixture, this test breaks for the wrong reason.

#### MEDIUM: `test_parse_milestone_stories_malformed_tables` (lines 267-296) -- weak assertion

- Lines 288-290: After parsing malformed input, asserts `self.assertIsInstance(stories, list)` -- this will pass even if the function returns an empty list when it should have found stories. The comment even says "The key assertion is that it returns a list without raising." This test verifies crash-resistance but not correctness.

#### LOW: `TestHexwisePipeline.test_full_setup_pipeline` (lines 341-407) overlaps heavily with `test_golden_run.py`

- The docstring at line 342 explicitly acknowledges this overlap. The test runs the same init -> labels -> milestones -> issues pipeline and makes the same assertions (17 issues, 3 milestones, 4 persona labels). The only difference is it doesn't capture golden snapshots. This is conscious duplication but still inflates the test count.

#### LOW: `test_ci_workflow_uses_configured_branch` (lines 420-428) -- mutates config dict

- Line 423: `config["project"]["base_branch"] = "develop"` -- mutates the config dict returned by `_generate_config()`. This is fine because `_generate_config` creates a new dict each time, but if this test were in `TestHexwiseSetup` (shared class), it would corrupt state.

---

### 6. `tests/test_golden_run.py`

**What it tests:** Golden snapshot regression: records or replays the full setup pipeline against Hexwise fixture.

**1 test method (sequential pipeline)**

#### CRITICAL: Golden test skips silently when recordings don't exist (lines 102-109)

- **Lines 102-109:** When `RECORD_MODE` is false and `replayer.has_recordings()` is false, the test calls `self.skipTest()`. This means on any CI system or fresh checkout without pre-recorded golden files, **the entire golden regression test is silently skipped**. The `warnings.warn()` on line 103 goes to stderr which is easily missed. A regression could be introduced and the golden test would provide zero protection.

#### HIGH: Golden test has only 1 test method covering 5 phases (lines 111-209)

- One monolithic test method runs 5 sequential phases. If Phase 3 (milestones) fails, Phases 4 (issues) and 5 (CI) never execute. In replay mode, a failure in any phase causes a single test failure with no visibility into which subsequent phases would also fail. This violates the principle of independent tests.

#### MEDIUM: `_check_or_record` lambda closures capture snapshot at call time (lines 93-109)

- Lines 145-148: `lambda snap: replayer.assert_files_match(snap, self.project)` -- the lambda captures `self.project` which is fine, but the snapshot `snap` is loaded inside `_check_or_record`. The assertion function only compares file paths and labels, not file contents. A golden test that doesn't verify file contents misses content regressions.

#### MEDIUM: No adversarial golden test cases

- The golden test only captures the happy path (everything succeeds). There are no golden recordings for error scenarios (e.g., what FakeGitHub state looks like when a milestone already exists, when a duplicate issue is skipped). This means the golden regression test only protects against regressions in the success path.

---

### 7. `tests/test_sprint_analytics.py`

**What it tests:** sprint_analytics.py: persona extraction, velocity, review rounds, workload, report formatting.

**11 test methods across 5 classes**

#### HIGH: `TestComputeReviewRounds.test_counts_review_events` relies on pre-shaped PR data (lines 134-164)

- **Lines 136-156:** Pre-populates `self.gh.prs` with dicts that include a `reviews` key. But the real `compute_review_rounds` function calls `gh_json` to fetch PRs, and the response format from GitHub doesn't include inline `reviews`. It requires a separate API call per PR to get reviews. FakeGitHub's `_pr_list` returns whatever is in `self.prs`, including the `reviews` field. This means the test is testing data it shaped itself, not the production data flow.
- If `compute_review_rounds` were refactored to fetch reviews via a separate API call, the FakeGitHub mock wouldn't support it and the test would break -- but more importantly, the current test doesn't verify the real review-fetching code path.

#### MEDIUM: `TestComputeVelocity.test_all_closed` (lines 47-69) -- pre-populates both milestones and issues

- Issues are directly appended to `self.gh.issues` with hand-crafted state. The test doesn't exercise the `issue list --milestone` filtering path through FakeGitHub because the issues are pre-populated. If FakeGitHub's milestone filtering is broken, this test still passes.

#### MEDIUM: `TestFormatReport.test_produces_valid_markdown` (lines 212-232) -- checks string containment, not markdown structure

- Line 228: `self.assertIn("16/16 SP (100%)", report)` -- if the format changes to `16 of 16 SP`, the test fails but the behavior is fine. Tests formatting, not meaning. No test verifies the report is valid markdown (headers, bullet lists properly structured).

#### LOW: No test for `sprint_analytics.main()` entry point

- The `main()` function is never called in tests. It likely calls all compute functions and prints the report. If `main()` crashes on argument parsing or milestone detection, no test catches it.

---

### 8. `tests/test_sprint_teardown.py`

**What it tests:** sprint_teardown.py: classify_entries, collect_directories, resolve_symlink_target, remove_symlinks, remove_generated, remove_empty_dirs, main().

**17 test methods across 8 classes**

This is one of the better test files. It uses real filesystem operations (symlinks, directories) and tests both positive and negative cases.

#### MEDIUM: `TestRemoveGenerated.test_interactive_yes_no` (lines 307-318) -- mocks `input()` but doesn't verify prompts

- Lines 307: `@patch("builtins.input", side_effect=["y", "n"])`. The test patches stdin but never asserts what prompt text was displayed. If `remove_generated` changes its prompt from "Remove X?" to nothing, the test still passes.

#### MEDIUM: `TestTeardownMainExecute.test_execute_removes_generated` (lines 502-511) -- mocks `check_active_loops` but doesn't test the active-loop abort path

- Line 507: `sprint_teardown.check_active_loops, return_value=[]`. The test mocks active loops to return empty. No test verifies what happens when `check_active_loops` returns non-empty (active loops should block teardown).

#### LOW: `TestTeardownMainDryRun` and `TestTeardownMainExecute` change cwd in setUp (lines 461-462, 494)

- `os.chdir(self.project_root)` in setUp. While the tests properly restore cwd in tearDown, if a test raises before tearDown, cwd remains changed. The `test_verify_fixes.py` has the same pattern. Using `addCleanup` would be more robust (and test_lifecycle.py correctly uses `self.addCleanup`).

---

### 9. `tests/test_verify_fixes.py`

**What it tests:** Config generation, CI generation, agent frontmatter, evals validation, load_config error handling, team index parsing.

**~18 test methods across 7 classes**

#### HIGH: `TestEvalsGeneric` (lines 271-293) -- tests absence of strings, which is fragile

- Lines 275-292: Three tests assert that the evals.json file does NOT contain "Dreamcatcher", "Rachel", "cargo build", or "cargo test". These are negative assertions: they pass as long as those strings are absent. If someone adds a new hardcoded reference (e.g., "HexWise"), these tests wouldn't catch it. Testing for absence of specific strings is a whack-a-mole approach that doesn't scale.

#### MEDIUM: `TestConfigGeneration._generate()` (lines 123-128) -- shared helper called by every test but with no assertion on its own

- The helper generates config but doesn't verify success. If `gen.generate()` silently fails (e.g., returns without writing files), every test that calls `_generate()` would fail later at a confusing point.

#### MEDIUM: `TestLoadConfigRaisesConfigError` (lines 295-331) -- all 4 tests use the same input ("nonexistent-dir")

- Lines 308, 314, 319, 328 all call `load_config("nonexistent-dir")`. They test four properties of the same error: it's a ConfigError, it's a ValueError, it's not a SystemExit, and it has a descriptive message. This is thorough for one error case but there's only one error case tested. No test for: config dir exists but project.toml is missing, config dir exists but TOML is malformed, etc.

#### LOW: `TestAgentFrontmatter` (lines 248-268) -- reads actual repo files, not fixtures

- Lines 263-264: `agents = ROOT / "skills" / "sprint-run" / "agents"` then reads `implementer.md` and `reviewer.md` from the actual repo. If these files are temporarily deleted during a rebase, the test fails for infrastructure reasons, not code bugs.

#### LOW: `TestCIGeneration.test_no_duplicate_test_job` (lines 219-245) -- brittle line-level assertion

- Line 242: `test_run_lines = [l for l in yaml.splitlines() if l.strip().startswith("run: cargo test")]`. This regex-style check on YAML output is brittle. If the indentation changes or if `run:` is on a different line from `cargo test`, the check breaks.

---

### 10. `tests/test_validate_anchors.py`

**What it tests:** validate_anchors.py: namespace resolution, anchor def scanning, anchor ref scanning, check mode, fix mode.

**~20 test methods across 6 classes**

#### MEDIUM: `TestNamespaceMap.test_all_mapped_files_exist` (lines 40-43) -- tests repo state, not code

- Line 42: `self.assertTrue(full.exists(), ...)`. This test verifies that every file in `NAMESPACE_MAP` exists on disk. It tests the repo's file structure, not the `validate_anchors.py` code. If someone deletes a mapped file, this test fails -- but that's a repo integrity issue, not a code bug.

#### MEDIUM: `TestFindAnchorDefs` and `TestFindAnchorRefs` use `delete=False` temp files without cleanup (lines 56-98, 107-141)

- Lines 56, 67, 78, 94, 108, 116, 123, 130, 137: All use `tempfile.NamedTemporaryFile(delete=False)` but never call `os.unlink()` to clean up. While the OS will eventually clean temp files, this leaks file descriptors and disk space during test runs.

#### LOW: `TestFixMode` (lines 211-281) -- good coverage but no test for concurrent fix of multiple anchors in the same file

- Tests fix of single anchor, fix above definition, skip existing, fix markdown heading. But no test where two missing anchors need to be inserted into the same file. The line number calculation could break when inserting the first anchor shifts lines for the second.

---

### 11. `tests/test_sync_backlog.py`

**What it tests:** sync_backlog.py: file hashing, state persistence, debounce/throttle scheduling, do_sync, main() entry point.

**~17 test methods across 5 classes**

#### HIGH: `TestMain.test_second_run_syncs` (lines 266-280) -- flaky timing dependency

- **Lines 276-278:** Calls `sync_backlog.main()` twice in sequence. The first call debounces, the second call syncs. This depends on the debounce logic seeing the same hashes on the second call (meaning files haven't changed between calls). Since both calls happen within milliseconds, this works. But if the debounce has a minimum time window, this test could become flaky.
- More critically, the test depends on the internal state file being written and read between calls. If `save_state` or `load_state` has a race condition, this test would be flaky.

#### MEDIUM: `TestCheckSync` (lines 79-154) -- good state machine tests but missing edge cases

- Tests: no change, first change (debounce), still changing (re-debounce), stabilized (sync), revert (cancel), throttle block, throttle expired. This covers the state machine well.
- Missing: what happens when `pending_hashes` has extra files not in current hashes (files deleted), what happens when `file_hashes` is corrupted (not a dict), what happens when `last_sync_at` is not a valid ISO datetime string.

#### MEDIUM: `TestDoSync.test_do_sync_creates_milestones_and_issues` (lines 185-195) -- verifies FakeGitHub state, not return value semantics

- Line 194-195: `self.assertEqual(created["milestones"], len(fake_gh.milestones))`. This verifies the return value matches FakeGitHub state, which is a tautology if `do_sync` simply reads from FakeGitHub after creating. The real question is whether the created milestones match the input milestone file content.

#### LOW: `TestMain._setup_project` (lines 213-247) creates an elaborate setup with inlined TOML strings

- The setup creates project.toml with string interpolation of paths. If `validate_project` changes its requirements, this setup needs manual updating. A shared fixture would be more maintainable.

---

### 12. `tests/test_release_gate.py`

**What it tests:** release_gate.py: calculate_version, bump_version, validate_gates, gate_tests, gate_build, find_milestone_number, do_release.

**~25 test methods across 8 classes**

#### HIGH: `TestDoRelease.test_happy_path` (lines 418-491) -- over-mocked, tests wiring not behavior

- **Lines 418-421:** Patches 5 things: `calculate_version`, `write_version_to_toml`, `subprocess.run`, `find_milestone_number`, and `gh`. With everything mocked, the test is verifying that `do_release` calls its dependencies in the right order with the right arguments. It's testing the orchestration wiring, not the actual behavior. If any of the mocked functions had a subtle bug in their real implementation, this test would still pass.
- **Lines 453-469:** Assertions inspect `mock_run.call_args_list` to verify exact argument order of git commands. This is extremely brittle -- any refactor that changes command order (e.g., adding a `git fetch` step) breaks the test.

#### MEDIUM: `TestGateTests.test_no_commands_configured` (line 245-249) -- tests absence of config key

- Line 246: `config = {"ci": {}}` -- no `check_commands` key. Test asserts `passed=True` with "No check_commands" message. This is correct behavior, but there's no test for `check_commands` being an empty list `[]` (which is different from missing). An empty list might cause different behavior.

#### MEDIUM: `TestValidateGates.test_all_pass` (lines 146-163) -- uses empty CI commands to bypass test/build gates

- Lines 157-158: `"check_commands": [], "build_command": ""`. This means `gate_tests` and `gate_build` trivially pass (no commands to run). The test verifies all 5 gates pass, but 2 of them pass vacuously. A more rigorous test would provide real commands that succeed.

#### MEDIUM: `_make_subprocess_side_effect` (lines 344-384) -- complex test helper that is itself untested

- This 40-line function builds a `side_effect` for `subprocess.run` with multiple conditional branches (tag_fails, commit_fails, push_tag_fails, rev-parse detection). If this helper has a bug, multiple `TestDoRelease` tests produce incorrect results. The helper should have its own unit tests, or at least be simpler.

#### LOW: `TestCalculateVersion` tests (lines 39-83) mock both `find_latest_semver_tag` and `parse_commits_since`

- All 4 tests mock both functions, leaving only the `calculate_version` orchestration logic under test. The actual tag-finding and commit-parsing logic is never tested in this file (may be tested elsewhere, but the coupling between version calculation and commit parsing is untested).

---

## Cross-Cutting Anti-Patterns

### 1. Copy-paste pipeline inflation (HIGH)

Three separate files test the same init -> bootstrap -> populate pipeline:
- `test_lifecycle.py:test_13_full_pipeline` (minimal MockProject, loose assertions)
- `test_hexwise_setup.py:TestHexwisePipeline.test_full_setup_pipeline` (Hexwise fixture, exact assertions)
- `test_golden_run.py:test_golden_full_setup_pipeline` (Hexwise fixture, golden snapshots)

The docstrings in each test explicitly acknowledge this overlap and explain why each exists. But in practice, if `populate_issues.create_issue` has a bug, all three tests fail with the same error. This creates noise in CI rather than signal. Two of these three could be removed if the golden test reliably ran (see Critical finding about skipTest).

### 2. Mock-level duplication (HIGH)

Multiple test files (`test_gh_interactions.py` and `test_lifecycle.py`) test the same functions (extract_sp, validate_message, bump_version) independently. At least 20 tests are pure duplicates across files:
- `TestExtractSP` in test_gh_interactions.py (13 tests) vs `test_11_extract_sp` in test_lifecycle.py (3 tests)
- `TestValidateMessage` in test_gh_interactions.py (9 tests) vs `test_12_commit_validation` in test_lifecycle.py (6 tests)
- `TestBumpVersion` in test_gh_interactions.py (5 tests) vs `TestBumpVersion` in test_release_gate.py (6 tests)

### 3. Fixture data as assertions (MEDIUM)

Multiple tests assert specific counts or strings that come from the Hexwise fixture:
- "17 issues" (3 files)
- "3 milestones" (3 files)
- "4 persona labels" (2 files)
- US-0101 acceptance_criteria count == 4 (1 file)

If the Hexwise fixture is updated, many tests break. These assertions test the fixture, not the code.

### 4. No fuzz testing or property-based testing (MEDIUM)

The TOML parser, story ID extractor, and markdown parsers are all hand-rolled and complex, but there are no randomized or property-based tests. These functions process untrusted input (user-authored markdown and TOML) and should be tested with random/adversarial inputs.

### 5. No performance or resource tests (LOW)

No test verifies that functions handle large inputs gracefully (e.g., 1000 milestones, 10000 issues, deeply nested TOML). The `warn_if_at_limit` function exists to detect truncation at 500 results, but no test creates 500+ items in FakeGitHub to verify the warning fires.

---

## What SHOULD Be Tested But Isn't

### Production functions with zero direct test coverage:

1. **`validate_config.main()`** -- the CLI entry point for config validation
2. **`sprint_init.main()`** -- the CLI entry point for project initialization
3. **`sprint_init.print_scan_results()`** -- output formatting
4. **`sprint_init.print_generation_summary()`** -- output formatting
5. **`commit.run_commit()`** -- the actual commit execution function (only `validate_message` and `check_atomicity` are tested)
6. **`commit.main()`** -- CLI entry point
7. **`sprint_analytics.main()`** -- CLI entry point
8. **`validate_config.list_milestone_issues()`** -- never directly tested
9. **`validate_config._print_errors()`** -- never tested
10. **`validate_config.get_ci_commands()`** -- never tested (trivial but still)
11. **`validate_config._has_closing_bracket()`** -- never directly tested
12. **`validate_config._count_trailing_backslashes()`** -- never directly tested
13. **`validate_config._unescape_toml_string()`** -- never directly tested
14. **`validate_config._strip_inline_comment()`** -- never directly tested
15. **`validate_config._parse_value()`** -- never directly tested (exercised through `parse_simple_toml` but edge cases not isolated)

### Error paths not tested:

1. **FakeGitHub receiving unknown subcommands** -- e.g., `gh issue view` (not just `list/create/edit/close`)
2. **Network timeouts in gh()** -- production gh() can timeout but no test simulates this
3. **File permission errors** -- `sprint_teardown.remove_symlinks` with read-only files
4. **Unicode handling** -- persona files with non-ASCII names (e.g., accented characters)
5. **Concurrent access** -- two sprint-monitor loops running simultaneously
6. **Empty milestone title** -- what happens when a milestone has title=""?
7. **Story ID collision** -- two stories with the same US-XXXX ID in different milestones

---

## Verdict

The test suite is **quantitatively impressive** (326+ tests) but has significant qualitative issues:

1. **~50 tests are duplicates** across files, inflating the count without adding coverage.
2. **~20 tests are tautologies or fixture-assertions** that can't meaningfully fail.
3. **The golden regression test silently skips** on fresh checkouts, providing zero protection exactly when it's needed most.
4. **FakeGitHub's `--jq` no-op** means any production code using `--jq` for data shaping is tested against a different contract.
5. **Error paths and edge cases** are the biggest coverage gap -- most tests follow happy paths.

A realistic test count after deduplication would be ~270 meaningful tests. Of those, roughly 240 test happy paths and 30 test error paths. For a codebase with ~15 production scripts, each having 5-15 public functions with multiple code paths, this represents decent but not thorough coverage.

**Priority fixes:**
1. Make the golden test fail (not skip) when recordings are absent
2. Fix the FakeGitHub `--jq` fidelity gap or explicitly document it as a known limitation
3. Delete duplicate test methods across files (especially extract_sp, validate_message, bump_version)
4. Add error-path tests for the 15 untested production functions
5. Replace fixture-count assertions with structural assertions
