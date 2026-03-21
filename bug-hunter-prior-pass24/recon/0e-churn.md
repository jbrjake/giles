# 0e - Git Churn Analysis

**Pass:** P24
**Date:** 2026-03-19
**Scope:** Last 50 commits (41f76a1..d01fd85), focus on since 2026-03-01

## Highest-Churn Files (last 50 commits)

| Touches | File | Category |
|---------|------|----------|
| 16 | `tests/test_kanban.py` | Test |
| 12 | `scripts/kanban.py` | Production |
| 11 | `scripts/validate_config.py` | Production |
| 6 | `tests/test_sprint_runtime.py` | Test |
| 6 | `CLAUDE.md` | Docs |
| 5 | `skills/sprint-run/scripts/sync_tracking.py` | Production |
| 4 | `tests/test_release_gate.py` | Test |
| 4 | `tests/test_property_parsing.py` | Test |
| 4 | `skills/sprint-run/references/story-execution.md` | Docs |
| 4 | `skills/sprint-run/references/kanban-protocol.md` | Docs |
| 4 | `CHEATSHEET.md` | Docs |
| 3 | `tests/test_pipeline_scripts.py` | Test |
| 3 | `skills/sprint-release/scripts/release_gate.py` | Production |
| 2 | `tests/test_verify_fixes.py` | Test |
| 2 | `tests/test_hexwise_setup.py` | Test |
| 2 | `skills/sprint-monitor/scripts/check_status.py` | Production |
| 2 | `skills/sprint-run/agents/implementer.md` | Docs |

## Co-Change Patterns

The following file pairs are frequently modified together, revealing coupling:

### Tier 1: Very Strong Coupling (changed together 8+ times)

- **`scripts/kanban.py` <-> `tests/test_kanban.py`** (changed together in ~12 of kanban.py's 12 touches)
  - Expected: production code and its tests move in lockstep. Healthy pattern.

### Tier 2: Strong Coupling (changed together 4-6 times)

- **`scripts/kanban.py` <-> `scripts/validate_config.py`** (~6 co-changes)
  - kanban.py depends on TF/read_tf/write_tf from validate_config.py. Fixes to YAML quoting, field handling, and round-trip fidelity ripple between these two. This coupling is structural (shared data model).

- **`scripts/validate_config.py` <-> `tests/test_kanban.py`** (~5 co-changes)
  - When validate_config's TF/write_tf changes, kanban tests need updating. Indirect coupling through the shared data model.

- **`scripts/kanban.py` <-> `skills/sprint-run/scripts/sync_tracking.py`** (~4 co-changes)
  - Two-path state management design: both write tracking files, so field allowlist and YAML format changes affect both.

### Tier 3: Moderate Coupling (changed together 2-3 times)

- **`skills/sprint-release/scripts/release_gate.py` <-> `tests/test_release_gate.py`** (3 co-changes)
- **`scripts/validate_config.py` <-> `skills/sprint-setup/scripts/bootstrap_github.py`** (2 co-changes)
- **`scripts/kanban.py` <-> `skills/sprint-run/references/kanban-protocol.md`** (2 co-changes) -- code/doc sync

## Recent Activity Concentration (since 2026-03-01)

All 50 most-recent commits fall within the March 2026 window. The work breaks into clear phases:

### Phase 1: Kanban State Machine (commits 41f76a1..6f4de6c)
- New `scripts/kanban.py` built from scratch (feat commits: core, sync, CLI, update)
- Extracted TF/read_tf/write_tf from sync_tracking.py into validate_config.py
- Heavy doc updates to replace raw `gh issue edit` with kanban.py usage

### Phase 2: Bug-Hunter Passes 22-23 (commits 7c2dc4e..d01fd85)
- Massive fix/test wave: 30+ commits in rapid succession
- kanban.py touched 12 times, validate_config.py 11 times
- Pattern: fix commit immediately followed by test-strengthening commit

## Hot Spots (Bug-Prone Areas)

### 1. `scripts/kanban.py` -- HIGHEST RISK
- 12 touches in 50 commits, with bug fixes in nearly every pass (BH22, BH23)
- Bugs found: comma quoting (BH23-200), double-fault TF restore (BH23-201), slug collision (BH23-204), field allowlist (BH23-230), filename casing (BH22-117), assign body match (BH22-109), lock_story sentinel (BH22-100), atomic_write_tf mutation (BH22-101), rollback safety (BH22-103)
- **Assessment:** Heavy recent churn with repeated bug fixes suggests this module may still harbor edge-case bugs, especially in the write/rollback paths.

### 2. `scripts/validate_config.py` -- HIGH RISK
- 11 touches, with TOML parser hardening across multiple passes (BH20, BH21, BH23)
- Bugs found: TOML escape sequences (BH23-227), frontmatter round-trip fidelity (BH23-205), _yaml_safe field coverage (BH23-210), read_tf missing files (BH23-232), comma quoting (BH23-200), numeric quoting (BH22-104)
- **Assessment:** The custom TOML parser and YAML frontmatter writer are the two most-patched subsystems in the entire codebase. Edge cases in string escaping/quoting keep surfacing.

### 3. `skills/sprint-run/scripts/sync_tracking.py` -- MODERATE RISK
- 5 touches, all bug fixes (BH22-110, BH23-207/212, field allowlist, pagination)
- Coupled to kanban.py through shared TF data model
- **Assessment:** Receives collateral damage from kanban.py/validate_config.py changes.

### 4. `skills/sprint-release/scripts/release_gate.py` -- MODERATE RISK
- 3 touches with targeted fixes: null-byte delimiter crash (BH23-101), tag pre-check (BH23-235), teardown heuristic (BH23-219)
- **Assessment:** Less churn than kanban/validate_config, but the null-byte crash (BH23-101) was a serious production bug.

## Churn Velocity

The 50 most-recent commits span roughly 2 weeks (early March to March 19). That is approximately 3.5 commits/day, heavily concentrated in bug-fix and test-strengthening work. The codebase is in a stabilization phase -- lots of hardening, few new features.

## Summary

| Risk | Files | Why |
|------|-------|-----|
| HIGHEST | `scripts/kanban.py` | 12 touches, 9+ distinct bug fixes, write/rollback paths fragile |
| HIGH | `scripts/validate_config.py` | 11 touches, TOML parser + YAML writer both repeatedly patched |
| MODERATE | `skills/sprint-run/scripts/sync_tracking.py` | 5 touches, coupled to kanban.py data model |
| MODERATE | `skills/sprint-release/scripts/release_gate.py` | 3 touches, had a P0 null-byte crash |
| LOW | `skills/sprint-monitor/scripts/check_status.py` | 2 touches, exception handling fixes |
