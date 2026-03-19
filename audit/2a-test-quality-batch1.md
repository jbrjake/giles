# Audit 2a: Test Quality — Batch 1

**Auditor:** Claude Opus 4.6 (adversarial review)
**Date:** 2026-03-19
**Files reviewed:**
- `tests/test_kanban.py` (62 tests)
- `tests/test_release_gate.py` (59 tests)
- `tests/test_pipeline_scripts.py` (140 tests)
- `tests/conftest.py` (0 tests, config only)

---

## conftest.py (0 tests)

### Findings

- [LOW] **Guard depends on optional dev package name stability.** The `jq` import guard at line 28 catches `ImportError` but assumes the package is literally named `jq`. If the test infrastructure ever migrates to `pyjq` or `jqpy`, this guard silently becomes a no-op.
  - Evidence: `import jq as _jq` (line 29)
  - Impact: Low — this is a safety net, not a test.

- [INFO] **sys.path ordering is fragile.** `conftest.py` inserts `tests/` at position 0, ahead of `scripts/`. If any test helper module shadows a script name (e.g., a `test_coverage.py` helper vs `scripts/test_coverage.py`), the shadow wins silently. The individual test files also do their own `sys.path.insert(0, ...)` (e.g., `test_release_gate.py` lines 19-21, `test_pipeline_scripts.py` lines 18-19), creating a double-insertion race condition where conftest order vs per-file order depends on import timing.
  - Evidence: Both conftest.py and individual test files insert the same paths.
  - Impact: Confusing but currently benign because no actual name collisions exist.

---

## test_kanban.py (62 tests)

### Findings

- [MEDIUM] **Green Bar Addict: `test_illegal_transitions` asserts existence but not content of error.** Lines 119-126 verify that `validate_transition()` returns a non-None string for illegal transitions, but never check that the error message contains the actual state names or a helpful description. A regression that returns `""` (empty string) for all illegal transitions would pass this test.
  - Evidence: `self.assertIsNotNone(result)` + `self.assertIsInstance(result, str)` — no content check.
  - Impact: The implementation could return a useless error message like `""` and this test would still pass.

- [MEDIUM] **Green Bar Addict: `test_same_state_is_noop` only checks non-None.** Line 133 — `self.assertIsNotNone(result)` — doesn't verify the error message mentions "already in state" or any useful diagnostic.
  - Evidence: Line 133 — only `assertIsNotNone`.
  - Impact: Same as above — an empty-string error would pass.

- [MEDIUM] **Happy Path Tourist: `do_transition` never tested with missing `issue_number`.** The production code at `kanban.py:257-259` checks `if not issue_num` and returns False with an error. No test covers this branch.
  - Evidence: All `_make_tf` helpers in `TestTransitionCommand` set `issue_number="42"`. The branch at kanban.py:257 is never exercised.
  - Impact: If someone removes the `issue_number` guard, no test catches it. A story without an issue_number would attempt a GitHub API call with an empty string.

- [MEDIUM] **Inspector Clouseau: `test_transition_updates_local_and_github` inspects mock internals.** Lines 419-425 dig into `mock.call_args_list[0][0][0]` — the exact positional structure of the first call's first positional arg. This is brittle if the `gh()` function's call signature changes (e.g., switches to kwargs).
  - Evidence: `first_call = mock.call_args_list[0]` / `args = first_call[0][0]` (lines 419-420)
  - Impact: A refactor from `gh(["issue", ...])` to `gh(args=["issue", ...])` breaks this test even if behavior is identical.

- [LOW] **Inspector Clouseau: `test_transition_to_done_closes_issue` uses string-contains on repr.** Line 474 — `all_calls = str(mock.call_args_list)` then `assertIn("kanban:done", all_calls)`. This inspects the string representation of mock internals. If `gh` is called with the label embedded differently (e.g., comma-separated in a single `--add-label` arg), the string search still matches accidentally.
  - Evidence: Lines 474-478
  - Impact: Fragile to mock repr format changes across Python versions.

