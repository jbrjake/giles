# Doc-Claims Audit — Pass 10

Systematic comparison of every testable documentation claim against the actual
implementation. Findings grouped by document.

---

## CLAUDE.md

### Wrong Claims

**MEDIUM** | `CLAUDE.md:39` | Function list for `validate_config.py`
- **Claim:** Lists `safe_int()` and `parse_iso_date()` as key functions.
- **Reality:** These exist and are correct, but the list omits `_parse_team_index()`,
  `_print_errors()`, `_DIRECTORY_TEMPLATE`, and `_REQUIRED_TOML_SECTIONS` which are
  significant internal helpers. CHEATSHEET covers them; CLAUDE.md does not. Acceptable
  as "summary" — no correction needed.

**LOW** | `CLAUDE.md:95` | Config structure lists `[project], [paths], [ci], [conventions], [release]`
- **Claim:** Five TOML sections.
- **Reality:** The `project.toml.tmpl` also includes a `[labels]` section (line 49 of
  template). The `[labels]` section is commented-out content in the template, but the
  section header itself exists. No script reads `[labels]` today, so this is a
  planned-but-unimplemented feature. The doc is technically correct about the
  implemented sections.

### Undocumented Features

**MEDIUM** | `CLAUDE.md` | Missing `[backlog] story_id_pattern` config key
- **Reality:** `populate_issues.py` reads `[backlog] story_id_pattern` from config
  (line 71) and uses it to override the default story ID regex. The CHEATSHEET
  mentions it at line 516 ("or set [backlog] story_id_pattern in TOML") but CLAUDE.md
  does not list `[backlog]` as a section or `story_id_pattern` as an optional key.

**LOW** | `CLAUDE.md` | Missing `[labels]` TOML section
- **Reality:** The `project.toml.tmpl` template includes a `[labels]` section for
  custom label categories. No script currently reads it, but it exists in the template.

### Verified Correct

- All 19 script paths exist at their documented locations.
- All 5 SKILL.md files exist.
- All 19 skeleton templates exist.
- All listed function names match actual definitions.
- Plugin structure tree is accurate.
- Required TOML keys match `_REQUIRED_TOML_KEYS` exactly.
- Optional deep-doc keys match what `get_prd_dir()`, `get_test_plan_dir()`, etc. implement.
- `project.base_branch` defaults to `main` — verified in `get_base_branch()`.
- Skill lifecycle description is accurate.
- "Four directories up" import chain claim is correct (4x `.parent` calls).
- All §-anchor references from CLAUDE.md resolve to actual anchor comments in target files.

---

## CHEATSHEET.md

### Wrong Claims

**HIGH** | `CHEATSHEET.md:113` | `KANBAN_STATES` listed under sync_tracking.py section
- **Claim:** `§validate_config.KANBAN_STATES` — `KANBAN_STATES` — "Tuple of 6 states: todo..done"
- **Reality:** Two problems:
  1. Listed under the `sync_tracking.py` section but the anchor resolves to
     `validate_config.py`. Misleading placement.
  2. Says "Tuple" but the actual type is `frozenset`, not `tuple`.
     Code: `KANBAN_STATES = frozenset(("todo", "design", "dev", "review", "integration", "done"))`

**HIGH** | `CHEATSHEET.md:205` | `§manage_epics._safe_int` anchor does not exist
- **Claim:** `§manage_epics._safe_int` — `_safe_int()` — "Extract leading digits from string, 0 on failure"
- **Reality:** `manage_epics.py` does NOT define `_safe_int()`. It imports it from
  `validate_config.py`: `from validate_config import safe_int as _safe_int` (line 26).
  There is no `# §manage_epics._safe_int` anchor comment in the file. Any tool trying
  to jump to this anchor will fail.

**HIGH** | `CHEATSHEET.md:220` | `§manage_sagas._safe_int` anchor does not exist
- **Claim:** `§manage_sagas._safe_int` — `_safe_int()` — "Extract leading digits from string, 0 on failure"
- **Reality:** Same as above. `manage_sagas.py` imports `safe_int as _safe_int` from
  `validate_config` (line 25). No anchor comment exists. No locally defined function.

