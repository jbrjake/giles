# Phase 0g — Recon Summary (Pass 38)

## Baseline

| Metric | Value |
|--------|-------|
| Python files | 56 (32 source, 24 test) |
| Total LOC | ~31,800 |
| Tests | 1182 pass, 0 fail, 0 skip |
| Test functions | 1213 |
| Coverage | 83% (5314 stmts, 914 missed) |
| Runtime | ~17s |
| Lint issues | 0 (ruff clean) |
| Skipped tests | 0 (1 conditional self.skipTest in golden_run) |

## Change Since Pass 37

One commit: `65636ca` — ruff.toml added, lint violations cleaned across 16 files (mostly removing unused imports, simplifying assertions in tests). Mechanical changes, but touched test files that need verification.

## Complexity Hotspots (prioritize for adversarial audit)

1. **validate_config.py** (1,245 LOC, 95% coverage) — custom TOML parser, ~30 shared helpers
2. **sprint_init.py** (1,027 LOC, 90%) — project scanner, config generator, symlink logic
3. **kanban.py** (809 LOC, 84%) — state machine, transitions, locking, WIP limits
4. **release_gate.py** (776 LOC, 89%) — semver, gates, release publishing
5. **check_status.py** (610 LOC, 76%) — CI/PR/milestone monitoring

## Churn Hotspots (prioritize for test quality audit)

1. **tests/test_hooks.py** (21 commits, 992 insertions) — most churned file in the project
2. **scripts/kanban.py** (12 commits)
3. **tests/test_new_scripts.py** (11 commits)
4. **skills/sprint-run/scripts/sync_tracking.py** (10 commits)
5. **Hook files** (review_gate 10, verify_agent_output 9, session_context 8, commit_gate 8)

## Low-Coverage Scripts (prioritize for doc-to-implementation audit)

| Script | Coverage | Gap |
|--------|----------|-----|
| assign_dod_level.py | 35% | main() + assign_levels() |
| smoke_test.py | 57% | main() + write_history() |
| history_to_checklist.py | 61% | generate_checklists() + main() |
| risk_register.py | 64% | main() + CLI subcommands |
| gap_scanner.py | 67% | main() + scan logic |
| test_categories.py | 67% | main() + report formatting |
| test_coverage.py | 68% | main() + check_test_coverage() |

## Audit Strategy

After 37 converged passes, remaining bugs will be subtle. Focus on:
1. **Ruff cleanup regressions** — did removing imports/changing assertions break anything?
2. **Logic in low-coverage code** — untested paths may harbor real bugs
3. **High-churn test files** — accumulated cruft, weakened assertions, duplicate coverage
4. **Edge cases in complex modules** — TOML parser, kanban state machine, release gates
5. **Doc drift** — CLAUDE.md/CHEATSHEET.md accuracy after recent changes
