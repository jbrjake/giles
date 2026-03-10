# Giles Max Confidence Ship — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship giles with full release automation, enforced conventional commits, auto-calculated semver, mock-based tests, and lifecycle integration harness.

**Architecture:** Two new scripts (`scripts/commit.py` for commit enforcement, `skills/sprint-release/scripts/release_gate.py` for release automation) plus two test suites (`scripts/test_gh_interactions.py` for unit tests, `scripts/test_lifecycle.py` for end-to-end). Mechanical fixes to 9 existing scripts (--help), 4 SKILL.md files (gh commands + commit.py refs), and a new README.md. All Python stdlib-only — no new dependencies.

**Tech Stack:** Python 3.10+ (stdlib only), Markdown, YAML frontmatter, gh CLI

**Spec:** `docs/superpowers/specs/2026-03-09-giles-max-confidence-design.md`

**Parallelism:** Chunks 1-3 are sequential (commit.py -> release_gate.py). Chunk 4 is independent — can run in parallel with Chunks 1-3. Chunk 5 depends on Chunks 1-3. Chunk 6 depends on everything.

---

## Chunk 1: `scripts/commit.py` — Conventional Commit Wrapper

### Task 1: Core validation — `validate_message()`

**Files:**
- Create: `scripts/commit.py`

- [ ] **Step 1: Create `scripts/commit.py` with module docstring, imports, and `validate_message()`**

```python
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
```

- [ ] **Step 2: Verify it compiles**

Run: `python3 -m py_compile scripts/commit.py`
Expected: no output (success)

- [ ] **Step 3: Commit**

```bash
git add scripts/commit.py
git commit -m "feat: add commit.py with validate_message()

Conventional commit message validator. Enforces type[(scope)][!]: description
format with 10 allowed types. Foundation for commit enforcement across all skills."
```

---

### Task 2: Atomicity check — `check_atomicity()`

**Files:**
- Modify: `scripts/commit.py`

- [ ] **Step 1: Add `check_atomicity()` after `validate_message()`**

```python
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
```

- [ ] **Step 2: Verify it compiles**

Run: `python3 -m py_compile scripts/commit.py`
Expected: no output (success)

- [ ] **Step 3: Commit**

```bash
git add scripts/commit.py
git commit -m "feat(commit): add atomicity enforcement

check_atomicity() warns when staged files span 3+ top-level directories.
Soft block with --force escape hatch."
```

---

### Task 3: Git commit execution + CLI

**Files:**
- Modify: `scripts/commit.py`

- [ ] **Step 1: Add `run_commit()` and `main()` with argparse**

```python
def run_commit(message: str, body: str = "") -> tuple[bool, str]:
    """Execute git commit. Returns (ok, output_or_error)."""
    args = ["git", "commit", "-m", message]
    if body:
        args.extend(["-m", body])
    r = subprocess.run(args, capture_output=True, text=True)
    if r.returncode != 0:
        return False, r.stderr.strip()
    return True, r.stdout.strip()


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
```

- [ ] **Step 2: Verify it compiles**

Run: `python3 -m py_compile scripts/commit.py`
Expected: no output (success)

- [ ] **Step 3: Test help output**

Run: `python3 scripts/commit.py --help`
Expected: argparse help text showing message, --body, --dry-run, --force

- [ ] **Step 4: Test validation rejection**

Run: `python3 scripts/commit.py "bad message without type"`
Expected: exit 1, stderr shows "REJECTED: Invalid conventional commit"

- [ ] **Step 5: Test validation acceptance (dry-run, no git repo needed)**