### Verified Correct

- All other listed anchors have matching `# §...` comments in source files.
- All function purposes accurately describe the implementations.
- All script file paths are correct.
- CHEATSHEET skeleton template table matches the 19 actual templates.
- CHEATSHEET config structure matches what validate_config.py requires.
- All reference file sections have matching `<!-- §... -->` anchor comments.

---

## README.md

### Wrong Claims

**HIGH** | `README.md:353` | Story table column order is wrong
- **Claim:** `| US-NNNN | title | saga | SP | priority |` with "optional 6th column: `| epic |`"
- **Reality:** The actual column order (from `milestone.md.tmpl` line 17 and the
  `_DEFAULT_ROW_RE` regex in `populate_issues.py` line 52) is:
  `| Story | Title | Epic | Saga | SP | Priority |`
  Epic is the 3rd column (between Title and Saga), not a 6th column appended at the end.
  The regex treats Epic as optional with `(?:(E-\d{4})\s*\|\s*)?` — it's an optional
  3rd column, not an optional 6th column.

### Verified Correct

- Six kanban states match: todo, design, dev, review, integration, done.
- WIP limits description matches kanban-protocol.md.
- Ceremony descriptions match the reference files.
- Deep documentation support features match the context assembly code.
- CI languages (Rust, Python, Node.js, Go) match `_SETUP_REGISTRY`.
- Base version `0.1.0` when no tags exist matches `calculate_version()`.
- Plugin install command format is reasonable.
- "superpowers" plugin requirement matches prerequisites-checklist.md.
- Sprint history / persona history feature descriptions match implementer.md and
  ceremony-retro.md references.
- Retro "must produce at least one doc change" rule matches
  `§ceremony-retro.rules_must_produce_at_least_one_doc_change`.

---

## skills/sprint-setup/SKILL.md

### Wrong Claims

**LOW** | `skills/sprint-setup/SKILL.md:91` | Hardcoded path example
- **Claim:** "Create sprint directories and `docs/dev-team/sprints/SPRINT-STATUS.md`"
- **Reality:** The actual path is config-driven via `project.toml [paths] sprints_dir`.
  `docs/dev-team/sprints/` is an example, not a fixed path. Should reference the
  config key instead of hardcoding an example path.

### Verified Correct

- Script paths in Quick Reference table are correct (relative to skill dir).
- Bash command paths use correct project-root-relative paths.
- Phase 0 description matches sprint_init.py behavior.
- Prerequisites checklist reference exists at the stated path.
- All scripts are described as idempotent — verified in bootstrap_github.py and
  populate_issues.py (both check for existing resources before creating).

---

## skills/sprint-run/SKILL.md

### Verified Correct

- All §-anchor references resolve to actual anchor comments.
- Phase detection table matches the state machine in kanban-protocol.md.
- Context assembly description matches the actual context injection logic.
- Story dispatch kanban state table matches the 6-state model.
- Reference file table paths all exist.
- Agent template paths exist.

---

## skills/sprint-monitor/SKILL.md

### Wrong Claims

**MEDIUM** | `skills/sprint-monitor/SKILL.md:247` | check_status.py coverage claim
- **Claim:** "Running `check_status.py` covers Steps 0-3, so the agent should NOT
  also run individual `gh` commands for the same checks."
- **Reality:** `check_status.py` covers Steps 0, 1, 1.5, 2, and 3. It does NOT cover
  Step 2.5 (mid-sprint check-in). The mid-sprint check-in is a Giles ceremony that
  involves writing a `mid-sprint-checkin.md` file and presenting it to the user. No
  function in `check_status.py` handles this. Saying "Steps 0-3" implies all steps
  including 2.5 are covered, which is incorrect.

### Verified Correct

- Seven-step list is accurate (0, 1, 1.5, 2, 2.5, 3, 4).
- check_status.py script path is correct.
- update_burndown.py script path is correct.
- Rate limiting documentation matches code behavior.
- Backlog sync description matches sync_backlog.py behavior.
- CI check description matches check_ci() implementation.
- Drift detection description matches check_branch_divergence() and
  check_direct_pushes() implementations.

