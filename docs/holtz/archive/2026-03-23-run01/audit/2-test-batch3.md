# Test Audit — Batch 3: Core Production Modules

**Auditor:** Holtz
**Date:** 2026-03-23
**Files:** test_pipeline_scripts.py, test_kanban.py, test_sprint_runtime.py, test_sync_backlog.py
**Total tests:** 475

---

## tests/test_pipeline_scripts.py
**Tests:** 166
**Red flags:** 1
**Anti-patterns found:** Permissive validator (minor, localized)
**Details:**

This is a strong test file. Assertions are specific and value-checking throughout. Highlights:

- **Team Voices:** Tests extract specific persona names, verify quote content (e.g., "type system" substring), check section context, verify continuation line joining, and test empty-quote filtering. Good edge coverage with empty dirs and empty quotes (BH33-006).
- **Traceability:** Tests both gap detection (synthetic untested story) and complete coverage (Hexwise fixture). `format_report` test verifies rendered output includes story IDs and titles, not just structure.
- **Test Coverage:** Tests all 4 language detection patterns (Rust, Python, JS, Go), including async Rust variants (tokio, async_std). Fuzzy matching test (TC-001 to test_tc_001_parse_hex) verifies the actual matching logic, not just counts. The "no actual tests" case verifies `planned_ids == missing_ids`, a proper set equality check.
- **Epic Management:** Parse, add, remove, reorder, renumber all tested with real fixture mutations. Edge cases: empty file parse, duplicate add raises ValueError, nonexistent remove returns False, renumber preserves headings but updates table rows, word-boundary renumber (US-01 vs US-0100), code block skipping (BH29-002). Round-trip contract test (AC format -> populate_issues parse) is particularly good.
- **Saga Management:** Parse, update allocation, update epic index, update team voices. Blank-line accumulation regression test (BH27-006) is a real bug hunter. Malformed file test verifies graceful degradation.
- **TOML Parser:** Comprehensive edge cases -- empty input, malformed quotes, multiline arrays, inline comments, booleans, integers, nested sections, duplicate sections, escaped backslash before quote, escaped quote in array, unterminated array (ValueError), single-quoted strings preserving # and containing double quotes, unquoted values, mixed quote arrays, _split_array internal function directly tested.
- **CI Generation:** All 4 supported languages plus unsupported (Haskell with TODO comment). YAML structure validation test (BH24-007) checks top-level keys, indentation consistency, job structure, and step entries without importing a YAML parser -- a smart approach.
- **Scanner Heuristics:** Python project fixture tests 15+ detection methods with specific value/confidence assertions. Minimal project fixture tests all the same methods return None/empty/zero-confidence. Good negative coverage.
- **Validate Project:** 7 negative tests (missing file, invalid TOML, too few personas, Giles-doesn't-count, missing persona file, missing TOML key, empty rules, no milestones) plus a sanity-check valid config.

**One minor concern:** `test_python_ci_yaml`, `test_node_ci_yaml`, `test_go_ci_yaml` check for keyword presence (`assertIn("pip install", yaml)`, `assertIn("npm", yaml)`) rather than structural correctness. This is borderline **permissive validator** -- but the separate `test_generated_yaml_has_valid_structure` test compensates with structural checks (top-level keys, indentation, job structure). The concern is that a language-specific test could pass even if the generated YAML is structurally broken, as long as the keywords appear somewhere. The structural test only runs for Python. Net: minor, well-compensated.

---

## tests/test_kanban.py
**Tests:** 87
**Red flags:** 0
**Anti-patterns found:** None
**Details:**

This is the strongest test file in the batch. The kanban state machine is critical infrastructure and the tests treat it that way.

- **Tracking File I/O:** Round-trip tests verify ALL fields (12 fields checked in test_round_trip). Comma-in-title (BH23-200) and empty-field round-trips are real edge cases that catch serialization bugs.
- **Transition Table:** Comprehensive: 6 legal transitions, 7 illegal transitions (including specific paths like dev->integration, dev->done), same-state noop, invalid state names. Crucially, `test_dev_to_integration_blocked` checks that the error message mentions "review" -- testing the UX, not just the boolean.
- **Preconditions:** 11 tests covering all gate conditions. Both positive and negative cases for each transition. Tests like `test_dev_to_review_requires_implementer` verify the error message contains "implementer" -- assertion on content, not just existence.
- **Atomic Write:** Tests file creation, no .tmp residue, and exception safety (BH22-055 -- verifies original file is untouched when write_tf raises OSError). This is real failure-mode testing.
- **File Locking:** Acquire/release without deadlock, lock file creation, cleanup verification, and a genuine concurrent lock serialization test using threads (BH23-114) that verifies ordering.
- **Find Story:** Standard lookup, missing story returns None, filename slug matching, case-insensitive search, and prefix collision avoidance (US-0042 vs US-00420). Multiple-match warning test uses stderr capture.
- **Transition Command (do_transition):** This is where the tests really shine. Tests verify: (1) local state update + exact label swap args on GitHub, (2) revert on GitHub failure, (3) double-fault restoration (both gh sync AND rollback fail -- tf.status still restored), (4) double-fault with real forward write (BH37-008 -- proves disk state has "design" while memory is restored to "todo"), (5) done transition closes issue, (6) close-before-label ordering (BH28-001), (7) close failure prevents stale kanban:done label, (8) transition log written/appended/rolled-back on failure, (9) review round escalation blocks after 3 cycles, (10) force override works.
- **WIP Limits:** Per-persona dev WIP, cross-persona independence, force override, review WIP at limit 2, review WIP per-reviewer independence, review WIP under limit, integration WIP team-wide at limit 3, integration WIP team-wide independence, integration WIP under limit. Exhaustive boundary testing.
- **Assign Command:** Revert on GitHub failure, implementer assignment with persona label and body update, reviewer-only assignment, both-assigned, fresh issue (no header), re-assign (header already present), skips body update when already assigned.
- **Sync Command:** Legal transition accepted, illegal transition warned+unchanged, new story creation, closed issue -> done, stale label override, local-absent warning, malformed title skipping, prune removes orphaned file, prune=False keeps+warns.
- **Update Command:** PR/branch update, None fields skipped, no-change optimization (mtime check), immutable field protection (path, story, sprint, status all rejected).
- **Status Command:** Board rendering with multiple states, assignee names visible, multiple-stories grouping, nonexistent sprint, empty stories dir.
- **CLI:** Exit code 2 on no command, --help shows subcommands, main exits 1 without config.

No anti-patterns detected. Assertions are specific and value-checking. Error paths are thoroughly covered. The double-fault tests are exemplary -- they test failure scenarios that many test suites never consider.

---

## tests/test_sprint_runtime.py
**Tests:** 203
**Red flags:** 1
**Anti-patterns found:** Permissive validator (minor, localized)
**Details:**

Another strong file covering check_status, bootstrap_github, populate_issues, sync_tracking, and update_burndown.

- **check_ci:** Tests no-runs, all-passing, failing-run (with action content verification), contract test for argument ordering (BH37-014), log fetch uses correct database ID.
- **check_prs:** No PRs, approved PR (with contract test for argument ordering), needs-review PR, mixed states with specific count assertions and action content.
- **bootstrap_github:** create_label verifies color/description passed (BH21-007), error handling verifies warning message content. Three idempotency tests (static labels, milestones, persona labels) verify counts don't change on second call. Sprint number collection tests heading extraction, filename fallback, and no-heading/no-number warning.
- **populate_issues:** format_issue_body tests full story (AC checkboxes, epic, saga, deps, test cases) and minimal story (no AC, no deps, no user story). Missing milestone still creates issue. get_existing_issues tests standard IDs, custom patterns, empty response, and gh failure. _infer_sprint_number tests heading match, prose-only fallback, filename digits, no-number default, content passthrough, multiple headings. _most_common_sprint tests clear winner, tie, empty, single, all-same.
- **find_milestone boundary:** Word-boundary tests (Sprint 1 vs Sprint 10, Sprint 10 vs Sprint 1, Sprint 1 vs Sprint 1a/11, Sprint 100 vs Sprint 10), no milestones, non-list response, leading zero (Sprint 07 matches find_milestone(7)).
- **get_linked_pr:** Correct story match, no-match returns None, slug match ignores sprint prefix, timeline API (linked PR, merged PR, latest-merged preference, no-match fallback, API error fallback), word-boundary (no substring match, exact match, end-of-branch match, longer ID no false positive), API failure warning, dict normalization.
- **extract_sp:** 13 tests covering label dict, label string, body text, body table, missing, lowercase, label priority, analytics table format, label with space, label uppercase, story points table, word-boundary adversarial tests (wasp, BSP).
- **check_branch_divergence:** No branches, low (ignored), medium, high, boundary values (10 not medium, 11 is medium, 20 is medium not high, 21 is high), multiple branches, API error, list response warning. FakeGitHub-backed duplicates for high, medium, no drift, unknown branch.
- **check_direct_pushes:** No pushes, pushes found, multiple capped at 3, API error. FakeGitHub-backed tests with jq filtering (merge commits excluded), no-jq fallback, empty commits, API error.
- **sync_one:** Closed issue updates status, label sync, PR number updated, no changes when in sync, closed sets completed date, sprint mismatch updates sprint, disk round-trip (BH23-116). Transition log: appended on change, survives round-trip, no log when unchanged. GitHub authoritative: no gh calls on disagreement (mock_gh_json.assert_not_called()).
- **create_from_issue:** Basic creation, creation with PR, creation for closed issue.
- **write_burndown:** Creates file with correct content (title, planned/completed SP, story IDs), zero SP handled. update_sprint_status: patches section, appends when missing, last section, no trailing newline, skips missing file (no creation).
- **kanban_from_labels:** Valid state, invalid falls to todo, invalid closed falls to done, no label open/closed, None in labels, non-dict/non-str labels, stale label for closed issue, string label format, multiple labels first kanban wins.
- **Tracking I/O:** Round-trip with all fields, missing fields default, no frontmatter, colon-in-title. YAML escaping: colon, bracket start, hash, no special chars (verifies no unnecessary quoting in raw file), existing quotes, special branch, empty string, all special start chars, dash-space, question-space, trailing colon, single/double quote start, boolean keywords. Backslash and backslash+quote combo round-trips.
- **Slug generation:** Basic, special chars removed, empty title, all special chars, similar titles produce different slugs.
- **build_rows:** Empty, all closed, mixed open/closed with SP, missing SP defaults to zero, tracking metadata merge.

**One minor concern:** `test_happy_path_with_sp` in TestCheckMilestone asserts `any("3/5" in line for line in report)` and then does a weaker check: `self.assertTrue("10" in report_text or "23" in report_text)`. The `or` makes this a **permissive validator** -- it passes if either the done SP (10) or total SP (23) appears anywhere in the report, without pinning which is which. If the code swapped done/planned totals, this test would still pass. The fix would be to assert "10 done" and "23 planned" (or whatever the actual format is) independently. This is a single test out of 203; the rest are tight.

---

## tests/test_sync_backlog.py
**Tests:** 19
**Red flags:** 0
**Anti-patterns found:** None
**Details:**

Compact and well-focused file for the backlog auto-sync engine.

- **Hash Functions:** Single file hashing verifies exact SHA-256 against manually computed expected value. Hash-change-on-edit verifies before/after differ. Missing file gracefully returns empty dict.
- **State File:** Missing returns defaults, round-trip equality, corrupt JSON returns defaults.
- **Check Sync (debounce/throttle):** This is the algorithm core and it is thoroughly tested. No-change returns no_changes. First change triggers debounce (sets pending, no sync). Still-changing re-debounces (updates pending). Stabilized triggers sync. Revert cancels pending (clears back to no_changes). Throttle blocks sync when recent. Throttle expired allows sync. Each test verifies both `result.status` and `result.should_sync` -- two independent assertions per test confirming the algorithm's dual output.
- **do_sync:** Creates milestones and issues (counts match FakeGitHub state). Idempotent (second call doesn't duplicate). Skips pre-existing issues (BH23-121 -- pre-populates US-0001, verifies only US-0002 created).
- **main() end-to-end:** Three-phase test: first run debounces (no issues created), second run syncs (issues created), third run reports no_changes. These exercise the full state machine through main() with a real filesystem and FakeGitHub.

No anti-patterns. The debounce/throttle tests are a textbook example of testing a state machine: each test isolates a single transition and verifies both output signals.

---

## Summary

| File | Tests | Red flags | Verdict |
|------|-------|-----------|---------|
| test_pipeline_scripts.py | 166 | 1 | DONE_WITH_CONCERNS |
| test_kanban.py | 87 | 0 | DONE |
| test_sprint_runtime.py | 203 | 1 | DONE_WITH_CONCERNS |
| test_sync_backlog.py | 19 | 0 | DONE |

**Overall: DONE_WITH_CONCERNS**

The concerns are minor and localized:

1. **test_pipeline_scripts.py:** Language-specific CI tests check keyword presence only (e.g., `assertIn("go test", yaml)`), relying on a separate Python-only structural test for YAML validity. If the Go or Node generator produced structurally broken YAML that still contained the right keywords, those tests would pass. Low risk because the generators share a common template.

2. **test_sprint_runtime.py:** `test_happy_path_with_sp` uses an OR assertion (`"10" in text or "23" in text`) that would pass even if done/planned SP totals were swapped. A single test out of 203; the surrounding SP tests are precise.

Neither concern indicates a systematic weakness. These are 475 tests across 4 files testing critical production infrastructure (TOML parser, kanban state machine, GitHub sync, sprint init, burndown, backlog sync), and the overwhelming majority use specific, value-checking assertions with both positive and negative cases. The kanban double-fault tests, WIP limit boundary tests, TOML parser edge cases, and sync_backlog state machine tests are particularly well-crafted.
