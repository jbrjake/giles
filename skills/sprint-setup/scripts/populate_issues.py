#!/usr/bin/env python3
"""Parse milestone docs and create GitHub issues for sprint stories.

Config-driven: reads milestone file paths and repo info from project.toml
via validate_config.load_config(). No hardcoded paths or project names.
"""

import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

# -- Import shared config ----------------------------------------------------
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent / "scripts"))
from validate_config import load_config, get_milestones


@dataclass
class Story:
    story_id: str
    title: str
    saga: str
    sp: int
    priority: str
    sprint: int
    user_story: str = ""
    acceptance_criteria: list[str] = field(default_factory=list)
    epic: str = ""
    blocked_by: str = ""
    blocks: str = ""
    test_cases: str = ""
    source_file: str = ""


def run_gh(args: list[str], check: bool = True) -> subprocess.CompletedProcess:
    """Run a gh CLI command."""
    result = subprocess.run(["gh", *args], capture_output=True, text=True)
    if check and result.returncode != 0:
        print(f"Error: gh {' '.join(args)}\n{result.stderr}")
        sys.exit(1)
    return result


def check_prerequisites() -> None:
    """Verify gh CLI auth."""
    r = subprocess.run(["gh", "auth", "status"], capture_output=True, text=True)
    if r.returncode != 0:
        print("Error: gh CLI not authenticated. Run 'gh auth login' first.")
        sys.exit(1)
    print("Prerequisites OK.")


# -- Story ID pattern --------------------------------------------------------

# Default pattern for story tables: | US-XXXX | title | saga | sp | priority |
_DEFAULT_ROW_RE = re.compile(
    r"\|\s*(US-\d{4})\s*\|\s*(.+?)\s*\|\s*(S\d{2})\s*\|\s*(\d+)\s*\|\s*(P\d)\s*\|"
)

# Sprint section header pattern
_SPRINT_HEADER_RE = re.compile(
    r"### Sprint (\d+):.*?\n(.*?)(?=\n### |\n## |\Z)", re.DOTALL
)


def _build_row_regex(config: dict) -> re.Pattern:
    """Build a row regex from config, or use the default.

    Config can specify [backlog] story_id_pattern for the ID column
    (e.g. "PROJ-\\d{4}").
    """
    backlog = config.get("backlog", {})
    pattern = backlog.get("story_id_pattern", "")
    if pattern:
        # Build regex: | <story_id> | <title> | <saga> | <sp> | <priority> |
        return re.compile(
            rf"\|\s*({pattern})\s*\|\s*(.+?)\s*\|\s*(S\d{{2}})\s*\|\s*(\d+)\s*\|\s*(P\d)\s*\|"
        )
    return _DEFAULT_ROW_RE


def parse_milestone_stories(
    milestone_files: list[str], config: dict
) -> list[Story]:
    """Parse sprint tables from milestone files to extract stories."""
    row_re = _build_row_regex(config)
    stories: list[Story] = []

    for mf_path in milestone_files:
        mf = Path(mf_path)
        if not mf.is_file():
            print(f"  Warning: Milestone file not found: {mf}")
            continue

        content = mf.read_text(encoding="utf-8")

        # Try structured sprint sections first
        found_sections = False
        for m in _SPRINT_HEADER_RE.finditer(content):
            found_sections = True
            sprint_num = int(m.group(1))
            for row in row_re.finditer(m.group(2)):
                stories.append(Story(
                    story_id=row.group(1), title=row.group(2).strip(),
                    saga=row.group(3), sp=int(row.group(4)),
                    priority=row.group(5), sprint=sprint_num,
                    source_file=str(mf),
                ))

        # If no sprint sections, scan the whole file for story rows
        if not found_sections:
            sprint_num = _infer_sprint_number(mf)
            for row in row_re.finditer(content):
                stories.append(Story(
                    story_id=row.group(1), title=row.group(2).strip(),
                    saga=row.group(3), sp=int(row.group(4)),
                    priority=row.group(5), sprint=sprint_num,
                    source_file=str(mf),
                ))

    return stories


