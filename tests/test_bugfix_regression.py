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
    """P7-05 / BH-020: sync_backlog import guard tested behaviorally."""

    def test_import_guard_uses_import_error(self):
        """BH23-100: When sync_backlog is unavailable, check_status sets
        sync_backlog_main to None and main() skips the sync step.

        The module-level import guard at check_status.py:26-30 catches
        ImportError and sets sync_backlog_main = None.  We verify this
        degrades correctly by checking the module attribute directly.
        """
        # Verify the import guard mechanism exists
        self.assertTrue(hasattr(check_status, 'sync_backlog_main'))
        # When sync_backlog IS available, sync_backlog_main is a callable
        if check_status.sync_backlog_main is not None:
            self.assertTrue(callable(check_status.sync_backlog_main))
        # Core functions must always be available regardless
        self.assertTrue(callable(check_status.check_ci))
        self.assertTrue(callable(check_status.check_prs))
        self.assertTrue(callable(check_status.check_milestone))

    def test_import_guard_failure_path(self):
        """BH28: Actually test the failure path by temporarily hiding sync_backlog."""
        import importlib
        saved = sys.modules.get("sync_backlog")
        # Simulate sync_backlog being unavailable
        sys.modules["sync_backlog"] = None  # type: ignore[assignment]
        try:
            # Re-import check_status to trigger the import guard
            importlib.reload(check_status)
            self.assertIsNone(check_status.sync_backlog_main)
            # Core functions must still work
            self.assertTrue(callable(check_status.check_ci))
        finally:
            # Restore
            if saved is not None:
                sys.modules["sync_backlog"] = saved
            else:
                sys.modules.pop("sync_backlog", None)
            importlib.reload(check_status)


class TestCheckStatusMainArgParsing(unittest.TestCase):
    """P5-13: check_status.main() help flag."""

    def test_help_exits_0(self):
        with patch("sys.argv", ["check_status.py", "--help"]):
            with self.assertRaises(SystemExit) as ctx:
                check_status.main()
            self.assertEqual(ctx.exception.code, 0)


class TestCheckSmokExceptionNarrowing(unittest.TestCase):
    """BH33-002: check_smoke must not swallow programming errors."""

    def test_type_error_propagates(self):
        """TypeError from inside check_smoke must not be caught."""
        config = {"ci": {"smoke_command": "true"}}
        with patch("subprocess.run", side_effect=TypeError("bad arg")):
            with self.assertRaises(TypeError):
                check_status.check_smoke(config, Path(tempfile.mkdtemp()))

    def test_os_error_caught(self):
        """OSError from subprocess is caught and reported."""
        config = {"ci": {"smoke_command": "true"}}
        report, actions = check_status.check_smoke(
            config, Path(tempfile.mkdtemp()),
        )
        # We need to mock subprocess.run to raise OSError
        with patch("subprocess.run", side_effect=OSError("no such file")):
            report, actions = check_status.check_smoke(
                config, Path(tempfile.mkdtemp()),
            )
        self.assertTrue(any("error" in line for line in report))


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
    """BH-009: frontmatter_value unescapes quotes like read_tf.

    BH21-016: _fm_val wrapper removed; tests now call frontmatter_value directly.
    """

    def test_escaped_quotes_unescaped(self):
        fm = 'title: "He said \\"hello\\" to her"'
        result = validate_config.frontmatter_value(fm, "title")
        self.assertEqual(result, 'He said "hello" to her')

    def test_plain_value_unchanged(self):
        fm = 'title: "Simple title"'
        result = validate_config.frontmatter_value(fm, "title")
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


# ---------------------------------------------------------------------------
# BH-001: UnboundLocalError in bootstrap_github milestone fallback
# ---------------------------------------------------------------------------


