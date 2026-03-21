# Pass 24 — Adversarial Code Audit

Audited all Python scripts across `scripts/`, `skills/sprint-setup/scripts/`,
`skills/sprint-run/scripts/`, `skills/sprint-monitor/scripts/`, and
`skills/sprint-release/scripts/`.

---

## 1. Command Injection / Shell Safety

### BH24-001: `do_assign` passes unsanitized issue body to `gh issue edit --body`

**File:** `scripts/kanban.py:328`

```python
gh(["issue", "edit", issue_num, "--body", new_body])
```

The `new_body` variable contains the full GitHub issue body, which could include
any characters. While `gh()` uses `subprocess.run` with a list (no `shell=True`),
the `gh` CLI itself interprets certain argument prefixes. The real risk here is
not shell injection but that `new_body` could be enormous (GitHub allows 65536
characters) and hit subprocess buffer limits or `gh` CLI argument length limits
on some operating systems. macOS `ARG_MAX` is ~262144 bytes. An issue body close
to that limit would cause `gh` to fail with an E2BIG error, and the resulting
`RuntimeError` is caught, but the rollback only restores `implementer`/`reviewer`
in the local tracking file -- the persona labels already applied to GitHub in
lines 314-317 are NOT rolled back. The error message at line 339 documents this
but the practical result is state divergence.

**Trigger:** Issue body approaching OS argument limit (~250KB).
**Impact:** Partial state update (labels applied, body not updated, local
rollback succeeds but GitHub labels persist).
**Test:** Create a GitHub issue with a body near 200KB, then run `kanban.py assign`.

### BH24-002: `gate_tests` and `gate_build` execute user-configured commands with `shell=True`

**File:** `skills/sprint-release/scripts/release_gate.py:219, 237`

The trust model is documented (BH18-003), but the 300-second timeout does not
protect against a malicious command that, for example, forks a background process
before exiting cleanly. More practically: if `check_commands` contains a
multiline string (the TOML parser accepts `\n` in double-quoted strings), the
`shell=True` call will execute multiple commands separated by newlines. The
TOML escape `\n` becomes a real newline, which bash interprets as a command
separator.

**Trigger:** `check_commands = ["echo harmless\nrm -rf /tmp/something"]` in project.toml.
**Impact:** The `\n` in a TOML double-quoted string is unescaped to a real
newline by `_unescape_toml_string()`, then passed to `shell=True`. The intent
is one command per array element, but newlines make it multiple commands.
**Test:** Add a check_command with an escaped newline in project.toml and run
`release_gate.py validate`.

### BH24-003: `_yaml_safe` does not quote values that start with `%`

**File:** `scripts/validate_config.py:1063`

The needs_quoting check looks at `value[0] in '\'\"[{>|*&!%@`'` which DOES
include `%`. HOWEVER, it does NOT include `~` which is a YAML value indicator
(home directory expansion by some YAML parsers). More importantly, values
starting with a bare `{` followed by non-YAML-flow content would break block
scalar detection in strict YAML parsers.

*After closer review: `{` IS in the check list. This is actually fine.*

**Revised finding:** The `_yaml_safe` function does not quote values that consist
entirely of whitespace (e.g., `"   "`). The `value != value.strip()` check at
line 1073 catches leading/trailing whitespace, but a value that is ALL spaces
(`value.strip()` returns `""`, which differs from `value`) would be quoted
correctly. **Downgraded — this is not actually a bug.**

### BH24-004: `generate_release_notes` embeds commit subjects directly into markdown

**File:** `skills/sprint-release/scripts/release_gate.py:375`

```python
lines.append(f"- {h}")
```

Commit subjects are placed directly into markdown without escaping. A commit
message containing `[malicious](https://evil.com)` would become a clickable
link in the GitHub Release. This is a minor markdown injection issue -- the
commit author already has code execution via the commit itself, so the threat
model is low, but it means a compromised dependency's commit messages could
inject links into release notes.

**Trigger:** A commit with markdown link syntax in the subject line.
**Impact:** Misleading links in GitHub Release notes.
**Test:** Create a commit with `feat: update [click here](https://example.com)`
and run `release_gate.py release`.

