# Adversarial Code Audit — Production Scripts

**Date:** 2026-03-16
**Auditor:** Claude Opus 4.6 (adversarial mode)
**Scope:** 6 highest-churn, highest-risk production scripts

---

## Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 3     |
| HIGH     | 11    |
| MEDIUM   | 16    |
| LOW      | 9     |

---

## 1. scripts/validate_config.py

### CRITICAL

**VC-001: TOML parser mishandles quoted keys entirely**
`validate_config.py:182`
```python
kv_match = re.match(r"^([a-zA-Z0-9_][a-zA-Z0-9_-]*)\s*=\s*(.*)$", line)
```
The TOML spec allows quoted keys (`"weird key" = "value"` and `'literal key' = "value"`). The regex only matches bare keys. If a user puts a quoted key in project.toml, the line falls through to the "unrecognized TOML line" warning and the key is silently dropped. The config appears to parse successfully but is missing data. This is especially dangerous because `validate_project()` only checks for required keys — an optional key with a quoted name would vanish without any error.

**Severity:** CRITICAL — silent data loss on valid TOML input.

**VC-002: `_strip_inline_comment` doesn't handle single-quoted strings with embedded `#`**
`validate_config.py:219-232`
The function tracks `quote_char` but only applies backslash-escape logic for double quotes (line 229). For single-quoted strings, TOML spec says no escape processing, so a `'` inside a single-quoted string is impossible — but the function also doesn't handle the case where `#` appears after the closing `'` with no space. More critically, if a value is `key = 'hello#world'`, the `#` inside the quotes is correctly ignored. But if the value is `key = 'hello' # comment with 'quotes'`, the second `'` after the comment `#` would be ignored since we already returned at the `#`. This is actually correct. However, the deeper issue is:

*Revised:* The actual bug is that `_strip_inline_comment` is called on the **raw value** after `=`, but the value `'foo' # bar` would be parsed by `_parse_value` which calls `_strip_inline_comment` again (line 291). Double-stripping is idempotent for simple cases but if the first strip removes a `#` that was actually inside a value context, the second strip sees different input. In practice this is safe because `_strip_inline_comment` is idempotent for well-formed input. Downgrading.

**Revised severity:** LOW — double-call is wasteful but not buggy for well-formed TOML.

### HIGH

**VC-003: `_unescape_toml_string` silently accepts invalid escape sequences**
`validate_config.py:280-281`
```python
else:
    result.append(s[i:i + 2])  # Unknown escape, keep as-is
```
TOML spec says unknown escape sequences are **errors**. This parser silently keeps them, meaning a typo like `\q` in a string becomes the literal characters `\q` instead of raising. If a path value contains `\n` meaning a literal backslash + n (e.g., a Windows path), the parser interprets it as a newline. A user writing `path = "C:\new_folder"` gets `C:<newline>ew_folder` with no warning.

**Severity:** HIGH — silent corruption of string values, especially on Windows paths.

**VC-004: `frontmatter_value` uses greedy `.+` which fails on multi-line YAML values**
`validate_config.py:891`
```python
m = re.search(rf"^{key}:\s*(.+)", frontmatter, re.MULTILINE)
```
The `.+` requires at least one character, so `key:` followed by an empty value returns `None` instead of empty string. More importantly, with `re.MULTILINE`, `^` matches at line start but `.+` still doesn't cross lines — so this works for single-line values. However, a YAML value like `title: "line1\nline2"` (where `_yaml_safe` produced a quoted string with a literal backslash-n) would match correctly. The real issue is that if the frontmatter somehow has the same key twice, `re.search` returns only the first match. If sync_tracking writes duplicate keys (possible if `write_tf` is called with a TF that was constructed from a corrupted read), the stale value persists.

**Revised severity:** MEDIUM — edge case but data could be stale.

**VC-005: `load_config` resolves paths relative to `config_dir.parent`, not cwd**
`validate_config.py:678`
```python
project_root = Path(config_dir).resolve().parent
```
This assumes sprint-config/ is always a direct child of the project root. If someone passes a nested config dir like `foo/bar/sprint-config`, the "project root" becomes `foo/bar/`, not the actual project root. Every path in `[paths]` would then resolve wrong. The CLAUDE.md says all skills use the default `sprint-config`, but `main()` at line 1033 accepts `sys.argv[1]` as `config_dir`, so a user could trigger this.

**Severity:** HIGH — all file paths resolve incorrectly with non-standard config_dir placement.

### MEDIUM

