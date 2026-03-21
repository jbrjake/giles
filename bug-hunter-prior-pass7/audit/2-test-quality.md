# Test Quality Audit — Phase 2

**Date:** 2026-03-15
**Auditor:** Claude Opus 4.6 (adversarial review)
**Scope:** All files in `tests/`

---

## Summary Statistics

### Test Method Counts Per File

| File | Test Classes | Test Methods | Notes |
|------|-------------|--------------|-------|
| `test_sync_backlog.py` | 5 | 14 | Solid coverage of debounce/throttle |
| `test_sprint_analytics.py` | 5 | 10 | Good per-function isolation |
| `test_golden_run.py` | 1 | 1 | Single mega-test with 5 phases |
| `test_hexwise_setup.py` | 2 | 18 | Rich fixture, good assertions |
| `test_sprint_teardown.py` | 8 | 20 | Best-tested module in the suite |
| `test_verify_fixes.py` | 6 | 19 | Regression tests for specific bugs |
| `test_release_gate.py` | 8 | 19 | Strong failure/rollback coverage |
| `test_gh_interactions.py` | 26 | ~95 | Largest file, comprehensive |
| `test_lifecycle.py` | 1 | 14 | Integration pipeline |
| `test_pipeline_scripts.py` | 12 | ~60 | Covers 5 scripts, good edge cases |
| `test_validate_anchors.py` | 5 | 16 | Clean, well-scoped |
| `fake_github.py` | — | — | Test infrastructure only |
| `golden_recorder.py` | — | — | Test infrastructure only |
| `golden_replay.py` | — | — | Test infrastructure only |

**Total test methods:** ~286
**Total test classes:** ~79

### Tautological Tests: 0

No tests assert `x == x` or similar trivially true conditions. This is a clean bill.

### Production Functions With Zero Test Coverage

See section 6 below for the full list (34 functions identified).

---

## Findings

### 1. Fragile State: `os.chdir` Used Extensively

**Anti-pattern type:** Fragile state (10)
**Severity:** MEDIUM

Multiple test classes use `os.chdir()` to change the working directory, which is global process state shared across all tests. If a test fails mid-execution (exception before `tearDown`), the cwd may not be restored, causing cascading failures in subsequent tests.

**Affected locations:**
- `test_sync_backlog.py` lines 254-262, 270-279, 287-296 — `TestMain` class uses `os.chdir(td)` in each test method
- `test_golden_run.py` lines 78-79 / 82 — `setUp`/`tearDown` chdir pair
- `test_hexwise_setup.py` lines 66-69 / 81-83 — `setUpClass`/`tearDownClass` chdir pair
- `test_lifecycle.py` lines 158-159 / 162 — `setUp`/`tearDown` chdir pair
- `test_release_gate.py` lines 395-396 / 413-414 — `setUp`/`tearDown` chdir pair
- `test_release_gate.py` lines 894-895 — `setUp` chdir pair
- `test_verify_fixes.py` lines 300-301 / 304-306 — `setUp`/`tearDown` chdir pair
- `test_pipeline_scripts.py` lines 1113-1114 — within `setUp`

**Why it matters:** `os.chdir()` is a process-global mutation. If any test raises an unhandled exception between `os.chdir(new)` and the cleanup `os.chdir(saved)`, every subsequent test runs in the wrong directory. Python's `unittest` does call `tearDown` even on failure, but `setUpClass`/`tearDownClass` chdir patterns (as in `test_hexwise_setup.py`) can silently corrupt global state if `setUpClass` fails partway through.

Some files mitigate this with `self.addCleanup(os.chdir, saved)` (e.g., `test_lifecycle.py` line 159), which is safer than relying on `tearDown`. But other files (e.g., `test_sync_backlog.py`) use manual try/finally blocks that are correct but more error-prone.

**What a real fix would look like:** Use `self.addCleanup(os.chdir, saved)` consistently across all test classes, or better yet, refactor production code to accept explicit paths rather than relying on cwd.

