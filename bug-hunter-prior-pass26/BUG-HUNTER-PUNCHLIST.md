# Bug Hunter Punchlist — Pass 26 (Systems & Integration Audit)

> Generated: 2026-03-20 | Project: giles | Baseline: 1089 pass, 0 fail
> Focus: Systems/integration in commit c653908 (9 files, 346 lines)

## Summary

| Severity | Open | Resolved | Deferred |
|----------|------|----------|----------|
| HIGH     | 2    | 0        | 0        |
| MEDIUM   | 3    | 0        | 0        |
| LOW      | 3    | 0        | 0        |

---

## Tier 1 — Fix Now (HIGH)

### Integration Failures

| ID | Title | Category | Acceptance Criteria | Validation |
|----|-------|----------|---------------------|------------|
| BH26-001 | verify_agent_output.main() tracking path never resolves — H-006 feature broken | bug/integration | `_TRACKING_PATH_PATTERN` captures `sprint-\d+/stories/\S+\.md` but actual files live under `{sprints_dir}/sprint-N/stories/`. The hook doesn't read `paths.sprints_dir` from config, so the captured path is always relative to CWD and never matches a real file. `update_tracking_verification` silently returns at the `if not p.is_file()` guard. The entire H-006 feature (writing verification results to tracking files) is non-functional. **Fix:** Read `paths.sprints_dir` from config via `_read_toml_key`, resolve the captured path against `_find_project_root() / sprints_dir`, or search for the file. | Test: create a tracking file at `{tmp}/sprints/sprint-1/stories/US-0001.md`, set `paths.sprints_dir = "sprints"` in config, feed agent output containing `sprint-1/stories/US-0001.md`, verify `verification_agent_stop` field is written. |
| BH26-002 | sync_tracking.py TOCTOU: sync_one() modifies TF before lock acquired | bug/race | `sync_one()` calls `_append_transition_log(tf, ...)` and sets `tf.status` at lines 137-141. The lock isn't acquired until line 278 (`with lock_story(...)`). If kanban.py writes to the same file between `sync_one()` returning and `write_tf()` executing, those changes are silently overwritten. **Fix:** Move the lock acquisition to wrap both `sync_one()` and `write_tf()`, or re-read the TF under lock before calling `sync_one()`. | Test: write a tracking file, call sync_one() to modify in memory, then write a different status to the same file (simulating concurrent kanban), then write_tf() — verify the concurrent write is not lost. |

---

## Tier 2 — Fix Soon (MEDIUM)

### Test Gaps

| ID | Title | Category | Acceptance Criteria | Validation |
|----|-------|----------|---------------------|------------|
| BH26-003 | No tests for review/integration WIP limits | test/missing | `check_wip_limit()` was expanded to support `review` (limit 2/reviewer) and `integration` (limit 3/team-wide), but all 3 tests in TestWIPLimit only cover the `dev` case. The review per-reviewer and integration team-wide logic paths are completely untested. | At least 4 new tests: (1) review limit blocks at 2, (2) review limit independent per reviewer, (3) integration limit blocks at 3, (4) integration is team-wide not per-persona |
| BH26-004 | _is_implementer_output() false negative allows verification skip | bug/safety | An implementer whose output says "I made the code changes and fixed the tests" (no commit/pushed/PR/branch/implementation keyword) would be classified as non-implementer, skipping verification entirely. This is a safety gap — the fail-open heuristic can miss real implementers. **Fix:** Add "merge" and "branch" to keywords, or use a different heuristic (e.g., check if the agent created/edited source files). | Test: output containing "I made the code changes" with check_commands set → currently returns False (bug), should return True or have a documented rationale for why this is acceptable. |
| BH26-005 | _has_unquoted_bracket() / _strip_inline_comment() ignore backslash-escaped quotes | bug/parser | In TOML, `\"` inside a double-quoted string is a valid escape. Both functions see the escaped `"` as closing the quote, causing subsequent `]` or `#` to be misinterpreted. Example: `"test\"param]"` — the `]` after the escaped quote is treated as unquoted, truncating the value. Same class of bug as BH25-002/DA-009 but for escaped quotes. | Test: `_has_unquoted_bracket('"test\\"val]"')` should return False (the `]` is inside quotes). `_strip_inline_comment('"test\\"val" # comment')` should return `"test\\"val"`. |

---

## Tier 3 — Fix When Convenient (LOW)

### Code Hygiene

| ID | Title | Category | Acceptance Criteria | Validation |
|----|-------|----------|---------------------|------------|
| BH26-006 | _append_transition_log is private but imported cross-module | code/convention | `sync_tracking.py:34` imports `_append_transition_log` from `kanban.py`. Leading underscore indicates module-private, but this function is now part of the cross-module API. | Rename to `append_transition_log` (no underscore) in kanban.py and update both import sites. |
| BH26-007 | INT-8 WIP warning inconsistent across states | code/inconsistency | `do_transition()` line 375 warns about missing WIP context only for `target == "dev"`, but WIP limits are now enforced for review and integration too. If sprints_dir/sprint is None for those targets, WIP is silently skipped without warning. | Either extend the warning to cover all WIP-limited states, or document why dev-only is sufficient. |
| BH26-008 | _is_implementer_output() false positive on review output | code/quality | Reviewer saying "I reviewed the commit" matches "commit" keyword → triggers unnecessary verification. Over-verification is safe but wastes time. | Add word boundary (`\bcommitted\b\|\bcommit[s]?\b` instead of bare `commit`) or require 2+ keyword matches to reduce false positives. |

---

## Emerging Patterns

### PAT-26-001: Hook system has a parallel config universe
**Instances:** BH26-001, BH25-002 (prior), BH26-005
**Root Cause:** Hooks use lightweight TOML parsing and don't read `paths.*` config keys. The hook system can find project.toml but doesn't understand project structure (sprints_dir, team_dir, etc.). This creates integration failures where hooks can't find the files that scripts manage.
**Systemic Fix:** Add a `_read_config_paths()` helper to `_common.py` that reads the key `paths.*` values from project.toml using the existing `_read_toml_key` function. All hooks that need to locate sprint artifacts would use this.

### PAT-26-002: Lock boundaries don't match modification boundaries
**Instances:** BH26-002, BH25-006 (prior)
**Root Cause:** Code modifies TF objects in memory before acquiring locks, then writes under lock. The lock prevents concurrent writes but doesn't prevent the in-memory state from becoming stale. The correct pattern is: acquire lock → read → modify → write → release lock.
**Systemic Fix:** Enforce in code review: any function that calls `_append_transition_log()` or modifies `tf.status` must do so inside a lock context.
