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
sys.path.insert(0, str(ROOT / "tests"))

from release_gate import (
    calculate_version,
    validate_gates,
    gate_tests,
    gate_build,
    do_release,
    find_milestone_number,
)
from fake_github import FakeGitHub, make_patched_subprocess


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
    """Tests validate_gates() with FakeGitHub-backed gate functions.

    Instead of mocking each gate function, these tests set up real GitHub
    state (issues, PRs, CI runs) and let the actual gate_stories, gate_ci,
    gate_prs, gate_tests, and gate_build functions execute against it.
    gate_tests and gate_build still need subprocess mocking for local commands.
    """

    def setUp(self):
        self.fake = FakeGitHub()
        self.patcher = patch("subprocess.run", make_patched_subprocess(self.fake))
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()

    def _add_closed_milestone(self, title="Sprint 1"):
        """Add a milestone with all issues closed."""
        self.fake.milestones.append({
            "number": 1, "title": title,
            "open_issues": 0, "closed_issues": 3,
        })

    def test_all_pass(self):
        """All gates pass: no open issues, CI green, no open PRs."""
        self._add_closed_milestone()
        # CI: one successful run on main
        self.fake.runs.append({
            "name": "CI", "status": "completed",
            "conclusion": "success", "headBranch": "main",
        })
        # No open issues for milestone (empty = all closed)
        # No open PRs
        config = {
            "project": {"base_branch": "main"},
            "ci": {"check_commands": [], "build_command": ""},
        }
        passed, results = validate_gates("Sprint 1", config)
        self.assertTrue(passed)
        self.assertEqual(len(results), 5)
        self.assertTrue(all(r[1] for r in results))

    def test_first_failure_stops(self):
        """Stories gate fails (open issues) — later gates don't run."""
        self._add_closed_milestone()
        # Add open issues for the milestone
        self.fake.issues.append({
            "number": 1, "title": "US-0001: Unfinished",
            "state": "open", "labels": [],
            "body": "", "milestone": {"title": "Sprint 1"},
        })
        self.fake.issues.append({
            "number": 2, "title": "US-0002: Also unfinished",
            "state": "open", "labels": [],
            "body": "", "milestone": {"title": "Sprint 1"},
        })
        config = {
            "project": {"base_branch": "main"},
            "ci": {},
        }
        passed, results = validate_gates("Sprint 1", config)
        self.assertFalse(passed)
        self.assertEqual(len(results), 1)
        self.assertFalse(results[0][1])
        self.assertIn("2 open", results[0][2])

    def test_middle_failure_pr_gate(self):
        """Stories and CI pass, but PR gate fails (open PR for milestone)."""
        self._add_closed_milestone()
        # CI green
        self.fake.runs.append({
            "name": "CI", "status": "completed",
            "conclusion": "success", "headBranch": "main",
        })
        # Open PR targeting the milestone
        self.fake.prs.append({
            "number": 10, "title": "WIP: feature",
            "state": "open",
            "milestone": {"title": "Sprint 1"},
            "headRefName": "feat/wip",
        })
        config = {
            "project": {"base_branch": "main"},
            "ci": {"check_commands": [], "build_command": ""},
        }
        passed, results = validate_gates("Sprint 1", config)
        self.assertFalse(passed)
        self.assertEqual(len(results), 3)  # Stories, CI, PRs
        # Stories and CI passed
        self.assertTrue(results[0][1])
        self.assertTrue(results[1][1])
        # PRs failed
        self.assertFalse(results[2][1])
        self.assertIn("open PR", results[2][2])


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


# ---------------------------------------------------------------------------
# do_release tests
# ---------------------------------------------------------------------------

import os

# Minimal project.toml content sufficient for write_version_to_toml
_MINIMAL_TOML = """\
[project]
name = "TestProject"
repo = "owner/repo"
language = "python"

[paths]
team_dir = "sprint-config/team"
backlog_dir = "sprint-config/backlog"
sprints_dir = "sprints"

[ci]
check_commands = ["python -m pytest"]
build_command = "make build"
"""


