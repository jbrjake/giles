# Dreamcatcher Alignment Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Giles consume dreamcatcher-depth documentation (sagas, epics, PRDs, test plans, rich personas) and extend Hexwise as a worked example.

**Architecture:** Hybrid context assembly — issues get structure (metadata + ACs), agents get depth (PRD excerpts + test cases at dispatch time). All new features guarded by "if configured" for graceful degradation.

**Tech Stack:** Python 3.10+ (stdlib only), Markdown, TOML

**Spec:** `docs/superpowers/specs/2026-03-11-dreamcatcher-alignment-design.md`

**Reference:** `references/dreamcatcher/` — do NOT modify these files; use them as format examples.

---

## File Structure

### Files to Create

**Skeleton templates** (`references/skeletons/`):
- `saga.md.tmpl` — saga structure with team voices, epic index
- `epic.md.tmpl` — epic with detailed stories, sprint allocation
- `story-detail.md.tmpl` — full story format (metadata table, ACs, tasks)
- `prd-index.md.tmpl` — PRD directory index
- `prd-section.md.tmpl` — individual PRD section
- `test-plan-index.md.tmpl` — test plan summary
- `golden-path.md.tmpl` — golden path scenario
- `test-case.md.tmpl` — functional/adversarial test case
- `story-map-index.md.tmpl` — activity-based story map
- `team-topology.md.tmpl` — team structure with insight mapping

**Hexwise docs** (`tests/fixtures/hexwise/docs/`):
- `agile/README.md` — backlog summary
- `agile/sagas/S01-core.md`, `S02-toolkit.md`
- `agile/epics/E-0101-parsing.md`, `E-0102-named-colors.md`, `E-0103-output.md`, `E-0201-contrast.md`, `E-0202-palettes.md`, `E-0203-batch.md`
- `prd/INDEX.md`
- `prd/01-color-parsing/formats-design.md`, `reference.md`
- `prd/02-contrast-access/wcag-design.md`, `reference.md`
- `prd/03-palette-gen/algorithms-design.md`, `reference.md`
- `test-plan/README.md`, `01-golden-paths.md`, `02-functional-tests.md`, `03-adversarial-tests.md`, `04-traceability.md`
- `user-stories/story-map/INDEX.md`
- `team/team-topology.md`

**Other:**
- `docs/superpowers/plans/future-full-pipeline.md` — option C breadcrumbs

### Files to Modify

**Skeleton templates** (rewrite with richer format):
- `references/skeletons/persona.md.tmpl`
- `references/skeletons/milestone.md.tmpl`
- `references/skeletons/project.toml.tmpl`
- `references/skeletons/backlog-index.md.tmpl`
- `references/skeletons/team-index.md.tmpl`

**Python scripts:**
- `scripts/validate_config.py` — add optional keys + helper functions
- `scripts/sprint_init.py` — add detection methods for PRDs, test plans, sagas, epics, story map
- `skills/sprint-setup/scripts/populate_issues.py` — detail block parser + enriched issue body
- `skills/sprint-setup/scripts/bootstrap_github.py` — epic label creation

**Sprint-run process:**
- `skills/sprint-run/SKILL.md` — orchestration logic for context injection
- `skills/sprint-run/agents/implementer.md` — new `### Test Plan Context` and `### Strategic Context` sections
- `skills/sprint-run/agents/reviewer.md` — new `### Test Coverage Verification` section
- `skills/sprint-run/references/ceremony-kickoff.md` — saga context step, enriched story walk
- `skills/sprint-run/references/ceremony-demo.md` — test plan verification, traceability summary
- `skills/sprint-run/references/ceremony-retro.md` — PRD feedback loop

**Hexwise fixture** (rewrite for depth):
- `tests/fixtures/hexwise/docs/team/INDEX.md`
- `tests/fixtures/hexwise/docs/team/rusti.md`, `palette.md`, `checker.md`
- `tests/fixtures/hexwise/docs/backlog/INDEX.md`
- `tests/fixtures/hexwise/docs/backlog/milestones/milestone-1.md`, `milestone-2.md` + new `milestone-3.md`
- `tests/fixtures/hexwise/RULES.md`, `DEVELOPMENT.md`

**Tests:**
- `tests/test_hexwise_setup.py` — update for new detection + richer parsing

**Meta-docs:**
- `CLAUDE.md` — update tables with new files and line refs
- `CHEATSHEET.md` — update line-number indices

---

## Chunk 1: Skeleton Templates & Configuration

### Task 1: Rewrite Existing Skeleton Templates

Rewrite the existing templates to match dreamcatcher depth. These define the canonical format for all Giles projects.

**Files:**
- Modify: `references/skeletons/persona.md.tmpl`
- Modify: `references/skeletons/milestone.md.tmpl`
- Modify: `references/skeletons/project.toml.tmpl`
- Modify: `references/skeletons/backlog-index.md.tmpl`
- Modify: `references/skeletons/team-index.md.tmpl`

- [ ] **Step 1: Rewrite persona.md.tmpl**

Replace the current 20-line template with the rich persona format. Use `references/dreamcatcher/docs/dev-team/01-sable-nakamura.md` as the structural reference, scaled down to the TODO-template level:

```markdown
# TODO: Full Name

## Line Index
Lines 1-6:    Index and quick reference
Lines 8-15:   Vital stats
Lines 17-30:  Origin story
Lines 32-45:  Professional identity
Lines 47-58:  Personality and quirks
Lines 60-70:  Relationships
Lines 72-80:  Improvisation notes

## Vital Stats
- **Age:** TODO
- **Location:** TODO
- **Education:** TODO
- **Languages:** TODO

## Origin Story
TODO: 2-3 paragraphs. How did this person end up here? What shaped their
perspective? Include specific jobs, formative experiences, and the thing
that made them care about this domain.

## Professional Identity
TODO: Coding style, technical obsessions, what they optimize for, what
they refuse to compromise on. Their code review philosophy.

## Personality and Quirks
TODO: Communication style, humor, verbal tics, catchphrases. What they
do when frustrated. What they do when excited. Silence tolerance.

## Relationships
TODO: Named relationships with other team members. Specific tensions,
mutual respect points, collaboration patterns. Who do they eat lunch
with? Who do they argue with productively?

## Improvisation Notes
TODO: How to play this character. Voice (measured? energetic? dry?),
pacing, signature phrases. What earns their trust. What breaks it.
Core wound or vulnerability that drives their excellence.
```

- [ ] **Step 2: Rewrite milestone.md.tmpl**

Replace the current 23-line template. Reference `references/dreamcatcher/docs/agile/sprints/milestone-1-walking-skeleton.md` for structure:

```markdown
# TODO: Milestone Name

TODO: 1-2 sentences describing what this milestone achieves and why it matters.

| Field | Value |
|-------|-------|
| Sprints | TODO: N-M |
| Total SP | TODO |
| Release | TODO: R1/R2/R3 |

---

### Sprint 1: TODO: Sprint Name (Weeks 1-2)

**Sprint Goal:** TODO: One sentence describing what this sprint proves.

| Story | Title | Epic | Saga | SP | Priority |
|-------|-------|------|------|----|----------|
| US-0101 | TODO: Story title | E-0101 | S01 | 5 | P0 |
| US-0102 | TODO: Story title | E-0101 | S01 | 3 | P1 |

**Total SP:** 8

**Key Deliverables:**
- TODO: What's shippable after this sprint

**Sprint Acceptance Criteria:**
- [ ] TODO: Criterion 1
- [ ] TODO: Criterion 2

**Risks & Dependencies:**
- TODO: What could block this sprint

---

## Cumulative Burndown

| Sprint | Stories Done | Cumulative SP | % Complete |
|--------|-------------|---------------|------------|
| 1 | TODO | TODO | TODO |

## Release Gate Checklist
- [ ] TODO: Gate criterion 1
- [ ] TODO: Gate criterion 2
```

- [ ] **Step 3: Update project.toml.tmpl**

Add the new optional keys to the existing template. Read the current file at `references/skeletons/project.toml.tmpl` (53 lines). Add after the existing `[paths]` entries:

```toml
# Optional — enable deeper doc consumption (sagas, epics, PRDs, test plans)
# prd_dir        = "sprint-config/prd"
# test_plan_dir  = "sprint-config/test-plan"
# sagas_dir      = "sprint-config/backlog/sagas"
# epics_dir      = "sprint-config/backlog/epics"
# story_map      = "sprint-config/backlog/story-map/INDEX.md"
# team_topology  = "sprint-config/team/team-topology.md"
# feedback_dir   = "sprint-config/team/feedback"
```

- [ ] **Step 4: Update backlog-index.md.tmpl and team-index.md.tmpl**

`backlog-index.md.tmpl` — add saga/epic routing rows:

```markdown
# Backlog

| Artifact | Path |
|----------|------|
| Milestones | `milestones/` |
| Sagas | `sagas/` (if present) |
| Epics | `epics/` (if present) |
| Story Map | `story-map/INDEX.md` (if present) |
```

`team-index.md.tmpl` — add topology reference:

```markdown
# Team

| Name | File | Role | Domain Keywords |
|------|------|------|----------------|
| TODO | TODO.md | TODO | TODO |

See also: `team-topology.md` (if present)
```

- [ ] **Step 5: Commit**

