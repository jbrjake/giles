"""Tests for scripts/check_lint_inventory.py."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import check_lint_inventory
from check_lint_inventory import extract_lint_files, discover_scripts


class TestExtractLintFiles(unittest.TestCase):
    """Parse py_compile entries from a Makefile."""

    def test_extracts_paths(self):
        with tempfile.NamedTemporaryFile("w", suffix="Makefile", delete=False) as f:
            f.write(
                "lint:\n"
                "\t$(PYTHON) -m py_compile scripts/foo.py\n"
                "\t$(PYTHON) -m py_compile hooks/bar.py\n"
            )
            f.flush()
            result = extract_lint_files(Path(f.name))
        self.assertEqual(result, {"scripts/foo.py", "hooks/bar.py"})

    def test_ignores_commented_py_compile_lines(self):
        with tempfile.NamedTemporaryFile("w", suffix="Makefile", delete=False) as f:
            f.write(
                "lint:\n"
                "# py_compile scripts/old.py\n"
                "\t# $(PYTHON) -m py_compile scripts/also_old.py\n"
                "\t$(PYTHON) -m py_compile scripts/real.py\n"
            )
            f.flush()
            result = extract_lint_files(Path(f.name))
        self.assertEqual(result, {"scripts/real.py"})

    def test_ignores_non_py_compile_lines(self):
        with tempfile.NamedTemporaryFile("w", suffix="Makefile", delete=False) as f:
            f.write(
                "lint:\n"
                "\t$(PYTHON) scripts/validate_anchors.py\n"
                "\t$(PYTHON) -m py_compile scripts/real.py\n"
            )
            f.flush()
            result = extract_lint_files(Path(f.name))
        self.assertEqual(result, {"scripts/real.py"})


class TestDiscoverScripts(unittest.TestCase):
    """Find .py files on disk."""

    def test_finds_scripts_and_hooks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "scripts").mkdir()
            (root / "scripts" / "one.py").touch()
            (root / "hooks").mkdir()
            (root / "hooks" / "two.py").touch()
            # __init__.py should be excluded
            (root / "hooks" / "__init__.py").touch()

            result = discover_scripts(root)
            self.assertEqual(result, {"scripts/one.py", "hooks/two.py"})

    def test_finds_skill_scripts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "scripts").mkdir()
            skill_dir = root / "skills" / "my-skill" / "scripts"
            skill_dir.mkdir(parents=True)
            (skill_dir / "do_thing.py").touch()

            result = discover_scripts(root)
            self.assertEqual(result, {"skills/my-skill/scripts/do_thing.py"})

    def test_empty_dirs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            # no scripts/ or hooks/ dirs at all
            result = discover_scripts(root)
            self.assertEqual(result, set())


class TestLiveInventory(unittest.TestCase):
    """Verify the real Makefile covers all scripts (integration test)."""

    def test_no_missing_scripts(self):
        root = Path(__file__).resolve().parent.parent
        makefile = root / "Makefile"
        if not makefile.exists():
            self.skipTest("no Makefile")

        lint_files = extract_lint_files(makefile)
        disk_files = discover_scripts(root)
        missing = disk_files - lint_files

        self.assertEqual(
            missing,
            set(),
            f"Scripts not in Makefile lint target: {sorted(missing)}",
        )


class TestMain(unittest.TestCase):
    """Integration test for main() entry point."""

    def test_main_returns_zero_when_synced(self):
        """main() should return 0 when Makefile covers all scripts."""
        rc = check_lint_inventory.main()
        self.assertEqual(rc, 0)

    def test_main_returns_one_when_missing(self):
        """main() should return 1 when a script is missing from Makefile."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "scripts").mkdir()
            (root / "scripts" / "orphan.py").touch()
            makefile = root / "Makefile"
            makefile.write_text("lint:\n\techo noop\n")

            rc = check_lint_inventory.main(root=root)
            self.assertEqual(rc, 1)

    def test_main_returns_zero_for_stale_only(self):
        """main() returns 0 when Makefile has entries for non-existent scripts."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            # No scripts/ or hooks/ dirs — all Makefile entries are stale
            makefile = root / "Makefile"
            makefile.write_text(
                "lint:\n"
                "\t$(PYTHON) -m py_compile scripts/ghost.py\n"
            )

            rc = check_lint_inventory.main(root=root)
            self.assertEqual(rc, 0, "Stale-only should return 0 (warning, not error)")
