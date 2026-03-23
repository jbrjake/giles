# Kanban / Sync Tracking Adversarial Audit

Audited: `scripts/kanban.py` (815 LOC), `skills/sprint-run/scripts/sync_tracking.py` (319 LOC)

Context: kanban.py is the mutation path (local-first, syncs to GitHub). sync_tracking.py is the reconciliation path (accepts GitHub state). Both write `status` to tracking files. They share `lock_sprint`/`lock_story`/`atomic_write_tf`/`append_transition_log` from kanban.py.

---

## Finding 1: sync_tracking.sync_one bypasses transition validation, WIP limits, and precondition checks

**Severity:** MEDIUM (by design, but has real consequences)
**Category:** Status conflict / Transition validation
**Location:** `sync_tracking.py:148` (sync_one), compared to `kanban.py:550-563` (do_sync)

**Problem:** The two sync paths disagree on whether external GitHub state changes require validation:

- `kanban.py do_sync` validates transitions via `validate_transition()` and rejects illegal ones (line 551). It logs a WARNING and does not write.
- `sync_tracking.py sync_one` accepts ANY valid kanban state from GitHub without transition validation (line 148). A manual label change from `todo` directly to `done` (skipping design/dev/review/integration) is silently accepted.

This means the invariant "stories must pass through review before done" can be circumvented by manually adding `kanban:done` label on GitHub, then running `sync_tracking.py`. The docstring acknowledges this ("intentionally accepts ANY valid GitHub state"), but the two sync paths being invoked by different callers (sprint-run uses sync_tracking, kanban CLI uses do_sync) means the same manual label change produces different results depending on which sync runs next.

**Evidence:**
```python
# sync_tracking.py:148 — no transition validation
if gh_status != tf.status and gh_status in KANBAN_STATES:
    ...
    tf.status = gh_status  # any state accepted

# kanban.py:551 — validates transitions
err = validate_transition(tf.status, github_state)
if err is None:
    ...  # accepted
else:
    ...  # WARNING, rejected
```

**Impact:** A story that should have been caught in review can be marked done by either (a) manually closing the issue on GitHub (both paths accept this — by design), or (b) manually applying `kanban:done` label to an open issue then running sync_tracking.py (only sync_tracking accepts this; kanban.py do_sync would reject it as an illegal transition). This bypasses review and integration gates. The `kanban_from_labels` function's BH21-012 override (closed issue = done regardless of label) limits the blast radius for (a), but (b) remains an open hole via sync_tracking.

---

## Finding 2: do_sync (kanban.py) silently drops duplicate story IDs; no collision detection for new files

**Severity:** LOW
**Category:** Error handling
**Location:** `kanban.py:515-519` (local_by_id construction), `kanban.py:574-576` (new file creation)

**Problem:** Two issues in `do_sync`:

1. **Silent duplicate override:** When building `local_by_id`, if two tracking files have the same story ID (different slugs), the second one silently overwrites the first in the dict. Compare with `sync_tracking.py:276-282` which detects and warns about duplicates.

2. **No slug collision check:** When creating a new tracking file (line 574-576), `do_sync` writes directly to the computed path without checking whether a file already exists with a different story ID at that path. Compare with `sync_tracking.py:202-211` which detects slug collisions and appends the issue number to disambiguate.

**Evidence:**
```python
# kanban.py:515-519 — no duplicate detection
local_by_id: dict[str, TF] = {}
for md_file in sorted(stories_dir.glob("*.md")):
    tf = read_tf(md_file)
    if tf.story:
        local_by_id[tf.story.upper()] = tf  # overwrites silently

# sync_tracking.py:276-282 — warns on duplicate
if key in seen_ids:
    print(f"Warning: duplicate story ID '{tf.story}' in ...")
```

**Impact:** In the duplicate case, one tracking file becomes invisible to sync, and its state may drift from GitHub without any warning. In the collision case, a new story could overwrite an existing story's tracking file. Both require the unusual condition of duplicate IDs or identical slugs, so probability is low.

