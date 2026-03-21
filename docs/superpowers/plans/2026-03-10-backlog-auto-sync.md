# Backlog Auto-Sync Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Automatically sync backlog milestone files to GitHub (milestones + issues) via the monitor loop, with debounce and throttle to avoid unnecessary API calls.

**Architecture:** New `scripts/sync_backlog.py` owns the scheduling layer (file hashing, debounce, throttle, state persistence). It imports and delegates to existing idempotent creation functions in `bootstrap_github.py` and `populate_issues.py`. The sprint-monitor skill calls it as Step 0 before CI/PR checks.

**Tech Stack:** Python 3.10+ stdlib only (hashlib, json, pathlib, datetime). No new dependencies.

---

## Chunk 1: The sync engine

### Task 1: Core hashing + state persistence

**Files:**
- Create: `scripts/sync_backlog.py`
- Test: `tests/test_sync_backlog.py`

The sync engine hashes milestone files and persists state to `.sync-state.json` inside `sprint-config/`. Three fields: `file_hashes` (dict of filename→sha256), `pending_hashes` (null or dict, for debounce), `last_sync_at` (ISO timestamp or null, for throttle).

- [ ] **Step 1: Write failing test for `hash_milestone_files()`**

```python
# tests/test_sync_backlog.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m unittest tests.test_sync_backlog -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'sync_backlog'`

- [ ] **Step 3: Implement `hash_milestone_files()`**

```python
# scripts/sync_backlog.py
#!/usr/bin/env python3
"""Backlog auto-sync engine with debounce and throttle.

Hashes milestone files to detect changes. When files stabilize after
an edit (debounce), syncs new milestones and issues to GitHub using
the idempotent functions from bootstrap_github.py and populate_issues.py.

State persists in sprint-config/.sync-state.json across loop invocations.

Usage: python scripts/sync_backlog.py
Exit: 0 = no action needed or synced, 1 = error.
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# -- Import shared config ----------------------------------------------------
sys.path.insert(0, str(Path(__file__).resolve().parent))
from validate_config import load_config, get_milestones

# -- Constants ---------------------------------------------------------------

THROTTLE_FLOOR_SECONDS = 600  # 10 minutes
STATE_FILENAME = ".sync-state.json"


def hash_milestone_files(file_paths: list[str]) -> dict[str, str]:
    """SHA-256 hash each milestone file. Returns {filename: hex_digest}."""
    result: dict[str, str] = {}
    for fp in file_paths:
        p = Path(fp)
        if not p.is_file():
            continue
        digest = hashlib.sha256(p.read_bytes()).hexdigest()
        result[p.name] = digest
    return result
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m unittest tests.test_sync_backlog -v`
Expected: 3 PASSED

- [ ] **Step 5: Write failing test for state load/save**

Add to `tests/test_sync_backlog.py`:

```python
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
```

- [ ] **Step 6: Run test to verify it fails**

Run: `.venv/bin/python -m unittest tests.test_sync_backlog -v`
Expected: FAIL — `AttributeError: module 'sync_backlog' has no attribute 'load_state'`

- [ ] **Step 7: Implement `load_state()` and `save_state()`**

Add to `scripts/sync_backlog.py`:

```python
def _default_state() -> dict:
    """Return a fresh state dict."""
    return {
        "file_hashes": {},
        "pending_hashes": None,
        "last_sync_at": None,
    }


def load_state(config_dir: Path) -> dict:
    """Load sync state from .sync-state.json, or return defaults."""
    path = config_dir / STATE_FILENAME
    if not path.is_file():
        return _default_state()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return _default_state()
        # Ensure all keys present
        defaults = _default_state()
        for key in defaults:
            if key not in data:
                data[key] = defaults[key]
        return data
    except (json.JSONDecodeError, OSError):
        return _default_state()


def save_state(config_dir: Path, state: dict) -> None:
    """Write sync state to .sync-state.json."""
    path = config_dir / STATE_FILENAME
    path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
```

- [ ] **Step 8: Run test to verify it passes**

Run: `.venv/bin/python -m unittest tests.test_sync_backlog -v`
Expected: 3 PASSED

- [ ] **Step 9: Commit**

```bash
git add scripts/sync_backlog.py tests/test_sync_backlog.py
git commit -m "feat: add sync_backlog core — file hashing and state persistence"
```

---

### Task 2: The scheduling algorithm (debounce + throttle)

