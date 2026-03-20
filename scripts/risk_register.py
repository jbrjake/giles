#!/usr/bin/env python3
"""Risk register management — add, resolve, list, and escalate risks.

Manages the risk register at ``sprint-config/risk-register.md``.

Usage:
    risk_register.py add_risk --title "..." --severity high|medium|low [--sprint N]
    risk_register.py resolve_risk --id R1 --resolution "..."
    risk_register.py list_open_risks
    risk_register.py escalate_overdue [--threshold 2]
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from validate_config import load_config, ConfigError


_REGISTER_PATH = Path("sprint-config/risk-register.md")
_TEMPLATE = (
    "# Risk Register\n\n"
    "Persistent tracking of risks across sprints. "
    "Reviewed at kickoff, updated at retro.\n\n"
    "| ID | Title | Severity | Status | Raised | Sprints Open | Resolution |\n"
    "|----|-------|----------|--------|--------|-------------|------------|\n"
)


def _read_register() -> str:
    """Read register or create from template."""
    if _REGISTER_PATH.is_file():
        return _REGISTER_PATH.read_text(encoding="utf-8")
    _REGISTER_PATH.parent.mkdir(parents=True, exist_ok=True)
    _REGISTER_PATH.write_text(_TEMPLATE, encoding="utf-8")
    return _TEMPLATE


def _next_id(text: str) -> str:
    """Find the next risk ID (R1, R2, etc.)."""
    ids = re.findall(r'\|\s*(R\d+)\s*\|', text)
    if not ids:
        return "R1"
    max_num = max(int(r[1:]) for r in ids)
    return f"R{max_num + 1}"


def _split_table_row(line: str, *, unescape: bool = True) -> list[str]:
    """Split a markdown table row on unescaped pipes.

    When *unescape* is True (default), \\| in cells is converted to |.
    Use unescape=False when modifying cells for write-back (to preserve escaping).
    """
    cells = [c.strip() for c in re.split(r'(?<!\\)\|', line)]
    # Remove leading/trailing empty strings from split
    if cells and cells[0] == "":
        cells = cells[1:]
    if cells and cells[-1] == "":
        cells = cells[:-1]
    if unescape:
        return [c.replace("\\|", "|") for c in cells]
    return cells


def _parse_rows(text: str) -> list[dict]:
    """Parse table rows into dicts."""
    rows: list[dict] = []
    for line in text.splitlines():
        if "|" not in line or line.strip().startswith("|--"):
            continue
        cells = _split_table_row(line)
        if len(cells) >= 6 and cells[0] not in ("ID", "---"):
            rows.append({
                "id": cells[0],
                "title": cells[1],
                "severity": cells[2],
                "status": cells[3],
                "raised": cells[4],
                "sprints_open": cells[5],
                "resolution": cells[6] if len(cells) > 6 else "",
            })
    return rows


def add_risk(title: str, severity: str, sprint: str = "current") -> str:
    """Add a risk to the register. Returns the assigned ID."""
    text = _read_register()
    rid = _next_id(text)
    title = title.replace("|", "\\|")
    row = f"| {rid} | {title} | {severity} | Open | Sprint {sprint} | 0 | |\n"
    text = text.rstrip() + "\n" + row
    _REGISTER_PATH.write_text(text, encoding="utf-8")
    return rid


def resolve_risk(risk_id: str, resolution: str) -> bool:
    """Resolve a risk by ID. Returns True if found."""
    text = _read_register()
    lines = text.splitlines()
    found = False
    for i, line in enumerate(lines):
        if "|" not in line or line.strip().startswith("|--"):
            continue
        cells = _split_table_row(line, unescape=False)
        if len(cells) >= 4 and cells[0] == risk_id and cells[3].lower() == "open":
            cells[3] = "Resolved"
            # Set resolution in the last column
            while len(cells) < 7:
                cells.append("")
            resolution_escaped = resolution.replace("|", "\\|")
            cells[6] = resolution_escaped
            lines[i] = "| " + " | ".join(cells) + " |"
            found = True
            break
    if found:
        _REGISTER_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return found


def list_open_risks() -> list[dict]:
    """Return all open risks."""
    text = _read_register()
    rows = _parse_rows(text)
    return [r for r in rows if r["status"].lower() == "open"]


def escalate_overdue(threshold: int = 2) -> list[dict]:
    """Return risks open longer than threshold sprints."""
    open_risks = list_open_risks()
    overdue: list[dict] = []
    for r in open_risks:
        try:
            sprints = int(r["sprints_open"])
        except (ValueError, KeyError):
            continue
        if sprints > threshold:
            overdue.append(r)
    return overdue


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Risk register management")
    sub = parser.add_subparsers(dest="command")

    add = sub.add_parser("add_risk")
    add.add_argument("--title", required=True)
    add.add_argument("--severity", required=True,
                     choices=["high", "medium", "low", "critical"])
    add.add_argument("--sprint", default="current")

    resolve = sub.add_parser("resolve_risk")
    resolve.add_argument("--id", required=True, dest="risk_id")
    resolve.add_argument("--resolution", required=True)

    sub.add_parser("list_open_risks")

    esc = sub.add_parser("escalate_overdue")
    esc.add_argument("--threshold", type=int, default=2)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(2)

    if args.command == "add_risk":
        rid = add_risk(args.title, args.severity, args.sprint)
        print(f"Added risk {rid}: {args.title}")

    elif args.command == "resolve_risk":
        if resolve_risk(args.risk_id, args.resolution):
            print(f"Resolved {args.risk_id}")
        else:
            print(f"Risk {args.risk_id} not found or already resolved",
                  file=sys.stderr)
            sys.exit(1)

    elif args.command == "list_open_risks":
        risks = list_open_risks()
        if not risks:
            print("No open risks")
        else:
            print("| ID | Title | Severity | Raised |")
            print("|----|-------|----------|--------|")
            for r in risks:
                print(f"| {r['id']} | {r['title']} | {r['severity']} | {r['raised']} |")

    elif args.command == "escalate_overdue":
        overdue = escalate_overdue(args.threshold)
        if overdue:
            for r in overdue:
                print(f"OVERDUE: {r['id']} — {r['title']} "
                      f"(open {r['sprints_open']} sprints, severity: {r['severity']})")
            sys.exit(1)
        else:
            print("No overdue risks")


if __name__ == "__main__":
    main()
