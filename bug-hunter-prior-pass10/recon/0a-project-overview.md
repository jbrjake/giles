# Project Overview — Giles Bug-Hunter Recon

## What Giles Is

Giles is a Claude Code plugin (v0.4.0, MIT, author: Jon Rubin / jbrjake) that runs full agile sprints with fictional team personas. It orchestrates GitHub issues, PRs, CI, kanban tracking, and sprint ceremonies (kickoff, demo, retro) through a built-in scrum master character named Giles — a librarian who ended up running standups.

Plugin manifest: `.claude-plugin/plugin.json`
Repository: `https://github.com/jbrjake/giles`

## Architecture

### Skill-Based Plugin Structure

Five skills, each with a `SKILL.md` entry point (YAML frontmatter with `name` and `description`):

| Skill | Entry Point | Purpose |
|-------|-------------|---------|
| sprint-setup | `skills/sprint-setup/SKILL.md` | One-time bootstrap: scan project, generate config, create GitHub labels/milestones/issues, set up CI |
| sprint-run | `skills/sprint-run/SKILL.md` | Run a sprint: kickoff ceremony, story execution (TDD, PRs, reviews via subagents), demo, retro |
| sprint-monitor | `skills/sprint-monitor/SKILL.md` | Continuous monitoring: CI status, open PRs, burndown, branch drift (designed for `/loop 5m`) |
| sprint-release | `skills/sprint-release/SKILL.md` | Release pipeline: gate validation, semver versioning, build artifacts, GitHub Release |
| sprint-teardown | `skills/sprint-teardown/SKILL.md` | Safe removal of sprint-config/ (symlinks removed, originals untouched) |

Lifecycle: `sprint-setup` -> `sprint-run` (repeats) -> `sprint-release` (at milestone end) -> `sprint-teardown`

### Subagent Templates

Two subagent markdown templates dispatched during sprint-run's story execution phase:

- `skills/sprint-run/agents/implementer.md` — TDD, PR creation, persona-voiced code
- `skills/sprint-run/agents/reviewer.md` — Three-pass review (correctness, conventions, testing)

### Config System

All skills read from `sprint-config/project.toml` via `validate_config.load_config()`.

**Required TOML keys:** `project.name`, `project.repo`, `project.language`, `paths.team_dir`, `paths.backlog_dir`, `paths.sprints_dir`, `ci.check_commands`, `ci.build_command`

**Optional keys:** `project.base_branch` (defaults to `main`), `conventions.branch_pattern`, `conventions.commit_style`, deep-doc paths (`paths.prd_dir`, `paths.test_plan_dir`, `paths.sagas_dir`, `paths.epics_dir`, `paths.story_map`, `paths.team_topology`)

**Config directory structure:**
```
sprint-config/
  project.toml             — main config
  definition-of-done.md    — evolving DoD
  team/INDEX.md            — persona table
  team/{name}.md           — persona files (symlinks to project docs)
  team/giles.md            — built-in scrum master (COPIED, not symlinked)
  team/insights.md         — motivation distillation (LLM-generated)
  team/history/            — sprint history (written during retro)
  backlog/INDEX.md         — backlog routing table
  backlog/milestones/      — one .md per milestone
  rules.md                 — project conventions (symlink)
  development.md           — dev process guide (symlink)
```

Key design choice: symlink-based config. `sprint_init.py` creates symlinks from `sprint-config/` to existing project files. Teardown removes symlinks without touching originals. Exception: `giles.md` is copied (plugin-owned).

### Custom TOML Parser

`validate_config.parse_simple_toml()` is a hand-rolled TOML parser (no `tomllib` dependency). Supports strings, ints, bools, arrays, and sections. This is a notable attack surface for edge cases.

## Python Scripts — Complete Inventory

### Shared Scripts (in `scripts/`)

