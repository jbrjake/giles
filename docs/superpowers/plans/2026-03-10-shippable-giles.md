# Shippable Giles Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Get the giles plugin to a shippable state — working end-to-end against a real-shaped project, with progressive disclosure SKILL.md files, golden-run regression tests, and polished onboarding.

**Architecture:** Build a mock Rust project (hexwise) as a permanent test fixture. Extend FakeGitHub to cover the full sprint lifecycle. Smoke test all scripts against the fixture, then do a live golden run to capture state snapshots at each skill phase. Refactor SKILL.md files for progressive disclosure. Rewrite README for marketplace onboarding.

**Tech Stack:** Python 3.10+ (stdlib only), unittest, Rust (fixture only — Cargo.toml + stubs), Markdown

---

## Chunk 1: Hexwise Fixture

Build the mock Rust project that all tests will use. This is a permanent fixture, not a temp directory — it lives in the repo so tests are reproducible.

### Task 1: Create hexwise project structure

**Files:**
- Create: `tests/fixtures/hexwise/Cargo.toml`
- Create: `tests/fixtures/hexwise/src/main.rs`
- Create: `tests/fixtures/hexwise/src/lib.rs`

- [ ] **Step 1: Create Cargo.toml**

```toml
[package]
name = "hexwise"
version = "0.1.0"
edition = "2021"
description = "CLI that finds the closest CSS named color for a hex code"

[dependencies]
```

- [ ] **Step 2: Create src/main.rs**

```rust
fn main() {
    println!("hexwise: not yet implemented");
}
```

- [ ] **Step 3: Create src/lib.rs**

```rust
/// Core color-matching logic for hexwise.
///
/// Parses hex color codes and finds the nearest CSS named color
/// using Euclidean distance in RGB space.

/// Parse a hex color string like "#ff6347" into (R, G, B).
pub fn parse_hex(input: &str) -> Result<(u8, u8, u8), String> {
    let hex = input.trim_start_matches('#');
    if hex.len() != 6 {
        return Err(format!("expected 6 hex digits, got {}", hex.len()));
    }
    let r = u8::from_str_radix(&hex[0..2], 16).map_err(|e| e.to_string())?;
    let g = u8::from_str_radix(&hex[2..4], 16).map_err(|e| e.to_string())?;
    let b = u8::from_str_radix(&hex[4..6], 16).map_err(|e| e.to_string())?;
    Ok((r, g, b))
}
```

- [ ] **Step 4: Commit**

```bash
git add tests/fixtures/hexwise/
git commit -m "test: add hexwise Rust fixture — Cargo.toml and src stubs"
```

### Task 2: Create hexwise team personas

**Files:**
- Create: `tests/fixtures/hexwise/docs/team/INDEX.md`
- Create: `tests/fixtures/hexwise/docs/team/rusti.md`
- Create: `tests/fixtures/hexwise/docs/team/palette.md`
- Create: `tests/fixtures/hexwise/docs/team/checker.md`

- [ ] **Step 1: Create team INDEX.md**

```markdown
# Dev Team

| Name | Role | File |
|------|------|------|
| Rusti | Lead / Architect | rusti.md |
| Palette | Feature Dev | palette.md |
| Checker | QA / Reviewer | checker.md |
```

- [ ] **Step 2: Create rusti.md**

```markdown
# Rusti

## Role
Lead / Architect

## Voice
Precise, idiomatic-Rust enthusiast. Cares about zero-copy and `clippy::pedantic`. Speaks in terms of ownership, lifetimes, and trait bounds. Disapproves of `.unwrap()` in library code.

## Domain
Systems programming, performance, API design, memory safety.

## Background
10 years in systems programming. Contributed to several Rust crates. Believes `unsafe` should be justified with a comment longer than the block itself.

## Review Focus
Idiomatic Rust, performance, memory safety, API ergonomics, error handling with `thiserror`/`anyhow` patterns.
```

- [ ] **Step 3: Create palette.md**

```markdown
# Palette

## Role
Feature Dev

## Voice
Creative, user-focused. Thinks about CLI UX and delightful output. Loves ANSI color codes and terminal art. Uses metaphors involving paint, canvas, and color theory.

## Domain
CLI design, user experience, color theory, output formatting.

## Background
Frontend-turned-CLI developer. Believes every terminal output is a tiny canvas. Has opinions about whether `#ff6347` feels warm or cool.

## Review Focus
User experience, output clarity, help text quality, edge case messaging.
```

- [ ] **Step 4: Create checker.md**

```markdown
# Checker

## Role
QA / Reviewer

## Voice
Skeptical, thorough. Writes the edge case tests everyone else forgets. Asks "but what if the input is empty?" before anyone else thinks of it. Dry humor.

## Domain
Testing, validation, error paths, fuzzing, boundary conditions.

## Background
Former QA lead who learned to code so they could write their own test harnesses. Keeps a personal list of bugs found per sprint.

## Review Focus
Test coverage, error handling, boundary conditions, input validation, panic paths.
```

- [ ] **Step 5: Commit**

```bash
git add tests/fixtures/hexwise/docs/team/
git commit -m "test: add hexwise team personas — Rusti, Palette, Checker"
```

### Task 3: Create hexwise backlog and project docs

**Files:**
- Create: `tests/fixtures/hexwise/docs/backlog/INDEX.md`
- Create: `tests/fixtures/hexwise/docs/backlog/milestones/milestone-1.md`
- Create: `tests/fixtures/hexwise/docs/backlog/milestones/milestone-2.md`
- Create: `tests/fixtures/hexwise/RULES.md`
- Create: `tests/fixtures/hexwise/DEVELOPMENT.md`

- [ ] **Step 1: Create backlog INDEX.md**

```markdown
# Backlog

| Milestone | File |
|-----------|------|
| M1: Core | milestones/milestone-1.md |
| M2: Polish | milestones/milestone-2.md |
```

- [ ] **Step 2: Create milestone-1.md**

The story table format must match what `populate_issues.parse_milestone_stories()` expects: `| story_id | title | saga | sp | priority |`

```markdown
# M1: Core — Parse, Match, Print

The walking skeleton: parse a hex code, find the nearest CSS color, print it.

### Sprint 1: Core

