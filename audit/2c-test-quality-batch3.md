# Test Quality Audit — Batch 3

Adversarial review of 8 test files for anti-patterns that create the appearance
of coverage without the substance.

**Files reviewed:** test_verify_fixes.py, test_bugfix_regression.py,
test_property_parsing.py, test_hexwise_setup.py, test_sprint_analytics.py,
test_sync_backlog.py, test_validate_anchors.py, test_sprint_teardown.py

---

## 1. test_verify_fixes.py (~2099 lines)

### Finding: Many "main() integration tests" only exercise argparse, not real work
**File:** test_verify_fixes.py:1015-1150
**Anti-pattern:** Happy Path Tourist / Green Bar Addict
**Problem:** A large block of tests labeled "P13-003: main() integration tests for
previously untested scripts" follows a consistent pattern: call `main()` with
`--help` (exits 0), call `main()` with no args or missing config (exits 1 or 2).
These tests verify only argument parsing and early-exit error paths. They never
exercise the scripts' core logic. Examples:

- `TestUpdateBurndownMain`: only tests `--help`, bad args, and no args.
- `TestTeamVoicesMain`: only tests missing config exits 1.
- `TestManageEpicsMain`: only tests no-args exits 1.
- `TestManageSagasMain`: only tests no-args exits 1.
- `TestTestCoverageMain`: only tests missing config exits 1.

The `TestEveryScriptMainCovered` gate test (line 1258) scans test source for
`module.main()` calls and flags scripts without them — but it does not
distinguish between an argparse-only test and a meaningful integration test.
A test that only calls `main()` with `--help` satisfies the gate while providing
zero coverage of the script's actual behavior.

**Impact:** 7 scripts have only argparse-level "integration" tests. A regression
that breaks their core logic path would not be caught.

**Counterpoint:** Some of these scripts DO have separate happy-path tests lower
in the file (e.g., `TestSetupCiMainHappyPath`, `TestSprintInitMainHappyPath`).
The issue is that others (update_burndown, manage_epics, manage_sagas) do not.

---

### Finding: TestTeardownDryRunOutput asserts "no crash" but not output content
**File:** test_verify_fixes.py:1869-1942
**Anti-pattern:** Green Bar Addict
**Problem:** `test_dry_run_with_symlinks_and_generated` (line 1872) calls
`print_dry_run()` with a mix of symlinks and generated files. The test's success
criterion is "if we get here without exception, the test passes" (line 1902).
There is no assertion on the output whatsoever. The function could print nothing,
print garbage, or print the wrong classification, and the test would still pass.

Similarly, `test_dry_run_empty_lists` (line 1906) and `test_dry_run_with_unknown_files`
(line 1921) only verify no crash. The last one does check `len(unknown) == 1`
before calling `print_dry_run`, but never inspects what was printed.

---

### Finding: TestEveryScriptMainCovered gate test is circumventable
**File:** test_verify_fixes.py:1258-1351
**Anti-pattern:** Paper Tiger
**Problem:** This gate test scans all test files for the regex pattern
`\bmodule_name\.main\(\)` to verify each script has a main() test. But:

1. The pattern matches `module.main()` calls inside comments or strings.
2. A test that calls `module.main()` with `--help` and only checks exit code 0
   satisfies the gate while testing nothing.
3. The `_KNOWN_UNTESTED` escape hatch is currently empty, which is good, but
   the test cannot distinguish between "has argparse test" and "has meaningful
   test."

---

### Finding: BH regression tests are generally solid — not rubber stamps
**File:** test_verify_fixes.py (various BH-xxx tests)
**Anti-pattern:** None (positive finding)
**Problem:** The BH-series regression tests in this file are well-constructed.
Examples of good practice:

- `TestBH19SymlinkTraversal` (line 1721): Creates an actual file outside the
  project root and verifies the symlink is rejected, checking `gen.skipped` for
  the REJECTED reason.
- `TestBH19SpRoundtrip` (line 1704): Tests 8 different SP values through a
  full format-then-extract roundtrip.
- `TestBH19BurndownClosedOverride` (line 1628): Tests the specific data-flow
  scenario where a closed issue has a stale kanban label.
