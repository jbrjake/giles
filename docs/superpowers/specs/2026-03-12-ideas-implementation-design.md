# IDEAS Implementation Design — Vertical Slices

> Implements accepted ideas from `IDEAS-accepted.md` and pipeline scripts from
> `docs/superpowers/plans/future-full-pipeline.md`. Four vertical chunks, each
> delivering a complete feature set end-to-end.

**Source material:** `IDEAS-accepted.md`, `IDEAS.md` (cross-cutting themes),
`docs/superpowers/plans/future-full-pipeline.md`

**Architecture:** Prompt-first where possible, scripts where data is needed.
All scripts are stdlib-only Python 3.10+. No new dependencies.

---

## Chunk Overview

| Chunk | Name | Core Deliverable | Dependencies |
|-------|------|-----------------|--------------|
| 1 | Giles the Butler | Persona + ceremony PM/Giles split + facilitation features | None |
| 2 | Persona Evolution | Sprint History + callbacks + analytics + evolving DoD | Chunk 1 |
| 3 | Agent Infrastructure + Monitor | Multi-pass review, context budgets, confidence signals, check-in, drift | Chunk 1 |
| 4 | Pipeline Scripts | Voice extraction, traceability, test coverage, saga/epic management | None |

Chunks 2 and 3 depend on Chunk 1 (Giles exists) but not on each other.
Chunk 4 is independent.

---

## Chunk 1: Giles the Butler

### Character

Giles is the **scrum master** — not the PM. He facilitates agile ceremonies
and coordinates process. The user's dev team personas include PM personas with
deep product knowledge; Giles runs the sprint while the PM owns the product.

**Backstory:** A librarian roped into letting these people use his library for
their project. He's really quite busy, but sure, if they need a scrum master
he's quite okay with taking one for the team. "And what is agile exactly?" he
asks. He's relieved to learn it's not about sports. He is brilliant and quite
a quick study — better at this than anyone expected, including himself.

**Personality:** Dryly sarcastic. Buttoned-down exterior concealing a wild
past that leaks under stress. Rakishly charming. Comically exasperated but
ever gentlemanly — a British butler sensibility. Reluctant competence.

**Facilitation style:** He reads the room. Scene beats, confidence checks,
and ceremony pacing are his character instincts, not formal protocols. He
frames sprint themes, identifies star-vehicle sprints, and handles scope
negotiation with a value/dependency 2x2 framework. He protects psychological
safety — after tough review cycles or scope cuts, he says the thing that makes
the user feel supported. Not sycophancy. Facilitation.

### New Files

| File | Purpose |
|------|---------|
| `references/skeletons/giles.md.tmpl` | Giles persona skeleton — ships fully written, not TODO-filled |
| `tests/fixtures/hexwise/docs/team/giles.md` | Hexwise-adapted Giles persona |

### Modified Files

| File | Changes |
|------|---------|
| `skills/sprint-run/references/ceremony-kickoff.md` | PM/Giles split: Giles opens and facilitates, PM presents stories. Add scene beats, confidence check, sprint theme, scope negotiation framework, ensemble/star framing |
| `skills/sprint-run/references/ceremony-demo.md` | PM/Giles split: Giles opens and manages flow, PM confirms acceptance, implementers present |
| `skills/sprint-run/references/ceremony-retro.md` | PM/Giles split: Giles facilitates Start/Stop/Continue, PM participates as team member |
| `skills/sprint-run/references/persona-guide.md` | Add Giles: always facilitator, never implementer/reviewer. PM role clarification |
| `skills/sprint-run/SKILL.md` | Update phase descriptions: Giles facilitates, PM presents |
| `scripts/sprint_init.py` | Auto-generate `sprint-config/team/giles.md` from skeleton, add to team INDEX |
| `tests/fixtures/hexwise/docs/team/INDEX.md` | Add Giles row |
| `tests/fixtures/hexwise/docs/team/team-topology.md` | Add Giles relationships |

---

## Chunk 2: Persona Evolution

### Sprint History

Giles appends persona observations to separate history files after each retro.
Written in Giles's voice describing the persona, not in their own voice.

