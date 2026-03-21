# 0e - Git Churn Analysis

**Date:** 2026-03-15
**Pass:** 12

## Method

Analyzed most recent 50 and 100 commits on `main` via file-change frequency. Cross-referenced against prior bug-hunter passes (3-11) to identify chronic hotspots.

```
git log --pretty=format: --name-only -50 | sort | uniq -c | sort -rn | head -30
git log --pretty=format: --name-only -100 | sort | uniq -c | sort -rn | head -30
```

## Recent 50 Commits

```
5c323d6 chore: update bug-hunter status with hypothesis test results (634 tests)
46dd8b6 feat(tests): add hypothesis property-based tests for regex/parsing hotspots
09dfbb4 feat(tests): implement real jq evaluation in FakeGitHub
7f0112e fix: migrate 2 remaining json.loads bypass sites to gh_json()
930e86a chore: mark all 42 bug-hunter pass 11 items as resolved
c94c9a5 feat(tests): add call-args audit helper to prevent mock-abuse (BH-P11-201)
d454e29 feat(tests): add FakeGitHub strict mode for unimplemented flag detection (BH-P11-200)
3303ce6 feat(tests): add main() coverage gate for all scripts (BH-P11-202)
bf977aa chore: add 3 structural prevention items from trend analysis (BH-P11-200/201/202)
a04b50a chore: mark all 39 bug-hunter pass 11 punchlist items as resolved
dfe0734 fix: final 5 items — FakeGitHub fidelity, teardown tests, MockProject dedup
81b447f fix: 11 remaining items — idempotency tests, format injection, git check, docs
52f5cbb fix: 6 code bugs — rollback warnings, PR selection, yaml quoting, regex, blockquotes
5a3956d test: add call_args assertions and main() integration tests
75abbdb fix: migrate 3 call sites from gh()+json.loads() to gh_json()
80242dd fix: batch 1 quick wins — 7 bug-hunter P11 items
749c77c chore: mark all 28 bug-hunter pass 10 punchlist items as resolved
d78e25e test: improve test fidelity — review data path, non-matching PRs, gate coverage
ecc0098 docs: fix doc drift — CHEATSHEET anchors, README column order, KANBAN_STATES type
9dd89c2 test: add 26 regression tests for BH-series bug fixes
124f1b8 fix: resolve 20 code bugs across all scripts (BH-001 through BH-025)
101131d test: add coverage for shared helpers, TOML edge cases, jq documentation
f431548 chore: mark all 27 bug-hunter pass 9 punchlist items as resolved
962fb35 docs: fix doc-code drift — paths, descriptions, missing entries
c964a30 fix: test quality — remove tautologies, deduplicate, add adversarial coverage
960b43c fix: code bugs — regex boundaries, input validation, shared helpers, logic fixes
4da049b chore: mark all 23 bug-hunter pass 8 punchlist items as resolved
027327f fix: MEDIUM+LOW bugs — golden test warning, test quality, multiline YAML, dead code
346de99 docs: fix broken anchors, remove phantom features, fill doc gaps
e1da676 fix: HIGH test mock bugs — flag parsing, milestone validation in FakeGitHub
c226292 fix: HIGH code bugs — empty labels, end_line semantics, quote stripping, config_dir
9b15ac3 fix: P0 critical bugs — anchor regex blind spots, gh() timeout crash
3e68df4 chore: mark all 22 bug-hunter punchlist items as fixed
f7b71c0 docs: P3 doc-code alignment — missing scripts, phantom features, anchor hygiene
837ff86 test: P2 coverage gaps — 41 new tests, tightened assertions
d824bad fix: P1 bugs — yaml trailing colon, import guard, sprint fallback, section boundary
0112c76 fix: P0 correctness bugs — single-quote arrays, sprint regex, gate truncation
521b31e chore: cleanup post-migration — delete throwaway scripts, fix remaining refs
5cc4108 feat: execute greppable anchor migration across all files
e945e0a feat: add migration CLI with dry-run and apply modes
0f97313 feat: add CHEATSHEET.md table rewriter for migration
fc38c17 feat: add CLAUDE.md doc-side rewriter for migration
83de91c feat: add source-side anchor insertion for migration
9874b25 feat: add CLI entry point for validate_anchors
20b8a16 feat: add fix mode for inserting missing anchors
6b918d1 feat: add check mode orchestrator for anchor validation
c2faf0d feat: add anchor reference scanner
4b1e5e4 feat: add anchor definition scanner
8d124a1 feat: add namespace map and resolver for anchor validation
ab2016d docs: implementation plan for greppable anchor migration
```

## Top 30 Most-Changed Files (last 100 commits)

