# Ceremony: Sprint Retro

Load this reference when running the retrospective ceremony at the end of a
sprint, after the demo.

## Purpose

Reflect on the sprint at a META level — not what was built, but how the team
worked. The key output is ACTIONABLE CHANGES to project docs (read target files
from project.toml `[paths]`).

A retro that produces no doc changes is a failed retro.

## Facilitation

The PM persona facilitates. Each persona who worked during the sprint speaks.

## Format: Start / Stop / Continue

Collect feedback from each persona involved in the sprint.

**Start doing:**
- New practices, tools, conventions to adopt
- Things the team did not do that would have helped
- Processes observed in other domains worth spreading

**Stop doing:**
- Practices that wasted time or caused problems
- Anti-patterns observed during the sprint
- Ceremony steps that added no value

**Continue doing:**
- Things that worked well and should be preserved
- Practices worth reinforcing or formalizing

## Feedback Distillation

This is the most important part of the retro. After collecting raw feedback:

### 1. Identify Patterns

Look for themes that multiple personas mentioned. A pattern raised by two or
more personas is a strong signal. A pattern raised by only one persona is still
worth recording but lower priority.

### 2. Propose Doc Changes

For each pattern, propose a concrete change:

- **Which file?** Any project doc listed in project.toml `[paths]`, or a
  skill reference file
- **What specific change?** New rule, modified convention, new pitfall entry,
  new checklist item, updated process step
- **Why?** What happened during the sprint that motivates this change — cite
  specific stories or incidents
- **PRD files?** If the sprint revealed design gaps, ambiguous requirements,
  or missing edge cases, propose changes to PRD `## Open Questions` or
  `## Requirements` sections in `{config [paths] prd_dir}`. Retro findings
  that reveal design gaps get added to Open Questions; resolved questions
  get promoted to Requirements.

### 3. Get User Approval

Present all proposed changes to the user. Do not apply changes without approval.
Group changes by file for easy review.

### 4. Apply Changes

After approval, edit the project docs directly. Verify each change is applied
correctly. Confirm the file stays under the 500-line target / 750-line hard
limit.

## Examples of Retro-Driven Doc Changes

- Sprint revealed a recurring code anti-pattern — add to project rules as a
  common pitfall
- Sprint revealed a reference doc fell out of sync — add lockstep update rule
  to development guide
- Sprint revealed that PR descriptions were too thin — strengthen the
  implementer skill prompt
- Sprint revealed a naming inconsistency — add to project naming conventions
- Sprint revealed that review cycles exceeded 3 rounds repeatedly — adjust the
  kanban-protocol.md escalation threshold
- Sprint revealed that kickoff missed dependency ordering — add dependency
  check step to ceremony-kickoff.md
- Sprint revealed a PRD requirement was ambiguous — add clarification to
  PRD requirements section and close the open question
- Sprint revealed an untested edge case — add to test plan adversarial
  tests and link to relevant story

## Output

Write `{sprints_dir}/sprint-{N}/retro.md` (path from project.toml `[paths]`):

```markdown
# Sprint {N} Retro — {date}

## Participants
{personas who worked this sprint}

## Raw Feedback

### {Persona Name} — {Role}
**Start:** {items}
**Stop:** {items}
**Continue:** {items}

## Patterns Identified
| Pattern | Raised By | Priority |
|---|---|---|

## Doc Changes Applied
| File | Change | Rationale |
|---|---|---|
| {file} | Added X to common pitfalls | {what happened} |

## Action Items for Next Sprint
| Item | Owner | Due |
|---|---|---|

## Velocity
- Planned: {X} SP
- Delivered: {X} SP
- Velocity: {X} SP/sprint
- Trend: {increasing / stable / decreasing}
```

## Rules

- Every retro must produce at least one proposed doc change. If the team cannot
  identify any improvements, the facilitation failed — dig deeper.
- Do not skip the velocity section. Track trend across sprints to calibrate
  future planning.
- Record action items with owners and due dates. Unowned action items do not get
  done.
- Save the retro doc before closing the sprint.
