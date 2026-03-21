# Test Quality Audit — Batch 2

Adversarial review of 10 test files (batch 2) covering lifecycle integration,
sync_backlog, sprint_analytics, sprint_teardown, validate_anchors, hexwise
setup, verify-fixes, property-based tests, golden-run infra, and mock_project.

**Audit date:** 2026-03-15
**Auditor:** Claude Opus 4.6 (adversarial test quality mode)
**Files reviewed:** 10 test files + 5 source files + 2 infra files

---

## Summary

| Severity | Count |
|----------|-------|
| HIGH     | 6     |
| MEDIUM   | 11    |
| LOW      | 6     |
| **Total**| **23**|

---

## Findings

### Finding 1: Golden replay compares file names only, not file contents
- **File:** tests/golden_replay.py:137-175
- **Anti-pattern:** Snapshot Trap / Shallow End
- **Severity:** HIGH
- **Evidence:** `assert_files_match()` compares only the *set of relative paths* between the recorded snapshot and the current run. The `file_tree` dict in the snapshot stores full file contents (golden_recorder.py:78-101 records `result[rel] = content`), but `assert_files_match` never reads or compares those contents — it only checks `set(snapshot.get("file_tree", {}).keys())`.
- **Why it matters:** A production regression that changes the *content* of a generated file (e.g., malformed project.toml, wrong persona template) would pass the golden replay test as long as the same set of files exists. The entire point of golden testing — catching content regressions — is defeated. The recorder captures the content, but the replayer throws it away.

### Finding 2: Property tests for _parse_team_index test a reimplemented parser, not the real one
- **File:** tests/test_property_parsing.py:394-458
- **Anti-pattern:** Tautology Test / Mockingbird
- **Severity:** HIGH
- **Evidence:** The class comment at line 392 admits: "We can't easily call _parse_team_index with hypothesis because it reads from a file. Instead, we test the regex logic it uses by extracting the core parsing into test cases that use the same patterns." The test then reimplements the parsing loop inline (lines 438-457) and asserts against *its own reimplementation*. If `_parse_team_index` in production diverges from this inline copy (which it already has — the real function has whitespace-stripping separator detection per BH-P11-109), these tests would still pass.
- **Why it matters:** The test exercises a copy-pasted algorithm, not the production code. Any bug in `_parse_team_index` that doesn't exist in the test's reimplementation goes undetected. This is literally testing your test code against itself.

### Finding 3: Three "never crashes" tests have zero assertions
- **File:** tests/test_property_parsing.py:103-106, 173-175, 186-189
- **Anti-pattern:** Green Bar Addict / Shallow End
- **Severity:** MEDIUM
- **Evidence:** Three hypothesis tests (`TestExtractStoryId.test_never_crashes`, `TestExtractSp.test_never_crashes_on_body`, `TestYamlSafe.test_never_crashes`) call the production function but make no assertions on the return value. They only verify the function doesn't raise an exception. Example at line 103-106:
  ```python
  def test_never_crashes(self, title: str):
      """Must never raise an exception."""
      extract_story_id(title)
  ```
- **Why it matters:** If `extract_story_id` were replaced with `def extract_story_id(x): return None`, these tests would still pass. The "never crashes" property is useful but low-value on its own — it should at minimum verify the return type. Other tests in the same class do have assertions, but these 3 tests (running a combined 1200 examples per `max_examples` setting) contribute noise to the test count without proportional bug-finding value.

### Finding 4: test_golden_run silently skips in non-CI when recordings are absent
- **File:** tests/test_golden_run.py:93-113
- **Anti-pattern:** Green Bar Addict
- **Severity:** MEDIUM
- **Evidence:** The `_check_or_record` method at line 93-113 has three branches: (1) record mode, (2) replay mode if recordings exist, (3) skipTest if recordings are absent and not in CI. Locally, if someone deletes the golden recordings, the single test in this file will always be marked "skipped" — a green bar with no actual verification. Only in CI (`os.environ.get("CI")`) does it fail.
- **Why it matters:** A developer could run the full test suite locally, see all green, and push — but the golden test was actually skipped. The test infrastructure is designed for CI safety but gives a false sense of local confidence. This is mitigated by the CI check, so MEDIUM not HIGH.

