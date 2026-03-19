# Phase 2 — Test Quality Audit (Pass 23)

**Auditor:** Claude Opus 4.6 (1M context)
**Scope:** All 15 test files, 854 passing tests
**Date:** 2026-03-19

---

## Summary Statistics

| File | Tests | Avg Assertions/Test | Mock Ratio | Tier 1 Issues | Tier 2 Issues | Tier 3 Issues |
|------|-------|-------------------|------------|---------------|---------------|---------------|
| `test_kanban.py` | 42 | 2.5 | Low | 0 | 1 | 2 |
| `test_lifecycle.py` | 14 | 3.5 | Low | 0 | 1 | 1 |
| `test_verify_fixes.py` | 26 | 2.0 | Low | 0 | 0 | 3 |
| `test_property_parsing.py` | 25 | 2.0 | None | 0 | 0 | 1 |
| `test_sprint_runtime.py` | ~95 | 2.5 | Medium | 1 | 3 | 3 |
| `test_release_gate.py` | 28 | 2.5 | High | 1 | 1 | 1 |
| `test_gh_interactions.py` | 30 | 2.0 | Medium | 0 | 1 | 1 |
| `test_bugfix_regression.py` | ~65 | 2.0 | Medium | 1 | 2 | 1 |
| `test_sprint_analytics.py` | 14 | 3.0 | Low | 0 | 0 | 1 |
| `test_pipeline_scripts.py` | ~50 | 2.5 | Low | 0 | 1 | 2 |
| `test_sprint_teardown.py` | 25 | 2.0 | Low | 0 | 0 | 1 |
| `test_hexwise_setup.py` | 20 | 2.0 | Low | 0 | 1 | 1 |
| `test_golden_run.py` | 5 | 2.0 | Low | 0 | 1 | 0 |
| `test_sync_backlog.py` | 14 | 2.5 | Low | 0 | 0 | 1 |
| `test_validate_anchors.py` | 17 | 2.0 | None | 0 | 0 | 1 |
| `test_fakegithub_fidelity.py` | 10 | 2.5 | None | 0 | 0 | 1 |

**Totals:** 3 Tier 1, 12 Tier 2, 21 Tier 3

---

## Tier 1 Findings (Actively Harmful)

### BH23-100: Green Bar Addict — `test_check_status_import_guard` asserts module attributes exist
**Severity:** MEDIUM
**Category:** test/bogus
**Location:** `tests/test_bugfix_regression.py:65-79`
**Problem:** This test asserts that `check_status` has `main`, `check_ci`, and `check_prs` attributes and that `main` is callable. These assertions would pass for any importable module with those names, regardless of whether the import guard for `sync_backlog` works correctly. The test claims to verify graceful degradation when `sync_backlog` is unavailable but never actually makes `sync_backlog` unavailable.
**Evidence:**
```python
def test_import_guard_uses_import_error(self):
    self.assertTrue(hasattr(check_status, 'main'))
    self.assertTrue(hasattr(check_status, 'check_ci'))
    self.assertTrue(hasattr(check_status, 'check_prs'))
    self.assertTrue(callable(check_status.main))
```
**Acceptance Criteria:**
- [ ] Test temporarily patches `sys.modules` to make `sync_backlog` raise `ImportError` on import, then verifies `check_status` functions still work
- [ ] Test verifies the specific degradation behavior (e.g., backlog sync step is skipped when unavailable)

### BH23-101: The Mockingbird — `do_release` happy path mocks 5 layers deep
**Severity:** HIGH
**Category:** test/mock-abuse
**Location:** `tests/test_release_gate.py:641-714`
**Problem:** `test_happy_path` patches `calculate_version`, `write_version_to_toml`, `subprocess.run`, `find_milestone_number`, AND `gh` simultaneously. With every input and output controlled by mocks, the test verifies that `do_release` calls its dependencies in the right order — but it cannot detect if any dependency's API contract changes. The test is effectively testing the call sequence, not the behavior. A refactor that changes the subprocess argument format would pass this test while breaking production.
**Evidence:**
```python
@patch("release_gate.gh")
@patch("release_gate.find_milestone_number")
@patch("release_gate.subprocess.run")
@patch("release_gate.write_version_to_toml")
@patch("release_gate.calculate_version")
def test_happy_path(self, mock_calc, mock_write_toml, mock_run, mock_ms, mock_gh):
```
**Acceptance Criteria:**
- [ ] At least one `do_release` test exercises the real `calculate_version` + `write_version_to_toml` path with only `subprocess.run` and `gh` mocked (via FakeGitHub)
- [ ] The test file's docstring already acknowledges this trade-off (BH-P11-060) — but no integration test exists for `do_release` through FakeGitHub with a real git repo

