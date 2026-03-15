#!/usr/bin/env python3
"""Auto-detect project structure and generate sprint-config/ directory.

Scans a project root to detect language, repo, CI, team personas, backlog,
and key documentation files. Generates a sprint-config/ directory with
symlinks to existing files, generated index files, or skeleton templates
for anything missing.

No external dependencies — stdlib only.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Import validation for self-check after generation
_SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_SCRIPTS_DIR))
from validate_config import validate_project

EXCLUDED_DIRS = {
    ".git", "node_modules", "target", ".venv", "__pycache__",
    "dist", "build", ".tox", ".mypy_cache", ".pytest_cache",
}

PERSONA_HEADINGS = {"## Role", "## Voice", "## Domain", "## Background",
                    "## Review Focus"}

# §sprint_init.RICH_PERSONA_HEADINGS
RICH_PERSONA_HEADINGS = {"## Origin Story", "## Professional Identity",
                          "## Personality and Quirks", "## Improvisation Notes"}

SKELETONS_DIR = Path(__file__).resolve().parent.parent / "references" / "skeletons"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class Detection:
    value: Any
    evidence: str
    confidence: float  # 0.0–1.0


@dataclass
class ScoredFile:
    path: str           # relative to project root
    confidence: float   # 0.0–1.0
    evidence: str       # what signals were found


@dataclass
# §sprint_init.ScanResult
class ScanResult:
    project_root: str
    language: Detection
    repo: Detection
    ci_commands: Detection        # value is list[str]
    build_command: Detection
    project_name: Detection
    persona_files: list[ScoredFile]
    team_index: Detection         # value is path or None
    backlog_files: list[ScoredFile]
    rules_file: Detection
    dev_guide: Detection
    architecture: Detection
    cheatsheet: Detection
    story_id_pattern: Detection
    binary_path: Detection
    # Optional deep doc detections (None when not present)
    prd_dir: Detection | None = None
    test_plan_dir: Detection | None = None
    sagas_dir: Detection | None = None
    epics_dir: Detection | None = None
    story_map: Detection | None = None
    team_topology: Detection | None = None


# ---------------------------------------------------------------------------
# ProjectScanner
# ---------------------------------------------------------------------------

# §sprint_init.ProjectScanner
class ProjectScanner:
    """Detect project structure from a root directory."""

    LANGUAGE_MARKERS = [
        ("Cargo.toml", "Rust"),
        ("package.json", "Node"),
        ("pyproject.toml", "Python"),
        ("setup.py", "Python"),
        ("go.mod", "Go"),
        ("pom.xml", "Java"),
        ("build.gradle", "Java"),
        ("Gemfile", "Ruby"),
        ("mix.exs", "Elixir"),
    ]

    CI_DEFAULTS: dict[str, list[str]] = {
        "Rust": ["cargo fmt --check", "cargo clippy -- -D warnings",
                 "cargo test"],
        "Node": ["npm ci", "npm run lint", "npm test"],
        "Python": ["ruff check .", "pytest"],
        "Go": ["go vet ./...", "go test ./..."],
        "Java": ["mvn verify"],
    }

    BUILD_DEFAULTS: dict[str, str] = {
        "Rust": "cargo build --release",
        "Node": "npm run build",
        "Python": "python -m build",
        "Go": "go build ./...",
        "Java": "mvn package",
    }

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()

    # -- helpers --

    def _glob_md(self) -> list[Path]:
        """Glob all .md files, excluding noise directories."""
        results: list[Path] = []
        for p in self.root.rglob("*.md"):
            # Only check path parts relative to root, not the full absolute path
            try:
                rel = p.relative_to(self.root)
            except ValueError:
                continue
            if any(part in EXCLUDED_DIRS for part in rel.parts):
                continue
            results.append(p)
        return results

    def _rel(self, p: Path) -> str:
        return str(p.relative_to(self.root))

    def _read_head(self, p: Path, lines: int = 30) -> list[str]:
        """Read first N lines of a file, silently returning [] on error."""
        try:
            with open(p, encoding="utf-8", errors="replace") as f:
                return f.readlines()[:lines]
        except OSError:
            return []

    # -- detectors --

    def detect_language(self) -> Detection:
        for marker, lang in self.LANGUAGE_MARKERS:
            if (self.root / marker).exists():
                return Detection(lang, marker, 1.0)
        return Detection("Unknown", "no manifest found", 0.0)

    def detect_repo(self) -> Detection:
        try:
            result = subprocess.run(
                ["git", "remote", "-v"], capture_output=True, text=True,
                cwd=self.root, timeout=5,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return Detection(None, "git not available", 0.0)
        if result.returncode != 0 or not result.stdout.strip():
            return Detection(None, "no git remote", 0.0)
        # Parse GitHub owner/repo from first fetch line
        m = re.search(r"github\.com[:/]([^/]+/[^/\s]+?)(?:\.git)?\s", result.stdout)
        if m:
            return Detection(m.group(1), f"git remote: {m.group(0).strip()}", 1.0)
        return Detection(None, "remote is not GitHub", 0.2)

    def detect_ci_commands(self, language: str) -> Detection:
        """Infer CI commands from workflow files or language defaults."""
        workflow_dir = self.root / ".github" / "workflows"
        commands: list[str] = []
        if workflow_dir.is_dir():
            for yml in sorted(workflow_dir.iterdir()):
                if yml.suffix not in (".yml", ".yaml"):
                    continue
                commands.extend(self._parse_workflow_runs(yml))
        if commands:
            return Detection(commands, f".github/workflows ({len(commands)} steps)",
                             0.9)
        defaults = self.CI_DEFAULTS.get(language, [])
        if defaults:
            return Detection(defaults, f"language defaults for {language}", 0.5)
        return Detection([], "no CI detected", 0.0)

    def _parse_workflow_runs(self, yml_path: Path) -> list[str]:
        """Extract 'run:' values from a workflow YAML (simple line parser)."""
        runs: list[str] = []
        try:
            with open(yml_path, encoding="utf-8") as f:
                lines = f.readlines()
            i = 0
            while i < len(lines):
                stripped = lines[i].strip()
                # Match both "run: cmd" and "- run: cmd" formats
                run_line = stripped
                if run_line.startswith("- "):
                    run_line = run_line[2:].strip()
                if run_line.startswith("run:"):
                    cmd = run_line[4:].strip()
                    if cmd == "|" or cmd == "":
                        # Multiline run block: collect subsequent indented lines
                        multiline_cmds: list[str] = []
                        i += 1
                        while i < len(lines) and (lines[i].startswith("  ") or lines[i].strip() == ""):
                            line_content = lines[i].strip()
                            if line_content:
                                multiline_cmds.append(line_content)
                            i += 1
                        if multiline_cmds:
                            runs.append("\n".join(multiline_cmds))
                        continue
                    else:
                        runs.append(cmd)
                i += 1
        except OSError:
            pass
        return runs

    def detect_build_command(self, language: str) -> Detection:
        default = self.BUILD_DEFAULTS.get(language)
        if default:
            return Detection(default, f"language default for {language}", 0.5)
        return Detection(None, "no build command inferred", 0.0)

    def detect_project_name(self, language: str) -> Detection:
        parsers: dict[str, tuple[str, Any]] = {
            "Rust": ("Cargo.toml", self._parse_cargo_name),
            "Node": ("package.json", self._parse_json_name),
            "Python": ("pyproject.toml", self._parse_pyproject_name),
        }
        if language in parsers:
            filename, parser = parsers[language]
            path = self.root / filename
            if path.exists():
                name = parser(path)
                if name:
                    return Detection(name, filename, 1.0)
        return Detection(self.root.name, "directory name fallback", 0.3)

    def _parse_cargo_name(self, path: Path) -> str | None:
        in_package = False
        for line in self._read_head(path, 50):
            if line.strip() == "[package]":
                in_package = True
                continue
            if in_package and line.strip().startswith("["):
                break
            if in_package:
                m = re.match(r'name\s*=\s*"([^"]+)"', line.strip())
                if m:
                    return m.group(1)
        return None

    def _parse_json_name(self, path: Path) -> str | None:
        import json as _json
        try:
            with open(path, encoding="utf-8") as f:
                data = _json.load(f)
            return data.get("name")
        except (OSError, ValueError):
            return None

    def _parse_pyproject_name(self, path: Path) -> str | None:
        in_project = False
        for line in self._read_head(path, 50):
            if line.strip() == "[project]":
                in_project = True
                continue
            if in_project and line.strip().startswith("["):
                break
            if in_project:
                m = re.match(r'name\s*=\s*"([^"]+)"', line.strip())
                if m:
                    return m.group(1)
        return None

    def detect_persona_files(self) -> list[ScoredFile]:
        results: list[ScoredFile] = []
        for p in self._glob_md():
            head = self._read_head(p)
            # Check original headings (compact format, 30 lines sufficient)
            hits = [h for h in PERSONA_HEADINGS
                    if any(line.strip().startswith(h) for line in head)]
            if len(hits) >= 3:
                conf = min(len(hits) / len(PERSONA_HEADINGS), 1.0)
                results.append(ScoredFile(
                    self._rel(p), conf,
                    f"matched headings: {', '.join(hits)}",
                ))
                continue
            # Rich personas are longer — read more lines for heading scan
            extended = self._read_head(p, 80)
            rich_hits = [h for h in RICH_PERSONA_HEADINGS
                         if any(line.strip().startswith(h) for line in extended)]
            if len(rich_hits) >= 3:
                conf = min(len(rich_hits) / len(RICH_PERSONA_HEADINGS), 1.0)
                results.append(ScoredFile(
                    self._rel(p), conf,
                    f"matched rich headings: {', '.join(rich_hits)}",
                ))
        results.sort(key=lambda s: s.confidence, reverse=True)
        return results

    def detect_team_index(self) -> Detection:
        for p in self._glob_md():
            head = self._read_head(p, 50)
            for line in head:
                if re.search(r"\|\s*Name\s*\|.*\|\s*Role\s*\|", line, re.I):
                    return Detection(self._rel(p), "table with Name/Role columns",
                                     0.9)
        return Detection(None, "no team index found", 0.0)

    def detect_backlog_files(self) -> list[ScoredFile]:
        """Detect milestone files — require sprint headers to distinguish
        from epics, sagas, PRDs, and other docs that reference stories."""
        story_re = re.compile(r"\|\s*US-\d+|\|\s*Story\s*\|.*\|\s*SP\s*\|",
                              re.I)
        sprint_re = re.compile(r"###?\s*Sprint\s+\d+", re.I)
        results: list[ScoredFile] = []
        for p in self._glob_md():
            try:
                text = p.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            story_hits = len(story_re.findall(text))
            sprint_hits = len(sprint_re.findall(text))
            # Milestone files must have sprint headers; story rows alone
            # could be epics, sagas, test plans, or story maps.
            if sprint_hits >= 1 and story_hits >= 1:
                total = story_hits + sprint_hits
                evidence_parts = [f"{story_hits} story rows",
                                  f"{sprint_hits} sprint headers"]
                conf = min(total / 10, 1.0)
                results.append(ScoredFile(
                    self._rel(p), conf, ", ".join(evidence_parts),
                ))
        results.sort(key=lambda s: s.confidence, reverse=True)
        return results

    def _walk_dirs(self, max_depth: int = 3) -> list[Path]:
        """Walk directories up to max_depth, skipping EXCLUDED_DIRS."""
        result = []
        for dirpath, dirnames, _ in os.walk(self.root):
            depth = Path(dirpath).relative_to(self.root).parts
            if len(depth) >= max_depth:
                dirnames.clear()
                continue
            dirnames[:] = [d for d in dirnames if d not in EXCLUDED_DIRS]
            result.append(Path(dirpath))
        return result

    def detect_prd_dir(self) -> Detection | None:
        """Detect PRD directory."""
        candidates = ["docs/prd", "prd", "docs/requirements"]
        for name in candidates:
            p = self.root / name
            if p.is_dir() and any(p.iterdir()):
                return Detection(name, f"found {name}/", 0.9)
        # Content scan: directories with files containing ## Requirements + ## Design
        for d in self._walk_dirs(max_depth=3):
            md_files = list(d.glob("*.md"))
            if len(md_files) >= 2:
                sample = md_files[0].read_text(encoding="utf-8", errors="replace")[:2000]
                if "## Requirements" in sample and "## Design" in sample:
                    rel = str(d.relative_to(self.root))
                    return Detection(rel, f"PRD content in {d.name}/", 0.7)
        return None

    def detect_test_plan_dir(self) -> Detection | None:
        """Detect test plan directory."""
        candidates = ["docs/test-plan", "test-plan", "docs/testing"]
        for name in candidates:
            p = self.root / name
            if p.is_dir() and any(p.iterdir()):
                return Detection(name, f"found {name}/", 0.9)
        return None

    def detect_sagas_dir(self) -> Detection | None:
        """Detect sagas directory."""
        candidates = ["docs/agile/sagas", "backlog/sagas", "docs/sagas"]
        for name in candidates:
            p = self.root / name
            if p.is_dir() and any(p.iterdir()):
                return Detection(name, f"found {name}/", 0.9)
        return None

    def detect_epics_dir(self) -> Detection | None:
        """Detect epics directory."""
        candidates = ["docs/agile/epics", "backlog/epics", "docs/epics"]
        for name in candidates:
            p = self.root / name
            if p.is_dir() and any(p.iterdir()):
                return Detection(name, f"found {name}/", 0.9)
        return None

    def detect_story_map(self) -> Detection | None:
        """Detect story map index."""
        candidates = [
            "docs/user-stories/story-map/INDEX.md",
            "docs/agile/story-map/INDEX.md",
            "docs/story-map/INDEX.md",
        ]
        for name in candidates:
            p = self.root / name
            if p.is_file():
                return Detection(name, f"found {name}", 0.9)
        return None

    def detect_team_topology(self) -> Detection | None:
        """Detect team topology file."""
        candidates = [
            "docs/team/team-topology.md", "docs/dev-team/team-topology.md",
            "docs/dev-team/who-we-are.md",
        ]
        for name in candidates:
            p = self.root / name
            if p.is_file():
                return Detection(name, f"found {name}", 0.9)
        return None

    def _find_first(self, *candidates: str) -> Detection:
        """Return the first existing file from a list of candidates."""
        for name in candidates:
            if (self.root / name).exists():
                return Detection(name, f"found {name}", 1.0)
        return Detection(None, f"none of {', '.join(candidates)} found", 0.0)

    def detect_rules_file(self) -> Detection:
        return self._find_first("RULES.md", "CONVENTIONS.md", "CONTRIBUTING.md")

    def detect_dev_guide(self) -> Detection:
        return self._find_first("DEVELOPMENT.md", "CONTRIBUTING.md", "HACKING.md")

    def detect_architecture(self) -> Detection:
        return self._find_first("ARCHITECTURE.md", "docs/architecture.md",
                                "DESIGN.md")

    def detect_cheatsheet(self) -> Detection:
        return self._find_first("CHEATSHEET.md", "docs/INDEX.md")

    def detect_story_id_pattern(self, backlog_files: list[ScoredFile]) -> Detection:
        patterns = re.compile(r"(US-\d{4}|[A-Z]{2,10}-\d+|#\d+)")
        counts: dict[str, int] = {}
        for sf in backlog_files:
            try:
                text = (self.root / sf.path).read_text(
                    encoding="utf-8", errors="replace")
            except OSError:
                continue
            for m in patterns.findall(text):
                # Normalize to the prefix pattern
                prefix = re.match(r"([A-Z#]+-?)", m)
                key = f"{prefix.group(1)}NNNN" if prefix else m
                counts[key] = counts.get(key, 0) + 1
        if counts:
            best = max(counts, key=lambda k: counts[k])
            return Detection(best, f"{counts[best]} occurrences", 0.8)
        return Detection(None, "no story IDs found", 0.0)

    def detect_binary_path(self, language: str) -> Detection:
        if language == "Rust":
            return Detection("target/release/<name>",
                             "Rust convention", 0.5)
        if language == "Go":
            return Detection("./<name>", "Go convention", 0.5)
        return Detection(None, "not applicable", 0.0)

    # -- full scan --

    def scan(self) -> ScanResult:
        lang = self.detect_language()
        backlog = self.detect_backlog_files()
        result = ScanResult(
            project_root=str(self.root),
            language=lang,
            repo=self.detect_repo(),
            ci_commands=self.detect_ci_commands(lang.value),
            build_command=self.detect_build_command(lang.value),
            project_name=self.detect_project_name(lang.value),
            persona_files=self.detect_persona_files(),
            team_index=self.detect_team_index(),
            backlog_files=backlog,
            rules_file=self.detect_rules_file(),
            dev_guide=self.detect_dev_guide(),
            architecture=self.detect_architecture(),
            cheatsheet=self.detect_cheatsheet(),
            story_id_pattern=self.detect_story_id_pattern(backlog),
            binary_path=self.detect_binary_path(lang.value),
        )
        # Deep doc detection (optional)
        result.prd_dir = self.detect_prd_dir()
        result.test_plan_dir = self.detect_test_plan_dir()
        result.sagas_dir = self.detect_sagas_dir()
        result.epics_dir = self.detect_epics_dir()
        result.story_map = self.detect_story_map()
        result.team_topology = self.detect_team_topology()
        return result


# ---------------------------------------------------------------------------
# ConfigGenerator
# ---------------------------------------------------------------------------

# §sprint_init.ConfigGenerator
class ConfigGenerator:
    """Generate sprint-config/ from scan results."""

    def __init__(self, scan: ScanResult) -> None:
        self.scan = scan
        self.root = Path(scan.project_root)
        self.config_dir = self.root / "sprint-config"
        self.created: list[str] = []
        self.skipped: list[str] = []

    # -- helpers --

    def _ensure_dir(self, d: Path) -> None:
        d.mkdir(parents=True, exist_ok=True)

    def _write(self, rel_path: str, content: str) -> None:
        target = self.config_dir / rel_path
        self._ensure_dir(target.parent)
        target.write_text(content, encoding="utf-8")
        self.created.append(f"  generated  {rel_path}")

    def _symlink(self, link_rel: str, target_rel: str) -> None:
        """Create a relative symlink from sprint-config/link_rel -> target."""
        link_path = self.config_dir / link_rel
        self._ensure_dir(link_path.parent)
        target_abs = self.root / target_rel
        if not target_abs.exists():
            self.skipped.append(f"  target missing: {target_rel}")
            return
        rel = os.path.relpath(target_abs, link_path.parent)
        if link_path.is_symlink() or link_path.exists():
            link_path.unlink()
        link_path.symlink_to(rel)
        self.created.append(f"  symlinked  {link_rel} -> {target_rel}")

    def _copy_skeleton(self, skeleton_name: str, dest_rel: str) -> None:
        src = SKELETONS_DIR / skeleton_name
        target = self.config_dir / dest_rel
        self._ensure_dir(target.parent)
        if src.exists():
            target.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
            self.created.append(f"  skeleton   {dest_rel} (from {skeleton_name})")
        else:
            target.write_text(
                f"<!-- TODO: populate {dest_rel} -->\n", encoding="utf-8")
            self.created.append(f"  stub       {dest_rel} (no skeleton available)")

    # -- generators --

    @staticmethod
    def _esc(val: str) -> str:
        """Escape special characters for TOML basic string values."""
        return (str(val)
                .replace('\\', '\\\\')
                .replace('"', '\\"')
                .replace('\n', '\\n')
                .replace('\t', '\\t'))

    def generate_project_toml(self) -> None:
        s = self.scan
        esc = self._esc
        lines = ['# Sprint Process Configuration',
                 '# Generated by sprint-init. Review and customize.',
                 '']

        # [project] — required keys: name, repo, language
        lines.append('[project]')
        lines.append(f'name = "{esc(s.project_name.value or "unknown")}"')
        lines.append(f'language = "{esc(s.language.value)}"')
        # Detect current branch for base_branch default
        try:
            _result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True, text=True, check=True,
                cwd=str(self.root))
            _current_branch = _result.stdout.strip()
        except (subprocess.CalledProcessError, FileNotFoundError):
            _current_branch = "main"
        lines.append(f'base_branch = "{esc(_current_branch)}"')
        if s.repo.value:
            lines.append(f'repo = "{esc(s.repo.value)}"')
        else:
            lines.append('repo = "TODO-owner/repo"')
        if s.story_id_pattern.value:
            lines.append(f'story_id_pattern = "{esc(s.story_id_pattern.value)}"')
        lines.append('')

        # [paths] — required keys: team_dir, backlog_dir, sprints_dir
        lines.append('[paths]')
        lines.append('team_dir = "sprint-config/team"')
        lines.append('backlog_dir = "sprint-config/backlog"')
        lines.append('sprints_dir = "docs/dev-team/sprints"')
        if s.rules_file.value:
            lines.append('rules_file = "sprint-config/rules.md"')
        if s.dev_guide.value:
            lines.append('dev_guide = "sprint-config/development.md"')
        if s.cheatsheet.value:
            lines.append(f'cheatsheet = "{s.cheatsheet.value}"')
        if s.architecture.value:
            lines.append(f'architecture = "{s.architecture.value}"')
        # Optional deep doc paths (only when detected)
        if s.prd_dir and s.prd_dir.value:
            lines.append('prd_dir = "sprint-config/prd"')
        if s.test_plan_dir and s.test_plan_dir.value:
            lines.append('test_plan_dir = "sprint-config/test-plan"')
        if s.sagas_dir and s.sagas_dir.value:
            lines.append('sagas_dir = "sprint-config/backlog/sagas"')
        if s.epics_dir and s.epics_dir.value:
            lines.append('epics_dir = "sprint-config/backlog/epics"')
        if s.story_map and s.story_map.value:
            lines.append('story_map = "sprint-config/backlog/story-map/INDEX.md"')
        if s.team_topology and s.team_topology.value:
            lines.append('team_topology = "sprint-config/team/team-topology.md"')
        lines.append('')

        # [ci] — required keys: check_commands (array), build_command (string)
        lines.append('[ci]')
        lines.append('check_commands = [')
        for cmd in (s.ci_commands.value or []):
            lines.append(f'    "{esc(cmd)}",')
        lines.append(']')
        if s.build_command.value:
            lines.append(f'build_command = "{esc(s.build_command.value)}"')
        else:
            lines.append('build_command = "TODO-build-command"')
        if s.binary_path.value:
            name = s.project_name.value or "app"
            lines.append(
                f'binary_path = "{s.binary_path.value.replace("<name>", name)}"')
        lines.append('')

        # [conventions] — optional but useful
        lines.append('[conventions]')
        lines.append('branch_pattern = "sprint-{N}/US-{ID}-{slug}"')
        lines.append('commit_style = "conventional"')
        lines.append('')

        self._write("project.toml", "\n".join(lines))

    def _infer_role(self, persona_path: str) -> str:
        """Infer a persona's role from their file's ## Role heading."""
        full = self.root / persona_path
        if not full.is_file():
            return "Team Member"
        try:
            text = full.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return "Team Member"
        in_role = False
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("## Role"):
                in_role = True
                # Check if role is on the same line: ## Role: Senior Engineer
                after = stripped[len("## Role"):].lstrip(":").strip()
                if after:
                    return after
                continue
            if in_role:
                if stripped.startswith("#"):
                    break
                if stripped:
                    return stripped
        return "Team Member"

    def generate_team(self) -> None:
        # Filter out any user-provided "giles" persona — Giles is plugin-managed
        personas = [sf for sf in self.scan.persona_files
                    if Path(sf.path).stem.lower() != "giles"]
        if not personas:
            self._copy_skeleton("team-index.md.tmpl", "team/INDEX.md")
            self._inject_giles()
            return
        # Generate symlinks
        for sf in personas:
            name = Path(sf.path).stem
            self._symlink(f"team/{name}.md", sf.path)
        # Generate INDEX with Name | Role | File columns
        rows = ["# Team Index", "",
                "| Name | Role | File |",
                "|------|------|------|"]
        for sf in personas:
            name = Path(sf.path).stem.replace("-", " ").replace("_", " ").title()
            role = self._infer_role(sf.path)
            filename = Path(sf.path).stem + ".md"
            rows.append(f"| {name} | {role} | {filename} |")
        rows.append("| Giles | Scrum Master / Facilitator | giles.md |")
        rows.append("")
        self._write("team/INDEX.md", "\n".join(rows))
        self._inject_giles()

    def _inject_giles(self) -> None:
        """Copy Giles persona skeleton into sprint-config/team/.

        Giles is plugin-owned (not user-authored), so he is copied rather
        than symlinked.  This means teardown will prompt before deleting
        him, which is the correct behavior for plugin-injected content.

        On re-run, a user-customized giles.md (regular file, not symlink)
        is preserved to avoid overwriting manual edits.
        """
        dest = self.config_dir / "team" / "giles.md"
        if dest.is_symlink():
            dest.unlink()
        elif dest.exists():
            self.skipped.append("  preserved  team/giles.md (user-customized)")
            return
        self._copy_skeleton("giles.md.tmpl", "team/giles.md")

    def generate_backlog(self) -> None:
        files = self.scan.backlog_files
        if not files:
            self._copy_skeleton("backlog-index.md.tmpl", "backlog/INDEX.md")
            return
        for sf in files:
            name = Path(sf.path).stem
            self._symlink(f"backlog/milestones/{name}.md", sf.path)
        rows = ["# Backlog Index", "",
                "| File | Signals | Confidence |",
                "|------|---------|------------|"]
        for sf in files:
            rows.append(f"| [{sf.path}]({sf.path}) | {sf.evidence} "
                        f"| {sf.confidence:.0%} |")
        rows.append("")
        self._write("backlog/INDEX.md", "\n".join(rows))

    def generate_doc_symlinks(self) -> None:
        mapping = [
            (self.scan.rules_file, "rules.md", "rules.md.tmpl"),
            (self.scan.dev_guide, "development.md", "development.md.tmpl"),
            (self.scan.architecture, "architecture.md", "architecture.md"),
            (self.scan.cheatsheet, "cheatsheet.md", "cheatsheet.md"),
        ]
        for detection, dest, skeleton in mapping:
            if detection.value:
                self._symlink(dest, detection.value)
            else:
                self._copy_skeleton(skeleton, dest)

        # Deep doc symlinks (directories and files)
        deep_symlinks = [
            (self.scan.prd_dir, "prd"),
            (self.scan.test_plan_dir, "test-plan"),
            (self.scan.sagas_dir, "backlog/sagas"),
            (self.scan.epics_dir, "backlog/epics"),
        ]
        for det, dest in deep_symlinks:
            if det and det.value:
                self._symlink(dest, det.value)

        # Story map (file, not directory — symlink the parent dir)
        if self.scan.story_map and self.scan.story_map.value:
            story_map_path = self.scan.story_map.value
            story_map_dir = str(Path(story_map_path).parent)
            self._symlink("backlog/story-map", story_map_dir)

        # Team topology (single file)
        if self.scan.team_topology and self.scan.team_topology.value:
            self._symlink("team/team-topology.md", self.scan.team_topology.value)

    def generate_definition_of_done(self) -> None:
        """Copy DoD skeleton into sprint-config/."""
        self._copy_skeleton("definition-of-done.md.tmpl",
                            "definition-of-done.md")

    def generate_history_dir(self) -> None:
        """Create {team_dir}/history/ directory for Sprint History files."""
        team_dir = self.config_dir / "team"
        history_dir = team_dir / "history"
        self._ensure_dir(history_dir)
        self.created.append("  directory  team/history/")

    def _write_manifest(self) -> None:
        """Write .sprint-init-manifest.json listing all created files.

        Teardown reads this to know exactly which files init created,
        instead of guessing from a hardcoded list.
        """
        # Parse the created list to extract relative paths
        files: list[str] = []
        symlinks: list[str] = []
        directories: list[str] = []
        for entry in self.created:
            entry = entry.strip()
            if entry.startswith("generated"):
                files.append(entry.split(None, 1)[1])
            elif entry.startswith("skeleton"):
                # "skeleton   dest_rel (from skeleton_name)"
                rel = entry.split(None, 1)[1].split(" (")[0]
                files.append(rel)
            elif entry.startswith("stub"):
                rel = entry.split(None, 1)[1].split(" (")[0]
                files.append(rel)
            elif entry.startswith("symlinked"):
                # "symlinked  link_rel -> target_rel"
                rel = entry.split(None, 1)[1].split(" -> ")[0]
                symlinks.append(rel)
            elif entry.startswith("directory"):
                directories.append(entry.split(None, 1)[1])

        manifest = {
            "generated_files": sorted(files),
            "symlinks": sorted(symlinks),
            "directories": sorted(directories),
        }
        manifest_path = self.config_dir / ".sprint-init-manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, indent=2) + "\n", encoding="utf-8",
        )

    def generate(self) -> None:
        self._ensure_dir(self.config_dir)
        self.generate_project_toml()
        self.generate_team()
        self.generate_backlog()
        self.generate_doc_symlinks()
        self.generate_definition_of_done()
        self.generate_history_dir()
        self._write_manifest()


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------