**VC-006: `_parse_value` falls back to raw unquoted string for unknown values**
`validate_config.py:341-347`
After the metacharacter check, any remaining unrecognized value is returned as a raw string. This means TOML float values like `timeout = 3.14` are returned as the string `"3.14"` instead of raising or returning a number. Downstream code using `int()` on this would crash. The warning on line 344-346 only fires for values containing spaces.

**Severity:** MEDIUM — floats and other TOML types silently become strings.

**VC-007: `_parse_team_index` doesn't validate required columns exist**
`validate_config.py:566-603`
The function parses whatever table headers it finds. If someone has a table with columns "Person | Job | Location", the function returns rows with keys "person", "job", "location" — but callers expect "name", "role", "file". `get_team_personas()` at line 707 does `row.get("name", "")` which silently returns empty string, producing personas with no names.

**Severity:** MEDIUM — garbage in, silence out. User gets no warning their team index has wrong columns.

**VC-008: `find_milestone` fetches ALL milestones every call, no caching**
`validate_config.py:975-977`
```python
milestones = gh_json(["api", "repos/{owner}/{repo}/milestones", "--paginate"])
```
Every call to `find_milestone` makes a paginated API call. In check_status.py, this is mitigated by caching (line 390), but other callers like `sprint_analytics.py:235` and `update_burndown.py:208` each make separate calls. Not a correctness bug, but an API rate-limit risk.

**Severity:** MEDIUM — unnecessary API calls could hit rate limits.

**VC-009: `parse_simple_toml` doesn't handle TOML's `\r\n` line endings**
`validate_config.py:146`
```python
for raw_line in text.split('\n'):
```
The comment says TOML only recognizes `\n` and `\r\n`, but `split('\n')` on `\r\n` text leaves `\r` at the end of each line. The `strip()` on line 147 handles this for most lines, but the raw value extraction on line 185 uses the pre-stripped `raw_val` from the regex match, which could still contain `\r` for values at end of line. Actually, looking more carefully, `raw_val = kv_match.group(2).strip()` does strip `\r`. So this is safe. Downgrading to informational.

**Revised severity:** LOW — `strip()` handles `\r` but the code relies on this implicitly.

### LOW

**VC-010: `warn_if_at_limit` default parameter mismatch**
`validate_config.py:1011`
```python
def warn_if_at_limit(results: list, limit: int = 500) -> bool:
```
The default is 500, but `list_milestone_issues` passes `limit=1000` (line 1006). If someone calls `warn_if_at_limit(issues)` after a 1000-limit query, the warning fires at 500 results — a false positive. The callers are mostly correct today, but the inconsistent default is a trap.

**Severity:** LOW — misleading default, not currently triggering bugs.

**VC-011: Section header regex rejects valid TOML section names**
`validate_config.py:169`
```python
header_match = re.match(r"^\[([a-zA-Z0-9_][a-zA-Z0-9_.-]*)\]\s*(?:#.*)?$", line)
```
TOML allows quoted section headers like `["section with spaces"]` and bare keys can start with digits (per TOML spec, bare keys are `[A-Za-z0-9_-]`). The kv_match regex was fixed for digit-start (BH20-002) but the section header regex still rejects `[0-config]`. Also, dots in section names like `[a.b.c]` are handled, but `[a."b.c"]` (quoted dotted key) is not.

**Severity:** LOW — the project only uses simple section names, but parser claims TOML support.

---

## 2. skills/sprint-run/scripts/sync_tracking.py

### HIGH

**ST-001: `_yaml_safe` quoting is incomplete — newlines are not escaped**
`sync_tracking.py:181-204`
The function quotes values containing `: `, `#`, `[`, etc., but does not check for or escape literal newline characters. If an issue title from GitHub contains a newline (rare but possible via API), the frontmatter would break:
```yaml
title: "line1
line2"
```
This produces invalid YAML that `read_tf` would fail to parse on next read, potentially losing tracking data.

**Severity:** HIGH — corrupted tracking file from unexpected GitHub data.

**ST-002: `read_tf` regex fails on frontmatter without trailing content**
`sync_tracking.py:160`
```python
fm = re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)", content, re.DOTALL)
```
If a file is exactly `---\nkey: val\n---` with no trailing newline after the closing `---`, the `\n?(.*)` part captures an empty body. That's fine. But if the file is `---\nkey: val\n---\n` (single trailing newline), the body becomes empty string, which is also fine. The real issue: if the file starts with BOM (`\xef\xbb\xbf`), the leading `^---` doesn't match and the entire file is treated as `body_text` with no frontmatter. All fields default to empty/zero.

**Severity:** HIGH — BOM-prefixed files (common from Windows editors) silently lose all metadata.

