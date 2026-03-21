# Recon 0e: Git Churn Analysis

Generated: 2026-03-16

## Raw Data

### Time Span of Last 50 Commits

All 50 commits land within ~25 hours (2026-03-15 21:06 to 2026-03-16 22:33).
This is an extremely compressed timeline — roughly 2 commits/hour, sustained.

### Commit Type Breakdown (last 50)

| Type     | Count | % of 50 |
|----------|------:|--------:|
| fix      |    32 |     64% |
| chore    |    13 |     26% |
| test     |     3 |      6% |
| refactor |     2 |      4% |
| feat     |     1 |      2% |

Overall repo (289 total commits): 122 fix (42%), 82 feat (28%).
The last 50 commits are fix-dominated at 64% — the repo is deep in a bug-hunting treadmill.

### Top 20 Most-Changed Files (last 50 commits)

| Touches | File | Category |
|--------:|------|----------|
|      17 | BUG-HUNTER-PUNCHLIST.md | bookkeeping |
|      13 | scripts/validate_config.py | production |
|      12 | BUG-HUNTER-STATUS.md | bookkeeping |
|       9 | tests/test_verify_fixes.py | test |
|       8 | tests/test_sprint_runtime.py | test |
|       7 | tests/fake_github.py | test infra |
|       7 | skills/sprint-run/scripts/sync_tracking.py | production |
|       6 | tests/test_release_gate.py | test |
|       6 | tests/test_property_parsing.py | test |
|       6 | tests/test_bugfix_regression.py | test |
|       6 | scripts/manage_epics.py | production |
|       5 | tests/test_gh_interactions.py | test |
|       5 | skills/sprint-setup/scripts/populate_issues.py | production |
|       4 | tests/test_lifecycle.py | test |
|       4 | tests/test_hexwise_setup.py | test |
|       4 | skills/sprint-run/scripts/update_burndown.py | production |
|       4 | scripts/sprint_init.py | production |
|       3 | tests/test_golden_run.py | test |
|       3 | skills/sprint-release/scripts/release_gate.py | production |
|       2 | (19 more files at 2 touches each) | mixed |

### Top Files Touched by `fix:` Commits Only

| Fix Touches | File |
|------------:|------|
|          22 | scripts/validate_config.py |
|          16 | skills/sprint-run/scripts/sync_tracking.py |
|          13 | tests/test_gh_interactions.py |
|          13 | skills/sprint-setup/scripts/populate_issues.py |
|          12 | tests/fake_github.py |
|          11 | skills/sprint-release/scripts/release_gate.py |
|          10 | tests/test_verify_fixes.py |
|          10 | scripts/manage_epics.py |
|           9 | tests/test_release_gate.py |
|           8 | skills/sprint-run/scripts/update_burndown.py |
|           8 | skills/sprint-monitor/scripts/check_status.py |
|           7 | scripts/sprint_init.py |
|           7 | scripts/sprint_analytics.py |
|           6 | tests/test_sprint_runtime.py |
|           6 | tests/test_property_parsing.py |
|           6 | scripts/manage_sagas.py |

### Bug-Hunter Pass References in Commit Messages

| Pass | Mentions | Notes |
|------|:--------:|-------|
| P13  |       20 | heaviest — lots of individual item IDs |
| P12  |       10 | second wave |
| P17  |        5 | leading-zero recurrence |
| P15  |        4 | BH-014 regression |
| P18  |        3 | ReDoS, leading-zero again |
| P19  |        3 | FakeGitHub fidelity |
| P16  |        3 | BH-014 limit increase |
| P20  |        2 | TOML unicode edge cases |

### Test File Churn Ranking

| Touches | Test File |
|--------:|-----------|
|       9 | test_verify_fixes.py |
|       8 | test_sprint_runtime.py |
|       7 | fake_github.py |
|       6 | test_release_gate.py |
|       6 | test_property_parsing.py |
|       6 | test_bugfix_regression.py |
|       5 | test_gh_interactions.py |
|       4 | test_lifecycle.py |
|       4 | test_hexwise_setup.py |

### Recurring Bug Categories

| Category | Commits | Files affected |
|----------|--------:|----------------|
| TOML parser edge cases | 4+ | validate_config.py |
| FakeGitHub fidelity gaps | 7+ | fake_github.py, test_*.py |
| YAML quoting/escaping | 6+ | sync_tracking.py, update_burndown.py |
| Leading-zero sprint numbers | 2 | validate_config.py, check_status.py |
| BH-014 (config validation) | 3 | validate_config.py (fixed, regressed, re-fixed) |

---

## Analysis

### 1. validate_config.py Is the Chronic Pain Center

**22 fix-commit touches** in 50 commits. This file is touched in nearly half of all fix commits.

It has been fixed for:
- Single-quote array parsing
- Sprint regex issues
- Unicode line separators crashing the parser
- Digit-start TOML keys
- Unquoted value warnings
- Section/key check regressions (BH-014, fixed three separate times)
- Leading-zero sprint detection
- gh() timeout crashes
- Anchor regex blind spots

