#!/usr/bin/env python3
"""Unit tests for scripts/sprint_teardown.py.

Tests classify_entries(), collect_directories(), remove_symlinks(),
remove_generated(), remove_empty_dirs(), and resolve_symlink_target()
using temporary directories with real symlinks and files.

Run: python -m unittest tests.test_sprint_teardown -v
"""
from __future__ import annotations

import os
import tempfile
import unittest
import unittest.mock
from pathlib import Path
from unittest.mock import patch

import sprint_teardown


class TestClassifyEntries(unittest.TestCase):
    """Test classify_entries() classification of symlinks, generated, and unknown files."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.config_dir = Path(self.tmpdir) / "sprint-config"
        self.config_dir.mkdir()

    def tearDown(self):
        # Clean up anything left over
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_symlink_file_classified(self):
        """A file symlink should appear in the symlinks list."""
        target = Path(self.tmpdir) / "real-file.md"
        target.write_text("original content")
        link = self.config_dir / "rules.md"
        link.symlink_to(target)

        symlinks, generated, unknown = sprint_teardown.classify_entries(self.config_dir)
        self.assertEqual(len(symlinks), 1)
        self.assertEqual(symlinks[0], link)
        self.assertEqual(len(generated), 0)
        self.assertEqual(len(unknown), 0)

    def test_generated_project_toml(self):
        """project.toml should be classified as generated."""
        (self.config_dir / "project.toml").write_text("[project]\nname = \"test\"")

        symlinks, generated, unknown = sprint_teardown.classify_entries(self.config_dir)
        self.assertEqual(len(symlinks), 0)
        self.assertEqual(len(generated), 1)
        self.assertEqual(generated[0].name, "project.toml")
        self.assertEqual(len(unknown), 0)

    def test_generated_index_md(self):
        """INDEX.md should be classified as generated."""
        (self.config_dir / "INDEX.md").write_text("# Index")

        symlinks, generated, unknown = sprint_teardown.classify_entries(self.config_dir)
        self.assertEqual(len(generated), 1)
        self.assertEqual(generated[0].name, "INDEX.md")

    def test_unknown_file_classified(self):
        """A regular file not in generated_names should be classified as unknown."""
        (self.config_dir / "custom-notes.txt").write_text("my notes")

        symlinks, generated, unknown = sprint_teardown.classify_entries(self.config_dir)
        self.assertEqual(len(symlinks), 0)
        self.assertEqual(len(generated), 0)
        self.assertEqual(len(unknown), 1)
        self.assertEqual(unknown[0].name, "custom-notes.txt")

    def test_mixed_entries(self):
        """Mix of symlinks, generated, and unknown files."""
        # Symlink
        target = Path(self.tmpdir) / "real.md"
        target.write_text("content")
        (self.config_dir / "rules.md").symlink_to(target)

        # Generated
        (self.config_dir / "project.toml").write_text("[project]")
        (self.config_dir / "INDEX.md").write_text("# Index")

        # Unknown
        (self.config_dir / "scratch.txt").write_text("scratch")

        symlinks, generated, unknown = sprint_teardown.classify_entries(self.config_dir)
        self.assertEqual(len(symlinks), 1)
        self.assertEqual(len(generated), 2)
        self.assertEqual(len(unknown), 1)

    def test_directory_symlink_classified(self):
        """A symlinked directory should appear in symlinks and not be descended into."""
        real_dir = Path(self.tmpdir) / "real-team"
        real_dir.mkdir()
        (real_dir / "persona.md").write_text("persona content")

        link = self.config_dir / "team"
        link.symlink_to(real_dir)

        symlinks, generated, unknown = sprint_teardown.classify_entries(self.config_dir)
        self.assertEqual(len(symlinks), 1)
        self.assertEqual(symlinks[0], link)
        # Files inside the symlinked directory should NOT appear
        self.assertEqual(len(generated), 0)
        self.assertEqual(len(unknown), 0)

    def test_nested_directory_entries(self):
        """Files in subdirectories should be classified correctly."""
        sub = self.config_dir / "backlog"
        sub.mkdir()
        (sub / "INDEX.md").write_text("# Backlog Index")
        (sub / "notes.txt").write_text("notes")

        target = Path(self.tmpdir) / "milestone.md"
        target.write_text("milestone content")
        (sub / "milestone.md").symlink_to(target)

        symlinks, generated, unknown = sprint_teardown.classify_entries(self.config_dir)
        self.assertEqual(len(symlinks), 1)
        self.assertEqual(symlinks[0].name, "milestone.md")
        self.assertEqual(len(generated), 1)
        self.assertEqual(generated[0].name, "INDEX.md")
        self.assertEqual(len(unknown), 1)
        self.assertEqual(unknown[0].name, "notes.txt")

    def test_empty_directory(self):
        """An empty config directory should return empty lists."""
        symlinks, generated, unknown = sprint_teardown.classify_entries(self.config_dir)
        self.assertEqual(symlinks, [])
        self.assertEqual(generated, [])
        self.assertEqual(unknown, [])

    def test_results_are_sorted(self):
        """Returned lists should be sorted by path."""
        (self.config_dir / "project.toml").write_text("[project]")

        sub = self.config_dir / "backlog"
        sub.mkdir()
        (sub / "INDEX.md").write_text("# Backlog")

        symlinks, generated, unknown = sprint_teardown.classify_entries(self.config_dir)
        self.assertEqual(len(generated), 2)
        self.assertTrue(generated[0] < generated[1])


class TestCollectDirectories(unittest.TestCase):
    """Test collect_directories() ordering and symlink handling."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.config_dir = Path(self.tmpdir) / "sprint-config"
        self.config_dir.mkdir()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_includes_config_dir_itself(self):
        """The config_dir itself should be in the returned list."""
        dirs = sprint_teardown.collect_directories(self.config_dir)
        self.assertIn(self.config_dir, dirs)

    def test_deepest_first_ordering(self):
        """Subdirectories should come before their parents."""
        child = self.config_dir / "team"
        child.mkdir()
        grandchild = child / "history"
        grandchild.mkdir()

        dirs = sprint_teardown.collect_directories(self.config_dir)
        idx_grandchild = dirs.index(grandchild)
        idx_child = dirs.index(child)
        idx_root = dirs.index(self.config_dir)
        self.assertLess(idx_grandchild, idx_child)
        self.assertLess(idx_child, idx_root)

    def test_excludes_symlinked_directories(self):
        """Symlinked directories should not appear as real directories."""
        real_dir = Path(self.tmpdir) / "real-team"
        real_dir.mkdir()
        link = self.config_dir / "team"
        link.symlink_to(real_dir)

        dirs = sprint_teardown.collect_directories(self.config_dir)
        self.assertNotIn(link, dirs)
        self.assertIn(self.config_dir, dirs)


