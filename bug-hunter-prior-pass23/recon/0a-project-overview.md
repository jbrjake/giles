# 0a — Project Overview

## What it is

Giles is a Claude Code plugin (v0.6.1, MIT license) that orchestrates agile sprints using fictional team personas. It manages the full sprint lifecycle — kickoff, story execution with TDD, code review, demo, and retrospective — with all artifacts flowing through GitHub (issues, PRs, labels, milestones). A built-in scrum master persona ("Giles") facilitates ceremonies. Stories move through a six-state kanban (TODO, DESIGN, DEV, REVIEW, INTEGRATION, DONE) with WIP limits and label sync. Implementer and reviewer subagents write code and review PRs in character. Retrospectives produce actual edits to project documentation.

## Architecture

### Layers

1. **Plugin manifest**: `.claude-plugin/plugin.json` — declares 5 skills in `skills/`.
2. **Skills** (each has a `SKILL.md` entry point read by Claude Code):
   - `sprint-setup` — one-time bootstrap: scan project, generate config, create GitHub labels/milestones/issues, set up CI.
   - `sprint-run` — full sprint execution: kickoff ceremony, story execution via subagents, demo, retro.
   - `sprint-monitor` — continuous loop: backlog sync, CI checks, PR babysitting, burndown updates.
   - `sprint-release` — gate validation, semver tagging, GitHub Release creation.
   - `sprint-teardown` — safe removal of `sprint-config/` (symlinks removed, originals untouched).
3. **Shared scripts** (`scripts/`): 14 production Python files (see below).
4. **Skill-local scripts** (`skills/*/scripts/`): 6 additional Python files.
5. **Reference docs** (`skills/*/references/`): markdown files defining protocols (kanban states, ceremonies, persona guide, tracking formats, context recovery).
6. **Skeleton templates** (`references/skeletons/`): 21 `.tmpl` files used by `sprint_init.py` to scaffold `sprint-config/`.

### Config system

All project-specific values live in `sprint-config/project.toml`, parsed by a custom TOML parser in `validate_config.py` (no `tomllib` dependency). Config directory uses symlinks to existing project files (team personas, rules, backlog). Generated files (project.toml, INDEX.md) are plugin-owned. Giles persona is copied, not symlinked.

Required TOML sections: `[project]`, `[paths]`, `[ci]`. Optional: `[conventions]`, `[release]`, deep-doc paths (PRD, test plans, sagas, epics, story map, team topology).

### State management (two paths)

- `kanban.py` — mutation path: local-first state transitions, syncs to GitHub on every write.
- `sync_tracking.py` — reconciliation path: accepts GitHub state for PR linkage, branch, completion metadata.

Both paths read/write YAML frontmatter tracking files under `sprint-config/sprints/`.

## Key design constraints

1. **stdlib-only runtime** — no pip packages required for users. Dev dependencies (pytest, hypothesis) are allowed. External CLI tools (`gh`, `jq`) are acceptable runtime dependencies.
2. **Custom TOML parser** — avoids `tomllib` (Python 3.11+) to support Python 3.10. Supports strings, ints, bools, arrays, sections. Not a full TOML implementation.
3. **sys.path.insert import chain** — skill scripts reach shared `scripts/validate_config.py` via relative path insertion four directories up. No package installation.
4. **Idempotent scripts** — all bootstrap and monitoring scripts skip resources that already exist. Designed for repeated invocation.
5. **Symlink-based config** — teardown removes symlinks without touching originals. Constrains what can be stored in `sprint-config/`.
6. **GitHub is source of truth** — local tracking files reconcile from GitHub state. Requires `gh` CLI and authentication.
7. **Cross-skill coupling** — `sync_backlog.py` imports `bootstrap_github` and `populate_issues` from `skills/sprint-setup/scripts/`. Intentional reuse, but creates a dependency from shared scripts into a specific skill.

## Technology

