# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

**giles** is a Claude Code plugin that runs agile sprints with persona-based development. It orchestrates GitHub issues, PRs, CI, kanban tracking, and sprint ceremonies (kickoff, demo, retro) using fictional team personas that implement and review code in-character.

## Plugin Structure

```
.claude-plugin/plugin.json   — plugin manifest (name, version, author)
skills/                      — 5 skills, each with SKILL.md entry point
  sprint-setup/              — one-time project bootstrap (GitHub labels, milestones, issues, CI)
  sprint-run/                — sprint execution (kickoff → stories → demo → retro)
  sprint-monitor/            — continuous CI/PR/burndown monitoring (designed for /loop)
  sprint-release/            — milestone release management (gates, tag, GitHub Release)
  sprint-teardown/           — safe removal of sprint-config/
scripts/                     — shared Python scripts (stdlib only, no external deps)
references/skeletons/        — .tmpl files used by sprint_init.py to scaffold sprint-config/
evals/evals.json             — skill evaluation scenarios
```

## Skill Lifecycle

`sprint-setup` → `sprint-run` (repeats per sprint) → `sprint-release` (at milestone end) → `sprint-teardown` (cleanup)

`sprint-monitor` runs alongside `sprint-run` via `/loop 5m sprint-monitor`.

## Quick File Lookup

For detailed §-anchor indices of all functions, sections, and reference files,
see `CHEATSHEET.md`. The tables below are a summary.

### Scripts (all stdlib-only Python 3.10+, no venv packages needed)

| Script | Purpose | Key functions |
|--------|---------|---------------|
| `scripts/validate_config.py` | Config validation + TOML parser + shared helpers | `parse_simple_toml()` §validate_config.parse_simple_toml, `validate_project()` §validate_config.validate_project, `load_config()` §validate_config.load_config, `safe_int()` §validate_config.safe_int, `parse_iso_date()` §validate_config.parse_iso_date, `gh()` §validate_config.gh, `gh_json()` §validate_config.gh_json, `extract_sp()` §validate_config.extract_sp, `get_team_personas()` §validate_config.get_team_personas, `get_milestones()` §validate_config.get_milestones, `get_base_branch()` §validate_config.get_base_branch, `get_sprints_dir()` §validate_config.get_sprints_dir, `get_prd_dir()` §validate_config.get_prd_dir, `get_test_plan_dir()` §validate_config.get_test_plan_dir, `get_sagas_dir()` §validate_config.get_sagas_dir, `get_epics_dir()` §validate_config.get_epics_dir, `get_story_map()` §validate_config.get_story_map, `extract_story_id()` §validate_config.extract_story_id, `kanban_from_labels()` §validate_config.kanban_from_labels, `find_milestone()` §validate_config.find_milestone, `warn_if_at_limit()` §validate_config.warn_if_at_limit, `list_milestone_issues()` §validate_config.list_milestone_issues, `detect_sprint()` §validate_config.detect_sprint, `get_ci_commands()` §validate_config.get_ci_commands, `TF` §validate_config.TF, `read_tf()` §validate_config.read_tf, `write_tf()` §validate_config.write_tf, `slug_from_title()` §validate_config.slug_from_title |
| `scripts/sprint_init.py` | Auto-detect project → generate sprint-config/ | `ProjectScanner` §sprint_init.ProjectScanner, `ConfigGenerator` §sprint_init.ConfigGenerator, `main()` §sprint_init.main |
| `scripts/sprint_teardown.py` | Safe removal of sprint-config/ | `classify_entries()` §sprint_teardown.classify_entries, `main()` §sprint_teardown.main |
| `skills/sprint-setup/scripts/bootstrap_github.py` | Create labels/milestones on GitHub | `create_label()` §bootstrap_github.create_label, `create_persona_labels()` §bootstrap_github.create_persona_labels, `_collect_sprint_numbers()` §bootstrap_github._collect_sprint_numbers, `create_sprint_labels()` §bootstrap_github.create_sprint_labels, `create_saga_labels()` §bootstrap_github.create_saga_labels, `create_static_labels()` §bootstrap_github.create_static_labels, `create_epic_labels()` §bootstrap_github.create_epic_labels, `create_milestones_on_github()` §bootstrap_github.create_milestones_on_github, `main()` §bootstrap_github.main |