```bash
git add references/skeletons/persona.md.tmpl references/skeletons/milestone.md.tmpl \
      references/skeletons/project.toml.tmpl references/skeletons/backlog-index.md.tmpl \
      references/skeletons/team-index.md.tmpl
git commit -m "feat: rewrite skeleton templates to dreamcatcher depth"
```

---

### Task 2: Create New Skeleton Templates

Create the 10 new template files that define formats for sagas, epics, PRDs, test plans, and story maps.

**Files:**
- Create: `references/skeletons/saga.md.tmpl`
- Create: `references/skeletons/epic.md.tmpl`
- Create: `references/skeletons/story-detail.md.tmpl`
- Create: `references/skeletons/prd-index.md.tmpl`
- Create: `references/skeletons/prd-section.md.tmpl`
- Create: `references/skeletons/test-plan-index.md.tmpl`
- Create: `references/skeletons/golden-path.md.tmpl`
- Create: `references/skeletons/test-case.md.tmpl`
- Create: `references/skeletons/story-map-index.md.tmpl`
- Create: `references/skeletons/team-topology.md.tmpl`

- [ ] **Step 1: Create saga.md.tmpl**

Reference `references/dreamcatcher/docs/agile/sagas/S01-walking-skeleton.md` for structure. Template should include: saga summary table, team voices section, epic index, dependency graph placeholder, sprint allocation, release gate checklist.

```markdown
# S{XX} — TODO: Saga Name

TODO: One paragraph describing the strategic initiative.

| Field | Value |
|-------|-------|
| Stories | TODO |
| Epics | TODO |
| Total SP | TODO |
| Sprints | TODO |

## Team Voices

> **TODO: PM Name:** TODO: Scope/priority perspective
>
> **TODO: Dev Name:** TODO: Technical perspective
>
> **TODO: QA Name:** TODO: Risk/testing perspective

## Epic Index

| Epic | Name | Stories | SP |
|------|------|---------|-----|
| E-{XXYY} | TODO | TODO | TODO |

## Sprint Allocation

| Sprint | Stories | SP |
|--------|---------|-----|
| TODO | TODO | TODO |

## Dependency Graph

```
TODO: ASCII art or text description of blocking relationships
```

## Release Gate Checklist
- [ ] TODO: Gate criterion 1
- [ ] TODO: Gate criterion 2
```

- [ ] **Step 2: Create epic.md.tmpl**

Reference `references/dreamcatcher/docs/agile/epics/E-0101-mvp-ingestion.md` for structure. Template includes: epic summary, sprint allocation, full story details using the detail block format, dependencies, test coverage.

```markdown
# E-{XXYY} — TODO: Epic Name

TODO: One paragraph describing what this epic delivers.

| Field | Value |
|-------|-------|
| Saga | S{XX} |
| Stories | TODO |
| Total SP | TODO |
| Sprints | TODO |
| Blocked By | TODO or — |
| Blocks | TODO or — |

## Sprint Allocation

| Sprint | Stories |
|--------|---------|
| TODO | TODO |

## Stories

### US-{AASS}: TODO: Story Title

| Field | Value |
|-------|-------|
| Story Points | TODO: {1, 2, 3, 5, 8, 13} |
| Priority | TODO: {P0, P1, P2} |
| Release | TODO: {R1, R2, R3} |
| Saga | S{XX} |
| Epic | E-{XXYY} |
| Personas | TODO |
| Blocked By | TODO or — |
| Blocks | TODO or — |
| Test Cases | TODO: TC-XXX-NNN, GP-NNN or — |

**As a** TODO: persona, **I want** TODO: capability **so that** TODO: benefit.

**Acceptance Criteria:**
- [ ] `AC-01`: TODO: Verifiable condition with measurable threshold
- [ ] `AC-02`: TODO: Another verifiable condition

**Tasks:**
- [ ] `T-{AASS}-01`: TODO: Implementation task (N SP)
- [ ] `T-{AASS}-02`: TODO: Implementation task (N SP)

---

(Repeat ### US-{AASS} block for each story in this epic)

## Epic Dependencies

```
TODO: ASCII art or text description of story-to-story blocking
```

## Test Coverage Summary

| Story | Test Cases |
|-------|-----------|
| US-{AASS} | TODO |
```

- [ ] **Step 3: Create story-detail.md.tmpl**

This is the standalone story format (used when stories appear outside epics):

```markdown
### US-{AASS}: TODO: Story Title

| Field | Value |
|-------|-------|
| Story Points | TODO: {1, 2, 3, 5, 8, 13} |
| Priority | TODO: {P0, P1, P2} |
| Release | TODO: {R1, R2, R3} |
| Saga | S{XX} |
| Epic | E-{XXYY} |
| Personas | TODO |
| Blocked By | TODO or — |
| Blocks | TODO or — |
| Test Cases | TODO: TC-XXX-NNN, GP-NNN or — |

**As a** TODO: persona, **I want** TODO: capability **so that** TODO: benefit.

**Acceptance Criteria:**
- [ ] `AC-01`: TODO: Verifiable condition with measurable threshold
- [ ] `AC-02`: TODO: Another verifiable condition

**Tasks:**
- [ ] `T-{AASS}-01`: TODO: Implementation task (N SP)
- [ ] `T-{AASS}-02`: TODO: Implementation task (N SP)
```

- [ ] **Step 4: Create PRD templates (prd-index.md.tmpl, prd-section.md.tmpl)**

Reference `references/dreamcatcher/docs/prd/01-log-ingestion-parsing/` for structure.

`prd-index.md.tmpl`:
```markdown
# Product Requirements Documents

| PRD | Domain | Status | Dependencies | Blocked By | Blocks |
|-----|--------|--------|-------------|------------|--------|
| PRD-01 | TODO | Draft | TODO or None | TODO or None | TODO or None |

## Document Map

| PRD | Files | Lines |
|-----|-------|-------|
| PRD-01 | TODO | TODO |
```

`prd-section.md.tmpl`:
```markdown
# PRD-{XX}: TODO: Domain Name

| Field | Value |
|-------|-------|
| Status | Draft |
| Last Updated | TODO: YYYY-MM-DD |
| Dependencies | TODO or None |
| Blocked By | TODO or None |
| Blocks | TODO or None |

## Purpose

TODO: 1-2 paragraphs. What problem does this subsystem solve?

## Requirements

### Functional

- **REQ-{PREFIX}-001:** TODO: Requirement description
- **REQ-{PREFIX}-002:** TODO: Requirement description

### Non-Functional

- **REQ-{PREFIX}-NF-001:** TODO: Performance/scale/memory requirement with threshold

## Design

TODO: Data structures, algorithms, key design decisions with rationale.

## Observability

TODO: Metrics, traces, health checks.

## Open Questions

- TODO: Unresolved design decision 1
- TODO: Unresolved design decision 2

## Future Work

- TODO: Known extensions not in current scope
```

- [ ] **Step 5: Create test plan templates (test-plan-index.md.tmpl, golden-path.md.tmpl, test-case.md.tmpl)**

Reference `references/dreamcatcher/docs/test-plan/` for structure.

`test-plan-index.md.tmpl`:
```markdown
# Test Plan

| Metric | Count |
|--------|-------|
| Golden Path Scenarios | TODO |
| Functional Test Cases | TODO |
| Adversarial Test Cases | TODO |
| **Total** | **TODO** |

## Test Pyramid

```
           Golden Paths (E2E)
          Adversarial + Perf
         Integration Tests
        Unit Tests (>80% core)
```

## Documents

| File | Content |
|------|---------|
| `01-golden-paths.md` | End-to-end smoke scenarios |
| `02-functional-tests.md` | Domain-specific functional tests |
| `03-adversarial-tests.md` | Edge cases, chaos, security |
| `04-traceability.md` | Story-to-test bidirectional mapping |
```

`golden-path.md.tmpl`:
```markdown
### GP-{NNN}: TODO: Scenario Name

**Personas:** TODO

**Given:** TODO: Starting state
**When:**
1. TODO: Step 1
2. TODO: Step 2
**Then:**
- TODO: Expected result 1
- TODO: Expected result 2

**Boundary tests:**
- TODO: Edge case variant 1

**Error variant:**
- TODO: What happens when something goes wrong

**Traceability:** TODO: US-XXXX, TC-XXX-NNN
```

`test-case.md.tmpl`:
```markdown
### TC-{PREFIX}-{NNN}: TODO: Test Case Title

**Persona:** TODO
**Priority:** TODO: P0/P1/P2
**Story:** TODO: US-XXXX

**Preconditions:**
- TODO: Setup requirement 1

**Steps:**
1. TODO: Action 1
2. TODO: Action 2

**Expected Results:**
- TODO: Verifiable outcome 1
- TODO: Verifiable outcome 2

**Acceptance:** PASS if TODO: condition
```

- [ ] **Step 6: Create story-map-index.md.tmpl and team-topology.md.tmpl**

Reference `references/dreamcatcher/docs/user-stories/story-map/INDEX.md` and `references/dreamcatcher/docs/dev-team/team-topology.md`.

`story-map-index.md.tmpl`:
```markdown
# User Story Map

## Activities

| # | Activity | Description |
|---|----------|-------------|
| 1 | TODO | TODO |
| 2 | TODO | TODO |

## Release Tiers

- **R1:** TODO: Thinnest end-to-end slice
- **R2:** TODO: Full v1
- **R3:** TODO: Fast-follow

## Stories by Activity

### Activity 1: TODO

**R1:**
- US-{AASS}: TODO: Title (TODO: personas)

**R2:**
- US-{AASS}: TODO: Title (TODO: personas)
```

