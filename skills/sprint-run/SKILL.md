---
name: sprint-run
description: Execute a complete sprint with persona-based development, TDD, GitHub PRs, and ceremonies. Use when starting a new sprint, continuing an in-progress sprint, running a sprint kickoff/demo/retro, or working sprint stories. Also triggers on "run sprint", "start sprint", "next sprint", "sprint kickoff", "sprint demo", "sprint retro", "work stories".
---

# Sprint Run

Orchestrate a complete sprint: kickoff, story execution, demo, retro.
Each phase is described below. Heavy detail lives in reference files --
this skill stays at the orchestration level.

All paths, commands, and persona names are read from `project.toml`
and the project's `sprint-config/` directory -- nothing is hardcoded.

---

## Config Validation

Before doing anything, run `scripts/validate_config.py` to confirm
`sprint-config/` is present and valid. If validation fails, tell the
user to run `sprint-setup` (which will invoke `sprint-init`) and stop.

Throughout this document, paths and commands reference `project.toml`
sections. Notation: `config [section] key` means the value of `key`
inside `[section]` of `sprint-config/project.toml`.

---

## Prerequisites

Verify before doing anything else. If any check fails, tell the user
to run `sprint-setup` first and stop.

1. Superpowers plugin installed -- check `~/.claude/plugins/` for a
   `superpowers` entry.
2. `gh` CLI authenticated -- run `gh auth status` and confirm success.
3. `SPRINT-STATUS.md` exists at the path from config `[paths] sprints_dir`.

These are non-negotiable because the sprint process depends on GitHub
issue/PR automation and the superpowers plugin for TDD and parallel
dispatch. Without them, every later step will fail in confusing ways.

---

## Phase Detection

On entry, read `{config [paths] sprints_dir}/SPRINT-STATUS.md` and
route to the correct phase:

| Condition | Action |
|-----------|--------|
| No sprint active | Start new sprint (Phase 1: Kickoff) |
| Sprint active, phase = kickoff | Resume kickoff |
| Sprint active, phase = development | Resume story execution (Phase 2) |
| Sprint active, phase = demo | Resume demo (Phase 3) |
| Sprint active, phase = retro | Resume retro (Phase 4) |
| Sprint complete | Increment sprint number, start Phase 1 |

If the user explicitly requests a specific phase (e.g., "sprint demo"),
jump directly to that phase -- but warn if prerequisite phases appear
incomplete.

---

## Phase 1: Sprint Kickoff (INTERACTIVE)

Read `skills/sprint-run/references/ceremony-kickoff.md` for the full template.

This phase is a conversation with the user. The team personas participate
in-character because surfacing concerns early prevents costly mid-sprint
pivots.

### Steps

1. **Load the milestone.** Read the milestone doc from
   `{config [paths] backlog_dir}/milestones/` and extract stories for
   the current sprint number.

2. **Present the sprint.** The PM persona (identified via
   `{config [paths] team_dir}/INDEX.md` -- the persona whose role
   contains "PM" or "product") presents:
   - Sprint goal (one sentence)
   - Story table: ID, title, SP, priority
   - Key deliverables and acceptance criteria
   - Known risks and dependencies

3. **Assign personas.** Read `skills/sprint-run/references/persona-guide.md` for
   assignment rules. Read `{config [paths] team_dir}/INDEX.md` to get
   the team roster. Match personas to stories by comparing each
   persona's domain keywords (from their persona file) against story
   content. Each story gets an implementer and a reviewer (different
   personas). Record assignments.

4. **Raise concerns in-persona.** Team members relevant to this
   sprint's stories voice questions in their own style, drawing from
   their persona file's domain focus. Only personas assigned to this
   sprint speak. Silence from uninvolved personas is better than filler.

5. **Resolve questions with user.** Work through each concern. If new
   tasks emerge, add them. If scope needs trimming, trim it. The user
   has final say.

6. **Create GitHub artifacts.** If not already done by `sprint-setup`:
   - Create GitHub milestone: `Sprint {N}`
   - Create GitHub issues for each story, labeled with saga, priority,
     persona, and `kanban:todo`

7. **Write kickoff notes.** Save to
   `{sprints_dir}/sprint-{N}/kickoff.md` with:
   - Sprint goal, story list, persona assignments
   - Questions raised and resolutions
   - Any scope changes agreed with the user

8. **Advance phase.** Update `SPRINT-STATUS.md`: set phase = development.

---

## Phase 2: Story Execution (AUTONOMOUS per-story, interactive at gates)

Read `skills/sprint-run/references/kanban-protocol.md` for the state machine governing
story transitions.

Stories flow through four kanban states. Each transition has a clear
purpose and exit criteria. The goal is to keep stories moving while
maintaining quality through persona-based review.

### TO-DO --> DESIGN

The implementer persona reads the story requirements, relevant PRDs,
and acceptance criteria, then produces a design.

1. Write design notes in
   `{sprints_dir}/sprint-{N}/stories/US-XXXX-slug.md`.
