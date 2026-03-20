"""Tests for new scripts: smoke_test.py, gap_scanner.py, test_categories.py."""
from __future__ import annotations

import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from smoke_test import run_smoke, write_history
from gap_scanner import (
    scan_for_gaps, has_user_facing_keywords, get_entry_points,
)


class TestSmokeTest(unittest.TestCase):
    """P0-SCRIPT-1: Smoke test runner."""

    def test_smoke_pass_exit_zero(self):
        status, code, _, _ = run_smoke("true")
        self.assertEqual(status, "SMOKE PASS")
        self.assertEqual(code, 0)

    def test_smoke_fail_exit_nonzero(self):
        status, code, _, _ = run_smoke("false")
        self.assertEqual(status, "SMOKE FAIL")
        self.assertEqual(code, 1)

    def test_smoke_skip_not_configured(self):
        status, code, _, _ = run_smoke("")
        self.assertEqual(status, "SMOKE SKIP")
        self.assertEqual(code, 2)

    def test_smoke_timeout(self):
        status, code, _, stderr = run_smoke("sleep 60", timeout=1)
        self.assertEqual(status, "SMOKE FAIL")
        self.assertEqual(code, 1)
        self.assertIn("timed out", stderr)

    def test_smoke_history_appends(self):
        """Smoke history file is appended, not overwritten."""
        with tempfile.TemporaryDirectory() as td:
            write_history(td, "SMOKE PASS", "true")
            write_history(td, "SMOKE FAIL", "false")
            history = (Path(td) / "smoke-history.md").read_text()
            self.assertIn("SMOKE PASS", history)
            self.assertIn("SMOKE FAIL", history)
            self.assertEqual(history.count("SMOKE"), 2)

    def test_smoke_history_creates_file(self):
        """History file is created if it doesn't exist."""
        with tempfile.TemporaryDirectory() as td:
            write_history(td, "SMOKE PASS", "echo ok")
            path = Path(td) / "smoke-history.md"
            self.assertTrue(path.is_file())
            content = path.read_text()
            self.assertIn("Smoke Test History", content)


class TestGapScanner(unittest.TestCase):
    """P0-SCRIPT-2: Gap scanner."""

    def test_skip_no_entry_points(self):
        """When entry_points not configured, output contains SKIP."""
        config = {"project": {"name": "test"}, "paths": {"sprints_dir": "/tmp"}}
        report, code = scan_for_gaps(config, 1)
        self.assertIn("SKIP", report)
        self.assertEqual(code, 0)

    def test_gap_detected(self):
        """Stories that don't touch entry points trigger GAP DETECTED."""
        from validate_config import TF, write_tf
        with tempfile.TemporaryDirectory() as td:
            stories_dir = Path(td) / "sprints" / "sprint-1" / "stories"
            stories_dir.mkdir(parents=True)
            # Create 5 stories, none touching src/main.py
            for i in range(1, 6):
                tf = TF(
                    path=stories_dir / f"US-{i:04d}-test.md",
                    story=f"US-{i:04d}", title="Test story",
                    sprint=1, status="dev",
                )
                tf.body_text = "Implement parser for module X"
                write_tf(tf)
            config = {
                "project": {"entry_points": ["src/main.py"]},
                "paths": {"sprints_dir": str(Path(td) / "sprints")},
            }
            report, code = scan_for_gaps(config, 1)
            self.assertIn("GAP DETECTED", report)
            self.assertEqual(code, 1)

    def test_no_gap_when_story_touches_entry_point(self):
        """Story referencing entry point in body produces NO GAP."""
        from validate_config import TF, write_tf
        with tempfile.TemporaryDirectory() as td:
            stories_dir = Path(td) / "sprints" / "sprint-1" / "stories"
            stories_dir.mkdir(parents=True)
            tf = TF(
                path=stories_dir / "US-0001-test.md",
                story="US-0001", title="Integration", sprint=1,
            )
            tf.body_text = "Wire up src/main.py to load the new parser"
            write_tf(tf)
            config = {
                "project": {"entry_points": ["src/main.py"]},
                "paths": {"sprints_dir": str(Path(td) / "sprints")},
            }
            report, code = scan_for_gaps(config, 1)
            self.assertIn("NO GAP", report)
            self.assertEqual(code, 0)

    def test_user_facing_keywords(self):
        """Keyword scanner detects user-facing language."""
        story = {"title": "Add visible bloom effect", "body": "user sees it on screen"}
        self.assertTrue(has_user_facing_keywords(story))

    def test_no_user_facing_keywords(self):
        story = {"title": "Refactor parser internals", "body": "module cleanup"}
        self.assertFalse(has_user_facing_keywords(story))

    def test_get_entry_points_from_config(self):
        config = {"project": {"entry_points": ["src/main.py", "src/app.py"]}}
        self.assertEqual(get_entry_points(config), ["src/main.py", "src/app.py"])

    def test_get_entry_points_missing(self):
        config = {"project": {"name": "test"}}
        self.assertEqual(get_entry_points(config), [])


if __name__ == "__main__":
    unittest.main()
