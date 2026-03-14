#!/usr/bin/env python3
"""Reconcile local story tracking files with GitHub state.

Usage: python sync_tracking.py <sprint-number>

Config-driven: reads sprints_dir, team_dir, and repo from project.toml
via validate_config.load_config(). No hardcoded project-specific values.

GitHub is authoritative. Local tracking files are updated to match.
Missing files are created; stale statuses are corrected.
Idempotent -- prints "Everything in sync" when nothing to fix.
"""
from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

# -- Import shared config ----------------------------------------------------
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent / "scripts"))
from validate_config import (
    load_config, gh, extract_story_id, get_sprints_dir, kanban_from_labels,
    find_milestone, warn_if_at_limit, list_milestone_issues,
    KANBAN_STATES,
)


def find_milestone_title(sprint_num: int) -> str | None:
    ms = find_milestone(sprint_num)
    return ms["title"] if ms else None


def _fetch_all_prs() -> list[dict]:
    """Fetch all PRs once for branch-based linkage (cached per sync run)."""
    try:
        raw = gh([
            "pr", "list", "--state", "all",
            "--json", "number,state,headRefName,mergedAt",
            "--limit", "500",
        ])
        return json.loads(raw) if raw else []
    except (RuntimeError, json.JSONDecodeError):
        return []


def get_linked_pr(
    issue_num: int, story_id: str, all_prs: list[dict] | None = None,
) -> dict | None:
    """Find PR linked to issue via timeline API, fallback to branch name.

    The fallback search uses the pre-fetched all_prs list to avoid
    per-issue API calls. Pass all_prs from _fetch_all_prs().
    """
    try:
        raw = gh([
            "api",
            f"repos/{{owner}}/{{repo}}/issues/{issue_num}/timeline",
            "--paginate", "--jq",
            '[.[] | select(.source?.issue?.pull_request?) '
            '| .source.issue] | first',
        ])
        if raw and raw != "null":
            d = json.loads(raw)
            return {
                "number": d.get("number"),
                "state": d.get("state"),
                "merged": (
                    d.get("pull_request", {}).get("merged_at") is not None
                ),
            }
    except (RuntimeError, json.JSONDecodeError):
        pass
    # Fallback: search pre-fetched PRs by branch name
    for pr in (all_prs or []):
        branch = pr.get("headRefName", "")
        if re.search(re.escape(story_id), branch, re.IGNORECASE):
            return {
                "number": pr["number"],
                "state": (
                    "merged"
                    if pr.get("mergedAt")
                    else pr["state"]
                ),
                "merged": pr.get("mergedAt") is not None,
            }
    return None


def slug_from_title(title: str) -> str:
    slug = re.sub(
        r"\s+", "-",
        re.sub(r"[^a-zA-Z0-9\s-]", "", title).strip(),
    ).lower()
    return slug if slug else "untitled"


def _parse_closed(iso: str) -> str:
    if not iso:
        return ""
    try:
        return datetime.fromisoformat(
            iso.replace("Z", "+00:00")
        ).strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        return ""


# -- Tracking file dataclass and I/O ----------------------------------------

@dataclass
class TF:
    path: Path
    story: str = ""
    title: str = ""
    sprint: int = 0
    implementer: str = ""
    reviewer: str = ""
    status: str = "todo"
    branch: str = ""
    pr_number: str = ""
    issue_number: str = ""
    started: str = ""
    completed: str = ""
    body_text: str = ""


def read_tf(path: Path) -> TF:
    tf = TF(path=path)
    content = path.read_text(encoding="utf-8")
    fm = re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)", content, re.DOTALL)
    if not fm:
        tf.body_text = content
        return tf
    raw, tf.body_text = fm.group(1), fm.group(2)

    def v(k: str) -> str:
        m = re.search(rf"^{k}:\s*(.+)", raw, re.MULTILINE)
        return m.group(1).strip() if m else ""

    tf.story, tf.title = v("story"), v("title")
    tf.sprint = int(v("sprint") or "0")
    tf.implementer, tf.reviewer = v("implementer"), v("reviewer")
    tf.status = v("status") or "todo"
    tf.branch, tf.pr_number = v("branch"), v("pr_number")
    tf.issue_number = v("issue_number")
    tf.started, tf.completed = v("started"), v("completed")
    return tf