### Finding 5: test_verify_fixes.test_source_uses_replace_not_format inspects source code instead of testing behavior
- **File:** tests/test_verify_fixes.py:605-612
- **Anti-pattern:** Inspector Clouseau
- **Severity:** MEDIUM
- **Evidence:** The test at line 605-612 uses `inspect.getsource(validate_project)` to check that the source code contains `.replace("{config_dir}"` and does not contain `.format(config_dir=`. This is testing implementation details, not behavior. If someone refactored `validate_project` to use f-strings or a different safe templating approach, this test would fail even though the behavior is correct.
- **Why it matters:** The companion tests (lines 587-603) already test the *behavior* — passing format-specifier strings and verifying they don't crash and are preserved literally in error messages. The source inspection test adds fragility without additional safety. If the behavior tests pass, the implementation choice is irrelevant.

### Finding 6: MockProject produces only 2 stories in 1 milestone — insufficient for edge case coverage
- **File:** tests/mock_project.py:124-131
- **Anti-pattern:** Happy Path Tourist
- **Severity:** MEDIUM
- **Evidence:** MockProject creates exactly 1 milestone with 2 stories, 2 personas, and minimal backlog structure. This fixture is used by `test_lifecycle.py` (13 tests) and `test_verify_fixes.py` (multiple classes). There is no multi-milestone scenario, no cross-milestone story references, no blocked/blocking relationships, no empty milestone, and no milestone with 0 stories.
- **Why it matters:** The `test_lifecycle.test_13_full_pipeline` test acknowledges this with a comment ("Assertions are intentionally loose... because the fixture is minimal") — but that means the full pipeline test can't catch regressions in milestone-to-story mapping logic, sprint numbering across milestones, or milestone ordering. The hexwise fixture covers some of this (3 milestones, 17 stories), but it's only used in `test_hexwise_setup` and `test_golden_run`, not in `test_lifecycle`.

### Finding 7: test_lifecycle.py has test numbering gaps (11, 12 removed) and sequential coupling
- **File:** tests/test_lifecycle.py:269-271
- **Anti-pattern:** Copy-Paste Archipelago (mild)
- **Severity:** LOW
- **Evidence:** Tests are numbered 01-14 but 11 and 12 are explicitly removed (comment at line 269-271: "removed — comprehensive versions live in test_gh_interactions.py"). The remaining tests use numbered names like `test_01_init_generates_valid_config` through `test_14_monitoring_pipeline`, which creates an implied sequential ordering. Each test independently creates its own state via `setUp()`, so they aren't actually coupled, but the numbering suggests an intended execution order.
- **Why it matters:** Minor readability issue. The numbering gaps suggest the test suite was built incrementally and the removed tests weren't renumbered. Not a bug risk, but confusing for new contributors.

### Finding 8: test_sprint_analytics TestComputeWorkload doesn't test SP-weighted workload
- **File:** tests/test_sprint_analytics.py:243-275
- **Anti-pattern:** Shallow End
- **Severity:** MEDIUM
- **Evidence:** `test_counts_per_persona` (line 250) verifies that workload returns story *counts* per persona, which matches the production code. However, the production function `compute_workload` only counts stories, not SP-weighted effort. There's no test verifying that if a persona has 2 stories worth 1 SP each and another has 1 story worth 13 SP, the workload distribution reflects this imbalance. The format_report test at line 281 uses a pre-built workload dict, so it can't catch this either.
- **Why it matters:** This isn't a test bug per se — the test matches the production code. But the analytics report could be misleading if it shows "rusti: 2, palette: 1" when rusti did 2 SP and palette did 13 SP. The test file doesn't have a single test for SP-weighted workload, making it harder to notice this design gap.

