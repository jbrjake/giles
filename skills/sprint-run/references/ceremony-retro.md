# Ceremony: Sprint Retro

Load this reference when running the retrospective ceremony at the end of a
sprint, after the demo.

## Purpose

Reflect on the sprint at a META level — not what was built, but how the team
worked. The key output is ACTIONABLE CHANGES to project docs (read target files
from project.toml `[paths]`).

A retro that produces no doc changes is a failed retro.

## Facilitation

Giles facilitates. The PM participates as a team member — they provide
feedback like everyone else, but they do not run the meeting.

- **Giles** opens, manages turn-taking, collects feedback, identifies
  patterns, proposes doc changes, and drives to action items.
- **PM persona** contributes Start/Stop/Continue feedback from the product
  perspective, like any other team member.
- **All personas** who worked during the sprint speak, including the PM.

**Psychological safety:** If the sprint involved difficult review cycles, scope
cuts, or repeated rework, Giles acknowledges it before diving into feedback:
"This sprint had more review rounds than anyone planned for. That's worth
discussing, and I'd like to hear what each of you thinks went on there."

If `{team_dir}/insights.md` exists, Giles reads it before the retro. If the
sprint hit close to home for someone — a story that touched what they protect,
a review cycle that challenged their core expertise — acknowledge it before
they have to raise it. "This sprint asked a lot of {persona_name}'s domain.
I'd like to hear from them first."

After cutting scope: "We deferred {N} stories this sprint. That was the right
call, and I want to hear whether anyone disagrees."

## Format: Start / Stop / Continue

Giles collects feedback from each persona involved in the sprint. He manages
turn-taking and ensures quieter personas speak. If someone hasn't contributed,
Giles calls on them: "{persona_name}, you've been quiet. What's your read on
the sprint?"

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

Giles looks for themes that multiple personas mentioned. A pattern raised by
two or more personas is a strong signal. A pattern raised by only one persona
is still worth recording but lower priority.

Giles synthesizes with data when available: "Three of you mentioned review
friction. The numbers back that up — average review rounds this sprint was 2.8,
up from 1.9 last sprint."

### 2. Propose Doc Changes

For each pattern, Giles proposes a concrete change:

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

### 5. Sprint Analytics

Run `scripts/sprint_analytics.py` (path relative to plugin root) to compute
sprint metrics. The script queries GitHub for review round counts, velocity,
and cycle times. Giles reviews the numbers and adds qualitative commentary.

Append findings to `{sprints_dir}/analytics.md`. Format:

    ### Sprint {N} — {theme}
    **Velocity:** {delivered_sp}/{planned_sp} SP ({percentage}%)
    **Review rounds:** avg {X} per story ({highest}: {story_id})
    **Cycle time:** avg {X} hours from design to done
    **Giles notes:** {qualitative commentary — patterns, surprises, recommendations}

If the analytics script is unavailable or fails, Giles writes observations
from memory. The script makes it precise; Giles makes it useful.

### 6. Write Sprint History

For each persona who worked during the sprint, Giles appends an entry to
`{team_dir}/history/{persona_name}.md`. Create the file if it doesn't exist.

Each entry follows this format:

    ---

    ### Sprint {N} — {sprint_theme}

    {2-3 paragraphs in Giles's voice: what they worked on, how it went,
    what surprised them, what they'd be wary of. Specific, not generic.
    Reference actual stories, actual code, actual review feedback.}

    **Worked on:** {story_ids}
    **Surprised by:** {specific observation}
    **Wary of next time:** {specific concern}
    **Emotional shift:** {if insights.md existed — note changes from start of sprint. "Came in wary of the parser; left confident after Checker's edge case tests all passed." These feed back into next sprint's distillation.}

Also append Giles's own entry to `{team_dir}/history/giles.md` — process
observations, facilitation learnings, what he'd adjust.

### 7. Definition of Done Review

Read `sprint-config/definition-of-done.md`. Based on this sprint's
experience, Giles proposes additions or modifications.

Examples of retro-driven DoD additions:
- "Error messages follow the format in rules.md" (after a sprint where they didn't)
- "Performance-sensitive code has benchmark results" (after a performance surprise)
- "New public APIs have usage examples" (after a reviewer noted missing docs)

Present proposed changes to the user. Apply only after approval.

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

**Facilitator:** Giles

## Participants
{personas who worked this sprint, including PM}

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
