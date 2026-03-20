#!/usr/bin/env python3
"""SessionStart context injection hook — injects retro action items,
DoD additions, and high-severity open risks into the conversation.

Makes retro learnings part of the prompt context, not a file the
agent might skip reading.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Config helpers (lightweight, no validate_config import)
# ---------------------------------------------------------------------------

def _read_toml_string(text: str, section: str, key: str) -> str:
    """Read a string value from a TOML section."""
    in_section = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("["):
            in_section = stripped == f"[{section}]"
            continue
        if not in_section:
            continue
        m = re.match(rf'{key}\s*=\s*"([^"]*)"', stripped)
        if m:
            return m.group(1)
    return ""


def _get_config_paths() -> dict[str, str]:
    """Read sprints_dir and team_dir from project.toml."""
    toml_path = Path("sprint-config/project.toml")
    if not toml_path.is_file():
        return {}
    text = toml_path.read_text(encoding="utf-8")
    return {
        "sprints_dir": _read_toml_string(text, "paths", "sprints_dir"),
        "team_dir": _read_toml_string(text, "paths", "team_dir"),
    }


# ---------------------------------------------------------------------------
# Extraction functions
# ---------------------------------------------------------------------------

def extract_retro_action_items(sprints_dir: str) -> list[str]:
    """Extract action items from the most recent retro.md."""
    sd = Path(sprints_dir)
    if not sd.is_dir():
        return []

    # Find the highest-numbered sprint directory
    sprint_dirs = sorted(
        [d for d in sd.iterdir() if d.is_dir() and d.name.startswith("sprint-")],
        key=lambda d: int(re.search(r'\d+', d.name).group()) if re.search(r'\d+', d.name) else 0,
        reverse=True,
    )

    for sprint_dir in sprint_dirs:
        retro_path = sprint_dir / "retro.md"
        if retro_path.is_file():
            text = retro_path.read_text(encoding="utf-8")
            return _parse_action_items(text)

    return []


def _parse_action_items(retro_text: str) -> list[str]:
    """Parse action items table from retro.md content."""
    items: list[str] = []
    in_action_section = False
    for line in retro_text.splitlines():
        if "Action Items" in line and line.startswith("#"):
            in_action_section = True
            continue
        if in_action_section:
            if line.startswith("#"):
                break  # next section
            # Parse table rows: | Item | Owner | Due |
            if "|" in line and not line.strip().startswith("|--"):
                cells = [c.strip() for c in line.split("|")]
                cells = [c for c in cells if c]
                if cells and cells[0] not in ("Item", "---"):
                    items.append(cells[0])
    return items


def extract_dod_retro_additions(config_dir: str = "sprint-config") -> list[str]:
    """Extract retro-driven additions from definition-of-done.md."""
    dod_path = Path(config_dir) / "definition-of-done.md"
    if not dod_path.is_file():
        return []
    text = dod_path.read_text(encoding="utf-8")
    additions: list[str] = []
    for line in text.splitlines():
        # Look for items marked as retro-driven
        if "retro" in line.lower() and (
            line.strip().startswith("-") or line.strip().startswith("*")
        ):
            additions.append(line.strip().lstrip("-* "))
    return additions


def extract_high_risks(config_dir: str = "sprint-config") -> list[str]:
    """Extract high-severity open risks from risk-register.md."""
    risk_path = Path(config_dir) / "risk-register.md"
    if not risk_path.is_file():
        return []
    text = risk_path.read_text(encoding="utf-8")
    risks: list[str] = []
    for line in text.splitlines():
        if "|" not in line or line.strip().startswith("|--"):
            continue
        cells = [c.strip() for c in line.split("|")]
        cells = [c for c in cells if c]
        if len(cells) >= 4:
            severity = cells[2].lower() if len(cells) > 2 else ""
            status = cells[3].lower() if len(cells) > 3 else ""
            if severity in ("high", "critical") and status in ("open", "unresolved"):
                title = cells[1] if len(cells) > 1 else cells[0]
                risks.append(f"[{severity.upper()}] {title}")
    return risks


def format_context(action_items: list[str],
                   dod_additions: list[str],
                   risks: list[str]) -> str:
    """Format extracted context as a compact summary (<50 lines target)."""
    if not action_items and not dod_additions and not risks:
        return ""

    lines: list[str] = ["## Sprint Context (auto-injected by Giles)", ""]

    if action_items:
        lines.append("### Retro Action Items (from last sprint)")
        for item in action_items:
            lines.append(f"- {item}")
        lines.append("")

    if dod_additions:
        lines.append("### Retro-Driven DoD Additions")
        for item in dod_additions:
            lines.append(f"- {item}")
        lines.append("")

    if risks:
        lines.append("### Open Risks (high severity)")
        for risk in risks:
            lines.append(f"- {risk}")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Hook entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Inject sprint context at session start."""
    paths = _get_config_paths()
    if not paths:
        sys.exit(0)

    sprints_dir = paths.get("sprints_dir", "")
    action_items = extract_retro_action_items(sprints_dir) if sprints_dir else []
    dod_additions = extract_dod_retro_additions()
    risks = extract_high_risks()

    output = format_context(action_items, dod_additions, risks)
    if output:
        print(output)

    sys.exit(0)


if __name__ == "__main__":
    main()
