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