class TestBH001MilestoneUnboundLocal(unittest.TestCase):
    """BH-001: create_milestones_on_github must not crash when a milestone
    file path exists in the list but the file is missing on disk."""

    def test_missing_milestone_file_no_crash(self):
        """If a milestone path doesn't exist on disk, skip it gracefully."""
        import bootstrap_github
        fake = FakeGitHub()
        with tempfile.TemporaryDirectory() as td:
            # Path in list but file does NOT exist
            nonexistent = os.path.join(td, "milestones", "phantom.md")
            config = {
                "paths": {"backlog_dir": os.path.join(td, "backlog")},
                "project": {"repo": "owner/repo"},
            }
            with patch("subprocess.run", make_patched_subprocess(fake)), \
                 patch("bootstrap_github.get_milestones",
                       return_value=[nonexistent]):
                # Should NOT raise UnboundLocalError — the pre-fix code
                # would crash with NameError because `text` was unbound.
                # After fix, it falls through to filename-based title.
                created = bootstrap_github.create_milestones_on_github(config)
            # It creates a milestone from the filename stem; the point is no crash
            self.assertIsInstance(created, int)


# ---------------------------------------------------------------------------
# BH-002: TOML parser must reject unquoted metacharacters
# ---------------------------------------------------------------------------


class TestBH002TomlRejectMetacharacters(unittest.TestCase):
    """BH-002: _parse_value must reject unquoted values with = [ ] { }."""

    def test_unquoted_equals_raises(self):
        """key = foo = bar should raise ValueError."""
        with self.assertRaises(ValueError) as ctx:
            validate_config.parse_simple_toml('name = foo = bar\n')
        self.assertIn("=", str(ctx.exception))

    def test_unquoted_bracket_raises(self):
        """key = foo[0] should raise ValueError."""
        with self.assertRaises(ValueError) as ctx:
            validate_config.parse_simple_toml('val = foo[0]\n')
        self.assertIn("[", str(ctx.exception))

    def test_unquoted_brace_raises(self):
        """key = {inline} should raise ValueError (not inline table support)."""
        with self.assertRaises(ValueError) as ctx:
            validate_config.parse_simple_toml('val = {inline}\n')
        self.assertIn("{", str(ctx.exception))

    def test_quoted_metacharacters_still_work(self):
        """Quoted values with metacharacters must parse normally."""
        result = validate_config.parse_simple_toml('cmd = "foo = bar"\n')
        self.assertEqual(result["cmd"], "foo = bar")

    def test_simple_unquoted_still_works(self):
        """Simple unquoted values like 'main' still parse as strings."""
        result = validate_config.parse_simple_toml('branch = main\n')
        self.assertEqual(result["branch"], "main")


# ---------------------------------------------------------------------------
# BH-003: load_config must propagate TOML parse errors
# ---------------------------------------------------------------------------


class TestBH003LoadConfigParseError(unittest.TestCase):
    """BH-003: load_config must show actual parse error, not 'missing section'."""

    def test_malformed_toml_shows_parse_error(self):
        """A TOML file with a syntax error should mention the parse failure."""
        with tempfile.TemporaryDirectory() as td:
            cfg = os.path.join(td, "sprint-config")
            os.makedirs(os.path.join(cfg, "team"))
            os.makedirs(os.path.join(cfg, "backlog", "milestones"))
            # Write malformed TOML (unterminated array)
            Path(os.path.join(cfg, "project.toml")).write_text(
                'name = [unterminated\n'
            )
            # Write required files
            Path(os.path.join(cfg, "team", "INDEX.md")).write_text(
                "| Name | Role | File |\n|---|---|---|\n"
                "| A | Dev | a.md |\n| B | Arch | b.md |\n"
            )
            Path(os.path.join(cfg, "backlog", "INDEX.md")).write_text("# Backlog\n")
            Path(os.path.join(cfg, "backlog", "milestones", "m1.md")).write_text(
                "# Sprint 1\n"
            )
            Path(os.path.join(cfg, "rules.md")).write_text("# Rules\n")
            Path(os.path.join(cfg, "development.md")).write_text("# Dev\n")
            Path(os.path.join(cfg, "team", "a.md")).write_text("# A\n")
            Path(os.path.join(cfg, "team", "b.md")).write_text("# B\n")
            with self.assertRaises(validate_config.ConfigError) as ctx:
                validate_config.load_config(cfg)
            msg = str(ctx.exception)
            # Must mention actual parse error, not just "missing section"
            self.assertTrue(
                "parse" in msg.lower() or "unterminated" in msg.lower(),
                f"Error should mention parse failure, got: {msg}"
            )