---

### 2. Tests That Test the Mock: `test_state_dump` in test_hexwise_setup.py

**Anti-pattern type:** Tests that test the mock (2)
**Severity:** LOW

**File:** `test_hexwise_setup.py`, line 429-442

```python
def test_state_dump(self):
    """FakeGitHub.dump_state() captures full state for golden snapshots."""
    config = self._generate_config()
    with patch("subprocess.run", make_patched_subprocess(self.fake_gh)):
        bootstrap_github.create_static_labels()
        bootstrap_github.create_persona_labels(config)
        bootstrap_github.create_milestones_on_github(config)
    state = self.fake_gh.dump_state()
    self.assertIn("labels", state)
    self.assertIn("milestones", state)
    self.assertGreater(len(state["labels"]), 0)
    self.assertGreater(len(state["milestones"]), 0)
```

This test verifies that `FakeGitHub.dump_state()` returns a dict with keys. It is testing the mock's serialization method, not any production behavior. If `dump_state()` broke, the golden test would fail anyway.

**Why it matters:** This test cannot detect a production regression. It only validates test infrastructure.

**What a real test would look like:** Remove this test. The golden run test already exercises `dump_state()` as a prerequisite for snapshot comparison.

---

### 3. Weak Assertions: `assertGreater(len(...), 0)` Instead of Exact Counts

**Anti-pattern type:** Weak assertions (4)
**Severity:** MEDIUM

Several tests use `assertGreater(len(x), 0)` or `assertGreaterEqual(len(x), N)` when the exact expected count is knowable and deterministic.

**Affected locations:**

- `test_lifecycle.py` line 230: `self.assertGreater(len(self.fake_gh.milestones), 0)` — the MockProject has exactly 1 milestone file with 1 sprint section, so this should assert `== 1`.
- `test_lifecycle.py` line 245: `self.assertGreater(len(stories), 0)` — the MockProject has exactly 2 stories.
- `test_lifecycle.py` line 266: `self.assertGreater(len(self.fake_gh.issues), 0)` — should assert `== 2`.
- `test_lifecycle.py` lines 450-454: `assertGreaterEqual(len(labels), 15)`, `assertGreaterEqual(len(milestones), 1)`, `assertGreaterEqual(len(issues), 1)` — the docstring says "assertions are intentionally loose" but the comment also says the fixture is deterministic.
- `test_golden_run.py` line 150: `self.assertGreater(len(self.fake_gh.labels), 10)` — exact count is known from the fixture.
- `test_sync_backlog.py` lines 189-190: `assertGreater(len(fake_gh.milestones), 0)`, `assertGreater(len(fake_gh.issues), 0)` — the fixture has exactly 1 milestone and 2 stories.
- `test_hexwise_setup.py` line 93: `self.assertGreaterEqual(len(self.scan.persona_files), 3)` — Hexwise has exactly 3 personas.
- `test_hexwise_setup.py` line 100: `self.assertGreaterEqual(len(self.scan.backlog_files), 2)` — Hexwise has exactly 3 milestone files.

**Why it matters:** A weak assertion like `> 0` passes even if a regression causes 90% of the expected data to be lost. If the code broke and created only 1 issue instead of 17, `assertGreater(len(...), 0)` would still pass.

**What real tests would look like:** `self.assertEqual(len(self.fake_gh.milestones), 1)`, `self.assertEqual(len(stories), 2)`, etc.

---

### 4. Duplicate Test Logic: Same Pipeline Tested Three Times

**Anti-pattern type:** Duplicate test logic (7)
**Severity:** LOW

The full setup pipeline (init -> labels -> milestones -> issues) is exercised in three separate test files:

1. `test_lifecycle.py::test_13_full_pipeline` — minimal synthetic project, loose assertions
2. `test_hexwise_setup.py::test_full_setup_pipeline` — hexwise fixture, exact assertions
3. `test_golden_run.py::test_golden_full_setup_pipeline` — hexwise fixture, snapshot regression

