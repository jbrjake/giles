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
| `scripts/validate_config.py` | Config validation + TOML parser | `validate_project()` :191, `load_config()` :368, `parse_simple_toml()` :22, `get_team_personas()` :398, `get_milestones()` :426 |
| `scripts/sprint_init.py` | Auto-detect project → generate sprint-config/ | `ProjectScanner.scan()` :349, `ConfigGenerator.generate()` :499 |
| `scripts/sprint_teardown.py` | Safe removal of sprint-config/ | `classify_entries()` :19, `main()` :347 |
| `skills/sprint-setup/scripts/bootstrap_github.py` | Create labels/milestones on GitHub | `create_persona_labels()` :78, `_collect_sprint_numbers()` :91, `create_static_labels()` :171, `create_milestones_on_github()` :200, `main()` :242 |
| `skills/sprint-setup/scripts/populate_issues.py` | Parse milestones → GitHub issues | `parse_milestone_stories()` :84, `enrich_from_epics()` :151, `_build_milestone_title_map()` :238, `create_issue()` :298 |
| `skills/sprint-setup/scripts/setup_ci.py` | Generate .github/workflows/ci.yml | `generate_ci_yaml()` :202, `_SETUP_REGISTRY` :60 (Rust/Python/Node/Go) |
| `skills/sprint-run/scripts/sync_tracking.py` | Reconcile local tracking ↔ GitHub | `sync_one()` :201, `create_from_issue()` :248 |
| `skills/sprint-run/scripts/update_burndown.py` | Update burndown from GitHub milestones | `write_burndown()` :100, `update_sprint_status()` :139 |
| `skills/sprint-monitor/scripts/check_status.py` | CI + PR + milestone status check | `check_ci()` :56, `check_prs()` :112, `check_milestone()` :188 |

### Skill Entry Points

| Skill | SKILL.md | Key sections |
|-------|----------|-------------|
| sprint-setup | `skills/sprint-setup/SKILL.md` | Phase 0: Config init :22, Step 1: Prerequisites :32, Step 2: GitHub bootstrap :46 |
| sprint-run | `skills/sprint-run/SKILL.md` | Phase detection :28, Phase 1: Kickoff :43, Phase 2: Story execution :49, Phase 3: Demo :64, Phase 4: Retro :70 |
| sprint-monitor | `skills/sprint-monitor/SKILL.md` | Prerequisites :27, CI check :45, PR check :79, Burndown :128, Rate limiting :171 |
| sprint-release | `skills/sprint-release/SKILL.md` | Gate validation :49, Tag+release :81, Build artifacts :102, GitHub Release :124, Rollback :243 |
| sprint-teardown | `skills/sprint-teardown/SKILL.md` | Safety principles :14, Dry run :63, Execute :116 |

### Reference Files

| File | What to find there |
|------|-------------------|
| `skills/sprint-run/references/kanban-protocol.md` | State machine (6 states), transition rules, WIP limits |
| `skills/sprint-run/references/persona-guide.md` | Persona assignment rules, voice guidelines, GitHub header format |
| `skills/sprint-run/references/ceremony-kickoff.md` | Kickoff agenda, output template, exit criteria |
| `skills/sprint-run/references/ceremony-demo.md` | Demo format, artifact requirements, acceptance verification |
| `skills/sprint-run/references/ceremony-retro.md` | Start/Stop/Continue format, feedback distillation, doc change rules |
| `skills/sprint-run/agents/implementer.md` | Subagent template for story implementation (TDD, PR creation) |
| `skills/sprint-run/agents/reviewer.md` | Subagent template for PR review (checklist, in-persona voice) |
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
├── backlog/INDEX.md       — backlog routing table
├── backlog/milestones/    — one .md per milestone with story tables
├── rules.md               — project conventions (symlink)
└── development.md         — dev process guide (symlink)
```

Required TOML keys: `project.name`, `project.repo`, `project.language`, `paths.team_dir`, `paths.backlog_dir`, `paths.sprints_dir`, `ci.check_commands`, `ci.build_command` (see `validate_config.py:177`).

Template: `references/skeletons/project.toml.tmpl`

### Skeleton Templates

`references/skeletons/*.tmpl` — used by `sprint_init.py` when project files are missing. Available: `project.toml`, `team-index.md`, `persona.md`, `backlog-index.md`, `milestone.md`, `rules.md`, `development.md`.

## Key Architectural Decisions

- **Config-driven**: Nothing is hardcoded to a specific project. All project-specific values come from `sprint-config/project.toml`.
- **Symlink-based config**: `sprint_init.py` creates symlinks from `sprint-config/` to existing project files. Teardown removes symlinks without touching originals.
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
