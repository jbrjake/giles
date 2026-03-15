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

from fake_github import FakeGitHub, make_patched_subprocess

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

    def test_multiline_array_in_release_section(self):
        """P7-07/P7-13: Multiline array in [release] must not corrupt next section."""
        toml_content = (
            '[release]\n'
            'gate_checks = [\n'
            '  "check1",\n'
            '  "check2"\n'
            ']\n'
            '\n'
            '[other]\n'
            'key = 1\n'
        )
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".toml", delete=False,
        ) as f:
            f.write(toml_content)
            path = Path(f.name)
        try:
            write_version_to_toml("2.0.0", path)
            text = path.read_text()
            self.assertIn('version = "2.0.0"', text)
            # [other] section must still be intact
            self.assertIn('[other]', text)
            self.assertIn('key = 1', text)
            # Version should be in [release], not [other]
            other_idx = text.index('[other]')
            version_idx = text.index('version = "2.0.0"')
            self.assertLess(version_idx, other_idx)
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

    @patch("release_gate.gh_json")
    @patch("release_gate.warn_if_at_limit")
    def test_limit_hit_fails_gate(self, mock_warn, mock_gh):
        """P7-03/P7-12: When 500 PRs returned, gate fails due to truncation risk."""
        mock_gh.return_value = [
            {"number": i, "title": f"PR {i}", "milestone": None}
            for i in range(500)
        ]
        ok, detail = gate_prs("Sprint 1")
        self.assertFalse(ok)
        self.assertIn("truncated", detail)


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
# bootstrap_github.py tests -- _collect_sprint_numbers
# ---------------------------------------------------------------------------

class TestCollectSprintNumbers(unittest.TestCase):
    """P7-06: _collect_sprint_numbers warns on silent fallback to sprint 1."""

    def test_heading_extraction(self):
        """Extracts sprint numbers from ### Sprint N: headings."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False
        ) as f:
            f.write("### Sprint 2: Core\n### Sprint 3: Polish\n")
            f.flush()
            result = bootstrap_github._collect_sprint_numbers([f.name])
        Path(f.name).unlink()
        self.assertEqual(result, {2, 3})

    def test_filename_fallback(self):
        """Falls back to filename number when no headings found."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", prefix="milestone-5-",
            delete=False
        ) as f:
            f.write("No sprint headings here.\n")
            f.flush()
            result = bootstrap_github._collect_sprint_numbers([f.name])
        Path(f.name).unlink()
        self.assertEqual(result, {5})

    def test_no_heading_no_number_warns(self):
        """P7-06: No heading + no digits in filename → warns + defaults to 1."""
        import io, contextlib
        td = tempfile.mkdtemp()
        fpath = Path(td) / "backlog.md"
        fpath.write_text("No sprint headings, no number in name.\n")
        captured = io.StringIO()
        with contextlib.redirect_stderr(captured):
            result = bootstrap_github._collect_sprint_numbers([str(fpath)])
        fpath.unlink()
        Path(td).rmdir()
        self.assertEqual(result, {1})
        self.assertIn("defaulting to sprint 1", captured.getvalue())


# ---------------------------------------------------------------------------
# populate_issues.py tests -- format_issue_body
# ---------------------------------------------------------------------------

