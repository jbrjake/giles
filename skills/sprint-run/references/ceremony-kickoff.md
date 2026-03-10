# Ceremony: Sprint Kickoff

Load this reference when running the kickoff ceremony at the start of a sprint.

## Purpose

Align the team on sprint goals, assign work, surface risks, and create shared
understanding before development starts.

## Facilitation

The PM persona facilitates. They present the sprint goal and stories, then
open the floor.

## Agenda

### 1. Sprint Goal

The PM reads the sprint goal from the milestone doc. State it clearly in one or
two sentences. Confirm the user agrees this is the right focus.

### 2. Story Walk

For each story in the sprint backlog:

- **PM presents:** ID, title, SP, priority, acceptance criteria
- **Assigned implementer responds** (in-persona): initial thoughts, concerns,
  dependencies, estimated complexity
- **Assigned reviewer responds** (in-persona): what they will focus on in
  review, any domain-specific concerns

Walk stories in priority order so that the most important stories get the most
discussion time.

### 3. Risk Discussion

Each persona raises domain-specific concerns:

- **Technical risks:** performance, memory, concurrency, platform differences
- **Dependency risks:** story A needs story B's code first, external dependency
  updates, API stability
- **Design risks:** PRD ambiguity, missing acceptance criteria, untested
  assumptions
- **Capacity risks:** too many stories for available personas, overlapping
  domain needs

### 4. Question Resolution

The user (as product owner) answers questions and clarifies requirements. Record
every question and its resolution. If a question cannot be answered immediately,
mark it as an open question and assign a due date.

### 5. New Tasks

If questions reveal work not in the sprint plan:

1. Create a GitHub issue for each new task
2. Assign it to the sprint milestone
3. Set story points and priority
4. Adjust sprint capacity if needed — drop lower-priority stories if the sprint
   is over capacity

### 6. Commitment

The team confirms the sprint scope is achievable. If not, the PM negotiates
scope reduction with the user until commitment is reached.

## Output

Write `{sprints_dir}/sprint-{N}/kickoff.md` (path from project.toml `[paths]`):

```markdown
# Sprint {N} Kickoff — {date}

## Sprint Goal
{from milestone doc}

## Stories
| Story | Title | SP | Implementer | Reviewer |
|---|---|---|---|---|

## Questions Raised
| # | Question | Resolution | Status |
|---|---|---|---|

## New Tasks Added
| Issue | Title | SP | Rationale |
|---|---|---|---|

## Risks Identified
| Risk | Domain | Mitigation | Owner |
|---|---|---|---|

## Team Commitment
{confirmed / adjusted scope with rationale}
```

## Exit Criteria

Do not proceed to development until:

1. Every story has an assigned implementer and reviewer
2. All blocking questions are resolved or have a resolution plan
3. The team has confirmed commitment to the sprint scope
4. The kickoff doc is written and saved
