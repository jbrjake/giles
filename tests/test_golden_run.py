#!/usr/bin/env python3
"""Golden-run test: record or replay the full setup pipeline.

Uses a SINGLE test method that runs all phases sequentially on one
FakeGitHub instance, so state accumulates across phases (labels persist
when milestones are created, milestones persist when issues are created).

First run (or GOLDEN_RECORD=1): runs pipeline, saves golden snapshots.
Subsequent runs: runs pipeline, asserts state matches golden snapshots.

Run: python tests/test_golden_run.py -v
Record: GOLDEN_RECORD=1 python tests/test_golden_run.py -v
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
FIXTURE_DIR = TESTS_DIR / "fixtures" / "hexwise"

sys.path.insert(0, str(REPO_ROOT / "scripts"))
from validate_config import parse_simple_toml, validate_project, get_milestones  # noqa: E402
from sprint_init import ProjectScanner, ConfigGenerator  # noqa: E402

sys.path.insert(0, str(REPO_ROOT / "skills" / "sprint-setup" / "scripts"))
import bootstrap_github  # noqa: E402
import populate_issues  # noqa: E402
import setup_ci  # noqa: E402

sys.path.insert(0, str(TESTS_DIR))
from fake_github import FakeGitHub, make_patched_subprocess  # noqa: E402
from golden_recorder import GoldenRecorder  # noqa: E402
from golden_replay import GoldenReplayer  # noqa: E402

RECORD_MODE = os.environ.get("GOLDEN_RECORD", "") == "1"


class TestGoldenRun(unittest.TestCase):
    """Golden-run: record or replay the full setup pipeline.

    Uses a single test method so FakeGitHub state accumulates across
    phases, matching how the real setup pipeline works.
    """

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="golden-run-")
        self.root = Path(self.tmpdir)
        shutil.copytree(FIXTURE_DIR, self.root / "hexwise")
        self.project = self.root / "hexwise"
        # Init git
        subprocess.run(
            ["git", "init"], cwd=str(self.project),
            capture_output=True, text=True,
        )
        subprocess.run(
            ["git", "remote", "add", "origin",
             "https://github.com/testowner/hexwise.git"],
            cwd=str(self.project), capture_output=True, text=True,
        )
        subprocess.run(
            ["git", "add", "."], cwd=str(self.project),
            capture_output=True, text=True,
        )
        subprocess.run(
            ["git", "-c", "user.name=Test", "-c", "user.email=test@test.com",
             "commit", "-m", "feat: initial"],
            cwd=str(self.project), capture_output=True, text=True,
        )
        self.fake_gh = FakeGitHub()
        self._saved_cwd = os.getcwd()
        os.chdir(self.project)

    def tearDown(self):
        os.chdir(self._saved_cwd)
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _generate_config(self) -> dict:
        scanner = ProjectScanner(self.project)
        scan = scanner.scan()
        gen = ConfigGenerator(scan)
        gen.generate()
        toml_path = self.project / "sprint-config" / "project.toml"
        return parse_simple_toml(toml_path.read_text())

    def _check_or_record(self, recorder, replayer, phase_name, check_fn):
        """Record a snapshot or replay-compare against golden state."""
        if RECORD_MODE:
            recorder.snapshot(phase_name)
        elif replayer.has_recordings():
            snapshot = replayer.load_snapshot(phase_name)
            diffs = check_fn(snapshot)
            self.assertEqual(diffs, [], f"{phase_name} mismatch: {diffs}")
        else:
            self.fail(
                "No golden recordings found. Run with GOLDEN_RECORD=1 to create them."
            )

    def test_golden_full_setup_pipeline(self):
        """Full sequential pipeline: init -> labels -> milestones -> issues -> CI.

        All phases run on the SAME FakeGitHub instance so state accumulates.
        Snapshots capture cumulative state at each checkpoint.
        """
        recorder = GoldenRecorder(self.project, self.fake_gh)
        replayer = GoldenReplayer()

        # Phase 1: sprint_init generates valid config
        config = self._generate_config()
        config_dir = str(self.project / "sprint-config")
        ok, errors = validate_project(config_dir)
        self.assertTrue(ok, f"Config validation failed: {errors}")

        self._check_or_record(
            recorder, replayer, "01-setup-init",
            lambda snap: replayer.assert_files_match(snap, self.project),
        )

        # Phase 2: bootstrap creates labels (cumulative)
        with patch("subprocess.run", make_patched_subprocess(self.fake_gh)):
            bootstrap_github.create_static_labels()
            bootstrap_github.create_persona_labels(config)

        self.assertGreater(len(self.fake_gh.labels), 10)
        self._check_or_record(
            recorder, replayer, "02-setup-labels",
            lambda snap: replayer.assert_labels_match(snap, self.fake_gh),
        )

        # Phase 3: bootstrap creates milestones (cumulative — labels still present)
        with patch("subprocess.run", make_patched_subprocess(self.fake_gh)):
            bootstrap_github.create_milestones_on_github(config)

        self.assertEqual(len(self.fake_gh.milestones), 3)
        self._check_or_record(
            recorder, replayer, "03-setup-milestones",
            lambda snap: replayer.assert_milestones_match(snap, self.fake_gh),
        )

        # Phase 4: populate creates issues (cumulative — labels + milestones present)
        with patch("subprocess.run", make_patched_subprocess(self.fake_gh)):
            milestone_files = get_milestones(config)
            stories = populate_issues.parse_milestone_stories(
                milestone_files, config,
            )
            ms_numbers = {
                ms["title"]: ms["number"]
                for ms in self.fake_gh.milestones
            }
            ms_titles = {}
            for i, mf in enumerate(milestone_files, 1):
                if i <= len(self.fake_gh.milestones):
                    ms_titles[i] = self.fake_gh.milestones[i - 1]["title"]
                else:
                    ms_titles[i] = f"Sprint {i}"

            for story in stories:
                if story.story_id not in populate_issues.get_existing_issues():
                    populate_issues.create_issue(story, ms_numbers, ms_titles)

        self.assertEqual(len(self.fake_gh.issues), 17)
        self._check_or_record(
            recorder, replayer, "04-setup-issues",
            lambda snap: replayer.assert_issues_match(snap, self.fake_gh),
        )

        # Phase 5: CI workflow generation
        yaml_content = setup_ci.generate_ci_yaml(config)
        self.assertIn("cargo test", yaml_content)
        self.assertIn("cargo clippy", yaml_content)

        if RECORD_MODE:
            ci_path = self.project / ".github" / "workflows" / "ci.yml"
            ci_path.parent.mkdir(parents=True, exist_ok=True)
            ci_path.write_text(yaml_content)
            recorder.snapshot("05-setup-ci")
            recorder.write_manifest()
            print("\n=== Golden run recorded. Review tests/golden/recordings/ ===")


if __name__ == "__main__":
    unittest.main()
