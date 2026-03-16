#!/usr/bin/env python3
"""Arg-parsing tests, FakeGitHub infrastructure tests, and BH-xxx regression tests.

Extracted from test_gh_interactions.py to keep test files focused.
Covers:
  - main() arg-parsing for sync_tracking, check_status, commit, sprint_analytics
  - FakeGitHub flag enforcement, short flags, --jq scoping, label filtering, strict mode
  - BH-series regression tests (BH-001 through BH-023)
  - Integration tests for check_status.main() and sync_tracking.main()
  - patch_gh helper tests and gate_prs demo tests

Run: python -m pytest tests/test_bugfix_regression.py -v
"""
from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
import warnings
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from fake_github import FakeGitHub, make_patched_subprocess
from gh_test_helpers import MonitoredMock, patch_gh

import validate_config
import commit
import sprint_analytics
import check_status
import sync_tracking
import update_burndown
from release_gate import gate_prs


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


# ---------------------------------------------------------------------------
# BH-series regression tests (pass 10 bug fixes)
# ---------------------------------------------------------------------------


class TestBH001PaginatedJson(unittest.TestCase):
    """BH-001: gh_json handles concatenated JSON arrays from --paginate."""

    def test_normal_json_still_works(self):
        """Single JSON array is parsed normally."""
        fake = FakeGitHub()
        fake.milestones = [{"number": 1, "title": "Sprint 1"}]
        with patch("subprocess.run", make_patched_subprocess(fake)):
            result = validate_config.gh_json([
                "api", "repos/{owner}/{repo}/milestones", "--paginate",
            ])
        self.assertEqual(len(result), 1)

    def test_concatenated_json_arrays(self):
        """BH-010: Concatenated arrays [a][b] are merged into one list.

        Tests the actual gh_json function via mock subprocess (not a
        reimplementation of the decode loop).
        """
        concatenated_output = '[{"a":1},{"a":2}][{"a":3}]'

        def _mock_run(cmd, **kw):
            import subprocess as _sp
            return _sp.CompletedProcess(
                args=cmd, returncode=0, stdout=concatenated_output, stderr="",
            )

        with patch("validate_config.subprocess.run", side_effect=_mock_run):
            result = validate_config.gh_json(["api", "repos/o/r/milestones", "--paginate"])
        self.assertEqual(len(result), 3)
        self.assertEqual(result[0]["a"], 1)
        self.assertEqual(result[2]["a"], 3)


class TestBH004VacuousTruth(unittest.TestCase):
    """BH-004: ci_ok is False when no checks are COMPLETED."""

    def test_in_progress_checks_not_green(self):
        """All checks in_progress should NOT report CI as green."""
        pr = {
            "number": 1, "title": "Test PR",
            "reviewDecision": "APPROVED",
            "statusCheckRollup": [
                {"status": "IN_PROGRESS", "conclusion": None},
            ],
            "createdAt": "",
            "labels": [],
        }
        fake = FakeGitHub()
        fake.prs.append(pr)
        with patch.object(check_status, "gh_json", return_value=[pr]):
            report, actions = check_status.check_prs()
        # Should NOT say "CI green, ready to merge"
        full = "\n".join(report)
        self.assertNotIn("CI green", full)
        self.assertIn("CI pending", full)

    def test_empty_checks_not_green(self):
        """No checks at all should NOT report CI as green."""
        pr = {
            "number": 2, "title": "Empty checks",
            "reviewDecision": "APPROVED",
            "statusCheckRollup": [],
            "createdAt": "",
            "labels": [],
        }
        with patch.object(check_status, "gh_json", return_value=[pr]):
            report, _actions = check_status.check_prs()
        full = "\n".join(report)
        self.assertNotIn("CI green", full)


