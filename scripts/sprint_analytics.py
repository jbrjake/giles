#!/usr/bin/env python3
"""Compute sprint metrics from GitHub data and local sprint docs.

Usage: python sprint_analytics.py [sprint-number]

Config-driven: reads repo, sprints_dir, team_dir from project.toml via
validate_config.load_config(). Queries GitHub for milestone, issue, and
PR data. Outputs a markdown report suitable for appending to analytics.md.

Exit: 0 = success, 1 = error, 2 = usage error.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

# -- Import shared config ----------------------------------------------------
sys.path.insert(0, str(Path(__file__).resolve().parent))
from validate_config import (
    load_config, extract_sp, gh, gh_json,
    detect_sprint, find_milestone, warn_if_at_limit,
)


# -- Metric computation -----------------------------------------------------


def extract_persona(issue: dict) -> str | None:
    """Extract persona name from labels (persona:name format)."""
    for label in issue.get("labels", []):
        name = label if isinstance(label, str) else label.get("name", "")
        if name.startswith("persona:"):
            return name[8:]
    return None


def compute_velocity(
    milestone_title: str,
) -> dict:
    """Compute planned vs delivered story points for a milestone."""
    issues = gh_json([
        "issue", "list", "--milestone", milestone_title,
        "--state", "all",
        "--json", "state,labels,body,title",
        "--limit", "500",
    ])
    if not isinstance(issues, list):
        issues = []
    warn_if_at_limit(issues)

    planned_sp = 0
    delivered_sp = 0
    story_count = 0
    delivered_count = 0

    for iss in issues:
        sp = extract_sp(iss)
        planned_sp += sp
        story_count += 1
        if iss.get("state") == "closed":
            delivered_sp += sp
            delivered_count += 1

    pct = round(delivered_sp / planned_sp * 100) if planned_sp else 0

    return {
        "planned_sp": planned_sp,
        "delivered_sp": delivered_sp,
        "percentage": pct,
        "story_count": story_count,
        "delivered_count": delivered_count,
    }


def compute_review_rounds(
    repo: str, milestone_title: str,
) -> dict:
    """Count review events per PR for stories in this milestone."""
    prs = gh_json([
        "pr", "list", "--state", "all",
        "--json", "number,title,labels,milestone,reviews",
        "--limit", "500",
    ])
    if not isinstance(prs, list):
        prs = []
    warn_if_at_limit(prs)

    # Filter to PRs for this milestone
    sprint_prs = []
    for pr in prs:
        ms = pr.get("milestone") or {}
        if ms.get("title") == milestone_title:
            sprint_prs.append(pr)

    if not sprint_prs:
        return {"avg_rounds": 0.0, "max_rounds": 0, "max_story": "", "pr_count": 0}

    rounds_per_pr: list[tuple[str, int]] = []
    for pr in sprint_prs:
        reviews = pr.get("reviews") or []
        # Count review rounds: each CHANGES_REQUESTED or APPROVED counts as a round
        round_count = sum(
            1 for r in reviews
            if r.get("state") in ("CHANGES_REQUESTED", "APPROVED")
        )
        # At minimum 1 round if there are any reviews
        if reviews and round_count == 0:
            round_count = 1
        title = pr.get("title", "?")
        rounds_per_pr.append((title, round_count))

    total_rounds = sum(r for _, r in rounds_per_pr)
    avg = total_rounds / len(rounds_per_pr) if rounds_per_pr else 0.0
    max_story, max_rounds = max(rounds_per_pr, key=lambda x: x[1])

    return {
        "avg_rounds": round(avg, 1),
        "max_rounds": max_rounds,
        "max_story": max_story,
        "pr_count": len(rounds_per_pr),
    }


def compute_workload(
    milestone_title: str,
) -> dict[str, int]:
    """Count stories per persona from issue labels."""
    issues = gh_json([
        "issue", "list", "--milestone", milestone_title,
        "--state", "all",
        "--json", "labels",
        "--limit", "500",
    ])
    if not isinstance(issues, list):
        issues = []
    warn_if_at_limit(issues, 500)

    persona_counts: dict[str, int] = {}
    for iss in issues:
        persona = extract_persona(iss)
        if persona:
            persona_counts[persona] = persona_counts.get(persona, 0) + 1
    return persona_counts


# -- Report formatting -------------------------------------------------------

def format_report(
    sprint_num: int,
    sprint_theme: str,
    velocity: dict,
    review: dict,
    workload: dict[str, int],
) -> str:
    """Produce a markdown analytics entry for one sprint."""
    lines = [
        f"### Sprint {sprint_num} — {sprint_theme}",
        f"**Velocity:** {velocity['delivered_sp']}/{velocity['planned_sp']}"
        f" SP ({velocity['percentage']}%)",
    ]

    if review["pr_count"] > 0:
        lines.append(
            f"**Review rounds:** avg {review['avg_rounds']} per story"
            f" (highest: {review['max_story']}, {review['max_rounds']} rounds)"
        )
    else:
        lines.append("**Review rounds:** no PR data available")

    if workload:
        parts = [f"{name}: {count}" for name, count in sorted(workload.items())]
        lines.append(f"**Workload:** {', '.join(parts)}")
    else:
        lines.append("**Workload:** no persona data available")

    lines.append("**Giles notes:** (to be filled by Giles during retro)")
    lines.append("")
    return "\n".join(lines)


# -- Main --------------------------------------------------------------------

def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] in ("-h", "--help"):
        print(__doc__.strip())
        sys.exit(0)

    config = load_config()
    repo = config.get("project", {}).get("repo", "")
    sprints_dir = Path(
        config.get("paths", {}).get("sprints_dir", "sprints"),
    )

    sprint_num: int | None = None
    if len(sys.argv) >= 2:
        if sys.argv[1].isdigit():
            sprint_num = int(sys.argv[1])
        else:
            print(
                "Usage: python sprint_analytics.py [sprint-number]",
                file=sys.stderr,
            )
            sys.exit(2)
    else:
        sprint_num = detect_sprint(sprints_dir)

    if sprint_num is None:
        print(
            "Cannot determine sprint. Provide argument or ensure "
            "SPRINT-STATUS.md exists.",
            file=sys.stderr,
        )
        sys.exit(2)

    if not repo:
        print("Error: project.repo not set in project.toml", file=sys.stderr)
        sys.exit(1)

    # Find milestone
    ms = find_milestone(sprint_num)
    if ms is None:
        print(f"No milestone found for Sprint {sprint_num}", file=sys.stderr)
        sys.exit(1)
    ms_title = ms["title"]

    # Read sprint theme from kickoff doc if available
    sprint_theme = "Untitled"
    kickoff = sprints_dir / f"sprint-{sprint_num}" / "kickoff.md"
    if kickoff.exists():
        text = kickoff.read_text(encoding="utf-8")
        m = re.search(r"Sprint Theme:\s*(.+)", text)
        if m:
            sprint_theme = m.group(1).strip()

    # Compute metrics
    velocity = compute_velocity(ms_title)
    review = compute_review_rounds(repo, ms_title)
    workload = compute_workload(ms_title)

    # Format and output
    report = format_report(sprint_num, sprint_theme, velocity, review, workload)
    print(report)

    # Append to analytics file if sprints_dir exists (idempotent)
    analytics_path = sprints_dir / "analytics.md"
    if sprints_dir.is_dir():
        if not analytics_path.exists():
            analytics_path.write_text(
                "# Sprint Analytics\n\n"
                "Computed by sprint_analytics.py. "
                "Giles adds qualitative commentary during retro.\n\n---\n\n",
                encoding="utf-8",
            )
        # Dedup: skip if this sprint already has an entry (BH-016)
        existing = analytics_path.read_text(encoding="utf-8")
        header = f"### Sprint {sprint_num}"
        if header in existing:
            print(f"Sprint {sprint_num} already in {analytics_path} (skipping)")
        else:
            with open(analytics_path, "a", encoding="utf-8") as f:
                f.write(report + "\n---\n\n")
            print(f"Appended to {analytics_path}")


if __name__ == "__main__":
    main()