Each file's docstring carefully explains why it is "complementary, not duplicative." And there are legitimate differences (fixture, assertion style, snapshot). But the core flow — `create_static_labels()` -> `create_persona_labels()` -> `create_milestones_on_github()` -> `parse_milestone_stories()` -> `create_issue()` — is copy-pasted across all three files with minor variations.

**Why it matters:** When the pipeline changes, all three must be updated. The near-identical setup boilerplate (git init, copy fixture, generate config) is ~40 lines repeated in each. A shared test helper or parametrized base class would reduce maintenance.

**Recommendation:** Extract a shared `_run_pipeline(project_root, fake_gh, config)` helper into a test utility module.

---

### 5. Happy Path Only: Several Test Classes Lack Error/Edge Cases

**Anti-pattern type:** Happy path only (3)
**Severity:** HIGH

**5a. `TestTeamVoices` (test_pipeline_scripts.py lines 32-89)**

Tests extract voices from valid saga files. No test for:
- Malformed blockquote syntax (e.g., `>` without `**Name:**`)
- File with valid structure but encoding errors (Latin-1 file read as UTF-8)
- Very long persona names or quotes
- Persona name containing special regex characters (e.g., `**J.R. (Bob):**`)

**5b. `TestComputeVelocity` (test_sprint_analytics.py lines 39-124)**

Good edge case for malformed SP labels, but no test for:
- Milestone with zero issues (division by zero in percentage calculation)
- Issues with no milestone field (should be filtered out)
- Negative story points (e.g., `sp:-3`)

**5c. `TestFormatReport` (test_sprint_analytics.py lines 209-245)**

Tests happy path and zero-data path. No test for:
- Very large numbers (999 SP, 100% velocity) — formatting edge cases
- Workload with a single persona (different formatting branch?)
- Non-ASCII persona names in workload

**5d. `TestGenerateReleaseNotes` (test_gh_interactions.py lines 347-368)**

Only 2 tests: basic notes and breaking changes. No test for:
- Empty commits list (notes for a release with no changes)
- Commits with scopes (do they render correctly?)
- Duplicate commit subjects
- Very long commit subjects (truncation?)
- Commit with only chore/ci types (no Features or Fixes sections)

---

### 6. Coverage Theater: Production Functions With No Corresponding Test

**Anti-pattern type:** Coverage theater (6)
**Severity:** HIGH

These production functions have **zero direct test coverage**. Some may be exercised incidentally through integration tests, but no test specifically validates their behavior or boundary conditions.

#### `scripts/validate_config.py`
- `gh()` (line 31) — the shared `gh` CLI wrapper. Tested only via mocks that replace it entirely.
- `gh_json()` (line 42) — same situation. The actual parsing of JSON from gh output is never tested.
- `get_ci_commands()` (line 576) — no direct test.
- `get_sprints_dir()` (line 593) — no direct test.
- `get_prd_dir()` (line 599) — tested only via `test_hexwise_setup.py` which checks `is not None`.
- `get_test_plan_dir()` (line 609) — same weak coverage.
- `get_sagas_dir()` (line 619) — same.
- `get_epics_dir()` (line 629) — same.
- `get_story_map()` (line 673) — same.
- `list_milestone_issues()` (line 757) — no test at all.
- `warn_if_at_limit()` (line 769) — no test at all.
- `_print_errors()` (line 479) — no test.
- `_strip_inline_comment()` (line 142) — tested implicitly through `parse_simple_toml` but no isolated boundary test.
- `_has_closing_bracket()` (line 158) — same.
- `_count_trailing_backslashes()` (line 134) — same.
- `_unescape_toml_string()` (line 174) — same.
- `_parse_value()` (line 198) — same.
- `_split_array()` (line 240) — same.
- `_set_nested()` (line 268) — same.

#### `scripts/sprint_init.py`
- `print_scan_results()` (line 851) — no test for output formatting.
- `print_generation_summary()` (line 888) — no test.
- `main()` (line 929) — no end-to-end CLI test.
- `_indicator()` (line 842) — no test.

