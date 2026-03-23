#!/usr/bin/env python3
"""Commit gate hook -- blocks git commit if tests haven't been run
since the last code change.

Uses git working-tree state comparison instead of Write/Edit hooks.
When check_commands are run, records a hash of the working tree state.
Blocks commit if the working tree has changed since tests last ran.
"""
from __future__ import annotations

import hashlib
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import _find_project_root, exit_block, exit_ok, read_event


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
    # Unknown extension -- conservative: not source
    return False


def _working_tree_hash() -> str:
    """Hash of all changes (staged + unstaged) relative to HEAD.

    This captures the working tree state at the time tests are run.
    If the hash changes between test run and commit, tests need to re-run.
    Returns "" on failure (git not available, empty repo, etc.).
    """
    try:
        result = subprocess.run(
            ["git", "diff", "HEAD"],
            capture_output=True, timeout=5,
        )
        if result.returncode != 0:
            # BH37-025: Fall back to staged diff for empty repos (no HEAD)
            result = subprocess.run(
                ["git", "diff", "--cached"],
                capture_output=True, timeout=5,
            )
            if result.returncode != 0:
                return ""
        return hashlib.sha256(result.stdout).hexdigest()[:16]
    except Exception:
        return ""


def _has_staged_source_files() -> bool:
    """Check if there are staged source files in the git index."""
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode != 0:
            return False
        for line in result.stdout.splitlines():
            if is_source_file(line.strip()):
                return True
    except Exception:
        pass
    return False


def mark_verified() -> None:
    """Record the working tree hash at verification time."""
    h = _working_tree_hash()
    if h:
        _state_file().write_text(h, encoding="utf-8")


def needs_verification() -> bool:
    """Check if the working tree has changed since tests last ran.

    Returns True if:
    - No verification has ever happened AND there are staged source files
    - The working tree hash has changed since last verification
    - Git is unavailable (fail closed -- assume verification needed)
    """
    sf = _state_file()
    if not sf.exists():
        return _has_staged_source_files()
    stored = sf.read_text(encoding="utf-8").strip()
    current = _working_tree_hash()
    if not current:
        # Git failed -- can't determine state, assume verification needed
        return True
    return stored != current


def check_commit_allowed(command: str,
                         _state_override: bool | None = None) -> str:
    """Check whether a git commit should be allowed.

    Returns 'allowed' or 'blocked'.

    Handles compound shell commands (``&&``, ``;``, ``|``) by splitting
    on shell operators and checking each subcommand independently.

    *_state_override* is for testing -- when provided, uses this value
    instead of the actual working tree state check.
    """
    # BH-005: Split compound commands and check each subcommand
    for subcommand in re.split(r'\s*(?:&&|\|\||\||;)\s*', command):
        result = _check_commit_single(subcommand.strip(),
                                      _state_override=_state_override)
        if result != "allowed":
            return result
    return "allowed"


def _check_commit_single(command: str,
                          _state_override: bool | None = None) -> str:
    """Check a single (non-compound) command for git commit."""
    # Only intercept git commit and scripts/commit.py
    is_commit = (
        re.search(r'\bgit\s+commit\b', command) or
        re.search(r'scripts/commit\.py\b', command)
    )
    if not is_commit:
        return "allowed"

    # BH31-001: Allow --dry-run through -- it validates without committing
    if re.search(r'--dry-run\b', command):
        return "allowed"

    needs = _state_override if _state_override is not None else needs_verification()
    if needs:
        return "blocked"
    return "allowed"


def _load_config_check_commands() -> list[str]:
    """Read check_commands from project.toml if available.

    BH30-002: Uses verify_agent_output._read_toml_key (proper array-bounded
    parser) instead of an inline parser that read past the array boundary.
    Falls back to empty list if config not found.
    """
    try:
        toml_path = _find_project_root() / "sprint-config" / "project.toml"
        if not toml_path.is_file():
            return []
        text = toml_path.read_text(encoding="utf-8")
        from verify_agent_output import _read_toml_key
        result = _read_toml_key(text, "ci", "check_commands")
        if isinstance(result, list):
            return result
    except Exception:
        pass
    return []


# BH27-004: Cached config commands -- loaded once per process.
_CONFIG_CHECK_COMMANDS: list[str] | None = None


def _matches_check_command(command: str) -> bool:
    """Check if a command matches a configured or common check command."""
    global _CONFIG_CHECK_COMMANDS
    if _CONFIG_CHECK_COMMANDS is None:
        _CONFIG_CHECK_COMMANDS = _load_config_check_commands()

    # First check: match against config-defined check_commands
    for cfg_cmd in _CONFIG_CHECK_COMMANDS:
        # BH35-010: Word boundaries prevent substring matches
        # BH38-201: Match all words of the configured command, not just the first,
        # so "python -m pytest" won't match "python some_script.py"
        if cfg_cmd:
            tokens = cfg_cmd.split()
            pattern = r'\b' + r'\s+'.join(re.escape(t) for t in tokens) + r'\b'
            if re.search(pattern, command):
                return True

    # Fallback: hardcoded patterns for common test runners
    patterns = [
        r'\bpytest\b', r'\bpython\s+-m\s+pytest\b',
        r'\bcargo\s+test\b', r'\bcargo\s+clippy\b',
        r'\bnpm\s+test\b', r'\bnpm\s+run\s+test\b',
        r'\bgo\s+test\b', r'\bruff\s+check\b',
        r'\bmypy\b', r'\bjest\b', r'\bvitest\b',
        r'\bswift\s+test\b', r'\bxcodebuild\s+test\b',
        r'\bmake\s+test\b', r'\bbazel\s+test\b',
    ]
    return any(re.search(p, command) for p in patterns)


# ---------------------------------------------------------------------------
# PostToolUse handler
# ---------------------------------------------------------------------------

def handle_post_tool_use(command: str, *, exit_code: int) -> None:
    """Record verification state after a check command passes."""
    if exit_code != 0:
        return
    if not _matches_check_command(command):
        return
    mark_verified()


# ---------------------------------------------------------------------------
# Hook entry points
# ---------------------------------------------------------------------------

def main() -> None:
    """PreToolUse hook for Bash tool -- gate commits on test verification."""
    input_data = read_event()

    tool_input = input_data.get("tool_input", input_data.get("input", {}))
    command = tool_input.get("command", "")
    if not command:
        exit_ok(hook_event="PreToolUse")

    # If committing, check verification state
    result = check_commit_allowed(command)
    if result == "blocked":
        exit_block(
            "Tests have not been run since the last code change. "
            "Run check_commands before committing."
        )

    exit_ok(hook_event="PreToolUse")


def post_main() -> None:
    """PostToolUse hook for Bash tool -- record verification after tests pass."""
    input_data = read_event()

    tool_input = input_data.get("tool_input", input_data.get("input", {}))
    command = tool_input.get("command", "")
    tool_output = input_data.get("tool_output",
                    input_data.get("tool_response",
                    input_data.get("output", {})))
    # BH-008: tool_output may be a string instead of dict
    if not isinstance(tool_output, dict):
        tool_output = {}
    exit_code = tool_output.get("exit_code", tool_output.get("exitCode", -1))
    if isinstance(exit_code, str):
        try:
            exit_code = int(exit_code)
        except ValueError:
            exit_code = -1

    handle_post_tool_use(command, exit_code=exit_code)

    exit_ok()


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--post":
        post_main()
    else:
        main()
