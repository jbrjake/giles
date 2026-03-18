#!/usr/bin/env python3
"""Sprint runtime module tests — extracted from test_gh_interactions.py.

Covers: check_status, bootstrap_github, populate_issues, sync_tracking,
update_burndown, kanban helpers, extract_sp, and shared validate_config helpers.

Run: python -m pytest tests/test_sprint_runtime.py -v
"""
from __future__ import annotations

import inspect
import io
import json
import os
import subprocess
import tempfile
import unittest
from contextlib import redirect_stderr
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch

from fake_github import FakeGitHub, make_patched_subprocess

import validate_config
import check_status
import bootstrap_github
import populate_issues
import sync_tracking
import update_burndown


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
        # BH-P11-063: Verify query requests correct JSON fields
        call_args = mock_gh.call_args[0][0]
        self.assertIn("run", call_args)
        self.assertIn("--json", call_args)

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
        # BH22-061: Verify the log fetch used the correct run database ID
        self.assertIn("42", str(mock_gh.call_args))


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
        # BH-P11-063: Verify query requests correct resource and fields
        call_args = mock_gh.call_args[0][0]
        self.assertIn("pr", call_args)
        self.assertIn("--json", call_args)

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
        bootstrap_github.create_label("test-label", "ff0000", "A test label")
        mock_gh.assert_called_once()
        call_args = mock_gh.call_args[0][0]
        self.assertIn("label", call_args)
        self.assertIn("create", call_args)
        self.assertIn("test-label", call_args)
        # BH21-007: Verify color and description are passed (not silently dropped)
        self.assertIn("ff0000", call_args)
        self.assertIn("A test label", call_args)

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
# BH-P11-001/002/003: Idempotency tests for bootstrap_github.py
# ---------------------------------------------------------------------------

class TestBootstrapStaticLabelsIdempotent(unittest.TestCase):
    """BH-P11-001: Calling create_static_labels() twice produces no duplicates."""

    def test_static_labels_idempotent(self):
        fake_gh = FakeGitHub()
        with patch("subprocess.run", make_patched_subprocess(fake_gh)):
            bootstrap_github.create_static_labels()
            count_after_first = len(fake_gh.labels)
            self.assertGreater(count_after_first, 0, "Should create labels")

            bootstrap_github.create_static_labels()
            count_after_second = len(fake_gh.labels)

        self.assertEqual(
            count_after_first, count_after_second,
            f"Label count changed from {count_after_first} to "
            f"{count_after_second} after second create_static_labels() call",
        )


