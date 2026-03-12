# Chunk 2: Persona Evolution — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Sprint History (separate files in Giles's voice), callbacks in agent templates, hybrid analytics (script + Giles commentary), and evolving Definition of Done.

**Architecture:** Sprint History lives in `{team_dir}/history/{name}.md`, written by Giles during retro. Agents read history before starting work. Analytics script computes metrics; Giles narrates. DoD is a config file refined by retros.

**Tech Stack:** Python 3.10+ stdlib (analytics script), Markdown (history files, DoD, ceremony updates)

**Spec:** `docs/superpowers/specs/2026-03-12-ideas-implementation-design.md` — Chunk 2 section

**Depends on:** Chunk 1 (Giles persona exists, ceremony retro has Giles as facilitator)

---

## File Structure

### Files to Create

| File | Purpose |
|------|---------|
| `scripts/sprint_analytics.py` | Compute sprint metrics from GitHub data + local sprint docs |
| `references/skeletons/definition-of-done.md.tmpl` | Baseline mechanical DoD template |
| `tests/fixtures/hexwise/docs/team/history/rusti.md` | Sample Sprint History (Giles voice) |
| `tests/fixtures/hexwise/docs/team/history/palette.md` | Sample Sprint History |
| `tests/fixtures/hexwise/docs/team/history/checker.md` | Sample Sprint History |
| `tests/fixtures/hexwise/docs/team/history/giles.md` | Sample Giles self-observations |

### Files to Modify

| File | Purpose |
|------|---------|
| `skills/sprint-run/agents/implementer.md` | Read history file, reference in design/PRs |
| `skills/sprint-run/agents/reviewer.md` | Read history file, reference in reviews |
| `skills/sprint-run/references/ceremony-retro.md` | New steps: run analytics, write history, propose DoD additions |
| `skills/sprint-run/references/ceremony-kickoff.md` | Giles reads analytics before kickoff |
| `skills/sprint-run/references/kanban-protocol.md` | "Done" references definition-of-done.md |
| `references/skeletons/persona.md.tmpl` | Note about Sprint History in history/ dir |
| `scripts/sprint_init.py` | Generate DoD file, create history/ directory |

---

## Task 0: Create Sprint History Fixture Files

**Files:**
- Create: `tests/fixtures/hexwise/docs/team/history/rusti.md`
- Create: `tests/fixtures/hexwise/docs/team/history/palette.md`
- Create: `tests/fixtures/hexwise/docs/team/history/checker.md`
- Create: `tests/fixtures/hexwise/docs/team/history/giles.md`

These demonstrate what accumulated Sprint History looks like — as if Hexwise has completed 2 sprints already.

- [ ] **Step 1: Create the history directory**

```bash
mkdir -p tests/fixtures/hexwise/docs/team/history
```

- [ ] **Step 2: Write Rusti's Sprint History**

Create `tests/fixtures/hexwise/docs/team/history/rusti.md`. Written in Giles's voice:

```markdown
# Sprint History — Rusti Ferris

Appended by Giles after each sprint retro. Do not edit manually.

---

### Sprint 1 — First Light

Rusti designed the Color struct with the intensity of someone defusing a bomb. Three iterations on the ownership model before she wrote a line of implementation. The result is, I will admit, elegant — the type system now prevents an entire category of errors that would have haunted us later. She is satisfied. I am relieved.

She and Checker had a productive exchange about hex parsing edge cases that I can only describe as two people who are very good at their jobs being very good at their jobs at each other. Rusti is now mildly paranoid about Unicode normalization, which I suspect will serve us well.

**Worked on:** US-0101 (hex parsing), US-0102 (RGB parsing), US-0104 (auto-detection)
**Surprised by:** The number of ways people write hex codes in the wild
**Wary of next time:** Floating-point conversion boundaries in HSL parsing

---

### Sprint 2 — Finding Words

Rusti spent most of the sprint arguing with the HSL parser and won. The conversion algorithm required more precision than she initially estimated, which she found personally offensive. She is now suspicious of all floating-point arithmetic, which frankly she should have been already.

Her output formatting work with Palette was smoother than I expected — they only argued about terminal color rendering twice, which I believe is a personal best. She deferred to Palette on ANSI display decisions with minimal visible discomfort.

**Worked on:** US-0103 (HSL parsing), US-0107 (formatted display, with Palette)
**Surprised by:** sRGB linearization edge cases near the 0.04045 threshold
**Wary of next time:** Any story that requires Palette and Rusti to share output code
```

