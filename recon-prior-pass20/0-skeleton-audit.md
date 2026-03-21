# Skeleton Template Audit

Audited: all 19 `.tmpl` files in `references/skeletons/`, cross-referenced
against `scripts/sprint_init.py` (ConfigGenerator), `scripts/validate_config.py`
(_REQUIRED_TOML_KEYS, _REQUIRED_FILES, _parse_team_index), and relevant tests.

---

## Summary

- **19 templates exist**, matching CLAUDE.md's documented count
- **7 templates are used by ConfigGenerator** in sprint_init.py
- **12 templates are unused by code** (reference-only, for manual use)
- **2 missing skeleton names** referenced in code but nonexistent as `.tmpl` files
- **2 templates have severely stale Line Index sections**
- **1 template has column order inconsistent with code-generated output**
- **3 phantom config keys** documented in project.toml.tmpl with no implementation

---

## Per-Template Findings

### 1. project.toml.tmpl

**Used by code:** No -- ConfigGenerator.generate_project_toml() builds TOML
programmatically (line 600-684). The skeleton exists for reference/documentation
only. When sprint_init runs, it generates project.toml from scan results, not
from this template.

**Structural validity:** Valid TOML. Parses correctly through parse_simple_toml().
The multiline `check_commands` array containing only comments parses to `[]`.

**Consistency with _REQUIRED_TOML_KEYS:** All 8 required keys are present:
- `project.name` -- present (as TODO placeholder)
- `project.repo` -- present (as TODO placeholder)
- `project.language` -- present (as TODO placeholder)
- `paths.team_dir` -- present
- `paths.backlog_dir` -- present
- `paths.sprints_dir` -- present
- `ci.check_commands` -- present (empty array after comment stripping)
- `ci.build_command` -- present (as TODO placeholder)

**Placeholder quality:** TODO markers are clear. `TODO-project-name`,
`TODO-owner/repo`, `TODO-language`, `TODO-build-command` all indicate what to
replace.

**Phantom config keys (never consumed by code):**

| Key | Line | Status |
|-----|------|--------|
| `feedback_dir` | 27 | No `get_feedback_dir()` exists. Previously flagged as P4-31. |
| `[labels]` section | 49-55 | No Python code reads `config["labels"]`. |
| `[release].version_scheme` | 58 | No code reads `version_scheme`. |

The `[release]` section itself is used by release_gate.py (for `version` key,
written at release time), but `version_scheme` and `milestones` sub-keys within
it are never read.

**Stale content:** No references to v5 actions or outdated versions. Clean.

---

### 2. team-index.md.tmpl

**Used by code:** Yes -- `_copy_skeleton("team-index.md.tmpl", "team/INDEX.md")`
at sprint_init.py line 717, when no persona files are detected.

**Column order mismatch:** The skeleton has:
```
| Name | File | Role | Domain Keywords |
```
But ConfigGenerator.generate_team() (line 726) produces:
```
| Name | Role | File |
```
And validate_config.py's description (line 408) says "Name, Role, File columns."

**Functional impact:** Low. `_parse_team_index` is header-name-based (line 578:
`headers = [c.lower() for c in cells]`), so column order does not break parsing.
But a user editing the skeleton could be confused by the inconsistency.

**Extra column:** `Domain Keywords` is a 4th column not consumed by any code.
No script reads `row["domain keywords"]`. Not harmful, but it's orphaned metadata.

---

### 3. persona.md.tmpl

**Used by code:** No. ConfigGenerator never copies this template. It exists as a
reference for users creating persona files manually.

