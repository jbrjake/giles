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
import subprocess
import sys
import traceback
from datetime import datetime, timedelta, timezone
from pathlib import Path

# -- Import shared config ----------------------------------------------------
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent / "scripts"))
from validate_config import load_config, ConfigError, extract_sp, gh, gh_json, get_base_branch, get_sprints_dir, detect_sprint, warn_if_at_limit, find_milestone, safe_int

# -- Import sync engine and smoke helpers ------------------------------------
try:
    from sync_backlog import main as sync_backlog_main
except ImportError as _import_err:
    print(f"Warning: sync_backlog unavailable: {_import_err}", file=sys.stderr)
    sync_backlog_main = None
try:
    from smoke_test import write_history as _write_smoke_history
except ImportError:
    _write_smoke_history = None

MAX_LOGS = 10
_MAX_LOG_LINES = 500          # BH21-019: cap CI log size before scanning
_MAX_LOG_BYTES = 100_000      # ~100 KB


def _truncate_log(log: str) -> str:
    """Cap CI log to _MAX_LOG_LINES / _MAX_LOG_BYTES, whichever hits first."""
    if len(log) <= _MAX_LOG_BYTES:
        lines = log.splitlines()
        if len(lines) <= _MAX_LOG_LINES:
            return log
        return "\n".join(lines[:_MAX_LOG_LINES])
    # Byte limit hit — take first N bytes, then trim to last full line
    truncated = log[:_MAX_LOG_BYTES]
    last_nl = truncated.rfind("\n")
    if last_nl > 0:
        truncated = truncated[:last_nl]
    return truncated


# -- CI check ----------------------------------------------------------------

