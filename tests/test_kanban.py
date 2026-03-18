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
    do_transition,
    do_assign,
    do_sync,
    do_status,
)
from gh_test_helpers import patch_gh


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


# ---------------------------------------------------------------------------
# Chunk 3 tests: do_transition, do_assign, do_sync, do_status
# ---------------------------------------------------------------------------

class TestTransitionCommand(unittest.TestCase):
    """do_transition() updates local state and syncs to GitHub."""

    def _make_tf(self, td: str, **kwargs) -> TF:
        stories_dir = Path(td) / "sprint-1" / "stories"
        stories_dir.mkdir(parents=True, exist_ok=True)
        p = stories_dir / "US-0042-feature.md"
        defaults = dict(
            path=p, story="US-0042", title="Feature", sprint=1,
            status="todo", implementer="rae", issue_number="42",
        )
        defaults.update(kwargs)
        tf = TF(**defaults)
        write_tf(tf)
        return tf

    def test_transition_updates_local_and_github(self):
        """Successful transition updates local file and calls gh with label swap."""
        with tempfile.TemporaryDirectory() as td:
            tf = self._make_tf(td)
            with patch_gh("kanban.gh") as mock:
                result = do_transition(tf, "design")
                self.assertTrue(result)
                # Local state updated
                loaded = read_tf(tf.path)
                self.assertEqual(loaded.status, "design")
                # Verify label swap args were passed to gh
                calls_str = str(mock.call_args_list)
                self.assertIn("kanban:todo", calls_str)
                self.assertIn("kanban:design", calls_str)

    def test_transition_reverts_on_github_failure(self):
        """RuntimeError from gh reverts local file to old status."""
        with tempfile.TemporaryDirectory() as td:
            tf = self._make_tf(td)
            with patch_gh("kanban.gh", side_effect=RuntimeError("API error")) as mock:
                result = do_transition(tf, "design")
                self.assertFalse(result)
                # Local state must be reverted
                loaded = read_tf(tf.path)
                self.assertEqual(loaded.status, "todo")
                # Verify the mock was called (and thus call_args is meaningful)
                self.assertIn("issue", str(mock.call_args))

    def test_transition_to_done_closes_issue(self):
        """Transitioning to done calls both label swap and issue close."""
        with tempfile.TemporaryDirectory() as td:
            tf = self._make_tf(
                td, status="integration", pr_number="99",
                implementer="rae", reviewer="chen",
            )
            calls_made = []

            def capture_gh(args):
                calls_made.append(list(args))
                return ""

            with patch_gh("kanban.gh", side_effect=capture_gh) as mock:
                result = do_transition(tf, "done")
                self.assertTrue(result)
                # Verify both label swap and close were issued
                all_calls = str(mock.call_args_list)
                self.assertIn("kanban:done", all_calls)
                # Find the close call
                close_calls = [c for c in calls_made if "close" in c]
                self.assertTrue(close_calls, "gh issue close must be called for done")


class TestAssignCommand(unittest.TestCase):
    """do_assign() updates local file and adds persona labels on GitHub."""

    def _make_tf(self, td: str, **kwargs) -> TF:
        stories_dir = Path(td) / "sprint-1" / "stories"
        stories_dir.mkdir(parents=True, exist_ok=True)
        p = stories_dir / "US-0043-assign-test.md"
        defaults = dict(
            path=p, story="US-0043", title="Assign test", sprint=1,
            status="todo", issue_number="43",
        )
        defaults.update(kwargs)
        tf = TF(**defaults)
        write_tf(tf)
        return tf

    def test_assign_reverts_on_github_failure(self):
        """RuntimeError from gh reverts local file to old personas."""
        with tempfile.TemporaryDirectory() as td:
            tf = self._make_tf(td, implementer="old-impl")
            with patch_gh("kanban.gh", side_effect=RuntimeError("API error")) as mock:
                result = do_assign(tf, implementer="new-impl")
                self.assertFalse(result)
                loaded = read_tf(tf.path)
                self.assertEqual(loaded.implementer, "old-impl")
                self.assertIn("issue", str(mock.call_args))

    def test_assign_implementer(self):
        """Assigning implementer adds persona label and updates local file."""
        with tempfile.TemporaryDirectory() as td:
            tf = self._make_tf(td)

            def gh_side_effect(args):
                if "view" in args:
                    return {"body": "> **[Unassigned]** \u00b7 Implementation\n\n## Story"}
                return ""

            with patch_gh("kanban.gh_json", side_effect=gh_side_effect) as mock_json, \
                 patch_gh("kanban.gh") as mock_gh:
                result = do_assign(tf, implementer="rae")
                self.assertTrue(result)
                loaded = read_tf(tf.path)
                self.assertEqual(loaded.implementer, "rae")
                # Verify gh_json was called for issue view
                self.assertIn("view", str(mock_json.call_args))
                # Verify gh was called with persona label
                self.assertIn("persona:rae", str(mock_gh.call_args_list))

    def test_assign_both(self):
        """Assigning both implementer and reviewer adds both persona labels."""
        with tempfile.TemporaryDirectory() as td:
            tf = self._make_tf(td)

            def gh_side_effect(args):
                if "view" in args:
                    return {"body": "> **[Unassigned]** \u00b7 Implementation\n\n## Story"}
                return ""

            with patch_gh("kanban.gh_json", side_effect=gh_side_effect) as mock_json, \
                 patch_gh("kanban.gh") as mock_gh:
                result = do_assign(tf, implementer="rae", reviewer="chen")
                self.assertTrue(result)
                loaded = read_tf(tf.path)
                self.assertEqual(loaded.implementer, "rae")
                self.assertEqual(loaded.reviewer, "chen")
                all_gh_calls = str(mock_gh.call_args_list)
                self.assertIn("persona:rae", all_gh_calls)
                self.assertIn("persona:chen", all_gh_calls)
                # Satisfy MonitoredMock for mock_json
                self.assertIn("view", str(mock_json.call_args))