def _make_subprocess_side_effect(*, tag_fails=False):
    """Build a side_effect function for subprocess.run.

    Returns CompletedProcess(returncode=0) for all commands except when
    tag_fails=True and the command is 'git tag'.
    """
    def _side_effect(cmd, **kwargs):
        # Detect 'git tag' invocations
        if isinstance(cmd, list) and len(cmd) >= 2 and cmd[0] == "git" and cmd[1] == "tag":
            if tag_fails:
                return subprocess.CompletedProcess(
                    args=cmd, returncode=1, stdout="", stderr="tag already exists",
                )
        return subprocess.CompletedProcess(
            args=cmd if isinstance(cmd, list) else [cmd],
            returncode=0, stdout="", stderr="",
        )
    return _side_effect


class TestDoRelease(unittest.TestCase):
    """Tests for do_release() — the full release orchestration flow."""

    def setUp(self):
        """Create a temp dir with sprint-config/project.toml and sprints/SPRINT-STATUS.md."""
        self._tmpdir = tempfile.TemporaryDirectory()
        self.tmpdir = self._tmpdir.name
        self._orig_cwd = os.getcwd()
        os.chdir(self.tmpdir)

        # Create sprint-config/project.toml
        sc_dir = Path(self.tmpdir) / "sprint-config"
        sc_dir.mkdir()
        (sc_dir / "project.toml").write_text(_MINIMAL_TOML, encoding="utf-8")

        # Create sprints/SPRINT-STATUS.md
        sprints_dir = Path(self.tmpdir) / "sprints"
        sprints_dir.mkdir()
        (sprints_dir / "SPRINT-STATUS.md").write_text(
            "| Sprint | Status | Date | Notes | Version |\n"
            "|--------|--------|------|-------|---------|\n",
            encoding="utf-8",
        )

    def tearDown(self):
        os.chdir(self._orig_cwd)
        self._tmpdir.cleanup()

    # -- Test 1: happy path ----------------------------------------------------

    @patch("release_gate.gh")
    @patch("release_gate.find_milestone_number")
    @patch("release_gate.subprocess.run")
    @patch("release_gate.write_version_to_toml")
    @patch("release_gate.calculate_version")
    def test_happy_path(self, mock_calc, mock_write_toml, mock_run, mock_ms, mock_gh):
        """All steps succeed: version written, tag pushed, release created, milestone closed."""
        mock_calc.return_value = ("1.1.0", "1.0.0", "minor", [
            {"subject": "feat: add dashboard", "body": ""},
            {"subject": "fix: login bug", "body": ""},
        ])
        mock_write_toml.return_value = None
        mock_run.side_effect = _make_subprocess_side_effect()
        mock_ms.return_value = 7
        mock_gh.return_value = "https://github.com/owner/repo/releases/tag/v1.1.0"

        config = {
            "project": {"name": "TestProject", "repo": "owner/repo"},
            "ci": {},
            "paths": {"sprints_dir": "sprints"},
        }
        result = do_release("Sprint 1: Walking Skeleton", config)

        self.assertTrue(result)

        # calculate_version called exactly once
        mock_calc.assert_called_once()

        # write_version_to_toml called with correct version
        mock_write_toml.assert_called_once()
        args = mock_write_toml.call_args
        self.assertEqual(args[0][0], "1.1.0")

        # subprocess.run called for: git status, git add, commit, git tag, git push
        self.assertEqual(mock_run.call_count, 5)
        run_cmds = [call[0][0] for call in mock_run.call_args_list]
        # git status (pre-flight)
        self.assertEqual(run_cmds[0][0], "git")
        self.assertEqual(run_cmds[0][1], "status")
        # git add
        self.assertEqual(run_cmds[1][0], "git")
        self.assertEqual(run_cmds[1][1], "add")
        # git tag
        self.assertEqual(run_cmds[3][0], "git")
        self.assertEqual(run_cmds[3][1], "tag")
        # git push
        self.assertEqual(run_cmds[4][0], "git")
        self.assertEqual(run_cmds[4][1], "push")

        # gh() called for: release create, milestone close, release view
        self.assertGreaterEqual(mock_gh.call_count, 2)
        gh_calls = [call[0][0] for call in mock_gh.call_args_list]
        # First gh call is release create
        self.assertEqual(gh_calls[0][0], "release")
        self.assertEqual(gh_calls[0][1], "create")
        # Second gh call is milestone close
        self.assertIn("milestones/7", gh_calls[1][1])

        # SPRINT-STATUS.md updated
        status = (Path(self.tmpdir) / "sprints" / "SPRINT-STATUS.md").read_text(
            encoding="utf-8",
        )
        self.assertIn("v1.1.0", status)
        self.assertIn("Released", status)

    # -- Test 2: no commits returns False --------------------------------------

    @patch("release_gate.gh")
    @patch("release_gate.find_milestone_number")
    @patch("release_gate.subprocess.run")
    @patch("release_gate.write_version_to_toml")
    @patch("release_gate.calculate_version")
    def test_no_commits_returns_false(
        self, mock_calc, mock_write_toml, mock_run, mock_ms, mock_gh,
    ):
        """When bump_type is 'none', do_release returns False immediately."""
        mock_calc.return_value = ("0.5.0", "0.5.0", "none", [])
        mock_run.side_effect = _make_subprocess_side_effect()

        config = {
            "project": {"name": "TestProject", "repo": "owner/repo"},
            "ci": {},
            "paths": {"sprints_dir": "sprints"},
        }
        result = do_release("Sprint 1: Walking Skeleton", config)

        self.assertFalse(result)
        mock_write_toml.assert_not_called()
        # Only pre-flight git status should have run
        self.assertEqual(mock_run.call_count, 1)
        mock_gh.assert_not_called()
        mock_ms.assert_not_called()

    # -- Test 3: tag failure returns False -------------------------------------

    @patch("release_gate.gh")
    @patch("release_gate.find_milestone_number")
    @patch("release_gate.subprocess.run")
    @patch("release_gate.write_version_to_toml")
    @patch("release_gate.calculate_version")
    def test_tag_failure_returns_false(
        self, mock_calc, mock_write_toml, mock_run, mock_ms, mock_gh,
    ):
        """When git tag fails, do_release returns False and no GH release is created."""
        mock_calc.return_value = ("2.0.0", "1.0.0", "major", [
            {"subject": "feat!: new API", "body": "BREAKING CHANGE: old removed"},
        ])
        mock_write_toml.return_value = None
        mock_run.side_effect = _make_subprocess_side_effect(tag_fails=True)

        config = {
            "project": {"name": "TestProject", "repo": "owner/repo"},
            "ci": {},
            "paths": {"sprints_dir": "sprints"},
        }
        result = do_release("Sprint 2: New API", config)

        self.assertFalse(result)

        # gh() should never be called — no release create, no milestone close
        mock_gh.assert_not_called()
        mock_ms.assert_not_called()

        # subprocess.run should have been called for git add, commit, and git tag (which failed)
        # but NOT for git push
        run_cmds = [call[0][0] for call in mock_run.call_args_list]
        push_calls = [c for c in run_cmds if isinstance(c, list) and "push" in c]
        self.assertEqual(len(push_calls), 0)

    # -- Test 4: dry run makes no mutations ------------------------------------

    @patch("release_gate.gh")
    @patch("release_gate.find_milestone_number")
    @patch("release_gate.subprocess.run")
    @patch("release_gate.write_version_to_toml")
    @patch("release_gate.calculate_version")
    def test_dry_run_no_mutations(
        self, mock_calc, mock_write_toml, mock_run, mock_ms, mock_gh,
    ):
        """With dry_run=True, only pre-flight git status runs. No mutations."""
        mock_calc.return_value = ("1.1.0", "1.0.0", "minor", [
            {"subject": "feat: add dashboard", "body": ""},
        ])
        mock_ms.return_value = 7
        mock_run.side_effect = _make_subprocess_side_effect()

        config = {
            "project": {"name": "TestProject", "repo": "owner/repo"},
            "ci": {},
            "paths": {"sprints_dir": "sprints"},
        }

        # Capture original SPRINT-STATUS.md content
        status_before = (
            Path(self.tmpdir) / "sprints" / "SPRINT-STATUS.md"
        ).read_text(encoding="utf-8")

        result = do_release("Sprint 1: Walking Skeleton", config, dry_run=True)

        self.assertTrue(result)

        # Only pre-flight git status should have run
        self.assertEqual(mock_run.call_count, 1)
        self.assertEqual(mock_run.call_args_list[0][0][0][:2], ["git", "status"])

        # No write_version_to_toml call
        mock_write_toml.assert_not_called()

        # No gh() calls (no release create, no milestone close)
        mock_gh.assert_not_called()

        # SPRINT-STATUS.md unchanged
        status_after = (
            Path(self.tmpdir) / "sprints" / "SPRINT-STATUS.md"
        ).read_text(encoding="utf-8")
        self.assertEqual(status_before, status_after)


if __name__ == "__main__":
    unittest.main()