`team-topology.md.tmpl`:
```markdown
# Team Topology

## Structure

| Function | Members |
|----------|---------|
| Engineering | TODO |
| QA | TODO |
| Product | TODO |

## Special Insight Mapping

| Background | Person | Relevance |
|-----------|--------|-----------|
| TODO: Unique expertise | TODO: Name | TODO: Why it matters |

## Personality Map

TODO: Bonds, tensions, communication patterns between team members.
Who works well together? Where is productive friction?
```

- [ ] **Step 7: Commit**

```bash
git add references/skeletons/saga.md.tmpl references/skeletons/epic.md.tmpl \
      references/skeletons/story-detail.md.tmpl references/skeletons/prd-index.md.tmpl \
      references/skeletons/prd-section.md.tmpl references/skeletons/test-plan-index.md.tmpl \
      references/skeletons/golden-path.md.tmpl references/skeletons/test-case.md.tmpl \
      references/skeletons/story-map-index.md.tmpl references/skeletons/team-topology.md.tmpl
git commit -m "feat: add skeleton templates for sagas, epics, PRDs, test plans, story maps"
```

---

### Task 3: Update validate_config.py

Add optional TOML keys and helper functions for accessing new doc paths.

**Files:**
- Modify: `scripts/validate_config.py:177` (optional keys), `:450+` (new helpers)
- Test: `tests/test_hexwise_setup.py`

- [ ] **Step 1: Write test for new helper functions**

Add to `tests/test_hexwise_setup.py`:

```python
def test_optional_paths_absent(self):
    """Optional doc paths return None when not configured."""
    from validate_config import (
        get_prd_dir, get_test_plan_dir, get_sagas_dir,
        get_epics_dir, get_story_map,
    )
    config = load_config("sprint-config")  # cwd is project_dir per setUpClass
    # Hexwise doesn't have these yet
    assert get_prd_dir(config) is None
    assert get_test_plan_dir(config) is None
    assert get_sagas_dir(config) is None
    assert get_epics_dir(config) is None
    assert get_story_map(config) is None
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/jonr/Documents/non-nitro-repos/giles && python -m pytest tests/test_hexwise_setup.py::TestHexwiseSetup::test_optional_paths_absent -v
```

Expected: FAIL — `get_prd_dir` not importable.

- [ ] **Step 3: Add helper functions to validate_config.py**

Add after `get_base_branch()` (line 450):

```python
def get_prd_dir(config: dict) -> Path | None:
    """Return PRD directory path, or None if not configured."""
    val = config.get("paths", {}).get("prd_dir")
    if not val:
        return None
    p = Path(val)
    return p if p.is_dir() else None


def get_test_plan_dir(config: dict) -> Path | None:
    """Return test plan directory path, or None if not configured."""
    val = config.get("paths", {}).get("test_plan_dir")
    if not val:
        return None
    p = Path(val)
    return p if p.is_dir() else None


def get_sagas_dir(config: dict) -> Path | None:
    """Return sagas directory path, or None if not configured."""
    val = config.get("paths", {}).get("sagas_dir")
    if not val:
        return None
    p = Path(val)
    return p if p.is_dir() else None


def get_epics_dir(config: dict) -> Path | None:
    """Return epics directory path, or None if not configured."""
    val = config.get("paths", {}).get("epics_dir")
    if not val:
        return None
    p = Path(val)
    return p if p.is_dir() else None


def get_story_map(config: dict) -> Path | None:
    """Return story map index file path, or None if not configured."""
    val = config.get("paths", {}).get("story_map")
    if not val:
        return None
    p = Path(val)
    return p if p.is_file() else None
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd /Users/jonr/Documents/non-nitro-repos/giles && python -m pytest tests/test_hexwise_setup.py::TestHexwiseSetup::test_optional_paths_absent -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/validate_config.py tests/test_hexwise_setup.py
git commit -m "feat: add optional path helpers for PRDs, test plans, sagas, epics, story map"
```

---

### Task 4: Update sprint_init.py — New Detection Methods

Add detection methods for PRDs, test plans, sagas, epics, story maps, and team topology.

**Files:**
- Modify: `scripts/sprint_init.py:255+` (new detection methods in ProjectScanner), `:560+` (new symlink logic in ConfigGenerator)
- Test: `tests/test_hexwise_setup.py`

- [ ] **Step 1: Write test for new detection**

Add to `tests/test_hexwise_setup.py`. This test will pass once Hexwise has the new docs AND sprint_init detects them — but write it now as the target:

```python
def test_scanner_deep_docs_absent(self):
    """Scanner returns None for deep docs when not present."""
    scanner = ProjectScanner(self.project_dir)
    # Call each method and verify graceful None return
    assert scanner.detect_prd_dir() is None
    assert scanner.detect_test_plan_dir() is None
    assert scanner.detect_sagas_dir() is None
    assert scanner.detect_epics_dir() is None
    assert scanner.detect_story_map() is None
```

Note: This test verifies the "absent" path. After Task 12 adds Hexwise deep docs, a second test (`test_scanner_detects_hexwise_deep_docs` in Task 17) will verify the "present" path.

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/jonr/Documents/non-nitro-repos/giles && python -m pytest tests/test_hexwise_setup.py::TestHexwiseSetup::test_scanner_detects_deep_docs -v
```

Expected: FAIL — `detect_prd_dir` not found.

- [ ] **Step 3: Add detection methods to ProjectScanner**

Add after `detect_backlog_files()` (around line 279 in sprint_init.py). Each method follows the existing pattern: scan for known directory names or content markers, return a `Detection` with path, evidence, and confidence.

**Important:** Detection values must be relative paths (like existing methods use). Use `str(p.relative_to(self.root))` or store just the candidate `name` string, not `str(p)` which would be absolute. `ConfigGenerator.generate_project_toml()` writes these as TOML values and they must be relative to project root.

```python
def detect_prd_dir(self) -> Detection | None:
    """Detect PRD directory."""
    candidates = ["docs/prd", "prd", "docs/requirements"]
    for name in candidates:
        p = self.root / name
        if p.is_dir() and any(p.iterdir()):
            return Detection(str(p), f"found {name}/", 0.9)
    # Content scan: directories with files containing ## Requirements + ## Design
    for d in self._walk_dirs(max_depth=3):
        md_files = list(d.glob("*.md"))
        if len(md_files) >= 2:
            sample = md_files[0].read_text(errors="replace")[:2000]
            if "## Requirements" in sample and "## Design" in sample:
                return Detection(str(d), f"PRD content in {d.name}/", 0.7)
    return None

def detect_test_plan_dir(self) -> Detection | None:
    """Detect test plan directory."""
    candidates = ["docs/test-plan", "test-plan", "docs/testing"]
    for name in candidates:
        p = self.root / name
        if p.is_dir() and any(p.iterdir()):
            return Detection(str(p), f"found {name}/", 0.9)
    return None

def detect_sagas_dir(self) -> Detection | None:
    """Detect sagas directory."""
    candidates = ["docs/agile/sagas", "backlog/sagas", "docs/sagas"]
    for name in candidates:
        p = self.root / name
        if p.is_dir() and any(p.iterdir()):
            return Detection(str(p), f"found {name}/", 0.9)
    return None

def detect_epics_dir(self) -> Detection | None:
    """Detect epics directory."""
    candidates = ["docs/agile/epics", "backlog/epics", "docs/epics"]
    for name in candidates:
        p = self.root / name
        if p.is_dir() and any(p.iterdir()):
            return Detection(str(p), f"found {name}/", 0.9)
    return None

def detect_story_map(self) -> Detection | None:
    """Detect story map index."""
    candidates = [
        "docs/user-stories/story-map/INDEX.md",
        "docs/agile/story-map/INDEX.md",
        "docs/story-map/INDEX.md",
    ]
    for name in candidates:
        p = self.root / name
        if p.is_file():
            return Detection(str(p), f"found {name}", 0.9)
    return None

def detect_team_topology(self) -> Detection | None:
    """Detect team topology file."""
    candidates = [
        "docs/team/team-topology.md", "docs/dev-team/team-topology.md",
        "docs/dev-team/who-we-are.md",
    ]
    for name in candidates:
        p = self.root / name
        if p.is_file():
            return Detection(str(p), f"found {name}", 0.9)
    return None
```

- [ ] **Step 4: Add fields to ScanResult and wire into scan()**

First, add new optional fields to the `ScanResult` dataclass (around line 65):

```python
prd_dir: Detection | None = None
test_plan_dir: Detection | None = None
sagas_dir: Detection | None = None
epics_dir: Detection | None = None
story_map: Detection | None = None
team_topology: Detection | None = None
```

Then in `ProjectScanner.scan()` (line 354), add calls to the new detection methods after the existing ones:

```python
result.prd_dir = self.detect_prd_dir()
result.test_plan_dir = self.detect_test_plan_dir()
result.sagas_dir = self.detect_sagas_dir()
result.epics_dir = self.detect_epics_dir()
result.story_map = self.detect_story_map()
result.team_topology = self.detect_team_topology()
```

- [ ] **Step 5: Wire detection into ConfigGenerator.generate()**

In `ConfigGenerator.generate()` (line 573) and `generate_project_toml()` (line 429), add optional TOML keys when detection results are present. In `generate_doc_symlinks()` (line 560), add symlink creation for the new directories.

- [ ] **Step 6: Add _walk_dirs helper if not present**

The `detect_prd_dir` method uses `_walk_dirs`. If it doesn't exist, add it:

```python
def _walk_dirs(self, max_depth: int = 3) -> list[Path]:
    """Walk directories up to max_depth, skipping EXCLUDED_DIRS."""
    result = []
    for dirpath, dirnames, _ in os.walk(self.root):
        depth = Path(dirpath).relative_to(self.root).parts
        if len(depth) >= max_depth:
            dirnames.clear()
            continue
        dirnames[:] = [d for d in dirnames if d not in EXCLUDED_DIRS]
        result.append(Path(dirpath))
    return result
