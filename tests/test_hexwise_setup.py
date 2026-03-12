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
from validate_config import load_config, parse_simple_toml, validate_project  # noqa: E402
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

    def test_optional_paths_present(self):
        """Optional doc paths return actual Paths when configured."""
        from validate_config import (
            get_prd_dir, get_test_plan_dir, get_sagas_dir,
            get_epics_dir, get_story_map,
        )
        config = load_config("sprint-config")
        # Hexwise now has deep docs — these should be detected and configured
        assert get_prd_dir(config) is not None
        assert get_test_plan_dir(config) is not None
        assert get_sagas_dir(config) is not None
        assert get_epics_dir(config) is not None
        assert get_story_map(config) is not None

    def test_scanner_detects_hexwise_deep_docs(self):
        """Scanner detects PRDs, test plan, sagas, epics in extended Hexwise."""
        scanner = ProjectScanner(self.project_dir)
        result = scanner.scan()
        assert result.prd_dir is not None
        assert result.test_plan_dir is not None
        assert result.sagas_dir is not None
        assert result.epics_dir is not None
        assert result.story_map is not None

    def test_config_generator_includes_optional_paths(self):
        """Generated project.toml includes optional paths when deep docs detected."""
        config = load_config("sprint-config")
        assert config["paths"].get("prd_dir") is not None
        assert config["paths"].get("sagas_dir") is not None
        assert config["paths"].get("epics_dir") is not None

    def test_populate_issues_parses_epic_stories(self):
        """populate_issues extracts stories from epic detail blocks."""
        from validate_config import get_milestones
        config = load_config("sprint-config")
        milestones = get_milestones(config)
        stories = populate_issues.parse_milestone_stories(milestones, config)
        stories = populate_issues.enrich_from_epics(stories, config)
        # Find a known story
        story_ids = {s.story_id for s in stories}
        assert "US-0101" in story_ids
        # Check enrichment worked
        us0101 = next(s for s in stories if s.story_id == "US-0101")
        assert us0101.epic != ""
        assert len(us0101.acceptance_criteria) >= 2

    def test_parse_detail_block_story(self):
        """Parser extracts stories from detail block format in epics."""
        epic_content = '''
### US-0101: Parse hex string

| Field | Value |
|-------|-------|
| Story Points | 3 |
| Priority | P0 |
| Saga | S01 |
| Epic | E-0101 |
| Blocked By | — |
| Blocks | US-0102 |
| Test Cases | TC-PAR-001, GP-001 |

**As a** CLI user, **I want** to pass a hex color code **so that** I can see its RGB breakdown.

**Acceptance Criteria:**
- [ ] `AC-01`: Input `#FF5733` returns `R:255 G:87 B:51`
- [ ] `AC-02`: Handles with/without `#` prefix

**Tasks:**
- [ ] `T-0101-01`: Validate hex input (1 SP)
- [ ] `T-0101-02`: Convert to RGB (2 SP)
'''
        stories = populate_issues.parse_detail_blocks(epic_content, sprint=1, source_file="test.md")
        assert len(stories) == 1
        s = stories[0]
        assert s.story_id == "US-0101"
        assert s.title == "Parse hex string"
        assert s.sp == 3
        assert s.priority == "P0"
        assert s.epic == "E-0101"
        assert s.blocks == "US-0102"
        assert s.test_cases == "TC-PAR-001, GP-001"
        assert "CLI user" in s.user_story
        assert len(s.acceptance_criteria) == 2


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
        self.assertEqual(len(self.fake_gh.milestones), 3, "Should have 3 milestones")
        self.assertEqual(len(self.fake_gh.issues), 17, "Should have 17 issues (stories)")

        # Verify persona labels exist
        persona_labels = [l for l in self.fake_gh.labels if l.startswith("persona:")]
        self.assertEqual(len(persona_labels), 3, "Should have 3 persona labels")

        # Verify stories have correct IDs (all 17 across 3 milestones)
        issue_titles = [iss["title"] for iss in self.fake_gh.issues]
        for sid in ("US-0101", "US-0102", "US-0103", "US-0104",
                     "US-0105", "US-0106", "US-0107", "US-0108",
                     "US-0201", "US-0202", "US-0203", "US-0204",
                     "US-0205", "US-0206", "US-0207", "US-0208",
                     "US-0209"):
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