2. Create branch using the pattern from
   `config [conventions] branch_pattern` (e.g., `sprint-{N}/US-XXXX-slug`).
3. Open a **draft PR** with full context in the description:
   - Story ID, title, acceptance criteria (copied in full)
   - Relevant PRD excerpts (so the reviewer can work entirely from the
     PR -- no external doc lookup needed)
   - Design decisions and rationale
   - Persona header: who implements, who reviews
   - Links to related stories/PRDs (for reference, not required reading)
4. Apply labels: persona, sprint, saga, priority, `kanban:design`.
5. Update the GitHub issue label to `kanban:design`.

The PR description carries full context because reviewers should never
need to leave the PR to understand what they are reviewing.

### DESIGN --> DEVELOPMENT

Dispatch the implementer as a subagent. Read `skills/sprint-run/agents/implementer.md`
for the full agent protocol. The implementer's persona file (from
`{config [paths] team_dir}/`) provides voice, domain focus, and
review style.

1. Subagent works in-persona.
2. Invoke `superpowers:test-driven-development` -- write failing tests
   first, then implement until tests pass.
3. If `config [paths] cheatsheet` or `config [paths] architecture`
   are defined, update those progressive disclosure docs in lockstep
   with code changes. Code without updated docs is incomplete work.
4. Push commits to the branch. Mark PR as ready for review.
5. Update the GitHub issue label to `kanban:dev`.

### DEVELOPMENT --> REVIEW

Dispatch the reviewer as a subagent. Read `skills/sprint-run/agents/reviewer.md` for the
full agent protocol. The reviewer's persona file (from
`{config [paths] team_dir}/`) provides voice and review perspective.

1. Reviewer is a **different persona** than the implementer. Read
   `skills/sprint-run/references/persona-guide.md` for the pairing rules.
2. Reviewer posts a GitHub PR review with a persona header identifying
   who they are and what perspective they bring.
3. Review is conducted entirely from the PR description + diff. This
   validates that the PR description is actually sufficient. If the
   reviewer needs to read external docs to understand the change, that
   is a defect in the PR description, not a defect in the reviewer.
4. If approved: proceed to integration.
5. If changes requested: implementer addresses feedback, then
   re-requests review. This loop repeats until approval.
6. Update the GitHub issue label to `kanban:review`.

### REVIEW --> INTEGRATION

1. Confirm CI is green -- check GitHub Actions status via `gh`.
2. Invoke `superpowers:verification-before-completion` to run the
   project's verification suite.
3. Squash-merge the PR to main.
4. Close the GitHub issue.
5. Update burndown: run `skills/sprint-run/scripts/update_burndown.py`.
6. Update story tracking file: set status = done, record completion date.
7. Update `SPRINT-STATUS.md` with the completed story.
8. Update the GitHub issue label to `kanban:done`.

### Parallel Dispatch

Check the story dependency graph before dispatching. Stories with no
dependencies on in-progress work can run simultaneously using
`superpowers:dispatching-parallel-agents`.

Stories that depend on an in-progress story wait. This is enforced
rather than advisory because merging dependent work out of order creates
integration nightmares that cost more time than the parallelism saves.

---

## Phase 3: Sprint Demo (INTERACTIVE)

Read `skills/sprint-run/references/ceremony-demo.md` for the full template.

Trigger: all stories are done, or the sprint timebox has elapsed.

The demo exists to prove the work is real. Personas present their own
stories because they understand the design intent, and the live
demonstration catches integration issues that tests alone can miss.

### Steps

1. **For each completed story,** the implementer persona presents:
   - What was built and why it matters (in their voice and style)
   - **Live demonstration** on the host machine:
     - Build: run `config [ci] build_command`
     - Test: run each command in `config [ci] check_commands`
     - Execute the feature -- capture output (logs, HTTP responses,
       terminal output)
     - Save artifacts to
       `{sprints_dir}/sprint-{N}/demo-artifacts/`
   - Test results, coverage data, benchmark numbers

2. **Team Q&A.** Other personas ask questions in-character. This surfaces
   integration concerns and usability issues that the implementer may
   have missed.

3. **Acceptance.** The PM persona confirms acceptance criteria are met
   for each story. If a criterion is not met, the story goes back to
   development with a clear description of what is missing.

4. **Write demo notes.** Save to
   `{sprints_dir}/sprint-{N}/demo.md` with:
   - Summary of each story demonstrated
   - Links to demo artifacts
   - Acceptance decisions
   - Any follow-up items identified

5. **Advance phase.** Update `SPRINT-STATUS.md`: set phase = retro.

---

## Phase 4: Sprint Retro (INTERACTIVE)

Read `skills/sprint-run/references/ceremony-retro.md` for the full template.

The retro is where the sprint process improves itself. Raw feedback is
valuable, but the real output is concrete changes to project
documentation -- otherwise the same problems recur next sprint.

### Steps

