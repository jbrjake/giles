# Holtz Punchlist (Run 4 — Targeted)

## SF-001: `done` state description includes post-transition work

- **Category:** `doc/semantic-fidelity`
- **Severity:** LOW
- **File:** `skills/sprint-run/references/kanban-protocol.md:21`
- **Lens:** semantic-fidelity
- **Predicted:** P1 (HIGH) — CONFIRMED
- **Discovery Chain:** custom-lenses.md defines semantic-fidelity → trace when `done` label is applied → burndown is updated AFTER transition (story-execution.md:222) → description says "burndown updated" but this is post-entry

**Description:** The `done` state description reads "Merged, issue closed, burndown updated." Under entry semantics, the description should reflect what is true at the moment the state is entered. At the moment of `done` entry: merged ✓, issue closed ✓ (closed inside do_transition), burndown updated ✗ (happens in a separate step after the transition).

**Evidence:**
- kanban-protocol.md line 21: `| done | kanban:done | Merged, issue closed, burndown updated |`
- story-execution.md lines 218-228: Step 1 transitions to done, Step 2 updates burndown (separate command)
- kanban.py line 405-406: issue close happens inside do_transition, before label swap

**Acceptance criteria:** The `done` description should not include "burndown updated" since that happens post-transition. Suggested: "Merged and issue closed — terminal state."
**Validation:** Read kanban-protocol.md line 21 and verify it no longer claims burndown is updated at entry.
**Status:** RESOLVED — changed to "Merged and issue closed — terminal state"

---

## SF-002: `integration` is the only working state with no entry guard

- **Category:** `design/semantic-fidelity`
- **Severity:** LOW
- **File:** `scripts/kanban.py:89-129` (check_preconditions)
- **Lens:** semantic-fidelity
- **Predicted:** P2 (MEDIUM) — CONFIRMED
- **Discovery Chain:** semantic-fidelity lens entry point → enumerate entry guards per state → design/dev/review/done all have guards → integration has none → description says "Review approved" but code doesn't verify

**Description:** Every working state except `integration` has at least one entry guard:
- `design`: implementer
- `dev`: branch + pr_number
- `review`: implementer + reviewer
- `done`: pr_number
- `integration`: (nothing)

The `integration` description says "Review approved — verifying CI, merging, closing issue." The "Review approved" part is entirely process-enforced — no code verifies that a PR review was submitted or approved. This is documented in the Rules section ("process guidelines, not programmatically enforced constraints") but creates an asymmetry that the semantic-fidelity lens flags.

**Evidence:**
- check_preconditions() has no branch for `target == "integration"` — falls through to `return None`
- test_unchecked_states_return_none (line 216): explicitly tests that integration has no guards
- kanban-protocol.md preconditions table: "todo, integration | (no preconditions)"

**Acceptance criteria:** Add `reviewer` entry guard for `integration` in check_preconditions. Update preconditions table in kanban-protocol.md. Add tests.
**Validation:** `python -m pytest tests/test_kanban.py -k "test_integration_requires_reviewer or test_integration_ok_with_reviewer" -v`
**Status:** RESOLVED — added reviewer entry guard, updated docs and tests (+2 tests)

---

## TP-001: kanban-protocol.md doesn't document two-sync-path enforcement differences

- **Category:** `doc/temporal-protocol`
- **Severity:** LOW
- **File:** `skills/sprint-run/references/kanban-protocol.md:78-94`
- **Lens:** temporal-protocol
- **Predicted:** P3 (LOW) — CONFIRMED
- **Discovery Chain:** temporal-protocol lens entry point → trace multi-file orchestration → discover do_sync validates transitions but sync_one doesn't → kanban-protocol.md §GitHub Label Sync only shows `kanban.py` commands → reader wouldn't know sync_tracking.py exists or behaves differently

**Description:** kanban-protocol.md's "GitHub Label Sync" section (lines 78-94) documents `kanban.py` as "the centralized state machine" for "all state management." But `sync_tracking.py` is a separate sync path that accepts any valid GitHub state without transition validation. A reader of kanban-protocol.md alone would not know that:
1. A second sync path exists (sync_tracking.py)
2. It bypasses transition validation
3. It can create state regressions (e.g., review → todo)

This is documented in CLAUDE.md ("Two-path state management") and in sync_tracking.py's docstring, but not in the protocol reference that agents actually read during sprint execution.

**Evidence:**
- kanban-protocol.md lines 78-94: only mentions `kanban.py` commands
- sync_tracking.py line 134-138: docstring explains intentional bypass
- CLAUDE.md: "Two-path state management" section describes the design

**Acceptance criteria:** Add a note to kanban-protocol.md mentioning that `sync_tracking.py` is a complementary path with different enforcement (reference CLAUDE.md for details), OR add a brief section after the GitHub Label Sync section.
**Validation:** Read kanban-protocol.md and verify the two-path design is mentioned.
**Status:** RESOLVED — added blockquote after GitHub Label Sync section

---

## SF-003: Forced-done via sync bypasses `done` entry guard

- **Category:** `design/semantic-fidelity`
- **Severity:** LOW
- **File:** `scripts/kanban.py:538-549` (do_sync)
- **Lens:** semantic-fidelity
- **Discovery Chain:** trace `done` entry guard (pr_number required) → find do_sync forced-close path → BH22-050 bypasses check_preconditions → tracking file in `done` without pr_number → check consumers → update_burndown.py uses `or "—"` default → safe

**Description:** When `do_sync` encounters a closed GitHub issue, it forces the local state to `done` regardless of the kanban transition graph (BH22-050). This bypasses `check_preconditions`, so the `done` entry guard (`pr_number` required) is not enforced. A tracking file can end up in `done` state without `pr_number`.

Downstream consumers handle this gracefully:
- `update_burndown.py` line 137: `frontmatter_value(fm, "pr_number") or "—"` (em dash fallback)
- `sprint_analytics.py`: doesn't reference `pr_number`

**Evidence:**
- kanban.py lines 538-549: closed-issue override with BH22-050 comment
- check_preconditions is not called in the do_sync forced-close path
- update_burndown.py line 137: graceful fallback

**Acceptance criteria:** Add a warning in do_sync when forced-done story lacks pr_number. Add tests for both the warning case and the no-warning case.
**Validation:** `python -m pytest tests/test_kanban.py -k "test_sync_forced_done" -v`
**Status:** RESOLVED — added warning in do_sync forced-done path (+2 tests)