# §check_status.check_ci
def check_ci() -> tuple[list[str], list[str]]:
    # BH24-041: wrap gh_json in try/except so proxy HTML errors don't crash monitor
    try:
        runs = gh_json([
            "run", "list", "--limit", "5",
            "--json", "status,conclusion,name,headBranch,databaseId",
        ])
    except RuntimeError as exc:
        return [f"CI: query failed — {exc}"], []
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
                # BH21-019: truncate oversized CI logs before scanning
                log = _truncate_log(log)
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
    # BH21-023: Require trailing space/punctuation/EOL (not hyphen) to avoid
    # matching "no error-handling" as a false positive.
    _FALSE_POSITIVE = re.compile(
        r"\b(?:0|no)\s+(?:errors?|fail(?:ures?|ed)?)(?:\s|[.,;:!)]|$)",
        re.IGNORECASE,
    )
    # BH23-211: Use word boundaries for keyword matching to avoid
    # false positives like "assertion_name" or "terror".
    _ERROR_KW = re.compile(
        r"\b(?:error|failed|panicked|assert(?:ion)?(?:\s+failed)?)\b",
        re.IGNORECASE,
    )
    _ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")
    for line in log.splitlines():
        # Strip ANSI codes before matching so \x1b[31mERROR → ERROR
        cleaned = _ANSI_RE.sub("", line)
        lower = cleaned.lower()
        if _ERROR_KW.search(lower):
            if _FALSE_POSITIVE.search(lower):
                continue
            trimmed = cleaned.strip()
            return trimmed[:117] + "..." if len(trimmed) > 117 else trimmed
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
def check_milestone(
    sprint_num: int, _ms: dict | None = None,
) -> tuple[list[str], list[str]]:
    """Check milestone progress.

    BH18-001/002: Uses find_milestone() from validate_config for consistent
    leading-zero handling and to avoid redundant API calls. Accepts an optional
    pre-fetched milestone dict to eliminate duplicate queries in main().
    """
    if _ms is None:
        try:
            _ms = find_milestone(sprint_num)
        except RuntimeError:
            return ["Progress: could not query milestones"], []

    if _ms is None:
        return [f"Progress: no milestone for Sprint {sprint_num}"], []

    opened = _ms.get("open_issues", 0)
    closed = _ms.get("closed_issues", 0)
    total = opened + closed
    pct = round(closed / total * 100) if total else 0

    sp_part = ""
    try:
        issues = gh_json([
            "issue", "list", "--milestone", _ms["title"],
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




# -- Smoke check -------------------------------------------------------------

# §check_status.check_smoke
def check_smoke(config: dict, sprints_dir: Path) -> tuple[list[str], list[str]]:
    """Run smoke test if configured and report result.

    Includes rate limiting: skips if last smoke check was < 10 minutes ago.
    Returns (report_lines, action_lines).
    """
    ci = config.get("ci", {})
    smoke_cmd = ci.get("smoke_command", "")
    if not smoke_cmd:
        return [], []  # silently skip when not configured

    # Rate limiting: check smoke history for recent runs
    history_path = sprints_dir / "smoke-history.md"
    if history_path.is_file():
        lines = [l for l in history_path.read_text(encoding="utf-8").splitlines() if l.strip()]
        if lines:
            last_line = lines[-1]
            # Parse date from "| 2026-03-20 14:30 | ..."
            date_match = re.match(r'\|\s*(\d{4}-\d{2}-\d{2} \d{2}:\d{2})Z?', last_line)
            if date_match:
                try:
                    last_run = datetime.strptime(date_match.group(1), "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
                    if (datetime.now(timezone.utc) - last_run).total_seconds() < 600:
                        return ["Smoke: skipped (ran < 10 minutes ago)"], []
                except ValueError:
                    pass

    # Run smoke test
    smoke_timeout = safe_int(ci.get("smoke_timeout", 30))
    try:
        result = subprocess.run(
            smoke_cmd, shell=True, capture_output=True, text=True,
            timeout=smoke_timeout,
        )
        status = "SMOKE PASS" if result.returncode == 0 else "SMOKE FAIL"
        # Write to smoke history so rate limiting and debt tracking work
        if _write_smoke_history:
            _write_smoke_history(
                str(sprints_dir), status, smoke_cmd,
                result.stdout or "", result.stderr or "",
            )
        if result.returncode == 0:
            return ["Smoke: PASS"], []
        else:
            # Check for regression: was last result a PASS?
            actions = []
            if history_path.is_file():
                text = history_path.read_text(encoding="utf-8")
                result_matches = re.findall(r'SMOKE (PASS|FAIL)', text)
                # Check second-to-last (last is the one we just wrote)
                if len(result_matches) >= 2 and result_matches[-2] == "PASS":
                    try:
                        prs = gh_json(["pr", "list", "--state", "merged",
                                       "--limit", "1", "--json", "number,title"])
                        if prs and isinstance(prs, list) and prs:
                            pr = prs[0]
                            actions.append(
                                f"INTEGRATION REGRESSION: smoke test failed after "
                                f"PR #{pr.get('number', '?')} ({pr.get('title', '?')})"
                            )
                    except RuntimeError:
                        actions.append("INTEGRATION REGRESSION: smoke test transitioned PASS → FAIL")
            stderr = (result.stderr or "").strip()[:200]
            return [f"Smoke: FAIL — {stderr}"], actions
    except subprocess.TimeoutExpired:
        if _write_smoke_history:
            _write_smoke_history(str(sprints_dir), "SMOKE FAIL", smoke_cmd, "", f"timed out after {smoke_timeout}s")
        return [f"Smoke: FAIL — timed out after {smoke_timeout}s"], \
               ["Smoke test timed out"]
    except (OSError, subprocess.SubprocessError) as exc:  # BH33-002
        return [f"Smoke: error — {exc}"], []


# -- Integration debt --------------------------------------------------------

# §check_status.check_integration_debt
def check_integration_debt(sprints_dir: Path, sprint_num: int,
                           ) -> tuple[list[str], list[str]]:
    """Check integration debt: sprints since last smoke pass.

    Returns (report_lines, action_lines). HIGH severity when debt > 2.
    """
    history_path = sprints_dir / "smoke-history.md"
    if not history_path.is_file():
        return ["Integration Debt: unknown (no smoke history)"], []

    text = history_path.read_text(encoding="utf-8")
    if "SMOKE PASS" not in text:
        return ["Integration Debt: unknown (no smoke pass on record)"], \
               ["HIGH: no smoke test has ever passed"]

    # Find the most recent SMOKE PASS line and its date
    pass_lines = [l for l in text.splitlines() if "SMOKE PASS" in l]
    if not pass_lines:
        return ["Integration Debt: unknown"], []

    # Estimate sprints since last pass by date proximity
    last_pass = pass_lines[-1]
    date_match = re.match(r'\|\s*(\d{4}-\d{2}-\d{2})', last_pass)
    if not date_match:
        return ["Integration Debt: unknown (unparseable date)"], []

    # Simple heuristic: count by weeks (assuming ~1 sprint per 1-2 weeks)
    try:
        pass_date = datetime.strptime(date_match.group(1), "%Y-%m-%d").replace(tzinfo=timezone.utc)
        days_since = (datetime.now(timezone.utc) - pass_date).days
        debt = max(0, days_since // 14)  # rough: 2-week sprints
    except ValueError:
        debt = 0

    report = [f"Integration Debt: {debt} sprints"]
    actions = []
    if debt > 2:
        actions.append(f"HIGH: integration debt is {debt} sprints — "
                       "the product hasn't been verified to work recently")
    return report, actions


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
        try:
            logs.pop(0).unlink()
        except OSError:
            pass  # BH21-022: best-effort cleanup; don't crash monitor
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
        except (RuntimeError, OSError, ValueError, ImportError) as exc:
            # BH24-019: narrow from bare Exception to let programming
            # errors (KeyError, TypeError, AttributeError) propagate
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

    # BH18-001/002: Query milestone once via find_milestone() (handles leading
    # zeros) and reuse for both created_at drift detection and check_milestone.
    since = (now - timedelta(days=14)).strftime("%Y-%m-%dT00:00:00Z")
    since_from_milestone = False
    cached_ms = None
    try:
        cached_ms = find_milestone(sprint_num)
        if cached_ms and cached_ms.get("created_at"):
            since = cached_ms["created_at"]
            since_from_milestone = True
    except RuntimeError:
        pass
    if not since_from_milestone:
        report_lines.append(
            "Drift: milestone date unavailable, checking last 14 days"
        )

    # Steps 1–4: CI → smoke → drift → PRs → direct pushes → milestone → debt
    checks = [
        check_ci,
        lambda: check_smoke(config, sprints_dir),
        lambda: check_branch_divergence(repo, base_branch, sprint_branches),
        check_prs,
        lambda: check_direct_pushes(repo, base_branch, since),
        lambda: check_milestone(sprint_num, _ms=cached_ms),
        lambda: check_integration_debt(sprints_dir, sprint_num),
    ]
    for fn in checks:
        try:
            r, a = fn()
            report_lines.extend(r)
            action_lines.extend(a)
        except (RuntimeError, OSError, ValueError) as exc:
            # BH24-019: narrow from bare Exception to let programming
            # errors (KeyError, TypeError, AttributeError) propagate
            report_lines.append(f"Check failed: {exc}")
            traceback.print_exc(file=sys.stderr)

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