Run: `cd /tmp && python3 /Users/jonr/Documents/non-nitro-repos/giles/scripts/commit.py --dry-run "feat: test message"`
Expected: exit 1 with "No staged changes" (since /tmp isn't a git repo with staged changes — the atomicity check runs git diff which will fail). That's OK — we'll test the full flow in the test suite.

- [ ] **Step 6: Commit**

```bash
git add scripts/commit.py
git commit -m "feat(commit): add CLI with argparse and git execution

Complete commit.py: validates message, checks atomicity, runs git commit.
Supports --dry-run, --body, and --force flags."
```

---

## Chunk 2: `release_gate.py` — Version Calculation & Gate Validation

### Task 4: Version calculation from commit log

**Files:**
- Create: `skills/sprint-release/scripts/release_gate.py`

- [ ] **Step 0: Create the scripts directory**

Run: `mkdir -p skills/sprint-release/scripts`

- [ ] **Step 1: Create `release_gate.py` with docstring, imports, and version functions**

```python
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
from validate_config import load_config
from commit import validate_message

COMMIT_PY = _SCRIPTS_DIR / "commit.py"


def gh(args: list[str]) -> str:
    """Run a gh CLI command and return stdout."""
    r = subprocess.run(
        ["gh", *args], capture_output=True, text=True, timeout=30,
    )
    if r.returncode != 0:
        raise RuntimeError(f"gh {' '.join(args)}: {r.stderr.strip()}")
    return r.stdout.strip()


def gh_json(args: list[str]) -> list | dict:
    """Run a gh CLI command and parse JSON output."""
    raw = gh(args)
    return json.loads(raw) if raw else []


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
```

- [ ] **Step 2: Verify it compiles**

Run: `python3 -m py_compile skills/sprint-release/scripts/release_gate.py`
Expected: no output (success)

- [ ] **Step 3: Commit**

```bash
git add skills/sprint-release/scripts/release_gate.py
git commit -m "feat(release): add version calculation from commit log

find_latest_semver_tag(), parse_commits_since(), determine_bump(),
bump_version(), calculate_version(). Base version 0.1.0 when no
semver tags exist. Bump rules: breaking->major, feat->minor, else->patch."
```

---

### Task 5: Gate validation functions

**Files:**
- Modify: `skills/sprint-release/scripts/release_gate.py`

- [ ] **Step 1: Add gate functions after the version calculation section**

```python
# -- Gate validation ---------------------------------------------------------


def gate_stories(milestone_title: str) -> tuple[bool, str]:
    """Gate: all issues in the milestone must be closed."""
    issues = gh_json([
        "issue", "list", "--milestone", milestone_title,
        "--state", "open", "--json", "number,title", "--limit", "200",
    ])
    if not issues:
        return True, "All issues closed"
    titles = [f"#{i['number']}: {i['title']}" for i in issues[:5]]
    return False, f"{len(issues)} open: {', '.join(titles)}"


def gate_ci() -> tuple[bool, str]:
    """Gate: most recent CI run on main must be successful."""
    runs = gh_json([
        "run", "list", "--branch", "main", "--limit", "1",
        "--json", "status,conclusion,name",
    ])
    if not runs:
        return False, "No CI runs found on main"
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
        "--json", "number,title,milestone", "--limit", "200",
    ])
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
        ("CI", gate_ci),
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
```

- [ ] **Step 2: Verify it compiles**

Run: `python3 -m py_compile skills/sprint-release/scripts/release_gate.py`
Expected: no output (success)

- [ ] **Step 3: Commit**

```bash
git add skills/sprint-release/scripts/release_gate.py
git commit -m "feat(release): add gate validation functions

Five gates: stories (all closed), CI (main passing), PRs (none open),
tests (check_commands pass), build (build_command succeeds). Sequential
execution, first failure stops. Gate summary table output."
```

---

### Task 6: TOML version writer

**Files:**
- Modify: `skills/sprint-release/scripts/release_gate.py`

- [ ] **Step 1: Add `write_version_to_toml()` after the gate functions**

```python
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
```

- [ ] **Step 2: Verify it compiles**

Run: `python3 -m py_compile skills/sprint-release/scripts/release_gate.py`
Expected: no output (success)

- [ ] **Step 3: Commit**

```bash
git add skills/sprint-release/scripts/release_gate.py
git commit -m "feat(release): add TOML version writer

write_version_to_toml() uses regex replacement on raw file.
Creates [release] section if missing, updates version key if present."
```

---

## Chunk 3: `release_gate.py` — Release Flow, Notes & CLI

### Task 7: Release notes generator

**Files:**
- Modify: `skills/sprint-release/scripts/release_gate.py`

- [ ] **Step 1: Add `generate_release_notes()` after the TOML writer**

```python
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
```

- [ ] **Step 2: Verify it compiles**

Run: `python3 -m py_compile skills/sprint-release/scripts/release_gate.py`
Expected: no output (success)

- [ ] **Step 3: Commit**

```bash
git add skills/sprint-release/scripts/release_gate.py
git commit -m "feat(release): add release notes generator

Groups conventional commits into Highlights, Features, Fixes,
Breaking Changes, and Full Changelog sections."
```

---

### Task 8: Release flow + dry-run

**Files:**
- Modify: `skills/sprint-release/scripts/release_gate.py`

- [ ] **Step 1: Add the release flow function**

```python
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
    """Execute the full release flow. Returns True on success."""
    project_name = config.get("project", {}).get("name", "Project")
    toml_path = Path("sprint-config/project.toml")

    # 1. Calculate version
    new_ver, base_ver, bump_type, commits = calculate_version()
    if bump_type == "none":
        print("No commits since last tag. Nothing to release.")
        return False

    print(f"Version: {base_ver} -> {new_ver} ({bump_type} bump)")
    print(f"  Based on {len(commits)} commit(s) since v{base_ver}")

    if dry_run:
        print(f"\n[DRY-RUN] Would write version {new_ver} to {toml_path}")
        print(f"[DRY-RUN] Would commit: chore: bump version to {new_ver}")
        print(f"[DRY-RUN] Would create tag: v{new_ver}")
        print(f"[DRY-RUN] Would push tag: git push origin v{new_ver}")
    else:
        # 2-3. Write version and commit
        write_version_to_toml(new_ver, toml_path)
        subprocess.run(["git", "add", str(toml_path)], check=True)
        r = subprocess.run(
            [sys.executable, str(COMMIT_PY), f"chore: bump version to {new_ver}"],
            capture_output=True, text=True,
        )
        if r.returncode != 0:
            print(f"Version commit failed: {r.stderr}", file=sys.stderr)
            return False

        # 4-5. Tag and push
        subprocess.run(
            ["git", "tag", "-a", f"v{new_ver}",
             "-m", f"Release {new_ver}: {milestone_title}"],
            check=True,
        )
        subprocess.run(
            ["git", "push", "origin", f"v{new_ver}"], check=True,
        )

    # 6. Generate release notes
    notes = generate_release_notes(
        new_ver, base_ver, commits, milestone_title, config,
    )
    notes_path = Path("release-notes.md")

    if dry_run:
        print(f"\n[DRY-RUN] Release notes:\n")
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
```

- [ ] **Step 2: Verify it compiles**

Run: `python3 -m py_compile skills/sprint-release/scripts/release_gate.py`
Expected: no output (success)

- [ ] **Step 3: Commit**

```bash
git add skills/sprint-release/scripts/release_gate.py
git commit -m "feat(release): add full release flow with dry-run

do_release() handles version bump, tagging, push, release notes,
GitHub Release creation, milestone close, and status update.
All mutations skipped in --dry-run mode."
```

---

### Task 9: CLI with argparse

**Files:**
- Modify: `skills/sprint-release/scripts/release_gate.py`

- [ ] **Step 1: Add `main()` with argparse subcommands**

```python
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
```

- [ ] **Step 2: Verify it compiles**

Run: `python3 -m py_compile skills/sprint-release/scripts/release_gate.py`
Expected: no output (success)

- [ ] **Step 3: Test help output**

Run: `python3 skills/sprint-release/scripts/release_gate.py --help`
Expected: argparse help showing validate/release subcommands and --dry-run

- [ ] **Step 4: Commit**

```bash
git add skills/sprint-release/scripts/release_gate.py
git commit -m "feat(release): add CLI with validate and release subcommands

argparse with --dry-run flag. validate runs gates only.
release runs gates then full release flow."
```

---

## Chunk 4: Fixes, References & README (independent — can run in parallel with Chunks 1-3)

### Task 10: Add `--help` guard to all 9 existing scripts

**Files:**
- Modify: `scripts/validate_config.py:454`
- Modify: `scripts/sprint_init.py:660`
- Modify: `scripts/sprint_teardown.py:347`
- Modify: `skills/sprint-setup/scripts/bootstrap_github.py:220`
- Modify: `skills/sprint-setup/scripts/populate_issues.py:311`
- Modify: `skills/sprint-setup/scripts/setup_ci.py:304`
- Modify: `skills/sprint-monitor/scripts/check_status.py:267`
- Modify: `skills/sprint-run/scripts/sync_tracking.py:276`
- Modify: `skills/sprint-run/scripts/update_burndown.py:208`

- [ ] **Step 1: Add the help guard to each script's `main()`**

In each file, add these 3 lines immediately after the `def main() -> None:` line (before any existing logic):

```python
    if len(sys.argv) > 1 and sys.argv[1] in ("-h", "--help"):
        print(__doc__.strip())
        sys.exit(0)
```

Apply to all 9 files listed above. The guard goes right after `def main() -> None:` and before any existing code in main.

- [ ] **Step 2: Verify all 9 files compile**

Run: `for f in scripts/validate_config.py scripts/sprint_init.py scripts/sprint_teardown.py skills/sprint-setup/scripts/bootstrap_github.py skills/sprint-setup/scripts/populate_issues.py skills/sprint-setup/scripts/setup_ci.py skills/sprint-monitor/scripts/check_status.py skills/sprint-run/scripts/sync_tracking.py skills/sprint-run/scripts/update_burndown.py; do python3 -m py_compile "$f" && echo "OK: $f" || echo "FAIL: $f"; done`
Expected: all 9 show OK

- [ ] **Step 3: Spot-check help output on 2-3 scripts**

Run: `python3 scripts/validate_config.py --help | head -5`
Expected: first 5 lines of the module docstring

Run: `python3 scripts/sprint_init.py --help | head -5`
Expected: first 5 lines of the module docstring

- [ ] **Step 4: Commit**

```bash
git add scripts/validate_config.py scripts/sprint_init.py scripts/sprint_teardown.py \
  skills/sprint-setup/scripts/bootstrap_github.py skills/sprint-setup/scripts/populate_issues.py \
  skills/sprint-setup/scripts/setup_ci.py skills/sprint-monitor/scripts/check_status.py \
  skills/sprint-run/scripts/sync_tracking.py skills/sprint-run/scripts/update_burndown.py
git commit -m "feat: add --help support to all 9 existing scripts

Each script now shows its module docstring when invoked with -h or --help
instead of crashing. No argparse — just a 3-line guard in main()."
```

---

### Task 11: Fix SKILL.md gh command issues

**Files:**
- Modify: `skills/sprint-release/SKILL.md:170-178`
- Modify: `skills/sprint-monitor/SKILL.md:139`
- Modify: `skills/sprint-run/agents/reviewer.md:100`

- [ ] **Step 1: Fix sprint-release/SKILL.md milestone close block**

Replace lines 170-178 (the milestone close section) with:

```markdown
### Close the GitHub Milestone

```bash
milestone_number=$(gh api repos/{owner}/{repo}/milestones \
  --jq ".[] | select(.title == \"${milestone_title}\") | .number")
gh api repos/{owner}/{repo}/milestones/${milestone_number} \
  -X PATCH -f state=closed
```

Note: `{owner}` and `{repo}` are auto-expanded by `gh api`. `${milestone_title}` is a shell variable.
```

Key changes: use `repos/{owner}/{repo}/` (auto-placeholder), use `==` instead of `contains` in jq, and use double-quoted `--jq` so `${milestone_title}` expands.

- [ ] **Step 2: Fix sprint-monitor/SKILL.md line 139**

Replace the `repos/${repo}/milestones` reference with `repos/{owner}/{repo}/milestones`.

- [ ] **Step 3: Fix reviewer.md line 100**

Replace `repos/${repo}/pulls/` with `repos/{owner}/{repo}/pulls/`.

- [ ] **Step 4: Fix sprint-monitor/SKILL.md line 138 comment**

The line above the `repos/` fix says `# Read repo from project.toml [project] repo`. Update to clarify that `{owner}/{repo}` are auto-expanded by `gh api`, not shell variables. Replace with: `# {owner} and {repo} are auto-expanded by gh api from the git remote`

- [ ] **Step 5: Commit**

```bash
git add skills/sprint-release/SKILL.md skills/sprint-monitor/SKILL.md \
  skills/sprint-run/agents/reviewer.md
git commit -m "fix: use gh api auto-placeholders consistently in SKILL.md

Replace repos/\${repo}/ with repos/{owner}/{repo}/ to match the pattern
used by all Python scripts. Fix jq expansion bug in sprint-release
milestone close command."
```

---

### Task 12: Add commit.py references to skills and agents

**Files:**
- Modify: `skills/sprint-run/SKILL.md`
- Modify: `skills/sprint-run/agents/implementer.md`
- Modify: `skills/sprint-setup/SKILL.md`
- Modify: `skills/sprint-release/SKILL.md`

- [ ] **Step 1: Add commit convention note to sprint-run/SKILL.md**

Find the Phase 2 story execution section. After the branch creation step, add:

```markdown
#### Commit Convention

All commits MUST use the conventional commit wrapper:

```bash
python {plugin_root}/scripts/commit.py "feat(module): description"
```

Do not use raw `git commit -m`. The wrapper validates message format and
checks atomicity. See `scripts/commit.py --help` for flags.
```

- [ ] **Step 2: Add commit instruction to implementer.md**

After the "Push commits to your branch" line (line 66), add:

```markdown
- All commits use the conventional commit wrapper: `python {plugin_root}/scripts/commit.py "type(scope): description"`
```

- [ ] **Step 3: Add commit note to sprint-setup/SKILL.md**

In the post-setup verification section, add a note that the CI workflow commit should use:
```
python {plugin_root}/scripts/commit.py "ci: add GitHub Actions workflow"
```

- [ ] **Step 4: Add commit enforcement note to reviewer.md**

After the review checklist section, add:

```markdown
#### Commit Format Enforcement
When requesting changes, verify that all commits on the PR branch follow conventional
commit format. If any commit messages are malformed, flag them in the review.
```

- [ ] **Step 5: Add commit note to sprint-release/SKILL.md**

In the prerequisites section, add:
```markdown
4. **Conventional commits.** All commits since the last release tag must follow
   conventional commit format. The release script calculates the version from
   the commit log. Run `python {plugin_root}/scripts/commit.py --help` for format.
```

- [ ] **Step 6: Commit**

```bash
git add skills/sprint-run/SKILL.md skills/sprint-run/agents/implementer.md \
  skills/sprint-run/agents/reviewer.md skills/sprint-setup/SKILL.md \
  skills/sprint-release/SKILL.md
git commit -m "docs: add commit.py references to all skills and agents

Skills now reference scripts/commit.py instead of raw git commit.
Reviewer agent checks commit format. Conventional commit enforcement
across the entire sprint lifecycle."
```

---

### Task 13: README.md

**Files:**
- Create: `README.md`

- [ ] **Step 1: Write README.md**

```markdown
# giles

Agile sprint orchestration plugin for Claude Code. Runs sprints with persona-based
development — fictional team members implement stories, review PRs, and run
ceremonies in character.

## Prerequisites

Before installing giles, make sure you have:

- **Claude Code** — [claude.ai/code](https://claude.ai/code)
- **GitHub CLI** — installed and authenticated (`gh auth login`)
- **Git** — with a GitHub remote configured
- **Python 3.10+** — for scripts (stdlib only, no pip packages needed)
- **Superpowers plugin** — install with `claude plugin add anthropic/superpowers`

## Install

```bash
claude plugin add jbrjake/giles
```

Available from [jbrjake/claude-plugin-marketplace](https://github.com/jbrjake/claude-plugin-marketplace).

## Prepare Your Project

giles auto-detects your project structure, but works best when you have:

### Team Personas

Markdown files with these headings (one file per persona):

```markdown
# Persona Name

## Role
Senior Engineer

## Voice
Direct and technical.

## Domain
Backend systems.

## Background
10 years experience.

## Review Focus
Performance and correctness.
```

### Sprint Backlog

Milestone docs with story tables:

```markdown
# Sprint 1: Walking Skeleton

### Sprint 1: Foundation

| US-0101 | Basic setup | S01 | 3 | P0 |
| US-0102 | Core feature | S01 | 5 | P1 |
```

Columns: Story ID | Title | Saga | Story Points | Priority

### Optional Files

- **Rules doc** — project conventions and constraints
- **Development guide** — dev process documentation
- **Architecture doc** — system design reference

## First Run

1. **Setup** — run the `sprint-setup` skill. It will:
   - Auto-detect your project and generate `sprint-config/`
   - Create GitHub labels, milestones, and issues
   - Generate a CI workflow

2. **Sprint** — run the `sprint-run` skill. It will:
   - Run a kickoff ceremony with persona assignments
   - Execute stories with TDD and in-persona PR reviews
   - Run demo and retrospective ceremonies

## Lifecycle

```
sprint-setup → sprint-run (repeat per sprint) → sprint-release → sprint-teardown
```

- **sprint-setup** — one-time project bootstrap
- **sprint-run** — kickoff, stories, demo, retro (repeats each sprint)
- **sprint-monitor** — continuous CI/PR/burndown checks (use with `/loop 5m`)
- **sprint-release** — gate validation, versioning, GitHub Release
- **sprint-teardown** — safe removal of sprint-config/

## Commit Conventions

giles enforces [conventional commits](https://www.conventionalcommits.org/) via
`scripts/commit.py`. All skills use this wrapper instead of raw `git commit`.

```
feat: add user authentication
fix(parser): handle empty input
feat!: redesign API (breaking change)
```

Versions are auto-calculated from the commit log at release time:
- `feat:` → minor bump
- `fix:` → patch bump
- `!` or `BREAKING CHANGE:` → major bump
- Base version: `0.1.0` if no semver tags exist

## License

MIT
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: add getting-started README

Covers prerequisites, installation from jbrjake/claude-plugin-marketplace,
project preparation (personas, backlog), first run, lifecycle overview,
and commit conventions."
```

---

## Chunk 5: Test Suites

### Task 14: Mock-based unit tests for commit.py and release_gate.py

**Files:**
- Create: `scripts/test_gh_interactions.py`

- [ ] **Step 1: Create test file with commit.py tests**

```python
#!/usr/bin/env python3
"""Mock-based unit tests for gh CLI interactions across giles scripts.

Tests commit.py validation and release_gate.py version calculation,
gate validation, TOML writing, and release notes without any real
gh CLI or git calls.

Run: python scripts/test_gh_interactions.py -v
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))

from commit import validate_message, check_atomicity

sys.path.insert(0, str(
    SCRIPTS_DIR.parent / "skills" / "sprint-release" / "scripts"
))
from release_gate import (
    determine_bump, bump_version, calculate_version,
    find_latest_semver_tag, parse_commits_since,
    write_version_to_toml, generate_release_notes,
    gate_stories, gate_ci, gate_prs,
    validate_gates, print_gate_summary,
)


# ---------------------------------------------------------------------------
# commit.py tests
# ---------------------------------------------------------------------------

class TestValidateMessage(unittest.TestCase):
    """Test conventional commit message validation."""

    def test_valid_feat(self):
        ok, err = validate_message("feat: add login")
        self.assertTrue(ok)
        self.assertEqual(err, "")

    def test_valid_fix_with_scope(self):
        ok, err = validate_message("fix(parser): handle nulls")
        self.assertTrue(ok)

    def test_valid_breaking(self):
        ok, err = validate_message("feat!: remove old API")
        self.assertTrue(ok)

    def test_valid_breaking_with_scope(self):
        ok, err = validate_message("refactor(core)!: rewrite engine")
        self.assertTrue(ok)

    def test_all_valid_types(self):
        for t in ("feat", "fix", "refactor", "test", "docs",
                   "chore", "ci", "perf", "build", "style"):
            ok, _ = validate_message(f"{t}: do something")
            self.assertTrue(ok, f"Type '{t}' should be valid")

    def test_invalid_type(self):
        ok, err = validate_message("feature: add login")
        self.assertFalse(ok)
        self.assertIn("Invalid conventional commit", err)

    def test_missing_colon(self):
        ok, err = validate_message("feat add login")
        self.assertFalse(ok)

    def test_empty_description(self):
        ok, err = validate_message("feat: ")
        self.assertFalse(ok)
        self.assertIn("empty", err.lower())

    def test_empty_message(self):
        ok, err = validate_message("")
        self.assertFalse(ok)

    def test_no_type_prefix(self):
        ok, err = validate_message("just a regular message")
        self.assertFalse(ok)


class TestCheckAtomicity(unittest.TestCase):
    """Test atomicity enforcement."""

    @patch("commit.subprocess.run")
    def test_no_staged_changes(self, mock_run):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr="",
        )
        ok, msg = check_atomicity()
        self.assertFalse(ok)
        self.assertIn("No staged changes", msg)

    @patch("commit.subprocess.run")
    def test_single_directory(self, mock_run):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="src/foo.py\nsrc/bar.py\n", stderr="",
        )
        ok, msg = check_atomicity()
        self.assertTrue(ok)

    @patch("commit.subprocess.run")
    def test_three_directories_without_force(self, mock_run):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0,
            stdout="src/a.py\ntests/b.py\ndocs/c.md\n", stderr="",
        )
        ok, msg = check_atomicity(force=False)
        self.assertFalse(ok)
        self.assertIn("3 directories", msg)

    @patch("commit.subprocess.run")
    def test_three_directories_with_force(self, mock_run):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0,
            stdout="src/a.py\ntests/b.py\ndocs/c.md\n", stderr="",
        )
        ok, msg = check_atomicity(force=True)
        self.assertTrue(ok)

    @patch("commit.subprocess.run")
    def test_root_files(self, mock_run):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0,
            stdout="README.md\nCLAUDE.md\n", stderr="",
        )
        ok, msg = check_atomicity()
        self.assertTrue(ok)  # both in (root), only 1 dir


# ---------------------------------------------------------------------------
# release_gate.py — version calculation tests
# ---------------------------------------------------------------------------

class TestDetermineBump(unittest.TestCase):

    def test_feat_is_minor(self):
        commits = [{"subject": "feat: add login", "body": ""}]
        self.assertEqual(determine_bump(commits), "minor")

    def test_fix_is_patch(self):
        commits = [{"subject": "fix: typo", "body": ""}]
        self.assertEqual(determine_bump(commits), "patch")

    def test_breaking_bang_is_major(self):
        commits = [{"subject": "feat!: remove API", "body": ""}]
        self.assertEqual(determine_bump(commits), "major")

    def test_breaking_trailer_is_major(self):
        commits = [{"subject": "refactor: redo", "body": "BREAKING CHANGE: old API removed"}]
        self.assertEqual(determine_bump(commits), "major")

    def test_breaking_wins_over_feat(self):
        commits = [
            {"subject": "feat: add thing", "body": ""},
            {"subject": "fix: stuff", "body": "BREAKING CHANGE: old removed"},
        ]
        self.assertEqual(determine_bump(commits), "major")

    def test_feat_wins_over_fix(self):
        commits = [
            {"subject": "fix: typo", "body": ""},
            {"subject": "feat: new feature", "body": ""},
            {"subject": "fix: another", "body": ""},
        ]
        self.assertEqual(determine_bump(commits), "minor")

    def test_chore_is_patch(self):
        commits = [{"subject": "chore: update deps", "body": ""}]
        self.assertEqual(determine_bump(commits), "patch")

    def test_scoped_feat(self):
        commits = [{"subject": "feat(auth): add oauth", "body": ""}]
        self.assertEqual(determine_bump(commits), "minor")

    def test_scoped_breaking(self):
        commits = [{"subject": "refactor(core)!: rewrite", "body": ""}]
        self.assertEqual(determine_bump(commits), "major")


class TestBumpVersion(unittest.TestCase):

    def test_patch(self):
        self.assertEqual(bump_version("0.1.0", "patch"), "0.1.1")

    def test_minor(self):
        self.assertEqual(bump_version("0.1.0", "minor"), "0.2.0")

    def test_major(self):
        self.assertEqual(bump_version("0.1.0", "major"), "1.0.0")

    def test_minor_resets_patch(self):
        self.assertEqual(bump_version("1.2.3", "minor"), "1.3.0")

    def test_major_resets_minor_and_patch(self):
        self.assertEqual(bump_version("1.2.3", "major"), "2.0.0")


class TestWriteVersionToToml(unittest.TestCase):

    def test_append_release_section(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".toml", delete=False,
        ) as f:
            f.write('[project]\nname = "test"\n')
            path = Path(f.name)
        try:
            write_version_to_toml("1.0.0", path)
            text = path.read_text()
            self.assertIn('[release]', text)
            self.assertIn('version = "1.0.0"', text)
            # Original content preserved
            self.assertIn('[project]', text)
            self.assertIn('name = "test"', text)
        finally:
            path.unlink()

    def test_update_existing_version(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".toml", delete=False,
        ) as f:
            f.write('[project]\nname = "test"\n\n[release]\nversion = "0.1.0"\n')
            path = Path(f.name)
        try:
            write_version_to_toml("0.2.0", path)
            text = path.read_text()
            self.assertIn('version = "0.2.0"', text)
            self.assertNotIn('version = "0.1.0"', text)
        finally:
            path.unlink()

    def test_add_version_to_existing_release_section(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".toml", delete=False,
        ) as f:
            f.write('[project]\nname = "test"\n\n[release]\ngate_file = "gates.md"\n')
            path = Path(f.name)
        try:
            write_version_to_toml("0.3.0", path)
            text = path.read_text()
            self.assertIn('version = "0.3.0"', text)
            self.assertIn('gate_file = "gates.md"', text)
        finally:
            path.unlink()


# ---------------------------------------------------------------------------
# release_gate.py — gate validation tests (mocked gh)
# ---------------------------------------------------------------------------

class TestGateStories(unittest.TestCase):

    @patch("release_gate.gh_json")
    def test_all_closed(self, mock_gh):
        mock_gh.return_value = []
        ok, detail = gate_stories("Sprint 1")
        self.assertTrue(ok)
        self.assertIn("closed", detail.lower())

    @patch("release_gate.gh_json")
    def test_open_issues(self, mock_gh):
        mock_gh.return_value = [
            {"number": 1, "title": "US-0101: Setup"},
            {"number": 2, "title": "US-0102: Feature"},
        ]
        ok, detail = gate_stories("Sprint 1")
        self.assertFalse(ok)
        self.assertIn("2 open", detail)


class TestGateCI(unittest.TestCase):

    @patch("release_gate.gh_json")
    def test_passing(self, mock_gh):
        mock_gh.return_value = [
            {"status": "completed", "conclusion": "success", "name": "CI"},
        ]
        ok, detail = gate_ci()
        self.assertTrue(ok)

    @patch("release_gate.gh_json")
    def test_failing(self, mock_gh):
        mock_gh.return_value = [
            {"status": "completed", "conclusion": "failure", "name": "CI"},
        ]
        ok, detail = gate_ci()
        self.assertFalse(ok)
        self.assertIn("failure", detail)

    @patch("release_gate.gh_json")
    def test_no_runs(self, mock_gh):
        mock_gh.return_value = []
        ok, detail = gate_ci()
        self.assertFalse(ok)


class TestGatePRs(unittest.TestCase):

    @patch("release_gate.gh_json")
    def test_no_prs(self, mock_gh):
        mock_gh.return_value = []
        ok, _ = gate_prs("Sprint 1")
        self.assertTrue(ok)

    @patch("release_gate.gh_json")
    def test_open_pr_for_milestone(self, mock_gh):
        mock_gh.return_value = [
            {"number": 10, "title": "feat: thing",
             "milestone": {"title": "Sprint 1"}},
        ]
        ok, detail = gate_prs("Sprint 1")
        self.assertFalse(ok)

    @patch("release_gate.gh_json")
    def test_pr_for_different_milestone(self, mock_gh):
        mock_gh.return_value = [
            {"number": 10, "title": "feat: thing",
             "milestone": {"title": "Sprint 2"}},
        ]
        ok, _ = gate_prs("Sprint 1")
        self.assertTrue(ok)


class TestGenerateReleaseNotes(unittest.TestCase):

    def test_basic_notes(self):
        commits = [
            {"subject": "feat: add login", "body": ""},
            {"subject": "fix: typo in config", "body": ""},
        ]
        config = {"project": {"repo": "test/repo"}}
        notes = generate_release_notes("0.2.0", "0.1.0", commits, "Sprint 1", config)
        self.assertIn("v0.2.0", notes)
        self.assertIn("## Features", notes)
        self.assertIn("## Fixes", notes)
        self.assertIn("compare/v0.1.0...v0.2.0", notes)

    def test_breaking_changes(self):
        commits = [
            {"subject": "feat!: new API", "body": "BREAKING CHANGE: old removed"},
        ]
        config = {"project": {"repo": "test/repo"}}
        notes = generate_release_notes("1.0.0", "0.5.0", commits, "Sprint 3", config)
        self.assertIn("## Breaking Changes", notes)


# ---------------------------------------------------------------------------
# check_status.py tests (mocked gh)
# ---------------------------------------------------------------------------

class TestCheckCI(unittest.TestCase):

    @patch("check_status.gh_json")
    def test_all_passing(self, mock_gh):
        sys.path.insert(0, str(
            SCRIPTS_DIR.parent / "skills" / "sprint-monitor" / "scripts"
        ))
        from check_status import check_ci
        mock_gh.return_value = [
            {"conclusion": "success", "status": "completed",
             "name": "CI", "headBranch": "main", "databaseId": 1},
        ]
        report, actions = check_ci()
        self.assertIn("1 passing", report[0])
        self.assertEqual(len(actions), 0)

    @patch("check_status.gh_json")
    @patch("check_status.gh")
    def test_failing_run(self, mock_gh_str, mock_gh_json):
        from check_status import check_ci
        mock_gh_json.return_value = [
            {"conclusion": "failure", "status": "completed",
             "name": "CI", "headBranch": "main", "databaseId": 99},
        ]
        mock_gh_str.return_value = "error: test failed"
        report, actions = check_ci()
        self.assertIn("1 failing", report[0])
        self.assertGreater(len(actions), 0)


class TestCheckPRs(unittest.TestCase):

    @patch("check_status.gh_json")
    def test_no_prs(self, mock_gh):
        from check_status import check_prs
        mock_gh.return_value = []
        report, actions = check_prs()
        self.assertIn("none open", report[0])

    @patch("check_status.gh_json")
    def test_approved_pr(self, mock_gh):
        from check_status import check_prs
        mock_gh.return_value = [
            {"number": 1, "title": "feat", "reviewDecision": "APPROVED",
             "labels": [], "statusCheckRollup": [
                 {"status": "COMPLETED", "conclusion": "SUCCESS"}
             ], "createdAt": "2026-03-09T00:00:00Z"},
        ]
        report, actions = check_prs()
        self.assertIn("1 approved", report[0])


# ---------------------------------------------------------------------------
# bootstrap_github.py tests (mocked run_gh)
# ---------------------------------------------------------------------------

class TestBootstrapLabel(unittest.TestCase):

    @patch("bootstrap_github.run_gh")
    def test_create_label_success(self, mock_run):
        sys.path.insert(0, str(
            SCRIPTS_DIR.parent / "skills" / "sprint-setup" / "scripts"
        ))
        from bootstrap_github import create_label
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr="",
        )
        # Should not raise
        create_label("test-label", "ff0000", "Test")
        mock_run.assert_called_once()

    @patch("bootstrap_github.run_gh")
    def test_create_label_already_exists(self, mock_run):
        from bootstrap_github import create_label
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=1, stdout="", stderr="already_exists",
        )
        # Should not raise (idempotent)
        create_label("test-label", "ff0000", "Test")


# ---------------------------------------------------------------------------
# populate_issues.py tests (mocked run_gh)
# ---------------------------------------------------------------------------

class TestGetExistingIssues(unittest.TestCase):

    @patch("populate_issues.run_gh")
    def test_parses_existing(self, mock_run):
        sys.path.insert(0, str(
            SCRIPTS_DIR.parent / "skills" / "sprint-setup" / "scripts"
        ))
        from populate_issues import get_existing_issues
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0,
            stdout=json.dumps([
                {"title": "US-0101: Setup"},
                {"title": "US-0102: Feature"},
            ]),
            stderr="",
        )
        existing = get_existing_issues()
        self.assertIn("US-0101", existing)
        self.assertIn("US-0102", existing)

    @patch("populate_issues.run_gh")
    def test_empty_on_failure(self, mock_run):
        from populate_issues import get_existing_issues
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=1, stdout="", stderr="error",
        )
        existing = get_existing_issues()
        self.assertEqual(len(existing), 0)


# ---------------------------------------------------------------------------
# sync_tracking.py tests (mocked gh)
# ---------------------------------------------------------------------------

class TestFindMilestoneTitle(unittest.TestCase):

    @patch("sync_tracking.gh")
    def test_finds_matching(self, mock_gh):
        sys.path.insert(0, str(
            SCRIPTS_DIR.parent / "skills" / "sprint-run" / "scripts"
        ))
        from sync_tracking import find_milestone_title
        mock_gh.return_value = json.dumps([
            {"title": "Sprint 1: Walking Skeleton", "number": 1},
            {"title": "Sprint 2: Core", "number": 2},
        ])
        result = find_milestone_title(1)
        self.assertEqual(result, "Sprint 1: Walking Skeleton")

    @patch("sync_tracking.gh")
    def test_returns_none(self, mock_gh):
        from sync_tracking import find_milestone_title
        mock_gh.return_value = json.dumps([
            {"title": "Sprint 2: Core", "number": 2},
        ])
        result = find_milestone_title(1)
        self.assertIsNone(result)


# ---------------------------------------------------------------------------
# update_burndown.py tests (mocked gh)
# ---------------------------------------------------------------------------

class TestExtractSP(unittest.TestCase):

    def test_from_label(self):
        sys.path.insert(0, str(
            SCRIPTS_DIR.parent / "skills" / "sprint-run" / "scripts"
        ))
        from update_burndown import extract_sp
        issue = {"labels": [{"name": "sp:5"}], "body": ""}
        self.assertEqual(extract_sp(issue), 5)

    def test_from_body(self):
        from update_burndown import extract_sp
        issue = {"labels": [], "body": "| Story Points | 8 |"}
        self.assertEqual(extract_sp(issue), 8)

    def test_no_sp(self):
        from update_burndown import extract_sp
        issue = {"labels": [], "body": "No points here"}
        self.assertEqual(extract_sp(issue), 0)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests**

Run: `python3 scripts/test_gh_interactions.py -v`
Expected: All tests pass

- [ ] **Step 3: Commit**

```bash
git add scripts/test_gh_interactions.py
git commit -m "test: add mock-based unit tests for commit.py and release_gate.py

Tests conventional commit validation, atomicity checks, version
calculation, bump logic, TOML writing, gate validation, and release
notes generation. All gh CLI calls mocked — no network access."
```

---

### Task 15: FakeGitHub + lifecycle integration test

**Files:**
- Create: `scripts/test_lifecycle.py`

- [ ] **Step 1: Create the lifecycle test with FakeGitHub backend**

```python
#!/usr/bin/env python3
"""End-to-end lifecycle test with a fake GitHub backend.

Creates a mock Rust project in a temp directory, runs the full giles
pipeline (init -> bootstrap -> populate -> monitor -> sync -> burndown
-> release), and verifies each stage. gh CLI calls are intercepted by
FakeGitHub; git operations run against a real temp repo.

Run: python scripts/test_lifecycle.py -v
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

SCRIPTS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPTS_DIR.parent
sys.path.insert(0, str(SCRIPTS_DIR))

from validate_config import validate_project, parse_simple_toml
from sprint_init import ProjectScanner, ConfigGenerator


class FakeGitHub:
    """In-memory fake GitHub state for intercepting gh CLI calls."""

    def __init__(self):
        self.labels: dict[str, dict] = {}
        self.milestones: dict[str, dict] = {}
        self._ms_counter = 0
        self.issues: dict[int, dict] = {}
        self._issue_counter = 0
        self.releases: dict[str, dict] = {}
        self.runs: list[dict] = [
            {"status": "completed", "conclusion": "success",
             "name": "CI", "headBranch": "main", "databaseId": 1},
        ]
        self.prs: list[dict] = []

    def handle(self, args: list[str]) -> subprocess.CompletedProcess:
        """Route a gh CLI call to the appropriate handler."""
        if not args:
            return self._fail("empty args")

        cmd = args[0]
        if cmd == "label":
            return self._handle_label(args[1:])
        elif cmd == "api":
            return self._handle_api(args[1:])
        elif cmd == "issue":
            return self._handle_issue(args[1:])
        elif cmd == "run":
            return self._handle_run(args[1:])
        elif cmd == "pr":
            return self._handle_pr(args[1:])
        elif cmd == "release":
            return self._handle_release(args[1:])
        elif cmd == "auth":
            return self._ok("")
        elif cmd == "--version":
            return self._ok("gh version 2.50.0")
        return self._fail(f"unhandled: gh {' '.join(args)}")

    def _ok(self, stdout: str) -> subprocess.CompletedProcess:
        return subprocess.CompletedProcess(
            args=[], returncode=0, stdout=stdout, stderr="",
        )

    def _fail(self, msg: str) -> subprocess.CompletedProcess:
        return subprocess.CompletedProcess(
            args=[], returncode=1, stdout="", stderr=msg,
        )

    def _handle_label(self, args):
        if args[0] == "create":
            name = args[1]
            color = ""
            desc = ""
            for i, a in enumerate(args):
                if a == "--color" and i + 1 < len(args):
                    color = args[i + 1]
                if a == "--description" and i + 1 < len(args):
                    desc = args[i + 1]
            self.labels[name] = {"color": color, "description": desc}
            return self._ok("")
        return self._fail(f"label: {args}")

    def _handle_api(self, args):
        endpoint = args[0] if args else ""
        # Replace gh auto-placeholders
        endpoint = endpoint.replace("{owner}", "testowner")
        endpoint = endpoint.replace("{repo}", "testrepo")

        method = "GET"
        fields = {}
        jq_filter = ""
        for i, a in enumerate(args):
            if a == "-X" and i + 1 < len(args):
                method = args[i + 1]
            if a == "-f" and i + 1 < len(args):
                k, v = args[i + 1].split("=", 1)
                fields[k] = v
            if a == "--jq" and i + 1 < len(args):
                jq_filter = args[i + 1]

        if "milestones" in endpoint:
            if method == "GET" or not fields:
                return self._ok(json.dumps(list(self.milestones.values())))
            if fields.get("title"):
                title = fields["title"]
                if title in self.milestones:
                    return self._fail("already_exists")
                self._ms_counter += 1
                self.milestones[title] = {
                    "number": self._ms_counter,
                    "title": title,
                    "state": fields.get("state", "open"),
                    "description": fields.get("description", ""),
                    "open_issues": 0,
                    "closed_issues": 0,
                }
                return self._ok(json.dumps(self.milestones[title]))
            if fields.get("state") == "closed":
                # Close a milestone
                for ms in self.milestones.values():
                    ms_num = str(ms["number"])
                    if endpoint.endswith(f"/{ms_num}"):
                        ms["state"] = "closed"
                        return self._ok(json.dumps(ms))
                return self._ok("{}")
        return self._ok("[]")

    def _handle_issue(self, args):
        if args[0] == "list":
            state_filter = "open"
            milestone_filter = ""
            json_fields = ""
            limit = 200
            for i, a in enumerate(args):
                if a == "--state" and i + 1 < len(args):
                    state_filter = args[i + 1]
                if a == "--milestone" and i + 1 < len(args):
                    milestone_filter = args[i + 1]
                if a == "--json" and i + 1 < len(args):
                    json_fields = args[i + 1]
            result = []
            for issue in self.issues.values():
                if milestone_filter:
                    ms = issue.get("milestone", {})
                    if isinstance(ms, dict) and ms.get("title") != milestone_filter:
                        continue
                if state_filter != "all" and issue.get("state") != state_filter:
                    continue
                result.append(issue)
            return self._ok(json.dumps(result[:limit]))

        elif args[0] == "create":
            self._issue_counter += 1
            title = ""
            body = ""
            labels = []
            milestone = ""
            for i, a in enumerate(args):
                if a == "--title" and i + 1 < len(args):
                    title = args[i + 1]
                if a == "--body" and i + 1 < len(args):
                    body = args[i + 1]
                if a == "--label" and i + 1 < len(args):
                    labels.append(args[i + 1])
                if a == "--milestone" and i + 1 < len(args):
                    milestone = args[i + 1]
            self.issues[self._issue_counter] = {
                "number": self._issue_counter,
                "title": title,
                "body": body,
                "state": "open",
                "labels": [{"name": l} for l in labels],
                "milestone": {"title": milestone} if milestone else None,
                "closedAt": None,
            }
            return self._ok(
                f"https://github.com/testowner/testrepo/issues/{self._issue_counter}"
            )
        return self._fail(f"issue: {args}")

    def _handle_run(self, args):
        if args[0] == "list":
            return self._ok(json.dumps(self.runs))
        if args[0] == "view":
            return self._ok("No failed steps")
        return self._fail(f"run: {args}")

    def _handle_pr(self, args):
        if args[0] == "list":
            return self._ok(json.dumps(self.prs))
        return self._fail(f"pr: {args}")

    def _handle_release(self, args):
        if args[0] == "create":
            tag = args[1]
            title = ""
            for i, a in enumerate(args):
                if a == "--title" and i + 1 < len(args):
                    title = args[i + 1]
            self.releases[tag] = {"tag": tag, "title": title}
            return self._ok("")
        if args[0] == "view":
            tag = args[1] if len(args) > 1 else ""
            if tag in self.releases:
                return self._ok(json.dumps({
                    "url": f"https://github.com/testowner/testrepo/releases/tag/{tag}",
                }))
            return self._fail("not found")
        return self._fail(f"release: {args}")


def make_patched_subprocess(fake: FakeGitHub, original_run):
    """Create a subprocess.run replacement that intercepts gh calls."""
    def patched_run(args, **kwargs):
        if isinstance(args, list) and args and args[0] == "gh":
            return fake.handle(args[1:])
        return original_run(args, **kwargs)
    return patched_run


class MockProject:
    """Create a minimal mock Rust project for lifecycle testing."""

    def __init__(self, root: Path):
        self.root = root

    def create(self) -> None:
        # Cargo.toml
        (self.root / "Cargo.toml").write_text(textwrap.dedent("""\
            [package]
            name = "test-project"
            version = "0.1.0"
            edition = "2021"
        """))

        # Git repo
        subprocess.run(["git", "init", str(self.root)],
                        capture_output=True, check=True)
        subprocess.run(["git", "-C", str(self.root), "config",
                        "user.email", "test@test.com"],
                        capture_output=True, check=True)
        subprocess.run(["git", "-C", str(self.root), "config",
                        "user.name", "Test"],
                        capture_output=True, check=True)

        # Fake git remote
        git_config = self.root / ".git" / "config"
        text = git_config.read_text()
        text += textwrap.dedent("""
            [remote "origin"]
                url = https://github.com/testowner/testrepo.git
                fetch = +refs/heads/*:refs/remotes/origin/*
        """)
        git_config.write_text(text)

        # Personas
        docs = self.root / "docs" / "dev-team"
        docs.mkdir(parents=True)
        for name, role in [("alice", "Senior Engineer"),
                           ("bob", "Systems Architect")]:
            (docs / f"{name}.md").write_text(textwrap.dedent(f"""\
                # {name.title()}

                ## Role
                {role}

                ## Voice
                Direct and technical.

                ## Domain
                Backend systems.

                ## Background
                10 years experience.

                ## Review Focus
                Performance and correctness.
            """))

        # Backlog
        milestones = self.root / "docs" / "backlog" / "milestones"
        milestones.mkdir(parents=True)
        (milestones / "milestone-1.md").write_text(textwrap.dedent("""\
            # Sprint 1: Walking Skeleton

            ### Sprint 1: Foundation

            | US-0101 | Basic setup | S01 | 3 | P0 |
            | US-0102 | Core feature | S01 | 5 | P1 |
        """))

        # Rules and dev guide
        (self.root / "RULES.md").write_text("# Rules\nNo panics.\n")
        (self.root / "DEVELOPMENT.md").write_text("# Dev\nUse TDD.\n")

        # Initial commit
        subprocess.run(["git", "-C", str(self.root), "add", "-A"],
                        capture_output=True, check=True)
        subprocess.run(["git", "-C", str(self.root), "commit",
                        "-m", "feat: initial project setup"],
                        capture_output=True, check=True)


class TestLifecycle(unittest.TestCase):
    """End-to-end lifecycle test with FakeGitHub."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="giles-lifecycle-")
        self.root = Path(self.tmpdir)
        self.mock = MockProject(self.root)
        self.mock.create()
        self.fake = FakeGitHub()
        self.original_cwd = os.getcwd()
        os.chdir(str(self.root))

    def tearDown(self):
        os.chdir(self.original_cwd)
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_01_init_generates_valid_config(self):
        """sprint_init.py generates config that passes validation."""
        scanner = ProjectScanner(self.root)
        scan = scanner.scan()
        gen = ConfigGenerator(scan)
        gen.generate()
        ok, errors = validate_project(str(self.root / "sprint-config"))
        self.assertTrue(ok, f"Validation failed: {errors}")

    def test_02_bootstrap_creates_labels_and_milestones(self):
        """bootstrap_github.py creates labels and milestones in fake."""
        # First init config
        scanner = ProjectScanner(self.root)
        scan = scanner.scan()
        gen = ConfigGenerator(scan)
        gen.generate()

        sys.path.insert(0, str(
            PROJECT_ROOT / "skills" / "sprint-setup" / "scripts"
        ))
        from bootstrap_github import main as bootstrap_main

        patched = make_patched_subprocess(self.fake, subprocess.run)
        with patch("subprocess.run", side_effect=patched):
            with patch("bootstrap_github.subprocess.run", side_effect=patched):
                # Suppress output
                from io import StringIO
                with patch("sys.stdout", new=StringIO()):
                    try:
                        bootstrap_main()
                    except SystemExit:
                        pass

        self.assertGreater(len(self.fake.labels), 0, "No labels created")
        self.assertGreater(len(self.fake.milestones), 0, "No milestones created")

    def test_03_populate_creates_issues(self):
        """populate_issues.py creates issues in fake."""
        scanner = ProjectScanner(self.root)
        scan = scanner.scan()
        gen = ConfigGenerator(scan)
        gen.generate()

        # Bootstrap milestones first
        sys.path.insert(0, str(
            PROJECT_ROOT / "skills" / "sprint-setup" / "scripts"
        ))

        patched = make_patched_subprocess(self.fake, subprocess.run)
        with patch("subprocess.run", side_effect=patched):
            from bootstrap_github import main as bootstrap_main
            with patch("bootstrap_github.subprocess.run", side_effect=patched):
                from io import StringIO
                with patch("sys.stdout", new=StringIO()):
                    try:
                        bootstrap_main()
                    except SystemExit:
                        pass

            from populate_issues import main as populate_main
            with patch("populate_issues.subprocess.run", side_effect=patched):
                with patch("sys.stdout", new=StringIO()):
                    try:
                        populate_main()
                    except SystemExit:
                        pass

        self.assertGreater(len(self.fake.issues), 0, "No issues created")

    def test_04_version_calculation(self):
        """Version calculates correctly from commit log."""
        sys.path.insert(0, str(
            PROJECT_ROOT / "skills" / "sprint-release" / "scripts"
        ))
        from release_gate import calculate_version

        # No tags, one feat commit -> 0.2.0
        new_ver, base_ver, bump_type, commits = calculate_version()
        self.assertEqual(base_ver, "0.1.0")
        self.assertEqual(bump_type, "minor")  # "feat: initial project setup"
        self.assertEqual(new_ver, "0.2.0")

    def test_05_version_with_tag(self):
        """Version bumps from existing tag."""
        subprocess.run(
            ["git", "-C", str(self.root), "tag", "-a", "v1.0.0",
             "-m", "Release 1.0.0"],
            capture_output=True, check=True,
        )
        # Add a fix commit after the tag
        (self.root / "fixfile.txt").write_text("fix\n")
        subprocess.run(["git", "-C", str(self.root), "add", "fixfile.txt"],
                        capture_output=True, check=True)
        subprocess.run(["git", "-C", str(self.root), "commit",
                        "-m", "fix: patch issue"],
                        capture_output=True, check=True)

        sys.path.insert(0, str(
            PROJECT_ROOT / "skills" / "sprint-release" / "scripts"
        ))
        from release_gate import calculate_version

        new_ver, base_ver, bump_type, commits = calculate_version()
        self.assertEqual(base_ver, "1.0.0")
        self.assertEqual(bump_type, "patch")
        self.assertEqual(new_ver, "1.0.1")

    def test_06_commit_validation(self):
        """commit.py validates conventional format."""
        from commit import validate_message

        ok, _ = validate_message("feat: valid message")
        self.assertTrue(ok)

        ok, _ = validate_message("invalid message")
        self.assertFalse(ok)

    def test_07_monitor_reports_status(self):
        """check_status.py reports correct counts from fake."""
        scanner = ProjectScanner(self.root)
        scan = scanner.scan()
        gen = ConfigGenerator(scan)
        gen.generate()

        # Create SPRINT-STATUS.md so monitor can detect sprint
        sprints_dir = self.root / "docs" / "dev-team" / "sprints"
        sprints_dir.mkdir(parents=True, exist_ok=True)
        (sprints_dir / "SPRINT-STATUS.md").write_text(
            "# Sprint Status\n\nCurrent Sprint: 1\n"
        )

        sys.path.insert(0, str(
            PROJECT_ROOT / "skills" / "sprint-monitor" / "scripts"
        ))
        from check_status import check_ci, check_prs

        patched = make_patched_subprocess(self.fake, subprocess.run)
        with patch("check_status.subprocess.run", side_effect=patched):
            report, actions = check_ci()
            self.assertIn("1 passing", report[0])

            pr_report, _ = check_prs()
            self.assertIn("none open", pr_report[0])

    def test_08_sync_creates_tracking_files(self):
        """sync_tracking.py creates tracking files from fake issues."""
        scanner = ProjectScanner(self.root)
        scan = scanner.scan()
        gen = ConfigGenerator(scan)
        gen.generate()

        # Bootstrap + populate to get issues into fake
        sys.path.insert(0, str(
            PROJECT_ROOT / "skills" / "sprint-setup" / "scripts"
        ))
        patched = make_patched_subprocess(self.fake, subprocess.run)
        with patch("subprocess.run", side_effect=patched):
            with patch("bootstrap_github.subprocess.run", side_effect=patched):
                from io import StringIO
                with patch("sys.stdout", new=StringIO()):
                    try:
                        from bootstrap_github import main as bm
                        bm()
                    except SystemExit:
                        pass
            with patch("populate_issues.subprocess.run", side_effect=patched):
                with patch("sys.stdout", new=StringIO()):
                    try:
                        from populate_issues import main as pm
                        pm()
                    except SystemExit:
                        pass

        # Now there should be issues in fake
        self.assertGreater(len(self.fake.issues), 0)

    def test_09_burndown_extracts_sp(self):
        """update_burndown.py SP extraction works correctly."""
        sys.path.insert(0, str(
            PROJECT_ROOT / "skills" / "sprint-run" / "scripts"
        ))
        from update_burndown import extract_sp

        self.assertEqual(extract_sp({"labels": [{"name": "sp:3"}], "body": ""}), 3)
        self.assertEqual(extract_sp({"labels": [], "body": "| Story Points | 5 |"}), 5)
        self.assertEqual(extract_sp({"labels": [], "body": "no points"}), 0)

    def test_10_version_calc_dry_run(self):
        """release_gate.py --dry-run evaluates gates without mutations."""
        sys.path.insert(0, str(
            PROJECT_ROOT / "skills" / "sprint-release" / "scripts"
        ))
        from release_gate import validate_gates

        # Close all issues in fake so stories gate passes
        for issue in self.fake.issues.values():
            issue["state"] = "closed"

        patched = make_patched_subprocess(self.fake, subprocess.run)
        config = {
            "ci": {"check_commands": [], "build_command": ""},
            "project": {"name": "test", "repo": "testowner/testrepo"},
        }
        with patch("release_gate.subprocess.run", side_effect=patched):
            passed, results = validate_gates("Sprint 1: Walking Skeleton", config)
            # Stories gate should pass (no open issues or no milestone match)
            # CI gate should pass (fake has a success run)
            for name, ok, detail in results:
                if name == "CI":
                    self.assertTrue(ok, f"CI gate failed: {detail}")

    def test_11_release_creates_tag(self):
        """Full release creates a git tag."""
        # Add a feat commit for version bump
        (self.root / "newfile.txt").write_text("release content\n")
        subprocess.run(["git", "-C", str(self.root), "add", "newfile.txt"],
                        capture_output=True, check=True)
        subprocess.run(["git", "-C", str(self.root), "commit",
                        "-m", "feat: add release content"],
                        capture_output=True, check=True)

        sys.path.insert(0, str(
            PROJECT_ROOT / "skills" / "sprint-release" / "scripts"
        ))
        from release_gate import calculate_version

        new_ver, base_ver, bump_type, commits = calculate_version()
        # Should be a minor bump (feat commit, no prior tags)
        self.assertEqual(bump_type, "minor")
        self.assertEqual(new_ver, "0.2.0")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the lifecycle tests**

Run: `python3 scripts/test_lifecycle.py -v`
Expected: All tests pass

- [ ] **Step 3: Commit**

```bash
git add scripts/test_lifecycle.py
git commit -m "test: add lifecycle integration test with FakeGitHub

End-to-end test: init -> bootstrap -> populate -> version calc.
FakeGitHub intercepts all gh CLI calls with in-memory state.
Real git operations against temp repo."
```

---

## Chunk 6: Final Verification

### Task 16: Run all tests and verify

**Files:** None (read-only verification)

- [ ] **Step 1: Compile all Python files**

Run: `for f in scripts/*.py skills/*/scripts/*.py; do python3 -m py_compile "$f" && echo "OK: $f" || echo "FAIL: $f"; done`
Expected: All files show OK (including the two new scripts and two new test files)

- [ ] **Step 2: Run original verification suite**

Run: `python3 scripts/verify_fixes.py -v`
Expected: All 13 tests pass (existing tests unbroken)

- [ ] **Step 3: Run mock-based unit tests**

Run: `python3 scripts/test_gh_interactions.py -v`
Expected: All tests pass

- [ ] **Step 4: Run lifecycle integration tests**

Run: `python3 scripts/test_lifecycle.py -v`
Expected: All tests pass

- [ ] **Step 5: Test --help on new scripts**

Run: `python3 scripts/commit.py --help && python3 skills/sprint-release/scripts/release_gate.py --help`
Expected: Both show argparse help text

- [ ] **Step 6: Test --help on existing scripts (spot check)**

Run: `python3 scripts/validate_config.py --help | head -3 && python3 scripts/sprint_init.py --help | head -3`
Expected: Module docstring shown, not a crash

- [ ] **Step 7: Version bump + final commit**

Update `.claude-plugin/plugin.json` version from `0.2.0` to `0.3.0`.

```bash
git add .claude-plugin/plugin.json
git commit -m "release: bump to v0.3.0 — max confidence ship

All features implemented and verified:
- Conventional commit enforcement (scripts/commit.py)
- Release gate automation (skills/sprint-release/scripts/release_gate.py)
- Auto-calculated semver from commit log
- --help on all 11 scripts
- gh command fixes in SKILL.md files
- README.md with install/getting-started
- Mock-based unit tests (test_gh_interactions.py)
- Lifecycle integration tests (test_lifecycle.py)"
```