class TestBootstrapMilestonesIdempotent(unittest.TestCase):
    """BH-P11-002: Calling create_milestones_on_github() twice produces no duplicates."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tmpdir.name)
        # Create a minimal milestone file
        backlog = self.root / "sprint-config" / "backlog" / "milestones"
        backlog.mkdir(parents=True)
        (backlog / "milestone-1.md").write_text(
            "# Sprint 1: Foundation\n\n"
            "### Sprint 1: Foundation\n\n"
            "| US-0101 | Setup | S01 | 3 | P0 |\n",
            encoding="utf-8",
        )
        self.config = {
            "project": {"name": "test", "repo": "owner/repo", "language": "python"},
            "paths": {
                "backlog_dir": str(self.root / "sprint-config" / "backlog"),
            },
        }

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_milestones_idempotent(self):
        fake_gh = FakeGitHub()
        with patch("subprocess.run", make_patched_subprocess(fake_gh)):
            bootstrap_github.create_milestones_on_github(self.config)
            count_after_first = len(fake_gh.milestones)
            self.assertEqual(count_after_first, 1, "Should create 1 milestone")

            bootstrap_github.create_milestones_on_github(self.config)
            count_after_second = len(fake_gh.milestones)

        self.assertEqual(
            count_after_first, count_after_second,
            f"Milestone count changed from {count_after_first} to "
            f"{count_after_second} after second call",
        )


class TestBootstrapPersonaLabelsIdempotent(unittest.TestCase):
    """BH-P11-003: Calling create_persona_labels() twice produces no duplicates."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tmpdir.name)
        team_dir = self.root / "sprint-config" / "team"
        team_dir.mkdir(parents=True)
        (team_dir / "INDEX.md").write_text(
            "| Name | Role | File |\n"
            "|------|------|------|\n"
            "| Alice | Engineer | alice.md |\n"
            "| Bob | Architect | bob.md |\n",
            encoding="utf-8",
        )
        (team_dir / "alice.md").write_text("# Alice\n## Role\nEngineer\n")
        (team_dir / "bob.md").write_text("# Bob\n## Role\nArchitect\n")
        self.config = {
            "project": {"name": "test", "repo": "owner/repo"},
            "paths": {"team_dir": str(team_dir)},
        }

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_persona_labels_idempotent(self):
        fake_gh = FakeGitHub()
        with patch("subprocess.run", make_patched_subprocess(fake_gh)):
            bootstrap_github.create_persona_labels(self.config)
            count_after_first = len(fake_gh.labels)
            self.assertGreater(count_after_first, 0, "Should create persona labels")

            bootstrap_github.create_persona_labels(self.config)
            count_after_second = len(fake_gh.labels)

        self.assertEqual(
            count_after_first, count_after_second,
            f"Persona label count changed from {count_after_first} to "
            f"{count_after_second} after second create_persona_labels() call",
        )
        # Verify both persona labels exist
        self.assertIn("persona:alice", fake_gh.labels)
        self.assertIn("persona:bob", fake_gh.labels)


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

    @patch("populate_issues.gh_json")
    def test_returns_story_ids(self, mock_gh_json):
        mock_gh_json.return_value = [
            {"title": "US-0101: Setup project"},
            {"title": "US-0102: Add auth"},
            {"title": "Not a story"},
        ]
        existing = populate_issues.get_existing_issues()
        self.assertIn("US-0101", existing)
        self.assertIn("US-0102", existing)
        self.assertEqual(len(existing), 2)

    @patch("populate_issues.gh_json")
    def test_handles_empty_response(self, mock_gh_json):
        mock_gh_json.return_value = []
        existing = populate_issues.get_existing_issues()
        self.assertEqual(len(existing), 0)

    @patch("populate_issues.gh_json")
    def test_handles_gh_failure(self, mock_gh_json):
        mock_gh_json.side_effect = RuntimeError("auth failed")
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

# BH21-016: TestFindMilestoneTitle removed — it tested the find_milestone_title()
# wrapper which was a one-line pass-through to find_milestone(). The wrapper
# was removed and the call site now uses find_milestone() directly.
# The underlying find_milestone() is tested by TestFindMilestoneBoundary below.


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

    @patch("validate_config.gh_json")
    def test_leading_zero_sprint_07_matches_find_7(self, mock_gh):
        """BH-001: 'Sprint 07:' must be found by find_milestone(7)."""
        mock_gh.return_value = [
            {"title": "Sprint 07: Walking Skeleton", "number": 1},
        ]
        result = validate_config.find_milestone(7)
        self.assertIsNotNone(result, "find_milestone(7) must match 'Sprint 07:'")
        self.assertEqual(result["title"], "Sprint 07: Walking Skeleton")

    @patch("validate_config.gh_json")
    def test_sprint_7_still_matches_without_leading_zero(self, mock_gh):
        """BH-001: 'Sprint 7:' must still be found by find_milestone(7)."""
        mock_gh.return_value = [
            {"title": "Sprint 7: Walking Skeleton", "number": 1},
        ]
        result = validate_config.find_milestone(7)
        self.assertIsNotNone(result)