```

- [ ] **Step 7: Run tests**

```bash
cd /Users/jonr/Documents/non-nitro-repos/giles && python -m pytest tests/test_hexwise_setup.py -v
```

Expected: All existing tests still pass + new detection test passes.

- [ ] **Step 8: Commit**

```bash
git add scripts/sprint_init.py tests/test_hexwise_setup.py
git commit -m "feat: sprint_init detects PRDs, test plans, sagas, epics, story maps"
```

---

### Task 5: Update populate_issues.py — Detail Block Parser

Teach the story parser to handle the dreamcatcher detail block format.

**Files:**
- Modify: `skills/sprint-setup/scripts/populate_issues.py:84` (parse_milestone_stories), `:151` (enrich_from_epics → rewrite), `:268` (format_issue_body)
- Test: `tests/test_hexwise_setup.py`

- [ ] **Step 1: Write test for detail block parsing**

```python
def test_parse_detail_block_story(self):
    """Parser extracts stories from detail block format in epics."""
    from populate_issues import parse_detail_blocks
    epic_content = '''
### US-0101: Parse hex string

| Field | Value |
|-------|-------|
| Story Points | 3 |
| Priority | P0 |
| Saga | S01 |
| Epic | E-0101 |
| Blocked By | — |
| Blocks | US-0102 |
| Test Cases | TC-PAR-001, GP-001 |

**As a** CLI user, **I want** to pass a hex color code **so that** I can see its RGB breakdown.

**Acceptance Criteria:**
- [ ] `AC-01`: Input `#FF5733` returns `R:255 G:87 B:51`
- [ ] `AC-02`: Handles with/without `#` prefix

**Tasks:**
- [ ] `T-0101-01`: Validate hex input (1 SP)
- [ ] `T-0101-02`: Convert to RGB (2 SP)
'''
    stories = parse_detail_blocks(epic_content, sprint=1, source_file="test.md")
    assert len(stories) == 1
    s = stories[0]
    assert s.story_id == "US-0101"
    assert s.title == "Parse hex string"
    assert s.sp == 3
    assert s.priority == "P0"
    assert s.epic == "E-0101"
    assert s.blocks == "US-0102"
    assert s.test_cases == "TC-PAR-001, GP-001"
    assert "CLI user" in s.user_story
    assert len(s.acceptance_criteria) == 2
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/jonr/Documents/non-nitro-repos/giles && python -m pytest tests/test_hexwise_setup.py::TestHexwiseSetup::test_parse_detail_block_story -v
```

Expected: FAIL — `parse_detail_blocks` not found.

- [ ] **Step 3: Implement parse_detail_blocks()**

Add to `populate_issues.py`. This function parses `### US-XXXX: Title` blocks with metadata tables, user stories, acceptance criteria, and tasks.

```python
_DETAIL_BLOCK_RE = re.compile(r"^###\s+(US-\d{4}):\s+(.+)$", re.MULTILINE)
_META_ROW_RE = re.compile(r"^\|\s*(.+?)\s*\|\s*(.+?)\s*\|$")

def parse_detail_blocks(content: str, sprint: int, source_file: str) -> list[Story]:
    """Parse detail-block-format stories from epic/milestone content."""
    stories = []
    # Split on ### US-XXXX headers
    parts = _DETAIL_BLOCK_RE.split(content)
    # parts: [preamble, id1, title1, body1, id2, title2, body2, ...]
    for i in range(1, len(parts), 3):
        if i + 2 > len(parts):
            break
        story_id, title, body = parts[i], parts[i+1].strip(), parts[i+2]

        # Parse metadata table
        meta = {}
        for m in _META_ROW_RE.finditer(body):
            key, val = m.group(1).strip(), m.group(2).strip()
            if key != "Field":  # skip header row
                meta[key.lower().replace(" ", "_")] = val

        # Parse user story (strip bold markdown to produce clean text)
        user_story = ""
        us_match = re.search(r"\*\*As a\*\*\s+(.+?)(?=\n\n|\n\*\*Acceptance)", body, re.DOTALL)
        if us_match:
            raw = us_match.group(0).strip()
            user_story = raw.replace("**", "")

        # Parse acceptance criteria
        ac = re.findall(r"- \[ \] `AC-\d+`:\s*(.+)", body)

        # Parse tasks (not stored on Story yet, but extracted for issue body)
        sp = int(meta.get("story_points", "0"))
        saga = meta.get("saga", "")
        priority = meta.get("priority", "")

        stories.append(Story(
            story_id=story_id,
            title=title,
            saga=saga,
            sp=sp,
            priority=priority,
            sprint=sprint,
            user_story=user_story,
            acceptance_criteria=ac,
            epic=meta.get("epic", ""),
            blocked_by=meta.get("blocked_by", "").replace("—", "").strip(),
            blocks=meta.get("blocks", "").replace("—", "").strip(),
            test_cases=meta.get("test_cases", "").replace("—", "").strip(),
            source_file=source_file,
        ))
    return stories
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd /Users/jonr/Documents/non-nitro-repos/giles && python -m pytest tests/test_hexwise_setup.py::TestHexwiseSetup::test_parse_detail_block_story -v
```

Expected: PASS

- [ ] **Step 5: Rewrite enrich_from_epics() to use parse_detail_blocks()**

Replace the existing `enrich_from_epics()` (line 151) with:

```python
def enrich_from_epics(stories: list[Story], config: dict) -> list[Story]:
    """Enrich stories with detail blocks from epic files, if available."""
    epics_dir = config.get("paths", {}).get("epics_dir")
    if not epics_dir:
        return stories
    epics_path = Path(epics_dir)
    if not epics_path.is_dir():
        return stories

    # Build lookup of existing stories by ID
    by_id = {s.story_id: s for s in stories}
    new_stories = []

    for epic_file in sorted(epics_path.glob("*.md")):
        content = epic_file.read_text(errors="replace")
        # Infer sprint from stories already parsed from milestones
        sprint = 1  # default
        parsed = parse_detail_blocks(content, sprint=sprint, source_file=str(epic_file))
        for ps in parsed:
            if ps.story_id in by_id:
                # Merge: detail block fields override table-row fields
                existing = by_id[ps.story_id]
                existing.user_story = ps.user_story or existing.user_story
                existing.acceptance_criteria = ps.acceptance_criteria or existing.acceptance_criteria
                existing.epic = ps.epic or existing.epic
                existing.blocked_by = ps.blocked_by or existing.blocked_by
                existing.blocks = ps.blocks or existing.blocks
                existing.test_cases = ps.test_cases or existing.test_cases
            else:
                new_stories.append(ps)

    return stories + new_stories
```

- [ ] **Step 6: Rewrite format_issue_body() for richer output**

Replace the existing `format_issue_body()` (line 268) with:

```python
def format_issue_body(story: Story, config: dict) -> str:
    """Format enriched GitHub issue body from story."""
    lines = []
    # Persona placeholder — updated after kickoff assignment
    lines.append("> **[Unassigned]** · Implementation\n")
    # Story header
    lines.append("## Story")
    lines.append(f"**{story.story_id}** — {story.title} | Sprint {story.sprint} | {story.sp} SP | {story.priority}")
    if story.epic:
        lines.append(f"**Epic:** {story.epic}")
    if story.saga:
        lines.append(f"**Saga:** {story.saga}")
    lines.append("")
    # User story
    if story.user_story:
        lines.append("## User Story")
        lines.append(story.user_story)
        lines.append("")
    # Acceptance criteria
    if story.acceptance_criteria:
        lines.append("## Acceptance Criteria")
        for i, ac in enumerate(story.acceptance_criteria, 1):
            lines.append(f"- [ ] `AC-{i:02d}`: {ac}")
        lines.append("")
    # Dependencies
    if story.blocked_by or story.blocks:
        lines.append("## Dependencies")
        if story.blocked_by:
            lines.append(f"**Blocked by:** {story.blocked_by}")
        if story.blocks:
            lines.append(f"**Blocks:** {story.blocks}")
        lines.append("")
    # Test coverage references (IDs only, not full content)
    if story.test_cases:
        lines.append("## Test Coverage")
        lines.append(f"**Test cases:** {story.test_cases}")
        lines.append("")
    return "\n".join(lines)
```

- [ ] **Step 7: Run all populate_issues tests**

```bash
cd /Users/jonr/Documents/non-nitro-repos/giles && python -m pytest tests/test_hexwise_setup.py tests/test_gh_interactions.py -v
```

Expected: All tests pass.

- [ ] **Step 8: Commit**

```bash
git add skills/sprint-setup/scripts/populate_issues.py tests/test_hexwise_setup.py
git commit -m "feat: populate_issues parses detail blocks, generates richer issue bodies"
```

---

