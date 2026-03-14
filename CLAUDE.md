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

For detailed line-number indices of all functions, sections, and reference files,
see `CHEATSHEET.md`. The tables below are a summary.

### Scripts (all stdlib-only Python 3.10+, no venv packages needed)

| Script | Purpose | Key functions |
|--------|---------|---------------|
| `scripts/validate_config.py` | Config validation + TOML parser + shared helpers | `parse_simple_toml()` :48, `validate_project()` :258, `load_config()` :435, `gh()` :23, `gh_json()` :33, `extract_sp()` :560, `get_team_personas()` :466, `get_milestones()` :494, `get_base_branch()` :518, `get_prd_dir()` :524, `get_test_plan_dir()` :533, `get_sagas_dir()` :542, `get_epics_dir()` :551, `get_story_map()` :589 |
| `scripts/sprint_init.py` | Auto-detect project → generate sprint-config/ | `ProjectScanner.scan()` :459, `ConfigGenerator.generate()` :793, `_inject_giles()` :669, `generate_definition_of_done()` :738, `generate_history_dir()` :743, `detect_prd_dir()` :336, `detect_test_plan_dir()` :353, `detect_sagas_dir()` :362, `detect_epics_dir()` :371, `detect_story_map()` :380, `detect_team_topology()` :393 |
| `scripts/sprint_teardown.py` | Safe removal of sprint-config/ | `classify_entries()` :20, `main()` :370 |
| `skills/sprint-setup/scripts/bootstrap_github.py` | Create labels/milestones on GitHub | `create_persona_labels()` :64, `_collect_sprint_numbers()` :77, `create_static_labels()` :157, `create_epic_labels()` :186, `create_milestones_on_github()` :197, `main()` :240 |
| `skills/sprint-setup/scripts/populate_issues.py` | Parse milestones → GitHub issues | `parse_milestone_stories()` :76, `parse_detail_blocks()` :141, `enrich_from_epics()` :191, `format_issue_body()` :292, `build_milestone_title_map()` :262, `create_issue()` :332 |
| `skills/sprint-setup/scripts/setup_ci.py` | Generate .github/workflows/ci.yml | `generate_ci_yaml()` :203, `_SETUP_REGISTRY` :61 (Rust/Python/Node/Go) |
| `skills/sprint-run/scripts/sync_tracking.py` | Reconcile local tracking ↔ GitHub | `sync_one()` :181, `create_from_issue()` :228 |
| `skills/sprint-run/scripts/update_burndown.py` | Update burndown from GitHub milestones | `write_burndown()` :52, `update_sprint_status()` :91 |
| `scripts/sync_backlog.py` | Backlog auto-sync with debounce/throttle | `hash_milestone_files()` :32, `check_sync()` :98, `do_sync()` :138, `main()` :181 |
| `scripts/sprint_analytics.py` | Sprint metrics (velocity, review rounds, workload) | `compute_velocity()` :38, `compute_review_rounds()` :76, `compute_workload()` :125, `format_report()` :149, `main()` :184 |
| `skills/sprint-monitor/scripts/check_status.py` | CI + PR + milestone + drift check | `check_ci()` :35, `check_prs()` :91, `check_milestone()` :167, `check_branch_divergence()` :222, `check_direct_pushes()` :260 |
| `scripts/team_voices.py` | Extract persona commentary from saga/epic files | `extract_voices()` :29, `VOICE_PATTERN` :24, `main()` :83 |
| `scripts/traceability.py` | Bidirectional story/PRD/test mapping with gap detection | `parse_stories()` :29, `parse_test_cases()` :76, `parse_requirements()` :97, `build_traceability()` :122, `format_report()` :165 |
| `scripts/test_coverage.py` | Compare planned test cases vs actual test files | `parse_planned_tests()` :40, `detect_test_functions()` :58, `scan_project_tests()` :66, `check_test_coverage()` :90, `_TEST_PATTERNS` :21 |
| `scripts/manage_epics.py` | Epic CRUD: add, remove, reorder stories | `parse_epic()` :26, `add_story()` :188, `remove_story()` :203, `reorder_stories()` :233, `renumber_stories()` :287 |
| `scripts/manage_sagas.py` | Saga management: allocation, index, voices | `parse_saga()` :31, `update_sprint_allocation()` :137, `update_epic_index()` :169, `update_team_voices()` :224 |

