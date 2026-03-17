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


# ---------------------------------------------------------------------------
# Chunk 2 tests: Transition table, preconditions, atomic writes, locking,
# story lookup
# ---------------------------------------------------------------------------

from kanban import (  # noqa: E402 — conftest.py puts scripts/ on sys.path
    TRANSITIONS,
    validate_transition,
    check_preconditions,
    atomic_write_tf,
    lock_story,
    lock_sprint,
    find_story,
)


class TestTransitionTable(unittest.TestCase):
    """TRANSITIONS dict and validate_transition() correctness."""

    def test_legal_transitions(self):
        """All documented legal single-step transitions return None."""
        legal = [
            ("todo", "design"),
            ("design", "dev"),
            ("dev", "review"),
            ("review", "dev"),
            ("review", "integration"),
            ("integration", "done"),
        ]
        for current, target in legal:
            with self.subTest(current=current, target=target):
                self.assertIsNone(
                    validate_transition(current, target),
                    f"Expected {current}→{target} to be legal",
                )

    def test_illegal_transitions(self):
        """Backward and skip transitions return error strings."""
        illegal = [
            ("todo", "dev"),
            ("todo", "review"),
            ("todo", "integration"),
            ("todo", "done"),
            ("design", "todo"),
            ("dev", "todo"),
            ("done", "todo"),
        ]
        for current, target in illegal:
            with self.subTest(current=current, target=target):
                result = validate_transition(current, target)
                self.assertIsNotNone(
                    result,
                    f"Expected {current}→{target} to be illegal",
                )
                self.assertIsInstance(result, str)

    def test_same_state_is_noop(self):
        """Transitioning to the same state returns an error."""
        for state in ("todo", "design", "dev", "review", "integration", "done"):
            with self.subTest(state=state):
                result = validate_transition(state, state)
                self.assertIsNotNone(result)

    def test_invalid_state_name(self):
        """Unknown target state names return an error."""
        self.assertIsNotNone(validate_transition("todo", "bogus"))
        self.assertIsNotNone(validate_transition("bogus", "design"))


class TestPreconditions(unittest.TestCase):
    """check_preconditions() gate logic."""

    def _tf(self, **kwargs) -> TF:
        return TF(path=Path("/tmp/fake.md"), **kwargs)

    def test_todo_to_design_requires_implementer(self):
        tf = self._tf(implementer="")
        self.assertIsNotNone(check_preconditions(tf, "design"))

    def test_todo_to_design_ok_with_implementer(self):
        tf = self._tf(implementer="rae")
        self.assertIsNone(check_preconditions(tf, "design"))

    def test_design_to_dev_requires_branch_and_pr(self):
        # missing both
        tf = self._tf(branch="", pr_number="")
        self.assertIsNotNone(check_preconditions(tf, "dev"))
        # missing only pr_number
        tf = self._tf(branch="sprint-1/US-0001-foo", pr_number="")
        self.assertIsNotNone(check_preconditions(tf, "dev"))
        # missing only branch
        tf = self._tf(branch="", pr_number="42")
        self.assertIsNotNone(check_preconditions(tf, "dev"))

    def test_design_to_dev_ok_with_branch_and_pr(self):
        tf = self._tf(branch="sprint-1/US-0001-foo", pr_number="42")
        self.assertIsNone(check_preconditions(tf, "dev"))

    def test_dev_to_review_requires_reviewer(self):
        tf = self._tf(reviewer="")
        self.assertIsNotNone(check_preconditions(tf, "review"))

    def test_dev_to_review_ok_with_both_assigned(self):
        tf = self._tf(implementer="rae", reviewer="chen")
        self.assertIsNone(check_preconditions(tf, "review"))

    def test_dev_to_review_requires_implementer(self):
        tf = self._tf(implementer="", reviewer="chen")
        self.assertIsNotNone(check_preconditions(tf, "review"))
        self.assertIn("implementer", check_preconditions(tf, "review"))

    def test_integration_to_done_requires_pr_number(self):
        tf = self._tf(pr_number="")
        self.assertIsNotNone(check_preconditions(tf, "done"))

    def test_integration_to_done_ok_with_pr_number(self):
        tf = self._tf(pr_number="99")
        self.assertIsNone(check_preconditions(tf, "done"))

    def test_unchecked_states_return_none(self):
        """States without preconditions (todo, integration) always pass."""
        tf = self._tf()  # all empty
        self.assertIsNone(check_preconditions(tf, "todo"))
        self.assertIsNone(check_preconditions(tf, "integration"))