### Task 6: Update bootstrap_github.py — Epic Labels

Add epic label creation when epics are detected.

**Files:**
- Modify: `skills/sprint-setup/scripts/bootstrap_github.py:171+`
- Test: `tests/test_hexwise_setup.py`

- [ ] **Step 1: Write test**

```python
def test_epic_labels_created(self):
    """Epic labels are created when epics_dir is configured."""
    # This test uses the existing fake_github infrastructure
    # Verify that create_epic_labels() parses epic IDs from filenames
    from bootstrap_github import create_epic_labels
    # Should extract E-0101, E-0102, etc. from filenames like E-0101-parsing.md
    assert callable(create_epic_labels)
```

- [ ] **Step 2: Implement create_epic_labels()**

Add to `bootstrap_github.py` after `create_static_labels()`:

```python
def create_epic_labels(config: dict, epics_dir: Path) -> None:
    """Create epic: labels from epic filenames in epics_dir."""
    epic_re = re.compile(r"(E-\d{4})")
    for f in sorted(epics_dir.glob("*.md")):
        m = epic_re.search(f.stem)
        if m:
            epic_id = m.group(1)
            label = f"epic:{epic_id}"
            create_label(label, "0e8a16", f"Epic {epic_id}")
```

Note: `create_label()` (line 55 in bootstrap_github.py) takes `(name, color, description)` — no `repo` parameter. It reads repo from config internally. Match this existing pattern.

- [ ] **Step 3: Wire into main()**

In `main()` (line 242), add a call to `create_epic_labels()` when `epics_dir` is configured:

```python
epics_dir = get_epics_dir(config)
if epics_dir:
    create_epic_labels(config, epics_dir)
```

Import `get_epics_dir` from `validate_config`.

- [ ] **Step 4: Run tests**

```bash
cd /Users/jonr/Documents/non-nitro-repos/giles && python -m pytest tests/test_hexwise_setup.py tests/test_gh_interactions.py -v
```

- [ ] **Step 5: Commit**

```bash
git add skills/sprint-setup/scripts/bootstrap_github.py tests/test_hexwise_setup.py
git commit -m "feat: bootstrap_github creates epic labels from epics directory"
```

---

## Chunk 2: Sprint Process Updates

### Task 7: Update Implementer Agent Template

Add new context sections for PRD, test plan, and saga context.

**Files:**
- Modify: `skills/sprint-run/agents/implementer.md`

- [ ] **Step 1: Add Strategic Context section**

Insert after `### Related Stories` (line 28) and before `## Your Process` (line 31):

```markdown
### Strategic Context
{saga_context — saga goal and where this story fits in the larger initiative. Omitted if sagas not configured.}

### Test Plan Context
{test_plan_context — preconditions and expected results from referenced test cases. Omitted if test plan not configured.}
```

- [ ] **Step 2: Update PR description template**

In the PR body template (line 43-58), add test plan and saga references after `## PRD Context`:

```markdown
## Test References
{test_case_ids — comma-separated list of test case IDs this story should satisfy}

## Strategic Context
{saga_goal — one-line saga objective for orientation}
```

- [ ] **Step 3: Clarify dependency status injection**

The existing `### Related Stories` section already has `{dependencies and related stories}`. Update the comment to make clear that sprint-run should inject the current GitHub state of blocked_by/blocks stories here:

```markdown
### Related Stories
{dependencies — current GitHub state of blocked_by/blocks stories: merged, in review, or in dev. Sprint-run checks `gh issue view` for each dependency and injects status.}
```

- [ ] **Step 4: Update Conventions Checklist**

Add to the checklist (line 128-136):

```markdown
- [ ] Test plan references covered (if test cases specified in story)
- [ ] Implementation satisfies PRD non-functional requirements (if PRD excerpts provided)
```

- [ ] **Step 5: Commit**

```bash
git add skills/sprint-run/agents/implementer.md
git commit -m "feat: implementer agent receives PRD, test plan, and saga context"
```

---

### Task 8: Update Reviewer Agent Template

Add test coverage verification and PRD non-functional requirements to review.

**Files:**
- Modify: `skills/sprint-run/agents/reviewer.md`

- [ ] **Step 1: Add Test Coverage Verification section**

Insert at the end of the `### 2. Read the Diff` section (before `### 3. Post Your Review` at line 63):

```markdown
### 2.5. Verify Test Coverage (if test plan context provided)

{test_coverage_verification — list of test case IDs with preconditions and expected results}

For each referenced test case:
- Confirm the implementation includes a test that covers this scenario
- Verify the test assertions match the expected results from the test plan
- Flag any test cases that are referenced but not covered

If test plan context is not provided, skip this step.
```

- [ ] **Step 2: Add PRD non-functional requirements to review checklist**

Add to the review checklist in the review template (lines 72-79):

```markdown
- [x/✗] Test plan coverage verified (if test cases referenced)
- [x/✗] PRD non-functional requirements met (if provided — check perf thresholds, memory budgets)
```

- [ ] **Step 3: Commit**

```bash
git add skills/sprint-run/agents/reviewer.md
git commit -m "feat: reviewer agent verifies test plan coverage and PRD non-functional reqs"
```

---

### Task 9: Update Ceremony References

Enrich kickoff, demo, and retro with hierarchy awareness.

**Files:**
- Modify: `skills/sprint-run/references/ceremony-kickoff.md`
- Modify: `skills/sprint-run/references/ceremony-demo.md`
- Modify: `skills/sprint-run/references/ceremony-retro.md`

- [ ] **Step 1: Update ceremony-kickoff.md**

Insert new step before `### 2. Story Walk` (line 22), after `### 1. Sprint Goal` content:

```markdown
### 1.5. Saga Context (if sagas configured)

For each saga active in this sprint:
- Read the saga file from `{config [paths] sagas_dir}`
- Present the saga goal and team voices section
- Frame how this sprint's stories advance the saga's strategic objective

If multiple sagas are active, present each briefly. This gives the team
the "why" before diving into the "what."
```

Update `### 2. Story Walk` to include epic and PRD context:

```markdown
- **PM presents:** ID, title, SP, priority, acceptance criteria,
  epic context (where in the epic, what's done/remaining),
  PRD references (requirement IDs if PRD configured),
  test plan references (test case IDs if test plan configured)
```

Update `### 3. Risk Discussion` to include:

```markdown
- **Design risks:** PRD ambiguity, missing acceptance criteria, untested
  assumptions, PRD open questions (read from `## Open Questions` sections
  in `{config [paths] prd_dir}` if configured)
```

- [ ] **Step 2: Update ceremony-demo.md**

Insert new step at the end of `### 3. Acceptance Verification` (before `### 4. Team Q&A` at line 53):

```markdown
### 3.5. Test Plan Verification (if test plan configured)

For each story demonstrated:
- Read the test cases referenced in the story's `Test Cases` field
- Confirm each referenced test case is covered by the implementation
- Record gaps: test cases that were planned but not implemented

This is not about whether tests pass (that's CI's job) — it's about
whether the test COVERAGE matches what the test plan specified.
```

Add to the Output template after `## Stories Demonstrated`:

```markdown
## Traceability
| Story | Epic | Test Cases Covered | Test Cases Gaps |
|-------|------|--------------------|-----------------|
```

- [ ] **Step 3: Update ceremony-retro.md**

Add to `### 2. Propose Doc Changes` (at end of bullet list, before `### 3. Get User Approval` at line 57):

```markdown
- **PRD files?** If the sprint revealed design gaps, ambiguous requirements,
  or missing edge cases, propose changes to PRD `## Open Questions` or
  `## Requirements` sections in `{config [paths] prd_dir}`. Retro findings
  that reveal design gaps get added to Open Questions; resolved questions
  get promoted to Requirements.
```

Add new row type example to `## Examples of Retro-Driven Doc Changes`:

```markdown
- Sprint revealed a PRD requirement was ambiguous — add clarification to
  PRD requirements section and close the open question
- Sprint revealed an untested edge case — add to test plan adversarial
  tests and link to relevant story
```

- [ ] **Step 4: Commit**

```bash
git add skills/sprint-run/references/ceremony-kickoff.md \
      skills/sprint-run/references/ceremony-demo.md \
      skills/sprint-run/references/ceremony-retro.md
git commit -m "feat: ceremonies reference saga context, test plan verification, PRD feedback"
```

---

### Task 10: Update sprint-run SKILL.md — Orchestration Logic

Add context assembly instructions for when deeper docs are available.

**Files:**
- Modify: `skills/sprint-run/SKILL.md`

- [ ] **Step 1: Add context assembly instructions**

Insert new section at the end of Phase 2 (after line 62), before `## Phase 3: Sprint Demo` (line 64):

```markdown
### Context Assembly for Agent Dispatch

When dispatching implementer or reviewer subagents, assemble context from deeper docs if configured. This is the hybrid model: issues have structure, agents get depth.

**Before dispatching implementer:**

1. Read story metadata (epic, saga, test_cases) from the GitHub issue or tracking file
2. If `config [paths] prd_dir` is configured:
   - Resolve PRD path: epic number's first two digits map to PRD directory (E-01xx → prd/01-*/)
   - If the epic's metadata table includes an explicit `PRD:` field, use that instead
   - Read `## Requirements` and `## Design` sections from matching PRD files
   - Inject into `{relevant_prd_excerpts}` placeholder in implementer prompt