**ST-003: `slug_from_title` produces identical slugs for different titles**
`sync_tracking.py:124-129`
```python
slug = re.sub(r"\s+", "-", re.sub(r"[^a-zA-Z0-9\s-]", "", title).strip()).lower()
```
Titles like "US-0001: Add login" and "US-0001: Add login!" produce the same slug `us-0001-add-login`. The collision detection in `create_from_issue` (line 301-305) only checks story ID mismatch, not title mismatch. Two different stories with the same ID prefix but different suffixes after stripping would collide silently (the second write_tf overwrites the first).

Actually, looking more carefully at line 301-305: `create_from_issue` reads the existing file, checks if the story ID differs, and only then appends the issue number. If two issues have the same slug AND the same story ID (duplicate detection in GitHub), this could cause the second issue's tracking data to overwrite the first. The main loop in `main()` uses `existing[tf.story]` (line 376), so duplicate story IDs are handled — the second one hits `sync_one` instead of `create_from_issue`.

**Revised severity:** MEDIUM — collision is mitigated by the story ID check, but edge cases with non-standard IDs could still lose data.

### MEDIUM

**ST-004: `get_linked_pr` timeline API returns inconsistent shapes**
`sync_tracking.py:61-99`
The `--jq` filter returns an array, but after `gh_json` processes paginated responses, `linked` could be a flat list of issues or a list of lists. Line 71 checks `if isinstance(linked, dict)` but never checks for nested lists. If the timeline API returns paginated results (unlikely for most repos but possible for issues with many cross-references), the JQ filter produces `[[issue1], [issue2]]` which `gh_json`'s paginate handler flattens. This should be fine, but the `isinstance(linked, dict)` check on line 71 would never be true since `gh_json` always returns a list for paginated results.

**Severity:** MEDIUM — dead code path (line 71-72 never executes), and the fallback logic could pick wrong PR for heavily cross-referenced issues.

**ST-005: `sync_one` doesn't detect or resolve conflicting state transitions**
`sync_tracking.py:234-278`
If an issue has both `state == "closed"` AND a kanban label like `kanban:dev`, the function sets status to "done" (line 241-245) and never updates the kanban label on GitHub. The local file says "done" but GitHub still shows the stale `kanban:dev` label. Next sync round, since `issue["state"] == "closed"`, the file stays "done" — but the GitHub label diverges permanently.

**Severity:** MEDIUM — label/status divergence between local and GitHub.

**ST-006: `write_tf` doesn't preserve unknown frontmatter keys**
`sync_tracking.py:208-228`
When reading and rewriting a tracking file, only the known fields (story, title, sprint, etc.) are preserved. If a user or another tool adds custom frontmatter keys, they are silently dropped on the next sync.

**Severity:** MEDIUM — silent data loss of user-added metadata.

---

## 3. skills/sprint-setup/scripts/populate_issues.py

### CRITICAL

**PI-001: `_safe_compile_pattern` ReDoS check is bypassable**
`populate_issues.py:82-96`
The ReDoS check tests against `"a" * 25` — a fixed, single-character string. A malicious pattern like `(b+)+$` would complete instantly on `"aaa..."` (no match, fast fail) but catastrophically backtrack on `"bbb...!"`. The test string needs to be crafted to match the pattern's vulnerable character class, not a fixed string. An attacker who controls `[backlog] story_id_pattern` in project.toml can craft a pattern that passes the safety check but causes ReDoS on actual milestone content.

**Severity:** CRITICAL — ReDoS protection is bypassable. A malicious project.toml can DoS the populate_issues script.

**Mitigation note:** The project.toml is a trusted input (same trust model as shell=True in release_gate.py), so this requires a malicious committer. But the code explicitly claims to protect against ReDoS, and that protection is broken.

### HIGH

**PI-002: `_build_row_regex` wraps user pattern in capturing group, shifting group numbers**
`populate_issues.py:113-114`
```python
return re.compile(
    rf"\|\s*({pattern})\s*\|\s*(.+?)\s*\|\s*(?:(E-\d{{4}})\s*\|\s*)?(S\d{{2}})\s*\|\s*(\d+)\s*\|\s*(P\d)\s*\|"
)
```
`_safe_compile_pattern` rejects patterns with capturing groups (line 72), but it uses the regex `(?<!\\)\((?!\?)` to detect them. This misses several patterns: `\(` (which the check treats as escaped but the outer regex would see as literal), and named groups `(?P<name>...)` are correctly caught by `(?!\?)` but `(?:...)` non-capturing groups are allowed through. However, the more subtle issue is that if `pattern` contains `|` (alternation), the wrapping `({pattern})` creates ambiguity: `(a|b)` becomes the first group, and subsequent group numbers stay correct. This is actually fine.

