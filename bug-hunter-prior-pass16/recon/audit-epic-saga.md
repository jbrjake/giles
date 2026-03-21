# Audit: manage_epics.py & manage_sagas.py

Adversarial code audit of CRUD operations on epic and saga markdown files.

Files audited:
- `scripts/manage_epics.py` (424 lines)
- `scripts/manage_sagas.py` (309 lines)
- `tests/test_pipeline_scripts.py` (relevant test classes)
- `tests/test_verify_fixes.py` (main() integration tests)
- `tests/fixtures/hexwise/docs/agile/epics/E-0101-parsing.md`
- `tests/fixtures/hexwise/docs/agile/sagas/S01-core.md`

---

## Findings

### 1. DATA LOSS — `remove_story` walk-back can eat the separator before the PREVIOUS story

**File:** `manage_epics.py:266-274`
**Severity:** Medium
**Status:** Bug

When removing a story, the code walks backward up to 3 lines to remove `---` separators and blank lines before the story. The walk-back stops and then adds 1 back (`sep_start += 1`) to "keep at least one blank line." But the kept line might be `---`, not a blank line — depending on the file structure. If the file has `---\n\n### US-...`, the walk-back hits `---` at position `sep_start`, walks back one more (line before `---`), then does `sep_start += 1` which leaves the `---` as the "kept" line. This is not data loss per se but leaves orphan `---` separators after removal. Repeated remove operations accumulate orphan separators.

More critically: if two stories are separated by exactly `\n---\n\n` (4 lines: blank, `---`, blank, heading), the walk-back cap of 3 lines means it only removes 3 of the 4 separator lines, leaving an artifact.

**Untested:** No test verifies the file content after removal is clean of orphan separators — `test_remove_story` only checks that the story ID is gone and others remain.

---

### 2. DATA LOSS — `reorder_stories` silently drops content between the header table and first story

**File:** `manage_epics.py:297-303`
**Severity:** Medium
**Status:** Bug

The code walks backward from the first story's `start_line` to find `stories_start`, eating blank lines and `---` separators. Then it adds 1 back. But any prose paragraphs between the header metadata table and the first `---` separator (like the description paragraph in `E-0101-parsing.md`, lines 3-6) are preserved because they don't match the walk-back condition. However, the `stories_start` calculation can land mid-separator, causing an off-by-one that either duplicates or drops a blank line on each reorder call.

Concrete scenario: In `E-0101-parsing.md`, there is:
```
| Sprints | 1–2 |
                    ← line 15 (blank)
---                 ← line 16
                    ← line 17 (blank)
### US-0101...      ← line 18
```
`first_section["start_line"]` = 17 (0-indexed: the `### US-0101` line is index 17). Walk-back: line 16 is blank → walk; line 15 is `---` → walk; line 14 is blank → walk. Now `stories_start` = 14. Then +1 = 15. So header is `lines[:15]`, which is the metadata table through the blank line on line 14 (0-indexed). The `---` separator on line 15 and blank line 16 are dropped. They get re-emitted by the reorder loop for subsequent stories but NOT before the first story. So the first reorder removes the `---` before the first story and never puts it back.

**Impact:** Idempotency violation. The file changes structure on every reorder even with the same order.

---

### 3. BUG — `_parse_header_table` in `manage_epics.py` stops at `###` but not `##`

**File:** `manage_epics.py:75`
**Severity:** Low
**Status:** Latent defect

The epic header table parser breaks on `###` headings (story headings), but does NOT break on `##` headings. If an epic file ever has a `## Description` or `## Notes` section between the header table and the first story, the parser would scan past it and potentially pick up table rows from that section as header metadata.

In contrast, `manage_sagas.py:69` correctly breaks on `##` headings.

---

### 4. BUG — `_parse_epic_from_lines` title extraction fails on files with no heading prefix

**File:** `manage_epics.py:39`
**Severity:** Low
**Status:** Latent defect

The title is extracted from `lines[0]` by stripping `#+\s*`. If the first line is not a heading (e.g., YAML frontmatter `---`, or a blank line), the "title" becomes the raw first line. The same issue exists in `manage_sagas.py:54`. Both assume line 0 is a markdown heading.