3. If `config [paths] test_plan_dir` is configured:
   - Parse `test_cases` field (comma-separated IDs like `TC-PAR-001, GP-001`)
   - Map ID prefix to file: `GP-*` → `01-golden-paths.md`, `TC-*` → `02-functional-tests.md` or `03-adversarial-tests.md`
   - Extract section by heading (`### TC-PAR-001: ...` through next `###`)
   - Inject into `### Test Plan Context` in implementer prompt
4. If `config [paths] sagas_dir` is configured:
   - Read saga file matching story's saga ID (S01 → sagas/S01-*.md)
   - Extract saga goal and team voices
   - Inject into `### Strategic Context` in implementer prompt
5. Check dependency status: for each story in `blocked_by`/`blocks`, run `gh issue view` to get current state (open/closed, kanban label)
   - Inject into `{dependencies}` in implementer prompt with current status

**Before dispatching reviewer:**

1. Same test case extraction as above
2. Inject test cases into `### Test Coverage Verification` in reviewer prompt
3. If PRD has non-functional requirements (REQ-*-NF-*), inject into review checklist

**When paths aren't configured:** Omit the corresponding sections. Prompts work exactly as before.
```

- [ ] **Step 2: Update Quick Reference table**

Add row to the Quick Reference table (line 13):

```markdown
| Context Assembly | This file (see "Context Assembly for Agent Dispatch") |
```

- [ ] **Step 3: Commit**

```bash
git add skills/sprint-run/SKILL.md
git commit -m "feat: sprint-run orchestrates context injection from PRDs, test plans, sagas"
```

---

## Chunk 3: Hexwise Documentation

### Task 11: Hexwise Team — Rich Personas

Rewrite the 3 persona files to dreamcatcher depth (60-80 lines each). Create team topology and update team index.

**Files:**
- Modify: `tests/fixtures/hexwise/docs/team/rusti.md`
- Modify: `tests/fixtures/hexwise/docs/team/palette.md`
- Modify: `tests/fixtures/hexwise/docs/team/checker.md`
- Modify: `tests/fixtures/hexwise/docs/team/INDEX.md`
- Create: `tests/fixtures/hexwise/docs/team/team-topology.md`

- [ ] **Step 1: Rewrite rusti.md**

Follow the persona template structure. 60-80 lines. Use the character sketch from the design spec as the seed:

> Rusti Ferris — Lead/Architect. Former embedded systems engineer who discovered Rust at a conference and never emotionally recovered. Treats zero-cost abstractions as a lifestyle philosophy. Has a mass-produced Ferris plushie she insists is "one of a kind." Privately worried the project is too fun to be taken seriously.

Include: Line Index, Vital Stats, Origin Story, Professional Identity, Personality and Quirks, Relationships (with Palette and Checker), Improvisation Notes. Ensure the `## Role`, `## Voice`, `## Domain`, `## Background`, `## Review Focus` headings still appear (sprint_init.py detects these via `PERSONA_HEADINGS`). Weave them into the richer structure — `## Role` can be part of Professional Identity, `## Voice` part of Improvisation Notes, etc. OR keep all five as separate sections alongside the new ones.

**DEPENDENCY: Task 4 (sprint_init.py) MUST complete before this task.** The rewritten personas use new headings that the scanner won't recognize without Task 4's `PERSONA_HEADINGS` update.

**Required approach:** Task 4 updates `PERSONA_HEADINGS` in `sprint_init.py:32` to accept BOTH old and new heading sets:

```python
PERSONA_HEADINGS = {"## Role", "## Voice", "## Domain", "## Background",
                    "## Review Focus"}
RICH_PERSONA_HEADINGS = {"## Origin Story", "## Professional Identity",
                         "## Personality and Quirks", "## Improvisation Notes"}
```

Then `detect_persona_files()` accepts a file matching EITHER the old set (3+ of 5 headings) OR the rich set (3+ of 4 headings). This lets other projects still use the simple format.

The rewritten personas MUST include all the rich headings. They MAY also include the old headings (for belt-and-suspenders) but it's not required after Task 4.

- [ ] **Step 2: Rewrite palette.md**

Same structure, 60-80 lines. Character seed from design spec:

> Palette Jones — Feature Dev. Art school dropout turned programmer. Knows color theory the way sommeliers know wine. Will mass-rename variables for aesthetic reasons. Genuinely believes `PapayaWhip` is a war crime against the CSS specification. Names test fixtures after Pantone Colors of the Year.

- [ ] **Step 3: Rewrite checker.md**

Same structure, 60-80 lines. Character seed from design spec:

> Checker Macready — QA/Reviewer. Former penetration tester who pivoted to QA because "breaking things on purpose should be someone's whole job." Trusts nothing, verifies everything, delivers verdicts with bone-dry humor. Signs off reviews with "I tried to break it. It held. For now."

- [ ] **Step 4: Update INDEX.md**

Rewrite to include insight mapping and richer columns:

```markdown
# Team

| Name | File | Role | Domain Keywords |
|------|------|------|----------------|
| Rusti Ferris | rusti.md | Lead / Architect | parsing, memory, performance, architecture |
| Palette Jones | palette.md | Feature Dev | color theory, UX, output formatting, CLI |
| Checker Macready | checker.md | QA / Reviewer | testing, edge cases, security, adversarial |

## Special Insight Mapping

| Background | Person | Relevance |
|-----------|--------|-----------|
| Embedded systems / Rust | Rusti Ferris | Zero-cost abstractions, memory layout, no-alloc design |
| Fine art / color theory | Palette Jones | WCAG contrast, color harmony, perceptual uniformity |
| Penetration testing | Checker Macready | Input validation, Unicode edge cases, fuzzing |

See also: `team-topology.md`
```

- [ ] **Step 5: Create team-topology.md**

```markdown
# Team Topology

## Structure

| Function | Members |
|----------|---------|
| Engineering | Rusti Ferris (Lead), Palette Jones (Feature) |
| QA | Checker Macready |

## Personality Map

**Rusti ↔ Palette:** Productive tension. Rusti wants minimal output;
Palette wants beautiful output. They argue about formatting in every
PR and the code is better for it. Rusti secretly admires Palette's
eye for detail; Palette secretly admires Rusti's restraint.

**Rusti ↔ Checker:** Deep mutual respect. Both care about correctness,
from different angles. Checker's adversarial tests have caught real
bugs in Rusti's parser code; Rusti considers this a compliment.

**Palette ↔ Checker:** Checker finds Palette's test fixture naming
("Viva Magenta", "Peach Fuzz") unprofessional. Palette finds Checker's
insistence on `test_input_001` soulless. They compromise on descriptive
names that happen to reference colors.
```

- [ ] **Step 6: Commit**

```bash
git add tests/fixtures/hexwise/docs/team/
git commit -m "feat: hexwise personas rewritten to dreamcatcher depth with team topology"
```

---

### Task 12: Hexwise Agile Docs — Sagas, Epics, Milestones, Story Map

Create the full agile hierarchy. This is the largest task — ~20 stories across 2 sagas, 6 epics, 3 milestones.

**Files:**
- Create: `tests/fixtures/hexwise/docs/agile/README.md`
- Create: `tests/fixtures/hexwise/docs/agile/sagas/S01-core.md`, `S02-toolkit.md`
- Create: `tests/fixtures/hexwise/docs/agile/epics/E-0101-parsing.md`, `E-0102-named-colors.md`, `E-0103-output.md`, `E-0201-contrast.md`, `E-0202-palettes.md`, `E-0203-batch.md`
- Modify: `tests/fixtures/hexwise/docs/backlog/milestones/milestone-1.md`, `milestone-2.md`
- Create: `tests/fixtures/hexwise/docs/backlog/milestones/milestone-3.md`
- Modify: `tests/fixtures/hexwise/docs/backlog/INDEX.md`
- Create: `tests/fixtures/hexwise/docs/user-stories/story-map/INDEX.md`

**Guidance for content creation:**

All stories use the full detail block format. Reference the design spec (Section 5) for the product concept, features, and epic breakdown. Reference `references/dreamcatcher/docs/agile/` for format and depth examples. Keep the tone whimsical — this is a color oracle, not enterprise software.

- [ ] **Step 1: Create agile/README.md**

Backlog summary: 2 sagas, 6 epics, ~20 stories, ~80 SP. Include the numbering scheme (same as dreamcatcher: US-AASS, E-XXYY, T-AASS-NN). Define releases:
- R1: Core (parse, convert, display) — Milestone 1
- R2: Toolkit (contrast, palettes, batch) — Milestones 2-3

- [ ] **Step 2: Create S01-core.md and S02-toolkit.md**

Each saga: 80-120 lines. Include saga summary table, team voices (Rusti, Palette, Checker each comment in character), epic index, sprint allocation, release gate checklist. Reference `references/dreamcatcher/docs/agile/sagas/S01-walking-skeleton.md` for structure.

S01 "Teach the oracle to see": Epics E-0101, E-0102, E-0103
S02 "Give the oracle opinions": Epics E-0201, E-0202, E-0203

- [ ] **Step 3: Create all 6 epic files**

Each epic: 100-150 lines. Full story details in detail block format. Every story needs:
- Metadata table (SP, priority, release, saga, epic, personas, blocked by, blocks, test cases)
- "As a..." narrative
- 2-4 acceptance criteria (specific, measurable — WCAG thresholds for contrast, exact RGB outputs for parsing)
- 2-4 tasks with SP breakdown