| Rank | Changes (100) | Changes (50) | File | Category |
|------|---------------|--------------|------|----------|
| 1 | 27 | 15 | `tests/test_gh_interactions.py` | Test |
| 2 | 19 | 8 | `scripts/validate_config.py` | Script (shared) |
| 3 | 16 | 6 | `skills/sprint-release/scripts/release_gate.py` | Script |
| 4 | 15 | 5 | `tests/test_release_gate.py` | Test |
| 5 | 15 | 6 | `skills/sprint-setup/scripts/populate_issues.py` | Script |
| 6 | 15 | 8 | `BUG-HUNTER-STATUS.md` | Chore |
| 7 | 14 | 5 | `tests/test_pipeline_scripts.py` | Test |
| 8 | 14 | 7 | `skills/sprint-run/scripts/sync_tracking.py` | Script |
| 9 | 14 | 6 | `scripts/sprint_analytics.py` | Script |
| 10 | 14 | 5 | `CLAUDE.md` | Docs (index) |
| 11 | 13 | 6 | `skills/sprint-monitor/scripts/check_status.py` | Script |
| 12 | 13 | 6 | `CHEATSHEET.md` | Docs (index) |
| 13 | 12 | 7 | `tests/fake_github.py` | Test infra |
| 14 | 10 | 7 | `BUG-HUNTER-PUNCHLIST.md` | Chore |
| 15 | 9 | 3 | `tests/test_lifecycle.py` | Test |
| 16 | 9 | 4 | `skills/sprint-run/scripts/update_burndown.py` | Script |
| 17 | 9 | 9 | `scripts/validate_anchors.py` | Script |
| 18 | 9 | 4 | `scripts/sprint_init.py` | Script |
| 19 | 8 | 3 | `skills/sprint-monitor/SKILL.md` | Skill entry |
| 20 | 7 | 5 | `tests/test_verify_fixes.py` | Test |
| 21 | 7 | 3 | `scripts/test_coverage.py` | Script |
| 22 | 7 | 4 | `scripts/manage_sagas.py` | Script |
| 23 | 6 | 3 | `scripts/sync_backlog.py` | Script |
| 24 | 6 | 6 | `scripts/migrate_to_anchors.py` | Script (deleted) |
| 25 | 6 | 4 | `scripts/manage_epics.py` | Script |
| 26 | 5 | 5 | `tests/test_validate_anchors.py` | Test |
| 27 | 5 | 5 | `tests/test_migrate_anchors.py` | Test (deleted) |
| 28 | 5 | 5 | `tests/test_hexwise_setup.py` | Test |
| 29 | 5 | 5 | `tests/test_golden_run.py` | Test |
| 30 | 5 | 4 | `README.md` | Docs |

## Hotspots (5+ changes in last 50 commits)

### Tier 1: Extreme churn (10+ changes in 50 commits)

| File | Changes (50) | Changes (100) | Pattern |
|------|-------------|---------------|---------|
| `tests/test_gh_interactions.py` | 15 | 27 | Most-changed file overall. Test additions, mock-abuse fixes, dedup, assertion tightening |
| `scripts/validate_config.py` | 8 | 19 | Shared utility hub. TOML parser fixes, helper additions, import cleanup |
| `BUG-HUNTER-STATUS.md` | 8 | 15 | Chore tracking file -- not code |
| `BUG-HUNTER-PUNCHLIST.md` | 7 | 10 | Chore tracking file -- not code |
| `tests/fake_github.py` | 7 | 12 | Test double improvements: strict mode, jq evaluation, flag parsing |

### Tier 2: High churn (5-9 changes in 50 commits)

| File | Changes (50) | Changes (100) | Pattern |
|------|-------------|---------------|---------|
| `scripts/validate_anchors.py` | 9 | 9 | All changes in one burst (anchor migration feature) |
| `skills/sprint-run/scripts/sync_tracking.py` | 7 | 14 | State reconciliation fixes, unused imports |
| `skills/sprint-setup/scripts/populate_issues.py` | 6 | 15 | Milestone parsing, regex, silent error handling |
| `skills/sprint-monitor/scripts/check_status.py` | 6 | 13 | CI check logic, drift detection, dead code |
| `CHEATSHEET.md` | 6 | 13 | Index file -- updated whenever code changes |
| `CLAUDE.md` | 5 | 14 | Index file -- updated whenever code changes |
| `scripts/sprint_analytics.py` | 6 | 14 | Search query quoting, PR truncation, review data |
| `skills/sprint-release/scripts/release_gate.py` | 6 | 16 | Rollback logic, version bumping, gate validation |
| `tests/test_pipeline_scripts.py` | 5 | 14 | Coverage additions, assertion fixes |
| `tests/test_release_gate.py` | 5 | 15 | Gate coverage, main() integration |
| `tests/test_verify_fixes.py` | 5 | 7 | Regression tests for bug-hunter fixes |
| `tests/test_validate_anchors.py` | 5 | 5 | Anchor validation tests |
| `tests/test_golden_run.py` | 5 | 5 | Golden recording test adjustments |
| `tests/test_hexwise_setup.py` | 5 | 5 | Integration test adjustments |

