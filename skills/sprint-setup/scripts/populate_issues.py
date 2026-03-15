#!/usr/bin/env python3
"""Parse milestone docs and create GitHub issues for sprint stories.

Config-driven: reads milestone file paths and repo info from project.toml
via validate_config.load_config(). No hardcoded paths or project names.
"""

import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

# -- Import shared config ----------------------------------------------------
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent / "scripts"))
from validate_config import load_config, ConfigError, get_milestones, gh, gh_json, warn_if_at_limit


@dataclass
# §populate_issues.Story
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


def check_prerequisites() -> None:
    """Verify gh CLI auth."""
    r = subprocess.run(["gh", "auth", "status"], capture_output=True, text=True)
    if r.returncode != 0:
        print("Error: gh CLI not authenticated. Run 'gh auth login' first.")
        sys.exit(1)
    print("Prerequisites OK.")


# -- Story ID pattern --------------------------------------------------------

# Story tables: | US-XXXX | title | [epic] | saga | sp | priority |
# Epic column is optional for backward compat with 5-column format.
_DEFAULT_ROW_RE = re.compile(
    r"\|\s*(US-\d{4})\s*\|\s*(.+?)\s*\|\s*(?:(E-\d{4})\s*\|\s*)?(S\d{2})\s*\|\s*(\d+)\s*\|\s*(P\d)\s*\|"
)

# Sprint section header pattern — only stops at next sprint header or
# higher-level heading, not arbitrary ### headings like ### Notes.
_SPRINT_HEADER_RE = re.compile(
    r"### Sprint (\d+):.*?\n(.*?)(?=\n### Sprint |\n## |\Z)", re.DOTALL
)


# §populate_issues._build_row_regex
def _build_row_regex(config: dict) -> re.Pattern:
    """Build a row regex from config, or use the default.

    Config can specify [backlog] story_id_pattern for the ID column
    (e.g. "PROJ-\\d{4}"). Invalid patterns fall back to the default.
    Patterns with capturing groups are rejected to prevent group-number shifts.
    """
    backlog = config.get("backlog", {})
    pattern = backlog.get("story_id_pattern", "")
    if pattern:
        # Reject patterns with unescaped capturing groups
        if re.search(r'(?<!\\)\((?!\?)', pattern):
            print(f"Warning: story_id_pattern contains capturing groups, "
                  f"using default pattern", file=sys.stderr)
            return _DEFAULT_ROW_RE
        try:
            return re.compile(
                rf"\|\s*({pattern})\s*\|\s*(.+?)\s*\|\s*(?:(E-\d{{4}})\s*\|\s*)?(S\d{{2}})\s*\|\s*(\d+)\s*\|\s*(P\d)\s*\|"
            )
        except re.error as exc:
            print(f"Warning: invalid story_id_pattern '{pattern}': {exc}, "
                  f"using default", file=sys.stderr)
            return _DEFAULT_ROW_RE
    return _DEFAULT_ROW_RE


# §populate_issues.parse_milestone_stories
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
                    epic=row.group(3) or "", saga=row.group(4),
                    sp=int(row.group(5)), priority=row.group(6),
                    sprint=sprint_num, source_file=str(mf),
                ))

        # If no sprint sections, scan the whole file for story rows
        if not found_sections:
            sprint_num = _infer_sprint_number(mf, content)
            for row in row_re.finditer(content):
                stories.append(Story(
                    story_id=row.group(1), title=row.group(2).strip(),
                    epic=row.group(3) or "", saga=row.group(4),
                    sp=int(row.group(5)), priority=row.group(6),
                    sprint=sprint_num, source_file=str(mf),
                ))

    return stories


# §populate_issues._infer_sprint_number
def _infer_sprint_number(mf: Path, content: str | None = None) -> int:
    """Infer sprint number from content headings first, then filename.

    Priority matches bootstrap_github._collect_sprint_numbers: content-first.
    Pass *content* to avoid re-reading the file (caller often has it already).
    """
    # Content-first: look for Sprint N headings (anchored to markdown heading)
    text = content if content is not None else mf.read_text(encoding="utf-8")
    # Prefer heading-anchored match (matches bootstrap_github._collect_sprint_numbers)
    m = re.search(r"^###\s+Sprint\s+(\d+)", text, re.MULTILINE)
    if m:
        return int(m.group(1))
    # Fallback: filename
    name = mf.stem.lower()
    m = re.search(r"(\d+)", name)
    if m:
        return int(m.group(1))
    return 1


# -- Detail block parser (dreamcatcher format) -------------------------------

_DETAIL_BLOCK_RE = re.compile(r"^###\s+(US-\d{4}):\s+(.+)$", re.MULTILINE)
_META_ROW_RE = re.compile(r"^\|\s*(.+?)\s*\|\s*(.+?)\s*\|$", re.MULTILINE)


