# Bug Hunter Pass 22 — Doc-to-Implementation Audit

Phase 1: Documentation claims vs actual implementation. Focus on the kanban
state machine and its integration into the surrounding system.

---

### BH22-001: `kanban` namespace missing from validate_anchors NAMESPACE_MAP
**Severity:** HIGH
**Category:** `doc/inconsistency`
**Location:** `scripts/validate_anchors.py:23-67`

**Problem:** `scripts/kanban.py` defines 10 anchor comments (`§kanban.TRANSITIONS`,
`§kanban.validate_transition`, etc.) and both `CLAUDE.md` (line 46) and
`CHEATSHEET.md` (lines 113-122) reference them. But the `"kanban"` key is
absent from `NAMESPACE_MAP` in `validate_anchors.py`, so every one of those
references is reported as "unknown namespace 'kanban'" and the validator exits
with failure. The validator itself is the canonical authority on what anchors
are valid; not registering a new script there means the guard doesn't guard.

Running `python scripts/validate_anchors.py` currently reports 10 broken
references from `CLAUDE.md` and CHEATSHEET.md and exits non-zero.

**Acceptance Criteria:**
- [ ] Add `"kanban": "scripts/kanban.py"` to `NAMESPACE_MAP` in `validate_anchors.py`
- [ ] `python scripts/validate_anchors.py` exits 0 with no "unknown namespace 'kanban'" errors

---

### BH22-002: CHEATSHEET.md references `§sync_tracking.slug_from_title`, `§sync_tracking.TF`, `§sync_tracking.read_tf`, `§sync_tracking.write_tf` — all moved to validate_config
**Severity:** HIGH
**Category:** `doc/stale`
**Location:** `CHEATSHEET.md:130-133`

**Problem:** Four anchors listed in the CHEATSHEET.md index for
`skills/sprint-run/scripts/sync_tracking.py` no longer exist in that file.
`slug_from_title`, `TF`, `read_tf`, and `write_tf` were moved to (or always
lived in) `scripts/validate_config.py`. `sync_tracking.py` now imports them
from there. The anchor validator confirms all four as broken:

```
CHEATSHEET.md:130 — §sync_tracking.slug_from_title — anchor not found in skills/sprint-run/scripts/sync_tracking.py
CHEATSHEET.md:131 — §sync_tracking.TF — anchor not found
CHEATSHEET.md:132 — §sync_tracking.read_tf — anchor not found
CHEATSHEET.md:133 — §sync_tracking.write_tf — anchor not found
```

The correct anchors exist in `validate_config.py` as `§validate_config.TF`,
`§validate_config.read_tf`, `§validate_config.write_tf`, and
`§validate_config.slug_from_title` — and are already referenced in CLAUDE.md.

**Acceptance Criteria:**
- [ ] Remove the four stale rows (lines 130-133) from the `sync_tracking.py` section of CHEATSHEET.md
- [ ] `python scripts/validate_anchors.py` exits 0 with no `§sync_tracking.*` broken references

---

### BH22-003: CLAUDE.md missing `build_parser`, `lock_story`, `lock_sprint` from kanban.py key-functions list
**Severity:** LOW
**Category:** `doc/missing`
**Location:** `CLAUDE.md:46`

**Problem:** The CLAUDE.md script table for `scripts/kanban.py` lists 9 key
functions. `kanban.py` defines two more with anchor comments that CHEATSHEET.md
covers (`§kanban.lock_story`, `§kanban.lock_sprint`) plus `build_parser`
(`§kanban.build_parser`). The CHEATSHEET.md already covers `main` but CLAUDE.md
does not. These omissions are acceptable for a summary table, but `lock_story`
and `lock_sprint` are the concurrency primitives introduced by the kanban
state machine and are operationally significant — the risk of race conditions
from parallel agent dispatch makes them worth surfacing.

**Acceptance Criteria:**
- [ ] Add `lock_story()` §kanban.lock_story and `lock_sprint()` §kanban.lock_sprint to the CLAUDE.md kanban.py key-functions cell
- [ ] Or document the deliberate omission policy for summary vs full index

---

### BH22-004: `story-execution.md` REVIEW→INTEGRATION section skips the `integration` state
**Severity:** HIGH
**Category:** `doc/inconsistency`
**Location:** `skills/sprint-run/references/story-execution.md:128-151`

