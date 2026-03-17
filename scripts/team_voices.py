#!/usr/bin/env python3
"""Extract persona commentary from saga and epic files.

Scans markdown files for blockquote patterns:
    > **Name:** "quoted text"
    > **Name:** unquoted text

Returns {persona_name: [{file, section, quote}]} index.

Run: python scripts/team_voices.py   (requires sprint-config/)
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))
from validate_config import load_config, ConfigError

# Pattern: > **Name:** "text" or > **Name:** text
# Note: colon is inside the bold markers: **Name:**
# Try fully-quoted first (entire text wrapped in quotes), then unquoted.
# §team_voices.VOICE_PATTERN
VOICE_PATTERN = re.compile(
    r'^>\s*\*\*([^*]+?):\*\*\s*(?:"(.+)"|(.+?))\s*$'
)


# §team_voices.extract_voices
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


# §team_voices._extract_from_file
def _extract_from_file(path: Path, voices: dict[str, list[dict]]) -> None:
    """Extract voice blocks from a single markdown file."""
    lines = path.read_text(encoding="utf-8").split('\n')
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
            # group(2) is quoted text, group(3) is unquoted text
            quote = (match.group(2) or match.group(3) or "").strip()
            # Consume continuation lines (blockquote lines without a new name)
            while (
                i + 1 < len(lines)
                and lines[i + 1].startswith(">")
                and not VOICE_PATTERN.match(lines[i + 1])
            ):
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


# §team_voices.main
def main() -> None:
    """CLI entry point: extract and print voice index."""
    try:
        config = load_config()
    except ConfigError:
        sys.exit(1)
    sagas_dir = config.get("paths", {}).get("sagas_dir")
    epics_dir = config.get("paths", {}).get("epics_dir")
    voices = extract_voices(sagas_dir=sagas_dir, epics_dir=epics_dir)

    for persona, quotes in sorted(voices.items()):
        print(f"\n## {persona} ({len(quotes)} quotes)")
        for q in quotes:
            text = q['quote']
            display = text[:80] + "..." if len(text) > 80 else text
            print(f"  - [{q['file']}:{q['section']}] {display}")


if __name__ == "__main__":
    main()
