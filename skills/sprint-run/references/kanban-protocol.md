# Kanban Protocol

Load this reference when transitioning stories between states or updating
tracking artifacts.

<!-- §kanban-protocol.states_6_todo_design_dev_review_integration_done -->
<!-- §kanban-protocol.states -->
## States

States use **entry semantics** — a story enters a state when that type of
work BEGINS, not when it ends. The board answers "what is this story doing
right now?"

| State | Label | Description |
|---|---|---|
| todo | `kanban:todo` | Story accepted into sprint, not yet started |
| design | `kanban:design` | Implementer creating branch, opening draft PR, writing design notes |
| dev | `kanban:dev` | TDD in progress: failing tests, implementation, green, push |
| review | `kanban:review` | Reviewer persona evaluating the PR |
| integration | `kanban:integration` | Review approved — verifying CI, merging, closing issue |
| done | `kanban:done` | Merged and issue closed — terminal state |

<!-- §kanban-protocol.transitions_allowed_state_changes -->
## Transitions

Transitions fire on **entry** to the target state. Each transition's
description is the condition that must be true BEFORE entering.

```
todo → design       Implementer assigned, ready to begin design work
design → dev        Design deliverables ready (branch, draft PR, design notes)
dev → review        Implementation complete, PR ready, reviewer assigned
review → dev        Changes requested — returning to development
review → integration Review approved by reviewer
integration → done  CI green, PR merged, issue closed
```

<!-- §kanban-protocol.rules_one_story_per_persona_in_dev_3_round_review_limit -->
## Rules

> **Note:** These rules are process guidelines for the AI team personas, not
> programmatically enforced constraints. `sync_tracking.py` accepts any valid
> kanban state from GitHub without validating the transition. `kanban.py sync`
> validates transitions and warns about illegal external changes.

- Allow only ONE story per persona in `dev` state at a time. This prevents
  context thrashing. A persona may have multiple stories in `design` because
  reading does not conflict.
- The `review → dev` loop can repeat at most 3 times. After 3 rounds of
  changes-requested, escalate to the user for guidance.
- Moving to `done` requires ALL criteria in `sprint-config/definition-of-done.md`
  to be satisfied. Read that file before marking any story complete.
- Every transition updates two artifacts:
  1. Story tracking file in `{sprints_dir}/sprint-{N}/stories/`
  2. GitHub issue label (swap old kanban label for new one)

  Burndown and SPRINT-STATUS.md are updated separately by `update_burndown.py`.

<!-- §kanban-protocol.preconditions -->
## Preconditions

The state machine enforces **entry guards** — conditions that must be met
before a story can enter the target state. These verify that the previous
phase's deliverables exist. Set required fields before calling
`kanban.py transition`:

| Target state | Required fields | How to set them |
|---|---|---|
| design | `implementer` | `kanban.py assign --implementer {name}` |
| dev | `branch` and `pr_number` | `kanban.py update --branch {name} --pr-number {N}` |
| review | `implementer` and `reviewer` | `kanban.py assign --implementer {name} --reviewer {name}` |
| integration | `reviewer` | `kanban.py assign --reviewer {name}` (set during review entry) |
| done | `pr_number` | `kanban.py update --pr-number {N}` |
| todo | (no preconditions) | — |

<!-- §kanban-protocol.github_label_sync_procedure -->
## GitHub Label Sync

All state management goes through the centralized state machine:

```bash
# State transitions (validates legality, checks preconditions, syncs GitHub label)
python "${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py" transition <story-id> <target-state> [--sprint N]

# Persona assignment (sets implementer/reviewer, adds persona labels on GitHub)
python "${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py" assign <story-id> --implementer <name> --reviewer <name> [--sprint N]

# Field updates (sets pr_number, branch, or other tracking fields)
python "${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py" update <story-id> --pr-number <N> --branch <name> [--sprint N]

# Sync local tracking files with GitHub state
python "${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py" sync [--sprint N] [--prune]
```

Use `kanban.py` exclusively for kanban label changes — it validates transitions, updates tracking files, and syncs GitHub atomically.

> **Two sync paths:** `kanban.py sync` validates transitions and rejects illegal
> external changes. `sync_tracking.py` is a complementary reconciliation path
> that accepts any valid GitHub state without transition validation — it fills in
> PR/branch metadata and corrects stale statuses. See CLAUDE.md "Two-path state
> management" for the design rationale.

<!-- §kanban-protocol.wip_limits_1_dev_persona_2_review_reviewer_3_integration -->
## WIP Limits

> **Note:** All three WIP limits (dev, review, integration) are enforced
> by `kanban.py check_wip_limit()`. Use `--force-wip` to override when justified.

| State | Scope | Max stories | Enforcement |
|---|---|---|---|
| design | whole team | No limit | — |
| dev | per persona | 1 | Code (`check_wip_limit`) |
| review | per reviewer | 2 | Code (`check_wip_limit`, override: `--force-wip`) |
| integration | whole team | 3 | Code (`check_wip_limit`, override: `--force-wip`) |

If a WIP limit is reached, the team must pull stories through the bottleneck
before starting new work.

### Review Round Escalation

After 3 `review → dev` cycles on a single story, `kanban.py` blocks further
transitions and recommends escalation to the user. This indicates a possible
design issue that review feedback alone isn't resolving.
Use `--force-review-round` to override after explicit discussion.

<!-- §kanban-protocol.blocked_stories -->
## Blocked Stories

If a story is blocked:

1. Add the `blocked` label to the GitHub issue
2. Comment on the issue describing the blocker and what unblocks it
3. Move the persona to their next-priority story
4. Raise the blocker in the next ceremony or immediately if critical
