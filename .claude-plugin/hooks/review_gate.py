#!/usr/bin/env python3
"""Review gate hook — blocks PR merges without approved reviews
and direct pushes to the base branch.

Registered as a PreToolUse hook for the Bash tool.  Inspects command
strings for ``gh pr merge`` and ``git push origin {base_branch}``
patterns.

When run as a hook, reads JSON from stdin with the tool input and
writes a reason string to stdout.  Exit code 2 blocks the action.
"""
from __future__ import annotations

import datetime
import json
import re
import subprocess
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------

def _get_base_branch() -> str:
    """Read base_branch from project.toml, defaulting to 'main'."""
    try:
        toml_path = Path("sprint-config/project.toml")
        if not toml_path.is_file():
            return "main"
        text = toml_path.read_text(encoding="utf-8")
        for line in text.splitlines():
            m = re.match(r'\s*base_branch\s*=\s*"([^"]+)"', line)
            if m:
                return m.group(1)
    except Exception:
        pass
    return "main"


# ---------------------------------------------------------------------------
# Review decision query
# ---------------------------------------------------------------------------

def _query_review_decision(pr_number: str) -> str:
    """Query GitHub for the review decision on a PR."""
    try:
        result = subprocess.run(
            ["gh", "pr", "view", pr_number, "--json", "reviewDecision"],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            return data.get("reviewDecision", "")
    except Exception:
        pass
    return ""


# ---------------------------------------------------------------------------
# Check functions (pure, testable)
# ---------------------------------------------------------------------------

def check_merge(command: str, *, base: str = "main",
                _review_decision: str | None = None) -> str:
    """Check whether a ``gh pr merge`` command should be allowed.

    Returns ``'allowed'`` if the PR has an APPROVED review,
    ``'blocked'`` otherwise.

    The *_review_decision* parameter is for testing — when provided,
    skips the actual GitHub API call.
    """
    m = re.search(r'gh\s+pr\s+merge\s+(\d+)', command)
    if not m:
        return "allowed"

    pr_number = m.group(1)

    if _review_decision is None:
        decision = _query_review_decision(pr_number)
    else:
        decision = _review_decision

    if decision == "APPROVED":
        return "allowed"
    return "blocked"


def check_push(command: str, *, base: str = "main") -> str:
    """Check whether a ``git push`` targets the base branch.

    Returns ``'blocked'`` for direct pushes to *base*, ``'allowed'``
    otherwise.
    """
    parts = command.split()
    if len(parts) < 2 or parts[0] != "git" or parts[1] != "push":
        return "allowed"

    # Separate flags from positional arguments
    positional: list[str] = []
    i = 2
    while i < len(parts):
        part = parts[i]
        if part in ("-u", "--set-upstream"):
            i += 1
            continue
        if part.startswith("-"):
            # Flags with separate values (e.g., --repo VALUE)
            if "=" not in part and part not in (
                "--force", "-f", "--force-with-lease",
                "--no-verify", "--verbose", "-v",
                "--dry-run", "-n", "--tags", "--all",
            ):
                i += 2  # skip flag + value
                continue
            i += 1
            continue
        positional.append(part)
        i += 1

    # positional[0] = remote, positional[1:] = refspecs
    if len(positional) >= 2:
        for refspec in positional[1:]:
            target = refspec.split(":")[-1] if ":" in refspec else refspec
            if target == base:
                return "blocked"

    return "allowed"


# ---------------------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------------------

def _log_blocked(command: str, reason: str) -> None:
    """Append a blocked attempt to the hook audit log."""
    log_dir = Path("sprint-config/sprints")
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "hook-audit.log"
    timestamp = datetime.datetime.now().isoformat()
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"{timestamp} BLOCKED: {reason} | command: {command}\n")


# ---------------------------------------------------------------------------
# Hook entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Read tool input from stdin JSON, decide allow/block."""
    try:
        input_data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        sys.exit(0)

    tool_input = input_data.get("tool_input", input_data.get("input", {}))
    command = tool_input.get("command", "")
    if not command:
        sys.exit(0)

    base = _get_base_branch()

    # Check for PR merge without approved review
    if "gh" in command and "pr" in command and "merge" in command:
        result = check_merge(command, base=base)
        if result == "blocked":
            reason = (
                "Review required: PR merge blocked because the PR has no "
                "approved review. Get a review approved before merging."
            )
            _log_blocked(command, reason)
            print(reason)
            sys.exit(2)

    # Check for direct push to base branch
    if "git" in command and "push" in command:
        result = check_push(command, base=base)
        if result == "blocked":
            reason = (
                f"Direct push to {base} is not allowed. "
                f"Create a PR instead."
            )
            _log_blocked(command, reason)
            print(reason)
            sys.exit(2)

    sys.exit(0)


if __name__ == "__main__":
    main()
