# Doc-to-Implementation Audit (Phase 1)

Date: 2026-03-15

Audited: CLAUDE.md, CHEATSHEET.md, README.md, all SKILL.md files, all
reference files, all Python scripts.

---

## Summary

- **Total discrepancies found:** 19
- **HIGH severity:** 5
- **MEDIUM severity:** 10
- **LOW severity:** 4

---

## Discrepancies

### 1. Missing scripts from CLAUDE.md and CHEATSHEET.md

**Doc:** CLAUDE.md (lines 37-55), CHEATSHEET.md (entire scripts section)
**Code:** `scripts/commit.py`, `scripts/validate_anchors.py`, `skills/sprint-release/scripts/release_gate.py`
**Severity:** HIGH

CLAUDE.md and CHEATSHEET.md list 15 scripts with function indices. Three
scripts that exist in the codebase are completely absent from both docs:

- `scripts/commit.py` -- commit message validation/formatting tool,
  referenced by `release_gate.py` (line 31: `COMMIT_PY = _SCRIPTS_DIR / "commit.py"`)
  and by `skills/sprint-release/SKILL.md` (line 45), and by
  `skills/sprint-run/references/story-execution.md`
- `scripts/validate_anchors.py` -- validates greppable anchors across files
- `skills/sprint-release/scripts/release_gate.py` -- release gate validation
  and automation (referenced by `skills/sprint-release/SKILL.md` line 12 as
  `scripts/release_gate.py --help`)

The `release_gate.py` script is the primary automation script for the
sprint-release skill. Its absence from the docs means an agent reading
CLAUDE.md or CHEATSHEET.md cannot discover it, navigate its functions, or
understand its role.

---

### 2. README.md documents phantom `feedback_dir` config key

**Doc:** README.md line 375
**Code:** No `get_feedback_dir()` function exists, no script reads `feedback_dir`
**Severity:** MEDIUM

README.md lists `feedback_dir` as an optional deep-doc path key:

```
[paths] -- prd_dir, test_plan_dir, sagas_dir, epics_dir, story_map,
  team_topology, feedback_dir
```

No Python script reads this key. No `get_feedback_dir()` function exists in
`validate_config.py`. The `project.toml.tmpl` skeleton has it commented out
(line 27: `# feedback_dir = "sprint-config/team/feedback"`). CLAUDE.md
correctly omits it. This was previously identified as bug P4-31.

---

### 3. CLAUDE.md config structure omits `definition-of-done.md` from `_REQUIRED_FILES`

**Doc:** CLAUDE.md lines 89-102 (config structure diagram)
**Code:** `scripts/validate_config.py` lines 281-292 (`_REQUIRED_FILES`)
**Severity:** LOW

The CLAUDE.md config structure diagram shows `definition-of-done.md` as part
of the expected directory layout, but `_REQUIRED_FILES` does not include it.
Validation will pass without this file present. The diagram correctly
represents what `sprint_init.py` generates, but not what `validate_project()`
requires. This is not a bug -- the DoD file is generated but not validated --
but the diagram could be misleading if read as "required structure."

---

### 4. Import chain claim is imprecise

**Doc:** CLAUDE.md line 122
**Code:** All `sys.path.insert` calls across scripts
**Severity:** MEDIUM

CLAUDE.md states: "All skill scripts do `sys.path.insert(0, ...)` to reach
`scripts/validate_config.py` four directories up."

This is only true for scripts under `skills/*/scripts/*.py` (6 files). Scripts
in the top-level `scripts/` directory use `Path(__file__).resolve().parent`
(same directory) instead. Examples:

- `scripts/sync_backlog.py` line 23: `sys.path.insert(0, str(Path(__file__).resolve().parent))`
- `scripts/sprint_analytics.py` line 19: same pattern
- `scripts/team_voices.py` line 19: `sys.path.insert(0, str(SCRIPTS_DIR))`

Additionally, `scripts/sync_backlog.py` also adds a second path to reach
`skills/sprint-setup/scripts/` (line 24), which is a different pattern entirely.

The `skills/sprint-release/scripts/release_gate.py` uses
`_PLUGIN_ROOT / "scripts"` (line 28-29) rather than `parent.parent.parent.parent`,
though the effect is the same.