def _infer_sprint_number(mf: Path) -> int:
    """Infer sprint number from filename or content.

    Looks for patterns like 'sprint-1', 'milestone-1', or a heading.
    """
    name = mf.stem.lower()
    m = re.search(r"(\d+)", name)
    if m:
        return int(m.group(1))
    # Try from content heading
    text = mf.read_text(encoding="utf-8")
    m = re.search(r"Sprint\s+(\d+)", text)
    if m:
        return int(m.group(1))
    return 1


def _extract_table_field(section: str, field_name: str) -> str:
    """Extract a value from a markdown metadata table row."""
    m = re.search(rf"\| {field_name}\s*\|\s*(.+?)\s*\|", section)
    if m and m.group(1).strip() not in ("\u2014", ""):
        return m.group(1).strip()
    return ""


def enrich_from_epics(stories: list[Story], config: dict) -> None:
    """Enrich stories with user-story text, ACs, metadata from epic files.

    Looks for epic files in backlog_dir. If [paths] epics_dir is set, uses
    that instead.
    """
    paths = config.get("paths", {})
    backlog_dir = paths.get("backlog_dir", "sprint-config/backlog")
    epics_dir_str = paths.get("epics_dir", "")
    if epics_dir_str:
        epics_dir = Path(epics_dir_str)
    else:
        epics_dir = Path(backlog_dir).parent / "epics"

    if not epics_dir.is_dir():
        return

    story_map: dict[str, Story] = {s.story_id: s for s in stories}
    epic_files = sorted(epics_dir.glob("*.md"))

    for path in epic_files:
        content = path.read_text(encoding="utf-8")
        epic_id_m = re.search(r"\| Epic\s*\|\s*(E-\d{4})\s*\|", content)
        epic_id = epic_id_m.group(1) if epic_id_m else ""

        # Split on story subsections
        for section in re.split(r"(?=^### [A-Z]+-\d+:)", content, flags=re.MULTILINE):
            header = re.match(r"### ([A-Z]+-\d+):\s*(.+)", section)
            if not header or header.group(1) not in story_map:
                continue
            story = story_map[header.group(1)]
            story.epic = epic_id

            # User story
            us = re.search(
                r"\*\*As an?\*\*\s*(.+?)\s*\*\*I want\*\*\s*(.+?)"
                r"\s*\*\*so that\*\*\s*(.+?)(?:\n\n|\n\*\*)",
                section, re.DOTALL,
            )
            if us:
                story.user_story = (
                    f"As a {us.group(1).strip().rstrip(',')}, "
                    f"I want {us.group(2).strip()} "
                    f"so that {us.group(3).strip().rstrip('.')}."
                )
            # Acceptance criteria
            story.acceptance_criteria = re.findall(
                r"-\s*\[[ x]\]\s*`?AC-\d+`?:\s*(.+)", section
            )
            story.blocked_by = _extract_table_field(section, "Blocked By")
            story.blocks = _extract_table_field(section, "Blocks")
            story.test_cases = _extract_table_field(section, "Test Cases")


def get_existing_issues() -> set[str]:
    """Fetch existing issue title prefixes (story IDs) for idempotency."""
    result = run_gh(
        ["issue", "list", "--limit", "200", "--json", "title", "--state", "all"],
        check=False,
    )
    if result.returncode != 0:
        return set()
    try:
        issues = json.loads(result.stdout)
    except json.JSONDecodeError:
        return set()
    existing: set[str] = set()
    for issue in issues:
        m = re.match(r"([A-Z]+-\d+):", issue.get("title", ""))
        if m:
            existing.add(m.group(1))
    return existing


def get_milestone_numbers() -> dict[str, int]:
    """Fetch milestone title -> number mapping from GitHub."""
    result = run_gh(
        ["api", "repos/{owner}/{repo}/milestones", "--jq", "."], check=False
    )
    if result.returncode != 0:
        return {}
    try:
        return {m["title"]: m["number"] for m in json.loads(result.stdout)}
    except (json.JSONDecodeError, KeyError):
        return {}


