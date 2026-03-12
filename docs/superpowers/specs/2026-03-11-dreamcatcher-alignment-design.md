# Dreamcatcher Alignment Design

**Date:** 2026-03-11
**Status:** Approved
**Scope:** Process alignment + Hexwise extension

## Problem

Giles currently reads a flat layer of project docs: milestone story tables, basic persona files, rules, and dev guides. Projects with dreamcatcher-depth documentation — sagas, epics, PRDs, test plans, user story maps, rich personas — have most of their content ignored. An agent fed dreamcatcher-style docs and running Giles sprints would miss the design specs, test plan, strategic context, and team narrative that make those docs valuable.

## Goal

A: Make Giles's sprint process fully consume dreamcatcher-depth documentation so that the design described in those docs gets implemented completely.

B: Extend the Hexwise example to dreamcatcher-depth documentation as a digestible worked example that demonstrates every document type and cross-reference pattern.

## Architecture: Hybrid Context Assembly

Issues get **structure**, agents get **depth**.

- `populate_issues.py` extracts story metadata + acceptance criteria + epic/saga/test-case labels into GitHub issues — scannable on a board
- `sprint-run` reads PRD excerpts and test plan references at dispatch time and injects them into implementer/reviewer agent prompts — actionable context
- Ceremonies reference the hierarchy directly (kickoff walks saga context, demo verifies against test plan, retro feeds back to PRD open questions)

When deeper docs aren't configured, Giles behaves exactly as today. Every enhancement is guarded by "if configured."

---

## Section 1: Configuration & Detection

### New optional TOML keys

```toml
[paths]
# Existing (required)
team_dir       = "sprint-config/team"
backlog_dir    = "sprint-config/backlog"
sprints_dir    = "docs/dev-team/sprints"
rules_file     = "sprint-config/rules.md"
dev_guide      = "sprint-config/development.md"

# New (optional)
prd_dir        = "sprint-config/prd"
test_plan_dir  = "sprint-config/test-plan"
sagas_dir      = "sprint-config/backlog/sagas"
epics_dir      = "sprint-config/backlog/epics"
story_map      = "sprint-config/backlog/story-map/INDEX.md"
team_topology  = "sprint-config/team/team-topology.md"
feedback_dir   = "sprint-config/team/feedback"  # forward declaration — consumed by future Option C work
```

### sprint_init.py changes

`ProjectScanner` gets new detection methods:

- **PRD detection:** Scan for `docs/prd/`, `prd/`, or directories containing files with `## Requirements` + `## Design` headings
- **Test plan detection:** Scan for `docs/test-plan/`, `test-plan/`, or files with `## Test Cases` / `## Golden Path` headings
- **Saga/epic detection:** Scan for `docs/agile/sagas/`, `backlog/sagas/`, or files matching `S\d{2}` patterns; similarly for epics with `E-\d{4}` patterns
- **Story map detection:** Scan for `story-map/INDEX.md` or files with `## Activity` headings
- **Team topology detection:** Scan for `team-topology.md` or `who-we-are.md`
- **Feedback detection:** Scan for `feedback/` directories under team dirs

`ConfigGenerator` symlinks these into `sprint-config/` when found.

### validate_config.py changes

- New optional keys added (no validation failure if absent)
- New helper functions: `get_prd_dir()`, `get_test_plan()`, `get_sagas()`, `get_epics()`, `get_story_map()` — each returns `None` if not configured

### Skeleton templates

Delete all existing templates in `references/skeletons/` and replace with the full set. The old minimal `persona.md.tmpl`, `milestone.md.tmpl`, etc. are superseded — the new templates are the canonical format:

| Template | Purpose |
|---|---|
| `saga.md.tmpl` | Saga structure: team voices, epic index, dependency graph |
| `epic.md.tmpl` | Epic structure: story details, sprint allocation, test coverage |
| `story-detail.md.tmpl` | Full story: metadata table, narrative, ACs, tasks, test refs |
| `prd-index.md.tmpl` | PRD directory index with status/dependencies |
| `prd-section.md.tmpl` | Individual PRD: requirements, design, observability |
| `test-plan-index.md.tmpl` | Test plan summary with test pyramid |
| `golden-path.md.tmpl` | Golden path scenario structure |
| `test-case.md.tmpl` | Functional/adversarial test case structure |
| `story-map-index.md.tmpl` | Activity-based story map |
| `team-topology.md.tmpl` | Team structure with insight mapping |
| `persona.md.tmpl` | Rich persona: vital stats, origin, personality, relationships, improv notes |
| `milestone.md.tmpl` | Milestone with sprint breakdown, burndown, release gates |
| `project.toml.tmpl` | Updated with new optional keys |
| `backlog-index.md.tmpl` | Backlog routing table |
| `team-index.md.tmpl` | Team routing table |
| `rules.md.tmpl` | Project rules |
| `development.md.tmpl` | Dev process guide |

---

## Section 2: Issue Population

### Story extraction — two formats, one parser

The parser detects which format a story is in:

1. **Table row format:** `| US-XXXX | Title | Saga | SP | Priority |` — from milestone story tables
2. **Detail block format:** `### US-XXXX: Title` followed by metadata table, "As a..." narrative, acceptance criteria checkboxes, tasks checkboxes

When detail blocks exist (in epics or enriched milestones), those take precedence. The `Story` dataclass already has fields for `epic`, `blocked_by`, `blocks`, `test_cases`, `user_story`, `acceptance_criteria`. The existing `enrich_from_epics()` function is rewritten to handle the full detail block format — it becomes the primary parser, not a secondary enrichment pass.

### GitHub issue body

The existing `format_issue_body()` function is rewritten to produce the richer format below. The persona header uses a placeholder until kickoff assigns personas — sprint-run updates the issue body after assignment.

```markdown
> **{persona_name}** · {persona_role} · Implementation

## Story
**{story_id}** — {story_title} | Sprint {sprint} | {sp} SP | {priority}
**Epic:** {epic_id} — {epic_title}
**Saga:** {saga_id} — {saga_title}

## User Story
As a {persona}, I want {capability} so that {benefit}.

## Acceptance Criteria
- [ ] `AC-01`: {criterion}
- [ ] `AC-02`: {criterion}

## Tasks
- [ ] `T-XXXX-01`: {task} ({sp} SP)
- [ ] `T-XXXX-02`: {task} ({sp} SP)

## Dependencies
**Blocked by:** {story_ids}
**Blocks:** {story_ids}

## Test Coverage
**Test cases:** {TC-XXX-NNN, GP-NNN references}
```

### New labels

When epic/saga data is available: `epic:{epic_id}` labels (e.g., `epic:E-0101`). `bootstrap_github.py` gets a new `create_epic_labels()` function that parses epic IDs from files in `epics_dir`.

### What does NOT go into issues

Full PRD content (goes to agents at dispatch time), full test case details with steps/preconditions (go to agents), team voice commentary (used in ceremonies). Issues DO include PRD reference IDs (e.g., "See PRD-01") and test case IDs (e.g., "TC-PAR-001") — just not the full text of those documents.

---

## Section 3: Agent Context Injection

### Implementer agent

`sprint-run` populates the implementer prompt with:

1. **PRD context:** Requirements + Design sections from PRDs matching the story's epic/saga. Injected into `{relevant_prd_excerpts}`.
2. **Test case references:** Preconditions + expected results from test cases in the story's `test_cases` field. Injected as `### Test Plan Context`.
3. **Saga context:** Strategic "why" — saga goal, where this story fits. Injected as `### Strategic Context`.
4. **Dependency status:** Current GitHub state of `blocked_by` / `blocks` stories. Injected into `{dependencies}`.

### Reviewer agent

