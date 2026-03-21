# Bug Hunter Punchlist — Pass 33 (Convergence Sweep)

> Generated: 2026-03-21 | Project: giles | Baseline: 1158 pass, 0 fail
> Focus: Final convergence sweep across all 19 non-core source files

## Summary

| Severity | Open | Resolved | Deferred |
|----------|------|----------|----------|
| HIGH     | 0    | 0        | 0        |
| MEDIUM   | 0    | 3        | 0        |
| LOW      | 0    | 3        | 2        |

---

## Resolved (Pass 33)

| ID | Title | Resolution | Validating Test |
|----|-------|------------|-----------------|
| BH33-001 | review_gate `--delete`/`-d`/`--mirror` bypass | Added to boolean flags; `--mirror` always blocked | `test_hooks.py::test_delete_flag_blocked`, `test_delete_short_flag_blocked`, `test_mirror_flag_blocked` |
| BH33-002 | check_smoke broad `except Exception` | Narrowed to `(OSError, subprocess.SubprocessError)` | `test_bugfix_regression.py::test_type_error_propagates`, `test_os_error_caught` |
| BH33-003 | smoke_test pipe corruption in history | Escape `\|` before table interpolation | `test_new_scripts.py::test_smoke_history_escapes_pipe_in_command` |
| BH33-004 | validate_anchors trailing newline accumulation | Strip trailing empty element from split | `test_validate_anchors.py::test_fix_idempotent_no_trailing_newlines` |
| BH33-005 | manage_sagas CLI JSON error handling | Wrapped json.loads in try/except | `test_verify_fixes.py::test_invalid_json_allocation_exits_1`, `test_invalid_json_voices_exits_1` |
| BH33-006 | team_voices empty quote ghost entries | Skip entries where quote is empty after strip | `test_pipeline_scripts.py::test_empty_quote_skipped` |

---

## Deferred

| Finding | Why deferred |
|---------|-------------|
| BH33-007: datetime.now() inconsistency in check_status | Writer (smoke_test.py) and reader (check_status.py) both use naive local time consistently. Only main() uses UTC for log timestamps. Changing would break existing smoke-history.md files. |
| BH33-008: assign_dod_level count reflects re-classification | Display-only metric. Showing re-classification rather than stored value is arguably more informative. |

---

## Pattern Blocks

### PATTERN-33-A: Missing flag whitelist entries (review_gate)

**Items:** BH33-001
**Root cause:** The boolean-flag whitelist in `_check_push_single` was built incrementally
and missed destructive flags (`--delete`, `-d`, `--mirror`). Any new git push flag added
in the future needs to be classified as boolean or value-taking.

### PATTERN-33-B: Broad exception catches (check_status pipeline)

**Items:** BH33-002
**Root cause:** Quick exception handling during initial development used `except Exception`
as a catch-all. The outer loop's narrowed catch (BH24-019) was designed to let programming
errors propagate, but inner catches circumvented this.
