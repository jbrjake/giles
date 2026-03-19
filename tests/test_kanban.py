"""Tests for kanban state machine and shared tracking file I/O."""
from __future__ import annotations

import sys
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
        """Write a tracking file and read it back — verify ALL fields."""
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "US-0001-test.md"
            tf = TF(
                path=p, story="US-0001", title="Test story",
                sprint=1, implementer="rae", reviewer="chen",
                status="dev", branch="sprint-1/US-0001-test",
                pr_number="42", issue_number="7",
                started="2026-03-10", completed="2026-03-15",
            )
            write_tf(tf)
            loaded = read_tf(p)
            self.assertEqual(loaded.story, "US-0001")
            self.assertEqual(loaded.title, "Test story")
            self.assertEqual(loaded.sprint, 1)
            self.assertEqual(loaded.implementer, "rae")
            self.assertEqual(loaded.reviewer, "chen")
            self.assertEqual(loaded.status, "dev")
            self.assertEqual(loaded.branch, "sprint-1/US-0001-test")
            self.assertEqual(loaded.pr_number, "42")
            self.assertEqual(loaded.issue_number, "7")
            self.assertEqual(loaded.started, "2026-03-10")
            self.assertEqual(loaded.completed, "2026-03-15")

    # BH23-200: Comma-containing values must survive round-trip
    def test_round_trip_comma_title(self):
        """Titles with commas are quoted by _yaml_safe and read back intact."""
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "US-0003-comma.md"
            tf = TF(path=p, story="US-0003", title="Parse, validate, transform",
                    sprint=1, status="todo")
            write_tf(tf)
            loaded = read_tf(p)
            self.assertEqual(loaded.title, "Parse, validate, transform")

    # BH22-060: Empty field round-trip
    def test_round_trip_empty_fields(self):
        """Write a TF with empty persona/branch fields and read back."""
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "US-0002-empty.md"
            tf = TF(path=p, story="US-0002", title="Empty fields",
                    sprint=1, implementer="", reviewer="", branch="", pr_number="")
            write_tf(tf)
            loaded = read_tf(p)
            self.assertEqual(loaded.implementer, "")
            self.assertEqual(loaded.reviewer, "")
            self.assertEqual(loaded.branch, "")
            self.assertEqual(loaded.pr_number, "")


# ---------------------------------------------------------------------------
# Chunk 2 tests: Transition table, preconditions, atomic writes, locking,
# story lookup
# ---------------------------------------------------------------------------