1. **Test case checklist:** Referenced test cases become a verification checklist in `### Test Coverage Verification`.
2. **PRD non-functional requirements:** Performance thresholds, memory budgets from relevant PRD. Added to review checklist.
3. **PR-is-self-contained rule still holds.** PR description is primary; test/PRD context is supplementary.

### PRD-to-story matching

PRDs map to stories through the **epic numbering convention**. PRD directories are numbered (`01-color-parsing/`, `02-contrast-access/`). Epics are numbered with a saga prefix (`E-0101`, `E-0201`). The mapping is:

- PRD number = epic's first two digits (the saga number)
- `E-01xx` stories → `prd_dir/01-*/`
- `E-02xx` stories → `prd_dir/02-*/`

When this convention doesn't hold (e.g., a story spans multiple PRD domains), the story's epic file can include an explicit `PRD: PRD-01, PRD-03` field in its metadata table, which overrides convention-based matching.

Sprint-run reads the PRD index file (`prd_dir/INDEX.md`) to discover available PRD directories and their domain names. For each story, it resolves the PRD path, then reads the `## Requirements` and `## Design` sections from files in that directory.

### Test case lookup

Test case IDs (e.g., `TC-PAR-001`, `GP-003`) are stored in the story's `test_cases` field as a comma-separated list. Resolution works by:

1. **ID prefix → file mapping:** The test plan index (`test_plan_dir/README.md`) contains a document map table linking prefixes to files:
   - `GP-*` → `01-golden-paths.md`
   - `TC-PAR-*` → `02-functional-tests.md`
   - `TC-ADV-*` → `03-adversarial-tests.md`
2. **ID → section heading:** Within each file, test cases are sections headed `### TC-PAR-001: Title` or `### GP-001: Title`
3. **Extraction:** Sprint-run reads from the section heading through the next `###` heading, capturing preconditions, steps, and expected results

If a test case ID can't be resolved (file missing, heading not found), sprint-run logs a warning and continues — missing test context is non-fatal.

### Orchestration logic

This logic lives in `sprint-run/SKILL.md` as instructions for the orchestrator. It is NOT a separate Python script — it's guidance for how the orchestrating agent assembles context before dispatching implementer/reviewer subagents.

```
For each story being dispatched:
  1. Read story metadata (epic, saga, test_cases from GitHub issue or tracking file)
  2. If prd_dir configured:
     - Resolve PRD path from epic number (convention) or explicit PRD field (override)
     - Read Requirements + Design sections from matching PRD files
  3. If test_plan_dir configured:
     - Parse test_cases field (comma-separated IDs)
     - Map each ID prefix to test plan file via README.md document map
     - Extract each test case section by heading
  4. If sagas_dir configured:
     - Read saga file matching story's saga ID (S01 → sagas/S01-*.md)
     - Extract saga goal and relevant team voices
  5. Assemble implementer prompt: inject PRD into {relevant_prd_excerpts},
     test cases into new ### Test Plan Context section,
     saga goal into new ### Strategic Context section
  6. After implementation, assemble reviewer prompt: inject test cases into
     new ### Test Coverage Verification section, PRD non-functional
     requirements into review checklist
```

The `### Test Plan Context`, `### Strategic Context`, and `### Test Coverage Verification` sections are NEW additions to the implementer and reviewer agent templates (`agents/implementer.md` and `agents/reviewer.md`). They use the same placeholder-token pattern as the existing `{relevant_prd_excerpts}`.

When paths aren't configured, these sections are omitted and prompts work exactly as today.

---

## Section 4: Ceremony Enhancements

### Kickoff

