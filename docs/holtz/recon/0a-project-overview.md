# Step 0a: Project Overview

**Project:** giles — Claude Code plugin for agile sprints with persona-based development
**Language:** Python 3.10+ (stdlib-only runtime, dev deps: pytest, hypothesis, jq, ruff)
**Repository structure:** Plugin with skills, scripts, hooks, references, skeleton templates

## Architecture

- **Plugin manifest:** `.claude-plugin/plugin.json`
- **5 skills:** sprint-setup, sprint-run, sprint-monitor, sprint-release, sprint-teardown
- **25 production scripts** (~10,138 LOC total) in `scripts/` and `skills/*/scripts/`
- **5 hooks** in `hooks/`: session_context, review_gate, commit_gate, verify_agent_output, _common
- **Skeleton templates:** 20 `.tmpl` files in `references/skeletons/`
- **Config system:** `sprint-config/project.toml` (custom TOML parser, no tomllib)

## Key Design Decisions

- **Config-driven:** All project-specific values from `sprint-config/project.toml`
- **Symlink-based config:** `sprint_init.py` creates symlinks; teardown removes them
- **Custom TOML parser:** `parse_simple_toml()` in validate_config.py (1245 LOC, largest file)
- **Scripts import chain:** Skill scripts use `sys.path.insert(0, ...)` to reach shared validate_config.py
- **Two-path state management:** kanban.py (mutation) + sync_tracking.py (reconciliation)
- **Idempotent scripts:** All bootstrap/monitoring scripts skip existing resources
- **Stdlib-only runtime:** No pip install needed for users; dev deps (pytest, hypothesis) are fine
- **GitHub as source of truth:** Local tracking files sync from GitHub state

## Module Sizes (top 10 by LOC)

| Script | LOC | Purpose |
|--------|-----|---------|
| validate_config.py | 1245 | Config validation, TOML parser, shared helpers |
| sprint_init.py | 1027 | Project scanner, config generator |
| kanban.py | 815 | Kanban state machine |
| release_gate.py | 776 | Release gates, versioning |
| check_status.py | 616 | CI/PR/milestone monitoring |
| populate_issues.py | 565 | Issue creation from milestones |
| sprint_teardown.py | 500 | Safe config removal |
| manage_epics.py | 432 | Epic CRUD |
| setup_ci.py | 416 | CI workflow generation |
| validate_anchors.py | 342 | Anchor reference validation |

## Test Infrastructure

- 20 test files in `tests/`
- Test helpers: conftest.py, fake_github.py, gh_test_helpers.py, mock_project.py, golden_recorder.py, golden_replay.py
- Prior audit: 1188 tests passing, lint clean after 39 bug-hunter passes

## Prior Audit Context

- 39 prior bug-hunter passes converged the codebase
- Last pass found 16 issues (0 HIGH, 7 MEDIUM, 7 LOW, 1 INFO) — all resolved
- Key patterns: missing API limits, doc/code drift at seams, dedup filter inconsistency
- All 22 sys.path.insert computations verified correct
- All critical seams verified clean (TF round-trip, lock coordination, atomic writes, label format, hooks, ConfigError propagation)

## Risk Areas for This Audit

1. **validate_config.py (1245 LOC):** Largest file, custom TOML parser, many shared helpers — any bug here cascades everywhere
2. **Cross-script import chain:** sys.path.insert fragility across skill boundaries
3. **Two-path state management:** kanban.py vs sync_tracking.py concurrency
4. **Template-based code generation:** setup_ci.py, sprint_init.py — template correctness
5. **Hook system:** 5 hooks with JSON output protocol — error handling at shell/Python boundary