from kanban import (  # noqa: E402 — conftest.py puts scripts/ on sys.path
    TRANSITIONS,
    validate_transition,
    check_preconditions,
    atomic_write_tf,
    _UPDATABLE_FIELDS,
    lock_story,
    lock_sprint,
    find_story,
    do_transition,
    do_assign,
    do_sync,
    do_status,
    do_update,
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

    # BH22-055: atomic_write_tf exception safety
    def test_atomic_write_preserves_original_on_failure(self):
        """If write_tf raises, the original file is untouched."""
        from unittest.mock import patch as _patch
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "US-0003-fail.md"
            tf = TF(path=p, story="US-0003", title="Original", sprint=1, status="todo")
            atomic_write_tf(tf)
            # Now try to overwrite with a failing write.
            # Patch kanban.write_tf because atomic_write_tf uses the name as
            # imported into the kanban module (not validate_config.write_tf).
            tf.status = "dev"
            with _patch("kanban.write_tf", side_effect=OSError("disk full")):
                with self.assertRaises(OSError):
                    atomic_write_tf(tf)
            # Original file should still have status=todo
            loaded = read_tf(p)
            self.assertEqual(loaded.status, "todo")
            # tf.path should not have been mutated
            self.assertEqual(tf.path, p)


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

    def test_concurrent_lock_serializes(self):
        """BH23-114: Two threads holding the same lock are serialized."""
        import threading
        import time
        with tempfile.TemporaryDirectory() as td:
            sprint_dir = Path(td) / "sprint-1"
            sprint_dir.mkdir()
            acquired = threading.Event()
            results = []

            def holder():
                with lock_sprint(sprint_dir):
                    acquired.set()
                    time.sleep(0.2)  # hold lock briefly
                    results.append("holder-done")

            def waiter():
                acquired.wait(timeout=2)  # wait for holder to grab lock
                with lock_sprint(sprint_dir):
                    results.append("waiter-done")

            t1 = threading.Thread(target=holder)
            t2 = threading.Thread(target=waiter)
            t1.start()
            t2.start()
            t1.join(timeout=5)
            t2.join(timeout=5)
            # Lock serialized: holder always finishes before waiter
            self.assertEqual(results, ["holder-done", "waiter-done"])


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
            # BH23-119: Verify at least 3 fields of the returned TF
            self.assertEqual(result.story, "US-0042")
            self.assertEqual(result.title, "Some feature")
            self.assertEqual(result.sprint, 1)
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

    # BH22-057: find_story case insensitivity and prefix collision
    def test_find_story_case_insensitive(self):
        """find_story matches regardless of case in the search ID."""
        with tempfile.TemporaryDirectory() as td:
            sprints_dir = Path(td)
            stories_dir = sprints_dir / "sprint-1" / "stories"
            stories_dir.mkdir(parents=True)
            tf = TF(path=stories_dir / "us-0010-lowercase.md",
                    story="US-0010", title="Test", sprint=1, status="todo")
            write_tf(tf)
            # Search with different casing
            result = find_story("us-0010", sprints_dir, sprint=1)
            self.assertIsNotNone(result)
            self.assertEqual(result.story, "US-0010")

    def test_find_story_no_prefix_collision(self):
        """US-0042 should NOT match US-00420-other.md."""
        with tempfile.TemporaryDirectory() as td:
            sprints_dir = Path(td)
            stories_dir = sprints_dir / "sprint-1" / "stories"
            stories_dir.mkdir(parents=True)
            # Create both files
            tf1 = TF(path=stories_dir / "US-0042-real.md",
                     story="US-0042", title="Real", sprint=1, status="dev")
            write_tf(tf1)
            tf2 = TF(path=stories_dir / "US-00420-other.md",
                     story="US-00420", title="Other", sprint=1, status="todo")
            write_tf(tf2)
            result = find_story("US-0042", sprints_dir, sprint=1)
            self.assertIsNotNone(result)
            self.assertEqual(result.story, "US-0042")  # not US-00420


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
                # BH22-058: Verify exact label swap call — issue number,
                # --remove-label and --add-label in one call
                first_call = mock.call_args_list[0]
                args = first_call[0][0]  # positional arg list
                self.assertIn("42", args)
                self.assertIn("--remove-label", args)
                self.assertIn("kanban:todo", args)
                self.assertIn("--add-label", args)
                self.assertIn("kanban:design", args)

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
                # BH22-054: Verify the failed call targeted the correct issue
                call_str = str(mock.call_args)
                self.assertIn("42", call_str)
                self.assertIn("kanban:design", call_str)

    # BH23-201: Double-fault restores tf.status on caller's object
    def test_transition_double_fault_restores_tf_status(self):
        """When both GitHub sync AND rollback fail, tf.status is still restored."""
        from unittest.mock import patch as _patch
        with tempfile.TemporaryDirectory() as td:
            tf = self._make_tf(td)
            # First call (gh sync) fails, then rollback (atomic_write_tf) also fails
            with patch_gh("kanban.gh", side_effect=RuntimeError("API error")):
                with _patch("kanban.atomic_write_tf",
                            side_effect=[None, OSError("disk full")]):
                    result = do_transition(tf, "design")
            self.assertFalse(result)
            # The caller's tf.status must be restored to "todo" even on double fault
            self.assertEqual(tf.status, "todo")

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


    # BH23-103: Test additional transition paths
    def test_transition_design_to_dev(self):
        """design→dev requires branch + pr_number set."""
        with tempfile.TemporaryDirectory() as td:
            tf = self._make_tf(td, status="design", implementer="rae",
                               branch="sprint-1/US-0042-feat", pr_number="55")
            with patch_gh("kanban.gh") as mock:
                result = do_transition(tf, "dev")
                self.assertTrue(result)
                loaded = read_tf(tf.path)
                self.assertEqual(loaded.status, "dev")

    def test_transition_review_to_integration(self):
        """review→integration is a legal transition."""
        with tempfile.TemporaryDirectory() as td:
            tf = self._make_tf(td, status="review", implementer="rae",
                               reviewer="chen", branch="sprint-1/US-0042-feat",
                               pr_number="55")
            with patch_gh("kanban.gh") as mock:
                result = do_transition(tf, "integration")
                self.assertTrue(result)
                loaded = read_tf(tf.path)
                self.assertEqual(loaded.status, "integration")

    def test_transition_review_to_dev_rejection_cycle(self):
        """review→dev is legal (reviewer requests changes)."""
        with tempfile.TemporaryDirectory() as td:
            tf = self._make_tf(td, status="review", implementer="rae",
                               reviewer="chen", branch="sprint-1/US-0042-feat",
                               pr_number="55")
            with patch_gh("kanban.gh"):
                result = do_transition(tf, "dev")
                self.assertTrue(result)
                loaded = read_tf(tf.path)
                self.assertEqual(loaded.status, "dev")


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

    # BH22-053: Reviewer-only assign
    def test_assign_reviewer_only(self):
        """Assigning only reviewer skips body update and only adds reviewer label."""
        with tempfile.TemporaryDirectory() as td:
            tf = self._make_tf(td)
            with patch_gh("kanban.gh") as mock_gh:
                result = do_assign(tf, reviewer="chen")
                self.assertTrue(result)
                loaded = read_tf(tf.path)
                self.assertEqual(loaded.reviewer, "chen")
                all_calls = str(mock_gh.call_args_list)
                self.assertIn("persona:chen", all_calls)
                # No body view should have been called (gh_json not patched)
                self.assertNotIn("view", all_calls)

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
                # BH22-052: Verify gh_json was called with the issue number
                self.assertIn("43", str(mock_json.call_args))
                self.assertIn("view", str(mock_json.call_args))


    def test_assign_fresh_issue_no_header(self):
        """BH23-113: Assign when issue body has no persona header."""
        with tempfile.TemporaryDirectory() as td:
            tf = self._make_tf(td)

            def gh_side_effect(args):
                if "view" in args:
                    return {"body": "## Story\nPlain body with no header."}
                return ""

            with patch_gh("kanban.gh_json", side_effect=gh_side_effect), \
                 patch_gh("kanban.gh") as mock_gh:
                result = do_assign(tf, implementer="rae")
                self.assertTrue(result)
                loaded = read_tf(tf.path)
                self.assertEqual(loaded.implementer, "rae")
                # Body update skipped — warning on stderr
                all_calls = str(mock_gh.call_args_list)
                self.assertIn("persona:rae", all_calls)

    def test_assign_skips_body_when_already_assigned(self):
        """BH23-113: Re-assign skips body update when [Unassigned] header is gone."""
        with tempfile.TemporaryDirectory() as td:
            tf = self._make_tf(td, implementer="old-persona")

            def gh_side_effect(args):
                if "view" in args:
                    return {"body": "> **[old-persona]** \u00b7 Implementation\n\n## Story"}
                return ""

            import io
            from contextlib import redirect_stderr
            buf = io.StringIO()
            with redirect_stderr(buf), \
                 patch_gh("kanban.gh_json", side_effect=gh_side_effect), \
                 patch_gh("kanban.gh") as mock_gh:
                result = do_assign(tf, implementer="new-persona")
                self.assertTrue(result)
                loaded = read_tf(tf.path)
                self.assertEqual(loaded.implementer, "new-persona")
                # Body update skipped — no --body call, warning emitted
                body_calls = [c for c in mock_gh.call_args_list
                              if "--body" in str(c)]
                self.assertEqual(len(body_calls), 0)
            self.assertIn("no [Unassigned] header", buf.getvalue())


class TestSyncCommand(unittest.TestCase):
    """do_sync() reconciles local tracking files against GitHub issue data."""

    def _sprints_dir(self, td: str) -> Path:
        d = Path(td) / "sprints"
        (d / "sprint-1" / "stories").mkdir(parents=True, exist_ok=True)
        return d

    def _issue(self, number: int, title: str, state: str = "open",
               labels: list | None = None) -> dict:
        # BH23-104: Use dict-format labels to match real gh_json output.
        # kanban_from_labels handles both formats, but tests should use
        # the same format production code receives from GitHub.
        if labels is None:
            label_name = f"kanban:{state}" if state != "open" else "kanban:todo"
            labels = [{"name": label_name}]
        issue_state = "open"
        if state == "closed":
            issue_state = "closed"
        return {"number": number, "title": title, "state": issue_state, "labels": labels, "closedAt": None}

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
                                  labels=[{"name": "kanban:design"}])]
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
                                  labels=[{"name": "kanban:review"}])]
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
                                  labels=[{"name": "kanban:todo"}])]
            changes = do_sync(sprints_dir, 1, issues)
            created = [c for c in changes if "created" in c and "US-0099" in c]
            self.assertTrue(created, f"Expected creation entry, got: {changes}")
            result = find_story("US-0099", sprints_dir, 1)
            self.assertIsNotNone(result)
            self.assertEqual(result.story, "US-0099")
            self.assertEqual(result.status, "todo")

    # BH22-050: Closed-issue sync coverage
    def test_sync_closed_issue_becomes_done(self):
        """Closed GitHub issue with no kanban label syncs as 'done'."""
        with tempfile.TemporaryDirectory() as td:
            sprints_dir = self._sprints_dir(td)
            self._write_tf(sprints_dir, 1, story="US-0047", status="review")
            issues = [{"number": 47, "title": "US-0047: Feature C",
                       "state": "closed", "labels": [],
                       "closedAt": "2026-03-18T00:00:00Z"}]
            changes = do_sync(sprints_dir, 1, issues)
            result = find_story("US-0047", sprints_dir, 1)
            self.assertEqual(result.status, "done")

    def test_sync_closed_issue_overrides_stale_label(self):
        """Closed issue with stale kanban:dev label still syncs as 'done'."""
        with tempfile.TemporaryDirectory() as td:
            sprints_dir = self._sprints_dir(td)
            self._write_tf(sprints_dir, 1, story="US-0048", status="dev")
            issues = [{"number": 48, "title": "US-0048: Feature D",
                       "state": "closed",
                       "labels": [{"name": "kanban:dev"}],
                       "closedAt": "2026-03-18T00:00:00Z"}]
            changes = do_sync(sprints_dir, 1, issues)
            result = find_story("US-0048", sprints_dir, 1)
            self.assertEqual(result.status, "done")

    # BH22-056: Local story absent from GitHub warning
    def test_sync_warns_about_local_story_absent_from_github(self):
        """Local story not on GitHub produces a warning."""
        with tempfile.TemporaryDirectory() as td:
            sprints_dir = self._sprints_dir(td)
            self._write_tf(sprints_dir, 1, story="US-0099", status="dev")
            changes = do_sync(sprints_dir, 1, [])  # empty issues list
            warnings = [c for c in changes if "WARNING" in c and "US-0099" in c]
            self.assertTrue(warnings, f"Expected warning, got: {changes}")

    # BH22-105: find_story warns on multiple matches
    def test_find_story_warns_on_multiple_matches(self):
        """find_story emits a warning when multiple files match the same ID."""
        import io
        from contextlib import redirect_stderr
        with tempfile.TemporaryDirectory() as td:
            sprints_dir = Path(td)
            stories_dir = sprints_dir / "sprint-1" / "stories"
            stories_dir.mkdir(parents=True)
            # Create two files that both match US-0042
            for name in ("US-0042-first.md", "US-0042-second.md"):
                tf = TF(path=stories_dir / name, story="US-0042",
                        title="Dupe", sprint=1, status="todo")
                write_tf(tf)
            buf = io.StringIO()
            with redirect_stderr(buf):
                result = find_story("US-0042", sprints_dir, sprint=1)
            self.assertIsNotNone(result)
            self.assertIn("multiple tracking files", buf.getvalue())

    # BH22-114: Malformed issue titles skip tracking file creation
    def test_sync_skips_malformed_issue_title(self):
        """Issues with no recognizable story ID produce a warning, not a file."""
        with tempfile.TemporaryDirectory() as td:
            sprints_dir = self._sprints_dir(td)
            # Issue with just a colon — extract_story_id falls back to UNKNOWN
            issues = [self._issue(99, ":", labels=[{"name": "kanban:todo"}])]
            changes = do_sync(sprints_dir, 1, issues)
            warnings = [c for c in changes if "WARNING" in c and "no recognizable" in c]
            self.assertTrue(warnings, f"Expected skip warning, got: {changes}")
            # No tracking file should be created
            stories = list((sprints_dir / "sprint-1" / "stories").glob("*.md"))
            self.assertEqual(len(stories), 0)


