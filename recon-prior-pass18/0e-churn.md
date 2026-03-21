# 0e - Git Churn Analysis

**Date:** 2026-03-16
**Total commits:** 279
**Contributors:** 3 (Jon Rubin: 274, Claude: 3, Jonathon Rubin: 2)

## Commit Type Breakdown (all 279 commits)

| Type | Count | % |
|------|-------|---|
| fix / bug / patch | 123 | 44% |
| feat / test / refactor | 109 | 39% |
| chore / docs | 62 | 22% |
| Bug-hunter pass refs (P1-P17, BH-) | 84 | 30% |

Note: categories overlap (a fix commit can also reference a bug-hunter pass).

## Most-Changed Files (last 100 commits)

| Touches | File | Category |
|---------|------|----------|
| 22 | `tests/test_gh_interactions.py` | test |
| 18 | `scripts/validate_config.py` | production |
| 18 | `BUG-HUNTER-PUNCHLIST.md` | audit tracking |
| 15 | `BUG-HUNTER-STATUS.md` | audit tracking |
| 14 | `tests/fake_github.py` | test infra |
| 14 | `skills/sprint-run/scripts/sync_tracking.py` | production |
| 13 | `skills/sprint-setup/scripts/populate_issues.py` | production |
| 12 | `tests/test_verify_fixes.py` | test |
| 12 | `tests/test_release_gate.py` | test |
| 11 | `skills/sprint-release/scripts/release_gate.py` | production |
| 9 | `scripts/validate_anchors.py` | production |
| 8 | `tests/test_property_parsing.py` | test |
| 8 | `skills/sprint-run/scripts/update_burndown.py` | production |
| 8 | `skills/sprint-monitor/scripts/check_status.py` | production |
| 8 | `scripts/sprint_init.py` | production |
| 8 | `scripts/manage_epics.py` | production |

## Lifetime Churn for Hot Files

| Total commits | File |
|---------------|------|
| 40 | `tests/test_gh_interactions.py` |
| 36 | `scripts/validate_config.py` |
| 28 | `skills/sprint-setup/scripts/populate_issues.py` |
| 26 | `skills/sprint-run/scripts/sync_tracking.py` |
| 26 | `skills/sprint-release/scripts/release_gate.py` |
| 23 | `tests/fake_github.py` |

## Patterns Observed

1. **validate_config.py is the #1 production hotspot.** 36 lifetime commits, 18 in the last 100. This file is the shared utility layer (TOML parser, `gh()` wrapper, `load_config()`, kanban helpers). It has been the target of repeated bug-hunter fixes including:
   - TOML parser single-quote handling, unquoted value warnings
   - load_config double-parsing fix (BH-014)
   - Section/key validation regression (P15-001, P15-002)
   - Leading-zero sprint fix (P17)
   - Repeated import/dead-code cleanups

2. **test_gh_interactions.py is the #1 test hotspot.** 40 lifetime commits. It has been split (P13-013), refactored (P12), and had assertions tightened across many passes. High churn here suggests the test may still be fragile or the code it covers keeps changing.

3. **sync_tracking.py and populate_issues.py are the next production hotspots** (26 and 28 commits respectively). Both deal with GitHub data marshaling (YAML quoting, milestone mapping, issue creation) -- areas prone to edge-case bugs.

4. **release_gate.py has 26 lifetime commits** covering tag deletion on push failure (BH-001), truncation risk gating, version calculation, and release notes generation.

5. **44% of all commits are fixes.** 30% of all commits explicitly reference a bug-hunter pass. The project has been through 17 audit passes, meaning the fix rate is high but the audit loop is actively catching real issues.

6. **fake_github.py (test infra) has 23 commits.** This test double has required significant fidelity work (milestone counters, label colors, jq evaluation, strict mode). Changes to FakeGitHub cascade to many test files.

7. **Nearly all commits are from a single contributor** (Jon Rubin, 274/279). The 3 Claude commits and 2 "Jonathon Rubin" commits are likely the same person or AI-assisted.
