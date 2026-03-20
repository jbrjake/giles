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


# ---------------------------------------------------------------------------
# Config reading (lightweight, no import dependency on validate_config)
# ---------------------------------------------------------------------------

def _read_toml_key(text: str, section: str, key: str) -> str | list[str] | None:
    """Extract a key from a TOML section.  Minimal parser for hook use."""
    in_section = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("["):
            in_section = stripped == f"[{section}]"
            continue
        if not in_section:
            continue
        m = re.match(rf'{key}\s*=\s*(.*)', stripped)
        if m:
            val = m.group(1).strip()
            if val.startswith("["):
                # Parse simple array of strings
                items = re.findall(r'"([^"]*)"', val)
                return items
            if val.startswith('"') and val.endswith('"'):
                return val[1:-1]
            return val
    return None


def load_check_commands(config_path: str = "sprint-config/project.toml",
                        ) -> tuple[list[str], str | None]:
    """Return (check_commands, smoke_command) from project.toml."""
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
# Hook entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Read event data from stdin, run verification, output results."""
    check_commands, smoke_command = load_check_commands()
    report, passed = run_verification(check_commands, smoke_command)
    print(report)
    # Exit 0 regardless — we inject information, not block.
    # The orchestrator decides whether to accept the agent's output.
    sys.exit(0)


if __name__ == "__main__":
    main()