| `skills/sprint-setup/scripts/populate_issues.py` | Parse milestones → GitHub issues | `parse_milestone_stories()` §populate_issues.parse_milestone_stories, `parse_detail_blocks()` §populate_issues.parse_detail_blocks, `enrich_from_epics()` §populate_issues.enrich_from_epics, `_most_common_sprint()` §populate_issues._most_common_sprint, `format_issue_body()` §populate_issues.format_issue_body, `build_milestone_title_map()` §populate_issues.build_milestone_title_map, `create_issue()` §populate_issues.create_issue |
| `skills/sprint-setup/scripts/setup_ci.py` | Generate .github/workflows/ci.yml | `generate_ci_yaml()` §setup_ci.generate_ci_yaml, `_SETUP_REGISTRY` §setup_ci._SETUP_REGISTRY (Rust/Python/Node/Go) |
| `scripts/kanban.py` | Kanban state machine — transitions, assign, update, sync, status | `TRANSITIONS` §kanban.TRANSITIONS, `validate_transition()` §kanban.validate_transition, `check_preconditions()` §kanban.check_preconditions, `check_wip_limit()` §kanban.check_wip_limit, `_count_review_rounds()` §kanban._count_review_rounds, `do_transition()` §kanban.do_transition, `do_assign()` §kanban.do_assign, `do_update()` §kanban.do_update, `do_sync()` §kanban.do_sync, `do_status()` §kanban.do_status, `find_story()` §kanban.find_story, `atomic_write_tf()` §kanban.atomic_write_tf, `lock_story()` §kanban.lock_story, `lock_sprint()` §kanban.lock_sprint |
| `skills/sprint-run/scripts/sync_tracking.py` | Reconcile local tracking ↔ GitHub | `sync_one()` §sync_tracking.sync_one, `create_from_issue()` §sync_tracking.create_from_issue |
| `skills/sprint-run/scripts/update_burndown.py` | Update burndown from GitHub milestones | `write_burndown()` §update_burndown.write_burndown, `update_sprint_status()` §update_burndown.update_sprint_status, `build_rows()` §update_burndown.build_rows |
| `scripts/sync_backlog.py` | Backlog auto-sync with debounce/throttle | `hash_milestone_files()` §sync_backlog.hash_milestone_files, `check_sync()` §sync_backlog.check_sync, `do_sync()` §sync_backlog.do_sync, `main()` §sync_backlog.main |
| `scripts/sprint_analytics.py` | Sprint metrics (velocity, review rounds, workload) | `compute_velocity()` §sprint_analytics.compute_velocity, `compute_review_rounds()` §sprint_analytics.compute_review_rounds, `compute_workload()` §sprint_analytics.compute_workload, `format_report()` §sprint_analytics.format_report, `main()` §sprint_analytics.main |
| `skills/sprint-monitor/scripts/check_status.py` | CI + PR + milestone + drift + smoke check | `check_ci()` §check_status.check_ci, `check_prs()` §check_status.check_prs, `check_milestone()` §check_status.check_milestone, `check_branch_divergence()` §check_status.check_branch_divergence, `check_direct_pushes()` §check_status.check_direct_pushes, `check_smoke()` §check_status.check_smoke, `check_integration_debt()` §check_status.check_integration_debt, `write_log()` §check_status.write_log, `main()` §check_status.main |
| `scripts/team_voices.py` | Extract persona commentary from saga/epic files | `extract_voices()` §team_voices.extract_voices, `VOICE_PATTERN` §team_voices.VOICE_PATTERN, `main()` §team_voices.main |
| `scripts/traceability.py` | Bidirectional story/PRD/test mapping with gap detection | `parse_stories()` §traceability.parse_stories, `parse_test_cases()` §traceability.parse_test_cases, `parse_requirements()` §traceability.parse_requirements, `build_traceability()` §traceability.build_traceability, `format_report()` §traceability.format_report |
| `scripts/test_coverage.py` | Compare planned test cases vs actual test files | `parse_planned_tests()` §test_coverage.parse_planned_tests, `detect_test_functions()` §test_coverage.detect_test_functions, `scan_project_tests()` §test_coverage.scan_project_tests, `check_test_coverage()` §test_coverage.check_test_coverage, `_TEST_PATTERNS` §test_coverage._TEST_PATTERNS |
| `scripts/manage_epics.py` | Epic CRUD: add, remove, reorder stories | `parse_epic()` §manage_epics.parse_epic, `add_story()` §manage_epics.add_story, `remove_story()` §manage_epics.remove_story, `reorder_stories()` §manage_epics.reorder_stories, `renumber_stories()` §manage_epics.renumber_stories |
| `scripts/manage_sagas.py` | Saga management: allocation, index, voices | `parse_saga()` §manage_sagas.parse_saga, `update_sprint_allocation()` §manage_sagas.update_sprint_allocation, `update_epic_index()` §manage_sagas.update_epic_index, `update_team_voices()` §manage_sagas.update_team_voices |
| `scripts/smoke_test.py` | Run configured smoke_command, write history | `run_smoke()` §smoke_test.run_smoke, `write_history()` §smoke_test.write_history, `main()` §smoke_test.main |
| `scripts/gap_scanner.py` | Detect sprints with no story touching entry points | `scan_for_gaps()` §gap_scanner.scan_for_gaps, `story_touches_entry_point()` §gap_scanner.story_touches_entry_point, `main()` §gap_scanner.main |
| `scripts/test_categories.py` | Categorize tests as unit/component/integration/smoke | `classify_test_file()` §test_categories.classify_test_file, `analyze()` §test_categories.analyze, `format_report()` §test_categories.format_report, `main()` §test_categories.main |
| `scripts/risk_register.py` | Risk register CRUD: add, resolve, list, escalate | `add_risk()` §risk_register.add_risk, `resolve_risk()` §risk_register.resolve_risk, `list_open_risks()` §risk_register.list_open_risks, `escalate_overdue()` §risk_register.escalate_overdue, `main()` §risk_register.main |
| `scripts/assign_dod_level.py` | Auto-classify stories as app/library DoD level | `classify_story()` §assign_dod_level.classify_story, `assign_levels()` §assign_dod_level.assign_levels, `main()` §assign_dod_level.main |
| `scripts/history_to_checklist.py` | Generate review checklists from persona history | `extract_checklist_items()` §history_to_checklist.extract_checklist_items, `generate_checklists()` §history_to_checklist.generate_checklists, `main()` §history_to_checklist.main |
| `scripts/commit.py` | Enforce conventional commits and atomic changes | `validate_message()` §commit.validate_message, `check_atomicity()` §commit.check_atomicity, `run_commit()` §commit.run_commit, `main()` §commit.main |
| `scripts/validate_anchors.py` | Validate §-prefixed anchor references in docs | `resolve_namespace()` §validate_anchors.resolve_namespace, `find_anchor_defs()` §validate_anchors.find_anchor_defs, `find_anchor_refs()` §validate_anchors.find_anchor_refs, `check_anchors()` §validate_anchors.check_anchors, `fix_missing_anchors()` §validate_anchors.fix_missing_anchors, `main()` §validate_anchors.main |
| `skills/sprint-release/scripts/release_gate.py` | Release gates, versioning, notes, publishing | `find_latest_semver_tag()` §release_gate.find_latest_semver_tag, `parse_commits_since()` §release_gate.parse_commits_since, `calculate_version()` §release_gate.calculate_version, `gate_stories()` §release_gate.gate_stories, `gate_ci()` §release_gate.gate_ci, `gate_prs()` §release_gate.gate_prs, `gate_tests()` §release_gate.gate_tests, `gate_build()` §release_gate.gate_build, `validate_gates()` §release_gate.validate_gates, `write_version_to_toml()` §release_gate.write_version_to_toml, `generate_release_notes()` §release_gate.generate_release_notes, `do_release()` §release_gate.do_release, `main()` §release_gate.main |