- [ ] **Step 3: Write Palette's Sprint History**

Create `tests/fixtures/hexwise/docs/team/history/palette.md` in Giles's voice. Cover sprints 1-2, referencing US-0105 (CSS database), US-0106 (name lookup), US-0107 (display), US-0108 (descriptions). Include her fixture naming victories and the creative tension with Rusti on output formatting.

- [ ] **Step 4: Write Checker's Sprint History**

Create `tests/fixtures/hexwise/docs/team/history/checker.md` in Giles's voice. Cover sprints 1-2, referencing her adversarial test cases, her edge case discoveries, her "I tried to break it" reviews. Include her naming detente with Palette.

- [ ] **Step 5: Write Giles's Sprint History**

Create `tests/fixtures/hexwise/docs/team/history/giles.md` — Giles's own observations about the process:

```markdown
# Sprint History — Giles

Self-observations. Someone has to keep notes on the notetaker.

---

### Sprint 1 — First Light

The first kickoff ran fourteen minutes over because I let the dependency graph discussion go three rounds when two would have sufficed. I have adjusted my facilitation accordingly. Next time I'm printing the graph on the whiteboard. In large type.

Scope was not an issue — 16 SP with three experienced personas was comfortable. The main risk (Color struct design being load-bearing) was identified early and mitigated by letting Rusti iterate on it before anyone else started.

Sprint theme was implicitly "foundations" but I should have named it explicitly. Noted for Sprint 2.

---

### Sprint 2 — Finding Words

Named the sprint theme this time: "the sprint where we teach the oracle to speak." This helped Palette frame her output work as the main event rather than a finishing touch. Giles 1, Process Debt 0.

The mid-sprint check-in revealed that HSL parsing was taking longer than planned. Adjusted by deprioritizing the synesthetic descriptions until the parser stabilized. The right call — Palette's descriptions feature still shipped, just with a day less polish than she wanted.

Review rounds: Rusti averaged 1.5, Palette averaged 2.0. The extra round on Palette's work was consistently about error handling patterns, not functionality. I've suggested she adopt Rusti's error type approach for Sprint 3. She said she'd "think about it," which I have learned means she will do it but needs to believe it was her idea.
```

- [ ] **Step 6: Commit**

```bash
git add tests/fixtures/hexwise/docs/team/history/
git commit -m "feat: add sample Sprint History files to Hexwise fixture"
```

---

## Task 1: Update Agent Templates for Callbacks

**Files:**
- Modify: `skills/sprint-run/agents/implementer.md`
- Modify: `skills/sprint-run/agents/reviewer.md`

- [ ] **Step 1: Read current implementer.md**

Read `skills/sprint-run/agents/implementer.md` (158 lines).

- [ ] **Step 2: Add history reading to implementer**

Add after the "Your Assignment" section (after the Strategic Context and Test Plan Context blocks, before "Your Process"):

```markdown
### Sprint History
Read `{team_dir}/history/{persona_file_stem}.md` if it exists. This contains
Giles's observations about your work in previous sprints — what you struggled
with, what surprised you, what you'd be wary of. Let it color your decisions.

If a previous sprint's observations are relevant to this story, reference them
in your design notes and PR description. Continuity matters. If you got burned
by lock contention in Sprint 2, say so when you encounter a concurrency story
in Sprint 5. The reviewer will take your wariness seriously because it's earned.

If the file doesn't exist (first sprint), skip this section.
```

- [ ] **Step 3: Add history reading to reviewer**

Read `skills/sprint-run/agents/reviewer.md` (133 lines). Add after "Read `{team_dir}/{persona_file}` for your full character profile":

