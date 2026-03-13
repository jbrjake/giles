#!/usr/bin/env python3
"""Tests for pipeline scripts (Chunk 4).

Covers: team_voices, traceability, test_coverage, manage_epics, manage_sagas.
Uses the Hexwise fixture at tests/fixtures/hexwise/.

Run: python -m unittest tests.test_pipeline_scripts -v
"""
from __future__ import annotations

import shutil
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HEXWISE = ROOT / "tests" / "fixtures" / "hexwise"
sys.path.insert(0, str(ROOT / "scripts"))


# ---------------------------------------------------------------------------
# Task 0: Team Voices
# ---------------------------------------------------------------------------

from team_voices import extract_voices


class TestTeamVoices(unittest.TestCase):
    """Extract persona commentary from saga/epic files."""

    def test_extract_voices_from_sagas(self):
        """Extract team voices from Hexwise saga files."""
        voices = extract_voices(
            sagas_dir=str(HEXWISE / "docs" / "agile" / "sagas"),
        )
        self.assertIn("Rusti Ferris", voices)
        self.assertIn("Palette Jones", voices)
        self.assertIn("Checker Macready", voices)
        # S01-core.md has all three personas
        rusti_quotes = [v for v in voices["Rusti Ferris"] if "S01" in v["file"]]
        self.assertGreaterEqual(len(rusti_quotes), 1)
        self.assertIn("type system", rusti_quotes[0]["quote"].lower())

    def test_extract_voices_from_epics(self):
        """Epic files don't have team voice blocks in Hexwise."""
        voices = extract_voices(
            epics_dir=str(HEXWISE / "docs" / "agile" / "epics"),
        )
        self.assertIsInstance(voices, dict)

    def test_extract_voices_empty_dir(self):
        """Gracefully handle directories with no persona commentary."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            voices = extract_voices(sagas_dir=tmp)
            self.assertEqual(voices, {})

    def test_extract_voices_both_sagas(self):
        """Both S01 and S02 have voices for all three personas."""
        voices = extract_voices(
            sagas_dir=str(HEXWISE / "docs" / "agile" / "sagas"),
        )
        for persona in ("Rusti Ferris", "Palette Jones", "Checker Macready"):
            files = {v["file"] for v in voices[persona]}
            self.assertIn("S01-core.md", files)
            self.assertIn("S02-toolkit.md", files)

    def test_extract_voices_section_context(self):
        """Voices include the section heading they appear under."""
        voices = extract_voices(
            sagas_dir=str(HEXWISE / "docs" / "agile" / "sagas"),
        )
        rusti_s01 = [v for v in voices["Rusti Ferris"] if v["file"] == "S01-core.md"]
        self.assertEqual(rusti_s01[0]["section"], "Team Voices")

    def test_continuation_lines_joined(self):
        """Multi-line blockquotes are joined into a single quote string."""
        voices = extract_voices(
            sagas_dir=str(HEXWISE / "docs" / "agile" / "sagas"),
        )
        rusti_s01 = [v for v in voices["Rusti Ferris"] if v["file"] == "S01-core.md"]
        # The quote spans 4 lines in the fixture — should be a single string
        self.assertIn("compiler", rusti_s01[0]["quote"].lower())


# ---------------------------------------------------------------------------
# Task 1: Traceability
# ---------------------------------------------------------------------------

from traceability import build_traceability, parse_stories, parse_requirements


class TestTraceability(unittest.TestCase):
    """Bidirectional story/PRD/test mapping with gap detection."""

    def test_parse_stories_finds_all(self):
        """Parse all 17 stories from Hexwise epic files."""
        stories = parse_stories(str(HEXWISE / "docs" / "agile" / "epics"))
        story_ids = sorted(stories.keys())
        self.assertEqual(len(story_ids), 17)
        self.assertIn("US-0101", story_ids)
        self.assertIn("US-0209", story_ids)

    def test_parse_stories_extracts_test_cases(self):
        """Each story has test case references from its metadata table."""
        stories = parse_stories(str(HEXWISE / "docs" / "agile" / "epics"))
        self.assertIn("TC-PAR-001", stories["US-0101"]["test_cases"])
        self.assertIn("GP-001", stories["US-0101"]["test_cases"])

    def test_traceability_no_gaps(self):
        """Hexwise has complete story-to-test traceability."""
        report = build_traceability(
            epics_dir=str(HEXWISE / "docs" / "agile" / "epics"),
            test_plan_dir=str(HEXWISE / "docs" / "test-plan"),
        )
        self.assertEqual(report["stories_without_tests"], [])

    def test_traceability_detects_gaps(self):
        """Detect stories that have no test case links."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            epic = Path(tmp) / "E-0101-test.md"
            epic.write_text(
                "### US-9999: Untested Story\n\n"
                "| Field | Value |\n|---|---|\n| Story Points | 3 |\n"
            )
            report = build_traceability(epics_dir=tmp)
            self.assertIn("US-9999", report["stories_without_tests"])

    def test_traceability_prd_coverage(self):
        """All REQ-* IDs in Hexwise PRDs map to stories."""
        report = build_traceability(
            epics_dir=str(HEXWISE / "docs" / "agile" / "epics"),
            prd_dir=str(HEXWISE / "docs" / "prd"),
        )
        self.assertEqual(report["requirements_without_stories"], [])

    def test_parse_requirements_finds_all(self):
        """Parse all REQ-* IDs from Hexwise PRD reference files."""
        reqs = parse_requirements(str(HEXWISE / "docs" / "prd"))
        req_ids = sorted(reqs.keys())
        self.assertIn("REQ-PAR-001", req_ids)
        self.assertIn("REQ-CON-001", req_ids)
        self.assertIn("REQ-PAL-001", req_ids)
        # Each requirement maps to at least one story
        for req_id, data in reqs.items():
            self.assertGreater(len(data["stories"]), 0, f"{req_id} has no story links")


if __name__ == "__main__":
    unittest.main()
