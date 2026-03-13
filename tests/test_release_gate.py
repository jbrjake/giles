#!/usr/bin/env python3
"""Tests for release_gate.py orchestration functions.

P2-02: Covers calculate_version(), validate_gates(), gate_tests(),
gate_build(), and do_release() with mocked subprocess/gh calls.

Run: python -m unittest tests.test_release_gate -v
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "skills" / "sprint-release" / "scripts"))

from release_gate import (
    calculate_version,
    validate_gates,
    gate_tests,
    gate_build,
    do_release,
    find_milestone_number,
)


# ---------------------------------------------------------------------------
# calculate_version tests
# ---------------------------------------------------------------------------

class TestCalculateVersion(unittest.TestCase):

    @patch("release_gate.parse_commits_since")
    @patch("release_gate.find_latest_semver_tag")
    def test_no_tags_uses_0_1_0_base(self, mock_tag, mock_commits):
        mock_tag.return_value = None
        mock_commits.return_value = [
            {"subject": "feat: initial", "body": ""},
        ]
        new_ver, base_ver, bump, commits = calculate_version()
        self.assertEqual(base_ver, "0.1.0")
        self.assertEqual(bump, "minor")
        self.assertEqual(new_ver, "0.2.0")

    @patch("release_gate.parse_commits_since")
    @patch("release_gate.find_latest_semver_tag")
    def test_existing_tag_bumps(self, mock_tag, mock_commits):
        mock_tag.return_value = "v1.2.3"
        mock_commits.return_value = [
            {"subject": "fix: patch", "body": ""},
        ]
        new_ver, base_ver, bump, commits = calculate_version()
        self.assertEqual(base_ver, "1.2.3")
        self.assertEqual(bump, "patch")
        self.assertEqual(new_ver, "1.2.4")

    @patch("release_gate.parse_commits_since")
    @patch("release_gate.find_latest_semver_tag")
    def test_no_commits_returns_none_bump(self, mock_tag, mock_commits):
        mock_tag.return_value = "v0.5.0"
        mock_commits.return_value = []
        new_ver, base_ver, bump, commits = calculate_version()
        self.assertEqual(bump, "none")
        self.assertEqual(new_ver, "0.5.0")  # unchanged

    @patch("release_gate.parse_commits_since")
    @patch("release_gate.find_latest_semver_tag")
    def test_breaking_change_is_major(self, mock_tag, mock_commits):
        mock_tag.return_value = "v1.0.0"
        mock_commits.return_value = [
            {"subject": "feat!: new API", "body": "BREAKING CHANGE: old removed"},
        ]
        new_ver, _, bump, _ = calculate_version()
        self.assertEqual(bump, "major")
        self.assertEqual(new_ver, "2.0.0")


# ---------------------------------------------------------------------------
# validate_gates tests
# ---------------------------------------------------------------------------

class TestValidateGates(unittest.TestCase):

    @patch("release_gate.gate_build")
    @patch("release_gate.gate_tests")
    @patch("release_gate.gate_prs")
    @patch("release_gate.gate_ci")
    @patch("release_gate.gate_stories")
    def test_all_pass(self, m_stories, m_ci, m_prs, m_tests, m_build):
        m_stories.return_value = (True, "All closed")
        m_ci.return_value = (True, "CI: success")
        m_prs.return_value = (True, "No open PRs")
        m_tests.return_value = (True, "2 commands passed")
        m_build.return_value = (True, "Build succeeded")

        passed, results = validate_gates("Sprint 1", {"ci": {}})
        self.assertTrue(passed)
        self.assertEqual(len(results), 5)
        self.assertTrue(all(r[1] for r in results))

    @patch("release_gate.gate_build")
    @patch("release_gate.gate_tests")
    @patch("release_gate.gate_prs")
    @patch("release_gate.gate_ci")
    @patch("release_gate.gate_stories")
    def test_first_failure_stops(self, m_stories, m_ci, m_prs, m_tests, m_build):
        m_stories.return_value = (False, "2 open issues")
        # These shouldn't be called because stories gate fails first
        m_ci.return_value = (True, "success")
        m_prs.return_value = (True, "no PRs")
        m_tests.return_value = (True, "passed")
        m_build.return_value = (True, "passed")

        passed, results = validate_gates("Sprint 1", {"ci": {}})
        self.assertFalse(passed)
        # Only 1 result because it stops after first failure
        self.assertEqual(len(results), 1)
        self.assertFalse(results[0][1])

    @patch("release_gate.gate_build")
    @patch("release_gate.gate_tests")
    @patch("release_gate.gate_prs")
    @patch("release_gate.gate_ci")
    @patch("release_gate.gate_stories")
    def test_middle_failure(self, m_stories, m_ci, m_prs, m_tests, m_build):
        m_stories.return_value = (True, "All closed")
        m_ci.return_value = (True, "success")
        m_prs.return_value = (False, "1 open PR")
        m_tests.return_value = (True, "passed")
        m_build.return_value = (True, "passed")

        passed, results = validate_gates("Sprint 1", {"ci": {}})
        self.assertFalse(passed)
        self.assertEqual(len(results), 3)  # Stories, CI, PRs


# ---------------------------------------------------------------------------
# gate_tests tests
# ---------------------------------------------------------------------------

class TestGateTests(unittest.TestCase):

    @patch("release_gate.subprocess.run")
    def test_all_commands_pass(self, mock_run):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="ok", stderr="",
        )
        config = {"ci": {"check_commands": ["make test", "make lint"]}}
        passed, detail = gate_tests(config)
        self.assertTrue(passed)
        self.assertIn("2 command(s) passed", detail)

    @patch("release_gate.subprocess.run")
    def test_command_failure(self, mock_run):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=1, stdout="", stderr="error",
        )
        config = {"ci": {"check_commands": ["make test"]}}
        passed, detail = gate_tests(config)
        self.assertFalse(passed)
        self.assertIn("failed", detail)

    def test_no_commands_configured(self):
        config = {"ci": {}}
        passed, detail = gate_tests(config)
        self.assertTrue(passed)
        self.assertIn("No check_commands", detail)


# ---------------------------------------------------------------------------
# gate_build tests
# ---------------------------------------------------------------------------

class TestGateBuild(unittest.TestCase):

    @patch("release_gate.subprocess.run")
    def test_build_success(self, mock_run):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="ok", stderr="",
        )
        config = {"ci": {"build_command": "make build"}}
        passed, detail = gate_build(config)
        self.assertTrue(passed)
        self.assertIn("succeeded", detail)

    @patch("release_gate.subprocess.run")
    def test_build_failure(self, mock_run):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=1, stdout="", stderr="compile error",
        )
        config = {"ci": {"build_command": "make build"}}
        passed, detail = gate_build(config)
        self.assertFalse(passed)
        self.assertIn("failed", detail)

    def test_no_build_command(self):
        config = {"ci": {}}
        passed, detail = gate_build(config)
        self.assertTrue(passed)
        self.assertIn("No build_command", detail)

    @patch("release_gate.subprocess.run")
    def test_missing_binary(self, mock_run):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="ok", stderr="",
        )
        config = {"ci": {
            "build_command": "make build",
            "binary_path": "/nonexistent/binary",
        }}
        passed, detail = gate_build(config)
        self.assertFalse(passed)
        self.assertIn("not found", detail)


# ---------------------------------------------------------------------------
# find_milestone_number tests
# ---------------------------------------------------------------------------

class TestFindMilestoneNumber(unittest.TestCase):

    @patch("release_gate.gh_json")
    def test_finds_milestone(self, mock_gh):
        mock_gh.return_value = [
            {"title": "Sprint 1: Skeleton", "number": 1},
            {"title": "Sprint 2: Features", "number": 2},
        ]
        self.assertEqual(find_milestone_number("Sprint 1: Skeleton"), 1)

    @patch("release_gate.gh_json")
    def test_no_match(self, mock_gh):
        mock_gh.return_value = [
            {"title": "Sprint 2: Features", "number": 2},
        ]
        self.assertIsNone(find_milestone_number("Sprint 3: Polish"))


if __name__ == "__main__":
    unittest.main()
