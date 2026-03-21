# Audit: populate_issues.py

**File:** `skills/sprint-setup/scripts/populate_issues.py`
**Coverage:** 71% (84 lines uncovered)
**Date:** 2026-03-16

---

## Findings

### 1. SECURITY: No shell injection, but issue body content is unsanitized (LOW)

**Lines:** 397-404 (create_issue)

`create_issue` passes `story.title` and the formatted body directly to `gh()` as
list arguments (`["issue", "create", "--title", title, "--body", body]`), which
go through `subprocess.run(["gh", *args])`. Because the arguments are passed as
a list (not a shell string), there is no classic shell injection.

However, the issue body and title are composed entirely from user-authored
markdown files (milestone docs, epic files). A malicious markdown file could
craft a title or body that confuses the `gh` CLI argument parser -- for example
a title starting with `--` could be interpreted as a flag. The `gh` CLI is
generally resilient to this since `--title` consumes the next arg as a value,
but this is defense-by-coincidence, not defense-by-design.

**Recommendation:** Prefix titles with a space or use `--` separator before
positional args if the CLI ever changes.

---

### 2. BUG: `get_existing_issues` regex misses custom story ID patterns (MEDIUM)

**Lines:** 289

```python
m = re.match(r"([A-Z]+-\d+):", issue.get("title", ""))
```

This hardcodes the `[A-Z]+-\d+` pattern for extracting story IDs from existing
issues. But `_build_row_regex` allows the config to specify a custom
`story_id_pattern` (line 70). If a project uses e.g. `PROJ-\d{4}` as their
pattern, the idempotency check works fine (it matches `[A-Z]+-\d+`). But if
someone configures a pattern like `\d{4}` (numeric-only IDs), the idempotency
check in `get_existing_issues` will fail to recognize existing issues, causing
duplicate creation.

**Severity:** Medium. The default `US-\d{4}` pattern works, and most custom
patterns would still match `[A-Z]+-\d+`. But the contract between
`_build_row_regex` and `get_existing_issues` is not enforced.

**Test gap:** `get_existing_issues` is tested (line 374-395 of
test_sprint_runtime.py) but only with `US-XXXX` titles, never with custom ID
patterns.

---

### 3. BUG: `_most_common_sprint` returns 0 for empty list -- downstream creates orphan issues (MEDIUM)

**Lines:** 220-221, 251-252, 263-270

When `enrich_from_epics` processes an epic file where no story IDs match the
existing `by_id` lookup, `known_sprints` is empty, so `_most_common_sprint`
returns 0. The code at line 263 correctly guards against this:

```python
elif sprint == 0:
    print(f"  Warning: skipping {ps.story_id} ...")
```

This is good defensive code (BH-011 fix). However, the warning goes to stdout
(not stderr) which is inconsistent -- other warnings in the file use
`file=sys.stderr`.

**Test gap:** The `sprint == 0` skip path (lines 263-270) is uncovered. No test
verifies that stories with undeterminable sprint numbers are actually skipped.

---

### 4. LOGIC: `build_milestone_title_map` silently overwrites on conflict (LOW)

**Lines:** 333-345

When two milestone files map to the same sprint number, the function warns but
then overwrites with the later file's title. The warning message says "using
'{title}' (from {mf.name})" but this depends on file iteration order, which
depends on `sorted()` order of milestone_files. Since milestone_files come from
config in declaration order, this is deterministic but potentially surprising.

The filename-fallback path (lines 339-345) calls `_infer_sprint_number(mf)`
**without** passing the `content` parameter, causing the file to be read again.
This is a minor inefficiency -- the content was already read on line 324.

**Test gap:** Lines 339-345 (filename fallback in `build_milestone_title_map`)
are uncovered.

---

### 5. UNTESTED: `check_prerequisites` is never tested (LOW)

**Lines:** 37-43

`check_prerequisites()` runs `gh auth status` via raw `subprocess.run` (not
the shared `gh()` helper). It calls `sys.exit(1)` on failure. No test covers
this function.

This function also does not use the shared `gh()` wrapper, meaning it bypasses
the timeout and error formatting that other gh calls get. If `gh` is not
installed, `subprocess.run` raises `FileNotFoundError`, which is unhandled.

**Test gap:** Zero coverage on lines 39-43.

---

### 6. UNTESTED: `main()` function is never tested (LOW)

**Lines:** 419-480

The entire `main()` flow is uncovered. Tests exercise individual functions
(`parse_milestone_stories`, `create_issue`, etc.) but never the orchestration
in `main()`. Error paths like "no milestone files found" (line 434), "no
stories found" (line 441), and the RuntimeError catch for `get_existing_issues`
(line 452) are all untested.

