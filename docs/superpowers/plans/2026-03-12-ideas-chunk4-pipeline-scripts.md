# Chunk 4: Pipeline Scripts — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build four pipeline scripts: team voice extraction, requirements traceability, test plan coverage, and saga/epic management. Integrate with ceremonies and monitor.

**Architecture:** All scripts follow existing patterns — stdlib-only Python 3.10+, `sys.path.insert` to reach `validate_config.py`, config-driven paths, idempotent operations. Each script is standalone with a `main()` entry point and importable functions.

**Tech Stack:** Python 3.10+ stdlib only

**Spec:** `docs/superpowers/specs/2026-03-12-ideas-implementation-design.md` — Chunk 4 section

**Depends on:** None (independent of Chunks 1-3, though integration points reference Giles)

---

## File Structure

### Files to Create

| File | Purpose |
|------|---------|
| `scripts/team_voices.py` | Extract persona commentary from saga/epic files |
| `scripts/traceability.py` | Bidirectional story ↔ PRD ↔ test case mapping with gap detection |
| `scripts/test_coverage.py` | Compare planned test cases against actual test files by language |
| `scripts/manage_sagas.py` | Saga CRUD with cross-reference updates |
| `scripts/manage_epics.py` | Epic CRUD with story re-numbering |

---

## Task 0: Team Voice Extraction

**Files:**
- Create: `scripts/team_voices.py`

- [ ] **Step 1: Design the extraction pattern**

Persona commentary in saga/epic files uses the blockquote format:
```markdown
> **Rusti Ferris:** "This is where the type system earns its keep..."
```

The script needs to:
1. Scan all files in `sagas_dir` and `epics_dir`
2. Extract blockquotes matching `> **{Name}:** "{text}"`
3. Index by persona name and source file
4. Return a dict: `{persona_name: [{file, context, quote}]}`

- [ ] **Step 2: Write failing tests**

Create test file. Tests should use the Hexwise fixture:

```python
def test_extract_voices_from_sagas():
    """Extract team voices from Hexwise saga files."""
    voices = extract_voices(sagas_dir="tests/fixtures/hexwise/docs/agile/sagas")
    assert "Rusti Ferris" in voices
    assert "Palette Jones" in voices
    assert "Checker Macready" in voices
    # S01-core.md has all three personas
    rusti_quotes = [v for v in voices["Rusti Ferris"] if "S01" in v["file"]]
    assert len(rusti_quotes) >= 1
    assert "type system" in rusti_quotes[0]["quote"].lower()

def test_extract_voices_from_epics():
    """Extract commentary from epic files (if present)."""
    voices = extract_voices(epics_dir="tests/fixtures/hexwise/docs/agile/epics")
    # Epics don't have team voice blocks in Hexwise, so should return empty
    # or only find any inline persona references
    assert isinstance(voices, dict)

def test_extract_voices_empty_dir(tmp_path):
    """Gracefully handle directories with no persona commentary."""
    voices = extract_voices(sagas_dir=str(tmp_path))
    assert voices == {}
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
python -m unittest tests/test_pipeline_scripts.py -v
```

Expected: ImportError or similar — script doesn't exist yet.

- [ ] **Step 4: Implement team_voices.py**

```python
"""Extract persona commentary from saga and epic files.

Scans markdown files for blockquote patterns:
    > **Name:** "quoted text"
    > **Name:** unquoted text

Returns {persona_name: [{file, context, quote}]} index.
"""
from __future__ import annotations
import re
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))
from validate_config import load_config

# Pattern: > **Name:** "text" or > **Name:** text
VOICE_PATTERN = re.compile(
    r'^>\s*\*\*([^*]+)\*\*:\s*"?(.+?)"?\s*$'
)


def extract_voices(
    sagas_dir: str | None = None,
    epics_dir: str | None = None,
) -> dict[str, list[dict]]:
    """Extract persona commentary blocks from saga/epic files."""
    voices: dict[str, list[dict]] = {}
    dirs = []
    if sagas_dir:
        dirs.append(Path(sagas_dir))
    if epics_dir:
        dirs.append(Path(epics_dir))

    for d in dirs:
        if not d.is_dir():
            continue
        for md_file in sorted(d.glob("*.md")):
            _extract_from_file(md_file, voices)
    return voices


def _extract_from_file(path: Path, voices: dict[str, list[dict]]) -> None:
    """Extract voice blocks from a single markdown file."""
    lines = path.read_text().splitlines()
    current_section = ""
    i = 0
    while i < len(lines):
        line = lines[i]
        # Track current heading for context
        if line.startswith("#"):
            current_section = line.lstrip("#").strip()

        match = VOICE_PATTERN.match(line)
        if match:
            name = match.group(1).strip()
            quote = match.group(2).strip()
            # Consume continuation lines (blockquote lines without a new name)
            while i + 1 < len(lines) and lines[i + 1].startswith(">") and not VOICE_PATTERN.match(lines[i + 1]):
                continuation = lines[i + 1].lstrip(">").strip()
                if continuation:
                    quote += " " + continuation
                i += 1

            voices.setdefault(name, []).append({
                "file": path.name,
                "section": current_section,
                "quote": quote,
            })
        i += 1


def main() -> None:
    """CLI entry point: extract and print voice index."""
    config = load_config()
    sagas_dir = config.get("paths", {}).get("sagas_dir")
    epics_dir = config.get("paths", {}).get("epics_dir")
    voices = extract_voices(sagas_dir=sagas_dir, epics_dir=epics_dir)

    for persona, quotes in sorted(voices.items()):
        print(f"\n## {persona} ({len(quotes)} quotes)")
        for q in quotes:
            print(f"  - [{q['file']}:{q['section']}] {q['quote'][:80]}...")


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
python -m unittest tests/test_pipeline_scripts.py::TestTeamVoices -v
```

