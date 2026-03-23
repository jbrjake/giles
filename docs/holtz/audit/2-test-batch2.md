# Test Batch 2 Audit (Predictions 3, 7)

Audited: `tests/test_hooks.py`, `tests/test_lifecycle.py`, `tests/test_hexwise_setup.py`

Focus area: high-churn hooks code (test_hooks.py had 18 changes in last 50 commits).

---

## tests/test_hooks.py
**Tests:** 113
**Red flags:** 1
**Anti-patterns found:** Permissive validator (minor, localized)
**Details:**

This is the largest test file in the project and, despite being the highest-churn file, it is in remarkably good shape. 113 tests across 14 test classes, 170 total assertions (1.5 assertions per test average). Every hook module (`review_gate`, `commit_gate`, `verify_agent_output`, `session_context`, `_common`) has dedicated coverage.

**Hook path verification (special check):** All imports use `from hooks.xxx`, matching the current `hooks/` directory layout (post-refactor from `2dc773d`). No references to the old `.claude-plugin/hooks/` path exist. The `hooks.json` manifest confirms all paths use `${CLAUDE_PLUGIN_ROOT}/hooks/`. Mocking is minimal and appropriate -- `sys.stdin`/`sys.stdout` patches for main() entry points, and `_state_override` params for unit-level commit gate tests. No subprocess mocking in this file; functions are tested directly.

**TestCheckMerge (8 tests):** Strong. Tests blocked (no review, changes requested, review required), allowed (approved, non-merge), and three BH-013 edge cases for bare `gh pr merge` without a PR number. All assertions check exact string equality against "blocked"/"allowed".

**TestCheckPush (22 tests):** Excellent edge coverage. This is where the high churn paid off -- the class accumulated specific regression tests for compound commands (&&, ;, |), colon refspecs (HEAD:main), force-push prefixes (+main, +HEAD:main), refs/heads/ paths, --delete/-d flags, --mirror, --all, --repo flag bypass, and bare push. Each is tagged with a BH bug ID. Both blocked and allowed paths are tested for each pattern. No missing edges visible.

**TestLogBlocked (2 tests):** Good. Tests both the "no config" noop path and the "config exists" logging path. The log test verifies file creation AND content ("BLOCKED", reason string).

**TestGetBaseBranch (5 tests):** Good. Tests correct section reading, wrong-section rejection, no-file default, no-key default, and single-quoted values (BH35-008). This is a pure TOML parser test exercised against real temp files, not mocked.

**TestInlineTomlSectionComments (3 tests):** Targeted regression tests for BH35-005 and BH35-017. Tests both `_read_toml_key` and `_read_toml_string` parsers handle `[ci] # comment` section headers. The multiline array test with inline comment containing a quoted string is a strong edge case.

**TestCommitGateWordBoundary (2 tests):** Clean regression test for BH35-010. Verifies "greppython" does NOT match "python -m pytest" but the exact command does. Uses save/restore of module-level state, which is fine for unit tests.

**TestVerifyAgentOutput (14 tests):** Strong. Covers passed/failed/skipped verification, stderr capture, bridge-to-commit-gate interaction (both success and failure paths), and 7 `_read_toml_key` parsing tests (arrays, multiline arrays, strings, inline comments, single quotes, brackets inside quotes, escaped quotes, array boundary bleed). The bridge tests (BH27-003) are integration-style -- they write a stale state file, run verification, then check commit_gate state. These are real correctness checks.

**TestSessionContext (9 tests):** Good range. Retro extraction (simple, multi-sprint with recency check, absolute paths), risk extraction with severity/status filtering, DoD retro additions with word-boundary rejection (BH30-004 -- "retroactive" must not match), empty inputs, and adversarial stress test (20 action items, 10 DoD additions, 10 risks) for line-count budget.

