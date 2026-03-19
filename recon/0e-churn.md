# 0e — Git Churn Analysis

Generated: 2026-03-18
Window: last 50 commits

## Top 20 Most-Changed Files (production code only)

Excludes test files, docs-only files (BUG-HUNTER-*.md), and blank lines from git log.

| Rank | Changes | File | Lines | Functions |
|------|---------|------|-------|-----------|
| 1 | 14 | `scripts/validate_config.py` | 1190 | 42 |
| 2 | 9 | `skills/sprint-run/scripts/sync_tracking.py` | 280 | 5 |
| 3 | 9 | `scripts/kanban.py` | 612 | 13 |
| 4 | 5 | `CHEATSHEET.md` | — | — |
| 5 | 4 | `skills/sprint-setup/scripts/populate_issues.py` | 553 | 16 |
| 6 | 4 | `CLAUDE.md` | — | — |
| 7 | 3 | `skills/sprint-run/scripts/update_burndown.py` | 225 | — |
| 8 | 3 | `skills/sprint-run/references/story-execution.md` | — | — |
| 9 | 3 | `scripts/manage_epics.py` | 410 | — |
| 10 | 2 | `skills/sprint-run/SKILL.md` | — | — |
| 11 | 2 | `skills/sprint-run/references/kanban-protocol.md` | — | — |
| 12 | 2 | `skills/sprint-run/references/ceremony-kickoff.md` | — | — |
| 13 | 2 | `skills/sprint-run/agents/implementer.md` | — | — |
| 14 | 2 | `skills/sprint-monitor/scripts/check_status.py` | 464 | — |
| 15 | 2 | `scripts/validate_anchors.py` | 337 | — |
| 16 | 2 | `scripts/traceability.py` | 222 | — |
| 17 | 2 | `scripts/sprint_init.py` | 996 | — |
| 18 | 2 | `scripts/manage_sagas.py` | 291 | — |

Note: test files excluded from ranking but for reference: `tests/test_kanban.py` (11 changes), `tests/test_sprint_runtime.py` (8), `tests/test_verify_fixes.py` (7), `tests/test_bugfix_regression.py` (4), `tests/fake_github.py` (4).

## Most Recently Changed Files (last 5 commits)

These files were touched in HEAD~5..HEAD:

| File | Category |
|------|----------|
| `scripts/kanban.py` | production |
| `scripts/validate_config.py` | production |
| `skills/sprint-run/scripts/sync_tracking.py` | production |
| `skills/sprint-run/references/kanban-protocol.md` | reference doc |
| `CHEATSHEET.md` | docs |
| `CLAUDE.md` | docs |
| `tests/test_kanban.py` | test |
| `tests/test_pipeline_scripts.py` | test |
| `tests/test_property_parsing.py` | test |
| `tests/test_sprint_runtime.py` | test |

## Hot Zones (appear in both lists)

Files that are both high-churn overall AND actively changing in the last 5 commits:

| File | Total changes (50 commits) | Lines | Functions | Verdict |
|------|---------------------------|-------|-----------|---------|
| **`scripts/validate_config.py`** | 14 | 1190 | 42 | CRITICAL |
| **`scripts/kanban.py`** | 9 | 612 | 13 | HIGH |
| **`skills/sprint-run/scripts/sync_tracking.py`** | 9 | 280 | 5 | HIGH |

## Risk Assessment

### CRITICAL: `scripts/validate_config.py`
- **Why**: Highest churn (14/50 commits), largest file (1190 lines), most functions (42). This is the shared foundation imported by every other script. It contains the TOML parser, config loader, all path helpers, GitHub wrappers, kanban state constants, and tracking file I/O (`read_tf`/`write_tf`). A bug here propagates everywhere.
- **Complexity factors**: Custom TOML parser (no external lib), YAML-like frontmatter read/write, slug generation, date parsing, GitHub CLI wrappers — many distinct responsibilities in one file.
- **Recent fix areas**: `_yaml_safe` numeric quoting (BH22-104), `write_tf` persona safety (BH22-108), state management model clarification (BH22-005/110).

### HIGH: `scripts/kanban.py`
- **Why**: 9 changes in 50 commits, 612 lines, 13 functions. This is a new subsystem (introduced in the last 20 commits) implementing the kanban state machine with GitHub sync, locking, atomic writes, and rollback. New code that has been through multiple rounds of bug fixes is a classic risk profile.
- **Complexity factors**: State machine transitions, file locking (sentinel files), atomic write with rollback, GitHub label/assignee sync, argparse CLI entry point.
- **Recent fix areas**: `lock_story` sentinel (BH22-100), `atomic_write_tf` mutation (BH22-101), rollback safety (BH22-102/103/107), filename casing (BH22-117), multi-match warning (BH22-105), `assign` body match (BH22-109).

### HIGH: `skills/sprint-run/scripts/sync_tracking.py`
- **Why**: 9 changes in 50 commits. This is the reconciliation path for local tracking files vs GitHub state. It works in tension with `kanban.py` (the mutation path), and the two-path model was itself a recent bug fix target (BH22-005/110).
- **Complexity factors**: Must handle partial data from GitHub, merge with local state, avoid overwriting kanban.py mutations. Only 5 functions / 280 lines, but the contract with kanban.py is subtle.

### MEDIUM: `skills/sprint-setup/scripts/populate_issues.py`
- **Why**: 4 changes, 553 lines, 16 functions. Parses milestone markdown into GitHub issues. Parsing logic is always fragile.
- **Complexity factors**: Markdown parsing (story tables, detail blocks), milestone-to-sprint mapping, epic enrichment, GitHub issue creation.

### MEDIUM: `scripts/manage_epics.py`
- **Why**: 3 changes, 410 lines. Markdown file manipulation (add/remove/reorder stories in epic files). Markdown manipulation is inherently brittle.

### LOW-MEDIUM: `skills/sprint-run/scripts/update_burndown.py`
- **Why**: 3 changes, 225 lines. Reads GitHub milestone data and writes burndown. Lower complexity but touches both GitHub API and file I/O.

## Commit Pattern Context

The last 20 commits show a concentrated bug-hunting cycle (BH22-* identifiers). The kanban subsystem was built and then immediately stress-tested, producing fixes across `kanban.py`, `validate_config.py`, and `sync_tracking.py`. This means:

1. **Many bugs have already been found and fixed** in these files — good.
2. **The fixes themselves are fresh and may introduce new issues** — the "fix creates a bug" pattern. Each fix should be reviewed for unintended side effects.
3. **The kanban/sync_tracking interaction** is the most architecturally risky area. Two subsystems with overlapping write paths to the same tracking files, coordinated by convention rather than a shared lock.