class TestFormatIssueBody(unittest.TestCase):
    """P7-16: Direct tests for populate_issues.format_issue_body()."""

    def test_full_story(self):
        """Body includes AC checkboxes, epic, saga, dependencies."""
        story = populate_issues.Story(
            story_id="US-0042", title="Add Login",
            saga="auth", sp=3, priority="high", sprint=1,
            user_story="As a user I want to log in.",
            acceptance_criteria=["Login form renders", "Session created"],
            epic="E-01: Authentication",
            blocked_by="US-0041", blocks="US-0043",
            test_cases="TC-01, TC-02",
        )
        body = populate_issues.format_issue_body(story)
        self.assertIn("- [ ] `AC-01`: Login form renders", body)
        self.assertIn("- [ ] `AC-02`: Session created", body)
        self.assertIn("**Epic:** E-01: Authentication", body)
        self.assertIn("**Saga:** auth", body)
        self.assertIn("**Blocked by:** US-0041", body)
        self.assertIn("**Blocks:** US-0043", body)
        self.assertIn("**Test cases:** TC-01, TC-02", body)
        self.assertIn("## User Story", body)

    def test_minimal_story(self):
        """Minimal story — no AC, no epic, no deps."""
        story = populate_issues.Story(
            story_id="US-0001", title="Stub",
            saga="core", sp=1, priority="low", sprint=1,
        )
        body = populate_issues.format_issue_body(story)
        self.assertIn("US-0001", body)
        self.assertIn("Stub", body)
        self.assertNotIn("## Acceptance Criteria", body)
        self.assertNotIn("## Dependencies", body)
        self.assertNotIn("## User Story", body)


class TestCreateIssueMissingMilestone(unittest.TestCase):
    """P7-18: create_issue when sprint has no milestone mapping."""

    @patch("populate_issues.gh")
    def test_missing_milestone_still_creates_issue(self, mock_gh):
        """Issue is created without --milestone when sprint not in mapping."""
        mock_gh.return_value = "https://github.com/test/repo/issues/1"
        story = populate_issues.Story(
            story_id="US-9999", title="Orphan Story",
            saga="core", sp=2, priority="medium", sprint=99,
        )
        # Sprint 99 has no entry in either dict
        result = populate_issues.create_issue(
            story, milestone_numbers={}, milestone_titles={},
        )
        self.assertTrue(result)
        # Verify --milestone was NOT passed
        call_args = mock_gh.call_args[0][0]
        self.assertNotIn("--milestone", call_args)


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
# populate_issues.py tests -- _infer_sprint_number
# ---------------------------------------------------------------------------

class TestInferSprintNumber(unittest.TestCase):
    """P7-10: Direct tests for populate_issues._infer_sprint_number."""

    def test_heading_match(self):
        """Heading-anchored ### Sprint N takes priority."""
        result = populate_issues._infer_sprint_number(
            Path("milestone-2.md"),
            "# Milestone 2\n\n### Sprint 2: Core\nThis builds on Sprint 1.",
        )
        self.assertEqual(result, 2)

    def test_prose_only_falls_through_to_filename(self):
        """P7-02: Prose mention of Sprint N should NOT match; fall back to filename."""
        result = populate_issues._infer_sprint_number(
            Path("milestone-3.md"),
            "No heading here\nRefers to Sprint 1 work.",
        )
        self.assertEqual(result, 3)  # from filename, not prose

    def test_filename_with_number(self):
        """Filename digits used as fallback when no heading present."""
        result = populate_issues._infer_sprint_number(
            Path("milestone-5.md"),
            "No sprint headings in this file.",
        )
        self.assertEqual(result, 5)

    def test_filename_without_number_defaults_to_1(self):
        """No heading, no digits in filename → default to 1."""
        result = populate_issues._infer_sprint_number(
            Path("backlog.md"),
            "No sprint headings here either.",
        )
        self.assertEqual(result, 1)

    def test_content_parameter_passthrough(self):
        """Content parameter prevents file I/O — uses provided text."""
        result = populate_issues._infer_sprint_number(
            Path("nonexistent-file.md"),
            "### Sprint 4: Final\nStory details.",
        )
        self.assertEqual(result, 4)

    def test_multiple_headings_returns_first(self):
        """Multiple sprint headings — returns the first one found."""
        result = populate_issues._infer_sprint_number(
            Path("multi.md"),
            "### Sprint 3: Early\n\n### Sprint 4: Late\n",
        )
        self.assertEqual(result, 3)


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
# P6-05: get_linked_pr timeline API + P6-06: word-boundary matching
# ---------------------------------------------------------------------------


