#!/usr/bin/env python3
"""Tests for sync_backlog.py — backlog auto-sync engine."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import sync_backlog


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
