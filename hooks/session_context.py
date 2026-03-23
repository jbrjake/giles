#!/usr/bin/env python3
"""SessionStart context injection hook -- injects retro action items,
DoD additions, and high-severity open risks into the conversation.

Makes retro learnings part of the prompt context, not a file the
agent might skip reading.
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import _find_project_root, exit_ok, exit_warn, read_toml_key


# BH-009: TOML reading consolidated into _common.read_toml_key (PAT-003 fix)
# Legacy _read_toml_string kept as thin wrapper for backward compatibility
def _read_toml_string(text: str, section: str, key: str) -> str:
    """Read a string value from a TOML section. Delegates to shared reader."""
    result = read_toml_key(text, section, key)
    return result if isinstance(result, str) else ""


def _get_config_paths() -> dict[str, str]:
    """Read sprints_dir and team_dir from project.toml."""
    toml_path = _find_project_root() / "sprint-config" / "project.toml"
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

    # Find the highest-numbered sprint directory (strict sprint-N pattern)
    sprint_dirs = sorted(
        [d for d in sd.iterdir()
         if d.is_dir() and re.match(r'^sprint-\d+$', d.name)],
        key=lambda d: int(d.name.split("-")[1]),
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
                # Skip header row and separator rows (incl. alignment: :---, ---:, :---:)
                if cells and cells[0] not in ("Item", "---") and not re.match(r'^:?-+:?$', cells[0]):
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
        # BH30-004: Use word-boundary match to avoid "retroactive" false positives
        if re.search(r'\bretro\b', line.lower()) and (
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
        # BJ-006: Use raw split to preserve column positions; don't filter empties
        cells = [c.strip() for c in line.split("|")]
        # Pipe-delimited rows start/end with |, so cells[0] and cells[-1] are empty
        # cells[0]='' (leading |), cells[1]=ID, cells[2]=Title,
        # cells[3]=Severity, cells[4]=Status, cells[5]='' (trailing |)
        if len(cells) >= 5:
            severity = cells[3].lower() if len(cells) > 3 else ""
            status = cells[4].lower() if len(cells) > 4 else ""
            if severity in ("high", "critical") and status in ("open", "unresolved"):
                title = cells[2] if len(cells) > 2 else cells[1]
                risks.append(f"[{severity.upper()}] {title}")
    return risks


_MAX_ITEMS_PER_SECTION = 10


def format_context(action_items: list[str],
                   dod_additions: list[str],
                   risks: list[str]) -> str:
    """Format extracted context as a compact summary.

    BJ-010: Truncates each section to _MAX_ITEMS_PER_SECTION items
    to keep output bounded for large projects.
    """
    if not action_items and not dod_additions and not risks:
        return ""

    lines: list[str] = ["## Sprint Context (auto-injected by Giles)", ""]

    def _add_section(title: str, items: list[str]) -> None:
        if not items:
            return
        lines.append(f"### {title}")
        shown = items[:_MAX_ITEMS_PER_SECTION]
        for item in shown:
            lines.append(f"- {item}")
        remaining = len(items) - len(shown)
        if remaining > 0:
            lines.append(f"- ...and {remaining} more")
        lines.append("")

    _add_section("Retro Action Items (from last sprint)", action_items)
    _add_section("Retro-Driven DoD Additions", dod_additions)
    _add_section("Open Risks (high severity)", risks)

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Hook entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Inject sprint context at session start.

    Note: This hook intentionally does not read JSON from stdin.
    SessionStart hooks receive event metadata on stdin, but this hook
    only needs to read config files and output context to stdout.
    The additionalContext field is injected into Claude's context.
    """
    paths = _get_config_paths()
    if not paths:
        exit_ok()

    # BH27-002: Resolve all paths against project root -- TOML values are
    # relative to the project root, not CWD.
    root = _find_project_root()
    sprints_dir = paths.get("sprints_dir", "")
    if sprints_dir:
        sprints_dir = str(root / sprints_dir)
    config_dir = str(root / "sprint-config")

    action_items = extract_retro_action_items(sprints_dir) if sprints_dir else []
    dod_additions = extract_dod_retro_additions(config_dir)
    risks = extract_high_risks(config_dir)

    output = format_context(action_items, dod_additions, risks)
    if output:
        exit_warn(output)

    exit_ok()


if __name__ == "__main__":
    main()
