#!/usr/bin/env python3
"""Release gate validation and automation for sprint milestones.

Usage:
  python release_gate.py validate "Sprint 1: Walking Skeleton"
  python release_gate.py release "Sprint 1: Walking Skeleton"
  python release_gate.py --dry-run release "Sprint 1: Walking Skeleton"

Validates release gates (stories, CI, PRs, tests, build), calculates
the next semantic version from the conventional commit log, and creates
a GitHub Release with auto-generated notes.

Exit codes: 0 = success, 1 = gate failure, 2 = usage error
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# -- Import shared config and commit validation ------------------------------
_PLUGIN_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_SCRIPTS_DIR = _PLUGIN_ROOT / "scripts"
sys.path.insert(0, str(_SCRIPTS_DIR))
from validate_config import load_config, get_base_branch, gh, gh_json, warn_if_at_limit
COMMIT_PY = _SCRIPTS_DIR / "commit.py"


# -- Version calculation -----------------------------------------------------

_SEMVER_TAG_RE = re.compile(r"^v(\d+\.\d+\.\d+)$")


def find_latest_semver_tag() -> str | None:
    """Find the most recent vX.Y.Z tag, or None if no semver tags exist."""
    r = subprocess.run(
        ["git", "tag", "--list", "v*", "--sort=-version:refname"],
        capture_output=True, text=True,
    )
    if r.returncode != 0:
        return None
    for line in r.stdout.strip().splitlines():
        tag = line.strip()
        if _SEMVER_TAG_RE.match(tag):
            return tag
    return None


def parse_commits_since(tag: str | None) -> list[dict]:
    """Parse commits since tag (or all commits). Returns [{subject, body}]."""
    if tag:
        cmd = ["git", "log", f"{tag}..HEAD", "--format=%s%n%b---COMMIT---"]
    else:
        cmd = ["git", "log", "--format=%s%n%b---COMMIT---"]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        return []
    commits = []
    for chunk in r.stdout.split("---COMMIT---"):
        chunk = chunk.strip()
        if not chunk:
            continue
        lines = chunk.splitlines()
        commits.append({
            "subject": lines[0] if lines else "",
            "body": "\n".join(lines[1:]).strip() if len(lines) > 1 else "",
        })
    return commits


def determine_bump(commits: list[dict]) -> str:
    """Determine bump type from conventional commits.

    Returns 'major', 'minor', or 'patch'. Highest bump wins.
    """
    bump = "patch"
    for c in commits:
        subj = c["subject"]
        body = c["body"]
        # Breaking change -> major (immediate return)
        if "BREAKING CHANGE:" in body or "BREAKING-CHANGE:" in body:
            return "major"
        if re.match(r"^[a-z]+(\([^)]+\))?!:", subj):
            return "major"
        # Feature -> minor
        if re.match(r"^feat(\([^)]+\))?:", subj):
            bump = "minor"
    return bump


def bump_version(base: str, bump_type: str) -> str:
    """Apply bump to a version string. E.g., ('0.1.0', 'minor') -> '0.2.0'."""
    parts = base.lstrip("v").split(".")
    major, minor, patch = int(parts[0]), int(parts[1]), int(parts[2])
    if bump_type == "major":
        return f"{major + 1}.0.0"
    elif bump_type == "minor":
        return f"{major}.{minor + 1}.0"
    else:
        return f"{major}.{minor}.{patch + 1}"


def calculate_version() -> tuple[str, str, str, list[dict]]:
    """Calculate next semantic version from commit log.

    Returns (new_version, base_version, bump_type, commits).
    Base is 0.1.0 if no semver tags exist.
    """
    tag = find_latest_semver_tag()
    base = tag.lstrip("v") if tag else "0.1.0"
    commits = parse_commits_since(tag)
    if not commits:
        return base, base, "none", commits
    bump_type = determine_bump(commits)
    new_version = bump_version(base, bump_type)
    return new_version, base, bump_type, commits


# -- Gate validation ---------------------------------------------------------


def gate_stories(milestone_title: str) -> tuple[bool, str]:
    """Gate: all issues in the milestone must be closed."""
    issues = gh_json([
        "issue", "list", "--milestone", milestone_title,
        "--state", "open", "--json", "number,title", "--limit", "500",
    ])
    warn_if_at_limit(issues, 500)
    if not issues:
        return True, "All issues closed"
    titles = [f"#{i['number']}: {i['title']}" for i in issues[:5]]
    return False, f"{len(issues)} open: {', '.join(titles)}"


def gate_ci(config: dict) -> tuple[bool, str]:
    """Gate: most recent CI run on the base branch must be successful."""
    base_branch = get_base_branch(config)
    runs = gh_json([
        "run", "list", "--branch", base_branch, "--limit", "1",
        "--json", "status,conclusion,name",
    ])
    if not runs:
        return False, f"No CI runs found on {base_branch}"
    run = runs[0]
    if run.get("conclusion") == "success":
        return True, f"{run.get('name', 'CI')}: success"
    return False, (
        f"{run.get('name', 'CI')}: "
        f"{run.get('conclusion', run.get('status', 'unknown'))}"
    )


def gate_prs(milestone_title: str) -> tuple[bool, str]:
    """Gate: no open PRs should target this milestone."""
    prs = gh_json([
        "pr", "list",
        "--json", "number,title,milestone", "--limit", "500",
    ])
    warn_if_at_limit(prs, 500)
    matching = [
        p for p in prs
        if (p.get("milestone") or {}).get("title") == milestone_title
    ]
    if not matching:
        return True, "No open PRs for milestone"
    titles = [f"#{p['number']}: {p['title']}" for p in matching[:5]]
    return False, f"{len(matching)} open PR(s): {', '.join(titles)}"


def gate_tests(config: dict) -> tuple[bool, str]:
    """Gate: all check_commands from config must pass."""
    commands = config.get("ci", {}).get("check_commands", [])
    if not commands:
        return True, "No check_commands configured"
    for cmd in commands:
        # shell=True is intentional — commands are user-configured shell
        # expressions (e.g. "cargo test", "npm run lint") from project.toml.
        r = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=300,
        )
        if r.returncode != 0:
            return False, f"'{cmd}' failed (exit {r.returncode})"
    return True, f"{len(commands)} command(s) passed"


def gate_build(config: dict) -> tuple[bool, str]:
    """Gate: build_command must succeed and produce binary if configured."""
    build_cmd = config.get("ci", {}).get("build_command", "")
    if not build_cmd:
        return True, "No build_command configured"
    # shell=True is intentional — build_command is a user-configured shell
    # expression (e.g. "make build", "cargo build --release") from project.toml.
    r = subprocess.run(
        build_cmd, shell=True, capture_output=True, text=True, timeout=300,
    )
    if r.returncode != 0:
        return False, f"Build failed (exit {r.returncode})"
    binary = config.get("ci", {}).get("binary_path", "")
    if binary and not Path(binary).exists():
        return False, f"Binary not found at {binary}"
    return True, "Build succeeded"


def validate_gates(
    milestone_title: str, config: dict,
) -> tuple[bool, list[tuple[str, bool, str]]]:
    """Run all gates sequentially. First failure stops.

    Returns (all_passed, [(gate_name, passed, detail), ...]).
    """
    results: list[tuple[str, bool, str]] = []
    gates = [
        ("Stories", lambda: gate_stories(milestone_title)),
        ("CI", lambda: gate_ci(config)),
        ("PRs", lambda: gate_prs(milestone_title)),
        ("Tests", lambda: gate_tests(config)),
        ("Build", lambda: gate_build(config)),
    ]
    all_passed = True
    for name, fn in gates:
        passed, detail = fn()
        results.append((name, passed, detail))
        if not passed:
            all_passed = False
            break
    return all_passed, results


def print_gate_summary(results: list[tuple[str, bool, str]]) -> None:
    """Print the gate summary table."""
    print(f"\n{'Gate':<24} | {'Status':<6} | Detail")
    print(f"{'-' * 24}-|{'-' * 8}|{'-' * 40}")
    for name, passed, detail in results:
        status = "PASS" if passed else "FAIL"
        print(f"{name:<24} | {status:<6} | {detail}")
    print()


# -- TOML version writer -----------------------------------------------------


def write_version_to_toml(version: str, toml_path: Path) -> None:
    """Write version to [release] section in project.toml.

    Uses regex replacement on the raw file — no full TOML serializer.
    Creates [release] section if it doesn't exist.
    """
    text = toml_path.read_text(encoding="utf-8")

    release_section = re.search(r"^\[release\]", text, re.MULTILINE)
    if release_section:
        start = release_section.start()
        next_section = re.search(r"^\[", text[start + 1:], re.MULTILINE)
        end = (start + 1 + next_section.start()) if next_section else len(text)

        section_text = text[start:end]
        version_re = re.compile(r'^version\s*=\s*"[^"]*"', re.MULTILINE)
        if version_re.search(section_text):
            new_section = version_re.sub(
                f'version = "{version}"', section_text, count=1,
            )
            text = text[:start] + new_section + text[end:]
        else:
            insert_pos = start + len("[release]")
            # Find end of line after [release]
            nl = text.find("\n", insert_pos)
            if nl == -1:
                nl = len(text)
            text = text[:nl + 1] + f'version = "{version}"\n' + text[nl + 1:]
    else:
        text = text.rstrip() + f'\n\n[release]\nversion = "{version}"\n'

    toml_path.write_text(text, encoding="utf-8")


# -- Release notes -----------------------------------------------------------


def generate_release_notes(
    version: str,
    prev_version: str,
    commits: list[dict],
    milestone_title: str,
    config: dict,
) -> str:
    """Generate release notes from conventional commits.

    Structure: Highlights, Features, Fixes, Breaking Changes, Full Changelog.
    """
    repo = config.get("project", {}).get("repo", "{owner}/{repo}")

    feats: list[str] = []
    fixes: list[str] = []
    breaking: list[str] = []
    other: list[str] = []

    for c in commits:
        subj = c["subject"]
        body = c["body"]

        is_breaking = (
            "BREAKING CHANGE:" in body
            or "BREAKING-CHANGE:" in body
            or bool(re.match(r"^[a-z]+(\([^)]+\))?!:", subj))
        )
        if is_breaking:
            breaking.append(subj)

        if re.match(r"^feat(\([^)]+\))?!?:", subj):
            feats.append(subj)
        elif re.match(r"^fix(\([^)]+\))?!?:", subj):
            fixes.append(subj)
        else:
            other.append(subj)

    lines = [f"# {milestone_title} — v{version}", ""]

    # Highlights — top features, or fixes, or other
    highlights = (feats[:5] if feats else fixes[:3]) or other[:3]
    if highlights:
        lines += ["## Highlights", ""]
        for h in highlights[:5]:
            lines.append(f"- {h}")
        lines.append("")

    if feats:
        lines += ["## Features", ""]
        for f in feats:
            lines.append(f"- {f}")
        lines.append("")

    if fixes:
        lines += ["## Fixes", ""]
        for f in fixes:
            lines.append(f"- {f}")
        lines.append("")

    if breaking:
        lines += ["## Breaking Changes", ""]
        for b in breaking:
            lines.append(f"- {b}")
        lines.append("")

    prev_tag = f"v{prev_version}" if prev_version != version else ""
    if prev_tag:
        lines += [
            "## Full Changelog",
            "",
            f"https://github.com/{repo}/compare/{prev_tag}...v{version}",
            "",
        ]

    return "\n".join(lines)


# -- Release flow ------------------------------------------------------------


def find_milestone_number(milestone_title: str) -> int | None:
    """Find GitHub milestone number by title."""
    milestones = gh_json([
        "api", "repos/{owner}/{repo}/milestones", "--paginate",
    ])
    for ms in (milestones if isinstance(milestones, list) else []):
        if ms.get("title") == milestone_title:
            return ms["number"]
    return None


def do_release(
    milestone_title: str, config: dict, dry_run: bool = False,
) -> bool:
    """Execute the full release flow. Returns True on success.

    Pre-flight: validates COMMIT_PY exists and working tree is clean.
    On failure: prints completed vs failed steps and restores project.toml
    if it was modified but not committed.
    """
    project_name = config.get("project", {}).get("name", "Project")
    toml_path = Path("sprint-config/project.toml")
    completed_steps: list[str] = []

    # Pre-flight checks
    if not COMMIT_PY.exists():
        print(f"Error: {COMMIT_PY} not found", file=sys.stderr)
        return False
    r = subprocess.run(
        ["git", "status", "--porcelain"], capture_output=True, text=True,
    )
    if r.returncode != 0 or r.stdout.strip():
        print("Error: working tree is not clean (commit or stash changes first)",
              file=sys.stderr)
        return False

    # 1. Calculate version
    new_ver, base_ver, bump_type, commits = calculate_version()
    if bump_type == "none":
        print("No commits since last tag. Nothing to release.")
        return False

    print(f"Version: {base_ver} -> {new_ver} ({bump_type} bump)")
    print(f"  Based on {len(commits)} commit(s) since v{base_ver}")

    def _fail(step: str, msg: str) -> bool:
        print(f"{msg}", file=sys.stderr)
        if completed_steps:
            print(f"Completed: {', '.join(completed_steps)}", file=sys.stderr)
        print(f"Failed at: {step}", file=sys.stderr)
        return False

    if dry_run:
        print(f"\n[DRY-RUN] Would write version {new_ver} to {toml_path}")
        print(f"[DRY-RUN] Would commit: chore: bump version to {new_ver}")
        print(f"[DRY-RUN] Would create tag: v{new_ver}")
        print(f"[DRY-RUN] Would push tag: git push origin v{new_ver}")
    else:
        # 2-3. Write version and commit
        write_version_to_toml(new_ver, toml_path)
        completed_steps.append("write-version")
        r = subprocess.run(
            ["git", "add", str(toml_path)], capture_output=True, text=True,
        )
        if r.returncode != 0:
            subprocess.run(
                ["git", "reset", "HEAD", "--", str(toml_path)],
                capture_output=True, text=True,
            )
            subprocess.run(
                ["git", "checkout", "--", str(toml_path)],
                capture_output=True, text=True,
            )
            return _fail("git-add", f"git add failed: {r.stderr.strip()}")
        r = subprocess.run(
            [sys.executable, str(COMMIT_PY), f"chore: bump version to {new_ver}"],
            capture_output=True, text=True,
        )
        if r.returncode != 0:
            subprocess.run(
                ["git", "reset", "HEAD", "--", str(toml_path)],
                capture_output=True, text=True,
            )
            subprocess.run(
                ["git", "checkout", "--", str(toml_path)],
                capture_output=True, text=True,
            )
            return _fail("commit", f"Version commit failed: {r.stderr}")
        completed_steps.append("commit-version")

        # 4-5. Tag and push
        r = subprocess.run(
            ["git", "tag", "-a", f"v{new_ver}",
             "-m", f"Release {new_ver}: {milestone_title}"],
            capture_output=True, text=True,
        )
        if r.returncode != 0:
            return _fail("create-tag", f"Tag creation failed: {r.stderr.strip()}")
        completed_steps.append("create-tag")
        r = subprocess.run(
            ["git", "push", "origin", f"v{new_ver}"],
            capture_output=True, text=True,
        )
        if r.returncode != 0:
            return _fail("push-tag", f"Tag push failed: {r.stderr.strip()}")
        completed_steps.append("push-tag")

    # 6. Generate release notes
    notes = generate_release_notes(
        new_ver, base_ver, commits, milestone_title, config,
    )
    notes_path = Path("release-notes.md")

    if dry_run:
        print("\n[DRY-RUN] Release notes:\n")
        print(notes)
        print(f"\n[DRY-RUN] Would create GitHub Release v{new_ver}")
    else:
        notes_path.write_text(notes, encoding="utf-8")

        # 7. Create GitHub Release
        release_args = [
            "release", "create", f"v{new_ver}",
            "--title", f"{project_name} {new_ver}",
            "--notes-file", str(notes_path),
        ]
        binary = config.get("ci", {}).get("binary_path", "")
        if binary and Path(binary).exists():
            release_args.append(binary)
        gh(release_args)
        completed_steps.append("github-release")

        # Clean up notes file
        notes_path.unlink(missing_ok=True)

    # 8. Close milestone
    ms_num = find_milestone_number(milestone_title)
    if ms_num is not None:
        if dry_run:
            print(f"[DRY-RUN] Would close milestone #{ms_num}")
        else:
            gh([
                "api", f"repos/{{owner}}/{{repo}}/milestones/{ms_num}",
                "-X", "PATCH", "-f", "state=closed",
            ])
            completed_steps.append("close-milestone")
            print(f"Milestone '{milestone_title}' closed.")
    else:
        print(f"Warning: milestone '{milestone_title}' not found on GitHub")

    # 9. Update SPRINT-STATUS.md
    sprints_dir = Path(
        config.get("paths", {}).get("sprints_dir", "sprints")
    )
    status_file = sprints_dir / "SPRINT-STATUS.md"
    if status_file.exists():
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        row = (
            f"| {milestone_title} Release | Released "
            f"| {now} | — | v{new_ver} |"
        )
        if dry_run:
            print(f"[DRY-RUN] Would append to SPRINT-STATUS.md: {row}")
        else:
            with open(status_file, "a", encoding="utf-8") as f:
                f.write(f"\n{row}\n")
            completed_steps.append("update-status")

    # 10. Print release URL
    if not dry_run:
        try:
            url = gh([
                "release", "view", f"v{new_ver}", "--json", "url", "--jq", ".url",
            ])
            print(f"\nRelease published: {url}")
        except RuntimeError:
            print(f"\nRelease v{new_ver} created (could not fetch URL)")

    return True


# -- CLI ---------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Release gate validation and automation",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Preview all operations without executing mutations",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    val_parser = sub.add_parser("validate", help="Run gate checks only")
    val_parser.add_argument("milestone", help="Milestone title")

    rel_parser = sub.add_parser("release", help="Validate gates then release")
    rel_parser.add_argument("milestone", help="Milestone title")

    args = parser.parse_args()
    config = load_config()

    if args.command == "validate":
        print(f"=== Gate Validation: {args.milestone} ===")
        passed, results = validate_gates(args.milestone, config)
        print_gate_summary(results)
        sys.exit(0 if passed else 1)

    elif args.command == "release":
        print(f"=== Release: {args.milestone} ===")
        if args.dry_run:
            print("[DRY-RUN MODE]\n")

        passed, results = validate_gates(args.milestone, config)
        print_gate_summary(results)
        if not passed:
            print("Release blocked by gate failure.")
            sys.exit(1)

        print("All gates passed. Proceeding to release.\n")
        ok = do_release(args.milestone, config, dry_run=args.dry_run)
        sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
