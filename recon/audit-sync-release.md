# Adversarial Audit: Sync, Tracking, and Release Scripts

**Scope:** sync_tracking.py, sync_backlog.py, release_gate.py, check_status.py
**Date:** 2026-03-16
**Auditor:** Claude Opus 4.6

---

## Findings

### 1. MEDIUM — Race: sync_tracking overwrites local edits without conflict detection

**File:** `skills/sprint-run/scripts/sync_tracking.py`, `sync_one()` (line 233)

GitHub is authoritative by design, but `sync_one()` unconditionally overwrites
local tracking file fields (status, pr_number, issue_number, sprint) with
GitHub state. If a human has manually edited a tracking file (e.g., added notes
to the body, corrected a field) *between* GitHub state changes, and the script
runs, `write_tf()` will overwrite the entire file. The `body_text` field IS
preserved through read/write, but any manual edits to frontmatter YAML fields
(implementer, reviewer, branch, started) that are NOT synced from GitHub will
survive only by accident -- they are never explicitly saved back unless the TF
is dirty.

**Actually, correction on re-read:** The `sync_one()` function only mutates
fields it explicitly sets (status, completed, pr_number, issue_number, sprint),
and only calls `write_tf()` when changes are detected. Other fields
(implementer, reviewer, branch, started, body_text) ARE preserved through the
read-modify-write cycle. This is safer than it first appears. **Downgrade: LOW.**

The remaining concern is non-atomic write: `write_tf()` calls
`path.write_text()` which is not atomic on all platforms. A crash mid-write
could truncate the file. Using write-to-temp + rename would be safer.

---

### 2. HIGH — calculate_version uses stale base on first release

**File:** `skills/sprint-release/scripts/release_gate.py`, `calculate_version()` (line 118)

When no semver tags exist, the base version is hardcoded to `"0.1.0"`. The
function then calls `parse_commits_since(None)`, which runs `git log` with no
range (ALL commits). If the repo has hundreds of commits, `determine_bump()`
scans them all. This is correct behavior, but:

The first release will ALWAYS bump from 0.1.0 based on every commit in history.
If any commit ever used `feat!:` or had "BREAKING CHANGE:" in the body,
the first release jumps to `1.0.0` -- which may surprise users expecting
`0.2.0`. This is a design choice, not a bug per se, but the surprise factor
is high. **Recommend:** Document this behavior, or consider: "first release
should always be 0.1.0 unless the user overrides."

---

### 3. HIGH — release_gate.py: tag can point to wrong commit under concurrent push

**File:** `skills/sprint-release/scripts/release_gate.py`, `do_release()` (line 428)

The release flow:
1. Check working tree is clean (line 459)
2. `calculate_version()` reads git log
3. `write_version_to_toml()` modifies project.toml
4. `git add` + `commit.py` creates the version bump commit
5. `git tag` creates the tag on HEAD
6. `git push origin <base_branch> v<version>` pushes both

Between step 1 (clean check) and step 6 (push), if another developer pushes
to the base branch, the push in step 6 will FAIL (non-fast-forward). The
rollback logic correctly handles this by calling `_rollback_tag()` and
`_rollback_commit()`.

However, `calculate_version()` at step 2 computes the version based on the
current commit log. If someone else pushes a `feat!:` commit to the remote
between step 2 and step 6, the calculated version could be WRONG (should have
been major but was calculated as minor). The tag never gets pushed (push fails),
so this is not a data corruption issue -- just a wasted cycle. **Acceptable
given the rollback design.**

The REAL risk: if git push succeeds despite a race (rebase or force-push
scenario), the tag could reference a commit that doesn't include the other
developer's changes. This is mitigated by the clean-tree check and the fact
that `git push` defaults to rejecting non-fast-forward updates.

**Verdict:** The rollback design is sound. The risk is theoretical. **Downgrade
to MEDIUM** -- recommend documenting that releases should not be run
concurrently.

---

### 4. MEDIUM — sync_backlog TOCTOU between hash check and do_sync

**File:** `scripts/sync_backlog.py`, `main()` (line 195)

The code explicitly acknowledges this at line 219-223:
```
# Note: there is a narrow TOCTOU window between hashing above and
# reading files inside do_sync().
```

