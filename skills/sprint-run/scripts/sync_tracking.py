#!/usr/bin/env python3
"""Reconcile local story tracking files with GitHub state.

Usage: python sync_tracking.py <sprint-number>

Config-driven: reads sprints_dir, team_dir, and repo from project.toml
via validate_config.load_config(). No hardcoded project-specific values.

Reconciliation role: this script accepts GitHub state for fields that
kanban.py does not manage (PR linkage, branch, completion dates). For
kanban state mutations, use kanban.py (local-first, then syncs to GitHub).
For reconciliation, this script fills in PR/branch metadata and corrects
stale statuses. Both paths are complementary, not competing.

Concurrency: BH27 — this script acquires lock_sprint for the entire sync
loop to prevent clobbering concurrent kanban.py operations.

Idempotent -- prints "Everything in sync" when nothing to fix.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

# -- Import shared config ----------------------------------------------------
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent / "scripts"))
from validate_config import (
    load_config, ConfigError, gh_json, extract_story_id, get_sprints_dir,
    kanban_from_labels, find_milestone,
    list_milestone_issues, parse_iso_date, short_title, KANBAN_STATES,
    warn_if_at_limit, TF, read_tf, write_tf, _yaml_safe, slug_from_title,  # noqa: F401 — re-exported for tests
)
from kanban import lock_sprint, atomic_write_tf, append_transition_log  # BH24-002, BH27


# §sync_tracking._fetch_all_prs
def _fetch_all_prs() -> list[dict]:
    """Fetch all PRs once for branch-based linkage (cached per sync run)."""
    try:
        result = gh_json([
            "pr", "list", "--state", "all",
            "--json", "number,state,headRefName,mergedAt",
            "--limit", "500",
        ])
        if not isinstance(result, list):
            return []
        warn_if_at_limit(result)  # BH-015: warn when 500 limit is hit
        return result
    except RuntimeError:
        return []


# §sync_tracking.get_linked_pr
def get_linked_pr(
    issue_num: int, story_id: str, all_prs: list[dict] | None = None,
) -> dict | None:
    """Find PR linked to issue via timeline API, fallback to branch name.

    The fallback search uses the pre-fetched all_prs list to avoid
    per-issue API calls. Pass all_prs from _fetch_all_prs().
    """
    try:
        # Fetch all linked PRs, prefer open/merged over closed
        linked = gh_json([
            "api",
            f"repos/{{owner}}/{{repo}}/issues/{issue_num}/timeline",
            "--paginate", "--jq",
            '[.[] | select(.source?.issue?.pull_request?) '
            '| .source.issue]',
        ])
        if linked:
            if isinstance(linked, dict):
                linked = [linked]
            if linked:
                # Prefer open PRs, then latest merged, then last in list
                best = linked[-1]  # default to last in list
                open_pr = None
                latest_merged = None
                latest_merged_at = ""
                for d in linked:
                    if d.get("state") == "open":
                        open_pr = d
                        break  # open PR takes priority
                    merged_at = d.get("pull_request", {}).get("merged_at")
                    if merged_at is not None:
                        if merged_at > latest_merged_at:
                            latest_merged = d
                            latest_merged_at = merged_at
                if open_pr:
                    best = open_pr
                elif latest_merged:
                    best = latest_merged
                return {
                    "number": best.get("number"),
                    "state": best.get("state"),
                    "merged": (
                        best.get("pull_request", {}).get("merged_at")
                        is not None
                    ),
                }
    except RuntimeError as exc:
        print(f"Warning: timeline API failed for issue {issue_num}: {exc}",
              file=sys.stderr)
    # Fallback: search pre-fetched PRs by branch name.
    # BH18-010: Match the story ID in the slug portion (after last /) to avoid
    # false matches on branches like sprint-2/us-0001-follow-up when looking
    # for sprint-1's US-0001.
    for pr in (all_prs or []):
        branch = pr.get("headRefName", "")
        slug = branch.rsplit("/", 1)[-1] if "/" in branch else branch
        if re.search(rf"\b{re.escape(story_id)}\b", slug, re.IGNORECASE):
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


# -- Sync logic --------------------------------------------------------------

# §sync_tracking.sync_one
def sync_one(
    tf: TF, issue: dict, pr: dict | None, sprint: int
) -> list[str]:
    """Update tracking file to match GitHub. Returns change descriptions.

    Note: This function intentionally accepts ANY valid GitHub state without
    transition validation.  This differs from ``kanban.py do_sync`` which
    validates transitions via ``validate_transition()``.  The rationale:
    sync_tracking trusts GitHub labels as source of truth — including
    manually applied ones that the kanban state machine would reject.
    See CLAUDE.md "Two-path state management" for the full design rationale.
    """
    changes: list[str] = []
    gh_status = kanban_from_labels(issue)

    # Accept any valid state from GitHub (intentional — see docstring)
    if gh_status != tf.status and gh_status in KANBAN_STATES:
        old_status = tf.status
        append_transition_log(tf, old_status, gh_status, "external: GitHub sync")
        changes.append(
            f"{tf.story}: status {old_status} -> {gh_status} (label sync)"
        )
        tf.status = gh_status

    if tf.status == "done" and not tf.completed:
        d = parse_iso_date(issue.get("closedAt", ""))
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


# §sync_tracking.create_from_issue
def create_from_issue(
    issue: dict, sprint: int, d: Path, pr: dict | None
) -> tuple[TF, list[str]]:
    sid = extract_story_id(issue["title"])
    short = short_title(issue["title"])
    slug = slug_from_title(short)
    # BH22-117: Match kanban.py do_sync filename convention — uppercase story
    # ID prefix, lowercase slug suffix.  This prevents duplicate tracking files
    # when both sync paths run on a fresh sprint.
    story_id_upper = sid.upper()
    filename = f"{story_id_upper}-{slug}.md" if slug else f"{story_id_upper}.md"
    # BH21-012: kanban_from_labels now handles closed-issue override internally
    status = kanban_from_labels(issue)
    target = d / filename
    # BH-016: Detect slug collision — if a file exists with a different story ID,
    # append issue number to make the slug unique.
    if target.is_file():
        existing = read_tf(target)
        if existing.story and existing.story != sid:
            # BH23-204: Keep story ID prefix in collision fallback filename
            # so find_story() can still locate the file by ID.
            slug = f"{slug}-{issue['number']}"
            filename = f"{story_id_upper}-{slug}.md"
            target = d / filename
            print(f"  Warning: slug collision for {sid}, using {filename}",
                  file=sys.stderr)
    tf = TF(
        path=target,
        story=sid,
        title=short,
        sprint=sprint,
        status=status,
        issue_number=str(issue["number"]),
        pr_number=str(pr["number"]) if pr else "",
        branch=f"sprint-{sprint}/{slug}"[:255],  # BH24-033: git branch name limit
    )
    if tf.status == "done":
        tf.completed = parse_iso_date(issue.get("closedAt", ""))
    # P1-STATE-3: Initialize verification section in body
    tf.body_text = (
        "## Verification\n"
        "- agent: []\n"
        "- orchestrator: []\n"
        "- unverified: []\n"
    )
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

    try:
        config = load_config()
    except ConfigError:
        sys.exit(1)
    sprints_dir = get_sprints_dir(config)

    stories_dir = sprints_dir / f"sprint-{sprint}" / "stories"
    stories_dir.mkdir(parents=True, exist_ok=True)

    ms = find_milestone(sprint)
    if not ms:
        print(f"No GitHub milestone for Sprint {sprint}", file=sys.stderr)
        sys.exit(1)
    mt = ms["title"]

    issues = list_milestone_issues(mt)
    if not issues:
        print(f"No issues in milestone '{mt}'")
        return

    existing: dict[str, TF] = {}
    seen_ids: dict[str, Path] = {}
    for p in stories_dir.glob("*.md"):
        tf = read_tf(p)
        if tf.story:
            # BH27: Normalize to uppercase — matches kanban.py do_sync convention
            key = tf.story.upper()
            if key in seen_ids:
                print(
                    f"Warning: duplicate story ID '{tf.story}' in "
                    f"{seen_ids[key]} and {p}",
                    file=sys.stderr,
                )
            seen_ids[key] = p
            existing[key] = tf

    all_prs = _fetch_all_prs()
    all_changes: list[str] = []

    # BH27: Use lock_sprint for the entire sync loop — matches kanban.py sync.
    # This prevents concurrent kanban.py WIP transitions (which also hold
    # lock_sprint) from colliding with our writes.
    sprint_dir = sprints_dir / f"sprint-{sprint}"
    with lock_sprint(sprint_dir):
        for issue in issues:
            sid = extract_story_id(issue["title"])
            pr = get_linked_pr(issue["number"], story_id=sid, all_prs=all_prs)
            if sid.upper() in existing:
                # Re-read under lock to get fresh state
                existing[sid] = read_tf(existing[sid].path)
                changes = sync_one(existing[sid], issue, pr, sprint)
                if changes:
                    atomic_write_tf(existing[sid])
                all_changes.extend(changes)
            else:
                tf, changes = create_from_issue(
                    issue, sprint, stories_dir, pr
                )
                atomic_write_tf(tf)
                all_changes.extend(changes)

    if all_changes:
        print(f"Sync complete -- {len(all_changes)} change(s):")
        for c in all_changes:
            print(f"  {c}")
    else:
        print("Everything in sync")


if __name__ == "__main__":
    main()
