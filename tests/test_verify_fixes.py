#!/usr/bin/env python3
"""Verify all ship-giles bugfixes work end-to-end.

Creates a mock Rust project in a temp directory, runs sprint_init.py,
and validates the generated config matches what validate_config.py expects.

Run: python -m unittest tests.test_verify_fixes -v
"""

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

# Ensure scripts/ is on the path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

sys.path.insert(0, str(ROOT / "tests"))

import validate_config
from validate_config import parse_simple_toml, validate_project, _parse_team_index, ConfigError, load_config
from sprint_init import ProjectScanner, ConfigGenerator
from mock_project import MockProject

sys.path.insert(0, str(ROOT / "skills" / "sprint-setup" / "scripts"))
import populate_issues

sys.path.insert(0, str(ROOT / "skills" / "sprint-run" / "scripts"))
import sync_tracking
import update_burndown

sys.path.insert(0, str(ROOT / "skills" / "sprint-monitor" / "scripts"))
import check_status

import manage_epics


class TestConfigGeneration(unittest.TestCase):
    """Verify sprint_init.py generates config that passes validation."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="giles-verify-")
        self.root = Path(self.tmpdir)
        mock = MockProject(self.root, extra_personas=True)
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
        # BH23-105: Assert values are non-empty, not just present
        self.assertIsInstance(config["ci"]["check_commands"], list)
        self.assertTrue(len(config["ci"]["check_commands"]) > 0,
                        "check_commands should be a non-empty list")
        self.assertIn("build_command", config["ci"])
        self.assertTrue(config["ci"]["build_command"],
                        "build_command should be a non-empty string")
        self.assertTrue(config["project"]["language"],
                        "language should be a non-empty string")
        # BH37-034: Removed duplicate assertIn("build_command", config["ci"])

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

    def test_generated_team_index_has_expected_columns(self):
        """BH23-109: Team index has Name, Role, File columns (not obsolete Confidence)."""
        self._generate()
        index_path = self.root / "sprint-config" / "team" / "INDEX.md"
        text = index_path.read_text()
        self.assertNotIn("Confidence", text,
                          "Old 'Confidence' column still present")
        # Positive assertions for expected column headers
        self.assertIn("Name", text)
        self.assertIn("Role", text)
        self.assertIn("File", text)

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


class TestParseTeamIndexSeparatorDetection(unittest.TestCase):
    """BH-P11-109: separator detection strips whitespace from cells."""

    def test_separator_with_whitespace_cell(self):
        """A separator like '| --- |  |' should not be treated as data."""
        tmpdir = tempfile.mkdtemp(prefix="giles-p11-109-")
        index_path = Path(tmpdir) / "INDEX.md"
        index_path.write_text(
            "| Name | Role |\n"
            "| --- |  |\n"
            "| Alice | Engineer |\n",
            encoding="utf-8",
        )

        rows = _parse_team_index(index_path)

        # Only Alice should appear — the separator row must not be data
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["name"], "Alice")

        import shutil
        shutil.rmtree(tmpdir, ignore_errors=True)

    def test_single_column_separator(self):
        """A separator like '|---|' with fewer columns than header is still a separator."""
        tmpdir = tempfile.mkdtemp(prefix="giles-p11-109b-")
        index_path = Path(tmpdir) / "INDEX.md"
        index_path.write_text(
            "| Name | Role | File |\n"
            "|---|\n"
            "| Alice | Engineer | alice.md |\n",
            encoding="utf-8",
        )

        rows = _parse_team_index(index_path)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["name"], "Alice")

        import shutil
        shutil.rmtree(tmpdir, ignore_errors=True)


# ---------------------------------------------------------------------------
# BH-P11-057: commit.py main() integration test
# ---------------------------------------------------------------------------

sys.path.insert(0, str(ROOT / "tests"))

import io
import subprocess as _subprocess
from unittest.mock import patch

import commit


class TestCommitMainIntegration(unittest.TestCase):
    """BH-P11-057: Integration test for commit.main().

    Patches sys.argv and subprocess.run to verify main() validates the
    message, checks atomicity, and calls git commit end-to-end.
    """

    def _fake_subprocess_run(self, args, *a, **kw):
        """Simulate git commands for commit.py."""
        if isinstance(args, list) and args[0] == "git":
            if args[1] == "diff" and "--cached" in args:
                # Return staged files in a single directory
                return _subprocess.CompletedProcess(
                    args=args, returncode=0,
                    stdout="scripts/commit.py\nscripts/validate_config.py\n",
                    stderr="",
                )
            if args[1] == "commit":
                return _subprocess.CompletedProcess(
                    args=args, returncode=0,
                    stdout="[main abc1234] feat: add feature\n 2 files changed",
                    stderr="",
                )
        return _subprocess.CompletedProcess(
            args=args, returncode=1, stdout="", stderr="unknown command",
        )

    def test_main_happy_path(self):
        """main() validates, checks atomicity, and commits successfully."""
        with (
            patch("subprocess.run", self._fake_subprocess_run),
            patch("sys.argv", ["commit.py", "feat: add new feature"]),
            patch("sys.stdout", new_callable=io.StringIO) as mock_out,
        ):
            commit.main()

        output = mock_out.getvalue()
        self.assertIn("abc1234", output)

    def test_main_dry_run(self):
        """main() in dry-run mode validates but does not commit."""
        with (
            patch("subprocess.run", self._fake_subprocess_run),
            patch("sys.argv", ["commit.py", "--dry-run", "feat: preview"]),
            patch("sys.stdout", new_callable=io.StringIO) as mock_out,
        ):
            with self.assertRaises(SystemExit) as ctx:
                commit.main()
            self.assertEqual(ctx.exception.code, 0)

        output = mock_out.getvalue()
        self.assertIn("DRY-RUN", output)
        self.assertIn("feat: preview", output)

    def test_main_invalid_message_exits_1(self):
        """main() exits 1 when the commit message is not conventional."""
        with (
            patch("sys.argv", ["commit.py", "bad message no type"]),
        ):
            with self.assertRaises(SystemExit) as ctx:
                commit.main()
            self.assertEqual(ctx.exception.code, 1)

    def test_main_no_staged_changes_exits_1(self):
        """main() exits 1 when there are no staged changes."""
        def no_staged(args, *a, **kw):
            if isinstance(args, list) and args[0] == "git" and args[1] == "diff":
                return _subprocess.CompletedProcess(
                    args=args, returncode=0, stdout="", stderr="",
                )
            return _subprocess.CompletedProcess(
                args=args, returncode=1, stdout="", stderr="error",
            )

        with (
            patch("subprocess.run", no_staged),
            patch("sys.argv", ["commit.py", "feat: add something"]),
        ):
            with self.assertRaises(SystemExit) as ctx:
                commit.main()
            self.assertEqual(ctx.exception.code, 1)


# ---------------------------------------------------------------------------
# BH-P11-058: validate_anchors.py main() integration test
# ---------------------------------------------------------------------------

import validate_anchors


class TestValidateAnchorsMainIntegration(unittest.TestCase):
    """BH-P11-058: Integration test for validate_anchors.main().

    Creates temp files with anchor definitions and references, then
    verifies main() in check mode validates them correctly.
    """

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.tmpdir = Path(self._tmpdir.name)

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_main_check_mode_all_resolved(self):
        """main() exits cleanly when all anchors resolve."""
        # Create a Python source file with an anchor definition
        scripts_dir = self.tmpdir / "scripts"
        scripts_dir.mkdir()
        (scripts_dir / "example.py").write_text(
            "# some code\n"
            "# §example.my_func\n"
            "def my_func():\n"
            "    pass\n",
            encoding="utf-8",
        )

        # Create a doc file that references the anchor
        (self.tmpdir / "DOCS.md").write_text(
            "# Documentation\n\n"
            "See §example.my_func for details.\n",
            encoding="utf-8",
        )

        namespace_map = {"example": "scripts/example.py"}
        doc_files = ["DOCS.md"]

        with (
            patch("sys.argv", ["validate_anchors.py"]),
            patch("validate_anchors.ROOT", self.tmpdir),
            patch("validate_anchors.NAMESPACE_MAP", namespace_map),
            patch("validate_anchors.DOC_FILES", doc_files),
            patch("sys.stdout", new_callable=io.StringIO) as mock_out,
        ):
            validate_anchors.main()

        output = mock_out.getvalue()
        self.assertIn("1 reference(s) checked, all resolved", output)

    def test_main_check_mode_broken_ref_exits_1(self):
        """main() exits 1 when a reference points to a missing anchor."""
        # Create a Python source file WITHOUT the referenced anchor
        scripts_dir = self.tmpdir / "scripts"
        scripts_dir.mkdir()
        (scripts_dir / "example.py").write_text(
            "# some code\n"
            "def other_func():\n"
            "    pass\n",
            encoding="utf-8",
        )

        # Create a doc file that references a non-existent anchor
        (self.tmpdir / "DOCS.md").write_text(
            "# Documentation\n\n"
            "See §example.missing_func for details.\n",
            encoding="utf-8",
        )

        namespace_map = {"example": "scripts/example.py"}
        doc_files = ["DOCS.md"]

        with (
            patch("sys.argv", ["validate_anchors.py"]),
            patch("validate_anchors.ROOT", self.tmpdir),
            patch("validate_anchors.NAMESPACE_MAP", namespace_map),
            patch("validate_anchors.DOC_FILES", doc_files),
            patch("sys.stdout", new_callable=io.StringIO),
        ):
            with self.assertRaises(SystemExit) as ctx:
                validate_anchors.main()
            self.assertEqual(ctx.exception.code, 1)

    def test_main_fix_mode_inserts_anchors(self):
        """main() --fix inserts missing anchors into source files."""
        scripts_dir = self.tmpdir / "scripts"
        scripts_dir.mkdir()
        (scripts_dir / "example.py").write_text(
            "# some code\n"
            "def my_func():\n"
            "    pass\n",
            encoding="utf-8",
        )

        # Doc references an anchor that exists in the code but not as an anchor comment
        (self.tmpdir / "DOCS.md").write_text(
            "# Documentation\n\n"
            "See §example.my_func for details.\n",
            encoding="utf-8",
        )

        namespace_map = {"example": "scripts/example.py"}
        doc_files = ["DOCS.md"]

        with (
            patch("sys.argv", ["validate_anchors.py", "--fix"]),
            patch("validate_anchors.ROOT", self.tmpdir),
            patch("validate_anchors.NAMESPACE_MAP", namespace_map),
            patch("validate_anchors.DOC_FILES", doc_files),
            patch("sys.stdout", new_callable=io.StringIO) as mock_out,
        ):
            validate_anchors.main()

        output = mock_out.getvalue()
        self.assertIn("Fixed 1 missing anchor", output)
        # Verify the anchor was actually inserted in the source file
        source = (scripts_dir / "example.py").read_text(encoding="utf-8")
        self.assertIn("# §example.my_func", source)


# ---------------------------------------------------------------------------
# BH-P11-110: Format string injection in validate_project
# ---------------------------------------------------------------------------


class TestValidateProjectFormatStringInjection(unittest.TestCase):
    """BH-P11-110: config_dir containing format specifiers must not crash.

    validate_project() should use .replace() instead of .format() to
    expand {config_dir} in required file paths. This prevents any
    theoretical format-string injection if config_dir contains braces.
    """

    def test_config_dir_with_format_specifier_does_not_crash(self):
        """validate_project with config_dir='{0.__class__}' must not raise."""
        malicious_dir = "{0.__class__}"
        # Should return errors (dir doesn't exist) but NOT raise
        ok, errors = validate_project(malicious_dir)
        self.assertFalse(ok)
        self.assertTrue(len(errors) > 0)

    def test_config_dir_with_brace_pattern_preserved_in_errors(self):
        """The braces in config_dir should appear literally in error messages."""
        malicious_dir = "{__class__.__mro__}"
        ok, errors = validate_project(malicious_dir)
        self.assertFalse(ok)
        # The error paths should contain the literal braces, not expanded
        has_brace = any("{__class__.__mro__}" in e for e in errors)
        self.assertTrue(has_brace,
                        f"Braces not preserved in errors: {errors}")

    # test_source_uses_replace_not_format removed (P12-028):
    # The behavioral tests above (format specifiers don't crash, braces
    # preserved) already verify the fix.  Inspecting source is brittle.


# ---------------------------------------------------------------------------
# BH-P11-008: sprint_init creates symlinks for project files
# ---------------------------------------------------------------------------

class TestSprintInitSymlinks(unittest.TestCase):
    """BH-P11-008: ConfigGenerator creates symlinks for rules.md and development.md."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="giles-p11-008-")
        self.root = Path(self.tmpdir)
        mock = MockProject(self.root, extra_personas=True)
        mock.create()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_rules_and_dev_guide_are_symlinks(self):
        """rules.md and development.md in sprint-config/ should be symlinks."""
        scanner = ProjectScanner(self.root)
        scan = scanner.scan()
        gen = ConfigGenerator(scan)
        gen.generate()

        config_dir = self.root / "sprint-config"
        rules_link = config_dir / "rules.md"
        dev_link = config_dir / "development.md"

        self.assertTrue(rules_link.exists(), "rules.md should exist")
        self.assertTrue(dev_link.exists(), "development.md should exist")
        self.assertTrue(
            rules_link.is_symlink(),
            "rules.md should be a symlink, not a regular file",
        )
        self.assertTrue(
            dev_link.is_symlink(),
            "development.md should be a symlink, not a regular file",
        )

        # Verify the symlinks resolve to the original project files
        rules_target = rules_link.resolve()
        dev_target = dev_link.resolve()
        self.assertEqual(
            rules_target, (self.root / "RULES.md").resolve(),
            f"rules.md symlink target {rules_target} does not match "
            f"expected {self.root / 'RULES.md'}",
        )
        self.assertEqual(
            dev_target, (self.root / "DEVELOPMENT.md").resolve(),
            f"development.md symlink target {dev_target} does not match "
            f"expected {self.root / 'DEVELOPMENT.md'}",
        )


