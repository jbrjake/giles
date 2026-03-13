#!/usr/bin/env python3
"""Shared defensive validation for the sprint process.

Every skill (sprint-setup, sprint-run, sprint-monitor, sprint-release) calls
validate_project() or load_config() before doing anything else. This ensures
the config directory is well-formed and all required files are present.

No external dependencies -- stdlib only.
"""

import os
import re
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Minimal TOML parser (handles the subset used by project.toml)
# ---------------------------------------------------------------------------

def parse_simple_toml(text: str) -> dict:
    """Parse a minimal TOML subset into a nested dict.

    Supports:
      - key = "value"  (strings)
      - key = 123      (integers)
      - key = true/false (booleans)
      - [section] and [section.subsection] headers
      - key = ["a", "b", "c"] (arrays of strings/ints/bools)
      - Multiline arrays (opening [ on one line, items on subsequent lines)
      - Comments starting with #
    """
    root: dict = {}
    current_section = root
    section_path: list[str] = []
    multiline_key: str | None = None
    multiline_buf: str = ""

    for raw_line in text.splitlines():
        line = raw_line.strip()

        # Continue collecting a multiline array
        if multiline_key is not None:
            multiline_buf += " " + line
            if "]" in line:
                _set_nested(
                    root, section_path, multiline_key,
                    _parse_value(multiline_buf.strip()),
                )
                multiline_key = None
                multiline_buf = ""
            continue

        # Blank lines and comments
        if not line or line.startswith("#"):
            continue

        # Section header: [section] or [section.subsection]
        header_match = re.match(r"^\[([a-zA-Z0-9_][a-zA-Z0-9_.]*)\]\s*(?:#.*)?$", line)
        if header_match:
            section_path = header_match.group(1).split(".")
            # Ensure the nested dicts exist
            current_section = root
            for part in section_path:
                current_section = current_section.setdefault(part, {})
            continue

        # Key = value
        kv_match = re.match(r"^([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*(.*)$", line)
        if kv_match:
            key = kv_match.group(1)
            raw_val = kv_match.group(2).strip()

            # Detect multiline array: line ends with [ but no closing ]
            stripped_no_comment = _strip_inline_comment(raw_val)
            if stripped_no_comment.startswith("[") and "]" not in stripped_no_comment:
                multiline_key = key
                multiline_buf = stripped_no_comment
                continue

            _set_nested(root, section_path, key, _parse_value(raw_val))

    return root


def _strip_inline_comment(val: str) -> str:
    """Remove trailing # comments that are outside of quotes."""
    in_str = False
    for i, ch in enumerate(val):
        if ch == '"' and (i == 0 or val[i - 1] != "\\"):
            in_str = not in_str
        elif ch == "#" and not in_str:
            return val[:i].rstrip()
    return val


def _parse_value(raw: str):
    """Parse a single TOML value (string, int, bool, or array)."""
    raw = _strip_inline_comment(raw).strip()

    # Boolean
    if raw == "true":
        return True
    if raw == "false":
        return False

    # String
    if raw.startswith('"') and raw.endswith('"'):
        return raw[1:-1].replace('\\"', '"')

    # Array
    if raw.startswith("[") and raw.endswith("]"):
        inner = raw[1:-1].strip()
        if not inner:
            return []
        items = []
        for part in _split_array(inner):
            part = part.strip()
            if part:
                items.append(_parse_value(part))
        return items

    # Integer
    try:
        return int(raw)
    except ValueError:
        pass

    # Fall back to raw string
    return raw


def _split_array(inner: str) -> list[str]:
    """Split array contents by commas, respecting quoted strings."""
    parts: list[str] = []
    current = ""
    in_str = False
    for ch in inner:
        if ch == '"' and (not current or current[-1] != "\\"):
            in_str = not in_str
            current += ch
        elif ch == "," and not in_str:
            parts.append(current)
            current = ""
        else:
            current += ch
    if current.strip():
        parts.append(current)
    return parts


