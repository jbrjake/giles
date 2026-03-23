#!/usr/bin/env python3
"""SubagentStop verification hook -- runs check_commands after agent completion.

When an implementer or fix agent completes, this hook runs the project's
``[ci] check_commands`` and compares results against the agent's claims.
If any command fails, it injects failure output.  If all pass, it
confirms verification.

Optionally runs ``smoke_command`` if configured.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import _find_project_root, exit_ok, exit_warn, read_event


# ---------------------------------------------------------------------------
# Config reading (lightweight, no import dependency on validate_config)
# ---------------------------------------------------------------------------


def _unescape_basic_string(s: str) -> str:
    """Unescape TOML basic string escape sequences (BH29-001).

    Per TOML spec, double-quoted strings process escape sequences:
    \\\" -> \", \\\\ -> \\, \\n -> newline, \\t -> tab, \\r -> CR.
    Unknown escapes are preserved as-is for safety.
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
            else:
                result.append(s[i])
                result.append(nxt)
            i += 2
        else:
            result.append(s[i])
            i += 1
    return "".join(result)


def _strip_inline_comment(val: str) -> str:
    """Strip an inline TOML comment, respecting quoted strings.

    Handles backslash-escaped quotes inside double-quoted TOML strings.
    Single-quoted strings are TOML literal strings (no escape processing).
    """
    in_quote = False
    quote_char = ""
    i = 0
    while i < len(val):
        ch = val[i]
        if ch == "\\" and in_quote and quote_char == '"':
            i += 2  # skip escaped char in double-quoted strings
            continue
        if ch in ('"', "'") and not in_quote:
            in_quote = True
            quote_char = ch
        elif ch == quote_char and in_quote:
            in_quote = False
        elif ch == "#" and not in_quote:
            return val[:i].rstrip()
        i += 1
    return val


def _has_unquoted_bracket(s: str) -> bool:
    """Check if s contains a ] that is not inside quotes.

    Handles backslash-escaped quotes inside double-quoted TOML strings.
    Single-quoted strings are TOML literal strings (no escape processing).
    """
    in_quote = False
    quote_char = ""
    i = 0
    while i < len(s):
        ch = s[i]
        if ch == "\\" and in_quote and quote_char == '"':
            i += 2  # skip escaped char in double-quoted strings
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


def _read_toml_key(text: str, section: str, key: str) -> str | list[str] | None:
    """Extract a key from a TOML section.  Minimal parser for hook use."""
    in_section = False
    # BH35-009: Use split('\n') instead of splitlines() per BH20-001
    lines = text.split('\n')
    i = 0
    while i < len(lines):
        stripped = lines[i].strip()
        if stripped.startswith("["):
            # BH35-005: Strip trailing comments before comparing
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
                # Collect multi-line array: accumulate until unquoted ]
                array_text = val
                while not _has_unquoted_bracket(array_text) and i + 1 < len(lines):
                    i += 1
                    # BH35-017: Strip inline comments from continuation lines
                    # to prevent quoted strings in comments becoming phantom items
                    array_text += " " + _strip_inline_comment(lines[i].strip())
                # Match quoted strings; double-quoted handles \" escapes,
                # single-quoted is literal (TOML spec).
                items = re.findall(r'"((?:[^"\\]|\\.)*)"|\'([^\']*)\'', array_text)
                # BH29-001: unescape double-quoted items; single-quoted are literal
                return [_unescape_basic_string(a) if a else b for a, b in items]
            if val.startswith('"') and val.endswith('"'):
                # BH29-001: unescape TOML basic string escape sequences
                return _unescape_basic_string(val[1:-1])
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
        # BH27-003: Bridge to commit_gate -- record that working tree is verified
        # so the commit gate doesn't block commits after agent verification.
        try:
            from commit_gate import mark_verified
            mark_verified()
        except ImportError:
            pass  # commit_gate not available -- skip bridging
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

def _resolve_tracking_path(relative: str) -> str | None:
    """Resolve a sprint-N/stories/X.md path to an absolute file path.

    Searches for the file under ``{project_root}/{sprints_dir}/{relative}``
    using ``paths.sprints_dir`` from project.toml, then falls back to
    ``{project_root}/{relative}``.  Returns None if not found.
    """
    root = _find_project_root()
    toml_path = root / "sprint-config" / "project.toml"
    if toml_path.is_file():
        text = toml_path.read_text(encoding="utf-8")
        sprints_dir = _read_toml_key(text, "paths", "sprints_dir")
        if isinstance(sprints_dir, str):
            candidate = root / sprints_dir / relative
            if candidate.is_file():
                return str(candidate)
    # Fallback: directly under project root
    candidate = root / relative
    if candidate.is_file():
        return str(candidate)
    return None


_IMPLEMENTER_ACTION_PATTERNS = re.compile(
    r"""
    \bcommitted\b                # BH35-018: word boundary to avoid "uncommitted"
    | \bpushed\b                 # pushed to remote
    | \bmerged\b                 # merged a branch/PR
    | created\s+(?:PR|branch)    # created a PR or branch
    | PR\s*\#\d+                 # references a specific PR number
    | created\s+branch           # created branch
    | tests?\s+pass              # reports test results
    | all\s+checks?\s+pass       # reports check results
    """,
    re.IGNORECASE | re.VERBOSE,
)

_TRACKING_PATH_PATTERN = re.compile(r"sprint-\d+/stories/\S+\.md")


def _is_implementer_output(output: str, check_commands: list[str]) -> bool:
    """Return True if the agent output looks like an implementer's.

    Heuristic: check_commands must be configured AND the output must
    contain at least one action-oriented keyword (committed, pushed,
    merged, created PR/branch, tests pass). Mention-only keywords
    (\"the commit\", \"the implementation\") are excluded to avoid
    false positives from reviewer agents.
    """
    if not check_commands:
        return False
    return bool(_IMPLEMENTER_ACTION_PATTERNS.search(output))


# ---------------------------------------------------------------------------
# Hook entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Read event data from stdin, run verification, output results."""
    event = read_event()

    output_text = event.get("output", "")

    check_commands, smoke_command = load_check_commands()

    # H-014: Skip verification for non-implementer agents
    if not _is_implementer_output(output_text, check_commands):
        exit_ok()

    report, passed = run_verification(check_commands, smoke_command)

    # H-006: Update tracking file if a story path is found in the output
    m = _TRACKING_PATH_PATTERN.search(output_text)
    if m:
        resolved = _resolve_tracking_path(m.group(0))
        if resolved:
            update_tracking_verification(resolved, passed, report)

    # Inject verification report as context -- don't block.
    exit_warn(report)


if __name__ == "__main__":
    main()
