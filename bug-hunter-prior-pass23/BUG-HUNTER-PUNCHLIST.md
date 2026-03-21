# Bug Hunter Punchlist — Pass 23 (Fresh Legacy Audit)

> Generated: 2026-03-19 | Project: giles | Baseline: 854 pass, 0 fail, 0 skip
> Method: Fresh adversarial audit — doc claims, test quality, code review
> Detail files: `audit/1-doc-claims.md`, `audit/2-test-quality.md`, `audit/3-code-audit.md`

## Summary

| Severity | Open | Resolved | Deferred |
|----------|------|----------|----------|
| CRITICAL | 0    | 0        | 0        |
| HIGH     | 4    | 0        | 0        |
| MEDIUM   | 17   | 0        | 0        |
| LOW      | 38   | 0        | 0        |

## Prioritized Action Items

### Tier 1 — Fix Now (HIGH)

| ID | Title | Category | Source |
|----|-------|----------|--------|
| BH23-001 | kanban.py update subcommand undocumented in all reference docs | doc/missing | Phase 1 |
| BH23-007 | kanban-protocol.md doesn't document update subcommand needed for dev preconditions | doc/missing | Phase 1 |
| BH23-011 | implementer.md doesn't tell agents to use kanban.py update for PR/branch | doc/missing | Phase 1 |
| BH23-101 | do_release happy path mocks 5 layers deep (Mockingbird) | test/mock-abuse | Phase 2 |

### Tier 2 — Fix Soon (MEDIUM)

| ID | Title | Category | Source |
|----|-------|----------|--------|
| BH23-002 | kanban-protocol.md claims 3-artifact updates, only 2 happen | doc/drift | Phase 1 |
| BH23-005 | sprint_teardown.py hardcodes docs/dev-team paths | doc/drift | Phase 1 |
| BH23-010 | sync_tracking.py status mutation overlaps kanban.py role | doc/drift | Phase 1 |
| BH23-012 | kanban-protocol.md Rules section incorrect about script acceptance | doc/drift | Phase 1 |
| BH23-013 | CLAUDE.md config tree mixes required vs runtime files | doc/drift | Phase 1 |
| BH23-100 | Green Bar Addict — import_guard test asserts module attrs exist | test/bogus | Phase 2 |
| BH23-103 | do_transition only tests 2 of 6 legal transitions | test/missing | Phase 2 |
| BH23-104 | do_sync tests use inconsistent label format (strings vs dicts) | test/missing | Phase 2 |
| BH23-112 | Golden run silently skips without recordings | test/fragile | Phase 2 |
| BH23-122 | FakeGitHub fidelity tests cover only 2 of 8+ handlers | test/missing | Phase 2 |
| BH23-200 | _yaml_safe doesn't quote comma-containing values | bug/logic | Phase 3 |
| BH23-201 | do_transition mutates caller's TF on rollback double-fault | bug/state | Phase 3 |
| BH23-204 | create_from_issue slug collision drops story ID prefix | bug/logic | Phase 3 |
| BH23-207 | sync_tracking.py doesn't acquire kanban locks | bug/state | Phase 3 |
| BH23-212 | get_existing_issues hard-fails on 500+ issues | design/inconsistency | Phase 3 |
| BH23-224 | update_team_voices doesn't sanitize markdown input | bug/security | Phase 3 |
| BH23-230 | do_update allows mutation of immutable TF fields (path, story) | bug/logic | Phase 3 |

### Tier 3 — Fix When Convenient (LOW)