### Finding 9: test_sync_backlog.TestDoSync.test_do_sync_creates_milestones_and_issues counts milestones by file count, not actual creation
- **File:** tests/test_sync_backlog.py:185-195
- **Anti-pattern:** Permissive Validator
- **Severity:** MEDIUM
- **Evidence:** The test asserts `created["milestones"] == len(fake_gh.milestones)`, but looking at `do_sync()` in sync_backlog.py line 173: `result["milestones"] = len(milestone_files)`. The production code sets the milestone count to the number of *milestone files*, not the number of milestones actually created on GitHub. The test then checks this file count matches the FakeGitHub count, which works in the happy path but would mask a bug where `create_milestones_on_github` silently fails to create some milestones.
- **Why it matters:** If `create_milestones_on_github` crashes halfway through 3 milestones (creating only 1), `do_sync` would still report `milestones: 3` because it uses `len(milestone_files)`. The test wouldn't catch this because it's comparing the wrong thing.

### Finding 10: test_validate_anchors never tests the actual NAMESPACE_MAP against real project files in a focused way
- **File:** tests/test_validate_anchors.py:40-43
- **Anti-pattern:** Time Bomb
- **Severity:** MEDIUM
- **Evidence:** `test_all_mapped_files_exist` (line 40-43) checks that every file in `NAMESPACE_MAP` exists on disk. This is a useful guard, but it runs against the *real repo* (not a test fixture), making it fragile to running tests from a partial checkout, a different branch, or after a rename. It also doesn't verify that the anchors referenced in CLAUDE.md actually resolve — that's what `validate_anchors.main()` does, but the test for `main()` (in test_verify_fixes.py:455-571) creates synthetic files, never testing the real NAMESPACE_MAP + real CLAUDE.md combination.
- **Why it matters:** The real-repo assertion could fail spuriously in CI if a file is renamed but the test hasn't been updated. Meanwhile, the synthetic main() tests don't catch drift between CLAUDE.md and the actual source files. The guard and the integration test cover different things but neither covers the full chain.

### Finding 11: test_hexwise_setup.test_populate_issues_parses_epic_stories uses hardcoded acceptance criteria count
- **File:** tests/test_hexwise_setup.py:227
- **Anti-pattern:** Snapshot Trap (mild)
- **Severity:** LOW
- **Evidence:** Line 227: `self.assertEqual(len(us0101.acceptance_criteria), 4)`. This hardcodes the expected number of acceptance criteria for US-0101 in the hexwise fixture. If the fixture is updated to add or remove acceptance criteria, this test will fail with a confusing "4 != 5" error that doesn't explain what changed.
- **Why it matters:** Minor fragility. The test is correct as a regression guard, but it's tightly coupled to the fixture content. A comment explaining why 4 is the expected count would help.

### Finding 12: test_sprint_teardown doesn't test the main() path with unknown files present
- **File:** tests/test_sprint_teardown.py:481-521
- **Anti-pattern:** Happy Path Tourist
- **Severity:** MEDIUM
- **Evidence:** `TestTeardownMainExecute.test_execute_removes_generated` (line 502) creates only a generated file (project.toml) — no symlinks and no unknown files. The `TestTeardownMainDryRun.test_dry_run_preserves_files` (line 469) creates a symlink and a generated file but no unknown files. Neither main() test exercises the code path where unknown files prevent directory removal (sprint_teardown.py line 160: `removable = [d for d in directories if d != config_dir or not unknown]`). The unit-level `TestFullTeardownFlow` test does cover unknown files, but it doesn't go through `main()`.
- **Why it matters:** The directory removal logic around unknown files is exercised at the unit level but not through the orchestration path. A bug in how `main()` passes the unknown list to `remove_empty_dirs` could go undetected.