### BH23-102: Inspector Clouseau — `TestCheckCI.test_all_passing` checks mock call_args format
**Severity:** LOW
**Category:** test/fragile
**Location:** `tests/test_sprint_runtime.py:47-59`
**Problem:** The test verifies that `mock_gh.call_args[0][0]` contains `"run"` and `"--json"`. This tests implementation details (the exact argument list structure) rather than behavior (that passing CI runs produce a "1 passing" report). If the production code switches from positional to keyword args or changes the argument order, this test breaks even though behavior is correct. Several tests across `test_sprint_runtime.py` exhibit this pattern.
**Evidence:**
```python
call_args = mock_gh.call_args[0][0]
self.assertIn("run", call_args)
self.assertIn("--json", call_args)
```
**Acceptance Criteria:**
- [ ] Call-args assertions should be separated into dedicated contract tests (e.g., "check_ci queries the run endpoint with JSON fields") rather than bolted onto behavioral tests
- [ ] Alternatively, these assertions should use FakeGitHub instead of raw mocks, so the contract is verified by the fake's dispatch table

---

## Tier 2 Findings (False Security)

### BH23-103: Happy Path Tourist — `do_transition` only tests todo->design, no multi-hop or edge states
**Severity:** MEDIUM
**Category:** test/missing
**Location:** `tests/test_kanban.py:346-418`
**Problem:** `TestTransitionCommand` has 3 tests covering todo->design, github failure rollback, and integration->done. But the kanban state machine has 6 legal transitions and the production code has distinct behavior for different transitions (e.g., the `done` transition also closes the issue). The review->dev, review->integration, and design->dev paths are untested through `do_transition`.
**Evidence:** Only 3 `do_transition` tests exist. The `TRANSITIONS` dict has 6 legal transitions, each with different precondition logic.
**Acceptance Criteria:**
- [ ] `do_transition` is tested for at least design->dev and review->integration transitions
- [ ] At least one test covers the review->dev rejection path (re-review cycle)

### BH23-104: Happy Path Tourist — `do_sync` missing edge cases for label format inconsistency
**Severity:** MEDIUM
**Category:** test/missing
**Location:** `tests/test_kanban.py:509-651`
**Problem:** `TestSyncCommand` tests with issues where labels are plain strings (e.g., `"kanban:design"`), but production GitHub issues return labels as `[{"name": "kanban:design"}]`. The `_issue` helper on line 517-524 constructs labels as plain strings, which may not match how `do_sync` actually receives data from `gh_json`. The test for closed issues (line 589) uses `{"name": "kanban:dev"}` format. This inconsistency means some sync tests may be exercising a code path that never occurs in production.
**Evidence:**
```python
def _issue(self, number, title, state="open", labels=None):
    if labels is None:
        labels = [f"kanban:{state}"] if state != "open" else ["kanban:todo"]
    # labels are strings like "kanban:todo", not {"name": "kanban:todo"} dicts
```
**Acceptance Criteria:**
- [ ] The `_issue` helper consistently uses the same label format that `do_sync` receives from GitHub (dict format `{"name": "..."}`)
- [ ] Verify `do_sync` handles both label formats or document which one is expected

### BH23-105: Rubber Stamp — `test_generated_toml_has_required_keys` checks key presence not values
**Severity:** LOW
**Category:** test/shallow
**Location:** `tests/test_verify_fixes.py:63-83`
**Problem:** The test verifies that TOML sections and keys exist but does not verify their values are sensible. For example, `check_commands` could be an empty list, `build_command` could be empty string, `language` could be wrong — the test would still pass. The corresponding `test_generated_config_passes_validation` partially covers this, but only for structural validity, not semantic correctness.
**Evidence:**
```python
self.assertIn("check_commands", config["ci"])
self.assertIn("build_command", config["ci"])
```
**Acceptance Criteria:**
- [ ] Assert `config["ci"]["check_commands"]` is a non-empty list
- [ ] Assert `config["ci"]["build_command"]` is a non-empty string
- [ ] Assert `config["project"]["language"]` matches the MockProject fixture language

