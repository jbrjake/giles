# Bug Hunter Punchlist — Pass 34 (Extend)

> Generated: 2026-03-21 | Project: giles | Baseline: 1158 pass, 0 fail → 1161 pass, 0 fail
> Focus: Resolve deferred items, audit fix commits + core files + test quality

## Summary

| Severity | Open | Resolved | Closed |
|----------|------|----------|--------|
| HIGH     | 0    | 0        | 0      |
| MEDIUM   | 0    | 3        | 0      |
| LOW      | 0    | 2        | 1      |

---

## Resolved (Pass 34)

| ID | Title | Severity | Resolution | Validating Test |
|----|-------|----------|------------|-----------------|
| BH34-001 | Naive datetime.now() across 4 files | LOW | All calls now use `datetime.now(timezone.utc)`; readers use `.replace(tzinfo=timezone.utc)` | All 1161 tests pass; `grep datetime.now()` returns 0 hits |
| BH34-002 | `git push --all` bypasses base-branch protection | MEDIUM | Added `--all` to unconditional block alongside `--mirror` | `test_hooks.py::test_all_flag_blocked` |
| BH34-003 | `populate_issues.py` `int()` crash on non-numeric story points | MEDIUM | Changed `int(meta.get("story_points", "0"))` → `safe_int(...)` | `test_hexwise_setup.py::test_parse_detail_blocks_non_numeric_sp` |
| BH34-004 | kanban-protocol.md says review/integration WIP limits are "Behavioral" but code enforces them | MEDIUM | Updated doc to say "Code (`check_wip_limit`, override: `--force-wip`)" | Documentation fix |
| BH34-005 | `test_os_error_caught` is test theater + leaked temp dirs | LOW | Rewrote with `TemporaryDirectory`; added `test_attribute_error_propagates` to validate exception boundary | `test_bugfix_regression.py::TestCheckSmokExceptionNarrowing` |

**Files changed:**
- `scripts/smoke_test.py` — UTC timestamp
- `skills/sprint-monitor/scripts/check_status.py` — UTC-aware parse + compare
- `scripts/kanban.py` — UTC transition log timestamps
- `.claude-plugin/hooks/review_gate.py` — UTC audit log + `--all` block
- `skills/sprint-setup/scripts/populate_issues.py` — `safe_int()` import + usage
- `skills/sprint-run/references/kanban-protocol.md` — WIP enforcement docs
- `tests/test_bugfix_regression.py` — rewritten weak test + new boundary test
- `tests/test_hooks.py` — `--all` block test
- `tests/test_hexwise_setup.py` — non-numeric SP test

---

## Closed (not a bug)

| Finding | Why closed |
|---------|-----------|
| BH33-008: assign_dod_level count display | Display-only metric. Count reflects current classification, which is more informative than stored value. |

---

## Deferred (low severity, from core audit)

| Finding | Why deferred |
|---------|-------------|
| TOML parser rejects hyphen-leading bare keys | Project templates don't use them; rare in practice |
| TOML parser accepts malformed quoted strings | Only affects hand-edited TOML with typos |
| kanban.py API contract incomplete for WIP lock | CLI handles correctly; only internal API callers |
| kanban.py case-sensitive persona comparison | Consistent in practice via do_assign |
| bootstrap_github.py milestone title length limit | Theoretical; headings are short |
| populate_issues.py ARG_MAX for long issue bodies | Bodies well under 1KB |

---

## Pattern Blocks

### PATTERN-34-A: Destructive git push flags (review_gate)

**Items:** BH34-002 (new), BH33-001 (prior)
**Root cause:** The boolean-flag whitelist in `_check_push_single` was designed for common flags
but missed destructive whole-repo operations (`--mirror`, `--all`). The parser correctly identifies
them as boolean flags, but the post-parse safety check only blocked `--mirror`. Now both are blocked.
**Sibling check:** `--tags` is in the boolean set but is read-only (pushes tags, doesn't delete).
No block needed.

### PATTERN-34-B: Unsafe type coercion at trust boundaries

**Items:** BH34-003
**Root cause:** `int()` used on values from markdown parsing without validation. The `safe_int()`
helper exists in validate_config.py for exactly this purpose but wasn't imported in populate_issues.py.
All other scripts that parse SP values already use `safe_int()` or `extract_sp()`.
