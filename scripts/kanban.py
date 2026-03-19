#!/usr/bin/env python3
"""Kanban state machine for sprint story management.

Usage:
    kanban.py transition <story-id> <target-state> [--sprint N]
    kanban.py assign <story-id> --implementer <name> [--reviewer <name>] [--sprint N]
    kanban.py update <story-id> [--pr-number N] [--branch NAME] [--sprint N]
    kanban.py sync [--sprint N] [--prune]
    kanban.py status [--sprint N]

Source of truth: local tracking files (sprint-{N}/stories/*.md).
GitHub is a downstream reflection synced on every mutation.
"""
from __future__ import annotations

import os
import re
import sys
from contextlib import contextmanager
from pathlib import Path
import argparse
from typing import Generator

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

    Does NOT mutate ``tf.path`` — writes to a temp file via a shallow
    copy to avoid visible side effects on the caller's TF object.
    """
    tf.path.parent.mkdir(parents=True, exist_ok=True)
    tmp = tf.path.with_suffix(".tmp")
    # Write via a shallow copy so tf.path is never mutated
    import dataclasses
    tmp_tf = dataclasses.replace(tf, path=tmp)
    write_tf(tmp_tf)
    os.rename(str(tmp), str(tf.path))


# ---------------------------------------------------------------------------
# File locking
# §kanban.lock_story
# §kanban.lock_sprint
# ---------------------------------------------------------------------------

@contextmanager
def lock_story(tracking_path: Path) -> Generator[None, None, None]:
    """Acquire an exclusive POSIX lock for a story via a sentinel file.

    Uses ``tracking_path.with_suffix('.lock')`` as the lock target so that
    ``atomic_write_tf``'s inode-replacing rename does not invalidate the
    lock.  The sentinel file is stable across renames.
    """
    lock_path = tracking_path.with_suffix(".lock")
    lock_path.touch(exist_ok=True)
    with open(lock_path, "r", encoding="utf-8") as fh:
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
    populated :class:`TF` on the first sorted match.  If multiple files
    match, a warning is printed to stderr listing all matches.
    Returns ``None`` if not found.
    """
    stories_dir = sprints_dir / f"sprint-{sprint}" / "stories"
    if not stories_dir.is_dir():
        return None
    prefix = story_id.upper()
    matches: list[Path] = []
    for md_file in sorted(stories_dir.glob("*.md")):
        stem = md_file.stem.upper()
        # Match exact ID or ID followed by a dash (slug separator)
        if stem == prefix or stem.startswith(prefix + "-"):
            matches.append(md_file)
    if not matches:
        return None
    if len(matches) > 1:
        names = ", ".join(m.name for m in matches)
        print(f"Warning: multiple tracking files match {story_id}: {names}. "
              "Using first match.", file=sys.stderr)
    return read_tf(matches[0])


# ---------------------------------------------------------------------------
# GitHub sync — do_transition, do_assign, do_sync, do_status
# ---------------------------------------------------------------------------

# §kanban._PERSONA_HEADER_PATTERN
_PERSONA_HEADER_PATTERN = re.compile(
    r'> \*\*\[Unassigned\]\*\* · Implementation'
)


# §kanban.do_transition
def do_transition(tf: TF, target: str) -> bool:
    """Execute a state transition: validate, update local, sync GitHub.

    Returns True on success, False on failure (with local state reverted).
    """
    err = validate_transition(tf.status, target)
    if err:
        print(f"{tf.story}: {err}", file=sys.stderr)
        return False
    err = check_preconditions(tf, target)
    if err:
        print(f"{tf.story}: {err}", file=sys.stderr)
        return False
    old_status = tf.status
    issue_num = tf.issue_number
    if not issue_num:
        print(f"{tf.story}: no issue_number — cannot sync to GitHub", file=sys.stderr)
        return False
    # Update local state
    tf.status = target
    atomic_write_tf(tf)
    # Sync to GitHub
    try:
        gh(["issue", "edit", issue_num,
            "--remove-label", f"kanban:{old_status}",
            "--add-label", f"kanban:{target}"])
        if target == "done":
            gh(["issue", "close", issue_num])
        print(f"{tf.story}: {old_status} → {target}")
        return True
    except RuntimeError as exc:
        try:
            tf.status = old_status
            atomic_write_tf(tf)
            print(f"{tf.story}: local state reverted. GitHub update failed: {exc}",
                  file=sys.stderr)
        except Exception as rollback_exc:
            # BH23-201: Always restore caller's tf.status even when disk
            # rollback fails, so the in-memory object is consistent.
            tf.status = old_status
            print(f"{tf.story}: CRITICAL — GitHub update failed ({exc}) AND "
                  f"local rollback failed ({rollback_exc}). Local and GitHub "
                  f"state may be inconsistent. Run 'kanban.py sync' to reconcile.",
                  file=sys.stderr)
        return False