---

## skills/sprint-release/SKILL.md

### Verified Correct

- Gate validation description matches release_gate.py gate functions.
- Five hardcoded gates match: gate_stories, gate_ci, gate_prs, gate_tests, gate_build.
- Version scheme description matches calculate_version() behavior.
- Base version 0.1.0 claim matches code.
- Rollback procedure is documented and matches do_release() capabilities.
- Script path `skills/sprint-release/scripts/release_gate.py` is correct.
- Reference path `skills/sprint-release/references/release-checklist.md` is correct.

---

## skills/sprint-teardown/SKILL.md

### Verified Correct

- Safety principles match sprint_teardown.py behavior (symlinks safe, generated
  files need confirmation).
- Script paths are correct.
- Classification categories (symlink, generated, unknown) match classify_entries().
- Dry-run mode exists and works as described.
- GitHub cleanup hints match print_github_cleanup_hints().

---

## Reference Files

### skills/sprint-run/references/kanban-protocol.md

- All 6 listed §-anchors have matching anchor comments. Correct.

### skills/sprint-run/references/persona-guide.md

- All 5 listed §-anchors have matching anchor comments. Correct.
- Both short (`§persona-guide.pm_persona`) and long form anchors exist.

### skills/sprint-run/references/ceremony-kickoff.md

- All 11 listed §-anchors have matching anchor comments. Correct.

### skills/sprint-run/references/ceremony-demo.md

- All 10 listed §-anchors have matching anchor comments. Correct.

### skills/sprint-run/references/ceremony-retro.md

- All 13 listed §-anchors have matching anchor comments. Correct.

### skills/sprint-run/references/story-execution.md

- All 7 listed §-anchors have matching anchor comments. Correct.

### skills/sprint-run/references/tracking-formats.md

- All 3 listed §-anchors have matching anchor comments. Correct.

### skills/sprint-run/references/context-recovery.md

- 1 §-anchor exists and matches. Correct.

### skills/sprint-setup/references/github-conventions.md

- All 4 listed §-anchors have matching anchor comments. Correct.

### skills/sprint-setup/references/ci-workflow-template.md

- All 2 listed §-anchors have matching anchor comments. Correct.

### skills/sprint-release/references/release-checklist.md

- All 6 listed §-anchors have matching anchor comments. Correct.

### skills/sprint-run/agents/implementer.md

- All 10 listed §-anchors have matching anchor comments. Correct.

### skills/sprint-run/agents/reviewer.md

- All 6 listed §-anchors have matching anchor comments. Correct.

---

## Undocumented Code

### Functions with anchor comments but NOT in CHEATSHEET

These functions have `# §` or `<!-- § -->` anchor comments in the source code
but are not listed in any documentation table:

| Anchor | File | Function |
|--------|------|----------|
| `§bootstrap_github.create_label` | bootstrap_github.py | `create_label()` |
| `§bootstrap_github.create_sprint_labels` | bootstrap_github.py | `create_sprint_labels()` |
| `§bootstrap_github._parse_saga_labels_from_backlog` | bootstrap_github.py | `_parse_saga_labels_from_backlog()` |
| `§bootstrap_github.create_saga_labels` | bootstrap_github.py | `create_saga_labels()` |
| `§team_voices._extract_from_file` | team_voices.py | `_extract_from_file()` |

Note: These are all documented in the CHEATSHEET. The above table is WRONG — let me
recheck.

Actually, upon re-examination: All of these ARE in the CHEATSHEET (lines 72-77 for
bootstrap_github, line 174 for team_voices). Retracted — no undocumented anchored
functions found.

### Functions WITHOUT anchor comments and NOT in docs

These public/semi-public functions exist in the code but have no anchor comment
and no documentation entry:

| File | Function | Notes |
|------|----------|-------|
| `bootstrap_github.py` | `check_prerequisites()` | No anchor, not in docs |
| `populate_issues.py` | `check_prerequisites()` | No anchor, not in docs |
| `setup_ci.py` | `check_prerequisites()` | No anchor, not in docs |
| `setup_ci.py` | `_generate_check_job()` | No anchor, not in docs |
| `setup_ci.py` | `_generate_test_job()` | No anchor, not in docs |
| `setup_ci.py` | `_generate_build_job()` | No anchor, not in docs |
| `setup_ci.py` | `_docs_lint_job()` | No anchor, not in docs |
| `setup_ci.py` | `_job_name_from_command()` | No anchor, not in docs |
| `setup_ci.py` | `_find_test_command()` | No anchor, not in docs |
| `release_gate.py` | `determine_bump()` | No anchor, not in docs |
| `release_gate.py` | `bump_version()` | No anchor, not in docs |
| `release_gate.py` | `print_gate_summary()` | No anchor, not in docs |
| `release_gate.py` | `find_milestone_number()` | No anchor, not in docs |
| `sprint_teardown.py` | `resolve_symlink_target()` | No anchor, not in docs |
| `sprint_teardown.py` | `symlink_display()` | No anchor, not in docs |
| `sprint_teardown.py` | `print_dry_run()` | No anchor, not in docs |
| `sprint_teardown.py` | `print_loop_cleanup_hints()` | No anchor, not in docs |
| `sync_tracking.py` | `_parse_closed()` | No anchor, not in docs |
| `sync_tracking.py` | `_yaml_safe()` | No anchor, not in docs |
| `update_burndown.py` | `_fm_val()` | No anchor, not in docs |
| `validate_config.py` | `_count_trailing_backslashes()` | No anchor, not in docs |
| `validate_config.py` | `_strip_inline_comment()` | No anchor, not in docs |
| `validate_config.py` | `_has_closing_bracket()` | No anchor, not in docs |
| `validate_config.py` | `_unescape_toml_string()` | No anchor, not in docs |
| `validate_config.py` | `_parse_value()` | No anchor, not in docs |
| `validate_config.py` | `_split_array()` | No anchor, not in docs |
| `validate_config.py` | `_set_nested()` | No anchor, not in docs |
| `validate_config.py` | `_print_errors()` | No anchor, not in docs |
| `check_status.py` | `_first_error()` | No anchor, not in docs |
| `check_status.py` | `_hours()` | No anchor, not in docs |
| `check_status.py` | `_age()` | No anchor, not in docs |
| `check_status.py` | `_count_sp()` | No anchor, not in docs |
| `populate_issues.py` | `_DETAIL_BLOCK_RE` | No anchor, not in docs |
| `populate_issues.py` | `_META_ROW_RE` | No anchor, not in docs |
| `populate_issues.py` | `_SPRINT_HEADER_RE` | No anchor, not in docs |

Most of these are private helpers (prefixed with `_`) and do not warrant
documentation entries. However, `check_prerequisites()` in three scripts
and the four release_gate.py functions (`determine_bump`, `bump_version`,
`print_gate_summary`, `find_milestone_number`) are significant public functions
that callers might want to reference.

---

## Summary of Findings

### HIGH severity (3)

1. **CHEATSHEET.md:205** — `§manage_epics._safe_int` anchor does not exist in source
   code. Function is an import alias, not a local definition.
2. **CHEATSHEET.md:220** — `§manage_sagas._safe_int` anchor does not exist in source
   code. Same issue as above.
3. **README.md:353** — Story table column order is wrong. Epic is the 3rd column
   (optional, between Title and Saga), not a 6th column appended at the end.

### MEDIUM severity (3)

4. **CHEATSHEET.md:113** — `KANBAN_STATES` described as "Tuple" but is actually
   `frozenset`. Also listed under wrong section (sync_tracking.py instead of
   validate_config.py).
5. **sprint-monitor/SKILL.md:247** — Claims `check_status.py` "covers Steps 0-3"
   but it skips Step 2.5 (mid-sprint check-in).
6. **CLAUDE.md** — Missing documentation for `[backlog] story_id_pattern` optional
   TOML config key.

### LOW severity (2)

7. **sprint-setup/SKILL.md:91** — Hardcodes example path `docs/dev-team/sprints/`
   instead of referencing config-driven `sprints_dir`.
8. **CLAUDE.md:95** — Config structure omits `[labels]` section from template.