def _set_nested(root: dict, section_path: list[str], key: str, value) -> None:
    """Set a value in a nested dict addressed by section_path + key."""
    target = root
    for part in section_path:
        target = target.setdefault(part, {})
    target[key] = value


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

_REQUIRED_FILES = [
    ("{config_dir}/project.toml",
     "Master configuration (project name, repo, language, CI commands)"),
    ("{config_dir}/team/INDEX.md",
     "Team roster listing personas with Name, Role, File columns"),
    ("{config_dir}/backlog/INDEX.md",
     "Backlog routing table"),
    ("{config_dir}/rules.md",
     "Project conventions and constraints"),
    ("{config_dir}/development.md",
     "Development process guide"),
]

_REQUIRED_TOML_KEYS: list[tuple[str, ...]] = [
    ("project", "name"),
    ("project", "repo"),
    ("project", "language"),
    ("paths", "team_dir"),
    ("paths", "backlog_dir"),
    ("paths", "sprints_dir"),
    ("ci", "check_commands"),
    ("ci", "build_command"),
]

_REQUIRED_TOML_SECTIONS = ["project", "paths", "ci"]


def validate_project(
    config_dir: str = "sprint-config",
) -> tuple[bool, list[str]]:
    """Validate the sprint config directory.

    Returns (success, errors) where errors is a list of human-readable
    strings describing what is wrong.
    """
    errors: list[str] = []
    config_path = Path(config_dir)

    # ------------------------------------------------------------------
    # 1. Required files exist
    # ------------------------------------------------------------------
    missing_files: list[tuple[str, str]] = []
    for template, description in _REQUIRED_FILES:
        fpath = template.format(config_dir=config_dir)
        if not Path(fpath).is_file():
            missing_files.append((fpath, description))
            errors.append(f"Missing file: {fpath} -- {description}")

    # ------------------------------------------------------------------
    # 2. project.toml parses and has required sections/keys
    # ------------------------------------------------------------------
    toml_path = config_path / "project.toml"
    config: dict = {}
    if toml_path.is_file():
        try:
            config = parse_simple_toml(toml_path.read_text(encoding="utf-8"))
        except Exception as exc:
            errors.append(f"Failed to parse {toml_path}: {exc}")

        # Required sections
        for section in _REQUIRED_TOML_SECTIONS:
            if section not in config:
                errors.append(
                    f"project.toml missing required section: [{section}]"
                )

        # Required keys
        for key_path in _REQUIRED_TOML_KEYS:
            obj = config
            resolved = True
            for part in key_path:
                if isinstance(obj, dict) and part in obj:
                    obj = obj[part]
                else:
                    resolved = False
                    break
            if not resolved:
                dotted = ".".join(key_path)
                errors.append(
                    f"project.toml missing required key: {dotted}"
                )

    # ------------------------------------------------------------------
    # 3. team/INDEX.md has at least 2 personas
    # ------------------------------------------------------------------
    team_index = config_path / "team" / "INDEX.md"
    persona_rows: list[dict[str, str]] = []
    if team_index.is_file():
        persona_rows = _parse_team_index(team_index)
        if len(persona_rows) < 2:
            errors.append(
                f"team/INDEX.md must list at least 2 personas "
                f"(found {len(persona_rows)})"
            )

    # ------------------------------------------------------------------
    # 4. Each persona has a corresponding file
    # ------------------------------------------------------------------
    for row in persona_rows:
        persona_file = row.get("file", "")
        if persona_file:
            full = config_path / "team" / persona_file
        else:
            name_slug = row.get("name", "unknown").lower().replace(" ", "-")
            full = config_path / "team" / f"{name_slug}.md"
        if not full.is_file():
            errors.append(f"Persona file missing: {full}")

    # ------------------------------------------------------------------
    # 5. At least one milestone file
    # ------------------------------------------------------------------
    milestones_dir = config_path / "backlog" / "milestones"
    if milestones_dir.is_dir():
        milestone_files = [
            f for f in milestones_dir.iterdir()
            if f.is_file() and f.suffix == ".md"
        ]
        if not milestone_files:
            errors.append(
                f"No milestone files found in {milestones_dir}/"
            )
    else:
        errors.append(f"Milestones directory missing: {milestones_dir}/")

    # ------------------------------------------------------------------
    # 6. rules.md and development.md are non-empty
    # ------------------------------------------------------------------
    for name in ("rules.md", "development.md"):
        fpath = config_path / name
        if fpath.is_file():
            if fpath.stat().st_size == 0:
                errors.append(f"{fpath} exists but is empty")

    return (len(errors) == 0, errors)


