#!/usr/bin/env python3
"""Bidirectional story / PRD / test case traceability with gap detection.

Scans epic files for US-XXXX stories and their Test Cases metadata,
PRD reference files for REQ-* requirement IDs, and test plan files
for TC-*/GP-* test case headings.  Builds a bidirectional map and
reports gaps: stories without tests, requirements without stories.

Run: python scripts/traceability.py   (requires sprint-config/)
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))
from validate_config import load_config, ConfigError, TABLE_ROW

# Patterns
# §traceability.STORY_HEADING
STORY_HEADING = re.compile(r'^###\s+(US-\d+):\s*(.+)')
# BH18-012: TABLE_ROW imported from validate_config
# §traceability.TEST_CASE_HEADING
TEST_CASE_HEADING = re.compile(r'^###\s+((?:TC|GP)-[\w-]+):\s*(.+)')
# §traceability.REQ_TABLE_ROW
REQ_TABLE_ROW = re.compile(r'^\|\s*(REQ-[\w-]+)\s*\|\s*(US-[\w, –-]+)\s*\|')
REQ_PATTERN = re.compile(r'US-\d+')


# §traceability.parse_stories
def parse_stories(epics_dir: str) -> dict[str, dict]:
    """Extract story IDs, titles, and test case links from epic files.

    Returns {story_id: {title, test_cases: [str], file}}.
    """
    stories: dict[str, dict] = {}
    epics_path = Path(epics_dir)
    if not epics_path.is_dir():
        return stories

    for md_file in sorted(epics_path.glob("*.md")):
        lines = md_file.read_text(encoding="utf-8").splitlines()
        i = 0
        while i < len(lines):
            m = STORY_HEADING.match(lines[i])
            if m:
                story_id = m.group(1)
                title = m.group(2).strip()
                test_cases: list[str] = []
                # Scan the metadata table following the heading
                j = i + 1
                while j < len(lines):
                    row = TABLE_ROW.match(lines[j])
                    if row:
                        field = row.group(1).strip()
                        value = row.group(2).strip()
                        if field == "Test Cases" and value not in ("—", "-", ""):
                            test_cases = [
                                tc.strip()
                                for tc in value.split(",")
                                if tc.strip()
                            ]
                    elif lines[j].strip() == "" and j > i + 2:
                        # Blank line after table ends the metadata block
                        break
                    elif lines[j].startswith("###"):
                        break
                    j += 1
                stories[story_id] = {
                    "title": title,
                    "test_cases": test_cases,
                    "file": md_file.name,
                }
            i += 1
    return stories


# §traceability.parse_test_cases
def parse_test_cases(test_plan_dir: str) -> dict[str, dict]:
    """Extract test case IDs from test plan files.

    Returns {tc_id: {title, file}}.
    """
    cases: dict[str, dict] = {}
    plan_path = Path(test_plan_dir)
    if not plan_path.is_dir():
        return cases

    for md_file in sorted(plan_path.glob("*.md")):
        for line in md_file.read_text(encoding="utf-8").splitlines():
            m = TEST_CASE_HEADING.match(line)
            if m:
                cases[m.group(1)] = {
                    "title": m.group(2).strip(),
                    "file": md_file.name,
                }
    return cases


# §traceability.parse_requirements
def parse_requirements(prd_dir: str) -> dict[str, dict]:
    """Extract REQ-* IDs and their story mappings from PRD reference files.

    Scans for markdown tables with | REQ-* | US-* | format.
    Returns {req_id: {stories: [str], file}}.
    """
    reqs: dict[str, dict] = {}
    prd_path = Path(prd_dir)
    if not prd_path.is_dir():
        return reqs

    for md_file in sorted(prd_path.rglob("*.md")):
        for line in md_file.read_text(encoding="utf-8").splitlines():
            m = REQ_TABLE_ROW.match(line)
            if m:
                req_id = m.group(1).strip()
                story_text = m.group(2).strip()
                story_ids = REQ_PATTERN.findall(story_text)
                reqs[req_id] = {
                    "stories": story_ids,
                    "file": str(md_file.relative_to(prd_path)),
                }
    return reqs


# §traceability.build_traceability
def build_traceability(
    epics_dir: str | None = None,
    test_plan_dir: str | None = None,
    prd_dir: str | None = None,
) -> dict:
    """Build bidirectional traceability map and find gaps.

    Returns:
        stories_without_tests: [story_id, ...]
        requirements_without_stories: [req_id, ...]
        story_count: int
        test_case_count: int
        requirement_count: int
    """
    stories = parse_stories(epics_dir) if epics_dir else {}
    test_cases = parse_test_cases(test_plan_dir) if test_plan_dir else {}
    requirements = parse_requirements(prd_dir) if prd_dir else {}

    # Stories with no test cases linked
    stories_without_tests = sorted(
        sid for sid, data in stories.items()
        if not data["test_cases"]
    )

    # Requirements that don't map to any story in the epic set
    all_story_ids = set(stories.keys())
    requirements_without_stories = sorted(
        rid for rid, data in requirements.items()
        if not any(s in all_story_ids for s in data["stories"])
    )

    return {
        "stories_without_tests": stories_without_tests,
        "requirements_without_stories": requirements_without_stories,
        "story_count": len(stories),
        "test_case_count": len(test_cases),
        "requirement_count": len(requirements),
        "stories": stories,
        "test_cases": test_cases,
        "requirements": requirements,
    }


# §traceability.format_report
def format_report(report: dict) -> str:
    """Produce a markdown traceability report."""
    lines = ["# Traceability Report", ""]
    lines.append(
        f"**Stories:** {report['story_count']}  "
        f"**Test Cases:** {report['test_case_count']}  "
        f"**Requirements:** {report['requirement_count']}"
    )
    lines.append("")

    if report["stories_without_tests"]:
        lines.append("## Stories Without Test Coverage")
        lines.append("")
        for sid in report["stories_without_tests"]:
            s = report["stories"][sid]
            lines.append(f"- **{sid}**: {s['title']} ({s['file']})")
        lines.append("")

    if report["requirements_without_stories"]:
        lines.append("## Requirements Without Story Links")
        lines.append("")
        for rid in report["requirements_without_stories"]:
            r = report["requirements"][rid]
            lines.append(f"- **{rid}** ({r['file']})")
        lines.append("")

    if not report["stories_without_tests"] and not report["requirements_without_stories"]:
        lines.append("All stories have test coverage. All requirements map to stories.")
        lines.append("")

    return "\n".join(lines)


# §traceability.main
def main() -> None:
    """CLI entry point: build and print traceability report."""
    try:
        config = load_config()
    except ConfigError:
        sys.exit(1)
    report = build_traceability(
        epics_dir=config.get("paths", {}).get("epics_dir"),
        test_plan_dir=config.get("paths", {}).get("test_plan_dir"),
        prd_dir=config.get("paths", {}).get("prd_dir"),
    )
    print(format_report(report))


if __name__ == "__main__":
    main()