def write_tf(tf: TF) -> None:
    lines = [
        "---",
        f"story: {tf.story}",
        f"title: {tf.title}",
        f"sprint: {tf.sprint}",
        f"implementer: {tf.implementer}",
        f"reviewer: {tf.reviewer}",
        f"status: {tf.status}",
        f"branch: {tf.branch}",
        f"pr_number: {tf.pr_number}",
        f"issue_number: {tf.issue_number}",
        f"started: {tf.started}",
        f"completed: {tf.completed}",
        "---",
    ]
    if tf.body_text:
        lines += ["", tf.body_text.strip()]
    lines.append("")
    tf.path.parent.mkdir(parents=True, exist_ok=True)
    tf.path.write_text("\n".join(lines), encoding="utf-8")


# -- Sync logic --------------------------------------------------------------

def sync_one(
    tf: TF, issue: dict, pr: dict | None, sprint: int
) -> list[str]:
    """Update tracking file to match GitHub. Returns change descriptions."""
    changes: list[str] = []
    gh_status = kanban_from_labels(issue)

    if issue["state"] == "closed" and tf.status != "done":
        changes.append(
            f"{tf.story}: status {tf.status} -> done (issue closed)"
        )
        tf.status = "done"
    elif gh_status != tf.status and gh_status in KANBAN_STATES:
        changes.append(
            f"{tf.story}: status {tf.status} -> {gh_status} (label sync)"
        )
        tf.status = gh_status

    if tf.status == "done" and not tf.completed:
        d = _parse_closed(issue.get("closedAt", ""))
        if d:
            tf.completed = d
            changes.append(f"{tf.story}: set completed = {d}")

    if pr:
        gh_pr = str(pr["number"])
        if tf.pr_number != gh_pr:
            changes.append(
                f"{tf.story}: pr_number "
                f"{tf.pr_number or '(empty)'} -> {gh_pr}"
            )
            tf.pr_number = gh_pr

    gh_issue = str(issue["number"])
    if tf.issue_number != gh_issue:
        changes.append(
            f"{tf.story}: issue_number "
            f"{tf.issue_number or '(empty)'} -> {gh_issue}"
        )
        tf.issue_number = gh_issue

    if tf.sprint != sprint:
        changes.append(f"{tf.story}: sprint {tf.sprint} -> {sprint}")
        tf.sprint = sprint
    return changes


def create_from_issue(
    issue: dict, sprint: int, d: Path, pr: dict | None
) -> tuple[TF, list[str]]:
    sid = extract_story_id(issue["title"])
    slug = slug_from_title(issue["title"])
    status = kanban_from_labels(issue)
    short = (
        issue["title"].split(":", 1)[-1].strip()
        if ":" in issue["title"]
        else issue["title"]
    )
    tf = TF(
        path=d / f"{slug}.md",
        story=sid,
        title=short,
        sprint=sprint,
        status=status,
        issue_number=str(issue["number"]),
        pr_number=str(pr["number"]) if pr else "",
        branch=f"sprint-{sprint}/{slug}",
    )
    if tf.status == "done":
        tf.completed = _parse_closed(issue.get("closedAt", ""))
    return tf, [f"{sid}: created tracking file {slug}.md (status={status})"]


# -- Main --------------------------------------------------------------------

def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] in ("-h", "--help"):
        print(__doc__.strip())
        sys.exit(0)
    if len(sys.argv) != 2 or not sys.argv[1].isdigit():
        print(
            "Usage: python sync_tracking.py <sprint-number>",
            file=sys.stderr,
        )
        sys.exit(2)

    sprint = int(sys.argv[1])

    config = load_config()
    sprints_dir = get_sprints_dir(config)

    stories_dir = sprints_dir / f"sprint-{sprint}" / "stories"
    stories_dir.mkdir(parents=True, exist_ok=True)

    mt = find_milestone_title(sprint)
    if not mt:
        print(f"No GitHub milestone for Sprint {sprint}", file=sys.stderr)
        sys.exit(1)

    issues = list_milestone_issues(mt)
    if not issues:
        print(f"No issues in milestone '{mt}'")
        return

    existing: dict[str, TF] = {}
    for p in stories_dir.glob("*.md"):
        tf = read_tf(p)
        if tf.story:
            existing[tf.story] = tf

    all_prs = _fetch_all_prs()
    all_changes: list[str] = []
    for issue in issues:
        sid = extract_story_id(issue["title"])
        pr = get_linked_pr(issue["number"], story_id=sid, all_prs=all_prs)
        if sid in existing:
            changes = sync_one(existing[sid], issue, pr, sprint)
            if changes:
                write_tf(existing[sid])
                all_changes.extend(changes)
        else:
            tf, changes = create_from_issue(
                issue, sprint, stories_dir, pr
            )
            write_tf(tf)
            all_changes.extend(changes)

    if all_changes:
        print(f"Sync complete -- {len(all_changes)} change(s):")
        for c in all_changes:
            print(f"  {c}")
    else:
        print("Everything in sync")


if __name__ == "__main__":
    main()
