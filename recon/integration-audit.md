# Integration Audit: Cross-Script Seams

Audited 2026-03-20. Focus: integration bugs across `validate_config.py`,
`kanban.py`, `sync_tracking.py`, `sync_backlog.py`, `bootstrap_github.py`,
and `populate_issues.py`.

Prior audit findings (Issues 1-3, 8, 13) have been fixed in current code.
This audit covers remaining and newly identified integration issues.

---

### FINDING-1: sync_tracking.py and kanban.py use incompatible lock scopes
**Files:** scripts/kanban.py, skills/sprint-run/scripts/sync_tracking.py
**Severity:** HIGH
**Description:** `kanban.py`'s CLI uses two different lock scopes depending
on the operation:
- WIP-limited transitions (dev, review, integration): `lock_sprint()` — acquires
  `.kanban.lock` in the sprint directory (kanban.py line 754)
- Other transitions, assign, update: `lock_story()` — acquires `<file>.lock`
  per tracking file (kanban.py lines 764, 779, 785)
- sync: `lock_sprint()` (kanban.py line 730)

Meanwhile, `sync_tracking.py` uses only `lock_story()` per file (lines 276, 288).

These are different lock files. A `kanban.py transition US-0042 dev` holding
`lock_sprint` and a concurrent `sync_tracking.py` run holding `lock_story` on the
same US-0042 file will NOT serialize. Both processes can read-modify-write the
same tracking file simultaneously. The `kanban.py` transition writes via
`atomic_write_tf` (rename-based), while `sync_tracking.py` writes via plain
`write_tf` (direct write). The last writer wins, potentially reverting the other's
changes.

**Evidence:**
```
# kanban.py line 754 — sprint-level lock for WIP transitions
with lock_sprint(sprints_dir / f"sprint-{sprint}"):
    tf = read_tf(tf.path)
    ok = do_transition(tf, args.target, ...)

# sync_tracking.py line 276 — per-story lock
with lock_story(existing[sid].path):
    existing[sid] = read_tf(existing[sid].path)
    changes = sync_one(existing[sid], issue, pr, sprint)
    if changes:
        write_tf(existing[sid])
```
The sprint lock file is `sprint-{N}/.kanban.lock`. The story lock file is
`sprint-{N}/stories/US-0042-slug.lock`. These are independent — neither
blocks the other.

---

### FINDING-2: sync_tracking.py uses non-atomic write_tf while kanban.py uses atomic_write_tf
**Files:** scripts/validate_config.py, scripts/kanban.py, skills/sprint-run/scripts/sync_tracking.py
**Severity:** MEDIUM
**Description:** `kanban.py` uses `atomic_write_tf()` for all writes. This
function writes to a `.tmp` file then does `os.rename()`, ensuring readers
never see a partially-written file.

`sync_tracking.py` uses plain `write_tf()` (validate_config.py line 1121),
which calls `path.write_text()` directly. This is not atomic — a concurrent
reader (e.g., `kanban.py`'s `check_wip_limit` scanning all story files, or
`do_status` building the board view) can observe a partially-written file.

Even though `sync_tracking.py` holds `lock_story` during the write, other code
paths that read tracking files do NOT acquire any lock:
- `kanban.py check_wip_limit` (line 279): reads all `*.md` files in stories/
- `kanban.py do_status` (line 636): reads all `*.md` files in stories/
- `kanban.py find_story` (line 218): reads matching files
- `kanban.py do_sync` (line 494): reads all `*.md` files

None of these acquire `lock_story`. A concurrent `write_tf` from
`sync_tracking.py` can produce a partially-written file that `read_tf` then
parses into a corrupt TF.

**Evidence:**
```python
# validate_config.py line 1141 — direct write (non-atomic)
tf.path.write_text("\n".join(lines), encoding="utf-8")

# kanban.py line 152-153 — atomic write via temp+rename
write_tf(tmp_tf)
os.rename(str(tmp), str(tf.path))
```