### Skill Entry Points

| Skill | SKILL.md | Key sections |
|-------|----------|-------------|
| sprint-setup | `skills/sprint-setup/SKILL.md` | Phase 0: Config init §sprint-setup.phase_0_project_initialization, Step 1: Prerequisites §sprint-setup.step_1_check_prerequisites, Step 2: GitHub bootstrap §sprint-setup.step_2_github_bootstrap |
| sprint-run | `skills/sprint-run/SKILL.md` | Phase detection §sprint-run.phase_detection, Phase 1: Kickoff §sprint-run.phase_1_sprint_kickoff_interactive, Phase 2: Story execution §sprint-run.phase_2_story_execution_autonomous_per_story_interactive_at_gates, Mid-sprint check-in §sprint-run.mid_sprint_check_in, Context Assembly §sprint-run.context_assembly_for_agent_dispatch, Phase 3: Demo §sprint-run.phase_3_sprint_demo_interactive, Phase 4: Retro §sprint-run.phase_4_sprint_retro_interactive (Giles facilitates all ceremonies) |
| sprint-monitor | `skills/sprint-monitor/SKILL.md` | Prerequisites §sprint-monitor.prerequisites, Backlog sync §sprint-monitor.step_0_sync_backlog, CI check §sprint-monitor.step_1_check_ci_status, Drift detection §sprint-monitor.step_1_5_drift_detection, PR check §sprint-monitor.step_2_check_open_prs, Mid-sprint check-in §sprint-monitor.step_2_5_mid_sprint_check_in, Check Sprint Status §sprint-monitor.step_3_check_sprint_status, Rate limiting §sprint-monitor.rate_limiting |
| sprint-release | `skills/sprint-release/SKILL.md` | Gate validation §sprint-release.gate_validation, Tag+release §sprint-release.step_2_tag_and_release, Build artifacts §sprint-release.build_artifacts, GitHub Release §sprint-release.github_release, Rollback §sprint-release.rollback |
| sprint-teardown | `skills/sprint-teardown/SKILL.md` | Safety principles §sprint-teardown.safety_principles, Dry run §sprint-teardown.step_3_dry_run, Execute §sprint-teardown.step_4_execute_teardown |