class TestGetLinkedPR(unittest.TestCase):
    """P1-02: Test get_linked_pr matches correct story ID."""

    @patch("sync_tracking.gh_json")
    def test_matches_correct_story_id(self, mock_gh_json):
        """Fallback search should match only the requested story ID."""
        mock_gh_json.side_effect = RuntimeError("timeline API unavailable")
        all_prs = [
            {"number": 10, "state": "MERGED", "headRefName": "sprint-1/us-0099-other", "mergedAt": "2026-03-01"},
            {"number": 20, "state": "OPEN", "headRefName": "sprint-1/us-0001-setup", "mergedAt": None},
        ]
        result = sync_tracking.get_linked_pr(1, story_id="US-0001", all_prs=all_prs)
        self.assertIsNotNone(result)
        self.assertEqual(result["number"], 20)

    @patch("sync_tracking.gh_json")
    def test_does_not_match_wrong_story(self, mock_gh_json):
        """Should return None if no PR matches the requested story ID."""
        mock_gh_json.side_effect = RuntimeError("timeline API unavailable")
        all_prs = [
            {"number": 10, "state": "OPEN", "headRefName": "sprint-1/us-0099-other", "mergedAt": None},
        ]
        result = sync_tracking.get_linked_pr(1, story_id="US-0001", all_prs=all_prs)
        self.assertIsNone(result)

    @patch("sync_tracking.gh_json")
    def test_slug_match_ignores_sprint_prefix(self, mock_gh_json):
        """BH18-010: Branch matching uses slug portion, not full path.

        sprint-2/us-0001-follow-up should NOT match when looking for
        sprint-1's US-0001 — the story ID appears in a different sprint's
        branch prefix, and the slug portion still matches. However, since
        both slugs contain 'us-0001', the current fix matches on the slug
        after the last '/'. This test documents the expected behavior.
        """
        mock_gh_json.side_effect = RuntimeError("timeline API unavailable")
        all_prs = [
            {"number": 10, "state": "OPEN",
             "headRefName": "sprint-1/us-0001-setup", "mergedAt": None},
            {"number": 20, "state": "OPEN",
             "headRefName": "sprint-2/us-0001-follow-up", "mergedAt": None},
        ]
        # Both branches have us-0001 in the slug — first match wins
        result = sync_tracking.get_linked_pr(1, story_id="US-0001", all_prs=all_prs)
        self.assertIsNotNone(result)
        self.assertEqual(result["number"], 10,
                         "Should match the first PR with US-0001 in slug")


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

    def test_timeline_prefers_latest_merged_pr(self):
        """P12-002: When multiple merged PRs exist, pick the latest merged one."""
        self.fake.timeline_events[8] = [
            {
                "source": {
                    "issue": {
                        "number": 10,
                        "state": "closed",
                        "pull_request": {"merged_at": "2026-01-01T00:00:00Z"},
                    }
                }
            },
            {
                "source": {
                    "issue": {
                        "number": 20,
                        "state": "closed",
                        "pull_request": {"merged_at": "2026-06-01T00:00:00Z"},
                    }
                }
            },
        ]
        patched = make_patched_subprocess(self.fake)
        with patch("subprocess.run", patched):
            result = sync_tracking.get_linked_pr(
                8, story_id="US-03", all_prs=[]
            )
        self.assertIsNotNone(result)
        # Should pick the latest merged PR (#20, merged June) not earliest (#10, merged Jan)
        self.assertEqual(result["number"], 20)

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

    @patch("sync_tracking.gh_json")
    def test_pr_link_no_substring_match(self, mock_gh_json):
        """US-01 must NOT match branch containing US-010."""
        mock_gh_json.side_effect = RuntimeError("timeline API unavailable")
        all_prs = [
            {"number": 30, "state": "OPEN", "headRefName": "sprint-1/US-010-feature", "mergedAt": None},
        ]
        result = sync_tracking.get_linked_pr(1, story_id="US-01", all_prs=all_prs)
        self.assertIsNone(result)

    @patch("sync_tracking.gh_json")
    def test_pr_link_exact_match(self, mock_gh_json):
        """US-01 should match branch sprint-1/US-01-setup."""
        mock_gh_json.side_effect = RuntimeError("timeline API unavailable")
        all_prs = [
            {"number": 31, "state": "OPEN", "headRefName": "sprint-1/US-01-setup", "mergedAt": None},
        ]
        result = sync_tracking.get_linked_pr(1, story_id="US-01", all_prs=all_prs)
        self.assertIsNotNone(result)
        self.assertEqual(result["number"], 31)

    @patch("sync_tracking.gh_json")
    def test_pr_link_exact_match_end_of_branch(self, mock_gh_json):
        """US-01 should match branch ending with US-01 (no trailing slug)."""
        mock_gh_json.side_effect = RuntimeError("timeline API unavailable")
        all_prs = [
            {"number": 32, "state": "OPEN", "headRefName": "sprint-1/US-01", "mergedAt": None},
        ]
        result = sync_tracking.get_linked_pr(1, story_id="US-01", all_prs=all_prs)
        self.assertIsNotNone(result)
        self.assertEqual(result["number"], 32)

    @patch("sync_tracking.gh_json")
    def test_pr_link_longer_id_no_false_positive(self, mock_gh_json):
        """US-0001 must NOT match US-00010 branch."""
        mock_gh_json.side_effect = RuntimeError("timeline API unavailable")
        all_prs = [
            {"number": 33, "state": "OPEN", "headRefName": "sprint-1/US-00010-big", "mergedAt": None},
        ]
        result = sync_tracking.get_linked_pr(1, story_id="US-0001", all_prs=all_prs)
        self.assertIsNone(result)