- **Python**: 3.10+ (stdlib only for runtime; custom TOML parser avoids 3.11 `tomllib`)
- **External CLIs**: `gh` (GitHub CLI, required), `jq` (optional)
- **Test framework**: pytest + hypothesis (property-based testing). 17 test files, ~15,500 LOC of tests.
- **Test infrastructure**: `tests/fake_github.py` (991 LOC) mocks `gh` CLI calls; `tests/mock_project.py` scaffolds temp project dirs.
- **No CI in-repo** — CI is generated per-project by `setup_ci.py` (supports Rust, Python, Node.js, Go).

## File counts and LOC

| Category | Files | LOC |
|----------|------:|----:|
| Production Python (`scripts/` + `skills/*/scripts/`) | 19 | ~8,400 |
| Test Python (`tests/`) | 23 | ~15,500 |
| Markdown (skills, references, docs) | ~90 | ~9,600 |
| Templates (`.tmpl`) | 21 | ~600 |
| **Total project files** | **~142** | **~34,100** |

### Largest production files

| File | LOC | Role |
|------|----:|------|
| `scripts/validate_config.py` | 1,190 | Config validation, TOML parser, shared helpers (gh wrapper, kanban states, TF read/write) |
| `scripts/sprint_init.py` | 996 | Project scanner + config generator |
| `skills/sprint-release/scripts/release_gate.py` | 745 | Release gates, versioning, notes |
| `scripts/kanban.py` | 612 | Kanban state machine, transitions, assign, sync |
| `skills/sprint-setup/scripts/populate_issues.py` | 553 | Milestone parsing, issue creation |
| `scripts/sprint_teardown.py` | 497 | Safe config removal |
| `skills/sprint-monitor/scripts/check_status.py` | 464 | CI/PR/milestone/drift checking |

## Risk areas for audit

1. **`validate_config.py` (1,190 LOC)** — single largest file; acts as a "god module" providing TOML parsing, config validation, GitHub CLI wrappers, kanban state constants, tracking file I/O (`read_tf`/`write_tf`), slug generation, milestone detection, and more. Every other script imports from it. High coupling, high blast radius for any bug.

2. **Custom TOML parser (`parse_simple_toml`)** — hand-rolled parser supporting a subset of TOML. Edge cases in quoting, escaping, nested arrays, multiline strings are likely under-tested compared to a standard library parser.

3. **`sys.path.insert` import chain** — all skill scripts manipulate `sys.path` to find `validate_config.py` four directories up. Fragile if directory structure changes. No `__init__.py` or package structure.

4. **Shell-out surface via `subprocess`** — 8 production files shell out via `subprocess.run` (to `gh`, `git`, build commands). Injection risk if user-controlled values (story titles, branch names, persona names) reach command construction without proper quoting.

5. **Cross-skill import coupling** — `sync_backlog.py` imports from `skills/sprint-setup/scripts/`. If those scripts change their interface, `sync_backlog` breaks silently (no type checking, no package boundary).

6. **YAML frontmatter parsing in tracking files** — `read_tf`/`write_tf` in `validate_config.py` handle YAML between `---` fences. Custom parsing logic (not a YAML library) is a rich source of edge cases around quoting, special characters, and numeric values.

7. **`sprint_init.py` (996 LOC)** — project scanner that auto-detects language, team files, backlog structure, rules files. Heuristic-heavy detection logic; many code paths for different project shapes.

8. **`release_gate.py` (745 LOC)** — conventional commit parsing, semver calculation, multi-gate validation. Complex state machine with many exit paths.

9. **`fake_github.py` (991 LOC)** — large test mock for `gh` CLI. If it drifts from real `gh` behavior, tests pass but production breaks. Has its own fidelity test suite (`test_fakegithub_fidelity.py`) but that only covers what was thought to test.

10. **Two-path state management** — `kanban.py` and `sync_tracking.py` both mutate tracking files. Concurrent or out-of-order execution could produce inconsistent state. The design doc acknowledges this split but it remains a coordination risk.

11. **File I/O atomicity** — `atomic_write_tf` in kanban.py suggests prior issues with partial writes. Worth verifying the atomicity guarantees actually hold (temp file + rename on the same filesystem).
