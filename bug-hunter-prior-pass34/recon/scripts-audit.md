# Scripts Audit Report — 2026-03-20 (Pass 2)

Full audit of 11 utility scripts focused on state mutations, edge cases,
integration issues, and error handling.  Supersedes prior pass (6 scripts).

Prior findings marked [FIXED] have been verified resolved in the current codebase.
Prior findings marked [STILL OPEN] persist.  New findings have fresh IDs.

---

## 1. `scripts/risk_register.py`

### FINDING-1: `resolve_risk()` does not escape pipe in resolution text
**Files:** risk_register.py
**Severity:** MEDIUM
**Description:** `add_risk()` now escapes `|` in titles (line 92), but
`resolve_risk()` only escapes the `resolution` parameter (line 113).
However, the resolution is inserted into cells that are rebuilt with
`" | ".join(cells)` on line 115.  If any *existing* cell already contains
an unescaped `|` from before the pipe-escaping fix was added, the
`_split_table_row()` call on line 107 will split on it, producing the
wrong number of cells and corrupting the row on write-back.
**Evidence:** Line 107 splits with `unescape=False`, which preserves
`\|` in cells but a legacy row written before the escaping fix would
have raw `|` in the title, causing a mis-split.

### FINDING-2: `_read_register()` creates file but operational functions use hardcoded relative path
**Files:** risk_register.py
**Severity:** MEDIUM
**Description:** `_REGISTER_PATH = Path("sprint-config/risk-register.md")` is a
module-level constant relative to cwd.  The script imports `load_config` but
never calls it in any operational function.  If invoked from a subdirectory or
if the config dir is non-default, the register will be read/written in the
wrong location.  All other scripts derive paths from config.
**Evidence:** Line 23 (`_REGISTER_PATH`), lines 88-96 (`add_risk`), lines 99-120
(`resolve_risk`) -- none accept a path parameter or consult config.

### FINDING-3: `add_risk()` writes without atomic strategy
**Files:** risk_register.py
**Severity:** LOW
**Description:** `add_risk()` reads the full file, appends a row, and writes
back with `write_text()`.  If the process is interrupted mid-write, the file
could be truncated.  The kanban system uses `atomic_write_tf()` (temp-then-rename)
for exactly this reason.  The risk register has no such protection.
**Evidence:** Line 95: `_REGISTER_PATH.write_text(text, encoding="utf-8")`

### FINDING-4: `_parse_rows()` does not validate row structure before dict access
**Files:** risk_register.py
**Severity:** LOW
**Description:** `_parse_rows()` checks `len(cells) >= 6` but then accesses
`cells[6]` with a conditional `if len(cells) > 6` (line 83).  A row with
exactly 6 cells will have an empty `"resolution"` key.  This works but makes
the 7-column table format fragile -- if a row has trailing whitespace that
produces an extra empty cell from `_split_table_row`, the count shifts.
**Evidence:** Lines 75-84.

---

## 2. `scripts/smoke_test.py`

