# Phase 0e: Git Churn Analysis

**Repo:** giles (167 total commits)
**Window:** last 50 commits analyzed, with daily breakdown since 2026-03-10

## Top 20 Most-Changed Files (last 50 commits)

| Rank | File | Changes | Notes |
|------|------|---------|-------|
| 1 | `scripts/validate_config.py` | 13 | Shared utility hub — every bug pass touches it |
| 2 | `tests/test_pipeline_scripts.py` | 12 | Tests for Chunk 3-4 pipeline scripts |
| 3 | `CLAUDE.md` | 12 | Line-number index — updated whenever code shifts |
| 4 | `tests/test_gh_interactions.py` | 11 | Main integration test file |
| 5 | `CHEATSHEET.md` | 11 | Detailed line-number index — same drift problem as CLAUDE.md |
| 6 | `skills/sprint-setup/scripts/populate_issues.py` | 9 | Milestone/issue parsing — 9 of 9 are fix commits |
| 7 | `skills/sprint-release/scripts/release_gate.py` | 9 | Release gating — 8 of 9 are fix commits |
| 8 | `skills/sprint-monitor/scripts/check_status.py` | 9 | CI/PR/drift checks — 7 of 9 are fix commits |
| 9 | `scripts/sprint_analytics.py` | 9 | Sprint metrics — all 9 are fix commits post-creation |
| 10 | `tests/test_release_gate.py` | 8 | Release gate tests |
| 11 | `skills/sprint-run/scripts/sync_tracking.py` | 8 | GitHub-to-local sync — 7 of 8 are fix commits |
| 12 | `scripts/manage_sagas.py` | 8 | Saga management |
| 13 | `scripts/manage_epics.py` | 8 | Epic management |
| 14 | `skills/sprint-run/scripts/update_burndown.py` | 6 | Burndown updates |
| 15 | `scripts/test_coverage.py` | 6 | Test coverage comparison |
| 16 | `scripts/sprint_init.py` | 6 | Project bootstrap/scaffold |
| 17 | `BUG-HUNTER-STATUS.md` | 6 | Audit tracking doc |
| 18 | `tests/fake_github.py` | 5 | Test double for gh CLI |
| 19 | `skills/sprint-monitor/SKILL.md` | 5 | Monitor skill entry point |
| 20 | `scripts/sprint_teardown.py` | 5 | Config removal |

## Recent Commit Patterns

### Commit type breakdown (last 50 commits)

| Type | Count | Percentage |
|------|-------|-----------|
| `fix:` | 32 | 64% |
| `docs:` | 8 | 16% |
| `feat:` | 5 | 10% |
| `test:` | 4 | 8% |
| `refactor:` | 1 | 2% |

The repo is overwhelmingly in fix/audit mode. 64% of the last 50 commits are fixes, and most reference specific punchlist IDs (33 unique IDs like P5-13, BH4-01, etc.).

### Daily velocity since 2026-03-10

| Date | Commits | Notes |
|------|---------|-------|
| Mar 10 | 14 | CI setup, README rewrite, sprint/milestone mapping fixes |
| Mar 11 | 43 | Feature burst (Chunks 1-4: Giles persona, ceremonies, analytics, pipeline scripts) |
| Mar 12 | 20 | Dreamcatcher alignment, deep doc features, bug fixes |
| Mar 13 | 50 | Entire day of bug-hunter audit passes (BH1 through P5) |
| Mar 14 | 0 | Current day (audit in progress) |

127 commits in 4 days. Mar 13 alone had 50 commits — all bug fixes and test additions from audit passes 1-5.

### Fix commit sub-patterns

The 32 fix commits break down into recurring themes:

1. **Stale line-number references** (8+ commits): CLAUDE.md and CHEATSHEET.md line refs drift whenever code changes. At least 8 commits exist solely to update line numbers.
2. **Batch bug-fix dumps** (5 commits): Large "resolve N items" commits (e.g., "batch resolve P5-05/06/07/08/14/15/16/19/21/23/24/31/32/33/34/35/36/37/40" touches 18 items at once).
3. **Test integrity fixes** (4 commits): Tests that were too loose, missing negative cases, or not testing real boundaries.
4. **Encoding/string handling** (3 commits): UTF-8, lstrip character stripping, TOML parser edge cases.
5. **API/GitHub interaction fixes** (3 commits): Milestone errors, query limits, flag validation.