# §populate_issues.parse_detail_blocks
def parse_detail_blocks(content: str, sprint: int, source_file: str) -> list[Story]:
    """Parse detail-block-format stories from epic/milestone content."""
    stories = []
    # Split on ### US-XXXX headers
    parts = _DETAIL_BLOCK_RE.split(content)
    # parts: [preamble, id1, title1, body1, id2, title2, body2, ...]
    for i in range(1, len(parts), 3):
        if i + 2 > len(parts):
            break
        story_id, title, body = parts[i], parts[i+1].strip(), parts[i+2]

        # Parse metadata table
        meta = {}
        for m in _META_ROW_RE.finditer(body):
            key, val = m.group(1).strip(), m.group(2).strip()
            if key != "Field":  # skip header row
                meta[key.lower().replace(" ", "_")] = val

        # Parse user story (strip bold markdown to produce clean text)
        user_story = ""
        us_match = re.search(r"\*\*As a\*\*\s+(.+?)(?=\n\n|\n\*\*Acceptance)", body, re.DOTALL)
        if us_match:
            raw = us_match.group(0).strip()
            user_story = raw.replace("**", "")

        # Parse acceptance criteria
        ac = re.findall(r"- \[ \] `AC-\d+`:\s*(.+)", body)

        sp = int(meta.get("story_points", "0"))
        saga = meta.get("saga", "")
        priority = meta.get("priority", "")

        stories.append(Story(
            story_id=story_id,
            title=title,
            saga=saga,
            sp=sp,
            priority=priority,
            sprint=sprint,
            user_story=user_story,
            acceptance_criteria=ac,
            epic=meta.get("epic", ""),
            blocked_by=meta.get("blocked_by", "").replace("\u2014", "").strip(),
            blocks=meta.get("blocks", "").replace("\u2014", "").strip(),
            test_cases=meta.get("test_cases", "").replace("\u2014", "").strip(),
            source_file=source_file,
        ))
    return stories


# §populate_issues.enrich_from_epics
def enrich_from_epics(stories: list[Story], config: dict) -> list[Story]:
    """Enrich stories with detail blocks from epic files, if available."""
    epics_dir = config.get("paths", {}).get("epics_dir")
    if not epics_dir:
        return stories
    epics_path = Path(epics_dir)
    if not epics_path.is_dir():
        return stories

    # Build lookup of existing stories by ID
    by_id = {s.story_id: s for s in stories}
    new_stories = []

    for epic_file in sorted(epics_path.glob("*.md")):
        content = epic_file.read_text(encoding="utf-8", errors="replace")
        # Infer sprint from stories already parsed in this epic file
        known_sprints = [
            by_id[sid].sprint
            for sid in re.findall(r"US-\d{4}", content)
            if sid in by_id
        ]
        # Use most common sprint; break ties by picking the lowest number
        sprint = min(
            (s for s in set(known_sprints)
             if known_sprints.count(s) == max(known_sprints.count(x) for x in set(known_sprints))),
        ) if known_sprints else 0
        parsed = parse_detail_blocks(content, sprint=sprint, source_file=str(epic_file))
        for ps in parsed:
            if ps.story_id in by_id:
                # Merge: detail block fields override table-row fields
                existing = by_id[ps.story_id]
                existing.user_story = ps.user_story or existing.user_story
                existing.acceptance_criteria = ps.acceptance_criteria or existing.acceptance_criteria
                existing.epic = ps.epic or existing.epic
                existing.blocked_by = ps.blocked_by or existing.blocked_by
                existing.blocks = ps.blocks or existing.blocks
                existing.test_cases = ps.test_cases or existing.test_cases
            elif sprint == 0:
                # Skip stories with undeterminable sprint to avoid
                # creating orphaned issues with no milestone (BH-011)
                print(
                    f"  Warning: skipping {ps.story_id} from "
                    f"{epic_file.name} — cannot determine sprint number"
                )
            else:
                new_stories.append(ps)

    return stories + new_stories


# §populate_issues.get_existing_issues
def get_existing_issues() -> set[str]:
    """Fetch existing issue title prefixes (story IDs) for idempotency."""
    try:
        issues = gh_json(["issue", "list", "--limit", "500", "--json", "title", "--state", "all"])
        if not isinstance(issues, list):
            raise RuntimeError(f"Expected list from gh, got {type(issues).__name__}")
        warn_if_at_limit(issues, 500)
    except RuntimeError as exc:
        print(f"Error: could not fetch existing issues: {exc}", file=sys.stderr)
        raise
    existing: set[str] = set()
    for issue in issues:
        m = re.match(r"([A-Z]+-\d+):", issue.get("title", ""))
        if m:
            existing.add(m.group(1))
    return existing


# §populate_issues.get_milestone_numbers
def get_milestone_numbers() -> dict[str, int]:
    """Fetch milestone title -> number mapping from GitHub."""
    try:
        milestones = gh_json(["api", "repos/{owner}/{repo}/milestones?per_page=100",
                              "--paginate"])
        if not isinstance(milestones, list):
            raise RuntimeError(f"Expected list from gh, got {type(milestones).__name__}")
        return {m["title"]: m["number"] for m in milestones}
    except (RuntimeError, KeyError) as exc:
        print(f"Error: could not fetch milestones: {exc}", file=sys.stderr)
        raise