- `TestP17SyncTrackingWritePersistence` (line 1279): Reads back from disk
  after sync to verify persistence, not just in-memory state.

These are not rubber stamps — they test the fixed behavior with assertions
specific enough to catch the original bug if it regressed.

---

## 2. test_bugfix_regression.py (~1475 lines)

### Finding: BH-021 test was previously "test theater" and explicitly rewritten
**File:** test_bugfix_regression.py:1171-1228
**Anti-pattern:** Paper Tiger (historically, now fixed)
**Problem:** The comment at line 1175 explicitly acknowledges: "BH19-002: Actually
call main() with do_sync failing. Previous version was test theater: saved/loaded
state without calling main()." The current version patches `do_sync` to raise
`RuntimeError("boom")` and then calls `sync_backlog.main()` to verify the real
failure path does not update `file_hashes`. This is now a good test.

**Observation:** The self-aware comment is a sign that prior passes identified
and fixed test theater. The current version asserts both the error status return
AND the specific state preservation (`file_hashes` retains pre-failure value).

---

### Finding: BH-004 vacuous-truth test could have a stronger assertion
**File:** test_bugfix_regression.py:331-367
**Anti-pattern:** Borderline Paper Tiger
**Problem:** `test_in_progress_checks_not_green` verifies that an IN_PROGRESS
check does not show "CI green" — it asserts `assertNotIn("CI green", full)` and
`assertIn("CI pending", full)`. However, it patches `check_status.gh_json`
directly rather than going through FakeGitHub, so it bypasses the whole `gh`
command construction path. If check_status changed its `gh_json` call arguments
(e.g., wrong JSON fields), this test would not catch it. The test verifies
output formatting correctness, not the data-fetching contract.

---

### Finding: Most BH-series tests in this file are well-targeted — not rubber stamps
**File:** test_bugfix_regression.py (various)
**Anti-pattern:** None (positive finding)
**Problem:** Key tests demonstrate anti-regression value:

- `TestBH001PaginatedJson` (line 297): Tests both normal JSON and concatenated
  arrays (the specific bug scenario) with correct value assertions.
- `TestBH011ExtractSpBoundary` (line 442): Tests that "BSP:" and "ISP=" do NOT
  match, while "SP:" and "sp:" DO match — exactly the boundary condition.
- `TestBH023HyphenatedTomlKeys` (line 500): Tests both hyphenated and
  underscored keys parse correctly.
- `TestBH002TomlRejectMetacharacters` (line 958): Tests unquoted `=`, `[`, `{`
  are rejected while quoted versions work fine.

---

### Finding: FakeGitHub strict mode test coverage is thorough
**File:** test_bugfix_regression.py:755-841
**Anti-pattern:** None (positive finding)
**Problem:** The strict mode tests verify: implemented flags don't warn,
unimplemented flags do warn, unknown flags always raise, warnings accumulate,
and `_IMPLEMENTED_FLAGS` is a subset of `_KNOWN_FLAGS`. The last check
(line 815-824) is a structural invariant test that prevents drift between
the two sets — this is genuinely protective.

---

## 3. test_property_parsing.py (528 lines)

### Finding: _yaml_safe dangerous-chars predicate is OUT OF SYNC with production code
**File:** test_property_parsing.py:224-242 vs. validate_config.py:1060-1073
**Anti-pattern:** Paper Tiger / Stale Mirror
**Problem:** `test_dangerous_chars_get_quoted` defines a local `dangerous`
predicate that duplicates the production code's quoting conditions, then asserts
that all dangerous values get quoted. But the test's predicate is MISSING several
conditions that the production code checks:

| Condition | Production | Test |
|-----------|-----------|------|
| `',' in value` (BH23-200) | Yes | **NO** |
| `'\n' in value` (BH21-005) | Yes | **NO** |
| `'\r' in value` (BH21-005) | Yes | **NO** |
| `value != value.strip()` (BH23-205) | Yes | **NO** |

