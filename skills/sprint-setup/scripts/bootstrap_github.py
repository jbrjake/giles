#!/usr/bin/env python3
"""Bootstrap GitHub labels, milestones, and project board for sprint process.

Config-driven: reads all project-specific values from project.toml via
validate_config.load_config(). No hardcoded project names, personas, or sagas.
"""

import re
import subprocess
import sys
from pathlib import Path

# -- Import shared config ----------------------------------------------------
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent / "scripts"))
from validate_config import load_config, get_team_personas, get_milestones, get_epics_dir


def run_gh(args: list[str], check: bool = True) -> subprocess.CompletedProcess:
    """Run a gh CLI command."""
    result = subprocess.run(["gh", *args], capture_output=True, text=True)
    if check and result.returncode != 0:
        print(f"Error: gh {' '.join(args)}")
        print(result.stderr)
        if check:
            sys.exit(1)
    return result


def check_prerequisites() -> None:
    """Verify gh CLI is installed and authenticated."""
    result = subprocess.run(
        ["gh", "--version"], capture_output=True, text=True
    )
    if result.returncode != 0:
        print("Error: gh CLI not installed. See https://cli.github.com/")
        sys.exit(1)

    result = subprocess.run(
        ["gh", "auth", "status"], capture_output=True, text=True
    )
    if result.returncode != 0:
        print("Error: gh CLI not authenticated. Run 'gh auth login' first.")
        sys.exit(1)

    result = subprocess.run(
        ["git", "remote", "-v"], capture_output=True, text=True
    )
    if result.returncode != 0 or not result.stdout.strip():
        print("Error: No git remote configured. Add a GitHub remote first.")
        sys.exit(1)

    print("Prerequisites OK: gh installed, authenticated, remote configured.")


def create_label(name: str, color: str, description: str = "") -> None:
    """Create a label, skip if it already exists."""
    result = run_gh(
        ["label", "create", name, "--color", color,
         "--description", description, "--force"],
        check=False,
    )
    if result.returncode == 0:
        print(f"  + {name}")
    else:
        print(f"  ! {name}: {result.stderr.strip()}")


# -- Distinct color palette for personas (up to 20) -------------------------

_PERSONA_COLORS = [
    "1f77b4", "ff7f0e", "2ca02c", "d62728", "9467bd",
    "8c564b", "e377c2", "7f7f7f", "bcbd22", "17becf",
    "aec7e8", "ffbb78", "98df8a", "ff9896", "c5b0d5",
    "c49c94", "f7b6d2", "dbdb8d", "9edae5", "393b79",
]


def create_persona_labels(config: dict) -> None:
    """Create persona labels from team/INDEX.md."""
    personas = get_team_personas(config)
    if not personas:
        print("  (no personas found in team index)")
        return
    print("Persona labels:")
    for i, persona in enumerate(personas):
        name = persona["name"].lower().replace(" ", "-")
        color = _PERSONA_COLORS[i % len(_PERSONA_COLORS)]
        create_label(f"persona:{name}", color, f"Assigned to {persona['name']}")


def _collect_sprint_numbers(milestone_files: list[str]) -> set[int]:
    """Scan milestone files for all sprint section numbers.

    A milestone file may contain multiple ``### Sprint N:`` sections.
    Falls back to inferring from the filename if no sections are found.
    """
    sprint_nums: set[int] = set()
    for mf_path in milestone_files:
        mf = Path(mf_path)
        if not mf.is_file():
            continue
        text = mf.read_text(encoding="utf-8")
        found = re.findall(r"### Sprint (\d+):", text)
        if found:
            sprint_nums.update(int(n) for n in found)
        else:
            # Infer sprint number from filename (e.g. milestone-2.md)
            m = re.search(r"(\d+)", mf.stem)
            sprint_nums.add(int(m.group(1)) if m else 1)
    return sprint_nums


def create_sprint_labels(config: dict) -> None:
    """Create sprint labels -- one per sprint section found across all milestones."""
    milestone_files = get_milestones(config)
    sprint_nums = _collect_sprint_numbers(milestone_files)
    if not sprint_nums:
        print("  (no sprints found in milestone files)")
        return
    print("\nSprint labels:")
    for n in sorted(sprint_nums):
        create_label(f"sprint:{n}", "0075ca", f"Sprint {n}")


