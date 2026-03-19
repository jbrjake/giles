# Phase 0a: Project Overview — Bug Hunter Recon

## Project Identity

- **Name:** giles
- **Version:** 0.6.1 (from `.claude-plugin/plugin.json`)
- **Author:** Jon Rubin
- **License:** MIT
- **Repo:** https://github.com/jbrjake/giles
- **Description:** Claude Code plugin for agile sprints with persona-based development. Orchestrates GitHub issues, PRs, CI, kanban tracking, and sprint ceremonies (kickoff, demo, retro) using fictional team personas.

## Project Structure Summary

```
.claude-plugin/plugin.json      Plugin manifest
CLAUDE.md                       Main agent instructions (144 lines)
CHEATSHEET.md                   Detailed line-number/anchor index (536 lines)
scripts/                        13 shared Python scripts (stdlib-only)
skills/
  sprint-setup/                 SKILL.md + scripts/ + references/
  sprint-run/                   SKILL.md + scripts/ + references/ + agents/
  sprint-monitor/               SKILL.md + scripts/
  sprint-release/               SKILL.md + scripts/ + references/
  sprint-teardown/              SKILL.md (no scripts, uses shared sprint_teardown.py)
references/skeletons/           19 .tmpl files for config scaffolding
evals/evals.json                Skill evaluation scenarios
tests/                          22 test files (unit, integration, property, golden)
```

## Script Inventory (by size)

| Script | Lines | Purpose |
|--------|-------|---------|
| `scripts/validate_config.py` | 1215 | Config validation, TOML parser, shared helpers (hub of everything) |
| `scripts/sprint_init.py` | 996 | Auto-detect project -> generate sprint-config/ |
| `skills/sprint-release/scripts/release_gate.py` | 759 | Release gates, versioning, notes, publishing, rollback |
| `scripts/kanban.py` | 631 | Kanban state machine (transitions, assign, sync, status) |
| `skills/sprint-setup/scripts/populate_issues.py` | 558 | Parse milestones -> GitHub issues |
| `scripts/sprint_teardown.py` | 500 | Safe removal of sprint-config/ |
| `skills/sprint-monitor/scripts/check_status.py` | 474 | CI + PR + milestone + drift check |
| `scripts/manage_epics.py` | 411 | Epic CRUD: add, remove, reorder stories |
| `skills/sprint-setup/scripts/setup_ci.py` | 408 | Generate CI workflow YAML |
| `skills/sprint-setup/scripts/bootstrap_github.py` | 341 | Create GitHub labels/milestones |
| `scripts/validate_anchors.py` | 337 | Validate doc anchor references |
| `scripts/manage_sagas.py` | 295 | Saga management |
| `skills/sprint-run/scripts/sync_tracking.py` | 289 | Reconcile local tracking with GitHub |
| `scripts/sprint_analytics.py` | 282 | Sprint velocity/review/workload metrics |
| `scripts/sync_backlog.py` | 252 | Backlog auto-sync with debounce/throttle |
| `skills/sprint-run/scripts/update_burndown.py` | 223 | Update burndown from GitHub milestones |
| `scripts/traceability.py` | 222 | Bidirectional story/PRD/test mapping |
| `scripts/test_coverage.py` | 210 | Compare planned tests vs actual test files |
| `scripts/commit.py` | 156 | Enforce conventional commits |
| `scripts/team_voices.py` | 108 | Extract persona commentary from saga/epic files |
| **Total** | **8667** | |

## Script Dependency Graph

