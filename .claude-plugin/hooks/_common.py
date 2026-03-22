"""Shared helpers for plugin hooks."""
from __future__ import annotations

import os
import sys
from pathlib import Path


def exit_ok() -> None:
    """Exit 0 with a stderr byte to silence Claude Code's 'hook error' display.

    Claude Code bug #34713: hooks that exit 0 with no stderr are mislabeled
    as 'hook error' in the transcript. Writing a newline to stderr prevents
    the false error label.
    """
    sys.stderr.write("\n")
    sys.exit(0)

_CONFIG_RELATIVE = "sprint-config/project.toml"


def _find_project_root() -> Path:
    """Locate the project root by searching for sprint-config/project.toml.

    Resolution order:
    1. ``CLAUDE_PROJECT_DIR`` environment variable (if set by Claude Code)
    2. Walk upward from CWD looking for sprint-config/project.toml
    3. Fall back to CWD
    """
    # 1. Environment variable
    env_dir = os.environ.get("CLAUDE_PROJECT_DIR")
    if env_dir:
        candidate = Path(env_dir)
        if (candidate / _CONFIG_RELATIVE).is_file():
            return candidate

    # 2. Walk upward from CWD
    current = Path.cwd().resolve()
    for parent in [current, *current.parents]:
        if (parent / _CONFIG_RELATIVE).is_file():
            return parent

    # 3. Fall back to CWD
    return Path.cwd()