| Script | Lines* | Purpose |
|--------|--------|---------|
| `scripts/validate_config.py` | — | **Central hub.** Config validation, custom TOML parser, shared GitHub CLI wrappers (`gh()`, `gh_json()`), helper functions. Imported by almost every other script. |
| `scripts/sprint_init.py` | — | Project auto-detection (`ProjectScanner`) and config generation (`ConfigGenerator`). Uses skeleton templates. |
| `scripts/sprint_teardown.py` | — | Safe sprint-config/ removal. Classifies entries as symlinks/generated/unknown. |
| `scripts/sync_backlog.py` | — | Backlog auto-sync with debounce/throttle. SHA-256 hashes milestone files for change detection. |
| `scripts/sprint_analytics.py` | — | Velocity, review rounds, workload metrics. |
| `scripts/team_voices.py` | — | Extract persona commentary from saga/epic files via regex. |
| `scripts/traceability.py` | — | Bidirectional story/PRD/test mapping with gap detection. |
| `scripts/test_coverage.py` | — | Compare planned test cases vs actual test files. Language-specific test function regexes. |
| `scripts/manage_epics.py` | — | Epic CRUD: add, remove, reorder, renumber stories. |
| `scripts/manage_sagas.py` | — | Saga management: allocation, index, voices. |
| `scripts/commit.py` | — | Conventional commit validation + atomicity check. |
| `scripts/validate_anchors.py` | — | Validate section-anchor references in docs. |

