#!/usr/bin/env python3
"""Quick status check for sprint monitoring.

Usage: python check_status.py [sprint-number]

Config-driven: reads sprints_dir and repo from project.toml via
validate_config.load_config(). No hardcoded project-specific values.

If sprint-number is omitted, reads from SPRINT-STATUS.md. Checks CI,
open PRs, and milestone progress. Writes timestamped log (keeps 10).
Exit: 0 = no action needed, 1 = action needed, 2 = usage error.
"""
from __future__ import annotations

import re
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

# -- Import shared config ----------------------------------------------------
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent / "scripts"))
from validate_config import load_config, ConfigError, extract_sp, gh, gh_json, get_base_branch, get_sprints_dir, detect_sprint, warn_if_at_limit

# -- Import sync engine ------------------------------------------------------
try:
    from sync_backlog import main as sync_backlog_main
except ImportError as _import_err:
    print(f"Warning: sync_backlog unavailable: {_import_err}", file=sys.stderr)
    sync_backlog_main = None

MAX_LOGS = 10


# -- CI check ----------------------------------------------------------------

# §check_status.check_ci
def check_ci() -> tuple[list[str], list[str]]:
    runs = gh_json([
        "run", "list", "--limit", "5",
        "--json", "status,conclusion,name,headBranch,databaseId",
    ])
    if not runs:
        return ["CI: no recent runs"], []

    passing = sum(1 for r in runs if r.get("conclusion") == "success")
    failing = [r for r in runs if r.get("conclusion") == "failure"]
    in_prog = [
        r for r in runs
        if r.get("status") in ("in_progress", "queued")
    ]

    parts = []
    if passing:
        parts.append(f"{passing} passing")
    if failing:
        parts.append(f"{len(failing)} failing")
    if in_prog:
        parts.append(f"{len(in_prog)} in progress")

    report, actions = [f"CI: {', '.join(parts)}"], []
    for run in failing:
        branch = run.get("headBranch", "?")
        name = run.get("name", "?")
        report.append(f"  - {name} on {branch}: FAILED")
        run_id = run.get("databaseId")
        if run_id:
            try:
                log = gh(["run", "view", str(run_id), "--log-failed"])
                err = _first_error(log)
                if err:
                    report.append(f"    Error: {err}")
                    actions.append(f"CI failing on {branch}: {err}")
            except RuntimeError:
                actions.append(
                    f"CI failing on {branch} (could not read logs)"
                )
    return report, actions


def _first_error(log: str) -> str:
    _FALSE_POSITIVE = re.compile(r"\b(?:0|no)\s+(?:error|fail)", re.IGNORECASE)
    for line in log.splitlines():
        lower = line.lower()
        if any(kw in lower for kw in ("error", "failed", "panicked", "assert")):
            if _FALSE_POSITIVE.search(lower):
                continue
            cleaned = re.sub(r"\x1b\[[0-9;]*m", "", line).strip()
            return cleaned[:117] + "..." if len(cleaned) > 117 else cleaned
    return ""


# -- PR check ----------------------------------------------------------------

# §check_status.check_prs
def check_prs() -> tuple[list[str], list[str]]:
    prs = gh_json([
        "pr", "list",
        "--json",
        "number,title,reviewDecision,labels,statusCheckRollup,createdAt",
    ])
    if not prs:
        return ["PRs: none open"], []

    needs_review: list[tuple[str, str]] = []
    approved: list[tuple[str, bool]] = []
    changes_req: list[str] = []

    for pr in prs:
        entry = f"#{pr.get('number', '?')}: {pr.get('title', '?')}"
        checks = pr.get("statusCheckRollup") or []
        completed = [c for c in checks if c.get("status") == "COMPLETED"]
        ci_ok = len(completed) > 0 and all(
            c.get("conclusion") == "SUCCESS" for c in completed
        )
        match pr.get("reviewDecision", ""):
            case "APPROVED":
                approved.append((entry, ci_ok))
            case "CHANGES_REQUESTED":
                changes_req.append(entry)
            case _:
                needs_review.append((entry, pr.get("createdAt", "")))

    parts = [f"{len(prs)} open"]
    if needs_review:
        parts.append(f"{len(needs_review)} needs review")
    if approved:
        parts.append(f"{len(approved)} approved")
    if changes_req:
        parts.append(f"{len(changes_req)} changes requested")

    report, actions = [f"PRs: {', '.join(parts)}"], []
    for entry, ci_ok in approved:
        tag = "CI green, ready to merge" if ci_ok else "CI pending/failing"
        report.append(f"  - {entry}: approved ({tag})")
        if ci_ok:
            actions.append(
                f"{entry}: approved + CI green -- ready to merge"
            )
    for entry, created in needs_review:
        age = _age(created)
        report.append(f"  - {entry}: awaiting review ({age})")
        if _hours(created) > 2:
            actions.append(f"{entry}: awaiting review for {age}")
    for entry in changes_req:
        report.append(f"  - {entry}: changes requested")
    return report, actions


