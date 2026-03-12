# Future Full Pipeline — Option C Roadmap

> This document captures enhancements scoped out of the dreamcatcher alignment
> work (2026-03-11) but documented as breadcrumbs for future implementation.
> Each item includes What, Why, Inputs, Outputs, Dependencies, and Scope.

**Context:** The dreamcatcher alignment (Option B) added config detection,
richer issue bodies, context injection at agent dispatch, ceremony
enhancements, and skeleton templates. Option C takes this further with
scripts that actively manage the document hierarchy.

---

## 1. Saga/Epic Management Scripts

- **What:** `scripts/manage_sagas.py`, `scripts/manage_epics.py` — CRUD operations on sagas/epics, automatic re-numbering
- **Why:** Let Giles manage the hierarchy programmatically instead of relying on hand-edited markdown
- **Inputs:** `sagas_dir`, `epics_dir` from config
- **Outputs:** Updated saga/epic files, re-numbered story references
- **Dependencies:** Config keys and detection (implemented in dreamcatcher alignment)
- **Scope:** Medium — file parsing + rewriting + cross-reference updates

## 2. Requirements Traceability

- **What:** `scripts/traceability.py` — parse stories, PRDs, test cases; build bidirectional map
- **Why:** Flag coverage gaps: stories with no tests, tests with no stories, PRD requirements with no stories
- **Inputs:** `epics_dir`, `prd_dir`, `test_plan_dir`
- **Outputs:** Traceability report (markdown), gap warnings
- **Dependencies:** Story extraction with test_cases, epic, saga fields (implemented in dreamcatcher alignment)
- **Scope:** Medium — parsing + cross-referencing + report generation

## 3. Test Plan Coverage Reporting

- **What:** `scripts/test_coverage.py` — compare planned test cases against actual test files
- **Why:** Know which planned tests are implemented, missing, or exist outside the plan
- **Inputs:** `test_plan_dir`, project test files (detected by language)
- **Outputs:** Coverage report, could integrate with `sprint-monitor`
- **Dependencies:** Test case extraction (implemented in dreamcatcher alignment)
- **Scope:** Medium-Large — needs language-specific test file parsing

## 4. Team Voice Extraction

- **What:** `scripts/team_voices.py` — parse saga/epic files for persona commentary blocks
- **Why:** Surface relevant voices during ceremonies automatically
- **Inputs:** `sagas_dir`, `epics_dir`, persona commentary format (`> **Name:** ...`)
- **Outputs:** Indexed commentary by persona and story/epic
- **Dependencies:** Config keys (implemented), ceremony enhancements (implemented)
- **Scope:** Small — regex extraction + indexing

## 5. Sprint Analytics

- **What:** `scripts/sprint_analytics.py` — velocity trends, SP accuracy, persona workload, epic completion
- **Why:** Data-driven retro observations, calibrate future planning
- **Inputs:** `sprints_dir` (sprint status, kickoff/demo/retro docs), GitHub milestone data
- **Outputs:** Analytics report, trend charts (text-based), retro data injection
- **Dependencies:** Retro enhancements (implemented)
- **Scope:** Medium — data collection + trend analysis

---

## Recommended Implementation Order

1. **Team Voice Extraction** (Small, no new dependencies)
2. **Requirements Traceability** (Medium, builds on existing parsing)
3. **Saga/Epic Management** (Medium, enables 4 and 5)
4. **Test Plan Coverage** (Medium-Large, needs language detection)
5. **Sprint Analytics** (Medium, needs sprint history data)