---

### 5. KANBAN_STATES type mismatch between CHEATSHEET and code

**Doc:** CHEATSHEET.md line 39: "Tuple of 6 states: todo..done"
**Code:** `scripts/validate_config.py` line 716: `KANBAN_STATES = frozenset(("todo", "design", "dev", "review", "integration", "done"))`
**Severity:** LOW

CHEATSHEET.md describes `KANBAN_STATES` as a "Tuple" but the actual type is
`frozenset`. The distinction matters for code that depends on ordering (frozenset
has no guaranteed order; tuple does). In practice, no code relies on the ordering
of KANBAN_STATES, so the impact is cosmetic. The CLAUDE.md correctly says
"frozenset" at line 716 via the anchor.

---

### 6. Kanban protocol and validate_config.py agree on states

**Doc:** `skills/sprint-run/references/kanban-protocol.md` lines 10-17
**Code:** `scripts/validate_config.py` line 716
**Severity:** N/A (PASS)

Both define exactly 6 states: todo, design, dev, review, integration, done.
No discrepancy.

---

### 7. `_REQUIRED_FILES` matches `validate_project()` checks

**Doc:** CLAUDE.md line 131
**Code:** `scripts/validate_config.py` lines 281-292, 310-417
**Severity:** N/A (PASS)

`_REQUIRED_FILES` lists 5 files. `validate_project()` checks all 5 plus
additional structural validations (team index personas >= 2, milestone files
exist, rules.md/development.md non-empty, TOML sections, TOML keys). Docs
and code agree.

---

### 8. Template count claim is correct

**Doc:** CLAUDE.md line 113: "19 templates"
**Code:** `references/skeletons/*.tmpl` glob
**Severity:** N/A (PASS)

Glob returns exactly 19 .tmpl files. Core (9): project.toml, team-index.md,
persona.md, giles.md, backlog-index.md, milestone.md, rules.md,
development.md, definition-of-done.md. Deep docs (10): saga.md, epic.md,
story-detail.md, prd-index.md, prd-section.md, test-plan-index.md,
golden-path.md, test-case.md, story-map-index.md, team-topology.md. Matches
the doc claim exactly.

---

### 9. Missing `get_team_topology()` function

**Doc:** CLAUDE.md line 107: lists `paths.team_topology` as an optional deep-doc key
**Code:** `scripts/validate_config.py` -- no `get_team_topology()` function exists
**Severity:** MEDIUM

CLAUDE.md documents `paths.team_topology` as a supported optional TOML key.
The `sprint_init.py` ConfigGenerator writes it to project.toml (line 628).
However, `validate_config.py` has no `get_team_topology()` accessor function,
unlike all other deep-doc paths which have dedicated getters (`get_prd_dir()`,
`get_test_plan_dir()`, `get_sagas_dir()`, `get_epics_dir()`, `get_story_map()`).

The key can still be accessed via `config.get("paths", {}).get("team_topology")`,
but the pattern is inconsistent with the other deep-doc paths.

---

### 10. CLAUDE.md Skill Entry Points table uses stale anchor names

**Doc:** CLAUDE.md line 61 (sprint-setup row)
**Code:** `skills/sprint-setup/SKILL.md` line 48-49
**Severity:** MEDIUM

CLAUDE.md references anchor `§sprint-setup.step_2_github_bootstrap` for the
sprint-setup skill. The actual SKILL.md file has both
`§sprint-setup.step_2_github_bootstrap` (line 48) and
`§sprint-setup.step_2_github_bootstrap_labels_milestones_issues_ci` (line 49).
The CLAUDE.md reference works but points to the short alias rather than the
full canonical anchor used in CHEATSHEET.md (line 238).

---

### 11. sprint-release SKILL.md references non-existent `scripts/commit.py --help`

**Doc:** `skills/sprint-release/SKILL.md` line 45
**Code:** `scripts/commit.py` exists but is not documented
**Severity:** MEDIUM

The SKILL.md says: "Run `python {plugin_root}/scripts/commit.py --help` for
format." The script exists but is not documented in CLAUDE.md or CHEATSHEET.md,
meaning an agent cannot learn about its interface from the documentation index.

---

### 12. CLAUDE.md lists `get_ci_commands()` in CHEATSHEET only, not in function table

