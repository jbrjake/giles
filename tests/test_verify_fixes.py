#!/usr/bin/env python3
"""Verify all ship-giles bugfixes work end-to-end.

Creates a mock Rust project in a temp directory, runs sprint_init.py,
and validates the generated config matches what validate_config.py expects.

Run: python -m unittest tests.test_verify_fixes -v
"""

import os
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

# Ensure scripts/ is on the path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from validate_config import parse_simple_toml, validate_project, _parse_team_index, ConfigError, load_config
from sprint_init import ProjectScanner, ConfigGenerator


class MockProject:
    """Create a minimal mock Rust project for testing."""

    def __init__(self, root: Path):
        self.root = root

    def create(self) -> None:
        # Cargo.toml (language detection)
        (self.root / "Cargo.toml").write_text(textwrap.dedent("""\
            [package]
            name = "test-project"
            version = "0.1.0"
            edition = "2021"
        """))

        # Git remote (repo detection)
        (self.root / ".git").mkdir()
        (self.root / ".git" / "config").write_text(textwrap.dedent("""\
            [remote "origin"]
                url = https://github.com/testowner/testrepo.git
                fetch = +refs/heads/*:refs/remotes/origin/*
        """))

        # Persona files — alice and bob use next-line role format
        docs = self.root / "docs" / "dev-team"
        docs.mkdir(parents=True)
        for name, role in [("alice", "Senior Engineer"),
                           ("bob", "Systems Architect")]:
            (docs / f"{name}.md").write_text(textwrap.dedent(f"""\
                # {name.title()}

                ## Role
                {role}

                ## Voice
                Direct and technical.

                ## Domain
                Backend systems.

                ## Background
                10 years experience.

                ## Review Focus
                Performance and correctness.
            """))

        # carol uses inline role format: "## Role: QA Lead"
        (docs / "carol.md").write_text(textwrap.dedent("""\
            # Carol

            ## Role: QA Lead

            ## Voice
            Thorough and cautious.

            ## Domain
            Testing and validation.

            ## Background
            8 years in QA.

            ## Review Focus
            Test coverage and edge cases.
        """))

        # Backlog with milestone
        backlog = self.root / "docs" / "backlog"
        backlog.mkdir(parents=True)
        milestones = backlog / "milestones"
        milestones.mkdir()
        (milestones / "milestone-1.md").write_text(textwrap.dedent("""\
            # Sprint 1: Walking Skeleton

            ### Sprint 1: Foundation

            | US-0101 | Basic setup | S01 | 3 | P0 |
            | US-0102 | Core feature | S01 | 5 | P1 |
        """))

        # Rules and dev guide
        (self.root / "RULES.md").write_text("# Rules\nNo panics in production.\n")
        (self.root / "DEVELOPMENT.md").write_text("# Development\nUse TDD.\n")


