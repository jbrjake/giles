#!/usr/bin/env python3
"""Shared defensive validation for the sprint process.

Every skill (sprint-setup, sprint-run, sprint-monitor, sprint-release) calls
validate_project() or load_config() before doing anything else. This ensures
the config directory is well-formed and all required files are present.

No external dependencies -- stdlib only.
"""

import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class ConfigError(ValueError):
    """Raised when sprint-config validation fails."""


# ---------------------------------------------------------------------------
# Shared utility helpers
# ---------------------------------------------------------------------------

# §validate_config.safe_int
def safe_int(value: str) -> int:
    """Extract leading digits from a string, returning 0 if none found."""
    m = re.match(r'(\d+)', str(value).strip())
    return int(m.group(1)) if m else 0


# §validate_config.parse_iso_date
def parse_iso_date(iso: str, fmt: str = "%Y-%m-%d", default: str = "") -> str:
    """Parse an ISO 8601 date string, return formatted date or default."""
    if not iso:
        return default
    try:
        return datetime.fromisoformat(
            iso.replace("Z", "+00:00")
        ).strftime(fmt)
    except (ValueError, TypeError):
        return default


# ---------------------------------------------------------------------------
# Shared GitHub CLI helpers
# ---------------------------------------------------------------------------

# §validate_config.gh
def gh(args: list[str], timeout: int = 60) -> str:
    """Run a gh CLI command and return stdout. Raises RuntimeError on failure."""
    try:
        r = subprocess.run(
            ["gh", *args], capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError(
            f"gh {' '.join(args)}: timed out after {timeout}s"
        ) from None
    if r.returncode != 0:
        raise RuntimeError(f"gh {' '.join(args)}: {r.stderr.strip()}")
    return r.stdout.strip()


# §validate_config.gh_json
def gh_json(args: list[str]) -> list | dict:
    """Run a gh CLI command and parse JSON output.

    Returns [] (empty list) when the command produces no output, rather
    than attempting json.loads("") which would raise JSONDecodeError.
    Callers should handle both list and dict return types.

    Handles ``gh api --paginate`` output, which concatenates raw JSON
    arrays per page (``[...][...]``).  The standard ``json.loads`` would
    fail or only parse the first page, so we use incremental decoding to
    merge all pages into a single list.
    """
    raw = gh(args)
    if not raw:
        return []
    # Fast path: try normal JSON parse first
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    # Slow path: handle concatenated JSON arrays from --paginate.
    # BH19-011: Wrap in try/except — truly garbage data (e.g., HTML error
    # pages) would raise JSONDecodeError from raw_decode with no handler.
    try:
        decoder = json.JSONDecoder()
        parts: list = []
        pos = 0
        length = len(raw)
        while pos < length:
            # Skip whitespace between concatenated objects
            while pos < length and raw[pos] in ' \n\r\t':
                pos += 1
            if pos >= length:
                break
            obj, end = decoder.raw_decode(raw, pos)
            if isinstance(obj, list):
                parts.extend(obj)
            else:
                parts.append(obj)
            pos = end
        return parts
    except json.JSONDecodeError:
        raise RuntimeError(
            f"gh returned non-JSON output ({len(raw)} bytes): "
            f"{raw[:80]!r}{'...' if len(raw) > 80 else ''}"
        )


# ---------------------------------------------------------------------------
# Minimal TOML parser (handles the subset used by project.toml)
# ---------------------------------------------------------------------------

# §validate_config.parse_simple_toml
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
            # Strip inline comments per continuation line (BH-001),
            # and use quote-aware bracket detection (BH-002).
            stripped_line = _strip_inline_comment(line)
            multiline_buf += " " + stripped_line
            if _has_closing_bracket(stripped_line):
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

        # Section header: [section] or [section.subsection] (hyphens allowed)
        header_match = re.match(r"^\[([a-zA-Z0-9_][a-zA-Z0-9_.-]*)\]\s*(?:#.*)?$", line)
        if header_match:
            section_path = header_match.group(1).split(".")
            # Ensure the nested dicts exist
            current_section = root
            for part in section_path:
                current_section = current_section.setdefault(part, {})
            continue

        # Key = value
        # Note: dotted keys (a.b = "value") are not supported. This project uses
        # section headers ([project], [paths]) rather than dotted keys.
        kv_match = re.match(r"^([a-zA-Z_][a-zA-Z0-9_-]*)\s*=\s*(.*)$", line)
        if kv_match:
            key = kv_match.group(1)
            raw_val = kv_match.group(2).strip()

            # Detect multiline array: starts with [ but no unquoted closing ]
            stripped_no_comment = _strip_inline_comment(raw_val)
            if stripped_no_comment.startswith("[") and not _has_closing_bracket(stripped_no_comment[1:]):
                multiline_key = key
                multiline_buf = stripped_no_comment
                continue

            _set_nested(root, section_path, key, _parse_value(raw_val))

    if multiline_key is not None:
        raise ValueError(
            f"Unterminated multiline array for key {multiline_key!r} "
            f"(missing closing ']')"
        )

    return root


def _count_trailing_backslashes(s: str, pos: int) -> int:
    """Count consecutive backslashes immediately before position *pos*."""
    n = 0
    while pos - 1 - n >= 0 and s[pos - 1 - n] == "\\":
        n += 1
    return n


def _strip_inline_comment(val: str) -> str:
    """Remove trailing # comments that are outside of quotes."""
    quote_char = None  # None, '"', or "'"
    for i, ch in enumerate(val):
        if quote_char is None:
            if ch in ('"', "'"):
                quote_char = ch
            elif ch == "#":
                return val[:i].rstrip()
        elif ch == quote_char:
            if quote_char == '"' and _count_trailing_backslashes(val, i) % 2 != 0:
                continue  # escaped double quote
            quote_char = None
    return val


def _has_closing_bracket(s: str) -> bool:
    """Check if s contains ] outside of quoted strings."""
    quote_char = None  # None, '"', or "'"
    for i, ch in enumerate(s):
        if quote_char is None:
            if ch in ('"', "'"):
                quote_char = ch
            elif ch == ']':
                return True
        elif ch == quote_char:
            if quote_char == '"' and _count_trailing_backslashes(s, i) % 2 != 0:
                continue  # escaped double quote
            quote_char = None
    return False


def _unescape_toml_string(s: str) -> str:
    """Process basic TOML escape sequences: \\n, \\t, \\\\, \\"."""
    result: list[str] = []
    i = 0
    while i < len(s):
        if s[i] == '\\' and i + 1 < len(s):
            nxt = s[i + 1]
            if nxt == 'n':
                result.append('\n')
            elif nxt == 't':
                result.append('\t')
            elif nxt == '\\':
                result.append('\\')
            elif nxt == '"':
                result.append('"')
            elif nxt == 'u' and i + 6 <= len(s):
                try:
                    result.append(chr(int(s[i + 2:i + 6], 16)))
                    i += 6
                    continue
                except (ValueError, OverflowError):
                    result.append(s[i:i + 2])
            elif nxt == 'U' and i + 10 <= len(s):
                try:
                    result.append(chr(int(s[i + 2:i + 10], 16)))
                    i += 10
                    continue
                except (ValueError, OverflowError):
                    result.append(s[i:i + 2])
            else:
                result.append(s[i:i + 2])  # Unknown escape, keep as-is
            i += 2
        else:
            result.append(s[i])
            i += 1
    return ''.join(result)


def _parse_value(raw: str):
    """Parse a single TOML value (string, int, bool, or array)."""
    raw = _strip_inline_comment(raw).strip()

    # Boolean
    if raw == "true":
        return True
    if raw == "false":
        return False

    # Detect unsupported multi-line strings (BH-007)
    if raw.startswith('"""') or raw.startswith("'''"):
        raise ValueError(
            f"Multi-line strings ({raw[:3]}...{raw[:3]}) are not supported "
            f"by this parser. Use single-line strings instead."
        )

    # String (must be at least 2 chars: opening + closing quote)
    if len(raw) >= 2 and raw.startswith('"') and raw.endswith('"'):
        return _unescape_toml_string(raw[1:-1])

    # Literal string (single-quoted, no escape processing per TOML spec)
    if len(raw) >= 2 and raw.startswith("'") and raw.endswith("'"):
        return raw[1:-1]

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

    # BH-002: Reject unquoted values containing TOML metacharacters that
    # indicate a syntax error (e.g., ``name = foo = bar``).
    for meta in ('=', '[', ']', '{', '}'):
        if meta in raw:
            raise ValueError(
                f"Unquoted TOML value contains '{meta}': {raw!r}. "
                f"Did you mean to quote it? Use: key = \"{raw}\""
            )

    # Fall back to raw string — intentional leniency: unquoted values like
    # ``key = hello`` are accepted as plain strings rather than raising.
    # This keeps the minimal parser forgiving for simple unquoted usage.
    if ' ' in raw and not raw.startswith('#'):
        print(f"Warning: unquoted TOML value '{raw}' interpreted as raw string. "
              f"Did you mean to quote it?", file=sys.stderr)
    return raw


def _split_array(inner: str) -> list[str]:
    """Split array contents by commas, respecting quoted strings and nesting.

    Handles both single- and double-quoted strings as per the TOML spec.
    Handles escaped quotes (``\\"``) and escaped backslashes (``\\\\``).
    An even number of consecutive backslashes before a quote means the
    quote is real (ends/starts the string); an odd number means it's escaped.

    Tracks bracket nesting depth so nested arrays like ``["a", "b"], ["c"]``
    are split correctly at the top-level commas only.
    """
    parts: list[str] = []
    current = ""
    in_str = False
    quote_char = ""
    depth = 0
    for ch in inner:
        if not in_str and ch in ('"', "'"):
            # Starting a new string — record which quote type
            n_bs = _count_trailing_backslashes(current, len(current))
            if n_bs % 2 == 0:
                in_str = True
                quote_char = ch
            current += ch
        elif in_str and ch == quote_char:
            # Potentially closing the current string
            n_bs = _count_trailing_backslashes(current, len(current))
            if n_bs % 2 == 0:
                in_str = False
                quote_char = ""
            current += ch
        elif not in_str and ch == "[":
            depth += 1
            current += ch
        elif not in_str and ch == "]":
            depth -= 1
            current += ch
        elif ch == "," and not in_str and depth == 0:
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

# §validate_config._REQUIRED_FILES
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
    ("{config_dir}/definition-of-done.md",
     "Definition of Done (baseline + retro-driven additions)"),
]

