# Phase 0a: Project Overview

**Project:** giles (Claude Code plugin)
**Version:** 0.4.0
**Author:** Jon Rubin
**Date:** 2026-03-15

---

## What This Project Is

Giles is a Claude Code plugin that runs agile sprints with persona-based development. It orchestrates GitHub issues, PRs, CI, kanban tracking, and sprint ceremonies (kickoff, demo, retro) using fictional team personas that implement and review code in-character.

The plugin provides five skills that form a lifecycle:

```
sprint-setup -> sprint-run (repeats) -> sprint-release -> sprint-teardown
                    ^
                    |
              sprint-monitor (runs alongside via /loop)
```

All scripts are stdlib-only Python 3.10+ with no pip dependencies. A custom TOML parser replaces `tomllib`. Configuration lives in `sprint-config/project.toml`, and the system uses symlinks to point from sprint-config/ into existing project files.

---

## Production Scripts

### Shared Scripts (`scripts/`)

| Script | LOC | Purpose |
|--------|-----|---------|
| `validate_config.py` | ~798 | **Root of the import chain.** Custom TOML parser (`parse_simple_toml`), config validation (`validate_project`), config loading (`load_config`), GitHub CLI wrappers (`gh`, `gh_json`), and ~20 shared helpers (story ID extraction, kanban state parsing, milestone queries, sprint detection). Every other script that touches config imports from here. |
| `sprint_init.py` | ~966 | Auto-detect project structure and generate `sprint-config/`. Two main classes: `ProjectScanner` (detects language, repo, CI commands, personas, backlog, deep docs) and `ConfigGenerator` (creates symlinks, generates files from skeleton templates). |
| `sprint_teardown.py` | ~474 | Safe removal of `sprint-config/`. Classifies entries as symlinks, generated files, or unknown; removes symlinks and generated files; leaves originals intact. **Standalone** -- does not import validate_config. |
| `sync_backlog.py` | ~247 | Backlog auto-sync with debounce/throttle. Hashes milestone files to detect changes, then lazily imports `bootstrap_github` and `populate_issues` to re-sync labels and issues. |
| `sprint_analytics.py` | ~276 | Sprint metrics: velocity (SP completed/total), review rounds (PR review iteration count), workload (per-persona SP distribution). Outputs formatted text report. |
| `team_voices.py` | ~107 | Extract persona commentary blockquotes from saga/epic files. Pattern-matches `> **Name:** quote` blocks. |
| `traceability.py` | ~223 | Bidirectional story-to-PRD-to-test mapping with gap detection. Parses stories, test cases, and requirements, then cross-references to find unlinked items. |
| `test_coverage.py` | ~198 | Compare planned test cases (from test plan docs) vs actual test files found in the project. Language-aware test function detection (Rust, Python, Node, Go). |
| `manage_epics.py` | ~405 | Epic CRUD: parse epic markdown, add/remove/reorder/renumber stories within an epic. **Standalone** -- no validate_config imports. |
| `manage_sagas.py` | ~298 | Saga management: parse saga markdown, update sprint allocation tables, update epic index, update team voice sections. Lazy-imports `parse_epic` from `manage_epics`. |
| `commit.py` | ~153 | Conventional commit message validation and atomicity enforcement. Checks prefix format (feat/fix/chore/etc), scope, and body structure. **Standalone.** |
| `validate_anchors.py` | ~330 | Validate and auto-fix `§`-prefixed anchor references in CLAUDE.md and CHEATSHEET.md. Has a `NAMESPACE_MAP` that maps short names to file paths, plus check/fix modes. **Standalone.** |

### Skill-Specific Scripts

