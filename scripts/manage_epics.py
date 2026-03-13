#!/usr/bin/env python3
"""Epic CRUD: parse, add, remove, reorder stories in epic markdown files.

Epic files use a structured format with a metadata table at the top
and ### US-XXXX: story sections with metadata tables, acceptance
criteria, and tasks.

Run: python scripts/manage_epics.py add <epic_file> <story_json>
     python scripts/manage_epics.py remove <epic_file> <story_id>
     python scripts/manage_epics.py reorder <epic_file> <id1,id2,...>
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))

STORY_HEADING = re.compile(r'^(###\s+(US-\d+):\s*(.+))')
TABLE_ROW = re.compile(r'^\|\s*(.+?)\s*\|\s*(.+?)\s*\|')


def parse_epic(path: str) -> dict:
    """Parse an epic file into structured data.

    Returns:
        title: str
        saga: str
        stories_count: int
        total_sp: int
        release: str
        stories: [{id, title, story_points, priority, ...}, ...]
        raw_sections: [{id, start_line, end_line, lines}, ...]
    """
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    metadata = _parse_header_table(lines)
    stories, raw_sections = _parse_stories(lines)

    return {
        "title": lines[0].lstrip("# ").strip() if lines else "",
        "saga": metadata.get("Saga", ""),
        "stories_count": int(metadata.get("Stories", "0")),
        "total_sp": int(metadata.get("Total SP", "0")),
        "release": metadata.get("Release", ""),
        "stories": stories,
        "raw_sections": raw_sections,
    }


def _parse_header_table(lines: list[str]) -> dict[str, str]:
    """Parse the epic-level metadata table at the top of the file."""
    metadata: dict[str, str] = {}
    in_table = False
    for line in lines:
        if line.startswith("###"):
            break  # Hit first story
        row = TABLE_ROW.match(line)
        if row:
            field = row.group(1).strip()
            value = row.group(2).strip()
            if field not in ("Field", "---", ""):
                metadata[field] = value
                in_table = True
        elif in_table and line.strip() == "":
            break
    return metadata


def _parse_stories(lines: list[str]) -> tuple[list[dict], list[dict]]:
    """Parse all ### US-XXXX story sections from the file."""
    stories: list[dict] = []
    raw_sections: list[dict] = []
    i = 0
    current_story_start = -1

    while i < len(lines):
        m = STORY_HEADING.match(lines[i])
        if m:
            # Close previous story section
            if current_story_start >= 0 and raw_sections:
                raw_sections[-1]["end_line"] = i - 1
                raw_sections[-1]["lines"] = lines[
                    raw_sections[-1]["start_line"]:i
                ]

            story_id = m.group(2)
            title = m.group(3).strip()
            current_story_start = i

            # Parse story metadata table
            story_meta: dict[str, str] = {}
            j = i + 1
            while j < len(lines):
                row = TABLE_ROW.match(lines[j])
                if row:
                    field = row.group(1).strip()
                    value = row.group(2).strip()
                    if field not in ("Field", "---", ""):
                        story_meta[field] = value
                elif lines[j].startswith("###"):
                    break
                j += 1

            stories.append({
                "id": story_id,
                "title": title,
                "story_points": int(story_meta.get("Story Points", "0")),
                "priority": story_meta.get("Priority", ""),
                "release": story_meta.get("Release", ""),
                "saga": story_meta.get("Saga", ""),
                "epic": story_meta.get("Epic", ""),
                "personas": story_meta.get("Personas", ""),
                "blocked_by": story_meta.get("Blocked By", ""),
                "blocks": story_meta.get("Blocks", ""),
                "test_cases": story_meta.get("Test Cases", ""),
            })
            raw_sections.append({
                "id": story_id,
                "start_line": i,
                "end_line": -1,
                "lines": [],
            })
        i += 1

    # Close the last story section
    if raw_sections:
        raw_sections[-1]["end_line"] = len(lines)
        raw_sections[-1]["lines"] = lines[raw_sections[-1]["start_line"]:]

    return stories, raw_sections


def _format_story_section(story_data: dict) -> str:
    """Format a story data dict as a markdown section."""
    lines = [
        f"### {story_data['id']}: {story_data['title']}",
        "",
        "| Field | Value |",
        "|-------|-------|",
        f"| Story Points | {story_data['story_points']} |",
        f"| Priority | {story_data['priority']} |",
    ]

    if story_data.get("personas"):
        personas = story_data["personas"]
        if isinstance(personas, list):
            personas = ", ".join(personas)
        lines.append(f"| Personas | {personas} |")

    blocked_by = story_data.get("blocked_by", [])
    if isinstance(blocked_by, list):
        blocked_by = ", ".join(blocked_by) if blocked_by else "\u2014"
    lines.append(f"| Blocked By | {blocked_by} |")

    blocks = story_data.get("blocks", [])
    if isinstance(blocks, list):
        blocks = ", ".join(blocks) if blocks else "\u2014"
    lines.append(f"| Blocks | {blocks} |")

    test_cases = story_data.get("test_cases", [])
    if isinstance(test_cases, list):
        test_cases = ", ".join(test_cases) if test_cases else "\u2014"
    lines.append(f"| Test Cases | {test_cases} |")

    # Acceptance criteria
    if story_data.get("acceptance_criteria"):
        lines.append("")
        lines.append("**Acceptance Criteria:**")
        for ac in story_data["acceptance_criteria"]:
            lines.append(f"- [ ] `{ac}`")

    # Tasks
    if story_data.get("tasks"):
        lines.append("")
        lines.append("**Tasks:**")
        for task in story_data["tasks"]:
            tid = task.get("id", "T-XXXX-01")
            desc = task.get("description", "")
            sp = task.get("sp", 1)
            lines.append(f"- [ ] `{tid}`: {desc} ({sp} SP)")

    return "\n".join(lines)