```
validate_config.py (1215 lines) — the hub; every other script imports from it
    |
    +-- kanban.py imports: load_config, ConfigError, TF, read_tf, write_tf,
    |       get_sprints_dir, detect_sprint, extract_story_id, kanban_from_labels,
    |       find_milestone, list_milestone_issues, gh, gh_json, short_title,
    |       slug_from_title, KANBAN_STATES, _yaml_safe
    |
    +-- sprint_init.py imports: validate_project
    |
    +-- sync_backlog.py imports: load_config, get_milestones, ConfigError
    |       also imports: bootstrap_github (from skills/sprint-setup/scripts/)
    |       also imports: populate_issues (from skills/sprint-setup/scripts/)
    |
    +-- sprint_analytics.py imports: load_config, ConfigError, extract_sp,
    |       gh_json, detect_sprint, find_milestone, get_sprints_dir, warn_if_at_limit
    |
    +-- traceability.py imports: load_config, ConfigError, TABLE_ROW
    |
    +-- test_coverage.py imports: load_config, ConfigError
    |
    +-- team_voices.py imports: load_config, ConfigError
    |
    +-- manage_epics.py imports: safe_int (as _safe_int), TABLE_ROW, parse_header_table
    |
    +-- manage_sagas.py imports: safe_int (as _safe_int), TABLE_ROW, parse_header_table
    |       also imports: manage_epics.parse_epic (at call time, inside update_epic_index)
    |
    +-- commit.py imports: (nothing from validate_config — standalone)
    |
    +-- sprint_teardown.py imports: (nothing from validate_config — standalone)
    |
    +-- validate_anchors.py imports: (nothing from validate_config — standalone)
    |
    +-- bootstrap_github.py imports: load_config, ConfigError, get_team_personas,
    |       get_milestones, get_epics_dir, get_sagas_dir, gh
    |
    +-- populate_issues.py imports: load_config, ConfigError, get_milestones,
    |       gh, gh_json, extract_story_id, warn_if_at_limit
    |
    +-- setup_ci.py imports: load_config, ConfigError, get_ci_commands
    |
    +-- sync_tracking.py imports: load_config, ConfigError, gh_json,
    |       extract_story_id, get_sprints_dir, kanban_from_labels, find_milestone,
    |       frontmatter_value, list_milestone_issues, parse_iso_date, short_title,
    |       KANBAN_STATES, warn_if_at_limit, TF, read_tf, write_tf, _yaml_safe,
    |       slug_from_title
    |
    +-- update_burndown.py imports: load_config, ConfigError, extract_sp,
    |       get_sprints_dir, find_milestone, extract_story_id, kanban_from_labels,
    |       list_milestone_issues, parse_iso_date, short_title, frontmatter_value
    |
    +-- check_status.py imports: load_config, ConfigError, extract_sp, gh,
    |       gh_json, get_base_branch, get_sprints_dir, detect_sprint,
    |       warn_if_at_limit, find_milestone
    |       also imports: sync_backlog.main (optional, for step 0)
    |
    +-- release_gate.py imports: load_config, ConfigError, get_base_branch,
            get_sprints_dir, gh, gh_json, warn_if_at_limit
```

### Cross-Skill Dependencies

1. **sync_backlog.py** (in `scripts/`) imports from `skills/sprint-setup/scripts/` (bootstrap_github, populate_issues). Documented as intentional coupling.
2. **check_status.py** (in `skills/sprint-monitor/scripts/`) imports `sync_backlog.main` from `scripts/`. Done with try/except for graceful failure.
3. **manage_sagas.py** imports `manage_epics.parse_epic` lazily inside `update_epic_index()`.

### sys.path.insert Pattern

- Skill scripts use 4x `.parent` traversal: `Path(__file__).resolve().parent.parent.parent.parent / "scripts"`
- Top-level scripts use 1x `.parent` traversal: `Path(__file__).resolve().parent`
- `sync_backlog.py` adds two paths (own dir + sprint-setup scripts)
- `release_gate.py` uses a named constant `_SCRIPTS_DIR` instead of inline traversal

## Skill SKILL.md Summary

| Skill | Lines | Key Pattern |
|-------|-------|-------------|
| sprint-setup | 101 | 3 phases: config init, prerequisites, GitHub bootstrap. Runs 3 scripts. |
| sprint-run | 160 | Phase detection -> kickoff -> story execution -> demo -> retro. References 10 doc files. |
| sprint-monitor | 326 | 7 steps (0-4 + 1.5 + 2.5). Designed for /loop 5m. Rate limiting. |
| sprint-release | 289 | 5 steps: gate validation -> tag -> build -> GitHub Release -> post-release + rollback. |
| sprint-teardown | 212 | Safety-first: dry-run, classify entries, prompt for generated files, verify targets. |

