# Git Churn Analysis

Repository: 244 total commits. Analysis based on last 50 and 100 commits.

## Commit Type Distribution (all 244 commits)

| Type | Count | % |
|------|------:|--:|
| fix | 78 | 32% |
| feat | 78 | 32% |
| docs | 39 | 16% |
| test | 17 | 7% |
| chore | 14 | 6% |
| refactor | 9 | 4% |
| other | 9 | 4% |

**Nearly one-third of all commits are fixes.** The ratio of fix to feat is 1:1 across the full history. In the last 100 commits, fixes dominate at 47/100 (combining `fix:` and `fix(tests):`).

## Top 20 Most-Changed Files (Last 50 Commits)

| Touches | File | Lines | Category |
|--------:|------|------:|----------|
| 19 | `tests/test_gh_interactions.py` | 3103 | test |
| 10 | `skills/sprint-run/scripts/sync_tracking.py` | 377 | production |
| 9 | `tests/fake_github.py` | 920 | test infra |
| 9 | `skills/sprint-setup/scripts/populate_issues.py` | 460 | production |
| 9 | `skills/sprint-release/scripts/release_gate.py` | 731 | production |
| 9 | `scripts/validate_config.py` | 885 | production |
| 8 | `tests/test_release_gate.py` | 1426 | test |
| 8 | `BUG-HUNTER-STATUS.md` | -- | tracking |
| 8 | `BUG-HUNTER-PUNCHLIST.md` | -- | tracking |
| 7 | `tests/test_verify_fixes.py` | 1082 | test |
| 7 | `skills/sprint-run/scripts/update_burndown.py` | 239 | production |
| 7 | `skills/sprint-monitor/scripts/check_status.py` | 439 | production |
| 7 | `scripts/sprint_analytics.py` | 282 | production |
| 6 | `CHEATSHEET.md` | -- | docs |
| 5 | `tests/test_pipeline_scripts.py` | 1511 | test |
| 5 | `scripts/sprint_init.py` | 975 | production |
| 5 | `scripts/manage_sagas.py` | 308 | production |
| 5 | `scripts/manage_epics.py` | 414 | production |
| 5 | `CLAUDE.md` | -- | docs |
| 4 | `tests/test_lifecycle.py` | -- | test |

## Top 20 Most-Changed Files (Last 100 Commits)

| Touches | File | Lines | Category |
|--------:|------|------:|----------|
| 30 | `tests/test_gh_interactions.py` | 3103 | test |
| 18 | `skills/sprint-release/scripts/release_gate.py` | 731 | production |
| 18 | `scripts/validate_config.py` | 885 | production |
| 16 | `tests/test_release_gate.py` | 1426 | test |
| 16 | `skills/sprint-run/scripts/sync_tracking.py` | 377 | production |
| 15 | `skills/sprint-setup/scripts/populate_issues.py` | 460 | production |
| 14 | `tests/fake_github.py` | 920 | test infra |
| 14 | `BUG-HUNTER-STATUS.md` | -- | tracking |
| 13 | `CLAUDE.md` | -- | docs |
| 12 | `tests/test_pipeline_scripts.py` | 1511 | test |
| 12 | `scripts/sprint_analytics.py` | 282 | production |
| 12 | `CHEATSHEET.md` | -- | docs |
| 11 | `skills/sprint-monitor/scripts/check_status.py` | 439 | production |
| 11 | `BUG-HUNTER-PUNCHLIST.md` | -- | tracking |
| 10 | `skills/sprint-run/scripts/update_burndown.py` | 239 | production |
| 9 | `tests/test_verify_fixes.py` | 1082 | test |
| 9 | `tests/test_lifecycle.py` | -- | test |
| 9 | `scripts/validate_anchors.py` | -- | production |
| 9 | `scripts/sprint_init.py` | 975 | production |
| 8 | `skills/sprint-monitor/SKILL.md` | -- | docs |

## Recent Commit Message Themes