**Test gap:** Lines 428-476, 480 are all uncovered.

---

### 7. BUG: `_DETAIL_BLOCK_RE` only matches `US-\d{4}` -- ignores custom patterns (MEDIUM)

**Lines:** 159

```python
_DETAIL_BLOCK_RE = re.compile(r"^###\s+(US-\d{4}):\s+(.+)$", re.MULTILINE)
```

This regex is hardcoded to `US-\d{4}` for detail block headers. Unlike the
table-row regex (which respects `_build_row_regex` and custom
`story_id_pattern`), detail blocks always require `US-XXXX` format. Projects
using a custom story ID pattern will have their detail blocks silently ignored
during enrichment.

**Test gap:** No test exercises `parse_detail_blocks` with non-US-XXXX IDs.

---

### 8. BUG: `_META_ROW_RE` matches separator rows and header rows partially (LOW)

**Lines:** 160, 179

```python
_META_ROW_RE = re.compile(r"^\|\s*(.+?)\s*\|\s*(.+?)\s*\|$", re.MULTILINE)
```

This regex matches any two-column markdown table row. The header row is filtered
out by checking `if key != "Field"` (line 179), but separator rows like
`|-------|-------|` will match with key=`-------` and value=`-------`. These
get added to the `meta` dict as `meta["-------"] = "-------"`. This is harmless
since no downstream code looks up that key, but it is sloppy parsing.

---

### 9. LOGIC: `parse_detail_blocks` off-by-one guard is unreachable (LOW)

**Lines:** 171-172

```python
if i + 2 > len(parts):
    break
```

Given that `range(1, len(parts), 3)` already ensures `i` is in bounds, and
`_DETAIL_BLOCK_RE.split()` always produces groups of 3 (id, title, body) after
the preamble, the condition `i + 2 > len(parts)` can only be true if the
regex split produces a partial group at the end. With the current regex (which
has exactly 2 capturing groups), `re.split` always produces complete triplets.
This line is defensive but effectively dead code.

**Test gap:** Line 172 is uncovered (confirmed by coverage report).

---

### 10. UNTESTED: `_build_row_regex` error paths (MEDIUM)

**Lines:** 73-84

Two defensive paths in `_build_row_regex`:
- Line 73-76: Reject patterns with unescaped capturing groups
- Line 81-84: Catch `re.error` for invalid regex patterns

Neither path has a direct test. These are safety-critical for preventing
group-number shifts that would corrupt all parsed story data.

**Test gap:** Lines 73-84 are uncovered. A property test or unit test with a
malicious `story_id_pattern` config would catch regressions here.

---

### 11. DUPLICATION: `sync_backlog.do_sync` duplicates the `main()` orchestration (INTENTIONAL)

**Lines:** sync_backlog.py:156-191 vs populate_issues.py:419-476

