#!/usr/bin/env python3
"""Commit gate hook — blocks git commit if tests haven't been run
since the last code change.

Tracks state via a session-scoped temp file.  When source files are
modified (Write/Edit tool calls), sets needs_verification.  When
check_commands are run, clears it.  Blocks commit if verification
is still needed.
"""
from __future__ import annotations

import json
import os
import re
import sys
import tempfile
from pathlib import Path


# Source file extensions that require verification before commit
_SOURCE_EXTENSIONS = frozenset({
    ".py", ".rs", ".go", ".ts", ".tsx", ".js", ".jsx",
    ".swift", ".kt", ".java", ".c", ".cpp", ".h", ".hpp",
    ".rb", ".ex", ".exs", ".cs", ".fs", ".zig", ".lua",
    ".sh", ".bash", ".zsh",
})

# Non-source files that don't require verification
_NON_SOURCE_EXTENSIONS = frozenset({
    ".md", ".txt", ".toml", ".yaml", ".yml", ".json",
    ".cfg", ".ini", ".lock", ".csv", ".html", ".css",
    ".svg", ".png", ".jpg", ".gif", ".ico",
})


def _state_file() -> Path:
    """Return the session-scoped state file path."""
    session_id = os.environ.get("CLAUDE_SESSION_ID", "default")
    return Path(tempfile.gettempdir()) / f"giles-verification-state-{session_id}"


def is_source_file(path: str) -> bool:
    """Check if a file path is a source file requiring verification."""
    ext = Path(path).suffix.lower()
    if ext in _SOURCE_EXTENSIONS:
        return True
    if ext in _NON_SOURCE_EXTENSIONS:
        return False
    # Unknown extension — conservative: not source
    return False


def mark_needs_verification() -> None:
    """Mark that source files have been modified and tests need to run."""
    _state_file().write_text("needs_verification", encoding="utf-8")


def mark_verified() -> None:
    """Mark that check_commands have been run since last modification."""
    sf = _state_file()
    if sf.exists():
        sf.unlink()


def needs_verification() -> bool:
    """Check if verification is needed before commit."""
    return _state_file().exists()


def check_commit_allowed(command: str,
                         _state_override: bool | None = None) -> str:
    """Check whether a git commit should be allowed.

    Returns 'allowed' or 'blocked'.

    *_state_override* is for testing — when provided, uses this value
    instead of reading the state file.
    """
    # Only intercept git commit and scripts/commit.py
    is_commit = (
        re.search(r'\bgit\s+commit\b', command) or
        re.search(r'scripts/commit\.py\b', command)
    )
    if not is_commit:
        return "allowed"

    needs = _state_override if _state_override is not None else needs_verification()
    if needs:
        return "blocked"
    return "allowed"


def _matches_check_command(command: str) -> bool:
    """Check if a command matches common check_command patterns."""
    patterns = [
        r'\bpytest\b', r'\bpython\s+-m\s+pytest\b',
        r'\bcargo\s+test\b', r'\bcargo\s+clippy\b',
        r'\bnpm\s+test\b', r'\bnpm\s+run\s+test\b',
        r'\bgo\s+test\b', r'\bruff\s+check\b',
        r'\bmypy\b', r'\bjest\b', r'\bvitest\b',
        r'\bswift\s+test\b', r'\bxcodebuild\s+test\b',
    ]
    return any(re.search(p, command) for p in patterns)


# ---------------------------------------------------------------------------
# Hook entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """PreToolUse hook for Bash tool — gate commits on test verification."""
    try:
        input_data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        sys.exit(0)

    tool_input = input_data.get("tool_input", input_data.get("input", {}))
    command = tool_input.get("command", "")
    if not command:
        sys.exit(0)

    # If running a check command, clear verification state
    if _matches_check_command(command):
        mark_verified()
        sys.exit(0)

    # If committing, check verification state
    result = check_commit_allowed(command)
    if result == "blocked":
        msg = (
            "Tests have not been run since the last code change. "
            "Run check_commands before committing."
        )
        print(msg)
        sys.exit(2)

    sys.exit(0)


if __name__ == "__main__":
    main()