# §kanban.do_assign
def do_assign(tf: TF, implementer: str = "", reviewer: str = "") -> bool:
    """Assign personas: update local → add persona labels on GitHub → update issue body.

    Returns True on success, False on failure (with local state reverted).
    """
    old_implementer = tf.implementer
    old_reviewer = tf.reviewer
    issue_num = tf.issue_number
    if not issue_num:
        print(f"{tf.story}: no issue_number — cannot sync to GitHub", file=sys.stderr)
        return False

    if implementer:
        tf.implementer = implementer
    if reviewer:
        tf.reviewer = reviewer
    atomic_write_tf(tf)

    try:
        # Add persona labels
        if implementer:
            gh(["issue", "edit", issue_num, "--add-label", f"persona:{implementer}"])
        if reviewer:
            gh(["issue", "edit", issue_num, "--add-label", f"persona:{reviewer}"])
        # Update issue body: replace [Unassigned] header with implementer name
        if implementer:
            raw = gh_json(["issue", "view", issue_num, "--json", "body"])
            body = raw.get("body", "") if isinstance(raw, dict) else ""
            new_body = _PERSONA_HEADER_PATTERN.sub(
                f"> **[{implementer}]** · Implementation",
                body,
                count=1,  # BH22-104: replace only first match
            )
            if new_body != body:
                gh(["issue", "edit", issue_num, "--body", new_body])
            else:
                print(f"{tf.story}: issue body has no [Unassigned] header to replace. "
                      "Body update skipped — update manually if needed.",
                      file=sys.stderr)
        return True
    except RuntimeError as exc:
        try:
            tf.implementer = old_implementer
            tf.reviewer = old_reviewer
            atomic_write_tf(tf)
            print(f"{tf.story}: local state reverted. GitHub update failed: {exc}. "
                  "Note: persona labels already applied on GitHub may persist.",
                  file=sys.stderr)
        except Exception as rollback_exc:
            print(f"{tf.story}: CRITICAL — GitHub update failed ({exc}) AND "
                  f"local rollback failed ({rollback_exc}). Run 'kanban.py sync'.",
                  file=sys.stderr)
        return False