class TestSyncCommand(unittest.TestCase):
    """do_sync() reconciles local tracking files against GitHub issue data."""

    def _sprints_dir(self, td: str) -> Path:
        d = Path(td) / "sprints"
        (d / "sprint-1" / "stories").mkdir(parents=True, exist_ok=True)
        return d

    def _issue(self, number: int, title: str, state: str = "open",
               labels: list | None = None) -> dict:
        if labels is None:
            labels = [f"kanban:{state}"] if state != "open" else ["kanban:todo"]
        return {"number": number, "title": title, "state": "open", "labels": labels}

    def _write_tf(self, sprints_dir: Path, sprint: int, **kwargs) -> TF:
        stories_dir = sprints_dir / f"sprint-{sprint}" / "stories"
        story_id = kwargs.get("story", "US-0001")
        p = stories_dir / f"{story_id}-test.md"
        defaults = dict(path=p, sprint=sprint)
        defaults.update(kwargs)
        tf = TF(**defaults)
        write_tf(tf)
        return tf

    def test_sync_accepts_legal_external_transition(self):
        """Local=todo, GitHub=design → accepted and local updated."""
        with tempfile.TemporaryDirectory() as td:
            sprints_dir = self._sprints_dir(td)
            self._write_tf(sprints_dir, 1, story="US-0045", status="todo",
                           implementer="rae")
            issues = [self._issue(45, "US-0045: Feature A",
                                  labels=["kanban:design"])]
            changes = do_sync(sprints_dir, 1, issues)
            # Change accepted
            accepted = [c for c in changes if "accepted" in c and "US-0045" in c]
            self.assertTrue(accepted, f"Expected accepted transition, got: {changes}")
            # Local file updated
            result = find_story("US-0045", sprints_dir, 1)
            self.assertIsNotNone(result)
            self.assertEqual(result.status, "design")

    def test_sync_rejects_illegal_external_transition(self):
        """Local=todo, GitHub=review → warning emitted, local unchanged."""
        with tempfile.TemporaryDirectory() as td:
            sprints_dir = self._sprints_dir(td)
            self._write_tf(sprints_dir, 1, story="US-0046", status="todo")
            issues = [self._issue(46, "US-0046: Feature B",
                                  labels=["kanban:review"])]
            changes = do_sync(sprints_dir, 1, issues)
            # Warning issued
            warnings = [c for c in changes if "WARNING" in c and "US-0046" in c]
            self.assertTrue(warnings, f"Expected warning, got: {changes}")
            # Local state unchanged
            result = find_story("US-0046", sprints_dir, 1)
            self.assertIsNotNone(result)
            self.assertEqual(result.status, "todo")

    def test_sync_creates_new_story(self):
        """A GitHub issue with no local counterpart creates a tracking file."""
        with tempfile.TemporaryDirectory() as td:
            sprints_dir = self._sprints_dir(td)
            issues = [self._issue(99, "US-0099: Brand new story",
                                  labels=["kanban:todo"])]
            changes = do_sync(sprints_dir, 1, issues)
            created = [c for c in changes if "created" in c and "US-0099" in c]
            self.assertTrue(created, f"Expected creation entry, got: {changes}")
            result = find_story("US-0099", sprints_dir, 1)
            self.assertIsNotNone(result)
            self.assertEqual(result.story, "US-0099")
            self.assertEqual(result.status, "todo")


class TestStatusCommand(unittest.TestCase):
    """do_status() renders a board view from local tracking files."""

    def _write_tf(self, stories_dir: Path, sprint: int, **kwargs) -> TF:
        story_id = kwargs.get("story", "US-0001")
        p = stories_dir / f"{story_id}-test.md"
        defaults = dict(path=p, sprint=sprint)
        defaults.update(kwargs)
        tf = TF(**defaults)
        write_tf(tf)
        return tf

    def test_status_shows_board(self):
        """Three stories in different states appear under correct headers."""
        with tempfile.TemporaryDirectory() as td:
            sprints_dir = Path(td) / "sprints"
            stories_dir = sprints_dir / "sprint-3" / "stories"
            stories_dir.mkdir(parents=True)
            self._write_tf(stories_dir, 3, story="US-0041", status="done",
                           implementer="rae", reviewer="chen")
            self._write_tf(stories_dir, 3, story="US-0042", status="dev",
                           implementer="rae", reviewer="chen")
            self._write_tf(stories_dir, 3, story="US-0043", status="todo")
            output = do_status(sprints_dir, 3)
            self.assertIn("Sprint 3", output)
            self.assertIn("TODO", output)
            self.assertIn("DEV", output)
            self.assertIn("DONE", output)
            self.assertIn("US-0041", output)
            self.assertIn("US-0042", output)
            self.assertIn("US-0043", output)


if __name__ == "__main__":
    unittest.main()