### FINDING-5: `write_history()` does not sanitize command or status for markdown table
**Files:** smoke_test.py
**Severity:** MEDIUM
**Description:** The `command` value is inserted directly into a markdown table
cell (line 87) inside backticks.  If the command contains a backtick character,
this breaks the markdown formatting.  If the command contains `|`, it breaks
the table structure.  The command comes from `project.toml`, so this is a
config-sourced injection into the history file.
**Evidence:** Line 87: `f"| {timestamp} | {commit} | \`{command}\` | {status} |\n"`
-- no escaping of `|` or `` ` `` in `command`.

### FINDING-6: `write_history()` appends without locking
**Files:** smoke_test.py
**Severity:** LOW
**Description:** If two `smoke_test.py` invocations run concurrently (e.g., from
parallel CI jobs), both will `open(history_path, "a")` and append.  While OS-level
append atomicity for small writes is generally safe on most filesystems, the
initial file creation check on line 77 has a TOCTOU race: both processes could
see `not history_path.is_file()`, both write the header, then both append data,
producing a file with duplicate headers.
**Evidence:** Lines 77-87.

### FINDING-7: [FIXED] `smoke_timeout` validation
**Description:** Prior SMOKE-2 finding.  Now uses `safe_int()` (line 108).

---

## 3. `scripts/sprint_analytics.py`

### FINDING-8: `compute_velocity()` and `compute_workload()` make separate GitHub API calls for the same milestone
**Files:** sprint_analytics.py
**Severity:** LOW
**Description:** `compute_velocity()` (line 44) and `compute_workload()` (line 140)
both call `gh_json(["issue", "list", ...])` for the same milestone with
slightly different `--json` fields.  This makes 2 API calls that could be
combined into one, doubling latency and API rate consumption.  In a CI context
with rate limiting this is wasteful.
**Evidence:** Lines 44-49 (`compute_velocity`), lines 140-147 (`compute_workload`).

### FINDING-9: `compute_review_rounds()` search filter is unreliable
**Files:** sprint_analytics.py
**Severity:** MEDIUM
**Description:** The `--search` flag with `milestone:"title"` (line 91) uses
GitHub's search syntax, which is known to be fuzzy and can over-match.  The
code has a post-filter on lines 99-103 to correct this, but the `gh pr list`
call with `--state all` and `--search` can also silently drop results if the
search index is stale or if the milestone title contains special characters
(quotes, colons).  The post-filter only removes false positives; it cannot
recover false negatives from the search.
**Evidence:** Lines 87-103.  The BH23-217 comment acknowledges the over-include
risk but doesn't address under-include.

### FINDING-10: `main()` hand-rolled arg parser doesn't handle combined flags
**Files:** sprint_analytics.py
**Severity:** LOW
**Description:** The script uses a hand-rolled parser (lines 203-223) that only
recognizes `-h`/`--help` as the first argument.  If a user passes
`sprint_analytics.py 3 --help` or `sprint_analytics.py --verbose 3`, the
script will print a usage error or crash with an unhelpful message.  The
comment on line 201 acknowledges this is intentional, but it means the script
cannot be extended with flags (like `--format json`) without switching to
argparse.
**Evidence:** Lines 197-223.

### FINDING-11: `sprint_theme` extraction regex is too greedy
**Files:** sprint_analytics.py
**Severity:** LOW
**Description:** `re.search(r"Sprint Theme:\s*(.+)", text)` on line 251 captures
everything after "Sprint Theme:" to end of line, including any trailing markdown
formatting (bold markers, links, etc.).  If the kickoff file has
`Sprint Theme: **Velocity Boost**`, the theme will be `**Velocity Boost**`
with the bold markers included.
**Evidence:** Line 251.

### FINDING-12: Analytics file append has no file locking
**Files:** sprint_analytics.py
**Severity:** LOW
**Description:** The dedup check (line 277) reads the file, then the append
(line 280) opens and writes.  If two processes run concurrently for the same
sprint, both could pass the dedup check and append duplicate entries.
The dedup regex uses `re.MULTILINE` and word boundaries, which is correct,
but the read-check-write sequence is not atomic.
**Evidence:** Lines 276-281.

---

## 4. `scripts/traceability.py`

### FINDING-13: `parse_stories()` metadata scan can bleed into body content
**Files:** traceability.py
**Severity:** MEDIUM
**Description:** The metadata table scanner (lines 53-70) stops on a blank line
only if `j > i + 2` (line 65).  This means if the metadata table has only
1 row followed by a blank line, the scanner does not stop -- it continues
scanning body content below the table.  Any body line matching `TABLE_ROW`
(e.g., a markdown table in the story's description) will be incorrectly
parsed as metadata.
**Evidence:** Line 65: `elif lines[j].strip() == "" and j > i + 2:` -- the
`j > i + 2` guard was likely meant to skip the heading line + separator, but
it means short metadata tables (1-2 rows) don't trigger the blank-line stop.

### FINDING-14: `parse_requirements()` uses `rglob` while `parse_stories()` and `parse_test_cases()` use `glob`
**Files:** traceability.py
**Severity:** LOW
**Description:** `parse_requirements()` on line 114 uses `prd_path.rglob("*.md")`
to recursively scan all subdirectories, while `parse_stories()` (line 43) and
`parse_test_cases()` (line 91) use non-recursive `glob("*.md")`.  If epic files
or test plan files are organized in subdirectories, they will be silently missed.
This inconsistency means the traceability report could show requirements
referencing stories that weren't parsed (because the epic file was in a
subdirectory).
**Evidence:** Line 114 (`rglob`) vs. lines 43, 91 (`glob`).

### FINDING-15: `build_traceability()` does not detect dangling test case references
**Files:** traceability.py
**Severity:** LOW
**Description:** The function reports stories without test cases and requirements
without stories, but does not report test cases that are not referenced by any
story.  "Orphaned" test cases (defined in the test plan but never linked from
any story) are silently ignored.  The `test_cases` dict is built but only used
for its count.
**Evidence:** Lines 128-169.  `test_cases` is returned in the report dict but
`format_report()` never checks for orphaned test cases.

---

## 5. `scripts/test_coverage.py`

### FINDING-16: Rust test pattern uses `re.findall` with `\s*` that does not span newlines by default
**Files:** test_coverage.py
**Severity:** MEDIUM
**Description:** The Rust test pattern on line 23 is:
```python
re.compile(r'#\[(?:test|tokio::test|async_std::test)\]\s*(?:#\[.*\]\s*)*(?:async\s+)?fn\s+(\w+)')
```
The `\s*` between `#[test]` and `fn` does not match newlines by default (no
`re.DOTALL`).  In standard Rust style, `#[test]` is on the line above the `fn`:
```rust
#[test]
fn test_something() { ... }
```
Since the pattern requires `#[test]` and `fn` on the same line (or connected
by non-newline whitespace), it will NOT match the standard Rust test format.
The only tests it will match are single-line `#[test] fn foo()` or tests
where `#[test]` and `fn` happen to be on the same line.
**Evidence:** Line 23.  This renders the Rust test detection in `test_coverage.py`
effectively broken for most Rust projects.

