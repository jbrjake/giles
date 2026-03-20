#!/usr/bin/env python3
"""Smoke test runner — runs the configured smoke_command and reports results.

Reads ``[ci] smoke_command`` from project.toml.  Runs the command with a
configurable timeout, captures output, and writes results to smoke history.

Exit codes:
    0 — SMOKE PASS
    1 — SMOKE FAIL
    2 — SMOKE SKIP (not configured)
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from validate_config import load_config, ConfigError, get_sprints_dir


# ---------------------------------------------------------------------------
# Smoke test execution
# ---------------------------------------------------------------------------

def run_smoke(command: str, timeout: int = 30) -> tuple[str, int, str, str]:
    """Run the smoke command and return (status, exit_code, stdout, stderr).

    Status is one of: 'SMOKE PASS', 'SMOKE FAIL', 'SMOKE SKIP'.
    """
    if not command:
        return "SMOKE SKIP", 2, "", "no smoke_command in project.toml"

    try:
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True,
            timeout=timeout,
        )
        if result.returncode == 0:
            return "SMOKE PASS", 0, result.stdout, result.stderr
        else:
            return "SMOKE FAIL", 1, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return "SMOKE FAIL", 1, "", f"timed out after {timeout}s"
    except Exception as exc:
        return "SMOKE FAIL", 1, "", str(exc)


# ---------------------------------------------------------------------------
# History tracking
# ---------------------------------------------------------------------------

def write_history(sprints_dir: str, status: str, command: str,
                  stdout: str = "", stderr: str = "") -> None:
    """Append a smoke result to smoke-history.md."""
    history_path = Path(sprints_dir) / "smoke-history.md"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

    # Get current git commit hash
    commit = "unknown"
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            commit = result.stdout.strip()
    except Exception:
        pass

    # Create file with header if it doesn't exist
    if not history_path.is_file():
        history_path.parent.mkdir(parents=True, exist_ok=True)
        history_path.write_text(
            "# Smoke Test History\n\n"
            "| Date | Commit | Command | Result |\n"
            "|------|--------|---------|--------|\n",
            encoding="utf-8",
        )

    with open(history_path, "a", encoding="utf-8") as f:
        f.write(f"| {timestamp} | {commit} | `{command}` | {status} |\n")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Run smoke test")
    parser.add_argument("--config", default="sprint-config/project.toml",
                        help="Path to project.toml")
    args = parser.parse_args()

    config_dir = str(Path(args.config).parent)
    try:
        config = load_config(config_dir)
    except ConfigError:
        sys.exit(1)

    ci = config.get("ci", {})
    command = ci.get("smoke_command", "")
    timeout = int(ci.get("smoke_timeout", 30))

    status, exit_code, stdout, stderr = run_smoke(command, timeout)
    print(status)

    if stdout.strip():
        print(stdout.strip())
    if stderr.strip():
        print(stderr.strip(), file=sys.stderr)

    # Write history
    sprints_dir = get_sprints_dir(config)
    if command:
        write_history(sprints_dir, status, command, stdout, stderr)

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