### BH23-106: Time Bomb — `test_recent_iso_returns_small_hours` uses wall clock time
**Severity:** LOW
**Category:** test/fragile
**Location:** `tests/test_sprint_runtime.py:1629-1631`
**Problem:** The test constructs a timestamp 30 minutes in the past using `datetime.now()` and asserts `_hours()` returns approximately 0.5. If the test runs slowly (e.g., CI under heavy load, debugger attached), the delta grows. The `delta=0.1` tolerance helps but doesn't eliminate the risk. Multiple tests in this class and `TestAge` use the same pattern.
**Evidence:**
```python
def test_recent_iso_returns_small_hours(self):
    recent = (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat()
    h = check_status._hours(recent)
    self.assertAlmostEqual(h, 0.5, delta=0.1)
```
**Acceptance Criteria:**
- [ ] Inject a fixed `now` parameter into `_hours()` and `_age()` or mock `datetime.now()` to make tests deterministic

### BH23-107: Happy Path Tourist — `gate_tests` and `gate_build` never test timeout with FakeGitHub
**Severity:** LOW
**Category:** test/missing
**Location:** `tests/test_release_gate.py:322-412`
**Problem:** `gate_tests` and `gate_build` are tested with direct `subprocess.run` mocks that return predetermined outcomes. The timeout tests (P13-014) mock `subprocess.run` to raise `TimeoutExpired`, but the `validate_gates` integration test in `TestValidateGates` uses a combined mock that always succeeds for shell commands. No test exercises the interaction between `validate_gates` short-circuit logic and a timeout failure in `gate_tests` or `gate_build`.
**Evidence:** `TestValidateGates.test_all_pass_with_real_commands` always returns `returncode=0` for shell commands. `TestGateTests.test_timeout_returns_failure` mocks at the unit level, never through `validate_gates`.
**Acceptance Criteria:**
- [ ] One `validate_gates` test exercises a timeout in `gate_tests` to verify the gate short-circuits correctly

### BH23-108: Happy Path Tourist — `test_lifecycle.py` monitoring pipeline hardcodes SP values
**Severity:** LOW
**Category:** test/fragile
**Location:** `tests/test_lifecycle.py:326-435`
**Problem:** `test_14_monitoring_pipeline` manually constructs `FakeGitHub.issues` with hardcoded SP labels (`sp:3`, `sp:5`, `sp:3`, `sp:2`), then asserts `"Completed: 8 SP"` and `"Remaining: 5 SP"`. The assertion values are manually computed from the inputs rather than derived. If `build_rows` or `write_burndown` SP extraction changes, the hardcoded expected values would mask the regression — the test would need to be updated to catch it, defeating its purpose as a regression test.
**Evidence:**
```python
self.assertIn("Completed: 8 SP", bd_text)
self.assertIn("Remaining: 5 SP", bd_text)
```
**Acceptance Criteria:**
- [ ] Either compute expected SP sums from the test data programmatically, or add a comment documenting the calculation `(3+5=8 done, 3+2=5 remaining)`

### BH23-109: Rubber Stamp — `TestConfigGeneration.test_generated_team_index_no_confidence_column` is obsolete
**Severity:** LOW
**Category:** test/bogus
**Location:** `tests/test_verify_fixes.py:108-114`
**Problem:** This test asserts that a "Confidence" column does not appear in generated team INDEX.md. This was a valid regression test when the Confidence column was recently removed, but it now tests for the absence of something that was never in the current codebase. If the column name were changed to anything else, this test would still pass. It provides no ongoing value.
**Evidence:**
```python
def test_generated_team_index_no_confidence_column(self):
    text = index_path.read_text()
    self.assertNotIn("Confidence", text)
```
**Acceptance Criteria:**
- [ ] Remove or replace with a positive assertion about expected column headers (Name, Role, File)