| Script | LOC | Purpose |
|--------|-----|---------|
| `skills/sprint-setup/scripts/bootstrap_github.py` | ~294 | Create GitHub labels (persona, sprint, saga, static, epic) and milestones via `gh` CLI. Reads persona list from team index, sprint numbers from milestone files, saga IDs from backlog index. |
| `skills/sprint-setup/scripts/populate_issues.py` | ~445 | Parse milestone markdown docs for story tables, enrich stories from epic files, create GitHub issues with labels and milestone assignment. |
| `skills/sprint-setup/scripts/setup_ci.py` | ~385 | Generate `.github/workflows/ci.yml` from config. Language-specific setup registry (Rust, Python, Node.js, Go) with environment blocks, test matrix, docs-lint job. |
| `skills/sprint-run/scripts/sync_tracking.py` | ~358 | Reconcile local story tracking YAML files with GitHub issue/PR state. GitHub is source of truth; local files get updated to match. |
| `skills/sprint-run/scripts/update_burndown.py` | ~230 | Update burndown chart data and SPRINT-STATUS.md from GitHub milestone completion state. |
| `skills/sprint-monitor/scripts/check_status.py` | ~431 | CI status check, open PR review, milestone progress, branch divergence detection, direct-push detection. Also imports `sync_backlog.main` for pre-check sync. |
| `skills/sprint-release/scripts/release_gate.py` | ~659 | Release gate validation (stories done, CI green, PRs merged, tests pass, build succeeds), semver version calculation from conventional commits, tag creation, GitHub Release creation, rollback support. |

**Total production scripts: 19** (~7,237 LOC)

---

## Test Files

### Test Infrastructure

| File | LOC | Purpose |
|------|-----|---------|
| `tests/fake_github.py` | ~716 | `FakeGitHub` class -- dispatch-based simulation of the `gh` CLI. Maintains in-memory state for issues, labels, milestones, PRs, releases. Used by most test files to avoid real GitHub calls. |

### Test Suites

| File | LOC | Targets |
|------|-----|---------|
| `tests/test_lifecycle.py` | ~594 | End-to-end lifecycle: sprint_init -> bootstrap_github -> populate_issues -> monitoring pipeline. Tests the full setup flow against a hexwise fixture. |
| `tests/test_gh_interactions.py` | ~large | commit.py validation, release_gate functions, check_status, bootstrap_github, populate_issues, sync_tracking, update_burndown. Broad coverage of all GitHub-interacting scripts. |
| `tests/test_release_gate.py` | ~1044 | calculate_version, validate_gates, gate_tests, gate_build, do_release, rollback. Deep coverage of the release workflow. |
| `tests/test_sprint_teardown.py` | ~526 | classify_entries, remove_symlinks, remove_generated, remove_empty_dirs, verify_teardown. Unit tests for safe removal logic. |
| `tests/test_hexwise_setup.py` | ~447 | ProjectScanner, ConfigGenerator, and pipeline integration against the rich hexwise fixture project. |
| `tests/test_verify_fixes.py` | ~395 | Config generation correctness, CI generation, agent frontmatter validation, evals genericness checks. Regression tests for previously-fixed bugs. |
| `tests/test_validate_anchors.py` | ~286 | Namespace resolution, anchor definition scanning, anchor reference scanning, check mode, fix mode. |
| `tests/test_sprint_analytics.py` | ~250 | Velocity, review rounds, workload computation with FakeGitHub mocking. |
| `tests/test_sync_backlog.py` | ~297 | Debounce/throttle algorithm, hash detection, sync triggering. |
| `tests/test_pipeline_scripts.py` | ~large | team_voices, traceability, test_coverage, manage_epics, manage_sagas against hexwise fixture data. |
| `tests/test_golden_run.py` | ~209 | Golden snapshot regression tests -- runs sprint_init against hexwise fixture and compares output to stored golden files. |

### Test Fixture

| Path | Purpose |
|------|---------|
| `tests/fixtures/hexwise/` | Complete mock Rust project with 3 personas, 2 milestones, 3 epics, 2 sagas, PRDs, test plans, story map, team topology. Used as the standard fixture for integration tests. |

**Total test files: 12** (11 suites + 1 infrastructure module)

---

## Skill Entry Points

Each skill has a `SKILL.md` file with YAML frontmatter (name, description) that serves as the entry point.

