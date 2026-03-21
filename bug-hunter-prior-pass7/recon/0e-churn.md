# Phase 0e: Code Churn Analysis

Generated: 2026-03-15

---

## 1. Top 20 Most-Changed Files (Last 50 Commits)

| Changes | File |
|---------|------|
| 10 | `tests/test_gh_interactions.py` |
| 9 | `scripts/validate_config.py` |
| 9 | `CLAUDE.md` |
| 8 | `skills/sprint-release/scripts/release_gate.py` |
| 7 | `tests/test_release_gate.py` |
| 7 | `tests/test_pipeline_scripts.py` |
| 7 | `skills/sprint-setup/scripts/populate_issues.py` |
| 7 | `skills/sprint-run/scripts/sync_tracking.py` |
| 7 | `scripts/validate_anchors.py` |
| 6 | `scripts/migrate_to_anchors.py` |
| 6 | `CHEATSHEET.md` |
| 5 | `tests/test_validate_anchors.py` |
| 5 | `tests/test_migrate_anchors.py` |
| 5 | `skills/sprint-monitor/SKILL.md` |
| 5 | `skills/sprint-monitor/scripts/check_status.py` |
| 5 | `scripts/sprint_init.py` |
| 5 | `scripts/sprint_analytics.py` |
| 5 | `BUG-HUNTER-STATUS.md` |
| 4 | `tests/test_lifecycle.py` |
| 4 | `tests/fake_github.py` |

### Analysis

**Highest-risk production files by churn:**

- **`validate_config.py` (9 changes):** The shared foundation script. Every other script imports from it. High churn here means downstream consumers could be affected by subtle interface changes. This is the single most important file to audit thoroughly.
- **`release_gate.py` (8 changes):** Release gating logic has been heavily reworked. Release-path bugs tend to be high-severity since they affect shipped artifacts.
- **`populate_issues.py` (7 changes):** GitHub issue creation. Repeated changes suggest the parsing/mapping logic was hard to get right.
- **`sync_tracking.py` (7 changes):** Local-to-GitHub reconciliation. Churn here suggests edge cases in state synchronization.
- **`check_status.py` (5 changes):** Monitoring script. Multiple fixes indicate the GitHub API surface is tricky to get right.

**Test file churn tracks production churn** (good sign): `test_gh_interactions.py` leads at 10 changes, and `test_release_gate.py` / `test_pipeline_scripts.py` are both at 7. This means bugs are being caught and test coverage is expanding alongside fixes.

**Documentation churn (`CLAUDE.md` at 9, `CHEATSHEET.md` at 6):** Line-number references need constant updating. This is a maintenance burden and a source of stale-reference bugs. The recent anchor migration (validate_anchors.py, migrate_to_anchors.py) is directly addressing this problem.

---

## 2. Commit Frequency by Author (Last 50 Commits)

| Commits | Author |
|---------|--------|
| 50 | Jon Rubin |

### Analysis

Single-author project. All changes flow through one person, which means:
- No merge-conflict churn or integration bugs.
- No review bottleneck from multiple contributors.
- But also no second pair of eyes on changes — the bug-hunter audit itself is filling this gap.

---

## 3. Files Changed in Last 10 Commits (Recent Activity)

```
521b31e chore: cleanup post-migration — delete throwaway scripts, fix remaining refs
  CHEATSHEET.md, CLAUDE.md, Makefile
  scripts/migrate_to_anchors.py, scripts/verify_line_refs.py
  skills/sprint-run/references/kanban-protocol.md
  skills/sprint-run/references/tracking-formats.md
  tests/test_migrate_anchors.py, tests/test_pipeline_scripts.py

5cc4108 feat: execute greppable anchor migration across all files
  39 files (broad migration sweep)

e945e0a feat: add migration CLI with dry-run and apply modes
  scripts/migrate_to_anchors.py

0f97313 feat: add CHEATSHEET.md table rewriter for migration
  scripts/migrate_to_anchors.py, tests/test_migrate_anchors.py

fc38c17 feat: add CLAUDE.md doc-side rewriter for migration
  scripts/migrate_to_anchors.py, tests/test_migrate_anchors.py

83de91c feat: add source-side anchor insertion for migration
  scripts/migrate_to_anchors.py, tests/test_migrate_anchors.py

9874b25 feat: add CLI entry point for validate_anchors
  scripts/validate_anchors.py

20b8a16 feat: add fix mode for inserting missing anchors
  scripts/validate_anchors.py, tests/test_validate_anchors.py

6b918d1 feat: add check mode orchestrator for anchor validation
  scripts/validate_anchors.py, tests/test_validate_anchors.py

c2faf0d feat: add anchor reference scanner
  scripts/validate_anchors.py, tests/test_validate_anchors.py
```