class TestAtomicWrite(unittest.TestCase):
    """atomic_write_tf() creates a file with no leftover .tmp."""

    def test_atomic_write_creates_file(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "stories" / "US-0001-test.md"
            tf = TF(
                path=p, story="US-0001", title="Atomic test",
                sprint=2, implementer="rae", status="dev",
            )
            atomic_write_tf(tf)
            self.assertTrue(p.exists(), "tracking file should exist")
            loaded = read_tf(p)
            self.assertEqual(loaded.story, "US-0001")
            self.assertEqual(loaded.implementer, "rae")

    def test_atomic_write_no_partial_state(self):
        """After atomic_write_tf no .tmp file remains."""
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "US-0002-check.md"
            tf = TF(path=p, story="US-0002", title="Check", sprint=1)
            atomic_write_tf(tf)
            # Overwrite with new data
            tf2 = TF(path=p, story="US-0002", title="Check updated", sprint=1)
            atomic_write_tf(tf2)
            tmp = p.with_suffix(".tmp")
            self.assertFalse(tmp.exists(), ".tmp file must not remain after write")
            loaded = read_tf(p)
            self.assertEqual(loaded.title, "Check updated")


class TestFileLocking(unittest.TestCase):
    """lock_story() and lock_sprint() acquire and release without deadlock."""

    def test_lock_story_acquires_and_releases(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "US-0001-test.md"
            tf = TF(path=p, story="US-0001", title="Lock test", sprint=1)
            write_tf(tf)
            # Acquire once, release, then acquire again — no deadlock.
            with lock_story(p):
                pass
            with lock_story(p):
                pass  # second acquire must succeed

    def test_lock_sprint_acquires_and_releases(self):
        with tempfile.TemporaryDirectory() as td:
            sprint_dir = Path(td) / "sprint-1"
            sprint_dir.mkdir()
            with lock_sprint(sprint_dir):
                pass
            with lock_sprint(sprint_dir):
                pass  # second acquire must succeed

    def test_lock_sprint_creates_lock_file(self):
        with tempfile.TemporaryDirectory() as td:
            sprint_dir = Path(td) / "sprint-1"
            sprint_dir.mkdir()
            with lock_sprint(sprint_dir):
                lock_file = sprint_dir / ".kanban.lock"
                self.assertTrue(lock_file.exists())


class TestFindStory(unittest.TestCase):
    """find_story() locates a tracking file by story ID."""

    def _make_sprint_dir(self, base: Path, sprint: int) -> Path:
        d = base / f"sprint-{sprint}" / "stories"
        d.mkdir(parents=True)
        return d

    def test_finds_story_by_id(self):
        with tempfile.TemporaryDirectory() as td:
            sprints_dir = Path(td) / "sprints"
            stories_dir = self._make_sprint_dir(sprints_dir, 1)
            p = stories_dir / "US-0042-some-feature.md"
            tf = TF(path=p, story="US-0042", title="Some feature", sprint=1)
            write_tf(tf)
            result = find_story("US-0042", sprints_dir, sprint=1)
            self.assertIsNotNone(result)
            self.assertEqual(result.story, "US-0042")
            self.assertEqual(result.path, p)

    def test_returns_none_for_missing_story(self):
        with tempfile.TemporaryDirectory() as td:
            sprints_dir = Path(td) / "sprints"
            self._make_sprint_dir(sprints_dir, 1)
            result = find_story("US-9999", sprints_dir, sprint=1)
            self.assertIsNone(result)

    def test_finds_story_by_id_prefix_in_filename(self):
        """find_story matches even when filename has extra slug after the ID."""
        with tempfile.TemporaryDirectory() as td:
            sprints_dir = Path(td) / "sprints"
            stories_dir = self._make_sprint_dir(sprints_dir, 2)
            p = stories_dir / "BUG-0007-fix-login-crash.md"
            tf = TF(path=p, story="BUG-0007", title="Fix login crash", sprint=2)
            write_tf(tf)
            result = find_story("BUG-0007", sprints_dir, sprint=2)
            self.assertIsNotNone(result)
            self.assertEqual(result.story, "BUG-0007")


if __name__ == "__main__":
    unittest.main()