class TestBH005SprintStatusRegex(unittest.TestCase):
    """BH-005: update_sprint_status handles content between heading and table."""

    def test_description_between_heading_and_table(self):
        """Old table rows are fully replaced even with content between heading and table."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            status_file = Path(tmpdir) / "SPRINT-STATUS.md"
            status_file.write_text(
                "# Sprint Status\n\n"
                "## Active Stories\n\n"
                "Some description paragraph.\n\n"
                "| old | table | old | old |\n"
                "|-----|-------|-----|-----|\n"
                "| OLD-001 | old | old | old |\n\n"
                "## Other\n",
                encoding="utf-8",
            )
            rows = [
                {"story_id": "NEW-001", "short_title": "New", "sp": 3,
                 "status": "dev", "closed": "\u2014",
                 "assignee": "Ren", "pr": "#1"},
            ]
            update_burndown.update_sprint_status(1, rows, Path(tmpdir))
            content = status_file.read_text()
            self.assertIn("NEW-001", content)
            self.assertNotIn("OLD-001", content)
            self.assertIn("## Other", content)


class TestBH008NestedArrays(unittest.TestCase):
    """BH-008: TOML parser handles nested arrays."""

    def test_nested_arrays_parsed(self):
        toml = '[test]\nkey = [["a", "b"], ["c", "d"]]'
        result = validate_config.parse_simple_toml(toml)
        val = result.get("test", {}).get("key", [])
        self.assertEqual(len(val), 2)
        self.assertEqual(val[0], ["a", "b"])
        self.assertEqual(val[1], ["c", "d"])


class TestBH009FmValEscape(unittest.TestCase):
    """BH-009: _fm_val unescapes quotes like read_tf."""

    def test_escaped_quotes_unescaped(self):
        fm = 'title: "He said \\"hello\\" to her"'
        result = update_burndown._fm_val(fm, "title")
        self.assertEqual(result, 'He said "hello" to her')

    def test_plain_value_unchanged(self):
        fm = 'title: "Simple title"'
        result = update_burndown._fm_val(fm, "title")
        self.assertEqual(result, "Simple title")


class TestBH010FlagEqualsValue(unittest.TestCase):
    """BH-010: _parse_flags handles --flag=value syntax."""

    def test_equals_syntax_parsed(self):
        result = FakeGitHub._parse_flags(["list", "--state=all"])
        self.assertIn("state", result)
        self.assertEqual(result["state"], ["all"])

    def test_space_syntax_still_works(self):
        result = FakeGitHub._parse_flags(["list", "--state", "all"])
        self.assertIn("state", result)
        self.assertEqual(result["state"], ["all"])


class TestBH011ExtractSpBoundary(unittest.TestCase):
    """BH-011: extract_sp doesn't match BSP, ISP as story points."""

    def test_standalone_sp_matches(self):
        self.assertEqual(validate_config.extract_sp({"body": "SP: 3"}), 3)

    def test_bsp_does_not_match(self):
        self.assertEqual(validate_config.extract_sp({"body": "BSP: 5"}), 0)

    def test_isp_does_not_match(self):
        self.assertEqual(validate_config.extract_sp({"body": "ISP = 3"}), 0)

    def test_story_points_still_matches(self):
        self.assertEqual(
            validate_config.extract_sp({"body": "Story Points: 8"}), 8)

    def test_start_of_line_sp(self):
        self.assertEqual(validate_config.extract_sp({"body": "sp: 5"}), 5)


class TestBH020CommitsSinceFilter(unittest.TestCase):
    """BH-020: FakeGitHub /commits endpoint respects -f since= filter."""

    def test_since_filters_old_commits(self):
        fake = FakeGitHub()
        fake.commits_data = [
            {"sha": "old", "commit": {"author": {"date": "2025-01-01T00:00:00Z"}}},
            {"sha": "new", "commit": {"author": {"date": "2026-01-01T00:00:00Z"}}},
        ]
        result = fake.handle([
            "api", "repos/test/test/commits",
            "-f", "sha=main", "-f", "since=2025-06-01T00:00:00Z",
        ])
        data = json.loads(result.stdout)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["sha"], "new")