# §populate_issues.build_milestone_title_map
def build_milestone_title_map(
    milestone_files: list[str],
) -> dict[int, str]:
    """Map sprint number -> milestone title by reading milestone file headings.

    A milestone file may contain multiple ``### Sprint N:`` sections.
    Each sprint maps to the title (``# heading``) of the file that contains it.
    Falls back to filename-based inference when no sprint sections exist.
    """
    result: dict[int, str] = {}
    for mf_path in milestone_files:
        mf = Path(mf_path)
        if not mf.is_file():
            continue
        text = mf.read_text(encoding="utf-8")
        heading = re.search(r"^#\s+(.+)", text, re.MULTILINE)
        title = heading.group(1).strip() if heading else mf.stem

        # Find all sprint sections in this file
        sprint_nums = re.findall(r"### Sprint (\d+):", text)
        if sprint_nums:
            for n in sprint_nums:
                result[int(n)] = title
        else:
            # Infer sprint number from filename
            num = _infer_sprint_number(mf)
            result[num] = title
    return result


# §populate_issues.format_issue_body
def format_issue_body(story: Story) -> str:
    """Format enriched GitHub issue body from story."""
    lines = []
    # Persona placeholder — updated after kickoff assignment
    lines.append("> **[Unassigned]** \u00b7 Implementation\n")
    # Story header
    lines.append("## Story")
    lines.append(f"**{story.story_id}** \u2014 {story.title} | Sprint {story.sprint} | {story.sp} SP | {story.priority}")
    if story.epic:
        lines.append(f"**Epic:** {story.epic}")
    if story.saga:
        lines.append(f"**Saga:** {story.saga}")
    lines.append("")
    # User story
    if story.user_story:
        lines.append("## User Story")
        lines.append(story.user_story)
        lines.append("")
    # Acceptance criteria
    if story.acceptance_criteria:
        lines.append("## Acceptance Criteria")
        for i, ac in enumerate(story.acceptance_criteria, 1):
            lines.append(f"- [ ] `AC-{i:02d}`: {ac}")
        lines.append("")
    # Dependencies
    if story.blocked_by or story.blocks:
        lines.append("## Dependencies")
        if story.blocked_by:
            lines.append(f"**Blocked by:** {story.blocked_by}")
        if story.blocks:
            lines.append(f"**Blocks:** {story.blocks}")
        lines.append("")
    # Test coverage references (IDs only, not full content)
    if story.test_cases:
        lines.append("## Test Coverage")
        lines.append(f"**Test cases:** {story.test_cases}")
        lines.append("")
    return "\n".join(lines)


# §populate_issues.create_issue
def create_issue(
    story: Story,
    milestone_numbers: dict[str, int],
    milestone_titles: dict[int, str],
) -> bool:
    """Create a single GitHub issue for a story. Return True if created."""
    title = f"{story.story_id}: {story.title}"
    labels = [f"sprint:{story.sprint}", "type:story", "kanban:todo"]
    if story.saga:
        labels.append(f"saga:{story.saga}")
    if story.priority:
        labels.append(f"priority:{story.priority}")
    args = ["issue", "create", "--title", title,
            "--body", format_issue_body(story)]
    for label in labels:
        args.extend(["--label", label])
    ms_title = milestone_titles.get(story.sprint, "")
    if ms_title in milestone_numbers:
        args.extend(["--milestone", ms_title])
    try:
        output = gh(args)
        print(f"  + {story.story_id}: {story.title}  ->  {output}")
        return True
    except RuntimeError as exc:
        print(f"  ! {story.story_id}: {exc}")
        return False


def main() -> None:
    """Parse milestones and create GitHub issues."""
    if len(sys.argv) > 1 and sys.argv[1] in ("-h", "--help"):
        print(__doc__.strip())
        sys.exit(0)
    try:
        config = load_config()
    except ConfigError:
        sys.exit(1)
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
    stories = enrich_from_epics(stories, config)
    enriched = sum(1 for s in stories if s.user_story)
    print(f"  Enriched {enriched}/{len(stories)} stories with epic details.")

    print("\nChecking for existing issues...")
    try:
        existing = get_existing_issues()
    except RuntimeError:
        print("Cannot proceed without checking existing issues (would create duplicates).",
              file=sys.stderr)
        sys.exit(1)
    if existing:
        print(f"  Found {len(existing)} existing story issues.")
    try:
        milestone_numbers = get_milestone_numbers()
    except (RuntimeError, KeyError):
        print("Cannot proceed without milestone data.", file=sys.stderr)
        sys.exit(1)
    milestone_titles = build_milestone_title_map(milestone_files)

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