- [LOW] **Happy Path Tourist: `do_assign` double-fault rollback path untested.** `kanban.py:342-345` has a `except Exception as rollback_exc` clause inside `do_assign`'s except handler (parallel to the one tested in `do_transition` by `test_transition_double_fault_restores_tf_status`). The `do_assign` equivalent is never tested.
  - Evidence: kanban.py lines 342-345 — no test covers `do_assign`'s rollback-of-rollback path.
  - Impact: If the double-fault handler in `do_assign` has a bug, it silently corrupts state.

- [LOW] **Fragile: Concurrent lock test uses `time.sleep(0.2)`.** `test_concurrent_lock_serializes` (line 294) depends on a 200ms sleep to ensure ordering. On a heavily loaded CI runner, the sleep could complete before the waiter thread even starts, making the test pass vacuously (both threads run sequentially anyway).
  - Evidence: Line 294 — `time.sleep(0.2)` in the `holder` thread.
  - Impact: The test could pass even if locking is completely broken, because the holder finishes before the waiter starts.

- [LOW] **Missing assertion messages: `test_sync_accepts_legal_external_transition`.** Lines 694-695 use a boolean comprehension `accepted = [c for c in changes if ...]` then `self.assertTrue(accepted, ...)` — but if `changes` is empty (e.g., no-op), the error message only shows an empty list without context about which sync step failed.
  - Evidence: Multiple `do_sync` tests use the same pattern (lines 694, 711, 724).
  - Impact: Debugging failures requires reading the test source rather than just the assertion message.

- [MEDIUM] **Happy Path Tourist: `do_status` with empty sprint directory untested.** `kanban.py:497-498` returns `"(no stories found)"` when the stories directory doesn't exist. No test covers this.
  - Evidence: `TestStatusCommand` always creates stories. The early-return path at kanban.py:498 is never hit.
  - Impact: If the empty-directory message format changes or the early-return is accidentally removed, no test catches it.

- [LOW] **Happy Path Tourist: CLI `main()` paths only test the "no config" case.** `TestCLIInfrastructure.test_main_exits_1_without_config` only tests that `main()` exits 1 when no sprint-config exists. The `sprint is None` exit path (kanban.py:579-581), the `find_milestone` failure path (kanban.py:590-592), and the `assign` without flags path (kanban.py:617-619) are never tested.
  - Evidence: Only one `TestCLIInfrastructure` test exists.
  - Impact: CLI error handling regressions would go undetected.

- [MEDIUM] **Round-trip test doesn't verify all fields.** `test_round_trip` (lines 22-37) writes a TF with 10 fields but only asserts 4 of them (`story`, `implementer`, `status`, `pr_number`). The `reviewer`, `branch`, `issue_number`, `title`, and `sprint` fields are never verified on the loaded copy.
  - Evidence: Lines 34-37 — only 4 assertions for a 10-field struct.
  - Impact: A serialization bug in `reviewer`, `branch`, `issue_number`, or `title` would be missed by this test. (The comma-title test partially covers `title`, and empty-fields covers some others, but a comprehensive single round-trip check is absent.)

---

## test_release_gate.py (59 tests)

### Findings

- [HIGH] **Mockingbird: `TestDoRelease` mocks 5 layers deep, testing call sequences not behavior.** The `test_happy_path` test (lines 684-757) patches `calculate_version`, `write_version_to_toml`, `subprocess.run`, `find_milestone_number`, AND `gh` — all simultaneously. The test then inspects `mock_run.call_args_list` positions by index (lines 715-735) to verify exact command ordering. This is pure implementation-detail verification; it would pass even if the actual git commands produce incorrect output.
  - Evidence: 5 `@patch` decorators on a single test. Lines 715-735 check `run_cmds[0][0]`, `run_cmds[0][1]`, etc. by index position.
  - Impact: Any reordering of git commands (e.g., adding a preflight check) shifts all indices and breaks the test without any actual behavioral regression. The existing `TestDoReleaseIntegration` and `TestDoReleaseFakeGH` classes partially compensate, but the unit test class itself is fragile scaffolding.