class TestUpdateCommand(unittest.TestCase):
    """do_update() safely updates individual tracking file fields."""

    def _make_tf(self, td: str, **kwargs) -> TF:
        stories_dir = Path(td) / "sprint-1" / "stories"
        stories_dir.mkdir(parents=True, exist_ok=True)
        p = stories_dir / "US-0050-update-test.md"
        defaults = dict(
            path=p, story="US-0050", title="Update test", sprint=1,
            status="design", implementer="rae", issue_number="50",
        )
        defaults.update(kwargs)
        tf = TF(**defaults)
        write_tf(tf)
        return tf

    def test_update_pr_number_and_branch(self):
        """Sets pr_number and branch fields atomically."""
        with tempfile.TemporaryDirectory() as td:
            tf = self._make_tf(td)
            ok = do_update(tf, pr_number="42", branch="sprint-1/US-0050-update")
            self.assertTrue(ok)
            loaded = read_tf(tf.path)
            self.assertEqual(loaded.pr_number, "42")
            self.assertEqual(loaded.branch, "sprint-1/US-0050-update")

    def test_update_skips_none_fields(self):
        """None values are ignored — only explicit strings are updated."""
        with tempfile.TemporaryDirectory() as td:
            tf = self._make_tf(td, pr_number="10", branch="old-branch")
            ok = do_update(tf, pr_number=None, branch="new-branch")
            self.assertTrue(ok)
            loaded = read_tf(tf.path)
            self.assertEqual(loaded.pr_number, "10")  # unchanged
            self.assertEqual(loaded.branch, "new-branch")

    def test_update_no_changes(self):
        """When values match current state, no write is performed."""
        with tempfile.TemporaryDirectory() as td:
            tf = self._make_tf(td, pr_number="42")
            ok = do_update(tf, pr_number="42")
            self.assertTrue(ok)

    # BH23-230: Immutable field protection
    def test_update_rejects_immutable_fields(self):
        """Cannot update path, story, sprint, or status via do_update."""
        with tempfile.TemporaryDirectory() as td:
            tf = self._make_tf(td)
            ok = do_update(tf, path="/tmp/evil.md")
            self.assertFalse(ok)
            ok = do_update(tf, story="HACKED")
            self.assertFalse(ok)
            ok = do_update(tf, status="done")
            self.assertFalse(ok)
            ok = do_update(tf, sprint="99")
            self.assertFalse(ok)
            # Verify the TF was not mutated
            self.assertEqual(tf.story, "US-0050")
            self.assertEqual(tf.status, "design")


