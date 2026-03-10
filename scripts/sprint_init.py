#!/usr/bin/env python3
"""Auto-detect project structure and generate sprint-config/ directory.

Scans a project root to detect language, repo, CI, team personas, backlog,
and key documentation files. Generates a sprint-config/ directory with
symlinks to existing files, generated index files, or skeleton templates
for anything missing.

No external dependencies — stdlib only.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

EXCLUDED_DIRS = {
    ".git", "node_modules", "target", ".venv", "__pycache__",
    "dist", "build", ".tox", ".mypy_cache", ".pytest_cache",
}

PERSONA_HEADINGS = {"## Role", "## Voice", "## Domain", "## Background",
                    "## Review Focus"}

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


# ---------------------------------------------------------------------------
# ProjectScanner
# ---------------------------------------------------------------------------

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
            if any(part in EXCLUDED_DIRS for part in p.parts):
                continue
            results.append(p)
        return results

    def _rel(self, p: Path) -> str:
        return str(p.relative_to(self.root))

    def _read_head(self, p: Path, lines: int = 30) -> list[str]:
        """Read first N lines of a file, silently returning [] on error."""
        try:
            with open(p, encoding="utf-8", errors="replace") as f:
                return [next(f) for _ in range(lines)]
        except (StopIteration, OSError):
            pass
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
                for line in f:
                    stripped = line.strip()
                    if stripped.startswith("run:"):
                        cmd = stripped[4:].strip().strip("|").strip()
                        if cmd:
                            runs.append(cmd)
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
            hits = [h for h in PERSONA_HEADINGS
                    if any(line.strip().startswith(h) for line in head)]
            if len(hits) >= 3:
                conf = min(len(hits) / len(PERSONA_HEADINGS), 1.0)
                results.append(ScoredFile(
                    self._rel(p), conf,
                    f"matched headings: {', '.join(hits)}",
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
            total = story_hits + sprint_hits
            if total >= 1:
                evidence_parts = []
                if story_hits:
                    evidence_parts.append(f"{story_hits} story rows")
                if sprint_hits:
                    evidence_parts.append(f"{sprint_hits} sprint headers")
                conf = min(total / 10, 1.0)
                results.append(ScoredFile(
                    self._rel(p), conf, ", ".join(evidence_parts),
                ))
        results.sort(key=lambda s: s.confidence, reverse=True)
        return results

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
        return ScanResult(
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


# ---------------------------------------------------------------------------
# ConfigGenerator
# ---------------------------------------------------------------------------

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

    def generate_project_toml(self) -> None:
        s = self.scan
        lines = ['[project]']
        lines.append(f'name = "{s.project_name.value or "unknown"}"')
        lines.append(f'language = "{s.language.value}"')
        if s.repo.value:
            lines.append(f'repo = "{s.repo.value}"')
        if s.story_id_pattern.value:
            lines.append(f'story_id_pattern = "{s.story_id_pattern.value}"')
        lines.append("")
        lines.append("[build]")
        if s.build_command.value:
            lines.append(f'command = "{s.build_command.value}"')
        if s.binary_path.value:
            name = s.project_name.value or "app"
            lines.append(
                f'binary = "{s.binary_path.value.replace("<name>", name)}"')
        lines.append("")
        lines.append("[ci]")
        lines.append("steps = [")
        for cmd in (s.ci_commands.value or []):
            lines.append(f'    "{cmd}",')
        lines.append("]")
        lines.append("")
        self._write("project.toml", "\n".join(lines))

    def generate_team(self) -> None:
        personas = self.scan.persona_files
        if not personas:
            self._copy_skeleton("team-index.md", "team/INDEX.md")
            return
        # Generate symlinks
        for sf in personas:
            name = Path(sf.path).stem
            self._symlink(f"team/{name}.md", sf.path)
        # Generate INDEX
        rows = ["# Team Index", "",
                "| Name | File | Confidence |",
                "|------|------|------------|"]
        for sf in personas:
            name = Path(sf.path).stem.replace("-", " ").replace("_", " ").title()
            rows.append(f"| {name} | [{sf.path}]({sf.path}) | {sf.confidence:.0%} |")
        rows.append("")
        self._write("team/INDEX.md", "\n".join(rows))

    def generate_backlog(self) -> None:
        files = self.scan.backlog_files
        if not files:
            self._copy_skeleton("backlog-index.md", "backlog/INDEX.md")
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
            (self.scan.rules_file, "rules.md", "rules.md"),
            (self.scan.dev_guide, "development.md", "development.md"),
            (self.scan.architecture, "architecture.md", "architecture.md"),
            (self.scan.cheatsheet, "cheatsheet.md", "cheatsheet.md"),
        ]
        for detection, dest, skeleton in mapping:
            if detection.value:
                self._symlink(dest, detection.value)
            else:
                self._copy_skeleton(skeleton, dest)

    def generate(self) -> None:
        self._ensure_dir(self.config_dir)
        self.generate_project_toml()
        self.generate_team()
        self.generate_backlog()
        self.generate_doc_symlinks()


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------

def _indicator(confidence: float) -> str:
    if confidence >= 0.7:
        return "\u2713"   # checkmark
    if confidence >= 0.3:
        return "?"
    return "\u2717"        # ballot x


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

def main() -> None:
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


if __name__ == "__main__":
    main()