---

## Finding 3: do_transition rollback after gh issue close creates irrecoverable split state

**Severity:** MEDIUM
**Category:** Error handling
**Location:** `kanban.py:398-428` (do_transition GitHub sync + rollback)

**Problem:** For `done` transitions, `do_transition` first closes the GitHub issue (line 406), then swaps labels (line 407-409). If the label swap fails (RuntimeError), the rollback (lines 413-416) reverts local state to `old_status`. But the issue is already closed on GitHub.

The code comments (BH28-001) acknowledge this ordering is deliberate and claim "next sync will fix it." This is true — the next `kanban.py sync` or `sync_tracking.py` run will see the closed issue and force local state to `done`. But there is a window problem:

1. Issue is closed on GitHub (irreversible without a separate reopen)
2. Local state is reverted to, say, `integration`
3. Before next sync runs, someone tries `kanban.py transition <story> done` again
4. `gh issue close` on an already-closed issue may fail (gh CLI returns non-zero for already-closed issues depending on version)
5. This triggers another rollback, leaving the story stuck in `integration` locally while `done` on GitHub

The only recovery is running `kanban.py sync` or `sync_tracking.py`, which will reconcile. But if the user keeps trying `transition` instead of `sync`, they're stuck in a retry loop that never succeeds.

**Evidence:**
```python
# kanban.py:405-409 — close first, then label swap
if target == "done":
    gh(["issue", "close", issue_num])  # succeeds
gh(["issue", "edit", issue_num,  # fails → rollback
    "--remove-label", f"kanban:{old_status}",
    "--add-label", f"kanban:{target}"])
```

The rollback error message says "GitHub update failed" but does not hint that the issue was already successfully closed and the user should run sync to reconcile.

---

## Finding 4: sync_tracking.py missing UNKNOWN story ID guard on create path

**Severity:** LOW (previously identified in phase 1 recon)
**Category:** Error handling
**Location:** `sync_tracking.py:293-308` (main loop, create path)

**Problem:** `kanban.py do_sync` checks `if story_id == "UNKNOWN": continue` (line 568) before creating tracking files. `sync_tracking.py` does not have this guard — `create_from_issue` is called for any issue in the milestone, including manually-filed bugs or spikes that lack a standard `[A-Z]+-\d+` ID.

**Evidence:**
```python
# kanban.py:568 — has UNKNOWN guard
if story_id == "UNKNOWN":
    changes.append(f"WARNING: issue #{issue_num} ...")
    continue

# sync_tracking.py:293-308 — no UNKNOWN guard
else:
    tf, changes = create_from_issue(issue, sprint, stories_dir, pr)
    atomic_write_tf(tf)
```

`extract_story_id` returns "UNKNOWN" only for empty/whitespace titles. An issue titled "Fix bug" produces slug "FIX-BUG" which passes the guard in kanban.py but creates a tracking file in both paths. The real gap is when `extract_story_id` returns "UNKNOWN" — sync_tracking will try to create a file named `UNKNOWN-{slug}.md` which could collide if multiple such issues exist.

---

## Finding 5: do_sync (kanban.py) does not update issue_number or other metadata on existing stories

**Severity:** LOW
**Category:** Status conflict / Completeness
**Location:** `kanban.py:531-564` (do_sync existing story handling)

**Problem:** When `do_sync` finds a matching local story, it only compares and potentially updates `status`. It does not sync `issue_number`, `pr_number`, `branch`, `completed`, or `sprint`. Compare with `sync_tracking.sync_one` (lines 156-182) which updates all of these fields.

This means `kanban.py sync` is a partial reconciliation — it handles state transitions but ignores metadata drift. If an issue was renumbered (rare but possible during repo transfer) or a PR was linked after the tracking file was created, `kanban.py sync` would not pick it up.

