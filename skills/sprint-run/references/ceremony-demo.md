# Ceremony: Sprint Demo

Load this reference when running the demo ceremony at the end of a sprint.

## Purpose

Demonstrate working software to stakeholders. Every feature shown must produce
REAL artifacts — actual build output, test results, logs, screenshots. No
slideware. No mockups. No "imagine this works."

## Facilitation

Giles opens the demo and manages presentation order. For each story, the
implementer persona presents their work. The PM confirms acceptance criteria.

- **Giles** opens, manages flow, calls on personas for Q&A, keeps time.
- **Implementer persona** presents each story they built.
- **PM persona** confirms acceptance criteria for each story.

**Ensemble framing:** If one story dominated the sprint (star-vehicle sprint),
Giles gives it 60% of demo time and presents it first. He acknowledges the
supporting cast: "This was {persona}'s sprint. Let's see the main event, then
we'll walk the supporting work."

For ensemble sprints, Giles walks stories in priority order with even time
allocation.

## For Each Story

### 1. Context (implementer persona, in character)

- What was the goal?
- Why does it matter? Frame in terms of user value, not technical description.
- What design decisions were made and why?
- What was surprising or harder than expected?

### 2. Live Demonstration (MUST produce real artifacts)

Run these steps and capture all output:

- **Build:** Use build command from project.toml `[ci] build_command` — capture output
- **Test:** Use test command from project.toml `[ci] check_commands` — capture full test output with pass/fail counts
- **Run:** Actually execute the feature and capture results:
  - For CLI features: run commands, capture stdout/stderr
  - For API features: make curl requests, show responses
  - For UI features: take screenshots if applicable
  - For data pipeline features: process sample data, show results
  - For performance features: run benchmarks, show numbers

Save ALL artifacts to `{sprints_dir}/sprint-{N}/demo-artifacts/` (path from project.toml `[paths]`).
Use descriptive filenames: `US-XXXX-build-output.txt`,
`US-XXXX-test-results.txt`, `US-XXXX-benchmark.txt`.

### 3. Acceptance Verification

Walk through each acceptance criterion from the story:

- Show evidence (test output, log output, measurements) for each criterion
- Link to the specific artifact that proves the criterion is met
- PM confirms for each criterion: accepted / needs follow-up

If a criterion is not met, record it as a follow-up item with a clear
description of what remains.

### 3.5. Test Plan Verification (if test plan configured)

For each story demonstrated:
- Read the test cases referenced in the story's `Test Cases` field
- Confirm each referenced test case is covered by the implementation
- Record gaps: test cases that were planned but not implemented

This is not about whether tests pass (that's CI's job) — it's about
whether the test COVERAGE matches what the test plan specified.

### 4. Team Q&A (in-persona)

Giles manages the Q&A flow. He ensures each persona gets a chance to comment
from their domain. If a persona hasn't spoken, Giles calls on them:
"{persona_name}, you've been quiet. Anything from the {domain} perspective?"

If `{team_dir}/insights.md` exists, Giles references it to call on personas
about stories that touch their territory. If a story involves the domain that
someone protects, their perspective is especially valuable — and potentially
especially charged.

Giles reads the Confidence section from each story's PR description before
the demo. During Q&A, he probes low-confidence areas harder:

- "Your PR noted low confidence on the edge case handling. Walk us through
  what you tested and what you didn't."
- "Medium confidence on the serialization logic — did the reviewer's
  second pass catch anything there?"

This ensures the demo doesn't just celebrate what worked — it examines
what might not have.

- Reviewer persona comments on code quality observations from their review
- Other team members ask questions from their domain perspective (e.g.,
  memory implications, security implications, adversarial test scenarios,
  algorithmic complexity, deployment implications, regression coverage)

## Output

Write `{sprints_dir}/sprint-{N}/demo.md` (path from project.toml `[paths]`):

```markdown
# Sprint {N} Demo — {date}

**Facilitator:** Giles

## Stories Demonstrated

### US-XXXX: {title}
**Presented by:** {persona name} ({role})
**Build Output:** [link to artifact]
**Test Results:** {pass/fail count}
**Acceptance Criteria:**
- [x] Criterion 1 — Evidence: {link/excerpt}
- [x] Criterion 2 — Evidence: {link/excerpt}
**Team Feedback:** {questions and responses}
**Status:** Accepted / Follow-up needed

## Sprint Metrics
- Stories completed: X/Y
- Story points delivered: X/Y
- Test count: X (Y passing)

## Traceability
| Story | Epic | Test Cases Covered | Test Cases Gaps |
|-------|------|--------------------|-----------------|
```

## Rules

- Do not demo a story that has not reached `kanban:done` status. If a story is
  incomplete, note it in the metrics as not demonstrated.
- Every accepted criterion must have a link to an artifact. No verbal-only
  evidence.
- If the build fails during demo, record the failure. Do not pretend it passed.
- Save the demo doc and all artifacts before proceeding to retro.