Files live at `{team_dir}/history/{persona_name}.md`. Agent templates read
both the persona file (character) and the history file (accumulated memory).

Example entry: "Rusti spent most of the sprint arguing with the HSL parser and
won. She is now suspicious of all floating-point arithmetic, which frankly she
should have been already."

### Callbacks

Not a separate feature — agents read Sprint History before starting work. If a
previous sprint's observations are relevant, they reference them in design
notes, PR descriptions, and reviews. "We've talked about this before, Conor."

### Analytics

Hybrid system: `scripts/sprint_analytics.py` computes metrics from GitHub data
and local sprint docs. Giles narrates the findings and appends qualitative
commentary to `{sprints_dir}/analytics.md`.

Metrics computed:
- Velocity per sprint (planned vs delivered SP)
- Review rounds per story
- Story cycle time (kanban state timestamps)
- Per-persona workload distribution
- Per-domain story counts and review friction

Giles references analytics during kickoff planning.

### Evolving Definition of Done

`sprint-config/definition-of-done.md` starts with a mechanical baseline (CI
green, PR approved, merged, issue closed, burndown updated). Each retro, Giles
proposes additions based on sprint learnings. Additions are user-approved.
Kanban protocol references this file instead of a hardcoded list.

### New Files

| File | Purpose |
|------|---------|
| `scripts/sprint_analytics.py` | Compute sprint metrics from GitHub + local docs |
| `references/skeletons/definition-of-done.md.tmpl` | Baseline mechanical DoD |

### Modified Files

| File | Changes |
|------|---------|
| `skills/sprint-run/agents/implementer.md` | Read `{team_dir}/history/{persona}.md` for prior sprint context. Reference in design notes |
| `skills/sprint-run/agents/reviewer.md` | Read history file before reviewing. Reference prior observations |
| `skills/sprint-run/references/ceremony-retro.md` | New steps: run analytics, Giles writes history entries, Giles proposes DoD additions |
| `skills/sprint-run/references/ceremony-kickoff.md` | Giles reads analytics.md and references patterns |
| `skills/sprint-run/references/kanban-protocol.md` | "Done" references definition-of-done.md |
| `references/skeletons/persona.md.tmpl` | Note about Sprint History living in `history/` dir |
| `scripts/sprint_init.py` | Generate `sprint-config/definition-of-done.md`, create `{team_dir}/history/` dir |

### Hexwise Fixture Updates

| File | Changes |
|------|---------|
| `tests/fixtures/hexwise/docs/team/history/rusti.md` | Sample Sprint History (1-2 sprints, Giles voice) |
| `tests/fixtures/hexwise/docs/team/history/palette.md` | Sample Sprint History |
| `tests/fixtures/hexwise/docs/team/history/checker.md` | Sample Sprint History |
| `tests/fixtures/hexwise/docs/team/history/giles.md` | Sample Giles self-observations |

---

## Chunk 3: Agent Infrastructure + Monitor

### Multi-Pass Review

Reviewer template restructured into three explicit passes:

1. **Correctness:** acceptance criteria, logic, edge cases
2. **Conventions:** rules file, file sizes, commit format, progressive disclosure
3. **Testing:** coverage, meaningful assertions, success/error paths, test plan

Each pass produces findings. Reviewer synthesizes into one GitHub review.

### Pair Review

Opt-in for stories with SP >= threshold (default 5) AND touching files owned
by multiple personas. Two reviewer subagents dispatched, each reviewing from
their domain. Implementer reconciles both sets of feedback.

### Context Budget Guidance

Implementer template gains a "Context Management" section:
- Load persona + rules at start
- Summarize PRD excerpts after design decisions are made
- On large stories (5+ SP), summarize design notes before implementation phase

Reviewer template notes: multi-pass review is itself a context strategy.

### Confidence Signals

Implementer PR description template gains `## Confidence` section: per-area
ratings (high/medium/low) with brief rationale. Reviewer reads confidence
first, spends proportionally more time on low-confidence areas. Demo probes
low-confidence features harder.

### Mid-Sprint Check-In