### Skill Entry Points

| Skill | SKILL.md | Key sections |
|-------|----------|-------------|
| sprint-setup | `skills/sprint-setup/SKILL.md` | Phase 0: Config init :22, Step 1: Prerequisites :32, Step 2: GitHub bootstrap :46 |
| sprint-run | `skills/sprint-run/SKILL.md` | Phase detection :29, Phase 1: Kickoff :44, Phase 2: Story execution :50, Mid-sprint check-in :54, Context Assembly :75, Phase 3: Demo :109, Phase 4: Retro :115 (Giles facilitates all ceremonies) |
| sprint-monitor | `skills/sprint-monitor/SKILL.md` | Prerequisites :28, Backlog sync :46, CI check :69, Drift detection :103, PR check :133, Mid-sprint check-in :182, Burndown :223, Rate limiting :266 |
| sprint-release | `skills/sprint-release/SKILL.md` | Gate validation :49, Tag+release :81, Build artifacts :102, GitHub Release :124, Rollback :243 |
| sprint-teardown | `skills/sprint-teardown/SKILL.md` | Safety principles :14, Dry run :63, Execute :116 |

### Reference Files

| File | What to find there |
|------|-------------------|
| `skills/sprint-run/references/kanban-protocol.md` | State machine (6 states), transition rules, WIP limits |
| `skills/sprint-run/references/persona-guide.md` | Persona assignment rules, voice guidelines, GitHub header format, Giles rules :47, PM role :59 |
| `skills/sprint-run/references/ceremony-kickoff.md` | Giles/PM split, team read :41, saga context :61, sprint theme :20, process context (analytics) :78, confidence check :141, scope negotiation :161, exit criteria :231 |
| `skills/sprint-run/references/ceremony-demo.md` | Giles/PM split, ensemble framing :17, artifact requirements, test plan verification :65, insights in Q&A :81, confidence probing :86, acceptance verification |
| `skills/sprint-run/references/ceremony-retro.md` | Giles/PM split, psychological safety :25, insights in retro :30, Start/Stop/Continue, feedback distillation, sprint analytics :101, write sprint history :118, emotional shift :136, DoD review :141 |
| `skills/sprint-run/references/context-recovery.md` | State reconstruction after context loss: read status/burndown, sync tracking, query GitHub, resume phase |
| `skills/sprint-run/references/story-execution.md` | Story lifecycle through kanban states, branch patterns, design/dev/review/integration transitions |
| `skills/sprint-run/references/tracking-formats.md` | SPRINT-STATUS.md format, story tracking file YAML frontmatter, burndown format |
| `skills/sprint-run/agents/implementer.md` | Subagent template: TDD, PR creation, motivation context :49, context management :57, strategic context :31, test plan context :34, sprint history :37, confidence signals :106 |
| `skills/sprint-run/agents/reviewer.md` | Subagent template: three-pass review (correctness/conventions/testing), confidence reading :41, sprint history callbacks :11, motivation insights :17, test coverage verification :84 |
| `skills/sprint-setup/references/github-conventions.md` | Label taxonomy, issue template, PR template, review template |
| `skills/sprint-setup/references/ci-workflow-template.md` | CI YAML template structure |
| `skills/sprint-release/references/release-checklist.md` | Per-milestone gate criteria template |

### Configuration System

All skills read from `sprint-config/project.toml` via `validate_config.load_config()`. Required structure:

```
sprint-config/
├── project.toml          — [project], [paths], [ci], [conventions], [release]
├── definition-of-done.md — evolving DoD (baseline + retro-driven additions)
├── team/INDEX.md          — markdown table: Name | Role | File
├── team/{name}.md         — persona files (symlinks to project docs)
├── team/giles.md          — built-in scrum master (copied, not symlinked)
├── team/history/          — Sprint History files (written by Giles during retro)
├── team/insights.md       — motivation distillation (LLM-generated at kickoff, regenerated per sprint)
├── backlog/INDEX.md       — backlog routing table
├── backlog/milestones/    — one .md per milestone with story tables
├── rules.md               — project conventions (symlink)
└── development.md         — dev process guide (symlink)
```

