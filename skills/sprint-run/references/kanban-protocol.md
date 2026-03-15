# Kanban Protocol

Load this reference when transitioning stories between states or updating
tracking artifacts.

<!-- §kanban-protocol.states_6_todo_design_dev_review_integration_done -->
<!-- §kanban-protocol.states -->
## States

| State | Label | Description |
|---|---|---|
| todo | `kanban:todo` | Story accepted into sprint, not yet started |
| design | `kanban:design` | Implementer reading PRDs, writing design notes, creating branch |
| dev | `kanban:dev` | TDD in progress: failing tests, implementation, green |
| review | `kanban:review` | PR ready, reviewer persona evaluating |
| integration | `kanban:integration` | Approved, CI green, merging |
| done | `kanban:done` | Merged, issue closed, burndown updated |

<!-- §kanban-protocol.transitions_allowed_state_changes -->
## Transitions

```
todo → design       Implementer starts reading PRDs, creates branch
design → dev        Design notes written, draft PR opened
dev → review        Tests pass, PR marked ready for review
review → dev        Changes requested by reviewer
review → integration Approved by reviewer
integration → done  CI green, merged, issue closed
```

<!-- §kanban-protocol.rules_one_story_per_persona_in_dev_3_round_review_limit -->
## Rules

- Allow only ONE story per persona in `dev` state at a time. This prevents
  context thrashing. A persona may have multiple stories in `design` because
  reading does not conflict.
- The `review → dev` loop can repeat at most 3 times. After 3 rounds of
  changes-requested, escalate to the user for guidance.
- Moving to `done` requires ALL criteria in `sprint-config/definition-of-done.md`
  to be satisfied. Read that file before marking any story complete.
- Every transition updates three artifacts:
  1. GitHub issue label (swap old kanban label for new one)
  2. Story tracking file in `{sprints_dir}/sprint-{N}/`
  3. Sprint status file

<!-- §kanban-protocol.github_label_sync_procedure -->
## GitHub Label Sync

On each transition, execute these steps in order:

1. Remove the old `kanban:*` label from the GitHub issue
2. Add the new `kanban:*` label to the GitHub issue
3. Update the project board column if using GitHub Projects
4. Log the transition in the story tracking file with a timestamp

<!-- §kanban-protocol.wip_limits_1_dev_persona_2_review_reviewer_3_integration -->
## WIP Limits

| State | Max stories (whole team) |
|---|---|
| design | No limit |
| dev | 1 per persona |
| review | 2 per reviewer persona |
| integration | 3 |

If a WIP limit is reached, the team must pull stories through the bottleneck
before starting new work.

<!-- §kanban-protocol.blocked_stories -->
## Blocked Stories

If a story is blocked:

1. Add the `blocked` label to the GitHub issue
2. Comment on the issue describing the blocker and what unblocks it
3. Move the persona to their next-priority story
4. Raise the blocker in the next ceremony or immediately if critical