The mitigation (debounce across invocations) is reasonable. A file changed in
the ~100ms gap would be caught on the next loop iteration. However, the debounce
requires the caller to invoke `main()` again. If sync_backlog is called once
manually (`python scripts/sync_backlog.py`), there IS no retry -- the stale
data is synced. The debounce only works with `sprint-monitor`'s loop.

**Impact:** Could sync partially-written milestone files to GitHub issues
during a manual run. Low severity since all creates are idempotent.

---

### 5. LOW — Shell injection surface in gate_tests and gate_build

**File:** `skills/sprint-release/scripts/release_gate.py`, lines 205-238

Both `gate_tests()` and `gate_build()` use `subprocess.run(cmd, shell=True)`.
The code has explicit comments explaining this is intentional -- commands come
from project.toml which is user-controlled. This is the right call: the user
IS the trust boundary here.

However, if a project.toml is committed to a public repo and a CI system runs
`release_gate.py validate` automatically, a malicious PR that modifies
`check_commands` in project.toml could execute arbitrary code. This is the
standard "build system trust" problem and is outside giles's threat model.
Noting for completeness.

---

### 6. MEDIUM — get_existing_issues in populate_issues uses different ID extraction than extract_story_id

**File:** `skills/sprint-setup/scripts/populate_issues.py`, `get_existing_issues()` (line 277)
**File:** `scripts/validate_config.py`, `extract_story_id()` (line 813)

`get_existing_issues()` uses the regex `r"([A-Z]+-\d+):"` (requires a colon
after the ID). `extract_story_id()` uses `r"([A-Z]+-\d+)"` (no colon required)
and falls back to a slug.

If an issue title is `"US-0001 Setup CI"` (space, no colon), then:
- `extract_story_id()` returns `"US-0001"` (matches)
- `get_existing_issues()` does NOT match (no colon after ID)

This means `do_sync()` in sync_backlog.py would call `create_issue()` for a
story that already exists as a GitHub issue (because it wasn't found in
`existing`). `create_issue()` would then create a DUPLICATE issue.

**Impact:** Duplicate issue creation for titles without colons after the story
ID. In practice, `create_issue()` formats titles as `"{story.story_id}:
{story.title}"` so issues created by giles always have the colon. But manually
created issues (or issues from other tools) could trigger duplicates.

---

### 7. LOW — sync_backlog import failure silently degrades

**File:** `scripts/sync_backlog.py`, lines 27-32

```python
try:
    import bootstrap_github
    import populate_issues
except ImportError:
    bootstrap_github = None
    populate_issues = None
```

If the import fails (e.g., bootstrap_github.py has a syntax error), the module
loads successfully but `do_sync()` raises `ImportError` with a generic message.
The actual root cause (syntax error) is swallowed. This makes debugging harder
than necessary.

---

### 8. MEDIUM — write_version_to_toml regex can match commented-out version lines

**File:** `skills/sprint-release/scripts/release_gate.py`, `write_version_to_toml()` (line 281)

The function correctly ignores `# [release]` as a section header (line 290).
But inside a matched `[release]` section, the version regex
`r'^version\s*=\s*"[^"]*"'` would match a commented-out version line like:

```toml
[release]
# version = "old"
version = "1.0.0"
```

The regex uses `^` with `re.MULTILINE`, so `# version = "old"` would NOT match
(the `#` is the first character). **Actually, this is safe.** The `^` anchors
to the start of a line, and `version` must be the first word. A `# version`
line starts with `#`, not `v`.

Wait -- let me re-check. The regex is `r'^version\s*=\s*"[^"]*"'`. On the line
`# version = "old"`, the `^` anchors to line start, and `#` != `v`, so it does
NOT match. This is correct.

**However**, the regex `count=1` means it only replaces the FIRST match. If
there are two `version = "X"` lines in the `[release]` section (from a manual
copy-paste error), only the first is updated. This is minor.

**Downgrade to LOW.**

---

### 9. HIGH — No 500-limit guard on list_milestone_issues in sync_tracking

**File:** `scripts/validate_config.py`, `list_milestone_issues()` (line 870)
**File:** `skills/sprint-run/scripts/sync_tracking.py`, `main()` (line 336)

`list_milestone_issues()` fetches with `--limit 500` and calls
`warn_if_at_limit()` -- but only prints a WARNING to stderr. sync_tracking's
`main()` continues to process the (potentially incomplete) list of 500 issues
as if it were complete.

