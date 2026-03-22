# Phase 0a: Project Overview — Bug Hunter Pass 35

**Date:** 2026-03-21
**Commit range:** 8852009 (HEAD, pass 34 chore) and all prior
**Prior pass:** Pass 34 (5 items resolved, 6 deferred as low-severity)
**Test baseline:** 1161 passed, 0 failed (17.58s)
**Production LOC:** ~11,187 across 26 files (19 scripts + 7 hooks/skills scripts)

---

## What Changed Since Last Pass

Pass 34 was the most recent pass. Commit 0ce81b2 fixed 5 items (BH34-001 through BH34-005). No commits exist after the pass 34 chore commit (8852009). The working tree shows the prior recon/punchlist files deleted and archived to `bug-hunter-prior-pass34/`.

### Files Modified in the Fix Commits (0ce81b2, b03ccbe)

| File | Lines | Changes |
|------|-------|---------|
| `.claude-plugin/hooks/review_gate.py` | 266 | `--delete`, `-d`, `--mirror` added to boolean flag set; `--all`/`--mirror` unconditional block; UTC timestamps |
| `scripts/kanban.py` | 818 | UTC timestamps in transition log |
| `scripts/smoke_test.py` | 129 | UTC timestamps; pipe-char escaping in markdown table |
| `scripts/manage_sagas.py` | 319 | JSON parse error handling for allocation/voices |
| `scripts/team_voices.py` | 110 | Skip empty blockquote entries |
| `scripts/validate_anchors.py` | 342 | Strip trailing empty element to prevent blank line accumulation |
| `skills/sprint-monitor/scripts/check_status.py` | 611 | UTC-aware datetime comparison; narrowed exception from `Exception` to `(OSError, subprocess.SubprocessError)` |
| `skills/sprint-setup/scripts/populate_issues.py` | 564 | `safe_int()` import; `int()` -> `safe_int()` for story points |
| `skills/sprint-run/references/kanban-protocol.md` | — | Doc fix: WIP limits enforcement description |

### Test Files Modified

| File | Changes |
|------|---------|
| `tests/test_bugfix_regression.py` | +3 tests: exception narrowing boundary tests |
| `tests/test_hexwise_setup.py` | +2 tests: 5-digit story ID, non-numeric SP |
| `tests/test_hooks.py` | +4 tests: --delete, -d, --mirror, --all blocking |
| `tests/test_new_scripts.py` | +1 test: pipe escaping in smoke history |
| `tests/test_pipeline_scripts.py` | +2 tests: empty voice skip, AC format round-trip |
| `tests/test_validate_anchors.py` | +1 test: fix idempotency (no trailing newlines) |
| `tests/test_verify_fixes.py` | +2 tests: invalid JSON for saga allocation/voices |

---

## Deferred Items From Pass 34

These were explicitly deferred as low-severity. Worth re-evaluating:

1. **TOML parser rejects hyphen-leading bare keys** — `validate_config.parse_simple_toml()`
2. **TOML parser accepts malformed quoted strings** — same parser
3. **kanban.py API contract incomplete for WIP lock** — `check_wip_limit` internal API
4. **kanban.py case-sensitive persona comparison** — `do_assign` path
5. **bootstrap_github.py milestone title length limit** — theoretical
6. **populate_issues.py ARG_MAX for long issue bodies** — theoretical

---

## Subsystem Inventory

### High-Churn (touched in 5+ of last 30 commits)

| Subsystem | Key Files | Last Fix | Risk |
|-----------|-----------|----------|------|
| Hooks | `review_gate.py`, `commit_gate.py`, `session_context.py`, `verify_agent_output.py` | 0ce81b2 | Medium — complex string parsing (TOML, git commands) |
| Kanban | `kanban.py`, `sync_tracking.py` | 0ce81b2 | Medium — state machine, locking, file I/O |
| Config/TOML | `validate_config.py` | 15694b0 | Medium — custom parser, many consumers |

### Medium-Churn (touched in 2-4 of last 30 commits)

| Subsystem | Key Files | Last Fix |
|-----------|-----------|----------|
| Sprint Monitor | `check_status.py` | 0ce81b2 |
| Populate Issues | `populate_issues.py` | 0ce81b2 |
| Gap Scanner | `gap_scanner.py` | 2768f12 |
| Manage Epics | `manage_epics.py` | 2768f12 |
| Manage Sagas | `manage_sagas.py` | b03ccbe |
| Sync Backlog | `sync_backlog.py` | 15694b0 |
| Risk Register | `risk_register.py` | e564910 |

