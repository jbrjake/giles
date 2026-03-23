"""Shared helpers for plugin hooks.

Output format follows the modern Claude Code hook protocol:
all hooks exit 0 and communicate decisions via JSON on stdout.
This avoids the stderr workaround needed by the older exit-code protocol.

BH-009: Shared TOML reader consolidated here from verify_agent_output.py
to eliminate triple-parser divergence (PAT-003) and circular dependency.
"""
from __future__ import annotations

import json
import os
import re
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


# ---------------------------------------------------------------------------
# Shared TOML reader (BH-009: consolidated from verify_agent_output)
# ---------------------------------------------------------------------------

def _unescape_basic_string(s: str) -> str:
    """Unescape TOML basic string escape sequences.

    Per TOML spec, double-quoted strings process escape sequences:
    \\", \\\\, \\n, \\t, \\r, \\b, \\f, \\uXXXX, \\UXXXXXXXX.
    Unknown escapes are preserved as-is for safety.

    BK-002: Added \\b, \\f, \\uXXXX, \\UXXXXXXXX to match
    validate_config._unescape_toml_string (PAT-004 fix).
    """
    result: list[str] = []
    i = 0
    while i < len(s):
        if s[i] == '\\' and i + 1 < len(s):
            nxt = s[i + 1]
            if nxt == '"':
                result.append('"')
            elif nxt == '\\':
                result.append('\\')
            elif nxt == 'n':
                result.append('\n')
            elif nxt == 't':
                result.append('\t')
            elif nxt == 'r':
                result.append('\r')
            elif nxt == 'b':
                result.append('\b')
            elif nxt == 'f':
                result.append('\f')
            elif nxt == 'u' and i + 6 <= len(s):
                try:
                    result.append(chr(int(s[i + 2:i + 6], 16)))
                    i += 6
                    continue
                except (ValueError, OverflowError):
                    result.append(s[i:i + 2])
            elif nxt == 'U' and i + 10 <= len(s):
                try:
                    result.append(chr(int(s[i + 2:i + 10], 16)))
                    i += 10
                    continue
                except (ValueError, OverflowError):
                    result.append(s[i:i + 2])
            else:
                result.append(s[i])
                result.append(nxt)
            i += 2
        else:
            result.append(s[i])
            i += 1
    return "".join(result)


def _count_trailing_backslashes(s: str, pos: int) -> int:
    """Count consecutive backslashes immediately before position *pos*.

    BK-005: Shared with validate_config.py — used for even/odd parity
    check to determine whether a quote character is escaped.
    """
    n = 0
    while pos - 1 - n >= 0 and s[pos - 1 - n] == "\\":
        n += 1
    return n


def _strip_inline_comment(val: str) -> str:
    """Remove trailing # comments that are outside of quotes.

    BK-005: Aligned with validate_config._strip_inline_comment — same
    parity-check algorithm for escape handling.
    """
    quote_char = None  # None, '"', or "'"
    for i, ch in enumerate(val):
        if quote_char is None:
            if ch in ('"', "'"):
                quote_char = ch
            elif ch == "#":
                return val[:i].rstrip()
        elif ch == quote_char:
            if quote_char == '"' and _count_trailing_backslashes(val, i) % 2 != 0:
                continue  # escaped double quote
            quote_char = None
    return val


def _has_unquoted_bracket(s: str) -> bool:
    """Check if s contains a ] that is not inside quotes."""
    in_quote = False
    quote_char = ""
    i = 0
    while i < len(s):
        ch = s[i]
        if ch == "\\" and in_quote and quote_char == '"':
            i += 2
            continue
        if ch in ('"', "'") and not in_quote:
            in_quote = True
            quote_char = ch
        elif ch == quote_char and in_quote:
            in_quote = False
        elif ch == "]" and not in_quote:
            return True
        i += 1
    return False


def read_toml_key(text: str, section: str, key: str) -> str | list[str] | None:
    """Extract a key from a TOML section.

    Shared lightweight TOML reader for all hooks. Handles:
    - Double-quoted strings with escape processing
    - Single-quoted literal strings
    - Unquoted bare values
    - Multi-line arrays
    - Inline comments
    - Section headers with trailing comments
    """
    in_section = False
    lines = text.split('\n')
    i = 0
    while i < len(lines):
        stripped = lines[i].strip()
        if stripped.startswith("["):
            in_section = stripped.split('#')[0].strip() == f"[{section}]"
            i += 1
            continue
        if not in_section:
            i += 1
            continue
        m = re.match(rf'{re.escape(key)}\s*=\s*(.*)', stripped)
        if m:
            val = _strip_inline_comment(m.group(1).strip())
            if val.startswith("["):
                array_text = val
                while not _has_unquoted_bracket(array_text) and i + 1 < len(lines):
                    i += 1
                    array_text += " " + _strip_inline_comment(lines[i].strip())
                items = re.findall(r'"((?:[^"\\]|\\.)*)"|\'([^\']*)\'', array_text)
                return [_unescape_basic_string(a) if a else b for a, b in items]
            if val.startswith('"') and val.endswith('"'):
                return _unescape_basic_string(val[1:-1])
            if val.startswith("'") and val.endswith("'"):
                return val[1:-1]
            return val if val else None
        i += 1
    return None