1. **Persona reflections.** Each persona involved in this sprint shares:
   - What went well (be specific -- name the practice, tool, or decision)
   - What was frustrating (be specific -- name the friction point)
   - What should change (propose a concrete action, not a vague wish)

2. **Identify actionable improvements.** Group feedback into themes.
   For each theme, decide: change a doc, change a process, or accept
   the tradeoff.

3. **Distill feedback into project docs.** This is the key output.
   Update targets are read from `config [paths]`:
   - `config [paths] rules_file` if new constraints were discovered
   - `config [paths] dev_guide` if process improvements are needed
   - Update skill references if the sprint process itself needs tuning
   - Update `skills/sprint-run/references/persona-guide.md` if pairing rules need adjustment
   - Any other path defined in `[paths]` that is relevant to the finding

   Each doc change gets a brief comment explaining which retro finding
   motivated it, so future readers understand the provenance.

4. **Write retro notes.** Save to
   `{sprints_dir}/sprint-{N}/retro.md` with:
   - Raw persona reflections
   - Themes identified
   - Actions taken (with links to the docs changed)
   - Velocity: planned SP vs. completed SP

5. **Record velocity.** Update `SPRINT-STATUS.md`:
   - Set phase = complete
   - Add a row to the velocity history table
   - Clear the active stories table

6. **Close out.** Tell the user: sprint complete. Next step is
   `sprint-run` again to begin the next sprint.

---

## Context Recovery

If Claude loses context mid-sprint (new conversation, context window
overflow, etc.), reconstruct state before resuming. All paths are read
from `config [paths]`:

1. Read `{sprints_dir}/SPRINT-STATUS.md` -- current sprint number,
   phase, velocity history.
2. Read `{sprints_dir}/sprint-{N}/burndown.md` -- what is done,
   what is in-flight.
3. Read in-flight story files in
   `{sprints_dir}/sprint-{N}/stories/` -- YAML frontmatter has
   exact state (status, branch, PR number, issue number).
4. Run `skills/sprint-run/scripts/sync_tracking.py` to reconcile local tracking files
   with GitHub state (issues, PRs, labels).
5. Query GitHub directly:
   - `gh issue list --milestone "Sprint {N}"`
   - `gh pr list --label "sprint-{N}"`
6. Resume from the detected phase via the phase detection table above.

Context recovery is aggressive by design. Every piece of sprint state
is persisted to files or GitHub, so no information depends on
conversation memory alone.

---

## Tracking File Formats

### SPRINT-STATUS.md

```markdown
# Project Status

## Current Sprint: 1

## Sprint Phase: development

## Velocity History

| Sprint | Planned SP | Completed SP |
|--------|-----------|-------------|

## Active Stories

| Story | Status | Assignee | PR |
|-------|--------|----------|----|
```

### Story File (YAML frontmatter)

```yaml
---
story: US-0101
title: Short description
sprint: 1
implementer: persona-slug
reviewer: persona-slug
status: dev
branch: sprint-1/US-0101-short-slug
pr_number: 3
issue_number: 1
started: 2026-03-10
completed:
---
```

The `status` field mirrors kanban states: `todo`, `design`, `dev`,
`review`, `done`. The frontmatter is the source of truth for story
state; the kanban labels on GitHub issues are kept in sync but the
file wins if they diverge.

---

## File Map

Files this skill creates or updates during a sprint. All paths are
resolved from `config [paths] sprints_dir` (shown here as `{sprints_dir}`):

| File | Created | Phase |
|------|---------|-------|
| `{sprints_dir}/SPRINT-STATUS.md` | By sprint-setup | All |
| `{sprints_dir}/sprint-{N}/kickoff.md` | By this skill | Kickoff |
| `{sprints_dir}/sprint-{N}/stories/US-XXXX-slug.md` | Per story | Design |
| `{sprints_dir}/sprint-{N}/burndown.md` | Updated per story | Development |
| `{sprints_dir}/sprint-{N}/demo-artifacts/` | Demo outputs | Demo |
| `{sprints_dir}/sprint-{N}/demo.md` | By this skill | Demo |
| `{sprints_dir}/sprint-{N}/retro.md` | By this skill | Retro |

---

## Reference Files

| Reference | Purpose |
|-----------|---------|
| `skills/sprint-run/references/ceremony-kickoff.md` | Kickoff meeting template and facilitation guide |
| `skills/sprint-run/references/ceremony-demo.md` | Demo meeting template and presentation format |
| `skills/sprint-run/references/ceremony-retro.md` | Retro meeting template and feedback structure |
| `skills/sprint-run/references/kanban-protocol.md` | Story state machine, transition rules, label conventions |
| `skills/sprint-run/references/persona-guide.md` | Persona assignment rules, pairing matrix, voice guides |
| `skills/sprint-run/agents/implementer.md` | Subagent protocol for story implementation |
| `skills/sprint-run/agents/reviewer.md` | Subagent protocol for PR review |
