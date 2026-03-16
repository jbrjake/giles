# Test Assertion Quality Audit

Audit of all test files in `tests/` for weak assertions that would pass even if production code was broken.

---

## Category 1: Existence checks that should be value checks

### 1.1 `test_hexwise_setup.py` > `TestHexwiseSetup` > `test_scanner_finds_rules_and_dev`
```python
self.assertIsNotNone(self.scan.rules_file.value)
self.assertIsNotNone(self.scan.dev_guide.value)
```
**Should assert:** The actual file path matches the expected location (e.g., `RULES.md` and `DEVELOPMENT.md` in the hexwise fixture). Currently, if the scanner returned a random wrong file, this test would still pass.
**Would catch a real bug?** No. A scanner that returned `/tmp/garbage.md` as the rules file would pass this test.

### 1.2 `test_hexwise_setup.py` > `TestHexwiseSetup` > `test_scanner_detects_hexwise_deep_docs`
```python
self.assertIsNotNone(result.prd_dir)
self.assertIsNotNone(result.test_plan_dir)
self.assertIsNotNone(result.sagas_dir)
self.assertIsNotNone(result.epics_dir)
self.assertIsNotNone(result.story_map)
```
**Should assert:** Each path points to the correct directory under the hexwise fixture. For example, `result.prd_dir` should end with `docs/prd`. Currently any non-None value passes.
**Would catch a real bug?** No. If the scanner confused `prd_dir` with `sagas_dir`, this test would not notice.

### 1.3 `test_hexwise_setup.py` > `TestHexwiseSetup` > `test_optional_paths_present`
```python
self.assertIsNotNone(get_prd_dir(config))
self.assertIsNotNone(get_test_plan_dir(config))
self.assertIsNotNone(get_sagas_dir(config))
self.assertIsNotNone(get_epics_dir(config))
self.assertIsNotNone(get_story_map(config))
```
**Should assert:** Each returned path resolves to an existing directory under the hexwise project tree. Currently any non-None string passes.
**Would catch a real bug?** No. Returning a stale or wrong path would pass.

### 1.4 `test_hexwise_setup.py` > `TestHexwiseSetup` > `test_config_generator_includes_optional_paths`
```python
self.assertIsNotNone(config["paths"].get("prd_dir"))
self.assertIsNotNone(config["paths"].get("sagas_dir"))
self.assertIsNotNone(config["paths"].get("epics_dir"))
```
**Should assert:** The values are valid paths that exist on disk and point to the correct directories.
**Would catch a real bug?** No. An empty string `""` is not None and would pass.

### 1.5 `test_sprint_runtime.py` > `TestFindMilestoneTitle` > `test_no_match_returns_none`
```python
self.assertIsNone(result)
```
**Acceptable.** This is testing a negative case where None is the correct return value. No issue here.

### 1.6 `test_sprint_analytics.py` > `TestExtractPersona` > `test_no_persona`
```python
self.assertIsNone(sprint_analytics.extract_persona(issue))
```
**Acceptable.** Negative case, None is the correct answer.

### 1.7 `test_sprint_teardown.py` > `TestResolveSymlinkTarget` > `test_valid_symlink`
```python
result = sprint_teardown.resolve_symlink_target(link)
self.assertIsNotNone(result)
self.assertEqual(result, target.resolve())
```
**Acceptable.** The assertIsNotNone is redundant (assertEqual would fail on None) but the value check is present.

---

## Category 2: Length checks that should be content checks

### 2.1 `test_lifecycle.py` > `TestLifecycle` > `test_13_full_pipeline`
```python
self.assertGreaterEqual(len(self.fake_gh.labels), 15,
                        "Labels: static + persona + sprint + saga + kanban")
```
**Should assert:** At minimum, specific critical labels exist (e.g., `kanban:todo`, `kanban:done`, `persona:rusti`, `persona:palette`). The count check only ensures "enough things exist" but a bug that creates 15 copies of the same label would pass.
**Would catch a real bug?** Unlikely. If `create_static_labels()` duplicated one label 15 times and skipped the rest, this passes.

