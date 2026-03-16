# Documentation vs Implementation Consistency Audit

Audited: 2026-03-16

## 1. CLAUDE.md Claims vs Reality

### 1.1 Function Existence

**All functions listed in CLAUDE.md's Scripts table verified to exist.** Every function
name in every script row resolves to an actual `def` or constant in the corresponding
Python file. No phantom functions found.

Scripts verified:
- `validate_config.py` -- all 23 listed functions/constants confirmed (gh, gh_json,
  parse_simple_toml, validate_project, load_config, safe_int, parse_iso_date, extract_sp,
  get_team_personas, get_milestones, get_base_branch, get_sprints_dir, get_prd_dir,
  get_test_plan_dir, get_sagas_dir, get_epics_dir, get_story_map, extract_story_id,
  kanban_from_labels, find_milestone, warn_if_at_limit, list_milestone_issues,
  detect_sprint, get_ci_commands)
- `sprint_init.py` -- ProjectScanner, ConfigGenerator, main() confirmed
- `sprint_teardown.py` -- classify_entries, main() confirmed (CLAUDE.md only lists key
  functions; CHEATSHEET.md has the full list)
- `bootstrap_github.py` -- all 6 listed confirmed
- `populate_issues.py` -- all 7 listed confirmed
- `setup_ci.py` -- generate_ci_yaml, _SETUP_REGISTRY confirmed
- `sync_tracking.py` -- sync_one, create_from_issue confirmed
- `update_burndown.py` -- write_burndown, update_sprint_status, build_rows confirmed
- `sync_backlog.py` -- all 4 listed confirmed
- `sprint_analytics.py` -- all 5 listed confirmed
- `check_status.py` -- all 7 listed confirmed
- `team_voices.py` -- extract_voices, VOICE_PATTERN, main confirmed
- `traceability.py` -- all 5 listed confirmed
- `test_coverage.py` -- all 5 listed confirmed
- `manage_epics.py` -- all 5 listed confirmed
- `manage_sagas.py` -- all 4 listed confirmed
- `commit.py` -- all 4 listed confirmed
- `validate_anchors.py` -- all 6 listed confirmed
- `release_gate.py` -- all 12 listed confirmed

### 1.2 Anchor References

**All anchor references in CLAUDE.md resolve to actual anchors in source files.** Each
`§namespace.symbol` reference was verified against the corresponding source file's
`# §namespace.symbol` or `<!-- §namespace.symbol -->` comment.

Both short aliases (e.g., `§sprint-run.phase_detection`) and verbose slugs
(e.g., `§sprint-run.phase_detection_reads_sprint_status_md`) are defined in SKILL.md
files where both are present, so references from both CLAUDE.md and CHEATSHEET.md resolve.

### 1.3 Required TOML Keys

CLAUDE.md states:
> Required TOML keys: `project.name`, `project.repo`, `project.language`,
> `paths.team_dir`, `paths.backlog_dir`, `paths.sprints_dir`, `ci.check_commands`,
> `ci.build_command`

Code (`_REQUIRED_TOML_KEYS` at line 391 of validate_config.py):
```python
_REQUIRED_TOML_KEYS = [
    ("project", "name"),
    ("project", "repo"),
    ("project", "language"),
    ("paths", "team_dir"),
    ("paths", "backlog_dir"),
    ("paths", "sprints_dir"),
    ("ci", "check_commands"),
    ("ci", "build_command"),
]
```

**Exact match.** No discrepancy.

### 1.4 Skeleton Template Count

CLAUDE.md claims "19 templates: 9 core + 10 deep-doc." Actual count from
`references/skeletons/*.tmpl`: **19 files.** All names match:

Core (9): project.toml, team-index.md, persona.md, giles.md, backlog-index.md,
milestone.md, rules.md, development.md, definition-of-done.md

Deep docs (10): saga.md, epic.md, story-detail.md, prd-index.md, prd-section.md,
test-plan-index.md, golden-path.md, test-case.md, story-map-index.md, team-topology.md

**Exact match.**

---

## 2. CHEATSHEET.md Accuracy

The CHEATSHEET uses anchor-based indices (not line numbers). All anchor references
in the CHEATSHEET were spot-checked by verifying the corresponding `§` comments exist
in the target source files.

### Spot-checked anchors (15 of ~120):