def _parse_saga_labels_from_backlog(config: dict) -> list[tuple[str, str]]:
    """Parse saga labels from backlog/INDEX.md.

    Looks for a table with columns containing saga IDs (Sxx) and names.
    Returns [(saga_id, saga_name), ...].
    """
    paths = config.get("paths", {})
    backlog_dir = paths.get("backlog_dir", "sprint-config/backlog")
    index_path = Path(backlog_dir) / "INDEX.md"

    if not index_path.is_file():
        return []

    text = index_path.read_text(encoding="utf-8")
    sagas: list[tuple[str, str]] = []

    # Match rows like: | S01 | Walking Skeleton | ... |
    # or: | S01: Walking Skeleton | ... |
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        # Pattern 1: | S01 | Walking Skeleton | ... |
        m = re.match(r"\|\s*(S\d{2})\s*\|\s*(.+?)\s*\|", stripped)
        if m:
            sagas.append((m.group(1), m.group(2).strip()))
            continue
        # Pattern 2: saga ID embedded in a cell
        m = re.search(r"(S\d{2})[:\s]+(.+?)(?:\s*\|)", stripped)
        if m:
            sagas.append((m.group(1), m.group(2).strip()))

    return sagas


def create_saga_labels(config: dict) -> None:
    """Create saga labels from backlog/INDEX.md."""
    sagas = _parse_saga_labels_from_backlog(config)
    if not sagas:
        print("\nSaga labels: (none found in backlog index)")
        return
    print("\nSaga labels:")
    for saga_id, saga_name in sagas:
        create_label(f"saga:{saga_id}", "0e8a16", saga_name)


def create_static_labels() -> None:
    """Create labels that are project-agnostic (priorities, kanban, types)."""
    # Priority labels
    print("\nPriority labels:")
    create_label("priority:P0", "b60205", "Blocks release")
    create_label("priority:P1", "d93f0b", "Must fix before GA")
    create_label("priority:P2", "fbca04", "Should fix")

    # Kanban labels
    print("\nKanban labels:")
    kanban = {
        "todo": ("cccccc", "Not yet started"),
        "design": ("c2e0c6", "Design in progress"),
        "dev": ("bfd4f2", "Development in progress"),
        "review": ("d4c5f9", "In code review"),
        "integration": ("fef2c0", "Merging and integration"),
        "done": ("0e8a16", "Complete"),
    }
    for state, (color, desc) in kanban.items():
        create_label(f"kanban:{state}", color, desc)

    # Type labels
    print("\nType labels:")
    create_label("type:story", "5319e7", "User story")
    create_label("type:bug", "b60205", "Bug fix")
    create_label("type:spike", "fbca04", "Research spike")
    create_label("type:chore", "ededed", "Maintenance task")


def create_epic_labels(epics_dir: Path) -> None:
    """Create epic: labels from epic filenames in epics_dir."""
    epic_re = re.compile(r"(E-\d{4})")
    for f in sorted(epics_dir.glob("*.md")):
        m = epic_re.search(f.stem)
        if m:
            epic_id = m.group(1)
            label = f"epic:{epic_id}"
            create_label(label, "0e8a16", f"Epic {epic_id}")


def create_milestones_on_github(config: dict) -> None:
    """Create sprint milestones from config milestone files."""
    milestone_files = get_milestones(config)
    if not milestone_files:
        print("\n=== No milestone files to create milestones from ===")
        return

    print("\n=== Creating Milestones ===\n")

    for i, mf_path in enumerate(milestone_files, 1):
        mf = Path(mf_path)
        # Parse title from the milestone file's first heading
        title = f"Sprint {i}"
        description = ""
        if mf.is_file():
            text = mf.read_text(encoding="utf-8")
            heading = re.search(r"^#\s+(.+)", text, re.MULTILINE)
            if heading:
                title = heading.group(1).strip()
            # Use first non-heading paragraph as description
            for line in text.splitlines():
                line = line.strip()
                if line and not line.startswith("#") and not line.startswith("|"):
                    description = line
                    break

        api_args = [
            "api", "repos/{owner}/{repo}/milestones",
            "-f", f"title={title}",
            "-f", f"description={description}",
            "-f", "state=open",
        ]
        result = run_gh(api_args, check=False)
        if result.returncode == 0:
            print(f"  + {title}")
        elif "already_exists" in result.stderr:
            print(f"  = {title} (already exists)")
        else:
            print(f"  ! {title}: {result.stderr.strip()}")


def main() -> None:
    """Run the full bootstrap using config."""
    if len(sys.argv) > 1 and sys.argv[1] in ("-h", "--help"):
        print(__doc__.strip())
        sys.exit(0)
    config = load_config()
    project_name = config.get("project", {}).get("name", "Project")

    print(f"=== {project_name} GitHub Bootstrap ===")
    check_prerequisites()

    print("\n=== Creating Labels ===\n")
    create_persona_labels(config)
    create_sprint_labels(config)
    create_saga_labels(config)
    create_static_labels()

    epics_dir = get_epics_dir(config)
    if epics_dir:
        print("\nCreating epic labels...")
        create_epic_labels(epics_dir)

    create_milestones_on_github(config)

    print("\n=== Bootstrap Complete ===")
    print(
        "Next: run populate_issues.py to create sprint stories as GitHub issues."
    )


if __name__ == "__main__":
    main()
