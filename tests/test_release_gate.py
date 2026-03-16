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
    bump_version,
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
# bump_version tests
# ---------------------------------------------------------------------------

class TestBumpVersion(unittest.TestCase):
    """P5-02: bump_version must reject non-3-part version strings."""

    def test_valid_three_part(self):
        self.assertEqual(bump_version("1.2.3", "patch"), "1.2.4")
        self.assertEqual(bump_version("1.2.3", "minor"), "1.3.0")
        self.assertEqual(bump_version("1.2.3", "major"), "2.0.0")

    def test_v_prefix_stripped(self):
        self.assertEqual(bump_version("v1.0.0", "minor"), "1.1.0")

    def test_two_part_raises_valueerror(self):
        with self.assertRaises(ValueError):
            bump_version("1.0", "minor")

    def test_one_part_raises_valueerror(self):
        with self.assertRaises(ValueError):
            bump_version("1", "patch")

    def test_four_part_raises_valueerror(self):
        with self.assertRaises(ValueError):
            bump_version("1.2.3.4", "minor")

    def test_empty_raises_valueerror(self):
        with self.assertRaises(ValueError):
            bump_version("", "patch")


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

    def test_all_pass_with_real_commands(self):
        """BH-007: All gates pass including gate_tests and gate_build with
        non-empty commands (not the trivial auto-pass empty-list case).

        Uses a subprocess mock that routes gh calls to FakeGitHub and
        simulates success for shell commands (check_commands, build_command).
        """
        self._add_closed_milestone()
        self.fake.runs.append({
            "name": "CI", "status": "completed",
            "conclusion": "success", "headBranch": "main",
        })
        # Stop the default patcher — we need a combined mock
        self.patcher.stop()

        fake_gh = self.fake
        _real_patched = make_patched_subprocess(fake_gh)

        def _combined_run(args, *a, **kw):
            # Shell commands (gate_tests, gate_build) pass shell=True with a string
            if kw.get("shell"):
                return subprocess.CompletedProcess(
                    args=args, returncode=0, stdout="ok\n", stderr="",
                )
            return _real_patched(args, *a, **kw)

        with patch("subprocess.run", _combined_run):
            config = {
                "project": {"base_branch": "main"},
                "ci": {
                    "check_commands": ["python -m pytest", "python -m flake8"],
                    "build_command": "make build",
                },
            }
            passed, results = validate_gates("Sprint 1", config)

        self.assertTrue(passed, f"All gates should pass, got: {results}")
        self.assertEqual(len(results), 5)
        # Verify Tests and Build gates actually ran with detail messages
        tests_result = results[3]  # (name, passed, detail)
        self.assertEqual(tests_result[0], "Tests")
        self.assertTrue(tests_result[1])
        self.assertIn("2 command(s) passed", tests_result[2])
        build_result = results[4]
        self.assertEqual(build_result[0], "Build")
        self.assertTrue(build_result[1])
        self.assertIn("succeeded", build_result[2])

        # Restart the default patcher for tearDown
        self.patcher = patch("subprocess.run", make_patched_subprocess(self.fake))
        self.patcher.start()

    def test_test_gate_failure_stops_before_build(self):
        """BH-007: When gate_tests fails, gate_build does not run.

        Verifies that validate_gates short-circuits on test failure.
        """
        self._add_closed_milestone()
        self.fake.runs.append({
            "name": "CI", "status": "completed",
            "conclusion": "success", "headBranch": "main",
        })
        self.patcher.stop()

        fake_gh = self.fake
        _real_patched = make_patched_subprocess(fake_gh)
        shell_call_count = 0

        def _combined_run(args, *a, **kw):
            nonlocal shell_call_count
            if kw.get("shell"):
                shell_call_count += 1
                # First shell command (check_command) fails
                return subprocess.CompletedProcess(
                    args=args, returncode=1, stdout="", stderr="test failed",
                )
            return _real_patched(args, *a, **kw)

        with patch("subprocess.run", _combined_run):
            config = {
                "project": {"base_branch": "main"},
                "ci": {
                    "check_commands": ["python -m pytest"],
                    "build_command": "make build",
                },
            }
            passed, results = validate_gates("Sprint 1", config)

        self.assertFalse(passed)
        # Stories, CI, PRs pass; Tests fails; Build never runs
        self.assertEqual(len(results), 4)
        self.assertFalse(results[3][1])
        self.assertIn("failed", results[3][2])
        # Only one shell command should have been invoked (the failing test)
        self.assertEqual(shell_call_count, 1)

        self.patcher = patch("subprocess.run", make_patched_subprocess(self.fake))
        self.patcher.start()


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

    @patch("release_gate.subprocess.run")
    def test_timeout_returns_failure(self, mock_run):
        """P13-014: TimeoutExpired is caught and returns clean failure."""
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="sleep 999", timeout=300)
        config = {"ci": {"check_commands": ["sleep 999"]}}
        passed, detail = gate_tests(config)
        self.assertFalse(passed)
        self.assertIn("timed out", detail)


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

    @patch("release_gate.subprocess.run")
    def test_build_timeout(self, mock_run):
        """P13-014: Build timeout returns clean failure."""
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="make build", timeout=300)
        config = {"ci": {"build_command": "make build"}}
        passed, detail = gate_build(config)
        self.assertFalse(passed)
        self.assertIn("timed out", detail)


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
# P13-016: write_version_to_toml code path tests
# ---------------------------------------------------------------------------