**Evidence:**
```python
# kanban.py:531-535 — only compares status
if story_id in local_by_id:
    tf = local_by_id[story_id]
    if tf.status == github_state:
        continue  # only checks status, ignores all other fields
```

vs. sync_tracking.sync_one which checks and updates: status, completed, pr_number, issue_number, sprint.

**Impact:** Minor. The two sync paths have complementary roles (stated in CLAUDE.md), and sprint-run uses sync_tracking for full reconciliation. But if someone only uses `kanban.py sync`, metadata fields can silently drift.

---

## Finding 6: WIP limit check reads stale file state when called from do_transition

**Severity:** LOW
**Category:** Race conditions
**Location:** `kanban.py:279-292` (check_wip_limit file scan)

**Problem:** `check_wip_limit` reads all story files in the stories directory to count how many are in the target state. This read happens inside `lock_sprint`, so no concurrent kanban.py process can mutate the files. However, `sync_tracking.py` fetches GitHub data OUTSIDE the lock (lines 264-285 in main: `issues = list_milestone_issues(mt)` and `all_prs = _fetch_all_prs()` happen before `with lock_sprint`). If sync_tracking and kanban.py run concurrently:

1. `kanban.py transition` acquires sprint lock, reads WIP count (0 in dev), writes story to dev
2. `kanban.py` releases lock
3. `sync_tracking.py` acquires sprint lock, has stale issue list from before step 1, writes its view of state

The lock prevents concurrent file writes, but the GitHub data feeding sync_tracking.py was fetched before the lock was acquired. This is an inherent limitation of the lock-after-fetch pattern.

**Evidence:**
```python
# sync_tracking.py main — fetch happens before lock
issues = list_milestone_issues(mt)  # line 264 — no lock
all_prs = _fetch_all_prs()           # line 285 — no lock
with lock_sprint(sprint_dir):        # line 292 — lock acquired AFTER fetch
    for issue in issues:
        ...  # uses stale data
```

**Impact:** In practice, low. The GitHub data is typically seconds old. And sync_tracking re-reads each tracking file under lock (line 298: `existing[sid.upper()] = read_tf(existing[sid.upper()].path)`), so it sees fresh local state. The stale data is only the GitHub issue list — if a kanban.py transition happened between fetch and lock, the GitHub labels may not yet reflect it (since kanban.py pushes labels to GitHub, which sync_tracking.py then re-fetches on next run). Self-healing on next cycle.

---

## Finding 7: append_transition_log is not atomic — body_text mutation can corrupt on concurrent read

**Severity:** LOW
**Category:** Transition log integrity
**Location:** `kanban.py:315-325` (append_transition_log)

**Problem:** `append_transition_log` mutates `tf.body_text` in-place. It is a pure in-memory operation (no file I/O), so it is not directly subject to file-level corruption. The caller (`do_transition`, `do_sync`, `sync_one`) is responsible for writing the result to disk via `atomic_write_tf`.

The actual integrity concern is: if two concurrent processes both hold TF objects read at different times and both call `append_transition_log` + `atomic_write_tf`, the second write silently overwrites the first's log entry. The sprint lock prevents this for kanban.py ↔ kanban.py and kanban.py ↔ sync_tracking.py concurrency. But there is no protection against a non-locking script (e.g., a future script or manual edit) appending to the log.

The `## Transition Log` header detection (line 321) uses a simple `in` check. If body_text contains the string "## Transition Log" in a different context (e.g., a comment about the transition log), the entry would be appended after that section rather than in the actual log. Unlikely but possible with sufficiently creative story descriptions.

**Evidence:**
```python
if tf.body_text and "## Transition Log" in tf.body_text:
    tf.body_text = tf.body_text.rstrip() + "\n" + log_entry
```

**Impact:** Low. The sprint lock serializes all production callers. The header ambiguity is theoretical.

---

## Finding 8: sync_tracking.py does not log transitions to GitHub (one-way sync gap)