For a milestone with >500 issues:
- Issues 501+ would never get tracking files created
- Existing tracking files for issues 501+ would never be synced
- No error, just a stderr warning that's easy to miss in automation

Contrast with `gate_prs()` in release_gate.py (line 184), which correctly
FAILS the gate when 500 PRs are returned.

**Recommendation:** Either paginate (using `gh api --paginate` instead of
`gh issue list`), or fail hard when the limit is hit in sync_tracking.

---

### 10. MEDIUM — _fetch_all_prs limit of 500 silently truncates

**File:** `skills/sprint-run/scripts/sync_tracking.py`, `_fetch_all_prs()` (line 36)

Uses `--limit 500` but does NOT call `warn_if_at_limit()`. If a repo has >500
PRs, the fallback branch-matching in `get_linked_pr()` silently misses PRs
not in the fetched set. The timeline API (primary path) would still find them,
but if the timeline API fails, the fallback is broken.

---

### 11. LOW — determine_bump does not handle pre-release versions

**File:** `skills/sprint-release/scripts/release_gate.py`, `bump_version()` (line 101)

`bump_version("1.0.0-beta.1", "patch")` would raise `ValueError` because
`"1.0.0-beta.1".split(".")` produces `["1", "0", "0-beta", "1"]` (4 parts).
Pre-release suffixes are not handled.

Similarly, `_SEMVER_TAG_RE` at line 35 (`r"^v(\d+\.\d+\.\d+)$"`) correctly
rejects pre-release tags like `v1.0.0-rc.1`, so they would never be used as
a base. But if someone creates such a tag and expects giles to bump from it,
it will be silently ignored and the previous clean semver tag will be used
instead.

---

### 12. MEDIUM — check_status.py passes user-controlled branch names to gh API URL

**File:** `skills/sprint-monitor/scripts/check_status.py`, `check_branch_divergence()` (line 227)

```python
data = gh_json([
    "api", f"repos/{repo}/compare/{base_branch}...{branch}",
    ...
])
```

`branch` comes from `pr["headRefName"]` which is fetched from GitHub (line 381).
Since this is data from GitHub's own API being fed back to GitHub's API, the
injection risk is minimal -- GitHub validates branch names on creation.

However, if FakeGitHub in tests returns a branch name with URL-special
characters, the API path could be malformed. Not a production risk.

---

### 13. LOW — check_status.py imports sync_backlog without config isolation

**File:** `skills/sprint-monitor/scripts/check_status.py`, lines 26-30

```python
try:
    from sync_backlog import main as sync_backlog_main
except ImportError as _import_err:
    ...
```

When `sync_backlog_main()` is called inside `check_status.main()` (line 368),
it calls `load_config()` independently. This means check_status loads config
once (line 335), and sync_backlog loads it again. If the config file changes
between these two loads, the two scripts operate on different configurations.

Extremely unlikely in practice (both loads happen within milliseconds), but
worth noting for correctness.

---

### 14. LOW — sync_tracking creates tracking files but never deletes stale ones

**File:** `skills/sprint-run/scripts/sync_tracking.py`, `main()` (line 309)

The main loop iterates over GitHub issues and either updates existing tracking
files or creates new ones. But if a tracking file exists locally for a story
that was REMOVED from the GitHub milestone (deleted issue, moved to another
milestone), the stale tracking file persists forever.

This is by design ("GitHub is authoritative" means sync adds/updates, not
deletes), but it could confuse burndown calculations if stale files are
counted.

---

### 15. MEDIUM — do_release rollback on github-release failure deletes the remote tag, but version commit is already pushed

**File:** `skills/sprint-release/scripts/release_gate.py`, `do_release()` (line 636-641)

If `gh release create` fails (line 637), the rollback calls `_rollback_tag()`
and `_rollback_commit()`. At this point, `pushed_to_remote = True` (set at
line 604), so `_rollback_commit()` will:
1. `git revert --no-edit HEAD` (creates a revert commit)
2. `git push origin <base_branch>` (pushes the revert)

And `_rollback_tag()` will:
1. `git tag -d v<version>` (delete local tag)
2. `git push --delete origin v<version>` (delete remote tag)

