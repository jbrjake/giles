# Test Quality Audit

Adversarial review of all 15 test files in `tests/` for anti-patterns that create
false confidence. Organized by severity tier, then by file.

---

## Tier 1: Actively Harmful (tests that mask bugs)

### AP-1: Mock-Return-Value Testing (The Mockingbird)

Tests that set `mock.return_value = X`, call a function, then assert `result == X`.
These test the mock, not the code. The function could return `mock.return_value`
directly and every test would still pass.

**test_release_gate.py:43-51** `TestCalculateVersion.test_no_tags_uses_0_1_0_base`
```python
mock_tag.return_value = None
mock_commits.return_value = [{"subject": "feat: initial", "body": ""}]
new_ver, base_ver, bump, commits = calculate_version()
self.assertEqual(base_ver, "0.1.0")
self.assertEqual(bump, "minor")
self.assertEqual(new_ver, "0.2.0")
```
Both `find_latest_semver_tag` and `parse_commits_since` are mocked. The test verifies
that `calculate_version()` correctly transforms mock inputs into outputs, but the two
critical functions that actually *do* the work (finding tags, parsing commits) are
completely bypassed. If `find_latest_semver_tag` starts returning garbage from real
git, this test won't catch it. This pattern repeats across all 4 tests in this class
(lines 43-83). The `determine_bump` and `bump_version` sub-functions *are* tested
independently elsewhere, so the real gap is: `calculate_version`'s *orchestration
logic* is the only thing tested, and it's trivial (two function calls + one
conditional). The test looks like it covers version calculation end-to-end, but it
does not.

**Bug that could slip through:** `find_latest_semver_tag` could silently fail (return
`None` when tags exist), and `parse_commits_since` could return malformed dicts. Neither
would be caught.

**test_sprint_runtime.py:461-471** `TestFindMilestoneTitle`
```python
mock_find.return_value = {"title": "Sprint 1: Walking Skeleton", "number": 1}
result = sync_tracking.find_milestone_title(1)
self.assertEqual(result, "Sprint 1: Walking Skeleton")
```
This is a textbook Mockingbird. The function extracts `["title"]` from whatever
`find_milestone` returns. The test mocks find_milestone, then asserts the title
it injected. The test would pass even if `find_milestone_title` returned a hardcoded
string. (2 tests in this class, both Mockingbirds.)

**test_sprint_runtime.py:121-131** `TestCreateLabel.test_creates_label`
```python
mock_gh.return_value = ""
bootstrap_github.create_label("test-label", "ff0000", "A test label")
mock_gh.assert_called_once()
```
Only checks that `gh` was called once. Does not verify the args include
`--color ff0000` or `--description "A test label"`. The color and description
could be silently dropped and this test would pass. Lines 128-130 check only
that `"label"`, `"create"`, and `"test-label"` appear in args -- but not color
or description.

### AP-2: Tautological / Green Bar Tests

**test_sprint_runtime.py:62-72** `TestCheckCI.test_failing_run`
```python
mock_gh.return_value = "error: something broke\nfatal: test failed"
report, actions = check_status.check_ci()
self.assertIn("1 failing", report[0])
self.assertTrue(len(actions) > 0)
```
The `self.assertTrue(len(actions) > 0)` is the weakest possible assertion. It says
"at least one action", but doesn't verify the action actually relates to the failing
run, contains the error message, or is actionable. If `check_ci` returned
`["drink more coffee"]` as an action, this test would pass.

**test_gh_interactions.py:358** `TestGatePRs.test_no_prs`
```python
self.assertTrue(len(detail) > 0, "Detail must not be empty")
```
The assertion is `len(detail) > 0` -- a single character passes. The gate function
could return "x" and this test is green. Similarly at line 378.

### AP-3: Tests That Pass If Function Returns Garbage

**test_sprint_runtime.py:132-143** `TestCreateLabel.test_label_error_handled`
```python
mock_gh.side_effect = RuntimeError("already exists")
bootstrap_github.create_label("existing-label", "ff0000")
mock_print.assert_called_once()
warning_msg = mock_print.call_args[0][0]
self.assertIn("existing-label", warning_msg)
self.assertIn("already exists", warning_msg)
```
This tests the error-handling path, which is good. However, it tests the *print
message*, not the behavior. If `create_label` caught the error but still created a
corrupted label entry, this test would pass. The test does not check that the label
was NOT created after the error.