```markdown
Also read `{team_dir}/history/{persona_file_stem}.md` if it exists for your
accumulated sprint observations. And read the implementer's history file at
`{team_dir}/history/{implementer_file_stem}.md` — knowing what they've
struggled with before helps you focus your review. If they were wary of
floating-point edge cases after Sprint 2, check those areas harder.
```

- [ ] **Step 4: Commit**

```bash
git add skills/sprint-run/agents/implementer.md skills/sprint-run/agents/reviewer.md
git commit -m "feat: agent templates read Sprint History for callbacks"
```

---

## Task 2: Update Retro Ceremony for Sprint History + Analytics

**Files:**
- Modify: `skills/sprint-run/references/ceremony-retro.md`

- [ ] **Step 1: Read current ceremony-retro.md**

Read `skills/sprint-run/references/ceremony-retro.md`. Chunk 1 will have already rewritten this for the Giles/PM split — build on that version.

- [ ] **Step 2: Add three new steps after "Apply Changes"**

**New step — Run Analytics:**

```markdown
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
```

**New step — Write Sprint History:**

```markdown
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

Also append Giles's own entry to `{team_dir}/history/giles.md` — process
observations, facilitation learnings, what he'd adjust.
```

**New step — Definition of Done Review:**

```markdown
### 7. Definition of Done Review

Read `sprint-config/definition-of-done.md`. Based on this sprint's
experience, Giles proposes additions or modifications.

Examples of retro-driven DoD additions:
- "Error messages follow the format in rules.md" (after a sprint where they didn't)
- "Performance-sensitive code has benchmark results" (after a performance surprise)
- "New public APIs have usage examples" (after a reviewer noted missing docs)

Present proposed changes to the user. Apply only after approval.
```

- [ ] **Step 3: Commit**

```bash
git add skills/sprint-run/references/ceremony-retro.md
git commit -m "feat: retro ceremony gains Sprint History, analytics, and DoD review steps"
```

---

## Task 3: Update Kickoff Ceremony for Analytics Reference

**Files:**
- Modify: `skills/sprint-run/references/ceremony-kickoff.md`

- [ ] **Step 1: Add analytics reading to kickoff**

Add before the Story Walk section (after Sprint Goal and Saga Context):

```markdown
### 1.7. Process Context (if analytics exist)

If `{sprints_dir}/analytics.md` exists, Giles reads it before the story walk.
He surfaces relevant patterns during persona assignment and story discussion:

- "Last three sprints, {domain} stories averaged {X} review rounds. Plan accordingly."
- "The velocity trend suggests we can handle {X} SP this sprint, not {Y}."
- "{persona} has been carrying {X}% of the workload. Let's distribute more evenly."

This is not a formal presentation — Giles weaves the data into his facilitation
naturally. He's the one who remembers what happened last time.
```

- [ ] **Step 2: Commit**

```bash
git add skills/sprint-run/references/ceremony-kickoff.md
git commit -m "feat: kickoff ceremony reads analytics for process context"
```

---

## Task 4: Create sprint_analytics.py

**Files:**
- Create: `scripts/sprint_analytics.py`

Stdlib-only Python 3.10+. Follows existing patterns: `sys.path.insert` to reach `validate_config.py`, uses `subprocess` for `gh` CLI calls, outputs structured data.

- [ ] **Step 1: Write the script skeleton**

The script should:
1. Load config via `validate_config.load_config()`
2. Read sprint status from `{sprints_dir}/SPRINT-STATUS.md`
3. Query GitHub for milestone data: `gh api repos/{repo}/milestones`
4. Query GitHub for PR review data: `gh pr list --json ...`
5. Compute metrics:
   - Velocity: planned SP vs delivered SP (from milestone open/closed issue counts and SP labels)
   - Review rounds per story: count review comments/events per PR
   - Persona workload: count stories per persona from kanban labels
6. Output a Python dict (for programmatic use) or print a markdown summary (for CLI use)