---

## 2. State Corruption

### BH24-005: `do_sync` in `kanban.py` does not hold a lock during iteration

**File:** `scripts/kanban.py:350-449`

The `main()` function at line 594 wraps `do_sync` in `lock_sprint`. However,
`do_sync` itself calls `atomic_write_tf` for each story it processes. If the
lock is held throughout (as in `main()`), this is fine. But `do_sync` is also
called by `sync_backlog.py` via a different path, and callers importing
`do_sync` directly might not hold the lock.

Looking at actual callers: `kanban.py main()` does hold `lock_sprint`. No other
file imports `do_sync` directly. **Downgraded to informational — API contract
should document that callers must hold `lock_sprint`.**

### BH24-006: `sync_tracking.py` and `kanban.py` can write the same tracking file concurrently

**File:** `skills/sprint-run/scripts/sync_tracking.py:17-19` (documented),
`scripts/kanban.py:155-193`

The docstring in `sync_tracking.py` (line 17) acknowledges this: "this script
does NOT acquire kanban locks before writing tracking files." The claim is that
sprint-monitor calls them sequentially, but there is no enforcement. If a user
runs `kanban.py transition US-0042 dev` while `sync_tracking.py` is running
(triggered by sprint-monitor), the last write wins, potentially reverting a
state change.

**Trigger:** Run `kanban.py transition` and `sync_tracking.py` in parallel.
**Impact:** The later write silently overwrites the earlier one, potentially
reverting a kanban state transition that was just made.
**Test:** Use two terminals to run both scripts simultaneously targeting the
same story.

### BH24-007: `write_version_to_toml` regex for `[release]` section boundary is fragile

**File:** `skills/sprint-release/scripts/release_gate.py:304`

```python
next_section = re.search(r"^\[(?![\[\s\"\'])", text[start + 1:], re.MULTILINE)
```

This searches for the next section header starting from `start + 1`, but
`start + 1` is one byte into the `[release]` header itself, not after it. If
`[release]` is at position 100 (the `[` character), then `start + 1` is 101,
which is inside the word `release]`. The regex then searches from `r` onwards,
which correctly won't match `release]...` as a section header. This works by
accident because the `[` at position 100 was already consumed.

But consider: if the TOML file has `[release]` immediately followed by
`[release.subsection]` (dot-qualified sections), the regex would match
`[release.subsection]` as the next section boundary and truncate it.

**Trigger:** A `project.toml` with `[release.metadata]` or similar subsection
after `[release]`.
**Impact:** Version would be written only into the `[release]` section (before
`[release.metadata]`), which is actually correct behavior. **Downgraded — works
as expected for flat TOML structures. Subsections are not used.**

### BH24-008: `atomic_write_tf` uses `os.rename` which is not atomic across filesystems

**File:** `scripts/kanban.py:152`

```python
os.rename(str(tmp), str(tf.path))
```

`os.rename` is atomic only when source and destination are on the same
filesystem. The temp file is created via `tf.path.with_suffix(".tmp")`, which is
in the same directory, so this is fine in practice. However, if someone mounts
sprints_dir on a different filesystem (e.g., NFS, network mount), the rename
would fail with `OSError` rather than being silently non-atomic.

**Trigger:** sprints_dir on a different filesystem than the temp file location.
**Impact:** `OSError` exception during write (not silent corruption).
**Test:** Mount sprints_dir on a tmpfs and verify write behavior.

---

## 3. Logic Bugs

### BH24-009: `_infer_sprint_number` double-reads the file when `content` is not passed

**File:** `skills/sprint-setup/scripts/populate_issues.py:180-197`

When `content is None`, the function reads the file. But line 418 calls
`_infer_sprint_number(mf)` without passing content, even though the caller
(`build_milestone_title_map`) has already read the file text at line 402.
This is a performance bug, not a correctness bug. The file is read twice.

**Trigger:** Any call to `build_milestone_title_map` with milestone files that
have no sprint sections.
**Impact:** Unnecessary file I/O (minor).
**Test:** Profile `build_milestone_title_map` with a single milestone file.