*Line counts: ~7,374 total across all 19 production scripts (scripts/ + skills/*/scripts/).

### Skill-Specific Scripts (in `skills/*/scripts/`)

| Script | Purpose |
|--------|---------|
| `skills/sprint-setup/scripts/bootstrap_github.py` | Create GitHub labels (persona, sprint, saga, epic, static) and milestones. Idempotent. |
| `skills/sprint-setup/scripts/populate_issues.py` | Parse milestone files, create GitHub issues with labels. Idempotent. |
| `skills/sprint-setup/scripts/setup_ci.py` | Generate `.github/workflows/ci.yml`. Language registry: Rust, Python, Node.js, Go. |
| `skills/sprint-run/scripts/sync_tracking.py` | Reconcile local tracking files with GitHub issue/PR state. GitHub is source of truth. |
| `skills/sprint-run/scripts/update_burndown.py` | Update burndown and sprint status from GitHub milestone data. |
| `skills/sprint-monitor/scripts/check_status.py` | CI check, PR monitoring, milestone progress, branch divergence, direct push detection. |
| `skills/sprint-release/scripts/release_gate.py` | Release gates (stories, CI, PRs, tests, build), semver calculation, release notes, `gh release create`. |

## Inter-File Dependency Graph

### Import Hub: `scripts/validate_config.py`

Every script except `commit.py`, `validate_anchors.py`, and `sprint_teardown.py` imports from `validate_config.py`. It is the single shared dependency for the entire codebase.

```
validate_config.py (hub — imported by 16 scripts)
├── sprint_init.py          imports: validate_project
├── sync_backlog.py          imports: load_config, ConfigError, get_milestones
├── team_voices.py           imports: load_config, ConfigError
├── traceability.py          imports: load_config, ConfigError
├── test_coverage.py         imports: load_config, ConfigError
├── manage_epics.py          imports: safe_int (as _safe_int)
├── manage_sagas.py          imports: safe_int (as _safe_int)
├── sprint_analytics.py      imports: load_config, ConfigError, extract_sp, gh_json, find_milestone, list_milestone_issues, warn_if_at_limit, get_sprints_dir, detect_sprint
├── bootstrap_github.py      imports: load_config, ConfigError, get_team_personas, get_milestones, get_epics_dir, gh
├── populate_issues.py       imports: load_config, ConfigError, get_milestones, gh, warn_if_at_limit
├── setup_ci.py              imports: load_config, ConfigError, get_ci_commands
├── sync_tracking.py         imports: load_config, ConfigError, extract_sp, extract_story_id, kanban_from_labels, find_milestone, list_milestone_issues, warn_if_at_limit, get_sprints_dir, detect_sprint, gh, gh_json, get_base_branch
├── update_burndown.py       imports: load_config, ConfigError, extract_sp, extract_story_id, kanban_from_labels, find_milestone, list_milestone_issues, warn_if_at_limit, get_sprints_dir, detect_sprint, gh_json, get_base_branch
├── check_status.py          imports: load_config, ConfigError, extract_sp, gh, gh_json, get_base_branch, get_sprints_dir, detect_sprint, warn_if_at_limit, parse_iso_date
└── release_gate.py          imports: load_config, ConfigError, get_base_branch, get_sprints_dir, gh, gh_json, warn_if_at_limit
```

### Standalone Scripts (no validate_config dependency)

- `scripts/commit.py` — uses only stdlib (argparse, re, subprocess)
- `scripts/validate_anchors.py` — uses only stdlib (re, sys, pathlib)
- `scripts/sprint_teardown.py` — uses only stdlib (json, os, subprocess, sys, pathlib)

### Cross-Skill Import: sync_backlog.py

`sync_backlog.py` is notable because it lazy-imports from a different skill:
```python
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "skills" / "sprint-setup" / "scripts"))
```
It imports `bootstrap_github` and `populate_issues` at runtime (inside `do_sync()`), creating a cross-skill dependency from `scripts/` into `skills/sprint-setup/scripts/`.

### sys.path.insert Pattern

All skill-specific scripts use `sys.path.insert(0, ...)` to reach `scripts/validate_config.py` four directories up:
```python
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent / "scripts"))
```
Shared scripts in `scripts/` use a simpler one-level path insert:
```python
sys.path.insert(0, str(Path(__file__).resolve().parent))
```

## Test Files — Complete Inventory

| Test File | What It Tests |
|-----------|---------------|
| `tests/test_pipeline_scripts.py` | Unit tests for team_voices, parse_simple_toml, setup_ci, ProjectScanner, traceability, test_coverage, manage_epics, manage_sagas, validate_project, detect_sprint, extract_story_id, kanban_from_labels |
| `tests/test_lifecycle.py` | End-to-end lifecycle: scan -> generate -> validate -> bootstrap -> populate -> sync -> burndown -> release gate. Also tests commit.py. |
| `tests/test_hexwise_setup.py` | Integration test for a specific project ("Hexwise") through scan -> generate -> validate -> bootstrap -> populate |
| `tests/test_golden_run.py` | Golden-file replay tests: runs full setup pipeline against recorded GitHub API responses |
| `tests/test_gh_interactions.py` | Tests for all scripts that interact with GitHub CLI (commit, analytics, release_gate, check_status, bootstrap, populate, sync_tracking, update_burndown, validate_config) |
| `tests/test_release_gate.py` | Focused tests for release_gate.py: semver parsing, gate functions, version calculation |
| `tests/test_sprint_analytics.py` | Tests for sprint_analytics.py: velocity, review rounds, workload |
| `tests/test_sprint_teardown.py` | Tests for sprint_teardown.py: classify entries, removal, edge cases |
| `tests/test_sync_backlog.py` | Tests for sync_backlog.py: hashing, throttle, debounce, state management |
| `tests/test_validate_anchors.py` | Tests for validate_anchors.py: namespace resolution, anchor defs/refs, check, fix |
| `tests/test_verify_fixes.py` | Regression tests verifying specific bug fixes stay fixed |

### Test Helpers

| File | Purpose |
|------|---------|
| `tests/fake_github.py` | `FakeGitHub` class + `make_patched_subprocess()` — mock GitHub CLI responses without hitting real API |
| `tests/golden_recorder.py` | Records real GitHub API call/response pairs for golden replay tests |
| `tests/golden_replay.py` | Replays recorded API interactions for deterministic testing |

### Golden Test Data

```
tests/golden/recordings/
  manifest.json
  01-setup-init.json
  02-setup-labels.json
  03-setup-milestones.json
  04-setup-issues.json
  05-setup-ci.json