class TestResolveSymlinkTarget(unittest.TestCase):
    """Test resolve_symlink_target() for valid and broken symlinks."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_valid_symlink(self):
        target = Path(self.tmpdir) / "real.md"
        target.write_text("content")
        link = Path(self.tmpdir) / "link.md"
        link.symlink_to(target)

        result = sprint_teardown.resolve_symlink_target(link)
        self.assertIsNotNone(result)
        self.assertEqual(result, target.resolve())

    def test_broken_symlink(self):
        target = Path(self.tmpdir) / "nonexistent.md"
        link = Path(self.tmpdir) / "link.md"
        link.symlink_to(target)

        result = sprint_teardown.resolve_symlink_target(link)
        self.assertIsNone(result)


class TestRemoveSymlinks(unittest.TestCase):
    """Test remove_symlinks() removes symlinks but leaves targets intact."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.project_root = Path(self.tmpdir)
        self.config_dir = self.project_root / "sprint-config"
        self.config_dir.mkdir()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_removes_symlinks_preserves_targets(self):
        """Symlinks should be removed while original files remain untouched."""
        target = self.project_root / "RULES.md"
        target.write_text("project rules")

        link = self.config_dir / "rules.md"
        link.symlink_to(target)

        count = sprint_teardown.remove_symlinks([link], self.project_root)
        self.assertEqual(count, 1)
        self.assertFalse(link.exists())
        self.assertTrue(target.exists())
        self.assertEqual(target.read_text(), "project rules")

    def test_removes_multiple_symlinks(self):
        """All symlinks in the list should be removed."""
        targets = []
        links = []
        for name in ("RULES.md", "DEVELOPMENT.md", "persona.md"):
            t = self.project_root / name
            t.write_text(f"content of {name}")
            targets.append(t)
            lnk = self.config_dir / name
            lnk.symlink_to(t)
            links.append(lnk)

        count = sprint_teardown.remove_symlinks(links, self.project_root)
        self.assertEqual(count, 3)
        for lnk in links:
            self.assertFalse(lnk.exists())
        for t in targets:
            self.assertTrue(t.exists())

    def test_empty_list(self):
        count = sprint_teardown.remove_symlinks([], self.project_root)
        self.assertEqual(count, 0)