def _build_milestone_title_map(
    milestone_files: list[str],
) -> dict[int, str]:
    """Map sprint number -> milestone title by reading milestone file headings."""
    result: dict[int, str] = {}
    for i, mf_path in enumerate(milestone_files, 1):
        mf = Path(mf_path)
        if not mf.is_file():
            result[i] = f"Sprint {i}"
            continue
        text = mf.read_text(encoding="utf-8")
        heading = re.search(r"^#\s+(.+)", text, re.MULTILINE)
        if heading:
            result[i] = heading.group(1).strip()
        else:
            result[i] = f"Sprint {i}"
    return result


def format_issue_body(story: Story) -> str:
    """Format the GitHub issue body from story details."""
    lines: list[str] = []
    if story.user_story:
        lines += [f"> {story.user_story}", ""]
    lines += ["| Field | Value |", "|-------|-------|",
              f"| Story Points | {story.sp} |",
              f"| Priority | {story.priority} |",
              f"| Saga | {story.saga} |"]
    if story.epic:
        lines.append(f"| Epic | {story.epic} |")
    lines.append(f"| Sprint | {story.sprint} |")
    for label, val in [("Blocked By", story.blocked_by),
                       ("Blocks", story.blocks),
                       ("Test Cases", story.test_cases)]:
        if val:
            lines.append(f"| {label} | {val} |")
    lines.append("")
    if story.acceptance_criteria:
        lines += ["## Acceptance Criteria", ""]
        for i, ac in enumerate(story.acceptance_criteria, 1):
            lines.append(f"- [ ] **AC-{i:02d}:** {ac}")
        lines.append("")
    if story.source_file:
        lines += ["---", "",
                  f"Source: `{Path(story.source_file).name}`"
                  f" | Sprint {story.sprint}"]
    return "\n".join(lines)


def create_issue(
    story: Story,
    milestone_numbers: dict[str, int],
    milestone_titles: dict[int, str],
) -> bool:
    """Create a single GitHub issue for a story. Return True if created."""
    title = f"{story.story_id}: {story.title}"
    labels = [f"saga:{story.saga}", f"sprint:{story.sprint}",
              f"priority:{story.priority}", "type:story", "kanban:todo"]
    args = ["issue", "create", "--title", title,
            "--body", format_issue_body(story)]
    for label in labels:
        args.extend(["--label", label])
    ms_title = milestone_titles.get(story.sprint, "")
    if ms_title in milestone_numbers:
        args.extend(["--milestone", ms_title])
    result = run_gh(args, check=False)
    if result.returncode == 0:
        print(f"  + {story.story_id}: {story.title}  ->  {result.stdout.strip()}")
        return True
    print(f"  ! {story.story_id}: {result.stderr.strip()}")
    return False


def main() -> None:
    """Parse milestones and create GitHub issues."""
    config = load_config()
    project_name = config.get("project", {}).get("name", "Project")
    print(f"=== {project_name} Issue Population ===\n")
    check_prerequisites()

    milestone_files = get_milestones(config)
    if not milestone_files:
        print("Error: No milestone files found in config.")
        sys.exit(1)

    print(f"\nParsing {len(milestone_files)} milestone file(s)...")
    stories = parse_milestone_stories(milestone_files, config)
    print(f"  Found {len(stories)} stories across sprints.")
    if not stories:
        print("Error: No stories found in milestone files.")
        sys.exit(1)

    print("\nEnriching from epic files...")
    enrich_from_epics(stories, config)
    enriched = sum(1 for s in stories if s.user_story)
    print(f"  Enriched {enriched}/{len(stories)} stories with epic details.")

    print("\nChecking for existing issues...")
    existing = get_existing_issues()
    if existing:
        print(f"  Found {len(existing)} existing story issues.")
    milestone_numbers = get_milestone_numbers()
    milestone_titles = _build_milestone_title_map(milestone_files)

    print("\n=== Creating Issues ===\n")
    created = skipped = 0
    for story in stories:
        if story.story_id in existing:
            print(f"  = {story.story_id}: {story.title} (already exists)")
            skipped += 1
            continue
        if create_issue(story, milestone_numbers, milestone_titles):
            created += 1
    print(f"\n=== Done: {created} created, {skipped} skipped ===")
    if created > 0:
        print("Next: run setup_ci.py to generate the CI workflow.")


if __name__ == "__main__":
    main()