### Reference Files

| File | What to find there |
|------|-------------------|
| `skills/sprint-run/references/kanban-protocol.md` | State machine (6 states), transition rules, WIP limits |
| `skills/sprint-run/references/persona-guide.md` | Persona assignment rules, voice guidelines, GitHub header format, Giles rules §persona-guide.giles_scrum_master, PM role §persona-guide.pm_persona |
| `skills/sprint-run/references/ceremony-kickoff.md` | Giles/PM split, team read §ceremony-kickoff.team_read, saga context §ceremony-kickoff.saga_context, sprint theme §ceremony-kickoff.sprint_theme, process context (analytics) §ceremony-kickoff.process_context_analytics, confidence check §ceremony-kickoff.confidence_check, scope negotiation §ceremony-kickoff.scope_negotiation, exit criteria §ceremony-kickoff.exit_criteria |
| `skills/sprint-run/references/ceremony-demo.md` | Giles/PM split, ensemble framing §ceremony-demo.facilitation, artifact requirements, test plan verification §ceremony-demo.test_plan_verification, insights in Q&A §ceremony-demo.4_team_q_a_in_persona, confidence probing §ceremony-demo.4_team_q_a_in_persona, acceptance verification |
| `skills/sprint-run/references/ceremony-retro.md` | Giles/PM split, psychological safety §ceremony-retro.facilitation, insights in retro §ceremony-retro.facilitation, Start/Stop/Continue, feedback distillation, sprint analytics §ceremony-retro.5_sprint_analytics, write sprint history §ceremony-retro.6_write_sprint_history, emotional shift §ceremony-retro.6_write_sprint_history, DoD review §ceremony-retro.7_definition_of_done_review |
| `skills/sprint-run/references/context-recovery.md` | State reconstruction after context loss: read status/burndown, sync tracking, query GitHub, resume phase |
| `skills/sprint-run/references/story-execution.md` | Story lifecycle through kanban states, branch patterns, design/dev/review/integration transitions |
| `skills/sprint-run/references/tracking-formats.md` | SPRINT-STATUS.md format, story tracking file YAML frontmatter |
| `skills/sprint-run/agents/implementer.md` | Subagent template: TDD, PR creation, motivation context §implementer.motivation_context, context management §implementer.context_management, strategic context §implementer.strategic_context, test plan context §implementer.test_plan_context, sprint history §implementer.sprint_history, confidence signals §implementer.confidence_signals |
| `skills/sprint-run/agents/reviewer.md` | Subagent template: three-pass review (correctness/conventions/testing), confidence reading §reviewer.review_process, sprint history callbacks §reviewer.review_process, motivation insights §reviewer.review_process, test coverage verification §reviewer.2_5_verify_test_coverage_if_test_plan_context_provided |
| `skills/sprint-setup/references/github-conventions.md` | Label taxonomy, issue template, PR template, review template |
| `skills/sprint-setup/references/prerequisites-checklist.md` | Prerequisites check: gh CLI, auth, superpowers plugin, git remote, toolchain, Python version |
| `skills/sprint-setup/references/ci-workflow-template.md` | CI YAML template structure |
| `skills/sprint-release/references/release-checklist.md` | Per-milestone gate criteria template |