---

### FINDING-3: kanban.py do_sync writes without per-story locks
**Files:** scripts/kanban.py
**Severity:** MEDIUM
**Description:** `kanban.py do_sync()` (called from CLI with `lock_sprint`
held) reads all story files into `local_by_id`, then iterates through GitHub
issues writing updated files via `atomic_write_tf`. It does NOT acquire
`lock_story` for individual files.

The sprint-level lock prevents concurrent `kanban.py sync` calls, but does
NOT prevent concurrent `sync_tracking.py` (which uses `lock_story`),
`do_assign` / `do_update` (which use `lock_story`), or non-WIP transitions
(which also use `lock_story`).

During the window where `do_sync` is iterating (potentially many stories),
a concurrent `kanban.py assign US-0042 --implementer rae` holding
`lock_story(US-0042)` could write to the same file that `do_sync` is about
to overwrite. Since `do_sync` read the file at the start of iteration (line
495), it has a stale copy and will overwrite the assignment.

**Evidence:**
```python
# kanban.py line 494-497 — reads all files at once, no per-story lock
for md_file in sorted(stories_dir.glob("*.md")):
    tf = read_tf(md_file)
    if tf.story:
        local_by_id[tf.story.upper()] = tf

# ... then later, line 534 — writes without re-reading or locking
atomic_write_tf(tf)
```

---

### FINDING-4: sync_tracking.py sync_one accepts any state transition; kanban.py do_sync validates
**Files:** scripts/kanban.py, skills/sprint-run/scripts/sync_tracking.py
**Severity:** MEDIUM
**Description:** The two sync paths have divergent transition acceptance
policies:

- `kanban.py do_sync` (line 529): validates transitions via
  `validate_transition()` and rejects illegal ones (e.g., `todo` -> `done`)
- `sync_tracking.py sync_one` (line 135): accepts ANY state change from
  GitHub with no validation

This means the same GitHub label change produces different behavior depending
on which sync path runs first. If `sync_tracking.py` runs before
`kanban.py do_sync`, an illegal transition (e.g., someone manually labeling
an issue `kanban:done` from `todo`) will be accepted locally. If
`kanban.py do_sync` runs first, it will be rejected with a warning.

The `sync_tracking.py` docstring (line 9-12) says this is intentional:
"this script accepts GitHub state for fields that kanban.py does not manage."
But it also accepts state changes that kanban.py actively rejects, creating
an inconsistency where running the "wrong" sync first produces permanently
different local state.

**Evidence:**
```python
# kanban.py line 529 — validates transition
err = validate_transition(tf.status, github_state)
if err is None:
    # ...accept...
else:
    # WARNING: illegal external transition ignored

# sync_tracking.py line 135 — no validation
if gh_status != tf.status and gh_status in KANBAN_STATES:
    append_transition_log(tf, old_status, gh_status, "external: GitHub sync")
    tf.status = gh_status  # accepts anything
```

---

### FINDING-5: kanban.py do_transition partial state on two-step GitHub sync failure
**Files:** scripts/kanban.py
**Severity:** MEDIUM
**Description:** `do_transition` makes two sequential GitHub API calls for
the `done` state: (1) remove/add label, (2) close issue. If the label
update succeeds but `gh issue close` fails, the local state has been rolled
back to the old status, but GitHub now has the new `kanban:done` label with
the issue still open.

The next `kanban.py sync` or `sync_tracking.py` run will see
`kanban_from_labels` return "done" (the label is present) but the issue is
open. Due to `kanban_from_labels`'s closed-issue override (line 1018),
an open issue with `kanban:done` returns "done" from the label. So the sync
will accept the transition to "done" — which may not be desired since the
issue was never actually closed.

