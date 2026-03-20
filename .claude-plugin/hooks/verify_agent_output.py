#!/usr/bin/env python3
"""SubagentStop verification hook — runs check_commands after agent completion.

When an implementer or fix agent completes, this hook runs the project's
``[ci] check_commands`` and compares results against the agent's claims.
If any command fails, it injects failure output.  If all pass, it
confirms verification.

Optionally runs ``smoke_command`` if configured.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

from hooks._common import _find_project_root


# ---------------------------------------------------------------------------
# Config reading (lightweight, no import dependency on validate_config)
# ---------------------------------------------------------------------------

def _strip_inline_comment(val: str) -> str:
    """Strip an inline TOML comment, respecting quoted strings."""
    in_quote = False
    quote_char = ""
    for j, ch in enumerate(val):
        if ch in ('"', "'") and not in_quote:
            in_quote = True
            quote_char = ch
        elif ch == quote_char and in_quote:
            in_quote = False
        elif ch == "#" and not in_quote:
            return val[:j].rstrip()
    return val


def _has_unquoted_bracket(s: str) -> bool:
    """Check if s contains a ] that is not inside quotes."""
    in_quote = False
    quote_char = ""
    for ch in s:
        if ch in ('"', "'") and not in_quote:
            in_quote = True
            quote_char = ch
        elif ch == quote_char and in_quote:
            in_quote = False
        elif ch == "]" and not in_quote:
            return True
    return False


def _read_toml_key(text: str, section: str, key: str) -> str | list[str] | None:
    """Extract a key from a TOML section.  Minimal parser for hook use."""
    in_section = False
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        stripped = lines[i].strip()
        if stripped.startswith("["):
            in_section = stripped == f"[{section}]"
            i += 1
            continue
        if not in_section:
            i += 1
            continue
        m = re.match(rf'{re.escape(key)}\s*=\s*(.*)', stripped)
        if m:
            val = _strip_inline_comment(m.group(1).strip())
            if val.startswith("["):
                # Collect multi-line array: accumulate until unquoted ]
                array_text = val
                while not _has_unquoted_bracket(array_text) and i + 1 < len(lines):
                    i += 1
                    array_text += " " + lines[i].strip()
                # Match both double and single quoted strings
                items = re.findall(r'"([^"]*)"|\'([^\']*)\'', array_text)
                return [a or b for a, b in items]
            if val.startswith('"') and val.endswith('"'):
                return val[1:-1]
            if val.startswith("'") and val.endswith("'"):
                return val[1:-1]
            return val
        i += 1
    return None


def load_check_commands(config_path: str | None = None,
                        ) -> tuple[list[str], str | None]:
    """Return (check_commands, smoke_command) from project.toml."""
    if config_path is None:
        p = _find_project_root() / "sprint-config" / "project.toml"
    else:
        p = Path(config_path)
    if not p.is_file():
        return [], None
    text = p.read_text(encoding="utf-8")
    check = _read_toml_key(text, "ci", "check_commands")
    if not isinstance(check, list):
        check = []
    smoke = _read_toml_key(text, "ci", "smoke_command")
    if isinstance(smoke, list):
        smoke = None
    return check, smoke


# ---------------------------------------------------------------------------
# Verification runner
# ---------------------------------------------------------------------------

def run_verification(check_commands: list[str],
                     smoke_command: str | None = None,
                     timeout: int = 120) -> tuple[str, bool]:
    """Run check commands and optional smoke command.

    Returns (report, all_passed) where report is a human-readable
    string and all_passed is True if every command exited 0.
    """
    if not check_commands and not smoke_command:
        return "VERIFICATION SKIPPED: no check_commands configured", True

    lines: list[str] = []
    all_passed = True

    for cmd in check_commands:
        try:
            # Trust boundary: commands come from project.toml, which is a project-controlled
            # config file. The user who configures check_commands/smoke_command accepts
            # responsibility for their content. This is equivalent to CI config.
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True,
                timeout=timeout,
            )
            if result.returncode == 0:
                lines.append(f"  PASS: {cmd}")
            else:
                all_passed = False
                stderr = result.stderr.strip()[:500] if result.stderr else "(no stderr)"
                lines.append(f"  FAIL: {cmd} (exit {result.returncode})")
                lines.append(f"    stderr: {stderr}")
        except subprocess.TimeoutExpired:
            all_passed = False
            lines.append(f"  FAIL: {cmd} (timed out after {timeout}s)")
        except Exception as exc:
            all_passed = False
            lines.append(f"  FAIL: {cmd} (error: {exc})")

    if smoke_command:
        try:
            # Trust boundary: commands come from project.toml, which is a project-controlled
            # config file. The user who configures check_commands/smoke_command accepts
            # responsibility for their content. This is equivalent to CI config.
            result = subprocess.run(
                smoke_command, shell=True, capture_output=True, text=True,
                timeout=timeout,
            )
            if result.returncode == 0:
                lines.append(f"  SMOKE PASS: {smoke_command}")
            else:
                all_passed = False
                stderr = result.stderr.strip()[:500] if result.stderr else "(no stderr)"
                lines.append(f"  SMOKE FAIL: {smoke_command} (exit {result.returncode})")
                lines.append(f"    stderr: {stderr}")
        except subprocess.TimeoutExpired:
            all_passed = False
            lines.append(f"  SMOKE FAIL: {smoke_command} (timed out)")
        except Exception as exc:
            all_passed = False
            lines.append(f"  SMOKE FAIL: {smoke_command} (error: {exc})")

    n = len(check_commands) + (1 if smoke_command else 0)
    if all_passed:
        header = f"VERIFICATION PASSED: {n} check command(s) confirmed"
    else:
        header = "VERIFICATION FAILED: agent claimed completion but checks failed"

    return header + "\n" + "\n".join(lines), all_passed


# ---------------------------------------------------------------------------
# Tracking file update
# ---------------------------------------------------------------------------

def update_tracking_verification(tracking_path: str,
                                 passed: bool,
                                 report: str) -> None:
    """Write verification result to a story tracking file's YAML frontmatter."""
    p = Path(tracking_path)
    if not p.is_file():
        return
    text = p.read_text(encoding="utf-8")
    # Find the closing --- of YAML frontmatter
    parts = text.split("---", 2)
    if len(parts) < 3:
        return
    yaml_section = parts[1]
    # Add or update verification.agent_stop
    status = "passed" if passed else "failed"
    verification_line = f"verification_agent_stop: {status}"
    if "verification_agent_stop:" in yaml_section:
        yaml_section = re.sub(
            r'verification_agent_stop:.*',
            verification_line,
            yaml_section,
        )
    else:
        yaml_section = yaml_section.rstrip() + f"\n{verification_line}\n"
    p.write_text("---" + yaml_section + "---" + parts[2], encoding="utf-8")


