# Bug Hunter Punchlist — Pass 29 (Cross-Component Gap Analysis)

> Generated: 2026-03-21 | Project: giles | Baseline: 1133 pass, 0 fail
> Focus: Patterns in the gaps between components across 28 prior passes + 6 recon audits

## Summary

| Severity | Open | Resolved | Deferred |
|----------|------|----------|----------|
| HIGH     | 0    | 1        | 0        |
| MEDIUM   | 0    | 4        | 0        |
| LOW      | 0    | 2        | 0        |

---

## Tier 1 — Fix Now (HIGH)

| ID | Title | Category | Status | Commit | Validating Test |
|----|-------|----------|--------|--------|-----------------|
| BH29-001 | `_read_toml_key` doesn't unescape `\"` in scalar strings; test asserts the bug | bug/test-masks-bug | RESOLVED | pending | `test_read_toml_key_inline_comment_after_escaped_quote`, `test_read_toml_key_escaped_quote_with_bracket` |

---

## Tier 2 — Fix Soon (MEDIUM)

| ID | Title | Category | Status | Commit | Validating Test |
|----|-------|----------|--------|--------|-----------------|
| BH29-002 | `renumber_stories()` replaces story IDs inside fenced code blocks | bug/text-processing | RESOLVED | pending | `test_renumber_skips_code_blocks` |
| BH29-003 | `gap_scanner` entry point matching: substring false positives + silent git failure | bug/boundary-validation | RESOLVED | pending | `test_entry_point_substring_no_false_positive`, `test_entry_point_word_boundary_match`, `test_entry_point_path_match_in_body` |
| BH29-004 | `test_status_wip_limit_warning` test name claims nonexistent feature | test/name-mismatch | RESOLVED | pending | Renamed to `test_status_groups_multiple_dev_stories` |
| BH29-005 | `test_update_no_changes` docstring claims no-write verification without verifying | test/weak-assertion | RESOLVED | pending | Added mtime assertion |

---

## Tier 3 — Low Priority (LOW)

| ID | Title | Category | Status | Commit | Validating Test |
|----|-------|----------|--------|--------|-----------------|
| BH29-006 | `_yaml_safe()` doesn't check for `\t` tab characters | bug/roundtrip | RESOLVED | pending | `test_dangerous_chars_get_quoted` (updated), `test_frontmatter_value_roundtrip` |
| BH29-007 | `session_context._read_toml_string` regex rejects `\"` escapes | bug/parser-divergence | RESOLVED | pending | N/A (low-risk path, regex fix only) |

---

## Deferred (structural, not punchlist items)

These are documented design decisions or structural issues that require architectural changes:

| Finding | Why deferred |
|---------|-------------|
| FINDING-3: do_sync no per-story locks | Mitigated by callers using lock_sprint — convention-based, not enforced. Would require API redesign. |
| FINDING-4: sync_tracking accepts any state | Documented as intentional in CLAUDE.md. Two sync paths have different trust models by design. |
| FINDING-44/45: Non-atomic writes, no locking in manage_epics/sagas | Structural. Would require extracting atomic_write and locking into a shared utility. Risk is low in practice (single-user tool). |
| FINDING-6: sync_backlog deferred import error | Partially fixed. Error surfaces at sync time. Early warning would be nice but not critical. |

---

## Pattern Blocks

### PATTERN-29-A: Tests that assert wrong behavior

**Items:** BH29-001, BH29-004, BH29-005
**Root cause:** Tests written to describe current behavior rather than correct behavior.
The test suite validates the code against itself, creating a closed loop where both
sides agree on wrong answers. This is the most dangerous pattern because it actively
blocks future correctness work.
**Resolution:** All 3 items fixed. Tests now assert spec-correct behavior.

### PATTERN-29-B: Uncontrolled text boundaries

**Items:** BH29-002, BH29-003
**Root cause:** Text processing functions that use substring matching (`in` operator)
or regex without context awareness (code blocks, line boundaries). The `in` operator
is a recurring source of false positives across the codebase.
**Resolution:** Both items fixed. Word-boundary matching and code-block awareness added.