from release_gate import write_version_to_toml


class TestWriteVersionToToml(unittest.TestCase):
    """P13-016: Cover all 3 code paths in write_version_to_toml."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.toml_path = Path(self._tmpdir.name) / "project.toml"

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_replace_existing_version(self):
        """Path 1: [release] exists with version= key — replaces it."""
        self.toml_path.write_text(
            '[project]\nname = "test"\n\n'
            '[release]\nversion = "0.1.0"\n',
            encoding="utf-8",
        )
        write_version_to_toml("0.2.0", self.toml_path)
        text = self.toml_path.read_text(encoding="utf-8")
        self.assertIn('version = "0.2.0"', text)
        self.assertNotIn('version = "0.1.0"', text)
        self.assertIn('[project]', text)

    def test_insert_into_existing_section(self):
        """Path 2: [release] exists but no version key — inserts it."""
        self.toml_path.write_text(
            '[project]\nname = "test"\n\n'
            '[release]\nnotes = "some notes"\n',
            encoding="utf-8",
        )
        write_version_to_toml("1.0.0", self.toml_path)
        text = self.toml_path.read_text(encoding="utf-8")
        self.assertIn('version = "1.0.0"', text)
        self.assertIn('notes = "some notes"', text)
        self.assertIn('[project]', text)

    def test_append_new_section(self):
        """Path 3: No [release] section — appends it."""
        self.toml_path.write_text(
            '[project]\nname = "test"\n\n'
            '[ci]\nbuild_command = "make"\n',
            encoding="utf-8",
        )
        write_version_to_toml("0.5.0", self.toml_path)
        text = self.toml_path.read_text(encoding="utf-8")
        self.assertIn('[release]', text)
        self.assertIn('version = "0.5.0"', text)
        # Original content preserved
        self.assertIn('[project]', text)
        self.assertIn('[ci]', text)
        self.assertIn('build_command = "make"', text)

    def test_comment_not_treated_as_section(self):
        """Edge: '# [release]' comment should NOT match as a section header."""
        self.toml_path.write_text(
            '[project]\nname = "test"\n\n'
            '# [release]\n'
            '# placeholder for future release config\n',
            encoding="utf-8",
        )
        write_version_to_toml("2.0.0", self.toml_path)
        text = self.toml_path.read_text(encoding="utf-8")
        # Should append a real [release] section, not modify the comment
        self.assertIn('# [release]', text)  # comment preserved
        # Count real [release] sections — should have exactly 1
        lines = [l for l in text.splitlines() if l.strip() == '[release]']
        self.assertEqual(len(lines), 1, f"Expected 1 real [release] section, found {len(lines)}")
        self.assertIn('version = "2.0.0"', text)

    def test_other_sections_preserved(self):
        """All other TOML content is preserved after version write."""
        original = (
            '[project]\nname = "MyProject"\nrepo = "owner/repo"\n\n'
            '[paths]\nsprints_dir = "sprints"\n\n'
            '[ci]\ncheck_commands = ["pytest"]\nbuild_command = "make"\n\n'
            '[release]\nversion = "0.1.0"\n'
        )
        self.toml_path.write_text(original, encoding="utf-8")
        write_version_to_toml("0.2.0", self.toml_path)
        text = self.toml_path.read_text(encoding="utf-8")
        # Version updated
        self.assertIn('version = "0.2.0"', text)
        # All other sections intact
        self.assertIn('name = "MyProject"', text)
        self.assertIn('repo = "owner/repo"', text)
        self.assertIn('sprints_dir = "sprints"', text)
        self.assertIn('check_commands = ["pytest"]', text)


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


def _make_subprocess_side_effect(
    *, tag_fails=False, commit_fails=False,
    push_tag_fails=False, pre_release_sha="abc123",
):
    """Build a side_effect function for subprocess.run.

    Returns CompletedProcess(returncode=0) for all commands except when
    tag_fails=True and the command is 'git tag', or commit_fails=True and
    the command invokes commit.py, or push_tag_fails=True and the command
    is 'git push'.
    """
    def _side_effect(cmd, **kwargs):
        # Detect 'git rev-parse HEAD' — return the pre-release sha
        if (isinstance(cmd, list) and len(cmd) >= 3
                and cmd[0] == "git" and cmd[1] == "rev-parse" and cmd[2] == "HEAD"):
            return subprocess.CompletedProcess(
                args=cmd, returncode=0, stdout=pre_release_sha, stderr="",
            )
        # Detect 'git tag' invocations
        if isinstance(cmd, list) and len(cmd) >= 2 and cmd[0] == "git" and cmd[1] == "tag":
            if tag_fails:
                return subprocess.CompletedProcess(
                    args=cmd, returncode=1, stdout="", stderr="tag already exists",
                )
        # Detect 'git push' invocations for tag push
        if (push_tag_fails and isinstance(cmd, list) and len(cmd) >= 3
                and cmd[0] == "git" and cmd[1] == "push"):
            return subprocess.CompletedProcess(
                args=cmd, returncode=1, stdout="", stderr="push rejected",
            )
        # Detect commit.py invocations
        if commit_fails and isinstance(cmd, list) and len(cmd) >= 2:
            if any("commit.py" in str(arg) for arg in cmd):
                return subprocess.CompletedProcess(
                    args=cmd, returncode=1, stdout="", stderr="commit hook failed",
                )
        return subprocess.CompletedProcess(
            args=cmd if isinstance(cmd, list) else [cmd],
            returncode=0, stdout="", stderr="",
        )
    return _side_effect


class TestDoRelease(unittest.TestCase):
    """Tests for do_release() — the full release orchestration flow.

    BH-P11-060: These tests intentionally patch subprocess.run globally rather
    than using FakeGitHub.  This is a deliberate trade-off: unit tests here
    verify the *call sequence* (correct git commands in the right order with
    the right arguments) without needing a real git repo.  Integration tests
    in TestDoReleaseDryRunIntegration and the golden-run suite exercise real
    git operations through FakeGitHub.  Changing these to use real git would
    make them slower and more brittle without improving coverage of the
    release orchestration logic.
    """

    def setUp(self):
        """Create a temp dir with sprint-config/project.toml and sprints/SPRINT-STATUS.md."""
        self._tmpdir = tempfile.TemporaryDirectory()
        self.tmpdir = self._tmpdir.name
        self._orig_cwd = os.getcwd()
        os.chdir(self.tmpdir)
        self.addCleanup(os.chdir, self._orig_cwd)

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

        # subprocess.run called for: git status, rev-parse, git add, commit,
        # git tag, git push, tag-verify
        self.assertGreaterEqual(mock_run.call_count, 6)
        run_cmds = [call[0][0] for call in mock_run.call_args_list]
        # git status (pre-flight)
        self.assertEqual(run_cmds[0][0], "git")
        self.assertEqual(run_cmds[0][1], "status")
        # git rev-parse HEAD (save pre-release sha)
        self.assertEqual(run_cmds[1][0], "git")
        self.assertEqual(run_cmds[1][1], "rev-parse")
        # git add
        self.assertEqual(run_cmds[2][0], "git")
        self.assertEqual(run_cmds[2][1], "add")
        # git tag
        self.assertEqual(run_cmds[4][0], "git")
        self.assertEqual(run_cmds[4][1], "tag")
        # git push
        self.assertEqual(run_cmds[5][0], "git")
        self.assertEqual(run_cmds[5][1], "push")

        # gh() called for: release create, milestone close, release view
        self.assertGreaterEqual(mock_gh.call_count, 2)
        gh_calls = [call[0][0] for call in mock_gh.call_args_list]
        # First gh call is release create with correct tag
        self.assertEqual(gh_calls[0][0], "release")
        self.assertEqual(gh_calls[0][1], "create")
        self.assertIn("v1.1.0", gh_calls[0])
        # Verify release notes content was passed (--notes-file arg present)
        self.assertTrue(
            any("--notes-file" in str(arg) or "--notes" in str(arg) for arg in gh_calls[0]),
            "release create should include notes"
        )
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

    # -- Test 4: commit failure triggers proper git rollback -------------------

    @patch("release_gate.gh")
    @patch("release_gate.find_milestone_number")
    @patch("release_gate.subprocess.run")
    @patch("release_gate.write_version_to_toml")
    @patch("release_gate.calculate_version")
    def test_commit_failure_rollback_unstages_and_restores(
        self, mock_calc, mock_write_toml, mock_run, mock_ms, mock_gh,
    ):
        """When commit fails, rollback calls git reset HEAD to unstage, then git checkout to restore."""
        mock_calc.return_value = ("1.1.0", "1.0.0", "minor", [
            {"subject": "feat: add dashboard", "body": ""},
        ])
        mock_write_toml.return_value = None
        mock_run.side_effect = _make_subprocess_side_effect(commit_fails=True)

        config = {
            "project": {"name": "TestProject", "repo": "owner/repo"},
            "ci": {},
            "paths": {"sprints_dir": "sprints"},
        }
        result = do_release("Sprint 1: Walking Skeleton", config)

        self.assertFalse(result)

        # No gh() calls — release was never created
        mock_gh.assert_not_called()
        mock_ms.assert_not_called()

        # Inspect subprocess.run calls for the rollback sequence
        run_cmds = [call[0][0] for call in mock_run.call_args_list]

        # Find git reset HEAD calls
        reset_calls = [
            c for c in run_cmds
            if isinstance(c, list) and len(c) >= 4
            and c[0] == "git" and c[1] == "reset" and c[2] == "HEAD"
            and c[3] == "--"
        ]
        self.assertGreaterEqual(
            len(reset_calls), 1,
            f"Expected at least one 'git reset HEAD --' call, got: {run_cmds}",
        )

        # Find git checkout -- calls (restore working tree)
        checkout_calls = [
            c for c in run_cmds
            if isinstance(c, list) and len(c) >= 3
            and c[0] == "git" and c[1] == "checkout" and c[2] == "--"
        ]
        self.assertGreaterEqual(
            len(checkout_calls), 1,
            f"Expected at least one 'git checkout --' call, got: {run_cmds}",
        )

        # Verify reset comes before checkout in the call list
        reset_idx = next(
            i for i, c in enumerate(run_cmds)
            if isinstance(c, list) and len(c) >= 4
            and c[0] == "git" and c[1] == "reset" and c[2] == "HEAD"
        )
        checkout_idx = next(
            i for i, c in enumerate(run_cmds)
            if isinstance(c, list) and len(c) >= 3
            and c[0] == "git" and c[1] == "checkout" and c[2] == "--"
        )
        self.assertLess(
            reset_idx, checkout_idx,
            "git reset HEAD should be called before git checkout --",
        )

    # -- Test 5: dry run makes no mutations ------------------------------------

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

        # Pre-flight git status + tag existence check in release notes
        self.assertGreaterEqual(mock_run.call_count, 1)
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

    # -- Test 6: P5-01 — rollback undoes version commit -----------------------

    @patch("release_gate.gh")
    @patch("release_gate.find_milestone_number")
    @patch("release_gate.subprocess.run")
    @patch("release_gate.write_version_to_toml")
    @patch("release_gate.calculate_version")
    def test_push_tag_failure_resets_commit_and_deletes_tag(
        self, mock_calc, mock_write_toml, mock_run, mock_ms, mock_gh,
    ):
        """BH-001: When push fails, BOTH the local tag AND the commit must be undone.

        Prior to this fix, only _rollback_commit() was called on push failure.
        The local tag created by 'git tag -a' was left orphaned, causing the
        next release attempt to fail with 'tag already exists'.
        """
        mock_calc.return_value = ("2.0.0", "1.0.0", "major", [
            {"subject": "feat!: new API", "body": "BREAKING CHANGE: v2"},
        ])
        mock_write_toml.return_value = None
        mock_run.side_effect = _make_subprocess_side_effect(
            push_tag_fails=True, pre_release_sha="deadbeef",
        )

        config = {
            "project": {"name": "TestProject", "repo": "owner/repo"},
            "ci": {},
            "paths": {"sprints_dir": "sprints"},
        }
        result = do_release("Sprint 2: API", config)

        self.assertFalse(result)

        run_cmds = [call[0][0] for call in mock_run.call_args_list]

        # BH-001: Verify local tag is deleted after push failure
        tag_delete_calls = [
            c for c in run_cmds
            if isinstance(c, list) and len(c) >= 3
            and c[0] == "git" and c[1] == "tag" and c[2] == "-d"
        ]
        self.assertGreaterEqual(
            len(tag_delete_calls), 1,
            f"Expected 'git tag -d v2.0.0' after push failure, got: {run_cmds}",
        )
        self.assertIn("v2.0.0", tag_delete_calls[0],
                       "Tag delete should target the release tag")

        # Verify git reset --hard <sha> was called to undo the commit
        reset_hard_calls = [
            c for c in run_cmds
            if isinstance(c, list) and len(c) >= 4
            and c[0] == "git" and c[1] == "reset" and c[2] == "--hard"
        ]
        self.assertGreaterEqual(
            len(reset_hard_calls), 1,
            f"Expected 'git reset --hard <sha>' after push failure, got: {run_cmds}",
        )
        self.assertEqual(reset_hard_calls[0][3], "deadbeef")

    # -- Test 7: P5-01 — gh release failure also resets commit + deletes tag ---

    @patch("release_gate.subprocess.run")
    @patch("release_gate.write_version_to_toml")
    @patch("release_gate.calculate_version")
    def test_gh_release_failure_resets_commit(
        self, mock_calc, mock_write_toml, mock_run,
    ):
        """P5-01 + P13-001: When GitHub release creation fails, commit is undone
        AND tag is deleted from both local and remote."""
        mock_calc.return_value = ("1.1.0", "1.0.0", "minor", [
            {"subject": "feat: dashboard", "body": ""},
        ])
        mock_write_toml.return_value = None
        mock_run.side_effect = _make_subprocess_side_effect(
            pre_release_sha="cafe0000",
        )

        config = {
            "project": {"name": "TestProject", "repo": "owner/repo"},
            "ci": {},
            "paths": {"sprints_dir": "sprints"},
        }

        # Patch gh() to fail on release create
        def _gh_side_effect(args):
            if args[0] == "release" and args[1] == "create":
                raise RuntimeError("GitHub API error")
            return ""

        with patch("release_gate.gh", side_effect=_gh_side_effect):
            with patch("release_gate.find_milestone_number", return_value=None):
                result = do_release("Sprint 1", config)

        self.assertFalse(result)

        # After push succeeded, rollback should use revert (not reset --hard)
        # because the commit is already on the remote
        run_cmds = [call[0][0] for call in mock_run.call_args_list]
        revert_calls = [
            c for c in run_cmds
            if isinstance(c, list) and len(c) >= 3
            and c[0] == "git" and c[1] == "revert"
        ]
        self.assertGreaterEqual(
            len(revert_calls), 1,
            f"Expected 'git revert' after release failure (commit already pushed), got: {run_cmds}",
        )

        # P13-001: Tag should be deleted from local AND remote
        tag_delete_calls = [
            c for c in run_cmds
            if isinstance(c, list) and len(c) >= 3
            and c[0] == "git" and c[1] == "tag" and c[2] == "-d"
        ]
        self.assertGreaterEqual(
            len(tag_delete_calls), 1,
            f"Expected 'git tag -d' to delete local tag, got: {run_cmds}",
        )
        push_delete_calls = [
            c for c in run_cmds
            if isinstance(c, list) and len(c) >= 3
            and c[0] == "git" and c[1] == "push" and "--delete" in c
        ]
        self.assertGreaterEqual(
            len(push_delete_calls), 1,
            f"Expected 'git push --delete' to remove remote tag, got: {run_cmds}",
        )

    # -- Test 8: P6-03 — gh release failure cleans up notes temp file ----------

    @patch("release_gate.subprocess.run")
    @patch("release_gate.write_version_to_toml")
    @patch("release_gate.calculate_version")
    def test_gh_release_failure_cleans_notes(
        self, mock_calc, mock_write_toml, mock_run,
    ):
        """P6-03: When GitHub release creation fails, no temp notes file remains."""
        mock_calc.return_value = ("1.1.0", "1.0.0", "minor", [
            {"subject": "feat: dashboard", "body": ""},
        ])
        mock_write_toml.return_value = None
        mock_run.side_effect = _make_subprocess_side_effect(
            pre_release_sha="cafe0000",
        )

        config = {
            "project": {"name": "TestProject", "repo": "owner/repo"},
            "ci": {},
            "paths": {"sprints_dir": "sprints"},
        }

        # Capture the notes file path from the gh() call
        notes_file_path = None

        def _gh_side_effect(args):
            nonlocal notes_file_path
            if args[0] == "release" and args[1] == "create":
                # Extract the --notes-file path from args
                for i, a in enumerate(args):
                    if a == "--notes-file" and i + 1 < len(args):
                        notes_file_path = args[i + 1]
                raise RuntimeError("GitHub API error")
            return ""

        with patch("release_gate.gh", side_effect=_gh_side_effect):
            with patch("release_gate.find_milestone_number", return_value=None):
                result = do_release("Sprint 1", config)

        self.assertFalse(result)

        # The notes file should have been cleaned up by the finally block
        self.assertIsNotNone(notes_file_path, "gh() should have received --notes-file")
        self.assertFalse(
            Path(notes_file_path).exists(),
            f"Temp notes file should be cleaned up after failure: {notes_file_path}",
        )

        # Also verify no release-notes.md in cwd (P6-04: should use tempfile)
        self.assertFalse(
            Path("release-notes.md").exists(),
            "release-notes.md should NOT be written to cwd",
        )

    # -- Test 9: P6-04 — release notes uses tempfile, not cwd -----------------

    @patch("release_gate.gh")
    @patch("release_gate.find_milestone_number")
    @patch("release_gate.subprocess.run")
    @patch("release_gate.write_version_to_toml")
    @patch("release_gate.calculate_version")
    def test_release_notes_uses_tempfile(
        self, mock_calc, mock_write_toml, mock_run, mock_ms, mock_gh,
    ):
        """P6-04: do_release writes notes to a temp file, not 'release-notes.md' in cwd."""
        mock_calc.return_value = ("1.1.0", "1.0.0", "minor", [
            {"subject": "feat: add dashboard", "body": ""},
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

        # Capture the --notes-file path passed to gh()
        notes_file_path = None
        original_gh_return = mock_gh.return_value

        def _gh_capture(args):
            nonlocal notes_file_path
            if isinstance(args, list) and len(args) >= 2:
                if args[0] == "release" and args[1] == "create":
                    for i, a in enumerate(args):
                        if a == "--notes-file" and i + 1 < len(args):
                            notes_file_path = args[i + 1]
            return original_gh_return

        mock_gh.side_effect = _gh_capture

        result = do_release("Sprint 1: Walking Skeleton", config)

        self.assertTrue(result)

        # Notes file should NOT be release-notes.md in cwd
        self.assertFalse(
            Path("release-notes.md").exists(),
            "release-notes.md should NOT be written to cwd",
        )

        # The notes file path should be in a temp directory, not cwd
        self.assertIsNotNone(notes_file_path, "gh() should have received --notes-file")
        self.assertNotEqual(
            Path(notes_file_path).name, "release-notes.md",
            "Notes file should not be named 'release-notes.md'",
        )
        # The temp file should be cleaned up after success
        self.assertFalse(
            Path(notes_file_path).exists(),
            f"Temp notes file should be cleaned up after success: {notes_file_path}",
        )


# ---------------------------------------------------------------------------
# P12-008: do_release happy path via FakeGitHub — verifies actual state changes
# ---------------------------------------------------------------------------


class TestDoReleaseFakeGH(unittest.TestCase):
    """P12-008: do_release happy path with FakeGitHub for gh calls.

    Unlike TestDoRelease (which patches gh globally and checks call sequences),
    this test routes gh calls through FakeGitHub and verifies actual state:
    release created, milestone closed, status file updated.
    """

    def setUp(self):
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

        # Set up FakeGitHub with a milestone
        self.fake = FakeGitHub()
        self.fake.milestones = [
            {"number": 1, "title": "Sprint 1: Walking Skeleton", "state": "open"},
        ]

    def tearDown(self):
        os.chdir(self._orig_cwd)
        self._tmpdir.cleanup()

    def _make_combined_side_effect(self):
        """Route gh calls to FakeGitHub, fake git commands."""
        def _side_effect(cmd, **kwargs):
            if isinstance(cmd, list) and cmd and cmd[0] == "gh":
                return self.fake.handle(cmd[1:])
            # git rev-parse HEAD
            if (isinstance(cmd, list) and len(cmd) >= 3
                    and cmd[0] == "git" and cmd[1] == "rev-parse"):
                return subprocess.CompletedProcess(
                    args=cmd, returncode=0, stdout="pre123", stderr="",
                )
            # All other git commands succeed
            return subprocess.CompletedProcess(
                args=cmd if isinstance(cmd, list) else [cmd],
                returncode=0, stdout="", stderr="",
            )
        return _side_effect

    @patch("release_gate.write_version_to_toml")
    @patch("release_gate.calculate_version")
    @patch("release_gate.subprocess.run")
    def test_happy_path_state_changes(self, mock_run, mock_calc, mock_write):
        """Verify actual state changes: release created, milestone closed, status updated."""
        mock_calc.return_value = ("1.1.0", "1.0.0", "minor", [
            {"subject": "feat: add dashboard", "body": ""},
        ])
        mock_write.return_value = None
        mock_run.side_effect = self._make_combined_side_effect()

        config = {
            "project": {"name": "TestProject", "repo": "owner/repo"},
            "ci": {},
            "paths": {"sprints_dir": "sprints"},
            "_config_dir": "sprint-config",
        }
        result = do_release("Sprint 1: Walking Skeleton", config)

        self.assertTrue(result, "do_release should return True on success")

        # Verify FakeGitHub state: release was created
        self.assertTrue(
            len(self.fake.releases) >= 1,
            f"Expected at least 1 release, got {len(self.fake.releases)}",
        )
        release = self.fake.releases[0]
        self.assertEqual(release["tag_name"], "v1.1.0")

        # Verify FakeGitHub state: milestone was closed
        ms = self.fake.milestones[0]
        self.assertEqual(ms["state"], "closed",
                         f"Milestone state should be 'closed', got '{ms['state']}'")

        # Verify SPRINT-STATUS.md was updated
        status = (Path(self.tmpdir) / "sprints" / "SPRINT-STATUS.md").read_text(
            encoding="utf-8",
        )
        self.assertIn("v1.1.0", status)
        self.assertIn("Released", status)


# ---------------------------------------------------------------------------
# P6-20: do_release pre-flight distinguishes git errors from dirty tree
# ---------------------------------------------------------------------------


class TestDoReleasePreFlight(unittest.TestCase):
    """P6-20: Pre-flight checks distinguish 'not a git repo' from 'dirty tree'."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.tmpdir = self._tmpdir.name
        self._orig_cwd = os.getcwd()
        os.chdir(self.tmpdir)
        self.addCleanup(os.chdir, self._orig_cwd)

        sc_dir = Path(self.tmpdir) / "sprint-config"
        sc_dir.mkdir()
        (sc_dir / "project.toml").write_text(_MINIMAL_TOML, encoding="utf-8")

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

    @patch("release_gate.calculate_version")
    @patch("release_gate.subprocess.run")
    def test_not_a_git_repo_error(self, mock_run, mock_calc):
        """Non-zero returncode from git status produces 'not a git repository' error."""
        import io
        from contextlib import redirect_stderr

        mock_run.return_value = subprocess.CompletedProcess(
            args=["git", "status", "--porcelain"],
            returncode=128,
            stdout="",
            stderr="fatal: not a git repository",
        )

        config = {
            "project": {"name": "TestProject", "repo": "owner/repo"},
            "ci": {},
            "paths": {"sprints_dir": "sprints"},
        }

        buf = io.StringIO()
        with redirect_stderr(buf):
            result = do_release("Sprint 1", config)

        self.assertFalse(result)
        self.assertIn("not a git repository", buf.getvalue())
        mock_calc.assert_not_called()

    @patch("release_gate.calculate_version")
    @patch("release_gate.subprocess.run")
    def test_dirty_tree_error(self, mock_run, mock_calc):
        """Zero returncode but non-empty stdout produces 'not clean' error."""
        import io
        from contextlib import redirect_stderr

        mock_run.return_value = subprocess.CompletedProcess(
            args=["git", "status", "--porcelain"],
            returncode=0,
            stdout=" M file.txt\n",
            stderr="",
        )

        config = {
            "project": {"name": "TestProject", "repo": "owner/repo"},
            "ci": {},
            "paths": {"sprints_dir": "sprints"},
        }

        buf = io.StringIO()
        with redirect_stderr(buf):
            result = do_release("Sprint 1", config)

        self.assertFalse(result)
        self.assertIn("not clean", buf.getvalue())
        mock_calc.assert_not_called()


