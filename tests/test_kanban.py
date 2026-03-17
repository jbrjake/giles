"""Tests for kanban state machine and shared tracking file I/O."""
from __future__ import annotations

import tempfile
import textwrap
import unittest
from pathlib import Path

from validate_config import TF, read_tf, write_tf


class TestTrackingFileIO(unittest.TestCase):
    """Verify TF, read_tf, write_tf work after extraction to validate_config."""

    def test_tf_defaults(self):
        tf = TF(path=Path("/tmp/fake.md"))
        self.assertEqual(tf.status, "todo")
        self.assertEqual(tf.implementer, "")
        self.assertEqual(tf.story, "")

    def test_round_trip(self):
        """Write a tracking file and read it back."""
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "US-0001-test.md"
            tf = TF(
                path=p, story="US-0001", title="Test story",
                sprint=1, implementer="rae", reviewer="chen",
                status="dev", branch="sprint-1/US-0001-test",
                pr_number="42", issue_number="7",
            )
            write_tf(tf)
            loaded = read_tf(p)
            self.assertEqual(loaded.story, "US-0001")
            self.assertEqual(loaded.implementer, "rae")
            self.assertEqual(loaded.status, "dev")
            self.assertEqual(loaded.pr_number, "42")


if __name__ == "__main__":
    unittest.main()