**Untested:** The empty-file test covers `lines=[]`, but no test covers a file whose first line is not a heading.

---

### 5. BUG — `parse_saga` crashes on empty file (IndexError)

**File:** `manage_sagas.py:54`
**Severity:** Medium
**Status:** Bug

```python
"title": re.sub(r'^#+\s*', '', lines[0]).strip() if lines else "",
```

This is guarded by `if lines`, so empty file won't crash. BUT: `Path(path).read_text("").splitlines()` on an empty file returns `[]`, and the `_parse_header_table`, `_parse_epic_index`, etc. all iterate safely over empty lists. So this is actually safe. Correction: NOT a bug.

However, the analogous code in `manage_epics.py:37-39` is also safe. Marking as reviewed-and-OK.

---

### 6. NO-OP VARIABLE — `in_table` is set but never read in `_parse_header_table` (epics)

**File:** `manage_epics.py:73, 83-84`
**Severity:** Low (code smell)
**Status:** Dead code interaction

The variable `in_table` is set to `True` when a table row is found, and the only place it's read is `elif in_table and line.strip() == ""`. This works correctly for its purpose — it stops scanning after the first blank line that follows the table. But it means a blank line BEFORE any table row would not trigger the break, which is correct behavior. Not a bug, but worth noting this logic differs subtly from the saga version which has no such guard (it scans ALL lines until `##`).

---

### 7. DATA LOSS — `renumber_stories` corrupts tables with multiple references to old_id on one line

**File:** `manage_epics.py:371`
**Severity:** Medium
**Status:** Bug

```python
new_lines.append(re.sub(rf'\b{re.escape(old_id)}\b', lambda m: replacement, line))
```

If a table row contains the same old_id multiple times (e.g., `| Blocks | US-0102, US-0102 |`), each occurrence is independently replaced with the full comma-separated `replacement`. So `US-0102, US-0102` becomes `US-0102a, US-0102b, US-0102a, US-0102b` — a Cartesian expansion that doubles the references.

The test fixture in `test_renumber_preserves_headings` has `| Blocks | US-0102, US-0104 |` where `US-0102` only appears once, so this is not caught.

---

### 8. UNTESTED — CLI `main()` subcommands for add/remove/reorder/renumber

**File:** `manage_epics.py:386-419`
**Severity:** Low (coverage gap)
**Status:** Untested

The test suite only tests `main()` with no arguments (exits 1). The `add`, `remove`, `reorder`, and `renumber` subcommand branches in `main()` are not tested via the CLI path. These are ~33 lines of uncovered code. Similarly, `manage_sagas.py:281-304` has `update-allocation`, `update-index`, `update-voices` subcommands with only the no-args case tested.

---

### 9. UNTESTED — `manage_sagas.update_team_voices` with no "Team Voices" section

**File:** `manage_sagas.py:255-256`
**Severity:** Low
**Status:** Untested silent no-op

If the saga file has no `## Team Voices` section, `update_team_voices` silently returns without modifying the file. Same pattern for `update_sprint_allocation` (line 169) and `update_epic_index` (line 206). None of these "section missing" early-return paths are tested.

---

### 10. BUG — `update_team_voices` emits double blank line before first voice

**File:** `manage_sagas.py:260-264`
**Severity:** Low
**Status:** Cosmetic bug

```python
new_section = ["## Team Voices", ""]
for name, quote in voices.items():
    if new_section[-1] != "":
        new_section.append("")
    new_section.append(f'> **{name}:** "{quote}"')
```

After `["## Team Voices", ""]`, `new_section[-1]` is `""`, so the `if` check is False for the first voice, and no extra blank line is added. Then for the second voice, `new_section[-1]` is the blockquote line (not empty), so a blank line IS added. This is actually correct behavior. Reviewed-and-OK.

---

### 11. CONCURRENCY — No file locking; concurrent writes cause data loss

**File:** Both files, all write operations
**Severity:** Medium
**Status:** Design limitation

Every write function follows the pattern: read file, parse, modify in memory, write entire file. Two concurrent operations on the same file (e.g., two `add_story` calls) will cause a lost-update race condition. The second writer overwrites the first writer's changes entirely.