#### `scripts/commit.py`
- `run_commit()` (line 90) — no test. Only `validate_message` and `check_atomicity` are tested.
- `main()` (line 101) — no end-to-end CLI test.

#### `scripts/traceability.py`
- `format_report()` (line 173) — no test for markdown output formatting.
- `main()` (line 207) — no CLI test.

#### `scripts/test_coverage.py`
- `format_report()` (line 143) — no test.
- `scan_project_tests()` (line 71) — tested implicitly but no isolated test with edge cases.
- `main()` (line 172) — no CLI test.

#### `scripts/team_voices.py`
- `main()` (line 89) — no CLI test.

#### `scripts/sprint_analytics.py`
- `main()` (line 190) — no CLI test.

#### `skills/sprint-setup/scripts/bootstrap_github.py`
- `check_prerequisites()` (line 18) — no test.
- `create_sprint_labels()` (line 103) — no direct test (exercised only incidentally).
- `create_saga_labels()` (line 152) — no direct test.
- `create_epic_labels()` (line 194) — no direct test.
- `_parse_saga_labels_from_backlog()` (line 116) — no test.
- `main()` (line 259) — no CLI test.

#### `skills/sprint-setup/scripts/populate_issues.py`
- `check_prerequisites()` (line 38) — no test.
- `_build_row_regex()` (line 63) — no isolated test.
- `_infer_sprint_number()` (line 133) — no direct test.
- `get_milestone_numbers()` (line 275) — no test.
- `build_milestone_title_map()` (line 286) — no test.
- `format_issue_body()` (line 317) — no test for the markdown body formatting.
- `main()` (line 383) — no CLI test.

#### `skills/sprint-setup/scripts/setup_ci.py`
- `check_prerequisites()` (line 317) — no test.
- `_job_name_from_command()` (line 285) — no test.
- `_find_test_command()` (line 309) — no test.
- `_generate_check_job()` (line 94) — no isolated test.
- `_generate_test_job()` (line 116) — no isolated test.
- `_generate_build_job()` (line 146) — no isolated test.
- `main()` (line 328) — no CLI test.

#### `skills/sprint-monitor/scripts/check_status.py`
- `write_log()` (line 305) — no test.
- `_count_sp()` (line 211) — no isolated test.
- `main()` (line 321) — no CLI test.

#### `skills/sprint-run/scripts/update_burndown.py`
- `closed_date()` (line 30) — tested only indirectly through integration tests.
- `load_tracking_metadata()` (line 125) — no test.
- `_fm_val()` (line 148) — no test.
- `main()` (line 156) — no CLI test.

#### `skills/sprint-run/scripts/sync_tracking.py`
- `_fetch_all_prs()` (line 38) — no test.
- `_parse_closed()` (line 104) — no isolated test.
- `main()` (line 285) — no CLI test.

#### `skills/sprint-release/scripts/release_gate.py`
- `find_latest_semver_tag()` (line 39) — no test.
- `parse_commits_since()` (line 57) — no test.
- `print_gate_summary()` (line 242) — no test.
- `main()` (line 613) — no CLI test.

#### `scripts/manage_epics.py`
- `_safe_int()` (line 27) — no test.
- `_parse_epic_from_lines()` (line 34) — no isolated test.
- `_parse_header_table()` (line 74) — no isolated test.
- `_parse_stories()` (line 94) — no isolated test.
- `_format_story_section()` (line 171) — no test.
- `main()` (line 357) — no CLI test.

#### `scripts/manage_sagas.py`
- `_safe_int()` (line 26) — no test.
- `_parse_header_table()` (line 69) — no isolated test.
- `_parse_epic_index()` (line 85) — no isolated test.
- `_parse_sprint_allocation()` (line 108) — no isolated test.
- `_find_section_ranges()` (line 130) — no isolated test.
- `main()` (line 263) — no CLI test.