**Evidence:**
```python
# kanban.py lines 390-394 — two-step GitHub update
gh(["issue", "edit", issue_num,
    "--remove-label", f"kanban:{old_status}",
    "--add-label", f"kanban:{target}"])
if target == "done":
    gh(["issue", "close", issue_num])  # if this fails...
# ... rollback reverts local state but GitHub label is already changed
```

---

### FINDING-6: sync_backlog.py import fallback silently degrades to None
**Files:** scripts/sync_backlog.py
**Severity:** MEDIUM
**Description:** `sync_backlog.py` imports `bootstrap_github` and
`populate_issues` in a try/except block (lines 27-32). If the import fails,
both modules are set to `None` and execution continues. The failure is only
detected later in `do_sync()` when `bootstrap_github is None` (line 162)
raises an `ImportError`.

The problem is that the original `ImportError` (which may contain useful
diagnostic information like "No module named X" or a circular import
traceback) is swallowed. The replacement `ImportError` at line 163 gives a
generic message.

More critically: the `sys.path.insert` at line 24 adds the
`skills/sprint-setup/scripts/` directory to `sys.path`. This directory also
contains scripts that import from `validate_config`. When
`bootstrap_github.py` is imported, its top-level code (line 14-15) does
ANOTHER `sys.path.insert` pointing to `scripts/` — but the path it
computes (`Path(__file__).resolve().parent.parent.parent.parent / "scripts"`)
resolves correctly only when `__file__` is the actual file path, not when
the module was imported with a modified `sys.path`. This works because
Python resolves `__file__` to the actual filesystem path, but it means both
`scripts/` entries are now on `sys.path` and `validate_config` could
potentially be imported from different locations if there were naming
conflicts.

**Evidence:**
```python
# sync_backlog.py lines 27-32 — swallows original ImportError
try:
    import bootstrap_github
    import populate_issues
except ImportError:
    bootstrap_github = None  # type: ignore[assignment]
    populate_issues = None  # type: ignore[assignment]

# Line 163 — replacement error loses original context
raise ImportError("bootstrap_github or populate_issues not available")
```

---

### FINDING-7: Two sync paths create tracking files with different body content
**Files:** scripts/kanban.py, skills/sprint-run/scripts/sync_tracking.py
**Severity:** LOW
**Description:** When creating tracking files for new stories discovered on
GitHub, the two sync paths produce different file content:

- `kanban.py do_sync` (line 555-562): Creates TF with default empty
  `body_text` — no Verification section, no Transition Log
- `sync_tracking.py create_from_issue` (lines 212-216): Creates TF with
  a Verification section in `body_text`

If `kanban.py do_sync` creates the file first, the Verification section
is missing. A subsequent `sync_tracking.py` run calls `sync_one` on the
existing file, which only updates frontmatter fields — it never adds the
missing Verification section. The P1-STATE-3 initialization is permanently
skipped for that story.

Additionally, `kanban.py do_sync` does not set `branch` or `pr_number`
fields, while `sync_tracking.py create_from_issue` sets both (line 207:
`branch=f"sprint-{sprint}/{slug}"` and line 206: `pr_number` from PR
linkage). Running `kanban.py sync` first loses this metadata.

**Evidence:**
```python
# kanban.py line 555 — bare TF, no body
tf = TF(path=path, story=story_id, title=short_title(title),
        sprint=sprint, status=github_state, issue_number=issue_num)

# sync_tracking.py line 199 — TF with body, branch, pr
tf = TF(path=target, story=sid, title=short,
        sprint=sprint, status=status, issue_number=str(issue["number"]),
        pr_number=str(pr["number"]) if pr else "",
        branch=f"sprint-{sprint}/{slug}"[:255])
tf.body_text = "## Verification\n- agent: []\n..."
```

---

### FINDING-8: _yaml_safe does not escape tab characters
**Files:** scripts/validate_config.py
**Severity:** LOW
**Description:** `_yaml_safe()` checks for and escapes newlines (`\n`),
carriage returns (`\r`), and backslashes, but does not check for tab
characters (`\t`). A tab in a tracking file value (e.g., a story title
pasted from a spreadsheet) would be written to the frontmatter unquoted
and unescaped.