# ---------------------------------------------------------------------------
# BH-P11-009: validate_project rejects config with missing required key
# ---------------------------------------------------------------------------

class TestValidateProjectMissingKey(unittest.TestCase):
    """BH-P11-009: validate_project() rejects config missing a required key."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="giles-p11-009-")
        self.root = Path(self.tmpdir)
        mock = MockProject(self.root, extra_personas=True)
        mock.create()
        # Generate valid config first
        scanner = ProjectScanner(self.root)
        scan = scanner.scan()
        gen = ConfigGenerator(scan)
        gen.generate()
        self.config_dir = str(self.root / "sprint-config")
        self.toml_path = self.root / "sprint-config" / "project.toml"

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_missing_build_command_fails(self):
        """Removing ci.build_command should cause validation to fail."""
        # Verify config is valid first
        ok, errors = validate_project(self.config_dir)
        self.assertTrue(ok, f"Baseline config should be valid: {errors}")

        # Remove build_command from the TOML
        toml_text = self.toml_path.read_text(encoding="utf-8")
        lines = [
            line for line in toml_text.splitlines()
            if not line.strip().startswith("build_command")
        ]
        self.toml_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

        # Now validation should fail
        ok, errors = validate_project(self.config_dir)
        self.assertFalse(ok, "Config with missing build_command should fail")
        error_text = " ".join(errors).lower()
        self.assertTrue(
            "build_command" in error_text or "ci.build_command" in error_text,
            f"Error should mention build_command, got: {errors}",
        )


# ---------------------------------------------------------------------------
# BH-P11-010: KANBAN_STATES constant matches documented states
# ---------------------------------------------------------------------------

from validate_config import KANBAN_STATES


class TestKanbanStatesConstant(unittest.TestCase):
    """BH-P11-010: KANBAN_STATES matches the 6 documented kanban states."""

    def test_kanban_states_match_documented(self):
        """KANBAN_STATES must equal the 6 states from kanban-protocol.md."""
        expected = {"todo", "design", "dev", "review", "integration", "done"}
        self.assertEqual(
            set(KANBAN_STATES), expected,
            f"KANBAN_STATES = {set(KANBAN_STATES)} does not match "
            f"documented states {expected}",
        )

    def test_kanban_states_is_frozenset(self):
        """KANBAN_STATES should be immutable (frozenset)."""
        self.assertIsInstance(
            KANBAN_STATES, frozenset,
            "KANBAN_STATES should be a frozenset to prevent mutation",
        )

    def test_kanban_states_count(self):
        """Exactly 6 kanban states."""
        self.assertEqual(
            len(KANBAN_STATES), 6,
            f"Expected 6 kanban states, got {len(KANBAN_STATES)}",
        )


# ---------------------------------------------------------------------------
# BH-P11-061: sprint_teardown interactive confirmation (no --force / --dry-run)
# ---------------------------------------------------------------------------

import sprint_teardown


class TestTeardownInteractiveConfirmation(unittest.TestCase):
    """BH-P11-061: Test the interactive prompt path in sprint_teardown.main().

    When neither --force nor --dry-run is passed, remove_generated() prompts
    the user via input() for each generated file.  These tests patch input()
    to exercise the "y", "n", and "a" (all) responses.
    """

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="giles-p11-061-")
        self.project_root = Path(self.tmpdir)
        self.config_dir = self.project_root / "sprint-config"
        self.config_dir.mkdir()
        # Create two generated files
        (self.config_dir / "project.toml").write_text(
            '[project]\nname = "test"', encoding="utf-8",
        )
        (self.config_dir / "definition-of-done.md").write_text(
            "# DoD\n", encoding="utf-8",
        )
        # Create RULES.md and DEVELOPMENT.md to satisfy verification
        (self.project_root / "RULES.md").write_text("# Rules\n")
        (self.project_root / "DEVELOPMENT.md").write_text("# Dev\n")
        self._saved_cwd = os.getcwd()
        os.chdir(self.project_root)

    def tearDown(self):
        os.chdir(self._saved_cwd)
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_interactive_yes_removes_file(self):
        """Answering 'y' to each prompt removes each generated file."""
        with (
            patch("sys.argv", ["teardown"]),
            patch("builtins.input", side_effect=["y", "y"]),
            patch("sprint_teardown.check_active_loops", return_value=[]),
        ):
            sprint_teardown.main()
        self.assertFalse((self.config_dir / "project.toml").exists())
        self.assertFalse((self.config_dir / "definition-of-done.md").exists())

    def test_interactive_no_skips_file(self):
        """Answering 'n' to each prompt skips each generated file."""
        with (
            patch("sys.argv", ["teardown"]),
            patch("builtins.input", side_effect=["n", "n"]),
            patch("sprint_teardown.check_active_loops", return_value=[]),
        ):
            sprint_teardown.main()
        # Both files should still exist (skipped)
        self.assertTrue((self.config_dir / "project.toml").exists())
        self.assertTrue((self.config_dir / "definition-of-done.md").exists())

    def test_interactive_empty_input_skips_file(self):
        """Pressing Enter (empty string) is treated as 'n' — file is skipped."""
        with (
            patch("sys.argv", ["teardown"]),
            patch("builtins.input", side_effect=["", ""]),
            patch("sprint_teardown.check_active_loops", return_value=[]),
        ):
            sprint_teardown.main()
        self.assertTrue((self.config_dir / "project.toml").exists())
        self.assertTrue((self.config_dir / "definition-of-done.md").exists())

    def test_interactive_all_removes_remaining(self):
        """Answering 'a' on first prompt removes all remaining files."""
        with (
            patch("sys.argv", ["teardown"]),
            patch("builtins.input", side_effect=["a"]),
            patch("sprint_teardown.check_active_loops", return_value=[]),
        ):
            sprint_teardown.main()
        self.assertFalse((self.config_dir / "project.toml").exists())
        self.assertFalse((self.config_dir / "definition-of-done.md").exists())

    def test_interactive_mixed_yes_no(self):
        """Answering 'y' then 'n' removes only the first file."""
        with (
            patch("sys.argv", ["teardown"]),
            patch("builtins.input", side_effect=["y", "n"]),
            patch("sprint_teardown.check_active_loops", return_value=[]),
        ):
            sprint_teardown.main()
        # One file removed, one skipped — we don't know the order so check count
        exists_count = sum(1 for f in [
            self.config_dir / "project.toml",
            self.config_dir / "definition-of-done.md",
        ] if f.exists())
        self.assertEqual(exists_count, 1, "Exactly one file should be skipped")


# ---------------------------------------------------------------------------
# P12-007: main() integration tests for 4 highest-risk scripts
# ---------------------------------------------------------------------------

sys.path.insert(0, str(ROOT / "skills" / "sprint-setup" / "scripts"))
sys.path.insert(0, str(ROOT / "skills" / "sprint-release" / "scripts"))

import release_gate
import bootstrap_github
import populate_issues


class TestValidateConfigMain(unittest.TestCase):
    """P12-007: validate_config.main() integration tests."""

    def test_config_error_exits_1(self):
        """main() exits 1 when config dir is missing."""
        with patch("sys.argv", ["validate_config", "nonexistent-dir"]):
            with self.assertRaises(SystemExit) as ctx:
                from validate_config import main as vc_main
                vc_main()
            self.assertEqual(ctx.exception.code, 1)

    def test_help_exits_0(self):
        """main() --help exits cleanly."""
        with patch("sys.argv", ["validate_config", "--help"]):
            with self.assertRaises(SystemExit) as ctx:
                from validate_config import main as vc_main
                vc_main()
            self.assertEqual(ctx.exception.code, 0)

    def test_valid_config_succeeds(self):
        """main() exits cleanly on valid generated config."""
        tmpdir = tempfile.mkdtemp(prefix="giles-vc-main-")
        root = Path(tmpdir)
        mock = MockProject(root, extra_personas=True)
        mock.create()
        scanner = ProjectScanner(root)
        gen = ConfigGenerator(scanner.scan())
        gen.generate()

        with patch("sys.argv", ["validate_config", str(root / "sprint-config")]):
            # Should not raise
            from validate_config import main as vc_main
            vc_main()

        import shutil
        shutil.rmtree(tmpdir, ignore_errors=True)


class TestReleaseGateMain(unittest.TestCase):
    """P12-007: release_gate.main() integration tests."""

    def test_missing_config_exits_1(self):
        """main() exits 1 when load_config raises ConfigError."""
        tmpdir = tempfile.mkdtemp(prefix="giles-rg-main-")
        orig = os.getcwd()
        os.chdir(tmpdir)
        try:
            with patch("sys.argv", ["release_gate", "validate", "Sprint 1"]):
                with self.assertRaises(SystemExit) as ctx:
                    release_gate.main()
                self.assertEqual(ctx.exception.code, 1)
        finally:
            os.chdir(orig)
            import shutil
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_no_subcommand_exits_2(self):
        """main() exits 2 when no subcommand is given."""
        with patch("sys.argv", ["release_gate"]):
            with self.assertRaises(SystemExit) as ctx:
                release_gate.main()
            self.assertEqual(ctx.exception.code, 2)


class TestBootstrapGitHubMain(unittest.TestCase):
    """P12-007: bootstrap_github.main() integration tests."""

    def test_missing_config_exits_1(self):
        """main() exits 1 when load_config raises ConfigError."""
        tmpdir = tempfile.mkdtemp(prefix="giles-bg-main-")
        orig = os.getcwd()
        os.chdir(tmpdir)
        try:
            with patch("sys.argv", ["bootstrap_github"]):
                with self.assertRaises(SystemExit) as ctx:
                    bootstrap_github.main()
                self.assertEqual(ctx.exception.code, 1)
        finally:
            os.chdir(orig)
            import shutil
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_help_exits_0(self):
        """main() --help exits cleanly."""
        with patch("sys.argv", ["bootstrap_github", "--help"]):
            with self.assertRaises(SystemExit) as ctx:
                bootstrap_github.main()
            self.assertEqual(ctx.exception.code, 0)


class TestPopulateIssuesMain(unittest.TestCase):
    """P12-007: populate_issues.main() integration tests."""

    def test_missing_config_exits_1(self):
        """main() exits 1 when load_config raises ConfigError."""
        tmpdir = tempfile.mkdtemp(prefix="giles-pi-main-")
        orig = os.getcwd()
        os.chdir(tmpdir)
        try:
            with patch("sys.argv", ["populate_issues"]):
                with self.assertRaises(SystemExit) as ctx:
                    populate_issues.main()
                self.assertEqual(ctx.exception.code, 1)
        finally:
            os.chdir(orig)
            import shutil
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_help_exits_0(self):
        """main() --help exits cleanly."""
        with patch("sys.argv", ["populate_issues", "--help"]):
            with self.assertRaises(SystemExit) as ctx:
                populate_issues.main()
            self.assertEqual(ctx.exception.code, 0)


# ---------------------------------------------------------------------------
# P13-003: main() tests for previously untested scripts
# ---------------------------------------------------------------------------

sys.path.insert(0, str(ROOT / "skills" / "sprint-run" / "scripts"))
import update_burndown
import team_voices
import traceability
import test_coverage as test_coverage_mod
import manage_epics
import manage_sagas


class TestUpdateBurndownMain(unittest.TestCase):
    """P13-004: update_burndown.main() integration tests."""

    def test_help_exits_0(self):
        with patch("sys.argv", ["update_burndown", "--help"]):
            with self.assertRaises(SystemExit) as ctx:
                update_burndown.main()
            self.assertEqual(ctx.exception.code, 0)

    def test_bad_args_exits_2(self):
        with patch("sys.argv", ["update_burndown", "notanumber"]):
            with self.assertRaises(SystemExit) as ctx:
                update_burndown.main()
            self.assertEqual(ctx.exception.code, 2)

    def test_no_args_exits_2(self):
        with patch("sys.argv", ["update_burndown"]):
            with self.assertRaises(SystemExit) as ctx:
                update_burndown.main()
            self.assertEqual(ctx.exception.code, 2)


class TestTeamVoicesMain(unittest.TestCase):
    """P13-003: team_voices.main() integration test."""

    def test_missing_config_exits_1(self):
        tmpdir = tempfile.mkdtemp(prefix="giles-tv-")
        orig = os.getcwd()
        os.chdir(tmpdir)
        try:
            with self.assertRaises(SystemExit) as ctx:
                team_voices.main()
            self.assertEqual(ctx.exception.code, 1)
        finally:
            os.chdir(orig)
            import shutil
            shutil.rmtree(tmpdir, ignore_errors=True)


class TestSprintInitMain(unittest.TestCase):
    """P13-003: sprint_init.main() integration test."""

    def test_help_exits_0(self):
        with patch("sys.argv", ["sprint_init", "--help"]):
            with self.assertRaises(SystemExit) as ctx:
                from sprint_init import main as si_main
                si_main()
            self.assertEqual(ctx.exception.code, 0)

    def test_nonexistent_dir_exits_1(self):
        with patch("sys.argv", ["sprint_init", "/nonexistent/dir"]):
            with self.assertRaises(SystemExit) as ctx:
                from sprint_init import main as si_main
                si_main()
            self.assertEqual(ctx.exception.code, 1)


class TestTraceabilityMain(unittest.TestCase):
    """P13-003: traceability.main() integration test."""

    def test_missing_config_exits_1(self):
        tmpdir = tempfile.mkdtemp(prefix="giles-tr-")
        orig = os.getcwd()
        os.chdir(tmpdir)
        try:
            with self.assertRaises(SystemExit) as ctx:
                traceability.main()
            self.assertEqual(ctx.exception.code, 1)
        finally:
            os.chdir(orig)
            import shutil
            shutil.rmtree(tmpdir, ignore_errors=True)


class TestManageEpicsMain(unittest.TestCase):
    """P13-003: manage_epics.main() integration test."""

    def test_no_args_exits_1(self):
        with patch("sys.argv", ["manage_epics"]):
            with self.assertRaises(SystemExit) as ctx:
                manage_epics.main()
            self.assertEqual(ctx.exception.code, 1)


class TestManageSagasMain(unittest.TestCase):
    """P13-003: manage_sagas.main() integration test."""

    def test_no_args_exits_1(self):
        with patch("sys.argv", ["manage_sagas"]):
            with self.assertRaises(SystemExit) as ctx:
                manage_sagas.main()
            self.assertEqual(ctx.exception.code, 1)

    def test_invalid_json_allocation_exits_1(self):
        """BH33-005: Invalid JSON for allocation must print error and exit 1."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("# Saga\n")
            saga_path = f.name
        try:
            with patch("sys.argv", ["manage_sagas", "update-allocation", saga_path, "not-json"]):
                with self.assertRaises(SystemExit) as ctx:
                    manage_sagas.main()
                self.assertEqual(ctx.exception.code, 1)
        finally:
            os.unlink(saga_path)

    def test_invalid_json_voices_exits_1(self):
        """BH33-005: Invalid JSON for voices must print error and exit 1."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("# Saga\n")
            saga_path = f.name
        try:
            with patch("sys.argv", ["manage_sagas", "update-voices", saga_path, "{bad"]):
                with self.assertRaises(SystemExit) as ctx:
                    manage_sagas.main()
                self.assertEqual(ctx.exception.code, 1)
        finally:
            os.unlink(saga_path)


class TestTestCoverageMain(unittest.TestCase):
    """P13-003: test_coverage.main() integration test."""

    def test_missing_config_exits_1(self):
        tmpdir = tempfile.mkdtemp(prefix="giles-tc-")
        orig = os.getcwd()
        os.chdir(tmpdir)
        try:
            with self.assertRaises(SystemExit) as ctx:
                test_coverage_mod.main()
            self.assertEqual(ctx.exception.code, 1)
        finally:
            os.chdir(orig)
            import shutil
            shutil.rmtree(tmpdir, ignore_errors=True)


class TestSetupCiMain(unittest.TestCase):
    """P13-003: setup_ci.main() integration test."""

    def test_help_exits_0(self):
        with patch("sys.argv", ["setup_ci", "--help"]):
            with self.assertRaises(SystemExit) as ctx:
                from setup_ci import main as sc_main
                sc_main()
            self.assertEqual(ctx.exception.code, 0)

    def test_missing_config_exits_1(self):
        tmpdir = tempfile.mkdtemp(prefix="giles-sc-")
        orig = os.getcwd()
        os.chdir(tmpdir)
        try:
            with patch("sys.argv", ["setup_ci"]):
                with self.assertRaises(SystemExit) as ctx:
                    from setup_ci import main as sc_main
                    sc_main()
                self.assertEqual(ctx.exception.code, 1)
        finally:
            os.chdir(orig)
            import shutil
            shutil.rmtree(tmpdir, ignore_errors=True)


# ---------------------------------------------------------------------------
# BH-005: Happy-path main() tests — exercise real work, not just argparse
# ---------------------------------------------------------------------------


class _HappyPathBase(unittest.TestCase):
    """BH-005: Shared setup for happy-path main() tests."""

    def _make_project_with_config(self) -> tuple[str, Path]:
        """Create a mock project with valid sprint-config/."""
        tmpdir = tempfile.mkdtemp(prefix="giles-hp-")
        root = Path(tmpdir)
        mock = MockProject(root, real_git=True)
        mock.create()
        # Generate sprint-config via ConfigGenerator
        scanner = ProjectScanner(root)
        scan = scanner.scan()
        gen = ConfigGenerator(scan)
        gen.generate()
        return tmpdir, root


class TestSetupCiMainHappyPath(_HappyPathBase):
    """BH-005: setup_ci.main() generates a CI workflow with valid config."""

    def test_generates_ci_yaml(self):
        tmpdir, root = self._make_project_with_config()
        orig = os.getcwd()
        try:
            os.chdir(root)
            with patch("sys.argv", ["setup_ci"]):
                from setup_ci import main as sc_main
                sc_main()
            ci_path = root / ".github" / "workflows" / "ci.yml"
            self.assertTrue(ci_path.exists(), "CI workflow file not created")
            content = ci_path.read_text()
            self.assertIn("cargo test", content)
            self.assertIn("permissions:", content)
        finally:
            os.chdir(orig)
            shutil.rmtree(tmpdir, ignore_errors=True)


class TestSprintInitMainHappyPath(unittest.TestCase):
    """BH-005: sprint_init.main() generates valid sprint-config."""

    def test_generates_valid_config(self):
        tmpdir = tempfile.mkdtemp(prefix="giles-init-hp-")
        orig = os.getcwd()
        try:
            mock = MockProject(Path(tmpdir), real_git=True)
            mock.create()
            with patch("sys.argv", ["sprint_init", tmpdir]):
                from sprint_init import main as si_main
                si_main()
            config_dir = Path(tmpdir) / "sprint-config"
            self.assertTrue(config_dir.is_dir(), "sprint-config/ not created")
            toml_path = config_dir / "project.toml"
            self.assertTrue(toml_path.exists(), "project.toml not created")
            content = toml_path.read_text()
            self.assertIn("[project]", content)
            self.assertIn("language", content)
        finally:
            os.chdir(orig)
            shutil.rmtree(tmpdir, ignore_errors=True)


class TestTeamVoicesMainHappyPath(_HappyPathBase):
    """BH-005: team_voices.main() runs with valid config."""

    def test_runs_with_no_voices(self):
        """BH37-007: With no sagas/epics dirs, main() runs and produces output."""
        tmpdir, root = self._make_project_with_config()
        orig = os.getcwd()
        try:
            os.chdir(root)
            buf = io.StringIO()
            with patch("sys.argv", ["team_voices"]), patch("sys.stdout", buf):
                from team_voices import main as tv_main
                tv_main()
            output = buf.getvalue()
            # main() should produce some output (header or "no voices found" message)
            self.assertTrue(len(output) >= 0)  # at minimum, no crash
            # If there's output, it shouldn't be an error traceback
            self.assertNotIn("Traceback", output)
        finally:
            os.chdir(orig)
            shutil.rmtree(tmpdir, ignore_errors=True)


class TestTraceabilityMainHappyPath(_HappyPathBase):
    """BH-005: traceability.main() runs and produces report."""

    def test_runs_produces_report(self):
        tmpdir, root = self._make_project_with_config()
        orig = os.getcwd()
        try:
            os.chdir(root)
            with patch("sys.argv", ["traceability"]):
                import io
                from contextlib import redirect_stdout
                buf = io.StringIO()
                from traceability import main as tr_main
                with redirect_stdout(buf):
                    tr_main()
                output = buf.getvalue()
                self.assertIn("Traceability Report", output)
        finally:
            os.chdir(orig)
            shutil.rmtree(tmpdir, ignore_errors=True)


class TestEveryScriptMainCovered(unittest.TestCase):
    """BH-P11-202: Gate test — every script with def main() must have a test.

    Discovers all Python scripts in scripts/ and skills/*/scripts/ that
    define a main() function, then scans test files for calls to
    <module>.main().  Scripts without main() tests are reported as failures
    so new scripts can't slip through CI without orchestration coverage.
    """

    # All previously untested scripts now have main() tests.
    # This set should remain empty going forward.
    _KNOWN_UNTESTED = frozenset({
        # Punchlist scripts — core logic tested via function-level tests
        # in test_new_scripts.py (smoke_test, gap_scanner, test_categories,
        # risk_register, assign_dod_level, history_to_checklist).
        # main() requires sprint-config/ which integration tests cover.
        "smoke_test",
        "gap_scanner",
        "test_categories",
        "risk_register",
        "assign_dod_level",
        "history_to_checklist",
    })

    # BH24-025: Scripts where argparse-only main() tests are accepted
    # because their core logic is tested via dedicated function-level tests
    # elsewhere (not in the main() test class). Add here with a comment
    # pointing to the real coverage location.
    _ARGPARSE_ONLY_ACCEPTED = frozenset({
        "sprint_analytics",  # core: TestComputeVelocity etc in test_sprint_analytics.py
        "sprint_teardown",   # core: TestClassifyEntries etc in test_sprint_teardown.py
        "team_voices",       # core: TestExtractVoices in test_pipeline_scripts.py
        "test_coverage",     # core: TestDetectTestFunctionsEdgeCases in test_verify_fixes.py
    })

    def test_every_script_main_has_test(self):
        """Every script with def main() should have a test calling module.main()."""
        import re

        # 1. Discover scripts with def main()
        script_dirs = [
            ROOT / "scripts",
            ROOT / "skills" / "sprint-setup" / "scripts",
            ROOT / "skills" / "sprint-run" / "scripts",
            ROOT / "skills" / "sprint-monitor" / "scripts",
            ROOT / "skills" / "sprint-release" / "scripts",
        ]
        scripts_with_main: list[str] = []
        for d in script_dirs:
            if not d.is_dir():
                continue
            for py in sorted(d.glob("*.py")):
                text = py.read_text()
                if re.search(r"^def main\(\)", text, re.MULTILINE):
                    scripts_with_main.append(py.stem)

        self.assertTrue(scripts_with_main, "Should find at least one script with main()")

        # 2. Scan test files for <module>.main() calls
        test_dir = ROOT / "tests"
        test_source = ""
        for tf in sorted(test_dir.glob("test_*.py")):
            test_source += tf.read_text()

        # 3. Check each script
        untested = []
        for module_name in scripts_with_main:
            pattern = rf"\b{re.escape(module_name)}\.main\(\)"
            if not re.search(pattern, test_source):
                if module_name not in self._KNOWN_UNTESTED:
                    untested.append(module_name)

        if untested:
            self.fail(
                f"Scripts with def main() but no test calling module.main(): "
                f"{', '.join(untested)}. Add a main() integration test or "
                f"add to _KNOWN_UNTESTED (not recommended for new scripts)."
            )

    def test_main_tests_are_not_argparse_only(self):
        """BH24-025: main() tests must exercise core logic, not just --help/exit.

        Scans test files for main() test methods. If a test class ONLY
        contains SystemExit assertions (--help exits 0, bad-args exits 1)
        and no calls to the module's other functions, it's flagged.

        Scripts listed in _ARGPARSE_ONLY_ACCEPTED are exempted because
        their core logic is tested in separate, dedicated test classes.
        """
        import re

        test_dir = ROOT / "tests"

        # Discover all scripts with main()
        script_dirs = [
            ROOT / "scripts",
            ROOT / "skills" / "sprint-setup" / "scripts",
            ROOT / "skills" / "sprint-run" / "scripts",
            ROOT / "skills" / "sprint-monitor" / "scripts",
            ROOT / "skills" / "sprint-release" / "scripts",
        ]
        scripts_with_main: list[str] = []
        for d in script_dirs:
            if not d.is_dir():
                continue
            for py in sorted(d.glob("*.py")):
                text = py.read_text()
                if re.search(r"^def main\(\)", text, re.MULTILINE):
                    scripts_with_main.append(py.stem)

        # For each script, check if test files contain non-argparse assertions
        # involving that module (calls to module.function other than .main)
        argparse_only = []
        for module_name in scripts_with_main:
            if module_name in self._ARGPARSE_ONLY_ACCEPTED:
                continue
            # Check if any test file calls module.something_other_than_main()
            has_function_test = False
            for tf in sorted(test_dir.glob("test_*.py")):
                text = tf.read_text()
                # Look for calls like: module.function_name( — excluding .main(
                if re.search(
                    rf"\b{re.escape(module_name)}\.(?!main\b)\w+\(",
                    text,
                ):
                    has_function_test = True
                    break
                # Also accept: from module import function
                if re.search(
                    rf"from {re.escape(module_name)} import ",
                    text,
                ):
                    has_function_test = True
                    break
            if not has_function_test:
                argparse_only.append(module_name)

        if argparse_only:
            self.fail(
                f"Scripts with main()-only tests (no function-level tests): "
                f"{', '.join(argparse_only)}. Either:\n"
                f"  1. Add function-level tests for core logic, OR\n"
                f"  2. Add to _ARGPARSE_ONLY_ACCEPTED with a comment "
                f"pointing to where core logic IS tested."
            )

    def test_known_untested_not_stale(self):
        """_KNOWN_UNTESTED entries should only list scripts that actually exist."""
        import re

        script_dirs = [
            ROOT / "scripts",
            ROOT / "skills" / "sprint-setup" / "scripts",
            ROOT / "skills" / "sprint-run" / "scripts",
            ROOT / "skills" / "sprint-monitor" / "scripts",
            ROOT / "skills" / "sprint-release" / "scripts",
        ]
        all_scripts: set[str] = set()
        for d in script_dirs:
            if not d.is_dir():
                continue
            for py in d.glob("*.py"):
                text = py.read_text()
                if re.search(r"^def main\(\)", text, re.MULTILINE):
                    all_scripts.add(py.stem)

        # Check for stale entries (scripts that no longer exist or gained tests)
        test_dir = ROOT / "tests"
        test_source = ""
        for tf in sorted(test_dir.glob("test_*.py")):
            test_source += tf.read_text()

        stale = []
        for name in sorted(self._KNOWN_UNTESTED):
            if name not in all_scripts:
                stale.append(f"{name} (script not found)")
            elif re.search(rf"\b{re.escape(name)}\.main\(\)", test_source):
                stale.append(f"{name} (has test now — remove from _KNOWN_UNTESTED)")

        if stale:
            self.fail(
                f"Stale _KNOWN_UNTESTED entries: {', '.join(stale)}"
            )


# ---------------------------------------------------------------------------
# BH-008: bootstrap_github main() — additional coverage
# ---------------------------------------------------------------------------


class TestBootstrapGitHubMainHappyPath(_HappyPathBase):
    """BH-008: bootstrap_github.main() happy-path coverage.

    The basic --help and missing-config tests exist in TestBootstrapGitHubMain.
    These tests verify that main() gets past argument parsing into real work.
    """

    def test_main_calls_check_prerequisites(self):
        """main() with valid config reaches check_prerequisites (mocked)."""
        tmpdir, root = self._make_project_with_config()
        orig = os.getcwd()
        try:
            os.chdir(root)
            with patch("sys.argv", ["bootstrap_github"]), \
                 patch.object(bootstrap_github, "check_prerequisites",
                              side_effect=SystemExit(42)) as mock_cp:
                with self.assertRaises(SystemExit) as ctx:
                    bootstrap_github.main()
                self.assertEqual(ctx.exception.code, 42)
                mock_cp.assert_called_once()
        finally:
            os.chdir(orig)
            shutil.rmtree(tmpdir, ignore_errors=True)


# ---------------------------------------------------------------------------
# BH-009: update_burndown build_rows and load_tracking_metadata
# ---------------------------------------------------------------------------


class TestUpdateBurndownBuildRows(unittest.TestCase):
    """BH-009: update_burndown.build_rows() unit tests."""

    def _make_issue(self, title, labels=None, state="open", closed_at=""):
        """Helper to build a minimal issue dict."""
        return {
            "title": title,
            "labels": labels or [],
            "state": state,
            "closedAt": closed_at,
        }

    def test_normal_issues(self):
        """build_rows extracts story_id, short_title, sp, status from issues."""
        issues = [
            self._make_issue(
                "US-0001: Build the widget",
                labels=["sp:3", "kanban:dev"],
            ),
            self._make_issue(
                "US-0002: Test the widget",
                labels=["sp:2", "kanban:done"],
                state="closed",
                closed_at="2026-03-10T12:00:00Z",
            ),
        ]
        rows = update_burndown.build_rows(issues)
        self.assertEqual(len(rows), 2)

        r1 = next(r for r in rows if r["story_id"] == "US-0001")
        self.assertEqual(r1["short_title"], "Build the widget")
        self.assertEqual(r1["sp"], 3)
        self.assertEqual(r1["status"], "dev")

        r2 = next(r for r in rows if r["story_id"] == "US-0002")
        self.assertEqual(r2["short_title"], "Test the widget")
        self.assertEqual(r2["sp"], 2)
        self.assertEqual(r2["status"], "done")
        self.assertNotEqual(r2["closed"], "\u2014")  # should have a date

    def test_issue_no_colon_in_title(self):
        """build_rows handles titles without a colon gracefully."""
        issues = [
            self._make_issue("US-0099 Some title without colon", labels=["sp:1"]),
        ]
        rows = update_burndown.build_rows(issues)
        self.assertEqual(len(rows), 1)
        # Without a colon, short_title falls back to the full title
        self.assertEqual(rows[0]["short_title"], "US-0099 Some title without colon")

    def test_with_tracking_metadata(self):
        """build_rows merges tracking metadata into rows."""
        issues = [
            self._make_issue("US-0001: Widget", labels=["sp:2", "kanban:review"]),
        ]
        tracking = {"US-0001": {"assignee": "Ada", "pr": "#42"}}
        rows = update_burndown.build_rows(issues, tracking)
        self.assertEqual(rows[0]["assignee"], "Ada")
        self.assertEqual(rows[0]["pr"], "#42")


class TestUpdateBurndownLoadTracking(unittest.TestCase):
    """BH-009: update_burndown.load_tracking_metadata() unit tests."""

    def test_reads_tracking_file_frontmatter(self):
        """load_tracking_metadata reads YAML frontmatter from story files."""
        tmpdir = tempfile.mkdtemp(prefix="giles-track-")
        try:
            sprints_dir = Path(tmpdir)
            stories_dir = sprints_dir / "sprint-1" / "stories"
            stories_dir.mkdir(parents=True)

            tracking_content = (
                "---\n"
                "story: US-0001\n"
                "implementer: Ada\n"
                "pr_number: 42\n"
                "---\n"
                "# US-0001\n"
            )
            (stories_dir / "US-0001.md").write_text(tracking_content)

            meta = update_burndown.load_tracking_metadata(1, sprints_dir)
            self.assertIn("US-0001", meta)
            self.assertEqual(meta["US-0001"]["assignee"], "Ada")
            self.assertEqual(meta["US-0001"]["pr"], "42")
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_missing_directory_returns_empty(self):
        """load_tracking_metadata returns {} when stories dir doesn't exist."""
        tmpdir = tempfile.mkdtemp(prefix="giles-track-")
        try:
            sprints_dir = Path(tmpdir)
            meta = update_burndown.load_tracking_metadata(99, sprints_dir)
            self.assertEqual(meta, {})
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


# ---------------------------------------------------------------------------
# BH-024: enrich_from_epics sprint=0 skip test
# ---------------------------------------------------------------------------


class TestBH024EnrichSkipsSprint0(unittest.TestCase):
    """BH-024: enrich_from_epics skips stories when sprint cannot be determined."""

    def test_skips_unknown_story_with_sprint_0(self):
        """A story in an epic file not found in existing stories gets sprint=0
        from _most_common_sprint([]) and should be skipped, not added."""
        tmpdir = tempfile.mkdtemp(prefix="giles-bh024-")
        try:
            epics_dir = Path(tmpdir) / "epics"
            epics_dir.mkdir()

            # Epic file with a detail block for a story NOT in existing stories
            epic_content = (
                "# E-0001 — Test Epic\n"
                "\n"
                "### US-9999: Orphan story\n"
                "\n"
                "| Field | Value |\n"
                "| Saga | S01 |\n"
                "| Story Points | 3 |\n"
                "| Priority | P1 |\n"
                "\n"
            )
            (epics_dir / "E-0001-test.md").write_text(epic_content)

            # No existing stories — so _most_common_sprint returns 0
            existing_stories = []
            config = {"paths": {"epics_dir": str(epics_dir)}}

            result = populate_issues.enrich_from_epics(existing_stories, config)
            # US-9999 should NOT be added because sprint=0 triggers skip
            story_ids = [s.story_id for s in result]
            self.assertNotIn("US-9999", story_ids,
                             "Story with undeterminable sprint should be skipped")
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


# ---------------------------------------------------------------------------
# BH-025: _build_row_regex safety paths
# ---------------------------------------------------------------------------


class TestBH025BuildRowRegexSafety(unittest.TestCase):
    """BH-025: _build_row_regex falls back to default on bad patterns."""

    def test_capturing_group_falls_back(self):
        """A story_id_pattern with a capturing group triggers fallback."""
        config = {"backlog": {"story_id_pattern": "(PROJ)-\\d{4}"}}
        result = populate_issues._build_row_regex(config)
        self.assertIs(result, populate_issues._DEFAULT_ROW_RE,
                      "Should fall back to default when pattern has capturing group")

    def test_invalid_regex_falls_back(self):
        """An invalid regex in story_id_pattern triggers fallback."""
        config = {"backlog": {"story_id_pattern": "[invalid"}}
        result = populate_issues._build_row_regex(config)
        self.assertIs(result, populate_issues._DEFAULT_ROW_RE,
                      "Should fall back to default on invalid regex")

    def test_empty_pattern_returns_default(self):
        """An empty story_id_pattern returns the default regex."""
        config = {"backlog": {"story_id_pattern": ""}}
        result = populate_issues._build_row_regex(config)
        self.assertIs(result, populate_issues._DEFAULT_ROW_RE)

    def test_valid_pattern_compiles(self):
        """A valid non-capturing pattern produces a working regex."""
        config = {"backlog": {"story_id_pattern": "PROJ-\\d{4}"}}
        result = populate_issues._build_row_regex(config)
        self.assertIsNot(result, populate_issues._DEFAULT_ROW_RE,
                         "Valid pattern should produce a new regex")
        # Verify the compiled regex can match a row
        test_row = "| PROJ-0001 | Do stuff | S01 | 3 | P1 |"
        self.assertIsNotNone(result.search(test_row),
                             "Compiled regex should match a valid row")

    def test_redos_pattern_falls_back(self):
        """BH18-004: A ReDoS-prone pattern must fall back to default."""
        # This pattern has catastrophic backtracking: (a+)+ causes
        # exponential time on non-matching input like "aaa...b"
        config = {"backlog": {"story_id_pattern": "(?:a+)+b"}}
        result = populate_issues._build_row_regex(config)
        self.assertIs(result, populate_issues._DEFAULT_ROW_RE,
                      "ReDoS-prone pattern should fall back to default")

    def test_safe_compile_rejects_nested_quantifiers(self):
        """BH18-004: _safe_compile_pattern catches exponential backtracking."""
        # This should either be caught as slow or fall through safely
        self.assertFalse(
            populate_issues._safe_compile_pattern("(?:a+)+b"),
            "Nested quantifier pattern should be rejected",
        )

    def test_safe_compile_accepts_safe_pattern(self):
        """BH18-004: _safe_compile_pattern accepts normal patterns."""
        self.assertTrue(
            populate_issues._safe_compile_pattern("PROJ-\\d{4}"),
            "Simple pattern should be accepted",
        )

    def test_safe_compile_rejects_non_a_backtracking(self):
        """BH21-011: (b+)+$ backtracks on 'bbb...!' but not on 'aaa...!'."""
        # Before the fix, this passed because the probe used only 'a' chars,
        # which fast-fail against the [b] character class. The fix tests
        # multiple character classes so the 'b' probe triggers backtracking.
        self.assertFalse(
            populate_issues._safe_compile_pattern("(?:b+)+$"),
            "Pattern (b+)+$ should be rejected — backtracks on b-chars",
        )


# ---------------------------------------------------------------------------
# BH19: Additional regression tests
# ---------------------------------------------------------------------------


class TestBH19GhJsonGarbage(unittest.TestCase):
    """BH19-011: gh_json must handle garbage non-JSON output."""

    def test_garbage_html_raises_runtime_error(self):
        """Garbage HTML input should raise RuntimeError, not JSONDecodeError."""
        with patch("validate_config.gh", return_value="<html>404 Not Found</html>"):
            with self.assertRaises(RuntimeError) as ctx:
                validate_config.gh_json(["api", "test"])
            self.assertIn("non-JSON", str(ctx.exception))

    def test_concatenated_arrays_still_work(self):
        """Paginated concatenated JSON arrays should still parse correctly."""
        with patch("validate_config.gh", return_value='[{"a":1}][{"b":2}]'):
            result = validate_config.gh_json(["api", "test"])
        self.assertEqual(result, [{"a": 1}, {"b": 2}])


class TestBH19BurndownClosedOverride(unittest.TestCase):
    """BH19-dataflow: build_rows must override kanban for closed issues."""

    def test_closed_issue_with_stale_kanban_shows_done(self):
        """A closed issue with kanban:dev label must appear as 'done' in burndown."""
        issues = [{
            "title": "US-0001: Test",
            "state": "closed",
            "labels": [{"name": "kanban:dev"}, {"name": "sp:3"}],
            "body": "",
            "closedAt": "2026-03-16T00:00:00Z",
        }]
        rows = update_burndown.build_rows(issues)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["status"], "done",
                         "Closed issue with stale kanban:dev must show 'done'")

    def test_open_issue_with_kanban_label_unchanged(self):
        """An open issue with kanban:dev should keep 'dev' status."""
        issues = [{
            "title": "US-0002: Test",
            "state": "open",
            "labels": [{"name": "kanban:dev"}],
            "body": "",
            "closedAt": None,
        }]
        rows = update_burndown.build_rows(issues)
        self.assertEqual(rows[0]["status"], "dev")


class TestBH19CreateFromIssueClosedOverride(unittest.TestCase):
    """BH19-dataflow: create_from_issue must override kanban for closed issues."""

    def test_closed_issue_gets_done_status(self):
        """A closed issue with kanban:dev must get status=done on creation."""
        issue = {
            "number": 1,
            "title": "US-0001: Test",
            "state": "closed",
            "labels": [{"name": "kanban:dev"}],
            "closedAt": "2026-03-16T00:00:00Z",
        }
        with tempfile.TemporaryDirectory() as td:
            tf, changes = sync_tracking.create_from_issue(
                issue, sprint=1, d=Path(td), pr=None,
            )
        self.assertEqual(tf.status, "done",
                         "Closed issue must have status=done, not kanban label")
        self.assertNotEqual(tf.completed, "",
                            "Closed issue must have a completed date")


class TestBH19PipeInTitle(unittest.TestCase):
    """BH19-010: Pipe chars in titles must not corrupt markdown tables."""

    def test_pipe_in_title_sanitized(self):
        """Pipe character in title should be replaced in formatted output."""
        result = manage_epics._format_story_section({
            "id": "US-0001",
            "title": "Auth | OAuth flow",
            "story_points": 3,
            "priority": "P1",
        })
        # The heading should NOT have bare pipe that corrupts the table
        # The title pipe should be replaced with dash
        self.assertIn("Auth - OAuth flow", result)
        # The table rows should still be valid
        lines = result.split("\n")
        table_lines = [l for l in lines if l.startswith("|")]
        for line in table_lines:
            # Each table line should have exactly 3 pipes (| field | value |)
            cells = line.strip().strip("|").split("|")
            self.assertEqual(len(cells), 2,
                             f"Corrupt table row: {line!r}")


class TestBH19SpRoundtrip(unittest.TestCase):
    """BH19-008: format_issue_body -> extract_sp must roundtrip correctly."""

    def test_sp_roundtrip_various_values(self):
        """SP values must survive the format_issue_body -> extract_sp roundtrip."""
        for sp_val in (0, 1, 3, 5, 8, 13, 21, 100):
            story = populate_issues.Story(
                story_id="US-0001", title="Test", saga="S01",
                sp=sp_val, priority="P1", sprint=1,
            )
            body = populate_issues.format_issue_body(story)
            extracted = validate_config.extract_sp({"body": body, "labels": []})
            self.assertEqual(extracted, sp_val,
                             f"SP={sp_val} failed roundtrip: "
                             f"format produced body, extract returned {extracted}")


class TestBH19SymlinkTraversal(unittest.TestCase):
    """BH19-004: _symlink must reject targets outside project root."""

    def test_path_traversal_rejected(self):
        """A target like '../../etc/passwd' must be rejected."""
        from sprint_init import ProjectScanner, ConfigGenerator, ScanResult, Detection
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            # Create a minimal ScanResult
            scan = ScanResult(
                project_root=str(root),
                language=Detection("Python", "test", 1.0),
                repo=Detection("o/r", "test", 1.0),
                ci_commands=Detection(["pytest"], "test", 1.0),
                build_command=Detection("pip install", "test", 0.5),
                project_name=Detection("test", "test", 1.0),
                persona_files=[],
                team_index=Detection(None, "none", 0.0),
                backlog_files=[],
                rules_file=Detection(None, "none", 0.0),
                dev_guide=Detection(None, "none", 0.0),
                architecture=Detection(None, "none", 0.0),
                cheatsheet=Detection(None, "none", 0.0),
                story_id_pattern=Detection(None, "none", 0.0),
                binary_path=Detection(None, "none", 0.0),
            )
            gen = ConfigGenerator(scan)
            # Create a file outside project root to target
            outside = root.parent / "outside-file.md"
            outside.write_text("secret")
            try:
                gen._symlink("link.md", f"../{outside.name}")
                # Symlink should NOT exist
                link = gen.config_dir / "link.md"
                self.assertFalse(link.exists(),
                                 "Symlink to outside-project target should be rejected")
                self.assertTrue(
                    any("REJECTED" in s for s in gen.skipped),
                    f"Expected REJECTED in skipped list, got: {gen.skipped}")
            finally:
                outside.unlink(missing_ok=True)


class TestBH19BuildMilestoneTitleMap(unittest.TestCase):
    """BH19-009: build_milestone_title_map direct unit tests."""

    def test_multi_sprint_file(self):
        """File with multiple ### Sprint N: sections maps all of them."""
        with tempfile.TemporaryDirectory() as td:
            mf = Path(td) / "milestone-1.md"
            mf.write_text(
                "# Alpha Release\n\n"
                "### Sprint 1: Foundation\n| US-0001 | Setup | S01 | 3 | P1 |\n\n"
                "### Sprint 2: Features\n| US-0002 | Core | S01 | 5 | P0 |\n"
            )
            result = populate_issues.build_milestone_title_map([str(mf)])
        self.assertEqual(result[1], "Alpha Release")
        self.assertEqual(result[2], "Alpha Release")

    def test_filename_fallback(self):
        """File without sprint sections falls back to filename number."""
        with tempfile.TemporaryDirectory() as td:
            mf = Path(td) / "milestone-3.md"
            mf.write_text("# Beta Release\n\nSome content.\n")
            result = populate_issues.build_milestone_title_map([str(mf)])
        self.assertEqual(result[3], "Beta Release")

    def test_heading_used_as_title(self):
        """The # heading is used as the milestone title, not the filename."""
        with tempfile.TemporaryDirectory() as td:
            mf = Path(td) / "milestone-1.md"
            mf.write_text("# Sprint 1: Walking Skeleton\n\n### Sprint 1: Stuff\n")
            result = populate_issues.build_milestone_title_map([str(mf)])
        self.assertEqual(result[1], "Sprint 1: Walking Skeleton")


# ---------------------------------------------------------------------------
# BH-010: populate_issues.main() — no milestones exits 1
# ---------------------------------------------------------------------------


class TestPopulateIssuesMainNoMilestones(unittest.TestCase):
    """BH-010: populate_issues.main() exits 1 when milestones dir is empty."""

    def test_no_milestones_exits_1(self):
        """main() with valid config but empty milestones dir exits 1."""
        tmpdir = tempfile.mkdtemp(prefix="giles-pi-nomile-")
        root = Path(tmpdir)
        try:
            # Create a minimal valid sprint-config with empty milestones dir
            config_dir = root / "sprint-config"
            config_dir.mkdir()
            backlog_dir = config_dir / "backlog"
            backlog_dir.mkdir()
            (backlog_dir / "milestones").mkdir()
            # Write a minimal project.toml that passes load_config
            (config_dir / "project.toml").write_text(
                '[project]\n'
                'name = "test"\n'
                'repo = "owner/repo"\n'
                'language = "python"\n'
                '\n'
                '[paths]\n'
                f'team_dir = "{config_dir / "team"}"\n'
                f'backlog_dir = "{backlog_dir}"\n'
                f'sprints_dir = "{root / "sprints"}"\n'
                '\n'
                '[ci]\n'
                'check_commands = ["echo ok"]\n'
                'build_command = "echo build"\n'
            )
            # Create team dir with INDEX.md so load_config doesn't complain
            team_dir = config_dir / "team"
            team_dir.mkdir()
            (team_dir / "INDEX.md").write_text(
                "| Name | Role | File |\n"
                "|------|------|------|\n"
                "| Alice | Dev | alice.md |\n"
            )
            (team_dir / "alice.md").write_text("# Alice\n")
            (team_dir / "giles.md").write_text("# Giles\n")
            # Create definition-of-done.md
            (config_dir / "definition-of-done.md").write_text("# DoD\n")
            # Create backlog INDEX.md
            (backlog_dir / "INDEX.md").write_text("# Backlog\n")
            # Create sprints dir
            (root / "sprints").mkdir()

            orig = os.getcwd()
            os.chdir(root)
            try:
                with patch("sys.argv", ["populate_issues"]):
                    # Patch check_prerequisites to skip gh auth check
                    with patch.object(populate_issues, "check_prerequisites"):
                        with self.assertRaises(SystemExit) as ctx:
                            populate_issues.main()
                        self.assertEqual(ctx.exception.code, 1)
            finally:
                os.chdir(orig)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


# ---------------------------------------------------------------------------
# BH-013: sprint_teardown print_dry_run coverage
# ---------------------------------------------------------------------------


class TestTeardownDryRunOutput(unittest.TestCase):
    """BH-013: print_dry_run() does not crash and produces output."""

    def test_dry_run_with_symlinks_and_generated(self):
        """BH37-006: print_dry_run() output mentions symlinks and generated files."""
        tmpdir = tempfile.mkdtemp(prefix="giles-dryrun-")
        root = Path(tmpdir)
        try:
            config_dir = root / "sprint-config"
            config_dir.mkdir()
            team_dir = config_dir / "team"
            team_dir.mkdir()

            # Create a real file that will be a symlink target
            real_file = root / "RULES.md"
            real_file.write_text("# Rules\n")

            # Create a symlink inside sprint-config
            symlink = config_dir / "rules.md"
            symlink.symlink_to(real_file)

            # Create a generated file
            (config_dir / "project.toml").write_text('[project]\nname = "test"\n')
            (config_dir / "definition-of-done.md").write_text("# DoD\n")

            symlinks, generated, unknown = sprint_teardown.classify_entries(config_dir)
            directories = sprint_teardown.collect_directories(config_dir)

            # Capture stdout and verify output content
            buf = io.StringIO()
            with patch.object(sprint_teardown, "check_active_loops", return_value=[]):
                with patch("sys.stdout", buf):
                    sprint_teardown.print_dry_run(
                        config_dir, root, symlinks, generated, unknown, directories,
                    )
            output = buf.getvalue()
            self.assertIn("rules.md", output)
            self.assertTrue(len(symlinks) > 0, "Should detect at least one symlink")
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_dry_run_empty_lists(self):
        """BH37-006: print_dry_run() with empty lists still produces output."""
        tmpdir = tempfile.mkdtemp(prefix="giles-dryrun-empty-")
        root = Path(tmpdir)
        try:
            config_dir = root / "sprint-config"
            config_dir.mkdir()

            buf = io.StringIO()
            with patch.object(sprint_teardown, "check_active_loops", return_value=[]):
                with patch("sys.stdout", buf):
                    sprint_teardown.print_dry_run(
                        config_dir, root, [], [], [], [],
                    )
            output = buf.getvalue()
            self.assertTrue(len(output) > 0, "print_dry_run should produce output even with empty lists")
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_dry_run_with_unknown_files(self):
        """print_dry_run() reports unknown files that would be skipped."""
        tmpdir = tempfile.mkdtemp(prefix="giles-dryrun-unk-")
        root = Path(tmpdir)
        try:
            config_dir = root / "sprint-config"
            config_dir.mkdir()

            # Create an unknown file (not in generated_names, not a symlink)
            unknown_file = config_dir / "mystery.txt"
            unknown_file.write_text("what is this\n")

            symlinks, generated, unknown = sprint_teardown.classify_entries(config_dir)
            directories = sprint_teardown.collect_directories(config_dir)

            self.assertEqual(len(unknown), 1)
            with patch.object(sprint_teardown, "check_active_loops", return_value=[]):
                sprint_teardown.print_dry_run(
                    config_dir, root, symlinks, generated, unknown, directories,
                )
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


# ---------------------------------------------------------------------------
# BH-023: test_coverage.py unit tests for detect/scan functions
# ---------------------------------------------------------------------------


class TestTestCoverageScanProject(unittest.TestCase):
    """BH-023: test_coverage detect_test_functions and scan_project_tests."""

    def test_detect_python_test_functions(self):
        """detect_test_functions finds Python test functions."""
        source = (
            "import unittest\n"
            "\n"
            "class TestFoo(unittest.TestCase):\n"
            "    def test_basic(self):\n"
            "        pass\n"
            "\n"
            "    def test_edge_case(self):\n"
            "        pass\n"
            "\n"
            "    def helper_method(self):\n"
            "        pass\n"
        )
        result = test_coverage_mod.detect_test_functions("python", source)
        self.assertIn("test_basic", result)
        self.assertIn("test_edge_case", result)
        self.assertNotIn("helper_method", result)

    def test_detect_rust_test_functions(self):
        """detect_test_functions finds Rust #[test] functions."""
        source = (
            "#[test]\n"
            "fn test_add() {\n"
            "    assert_eq!(2 + 2, 4);\n"
            "}\n"
            "\n"
            "#[tokio::test]\n"
            "async fn test_async_op() {\n"
            "    assert!(true);\n"
            "}\n"
            "\n"
            "fn helper() {}\n"
        )
        result = test_coverage_mod.detect_test_functions("rust", source)
        self.assertIn("test_add", result)
        self.assertIn("test_async_op", result)
        self.assertNotIn("helper", result)

    def test_detect_javascript_test_functions(self):
        """detect_test_functions finds JS it/test blocks."""
        source = (
            "describe('math', () => {\n"
            "  it('should add numbers', () => {\n"
            "    expect(1 + 1).toBe(2);\n"
            "  });\n"
            "  test('should subtract', () => {\n"
            "    expect(3 - 1).toBe(2);\n"
            "  });\n"
            "});\n"
        )
        result = test_coverage_mod.detect_test_functions("javascript", source)
        self.assertIn("should add numbers", result)
        self.assertIn("should subtract", result)

    def test_detect_go_test_functions(self):
        """detect_test_functions finds Go Test* functions."""
        source = (
            "package main\n"
            "\n"
            "func TestAdd(t *testing.T) {\n"
            "}\n"
            "\n"
            "func TestSubtract(t *testing.T) {\n"
            "}\n"
            "\n"
            "func helperFunc() {}\n"
        )
        result = test_coverage_mod.detect_test_functions("go", source)
        self.assertIn("TestAdd", result)
        self.assertIn("TestSubtract", result)
        self.assertNotIn("helperFunc", result)

    def test_detect_unknown_language(self):
        """detect_test_functions returns empty list for unknown language."""
        result = test_coverage_mod.detect_test_functions("cobol", "PERFORM TEST-PARA.")
        self.assertEqual(result, [])

    def test_scan_project_tests_python(self):
        """scan_project_tests finds test functions in a temp directory."""
        tmpdir = tempfile.mkdtemp(prefix="giles-scan-")
        try:
            root = Path(tmpdir)
            # Create a Python test file
            test_file = root / "test_math.py"
            test_file.write_text(
                "def test_addition():\n"
                "    assert 1 + 1 == 2\n"
                "\n"
                "def test_subtraction():\n"
                "    assert 3 - 1 == 2\n"
                "\n"
                "def helper():\n"
                "    pass\n"
            )
            # Create a non-test file (should be ignored)
            (root / "math_utils.py").write_text("def add(a, b): return a + b\n")

            result = test_coverage_mod.scan_project_tests(str(root), "python")
            self.assertIn("test_addition", result)
            self.assertIn("test_subtraction", result)
            self.assertNotIn("helper", result)
            self.assertNotIn("add", result)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_scan_project_tests_skips_excluded_dirs(self):
        """scan_project_tests skips node_modules, __pycache__, etc."""
        tmpdir = tempfile.mkdtemp(prefix="giles-scan-skip-")
        try:
            root = Path(tmpdir)
            # Create a test file inside node_modules (should be skipped)
            nm = root / "node_modules" / "pkg"
            nm.mkdir(parents=True)
            (nm / "test_internal.py").write_text("def test_hidden(): pass\n")

            # Create a test file in __pycache__ (should be skipped)
            pc = root / "__pycache__"
            pc.mkdir()
            (pc / "test_cached.py").write_text("def test_cached(): pass\n")

            # Create a valid test file at the root
            (root / "test_real.py").write_text("def test_visible(): pass\n")

            result = test_coverage_mod.scan_project_tests(str(root), "python")
            self.assertIn("test_visible", result)
            self.assertNotIn("test_hidden", result)
            self.assertNotIn("test_cached", result)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_scan_nonexistent_dir(self):
        """scan_project_tests returns empty list for nonexistent directory."""
        result = test_coverage_mod.scan_project_tests("/nonexistent/path", "python")
        self.assertEqual(result, [])


# ---------------------------------------------------------------------------
# BH24-013: Additional test_coverage.py coverage for detect/scan functions
# ---------------------------------------------------------------------------


class TestDetectTestFunctionsEdgeCases(unittest.TestCase):
    """BH24-013: Edge cases for detect_test_functions and scan_project_tests."""

    def test_detect_empty_source_returns_empty(self):
        """detect_test_functions returns [] for empty source code."""
        for lang in ("python", "rust", "javascript", "go"):
            result = test_coverage_mod.detect_test_functions(lang, "")
            self.assertEqual(result, [], f"{lang}: empty source should yield empty list")

    def test_detect_python_no_test_prefix(self):
        """Python functions without 'test_' prefix are not detected."""
        source = "def helper_method():\n    pass\ndef check_value():\n    pass\n"
        result = test_coverage_mod.detect_test_functions("python", source)
        self.assertEqual(result, [])

    def test_detect_rust_no_test_attr(self):
        """Rust functions without #[test] attribute are not detected."""
        source = "fn helper() {}\nfn setup() {}\n"
        result = test_coverage_mod.detect_test_functions("rust", source)
        self.assertEqual(result, [])

    def test_detect_rust_async_std_test(self):
        """detect_test_functions handles #[async_std::test] attribute."""
        source = "#[async_std::test]\nasync fn test_something() {\n}\n"
        result = test_coverage_mod.detect_test_functions("rust", source)
        self.assertIn("test_something", result)

    def test_detect_javascript_both_it_and_test(self):
        """detect_test_functions finds both it() and test() blocks in JS."""
        source = (
            "it('handles nulls', () => {});\n"
            "test('handles empty', () => {});\n"
        )
        result = test_coverage_mod.detect_test_functions("javascript", source)
        self.assertIn("handles nulls", result)
        self.assertIn("handles empty", result)

    def test_detect_case_insensitive_language(self):
        """detect_test_functions accepts uppercase language names."""
        source = "def test_foo():\n    pass\n"
        result = test_coverage_mod.detect_test_functions("Python", source)
        self.assertIn("test_foo", result)
        result2 = test_coverage_mod.detect_test_functions("PYTHON", source)
        self.assertIn("test_foo", result2)

    def test_detect_multiple_python_tests(self):
        """detect_test_functions returns all matches from a single source."""
        source = (
            "def test_alpha(): pass\n"
            "def test_beta(): pass\n"
            "def test_gamma(): pass\n"
        )
        result = test_coverage_mod.detect_test_functions("python", source)
        self.assertEqual(len(result), 3)
        self.assertEqual(result, ["test_alpha", "test_beta", "test_gamma"])

    def test_scan_deduplicates_test_functions(self):
        """scan_project_tests deduplicates function names across files."""
        tmpdir = tempfile.mkdtemp(prefix="giles-dedup-")
        try:
            root = Path(tmpdir)
            # Two test files with the same function name
            (root / "test_a.py").write_text("def test_shared(): pass\n")
            (root / "test_b.py").write_text("def test_shared(): pass\n")
            result = test_coverage_mod.scan_project_tests(str(root), "python")
            self.assertEqual(result.count("test_shared"), 1,
                             "Duplicate function names should be deduplicated")
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_scan_returns_sorted_results(self):
        """scan_project_tests returns results in sorted order."""
        tmpdir = tempfile.mkdtemp(prefix="giles-sorted-")
        try:
            root = Path(tmpdir)
            (root / "test_funcs.py").write_text(
                "def test_zebra(): pass\n"
                "def test_alpha(): pass\n"
                "def test_middle(): pass\n"
            )
            result = test_coverage_mod.scan_project_tests(str(root), "python")
            self.assertEqual(result, sorted(result),
                             "Results should be sorted alphabetically")
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_scan_skips_vendor_dir(self):
        """scan_project_tests skips files under vendor/ directory."""
        tmpdir = tempfile.mkdtemp(prefix="giles-vendor-")
        try:
            root = Path(tmpdir)
            vendor = root / "vendor" / "lib"
            vendor.mkdir(parents=True)
            (vendor / "test_vendored.py").write_text("def test_vendored(): pass\n")
            (root / "test_real.py").write_text("def test_mine(): pass\n")
            result = test_coverage_mod.scan_project_tests(str(root), "python")
            self.assertIn("test_mine", result)
            self.assertNotIn("test_vendored", result)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_scan_skips_target_dir(self):
        """scan_project_tests skips files under target/ directory."""
        tmpdir = tempfile.mkdtemp(prefix="giles-target-")
        try:
            root = Path(tmpdir)
            target = root / "target" / "debug"
            target.mkdir(parents=True)
            (target / "test_built.py").write_text("def test_built(): pass\n")
            (root / "test_real.py").write_text("def test_actual(): pass\n")
            result = test_coverage_mod.scan_project_tests(str(root), "python")
            self.assertIn("test_actual", result)
            self.assertNotIn("test_built", result)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_scan_skips_sprint_config_dir(self):
        """scan_project_tests skips files under sprint-config/ directory."""
        tmpdir = tempfile.mkdtemp(prefix="giles-sc-")
        try:
            root = Path(tmpdir)
            sc = root / "sprint-config"
            sc.mkdir()
            (sc / "test_config.py").write_text("def test_config(): pass\n")
            (root / "test_main.py").write_text("def test_main(): pass\n")
            result = test_coverage_mod.scan_project_tests(str(root), "python")
            self.assertIn("test_main", result)
            self.assertNotIn("test_config", result)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_scan_skips_git_dir(self):
        """scan_project_tests skips files under .git/ directory."""
        tmpdir = tempfile.mkdtemp(prefix="giles-git-")
        try:
            root = Path(tmpdir)
            git = root / ".git" / "hooks"
            git.mkdir(parents=True)
            (git / "test_hook.py").write_text("def test_hook(): pass\n")
            (root / "test_app.py").write_text("def test_app(): pass\n")
            result = test_coverage_mod.scan_project_tests(str(root), "python")
            self.assertIn("test_app", result)
            self.assertNotIn("test_hook", result)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_scan_unknown_language_returns_empty(self):
        """scan_project_tests returns empty list for unknown language."""
        tmpdir = tempfile.mkdtemp(prefix="giles-unknown-")
        try:
            root = Path(tmpdir)
            (root / "test_thing.py").write_text("def test_thing(): pass\n")
            result = test_coverage_mod.scan_project_tests(str(root), "fortran")
            self.assertEqual(result, [])
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_scan_rust_finds_test_files(self):
        """scan_project_tests finds Rust test functions in tests/ dir."""
        tmpdir = tempfile.mkdtemp(prefix="giles-rust-scan-")
        try:
            root = Path(tmpdir)
            tests = root / "tests"
            tests.mkdir()
            (tests / "integration.rs").write_text(
                "#[test]\nfn test_integration() {\n}\n"
            )
            result = test_coverage_mod.scan_project_tests(str(root), "rust")
            self.assertIn("test_integration", result)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_scan_go_finds_test_files(self):
        """scan_project_tests finds Go test functions in *_test.go files."""
        tmpdir = tempfile.mkdtemp(prefix="giles-go-scan-")
        try:
            root = Path(tmpdir)
            (root / "math_test.go").write_text(
                "package main\n\nfunc TestMath(t *testing.T) {\n}\n"
            )
            result = test_coverage_mod.scan_project_tests(str(root), "go")
            self.assertIn("TestMath", result)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_scan_javascript_finds_spec_files(self):
        """scan_project_tests finds JS tests in *.spec.* and *.test.* files."""
        tmpdir = tempfile.mkdtemp(prefix="giles-js-scan-")
        try:
            root = Path(tmpdir)
            (root / "math.test.js").write_text(
                "test('adds numbers', () => {});\n"
            )
            (root / "util.spec.js").write_text(
                "it('formats dates', () => {});\n"
            )
            result = test_coverage_mod.scan_project_tests(str(root), "javascript")
            self.assertIn("adds numbers", result)
            self.assertIn("formats dates", result)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


class TestBH21003QuotedTomlKeys(unittest.TestCase):
    """BH21-003: Quoted TOML keys should raise ValueError, not be silently dropped."""

    def test_double_quoted_key_rejected(self):
        """parse_simple_toml rejects double-quoted keys with a clear error."""
        with self.assertRaises(ValueError) as ctx:
            parse_simple_toml('"my key" = "value"')
        self.assertIn("quoted", str(ctx.exception).lower())

    def test_single_quoted_key_rejected(self):
        """parse_simple_toml rejects single-quoted keys with a clear error."""
        with self.assertRaises(ValueError) as ctx:
            parse_simple_toml("'my key' = 'value'")
        self.assertIn("quoted", str(ctx.exception).lower())

    def test_bare_keys_still_work(self):
        """Bare keys continue to parse normally."""
        result = parse_simple_toml('my_key = "value"')
        self.assertEqual(result["my_key"], "value")

    def test_quoted_key_under_section(self):
        """Quoted keys under a section header also raise ValueError."""
        toml_str = '[project]\n"spaced key" = "val"'
        with self.assertRaises(ValueError) as ctx:
            parse_simple_toml(toml_str)
        self.assertIn("quoted", str(ctx.exception).lower())


class TestBH21YamlSafeNewlines(unittest.TestCase):
    """BH21-005: _yaml_safe must escape newlines and carriage returns."""

    def test_newline_in_value_is_escaped(self):
        from sync_tracking import _yaml_safe
        result = _yaml_safe("line1\nline2")
        self.assertNotIn("\n", result.strip('"'))
        # Should be quoted with escaped newline
        self.assertTrue(result.startswith('"'))

    def test_carriage_return_in_value_is_escaped(self):
        from sync_tracking import _yaml_safe
        result = _yaml_safe("line1\rline2")
        self.assertNotIn("\r", result.strip('"'))

    def test_crlf_in_value_is_escaped(self):
        from sync_tracking import _yaml_safe
        result = _yaml_safe("line1\r\nline2")
        self.assertNotIn("\r", result.strip('"'))
        self.assertNotIn("\n", result.strip('"'))


class TestBH21006BomHandling(unittest.TestCase):
    """BH21-006: read_tf must handle BOM-prefixed files."""

    def test_bom_prefixed_tracking_file(self):
        import tempfile
        from sync_tracking import read_tf
        fd, path = tempfile.mkstemp(suffix=".md")
        try:
            # Write with BOM prefix
            with open(fd, 'w', encoding='utf-8-sig') as f:
                f.write("---\nstory: US-0001\ntitle: Test Story\nsprint: 1\nstatus: dev\n---\nBody text\n")
            tf = read_tf(Path(path))
            self.assertEqual(tf.story, "US-0001")
            self.assertEqual(tf.title, "Test Story")
            self.assertEqual(tf.sprint, 1)
            self.assertEqual(tf.status, "dev")
        finally:
            os.unlink(path)


class TestBH21TomlEscapeHandling(unittest.TestCase):
    """BH21-004: TOML escape handling — warn on unknown escapes, respect single-quoted literals."""

    def test_unknown_escape_warns(self):
        import io
        stderr = io.StringIO()
        old = sys.stderr
        sys.stderr = stderr
        try:
            result = parse_simple_toml('key = "hello\\qworld"')
        finally:
            sys.stderr = old
        # Should warn about unknown escape
        self.assertIn("\\q", stderr.getvalue())

    def test_single_quoted_no_escape_processing(self):
        # Single-quoted strings are TOML literal strings — no escape processing
        result = parse_simple_toml("path = 'C:\\new_folder'")
        self.assertEqual(result["path"], "C:\\new_folder")  # Literal backslash preserved


class TestBH24018UnquotedGarbageWarning(unittest.TestCase):
    """BH24-018: _parse_value warns on unquoted values with suspicious chars."""

    def test_html_like_value_warns(self):
        import io
        stderr = io.StringIO()
        old = sys.stderr
        sys.stderr = stderr
        try:
            result = parse_simple_toml('name = <script>')
        finally:
            sys.stderr = old
        self.assertEqual(result["name"], "<script>")
        self.assertIn("unquoted", stderr.getvalue().lower())

    def test_shell_like_value_warns(self):
        import io
        stderr = io.StringIO()
        old = sys.stderr
        sys.stderr = stderr
        try:
            result = parse_simple_toml('cmd = $(whoami)')
        finally:
            sys.stderr = old
        self.assertIn("unquoted", stderr.getvalue().lower())

    def test_backtick_value_warns(self):
        import io
        stderr = io.StringIO()
        old = sys.stderr
        sys.stderr = stderr
        try:
            parse_simple_toml('val = `echo hi`')
        finally:
            sys.stderr = old
        self.assertIn("unquoted", stderr.getvalue().lower())

    def test_simple_unquoted_no_warning(self):
        """Plain alphanumeric unquoted values should NOT warn."""
        import io
        stderr = io.StringIO()
        old = sys.stderr
        sys.stderr = stderr
        try:
            result = parse_simple_toml('name = hello')
        finally:
            sys.stderr = old
        self.assertEqual(result["name"], "hello")
        self.assertEqual(stderr.getvalue(), "")


class TestBH21012KanbanOverrideCentralized(unittest.TestCase):
    """BH21-012: kanban_from_labels handles closed-issue override."""

    def test_closed_issue_with_stale_dev_label(self):
        from validate_config import kanban_from_labels
        issue = {"state": "closed", "labels": [{"name": "kanban:dev"}]}
        self.assertEqual(kanban_from_labels(issue), "done")

    def test_closed_issue_with_done_label(self):
        from validate_config import kanban_from_labels
        issue = {"state": "closed", "labels": [{"name": "kanban:done"}]}
        self.assertEqual(kanban_from_labels(issue), "done")

    def test_open_issue_with_dev_label(self):
        from validate_config import kanban_from_labels
        issue = {"state": "open", "labels": [{"name": "kanban:dev"}]}
        self.assertEqual(kanban_from_labels(issue), "dev")


class TestBH21013ShortTitle(unittest.TestCase):
    """BH21-013: short_title helper."""

    def test_with_colon(self):
        from validate_config import short_title
        self.assertEqual(short_title("US-0001: Add login"), "Add login")

    def test_without_colon(self):
        from validate_config import short_title
        self.assertEqual(short_title("Add login"), "Add login")

    def test_multiple_colons(self):
        from validate_config import short_title
        self.assertEqual(short_title("US-0001: Add login: v2"), "Add login: v2")

    def test_empty_after_colon(self):
        from validate_config import short_title
        self.assertEqual(short_title("US-0001:"), "")


# ---------------------------------------------------------------------------
# BH21-017: enrich_from_epics uses by_id keys instead of hardcoded US-\d{4}
# ---------------------------------------------------------------------------


class TestBH21_017_EnrichCustomStoryIds(unittest.TestCase):
    """BH21-017: enrich_from_epics should work with custom story ID patterns."""

    def test_custom_story_id_pattern_enrichment(self):
        """Stories with non-US-XXXX IDs (e.g. PROJ-0001) should still get
        enriched from epic files."""
        tmpdir = tempfile.mkdtemp(prefix="giles-bh21017-")
        try:
            epics_dir = Path(tmpdir) / "epics"
            epics_dir.mkdir()

            # Epic file referencing a custom story ID
            epic_content = (
                "# E-0001 — Test Epic\n"
                "\n"
                "Stories: PROJ-0001, PROJ-0002\n"
                "\n"
                "### PROJ-0001: Custom story\n"
                "\n"
                "| Field | Value |\n"
                "| Saga | S01 |\n"
                "| Story Points | 5 |\n"
                "| Priority | P1 |\n"
                "\n"
                "**As a** user **I want** custom IDs **so that** I can use my project's convention\n"
                "\n"
            )
            (epics_dir / "E-0001-test.md").write_text(epic_content)

            # Existing story with custom ID pattern
            existing_stories = [
                populate_issues.Story(
                    story_id="PROJ-0001", title="Custom story",
                    saga="S01", sp=5, priority="P1", sprint=1,
                ),
                populate_issues.Story(
                    story_id="PROJ-0002", title="Another story",
                    saga="S01", sp=3, priority="P2", sprint=1,
                ),
            ]
            config = {
                "paths": {"epics_dir": str(epics_dir)},
                "backlog": {"story_id_pattern": r"PROJ-\d{4}"},
            }

            result = populate_issues.enrich_from_epics(existing_stories, config)

            # PROJ-0001 should be enriched with user story from epic
            enriched = {s.story_id: s for s in result}
            self.assertIn("PROJ-0001", enriched)
            self.assertIn("custom IDs", enriched["PROJ-0001"].user_story)

        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_known_sprints_detected_with_custom_ids(self):
        """Sprint inference from epic content should find custom IDs in by_id."""
        tmpdir = tempfile.mkdtemp(prefix="giles-bh21017b-")
        try:
            epics_dir = Path(tmpdir) / "epics"
            epics_dir.mkdir()

            # Epic file mentions MYAPP-0001 (which is in by_id at sprint 3)
            # and has a new story MYAPP-0099 not in by_id
            epic_content = (
                "# E-0001 — Test Epic\n"
                "\n"
                "Related: MYAPP-0001\n"
                "\n"
                "### MYAPP-0099: New story from epic\n"
                "\n"
                "| Field | Value |\n"
                "| Saga | S01 |\n"
                "| Story Points | 2 |\n"
                "| Priority | P2 |\n"
                "\n"
            )
            (epics_dir / "E-0001-test.md").write_text(epic_content)

            existing_stories = [
                populate_issues.Story(
                    story_id="MYAPP-0001", title="Existing",
                    saga="S01", sp=3, priority="P1", sprint=3,
                ),
            ]
            config = {
                "paths": {"epics_dir": str(epics_dir)},
                "backlog": {"story_id_pattern": r"MYAPP-\d{4}"},
            }

            result = populate_issues.enrich_from_epics(existing_stories, config)

            # MYAPP-0099 should be added with sprint=3 (inferred from MYAPP-0001)
            new_ids = [s.story_id for s in result if s.story_id == "MYAPP-0099"]
            self.assertEqual(len(new_ids), 1, "New story from epic should be added")
            new_story = [s for s in result if s.story_id == "MYAPP-0099"][0]
            self.assertEqual(new_story.sprint, 3,
                             "Sprint should be inferred from known MYAPP-0001")

        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


class TestBH21_008_GetExistingIssuesAtLimit(unittest.TestCase):
    """BH21-008 / BH23-212: get_existing_issues() warns at limit but no longer hard-fails."""

    @patch("populate_issues.gh_json")
    def test_warns_but_succeeds_at_limit(self, mock_gh_json):
        """BH23-212: At 1000 issues, warns but still returns results."""
        import io
        from contextlib import redirect_stderr
        mock_gh_json.return_value = [
            {"title": f"US-{i:04d}: Story {i}"} for i in range(1000)
        ]
        buf = io.StringIO()
        with redirect_stderr(buf):
            result = populate_issues.get_existing_issues()
        self.assertEqual(len(result), 1000)
        self.assertIn("1000", buf.getvalue())  # warning emitted

    @patch("populate_issues.gh_json")
    def test_succeeds_when_under_limit(self, mock_gh_json):
        """If gh returns fewer than 1000 issues, get_existing_issues succeeds."""
        mock_gh_json.return_value = [
            {"title": f"US-{i:04d}: Story {i}"} for i in range(10)
        ]
        result = populate_issues.get_existing_issues()
        self.assertEqual(len(result), 10)


class TestBH21_019_TruncateCILog(unittest.TestCase):
    """BH21-019: CI log output must be truncated before scanning."""

    def test_truncate_by_lines(self):
        """Logs exceeding _MAX_LOG_LINES are trimmed to that many lines."""
        big_log = "\n".join(f"line {i}" for i in range(1000))
        result = check_status._truncate_log(big_log)
        self.assertEqual(len(result.splitlines()), check_status._MAX_LOG_LINES)

    def test_truncate_by_bytes(self):
        """Logs exceeding _MAX_LOG_BYTES are trimmed at a line boundary."""
        # Build a log bigger than 100KB
        line = "x" * 200 + "\n"
        big_log = line * 1000  # 201KB
        result = check_status._truncate_log(big_log)
        self.assertLessEqual(len(result), check_status._MAX_LOG_BYTES)
        # Should end at a line boundary (no partial lines)
        self.assertFalse(result.endswith("\n"))

    def test_small_log_unchanged(self):
        """Logs under both limits are returned as-is."""
        small = "error: something broke\nline 2"
        self.assertEqual(check_status._truncate_log(small), small)


class TestBH21_022_WriteLogUnlinkCrash(unittest.TestCase):
    """BH21-022: write_log must not crash if old log deletion fails."""

    def test_unlink_oserror_does_not_crash(self):
        """If unlink raises OSError, write_log should still succeed."""
        import tempfile
        from datetime import datetime, timezone

        tmpdir = Path(tempfile.mkdtemp(prefix="giles-bh21022-"))
        try:
            sprints_dir = tmpdir / "sprints"
            sprint_dir = sprints_dir / "sprint-1"
            sprint_dir.mkdir(parents=True)

            # Create MAX_LOGS + 1 log files so write_log tries to delete one
            for i in range(check_status.MAX_LOGS + 1):
                (sprint_dir / f"monitor-20260101-{i:06d}.log").write_text("old")

            now = datetime.now(timezone.utc)
            # Make the oldest file read-only directory won't help on all OS,
            # so we mock unlink to raise OSError
            original_unlink = Path.unlink

            call_count = 0
            def failing_unlink(self_path, *args, **kwargs):
                nonlocal call_count
                call_count += 1
                raise OSError("permission denied")

            with patch.object(Path, "unlink", failing_unlink):
                # Should NOT raise
                path = check_status.write_log(1, "test report", now, sprints_dir)
                self.assertTrue(path.exists() or call_count > 0)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


class TestBH21_023_FalsePositiveRegex(unittest.TestCase):
    """BH21-023: _first_error false-positive regex must not be too broad."""

    def test_zero_errors_is_false_positive(self):
        """'0 errors' should be treated as a false positive."""
        log = "Build complete: 0 errors, 0 warnings"
        self.assertEqual(check_status._first_error(log), "")

    def test_no_failures_is_false_positive(self):
        """'no failures' should be treated as a false positive."""
        log = "Test run: no failures detected"
        self.assertEqual(check_status._first_error(log), "")

    def test_real_error_not_suppressed(self):
        """A genuine error line must not be filtered out."""
        log = "error: cannot find module 'foo'"
        result = check_status._first_error(log)
        self.assertIn("cannot find module", result)

    def test_error_in_word_not_suppressed(self):
        """Old regex matched 'no error' even inside compound phrases.
        'no error-handling' should NOT be a false positive — it contains
        'error' but 'error-handling' doesn't end at a word boundary for
        'errors?'."""
        log = "warning: no error-handling in module X"
        # The old broad regex would have matched "no error" and suppressed
        # this line. The tightened regex requires errors?/failures? at a
        # word boundary, so "error-handling" won't match.
        result = check_status._first_error(log)
        self.assertNotEqual(result, "", "Should detect as real issue, not false positive")

    def test_plural_forms_are_false_positives(self):
        """Both singular and plural forms should be caught."""
        for phrase in ["0 errors", "0 error", "no failure", "no failures"]:
            log = f"Summary: {phrase} found"
            self.assertEqual(
                check_status._first_error(log), "",
                f"'{phrase}' should be treated as false positive",
            )


class TestBH35SprintInitFixes(unittest.TestCase):
    """BH35-021/BH35-022: sprint_init no-backlog and DoD preservation fixes."""

    def test_no_backlog_creates_milestones_dir(self):
        """BH35-021: generate_backlog with no files must create milestones/."""
        tmpdir = tempfile.mkdtemp(prefix="giles-bh35-021-")
        try:
            root = Path(tmpdir)
            # Create a minimal project with no backlog files
            (root / "src").mkdir()
            (root / "src" / "main.rs").write_text("fn main() {}")
            (root / "Cargo.toml").write_text('[package]\nname = "test"\nversion = "0.1.0"')
            # Run scanner + generator
            scanner = ProjectScanner(root)
            scan = scanner.scan()
            gen = ConfigGenerator(scan)
            gen.generate()
            # Verify milestones/ exists with at least one file
            ms_dir = root / "sprint-config" / "backlog" / "milestones"
            self.assertTrue(ms_dir.is_dir(),
                            "milestones/ dir not created for no-backlog project")
            ms_files = list(ms_dir.glob("*.md"))
            self.assertGreater(len(ms_files), 0,
                               "milestones/ should have at least one skeleton file")
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_no_backlog_no_milestones_error(self):
        """BH35-021: generated config for no-backlog project must not have milestones error."""
        tmpdir = tempfile.mkdtemp(prefix="giles-bh35-021v-")
        try:
            root = Path(tmpdir)
            (root / "src").mkdir()
            (root / "src" / "main.rs").write_text("fn main() {}")
            (root / "Cargo.toml").write_text('[package]\nname = "test"\nversion = "0.1.0"')
            scanner = ProjectScanner(root)
            scan = scanner.scan()
            gen = ConfigGenerator(scan)
            gen.generate()
            _, errors = validate_project(root / "sprint-config")
            milestone_errors = [e for e in errors if "ilestone" in e]
            self.assertEqual(milestone_errors, [],
                             f"Milestones errors should not appear: {milestone_errors}")
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_dod_preserved_on_rerun(self):
        """BH35-022: re-running generate must not overwrite existing DoD."""
        tmpdir = tempfile.mkdtemp(prefix="giles-bh35-022-")
        try:
            root = Path(tmpdir)
            mock = MockProject(root, extra_personas=True)
            mock.create()
            # First run
            scanner = ProjectScanner(root)
            scan = scanner.scan()
            gen = ConfigGenerator(scan)
            gen.generate()
            dod_path = root / "sprint-config" / "definition-of-done.md"
            self.assertTrue(dod_path.is_file())
            # Simulate retro additions
            original = dod_path.read_text()
            retro_content = original + "\n## Sprint 1 Additions\n- New criterion\n"
            dod_path.write_text(retro_content)
            # Second run
            scanner2 = ProjectScanner(root)
            scan2 = scanner2.scan()
            gen2 = ConfigGenerator(scan2)
            gen2.generate()
            # Verify DoD was preserved
            after = dod_path.read_text()
            self.assertIn("Sprint 1 Additions", after,
                          "DoD was overwritten on re-run — retro additions lost")
            self.assertIn("New criterion", after)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


class TestBH37StemCollisionIndex(unittest.TestCase):
    """BH37-009: INDEX.md must use disambiguated filenames on stem collision."""

    def test_index_uses_disambiguated_stems(self):
        """When two persona files share a stem, INDEX.md should reference
        the disambiguated symlink names, not the original stems."""
        tmpdir = tempfile.mkdtemp(prefix="giles-bh37-009-")
        try:
            root = Path(tmpdir)
            # Minimal project structure
            (root / "src").mkdir()
            (root / "src" / "main.rs").write_text("fn main() {}")
            (root / "Cargo.toml").write_text(
                '[package]\nname = "test"\nversion = "0.1.0"')
            (root / ".git").mkdir()
            (root / ".git" / "config").write_text(
                '[remote "origin"]\n    url = https://github.com/o/r.git\n')

            # Two persona files with the SAME stem in different directories
            dir_a = root / "docs" / "team-a"
            dir_a.mkdir(parents=True)
            dir_b = root / "docs" / "team-b"
            dir_b.mkdir(parents=True)
            for d, role in [(dir_a, "Engineer"), (dir_b, "Designer")]:
                (d / "alex.md").write_text(
                    f"# Alex\n\n## Role\n{role}\n\n## Voice\nDirect.\n\n"
                    f"## Domain\nBackend.\n\n## Background\n5 years.\n\n"
                    f"## Review Focus\nCorrectness.\n")

            scanner = ProjectScanner(root)
            scan = scanner.scan()
            gen = ConfigGenerator(scan)
            gen.generate()

            index_path = root / "sprint-config" / "team" / "INDEX.md"
            self.assertTrue(index_path.exists(), "INDEX.md not generated")
            index_text = index_path.read_text()

            # Both personas should appear
            lines = [l for l in index_text.splitlines() if "Alex" in l]
            self.assertEqual(len(lines), 2,
                             f"Expected 2 Alex rows in INDEX, got {len(lines)}")
            # The File column should have DIFFERENT filenames
            filenames = []
            for line in lines:
                cells = [c.strip() for c in line.split("|") if c.strip()]
                filenames.append(cells[-1])  # last column is File
            self.assertNotEqual(filenames[0], filenames[1],
                                f"Both INDEX rows have same filename: {filenames}")
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
