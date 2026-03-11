#!/usr/bin/env python3
"""Smoke tests: run sprint_init against the hexwise fixture.

Validates that ProjectScanner correctly detects the Rust project structure
(language, personas, milestones, rules, dev guide) and that ConfigGenerator
produces a sprint-config/ directory that passes validate_project().
"""

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

# Ensure scripts/ and tests/ are importable
_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT / "scripts"))
sys.path.insert(0, str(_REPO_ROOT / "tests"))

from sprint_init import ConfigGenerator, ProjectScanner  # noqa: E402
from validate_config import parse_simple_toml, validate_project  # noqa: E402
from fake_github import FakeGitHub, make_patched_subprocess  # noqa: E402

sys.path.insert(0, str(_REPO_ROOT / "skills" / "sprint-setup" / "scripts"))
import bootstrap_github  # noqa: E402
import populate_issues  # noqa: E402

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "hexwise"


class TestHexwiseSetup(unittest.TestCase):
    """End-to-end tests: scan hexwise fixture -> generate config -> validate."""

    @classmethod
    def setUpClass(cls):
        """Copy fixture to a temp dir, git-init it, and scan."""
        cls._tmpdir_obj = tempfile.TemporaryDirectory()
        cls.project_dir = Path(cls._tmpdir_obj.name) / "hexwise"
        shutil.copytree(FIXTURE_DIR, cls.project_dir)

        # Set up a git repo so detect_repo() can parse the remote
        subprocess.run(
            ["git", "init"], cwd=cls.project_dir,
            capture_output=True, check=True,
        )
        subprocess.run(
            ["git", "remote", "add", "origin",
             "https://github.com/testowner/hexwise.git"],
            cwd=cls.project_dir, capture_output=True, check=True,
        )
        subprocess.run(
            ["git", "add", "."], cwd=cls.project_dir,
            capture_output=True, check=True,
        )
        subprocess.run(
            ["git", "-c", "user.email=test@test.com",
             "-c", "user.name=Test",
             "commit", "-m", "init"],
            cwd=cls.project_dir, capture_output=True, check=True,
        )

        # chdir so ConfigGenerator's relative symlinks work properly
        cls._orig_cwd = os.getcwd()
        os.chdir(cls.project_dir)

        # Scan once — all scanner tests share this result
        scanner = ProjectScanner(cls.project_dir)
        cls.scan = scanner.scan()

        # Generate config once — all config tests share this result
        gen = ConfigGenerator(cls.scan)
        gen.generate()
        cls.config_dir = cls.project_dir / "sprint-config"

    @classmethod
    def tearDownClass(cls):
        os.chdir(cls._orig_cwd)
        cls._tmpdir_obj.cleanup()

    # ------------------------------------------------------------------
    # Scanner tests
    # ------------------------------------------------------------------

    def test_scanner_detects_rust(self):
        self.assertEqual(self.scan.language.value.lower(), "rust")

    def test_scanner_finds_personas(self):
        self.assertGreaterEqual(len(self.scan.persona_files), 3)
        names = {Path(p.path).stem for p in self.scan.persona_files}
        self.assertIn("rusti", names)
        self.assertIn("palette", names)
        self.assertIn("checker", names)

    def test_scanner_finds_milestones(self):
        self.assertGreaterEqual(len(self.scan.backlog_files), 2)

    def test_scanner_finds_rules_and_dev(self):
        self.assertIsNotNone(self.scan.rules_file.value)
        self.assertIsNotNone(self.scan.dev_guide.value)

    # ------------------------------------------------------------------
    # ConfigGenerator / validate tests
    # ------------------------------------------------------------------

    def test_config_generation_succeeds(self):
        ok, errors = validate_project(str(self.config_dir))
        self.assertTrue(ok, f"validate_project failed: {errors}")

    def test_config_has_correct_language(self):
        toml_text = (self.config_dir / "project.toml").read_text()
        config = parse_simple_toml(toml_text)
        # Language may be title-cased ("Rust") in the TOML
        self.assertEqual(config["project"]["language"].lower(), "rust")

    def test_config_has_rust_ci_commands(self):
        toml_text = (self.config_dir / "project.toml").read_text()
        config = parse_simple_toml(toml_text)
        ci_cmds = config["ci"]["check_commands"]
        joined = " ".join(ci_cmds)
        self.assertIn("cargo", joined)

    def test_config_has_three_personas(self):
        index_text = (self.config_dir / "team" / "INDEX.md").read_text()
        index_lower = index_text.lower()
        self.assertIn("rusti", index_lower)
        self.assertIn("palette", index_lower)
        self.assertIn("checker", index_lower)

    def test_config_has_two_milestones(self):
        ms_dir = self.config_dir / "backlog" / "milestones"
        md_files = [f for f in ms_dir.iterdir()
                    if f.is_file() and f.suffix == ".md"]
        self.assertGreaterEqual(len(md_files), 2)

    def test_repo_detection(self):
        toml_text = (self.config_dir / "project.toml").read_text()
        config = parse_simple_toml(toml_text)
        self.assertIn("testowner/hexwise", config["project"]["repo"])


