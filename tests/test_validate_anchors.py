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


if __name__ == "__main__":
    unittest.main()