# ---------------------------------------------------------------------------
# Implementer detection
# ---------------------------------------------------------------------------

_IMPLEMENTER_KEYWORDS = re.compile(
    r"commit|pushed|PR\s*#|created\s+branch|implementation",
    re.IGNORECASE,
)

_TRACKING_PATH_PATTERN = re.compile(r"sprint-\d+/stories/\S+\.md")


def _is_implementer_output(output: str, check_commands: list[str]) -> bool:
    """Return True if the agent output looks like an implementer's.

    Heuristic: check_commands must be configured AND the output must
    contain at least one implementation-related keyword.
    """
    if not check_commands:
        return False
    return bool(_IMPLEMENTER_KEYWORDS.search(output))


# ---------------------------------------------------------------------------
# Hook entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Read event data from stdin, run verification, output results."""
    # Read stdin JSON event data (SubagentStop format)
    try:
        event = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        event = {}

    output_text = event.get("output", "")

    check_commands, smoke_command = load_check_commands()

    # H-014: Skip verification for non-implementer agents
    if not _is_implementer_output(output_text, check_commands):
        print("VERIFICATION SKIPPED: non-implementer agent")
        sys.exit(0)

    report, passed = run_verification(check_commands, smoke_command)
    print(report)

    # H-006: Update tracking file if a story path is found in the output
    m = _TRACKING_PATH_PATTERN.search(output_text)
    if m:
        update_tracking_verification(m.group(0), passed, report)

    # Exit 0 regardless — we inject information, not block.
    # The orchestrator decides whether to accept the agent's output.
    sys.exit(0)


if __name__ == "__main__":
    main()