### Analysis

The last 10 commits are entirely focused on the **greppable anchor migration** — replacing fragile line-number references with stable `§section.name` anchors. This is infrastructure work, not feature development. The migration touched 39 files in one commit, which is a risk factor for introduced regressions in those files (though the changes are mechanical find-and-replace).

**Risk areas from recent activity:**
- `scripts/migrate_to_anchors.py` — brand new script, 5 commits of incremental build-up. Likely well-tested since it was built test-first, but the CLI/apply mode (e945e0a) was added in a single commit without tests in that same commit.
- The 39-file sweep (5cc4108) — any file touched in that commit could have anchor insertion artifacts or broken formatting.

---

## 4. Fix/Bug/Broken/Revert Commits (Last 50)

| Commit | Description |
|--------|-------------|
| `521b31e` | chore: cleanup post-migration — delete throwaway scripts, fix remaining refs |
| `51ab4ad` | docs: fix remaining spec review findings |
| `ee72a3a` | fix: P6-22 — warn when team INDEX.md row has wrong cell count |
| `6b7a52e` | fix: P6-21 — move lazy imports to module level in sync_backlog |
| `129e979` | fix: P6-20 — distinguish "not a git repo" from "dirty tree" in pre-flight |
| `e6a1f72` | fix: P6-18 — join multiline workflow run blocks with newline, not && |
| `a82ecf5` | fix: P6-17 — write_tf quotes YAML-sensitive values in frontmatter |
| `e22e0e1` | fix: P6-16 — load_config raises ConfigError instead of calling sys.exit |
| `f409f15` | fix: P6-14 — add addCleanup safety net for os.chdir in test setUp |
| `806dfbb` | fix: P6-12/13 — TOML parser handles single-quoted strings, documents unquoted fallthrough |
| `0d8445b` | fix: P6-09/10/15 — remove phantom features and clarify doc-code alignment |
| `34d7c9b` | fix: P6-03/04 — release notes cleanup on failure + use tempfile instead of cwd |
| `92822ca` | fix: P6-02/05/06 — add FakeGitHub endpoints for monitoring + fix substring match |
| `f42139c` | fix: P6-01/07/11 — FakeGitHub fidelity: short flags, --jq scoping, label filter |
| `86b5334` | fix: P5-13 — add main() entry point tests for all 6 scripts |
| `56f928f` | fix: P5-10/11/17/20/41 — add test coverage + fix milestone fallback |
| `c850f69` | docs: P5-44/P5-47 — fix 26 stale line refs, add missing reference indices |
| `a3fe078` | fix: resolve P5-18/26/27/28/29/30/42/43/45/46 — doc-code mismatches and test hygiene |
| `5e54e1f` | fix: batch resolve P5-05/06/07/08/14/15/16/19/21/23/24/31/32/33/34/35/36/37/40 |
| `7695904` | fix: P5-09 — FakeGitHub flag enforcement with _KNOWN_FLAGS registry |
| `ed2c848` | fix: Phase 1 CRITICAL — bump_version validation, TOML EOF check, rollback commit undo |
| `d1be621` | fix: P4-07/37 — re-raise milestone API errors, fix lstrip char stripping |
| `0ef40d7` | fix: P4-01 — lowercase language key in test_coverage.py main() |
| `63293e7` | fix: P4-17/20/27/32 — doc phantom flags, test assertions, tracking states |
| `afcebf6` | fix: BH4-01 through BH4-16 — fourth-audit code and test fixes |
| `692d28b` | fix: BH3-01 through BH3-10 — resolve all third-audit findings |

### Analysis

**26 out of 50 commits (52%) are fix commits.** This is expected given the project is in an active bug-hunting audit phase (Passes 3-6 are visible), but it reveals important patterns:

**Recurring fix categories:**
1. **FakeGitHub test infra (4 commits):** P6-01/02/05/06/07/11, P5-09. The test mock for `gh` CLI keeps needing fixes for flag handling, --jq scoping, endpoint coverage. This suggests the mock is fragile and doesn't fully model the real `gh` behavior. High risk that tests pass with FakeGitHub but would fail against real GitHub.
2. **Doc-code mismatches (5+ commits):** P5-44/47, P5-18/26-30/42-46, P6-09/10/15. Phantom features documented but not implemented, stale line refs. The anchor migration is addressing the line-ref problem, but phantom features are a deeper design issue.
3. **TOML parser edge cases (2 commits):** P6-12/13, P4-07. Single-quoted strings, unquoted fallthrough, lstrip bugs. The custom parser keeps revealing gaps — consider whether it needs fuzz testing.
4. **Release pipeline (2 commits):** P6-03/04, Phase 1 CRITICAL. Tempfile handling, rollback logic, bump_version validation. Release path bugs are high-severity.
5. **Config/validation (3 commits):** P6-16 (sys.exit vs raise), P6-20 (git repo detection), P4-01 (case sensitivity). The shared config layer keeps getting patched.