1. **Saga context (new step, before Story Walk):** PM presents saga goals for this sprint's work. Multiple active sagas each get brief framing.
2. **Story walk enriched:** PM includes epic context (position in epic, what's completed/remaining), PRD references (requirement IDs), test plan references (test case IDs).
3. **Risk discussion enriched:** Personas can reference PRD open questions.

### Demo

1. **Test plan verification (new step):** Walk referenced test cases and confirm coverage. Gaps recorded.
2. **Traceability summary (new output section):**
   ```markdown
   ## Traceability
   | Story | Epic | Test Cases Covered | Test Cases Gaps |
   |-------|------|--------------------|-----------------|
   ```

### Retro

1. **PRD feedback loop:** Design issues route back as proposed changes to PRD sections — not just rules/dev-guide. PRDs use a `## Open Questions` section (standard heading in the `prd-section.md.tmpl` template) for unresolved design decisions. Retro findings that reveal design gaps get added there, or promote open questions to resolved requirements in `## Requirements`.

---

## Section 5: Hexwise Extension

### Product concept

Hexwise is a **color oracle for the terminal** — you give it colors, it tells you things about them with more personality than strictly necessary.

### Features

| Feature | Flavor |
|---|---|
| Parse hex/RGB/HSL | "Ah, `#FF5733` — that's 255 red, 87 green, 51 blue. A sunset having a panic attack." |
| Named color lookup | Knows all 148 CSS named colors. Has opinions about `PapayaWhip`. |
| Contrast checking | WCAG AA/AAA verdicts delivered with appropriate alarm or approval |
| Palette generation | Complementary, analogous, triadic — presented as cast lists |
| Color descriptions | Synesthetic flavor text: warmth, mood, personality |
| Batch mode | Reads colors from stdin, judges them all |

### Personas

**Rusti Ferris** — Lead/Architect. Former embedded systems engineer who discovered Rust at a conference and never emotionally recovered. Treats zero-cost abstractions as a lifestyle philosophy. Has a mass-produced Ferris plushie she insists is "one of a kind." Privately worried the project is too fun to be taken seriously.

**Palette Jones** — Feature Dev. Art school dropout turned programmer. Knows color theory the way sommeliers know wine. Will mass-rename variables for aesthetic reasons. Genuinely believes `PapayaWhip` is a war crime against the CSS specification. Names test fixtures after Pantone Colors of the Year.

**Checker Macready** — QA/Reviewer. Former penetration tester who pivoted to QA because "breaking things on purpose should be someone's whole job." Trusts nothing, verifies everything, delivers verdicts with bone-dry humor. Signs off reviews with "I tried to break it. It held. For now."

Each persona: 60-80 lines with vital stats, origin, professional identity, quirks, relationships, improv notes.

### Sagas

**S01 — Core Color Operations** ("Teach the oracle to see")

**S02 — The Toolkit** ("Give the oracle opinions")

### Epics

| Epic | Name | Stories | Saga |
|---|---|---|---|
| E-0101 | Color Parsing & Conversion | 4 | S01 |
| E-0102 | Named Color Database | 2 | S01 |
| E-0103 | Output & Formatting | 2 | S01 |
| E-0201 | Contrast Checking | 3 | S02 |
| E-0202 | Palette Generation | 3 | S02 |
| E-0203 | Batch Mode & Error UX | 3 | S02 |

~20 stories, 3 milestones, 5 sprints.

### PRDs

| PRD | Domain | Content |
|---|---|---|
| PRD-01 | Color Parsing & Conversion | Format matrix, conversion algorithms, ColorValue struct |
| PRD-02 | Contrast & Accessibility | WCAG 2.1 formulas, AA/AAA thresholds |
| PRD-03 | Palette Generation | Color wheel math, output formats |

### Test plan

| Document | Content |
|---|---|
| Golden paths (4-5) | First Impression, Contrast Question, Palette Party, Batch Judgment |
| Functional tests (~30) | TC-PAR, TC-CON, TC-PAL, TC-OUT domains |
| Adversarial tests (~10) | Empty input, invalid hex, Unicode tricks, edge ratios |
| Traceability matrix | Story-to-test bidirectional mapping |

### Document structure

```
hexwise/docs/
├── agile/
│   ├── README.md
│   ├── sagas/          (2 files)
│   ├── epics/          (6 files)
│   └── milestones/     (3 files)
├── prd/
│   ├── INDEX.md
│   ├── 01-color-parsing/
│   ├── 02-contrast-access/
│   └── 03-palette-gen/
├── test-plan/
│   ├── README.md
│   ├── 01-golden-paths.md
│   ├── 02-functional-tests.md
│   ├── 03-adversarial-tests.md
│   └── 04-traceability.md
├── user-stories/
│   └── story-map/INDEX.md
└── team/
    ├── INDEX.md
    ├── team-topology.md
    ├── rusti.md
    ├── palette.md
    └── checker.md
```

### Scale targets

| Artifact | Count | Lines/file |
|---|---|---|
| Sagas | 2 | 80-120 |
| Epics | 6 | 100-150 |
| Stories | ~20 | ~20 each (in epics) |
| Milestones | 3 | 80-120 |
| Personas | 3 | 60-80 |
| PRD sections | 3 domains, 6 files | 60-100 |
| Golden paths | 4-5 | 30-50 |
| Functional tests | ~30 | 10-15 each |
| Adversarial tests | ~10 | 10-15 each |
| Traceability matrix | 1 | 40-60 |

### The vibe

Technical rigor is real — WCAG formulas are correct, acceptance criteria are measurable, test cases are thorough. But the voice is warm and a little extra. Someone reading these should think "I want to build something like this" and also smile at least twice.

---

## Section 6: Future Work Breadcrumbs (Option C)

Documented in `docs/superpowers/plans/future-full-pipeline.md` for a future agent to pick up.

### Saga/Epic Management Scripts

- **What:** `scripts/manage_sagas.py`, `scripts/manage_epics.py` — CRUD operations on sagas/epics, automatic re-numbering
- **Why:** Let Giles manage the hierarchy programmatically instead of relying on hand-edited markdown
- **Inputs:** `sagas_dir`, `epics_dir` from config
- **Outputs:** Updated saga/epic files, re-numbered story references
- **Depends on:** Section 1 (config keys and detection)
- **Scope:** Medium — file parsing + rewriting + cross-reference updates

### Requirements Traceability

- **What:** `scripts/traceability.py` — parse stories, PRDs, test cases; build bidirectional map
- **Why:** Flag coverage gaps: stories with no tests, tests with no stories, PRD requirements with no stories
- **Inputs:** `epics_dir`, `prd_dir`, `test_plan_dir`
- **Outputs:** Traceability report (markdown), gap warnings
- **Depends on:** Section 2 (story extraction with test_cases, epic, saga fields)
- **Scope:** Medium — parsing + cross-referencing + report generation

### Test Plan Coverage Reporting

- **What:** `scripts/test_coverage.py` — compare planned test cases against actual test files
- **Why:** Know which planned tests are implemented, missing, or exist outside the plan
- **Inputs:** `test_plan_dir`, project test files (detected by language)
- **Outputs:** Coverage report, could integrate with `sprint-monitor`
- **Depends on:** Section 3 (test case extraction)
- **Scope:** Medium-Large — needs language-specific test file parsing

### Team Voice Extraction

- **What:** `scripts/team_voices.py` — parse saga/epic files for persona commentary blocks
- **Why:** Surface relevant voices during ceremonies automatically
- **Inputs:** `sagas_dir`, `epics_dir`, persona commentary format ("> **Name:** ...")
- **Outputs:** Indexed commentary by persona and story/epic
- **Depends on:** Section 1 (config keys), Section 4 (ceremony enhancements)
- **Scope:** Small — regex extraction + indexing

### Sprint Analytics

- **What:** `scripts/sprint_analytics.py` — velocity trends, SP accuracy, persona workload, epic completion
- **Why:** Data-driven retro observations, calibrate future planning
- **Inputs:** `sprints_dir` (sprint status, kickoff/demo/retro docs), GitHub milestone data
- **Outputs:** Analytics report, trend charts (text-based), retro data injection
- **Depends on:** Section 4 (retro enhancements)
- **Scope:** Medium — data collection + trend analysis