def _hours(iso: str) -> float:
    if not iso:
        return 0.0
    try:
        return (
            datetime.now(timezone.utc)
            - datetime.fromisoformat(iso.replace("Z", "+00:00"))
        ).total_seconds() / 3600
    except (ValueError, TypeError):
        return 0.0


def _age(iso: str) -> str:
    h = _hours(iso)
    if h < 1:
        return f"{int(h * 60)}m"
    return f"{h:.1f}h" if h < 24 else f"{h / 24:.1f}d"


# -- Milestone progress ------------------------------------------------------

# §check_status.check_milestone
def check_milestone(sprint_num: int) -> tuple[list[str], list[str]]:
    try:
        milestones = gh_json([
            "api", "repos/{owner}/{repo}/milestones", "--paginate",
        ])
    except RuntimeError:
        return ["Progress: could not query milestones"], []

    ms = next(
        (
            m
            for m in (milestones if isinstance(milestones, list) else [])
            if re.match(rf"^Sprint {sprint_num}\b", m.get("title", ""))
        ),
        None,
    )
    if ms is None:
        return [f"Progress: no milestone for Sprint {sprint_num}"], []

    opened = ms.get("open_issues", 0)
    closed = ms.get("closed_issues", 0)
    total = opened + closed
    pct = round(closed / total * 100) if total else 0

    sp_part = ""
    try:
        issues = gh_json([
            "issue", "list", "--milestone", ms["title"],
            "--state", "all",
            "--json", "state,labels,body", "--limit", "500",
        ])
        warn_if_at_limit(issues, 500)
        t_sp, d_sp = _count_sp(issues)
        if t_sp:
            sp_part = f", {d_sp}/{t_sp} SP"
    except RuntimeError:
        pass
    return [f"Progress: {closed}/{total} stories done{sp_part} ({pct}%)"], []


def _count_sp(issues: list[dict]) -> tuple[int, int]:
    t = d = 0
    for i in issues:
        sp = extract_sp(i)
        t += sp
        if i.get("state") == "closed":
            d += sp
    return t, d




# -- Drift detection ---------------------------------------------------------

# §check_status.check_branch_divergence
def check_branch_divergence(
    repo: str, base_branch: str, sprint_branches: list[str],
) -> tuple[list[str], list[str]]:
    """Check if any sprint branch has diverged significantly from base.

    Returns (report_lines, action_lines).
    Risk is 'high' if behind_count > 20 commits, 'medium' if > 10.
    """
    report: list[str] = []
    actions: list[str] = []
    for branch in sprint_branches:
        try:
            data = gh_json([
                "api", f"repos/{repo}/compare/{base_branch}...{branch}",
                "--jq", "{behind_by: .behind_by, ahead_by: .ahead_by}",
            ])
            if isinstance(data, list):
                report.append(
                    f"  Drift: WARNING — could not parse divergence "
                    f"data for {branch} (unexpected list response)"
                )
                continue
            behind = data.get("behind_by", 0)
            ahead = data.get("ahead_by", 0)
            if behind > 20:
                msg = (
                    f"{branch} is {behind} commits behind {base_branch}. "
                    "A rebase before the next review round would be prudent. "
                    "I say this from experience."
                )
                report.append(f"  Drift: HIGH — {msg}")
                actions.append(f"Branch drift: {branch} ({behind} behind)")
            elif behind > 10:
                report.append(
                    f"  Drift: MEDIUM — {branch} is {behind} commits "
                    f"behind {base_branch} ({ahead} ahead)"
                )
        except RuntimeError as exc:
            report.append(f"  Drift: skipped {branch} — {exc}")
    return report, actions