# ---------------------------------------------------------------------------
# BH-007: TOML parser must reject triple-quoted strings
# ---------------------------------------------------------------------------


class TestBH007TripleQuotedStrings(unittest.TestCase):
    """BH-007: Triple-quoted strings (\"\"\"...\"\"\") must raise, not corrupt."""

    def test_triple_double_quote_raises(self):
        with self.assertRaises(ValueError) as ctx:
            validate_config.parse_simple_toml('key = """\nfoo\n"""\n')
        self.assertIn("Multi-line", str(ctx.exception))

    def test_triple_single_quote_raises(self):
        with self.assertRaises(ValueError) as ctx:
            validate_config.parse_simple_toml("key = '''\nfoo\n'''\n")
        self.assertIn("Multi-line", str(ctx.exception))


# ---------------------------------------------------------------------------
# BH-004: Saga label discovery from saga files
# ---------------------------------------------------------------------------


class TestBH004SagaLabelFromFiles(unittest.TestCase):
    """BH-004: create_saga_labels should scan saga files when INDEX has no saga rows."""

    def test_saga_files_discovered(self):
        """Saga labels from S01-*.md files when INDEX is a routing table."""
        import bootstrap_github
        fake = FakeGitHub()
        with tempfile.TemporaryDirectory() as td:
            sagas_dir = os.path.join(td, "sagas")
            os.makedirs(sagas_dir)
            # Create saga files like hexwise fixture
            Path(os.path.join(sagas_dir, "S01-core.md")).write_text(
                "# S01 — Core Foundation\n\nSaga description.\n"
            )
            Path(os.path.join(sagas_dir, "S02-polish.md")).write_text(
                "# S02 — Polish and Shine\n\nSaga description.\n"
            )
            config = {
                "paths": {
                    "backlog_dir": os.path.join(td, "backlog"),
                    "sagas_dir": sagas_dir,
                },
            }
            # backlog INDEX has no saga rows (routing table style)
            backlog_dir = os.path.join(td, "backlog")
            os.makedirs(backlog_dir)
            Path(os.path.join(backlog_dir, "INDEX.md")).write_text(
                "| Artifact | Path |\n|---|---|\n| Milestones | milestones/ |\n"
            )
            with patch("subprocess.run", make_patched_subprocess(fake)):
                bootstrap_github.create_saga_labels(config)
            # Should have created saga:S01 and saga:S02 labels
            self.assertIn("saga:S01", fake.labels)
            self.assertIn("saga:S02", fake.labels)


# ---------------------------------------------------------------------------
# BH-006: Story ID regex matches without colon
# ---------------------------------------------------------------------------


class TestBH006StoryIdRegexConsistency(unittest.TestCase):
    """BH-006: get_existing_issues must match IDs without colons."""

    def test_matches_id_without_colon(self):
        """Issue titled 'US-0001 Setup' should be detected as existing."""
        import populate_issues
        with patch("populate_issues.gh_json", return_value=[
            {"title": "US-0001 Setup CI"},
            {"title": "US-0002: Core feature"},
        ]):
            existing = populate_issues.get_existing_issues()
        self.assertIn("US-0001", existing)  # no colon
        self.assertIn("US-0002", existing)  # with colon


# ---------------------------------------------------------------------------
# BH-016: kanban_from_labels picks most advanced state
# ---------------------------------------------------------------------------