### Dominant pattern: bug-hunter adversarial review passes
The last ~120 commits are overwhelmingly driven by a repeating "bug-hunter" adversarial audit cycle:
- Pass 4 (BH-series), Pass 5 (P5-series), Pass 6 (P6-series), Pass 7 (unnumbered), Pass 8 (P8-series), Pass 9, Pass 10, Pass 11 (BH-P11-series), Pass 12 (P12-series)
- Each pass follows the same template: audit finds N items, then N/2 to N fix commits, then a "chore: mark all N items resolved" commit
- Pass 11 alone generated 42 items and at least 10 fix commits
- Pass 12 generated 35 items

### Recurring fix categories (from commit messages)
1. **Regex and parsing bugs** — mentioned across passes 4-12 for validate_config, populate_issues, sprint_analytics
2. **TOML parser issues** — single-quote arrays, bracket-in-string, hyphens, escapes, EOF check (at least 4 separate fix commits)
3. **FakeGitHub fidelity** — repeatedly tightened: short flags, --jq scoping, label filter, strict mode, known flags registry, do_release support (8+ commits)
4. **json.loads bypass / gh_json migration** — same anti-pattern fixed in 3 separate commits across different files
5. **YAML quoting / frontmatter issues** — trailing colon, sensitive values, multiline (3+ commits)
6. **Doc-code drift** — stale line references in CLAUDE.md/CHEATSHEET.md fixed in at least 6 separate commits
7. **Encoding (utf-8)** — added across multiple files in at least 2 passes
8. **Load_config / sys.exit** — changed from sys.exit to ConfigError raise (at least 2 commits)

## Files with Repeated Fixes (Instability Indicators)

### Tier 1: Highest instability concern

**`scripts/validate_config.py`** (885 lines, 18 touches in 100 commits)
- TOML parser bugs across 4+ passes (single quotes, brackets, hyphens, escapes, EOF)
- gh() timeout crash (P0)
- ConfigError vs sys.exit refactor
- Regex boundary fixes
- API limit bumps
- gh_json migration
- This is the shared foundation library. Every other script depends on it. Bugs here cascade.

**`skills/sprint-release/scripts/release_gate.py`** (731 lines, 18 touches in 100 commits)
- P0 correctness: gate truncation
- Rollback commit undo (Phase 1 CRITICAL)
- bump_version validation
- Release notes cleanup on failure + tempfile fix
- Rollback warnings
- PR selection bugs
- Production logic bugs (P0 in pass 12)
- The most complex single script. Every pass finds something new.

**`skills/sprint-run/scripts/sync_tracking.py`** (377 lines, 16 touches in 100 commits)
- YAML quoting/frontmatter issues (at least 3 times)
- Empty labels
- end_line semantics
- config_dir bug
- Production logic bugs (P0 in pass 12)
- Deceptively small (377 lines) for the bug density.

### Tier 2: Moderate instability concern

**`skills/sprint-setup/scripts/populate_issues.py`** (460 lines, 15 touches)
- Milestone title mapping (fixed at initial ship, then re-fixed)
- lstrip char stripping bug
- Milestone API error re-raise
- Regex for optional Epic column
- gh_json migration

**`skills/sprint-monitor/scripts/check_status.py`** (439 lines, 11 touches)
- Regex boundaries
- Format injection
- Multiline workflow run blocks (newline vs &&)
- gh() wrapper consolidation

**`scripts/sprint_analytics.py`** (282 lines, 12 touches)
- Format injection
- Multiline YAML
- Dead code removal
- Repeated across multiple passes for the same categories of bug

**`skills/sprint-run/scripts/update_burndown.py`** (239 lines, 10 touches)
- Smallest of the hotspot scripts by far
- end_line semantics
- YAML-sensitive values in frontmatter
- get_sprints_dir refactor

### Tier 3: Test infrastructure instability

**`tests/test_gh_interactions.py`** (3103 lines, 30 touches)
- By far the most-changed file in the repo
- 3103 lines is enormous for a test file
- Repeatedly had tautological assertions removed
- call_args assertions added retroactively
- main() integration tests added late
- Structural refactoring (shared pipeline helper extraction)
- This file is a magnet for churn because every production fix needs a corresponding test change

