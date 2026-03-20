# Ceremony: Sprint Retro

Load this reference when running the retrospective ceremony at the end of a
sprint, after the demo.

## Purpose

Reflect on the sprint at a META level — not what was built, but how the team
worked. The key output is ACTIONABLE CHANGES to project docs (read target files
from project.toml `[paths]`).

A retro that produces no doc changes is a failed retro.

<!-- §ceremony-retro.facilitation_giles_facilitates_pm_participates_as_team_member -->
<!-- §ceremony-retro.facilitation -->
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

<!-- §ceremony-retro.format_start_stop_continue -->
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

<!-- §ceremony-retro.feedback_distillation_identify_patterns_propose_doc_changes -->
## Feedback Distillation

This is the most important part of the retro. After collecting raw feedback:

### 1. Identify Patterns

Giles looks for themes that multiple personas mentioned. A pattern raised by
two or more personas is a strong signal. A pattern raised by only one persona
is still worth recording but lower priority.

Giles synthesizes with data when available: "Three of you mentioned review
friction. The numbers back that up — average review rounds this sprint was 2.8,
up from 1.9 last sprint."

<!-- §ceremony-retro.2_propose_doc_changes -->
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

<!-- §ceremony-retro.3_get_user_approval -->
### 3. Get User Approval

Present all proposed changes to the user. Do not apply changes without approval.
Group changes by file for easy review.

<!-- §ceremony-retro.4_apply_changes -->
### 4. Apply Changes

After approval, edit the project docs directly. Verify each change is applied
correctly. Confirm the file stays under the 500-line target / 750-line hard
limit.

<!-- §ceremony-retro.fix_failure_analysis -->
### 4.5. Fix Failure Analysis

For each time during the sprint that something was claimed fixed but wasn't,
analyze the pattern.  This is separate from Start/Stop/Continue — it's about
the fix-verify-fix loop.

For each failed fix attempt this sprint:
- What was claimed?
- What evidence supported the claim?
- What evidence would have refuted it?
- What is the general principle?
- What checklist item prevents the category?

Feed identified principles into the Principle Extraction step below.

<!-- §ceremony-retro.structural_encoding -->
### 4.6. Structural Encoding

For each action item, classify:

- **Structural** (can be enforced by hook/script/precondition — specify which
  file to modify)
- **Behavioral** (relies on LLM discipline — mark as at-risk)

| Item | Classification | Encoding Target |
|------|---------------|-----------------|

Target: >50% structural.  Behavioral items are injected as warnings by the
SessionStart hook.

<!-- §ceremony-retro.principle_extraction -->
### 4.7. Principle Extraction

Review the action items as a group.  Are any of them instances of the same
broader principle?  If so, name the principle and record it.

Principles are more durable than rules — "the app target is a different
artifact than the library" catches multiple bugs that individual rules would
catch one at a time.

Record principles in a `## Principles` section of the retro doc.  Principles
carry forward to SessionStart hook context alongside action items.

<!-- §ceremony-retro.5_sprint_analytics -->
### 5. Sprint Analytics

Run `"${CLAUDE_PLUGIN_ROOT}/scripts/sprint_analytics.py"` to compute
sprint metrics. The script queries GitHub for review round counts and velocity.
Giles reviews the numbers and adds qualitative commentary.

Append findings to `{sprints_dir}/analytics.md`. Format:

    ### Sprint {N} — {theme}
    **Velocity:** {delivered_sp}/{planned_sp} SP ({percentage}%)
    **Review rounds:** avg {X} per story ({highest}: {story_id})
    **Giles notes:** {qualitative commentary — patterns, surprises, recommendations}

If the analytics script is unavailable or fails, Giles writes observations
from memory. The script makes it precise; Giles makes it useful.

<!-- §ceremony-retro.6_write_sprint_history -->
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

<!-- §ceremony-retro.7_definition_of_done_review -->
### 7. Definition of Done Review

Read `sprint-config/definition-of-done.md`. Based on this sprint's
experience, Giles proposes additions or modifications.

Examples of retro-driven DoD additions:
- "Error messages follow the format in rules.md" (after a sprint where they didn't)
- "Performance-sensitive code has benchmark results" (after a performance surprise)
- "New public APIs have usage examples" (after a reviewer noted missing docs)

Present proposed changes to the user. Apply only after approval.

<!-- §ceremony-retro.standing_questions -->
### 8. Standing Questions (mandatory, every retro)

These questions are asked every retro, regardless of sprint outcomes:

1. "Did we verify the product launches this sprint?  What was the smoke test result?"
2. "What test categories are missing?" (Check `test_categories.py` output)
3. "Which retro action items from last sprint were structurally encoded vs merely documented?"
4. "What failure mode have we not yet experienced but could?" (Forward-looking risk)

Record answers in the retro output.

<!-- §ceremony-retro.examples_of_retro_driven_doc_changes -->
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

<!-- §ceremony-retro.output_template_retro_md -->
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
| Item | Classification | Encoding Target | Owner | Due |
|---|---|---|---|---|

## Principles
{broader principles extracted from this sprint's action items}

## Velocity
- Planned: {X} SP
- Delivered: {X} SP
- Velocity: {X} SP/sprint
- Trend: {increasing / stable / decreasing}
```

<!-- §ceremony-retro.rules_must_produce_at_least_one_doc_change -->
## Rules

- Every retro must produce at least one proposed doc change. If the team cannot
  identify any improvements, the facilitation failed — dig deeper.
- Do not skip the velocity section. Track trend across sprints to calibrate
  future planning.
- Record action items with owners and due dates. Unowned action items do not get
  done.
- Save the retro doc before closing the sprint.