**Severity:** LOW
**Category:** Status conflict
**Location:** `sync_tracking.py:148-154` (sync_one status update)

**Problem:** When `sync_tracking.sync_one` accepts a status change from GitHub, it appends a transition log entry locally but does not push anything back to GitHub. This is by design (sync_tracking reads from GitHub, does not write to it). But it means:

1. Manual label change on GitHub → sync_tracking accepts → local state updated → no confirmation sent to GitHub
2. If the label was manually changed to an intermediate state (e.g., someone adds `kanban:review` while removing `kanban:dev`), sync_tracking trusts it blindly
3. The local transition log captures the change but GitHub's timeline has no corresponding event

Compare with `kanban.py do_transition` which always writes labels to GitHub after local state change.

**Impact:** Informational. The local transition log serves as the audit trail. GitHub's issue timeline shows when labels were manually changed. The gap is in traceability — there is no single source that shows all state changes with timestamps and attribution.

---

## Finding 9: do_transition WIP limit check skipped when sprints_dir/sprint not provided

**Severity:** LOW
**Category:** WIP limit enforcement
**Location:** `kanban.py:378-386` (do_transition WIP check conditional)

**Problem:** The WIP limit check requires both `sprints_dir` and `sprint` parameters. When called programmatically (not via CLI), these can be None, causing the WIP check to be silently skipped. The code does print a warning (lines 384-386), but only to stderr, and returns True (success) regardless.

This means any programmatic caller that forgets to pass sprints_dir/sprint bypasses WIP enforcement entirely. The CLI `main()` always provides these values, so this only affects direct API callers.

**Evidence:**
```python
# kanban.py:378-386
if target in ("dev", "review", "integration") and not force_wip and sprints_dir and sprint is not None:
    wip_err = check_wip_limit(tf, target, sprints_dir, sprint)
    ...
# INT-8: Warn when WIP limit not checked due to missing context
if target in ("dev", "review", "integration") and not force_wip and (sprints_dir is None or sprint is None):
    print(f"{tf.story}: warning: WIP limit not checked ...", file=sys.stderr)
```

**Impact:** Low for current usage. All production callers go through CLI main(). Future programmatic callers could accidentally skip WIP limits.

---

## Finding 10: Prune deletes lock file but not .tmp file

**Severity:** LOW
**Category:** Error handling / Cleanup
**Location:** `kanban.py:601-604` (do_sync prune)

**Problem:** When pruning orphaned stories, `do_sync` deletes the tracking file and its `.lock` sentinel, but does not clean up any `.tmp` file that might exist from a crashed `atomic_write_tf`. The `.tmp` file is the intermediate file created during atomic writes (line 148: `tmp = tf.path.with_suffix(".tmp")`). If `atomic_write_tf` crashed between creating the temp file and the rename, a stale `.tmp` file would persist after pruning.

**Evidence:**
```python
# kanban.py:601-604
if prune:
    tf.path.unlink(missing_ok=True)
    lock_file = tf.path.with_suffix(".lock")
    lock_file.unlink(missing_ok=True)
    # no cleanup of .tmp file
```

**Impact:** Very low. The `.tmp` file would be a harmless orphan. It would not match `*.md` globs used by file scanning. Just a minor cleanliness issue.

---

## Finding 11: kanban.py do_sync skips precondition checks when accepting external transitions

**Severity:** MEDIUM
**Category:** Transition validation
**Location:** `kanban.py:550-559` (do_sync external transition acceptance)

**Problem:** When `do_sync` accepts a valid external transition from GitHub (line 551-559), it validates the transition graph via `validate_transition()` but does NOT check preconditions via `check_preconditions()`. This means an external state change to `dev` is accepted even if `branch` and `pr_number` are not set, and a change to `review` is accepted even if `implementer` and `reviewer` are not set.

`do_transition` (the local mutation path) checks both validation AND preconditions (lines 350, 361). `do_sync` only checks validation.

