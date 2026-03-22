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
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

# -- Import shared config ----------------------------------------------------
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "skills" / "sprint-setup" / "scripts"))
from validate_config import load_config, get_milestones, ConfigError

try:
    import bootstrap_github
    import populate_issues
except ImportError as _import_err:
    # BH31: Warn early so users can diagnose import failures before sync time
    print(f"sync_backlog: warning — optional imports unavailable: {_import_err}",
          file=sys.stderr)
    bootstrap_github = None  # type: ignore[assignment]
    populate_issues = None  # type: ignore[assignment]

# -- Constants ---------------------------------------------------------------

# §sync_backlog.THROTTLE_FLOOR_SECONDS
THROTTLE_FLOOR_SECONDS = 600  # 10 minutes
# §sync_backlog.STATE_FILENAME
STATE_FILENAME = ".sync-state.json"


# §sync_backlog.hash_milestone_files
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


# §sync_backlog._default_state
def _default_state() -> dict:
    """Return a fresh state dict."""
    return {
        "file_hashes": {},
        "pending_hashes": None,
        "last_sync_at": None,
    }


# §sync_backlog.load_state
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


# §sync_backlog.save_state
def save_state(config_dir: Path, state: dict) -> None:
    """Write sync state to .sync-state.json."""
    path = config_dir / STATE_FILENAME
    path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


@dataclass
# §sync_backlog.SyncResult
class SyncResult:
    """Result of the sync scheduling decision."""
    status: str        # "no_changes", "debouncing", "throttled", "sync"
    should_sync: bool
    message: str = ""


# §sync_backlog._is_throttled
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


# §sync_backlog.check_sync
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


# §sync_backlog.do_sync
def do_sync(config: dict) -> dict[str, int]:
    """Run the idempotent milestone + issue creation. Return counts.

    Uses bootstrap_github and populate_issues (imported at module level
    with graceful fallback if sprint-setup scripts are unavailable).
    """
    if bootstrap_github is None or populate_issues is None:
        raise ImportError("bootstrap_github or populate_issues not available")

    result = {"milestones": 0, "issues": 0}

    # 1. Create milestones
    milestone_files = get_milestones(config)
    if not milestone_files:
        return result

    result["milestones"] = bootstrap_github.create_milestones_on_github(config)

    # 2. Create issues
    stories = populate_issues.parse_milestone_stories(milestone_files, config)
    if not stories:
        return result

    stories = populate_issues.enrich_from_epics(stories, config)
    existing = populate_issues.get_existing_issues()
    milestone_numbers = populate_issues.get_milestone_numbers()
    milestone_titles = populate_issues.build_milestone_title_map(milestone_files)

    created = 0
    failed = 0
    for story in stories:
        if story.story_id in existing:
            continue
        if populate_issues.create_issue(story, milestone_numbers, milestone_titles):
            created += 1
        else:
            failed += 1
    result["issues"] = created
    result["failed"] = failed
    return result


# §sync_backlog.main
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
    config_dir = Path(config.get("_config_dir", "sprint-config"))

    now = datetime.now(timezone.utc)
    current_hashes = hash_milestone_files(milestone_files)
    state = load_state(config_dir)

    result = check_sync(current_hashes, state, now)
    print(f"sync: {result.message}")

    if result.should_sync:
        # Note: there is a narrow TOCTOU window between hashing above and
        # reading files inside do_sync().  The debounce mechanism mitigates
        # this — hashes must be stable across multiple invocations before
        # syncing, so a file edited during the ~100 ms gap would simply
        # cause the next check to detect a change and re-sync.
        try:
            counts = do_sync(config)
        except Exception as exc:
            # BH-021: Do NOT update state on failure — next run should retry
            print(f"sync: do_sync failed — {exc}", file=sys.stderr)
            print("sync: state NOT updated; next run will retry")
            save_state(config_dir, state)
            return "error"
        failed = counts.get("failed", 0)
        if failed:
            # Partial failure: some issues created, some failed.
            # Do NOT update hashes — next run should retry the failures.
            print(f"sync: created {counts['issues']} issues, "
                  f"{failed} failed — state NOT updated for retry",
                  file=sys.stderr)
        else:
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
    except (ConfigError, RuntimeError, ImportError) as exc:
        # BH18-015: Catch specific exceptions instead of bare Exception
        # to avoid swallowing unexpected bugs (KeyboardInterrupt, etc.)
        print(f"sync: error — {exc}", file=sys.stderr)
        sys.exit(1)