## Commit Pattern Analysis

All 50 recent commits fall into these categories:

| Type | Count | Notes |
|------|-------|-------|
| `fix:` | ~18 | Bug-hunter batch fixes across passes 8-11 |
| `feat(tests):` | ~6 | Test infrastructure: hypothesis tests, FakeGitHub strict mode, call-args audit |
| `test:` | ~5 | Regression tests, coverage expansion |
| `chore:` | ~8 | Punchlist resolution markers |
| `docs:` | ~4 | Doc drift fixes, anchor hygiene |
| `feat:` | ~9 | Anchor migration feature (all in one burst) |

**Zero product-feature commits in the last 50 commits.** The entire window is audit/fix/test work plus the validate_anchors tooling feature.

## Recurring Fix Themes (across all bug-hunter passes)

1. **Regex over/under-matching** (8+ instances): `extract_sp`, `_first_error`, VOICE_PATTERN, anchor regex, story ID detection. Regexes written for happy paths break on adversarial inputs. Now partially mitigated by hypothesis property-based tests (26 `@given` tests added in pass 11).

2. **FakeGitHub fidelity gaps** (6+ instances): `--search` ignored, `--jq` not applied, `--flag=value` syntax not parsed, missing endpoints. Now partially mitigated by strict mode (pass 11) and real jq evaluation.

3. **TOML parser edge cases** (5+ instances): single-quote arrays, nested arrays, hyphenated keys, multiline comments, escaped backslashes. Custom parser keeps hitting TOML spec corners.

4. **Doc-code drift** (7+ instances): phantom features, wrong paths, stale line numbers. CLAUDE.md + CHEATSHEET.md together account for 27 changes in 100 commits -- mostly fix-the-fix cycles.

5. **Unused imports / dead code** (11 instances found this pass): imports added during development and never cleaned up. Accumulating across refactoring cycles.

## Files That Have Been Repeatedly Bug-Fixed

### Chronic hotspots (fixed in 5+ separate bug-hunter passes)

| File | Passes fixed in | Total mods (100) | Bug categories |
|------|----------------|------------------|----------------|
| `scripts/validate_config.py` | 3-11 (all) | 19 | TOML parser, regex, error handling, shared helpers |
| `skills/sprint-release/scripts/release_gate.py` | 3, 5-11 | 16 | Rollback logic, version bumping, gate validation, push semantics |
| `skills/sprint-setup/scripts/populate_issues.py` | 3-6, 9-11 | 15 | Milestone parsing, regex, silent error swallowing |
| `skills/sprint-run/scripts/sync_tracking.py` | 3-6, 9-11 | 14 | State reconciliation, linked PR detection, YAML frontmatter |
| `skills/sprint-monitor/scripts/check_status.py` | 5-11 | 13 | CI check vacuous truth, error keyword matching, drift detection |
| `scripts/sprint_analytics.py` | 5-11 | 14 | Search query quoting, PR truncation, review round data path |
| `tests/fake_github.py` | 5-11 | 12 | Flag parsing, endpoint fidelity, jq handling, strict mode |
| `tests/test_gh_interactions.py` | 3-11 (all) | 27 | Mock abuse, duplicate tests, tautological assertions, new coverage |

## Key Takeaways

1. **`tests/test_gh_interactions.py` is the most-churned file** (27 changes in 100 commits). It has more modifications than any production script. This is partly because it is the catch-all test file for all GitHub-facing scripts, and partly because prior passes kept finding test quality issues in it.

2. **`scripts/validate_config.py` remains the highest-risk production file** (19 changes). As the shared utility hub imported by every script, bugs here cascade. The TOML parser and `gh_json()` helper are the most fragile subsystems.

3. **Index documentation (`CLAUDE.md` + `CHEATSHEET.md`) amplifies churn.** Every code fix triggers a doc update, doubling surface area. 27 combined changes in 100 commits.

4. **The codebase is stabilizing.** Pass 11 shifted from pure bug-fixing to structural prevention (hypothesis tests, strict mode, call-args audit). The ratio of `feat(tests):` to `fix:` commits is improving.

5. **Anchor migration (`validate_anchors.py`) was a burst of churn.** 9 changes in 50 commits, but all during a single feature build. This is healthy feature-development churn, not bug-fix churn.
