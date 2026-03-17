# Kanban State Machine Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Centralize all kanban state transitions into a single `scripts/kanban.py` script that owns story state, validates transitions, and syncs GitHub as a write-through side effect.

**Architecture:** Local tracking files are source of truth. Every mutating command atomically updates the tracking file and pushes the change to GitHub. A bidirectional sync command accepts legal external changes from GitHub. File locking with `fcntl` handles concurrent access from parallel agents.

**Tech Stack:** Python 3.10+ stdlib only (no external deps). `gh` CLI for GitHub interaction. `fcntl` for POSIX file locking.

**Spec:** `docs/superpowers/specs/2026-03-17-kanban-state-machine-design.md`

---

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `scripts/kanban.py` | Create | State machine: transition table, validation, assign, sync, status, atomic writes, file locking |
| `scripts/validate_config.py` | Modify | Receive extracted `TF`, `read_tf`, `write_tf`, `_yaml_safe` from sync_tracking.py |
| `skills/sprint-run/scripts/sync_tracking.py` | Modify | Import TF/read_tf/write_tf from validate_config.py instead of defining locally |
| `skills/sprint-run/agents/implementer.md` | Modify | Replace `gh issue edit` label commands with `kanban.py` calls |
| `skills/sprint-run/references/story-execution.md` | Modify | Replace all `gh issue edit` label commands with `kanban.py` calls |
| `skills/sprint-run/references/kanban-protocol.md` | Modify | Update "GitHub Label Sync" section to reference `kanban.py` |
| `skills/sprint-run/references/tracking-formats.md` | Modify | Flip source-of-truth statement |
| `skills/sprint-run/references/ceremony-kickoff.md` | Modify | Add `kanban.py assign` to exit criteria |
| `skills/sprint-run/SKILL.md` | Modify | Add note that all state changes go through `kanban.py` |
| `tests/test_kanban.py` | Create | Unit tests for state machine |
| `CLAUDE.md` | Modify | Add kanban.py to script table |
| `CHEATSHEET.md` | Modify | Add kanban.py index |

---

## Chunk 1: Extract Tracking File I/O into validate_config.py

Move `TF`, `read_tf`, `write_tf`, `_yaml_safe` from `sync_tracking.py` into `validate_config.py` so both `kanban.py` and `sync_tracking.py` can import them.

### Task 1: Write failing test for TF import from validate_config

**Files:**
- Create: `tests/test_kanban.py`

- [ ] **Step 1: Write failing test**

```python
"""Tests for kanban state machine and shared tracking file I/O."""
from __future__ import annotations

import textwrap
import unittest
from pathlib import Path

# After extraction, these should be importable from validate_config
from validate_config import TF, read_tf, write_tf


class TestTrackingFileIO(unittest.TestCase):
    """Verify TF, read_tf, write_tf work after extraction to validate_config."""

    def test_tf_defaults(self):
        tf = TF(path=Path("/tmp/fake.md"))
        self.assertEqual(tf.status, "todo")
        self.assertEqual(tf.implementer, "")
        self.assertEqual(tf.story, "")

    def test_round_trip(self, tmp_path=None):
        """Write a tracking file and read it back."""
        import tempfile
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/jonr/Documents/non-nitro-repos/giles && python -m pytest tests/test_kanban.py::TestTrackingFileIO -v`
Expected: `ImportError: cannot import name 'TF' from 'validate_config'`

### Task 2: Extract TF, read_tf, write_tf, _yaml_safe into validate_config.py

**Files:**
- Modify: `scripts/validate_config.py` (add ~90 lines at end, before no other code depends on position)
- Modify: `skills/sprint-run/scripts/sync_tracking.py` (replace local definitions with imports)

- [ ] **Step 3: Copy TF, _yaml_safe, read_tf, write_tf into validate_config.py**

Add after the existing `kanban_from_labels` function block (around line 988). Include the `TF` dataclass, `_yaml_safe()`, `read_tf()`, and `write_tf()` verbatim from `sync_tracking.py` lines 129-225. Add `§validate_config.TF`, `§validate_config.read_tf`, `§validate_config.write_tf`, `§validate_config._yaml_safe` anchor comments. The `read_tf` function uses `frontmatter_value` which is already in `validate_config.py`.

The `write_tf` function needs `import re` (already imported) and `from dataclasses import dataclass` (add to imports at top of file).

- [ ] **Step 4: Update sync_tracking.py imports**

Replace the local `TF` class, `_yaml_safe`, `read_tf`, `write_tf` definitions with imports:

```python
from validate_config import (
    load_config, ConfigError, gh_json, extract_story_id, get_sprints_dir,
    kanban_from_labels, find_milestone, frontmatter_value,
    list_milestone_issues, parse_iso_date, short_title, KANBAN_STATES,
    warn_if_at_limit, TF, read_tf, write_tf, _yaml_safe,
)
```