| ID | Title | Category | Source |
|----|-------|----------|--------|
| BH23-003 | story-execution.md applies kanban label directly via gh pr edit | doc/drift | Phase 1 |
| BH23-004 | implementer.md hardcodes sprints_dir path | doc/drift | Phase 1 |
| BH23-006 | story-execution.md step 6 redundant with kanban.py transition done | doc/drift | Phase 1 |
| BH23-008 | CLAUDE.md parse_simple_toml doc omits float gap and literal strings | doc/drift | Phase 1 |
| BH23-009 | CLAUDE.md "four directories up" claim only applies to skill scripts | doc/drift | Phase 1 |
| BH23-102 | Inspector Clouseau — check_ci test checks mock call_args format | test/fragile | Phase 2 |
| BH23-105 | Rubber Stamp — config key tests check presence not values | test/shallow | Phase 2 |
| BH23-106 | Time Bomb — _hours() tests use wall clock time | test/fragile | Phase 2 |
| BH23-107 | gate_tests/build timeout not tested through validate_gates | test/missing | Phase 2 |
| BH23-108 | monitoring pipeline hardcodes SP values | test/fragile | Phase 2 |
| BH23-109 | Obsolete negative test for removed Confidence column | test/bogus | Phase 2 |
| BH23-110 | check_prs not tested with mixed review states | test/missing | Phase 2 |
| BH23-111 | test_state_dump checks structure not content | test/shallow | Phase 2 |
| BH23-113 | do_assign body-update not tested for edge cases | test/shallow | Phase 2 |
| BH23-114 | Lock contention never tested | test/shallow | Phase 2 |
| BH23-115 | _yaml_safe property tests miss numeric strings | test/missing | Phase 2 |
| BH23-116 | TestSyncOne never writes TF to disk | test/shallow | Phase 2 |
| BH23-117 | Traceability tests only check report structure | test/shallow | Phase 2 |
| BH23-118 | manage_epics remove_story not tested for missing ID | test/missing | Phase 2 |
| BH23-119 | Multiple tests use assertIsNotNone without content checks | test/shallow | Phase 2 |
| BH23-120 | fix_missing_anchors CONSTANT definition path untested | test/missing | Phase 2 |
| BH23-121 | sync_backlog do_sync not tested with pre-existing issues | test/missing | Phase 2 |
| BH23-123 | compute_workload not tested with mixed milestones | test/missing | Phase 2 |
| BH23-124 | full_pipeline label count bound too loose | test/shallow | Phase 2 |
| BH23-125 | check_atomicity 2-directory boundary not tested | test/missing | Phase 2 |
| BH23-126 | do_status output doesn't verify assignee names | test/shallow | Phase 2 |
| BH23-127 | do_release rollback never verified end-to-end | test/missing | Phase 2 |
| BH23-128 | hexwise_setup shares mutable state across tests | test/fragile | Phase 2 |
| BH23-202 | do_assign partial GitHub state on rollback | bug/state | Phase 3 |
| BH23-205 | frontmatter_value unescaping order may fail on backslash-quote | bug/logic | Phase 3 |
| BH23-210 | write_tf doesn't quote pr_number/issue_number fields | bug/logic | Phase 3 |
| BH23-211 | _first_error false positive exclusion may flag "error-handling" | bug/logic | Phase 3 |
| BH23-214 | renumber_stories replaces IDs in body text (cosmetic) | bug/logic | Phase 3 |
| BH23-217 | compute_review_rounds --search milestone filtering reliability | bug/logic | Phase 3 |
| BH23-219 | write_version_to_toml next-section regex excludes space-leading sections | bug/logic | Phase 3 |
| BH23-220 | gh() error messages may leak sensitive body content | bug/security | Phase 3 |
| BH23-225 | manage_epics.main accepts untrusted JSON without full sanitization | bug/security | Phase 3 |
| BH23-227 | setup_ci._yaml_safe_command doesn't escape internal double quotes | bug/logic | Phase 3 |
| BH23-228 | bootstrap_github milestone titles not sanitized for control chars | bug/security | Phase 3 |
| BH23-231 | check_status main catches only RuntimeError, not KeyError/TypeError | bug/error-handling | Phase 3 |
| BH23-232 | read_tf doesn't handle concurrent file deletion | bug/error-handling | Phase 3 |
| BH23-235 | do_release doesn't check for existing tag before creating | bug/error-handling | Phase 3 |
| BH23-236 | _unescape_toml_string missing \b, \f, \r escape handling | bug/logic | Phase 3 |

## Emerging Patterns

### PAT-23-001: kanban.py update subcommand invisible to agents
**Instances:** BH23-001, BH23-007, BH23-011
**Root Cause:** The `update` subcommand was added (BH22-113) but no reference docs were updated to mention it. All three ceremony/execution/agent docs reference the workflow gap without bridging it.
**Systemic Fix:** Add `kanban.py update` to kanban-protocol.md, story-execution.md, and implementer.md in a single doc pass.
**Detection Rule:** `grep -rL "kanban.py update" skills/sprint-run/references/ skills/sprint-run/agents/`

### PAT-23-002: Tests verify structure but not computed values
**Instances:** BH23-105, BH23-111, BH23-117, BH23-119, BH23-124, BH23-126
**Root Cause:** Many tests use `assertIn`, `assertIsNotNone`, `assertGreaterEqual` instead of exact value assertions. This pattern emerged from property-test and smoke-test contexts but leaked into functional tests where exact values are knowable.
**Systemic Fix:** Review each functional test: if the expected output is deterministic, assert the exact value. Reserve loose bounds for genuine non-determinism (timestamps, counts that depend on external state).

### PAT-23-003: Happy Path Tourist — untested state transitions
**Instances:** BH23-103, BH23-110, BH23-113, BH23-118, BH23-121
**Root Cause:** Kanban state machine, PR classification, and sync operations each have multiple distinct code paths, but tests only exercise 1-2 of them. The production code has if/elif chains with 3+ branches but only the first branch is tested.
**Systemic Fix:** For each function with N code paths, require at least N/2 test cases targeting different branches.

### PAT-23-004: Insufficient input sanitization at CLI/markdown boundaries
**Instances:** BH23-220, BH23-224, BH23-225, BH23-227, BH23-228
**Root Cause:** CLI arguments and markdown file content flow through to `gh` API calls, markdown output, and YAML serialization without consistent sanitization. Each module has its own ad-hoc escaping, but there's no centralized sanitization layer.
**Systemic Fix:** Create a `sanitize_for_markdown(s)` and `sanitize_for_gh_arg(s)` helper in validate_config.py, and use them consistently at all CLI→API and CLI→markdown boundaries.

### PAT-23-005: State mutation before confirmation of durability
**Instances:** BH23-201, BH23-202, BH23-207, BH23-230
**Root Cause:** Functions mutate shared state (TF objects, tracking files) before confirming the operation succeeded (GitHub sync, disk write). When the confirmation fails, rollback is attempted but may leave the shared object in an inconsistent state.
**Systemic Fix:** Prefer copy-on-write patterns — mutate a copy, then swap on success. For file I/O, the `atomic_write_tf` pattern is correct; apply the same discipline to in-memory TF objects.
