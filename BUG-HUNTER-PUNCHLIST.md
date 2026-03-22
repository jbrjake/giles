# Bug Hunter Punchlist — Pass 39

> Generated: 2026-03-21 | Project: giles | Baseline: 1184 pass, 0 fail, lint-clean
> Focus: Systemic adversarial review of inter-component seams — zero trust

## Summary

| Severity | Open | Resolved | Closed |
|----------|------|----------|--------|
| HIGH     | 0    | 0        | 0      |
| MEDIUM   | 0    | 5        | 2      |
| LOW      | 0    | 4        | 3      |
| INFO     | 0    | 0        | 1      |

---

## Open

None — all 16 items resolved or closed.

---

## Resolved

| ID | Title | Severity | Test |
|----|-------|----------|------|
| BH39-001 | populate_issues dedup filter drops custom-pattern story IDs | MEDIUM | test_returns_custom_pattern_ids |
| BH39-100 | tracking-formats.md stale claim about external sync logging | MEDIUM | (doc fix) |
| BH39-103 | sync_tracking leaves stale metadata on regressed stories | MEDIUM | (documented as expected behavior) |
| BH39-201 | check_prs() missing --limit truncates at 30 | MEDIUM | TestBH39_201_CheckPrsLimit |
| BH39-202 | sprint_analytics review rounds --search undercount | MEDIUM | TestComputeReviewRounds (existing) |
| BH39-101 | assign_dod_level non-atomic write_tf | LOW | TestBH39_101_AssignDodLevelAtomicWrite |
| BH39-104 | lock_story dead code — no deprecation note | LOW | (docstring fix) |
| BH39-207 | find_milestone missing per_page=100 | LOW | (API efficiency fix) |
| BH39-208 | check_milestone missing isinstance guard | LOW | TestBH39_208_CheckMilestoneTypeGuard |

---

## Closed (won't fix)

| ID | Title | Severity | Reason |
|----|-------|----------|--------|
| BH39-002 | Non-story issues get junk tracking files | MEDIUM | Architectural — would need label filter changing sync semantics. Current behavior consistent between kanban.py and sync_tracking.py. |
| BH39-003 | smoke_test.write_history type annotation says str, callers pass Path | LOW | Cosmetic — Path(Path_obj) works fine. No runtime impact. |
| BH39-102 | SPRINT-STATUS.md non-atomic writes | LOW | Display-only file, phase separation makes concurrent access extremely unlikely. |
| BH39-200 | gh_json pagination could merge error dict into list | MEDIUM | gh CLI stops on HTTP errors, preventing interleaved error pages. Theoretically possible but practically prevented by gh behavior. |
| BH39-203 | Dead isinstance(linked, dict) branch in sync_tracking | LOW | Harmless safety net — jq filter wraps in array so dict branch never fires. No functional impact. |
| BH39-204 | _esc() missing \b\f escape for TOML spec compliance | LOW | Round-trip is correct because backslash is escaped first. Only cosmetic TOML spec violation for control chars. |
| BH39-209 | Hook protocol question — plain text not JSON | INFO | Verified correct — all hooks use plain text consistently. Not a bug. |

---

## Pattern Blocks

### PATTERN-39-A: Missing API limits / guards
**Items:** BH39-201, BH39-207, BH39-208
**Root cause:** When new code is added that calls GitHub API (check_prs, find_milestone), it doesn't always inherit the defensive patterns (--limit, per_page, isinstance guard) used by similar calls elsewhere. Each call site was written independently.
**Lesson:** When adding a new gh_json call, check existing calls in the same module for --limit, isinstance guard, and warn_if_at_limit patterns. Copy the defensive posture.

### PATTERN-39-B: Doc/code semantic drift on behavior changes
**Items:** BH39-100, BH39-103, BH39-104
**Root cause:** When behavior changes (adding transition logging to sync paths, moving from lock_story to lock_sprint, accepting state regression), the documentation and docstrings weren't updated to reflect the new reality.
**Lesson:** When modifying component behavior at a seam boundary, grep the codebase for documentation of the old behavior. This is the same pattern as PATTERN-38-A from the prior pass.

### PATTERN-39-C: Dedup filter inconsistency
**Items:** BH39-001, BH39-002
**Root cause:** extract_story_id() has a broad fallback (sanitized slug) but consumers filter its output inconsistently. populate_issues only accepted [A-Z]+-\d+ (too strict), while kanban.py only rejected "UNKNOWN" (more permissive). The contract between producer and consumer was implicit.
**Lesson:** When a function has multiple output paths (standard match vs fallback), document the contract for consumers: which outputs should they accept/reject?
