#!/usr/bin/env python3
"""Tests for sprint_analytics.py.

Uses FakeGitHub for mocked subprocess calls. Tests metric computation
and report formatting without real GitHub API calls.

Run: python -m unittest tests.test_sprint_analytics -v
"""
from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))

import sprint_analytics
from fake_github import FakeGitHub, make_patched_subprocess


class TestExtractPersona(unittest.TestCase):
    """Test persona extraction from issue labels."""

    def test_persona_from_label(self):
        issue = {"labels": [{"name": "persona:rusti"}, {"name": "sprint:1"}]}
        self.assertEqual(sprint_analytics.extract_persona(issue), "rusti")

    def test_no_persona(self):
        issue = {"labels": [{"name": "sprint:1"}]}
        self.assertIsNone(sprint_analytics.extract_persona(issue))


class TestComputeVelocity(unittest.TestCase):
    """Test velocity computation with mocked GitHub."""

    def setUp(self):
        self.gh = FakeGitHub()
        self.patched = make_patched_subprocess(self.gh)

    def test_all_closed(self):
        """Velocity 100% when all issues are closed."""
        # Create milestone
        self.gh.milestones.append({
            "number": 1, "title": "Sprint 1: First Light",
            "state": "open", "open_issues": 0, "closed_issues": 3,
        })
        # Create closed issues with SP labels
        for i, sp in enumerate([3, 5, 3], start=1):
            self.gh.issues.append({
                "number": i,
                "title": f"US-010{i}: Story {i}",
                "state": "closed",
                "labels": [{"name": f"sp:{sp}"}],
                "body": "",
                "milestone": {"title": "Sprint 1: First Light"},
            })

        with patch("subprocess.run", self.patched):
            result = sprint_analytics.compute_velocity("Sprint 1: First Light")

        self.assertEqual(result["planned_sp"], 11)
        self.assertEqual(result["delivered_sp"], 11)
        self.assertEqual(result["percentage"], 100)
        self.assertEqual(result["story_count"], 3)

    def test_partial_delivery(self):
        """Velocity reflects partial delivery."""
        self.gh.issues.append({
            "number": 1, "title": "US-0101", "state": "closed",
            "labels": [{"name": "sp:5"}], "body": "",
            "milestone": {"title": "Sprint 1"},
        })
        self.gh.issues.append({
            "number": 2, "title": "US-0102", "state": "open",
            "labels": [{"name": "sp:3"}], "body": "",
            "milestone": {"title": "Sprint 1"},
        })

        with patch("subprocess.run", self.patched):
            result = sprint_analytics.compute_velocity("Sprint 1")

        self.assertEqual(result["planned_sp"], 8)
        self.assertEqual(result["delivered_sp"], 5)
        self.assertEqual(result["percentage"], 62)

    def test_malformed_sp_labels_contribute_zero(self):
        """Issues with malformed SP labels (sp:abc, sp:) contribute 0 SP.

        Note: sp:3.5 extracts the leading integer (3) via regex, which
        is intentional — extract_sp uses r"sp:(\\d+)" and picks up the
        integer prefix. Truly non-numeric labels contribute 0.
        """
        for i, bad_label in enumerate(["sp:abc", "sp:"], start=1):
            self.gh.issues.append({
                "number": i, "title": f"US-010{i}", "state": "closed",
                "labels": [{"name": bad_label}], "body": "",
                "milestone": {"title": "Sprint 1"},
            })
        # sp:3.5 extracts 3 (leading digits)
        self.gh.issues.append({
            "number": 3, "title": "US-0103", "state": "closed",
            "labels": [{"name": "sp:3.5"}], "body": "",
            "milestone": {"title": "Sprint 1"},
        })
        # One valid issue
        self.gh.issues.append({
            "number": 4, "title": "US-0104", "state": "closed",
            "labels": [{"name": "sp:5"}], "body": "",
            "milestone": {"title": "Sprint 1"},
        })

        with patch("subprocess.run", self.patched):
            result = sprint_analytics.compute_velocity("Sprint 1")

        # sp:abc and sp: yield 0; sp:3.5 yields 3; sp:5 yields 5 => total 8
        self.assertEqual(result["planned_sp"], 8)
        self.assertEqual(result["delivered_sp"], 8)
        self.assertEqual(result["story_count"], 4)