- [HIGH] **Rubber Stamp: `test_release_notes_contain_correct_sections` doesn't verify notes content.** Lines 1296-1319 claim to verify release notes have correct sections for commit types, but the test never actually reads the notes. It only checks `self.fake.releases[0]["tag_name"]` (line 1319). The `FakeGitHub.handle` for `release create` receives the `--notes-file` path but the test never reads the file to verify its contents.
  - Evidence: Test name says "release_notes_contain_correct_sections" but only asserts `tag_name == "v2.0.0"`.
  - Impact: Release notes could be completely empty or malformed and this test would still pass.

- [MEDIUM] **Happy Path Tourist: `generate_release_notes` never directly tested.** The function at `release_gate.py:331-420` handles 7 distinct formatting branches (highlights from feats vs fixes vs other, features section, fixes section, breaking changes section, compare link with existing tag, compare link without existing tag, no compare link). None of these branches are tested in isolation. The function is only exercised indirectly through `do_release` where notes are written to a temp file and never read.
  - Evidence: No `TestGenerateReleaseNotes` class exists. `generate_release_notes` is called in `do_release` tests but the output is never asserted.
  - Impact: Notes formatting bugs (wrong section headers, missing breaking changes, malformed compare URLs) are invisible.

- [MEDIUM] **Happy Path Tourist: `determine_bump` never tested directly.** The function at `release_gate.py:83-100` determines bump type from conventional commits. It has 4 branches: BREAKING CHANGE in body, `!:` in subject, `feat:` prefix, and default patch. These are only tested indirectly via `calculate_version` tests. A direct test would verify edge cases like `fix!:` (breaking fix), `chore(scope):` (patch), multiple commits where highest bump wins, etc.
  - Evidence: No `TestDetermineBump` class. The function is complex enough (regex matching, early returns) to warrant its own tests.
  - Impact: A regex change in `determine_bump` could mis-categorize commits without detection.

- [MEDIUM] **Inspector Clouseau: `test_commit_failure_rollback_unstages_and_restores` checks command ordering by index.** Lines 854-893 find `git reset HEAD` and `git checkout --` calls by scanning the command list, then assert `reset_idx < checkout_idx`. This verifies implementation order rather than outcome (was the file actually restored?). The `TestDoReleaseIntegration.test_commit_failure_restores_toml` test does verify the actual file content, but this unit test is pure sequence inspection.
  - Evidence: Lines 880-893 — `self.assertLess(reset_idx, checkout_idx, ...)`
  - Impact: If the rollback achieves the same result through a different command sequence, this test breaks.