**TestCommitGate (10 tests):** Good. Tests blocked/allowed for `git commit`, `scripts/commit.py`, `--dry-run` exemptions, source file detection (6 file types), check command matching (7 commands). The state machine tests (`mark_verified` -> `needs_verification` -> `check_commit_allowed`) exercise the real hash-based verification, not just the `_state_override` path. The stale-hash test writes a fake hash and verifies it triggers blocking.

**TestPostToolUseVerification (4 tests):** Clean. Tests success marks verified, failure does not, non-check ignored, and failure-then-success sequence. All use real state file cleanup.

**TestHookMainEntryPoints (4 tests):** Integration tests for actual `main()` and `post_main()` entry points with JSON stdin/stdout protocol. These verify the full hook contract: JSON in, JSON out, `continue` field, `permissionDecision` field. Good that these exist -- they catch protocol regressions that unit tests on individual functions would miss.

**TestSessionIdConsistency (2 tests):** Tests state file path consistency with and without `CLAUDE_SESSION_ID` env var. Appropriate for the bug it catches (BH28-003).

**TestUpdateTrackingVerification (5 tests):** Tests passed/failed writing, idempotent update (no duplication), no-frontmatter noop, and missing-file noop. The duplication test (line 1022) is particularly good -- it writes twice and asserts exactly 1 occurrence.

**TestResolveTrackingPath (4 tests):** Tests resolution via sprints_dir, direct-under-root fallback, not-found returns None, and end-to-end integration with update_tracking. The `assertIsNotNone` calls on lines 1081/1102/1139 are precondition guards followed by `assertTrue(Path(resolved).is_file())` -- not rubber stamps.

**TestFindProjectRoot (4 tests):** Tests CWD, parent directory walk-up, no-config fallback, and env var override. All use real temp dirs with real file structures.

**TestIsImplementerOutput (11 tests):** Good coverage of keyword matching. Tests positive cases (commit, PR, pushed, merged, branch, tests pass) and negative cases (no keywords, no check_commands, empty, reviewer mentioning commit, reviewer mentioning implementation). The reviewer-false-positive tests (BH26-008) are real correctness checks -- they verify the heuristic rejects reviewer language.

**One minor permissive validator concern:** `test_load_check_commands_from_toml` (line 392-400) checks `cmds == ["python -m pytest"]` and `smoke is None` but does not test what happens with a malformed TOML (missing section, missing key, empty file). The function is tested indirectly through 7 `_read_toml_key` tests and the main() integration tests, but `load_check_commands` itself only has the happy path tested.

---

## tests/test_lifecycle.py
**Tests:** 15
**Red flags:** 0
**Anti-patterns found:** None
**Details:**

This is the integration backbone: init -> bootstrap -> populate -> version -> release notes -> monitoring pipeline, all exercised against a real temp repo with FakeGitHub intercepting subprocess calls. 49 assertions across 15 tests (3.3 per test average).

**Test 01 (config validation):** Generates config, runs `validate_project()`, asserts `ok == True` with error details on failure. Not a rubber stamp -- `validate_project` checks ~15 required files and TOML keys.

**Test 02 (TOML keys):** Asserts specific sections exist and `language` is "rust". 5 assertions.

**Test 03 (label creation):** Creates 2 labels via FakeGitHub, checks both exist by name AND verifies color value. Not just structure.

**Test 04 (static labels):** Checks 7 specific label names. Loop assertion with per-label error messages.

**Test 05 (milestone creation):** Checks count == 1 and title content. The `any("Sprint 1" in t for t in titles)` assertion is mildly loose but appropriate for a generated title that includes sprint number.

**Test 06 (populate issues):** Strong. Verifies story count, existing-issues detection, issue creation count, specific story ID in titles, AND (P15 addition) verifies issue bodies are non-trivial (> 20 chars) and contain "Story" section header. 6+ assertions.

**Test 07 (idempotent detection):** Pre-populates FakeGitHub with issues, then calls `get_existing_issues()` and verifies both story IDs found. Clean.