### FINDING-17: `scan_project_tests()` reads Rust source files that are not test files
**Files:** test_coverage.py
**Severity:** LOW
**Description:** The Rust file patterns on line 32 include `**/src/**/*.rs`,
which matches ALL Rust source files, not just test files.  While this is
intentional (Rust `#[test]` functions can live in any source file), it means
the scanner reads every `.rs` file in the project tree.  For large Rust projects,
this could be slow and memory-intensive.
**Evidence:** Line 32: `"rust": ["**/tests/**/*.rs", "**/src/**/*.rs"]`.

### FINDING-18: Fuzzy matching can produce false negatives for test cases with short IDs
**Files:** test_coverage.py
**Severity:** LOW
**Description:** The slug matching on lines 125-135 splits on the first underscore
to extract the slug portion.  For a TC ID like `TC-A-1`, the normalized form is
`tc_a_1` and the slug is `a_1` (only 3 chars).  Since the minimum slug length
for matching is 4 chars (line 134), this slug is skipped.  If no test function
contains `tc_a_1` as a substring but does contain `a_1`, the match fails.
**Evidence:** Lines 124-135.  Short TC IDs (under 4 chars after prefix removal)
can only match via the full normalized form, not the slug.

---

## 6. `scripts/manage_epics.py`

### FINDING-19: `remove_story()` silently returns on missing story ID
**Files:** manage_epics.py
**Severity:** MEDIUM
**Description:** `remove_story()` returns without error if the story ID is not
found (line 243: `if not section: return`).  The CLI `main()` then prints
"Removed {story_id} from {epic_file}" (line 387) even though nothing was
removed.  This misleading success message could cause confusion in automated
workflows.
**Evidence:** Lines 242-243 (`remove_story` returns silently), line 387 (prints
success unconditionally).

### FINDING-20: `reorder_stories()` walks back past header content
**Files:** manage_epics.py
**Severity:** MEDIUM
**Description:** The walk-back loop on lines 283-285 removes blank lines and
`---` separators above the first story section.  However, if the epic file has
a metadata table followed by a blank line and then a `---` separator before the
first story, this walk-back will eat the blank line that terminates the metadata
table, potentially merging the header table with the story content on rewrite.
The walk-back has no guard against going past the header table.
**Evidence:** Lines 283-285:
```python
while stories_start > 0 and lines[stories_start - 1].strip() in ("", "---"):
    stories_start -= 1
```
This walks backward unconditionally over all blank/separator lines.