class TestComputeReviewRounds(unittest.TestCase):
    """Test review round computation."""

    def setUp(self):
        self.gh = FakeGitHub()
        self.patched = make_patched_subprocess(self.gh)

    def test_counts_review_events(self):
        """Each CHANGES_REQUESTED or APPROVED counts as a round.

        BH-002: Includes a PR from a *different* milestone to verify
        the post-fetch filter (line 97: ms.get('title') == milestone_title)
        actually excludes non-matching PRs.

        BH-006: Creates PRs via _pr_create and adds reviews via _pr_review
        so the test exercises the real review accumulation path, instead of
        injecting a 'reviews' key directly into the PR dict.
        """
        with patch("subprocess.run", self.patched):
            # Create PR #1 for Sprint 1 via gh pr create
            subprocess.run([
                "gh", "pr", "create",
                "--title", "US-0101: Parse hex",
                "--base", "main", "--head", "feat/hex",
                "--milestone", "Sprint 1",
            ])
            # Add reviews via gh pr review (exercises _pr_review path)
            subprocess.run([
                "gh", "pr", "review", "1", "--request-changes",
                "--body", "needs error handling",
            ])
            subprocess.run([
                "gh", "pr", "review", "1", "--approve",
                "--body", "looks good now",
            ])

            # Create PR #2 for Sprint 1
            subprocess.run([
                "gh", "pr", "create",
                "--title", "US-0102: Parse RGB",
                "--base", "main", "--head", "feat/rgb",
                "--milestone", "Sprint 1",
            ])
            subprocess.run([
                "gh", "pr", "review", "2", "--approve",
                "--body", "ship it",
            ])

            # BH-002: Create PR #3 for a DIFFERENT milestone.
            # This must be excluded by the post-fetch milestone filter.
            subprocess.run([
                "gh", "pr", "create",
                "--title", "US-0201: Gradient support",
                "--base", "main", "--head", "feat/gradient",
                "--milestone", "Sprint 2",
            ])
            subprocess.run([
                "gh", "pr", "review", "3", "--request-changes",
                "--body", "wrong approach",
            ])
            subprocess.run([
                "gh", "pr", "review", "3", "--request-changes",
                "--body", "still wrong",
            ])
            subprocess.run([
                "gh", "pr", "review", "3", "--approve",
                "--body", "ok fine",
            ])

            # Set all PRs to state "closed" so --state all returns them
            for pr in self.gh.prs:
                pr["state"] = "closed"

            result = sprint_analytics.compute_review_rounds("Sprint 1")

        # Only Sprint 1 PRs should be counted (PR #1: 2 rounds, PR #2: 1 round)
        self.assertEqual(result["pr_count"], 2)
        self.assertEqual(result["avg_rounds"], 1.5)
        self.assertEqual(result["max_rounds"], 2)
        self.assertIn("US-0101", result["max_story"])

    def test_no_prs(self):
        """Handles empty PR list gracefully."""
        with patch("subprocess.run", self.patched):
            result = sprint_analytics.compute_review_rounds("Sprint 1")
        self.assertEqual(result["avg_rounds"], 0.0)
        self.assertEqual(result["pr_count"], 0)

    def test_all_zero_rounds_max_story_is_none(self):
        """BH-P11-108: When all PRs have 0 rounds, max_story should be 'none'."""
        with patch("subprocess.run", self.patched):
            # Create PRs with no reviews
            subprocess.run([
                "gh", "pr", "create",
                "--title", "US-0101: No reviews",
                "--base", "main", "--head", "feat/a",
                "--milestone", "Sprint 1",
            ])
            subprocess.run([
                "gh", "pr", "create",
                "--title", "US-0102: Also no reviews",
                "--base", "main", "--head", "feat/b",
                "--milestone", "Sprint 1",
            ])
            for pr in self.gh.prs:
                pr["state"] = "closed"

            result = sprint_analytics.compute_review_rounds("Sprint 1")

        self.assertEqual(result["max_rounds"], 0)
        self.assertEqual(result["max_story"], "none",
                         "max_story should be 'none' when no PR has any reviews")