The custom TOML parser (`parse_simple_toml`) is the root of much of this. Every new edge case someone feeds it reveals another gap. This is the predictable outcome of writing a hand-rolled parser for a real format — the long tail of edge cases never ends. The parser has been patched for: multiline comments, bracket-in-string, hyphens, escapes, single quotes, unquoted values, unicode line separators, digit-start keys. Each fix is narrow and correct, but the pattern says the next fuzz run will find another crash.

**Verdict**: The TOML parser is the single highest-risk component. Either it needs property-based fuzz testing to find the remaining edge cases proactively, or it should be replaced with `tomllib` (Python 3.11+) or a vendored TOML library.

### 2. sync_tracking.py Is the Second Chronic Hotspot

**16 fix-commit touches**. Problems keep surfacing in:
- YAML safe escaping (backslashes, trailing colons, multiline, folded style)
- Label handling (None labels, empty labels)
- Branch slug matching
- gh_json migration (moved from `gh()` + `json.loads()` to `gh_json()` three separate times — missed call sites each time)

The YAML generation is hand-rolled (like the TOML parser). Same pattern: a bespoke serializer that keeps getting edge-cased. The `_yaml_safe` function has been patched at least 4 times across these commits.

**Verdict**: The hand-rolled YAML emitter in sync_tracking is a smaller version of the TOML parser problem. It would benefit from a structured serializer or at minimum exhaustive property tests.

### 3. FakeGitHub Is a Maintenance Sink

**12 fix touches** to fake_github.py, plus **7+ "fidelity" commits** across the history. The test mock keeps drifting from real `gh` CLI behavior:
- Missing flag support (short flags, --jq, --limit, --state)
- Missing endpoints (monitoring routes)
- Milestone counter bugs
- Label filter bugs
- jq expression evaluation gaps
- Ignored search predicates

Each time someone writes a new test that exercises a slightly different `gh` call pattern, the fake breaks. This is a structural problem: the mock is trying to simulate a complex CLI tool and will always lag behind real usage.

**Verdict**: FakeGitHub will continue to be a maintenance drag. Consider: (a) recording/replaying real `gh` output, (b) a contract test suite that validates FakeGitHub against real `gh` behavior, or (c) accepting the cost and budgeting for it.

### 4. The Bug-Hunter Treadmill

The commit history shows 20 passes (P1 through P20) of automated bug-hunting, each generating a punchlist of items. The pattern per pass:
1. Run analysis, generate punchlist
2. Fix batch 1
3. Fix batch 2
4. Fix batch 3
5. Mark pass complete, note deferred items
6. Start next pass

This is visible in the pass reference counts: P13 had 20 mentions (the most complex), tapering to P20 with 2. But the **convergence is slow** — P20 still found new TOML parser crashes. The deferred items pile up:
- P19: 3 deferred
- P20: 4 deferred

Each pass introduces regression risk. The BH-014 item was fixed, broke again in P15, and was re-fixed. The leading-zero bug was fixed in P17 and then re-fixed in P18 (different file, same class of bug).

**Verdict**: The bug-hunting passes are finding real bugs but the process is grinding — diminishing returns with non-zero regression risk per pass. The high churn in test files (test_verify_fixes.py at 9 touches, test_bugfix_regression.py at 6) suggests tests are being written reactively rather than designed upfront.

### 5. Commit Velocity vs. Stability Concern

50 commits in 25 hours. Some 2-minute gaps between commits (e.g., P17 batches 1-3 in 4 minutes). This pace suggests:
- Commits are being made before the full impact is understood
- Batch fixes are being split across commits but not tested as a whole
- The "batch 1 / batch 2 / batch 3" pattern within each pass suggests the fix-test-fix cycle is discovering new breakage as it goes

### 6. Feature Work Has Stopped

In the last 50 commits: **1 feat commit** (and it's a test infrastructure addition, not a user feature). The last 50 are entirely maintenance. The repo is at 42% fix commits lifetime, but the recent window is 64% fixes. The trend line is going the wrong way.

### 7. Quiet Files (Not Churning)

Notable files that are NOT in the churn list despite being important:
- `scripts/commit.py` — appears stable
- `scripts/validate_anchors.py` — 1 touch only
- `scripts/team_voices.py` — 1 touch in fix commits
- `scripts/test_coverage.py` — 1 touch in fix commits
- All SKILL.md files — stable
- All reference docs — stable (except kanban-protocol.md, 1 touch)

The skill definitions and reference docs are solid. The instability is concentrated in the Python scripts that do real work, especially parsing and serialization.

---

## Summary of Churn Signals

| Signal | Severity | Root Cause |
|--------|----------|------------|
| validate_config.py: 22 fix touches | HIGH | Hand-rolled TOML parser can't handle the long tail |
| sync_tracking.py: 16 fix touches | HIGH | Hand-rolled YAML emitter keeps getting edge-cased |
| fake_github.py: 12 fix touches | MEDIUM | Mock fidelity gap is structural |
| BH-014 regression cycle (3 fixes) | HIGH | Config validation has coupled code paths |
| 64% fix ratio in recent commits | HIGH | Bug-hunting treadmill, no feature progress |
| 50 commits in 25 hours | MEDIUM | Pace suggests reactive fix-break-fix cycling |
| TOML parser still crashing at P20 | HIGH | Fundamental approach problem, not a bug count problem |
| Deferred items accumulating | MEDIUM | Passes are not converging to zero |