Revised: The actual risk is if the user pattern contains a `]` that interacts with the surrounding `\|\s*` context. For example, a pattern `[A-Z]+` in the wrapping becomes `\|\s*([A-Z]+)\s*\|` which is fine. But `[A-Z\|]+` would match the pipe delimiter, consuming the column boundary and causing the subsequent groups to mismatch. The `_safe_compile_pattern` does not check for this.

**Severity:** HIGH — user-supplied regex can consume column delimiters, causing silent story data corruption (wrong saga/sp/priority assigned).

**PI-003: `get_existing_issues` only fetches 500 issues for dedup check**
`populate_issues.py:333`
```python
issues = gh_json(["issue", "list", "--limit", "500", "--json", "title", "--state", "all"])
```
Projects with >500 issues will have incomplete dedup data. The script would create duplicate issues for stories that exist but weren't fetched. `warn_if_at_limit` prints a warning but the script continues anyway (line 337-339 only re-raises on RuntimeError, not on truncation).

**Severity:** HIGH — duplicate GitHub issues created for large projects.

### MEDIUM

**PI-004: `parse_detail_blocks` assumes exactly 3 parts per story block**
`populate_issues.py:222-226`
```python
parts = detail_re.split(content)
# parts: [preamble, id1, title1, body1, id2, title2, body2, ...]
for i in range(1, len(parts), 3):
    if i + 2 > len(parts):
        break
```
The regex has 2 capturing groups, so `split` produces groups of 3 (id, title, body). But if the user's custom `story_id_pattern` has zero capturing groups (non-capturing groups only), `_build_detail_block_re` wraps it in `({pattern})` adding 1, plus the title group `(.+)` adds another — so the groups stay at 2. This is correct. However, if the regex matches in a way that the title group is empty (e.g., `### US-0001: `), `parts[i+1].strip()` returns empty string, which becomes the story title. The story is created with no title.

**Severity:** MEDIUM — empty titles produce broken GitHub issues.

**PI-005: `enrich_from_epics` hardcodes `US-\d{4}` even when custom pattern is configured**
`populate_issues.py:301`
```python
known_sprints = [
    by_id[sid].sprint
    for sid in re.findall(r"US-\d{4}", content)
    if sid in by_id
]
```
If the project uses a custom story ID pattern like `PROJ-\d{4}`, this `re.findall` still looks for `US-\d{4}`, finds nothing, and `_most_common_sprint` returns 0. Stories from epics that only exist in detail blocks (not in milestone tables) would be skipped due to the sprint=0 guard on line 316-322.

**Severity:** MEDIUM — epic enrichment silently fails for projects with custom story ID patterns.

**PI-006: `build_milestone_title_map` can produce wrong sprint-to-milestone mapping**
`populate_issues.py:393-400`
When no sprint sections exist, the function calls `_infer_sprint_number(mf)` which may re-read the file (line 180: `content if content is not None else mf.read_text()`). But the caller at line 395 doesn't pass `content`, so the file is re-read. This isn't a bug per se, but `_infer_sprint_number` first checks for `### Sprint N:` headings (line 181) — which won't be found (since we're in the `else` branch because `sprint_nums` was empty at line 385). It then falls back to the filename. If the filename has a number that doesn't correspond to the sprint (e.g., `milestone-v2.md` for a milestone that covers sprints 5-8), the mapping is wrong and issues get assigned to the wrong milestone.

**Severity:** MEDIUM — wrong milestone assignment possible with certain filename conventions.

### LOW

**PI-007: `create_issue` doesn't add epic label even when `story.epic` is set**
`populate_issues.py:453-456`
The labels list includes saga and priority but not epic:
```python
labels = [f"sprint:{story.sprint}", "type:story", "kanban:todo"]
if story.saga:
    labels.append(f"saga:{story.saga}")
if story.priority:
    labels.append(f"priority:{story.priority}")
```
Even though `bootstrap_github.create_epic_labels` creates `epic:E-XXXX` labels, `create_issue` never applies them to issues. Epic information is only in the issue body text, not as a label.

**Severity:** LOW — missing feature, not a bug. Epic filtering by label won't work.

---

## 4. skills/sprint-release/scripts/release_gate.py

### CRITICAL