### 2.2 `test_hexwise_setup.py` > `TestHexwisePipeline` > `test_full_setup_pipeline`
```python
self.assertGreaterEqual(len(self.fake_gh.labels), 17,
                        "Should have static + persona + sprint labels")
```
**Should assert:** Spot-check specific critical labels exist. A count >= 17 tells you nothing about what those labels are.
**Would catch a real bug?** Partially. The test does also verify persona label count and story IDs separately, so the label count alone is a weaker element in an otherwise decent test.

### 2.3 `test_hexwise_setup.py` > `TestHexwisePipeline` > `test_state_dump`
```python
self.assertGreaterEqual(len(state["labels"]), 13)  # static labels minimum
```
**Should assert:** Specific labels are present in the dump, not just a count. This is testing the dump mechanism, not label creation, but the count is still fragile.
**Would catch a real bug?** No. If `dump_state()` returned wrong label data, this would still pass as long as the count was >= 13.

### 2.4 `test_validate_anchors.py` > `TestCheckAnchors` > `test_broken_ref_detected`
```python
self.assertEqual(len(broken), 1)
self.assertIn("nonexistent", broken[0])
```
**Mostly OK.** The length check is followed by a content check. Minor improvement: also verify `broken[0]` mentions the file/line.

### 2.5 `test_validate_anchors.py` > `TestCheckAnchors` > `test_unknown_namespace_is_broken`
```python
self.assertEqual(len(broken), 1)
self.assertIn("typomod", broken[0])
```
**Mostly OK.** Same pattern as 2.4.

### 2.6 `test_validate_anchors.py` > `TestCheckAnchors` > `test_unreferenced_anchor_reported`
```python
self.assertEqual(len(unreferenced), 1)
self.assertIn("mymod.my_func", unreferenced[0])
```
**Mostly OK.** Same pattern.

### 2.7 `test_validate_anchors.py` > `TestFindAnchorDefs` > `test_multiple_anchors`
```python
self.assertEqual(len(defs), 2)
self.assertIn("mod.func_a", defs)
self.assertIn("mod.CONST_B", defs)
```
**Mostly OK.** The key check supplements the length check. Missing: line number validation (defs values are line numbers and are never checked).
**Would catch a real bug?** Partially. If `find_anchor_defs` returned `{"mod.func_a": 999, "mod.CONST_B": 0}` with wrong line numbers, this would pass.

### 2.8 `test_sprint_runtime.py` > `TestCheckCI` > `test_failing_run`
```python
self.assertTrue(len(actions) > 0)
```
**Should assert:** The actions list contains a specific action type or message text (e.g., that the failing run ID is mentioned). `len > 0` passes even if the actions are nonsensical.
**Would catch a real bug?** No. An action list containing `[""]` would pass.

### 2.9 `test_pipeline_scripts.py` > `TestTeamVoices` > `test_extract_voices_from_sagas`
```python
rusti_quotes = [v for v in voices["Rusti Ferris"] if "S01" in v["file"]]
self.assertGreaterEqual(len(rusti_quotes), 1)
```
**Should assert:** The exact expected count of quotes (there are a known number of Rusti quotes in S01-core.md). The >= 1 check means the test would pass even if 3 of 4 quotes were silently dropped.
**Would catch a real bug?** Partially. Would catch total breakage but not partial data loss.

### 2.10 `test_fakegithub_fidelity.py` > `TestTimelineJqExpression` > `test_jq_expression_filters_correctly`
```python
self.assertEqual(len(result), 2)
```
**Followed by `numbers = {r["number"] for r in result}; self.assertEqual(numbers, {42, 55})`.** This is good -- length check is backed by content check.

