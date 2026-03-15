#!/usr/bin/env python3
"""Tests for migrate_to_anchors.py."""
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from migrate_to_anchors import insert_source_anchors, build_anchor_name


class TestBuildAnchorName(unittest.TestCase):
    """Derive §namespace.symbol from file path and symbol name."""

    def test_shared_script(self):
        name = build_anchor_name("scripts/validate_config.py", "parse_simple_toml")
        self.assertEqual(name, "validate_config.parse_simple_toml")

    def test_skill_script(self):
        name = build_anchor_name(
            "skills/sprint-setup/scripts/bootstrap_github.py", "create_label"
        )
        self.assertEqual(name, "bootstrap_github.create_label")

    def test_strips_parens(self):
        name = build_anchor_name("scripts/validate_config.py", "gh()")
        self.assertEqual(name, "validate_config.gh")

    def test_strips_asterisks(self):
        name = build_anchor_name("scripts/validate_config.py", "_REQUIRED_FILES")
        self.assertEqual(name, "validate_config._REQUIRED_FILES")


class TestInsertSourceAnchors(unittest.TestCase):
    """Insert # §... comments into Python source files."""

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        src = self.tmpdir / "scripts"
        src.mkdir()
        (src / "mymod.py").write_text(textwrap.dedent("""\
            import os

            def my_func():
                pass

            class MyClass:
                pass

            MY_CONST = 42
        """))

    def test_inserts_anchor_above_function(self):
        refs = [("scripts/mymod.py", "my_func", 3, 1)]
        count = insert_source_anchors(refs, root=self.tmpdir)
        self.assertEqual(count, 1)
        content = (self.tmpdir / "scripts" / "mymod.py").read_text()
        lines = content.splitlines()
        anchor_idx = next(i for i, l in enumerate(lines) if "§mymod.my_func" in l)
        self.assertIn("def my_func", lines[anchor_idx + 1])

    def test_skips_if_anchor_exists(self):
        (self.tmpdir / "scripts" / "mymod.py").write_text(
            "# §mymod.my_func\ndef my_func():\n    pass\n"
        )
        refs = [("scripts/mymod.py", "my_func", 2, 1)]
        count = insert_source_anchors(refs, root=self.tmpdir)
        self.assertEqual(count, 0)

    def test_handles_multiple_refs_same_file(self):
        refs = [
            ("scripts/mymod.py", "my_func", 3, 1),
            ("scripts/mymod.py", "MyClass", 6, 2),
            ("scripts/mymod.py", "MY_CONST", 9, 3),
        ]
        count = insert_source_anchors(refs, root=self.tmpdir)
        self.assertEqual(count, 3)
        content = (self.tmpdir / "scripts" / "mymod.py").read_text()
        self.assertIn("# §mymod.my_func", content)
        self.assertIn("# §mymod.MyClass", content)
        self.assertIn("# §mymod.MY_CONST", content)


from migrate_to_anchors import rewrite_claude_md_refs


class TestRewriteClaudeMd(unittest.TestCase):
    """Rewrite :NN refs in CLAUDE.md-style tables."""

    def test_table_symbol_ref(self):
        line = "| `scripts/validate_config.py` | desc | `parse_simple_toml()` :47, `load_config()` :457 |"
        result = rewrite_claude_md_refs(line)
        self.assertIn("§validate_config.parse_simple_toml", result)
        self.assertIn("§validate_config.load_config", result)
        self.assertNotIn(":47", result)
        self.assertNotIn(":457", result)

    def test_skill_entry_point_ref(self):
        line = "| sprint-run | `skills/sprint-run/SKILL.md` | Phase detection :29, Phase 1: Kickoff :44 |"
        result = rewrite_claude_md_refs(line)
        self.assertNotIn(":29", result)
        self.assertNotIn(":44", result)

    def test_prose_file_ref(self):
        line = "see `validate_config.py:304`"
        result = rewrite_claude_md_refs(line)
        self.assertNotIn(":304", result)
        self.assertIn("§validate_config.validate_project", result)

    def test_no_ref_unchanged(self):
        line = "This line has no references."
        result = rewrite_claude_md_refs(line)
        self.assertEqual(result, line)


if __name__ == "__main__":
    unittest.main()