### BH24-010: `enrich_from_epics` uses string containment to match story IDs

**File:** `skills/sprint-setup/scripts/populate_issues.py:312-313`

```python
known_sprints = [
    by_id[sid].sprint
    for sid in by_id
    if sid in content
]
```

This checks if the story ID string appears anywhere in the epic file content,
not just in structured positions. If an epic file contains a reference to
`US-0001` in a comment or dependency field, but the epic is actually about
different stories, the sprint number inference will include that story's sprint.
More critically, `US-001` would match inside `US-0012` (substring match).

**Trigger:** An epic file that mentions `US-001` in prose, where `US-0012` and
`US-001` are both in the `by_id` dict.
**Impact:** Incorrect sprint number inference for the epic, causing stories to
be assigned to the wrong milestone.
**Test:** Create an epic file referencing US-001 in prose alongside US-0012 in
a story heading, with different sprint numbers.

### BH24-011: `parse_detail_blocks` splits on regex groups, fragile to group count

**File:** `skills/sprint-setup/scripts/populate_issues.py:229-234`

```python
parts = detail_re.split(content)
# parts: [preamble, id1, title1, body1, id2, title2, body2, ...]
for i in range(1, len(parts), 3):
```

The step size of 3 assumes the regex has exactly 2 capturing groups. The default
`_DETAIL_BLOCK_RE` has 2 groups: `(US-\d{4})` and `(.+)`. But
`_build_detail_block_re` constructs the regex from a user-supplied pattern that
has been validated to have no capturing groups (`_safe_compile_pattern` rejects
them). So the custom pattern becomes the first group, and `(.+)` is the second.
This is correct.

However, if `_safe_compile_pattern` has a false negative (a capturing group
disguised via a pattern the check misses), the group count would change, and the
step-3 iteration would produce garbled story data. The check at line 72 uses
`(?<!\\)\((?!\?)` to detect groups, which would miss `(?P<name>...)` named
groups since they start with `(?P` which begins with `(?` — but wait, `(?P` does
start with `(?` so the `(?!\?)` negative lookahead would NOT match because the
character after `(` is `?`. So named groups ARE rejected. This is correct.

**Downgraded — the validation is thorough enough. Informational only.**

### BH24-012: `slug_from_title` returns "untitled" for empty input, creating collision risk

**File:** `scripts/validate_config.py:1029`

If multiple stories have titles that produce empty slugs (after stripping
non-alphanumeric characters), they all get the slug "untitled". Combined with
the same story ID prefix, this creates filename collisions. The collision
detection in `sync_tracking.py:189` handles this for different story IDs, but
not for the same story ID written twice.

**Trigger:** Two stories whose titles consist entirely of special characters
(unlikely but possible with non-English titles).
**Impact:** Filename collision, second story overwrites first.
**Test:** Create two stories with titles like "???" and "!!!" and verify
tracking file creation.

### BH24-013: `update_sprint_status` regex replacement can match in the wrong location

**File:** `skills/sprint-run/scripts/update_burndown.py:107`

```python
pattern = r"## Active Stories\n(?:(?!\n## )[^\n]*\n)*(?:(?!\n## )[^\n]+\n?)?"
```

This pattern looks for `## Active Stories` followed by lines that don't start
with `## `. But the pattern requires `## Active Stories` to NOT be preceded by a
newline (because the `\n` before `## Active Stories` is consumed by the previous
`[^\n]*\n`). If the section appears at the very start of the file (no preceding
newline), the pattern still matches. However, if there are TWO `## Active Stories`
sections in the file (e.g., from a manual edit), only the first is replaced.
The `re.sub` with no `count` argument replaces ALL matches, so this is actually
fine.

**Downgraded — works correctly.**

### BH24-014: `check_sync` in `sync_backlog.py` mutates state dict for debouncing but state is saved even on no_changes

**File:** `scripts/sync_backlog.py:129-135`

When `current_hashes == stored and pending is not None`, the function sets
`state["pending_hashes"] = None` and returns `SyncResult("no_changes", ...)`.
Back in `main()` at line 237, the `elif result.status == "no_changes": pass`
branch does nothing, but then line 241 `save_state(config_dir, state)` saves
the state unconditionally. This means the `pending_hashes = None` mutation IS
persisted, which is the correct behavior (cancelling a pending sync because
files reverted). This is actually fine.