### 2.11 `test_verify_fixes.py` > `TestConfigGeneration` > `test_generated_team_index_has_role_column`
```python
self.assertGreaterEqual(len(rows), 3, "Need at least 3 personas")
```
**Should assert:** Exact count, since the MockProject is created with `extra_personas=True` which produces a known number. Also check that expected persona names appear.
**Would catch a real bug?** Partially. If only 3 of 5 personas were generated, this would still pass.

---

## Category 3: Type checks that should be behavioral checks

### 3.1 `test_bugfix_regression.py` > `TestCheckStatusImportGuard` > `test_import_guard_uses_import_error`
```python
self.assertTrue(hasattr(check_status, 'main'))
self.assertTrue(hasattr(check_status, 'check_ci'))
self.assertTrue(hasattr(check_status, 'check_prs'))
self.assertTrue(callable(check_status.main))
```
**Should assert:** Call `check_status.check_ci()` (with mocked gh_json) and verify it returns a result, rather than just checking attributes exist. The `hasattr` checks only confirm the module loaded; they don't test the import guard's degraded behavior.
**Would catch a real bug?** No. If the import guard silently broke `check_ci` by setting it to a no-op function, these checks would still pass.

### 3.2 `test_fakegithub_fidelity.py` > `TestTimelineJqExpression` > `test_jq_expression_filters_correctly`
```python
self.assertIsInstance(result, list)
```
**Acceptable.** This precedes content assertions. The type check is a guard, not the main assertion.

### 3.3 `test_pipeline_scripts.py` > `TestTeamVoices` > `test_extract_voices_from_epics_returns_empty`
```python
self.assertIsInstance(voices, dict)
self.assertEqual(len(voices), 0, "Expected no voices in Hexwise epics")
```
**Acceptable.** The `assertEqual(len, 0)` is the real assertion. The `assertIsInstance` is a guard.

---

## Category 4: Tests that verify the mock, not the code

