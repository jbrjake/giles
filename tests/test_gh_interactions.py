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
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "scripts"))

from fake_github import FakeGitHub

import commit
from commit import validate_message, check_atomicity
import sprint_analytics

sys.path.insert(0, str(ROOT / "skills" / "sprint-release" / "scripts"))
from release_gate import (
    determine_bump, bump_version,
    write_version_to_toml, generate_release_notes,
    gate_stories, gate_ci, gate_prs,
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
        ok, detail = gate_ci({"project": {}})
        self.assertTrue(ok)

    @patch("release_gate.gh_json")
    def test_failing(self, mock_gh):
        mock_gh.return_value = [
            {"status": "completed", "conclusion": "failure", "name": "CI"},
        ]
        ok, detail = gate_ci({"project": {}})
        self.assertFalse(ok)
        self.assertIn("failure", detail)

    @patch("release_gate.gh_json")
    def test_no_runs(self, mock_gh):
        mock_gh.return_value = []
        ok, detail = gate_ci({"project": {}})
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
        # In test env the prior tag doesn't exist, so we get initial release text
        self.assertIn("## Full Changelog", notes)

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
# bootstrap_github.py tests -- create_label with mocked gh
# ---------------------------------------------------------------------------

class TestCreateLabel(unittest.TestCase):
    """Test bootstrap_github.create_label() with mocked gh."""

    @patch("bootstrap_github.gh")
    def test_creates_label(self, mock_gh):
        mock_gh.return_value = ""
        # Should not raise
        bootstrap_github.create_label("test-label", "ff0000", "A test label")
        mock_gh.assert_called_once()
        call_args = mock_gh.call_args[0][0]
        self.assertIn("label", call_args)
        self.assertIn("create", call_args)
        self.assertIn("test-label", call_args)

    @patch("builtins.print")
    @patch("bootstrap_github.gh")
    def test_label_error_handled(self, mock_gh, mock_print):
        mock_gh.side_effect = RuntimeError("already exists")
        # Should not raise (create_label handles errors gracefully)
        bootstrap_github.create_label("existing-label", "ff0000")
        # Verify the gh call was attempted (and failed)
        mock_gh.assert_called_once()
        # Verify the warning was printed (not silently swallowed)
        mock_print.assert_called_once()
        warning_msg = mock_print.call_args[0][0]
        self.assertIn("existing-label", warning_msg)
        self.assertIn("already exists", warning_msg)


# ---------------------------------------------------------------------------
# populate_issues.py tests -- get_existing_issues with mocked gh
# ---------------------------------------------------------------------------

class TestGetExistingIssues(unittest.TestCase):
    """Test populate_issues.get_existing_issues() with mocked gh."""

    @patch("populate_issues.gh")
    def test_returns_story_ids(self, mock_gh):
        mock_gh.return_value = json.dumps([
            {"title": "US-0101: Setup project"},
            {"title": "US-0102: Add auth"},
            {"title": "Not a story"},
        ])
        existing = populate_issues.get_existing_issues()
        self.assertIn("US-0101", existing)
        self.assertIn("US-0102", existing)
        self.assertEqual(len(existing), 2)

    @patch("populate_issues.gh")
    def test_handles_empty_response(self, mock_gh):
        mock_gh.return_value = "[]"
        existing = populate_issues.get_existing_issues()
        self.assertEqual(len(existing), 0)

    @patch("populate_issues.gh")
    def test_handles_gh_failure(self, mock_gh):
        mock_gh.side_effect = RuntimeError("auth failed")
        with self.assertRaises(RuntimeError):
            populate_issues.get_existing_issues()


# ---------------------------------------------------------------------------
# sync_tracking.py tests -- find_milestone_title with mocked gh
# ---------------------------------------------------------------------------

class TestFindMilestoneTitle(unittest.TestCase):
    """Test sync_tracking.find_milestone_title() pass-through."""

    @patch("sync_tracking.find_milestone")
    def test_finds_sprint(self, mock_find):
        mock_find.return_value = {"title": "Sprint 1: Walking Skeleton", "number": 1}
        result = sync_tracking.find_milestone_title(1)
        self.assertEqual(result, "Sprint 1: Walking Skeleton")

    @patch("sync_tracking.find_milestone")
    def test_no_match_returns_none(self, mock_find):
        mock_find.return_value = None
        result = sync_tracking.find_milestone_title(1)
        self.assertIsNone(result)


# Import validate_config for direct tests
import validate_config


class TestFindMilestoneBoundary(unittest.TestCase):
    """BH-004/BH-007: Direct tests for find_milestone word-boundary regex.

    These test the actual regex in find_milestone() by mocking only at the
    system boundary (gh_json), not the function under test.
    """

    @patch("validate_config.gh_json")
    def test_sprint_1_does_not_match_sprint_10(self, mock_gh):
        """Sprint 1 search must not return 'Sprint 10: Polish'."""
        mock_gh.return_value = [
            {"title": "Sprint 10: Polish", "number": 10},
            {"title": "Sprint 1: Walking Skeleton", "number": 1},
        ]
        result = validate_config.find_milestone(1)
        self.assertIsNotNone(result)
        self.assertEqual(result["number"], 1)
        self.assertEqual(result["title"], "Sprint 1: Walking Skeleton")

    @patch("validate_config.gh_json")
    def test_sprint_10_does_not_match_sprint_1(self, mock_gh):
        """Sprint 10 search must not return 'Sprint 1: Walking Skeleton'."""
        mock_gh.return_value = [
            {"title": "Sprint 1: Walking Skeleton", "number": 1},
            {"title": "Sprint 10: Polish", "number": 10},
        ]
        result = validate_config.find_milestone(10)
        self.assertIsNotNone(result)
        self.assertEqual(result["number"], 10)

    @patch("validate_config.gh_json")
    def test_sprint_1_does_not_match_sprint_1a(self, mock_gh):
        """Sprint 1 must not match 'Sprint 1a' or 'Sprint 11'."""
        mock_gh.return_value = [
            {"title": "Sprint 1a: Special", "number": 2},
            {"title": "Sprint 11: Endgame", "number": 11},
        ]
        result = validate_config.find_milestone(1)
        self.assertIsNone(result)

    @patch("validate_config.gh_json")
    def test_sprint_100_does_not_match_sprint_10(self, mock_gh):
        mock_gh.return_value = [
            {"title": "Sprint 10: Polish", "number": 10},
        ]
        result = validate_config.find_milestone(100)
        self.assertIsNone(result)

    @patch("validate_config.gh_json")
    def test_no_milestones_returns_none(self, mock_gh):
        mock_gh.return_value = []
        result = validate_config.find_milestone(1)
        self.assertIsNone(result)

    @patch("validate_config.gh_json")
    def test_non_list_response_returns_none(self, mock_gh):
        mock_gh.return_value = {"error": "not found"}
        result = validate_config.find_milestone(1)
        self.assertIsNone(result)


class TestGetLinkedPR(unittest.TestCase):
    """P1-02: Test get_linked_pr matches correct story ID."""

    @patch("sync_tracking.gh")
    def test_matches_correct_story_id(self, mock_gh):
        """Fallback search should match only the requested story ID."""
        mock_gh.side_effect = RuntimeError("timeline API unavailable")
        all_prs = [
            {"number": 10, "state": "MERGED", "headRefName": "sprint-1/us-0099-other", "mergedAt": "2026-03-01"},
            {"number": 20, "state": "OPEN", "headRefName": "sprint-1/us-0001-setup", "mergedAt": None},
        ]
        result = sync_tracking.get_linked_pr(1, story_id="US-0001", all_prs=all_prs)
        self.assertIsNotNone(result)
        self.assertEqual(result["number"], 20)

    @patch("sync_tracking.gh")
    def test_does_not_match_wrong_story(self, mock_gh):
        """Should return None if no PR matches the requested story ID."""
        mock_gh.side_effect = RuntimeError("timeline API unavailable")
        all_prs = [
            {"number": 10, "state": "OPEN", "headRefName": "sprint-1/us-0099-other", "mergedAt": None},
        ]
        result = sync_tracking.get_linked_pr(1, story_id="US-0001", all_prs=all_prs)
        self.assertIsNone(result)


# ---------------------------------------------------------------------------
# update_burndown.py tests -- extract_sp
# ---------------------------------------------------------------------------

class TestExtractSP(unittest.TestCase):
    """Test shared extract_sp() via update_burndown (which imports from validate_config)."""

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

    def test_sp_from_analytics_table_format(self):
        """P1-05: Ensure | N SP | format (used by analytics) also works."""
        issue = {"labels": [], "body": "| 5 SP |"}
        self.assertEqual(update_burndown.extract_sp(issue), 5)

    def test_sp_label_with_space(self):
        """P5-24: 'sp: 3' (with space) should extract 3."""
        issue = {"labels": [{"name": "sp: 3"}], "body": ""}
        self.assertEqual(update_burndown.extract_sp(issue), 3)

    def test_sp_label_uppercase(self):
        """P5-24: 'SP:3' (uppercase) should extract 3."""
        issue = {"labels": [{"name": "SP:3"}], "body": ""}
        self.assertEqual(update_burndown.extract_sp(issue), 3)

    def test_sp_from_story_points_table(self):
        issue = {"labels": [], "body": "| Story Points | 13 |"}
        self.assertEqual(update_burndown.extract_sp(issue), 13)


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


# ---------------------------------------------------------------------------
# check_status.py tests -- drift detection
# ---------------------------------------------------------------------------

class TestCheckBranchDivergence(unittest.TestCase):
    """Test check_status.check_branch_divergence() with mocked gh_json."""

    @patch("check_status.gh_json")
    def test_no_branches(self, mock_gh):
        report, actions = check_status.check_branch_divergence(
            "owner/repo", "main", [],
        )
        self.assertEqual(report, [])
        self.assertEqual(actions, [])
        mock_gh.assert_not_called()

    @patch("check_status.gh_json")
    def test_low_divergence_ignored(self, mock_gh):
        mock_gh.return_value = {"behind_by": 3, "ahead_by": 5}
        report, actions = check_status.check_branch_divergence(
            "owner/repo", "main", ["feat/small"],
        )
        self.assertEqual(report, [])
        self.assertEqual(actions, [])

    @patch("check_status.gh_json")
    def test_medium_divergence(self, mock_gh):
        mock_gh.return_value = {"behind_by": 15, "ahead_by": 8}
        report, actions = check_status.check_branch_divergence(
            "owner/repo", "main", ["feat/medium"],
        )
        self.assertEqual(len(report), 1)
        self.assertIn("MEDIUM", report[0])
        self.assertIn("15", report[0])
        self.assertEqual(actions, [])

    @patch("check_status.gh_json")
    def test_high_divergence(self, mock_gh):
        mock_gh.return_value = {"behind_by": 25, "ahead_by": 10}
        report, actions = check_status.check_branch_divergence(
            "owner/repo", "main", ["feat/big"],
        )
        self.assertEqual(len(report), 1)
        self.assertIn("HIGH", report[0])
        self.assertEqual(len(actions), 1)
        self.assertIn("25 behind", actions[0])

    @patch("check_status.gh_json")
    def test_multiple_branches(self, mock_gh):
        mock_gh.side_effect = [
            {"behind_by": 5, "ahead_by": 2},   # low — skipped
            {"behind_by": 25, "ahead_by": 10},  # high
        ]
        report, actions = check_status.check_branch_divergence(
            "owner/repo", "main", ["feat/ok", "feat/stale"],
        )
        self.assertEqual(len(report), 1)
        self.assertIn("feat/stale", report[0])

    @patch("check_status.gh_json")
    def test_api_error_handled(self, mock_gh):
        mock_gh.side_effect = RuntimeError("API error")
        report, actions = check_status.check_branch_divergence(
            "owner/repo", "main", ["feat/broken"],
        )
        # Error is now reported (not silently swallowed)
        self.assertEqual(len(report), 1)
        self.assertIn("skipped", report[0])
        self.assertIn("feat/broken", report[0])
        self.assertEqual(actions, [])


class TestCheckDirectPushes(unittest.TestCase):
    """Test check_status.check_direct_pushes() with mocked gh_json."""

    @patch("check_status.gh_json")
    def test_no_direct_pushes(self, mock_gh):
        mock_gh.return_value = []
        report, actions = check_status.check_direct_pushes(
            "owner/repo", "main", "2026-03-01T00:00:00Z",
        )
        self.assertEqual(report, [])
        self.assertEqual(actions, [])

    @patch("check_status.gh_json")
    def test_direct_pushes_found(self, mock_gh):
        mock_gh.return_value = [
            {"sha": "abc12345", "message": "quick fix",
             "author": "someone", "date": "2026-03-10T12:00:00Z"},
        ]
        report, actions = check_status.check_direct_pushes(
            "owner/repo", "main", "2026-03-01T00:00:00Z",
        )
        self.assertTrue(len(report) >= 1)
        self.assertIn("1 direct push", report[0])
        self.assertEqual(len(actions), 1)
        self.assertIn("pushed directly", actions[0])

    @patch("check_status.gh_json")
    def test_multiple_pushes_capped(self, mock_gh):
        mock_gh.return_value = [
            {"sha": f"sha{i}", "message": f"fix {i}",
             "author": "dev", "date": "2026-03-10"}
            for i in range(5)
        ]
        report, actions = check_status.check_direct_pushes(
            "owner/repo", "main", "2026-03-01T00:00:00Z",
        )
        self.assertIn("5 direct push", report[0])
        # Shows at most 3 individual commits
        commit_lines = [r for r in report if r.startswith("    ")]
        self.assertEqual(len(commit_lines), 3)

    @patch("check_status.gh_json")
    def test_api_error_handled(self, mock_gh):
        mock_gh.side_effect = RuntimeError("API error")
        report, actions = check_status.check_direct_pushes(
            "owner/repo", "main", "2026-03-01T00:00:00Z",
        )
        # Error is now reported (not silently swallowed)
        self.assertEqual(len(report), 1)
        self.assertIn("skipped", report[0])
        self.assertEqual(actions, [])


# ---------------------------------------------------------------------------
# P2-04: sync_tracking.py tests -- sync_one, create_from_issue
# ---------------------------------------------------------------------------

class TestSyncOne(unittest.TestCase):
    """Test sync_tracking.sync_one() status reconciliation."""

    def test_closed_issue_updates_status(self):
        tf = sync_tracking.TF(
            path=Path("/tmp/test.md"), story="US-0001",
            status="dev", sprint=1,
        )
        issue = {"state": "closed", "labels": [], "closedAt": "2026-03-10T12:00:00Z", "number": 1}
        changes = sync_tracking.sync_one(tf, issue, None, 1)
        self.assertEqual(tf.status, "done")
        self.assertTrue(any("done" in c for c in changes))

    def test_label_sync_updates_status(self):
        tf = sync_tracking.TF(
            path=Path("/tmp/test.md"), story="US-0001",
            status="todo", sprint=1,
        )
        issue = {"state": "open", "labels": [{"name": "kanban:review"}], "number": 1}
        changes = sync_tracking.sync_one(tf, issue, None, 1)
        self.assertEqual(tf.status, "review")
        self.assertTrue(len(changes) > 0)

    def test_pr_number_updated(self):
        tf = sync_tracking.TF(
            path=Path("/tmp/test.md"), story="US-0001",
            status="dev", pr_number="", sprint=1, issue_number="1",
        )
        issue = {"state": "open", "labels": [{"name": "kanban:dev"}], "number": 1}
        pr = {"number": 42, "state": "open", "merged": False}
        changes = sync_tracking.sync_one(tf, issue, pr, 1)
        self.assertEqual(tf.pr_number, "42")

    def test_no_changes_when_in_sync(self):
        tf = sync_tracking.TF(
            path=Path("/tmp/test.md"), story="US-0001",
            status="todo", sprint=1, issue_number="5",
        )
        issue = {"state": "open", "labels": [], "number": 5}
        changes = sync_tracking.sync_one(tf, issue, None, 1)
        self.assertEqual(changes, [])


class TestCreateFromIssue(unittest.TestCase):
    """Test sync_tracking.create_from_issue() creates valid tracking file."""

    def test_basic_creation(self):
        issue = {
            "title": "US-0001: Setup CI",
            "number": 1,
            "state": "open",
            "labels": [],
            "closedAt": None,
        }
        tf, changes = sync_tracking.create_from_issue(
            issue, sprint=1, d=Path("/tmp"), pr=None,
        )
        self.assertEqual(tf.story, "US-0001")
        self.assertEqual(tf.title, "Setup CI")
        self.assertEqual(tf.sprint, 1)
        self.assertEqual(tf.status, "todo")
        self.assertEqual(tf.issue_number, "1")
        self.assertTrue(len(changes) > 0)

    def test_creation_with_pr(self):
        issue = {
            "title": "US-0002: Add auth",
            "number": 2,
            "state": "open",
            "labels": [{"name": "kanban:dev"}],
            "closedAt": None,
        }
        pr = {"number": 10, "state": "open", "merged": False}
        tf, changes = sync_tracking.create_from_issue(
            issue, sprint=1, d=Path("/tmp"), pr=pr,
        )
        self.assertEqual(tf.pr_number, "10")
        self.assertEqual(tf.status, "dev")

    def test_creation_for_closed_issue(self):
        issue = {
            "title": "US-0003: Fix bug",
            "number": 3,
            "state": "closed",
            "labels": [],
            "closedAt": "2026-03-09T10:00:00Z",
        }
        tf, changes = sync_tracking.create_from_issue(
            issue, sprint=2, d=Path("/tmp"), pr=None,
        )
        self.assertEqual(tf.status, "done")
        self.assertEqual(tf.completed, "2026-03-09")


# ---------------------------------------------------------------------------
# P2-05: update_burndown.py tests -- write_burndown, update_sprint_status
# ---------------------------------------------------------------------------

class TestWriteBurndown(unittest.TestCase):
    """Test update_burndown.write_burndown() output format."""

    def test_creates_burndown_file(self):
        import tempfile
        from datetime import datetime, timezone
        with tempfile.TemporaryDirectory() as tmpdir:
            sprints_dir = Path(tmpdir)
            rows = [
                {"story_id": "US-0001", "short_title": "Setup", "sp": 3,
                 "status": "done", "closed": "2026-03-09"},
                {"story_id": "US-0002", "short_title": "Auth", "sp": 5,
                 "status": "dev", "closed": "\u2014"},
            ]
            now = datetime(2026, 3, 10, 12, 0, tzinfo=timezone.utc)
            path = update_burndown.write_burndown(1, rows, now, sprints_dir)
            self.assertTrue(path.exists())
            content = path.read_text()
            self.assertIn("Sprint 1 Burndown", content)
            self.assertIn("Planned: 8 SP", content)
            self.assertIn("Completed: 3 SP", content)
            self.assertIn("US-0001", content)
            self.assertIn("US-0002", content)

    def test_zero_sp_handled(self):
        import tempfile
        from datetime import datetime, timezone
        with tempfile.TemporaryDirectory() as tmpdir:
            rows = [
                {"story_id": "US-0001", "short_title": "Spike", "sp": 0,
                 "status": "done", "closed": "2026-03-09"},
            ]
            now = datetime(2026, 3, 10, 12, 0, tzinfo=timezone.utc)
            path = update_burndown.write_burndown(1, rows, now, Path(tmpdir))
            content = path.read_text()
            self.assertIn("Progress: 0%", content)


class TestUpdateSprintStatus(unittest.TestCase):
    """Test update_burndown.update_sprint_status() patches SPRINT-STATUS.md."""

    def test_patches_active_stories_section(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            status_file = Path(tmpdir) / "SPRINT-STATUS.md"
            status_file.write_text(
                "# Sprint Status\n\n## Active Stories\n\n"
                "| Story | Status | Assignee | PR |\n"
                "|-------|--------|----------|----|"
                "\n| old | old | old | old |\n\n## Other\n",
                encoding="utf-8",
            )
            rows = [
                {"story_id": "US-0001", "short_title": "Setup", "sp": 3,
                 "status": "done", "closed": "2026-03-09",
                 "assignee": "Ren", "pr": "#1"},
            ]
            update_burndown.update_sprint_status(1, rows, Path(tmpdir))
            content = status_file.read_text()
            self.assertIn("US-0001", content)
            self.assertIn("Ren", content)
            self.assertNotIn("old", content)
            # Other section preserved
            self.assertIn("## Other", content)

    def test_appends_when_section_missing(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            status_file = Path(tmpdir) / "SPRINT-STATUS.md"
            status_file.write_text("# Sprint Status\n", encoding="utf-8")
            rows = [
                {"story_id": "US-0001", "short_title": "Setup", "sp": 3,
                 "status": "todo", "closed": "\u2014"},
            ]
            update_burndown.update_sprint_status(1, rows, Path(tmpdir))
            content = status_file.read_text()
            self.assertIn("## Active Stories", content)
            self.assertIn("US-0001", content)

    def test_skips_missing_file(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            rows = [{"story_id": "X", "short_title": "X", "sp": 0,
                      "status": "todo", "closed": ""}]
            # Should not raise
            update_burndown.update_sprint_status(1, rows, Path(tmpdir))


class TestKanbanFromLabels(unittest.TestCase):
    """BH3-03: kanban_from_labels validates against allowed states."""

    def test_valid_state_returned(self):
        issue = {"labels": [{"name": "kanban:review"}], "state": "open"}
        self.assertEqual(validate_config.kanban_from_labels(issue), "review")

    def test_invalid_state_falls_back_to_todo(self):
        issue = {"labels": [{"name": "kanban:garbage"}], "state": "open"}
        self.assertEqual(validate_config.kanban_from_labels(issue), "todo")

    def test_invalid_state_closed_falls_back_to_done(self):
        issue = {"labels": [{"name": "kanban:garbage"}], "state": "closed"}
        self.assertEqual(validate_config.kanban_from_labels(issue), "done")

    def test_no_kanban_label_open(self):
        issue = {"labels": [], "state": "open"}
        self.assertEqual(validate_config.kanban_from_labels(issue), "todo")

    def test_no_kanban_label_closed(self):
        issue = {"labels": [], "state": "closed"}
        self.assertEqual(validate_config.kanban_from_labels(issue), "done")


# ---------------------------------------------------------------------------
# P5-17: check_status helper tests (_first_error, _hours, _age)
# ---------------------------------------------------------------------------


class TestFirstError(unittest.TestCase):
    """P5-17: _first_error extracts first error line from CI logs."""

    def test_finds_error_keyword(self):
        log = "step 1: ok\nstep 2: ERROR: foo failed\nstep 3: ok"
        result = check_status._first_error(log)
        self.assertIn("foo failed", result)

    def test_strips_ansi_codes(self):
        log = "\x1b[31mERROR: something broke\x1b[0m"
        result = check_status._first_error(log)
        self.assertNotIn("\x1b", result)
        self.assertIn("something broke", result)

    def test_truncates_long_lines(self):
        log = "ERROR: " + "x" * 200
        result = check_status._first_error(log)
        self.assertTrue(result.endswith("..."))
        self.assertLessEqual(len(result), 120)

    def test_returns_empty_on_no_match(self):
        log = "all good\nno problems here"
        self.assertEqual(check_status._first_error(log), "")

    def test_matches_failed_keyword(self):
        log = "test_foo FAILED"
        self.assertIn("FAILED", check_status._first_error(log))

    def test_matches_panicked(self):
        log = "thread 'main' panicked at 'assertion failed'"
        self.assertIn("panicked", check_status._first_error(log))


class TestHours(unittest.TestCase):
    """P5-17: _hours parses ISO 8601 timestamps."""

    def test_empty_string_returns_zero(self):
        self.assertEqual(check_status._hours(""), 0.0)

    def test_recent_iso_returns_small_hours(self):
        from datetime import datetime, timezone, timedelta
        recent = (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat()
        h = check_status._hours(recent)
        self.assertAlmostEqual(h, 0.5, delta=0.1)

    def test_zulu_suffix_parsed(self):
        from datetime import datetime, timezone, timedelta
        ts = (datetime.now(timezone.utc) - timedelta(hours=3)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        self.assertAlmostEqual(check_status._hours(ts), 3.0, delta=0.1)

    def test_invalid_format_returns_zero(self):
        self.assertEqual(check_status._hours("not-a-date"), 0.0)


class TestAge(unittest.TestCase):
    """P5-17: _age formats time deltas as human-readable strings."""

    def test_minutes(self):
        from datetime import datetime, timezone, timedelta
        ts = (datetime.now(timezone.utc) - timedelta(minutes=45)).isoformat()
        self.assertTrue(check_status._age(ts).endswith("m"))

    def test_hours(self):
        from datetime import datetime, timezone, timedelta
        ts = (datetime.now(timezone.utc) - timedelta(hours=5)).isoformat()
        self.assertIn("h", check_status._age(ts))

    def test_days(self):
        from datetime import datetime, timezone, timedelta
        ts = (datetime.now(timezone.utc) - timedelta(days=3)).isoformat()
        self.assertIn("d", check_status._age(ts))


# ---------------------------------------------------------------------------
# P5-10: check_milestone tests
# ---------------------------------------------------------------------------


class TestCheckMilestone(unittest.TestCase):
    """P5-10: check_milestone with mocked gh_json."""

    def _mock_gh_json(self, milestones=None, issues=None):
        """Return a side_effect function for gh_json calls."""
        call_count = [0]
        def _side_effect(args):
            call_count[0] += 1
            if call_count[0] == 1:
                return milestones if milestones is not None else []
            return issues if issues is not None else []
        return _side_effect

    def test_happy_path_with_sp(self):
        milestones = [
            {"title": "Sprint 1", "open_issues": 2, "closed_issues": 3},
        ]
        issues = [
            {"state": "closed", "labels": [{"name": "sp:3"}], "body": ""},
            {"state": "closed", "labels": [{"name": "sp:5"}], "body": ""},
            {"state": "closed", "labels": [{"name": "sp:2"}], "body": ""},
            {"state": "open", "labels": [{"name": "sp:8"}], "body": ""},
            {"state": "open", "labels": [{"name": "sp:5"}], "body": ""},
        ]
        with patch.object(
            check_status, "gh_json",
            side_effect=self._mock_gh_json(milestones, issues),
        ):
            report, actions = check_status.check_milestone(1)
        self.assertTrue(any("3/5" in line for line in report))
        self.assertTrue(any("SP" in line for line in report))

    def test_no_milestone_found(self):
        with patch.object(
            check_status, "gh_json", return_value=[],
        ):
            report, actions = check_status.check_milestone(99)
        self.assertTrue(any("no milestone" in line for line in report))

    def test_zero_total_stories(self):
        milestones = [
            {"title": "Sprint 1", "open_issues": 0, "closed_issues": 0},
        ]
        with patch.object(
            check_status, "gh_json",
            side_effect=self._mock_gh_json(milestones, []),
        ):
            report, actions = check_status.check_milestone(1)
        self.assertTrue(any("0/0" in line for line in report))
        self.assertTrue(any("0%" in line for line in report))

    def test_api_error_graceful(self):
        with patch.object(
            check_status, "gh_json", side_effect=RuntimeError("oops"),
        ):
            report, actions = check_status.check_milestone(1)
        self.assertTrue(any("could not query" in line for line in report))


# ---------------------------------------------------------------------------
# P5-11: sync_tracking read_tf / write_tf / slug tests
# ---------------------------------------------------------------------------


class TestSyncTrackingIO(unittest.TestCase):
    """P5-11: round-trip and edge case tests for tracking file I/O."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="sync-tf-")
        self.tmp = Path(self.tmpdir)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_roundtrip(self):
        tf = sync_tracking.TF(
            path=self.tmp / "test.md",
            story="US-101", title="Test story",
            sprint=2, implementer="alice", reviewer="bob",
            status="dev", branch="sprint-2/test",
            pr_number="42", issue_number="7",
            started="2026-01-01", completed="",
            body_text="Some body text here.",
        )
        sync_tracking.write_tf(tf)
        recovered = sync_tracking.read_tf(self.tmp / "test.md")
        self.assertEqual(recovered.story, "US-101")
        self.assertEqual(recovered.title, "Test story")
        self.assertEqual(recovered.sprint, 2)
        self.assertEqual(recovered.implementer, "alice")
        self.assertEqual(recovered.reviewer, "bob")
        self.assertEqual(recovered.status, "dev")
        self.assertEqual(recovered.pr_number, "42")
        self.assertEqual(recovered.issue_number, "7")
        self.assertIn("Some body text", recovered.body_text)

    def test_missing_fields_default(self):
        p = self.tmp / "empty.md"
        p.write_text("---\nstory: US-999\n---\n", encoding="utf-8")
        tf = sync_tracking.read_tf(p)
        self.assertEqual(tf.story, "US-999")
        self.assertEqual(tf.sprint, 0)
        self.assertEqual(tf.status, "todo")
        self.assertEqual(tf.implementer, "")

    def test_no_frontmatter(self):
        p = self.tmp / "plain.md"
        p.write_text("Just plain text\n", encoding="utf-8")
        tf = sync_tracking.read_tf(p)
        self.assertEqual(tf.story, "")
        self.assertIn("plain text", tf.body_text)

    def test_colon_in_title(self):
        tf = sync_tracking.TF(
            path=self.tmp / "colon.md",
            story="US-50", title="Fix: colon edge case",
        )
        sync_tracking.write_tf(tf)
        recovered = sync_tracking.read_tf(self.tmp / "colon.md")
        self.assertEqual(recovered.title, "Fix: colon edge case")


class TestSlugFromTitle(unittest.TestCase):
    """P5-11: slug generation edge cases."""

    def test_basic_slug(self):
        self.assertEqual(
            sync_tracking.slug_from_title("Add User Auth"),
            "add-user-auth",
        )

    def test_special_chars_removed(self):
        slug = sync_tracking.slug_from_title("Fix: bug #42 (urgent!)")
        self.assertNotIn("#", slug)
        self.assertNotIn("!", slug)
        self.assertNotIn("(", slug)

    def test_empty_title(self):
        self.assertEqual(sync_tracking.slug_from_title(""), "untitled")

    def test_all_special_chars(self):
        self.assertEqual(sync_tracking.slug_from_title("!!!"), "untitled")

    def test_similar_titles_produce_different_slugs(self):
        s1 = sync_tracking.slug_from_title("Add auth")
        s2 = sync_tracking.slug_from_title("Add auth module")
        self.assertNotEqual(s1, s2)


# ---------------------------------------------------------------------------
# P5-13: main() entry point tests (error paths)
# ---------------------------------------------------------------------------


class TestSyncTrackingMainArgParsing(unittest.TestCase):
    """P5-13: sync_tracking.main() rejects bad args."""

    def test_no_args_exits_2(self):
        with patch("sys.argv", ["sync_tracking.py"]):
            with self.assertRaises(SystemExit) as ctx:
                sync_tracking.main()
            self.assertEqual(ctx.exception.code, 2)

    def test_non_numeric_exits_2(self):
        with patch("sys.argv", ["sync_tracking.py", "abc"]):
            with self.assertRaises(SystemExit) as ctx:
                sync_tracking.main()
            self.assertEqual(ctx.exception.code, 2)

    def test_help_exits_0(self):
        with patch("sys.argv", ["sync_tracking.py", "--help"]):
            with self.assertRaises(SystemExit) as ctx:
                sync_tracking.main()
            self.assertEqual(ctx.exception.code, 0)


class TestCheckStatusMainArgParsing(unittest.TestCase):
    """P5-13: check_status.main() help flag."""

    def test_help_exits_0(self):
        with patch("sys.argv", ["check_status.py", "--help"]):
            with self.assertRaises(SystemExit) as ctx:
                check_status.main()
            self.assertEqual(ctx.exception.code, 0)


class TestCommitMainArgParsing(unittest.TestCase):
    """P5-13: commit.main() error paths."""

    def test_no_args_exits_2(self):
        with patch("sys.argv", ["commit.py"]):
            with self.assertRaises(SystemExit) as ctx:
                commit.main()
            self.assertEqual(ctx.exception.code, 2)

    def test_help_exits_0(self):
        with patch("sys.argv", ["commit.py", "--help"]):
            with self.assertRaises(SystemExit) as ctx:
                commit.main()
            self.assertEqual(ctx.exception.code, 0)


class TestSprintAnalyticsMainArgParsing(unittest.TestCase):
    """P5-13: sprint_analytics.main() help flag."""

    def test_help_exits_0(self):
        with patch("sys.argv", ["sprint_analytics.py", "--help"]):
            with self.assertRaises(SystemExit) as ctx:
                sprint_analytics.main()
            self.assertEqual(ctx.exception.code, 0)


# ---------------------------------------------------------------------------
# P5-09: FakeGitHub flag enforcement
# ---------------------------------------------------------------------------


class TestFakeGitHubFlagEnforcement(unittest.TestCase):
    """P5-09: FakeGitHub raises NotImplementedError on unknown flags."""

    def setUp(self):
        self.fake = FakeGitHub()

    def test_unknown_flag_on_issue_list_raises(self):
        """An unregistered flag like --assignee raises NotImplementedError."""
        with self.assertRaises(NotImplementedError) as ctx:
            self.fake.handle(["issue", "list", "--assignee", "jonr"])
        self.assertIn("assignee", str(ctx.exception))

    def test_known_flags_accepted(self):
        """Registered flags like --state, --json don't raise."""
        result = self.fake.handle([
            "issue", "list", "--state", "open", "--json", "number,title",
        ])
        self.assertEqual(result.returncode, 0)

    def test_noop_flags_accepted(self):
        """Flags in _ACCEPTED_NOOP_FLAGS (--paginate, --jq) are silently allowed."""
        result = self.fake.handle([
            "issue", "list", "--state", "all", "--jq", ".[].title",
        ])
        self.assertEqual(result.returncode, 0)

    def test_unknown_flag_on_pr_list_raises(self):
        with self.assertRaises(NotImplementedError):
            self.fake.handle(["pr", "list", "--search", "is:draft"])

    def test_unknown_flag_on_release_create_raises(self):
        with self.assertRaises(NotImplementedError):
            self.fake.handle(["release", "create", "v1.0.0", "--prerelease"])


if __name__ == "__main__":
    unittest.main()
