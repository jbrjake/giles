#!/usr/bin/env python3
"""Tests for sync_backlog.py — backlog auto-sync engine."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))

import sync_backlog
from fake_github import FakeGitHub, make_patched_subprocess


class TestHashMilestoneFiles(unittest.TestCase):
    """Test file hashing for change detection."""

    def test_hashes_single_file(self):
        with tempfile.TemporaryDirectory() as td:
            ms_dir = Path(td) / "milestones"
            ms_dir.mkdir()
            (ms_dir / "milestone-1.md").write_text("# Sprint 1\nstories here")
            result = sync_backlog.hash_milestone_files([str(ms_dir / "milestone-1.md")])
            self.assertIn("milestone-1.md", result)
            self.assertEqual(len(result["milestone-1.md"]), 64)  # sha256 hex

    def test_hashes_change_on_edit(self):
        with tempfile.TemporaryDirectory() as td:
            ms_dir = Path(td) / "milestones"
            ms_dir.mkdir()
            f = ms_dir / "milestone-1.md"
            f.write_text("version 1")
            h1 = sync_backlog.hash_milestone_files([str(f)])
            f.write_text("version 2")
            h2 = sync_backlog.hash_milestone_files([str(f)])
            self.assertNotEqual(h1["milestone-1.md"], h2["milestone-1.md"])

    def test_missing_file_skipped(self):
        result = sync_backlog.hash_milestone_files(["/nonexistent/file.md"])
        self.assertEqual(result, {})


class TestStateFile(unittest.TestCase):
    """Test .sync-state.json persistence."""

    def test_load_missing_returns_defaults(self):
        with tempfile.TemporaryDirectory() as td:
            state = sync_backlog.load_state(Path(td))
            self.assertEqual(state["file_hashes"], {})
            self.assertIsNone(state["pending_hashes"])
            self.assertIsNone(state["last_sync_at"])

    def test_round_trip(self):
        with tempfile.TemporaryDirectory() as td:
            state = {
                "file_hashes": {"m1.md": "abc123"},
                "pending_hashes": None,
                "last_sync_at": "2026-03-10T12:00:00+00:00",
            }
            sync_backlog.save_state(Path(td), state)
            loaded = sync_backlog.load_state(Path(td))
            self.assertEqual(loaded, state)

    def test_corrupt_file_returns_defaults(self):
        with tempfile.TemporaryDirectory() as td:
            (Path(td) / sync_backlog.STATE_FILENAME).write_text("not json")
            state = sync_backlog.load_state(Path(td))
            self.assertEqual(state["file_hashes"], {})


class TestCheckSync(unittest.TestCase):
    """Test the debounce + throttle scheduling algorithm."""

    def _make_hashes(self, content: str = "v1") -> dict[str, str]:
        """Helper: create a simple hash dict."""
        import hashlib
        h = hashlib.sha256(content.encode()).hexdigest()
        return {"milestone-1.md": h}

    def test_no_change_returns_no_changes(self):
        """When hashes match stored state, report no changes."""
        hashes = self._make_hashes("v1")
        state = {"file_hashes": hashes.copy(), "pending_hashes": None, "last_sync_at": None}
        result = sync_backlog.check_sync(hashes, state, datetime.now(timezone.utc))
        self.assertEqual(result.status, "no_changes")
        self.assertFalse(result.should_sync)

    def test_first_change_triggers_debounce(self):
        """First detection of changed files sets pending, doesn't sync."""
        old = self._make_hashes("v1")
        new = self._make_hashes("v2")
        state = {"file_hashes": old, "pending_hashes": None, "last_sync_at": None}
        result = sync_backlog.check_sync(new, state, datetime.now(timezone.utc))
        self.assertEqual(result.status, "debouncing")
        self.assertFalse(result.should_sync)
        self.assertEqual(state["pending_hashes"], new)

    def test_still_changing_re_debounces(self):
        """If files changed again since pending, update pending, don't sync."""
        old = self._make_hashes("v1")
        pending = self._make_hashes("v2")
        newest = self._make_hashes("v3")
        state = {"file_hashes": old, "pending_hashes": pending, "last_sync_at": None}
        result = sync_backlog.check_sync(newest, state, datetime.now(timezone.utc))
        self.assertEqual(result.status, "debouncing")
        self.assertFalse(result.should_sync)
        self.assertEqual(state["pending_hashes"], newest)

    def test_stabilized_triggers_sync(self):
        """When current hashes match pending, sync should fire."""
        old = self._make_hashes("v1")
        pending = self._make_hashes("v2")
        state = {"file_hashes": old, "pending_hashes": pending.copy(), "last_sync_at": None}
        result = sync_backlog.check_sync(pending, state, datetime.now(timezone.utc))
        self.assertEqual(result.status, "sync")
        self.assertTrue(result.should_sync)

    def test_revert_cancels_pending(self):
        """If files revert to stored state while pending, cancel the sync."""
        original = self._make_hashes("v1")
        pending = self._make_hashes("v2")
        state = {"file_hashes": original, "pending_hashes": pending, "last_sync_at": None}
        result = sync_backlog.check_sync(original, state, datetime.now(timezone.utc))
        self.assertEqual(result.status, "no_changes")
        self.assertFalse(result.should_sync)
        self.assertIsNone(state["pending_hashes"])

    def test_throttle_blocks_sync(self):
        """When last sync was recent, skip even if files changed."""
        old = self._make_hashes("v1")
        new = self._make_hashes("v2")
        recent = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
        state = {"file_hashes": old, "pending_hashes": new.copy(), "last_sync_at": recent}
        result = sync_backlog.check_sync(new, state, datetime.now(timezone.utc))
        self.assertEqual(result.status, "throttled")
        self.assertFalse(result.should_sync)

    def test_throttle_expired_allows_sync(self):
        """When last sync was long ago, allow sync."""
        old = self._make_hashes("v1")
        pending = self._make_hashes("v2")
        old_time = (datetime.now(timezone.utc) - timedelta(minutes=15)).isoformat()
        state = {"file_hashes": old, "pending_hashes": pending.copy(), "last_sync_at": old_time}
        result = sync_backlog.check_sync(pending, state, datetime.now(timezone.utc))
        self.assertEqual(result.status, "sync")
        self.assertTrue(result.should_sync)