| Anchor | File | Status |
|--------|------|--------|
| §validate_config.safe_int | scripts/validate_config.py:31 | Correct |
| §validate_config.KANBAN_STATES | scripts/validate_config.py:828 | Correct |
| §update_burndown.build_rows | skills/sprint-run/scripts/update_burndown.py:156 | Correct |
| §sprint_teardown.collect_directories | scripts/sprint_teardown.py:86 | Correct |
| §sprint_teardown.remove_symlinks | scripts/sprint_teardown.py:213 | Correct |
| §sprint_teardown.remove_empty_dirs | scripts/sprint_teardown.py:265 | Correct |
| §sprint_teardown.check_active_loops | scripts/sprint_teardown.py:280 | Correct |
| §sprint_teardown.print_github_cleanup_hints | scripts/sprint_teardown.py:327 | Correct |
| §populate_issues._most_common_sprint | populate_issues.py:214 | Correct |
| §sprint-setup.step_2_github_bootstrap_labels_milestones_issues_ci | SKILL.md:49 | Correct |
| §sprint-monitor.step_0_sync_backlog_debounce_throttle | SKILL.md:49 | Correct |
| §sprint-monitor.step_1_5_drift_detection | SKILL.md:110 | Correct |
| §sprint-monitor.rate_limiting_and_deduplication | SKILL.md:283 | Correct |
| §sprint-release.build_artifacts | SKILL.md:109 | Correct |
| §sprint-release.github_release | SKILL.md:127 | Correct |

**All 15 spot checks passed.** No drift detected between CHEATSHEET anchors and code.

### CHEATSHEET functions vs CLAUDE.md

The CHEATSHEET lists more functions per script than CLAUDE.md. This is by design --
CLAUDE.md is a summary ("Key functions"), while CHEATSHEET is exhaustive. No
inconsistency: every function in CLAUDE.md appears in the CHEATSHEET, and the
CHEATSHEET adds supplementary entries.

Functions in CHEATSHEET but not CLAUDE.md (expected -- these are internal helpers):
- `sprint_teardown.py`: collect_directories, remove_symlinks, remove_generated,
  remove_empty_dirs, check_active_loops, print_github_cleanup_hints
- `sprint_init.py`: RICH_PERSONA_HEADINGS, ScanResult, _indicator, print_scan_results,
  print_generation_summary
- `bootstrap_github.py`: create_label, create_sprint_labels, _parse_saga_labels_from_backlog,
  create_saga_labels
- `populate_issues.py`: Story, _build_row_regex, _infer_sprint_number,
  get_existing_issues, get_milestone_numbers
- `sync_tracking.py`: find_milestone_title, _fetch_all_prs, slug_from_title, TF,
  read_tf, write_tf
- `update_burndown.py`: closed_date, load_tracking_metadata, main
- Various others in sync_backlog, sprint_analytics, team_voices, manage_epics/sagas

---

## 3. Skill SKILL.md Docs vs Script Behavior

### sprint-setup/SKILL.md

**Consistent.** Steps match implementation:
- Phase 0 calls sprint_init.py -- matches code
- Step 1 checks prerequisites -- matches bootstrap_github.py's check_prerequisites()
- Step 2 runs bootstrap_github.py, populate_issues.py, setup_ci.py -- matches code

No undocumented features. No documented features missing from code.

### sprint-run/SKILL.md

**Consistent with one observation:**

- Phase detection reads SPRINT-STATUS.md -- matches code logic
- Phase 1 (kickoff) matches ceremony-kickoff.md
- Phase 2 (story execution) matches story-execution.md + kanban-protocol.md
- Context Assembly section accurately describes PRD/test plan/saga injection
- Mid-sprint check-in matches sprint-monitor's step 2.5

**Observation:** The SKILL.md mentions "insights.md" injection into implementer/reviewer
prompts. This is a SKILL.md instruction to the LLM orchestrator, not a script feature.
The scripts themselves do not read or inject insights.md -- that is the LLM's
responsibility during context assembly. This is correctly designed but could be
misunderstood as a missing script feature.

### sprint-monitor/SKILL.md

**Consistent.** The SKILL.md describes steps 0-4 which match what check_status.py does:
- Step 0: sync_backlog.py
- Step 1: CI check
- Step 1.5: drift detection (branch divergence + direct pushes)
- Step 2: PR check
- Step 2.5: mid-sprint check-in
- Step 3: Sprint status
- Step 4: Report

**Minor mismatch:** SKILL.md step 3 says "Running `check_status.py` covers Steps 0-3"
but check_status.py actually calls sync_backlog internally only if the import succeeds
(it catches ImportError). The claim is mostly accurate but the fallback behavior isn't
documented.