**Files:**
- Modify: `scripts/sync_backlog.py`
- Test: `tests/test_sync_backlog.py`

The `check_sync()` function implements the full decision algorithm. It returns a `SyncResult` with a status string and an optional count of created items. The actual GitHub sync is delegated to a callback so tests can mock it.

- [ ] **Step 1: Write failing tests for the scheduling algorithm**

Add to `tests/test_sync_backlog.py`:

```python
from datetime import datetime, timezone, timedelta


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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m unittest tests.test_sync_backlog.TestCheckSync -v`
Expected: FAIL — `AttributeError: module 'sync_backlog' has no attribute 'check_sync'`

- [ ] **Step 3: Implement `SyncResult` and `check_sync()`**

Add to `scripts/sync_backlog.py`:

```python
from dataclasses import dataclass


@dataclass
class SyncResult:
    """Result of the sync scheduling decision."""
    status: str        # "no_changes", "debouncing", "throttled", "sync"
    should_sync: bool
    message: str = ""


def _is_throttled(state: dict, now: datetime) -> bool:
    """Check if last sync was within the throttle floor."""
    last = state.get("last_sync_at")
    if not last:
        return False
    try:
        last_dt = datetime.fromisoformat(last)
        return (now - last_dt).total_seconds() < THROTTLE_FLOOR_SECONDS
    except (ValueError, TypeError):
        return False


def check_sync(
    current_hashes: dict[str, str],
    state: dict,
    now: datetime,
) -> SyncResult:
    """Decide whether to sync based on file hashes, debounce, and throttle.

    Mutates state in-place (sets pending_hashes, etc.). Caller is
    responsible for saving state and performing the actual sync.
    """
    stored = state.get("file_hashes", {})
    pending = state.get("pending_hashes")

    # No change at all
    if current_hashes == stored and pending is None:
        return SyncResult("no_changes", False, "no changes detected")

    # Edits reverted to stored state while debounce was pending
    if current_hashes == stored and pending is not None:
        state["pending_hashes"] = None
        return SyncResult("no_changes", False, "changes reverted, cancelled pending sync")

    # Files differ from stored — something changed
    if current_hashes != stored:
        if pending is None:
            # First detection: start debounce
            state["pending_hashes"] = current_hashes
            return SyncResult("debouncing", False, "change detected, debouncing")
        if current_hashes != pending:
            # Still changing: re-debounce
            state["pending_hashes"] = current_hashes
            return SyncResult("debouncing", False, "files still changing, re-debouncing")

    # current_hashes == pending (stabilized) — ready to sync if not throttled
    if _is_throttled(state, now):
        return SyncResult("throttled", False, "throttled, will sync later")

    return SyncResult("sync", True, "files stabilized, syncing")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m unittest tests.test_sync_backlog.TestCheckSync -v`
Expected: 7 PASSED

- [ ] **Step 5: Commit**

```bash
git add scripts/sync_backlog.py tests/test_sync_backlog.py
git commit -m "feat: add check_sync scheduling algorithm with debounce and throttle"
```

---

### Task 3: The sync action — wiring to bootstrap/populate

**Files:**
- Modify: `scripts/sync_backlog.py`
- Test: `tests/test_sync_backlog.py`
- Read: `skills/sprint-setup/scripts/bootstrap_github.py`, `skills/sprint-setup/scripts/populate_issues.py`

This task adds `do_sync()` which calls the existing idempotent functions from `bootstrap_github` and `populate_issues`, and `main()` which ties everything together.

- [ ] **Step 1: Write failing test for `do_sync()`**

Add to `tests/test_sync_backlog.py`:

```python
sys.path.insert(0, str(ROOT / "tests"))

from fake_github import FakeGitHub, make_patched_subprocess


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
            self.assertIn("milestones", created)
            self.assertIn("issues", created)

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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m unittest tests.test_sync_backlog.TestDoSync -v`
Expected: FAIL — `AttributeError: module 'sync_backlog' has no attribute 'do_sync'`

- [ ] **Step 3: Implement `do_sync()`**

Add to `scripts/sync_backlog.py`:

```python
def do_sync(config: dict) -> dict[str, int]:
    """Run the idempotent milestone + issue creation. Return counts.

    Imports bootstrap_github and populate_issues lazily to avoid pulling
    in the setup scripts at module load time.
    """
    # Lazy import — only needed when actually syncing
    _setup_scripts = str(Path(__file__).resolve().parent.parent / "skills" / "sprint-setup" / "scripts")
    if _setup_scripts not in sys.path:
        sys.path.insert(0, _setup_scripts)
    import bootstrap_github
    import populate_issues

    result = {"milestones": 0, "issues": 0}

    # 1. Create milestones
    milestone_files = get_milestones(config)
    if not milestone_files:
        return result

    bootstrap_github.create_milestones_on_github(config)
    result["milestones"] = len(milestone_files)

    # 2. Create issues
    stories = populate_issues.parse_milestone_stories(milestone_files, config)
    if not stories:
        return result

    populate_issues.enrich_from_epics(stories, config)
    existing = populate_issues.get_existing_issues()
    milestone_numbers = populate_issues.get_milestone_numbers()
    milestone_titles = populate_issues._build_milestone_title_map(milestone_files)

    created = 0
    for story in stories:
        if story.story_id in existing:
            continue
        if populate_issues.create_issue(story, milestone_numbers, milestone_titles):
            created += 1
    result["issues"] = created
    return result
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m unittest tests.test_sync_backlog.TestDoSync -v`
Expected: 2 PASSED

- [ ] **Step 5: Commit**

```bash
git add scripts/sync_backlog.py tests/test_sync_backlog.py
git commit -m "feat: add do_sync — wires scheduling to bootstrap/populate"
```

---

### Task 4: The `main()` entry point

**Files:**
- Modify: `scripts/sync_backlog.py`
- Test: `tests/test_sync_backlog.py`

`main()` ties it all together: load config, hash files, check sync decision, optionally run `do_sync()`, save state, print status line.

- [ ] **Step 1: Write failing test for `main()`**

Add to `tests/test_sync_backlog.py`:

```python
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
            f'[project]\nname = "test"\nrepo = "o/r"\nlanguage = "python"\n\n'
            f'[paths]\nteam_dir = "{team_dir}"\nbacklog_dir = "{backlog}"\n'
            f'sprints_dir = "{root / "sprints"}"\n\n'
            f'[ci]\ncheck_commands = ["pytest"]\nbuild_command = "echo ok"\n'
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m unittest tests.test_sync_backlog.TestMain -v`
Expected: FAIL — `sync_backlog.main` doesn't return status yet (or doesn't exist as this form)

- [ ] **Step 3: Implement `main()`**

Add to `scripts/sync_backlog.py`:

```python
def main() -> str:
    """Run one sync cycle. Returns status string.

    Intended to be called from sprint-monitor on each loop iteration,
    or standalone for manual sync.
    """
    config = load_config()
    milestone_files = get_milestones(config)

    if not milestone_files:
        print("sync: no milestone files found")
        return "no_changes"

    # Determine config dir for state file
    paths = config.get("paths", {})
    backlog_dir = paths.get("backlog_dir", "sprint-config/backlog")
    config_dir = Path(backlog_dir).parent  # sprint-config/

    now = datetime.now(timezone.utc)
    current_hashes = hash_milestone_files(milestone_files)
    state = load_state(config_dir)

    result = check_sync(current_hashes, state, now)
    print(f"sync: {result.message}")

    if result.should_sync:
        counts = do_sync(config)
        state["file_hashes"] = current_hashes
        state["pending_hashes"] = None
        state["last_sync_at"] = now.isoformat()
        print(f"sync: created {counts['issues']} issues, "
              f"synced {counts['milestones']} milestones")
    elif result.status == "no_changes":
        pass  # state unchanged
    # For debouncing/throttled, state was already mutated by check_sync

    save_state(config_dir, state)
    return result.status


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"sync: error — {exc}", file=sys.stderr)
        sys.exit(1)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m unittest tests.test_sync_backlog.TestMain -v`
Expected: 3 PASSED

- [ ] **Step 5: Run full test suite to verify nothing broke**

Run: `.venv/bin/python -m unittest discover -s tests -v`
Expected: All tests pass

- [ ] **Step 6: Commit**

```bash
git add scripts/sync_backlog.py tests/test_sync_backlog.py
git commit -m "feat: add sync_backlog main() — full debounce+throttle entry point"
```

---

## Chunk 2: Integration with sprint-monitor and housekeeping

### Task 5: Update sprint-monitor skill to call sync_backlog

**Files:**
- Modify: `skills/sprint-monitor/SKILL.md`
- Modify: `skills/sprint-monitor/scripts/check_status.py`

