# Audit Pass 15 — Untouched Code Review

Audited 8 scripts not modified in pass 14. Each file read in full and examined
for logic bugs, edge cases, error handling, regex issues, and security concerns.

---

### Finding: reorder_stories duplicates separators on every reorder

**File:** scripts/manage_epics.py:325-336
**Severity:** MEDIUM
**Problem:** `reorder_stories` inserts `---` separators between reassembled
story sections, but the raw section lines already include trailing blank lines
and `---` separators from the original file. On each reorder, extra separator
lines accumulate. After N reorders, each section boundary grows by 3 lines
(blank, `---`, blank) per invocation.

**Evidence:** `_parse_stories` sets each section's lines to everything from
its `### US-XXXX` heading up to (but not including) the next heading. This
slice includes any trailing blank lines and `---` separators:

```python
# _parse_stories line 102-104:
raw_sections[-1]["end_line"] = i
raw_sections[-1]["lines"] = lines[raw_sections[-1]["start_line"]:i]
```

Then `reorder_stories` line 331-335 injects new separators:

```python
if stories_emitted > 0:
    new_lines.append("")
    new_lines.append("---")
    new_lines.append("")
new_lines.extend(section_map[sid])  # section already has trailing separator
```

**Acceptance Criteria:** Raw section lines must be stripped of trailing blank
lines and `---` separators before reassembly, OR the separator injection in
`reorder_stories` must check whether the previous section already ends with
a separator. Running `reorder_stories` twice with the same order must produce
identical output (idempotency).

---

### Finding: _parse_header_table accepts colon-aligned separator rows as data

**File:** scripts/manage_epics.py:70-86, scripts/manage_sagas.py:65-77
**Severity:** LOW
**Problem:** Both `_parse_header_table` functions filter separator rows by
checking `field.strip("-") != ""`. This correctly handles `|---|---|` but
fails on alignment-style separators like `|:---|:---|` where
`":---".strip("-")` yields `":"`, which is not empty. Such a row would be
stored as metadata with field `":---"` and value `":---"`.

The story metadata parser in `_parse_stories` (line 126) has a dedicated
separator regex `r'^\|[-:\s|]+\|$'` but the header-level parsers lack it.

**Evidence:**
```python
# manage_epics.py line 81:
if field not in ("Field", "---", "") and field.strip("-") != "":
    metadata[field] = value
# ":---".strip("-") == ":" which is truthy => incorrectly stored
```

**Acceptance Criteria:** Header table parsers must skip separator rows
containing only `-`, `:`, spaces, and `|` characters. Either add the
separator regex from line 126 or extend the strip to `field.strip("-:")`.

---

### Finding: TOML escaper misses carriage return character

**File:** scripts/sprint_init.py:579-586
**Severity:** LOW
**Problem:** The `_esc` method escapes `\`, `"`, `\n`, and `\t` for TOML
basic strings but does not escape `\r` (carriage return). Per the TOML
specification, carriage returns in basic strings must be escaped as `\r`.
A project name or repo path containing `\r` would produce invalid TOML
that `parse_simple_toml` would reject on re-read.

**Evidence:**
```python
def _esc(val: str) -> str:
    return (str(val)
            .replace('\\', '\\\\')
            .replace('"', '\\"')
            .replace('\n', '\\n')
            .replace('\t', '\\t'))
    # Missing: .replace('\r', '\\r')
```

**Acceptance Criteria:** `_esc` must also replace `\r` with `\\r`. This
matches the TOML v1.0 spec for basic string escapes.

---

### Finding: _format_story_section allows newlines in heading, corrupting file structure

**File:** scripts/manage_epics.py:167-174
**Severity:** MEDIUM
**Problem:** When `add_story` is called with story data from `json.loads`
(e.g., from CLI argv), the `title` and `id` fields are interpolated directly
into a `### {sid}: {title}` heading with no sanitization. If either contains
a newline, the heading would be split across lines, creating a malformed
section that `_parse_stories` cannot parse back. Similarly, the `description`
field in tasks (line 217) and `priority` field (line 179) are unvalidated.

**Evidence:**
```python
sid = story_data.get("id", "US-XXXX")
title = story_data.get("title", "Untitled")
lines = [
    f"### {sid}: {title}",  # newline in title breaks the heading
```

Calling `manage_epics.py add epic.md '{"id":"US-999","title":"foo\nbar"}'`
would produce a heading split across two lines.

**Acceptance Criteria:** `_format_story_section` must strip or reject
newlines (and other control characters) in `id`, `title`, and `description`
fields before interpolation. At minimum, replace `\n` and `\r` with spaces.

---

### Finding: _write_manifest parses human-readable log strings, fragile to paths containing " (" or " -> "

**File:** scripts/sprint_init.py:802-838
**Severity:** LOW
**Problem:** The manifest is built by parsing the human-readable strings in
`self.created` (e.g., `"skeleton   team/giles.md (from giles.md.tmpl)"`).
The parsing splits on `" ("` and `" -> "` to extract paths. If a file path
itself contains the substring ` (` or ` -> `, the path is truncated.

