#!/usr/bin/env python3
"""Compare planned test cases against actual test files by language.

Parses test plan files for TC-*/GP-* test case IDs, scans the project
tree for actual test functions using language-specific patterns, and
reports what's implemented, what's missing, and what's unplanned.

Run: python scripts/test_coverage.py   (requires sprint-config/)
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))
from validate_config import load_config, ConfigError

# Language-specific test function patterns
# §test_coverage._TEST_PATTERNS
_TEST_PATTERNS: dict[str, re.Pattern] = {
    "rust": re.compile(r'#\[(?:test|tokio::test|async_std::test)\][\s\S]*?(?:async\s+)?fn\s+(\w+)'),
    "python": re.compile(r'def\s+(test_\w+)'),
    "javascript": re.compile(r'(?:it|test)\s*\(\s*[\'"]([^\'"]+)'),
    "go": re.compile(r'func\s+(Test\w+)'),
}

# Language-specific test file glob patterns
# §test_coverage._TEST_FILE_PATTERNS
_TEST_FILE_PATTERNS: dict[str, list[str]] = {
    "rust": ["**/tests/**/*.rs", "**/src/**/*.rs"],
    "python": ["**/test_*.py", "**/*_test.py"],
    "javascript": ["**/*.test.*", "**/*.spec.*"],
    "go": ["**/*_test.go"],
}

# Test case heading in plan files
_PLAN_TC_HEADING = re.compile(r'^###\s+((?:TC|GP)-[\w-]+):\s*(.+)')


# §test_coverage.parse_planned_tests
def parse_planned_tests(test_plan_dir: str) -> dict[str, str]:
    """Extract test case IDs and titles from test plan files.

    Returns {tc_id: title}.
    """
    planned: dict[str, str] = {}
    plan_path = Path(test_plan_dir)
    if not plan_path.is_dir():
        return planned

    for md_file in sorted(plan_path.glob("*.md")):
        for line in md_file.read_text(encoding="utf-8").split('\n'):
            m = _PLAN_TC_HEADING.match(line)
            if m:
                planned[m.group(1)] = m.group(2).strip()
    return planned


# §test_coverage.detect_test_functions
def detect_test_functions(language: str, source: str) -> list[str]:
    """Find test function names in source code for a given language."""
    pattern = _TEST_PATTERNS.get(language.lower())
    if not pattern:
        return []
    return pattern.findall(source)


# §test_coverage.scan_project_tests
def scan_project_tests(project_root: str, language: str) -> list[str]:
    """Walk the project tree, find all test files and extract function names."""
    root = Path(project_root)
    if not root.is_dir():
        return []

    file_patterns = _TEST_FILE_PATTERNS.get(language.lower(), [])
    all_functions: list[str] = []

    for pattern in file_patterns:
        for test_file in root.glob(pattern):
            # Skip sprint-config, node_modules, target, etc.
            # Use relative_to(root) to avoid matching absolute path
            # components (e.g., /Users/jonr/target/myproject).
            try:
                parts = test_file.relative_to(root).parts
            except ValueError:
                parts = test_file.parts
            if any(skip in parts for skip in (
                "node_modules", "target", ".git", "sprint-config",
                "__pycache__", "vendor",
            )):
                continue
            source = test_file.read_text(encoding="utf-8", errors="replace")
            all_functions.extend(detect_test_functions(language, source))

    return sorted(set(all_functions))


# §test_coverage.check_test_coverage
def check_test_coverage(
    test_plan_dir: str,
    project_root: str,
    language: str,
) -> dict:
    """Compare planned test cases vs actual test implementations.

    Returns:
        planned: [tc_id, ...]
        implemented: [func_name, ...]
        missing: [tc_id, ...]  (planned but no matching function found)
    """
    planned = parse_planned_tests(test_plan_dir)
    implemented = scan_project_tests(project_root, language)

    # Fuzzy match: a planned test case is "covered" if any implemented
    # test function name contains the test case ID (normalized to
    # lowercase with hyphens converted to underscores) as a substring.
    impl_lower = [f.lower() for f in implemented]
    matched: set[str] = set()
    for tc_id in planned:
        # TC-PAR-001 → tc_par_001; GP-GOLDEN-01 → gp_golden_01
        normalized = tc_id.lower().replace("-", "_")
        # Also try just the slug portion (e.g., "par_001" from "tc_par_001")
        parts = normalized.split("_", 1)
        slug = parts[1] if len(parts) > 1 else normalized
        # Use word-boundary matching to avoid false positives with short slugs.
        # Only use slug matching if the slug is long enough to be meaningful
        # (at least 4 chars), otherwise short slugs like "e_1" match unrelated
        # functions like "test_type_e_1_setup".
        norm_re = re.compile(r"(?:^|_)" + re.escape(normalized) + r"(?:$|_)")
        slug_re = (
            re.compile(r"(?:^|_)" + re.escape(slug) + r"(?:$|_)")
            if len(slug) >= 4
            else None
        )
        for impl_name in impl_lower:
            if norm_re.search(impl_name):
                matched.add(tc_id)
                break
            if slug_re and slug_re.search(impl_name):
                matched.add(tc_id)
                break
    missing = sorted(set(planned.keys()) - matched)

    return {
        "planned": sorted(planned.keys()),
        "implemented": implemented,
        "missing": missing,
        "matched": sorted(matched),
        "planned_details": planned,
    }


# §test_coverage.format_report
def format_report(coverage: dict) -> str:
    """Produce a markdown coverage report."""
    lines = ["# Test Coverage Report", ""]
    lines.append(
        f"**Planned:** {len(coverage['planned'])}  "
        f"**Implemented:** {len(coverage['implemented'])}  "
        f"**Missing:** {len(coverage['missing'])}"
    )
    lines.append("")

    if coverage["implemented"]:
        lines.append("## Implemented Test Functions")
        lines.append("")
        for func in coverage["implemented"]:
            lines.append(f"- `{func}`")
        lines.append("")

    if coverage["missing"]:
        lines.append("## Planned Tests (Not Yet Matched)")
        lines.append("")
        for tc_id in coverage["missing"]:
            title = coverage["planned_details"].get(tc_id, "")
            lines.append(f"- **{tc_id}**: {title}")
        lines.append("")

    return "\n".join(lines)


# §test_coverage.main
def main() -> None:
    """CLI entry point: check test coverage and print report."""
    try:
        config = load_config()
    except ConfigError:
        sys.exit(1)
    test_plan_dir = config.get("paths", {}).get("test_plan_dir")
    language = config.get("project", {}).get("language", "python").lower()

    if not test_plan_dir:
        print("No test_plan_dir configured in project.toml")
        sys.exit(1)

    # Project root is the directory containing sprint-config/
    project_root = str(Path("sprint-config").resolve().parent)

    report = check_test_coverage(
        test_plan_dir=test_plan_dir,
        project_root=project_root,
        language=language,
    )
    print(format_report(report))


if __name__ == "__main__":
    main()