### Low-Churn / Untouched (not modified in last 10 commits)

| File | Last Commit | Notes |
|------|-------------|-------|
| `sprint_init.py` | 7bbf41b | Project scanner/generator — large, complex |
| `sprint_teardown.py` | 87237e3 | Simple but safety-critical |
| `sprint_analytics.py` | d9e874b | Metrics computation |
| `test_categories.py` | d67d173 | Test classifier |
| `assign_dod_level.py` | 18f5238 | Story classifier |
| `history_to_checklist.py` | 18f5238 | Checklist generator |
| `test_coverage.py` | 0eeccec | Test file scanner |
| `traceability.py` | 0eeccec | PRD/test mapping |
| `commit.py` | f7b71c0 | Conventional commit enforcer |
| `setup_ci.py` | 069ab46 | CI YAML generator |
| `bootstrap_github.py` | a26bd76 | GitHub label/milestone creation |
| `update_burndown.py` | a044798 | Burndown chart updates |
| `release_gate.py` | 7aaf4d2 | Release gating + versioning |

---

## Key Architectural Observations

1. **Fix density is dropping.** Pass 34 found 5 items (3 MEDIUM, 2 LOW) compared to earlier passes that found 5-10 HIGH/MEDIUM items. The codebase is converging.

2. **Pattern: UTC consistency is now complete.** BH34-001 was the last `datetime.now()` without UTC. All timestamps are now timezone-aware. The readers (check_status smoke/debt checks) use `.replace(tzinfo=timezone.utc)` on parsed naive timestamps.

3. **TOML parser remains a risk surface.** The custom parser in `validate_config.py` has been the subject of multiple bug-hunter findings across many passes. Two deferred items remain. The inline TOML readers in `commit_gate.py` and `session_context.py` are separate implementations (lightweight parsers) that have also been fixed repeatedly.

4. **review_gate.py git-push parser is hardening but complex.** The `_check_push_single` function uses manual positional argument parsing with a whitelist of flags. Each pass finds new edge cases (--delete, --mirror, --all). The approach of whitelisting known-safe patterns means any unknown flag could be misclassified.

5. **Untouched files are a mixed bag.** `sprint_init.py` (project scanner) and `release_gate.py` (release gating) are both large and complex but have received less recent scrutiny. `sprint_init.py` was last fixed for ReDoS issues; `release_gate.py` was last fixed for MonitoredMock warnings.

6. **Test infrastructure is mature.** 1161 tests, all passing. The `fake_github.py` mock, golden test system, and property-based tests provide good coverage. Test quality has been audited in multiple passes.

---

## Files That Warrant Deeper Audit

### Priority 1: Recently-fixed files (regression risk from fixes)

- **`.claude-plugin/hooks/review_gate.py`** — The `_check_push_single` parser has grown through incremental fixes. Worth checking for remaining edge cases in the positional-arg extraction logic, especially around flag-value pairs and the boolean flag whitelist.
- **`scripts/validate_config.py`** — The TOML parser has two deferred items. The `safe_int()` function is now used more broadly. Worth checking edge cases.
- **`skills/sprint-monitor/scripts/check_status.py`** — Exception narrowing from `Exception` to `(OSError, subprocess.SubprocessError)` is correct but worth verifying no other exception types from `subprocess.run` could occur.

### Priority 2: Untouched complex files

- **`scripts/sprint_init.py`** — 1236 lines (largest script), untouched since ReDoS fix. Complex project scanning logic.
- **`skills/sprint-release/scripts/release_gate.py`** — Release gating with semver, commit parsing, multiple gates. Not recently audited.
- **`skills/sprint-setup/scripts/bootstrap_github.py`** — GitHub API interactions, label/milestone creation. Milestone title mapping was a prior bug source.

### Priority 3: Cross-component seams

- **kanban.py <-> sync_tracking.py** — Two-path state management. Lock semantics, atomic writes, status reconciliation.
- **commit_gate.py <-> validate_config.py** — Inline TOML parser in commit_gate vs full parser in validate_config. Different implementations could diverge.
- **populate_issues.py <-> manage_epics.py** — Story format contracts (AC prefix format, story ID patterns). The BH30-005 round-trip test covers this but the seam is wide.

### Priority 4: Hooks subsystem as a whole

- **`session_context.py`** — Path resolution, TOML reading, DoD retro extraction. Multiple prior fixes.
- **`verify_agent_output.py`** — Agent detection, tracking file updates. Prior fixes for false positives/negatives.
- **`commit_gate.py`** — Inline config reading, CI command execution. Prior fixes for state handling.