class TestSyncPrune(unittest.TestCase):
    """do_sync(prune=True) removes orphaned local stories."""

    def _sprints_dir(self, td: str) -> Path:
        d = Path(td) / "sprints"
        (d / "sprint-1" / "stories").mkdir(parents=True, exist_ok=True)
        return d

    def test_prune_removes_orphaned_file(self):
        """Local story absent from GitHub is deleted when prune=True."""
        with tempfile.TemporaryDirectory() as td:
            sprints_dir = self._sprints_dir(td)
            stories_dir = sprints_dir / "sprint-1" / "stories"
            p = stories_dir / "US-0099-orphan.md"
            tf = TF(path=p, story="US-0099", title="Orphan", sprint=1, status="dev")
            write_tf(tf)
            self.assertTrue(p.exists())
            changes = do_sync(sprints_dir, 1, [], prune=True)
            self.assertFalse(p.exists())
            pruned = [c for c in changes if "pruned" in c and "US-0099" in c]
            self.assertTrue(pruned)

    def test_no_prune_keeps_file(self):
        """Default (prune=False) keeps orphaned files and warns."""
        with tempfile.TemporaryDirectory() as td:
            sprints_dir = self._sprints_dir(td)
            stories_dir = sprints_dir / "sprint-1" / "stories"
            p = stories_dir / "US-0099-orphan.md"
            tf = TF(path=p, story="US-0099", title="Orphan", sprint=1, status="dev")
            write_tf(tf)
            changes = do_sync(sprints_dir, 1, [], prune=False)
            self.assertTrue(p.exists())
            self.assertTrue(any("--prune" in c for c in changes))


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
            # BH23-126: Verify assignee names appear in the output
            self.assertIn("rae", output)
            self.assertIn("chen", output)

    def test_status_wip_limit_warning(self):
        """BH23-126: 4+ stories in DEV triggers WIP limit context."""
        with tempfile.TemporaryDirectory() as td:
            sprints_dir = Path(td) / "sprints"
            stories_dir = sprints_dir / "sprint-1" / "stories"
            stories_dir.mkdir(parents=True)
            for i in range(4):
                self._write_tf(stories_dir, 1,
                               story=f"US-{i:04d}", status="dev",
                               implementer=f"dev-{i}")
            output = do_status(sprints_dir, 1)
            self.assertIn("DEV", output)
            # All 4 dev stories should appear
            for i in range(4):
                self.assertIn(f"US-{i:04d}", output)