### BH23-110: Happy Path Tourist — `check_prs` not tested with mixed review states
**Severity:** LOW
**Category:** test/missing
**Location:** `tests/test_sprint_runtime.py:77-113`
**Problem:** `TestCheckPRs` has 3 tests: no PRs, one approved PR, and one needs-review PR. But `check_prs` aggregates multiple PRs and produces a summary with counts. The interaction between approved, needs-review, and CI-failing PRs in a single response is untested. The production code has logic to classify each PR into buckets and generate action items — this multi-PR path is never exercised.
**Evidence:** All tests pass a single-element list to `mock_gh.return_value`.
**Acceptance Criteria:**
- [ ] Add a test with 3+ PRs in different states (approved + needs-review + CI-failing) and verify the summary counts

### BH23-111: Rubber Stamp — `test_state_dump` checks structure not content
**Severity:** LOW
**Category:** test/shallow
**Location:** `tests/test_hexwise_setup.py:423-436`
**Problem:** `test_state_dump` verifies that `dump_state()` returns a dict with `"labels"` and `"milestones"` keys and that counts exceed thresholds. It does not verify that specific label names, milestone titles, or any actual content is correct. The golden-run tests cover content comparison, but this test provides false security by counting without inspecting.
**Evidence:**
```python
self.assertGreaterEqual(len(state["labels"]), 13)
self.assertEqual(len(state["milestones"]), 3)
```
**Acceptance Criteria:**
- [ ] Either delete the test (golden-run covers this) or add at least one content assertion (e.g., specific label name or milestone title)

### BH23-112: Happy Path Tourist — `TestGoldenRun` silently skips in non-CI without recordings
**Severity:** MEDIUM
**Category:** test/fragile
**Location:** `tests/test_golden_run.py:93-119`
**Problem:** When golden recordings are absent and `CI` env var is not set, `_check_or_record` calls `self.skipTest()`, making the entire pipeline test a no-op. This means the golden run test provides zero coverage in local development environments that haven't run `GOLDEN_RECORD=1`. The test file's primary value proposition — catching exact output regressions — is silently disabled.
**Evidence:**
```python
else:
    if os.environ.get("CI"):
        self.fail(...)
    else:
        self.skipTest(...)
```
**Acceptance Criteria:**
- [ ] Golden recordings should be committed to the repo so the test always runs
- [ ] Or, if recordings are intentionally not committed, the Makefile `test` target should run `GOLDEN_RECORD=1` first if recordings are absent

---

## Tier 3 Findings (Missed Opportunities)

### BH23-113: Shallow End — `do_assign` body-update path not tested when gh_json returns unexpected format
**Severity:** LOW
**Category:** test/shallow
**Location:** `tests/test_kanban.py:448-506`
**Problem:** `test_assign_implementer` mocks `gh_json` to return a dict with `"body"` containing the exact expected header format (`> **[Unassigned]**`). The production code's regex for body parsing likely has edge cases (no header, malformed header, already-assigned header). None of these are tested.
**Evidence:** All `gh_json` side_effects return the exact happy-path body format.
**Acceptance Criteria:**
- [ ] Test `do_assign` when the issue body has no assignee header (fresh issue)
- [ ] Test `do_assign` when the issue body already has a different implementer assigned

### BH23-114: Shallow End — Lock contention in `TestFileLocking` never tested
**Severity:** LOW
**Category:** test/shallow
**Location:** `tests/test_kanban.py:238-268`
**Problem:** `TestFileLocking` tests acquire-then-release-then-acquire-again patterns, which verify no deadlock on sequential access. But the `lock_story` and `lock_sprint` functions use `fcntl.flock` for advisory locking, which is designed for concurrent access. No test verifies the lock actually blocks a second process/thread from writing simultaneously.
**Evidence:**
```python
with lock_story(p):
    pass
with lock_story(p):
    pass  # second acquire must succeed
```
**Acceptance Criteria:**
- [ ] Add a test that starts a background thread holding the lock and verifies a second thread blocks or raises within a timeout

