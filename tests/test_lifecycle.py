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
from mock_project import MockProject

sys.path.insert(0, str(ROOT / "skills" / "sprint-release" / "scripts"))
from release_gate import (
    determine_bump, bump_version, write_version_to_toml,
    generate_release_notes,
)

sys.path.insert(0, str(ROOT / "skills" / "sprint-setup" / "scripts"))
import bootstrap_github
import populate_issues

sys.path.insert(0, str(ROOT / "skills" / "sprint-run" / "scripts"))
import sync_tracking
import update_burndown

sys.path.insert(0, str(ROOT / "skills" / "sprint-monitor" / "scripts"))
import check_status


# ---------------------------------------------------------------------------
# Lifecycle tests
# ---------------------------------------------------------------------------

class TestLifecycle(unittest.TestCase):
    """End-to-end lifecycle tests with FakeGitHub."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="giles-lifecycle-")
        self.root = Path(self.tmpdir)
        self.mock = MockProject(self.root, real_git=True)
        self.mock.create()
        self.fake_gh = FakeGitHub()
        self._saved_cwd = os.getcwd()
        os.chdir(self.root)
        self.addCleanup(os.chdir, self._saved_cwd)

    def tearDown(self):
        # BH-011: Verify FakeGitHub didn't silently ignore any flags
        if hasattr(self, 'fake_gh') and self.fake_gh._strict_warnings:
            print(f"FakeGitHub strict warnings: {self.fake_gh._strict_warnings}",
                  file=sys.stderr)
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

        self.assertEqual(len(self.fake_gh.milestones), 1)
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
        self.assertEqual(len(stories), 2)

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

        self.assertEqual(len(self.fake_gh.issues), 2)
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

    # -- Test 09b: release notes compare link with real prior tag -------------

    def test_09b_release_notes_compare_link(self):
        """P6-19: compare link is generated when prior tag exists in git."""
        # Create a real v0.1.0 tag in the temp repo
        subprocess.run(
            ["git", "-c", "user.name=Test", "-c", "user.email=test@test.com",
             "tag", "v0.1.0"],
            cwd=str(self.root), capture_output=True, text=True, check=True,
        )

        commits = [
            {"subject": "feat: add dashboard", "body": ""},
        ]
        config = {"project": {"repo": "testowner/testrepo"}}
        notes = generate_release_notes(
            "0.2.0", "0.1.0", commits,
            "Sprint 2: Features", config,
        )
        expected_link = "https://github.com/testowner/testrepo/compare/v0.1.0...v0.2.0"
        self.assertIn(expected_link, notes,
                      "Compare link should appear when prior tag exists")
        # Should NOT contain "initial release" text
        self.assertNotIn("initial release", notes)

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

    # Tests 11 (extract_sp) and 12 (commit validation) removed —
    # comprehensive versions live in test_gh_interactions.py:
    #   TestExtractSP (10 cases) and TestValidateMessage (9 cases).

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
            bootstrap_github.create_static_labels()
            bootstrap_github.create_persona_labels(config)
            bootstrap_github.create_milestones_on_github(config)

            from gh_test_helpers import populate_test_issues
            populate_test_issues(self.fake_gh, config, populate_issues)

        # Verify the pipeline produced expected counts
        self.assertGreaterEqual(len(self.fake_gh.labels), 15,
                                "Labels: static + persona + sprint + saga + kanban")
        self.assertEqual(len(self.fake_gh.milestones), 1,
                         "Exactly 1 milestone from milestone-1.md")
        self.assertEqual(len(self.fake_gh.issues), 2,
                         "Exactly 2 issues from 2 stories in milestone-1.md")


    # -- Test 14: monitoring pipeline (sync → burndown → check) ---------------

    def test_14_monitoring_pipeline(self):
        """P6-08: sync_tracking → update_burndown → check_status pipeline."""
        from datetime import datetime, timezone

        config = self._generate_config()
        sprints_dir = self.root / "sprints"
        sprints_dir.mkdir(exist_ok=True)

        # SPRINT-STATUS.md so detect_sprint() can find the current sprint
        (sprints_dir / "SPRINT-STATUS.md").write_text(
            "# Sprint Status\n\nCurrent Sprint: 1\n\n## Active Stories\n",
            encoding="utf-8",
        )

        # Set up FakeGitHub state: one milestone, four issues
        ms_title = "Sprint 1: Foundation"
        self.fake_gh.milestones = [{
            "number": 1,
            "title": ms_title,
            "state": "open",
            "open_issues": 2,
            "closed_issues": 2,
        }]

        now_iso = datetime.now(timezone.utc).isoformat()
        self.fake_gh.issues = [
            {
                "number": 1,
                "title": "US-0101: Basic setup",
                "body": "| Story Points | 3 |",
                "state": "closed",
                "labels": [{"name": "kanban:done"}, {"name": "sp:3"}],
                "milestone": {"title": ms_title},
                "closedAt": now_iso,
            },
            {
                "number": 2,
                "title": "US-0102: Core feature",
                "body": "",
                "state": "closed",
                "labels": [{"name": "kanban:done"}, {"name": "sp:5"}],
                "milestone": {"title": ms_title},
                "closedAt": now_iso,
            },
            {
                "number": 3,
                "title": "US-0103: API endpoint",
                "body": "",
                "state": "open",
                "labels": [{"name": "kanban:dev"}, {"name": "sp:3"}],
                "milestone": {"title": ms_title},
                "closedAt": None,
            },
            {
                "number": 4,
                "title": "US-0104: Documentation",
                "body": "",
                "state": "open",
                "labels": [{"name": "kanban:todo"}, {"name": "sp:2"}],
                "milestone": {"title": ms_title},
                "closedAt": None,
            },
        ]

        stories_dir = sprints_dir / "sprint-1" / "stories"
        stories_dir.mkdir(parents=True, exist_ok=True)

        with patch("subprocess.run", make_patched_subprocess(self.fake_gh)):
            # --- Phase 1: sync_tracking creates tracking files ---------------
            for issue in self.fake_gh.issues:
                tf, changes = sync_tracking.create_from_issue(
                    issue, sprint=1, d=stories_dir, pr=None,
                )
                sync_tracking.write_tf(tf)

            tracking_files = list(stories_dir.glob("*.md"))
            self.assertEqual(
                len(tracking_files), 4,
                f"Expected 4 tracking files, got {len(tracking_files)}",
            )

            # --- Phase 2: update_burndown reads tracking + writes burndown ---
            issues = self.fake_gh.issues
            now = datetime.now(timezone.utc)
            rows = update_burndown.build_rows(issues)

            bd_path = update_burndown.write_burndown(1, rows, now, sprints_dir)
            update_burndown.update_sprint_status(1, rows, sprints_dir)

            self.assertTrue(bd_path.exists(), "Burndown file should exist")
            bd_text = bd_path.read_text(encoding="utf-8")
            self.assertIn("Sprint 1 Burndown", bd_text)
            # 8 done SP out of 13 total
            self.assertIn("Completed: 8 SP", bd_text)
            self.assertIn("Remaining: 5 SP", bd_text)

            status_text = (sprints_dir / "SPRINT-STATUS.md").read_text(
                encoding="utf-8",
            )
            self.assertIn("Active Stories", status_text)
            self.assertIn("US-0101", status_text)

            # --- Phase 3: check_milestone reports progress -------------------
            report, actions = check_status.check_milestone(1)

            report_text = "\n".join(report)
            # 2 closed out of 4 total stories
            self.assertIn("2/4", report_text)
            self.assertIn("50%", report_text)
            # SP counts: 8 done out of 13
            self.assertIn("8/13 SP", report_text)


if __name__ == "__main__":
    unittest.main()
