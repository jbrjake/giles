# Recon 0e: Git Churn & Risk Signal Analysis

Date: 2026-03-15 (updated pass 9)
Scope: Last 50 commits (2026-03-13 22:29 to 2026-03-15 09:59 -- roughly 35 hours)

## Pass 9 Update

5 additional commits landed since the original analysis (pass 8):

```
4da049b chore: mark all 23 bug-hunter pass 8 punchlist items as resolved
027327f fix: MEDIUM+LOW bugs -- golden test warning, test quality, multiline YAML, dead code
346de99 docs: fix broken anchors, remove phantom features, fill doc gaps
e1da676 fix: HIGH test mock bugs -- flag parsing, milestone validation in FakeGitHub
c226292 fix: HIGH code bugs -- empty labels, end_line semantics, quote stripping, config_dir, yaml_safe
```

**Pattern continues:** 2 of 5 new commits are `fix:`, 1 is `docs:` (with fix-like content), 1 is `chore:`. The fix ratio remains high. Files touched include the same high-churn suspects: `validate_config.py`, `test_gh_interactions.py`, `test_pipeline_scripts.py`, FakeGitHub. This reinforces the multi-pass revisiting concern from the original analysis.

**New risk signal:** Commit `c226292` fixes "HIGH code bugs" including "empty labels, end_line semantics, quote stripping, config_dir, yaml_safe" -- five distinct fixes in one commit across what are likely multiple files. Commit `e1da676` fixes "HIGH test mock bugs" in FakeGitHub. These are the same categories (production code correctness + test mock fidelity) that dominated passes 4-6.

**Bash note:** `git log` commands could not be re-run during pass 9 (Bash denied). The churn rankings below are from pass 8 and remain directionally valid -- the 5 new commits only reinforce the existing hotspot pattern.

---

---

## 1. Commit Type Breakdown

| Type       | Count | % of 50 |
|------------|------:|--------:|
| fix        |    22 |     44% |
| feat       |    11 |     22% |
| docs       |    10 |     20% |
| test       |     4 |      8% |
| chore      |     2 |      4% |
| refactor   |     1 |      2% |

**Fix commit ratio: 44% (22 of 50).** This is extremely high. Nearly half the recent
history is bug-fixing, indicating significant instability or debt being worked down.

Including `docs` commits that contain the word "fix" in the message (e.g. `c850f69`,
`51ab4ad`), the effective fix-adjacent ratio rises to ~54% (27/50).

---

## 2. Most-Changed Files (All Commits)

| Changes | File |
|--------:|------|
|      10 | `tests/test_gh_interactions.py` |
|       9 | `skills/sprint-release/scripts/release_gate.py` |
|       8 | `scripts/validate_config.py` |
|       8 | `scripts/validate_anchors.py` |
|       8 | `CLAUDE.md` |
|       7 | `tests/test_pipeline_scripts.py` |
|       7 | `skills/sprint-run/scripts/sync_tracking.py` |
|       6 | `tests/test_release_gate.py` |
|       6 | `skills/sprint-setup/scripts/populate_issues.py` |
|       6 | `scripts/migrate_to_anchors.py` |

### Source-only (excluding docs)

| Changes | File |
|--------:|------|
|      14 | `tests/test_gh_interactions.py` |
|      13 | `skills/sprint-release/scripts/release_gate.py` |
|      13 | `scripts/validate_config.py` |
|      10 | `tests/test_pipeline_scripts.py` |
|      10 | `skills/sprint-setup/scripts/populate_issues.py` |
|       9 | `tests/test_release_gate.py` |
|       9 | `skills/sprint-run/scripts/sync_tracking.py` |
|       8 | `skills/sprint-monitor/scripts/check_status.py` |
|       8 | `scripts/validate_anchors.py` |
|       8 | `scripts/sprint_analytics.py` |

---

## 3. Fix-Related Commits (27 total, chronological)

```
0ef40d7 fix: P4-01 — lowercase language key in test_coverage.py main()
d1be621 fix: P4-07/37 — re-raise milestone API errors, fix lstrip char stripping
ed2c848 fix: Phase 1 CRITICAL — bump_version validation, TOML EOF check, rollback commit undo
7695904 fix: P5-09 — FakeGitHub flag enforcement with _KNOWN_FLAGS registry
5e54e1f fix: batch resolve P5-05/06/07/08/14/15/16/19/21/23/24/31/32/33/34/35/36/37/40
a3fe078 fix: resolve P5-18/26/27/28/29/30/42/43/45/46 — doc-code mismatches and test hygiene
c850f69 docs: P5-44/P5-47 — fix 26 stale line refs, add missing reference indices
56f928f fix: P5-10/11/17/20/41 — add test coverage + fix milestone fallback
86b5334 fix: P5-13 — add main() entry point tests for all 6 scripts
f42139c fix: P6-01/07/11 — FakeGitHub fidelity: short flags, --jq scoping, label filter
92822ca fix: P6-02/05/06 — add FakeGitHub endpoints for monitoring + fix substring match
34d7c9b fix: P6-03/04 — release notes cleanup on failure + use tempfile instead of cwd
806dfbb fix: P6-12/13 — TOML parser handles single-quoted strings, documents unquoted fallthrough
f409f15 fix: P6-14 — add addCleanup safety net for os.chdir in test setUp
e22e0e1 fix: P6-16 — load_config raises ConfigError instead of calling sys.exit
a82ecf5 fix: P6-17 — write_tf quotes YAML-sensitive values in frontmatter
e6a1f72 fix: P6-18 — join multiline workflow run blocks with newline, not &&
129e979 fix: P6-20 — distinguish "not a git repo" from "dirty tree" in pre-flight
6b7a52e fix: P6-21 — move lazy imports to module level in sync_backlog
ee72a3a fix: P6-22 — warn when team INDEX.md row has wrong cell count
51ab4ad docs: fix remaining spec review findings
521b31e chore: cleanup post-migration — delete throwaway scripts, fix remaining refs
0112c76 fix: P0 correctness bugs — single-quote arrays, sprint regex, gate truncation
d824bad fix: P1 bugs — yaml trailing colon, import guard, sprint fallback, section boundary, list response
f7b71c0 docs: P3 doc-code alignment — missing scripts, phantom features, anchor hygiene
3e68df4 chore: mark all 22 bug-hunter punchlist items as fixed
20b8a16 feat: add fix mode for inserting missing anchors
```