#### `scripts/validate_anchors.py`
- `_find_symbol_line()` (line 162) — no isolated test.
- `_find_heading_line()` (line 179) — no isolated test.
- `main()` (line 290) — no CLI test.

**Total untested functions: ~75** (many are private helpers tested only via integration, but ~34 are public functions with no direct test at all).

---

### 7. Missing Boundary Tests: TOML Parser Edge Cases

**Anti-pattern type:** Missing boundary tests (5)
**Severity:** MEDIUM

The `parse_simple_toml()` function in `validate_config.py` has good edge-case tests in `test_pipeline_scripts.py::TestParseSimpleToml`, including empty input, malformed quotes, multiline arrays, booleans, integers, nested sections, and single-quote strings. This is actually one of the better-tested functions.

However, there are still missing boundary tests:

- **Unicode keys:** `key_with_emoji = "value"` — does the parser handle non-ASCII key names?
- **Empty array:** `items = []` — is this handled correctly?
- **Deeply nested sections:** `[a.b.c.d.e]` — does it create the full chain?
- **Key with dots:** `"dotted.key" = "value"` (TOML quoted keys) — likely unsupported but should not crash.
- **Tab indentation:** Values indented with tabs vs spaces.
- **Windows line endings:** `\r\n` — does the parser handle this?
- **Very large files:** Performance/memory with 10,000-line TOML.

---

### 8. Missing Negative Tests: Functions That Should Reject Invalid Input

**Anti-pattern type:** Missing negative tests (9)
**Severity:** HIGH

**8a. `extract_sp()` — no test for non-integer body text**

`validate_config.extract_sp()` is well-tested for labels but missing:
- Body containing `Story Points: abc` (non-numeric)
- Body containing `SP: -5` (negative)
- Body containing `Story Points: 1000000` (unreasonably large)

**8b. `create_issue()` — no test for missing milestone mapping**

`populate_issues.create_issue()` is called with `ms_numbers` and `ms_titles` dicts. No test verifies behavior when the story's sprint number is not in these dicts (KeyError path).

**8c. `parse_detail_blocks()` — limited negative testing**

`test_hexwise_setup.py` line 229 tests a well-formed detail block. `test_hexwise_setup.py` line 267 tests malformed tables. But no test for:
- Detail block with missing metadata table entirely
- Detail block with duplicate story IDs
- Empty file passed to `parse_detail_blocks()`

**8d. `bump_version()` — good negative tests in test_release_gate.py**

This is actually well-covered: 2-part, 1-part, 4-part, and empty all raise `ValueError`. No findings here.

**8e. `sync_one()` — no test for invalid kanban state transition**

`sync_tracking.sync_one()` updates status based on labels and issue state. No test verifies:
- What happens if the label says `kanban:dev` but the issue is closed (conflict)
- What happens if multiple kanban labels are present

**8f. `check_ci()` — no test for malformed run data**

`check_status.check_ci()` parses CI run data with fields like `status`, `conclusion`, `headBranch`. No test for:
- Run missing `conclusion` key
- Run with `status: "in_progress"` (neither completed nor failed)

---

### 9. Tests That Can't Fail (or Are Very Hard to Fail)

**Anti-pattern type:** Tests that can't fail (8)
**Severity:** LOW

**9a. `test_no_hardcoded_project_names` / `test_no_hardcoded_persona_names` / `test_no_hardcoded_cargo_commands` (test_verify_fixes.py lines 274-293)**

These tests check that `evals.json` does not contain specific strings like "Dreamcatcher", "Rachel", or "cargo build". Once these were removed, these tests will pass forever. They are regression guards, which is valid, but they can never catch a new instance of hardcoding — only the exact old values.

**9b. `test_correct_cells_no_warning` (test_verify_fixes.py line 368-390)**

Checks that a correctly formatted team index produces no stderr warnings. This test will always pass unless someone breaks the parser to emit warnings on valid input.

These are all defensible as regression tests, so severity is LOW.

---

### 10. `FakeGitHub` Testing Itself Through Production Code