### FINDING-21: `renumber_stories()` replaces in all non-heading lines, including code blocks
**Files:** manage_epics.py
**Severity:** MEDIUM
**Description:** `renumber_stories()` uses `re.sub` with word boundary matching
to replace old story IDs on every non-heading line (line 360).  This will replace
occurrences inside fenced code blocks, inline code, URLs, and comments.  A code
block containing `// Reference: US-0102` would have the reference corrupted to
`// Reference: US-0102a, US-0102b`.
**Evidence:** Lines 355-361.  The heading preservation (line 356-358) is good,
but no other context is checked.

### FINDING-22: `add_story()` accepts empty story ID
**Files:** manage_epics.py
**Severity:** LOW
**Description:** If `story_data` has no `"id"` key, `story_data.get("id", "")`
returns empty string (line 216).  The `if story_id:` check (line 217) then
skips the duplicate check entirely, allowing a story with no ID to be appended.
The formatted section will have `### : Untitled` as its heading, which won't
parse correctly on re-read.
**Evidence:** Lines 216-220.

### FINDING-23: `_format_story_section()` shadow variable `sp`
**Files:** manage_epics.py
**Severity:** LOW
**Description:** The variable `sp` is assigned on line 157 for story points, then
reassigned on line 203 for task SP inside the tasks loop.  While Python scoping
makes this technically fine (the first `sp` is no longer needed by then), it
reduces readability and could cause bugs if the function is extended.
**Evidence:** Line 157: `sp = story_data.get("story_points", 0)`, line 203:
`sp = task.get("sp", 1)`.

---

## 7. `scripts/manage_sagas.py`

### FINDING-24: Section replacement can corrupt file when section is not the last one
**Files:** manage_sagas.py
**Severity:** HIGH
**Description:** All three update functions (`update_sprint_allocation`,
`update_epic_index`, `update_team_voices`) use the pattern:
```python
new_lines = lines[:start] + new_section + [""] + lines[end:]
```
The `end` value comes from `_find_section_ranges()`, which sets `end` to the
start of the *next* `##` section.  But `new_section` starts with the `## `
heading itself.  So if the replacement section content is longer or shorter
than the original, all subsequent section ranges computed from the original
`lines` list are invalidated.  This is fine when only ONE section is updated
per call, but if a caller were to chain updates (e.g., update allocation then
update index without re-reading the file), the second update would use stale
line numbers and corrupt the file.

More critically: the `end` value for the LAST section is `len(lines)`.  If
the last section is "Sprint Allocation" and the replacement content has fewer
lines, `lines[end:]` is empty, which is correct.  But if the section being
replaced is NOT the last section, `lines[end:]` includes all subsequent sections.
The replacement inserts `new_section + [""]` which includes a trailing blank line,
and `lines[end:]` starts at the next `##` heading.  This produces a correct
result ONLY if there's no content between sections that isn't captured by
the range.  Content between two `##` headings that doesn't start with `##`
(like a bare paragraph) will be included in the preceding section's range
and preserved.  This seems correct on analysis, but the single-blank-line
insertion (`[""]`) could accumulate extra blank lines on repeated updates.
**Evidence:** Lines 155-170 (`update_sprint_allocation`), 212-226
(`update_epic_index`), 252-254 (`update_team_voices`).  Each call adds one
`[""]` element as a separator, which accumulates on repeated calls.

### FINDING-25: `update_epic_index()` epic ID extraction is fragile
**Files:** manage_sagas.py
**Severity:** MEDIUM
**Description:** The epic ID is extracted from the filename by splitting on `-`
and taking the first two parts (line 200: `f"{parts[0]}-{parts[1]}"`).  For a
file named `E-0101-parsing.md`, this produces `E-0101`.  But for a file named
`E-0101.md` (no slug), the stem split produces `["E", "0101"]` which works.
However, for `Epic-0101-parsing.md`, it produces `Epic-0101` instead of
`E-0101`.  The function assumes a specific filename convention that is not
validated or documented.
**Evidence:** Lines 197-200.  The `len(parts) < 2` guard (line 198) skips
single-segment names, but does not validate that the first part is a valid
epic ID prefix.