# §sprint_init._indicator
def _indicator(confidence: float) -> str:
    if confidence >= 0.7:
        return "\u2713"   # checkmark
    if confidence >= 0.3:
        return "?"
    return "\u2717"        # ballot x


# §sprint_init.print_scan_results
def print_scan_results(scan: ScanResult) -> None:
    print("\n=== Project Scan Results ===\n")
    detections: list[tuple[str, Detection]] = [
        ("Language", scan.language),
        ("Repository", scan.repo),
        ("Project name", scan.project_name),
        ("Build command", scan.build_command),
        ("CI commands", scan.ci_commands),
        ("Rules file", scan.rules_file),
        ("Dev guide", scan.dev_guide),
        ("Architecture", scan.architecture),
        ("Cheatsheet", scan.cheatsheet),
        ("Story ID pattern", scan.story_id_pattern),
    ]
    for label, det in detections:
        ind = _indicator(det.confidence)
        val = det.value
        if isinstance(val, list):
            val = f"[{len(val)} items]"
        print(f"  {ind} {label:20s} {val}   ({det.evidence})")

    if scan.persona_files:
        print(f"\n  Persona files ({len(scan.persona_files)}):")
        for sf in scan.persona_files:
            print(f"    {_indicator(sf.confidence)} {sf.path}  ({sf.evidence})")
    else:
        print("\n  \u2717 No persona files detected")

    if scan.backlog_files:
        print(f"\n  Backlog files ({len(scan.backlog_files)}):")
        for sf in scan.backlog_files:
            print(f"    {_indicator(sf.confidence)} {sf.path}  ({sf.evidence})")
    else:
        print("\n  \u2717 No backlog files detected")