# §kanban.do_sync
def do_sync(sprints_dir: Path, sprint: int, issues: list,
            *, prune: bool = False) -> list[str]:
    """Bidirectional sync — accepts legal external GitHub changes, creates new stories.

    Takes a pre-fetched list of GitHub issue dicts so callers control the API
    query (no GitHub calls made here).  Returns a list of change descriptions.
    When *prune* is True, orphaned local stories (not found on GitHub) are
    deleted instead of just warned about.
    """
    stories_dir = sprints_dir / f"sprint-{sprint}" / "stories"
    stories_dir.mkdir(parents=True, exist_ok=True)

    # Build index of local tracking files by story ID
    local_by_id: dict[str, TF] = {}
    for md_file in sorted(stories_dir.glob("*.md")):
        tf = read_tf(md_file)
        if tf.story:
            local_by_id[tf.story.upper()] = tf

    changes: list[str] = []
    github_ids: set[str] = set()

    for issue in issues:
        title = issue.get("title", "")
        story_id = extract_story_id(title).upper()
        github_ids.add(story_id)
        github_state = kanban_from_labels(issue)
        issue_num = str(issue.get("number", ""))

        if story_id in local_by_id:
            tf = local_by_id[story_id]
            if tf.status == github_state:
                # No-op: states match
                continue
            # BH22-050: A closed GitHub issue is always authoritative — the
            # issue has been explicitly closed, so force local state to done
            # regardless of the kanban transition graph.
            issue_closed = issue.get("state") == "closed"
            if issue_closed and github_state == "done":
                old = tf.status
                tf.status = "done"
                atomic_write_tf(tf)
                changes.append(
                    f"accepted external transition {story_id}: {old} → done "
                    f"(issue closed on GitHub)"
                )
                continue
            # States diverge — validate the external transition
            err = validate_transition(tf.status, github_state)
            if err is None:
                old = tf.status
                tf.status = github_state
                atomic_write_tf(tf)
                changes.append(
                    f"accepted external transition {story_id}: {old} → {github_state}"
                )
            else:
                changes.append(
                    f"WARNING: illegal external transition ignored for {story_id}: "
                    f"{tf.status} → {github_state} ({err})"
                )
        else:
            # New story from GitHub — create local tracking file
            # BH22-114: skip issues with no recognizable story ID
            if story_id == "UNKNOWN":
                changes.append(
                    f"WARNING: issue #{issue_num} ({title!r}) has no recognizable "
                    f"story ID — skipping tracking file creation"
                )
                continue
            slug = slug_from_title(short_title(title))
            filename = f"{story_id}-{slug}.md" if slug else f"{story_id}.md"
            path = stories_dir / filename
            tf = TF(
                path=path,
                story=story_id,
                title=short_title(title),
                sprint=sprint,
                status=github_state,
                issue_number=issue_num,
            )
            atomic_write_tf(tf)
            local_by_id[story_id] = tf
            changes.append(f"created tracking file for new story {story_id} ({github_state})")

    # Warn (or prune) local stories absent from GitHub
    for story_id, tf in local_by_id.items():
        if story_id not in github_ids:
            if prune:
                tf.path.unlink(missing_ok=True)
                lock_file = tf.path.with_suffix(".lock")
                lock_file.unlink(missing_ok=True)
                changes.append(f"pruned orphaned story {story_id} ({tf.path.name})")
            else:
                changes.append(
                    f"WARNING: local story {story_id} not found on GitHub "
                    f"(use --prune to remove orphaned files)"
                )

    return changes


# Fields that do_update is allowed to modify.  Immutable fields like
# path and story are excluded to prevent accidental file relocation.
_UPDATABLE_FIELDS = frozenset({
    "pr_number", "branch", "implementer", "reviewer",
    "started", "completed", "title",
})


# §kanban.do_update
def do_update(tf: TF, **fields: str) -> bool:
    """Update individual tracking file fields safely.

    Only non-None values are applied.  Only fields in ``_UPDATABLE_FIELDS``
    can be set — ``path``, ``story``, ``sprint``, and ``status`` are
    immutable (use ``transition`` or ``sync`` to change those).
    Writes atomically under lock.  Returns True on success.
    """
    changed = []
    for key, value in fields.items():
        if value is None:
            continue
        if key not in _UPDATABLE_FIELDS:
            print(f"Cannot update field '{key}' — "
                  f"allowed fields: {sorted(_UPDATABLE_FIELDS)}", file=sys.stderr)
            return False
        old = getattr(tf, key)
        if old != value:
            setattr(tf, key, value)
            changed.append(f"{key}: {old!r} → {value!r}")
    if changed:
        atomic_write_tf(tf)
        for c in changed:
            print(f"{tf.story}: {c}")
    else:
        print(f"{tf.story}: no changes")
    return True


