#!/usr/bin/env python3
"""Mock-based unit tests for gh CLI interactions across giles scripts.

Tests commit.py validation and release_gate.py version calculation,
gate validation, TOML writing, and release notes without any real
gh CLI or git calls.

Also tests check_status.py, bootstrap_github.py, populate_issues.py,
sync_tracking.py, and update_burndown.py with mocked subprocess calls.

Run: python -m unittest tests.test_gh_interactions -v
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from commit import validate_message, check_atomicity

sys.path.insert(0, str(ROOT / "skills" / "sprint-release" / "scripts"))
from release_gate import (
    determine_bump, bump_version, calculate_version,
    find_latest_semver_tag, parse_commits_since,
    write_version_to_toml, generate_release_notes,
    gate_stories, gate_ci, gate_prs,
    validate_gates, print_gate_summary,
)

sys.path.insert(0, str(ROOT / "skills" / "sprint-monitor" / "scripts"))
import check_status

sys.path.insert(0, str(ROOT / "skills" / "sprint-setup" / "scripts"))
import bootstrap_github
import populate_issues

sys.path.insert(0, str(ROOT / "skills" / "sprint-run" / "scripts"))
import sync_tracking
import update_burndown


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
        # Regex requires .+ after ": ", so empty desc fails as invalid format
        self.assertIn("Invalid conventional commit", err)

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
# release_gate.py -- version calculation tests
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
# release_gate.py -- gate validation tests (mocked gh)
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
# check_status.py tests -- check_ci() and check_prs()
# ---------------------------------------------------------------------------

class TestCheckCI(unittest.TestCase):
    """Test check_status.check_ci() with mocked gh_json."""

    @patch("check_status.gh_json")
    def test_no_runs(self, mock_gh):
        mock_gh.return_value = []
        report, actions = check_status.check_ci()
        self.assertEqual(len(report), 1)
        self.assertIn("no recent runs", report[0])

    @patch("check_status.gh_json")
    def test_all_passing(self, mock_gh):
        mock_gh.return_value = [
            {"status": "completed", "conclusion": "success",
             "name": "CI", "headBranch": "main", "databaseId": 1},
        ]
        report, actions = check_status.check_ci()
        self.assertIn("1 passing", report[0])
        self.assertEqual(len(actions), 0)

    @patch("check_status.gh")
    @patch("check_status.gh_json")
    def test_failing_run(self, mock_gh_json, mock_gh):
        mock_gh_json.return_value = [
            {"status": "completed", "conclusion": "failure",
             "name": "CI", "headBranch": "feat/x", "databaseId": 42},
        ]
        # Mock the gh() call for log-failed
        mock_gh.return_value = "error: something broke\nfatal: test failed"
        report, actions = check_status.check_ci()
        self.assertIn("1 failing", report[0])
        self.assertTrue(len(actions) > 0)


class TestCheckPRs(unittest.TestCase):
    """Test check_status.check_prs() with mocked gh_json."""

    @patch("check_status.gh_json")
    def test_no_prs(self, mock_gh):
        mock_gh.return_value = []
        report, actions = check_status.check_prs()
        self.assertIn("none open", report[0])

    @patch("check_status.gh_json")
    def test_approved_pr(self, mock_gh):
        mock_gh.return_value = [
            {"number": 1, "title": "feat: add login",
             "reviewDecision": "APPROVED",
             "statusCheckRollup": [
                 {"status": "COMPLETED", "conclusion": "SUCCESS"},
             ],
             "labels": [], "createdAt": "2026-03-09T00:00:00Z"},
        ]
        report, actions = check_status.check_prs()
        self.assertIn("1 open", report[0])
        self.assertIn("1 approved", report[0])

    @patch("check_status.gh_json")
    def test_needs_review_pr(self, mock_gh):
        mock_gh.return_value = [
            {"number": 2, "title": "fix: typo",
             "reviewDecision": "",
             "statusCheckRollup": [],
             "labels": [], "createdAt": "2026-03-09T00:00:00Z"},
        ]
        report, actions = check_status.check_prs()
        self.assertIn("1 needs review", report[0])


# ---------------------------------------------------------------------------
# bootstrap_github.py tests -- create_label with mocked run_gh
# ---------------------------------------------------------------------------

class TestCreateLabel(unittest.TestCase):
    """Test bootstrap_github.create_label() with mocked run_gh."""

    @patch("bootstrap_github.run_gh")
    def test_creates_label(self, mock_run_gh):
        mock_run_gh.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr="",
        )
        # Should not raise
        bootstrap_github.create_label("test-label", "ff0000", "A test label")
        mock_run_gh.assert_called_once()
        call_args = mock_run_gh.call_args[0][0]
        self.assertIn("label", call_args)
        self.assertIn("create", call_args)
        self.assertIn("test-label", call_args)

    @patch("bootstrap_github.run_gh")
    def test_label_error_handled(self, mock_run_gh):
        mock_run_gh.return_value = subprocess.CompletedProcess(
            args=[], returncode=1, stdout="", stderr="already exists",
        )
        # Should not raise (create_label handles errors gracefully)
        bootstrap_github.create_label("existing-label", "ff0000")


# ---------------------------------------------------------------------------
# populate_issues.py tests -- get_existing_issues with mocked run_gh
# ---------------------------------------------------------------------------

class TestGetExistingIssues(unittest.TestCase):
    """Test populate_issues.get_existing_issues() with mocked run_gh."""

    @patch("populate_issues.run_gh")
    def test_returns_story_ids(self, mock_run_gh):
        mock_run_gh.return_value = subprocess.CompletedProcess(
            args=[], returncode=0,
            stdout=json.dumps([
                {"title": "US-0101: Setup project"},
                {"title": "US-0102: Add auth"},
                {"title": "Not a story"},
            ]),
            stderr="",
        )
        existing = populate_issues.get_existing_issues()
        self.assertIn("US-0101", existing)
        self.assertIn("US-0102", existing)
        self.assertEqual(len(existing), 2)

    @patch("populate_issues.run_gh")
    def test_handles_empty_response(self, mock_run_gh):
        mock_run_gh.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="[]", stderr="",
        )
        existing = populate_issues.get_existing_issues()
        self.assertEqual(len(existing), 0)

    @patch("populate_issues.run_gh")
    def test_handles_gh_failure(self, mock_run_gh):
        mock_run_gh.return_value = subprocess.CompletedProcess(
            args=[], returncode=1, stdout="", stderr="auth failed",
        )
        existing = populate_issues.get_existing_issues()
        self.assertEqual(len(existing), 0)


# ---------------------------------------------------------------------------
# sync_tracking.py tests -- find_milestone_title with mocked gh
# ---------------------------------------------------------------------------

class TestFindMilestoneTitle(unittest.TestCase):
    """Test sync_tracking.find_milestone_title() with mocked gh."""

    @patch("sync_tracking.gh")
    def test_finds_sprint(self, mock_gh):
        mock_gh.return_value = json.dumps([
            {"title": "Sprint 1: Walking Skeleton", "number": 1},
            {"title": "Sprint 2: Features", "number": 2},
        ])
        result = sync_tracking.find_milestone_title(1)
        self.assertEqual(result, "Sprint 1: Walking Skeleton")

    @patch("sync_tracking.gh")
    def test_no_match(self, mock_gh):
        mock_gh.return_value = json.dumps([
            {"title": "Sprint 2: Features", "number": 2},
        ])
        result = sync_tracking.find_milestone_title(1)
        self.assertIsNone(result)

    @patch("sync_tracking.gh")
    def test_empty_response(self, mock_gh):
        mock_gh.return_value = ""
        result = sync_tracking.find_milestone_title(1)
        self.assertIsNone(result)


# ---------------------------------------------------------------------------
# update_burndown.py tests -- extract_sp
# ---------------------------------------------------------------------------

class TestExtractSP(unittest.TestCase):
    """Test update_burndown.extract_sp() label/body parsing."""

    def test_sp_from_label_dict(self):
        issue = {"labels": [{"name": "sp:3"}], "body": ""}
        self.assertEqual(update_burndown.extract_sp(issue), 3)

    def test_sp_from_label_string(self):
        issue = {"labels": ["sp:5"], "body": ""}
        self.assertEqual(update_burndown.extract_sp(issue), 5)

    def test_sp_from_body(self):
        issue = {"labels": [], "body": "Story Points: 8"}
        self.assertEqual(update_burndown.extract_sp(issue), 8)

    def test_sp_from_body_table(self):
        issue = {"labels": [], "body": "| SP | 3 |"}
        self.assertEqual(update_burndown.extract_sp(issue), 3)

    def test_sp_zero_when_missing(self):
        issue = {"labels": [], "body": "No points here"}
        self.assertEqual(update_burndown.extract_sp(issue), 0)

    def test_sp_from_body_lowercase(self):
        issue = {"labels": [], "body": "sp = 2"}
        self.assertEqual(update_burndown.extract_sp(issue), 2)

    def test_label_takes_priority(self):
        issue = {"labels": [{"name": "sp:3"}], "body": "SP: 8"}
        self.assertEqual(update_burndown.extract_sp(issue), 3)


class TestGetBaseBranch(unittest.TestCase):
    def test_returns_configured_branch(self):
        config = {"project": {"base_branch": "develop"}}
        from validate_config import get_base_branch
        self.assertEqual(get_base_branch(config), "develop")

    def test_defaults_to_main(self):
        config = {"project": {"name": "test"}}
        from validate_config import get_base_branch
        self.assertEqual(get_base_branch(config), "main")

    def test_empty_string_defaults_to_main(self):
        config = {"project": {"base_branch": ""}}
        from validate_config import get_base_branch
        self.assertEqual(get_base_branch(config), "main")


if __name__ == "__main__":
    unittest.main()
