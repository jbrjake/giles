#!/usr/bin/env python3
"""Generate domain-specific review checklist items from persona history.

Parses persona history files for patterns of bugs caught, issues found,
and generates checklist items for future reviews.

Usage: python history_to_checklist.py [--team-dir sprint-config/team]
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from validate_config import load_config, ConfigError

# Keywords that indicate a bug/issue pattern
_PATTERN_KEYWORDS = re.compile(
    r'\b(bug|issue|caught|fixed|found|regression|broke|fail|miss|error|crash|'
    r'violated|violation|incorrect|wrong|stale|leak|race|deadlock)\b',
    re.IGNORECASE,
)


def extract_checklist_items(history_text: str,
                            persona_name: str) -> list[str]:
    """Extract review checklist items from a persona's history."""
    items: list[str] = []
    # Look for sentences containing pattern keywords near technical terms
    for line in history_text.splitlines():
        if not _PATTERN_KEYWORDS.search(line):
            continue
        # Extract the sprint context
        sprint_match = re.search(r'Sprint (\d+)', line)
        sprint_ref = f"Sprint {sprint_match.group(1)}" if sprint_match else "prior sprint"

        # Clean up the line for a checklist item
        cleaned = line.strip().lstrip("-*• ")
        if len(cleaned) > 20:
            items.append(
                f"{persona_name} history: check for similar issues "
                f"({cleaned[:80]}... from {sprint_ref})"
            )

    return items


def generate_checklists(team_dir: str) -> dict[str, list[str]]:
    """Generate checklists for all personas with history files."""
    history_dir = Path(team_dir) / "history"
    if not history_dir.is_dir():
        return {}

    result: dict[str, list[str]] = {}
    for md_file in sorted(history_dir.glob("*.md")):
        persona = md_file.stem
        text = md_file.read_text(encoding="utf-8")
        items = extract_checklist_items(text, persona)
        if items:
            result[persona] = items

    return result


def format_checklist(checklists: dict[str, list[str]]) -> str:
    """Format all checklists as markdown."""
    if not checklists:
        return "No history-derived checklist items found."

    lines: list[str] = ["# History-Derived Review Checklist", ""]
    for persona, items in sorted(checklists.items()):
        lines.append(f"## {persona}")
        for item in items:
            lines.append(f"- [ ] {item}")
        lines.append("")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate review checklists from persona history")
    parser.add_argument("--team-dir", default=None)
    args = parser.parse_args()

    team_dir = args.team_dir
    if not team_dir:
        try:
            config = load_config()
            team_dir = config.get("paths", {}).get(
                "team_dir", "sprint-config/team")
        except ConfigError:
            team_dir = "sprint-config/team"

    checklists = generate_checklists(team_dir)
    print(format_checklist(checklists))


if __name__ == "__main__":
    main()
