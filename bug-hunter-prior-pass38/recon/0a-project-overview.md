# Phase 0a: Project Overview

## What giles is

A Claude Code plugin (v0.6.1) for running agile sprints with persona-based development. It orchestrates GitHub issues, PRs, CI, kanban tracking, and sprint ceremonies (kickoff, demo, retro) using fictional team personas that implement and review code in-character. A built-in scrum master persona named Giles facilitates all ceremonies.

## Codebase metrics

| Metric | Count |
|--------|-------|
| Python source files (scripts + skills + hooks) | 32 |
| Python test files | 24 |
| Total Python files | 56 |
| Source LOC (scripts + skills) | 10,118 |
| Hooks LOC | 1,169 |
| Test LOC | 20,520 |
| **Total Python LOC** | **31,807** |
| Skeleton templates (.tmpl) | 20 |
| Skill entry points (SKILL.md) | 5 |

Test-to-source ratio: ~1.8x (20,520 test LOC / 11,287 source+hooks LOC). Heavy testing.

## Project structure

```
giles/
├── .claude-plugin/
│   ├── plugin.json              — plugin manifest (name, version, hooks config)
│   └── hooks/                   — 6 files, 1,169 LOC
│       ├── commit_gate.py       — PreToolUse + PostToolUse hook for git commit
│       ├── review_gate.py       — PreToolUse hook for Bash (review gates)
│       ├── session_context.py   — SessionStart hook
│       ├── verify_agent_output.py — SubagentStop hook
│       └── _common.py           — shared hook utilities
├── scripts/                     — 21 files, 6,873 LOC — shared Python scripts
├── skills/                      — 5 skills, each with SKILL.md + scripts/
│   ├── sprint-setup/scripts/    — bootstrap_github, populate_issues, setup_ci
│   ├── sprint-run/scripts/      — sync_tracking, update_burndown
│   ├── sprint-monitor/scripts/  — check_status
│   ├── sprint-release/scripts/  — release_gate
│   └── sprint-teardown/         — SKILL.md only (uses scripts/sprint_teardown.py)
├── tests/                       — 24 files, 20,520 LOC
├── references/skeletons/        — 20 .tmpl files for sprint-config scaffolding
├── evals/                       — evals.json for skill evaluation
├── CLAUDE.md                    — main agent instructions (22.6 KB)
├── CHEATSHEET.md                — line-number index for all scripts/refs (39 KB)
├── Makefile                     — test, lint, venv targets
└── ruff.toml                    — ruff config (E/F rules, ignores E402/E501/E741)
```

## Largest source files (complexity hotspots)

| File | LOC | Role |
|------|-----|------|
| `scripts/validate_config.py` | 1,245 | Config validation, TOML parser, ~30 shared helpers |
| `scripts/sprint_init.py` | 1,027 | Auto-detect project, generate sprint-config/ |
| `scripts/kanban.py` | 809 | Kanban state machine, transitions, WIP limits, locking |
| `skills/sprint-release/scripts/release_gate.py` | 776 | Release gates, semver, notes, publishing |
| `skills/sprint-monitor/scripts/check_status.py` | 610 | CI + PR + milestone + drift + smoke checking |
| `skills/sprint-setup/scripts/populate_issues.py` | 564 | Parse milestones, create GitHub issues |
| `scripts/sprint_teardown.py` | 500 | Safe removal of sprint-config/ |
| `scripts/manage_epics.py` | 432 | Epic CRUD: add, remove, reorder stories |

## Largest test files

| File | LOC |
|------|-----|
| `tests/test_verify_fixes.py` | 2,978 |
| `tests/test_sprint_runtime.py` | 2,536 |
| `tests/test_pipeline_scripts.py` | 2,290 |
| `tests/test_release_gate.py` | 2,102 |
| `tests/test_bugfix_regression.py` | 1,529 |
| `tests/test_kanban.py` | 1,434 |
| `tests/test_hooks.py` | 1,270 |
| `tests/fake_github.py` | 991 (test infrastructure, not tests) |

## Architecture notes relevant to bug hunting

### Dependency policy
- **Stdlib-only for user runtime** -- no pip install needed. Custom TOML parser instead of tomllib.
- Dev dependencies (pytest, hypothesis, ruff) are fine. CLI tools like `gh` and `jq` are also acceptable.

### Import chain risk area
- Skill scripts in `skills/*/scripts/` do `sys.path.insert(0, ...)` to reach `scripts/validate_config.py` four directories up. Top-level `scripts/` use a single parent path insert. This is a potential source of import path bugs.

### Two-path state management
- `kanban.py` is the mutation path (local-first, syncs to GitHub on every write, validates transitions).
- `sync_tracking.py` is the reconciliation path (accepts GitHub state for PR linkage, branch, completion metadata).
- Both can write `status` -- kanban validates transitions, sync_tracking accepts any valid state from GitHub. Conflict potential here.

### Cross-skill coupling
- `scripts/sync_backlog.py` imports `bootstrap_github` and `populate_issues` from `skills/sprint-setup/scripts/`. Intentional coupling for backlog auto-sync reuse.

### Idempotency contract
- All bootstrap and monitoring scripts are supposed to be idempotent (skip existing resources). Violations of this contract would be bugs.

### Hooks system
- 4 hooks registered in plugin.json: PreToolUse/Bash (commit_gate, review_gate), PostToolUse/Bash (commit_gate --post), SubagentStop (verify_agent_output), SessionStart (session_context).
- Hooks are a newer addition (hooks LOC is ~10% of source). Worth scrutiny for edge cases.

### Config system
- Everything flows through `sprint-config/project.toml` via `validate_config.load_config()`.
- Symlink-based: sprint-config/ files are symlinks to project files (except giles.md which is copied).
- Required TOML keys enforced by `_REQUIRED_TOML_KEYS`; optional deep-doc keys for PRD, test plans, sagas, epics.

### Test infrastructure
- `fake_github.py` (991 LOC) -- mock GitHub CLI layer for offline testing.
- `mock_project.py` -- scaffolds test project directories.
- Golden recording/replay for end-to-end validation.
- Property-based tests via hypothesis.

### Prior bug-hunting passes
- 37 prior passes completed (directories `bug-hunter-prior-pass5` through `bug-hunter-prior-pass37`).
- Most recent commit: "bug-hunter pass 37 -- fully converged, 32/32 resolved".
- Codebase has been heavily audited. Remaining bugs are likely subtle: edge cases, race conditions, semantic mismatches between docs and code.

### Linting
- ruff configured with E/F rules, ignoring E402 (sys.path inserts), E501 (long lines), E741 (ambiguous names).
- Latest commit added ruff.toml and cleaned all lint violations.