Remove lines 127-225 from `sync_tracking.py` (the `TF` class, `_yaml_safe`, `read_tf`, `write_tf` definitions). Also extract `slug_from_title` into `validate_config.py` (it's a 4-line pure function that `kanban.py` also needs, and importing from `sync_tracking` would require a cross-skill path hack).

**Important:** `_yaml_safe` and `slug_from_title` must be included in the `sync_tracking.py` import line so that existing tests that do `from sync_tracking import _yaml_safe` (e.g., `test_property_parsing.py`, `test_verify_fixes.py`) continue to work — Python re-exports imported names.

- [ ] **Step 5: Run test to verify it passes**

Run: `cd /Users/jonr/Documents/non-nitro-repos/giles && python -m pytest tests/test_kanban.py::TestTrackingFileIO -v`
Expected: PASS

- [ ] **Step 6: Run full test suite to verify no regressions**

Run: `cd /Users/jonr/Documents/non-nitro-repos/giles && python -m pytest tests/ -v --tb=short`
Expected: All existing tests pass. `sync_tracking.py` still works because it imports from `validate_config` now.

- [ ] **Step 7: Commit**

```bash
git add scripts/validate_config.py skills/sprint-run/scripts/sync_tracking.py tests/test_kanban.py
git commit -m "refactor: extract TF, read_tf, write_tf into validate_config.py

Shared tracking file I/O primitives now live in validate_config.py so
kanban.py can import them directly. sync_tracking.py imports instead of
defining locally."
```

---

## Chunk 2: Core State Machine — Transition Validation and Atomic Writes

Build the transition table, validation logic, atomic file writes, and file locking. No GitHub integration yet — that comes in Chunk 3.

### Task 3: Write failing tests for transition validation

**Files:**
- Modify: `tests/test_kanban.py`

- [ ] **Step 1: Write failing tests**

```python
class TestTransitionTable(unittest.TestCase):
    """Verify transition validation logic."""

    def test_legal_transitions(self):
        from kanban import validate_transition
        # All legal transitions should return no error
        legal = [
            ("todo", "design"),
            ("design", "dev"),
            ("dev", "review"),
            ("review", "dev"),
            ("review", "integration"),
            ("integration", "done"),
        ]
        for current, target in legal:
            err = validate_transition(current, target)
            self.assertIsNone(err, f"{current} → {target} should be legal")

    def test_illegal_transitions(self):
        from kanban import validate_transition
        illegal = [
            ("todo", "dev"),
            ("todo", "review"),
            ("todo", "done"),
            ("design", "review"),
            ("dev", "done"),
            ("done", "todo"),
            ("done", "design"),
        ]
        for current, target in illegal:
            err = validate_transition(current, target)
            self.assertIsNotNone(err, f"{current} → {target} should be illegal")

    def test_same_state_is_noop(self):
        from kanban import validate_transition
        for state in ("todo", "design", "dev", "review", "done"):
            err = validate_transition(state, state)
            self.assertIsNotNone(err, f"{state} → {state} should be rejected")

    def test_invalid_state_name(self):
        from kanban import validate_transition
        err = validate_transition("todo", "invalid")
        self.assertIsNotNone(err)
        self.assertIn("invalid", err)


class TestPreconditions(unittest.TestCase):
    """Verify precondition checks before transitions."""

    def test_todo_to_design_requires_implementer(self):
        from kanban import check_preconditions
        from validate_config import TF
        tf = TF(path=Path("/tmp/f.md"), status="todo", implementer="")
        err = check_preconditions(tf, "design")
        self.assertIsNotNone(err)
        self.assertIn("implementer", err)

    def test_todo_to_design_ok_with_implementer(self):
        from kanban import check_preconditions
        from validate_config import TF
        tf = TF(path=Path("/tmp/f.md"), status="todo", implementer="rae")
        err = check_preconditions(tf, "design")
        self.assertIsNone(err)

    def test_design_to_dev_requires_branch_and_pr(self):
        from kanban import check_preconditions
        from validate_config import TF
        tf = TF(path=Path("/tmp/f.md"), status="design",
                implementer="rae", branch="", pr_number="")
        err = check_preconditions(tf, "dev")
        self.assertIsNotNone(err)
        self.assertIn("branch", err)

    def test_dev_to_review_requires_reviewer(self):
        from kanban import check_preconditions
        from validate_config import TF
        tf = TF(path=Path("/tmp/f.md"), status="dev",
                implementer="rae", reviewer="")
        err = check_preconditions(tf, "review")
        self.assertIsNotNone(err)
        self.assertIn("reviewer", err)

    def test_integration_to_done_requires_pr_number(self):
        from kanban import check_preconditions
        from validate_config import TF
        tf = TF(path=Path("/tmp/f.md"), status="integration",
                implementer="rae", reviewer="chen", pr_number="")
        err = check_preconditions(tf, "done")
        self.assertIsNotNone(err)
        self.assertIn("pr", err.lower())
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/jonr/Documents/non-nitro-repos/giles && python -m pytest tests/test_kanban.py::TestTransitionTable tests/test_kanban.py::TestPreconditions -v`
Expected: `ModuleNotFoundError: No module named 'kanban'`

### Task 4: Implement transition table and precondition checks

**Files:**
- Create: `scripts/kanban.py`

- [ ] **Step 3: Create kanban.py with transition validation**

```python
#!/usr/bin/env python3
"""Kanban state machine for sprint story management.

Usage:
    kanban.py transition <story-id> <target-state> [--sprint N]
    kanban.py assign <story-id> --implementer <name> [--reviewer <name>] [--sprint N]
    kanban.py sync [--sprint N]
    kanban.py status [--sprint N]

Source of truth: local tracking files (sprint-{N}/stories/*.md).
GitHub is a downstream reflection synced on every mutation.
"""
from __future__ import annotations

import sys
from pathlib import Path

try:
    import fcntl
except ImportError:
    sys.exit(
        "kanban.py requires POSIX file locking (fcntl). "
        "Run on macOS, Linux, or WSL."
    )

# -- Import shared config -----------------------------------------------
sys.path.insert(0, str(Path(__file__).resolve().parent))
from validate_config import (
    load_config, ConfigError, TF, read_tf, write_tf,
    get_sprints_dir, detect_sprint, extract_story_id,
    kanban_from_labels, find_milestone, list_milestone_issues,
    gh, gh_json, KANBAN_STATES,
)


# §kanban.TRANSITIONS
TRANSITIONS: dict[str, list[str]] = {
    "todo":        ["design"],
    "design":      ["dev"],
    "dev":         ["review"],
    "review":      ["dev", "integration"],
    "integration": ["done"],
    "done":        [],
}


# §kanban.validate_transition
def validate_transition(current: str, target: str) -> str | None:
    """Return None if legal, or an error message if illegal."""
    if target not in KANBAN_STATES:
        valid = ", ".join(sorted(KANBAN_STATES))
        return f"'{target}' is not a valid state. Valid states: {valid}"
    if current == target:
        return f"already in state '{current}'"
    allowed = TRANSITIONS.get(current, [])
    if target not in allowed:
        hint = ", ".join(allowed) if allowed else "(terminal state)"
        return (
            f"cannot transition {current} → {target}. "
            f"Legal transitions from {current}: {hint}"
        )
    return None


# §kanban.check_preconditions
def check_preconditions(tf: TF, target: str) -> str | None:
    """Return None if preconditions met, or an error message."""
    if target == "design":
        if not tf.implementer:
            return (
                "cannot transition todo → design — no implementer assigned. "
                "Run 'kanban.py assign <story-id> --implementer <name>' first."
            )
    elif target == "dev":
        missing = []
        if not tf.branch:
            missing.append("branch")
        if not tf.pr_number:
            missing.append("pr_number")
        if missing:
            return (
                f"cannot transition design → dev — {', '.join(missing)} not set. "
                "The implementer agent must create a branch and draft PR first."
            )
    elif target == "review":
        if not tf.reviewer:
            return (
                "cannot transition dev → review — no reviewer assigned. "
                "Run 'kanban.py assign <story-id> --reviewer <name>' first."
            )
    elif target == "done":
        if not tf.pr_number:
            return (
                "cannot transition integration → done — no PR number set. "
                "The PR must exist and be merged before marking done."
            )
    return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/jonr/Documents/non-nitro-repos/giles && python -m pytest tests/test_kanban.py::TestTransitionTable tests/test_kanban.py::TestPreconditions -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/kanban.py tests/test_kanban.py
git commit -m "feat: kanban state machine — transition table and precondition validation"
```

### Task 5: Atomic file writes and file locking

**Files:**
- Modify: `scripts/kanban.py`
- Modify: `tests/test_kanban.py`

- [ ] **Step 6: Write failing tests for atomic write and file locking**

```python
import tempfile

class TestAtomicWrite(unittest.TestCase):
    """Verify atomic write-to-temp-then-rename pattern."""

    def test_atomic_write_creates_file(self):
        from kanban import atomic_write_tf
        from validate_config import TF
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "stories" / "US-0001-test.md"
            p.parent.mkdir(parents=True)
            tf = TF(path=p, story="US-0001", title="Test", sprint=1, status="todo")
            atomic_write_tf(tf)
            self.assertTrue(p.exists())
            loaded = read_tf(p)
            self.assertEqual(loaded.story, "US-0001")
            self.assertEqual(loaded.status, "todo")

    def test_atomic_write_no_partial_state(self):
        """If we read during a write, we get old or new state, never partial."""
        from kanban import atomic_write_tf
        from validate_config import TF
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "US-0001-test.md"
            # Write initial state
            tf = TF(path=p, story="US-0001", title="Test", sprint=1, status="todo")
            atomic_write_tf(tf)
            # Overwrite with new state
            tf.status = "dev"
            tf.implementer = "rae"
            atomic_write_tf(tf)
            loaded = read_tf(p)
            self.assertEqual(loaded.status, "dev")
            self.assertEqual(loaded.implementer, "rae")
            # No .tmp file left behind
            self.assertFalse(p.with_suffix(".tmp").exists())


class TestFileLocking(unittest.TestCase):
    """Verify file locking context manager."""

    def test_lock_story_acquires_and_releases(self):
        from kanban import lock_story
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "US-0001-test.md"
            p.write_text("---\nstory: US-0001\nstatus: todo\n---\n")
            # Should be able to acquire lock
            with lock_story(p):
                content = p.read_text()
                self.assertIn("US-0001", content)
            # Lock released — should be able to acquire again
            with lock_story(p):
                pass  # no deadlock
```

- [ ] **Step 7: Run tests to verify they fail**

Run: `cd /Users/jonr/Documents/non-nitro-repos/giles && python -m pytest tests/test_kanban.py::TestAtomicWrite tests/test_kanban.py::TestFileLocking -v`
Expected: FAIL — `cannot import name 'atomic_write_tf'`

- [ ] **Step 8: Implement atomic_write_tf and lock_story**

Add to `scripts/kanban.py`:

```python
import os
from contextlib import contextmanager


# §kanban.atomic_write_tf
def atomic_write_tf(tf: TF) -> None:
    """Write tracking file atomically via temp-then-rename.

    Delegates to write_tf to avoid duplicating YAML serialization.
    Temporarily swaps path to .tmp, writes, then atomically renames.
    """
    tf.path.parent.mkdir(parents=True, exist_ok=True)
    tmp = tf.path.with_suffix(".tmp")
    original_path = tf.path
    tf.path = tmp
    write_tf(tf)
    tf.path = original_path
    os.rename(str(tmp), str(tf.path))
```

```python
# §kanban.lock_story
@contextmanager
def lock_story(tracking_path: Path):
    """Acquire exclusive lock on a tracking file for read-modify-write."""
    fd = open(tracking_path, "r")
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        fd.close()


# §kanban.lock_sprint
@contextmanager
def lock_sprint(sprint_dir: Path):
    """Acquire exclusive lock for sprint-wide operations (sync)."""
    lock_path = sprint_dir / ".kanban.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.touch(exist_ok=True)
    fd = open(lock_path, "r")
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        fd.close()
```

- [ ] **Step 9: Run tests to verify they pass**

Run: `cd /Users/jonr/Documents/non-nitro-repos/giles && python -m pytest tests/test_kanban.py::TestAtomicWrite tests/test_kanban.py::TestFileLocking -v`
Expected: All PASS

- [ ] **Step 10: Commit**

```bash
git add scripts/kanban.py tests/test_kanban.py
git commit -m "feat: kanban atomic file writes and POSIX file locking"
```

### Task 6: Story file lookup helper

**Files:**
- Modify: `scripts/kanban.py`
- Modify: `tests/test_kanban.py`

- [ ] **Step 11: Write failing test for find_story**

```python
class TestFindStory(unittest.TestCase):
    """Verify story lookup by ID in sprint directory."""

    def test_finds_story_by_id(self):
        from kanban import find_story
        from validate_config import TF
        with tempfile.TemporaryDirectory() as td:
            stories = Path(td) / "sprint-1" / "stories"
            stories.mkdir(parents=True)
            tf = TF(path=stories / "US-0042-test.md",
                    story="US-0042", title="Test", sprint=1, status="todo")
            atomic_write_tf(tf)
            found = find_story("US-0042", Path(td), sprint=1)
            self.assertIsNotNone(found)
            self.assertEqual(found.story, "US-0042")

    def test_returns_none_for_missing_story(self):
        from kanban import find_story
        with tempfile.TemporaryDirectory() as td:
            stories = Path(td) / "sprint-1" / "stories"
            stories.mkdir(parents=True)
            found = find_story("US-9999", Path(td), sprint=1)
            self.assertIsNone(found)
```

- [ ] **Step 12: Run to verify fail, implement, run to verify pass**

Implement in `kanban.py`:

```python
# §kanban.find_story
def find_story(story_id: str, sprints_dir: Path, sprint: int) -> TF | None:
    """Find a tracking file by story ID in the sprint directory."""
    stories_dir = sprints_dir / f"sprint-{sprint}" / "stories"
    if not stories_dir.is_dir():
        return None
    for p in stories_dir.glob("*.md"):
        tf = read_tf(p)
        if tf.story == story_id:
            return tf
    return None
```

Run: `cd /Users/jonr/Documents/non-nitro-repos/giles && python -m pytest tests/test_kanban.py::TestFindStory -v`
Expected: PASS

- [ ] **Step 13: Commit**

```bash
git add scripts/kanban.py tests/test_kanban.py
git commit -m "feat: kanban story lookup by ID in sprint directory"
```

---

## Chunk 3: GitHub Sync — Write-Through and Bidirectional Merge

Wire up the GitHub integration: label swaps on transition, issue body updates on assign, and bidirectional sync.

### Task 7: Write failing tests for transition with GitHub sync

**Files:**
- Modify: `tests/test_kanban.py`

- [ ] **Step 1: Write failing tests using patch_gh**

```python
from gh_test_helpers import patch_gh


class TestTransitionCommand(unittest.TestCase):
    """Verify transition command updates local state + GitHub."""

    def test_transition_updates_local_and_github(self):
        from kanban import do_transition, atomic_write_tf
        from validate_config import TF
        with tempfile.TemporaryDirectory() as td:
            stories = Path(td) / "sprint-1" / "stories"
            stories.mkdir(parents=True)
            tf = TF(path=stories / "US-0042-test.md",
                    story="US-0042", title="Test", sprint=1,
                    status="todo", implementer="rae", issue_number="7")
            atomic_write_tf(tf)
            with patch_gh("kanban.gh", return_value="") as mock:
                result = do_transition(tf, "design")
                self.assertTrue(result)
                # Verify GitHub label swap was called
                call_str = str(mock.call_args)
                self.assertIn("kanban:todo", call_str)
                self.assertIn("kanban:design", call_str)
            # Verify local file updated
            loaded = read_tf(stories / "US-0042-test.md")
            self.assertEqual(loaded.status, "design")

    def test_transition_reverts_on_github_failure(self):
        from kanban import do_transition, atomic_write_tf
        from validate_config import TF
        with tempfile.TemporaryDirectory() as td:
            stories = Path(td) / "sprint-1" / "stories"
            stories.mkdir(parents=True)
            tf = TF(path=stories / "US-0042-test.md",
                    story="US-0042", title="Test", sprint=1,
                    status="todo", implementer="rae", issue_number="7")
            atomic_write_tf(tf)
            with patch_gh("kanban.gh", side_effect=RuntimeError("API down")) as mock:
                result = do_transition(tf, "design")
                self.assertFalse(result)
                _ = mock.call_args  # satisfy MonitoredMock
            # Local file should be reverted
            loaded = read_tf(stories / "US-0042-test.md")
            self.assertEqual(loaded.status, "todo")

    def test_transition_to_done_closes_issue(self):
        from kanban import do_transition, atomic_write_tf
        from validate_config import TF
        with tempfile.TemporaryDirectory() as td:
            stories = Path(td) / "sprint-1" / "stories"
            stories.mkdir(parents=True)
            tf = TF(path=stories / "US-0042-test.md",
                    story="US-0042", title="Test", sprint=1,
                    status="integration", implementer="rae",
                    reviewer="chen", issue_number="7", pr_number="10",
                    branch="sprint-1/US-0042-test")
            atomic_write_tf(tf)
            calls = []
            def track_gh(args):
                calls.append(args)
                return ""
            with patch_gh("kanban.gh", side_effect=track_gh) as mock:
                result = do_transition(tf, "done")
                self.assertTrue(result)
                _ = mock.call_args
            # Should have label swap AND issue close
            all_args = str(calls)
            self.assertIn("kanban:done", all_args)
            self.assertIn("close", all_args)
```

- [ ] **Step 2: Run to verify fail**

Run: `cd /Users/jonr/Documents/non-nitro-repos/giles && python -m pytest tests/test_kanban.py::TestTransitionCommand -v`
Expected: FAIL — `cannot import name 'do_transition'`

### Task 8: Implement do_transition with GitHub sync and rollback

**Files:**
- Modify: `scripts/kanban.py`

- [ ] **Step 3: Implement do_transition**

```python
# §kanban.do_transition
def do_transition(tf: TF, target: str) -> bool:
    """Execute a state transition: validate, update local, sync GitHub.

    Returns True on success, False on failure (with local state reverted).
    """
    # Validate transition
    err = validate_transition(tf.status, target)
    if err:
        print(f"{tf.story}: {err}", file=sys.stderr)
        return False

    # Check preconditions
    err = check_preconditions(tf, target)
    if err:
        print(f"{tf.story}: {err}", file=sys.stderr)
        return False

    old_status = tf.status
    issue_num = tf.issue_number
    if not issue_num:
        print(f"{tf.story}: no issue_number — cannot sync to GitHub",
              file=sys.stderr)
        return False

    # Update local state
    tf.status = target
    atomic_write_tf(tf)

    # Sync to GitHub
    try:
        gh(["issue", "edit", issue_num,
            "--remove-label", f"kanban:{old_status}",
            "--add-label", f"kanban:{target}"])
        if target == "done":
            gh(["issue", "close", issue_num])
        print(f"{tf.story}: {old_status} → {target}")
        return True
    except RuntimeError as exc:
        # Rollback local state
        tf.status = old_status
        atomic_write_tf(tf)
        print(f"{tf.story}: local state reverted. "
              f"GitHub update failed: {exc}. Retry with same command.",
              file=sys.stderr)
        return False
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/jonr/Documents/non-nitro-repos/giles && python -m pytest tests/test_kanban.py::TestTransitionCommand -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/kanban.py tests/test_kanban.py
git commit -m "feat: kanban transition command with GitHub sync and rollback"
```

### Task 9: Write failing tests for assign command

**Files:**
- Modify: `tests/test_kanban.py`

- [ ] **Step 6: Write failing tests**

```python
class TestAssignCommand(unittest.TestCase):
    """Verify assign command updates local state + GitHub."""

    def test_assign_implementer(self):
        from kanban import do_assign, atomic_write_tf
        from validate_config import TF
        with tempfile.TemporaryDirectory() as td:
            stories = Path(td) / "sprint-1" / "stories"
            stories.mkdir(parents=True)
            tf = TF(path=stories / "US-0042-test.md",
                    story="US-0042", title="Test", sprint=1,
                    status="todo", issue_number="7")
            atomic_write_tf(tf)
            calls = []
            def track_gh(args):
                calls.append(args)
                if "view" in args:
                    return '{"body": "> **[Unassigned]** \\u00b7 Implementation\\n\\n## Story"}'
                return ""
            with patch_gh("kanban.gh", side_effect=track_gh) as mock:
                result = do_assign(tf, implementer="rae")
                self.assertTrue(result)
                _ = mock.call_args
            loaded = read_tf(stories / "US-0042-test.md")
            self.assertEqual(loaded.implementer, "rae")

    def test_assign_both(self):
        from kanban import do_assign, atomic_write_tf
        from validate_config import TF
        with tempfile.TemporaryDirectory() as td:
            stories = Path(td) / "sprint-1" / "stories"
            stories.mkdir(parents=True)
            tf = TF(path=stories / "US-0042-test.md",
                    story="US-0042", title="Test", sprint=1,
                    status="todo", issue_number="7")
            atomic_write_tf(tf)
            calls = []
            def track_gh(args):
                calls.append(args)
                if "view" in args:
                    return '{"body": "> **[Unassigned]** \\u00b7 Implementation\\n\\n## Story"}'
                return ""
            with patch_gh("kanban.gh", side_effect=track_gh) as mock:
                result = do_assign(tf, implementer="rae", reviewer="chen")
                self.assertTrue(result)
                _ = mock.call_args
            loaded = read_tf(stories / "US-0042-test.md")
            self.assertEqual(loaded.implementer, "rae")
            self.assertEqual(loaded.reviewer, "chen")
            # Verify persona labels added
            all_args = str(calls)
            self.assertIn("persona:rae", all_args)
            self.assertIn("persona:chen", all_args)
```

- [ ] **Step 7: Run to verify fail, implement, run to verify pass**

Implement `do_assign` in `kanban.py`:

```python
import json
import re


# §kanban._PERSONA_HEADER_PATTERN
_PERSONA_HEADER_PATTERN = re.compile(
    r'> \*\*\[Unassigned\]\*\* · Implementation'
)


# §kanban.do_assign
def do_assign(
    tf: TF,
    implementer: str = "",
    reviewer: str = "",
) -> bool:
    """Assign personas to a story: update local state + GitHub.

    Returns True on success, False on failure (with local state reverted).
    """
    old_impl = tf.implementer
    old_rev = tf.reviewer
    issue_num = tf.issue_number
    if not issue_num:
        print(f"{tf.story}: no issue_number — cannot sync to GitHub",
              file=sys.stderr)
        return False

    # Update local state
    if implementer:
        tf.implementer = implementer
    if reviewer:
        tf.reviewer = reviewer
    atomic_write_tf(tf)

    # Sync to GitHub
    try:
        # Add persona labels
        label_args = ["issue", "edit", issue_num]
        if implementer:
            label_args.extend(["--add-label", f"persona:{implementer}"])
        if reviewer:
            label_args.extend(["--add-label", f"persona:{reviewer}"])
        gh(label_args)

        # Update issue body: replace [Unassigned] with persona header
        if implementer:
            raw = gh(["issue", "view", issue_num, "--json", "body"])
            body_data = json.loads(raw)
            body = body_data.get("body", "")
            new_header = f"> **{implementer}** · Implementation"
            new_body = _PERSONA_HEADER_PATTERN.sub(new_header, body)
            if new_body != body:
                gh(["issue", "edit", issue_num, "--body", new_body])

        names = []
        if implementer:
            names.append(f"implementer={implementer}")
        if reviewer:
            names.append(f"reviewer={reviewer}")
        print(f"{tf.story}: assigned {', '.join(names)}")
        return True
    except RuntimeError as exc:
        # Rollback local state
        tf.implementer = old_impl
        tf.reviewer = old_rev
        atomic_write_tf(tf)
        print(f"{tf.story}: local state reverted. "
              f"GitHub update failed: {exc}. Retry with same command.",
              file=sys.stderr)
        return False
```

Run: `cd /Users/jonr/Documents/non-nitro-repos/giles && python -m pytest tests/test_kanban.py::TestAssignCommand -v`
Expected: All PASS

- [ ] **Step 8: Commit**

```bash
git add scripts/kanban.py tests/test_kanban.py
git commit -m "feat: kanban assign command with persona labels and issue body update"
```

### Task 10: Write failing tests for sync command

**Files:**
- Modify: `tests/test_kanban.py`

- [ ] **Step 9: Write failing tests**

```python
class TestSyncCommand(unittest.TestCase):
    """Verify bidirectional sync with GitHub."""

    def test_sync_accepts_legal_external_transition(self):
        from kanban import do_sync, atomic_write_tf
        from validate_config import TF
        with tempfile.TemporaryDirectory() as td:
            stories = Path(td) / "sprint-1" / "stories"
            stories.mkdir(parents=True)
            # Local state: todo
            tf = TF(path=stories / "US-0042-test.md",
                    story="US-0042", title="Test", sprint=1,
                    status="todo", implementer="rae", issue_number="7")
            atomic_write_tf(tf)
            # GitHub says: design (legal transition from todo)
            issues = [{"number": 7, "title": "US-0042: Test",
                       "state": "open",
                       "labels": [{"name": "kanban:design"}],
                       "body": "", "closedAt": None}]
            changes = do_sync(Path(td), 1, issues)
            self.assertTrue(any("design" in c for c in changes))
            loaded = read_tf(stories / "US-0042-test.md")
            self.assertEqual(loaded.status, "design")

    def test_sync_rejects_illegal_external_transition(self):
        from kanban import do_sync, atomic_write_tf
        from validate_config import TF
        with tempfile.TemporaryDirectory() as td:
            stories = Path(td) / "sprint-1" / "stories"
            stories.mkdir(parents=True)
            tf = TF(path=stories / "US-0042-test.md",
                    story="US-0042", title="Test", sprint=1,
                    status="todo", implementer="rae", issue_number="7")
            atomic_write_tf(tf)
            # GitHub says: review (illegal from todo)
            issues = [{"number": 7, "title": "US-0042: Test",
                       "state": "open",
                       "labels": [{"name": "kanban:review"}],
                       "body": "", "closedAt": None}]
            changes = do_sync(Path(td), 1, issues)
            self.assertTrue(any("illegal" in c.lower() for c in changes))
            loaded = read_tf(stories / "US-0042-test.md")
            self.assertEqual(loaded.status, "todo")  # unchanged

    def test_sync_creates_new_story(self):
        from kanban import do_sync
        with tempfile.TemporaryDirectory() as td:
            stories = Path(td) / "sprint-1" / "stories"
            stories.mkdir(parents=True)
            # New issue not in local tracking
            issues = [{"number": 12, "title": "US-0050: New feature",
                       "state": "open",
                       "labels": [{"name": "kanban:todo"}],
                       "body": "> **[Unassigned]**", "closedAt": None}]
            changes = do_sync(Path(td), 1, issues)
            self.assertTrue(any("created" in c.lower() for c in changes))
            # Should have created a tracking file
            files = list(stories.glob("*.md"))
            self.assertEqual(len(files), 1)
            loaded = read_tf(files[0])
            self.assertEqual(loaded.story, "US-0050")
```

- [ ] **Step 10: Run to verify fail, implement, run to verify pass**

Implement `do_sync` in `kanban.py`:

```python
# §kanban.do_sync
def do_sync(
    sprints_dir: Path, sprint: int, issues: list[dict]
) -> list[str]:
    """Bidirectional sync: accept legal external GitHub changes, create new stories.

    Args:
        sprints_dir: Path to sprints directory.
        sprint: Sprint number.
        issues: List of GitHub issue dicts (from list_milestone_issues).

    Returns:
        List of change/warning descriptions.
    """
    stories_dir = sprints_dir / f"sprint-{sprint}" / "stories"
    stories_dir.mkdir(parents=True, exist_ok=True)
    changes: list[str] = []

    # Load all local tracking files
    local: dict[str, TF] = {}
    for p in stories_dir.glob("*.md"):
        tf = read_tf(p)
        if tf.story:
            local[tf.story] = tf

    seen_stories: set[str] = set()

    for issue in issues:
        sid = extract_story_id(issue["title"])
        if not sid:
            continue
        seen_stories.add(sid)
        gh_status = kanban_from_labels(issue)

        if sid in local:
            tf = local[sid]
            if gh_status == tf.status:
                continue  # in sync
            # Validate the external transition
            err = validate_transition(tf.status, gh_status)
            if err is None:
                old = tf.status
                tf.status = gh_status
                atomic_write_tf(tf)
                changes.append(
                    f"{sid}: accepted external change {old} → {gh_status}"
                )
            else:
                changes.append(
                    f"{sid}: ILLEGAL external change — GitHub shows "
                    f"kanban:{gh_status} but local state is {tf.status}. {err}"
                )
        else:
            # New issue — create tracking file
            slug = slug_from_title(issue["title"])
            target = stories_dir / f"{slug}.md"
            tf = TF(
                path=target,
                story=sid,
                title=short_title(issue["title"]),
                sprint=sprint,
                status=gh_status,
                issue_number=str(issue["number"]),
            )
            atomic_write_tf(tf)
            changes.append(
                f"{sid}: created tracking file {slug}.md (status={gh_status})"
            )

    # Warn about local stories not found on GitHub
    for sid, tf in local.items():
        if sid not in seen_stories:
            changes.append(
                f"{sid}: exists locally but not found on GitHub. "
                "Issue may have been deleted externally."
            )

    return changes


Reuse existing functions: import `short_title` from `validate_config` (already imported) and `slug_from_title` from `sync_tracking` (add to kanban.py imports). Don't duplicate these.
```

Run: `cd /Users/jonr/Documents/non-nitro-repos/giles && python -m pytest tests/test_kanban.py::TestSyncCommand -v`
Expected: All PASS

- [ ] **Step 11: Commit**

```bash
git add scripts/kanban.py tests/test_kanban.py
git commit -m "feat: kanban bidirectional sync — accept legal external changes, create new stories"
```

### Task 11: Status command

**Files:**
- Modify: `scripts/kanban.py`
- Modify: `tests/test_kanban.py`

- [ ] **Step 12: Write failing test, implement, verify**

Test:
```python
class TestStatusCommand(unittest.TestCase):
    def test_status_shows_board(self):
        from kanban import do_status, atomic_write_tf
        from validate_config import TF
        with tempfile.TemporaryDirectory() as td:
            stories = Path(td) / "sprint-1" / "stories"
            stories.mkdir(parents=True)
            for sid, status, impl in [
                ("US-0001", "todo", ""),
                ("US-0002", "dev", "rae"),
                ("US-0003", "done", "chen"),
            ]:
                tf = TF(path=stories / f"{sid}-test.md",
                        story=sid, title="Test", sprint=1,
                        status=status, implementer=impl)
                atomic_write_tf(tf)
            output = do_status(Path(td), 1)
            self.assertIn("TODO", output)
            self.assertIn("DEV", output)
            self.assertIn("DONE", output)
            self.assertIn("US-0001", output)
            self.assertIn("US-0002", output)
```

Implement `do_status`:
```python
# §kanban.do_status
def do_status(sprints_dir: Path, sprint: int) -> str:
    """Render a text board view from local tracking files."""
    stories_dir = sprints_dir / f"sprint-{sprint}" / "stories"
    if not stories_dir.is_dir():
        return f"No stories directory for sprint {sprint}"

    by_state: dict[str, list[TF]] = {s: [] for s in
        ("todo", "design", "dev", "review", "integration", "done")}
    for p in stories_dir.glob("*.md"):
        tf = read_tf(p)
        if tf.story and tf.status in by_state:
            by_state[tf.status].append(tf)

    lines = [f"Sprint {sprint}"]
    lines.append("")
    for state in ("todo", "design", "dev", "review", "integration", "done"):
        stories = by_state[state]
        if not stories:
            continue
        entries = []
        for tf in sorted(stories, key=lambda t: t.story):
            parts = [tf.story]
            if tf.implementer:
                if tf.reviewer:
                    parts.append(f"{tf.implementer} → {tf.reviewer}")
                else:
                    parts.append(tf.implementer)
            entries.append(f"  {', '.join(parts)}")
        label = state.upper()
        lines.append(f"{label} ({len(stories)}):")
        lines.extend(entries)
        lines.append("")
    return "\n".join(lines)
```

Run: `cd /Users/jonr/Documents/non-nitro-repos/giles && python -m pytest tests/test_kanban.py::TestStatusCommand -v`
Expected: PASS

- [ ] **Step 13: Commit**

```bash
git add scripts/kanban.py tests/test_kanban.py
git commit -m "feat: kanban status command — read-only board view"
```

---

## Chunk 4: CLI Entry Point and Full Test Suite

### Task 12: CLI argument parsing and main()

**Files:**
- Modify: `scripts/kanban.py`
- Modify: `tests/test_kanban.py`

- [ ] **Step 1: Implement argparse CLI**

Add to `kanban.py`:

```python
import argparse


# §kanban.build_parser
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Kanban state machine for sprint story management.")
    sub = parser.add_subparsers(dest="command")

    # transition
    tr = sub.add_parser("transition", help="Transition a story to a new state")
    tr.add_argument("story_id", help="Story ID (e.g., US-0042)")
    tr.add_argument("target", help="Target kanban state")
    tr.add_argument("--sprint", type=int, default=None)

    # assign
    asn = sub.add_parser("assign", help="Assign personas to a story")
    asn.add_argument("story_id", help="Story ID (e.g., US-0042)")
    asn.add_argument("--implementer", default="")
    asn.add_argument("--reviewer", default="")
    asn.add_argument("--sprint", type=int, default=None)

    # sync
    sy = sub.add_parser("sync", help="Bidirectional sync with GitHub")
    sy.add_argument("--sprint", type=int, default=None)

    # status
    st = sub.add_parser("status", help="Show kanban board")
    st.add_argument("--sprint", type=int, default=None)

    return parser


# §kanban.main
def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(2)

    try:
        config = load_config()
    except ConfigError:
        sys.exit(1)
    sprints_dir = get_sprints_dir(config)

    sprint = args.sprint or detect_sprint(sprints_dir)
    if sprint is None:
        print("Cannot detect sprint number. Use --sprint N.", file=sys.stderr)
        sys.exit(1)

    if args.command == "status":
        print(do_status(sprints_dir, sprint))
        return

    if args.command == "sync":
        sprint_dir = sprints_dir / f"sprint-{sprint}"
        ms = find_milestone(sprint)
        if not ms:
            print(f"No GitHub milestone for Sprint {sprint}", file=sys.stderr)
            sys.exit(1)
        issues = list_milestone_issues(ms["title"])
        with lock_sprint(sprint_dir):
            changes = do_sync(sprints_dir, sprint, issues)
        if changes:
            for c in changes:
                print(f"  {c}")
        else:
            print("Everything in sync")
        return

    # transition and assign need a story
    tf = find_story(args.story_id, sprints_dir, sprint)
    if tf is None:
        print(f"{args.story_id}: no tracking file found in sprint {sprint}. "
              "Run 'kanban.py sync' to pull new issues from GitHub.",
              file=sys.stderr)
        sys.exit(1)

    if args.command == "transition":
        with lock_story(tf.path):
            ok = do_transition(tf, args.target)
        sys.exit(0 if ok else 1)

    if args.command == "assign":
        if not args.implementer and not args.reviewer:
            print("Provide --implementer and/or --reviewer", file=sys.stderr)
            sys.exit(2)
        with lock_story(tf.path):
            ok = do_assign(tf, implementer=args.implementer, reviewer=args.reviewer)
        sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Write a CLI smoke test**

```python
class TestCLI(unittest.TestCase):
    def test_no_command_shows_help(self):
        import subprocess
        result = subprocess.run(
            [sys.executable, str(Path(__file__).resolve().parent.parent / "scripts" / "kanban.py")],
            capture_output=True, text=True
        )
        self.assertEqual(result.returncode, 2)
```

- [ ] **Step 3: Run full test suite**

Run: `cd /Users/jonr/Documents/non-nitro-repos/giles && python -m pytest tests/test_kanban.py -v`
Expected: All PASS

Run: `cd /Users/jonr/Documents/non-nitro-repos/giles && python -m pytest tests/ -v --tb=short`
Expected: No regressions

- [ ] **Step 4: Commit**

```bash
git add scripts/kanban.py tests/test_kanban.py
git commit -m "feat: kanban CLI entry point with argparse subcommands"
```

---

## Chunk 5: Update Prompt Files and Documentation

Replace all scattered `gh issue edit` label commands with `kanban.py` calls in agent prompts and reference docs.

### Task 13: Update implementer.md

**Files:**
- Modify: `skills/sprint-run/agents/implementer.md`

- [ ] **Step 1: Replace label commands**

In step 1 (Create Branch and Draft PR, around line 89), the PR creation command stays unchanged (PR labels are out of scope). After the PR creation, add a note:

After creating the draft PR, update the tracking file with `pr_number` and `branch` fields. Then transition:
```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py" transition {story_id} design --sprint {sprint_number}
```

In step 5 (Push and Mark Ready, around line 168), replace:
```bash
gh issue edit {issue_number} --remove-label "kanban:dev" --add-label "kanban:review"
```
with:
```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py" transition {story_id} review --sprint {sprint_number}
```

Also add between steps 2 (Design) and 3 (Implement with TDD):
```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py" transition {story_id} dev --sprint {sprint_number}
```

- [ ] **Step 2: Commit**

```bash
git add skills/sprint-run/agents/implementer.md
git commit -m "docs: replace gh issue edit with kanban.py in implementer agent"
```

### Task 14: Update story-execution.md

**Files:**
- Modify: `skills/sprint-run/references/story-execution.md`

- [ ] **Step 3: Replace all label commands**

Replace `gh issue edit {issue_number} --remove-label "kanban:todo" --add-label "kanban:design"` (line 41) with:
```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py" transition {story_id} design
```

Replace `gh issue edit {issue_number} --remove-label "kanban:design" --add-label "kanban:dev"` (line 79) with:
```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py" transition {story_id} dev
```

Replace the vague "Update the GitHub issue label to `kanban:review`" (line 102) with:
```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py" transition {story_id} review
```

Replace `gh issue edit {issue_number} --remove-label "kanban:review" --add-label "kanban:done"` and `gh issue close` (lines 140-141) with:
```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py" transition {story_id} done
```

- [ ] **Step 4: Commit**

```bash
git add skills/sprint-run/references/story-execution.md
git commit -m "docs: replace gh issue edit with kanban.py in story-execution reference"
```

### Task 15: Update kanban-protocol.md

**Files:**
- Modify: `skills/sprint-run/references/kanban-protocol.md`

- [ ] **Step 5: Update GitHub Label Sync section**

Replace lines 54-59 (the manual 4-step label sync procedure) with:

```markdown
All state transitions go through the centralized state machine:

\`\`\`bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py" transition <story-id> <target-state>
\`\`\`

The script validates the transition is legal, updates the local tracking
file, and syncs the GitHub issue label atomically. Never use raw
`gh issue edit` for kanban labels — always use `kanban.py`.
```

- [ ] **Step 6: Commit**

```bash
git add skills/sprint-run/references/kanban-protocol.md
git commit -m "docs: update kanban protocol to reference kanban.py state machine"
```

### Task 16: Update tracking-formats.md

**Files:**
- Modify: `skills/sprint-run/references/tracking-formats.md`

- [ ] **Step 7: Flip source-of-truth statement**

Replace lines 44-47:
```
The `status` field mirrors kanban states: `todo`, `design`, `dev`,
`review`, `integration`, `done`. GitHub is the source of truth for story state;
`sync_tracking.py` updates local tracking files to match GitHub.
If they diverge, GitHub wins.
```
with:
```
The `status` field mirrors kanban states: `todo`, `design`, `dev`,
`review`, `integration`, `done`. Local tracking files are the source of
truth for story state; `kanban.py` syncs changes to GitHub on every
mutation. Use `kanban.py sync` to accept legal external GitHub changes.
```

- [ ] **Step 8: Commit**

```bash
git add skills/sprint-run/references/tracking-formats.md
git commit -m "docs: flip source-of-truth statement to local-authoritative"
```

### Task 17: Update ceremony-kickoff.md

**Files:**
- Modify: `skills/sprint-run/references/ceremony-kickoff.md`

- [ ] **Step 9: Add kanban.py assign to exit criteria**

After the existing exit criteria (line 252-255), add a new step:

```markdown
5. Every story's persona assignment is synced to GitHub:
   ```bash
   python "${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py" assign {story_id} --implementer {impl} --reviewer {rev}
   ```
```

- [ ] **Step 10: Commit**

```bash
git add skills/sprint-run/references/ceremony-kickoff.md
git commit -m "docs: add kanban.py assign to kickoff exit criteria"
```

### Task 18: Update sprint-run SKILL.md

**Files:**
- Modify: `skills/sprint-run/SKILL.md`

- [ ] **Step 11: Add state machine note**

After the Config & Prerequisites section (around line 28), add:

```markdown
### State Management

All story state changes (kanban transitions, persona assignment) go through
`"${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py"`. Never use raw `gh issue edit`
for kanban labels. The state machine validates transitions, updates local
tracking files atomically, and syncs GitHub as a write-through side effect.

Key commands:
- `kanban.py transition <story-id> <state>` — move a story through the kanban
- `kanban.py assign <story-id> --implementer X --reviewer Y` — assign personas
- `kanban.py sync` — pull external GitHub changes (bidirectional merge)
- `kanban.py status` — show the kanban board
```

- [ ] **Step 12: Commit**

```bash
git add skills/sprint-run/SKILL.md
git commit -m "docs: add state machine note to sprint-run SKILL.md"
```

### Task 19: Update CLAUDE.md and CHEATSHEET.md

**Files:**
- Modify: `CLAUDE.md`
- Modify: `CHEATSHEET.md`

- [ ] **Step 13: Add kanban.py to CLAUDE.md script table**

Add a new row to the Scripts table:

```markdown
| `scripts/kanban.py` | Kanban state machine — transitions, assign, sync, status | `validate_transition()` §kanban.validate_transition, `check_preconditions()` §kanban.check_preconditions, `do_transition()` §kanban.do_transition, `do_assign()` §kanban.do_assign, `do_sync()` §kanban.do_sync, `do_status()` §kanban.do_status, `find_story()` §kanban.find_story, `atomic_write_tf()` §kanban.atomic_write_tf |
```

- [ ] **Step 14: Add kanban.py section to CHEATSHEET.md**

Add a new section with line-number references for all anchored functions.

- [ ] **Step 15: Commit**

```bash
git add CLAUDE.md CHEATSHEET.md
git commit -m "docs: add kanban.py to CLAUDE.md script table and CHEATSHEET.md index"
```

### Task 20: Final regression test

- [ ] **Step 16: Run full test suite**

Run: `cd /Users/jonr/Documents/non-nitro-repos/giles && python -m pytest tests/ -v --tb=short`
Expected: All tests pass, no regressions.

- [ ] **Step 17: Verify kanban.py --help works**

Run: `cd /Users/jonr/Documents/non-nitro-repos/giles && python scripts/kanban.py --help`
Expected: Shows help with all 4 subcommands.

Run: `cd /Users/jonr/Documents/non-nitro-repos/giles && python scripts/kanban.py transition --help`
Expected: Shows transition subcommand help.