**Evidence:**
```python
elif entry.startswith("skeleton"):
    rel = entry.split(None, 1)[1].split(" (")[0]   # breaks if path has " ("
    files.append(rel)
elif entry.startswith("symlinked"):
    rel = entry.split(None, 1)[1].split(" -> ")[0]  # breaks if path has " -> "
    symlinks.append(rel)
```

While unlikely in practice (sprint-config paths are generated), this is a
design fragility. The manifest data should be collected from the actual
parameters passed to `_write`, `_symlink`, and `_copy_skeleton` rather
than reverse-engineering them from display strings.

**Acceptance Criteria:** Manifest data should be accumulated from the actual
path arguments at creation time, not parsed from log messages. For example,
have `_write` append to a `self._manifest_files` list directly.

---

### Finding: _find_section_ranges strips content-level # from headings

**File:** scripts/manage_sagas.py:141
**Severity:** LOW
**Problem:** `heading = line.lstrip("#").strip()` strips ALL leading `#`
characters, not just the markdown heading prefix. A heading like
`## #Channel-Ops` would be stored as `"Channel-Ops"` instead of
`"#Channel-Ops"`, causing lookup mismatches in `update_sprint_allocation`,
`update_epic_index`, and `update_team_voices` which use hardcoded section
names.

**Evidence:**
```python
heading = line.lstrip("#").strip()
# "## #Hashtag" -> lstrip("#") -> " #Hashtag" -> ... wait, actually:
# "## #Hashtag".lstrip("#") == " #Hashtag"
# " #Hashtag".strip() == "#Hashtag"
# Hmm, this actually preserves the # after the space.
```

Actually on closer analysis: `"## #Hashtag".lstrip("#")` yields `" #Hashtag"`
because `lstrip` stops at the first non-`#` character (the space). Then
`.strip()` yields `"#Hashtag"`. So this specific case is fine.

The real issue is a heading like `### Notes` (triple-hash). `line.startswith("## ")`
would be True (it starts with `## `), but `line.startswith("### ")` would also be True
and is explicitly excluded at line 138. So this is actually correctly handled.

After deeper analysis, the `lstrip("#")` approach is safe because `## ` headings
always have a space after the hashes, so `lstrip` stops at the space. **Withdrawn.**

---

### Finding: Rust test pattern in test_coverage.py misses #[rstest] and #[test_case] attributes

**File:** scripts/test_coverage.py:23
**Severity:** LOW
**Problem:** The Rust test detection pattern only matches `#[test]`,
`#[tokio::test]`, and `#[async_std::test]`. It does not match parameterized
test macros commonly used in the Rust ecosystem: `#[rstest]`,
`#[test_case(...)]`, and `#[googletest::test]`. Projects using these
frameworks would report zero test functions found.

**Evidence:**
```python
"rust": re.compile(
    r'#\[(?:test|tokio::test|async_std::test)\]'
    r'\s*(?:#\[.*\]\s*)*(?:async\s+)?fn\s+(\w+)'
),
```

**Acceptance Criteria:** Either expand the pattern to include common
parameterized test attributes, or document the limitation in the function
docstring. At minimum, `rstest` should be included as it's a widely-used
crate.

---

### Finding: sprint_analytics silently continues on non-digit sprint argument after -h check

**File:** scripts/sprint_analytics.py:199-219
**Severity:** LOW
**Problem:** The CLI parser checks for `-h`/`--help` only at `argv[1]`.
If `argv[1]` is another flag like `--verbose` or a typo like `sprint-3`,
the code falls through to the `isdigit()` check, fails, prints a usage
message, and exits. This is correct behavior but the error message
(`Usage: python sprint_analytics.py [sprint-number]`) doesn't explain
what went wrong. More importantly, negative sprint numbers (e.g., `-1`)
would be treated as a flag because `-1` starts with `-`... wait, `-1`
is not `-h`/`--help`, so `sys.argv[1]` would be `-1`, `"-1".isdigit()`
is `False` (negative sign), so it would print usage and exit with code 2.

**Evidence:**
```python
if len(sys.argv) >= 2:
    if sys.argv[1].isdigit():
        sprint_num = int(sys.argv[1])
    else:
        print("Usage: ...", file=sys.stderr)
        sys.exit(2)
```

This is borderline -- negative sprint numbers are invalid anyway. But a
sprint number like `03` would parse correctly (`"03".isdigit()` is True).
**Withdrawn as not a real bug.**

---

### Finding: test_coverage.py Rust file pattern scans all .rs files in src/, not just test modules

**File:** scripts/test_coverage.py:32
**Severity:** MEDIUM
**Problem:** The Rust test file pattern includes `**/src/**/*.rs`, which
scans ALL source files under `src/`. In Rust projects, test functions are
often defined in `#[cfg(test)] mod tests { ... }` blocks within regular
source files. While the test function regex correctly identifies `#[test] fn`
patterns, scanning ALL `.rs` files is inefficient for large codebases and
could hit performance issues.

