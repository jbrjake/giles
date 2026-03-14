#!/usr/bin/env python3
"""Tests for sprint_analytics.py.

Uses FakeGitHub for mocked subprocess calls. Tests metric computation
and report formatting without real GitHub API calls.

Run: python -m unittest tests.test_sprint_analytics -v
"""
from __future__ import annotations

import json
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


class TestComputeReviewRounds(unittest.TestCase):
    """Test review round computation."""

    def setUp(self):
        self.gh = FakeGitHub()
        self.patched = make_patched_subprocess(self.gh)

    def test_counts_review_events(self):
        """Each CHANGES_REQUESTED or APPROVED counts as a round."""
        self.gh.prs.append({
            "number": 1,
            "title": "US-0101: Parse hex",
            "state": "closed",
            "labels": [],
            "milestone": {"title": "Sprint 1"},
            "reviews": [
                {"state": "CHANGES_REQUESTED"},
                {"state": "APPROVED"},
            ],
        })
        self.gh.prs.append({
            "number": 2,
            "title": "US-0102: Parse RGB",
            "state": "closed",
            "labels": [],
            "milestone": {"title": "Sprint 1"},
            "reviews": [
                {"state": "APPROVED"},
            ],
        })

        with patch("subprocess.run", self.patched):
            result = sprint_analytics.compute_review_rounds("Sprint 1")

        self.assertEqual(result["avg_rounds"], 1.5)
        self.assertEqual(result["max_rounds"], 2)
        self.assertIn("US-0101", result["max_story"])
        self.assertEqual(result["pr_count"], 2)

    def test_no_prs(self):
        """Handles empty PR list gracefully."""
        with patch("subprocess.run", self.patched):
            result = sprint_analytics.compute_review_rounds("Sprint 1")
        self.assertEqual(result["avg_rounds"], 0.0)
        self.assertEqual(result["pr_count"], 0)


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


if __name__ == "__main__":
    unittest.main()
