# Kanban State Machine Design

**Date:** 2026-03-17
**Status:** Draft

## Problem

Kanban state transitions are scattered across 4+ files as LLM prompt
instructions. Nobody reliably executes them. The result:

- Issues stay `kanban:todo` through their entire lifecycle
- Issues show `[Unassigned]` after personas are assigned at kickoff
- PRs in review still have `kanban:dev` on their issue
- `sync_tracking.py` reads from GitHub but never writes back

The root cause: no single owner for state transitions, no enforcement,
no atomicity.

## Solution

A centralized state machine script (`scripts/kanban.py`) that owns all
story state. Local tracking files are the source of truth. GitHub is a
downstream reflection synced on every mutation.

## Architecture Inversion

Current data flow (GitHub authoritative):
```
GitHub labels → sync_tracking.py → local tracking files
```

New data flow (local state authoritative):
```
kanban.py → local tracking files → GitHub sync (write-through)
                                ← GitHub sync (bidirectional merge via sync subcommand)
```

## State Model

Each story has:

| Field | Source | Mutated by |
|---|---|---|
| `status` | Tracking file YAML frontmatter | `kanban.py transition` |
| `implementer` | Tracking file YAML frontmatter | `kanban.py assign` |
| `reviewer` | Tracking file YAML frontmatter | `kanban.py assign` |
| `issue_number` | Tracking file YAML frontmatter | `kanban.py sync` (on creation) |
| `pr_number` | Tracking file YAML frontmatter | Agent (unchanged) |
| `branch` | Tracking file YAML frontmatter | Agent (unchanged) |

The tracking files (`sprint-{N}/stories/*.md`) are the authoritative store.
`kanban.py` is the exclusive writer for `status`, `implementer`, and `reviewer`.
Agents can still write to the body text (design notes, etc.) and to `pr_number`
and `branch` fields.

**Agent responsibility:** The implementer agent must write `pr_number` and
`branch` to the tracking file during the design phase (after creating the
draft PR). The `design → dev` transition checks that these fields are set
and fails with a clear error if they're missing. This is an explicit
contract: `kanban.py` owns state transitions, agents own PR/branch metadata.

## Transition Table

```
todo → design        requires: implementer assigned
design → dev         requires: branch set, pr_number set (draft PR exists)
dev → review         requires: implementer assigned, reviewer assigned
review → dev         (changes requested — no new preconditions)
review → integration requires: (approval — validated by caller)
integration → done   requires: pr merged (checked via gh)
```

Illegal transitions are rejected with an error explaining what's wrong
and what to do instead.

## Command Interface

All commands are atomic: local tracking file update + GitHub sync in one
call. If the GitHub call fails, the local write rolls back.

Sprint number is auto-detected from `SPRINT-STATUS.md` unless `--sprint`
overrides.

### `kanban.py transition <story-id> <target-state> [--sprint N]`

1. Load tracking file for the story
2. Validate current → target is a legal transition
3. Check preconditions from transition table
4. Update tracking file `status` field (atomic write)
5. Swap GitHub issue label: remove old `kanban:*`, add new `kanban:*`
6. If transitioning to `done`: close the GitHub issue
7. Print: `US-0042: dev → review`

### `kanban.py assign <story-id> --implementer <name> [--reviewer <name>] [--sprint N]`

1. Load tracking file
2. Write `implementer` and/or `reviewer` fields (atomic write)
3. Update GitHub issue body: replace `> **[Unassigned]** · Implementation`
   with `> **{persona_name}** · {persona_role} · Implementation`
4. Add `persona:{name}` label(s) to the GitHub issue
5. Print: `US-0042: assigned implementer=rae, reviewer=chen`

### `kanban.py sync [--sprint N]`

Bidirectional merge. The only command that reads FROM GitHub:

1. Fetch all issues in the sprint milestone
2. For each issue:
   - **Exists locally, same state:** no-op
   - **Exists locally, different state:** validate GitHub state is a legal
     transition from local state. Accept if legal, warn if illegal.
   - **New issue (no local tracking file):** create tracking file from
     issue data, accept whatever state GitHub shows.
3. For each local story not on GitHub: warn (externally deleted?)

No outbound push. Mutations push on their own.

### `kanban.py status [--sprint N]`

Read-only board view from local tracking files. No GitHub calls.

```
Sprint 3 — 12 SP

TODO (2):  US-0045 (3 SP, unassigned), US-0046 (2 SP, rae)
DEV (1):   US-0042 (5 SP, rae → chen)
REVIEW (1): US-0043 (2 SP, chen → rae)
DONE (2):  US-0041, US-0044
```

## GitHub Sync Details

### Label management

Each transition swaps one `kanban:*` label for another:
```bash
gh issue edit {number} --remove-label "kanban:{old}" --add-label "kanban:{new}"
```

The `assign` command adds persona labels:
```bash
gh issue edit {number} --add-label "persona:{implementer}" --add-label "persona:{reviewer}"
```

### Issue body update (assign only)

Read current body via `gh issue view --json body`, replace the persona
header line, write back via `gh issue edit --body`. Only the `assign`
command touches the issue body.

### Issue close (done only)

`gh issue close {number}` when transitioning to `done`.

### Rollback strategy

1. Read current tracking file state (snapshot)
2. Write new local state (atomic write)
3. Attempt GitHub call(s)
4. If GitHub fails: restore snapshot, print error, exit non-zero

For commands with multiple GitHub calls (e.g., `assign` does label add +
body update), if the second call fails after the first succeeded, the
error message includes what was partially applied. Full transactional
rollback across multiple `gh` calls isn't worth the complexity — the
partial state is still valid, just incomplete.