def add_story(path: str, story_data: dict) -> None:
    """Append a new story section to an epic file."""
    content = Path(path).read_text(encoding="utf-8")
    new_section = _format_story_section(story_data)

    # Ensure the file ends with proper separation
    if not content.endswith("\n"):
        content += "\n"
    if not content.endswith("\n\n"):
        content += "\n"

    content += "---\n\n" + new_section + "\n"
    Path(path).write_text(content, encoding="utf-8")


def remove_story(path: str, story_id: str) -> None:
    """Remove a story section from an epic file."""
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    epic = parse_epic(path)
    section = next(
        (s for s in epic["raw_sections"] if s["id"] == story_id), None
    )
    if not section:
        return

    start = section["start_line"]
    end = section["end_line"]

    # Also remove the --- separator before this story (if present)
    sep_start = start
    while sep_start > 0 and lines[sep_start - 1].strip() in ("", "---"):
        sep_start -= 1
    # Keep at least one blank line
    if sep_start < start:
        sep_start += 1

    new_lines = lines[:sep_start] + lines[end:]
    # Clean up trailing blank lines
    while new_lines and new_lines[-1].strip() == "":
        new_lines.pop()
    new_lines.append("")

    Path(path).write_text("\n".join(new_lines), encoding="utf-8")


def reorder_stories(path: str, story_ids: list[str]) -> None:
    """Reorder story sections to match the given ID list."""
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    epic = parse_epic(path)

    # Find where stories begin (after the header/intro)
    first_section = epic["raw_sections"][0] if epic["raw_sections"] else None
    if not first_section:
        return

    # Find the start of the stories area (including separator before first story)
    stories_start = first_section["start_line"]
    while stories_start > 0 and lines[stories_start - 1].strip() in ("", "---"):
        stories_start -= 1
    if stories_start > 0:
        stories_start += 1  # Keep at least one separator line

    header = lines[:stories_start]

    # Build section map
    section_map: dict[str, list[str]] = {}
    for sec in epic["raw_sections"]:
        section_map[sec["id"]] = sec["lines"]

    # Validate: all existing stories must be in the provided ID list
    existing_ids = set(section_map.keys())
    provided_ids = set(story_ids)
    missing_from_list = existing_ids - provided_ids
    if missing_from_list:
        raise ValueError(
            f"reorder_stories: story IDs missing from provided list: "
            f"{sorted(missing_from_list)}. All stories must be included "
            f"to prevent data loss."
        )

    # Reassemble in new order
    new_lines = list(header)
    for i, sid in enumerate(story_ids):
        if sid not in section_map:
            continue
        if i > 0 or new_lines:
            new_lines.append("")
            new_lines.append("---")
            new_lines.append("")
        new_lines.extend(section_map[sid])

    # Clean up trailing blank lines
    while new_lines and new_lines[-1].strip() == "":
        new_lines.pop()
    new_lines.append("")

    Path(path).write_text("\n".join(new_lines), encoding="utf-8")


def renumber_stories(path: str, old_id: str, new_ids: list[str]) -> None:
    """Replace references to old_id with new_ids in metadata fields.

    Useful for story splits (e.g., US-0102 → US-0102a, US-0102b).
    Only replaces in table rows and body text, not in ### headings,
    to preserve the parseable heading format.
    """
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    replacement = ", ".join(new_ids)
    new_lines = []
    for line in lines:
        if line.startswith("### "):
            # Preserve headings — don't corrupt ### US-XXXX: Title
            new_lines.append(line)
        else:
            new_lines.append(re.sub(rf'\b{re.escape(old_id)}\b', replacement, line))
    Path(path).write_text("\n".join(new_lines), encoding="utf-8")


def main() -> None:
    """CLI entry point with subcommands: add, remove, reorder, renumber."""
    if len(sys.argv) < 3:
        print("Usage: manage_epics.py <command> <epic_file> [args...]")
        print("Commands: add, remove, reorder, renumber")
        sys.exit(1)

    command = sys.argv[1]
    epic_file = sys.argv[2]

    if command == "add":
        story_json = sys.argv[3] if len(sys.argv) > 3 else "{}"
        story_data = json.loads(story_json)
        add_story(epic_file, story_data)
        print(f"Added story {story_data.get('id', '?')} to {epic_file}")

    elif command == "remove":
        story_id = sys.argv[3]
        remove_story(epic_file, story_id)
        print(f"Removed {story_id} from {epic_file}")

    elif command == "reorder":
        ids = sys.argv[3].split(",")
        reorder_stories(epic_file, ids)
        print(f"Reordered stories in {epic_file}")

    elif command == "renumber":
        old_id = sys.argv[3]
        new_ids = sys.argv[4].split(",")
        renumber_stories(epic_file, old_id, new_ids)
        print(f"Renumbered {old_id} → {new_ids} in {epic_file}")

    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