### Finding 13: test_sync_backlog.TestMain tests don't verify the content of created issues
- **File:** tests/test_sync_backlog.py:266-281
- **Anti-pattern:** Shallow End
- **Severity:** LOW
- **Evidence:** `test_second_run_syncs` (line 266) asserts `len(fake_gh.issues) > 0` after sync but doesn't check issue titles, labels, milestones, or bodies. The milestone file has a story ID `US-0001` but the test never verifies that the created issue title contains "US-0001".
- **Why it matters:** The test confirms that *some* issues were created but not that they match the milestone content. A parser bug that generates issues with wrong titles or missing labels would pass this test.

### Finding 14: test_verify_fixes has 12 scripts in _KNOWN_UNTESTED — large untested surface area
- **File:** tests/test_verify_fixes.py:864-877
- **Anti-pattern:** Happy Path Tourist (meta-level)
- **Severity:** HIGH
- **Evidence:** The `TestEveryScriptMainCovered._KNOWN_UNTESTED` frozenset contains 12 scripts that have `def main()` but no test calling `module.main()`:
  ```python
  _KNOWN_UNTESTED = frozenset((
      "team_voices", "sprint_init", "traceability", "validate_config",
      "manage_sagas", "manage_epics", "test_coverage", "setup_ci",
      "bootstrap_github", "populate_issues", "update_burndown", "release_gate",
  ))
  ```
  Several of these (release_gate, bootstrap_github, populate_issues, setup_ci) are core pipeline scripts. The gate test exists to prevent *new* scripts from bypassing testing, but it grandfathers in 12 existing scripts with zero orchestration coverage.
- **Why it matters:** These 12 scripts could have bugs in their main() entry points (argument parsing, error handling, exit codes) that no test exercises. The gate test is well-designed as a ratchet mechanism, but the starting position is permissive. `release_gate.main()` orchestrates versioning, tagging, and release publishing — a main() bug there could publish a bad release.

### Finding 15: test_lifecycle.test_14_monitoring_pipeline manually reimplements burndown logic
- **File:** tests/test_lifecycle.py:400-461
- **Anti-pattern:** Tautology Test (mild)
- **Severity:** MEDIUM
- **Evidence:** Phase 2 of this test (lines 413-445) manually loops through `fake_gh.issues`, calls `extract_story_id`, `kanban_from_labels`, `extract_sp`, and `update_burndown.closed_date` to build `rows`, then passes them to `write_burndown` and `update_sprint_status`. This reimplements the exact logic that production code would perform. The test verifies that the output of its own row-building matches expected values, but it doesn't test whether the production code would build the same rows from the same GitHub data.
- **Why it matters:** If `update_burndown.py` has its own issue-to-row mapping logic (which it likely does in a real pipeline), this test doesn't exercise it. It tests the shared utility functions (`extract_sp`, `kanban_from_labels`) individually but assembles them in a test-specific way.

### Finding 16: test_sprint_analytics.TestComputeVelocity.test_partial_delivery relies on integer truncation behavior
- **File:** tests/test_sprint_analytics.py:92
- **Anti-pattern:** Permissive Validator (mild)
- **Severity:** LOW
- **Evidence:** Line 92: `self.assertEqual(result["percentage"], 62)`. The calculation is `round(5/8 * 100) = round(62.5) = 62` (Python's banker's rounding). If someone changed the production code to use `int()` truncation or `math.ceil`, the percentage would become 62 or 63. The test asserts 62 but doesn't document that this relies on `round()` with banker's rounding for the `.5` case.
- **Why it matters:** Minor. A developer changing the rounding strategy might be surprised by this test failure. A comment noting the rounding behavior would help.