def _parse_team_index(index_path: Path) -> list[dict[str, str]]:
    """Parse the markdown table in team/INDEX.md.

    Expects a table with at least Name, Role, and File columns.
    Returns a list of dicts with lowercase keys.
    """
    lines = index_path.read_text(encoding="utf-8").splitlines()
    headers: list[str] = []
    rows: list[dict[str, str]] = []

    for line in lines:
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        cells = [c.strip() for c in stripped.strip("|").split("|")]

        # First table row is the header
        if not headers:
            headers = [c.lower() for c in cells]
            continue

        # Skip separator rows (e.g., |---|---|---|)
        if all(re.match(r"^[-:]+$", c) for c in cells):
            continue

        row = {}
        for i, cell in enumerate(cells):
            if i < len(headers):
                row[headers[i]] = cell
        rows.append(row)

    return rows


# ---------------------------------------------------------------------------
# Pretty error output
# ---------------------------------------------------------------------------

_DIRECTORY_TEMPLATE = """\
Expected directory structure:
  {config_dir}/
  |-- project.toml
  |-- team/
  |   |-- INDEX.md
  |   +-- {{name}}.md (one per persona)
  |-- backlog/
  |   |-- INDEX.md
  |   +-- milestones/
  |       +-- {{milestone}}.md
  |-- rules.md
  +-- development.md

Run sprint-init to auto-detect and scaffold {config_dir}/."""


def _print_errors(errors: list[str], config_dir: str) -> None:
    """Print validation errors with actionable guidance."""
    print(f"\nSprint process cannot run. {len(errors)} problem(s) found:\n")
    for err in errors:
        print(f"  x {err}")
    print()
    print(_DIRECTORY_TEMPLATE.format(config_dir=config_dir))


# ---------------------------------------------------------------------------
# Convenience: load_config
# ---------------------------------------------------------------------------

def load_config(config_dir: str = "sprint-config") -> dict:
    """Validate config, then return the parsed project.toml as a dict.

    Resolves all [paths] values relative to the project root (the directory
    from which the script is invoked), not relative to config_dir.

    Calls sys.exit(1) if validation fails.
    """
    ok, errors = validate_project(config_dir)
    if not ok:
        _print_errors(errors, config_dir)
        sys.exit(1)

    toml_path = Path(config_dir) / "project.toml"
    config = parse_simple_toml(toml_path.read_text(encoding="utf-8"))

    # Resolve paths relative to the project root, which is the parent
    # of config_dir. This ensures scripts work regardless of cwd.
    project_root = Path(config_dir).resolve().parent
    if "paths" in config and isinstance(config["paths"], dict):
        for key, val in config["paths"].items():
            if isinstance(val, str):
                config["paths"][key] = str(project_root / val)

    return config


# ---------------------------------------------------------------------------
# Query helpers
# ---------------------------------------------------------------------------

def get_team_personas(config: dict) -> list[dict[str, str]]:
    """Return a list of persona dicts from team/INDEX.md.

    Each dict has keys: name, role, file (absolute path).
    """
    paths = config.get("paths", {})
    team_dir = paths.get("team_dir", "sprint-config/team")
    index_path = Path(team_dir) / "INDEX.md"

    if not index_path.is_file():
        return []

    rows = _parse_team_index(index_path)
    result: list[dict[str, str]] = []
    for row in rows:
        name = row.get("name", "")
        role = row.get("role", "")
        file_ref = row.get("file", "")
        if file_ref:
            fpath = str(Path(team_dir) / file_ref)
        else:
            slug = name.lower().replace(" ", "-")
            fpath = str(Path(team_dir) / f"{slug}.md")
        result.append({"name": name, "role": role, "file": fpath})

    return result