Key functions:
- `compute_velocity(sprints_dir, sprint_number)` — read tracking files for planned/delivered
- `compute_review_rounds(repo, sprint_milestone)` — query PR review events
- `compute_cycle_times(sprints_dir, sprint_number)` — parse kanban timestamps from tracking files
- `compute_workload(repo, sprint_milestone)` — count stories per persona label
- `format_report(metrics)` — produce markdown summary
- `main()` — CLI entry point

- [ ] **Step 2: Write tests**

Add tests that use mocked `gh` output (following the `FakeGitHub` pattern from `tests/fake_github.py`). Test:
- `compute_velocity` with known SP values
- `compute_review_rounds` with mocked PR review data
- `format_report` produces valid markdown

- [ ] **Step 3: Run tests**

```bash
python -m unittest discover -s tests -v
```

- [ ] **Step 4: Commit**

```bash
git add scripts/sprint_analytics.py tests/
git commit -m "feat: add sprint_analytics.py for hybrid metrics computation"
```

---

## Task 5: Create Definition of Done Skeleton + Init Integration

**Files:**
- Create: `references/skeletons/definition-of-done.md.tmpl`
- Modify: `scripts/sprint_init.py`
- Modify: `skills/sprint-run/references/kanban-protocol.md`

- [ ] **Step 1: Write the DoD skeleton template**

```markdown
# Definition of Done

Baseline criteria for a story to be considered complete. This document evolves —
Giles proposes additions during retro based on sprint learnings.

## Mechanical (required for all stories)

- [ ] CI green on the PR branch
- [ ] PR approved by reviewer persona
- [ ] PR merged to base branch
- [ ] GitHub issue closed
- [ ] Burndown chart updated
- [ ] Story tracking file updated

## Semantic (refined by retros)

(No additions yet. After Sprint 1, Giles will propose additions based on
what the team learns.)
```

- [ ] **Step 2: Update sprint_init.py to generate DoD and history dir**

Add to `ConfigGenerator.generate()`:
1. Copy `definition-of-done.md.tmpl` to `sprint-config/definition-of-done.md`
2. Create `{team_dir}/history/` directory

- [ ] **Step 3: Update kanban-protocol.md**

Replace the hardcoded "done requires" list at line 35 with:

```markdown
- Moving to `done` requires ALL criteria in `sprint-config/definition-of-done.md`
  to be satisfied. Read that file before marking any story complete.
```

- [ ] **Step 4: Write tests for DoD generation**

Verify that after running ConfigGenerator, `sprint-config/definition-of-done.md` exists and contains the baseline criteria. Verify `{team_dir}/history/` directory exists.

- [ ] **Step 5: Run tests and commit**

```bash
python -m unittest discover -s tests -v
git add references/skeletons/definition-of-done.md.tmpl scripts/sprint_init.py skills/sprint-run/references/kanban-protocol.md tests/
git commit -m "feat: evolving Definition of Done with skeleton, init, and kanban integration"
```

---

## Task 6: Update Persona Skeleton Template

**Files:**
- Modify: `references/skeletons/persona.md.tmpl`

- [ ] **Step 1: Add Sprint History note to persona skeleton**

Add after the Improvisation Notes section:

```markdown
## Sprint History

Sprint observations for this persona are maintained separately by Giles at
`history/{persona_name}.md` in the team directory. They are not part of this
file — this file is your character; the history file is what happened to your
character. See the history file for accumulated sprint memory.
```

- [ ] **Step 2: Commit**

```bash
git add references/skeletons/persona.md.tmpl
git commit -m "feat: persona skeleton notes Sprint History location"
```

---

## Task 7: Update CLAUDE.md and CHEATSHEET.md

- [ ] **Step 1: Add new files to CLAUDE.md reference tables**

Add `scripts/sprint_analytics.py` to the Scripts table. Add `definition-of-done.md` to the Configuration System section. Note the `{team_dir}/history/` directory.

- [ ] **Step 2: Update CHEATSHEET.md with line numbers**

Add line-number index for `sprint_analytics.py`. Update ceremony-retro.md line references for the new steps.

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md CHEATSHEET.md
git commit -m "docs: update CLAUDE.md and CHEATSHEET.md for Chunk 2 additions"
```