---

## Tier 2: False Security (tests that look thorough but aren't)

### AP-4: Happy Path Tourist (Missing Negative Tests)

**test_sync_backlog.py** -- `TestDoSync`
Only tests two scenarios: first sync (creates milestones + issues), and idempotent
second sync. Missing:
- What happens when `do_sync` is called with invalid config (e.g., missing `backlog_dir`)?
- What happens when milestone files have malformed content?
- What happens when FakeGitHub returns errors during sync?
- What happens when `get_milestones()` returns an empty list?

These are real operational scenarios. A malformed milestone file could crash the sync
without any test catching it.

**test_validate_anchors.py** -- `TestFixMode`
Tests 5 fix scenarios, all with well-formed inputs. Missing:
- What happens when the source file is read-only?
- What happens when the anchor target is ambiguous (multiple `def my_func` in one file)?
- What happens when the file has mixed encodings?
- `fix_missing_anchors` return value is checked, but the *content correctness* of the
  inserted anchor is only spot-checked (just verifies the string appears).

**test_sprint_analytics.py** -- `TestComputeWorkload`
Only tests the "persona labels present" and "no persona labels" cases. Missing:
- Issue with multiple persona labels (ambiguous -- which wins?)
- Issue in the wrong milestone (should not be counted)
- Empty milestone (zero issues)

**test_gh_interactions.py** -- `TestGateCI`
Tests passing, failing, and no-runs. Missing:
- CI run that is still `in_progress` (not completed) -- what does the gate return?
- Multiple runs with mixed conclusions (some success, some failure)
- Run on a non-main branch (should it be excluded?)

**test_sprint_teardown.py** -- `TestTeardownMainExecute`
Only tests the happy path (generated file removed). Missing:
- What if removal fails due to permissions?
- What if the directory structure is deeper than expected?
- What if `check_active_loops` returns active loops and there's no `--force`?

### AP-5: Overcovered by Name, Undercovered by Behavior

**test_pipeline_scripts.py:32-89** `TestTeamVoices`
6 tests for `extract_voices`, but all test with the same Hexwise fixture data.
The tests verify that specific personas appear and specific quotes contain expected
words. But they never test:
- What happens with malformed blockquote syntax (missing `>` prefix)?
- What happens when a persona name contains special characters?
- What happens with deeply nested markdown sections?

The fixture-coupling means these tests would all break if the Hexwise fixture
content changed, but would NOT catch bugs in edge-case parsing.

**test_pipeline_scripts.py:98-153** `TestTraceability`
All 6 tests run against the Hexwise fixture. The "detects gaps" test (line 123)
is the only one that creates synthetic data -- and it's minimal (one story, zero
test cases). The positive-path tests all rely on Hexwise having complete traceability.
If `build_traceability` had a bug that only manifested when a story had *multiple*
test cases with the same prefix, no test would catch it.

**test_lifecycle.py** -- `test_14_monitoring_pipeline`
This is a 100-line integration test that exercises sync_tracking, update_burndown,
and check_status together. It is thoroughly written, but the burndown assertions
only check string containment:
```python
self.assertIn("Completed: 8 SP", bd_text)
self.assertIn("Remaining: 5 SP", bd_text)
```
If `write_burndown` put the numbers in the wrong table column, or duplicated entries,
or corrupted the markdown table structure, these assertions would still pass as long
as the strings appear *somewhere* in the output.

### AP-6: Fixture-Coupled Tests

**test_hexwise_setup.py** -- Entire file
All tests in `TestHexwiseSetup` use `setUpClass` to scan and generate config once.
If any test modifies the shared state (config_dir contents), all subsequent tests
are affected. The `@classmethod setUpClass` pattern with shared `cls.scan` and
`cls.config_dir` means test isolation is broken by design.

Specific risk: `test_config_has_three_milestones` (line 137) counts `.md` files in
the milestones directory. If the hexwise fixture adds or removes a milestone file,
this test breaks with a count mismatch -- but so would every other test that depends
on `cls.config_dir`. This is a cascade failure waiting to happen.

**test_golden_run.py** -- `test_golden_full_setup_pipeline`
Depends entirely on golden snapshot files existing. When they don't exist:
- In CI: fails with an explicit error (good)
- Locally: *skips the test* (line 116). This means local developers get no coverage
  from this test unless they remember to run `GOLDEN_RECORD=1` first. The test
  appears in the test count but provides zero verification.

