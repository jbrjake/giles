# Phase 3: Adversarial Code Audit

Audit date: 2026-03-18
Auditor: Claude Sonnet 4.6
Files audited: `scripts/kanban.py`, `scripts/validate_config.py` (lines 880–1183),
`skills/sprint-run/scripts/sync_tracking.py`, integration references.

---

### BH22-100: lock_story holds stale file descriptor after atomic_write_tf rename
**Severity:** HIGH
**Category:** `bug/race`
**Location:** `scripts/kanban.py:161-173`, `scripts/kanban.py:136-151`

**Problem:** `lock_story` opens the tracking file in `"r"` mode and acquires an exclusive `flock` on that file descriptor. `atomic_write_tf` then writes to a `.tmp` sibling and calls `os.rename(tmp, original)`, which atomically replaces the inode at the path. On Linux and macOS, `rename()` does not affect the old inode — the lock file descriptor now points to the unlinked (or replaced) inode, not to the new file content. Any competing process that opens the *new* file at the same path gets a fresh, unrelated file descriptor and can acquire its own `flock` independently because the lock is attached to the old inode.

Concrete race window: process A calls `lock_story`, opens fd #5 on inode X, flocks it. It then calls `atomic_write_tf`, which renames `.tmp` (inode Y) over the path, destroying inode X's directory entry. Process B now calls `lock_story`, opens fd #6 on inode Y (the new file at the same path), and acquires `LOCK_EX` on inode Y. Both processes now hold "exclusive" locks on different inodes and will simultaneously write, corrupting the file.

The sentinel-file approach in `lock_sprint` (`.kanban.lock`) avoids this because `lock_sprint`'s sentinel is never renamed. `lock_story` needs the same sentinel strategy.

**Acceptance Criteria:**
- [ ] `lock_story` uses a stable sentinel file (e.g., `tracking_path.with_suffix(".lock")`) that is never atomically replaced
- [ ] The lock file is created with `touch(exist_ok=True)` before opening, so the path always exists
- [ ] Tests confirm two concurrent processes cannot both complete a transition on the same story

---

### BH22-101: atomic_write_tf mutates tf.path — visible side effect under concurrent use
**Severity:** MEDIUM
**Category:** `bug/race`
**Location:** `scripts/kanban.py:143-151`

**Problem:** `atomic_write_tf` temporarily sets `tf.path = tmp` to redirect `write_tf` to the temp file, then restores `tf.path = original_path` in `finally`. If any code reads `tf.path` between the mutation and the `finally` (e.g., a debugger, a signal handler, or a multi-threaded caller), it will see the `.tmp` path. More practically: the `finally` only restores `tf.path` — if `write_tf` raises *before* the rename, `tf.path` is correctly restored but the caller's `TF` object now has a path pointing to where the write did not complete. A subsequent unconditional read of `tf.path` on the error path could pick up stale data from a previous on-disk state.

The bug is latent today (no multi-threaded callers), but the mutation of a shared dataclass field inside a utility function is a correctness hazard. The canonical fix is to write directly to the temp path without mutating `tf`.

**Acceptance Criteria:**
- [ ] `atomic_write_tf` does not mutate `tf.path`; instead, create a separate `TF` with `path=tmp` (or write the YAML directly without a TF)
- [ ] `tf.path` remains unchanged if `write_tf` raises during the temp write

---

### BH22-102: do_transition rollback fails silently if second atomic_write_tf also raises
**Severity:** HIGH
**Category:** `bug/logic`
**Location:** `scripts/kanban.py:258-263`

**Problem:** In `do_transition`, if the GitHub `gh()` call fails, the rollback path sets `tf.status = old_status` and calls `atomic_write_tf(tf)`. If this *second* `atomic_write_tf` call also raises (e.g., disk full, permission error, concurrent deletion of the stories directory), the exception propagates out of the `except RuntimeError` block uncaught. The story is now in `target` state on disk and `old_status` in memory, and the caller sees an exception rather than `False`. The function's documented contract ("returns False on failure, with local state reverted") is violated.

The disk is now inconsistent: local file says `target`, GitHub says `old_status`. The next `kanban.py sync` will accept the GitHub state as authoritative and silently overwrite the local file, but only if sync runs before the next transition attempt. Until then, any `validate_transition` call sees `target` as the current state and may allow or block transitions based on incorrect state.