This is acknowledged as a design limitation (single-user CLI tool), but worth noting because `sprint-monitor` runs on a loop and could theoretically trigger concurrent saga updates.

---

### 12. BUG — `_parse_stories` metadata scan in epics skips the first non-table line without consuming it

**File:** `manage_epics.py:116-135`
**Severity:** Low
**Status:** Latent defect

The inner `while j < len(lines)` loop parses the metadata table within a story section. When it encounters a non-table, non-separator, non-blank line after the table has started (`elif in_meta_table:` on line 132), it breaks. But the outer `while i < len(lines)` loop increments `i` from the HEADING line's position, not from `j`. So the story body content is never skipped — it just isn't parsed as metadata. This is correct behavior. However, if the body contains a markdown table (like an example table in acceptance criteria), those rows are NOT read as metadata because `in_meta_table` causes an early break after the first blank line. This is the correct defensive behavior.

Reviewed-and-OK.

---

### 13. BUG — `reorder_stories` loses content that comes after the last story

**File:** `manage_epics.py:347-352`
**Severity:** Medium
**Status:** Bug

After reassembling stories, the function strips trailing blank lines and adds a single empty line. But any content that appeared AFTER the last story section in the original file (e.g., a `## Notes` section, a footer, an appendix) is lost. The last `raw_section["end_line"]` is set to `len(lines)` (manage_epics.py:160), meaning the last section captures everything to EOF. When `reorder_stories` reassembles from `section_map`, it strips trailing blanks from each section, but the "after all stories" content was included in the last section's `lines` and survives. Wait — let me re-examine.

Actually, `raw_sections[-1]["end_line"] = len(lines)` and `raw_sections[-1]["lines"] = lines[raw_sections[-1]["start_line"]:]`. So the last story section's `lines` includes everything from its heading to EOF. Any content after the stories (like a `## Notes` section) gets bundled into the last story's `lines`. When reordered, that trailing content moves with the last story but appears in whatever position that story lands. If that story is not last in the new order, the trailing content appears mid-file.

**Impact:** If a `## Notes` or any non-story section appears at the bottom of an epic file, reordering stories will splice that content into the middle of the file, attached to whichever story was originally last.

---

### 14. BUG — `_find_section_ranges` in sagas treats content before first `##` as unnamed

**File:** `manage_sagas.py:133-149`
**Severity:** Low
**Status:** Design gap

Everything before the first `## ` heading is not tracked in `section_ranges`. The `current_section` starts as `""` and only gets set when a `## ` heading is found. The range `("", 0)` is never stored because the `if current_section:` check on line 139 is False for `""`. This means `update_sprint_allocation` and friends can't operate on the preamble, which is fine. But if someone calls `_find_section_ranges` expecting the preamble to be tracked, they won't find it.

---

### 15. BUG — `update_epic_index` filename parsing assumes E-NNNN-name.md format

**File:** `manage_sagas.py:214-217`
**Severity:** Low
**Status:** Fragile parsing

```python
parts = md_file.stem.split("-")
if len(parts) < 2:
    continue
epic_id = f"{parts[0]}-{parts[1]}"
```

This constructs epic IDs from the filename. If the filename is `E-0101-parsing.md`, parts = `["E", "0101", "parsing"]`, so `epic_id` = `"E-0101"`. But if the epic name contains hyphens (e.g., `E-0101-named-colors.md`), parts = `["E", "0101", "named", "colors"]`, and `epic_id` = `"E-0101"` — still correct. However, if the filename deviates from the convention (e.g., `my-epic-0101.md`), you get `epic_id = "my-epic"` — nonsensical but silently accepted. The `len(parts) < 2` guard only catches single-word filenames.

---

### 16. UNTESTED — `reorder_stories` validation error path (missing IDs)

**File:** `manage_epics.py:314-320`
**Severity:** Low
**Status:** Untested

The `ValueError` raised when `story_ids` doesn't include all existing IDs is not tested. The test `test_reorder_stories` provides all 4 story IDs. No test verifies the data-loss prevention guard.

---