## Key Reference Files

| File | Lines | Purpose |
|------|-------|---------|
| kanban-protocol.md | 113 | 6-state machine, transition rules, WIP limits, preconditions |
| persona-guide.md | 77 | Assignment rules, voice guidelines, Giles/PM roles |
| story-execution.md | 175 | Story lifecycle: TODO->DESIGN->DEV->REVIEW->INTEGRATION->DONE |
| tracking-formats.md | 64 | SPRINT-STATUS.md + story file YAML frontmatter format |
| ceremony-kickoff.md | (full) | Giles/PM ceremony script with team read, saga context |
| ceremony-demo.md | (full) | Demo facilitation, acceptance verification |
| ceremony-retro.md | (full) | Retro facilitation, Start/Stop/Continue, analytics |

## Skeleton Templates

19 templates in `references/skeletons/`. CLAUDE.md claims 9 core + 10 deep-doc. Actual count matches: 19 .tmpl files found. The `project.toml.tmpl` is referenced but `sprint_init.py` generates TOML programmatically rather than using the template.

## TODOs / FIXMEs Found

### In Python source code (excluding test assertions about TODO content):

1. **`setup_ci.py:246`** — Unsupported language fallback: `"# TODO: Add setup steps for {language}"`. This is generated YAML content, not a code TODO.

2. **`sprint_init.py:585`** — Skeleton stub fallback: `f"<!-- TODO: populate {dest_rel} -->\n"`. Written to generated files when no skeleton template exists. Intentional placeholder.

3. **`sprint_init.py:629`** — `'repo = "TODO-owner/repo"'` written to project.toml when repo detection fails.

4. **`sprint_init.py:671`** — `'build_command = "TODO-build-command"'` written to project.toml when build command detection fails.

**No genuine code-level TODOs or FIXMEs.** All instances are user-facing placeholders in generated content.

### In markdown files:

No actionable TODOs found. References to "TODO" in CHEATSHEET.md are about transitions (TODO -> DESIGN) or skeleton descriptions ("not TODO-filled").

## Dead Code / Unused Imports Analysis

### Potentially Unused Imports

1. **`populate_issues.py` line 9: `import subprocess`** — Only used in `check_prerequisites()` for `subprocess.run(["gh", "auth", "status"])`. This could use the shared `gh()` wrapper from validate_config, but check_prerequisites is a simpler pattern (checks exit code, no output parsing). Not dead, but redundant with shared helper.

2. **`sprint_init.py` line 21: `from typing import Any`** — Used in `Detection` dataclass and `detect_project_name` parsers dict. Not dead.

3. **`kanban.py` line 149: `import dataclasses`** — Imported inside `atomic_write_tf()`. Used for `dataclasses.replace()`. Not dead, but unusual placement (inside function body).

### No Dead Code Found

All functions appear to be called from either:
- Their script's `main()` entry point
- Other scripts that import them
- Test files that exercise them

### Private Symbol Exports

Two "private" symbols are imported by external scripts:
- `validate_config._yaml_safe` — imported by `kanban.py` and `sync_tracking.py`
- These are documented in CHEATSHEET.md, suggesting they are intentionally semi-public despite the underscore prefix.

## Doc Coverage Gaps

### Well-Documented

- CLAUDE.md and CHEATSHEET.md provide comprehensive function indices
- Every script has a docstring and anchor comments
- Every SKILL.md has a quick-reference table
- All reference files have section anchors

### Gaps Found