**Anti-pattern type:** Tests that test the mock (2)
**Severity:** MEDIUM

**File:** `test_gh_interactions.py`, class `TestCheckBranchDivergenceFakeGH` (lines 955-1004) and `TestCheckDirectPushesFakeGH` (lines 1007-1071)

These test classes are explicitly labeled "P6-02: through FakeGitHub endpoints" and duplicate the same tests that exist with `@patch("check_status.gh_json")` mocks. The FakeGitHub versions test that the FakeGitHub implementation correctly processes the `compare` and `commits` API paths. This is testing the mock, not the production code.

Example: `TestCheckBranchDivergenceFakeGH.test_high_drift` (line 966) sets `self.fake.comparisons["feat/stale"] = {"behind_by": 25, ...}` and then calls `check_branch_divergence()`. But the real test of production logic is already in `TestCheckBranchDivergence.test_high_divergence` (line 862), which mocks `gh_json` directly.

**Why it matters:** The FakeGitHub versions are testing a different code path: production code -> `subprocess.run` patch -> `FakeGitHub.handle()` -> `_handle_api()` -> compare endpoint. A failure here could be either a production bug OR a FakeGitHub bug. When the FakeGitHub-backed test fails, you don't immediately know which is broken. The direct `@patch("check_status.gh_json")` version isolates the production logic.

**Counterpoint:** The FakeGitHub versions do serve as integration tests of the full call chain. But the docstring's "P6-02" label suggests they were created specifically to test FakeGitHub endpoints, confirming they are testing the mock.

---

### 11. Golden Run Test Relies on External Recording State

**Anti-pattern type:** Tests that can't fail (8)
**Severity:** MEDIUM

**File:** `test_golden_run.py`, line 96-104

```python
def _check_or_record(self, recorder, replayer, phase_name, check_fn):
    if RECORD_MODE:
        recorder.snapshot(phase_name)
    elif replayer.has_recordings():
        snapshot = replayer.load_snapshot(phase_name)
        diffs = check_fn(snapshot)
        self.assertEqual(diffs, [], ...)
    else:
        self.skipTest(
            "No golden recordings found. Run with GOLDEN_RECORD=1 to create them."
        )
```

If golden recordings don't exist (the default), every phase comparison is skipped via `self.skipTest`. The test still "passes" (shows as skipped, not failed). In CI without golden recordings, this provides zero protection.

**Why it matters:** A test that silently skips gives false confidence. If golden recordings are never committed to the repo, this test is permanently disabled.

---

### 12. Inconsistent Cleanup: Some Tests Use `tempfile.mkdtemp` Without Guaranteed Cleanup

**Anti-pattern type:** Fragile state (10)
**Severity:** LOW

**Affected locations:**
- `test_verify_fixes.py` lines 342-366: `tmpdir = tempfile.mkdtemp()` with `shutil.rmtree(tmpdir)` at end of method, not in a `finally` or `addCleanup`. If the test fails with an exception, the temp dir leaks.
- `test_pipeline_scripts.py` lines 838-898: `self._tmpdir = tempfile.mkdtemp()` with cleanup in `tearDown` (correct).

Most tests use `tempfile.TemporaryDirectory()` context manager or explicit `tearDown` cleanup, which is correct. A few use bare `mkdtemp()` with manual cleanup that could leak on exceptions.

---

### 13. Missing Test: `format_issue_body()` Output Correctness

**Anti-pattern type:** Coverage theater (6)
**Severity:** HIGH

`populate_issues.format_issue_body()` (line 317) generates the full GitHub issue body markdown from a `Story` object. This includes:
- User story text
- Acceptance criteria checkboxes
- Task breakdown
- Metadata table (epic, saga, blocks, blocked-by, test cases)

This function has **zero tests**. The integration tests create issues and verify they exist by title, but never inspect the issue body content. A regression in body formatting (e.g., breaking the acceptance criteria checkboxes) would pass all existing tests.

