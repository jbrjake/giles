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
| `scripts/validate_config.py` | Config validation + TOML parser | `validate_project()` :191, `load_config()` :368, `parse_simple_toml()` :21, `get_team_personas()` :398, `get_milestones()` :426, `get_base_branch()` :450, `get_prd_dir()` :456, `get_test_plan_dir()` :465, `get_sagas_dir()` :474, `get_epics_dir()` :483, `get_story_map()` :492 |
| `scripts/sprint_init.py` | Auto-detect project → generate sprint-config/ | `ProjectScanner.scan()` :458, `ConfigGenerator.generate()` :736, `_inject_giles()` :673, `detect_prd_dir()` :340, `detect_test_plan_dir()` :357, `detect_sagas_dir()` :366, `detect_epics_dir()` :375, `detect_story_map()` :384, `detect_team_topology()` :397 |
| `scripts/sprint_teardown.py` | Safe removal of sprint-config/ | `classify_entries()` :19, `main()` :347 |
| `skills/sprint-setup/scripts/bootstrap_github.py` | Create labels/milestones on GitHub | `create_persona_labels()` :78, `_collect_sprint_numbers()` :91, `create_static_labels()` :171, `create_epic_labels()` :200, `create_milestones_on_github()` :211, `main()` :253 |
| `skills/sprint-setup/scripts/populate_issues.py` | Parse milestones → GitHub issues | `parse_milestone_stories()` :85, `parse_detail_blocks()` :150, `enrich_from_epics()` :200, `format_issue_body()` :297, `_build_milestone_title_map()` :267, `create_issue()` :337 |
| `skills/sprint-setup/scripts/setup_ci.py` | Generate .github/workflows/ci.yml | `generate_ci_yaml()` :202, `_SETUP_REGISTRY` :60 (Rust/Python/Node/Go) |
| `skills/sprint-run/scripts/sync_tracking.py` | Reconcile local tracking ↔ GitHub | `sync_one()` :201, `create_from_issue()` :248 |
| `skills/sprint-run/scripts/update_burndown.py` | Update burndown from GitHub milestones | `write_burndown()` :100, `update_sprint_status()` :139 |
| `scripts/sync_backlog.py` | Backlog auto-sync with debounce/throttle | `hash_milestone_files()` :32, `check_sync()` :98, `do_sync()` :138, `main()` :181 |
| `skills/sprint-monitor/scripts/check_status.py` | CI + PR + milestone status check | `check_ci()` :62, `check_prs()` :118, `check_milestone()` :194 |

### Skill Entry Points

| Skill | SKILL.md | Key sections |
|-------|----------|-------------|
| sprint-setup | `skills/sprint-setup/SKILL.md` | Phase 0: Config init :22, Step 1: Prerequisites :32, Step 2: GitHub bootstrap :46 |
| sprint-run | `skills/sprint-run/SKILL.md` | Phase detection :29, Phase 1: Kickoff :44, Phase 2: Story execution :50, Context Assembly :65, Phase 3: Demo :97, Phase 4: Retro :103 (Giles facilitates all ceremonies) |
| sprint-monitor | `skills/sprint-monitor/SKILL.md` | Prerequisites :27, Backlog sync :46, CI check :69, PR check :103, Burndown :152, Rate limiting :195 |
| sprint-release | `skills/sprint-release/SKILL.md` | Gate validation :49, Tag+release :81, Build artifacts :102, GitHub Release :124, Rollback :243 |
| sprint-teardown | `skills/sprint-teardown/SKILL.md` | Safety principles :14, Dry run :63, Execute :116 |

### Reference Files

| File | What to find there |
|------|-------------------|
| `skills/sprint-run/references/kanban-protocol.md` | State machine (6 states), transition rules, WIP limits |
| `skills/sprint-run/references/persona-guide.md` | Persona assignment rules, voice guidelines, GitHub header format, Giles rules :44, PM role :56 |
| `skills/sprint-run/references/ceremony-kickoff.md` | Giles/PM split, saga context :41, sprint theme :20, confidence check :99, scope negotiation :119, exit criteria :189 |
| `skills/sprint-run/references/ceremony-demo.md` | Giles/PM split, ensemble framing :17, artifact requirements, test plan verification :57, acceptance verification |
| `skills/sprint-run/references/ceremony-retro.md` | Giles/PM split, psychological safety :24, Start/Stop/Continue, feedback distillation, doc change rules |
| `skills/sprint-run/agents/implementer.md` | Subagent template: TDD, PR creation, strategic context :31, test plan context :34 |
| `skills/sprint-run/agents/reviewer.md` | Subagent template: PR review, in-persona voice, test coverage verification :63 |
| `skills/sprint-setup/references/github-conventions.md` | Label taxonomy, issue template, PR template, review template |
| `skills/sprint-setup/references/ci-workflow-template.md` | CI YAML template structure |
| `skills/sprint-release/references/release-checklist.md` | Per-milestone gate criteria template |