**`tests/fake_github.py`** (920 lines, 14 touches)
- Test double that keeps needing fidelity improvements
- Short flag support, --jq scoping, label filtering, --limit/--state enforcement
- Strict mode and _KNOWN_FLAGS registry added after finding tests were passing due to missing flag enforcement
- Real jq evaluation added in pass 12
- The repeated fidelity issues suggest the original design was too loose, causing tests to pass that should have failed

**`tests/test_release_gate.py`** (1426 lines, 16 touches)
- Mirrors release_gate.py instability
- gate_ci tests mentioned in at least 3 separate fix commits

## Red Flags

### 1. TOML parser keeps breaking
The custom TOML parser in validate_config.py has been fixed for:
- Single-quoted strings (pass 6)
- Single-quote arrays (pass 7)
- Bracket-in-string (pass ~5)
- Hyphens in keys
- Escape sequences
- Multiline comments
- EOF edge case
This is a hand-rolled parser replacing `tomllib`. The surface area of TOML edge cases is large and keeps surfacing. **Strong candidate for further bugs.**

### 2. FakeGitHub is a leaky test double
8+ commits tightening FakeGitHub suggest the test infrastructure was not faithfully simulating `gh` CLI behavior. Tests that passed against FakeGitHub may not have been testing what they appeared to test. The late additions of strict mode, known-flags registry, and real jq evaluation confirm this retroactively. **Any test that relies on FakeGitHub behavior added before pass 11 deserves skepticism.**

### 3. The bug-hunter loop is generating diminishing returns
- Pass 4: 16 items
- Pass 5: ~47 items (big sweep)
- Pass 6: 24 items
- Pass 7: 22 items
- Pass 8: 23 items
- Pass 9: 27 items
- Pass 10: 28 items
- Pass 11: 42 items (+ 3 structural prevention items)
- Pass 12: 35 items

Item counts are NOT decreasing. Each pass finds as many or more issues than the previous. This could indicate: (a) each pass is widening scope, (b) the fixes from earlier passes are introducing new bugs, or (c) the codebase has deep structural issues that surface-level fixes don't address.

### 4. Batch fix commits are a smell
Commits like "fix: resolve 20 code bugs across all scripts (BH-001 through BH-025)" and "fix: batch resolve P5-05/06/07/08/14/15/16/19/21/23/24/31/32/33/34/35/36/37/40" touch many files in a single commit. This makes it hard to verify each fix in isolation and easy to introduce regressions.

### 5. release_gate.py has P0/CRITICAL bugs found late
A "Phase 1 CRITICAL" fix (bump_version validation, TOML EOF check, rollback commit undo) appeared in pass 5. P0 production logic bugs were still being found in pass 12. This is the release pipeline -- the code that tags and publishes releases. Finding critical bugs here late is concerning.

### 6. Doc-code drift is chronic
CLAUDE.md and CHEATSHEET.md appear in 13 and 12 of the last 100 commits respectively, almost always for "fix stale line refs." The line-number reference system creates a maintenance burden that generates churn every time code changes. At least 6 separate commits are dedicated solely to updating stale line references.

### 7. sync_tracking.py: high bug density per line
At 377 lines with 16 touches in 100 commits, sync_tracking.py has the highest churn-per-line ratio of any production file. It interacts with both GitHub API and local YAML files, creating a wide surface for parsing, quoting, and state-sync bugs.

## Summary: Priority Files for Adversarial Review

1. **`scripts/validate_config.py`** -- shared foundation, TOML parser fragility, 18 touches
2. **`skills/sprint-release/scripts/release_gate.py`** -- complex release logic, P0 bugs found in pass 12
3. **`skills/sprint-run/scripts/sync_tracking.py`** -- highest bug density per line
4. **`tests/fake_github.py`** -- leaky test double undermines test reliability
5. **`skills/sprint-setup/scripts/populate_issues.py`** -- parsing/regex hotspot
6. **`skills/sprint-monitor/scripts/check_status.py`** -- format injection, regex issues
7. **`scripts/sprint_analytics.py`** -- repeated fixes for same bug categories
