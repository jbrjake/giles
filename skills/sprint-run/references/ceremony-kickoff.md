# Ceremony: Sprint Kickoff

Load this reference when running the kickoff ceremony at the start of a sprint.

## Purpose

Align the team on sprint goals, assign work, surface risks, and create shared
understanding before development starts.

<!-- §ceremony-kickoff.facilitation_giles_pm_split -->
## Facilitation

Giles facilitates. The PM persona presents product context. These are distinct
roles:

- **Giles** opens the meeting, manages the agenda, calls on personas, drives
  rhythm, manages scope negotiation, and drives to commitment.
- **PM persona** presents the sprint goal, walks stories, answers product
  questions, and assesses story value during scope negotiation.

<!-- §ceremony-kickoff.sprint_theme -->
<!-- §ceremony-kickoff.sprint_theme_hardening_feature_star_vehicle_ensemble -->
## Sprint Theme

After reading the milestone doc, Giles identifies the sprint's character and
names it. This frames the team's expectations:

- A **hardening sprint** is about stability, not features. "We're shoring up
  the foundation. Keep your ambitions architectural."
- A **feature sprint** is about shipping. "Three new user-facing stories. Make
  them work, make them correct, make them pleasant."
- A **star-vehicle sprint** is dominated by one big story. "This is {persona}'s
  sprint. Everyone else is in a supporting role. Plan your attention accordingly."
- An **ensemble sprint** spreads load evenly. "No headliners, no openers.
  Everyone carries equal weight this round."

<!-- §ceremony-kickoff.agenda_opening_team_read_saga_context_goal_story_walk_risks_questions_commitment -->
## Agenda

### 0. Previous Sprint Health

Run `python "${CLAUDE_PLUGIN_ROOT}/scripts/smoke_test.py"` and the project's
`[ci] check_commands`.  If SMOKE FAIL, discuss immediately: the foundation is
broken and must be fixed before new work begins.  Add a fix story to the sprint.

If SMOKE SKIP (not configured), note it and proceed.

### 1. Opening

Giles opens the meeting. One sentence to set the tone: "Right then. Sprint {N}.
Let's see what we're working with."

<!-- §ceremony-kickoff.team_read -->
<!-- §ceremony-kickoff.1_5_team_read_write_insights -->
### 1.5. Team Read (Write Insights)

Giles reads all persona files from `{config [paths] team_dir}` and any history
files from `{team_dir}/history/`. From these, he distills a compact insight for
each persona and writes `{team_dir}/insights.md`:

    # Team Insights
    > Giles's observations on what drives each member of this team.
    > Written at the start of each sprint. Not shown to the team.

    ### {Persona Name}
    **What drives them:** {1-2 sentences from Origin Story + Professional Identity}
    **What they protect:** {1 sentence — what triggers defensiveness}
    **What earns their trust:** {1 sentence from Improvisation Notes}
    **Current emotional state:** {1-2 sentences from sprint history, or "First sprint" if none}

Regenerate this file each sprint — it is a current snapshot, not an append-only
log. History files are the append-only record; insights are the distillation.
This should be compact — roughly 400 tokens for a team of 5.

<!-- §ceremony-kickoff.saga_context -->
<!-- §ceremony-kickoff.1_7_saga_context_if_sagas_configured -->
### 1.7. Saga Context (if sagas configured)

For each saga active in this sprint:
- Read the saga file from `{config [paths] sagas_dir}`
- PM presents the saga goal and team voices section
- Giles frames how this sprint's stories advance the saga's strategic objective

If multiple sagas are active, present each briefly. This gives the team
the "why" before diving into the "what."

### 2. Sprint Goal

PM presents the sprint goal from the milestone doc. State it clearly in one or
two sentences. Confirm the user agrees this is the right focus.

Giles names the sprint theme (see Sprint Theme above).

<!-- §ceremony-kickoff.process_context_analytics -->
<!-- §ceremony-kickoff.2_5_process_context_if_analytics_exist -->
### 2.5. Process Context (if analytics exist)

If `{sprints_dir}/analytics.md` exists, Giles reads it before the story walk.
He surfaces relevant patterns during persona assignment and story discussion:

- "Last three sprints, {domain} stories averaged {X} review rounds. Plan accordingly."
- "The velocity trend suggests we can handle {X} SP this sprint, not {Y}."
- "{persona} has been carrying {X}% of the workload. Let's distribute more evenly."

This is not a formal presentation — Giles weaves the data into his facilitation
naturally. He's the one who remembers what happened last time.

<!-- §ceremony-kickoff.user_facing_delta -->
### 2.7. User-Facing Delta

Before walking stories, PM declares the user-facing delta:

**PM declares:** "After this sprint, the user will see/experience: ___."

If the delta is "nothing new" (foundational sprint), declare it explicitly:
"This sprint is foundational. No user-visible change expected."

If declared foundational, record `type: foundational` in SPRINT-STATUS.md.
Otherwise, at least one story must map to the declared delta.

<!-- §ceremony-kickoff.3_story_walk -->
### 3. Story Walk

For each story in the sprint backlog:

- **PM presents:** ID, title, SP, priority, acceptance criteria,
  epic context (where in the epic, what's done/remaining),
  PRD references (requirement IDs if PRD configured),
  test plan references (test case IDs if test plan configured)
- **Giles calls on the assigned implementer** (in-persona): initial thoughts,
  concerns, dependencies, estimated complexity
- **Giles calls on the assigned reviewer** (in-persona): what they will focus
  on in review, any domain-specific concerns

**Rhythm:** Giles manages story order and energy. Walk stories in priority order,
but after a heavy discussion, follow with a lighter story or a quick win. After a
stretch of easy consensus, Giles probes: "Really? No concerns? {reviewer_name},
what happens when we get 10 million of those?"

**Motivation awareness:** If `{team_dir}/insights.md` exists, Giles uses it to
read the room. If a story touches what someone protects — correctness for a
programmer who once shipped a catastrophic bug, being heard for a QA lead who
was once ignored — probe harder on that story. The insights don't change the
agenda. They change how Giles facilitates it.

**Star-vehicle sprints:** If one story dominates the sprint (5+ SP, critical
path), Giles gives it 60% of the story walk time and presents it first. He
acknowledges the supporting cast: "The remaining stories orbit this one. Let's
walk them efficiently."

<!-- §ceremony-kickoff.integration_gap_scan -->
### 3.5. Integration Gap Scan

Run `python "${CLAUDE_PLUGIN_ROOT}/scripts/gap_scanner.py" --config sprint-config/project.toml --sprint {N}`.
Present results.

If GAP DETECTED, discuss: add an integration story, or defer with explicit
rationale recorded in kickoff notes.

### 4. Risk Discussion

Each persona raises domain-specific concerns:

- **Technical risks:** performance, memory, concurrency, platform differences
- **Dependency risks:** story A needs story B's code first, external dependency
  updates, API stability
- **Design risks:** PRD ambiguity, missing acceptance criteria, untested
  assumptions, PRD open questions (read from `## Open Questions` sections
  in `{config [paths] prd_dir}` if configured)
- **Capacity risks:** too many stories for available personas, overlapping
  domain needs

Giles synthesizes after all personas speak: identifies patterns, groups related
risks, and summarizes the risk landscape. "So we have two stories that share a
parser dependency and a PRD question that nobody has answered yet. Those are
related. Let's resolve the PRD question before either story starts."

If `{team_dir}/insights.md` exists, name which personas will feel which risks
most urgently. A risk that touches someone's core motivation is not just a
technical concern — it will shape how they work the entire sprint.

<!-- §ceremony-kickoff.confidence_check -->
<!-- §ceremony-kickoff.4_5_confidence_check -->
### 4.5. Confidence Check

After risks, Giles reads the room. If all personas expressed high confidence
and no major risks were raised, Giles offers to abbreviate:

"Right, you all look terribly keen and nobody's pulling that face {reviewer_name}
makes when she's about to say something alarming. Shall we skip the extended
discussion and commit?"

- If the user agrees, jump to Commitment.
- If any persona or the user hesitates, continue normally through Question
  Resolution and Scope Negotiation.

### 5. Question Resolution

The user (as product owner) answers questions. PM answers product questions.
Giles tracks the Q&A and ensures every question gets a resolution or an explicit
"open" status with a due date. If a question cannot be answered immediately,
mark it as open and assign responsibility.

<!-- §ceremony-kickoff.scope_negotiation -->
<!-- §ceremony-kickoff.5_5_scope_negotiation -->
### 5.5. Scope Negotiation

When the sprint is over capacity (total SP exceeds team velocity or persona
load is unbalanced), Giles runs scope negotiation:

**The 2x2 framework:** Giles presents stories on two axes:
- **Value to milestone goal** (PM provides this assessment): high or low
- **Dependency risk** (from the dependency graph): high or low

| | Low Dependency Risk | High Dependency Risk |
|---|---|---|
| **High Value** | Keep | Discuss — value may justify the risk |
| **Low Value** | Keep if capacity allows | Cut first |

High-value + low-dependency stories stay. Low-value + high-dependency stories
go first. The middle gets discussed. Giles frames this as analysis, not as
loss: "We're not cutting stories. We're sequencing them across sprints."

### 6. New Tasks

If questions reveal work not in the sprint plan:

1. Create a GitHub issue for each new task
2. Assign it to the sprint milestone
3. Set story points and priority
4. Adjust sprint capacity if needed — use the scope negotiation framework
   above if the sprint is over capacity

### 7. Commitment

Giles drives to commitment:

- PM confirms the scope is achievable from a product perspective.
- Giles confirms from a process perspective: persona load is balanced, no
  single persona is overloaded, dependencies are sequenced.
- If commitment cannot be reached, return to Scope Negotiation.

<!-- §ceremony-kickoff.output_template_kickoff_md -->
## Output

Write `{sprints_dir}/sprint-{N}/kickoff.md` (path from project.toml `[paths]`):

```markdown
# Sprint {N} Kickoff — {date}

**Facilitator:** Giles
**Sprint Theme:** {theme name and one-sentence description}

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

<!-- §ceremony-kickoff.exit_criteria -->
## Exit Criteria

Do not proceed to development until:

1. Every story has an assigned implementer and reviewer
2. All blocking questions are resolved or have a resolution plan
3. The team has confirmed commitment to the sprint scope
4. User-facing delta has been declared and at least one story maps to it (unless foundational)
5. Gap scanner has run; any detected gaps have been addressed or explicitly deferred
6. The kickoff doc is written and saved
7. Tracking files exist for all sprint stories:
   ```bash
   python "${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py" sync --sprint {N}
   ```
8. Every story's persona assignment is synced to GitHub:
   ```bash
   python "${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py" assign {story_id} --implementer {impl} --reviewer {rev}
   ```
