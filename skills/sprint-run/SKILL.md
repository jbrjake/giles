---
name: sprint-run
description: Execute a complete sprint with persona-based development, TDD, GitHub PRs, and ceremonies. Use when starting a new sprint, continuing an in-progress sprint, running a sprint kickoff/demo/retro, or working sprint stories. Also triggers on "run sprint", "start sprint", "next sprint", "sprint kickoff", "sprint demo", "sprint retro", "work stories".
---

# Sprint Run

Orchestrate a complete sprint: kickoff, story execution, demo, retro.
All paths, commands, and persona names come from `sprint-config/project.toml`.

## Quick Reference

| Phase | Read These First |
|-------|-----------------|
| Kickoff | `references/ceremony-kickoff.md`, `references/persona-guide.md` |
| Story Execution | `references/story-execution.md`, `references/kanban-protocol.md` |
| Demo | `references/ceremony-demo.md` |
| Retro | `references/ceremony-retro.md` |
| Lost context? | `references/context-recovery.md` |
| File formats | `references/tracking-formats.md` |

## Config & Prerequisites

Run `scripts/validate_config.py` first. If it fails, tell the user to run `sprint-setup` and stop.

Also verify: superpowers plugin installed (`~/.claude/plugins/`), `gh` CLI authenticated (`gh auth status`), and `SPRINT-STATUS.md` exists at `config [paths] sprints_dir`. These are non-negotiable -- without them every later step fails.

## Phase Detection

Read `{config [paths] sprints_dir}/SPRINT-STATUS.md` and route:

| Condition | Action |
|-----------|--------|
| No sprint active | Start new sprint (Phase 1: Kickoff) |
| Sprint active, phase = kickoff | Resume kickoff |
| Sprint active, phase = development | Resume story execution (Phase 2) |
| Sprint active, phase = demo | Resume demo (Phase 3) |
| Sprint active, phase = retro | Resume retro (Phase 4) |
| Sprint complete | Increment sprint number, start Phase 1 |

If the user explicitly requests a specific phase (e.g., "sprint demo"), jump directly -- but warn if prerequisite phases appear incomplete.

## Phase 1: Sprint Kickoff (INTERACTIVE)

Read `references/ceremony-kickoff.md` for the full ceremony script.

Load the milestone from `{config [paths] backlog_dir}/milestones/`. The PM persona presents the sprint goal, story table, and risks. Assign personas per `references/persona-guide.md`. Personas raise concerns in-character; the user resolves them. Create GitHub milestone and issues if not already done. Write kickoff notes to `{sprints_dir}/sprint-{N}/kickoff.md`. Advance phase to development.

## Phase 2: Story Execution (AUTONOMOUS per-story, interactive at gates)

Read `references/story-execution.md` for the full TDD workflow, kanban transitions, and commit conventions. Read `references/kanban-protocol.md` for the state machine.

Determine each story's current kanban state and execute the appropriate transition:

| Current State | Transition | Key Action |
|---------------|------------|------------|
| todo | TO-DO --> DESIGN | Create design notes, draft PR, apply labels |
| design | DESIGN --> DEV | Dispatch implementer subagent, TDD, push code |
| dev | DEV --> REVIEW | Dispatch reviewer subagent, PR review |
| review | REVIEW --> INTEGRATION | CI green, squash-merge, close issue, update burndown |

Stories with no dependencies can run in parallel via `superpowers:dispatching-parallel-agents`. Dependent stories wait.

## Phase 3: Sprint Demo (INTERACTIVE)

Read `references/ceremony-demo.md` for the full ceremony script.

Trigger when all stories are done or the sprint timebox has elapsed. Each implementer persona demonstrates their story with live builds and tests. The PM persona confirms acceptance criteria. Write demo notes to `{sprints_dir}/sprint-{N}/demo.md`. Advance phase to retro.

## Phase 4: Sprint Retro (INTERACTIVE)

Read `references/ceremony-retro.md` for the full ceremony script.

Each persona shares specific reflections (what worked, what hurt, what to change). Group feedback into themes, then distill improvements into project docs (`config [paths] rules_file`, `config [paths] dev_guide`, skill references). Write retro notes to `{sprints_dir}/sprint-{N}/retro.md`. Record velocity in `SPRINT-STATUS.md` and set phase to complete.

## Reference Files

| Reference | Purpose |
|-----------|---------|
| `references/ceremony-kickoff.md` | Kickoff meeting template and facilitation guide |
| `references/ceremony-demo.md` | Demo meeting template and presentation format |
| `references/ceremony-retro.md` | Retro meeting template and feedback structure |
| `references/kanban-protocol.md` | Story state machine, transition rules, label conventions |
| `references/persona-guide.md` | Persona assignment rules, pairing matrix, voice guides |
| `references/story-execution.md` | Full story workflow: kanban transitions, TDD, commit conventions |
| `references/context-recovery.md` | How to reconstruct sprint state after context loss |
| `references/tracking-formats.md` | SPRINT-STATUS.md and story file format specs |
| `agents/implementer.md` | Subagent protocol for story implementation |
| `agents/reviewer.md` | Subagent protocol for PR review |