class TestBH022FirstErrorFalsePositive(unittest.TestCase):
    """BH-022: _first_error skips lines like '0 errors'."""

    def test_zero_errors_skipped(self):
        log = "Tests: 42 passed, 0 errors\nfatal: actual error here"
        result = check_status._first_error(log)
        self.assertIn("actual error", result)
        self.assertNotIn("0 errors", result)

    def test_no_failures_skipped(self):
        log = "no failed tests\nERROR: real problem"
        result = check_status._first_error(log)
        self.assertIn("real problem", result)

    def test_real_error_still_matched(self):
        log = "ERROR: something broke"
        result = check_status._first_error(log)
        self.assertIn("something broke", result)


class TestBH023HyphenatedTomlKeys(unittest.TestCase):
    """BH-023: TOML parser accepts hyphenated bare keys."""

    def test_hyphenated_key_parsed(self):
        result = validate_config.parse_simple_toml('base-branch = "main"')
        self.assertEqual(result.get("base-branch"), "main")

    def test_underscored_key_still_works(self):
        result = validate_config.parse_simple_toml('base_branch = "main"')
        self.assertEqual(result.get("base_branch"), "main")


# ---------------------------------------------------------------------------
# BH-P11-055: check_status.py main() integration test
# ---------------------------------------------------------------------------