# §kanban.do_status
def do_status(sprints_dir: Path, sprint: int) -> str:
    """Read-only board view from local tracking files.  No GitHub calls.

    Returns a formatted string grouping stories by kanban state.
    """
    stories_dir = sprints_dir / f"sprint-{sprint}" / "stories"
    if not stories_dir.is_dir():
        return f"Sprint {sprint}\n\n(no stories found)"

    # Ordered state list for display
    _STATE_ORDER = ("todo", "design", "dev", "review", "integration", "done")

    buckets: dict[str, list[TF]] = {state: [] for state in _STATE_ORDER}
    for md_file in sorted(stories_dir.glob("*.md")):
        tf = read_tf(md_file)
        state = tf.status if tf.status in buckets else "todo"
        buckets[state].append(tf)

    lines: list[str] = [f"Sprint {sprint}", ""]
    for state in _STATE_ORDER:
        stories = buckets[state]
        if not stories:
            continue
        lines.append(f"{state.upper()} ({len(stories)}):")
        for tf in stories:
            persona_parts = []
            if tf.implementer:
                persona_parts.append(tf.implementer)
            if tf.reviewer:
                persona_parts.append(tf.reviewer)
            persona_str = f" ({' → '.join(persona_parts)})" if persona_parts else ""
            lines.append(f"  {tf.story}{persona_str}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI entry point
# §kanban.build_parser
# §kanban.main
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Kanban state machine for sprint story management.")
    sub = parser.add_subparsers(dest="command")

    tr = sub.add_parser("transition", help="Transition a story to a new state")
    tr.add_argument("story_id", help="Story ID (e.g., US-0042)")
    tr.add_argument("target", help="Target kanban state")
    tr.add_argument("--sprint", type=int, default=None)

    asn = sub.add_parser("assign", help="Assign personas to a story")
    asn.add_argument("story_id", help="Story ID (e.g., US-0042)")
    asn.add_argument("--implementer", default="")
    asn.add_argument("--reviewer", default="")
    asn.add_argument("--sprint", type=int, default=None)

    sy = sub.add_parser("sync", help="Bidirectional sync with GitHub")
    sy.add_argument("--sprint", type=int, default=None)
    sy.add_argument("--prune", action="store_true",
                    help="Delete local tracking files for stories not on GitHub")

    up = sub.add_parser("update", help="Update tracking file fields")
    up.add_argument("story_id", help="Story ID (e.g., US-0042)")
    up.add_argument("--pr-number", default=None)
    up.add_argument("--branch", default=None)
    up.add_argument("--sprint", type=int, default=None)

    st = sub.add_parser("status", help="Show kanban board")
    st.add_argument("--sprint", type=int, default=None)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(2)

    try:
        config = load_config()
    except ConfigError:
        sys.exit(1)
    sprints_dir = get_sprints_dir(config)

    sprint = detect_sprint(sprints_dir) if args.sprint is None else args.sprint
    if sprint is None:
        print("Cannot detect sprint number. Use --sprint N.", file=sys.stderr)
        sys.exit(1)

    if args.command == "status":
        print(do_status(sprints_dir, sprint))
        return

    if args.command == "sync":
        sprint_dir = sprints_dir / f"sprint-{sprint}"
        ms = find_milestone(sprint)
        if not ms:
            print(f"No GitHub milestone for Sprint {sprint}", file=sys.stderr)
            sys.exit(1)
        issues = list_milestone_issues(ms["title"])
        with lock_sprint(sprint_dir):
            changes = do_sync(sprints_dir, sprint, issues, prune=args.prune)
        if changes:
            for c in changes:
                print(f"  {c}")
        else:
            print("Everything in sync")
        return

    # transition and assign need a story
    tf = find_story(args.story_id, sprints_dir, sprint)
    if tf is None:
        print(f"{args.story_id}: no tracking file found in sprint {sprint}. "
              "Run 'kanban.py sync' to pull new issues from GitHub.",
              file=sys.stderr)
        sys.exit(1)

    if args.command == "transition":
        with lock_story(tf.path):
            ok = do_transition(tf, args.target)
        sys.exit(0 if ok else 1)

    if args.command == "assign":
        if not args.implementer and not args.reviewer:
            print("Provide --implementer and/or --reviewer", file=sys.stderr)
            sys.exit(2)
        with lock_story(tf.path):
            ok = do_assign(tf, implementer=args.implementer, reviewer=args.reviewer)
        sys.exit(0 if ok else 1)

    if args.command == "update":
        with lock_story(tf.path):
            ok = do_update(tf, pr_number=args.pr_number, branch=args.branch)
        sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
