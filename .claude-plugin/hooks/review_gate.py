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

from hooks._common import _find_project_root


# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------

def _get_base_branch() -> str:
    """Read base_branch from project.toml's [project] section, defaulting to 'main'."""
    try:
        toml_path = _find_project_root() / "sprint-config" / "project.toml"
        if not toml_path.is_file():
            return "main"
        text = toml_path.read_text(encoding="utf-8")
        current_section = ""
        for line in text.splitlines():
            section_m = re.match(r'^\s*\[([^\]]+)\]', line)
            if section_m:
                current_section = section_m.group(1).strip()
                continue
            if current_section == "project":
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

    When ``gh pr merge`` is invoked without an explicit PR number we
    cannot look up the review status, so we fail closed (return
    ``'blocked'``).

    The *_review_decision* parameter is for testing — when provided,
    skips the actual GitHub API call.
    """
    # Match with an explicit PR number
    m = re.search(r'gh\s+pr\s+merge\s+(\d+)', command)
    if m:
        pr_number = m.group(1)
        if _review_decision is None:
            decision = _query_review_decision(pr_number)
        else:
            decision = _review_decision
        if decision == "APPROVED":
            return "allowed"
        return "blocked"

    # Match without a PR number (e.g. "gh pr merge" or "gh pr merge --squash")
    if re.search(r'gh\s+pr\s+merge(?:\s|$)', command):
        return "blocked"

    return "allowed"


def check_push(command: str, *, base: str = "main") -> str:
    """Check whether a ``git push`` targets the base branch.

    Returns ``'blocked'`` for direct pushes to *base*, ``'warn'`` for
    bare ``git push`` (could push to base if upstream is set),
    ``'allowed'`` otherwise.

    Handles compound shell commands (``&&``, ``;``, ``|``) by splitting
    on shell operators and checking each subcommand.
    """
    # BH27-005: Split compound commands and check each subcommand
    # BH35-007: Also split on single pipe |  (match || before | via ordering)
    for subcommand in re.split(r'\s*(?:&&|\|\||\||;)\s*', command):
        result = _check_push_single(subcommand.strip(), base=base)
        if result != "allowed":
            return result
    return "allowed"


def _check_push_single(command: str, *, base: str = "main") -> str:
    """Check a single (non-compound) command for git push to base."""
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
                "--delete", "-d", "--mirror",  # BH33-001
            ):
                i += 2  # skip flag + value
                continue
            i += 1
            continue
        positional.append(part)
        i += 1

    # BH33-001: --mirror pushes ALL refs (including base) and deletes remote
    # refs not present locally. Always block — too destructive to allow.
    # BH34-002: --all pushes every local branch, including base. Same risk class.
    if "--mirror" in parts or "--all" in parts:
        return "blocked"

    # Bare "git push" with no remote or refspec — could push to base branch
    # if current branch tracks origin/base. Warn rather than silently allow.
    if not positional:
        return "warn"

    # positional[0] = remote, positional[1:] = refspecs
    if len(positional) >= 2:
        for refspec in positional[1:]:
            target = refspec.split(":")[-1] if ":" in refspec else refspec
            # BH35-002: Strip leading + (force-push refspec prefix)
            target = target.lstrip("+")
            # BH35-003: Strip refs/heads/ prefix (full ref path)
            if target.startswith("refs/heads/"):
                target = target[len("refs/heads/"):]
            if target == base:
                return "blocked"

    return "allowed"


# ---------------------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------------------

def _log_blocked(command: str, reason: str) -> None:
    """Append a blocked attempt to the hook audit log.

    Only writes if sprint-config/project.toml exists — avoids creating
    sprint-config/ directories in projects that don't use giles.
    """
    root = _find_project_root()
    toml_path = root / "sprint-config" / "project.toml"
    if not toml_path.is_file():
        return
    # Read sprints_dir from config, fall back to sprint-config/sprints
    sprints_dir = "sprint-config/sprints"
    try:
        text = toml_path.read_text(encoding="utf-8")
        in_paths = False
        for line in text.splitlines():
            s = line.strip()
            if s.startswith("["):
                in_paths = s == "[paths]"
                continue
            if in_paths:
                m = re.match(r'sprints_dir\s*=\s*["\']([^"\']*)["\']', s)
                if m:
                    sprints_dir = m.group(1)
                    break
    except Exception:
        pass
    log_dir = root / sprints_dir
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "hook-audit.log"
    timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
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
        if result == "warn":
            print(
                f"Warning: bare 'git push' may push to {base} if the "
                f"current branch tracks origin/{base}. "
                f"Specify a remote and branch explicitly."
            )
            # Don't block — just warn. The user might be on a feature branch.

    sys.exit(0)


if __name__ == "__main__":
    main()