**Story allocation per epic:**
- E-0101 (Parsing): ~4 stories — hex parsing, RGB parsing, HSL parsing, format detection
- E-0102 (Named Colors): ~2 stories — CSS color database, name lookup
- E-0103 (Output): ~2 stories — formatted display, color descriptions
- E-0201 (Contrast): ~3 stories — luminance calc, contrast ratio, WCAG verdict
- E-0202 (Palettes): ~3 stories — complementary, analogous/triadic, palette display
- E-0203 (Batch): ~3 stories — stdin reading, batch output, error handling

Ensure cross-references: blocked_by/blocks between stories, test case IDs referencing the test plan using this allocation:
- E-0101 stories → TC-PAR-*, GP-001
- E-0102 stories → TC-NAM-*
- E-0103 stories → TC-OUT-*, GP-001
- E-0201 stories → TC-CON-*, GP-002
- E-0202 stories → TC-PAL-*, GP-003
- E-0203 stories → TC-BAT-*, GP-004

**PRD override fields:** The convention-based PRD mapping (E-01xx → prd/01-*, E-02xx → prd/02-*) breaks for E-0202 and E-0203 because S02 has 3 epics but only 2 map to PRD-02. Add explicit `PRD:` fields in story metadata tables for:
- E-0202 (Palette Generation) stories: `| PRD | PRD-03 |` — overrides convention that would route to prd/02-contrast-access/
- E-0203 (Batch Mode) stories: no PRD field needed (no dedicated PRD; batch mode is a CLI concern, not a domain design doc)

Technical accuracy matters:
- WCAG relative luminance: `L = 0.2126*R + 0.7152*G + 0.0722*B` (after sRGB linearization)
- Contrast ratio: `(L1 + 0.05) / (L2 + 0.05)` where L1 > L2
- HSL conversion: standard formulae (atan2-based hue, saturation from chroma/lightness)
- Complementary = hue + 180°, analogous = hue ± 30°, triadic = hue ± 120°

- [ ] **Step 4: Rewrite milestone files**

Rewrite milestone-1.md and milestone-2.md to the richer format (reference the milestone.md.tmpl from Task 1). Create milestone-3.md.

- Milestone 1 "Core" (Sprints 1-2): Stories from E-0101, E-0102, E-0103
- Milestone 2 "Toolkit" (Sprints 3-4): Stories from E-0201, E-0202
- Milestone 3 "Polish" (Sprint 5): Stories from E-0203

Each milestone: 80-120 lines with sprint breakdown, SP totals, key deliverables, sprint acceptance criteria, risks, cumulative burndown table.

- [ ] **Step 5: Update backlog/INDEX.md**

Update routing table to include sagas and epics:

```markdown
# Backlog

| Artifact | Path |
|----------|------|
| Milestones | `milestones/` |
| Sagas | `../agile/sagas/` |
| Epics | `../agile/epics/` |
| Story Map | `../user-stories/story-map/INDEX.md` |
| Backlog Summary | `../agile/README.md` |
```

- [ ] **Step 6: Create story-map/INDEX.md**

5 activities, release tiers. Reference `references/dreamcatcher/docs/user-stories/story-map/INDEX.md` for format.

Activities:
1. Parse Colors — input handling, format detection
2. Convert & Compute — RGB/HSL conversion, luminance, contrast
3. Name & Describe — CSS names, synesthetic descriptions
4. Generate Palettes — complementary, analogous, triadic
5. Format & Output — display, batch mode, error handling

- [ ] **Step 7: Commit**

```bash
git add tests/fixtures/hexwise/docs/agile/ tests/fixtures/hexwise/docs/backlog/ \
      tests/fixtures/hexwise/docs/user-stories/
git commit -m "feat: hexwise agile docs — 2 sagas, 6 epics, ~20 stories, 3 milestones"
```

---

### Task 13: Hexwise PRDs

Create 3 PRD domains with design docs and reference files.

**Files:**
- Create: `tests/fixtures/hexwise/docs/prd/INDEX.md`
- Create: `tests/fixtures/hexwise/docs/prd/01-color-parsing/formats-design.md`
- Create: `tests/fixtures/hexwise/docs/prd/01-color-parsing/reference.md`
- Create: `tests/fixtures/hexwise/docs/prd/02-contrast-access/wcag-design.md`
- Create: `tests/fixtures/hexwise/docs/prd/02-contrast-access/reference.md`
- Create: `tests/fixtures/hexwise/docs/prd/03-palette-gen/algorithms-design.md`
- Create: `tests/fixtures/hexwise/docs/prd/03-palette-gen/reference.md`

- [ ] **Step 1: Create INDEX.md**

PRD routing table with status, dependencies, blocked-by/blocks:

```markdown
# Product Requirements Documents

| PRD | Domain | Status | Blocked By | Blocks |
|-----|--------|--------|------------|--------|
| PRD-01 | Color Parsing & Conversion | Draft | None | PRD-02, PRD-03 |
| PRD-02 | Contrast & Accessibility | Draft | PRD-01 | None |
| PRD-03 | Palette Generation | Draft | PRD-01 | None |
```

- [ ] **Step 2: Create PRD-01 (Color Parsing)**

`formats-design.md` (60-80 lines): Format support matrix (hex, RGB tuple, HSL, CSS named), `ColorValue` enum/struct design, parsing algorithm, auto-detection logic. Include functional requirements (REQ-PAR-001 through REQ-PAR-006) and non-functional (REQ-PAR-NF-001: parse <1ms per color). Include Palette's design note about HSL being how humans think.

`reference.md` (40-60 lines): Observability (N/A for CLI), acceptance criteria summary, open questions ("Should we support 3-digit hex shorthand `#F53`?"), future work (CMYK, Lab color space).

- [ ] **Step 3: Create PRD-02 (Contrast & Accessibility)**

`wcag-design.md` (60-80 lines): WCAG 2.1 relative luminance formula (with sRGB linearization), contrast ratio formula, AA (4.5:1) and AAA (7:1) thresholds, large text exception (3:1). Include functional requirements (REQ-CON-001 through REQ-CON-004). Include Checker's design note about rounding at exactly 4.5:1.

`reference.md` (40-60 lines): Open questions ("Do we report large-text thresholds separately?"), future work (color blindness simulation).

- [ ] **Step 4: Create PRD-03 (Palette Generation)**

`algorithms-design.md` (60-80 lines): Color wheel math — HSL-based rotation. Complementary (+180°), analogous (±30°), triadic (±120°). Output format options (hex list, named if close match, JSON). Include Palette's design note about triadic palettes being heist crews.

`reference.md` (40-60 lines): Open questions ("Split-complementary as a fourth mode?"), future work (perceptual uniformity via OKLab).

- [ ] **Step 5: Commit**

```bash
git add tests/fixtures/hexwise/docs/prd/
git commit -m "feat: hexwise PRDs — color parsing, contrast, palette generation"
```

---

### Task 14: Hexwise Test Plan

Create comprehensive test plan with golden paths, functional tests, adversarial tests, and traceability.

**Files:**
- Create: `tests/fixtures/hexwise/docs/test-plan/README.md`
- Create: `tests/fixtures/hexwise/docs/test-plan/01-golden-paths.md`
- Create: `tests/fixtures/hexwise/docs/test-plan/02-functional-tests.md`
- Create: `tests/fixtures/hexwise/docs/test-plan/03-adversarial-tests.md`
- Create: `tests/fixtures/hexwise/docs/test-plan/04-traceability.md`

- [ ] **Step 1: Create README.md**

Test plan summary with counts, test pyramid, document map. Include prefix-to-file mapping (critical for sprint-run test case lookup):

```markdown
## Document Map

| Prefix | File | Domain |
|--------|------|--------|
| GP-* | `01-golden-paths.md` | End-to-end scenarios |
| TC-PAR-* | `02-functional-tests.md` | Parsing & conversion |
| TC-NAM-* | `02-functional-tests.md` | Named colors |
| TC-OUT-* | `02-functional-tests.md` | Output & formatting |
| TC-CON-* | `02-functional-tests.md` | Contrast checking |
| TC-PAL-* | `02-functional-tests.md` | Palette generation |
| TC-BAT-* | `02-functional-tests.md` | Batch mode |
| TC-ADV-* | `03-adversarial-tests.md` | Edge cases & adversarial |
```

- [ ] **Step 2: Create 01-golden-paths.md**

4-5 golden path scenarios. Use the Given/When/Then format from `references/dreamcatcher/docs/test-plan/01-golden-path-scenarios.md`. Include boundary tests and error variants.

- GP-001: "First Impression" — `hexwise #FF5733` returns RGB + description
- GP-002: "The Contrast Question" — `hexwise contrast #000000 #FFFFFF` passes AAA
- GP-003: "Palette Party" — `hexwise palette --triadic #3498DB` returns 3 colors
- GP-004: "Batch Judgment" — pipe 10 colors via stdin, get 10 results
- GP-005: "Name That Color" — `hexwise name coral` returns `#FF7F50`

Each golden path: 30-50 lines.

- [ ] **Step 3: Create 02-functional-tests.md**

~30 test cases across domains. Use the TC format from `references/dreamcatcher/docs/test-plan/02-functional-tests-pipeline.md`. Each test case: persona, priority, story reference, preconditions, steps, expected results.