class TestCLI(unittest.TestCase):
    def test_no_command_exits_2(self):
        """Running kanban.py with no subcommand exits with code 2."""
        import subprocess
        result = subprocess.run(
            [sys.executable, str(Path(__file__).resolve().parent.parent / "scripts" / "kanban.py")],
            capture_output=True, text=True
        )
        self.assertEqual(result.returncode, 2)

    def test_help_flag(self):
        """--help exits 0 and shows subcommands."""
        import subprocess
        result = subprocess.run(
            [sys.executable, str(Path(__file__).resolve().parent.parent / "scripts" / "kanban.py"), "--help"],
            capture_output=True, text=True
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("transition", result.stdout)
        self.assertIn("assign", result.stdout)
        self.assertIn("sync", result.stdout)
        self.assertIn("status", result.stdout)


class TestCLIInfrastructure(unittest.TestCase):
    """CLI plumbing tests — validates arg parsing and error handling,
    not kanban logic.  These exercise load_config / arg dispatch paths."""

    def test_main_exits_1_without_config(self):
        """main() with any subcommand exits 1 when no sprint-config exists."""
        from unittest.mock import patch as _patch
        import kanban
        with _patch("sys.argv", ["kanban.py", "status"]):
            with self.assertRaises(SystemExit) as ctx:
                kanban.main()
            self.assertEqual(ctx.exception.code, 1)


if __name__ == "__main__":
    unittest.main()
