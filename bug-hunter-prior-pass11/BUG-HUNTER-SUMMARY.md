# Bug Hunter Pass 11 — Summary

> Fresh adversarial legacy review | 2026-03-15

## Headline

39 findings across 3 audit phases. The codebase is in good shape after 10 prior passes — what remains are structural test quality issues and cross-script interaction bugs that individual passes couldn't see. The biggest theme: **tests that verify mock behavior rather than production behavior**, creating false confidence around the most critical code paths (release gating, monitoring, state sync).

## By the Numbers

| Metric | Value |
|--------|-------|
| Tests before | 546 pass, 0 fail, 0 skip |
| Lint before | Clean (477 anchors resolved) |
| Doc claims checked | 112 (102 passed, 10 failed) |
| Punchlist items | 39 |
| High severity | 6 |
| Medium severity | 17 |
| Low severity | 16 |

## Severity Breakdown

### High (6) — Fix first

| ID | Title | Category |
|----|-------|----------|
| BH-P11-004 | Kanban transitions documented but not enforced | doc-drift |
| BH-P11-050 | `test_skips_missing_file` has zero assertions | assertion-free |
| BH-P11-051 | Golden snapshots silently degrade to warnings | weak-test |
| BH-P11-052 | `gate_stories` tests are mock-returns-what-you-assert | mock-abuse |
| BH-P11-053 | `gate_ci` tests are mock-returns-what-you-assert | mock-abuse |
| BH-P11-054 | FakeGitHub `--jq` never evaluated | mock-abuse |

### High (code bugs from Phase 3 — also fix first)

| ID | Title | Category |
|----|-------|----------|
| BH-P11-100 | `do_release` rollback silently swallows failures | logic-bug |
| BH-P11-101 | `get_linked_pr` merged-PR selection is order-dependent | logic-bug |
| BH-P11-102 | `populate_issues` bypasses `gh_json` concatenation fix | logic-bug |
| BH-P11-103 | `populate_issues` raw `json.loads` without type validation | error-handling |

### Medium (17) — Fix in batches

Themes: missing `main()` integration tests (4), mock-abuse / fidelity gaps (4), logic bugs (5), doc-drift (3), boundary/error handling (1).

### Low (16) — Address as cleanup

Themes: missing minor tests (4), duplicate code (1), cosmetic logic bugs (5), security edge cases (1), low-impact UX issues (5).

## Pattern Analysis

### Pattern 1: Mock-Returns-What-You-Assert (7 items)

BH-P11-052, 053, 054, 059, 060, 063, and partially 051.

**Root cause:** Tests for critical functions (gate_stories, gate_ci, check_ci, check_prs) patch `gh_json` or `subprocess.run` to return pre-shaped data, then verify the function formats the data correctly. They never verify the function constructs the RIGHT query. If the production code dropped a milestone filter, a branch filter, or a state filter, every test would still pass.

**Fix strategy:** For each mock-abuse test, add one assertion on `mock.call_args` to verify the query contains the expected filter parameters. This is a low-effort, high-value fix — one line per test.

### Pattern 2: Bypassing `gh_json` (3 items)

BH-P11-102, 103, 104.

**Root cause:** The BH-001 fix from pass 10 added incremental JSON decoding to `gh_json()` to handle concatenated paginated output (`[...][...]`). But three call sites (`get_milestone_numbers`, `get_existing_issues`, `get_linked_pr`) still call `gh()` directly + `json.loads()`, completely bypassing that fix. These are ticking time bombs — they'll break when any repo has enough milestones/issues/timeline events to trigger pagination.

**Fix strategy:** Replace all three with `gh_json()` calls. This is a safe, mechanical refactor.

### Pattern 3: Missing `main()` Integration Tests (5 items)

BH-P11-055, 056, 057, 058, 061.

**Root cause:** Scripts have good unit tests for individual functions but no test exercises `main()` end-to-end. The orchestration logic — arg parsing, config loading, error handling, output — is untested. Bugs in how functions are called together won't be caught.

**Fix strategy:** One integration test per script. Use the established pattern from `test_sprint_analytics.py::TestMainIntegration` as a template.

### Pattern 4: Doc-Code Drift on Process Rules (3 items)

BH-P11-004, 005, 006.

**Root cause:** `kanban-protocol.md` describes transition rules, WIP limits, and review round limits in imperative language ("can repeat at most 3 times") but these are LLM behavioral guidelines, not programmatic constraints. The docs read like enforced rules but the code does nothing.

**Fix strategy:** Add clarifying language to kanban-protocol.md: "These rules are process guidelines for the AI team personas, not programmatically enforced constraints."

## Recommended Fix Order

### Batch 1: Quick wins (1 hour)
1. BH-P11-004/005/006 — Doc clarification (3 items, text-only fix)
2. BH-P11-050 — Add assertion to assertion-free test (1 line)
3. BH-P11-051 — Golden test: `self.skipTest()` when recordings absent
4. BH-P11-108 — `max_story = "none"` when `max_rounds == 0`
5. BH-P11-109 — Strip cells before separator check

### Batch 2: gh_json migration (30 min)
6. BH-P11-102/103/104 — Replace `gh()` + `json.loads()` with `gh_json()`

### Batch 3: Test quality upgrades (1 hour)
7. BH-P11-052/053/063 — Add `call_args` assertions to mock-abuse tests
8. BH-P11-055-058 — Add `main()` integration tests for 4 scripts

### Batch 4: Code fixes (1 hour)
9. BH-P11-100 — Rollback return code checking + user warnings
10. BH-P11-101 — Break after finding merged PR (or sort by merged_at)
11. BH-P11-105 — Add `'` and `"` to `_yaml_safe` sensitive chars
12. BH-P11-106 — Exclude `[` in next-section regex lookahead
13. BH-P11-107 — Lazy import + traceback logging for sync exceptions

### Batch 5: Cleanup (as time allows)
14. BH-P11-062 — Extract shared MockProject
15. BH-P11-059/054 — FakeGitHub fidelity (jq, search)
16. Remaining Low-severity items

## What This Pass Did NOT Find

After 10 prior passes (100+ fixes), the codebase is surprisingly clean in these areas:
- **TOML parser:** 14/14 doc claims pass. Edge cases well-tested.
- **Release gate pipeline:** 16/16 doc claims pass. All 5 gates have positive and negative tests.
- **Sprint teardown:** 6/6 claims pass. Symlink safety well-tested.
- **Backlog sync:** 7/7 claims pass. State machine thoroughly tested.
- **Anchor validation:** 7/7 claims pass. Both check and fix modes covered.
- **Zero tautological assertions** found across 546 tests.
- **Zero commented-out tests** or explicit skips.