### 17. UNTESTED — `reorder_stories` warning path (extra IDs not in file)

**File:** `manage_epics.py:323-326`
**Severity:** Low
**Status:** Untested

The `stderr` warning for IDs in the provided list that don't exist in the file is not tested.

---

### 18. BUG — `add_story` double-newline check has off-by-one on files ending with `\n\n\n`

**File:** `manage_epics.py:241-244`
**Severity:** Low
**Status:** Cosmetic

```python
if not content.endswith("\n"):
    content += "\n"
if not content.endswith("\n\n"):
    content += "\n"
```

If the file already ends with `\n\n`, both checks pass. If it ends with `\n`, the first check passes, the second adds `\n`. If it ends with no newline, the first adds `\n`, then the second adds `\n`. This is correct. But if the file ends with `\n\n\n` (triple newline), both checks pass and no trimming occurs. Repeated `add_story` calls after manual edits can accumulate whitespace. This is cosmetic only.

---

### 19. BUG — `_parse_epic_from_lines` metadata extraction misses multi-column tables

**File:** `manage_epics.py:23`
**Severity:** Low
**Status:** Latent

`TABLE_ROW = re.compile(r'^\|\s*(.+?)\s*\|\s*(.+?)\s*\|')` only captures the first two columns. If the header table has more than 2 columns (e.g., `| Field | Value | Notes |`), the regex captures `Field` and `Value` but ignores `Notes`. The third column is silently dropped. This matches the expected format but would silently lose data if the format evolved.

---

### 20. BUG — `_parse_sprint_allocation` uses `int()` for Epic Index but `str` for Sprint Allocation

**File:** `manage_sagas.py:98` vs `manage_sagas.py:117-121`
**Severity:** Low
**Status:** Inconsistency

In `_parse_epic_index`, the `stories` and `sp` fields are parsed as `int()` (lines 97-98). In `_parse_sprint_allocation`, `stories` and `sp` are kept as strings (lines 119-120). This means downstream code must handle mixed types. The sprint allocation regex (`\d+`) guarantees the `sp` field matches digits, but it's returned as a string. The test at line 455 asserts `result["sprint_allocation"][0]["sp"]` equals `"11"` (string), confirming the inconsistency is baked into the API contract.

---

## Summary

| # | Severity | Category | Finding |
|---|----------|----------|---------|
| 1 | Medium | Data loss | `remove_story` walk-back leaves orphan `---` separators |
| 2 | Medium | Data loss | `reorder_stories` drops `---` before first story, idempotency violation |
| 3 | Low | Parse bug | Epic header parser doesn't stop at `##` headings |
| 4 | Low | Parse bug | Title extraction assumes line 0 is a heading |
| 5 | -- | Reviewed OK | `parse_saga` empty file handling is safe |
| 6 | Low | Dead code | `in_table` variable in epic header parser |
| 7 | Medium | Data loss | `renumber_stories` Cartesian expansion on duplicate refs |
| 8 | Low | Coverage | CLI `main()` subcommands untested (both files) |
| 9 | Low | Coverage | "Section missing" early-return paths untested |
| 10 | -- | Reviewed OK | `update_team_voices` blank line logic is correct |
| 11 | Medium | Concurrency | No file locking; concurrent writes cause lost updates |
| 12 | -- | Reviewed OK | Story metadata scan correctly stops at body content |
| 13 | Medium | Data loss | `reorder_stories` moves post-story content with last story |
| 14 | Low | Design gap | Saga preamble not tracked in section_ranges |
| 15 | Low | Fragile parse | Epic filename parsing assumes convention |
| 16 | Low | Coverage | `reorder_stories` missing-ID ValueError untested |
| 17 | Low | Coverage | `reorder_stories` extra-ID warning untested |
| 18 | Low | Cosmetic | `add_story` doesn't trim excess trailing newlines |
| 19 | Low | Latent | TABLE_ROW regex silently drops columns beyond 2 |
| 20 | Low | Inconsistency | Sprint allocation returns strings, epic index returns ints |

**Actionable items (Medium severity):** 1, 2, 7, 11, 13
**Coverage gaps worth closing:** 8, 9, 16, 17
