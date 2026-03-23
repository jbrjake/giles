# Architecture Baseline

**Project:** giles
**Established:** 2026-03-23
**Last Updated:** 2026-03-23

## Documented Intent

Source: CLAUDE.md, README.md, plugin.json

### Layering Rules

- Skills (`skills/*/SKILL.md`) are the entry points; scripts are the execution layer
- All scripts import from `validate_config.py` as the shared foundation (one-way dependency)
- Skill scripts use `sys.path.insert` to reach `scripts/` four directories up
- Top-level scripts use single-level parent path for imports
- Hooks (`hooks/`) are an independent subsystem; they import only from `_common.py`, not from `scripts/`
- `sync_backlog.py` is the only cross-skill import: it imports from `skills/sprint-setup/scripts/`

### Boundaries

- `validate_config.py` owns config parsing, TOML parser, and all shared helpers
- `kanban.py` owns state mutations (transitions, assign, update); `sync_tracking.py` owns reconciliation
- Each skill owns its scripts subdirectory; no skill imports from another skill's scripts (exception: sync_backlog)
- Hooks are self-contained with `_common.py` providing shared utilities
- Skeleton templates in `references/skeletons/` are consumed only by `sprint_init.py`

### Conventions

- Scripts use `from __future__ import annotations` (PEP 563)
- All scripts are stdlib-only at runtime; dev deps are in requirements-dev.txt
- GitHub CLI (`gh`) is the external interface for all GitHub operations
- All bootstrap operations are idempotent (skip existing resources)
- Atomic writes via `atomic_write_text()` / `atomic_write_tf()` for concurrent safety

### Invariants

- No external Python packages required for plugin users
- `validate_config.load_config()` is the single entry point for reading project.toml
- All `gh` CLI calls go through `validate_config.gh()` or `validate_config.gh_json()` wrappers
- Tracking files use YAML frontmatter format parsed by `validate_config.read_tf()` / `write_tf()`

## Structural Snapshot

### Module Dependencies

| Module | Depends On |
|--------|-----------|
| validate_config | (none — foundation) |
| kanban | validate_config |
| sprint_init | validate_config |
| sprint_teardown | (none — standalone with subprocess) |
| sync_backlog | validate_config, bootstrap_github, populate_issues |
| commit | (none — standalone) |
| manage_epics | validate_config |
| manage_sagas | validate_config |
| sprint_analytics | validate_config |
| traceability | validate_config |
| test_coverage | validate_config |
| team_voices | validate_config |
| smoke_test | validate_config |
| gap_scanner | validate_config |
| test_categories | validate_config |
| risk_register | validate_config |
| assign_dod_level | validate_config, kanban |
| history_to_checklist | validate_config |
| bootstrap_github | validate_config |
| populate_issues | validate_config |
| setup_ci | validate_config |
| sync_tracking | validate_config, kanban |
| update_burndown | validate_config |
| check_status | validate_config |
| release_gate | validate_config |
| hook_common | (none — hook foundation) |
| hook_commit_gate | hook_common |
| hook_review_gate | hook_common |
| hook_session_context | hook_common |
| hook_verify_agent | hook_common |
| validate_anchors | (none — standalone) |

### Layering Direction

**Assessment:** clean top-down with one documented exception

**Layers (top to bottom):**
1. Skills (SKILL.md entry points) — orchestration
2. Skill scripts (setup/run/monitor/release) — skill-specific logic
3. Top-level scripts (kanban, manage_*, analytics, etc.) — shared business logic
4. validate_config — foundation (config, helpers, TOML parser)
5. Hooks — independent subsystem (hook_common → hook_*)

**Exceptions:**
- sync_backlog (layer 3) imports from bootstrap_github + populate_issues (layer 2) — documented and intentional cross-skill coupling

### Naming Conventions

- **Files:** snake_case for all Python files
- **Functions:** snake_case, private functions prefixed with `_`
- **Classes:** PascalCase (ProjectScanner, ConfigGenerator, TF)
- **Constants:** UPPER_SNAKE_CASE (TRANSITIONS, KANBAN_STATES, TABLE_ROW)
- **Test files:** `test_*.py` in `tests/` directory
- **Anchors:** `§namespace.identifier` format in source comments

### Boundary Clarity

**Assessment:** clean boundaries with validate_config as a clear hub

**Observations:**
- validate_config.py (1245 LOC) is the hub — imported by 20 of 25 production scripts
- Hooks are fully isolated from production scripts (separate import chain)
- Two-path state management (kanban + sync_tracking) is well-documented
- Sprint teardown is notably standalone — no imports from validate_config

## Drift Log

### 2026-03-23 (run 1): Baseline established

### 2026-03-23 (run 2): Bidirectional deferred imports between commit_gate and verify_agent_output
**Type:** dependency-reversal
**Evidence:** `commit_gate.py:178` does `from verify_agent_output import _read_toml_key` (deferred, inside `_load_config_check_commands()`). `verify_agent_output.py:241` does `from commit_gate import mark_verified` (deferred, inside main flow). Both are function-level imports, not top-level. The run 1 baseline recorded these hooks as independent (both only depending on `_common`). The deferred nature prevented detection during top-level import analysis.
**Severity:** MEDIUM
**Punchlist item:** BH-009 (escalated — combines with PAT-003 recommendation)