```

## Reference Files

### Skill Reference Docs (12 files)

| File | Content |
|------|---------|
| `skills/sprint-run/references/kanban-protocol.md` | 6-state kanban: todo, design, dev, review, integration, done. WIP limits, transition rules. |
| `skills/sprint-run/references/persona-guide.md` | Persona assignment, voice guidelines, GitHub header format, Giles/PM rules |
| `skills/sprint-run/references/ceremony-kickoff.md` | Kickoff ceremony protocol: team read, saga context, sprint theme, confidence check, scope negotiation |
| `skills/sprint-run/references/ceremony-demo.md` | Demo ceremony: live artifacts, acceptance verification, test plan check |
| `skills/sprint-run/references/ceremony-retro.md` | Retro ceremony: Start/Stop/Continue, feedback distillation, doc changes, analytics, history writing |
| `skills/sprint-run/references/context-recovery.md` | 6-step state reconstruction after context loss |
| `skills/sprint-run/references/story-execution.md` | Story lifecycle through kanban states, branch patterns, TDD, pair review |
| `skills/sprint-run/references/tracking-formats.md` | SPRINT-STATUS.md format, story file YAML frontmatter |
| `skills/sprint-setup/references/github-conventions.md` | Label taxonomy, issue/PR/review templates |
| `skills/sprint-setup/references/prerequisites-checklist.md` | Prerequisites: gh CLI, auth, superpowers plugin, git remote, toolchain, Python version |
| `skills/sprint-setup/references/ci-workflow-template.md` | CI YAML template skeleton |
| `skills/sprint-release/references/release-checklist.md` | Per-milestone gate criteria |

### Skeleton Templates (19 files in `references/skeletons/`)

**Core (9):** project.toml, team-index.md, persona.md, giles.md, backlog-index.md, milestone.md, rules.md, development.md, definition-of-done.md

**Deep docs (10):** saga.md, epic.md, story-detail.md, prd-index.md, prd-section.md, test-plan-index.md, golden-path.md, test-case.md, story-map-index.md, team-topology.md

## External Dependencies

**Production scripts:** stdlib only. Zero pip dependencies. This is an explicit design constraint (Python 3.10+).

**Stdlib modules used across production code:** `json`, `re`, `subprocess`, `sys`, `os`, `hashlib`, `argparse`, `tempfile`, `pathlib.Path`, `dataclasses`, `datetime`, `collections.abc`, `typing`

**External runtime dependency:** `gh` CLI (GitHub CLI) — required and used extensively via `subprocess.run()` for all GitHub operations (issues, PRs, labels, milestones, releases, code reviews).

**Test-only stdlib modules:** `unittest`, `unittest.mock`, `tempfile`, `textwrap`, `shutil`

## Notable / Unusual Patterns

1. **Custom TOML parser instead of `tomllib`** — `parse_simple_toml()` in validate_config.py is a hand-rolled parser. `tomllib` is available in Python 3.11+ stdlib but was avoided, presumably for 3.10 compatibility. This is a known complexity/bug-risk area.

2. **sys.path.insert import chain** — No proper Python packaging. Every script manipulates `sys.path` to find `validate_config.py`. Skill scripts go four directories up. This is fragile but functional.

3. **Lazy cross-skill import** — `sync_backlog.py` lazy-imports `bootstrap_github` and `populate_issues` from the sprint-setup skill inside `do_sync()`, creating an unusual cross-boundary dependency.

4. **GitHub CLI as the only external interface** — All GitHub interaction goes through `subprocess.run(["gh", ...])`. The `gh()` and `gh_json()` wrappers in validate_config.py are the shared interface. `fake_github.py` in tests patches `subprocess.run` to mock this.

5. **Symlink-based config with copy exception** — Config files are symlinks to project originals, but `giles.md` is copied because it's plugin-owned. Teardown must handle this asymmetry.

6. **Duplicated `_safe_int()` functions** — Both `manage_epics.py` and `manage_sagas.py` import `safe_int` from `validate_config` and alias it as `_safe_int`. Worth checking if these are used consistently.

7. **`from __future__ import annotations`** — Used in most but not all scripts. Inconsistent application (e.g., `validate_config.py` itself does not use it).

8. **No `__init__.py` files** — The `scripts/` and `skills/*/scripts/` directories have no package markers. Import relies entirely on `sys.path` manipulation.

9. **Evals file** — `evals/evals.json` exists for skill evaluation scenarios but was not examined in detail for this recon pass.

10. **Documentation system with section anchors** — Uses `§`-prefixed anchors (e.g., `§validate_config.parse_simple_toml`) for cross-referencing between CLAUDE.md/CHEATSHEET.md and source code. `validate_anchors.py` enforces these references match real anchor comments in the source.

## File Count Summary

- **Production Python scripts:** 19 (12 shared + 7 skill-specific)
- **Test Python files:** 14 (11 test files + 3 helpers)
- **Skeleton templates:** 19
- **Reference docs:** 12
- **Subagent templates:** 2
- **SKILL.md entry points:** 5
- **Total production Python LOC:** ~7,374