### Finding 17: test_hexwise_setup.test_full_setup_pipeline duplicates pipeline code from test_lifecycle
- **File:** tests/test_hexwise_setup.py:341-407 vs tests/test_lifecycle.py:275-327
- **Anti-pattern:** Copy-Paste Archipelago
- **Severity:** MEDIUM
- **Evidence:** Both `test_hexwise_setup.test_full_setup_pipeline` and `test_lifecycle.test_13_full_pipeline` contain nearly identical pipeline orchestration code: generate config, patch subprocess, create static labels, create persona labels, create milestones, parse stories, build ms_numbers/ms_titles dicts, loop through stories calling create_issue. The `test_golden_run.test_golden_full_setup_pipeline` (test_golden_run.py:115-214) contains a third copy. All three tests have explanatory docstrings noting they complement each other, but the pipeline orchestration code is duplicated verbatim.
- **Why it matters:** When the pipeline API changes (e.g., a new required parameter to `create_issue`), all three copies must be updated. A shared helper like `run_full_pipeline(fake_gh, config)` would reduce this to one maintenance point.

### Finding 18: golden_replay.assert_issues_match compares title sets, not ordered lists
- **File:** tests/golden_replay.py:116-133
- **Anti-pattern:** Permissive Validator
- **Severity:** LOW
- **Evidence:** Lines 116-133 sort issue titles and compare sets: `missing = set(recorded_titles) - set(current_titles)`. This means if two issues have the same title (which is unlikely but possible), a count mismatch would be caught by the length check (line 110-114) but the title comparison would not detect which duplicate is missing.
- **Why it matters:** Minor edge case. In practice, story IDs make titles unique. But the choice to use set comparison instead of list comparison means ordering changes are not detected either — if the pipeline starts emitting issues in a different order, the golden test won't notice.

### Finding 19: test_property_parsing strategy for _toml_string_val blacklists characters that are valid TOML
- **File:** tests/test_property_parsing.py:264-270
- **Anti-pattern:** Happy Path Tourist
- **Severity:** HIGH
- **Evidence:** The `_toml_string_val` strategy at lines 264-270 blacklists `'"\\#\n\r'` characters:
  ```python
  _toml_string_val = st.text(
      alphabet=st.characters(
          whitelist_categories=("L", "N", "P", "S", "Z"),
          blacklist_characters='"\\#\n\r',
      ),
      max_size=50,
  )
  ```
  This means the property tests for `parse_simple_toml` *never* test strings containing backslashes, double quotes, hash characters, or newlines within quoted values. These are exactly the characters that require escaping in TOML and are the most likely to trigger parser bugs. The `_toml_line` helper (line 276-283) does escape `\\` and `"`, but since the strategy never generates them, the escape logic is never exercised by the property tests.
- **Why it matters:** The custom TOML parser is a known complexity hotspot (documented as an architectural decision). Property tests that systematically avoid the hardest parsing cases provide false confidence. A string like `value = "path\\to\\file"` or `value = "say \"hello\""` is never generated, so parser bugs with escape sequences go untested by the fuzz engine.

### Finding 20: test_verify_fixes.TestCommitMainIntegration._fake_subprocess_run always returns the same staged files
- **File:** tests/test_verify_fixes.py:372-390
- **Anti-pattern:** Mockingbird
- **Severity:** LOW
- **Evidence:** The fake subprocess at lines 372-390 always returns `"scripts/commit.py\nscripts/validate_config.py\n"` for `git diff --cached`. This means `check_atomicity()` always sees files in the same directory (scripts/), so the atomicity check always passes. The test never exercises the warning path where staged files span multiple unrelated directories.
- **Why it matters:** Minor. The main purpose of `test_main_happy_path` is to test the main() orchestration, not atomicity. But since the test name is "happy path," it's worth noting that atomicity is never tested in an unhappy state.

### Finding 21: test_sync_backlog.TestCheckSync tests never exercise the combination of throttle + stabilized state
- **File:** tests/test_sync_backlog.py:136-154
- **Anti-pattern:** Happy Path Tourist
- **Severity:** LOW
- **Evidence:** `test_throttle_blocks_sync` (line 136) tests throttling with `pending_hashes` set, and `test_throttle_expired_allows_sync` (line 146) tests throttle expiry. But neither test verifies what happens when a file changes *during* a throttle period, then stabilizes, and *then* the throttle expires. The production code handles this implicitly (debounce updates pending_hashes, then on next check after throttle expires, pending == current triggers sync), but this multi-step scenario is not tested.
- **Why it matters:** The debounce+throttle interaction is the most complex state machine in sync_backlog. Testing each guard in isolation proves each condition works, but doesn't prove the combined state transitions work correctly.