**Tests 08-09b (version/release notes):** Tests `determine_bump` returns "minor" for feat+fix commits, `bump_version` produces "0.2.0", release notes contain expected sections/content, and compare link is generated when prior tag exists in git. Test 09b creates a real git tag and verifies the compare URL format.

**Test 10 (version write):** Writes version to TOML, verifies it appears AND original structure survives.

**Test 13 (full pipeline):** End-to-end pipeline with exact count assertions: >= 17 labels (with error detail listing all label names), exactly 1 milestone, exactly 2 issues. Well-documented scope comment explaining relationship to parallel tests.

**Test 14 (monitoring pipeline):** The most complex test. Sets up 4 issues with specific SP values and states, runs sync_tracking -> update_burndown -> check_milestone. Verifies: 4 tracking files created, burndown file exists AND contains "Completed: 8 SP" / "Remaining: 5 SP" (calculated from test data), status file contains story IDs, milestone report shows "2/4" stories and "8/13 SP" with "50%". This is real math verification, not structure checking.

**Test 15 (duplicate milestone):** Forces a duplicate milestone creation via the `gh()` helper and asserts it raises RuntimeError with "already exists". Proper negative test.

**Test 16 (missing config key):** Removes `repo` from TOML, runs validation, asserts failure with "repo" in error text. Proper negative test.

**No concerns.** The FakeGitHub approach is the right level of mocking -- it intercepts at the subprocess boundary so all JSON parsing and data transformation in the real code is exercised.

---

## tests/test_hexwise_setup.py
**Tests:** 27
**Red flags:** 2
**Anti-patterns found:** Rubber stamp (one cluster), Happy path tourist (mild)
**Details:**

Two classes: `TestHexwiseSetup` (20 tests, shared fixture via `setUpClass`) and `TestHexwisePipeline` (7 tests, per-test setUp). 82 assertions across 27 tests (3.0 per test average). Tests run against the hexwise fixture, a realistic 3-persona Rust project with deep docs.

**TestHexwiseSetup -- Scanner tests (4 tests):** Good. Verifies language detection ("rust"), persona count (4 = 3 devs + Giles) with specific name checks, milestone count (3), and rules/dev guide detection. Lines 108-112 show a BH-013 fix where `assertIsNotNone` was upgraded to also check path content ("RULES", "DEVELOPMENT"). The persona test checks specific names (rusti, palette, checker). Clean.

**TestHexwiseSetup -- Config tests (6 tests):** Good. Config validation via `validate_project()`, language check ("rust"), CI command check ("cargo" in joined string), persona names in INDEX.md, milestone file count (3), repo detection ("testowner/hexwise").

**TestHexwiseSetup -- Optional paths (3 tests):**

**Rubber stamp cluster (lines 153-186):** `test_optional_paths_present` does 5 `assertIsNotNone` calls with no content verification at all. `test_config_generator_includes_optional_paths` does 3 more `assertIsNotNone` calls. These 8 assertions only verify that values are not None -- they don't check that the paths point to the right directories or contain expected content. `test_scanner_detects_hexwise_deep_docs` partially redeems itself with BH-013 content checks on lines 177-179 (`assertIn("prd", ...)` etc.), but `test_plan_dir` and `story_map` are still only checked for not-None.

Net: 7 out of 82 assertions (8.5%) are pure not-None rubber stamps. Not critical -- these are optional config paths where "detected vs not detected" is the primary concern -- but `test_optional_paths_present` could verify the actual path values match expected directory names.

**TestHexwiseSetup -- Giles/DoD/history tests (4 tests):** Good. Giles persona existence AND non-symlink check (important architectural constraint), Giles section headers (7 specific section names), Giles in team INDEX, and DoD with section verification ("Mechanical", "Semantic", "CI green").