- [ ] **Step 6: Commit**

```bash
git add scripts/team_voices.py tests/test_pipeline_scripts.py
git commit -m "feat: add team_voices.py for persona commentary extraction"
```

---

## Task 1: Requirements Traceability

**Files:**
- Create: `scripts/traceability.py`

- [ ] **Step 1: Write failing tests**

Tests use Hexwise fixture. Hexwise has complete traceability (04-traceability.md confirms all 17 stories are covered), so the script should report zero gaps.

```python
def test_traceability_no_gaps():
    """Hexwise has complete story-to-test traceability."""
    report = build_traceability(
        epics_dir="tests/fixtures/hexwise/docs/agile/epics",
        test_plan_dir="tests/fixtures/hexwise/docs/test-plan",
    )
    assert report["stories_without_tests"] == []

def test_traceability_detects_gaps(tmp_path):
    """Detect stories that have no test case links."""
    # Create a minimal epic with a story that has no Test Cases field
    epic = tmp_path / "E-0101-test.md"
    epic.write_text("### US-9999: Untested Story\n\n| Field | Value |\n|---|---|\n| Story Points | 3 |\n")
    report = build_traceability(epics_dir=str(tmp_path))
    assert "US-9999" in report["stories_without_tests"]

def test_traceability_prd_coverage():
    """Check PRD requirements link to stories."""
    report = build_traceability(
        epics_dir="tests/fixtures/hexwise/docs/agile/epics",
        prd_dir="tests/fixtures/hexwise/docs/prd",
    )
    # All REQ-* IDs in Hexwise PRDs should map to stories
    assert report["requirements_without_stories"] == []
```

- [ ] **Step 2: Run tests to verify they fail**

- [ ] **Step 3: Implement traceability.py**

Key functions:
- `parse_stories(epics_dir)` — extract story IDs, test case links, PRD links from epic files
- `parse_test_cases(test_plan_dir)` — extract test case IDs from test plan files
- `parse_requirements(prd_dir)` — extract REQ-* IDs from PRD files
- `build_traceability(epics_dir, test_plan_dir, prd_dir)` — build bidirectional maps, find gaps
- `format_report(traceability)` — produce markdown report
- `main()` — CLI entry point

Story extraction pattern: scan for `### US-XXXX:` headings, then parse the metadata table for `Test Cases` and `PRD` fields.

Test case extraction: scan for `### TC-*:` and `### GP-*:` headings.

Requirement extraction: scan for `**REQ-*:**` patterns in PRD files.

- [ ] **Step 4: Run tests to verify they pass**

- [ ] **Step 5: Commit**

```bash
git add scripts/traceability.py tests/test_pipeline_scripts.py
git commit -m "feat: add traceability.py for story/PRD/test bidirectional mapping"
```

---

## Task 2: Test Plan Coverage

**Files:**
- Create: `scripts/test_coverage.py`

- [ ] **Step 1: Write failing tests**

```python
def test_coverage_no_actual_tests():
    """Hexwise fixture has no actual test files (it's a fixture, not built)."""
    report = check_test_coverage(
        test_plan_dir="tests/fixtures/hexwise/docs/test-plan",
        project_root="tests/fixtures/hexwise",
        language="rust",
    )
    assert len(report["planned"]) > 0  # ~45 planned tests
    assert len(report["implemented"]) == 0  # no actual tests
    assert report["planned"] == report["missing"]  # all missing

def test_coverage_language_detection():
    """Detect test patterns per language."""
    # Rust: #[test] fn test_name
    # Python: def test_name
    # etc.
    assert detect_test_functions("rust", '#[test]\nfn test_parsing() {') == ["test_parsing"]
    assert detect_test_functions("python", 'def test_parsing(self):') == ["test_parsing"]
```

- [ ] **Step 2: Run tests to verify they fail**

- [ ] **Step 3: Implement test_coverage.py**

Key functions:
- `parse_planned_tests(test_plan_dir)` — extract test case IDs and titles from plan files
- `detect_test_functions(language, source)` — find test function names in source code
- `scan_project_tests(project_root, language)` — walk project tree, find all test files and functions
- `check_test_coverage(test_plan_dir, project_root, language)` — compare planned vs actual
- `format_report(coverage)` — markdown report: implemented, missing, unplanned
- `main()` — CLI entry point

Language-specific detection:

```python
_TEST_PATTERNS = {
    "rust": re.compile(r'#\[test\]\s*(?:#\[.*\]\s*)*fn\s+(\w+)'),
    "python": re.compile(r'def\s+(test_\w+)'),
    "javascript": re.compile(r'(?:it|test)\s*\(\s*[\'"]([^\'"]+)'),
    "go": re.compile(r'func\s+(Test\w+)'),
}

_TEST_FILE_PATTERNS = {
    "rust": ["**/tests/**/*.rs", "**/src/**/*.rs"],  # scan src for #[test] too
    "python": ["**/test_*.py", "**/*_test.py"],
    "javascript": ["**/*.test.*", "**/*.spec.*"],
    "go": ["**/*_test.go"],
}
```

- [ ] **Step 4: Run tests to verify they pass**

- [ ] **Step 5: Commit**

```bash
git add scripts/test_coverage.py tests/test_pipeline_scripts.py
git commit -m "feat: add test_coverage.py for planned vs actual test comparison"
```

---

## Task 3: Saga/Epic Management

**Files:**
- Create: `scripts/manage_sagas.py`
- Create: `scripts/manage_epics.py`

These are CRUD utilities for programmatic editing of saga and epic markdown files. More complex than the other scripts because they modify structured markdown.

- [ ] **Step 1: Write failing tests for epic management**

```python
def test_add_story_to_epic(tmp_path):
    """Add a new story to an epic file."""
    # Copy E-0101-parsing.md to tmp_path
    # Call add_story(epic_file, story_data)
    # Verify the story appears in the file with correct format

def test_reorder_stories(tmp_path):
    """Reorder stories within an epic."""
    # Verify story order matches the requested order

def test_renumber_after_split(tmp_path):
    """Re-number story references when a story is split."""
    # Split US-0102 into US-0102a and US-0102b
    # Verify dependency graphs update, sprint allocations update
```

- [ ] **Step 2: Write failing tests for saga management**

```python
def test_update_sprint_allocation(tmp_path):
    """Update sprint allocation table in a saga."""
    # Change which stories are in which sprint
    # Verify the allocation table updates correctly

def test_update_epic_index(tmp_path):
    """Update epic index when story counts change."""
    # Add a story to an epic, verify saga's epic index table updates
```

- [ ] **Step 3: Run tests to verify they fail**

- [ ] **Step 4: Implement manage_epics.py**

Key functions:
- `parse_epic(path)` — parse epic file into structured data (metadata, stories list)
- `add_story(path, story_data)` — append a new story section to the epic
- `remove_story(path, story_id)` — remove a story section, update metadata
- `reorder_stories(path, story_ids)` — reorder story sections to match given ID list
- `update_dependency_graph(path)` — regenerate the dependency graph section from story metadata
- `renumber_stories(path, old_id, new_ids)` — replace references to old_id with new_ids
- `main()` — CLI with subcommands: add, remove, reorder, renumber

Story data format for add:
```python
{
    "id": "US-XXXX",
    "title": "...",
    "story_points": 3,
    "priority": "P1",
    "personas": ["Name1", "Name2"],
    "blocked_by": ["US-YYYY"],
    "blocks": [],
    "test_cases": ["TC-XXX-001"],
    "acceptance_criteria": ["AC-01: ...", "AC-02: ..."],
    "tasks": [{"id": "T-XXXX-01", "description": "...", "sp": 1}],
}
```

- [ ] **Step 5: Implement manage_sagas.py**

Key functions:
- `parse_saga(path)` — parse saga file into structured data
- `update_sprint_allocation(path, allocation)` — rewrite sprint allocation table
- `update_epic_index(path, epics_dir)` — recalculate epic index from epic files
- `update_team_voices(path, voices)` — update the team voices blockquote section
- `main()` — CLI with subcommands: update-allocation, update-index, update-voices

- [ ] **Step 6: Run tests to verify they pass**

- [ ] **Step 7: Commit**

```bash
git add scripts/manage_sagas.py scripts/manage_epics.py tests/test_pipeline_scripts.py
git commit -m "feat: add saga/epic management scripts for programmatic backlog editing"
```

---

## Task 4: Integration Notes and Documentation

- [ ] **Step 1: Document integration points**

These scripts are standalone but integrate with the sprint lifecycle:

| Script | Integration Point | When |
|--------|------------------|------|
| `team_voices.py` | Kickoff ceremony | Giles surfaces relevant voices during story walk |
| `traceability.py` | Sprint-monitor | Periodic gap detection, kickoff prep |
| `test_coverage.py` | Demo ceremony | Verify test plan commitments were delivered |
| `manage_sagas.py` | Sprint-setup | Backlog modifications during planning |
| `manage_epics.py` | Sprint-setup | Story splits, re-numbering |

Integration is done by the ceremony references and monitor SKILL.md reading the script outputs — no code coupling between the scripts and the skills.

- [ ] **Step 2: Update CLAUDE.md**

Add all five scripts to the Scripts table with purpose and key functions.

- [ ] **Step 3: Update CHEATSHEET.md**

Add line-number indices for all five scripts.

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md CHEATSHEET.md
git commit -m "docs: update CLAUDE.md and CHEATSHEET.md for Chunk 4 pipeline scripts"
```
