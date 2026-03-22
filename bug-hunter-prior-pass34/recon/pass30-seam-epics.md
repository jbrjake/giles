# Pass 30 — Seam Audit: manage_epics.py / populate_issues.py

**Components:**
- `scripts/manage_epics.py` — Epic CRUD (add, remove, reorder, renumber stories)
- `skills/sprint-setup/scripts/populate_issues.py` — Parse epics to create GitHub issues

**Date:** 2026-03-21

---

## Bug 1 (MEDIUM): Acceptance criteria format mismatch — add_story output is invisible to parse_detail_blocks

**manage_epics._format_story_section** (line 194) emits acceptance criteria as:
```
- [ ] `Do the thing`
```

**populate_issues.parse_detail_blocks** (line 254) parses acceptance criteria with:
```python
ac = re.findall(r"- \[ \] `AC-\d+`:\s*(.+)", body)
```

This regex requires the `AC-NN:` prefix inside the backtick (e.g., `` `AC-01`: Do the thing ``). The format produced by `_format_story_section` puts the raw AC text inside backticks with no `AC-NN:` prefix. Result: after `add_story()` writes a story with acceptance criteria, `parse_detail_blocks` will find zero acceptance criteria for that story. The skeleton template (`references/skeletons/epic.md.tmpl` line 39) uses the `AC-NN:` prefix format, so hand-authored epics work. Only `add_story`-generated content breaks.

**Impact:** Stories added via `manage_epics.add_story()` will have their acceptance criteria silently dropped when `populate_issues.enrich_from_epics()` creates GitHub issues. The issue body will be missing the acceptance criteria section entirely.

---

## Bug 2 (LOW): _format_story_section omits Saga, Epic, and Release metadata rows

**manage_epics._format_story_section** (lines 159-187) emits these table fields:
- Story Points, Priority, Personas (conditional), Blocked By, Blocks, Test Cases

It does **not** emit:
- `Saga`, `Epic`, `Release`

**populate_issues.parse_detail_blocks** (lines 257-258, 269) reads `saga`, `epic`, and `priority` from the metadata table. These are used to set labels (saga label), link to epics, and set priority labels on GitHub issues.

After `add_story()`, even if the input `story_data` dict includes `saga`, `epic`, and `release` keys, they are silently discarded — never written to the metadata table. When `parse_detail_blocks` later reads the file, these fields default to empty strings.

**Impact:** Stories created via `add_story()` lose their saga association and epic linkage when parsed by `populate_issues`. The GitHub issue will be missing `saga:SXX` labels and epic references.

---

## Bug 3 (MEDIUM): Story ID regex width mismatch — \d+ vs \d{4}

**manage_epics.STORY_HEADING** (line 22):
```python
re.compile(r'^(###\s+(US-\d+):\s*(.+))')
```

**populate_issues._DETAIL_BLOCK_RE** (line 206):
```python
re.compile(r"^###\s+(US-\d{4}):\s+(.+)$", re.MULTILINE)
```

Differences:
1. `\d+` (manage_epics) vs `\d{4}` (populate_issues) — manage_epics can parse 5+ digit IDs like `US-01021`; populate_issues silently skips them.
2. `\s*` (manage_epics) vs `\s+` (populate_issues) after the colon — manage_epics tolerates `### US-0001:Title` with no space; populate_issues requires at least one space.

The first difference matters if a project uses extended story IDs. manage_epics will happily parse, manipulate, and write back `US-01021` stories, but populate_issues will never see them. The second difference is minor (only matters if someone manually removes the space after the colon, which _format_story_section always includes).

**Impact:** If the project uses story IDs with more or fewer than 4 digits, manage_epics will process them but populate_issues will silently ignore them during issue creation.

---

## Bug 4 (LOW): Separator row pollution in parse_detail_blocks metadata