# ---------------------------------------------------------------------------
# P5-12: do_release integration test (dry-run path)
# ---------------------------------------------------------------------------


class TestDoReleaseDryRunIntegration(unittest.TestCase):
    """P5-12: Exercises do_release dry-run path end-to-end.

    Uses mocked subprocess to simulate a real git repo with tags and
    commits, then verifies version calculation → notes generation flow.
    """

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="release-int-")
        self.toml_path = Path(self.tmpdir) / "project.toml"
        self.toml_path.write_text(
            '[project]\nname = "TestApp"\nrepo = "owner/repo"\n'
            '[release]\nversion = "1.0.0"\n',
            encoding="utf-8",
        )
        self.config = {
            "project": {"name": "TestApp", "repo": "owner/repo"},
            "_config_dir": self.tmpdir,
        }

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _make_side_effect(self):
        """Subprocess side effect for dry-run test."""
        def side_effect(args, **kwargs):
            cmd = args if isinstance(args, list) else [args]
            joined = " ".join(str(a) for a in cmd)
            # git status --porcelain (clean tree)
            if "status" in joined and "porcelain" in joined:
                return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
            # git tag --list (existing tag)
            if "tag" in joined and "--list" in joined:
                return subprocess.CompletedProcess(
                    cmd, 0, stdout="v1.0.0\n", stderr="",
                )
            # git log (commits since tag) — must use the \x00--END--\x00 delimiter
            # that parse_commits_since expects from --format="%s\n%b\x00--END--\x00"
            if "git" in joined and "log" in joined:
                delim = "\x00--END--\x00"
                return subprocess.CompletedProcess(
                    cmd, 0,
                    stdout=f"feat: add new feature\n{delim}fix: resolve bug\n{delim}",
                    stderr="",
                )
            # Default success
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
        return side_effect

    def test_dry_run_calculates_version_and_notes(self):
        """Dry-run exercises version calc + notes generation without side effects."""
        import io
        from contextlib import redirect_stdout

        with patch("subprocess.run", side_effect=self._make_side_effect()):
            buf = io.StringIO()
            with redirect_stdout(buf):
                result = do_release(
                    "Sprint 1", self.config, dry_run=True,
                )
        output = buf.getvalue()
        # Dry run should print version bump info with correct calculated version
        # feat commit should trigger minor bump: 1.0.0 → 1.1.0
        self.assertIn("1.1.0", output)
        self.assertIn("minor bump", output)
        self.assertIn("DRY-RUN", output)
        # Version file should NOT be modified (dry run)
        self.assertIn('version = "1.0.0"', self.toml_path.read_text())