### Configuration System

All skills read from `sprint-config/project.toml` via `validate_config.load_config()`. Required structure:

```
sprint-config/
├── project.toml          — REQUIRED — [project], [paths], [ci], [conventions], [release]
├── definition-of-done.md — REQUIRED — evolving DoD (baseline + retro-driven additions)
├── team/INDEX.md          — REQUIRED — markdown table: Name | Role | File
├── team/{name}.md         — REQUIRED — persona files (symlinks to project docs)
├── team/giles.md          — runtime — built-in scrum master (copied by sprint-init, checked by sprint-run)
├── team/history/          — runtime — Sprint History files (written by Giles during retro)
├── team/insights.md       — runtime — motivation distillation (LLM-generated at kickoff)
├── backlog/INDEX.md       — REQUIRED — backlog routing table
├── backlog/milestones/    — REQUIRED — one .md per milestone with story tables
├── rules.md               — REQUIRED — project conventions (symlink)
└── development.md         — REQUIRED — dev process guide (symlink)
```

Required TOML keys: `project.name`, `project.repo`, `project.language`, `paths.team_dir`, `paths.backlog_dir`, `paths.sprints_dir`, `ci.check_commands`, `ci.build_command` (see §validate_config._REQUIRED_TOML_KEYS).
Optional: `project.base_branch` (defaults to `main` — branch PRs target and CI watches).
Optional `[conventions]` keys (generated by §sprint_init.ConfigGenerator): `branch_pattern` (documents the branch naming convention), `commit_style` (documents the commit format convention). These are informational — referenced by humans and skill prompts but not read by scripts.
Optional deep-doc keys: `paths.prd_dir`, `paths.test_plan_dir`, `paths.sagas_dir`, `paths.epics_dir`, `paths.story_map`, `paths.team_topology`.

Template: `references/skeletons/project.toml.tmpl`

### Skeleton Templates