class TestDoSync(unittest.TestCase):
    """Test that do_sync calls bootstrap + populate correctly."""

    def _write_config_and_milestones(self, td: str) -> dict:
        """Set up a minimal sprint-config in td, return config dict."""
        root = Path(td)
        config_dir = root / "sprint-config"
        config_dir.mkdir()
        backlog = config_dir / "backlog"
        backlog.mkdir()
        ms_dir = backlog / "milestones"
        ms_dir.mkdir()
        (ms_dir / "milestone-1.md").write_text(
            "# Milestone 1: Walking Skeleton\n\n"
            "### Sprint 1: Foundation\n\n"
            "| ID | Title | Saga | SP | Pri |\n"
            "|------|-------|------|----|----- |\n"
            "| US-0001 | Setup CI | S01 | 3 | P1 |\n"
            "| US-0002 | Add auth | S01 | 5 | P1 |\n"
        )
        config = {
            "project": {"name": "test", "repo": "owner/repo", "language": "python"},
            "paths": {"backlog_dir": str(backlog), "team_dir": str(config_dir / "team"),
                       "sprints_dir": str(root / "sprints")},
            "ci": {"check_commands": ["pytest"], "build_command": "echo ok"},
        }
        return config

    def test_do_sync_creates_milestones_and_issues(self):
        fake_gh = FakeGitHub()
        with tempfile.TemporaryDirectory() as td:
            config = self._write_config_and_milestones(td)
            with patch("subprocess.run", make_patched_subprocess(fake_gh)):
                created = sync_backlog.do_sync(config)
            self.assertGreater(len(fake_gh.milestones), 0)
            self.assertGreater(len(fake_gh.issues), 0)
            # Verify return counts match actual FakeGitHub state
            self.assertEqual(created["milestones"], len(fake_gh.milestones))
            self.assertEqual(created["issues"], len(fake_gh.issues))

    def test_do_sync_idempotent(self):
        """Running do_sync twice doesn't duplicate issues."""
        fake_gh = FakeGitHub()
        with tempfile.TemporaryDirectory() as td:
            config = self._write_config_and_milestones(td)
            with patch("subprocess.run", make_patched_subprocess(fake_gh)):
                sync_backlog.do_sync(config)
                count_after_first = len(fake_gh.issues)
                sync_backlog.do_sync(config)
                count_after_second = len(fake_gh.issues)
            self.assertEqual(count_after_first, count_after_second)