### Finding 22: test_hexwise_setup re-scans in test_scanner_detects_hexwise_deep_docs despite having cls.scan
- **File:** tests/test_hexwise_setup.py:159-167
- **Anti-pattern:** Copy-Paste Archipelago (mild)
- **Severity:** LOW
- **Evidence:** Line 161: `scanner = ProjectScanner(self.project_dir)` creates a new scanner and calls `scanner.scan()` even though `cls.scan` (line 72-73 in setUpClass) already performed the same scan and stored the result. This redundant scan doesn't test anything different.
- **Why it matters:** Purely a maintenance/clarity issue. It wastes test time and creates confusion about whether the test intentionally re-scans (it doesn't — the docstring says nothing about testing scan freshness).

### Finding 23: Golden recorder captures symlink-resolved content but replayer checks raw paths
- **File:** tests/golden_recorder.py:90-100 vs tests/golden_replay.py:155-161
- **Anti-pattern:** Inspector Clouseau (mild)
- **Severity:** HIGH
- **Evidence:** The recorder at golden_recorder.py:90-94 iterates files with `rglob("*")` and reads content via `file_path.read_text()`, which follows symlinks (reads the target content). It stores the path as `file_path.relative_to(self.project_root)`. The replayer at golden_replay.py:155-161 also uses `rglob("*")` with `file_path.is_file()`, which returns True for symlinks to files. However, if a symlink target changes between recording and replay (e.g., a persona file's content is updated), the replayer's `assert_files_match` won't detect it because it only checks path presence, not content (per Finding 1). The combination means: (a) content is recorded but never checked, and (b) symlink targets could change without detection.
- **Why it matters:** This compounds Finding 1. The golden test infrastructure has all the data it needs to detect content regressions but doesn't use it. The recorder does the expensive work of capturing file contents; the replayer ignores it. This is the most impactful fix opportunity in the entire test suite — implementing content comparison in `assert_files_match` would immediately add regression detection for all generated and symlinked files.

---

## Overall Assessment

**Strongest test files:**
- `test_sync_backlog.py` — Thorough coverage of the debounce/throttle state machine with 7 distinct state transitions. Good use of FakeGitHub for integration.
- `test_sprint_teardown.py` — Comprehensive coverage of classify/remove/verify with real symlinks. Tests both unit-level functions and main() with multiple interaction modes.
- `test_sprint_analytics.py` — Good end-to-end coverage including main() integration, deduplication, and edge cases (no PRs, malformed labels).

**Weakest areas:**
1. **Golden test infra** (Findings 1, 23): Records content but never compares it. The most impactful single fix.
2. **Property test strategies** (Findings 2, 19): The team-index tests exercise a reimplemented parser, and the TOML string strategy avoids the hardest characters. These weaken the fuzz testing promise.
3. **12 untested main() functions** (Finding 14): The gate test is well-designed as a ratchet, but the starting point leaves core pipeline scripts uncovered.
4. **Pipeline code duplication** (Finding 17): Three copies of the same pipeline orchestration across test files.

**Recommended priority fixes:**
1. Implement content comparison in `golden_replay.assert_files_match` (Findings 1, 23)
2. Remove character blacklist from `_toml_string_val` strategy, handle escaping properly (Finding 19)
3. Replace inline parser reimplementation with calls to actual `_parse_team_index` via temp files (Finding 2)
4. Extract shared pipeline helper to eliminate three-way duplication (Finding 17)
5. Add main() integration tests for release_gate and bootstrap_github (Finding 14, highest-risk entries)
