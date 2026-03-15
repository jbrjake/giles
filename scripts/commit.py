#!/usr/bin/env python3
"""Enforce conventional commits and atomic changes.

Usage:
  python commit.py "feat: add authentication"
  python commit.py "fix(parser): handle empty input"
  python commit.py --body "BREAKING CHANGE: removed old API" "feat!: new API"
  python commit.py --dry-run "feat: preview commit"
  python commit.py --force "refactor: broad cleanup across dirs"

Conventional commit format: <type>[(scope)][!]: <description>

Types: feat, fix, refactor, test, docs, chore, ci, perf, build, style

Exit codes: 0 = success, 1 = validation failure or git error
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys

VALID_TYPES = frozenset({
    "feat", "fix", "refactor", "test", "docs",
    "chore", "ci", "perf", "build", "style",
})

CC_RE = re.compile(
    r"^(?P<type>" + "|".join(sorted(VALID_TYPES)) + r")"
    r"(?:\((?P<scope>[a-zA-Z0-9_.-]+)\))?"
    r"(?P<breaking>!)?"
    r":\s+(?P<desc>.+)$"
)


# §commit.validate_message
def validate_message(message: str) -> tuple[bool, str]:
    """Validate a conventional commit message.

    Returns (ok, error_message). error_message is empty on success.
    """
    if not message or not message.strip():
        return False, "Commit message is empty"
    first_line = message.strip().splitlines()[0]
    m = CC_RE.match(first_line)
    if not m:
        return False, (
            f"Invalid conventional commit: '{first_line}'\n"
            f"Expected: <type>[(scope)][!]: <description>\n"
            f"Types: {', '.join(sorted(VALID_TYPES))}"
        )
    if not m.group("desc").strip():
        return False, "Description after colon is empty"
    return True, ""


# §commit.check_atomicity
def check_atomicity(force: bool = False) -> tuple[bool, str]:
    """Check staged files don't span too many top-level directories.

    Returns (ok, warning_message). warning_message is empty on success.
    Requires --force if files span 3+ top-level directories.
    """
    r = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        capture_output=True, text=True,
    )
    if r.returncode != 0:
        return False, f"git diff failed: {r.stderr.strip()}"
    files = [f for f in r.stdout.strip().splitlines() if f]
    if not files:
        return False, "No staged changes to commit"
    dirs = set()
    for f in files:
        parts = f.split("/")
        dirs.add(parts[0] if len(parts) > 1 else "(root)")
    if len(dirs) >= 3:
        warning = (
            f"Staged files span {len(dirs)} directories: "
            f"{', '.join(sorted(dirs))}"
        )
        if not force:
            return False, (
                f"{warning}\n"
                f"Consider splitting into atomic commits, or use --force."
            )
        return True, f"{warning} (overridden by --force)"
    return True, ""


# §commit.run_commit
def run_commit(message: str, body: str = "") -> tuple[bool, str]:
    """Execute git commit. Returns (ok, output_or_error)."""
    args = ["git", "commit", "-m", message]
    if body:
        args.extend(["-m", body])
    r = subprocess.run(args, capture_output=True, text=True)
    if r.returncode != 0:
        return False, r.stderr.strip()
    return True, r.stdout.strip()


# §commit.main
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Conventional commit wrapper with atomicity enforcement",
    )
    parser.add_argument("message", help="Commit message (conventional format)")
    parser.add_argument(
        "--body", default="",
        help="Commit body (for BREAKING CHANGE trailers)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Validate and show what would be committed, without committing",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Override atomicity warning for cross-cutting changes",
    )
    args = parser.parse_args()

    # Validate message
    ok, err = validate_message(args.message)
    if not ok:
        print(f"REJECTED: {err}", file=sys.stderr)
        sys.exit(1)

    # Check atomicity
    ok, warning = check_atomicity(force=args.force)
    if not ok:
        if "No staged changes" in warning:
            print(f"REJECTED: {warning}", file=sys.stderr)
        else:
            print(f"WARNING: {warning}", file=sys.stderr)
        sys.exit(1)
    if warning:
        # --force was used; print the overridden warning for visibility
        print(f"NOTE: {warning}", file=sys.stderr)

    if args.dry_run:
        print(f"[DRY-RUN] Would commit: {args.message}")
        if args.body:
            print(f"[DRY-RUN] Body: {args.body}")
        sys.exit(0)

    ok, output = run_commit(args.message, args.body)
    if not ok:
        print(f"Commit failed: {output}", file=sys.stderr)
        sys.exit(1)
    print(output)


if __name__ == "__main__":
    main()