class TestConfigGeneration(unittest.TestCase):
    """Verify sprint_init.py generates config that passes validation."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="giles-verify-")
        self.root = Path(self.tmpdir)
        mock = MockProject(self.root)
        mock.create()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _generate(self) -> ConfigGenerator:
        scanner = ProjectScanner(self.root)
        scan = scanner.scan()
        gen = ConfigGenerator(scan)
        gen.generate()
        return gen

    def test_generated_toml_has_required_keys(self):
        """Bug 1: Generated TOML must have [ci] check_commands,
        [ci] build_command, and [paths] section."""
        self._generate()
        toml_path = self.root / "sprint-config" / "project.toml"
        self.assertTrue(toml_path.exists(), "project.toml not generated")
        config = parse_simple_toml(toml_path.read_text())

        # Required sections
        for section in ("project", "paths", "ci"):
            self.assertIn(section, config, f"Missing [{section}] section")

        # Required keys
        self.assertIn("name", config["project"])
        self.assertIn("repo", config["project"])
        self.assertIn("language", config["project"])
        self.assertIn("team_dir", config["paths"])
        self.assertIn("backlog_dir", config["paths"])
        self.assertIn("sprints_dir", config["paths"])
        self.assertIn("check_commands", config["ci"])
        self.assertIn("build_command", config["ci"])

    def test_generated_toml_no_wrong_keys(self):
        """Bug 1: Must NOT have old [build] section or [ci] steps key."""
        self._generate()
        toml_path = self.root / "sprint-config" / "project.toml"
        config = parse_simple_toml(toml_path.read_text())
        self.assertNotIn("build", config, "Old [build] section still present")
        self.assertNotIn("steps", config.get("ci", {}),
                         "Old [ci] steps key still present")

    def test_generated_team_index_has_role_column(self):
        """Bug 2: Team INDEX.md must have Name | Role | File columns."""
        self._generate()
        index_path = self.root / "sprint-config" / "team" / "INDEX.md"
        self.assertTrue(index_path.exists(), "team/INDEX.md not generated")
        rows = _parse_team_index(index_path)
        self.assertGreaterEqual(len(rows), 3, "Need at least 3 personas")
        for row in rows:
            self.assertIn("name", row, f"Row missing 'name': {row}")
            self.assertIn("role", row, f"Row missing 'role': {row}")
            self.assertIn("file", row, f"Row missing 'file': {row}")
            self.assertNotEqual(row["role"], "",
                                f"Role is empty for {row.get('name')}")

    def test_generated_team_index_no_confidence_column(self):
        """Bug 2: Confidence column should be gone."""
        self._generate()
        index_path = self.root / "sprint-config" / "team" / "INDEX.md"
        text = index_path.read_text()
        self.assertNotIn("Confidence", text,
                          "Old 'Confidence' column still present")

    def test_generated_config_passes_validation(self):
        """Contract: Generated config must pass validate_project()."""
        self._generate()
        config_dir = str(self.root / "sprint-config")
        ok, errors = validate_project(config_dir)
        self.assertTrue(ok,
                        f"Generated config failed validation: {errors}")

    def test_inferred_role_from_persona(self):
        """Bug 2: Role should be inferred from ## Role heading."""
        self._generate()
        index_path = self.root / "sprint-config" / "team" / "INDEX.md"
        rows = _parse_team_index(index_path)
        roles = {r["name"].lower(): r["role"] for r in rows}
        # Check that at least one role was inferred (not fallback)
        non_fallback = [r for r in roles.values() if r != "Team Member"]
        self.assertTrue(len(non_fallback) > 0,
                        f"No roles inferred, all are fallback: {roles}")


class TestCIGeneration(unittest.TestCase):
    """Verify setup_ci.py generates correct CI YAML."""

    def test_doc_lint_uses_language_extensions(self):
        """Bug 4: Doc lint should use language-appropriate extensions."""
        sys.path.insert(0, str(
            ROOT / "skills" / "sprint-setup" / "scripts"))
        from setup_ci import _docs_lint_job
        # Rust should include .rs
        rust_job = _docs_lint_job("rust")
        self.assertIn(".rs", rust_job)
        # Python should include .py, not .rs
        py_job = _docs_lint_job("python")
        self.assertIn(".py", py_job)
        self.assertNotIn(".rs", py_job)

    def test_no_duplicate_test_job(self):
        """Bug 5: Test command should not appear in both check jobs
        and the test matrix job."""
        sys.path.insert(0, str(
            ROOT / "skills" / "sprint-setup" / "scripts"))
        from setup_ci import generate_ci_yaml
        config = {
            "project": {"language": "rust", "name": "test"},
            "ci": {
                "check_commands": [
                    "cargo fmt --check",
                    "cargo clippy -- -D warnings",
                    "cargo test",
                ],
                "build_command": "cargo build --release",
            },
        }
        yaml = generate_ci_yaml(config)
        # "cargo test" should appear in the test matrix job
        self.assertIn("matrix:", yaml)
        # Count how many jobs run "cargo test" — should be exactly 1
        # (the matrix test job, not also a standalone check job)
        test_run_lines = [l for l in yaml.splitlines()
                          if l.strip().startswith("run: cargo test")]
        self.assertEqual(len(test_run_lines), 1,
                         f"'cargo test' appears {len(test_run_lines)} times "
                         f"as a run command, expected 1")


class TestAgentFrontmatter(unittest.TestCase):
    """Verify agent files have YAML frontmatter."""

    def _check_frontmatter(self, path: Path):
        self.assertTrue(path.exists(), f"{path} does not exist")
        text = path.read_text()
        self.assertTrue(text.startswith("---"),
                        f"{path.name} missing YAML frontmatter")
        end = text.index("---", 3)
        fm = text[3:end]
        self.assertIn("name:", fm, f"{path.name} frontmatter missing 'name'")
        self.assertIn("description:", fm,
                      f"{path.name} frontmatter missing 'description'")

    def test_implementer_has_frontmatter(self):
        agents = ROOT / "skills" / "sprint-run" / "agents"
        self._check_frontmatter(agents / "implementer.md")

    def test_reviewer_has_frontmatter(self):
        agents = ROOT / "skills" / "sprint-run" / "agents"
        self._check_frontmatter(agents / "reviewer.md")