1. **No README for tests/**: 22 test files exist but there's no guidance on how to run them, what they cover, or the test architecture (fake_github.py, golden_replay.py, gh_test_helpers.py, conftest.py).

2. **conftest.py path management**: `tests/conftest.py` handles sys.path insertion centrally, but several test files ALSO do their own sys.path.insert calls. This duplication could cause subtle import order issues.

3. **`project.toml.tmpl`** exists as a skeleton but `sprint_init.py`'s `ConfigGenerator.generate_project_toml()` builds TOML programmatically without reading it. The template file appears to be documentation-only or unused.

4. **CLAUDE.md line 118** says "19 templates" for skeletons. Actual count is 19. Matches.

5. **Evals**: `evals/evals.json` exists but no documentation describes the eval framework or how to run evals.

## Initial Red Flags

### Architecture

1. **validate_config.py is 1215 lines** — This is the hub that every script imports from. It contains the TOML parser, config validation, GitHub CLI wrappers, tracking file I/O (TF dataclass, read_tf, write_tf), milestone lookup, story ID extraction, kanban state helpers, and more. A failure or regression here cascades everywhere. The file does too many things.

2. **sys.path.insert proliferation** — Every script that needs shared code does `sys.path.insert(0, ...)` with path traversal. This is fragile (depends on exact directory depth) and makes imports invisible to static analysis tools. The 4-level parent traversal pattern in skill scripts (`parent.parent.parent.parent`) is particularly brittle.

3. **Two parallel sync paths** — `kanban.py` (mutation path, validates transitions) and `sync_tracking.py` (reconciliation path, accepts any valid state). Both write tracking files. The CLAUDE.md documents this as intentional, and `sync_tracking.py` itself notes it does NOT acquire kanban locks. This creates a documented TOCTOU window if both run concurrently.

4. **`shell=True` in release_gate.py** — `gate_tests()` and `gate_build()` execute user-configured commands via `subprocess.run(cmd, shell=True)`. The trust model is documented in the docstring, but this is still a significant attack surface for malicious project.toml content.

### Data Integrity

5. **No atomic writes in sync_tracking.py** — `sync_tracking.py` uses `write_tf()` directly (not `atomic_write_tf()`), while `kanban.py` uses `atomic_write_tf()` for all mutations. This means sync_tracking writes are not crash-safe.

6. **Pagination limits** — Multiple scripts use `--limit 500` or `--limit 1000` for GitHub API queries. `warn_if_at_limit()` prints a warning but code continues. For repos with >500 issues, syncs could miss stories silently.

### Code Quality

7. **`_yaml_safe` exported with underscore prefix** — Both `kanban.py` and `sync_tracking.py` import `_yaml_safe` from validate_config. The underscore convention suggests it's private, but it's used as a public API. Should be renamed without the underscore.

8. **`check_status.py` imports `sync_backlog.main`** — This creates a circular-ish dependency: check_status (sprint-monitor skill) imports sync_backlog (shared script), which imports bootstrap_github and populate_issues (sprint-setup skill). Monitor skill effectively depends on setup skill.

9. **Custom TOML parser** — `parse_simple_toml()` in validate_config.py is a hand-rolled parser. The CLAUDE.md documents it doesn't support floats (returned as raw strings). Custom parsers are a common source of edge-case bugs, especially for escape processing (`\uXXXX`).

10. **Lock file cleanup** — `kanban.py` creates `.lock` sentinel files but never cleans them up. The `sprint_teardown.py` script does not specifically handle `.lock` files. These accumulate as orphaned files in the sprints directory.

### Testing

11. **Test file sprawl** — 22 test files in `tests/` with names like `test_verify_fixes.py`, `test_bugfix_regression.py`, `test_lifecycle.py`, `test_hexwise_setup.py`. Some appear to be regression tests from specific bug hunts. No clear organization into unit vs integration vs property tests.

12. **Test path setup duplication** — Despite `conftest.py` centralizing path management, multiple test files redundantly insert their own sys.path entries. This suggests conftest.py was added later and not all tests were updated.

### Process

13. **No `__init__.py` files anywhere** — The project relies entirely on sys.path.insert for imports rather than proper Python packages. This prevents standard tooling (mypy, pylint, pyright) from understanding the import graph.

14. **No type checking configured** — No `mypy.ini`, `pyproject.toml` [tool.mypy], or `pyrightconfig.json`. Type hints are used throughout the code but never validated.
