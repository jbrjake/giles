#!/usr/bin/env python3
"""Tests for validate_anchors.py."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from validate_anchors import resolve_namespace, NAMESPACE_MAP


class TestNamespaceMap(unittest.TestCase):
    """Namespace-to-file resolution."""

    def test_shared_script_namespace(self):
        path = resolve_namespace("validate_config")
        self.assertEqual(path, "scripts/validate_config.py")

    def test_skill_script_namespace(self):
        path = resolve_namespace("bootstrap_github")
        self.assertEqual(path, "skills/sprint-setup/scripts/bootstrap_github.py")

    def test_skill_md_namespace(self):
        path = resolve_namespace("sprint-run")
        self.assertEqual(path, "skills/sprint-run/SKILL.md")

    def test_reference_md_namespace(self):
        path = resolve_namespace("ceremony-kickoff")
        self.assertEqual(path, "skills/sprint-run/references/ceremony-kickoff.md")

    def test_agent_namespace(self):
        path = resolve_namespace("implementer")
        self.assertEqual(path, "skills/sprint-run/agents/implementer.md")

    def test_unknown_namespace_raises(self):
        with self.assertRaises(KeyError):
            resolve_namespace("nonexistent")

    def test_all_mapped_files_exist(self):
        for ns, rel_path in NAMESPACE_MAP.items():
            full = ROOT / rel_path
            self.assertTrue(full.exists(), f"§{ns} -> {rel_path} does not exist")


import tempfile
import textwrap

from validate_anchors import find_anchor_defs


class TestFindAnchorDefs(unittest.TestCase):
    """Scan files for anchor definition comments."""

    def test_python_function_anchor(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(textwrap.dedent("""\
                # §mymod.my_func
                def my_func():
                    pass
            """))
            f.flush()
            defs = find_anchor_defs(Path(f.name))
        self.assertEqual(defs, {"mymod.my_func": 1})

    def test_markdown_heading_anchor(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write(textwrap.dedent("""\
                # Title
                <!-- §sprint-run.kickoff -->
                ## Kickoff
            """))
            f.flush()
            defs = find_anchor_defs(Path(f.name))
        self.assertEqual(defs, {"sprint-run.kickoff": 2})

    def test_multiple_anchors(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(textwrap.dedent("""\
                # §mod.func_a
                def func_a():
                    pass

                # §mod.CONST_B
                CONST_B = 42
            """))
            f.flush()
            defs = find_anchor_defs(Path(f.name))
        self.assertEqual(len(defs), 2)
        self.assertIn("mod.func_a", defs)
        self.assertIn("mod.CONST_B", defs)

    def test_no_anchors_returns_empty(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("def plain_func():\n    pass\n")
            f.flush()
            defs = find_anchor_defs(Path(f.name))
        self.assertEqual(defs, {})


from validate_anchors import find_anchor_refs


class TestFindAnchorRefs(unittest.TestCase):
    """Scan doc files for §-prefixed references."""

    def test_table_cell_refs(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("| `scripts/foo.py` | `bar()` §foo.bar, `baz()` §foo.baz |\n")
            f.flush()
            refs = find_anchor_refs(Path(f.name))
        names = [r[0] for r in refs]
        self.assertEqual(names, ["foo.bar", "foo.baz"])

    def test_anchor_column_ref(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("| §validate_config.gh | `gh()` | Wrapper |\n")
            f.flush()
            refs = find_anchor_refs(Path(f.name))
        self.assertEqual(refs[0][0], "validate_config.gh")

    def test_prose_ref(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("See §sprint-run.kickoff for details.\n")
            f.flush()
            refs = find_anchor_refs(Path(f.name))
        self.assertEqual(refs[0][0], "sprint-run.kickoff")

    def test_no_refs_returns_empty(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("No anchor references here.\n")
            f.flush()
            refs = find_anchor_refs(Path(f.name))
        self.assertEqual(refs, [])

    def test_ref_includes_line_number(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("line one\n§foo.bar on line two\n")
            f.flush()
            refs = find_anchor_refs(Path(f.name))
        self.assertEqual(refs[0], ("foo.bar", 2))


import os

from validate_anchors import check_anchors


class TestCheckAnchors(unittest.TestCase):
    """End-to-end check mode."""

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        # Create a minimal source file with an anchor
        src = self.tmpdir / "scripts"
        src.mkdir()
        (src / "mymod.py").write_text(
            "# §mymod.my_func\ndef my_func():\n    pass\n"
        )
        # Create a doc file referencing it
        (self.tmpdir / "DOC.md").write_text(
            "| `scripts/mymod.py` | `my_func()` §mymod.my_func |\n"
        )

    def test_all_refs_resolve(self):
        ns_map = {"mymod": "scripts/mymod.py"}
        broken, unreferenced = check_anchors(
            root=self.tmpdir,
            doc_files=["DOC.md"],
            namespace_map=ns_map,
        )
        self.assertEqual(broken, [])

    def test_broken_ref_detected(self):
        (self.tmpdir / "DOC.md").write_text("See §mymod.nonexistent\n")
        ns_map = {"mymod": "scripts/mymod.py"}
        broken, unreferenced = check_anchors(
            root=self.tmpdir,
            doc_files=["DOC.md"],
            namespace_map=ns_map,
        )
        self.assertEqual(len(broken), 1)
        self.assertIn("nonexistent", broken[0])

    def test_unknown_namespace_is_broken(self):
        (self.tmpdir / "DOC.md").write_text("See §typomod.func\n")
        ns_map = {"mymod": "scripts/mymod.py"}
        broken, _ = check_anchors(
            root=self.tmpdir,
            doc_files=["DOC.md"],
            namespace_map=ns_map,
        )
        self.assertEqual(len(broken), 1)
        self.assertIn("typomod", broken[0])

    def test_unreferenced_anchor_reported(self):
        (self.tmpdir / "DOC.md").write_text("No refs here.\n")
        ns_map = {"mymod": "scripts/mymod.py"}
        _, unreferenced = check_anchors(
            root=self.tmpdir,
            doc_files=["DOC.md"],
            namespace_map=ns_map,
        )
        self.assertEqual(len(unreferenced), 1)
        self.assertIn("mymod.my_func", unreferenced[0])


if __name__ == "__main__":
    unittest.main()