## Hotspot Analysis

### Tier 1: Chronic Hotspots (changed in nearly every audit pass)

**`scripts/validate_config.py`** (13 changes, #1 overall)
- The shared utility hub for the entire project. Every script imports from it.
- Touched by every single bug-hunter pass (BH1 through P5).
- Contains the TOML parser, GitHub helpers, config loading, path helpers — too many responsibilities in one file.
- Signal: Central coupling point. Bugs here cascade everywhere.

**`CLAUDE.md` + `CHEATSHEET.md`** (12 + 11 = 23 combined changes)
- These are line-number index files that go stale every time code changes.
- Over half their commits are just fixing drifted line numbers.
- Signal: The line-number indexing pattern creates a maintenance burden that generates churn without adding value. Every code change requires a doc update.

### Tier 2: Fix Magnets (high fix-to-feature ratio)

**`skills/sprint-setup/scripts/populate_issues.py`** (9 changes, all fixes after initial commit)
- Milestone parsing, regex handling, string stripping — repeated edge-case bugs.
- Signal: Complex parsing logic that keeps surfacing new failure modes.

**`skills/sprint-release/scripts/release_gate.py`** (9 changes, nearly all fixes)
- Created once, then fixed 8 times across 4 audit passes.
- Signal: Insufficient initial testing; release flow has many edge cases.

**`scripts/sprint_analytics.py`** (9 changes, all fixes after feature commit)
- Created in one commit, then fixed in every subsequent audit pass.
- Signal: Was shipped without adequate test coverage.

**`skills/sprint-monitor/scripts/check_status.py`** (9 changes, mostly fixes)
- CI check, PR check, drift detection — each sub-function needed fixes.
- Signal: Multiple responsibilities, each with its own failure modes.

### Tier 3: Stabilizing (high churn but potentially settling)

**`skills/sprint-run/scripts/sync_tracking.py`** (8 changes)
- GitHub-as-source-of-truth sync logic — complex state reconciliation.
- Most recent changes are from P4/P5 passes, suggesting ongoing fragility.

**`tests/test_gh_interactions.py`** and **`tests/test_pipeline_scripts.py`** (11 + 12 = 23 combined)
- Test files that are themselves being fixed — assertions too loose, missing edge cases, etc.
- Signal: Tests written hastily alongside features, then repeatedly tightened during audits.

**`tests/fake_github.py`** (5 changes)
- The test double for GitHub CLI interactions keeps getting stricter (flag registry, state enforcement).
- Signal: The abstraction boundary between real `gh` and fake `gh` was originally too loose.

## Observations

1. **The project is in a fix-dominated phase.** 64% of the last 50 commits are fixes. The feature work (Chunks 1-4) landed on Mar 11-12, and everything since has been audit-driven remediation. This is expected given the ongoing bug-hunter passes, but the volume (33 unique bug IDs resolved) suggests the features shipped with significant gaps.

2. **validate_config.py is the gravitational center.** At 13 touches in 50 commits, it is the most-changed file. It holds the TOML parser, GitHub CLI wrappers, config loading, and a dozen path helpers. This concentration of responsibility means any change to any subsystem likely touches this file.

3. **Line-number indexing is a churn amplifier.** CLAUDE.md and CHEATSHEET.md together account for 23 file changes, most of which are purely mechanical line-number updates. This is a design choice that trades navigation convenience for maintenance cost. Every code edit triggers a doc edit, doubling the surface area for stale references.

4. **Batch fix commits obscure individual change quality.** Commits like "batch resolve P5-05/06/.../40" touch 18 punchlist items in one commit. This makes it hard to bisect regressions and suggests each fix may not have been individually verified.

5. **Test files have nearly as much churn as the code they test.** `test_pipeline_scripts.py` (12 changes) and `test_gh_interactions.py` (11 changes) rival the production code they cover. This suggests the test infrastructure is still maturing.

6. **Mar 13 was an extreme outlier** with 50 commits in one day — all bug-hunter fixes. That velocity suggests automated/assisted fix application rather than careful manual changes. Worth verifying that fixes from that day actually resolve their issues without introducing new ones.

7. **Every script created in Chunks 3-4 (analytics, coverage, traceability, voices, epics, sagas) became a fix magnet.** All six went through multiple rounds of post-creation fixes. This pattern suggests the feature development process may benefit from more thorough initial testing before commit.