class TestBH016KanbanMultipleLabels(unittest.TestCase):
    """BH-016: kanban_from_labels should prefer most advanced state."""

    def test_multiple_kanban_labels_picks_most_advanced(self):
        """With kanban:dev and kanban:review, should return review."""
        issue = {
            "labels": [{"name": "kanban:dev"}, {"name": "kanban:review"}],
            "state": "open",
        }
        result = validate_config.kanban_from_labels(issue)
        # review is more advanced than dev in the pipeline
        self.assertEqual(result, "review")

    def test_single_kanban_label_unchanged(self):
        """Normal single-label case should still work."""
        issue = {
            "labels": [{"name": "kanban:design"}],
            "state": "open",
        }
        result = validate_config.kanban_from_labels(issue)
        self.assertEqual(result, "design")


# ---------------------------------------------------------------------------
# BH-018: reorder_stories idempotency
# ---------------------------------------------------------------------------

import manage_epics


class TestBH018ReorderIdempotency(unittest.TestCase):
    """BH-018: reorder_stories must be idempotent — same order twice = same file."""

    def test_reorder_same_order_twice_is_idempotent(self):
        """Reordering with the same order twice must produce identical output."""
        with tempfile.TemporaryDirectory() as td:
            epic_path = os.path.join(td, "epic.md")
            Path(epic_path).write_text(
                "# Epic: Test\n\n| Field | Value |\n|---|---|\n| Sprints | 1 |\n\n"
                "---\n\n### US-0001: First story\n\nBody of first.\n\n"
                "---\n\n### US-0002: Second story\n\nBody of second.\n"
            )
            manage_epics.reorder_stories(epic_path, ["US-0001", "US-0002"])
            after_first = Path(epic_path).read_text()
            manage_epics.reorder_stories(epic_path, ["US-0001", "US-0002"])
            after_second = Path(epic_path).read_text()
            self.assertEqual(after_first, after_second,
                             "Reorder with same order should be idempotent")


# ---------------------------------------------------------------------------
# BH-021: sync_backlog state not updated on partial failure
# ---------------------------------------------------------------------------


class TestBH021SyncBacklogPartialFailure(unittest.TestCase):
    """BH-021: do_sync failure must NOT update file_hashes in state."""

    def test_state_not_updated_on_do_sync_failure(self):
        """BH19-002: Actually call main() with do_sync failing.

        Previous version was test theater: saved/loaded state without calling
        main(). This version triggers the real failure path in sync_backlog.main().
        """
        import sync_backlog
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            cfg = root / "sprint-config"
            cfg.mkdir()
            backlog = cfg / "backlog"
            backlog.mkdir()
            ms_dir = backlog / "milestones"
            ms_dir.mkdir()
            (ms_dir / "m1.md").write_text("# Sprint 1\n### Sprint 1: X\n| US-0001 | T | S01 | 3 | P1 |\n")
            (backlog / "INDEX.md").write_text("# Backlog\n")
            (cfg / "rules.md").write_text("# Rules\n")
            (cfg / "development.md").write_text("# Dev\n")
            (cfg / "definition-of-done.md").write_text("# DoD\n")
            team = cfg / "team"
            team.mkdir()
            (team / "INDEX.md").write_text(
                "| Name | Role | File |\n|---|---|---|\n"
                "| A | Dev | a.md |\n| B | Rev | b.md |\n"
            )
            (team / "a.md").write_text("# A\n")
            (team / "b.md").write_text("# B\n")
            (cfg / "project.toml").write_text(
                f'[project]\nname = "test"\nrepo = "o/r"\nlanguage = "py"\n\n'
                f'[paths]\nteam_dir = "{team}"\nbacklog_dir = "{backlog}"\n'
                f'sprints_dir = "{root / "sprints"}"\n\n'
                f'[ci]\ncheck_commands = ["true"]\nbuild_command = "true"\n'
            )
            # Seed state with old hashes so check_sync returns "sync"
            old_hashes = sync_backlog.hash_milestone_files([str(ms_dir / "m1.md")])
            state = {
                "file_hashes": {"different": "hash"},
                "pending_hashes": old_hashes,
                "last_sync_at": None,
            }
            sync_backlog.save_state(cfg, state)
            # Mock do_sync to raise
            with patch.object(sync_backlog, "do_sync", side_effect=RuntimeError("boom")), \
                 patch("os.getcwd", return_value=str(root)), \
                 patch.object(sync_backlog, "load_config",
                              return_value=sync_backlog.load_config(str(cfg))):
                result = sync_backlog.main()
            self.assertEqual(result, "error")
            # Key assertion: file_hashes must NOT be updated to current hashes
            loaded = sync_backlog.load_state(cfg)
            self.assertNotEqual(loaded["file_hashes"], old_hashes,
                                "State should not be updated when do_sync fails")
            self.assertEqual(loaded["file_hashes"], {"different": "hash"},
                             "file_hashes should retain pre-failure value")

    def test_state_file_roundtrip(self):
        """State file save/load roundtrip (separated from failure test)."""
        import sync_backlog
        with tempfile.TemporaryDirectory() as td:
            cfg = Path(td) / "sprint-config"
            cfg.mkdir()
            state = {"file_hashes": {"old": "hash"}, "pending_hashes": None,
                     "last_sync_at": "2026-01-01T00:00:00+00:00"}
            sync_backlog.save_state(cfg, state)
            loaded = sync_backlog.load_state(cfg)
            self.assertEqual(loaded["file_hashes"], {"old": "hash"})