Required TOML keys: `project.name`, `project.repo`, `project.language`, `paths.team_dir`, `paths.backlog_dir`, `paths.sprints_dir`, `ci.check_commands`, `ci.build_command` (see `validate_config.py:199`).
Optional: `project.base_branch` (defaults to `main` — branch PRs target and CI watches).
Optional `[conventions]` keys (generated by `sprint_init.py:608-614`): `branch_pattern` (branch naming template, used by story-execution.md), `commit_style` (conventional commits format), `merge_strategy` (squash/merge/rebase, used by sprint-monitor for PR merges).
Optional deep-doc keys: `paths.prd_dir`, `paths.test_plan_dir`, `paths.sagas_dir`, `paths.epics_dir`, `paths.story_map`, `paths.team_topology`, `paths.feedback_dir`.

Template: `references/skeletons/project.toml.tmpl`

### Skeleton Templates

`references/skeletons/*.tmpl` — used by `sprint_init.py` when project files are missing. 19 templates:
- **Core** (9): `project.toml`, `team-index.md`, `persona.md`, `giles.md` (built-in scrum master), `backlog-index.md`, `milestone.md`, `rules.md`, `development.md`, `definition-of-done.md`
- **Deep docs** (10): `saga.md`, `epic.md`, `story-detail.md`, `prd-index.md`, `prd-section.md`, `test-plan-index.md`, `golden-path.md`, `test-case.md`, `story-map-index.md`, `team-topology.md`

## Key Architectural Decisions

- **Config-driven**: Nothing is hardcoded to a specific project. All project-specific values come from `sprint-config/project.toml`.
- **Symlink-based config**: `sprint_init.py` creates symlinks from `sprint-config/` to existing project files. Teardown removes symlinks without touching originals. Exception: Giles is copied (plugin-owned), not symlinked.
- **Custom TOML parser**: `validate_config.py:43` has a minimal TOML parser (no `tomllib` dependency) supporting strings, ints, bools, arrays, sections.
- **Scripts import chain**: All skill scripts do `sys.path.insert(0, ...)` to reach `scripts/validate_config.py` four directories up.
- **GitHub as source of truth**: `sync_tracking.py` treats GitHub issue/PR state as authoritative and updates local tracking files to match.
- **Idempotent scripts**: All bootstrap and monitoring scripts skip resources that already exist.

## Common Tasks

| Task | What to do |
|------|-----------|
| Add a new skill | Create `skills/<name>/SKILL.md` with YAML frontmatter (`name`, `description`) |
| Modify config validation | Edit `scripts/validate_config.py` — `_REQUIRED_FILES` :231, `_REQUIRED_TOML_KEYS` :244 |
| Add a new label category | Edit `skills/sprint-setup/scripts/bootstrap_github.py` — add to `create_static_labels()` :157 or create new function |
| Add language support to CI | Edit `skills/sprint-setup/scripts/setup_ci.py` — add to `_SETUP_REGISTRY` :61 and `_ENV_BLOCKS` :75 |
| Add a new kanban state | Update `skills/sprint-run/references/kanban-protocol.md` + `sync_tracking.py:26` `KANBAN_STATES` |
| Change sprint tracking format | Edit `skills/sprint-run/references/tracking-formats.md` + update `sync_tracking.py` and `update_burndown.py` |
| Add a skeleton template | Create `references/skeletons/<name>.tmpl`, wire it in `sprint_init.py:793` (ConfigGenerator.generate) |
| Add deep documentation support | Set optional TOML keys (`paths.prd_dir`, `paths.test_plan_dir`, `paths.sagas_dir`, `paths.epics_dir`, `paths.story_map`, `paths.team_topology`). Sprint-run Context Assembly (:75 in SKILL.md) handles injection into agent prompts. |