### 4.1 `test_sprint_runtime.py` > `TestCreateLabel` > `test_creates_label`
```python
mock_gh.assert_called_once()
call_args = mock_gh.call_args[0][0]
self.assertIn("label", call_args)
self.assertIn("create", call_args)
self.assertIn("test-label", call_args)
```
**Missing:** No assertion that the label was actually created (checking FakeGitHub state or verifying the function's return value). The test only confirms the function called `gh()` with the right arguments. If `create_label` called `gh()` correctly but a bug in `gh()` swallowed the error, this test wouldn't know.
**Would catch a real bug?** Partially. Catches argument construction bugs but not response handling bugs.

### 4.2 `test_sprint_runtime.py` > `TestCreateLabel` > `test_label_error_handled`
```python
mock_gh.assert_called_once()
mock_print.assert_called_once()
warning_msg = mock_print.call_args[0][0]
self.assertIn("existing-label", warning_msg)
self.assertIn("already exists", warning_msg)
```
**Missing:** No assertion on the function's return value. Does `create_label` return True/False? Does it silently succeed? The test verifies the side effects (called gh, printed warning) but not the function's contract.
**Would catch a real bug?** Partially. Catches "forgot to print" but not "returned wrong success status."

### 4.3 `test_sprint_runtime.py` > `TestCreateIssueMissingMilestone` > `test_missing_milestone_still_creates_issue`
```python
mock_gh.return_value = "https://github.com/test/repo/issues/1"
# ...
result = populate_issues.create_issue(story, milestone_numbers={}, milestone_titles={})
self.assertTrue(result)
call_args = mock_gh.call_args[0][0]
self.assertNotIn("--milestone", call_args)
```
**Mostly OK.** Both the return value (`assertTrue(result)`) and the mock args are checked. However, `assertTrue(result)` is weak -- it should check the specific return value (e.g., the URL string).

### 4.4 `test_gh_interactions.py` > `TestGateStories` > `test_all_closed`
```python
ok, detail = gate_stories("Sprint 1")
self.assertTrue(ok)
self.assertIn("closed", detail.lower())
# BH-P11-052: Verify query includes milestone filter
call_args = mock_gh.call_args[0][0]
self.assertIn("--milestone", call_args)
self.assertIn("Sprint 1", call_args)
state_idx = call_args.index("--state")
self.assertEqual(call_args[state_idx + 1], "open")
```
**Good pattern.** Tests both the return value AND the mock arguments. This is the right approach -- the "BH-P11-052" additions verify the query shape, which is important for correctness against the real GitHub API.

### 4.5 `test_gh_interactions.py` > `TestGateCI` > `test_passing`
```python
ok, detail = gate_ci({"project": {}})
self.assertTrue(ok)
call_args = mock_gh.call_args[0][0]
self.assertIn("--branch", call_args)
self.assertIn("main", call_args)
```
**Good.** Return value AND query shape both checked.

### 4.6 `test_gh_interactions.py` > `TestGateCI` > `test_no_runs`
```python
mock_gh.return_value = []
ok, detail = gate_ci({"project": {}})
self.assertFalse(ok)
```
**Missing:** No assertion on `detail`. If the function returned `(False, "")` with an empty detail string, the test would pass but the user would get a useless error message.
**Would catch a real bug?** Partially. Catches the boolean but not the error message quality.

### 4.7 `test_gh_interactions.py` > `TestGatePRs` > `test_no_prs`
```python
ok, _ = gate_prs("Sprint 1")
self.assertTrue(ok)
```
**Missing:** The `detail` return value is explicitly ignored (`_`). Should verify the detail message says something meaningful like "no open PRs."
**Would catch a real bug?** No. If the function returned `(True, "ERROR: something broke")`, this would pass.

### 4.8 `test_gh_interactions.py` > `TestGatePRs` > `test_pr_for_different_milestone`
```python
ok, _ = gate_prs("Sprint 1")
self.assertTrue(ok)
```
**Same issue as 4.7.** Detail is discarded.

---

## Category 5: Regression tests with stale expectations

### 5.1 `test_hexwise_setup.py` > `TestHexwiseSetup` > `test_scanner_finds_personas`
```python
self.assertEqual(len(self.scan.persona_files), 4)  # 3 devs + giles
```
**Risk:** If a persona is added or removed from the hexwise fixture, this magic number becomes stale. The comment "3 devs + giles" helps, but the test doesn't verify which personas were found -- only the count.
**Should also assert:** Specific persona names are present.

### 5.2 `test_hexwise_setup.py` > `TestHexwiseSetup` > `test_scanner_finds_milestones`
```python
self.assertEqual(len(self.scan.backlog_files), 3)  # 3 milestone files
```
**Risk:** Same staleness risk. Adding a 4th milestone file to the fixture breaks this test silently (it would fail, not produce a false positive, so this is actually OK -- the failure alerts you).

### 5.3 `test_hexwise_setup.py` > `TestHexwiseSetup` > `test_config_has_three_milestones`
```python
self.assertEqual(len(md_files), 3)  # 3 milestone files
```
**Risk:** Same as 5.2. Tied to fixture state.

### 5.4 `test_hexwise_setup.py` > `TestHexwisePipeline` > `test_full_setup_pipeline`
```python
self.assertEqual(len(self.fake_gh.milestones), 3, "Should have 3 milestones")
self.assertEqual(len(self.fake_gh.issues), 17, "Should have 17 issues (stories)")
self.assertEqual(len(persona_labels), 4, "Should have 4 persona labels (3 devs + Giles)")
```
**Risk:** These are exact counts derived from the hexwise fixture. If the fixture changes (e.g., a story is added), all three assertions become stale. However, this is intentional -- the test is meant to detect fixture changes.
**Acceptable as designed.** The comment makes the expectation clear.

### 5.5 `test_golden_run.py` > `TestGoldenRun` > `test_golden_full_setup_pipeline`
```python
self.assertGreater(len(self.fake_gh.labels), 10)
self.assertEqual(len(self.fake_gh.milestones), 3)
self.assertEqual(len(self.fake_gh.issues), 17)
```
**Risk:** Same as 5.4. The milestone count (3) and issue count (17) are tied to the hexwise fixture. The label count uses `> 10` which is more resilient but also less precise.

### 5.6 `test_pipeline_scripts.py` > `TestTraceability` > `test_parse_stories_finds_all`
```python
stories = parse_stories(str(HEXWISE / "docs" / "agile" / "epics"))
story_ids = sorted(stories.keys())
self.assertEqual(len(story_ids), 17)
```
**Risk:** Same fixture-count dependency. If a story is added to the hexwise fixture, this breaks.

### 5.7 `test_pipeline_scripts.py` > `TestManageEpics` > `test_parse_epic_metadata`
```python
self.assertEqual(epic["stories_count"], 4)
self.assertEqual(epic["total_sp"], 16)
```
**Risk:** These are magic numbers tied to the content of `E-0101-parsing.md`. If the fixture file's SP values change, these become stale.
**Mitigated by:** Being fixture-specific tests that are expected to break when the fixture changes.

### 5.8 `test_pipeline_scripts.py` > `TestManageSagas` > `test_parse_saga_metadata`
```python
self.assertEqual(saga["stories_count"], 8)
self.assertEqual(saga["epics_count"], 3)
self.assertEqual(saga["total_sp"], 34)
```
**Risk:** Same as 5.7. Tied to `S01-core.md` fixture content.

### 5.9 `test_verify_fixes.py` > `TestKanbanStatesConstant` > `test_kanban_states_count`
```python
self.assertEqual(len(KANBAN_STATES), 6, "Expected 6 kanban states, got ...")
```
**Risk:** If a 7th kanban state is added to the protocol, this test becomes stale. However, this is intentional -- the test exists specifically to catch unintentional state additions.
**Acceptable as designed.**

### 5.10 `test_sprint_runtime.py` > `TestCheckCI` > `test_all_passing`
```python
self.assertIn("1 passing", report[0])
```
**Risk:** The string "1 passing" is a magic value. If the format changes to "1 run passing" or "1 succeeded", the test breaks. This is desirable behavior (catches format regressions).
**Acceptable as designed.**

---

## Summary

| Category | Count | Severity |
|----------|-------|----------|
| 1. Existence checks that should be value checks | 4 | HIGH -- tests would pass with completely wrong values |
| 2. Length checks that should be content checks | 5 | MEDIUM -- tests catch total failure but miss partial corruption |
| 3. Type checks that should be behavioral checks | 1 | MEDIUM -- structural check without behavioral verification |
| 4. Tests that verify mock, not code | 5 | MEDIUM -- catches argument bugs but misses result-processing bugs |
| 5. Regression tests with stale expectations | 6 | LOW -- intentional fixture coupling, well-documented |

**Total weak assertions: 21**

### Priority fixes (assertions that definitely cannot catch real bugs):

1. **test_hexwise_setup.py lines 103-104:** `assertIsNotNone` on scanner results should assert actual paths.
2. **test_hexwise_setup.py lines 153-157, 163-167, 172-174:** All `assertIsNotNone` on optional paths should verify path correctness.
3. **test_bugfix_regression.py lines 74-79:** `hasattr`/`callable` checks on check_status should test degraded behavior.
4. **test_gh_interactions.py line 355:** `gate_prs` test discards detail string; should verify it.
5. **test_gh_interactions.py line 347:** `gate_ci` no-runs test should verify error detail.
6. **test_sprint_runtime.py line 72:** `assertTrue(len(actions) > 0)` should check action content.

### Tests that are better than they appear:

- `test_hexwise_setup.py::test_full_setup_pipeline` -- looks like count-only but also verifies all 17 story IDs by name.
- `test_fakegithub_fidelity.py::test_jq_expression_filters_correctly` -- length check is followed by content verification.
- `test_gh_interactions.py::TestGateStories` -- good pattern of checking both return value AND query arguments.
- Property-based tests in `test_property_parsing.py` -- strong assertions on invariants, no weak checks found.
