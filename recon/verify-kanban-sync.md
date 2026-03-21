# Kanban/Sync Integration Audit — Verification Pass

**Date:** 2026-03-21
**Scope:** Re-check FINDING-3, -4, -6, -7, -8, -10 from integration-audit against current code.

---

## FINDING-3: kanban do_sync reads all files upfront without per-story locks

**Verdict: STILL OPEN (by design, mitigated)**

`do_sync` (kanban.py lines 490-600) reads all local tracking files into `local_by_id` at the top of the function (lines 503-507) without any locks, then iterates GitHub issues and writes back with `atomic_write_tf` — also without per-story locks.

However, the CLI `main()` (line 749) wraps the entire `do_sync` call in `lock_sprint()`, which serializes it against other kanban mutations. Similarly, `sync_tracking.py main()` (line 279) also uses `lock_sprint()` for its entire sync loop.

**Remaining concern:** If `do_sync` is called programmatically (not via CLI) without holding `lock_sprint`, there is no built-in protection. The function itself does not acquire any lock — callers must do it. This is documented only by convention, not enforced.

---

## FINDING-4: sync_tracking accepts any state; kanban validates transitions

**Verdict: STILL OPEN (by design)**

`sync_one` in `sync_tracking.py` (lines 128-169) accepts any GitHub state without transition validation:

```python
if gh_status != tf.status and gh_status in KANBAN_STATES:
    old_status = tf.status
    append_transition_log(tf, old_status, gh_status, "external: GitHub sync")
    tf.status = gh_status
```

The only check is `gh_status in KANBAN_STATES` — any valid state name is accepted regardless of whether the transition is legal (e.g., `todo -> done` would be accepted).

By contrast, `kanban.py do_sync` (lines 538-552) does validate transitions via `validate_transition()` and rejects illegal ones with a WARNING. The one exception is closed GitHub issues with `kanban:done` label (lines 527-537), which are force-accepted — a reasonable special case.

This means the two sync paths have deliberately different trust models: `kanban.py do_sync` validates, `sync_tracking.py sync_one` does not. The CLAUDE.md documents this as intentional ("sync_tracking.py accepts any valid state from GitHub"), but it means a manually-applied illegal label on GitHub will be silently accepted by `sync_tracking.py` while being rejected by `kanban.py sync`.

---

## FINDING-7: Two sync paths create TFs with different body content

**Verdict: FIXED**

Both paths now produce identical body content:

`kanban.py do_sync` (lines 576-581):
```python
tf.body_text = (
    "## Verification\n"
    "- agent: []\n"
    "- orchestrator: []\n"
    "- unverified: []\n"
)
```

`sync_tracking.py create_from_issue` (lines 212-217):
```python
tf.body_text = (
    "## Verification\n"
    "- agent: []\n"
    "- orchestrator: []\n"
    "- unverified: []\n"
)
```

The BH27 comment at kanban.py line 573-575 confirms this was an intentional fix: "Initialize verification section to match sync_tracking's create_from_issue, ensuring consistent body regardless of which sync path creates the file first."

**Note:** `create_from_issue` also sets `tf.branch` (line 207: `f"sprint-{sprint}/{slug}"[:255]`) while `kanban.py do_sync` does not set a branch. This is a minor field-level difference, not a body content issue.

---

## FINDING-8: _yaml_safe doesn't escape tab characters

**Verdict: STILL OPEN**

`_yaml_safe` (validate_config.py lines 1056-1085) checks for and escapes:
- `\n` (newline) — line 1075
- `\r` (carriage return) — line 1076
- `\\` (backslash) — line 1074
- `"` (double quote) — line 1082

But `\t` (tab) is not in the `needs_quoting` check and is not escaped in the quoting path. A tab character in a YAML value could cause parsing issues depending on the YAML reader, since tabs are not allowed as indentation in YAML and can be ambiguous in values.

**Severity:** Low. Tab characters in story titles or field values would be unusual in practice. The tracking file frontmatter is read by `read_tf` which uses line-by-line parsing, not a full YAML parser, so tabs in values would likely survive a round-trip. But if any downstream tool reads the frontmatter as YAML, tabs could cause issues.

---

## FINDING-10: sync_backlog marks sync complete on partial failure

**Verdict: FIXED**

`sync_backlog.py main()` (lines 222-253) now handles partial failures correctly:

1. **Complete failure** (lines 230-235): On exception from `do_sync`, the state is NOT updated with new hashes — only `save_state` is called with the unchanged state so debounce/throttle state persists. The comment at line 231 confirms: "BH-021: Do NOT update state on failure — next run should retry."

2. **Partial failure** (lines 236-242): `do_sync` returns a `failed` count. When `failed > 0`, hashes are deliberately NOT updated:
```python
if failed:
    print(f"sync: created {counts['issues']} issues, "
          f"{failed} failed — state NOT updated for retry",
          file=sys.stderr)
else:
    state["file_hashes"] = current_hashes
    ...
```

Only when all issues succeed (lines 243-246) are `file_hashes`, `pending_hashes`, and `last_sync_at` updated. This ensures the next run will retry failed issues.

---

## FINDING-6: sync_backlog import error swallowed

**Verdict: PARTIALLY FIXED**

The ImportError at module level (lines 27-32) is still caught and silently swallowed:

```python
try:
    import bootstrap_github
    import populate_issues
except ImportError:
    bootstrap_github = None
    populate_issues = None
```

No warning is printed at import time. However, `do_sync` (line 162-163) now raises an ImportError if either module is None:

```python
if bootstrap_github is None or populate_issues is None:
    raise ImportError("bootstrap_github or populate_issues not available")
```

And `main()` at lines 258-264 catches this:

```python
except (ConfigError, RuntimeError, ImportError) as exc:
    print(f"sync: error — {exc}", file=sys.stderr)
    sys.exit(1)
```

So the failure is no longer truly "swallowed" — it surfaces at sync time with a clear error message. But the import failure is deferred rather than detected early. If `sync_backlog.py` is imported but `do_sync` is never called (e.g., the `check_sync` returns `should_sync=False` every time), the broken import would never be noticed.

**Remaining concern:** An early warning at import time (e.g., `print("Warning: bootstrap_github/populate_issues not importable", file=sys.stderr)`) would make debugging easier, but the current behavior is functionally correct — the error surfaces before any data corruption can occur.

---

## Summary

| Finding | Status | Notes |
|---------|--------|-------|
| FINDING-3: do_sync no per-story locks | STILL OPEN | Mitigated by callers using `lock_sprint`, but not enforced in function |
| FINDING-4: sync_tracking accepts any state | STILL OPEN | Documented as intentional design; two sync paths have different trust models |
| FINDING-7: Different TF body content | FIXED | Both paths now write identical verification sections (BH27) |
| FINDING-8: _yaml_safe no tab escape | STILL OPEN | Low severity; tabs in values are unlikely in practice |
| FINDING-10: Partial failure updates state | FIXED | `failed` count tracked; hashes only updated on full success (BH-021) |
| FINDING-6: Import error swallowed | PARTIALLY FIXED | Error now surfaces at sync time via raise; still no early warning at import |