When `read_tf` reads it back, `frontmatter_value` uses
`re.search(rf"^{key}:[ \t]*([^\n]*)", ...)` — the `[ \t]*` after the colon
would consume leading tabs. But a tab in the middle of the value would be
preserved as-is. This is mostly harmless but breaks the principle that
`_yaml_safe` → `write_tf` → `read_tf` → `frontmatter_value` is a lossless
roundtrip for all string values.

**Evidence:**
```python
# validate_config.py line 1065-1078 — no \t check
needs_quoting = (
    ': ' in value
    or value.endswith(':')
    # ... many checks ...
    or '\n' in value
    or '\r' in value
    # missing: or '\t' in value
)
```

---

### FINDING-9: sync_tracking.py's existing dict uses case-sensitive story ID keys
**Files:** skills/sprint-run/scripts/sync_tracking.py, scripts/kanban.py
**Severity:** LOW
**Description:** `sync_tracking.py` builds its `existing` dict using
`tf.story` directly as the key (line 268):
```python
existing[tf.story] = tf
```

Then it looks up stories using `extract_story_id(issue["title"])` (line 273),
which returns uppercase IDs for standard patterns.

If a tracking file was somehow written with a lowercase story ID (e.g., by
manual editing: `story: us-0042`), the lookup `sid in existing` would fail
(since `sid` is "US-0042" but the key is "us-0042"). `sync_tracking.py`
would then create a DUPLICATE tracking file for the same story.

By contrast, `kanban.py do_sync` normalizes to uppercase on both sides:
`local_by_id[tf.story.upper()]` (line 497) and
`story_id = extract_story_id(title).upper()` (line 504).

`kanban.py find_story` also normalizes: `prefix = story_id.upper()` and
`stem = md_file.stem.upper()` (lines 216, 219).

Only `sync_tracking.py` is missing the `.upper()` normalization on the
dict key side.

**Evidence:**
```python
# sync_tracking.py line 268 — case-sensitive key
existing[tf.story] = tf

# kanban.py line 497 — case-normalized key
local_by_id[tf.story.upper()] = tf
```

---

### FINDING-10: sync_backlog.py do_sync does not handle partial issue creation failure
**Files:** scripts/sync_backlog.py, skills/sprint-setup/scripts/populate_issues.py
**Severity:** LOW
**Description:** `sync_backlog.py do_sync()` iterates through stories and
calls `populate_issues.create_issue()` for each (lines 185-189). If any
single `create_issue` call fails, it returns `False` (the exception is
caught internally in `create_issue`). The loop continues with the next story.

However, the function then updates `state["file_hashes"]` to `current_hashes`
(line 232 in `main()`), marking the sync as complete. On the next run,
`check_sync` will see no changes and skip syncing. The stories that failed
creation are effectively lost — they won't be retried unless the milestone
file changes again.

This contrasts with the `except Exception` path at line 226, which correctly
does NOT update hashes on total failure. But partial failure (some issues
created, some not) updates hashes as if everything succeeded.

**Evidence:**
```python
# sync_backlog.py lines 184-191 — partial failures not tracked
created = 0
for story in stories:
    if story.story_id in existing:
        continue
    if populate_issues.create_issue(story, milestone_numbers, milestone_titles):
        created += 1
result["issues"] = created
return result  # no indication of failures

# Line 232 — hashes updated as if sync fully succeeded
state["file_hashes"] = current_hashes
```

---

### FINDING-11: do_transition rollback leaves GitHub labels in inconsistent state on done transition
**Files:** scripts/kanban.py
**Severity:** LOW
**Description:** In `do_transition`, when transitioning to `done`, two
GitHub operations happen: (1) label swap, (2) issue close. If operation 1
succeeds but operation 2 fails, the rollback (lines 398-401) restores
local state but does NOT reverse the label change on GitHub.