```python
# do_transition lines 258-263 — rollback exception is not caught
except RuntimeError as exc:
    tf.status = old_status
    atomic_write_tf(tf)          # <-- uncaught if this raises
    print(f"{tf.story}: local state reverted. GitHub update failed: {exc}",
          file=sys.stderr)
    return False
```

**Acceptance Criteria:**
- [ ] The rollback `atomic_write_tf` is wrapped in a `try/except` that logs the dual-failure case and still returns `False`
- [ ] The error message in the dual-failure case explicitly states that both local and GitHub states are uncertain and `kanban.py sync` should be run
- [ ] Same pattern applied to `do_assign`'s rollback path (lines 303–307)

---

### BH22-103: do_assign partial-success leaves GitHub and local file inconsistent
**Severity:** HIGH
**Category:** `bug/logic`
**Location:** `scripts/kanban.py:285-308`

**Problem:** `do_assign` performs multiple sequential GitHub writes: add `persona:{implementer}` label, then add `persona:{reviewer}` label, then fetch the issue body, then update the issue body. Each step can fail independently. The rollback only reverts the *local* tracking file — it does not undo any GitHub labels already written.

If the reviewer label write succeeds but the body update fails:
1. GitHub has `persona:{implementer}` and `persona:{reviewer}` labels on the issue
2. The issue body still shows `[Unassigned]`
3. The local tracking file is reverted to old values

