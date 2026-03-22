# Bug Hunter Status — Pass 34 (Extend)

**Started:** 2026-03-21
**Current Phase:** Complete
**Focus:** Resolve deferred items, audit fix commits + core files + test quality

## Deferred Item Resolution

| Item | Status |
|------|--------|
| BH33-007 → BH34-001: datetime inconsistency | RESOLVED — all datetime.now() use UTC |
| BH33-008: assign_dod_level count display | CLOSED — correct by design |

## Audit Results

| Audit | Findings | Actionable |
|-------|----------|------------|
| Fix audit (b03ccbe) | All 6 fixes clean, 1 pre-existing gap (--all bypass) | BH34-002 |
| Core files audit | 1 crash bug (safe_int), 1 doc mismatch (WIP), several low/theoretical | BH34-003, BH34-004 |
| Test quality audit | 15/16 solid, 1 weak (test_os_error_caught) | BH34-005 |

## Fix Progress

| Item | Status |
|------|--------|
| BH34-001: Naive datetime.now() → UTC (4 files) | RESOLVED |
| BH34-002: review_gate --all bypass | RESOLVED |
| BH34-003: populate_issues int() → safe_int() | RESOLVED |
| BH34-004: kanban-protocol.md WIP limits doc mismatch | RESOLVED |
| BH34-005: test_os_error_caught weak test + leaked temp dirs | RESOLVED |

## Metrics

| Metric | Before | After | Change |
|--------|--------|-------|--------|
| Tests | 1158 | 1161 | +3 |
| Passed | 1158 | 1161 | +3 |
| Failed | 0 | 0 | 0 |
| Naive datetime.now() calls | 4 | 0 | -4 |

## Deferred (from core audit, low severity)

| Finding | Why deferred |
|---------|-------------|
| TOML parser rejects hyphen-leading bare keys | Project templates don't use them; rare in practice |
| TOML parser accepts malformed quoted strings | Only affects hand-edited TOML with typos |
| kanban.py API contract incomplete for WIP lock | CLI handles correctly; API callers are internal |
| kanban.py case-sensitive persona comparison | Consistent in practice via do_assign |
| bootstrap_github.py milestone title length | Theoretical; headings are short in practice |
| populate_issues.py ARG_MAX for long issue bodies | Issue bodies from format_issue_body are well under 1KB |