| US-0101 | Parse hex color input (#RRGGBB and #RGB shorthand) | S01 | 3 | P0 |
| US-0102 | Find nearest CSS named color (Euclidean distance in RGB) | S01 | 5 | P0 |
| US-0103 | Print formatted color output with name and RGB values | S01 | 3 | P1 |
```

- [ ] **Step 3: Create milestone-2.md**

```markdown
# M2: Polish — Descriptions, JSON, Errors

Make it delightful and robust.

### Sprint 2: Polish

| US-0201 | Add personality descriptions for common colors | S02 | 3 | P1 |
| US-0202 | Add --format json output flag | S02 | 3 | P1 |
| US-0203 | Graceful error handling for invalid hex input | S02 | 2 | P0 |
```

- [ ] **Step 4: Create RULES.md**

```markdown
# Project Rules

- No `.unwrap()` in library code — use `Result` with descriptive errors.
- All public functions must have doc comments.
- Run `cargo clippy -- -D warnings` before every commit.
- Keep dependencies at zero unless absolutely necessary.
- Tests go in the same file as the code they test (unit) or in `tests/` (integration).
```

- [ ] **Step 5: Create DEVELOPMENT.md**

~~~markdown
# Development Guide

## Build

    cargo build

## Test

    cargo test

## Lint

    cargo fmt --check
    cargo clippy -- -D warnings

## Workflow
1. Write a failing test.
2. Write the minimal code to make it pass.
3. Run `cargo fmt` and `cargo clippy`.
4. Commit with a conventional commit message.
~~~

- [ ] **Step 6: Commit**

```bash
git add tests/fixtures/hexwise/docs/ tests/fixtures/hexwise/RULES.md tests/fixtures/hexwise/DEVELOPMENT.md
git commit -m "test: add hexwise backlog (2 milestones, 6 stories) and project docs"
```

### Task 4: Smoke test sprint_init against hexwise

**Files:**
- Create: `tests/test_hexwise_setup.py`

This test copies the hexwise fixture to a temp directory (so we don't pollute the fixture), initializes a git repo, runs `sprint_init.py`, and verifies the generated `sprint-config/` is valid.

- [ ] **Step 1: Write test_hexwise_setup.py**

```python
#!/usr/bin/env python3
"""Smoke test: sprint_init against hexwise fixture.

Copies the hexwise fixture to a temp dir, runs ProjectScanner + ConfigGenerator,
and validates the resulting sprint-config/.

Run: python tests/test_hexwise_setup.py -v
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
FIXTURE_DIR = TESTS_DIR / "fixtures" / "hexwise"

sys.path.insert(0, str(REPO_ROOT / "scripts"))
from validate_config import parse_simple_toml, validate_project
from sprint_init import ProjectScanner, ConfigGenerator


class TestHexwiseSetup(unittest.TestCase):
    """Verify sprint_init works against the hexwise fixture."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="hexwise-test-")
        self.root = Path(self.tmpdir)
        # Copy fixture to temp dir
        shutil.copytree(FIXTURE_DIR, self.root / "hexwise")
        self.project = self.root / "hexwise"
        # Init git repo
        subprocess.run(
            ["git", "init"], cwd=str(self.project),
            capture_output=True, text=True,
        )
        subprocess.run(
            ["git", "remote", "add", "origin",
             "https://github.com/testowner/hexwise.git"],
            cwd=str(self.project), capture_output=True, text=True,
        )
        subprocess.run(
            ["git", "add", "."], cwd=str(self.project),
            capture_output=True, text=True,
        )
        subprocess.run(
            ["git", "-c", "user.name=Test", "-c", "user.email=test@test.com",
             "commit", "-m", "feat: initial hexwise setup"],
            cwd=str(self.project), capture_output=True, text=True,
        )
        self._saved_cwd = os.getcwd()
        os.chdir(self.project)

    def tearDown(self):
        os.chdir(self._saved_cwd)
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _generate_config(self) -> dict:
        scanner = ProjectScanner(self.project)
        scan = scanner.scan()
        gen = ConfigGenerator(scan)
        gen.generate()
        toml_path = self.project / "sprint-config" / "project.toml"
        return parse_simple_toml(toml_path.read_text())

    def test_scanner_detects_rust(self):
        """ProjectScanner detects Rust from Cargo.toml."""
        scanner = ProjectScanner(self.project)
        scan = scanner.scan()
        self.assertEqual(scan.language.value.lower(), "rust")
        self.assertGreater(scan.language.confidence, 0.8)

    def test_scanner_finds_personas(self):
        """ProjectScanner finds all 3 hexwise personas."""
        scanner = ProjectScanner(self.project)
        scan = scanner.scan()
        # ScanResult has persona_files: list[ScoredFile], ScoredFile has path: str
        self.assertGreaterEqual(len(scan.persona_files), 3)
        names = [Path(p.path).stem for p in scan.persona_files]
        self.assertIn("rusti", names)
        self.assertIn("palette", names)
        self.assertIn("checker", names)

    def test_scanner_finds_milestones(self):
        """ProjectScanner finds both milestone files."""
        scanner = ProjectScanner(self.project)
        scan = scanner.scan()
        # ScanResult has backlog_files: list[ScoredFile]
        self.assertGreaterEqual(len(scan.backlog_files), 2)

    def test_scanner_finds_rules_and_dev(self):
        """ProjectScanner finds RULES.md and DEVELOPMENT.md."""
        scanner = ProjectScanner(self.project)
        scan = scanner.scan()
        # rules_file and dev_guide are Detection objects; check .value is not None
        self.assertIsNotNone(scan.rules_file.value)
        self.assertIsNotNone(scan.dev_guide.value)

    def test_config_generation_succeeds(self):
        """ConfigGenerator produces valid sprint-config/."""
        self._generate_config()
        config_dir = str(self.project / "sprint-config")
        ok, errors = validate_project(config_dir)
        self.assertTrue(ok, f"Validation failed: {errors}")

    def test_config_has_correct_language(self):
        """Generated config has language = rust."""
        config = self._generate_config()
        self.assertEqual(config["project"]["language"].lower(), "rust")

    def test_config_has_rust_ci_commands(self):
        """Generated config has Rust-specific CI commands."""
        config = self._generate_config()
        checks = config["ci"]["check_commands"]
        # Should include cargo commands
        has_cargo = any("cargo" in cmd for cmd in checks)
        self.assertTrue(has_cargo, f"No cargo commands in: {checks}")

    def test_config_has_three_personas(self):
        """Generated team/INDEX.md references all 3 personas."""
        self._generate_config()
        index = (self.project / "sprint-config" / "team" / "INDEX.md").read_text()
        for name in ("rusti", "palette", "checker"):
            self.assertIn(name, index.lower(), f"Missing {name} in INDEX.md")

    def test_config_has_two_milestones(self):
        """Generated backlog has both milestones."""
        self._generate_config()
        ms_dir = self.project / "sprint-config" / "backlog" / "milestones"
        milestone_files = list(ms_dir.glob("*.md"))
        self.assertGreaterEqual(len(milestone_files), 2)

    def test_repo_detection(self):
        """Generated config has correct repo from git remote."""
        config = self._generate_config()
        self.assertIn("testowner/hexwise", config["project"]["repo"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests**

```bash
python tests/test_hexwise_setup.py -v
```

Expected: All tests pass. If any fail, fix the fixture or the scanner before proceeding.

- [ ] **Step 3: Fix any failures**

Common issues to expect:
- `ProjectScanner` may not find personas if it looks for a specific directory name (e.g., `dev-team` vs `team`). Check `sprint_init.py` `detect_persona_files()` for the search patterns — it scans all `.md` files for persona headings, not specific directories. Adjust fixture if needed.
- Story table format may not match `parse_milestone_stories()` regex. Check `populate_issues.py:84` for the expected pattern: `| US-NNNN | title | SNN | SP | PN |`.
- `RULES.md` vs `rules.md` — check if the scanner is case-sensitive (`detect_rules_file()` in `sprint_init.py`).

- [ ] **Step 4: Commit**

```bash
git add tests/test_hexwise_setup.py
git commit -m "test: add hexwise smoke test — sprint_init against fixture"
```

---

## Chunk 2: FakeGitHub Extension + Full Pipeline Test

Extend FakeGitHub to cover the operations needed for sprint-run (PR create/review/merge, issue edit, CI checks with branch filtering). Then write an end-to-end pipeline test that runs the full setup → bootstrap → populate flow against hexwise.

### Task 5: Extend FakeGitHub with PR and issue operations

**Files:**
- Create: `tests/fake_github.py` (extracted from `scripts/test_lifecycle.py`, extended)

Extract FakeGitHub into its own module so both old and new tests can use it. Extend with PR create/review/merge and issue edit.

- [ ] **Step 1: Create tests/fake_github.py**

Extract `FakeGitHub`, `make_patched_subprocess` from `scripts/test_lifecycle.py` into `tests/fake_github.py`. Add new capabilities:

```python
#!/usr/bin/env python3
"""FakeGitHub: in-memory GitHub state for testing giles scripts.

Intercepts `gh` CLI subprocess calls and simulates GitHub API responses.
Supports: labels, milestones, issues, PRs (create/review/merge), runs, releases.

Usage:
    fake = FakeGitHub()
    with patch("subprocess.run", make_patched_subprocess(fake)):
        # code that calls gh CLI
"""
from __future__ import annotations

import json
import subprocess


class FakeGitHub:
    """Simulate GitHub API responses for gh CLI calls."""

    def __init__(self):
        self.labels: dict[str, dict] = {}
        self.milestones: list[dict] = []
        self.issues: list[dict] = []
        self.releases: list[dict] = []
        self.runs: list[dict] = []
        self.prs: list[dict] = []
        self.reviews: list[dict] = []
        self._next_issue = 1
        self._next_ms = 1
        self._next_pr = 1

    # -- Dispatch -------------------------------------------------------------

    def handle(self, args: list[str]) -> subprocess.CompletedProcess:
        if not args:
            return self._fail("no args")
        cmd = args[0]
        dispatch = {
            "label": self._handle_label,
            "api": self._handle_api,
            "issue": self._handle_issue,
            "run": self._handle_run,
            "pr": self._handle_pr,
            "release": self._handle_release,
            "auth": lambda a: self._ok(""),
            "--version": lambda a: self._ok("gh version 2.40.0 (fake)"),
        }
        handler = dispatch.get(cmd)
        if handler:
            return handler(args[1:])
        return self._fail(f"unknown command: {cmd}")

    def _ok(self, stdout: str) -> subprocess.CompletedProcess:
        return subprocess.CompletedProcess(
            args=[], returncode=0, stdout=stdout, stderr="",
        )

    def _fail(self, msg: str) -> subprocess.CompletedProcess:
        return subprocess.CompletedProcess(
            args=[], returncode=1, stdout="", stderr=msg,
        )

    # -- Labels ---------------------------------------------------------------

    def _handle_label(self, args: list[str]) -> subprocess.CompletedProcess:
        if not args or args[0] != "create":
            return self._fail("only label create supported")
        name = args[1] if len(args) > 1 else ""
        color, desc = "", ""
        i = 2
        while i < len(args):
            if args[i] == "--color" and i + 1 < len(args):
                color = args[i + 1]; i += 2
            elif args[i] == "--description" and i + 1 < len(args):
                desc = args[i + 1]; i += 2
            elif args[i] == "--force":
                i += 1
            else:
                i += 1
        self.labels[name] = {"name": name, "color": color, "description": desc}
        return self._ok("")

    # -- API (milestones) -----------------------------------------------------

    def _handle_api(self, args: list[str]) -> subprocess.CompletedProcess:
        if not args:
            return self._fail("no api path")
        path = args[0]
        if "milestones" in path and "-f" in args:
            title, description = "", ""
            for i, a in enumerate(args):
                if a == "-f" and i + 1 < len(args):
                    kv = args[i + 1]
                    if kv.startswith("title="):
                        title = kv[6:]
                    elif kv.startswith("description="):
                        description = kv[12:]
            ms = {
                "number": self._next_ms, "title": title,
                "description": description, "state": "open",
                "open_issues": 0, "closed_issues": 0,
            }
            self._next_ms += 1
            self.milestones.append(ms)
            return self._ok(json.dumps(ms))
        if "milestones" in path and "-f" not in args and "-X" not in args:
            return self._ok(json.dumps(self.milestones))
        if "milestones" in path and "-X" in args:
            return self._ok("{}")
        return self._ok("[]")

    # -- Issues ---------------------------------------------------------------

    def _handle_issue(self, args: list[str]) -> subprocess.CompletedProcess:
        if not args:
            return self._fail("no issue subcommand")
        sub = args[0]

        if sub == "create":
            title, body, milestone = "", "", ""
            labels = []
            i = 1
            while i < len(args):
                if args[i] == "--title" and i + 1 < len(args):
                    title = args[i + 1]; i += 2
                elif args[i] == "--body" and i + 1 < len(args):
                    body = args[i + 1]; i += 2
                elif args[i] == "--label" and i + 1 < len(args):
                    labels.append(args[i + 1]); i += 2
                elif args[i] == "--milestone" and i + 1 < len(args):
                    milestone = args[i + 1]; i += 2
                else:
                    i += 1
            issue = {
                "number": self._next_issue, "title": title, "body": body,
                "state": "open",
                "labels": [{"name": l} for l in labels],
                "milestone": {"title": milestone} if milestone else None,
                "closedAt": None,
            }
            self._next_issue += 1
            self.issues.append(issue)
            return self._ok(
                f"https://github.com/testowner/hexwise/issues/{issue['number']}"
            )

        elif sub == "edit":
            # gh issue edit <number> --add-label <label> ...
            number = int(args[1]) if len(args) > 1 else 0
            issue = next((i for i in self.issues if i["number"] == number), None)
            if not issue:
                return self._fail(f"issue {number} not found")
            i = 2
            while i < len(args):
                if args[i] == "--add-label" and i + 1 < len(args):
                    issue["labels"].append({"name": args[i + 1]}); i += 2
                elif args[i] == "--remove-label" and i + 1 < len(args):
                    issue["labels"] = [
                        l for l in issue["labels"] if l["name"] != args[i + 1]
                    ]; i += 2
                elif args[i] == "--milestone" and i + 1 < len(args):
                    issue["milestone"] = {"title": args[i + 1]}; i += 2
                else:
                    i += 1
            return self._ok("")

        elif sub == "close":
            number = int(args[1]) if len(args) > 1 else 0
            issue = next((i for i in self.issues if i["number"] == number), None)
            if issue:
                issue["state"] = "closed"
                issue["closedAt"] = "2026-03-10T00:00:00Z"
            return self._ok("")

        elif sub == "list":
            state_filter, milestone_filter = "open", ""
            i = 1
            while i < len(args):
                if args[i] == "--state" and i + 1 < len(args):
                    state_filter = args[i + 1]; i += 2
                elif args[i] == "--milestone" and i + 1 < len(args):
                    milestone_filter = args[i + 1]; i += 2
                elif args[i] in ("--json", "--limit") and i + 1 < len(args):
                    i += 2
                else:
                    i += 1
            filtered = self.issues
            if state_filter != "all":
                filtered = [iss for iss in filtered if iss["state"] == state_filter]
            if milestone_filter:
                filtered = [
                    iss for iss in filtered
                    if (iss.get("milestone") or {}).get("title") == milestone_filter
                ]
            return self._ok(json.dumps(filtered))

        return self._fail(f"issue {sub} not supported")

    # -- PRs ------------------------------------------------------------------

    def _handle_pr(self, args: list[str]) -> subprocess.CompletedProcess:
        if not args:
            return self._fail("no pr subcommand")
        sub = args[0]

        if sub == "create":
            title, body, base, head, milestone = "", "", "main", "", ""
            labels = []
            i = 1
            while i < len(args):
                if args[i] == "--title" and i + 1 < len(args):
                    title = args[i + 1]; i += 2
                elif args[i] == "--body" and i + 1 < len(args):
                    body = args[i + 1]; i += 2
                elif args[i] == "--base" and i + 1 < len(args):
                    base = args[i + 1]; i += 2
                elif args[i] == "--head" and i + 1 < len(args):
                    head = args[i + 1]; i += 2
                elif args[i] == "--label" and i + 1 < len(args):
                    labels.append(args[i + 1]); i += 2
                elif args[i] == "--milestone" and i + 1 < len(args):
                    milestone = args[i + 1]; i += 2
                else:
                    i += 1
            pr = {
                "number": self._next_pr, "title": title, "body": body,
                "state": "open", "base": {"ref": base}, "head": {"ref": head},
                "labels": [{"name": l} for l in labels],
                "milestone": {"title": milestone} if milestone else None,
                "reviewDecision": "", "merged": False,
                "statusCheckRollup": [],
                "createdAt": "2026-03-10T00:00:00Z",
            }
            self._next_pr += 1
            self.prs.append(pr)
            return self._ok(
                f"https://github.com/testowner/hexwise/pull/{pr['number']}"
            )

        elif sub == "review":
            # gh pr review <number> --approve / --request-changes --body <msg>
            number = int(args[1]) if len(args) > 1 else 0
            action, body = "approve", ""
            i = 2
            while i < len(args):
                if args[i] == "--approve":
                    action = "approve"; i += 1
                elif args[i] == "--request-changes":
                    action = "request_changes"; i += 1
                elif args[i] == "--body" and i + 1 < len(args):
                    body = args[i + 1]; i += 2
                else:
                    i += 1
            pr = next((p for p in self.prs if p["number"] == number), None)
            if pr and action == "approve":
                pr["reviewDecision"] = "APPROVED"
            review = {"pr": number, "action": action, "body": body}
            self.reviews.append(review)
            return self._ok("")

        elif sub == "merge":
            number = int(args[1]) if len(args) > 1 else 0
            pr = next((p for p in self.prs if p["number"] == number), None)
            if pr:
                pr["state"] = "closed"
                pr["merged"] = True
            return self._ok("")

        elif sub == "list":
            state_filter = "open"
            i = 1
            while i < len(args):
                if args[i] == "--state" and i + 1 < len(args):
                    state_filter = args[i + 1]; i += 2
                elif args[i] in ("--json", "--limit") and i + 1 < len(args):
                    i += 2
                else:
                    i += 1
            filtered = self.prs
            if state_filter != "all":
                filtered = [p for p in filtered if p["state"] == state_filter]
            return self._ok(json.dumps(filtered))

        return self._fail(f"pr {sub} not supported")

    # -- Runs -----------------------------------------------------------------

    def _handle_run(self, args: list[str]) -> subprocess.CompletedProcess:
        if not args:
            return self._fail("no run subcommand")
        sub = args[0]
        if sub == "list":
            # Support --branch filter
            branch = ""
            i = 1
            while i < len(args):
                if args[i] == "--branch" and i + 1 < len(args):
                    branch = args[i + 1]; i += 2
                elif args[i] in ("--json", "--limit") and i + 1 < len(args):
                    i += 2
                else:
                    i += 1
            filtered = self.runs
            if branch:
                filtered = [r for r in filtered if r.get("headBranch") == branch]
            return self._ok(json.dumps(filtered))
        elif sub == "view":
            return self._ok("no logs")
        return self._fail(f"run {sub} not supported")

    # -- Releases -------------------------------------------------------------

    def _handle_release(self, args: list[str]) -> subprocess.CompletedProcess:
        if not args:
            return self._fail("no release subcommand")
        sub = args[0]
        if sub == "create":
            tag = ""
            title = ""
            notes = ""
            i = 1
            while i < len(args):
                if args[i] == "--tag" and i + 1 < len(args):
                    tag = args[i + 1]; i += 2
                elif args[i] == "--title" and i + 1 < len(args):
                    title = args[i + 1]; i += 2
                elif args[i] == "--notes" and i + 1 < len(args):
                    notes = args[i + 1]; i += 2
                elif not args[i].startswith("--") and not tag:
                    tag = args[i]; i += 1
                else:
                    i += 1
            self.releases.append({"tag_name": tag, "title": title, "body": notes})
            return self._ok(
                f"https://github.com/testowner/hexwise/releases/tag/{tag}"
            )
        elif sub == "view":
            tag = args[1] if len(args) > 1 else ""
            return self._ok(json.dumps({
                "url": f"https://github.com/testowner/hexwise/releases/tag/{tag}"
            }))
        return self._fail(f"release {sub} not supported")

    # -- State dump -----------------------------------------------------------

    def dump_state(self) -> dict:
        """Dump full state for golden-run snapshots."""
        return {
            "labels": dict(self.labels),
            "milestones": list(self.milestones),
            "issues": list(self.issues),
            "prs": list(self.prs),
            "reviews": list(self.reviews),
            "releases": list(self.releases),
            "runs": list(self.runs),
        }


def make_patched_subprocess(fake_gh: FakeGitHub):
    """Create a subprocess.run replacement that intercepts gh calls."""
    _real_run = subprocess.run

    def patched_run(args, *a, **kw):
        if isinstance(args, list) and args and args[0] == "gh":
            return fake_gh.handle(args[1:])
        return _real_run(args, *a, **kw)

    return patched_run
```

- [ ] **Step 2: Verify the extracted FakeGitHub imports correctly**

```bash
python -c "import sys; sys.path.insert(0, 'tests'); from fake_github import FakeGitHub; print('import OK')"
```

- [ ] **Step 3: Commit**

```bash
git add tests/fake_github.py
git commit -m "refactor: extract FakeGitHub into tests/fake_github.py with PR/issue extensions"
```

### Task 6: Update existing tests to use shared FakeGitHub

**Files:**
- Modify: `scripts/test_lifecycle.py` — replace inline FakeGitHub with import from `tests/fake_github.py`

- [ ] **Step 1: Update imports in test_lifecycle.py**

Replace the inline `FakeGitHub` class and `make_patched_subprocess` function (lines 46-271) with:

```python
# Shared FakeGitHub mock — extracted to tests/fake_github.py
_TESTS_DIR = PLUGIN_ROOT / "tests"
sys.path.insert(0, str(_TESTS_DIR))
from fake_github import FakeGitHub, make_patched_subprocess
```

Remove the old `FakeGitHub` class and `make_patched_subprocess` function from the file. Keep `MockProject` and all test classes.

- [ ] **Step 2: Run existing tests to verify no regression**

```bash
python scripts/test_lifecycle.py -v
python scripts/test_gh_interactions.py -v
```

Expected: 13/13 and 63/63 pass.

- [ ] **Step 3: Commit**

```bash
git add scripts/test_lifecycle.py tests/fake_github.py
git commit -m "refactor: test_lifecycle.py uses shared FakeGitHub from tests/"
```

### Task 7: Full pipeline test — setup through issue population

**Files:**
- Modify: `tests/test_hexwise_setup.py` — add full pipeline test

- [ ] **Step 1: Add pipeline test to test_hexwise_setup.py**

Add this test class after the existing `TestHexwiseSetup`:

```python
sys.path.insert(0, str(REPO_ROOT / "tests"))
from fake_github import FakeGitHub, make_patched_subprocess

sys.path.insert(0, str(REPO_ROOT / "skills" / "sprint-setup" / "scripts"))
import bootstrap_github
import populate_issues


class TestHexwisePipeline(unittest.TestCase):
    """Full pipeline: init -> bootstrap -> populate against hexwise."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="hexwise-pipeline-")
        self.root = Path(self.tmpdir)
        shutil.copytree(FIXTURE_DIR, self.root / "hexwise")
        self.project = self.root / "hexwise"
        subprocess.run(
            ["git", "init"], cwd=str(self.project),
            capture_output=True, text=True,
        )
        subprocess.run(
            ["git", "remote", "add", "origin",
             "https://github.com/testowner/hexwise.git"],
            cwd=str(self.project), capture_output=True, text=True,
        )
        subprocess.run(
            ["git", "add", "."], cwd=str(self.project),
            capture_output=True, text=True,
        )
        subprocess.run(
            ["git", "-c", "user.name=Test", "-c", "user.email=test@test.com",
             "commit", "-m", "feat: initial"],
            cwd=str(self.project), capture_output=True, text=True,
        )
        self.fake_gh = FakeGitHub()
        self._saved_cwd = os.getcwd()
        os.chdir(self.project)

    def tearDown(self):
        os.chdir(self._saved_cwd)
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _generate_config(self) -> dict:
        scanner = ProjectScanner(self.project)
        scan = scanner.scan()
        gen = ConfigGenerator(scan)
        gen.generate()
        toml_path = self.project / "sprint-config" / "project.toml"
        return parse_simple_toml(toml_path.read_text())

    def test_full_setup_pipeline(self):
        """Init -> labels -> milestones -> issues all succeed."""
        config = self._generate_config()

        with patch("subprocess.run", make_patched_subprocess(self.fake_gh)):
            bootstrap_github.create_static_labels()
            bootstrap_github.create_persona_labels(config)
            bootstrap_github.create_milestones_on_github(config)

            from validate_config import get_milestones
            milestone_files = get_milestones(config)
            stories = populate_issues.parse_milestone_stories(
                milestone_files, config,
            )

            ms_numbers = {
                ms["title"]: ms["number"]
                for ms in self.fake_gh.milestones
            }
            ms_titles = {}
            for i, mf in enumerate(milestone_files, 1):
                if i <= len(self.fake_gh.milestones):
                    ms_titles[i] = self.fake_gh.milestones[i - 1]["title"]
                else:
                    ms_titles[i] = f"Sprint {i}"

            existing = populate_issues.get_existing_issues()
            for story in stories:
                if story.story_id not in existing:
                    populate_issues.create_issue(story, ms_numbers, ms_titles)

        # Verify results
        self.assertGreater(len(self.fake_gh.labels), 10, "Should have many labels")
        self.assertEqual(len(self.fake_gh.milestones), 2, "Should have 2 milestones")
        self.assertEqual(len(self.fake_gh.issues), 6, "Should have 6 issues (stories)")

        # Verify persona labels exist
        persona_labels = [l for l in self.fake_gh.labels if l.startswith("persona:")]
        self.assertEqual(len(persona_labels), 3, "Should have 3 persona labels")

        # Verify stories have correct IDs
        issue_titles = [iss["title"] for iss in self.fake_gh.issues]
        for sid in ("US-0101", "US-0102", "US-0103", "US-0201", "US-0202", "US-0203"):
            self.assertTrue(
                any(sid in t for t in issue_titles),
                f"{sid} not found in {issue_titles}",
            )

    def test_ci_workflow_has_cargo(self):
        """setup_ci generates a workflow with cargo commands for Rust."""
        config = self._generate_config()
        sys.path.insert(0, str(REPO_ROOT / "skills" / "sprint-setup" / "scripts"))
        from setup_ci import generate_ci_yaml

        yaml_content = generate_ci_yaml(config)
        self.assertIn("cargo", yaml_content)
        self.assertIn("cargo test", yaml_content)
        self.assertIn("cargo clippy", yaml_content)

    def test_state_dump(self):
        """FakeGitHub.dump_state() captures full state for golden snapshots."""
        config = self._generate_config()

        with patch("subprocess.run", make_patched_subprocess(self.fake_gh)):
            bootstrap_github.create_static_labels()
            bootstrap_github.create_persona_labels(config)
            bootstrap_github.create_milestones_on_github(config)

        state = self.fake_gh.dump_state()
        self.assertIn("labels", state)
        self.assertIn("milestones", state)
        self.assertGreater(len(state["labels"]), 0)
        self.assertGreater(len(state["milestones"]), 0)
```

- [ ] **Step 2: Run all tests**

```bash
python tests/test_hexwise_setup.py -v
```

Expected: All pass, including the pipeline test showing 6 issues created.

- [ ] **Step 3: Commit**

```bash
git add tests/test_hexwise_setup.py
git commit -m "test: add hexwise full pipeline test — init through issue population"
```

---

## Chunk 3: Golden-Run Infrastructure

Build the recording/replay system. The recorder captures state snapshots (GitHub state + file tree) at each skill phase during a live golden run. The replay harness loads snapshots and verifies scripts produce the same results.

### Task 8: Create the golden-run recorder

**Files:**
- Create: `tests/golden_recorder.py`

The recorder captures state snapshots between skill phases. Each snapshot includes: FakeGitHub state dump, sprint-config/ file tree with contents, and sprint tracking file contents.

- [ ] **Step 1: Write golden_recorder.py**

```python
#!/usr/bin/env python3
"""Golden-run recorder: captures state snapshots at skill phase boundaries.

During a live golden run, call `recorder.snapshot(phase_name)` after each
skill phase completes. The recorder saves:
  - FakeGitHub state (labels, milestones, issues, PRs, reviews)
  - File tree of sprint-config/ and sprint tracking files
  - Phase metadata (name, ordering)

Snapshots are saved to tests/golden/recordings/.

Usage:
    recorder = GoldenRecorder(project_root, fake_gh)
    # ... run skill phase ...
    recorder.snapshot("01-setup-labels")
    # ... run next phase ...
    recorder.snapshot("02-setup-milestones")
    recorder.write_manifest()
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fake_github import FakeGitHub

GOLDEN_DIR = Path(__file__).resolve().parent / "golden" / "recordings"


class GoldenRecorder:
    """Record state snapshots during a golden run."""

    def __init__(self, project_root: Path, fake_gh: "FakeGitHub"):
        self.project_root = project_root
        self.fake_gh = fake_gh
        self.phases: list[str] = []
        self.output_dir = GOLDEN_DIR
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def snapshot(self, phase_name: str) -> Path:
        """Capture current state and save as a golden snapshot."""
        self.phases.append(phase_name)
        snapshot = {
            "phase": phase_name,
            "github_state": self.fake_gh.dump_state(),
            "files": self._capture_files(),
        }
        out_path = self.output_dir / f"{phase_name}.json"
        out_path.write_text(
            json.dumps(snapshot, indent=2, default=str),
            encoding="utf-8",
        )
        return out_path

    def write_manifest(self) -> Path:
        """Write manifest listing all recorded phases in order."""
        manifest = {
            "project": "hexwise",
            "phases": self.phases,
            "total_phases": len(self.phases),
        }
        manifest_path = self.output_dir / "manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, indent=2),
            encoding="utf-8",
        )
        return manifest_path

    def _capture_files(self) -> dict[str, str]:
        """Capture contents of sprint-config/ and tracking files."""
        files = {}
        config_dir = self.project_root / "sprint-config"
        if config_dir.exists():
            for p in sorted(config_dir.rglob("*")):
                if p.is_file():
                    rel = str(p.relative_to(self.project_root))
                    try:
                        files[rel] = p.read_text(encoding="utf-8")
                    except UnicodeDecodeError:
                        files[rel] = "<binary>"

        # Also capture sprint tracking files — check common locations
        # (sprints_dir comes from project.toml [paths] sprints_dir)
        for tracking_name in ("sprints", "docs/sprints", "docs/dev-team/sprints"):
            tracking_dir = self.project_root / tracking_name
            if tracking_dir.exists():
                for p in sorted(tracking_dir.rglob("*")):
                    if p.is_file():
                        rel = str(p.relative_to(self.project_root))
                        try:
                            files[rel] = p.read_text(encoding="utf-8")
                        except UnicodeDecodeError:
                            files[rel] = "<binary>"
        return files
```

- [ ] **Step 2: Commit**

```bash
git add tests/golden_recorder.py
git commit -m "feat: add golden-run recorder for state snapshots"
```

### Task 9: Create the golden-run replay harness

**Files:**
- Create: `tests/golden_replay.py`

The replay harness loads golden snapshots and provides assertions for comparing current state against recorded golden state.

- [ ] **Step 1: Write golden_replay.py**

```python
#!/usr/bin/env python3
"""Golden-run replay: load snapshots and assert state matches.

Used in regression tests to verify scripts still produce the same
GitHub API calls and file mutations as the golden run.

Usage:
    replayer = GoldenReplayer()
    snapshot = replayer.load_snapshot("01-setup-labels")
    # ... run scripts ...
    replayer.assert_github_matches(snapshot, fake_gh)
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fake_github import FakeGitHub

GOLDEN_DIR = Path(__file__).resolve().parent / "golden" / "recordings"


class GoldenReplayer:
    """Load and compare golden-run snapshots."""

    def __init__(self, golden_dir: Path | None = None):
        self.golden_dir = golden_dir or GOLDEN_DIR

    def has_recordings(self) -> bool:
        """Check if golden recordings exist."""
        manifest = self.golden_dir / "manifest.json"
        return manifest.exists()

    def load_manifest(self) -> dict:
        """Load the golden-run manifest."""
        manifest_path = self.golden_dir / "manifest.json"
        return json.loads(manifest_path.read_text(encoding="utf-8"))

    def load_snapshot(self, phase_name: str) -> dict:
        """Load a single phase snapshot."""
        path = self.golden_dir / f"{phase_name}.json"
        return json.loads(path.read_text(encoding="utf-8"))

    def assert_labels_match(self, snapshot: dict, fake_gh: "FakeGitHub") -> list[str]:
        """Compare label state. Returns list of differences."""
        expected = set(snapshot["github_state"]["labels"].keys())
        actual = set(fake_gh.labels.keys())
        diffs = []
        missing = expected - actual
        extra = actual - expected
        if missing:
            diffs.append(f"Missing labels: {sorted(missing)}")
        if extra:
            diffs.append(f"Extra labels: {sorted(extra)}")
        return diffs

    def assert_milestones_match(
        self, snapshot: dict, fake_gh: "FakeGitHub",
    ) -> list[str]:
        """Compare milestone state. Returns list of differences."""
        expected_titles = {
            ms["title"] for ms in snapshot["github_state"]["milestones"]
        }
        actual_titles = {ms["title"] for ms in fake_gh.milestones}
        diffs = []
        if expected_titles != actual_titles:
            diffs.append(
                f"Milestone mismatch: expected {sorted(expected_titles)}, "
                f"got {sorted(actual_titles)}"
            )
        return diffs

    def assert_issues_match(self, snapshot: dict, fake_gh: "FakeGitHub") -> list[str]:
        """Compare issue state. Returns list of differences."""
        expected_titles = sorted(
            iss["title"] for iss in snapshot["github_state"]["issues"]
        )
        actual_titles = sorted(
            iss["title"] for iss in fake_gh.issues
        )
        diffs = []
        if len(expected_titles) != len(actual_titles):
            diffs.append(
                f"Issue count mismatch: expected {len(expected_titles)}, "
                f"got {len(actual_titles)}"
            )
        for exp, act in zip(expected_titles, actual_titles):
            if exp != act:
                diffs.append(f"Issue title mismatch: expected '{exp}', got '{act}'")
        return diffs

    def assert_files_match(
        self, snapshot: dict, project_root: Path,
    ) -> list[str]:
        """Compare file tree. Returns list of differences."""
        expected_files = set(snapshot.get("files", {}).keys())
        actual_files = set()
        config_dir = project_root / "sprint-config"
        if config_dir.exists():
            for p in sorted(config_dir.rglob("*")):
                if p.is_file():
                    actual_files.add(str(p.relative_to(project_root)))
        diffs = []
        missing = expected_files - actual_files
        extra = actual_files - expected_files
        if missing:
            diffs.append(f"Missing files: {sorted(missing)}")
        if extra:
            diffs.append(f"Extra files: {sorted(extra)}")
        return diffs
```

- [ ] **Step 2: Commit**

```bash
git add tests/golden_replay.py
git commit -m "feat: add golden-run replay harness for regression testing"
```

### Task 10: Create the golden-run recording test

**Files:**
- Create: `tests/test_golden_run.py`

This test does two things:
1. **Record mode** (first run, or when `GOLDEN_RECORD=1`): Runs the full setup pipeline, records state snapshots.
2. **Replay mode** (subsequent runs): Loads golden snapshots, runs the pipeline, asserts state matches.

- [ ] **Step 1: Write test_golden_run.py**

```python
#!/usr/bin/env python3
"""Golden-run test: record or replay the full setup pipeline.

Uses a SINGLE test method that runs all phases sequentially on one
FakeGitHub instance, so state accumulates across phases (labels persist
when milestones are created, milestones persist when issues are created).

First run (or GOLDEN_RECORD=1): runs pipeline, saves golden snapshots.
Subsequent runs: runs pipeline, asserts state matches golden snapshots.

Run: python tests/test_golden_run.py -v
Record: GOLDEN_RECORD=1 python tests/test_golden_run.py -v
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
FIXTURE_DIR = TESTS_DIR / "fixtures" / "hexwise"

sys.path.insert(0, str(REPO_ROOT / "scripts"))
from validate_config import parse_simple_toml, validate_project, get_milestones
from sprint_init import ProjectScanner, ConfigGenerator

sys.path.insert(0, str(REPO_ROOT / "skills" / "sprint-setup" / "scripts"))
import bootstrap_github
import populate_issues
import setup_ci

sys.path.insert(0, str(TESTS_DIR))
from fake_github import FakeGitHub, make_patched_subprocess
from golden_recorder import GoldenRecorder
from golden_replay import GoldenReplayer

RECORD_MODE = os.environ.get("GOLDEN_RECORD", "") == "1"


class TestGoldenRun(unittest.TestCase):
    """Golden-run: record or replay the full setup pipeline.

    Uses a single test method so FakeGitHub state accumulates across
    phases, matching how the real setup pipeline works.
    """

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="golden-run-")
        self.root = Path(self.tmpdir)
        shutil.copytree(FIXTURE_DIR, self.root / "hexwise")
        self.project = self.root / "hexwise"
        # Init git
        subprocess.run(
            ["git", "init"], cwd=str(self.project),
            capture_output=True, text=True,
        )
        subprocess.run(
            ["git", "remote", "add", "origin",
             "https://github.com/testowner/hexwise.git"],
            cwd=str(self.project), capture_output=True, text=True,
        )
        subprocess.run(
            ["git", "add", "."], cwd=str(self.project),
            capture_output=True, text=True,
        )
        subprocess.run(
            ["git", "-c", "user.name=Test", "-c", "user.email=test@test.com",
             "commit", "-m", "feat: initial"],
            cwd=str(self.project), capture_output=True, text=True,
        )
        self.fake_gh = FakeGitHub()
        self._saved_cwd = os.getcwd()
        os.chdir(self.project)

    def tearDown(self):
        os.chdir(self._saved_cwd)
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _generate_config(self) -> dict:
        scanner = ProjectScanner(self.project)
        scan = scanner.scan()
        gen = ConfigGenerator(scan)
        gen.generate()
        toml_path = self.project / "sprint-config" / "project.toml"
        return parse_simple_toml(toml_path.read_text())

    def _check_or_record(self, recorder, replayer, phase_name, check_fn):
        """Record a snapshot or replay-compare against golden state."""
        if RECORD_MODE:
            recorder.snapshot(phase_name)
        elif replayer.has_recordings():
            snapshot = replayer.load_snapshot(phase_name)
            diffs = check_fn(snapshot)
            self.assertEqual(diffs, [], f"{phase_name} mismatch: {diffs}")

    def test_golden_full_setup_pipeline(self):
        """Full sequential pipeline: init -> labels -> milestones -> issues -> CI.

        All phases run on the SAME FakeGitHub instance so state accumulates.
        Snapshots capture cumulative state at each checkpoint.
        """
        recorder = GoldenRecorder(self.project, self.fake_gh)
        replayer = GoldenReplayer()

        # Phase 1: sprint_init generates valid config
        config = self._generate_config()
        config_dir = str(self.project / "sprint-config")
        ok, errors = validate_project(config_dir)
        self.assertTrue(ok, f"Config validation failed: {errors}")

        self._check_or_record(
            recorder, replayer, "01-setup-init",
            lambda snap: replayer.assert_files_match(snap, self.project),
        )

        # Phase 2: bootstrap creates labels (cumulative)
        with patch("subprocess.run", make_patched_subprocess(self.fake_gh)):
            bootstrap_github.create_static_labels()
            bootstrap_github.create_persona_labels(config)

        self.assertGreater(len(self.fake_gh.labels), 10)
        self._check_or_record(
            recorder, replayer, "02-setup-labels",
            lambda snap: replayer.assert_labels_match(snap, self.fake_gh),
        )

        # Phase 3: bootstrap creates milestones (cumulative — labels still present)
        with patch("subprocess.run", make_patched_subprocess(self.fake_gh)):
            bootstrap_github.create_milestones_on_github(config)

        self.assertEqual(len(self.fake_gh.milestones), 2)
        self._check_or_record(
            recorder, replayer, "03-setup-milestones",
            lambda snap: replayer.assert_milestones_match(snap, self.fake_gh),
        )

        # Phase 4: populate creates issues (cumulative — labels + milestones present)
        with patch("subprocess.run", make_patched_subprocess(self.fake_gh)):
            milestone_files = get_milestones(config)
            stories = populate_issues.parse_milestone_stories(
                milestone_files, config,
            )
            ms_numbers = {
                ms["title"]: ms["number"]
                for ms in self.fake_gh.milestones
            }
            ms_titles = {}
            for i, mf in enumerate(milestone_files, 1):
                if i <= len(self.fake_gh.milestones):
                    ms_titles[i] = self.fake_gh.milestones[i - 1]["title"]
                else:
                    ms_titles[i] = f"Sprint {i}"

            for story in stories:
                if story.story_id not in populate_issues.get_existing_issues():
                    populate_issues.create_issue(story, ms_numbers, ms_titles)

        self.assertEqual(len(self.fake_gh.issues), 6)
        self._check_or_record(
            recorder, replayer, "04-setup-issues",
            lambda snap: replayer.assert_issues_match(snap, self.fake_gh),
        )

        # Phase 5: CI workflow generation
        yaml_content = setup_ci.generate_ci_yaml(config)
        self.assertIn("cargo test", yaml_content)
        self.assertIn("cargo clippy", yaml_content)

        if RECORD_MODE:
            ci_path = self.project / ".github" / "workflows" / "ci.yml"
            ci_path.parent.mkdir(parents=True, exist_ok=True)
            ci_path.write_text(yaml_content)
            recorder.snapshot("05-setup-ci")
            # Write manifest after all phases complete
            recorder.write_manifest()
            print("\n=== Golden run recorded. Review tests/golden/recordings/ ===")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run in record mode**

```bash
GOLDEN_RECORD=1 python tests/test_golden_run.py -v
```

Expected: All pass, golden snapshots saved to `tests/golden/recordings/`.

- [ ] **Step 3: Verify recordings exist**

```bash
ls tests/golden/recordings/
```

Expected: `01-setup-init.json`, `02-setup-labels.json`, etc.

- [ ] **Step 4: Run in replay mode**

```bash
python tests/test_golden_run.py -v
```

Expected: All pass by comparing against recorded golden state.

- [ ] **Step 5: Commit recordings and test**

```bash
git add tests/test_golden_run.py tests/golden/
git commit -m "test: add golden-run recording/replay test for hexwise setup pipeline"
```

---

## Chunk 4: Progressive Disclosure Refactor

Refactor the two largest SKILL.md files (`sprint-setup` and `sprint-run`) to use progressive disclosure. Extract procedural details into reference files that Claude reads on-demand. Keep routing/decision logic inline.

### Task 11: Extract sprint-setup prerequisites into reference

**Files:**
- Create: `skills/sprint-setup/references/prerequisites-checklist.md`
- Modify: `skills/sprint-setup/SKILL.md`

- [ ] **Step 1: Read the current SKILL.md to identify exact extraction boundaries**

```bash
grep -n "^##\|^###" skills/sprint-setup/SKILL.md
```

Identify the line range for the prerequisites section (approximately lines 42-166 based on analysis).

- [ ] **Step 2: Create prerequisites-checklist.md**

Extract the prerequisites content (gh CLI install, auth check, git remote, language toolchain, etc.) into `skills/sprint-setup/references/prerequisites-checklist.md`. Keep the full detail including OS-specific install commands.

- [ ] **Step 3: Replace inline prerequisites in SKILL.md**

Replace the ~100-line prerequisites section with a compact reference:

```markdown
### Step 1: Check Prerequisites

Read `references/prerequisites-checklist.md` and verify each item:
1. `gh` CLI installed and authenticated
2. Git remote configured
3. Language toolchain available (detected from project)

If any prerequisite fails, follow the install/fix instructions in the checklist.
Proceed to Step 2 only when all checks pass.
```

- [ ] **Step 4: Run existing tests to verify no regression**

```bash
python scripts/test_lifecycle.py -v
python tests/test_hexwise_setup.py -v
```

- [ ] **Step 5: Commit**

```bash
git add skills/sprint-setup/SKILL.md skills/sprint-setup/references/prerequisites-checklist.md
git commit -m "refactor(sprint-setup): extract prerequisites into reference doc"
```

### Task 12: Condense sprint-setup bootstrap steps

**Files:**
- Modify: `skills/sprint-setup/SKILL.md`

The label taxonomy and CI setup sections duplicate content from `github-conventions.md` and `ci-workflow-template.md`.

- [ ] **Step 1: Condense label taxonomy section**

Replace the ~40-line inline label taxonomy with:

```markdown
#### 2.1 Create Labels

Read `references/github-conventions.md` for the full label taxonomy (persona, sprint, saga, priority, kanban, type categories).

Run the bootstrap script (reads `sprint-config/project.toml` from cwd):
```bash
python skills/sprint-setup/scripts/bootstrap_github.py
```

The script creates all labels idempotently — safe to re-run.
```

- [ ] **Step 2: Condense CI setup section**

Replace the ~32-line inline CI section with:

```markdown
#### 2.5 Generate CI Workflow

Read `references/ci-workflow-template.md` for the workflow structure.

Run the CI setup script (reads `sprint-config/project.toml` from cwd):
```bash
python skills/sprint-setup/scripts/setup_ci.py
```

Supported languages: Rust, Python, Node.js, Go (with graceful fallback for others).
Review the generated `.github/workflows/ci.yml` before committing.
```

- [ ] **Step 3: Add quick-reference table at top of SKILL.md**

After the frontmatter, add:

```markdown
## Quick Reference

| Phase | Read These First |
|-------|-----------------|
| Prerequisites | `references/prerequisites-checklist.md` |
| Labels & Conventions | `references/github-conventions.md` |
| CI Workflow | `references/ci-workflow-template.md` |
| Scripts | `scripts/bootstrap_github.py`, `scripts/populate_issues.py`, `scripts/setup_ci.py` |
```

- [ ] **Step 4: Verify SKILL.md line count is under 100**

```bash
wc -l skills/sprint-setup/SKILL.md
```

Target: under 100 lines (spec success criteria).

- [ ] **Step 5: Commit**

```bash
git add skills/sprint-setup/SKILL.md
git commit -m "refactor(sprint-setup): condense SKILL.md with progressive disclosure"
```

### Task 13: Refactor sprint-run SKILL.md

**Files:**
- Create: `skills/sprint-run/references/story-execution.md`
- Create: `skills/sprint-run/references/context-recovery.md`
- Create: `skills/sprint-run/references/tracking-formats.md`
- Modify: `skills/sprint-run/SKILL.md`

- [ ] **Step 1: Extract story execution details**

The story execution section (approximately lines 118-217) describes 4 kanban transitions with detailed substeps. Extract into `references/story-execution.md` with full detail. Keep the phase detection table and 1-line summaries per transition in SKILL.md.

Content for `story-execution.md`:
- TO-DO -> DESIGN transition (design doc creation, persona assignment)
- DESIGN -> DEV transition (branch creation, TDD workflow, implementer agent)
- DEV -> REVIEW transition (PR creation, reviewer agent)
- REVIEW -> INTEGRATION transition (merge, issue close, tracking update)
- Parallel dispatch rules for multiple stories
- Cross-references to `kanban-protocol.md`, `persona-guide.md`, `implementer.md`, `reviewer.md`

- [ ] **Step 2: Extract context recovery**

Move context recovery steps (approximately lines 308-331) into `references/context-recovery.md`.

- [ ] **Step 3: Extract tracking formats**

Move SPRINT-STATUS.md and story file YAML format specs (approximately lines 334-377) into `references/tracking-formats.md`.

- [ ] **Step 4: Rewrite sprint-run SKILL.md as a routing document**

The new SKILL.md should be ~80 lines:

```markdown
## Quick Reference

| Phase | Read These First |
|-------|-----------------|
| Kickoff | `references/ceremony-kickoff.md`, `references/persona-guide.md` |
| Story Execution | `references/story-execution.md`, `references/kanban-protocol.md` |
| Demo | `references/ceremony-demo.md` |
| Retro | `references/ceremony-retro.md` |
| Lost context? | `references/context-recovery.md` |
| File formats | `references/tracking-formats.md` |

## Phase Detection

[Keep the existing phase detection table inline — it's the router]

## Phase 1: Kickoff
Read `references/ceremony-kickoff.md` for the full ceremony script.
[2-3 line summary of inputs/outputs]

## Phase 2: Story Execution
Read `references/story-execution.md` for the full TDD workflow.
[Phase detection: which transition to execute based on story state]

## Phase 3: Demo
Read `references/ceremony-demo.md` for the full ceremony script.
[2-3 line summary]

## Phase 4: Retro
Read `references/ceremony-retro.md` for the full ceremony script.
[2-3 line summary]
```

- [ ] **Step 5: Verify SKILL.md line count is under 100**

```bash
wc -l skills/sprint-run/SKILL.md
```

Target: under 100 lines (spec success criteria).

- [ ] **Step 6: Run all tests**

```bash
python scripts/test_lifecycle.py -v
python scripts/test_gh_interactions.py -v
python tests/test_hexwise_setup.py -v
```

- [ ] **Step 7: Commit**

```bash
git add skills/sprint-run/SKILL.md skills/sprint-run/references/
git commit -m "refactor(sprint-run): progressive disclosure — SKILL.md routes to reference docs"
```

### Task 14: Light-touch refactor for remaining skills

**Files:**
- Modify: `skills/sprint-release/SKILL.md` — add quick-reference table
- Modify: `skills/sprint-monitor/SKILL.md` — add quick-reference table
- Review: `skills/sprint-teardown/SKILL.md` — confirm no changes needed

- [ ] **Step 1: Add quick-reference table to sprint-release SKILL.md**

After frontmatter:

```markdown
## Quick Reference

| Phase | Read These First |
|-------|-----------------|
| Gate Validation | `references/release-checklist.md` |
| Scripts | `scripts/release_gate.py --help` |
```

- [ ] **Step 2: Add quick-reference table to sprint-monitor SKILL.md**

After frontmatter:

```markdown
## Quick Reference

| Step | Script |
|------|--------|
| Full status check | `scripts/check_status.py [sprint-number]` |
| Burndown update | `skills/sprint-run/scripts/update_burndown.py` |
```

- [ ] **Step 3: Review sprint-teardown SKILL.md**

Read the file. At ~208 lines it exceeds the spec's 100-line target, but teardown is a safety-critical linear checklist — extracting content would reduce clarity without meaningful benefit. Note the deviation from spec and move on.

- [ ] **Step 4: Commit**

```bash
git add skills/sprint-release/SKILL.md skills/sprint-monitor/SKILL.md
git commit -m "refactor: add quick-reference tables to release and monitor skills"
```

---

## Chunk 5: README, Onboarding & Distribution Hygiene

### Task 15: Rewrite README.md

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Read existing README**

```bash
cat README.md
```

Understand what's there now.

- [ ] **Step 2: Rewrite README.md**

~~~markdown
# giles

Agile sprints with persona-driven development in Claude Code.

giles orchestrates GitHub issues, PRs, CI, kanban tracking, and sprint ceremonies
(kickoff, demo, retro) using fictional team personas that implement and review
code in-character.

## What It Looks Like

Here's what happens when you run `/sprint-setup` on a Rust project:

```
> /sprint-setup

Scanning project structure...
  Language: Rust (Cargo.toml)
  Personas: 3 found (rusti.md, palette.md, checker.md)
  Backlog:  2 milestones, 6 stories

Generating sprint-config/...
  project.toml        (created)
  team/INDEX.md        (symlink -> docs/team/INDEX.md)
  team/rusti.md        (symlink -> docs/team/rusti.md)
  team/palette.md      (symlink -> docs/team/palette.md)
  team/checker.md      (symlink -> docs/team/checker.md)
  backlog/milestones/  (symlinked 2 files)
  rules.md             (symlink -> RULES.md)
  development.md       (symlink -> DEVELOPMENT.md)

Bootstrapping GitHub...
  Labels:     18 created (persona, priority, kanban, type, saga)
  Milestones: 2 created
  Issues:     6 created from backlog stories
  CI:         .github/workflows/ci.yml generated

Ready. Run /sprint-run to start Sprint 1.
```

## Quick Start

### Prerequisites

- [Claude Code](https://claude.ai/code) installed
- A GitHub repo with `gh` CLI [authenticated](https://cli.github.com/manual/gh_auth_login)
- Project docs: team personas (markdown files with Role/Voice/Domain sections)
  and a sprint backlog (milestone files with story tables)

### Install

Add giles as a Claude Code plugin:

```bash
claude plugin add jbrjake/giles
```

### Run Your First Sprint

**1. Bootstrap your project:**

```
/sprint-setup
```

giles scans your project, detects the language and toolchain, finds your
persona files and backlog, and generates a `sprint-config/` directory.
It then creates GitHub labels, milestones, and issues from your backlog.

**2. Start the sprint:**

```
/sprint-run
```

giles runs a kickoff ceremony, assigns stories to personas, and begins
the development cycle: design, implement (TDD), review, merge -- all
in-persona.

**3. Monitor progress (optional):**

```
/loop 5m sprint-monitor
```

Continuously checks CI status, PR reviews, and burndown progress.

## Skills

| Skill | What It Does | When to Use |
|-------|-------------|-------------|
| `sprint-setup` | Bootstrap project config, GitHub labels/milestones/issues, CI | Once per project |
| `sprint-run` | Run sprint ceremonies and story execution | Each sprint |
| `sprint-monitor` | Check CI, PRs, burndown | Alongside sprint-run via `/loop` |
| `sprint-release` | Validate gates, tag, create GitHub Release | At milestone end |
| `sprint-teardown` | Safely remove sprint-config/ | When done with giles |

## Configuration

giles reads from `sprint-config/project.toml`, generated by `sprint-setup`.
Key sections:

```toml
[project]
name = "your-project"
repo = "owner/repo"
language = "rust"          # auto-detected

[ci]
check_commands = ["cargo fmt --check", "cargo clippy", "cargo test"]
build_command = "cargo build --release"
```

See `references/skeletons/project.toml.tmpl` for the full template.

## How Personas Work

Each persona is a markdown file with these sections:

```markdown
# Name
## Role
## Voice
## Domain
## Background
## Review Focus
```

giles assigns stories to personas by domain match and uses their voice
for commits, PR descriptions, and code reviews.

## FAQ

**Q: giles didn't find my persona files.**
A: Persona files need at least 3 of these headings: `## Role`, `## Voice`,
`## Domain`, `## Background`, `## Review Focus`. Check your markdown formatting.

**Q: `gh` auth fails during setup.**
A: Run `gh auth status` to verify authentication. If needed: `gh auth login`.

**Q: Can I use giles with a monorepo?**
A: giles expects one `sprint-config/` per project root. For monorepos,
run setup from the subdirectory containing your `Cargo.toml`/`package.json`.

**Q: How do I re-run setup after changing my backlog?**
A: All scripts are idempotent. Run `/sprint-setup` again -- it skips
existing labels/milestones and only creates new issues.

**Q: How do I remove giles from my project?**
A: Run `/sprint-teardown`. It removes `sprint-config/` (symlinks only --
your original files are untouched) and optionally cleans up GitHub labels.

## License

MIT
~~~

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: rewrite README for marketplace onboarding"
```

### Task 16: Distribution hygiene

**Files:**
- Modify: `.gitignore`
- Review: `.claude-plugin/plugin.json`
- Review: `LICENSE`

- [ ] **Step 1: Update .gitignore**

Read current `.gitignore` and ensure these entries exist:

```
.DS_Store
sprint-config/
.pytest_cache/
__pycache__/
*.pyc
target/
.claude/worktrees/
```

- [ ] **Step 2: Verify plugin.json is marketplace-ready**

Read `.claude-plugin/plugin.json`. Verify:
- `name` matches repo name
- `version` is correct
- `repository` URL is correct
- `description` is clear
- `keywords` are relevant

- [ ] **Step 3: Verify LICENSE exists**

```bash
head -5 LICENSE
```

- [ ] **Step 4: Remove any .DS_Store files from tracking**

```bash
git rm --cached -r '*.DS_Store' 2>/dev/null || true
```

- [ ] **Step 5: Commit**

```bash
git add .gitignore
git commit -m "chore: update .gitignore for distribution hygiene"
```

### Task 17: Run all tests and tag release

**Files:** None (verification only)

- [ ] **Step 1: Run the complete test suite**

```bash
python scripts/test_lifecycle.py -v
python scripts/test_gh_interactions.py -v
python tests/test_hexwise_setup.py -v
python tests/test_golden_run.py -v
```

Expected: All tests pass.

- [ ] **Step 2: Verify SKILL.md line counts**

```bash
wc -l skills/*/SKILL.md
```

Expected: sprint-setup and sprint-run under 100 lines each. Sprint-monitor, sprint-release, and sprint-teardown may be larger (they're linear cookbooks where extraction would reduce clarity).

- [ ] **Step 3: Bump version in plugin.json**

Update version from `0.3.0` to `0.4.0` (minor bump for new test infrastructure + refactored docs).

- [ ] **Step 4: Commit and tag**

```bash
git add .claude-plugin/plugin.json
git commit -m "release: bump to v0.4.0 — shippable state"
git tag v0.4.0
```

- [ ] **Step 5: Verify tag**

```bash
git log --oneline -5
git tag -l 'v0.*'
```

Expected: v0.4.0 tag on latest commit.