## Concurrency

Parallel agent dispatch means multiple implementers could transition
different stories simultaneously, and `sync` could run while a transition
is in progress.

### Atomic file writes

All tracking file updates go through write-to-temp-then-rename:
```python
def atomic_write(path: Path, content: str):
    tmp = path.with_suffix(".tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.rename(path)  # POSIX rename is atomic
```

Readers never see a half-written file.

### File locking with `fcntl.flock()`

- **Per-story lock:** `transition` and `assign` acquire an exclusive lock
  on the tracking file before read-modify-write.
- **Sprint-level lock:** `sync` acquires an exclusive lock on
  `sprint-{N}/.kanban.lock` before processing, then locks individual
  story files as it processes them.
- **Lock ordering:** single-story commands lock only the tracking file.
  `sync` locks sprint lock first, then story files. Single lock hierarchy
  prevents deadlocks.

```python
@contextmanager
def lock_story(tracking_path: Path):
    fd = open(tracking_path, "r")
    fcntl.flock(fd, fcntl.LOCK_EX)
    try:
        yield
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        fd.close()
```

Advisory locks, released automatically on process death. `fcntl` is
stdlib, macOS and Linux only. Windows-native Python is unsupported —
`kanban.py` uses a guarded import that exits with a clear error message
if `fcntl` is unavailable:

```python
try:
    import fcntl
except ImportError:
    sys.exit("kanban.py requires POSIX file locking (fcntl). "
             "Run on macOS, Linux, or WSL.")
```

## Integration with Existing Code

### What it replaces

**`sync_tracking.py`** — the `sync` subcommand absorbs its core purpose.
`sync_one()` and `create_from_issue()` logic moves into `kanban.py`.
The old script becomes a thin wrapper or gets removed.

**Shared tracking file I/O:** The `TF` dataclass, `read_tf()`, `write_tf()`,
and `_yaml_safe()` currently live in `sync_tracking.py`. These are extracted
into `validate_config.py` (the shared utilities module) so `kanban.py` can
import them directly. This removes `kanban.py`'s dependency on
`sync_tracking.py` and makes the deprecation path clean.

**Scattered `gh issue edit` commands** in agent prompts and reference
docs — all replaced with `kanban.py` calls:

| Current | Replacement |
|---|---|
| `gh issue edit {n} --remove-label "kanban:todo" --add-label "kanban:design"` | `kanban.py transition {story_id} design` |
| `gh issue edit {n} --remove-label "kanban:dev" --add-label "kanban:review"` | `kanban.py transition {story_id} review` |
| `gh issue edit {n} --remove-label "kanban:review" --add-label "kanban:done"` / `gh issue close` | `kanban.py transition {story_id} done` |
| Manual persona update on issue body | `kanban.py assign {story_id} --implementer rae --reviewer chen` |

### Files that need updating

| File | Change |
|---|---|
| `skills/sprint-run/agents/implementer.md` | Replace raw `gh issue edit` label commands with `kanban.py transition` and `kanban.py assign` |
| `skills/sprint-run/references/story-execution.md` | Replace all `gh issue edit` label commands with `kanban.py` calls |
| `skills/sprint-run/references/kanban-protocol.md` | Update "GitHub Label Sync" section to reference `kanban.py` |
| `skills/sprint-run/SKILL.md` | Add note that all state changes go through `kanban.py` |
| `skills/sprint-run/references/ceremony-kickoff.md` | Add exit criteria step: run `kanban.py assign` for each story |
| `skills/sprint-run/scripts/sync_tracking.py` | Deprecate or thin wrapper around `kanban.py sync` |
| `skills/sprint-run/references/tracking-formats.md` | Update source-of-truth statement: local tracking files are authoritative, not GitHub |

### What it does NOT replace

- **PR labels** — implementer still applies labels to PRs via `gh pr create --label` and `gh pr edit --add-label`. State machine manages issue state, not PR metadata.
- **PR operations** — `gh pr create`, `gh pr ready`, `gh pr merge` stay in agent prompts. The state machine doesn't own the PR lifecycle (future scope).
- **Burndown and sprint status** — `update_burndown.py` still reads tracking files independently.

### Import chain

`kanban.py` lives in `scripts/` alongside `validate_config.py`. Imports
`load_config`, `kanban_from_labels`, `extract_story_id`, `find_milestone`,
`list_milestone_issues`, `gh`, `gh_json` from `validate_config.py`.

## Error Handling

| Scenario | Behavior |
|---|---|
| Story not found | `US-9999: no tracking file found in sprint {N}. Run 'kanban.py sync' to pull new issues from GitHub.` |
| Illegal transition | `US-0042: cannot transition dev → done. Legal transitions from dev: review.` |
| Precondition not met | `US-0042: cannot transition todo → design — no implementer assigned. Run 'kanban.py assign' first.` |
| GitHub API failure | Revert tracking file. `US-0042: local state reverted. GitHub update failed: {error}. Retry with same command.` |
| Sync finds illegal external transition | `US-0042: GitHub shows kanban:review but local state is todo. Illegal transition. Fix GitHub label or advance through legal states.` |
| Sync finds new issue | `US-0050: new issue discovered on GitHub. Created tracking file (status=todo).` |
| Sync finds missing issue | `US-0042: exists locally but not found on GitHub. Issue may have been deleted externally.` |

## Future Scope

- **PR lifecycle management** — wrap `gh pr create`, `gh pr ready`, `gh pr merge` into the state machine so PR state is also centrally managed.
- **Event hooks** — run callbacks on transitions (e.g., auto-trigger burndown update on `done`).
