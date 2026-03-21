#!/usr/bin/env python3
"""Automated DoD level assignment — classify stories as app or library level.

Scans story acceptance criteria for user-facing keywords and assigns
``dod_level: app`` (heavier verification) or ``dod_level: library``.

Usage: python assign_dod_level.py [--sprint N]
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from validate_config import (
    load_config, ConfigError, get_sprints_dir, detect_sprint, read_tf, write_tf,
)
# BH36-001: Use lock_sprint (not lock_story) for mutual exclusion with
# kanban.py and sync_tracking.py, which both hold lock_sprint.
from kanban import lock_sprint

_APP_KEYWORDS = re.compile(
    r'\b(visible|display|launch|screen|render|user|window|UI|app|'
    r'button|menu|dialog|notification|toast|animation|gesture)\b',
    re.IGNORECASE,
)


def classify_story(body_text: str, title: str = "") -> str:
    """Return 'app' if user-facing keywords found, else 'library'."""
    text = f"{title} {body_text}"
    if _APP_KEYWORDS.search(text):
        return "app"
    return "library"


def assign_levels(sprints_dir: str, sprint: int) -> dict[str, int]:
    """Assign DoD levels to all stories in a sprint. Returns counts."""
    stories_dir = Path(sprints_dir) / f"sprint-{sprint}" / "stories"
    if not stories_dir.is_dir():
        return {"app": 0, "library": 0}

    sprint_dir = Path(sprints_dir) / f"sprint-{sprint}"
    counts = {"app": 0, "library": 0}
    for md_file in sorted(stories_dir.glob("*.md")):
        tf = read_tf(md_file)
        level = classify_story(tf.body_text, tf.title)
        counts[level] += 1
        # Write level to body if not already present
        if "dod_level:" not in tf.body_text:
            with lock_sprint(sprint_dir):
                tf = read_tf(md_file)  # re-read under lock
                if "dod_level:" not in tf.body_text:
                    tf.body_text = tf.body_text.rstrip() + f"\n\ndod_level: {level}\n"
                    write_tf(tf)

    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description="Assign DoD levels")
    parser.add_argument("--sprint", type=int, default=None)
    args = parser.parse_args()

    try:
        config = load_config()
    except ConfigError:
        sys.exit(1)

    sprints_dir = get_sprints_dir(config)
    sprint = args.sprint if args.sprint is not None else detect_sprint(Path(sprints_dir))
    if sprint is None:
        print("Cannot detect sprint. Use --sprint N.", file=sys.stderr)
        sys.exit(1)

    counts = assign_levels(str(sprints_dir), sprint)
    print(f"Sprint {sprint}: {counts['app']} stories at app DoD, "
          f"{counts['library']} stories at library DoD")


if __name__ == "__main__":
    main()