**Doc:** CLAUDE.md line 39 (validate_config.py function list)
**Code:** `scripts/validate_config.py` line 576 (`get_ci_commands()`)
**Severity:** MEDIUM

CLAUDE.md's script table for `validate_config.py` lists 21 functions but omits
`get_ci_commands()`. CHEATSHEET.md line 28 correctly includes it. The function
exists and is called by `setup_ci.py` (line 214 via the import at line 16).

---

### 13. sprint-monitor SKILL.md anchor mismatch in CLAUDE.md

**Doc:** CLAUDE.md line 63
**Code:** `skills/sprint-monitor/SKILL.md` line 30
**Severity:** LOW

CLAUDE.md references `§sprint-monitor.prerequisites` which exists. However,
the CHEATSHEET.md does not include this section in its sprint-monitor table
(CHEATSHEET starts at line 258 with `step_0_sync_backlog`). The CHEATSHEET
omits the prerequisites section from its index.

---

### 14. CLAUDE.md config structure shows `[release]` section but it is not required

**Doc:** CLAUDE.md line 91: `sprint-config/project.toml -- [project], [paths], [ci], [conventions], [release]`
**Code:** `scripts/validate_config.py` line 307: `_REQUIRED_TOML_SECTIONS = ["project", "paths", "ci"]`
**Severity:** MEDIUM

The config structure diagram implies 5 TOML sections: project, paths, ci,
conventions, release. Only 3 are actually required by validation. The
`[conventions]` section is documented as optional on CLAUDE.md line 106.
The `[release]` section is only created by `release_gate.py` during a release.
But the diagram presents all 5 as if they are standard parts of the config.

---

### 15. `sync_backlog.py` import chain is different from documented pattern

