# Ceremony: Sprint Demo

Load this reference when running the demo ceremony at the end of a sprint.

## Purpose

Demonstrate working software to stakeholders. Every feature shown must produce
REAL artifacts — actual build output, test results, logs, screenshots. No
slideware. No mockups. No "imagine this works."

## Facilitation

The PM persona introduces each story. The implementer persona presents their
work.

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

### 4. Team Q&A (in-persona)

- Reviewer persona comments on code quality observations from their review
- Other team members ask questions from their domain perspective (e.g.,
  memory implications, security implications, adversarial test scenarios,
  algorithmic complexity, deployment implications, regression coverage)

## Output

Write `{sprints_dir}/sprint-{N}/demo.md` (path from project.toml `[paths]`):

```markdown
# Sprint {N} Demo — {date}

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
```

## Rules

- Do not demo a story that has not reached `kanban:done` status. If a story is
  incomplete, note it in the metrics as not demonstrated.
- Every accepted criterion must have a link to an artifact. No verbal-only
  evidence.
- If the build fails during demo, record the failure. Do not pretend it passed.
- Save the demo doc and all artifacts before proceeding to retro.