# ---------------------------------------------------------------------------
# BH-017: sprint_init preserves existing project.toml
# ---------------------------------------------------------------------------


class TestBH017ProjectTomlPreserved(unittest.TestCase):
    """BH-017: sprint_init must not overwrite existing project.toml."""

    def test_existing_project_toml_preserved(self):
        """Re-running init should skip project.toml if it already exists."""
        from sprint_init import ConfigGenerator, ProjectScanner
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            config_dir = root / "sprint-config"
            config_dir.mkdir()
            # Write a "user-edited" project.toml
            toml = config_dir / "project.toml"
            toml.write_text('[project]\nname = "my-edits"\n')
            # Create a minimal scanner and ConfigGenerator
            scanner = ProjectScanner(str(root))
            scan = scanner.scan()
            gen = ConfigGenerator(scan)
            # Override config_dir to our temp dir
            gen.config_dir = config_dir
            gen.generate_project_toml()
            # Must preserve user content, not overwrite
            content = toml.read_text()
            self.assertIn("my-edits", content,
                          "project.toml should preserve user edits on re-run")


# ---------------------------------------------------------------------------
# P17 Mutation killers — tests that prevent surviving mutations
# ---------------------------------------------------------------------------


class TestP17SyncTrackingWritePersistence(unittest.TestCase):
    """BH-002: sync_one changes MUST be written to disk, not just in memory."""

    def test_sync_writes_status_change_to_disk(self):
        """After syncing a closed issue, the tracking file on disk must reflect 'done'."""
        with tempfile.TemporaryDirectory() as td:
            stories_dir = Path(td) / "sprint-1"
            stories_dir.mkdir()
            # Create a tracking file with status: dev
            tf_path = stories_dir / "us-0001-setup.md"
            tf_path.write_text(
                "---\nstory: US-0001\ntitle: Setup\nstatus: dev\n"
                "sprint: 1\nissue_number: 1\n---\nBody text.\n"
            )
            # Simulate a closed issue
            issue = {
                "number": 1, "title": "US-0001: Setup", "state": "closed",
                "labels": [{"name": "kanban:done"}],
                "closedAt": "2026-03-15T12:00:00Z", "body": "",
            }
            tf = sync_tracking.read_tf(tf_path)
            changes = sync_tracking.sync_one(tf, issue, pr=None, sprint=1)
            if changes:
                sync_tracking.write_tf(tf)
            # Read back from DISK — the whole point of this test
            disk_content = tf_path.read_text()
            self.assertIn("status: done", disk_content,
                          "Status change must be persisted to disk")