class TestRemoveGenerated(unittest.TestCase):
    """Test remove_generated() with force mode."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.project_root = Path(self.tmpdir)
        self.config_dir = self.project_root / "sprint-config"
        self.config_dir.mkdir()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_force_removes_all(self):
        """With force=True, all generated files should be removed without prompting."""
        files = []
        for name in ("project.toml", "INDEX.md"):
            f = self.config_dir / name
            f.write_text("generated")
            files.append(f)

        count = sprint_teardown.remove_generated(files, self.project_root, force=True)
        self.assertEqual(count, 2)
        for f in files:
            self.assertFalse(f.exists())

    def test_empty_list(self):
        count = sprint_teardown.remove_generated([], self.project_root, force=True)
        self.assertEqual(count, 0)

    @patch("builtins.input", side_effect=["y", "n"])
    def test_interactive_yes_no(self, mock_input):
        """Interactive mode: 'y' removes, 'n' skips."""
        f1 = self.config_dir / "project.toml"
        f1.write_text("gen1")
        f2 = self.config_dir / "INDEX.md"
        f2.write_text("gen2")

        count = sprint_teardown.remove_generated([f1, f2], self.project_root, force=False)
        self.assertEqual(count, 1)
        self.assertFalse(f1.exists())
        self.assertTrue(f2.exists())

    @patch("builtins.input", side_effect=["a"])
    def test_interactive_all(self, mock_input):
        """Interactive mode: 'a' removes all remaining files."""
        f1 = self.config_dir / "project.toml"
        f1.write_text("gen1")
        f2 = self.config_dir / "INDEX.md"
        f2.write_text("gen2")

        count = sprint_teardown.remove_generated([f1, f2], self.project_root, force=False)
        self.assertEqual(count, 2)
        self.assertFalse(f1.exists())
        self.assertFalse(f2.exists())


class TestRemoveEmptyDirs(unittest.TestCase):
    """Test remove_empty_dirs() removes only empty directories."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.project_root = Path(self.tmpdir)
        self.config_dir = self.project_root / "sprint-config"
        self.config_dir.mkdir()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_removes_empty_dirs(self):
        child = self.config_dir / "team"
        child.mkdir()
        dirs = [child, self.config_dir]

        count = sprint_teardown.remove_empty_dirs(dirs, self.project_root)
        self.assertEqual(count, 2)
        self.assertFalse(child.exists())
        self.assertFalse(self.config_dir.exists())

    def test_skips_nonempty_dirs(self):
        child = self.config_dir / "team"
        child.mkdir()
        (child / "file.txt").write_text("keep me")

        dirs = [child, self.config_dir]
        count = sprint_teardown.remove_empty_dirs(dirs, self.project_root)
        # child has a file so neither child nor config_dir can be removed
        self.assertEqual(count, 0)
        self.assertTrue(child.exists())

    def test_deepest_first_cascading_removal(self):
        """When deepest dirs are empty, their parents become empty and can also be removed."""
        grandchild = self.config_dir / "team" / "history"
        grandchild.mkdir(parents=True)

        dirs = sprint_teardown.collect_directories(self.config_dir)
        count = sprint_teardown.remove_empty_dirs(dirs, self.project_root)
        # grandchild, team, sprint-config all empty and removed in order
        self.assertEqual(count, 3)
        self.assertFalse(self.config_dir.exists())


