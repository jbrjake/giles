# Doc-to-Implementation Audit — Fresh Pass (2026-03-15)

Audited: all doc sources (CLAUDE.md, CHEATSHEET.md, README.md, 5 SKILL.md files,
15 reference/agent files, plugin.json) vs actual Python scripts, § anchor
definitions, config keys, kanban states, release gates, and file paths.

Previous audit (pass 8) had 11 findings. All 11 have been resolved. This is a
clean-slate re-audit.

---

## Verified (no discrepancies)

These categories were checked exhaustively and are consistent:

- **All 60+ functions** listed in CLAUDE.md script tables exist in their stated files
  with matching § anchor definitions.
- **All § anchors referenced in CLAUDE.md** resolve to actual `<!-- § -->` or `# §`
  definitions in target files. Every anchor in the Skill Entry Points table, Reference
  Files table, and inline references was verified.
- **All § anchors referenced in CHEATSHEET.md** resolve. Every anchor in the 18 script
  tables, 7 skill entry point tables, 8 reference file tables, and 2 subagent
  descriptions was verified against target files.
- **Kanban states** are consistent across all sources: `todo`, `design`, `dev`,
  `review`, `integration`, `done` in validate_config.py KANBAN_STATES frozenset,
  kanban-protocol.md, github-conventions.md, bootstrap_github.py kanban labels,
  README.md kanban table, tracking-formats.md status field.
- **Required TOML keys** in CLAUDE.md (line 108) match `_REQUIRED_TOML_KEYS` in
  validate_config.py exactly: project.name, project.repo, project.language,
  paths.team_dir, paths.backlog_dir, paths.sprints_dir, ci.check_commands,
  ci.build_command.
- **Plugin.json** lists all 5 skills with correct paths. All paths exist on disk.
- **19 skeleton templates** exist in `references/skeletons/`, matching CLAUDE.md and
  CHEATSHEET.md claims (9 core + 10 deep-doc).
- **Release gate names** in release-checklist.md (Stories, CI, PRs, Tests, Build) match
  `release_gate.py` function names (gate_stories, gate_ci, gate_prs, gate_tests,
  gate_build) and match sprint-release SKILL.md gate descriptions.
- **Priority labels (3)**, **type labels (4)**, and **kanban labels (6)** in
  bootstrap_github.py match github-conventions.md exactly.
- **Import chain**: All skill scripts under `skills/*/scripts/` use 4 `.parent` calls
  to reach repo root, then append `/scripts`. CLAUDE.md's "four directories up" is
  accurate.
- **Config structure** in CLAUDE.md matches validate_config.py's `_REQUIRED_FILES` and
  `_REQUIRED_TOML_KEYS`.
- **Sprint ceremony anchors** all resolve: kickoff (12 anchors), demo (10 anchors),
  retro (14 anchors), story-execution (7 anchors), context-recovery (1 anchor),
  tracking-formats (4 anchors).
- **Subagent template anchors** all resolve: implementer.md (10 anchors), reviewer.md
  (6 anchors).
- **evals/evals.json** exists as claimed in CLAUDE.md plugin structure.

---

## Findings

### F01: CHEATSHEET.md + CLAUDE.md — "line numbers" claim vs actual content

**Files:**
- `CHEATSHEET.md` line 3: "Quick-reference index with line numbers."
- `CLAUDE.md` lines 32-33: "For detailed line-number indices of all functions,
  sections, and reference files, see `CHEATSHEET.md`."

**Claim:** CHEATSHEET.md contains line-number indices.

**Reality:** CHEATSHEET.md contains § anchor references, not line numbers. Every
table uses `| Anchor | Function | Purpose |` columns with entries like
`§validate_config.gh`. There are zero line numbers in the file.

**Which is wrong:** Both docs (CLAUDE.md and CHEATSHEET.md) use outdated
descriptions. The content is correct and useful; the meta-description is stale.

**Severity:** Medium. No agent will be misled by the content itself, but the
framing is inaccurate and could confuse someone trying to understand the indexing
scheme.

---

### F02: sprint-monitor SKILL.md — Quick Reference table has wrong script path

**File:** `skills/sprint-monitor/SKILL.md` line 10

**Claim:** Quick Reference table says `scripts/check_status.py [sprint-number]`

**Reality:** The actual file path is `skills/sprint-monitor/scripts/check_status.py`.
There is no `scripts/check_status.py` at the repo root. The body text at line 237
correctly uses `python3 skills/sprint-monitor/scripts/check_status.py`.

**Which is wrong:** The Quick Reference table path is wrong.

**Severity:** High. An agent following the Quick Reference will get a "file not
found" error. The correct path is only 200+ lines further down.

---

### F03: README.md — story table format omits optional epic column

**File:** `README.md` line 353

**Claim:** "`| US-NNNN | title | saga | SP | priority |`" (5 columns)

**Reality:** `populate_issues.py` line 49-52 shows the default regex supports 6
columns: `| US-XXXX | title | [epic] | saga | sp | priority |` where the epic
column (E-XXXX) is optional for backward compatibility. The comment on line 49
explicitly says "Epic column is optional for backward compat with 5-column format."

**Which is wrong:** README is incomplete. The 5-column format works, but the README
should mention the optional epic column for users who want epic-level tracking.

