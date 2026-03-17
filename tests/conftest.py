"""Shared test configuration — centralizes sys.path setup for all test files.

Instead of every test file doing sys.path.insert(0, ...) independently,
this conftest.py adds all script directories once when pytest starts.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Add all script directories to sys.path (order matters for shadowing)
_SCRIPT_PATHS = [
    ROOT / "tests",
    ROOT / "scripts",
    ROOT / "skills" / "sprint-setup" / "scripts",
    ROOT / "skills" / "sprint-run" / "scripts",
    ROOT / "skills" / "sprint-monitor" / "scripts",
    ROOT / "skills" / "sprint-release" / "scripts",
]

for p in _SCRIPT_PATHS:
    _p_str = str(p)
    if _p_str not in sys.path:
        sys.path.insert(0, _p_str)

# BH21-002: Enforce jq availability — without it, FakeGitHub silently
# degrades jq-dependent tests (returns unfiltered data instead of failing).
try:
    import jq as _jq  # noqa: F401
except ImportError:
    raise ImportError(
        "The 'jq' Python package is required for tests. "
        "Install dev dependencies: pip install -r requirements-dev.txt"
    )