`references/skeletons/*.tmpl` — used by `sprint_init.py` when project files are missing. 19 templates:
- **Core** (9): `project.toml`, `team-index.md`, `persona.md`, `giles.md` (built-in scrum master), `backlog-index.md`, `milestone.md`, `rules.md`, `development.md`, `definition-of-done.md`
- **Deep docs** (10): `saga.md`, `epic.md`, `story-detail.md`, `prd-index.md`, `prd-section.md`, `test-plan-index.md`, `golden-path.md`, `test-case.md`, `story-map-index.md`, `team-topology.md`

## Key Architectural Decisions

- **Config-driven**: Nothing is hardcoded to a specific project. All project-specific values come from `sprint-config/project.toml`.
- **Symlink-based config**: `sprint_init.py` creates symlinks from `sprint-config/` to existing project files. Teardown removes symlinks without touching originals. Exception: Giles is copied (plugin-owned), not symlinked.
- **Custom TOML parser**: §validate_config.parse_simple_toml is a minimal TOML parser (no `tomllib` dependency) supporting double-quoted strings (with escape processing including `\uXXXX`), single-quoted literal strings, ints, bools, arrays, bare keys, and sections. Floats are not supported (returned as raw strings).
- **Scripts import chain**: Skill scripts in `skills/*/scripts/` do `sys.path.insert(0, ...)` to reach `scripts/validate_config.py` four directories up. Scripts in the top-level `scripts/` directory use a single-level parent path.
- **Two-path state management**: `kanban.py` is the mutation path (local-first, syncs to GitHub on every write). `sync_tracking.py` is the reconciliation path (accepts GitHub state for PR linkage, branch, and completion metadata). Both paths can write `status` — `kanban.py` validates transitions, `sync_tracking.py` accepts any valid state from GitHub. For kanban transitions and persona assignment, use `kanban.py`. For field updates (`pr_number`, `branch`), use `kanban.py update`. For filling in PR/branch fields from GitHub and correcting stale statuses, use `sync_tracking.py`.
- **Idempotent scripts**: All bootstrap and monitoring scripts skip resources that already exist.
- **Cross-skill dependency**: `scripts/sync_backlog.py` imports `bootstrap_github` and `populate_issues` from `skills/sprint-setup/scripts/` for backlog auto-sync. This is an intentional coupling — sync_backlog reuses the idempotent creation functions rather than duplicating them.

## Common Tasks

| Task | What to do |
|------|-----------|
| Add a new skill | Create `skills/<name>/SKILL.md` with YAML frontmatter (`name`, `description`) |
| Modify config validation | Edit `scripts/validate_config.py` — `_REQUIRED_FILES` §validate_config._REQUIRED_FILES, `_REQUIRED_TOML_KEYS` §validate_config._REQUIRED_TOML_KEYS |
| Add a new label category | Edit `skills/sprint-setup/scripts/bootstrap_github.py` — add to `create_static_labels()` §bootstrap_github.create_static_labels or create new function |
| Add language support to CI | Edit `skills/sprint-setup/scripts/setup_ci.py` — add to `_SETUP_REGISTRY` §setup_ci._SETUP_REGISTRY and `_ENV_BLOCKS` §setup_ci._ENV_BLOCKS |
| Add a new kanban state | Update `skills/sprint-run/references/kanban-protocol.md` + §validate_config.KANBAN_STATES |
| Change sprint tracking format | Edit `skills/sprint-run/references/tracking-formats.md` + update `sync_tracking.py` and `update_burndown.py` |
| Add a skeleton template | Create `references/skeletons/<name>.tmpl`, wire it in §sprint_init.ConfigGenerator (ConfigGenerator.generate) |
| Add deep documentation support | Set optional TOML keys (`paths.prd_dir`, `paths.test_plan_dir`, `paths.sagas_dir`, `paths.epics_dir`, `paths.story_map`, `paths.team_topology`). Sprint-run §sprint-run.context_assembly_for_agent_dispatch handles injection into agent prompts. |