**RG-001: `_rollback_commit` uses `git reset --hard` which can destroy work**
`release_gate.py:534-536`
```python
subprocess.run(
    ["git", "reset", "--hard", pre_release_sha],
    capture_output=True, text=True,
)
```
If the release fails after the version commit but before push, the rollback does `git reset --hard`. The pre-flight check (line 465) ensures a clean working tree at start, but between the check and the rollback, another process could have created files. More importantly, the version commit itself is blown away silently — the user sees "Tag creation failed" but the commit is gone from reflog only. Actually, `git reset --hard` preserves the commit in reflog, so it's recoverable. But the destructive nature without user confirmation is concerning.

**Revised severity:** MEDIUM — recoverable via reflog, but silent destructive action.

### HIGH

**RG-002: `gate_prs` searches ALL open PRs, not milestone-filtered**
`release_gate.py:175-178`
```python
prs = gh_json([
    "pr", "list",
    "--json", "number,title,milestone", "--limit", "500",
])
```
The query fetches ALL open PRs (no milestone filter), then filters client-side on line 189-192. For repos with >500 open PRs, the 500-limit means milestone PRs could be missed. The function correctly fails the gate at 500 (lines 184-188), but the underlying issue is inefficiency and the hard failure on large repos.

**Severity:** HIGH — release gate always fails on repos with 500+ open PRs, even if none target the milestone.

**RG-003: `do_release` pushes directly to base branch without checking branch protection**
`release_gate.py:601-604`
```python
r = subprocess.run(
    ["git", "push", "origin", base_branch, f"v{new_ver}"],
    capture_output=True, text=True,
)
```
If the base branch has push protection rules (common in production repos), this push will fail. The rollback logic handles this, but the failure message (`"Push failed"`) doesn't hint that branch protection might be the cause. More critically, the push bundles the commit AND the tag in one command — if the commit push fails but the tag push partially succeeds (possible with some git server configurations), the rollback logic deletes the tag but the remote may be in an inconsistent state.

**Severity:** HIGH — partial push failure can leave remote in inconsistent state.

**RG-004: `write_version_to_toml` regex replacement can corrupt file**
`release_gate.py:296-300`
```python
release_section = re.search(r"^(?!#)\[release\]", text, re.MULTILINE)
...
next_section = re.search(r"^\[(?![\[\s\"\'])", text[start + 1:], re.MULTILINE)
```
The next-section regex `^\[(?![\[\s\"\'])` is designed to match section headers but not array-of-tables. However, if a TOML value inside `[release]` contains a line starting with `[` (e.g., an array value on its own line), the regex would incorrectly identify it as the next section boundary, truncating the `[release]` section content.

Example:
```toml
[release]
version = "1.0.0"
artifacts = [
    "bin/app"
]

[ci]
```
The `[` at `"bin/app"` line start won't match because it doesn't start at column 0 after stripping (the line has spaces). But `]` on its own line does start at column 0 — though `]` doesn't match `\[`. Actually, looking more carefully, the array items are indented so `^\[` at start-of-line won't match them. But an unindented array would match:

```toml
[release]
version = "1.0.0"
tags = [
"v1.0.0"
]
```

Here `"v1.0.0"` starts with `"` not `[`, and `]` starts with `]` not `[`. So this specific scenario is safe. The regex is actually fairly robust.

**Revised severity:** LOW — the regex handles most realistic cases correctly.

### MEDIUM

**RG-005: `parse_commits_since` with no tag fetches ALL commits**
`release_gate.py:63-64`
```python
if tag:
    cmd = ["git", "log", f"{tag}..HEAD", f"--format={fmt}"]
else:
    cmd = ["git", "log", f"--format={fmt}"]
```
For a first release on a repo with thousands of commits, this fetches every commit. The output could be very large, and `determine_bump` processes all of them. On a repo with 50K commits, this could take significant time and memory.

**Severity:** MEDIUM — performance degradation on first release of large repos.

**RG-006: `determine_bump` doesn't handle scoped breaking changes in subject line**
`release_gate.py:93`
```python
if re.match(r"^[a-z]+(\([^)]+\))?!:", subj):
```
This correctly matches `feat!: breaking` and `feat(scope)!: breaking`. But it doesn't match uppercase conventional commits (e.g., `FEAT!: breaking`), which some teams use. This is arguably correct per the conventional commits spec (lowercase types), but it's an assumption that isn't documented or validated upstream.

**Severity:** LOW — conventional commit spec says lowercase, but silent ignore of uppercase is surprising.

**RG-007: `do_release` calls `_rollback_tag` and `_rollback_commit` on GitHub Release failure, but commit was already pushed**
`release_gate.py:643-647`
```python
except RuntimeError as exc:
    _rollback_tag()
    _rollback_commit()
```
At this point, `pushed_to_remote` is `True`, so `_rollback_commit` creates a revert commit and pushes it. This means a failed GitHub Release creates TWO extra commits on the base branch (the version bump + the revert). The tag is also deleted from remote. But the git history permanently contains the bump-and-revert noise.