class TestGetLinkedPrTimeline(unittest.TestCase):
    """P6-05: Test get_linked_pr primary path via timeline API."""

    def setUp(self):
        self.fake = FakeGitHub()

    def test_timeline_returns_linked_pr(self):
        """Timeline API returns a linked PR -- should use it, not fallback."""
        self.fake.timeline_events[5] = [
            {
                "source": {
                    "issue": {
                        "number": 42,
                        "state": "open",
                        "pull_request": {"merged_at": None},
                    }
                }
            }
        ]
        patched = make_patched_subprocess(self.fake)
        with patch("subprocess.run", patched):
            result = sync_tracking.get_linked_pr(
                5, story_id="US-01", all_prs=[]
            )
        self.assertIsNotNone(result)
        self.assertEqual(result["number"], 42)
        self.assertFalse(result["merged"])

    def test_timeline_returns_merged_pr(self):
        """Timeline API returns a merged PR -- merged flag should be True."""
        self.fake.timeline_events[7] = [
            {
                "source": {
                    "issue": {
                        "number": 99,
                        "state": "closed",
                        "pull_request": {"merged_at": "2026-03-10T12:00:00Z"},
                    }
                }
            }
        ]
        patched = make_patched_subprocess(self.fake)
        with patch("subprocess.run", patched):
            result = sync_tracking.get_linked_pr(
                7, story_id="US-02", all_prs=[]
            )
        self.assertIsNotNone(result)
        self.assertEqual(result["number"], 99)
        self.assertTrue(result["merged"])

    def test_timeline_no_match_falls_back(self):
        """Timeline has events but no PR link -- should fall back to branch search."""
        # Events with no pull_request field -> timeline returns "null"
        self.fake.timeline_events[3] = [
            {"source": {"issue": {"number": 10, "state": "open"}}}
        ]
        patched = make_patched_subprocess(self.fake)
        all_prs = [
            {"number": 50, "state": "OPEN", "headRefName": "sprint-1/US-03-feat", "mergedAt": None},
        ]
        with patch("subprocess.run", patched):
            result = sync_tracking.get_linked_pr(
                3, story_id="US-03", all_prs=all_prs
            )
        self.assertIsNotNone(result)
        self.assertEqual(result["number"], 50)

    def test_timeline_api_error_falls_back(self):
        """No timeline events registered -- FakeGitHub errors, fallback fires."""
        # Don't register any timeline events for issue 8
        patched = make_patched_subprocess(self.fake)
        all_prs = [
            {"number": 60, "state": "OPEN", "headRefName": "sprint-1/US-04-work", "mergedAt": None},
        ]
        with patch("subprocess.run", patched):
            result = sync_tracking.get_linked_pr(
                8, story_id="US-04", all_prs=all_prs
            )
        self.assertIsNotNone(result)
        self.assertEqual(result["number"], 60)