### BH23-115: Shallow End — `test_property_parsing.py` `_yaml_safe` never tests numeric-looking strings
**Severity:** LOW
**Category:** test/missing
**Location:** `tests/test_property_parsing.py:173-264`
**Problem:** The `_yaml_safe` property tests generate random strings but the `dangerous_chars_get_quoted` test does not check for purely numeric strings like `"42"` or `"3.14"` which YAML parsers interpret as numbers. The production code (BH22-104) added numeric quoting, but the property test does not include this invariant.
**Evidence:** The `test_dangerous_chars_get_quoted` method checks for YAML bool keywords and special characters, but not for strings that look like integers or floats.
**Acceptance Criteria:**
- [ ] Add a property: if `value` matches `r"^\d+$"` or `r"^\d+\.\d+$"`, assert the result is quoted

### BH23-116: Shallow End — `TestSyncOne` never writes the TF to disk and reads back
**Severity:** LOW
**Category:** test/shallow
**Location:** `tests/test_sprint_runtime.py:1248-1309`
**Problem:** `TestSyncOne` creates TF objects with `path=Path("/tmp/test.md")` but never calls `write_tf` or reads back from disk. It only inspects the in-memory TF object. This means the test does not verify that sync_one's changes survive a write/read round-trip through the YAML frontmatter serializer. Bugs in `_yaml_safe` quoting of synced values would be invisible.
**Evidence:**
```python
tf = sync_tracking.TF(path=Path("/tmp/test.md"), ...)
changes = sync_tracking.sync_one(tf, issue, None, 1)
self.assertEqual(tf.status, "done")  # only in-memory check
```
**Acceptance Criteria:**
- [ ] At least one `sync_one` test writes the TF to a temp file after sync and reads it back to verify round-trip fidelity

### BH23-117: Shallow End — `test_pipeline_scripts.py` traceability tests only check report structure
**Severity:** LOW
**Category:** test/shallow
**Location:** `tests/test_pipeline_scripts.py` (traceability section)
**Problem:** The traceability tests verify that `build_traceability` returns a dict with expected keys and that `format_report` produces markdown with headers. They do not verify that actual gaps are detected — e.g., a story with no test case link should appear in the "Gaps" section. The test always runs against the hexwise fixture which may have complete coverage, making gap detection untestable.
**Acceptance Criteria:**
- [ ] Add a test with a synthetic story that has no test case mapping and verify the gap report includes it

### BH23-118: Shallow End — `test_pipeline_scripts.py` `manage_epics` remove_story not tested for missing story
**Severity:** LOW
**Category:** test/missing
**Location:** `tests/test_pipeline_scripts.py` (manage_epics section)
**Problem:** The `manage_epics` tests cover `add_story`, `remove_story`, and `reorder_stories` for the happy path. But `remove_story` when the story ID doesn't exist in the epic is not tested. The production code should handle this gracefully (return 0 or raise), and the test suite should document which.
**Acceptance Criteria:**
- [ ] Test `remove_story` with a non-existent story ID and assert the expected behavior (no crash, return value)

### BH23-119: Rubber Stamp — Multiple tests assert `assertIsNotNone` without inspecting content
**Severity:** LOW
**Category:** test/shallow
**Location:** Multiple files
**Problem:** Several tests across the suite use `assertIsNotNone(result)` followed by a single field check, without verifying the full shape of the returned object. This is a systemic pattern where tests verify "something was returned" rather than "the right thing was returned." Examples include `find_story` tests that check `result.story` but not `result.path` or `result.status`, and `get_linked_pr` tests that check `result["number"]` but not `result["merged"]`.
**Evidence:** In `test_kanban.py:286-288`:
```python
result = find_story("US-0042", sprints_dir, sprint=1)
self.assertIsNotNone(result)
self.assertEqual(result.story, "US-0042")
# result.path, result.status, result.sprint NOT checked
```
**Acceptance Criteria:**
- [ ] Critical lookup functions (`find_story`, `get_linked_pr`) should verify at least 3 fields of the returned object in their primary test case