class TestHexwisePipeline(unittest.TestCase):
    """Full pipeline: init -> bootstrap -> populate against hexwise."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="hexwise-pipeline-")
        self.root = Path(self.tmpdir)
        shutil.copytree(FIXTURE_DIR, self.root / "hexwise")
        self.project = self.root / "hexwise"
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

    def test_full_setup_pipeline(self):
        """Init -> labels -> milestones -> issues all succeed."""
        config = self._generate_config()

        with patch("subprocess.run", make_patched_subprocess(self.fake_gh)):
            bootstrap_github.create_static_labels()
            bootstrap_github.create_persona_labels(config)
            bootstrap_github.create_milestones_on_github(config)

            from validate_config import get_milestones
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

            existing = populate_issues.get_existing_issues()
            for story in stories:
                if story.story_id not in existing:
                    populate_issues.create_issue(story, ms_numbers, ms_titles)

        # Verify results
        self.assertGreater(len(self.fake_gh.labels), 10, "Should have many labels")
        self.assertEqual(len(self.fake_gh.milestones), 2, "Should have 2 milestones")
        self.assertEqual(len(self.fake_gh.issues), 6, "Should have 6 issues (stories)")

        # Verify persona labels exist
        persona_labels = [l for l in self.fake_gh.labels if l.startswith("persona:")]
        self.assertEqual(len(persona_labels), 3, "Should have 3 persona labels")

        # Verify stories have correct IDs
        issue_titles = [iss["title"] for iss in self.fake_gh.issues]
        for sid in ("US-0101", "US-0102", "US-0103",
                     "US-0201", "US-0202", "US-0203"):
            self.assertTrue(
                any(sid in t for t in issue_titles),
                f"{sid} not found in {issue_titles}",
            )

    def test_ci_workflow_has_cargo(self):
        """setup_ci generates a workflow with cargo commands for Rust."""
        config = self._generate_config()
        sys.path.insert(0, str(_REPO_ROOT / "skills" / "sprint-setup" / "scripts"))
        from setup_ci import generate_ci_yaml

        yaml_content = generate_ci_yaml(config)
        self.assertIn("cargo", yaml_content)
        self.assertIn("cargo test", yaml_content)
        self.assertIn("cargo clippy", yaml_content)

    def test_ci_workflow_uses_configured_branch(self):
        """setup_ci uses base_branch from config instead of hardcoded main."""
        config = self._generate_config()
        config["project"]["base_branch"] = "develop"
        sys.path.insert(0, str(_REPO_ROOT / "skills" / "sprint-setup" / "scripts"))
        from setup_ci import generate_ci_yaml
        yaml_content = generate_ci_yaml(config)
        self.assertIn("branches: [develop]", yaml_content)
        self.assertNotIn("branches: [main]", yaml_content)

    def test_state_dump(self):
        """FakeGitHub.dump_state() captures full state for golden snapshots."""
        config = self._generate_config()

        with patch("subprocess.run", make_patched_subprocess(self.fake_gh)):
            bootstrap_github.create_static_labels()
            bootstrap_github.create_persona_labels(config)
            bootstrap_github.create_milestones_on_github(config)

        state = self.fake_gh.dump_state()
        self.assertIn("labels", state)
        self.assertIn("milestones", state)
        self.assertGreater(len(state["labels"]), 0)
        self.assertGreater(len(state["milestones"]), 0)


if __name__ == "__main__":
    unittest.main()