# ---------------------------------------------------------------------------
# P7-17: find_latest_semver_tag and parse_commits_since direct tests
# ---------------------------------------------------------------------------

from release_gate import find_latest_semver_tag, parse_commits_since


class TestFindLatestSemverTag(unittest.TestCase):
    """P7-17: Direct tests for find_latest_semver_tag()."""

    @patch("release_gate.subprocess.run")
    def test_no_tags(self, mock_run):
        """No tags → returns None."""
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr="",
        )
        self.assertIsNone(find_latest_semver_tag())

    @patch("release_gate.subprocess.run")
    def test_single_tag(self, mock_run):
        """Single semver tag is returned."""
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="v1.2.3\n", stderr="",
        )
        self.assertEqual(find_latest_semver_tag(), "v1.2.3")

    @patch("release_gate.subprocess.run")
    def test_multiple_tags_sorted(self, mock_run):
        """First matching semver tag returned (already sorted by git)."""
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0,
            stdout="v2.0.0\nv1.5.0\nv1.0.0\n", stderr="",
        )
        self.assertEqual(find_latest_semver_tag(), "v2.0.0")

    @patch("release_gate.subprocess.run")
    def test_non_semver_tags_skipped(self, mock_run):
        """Non-semver tags are skipped."""
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0,
            stdout="v-beta\nv1.0.0\n", stderr="",
        )
        self.assertEqual(find_latest_semver_tag(), "v1.0.0")

    @patch("release_gate.subprocess.run")
    def test_git_error_returns_none(self, mock_run):
        """Git error → returns None."""
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=128, stdout="", stderr="error",
        )
        self.assertIsNone(find_latest_semver_tag())


