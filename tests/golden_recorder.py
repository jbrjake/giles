"""Golden-run recorder: captures state snapshots during pipeline execution.

Records GitHub state (via FakeGitHub.dump_state()) and file-tree contents
at named phases so they can be replayed later for regression testing.

Usage:
    recorder = GoldenRecorder(project_root, fake_gh)
    recorder.snapshot("after_init")
    recorder.snapshot("after_bootstrap")
    recorder.write_manifest()
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fake_github import FakeGitHub

GOLDEN_DIR = Path(__file__).resolve().parent / "golden" / "recordings"


class GoldenRecorder:
    """Record state snapshots at each pipeline phase."""

    def __init__(self, project_root: Path, fake_gh: "FakeGitHub") -> None:
        self.project_root = project_root
        self.fake_gh = fake_gh
        self.phases: list[str] = []
        self.output_dir = GOLDEN_DIR

    def snapshot(self, phase_name: str) -> Path:
        """Capture GitHub state and file tree, save as JSON.

        Returns the path to the written snapshot file.
        """
        self.output_dir.mkdir(parents=True, exist_ok=True)

        github_state = self.fake_gh.dump_state()
        file_tree = self._capture_files()

        data = {
            "phase": phase_name,
            "github_state": github_state,
            "file_tree": file_tree,
        }

        out_path = self.output_dir / f"{phase_name}.json"
        out_path.write_text(json.dumps(data, indent=2, default=str))
        self.phases.append(phase_name)
        return out_path

    def write_manifest(self) -> Path:
        """Write manifest.json summarizing the recording session.

        Returns the path to the manifest file.
        """
        self.output_dir.mkdir(parents=True, exist_ok=True)

        project_name = self.project_root.name
        manifest = {
            "project": project_name,
            "phases": list(self.phases),
            "total": len(self.phases),
        }

        manifest_path = self.output_dir / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2))
        return manifest_path

    def _capture_files(self) -> dict[str, str]:
        """Capture file contents from sprint-config/ and common tracking dirs.

        Returns a dict mapping relative paths (from project root) to file
        contents. Binary files and files that cannot be decoded are skipped.
        """
        result: dict[str, str] = {}

        dirs_to_capture = [
            self.project_root / "sprint-config",
            self.project_root / "sprints",
            self.project_root / "docs" / "sprints",
            self.project_root / "docs" / "dev-team" / "sprints",
        ]

        for dir_path in dirs_to_capture:
            if not dir_path.is_dir():
                continue
            for file_path in sorted(dir_path.rglob("*")):
                if not file_path.is_file():
                    continue
                # Resolve symlinks for reading but store original relative path
                rel = str(file_path.relative_to(self.project_root))
                try:
                    content = file_path.read_text(encoding="utf-8")
                    result[rel] = content
                except (UnicodeDecodeError, OSError):
                    # Skip binary or unreadable files
                    continue

        return result