def get_milestones(config: dict) -> list[str]:
    """Return a sorted list of milestone file paths."""
    paths = config.get("paths", {})
    backlog_dir = paths.get("backlog_dir", "sprint-config/backlog")
    milestones_dir = Path(backlog_dir) / "milestones"

    if not milestones_dir.is_dir():
        return []

    return sorted(
        str(f) for f in milestones_dir.iterdir()
        if f.is_file() and f.suffix == ".md"
    )


def get_ci_commands(config: dict) -> list[str]:
    """Return the CI check commands list from [ci]."""
    ci = config.get("ci", {})
    commands = ci.get("check_commands", [])
    if isinstance(commands, list):
        return commands
    return [str(commands)]


def get_base_branch(config: dict) -> str:
    """Return the base branch from config, defaulting to 'main'."""
    branch = config.get("project", {}).get("base_branch", "main")
    return branch if branch else "main"


def get_prd_dir(config: dict) -> Path | None:
    """Return PRD directory path, or None if not configured."""
    val = config.get("paths", {}).get("prd_dir")
    if not val:
        return None
    p = Path(val)
    return p if p.is_dir() else None


def get_test_plan_dir(config: dict) -> Path | None:
    """Return test plan directory path, or None if not configured."""
    val = config.get("paths", {}).get("test_plan_dir")
    if not val:
        return None
    p = Path(val)
    return p if p.is_dir() else None


def get_sagas_dir(config: dict) -> Path | None:
    """Return sagas directory path, or None if not configured."""
    val = config.get("paths", {}).get("sagas_dir")
    if not val:
        return None
    p = Path(val)
    return p if p.is_dir() else None


def get_epics_dir(config: dict) -> Path | None:
    """Return epics directory path, or None if not configured."""
    val = config.get("paths", {}).get("epics_dir")
    if not val:
        return None
    p = Path(val)
    return p if p.is_dir() else None


def extract_sp(issue: dict) -> int:
    """Extract story points from an issue's labels or body text.

    Checks (in order):
      1. Labels matching sp:N
      2. Body text with "story points: N" or "sp = N" (case-insensitive)
      3. Body table format | SP | N | or | Story Points | N |
      4. Body table format | N SP | (analytics-style)
    Returns 0 if no story points found.
    """
    import re
    for label in issue.get("labels", []):
        name = label if isinstance(label, str) else label.get("name", "")
        if m := re.match(r"sp:(\d+)", name):
            return int(m.group(1))
    body = issue.get("body", "") or ""
    if m := re.search(
        r"(?:story\s*points?|sp)\s*[:=]\s*(\d+)", body, re.IGNORECASE
    ):
        return int(m.group(1))
    if m := re.search(r"\|\s*SP\s*\|\s*(\d+)\s*\|", body):
        return int(m.group(1))
    if m := re.search(r"\|\s*Story Points?\s*\|\s*(\d+)\s*\|", body):
        return int(m.group(1))
    if m := re.search(r"\|\s*(\d+)\s*SP\s*\|", body):
        return int(m.group(1))
    return 0


def get_story_map(config: dict) -> Path | None:
    """Return story map index file path, or None if not configured."""
    val = config.get("paths", {}).get("story_map")
    if not val:
        return None
    p = Path(val)
    return p if p.is_file() else None


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Run validation from the command line."""
    if len(sys.argv) > 1 and sys.argv[1] in ("-h", "--help"):
        print(__doc__.strip())
        sys.exit(0)
    config_dir = sys.argv[1] if len(sys.argv) > 1 else "sprint-config"

    ok, errors = validate_project(config_dir)
    if ok:
        print(f"Config OK: {config_dir}/ is valid.")
    else:
        _print_errors(errors, config_dir)
        sys.exit(1)


if __name__ == "__main__":
    main()