class TestP17YamlSafeRoundtrip(unittest.TestCase):
    """BH-003: _yaml_safe must be exercised by adversarial titles."""

    def test_title_with_colon_roundtrips(self):
        """A title containing ': ' must survive write→read via TF."""
        with tempfile.TemporaryDirectory() as td:
            tf_path = Path(td) / "test.md"
            title = "US-0001: Fix the thing: edge case"
            tf = sync_tracking.TF(path=tf_path, story="US-0001",
                                  title=title, status="todo", sprint=1)
            sync_tracking.write_tf(tf)
            recovered = sync_tracking.read_tf(tf_path)
            self.assertEqual(recovered.title, title,
                             "Title with colons must roundtrip through write/read")

    def test_title_with_hash_roundtrips(self):
        """A title containing '#' must survive write→read via TF."""
        with tempfile.TemporaryDirectory() as td:
            tf_path = Path(td) / "test.md"
            title = "Fix #42 bug in parser"
            tf = sync_tracking.TF(path=tf_path, story="US-0042",
                                  title=title, status="dev", sprint=1)
            sync_tracking.write_tf(tf)
            recovered = sync_tracking.read_tf(tf_path)
            self.assertEqual(recovered.title, title)


class TestP17BurndownTableHeader(unittest.TestCase):
    """BH-004: Burndown output must contain the table header row."""

    def test_burndown_contains_table_header(self):
        """write_burndown output must include column headers."""
        rows = [
            {"story_id": "US-0001", "short_title": "Setup", "sp": 3,
             "status": "done", "closed": "2026-03-15", "assignee": "—",
             "pr": "—"},
        ]
        with tempfile.TemporaryDirectory() as td:
            sprints_dir = Path(td)
            now = datetime(2026, 3, 16, tzinfo=timezone.utc)
            update_burndown.write_burndown(1, rows, now, sprints_dir)
            content = (sprints_dir / "sprint-1" / "burndown.md").read_text()
            self.assertIn("| Story ", content,
                          "Burndown must contain table header row")
            self.assertIn("| SP ", content)


class TestP17FormatIssueBodySP(unittest.TestCase):
    """BH-005: format_issue_body must include story points."""

    def test_sp_present_in_body(self):
        """Issue body must contain the SP value."""
        import populate_issues
        story = populate_issues.Story(
            story_id="US-0001", title="Test story", saga="S01",
            sprint=1, sp=5, priority="P0",
        )
        body = populate_issues.format_issue_body(story)
        self.assertIn("5 SP", body,
                      "Issue body must contain story points")


class TestP17CIPythonVersion(unittest.TestCase):
    """BH-006: Generated CI must use Python 3.x, not 2.7."""

    def test_python_ci_uses_python3(self):
        """Python project CI must specify a Python 3.x version."""
        from setup_ci import generate_ci_yaml
        config = {
            "project": {"language": "python", "name": "test"},
            "ci": {"check_commands": ["pytest"], "build_command": ""},
        }
        yaml = generate_ci_yaml(config)
        self.assertIn("python-version", yaml)
        self.assertNotIn("2.7", yaml, "CI must not use Python 2.7")
        # Must reference Python 3.x
        self.assertRegex(yaml, r'python-version.*3\.',
                         "CI must use Python 3.x")