class TestEvalsGeneric(unittest.TestCase):
    """Verify evals don't contain project-specific references."""

    def test_no_hardcoded_project_names(self):
        evals_path = ROOT / "evals" / "evals.json"
        text = evals_path.read_text()
        self.assertNotIn("Dreamcatcher", text,
                          "Evals still reference 'Dreamcatcher'")

    def test_no_hardcoded_persona_names(self):
        evals_path = ROOT / "evals" / "evals.json"
        text = evals_path.read_text()
        self.assertNotIn("Rachel", text,
                          "Evals still reference 'Rachel'")

    def test_no_hardcoded_cargo_commands(self):
        evals_path = ROOT / "evals" / "evals.json"
        text = evals_path.read_text()
        self.assertNotIn("cargo build", text,
                          "Evals still reference 'cargo build'")
        self.assertNotIn("cargo test", text,
                          "Evals still reference 'cargo test'")


class TestLoadConfigRaisesConfigError(unittest.TestCase):
    """P6-16: load_config raises ConfigError, not SystemExit, on bad config."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="giles-p616-")
        self.orig_dir = os.getcwd()
        os.chdir(self.tmpdir)

    def tearDown(self):
        os.chdir(self.orig_dir)
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_missing_config_dir_raises_config_error(self):
        """load_config with nonexistent config dir raises ConfigError."""
        with self.assertRaises(ConfigError):
            load_config("nonexistent-dir")

    def test_config_error_is_value_error(self):
        """ConfigError is a subclass of ValueError for broad catches."""
        with self.assertRaises(ValueError):
            load_config("nonexistent-dir")

    def test_config_error_does_not_raise_system_exit(self):
        """load_config must not call sys.exit."""
        try:
            load_config("nonexistent-dir")
        except SystemExit:
            self.fail("load_config raised SystemExit instead of ConfigError")
        except ConfigError:
            pass  # expected

    def test_config_error_message_includes_details(self):
        """ConfigError message includes the validation error details."""
        with self.assertRaises(ConfigError) as ctx:
            load_config("nonexistent-dir")
        self.assertIn("validation failed", str(ctx.exception).lower())


class TestParseTeamIndexCellCountWarning(unittest.TestCase):
    """P6-22: _parse_team_index warns on mismatched cell count."""

    def test_fewer_cells_prints_warning(self):
        """Row with fewer cells than header triggers a warning on stderr."""
        import io
        from contextlib import redirect_stderr

        tmpdir = tempfile.mkdtemp(prefix="giles-p622-")
        index_path = Path(tmpdir) / "INDEX.md"
        index_path.write_text(
            "| Name | Role | File |\n"
            "|------|------|------|\n"
            "| Alice | Engineer | alice.md |\n"
            "| Bob | Architect |\n",  # only 2 cells, expected 3
            encoding="utf-8",
        )

        buf = io.StringIO()
        with redirect_stderr(buf):
            rows = _parse_team_index(index_path)

        warning_output = buf.getvalue()
        self.assertIn("Warning", warning_output)
        self.assertIn("2 cells", warning_output)
        self.assertIn("expected 3", warning_output)

        # Row should still be parsed (graceful handling)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1].get("name"), "Bob")

        import shutil
        shutil.rmtree(tmpdir, ignore_errors=True)

    def test_correct_cells_no_warning(self):
        """Row with correct cell count does not produce a warning."""
        import io
        from contextlib import redirect_stderr

        tmpdir = tempfile.mkdtemp(prefix="giles-p622-")
        index_path = Path(tmpdir) / "INDEX.md"
        index_path.write_text(
            "| Name | Role | File |\n"
            "|------|------|------|\n"
            "| Alice | Engineer | alice.md |\n",
            encoding="utf-8",
        )

        buf = io.StringIO()
        with redirect_stderr(buf):
            rows = _parse_team_index(index_path)

        self.assertEqual(buf.getvalue(), "")
        self.assertEqual(len(rows), 1)

        import shutil
        shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