class TestComputeWorkload(unittest.TestCase):
    """Test workload distribution computation."""

    def setUp(self):
        self.gh = FakeGitHub()
        self.patched = make_patched_subprocess(self.gh)

    def test_counts_per_persona(self):
        self.gh.issues.extend([
            {"number": 1, "labels": [{"name": "persona:rusti"}],
             "milestone": {"title": "Sprint 1"}, "state": "closed"},
            {"number": 2, "labels": [{"name": "persona:rusti"}],
             "milestone": {"title": "Sprint 1"}, "state": "closed"},
            {"number": 3, "labels": [{"name": "persona:palette"}],
             "milestone": {"title": "Sprint 1"}, "state": "closed"},
        ])

        with patch("subprocess.run", self.patched):
            result = sprint_analytics.compute_workload("Sprint 1")

        self.assertEqual(result["rusti"], 2)
        self.assertEqual(result["palette"], 1)

    def test_no_persona_labels(self):
        self.gh.issues.append({
            "number": 1, "labels": [{"name": "sprint:1"}],
            "milestone": {"title": "Sprint 1"}, "state": "closed",
        })

        with patch("subprocess.run", self.patched):
            result = sprint_analytics.compute_workload("Sprint 1")

        self.assertEqual(result, {})


class TestFormatReport(unittest.TestCase):
    """Test markdown report formatting."""

    def test_produces_valid_markdown(self):
        velocity = {
            "planned_sp": 16, "delivered_sp": 16, "percentage": 100,
            "story_count": 4, "delivered_count": 4,
        }
        review = {
            "avg_rounds": 1.5, "max_rounds": 2,
            "max_story": "US-0101: Parse hex", "pr_count": 4,
        }
        workload = {"rusti": 3, "palette": 1}

        report = sprint_analytics.format_report(
            1, "First Light", velocity, review, workload,
        )

        self.assertIn("### Sprint 1 — First Light", report)
        self.assertIn("16/16 SP (100%)", report)
        self.assertIn("avg 1.5 per story", report)
        self.assertIn("rusti: 3", report)
        self.assertIn("palette: 1", report)
        self.assertIn("Giles notes:", report)

    def test_no_pr_data(self):
        velocity = {
            "planned_sp": 0, "delivered_sp": 0, "percentage": 0,
            "story_count": 0, "delivered_count": 0,
        }
        review = {
            "avg_rounds": 0.0, "max_rounds": 0,
            "max_story": "", "pr_count": 0,
        }
        report = sprint_analytics.format_report(1, "Empty", velocity, review, {})
        self.assertIn("no PR data available", report)
        self.assertIn("no persona data available", report)