This produces a GitHub state that is inconsistent with both the old and new local state, and the local rollback hides the inconsistency. A subsequent `kanban.py assign` will add duplicate persona labels (GitHub's `--add-label` does not error on duplicates, so they silently stack).

**Acceptance Criteria:**
- [ ] Error message on partial failure explicitly states which GitHub operations succeeded before the failure
- [ ] A `--force` flag or idempotency guard prevents duplicate persona labels on retry
- [ ] Alternatively: the issue body pattern is made a `sub(..., count=1)` (see BH22-104) and a subsequent full re-run is safe

---

### BH22-104: _PERSONA_HEADER_PATTERN replaces ALL matches; no match is silently ignored
**Severity:** MEDIUM
**Category:** `bug/logic`
**Location:** `scripts/kanban.py:222-224`, `scripts/kanban.py:295-300`

**Problem 1 — multiple matches:** `_PERSONA_HEADER_PATTERN` matches `> **[Unassigned]** · Implementation` with `re.sub`, which replaces all non-overlapping occurrences. If an issue body was manually edited to include the header twice (e.g., copy-paste in GitHub's web UI), both occurrences are replaced. This produces a body with two persona headers, which is visually confusing and breaks the intent of the one-implementer assignment model.

The fix is `_PERSONA_HEADER_PATTERN.sub(..., body, count=1)` — replace only the first occurrence.

**Problem 2 — no match:** If the issue body was manually edited before `do_assign` runs (e.g., the `[Unassigned]` text was removed or the body was rewritten), the regex finds no match. `new_body == body`, so the `if new_body != body:` guard skips the edit silently. The local tracking file is updated with the implementer name, but the GitHub issue body still shows whatever the manual edit left. No warning is printed. The operator has no indication that the body was not updated.

**Acceptance Criteria:**
- [ ] Replace only the first occurrence using `count=1` in `re.sub` to prevent double-replacement
- [ ] Log a warning to stderr when `new_body == body` (no pattern match found), advising manual update of the issue body

---

### BH22-105: find_story prefix match has false positive for numeric story IDs
**Severity:** LOW
**Category:** `bug/logic`
**Location:** `scripts/kanban.py:208-213`

**Problem:** `find_story` matches files whose uppercased stem `startswith(prefix + "-")`. The intent is to match `US-0042-some-feature.md` for story ID `US-0042`. However, if story IDs are purely numeric after the prefix (e.g., `US-1` and `US-10` both exist), the comparison for `US-1` would match `US-1-foo.md` correctly, but would also match `US-10-bar.md` because `"US-10-BAR".startswith("US-1" + "-")` is `False` — this specific example is actually safe.

The real hazard: IDs like `US-001` and `US-0011`. The `startswith("US-001-")` check for story `US-001` would NOT falsely match `US-0011-feature.md` because the separator is `"-"`, not a digit. But `extract_story_id` uses `re.match(r"([A-Z]+-\d+)", title)`, which matches `US-0011` in the title `US-0011: Feature`. So `find_story("US-0011", ...)` calls `prefix = "US-0011"`, and only files starting with `US-0011-` are matched. This is safe.

The *actual* false positive occurs with the exact-stem match (`stem == prefix`). If a file is named exactly `US-0042.md` (no slug), and story ID `US-0042` is searched, the `stem == prefix` check matches correctly. But if someone creates `US-0042.md` for story `US-042` (extra zero), both `stem == "US-0042"` and `stem.startswith("US-042-")` paths miss each other — no false positive but potentially a missed story.

The more dangerous case: `find_story` returns the *first* sorted match and silently ignores subsequent matches. If two files match (possible when a story is duplicated by `do_sync`), the second is silently ignored. No warning is logged.

**Acceptance Criteria:**
- [ ] When `find_story` finds more than one matching file, log a warning to stderr listing all matches and return the first
- [ ] Document the exact matching semantics in the docstring

---

### BH22-106: lock_story requires the file to exist — fails if called on a new story
**Severity:** MEDIUM
**Category:** `bug/logic`
**Location:** `scripts/kanban.py:168`

**Problem:** `lock_story` opens `tracking_path` in `"r"` mode. If the file does not exist, `open()` raises `FileNotFoundError`. The `main()` function calls `find_story` first and only calls `lock_story(tf.path)` if a TF was returned, which guarantees the file exists for the `transition` and `assign` commands.

However, `do_sync` calls `atomic_write_tf` to create *new* tracking files without any lock. There is no protection against two concurrent `kanban.py sync` processes both deciding that the same new story does not exist locally and both creating a file for it — the second rename clobbers the first silently. This is a coordination gap between `do_sync` (which uses `lock_sprint`) and new-file creation within that lock (which is correctly protected), but the documentation of `lock_story` ("The file must already exist") creates a maintenance trap if a future caller tries to use it on a new story.

A secondary issue: `do_sync` is called inside `lock_sprint`, which protects the sprint directory's `.kanban.lock` sentinel. This provides sprint-level serialization for `sync` commands. But `transition` and `assign` only use `lock_story`, not `lock_sprint` — so a concurrent `sync` and `transition` can race on the same story if `sync` is creating a new file for that story at the same time.

**Acceptance Criteria:**
- [ ] Document clearly that `lock_story` must only be called on existing files
- [ ] `do_sync`'s new-file creation path is already inside `lock_sprint` — confirm this is documented as the reason no additional lock is needed
- [ ] Add a guard in `main()` for `transition` and `assign` that acquires `lock_sprint` first, then `lock_story`, to prevent the sync+transition race (or document why this race is acceptable)

---

### BH22-107: sprint=0 accepted silently when detect_sprint() returns None
**Severity:** MEDIUM
**Category:** `bug/logic`
**Location:** `scripts/kanban.py:464`

**Problem:** The sprint resolution is:
```python
sprint = args.sprint or detect_sprint(sprints_dir)
```
If `args.sprint` is `0` (passed explicitly as `--sprint 0`), Python evaluates `0 or detect_sprint(sprints_dir)`, which calls `detect_sprint` because `0` is falsy. If `detect_sprint` returns a valid integer, that integer is used — silently ignoring the user's explicit `--sprint 0`. If `detect_sprint` also returns `None`, the `if sprint is None` check correctly exits. But if the user genuinely meant sprint 0 (not a typical sprint number but not impossible), their explicit argument is silently discarded.

More practically: if a user accidentally types `--sprint 0`, they get behavior from the auto-detected sprint with no indication their flag was ignored.

**Acceptance Criteria:**
- [ ] Replace `args.sprint or detect_sprint(sprints_dir)` with `detect_sprint(sprints_dir) if args.sprint is None else args.sprint`
- [ ] This matches the pattern used elsewhere in the codebase for optional int arguments

---

### BH22-108: frontmatter_value regex `.+` can consume a multiline value's first line only, returning truncated data
**Severity:** MEDIUM
**Category:** `bug/logic`
**Location:** `scripts/validate_config.py:905`

**Problem:** The regex `rf"^{key}:\s*(.+)"` uses `.+` without `re.DOTALL`, so `.` does not match `\n`. This is intentional for YAML: each field is one line. However, `_yaml_safe` now escapes `\n` as `\\n` (literal backslash-n) before quoting, so a value containing a real newline is stored as `"line1\\nline2"` in the frontmatter. When read back, `frontmatter_value` captures `"line1\\nline2"` as a single line (correct), strips quotes, and unescapes `\\"` and `\\\\`. But the unescape order is `replace('\\"', '"').replace('\\\\', '\\')`.

**Actual exploit path for empty implementer:** If an implementer name is the empty string `""`, `_yaml_safe("")` returns `""` (falsy early return, no quoting). `write_tf` writes `implementer: ` (no value). When `frontmatter_value` is called with `key="implementer"`, the regex `r"^implementer:\s*(.+)"` requires at least one character after the optional whitespace. An empty value matches nothing — `m` is `None` — and the function returns `None`. The caller `read_tf` uses `v("implementer") or ""` so the empty string is correctly recovered. This path is safe.

**The real bug:** `_yaml_safe` does not quote values that are purely numeric strings (e.g., a persona named `"007"` or a branch named `"123"`). `write_tf` emits `implementer: 007`. When read back by a real YAML parser (not `frontmatter_value`), `007` is an octal literal. `frontmatter_value` is not a real YAML parser so it returns the string `"007"` correctly — but any tool or script that passes tracking files through a real YAML parser will misread numeric-looking values. This is a latent cross-tool compatibility bug.

**Acceptance Criteria:**
- [ ] `_yaml_safe` should quote values that are purely numeric strings (match `r"^\d+$"`) to prevent YAML parser misinterpretation by third-party tools
- [ ] Add a test case for `_yaml_safe("007")` returning `'"007"'`

---

### BH22-109: write_tf does not apply _yaml_safe to implementer, reviewer, status, pr_number, issue_number, started, completed
**Severity:** MEDIUM
**Category:** `bug/logic`
**Location:** `scripts/validate_config.py:1088-1096`

**Problem:** `write_tf` calls `_yaml_safe` on `story`, `title`, and `branch`, but writes `implementer`, `reviewer`, `status`, `pr_number`, `issue_number`, `started`, and `completed` as raw interpolated strings:

```python
f"implementer: {tf.implementer}",
f"reviewer: {tf.reviewer}",
f"status: {tf.status}",
```

A persona name containing a YAML-sensitive character — e.g., `implementer: "Alice: the Architect"` — would write `implementer: Alice: the Architect`, which is an invalid YAML mapping value (looks like a nested key). `frontmatter_value` would still parse it correctly (it just grabs everything after `implementer:\s+`), but the file would be malformed YAML for any real YAML parser.

More importantly, a reviewer name like `null` or `true` or `yes` would be written unquoted and misread by a YAML parser as boolean/null. The `_yaml_safe` function explicitly handles these YAML keywords, but it is not applied to these fields.

In practice, persona names come from controlled config and are unlikely to contain YAML-special characters. The `status` field is always one of the six KANBAN_STATES (all lowercase alpha, safe). `pr_number` and `issue_number` are always digit strings or empty. `started` and `completed` are ISO date strings (safe). The real risk is `implementer` and `reviewer`, which come from user-controlled config or GitHub labels.

**Acceptance Criteria:**
- [ ] Apply `_yaml_safe` to `implementer` and `reviewer` fields in `write_tf`
- [ ] Add a note in `write_tf` explaining which fields are safe to write without quoting and why

---

### BH22-110: sync_tracking.py and kanban.py do_sync are architecturally dual-write with no coordination
**Severity:** HIGH
**Category:** `bug/integration`
**Location:** `skills/sprint-run/scripts/sync_tracking.py:252-259`, `scripts/kanban.py:312-381`

**Problem:** Two independent code paths can modify the same story tracking files:

1. `kanban.py sync` — calls `do_sync()`, acquires `lock_sprint`, fetches issues from GitHub, and writes tracking files via `atomic_write_tf`.
2. `sync_tracking.py` — called by `sprint-monitor` and by the sprint-run story dispatch path, also fetches issues from GitHub and writes tracking files via `write_tf` (non-atomic).

These two sync paths disagree on several behaviors:
- `sync_tracking.py` uses non-atomic `write_tf` (not `atomic_write_tf`), so it has no rename safety
- `sync_tracking.py` accepts *any* state change from GitHub without validating the transition; `do_sync` calls `validate_transition` and logs illegal transitions as warnings
- `sync_tracking.py` fills in `pr_number`, `branch`, `implementer` (from PR lookup), and `completed` (from `closedAt`); `do_sync` only syncs `status` and creates bare TF objects (no PR linkage at all)
- Neither holds a lock that prevents the other from running concurrently

If `sprint-monitor` runs `sync_tracking.py` while `sprint-run` uses `kanban.py sync`, the two writes race. The last write wins. The winner depends on OS scheduling, not intent. A `sync_tracking.py` write could clobber a `kanban.py`-written file that had the correct new state from a just-completed transition.

The inconsistency in PR/branch fields is the most damaging: `do_sync` creates a new story TF with empty `pr_number` and `branch`. If the story already has a PR, a subsequent `sync_tracking.py` run will correctly fill those fields in, but until then, `check_preconditions` for `dev` will fail because `tf.pr_number` is empty.

**Acceptance Criteria:**
- [ ] Define a single canonical sync path. The recommendation: `sync_tracking.py` is the canonical syncer (it fills in all fields); `kanban.py sync` should either call `sync_tracking`'s logic or be deprecated in favor of `sync_tracking.py`
- [ ] If both are kept: `do_sync` must also populate `pr_number` and `branch` from a PR lookup, matching `sync_tracking.create_from_issue`
- [ ] Both sync paths must use `lock_sprint` to prevent concurrent writes
- [ ] `sync_tracking.py` should use `atomic_write_tf` instead of `write_tf`

---

### BH22-111: do_sync uses extract_story_id on GitHub issue titles — fallback slug is not uppercase
**Severity:** LOW
**Category:** `bug/logic`
**Location:** `scripts/kanban.py:333-334`

**Problem:** `do_sync` calls `extract_story_id(title).upper()` and adds the result to `github_ids`. However, `extract_story_id`'s fallback path (when no `[A-Z]+-\d+` pattern matches) returns a lowercase slug like `"my-story"`. The `.upper()` call converts it to `"MY-STORY"`. The local index `local_by_id` is built with `tf.story.upper()` (line 325). So comparison is consistent.

But when a new TF is created (line 362), it uses `story=story_id` where `story_id` is already `.upper()`'d. So the created TF's `story` field is `"MY-STORY"`, and if the tracking file is later read back and `tf.story` is used for display, it will show in uppercase even though the GitHub title had lowercase. This is a cosmetic issue but could confuse operators comparing story IDs against GitHub titles.

More critically: on the next sync run, `extract_story_id(title)` returns `"my-story"` (lowercase), `.upper()` gives `"MY-STORY"`, `local_by_id["MY-STORY"]` matches, and the story is treated as existing — correct. So there is no infinite re-creation loop. But the root problem is that `extract_story_id` should return uppercase slugs consistently without the caller needing to remember to call `.upper()`.

**Acceptance Criteria:**
- [ ] `extract_story_id`'s fallback path should return an uppercase result to match the `[A-Z]+-\d+` convention
- [ ] Or: document clearly that all callers must call `.upper()` on the result and audit all call sites

---

### BH22-112: kickoff exit criteria call kanban.py assign before tracking files exist
**Severity:** HIGH
**Category:** `bug/integration`
**Location:** `skills/sprint-run/references/ceremony-kickoff.md:257-259`

**Problem:** The kickoff exit criteria (step 5) instructs:
```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py" assign {story_id} --implementer {impl} --reviewer {rev}
```
But `kanban.py assign` calls `find_story(args.story_id, sprints_dir, sprint)`, which looks for a file in `sprint-{N}/stories/`. Tracking files are created by `sync_tracking.py` or `kanban.py sync`, neither of which is called as part of the kickoff ceremony. The kickoff creates GitHub issues (via Phase 1 in `sprint-run/SKILL.md`), but does not explicitly sync those issues to local tracking files first.

If `find_story` returns `None`, `main()` prints an error and exits with code 1. The kickoff's `assign` step fails silently in an automated run, and the persona assignments are never recorded in the local tracking files or GitHub. Development then starts with stories in an unassigned state, causing the `design` precondition check (`tf.implementer must be set`) to fail.

The ceremony-kickoff.md says to run `assign` at exit, but neither that file nor `SKILL.md` Phase 1 includes a step to run `kanban.py sync` (or `sync_tracking.py`) to create the tracking files first.

**Acceptance Criteria:**
- [ ] `ceremony-kickoff.md` exit criteria must include a step to run `kanban.py sync --sprint {N}` before the `assign` loop
- [ ] Or: `kanban.py assign` should auto-create a minimal tracking file if none exists (using `do_sync` internally for the single story)
- [ ] `SKILL.md` Phase 1 should explicitly state that tracking files are created as part of kickoff before persona assignment

---

### BH22-113: implementer.md calls kanban.py transition with story_id from template, but story_id is the US-XXXX ID not the GitHub issue number
**Severity:** LOW
**Category:** `design/gap`
**Location:** `skills/sprint-run/agents/implementer.md:133`

**Problem:** The implementer agent template shows:
```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py" transition {story_id} design --sprint {sprint_number}
```
Where `{story_id}` is documented as e.g. `US-0042`. This is correct — `find_story` matches on the `[A-Z]+-\d+` ID. However, the template also says "After creating the draft PR, update the tracking file with `pr_number` and `branch` fields" but does not show the mechanism. The implementer is expected to manually edit the tracking file YAML frontmatter to set `pr_number` before calling `kanban.py transition {story_id} dev`, since the `dev` precondition requires `pr_number` to be set.

There is no `kanban.py set-field` or similar command to update individual tracking file fields. The only way to set `pr_number` and `branch` is to directly write the YAML frontmatter. This is fragile: the implementer subagent must know the exact YAML frontmatter format, write it correctly without corrupting the file, and not trigger the `frontmatter_value` regex edge cases.

Additionally, `story-execution.md` step 4 shows running `kanban.py transition {story_id} design` *without* first setting `pr_number` or `branch`, then later transitioning to `dev` *with* those fields set. But there is no documented step for how the subagent updates the tracking file between those two transitions.

**Acceptance Criteria:**
- [ ] Add a `kanban.py update <story_id> --pr-number N --branch NAME` subcommand that safely updates individual tracking file fields
- [ ] Or: document explicitly in `implementer.md` that the agent should use `write_tf` through a one-liner Python invocation to update fields, with the exact command shown
- [ ] `story-execution.md` should include an explicit "update tracking file" step between the design and dev transitions

---

### BH22-114: slug_from_title returns "untitled" for empty string, but empty title is not guarded upstream
**Severity:** LOW
**Category:** `bug/logic`
**Location:** `scripts/validate_config.py:997-1003`

**Problem:** `slug_from_title("")` strips non-alphanumeric characters, leaving an empty string after `.strip()`, which causes the final `return slug if slug else "untitled"` to return `"untitled"`. This is the correct fallback.

But `do_sync` calls `slug_from_title(short_title(title))` where `short_title(title)` returns `title.split(":", 1)[-1].strip()`. For a GitHub issue titled `:` (just a colon), `short_title(":")` returns `""` (empty string after the colon, stripped). `slug_from_title("")` returns `"untitled"`. `do_sync` creates a file named `"UNKNOWN-untitled.md"` (if `extract_story_id` also falls back). No error is raised.

On the next sync, the issue titled `:` will match the local file because `local_by_id` is keyed by story_id (not slug), so no duplicate is created. But the file is named `UNKNOWN-untitled.md` and the `story` field in frontmatter is `"UNKNOWN"` — a legitimate confusion source and potential collision if two malformed issues exist.

This is an edge case for deliberately malformed issue titles, but worth guarding.

**Acceptance Criteria:**
- [ ] `do_sync` and `create_from_issue` should log a warning when `extract_story_id` returns the fallback `"unknown"` slug (indicating no real story ID was found), and skip creating a tracking file for such issues
- [ ] Add a test for a GitHub issue with no recognizable story ID in the title

---

### BH22-115: do_transition closes GitHub issue for "done" but does not handle partial success (label edited, close fails)
**Severity:** MEDIUM
**Category:** `bug/logic`
**Location:** `scripts/kanban.py:251-255`

**Problem:** `do_transition` for `target == "done"` makes two sequential GitHub calls:
1. `gh issue edit ... --remove-label kanban:integration --add-label kanban:done`
2. `gh issue close {issue_num}`

If call 1 succeeds but call 2 fails, the `except RuntimeError` block reverts the local file to `old_status` (integration) and tries to remove the `kanban:done` label and re-add `kanban:integration`. But the rollback only calls `atomic_write_tf` — it does not undo the GitHub label swap. After the failure:
- Local file: `integration` (reverted correctly)
- GitHub labels: `kanban:done` (not reverted)
- GitHub issue state: open (close failed)

This produces a GitHub issue with `kanban:done` label that is not closed. `kanban_from_labels` will return `"done"`, but the next `sync_tracking.py` run will see a closed-issue override only if the issue is actually closed (it checks `issue.get("state") == "closed"`). Since the issue is *open* with a `kanban:done` label, `kanban_from_labels` returns `"done"` without the override. The sync will write `status=done` to the local file, which conflicts with the reverted `integration` state.

The rollback in `do_transition` needs to undo GitHub labels when reverting, not just the local file.

**Acceptance Criteria:**
- [ ] When `do_transition` catches a RuntimeError after the label edit but during the close, it must also attempt to revert the GitHub labels (swap `kanban:done` back to `kanban:{old_status}`) and log which reversal operations failed
- [ ] The error message should include explicit instructions to run `kanban.py sync` to re-establish consistency

---

### BH22-116: do_sync ignores local stories absent from GitHub without offering resolution
**Severity:** LOW
**Category:** `design/gap`
**Location:** `scripts/kanban.py:374-379`

**Problem:** When a local story has no corresponding GitHub issue, `do_sync` appends a `WARNING: local story {story_id} not found on GitHub` string to the changes list. This is printed to stdout. No further action is taken — the local file is left as-is.

This creates a class of permanently-warning stories. Every subsequent `kanban.py sync` will repeat the warning. There is no mechanism to acknowledge the warning, delete the orphaned file, or create the missing GitHub issue. In a long-running sprint, operators will habituate to the warning and miss genuinely new orphans.

**Acceptance Criteria:**
- [ ] Document the expected operator action when this warning fires (e.g., "run `kanban.py sync --repair` to create missing GitHub issues or delete orphaned local files")
- [ ] Consider adding a `--repair` flag to `kanban.py sync` that offers to delete orphaned local tracking files after confirmation

---

### BH22-117: sync_tracking.py create_from_issue uses full title slug (not story ID prefix) for filename
**Severity:** MEDIUM
**Category:** `bug/integration`
**Location:** `skills/sprint-run/scripts/sync_tracking.py:167-171`

**Problem:** `create_from_issue` builds the filename as:
```python
slug = slug_from_title(issue["title"])
target = d / f"{slug}.md"
```
This uses the *full* title slug (e.g., `us-0042-implement-the-parser.md`), not the `story_id + "-" + short_title_slug` pattern that `do_sync` in `kanban.py` uses (e.g., `US-0042-implement-the-parser.md`). Specifically: `slug_from_title` lowercases everything, while `do_sync` uses `f"{story_id}-{slug}.md"` where `story_id` is already `.upper()`'d.

The result: the same GitHub issue produces a file named `us-0042-implement-the-parser.md` when created by `sync_tracking.py`, and `US-0042-implement-the-parser.md` when created by `kanban.py sync`. `find_story` matches with `stem.upper()`, so both files are found correctly. But if both sync paths run on a fresh sprint (no local files yet), whichever runs first creates a file, and the second path uses `d / f"{slug}.md"` or `d / f"{story_id}-{slug}.md"` respectively — they produce different filenames and the second creates a duplicate.

`sync_tracking.py`'s collision detection (lines 174-178) checks for an existing file at the slug path, but the `kanban.py`-generated uppercase filename would not collide with the lowercase path, so the duplicate passes the check.

**Acceptance Criteria:**
- [ ] Both sync paths should produce identically-named files for the same issue. Standardize on `{STORY_ID}-{short_slug}.md` (uppercase ID, lowercase slug)
- [ ] `create_from_issue` should use `f"{sid}-{slug_from_title(short_title(issue['title']))}.md"` instead of `f"{slug_from_title(issue['title'])}.md"`