Add Step 0 (backlog sync) before the existing CI check step. The monitor calls `sync_backlog.main()` and includes its status line in the report.

- [ ] **Step 1: Edit `SKILL.md` to add Step 0**

In `skills/sprint-monitor/SKILL.md`, after the "Each invocation performs four steps" list (line 21), change it to five steps:

```markdown
Each invocation performs five steps in order:
0. Sync backlog to GitHub (milestones + issues)
1. Check CI status
2. Check open PRs
3. Update burndown
4. Report a one-line summary
```

Then insert a new section before "## Step 1 -- Check CI Status" (before line 45):

```markdown
## Step 0 -- Sync Backlog

Run the backlog sync engine to detect new or changed milestone files and
create corresponding GitHub milestones and issues:

\```bash
python3 scripts/sync_backlog.py
\```

This script:
- Hashes milestone files and compares against cached state.
- **Debounce:** waits one iteration after detecting a change before syncing
  (in case the user is still editing).
- **Throttle:** syncs at most once per 10 minutes.
- Delegates to the idempotent `bootstrap_github.create_milestones_on_github()`
  and `populate_issues.create_issue()` functions.
- Prints a one-line status: `sync: no changes detected`, `sync: change detected,
  debouncing`, `sync: throttled, will sync later`, or `sync: created N issues,
  synced M milestones`.

If the script fails, log the error and continue with Step 1. The sync is
best-effort and must not block monitoring.
```

- [ ] **Step 2: Add sync import and call to `check_status.py`**

At the top of `skills/sprint-monitor/scripts/check_status.py`, after the existing `sys.path.insert` and `from validate_config import load_config` (line 24), add:

```python
# -- Import sync engine ------------------------------------------------------
try:
    from sync_backlog import main as sync_backlog_main
except ImportError:
    sync_backlog_main = None
```

In `main()` (around line 297), before the `for fn in [check_ci, check_prs, ...]` loop, add:

```python
    # Step 0: Sync backlog
    if sync_backlog_main is not None:
        try:
            sync_status = sync_backlog_main()
            report_lines.append(f"Sync: {sync_status}")
        except Exception as exc:
            report_lines.append(f"Sync: error — {exc}")
```

- [ ] **Step 3: Write test for sync integration in check_status**

Add to `tests/test_gh_interactions.py` (or `tests/test_sync_backlog.py`):

```python
class TestCheckStatusSyncIntegration(unittest.TestCase):
    """Verify check_status imports and calls sync_backlog when available."""

    def test_sync_import_exists(self):
        """check_status can import sync_backlog_main."""
        from importlib import reload
        import check_status as cs
        reload(cs)
        self.assertIsNotNone(cs.sync_backlog_main)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m unittest tests.test_sync_backlog -v`
Expected: All pass

- [ ] **Step 5: Commit**

```bash
git add skills/sprint-monitor/SKILL.md skills/sprint-monitor/scripts/check_status.py tests/test_sync_backlog.py
git commit -m "feat: integrate sync_backlog into sprint-monitor as Step 0"
```

---

### Task 6: Update Makefile lint target and CLAUDE.md/CHEATSHEET.md

**Files:**
- Modify: `Makefile`
- Modify: `CLAUDE.md`
- Modify: `CHEATSHEET.md` (if it exists and has script index)

- [ ] **Step 1: Add `sync_backlog.py` to Makefile lint target**

In `Makefile`, after the `py_compile` line for `scripts/sprint_teardown.py` (around line 33), add:

```makefile
	$(PYTHON) -m py_compile scripts/sync_backlog.py
```

- [ ] **Step 2: Update CLAUDE.md script table**

In `CLAUDE.md`, add a row to the "Scripts" table:

```markdown
| `scripts/sync_backlog.py` | Backlog auto-sync with debounce/throttle | `hash_milestone_files()`, `check_sync()`, `do_sync()`, `main()` |
```

Also update the sprint-monitor SKILL.md entry in the "Key sections" column to mention the new Step 0.

- [ ] **Step 3: Update CHEATSHEET.md**

Add a section for `sync_backlog.py` with line-number index (exact line numbers will be determined after implementation).

- [ ] **Step 4: Run full test suite**

Run: `make test`
Expected: All tests pass, lint passes

- [ ] **Step 5: Commit**

```bash
git add Makefile CLAUDE.md CHEATSHEET.md
git commit -m "docs: add sync_backlog to lint target, CLAUDE.md, and CHEATSHEET.md"
```