class TestGetLinkedPrWordBoundary(unittest.TestCase):
    """P6-06: Fallback branch matching must use word boundaries."""

    @patch("sync_tracking.gh")
    def test_pr_link_no_substring_match(self, mock_gh):
        """US-01 must NOT match branch containing US-010."""
        mock_gh.side_effect = RuntimeError("timeline API unavailable")
        all_prs = [
            {"number": 30, "state": "OPEN", "headRefName": "sprint-1/US-010-feature", "mergedAt": None},
        ]
        result = sync_tracking.get_linked_pr(1, story_id="US-01", all_prs=all_prs)
        self.assertIsNone(result)

    @patch("sync_tracking.gh")
    def test_pr_link_exact_match(self, mock_gh):
        """US-01 should match branch sprint-1/US-01-setup."""
        mock_gh.side_effect = RuntimeError("timeline API unavailable")
        all_prs = [
            {"number": 31, "state": "OPEN", "headRefName": "sprint-1/US-01-setup", "mergedAt": None},
        ]
        result = sync_tracking.get_linked_pr(1, story_id="US-01", all_prs=all_prs)
        self.assertIsNotNone(result)
        self.assertEqual(result["number"], 31)

    @patch("sync_tracking.gh")
    def test_pr_link_exact_match_end_of_branch(self, mock_gh):
        """US-01 should match branch ending with US-01 (no trailing slug)."""
        mock_gh.side_effect = RuntimeError("timeline API unavailable")
        all_prs = [
            {"number": 32, "state": "OPEN", "headRefName": "sprint-1/US-01", "mergedAt": None},
        ]
        result = sync_tracking.get_linked_pr(1, story_id="US-01", all_prs=all_prs)
        self.assertIsNotNone(result)
        self.assertEqual(result["number"], 32)

    @patch("sync_tracking.gh")
    def test_pr_link_longer_id_no_false_positive(self, mock_gh):
        """US-0001 must NOT match US-00010 branch."""
        mock_gh.side_effect = RuntimeError("timeline API unavailable")
        all_prs = [
            {"number": 33, "state": "OPEN", "headRefName": "sprint-1/US-00010-big", "mergedAt": None},
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

    @patch("check_status.gh_json")
    def test_list_response_warns(self, mock_gh):
        """P7-08: List response adds warning instead of silently skipping."""
        mock_gh.return_value = [{"behind_by": 5}]  # list, not dict
        report, actions = check_status.check_branch_divergence(
            "owner/repo", "main", ["feat/odd"],
        )
        self.assertEqual(len(report), 1)
        self.assertIn("WARNING", report[0])
        self.assertIn("feat/odd", report[0])


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
# P6-02: FakeGitHub-backed tests for check_branch_divergence / check_direct_pushes
# ---------------------------------------------------------------------------


class TestCheckBranchDivergenceFakeGH(unittest.TestCase):
    """P6-02: check_branch_divergence through FakeGitHub endpoints."""

    def setUp(self):
        self.fake = FakeGitHub()
        self.patcher = patch("subprocess.run", make_patched_subprocess(self.fake))
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()

    def test_high_drift(self):
        """behind_by=25 triggers HIGH drift report and action."""
        self.fake.comparisons["feat/stale"] = {"behind_by": 25, "ahead_by": 10}
        report, actions = check_status.check_branch_divergence(
            "owner/repo", "main", ["feat/stale"],
        )
        self.assertEqual(len(report), 1)
        self.assertIn("HIGH", report[0])
        self.assertEqual(len(actions), 1)
        self.assertIn("25 behind", actions[0])

    def test_medium_drift(self):
        """behind_by=15 triggers MEDIUM drift report, no action."""
        self.fake.comparisons["feat/medium"] = {"behind_by": 15, "ahead_by": 8}
        report, actions = check_status.check_branch_divergence(
            "owner/repo", "main", ["feat/medium"],
        )
        self.assertEqual(len(report), 1)
        self.assertIn("MEDIUM", report[0])
        self.assertIn("15", report[0])
        self.assertEqual(actions, [])

    def test_no_drift(self):
        """behind_by=2 produces no drift report."""
        self.fake.comparisons["feat/clean"] = {"behind_by": 2, "ahead_by": 1}
        report, actions = check_status.check_branch_divergence(
            "owner/repo", "main", ["feat/clean"],
        )
        self.assertEqual(report, [])
        self.assertEqual(actions, [])

    def test_api_error_handled(self):
        """Branch not in comparisons still returns default {behind_by: 0}."""
        # Default is behind_by=0, ahead_by=0 — no drift
        report, actions = check_status.check_branch_divergence(
            "owner/repo", "main", ["feat/unknown"],
        )
        self.assertEqual(report, [])
        self.assertEqual(actions, [])


class TestCheckDirectPushesFakeGH(unittest.TestCase):
    """P6-02: check_direct_pushes through FakeGitHub endpoints."""

    def setUp(self):
        self.fake = FakeGitHub()
        self.patcher = patch("subprocess.run", make_patched_subprocess(self.fake))
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()

    def test_direct_pushes_detected(self):
        """Commits with 1 parent (direct pushes) are reported."""
        # Store data in post-jq shape: the production --jq filters to
        # 1-parent commits and reshapes to {sha, message, author, date}.
        # FakeGitHub doesn't execute --jq, so we pre-shape the data.
        self.fake.commits_data = [
            {
                "sha": "abc12345",
                "message": "quick hotfix",
                "author": "dev",
                "date": "2026-03-10T12:00:00Z",
            },
            {
                "sha": "def67890",
                "message": "another direct push",
                "author": "dev",
                "date": "2026-03-10T13:00:00Z",
            },
        ]
        report, actions = check_status.check_direct_pushes(
            "owner/repo", "main", "2026-03-01T00:00:00Z",
        )
        self.assertTrue(len(report) >= 1)
        self.assertIn("2 direct push", report[0])
        self.assertEqual(len(actions), 1)
        self.assertIn("pushed directly", actions[0])

    def test_no_direct_pushes(self):
        """Empty commits list produces no report."""
        self.fake.commits_data = []
        report, actions = check_status.check_direct_pushes(
            "owner/repo", "main", "2026-03-01T00:00:00Z",
        )
        self.assertEqual(report, [])
        self.assertEqual(actions, [])

    def test_api_error_handled(self):
        """If the commits endpoint is unavailable, error is reported gracefully."""
        # Patch the fake to simulate an API failure for commits
        original_handle = self.fake._handle_api

        def failing_api(args):
            if args and args[0].endswith("/commits"):
                return self.fake._fail("server error")
            return original_handle(args)

        self.fake._handle_api = failing_api
        report, actions = check_status.check_direct_pushes(
            "owner/repo", "main", "2026-03-01T00:00:00Z",
        )
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


class TestWriteTfEscaping(unittest.TestCase):
    """P6-17: write_tf quotes YAML-sensitive values; read_tf round-trips them."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="sync-esc-")
        self.tmp = Path(self.tmpdir)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_title_with_colon_roundtrips(self):
        tf = sync_tracking.TF(
            path=self.tmp / "colon.md",
            story="US-01", title="Feat: Add auth", sprint=1,
        )
        sync_tracking.write_tf(tf)
        result = sync_tracking.read_tf(tf.path)
        self.assertEqual(result.title, "Feat: Add auth")

    def test_title_starting_with_bracket(self):
        tf = sync_tracking.TF(
            path=self.tmp / "bracket.md",
            story="US-02", title="[WIP] Feature", sprint=1,
        )
        sync_tracking.write_tf(tf)
        result = sync_tracking.read_tf(tf.path)
        self.assertEqual(result.title, "[WIP] Feature")

    def test_title_with_hash(self):
        tf = sync_tracking.TF(
            path=self.tmp / "hash.md",
            story="US-03", title="Fix #42 bug", sprint=1,
        )
        sync_tracking.write_tf(tf)
        result = sync_tracking.read_tf(tf.path)
        self.assertEqual(result.title, "Fix #42 bug")

    def test_title_without_special_chars(self):
        tf = sync_tracking.TF(
            path=self.tmp / "plain.md",
            story="US-04", title="Simple title", sprint=1,
        )
        sync_tracking.write_tf(tf)
        # Verify no quotes were added in the raw file
        raw = tf.path.read_text(encoding="utf-8")
        self.assertIn("title: Simple title", raw)
        self.assertNotIn('title: "Simple title"', raw)
        result = sync_tracking.read_tf(tf.path)
        self.assertEqual(result.title, "Simple title")

    def test_title_with_existing_quotes(self):
        tf = sync_tracking.TF(
            path=self.tmp / "quotes.md",
            story="US-05", title='Say "hello"', sprint=1,
        )
        sync_tracking.write_tf(tf)
        result = sync_tracking.read_tf(tf.path)
        self.assertEqual(result.title, 'Say "hello"')

    def test_branch_with_special_chars_roundtrips(self):
        tf = sync_tracking.TF(
            path=self.tmp / "branch.md",
            story="US-06", title="Normal", sprint=1,
            branch="[feature]/test",
        )
        sync_tracking.write_tf(tf)
        result = sync_tracking.read_tf(tf.path)
        self.assertEqual(result.branch, "[feature]/test")

    def test_yaml_safe_empty_string(self):
        # _yaml_safe should pass through empty strings unchanged
        self.assertEqual(sync_tracking._yaml_safe(""), "")

    def test_yaml_safe_special_start_chars(self):
        for ch in '[{>|*&!%@`':
            val = f"{ch}value"
            safe = sync_tracking._yaml_safe(val)
            self.assertTrue(safe.startswith('"'), f"Expected quoting for {ch!r}")

    def test_yaml_safe_dash_space_prefix(self):
        self.assertEqual(sync_tracking._yaml_safe("- list item"), '"- list item"')

    def test_yaml_safe_question_space_prefix(self):
        self.assertEqual(sync_tracking._yaml_safe("? key"), '"? key"')

    def test_yaml_safe_trailing_colon(self):
        """P7-04: Trailing colon must be quoted (YAML mapping key)."""
        self.assertEqual(sync_tracking._yaml_safe("http:"), '"http:"')

    def test_yaml_safe_trailing_colon_note(self):
        """P7-04: Another trailing colon case."""
        self.assertEqual(sync_tracking._yaml_safe("note:"), '"note:"')

    def test_yaml_safe_normal_no_quoting(self):
        """P7-04: Normal value without colon should not be quoted."""
        self.assertEqual(sync_tracking._yaml_safe("normal"), "normal")


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


class TestCheckStatusImportGuard(unittest.TestCase):
    """P7-05: sync_backlog import uses ImportError, not bare Exception."""

    def test_import_guard_uses_import_error(self):
        """ImportError should be caught gracefully (sync_backlog missing)."""
        # Verify the import guard specifically uses ImportError, not bare Exception.
        import inspect
        source = inspect.getsource(check_status)
        # Find the import block (between "Import sync engine" and "MAX_LOGS")
        import_block = source[
            source.index("Import sync engine"):source.index("MAX_LOGS")
        ]
        self.assertIn("except ImportError", import_block)
        self.assertNotIn("except Exception", import_block)


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
        """Flags in _ACCEPTED_NOOP_FLAGS (--paginate, --notes-file) are silently allowed."""
        result = self.fake.handle([
            "issue", "list", "--state", "all", "--paginate",
        ])
        self.assertEqual(result.returncode, 0)

    def test_unknown_flag_on_pr_list_raises(self):
        with self.assertRaises(NotImplementedError):
            self.fake.handle(["pr", "list", "--assignee", "@me"])

    def test_unknown_flag_on_release_create_raises(self):
        with self.assertRaises(NotImplementedError):
            self.fake.handle(["release", "create", "v1.0.0", "--prerelease"])


class TestFakeGitHubShortFlags(unittest.TestCase):
    """P6-01: _parse_flags handles single-dash flags (-f, -X)."""

    def setUp(self):
        self.fake = FakeGitHub()

    def test_short_flag_f_parsed(self):
        """-f 'title=val' is captured by _parse_flags."""
        flags = FakeGitHub._parse_flags(
            ["repos/o/r/milestones", "-f", "title=Sprint 1"], start=1,
        )
        self.assertIn("f", flags)
        self.assertEqual(flags["f"], ["title=Sprint 1"])

    def test_short_flag_X_parsed(self):
        """-X PATCH is captured by _parse_flags."""
        flags = FakeGitHub._parse_flags(
            ["repos/o/r/milestones/1", "-X", "PATCH"], start=1,
        )
        self.assertIn("X", flags)
        self.assertEqual(flags["X"], ["PATCH"])

    def test_unknown_short_flag_raises(self):
        """-z is not in _KNOWN_FLAGS['api'] and raises NotImplementedError."""
        with self.assertRaises(NotImplementedError) as ctx:
            self.fake.handle(["api", "repos/o/r/milestones", "-z", "val"])
        self.assertIn("-z", str(ctx.exception))

    def test_short_and_long_flags_mixed(self):
        """-f and --paginate can coexist in one parse."""
        flags = FakeGitHub._parse_flags(
            ["repos/o/r/milestones", "-f", "title=X", "--paginate"], start=1,
        )
        self.assertIn("f", flags)
        self.assertEqual(flags["f"], ["title=X"])
        self.assertIn("paginate", flags)


class TestFakeGitHubJqHandlerScoped(unittest.TestCase):
    """P6-07: --jq is handler-scoped, not a global noop."""

    def setUp(self):
        self.fake = FakeGitHub()

    def test_jq_accepted_on_api_handler(self):
        """api handler has 'jq' in _KNOWN_FLAGS, so --jq is accepted."""
        # Provide a milestones path so the api handler returns data
        self.fake.milestones.append({"number": 1, "title": "M1"})
        result = self.fake.handle([
            "api", "repos/o/r/milestones", "--jq", ".[].title",
        ])
        self.assertEqual(result.returncode, 0)

    def test_jq_rejected_on_handler_without_it(self):
        """Handlers without 'jq' in _KNOWN_FLAGS raise NotImplementedError."""
        with self.assertRaises(NotImplementedError) as ctx:
            self.fake.handle([
                "issue", "list", "--state", "all", "--jq", ".[].title",
            ])
        self.assertIn("jq", str(ctx.exception))
        self.assertIn("issue_list", str(ctx.exception))


class TestFakeGitHubIssueLabelFilter(unittest.TestCase):
    """P6-11: _issue_list implements --label filtering."""

    def setUp(self):
        self.fake = FakeGitHub()
        # Create issues with different labels
        self.fake.handle([
            "issue", "create", "--title", "Bug fix",
            "--label", "bug", "--label", "priority",
        ])
        self.fake.handle([
            "issue", "create", "--title", "Feature A",
            "--label", "enhancement",
        ])
        self.fake.handle([
            "issue", "create", "--title", "Another bug",
            "--label", "bug",
        ])

    def test_label_filter_returns_matching_issues(self):
        """--label bug returns only issues with the 'bug' label."""
        result = self.fake.handle([
            "issue", "list", "--state", "all", "--label", "bug",
            "--json", "number,title",
        ])
        self.assertEqual(result.returncode, 0)
        issues = json.loads(result.stdout)
        self.assertEqual(len(issues), 2)
        titles = {iss["title"] for iss in issues}
        self.assertEqual(titles, {"Bug fix", "Another bug"})

    def test_label_filter_no_matches(self):
        """--label with a non-existent label returns empty list."""
        result = self.fake.handle([
            "issue", "list", "--state", "all", "--label", "docs",
            "--json", "number",
        ])
        self.assertEqual(result.returncode, 0)
        issues = json.loads(result.stdout)
        self.assertEqual(len(issues), 0)

    def test_label_filter_with_milestone(self):
        """--label and --milestone filters compose together."""
        # Create a milestone and an issue with both label and milestone
        self.fake.handle(["api", "repos/o/r/milestones", "-f", "title=M1"])
        self.fake.handle([
            "issue", "create", "--title", "Tracked bug",
            "--label", "bug", "--milestone", "M1",
        ])
        result = self.fake.handle([
            "issue", "list", "--state", "all",
            "--label", "bug", "--milestone", "M1",
            "--json", "number,title",
        ])
        self.assertEqual(result.returncode, 0)
        issues = json.loads(result.stdout)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0]["title"], "Tracked bug")

    def test_no_label_filter_returns_all(self):
        """Without --label, all issues are returned (existing behavior)."""
        result = self.fake.handle([
            "issue", "list", "--state", "all", "--json", "number",
        ])
        self.assertEqual(result.returncode, 0)
        issues = json.loads(result.stdout)
        self.assertEqual(len(issues), 3)


if __name__ == "__main__":
    unittest.main()