**Doc:** CLAUDE.md line 122: "All skill scripts do sys.path.insert(0, ...) four directories up"
**Code:** `scripts/sync_backlog.py` lines 23-24
**Severity:** LOW (already covered by #4, this is a specific case)

`sync_backlog.py` uses two `sys.path.insert` calls: one for `scripts/` (same
dir) and one specifically for `skills/sprint-setup/scripts/` to import
`bootstrap_github` and `populate_issues`. This is a unique cross-skill import
pattern not documented anywhere.

---

### 16. CHEATSHEET.md lists `sync_tracking.py` anchor `§validate_config.KANBAN_STATES` under sync_tracking heading

**Doc:** CHEATSHEET.md line 113
**Code:** `scripts/validate_config.py` line 716
**Severity:** LOW

CHEATSHEET.md's sync_tracking section (line 113) lists
`§validate_config.KANBAN_STATES` as a "Tuple of 6 states: todo..done" under
the sync_tracking heading. While the anchor does reference
validate_config.py (which is correct), listing it under sync_tracking's
section implies it is defined in sync_tracking.py, which it is not.

---

### 17. sprint-release SKILL.md references `[release] milestones` and `[release] gate_file` TOML keys

**Doc:** `skills/sprint-release/SKILL.md` lines 59-60
**Code:** `skills/sprint-release/scripts/release_gate.py` -- does not read these keys
**Severity:** HIGH

The SKILL.md says: "Read gate criteria from `project.toml [release] milestones`
and the gate file specified by `project.toml [release] gate_file`." However,
`release_gate.py` does not read `[release].milestones` or `[release].gate_file`
from the TOML config. The gates are hardcoded as five functions
(`gate_stories`, `gate_ci`, `gate_prs`, `gate_tests`, `gate_build`) in the
script itself. The milestone title is passed as a CLI argument, not read from
config.

---

### 18. sprint-release SKILL.md references `[release]` version scheme from config

**Doc:** `skills/sprint-release/SKILL.md` lines 90-91
**Code:** `skills/sprint-release/scripts/release_gate.py` lines 116-129
**Severity:** HIGH

The SKILL.md says: "Read the version scheme and milestone versions from
`project.toml [release]`. Each milestone maps to a version and name defined
in config." In reality, `release_gate.py` calculates the version automatically
from conventional commits using `calculate_version()`. It does not read version
mappings from the TOML config. The `[release]` section is *written to* by the
script (via `write_version_to_toml()`) but not read from for version calculation.

---

### 19. sprint-release SKILL.md references `sbom_command` and per-platform builds

**Doc:** `skills/sprint-release/SKILL.md` lines 122-125
**Code:** `skills/sprint-release/scripts/release_gate.py`
**Severity:** HIGH

The SKILL.md describes reading `sbom_command` from `project.toml [ci]` and
running builds for "each target platform defined in config." However:

- `release_gate.py` does not read or use `sbom_command` from the config.
  SBOM generation is not implemented.
- There is no multi-platform build support. The script runs `build_command`
  once and checks for a single `binary_path`.
- The SKILL.md's bash examples reference `${sbom_command}` and `${binary_path}`
  as shell variables, but these are conceptual -- the actual script handles
  this differently via Python's `subprocess.run()`.

The SKILL.md describes a more ambitious release pipeline than what
`release_gate.py` currently implements.

---

## Verified Claims (No Discrepancy)

The following claims were checked and found correct:

1. **Plugin structure** (CLAUDE.md lines 11-22): All directories and files exist as described.
2. **5 skills** with SKILL.md entry points: All 5 exist with correct YAML frontmatter.
3. **KANBAN_STATES values**: kanban-protocol.md and validate_config.py agree on 6 states.
4. **19 skeleton templates**: Exact count matches.
5. **Required TOML keys** (CLAUDE.md line 104): Match `_REQUIRED_TOML_KEYS` exactly.
6. **Optional deep-doc paths** (CLAUDE.md line 107): `get_prd_dir()`, `get_test_plan_dir()`, `get_sagas_dir()`, `get_epics_dir()`, `get_story_map()` all exist and work as documented.
7. **Symlink-based config**: `sprint_init.py` uses `_symlink()` for project files and `_copy_skeleton()` for Giles. Teardown removes symlinks without touching targets.
8. **Custom TOML parser**: `parse_simple_toml()` supports strings, ints, bools, arrays, sections as documented.
9. **GitHub as source of truth**: `sync_tracking.py` treats GitHub state as authoritative.
10. **Idempotent scripts**: `bootstrap_github.py` uses `--force` on label creation; `populate_issues.py` checks existing issues before creating.
11. **Script docstrings**: All scripts have accurate module-level docstrings matching their actual behavior.
12. **Function signatures**: All functions listed in CLAUDE.md exist with matching names and purposes (except the omissions noted above).
13. **Reference files**: All 12 reference files listed in CLAUDE.md exist at the specified paths.
14. **Agent templates**: `implementer.md` and `reviewer.md` exist with the documented section anchors.
15. **evals.json**: Exists with 6 evaluation scenarios.
16. **base_branch default**: `get_base_branch()` correctly defaults to "main" as documented.
17. **`_SETUP_REGISTRY` languages**: Supports Rust, Python, Node/Node.js/JavaScript/TypeScript, Go/Golang as documented.

---

## Recommendations

### Priority 1 (HIGH -- misleading docs)

1. **Add `release_gate.py` to CLAUDE.md and CHEATSHEET.md.** This is the
   primary script for the sprint-release skill and is completely undocumented
   in the index files.

2. **Update sprint-release SKILL.md to match `release_gate.py` reality.**
   The SKILL.md describes features that don't exist (config-driven gates,
   config-driven versions, SBOM, multi-platform builds). Either implement
   those features or rewrite the SKILL.md to match current capabilities.

### Priority 2 (MEDIUM -- stale docs)

3. **Add `commit.py` and `validate_anchors.py` to CLAUDE.md/CHEATSHEET.md.**
4. **Remove `feedback_dir` from README.md** or implement it.
5. **Add `get_ci_commands()` to CLAUDE.md function table.**
6. **Add `get_team_topology()` to `validate_config.py`** for consistency.
7. **Clarify import chain description** to distinguish skill scripts (4 dirs up)
   from shared scripts (same directory).
8. **Clarify config structure diagram** to indicate which TOML sections are
   required vs optional.

### Priority 3 (LOW -- cosmetic)

9. **Fix CHEATSHEET.md KANBAN_STATES type**: "frozenset" not "Tuple".
10. **Move `§validate_config.KANBAN_STATES` out of sync_tracking section** in CHEATSHEET.md.