### AP-7: String-Matching Assertions on Error Messages

**test_gh_interactions.py:58-61** `TestValidateMessage.test_invalid_type`
```python
ok, err = validate_message("feature: add login")
self.assertFalse(ok)
self.assertIn("Invalid conventional commit", err)
```
This checks the error *message text*, not the error *behavior*. If the message
changes from "Invalid conventional commit" to "Bad commit format", the test breaks
even though the behavior is identical. This pattern repeats across 5+ tests in
TestValidateMessage. The `self.assertFalse(ok)` is the meaningful assertion; the
string checks are fragile.

**test_sprint_runtime.py:288-300** `TestCollectSprintNumbers.test_no_heading_no_number_warns`
```python
self.assertIn("defaulting to sprint 1", captured.getvalue())
```
Tests the exact stderr warning text. If the message is rephrased, the test breaks
with no change in behavior.

### AP-8: Permissive Validators

**test_sprint_runtime.py:54-59** `TestCheckCI.test_all_passing`
```python
call_args = mock_gh.call_args[0][0]
self.assertIn("run", call_args)
self.assertIn("--json", call_args)
```
Uses `assertIn` on a list to verify CLI arguments. The check passes if "run" appears
*anywhere* in the args list -- it could be a value, not a command. A more robust
check would verify the positional structure: `args[0] == "run"` and `"--json"` is
followed by the expected field list.

---

## Tier 3: Missed Opportunities

### AP-9: Coverage Gaming (Call Without Meaningful Assert)

**test_verify_fixes.py:201-222** `TestEvalsGeneric`
Three tests that read `evals.json` and check that certain strings are NOT present:
```python
self.assertNotIn("Dreamcatcher", text)
self.assertNotIn("Rachel", text)
self.assertNotIn("cargo build", text)
```
These verify that hardcoded project-specific values were removed from evals, but they
don't verify that the evals *work* -- no test loads the eval scenarios and validates
their structure, completeness, or that they exercise real skill behaviors. The file
could be empty JSON and all three tests would pass.

**test_verify_fixes.py:178-199** `TestAgentFrontmatter`
Tests that agent `.md` files start with `---` and contain `name:` and `description:`.
Does not verify the frontmatter parses as valid YAML, or that the values are non-empty,
or that the descriptions match what the skill system expects. The files could have
`name: ""` and `description: ""` and both tests pass.

**test_verify_fixes.py (multiple classes, lines 870-1134)**
Approximately 15 `main()` integration tests follow this pattern:
```python
def test_missing_config_exits_1(self):
    with self.assertRaises(SystemExit) as ctx:
        module.main()
    self.assertEqual(ctx.exception.code, 1)
```
These verify that `main()` exits with code 1 on bad input. This is the bare minimum
"doesn't crash" test. They don't verify *what* error message is shown, whether
cleanup happens, or whether the error path handles edge cases. While they prevent
regressions where `main()` would hang or exit 0 on bad input, they provide no insight
into the actual error-handling quality.

### AP-10: Copy-Paste Test Setup That Masks Bugs

**test_sprint_teardown.py** -- 7 test classes, each with identical setUp/tearDown
Each class creates its own `tempfile.mkdtemp()`, `sprint-config` directory, etc.
The setup is nearly identical across TestClassifyEntries, TestCollectDirectories,
TestResolveSymlinkTarget, TestRemoveSymlinks, TestRemoveGenerated, TestRemoveEmptyDirs,
and TestFullTeardownFlow. This isn't harmful per se, but the duplication means:
- If there's a bug that only manifests with a specific directory structure, each
  class creates its own minimal structure and the bug escapes.
- No test creates a *realistic* directory tree with all entry types (symlinks,
  generated, unknown, nested, broken symlinks) simultaneously.

`TestFullTeardownFlow` comes closest but still uses a minimal tree.

**test_bugfix_regression.py** -- git-dirty check tests (lines 544-634)
Three tests that mock `subprocess.run` with identical side_effect functions
(lines 549-562, 577-589, 601-615). Each one re-implements the same
`side_effect` pattern to distinguish `git` from other subprocess calls.
The side_effect at line 577 (`test_dirty_files_proceed_with_force`) is
literally copy-pasted from line 549 with zero changes -- same mock behavior,
different test name. If the git-dirty check logic changed its subprocess
call pattern, the side_effect might silently stop matching.