### FINDING-26: `_find_section_ranges()` dedup counter can collide with intentional numbered headings
**Files:** manage_sagas.py
**Severity:** LOW
**Description:** If two `## Team Voices` headings exist, the second becomes
`Team Voices (2)`.  But if the file already has a heading `## Team Voices (2)`,
the dedup logic on lines 126-130 would check for `Team Voices (2)` in the ranges
dict, find it already exists (from the actual heading), and increment to
`Team Voices (3)`.  This is a minor robustness issue -- duplicate `##` headings
in a saga file should not occur in normal use.
**Evidence:** Lines 126-130.

### FINDING-27: `update_team_voices()` does not sanitize `name` for heading injection
**Files:** manage_sagas.py
**Severity:** LOW
**Description:** The sanitization on line 247 strips newlines and `**` from the
persona name, but does not strip `>` characters.  A name containing `>` would
not break the blockquote format (it would just add nested quoting), but a name
containing `## ` on a line boundary (after stripping `\n`) could be problematic.
The newline stripping on line 247 makes this unlikely in practice.
**Evidence:** Line 247: `safe_name = name.replace("\n", " ").replace("\r", "").replace("**", "")`

---

## 8. `scripts/gap_scanner.py`

### FINDING-28: [FIXED] Git diff runs once per story now (prior GAP-1)
**Description:** The git diff call was hoisted outside the entry-point loop.
The comment on line 69 confirms: "Check branch diff once (not per entry point)".

### FINDING-29: [STILL OPEN] `HEAD...{branch}` with deleted branches (prior GAP-2)
**Files:** gap_scanner.py
**Severity:** MEDIUM
**Description:** `git diff --name-only HEAD...{branch}` silently fails for
merged/deleted branches.  The `except Exception: pass` on line 81 swallows the
error, causing the function to return `None` (no entry point touched) even
though the branch *did* touch entry points before being deleted.
**Evidence:** Lines 71-82.

### FINDING-30: `get_entry_points()` returns TOML array but substring match is used
**Files:** gap_scanner.py
**Severity:** MEDIUM
**Description:** `entry_points` is a list of strings from TOML config.  The body
text check on line 66 (`if ep in body`) does a substring match, which can produce
false positives.  An entry point `"main"` would match any body text containing
"mainly", "domain", "maintenance", etc.  Similarly, the changed-files check on
line 79 (`if ep in changed_files`) matches substrings of file paths, so entry
point `"src/main"` would match `"src/main_test.rs"`.
**Evidence:** Lines 65-66 and 78-79.

---

## 9. `scripts/assign_dod_level.py`

### FINDING-31: [FIXED] Falsy sprint check (prior DOD-1/CROSS-2)
**Description:** Now uses `args.sprint if args.sprint is not None else detect_sprint(...)` (line 70).

### FINDING-32: `assign_levels()` re-reads file under lock but does not re-classify
**Files:** assign_dod_level.py
**Severity:** LOW
**Description:** On line 46, the classification is computed from the initial
`read_tf()` outside the lock.  Under the lock (line 51), the file is re-read
to check if `dod_level:` was added by another process.  But the classification
itself (`level = classify_story(...)`) was computed from the pre-lock read.
If another process modified the body text between the initial read and the lock
acquisition, the classification may be based on stale data.
**Evidence:** Lines 45-54.  `classify_story()` is called on line 46 (outside lock),
but `write_tf()` on line 54 uses the `level` from that pre-lock classification.

### FINDING-33: [STILL OPEN] `classify_story()` keyword `user` matches too broadly (prior DOD-4)
**Files:** assign_dod_level.py
**Severity:** LOW
**Description:** The word `user` in `_APP_KEYWORDS` regex matches any story
mentioning "user" in any context, causing over-classification as `app`.
**Evidence:** Line 23.

---

## 10. `scripts/history_to_checklist.py`

### FINDING-34: [FIXED] Truncation suffix always appended (prior HIST-1)
**Description:** Now uses conditional `suffix = "..." if len(cleaned) > 80 else ""` (line 42).

### FINDING-35: [STILL OPEN] No deduplication of checklist items across sprints (prior HIST-2)
**Files:** history_to_checklist.py
**Severity:** LOW
**Description:** Same bug pattern mentioned multiple times across sprint histories
produces near-duplicate checklist items.
**Evidence:** Lines 31-46.