# §validate_config._REQUIRED_TOML_KEYS
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

# §validate_config._REQUIRED_TOML_SECTIONS
_REQUIRED_TOML_SECTIONS = ["project", "paths", "ci"]


# §validate_config.validate_project
def validate_project(
    config_dir: str = "sprint-config",
    _config: dict | None = None,
) -> tuple[bool, list[str]]:
    """Validate the sprint config directory.

    Returns (success, errors) where errors is a list of human-readable
    strings describing what is wrong.

    If *_config* is provided (pre-parsed TOML dict), skip re-reading
    project.toml from disk (BH-014: avoids double-parse in load_config).
    """
    errors: list[str] = []
    config_path = Path(config_dir)

    # ------------------------------------------------------------------
    # 1. Required files exist
    # ------------------------------------------------------------------
    missing_files: list[tuple[str, str]] = []
    for template, description in _REQUIRED_FILES:
        # Use .replace() instead of .format() to avoid format-string
        # injection if config_dir contains braces (BH-P11-110).
        fpath = template.replace("{config_dir}", str(config_dir))
        if not Path(fpath).is_file():
            missing_files.append((fpath, description))
            errors.append(f"Missing file: {fpath} -- {description}")

    # ------------------------------------------------------------------
    # 2. project.toml parses and has required sections/keys
    # ------------------------------------------------------------------
    toml_path = config_path / "project.toml"
    config: dict = _config if _config is not None else {}
    if _config is None and toml_path.is_file():
        try:
            config = parse_simple_toml(toml_path.read_text(encoding="utf-8"))
        except Exception as exc:
            errors.append(f"Failed to parse {toml_path}: {exc}")

    # Required sections (must run regardless of whether _config was provided,
    # and even when config is empty — an empty dict IS a validation failure)
    if toml_path.is_file() or _config is not None:
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
    # 3. team/INDEX.md has at least 2 non-Giles personas
    # ------------------------------------------------------------------
    # BH18-008: Sprint-run requires at least 2 personas for implementer/
    # reviewer assignment. Giles (scrum master) doesn't count — he
    # facilitates but doesn't implement or review code.
    team_index = config_path / "team" / "INDEX.md"
    persona_rows: list[dict[str, str]] = []
    if team_index.is_file():
        persona_rows = _parse_team_index(team_index)
        non_giles = [r for r in persona_rows
                     if r.get("name", "").lower() != "giles"]
        if len(non_giles) < 2:
            errors.append(
                f"team/INDEX.md must list at least 2 non-Giles personas "
                f"for implementer/reviewer assignment "
                f"(found {len(non_giles)})"
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


# §validate_config._parse_team_index
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
        # Strip whitespace from cells and filter empty ones before checking
        sep_cells = [c.strip() for c in cells]
        if all(re.match(r"^[-:]+$", c) for c in sep_cells if c):
            continue

        if len(cells) != len(headers):
            print(f"Warning: team/INDEX.md row has {len(cells)} cells, expected {len(headers)}",
                  file=sys.stderr)
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

# §validate_config.load_config
def load_config(config_dir: str = "sprint-config") -> dict:
    """Validate config, then return the parsed project.toml as a dict.

    Resolves all [paths] values relative to the project root (the directory
    from which the script is invoked), not relative to config_dir.

    Raises ConfigError if validation fails.
    """
    # BH-014: Parse TOML once and pass to validate_project to avoid
    # double-read (previously parsed in validate_project AND here).
    # BH-003: Propagate parse errors instead of swallowing them.
    toml_path = Path(config_dir) / "project.toml"
    config: dict = {}
    _parse_error: str = ""
    if toml_path.is_file():
        try:
            config = parse_simple_toml(toml_path.read_text(encoding="utf-8"))
        except Exception as exc:
            _parse_error = f"Failed to parse {toml_path}: {exc}"

    ok, errors = validate_project(config_dir, _config=config)
    # BH-003: Prepend the actual parse error so users see the root cause
    if _parse_error:
        errors.insert(0, _parse_error)
        ok = False
    if not ok:
        _print_errors(errors, config_dir)
        raise ConfigError(
            f"Config validation failed ({len(errors)} error(s)): "
            + "; ".join(errors)
        )

    # Store config_dir so downstream code can derive file paths
    config["_config_dir"] = config_dir

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

# §validate_config.get_team_personas
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


# §validate_config.get_milestones
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


# §validate_config.get_ci_commands
def get_ci_commands(config: dict) -> list[str]:
    """Return the CI check commands list from [ci]."""
    ci = config.get("ci", {})
    commands = ci.get("check_commands", [])
    if isinstance(commands, list):
        return commands
    return [str(commands)]


# §validate_config.get_base_branch
def get_base_branch(config: dict) -> str:
    """Return the base branch from config, defaulting to 'main'."""
    branch = config.get("project", {}).get("base_branch", "main")
    return branch if branch else "main"


# §validate_config.get_sprints_dir
def get_sprints_dir(config: dict) -> Path:
    """Return sprints directory path (required key, always present after validation)."""
    return Path(config.get("paths", {}).get("sprints_dir", "sprints"))


# §validate_config.get_prd_dir
def get_prd_dir(config: dict) -> Path | None:
    """Return PRD directory path, or None if not configured."""
    val = config.get("paths", {}).get("prd_dir")
    if not val:
        return None
    p = Path(val)
    return p if p.is_dir() else None


# §validate_config.get_test_plan_dir
def get_test_plan_dir(config: dict) -> Path | None:
    """Return test plan directory path, or None if not configured."""
    val = config.get("paths", {}).get("test_plan_dir")
    if not val:
        return None
    p = Path(val)
    return p if p.is_dir() else None


# §validate_config.get_sagas_dir
def get_sagas_dir(config: dict) -> Path | None:
    """Return sagas directory path, or None if not configured."""
    val = config.get("paths", {}).get("sagas_dir")
    if not val:
        return None
    p = Path(val)
    return p if p.is_dir() else None


# §validate_config.get_epics_dir
def get_epics_dir(config: dict) -> Path | None:
    """Return epics directory path, or None if not configured."""
    val = config.get("paths", {}).get("epics_dir")
    if not val:
        return None
    p = Path(val)
    return p if p.is_dir() else None


# §validate_config.extract_sp
def extract_sp(issue: dict) -> int:
    """Extract story points from an issue's labels or body text.

    Checks (in order):
      1. Labels matching sp:N (manual use — bootstrap does not create sp: labels)
      2. Body text with "story points: N" or "sp = N" (case-insensitive)
      3. Body table format | SP | N | or | Story Points | N |
      4. Body table format | N SP | (analytics-style)
    Returns 0 if no story points found.
    Note: In the automated flow, SP comes from the issue body (populated by
    format_issue_body). The label path exists for manual sp:N label use.
    """
    for label in issue.get("labels", []):
        if isinstance(label, str):
            name = label
        elif isinstance(label, dict):
            name = label.get("name", "")
        else:
            continue
        if m := re.search(r"sp:\s*(\d+)", name, re.IGNORECASE):
            return int(m.group(1))
    body = issue.get("body", "") or ""
    if m := re.search(
        r"(?:story\s*points?|(?<![a-zA-Z])sp)\s*[:=]\s*(\d+)", body, re.IGNORECASE
    ):
        return int(m.group(1))
    if m := re.search(r"\|\s*SP\s*\|\s*(\d+)\s*\|", body):
        return int(m.group(1))
    if m := re.search(r"\|\s*Story Points?\s*\|\s*(\d+)\s*\|", body):
        return int(m.group(1))
    if m := re.search(r"\|\s*(\d+)\s*SP\s*\|", body):
        return int(m.group(1))
    return 0


# §validate_config.get_story_map
def get_story_map(config: dict) -> Path | None:
    """Return story map index file path, or None if not configured."""
    val = config.get("paths", {}).get("story_map")
    if not val:
        return None
    p = Path(val)
    return p if p.is_file() else None


# ---------------------------------------------------------------------------
# Shared markdown table helpers (BH18-012/013)
# ---------------------------------------------------------------------------

# §validate_config.TABLE_ROW
TABLE_ROW = re.compile(r'^\|\s*(.+?)\s*\|\s*(.+?)\s*\|')


# §validate_config.parse_header_table
def parse_header_table(lines: list[str], stop_heading: str = "###") -> dict[str, str]:
    """Parse a markdown metadata table at the top of a structured file.

    BH18-013: Shared implementation — manage_epics and manage_sagas
    previously had independent copies. The stop_heading parameter
    controls where to stop scanning (### for epics, ## for sagas).
    """
    metadata: dict[str, str] = {}
    in_table = False
    for line in lines:
        if line.startswith(stop_heading):
            break
        row = TABLE_ROW.match(line)
        if row:
            field = row.group(1).strip()
            value = row.group(2).strip()
            if field not in ("Field", "---", "") and field.strip("-") != "":
                metadata[field] = value
                in_table = True
        elif in_table and line.strip() == "":
            break
    return metadata


# ---------------------------------------------------------------------------
# Frontmatter parsing helper (shared by sync_tracking and update_burndown)
# ---------------------------------------------------------------------------

# §validate_config.frontmatter_value
def frontmatter_value(frontmatter: str, key: str) -> str | None:
    """Extract a value from YAML-ish frontmatter text.

    BH18-005: Shared implementation — sync_tracking.read_tf and
    update_burndown._fm_val previously had independent copies of this logic.
    The unescape order (quotes then backslashes) must match _yaml_safe()
    in sync_tracking.py.
    """
    m = re.search(rf"^{key}:\s*(.+)", frontmatter, re.MULTILINE)
    if not m:
        return None
    val = m.group(1).strip()
    # Strip surrounding double quotes and unescape (reverse of _yaml_safe)
    if len(val) >= 2 and val[0] == '"' and val[-1] == '"':
        val = val[1:-1].replace('\\"', '"').replace('\\\\', '\\')
    return val


# ---------------------------------------------------------------------------
# Sprint / story / kanban helpers (shared across skills)
# ---------------------------------------------------------------------------

# §validate_config.detect_sprint
def detect_sprint(sprints_dir: Path) -> int | None:
    """Detect the current sprint number from SPRINT-STATUS.md."""
    status_file = sprints_dir / "SPRINT-STATUS.md"
    if not status_file.exists():
        return None
    m = re.search(
        r"Current Sprint:\s*(\d+)",
        status_file.read_text(encoding="utf-8"),
    )
    return int(m.group(1)) if m else None


# §validate_config.extract_story_id
def extract_story_id(title: str) -> str:
    """Extract story ID (e.g. US-0001) from an issue title.

    Falls back to a sanitized slug from the title prefix when no
    standard ID pattern is found.
    """
    m = re.match(r"([A-Z]+-\d+)", title)
    if m:
        return m.group(1)
    # Fallback: sanitize the prefix before any colon into a safe slug
    prefix = title.split(":")[0].strip()
    slug = re.sub(r"[^a-zA-Z0-9_-]", "-", prefix).strip("-").lower()
    return slug[:40] if slug else "unknown"


# §validate_config.KANBAN_STATES
KANBAN_STATES = frozenset(("todo", "design", "dev", "review", "integration", "done"))

# BH-016: Ordered progression for picking most advanced state
_KANBAN_ORDER = ("todo", "design", "dev", "review", "integration", "done")


# §validate_config.kanban_from_labels
def kanban_from_labels(issue: dict) -> str:
    """Derive kanban status from an issue's labels.

    Returns a valid kanban state. Invalid label values are ignored.
    BH-016: When multiple kanban labels exist, returns the most advanced state.
    """
    fallback = "done" if issue.get("state") == "closed" else "todo"
    best = -1
    for label in issue.get("labels", []):
        # BH19-003: Handle None/int/bool labels safely (malformed API responses)
        if isinstance(label, str):
            name = label
        elif isinstance(label, dict):
            name = label.get("name", "")
        else:
            continue
        if name.startswith("kanban:"):
            state = name.split(":", 1)[1]
            if state in KANBAN_STATES:
                idx = _KANBAN_ORDER.index(state)
                if idx > best:
                    best = idx
    return _KANBAN_ORDER[best] if best >= 0 else fallback


# §validate_config.find_milestone
def find_milestone(sprint_num: int) -> dict | None:
    """Find the GitHub milestone matching a sprint number.

    Queries the current repo (via gh CLI's {owner}/{repo} template).
    Returns the milestone dict or None.
    """
    num = int(sprint_num)
    milestones = gh_json([
        "api", "repos/{owner}/{repo}/milestones", "--paginate",
    ])
    if not isinstance(milestones, list):
        return None
    for ms in milestones:
        title = ms.get("title", "")
        # BH-001: Match sprint numbers with optional leading zeros
        # (e.g., "Sprint 07:" matches find_milestone(7))
        if re.match(rf"^Sprint 0*{num}\b", title):
            return ms
    return None


# §validate_config.list_milestone_issues
def list_milestone_issues(milestone_title: str) -> list[dict]:
    """Fetch all issues for a milestone (all states). Shared by sync/burndown.

    BH-014: Uses --limit 1000 and warns loudly when limit is hit.
    """
    try:
        issues = gh_json([
            "issue", "list", "--milestone", milestone_title, "--state", "all",
            "--json", "number,title,state,labels,closedAt,body", "--limit", "1000",
        ])
    except RuntimeError as exc:
        print(f"Warning: failed to fetch issues for milestone "
              f"'{milestone_title}': {exc}", file=sys.stderr)
        return []
    if not isinstance(issues, list):
        return []
    warn_if_at_limit(issues, 1000)
    return issues


# §validate_config.warn_if_at_limit
def warn_if_at_limit(results: list, limit: int = 500) -> bool:
    """Warn if API results hit the limit, suggesting data may be incomplete.

    Returns True if the limit was hit, False otherwise.
    """
    if len(results) >= limit:
        print(f"Warning: query returned {limit} results (the limit). "
              f"Data may be incomplete for projects with more items.",
              file=sys.stderr)
        return True
    return False


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