More significantly, the Python test file pattern `**/test_*.py` and
`**/*_test.py` are specific to test files, but the Rust `**/src/**/*.rs`
pattern is not. This inconsistency means Rust projects may find tests that
other language patterns would miss (inline test modules), which is actually
desirable behavior. **Withdrawn -- this is intentional for Rust's inline
test convention.**

---

### Finding: traceability parse_stories doesn't handle separator rows in metadata table

**File:** scripts/traceability.py:54-64
**Severity:** LOW
**Problem:** Unlike `manage_epics._parse_stories` (which has explicit
separator row handling at line 126), `traceability.parse_stories` passes
separator rows through `TABLE_ROW` match. A separator row `|---|---|`
matches with field=`---` and value=`---`. Since `field == "Test Cases"`
is False for `---`, it's harmlessly ignored. However, the code also
doesn't track `in_table` state, meaning it doesn't stop scanning at
the end of the metadata table. It continues scanning the entire story
section for table rows.

If a story section contains a secondary table (e.g., in acceptance
criteria or task details) with a "Test Cases" column, those values would
be incorrectly captured.

**Evidence:**
```python
while j < len(lines):
    row = TABLE_ROW.match(lines[j])
    if row:
        field = row.group(1).strip()
        value = row.group(2).strip()
        if field == "Test Cases" and value not in ("—", "-", ""):
            test_cases = [...]
    elif lines[j].strip() == "" and j > i + 2:
        break  # only stops at blank lines 2+ lines after heading
```

A story with a body table like `| Test Cases | TC-999 |` after the
metadata section would incorrectly override the real test_cases list.

**Acceptance Criteria:** The metadata scanner should track `in_table`
state (like `_parse_stories` does) and stop scanning for metadata after
the first non-table line following the table, to avoid picking up data
from body-level tables.

---

### Finding: manage_sagas update_epic_index silently skips files where stem has fewer than 2 hyphen-parts

**File:** scripts/manage_sagas.py:213-217
**Severity:** LOW
**Problem:** The epic file scanner constructs `epic_id` from
`parts[0]-parts[1]` where parts come from `md_file.stem.split("-")`.
Files named without a hyphen (e.g., `overview.md`) are silently skipped
because `len(parts) < 2`. But files with the pattern `E-0101-parsing.md`
split into `["E", "0101", "parsing"]`, giving `epic_id = "E-0101"`.

The issue: if a filename is `E0101-parsing.md` (no hyphen after E), parts
are `["E0101", "parsing"]`, giving `epic_id = "E0101-parsing"` which is
wrong. This is a fragile filename convention dependency with no validation
or error message.

**Evidence:**
```python
parts = md_file.stem.split("-")
if len(parts) < 2:
    continue
epic_id = f"{parts[0]}-{parts[1]}"
```

**Acceptance Criteria:** Either validate the epic ID format against a
pattern like `^E-\d+$`, or document the required filename convention.
At minimum, warn when a `.md` file is skipped so the user knows data
may be missing.

---

### Finding: sprint_init _parse_workflow_runs has dead-code first if-block for folded YAML

**File:** scripts/sprint_init.py:217-220
**Severity:** LOW
**Problem:** The first `if cmd in (">", ">-")` block at line 217 executes
`pass` and falls through. The second `if cmd in ("|", "", ">", ">-")` at
line 221 is a superset that also handles `>` and `>-`. The first block is
pure dead code that adds no behavior.

**Evidence:**
```python
if cmd in (">", ">-"):
    # Folded YAML style — not fully supported, but collect
    # the block the same way as literal style (P13-021).
    pass  # fall through to multiline collection below
if cmd in ("|", "", ">", ">-"):
    # Multiline run block: collect subsequent indented lines
```

**Acceptance Criteria:** Remove the dead `if cmd in (">", ">-"): pass`
block. The comment about P13-021 can be moved to the second block.

---

## Files Audited and Confirmed Clean

**scripts/sprint_teardown.py** — 476 lines. Thoroughly reviewed: file
classification, symlink removal, directory cleanup, prompt handling.
`followlinks=False` correctly prevents symlink traversal. `list(dirs)`
copy-for-iteration is correct. EOFError handling for non-interactive mode.
No bugs found.

**scripts/team_voices.py** — 109 lines. Clean. VOICE_PATTERN correctly
handles quoted and unquoted text. Continuation line consumption is correct.
File reading uses UTF-8 encoding. No injection or traversal risks.

**scripts/sprint_analytics.py** — 283 lines. Clean apart from the minor
kickoff file read lacking `errors="replace"` (line 246), which would
raise UnicodeDecodeError on non-UTF-8 content. All other file reads in
the codebase use `errors="replace"`. This is cosmetic since kickoff files
are always generated by the tool itself.

---

## Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 0 |
| HIGH     | 0 |
| MEDIUM   | 2 |
| LOW      | 7 |

The two MEDIUM findings (reorder separator duplication, heading injection
via unsanitized story data) are the most actionable. The LOW findings are
defense-in-depth improvements: separator row filtering, TOML escaping,
manifest parsing fragility, and documentation of assumptions.