| Skill | Entry Point | Purpose |
|-------|-------------|---------|
| sprint-setup | `skills/sprint-setup/SKILL.md` | One-time project bootstrap: config init, GitHub labels/milestones, issue population, CI workflow. |
| sprint-run | `skills/sprint-run/SKILL.md` | Sprint execution lifecycle: kickoff ceremony, story execution (design/dev/review/integration), demo ceremony, retro ceremony. |
| sprint-monitor | `skills/sprint-monitor/SKILL.md` | Continuous monitoring via `/loop`: CI status, PR review, burndown, drift detection, backlog sync. |
| sprint-release | `skills/sprint-release/SKILL.md` | Milestone release: gate validation, semver tagging, GitHub Release creation, rollback. |
| sprint-teardown | `skills/sprint-teardown/SKILL.md` | Safe removal of sprint-config/ directory. |

### Agent Templates

| File | Purpose |
|------|---------|
| `skills/sprint-run/agents/implementer.md` | Subagent prompt for story implementation: TDD workflow, PR creation, motivation/strategic context injection. |
| `skills/sprint-run/agents/reviewer.md` | Subagent prompt for code review: three-pass review (correctness/conventions/testing), confidence reading, test coverage verification. |

---

## Reference and Config Files

### Skill Reference Documents

| File | Purpose |
|------|---------|
| `skills/sprint-run/references/kanban-protocol.md` | Kanban state machine (6 states: todo, design, dev, review, integration, done), transition rules, WIP limits. |
| `skills/sprint-run/references/persona-guide.md` | Persona assignment rules, voice guidelines, GitHub header format, Giles scrum master rules, PM role. |
| `skills/sprint-run/references/ceremony-kickoff.md` | Kickoff ceremony script: Giles/PM split, team read, saga context, sprint theme, analytics, confidence check, scope negotiation. |
| `skills/sprint-run/references/ceremony-demo.md` | Demo ceremony script: ensemble framing, artifact requirements, test plan verification, Q&A in persona, acceptance. |
| `skills/sprint-run/references/ceremony-retro.md` | Retro ceremony script: psychological safety, Start/Stop/Continue, feedback distillation, sprint analytics, sprint history, DoD review. |
| `skills/sprint-run/references/context-recovery.md` | State reconstruction after context loss: read status/burndown, sync tracking, query GitHub, resume phase. |
| `skills/sprint-run/references/story-execution.md` | Story lifecycle through kanban states, branch patterns, design/dev/review/integration transitions. |
| `skills/sprint-run/references/tracking-formats.md` | SPRINT-STATUS.md format, story tracking file YAML frontmatter, burndown format. |
| `skills/sprint-setup/references/github-conventions.md` | Label taxonomy, issue template, PR template, review template. |
| `skills/sprint-setup/references/ci-workflow-template.md` | CI YAML template structure. |
| `skills/sprint-setup/references/sprint-config-structure.md` | Expected sprint-config/ directory layout. |
| `skills/sprint-release/references/release-checklist.md` | Per-milestone gate criteria template. |

### Skeleton Templates (`references/skeletons/`)

19 `.tmpl` files used by `sprint_init.py` to scaffold `sprint-config/` when project files are missing:

**Core (9):** `project.toml`, `team-index.md`, `persona.md`, `giles.md`, `backlog-index.md`, `milestone.md`, `rules.md`, `development.md`, `definition-of-done.md`

**Deep docs (10):** `saga.md`, `epic.md`, `story-detail.md`, `prd-index.md`, `prd-section.md`, `test-plan-index.md`, `golden-path.md`, `test-case.md`, `story-map-index.md`, `team-topology.md`

### Project-Level Files

| File | Purpose |
|------|---------|
| `CLAUDE.md` | Main agent instructions: script tables, skill entry points, config system, architecture decisions, common tasks. |
| `CHEATSHEET.md` | Detailed line-number index for all functions, sections, and reference files. |
| `.claude-plugin/plugin.json` | Plugin manifest: name, version, author, skill list. |
| `evals/evals.json` | Skill evaluation scenarios. |

---

## Key Architectural Patterns

### 1. Config-Driven Design

Nothing is hardcoded to a specific project. All project-specific values come from `sprint-config/project.toml`. Required TOML keys: `project.name`, `project.repo`, `project.language`, `paths.team_dir`, `paths.backlog_dir`, `paths.sprints_dir`, `ci.check_commands`, `ci.build_command`.

### 2. Symlink-Based Configuration