### AP-11: Shallow End (Unit Tests Without Integration Path)

**Scripts with no integration test covering the full call chain:**

1. **`scripts/team_voices.py`**: `extract_voices()` is tested against fixture files,
   but the full path from `main()` -> `load_config()` -> `extract_voices()` ->
   format output is only tested as "main exits 1 with no config" (a crash test).
   No test verifies that `main()` with valid config produces correct output.

2. **`scripts/traceability.py`**: Same pattern. `build_traceability()` is tested,
   `main()` is only tested for exit-code-on-error. No test verifies the full
   main() -> format_report() -> print output path.

3. **`scripts/test_coverage.py`**: `check_test_coverage()` is tested, but
   `main()` only has an "exits 1 on bad config" test. No test exercises the
   full pipeline with valid config.

4. **`scripts/manage_epics.py` and `scripts/manage_sagas.py`**: Both only have
   "exits 1 on no args" tests. The actual CRUD operations (add_story, remove_story,
   reorder_stories, etc.) are tested in test_pipeline_scripts.py but never through
   the `main()` entry point. A bug in argument parsing would escape.

### AP-12: Mutation Resilience Concerns

Several tests would survive common mutations:

**test_sprint_analytics.py:276-309** `TestFormatReport`
```python
self.assertIn("### Sprint 1 — First Light", report)
self.assertIn("16/16 SP (100%)", report)
```
If `format_report` swapped the order of sections, duplicated content, or inserted
garbage text between the expected strings, all assertions pass. The test verifies
*presence* of strings, not *structure* of the markdown.

**test_lifecycle.py:227-244** `test_09_release_notes`
```python
self.assertIn("v0.2.0", notes)
self.assertIn("## Features", notes)
self.assertIn("## Fixes", notes)
self.assertIn("add login flow", notes)
```
Same pattern: presence checks. If the release notes duplicated every entry, put
fixes under "Features" and vice versa, or broke the markdown structure, every
assertion still passes.

---

## Summary Statistics

| Anti-Pattern | Count | Severity |
|-------------|-------|----------|
| Mock-return-value testing | 8 instances | High |
| Weak/permissive assertions | 12 instances | Medium |
| Happy-path-only coverage | 6 functions | Medium |
| Fixture-coupled tests | 2 test classes | Medium |
| String-matching on error msgs | 8 instances | Low |
| Coverage gaming (call w/o assert) | ~18 tests | Low-Medium |
| Missing integration paths | 5 scripts | Medium |
| Copy-paste test setup | 3 test files | Low |

## What's Actually Good

To be fair, several things are done well:

1. **FakeGitHub** is a sophisticated test double that replaces subprocess calls with
   in-memory state. It has strict mode, flag validation, and milestone counter tracking.
   This is significantly better than bare mocks.

2. **Property-based tests** (test_property_parsing.py) use Hypothesis to fuzz
   parse_simple_toml, extract_story_id, extract_sp, _yaml_safe, and _parse_team_index.
   These are genuinely high-value tests.

3. **MonitoredMock/patch_gh** (gh_test_helpers.py) is a clever guard against the
   mock-return-value anti-pattern. It emits warnings when tests don't inspect call args.

4. **The BH-regression tests** show evidence of adversarial testing -- many tests
   were written to pin specific bugs found in prior passes.

5. **Test test** pattern: `TestAssertFilesMatchAdversarial` in test_golden_run.py
   tests that the golden replayer actually detects mismatches. This meta-test prevents
   the golden comparison from silently passing.

## Top Recommendations

1. **Replace mock-patched `calculate_version` tests** with FakeGitHub-backed tests
   that create real git tags and commits in the temp repo, then call `calculate_version`
   with only `subprocess.run` patched (for `gh` commands, not `git` commands).

2. **Add structure assertions** to format_report and generate_release_notes tests.
   Instead of `assertIn("## Features", notes)`, parse the markdown and verify section
   ordering, entry counts, and content placement.

3. **Add happy-path main() tests** for team_voices, traceability, test_coverage,
   manage_epics, and manage_sagas that exercise the full pipeline with valid config,
   not just exit-code tests.

4. **Add negative tests for do_sync**: malformed milestone files, FakeGitHub errors
   during sync, empty milestone lists.

5. **Replace string-matching on error messages** with behavioral assertions (does the
   function return the right status? does it clean up correctly?) rather than checking
   exact error text.