**Downgraded — not a bug.**

### BH24-015: `sprint_analytics.compute_velocity` returns `percentage: 0` when all issues are open with 0 SP

**File:** `scripts/sprint_analytics.py:67`

```python
pct = round(delivered_sp / planned_sp * 100) if planned_sp else 0
```

If all stories have 0 SP (because `extract_sp` couldn't find SP in the body),
`planned_sp` is 0, so `pct` is 0. This is technically correct (0/0 → 0%), but
the report silently claims "0 SP planned" which looks like a data error rather
than a missing-SP-data issue. There is no warning emitted.

**Trigger:** Stories created without SP data in body or labels.
**Impact:** Misleading analytics report (0% velocity when data is actually missing).
**Test:** Create milestone issues without any SP data and run `sprint_analytics.py`.

---

## 4. Error Handling Gaps

### BH24-016: `gh_json` slow-path `JSONDecodeError` raises `RuntimeError` but callers inconsistently handle it

**File:** `scripts/validate_config.py:122-126`

When `gh_json` receives garbage (e.g., an HTML error page from a proxy), it
raises `RuntimeError`. Some callers handle this:
- `sync_tracking._fetch_all_prs` (line 52): catches `RuntimeError`, returns `[]`
- `check_status.check_ci` (line 56): does NOT catch `RuntimeError` — an HTML
  error page from `gh run list --json` would crash the entire monitor

The inconsistency means some `gh_json` callers will crash on malformed responses
while others degrade gracefully.

**Trigger:** Corporate proxy or VPN that returns HTML for failed requests.
**Impact:** `check_status.py` crashes instead of reporting the error.
**Test:** Mock `gh` to return HTML and run `check_status.py`.

### BH24-017: `find_milestone` queries all milestones on every call with no caching

**File:** `scripts/validate_config.py:1146-1157`

`find_milestone` makes a paginated API call to list ALL milestones every time
it is called. In `check_status.py:main()`, `find_milestone` is called once at
line 426, and the result is cached as `cached_ms` and passed to
`check_milestone`. But in `kanban.py:main()` at line 589, `find_milestone` is
called, and then `list_milestone_issues` at line 593 makes ANOTHER API call.
In `sprint_analytics.py`, `find_milestone` is called, then `compute_velocity`,
`compute_review_rounds`, and `compute_workload` each make their own API calls.

This is a performance issue, not a correctness issue, but with many milestones
the paginated query can be slow.

**Trigger:** Repository with many milestones (>30).
**Impact:** Slow execution due to redundant API calls.

### BH24-018: `read_tf` silently returns default TF on `FileNotFoundError` but not on `PermissionError`

**File:** `scripts/validate_config.py:1088`

```python
except FileNotFoundError:
    return tf  # return default TF
```

If the file exists but is unreadable (permissions issue), `PermissionError` is
NOT caught and will propagate as an unhandled exception. This could crash
`kanban.py do_sync` which iterates over all `.md` files.

**Trigger:** A tracking file with restrictive permissions (e.g., 000).
**Impact:** Unhandled `PermissionError` crashes the sync loop.
**Test:** `chmod 000` a tracking file and run `kanban.py sync`.

### BH24-019: `do_release` rollback has a gap between tag push and release creation

**File:** `skills/sprint-release/scripts/release_gate.py:614-661`

After pushing the tag (line 617), if `gh release create` fails (line 656),
`_rollback_tag()` is called. This deletes the tag locally and remotely. But
between the push at line 617 and the rollback, GitHub may have already triggered
workflows on the tag. The rollback deletes the tag but cannot cancel those
workflows. A half-completed CI run could produce artifacts for a version that
was rolled back.

**Trigger:** `gh release create` fails (e.g., network timeout, auth issue).
**Impact:** Ghost CI runs for a rolled-back version.
**Test:** Mock `gh release create` to fail after tag push and check CI status.

### BH24-020: `_rollback_commit` can push a revert to the wrong branch

**File:** `skills/sprint-release/scripts/release_gate.py:521-522`

```python
base = get_base_branch(config)
r2 = subprocess.run(
    ["git", "push", "origin", base], ...
)
```

If the user has switched branches between the original push and the rollback
(unlikely but possible if running in a script), the revert commit is created on
HEAD (which could be a different branch) and pushed to the base branch. This
would push unrelated commits to the base branch.

**Trigger:** Branch switch between release attempt and rollback.
**Impact:** Unrelated commits pushed to the base branch.
**Test:** Difficult to trigger — requires concurrent branch operations.

---

## 5. Cross-Script Consistency

### BH24-021: `kanban.py do_sync` and `sync_tracking.py create_from_issue` use different filename conventions

**File:** `scripts/kanban.py:421`, `skills/sprint-run/scripts/sync_tracking.py:183`

Both create tracking files for new stories. Let me compare:

- `kanban.py` line 421: `filename = f"{story_id}-{slug}.md" if slug else f"{story_id}.md"`
  where `story_id` comes from `extract_story_id(title).upper()` (line 374)
- `sync_tracking.py` line 183: `filename = f"{story_id_upper}-{slug}.md" if slug else f"{story_id_upper}.md"`
  where `story_id_upper = sid.upper()` and `sid = extract_story_id(issue["title"])`

Both use uppercase story IDs and the same slug function. The convention matches.
The comment at `sync_tracking.py:179-181` (BH22-117) explicitly documents this
alignment.

**Downgraded — conventions match. No bug.**

### BH24-022: `sprint_analytics.compute_review_rounds` searches PRs by milestone title differently than `compute_velocity`

**File:** `scripts/sprint_analytics.py:83-99`

`compute_velocity` (line 44) uses `--milestone` flag on `gh issue list`.
`compute_review_rounds` (line 83) uses `--search milestone:"title"` on `gh pr list`.
The `--search` approach is a text search, not an exact match. The BH23-217
comment at line 93 acknowledges this and adds a post-filter. However, the
post-filter at line 98 compares `ms.get("title") == milestone_title`, which is
an exact string match. If a milestone title contains special characters that
GitHub's search interprets differently (e.g., colons, quotes), the `--search`
may return no results even when matching PRs exist, causing the post-filter to
also find nothing.

**Trigger:** Milestone title like `Sprint 1: "Special" Release` (with quotes).
**Impact:** `compute_review_rounds` returns empty results while
`compute_velocity` works correctly. The analytics report shows "no PR data
available" even when PRs exist.
**Test:** Create a milestone with quotes in the title and verify review round
computation.

### BH24-023: `populate_issues.get_existing_issues` filters by regex but `create_issue` doesn't check the same way

**File:** `skills/sprint-setup/scripts/populate_issues.py:368, 546`

`get_existing_issues` at line 368 only adds IDs matching `[A-Z]+-\d+` to the
existing set. But the `story.story_id` at line 546 comes from the regex
match in `_DEFAULT_ROW_RE` which captures `US-\d{4}`. These always match
`[A-Z]+-\d+`, so there is no gap for the default pattern.

However, with a custom `story_id_pattern` (from config), the captured story ID
might not match `[A-Z]+-\d+`. For example, a pattern like `[a-z]+-\d+` would
capture lowercase IDs. These would NOT be in the `existing` set (because the
filter at line 368 requires uppercase). So the idempotency check would fail,
creating duplicate issues.

**Trigger:** Custom `story_id_pattern` that matches lowercase IDs.
**Impact:** Duplicate issues created on re-run because the lowercase ID doesn't
pass the `[A-Z]+-\d+` filter in `get_existing_issues`.
**Test:** Set `story_id_pattern = "[a-z]+-\\d+"` in project.toml and run
`populate_issues.py` twice.

---

## 6. Duplicated Logic

### BH24-024: Date formatting is done differently in `sprint_analytics.py` vs `update_burndown.py`

**File:** `scripts/sprint_analytics.py:247-249` vs
`skills/sprint-run/scripts/update_burndown.py:29-31`

`sprint_analytics.py` reads sprint theme from a kickoff file:
```python
m = re.search(r"Sprint Theme:\s*(.+)", text)
```

`update_burndown.py` uses `parse_iso_date` for dates (from validate_config),
while `sprint_analytics.py` formats velocity percentage with `round()` and
`update_burndown.py` also uses `round()`. This is consistent.

However, the SP extraction logic is used differently:
- `sprint_analytics.py:61` calls `extract_sp(iss)` with issues that have
  `"body"` in their JSON fields
- `update_burndown.py:158` calls `extract_sp(issue)` with issues from
  `list_milestone_issues` which requests `"body"` in the JSON fields

Both are consistent. **Downgraded — no actual divergence.**

### BH24-025: `_parse_epic_from_lines` and `parse_saga` use `parse_header_table` but with different `stop_heading` values

**File:** `scripts/manage_epics.py:31` uses `stop_heading="###"`,
`scripts/manage_sagas.py:46` uses `stop_heading="##"`

This is intentional and documented in `parse_header_table`'s docstring
(validate_config.py:887). Epics have ### subsections, sagas have ## subsections.
**Not a bug — by design.**

### BH24-026: Story title sanitization is done differently in `manage_epics._sanitize_md` vs `manage_sagas.update_team_voices`

**File:** `scripts/manage_epics.py:147-149` vs `scripts/manage_sagas.py:247-248`

`manage_epics._sanitize_md`:
```python
return value.replace("\n", " ").replace("\r", " ").replace("|", "-")
```

`manage_sagas.update_team_voices`:
```python
safe_name = name.replace("\n", " ").replace("\r", "").replace("**", "")
safe_quote = quote.replace("\n", " ").replace("\r", "").replace('"', "'")
```

The `\r` handling differs: epics replace with space, sagas replace with empty
string. The pipe character `|` is only stripped in epics (for table safety), not
in sagas (where the content is in blockquotes, not tables). The sagas function
strips `**` (bold markers) and `"` (double quotes) which epics does not.

This is intentional — different contexts require different sanitization. But
neither function strips `>` (blockquote marker), which means a persona name like
`> Injected` in `update_team_voices` would create a nested blockquote:

```markdown
> **> Injected:** "quote"
```

**Trigger:** A persona name containing `>` passed to `update_team_voices`.
**Impact:** Malformed markdown in the saga file (broken blockquote structure).
**Test:** Call `update_team_voices` with a name containing `>` and inspect output.

### BH24-027: Two independent implementations of "extract story ID from title"

**File:** `scripts/validate_config.py:957-971` (`extract_story_id`) and
`skills/sprint-setup/scripts/populate_issues.py:366-369` (inline regex)

`extract_story_id` at line 963 uses `re.match(r"([A-Z]+-\d+)", title)`.
`get_existing_issues` at line 368 uses `re.match(r"[A-Z]+-\d+", sid)` where
`sid` is already the output of `extract_story_id`.

This is actually a validation step on `extract_story_id`'s output — checking
that the result looks like a proper story ID (not a fallback slug). The double
check is defensive, not duplicated. **Downgraded — not a real duplication issue.**

---

## 7. Additional Findings

### BH24-028: `_first_error` in `check_status.py` compiles regexes inside a loop

**File:** `skills/sprint-monitor/scripts/check_status.py:100-123`

The `_first_error` function compiles `_FALSE_POSITIVE`, `_ERROR_KW`, and
`_ANSI_RE` regex patterns on every call. These are defined as local variables
inside the function body, so they are recompiled each time the function is called.
Since `_first_error` is called once per failing CI run (usually 0-5 times), this
is not a performance issue, but it would be cleaner as module-level constants.

**Impact:** Minor code quality issue.

### BH24-029: `lock_story` opens the lock file in read mode but `lock_sprint` opens in read-write mode

**File:** `scripts/kanban.py:171` vs `scripts/kanban.py:188`

```python
# lock_story
with open(lock_path, "r", encoding="utf-8") as fh:
    fcntl.flock(fh, fcntl.LOCK_EX)

# lock_sprint
with open(lock_file, "r+", encoding="utf-8") as fh:
    fcntl.flock(fh, fcntl.LOCK_EX)
```

Both work for `fcntl.flock` (which only needs a valid file descriptor), but
`"r"` would fail on a newly-created empty file on some platforms if the file
doesn't exist yet. The `lock_path.touch(exist_ok=True)` at line 170 ensures the
file exists, so `"r"` works. The inconsistency is harmless but confusing. Using
`"r"` is actually slightly safer as it prevents accidental writes to the lock file.

**Impact:** None (cosmetic inconsistency).

### BH24-030: `_parse_workflow_runs` can produce empty multiline commands

**File:** `scripts/sprint_init.py:232-233`

```python
if multiline_cmds:
    runs.append("\n".join(multiline_cmds))
```

If a multiline `run: |` block contains only YAML comments (lines starting with
`#`), `multiline_cmds` will be empty and nothing is appended. This is correct.
But if a `run: |` block contains only blank lines, they are also skipped (line
228 checks `if line_content`), resulting in no command being added. A `run: |`
block with only blank lines is malformed YAML anyway.

**Downgraded — correct behavior.**

### BH24-031: `_safe_compile_pattern` ReDoS test uses fixed probe characters

**File:** `skills/sprint-setup/scripts/populate_issues.py:92-103`

The ReDoS detection probes with 9 specific characters: `"aA0b_-/ \t"`. A
pathological regex that only exhibits catastrophic backtracking on, say, Unicode
characters or specific byte sequences not in this probe set would pass the check.
The 25-character limit makes this unlikely to cause real harm (even a bad pattern
on 25 chars takes <1s for most practical cases), but it is a theoretical gap.

**Trigger:** A story_id_pattern that backtracks catastrophically only on
characters not in the probe set.
**Impact:** Slow regex execution on actual milestone file content.
**Test:** Construct a pattern that is fast on ASCII but slow on, e.g., accented
characters, and verify the check passes.

### BH24-032: `reorder_stories` walks backwards over blank/separator lines without a lower bound

**File:** `scripts/manage_epics.py:283`

```python
while stories_start > 0 and lines[stories_start - 1].strip() in ("", "---"):
    stories_start -= 1
```

This loop walks backwards from the first story section, consuming all blank
lines and `---` separators. If the file header is entirely composed of blank
lines and `---` separators (pathological case), `stories_start` would reach 0
and the entire header would be consumed. The `> 0` check prevents an
off-by-one, but the header content between line 0 and the first story could be
entirely lost if it is all separators/blanks.

**Trigger:** An epic file whose header content is entirely `---` and blank lines.
**Impact:** Header content (title, metadata table) consumed into the "separator
area" and not included in the reordered output.
**Test:** Create an epic file with only `---` lines before the first story and
run `reorder_stories`.

### BH24-033: `parse_simple_toml` allows key names starting with digits due to regex

**File:** `scripts/validate_config.py:201`

```python
kv_match = re.match(r"^([a-zA-Z0-9_][a-zA-Z0-9_-]*)\s*=\s*(.*)$", line)
```

The comment at line 200 says "BH20-002: Allow digit-start keys per TOML spec
(bare keys are [A-Za-z0-9_-])". This is correct per the TOML spec. However, the
section header regex at line 178 also allows digit-start sections:

```python
header_match = re.match(r"^\[([a-zA-Z0-9_][a-zA-Z0-9_.-]*)\]\s*(?:#.*)?$", line)
```

But the `_REQUIRED_TOML_SECTIONS` check (line 466) expects sections named
"project", "paths", "ci" — all starting with letters. No bug here.

**Downgraded — informational.**

### BH24-034: `check_branch_divergence` passes repo string to `gh api` without validation

**File:** `skills/sprint-monitor/scripts/check_status.py:271-272`

```python
data = gh_json([
    "api", f"repos/{repo}/compare/{base_branch}...{branch}",
    ...
])
```

The `repo` value comes from `config.get("project", {}).get("repo", "")` which
is user-configured in project.toml. The `branch` values come from `gh pr list`
output (GitHub-controlled). The `base_branch` comes from config. None of these
are shell-injected (using list args, not shell=True), but a malicious `repo`
value like `../../api/other/endpoint` would construct a URL path traversal
against the GitHub API. The `gh` CLI would likely reject this, but it's worth
noting that `repo` is treated as trusted input throughout the codebase.

**Trigger:** Malicious `repo` value in project.toml.
**Impact:** API path traversal (mitigated by `gh` CLI URL handling).
**Test:** Set `repo = "../../api/repos"` in project.toml and run
`check_status.py`.

### BH24-035: `generate_ci_yaml` does not escape `base_branch` in YAML output

**File:** `skills/sprint-setup/scripts/setup_ci.py:256-258`

```python
lines = [
    ...
    f"    branches: [{base_branch}]",
    ...
    f"    branches: [{base_branch}]",
]
```

The `base_branch` value is interpolated directly into YAML. If the base branch
name contains YAML-special characters (e.g., `main: production` or `feature[1]`),
the generated YAML would be syntactically invalid. Branch names with colons are
valid in git.

**Trigger:** A base branch named something like `release:v2` or `main[stable]`.
**Impact:** Generated CI workflow YAML is syntactically invalid and would fail
GitHub Actions parsing.
**Test:** Set `base_branch = "release:v2"` in project.toml and run
`setup_ci.py`.

### BH24-036: `classify_entries` in `sprint_teardown.py` removes directory symlinks from `dirs` list using `list.remove()` which is O(n)

**File:** `scripts/sprint_teardown.py:68`

```python
dirs.remove(d)  # Don't descend into symlinked dirs
```

Using `list.remove(d)` in a loop over `list(dirs)` is O(n^2) in the worst case.
For typical sprint-config directories (< 20 entries), this is negligible.

**Impact:** None (performance, small N).

### BH24-037: `_rollback_commit` uses `git reset --hard` without checking current branch

**File:** `skills/sprint-release/scripts/release_gate.py:538-541`

```python
subprocess.run(
    ["git", "reset", "--hard", pre_release_sha],
    capture_output=True, text=True,
)
```

The `git reset --hard` is executed without verifying that HEAD is still on the
expected branch. If another process has switched branches (admittedly unlikely
during a release), this resets the wrong branch.

More practically: the `pre_release_sha` is captured at line 498, but if the
commit at line 559 adds to the commit history, `git reset --hard pre_release_sha`
correctly undoes it. The concern is that `git reset --hard` discards ALL working
tree changes, including any untracked files that appeared during the build
(line 236 `gate_build` runs `build_command` with `shell=True`). Build artifacts
created in the working tree would be silently deleted.

**Trigger:** `gate_build` creates build artifacts, then the release fails at a
later step.
**Impact:** Build artifacts deleted by rollback's `git reset --hard`.
**Test:** Configure a build_command that creates a file, fail the release at the
tag push step, and verify the file is gone.

---

## Summary

| ID | Category | Severity | File |
|----|----------|----------|------|
| BH24-001 | Shell safety | Medium | kanban.py:328 |
| BH24-002 | Shell safety | Low | release_gate.py:219 |
| BH24-004 | Shell safety | Low | release_gate.py:375 |
| BH24-006 | State corruption | Medium | sync_tracking.py / kanban.py |
| BH24-010 | Logic bug | Medium | populate_issues.py:312 |
| BH24-012 | Logic bug | Low | validate_config.py:1029 |
| BH24-015 | Logic bug | Low | sprint_analytics.py:67 |
| BH24-016 | Error handling | Medium | check_status.py:56 |
| BH24-018 | Error handling | Medium | validate_config.py:1088 |
| BH24-019 | Error handling | Low | release_gate.py:614-661 |
| BH24-022 | Consistency | Medium | sprint_analytics.py:83-99 |
| BH24-023 | Consistency | Medium | populate_issues.py:368 |
| BH24-026 | Duplicated logic | Low | manage_sagas.py:247 |
| BH24-031 | Logic bug | Low | populate_issues.py:92 |
| BH24-032 | Logic bug | Low | manage_epics.py:283 |
| BH24-035 | Shell safety | Medium | setup_ci.py:256 |
| BH24-037 | Error handling | Low | release_gate.py:538 |
