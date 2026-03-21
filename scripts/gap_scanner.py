#!/usr/bin/env python3
"""Gap scanner — detect sprints where no story touches integration entry points.

Reads ``[project] entry_points`` from project.toml and compares against
sprint stories' acceptance criteria and branch diffs.  Flags when stories
modify subsystems but no story touches the integration layer.

Exit codes:
    0 — no gap detected or skip (not configured)
    1 — gap detected
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from validate_config import (
    load_config, ConfigError, get_sprints_dir, detect_sprint, read_tf,
)


# User-facing keywords that suggest integration wiring is needed
_USER_FACING_KEYWORDS = re.compile(
    r'\b(visible|display|render|launch|screen|user|window|UI|app|'
    r'endpoint|route|handler|main)\b',
    re.IGNORECASE,
)


def get_entry_points(config: dict) -> list[str]:
    """Read entry_points from project config."""
    return config.get("project", {}).get("entry_points", [])


def scan_stories(sprints_dir: str, sprint: int) -> list[dict]:
    """Read all story tracking files for the given sprint."""
    stories_dir = Path(sprints_dir) / f"sprint-{sprint}" / "stories"
    if not stories_dir.is_dir():
        return []
    stories = []
    for md_file in sorted(stories_dir.glob("*.md")):
        tf = read_tf(md_file)
        stories.append({
            "story": tf.story,
            "title": tf.title,
            "branch": tf.branch,
            "body": tf.body_text,
        })
    return stories


def story_touches_entry_point(story: dict, entry_points: list[str]) -> str | None:
    """Check if a story's body or branch diff touches any entry point.

    Returns the entry point path if found, None otherwise.
    """
    body = story.get("body", "")
    branch = story.get("branch", "")

    # Check body text first (no subprocess needed)
    # BH29-003: Use word-boundary matching to avoid false positives
    # (e.g., entry point "main" should not match "domain")
    for ep in entry_points:
        if re.search(rf'\b{re.escape(ep)}\b', body):
            return ep

    # Check branch diff once (not per entry point)
    if branch:
        try:
            result = subprocess.run(
                ["git", "diff", "--name-only", f"HEAD...{branch}"],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0:
                # BH29-003: Match per-line to avoid cross-line false positives
                changed_lines = result.stdout.strip().splitlines()
                for ep in entry_points:
                    for changed_file in changed_lines:
                        if ep in changed_file:
                            return ep
        except Exception as exc:
            # BH29-003: Log warning instead of silently swallowing
            print(f"gap_scanner: git diff failed for branch {branch}: {exc}",
                  file=sys.stderr)
    return None


def has_user_facing_keywords(story: dict) -> bool:
    """Check if a story has user-facing keywords in title or body."""
    text = f"{story.get('title', '')} {story.get('body', '')}"
    return bool(_USER_FACING_KEYWORDS.search(text))


def scan_for_gaps(config: dict, sprint: int) -> tuple[str, int]:
    """Run the gap scan and return (report, exit_code)."""
    entry_points = get_entry_points(config)
    if not entry_points:
        return "SKIP: no entry_points configured in project.toml", 0

    sprints_dir = get_sprints_dir(config)
    stories = scan_stories(sprints_dir, sprint)
    if not stories:
        return f"SKIP: no stories found for sprint {sprint}", 0

    # Check which stories touch entry points
    touching: list[tuple[str, str]] = []  # (story_id, entry_point)
    for story in stories:
        ep = story_touches_entry_point(story, entry_points)
        if ep:
            touching.append((story["story"], ep))

    # Check for user-facing keywords without entry point coverage
    user_facing_count = sum(1 for s in stories if has_user_facing_keywords(s))

    if touching:
        lines = ["NO GAP:"]
        for story_id, ep in touching:
            lines.append(f"  story {story_id} touches entry point {ep}")
        return "\n".join(lines), 0

    # Gap detected
    ep_list = ", ".join(entry_points)
    lines = [
        f"GAP DETECTED: {len(stories)} stories modify subsystems, "
        f"0 stories touch entry points [{ep_list}]",
    ]
    if user_facing_count > 0:
        lines.append(
            f"  {user_facing_count} stories have user-facing language "
            f"but none touch integration entry points"
        )
    return "\n".join(lines), 1


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Scan for integration gaps")
    parser.add_argument("--config", default="sprint-config/project.toml")
    parser.add_argument("--sprint", type=int, default=None)
    args = parser.parse_args()

    config_dir = str(Path(args.config).parent)
    try:
        config = load_config(config_dir)
    except ConfigError:
        sys.exit(1)

    sprints_dir = get_sprints_dir(config)
    sprint = args.sprint if args.sprint is not None else detect_sprint(Path(sprints_dir))
    if sprint is None:
        print("Cannot detect sprint. Use --sprint N.", file=sys.stderr)
        sys.exit(1)

    report, exit_code = scan_for_gaps(config, sprint)
    print(report)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