**No reverts found.** Good — changes are going forward, not being undone.

---

## 5. Large Commits (File Count and Churn Volume)

| Commit | Files | Insertions | Deletions | Description |
|--------|-------|------------|-----------|-------------|
| `5cc4108` | 39 | 695 | 372 | Anchor migration across all files |
| `afcebf6` | 15 | 258 | 142 | BH4-01 through BH4-16 fixes |
| `e22e0e1` | 13 | 124 | 29 | P6-16 load_config refactor |
| `692d28b` | 12 | 512 | 103 | BH3-01 through BH3-10 fixes |
| `5e54e1f` | 12 | 133 | 37 | Batch resolve 19 P5 items |
| `0d8445b` | 10 | 8 | 11 | P6-09/10/15 phantom removal |
| `521b31e` | 9 | 23 | 805 | Post-migration cleanup |
| `a3fe078` | 8 | 21 | 11 | P5-18/26-30/42-46 fixes |
| `ab2016d` | 1 | 1651 | 0 | Implementation plan doc (low risk) |

### Analysis

**High-risk large commits:**

1. **`5cc4108` (39 files, +695/-372):** The anchor migration sweep. Mechanical changes but touching nearly every file in the project. Any formatting or regex errors in the migration script would propagate across all 39 files. Worth spot-checking a sample of affected files.

2. **`afcebf6` (15 files, +258/-142) and `692d28b` (12 files, +512/-103):** Batch audit fix commits. These bundle many unrelated fixes into one commit, making it harder to bisect if something breaks. The changes are individually small but the blast radius is wide.

3. **`e22e0e1` (13 files, +124/-29):** The `load_config` refactor from sys.exit to ConfigError. This changed the error-handling contract across 13 files — any caller that wasn't updated would break silently (catching SystemExit instead of ConfigError, or not catching at all).

4. **`521b31e` (9 files, -805 lines):** Large deletion commit (cleanup). Deletions are generally safe, but verify nothing was deleted that's still imported or referenced.

---

## Summary: Risk Heatmap

### Tier 1 — Highest Risk (audit these first)
| File | Why |
|------|-----|
| `scripts/validate_config.py` | 9 changes, shared foundation, TOML parser edge cases, config contract changes |
| `skills/sprint-release/scripts/release_gate.py` | 8 changes, release-path severity, CRITICAL fix in history |
| `tests/fake_github.py` | 4 changes, 4 fix commits about its fidelity — if the mock is wrong, tests give false confidence |

### Tier 2 — Elevated Risk
| File | Why |
|------|-----|
| `skills/sprint-setup/scripts/populate_issues.py` | 7 changes, GitHub API interaction, milestone mapping bugs |
| `skills/sprint-run/scripts/sync_tracking.py` | 7 changes, state reconciliation logic |
| `skills/sprint-monitor/scripts/check_status.py` | 5 changes, monitoring edge cases |
| `scripts/sprint_init.py` | 5 changes, project scanner and config generation |

### Tier 3 — Watch List
| File | Why |
|------|-----|
| `scripts/validate_anchors.py` | 7 changes but all new code (built incrementally with tests) |
| `scripts/migrate_to_anchors.py` | 6 changes, new tooling, 39-file blast radius |
| `scripts/sprint_analytics.py` | 5 changes, metrics calculations |

### Key Patterns

1. **Fix-heavy history (52% fix commits):** The codebase is in hardening mode. Most of the low-hanging bugs have been caught by Passes 3-6, but the recurring categories (FakeGitHub fidelity, TOML parsing, doc-code drift) suggest systemic issues in those areas.

2. **Batch fix commits are hard to bisect:** Multiple audit items bundled per commit. If a regression surfaces, `git bisect` will point to a commit containing 5-16 unrelated changes.

3. **The custom TOML parser is a recurring source of bugs:** Two separate audit passes found edge cases. It would benefit from property-based or fuzz testing.

4. **FakeGitHub keeps needing patches:** The mock doesn't faithfully reproduce `gh` CLI behavior. Each audit pass finds new gaps. Consider whether a table-driven approach or recording/replaying real `gh` output would be more reliable.

5. **Documentation maintenance is expensive:** CLAUDE.md and CHEATSHEET.md are in the top 20 by churn, and stale-reference fixes appear in multiple audit passes. The anchor migration should reduce this, but only if the anchors themselves are kept in sync.
