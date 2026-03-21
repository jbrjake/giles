#!/usr/bin/env python3
"""Test category analyzer — categorize tests as unit/component/integration/smoke.

Scans test directories and classifies tests by heuristic: directory
structure, naming patterns, and configurable overrides.  Reports
distribution and flags when integration test count is zero.

Exit codes:
    0 — healthy distribution
    1 — zero integration tests detected
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from validate_config import load_config, ConfigError


# ---------------------------------------------------------------------------
# Category detection
# ---------------------------------------------------------------------------

# Directory patterns that indicate test category
_DIR_PATTERNS: dict[str, list[str]] = {
    "integration": ["integration", "e2e", "end_to_end", "end-to-end", "acceptance"],
    "smoke": ["smoke", "sanity"],
    "component": ["component", "functional"],
}

# Test name patterns
_NAME_PATTERNS: dict[str, re.Pattern] = {
    "integration": re.compile(r'test_(?:integration|e2e|end_to_end)', re.IGNORECASE),
    "smoke": re.compile(r'test_(?:smoke|sanity)', re.IGNORECASE),
}


# §test_categories.classify_test_file
def classify_test_file(path: Path,
                       integration_dirs: list[str] | None = None,
                       smoke_dirs: list[str] | None = None) -> str:
    """Classify a test file as unit/component/integration/smoke."""
    parts = [p.lower() for p in path.parts]

    # Check configurable override directories first
    if integration_dirs:
        for d in integration_dirs:
            if d.lower() in parts:
                return "integration"
    if smoke_dirs:
        for d in smoke_dirs:
            if d.lower() in parts:
                return "smoke"

    # Check built-in directory patterns
    for category, dir_names in _DIR_PATTERNS.items():
        for dirname in dir_names:
            if dirname in parts:
                return category

    # Check test filename patterns
    stem = path.stem.lower()
    for category, pattern in _NAME_PATTERNS.items():
        if pattern.search(stem):
            return category

    # Default: unit test
    return "unit"


def count_test_functions(path: Path) -> int:
    """Count test functions/methods in a file."""
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return 0

    count = 0
    for line in content.splitlines():
        stripped = line.strip()
        # Python: def test_ or async def test_
        if re.match(r'(async\s+)?def\s+test_', stripped):
            count += 1
        # Rust: #[test] fn or #[tokio::test]
        elif stripped == "#[test]" or stripped.startswith("#[tokio::test"):
            count += 1
        # JS/TS: it(, test(, describe(
        elif re.match(r"(it|test)\s*\(", stripped):
            count += 1
        # Go: func Test
        elif re.match(r'func\s+Test', stripped):
            count += 1
    return count


def find_test_files(root: Path) -> list[Path]:
    """Find all test files in the project."""
    test_files: list[Path] = []
    # Common test file patterns
    patterns = [
        "test_*.py", "*_test.py", "test_*.rs", "*_test.rs",
        "*.test.ts", "*.test.tsx", "*.test.js", "*.test.jsx",
        "*.spec.ts", "*.spec.tsx", "*.spec.js", "*.spec.jsx",
        "*_test.go",
    ]

    for dirpath, dirnames, filenames in os.walk(root):
        # Skip hidden dirs, node_modules, target, etc.
        dirnames[:] = [
            d for d in dirnames
            if not d.startswith(".") and d not in (
                "node_modules", "target", "build", "dist",
                "__pycache__", ".git", "venv", ".venv",
            )
        ]
        for fname in filenames:
            fpath = Path(dirpath) / fname
            for pat in patterns:
                if fpath.match(pat):
                    test_files.append(fpath)
                    break
    return test_files


# §test_categories.analyze
def analyze(root: Path,
            integration_dirs: list[str] | None = None,
            smoke_dirs: list[str] | None = None,
            ) -> dict[str, int]:
    """Analyze test distribution. Returns {category: count}."""
    test_files = find_test_files(root)
    counts: dict[str, int] = {
        "unit": 0, "component": 0, "integration": 0, "smoke": 0,
    }

    for tf in test_files:
        category = classify_test_file(tf, integration_dirs, smoke_dirs)
        n = count_test_functions(tf)
        counts[category] = counts.get(category, 0) + n

    return counts


# §test_categories.format_report
def format_report(counts: dict[str, int]) -> str:
    """Format the test distribution report."""
    total = sum(counts.values())
    if total == 0:
        return "No tests found"

    lines: list[str] = []
    for category in ("unit", "component", "integration", "smoke"):
        n = counts.get(category, 0)
        pct = round(100 * n / total) if total > 0 else 0
        lines.append(f"{category}: {n} ({pct}%)")

    if counts.get("integration", 0) == 0:
        lines.append("WARNING: 0 integration tests detected")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

# §test_categories.main
def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze test categories")
    parser.add_argument("--root", default=".", help="Project root directory")
    parser.add_argument("--config", default=None, help="Path to project.toml")
    args = parser.parse_args()

    integration_dirs: list[str] | None = None
    smoke_dirs: list[str] | None = None

    if args.config:
        try:
            config_dir = str(Path(args.config).parent)
            config = load_config(config_dir)
            testing = config.get("testing", {})
            integration_dirs = testing.get("integration_dirs")
            smoke_dirs = testing.get("smoke_dirs")
        except ConfigError:
            pass

    root = Path(args.root).resolve()
    counts = analyze(root, integration_dirs, smoke_dirs)
    report = format_report(counts)
    print(report)

    if counts.get("integration", 0) == 0:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