class TestParseCommitsSince(unittest.TestCase):
    """P7-17: Direct tests for parse_commits_since()."""

    @patch("release_gate.subprocess.run")
    def test_with_tag(self, mock_run):
        """Parses commits since a given tag."""
        delim = "\x00--END--\x00"
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0,
            stdout=f"feat: add login\n\nbody text{delim}fix: typo{delim}",
            stderr="",
        )
        commits = parse_commits_since("v1.0.0")
        self.assertEqual(len(commits), 2)
        self.assertEqual(commits[0]["subject"], "feat: add login")
        self.assertEqual(commits[0]["body"], "body text")
        self.assertEqual(commits[1]["subject"], "fix: typo")

    @patch("release_gate.subprocess.run")
    def test_no_tag_all_commits(self, mock_run):
        """No tag → parses all commits."""
        delim = "\x00--END--\x00"
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0,
            stdout=f"initial commit{delim}",
            stderr="",
        )
        commits = parse_commits_since(None)
        self.assertEqual(len(commits), 1)
        # Verify the command didn't include a tag..HEAD range
        cmd = mock_run.call_args[0][0]
        self.assertNotIn("..HEAD", " ".join(cmd))

    @patch("release_gate.subprocess.run")
    def test_empty_range(self, mock_run):
        """Empty commit range returns empty list."""
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr="",
        )
        commits = parse_commits_since("v1.0.0")
        self.assertEqual(commits, [])

    @patch("release_gate.subprocess.run")
    def test_git_error(self, mock_run):
        """Git error returns empty list."""
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=128, stdout="", stderr="error",
        )
        commits = parse_commits_since("v1.0.0")
        self.assertEqual(commits, [])