- [MEDIUM] **Time Bomb: `do_release` writes current UTC date to SPRINT-STATUS.md.** The happy path test at line 756 asserts `self.assertIn("Released", status)` but doesn't verify the date. The date comes from `datetime.now(timezone.utc)` at release_gate.py:685. If a test runs at midnight UTC, the date could differ from expectations. Currently this isn't directly tested (the test doesn't assert the date format), but if someone adds a date assertion later, it would be flaky.
  - Evidence: release_gate.py:685 — `datetime.now(timezone.utc).strftime("%Y-%m-%d")`
  - Impact: Low currently, but a latent time bomb for future test additions.

- [LOW] **Fragile: `TestDoReleaseFakeGH` restarts patcher in test body.** In `TestValidateGates.test_all_pass_with_real_commands` (lines 231-268), the default patcher is stopped, a new combined mock is created, and then the default patcher is restarted for tearDown. If the test fails between `self.patcher.stop()` and the restart (line 267), tearDown will call `stop()` on an already-stopped patcher, potentially masking the real failure with a double-stop error.
  - Evidence: Lines 231, 267-268 — manual stop/restart of patcher.
  - Impact: Test failures in this method could produce confusing secondary errors.

- [LOW] **Fragile: `TestDoRelease.setUp` uses `os.chdir` and `addCleanup`.** Lines 655-657 change the process working directory and use `addCleanup` to restore it. If any test in this class raises an exception during setUp (before addCleanup registers), the working directory is permanently changed for all subsequent tests.
  - Evidence: `os.chdir(self.tmpdir)` at line 656; `self.addCleanup(os.chdir, self._orig_cwd)` at line 657.
  - Impact: A setUp failure would contaminate all subsequent test classes. (tearDown at lines 673-675 also does chdir, which is redundant with addCleanup, suggesting prior confusion about cleanup order.)

- [LOW] **Happy Path Tourist: `print_gate_summary` never tested.** The function at release_gate.py:275-282 formats the gate results table. No test verifies its output format.
  - Evidence: No test calls or asserts on `print_gate_summary`.
  - Impact: Formatting regressions in the human-readable gate summary would be invisible.

- [LOW] **Happy Path Tourist: `release_gate.main()` CLI dispatch never tested.** The `main()` function at release_gate.py:714-755 has branches for `validate` vs `release` commands, dry-run flag handling, and error exits. None are directly tested.
  - Evidence: No test class for the CLI entry point.
  - Impact: CLI argument parsing regressions undetected.

- [MEDIUM] **Happy Path Tourist: `gate_stories` and `gate_ci` and `gate_prs` only tested indirectly.** These three gate functions are exercised through `validate_gates` tests but never have dedicated test classes. Edge cases like `gate_stories` returning unexpected types, `gate_ci` with no runs on the branch, or `gate_prs` hitting the 500-result truncation limit (release_gate.py:186-190) are untested.
  - Evidence: No `TestGateStories`, `TestGateCi`, or `TestGatePrs` classes exist.
  - Impact: The 500-PR truncation safety check at release_gate.py:186-190 is completely untested — a particularly important safety gate.

- [LOW] **Rubber Stamp: `test_version_written_to_correct_path` asserts mocked write was called.** Lines 1324-1345 verify `mock_write.assert_called_once()` and check the path argument contains "project.toml". Since `write_version_to_toml` is mocked, this only verifies the mock was called — not that the real function writes correctly. (The `TestWriteVersionToToml` class does cover the real function, so this is a duplication-of-mocking concern rather than a gap.)
  - Evidence: Lines 1341-1345.
  - Impact: Minor — the real function is tested elsewhere.

---

## test_pipeline_scripts.py (140 tests)

### Findings

- [HIGH] **Green Bar Addict: CI generation tests only check keyword presence, not structure.** `TestCIGeneration` (lines 695-756) tests Python, Node.js, and Go CI YAML generation by checking that output contains substrings like `"pip install"`, `"npm"`, `"go test"`. These tests would pass even if the YAML is syntactically invalid, has incorrect indentation (breaking GitHub Actions), or produces a workflow that doesn't actually run the configured commands.
  - Evidence: `self.assertIn("pip install", yaml)` (line 708), `self.assertIn("npm", yaml)` (line 722).
  - Impact: A YAML generation bug that produces `run: |pip install` (missing space) or puts commands under the wrong `steps:` key would pass all tests. No test parses the YAML output or validates its structure.

- [HIGH] **Green Bar Addict: `test_extract_voices_from_sagas` uses weak content assertions.** Lines 35-46 check that `"type system"` appears in the first Rusti quote (`assertIn("type system", rusti_quotes[0]["quote"].lower())`). This is a substring check on fixture data that would pass even if the extraction logic captured surrounding markdown formatting, blank lines, or metadata as part of the "quote". No test verifies that quotes are cleanly extracted without markdown artifacts.
  - Evidence: `self.assertIn("type system", rusti_quotes[0]["quote"].lower())` (line 46)
  - Impact: Quotes could contain `> `, `**`, or heading prefixes and this test would still pass.

- [MEDIUM] **Happy Path Tourist: `test_unsupported_language_produces_todo_comment` doesn't test Rust.** The `TestCIGeneration` class tests Python, Node.js, Go, and an unsupported language (Haskell). But Rust — which per `CLAUDE.md` has its own entry in `_SETUP_REGISTRY` — is never tested for CI generation.
  - Evidence: No `test_rust_ci_yaml` method in `TestCIGeneration`.
  - Impact: Rust CI generation regressions would be invisible.

- [MEDIUM] **Happy Path Tourist: `parse_saga` title extraction from malformed file is tested, but `parse_epic` title from empty file isn't verified for correctness.** `test_parse_epic_empty_file` (lines 371-382) checks `epic["title"] == ""` for an empty file. But what about a file with content that lacks the expected `# E-XXXX` heading? The fallback behavior (what title does it extract from `"Random text without heading format"`) is untested.
  - Evidence: Only empty file is tested, not a file with malformed heading format.
  - Impact: A file without `#` heading could produce unexpected title extraction results.

- [MEDIUM] **Fragile: Fixture-dependent tests assume exact content of `tests/fixtures/hexwise/`.** At least 20 tests depend on exact content of Hexwise fixture files (story counts, persona names, specific story IDs like `US-0101`, exact SP totals). If anyone edits the fixture to add a story, rename a persona, or adjust SP values, multiple tests break simultaneously with no clear connection to the actual code change.
  - Evidence: `self.assertEqual(len(story_ids), 17)` (line 105), `self.assertEqual(epic["total_sp"], 16)` (line 287), `self.assertEqual(saga["stories_count"], 8)` (line 438).
  - Impact: Fixture maintenance silently breaks many tests. No constants or shared definitions connect the expected values to the fixture data.

- [MEDIUM] **Green Bar Addict: `test_traceability_no_gaps` asserts empty list without verifying count.** Line 121 — `self.assertEqual(report["stories_without_tests"], [])` — this would also pass if `build_traceability` returns no stories at all (i.e., the function is broken and returns `{"stories_without_tests": []}` with 0 stories parsed). The test doesn't first verify that stories were actually parsed.
  - Evidence: No preceding assertion like `self.assertGreater(len(report["stories"]), 0)`.
  - Impact: If `build_traceability` fails silently (returns empty structures), this test passes vacuously.

- [MEDIUM] **Green Bar Addict: `test_traceability_prd_coverage` same vacuous-pass risk.** Line 141 — `self.assertEqual(report["requirements_without_stories"], [])` — same issue. If `parse_requirements` returns empty, there are no requirements to be uncovered, so the assertion passes trivially.
  - Evidence: No guard assertion that requirements were actually parsed.
  - Impact: A silently broken `parse_requirements` function would pass this test.

- [MEDIUM] **Happy Path Tourist: `reorder_stories` with wrong/missing IDs untested.** `test_reorder_stories` (lines 345-353) passes the exact correct set of IDs in a new order. What happens when the caller passes an ID that doesn't exist in the epic, or omits one? The production code's behavior under these conditions is undocumented and untested.
  - Evidence: Only one happy-path test for `reorder_stories`.
  - Impact: A caller could silently lose stories by passing an incomplete ID list.

- [LOW] **Happy Path Tourist: `update_team_voices` with empty voices dict untested.** What happens if `update_team_voices(saga_path, {})` is called? Does it clear the existing voices section? Leave it unchanged? No test covers this.
  - Evidence: Tests at lines 787-836 only test 1+ voices.
  - Impact: Clearing voices during a retro could produce unexpected results.

- [LOW] **Happy Path Tourist: `renumber_stories` with empty new_ids list untested.** What happens if `renumber_stories(path, "US-0102", [])` is called? Does it delete all references? Leave them unchanged?
  - Evidence: Tests only use 2-element replacement lists.
  - Impact: Edge case that could corrupt epic files if misused.

- [LOW] **Green Bar Addict: `test_detect_language_python` checks `.value` and `.confidence` but not `.evidence`.** Line 1065 — the `Detection` namedtuple/dataclass likely has an `evidence` field explaining why Python was detected. This is never checked.
  - Evidence: `self.assertEqual(det.value, "Python")` but no `det.evidence` assertion.
  - Impact: Minor — the evidence string could be wrong without detection.

- [LOW] **Inspector Clouseau: `test_split_array_trailing_comma` asserts internal formatting.** Line 664 — `self.assertEqual(_split_array('"a", "b",'), ['"a"', ' "b"'])` — note the leading space in `' "b"'`. This tests the exact internal whitespace handling of a private function. If `_split_array` is refactored to strip whitespace from elements, this test breaks even though the higher-level parse behavior is unchanged.
  - Evidence: Leading space in expected value on line 664.
  - Impact: Fragile to internal refactoring of `_split_array`.

- [LOW] **Happy Path Tourist: `validate_project` tests don't cover symlink validation.** Per CLAUDE.md, sprint-config uses symlinks to project files. `TestValidateProjectNegative` creates real files, never broken symlinks. If a symlink target is deleted, does `validate_project` report the error clearly?
  - Evidence: `_write_minimal_config` creates real files, not symlinks.
  - Impact: Broken symlinks in sprint-config would produce unclear errors.

- [LOW] **Fragile: `TestScannerPythonProject` and `TestScannerMinimalProject` use `tempfile.mkdtemp` without `TemporaryDirectory` context manager.** Lines 998, 1160 use `mkdtemp` and manual `shutil.rmtree` in `tearDown`. If `setUp` raises after `mkdtemp` but before the scanner is created, `tearDown` still runs but `self._tmpdir` exists. However if `setUp` raises before `self._tmpdir` is set, `tearDown` would raise `AttributeError`, masking the original error.
  - Evidence: `self._tmpdir = tempfile.mkdtemp()` (line 998), `shutil.rmtree(self._tmpdir, ...)` (line 1060).
  - Impact: Confusing error cascades if setUp fails partway through. (The `ignore_errors=True` on rmtree mitigates the worst case.)

- [LOW] **Return values not tested: `update_sprint_allocation` and `update_epic_index`.** `test_update_sprint_allocation` (lines 458-470) and `test_update_epic_index` (lines 472-481) call the functions but don't check return values. If these functions return a success/failure indicator, it's ignored.
  - Evidence: Lines 467, 478 — no `result = ...` or assertion on return value.
  - Impact: If these functions start returning False on failure, tests would still pass.

---

## Cross-File Patterns

- [MEDIUM] **Systematic: `assertIsNotNone` used without follow-up content check.** Across all files, `assertIsNotNone(result)` is used as a primary assertion at least 15 times. In most cases, the return value is a string error message, but the message content is never verified. This is the single most common anti-pattern across the test suite.

- [MEDIUM] **Systematic: `str(mock.call_args_list)` string-searching pattern.** At least 10 tests across `test_kanban.py` and `test_release_gate.py` convert mock call args to strings and use `assertIn` to check for substrings. This is fragile to Python version changes in mock repr format and doesn't distinguish between arguments, keyword arguments, and nested structures.

- [LOW] **Systematic: Error messages in assertions are inconsistent.** Some tests provide excellent diagnostic messages (e.g., `f"Expected {current}->{target} to be legal"`), while others provide none at all (bare `assertIsNotNone`). No consistent policy for assertion messages exists.

---

## Summary Table

| File | Tests | HIGH | MEDIUM | LOW |
|------|-------|------|--------|-----|
| conftest.py | 0 | 0 | 0 | 2 |
| test_kanban.py | 62 | 0 | 5 | 5 |
| test_release_gate.py | 59 | 2 | 4 | 5 |
| test_pipeline_scripts.py | 140 | 2 | 6 | 7 |
| Cross-file patterns | — | 0 | 2 | 1 |
| **Total** | **261** | **4** | **17** | **20** |

### Highest-Priority Items

1. **test_release_gate.py: `test_release_notes_contain_correct_sections` is a rubber stamp** — claims to verify notes content but only checks the tag name. This is the most egregious finding: the test name actively misleads about what it covers.

2. **test_release_gate.py: `generate_release_notes` has zero direct test coverage** — a function with 7 formatting branches that produces user-visible output, tested only indirectly through tests that never read the output.

3. **test_pipeline_scripts.py: CI YAML tests check substrings, not structure** — the most impactful gap because invalid YAML would break real CI pipelines.

4. **test_release_gate.py: `TestDoRelease` mocks 5 layers** — while compensated by integration tests, the unit tests provide a false sense of coverage by verifying mock call sequences rather than behavior.
