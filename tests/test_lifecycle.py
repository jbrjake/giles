#!/usr/bin/env python3
"""Lifecycle integration test with FakeGitHub.

End-to-end test: sprint_init -> bootstrap_github -> populate_issues ->
version calculation. FakeGitHub intercepts gh CLI calls via subprocess
patching. Real git operations run against a temp repo.

Run: python -m unittest tests.test_lifecycle -v
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))

from validate_config import parse_simple_toml, validate_project
from sprint_init import ProjectScanner, ConfigGenerator
from commit import validate_message, check_atomicity
from fake_github import FakeGitHub, make_patched_subprocess

sys.path.insert(0, str(ROOT / "skills" / "sprint-release" / "scripts"))
from release_gate import (
    determine_bump, bump_version, write_version_to_toml,
    generate_release_notes,
)

sys.path.insert(0, str(ROOT / "skills" / "sprint-setup" / "scripts"))
import bootstrap_github
import populate_issues

sys.path.insert(0, str(ROOT / "skills" / "sprint-run" / "scripts"))
import update_burndown


# ---------------------------------------------------------------------------
# MockProject: create a temp Rust project for testing
# ---------------------------------------------------------------------------

class MockProject:
    """Create a minimal mock Rust project in a temp directory."""

    def __init__(self, root: Path):
        self.root = root

    def create(self) -> None:
        # Cargo.toml (language detection)
        (self.root / "Cargo.toml").write_text(textwrap.dedent("""\
            [package]
            name = "test-project"
            version = "0.1.0"
            edition = "2021"
        """))

        # Real git repo
        subprocess.run(
            ["git", "init"], cwd=str(self.root),
            capture_output=True, text=True,
        )
        subprocess.run(
            ["git", "remote", "add", "origin",
             "https://github.com/testowner/testrepo.git"],
            cwd=str(self.root), capture_output=True, text=True,
        )
        # Initial commit so git log doesn't fail
        subprocess.run(
            ["git", "add", "."], cwd=str(self.root),
            capture_output=True, text=True,
        )
        subprocess.run(
            ["git", "-c", "user.name=Test", "-c", "user.email=test@test.com",
             "commit", "-m", "feat: initial project setup"],
            cwd=str(self.root), capture_output=True, text=True,
        )

        # Persona files
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

        # Backlog with milestone
        backlog = self.root / "docs" / "backlog"
        backlog.mkdir(parents=True)
        milestones = backlog / "milestones"
        milestones.mkdir()
        (milestones / "milestone-1.md").write_text(textwrap.dedent("""\
            # Sprint 1: Walking Skeleton

            ### Sprint 1: Foundation

            | US-0101 | Basic setup | S01 | 3 | P0 |
            | US-0102 | Core feature | S01 | 5 | P1 |
        """))

        # Rules and dev guide
        (self.root / "RULES.md").write_text("# Rules\nNo panics in production.\n")
        (self.root / "DEVELOPMENT.md").write_text("# Development\nUse TDD.\n")

    def add_and_commit(self, msg: str) -> None:
        """Stage all and commit in the temp repo."""
        subprocess.run(
            ["git", "add", "-A"], cwd=str(self.root),
            capture_output=True, text=True,
        )
        subprocess.run(
            ["git", "-c", "user.name=Test", "-c", "user.email=test@test.com",
             "commit", "-m", msg, "--allow-empty"],
            cwd=str(self.root), capture_output=True, text=True,
        )


# ---------------------------------------------------------------------------
# Lifecycle tests
# ---------------------------------------------------------------------------

class TestLifecycle(unittest.TestCase):
    """End-to-end lifecycle tests with FakeGitHub."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="giles-lifecycle-")
        self.root = Path(self.tmpdir)
        self.mock = MockProject(self.root)
        self.mock.create()
        self.fake_gh = FakeGitHub()
        self._saved_cwd = os.getcwd()
        os.chdir(self.root)

    def tearDown(self):
        os.chdir(self._saved_cwd)
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _generate_config(self) -> dict:
        """Run sprint_init to generate sprint-config/."""
        scanner = ProjectScanner(self.root)
        scan = scanner.scan()
        gen = ConfigGenerator(scan)
        gen.generate()
        toml_path = self.root / "sprint-config" / "project.toml"
        return parse_simple_toml(toml_path.read_text())

    # -- Test 01: sprint_init generates valid config -------------------------

    def test_01_init_generates_valid_config(self):
        """sprint_init produces config that passes validation."""
        self._generate_config()
        config_dir = str(self.root / "sprint-config")
        ok, errors = validate_project(config_dir)
        self.assertTrue(ok, f"Validation failed: {errors}")

    # -- Test 02: config has expected TOML keys ------------------------------

    def test_02_config_has_required_keys(self):
        """Generated config has all required TOML sections and keys."""
        config = self._generate_config()
        self.assertIn("project", config)
        self.assertIn("paths", config)
        self.assertIn("ci", config)
        self.assertEqual(config["project"]["language"].lower(), "rust")
        self.assertIn("check_commands", config["ci"])
        self.assertIn("build_command", config["ci"])

    # -- Test 03: bootstrap creates labels -----------------------------------

    def test_03_bootstrap_creates_labels(self):
        """bootstrap_github.create_label creates labels in FakeGitHub."""
        with patch("subprocess.run", make_patched_subprocess(self.fake_gh)):
            bootstrap_github.create_label("kanban:todo", "cccccc", "Not started")
            bootstrap_github.create_label("saga:S01", "0e8a16", "Saga 1")

        self.assertIn("kanban:todo", self.fake_gh.labels)
        self.assertIn("saga:S01", self.fake_gh.labels)
        self.assertEqual(self.fake_gh.labels["kanban:todo"]["color"], "cccccc")

    # -- Test 04: bootstrap static labels ------------------------------------

    def test_04_static_labels_created(self):
        """create_static_labels creates priority, kanban, and type labels."""
        with patch("subprocess.run", make_patched_subprocess(self.fake_gh)):
            bootstrap_github.create_static_labels()

        expected = [
            "priority:P0", "priority:P1", "priority:P2",
            "kanban:todo", "kanban:done",
            "type:story", "type:bug",
        ]
        for label in expected:
            self.assertIn(label, self.fake_gh.labels, f"Missing: {label}")

    # -- Test 05: bootstrap milestones ---------------------------------------

    def test_05_milestones_created(self):
        """create_milestones_on_github creates milestones."""
        config = self._generate_config()
        with patch("subprocess.run", make_patched_subprocess(self.fake_gh)):
            bootstrap_github.create_milestones_on_github(config)

        self.assertGreater(len(self.fake_gh.milestones), 0)
        titles = [ms["title"] for ms in self.fake_gh.milestones]
        # Should contain something related to Sprint 1
        has_sprint_1 = any("Sprint 1" in t for t in titles)
        self.assertTrue(has_sprint_1, f"No Sprint 1 milestone in {titles}")

    # -- Test 06: populate issues creates stories ----------------------------

    def test_06_populate_creates_issues(self):
        """populate_issues creates GitHub issues from milestone files."""
        config = self._generate_config()
        from validate_config import get_milestones
        milestone_files = get_milestones(config)

        stories = populate_issues.parse_milestone_stories(milestone_files, config)
        self.assertGreater(len(stories), 0)

        # Fake existing issues: none
        with patch("subprocess.run", make_patched_subprocess(self.fake_gh)):
            existing = populate_issues.get_existing_issues()
            self.assertEqual(len(existing), 0)

            # Create milestones first so milestone_numbers can be resolved
            bootstrap_github.create_milestones_on_github(config)

            ms_numbers = {}
            for ms in self.fake_gh.milestones:
                ms_numbers[ms["title"]] = ms["number"]

            ms_titles = {}
            for i, mf in enumerate(milestone_files, 1):
                ms_titles[i] = self.fake_gh.milestones[i - 1]["title"] if i <= len(self.fake_gh.milestones) else f"Sprint {i}"

            for story in stories:
                populate_issues.create_issue(story, ms_numbers, ms_titles)

        self.assertGreater(len(self.fake_gh.issues), 0)
        issue_titles = [iss["title"] for iss in self.fake_gh.issues]
        self.assertTrue(
            any("US-0101" in t for t in issue_titles),
            f"US-0101 not found in {issue_titles}",
        )

    # -- Test 07: idempotent issue creation ----------------------------------

    def test_07_idempotent_issue_detection(self):
        """get_existing_issues returns story IDs from existing issues."""
        self.fake_gh.issues = [
            {"number": 1, "title": "US-0101: Setup", "state": "open",
             "labels": [], "body": "", "milestone": None, "closedAt": None},
            {"number": 2, "title": "US-0102: Feature", "state": "open",
             "labels": [], "body": "", "milestone": None, "closedAt": None},
        ]
        with patch("subprocess.run", make_patched_subprocess(self.fake_gh)):
            existing = populate_issues.get_existing_issues()
        self.assertIn("US-0101", existing)
        self.assertIn("US-0102", existing)

    # -- Test 08: version calculation ----------------------------------------

    def test_08_version_calculation(self):
        """determine_bump + bump_version produce correct semver."""
        # Add commits to temp repo
        self.mock.add_and_commit("feat: add authentication")
        self.mock.add_and_commit("fix: handle null pointer")

        commits = [
            {"subject": "feat: add authentication", "body": ""},
            {"subject": "fix: handle null pointer", "body": ""},
        ]
        bump = determine_bump(commits)
        self.assertEqual(bump, "minor")

        new_ver = bump_version("0.1.0", bump)
        self.assertEqual(new_ver, "0.2.0")

    # -- Test 09: release notes generation -----------------------------------

    def test_09_release_notes(self):
        """generate_release_notes produces structured markdown."""
        commits = [
            {"subject": "feat: add login flow", "body": ""},
            {"subject": "feat: add registration", "body": ""},
            {"subject": "fix: password hashing", "body": ""},
        ]
        config = {"project": {"repo": "testowner/testrepo"}}
        notes = generate_release_notes(
            "0.2.0", "0.1.0", commits,
            "Sprint 1: Walking Skeleton", config,
        )
        self.assertIn("v0.2.0", notes)
        self.assertIn("## Features", notes)
        self.assertIn("## Fixes", notes)
        self.assertIn("add login flow", notes)
        self.assertIn("## Full Changelog", notes)

    # -- Test 10: write version to TOML --------------------------------------

    def test_10_version_written_to_toml(self):
        """write_version_to_toml updates project.toml correctly."""
        config = self._generate_config()
        toml_path = self.root / "sprint-config" / "project.toml"
        write_version_to_toml("0.2.0", toml_path)

        text = toml_path.read_text()
        self.assertIn('version = "0.2.0"', text)
        # Original config should still be intact
        self.assertIn("[project]", text)

    # -- Test 11: extract_sp from issue data ---------------------------------

    def test_11_extract_sp(self):
        """update_burndown.extract_sp handles labels and body."""
        # From label
        issue_label = {
            "labels": [{"name": "sp:3"}],
            "body": "",
        }
        self.assertEqual(update_burndown.extract_sp(issue_label), 3)

        # From body
        issue_body = {
            "labels": [],
            "body": "| Story Points | 5 |",
        }
        self.assertEqual(update_burndown.extract_sp(issue_body), 5)

        # No SP
        issue_none = {"labels": [], "body": "No points"}
        self.assertEqual(update_burndown.extract_sp(issue_none), 0)

    # -- Test 12: commit message validation in lifecycle ---------------------

    def test_12_commit_validation(self):
        """Commit message validation works across all types."""
        # Valid messages
        for msg in ["feat: add login", "fix(parser): handle null",
                     "refactor!: rewrite core"]:
            ok, err = validate_message(msg)
            self.assertTrue(ok, f"'{msg}' should be valid: {err}")

        # Invalid messages
        for msg in ["", "not a commit", "feature: wrong type"]:
            ok, _ = validate_message(msg)
            self.assertFalse(ok, f"'{msg}' should be invalid")

    # -- Test 13: full init -> bootstrap -> issues pipeline ------------------

    def test_13_full_pipeline(self):
        """Full pipeline: init -> bootstrap labels -> create milestones -> create issues.

        Scope: MINIMAL SYNTHETIC project (MockProject — 2 personas, 1 milestone,
        2 stories). Exercises the pipeline with a bare-bones generated-from-scratch
        project to catch regressions in the basic happy path.

        Assertions are intentionally loose (>10 labels, >0 milestones, >0 issues)
        because the fixture is minimal and we only care that the pipeline completes.

        Complements (not duplicates):
        - test_hexwise_setup.test_full_setup_pipeline: same pipeline but runs
          against the rich hexwise fixture with exact count assertions.
        - test_golden_run.test_golden_full_setup_pipeline: same hexwise fixture
          but captures/replays golden snapshots at each phase boundary.
        """
        config = self._generate_config()

        with patch("subprocess.run", make_patched_subprocess(self.fake_gh)):
            # Bootstrap labels
            bootstrap_github.create_static_labels()
            bootstrap_github.create_persona_labels(config)

            # Create milestones
            bootstrap_github.create_milestones_on_github(config)

            # Populate issues
            from validate_config import get_milestones
            milestone_files = get_milestones(config)
            stories = populate_issues.parse_milestone_stories(
                milestone_files, config,
            )

            ms_numbers = {ms["title"]: ms["number"]
                          for ms in self.fake_gh.milestones}
            ms_titles = {}
            for i, mf in enumerate(milestone_files, 1):
                if i <= len(self.fake_gh.milestones):
                    ms_titles[i] = self.fake_gh.milestones[i - 1]["title"]
                else:
                    ms_titles[i] = f"Sprint {i}"

            for story in stories:
                if story.story_id not in populate_issues.get_existing_issues():
                    populate_issues.create_issue(story, ms_numbers, ms_titles)

        # Verify the pipeline produced expected counts
        self.assertGreaterEqual(len(self.fake_gh.labels), 15,
                                "Labels: static + persona + sprint + saga + kanban")
        self.assertGreaterEqual(len(self.fake_gh.milestones), 1,
                                "At least one milestone from sprint sections")
        self.assertGreaterEqual(len(self.fake_gh.issues), 1,
                                "At least one story issue created")


if __name__ == "__main__":
    unittest.main()