After rollback, the local file says `status: integration` (old state) but
GitHub has `kanban:done` label (new state) and the issue is still open.
The rollback error message says "local state reverted" but doesn't mention
the stale label.

The same partial-rollback issue exists for `do_assign`: if the persona
label is applied but the body update fails, the label persists. The
docstring for `do_assign` documents this (line 422-424), but `do_transition`
does not document its equivalent risk.

**Evidence:**
```python
# kanban.py lines 390-394 — label already changed before close attempt
gh(["issue", "edit", issue_num,
    "--remove-label", f"kanban:{old_status}",
    "--add-label", f"kanban:{target}"])
if target == "done":
    gh(["issue", "close", issue_num])  # if this fails...

# Lines 398-401 — rollback only fixes local, not GitHub labels
tf.status = old_status
tf.body_text = old_body
atomic_write_tf(tf)
```

---

## Summary

| # | Severity | Category | One-line |
|---|----------|----------|----------|
| 1 | HIGH | race condition | lock_sprint vs lock_story use different lock files; kanban transitions and sync_tracking don't serialize |
| 2 | MEDIUM | race condition | sync_tracking uses non-atomic write_tf; concurrent readers see partial files |
| 3 | MEDIUM | race condition | kanban do_sync reads all files upfront without per-story locks; concurrent writes clobbered |
| 4 | MEDIUM | semantic divergence | sync_tracking accepts any state; kanban do_sync validates transitions — different outcomes from same input |
| 5 | MEDIUM | partial state | done transition: label swap succeeds, close fails → GitHub label diverges from local state |
| 6 | MEDIUM | error handling | sync_backlog import try/except swallows original ImportError diagnostic |
| 7 | LOW | inconsistency | Two sync paths create tracking files with different body content (verification section, branch, PR) |
| 8 | LOW | roundtrip | _yaml_safe does not escape tab characters |
| 9 | LOW | case sensitivity | sync_tracking existing dict uses case-sensitive keys; kanban do_sync normalizes to uppercase |
| 10 | LOW | partial failure | sync_backlog marks sync complete even when some issues fail to create |
| 11 | LOW | partial rollback | do_transition rollback doesn't reverse GitHub label changes; undocumented unlike do_assign |

### Key integration seam answers

1. **Does sync_backlog.py correctly import from bootstrap_github.py and
   populate_issues.py?** Yes, the function signatures are compatible and the
   `sys.path` manipulation works. The `do_sync` function correctly calls
   `create_milestones_on_github(config)`, `parse_milestone_stories(milestone_files, config)`,
   `enrich_from_epics(stories, config)`, etc. with correct argument types.
   The only issue is that the import fallback swallows the original error
   (Finding 6).

2. **Does sync_tracking.py correctly use kanban.py's locking API?** It uses
   `lock_story` correctly, but this is insufficient because `kanban.py`'s
   own CLI uses `lock_sprint` for some operations. The two lock types don't
   interlock (Finding 1).

3. **Are there functions used by multiple callers with different assumptions?**
   Yes — `kanban_from_labels` and `validate_transition` are used differently
   by the two sync paths (Finding 4). `write_tf` vs `atomic_write_tf` is
   another: kanban.py exclusively uses the atomic version, sync_tracking.py
   uses the non-atomic version (Finding 2).

4. **Are there state mutations outside locks?** Yes — `kanban.py do_sync`
   writes files under `lock_sprint` but without `lock_story`, so concurrent
   processes holding `lock_story` can collide (Finding 3). `do_status` and
   `check_wip_limit` read files without any lock.

5. **Are there error paths where state is partially updated?** Yes —
   the `done` transition can leave GitHub labels inconsistent on partial
   failure (Finding 5, 11). `sync_backlog.py` marks sync complete even
   when individual issues fail to create (Finding 10).