Key test cases:
- TC-PAR-001 through TC-PAR-008: Hex parsing (valid, invalid, case, prefix)
- TC-NAM-001 through TC-NAM-004: Named color lookup (exact, close match, unknown)
- TC-CON-001 through TC-CON-006: Contrast checking (black/white, edge ratios, AA vs AAA)
- TC-PAL-001 through TC-PAL-006: Palette generation (complementary, analogous, triadic)
- TC-OUT-001 through TC-OUT-004: Output formatting (plain, JSON, color descriptions)
- TC-BAT-001 through TC-BAT-004: Batch mode (stdin, mixed valid/invalid, empty)

Each test case: 10-15 lines.

- [ ] **Step 4: Create 03-adversarial-tests.md**

~10 adversarial test cases. Checker's favorites:
- TC-ADV-001: Empty string input
- TC-ADV-002: `#GGGGGG` (invalid hex characters)
- TC-ADV-003: `#FFF` (3-digit shorthand)
- TC-ADV-004: Unicode fullwidth `＃ＦＦ５７３３`
- TC-ADV-005: Contrast of color against itself (exactly 1:1)
- TC-ADV-006: Extremely long input string (1MB of 'F')
- TC-ADV-007: Null bytes in input
- TC-ADV-008: HSL with out-of-range values (hue=400, saturation=200%)
- TC-ADV-009: Named color with mixed case and spaces ("  Coral  ")
- TC-ADV-010: Batch mode with 10,000 lines via stdin

- [ ] **Step 5: Create 04-traceability.md**

Bidirectional mapping: story → test cases, test case → stories. Plus persona coverage matrix.

- [ ] **Step 6: Commit**

```bash
git add tests/fixtures/hexwise/docs/test-plan/
git commit -m "feat: hexwise test plan — golden paths, functional, adversarial, traceability"
```

---

### Task 15: Hexwise Project File Updates

Update RULES.md, DEVELOPMENT.md, and Cargo.toml to reflect the expanded scope.

**Files:**
- Modify: `tests/fixtures/hexwise/RULES.md`
- Modify: `tests/fixtures/hexwise/DEVELOPMENT.md`
- Modify: `tests/fixtures/hexwise/Cargo.toml`

- [ ] **Step 1: Update RULES.md**

Keep the existing rules (no .unwrap in lib, doc comments, clippy, zero deps, test location). Add rules for the new features:
- Color values always stored as sRGB u8 triples internally
- All floating-point comparisons use epsilon (for contrast ratio edge cases)
- Error messages include what was expected and what was received
- CLI exit codes: 0 = success, 1 = invalid input, 2 = system error

- [ ] **Step 2: Update DEVELOPMENT.md**

Add sections for the new feature areas (contrast testing approach, palette verification). Keep the existing build/test/lint/workflow sections.

- [ ] **Step 3: Update Cargo.toml**

Update description to "A color oracle for the terminal." Keep zero dependencies.

- [ ] **Step 4: Commit**

```bash
git add tests/fixtures/hexwise/RULES.md tests/fixtures/hexwise/DEVELOPMENT.md \
      tests/fixtures/hexwise/Cargo.toml
git commit -m "feat: hexwise project files updated for expanded scope"
```

---

## Chunk 4: Integration & Cleanup

### Task 16: Future Work Breadcrumbs

Document the Option C roadmap.

**Files:**
- Create: `docs/superpowers/plans/future-full-pipeline.md`

- [ ] **Step 1: Write the document**

Content directly from the design spec Section 6. Include all 5 items (Saga/Epic Management Scripts, Requirements Traceability, Test Plan Coverage Reporting, Team Voice Extraction, Sprint Analytics) with What/Why/Inputs/Outputs/Dependencies/Scope for each.

- [ ] **Step 2: Commit**

```bash
git add docs/superpowers/plans/future-full-pipeline.md
git commit -m "docs: option C future work roadmap — saga management, traceability, analytics"
```

---

### Task 17: Update Tests

Update `test_hexwise_setup.py` to verify the full pipeline works with the enriched Hexwise docs.

**Files:**
- Modify: `tests/test_hexwise_setup.py`

- [ ] **Step 1: Add test for deep doc detection**

```python
def test_scanner_detects_hexwise_deep_docs(self):
    """Scanner detects PRDs, test plan, sagas, epics in extended Hexwise."""
    scanner = ProjectScanner(self.project_dir)
    result = scanner.scan()
    # ScanResult dataclass fields (added in Task 4)
    assert result.prd_dir is not None
    assert result.test_plan_dir is not None
    assert result.sagas_dir is not None
    assert result.epics_dir is not None
    assert result.story_map is not None
```

- [ ] **Step 2: Add test for enriched config generation**

```python
def test_config_generator_includes_optional_paths(self):
    """Generated project.toml includes optional paths when deep docs detected."""
    scanner = ProjectScanner(self.project_dir)
    scan_result = scanner.scan()
    gen = ConfigGenerator(self.project_dir, scan_result)
    gen.generate()
    config = load_config("sprint-config")  # cwd is project_dir per setUpClass
    assert config["paths"].get("prd_dir") is not None
    assert config["paths"].get("sagas_dir") is not None
    assert config["paths"].get("epics_dir") is not None
```

- [ ] **Step 3: Add test for detail block parsing in pipeline**

```python
def test_populate_issues_parses_epic_stories(self):
    """populate_issues extracts stories from epic detail blocks."""
    # Run the full pipeline and verify stories have epic, test_cases, etc.
    config = load_config("sprint-config")  # cwd is project_dir per setUpClass
    milestones = get_milestones(config)
    stories = parse_milestone_stories(milestones)
    stories = enrich_from_epics(stories, config)
    story = next(s for s in stories if s.story_id == "US-0101")
    assert story.epic == "E-0101"
    assert story.test_cases != ""
    assert len(story.acceptance_criteria) >= 2
```

- [ ] **Step 4: Update existing tests for new fixture state**

Specific assertions that WILL break and need updating:

- `test_full_setup_pipeline` (line ~219): `assertEqual(len(self.fake_gh.milestones), 2, ...)` → change to 3
- `test_full_setup_pipeline` (line ~220): `assertEqual(len(self.fake_gh.issues), 6, ...)` → change to ~20 (match actual story count)
- `test_full_setup_pipeline` (lines ~228-233): hardcoded story ID list `["US-0101", "US-0102", "US-0103", "US-0201", "US-0202", "US-0203"]` → expand to include all new story IDs
- `test_config_has_two_milestones` (line ~132): asserts `>= 2` which still passes with 3 — no change needed
- `test_scanner_finds_personas` (line ~112): may need updating if persona count or detection logic changed

Import `enrich_from_epics`, `parse_milestone_stories` from `populate_issues` in the test that needs them.

- [ ] **Step 5: Run full test suite**

```bash
cd /Users/jonr/Documents/non-nitro-repos/giles && python -m pytest tests/ -v
```

Expected: All tests pass.

- [ ] **Step 6: Commit**

```bash
git add tests/test_hexwise_setup.py
git commit -m "test: update hexwise tests for deep doc detection and enriched parsing"
```

---

### Task 18: Update CLAUDE.md and CHEATSHEET.md

Update meta-documentation with new file references and line numbers.

**Files:**
- Modify: `CLAUDE.md`
- Modify: `CHEATSHEET.md`

- [ ] **Step 1: Update CLAUDE.md**

Add new skeleton templates to the Reference Files table. Update the Configuration System section to mention optional paths. Update the Common Tasks table with new tasks (add PRD, add test plan, etc.). Update line-number references in script tables after code changes.

- [ ] **Step 2: Update CHEATSHEET.md**

Update all line-number indices after code changes to validate_config.py, sprint_init.py, populate_issues.py, bootstrap_github.py. Add entries for new skeleton templates.

- [ ] **Step 3: Verify line numbers are accurate**

Spot-check 5-10 line references against actual file content.

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md CHEATSHEET.md
git commit -m "docs: update CLAUDE.md and CHEATSHEET.md with new files and line refs"
```

---

## Dependency Graph

```
Task 1 (rewrite templates)     ──┐
Task 2 (new templates)         ──┤
                                  ├→ Task 5 (populate_issues) ─→ Task 17 (tests)
Task 3 (validate_config)  ──────┤                                    │
Task 4 (sprint_init)  ──────────┤                                    │
Task 6 (bootstrap_github) ──────┘                                    │
                                  │                                  │
Task 7 (implementer.md)  ──┐     │                                   │
Task 8 (reviewer.md)  ─────┤→ Task 10 (SKILL.md) ───────────────────┤
Task 9 (ceremonies)  ───────┘                                        │
                                  │                                  │
Task 4 (sprint_init) ────────────→ Task 11 (hexwise team) ──┐       │
                                   Task 12 (hexwise agile) ──┤→ T15 ┤
                                   Task 13 (hexwise PRDs)  ──┤      │
                                   Task 14 (hexwise test plan)┘      │
                                                                     │
Task 16 (future work)  ─────────────────────────────────────────────┤
                                                                     │
                                                          Task 18 (CLAUDE.md) — LAST
```

**Parallelizable groups:**
- Group A: Tasks 1, 2, 3, 4, 6 (templates + config — some internal deps)
- Group B: Tasks 7, 8, 9, 10 (sprint process — mostly independent)
- Group C: Tasks 11, 12, 13, 14, 15 (hexwise docs — independent of A and B)
- Group D: Task 16 (future work — fully independent)
- Sequential: Task 5 after Group A, Task 17 after all, Task 18 last