**Problem:** The section header is `## REVIEW --> INTEGRATION` but step 4
instructs:

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py" transition {story_id} done
```

This skips the `integration` kanban state entirely. According to `kanban.py`'s
`TRANSITIONS` table, `review → done` is an **illegal transition** — the only
legal path is `review → integration → done`. An agent following this instruction
verbatim will get an error from `validate_transition()`:

> "Cannot transition 'review' → 'done'. Allowed next states from 'review': ['dev', 'integration']"

The section should issue two transitions: first `transition {story_id} integration`
(after the squash-merge), then `transition {story_id} done` (after confirming
close). Or if `integration` is meant to be a momentary state, the script should
handle the two-step atomically — but currently it does not.

**Acceptance Criteria:**
- [ ] Update `story-execution.md` step 4 to first transition to `integration`, then `done`
- [ ] Or update `kanban.py` TRANSITIONS to allow `review → done` directly and document the rationale
- [ ] Either way, the doc and the code must agree

---

### BH22-005: Conflicting "source of truth" claims — kanban.py says local, sync_tracking.py says GitHub
**Severity:** MEDIUM
**Category:** `doc/inconsistency`
**Location:** `scripts/kanban.py:10-12`, `skills/sprint-run/scripts/sync_tracking.py:9`

**Problem:** The two scripts used for kanban state management make opposite
claims about which system is authoritative:

`scripts/kanban.py` (line 10-12):
```
Source of truth: local tracking files (sprint-{N}/stories/*.md).
GitHub is a downstream reflection synced on every mutation.
```

`skills/sprint-run/scripts/sync_tracking.py` (line 9):
```
GitHub is authoritative. Local tracking files are updated to match.
Missing files are created; stale statuses are corrected.
```

`tracking-formats.md` (line 47) agrees with `kanban.py`:
> "Local tracking files are the source of truth for story state; `kanban.py`
> syncs changes to GitHub on every mutation."

But `CLAUDE.md` (line 128, Key Architectural Decisions) says:
> "**GitHub as source of truth**: `sync_tracking.py` treats GitHub issue/PR
> state as authoritative and updates local tracking files to match."

The intended architecture (as described in `docs/superpowers/specs/2026-03-17-kanban-state-machine-design.md`)
is that `kanban.py` is the write path (local-first) and `sync_tracking.py` is
the read/reconcile path (GitHub wins on conflict). These are complementary, not
contradictory — but the docstrings frame them as opposing truths. A developer
reading both scripts will be confused about which to trust when they diverge.

**Acceptance Criteria:**
- [ ] Update `sync_tracking.py` docstring to clarify its role: "GitHub is authoritative for *reconciliation* — this script accepts GitHub state when the two diverge. For mutations, use `kanban.py` (local-first, then syncs to GitHub)."
- [ ] Update CLAUDE.md Key Architectural Decisions to reflect the two-path model: `kanban.py` = mutation (local-first), `sync_tracking.py` = reconciliation (GitHub wins on conflict)
- [ ] `tracking-formats.md` wording is already correct; no change needed there

---

### BH22-006: `kanban-protocol.md` transition table omits the `todo → design` entry label sync precondition
**Severity:** LOW
**Category:** `doc/missing`
**Location:** `skills/sprint-run/references/kanban-protocol.md:57-62`

**Problem:** `kanban-protocol.md` describes GitHub Label Sync as:

> "The script validates the transition is legal, updates the local tracking
> file, and syncs the GitHub issue label atomically."

But `kanban.py`'s `check_preconditions()` (line 88-128) enforces that entering
`design` requires `tf.implementer` to be set, and entering `dev` requires both
`tf.branch` and `tf.pr_number`. The protocol doc says nothing about these
preconditions. An agent following the protocol doc without reading kanban.py
will attempt a `todo → design` transition before calling `kanban.py assign`,
get a precondition failure, and have no documented recovery path.

The `story-execution.md` step 4 for `TO-DO → DESIGN` correctly calls `kanban.py
transition {story_id} design` after labels and branch are set, but the
precondition that `implementer` must be assigned first is not mentioned.

**Acceptance Criteria:**
- [ ] Add a "Preconditions" subsection to `kanban-protocol.md` listing entry conditions for each state (mirrors `check_preconditions()` in kanban.py)
- [ ] Or add a note to the GitHub Label Sync section: "The script enforces entry preconditions (e.g., implementer must be set before entering design). Use `kanban.py assign` before `kanban.py transition`."

---

### BH22-007: `story-execution.md` `DESIGN → DEVELOPMENT` transition calls `kanban.py transition {story_id} dev` before listing branch/PR as done — precondition will fail
**Severity:** MEDIUM
**Category:** `doc/inconsistency`
**Location:** `skills/sprint-run/references/story-execution.md:61-80`

**Problem:** The `DESIGN --> DEVELOPMENT` section instructs:

> 4. Push commits to the branch. Mark PR as ready for review.
> ```bash
> gh pr ready {pr_number}
> python "${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py" transition {story_id} dev
> ```

`check_preconditions()` in `kanban.py` requires `tf.branch` and `tf.pr_number`
to both be set before allowing a transition to `dev`. If these fields haven't
been written to the tracking file (via `kanban.py assign` or direct edit),
the transition will fail with:

> "Precondition failed: branch, pr_number must be set before entering dev."

The section says "push commits" and "mark PR ready" but does not instruct the
agent to update the tracking file with the branch name and PR number first.
The `implementer.md` step 1 does write `pr_number` and `branch` to the tracking
file after creating the draft PR, so an agent following that path is safe — but
`story-execution.md` is a standalone reference that omits this.

**Acceptance Criteria:**
- [ ] Add an explicit step in `DESIGN → DEVELOPMENT` of `story-execution.md`: update the tracking file with `branch` and `pr_number` before calling `kanban.py transition {story_id} dev`
- [ ] Or add a note that `implementer.md` handles this and `story-execution.md` is a summary, not a standalone procedure

---

### BH22-008: `kanban-protocol.md` WIP limits section contradicts itself — dev limit is "1 per persona" in text but "no limit" isn't stated anywhere
**Severity:** LOW
**Category:** `doc/inconsistency`
**Location:** `skills/sprint-run/references/kanban-protocol.md:64-79`

**Problem:** The Rules section (line 39) says "Allow only ONE story per persona
in `dev` state." The WIP Limits table (line 71-77) says:

| State | Max stories (whole team) |
|---|---|
| design | No limit |
| dev | 1 per persona |
| review | 2 per reviewer persona |
| integration | 3 |

The table column says "whole team" but dev and review limits are "per persona."
The column header is misleading — it implies a team-wide cap, but two of the
four entries are per-persona caps. The `integration` limit of 3 is whole-team
while `dev` is per-persona: these are fundamentally different kinds of limits
mixed in the same column.

**Acceptance Criteria:**
- [ ] Change the WIP Limits table to have two columns: "Scope" (whole-team vs per-persona) and "Max stories"
- [ ] Or split into two tables: per-persona limits and team-wide limits

---

### BH22-009: Anchor validator reports 6 defined-but-unreferenced anchors — not broken but worth noting
**Severity:** LOW
**Category:** `doc/missing`
**Location:** Various

**Problem:** `python scripts/validate_anchors.py` reports these anchors as
defined but never referenced in CLAUDE.md or CHEATSHEET.md:

```
§populate_issues._safe_compile_pattern in skills/sprint-setup/scripts/populate_issues.py
§sprint-run.state_management in skills/sprint-run/SKILL.md
§validate_config.TABLE_ROW in scripts/validate_config.py
§validate_config._yaml_safe in scripts/validate_config.py
§validate_config.frontmatter_value in scripts/validate_config.py
§validate_config.short_title in scripts/validate_config.py
```

Four of the six are in `validate_config.py` — these are helper functions added
after CLAUDE.md and CHEATSHEET.md were last updated. `§sprint-run.state_management`
in SKILL.md and `§populate_issues._safe_compile_pattern` are similarly invisible
to the index. Unreferenced anchors aren't bugs per se, but they indicate the
index is drifting from the implementation.

**Acceptance Criteria:**
- [ ] Add the four `validate_config` helpers (`TABLE_ROW`, `_yaml_safe`, `frontmatter_value`, `short_title`) to the CHEATSHEET.md validate_config.py section
- [ ] Decide whether `§sprint-run.state_management` and `§populate_issues._safe_compile_pattern` are worth surfacing in the index, or remove the anchor comments if not