### FINDING-36: [STILL OPEN] `load_config()` failure silently falls back to hardcoded path (prior HIST-3)
**Files:** history_to_checklist.py
**Severity:** LOW
**Description:** No warning emitted when config load fails and fallback is used.
**Evidence:** Lines 91-96.

---

## 11. `scripts/commit.py`

### FINDING-37: `check_atomicity()` does not handle detached HEAD state
**Files:** commit.py
**Severity:** LOW
**Description:** `git diff --cached --name-only` works in detached HEAD state,
so `check_atomicity()` itself is fine.  However, `run_commit()` on line 98 runs
`git commit -m message` which will fail in detached HEAD state with an error
about not being on a branch.  The error message from git is passed through
(line 100), but the script does not provide a more helpful message about the
detached HEAD condition.
**Evidence:** Lines 93-101.

### FINDING-38: Scope validation allows dots but not slashes in scope names
**Files:** commit.py
**Severity:** LOW
**Description:** The CC_RE pattern on lines 29-34 allows `[a-zA-Z0-9_.-]+` for
scope names.  This means `feat(some.module): desc` is valid but
`feat(some/module): desc` is rejected.  Some projects use path-like scopes
(e.g., `fix(scripts/kanban): ...`), which would be rejected by this pattern.
The scope pattern should either document this restriction or support `/`.
**Evidence:** Line 31: `r"(?:\((?P<scope>[a-zA-Z0-9_.-]+)\))?"`.

### FINDING-39: `run_commit()` passes message as `-m` which may hit shell argument length limits
**Files:** commit.py
**Severity:** LOW
**Description:** `subprocess.run(["git", "commit", "-m", message])` passes the
commit message as a command-line argument.  For very long messages (>128KB on
some systems), this will hit `ARG_MAX` limits.  In practice commit messages
are short, but the `--body` flag allows arbitrary-length body text that is also
passed as a `-m` argument (line 97).
**Evidence:** Lines 95-98.

---

## 12. `scripts/test_categories.py`

### FINDING-40: [STILL OPEN] `count_test_functions()` counts `#[test]` attributes, not fn definitions (prior CAT-1)
**Files:** test_categories.py
**Severity:** MEDIUM
**Description:** A `#[test]` attribute followed by a blank line (no `fn`) is
counted as a test function.  Conversely, a `#[test]` on the same line as `fn`
would be double-counted (once for the attribute, once if `fn Test` matched).
**Evidence:** Lines 88-89.

### FINDING-41: `find_test_files()` does not skip `sprint-config` directory
**Files:** test_categories.py
**Severity:** LOW
**Description:** The directory exclusion list on lines 113-117 skips `node_modules`,
`target`, `build`, etc., but does NOT skip `sprint-config`.  If sprint-config
contains any test-like files (e.g., a symlinked `test_plan/` directory), they
could be picked up.  Compare with `test_coverage.py` line 90 which does skip
`sprint-config`.
**Evidence:** Lines 113-117.

---

## Cross-Cutting Issues

### FINDING-42: Inconsistent `load_config()` calling conventions across scripts
**Files:** All 11 scripts
**Severity:** MEDIUM
**Description:** Scripts use four distinct patterns for config loading:

| Pattern | Scripts |
|---------|---------|
| `load_config()` (no arg, default dir) | assign_dod_level, sprint_analytics, traceability, test_coverage, commit (doesn't call it) |
| `load_config(config_dir)` via `--config` flag | gap_scanner, smoke_test, test_categories |
| `load_config()` with fallback on failure | history_to_checklist |
| Imports but never calls `load_config` | risk_register, commit |

This means scripts behave differently when invoked from non-root working
directories or with non-default config paths.

### FINDING-43: No script validates that `get_sprints_dir()` result actually exists before use
**Files:** sprint_analytics.py, gap_scanner.py, assign_dod_level.py
**Severity:** LOW
**Description:** `get_sprints_dir()` returns `Path(config.get("paths", {}).get("sprints_dir", "sprints"))`,
which could be a non-existent directory.  Most callers then do
`Path(sprints_dir) / f"sprint-{sprint}" / "stories"` and check `is_dir()` on
the stories subdirectory, which handles the missing case.  But `sprint_analytics.py`
line 266 checks `sprints_dir.is_dir()` before writing, while line 248 constructs
a `kickoff` path without checking if the sprint dir exists first (the `kickoff.exists()`
check on line 249 handles it gracefully).  Inconsistent but not a bug.

### FINDING-44: Multiple scripts write to files without atomic write strategy
**Files:** risk_register.py, smoke_test.py, sprint_analytics.py, manage_epics.py, manage_sagas.py
**Severity:** MEDIUM
**Description:** These scripts use `Path.write_text()` or `open(path, "a")` for
file mutations without the temp-then-rename atomic write pattern used by
`kanban.py`'s `atomic_write_tf()`.  A crash or power failure during write could
leave these files truncated or corrupted:
- risk_register.py: lines 95, 119 (`write_text`)
- manage_epics.py: lines 230, 265, 337, 361 (`write_text`)
- manage_sagas.py: lines 170, 226, 254 (`write_text`)
- sprint_analytics.py: line 268 (`write_text`), line 280 (`open(..., "a")`)

The kanban system already has the `atomic_write_tf` pattern.  These scripts could
use a similar approach or a shared `atomic_write_text()` helper.

### FINDING-45: `manage_epics.py` and `manage_sagas.py` have no file locking
**Files:** manage_epics.py, manage_sagas.py
**Severity:** MEDIUM
**Description:** Both scripts perform read-modify-write cycles on markdown files
without any file locking.  If two processes concurrently add stories to the same
epic file, one update will be lost.  The kanban system has `lock_story()` and
`lock_sprint()` for exactly this pattern.  These scripts have no equivalent,
despite performing analogous state mutations.
**Evidence:** `add_story()` (manage_epics.py:210-230), `remove_story()` (lines 234-265),
`reorder_stories()` (lines 269-337), `update_sprint_allocation()` (manage_sagas.py:141-170),
`update_epic_index()` (lines 174-226), `update_team_voices()` (lines 230-254).

---

## Summary by Severity

| Severity | Count | IDs |
|----------|-------|-----|
| HIGH | 1 | FINDING-24 |
| MEDIUM | 12 | FINDING-1, FINDING-2, FINDING-5, FINDING-9, FINDING-13, FINDING-16, FINDING-19, FINDING-25, FINDING-29, FINDING-30, FINDING-42, FINDING-44, FINDING-45 |
| LOW | 18 | FINDING-3, FINDING-4, FINDING-6, FINDING-8, FINDING-10, FINDING-11, FINDING-12, FINDING-14, FINDING-15, FINDING-17, FINDING-18, FINDING-22, FINDING-23, FINDING-26, FINDING-27, FINDING-32, FINDING-33, FINDING-35, FINDING-36, FINDING-37, FINDING-38, FINDING-39, FINDING-40, FINDING-41, FINDING-43 |

## Fixed Since Prior Audit

| Prior ID | Status | Notes |
|----------|--------|-------|
| SMOKE-2 | FIXED | Now uses `safe_int()` |
| GAP-1 | FIXED | Git diff hoisted outside loop |
| RISK-1 | FIXED | `resolve_risk()` rewritten with line-based parsing |
| RISK-5 (title pipe) | FIXED | `add_risk()` now escapes `\|` in title |
| DOD-1 / CROSS-2 | FIXED | Uses `is not None` check |
| HIST-1 | FIXED | Conditional `...` suffix |

## Priority Fixes

1. **FINDING-24** (HIGH) — `manage_sagas.py` section replacement can accumulate blank lines on repeated updates.  Add a "strip trailing blank lines from section before replacement" pattern.
2. **FINDING-16** (MEDIUM) — Rust test detection pattern in `test_coverage.py` is effectively broken for standard Rust formatting.  Add `re.DOTALL` or use a multiline-aware approach.
3. **FINDING-44/45** (MEDIUM) — Add atomic write and file locking to `manage_epics.py` and `manage_sagas.py` state mutation functions.
4. **FINDING-19** (MEDIUM) — `remove_story()` should return a boolean or raise on missing ID; CLI should not print success.
5. **FINDING-13** (MEDIUM) — Fix `parse_stories()` metadata boundary detection for short tables.
6. **FINDING-42** (MEDIUM) — Standardize config loading pattern across all scripts.