**Structural validity:** Valid markdown. Headings properly nested (# -> ##).

**Line Index is severely stale:** Every entry after the first is wrong.

| Index Claim | Actual Lines | Delta |
|------------|-------------|-------|
| Lines 1-6: Index | Lines 1-10 | +4 lines |
| Lines 8-15: Vital stats | Lines 12-16 | Shifted +4 |
| Lines 17-34: Origin story | Lines 18-30 | End shifted -4 |
| Lines 36-51: Professional identity | Lines 32-39 | Shifted -4, end -12 |
| Lines 53-66: Personality and quirks | Lines 41-48 | Shifted -12 |
| Lines 68-78: Relationships | Lines 50-53 | Shifted -18 |
| Lines 80-96: Improvisation notes | Lines 55-67 | File ends at line 75. Claimed end (96) is 21 lines past EOF. |

The Line Index appears to have been written for an earlier, longer version of the
template. The `## Sprint History` section at line 69 is not mentioned in the
Line Index at all.

**Scanner compatibility:** The template has 4 of 4 RICH_PERSONA_HEADINGS
(Origin Story, Professional Identity, Personality and Quirks, Improvisation
Notes). Scanner requires >= 3, so persona files based on this template will be
correctly detected.

---

### 4. giles.md.tmpl

**Used by code:** Yes -- `_copy_skeleton("giles.md.tmpl", "team/giles.md")`
at sprint_init.py line 754.

**Test expectations (test_hexwise_setup.py lines 190-197):** Checks for 7
section headings: Vital Stats, Origin Story, Professional Identity,
Personality and Quirks, Relationships, Improvisation Notes, Facilitation Style.
All 7 are present. Tests pass.

**Line Index is stale after the first entry:**

| Index Claim | Actual Line | Delta |
|------------|------------|-------|
| Vital Stats: 12-16 | 12-16 | Correct |
| Origin Story: 18-28 | 18-26 | End off by 2 (28 is next heading) |
| Professional Identity: 30-38 | 28-34 | Start off by 2, end off by 4 |
| Personality and Quirks: 40-52 | 36-44 | Start off by 4, end off by 8 |
| Relationships: 54-62 | 46-52 | Start off by 8, end off by 10 |
| Improvisation Notes: 64-80 | 54-64 | Start off by 10, end off by 16 |
| Facilitation Style: 82-96 | 66-79 | Start off by 16. File ends at 79, not 96. |

The drift accumulates progressively, suggesting the Line Index was written for
a version with more content per section (possibly with blank lines or extra
paragraphs that were later edited out).

**Content quality:** Excellent. Rich character writing. All test-expected
sections present.

---

### 5. backlog-index.md.tmpl

**Used by code:** Yes -- `_copy_skeleton("backlog-index.md.tmpl",
"backlog/INDEX.md")` at sprint_init.py line 759.

**Structural validity:** Valid markdown table. Simple routing table format.

**No issues found.**

---

### 6. milestone.md.tmpl

**Used by code:** No. ConfigGenerator never copies this template. Milestone
files come from project backlog via symlinks.

**Structural validity:** Valid markdown. Story table has 6 columns matching the
format documented in the codebase: `| Story | Title | Epic | Saga | SP | Priority |`.

**Consistency:** The column order matches `_DEFAULT_ROW_RE` in populate_issues.py.
The `### Sprint N:` heading pattern matches what `detect_backlog_files()` looks
for (`###?\s*Sprint\s+\d+`).

**No issues found.**

---

### 7. rules.md.tmpl

**Used by code:** Yes -- `_copy_skeleton("rules.md.tmpl", dest)` via
generate_doc_symlinks() at sprint_init.py line 775, when no RULES.md is detected.

**Structural validity:** Valid markdown. 5 sections with TODO markers.

**validate_project check:** Line 550-554 checks that rules.md is non-empty.
The skeleton has content, so this passes.

**No issues found.**

---

### 8. development.md.tmpl

**Used by code:** Yes -- `_copy_skeleton("development.md.tmpl", dest)` via
generate_doc_symlinks() at sprint_init.py line 776, when no DEVELOPMENT.md is
detected.

**Structural validity:** Valid markdown. 5 sections with TODO markers.

**validate_project check:** Line 550-554 checks that development.md is non-empty.
The skeleton has content, so this passes.

**No issues found.**

---

### 9. definition-of-done.md.tmpl

**Used by code:** Yes -- `_copy_skeleton("definition-of-done.md.tmpl",
"definition-of-done.md")` at sprint_init.py line 809.

**Test expectations (test_hexwise_setup.py lines 205-213):**
- `assertIn("## Mechanical", text)` -- present at line 6
- `assertIn("## Semantic", text)` -- present at line 15
- `assertIn("CI green", text)` -- present at line 8

All test assertions match the template content.

**No issues found.**

---

### 10. saga.md.tmpl

**Used by code:** No. Reference-only for manual saga creation.

**Structural validity:** Valid markdown. Tables properly formatted. Sections
well-organized with Team Voices, Epic Index, Sprint Allocation, Dependency Graph,
Release Gate Checklist.

**Placeholder quality:** Clear TODO markers with format hints (e.g.,
`S{XX}`, `E-{XXYY}`).

**No issues found.**

---

### 11. epic.md.tmpl

**Used by code:** No. Reference-only for manual epic creation.

**Structural validity:** Valid markdown. Story detail block format matches
what `parse_detail_blocks()` in populate_issues.py expects (### heading,
metadata table, ACs, tasks).

**No issues found.**

---

### 12. story-detail.md.tmpl

**Used by code:** No. Reference-only.

**Structural validity:** Valid markdown. Same story block format as in epic.md.tmpl.

**No issues found.**

---

### 13. prd-index.md.tmpl

**Used by code:** No. Reference-only.

**Structural validity:** Valid markdown tables.

**No issues found.**

---

### 14. prd-section.md.tmpl

**Used by code:** No. Reference-only.

**Structural validity:** Valid markdown. Sections match what the PRD content
scanner looks for (`## Requirements` and `## Design` -- see
ProjectScanner.detect_prd_dir() line 387).

**No issues found.**

---

### 15. test-plan-index.md.tmpl

**Used by code:** No. Reference-only.

**Structural validity:** Valid markdown. ASCII art test pyramid is a nice touch.

**No issues found.**

---

### 16. golden-path.md.tmpl

**Used by code:** No. Reference-only.

**Structural validity:** Valid markdown. Given/When/Then format is standard.

**No issues found.**

---

### 17. test-case.md.tmpl

**Used by code:** No. Reference-only.

**Structural validity:** Valid markdown.

**No issues found.**

---

### 18. story-map-index.md.tmpl

**Used by code:** No. Reference-only.

**Structural validity:** Valid markdown tables.

**No issues found.**

---

### 19. team-topology.md.tmpl

**Used by code:** No. Reference-only.

**Structural validity:** Valid markdown tables.

**No issues found.**

---

## Missing Skeleton Templates

Two skeleton names are referenced in `generate_doc_symlinks()` (line 777-778)
but do NOT exist as `.tmpl` files:

| Referenced Name | Context | What Happens |
|----------------|---------|--------------|
| `architecture.md` | sprint_init.py line 777 | Falls through to `_copy_skeleton` stub path: writes `<!-- TODO: populate architecture.md -->` |
| `cheatsheet.md` | sprint_init.py line 778 | Falls through to `_copy_skeleton` stub path: writes `<!-- TODO: populate cheatsheet.md -->` |

**Note:** These are only copied when no ARCHITECTURE.md or CHEATSHEET.md is
detected in the project. The fallback behavior (stub file) works correctly
thanks to `_copy_skeleton`'s graceful handling (lines 583-586). But unlike the
other doc symlinks (rules, development), these have no real skeleton content.

**Graceful handling confirmed:** `_copy_skeleton` checks `src.exists()` at line
580. When the skeleton file does not exist, it writes a stub with a TODO comment
and logs `"stub  {dest_rel} (no skeleton available)"`. This is correct behavior.

---

## Template Usage Summary

### Used by ConfigGenerator (7):

| Template | Method | Condition |
|----------|--------|-----------|
| `team-index.md.tmpl` | `generate_team()` | No persona files detected |
| `giles.md.tmpl` | `_inject_giles()` | Always (Giles is plugin-owned) |
| `backlog-index.md.tmpl` | `generate_backlog()` | No backlog files detected |
| `rules.md.tmpl` | `generate_doc_symlinks()` | No RULES.md detected |
| `development.md.tmpl` | `generate_doc_symlinks()` | No DEVELOPMENT.md detected |
| `definition-of-done.md.tmpl` | `generate_definition_of_done()` | Always |
| `project.toml.tmpl` | N/A (reference only) | ConfigGenerator builds TOML programmatically |

Note: `project.toml.tmpl` exists but is NOT used by `_copy_skeleton`. The TOML
is generated programmatically by `generate_project_toml()`. The template serves
as documentation of the expected format.

### Reference-only (12, never copied by code):

`persona.md.tmpl`, `milestone.md.tmpl`, `saga.md.tmpl`, `epic.md.tmpl`,
`story-detail.md.tmpl`, `prd-index.md.tmpl`, `prd-section.md.tmpl`,
`test-plan-index.md.tmpl`, `golden-path.md.tmpl`, `test-case.md.tmpl`,
`story-map-index.md.tmpl`, `team-topology.md.tmpl`

These exist for users who want to create deep-doc files manually. They are
referenced in CHEATSHEET.md and design specs but are not wired into
ConfigGenerator.

---

## Findings Requiring Attention

### HIGH: Stale Line Indices (2 files)

**persona.md.tmpl** -- Every Line Index entry after the first is wrong. The index
references lines up to 96 but the file is only 75 lines long. The `## Sprint
History` section (line 69) is not mentioned in the index at all.

**giles.md.tmpl** -- Line Index is correct only for Vital Stats (12-16). All
subsequent entries drift progressively. Claimed "Facilitation Style: 82-96" but
the section starts at line 66 and the file ends at line 79.

### MEDIUM: team-index.md.tmpl column order inconsistency

Template has `| Name | File | Role | Domain Keywords |` (4 columns).
Code generates `| Name | Role | File |` (3 columns).
Documentation says "Name, Role, File columns."

The 4th column (`Domain Keywords`) is never consumed by any code.

### LOW: Phantom config keys in project.toml.tmpl

Three config keys/sections are documented in the template but no Python code
reads them:
- `feedback_dir` (line 27) -- previously flagged as P4-31
- `[labels]` section (lines 49-55) -- no code reads `config["labels"]`
- `[release].version_scheme` (line 58) -- no code reads this value

### LOW: Missing skeleton files for architecture and cheatsheet

`architecture.md` and `cheatsheet.md` are referenced as skeleton names in
`generate_doc_symlinks()` but no corresponding `.tmpl` files exist. The code
handles this gracefully (writes a stub), but users get a bare `<!-- TODO -->`
comment instead of a structured template.

### INFO: project.toml.tmpl is reference-only

Despite being in the skeletons directory, this template is never used by
`_copy_skeleton`. ConfigGenerator builds project.toml programmatically from
scan results. The template exists purely as documentation. This is not a bug
-- it's working as designed -- but could confuse someone reading the code.

---

## No Issues Found

- No stale GitHub Actions version references (no v5/v6 refs in any template)
- No outdated Python versions
- No outdated tool names
- All markdown tables are properly formatted with aligned separators
- All 7 used templates produce content that passes validate_project()
- definition-of-done.md.tmpl matches all test expectations (Mechanical, Semantic, CI green)
- giles.md.tmpl has all 7 sections that test_hexwise_setup checks
- milestone.md.tmpl story table format matches populate_issues.py row regex
- _copy_skeleton handles missing templates gracefully (stub fallback)