**Evidence:**
```python
# kanban.py do_transition (lines 350-362) — validates AND checks preconditions
err = validate_transition(tf.status, target)
if err: ...
err = check_preconditions(tf, target)
if err: ...

# kanban.py do_sync (lines 551-559) — validates only
err = validate_transition(tf.status, github_state)
if err is None:
    tf.status = github_state  # no precondition check
```

**Impact:** A story can reach `dev` or `review` state via external label change without the required metadata (branch, PR, reviewer). Downstream tooling that assumes preconditions are met for a given state may fail or produce confusing results. The sync_tracking path has the same gap (by design — it accepts any valid state). But kanban.py do_sync presents itself as the stricter path and still skips this check.

---

## Finding 12: create_from_issue (sync_tracking) sets branch to slug-based guess, not actual branch

**Severity:** LOW
**Category:** Error handling / Data accuracy
**Location:** `sync_tracking.py:220` (create_from_issue branch field)

**Problem:** When creating a new tracking file, `create_from_issue` sets the branch to `f"sprint-{sprint}/{slug}"[:255]` — a computed guess based on naming convention, not the actual branch from the linked PR. If the PR's branch name does not follow this convention, the tracking file has an incorrect branch field from creation.

The `pr` dict passed to `create_from_issue` contains `number`, `state`, and `merged` keys (from `get_linked_pr`), but NOT `headRefName` (the actual branch name). The branch name is available in the `_fetch_all_prs` result but is not propagated through `get_linked_pr` into `create_from_issue`.

**Evidence:**
```python
# sync_tracking.py:220
branch=f"sprint-{sprint}/{slug}"[:255],  # guessed, not actual

# sync_tracking.py:113-121 — get_linked_pr only returns number/state/merged
return {
    "number": pr["number"],
    "state": ...,
    "merged": ...,
}
# headRefName is available in pr dict but not included in return value
```

**Impact:** If the actual branch name differs from the convention, the tracking file has a stale/incorrect branch value. Subsequent `sync_one` calls do not update the branch field (it only updates status, completed, pr_number, issue_number, sprint). The branch field is only correctable via `kanban.py update --branch`.

---

## Summary

| # | Severity | Category | One-liner |
|---|----------|----------|-----------|
| 1 | MEDIUM | Status conflict | sync_tracking accepts any state; kanban.py do_sync validates transitions |
| 2 | LOW | Error handling | kanban.py do_sync has no duplicate ID warning or slug collision check |
| 3 | MEDIUM | Error handling | Rollback after gh issue close leaves irrecoverable split until sync |
| 4 | LOW | Error handling | sync_tracking missing UNKNOWN story ID guard (known from phase 1) |
| 5 | LOW | Completeness | kanban.py do_sync only syncs status, not metadata fields |
| 6 | LOW | Race conditions | sync_tracking fetches GitHub data outside lock (stale-data window) |
| 7 | LOW | Log integrity | append_transition_log header detection is string-match heuristic |
| 8 | LOW | Status conflict | sync_tracking does not write back to GitHub (one-way) |
| 9 | LOW | WIP enforcement | WIP check silently skipped without sprints_dir/sprint params |
| 10 | LOW | Cleanup | Prune does not remove .tmp files from crashed atomic writes |
| 11 | MEDIUM | Transition validation | kanban.py do_sync skips precondition checks on external transitions |
| 12 | LOW | Data accuracy | create_from_issue guesses branch name instead of using actual PR branch |

**3 MEDIUM, 9 LOW, 0 HIGH, 0 CRITICAL.**

The two-path design is fundamentally sound: kanban.py enforces invariants for local mutations, sync_tracking.py is permissive for reconciliation. The main risk area is Finding 1 + Finding 11 together — `kanban.py do_sync` presents itself as the validated sync path but still skips precondition checks, and `sync_tracking.py` skips transition validation entirely. A story can reach any state via manual GitHub label changes, bypassing review gates, WIP limits, and metadata preconditions regardless of which sync path runs.
