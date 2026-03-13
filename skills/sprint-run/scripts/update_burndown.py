#!/usr/bin/env python3
"""Update burndown data from GitHub milestone state.

Usage: python update_burndown.py <sprint-number>

Config-driven: reads sprints_dir, repo, and other paths from project.toml
via validate_config.load_config(). No hardcoded project-specific values.

Queries GitHub milestone and issues, calculates SP progress, and writes
burndown.md plus SPRINT-STATUS.md. Idempotent -- safe to run repeatedly.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# -- Import shared config ----------------------------------------------------
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent / "scripts"))
from validate_config import load_config, extract_sp


def gh(args: list[str]) -> str:
    """Run a gh CLI command and return stdout."""
    result = subprocess.run(
        ["gh", *args], capture_output=True, text=True, timeout=30
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"gh {' '.join(args)} failed: {result.stderr.strip()}"
        )
    return result.stdout.strip()


def find_milestone(sprint_num: int) -> dict | None:
    raw = gh(["api", "repos/{owner}/{repo}/milestones", "--paginate"])
    for ms in (json.loads(raw) if raw else []):
        if re.match(rf"^Sprint {sprint_num}\b", ms.get("title", "")):
            return ms
    return None


def list_milestone_issues(milestone_title: str) -> list[dict]:
    raw = gh([
        "issue", "list", "--milestone", milestone_title, "--state", "all",
        "--json", "number,title,state,labels,closedAt,body", "--limit", "200",
    ])
    return json.loads(raw) if raw else []


def extract_story_id(title: str) -> str:
    m = re.match(r"([A-Z]+-\d+)", title)
    return m.group(1) if m else title.split(":")[0].strip()


def kanban_status(issue: dict) -> str:
    """Derive kanban status from labels."""
    for label in issue.get("labels", []):
        name = label if isinstance(label, str) else label.get("name", "")
        if name.startswith("kanban:"):
            return name.split(":", 1)[1]
    return "done" if issue.get("state") == "closed" else "todo"


def closed_date(issue: dict) -> str:
    """Return the date an issue was closed, or a dash."""
    raw = issue.get("closedAt")
    if not raw:
        return "\u2014"
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        return "\u2014"


# -- Output writers ----------------------------------------------------------

def write_burndown(
    sprint_num: int, rows: list[dict], now: datetime, sprints_dir: Path
) -> Path:
    """Write sprints/sprint-{N}/burndown.md."""
    sprint_dir = sprints_dir / f"sprint-{sprint_num}"
    sprint_dir.mkdir(parents=True, exist_ok=True)
    path = sprint_dir / "burndown.md"

    total_sp = sum(r["sp"] for r in rows)
    done_sp = sum(r["sp"] for r in rows if r["status"] == "done")
    remaining_sp = total_sp - done_sp
    pct = round(done_sp / total_sp * 100) if total_sp else 0

    lines: list[str] = [
        f"# Sprint {sprint_num} Burndown",
        "",
        f"**Updated:** {now.strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        "| Story | SP | Status | Completed |",
        "|-------|-----|--------|-----------|",
    ]
    for r in sorted(rows, key=lambda r: r["story_id"]):
        lines.append(
            f"| {r['story_id']}: {r['short_title']} "
            f"| {r['sp']} | {r['status']} | {r['closed']} |"
        )
    lines += [
        "",
        "## Summary",
        f"- Planned: {total_sp} SP",
        f"- Completed: {done_sp} SP",
        f"- Remaining: {remaining_sp} SP",
        f"- Progress: {pct}%",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def update_sprint_status(
    sprint_num: int, rows: list[dict], sprints_dir: Path
) -> None:
    """Patch the Active Stories table in SPRINT-STATUS.md."""
    status_file = sprints_dir / "SPRINT-STATUS.md"
    if not status_file.exists():
        return

    text = status_file.read_text(encoding="utf-8")

    # Build replacement table
    header = (
        "## Active Stories\n\n"
        "| Story | Status | Assignee | PR |\n"
        "|-------|--------|----------|----|"
    )
    table_lines = [header]
    for r in sorted(rows, key=lambda r: r["story_id"]):
        assignee = r.get("assignee", "\u2014")
        pr = r.get("pr", "\u2014")
        table_lines.append(
            f"| {r['story_id']}: {r['short_title']} "
            f"| {r['status']} | {assignee} | {pr} |"
        )

    new_table = "\n".join(table_lines) + "\n"

    # Replace existing Active Stories section
    pattern = r"## Active Stories.*?(?=\n## |\Z)"
    if re.search(pattern, text, re.DOTALL):
        text = re.sub(pattern, new_table.rstrip(), text, flags=re.DOTALL)
    else:
        text = text.rstrip() + "\n\n" + new_table

    status_file.write_text(text, encoding="utf-8")


# -- Persona / PR helpers ---------------------------------------------------

def load_tracking_metadata(
    sprint_num: int, sprints_dir: Path
) -> dict[str, dict]:
    """Read YAML-ish frontmatter from story tracking files for assignee/PR."""
    stories_dir = sprints_dir / f"sprint-{sprint_num}" / "stories"
    meta: dict[str, dict] = {}
    if not stories_dir.is_dir():
        return meta
    for path in stories_dir.glob("*.md"):
        content = path.read_text(encoding="utf-8")
        fm_match = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
        if not fm_match:
            continue
        fm = fm_match.group(1)
        story_id = _fm_val(fm, "story")
        if story_id:
            meta[story_id] = {
                "assignee": _fm_val(fm, "implementer") or "\u2014",
                "pr": _fm_val(fm, "pr_number") or "\u2014",
            }
    return meta


def _fm_val(frontmatter: str, key: str) -> str | None:
    m = re.search(rf"^{key}:\s*(.+)", frontmatter, re.MULTILINE)
    return m.group(1).strip() if m else None


# -- Main --------------------------------------------------------------------

def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] in ("-h", "--help"):
        print(__doc__.strip())
        sys.exit(0)
    if len(sys.argv) != 2 or not sys.argv[1].isdigit():
        print(
            "Usage: python update_burndown.py <sprint-number>",
            file=sys.stderr,
        )
        sys.exit(2)

    sprint_num = int(sys.argv[1])

    config = load_config()
    sprints_dir = Path(
        config.get("paths", {}).get("sprints_dir", "sprints")
    )

    now = datetime.now(timezone.utc)

    milestone = find_milestone(sprint_num)
    if milestone is None:
        print(
            f"No GitHub milestone found for Sprint {sprint_num}",
            file=sys.stderr,
        )
        sys.exit(1)

    issues = list_milestone_issues(milestone["title"])
    if not issues:
        print(
            f"No issues found in milestone '{milestone['title']}'",
            file=sys.stderr,
        )
        sys.exit(1)

    tracking = load_tracking_metadata(sprint_num, sprints_dir)

    rows: list[dict] = []
    for issue in issues:
        sid = extract_story_id(issue["title"])
        short_title = (
            issue["title"].split(":", 1)[-1].strip()
            if ":" in issue["title"]
            else issue["title"]
        )
        sp = extract_sp(issue)
        status = kanban_status(issue)
        t = tracking.get(sid, {})
        rows.append({
            "story_id": sid,
            "short_title": short_title,
            "sp": sp,
            "status": status,
            "closed": closed_date(issue),
            "assignee": t.get("assignee", "\u2014"),
            "pr": t.get("pr", "\u2014"),
        })

    burndown_path = write_burndown(sprint_num, rows, now, sprints_dir)
    update_sprint_status(sprint_num, rows, sprints_dir)

    total_sp = sum(r["sp"] for r in rows)
    done_sp = sum(r["sp"] for r in rows if r["status"] == "done")
    pct = round(done_sp / total_sp * 100) if total_sp else 0
    print(
        f"Sprint {sprint_num}: {done_sp}/{total_sp} SP ({pct}%) "
        f"-- burndown written to {burndown_path}"
    )


if __name__ == "__main__":
    main()
