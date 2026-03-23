"""Shared helpers for plugin hooks.

Output format follows the modern Claude Code hook protocol:
all hooks exit 0 and communicate decisions via JSON on stdout.
This avoids the stderr workaround needed by the older exit-code protocol.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def read_event() -> dict:
    """Read JSON event payload from stdin.

    Returns an empty dict if stdin is empty, closed, or contains
    invalid JSON -- hooks degrade gracefully rather than crashing.
    """
    try:
        return json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError, ValueError):
        return {}


def exit_ok(*, hook_event: str = "") -> None:
    """Allow the action and suppress output.

    For PreToolUse hooks, includes ``hookSpecificOutput`` with
    ``permissionDecision: "allow"`` to prevent phantom 'hook error'
    labels in the Claude Code UI.
    """
    result: dict = {"continue": True, "suppressOutput": True}
    if hook_event == "PreToolUse":
        result["hookSpecificOutput"] = {
            "hookEventName": "PreToolUse",
            "permissionDecision": "allow",
            "permissionDecisionReason": "",
        }
    print(json.dumps(result))
    sys.exit(0)


def exit_warn(message: str) -> None:
    """Allow the action but surface a message as additionalContext.

    Used for warnings (review_gate bare push) and context injection
    (session_context, verify_agent_output reports).
    """
    print(json.dumps({
        "continue": True,
        "suppressOutput": False,
        "additionalContext": message,
    }))
    sys.exit(0)


def exit_block(reason: str) -> None:
    """Block a PreToolUse action with a reason."""
    print(json.dumps({
        "continue": False,
        "suppressOutput": False,
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "block",
            "permissionDecisionReason": reason,
        },
    }))
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