# §check_status.check_direct_pushes
def check_direct_pushes(
    repo: str, base_branch: str, since: str,
) -> tuple[list[str], list[str]]:
    """Check for commits pushed directly to base branch since a date.

    Returns (report_lines, action_lines) for non-merge commits found.
    """
    report: list[str] = []
    actions: list[str] = []
    try:
        # Note: `select(.parents | length == 1)` intentionally excludes
        # merge commits (2+ parents) AND the initial/root commit (0 parents).
        # Excluding root commits is acceptable — force-pushed root commits
        # are extremely rare and not a practical drift concern. (BH-P11-114)
        commits = gh_json([
            "api", f"repos/{repo}/commits",
            "-f", f"sha={base_branch}", "-f", f"since={since}",
            "--jq",
            '[.[] | select(.parents | length == 1) | '
            '{sha: .sha[:8], message: .commit.message, '
            'author: .commit.author.name, date: .commit.author.date}]',
        ])
        if isinstance(commits, list) and commits:
            report.append(
                f"  Drift: {len(commits)} direct push(es) to {base_branch} "
                f"since {since}"
            )
            for c in commits[:3]:
                sha = c.get("sha", "?")
                msg = (c.get("message", "") or "").split("\n")[0][:60]
                report.append(f"    {sha}: {msg}")
            actions.append(
                f"Someone appears to have pushed directly to {base_branch}. "
                "I won't say who, but I will say it's making the merge "
                "queue nervous."
            )
    except RuntimeError as exc:
        report.append(f"  Drift: direct push check skipped — {exc}")
    return report, actions


# -- Log management ----------------------------------------------------------

# §check_status.write_log
def write_log(
    sprint_num: int, report: str, now: datetime, sprints_dir: Path
) -> Path:
    d = sprints_dir / f"sprint-{sprint_num}"
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"monitor-{now.strftime('%Y%m%d-%H%M%S')}.log"
    path.write_text(report, encoding="utf-8")
    logs = sorted(d.glob("monitor-*.log"))
    while len(logs) > MAX_LOGS:
        logs.pop(0).unlink()
    return path


# -- Main --------------------------------------------------------------------

# §check_status.main
def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] in ("-h", "--help"):
        print(__doc__.strip())
        sys.exit(0)
    try:
        config = load_config()
    except ConfigError:
        sys.exit(1)
    sprints_dir = get_sprints_dir(config)

    sprint_num: int | None = None
    if len(sys.argv) >= 2:
        if sys.argv[1].isdigit():
            sprint_num = int(sys.argv[1])
        else:
            print(
                "Usage: python check_status.py [sprint-number]",
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

    now = datetime.now(timezone.utc)
    report_lines: list[str] = [f"=== Sprint {sprint_num} Status ==="]
    action_lines: list[str] = []

    # Step 0: Sync backlog
    if sync_backlog_main is not None:
        try:
            sync_status = sync_backlog_main()
            report_lines.append(f"Sync: {sync_status}")
        except Exception as exc:
            report_lines.append(f"Sync: error — {exc}")
            traceback.print_exc(file=sys.stderr)

    repo = config.get("project", {}).get("repo", "")
    base_branch = get_base_branch(config)

    # Collect open PR branches for drift detection
    sprint_branches: list[str] = []
    try:
        prs = gh_json(["pr", "list", "--json", "headRefName"])
        sprint_branches = [p["headRefName"] for p in (prs or []) if p.get("headRefName")]
    except RuntimeError:
        pass

    # Sprint start date from milestone created_at (not filesystem mtime,
    # which resets every time SPRINT-STATUS.md is rewritten — BH-014)
    since = now.strftime("%Y-%m-%dT00:00:00Z")
    try:
        milestones = gh_json([
            "api", "repos/{owner}/{repo}/milestones", "--paginate",
        ])
        if isinstance(milestones, list):
            ms = next(
                (m for m in milestones
                 if re.match(rf"^Sprint {sprint_num}\b", m.get("title", ""))),
                None,
            )
            if ms and ms.get("created_at"):
                since = ms["created_at"]
    except RuntimeError:
        pass

    # Steps 1, 1.5, 2, 2.5, 3: CI → drift → PRs → direct pushes → milestone
    checks = [
        check_ci,
        lambda: check_branch_divergence(repo, base_branch, sprint_branches),
        check_prs,
        lambda: check_direct_pushes(repo, base_branch, since),
        lambda: check_milestone(sprint_num),
    ]
    for fn in checks:
        try:
            r, a = fn()
            report_lines.extend(r)
            action_lines.extend(a)
        except RuntimeError as exc:
            report_lines.append(f"Check failed: {exc}")

    if action_lines:
        report_lines += [
            "", "Action needed:",
        ] + [f"  - {a}" for a in action_lines]

    full = "\n".join(report_lines)
    print(full)

    try:
        lp = write_log(sprint_num, full, now, sprints_dir)
        print(f"\nLog written: {lp}")
    except OSError as exc:
        print(
            f"\nWarning: could not write log: {exc}", file=sys.stderr
        )

    sys.exit(1 if action_lines else 0)


if __name__ == "__main__":
    main()