### Configuration System

All skills read from `sprint-config/project.toml` via `validate_config.load_config()`. Required structure:

```
sprint-config/
├── project.toml          — [project], [paths], [ci], [conventions], [release]
├── team/INDEX.md          — markdown table: Name | Role | File
├── team/{name}.md         — persona files (symlinks to project docs)
├── team/giles.md          — built-in scrum master (copied, not symlinked)
├── backlog/INDEX.md       — backlog routing table
├── backlog/milestones/    — one .md per milestone with story tables
├── rules.md               — project conventions (symlink)
└── development.md         — dev process guide (symlink)
```

Required TOML keys: `project.name`, `project.repo`, `project.language`, `paths.team_dir`, `paths.backlog_dir`, `paths.sprints_dir`, `ci.check_commands`, `ci.build_command` (see `validate_config.py:177`).
Optional: `project.base_branch` (defaults to `main` — branch PRs target and CI watches).
Optional deep-doc keys: `paths.prd_dir`, `paths.test_plan_dir`, `paths.sagas_dir`, `paths.epics_dir`, `paths.story_map`, `paths.team_topology`, `paths.feedback_dir`.

Template: `references/skeletons/project.toml.tmpl`

### Skeleton Templates

`references/skeletons/*.tmpl` — used by `sprint_init.py` when project files are missing. 18 templates:
- **Core** (8): `project.toml`, `team-index.md`, `persona.md`, `giles.md` (built-in scrum master), `backlog-index.md`, `milestone.md`, `rules.md`, `development.md`
- **Deep docs** (10): `saga.md`, `epic.md`, `story-detail.md`, `prd-index.md`, `prd-section.md`, `test-plan-index.md`, `golden-path.md`, `test-case.md`, `story-map-index.md`, `team-topology.md`

## Key Architectural Decisions

- **Config-driven**: Nothing is hardcoded to a specific project. All project-specific values come from `sprint-config/project.toml`.
- **Symlink-based config**: `sprint_init.py` creates symlinks from `sprint-config/` to existing project files. Teardown removes symlinks without touching originals. Exception: Giles is copied (plugin-owned), not symlinked.
- **Custom TOML parser**: `validate_config.py:22` has a minimal TOML parser (no `tomllib` dependency) supporting strings, ints, bools, arrays, sections.
- **Scripts import chain**: All skill scripts do `sys.path.insert(0, ...)` to reach `scripts/validate_config.py` four directories up.
- **GitHub as source of truth**: `sync_tracking.py` treats GitHub issue/PR state as authoritative and updates local tracking files to match.
- **Idempotent scripts**: All bootstrap and monitoring scripts skip resources that already exist.

## Common Tasks

| Task | What to do |
|------|-----------|
| Add a new skill | Create `skills/<name>/SKILL.md` with YAML frontmatter (`name`, `description`) |
| Modify config validation | Edit `scripts/validate_config.py` — `_REQUIRED_FILES` :164, `_REQUIRED_TOML_KEYS` :177 |
| Add a new label category | Edit `skills/sprint-setup/scripts/bootstrap_github.py` — add to `create_static_labels()` :171 or create new function |
| Add language support to CI | Edit `skills/sprint-setup/scripts/setup_ci.py` — add to `_SETUP_REGISTRY` :60 and `_ENV_BLOCKS` :74 |
| Add a new kanban state | Update `skills/sprint-run/references/kanban-protocol.md` + `sync_tracking.py:27` `KANBAN_STATES` |
| Change sprint tracking format | Edit `skills/sprint-run/references/tracking-formats.md` + update `sync_tracking.py` and `update_burndown.py` |
| Add a skeleton template | Create `references/skeletons/<name>.tmpl`, wire it in `sprint_init.py:ConfigGenerator` |
| Add deep documentation support | Set optional TOML keys (`paths.prd_dir`, `paths.test_plan_dir`, `paths.sagas_dir`, `paths.epics_dir`, `paths.story_map`, `paths.team_topology`). Sprint-run Context Assembly (:65 in SKILL.md) handles injection into agent prompts. |
