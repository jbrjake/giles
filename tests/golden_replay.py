"""Golden-run replayer: loads recorded snapshots and asserts consistency.

Compares recorded golden state against current FakeGitHub / file-tree
state. All assert methods return a list of difference strings; an empty
list means the states match.

Usage:
    replayer = GoldenReplayer()
    if replayer.has_recordings():
        snap = replayer.load_snapshot("after_bootstrap")
        diffs = replayer.assert_labels_match(snap, fake_gh)
        assert not diffs, diffs
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fake_github import FakeGitHub

GOLDEN_DIR = Path(__file__).resolve().parent / "golden" / "recordings"


class GoldenReplayer:
    """Load and compare golden-run recordings."""

    def __init__(self, golden_dir: Path | None = None) -> None:
        self.golden_dir = golden_dir if golden_dir is not None else GOLDEN_DIR

    def has_recordings(self) -> bool:
        """Check whether a manifest.json exists in the golden directory."""
        return (self.golden_dir / "manifest.json").is_file()

    def load_manifest(self) -> dict:
        """Load and return the manifest.json contents."""
        manifest_path = self.golden_dir / "manifest.json"
        return json.loads(manifest_path.read_text(encoding="utf-8"))

    def load_snapshot(self, phase_name: str) -> dict:
        """Load a single phase snapshot by name."""
        snap_path = self.golden_dir / f"{phase_name}.json"
        return json.loads(snap_path.read_text(encoding="utf-8"))

    def assert_labels_match(
        self, snapshot: dict, fake_gh: "FakeGitHub"
    ) -> list[str]:
        """Compare label names AND colors between snapshot and current state.

        BH-003: Previously only compared names. Now also checks colors so
        a regression that changes label colors is caught.
        """
        diffs: list[str] = []
        gh_state = snapshot.get("github_state", {})
        recorded_labels = gh_state.get("labels", {})
        recorded_names = set(recorded_labels.keys())
        current_names = set(fake_gh.labels.keys())

        missing = recorded_names - current_names
        extra = current_names - recorded_names

        if missing:
            diffs.append(
                f"Labels in recording but not current: {sorted(missing)}"
            )
        if extra:
            diffs.append(
                f"Labels in current but not recording: {sorted(extra)}"
            )

        # Compare colors for labels present in both
        for name in sorted(recorded_names & current_names):
            rec_color = recorded_labels[name].get("color", "")
            cur_data = fake_gh.labels.get(name, {})
            cur_color = cur_data.get("color", "")
            if rec_color and cur_color and rec_color != cur_color:
                diffs.append(
                    f"Label '{name}' color mismatch: "
                    f"recorded={rec_color}, current={cur_color}"
                )

        return diffs

    def assert_milestones_match(
        self, snapshot: dict, fake_gh: "FakeGitHub"
    ) -> list[str]:
        """Compare milestone titles AND descriptions between snapshot and current state.

        BH-003: Previously only compared titles. Now also checks descriptions.
        """
        diffs: list[str] = []
        gh_state = snapshot.get("github_state", {})

        recorded = sorted(
            gh_state.get("milestones", []),
            key=lambda m: m.get("title", ""),
        )
        current = sorted(
            fake_gh.milestones,
            key=lambda m: m.get("title", ""),
        )

        recorded_titles = [m.get("title", "") for m in recorded]
        current_titles = [m.get("title", "") for m in current]

        if recorded_titles != current_titles:
            diffs.append(
                f"Milestone mismatch: recorded={recorded_titles}, "
                f"current={current_titles}"
            )

        # Compare descriptions for milestones present in both
        for rec_ms, cur_ms in zip(recorded, current):
            if rec_ms.get("title") != cur_ms.get("title"):
                continue
            rec_desc = rec_ms.get("description", "")
            cur_desc = cur_ms.get("description", "")
            if rec_desc and rec_desc != cur_desc:
                diffs.append(
                    f"Milestone '{rec_ms['title']}' description mismatch"
                )

        return diffs

    def assert_issues_match(
        self, snapshot: dict, fake_gh: "FakeGitHub"
    ) -> list[str]:
        """Compare issue titles, label sets, and milestones between snapshot and current.

        BH-003: Previously only compared titles. Now also checks that each
        issue has the same labels and milestone assignment.
        """
        diffs: list[str] = []
        gh_state = snapshot.get("github_state", {})

        recorded_issues = gh_state.get("issues", [])
        current_issues = fake_gh.issues

        if len(recorded_issues) != len(current_issues):
            diffs.append(
                f"Issue count mismatch: recorded={len(recorded_issues)}, "
                f"current={len(current_issues)}"
            )

        recorded_titles = sorted(
            iss.get("title", "") for iss in recorded_issues
        )
        current_titles = sorted(
            iss.get("title", "") for iss in current_issues
        )

        missing = set(recorded_titles) - set(current_titles)
        extra = set(current_titles) - set(recorded_titles)

        if missing:
            diffs.append(
                f"Issues in recording but not current: {sorted(missing)}"
            )
        if extra:
            diffs.append(
                f"Issues in current but not recording: {sorted(extra)}"
            )

        # Compare labels and milestones for issues present in both
        rec_by_title = {i.get("title", ""): i for i in recorded_issues}
        cur_by_title = {i.get("title", ""): i for i in current_issues}
        for title in sorted(set(rec_by_title) & set(cur_by_title)):
            rec = rec_by_title[title]
            cur = cur_by_title[title]
            rec_labels = sorted(
                l.get("name", "") if isinstance(l, dict) else l
                for l in rec.get("labels", [])
            )
            cur_labels = sorted(
                l.get("name", "") if isinstance(l, dict) else l
                for l in cur.get("labels", [])
            )
            if rec_labels != cur_labels:
                diffs.append(
                    f"Issue '{title}' label mismatch: "
                    f"recorded={rec_labels}, current={cur_labels}"
                )
            rec_ms = (rec.get("milestone") or {}).get("title", "")
            cur_ms = (cur.get("milestone") or {}).get("title", "")
            if rec_ms != cur_ms:
                diffs.append(
                    f"Issue '{title}' milestone mismatch: "
                    f"recorded={rec_ms!r}, current={cur_ms!r}"
                )

        return diffs

    def assert_files_match(
        self, snapshot: dict, project_root: Path
    ) -> list[str]:
        """Compare file tree between snapshot and current project root.

        Returns a list of difference descriptions (empty means match).
        """
        diffs: list[str] = []
        recorded_files = set(snapshot.get("file_tree", {}).keys())

        # Rebuild current file tree using the same dirs the recorder checks
        current_files: set[str] = set()
        dirs_to_check = [
            project_root / "sprint-config",
            project_root / "sprints",
            project_root / "docs" / "sprints",
            project_root / "docs" / "dev-team" / "sprints",
        ]
        for dir_path in dirs_to_check:
            if not dir_path.is_dir():
                continue
            for file_path in sorted(dir_path.rglob("*")):
                if file_path.is_file():
                    rel = str(file_path.relative_to(project_root))
                    current_files.add(rel)

        missing = recorded_files - current_files
        extra = current_files - recorded_files

        if missing:
            diffs.append(
                f"Files in recording but not on disk: {sorted(missing)}"
            )
        if extra:
            diffs.append(
                f"Files on disk but not in recording: {sorted(extra)}"
            )

        # Compare file contents for files that exist in both sets
        recorded_tree = snapshot.get("file_tree", {})
        common_files = recorded_files & current_files
        for rel_path in sorted(common_files):
            recorded_content = recorded_tree.get(rel_path, "")
            actual_path = project_root / rel_path
            try:
                actual_content = actual_path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue  # skip unreadable files
            if recorded_content != actual_content:
                diffs.append(
                    f"Content mismatch: {rel_path}"
                )

        return diffs