### BH23-120: Shallow End — `test_validate_anchors.py` never tests fix_missing_anchors with CONSTANT definition
**Severity:** LOW
**Category:** test/missing
**Location:** `tests/test_validate_anchors.py:206-279`
**Problem:** `TestFixMode` tests autofix for Python function anchors (`def my_func`) and markdown heading anchors (`## Kickoff`). But the production `fix_missing_anchors` also handles Python constants (`CONST = 42` is in the test file's setUp). No test verifies that a reference like `§mymod.CONST` would be auto-fixed by inserting `# §mymod.CONST` above `CONST = 42`.
**Acceptance Criteria:**
- [ ] Add a test that references `§mymod.CONST` and verifies the anchor is inserted above the constant assignment

### BH23-121: Shallow End — `test_sync_backlog.py` `do_sync` never tests with pre-existing GitHub issues
**Severity:** LOW
**Category:** test/missing
**Location:** `tests/test_sync_backlog.py:152-202`
**Problem:** `TestDoSync.test_do_sync_idempotent` verifies that running `do_sync` twice produces the same issue count, but it starts from an empty FakeGitHub. It never tests `do_sync` against a FakeGitHub that already has some issues from a previous manual creation — the scenario where backlog files add a new story but existing stories already have GitHub issues.
**Acceptance Criteria:**
- [ ] Test `do_sync` with FakeGitHub pre-populated with 1 existing issue, adding a new story to the milestone file, and verify only 1 new issue is created

### BH23-122: Shallow End — `test_fakegithub_fidelity.py` covers only timeline jq and search predicates
**Severity:** MEDIUM
**Category:** test/missing
**Location:** `tests/test_fakegithub_fidelity.py`
**Problem:** The fidelity test file covers exactly 2 things: the timeline jq expression and search predicate warnings. FakeGitHub is 992 lines with dispatch for issue, PR, label, milestone, run, release, and auth handlers. Major fidelity gaps include: (1) PR merge behavior, (2) issue label manipulation (add/remove), (3) milestone assignment counting edge cases, (4) release creation response format. Any of these could diverge from real `gh` behavior without detection.
**Evidence:** Only `TestTimelineJqExpression`, `TestSearchPredicateWarning`, and `TestMilestoneCounters` exist. The milestone counter tests are good but only cover the basic lifecycle.
**Acceptance Criteria:**
- [ ] Add fidelity tests for at least: PR label filtering, issue edit (add-label, remove-label), and release create response format
- [ ] Compare FakeGitHub output format for `issue list --json` against a recorded real `gh` response

### BH23-123: Happy Path Tourist — `test_sprint_analytics.py` `compute_workload` never tests mixed milestones
**Severity:** LOW
**Category:** test/missing
**Location:** `tests/test_sprint_analytics.py:238-269`
**Problem:** `TestComputeWorkload.test_counts_per_persona` puts all issues in "Sprint 1" milestone. But `compute_workload` queries all issues for a milestone title, and if FakeGitHub's issue filtering has a bug that returns all issues regardless of milestone, this test would still pass. The Sprint Analytics test for `compute_review_rounds` (BH-002) correctly tests cross-milestone filtering, but `compute_workload` does not.
**Acceptance Criteria:**
- [ ] Add a test with issues in 2 different milestones and verify only the target milestone's issues are counted

### BH23-124: Permissive Validator — `test_13_full_pipeline` uses `assertGreaterEqual(labels, 15)`
**Severity:** LOW
**Category:** test/shallow
**Location:** `tests/test_lifecycle.py:316`
**Problem:** The full pipeline test asserts `>= 15` labels, `== 1` milestone, `== 2` issues. The label count assertion is intentionally loose (documented as "minimal and we only care that the pipeline completes"), but this means 5 labels could be missing and the test would still pass. Since the hexwise pipeline test has exact counts, this is acceptable as a smoke test — but the loose label bound should be tighter or documented with the expected minimum.
**Evidence:**
```python
self.assertGreaterEqual(len(self.fake_gh.labels), 15,
                        "Labels: static + persona + sprint + saga + kanban")
```
**Acceptance Criteria:**
- [ ] Either tighten the bound to the actual expected count for a 2-persona project, or add a comment documenting why 15 is the correct minimum

### BH23-125: Shallow End — `test_gh_interactions.py` `check_atomicity` never tests with test files alongside source
**Severity:** LOW
**Category:** test/missing
**Location:** `tests/test_gh_interactions.py:84-128`
**Problem:** `TestCheckAtomicity` tests single-directory, three-directory, and root-file scenarios. But the common pattern of `src/` + `tests/` (2 directories) is not tested. The production code has a threshold of 3 directories before rejecting, so 2 directories should pass — but this boundary is only implicitly tested via the 3-directory test, not explicitly.
**Acceptance Criteria:**
- [ ] Add an explicit 2-directory test (`src/foo.py` + `tests/test_foo.py`) to document the boundary behavior

### BH23-126: Shallow End — No test verifies `do_status` output contains WIP limits or assignee info
**Severity:** LOW
**Category:** test/shallow
**Location:** `tests/test_kanban.py:733-763`
**Problem:** `TestStatusCommand.test_status_shows_board` verifies that story IDs and state headers appear in the output. It does not verify that implementer/reviewer names appear next to stories, or that WIP limit warnings appear when a column is over capacity. The kanban protocol defines WIP limits, but `do_status` rendering of those limits is never tested.
**Acceptance Criteria:**
- [ ] Assert that the output contains implementer names ("rae", "chen") next to the correct stories
- [ ] Add a test with 4+ stories in DEV to verify WIP limit warning appears

### BH23-127: Shallow End — `test_release_gate.py` `do_release` rollback path never verified end-to-end
**Severity:** MEDIUM
**Category:** test/missing
**Location:** `tests/test_release_gate.py:780-800`
**Problem:** `test_commit_failure_rollback_unstages_and_restores` mocks `subprocess.run` and verifies that git reset/checkout commands are issued. But since subprocess is fully mocked, it cannot verify that the rollback actually restores the working directory. The test proves the commands are called but not that they work. A real integration test with a temp git repo would catch issues like wrong reset mode or missing file path arguments.
**Acceptance Criteria:**
- [ ] Add one integration test for `do_release` rollback that uses a real temp git repo and verifies the project.toml is restored to its pre-release content

### BH23-128: Shallow End — `test_hexwise_setup.py` `setUpClass` shares mutable state across tests
**Severity:** LOW
**Category:** test/fragile
**Location:** `tests/test_hexwise_setup.py:37-83`
**Problem:** `TestHexwiseSetup.setUpClass` runs the scanner and generator once, storing results as class attributes. All tests share the same `self.config_dir` and `self.scan`. This is efficient but creates a Schrodinger Test risk: if one test modifies files in `config_dir`, subsequent tests could fail or pass incorrectly. Currently no test modifies files, but the shared-mutable-state pattern is fragile for future additions.
**Acceptance Criteria:**
- [ ] Document the shared-state contract with a comment in `setUpClass` (e.g., "Tests MUST NOT modify files in config_dir")

---

## Cross-Cutting Observations

### Systemic Pattern: Mock-at-module-boundary vs. mock-at-function-level inconsistency

Across the test suite, two incompatible mocking strategies are used:
1. `make_patched_subprocess(FakeGitHub)` — patches `subprocess.run` globally, intercepts `gh` calls, passes others through. Used by integration tests.
2. `@patch("module.gh_json")` / `@patch("module.gh")` — patches individual function imports. Used by unit tests.

When a module calls `gh()` which calls `subprocess.run`, these two strategies produce different coverage. Strategy 1 exercises the real `gh()` wrapper (argument construction, error handling, retry logic). Strategy 2 skips it entirely. About 60% of the `check_status` tests use strategy 2, meaning the `gh()` wrapper's error handling is undertested for those code paths.

### Systemic Pattern: Assertion density is adequate but depth is shallow

Average assertions per test is 2.0-3.5, which is reasonable. However, many assertions check structure (`assertIn`, `assertIsNotNone`, `assertIsInstance`) rather than exact values. This is appropriate for format-sensitive output (markdown reports) but creates false security for data processing functions where exact values matter (SP calculation, version bumping, milestone matching).

### Systemic Pattern: Property tests cover crash-resistance but not correctness invariants

`test_property_parsing.py` is well-written and covers 5 critical functions. However, most properties test "never crashes" and "returns correct type" rather than semantic invariants. For example, `extract_story_id` tests could add: "if input contains `PREFIX-NNN:`, the output always starts with `PREFIX-NNN`." The `_yaml_safe` tests are the exception — they do test a meaningful roundtrip invariant.