class TestCheckStatusMainIntegration(unittest.TestCase):
    """BH-P11-055: Integration test for check_status.main().

    Patches sys.argv, load_config, and subprocess.run (via FakeGitHub)
    to verify main() orchestrates all checks and writes a log file.
    """

    def setUp(self):
        self.gh = FakeGitHub()
        self.patched = make_patched_subprocess(self.gh)
        self._tmpdir = tempfile.TemporaryDirectory()
        self.tmpdir = self._tmpdir.name
        self._orig_cwd = os.getcwd()
        os.chdir(self.tmpdir)

        self.sprints_dir = Path(self.tmpdir) / "sprints"
        sprint_dir = self.sprints_dir / "sprint-1"
        sprint_dir.mkdir(parents=True)

        # Populate GitHub state: milestone + issues
        self.gh.milestones.append({
            "number": 1, "title": "Sprint 1: First Light",
            "state": "open", "open_issues": 1, "closed_issues": 1,
            "created_at": "2026-03-01T00:00:00Z",
        })
        self.gh.issues.extend([
            {
                "number": 1, "title": "US-0101: Story 1", "state": "closed",
                "labels": [{"name": "sp:5"}], "body": "",
                "milestone": {"title": "Sprint 1: First Light"},
                "closedAt": "2026-03-10T12:00:00Z",
            },
            {
                "number": 2, "title": "US-0102: Story 2", "state": "open",
                "labels": [{"name": "sp:3"}], "body": "",
                "milestone": {"title": "Sprint 1: First Light"},
                "closedAt": None,
            },
        ])
        # One CI run
        self.gh.runs.append({
            "status": "completed", "conclusion": "success",
            "name": "CI", "headBranch": "main", "databaseId": 1,
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

    def test_main_happy_path(self):
        """main() with explicit sprint number runs all checks and writes log."""
        config = self._make_config()

        with (
            patch("subprocess.run", self.patched),
            patch("check_status.load_config", return_value=config),
            patch("check_status.sync_backlog_main", None),
            patch("sys.argv", ["check_status.py", "1"]),
            patch("sys.stdout", new_callable=io.StringIO) as mock_out,
        ):
            # main() calls sys.exit(0) when no actions needed or sys.exit(1) when actions
            with self.assertRaises(SystemExit) as ctx:
                check_status.main()

        output = mock_out.getvalue()
        # Report header
        self.assertIn("Sprint 1 Status", output)
        # CI check ran
        self.assertIn("CI:", output)
        # Progress check ran
        self.assertIn("Progress:", output)
        # Log file was written
        self.assertIn("Log written:", output)
        # Verify log file exists on disk
        logs = list((self.sprints_dir / "sprint-1").glob("monitor-*.log"))
        self.assertGreaterEqual(len(logs), 1)
        log_text = logs[0].read_text(encoding="utf-8")
        self.assertIn("Sprint 1 Status", log_text)

    def test_main_config_error_exits_1(self):
        """main() exits 1 when load_config raises ConfigError."""
        from validate_config import ConfigError

        with (
            patch("check_status.load_config", side_effect=ConfigError("bad")),
            patch("sys.argv", ["check_status.py", "1"]),
        ):
            with self.assertRaises(SystemExit) as ctx:
                check_status.main()
            self.assertEqual(ctx.exception.code, 1)

    def test_main_non_numeric_arg_exits_2(self):
        """main() exits 2 when given a non-numeric sprint argument."""
        config = self._make_config()
        with (
            patch("check_status.load_config", return_value=config),
            patch("sys.argv", ["check_status.py", "abc"]),
        ):
            with self.assertRaises(SystemExit) as ctx:
                check_status.main()
            self.assertEqual(ctx.exception.code, 2)


# ---------------------------------------------------------------------------
# BH-P11-056: sync_tracking.py main() integration test
# ---------------------------------------------------------------------------


class TestSyncTrackingMainIntegration(unittest.TestCase):
    """BH-P11-056: Integration test for sync_tracking.main().

    Patches sys.argv, load_config, subprocess.run (via FakeGitHub), and
    find_milestone to verify main() fetches issues and creates tracking files.
    """

    def setUp(self):
        self.gh = FakeGitHub()
        self.patched = make_patched_subprocess(self.gh)
        self._tmpdir = tempfile.TemporaryDirectory()
        self.tmpdir = self._tmpdir.name
        self._orig_cwd = os.getcwd()
        os.chdir(self.tmpdir)

        self.sprints_dir = Path(self.tmpdir) / "sprints"
        self.sprints_dir.mkdir(parents=True)

        # Populate GitHub state: milestone + issues
        self.gh.milestones.append({
            "number": 1, "title": "Sprint 1: First Light",
            "state": "open", "open_issues": 2, "closed_issues": 0,
        })
        self.gh.issues.extend([
            {
                "number": 1, "title": "US-0101: Setup CI",
                "state": "open", "body": "Set up CI pipeline",
                "labels": [{"name": "kanban:dev"}, {"name": "sp:3"}],
                "milestone": {"title": "Sprint 1: First Light"},
                "closedAt": None,
            },
            {
                "number": 2, "title": "US-0102: Add auth",
                "state": "open", "body": "Add authentication",
                "labels": [{"name": "kanban:todo"}, {"name": "sp:5"}],
                "milestone": {"title": "Sprint 1: First Light"},
                "closedAt": None,
            },
        ])

    def tearDown(self):
        os.chdir(self._orig_cwd)
        self._tmpdir.cleanup()

    def _make_config(self):
        return {
            "project": {"name": "TestProj", "repo": "owner/repo"},
            "paths": {"sprints_dir": str(self.sprints_dir)},
            "ci": {"check_commands": [], "build_command": ""},
        }

    def test_main_creates_tracking_files(self):
        """main() creates tracking files for each issue in the milestone."""
        config = self._make_config()
        ms = {"number": 1, "title": "Sprint 1: First Light"}

        with (
            patch("subprocess.run", self.patched),
            patch("sync_tracking.load_config", return_value=config),
            patch("sync_tracking.find_milestone", return_value=ms),
            patch("sys.argv", ["sync_tracking.py", "1"]),
            patch("sys.stdout", new_callable=io.StringIO) as mock_out,
        ):
            sync_tracking.main()

        output = mock_out.getvalue()
        # Should report changes
        self.assertIn("Sync complete", output)
        self.assertIn("created tracking file", output)

        # Verify tracking files were created
        stories_dir = self.sprints_dir / "sprint-1" / "stories"
        tracking_files = list(stories_dir.glob("*.md"))
        self.assertEqual(len(tracking_files), 2)

        # Verify content of one tracking file
        contents = [f.read_text(encoding="utf-8") for f in tracking_files]
        all_text = "\n".join(contents)
        self.assertIn("US-0101", all_text)
        self.assertIn("US-0102", all_text)

    def test_main_idempotent_sync(self):
        """Running main() twice reports 'Everything in sync' on second run."""
        config = self._make_config()
        ms = {"number": 1, "title": "Sprint 1: First Light"}

        # First run creates files
        with (
            patch("subprocess.run", self.patched),
            patch("sync_tracking.load_config", return_value=config),
            patch("sync_tracking.find_milestone", return_value=ms),
            patch("sys.argv", ["sync_tracking.py", "1"]),
            patch("sys.stdout", new_callable=io.StringIO),
        ):
            sync_tracking.main()

        # Second run should be idempotent
        with (
            patch("subprocess.run", self.patched),
            patch("sync_tracking.load_config", return_value=config),
            patch("sync_tracking.find_milestone", return_value=ms),
            patch("sys.argv", ["sync_tracking.py", "1"]),
            patch("sys.stdout", new_callable=io.StringIO) as mock_out,
        ):
            sync_tracking.main()

        self.assertIn("Everything in sync", mock_out.getvalue())

    def test_main_no_milestone_exits_1(self):
        """main() exits 1 when no milestone is found."""
        config = self._make_config()

        with (
            patch("subprocess.run", self.patched),
            patch("sync_tracking.load_config", return_value=config),
            patch("sync_tracking.find_milestone", return_value=None),
            patch("sys.argv", ["sync_tracking.py", "99"]),
        ):
            with self.assertRaises(SystemExit) as ctx:
                sync_tracking.main()
            self.assertEqual(ctx.exception.code, 1)


class TestFakeGitHubStrictMode(unittest.TestCase):
    """BH-P11-200: FakeGitHub strict mode warns on accepted-but-unimplemented flags."""

    def test_jq_now_implemented_no_warning(self):
        """--jq on api handler is now evaluated; no strict warning."""
        fake = FakeGitHub(strict=True)
        fake.milestones.append({"number": 1, "title": "M1"})
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            # Should NOT warn since jq is now in _IMPLEMENTED_FLAGS
            fake.handle(["api", "repos/o/r/milestones", "--jq", ".[].title"])
        self.assertEqual(len(fake._strict_warnings), 0)

    def test_jq_evaluates_on_release_view(self):
        """--jq on release view extracts the url field."""
        fake = FakeGitHub(strict=True)
        result = fake.handle(["release", "view", "v1.0.0", "--jq", ".url"])
        self.assertEqual(result.returncode, 0)
        # jq should extract the raw url string
        self.assertIn("v1.0.0", result.stdout)
        self.assertNotIn("{", result.stdout)  # not JSON, raw string

    def test_strict_warns_on_release_create_target(self):
        """--target on release create is accepted but not used; strict warns."""
        fake = FakeGitHub(strict=True)
        with self.assertWarns(UserWarning):
            fake.handle([
                "release", "create", "v1.0", "--title", "Release",
                "--notes", "test", "--target", "main",
            ])
        self.assertEqual(len(fake._strict_warnings), 1)

    def test_strict_false_suppresses_warnings(self):
        """strict=False disables unimplemented-flag warnings."""
        fake = FakeGitHub(strict=False)
        fake.milestones.append({"number": 1, "title": "M1"})
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            # Should NOT raise even with warnings-as-errors
            fake.handle(["api", "repos/o/r/milestones", "--jq", ".[].title"])
        self.assertEqual(len(fake._strict_warnings), 0)

    def test_implemented_flags_no_warning(self):
        """Flags in _IMPLEMENTED_FLAGS don't trigger strict warnings."""
        fake = FakeGitHub(strict=True)
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            # --state and --json are implemented in issue_list
            fake.handle(["issue", "list", "--state", "all", "--json", "number"])
        self.assertEqual(len(fake._strict_warnings), 0)

    def test_unknown_flag_always_raises(self):
        """Unknown flags raise NotImplementedError regardless of strict mode."""
        for strict in (True, False):
            fake = FakeGitHub(strict=strict)
            with self.assertRaises(NotImplementedError):
                fake.handle(["issue", "list", "--bogus-flag", "val"])

    def test_implemented_subset_of_known(self):
        """Every _IMPLEMENTED_FLAGS entry must be a subset of _KNOWN_FLAGS."""
        for handler, impl_flags in FakeGitHub._IMPLEMENTED_FLAGS.items():
            known = FakeGitHub._KNOWN_FLAGS.get(handler, frozenset())
            extra = impl_flags - known
            self.assertEqual(
                extra, frozenset(),
                f"_IMPLEMENTED_FLAGS['{handler}'] contains flags not in "
                f"_KNOWN_FLAGS: {extra}",
            )

    def test_strict_warnings_accumulate(self):
        """Multiple strict warnings accumulate in _strict_warnings."""
        fake = FakeGitHub(strict=True)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            # --target on release create is accepted but not implemented
            fake.handle([
                "release", "create", "v1.0", "--title", "R1",
                "--notes", "test", "--target", "main",
            ])
            fake.handle([
                "release", "create", "v2.0", "--title", "R2",
                "--notes", "test", "--target", "dev",
            ])
        self.assertEqual(len(fake._strict_warnings), 2)


class TestPatchGhHelper(unittest.TestCase):
    """BH-P11-201: Tests for the call-args audit helper."""

    def test_warns_when_call_args_not_checked(self):
        """patch_gh warns if mock was called but call_args never inspected."""
        with self.assertWarns(UserWarning) as cm:
            with patch_gh("release_gate.gh_json", return_value=[]) as mock:
                # Call the mock but don't inspect call_args
                gate_prs("Sprint 1")
        self.assertIn("call_args was never inspected", str(cm.warning))

    def test_no_warning_when_call_args_checked(self):
        """patch_gh does not warn when call_args is inspected."""
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            with patch_gh("release_gate.gh_json", return_value=[]) as mock:
                gate_prs("Sprint 1")
                _ = mock.call_args  # inspect call_args

    def test_no_warning_when_assert_called_with_used(self):
        """patch_gh recognizes assert_called_with as verification."""
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            with patch_gh("release_gate.gh_json", return_value=[]) as mock:
                gate_prs("Sprint 1")
                mock.assert_called_once_with(mock.call_args[0][0])

    def test_no_warning_when_mock_not_called(self):
        """patch_gh does not warn if mock was never called."""
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            with patch_gh("release_gate.gh_json", return_value=[]):
                pass  # never call the mock

    def test_monitored_mock_delegates_return_value(self):
        """MonitoredMock proxies return_value correctly."""
        from unittest.mock import MagicMock
        inner = MagicMock(return_value=42)
        proxy = MonitoredMock(inner)
        result = proxy(1, 2, key="val")
        self.assertEqual(result, 42)
        self.assertTrue(inner.called)

    def test_monitored_mock_tracks_call_args_list(self):
        """Accessing call_args_list sets args_checked."""
        from unittest.mock import MagicMock
        inner = MagicMock(return_value="ok")
        proxy = MonitoredMock(inner)
        proxy("arg1")
        self.assertFalse(proxy.args_checked)
        _ = proxy.call_args_list
        self.assertTrue(proxy.args_checked)


class TestGatePRsWithPatchGh(unittest.TestCase):
    """BH-P11-201: Demo — existing gate_prs tests rewritten with patch_gh."""

    def test_no_prs_verifies_query(self):
        """gate_prs with no open PRs — verifies the query includes json fields."""
        with patch_gh("release_gate.gh_json", return_value=[]) as mock:
            ok, _ = gate_prs("Sprint 1")
            self.assertTrue(ok)
            # Verify the query parameters
            call_args = mock.call_args[0][0]
            self.assertIn("--json", call_args)

    def test_open_pr_for_milestone_verifies_query(self):
        """gate_prs with open PRs — verifies milestone filter."""
        with patch_gh("release_gate.gh_json", return_value=[
            {"number": 10, "title": "feat: thing",
             "milestone": {"title": "Sprint 1"}},
        ]) as mock:
            ok, detail = gate_prs("Sprint 1")
            self.assertFalse(ok)
            # Verify the query parameters
            call_args = mock.call_args[0][0]
            self.assertIn("--json", call_args)


if __name__ == "__main__":
    unittest.main()