**Severity:** MEDIUM — messy git history on GitHub Release failure, and the revert push could itself fail.

**RG-008: Race between `git status --porcelain` check and version file write**
`release_gate.py:454-465 -> 540`
The working tree cleanliness check happens at line 454, but the version file write happens at line 540. Between these two points, another process could modify files. The pre_release_sha capture (line 493) helps with rollback, but doesn't prevent the issue.

**Severity:** MEDIUM — TOCTOU window, mitigated by typical single-user workflows.

---

## 5. skills/sprint-monitor/scripts/check_status.py

### HIGH

**CS-001: `check_ci` fetches failed run logs without size limits**
`check_status.py:69`
```python
log = gh(["run", "view", str(run_id), "--log-failed"])
```
Failed CI logs can be megabytes of text. The `gh()` function has a 60s timeout but no output size limit. `_first_error` then scans every line. For a failing test suite with thousands of lines of output, this could be slow and memory-intensive. The `gh` function captures all output into a string (line 59: `capture_output=True`).

**Severity:** HIGH — unbounded memory consumption from large CI logs.

**CS-002: `sync_backlog_main` import falls through to `None` without disabling the feature**
`check_status.py:26-30`
```python
try:
    from sync_backlog import main as sync_backlog_main
except ImportError as _import_err:
    print(f"Warning: sync_backlog unavailable: {_import_err}", file=sys.stderr)
    sync_backlog_main = None
```
If `sync_backlog` imports successfully but one of its transitive imports (bootstrap_github, populate_issues) fails, the import error is caught here and the entire sync is disabled. The user sees a warning buried in stderr that's easy to miss. The step 0 sync (line 365-370) then silently does nothing, and the user thinks their backlog is in sync when it isn't.

**Severity:** MEDIUM — silent feature degradation. Changed from HIGH because the monitor's primary job is CI/PR/milestone checking, not sync.

### MEDIUM

**CS-003: `_first_error` false positive filter is too aggressive**
`check_status.py:82-83`
```python
_FALSE_POSITIVE = re.compile(r"\b(?:0|no)\s+(?:error|fail)", re.IGNORECASE)
```
This matches "no errors" and "0 failures" — but also matches "errno" (partial word match prevented by `\b`). Actually, `\b` before `0` is a word boundary, and before `no` is also a word boundary. But consider the log line `"Error: cannot find module 'no-fail'"` — the `no` before `fail` in the module name would match the false positive filter, causing a real error to be skipped.

**Severity:** MEDIUM — real errors could be filtered out by the false positive regex.

**CS-004: `check_branch_divergence` trusts user-supplied `repo` value in API URL**
`check_status.py:238-240`
```python
data = gh_json([
    "api", f"repos/{repo}/compare/{base_branch}...{branch}",
])
```
The `repo` value comes from `config["project"]["repo"]` which comes from project.toml. If the repo value contains path traversal characters (e.g., `../other-repo`), the API URL becomes `repos/../other-repo/compare/...`. GitHub's API would likely reject this, but it's still passing unsanitized user input into an API path.

**Severity:** MEDIUM — untrusted input in API path, mitigated by gh CLI and GitHub API validation.

**CS-005: `write_log` deletion loop has no error handling**
`check_status.py:321-322`
```python
while len(logs) > MAX_LOGS:
    logs.pop(0).unlink()
```
If any `unlink()` call fails (permission denied, file in use), the exception propagates up and the entire status check fails after all the work is done. The main function catches `OSError` for the write (line 428) but the deletion happens inside `write_log`.

**Severity:** MEDIUM — old log cleanup failure crashes the monitor.

### LOW

**CS-006: `check_milestone` silently returns partial data when SP query fails**
`check_status.py:196-207`
```python
try:
    issues = gh_json([...])
    t_sp, d_sp = _count_sp(issues)
    if t_sp:
        sp_part = f", {d_sp}/{t_sp} SP"
except RuntimeError:
    pass
```
If the issue query fails, the milestone progress is reported without SP data, and there's no indication in the output that SP data is missing. The user sees "5/10 stories done (50%)" without knowing whether that's 5/50 SP or 5/10 SP.

**Severity:** LOW — degraded output quality, not a correctness issue.

---

## 6. scripts/sync_backlog.py

### HIGH