The newline/CR omission is partially excused by the hypothesis strategy
blacklisting `\r` at line 298, but `\n` is NOT blacklisted — so the strategy
can generate strings containing newlines. When it does, the test's `dangerous`
predicate says "not dangerous" (because it doesn't check for `\n`), so the
assertion is skipped. The production code WILL quote it, but the test doesn't
verify this.

For commas: the strategy CAN generate strings with commas (punctuation category
`P` includes commas). A comma-containing value will be quoted by production code
but the test's predicate won't flag it as needing quoting, so again, the
assertion is skipped — a false negative.

For leading/trailing whitespace: the strategy generates text with `Z` category
(spaces), so values like `" hello"` can be generated. Production quotes these,
but the test doesn't check.

**Evidence:** The test predicate at line 225-237 has 8 conditions; the production
code at validate_config.py:1060-1073 has 12 conditions. The test last received
conditions through BH-007; BH21-005, BH22-108, BH23-200, and BH23-205 added
new quoting triggers to production code but the test predicate was never updated.

**Impact:** Hypothesis can generate values that should be quoted, but the test
won't flag the missing quoting because its mirror predicate doesn't know about
the newer conditions. This means if someone removes the comma or newline quoting
from production, this test won't catch the regression.

---

### Finding: hypothesis strategies are well-tuned for the functions tested
**File:** test_property_parsing.py (all classes)
**Anti-pattern:** None (positive finding)
**Problem:** The property tests genuinely exercise production code with diverse
inputs:

- `extract_story_id`: 5 property tests including boundary cases (emoji, empty
  string, whitespace, dashes), testing filename safety, length bounds, and
  standard-ID extraction. The explicit `@example` decorators hit corner cases.
- `extract_sp`: Tests label extraction, body text, table format, `sp=` format,
  label-body precedence, and false positive rejection.
- `parse_simple_toml`: Full roundtrip testing for strings, ints, bools, sections,
  arrays, multiline arrays, and multiple sections. The TOML escaping helper
  `_toml_line` is well-implemented.
- `_parse_team_index`: Tests row extraction with generated names/roles and
  row-count fidelity.

The max_examples counts (200-500) are reasonable for the input complexity.

---

### Finding: _yaml_safe frontmatter_value roundtrip test is excellent
**File:** test_property_parsing.py:275-285
**Anti-pattern:** None (positive finding)
**Problem:** `test_frontmatter_value_roundtrip` (BH23-205) tests the full
write-then-read cycle: `_yaml_safe(value)` produces a YAML-safe string, then
`frontmatter_value(f"key: {safe}", "key")` reads it back and compares to the
original. This catches any mismatch between quoting and unquoting logic. This
is the gold standard for roundtrip property testing.

---

### Finding: Quoting roundtrip test uses a hand-rolled unescaper
**File:** test_property_parsing.py:196-219
**Anti-pattern:** Borderline Rubber Stamp
**Problem:** `test_quoting_roundtrip` (line 197) implements its own unescaping
logic to verify roundtrips. If both the test's unescaper and the production
code's escaper have the same bug, the test passes despite the bug. The
`test_frontmatter_value_roundtrip` at line 275 is strictly superior because
it uses the ACTUAL production `frontmatter_value` function for the read-back.
The hand-rolled roundtrip test at line 197 is largely redundant with 275 and
carries more risk of tautological agreement.

---

## 4. test_hexwise_setup.py (457 lines)

### Finding: setUpClass shares mutable state but includes a warning comment
**File:** test_hexwise_setup.py:37-83
**Anti-pattern:** Shared Mutable State (acknowledged)
**Problem:** `TestHexwiseSetup.setUpClass` copies the hexwise fixture to a temp
dir, runs `ProjectScanner.scan()` and `ConfigGenerator.generate()` once, and
stores results on `cls.scan` and `cls.config_dir`. The docstring at line 39-43
explicitly warns: "WARNING: Shared mutable state — cls.project_dir and
cls.config_dir are shared across all test methods. Tests MUST NOT modify files."

All 17 tests in this class are read-only assertions, which is correct. But:

1. `test_scanner_detects_hexwise_deep_docs` at line 167 creates a NEW
   `ProjectScanner` and calls `scanner.scan()` again, which is harmless but
   inconsistent — if the class is truly read-only, why re-scan?
2. The `addClassCleanup` at line 74 handles cwd restoration even if a test
   raises, which is good practice.

**Assessment:** The shared state is intentional and well-managed. Not a real bug.

---

### Finding: TestHexwisePipeline mutates FakeGitHub per test — properly isolated
**File:** test_hexwise_setup.py:311-453
**Anti-pattern:** None (positive finding)
**Problem:** Unlike `TestHexwiseSetup`, the `TestHexwisePipeline` class uses
per-test `setUp`/`tearDown` with fresh temp directories and fresh `FakeGitHub`
instances. Each test gets its own mutable state. The `tearDown` even checks
`self.fake_gh._strict_warnings` and fails the test if any accumulated — a
defensive pattern that catches FakeGitHub fidelity issues.

---

### Finding: test_full_setup_pipeline has exact counts — good, not too loose
**File:** test_hexwise_setup.py:358-405
**Anti-pattern:** None (positive finding)
**Problem:** The assertions use exact counts: 3 milestones, 17 issues, 4 persona
labels, and every story ID from US-0101 through US-0209 is verified by name.
The docstring at line 359-373 explicitly documents the scope and differentiates
this test from test_lifecycle and test_golden_run. This is not a "green bar
addict" test — it verifies both quantity and identity.

---

### Finding: test_state_dump verifies content, not just structure (after BH23-111 fix)
**File:** test_hexwise_setup.py:428-452
**Anti-pattern:** None (positive finding, previously was Green Bar Addict)
**Problem:** The comment "BH23-111: Verify content, not just structure" at line
442 flags that this test was upgraded. It now checks that specific label names
exist ("kanban:todo", "type:story", "priority:P0") and that milestone titles
contain expected project content. Before BH23-111, it only checked `len >= 13`.

---

## 5. test_sprint_analytics.py (455 lines)

### Finding: Tests use realistic but minimal data — appropriate for unit tests
**File:** test_sprint_analytics.py (all classes)
**Anti-pattern:** None (positive finding)
**Problem:** The test data is not trivially simple but also not bloated:

- `test_all_closed`: 3 issues with SP values [3, 5, 3], verifying total = 11.
- `test_partial_delivery`: 2 issues, one closed (5 SP) and one open (3 SP),
  verifying percentage = 62% (not just "less than 100%").
- `test_malformed_sp_labels_contribute_zero`: Tests "sp:abc", "sp:", "sp:3.5",
  and "sp:5" together, with a nuanced comment explaining that sp:3.5 extracts
  the leading integer 3 (intentional behavior).

---

### Finding: test_counts_review_events properly exercises the milestone exclusion
**File:** test_sprint_analytics.py:131-203
**Anti-pattern:** None (positive finding)
**Problem:** This test creates PRs in TWO milestones and verifies that only
Sprint 1 PRs are counted. The BH-002 comment explains the purpose. Reviews are
added via `gh pr review` (the FakeGitHub's `_pr_review` path), not by directly
injecting review data. This exercises more of the real code path.

---

### Finding: format_report test checks exact formatted values, not just "contains text"
**File:** test_sprint_analytics.py:290-326
**Anti-pattern:** None (positive finding)
**Problem:** `test_produces_valid_markdown` asserts specific formatted strings:
"16/16 SP (100%)", "avg 1.5 per story", "rusti: 3", "palette: 1". These are
precise enough to catch formatting regressions. `test_no_pr_data` verifies
the fallback messages "no PR data available" and "no persona data available".

---

### Finding: TestMainIntegration test_main_deduplicates_analytics_entry is a good guard
**File:** test_sprint_analytics.py:422-451
**Anti-pattern:** None (positive finding)
**Problem:** This test pre-creates an analytics.md with a Sprint 1 entry, runs
main(), and verifies: (a) output says "skipping", (b) the file still has exactly
1 occurrence of "### Sprint 1". This prevents duplicate entries on re-run.

---

## 6. test_sync_backlog.py (316 lines)

### Finding: Debounce/throttle logic is well-covered with state machine tests
**File:** test_sync_backlog.py:74-149
**Anti-pattern:** None (positive finding)
**Problem:** `TestCheckSync` covers 6 states of the debounce/throttle algorithm:
no change, first change (debounce), still changing (re-debounce), stabilized
(sync), revert (cancel), throttle block, and throttle expired. Each test builds
explicit state dicts and asserts both the return status and the mutation of the
state dict (e.g., `state["pending_hashes"]` is updated correctly). This is
thorough state-machine testing.

---

### Finding: test_do_sync_idempotent verifies count but not content stability
**File:** test_sync_backlog.py:192-202
**Anti-pattern:** Borderline Green Bar Addict
**Problem:** `test_do_sync_idempotent` runs `do_sync` twice and asserts
`count_after_first == count_after_second`. But it doesn't verify that the
issues themselves haven't changed — only that the count is stable. If the
second run modified existing issues (e.g., changed their labels or bodies),
this test wouldn't catch it.

**Counterpoint:** `test_do_sync_skips_preexisting_issues` (line 205) covers
the pre-existing issue case by checking that only 1 new issue was created
when US-0001 already exists. Together the two tests provide reasonable coverage.

---

### Finding: TestMain end-to-end tests verify the 3-run lifecycle correctly
**File:** test_sync_backlog.py:224-315
**Anti-pattern:** None (positive finding)
**Problem:** Three tests exercise the full main() lifecycle:
1. First run: debouncing (no issues created)
2. Second run: sync (issues created)
3. Third run: no_changes

This mirrors the real production usage pattern. Each test verifies both the
return status string AND the side effects (issue count, state file contents).

---

## 7. test_validate_anchors.py (299 lines)

### Finding: Tests cover all major operations but miss edge cases
**File:** test_validate_anchors.py (all classes)
**Anti-pattern:** Happy Path Tourist (mild)
**Problem:** The tests cover: namespace resolution, anchor definition scanning,
anchor reference scanning, end-to-end check mode, and fix mode. However, some
edge cases are absent:

1. **No test for duplicate anchor definitions.** What if two `# §mymod.func`
   comments exist in the same file? `find_anchor_defs` returns a dict keyed
   by anchor name, so the second definition silently overwrites the first.
   No test verifies this behavior.
2. **No test for anchors in non-standard locations.** The tests use the comment
   format `# §ns.name` and the HTML comment format `<!-- §ns.name -->`. But
   what about anchors inside docstrings, or multi-line comments? The production
   regex may or may not match these.
3. **No test for `main()` with `--check` flag** (only `--fix` and default are
   tested in test_verify_fixes.py).

---

### Finding: test_all_mapped_files_exist is a live filesystem assertion
**File:** test_validate_anchors.py:38-41
**Anti-pattern:** None (positive finding, but fragile)
**Problem:** `test_all_mapped_files_exist` iterates every entry in
`NAMESPACE_MAP` and asserts the mapped file exists on disk. This is a structural
integrity test that catches stale namespace mappings (e.g., a file was renamed
but the map wasn't updated). However, it depends on the test being run from
within the giles repository with the correct working directory. If run from a
different location, it would fail with misleading errors.

---

### Finding: TestFixMode tests are properly assertive
**File:** test_validate_anchors.py:209-296
**Anti-pattern:** None (positive finding)
**Problem:** Fix-mode tests verify:
- Anchor comment is inserted (content check)
- Anchor is inserted ABOVE the definition (line-ordering check)
- Existing anchors are not duplicated (idempotency)
- Markdown headings get `<!-- -->` format anchors
- Constants (CONST = 42) are handled correctly
- Unfixable references (symbol doesn't exist) return 0

These are well-targeted and assertion-rich.

---

## 8. test_sprint_teardown.py (639 lines)

### Finding: Tests use real filesystem operations — no excessive mocking
**File:** test_sprint_teardown.py (all classes)
**Anti-pattern:** None (positive finding)
**Problem:** Every test class creates actual temp directories with real symlinks,
real files, and real directory structures. The teardown code uses real file
operations (symlink creation, file removal, directory cleanup). The only mock
in the entire file is for `subprocess.run` (git commands) in
`TestGitDirtyCheck`, and `builtins.input` in the interactive confirmation tests.
This is the opposite of "Mockingbird" — these tests exercise the real code paths.

---

### Finding: TestGitDirtyCheck mocks subprocess.run with a side_effect function
**File:** test_sprint_teardown.py:525-634
**Anti-pattern:** Borderline Mockingbird
**Problem:** The `test_dirty_files_block_without_force` test (line 545) patches
`subprocess.run` globally with a `side_effect` function that returns canned
results for `git` commands. This means the test verifies that `main()` handles
the git output correctly, but it doesn't verify that `main()` constructs the
correct `git diff` command. If someone changed the git command to
`git status --porcelain` instead of `git diff`, the mock would still return
the same canned output and the test would still pass.

However, this is an acceptable trade-off since the alternative (real git
operations) would require setting up a full git repo in every test case, which
the other test classes already do.

---

### Finding: Interactive confirmation tests are thorough
**File:** test_sprint_teardown.py:273-327
**Anti-pattern:** None (positive finding)
**Problem:** `TestRemoveGenerated` tests all interactive paths: force mode
(removes all), interactive yes/no, and interactive "all" (removes remaining).
The tests in test_verify_fixes.py at line 782-871 extend this further with
mixed yes/no, empty input (treated as no), and the "a" (all) shortcut.
Together these provide complete coverage of the interactive prompt logic.

---

### Finding: Cascading directory removal test is correctly structured
**File:** test_sprint_teardown.py:364-373
**Anti-pattern:** None (positive finding)
**Problem:** `test_deepest_first_cascading_removal` creates a 3-level deep
directory structure (sprint-config/team/history), calls `collect_directories`
to get the removal order, then calls `remove_empty_dirs` and asserts all 3
directories were removed. The assertion `count == 3` combined with
`assertFalse(self.config_dir.exists())` verifies both the count and the
actual filesystem state.

---

## Summary of Findings

### Genuine Issues (ordered by severity)

| # | File | Finding | Anti-pattern | Severity |
|---|------|---------|-------------|----------|
| 1 | test_property_parsing.py:224-242 | `_yaml_safe` dangerous-chars predicate missing 4 production conditions (comma, newline, CR, whitespace) | Paper Tiger / Stale Mirror | **HIGH** — property test gives false confidence |
| 2 | test_verify_fixes.py:1015-1150 | 7 scripts have argparse-only "main() integration tests" that test nothing beyond `--help` | Happy Path Tourist | MEDIUM |
| 3 | test_verify_fixes.py:1872-1942 | print_dry_run tests assert "no crash" but never inspect output | Green Bar Addict | MEDIUM |
| 4 | test_property_parsing.py:196-219 | Hand-rolled unescaper in roundtrip test risks tautological agreement | Borderline Rubber Stamp | LOW |
| 5 | test_verify_fixes.py:1258-1351 | Gate test counts `module.main()` calls in source but cannot distinguish argparse from real tests | Paper Tiger | LOW |
| 6 | test_sync_backlog.py:192-202 | Idempotency test checks count stability, not content stability | Borderline Green Bar Addict | LOW |
| 7 | test_validate_anchors.py | No tests for duplicate anchor definitions or non-standard anchor locations | Happy Path Tourist (mild) | LOW |

### Positive Findings

The test suite is generally mature and well-hardened after 22+ passes of bug hunting:

- **test_bugfix_regression.py**: BH-series regression tests have specific, targeted assertions that test the actual fixed behavior.
- **test_hexwise_setup.py**: Shared state is explicitly documented and properly managed; the pipeline test has exact-count assertions.
- **test_sprint_analytics.py**: Tests use realistic data, verify milestone exclusion, and check precise formatted output strings.
- **test_sync_backlog.py**: Debounce/throttle state machine is exhaustively covered with 6 state transitions.
- **test_sprint_teardown.py**: Uses real filesystem operations throughout — minimal mocking.
- **test_property_parsing.py**: Hypothesis strategies are well-tuned with good max_examples counts and explicit @example corner cases.
- **test_verify_fixes.py**: BH regression tests are NOT rubber stamps — they assert on the specific behavior that was broken.