**What a real test would look like:**
```python
def test_format_issue_body_includes_ac():
    story = Story(story_id="US-01", title="Test",
                  acceptance_criteria=["AC-01: Input validated"],
                  ...)
    body = format_issue_body(story)
    assert "- [ ] AC-01" in body
```

---

### 14. Missing Test: `write_log()` in check_status.py

**Anti-pattern type:** Coverage theater (6)
**Severity:** MEDIUM

`check_status.write_log()` (line 305) writes the monitoring log to disk. No test verifies:
- File is created at the correct path
- Log format includes timestamp
- Appending vs overwriting behavior
- Handling of very long report lines

---

### 15. `assertIsNotNone` Used Where Stronger Assertions Are Possible

**Anti-pattern type:** Weak assertions (4)
**Severity:** LOW

**Affected locations:**
- `test_hexwise_setup.py` line 103: `self.assertIsNotNone(self.scan.rules_file.value)` — should assert the exact filename.
- `test_hexwise_setup.py` line 104: `self.assertIsNotNone(self.scan.dev_guide.value)` — same.
- `test_hexwise_setup.py` lines 153-157: Five `assertIsNotNone` calls for optional paths — should assert the actual path strings.
- `test_hexwise_setup.py` lines 163-167: Same pattern for deep doc detection.
- `test_pipeline_scripts.py` lines 929-939: `assertIsNotNone(det)` then `assertEqual(det.value, ...)` — the `assertIsNotNone` is redundant when followed by `assertEqual`.

---

## Recommendations (Priority Order)

### HIGH Priority

1. **Add tests for `format_issue_body()`** — zero coverage for a function that generates user-visible content.
2. **Add negative tests for `create_issue()` with missing milestone mappings** — KeyError path untested.
3. **Add tests for `list_milestone_issues()`** — public function with zero coverage.
4. **Add edge case tests for `extract_sp()` with non-numeric body text** — production code may silently return 0 or raise.
5. **Add tests for `find_latest_semver_tag()` and `parse_commits_since()`** — these are critical to release correctness and have zero direct tests.

### MEDIUM Priority

6. **Replace `assertGreater(len(...), 0)` with exact counts** where the fixture is deterministic.
7. **Standardize `os.chdir` cleanup** to use `self.addCleanup()` consistently.
8. **Add tests for `write_log()`** in check_status.py.
9. **Add TOML parser boundary tests** for empty arrays, Unicode keys, Windows line endings.
10. **Ensure golden run test fails (not skips) when recordings are absent** — or commit the recordings.

### LOW Priority

11. **Remove `test_state_dump`** — it tests FakeGitHub, not production code.
12. **Extract shared pipeline setup** into a test utility to reduce duplication.
13. **Add tests for `main()` entry points** of at least the most critical scripts (commit.py, release_gate.py).
14. **Fix bare `tempfile.mkdtemp()` calls** to use context managers or `addCleanup()`.

---

## Positive Observations

This test suite is substantially above average for a project of this size. Several things are done well:

1. **FakeGitHub with flag validation** (`_check_flags`) prevents silent test passing when production code sends unrecognized flags. This is excellent test infrastructure design.

2. **Sprint teardown tests** are thorough: 8 test classes covering classification, symlink handling, generated file removal, interactive mode, empty directories, and full teardown flow. This is the gold standard in this codebase.

3. **TOML parser edge cases** are well-covered: escaped backslashes, unterminated arrays, single-quoted strings, inline comments, booleans, integers, nested sections.

4. **Word-boundary regex tests** (P6-06) for story ID matching are excellent — they specifically test that `US-01` does not match `US-010`, which is a real production bug class.

5. **Release rollback tests** are thorough: commit failure, tag failure, push failure, and GitHub release failure all have dedicated tests that verify the correct `git reset --hard` calls in the right order.

6. **Idempotency tests** (`test_do_sync_idempotent`, `test_07_idempotent_issue_detection`) verify that running the same operation twice does not duplicate resources.