This means a failed GitHub Release results in THREE commits on the base branch:
the original version bump, the revert, and whatever was there before. The tag
is cleaned up. This is messy but correct -- the base branch ends up in the
right state (version bump undone). The commit history has noise but no data
loss.

**Recommendation:** Consider: if only the GitHub Release creation failed (tag
and commit pushed successfully), offer to retry the `gh release create` rather
than rolling everything back.

---

### 16. LOW — generate_release_notes compare link check runs git locally, not against remote

**File:** `skills/sprint-release/scripts/release_gate.py`, `generate_release_notes()` (line 390-394)

The code checks if the previous tag exists by running `git rev-parse --verify
refs/tags/{prev_tag}` locally. But the compare link points to GitHub. If the
tag exists locally but hasn't been pushed to the remote (or vice versa), the
compare link could 404.

In the release flow, the previous tag should always exist on the remote (it was
from the PREVIOUS release). Low risk.

---

### 17. MEDIUM — sync_backlog.do_sync does not update state on partial failure

**File:** `scripts/sync_backlog.py`, `main()` (line 224-228)

If `do_sync()` succeeds partially (creates milestones but fails mid-way through
issue creation), `main()` still sets `state["file_hashes"] = current_hashes`
(line 225). On the next invocation, `check_sync()` sees no change and returns
"no_changes". The partially-created issues are never retried.

The mitigation is that `populate_issues.create_issue()` is idempotent (checks
`get_existing_issues()` first), so rerunning `do_sync()` manually would skip
already-created issues. But the automatic retry won't happen because the state
file says "all synced."

**To trigger a retry,** the user would need to edit a milestone file (changing
its hash) to force a new sync cycle.

---

### 18. LOW — check_status writes log files with second-precision timestamps, not atomic

**File:** `skills/sprint-monitor/scripts/check_status.py`, `write_log()` (line 314)

Filename: `monitor-{now.strftime('%Y%m%d-%H%M%S')}.log`. If `main()` is called
twice in the same second (unlikely but possible in tests or fast loops), the
second write overwrites the first. The log rotation (`while len(logs) >
MAX_LOGS`) uses `sorted(d.glob("monitor-*.log"))` which sorts lexically --
correct for this timestamp format.

---

## Summary

| # | Severity | Category | Script | One-liner |
|---|----------|----------|--------|-----------|
| 1 | LOW | Race | sync_tracking.py | Non-atomic file writes could truncate on crash |
| 2 | HIGH | Logic | release_gate.py | First release scans ALL commits; surprise major bump |
| 3 | MEDIUM | Race | release_gate.py | Concurrent push could waste a release cycle (rollback handles it) |
| 4 | MEDIUM | TOCTOU | sync_backlog.py | Manual single-run can sync stale file content |
| 5 | LOW | Security | release_gate.py | shell=True with user TOML config (intentional, documented) |
| 6 | MEDIUM | Inconsistency | populate_issues.py | ID extraction regex differs from extract_story_id (colon required) |
| 7 | LOW | Error handling | sync_backlog.py | Import failure swallows root cause |
| 8 | LOW | Logic | release_gate.py | TOML version write safe against comments (re-verified) |
| 9 | HIGH | Data loss | validate_config.py | 500-issue limit silently truncates sync; no pagination |
| 10 | MEDIUM | Data loss | sync_tracking.py | _fetch_all_prs 500 limit with no warning |
| 11 | LOW | Logic | release_gate.py | Pre-release semver versions not handled |
| 12 | MEDIUM | Security | check_status.py | Branch names in API URLs (low practical risk) |
| 13 | LOW | Race | check_status.py | Double config load with sync_backlog |
| 14 | LOW | Data loss | sync_tracking.py | Stale tracking files never deleted |
| 15 | MEDIUM | Error recovery | release_gate.py | Failed GH Release creates noisy revert commits |
| 16 | LOW | Logic | release_gate.py | Compare link checks local tag, not remote |
| 17 | MEDIUM | Partial failure | sync_backlog.py | State marked synced after partial do_sync failure |
| 18 | LOW | Race | check_status.py | Same-second log writes overwrite each other |

**HIGH findings (action recommended):** #2, #9
**MEDIUM findings (worth addressing):** #3, #4, #6, #10, #12, #15, #17
**LOW findings (acceptable or informational):** #1, #5, #7, #8, #11, #13, #14, #16, #18