Sprint-monitor detects when stories_done >= stories_total / 2. Outputs a
Giles-voiced check-in: velocity vs plan, stories taking longer than expected,
design decisions to revisit. Pulls in PM for product questions if drift
detected. Sprint-run picks up pending check-in if user invokes it.

### Drift Detection

Sprint-monitor gains:
- Branch divergence check (story branches vs base branch merge conflict risk)
- Direct-push detection (commits to base branch during active sprint)
- Giles-voiced warnings in output

### Modified Files

| File | Changes |
|------|---------|
| `skills/sprint-run/agents/reviewer.md` | Three-pass review structure, read confidence section |
| `skills/sprint-run/agents/implementer.md` | Context budget section, confidence section in PR template |
| `skills/sprint-run/SKILL.md` | Pair review logic, mid-sprint check-in phase |
| `skills/sprint-run/references/story-execution.md` | Pair review variant in REVIEW transition |
| `skills/sprint-run/references/ceremony-demo.md` | Confidence signal probing |
| `skills/sprint-monitor/SKILL.md` | Mid-sprint check-in threshold, drift detection steps |
| `skills/sprint-monitor/scripts/check_status.py` | `check_branch_divergence()`, `check_direct_pushes()` |

---

## Chunk 4: Pipeline Scripts

All stdlib-only Python 3.10+, following existing patterns.

### Team Voice Extraction

**`scripts/team_voices.py`** — Parse saga/epic files for persona commentary
blocks (`> **Name:** ...`). Index by persona and saga/epic. Used by kickoff
to surface relevant voices when presenting stories.

### Requirements Traceability

**`scripts/traceability.py`** — Parse stories, PRDs, and test cases. Build
bidirectional map. Flag gaps: stories without tests, tests without stories,
PRD requirements without implementing stories. Output: markdown report +
stdout warnings.

### Test Plan Coverage

**`scripts/test_coverage.py`** — Compare planned test cases against actual
test files. Language-specific detection (Rust `#[test]`, Python `def test_*`,
Node `*.test.*`, Go `func Test*`). Report: implemented, missing, unplanned.

### Saga/Epic Management

**`scripts/manage_sagas.py`**, **`scripts/manage_epics.py`** — CRUD for
saga/epic files. Add/remove/reorder stories, update sprint allocations,
re-number cross-references, update dependency graphs.

### New Files

| File | Purpose |
|------|---------|
| `scripts/team_voices.py` | Extract persona commentary from saga/epic files |
| `scripts/traceability.py` | Bidirectional story↔PRD↔test mapping with gap detection |
| `scripts/test_coverage.py` | Planned vs actual test coverage by language |
| `scripts/manage_sagas.py` | Saga CRUD with cross-reference updates |
| `scripts/manage_epics.py` | Epic CRUD with story re-numbering |

### Integration Points

- `sprint-monitor` can run traceability periodically
- Kickoff ceremony uses team_voices output
- Demo ceremony uses test_coverage output
- Sprint-setup can call manage_sagas/epics during backlog modifications

---

## Explicitly Out of Scope

| Item | Reason |
|------|--------|
| First impressions | Removed from IDEAS-accepted |
| Understudy/stretch-casting | Not accepted |
| Warm-up exercises | Not accepted |
| Pre-mortem | Not accepted |
| Speculative branching | Not accepted |
| Prompt versioning | Not accepted |
| Offline mode | Not accepted |
| Story decomposition agent | Not accepted |
| Plugin composition hooks | Not accepted |
| Persona cache | Not accepted |
| Structured error escalation | Removed from IDEAS-accepted |
| Retro decay tracking | Removed from IDEAS-accepted |
| Persona workflow preferences | Removed from IDEAS-accepted |

---

## Validation Strategy

Each chunk updates Hexwise fixture and existing tests to validate:

- **Chunk 1:** sprint_init detects Giles, generates persona, adds to INDEX
- **Chunk 2:** analytics script runs against Hexwise GitHub data (mocked),
  history files parse correctly, DoD template generates
- **Chunk 3:** check_status.py drift detection against fixture branches (mocked)
- **Chunk 4:** team_voices extracts from Hexwise sagas, traceability produces
  clean report, test_coverage reports "no actual tests" correctly