**TestHexwiseSetup -- Parse tests (4 tests):** Strong. `test_populate_issues_parses_epic_stories` checks story ID presence, enrichment result (epic non-empty, acceptance criteria count == 4). `test_parse_detail_block_story` is thorough -- 10 assertions on a single parsed story (ID, title, SP, priority, epic, blocks, test_cases, user_story, AC count). `test_parse_detail_blocks_five_digit_id` is a targeted BH30-003 regression test. `test_parse_detail_blocks_non_numeric_sp` tests graceful degradation (TBD -> 0).

**TestHexwiseSetup -- Malformed tables (1 test):** The only explicit error-path test in the class. Verifies the parser does not crash on badly-formatted markdown and still finds the one valid row (US-0102). Appropriate.

**TestHexwisePipeline (3+2+1+1 tests):**

`test_full_setup_pipeline`: End-to-end with exact count assertions (>= 17 labels, 3 milestones, 17 issues, 4 persona labels) AND enumeration of all 17 story IDs. The most thorough pipeline test in the project.

`test_ci_workflow_has_cargo` / `test_ci_workflow_uses_configured_branch`: Tests CI YAML generation with specific string checks ("cargo test", "cargo clippy", "branches: [develop]"). The branch test also checks the negative: `assertNotIn("branches: [main]")`.

`test_state_dump`: Tests FakeGitHub's `dump_state()`. BH23-111 comment notes the upgrade from structure-only to content checks. Verifies specific label names (kanban:todo, type:story, priority:P0) and milestone title content.

**Happy path tourist (mild):** Almost all tests are success paths. The only error-path test is `test_parse_milestone_stories_malformed_tables`. Missing: what happens when the hexwise fixture has a missing persona file, a corrupt milestone, or an invalid TOML. Given that test_lifecycle covers config validation error paths (Test 16), and the fixture is read-only-by-convention, this is a minor gap.

---

## Hook-specific structural check

**Do test_hooks.py tests reference correct hook paths?**

Yes. All imports use `from hooks.xxx` (e.g., `from hooks.review_gate import check_merge`), matching the current directory structure at `hooks/` (moved from `.claude-plugin/hooks/` in commit `2dc773d`). No stale path references found.

**Does the test mocking match the current hooks structure?**

Yes. The tests mock at the right boundaries:
- `sys.stdin`/`sys.stdout` for main() entry point tests (testing the JSON protocol)
- `_state_override` parameter for commit_gate unit tests (bypassing filesystem)
- Real temp directories with real files for TOML parsing, tracking files, and project root detection
- No subprocess mocking in test_hooks.py (hooks are tested as direct function calls)
- subprocess.run is only mocked in test_lifecycle.py and test_hexwise_setup.py via FakeGitHub

The `hooks.json` manifest confirms all hook commands use `${CLAUDE_PLUGIN_ROOT}/hooks/` paths, which aligns with the import structure in tests.

---

## Summary

| File | Tests | Assertions | Assertions/test | Red flags | Status |
|------|-------|------------|-----------------|-----------|--------|
| test_hooks.py | 113 | 170 | 1.5 | 1 | Good |
| test_lifecycle.py | 15 | 49 | 3.3 | 0 | Clean |
| test_hexwise_setup.py | 27 | 82 | 3.0 | 2 | Acceptable |

**Total red flags: 3** (all minor)

1. **test_hooks.py:** `load_check_commands` only has a happy-path test. Error paths (malformed TOML, missing section) are covered indirectly through `_read_toml_key` tests but not through the function itself.
2. **test_hexwise_setup.py:** 7 assertions in `test_optional_paths_present` and `test_config_generator_includes_optional_paths` are pure `assertIsNotNone` rubber stamps. Should verify path content.
3. **test_hexwise_setup.py:** No error-path tests for the scanner or config generator against corrupted fixture data (minor -- these are integration tests, not unit tests, and error paths are covered in test_lifecycle).

**Status: DONE**

The high churn in test_hooks.py was productive churn, not thrashing -- each BH-tagged regression test addresses a specific bypass or parsing edge case. The hook tests are well-structured and test the right things at the right abstraction level. No systemic anti-patterns detected.
