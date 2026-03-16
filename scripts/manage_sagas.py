#!/usr/bin/env python3
"""Saga CRUD: parse, update sprint allocation, epic index, team voices.

Saga files use a structured format with metadata table, Team Voices
blockquotes, Epic Index table, Sprint Allocation table, Dependency
Graph, and Release Gate Checklist.

Run: python scripts/manage_sagas.py update-allocation <saga_file> <json>
     python scripts/manage_sagas.py update-index <saga_file> <epics_dir>
     python scripts/manage_sagas.py update-voices <saga_file> <voices_json>
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))

# BH18-012: TABLE_ROW imported from validate_config (single source of truth)
from validate_config import safe_int as _safe_int, TABLE_ROW, parse_header_table
EPIC_TABLE_ROW = re.compile(
    r'^\|\s*(E-\d+)\s*\|\s*(.+?)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|'
)
SPRINT_TABLE_ROW = re.compile(
    r'^\|\s*(Sprint\s+\d+)\s*\|\s*(.+?)\s*\|\s*(\d+)\s*\|'
)


# §manage_sagas.parse_saga
def parse_saga(path: str) -> dict:
    """Parse a saga file into structured data.

    Returns:
        title: str
        stories_count: int
        epics_count: int
        total_sp: int
        epic_index: [{id, name, stories, sp}, ...]
        sprint_allocation: [{sprint, stories, sp}, ...]
        section_ranges: {section_name: (start_line, end_line)}
    """
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    metadata = parse_header_table(lines, stop_heading="##")
    epic_index = _parse_epic_index(lines)
    sprint_allocation = _parse_sprint_allocation(lines)
    section_ranges = _find_section_ranges(lines)

    return {
        "title": re.sub(r'^#+\s*', '', lines[0]).strip() if lines else "",
        "stories_count": _safe_int(metadata.get("Stories", "0")),
        "epics_count": _safe_int(metadata.get("Epics", "0")),
        "total_sp": _safe_int(metadata.get("Total SP", "0")),
        "epic_index": epic_index,
        "sprint_allocation": sprint_allocation,
        "section_ranges": section_ranges,
    }



# §manage_sagas._parse_epic_index
def _parse_epic_index(lines: list[str]) -> list[dict]:
    """Parse the Epic Index table."""
    epics: list[dict] = []
    in_section = False
    for line in lines:
        if line.strip() == "## Epic Index":
            in_section = True
            continue
        if in_section and line.startswith("## "):
            break
        if in_section:
            m = EPIC_TABLE_ROW.match(line)
            if m:
                epics.append({
                    "id": m.group(1).strip(),
                    "name": m.group(2).strip(),
                    "stories": int(m.group(3)),
                    "sp": int(m.group(4)),
                })
    return epics


# §manage_sagas._parse_sprint_allocation
def _parse_sprint_allocation(lines: list[str]) -> list[dict]:
    """Parse the Sprint Allocation table."""
    sprints: list[dict] = []
    in_section = False
    for line in lines:
        if line.strip() == "## Sprint Allocation":
            in_section = True
            continue
        if in_section and line.startswith("## "):
            break
        if in_section:
            m = SPRINT_TABLE_ROW.match(line)
            if m:
                sprints.append({
                    "sprint": m.group(1).strip(),
                    "stories": m.group(2).strip(),
                    "sp": m.group(3).strip(),
                })
    return sprints


# §manage_sagas._find_section_ranges
def _find_section_ranges(lines: list[str]) -> dict[str, tuple[int, int]]:
    """Find line ranges for each ## section.

    Only ``## `` headings (level 2) are treated as section boundaries.
    Subsections (``### ``, ``#### ``, etc.) within a section are preserved
    as part of that section's content.
    """
    ranges: dict[str, tuple[int, int]] = {}
    current_section = ""
    current_start = 0

    for i, line in enumerate(lines):
        if line.startswith("## ") and not line.startswith("### "):
            if current_section:
                ranges[current_section] = (current_start, i)
            heading = line.lstrip("#").strip()
            # Deduplicate: append a counter suffix if heading already seen
            if heading in ranges:
                n = 2
                while f"{heading} ({n})" in ranges:
                    n += 1
                heading = f"{heading} ({n})"
            current_section = heading
            current_start = i

    if current_section:
        ranges[current_section] = (current_start, len(lines))

    return ranges


# §manage_sagas.update_sprint_allocation
def update_sprint_allocation(
    path: str,
    allocation: list[dict],
) -> None:
    """Rewrite the Sprint Allocation table in a saga file.

    allocation: [{sprint: str, stories: str, sp: str}, ...]
    """
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    section_ranges = _find_section_ranges(lines)

    if "Sprint Allocation" not in section_ranges:
        return

    start, end = section_ranges["Sprint Allocation"]

    # Build new table
    new_section = [
        "## Sprint Allocation",
        "",
        "| Sprint | Stories | SP |",
        "|--------|---------|-----|",
    ]
    for entry in allocation:
        new_section.append(
            f"| {entry['sprint']} | {entry['stories']} | {entry['sp']} |"
        )

    new_lines = lines[:start] + new_section + [""] + lines[end:]
    Path(path).write_text("\n".join(new_lines), encoding="utf-8")


# §manage_sagas.update_epic_index
def update_epic_index(
    path: str,
    epics_dir: str,
    saga_id: str = "",
) -> None:
    """Recalculate epic index from epic files.

    Scans epics_dir for epic files belonging to this saga, parses
    their metadata, and rebuilds the Epic Index table.
    """
    from manage_epics import parse_epic

    lines = Path(path).read_text(encoding="utf-8").splitlines()
    section_ranges = _find_section_ranges(lines)

    if "Epic Index" not in section_ranges:
        return

    # Parse epic files
    epics_path = Path(epics_dir)
    epics_data: list[dict] = []
    for md_file in sorted(epics_path.glob("*.md")):
        # The filename must be like E-0101-parsing.md — skip non-standard names
        parts = md_file.stem.split("-")
        if len(parts) < 2:
            continue
        epic_id = f"{parts[0]}-{parts[1]}"
        epic = parse_epic(str(md_file))
        # Filter by saga if specified
        if saga_id and epic.get("saga") != saga_id:
            continue
        epics_data.append({
            "id": epic_id,
            "name": epic.get("title", "").split(" — ", 1)[-1] if " — " in epic.get("title", "") else epic.get("title", ""),
            "stories": epic.get("stories_count", 0),
            "sp": epic.get("total_sp", 0),
        })

    start, end = section_ranges["Epic Index"]

    new_section = [
        "## Epic Index",
        "",
        "| Epic | Name | Stories | SP |",
        "|------|------|---------|-----|",
    ]
    for e in epics_data:
        new_section.append(
            f"| {e['id']} | {e['name']} | {e['stories']} | {e['sp']} |"
        )

    new_lines = lines[:start] + new_section + [""] + lines[end:]
    Path(path).write_text("\n".join(new_lines), encoding="utf-8")


# §manage_sagas.update_team_voices
def update_team_voices(path: str, voices: dict[str, str]) -> None:
    """Update the Team Voices blockquote section.

    voices: {persona_name: "quote text"}
    """
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    section_ranges = _find_section_ranges(lines)

    if "Team Voices" not in section_ranges:
        return

    start, end = section_ranges["Team Voices"]

    new_section = ["## Team Voices", ""]
    for name, quote in voices.items():
        if new_section[-1] != "":
            new_section.append("")
        new_section.append(f'> **{name}:** "{quote}"')

    new_lines = lines[:start] + new_section + [""] + lines[end:]
    Path(path).write_text("\n".join(new_lines), encoding="utf-8")


# §manage_sagas.main
def main() -> None:
    """CLI entry point with subcommands."""
    if len(sys.argv) < 3:
        print("Usage: manage_sagas.py <command> <saga_file> [args...]")
        print("Commands: update-allocation, update-index, update-voices")
        sys.exit(1)

    command = sys.argv[1]
    saga_file = sys.argv[2]

    if command == "update-allocation":
        alloc_json = sys.argv[3] if len(sys.argv) > 3 else "[]"
        allocation = json.loads(alloc_json)
        update_sprint_allocation(saga_file, allocation)
        print(f"Updated sprint allocation in {saga_file}")

    elif command == "update-index":
        if len(sys.argv) < 4:
            print("Usage: manage_sagas.py update-index <saga-file> <epics-dir> [saga-id]", file=sys.stderr)
            sys.exit(1)
        epics_dir = sys.argv[3]
        saga_id = sys.argv[4] if len(sys.argv) > 4 else ""
        update_epic_index(saga_file, epics_dir, saga_id=saga_id)
        print(f"Updated epic index in {saga_file}")

    elif command == "update-voices":
        voices_json = sys.argv[3] if len(sys.argv) > 3 else "{}"
        voices = json.loads(voices_json)
        update_team_voices(saga_file, voices)
        print(f"Updated team voices in {saga_file}")

    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