class TestGetLinkedPrWarning(unittest.TestCase):
    """P13-010: get_linked_pr should warn when timeline API fails."""

    def test_timeline_api_failure_emits_warning(self):
        """P13-010: get_linked_pr logs warning when timeline API fails."""
        buf = io.StringIO()

        def failing_gh_json(args):
            if "timeline" in str(args):
                raise RuntimeError("API timeout")
            return []

        with redirect_stderr(buf):
            with patch("sync_tracking.gh_json", side_effect=failing_gh_json):
                result = sync_tracking.get_linked_pr(1, "US-0101", all_prs=[])

        self.assertIsNone(result)
        warning_text = buf.getvalue()
        self.assertIn("timeline", warning_text.lower())
        self.assertIn("API timeout", warning_text)


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
# BH-022 / BH-025 / BH-026: Tests for new shared helpers
# ---------------------------------------------------------------------------

class TestSharedHelpers(unittest.TestCase):
    """Tests for safe_int and parse_iso_date in validate_config."""

    def test_safe_int_basic(self):
        from validate_config import safe_int
        self.assertEqual(safe_int("42"), 42)
        self.assertEqual(safe_int("  5abc"), 5)
        self.assertEqual(safe_int("abc"), 0)
        self.assertEqual(safe_int(""), 0)

    def test_parse_iso_date_utc(self):
        from validate_config import parse_iso_date
        self.assertEqual(parse_iso_date("2026-03-15T12:00:00Z"), "2026-03-15")

    def test_parse_iso_date_empty(self):
        from validate_config import parse_iso_date
        self.assertEqual(parse_iso_date(""), "")
        self.assertEqual(parse_iso_date("", default="\u2014"), "\u2014")

    def test_parse_iso_date_invalid(self):
        from validate_config import parse_iso_date
        self.assertEqual(parse_iso_date("not-a-date"), "")

    def test_parse_iso_date_custom_format(self):
        from validate_config import parse_iso_date
        result = parse_iso_date("2026-03-15T12:00:00Z", fmt="%Y-%m-%dT%H:%M")
        self.assertIn("2026-03-15", result)

    def test_gh_custom_timeout(self):
        """BH-016 / BH-020: gh() passes custom timeout to subprocess.

        BH-020: Replaced signature inspection with behavioral test.
        """
        from validate_config import gh
        import subprocess as _sp
        with patch("validate_config.subprocess.run",
                   side_effect=_sp.TimeoutExpired(cmd="gh", timeout=5)) as mock_run:
            with self.assertRaises(RuntimeError) as ctx:
                gh(["api", "repos"], timeout=5)
            # Verify timeout was actually passed through to subprocess.run
            mock_run.assert_called_once()
            call_kwargs = mock_run.call_args[1]
            self.assertEqual(call_kwargs.get("timeout"), 5)
            self.assertIn("timed out", str(ctx.exception))


class TestParseSimpleTomlEdgeCases(unittest.TestCase):
    """BH-022: TOML parser edge cases for escaping, brackets, comments."""

    def test_inline_comment_stripped(self):
        from validate_config import parse_simple_toml
        result = parse_simple_toml('[project]\nname = "test"  # a comment\n')
        self.assertEqual(result["project"]["name"], "test")

    def test_escaped_quotes_in_string(self):
        from validate_config import parse_simple_toml
        toml_str = '[project]\nname = "has \\"quotes\\""\n'
        result = parse_simple_toml(toml_str)
        self.assertIn("quotes", result["project"]["name"])

    def test_array_value(self):
        from validate_config import parse_simple_toml
        result = parse_simple_toml('[ci]\ncheck_commands = ["lint", "test"]\n')
        self.assertEqual(result["ci"]["check_commands"], ["lint", "test"])

    def test_boolean_values(self):
        from validate_config import parse_simple_toml
        result = parse_simple_toml('[project]\nenabled = true\ndisabled = false\n')
        self.assertTrue(result["project"]["enabled"])
        self.assertFalse(result["project"]["disabled"])