# ---------------------------------------------------------------------------
# BH-P11-112: do_release handles FileNotFoundError when git is missing
# ---------------------------------------------------------------------------


class TestDoReleaseGitMissing(unittest.TestCase):
    """BH-P11-112: do_release should handle FileNotFoundError from subprocess.

    If git is not installed, subprocess.run raises FileNotFoundError.
    do_release must catch this and print a clean error, not crash with a
    traceback.
    """

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.tmpdir = self._tmpdir.name
        self._orig_cwd = os.getcwd()
        os.chdir(self.tmpdir)
        self.addCleanup(os.chdir, self._orig_cwd)

        sc_dir = Path(self.tmpdir) / "sprint-config"
        sc_dir.mkdir()
        (sc_dir / "project.toml").write_text(
            '[project]\nname = "TestApp"\nrepo = "owner/repo"\n',
            encoding="utf-8",
        )

    def tearDown(self):
        os.chdir(self._orig_cwd)
        self._tmpdir.cleanup()

    @patch("release_gate.subprocess.run")
    def test_git_not_installed_returns_false(self, mock_run):
        """FileNotFoundError from subprocess.run produces a clean error."""
        import io
        from contextlib import redirect_stderr

        mock_run.side_effect = FileNotFoundError(
            "[Errno 2] No such file or directory: 'git'"
        )

        config = {
            "project": {"name": "TestApp", "repo": "owner/repo"},
            "ci": {},
            "paths": {"sprints_dir": "sprints"},
        }

        buf = io.StringIO()
        with redirect_stderr(buf):
            result = do_release("Sprint 1", config)

        self.assertFalse(result)
        self.assertIn("git", buf.getvalue().lower())


if __name__ == "__main__":
    unittest.main()