# §sprint_init.print_generation_summary
def print_generation_summary(gen: ConfigGenerator) -> None:
    print("\n=== Generated sprint-config/ ===\n")
    for line in gen.created:
        print(line)
    if gen.skipped:
        print("\n  Skipped:")
        for line in gen.skipped:
            print(line)
    print(f"\n  Total: {len(gen.created)} items created in sprint-config/")

    # Suggest next steps
    print("\n=== Next Steps ===\n")
    suggestions = []
    s = gen.scan
    if s.language.confidence == 0.0:
        suggestions.append(
            "Set [project] language in sprint-config/project.toml manually.")
    if not s.persona_files:
        suggestions.append(
            "Add team persona files or populate sprint-config/team/INDEX.md.")
    if not s.backlog_files:
        suggestions.append(
            "Add backlog/sprint files or populate sprint-config/backlog/INDEX.md.")
    if s.rules_file.confidence == 0.0:
        suggestions.append(
            "Create RULES.md or edit sprint-config/rules.md skeleton.")
    if s.dev_guide.confidence == 0.0:
        suggestions.append(
            "Create DEVELOPMENT.md or edit sprint-config/development.md skeleton.")
    if suggestions:
        for i, sug in enumerate(suggestions, 1):
            print(f"  {i}. {sug}")
    else:
        print("  All detections high confidence. Review sprint-config/ and adjust.")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

# §sprint_init.main
def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] in ("-h", "--help"):
        print(__doc__.strip())
        sys.exit(0)
    root = sys.argv[1] if len(sys.argv) > 1 else "."
    root = os.path.abspath(root)

    if not os.path.isdir(root):
        print(f"Error: {root} is not a directory.")
        sys.exit(1)

    print(f"Scanning {root} ...")
    scanner = ProjectScanner(root)
    scan = scanner.scan()
    print_scan_results(scan)

    gen = ConfigGenerator(scan)
    gen.generate()
    print_generation_summary(gen)

    # Self-validate generated config
    print("\n=== Validating Generated Config ===\n")
    ok, errors = validate_project(str(gen.config_dir))
    if ok:
        print("  Self-validation passed.")
    else:
        print("  Self-validation FAILED. This is a bug in sprint_init.py:")
        for err in errors:
            print(f"    x {err}")
        print()
        print("  The generated config does not pass validate_config.py.")
        print("  Please file a bug report.")
        sys.exit(1)


if __name__ == "__main__":
    main()