# ---------------------------------------------------------------------------
# BH-004: extract_sp word-boundary adversarial tests
# ---------------------------------------------------------------------------

class TestExtractSPWordBoundary(unittest.TestCase):
    """Verify extract_sp doesn't match 'sp' as a substring."""

    def test_wasp_not_matched(self):
        issue = {"labels": [], "body": "The wasp: 3 project"}
        self.assertEqual(update_burndown.extract_sp(issue), 0)

    def test_bsp_not_matched(self):
        issue = {"labels": [], "body": "BSP: 2 value"}
        self.assertEqual(update_burndown.extract_sp(issue), 0)

    def test_standalone_sp_still_works(self):
        issue = {"labels": [], "body": "sp: 5"}
        self.assertEqual(update_burndown.extract_sp(issue), 5)

    def test_sp_with_equals(self):
        issue = {"labels": [], "body": "SP = 8"}
        self.assertEqual(update_burndown.extract_sp(issue), 8)


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

    def test_unknown_branch_returns_no_drift(self):
        """Branch not in comparisons returns default {behind_by: 0} — no drift."""
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

    def _setup_mixed_commits(self):
        """Set up commits with both direct pushes and merges."""
        self.fake.commits_data = [
            {
                "sha": "abc12345full",
                "parents": [{"sha": "parent1"}],  # 1 parent = direct push
                "commit": {
                    "message": "quick hotfix",
                    "author": {"name": "dev", "date": "2026-03-10T12:00:00Z"},
                },
            },
            {
                "sha": "def67890full",
                "parents": [{"sha": "parent2"}],  # 1 parent = direct push
                "commit": {
                    "message": "another direct push",
                    "author": {"name": "dev", "date": "2026-03-10T13:00:00Z"},
                },
            },
            {
                "sha": "merge123456",
                "parents": [{"sha": "p1"}, {"sha": "p2"}],  # 2 parents = merge
                "commit": {
                    "message": "Merge branch 'feat' into main",
                    "author": {"name": "dev", "date": "2026-03-10T14:00:00Z"},
                },
            },
        ]

    def test_jq_filters_merge_commits(self):
        """With jq available, merge commits (2+ parents) are excluded."""
        # BH21-002: jq is now a required dev dependency (enforced by conftest.py)
        self._setup_mixed_commits()
        report, actions = check_status.check_direct_pushes(
            "owner/repo", "main", "2026-03-01T00:00:00Z",
        )
        self.assertTrue(len(report) >= 1)
        self.assertIn("2 direct push", report[0])
        self.assertEqual(len(actions), 1)
        self.assertIn("pushed directly", actions[0])

    def test_no_jq_returns_all_commits(self):
        """Without jq, all commits (including merges) are returned."""
        self._setup_mixed_commits()
        # Force jq unavailable
        saved = FakeGitHub._jq_available
        FakeGitHub._jq_available = False
        try:
            report, actions = check_status.check_direct_pushes(
                "owner/repo", "main", "2026-03-01T00:00:00Z",
            )
        finally:
            FakeGitHub._jq_available = saved
        # Without jq filtering, all 3 commits are counted (including merge)
        self.assertTrue(len(report) >= 1)
        self.assertIn("3 direct push", report[0])
        self.assertEqual(len(actions), 1)

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

    def test_closed_issue_sets_completed_date(self):
        """P15: sync_one must populate tf.completed from closedAt."""
        tf = sync_tracking.TF(
            path=Path("/tmp/test.md"), story="US-0002",
            status="dev", sprint=1,
        )
        issue = {"state": "closed", "labels": [], "closedAt": "2026-03-10T12:00:00Z", "number": 2}
        sync_tracking.sync_one(tf, issue, None, 1)
        self.assertEqual(tf.completed, "2026-03-10")

    def test_sprint_mismatch_updates_sprint(self):
        """P15: sync_one must update tf.sprint when it disagrees with passed sprint."""
        tf = sync_tracking.TF(
            path=Path("/tmp/test.md"), story="US-0003",
            status="todo", sprint=1, issue_number="3",
        )
        issue = {"state": "open", "labels": [], "number": 3}
        changes = sync_tracking.sync_one(tf, issue, None, sprint=2)
        self.assertEqual(tf.sprint, 2)
        self.assertTrue(any("sprint" in c for c in changes))


