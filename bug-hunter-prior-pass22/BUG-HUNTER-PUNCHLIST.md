# Bug Hunter Punchlist — Pass 22 (Post-Kanban State Machine)

> Generated: 2026-03-18 | Project: giles | Baseline: 839 pass, 0 fail, 0 skip
> Method: Fresh adversarial audit — doc consistency, test quality, adversarial code review
> Detail files: `audit/1-doc-claims.md`, `audit/2-test-quality.md`, `audit/3-code-audit.md`

## Summary

| Severity | Open | Resolved | Deferred |
|----------|------|----------|----------|
| HIGH     | 0    | 8        | 0        |
| MEDIUM   | 0    | 15       | 0        |
| LOW      | 0    | 17       | 0        |

## Prioritized Action Items

### Tier 1 — Fix Now (HIGH, blocks correct operation)

| ID | Title | Category | File |
|----|-------|----------|------|
| BH22-100 | lock_story holds stale fd after atomic rename | `bug/race` | `kanban.py:161` |
| BH22-110 | sync_tracking.py and kanban.py are unsynchronized dual-write paths | `bug/integration` | `kanban.py + sync_tracking.py` |
| BH22-004 | story-execution.md tells agents to do illegal review→done transition | `doc/inconsistency` | `story-execution.md:128` |
| BH22-112 | kickoff assign runs before tracking files exist | `bug/integration` | `ceremony-kickoff.md:257` |
| BH22-102 | do_transition rollback can fail uncaught, leaving inconsistent state | `bug/logic` | `kanban.py:258` |
| BH22-103 | do_assign partial-success leaves GitHub labels without local state | `bug/logic` | `kanban.py:285` |
| BH22-001 | kanban namespace missing from validate_anchors NAMESPACE_MAP | `doc/inconsistency` | `validate_anchors.py:23` |
| BH22-002 | CHEATSHEET.md references 4 stale sync_tracking anchors | `doc/stale` | `CHEATSHEET.md:130` |

### Tier 2 — Fix Soon (MEDIUM, latent bugs or thin coverage)

| ID | Title | Category | File |
|----|-------|----------|------|
| BH22-117 | create_from_issue vs do_sync produce different filenames for same issue | `bug/integration` | `sync_tracking.py:167` |
| BH22-109 | write_tf skips _yaml_safe on implementer/reviewer fields | `bug/logic` | `validate_config.py:1088` |
| BH22-107 | sprint=0 silently discarded by or-based resolution | `bug/logic` | `kanban.py:464` |
| BH22-101 | atomic_write_tf mutates tf.path as visible side effect | `bug/race` | `kanban.py:143` |
| BH22-115 | do_transition done: label edited but close fails → inconsistent state | `bug/logic` | `kanban.py:251` |
| BH22-104 | _PERSONA_HEADER_PATTERN replaces all matches; no-match silent | `bug/logic` | `kanban.py:222` |
| BH22-106 | lock_story requires file to exist — undocumented constraint | `bug/logic` | `kanban.py:168` |
| BH22-108 | _yaml_safe doesn't quote purely numeric strings | `bug/logic` | `validate_config.py:905` |
| BH22-005 | Contradictory source-of-truth claims across 4 files | `doc/inconsistency` | multiple |
| BH22-007 | story-execution.md design→dev missing tracking file update step | `doc/inconsistency` | `story-execution.md:61` |
| BH22-050 | _issue() test helper hardcodes state:"open", masking closed-issue logic | `test/thin` | `test_kanban.py:426` |
| BH22-051 | test_assign_implementer doesn't verify body-update was issued | `test/thin` | `test_kanban.py:373` |
| BH22-053 | No test for reviewer-only assign path | `test/missing` | `test_kanban.py:346` |
| BH22-055 | atomic_write_tf exception-safety path untested | `test/missing` | `test_kanban.py:187` |
| BH22-060 | No round-trip test for empty/whitespace tracking file fields | `test/missing` | `test_kanban.py` |

### Tier 3 — Fix When Convenient (LOW)

| ID | Title | Category |
|----|-------|----------|
| BH22-003 | CLAUDE.md missing lock_story/lock_sprint from kanban.py entry | `doc/missing` |
| BH22-006 | kanban-protocol.md omits precondition documentation | `doc/missing` |
| BH22-008 | WIP limits table mixes per-persona and team-wide in one column | `doc/inconsistency` |
| BH22-009 | 6 defined-but-unreferenced anchors (index drift) | `doc/missing` |
| BH22-052 | test_assign_both MonitoredMock satisfaction is theater | `test/mock-abuse` |
| BH22-054 | Revert-on-failure call-args check is trivially satisfied | `test/thin` |
| BH22-056 | do_sync "local absent from GitHub" warning path untested | `test/missing` |
| BH22-057 | find_story case-sensitivity and prefix-collision untested | `test/missing` |
| BH22-058 | Transition test verifies labels via string conversion (brittle) | `test/thin` |
| BH22-059 | test_main_status_no_config is coverage theater | `test/thin` |
| BH22-061 | test_failing_run doesn't verify log-fetch call args | `test/thin` |
| BH22-062 | test_empty_preserves_empty has misleading name | `test/bogus` |
| BH22-105 | find_story silently ignores multiple matches | `bug/logic` |
| BH22-111 | extract_story_id fallback returns lowercase | `bug/logic` |
| BH22-113 | No kanban.py command to update individual tracking file fields | `design/gap` |
| BH22-114 | Malformed issue titles create UNKNOWN-untitled.md silently | `bug/logic` |
| BH22-116 | Orphaned local stories warn forever with no resolution path | `design/gap` |

## Emerging Patterns

### PAT-22-001: Atomic rename breaks POSIX flock
**Instances:** BH22-100, BH22-101
**Root cause:** `atomic_write_tf` replaces the inode via `os.rename`, but `lock_story` holds a lock on the old inode's fd. Lock is effectively no-op after the first write.
**Systemic fix:** Use sentinel files for all locks (like `lock_sprint` already does).

### PAT-22-002: Dual sync paths with divergent behavior
**Instances:** BH22-110, BH22-117, BH22-005
**Root cause:** `kanban.py sync` and `sync_tracking.py` both modify tracking files with different validation rules, filename conventions, and field population. Neither coordinates with the other.
**Systemic fix:** Designate one canonical sync path. Either `do_sync` absorbs `sync_tracking`'s PR-linkage logic, or `sync_tracking` absorbs `do_sync`'s transition validation.

### PAT-22-003: Missing orchestration steps between ceremony and state machine
**Instances:** BH22-004, BH22-007, BH22-112, BH22-113
**Root cause:** The prompt files were updated to reference `kanban.py` commands, but the prerequisite steps (create tracking files, set field values, use correct state sequence) weren't added. The state machine enforces preconditions that the docs don't prepare agents for.
**Systemic fix:** Add a "State Machine Prerequisites" checklist to each ceremony/execution reference that lists exactly what must be true before each `kanban.py` call.