### sprint-release/SKILL.md

**Consistent.** The 5 gates documented match the 5 gates in release_gate.py's
`validate_gates()`:
1. Stories (gate_stories)
2. CI (gate_ci)
3. PRs (gate_prs)
4. Tests (gate_tests)
5. Build (gate_build)

The version calculation, tag/push flow, release notes generation, and milestone closing
all match the do_release() implementation.

**Rollback procedure in SKILL.md describes manual cleanup commands, while release_gate.py
has automated rollback (`_rollback_tag()`, `_rollback_commit()`).** The SKILL.md focuses
on user-initiated rollback of a published release, while the code handles failure
recovery during the release process. These serve different purposes and are complementary,
not contradictory.

### sprint-teardown/SKILL.md

**Consistent.** The 4-phase cleanup matches sprint_teardown.py:
1. Symlinks removed first
2. Generated files prompted
3. Empty dirs cleaned up
4. Targets verified

The dry-run option matches `--dry-run` flag in the script. The `--force` flag for
skipping generated file prompts is documented in the script's help text but not
mentioned in SKILL.md (minor omission).

---

## 4. Kanban States

| Source | States |
|--------|--------|
| `validate_config.py` KANBAN_STATES | `todo, design, dev, review, integration, done` |
| `kanban-protocol.md` States table | `todo, design, dev, review, integration, done` |
| `bootstrap_github.py` create_static_labels() | `todo, design, dev, review, integration, done` |
| CLAUDE.md reference | "State machine (6 states)" |

**All four sources match exactly.** 6 states, same names.

---

## 5. Template Accuracy

### sprint_init.py's ConfigGenerator.generate() vs skeletons

The `generate()` method calls:
1. `generate_project_toml()` -- writes inline, does not use project.toml.tmpl
2. `generate_team()` -- uses team-index.md.tmpl (fallback), giles.md.tmpl (always)
3. `generate_backlog()` -- uses backlog-index.md.tmpl (fallback)
4. `generate_doc_symlinks()` -- uses rules.md.tmpl, development.md.tmpl (fallbacks)
5. `generate_definition_of_done()` -- uses definition-of-done.md.tmpl (always)
6. `generate_history_dir()` -- creates directory, no template

**Minor inconsistency: project.toml.tmpl exists but is not used by sprint_init.py.**
The ConfigGenerator writes project.toml inline via `generate_project_toml()`. The
template file `references/skeletons/project.toml.tmpl` exists as a reference document
but is never loaded by any code path. This is not a bug -- the generator needs to
interpolate scan results, which a static template cannot do -- but it means the template
could drift from what the generator actually produces.

**Skeleton templates not directly used by sprint_init.py:** persona.md.tmpl,
milestone.md.tmpl, and all 10 deep-doc templates. These are intended for manual use
or future expansion, not for automatic generation. The CLAUDE.md states templates are
"used by sprint_init.py when project files are missing" but this is only partially true --
only 5 of the 19 templates are actually loaded by the code. The other 14 exist as
reference templates for manual scaffolding.

---

## Summary of Findings

### Clean (no issues)
- All function names in CLAUDE.md match reality
- All anchor references resolve correctly
- Required TOML keys match exactly
- Kanban states are consistent across all sources
- Skeleton template count (19) matches documentation
- CHEATSHEET anchors are accurate (15/15 spot checks passed)
- Gate validation documentation matches implementation

### Minor Inconsistencies (informational, low priority)

1. **CLAUDE.md overstates template usage.** Says all 19 skeletons are "used by
   sprint_init.py" but only 5 are actually loaded by code. The other 14 are reference
   templates for manual use. (CLAUDE.md line 117)

2. **project.toml.tmpl exists but is never loaded.** ConfigGenerator writes project.toml
   inline. The template could drift from actual generated output.

3. **sprint-teardown SKILL.md omits --force flag.** The script supports `--force` to
   skip generated-file prompts, but the SKILL.md only documents `--dry-run`.

4. **sprint-monitor SKILL.md claim "check_status.py covers Steps 0-3" is slightly
   imprecise.** The sync_backlog import is wrapped in a try/except and may silently
   skip Step 0 if the import fails.

### No Critical Mismatches Found

The documentation is in good shape. All anchor references resolve, all function names
are accurate, and the architectural claims (config-driven, idempotent, GitHub as source
of truth) are faithfully implemented.