**Severity:** Medium. Users won't be blocked (5-column format works), but they
won't discover epic column support from the README alone.

---

### F04: CLAUDE.md — tracking-formats.md described as containing "burndown format"

**File:** `CLAUDE.md` line 81

**Claim:** Reference Files table says tracking-formats.md contains "SPRINT-STATUS.md
format, story tracking file YAML frontmatter, burndown format"

**Reality:** `tracking-formats.md` has three sections:
1. `SPRINT-STATUS.md` format (§tracking-formats.sprint_status_md_format)
2. Story File YAML frontmatter (§tracking-formats.story_file_yaml_frontmatter)
3. File Map (§tracking-formats.file_map_where_each_tracking_file_lives)

The File Map mentions `burndown.md` as a file that exists, but the actual burndown
file format is NOT defined in this document. The burndown format is defined only
implicitly by `update_burndown.py`'s `write_burndown()` function.

**Which is wrong:** CLAUDE.md overstates the file's scope. The "burndown format"
is not documented anywhere in the reference files.

**Severity:** Medium. An agent looking for the burndown format specification will
read tracking-formats.md, find no format definition, and have to reverse-engineer
it from the Python code.

---

### F05: CHEATSHEET.md — config structure missing `team/insights.md`

**File:** `CHEATSHEET.md` lines 481-493 (config structure block)

**Claim:** Config structure lists: project.toml, definition-of-done.md, team/INDEX.md,
team/{name}.md, team/giles.md, team/history/, backlog/INDEX.md, backlog/milestones/,
rules.md, development.md.

**Reality:** CLAUDE.md line 101 correctly includes `team/insights.md` in the same
structure block. CHEATSHEET.md omits it. The `insights.md` file is a runtime artifact
created during kickoff (§ceremony-kickoff.1_5_team_read_write_insights) and
referenced by both implementer.md and reviewer.md agent templates.

**Which is wrong:** CHEATSHEET.md is incomplete.

**Severity:** Medium. An agent reading CHEATSHEET.md's config structure won't know
about insights.md. CLAUDE.md has the correct listing.

---

### F06: README.md — sprint-monitor skill description omits two features

**File:** `README.md` line 342 and lines 265-280

**Claim:** Skills table says sprint-monitor "Checks CI status, open PRs, and burndown
(designed for `/loop`)". The Continuous Monitoring section describes: backlog sync,
CI status, PR babysitting, burndown.

**Reality:** sprint-monitor SKILL.md also defines:
- Step 1.5: Drift Detection (branch divergence + direct pushes to base branch)
- Step 2.5: Mid-Sprint Check-In (threshold-triggered Giles ceremony)

Both are implemented in check_status.py (check_branch_divergence,
check_direct_pushes) and described in the SKILL.md with their own § anchors.

**Which is wrong:** README is incomplete. Two monitoring features are undocumented
in the user-facing README.

**Severity:** Medium. Users won't know these features exist from the README. They
are only visible in the SKILL.md.

---

### F07: CLAUDE.md — check_status.py function list incomplete

**File:** `CLAUDE.md` line 50 (check_status.py row in Scripts table)

**Claim:** Lists 5 functions: `check_ci()`, `check_prs()`, `check_milestone()`,
`check_branch_divergence()`, `check_direct_pushes()`.

**Reality:** check_status.py also has `write_log()` (line 309, with anchor
§check_status.write_log) and `main()` (line 325, with anchor §check_status.main).
CHEATSHEET.md correctly lists all 7 functions.

**Which is wrong:** CLAUDE.md table is intentionally a summary ("The tables below
are a summary") so this is borderline. However, `write_log()` and `main()` are listed
in CHEATSHEET.md and have § anchors, making the omission inconsistent with how
other scripts are documented in CLAUDE.md (most include `main()`).

**Severity:** Low. The omission follows the "summary" framing, but the inconsistency
(some scripts list `main()`, this one doesn't) could confuse agents.

---

## Summary

| # | Source | Type | Severity | What's wrong |
|---|--------|------|----------|--------------|
| F01 | CHEATSHEET.md:3, CLAUDE.md:32 | Stale description | Medium | Says "line numbers" but content uses § anchors |
| F02 | sprint-monitor SKILL.md:10 | Wrong path | High | Quick Reference says `scripts/check_status.py`, actual is `skills/sprint-monitor/scripts/check_status.py` |
| F03 | README.md:353 | Incomplete | Medium | Story table format omits optional epic column |
| F04 | CLAUDE.md:81 | Overstated scope | Medium | Claims tracking-formats.md has "burndown format" -- it doesn't |
| F05 | CHEATSHEET.md:481-493 | Missing entry | Medium | Config structure omits `team/insights.md` |
| F06 | README.md:342,265-280 | Incomplete | Medium | Monitor description omits drift detection and mid-sprint check-in |
| F07 | CLAUDE.md:50 | Incomplete | Low | check_status.py row missing write_log() and main() |

**Prior audit findings (pass 8):** All 11 findings have been resolved.

**Overall assessment:** The documentation is in very good shape. All § anchor
references resolve. All function claims are accurate. The remaining issues are
completeness gaps (features exist but aren't mentioned in user-facing docs) and
two stale descriptions. The one high-severity item is the wrong script path in the
sprint-monitor Quick Reference table.