class TestFullTeardownFlow(unittest.TestCase):
    """Integration-style test: classify, remove, verify originals intact."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.project_root = Path(self.tmpdir)
        self.config_dir = self.project_root / "sprint-config"
        self.config_dir.mkdir()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_teardown_preserves_originals(self):
        """Full classify-then-remove flow: symlinks and generated files removed,
        original files survive, unknown files skipped."""
        # Create original project files
        rules = self.project_root / "RULES.md"
        rules.write_text("# Project Rules")
        dev = self.project_root / "DEVELOPMENT.md"
        dev.write_text("# Dev Guide")

        # Create symlinks in config dir
        (self.config_dir / "rules.md").symlink_to(rules)
        (self.config_dir / "development.md").symlink_to(dev)

        # Create generated files
        (self.config_dir / "project.toml").write_text('[project]\nname = "test"')
        team_dir = self.config_dir / "team"
        team_dir.mkdir()
        (team_dir / "INDEX.md").write_text("# Team Index")

        # Create an unknown file
        (self.config_dir / "custom.txt").write_text("user notes")

        # Classify
        symlinks, generated, unknown = sprint_teardown.classify_entries(self.config_dir)
        self.assertEqual(len(symlinks), 2)
        self.assertEqual(len(generated), 2)
        self.assertEqual(len(unknown), 1)

        # Remove symlinks
        sprint_teardown.remove_symlinks(symlinks, self.project_root)

        # Remove generated (force mode)
        sprint_teardown.remove_generated(generated, self.project_root, force=True)

        # Originals should still exist
        self.assertTrue(rules.exists())
        self.assertEqual(rules.read_text(), "# Project Rules")
        self.assertTrue(dev.exists())
        self.assertEqual(dev.read_text(), "# Dev Guide")

        # Unknown file should still exist (we did not remove it)
        self.assertTrue((self.config_dir / "custom.txt").exists())

        # Symlinks and generated files should be gone
        self.assertFalse((self.config_dir / "rules.md").exists())
        self.assertFalse((self.config_dir / "development.md").exists())
        self.assertFalse((self.config_dir / "project.toml").exists())
        self.assertFalse((team_dir / "INDEX.md").exists())


# ---------------------------------------------------------------------------
# P5-25: sprint_teardown main() tests
# ---------------------------------------------------------------------------


class TestTeardownMainDryRun(unittest.TestCase):
    """P5-25: main() dry-run mode."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.project_root = Path(self.tmpdir)
        self.config_dir = self.project_root / "sprint-config"
        self.config_dir.mkdir()
        # Create a symlink and a generated file
        orig = self.project_root / "RULES.md"
        orig.write_text("# Rules")
        (self.config_dir / "rules.md").symlink_to(orig)
        (self.config_dir / "project.toml").write_text('[project]\nname = "test"')
        self._saved_cwd = os.getcwd()
        os.chdir(self.project_root)

    def tearDown(self):
        os.chdir(self._saved_cwd)
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_dry_run_preserves_files(self):
        """Dry run should not remove any files."""
        with unittest.mock.patch(
            "sys.argv", ["teardown", "--dry-run"],
        ), self.assertRaises(SystemExit) as ctx:
            sprint_teardown.main()
        self.assertEqual(ctx.exception.code, 0)
        # Files should still exist after dry run
        self.assertTrue((self.config_dir / "rules.md").exists())
        self.assertTrue((self.config_dir / "project.toml").exists())


class TestTeardownMainExecute(unittest.TestCase):
    """P5-25: main() execute mode."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.project_root = Path(self.tmpdir)
        self.config_dir = self.project_root / "sprint-config"
        self.config_dir.mkdir()
        # Create a generated file only (no symlinks, no unknowns)
        (self.config_dir / "project.toml").write_text('[project]\nname = "test"')
        # Create RULES.md and DEVELOPMENT.md to satisfy verification
        (self.project_root / "RULES.md").write_text("# Rules")
        (self.project_root / "DEVELOPMENT.md").write_text("# Dev")
        self._saved_cwd = os.getcwd()
        os.chdir(self.project_root)

    def tearDown(self):
        os.chdir(self._saved_cwd)
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_execute_removes_generated(self):
        """Execute mode removes generated files and cleans up."""
        with unittest.mock.patch(
            "sys.argv", ["teardown", "--force"],
        ), unittest.mock.patch(
            "sprint_teardown.check_active_loops", return_value=[],
        ):
            sprint_teardown.main()
        # Generated file should be removed
        self.assertFalse((self.config_dir / "project.toml").exists())

    def test_no_config_dir_exits_cleanly(self):
        """main() exits cleanly when sprint-config/ doesn't exist."""
        import shutil
        shutil.rmtree(self.config_dir)
        with unittest.mock.patch(
            "sys.argv", ["teardown"],
        ), self.assertRaises(SystemExit) as ctx:
            sprint_teardown.main()
        self.assertEqual(ctx.exception.code, 0)


if __name__ == "__main__":
    unittest.main()