**populate_issues._META_ROW_RE** (line 207):
```python
re.compile(r"^\|\s*(.+?)\s*\|\s*(.+?)\s*\|$", re.MULTILINE)
```

This matches separator rows like `|-------|-------|`, producing a junk metadata entry `{"-------": "-------"}`. The only filter is `key != "Field"` (line 243), which doesn't catch the separator.

In contrast, **manage_epics._parse_stories** (line 101) uses the shared `TABLE_ROW` pattern and properly filters with:
```python
field not in ("Field", "---", "") and field.strip("-") != ""
```

The `field.strip("-") != ""` check correctly rejects separator rows.

**Impact:** Harmless in practice — no code looks up `-------` as a metadata key. But it's an inconsistency that could cause confusion if metadata is ever dumped for debugging, and could become a real bug if a future field name happens to be all dashes.

---

## Bug 5 (INFO): renumber_stories comma-joined IDs are syntactically valid but semantically fragile

After `renumber_stories(path, "US-0102", ["US-0102a", "US-0102b"])`, a `Blocked By` row becomes:
```
| Blocked By | US-0102a, US-0102b |
```

**populate_issues.parse_detail_blocks** reads this as `blocked_by = "US-0102a, US-0102b"`, which passes through to the GitHub issue body as-is. This is technically fine — the value is preserved as a string.

However, the suffixed IDs (`US-0102a`) don't match either heading regex (`US-\d+` or `US-\d{4}`), so:
- Neither component can parse `### US-0102a: ...` as a story heading
- If someone manually creates headings for the split stories, they'd need to use a non-standard ID format

This is more of a design gap than a bug: `renumber_stories` replaces IDs in table rows and body text but explicitly preserves headings. The docstring says this is intentional ("to preserve the parseable heading format"). But it means the old heading `### US-0102` still exists while its metadata now references `US-0102a, US-0102b` — a state that's internally inconsistent.

**Impact:** Not a parsing failure, but the renumber workflow leaves the file in a state where the heading ID doesn't match the metadata references. Downstream consumers see the old ID from the heading and the new IDs from the metadata.

---

## Bug 6 (INFO): _format_story_section omits user story ("As a...") block

The skeleton template (epic.md.tmpl line 36) includes:
```
**As a** TODO: persona, **I want** TODO: capability **so that** TODO: benefit.
```

**populate_issues.parse_detail_blocks** (line 248) parses this with:
```python
us_match = re.search(r"\*\*As a\*\*\s+(.+?)(?=\n\n|\n\*\*Acceptance)", body, re.DOTALL)
```

**manage_epics._format_story_section** never emits a user story block, even if `story_data` contains a `user_story` key. There is no code path that writes the `**As a**` / `**I want**` / `**so that**` block.

**Impact:** Stories added via `add_story()` will always have an empty `user_story` when parsed by `parse_detail_blocks`. The GitHub issue body will be missing the "User Story" section.

---

## Summary

| # | Severity | Description |
|---|----------|-------------|
| 1 | MEDIUM | AC format mismatch: `_format_story_section` emits `` `text` ``, parser expects `` `AC-NN`: text `` |
| 2 | LOW | `_format_story_section` omits Saga/Epic/Release rows; `parse_detail_blocks` reads empty strings |
| 3 | MEDIUM | `\d+` vs `\d{4}` in story ID patterns; 5+ digit IDs parsed by one, ignored by other |
| 4 | LOW | `_META_ROW_RE` doesn't filter separator rows (harmless junk key `-------`) |
| 5 | INFO | `renumber_stories` leaves heading with old ID, metadata with new IDs — internally inconsistent |
| 6 | INFO | `_format_story_section` never writes user story block; `parse_detail_blocks` can't find one |

**Bugs 1 and 3 are the most actionable.** Bug 1 means acceptance criteria from `add_story` are silently lost during issue creation. Bug 3 means any project using non-4-digit story IDs will have manage_epics and populate_issues disagree on which stories exist.