`sprint_init.py` creates symlinks from `sprint-config/` to existing project files. Teardown removes symlinks without touching originals. Exception: `giles.md` (the built-in scrum master persona) is copied, not symlinked, because it is plugin-owned.

### 3. Custom TOML Parser

`validate_config.parse_simple_toml()` is a hand-rolled TOML parser supporting strings, ints, bools, arrays, and sections. This avoids any dependency on `tomllib` (Python 3.11+) or external packages.

### 4. GitHub as Source of Truth

`sync_tracking.py` treats GitHub issue/PR state as authoritative and updates local tracking files to match. Labels drive kanban state (`kanban_from_labels()`). Milestones drive sprint assignment.

### 5. Idempotent Operations

All bootstrap and monitoring scripts skip resources that already exist. `create_label(..., --force)` updates rather than fails. Issue creation checks for duplicates. CI generation refuses to overwrite.

### 6. FakeGitHub Test Infrastructure

`tests/fake_github.py` provides a `FakeGitHub` class that simulates the `gh` CLI by dispatching commands to in-memory state. Tests monkeypatch `subprocess.run` to intercept `gh` calls and route them through FakeGitHub. This lets the full test suite run without network access or GitHub authentication.

### 7. Import Chain via sys.path.insert

All skill scripts use `sys.path.insert(0, ...)` to reach `scripts/validate_config.py`, which lives four directories up from skill scripts:

```
skills/<skill>/scripts/<script>.py
    -> sys.path.insert(0, Path(__file__).resolve().parent.parent.parent.parent / "scripts")
    -> from validate_config import load_config, gh, ...
```

---

## Script Dependency Chain

```
                    validate_config.py
                    (ROOT — everyone imports from here)
                           |
          +----------------+------------------+------------------+
          |                |                  |                  |
    sprint_init.py   sync_backlog.py   sprint_analytics.py   team_voices.py
    (validate_project)  (load_config,     (load_config,        (load_config)
                         get_milestones)   extract_sp, gh,
                         |                 gh_json, etc.)
                         |
                +--------+--------+
                |                 |
         bootstrap_github.py  populate_issues.py
         (load_config,        (load_config,
          get_team_personas,   get_milestones,
          get_milestones,      gh,
          get_epics_dir, gh)   warn_if_at_limit)

    traceability.py        test_coverage.py       setup_ci.py
    (load_config)          (load_config)          (load_config,
                                                   get_ci_commands)

    sync_tracking.py       update_burndown.py     check_status.py
    (load_config, gh,      (load_config,          (load_config, gh,
     extract_story_id,      extract_sp,            gh_json,
     get_sprints_dir,       get_sprints_dir,       get_base_branch,
     kanban_from_labels,    find_milestone, etc.)   detect_sprint;
     find_milestone,                               also imports
     list_milestone_issues,                        sync_backlog.main)
     KANBAN_STATES)

    release_gate.py        manage_sagas.py
    (load_config,          (lazy imports
     get_base_branch,       manage_epics.
     get_sprints_dir,       parse_epic)
     gh, gh_json,
     warn_if_at_limit)

    STANDALONE (no validate_config imports):
      sprint_teardown.py
      commit.py
      manage_epics.py
      validate_anchors.py
```

### Cross-Skill Import

`check_status.py` (sprint-monitor) imports `sync_backlog.main` (shared scripts), which in turn lazy-imports `bootstrap_github` and `populate_issues` (sprint-setup). This is the only cross-skill dependency.

### Lateral Import

`manage_sagas.py` lazy-imports `parse_epic` from `manage_epics.py`. Both live in `scripts/`.

---

## Eval System

`evals/evals.json` contains skill evaluation scenarios. Tests in `test_verify_fixes.py` validate that evals reference no hardcoded project names (genericness check).

---

## Summary Statistics

| Category | Count |
|----------|-------|
| Production scripts | 19 (~7,200 LOC) |
| Test files | 12 (11 suites + 1 infra) |
| Skills | 5 |
| Agent templates | 2 |
| Reference documents | 12 |
| Skeleton templates | 19 |
| Test fixture projects | 1 (hexwise) |