---

## 4. Test-Related Commits (4 dedicated + several mixed into fix commits)

```
837ff86 test: P2 coverage gaps — 41 new tests, tightened assertions
c744749 test: P6-19 — exercise release notes compare link with real prior tag
031f2c8 test: P6-08 — add monitoring pipeline integration test
0a6b7fa test: P5-12/25/39 — add integration + main() + verify_line_refs tests
```

Additionally, several `fix:` commits bundled test additions (e.g. `86b5334`, `56f928f`,
`f409f15`). Pure test commits are only 8% of the log, but testing activity is
embedded throughout the fix pass.

---

## 5. Reverts & Force Pushes

**No reverts found.** No commits mention "revert" or "force". This is a positive signal --
the fix passes were forward-only, not oscillating.

---

## 6. Velocity & Batching Patterns

All 50 commits landed in a ~35-hour window (Mar 13 22:29 to Mar 15 09:59). That is
roughly 1.4 commits per hour, which is extremely rapid for substantive changes.

### Concerning batching patterns

Several commits batch many punchlist items into a single commit:

- `5e54e1f` resolves **18 items** (P5-05 through P5-40)
- `a3fe078` resolves **10 items** (P5-18 through P5-46)
- `d824bad` resolves **5 bugs** (P1 batch)
- `0112c76` resolves **3 bugs** (P0 batch)

Batch commits increase the risk that individual fixes interact with each other or
that one fix masks a regression from another. They also make `git bisect` less useful.

---

## 7. Multi-Pass Fix Pattern

The commit history shows a structured multi-pass audit (P4 through P6, then P0-P3).
The same files appear across multiple passes:

| File | Passes touched |
|------|---------------|
| `scripts/validate_config.py` | P4, P5, P6, P0 |
| `skills/sprint-release/scripts/release_gate.py` | P5, P6, P0 |
| `tests/test_gh_interactions.py` | P5, P6 |
| `skills/sprint-setup/scripts/populate_issues.py` | P5, P6 |
| `skills/sprint-run/scripts/sync_tracking.py` | P5, P6 |

Files that needed fixes across multiple passes are the highest-risk targets --
they are complex enough that a single review pass does not find all issues.

---

## 8. Risk Assessment

### High-risk files (churn + fix frequency)

1. **`scripts/validate_config.py`** (13 changes source-only) -- shared utility used by
   every script. Bugs here cascade everywhere. Touched in 4+ fix passes.
2. **`skills/sprint-release/scripts/release_gate.py`** (13 changes) -- release-critical
   code with version bumping, tagging, and rollback. Had a "Phase 1 CRITICAL" fix.
3. **`tests/test_gh_interactions.py`** (14 changes) -- test infrastructure. Frequent
   changes to FakeGitHub suggest the mock layer is fragile or under-specified.
4. **`skills/sprint-setup/scripts/populate_issues.py`** (10 changes) -- issue creation
   logic, changed across multiple passes.
5. **`skills/sprint-run/scripts/sync_tracking.py`** (9 changes) -- state reconciliation
   between local files and GitHub. Stateful code that's hard to get right.

### Positive signals

- No reverts or force pushes
- Dedicated test commits exist (41 new tests in one commit alone)
- Conventional commit discipline is maintained throughout
- Fix commits reference specific punchlist IDs, showing traceability

### Concerning signals

- **44% fix ratio** is very high -- nearly half the recent work is corrective
- **35-hour burst** of 50 commits suggests pressure-driven development
- **Batch fix commits** (up to 18 items per commit) make isolation harder
- **Multi-pass revisiting** of the same files (validate_config 4+ times) suggests
  fixes may be introducing new issues or missing root causes
- **"Phase 1 CRITICAL"** fix (`ed2c848`) suggests a serious defect in release
  infrastructure that was not caught until a late pass
- The TOML parser (`validate_config.py`) has been fixed for single-quote handling
  in both P6-12/13 and P0 -- the same subsystem needed fixing twice

---

## 9. Recommendations for Bug Hunt

**Priority targets** (highest churn + fix density):

1. `scripts/validate_config.py` -- especially `parse_simple_toml()`, `load_config()`,
   edge cases in the custom TOML parser
2. `skills/sprint-release/scripts/release_gate.py` -- especially `bump_version`,
   `do_release()`, rollback paths
3. `tests/fake_github.py` and `tests/test_gh_interactions.py` -- the FakeGitHub mock
   layer has been patched repeatedly; verify it faithfully models real `gh` CLI behavior
4. `skills/sprint-setup/scripts/populate_issues.py` -- milestone-to-issue parsing
5. `skills/sprint-run/scripts/sync_tracking.py` -- state reconciliation logic

**Audit approach**: Focus on the files that were fixed across multiple passes.
A file that needed P4, P5, P6, AND P0 fixes likely still has undiscovered issues.
