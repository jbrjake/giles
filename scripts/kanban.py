#!/usr/bin/env python3
"""Kanban state machine for sprint story management.

Usage:
    kanban.py transition <story-id> <target-state> [--sprint N]
    kanban.py assign <story-id> --implementer <name> [--reviewer <name>] [--sprint N]
    kanban.py sync [--sprint N]
    kanban.py status [--sprint N]

Source of truth: local tracking files (sprint-{N}/stories/*.md).
GitHub is a downstream reflection synced on every mutation.
"""
from __future__ import annotations

import os
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Generator, Iterator

try:
    import fcntl
except ImportError:
    sys.exit(
        "kanban.py requires POSIX file locking (fcntl). "
        "Run on macOS, Linux, or WSL."
    )

sys.path.insert(0, str(Path(__file__).resolve().parent))
from validate_config import (
    load_config, ConfigError, TF, read_tf, write_tf,
    get_sprints_dir, detect_sprint, extract_story_id,
    kanban_from_labels, find_milestone, list_milestone_issues,
    gh, gh_json, short_title, slug_from_title,
    KANBAN_STATES, _yaml_safe,
)


# ---------------------------------------------------------------------------
# Transition table
# §kanban.TRANSITIONS
# ---------------------------------------------------------------------------

TRANSITIONS: dict[str, list[str]] = {
    "todo":        ["design"],
    "design":      ["dev"],
    "dev":         ["review"],
    "review":      ["dev", "integration"],
    "integration": ["done"],
    "done":        [],
}


# ---------------------------------------------------------------------------
# Transition validation
# §kanban.validate_transition
# ---------------------------------------------------------------------------

def validate_transition(current: str, target: str) -> str | None:
    """Check whether a state transition is legal.

    Returns None if the transition is allowed, or an error message string if
    it is not.  Does not touch the filesystem.
    """
    if target not in KANBAN_STATES:
        return f"Unknown target state {target!r}. Valid states: {sorted(KANBAN_STATES)}"
    if current not in KANBAN_STATES:
        return f"Unknown current state {current!r}. Valid states: {sorted(KANBAN_STATES)}"
    if current == target:
        return f"Story is already in state {current!r}; no transition needed."
    allowed = TRANSITIONS.get(current, [])
    if target not in allowed:
        return (
            f"Cannot transition {current!r} → {target!r}. "
            f"Allowed next states from {current!r}: {allowed or ['(none)']}"
        )
    return None


# ---------------------------------------------------------------------------
# Precondition checks
# §kanban.check_preconditions
# ---------------------------------------------------------------------------

def check_preconditions(tf: TF, target: str) -> str | None:
    """Verify that the tracking file satisfies entry conditions for *target*.

    Returns None if all preconditions are met, or an error message string if
    one or more are not.  Does not touch the filesystem or GitHub.

    Precondition rules
    ------------------
    design      — tf.implementer must be set
    dev         — tf.branch and tf.pr_number must both be set
    review      — tf.implementer and tf.reviewer must be set
    done        — tf.pr_number must be set
    todo / integration — no preconditions
    """
    if target == "design":
        if not tf.implementer:
            return "Precondition failed: 'implementer' must be set before entering design."
    elif target == "dev":
        missing = []
        if not tf.branch:
            missing.append("branch")
        if not tf.pr_number:
            missing.append("pr_number")
        if missing:
            return (
                f"Precondition failed: {', '.join(missing)} must be set before entering dev."
            )
    elif target == "review":
        missing = []
        if not tf.implementer:
            missing.append("implementer")
        if not tf.reviewer:
            missing.append("reviewer")
        if missing:
            return (
                f"Precondition failed: {', '.join(missing)} must be set before entering review."
            )
    elif target == "done":
        if not tf.pr_number:
            return "Precondition failed: 'pr_number' must be set before entering done."
    return None


# ---------------------------------------------------------------------------
# Atomic file write
# §kanban.atomic_write_tf
# ---------------------------------------------------------------------------

def atomic_write_tf(tf: TF) -> None:
    """Write a tracking file atomically using a temp-then-rename strategy.

    Creates parent directories as needed.  The destination file either
    contains the complete new content or the old content; there is no
    observable window with a partial write.
    """
    tf.path.parent.mkdir(parents=True, exist_ok=True)
    tmp = tf.path.with_suffix(".tmp")
    original_path = tf.path
    tf.path = tmp
    try:
        write_tf(tf)
    finally:
        tf.path = original_path
    os.rename(str(tmp), str(original_path))


# ---------------------------------------------------------------------------
# File locking
# §kanban.lock_story
# §kanban.lock_sprint
# ---------------------------------------------------------------------------

@contextmanager
def lock_story(tracking_path: Path) -> Generator[None, None, None]:
    """Acquire an exclusive POSIX lock on *tracking_path* for the duration of
    the ``with`` block.

    The file must already exist.  If concurrent processes race, they block
    until the lock is released.
    """
    with open(tracking_path, "r", encoding="utf-8") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)


@contextmanager
def lock_sprint(sprint_dir: Path) -> Generator[None, None, None]:
    """Acquire an exclusive POSIX lock on a sentinel file inside *sprint_dir*.

    The sentinel file is ``sprint_dir/.kanban.lock`` and is created if it
    does not exist.  This serialises all kanban mutations within a sprint.
    """
    lock_file = sprint_dir / ".kanban.lock"
    lock_file.touch(exist_ok=True)
    with open(lock_file, "r+", encoding="utf-8") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)


# ---------------------------------------------------------------------------
# Story lookup
# §kanban.find_story
# ---------------------------------------------------------------------------

def find_story(story_id: str, sprints_dir: Path, sprint: int) -> TF | None:
    """Locate a tracking file for *story_id* inside ``sprint-{sprint}/stories/``.

    Matches files whose stem begins with the story ID (e.g.
    ``US-0042-some-feature.md`` matches story ID ``US-0042``).  Returns a
    populated :class:`TF` on the first match, or ``None`` if not found.
    """
    stories_dir = sprints_dir / f"sprint-{sprint}" / "stories"
    if not stories_dir.is_dir():
        return None
    prefix = story_id.upper()
    for md_file in sorted(stories_dir.glob("*.md")):
        stem = md_file.stem.upper()
        # Match exact ID or ID followed by a dash (slug separator)
        if stem == prefix or stem.startswith(prefix + "-"):
            return read_tf(md_file)
    return None
