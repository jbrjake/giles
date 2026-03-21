# 0e - Git Churn Analysis

## Method

Analyzed the last 50 commits on `main` using file-change frequency:
```
git log --pretty=format: --name-only -50 | sort | uniq -c | sort -rn | head -30
```

## Top 20 Most-Changed Files (last 50 commits)

| Rank | Changes | File | Category |
|------|---------|------|----------|
| 1 | 10 | `tests/test_gh_interactions.py` | Test |
| 2 | 9 | `scripts/validate_anchors.py` | Script |
| 3 | 7 | `CLAUDE.md` | Docs |
| 4 | 6 | `tests/test_release_gate.py` | Test |
| 5 | 6 | `tests/test_pipeline_scripts.py` | Test |
| 6 | 6 | `skills/sprint-run/scripts/sync_tracking.py` | Script |
| 7 | 6 | `skills/sprint-release/scripts/release_gate.py` | Script |
| 8 | 6 | `scripts/validate_config.py` | Script |
| 9 | 6 | `scripts/migrate_to_anchors.py` | Script |
| 10 | 6 | `BUG-HUNTER-STATUS.md` | Docs (tracking) |
| 11 | 5 | `tests/test_validate_anchors.py` | Test |
| 12 | 5 | `tests/test_migrate_anchors.py` | Test |
| 13 | 5 | `tests/test_lifecycle.py` | Test |
| 14 | 5 | `tests/fake_github.py` | Test infra |
| 15 | 5 | `skills/sprint-setup/scripts/populate_issues.py` | Script |
| 16 | 5 | `scripts/sprint_init.py` | Script |
| 17 | 5 | `CHEATSHEET.md` | Docs |
| 18 | 5 | `BUG-HUNTER-PUNCHLIST.md` | Docs (tracking) |
| 19 | 4 | `skills/sprint-run/scripts/update_burndown.py` | Script |
| 20 | 4 | `skills/sprint-monitor/SKILL.md` | Skill entry |

## Commit Patterns

The last 50 commits span 9 bug-hunter passes plus a greppable anchor migration feature. The commit history shows:

1. **Bug-hunter audit cycles dominate**: Passes 5 through 9 are visible, each following the same pattern: fix commits (prefixed `fix:`), then test additions (`test:`), then doc alignment (`docs:`), then a chore commit marking items resolved (`chore: mark all N punchlist items as resolved`).

2. **Greppable anchor migration** (commits `ab2016d` through `521b31e`): A 10-commit feature branch introducing `scripts/validate_anchors.py` and `scripts/migrate_to_anchors.py`. This explains why `validate_anchors.py` shows 9 changes -- it was built incrementally then bug-fixed across multiple passes.

3. **Conventional commit style** is consistent: `fix:`, `feat:`, `test:`, `docs:`, `chore:` prefixes throughout.

## Hotspot Analysis

### Highest-risk files (most churn + core logic)

- **`tests/test_gh_interactions.py`** (10 changes): The most-changed file in the repo. This is the test file for GitHub interaction logic. Heavy churn here suggests the GitHub integration layer is complex and frequently needs correction. Worth close inspection for mock fidelity issues.

- **`scripts/validate_config.py`** (6 changes): The shared helpers module imported by every other script. Changes here ripple everywhere. High churn = high risk of subtle regressions.

- **`skills/sprint-release/scripts/release_gate.py`** (6 changes): Release gating logic has been patched 6 times in 50 commits. Possible sign of under-specified edge cases.

- **`skills/sprint-run/scripts/sync_tracking.py`** (6 changes): Tracking reconciliation between local files and GitHub. Repeated fixes suggest state synchronization is fragile.

- **`tests/fake_github.py`** (5 changes): The test double for `gh` CLI calls. Frequent changes indicate ongoing fidelity gaps between the fake and real GitHub CLI behavior.

### Test file churn breakdown

| Test file | Changes |
|-----------|---------|
| `test_gh_interactions.py` | 10 |
| `test_release_gate.py` | 6 |
| `test_pipeline_scripts.py` | 6 |
| `test_validate_anchors.py` | 5 |
| `test_migrate_anchors.py` | 5 |
| `test_lifecycle.py` | 5 |
| `fake_github.py` | 5 |
| `test_verify_fixes.py` | 2 |
| `test_sync_backlog.py` | 2 |
| `test_hexwise_setup.py` | 2 |
| `test_golden_run.py` | 2 |
| `test_sprint_teardown.py` | 1 |
| `test_sprint_analytics.py` | 0 |

Test files account for roughly half of all churn, which tracks with the bug-hunter audit methodology: find bugs, write tests, fix code.

### Documentation churn

`CLAUDE.md` (7 changes) and `CHEATSHEET.md` (5 changes) are updated frequently, likely to keep line-number references in sync with code changes. `BUG-HUNTER-STATUS.md` and `BUG-HUNTER-PUNCHLIST.md` are tracking artifacts, not real code risk.

## Key Takeaways for Bug Hunting

1. **Focus on the top-4 scripts**: `validate_config.py`, `release_gate.py`, `sync_tracking.py`, `validate_anchors.py` -- these have the most churn and carry the most logic.
2. **`fake_github.py` fidelity**: 5 changes in 50 commits means the test double keeps needing corrections. Any test that relies on it could be passing with incorrect assumptions.
3. **`test_gh_interactions.py`**: 10 changes means tests were repeatedly added/fixed. Look for tests that were weakened (assertions removed) rather than strengthened.
4. **No files are "stable and untouched"** among the core scripts -- every major script has been touched at least once in this window, which suggests the codebase is still maturing.