**SB-001: `do_sync` calls `populate_issues.get_existing_issues()` which can raise RuntimeError, but error path saves state incorrectly**
`sync_backlog.py:224-231`
```python
try:
    counts = do_sync(config)
except Exception as exc:
    # BH-021: Do NOT update state on failure — next run should retry
    print(f"sync: do_sync failed — {exc}", file=sys.stderr)
    print("sync: state NOT updated; next run will retry")
    save_state(config_dir, state)
    return "error"
```
The comment says "Do NOT update state on failure" and "next run will retry". But `state` was already mutated by `check_sync` (line 215) — specifically, `pending_hashes` was set to `current_hashes` in a previous invocation, and in this invocation, since `current_hashes == pending` (stabilized), `check_sync` returned `SyncResult("sync", True, ...)` without clearing `pending_hashes`. So saving the state here actually preserves `pending_hashes` pointing to the current hashes. On next run, `current_hashes == stored`? No — `file_hashes` hasn't been updated. So `current_hashes != stored`, and `pending` is still the current hashes, so `current_hashes == pending` — which means `check_sync` returns "sync" again. This IS correct retry behavior. But the state mutation comment is misleading — the state WAS mutated by check_sync in a previous call, and that mutation is being preserved.

The actual bug: if `do_sync` partially succeeds (creates some milestones, then fails on issues), the next retry recreates the milestones (idempotent, fine) and also retries all issues. The `get_existing_issues()` call inside `do_sync` will detect the partially-created issues, so this is safe. No real bug here.

**Revised severity:** LOW — the comment is misleading but the behavior is correct.

**SB-002: `hash_milestone_files` uses filename as key, not full path**
`sync_backlog.py:51`
```python
result[p.name] = digest
```
If two milestone files have the same filename in different directories (unlikely but possible with custom backlog structures), only one hash is stored. A change to the shadowed file would never be detected.

**Severity:** MEDIUM — filename collision in hash map causes missed file changes.

### MEDIUM

**SB-003: `check_sync` debounce requires exactly two consecutive matching calls**
`sync_backlog.py:115-152`
The debounce logic works by: (1) first detection sets `pending_hashes`, returns "debouncing"; (2) second call with same hashes returns "sync". But if the monitor loop interval is long (5 minutes per SKILL.md), the file could change between the two calls without being detected. The debounce only ensures the hash is stable across TWO calls, not that the file hasn't changed during the interval. A file that changes rapidly but happens to have the same hash at both sample points would be considered "stable".

**Severity:** MEDIUM — debounce granularity depends entirely on caller's polling interval.

**SB-004: `save_state` writes JSON without atomic rename**
`sync_backlog.py:88-89`
```python
path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
```
If the process is killed during the write, the state file could be truncated/corrupt. Next `load_state` call would hit `json.JSONDecodeError` and return defaults, which means all file hashes are lost and the next sync considers everything changed (triggering a full re-sync). The full re-sync is idempotent, so no data loss, but it's wasteful.

**Severity:** MEDIUM — crash during write causes unnecessary full re-sync.

**SB-005: `main()` catches `ConfigError` at module level but `do_sync` calls `load_config` indirectly through `get_milestones`**
`sync_backlog.py:201 vs 156`
`main()` calls `load_config()` (line 201) and stores the config. Then `do_sync(config)` is called with that config. Inside `do_sync`, `get_milestones(config)` (line 168) is called, which uses the already-loaded config. But `bootstrap_github.create_milestones_on_github(config)` at line 172 internally calls `get_milestones(config)` again and also calls `gh()` which could raise RuntimeError. The `except Exception` in `main()` catches this.

However, `populate_issues.get_existing_issues()` at line 180 can raise RuntimeError (it re-raises on line 339), and this propagates through the `except Exception` handler correctly. No actual bug, but the error handling is split across multiple layers making it hard to reason about.

**Severity:** LOW — code is correct but the error propagation path is convoluted.

---

## Cross-Cutting Issues

### HIGH

**CC-001: Inconsistent `issue["title"]` key assumption across scripts**
Multiple files assume `issue["title"]` is always present and non-empty:
- `sync_tracking.py:285` — `extract_story_id(issue["title"])` — KeyError if "title" missing
- `update_burndown.py:158` — `extract_story_id(issue["title"])` — same
- `populate_issues.py:344` — `issue.get("title", "")` — safe
- `check_status.py` — doesn't access issue titles directly

The gh_json queries include `"title"` in `--json` fields, so gh CLI should always return it. But if the GitHub API returns a malformed response (empty object in array), the KeyError would crash the sync/burndown scripts mid-run, leaving partially-written files.

**Severity:** HIGH — unhandled KeyError from malformed API response crashes mid-operation.