class TestSyncOneGitHubAuthoritative(unittest.TestCase):
    """BH-P11-007: sync_one() must NOT push local state back to GitHub.

    GitHub is authoritative. When local status disagrees with GitHub labels,
    sync_one() should update the local TF to match GitHub — never invoke
    gh issue edit or gh label commands to change GitHub state.
    """

    def test_no_gh_calls_on_status_disagreement(self):
        """sync_one() with disagreeing states must not call gh CLI."""
        gh_calls: list[list[str]] = []

        def spy_subprocess(args, *a, **kw):
            if isinstance(args, list) and args and args[0] == "gh":
                gh_calls.append(args)
            return subprocess.CompletedProcess(
                args=args, returncode=0, stdout="", stderr="",
            )

        # Local says "todo", GitHub says "review" via labels
        tf = sync_tracking.TF(
            path=Path("/tmp/test.md"), story="US-0001",
            status="todo", sprint=1, issue_number="5",
        )
        issue = {
            "state": "open",
            "labels": [{"name": "kanban:review"}],
            "number": 5,
        }

        with patch("subprocess.run", spy_subprocess):
            changes = sync_tracking.sync_one(tf, issue, None, 1)

        # Local TF should be updated to match GitHub
        self.assertEqual(tf.status, "review")
        self.assertTrue(len(changes) > 0)

        # No gh CLI calls should have been made
        gh_edit_calls = [
            c for c in gh_calls
            if len(c) > 2 and c[1] in ("issue", "label")
        ]
        self.assertEqual(
            gh_edit_calls, [],
            f"sync_one() should not call gh to modify GitHub state, "
            f"but found: {gh_edit_calls}",
        )


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

    def test_active_stories_is_last_section(self):
        """P13-018: Replacement works when Active Stories is the final section."""
        with tempfile.TemporaryDirectory() as tmpdir:
            status_file = Path(tmpdir) / "SPRINT-STATUS.md"
            status_file.write_text(
                "# Sprint Status\n\n## Active Stories\n\n"
                "| Story | Status | Assignee | PR |\n"
                "|-------|--------|----------|----|"
                "\n| old | old | old | old |\n",
                encoding="utf-8",
            )
            rows = [
                {"story_id": "US-0099", "short_title": "Final", "sp": 2,
                 "status": "dev", "closed": "\u2014",
                 "assignee": "Alice", "pr": "#5"},
            ]
            update_burndown.update_sprint_status(1, rows, Path(tmpdir))
            content = status_file.read_text()
            self.assertIn("US-0099", content)
            self.assertNotIn("old", content)

    def test_no_trailing_newline(self):
        """P13-018: File without trailing newline is handled correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            status_file = Path(tmpdir) / "SPRINT-STATUS.md"
            status_file.write_text(
                "# Sprint Status\n\n## Active Stories\n\n"
                "| Story | Status | Assignee | PR |\n"
                "|-------|--------|----------|----|"
                "\n| old | old | old | old |",  # no trailing \n
                encoding="utf-8",
            )
            rows = [
                {"story_id": "US-0050", "short_title": "Mid", "sp": 1,
                 "status": "todo", "closed": "\u2014"},
            ]
            update_burndown.update_sprint_status(1, rows, Path(tmpdir))
            content = status_file.read_text()
            self.assertIn("US-0050", content)
            self.assertNotIn("old", content)

    def test_skips_missing_file(self):
        """BH-P11-050: Assert no file is created when SPRINT-STATUS.md is missing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            rows = [{"story_id": "X", "short_title": "X", "sp": 0,
                      "status": "todo", "closed": ""}]
            result = update_burndown.update_sprint_status(1, rows, Path(tmpdir))
            # Should return None (early exit) and not create any file
            self.assertIsNone(result)
            self.assertFalse(
                (Path(tmpdir) / "SPRINT-STATUS.md").exists(),
                "SPRINT-STATUS.md should not be created when it doesn't exist",
            )


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

    def test_none_label_does_not_crash(self):
        """BH19-003: None in labels list must not raise AttributeError."""
        issue = {"labels": [None, {"name": "kanban:dev"}], "state": "open"}
        self.assertEqual(validate_config.kanban_from_labels(issue), "dev")

    def test_non_dict_non_str_labels_skipped(self):
        """BH19-003: int/bool/None labels are silently skipped."""
        issue = {"labels": [42, True, None], "state": "open"}
        self.assertEqual(validate_config.kanban_from_labels(issue), "todo")

    def test_closed_with_stale_kanban_label(self):
        """BH21-012: kanban_from_labels now overrides stale labels for closed issues."""
        issue = {"labels": [{"name": "kanban:dev"}], "state": "closed"}
        self.assertEqual(validate_config.kanban_from_labels(issue), "done",
                         "closed issues always return 'done' regardless of kanban label")


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
        recent = (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat()
        h = check_status._hours(recent)
        self.assertAlmostEqual(h, 0.5, delta=0.1)

    def test_zulu_suffix_parsed(self):
        ts = (datetime.now(timezone.utc) - timedelta(hours=3)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        self.assertAlmostEqual(check_status._hours(ts), 3.0, delta=0.1)

    def test_invalid_format_returns_zero(self):
        self.assertEqual(check_status._hours("not-a-date"), 0.0)


class TestAge(unittest.TestCase):
    """P5-17: _age formats time deltas as human-readable strings."""

    def test_minutes(self):
        ts = (datetime.now(timezone.utc) - timedelta(minutes=45)).isoformat()
        self.assertTrue(check_status._age(ts).endswith("m"))

    def test_hours(self):
        ts = (datetime.now(timezone.utc) - timedelta(hours=5)).isoformat()
        self.assertIn("h", check_status._age(ts))

    def test_days(self):
        ts = (datetime.now(timezone.utc) - timedelta(days=3)).isoformat()
        self.assertIn("d", check_status._age(ts))


# ---------------------------------------------------------------------------
# P5-10: check_milestone tests
# ---------------------------------------------------------------------------


class TestCheckMilestone(unittest.TestCase):
    """P5-10: check_milestone with mocked find_milestone + gh_json.

    BH18-001/002: check_milestone now uses find_milestone() from validate_config
    for milestone lookup (handles leading zeros, avoids redundant API calls).
    Tests mock find_milestone for the lookup and gh_json for the issue SP query.
    """

    def test_happy_path_with_sp(self):
        ms = {"title": "Sprint 1", "open_issues": 2, "closed_issues": 3}
        issues = [
            {"state": "closed", "labels": [{"name": "sp:3"}], "body": ""},
            {"state": "closed", "labels": [{"name": "sp:5"}], "body": ""},
            {"state": "closed", "labels": [{"name": "sp:2"}], "body": ""},
            {"state": "open", "labels": [{"name": "sp:8"}], "body": ""},
            {"state": "open", "labels": [{"name": "sp:5"}], "body": ""},
        ]
        with patch.object(check_status, "find_milestone", return_value=ms), \
             patch.object(check_status, "gh_json", return_value=issues):
            report, actions = check_status.check_milestone(1)
        self.assertTrue(any("3/5" in line for line in report))
        self.assertTrue(any("SP" in line for line in report))

    def test_no_milestone_found(self):
        with patch.object(check_status, "find_milestone", return_value=None):
            report, actions = check_status.check_milestone(99)
        self.assertTrue(any("no milestone" in line for line in report))

    def test_zero_total_stories(self):
        ms = {"title": "Sprint 1", "open_issues": 0, "closed_issues": 0}
        with patch.object(check_status, "find_milestone", return_value=ms), \
             patch.object(check_status, "gh_json", return_value=[]):
            report, actions = check_status.check_milestone(1)
        self.assertTrue(any("0/0" in line for line in report))
        self.assertTrue(any("0%" in line for line in report))

    def test_api_error_graceful(self):
        with patch.object(
            check_status, "find_milestone", side_effect=RuntimeError("oops"),
        ):
            report, actions = check_status.check_milestone(1)
        self.assertTrue(any("could not query" in line for line in report))

    def test_leading_zero_milestone_found(self):
        """BH18-001: check_milestone must find 'Sprint 07' when asked for sprint 7."""
        ms = {"title": "Sprint 07: Walking Skeleton",
              "open_issues": 1, "closed_issues": 2}
        issues = [
            {"state": "closed", "labels": [{"name": "sp:3"}], "body": ""},
            {"state": "closed", "labels": [{"name": "sp:5"}], "body": ""},
            {"state": "open", "labels": [{"name": "sp:2"}], "body": ""},
        ]
        with patch.object(check_status, "find_milestone", return_value=ms), \
             patch.object(check_status, "gh_json", return_value=issues):
            report, actions = check_status.check_milestone(7)
        report_text = "\n".join(report)
        self.assertNotIn("no milestone", report_text,
                         "check_milestone(7) should find 'Sprint 07:' milestone")
        self.assertIn("2/3", report_text)

    def test_leading_zero_and_plain_both_work(self):
        """BH18-001: Both 'Sprint 7' and 'Sprint 07' must match sprint 7."""
        for title in ("Sprint 7: Plain", "Sprint 07: Leading Zero"):
            ms = {"title": title, "open_issues": 0, "closed_issues": 1}
            with patch.object(check_status, "find_milestone", return_value=ms), \
                 patch.object(check_status, "gh_json", return_value=[]):
                report, _ = check_status.check_milestone(7)
            report_text = "\n".join(report)
            self.assertNotIn("no milestone", report_text,
                             f"check_milestone(7) should find '{title}'")


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

    def test_yaml_safe_single_quote_start(self):
        """BH-P11-105: Single-quote start must trigger quoting."""
        val = "'Twas a dark night'"
        safe = sync_tracking._yaml_safe(val)
        self.assertTrue(safe.startswith('"'),
                        f"Expected quoting for single-quote start: {safe!r}")

    def test_yaml_safe_double_quote_start(self):
        """BH-P11-105: Double-quote start must trigger quoting."""
        val = '"Hello" said Bob'
        safe = sync_tracking._yaml_safe(val)
        self.assertTrue(safe.startswith('"'),
                        f"Expected quoting for double-quote start: {safe!r}")

    def test_single_quote_title_roundtrips(self):
        """BH-P11-105: Title starting and ending with single quotes round-trips."""
        tf = sync_tracking.TF(
            path=self.tmp / "squote.md",
            story="US-07", title="'Twas a dark night'", sprint=1,
        )
        sync_tracking.write_tf(tf)
        result = sync_tracking.read_tf(tf.path)
        self.assertEqual(result.title, "'Twas a dark night'")

    def test_backslash_in_value_roundtrips(self):
        """BH-007: Backslash must be escaped so it round-trips correctly."""
        tf = sync_tracking.TF(
            path=self.tmp / "backslash.md",
            story="US-08", title="C:\\Users\\name", sprint=1,
        )
        sync_tracking.write_tf(tf)
        result = sync_tracking.read_tf(tf.path)
        self.assertEqual(result.title, "C:\\Users\\name")

    def test_backslash_quote_combo_roundtrips(self):
        """BH-007: Value with both backslashes and quotes round-trips."""
        tf = sync_tracking.TF(
            path=self.tmp / "combo.md",
            story="US-09", title='path\\"quoted"', sprint=1,
        )
        sync_tracking.write_tf(tf)
        result = sync_tracking.read_tf(tf.path)
        self.assertEqual(result.title, 'path\\"quoted"')

    def test_yaml_boolean_keyword_roundtrips(self):
        """BH-007: Boolean keywords must be quoted and round-trip as strings."""
        for kw in ("true", "false", "null", "yes", "no"):
            tf = sync_tracking.TF(
                path=self.tmp / f"bool-{kw}.md",
                story="US-10", title=kw, sprint=1,
            )
            sync_tracking.write_tf(tf)
            result = sync_tracking.read_tf(tf.path)
            self.assertEqual(result.title, kw, f"Boolean keyword {kw!r} did not round-trip")


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