`sync_backlog.do_sync()` reimplements essentially the same pipeline as
`populate_issues.main()`: parse stories, enrich from epics, get existing
issues, get milestone numbers, build title map, create issues. The CLAUDE.md
documents this as intentional ("sync_backlog reuses the idempotent creation
functions rather than duplicating them"). The functions are reused but the
orchestration is duplicated.

This means a bug fix to the orchestration flow in `main()` must also be applied
to `do_sync()`. For example, if someone adds a new enrichment step to `main()`,
they must remember to add it to `do_sync()` as well.

---

### 12. EDGE CASE: `enrich_from_epics` can assign sprint=0 to new stories (MEDIUM)

**Lines:** 251-271

When an epic file contains stories not found in the `by_id` lookup AND
`_most_common_sprint` returns 0, the code correctly skips them (line 263-269).
But when `_most_common_sprint` returns a nonzero value based on a single
match, ALL new stories from that epic file get assigned that sprint number,
even if they logically belong to a different sprint. This is a best-effort
heuristic, but could silently assign stories to the wrong milestone.

Example: epic file mentions US-0101 (sprint 1) and US-0201 (sprint 2), but
US-0201 is not in `by_id`. If US-0101 IS in `by_id`, the heuristic picks
sprint 1, and any new stories from the epic get sprint 1 -- possibly wrong.

---

### 13. EDGE CASE: `get_existing_issues` 500-issue limit may cause duplicates (LOW)

**Lines:** 280-283

`get_existing_issues` fetches at most 500 issues (`--limit 500`) and calls
`warn_if_at_limit`. For projects with >500 issues, the function will miss some
existing stories, potentially causing duplicate issue creation. The warning
prints to stderr but does not abort -- execution continues with an incomplete
set.

The `--state all` flag means it fetches both open and closed issues, which
is correct for idempotency, but increases the likelihood of hitting the limit.

---

### 14. EDGE CASE: `format_issue_body` AC numbering ignores original AC IDs (LOW)

**Lines:** 371-372

```python
for i, ac in enumerate(story.acceptance_criteria, 1):
    lines.append(f"- [ ] `AC-{i:02d}`: {ac}")
```

The acceptance criteria are renumbered sequentially (AC-01, AC-02, ...) even
if the source epic file had different numbering (e.g., AC-05, AC-06). The
original AC IDs from the epic file are stripped during `parse_detail_blocks`
(line 190 extracts only the text after `AC-\d+`), so the mapping between
source AC IDs and issue AC IDs is lost.

This could cause confusion when cross-referencing test cases that reference
original AC IDs from the epic file.

---

### 15. UNTESTED: `get_milestone_numbers` (MEDIUM)

**Lines:** 296-306

`get_milestone_numbers()` calls the GitHub API to fetch milestone data and
has error handling for `RuntimeError` and `KeyError`. This function is never
directly unit-tested. It is exercised indirectly through integration tests
(test_lifecycle.py, test_hexwise_setup.py) that use FakeGitHub, but there
are no tests for:
- API returning non-list data (line 301-302)
- Missing "title" or "number" keys in milestone objects (line 303, KeyError)
- API failure (lines 304-306)

---

### 16. BUG: `_infer_sprint_number` reads file when content=None but file may not exist (LOW)

**Lines:** 145

```python
text = content if content is not None else mf.read_text(encoding="utf-8")
```

If called with `content=None` and `mf` points to a nonexistent file, this
raises `FileNotFoundError`. Currently, all callers either pass content or
verify the file exists first (line 99 checks `mf.is_file()`), so this is
not reachable in practice. But `_infer_sprint_number` is a public-ish helper
that could be called from new code without the guard.

The `build_milestone_title_map` function at line 340 calls
`_infer_sprint_number(mf)` WITHOUT passing content, but line 322 already
checks `mf.is_file()`, so this is safe.

---

### 17. MISSING TEST: `parse_milestone_stories` with missing file path (LOW)

**Lines:** 99-101

The warning path when a milestone file does not exist is uncovered:
```python
if not mf.is_file():
    print(f"  Warning: Milestone file not found: {mf}")
    continue
```

---

### 18. MISSING TEST: Duplicate story ID detection (LOW)

**Lines:** 107-110

The duplicate story ID detection path is uncovered:
```python
if sid in seen_ids:
    print(f"  Warning: duplicate story ID {sid} ...")
    return
```

No test creates a milestone file with duplicate story IDs to verify
this deduplication works.

---

## Coverage Gap Summary

| Lines | Function/Path | Severity |
|-------|--------------|----------|
| 39-43 | `check_prerequisites` | Low |
| 73-84 | `_build_row_regex` error paths | Medium |
| 99-101 | Missing milestone file warning | Low |
| 107-110 | Duplicate story ID warning | Low |
| 129-131 | Fallback whole-file scan (no sprint sections) | Low |
| 159 | `_DETAIL_BLOCK_RE` hardcoded pattern | Medium |
| 172 | `parse_detail_blocks` off-by-one guard | Low |
| 221 | `_most_common_sprint` empty list | Low |
| 263-271 | `enrich_from_epics` sprint=0 skip path | Medium |
| 282 | `get_existing_issues` non-list check | Low |
| 296-306 | `get_milestone_numbers` entirely | Medium |
| 339-345 | `build_milestone_title_map` filename fallback | Low |
| 414-416 | `create_issue` RuntimeError path | Low |
| 428-476 | `main()` orchestration | Low |

## Recommendations (prioritized)

1. **Finding 2 + 7:** Unify the story ID pattern. Either make
   `_DETAIL_BLOCK_RE` and `get_existing_issues` respect the custom
   `story_id_pattern`, or document that only `US-\d{4}` is supported for
   detail blocks and idempotency.

2. **Finding 10:** Add unit tests for `_build_row_regex` with capturing groups
   and invalid regex patterns. These are safety-critical paths.

3. **Finding 3 + 12:** Add a test for the `sprint == 0` skip path in
   `enrich_from_epics`. This was a BH-011 fix but has no regression test.

4. **Finding 15:** Add direct unit tests for `get_milestone_numbers` error
   handling.

5. **Finding 11:** Consider extracting the shared orchestration pipeline from
   `main()` and `sync_backlog.do_sync()` into a common function to prevent
   drift.