class TestP17DetectSprintSpecificity(unittest.TestCase):
    """BH-012: detect_sprint must match 'Current Sprint:' not just 'Sprint:'."""

    def test_current_sprint_not_confused_with_narrative(self):
        """Status file with 'Sprint 2 recap' and 'Current Sprint: 3' returns 3."""
        with tempfile.TemporaryDirectory() as td:
            status = Path(td) / "SPRINT-STATUS.md"
            status.write_text(
                "# Sprint 2 Recap\n\nGood sprint.\n\nCurrent Sprint: 3\n"
            )
            result = validate_config.detect_sprint(Path(td))
            self.assertEqual(result, 3,
                             "Must return Current Sprint value, not narrative Sprint mention")


class TestP17ReviewRoundsExcludesCommented(unittest.TestCase):
    """BH-007: compute_review_rounds must not count COMMENTED reviews."""

    def test_commented_review_not_counted(self):
        """COMMENTED reviews should not count as review rounds."""
        fake = FakeGitHub()
        # Create milestone and PR
        fake.handle(["api", "repos/o/r/milestones", "-f", "title=Sprint 1"])
        fake.handle([
            "pr", "create", "--title", "feat: thing",
            "--head", "feat-thing", "--milestone", "Sprint 1",
        ])
        # Add reviews: 1 APPROVED, 1 COMMENTED (should not count)
        fake.handle(["pr", "review", "1", "--approve", "--body", "LGTM"])
        # Manually add a COMMENTED review (FakeGitHub doesn't have a flag for this)
        pr = fake.prs[0]
        pr.setdefault("reviews", []).append({
            "pr_number": 1, "state": "COMMENTED", "body": "Just a note",
        })
        # compute_review_rounds filters: only APPROVED + CHANGES_REQUESTED
        # With the mutation (count all), rounds = 2. Correct: rounds = 1.
        with patch("subprocess.run", make_patched_subprocess(fake)):
            result = sprint_analytics.compute_review_rounds("Sprint 1")
        self.assertEqual(result["avg_rounds"], 1.0,
                         "COMMENTED reviews must not count as rounds")

    def test_commented_only_reviews_zero_rounds(self):
        """BH18-006: PR with only COMMENTED reviews should show 0 rounds."""
        fake = FakeGitHub()
        fake.handle(["api", "repos/o/r/milestones", "-f", "title=Sprint 1"])
        fake.handle([
            "pr", "create", "--title", "feat: thing",
            "--head", "feat-thing", "--milestone", "Sprint 1",
        ])
        # Add only COMMENTED reviews — no APPROVED or CHANGES_REQUESTED
        pr = fake.prs[0]
        pr["reviews"] = [
            {"pr_number": 1, "state": "COMMENTED", "body": "Looks interesting"},
            {"pr_number": 1, "state": "COMMENTED", "body": "Have you considered..."},
        ]
        with patch("subprocess.run", make_patched_subprocess(fake)):
            result = sprint_analytics.compute_review_rounds("Sprint 1")
        # COMMENTED-only PRs should NOT count as having review rounds
        self.assertEqual(result["avg_rounds"], 0.0,
                         "COMMENTED-only reviews must not count as review rounds")
        self.assertEqual(result["max_rounds"], 0)


class TestP17AddStorySeparator(unittest.TestCase):
    """BH-008: add_story must include --- separator before new story."""

    def test_separator_before_new_story(self):
        """New story must be preceded by a --- separator."""
        with tempfile.TemporaryDirectory() as td:
            epic_path = os.path.join(td, "epic.md")
            Path(epic_path).write_text(
                "# Epic: Test\n\n| Field | Value |\n|---|---|\n| Sprints | 1 |\n\n"
                "---\n\n### US-0001: First\n\nBody.\n"
            )
            story_data = {
                "id": "US-0002", "title": "Second story",
                "sp": 3, "priority": "P1",
            }
            manage_epics.add_story(epic_path, story_data)
            content = Path(epic_path).read_text()
            self.assertIn("---\n\n### US-0002:", content,
                          "New story must be preceded by --- separator")


if __name__ == "__main__":
    unittest.main()