class TestMain(unittest.TestCase):
    """Test the main() entry point end-to-end."""

    def _setup_project(self, td: str) -> Path:
        """Create minimal sprint-config with project.toml + milestone."""
        root = Path(td)
        config_dir = root / "sprint-config"
        config_dir.mkdir()
        backlog = config_dir / "backlog"
        backlog.mkdir()
        ms_dir = backlog / "milestones"
        ms_dir.mkdir()
        (ms_dir / "milestone-1.md").write_text(
            "# Milestone 1: Walking Skeleton\n\n"
            "### Sprint 1: Foundation\n\n"
            "| ID | Title | Saga | SP | Pri |\n"
            "|------|-------|------|----|----- |\n"
            "| US-0001 | Setup CI | S01 | 3 | P1 |\n"
        )
        (backlog / "INDEX.md").write_text("| Saga | Name |\n|---|---|\n")
        (config_dir / "rules.md").write_text("# Rules\n")
        (config_dir / "development.md").write_text("# Development\n")
        team_dir = config_dir / "team"
        team_dir.mkdir()
        (team_dir / "INDEX.md").write_text(
            "| Name | Role | File |\n|---|---|---|\n"
            "| Alice | Dev | alice.md |\n"
            "| Bob | Reviewer | bob.md |\n"
        )
        (team_dir / "alice.md").write_text("# Alice\nDeveloper persona.\n")
        (team_dir / "bob.md").write_text("# Bob\nReviewer persona.\n")
        (config_dir / "project.toml").write_text(
            '[project]\nname = "test"\nrepo = "o/r"\nlanguage = "python"\n\n'
            f'[paths]\nteam_dir = "{team_dir}"\nbacklog_dir = "{backlog}"\n'
            f'sprints_dir = "{root / "sprints"}"\n\n'
            '[ci]\ncheck_commands = ["pytest"]\nbuild_command = "echo ok"\n'
        )
        return config_dir

    def test_first_run_debounces(self):
        """First invocation with no prior state detects change and debounces."""
        fake_gh = FakeGitHub()
        with tempfile.TemporaryDirectory() as td:
            config_dir = self._setup_project(td)
            import os
            old_cwd = os.getcwd()
            try:
                os.chdir(td)
                with patch("subprocess.run", make_patched_subprocess(fake_gh)):
                    status = sync_backlog.main()
                self.assertEqual(status, "debouncing")
                # No issues created yet (debouncing)
                self.assertEqual(len(fake_gh.issues), 0)
            finally:
                os.chdir(old_cwd)

    def test_second_run_syncs(self):
        """Second invocation (stable files) performs the sync."""
        fake_gh = FakeGitHub()
        with tempfile.TemporaryDirectory() as td:
            config_dir = self._setup_project(td)
            import os
            old_cwd = os.getcwd()
            try:
                os.chdir(td)
                with patch("subprocess.run", make_patched_subprocess(fake_gh)):
                    sync_backlog.main()  # debounce
                    status = sync_backlog.main()  # sync
                self.assertEqual(status, "sync")
                self.assertGreater(len(fake_gh.issues), 0)
            finally:
                os.chdir(old_cwd)

    def test_third_run_no_changes(self):
        """After sync, if nothing changed, report no_changes."""
        fake_gh = FakeGitHub()
        with tempfile.TemporaryDirectory() as td:
            config_dir = self._setup_project(td)
            import os
            old_cwd = os.getcwd()
            try:
                os.chdir(td)
                with patch("subprocess.run", make_patched_subprocess(fake_gh)):
                    sync_backlog.main()  # debounce
                    sync_backlog.main()  # sync
                    status = sync_backlog.main()  # no changes
                self.assertEqual(status, "no_changes")
            finally:
                os.chdir(old_cwd)