class TestMainIntegration(unittest.TestCase):
    """BH-019: Integration test for sprint_analytics.main().

    Patches sys.argv, load_config, find_milestone, and subprocess.run
    (via FakeGitHub) to verify end-to-end behavior: config loading,
    milestone lookup, metric computation, report output, and file write.
    """

    def setUp(self):
        self.gh = FakeGitHub()
        self.patched = make_patched_subprocess(self.gh)
        self._tmpdir = tempfile.TemporaryDirectory()
        self.tmpdir = self._tmpdir.name
        self._orig_cwd = os.getcwd()
        os.chdir(self.tmpdir)

        # Create sprints dir with a sprint-1 subdirectory and kickoff file
        self.sprints_dir = Path(self.tmpdir) / "sprints"
        sprint_dir = self.sprints_dir / "sprint-1"
        sprint_dir.mkdir(parents=True)
        (sprint_dir / "kickoff.md").write_text(
            "# Sprint 1 Kickoff\n\nSprint Theme: First Light\n",
            encoding="utf-8",
        )

        # Populate GitHub state: milestone, issues, PRs
        self.gh.milestones.append({
            "number": 1, "title": "Sprint 1: First Light",
            "state": "open", "open_issues": 0, "closed_issues": 2,
        })
        for i, sp in enumerate([5, 3], start=1):
            self.gh.issues.append({
                "number": i,
                "title": f"US-010{i}: Story {i}",
                "state": "closed",
                "labels": [{"name": f"sp:{sp}"}, {"name": "persona:rusti"}],
                "body": "",
                "milestone": {"title": "Sprint 1: First Light"},
            })

    def tearDown(self):
        os.chdir(self._orig_cwd)
        self._tmpdir.cleanup()

    def _make_config(self):
        return {
            "project": {"name": "TestProj", "repo": "owner/repo"},
            "paths": {"sprints_dir": str(self.sprints_dir)},
            "ci": {"check_commands": [], "build_command": ""},
        }

    def test_main_with_explicit_sprint_number(self):
        """main() with explicit sprint number produces report and writes analytics file."""
        config = self._make_config()
        ms = {"number": 1, "title": "Sprint 1: First Light"}

        with (
            patch("subprocess.run", self.patched),
            patch("sprint_analytics.load_config", return_value=config),
            patch("sprint_analytics.find_milestone", return_value=ms),
            patch("sys.argv", ["sprint_analytics.py", "1"]),
            patch("sys.stdout", new_callable=io.StringIO) as mock_out,
        ):
            sprint_analytics.main()

        output = mock_out.getvalue()
        # Report should be printed to stdout
        self.assertIn("### Sprint 1", output)
        self.assertIn("First Light", output)
        self.assertIn("8/8 SP (100%)", output)
        self.assertIn("rusti: 2", output)

        # analytics.md should have been created and contain the report
        analytics_path = self.sprints_dir / "analytics.md"
        self.assertTrue(analytics_path.exists())
        analytics_text = analytics_path.read_text(encoding="utf-8")
        self.assertIn("### Sprint 1", analytics_text)
        self.assertIn("Appended", output)

    def test_main_no_milestone_exits(self):
        """main() exits with code 1 when no milestone matches."""
        config = self._make_config()

        with (
            patch("subprocess.run", self.patched),
            patch("sprint_analytics.load_config", return_value=config),
            patch("sprint_analytics.find_milestone", return_value=None),
            patch("sys.argv", ["sprint_analytics.py", "99"]),
        ):
            with self.assertRaises(SystemExit) as cm:
                sprint_analytics.main()
            self.assertEqual(cm.exception.code, 1)

    def test_main_deduplicates_analytics_entry(self):
        """main() does not append duplicate sprint entries to analytics.md."""
        config = self._make_config()
        ms = {"number": 1, "title": "Sprint 1: First Light"}

        # Pre-create analytics.md with an existing Sprint 1 entry
        self.sprints_dir.mkdir(exist_ok=True)
        (self.sprints_dir / "analytics.md").write_text(
            "# Sprint Analytics\n\n---\n\n### Sprint 1 — First Light\n"
            "**Velocity:** 8/8 SP (100%)\n\n---\n\n",
            encoding="utf-8",
        )

        with (
            patch("subprocess.run", self.patched),
            patch("sprint_analytics.load_config", return_value=config),
            patch("sprint_analytics.find_milestone", return_value=ms),
            patch("sys.argv", ["sprint_analytics.py", "1"]),
            patch("sys.stdout", new_callable=io.StringIO) as mock_out,
        ):
            sprint_analytics.main()

        output = mock_out.getvalue()
        self.assertIn("skipping", output)

        # File should NOT have duplicate entries
        text = (self.sprints_dir / "analytics.md").read_text(encoding="utf-8")
        count = text.count("### Sprint 1")
        self.assertEqual(count, 1, "Should not duplicate Sprint 1 entry")


if __name__ == "__main__":
    unittest.main()