**CC-002: Three independent implementations of "short title" extraction**
- `sync_tracking.py:293-296`: `issue["title"].split(":", 1)[-1].strip()`
- `update_burndown.py:159-162`: identical logic
- `populate_issues.py:412`: `story.title` (already the short part)

If the title format changes (e.g., from `US-0001: Title` to `US-0001 - Title`), two scripts need updating. This should be a shared function in validate_config.py.

**Severity:** MEDIUM — duplicated logic will diverge.

**CC-003: `kanban_from_labels` + closed-issue override is duplicated in three places**
The pattern `status = kanban_from_labels(issue); if closed and status != "done": status = "done"` appears in:
- `sync_tracking.py:240-245` (sync_one)
- `sync_tracking.py:290-291` (create_from_issue)
- `update_burndown.py:169-171` (build_rows)

This override logic should be in `kanban_from_labels` itself, or in a wrapper function. If the logic changes (e.g., adding a "cancelled" state for closed-but-not-done), three places need updating.

**Severity:** MEDIUM — triplicated business logic, divergence risk.

**CC-004: `sys.path.insert(0, ...)` is used everywhere but path calculation varies**
Each script calculates the path to `scripts/` differently:
- `sync_tracking.py:21`: `parent.parent.parent.parent / "scripts"` (4 levels up)
- `check_status.py:22`: same 4 levels
- `sync_backlog.py:23`: `parent` (same directory)
- `sprint_analytics.py:19`: `parent` (same directory)

If a script is moved to a different directory depth, the import silently fails and the script crashes with a confusing ImportError. No mechanism validates the path is correct before importing.

**Severity:** LOW — brittle but working; would only break if file is moved.

### MEDIUM

**CC-005: All `gh_json` list queries use `--limit 500` or `--limit 1000` with warn-only on truncation**
Every query that could return more results than the limit emits a warning but continues processing with incomplete data. Scripts like `sync_tracking.py`, `populate_issues.py`, and `sprint_analytics.py` silently operate on partial data. The `warn_if_at_limit` function returns a boolean, but no caller uses it to abort or paginate.

In `populate_issues.py:333`, truncated results mean the dedup check is incomplete, leading to duplicate issues. In `sync_tracking.py:43`, truncated PR results mean some story-PR links are missed.

**Severity:** MEDIUM — data integrity degrades silently at scale.

**CC-006: No locking on shared state files**
Multiple scripts write to the same files:
- `SPRINT-STATUS.md` — written by `update_burndown.py` and `release_gate.py`
- `.sync-state.json` — written by `sync_backlog.py` (called from `check_status.py`)
- Story tracking files — written by `sync_tracking.py`

If two processes (e.g., a manual sync_tracking run and a monitor-triggered sync) run simultaneously, they could corrupt these files. No file locking is used anywhere.

**Severity:** MEDIUM — race condition on concurrent execution, mitigated by typical single-user workflows.

---

## Positive Observations

The codebase has clearly been through multiple rounds of hardening (the BH-xxx fix references). Notable strengths:

1. **Idempotent design** — bootstrap and sync scripts handle re-runs gracefully
2. **Error messages** — most RuntimeError messages include the failing command and context
3. **Defensive type checks** — `isinstance(label, str) / isinstance(label, dict)` pattern is thorough
4. **Trust model documentation** — the shell=True usage in release_gate.py has explicit trust model comments
5. **Paginate handling** — gh_json's incremental decoder handles concatenated JSON arrays
6. **Rollback logic** — release_gate.py has multi-stage rollback (tag + commit + remote)
7. **BOM/encoding** — consistent `encoding="utf-8"` on all file operations

---

## Recommended Priority Fixes

1. **PI-001 (CRITICAL):** Replace the fixed-string ReDoS test with a pattern-aware approach, or use `re.fullmatch` with a timeout (Python 3.11+ has no native timeout, but you can use the `signal` module on Unix).

2. **VC-001 (CRITICAL):** Either support quoted TOML keys or explicitly reject them with a clear error instead of silent dropping.

3. **VC-003 (HIGH):** At minimum, warn on unknown escape sequences. Ideally, raise ValueError.

4. **ST-001 (HIGH):** Add newline escaping to `_yaml_safe`. Also escape `\r`.

5. **CC-001 (HIGH):** Wrap all `issue["title"]` accesses in `.get("title", "")` with a warning when missing.

6. **PI-003 (HIGH):** Add pagination or increase the limit for `get_existing_issues`, or abort if truncated.

7. **CC-003 (MEDIUM):** Extract the closed-issue kanban override into a shared function.

8. **CC-002 (MEDIUM):** Extract short-title extraction into a shared function in validate_config.py.
