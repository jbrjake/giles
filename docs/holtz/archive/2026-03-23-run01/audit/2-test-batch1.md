# Test Batch 1 Audit (Prediction 8)

Audited: `tests/test_new_scripts.py`, `tests/test_sprint_analytics.py`, `tests/test_validate_anchors.py`

---

## tests/test_new_scripts.py
**Tests:** 38
**Red flags:** 1
**Anti-patterns found:** Happy path tourist (minor), Rubber stamp (one instance)
**Details:**

This is a well-structured omnibus file covering 6 scripts across 6 test classes. Most tests are solid with specific value assertions and good edge coverage (BH-tagged regression tests, word-boundary false-positive checks, pipe escaping). Specifics:

**TestSmokeTest (8 tests):** Strong. Tests pass, fail, skip, timeout, nonexistent command, history append/create, and pipe escaping. All assertions check specific values (status strings, exit codes, line counts). The timeout test even verifies the error message content. No issues.

**TestGapScanner (13 tests):** Strong. Good boundary testing with BH29-003 and BH30-001 regression tests for false-positive substring matching. Tests both body-text and path-based entry point matching. Tests the "no gap" path and the "gap detected" path with specific report content checks. No issues.

**TestTestCategories (8 tests):** Mostly good. Tests classify by directory, name pattern, and default. The `test_analyze_with_dirs` test creates real files and checks counted values. The zero-test edge case is covered. No issues.

**TestRiskRegister (7 tests):** Good. Tests add, list, resolve, escalate, and nonexistent-resolve. Pipe roundtrip test (DA-021/022) is thorough -- verifies escaped pipes survive add/resolve/list cycle and checks field values. One minor concern: `test_add_risk_sanitizes_pipes` checks that a data line with "R1" exists (len == 1) but doesn't verify the row actually has correct column count -- it just checks one line matched, which is more of a structural check than a correctness check. Minor rubber stamp.

**TestAssignDodLevel (6 tests):** Good. Tests word boundary matching ("username" should NOT trigger "user"), case insensitivity, title vs body priority. These are real correctness checks.

**TestHistoryToChecklist (4 tests):** Good. Tests extraction with keyword matching, empty history, directory scanning, and missing directory. The extraction test checks both count and content of extracted items.

**Missing edge cases (minor):**
- `run_smoke` is never tested with a command that produces stdout/stderr to verify those are captured (only status/code are checked in most tests).
- `assign_levels()` (the function that actually writes dod_level to files) is never tested -- only the classifier is.
- `main()` functions for smoke_test, gap_scanner, test_categories, assign_dod_level, and history_to_checklist are untested.

---

## tests/test_sprint_analytics.py
**Tests:** 12
**Red flags:** 0
**Anti-patterns found:** None significant
**Details:**

This is a well-designed test file. Uses a purpose-built FakeGitHub mock that simulates the `gh` CLI at the subprocess level, which means the real JSON parsing and data flow in the source code is exercised -- not mocked away.

**TestExtractPersona (2 tests):** Simple but correct. Tests label extraction and no-persona case. Appropriate for a pure function.

**TestComputeVelocity (3 tests):** Strong. Tests 100% delivery, partial delivery, and malformed SP labels. The malformed test is particularly good -- it verifies the regex-based extraction behavior where `sp:3.5` extracts 3 (leading digits) while `sp:abc` and `sp:` contribute 0. Assertions check all four return fields.

**TestComputeReviewRounds (3 tests):** Strong. BH-002 tests cross-milestone filtering by creating PRs in Sprint 2 and verifying they're excluded. BH-006 creates PRs and reviews through the FakeGitHub's `gh pr create` / `gh pr review` path rather than injecting data directly. The zero-reviews edge case (BH-P11-108) checks that `max_story` is "none", which is a real correctness check against the source code line 127-128.

**TestComputeWorkload (3 tests):** Good. Tests per-persona counting, no-persona case, and cross-milestone filtering (BH23-123). Assertions check exact counts per persona.

**TestFormatReport (2 tests):** Checks specific strings in the formatted output including "16/16 SP (100%)", persona counts, and the "no PR data available" / "no persona data available" fallback text. These are correctness checks, not rubber stamps.

**TestMainIntegration (3 tests):** Thorough end-to-end test. Sets up FakeGitHub state, temp directories, kickoff files, patches sys.argv/stdout, and verifies:
1. Report content printed to stdout with exact SP values
2. analytics.md file creation with correct content
3. Exit code 1 when milestone not found
4. Dedup logic -- skips writing when sprint entry already exists

This file is solid. The FakeGitHub approach is a good middle ground -- it mocks at the subprocess boundary, not at the function level, so the real code path is exercised.

---

## tests/test_validate_anchors.py
**Tests:** 18
**Red flags:** 0
**Anti-patterns found:** None
**Details:**

This is a thorough test file covering all five public functions in validate_anchors.py.

**TestNamespaceMap (7 tests):** Tests resolution for shared scripts, skill scripts, SKILL.md files, reference docs, and agent templates. The `test_unknown_namespace_raises` verifies the error path. The `test_all_mapped_files_exist` test is a real-project integrity check -- it iterates every entry in NAMESPACE_MAP and asserts the file exists on disk. This is a valuable regression test against stale mappings.

**TestFindAnchorDefs (4 tests):** Tests Python function anchors, markdown heading anchors, multiple anchors, and the empty case. Each test creates a temp file with specific content and verifies exact anchor names and line numbers. The line-number assertions are meaningful -- they verify the parser counts lines correctly.

**TestFindAnchorRefs (5 tests):** Tests table cell refs (multi-ref single line), anchor-column refs, prose refs, empty case, and line-number accuracy. The `test_table_cell_refs` test verifies both refs are extracted in order from a single line, which exercises the regex iteration logic.

**TestCheckAnchors (4 tests):** End-to-end check mode tests. Creates source files with anchors and doc files with references, then tests: all-resolve, broken-ref detection, unknown-namespace detection, and unreferenced-anchor detection. Each test sets up a different scenario in a temp directory and checks specific error messages.

**TestFixMode (7 tests):** Tests the autofix functionality. Verifies: Python anchor insertion, correct placement above definition, skip-existing (idempotent), markdown heading fix, constant definition fix (BH23-120), unfixable symbol handling, and repeated-fix idempotency (BH33-004 -- no trailing newline accumulation). The placement test checks that the anchor comment appears on the line immediately above the `def` statement, which is a real correctness check.

No anti-patterns detected. Every test has meaningful assertions that verify correctness, not just structure. Edge cases and error paths are covered.

---

## Summary

| File | Tests | Red flags | Verdict |
|------|-------|-----------|---------|
| test_new_scripts.py | 38 | 1 | Solid, minor gaps in main() coverage and one near-rubber-stamp |
| test_sprint_analytics.py | 12 | 0 | Strong -- FakeGitHub approach keeps assertions real |
| test_validate_anchors.py | 18 | 0 | Thorough -- all public functions covered with edge cases |

**Status: DONE**

These three files are the strongest test files in the predicted batch. The FakeGitHub infrastructure in test_sprint_analytics.py is particularly well done -- mocking at the subprocess boundary instead of at the function level means the JSON parsing, filtering, and computation logic is genuinely exercised. The validate_anchors tests cover all five public API functions with temp-file-based scenarios that verify both happy and error paths. test_new_scripts.py covers the most ground (6 scripts) and the only real concern is that `main()` entry points and the `assign_levels()` write path are untested.
