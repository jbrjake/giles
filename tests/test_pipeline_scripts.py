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


# ---------------------------------------------------------------------------
# Task 2: Test Coverage
# ---------------------------------------------------------------------------

from test_coverage import check_test_coverage, detect_test_functions


class TestCoverage(unittest.TestCase):
    """Compare planned test cases against actual test files."""

    def test_coverage_no_actual_tests(self):
        """Hexwise fixture has no actual test files (it's a fixture)."""
        report = check_test_coverage(
            test_plan_dir=str(HEXWISE / "docs" / "test-plan"),
            project_root=str(HEXWISE),
            language="rust",
        )
        self.assertGreater(len(report["planned"]), 0)
        self.assertEqual(len(report["implemented"]), 0)
        self.assertEqual(report["planned"], report["missing"])

    def test_coverage_language_detection_rust(self):
        """Detect #[test] fn patterns in Rust."""
        funcs = detect_test_functions("rust", '#[test]\nfn test_parsing() {')
        self.assertEqual(funcs, ["test_parsing"])

    def test_coverage_language_detection_python(self):
        """Detect def test_* patterns in Python."""
        funcs = detect_test_functions("python", 'def test_parsing(self):')
        self.assertEqual(funcs, ["test_parsing"])

    def test_coverage_language_detection_js(self):
        """Detect it/test patterns in JavaScript."""
        funcs = detect_test_functions("javascript", "it('should parse colors', () => {")
        self.assertEqual(funcs, ["should parse colors"])

    def test_coverage_language_detection_go(self):
        """Detect func Test* patterns in Go."""
        funcs = detect_test_functions("go", 'func TestParsing(t *testing.T) {')
        self.assertEqual(funcs, ["TestParsing"])

    def test_coverage_with_actual_tests(self):
        """Detect test functions when actual test files exist."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            # Create a minimal test plan
            plan_dir = Path(tmp) / "plan"
            plan_dir.mkdir()
            (plan_dir / "tests.md").write_text(
                "### TC-001: Parse hex\n### TC-002: Parse RGB\n"
            )
            # Create actual test file with one matching function
            test_dir = Path(tmp) / "project" / "tests"
            test_dir.mkdir(parents=True)
            (test_dir / "test_parse.py").write_text(
                "def test_parse_hex():\n    pass\n"
            )
            report = check_test_coverage(
                test_plan_dir=str(plan_dir),
                project_root=str(Path(tmp) / "project"),
                language="python",
            )
            self.assertEqual(len(report["planned"]), 2)
            self.assertEqual(len(report["implemented"]), 1)
            self.assertIn("test_parse_hex", report["implemented"])


# ---------------------------------------------------------------------------
# Task 3: Epic Management
# ---------------------------------------------------------------------------

from manage_epics import parse_epic, add_story, remove_story, reorder_stories


class TestManageEpics(unittest.TestCase):
    """CRUD operations on epic markdown files."""

    def _copy_epic(self, tmp_path: Path) -> Path:
        """Copy E-0101-parsing.md to tmp for mutation testing."""
        src = HEXWISE / "docs" / "agile" / "epics" / "E-0101-parsing.md"
        dst = tmp_path / "E-0101-parsing.md"
        shutil.copy2(src, dst)
        return dst

    def test_parse_epic_metadata(self):
        """Parse epic metadata (saga, stories count, total SP)."""
        epic = parse_epic(
            str(HEXWISE / "docs" / "agile" / "epics" / "E-0101-parsing.md")
        )
        self.assertEqual(epic["saga"], "S01")
        self.assertEqual(epic["stories_count"], 4)
        self.assertEqual(epic["total_sp"], 16)

    def test_parse_epic_stories(self):
        """Parse all stories from an epic file."""
        epic = parse_epic(
            str(HEXWISE / "docs" / "agile" / "epics" / "E-0101-parsing.md")
        )
        story_ids = [s["id"] for s in epic["stories"]]
        self.assertEqual(story_ids, ["US-0101", "US-0102", "US-0103", "US-0104"])

    def test_parse_epic_story_fields(self):
        """Each story includes key metadata fields."""
        epic = parse_epic(
            str(HEXWISE / "docs" / "agile" / "epics" / "E-0101-parsing.md")
        )
        us0101 = epic["stories"][0]
        self.assertEqual(us0101["id"], "US-0101")
        self.assertEqual(us0101["title"], "Parse Hex Color Input")
        self.assertEqual(us0101["story_points"], 3)
        self.assertEqual(us0101["priority"], "P0")

    def test_add_story_to_epic(self):
        """Add a new story to an epic file."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            epic_path = self._copy_epic(Path(tmp))
            add_story(str(epic_path), {
                "id": "US-0110",
                "title": "Parse CMYK Input",
                "story_points": 3,
                "priority": "P2",
                "personas": ["Rusti Ferris"],
                "blocked_by": ["US-0101"],
                "blocks": [],
                "test_cases": ["TC-PAR-010"],
                "acceptance_criteria": ["AC-01: Parse cmyk(C,M,Y,K) format"],
                "tasks": [{"id": "T-0110-01", "description": "Implement CMYK parser", "sp": 3}],
            })
            result = parse_epic(str(epic_path))
            story_ids = [s["id"] for s in result["stories"]]
            self.assertIn("US-0110", story_ids)
            # Verify it appears in the file content
            content = epic_path.read_text()
            self.assertIn("US-0110", content)
            self.assertIn("Parse CMYK Input", content)

    def test_remove_story(self):
        """Remove a story from an epic file."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            epic_path = self._copy_epic(Path(tmp))
            remove_story(str(epic_path), "US-0103")
            result = parse_epic(str(epic_path))
            story_ids = [s["id"] for s in result["stories"]]
            self.assertNotIn("US-0103", story_ids)
            self.assertIn("US-0101", story_ids)
            self.assertIn("US-0102", story_ids)

    def test_reorder_stories(self):
        """Reorder stories within an epic."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            epic_path = self._copy_epic(Path(tmp))
            reorder_stories(str(epic_path), ["US-0104", "US-0101", "US-0102", "US-0103"])
            result = parse_epic(str(epic_path))
            story_ids = [s["id"] for s in result["stories"]]
            self.assertEqual(story_ids, ["US-0104", "US-0101", "US-0102", "US-0103"])


# ---------------------------------------------------------------------------
# Task 3: Saga Management
# ---------------------------------------------------------------------------

from manage_sagas import parse_saga, update_sprint_allocation, update_epic_index


class TestManageSagas(unittest.TestCase):
    """CRUD operations on saga markdown files."""

    def _copy_saga(self, tmp_path: Path) -> Path:
        """Copy S01-core.md to tmp for mutation testing."""
        src = HEXWISE / "docs" / "agile" / "sagas" / "S01-core.md"
        dst = tmp_path / "S01-core.md"
        shutil.copy2(src, dst)
        return dst

    def test_parse_saga_metadata(self):
        """Parse saga metadata (stories, epics, total SP)."""
        saga = parse_saga(
            str(HEXWISE / "docs" / "agile" / "sagas" / "S01-core.md")
        )
        self.assertEqual(saga["stories_count"], 8)
        self.assertEqual(saga["epics_count"], 3)
        self.assertEqual(saga["total_sp"], 34)

    def test_parse_saga_epic_index(self):
        """Parse epic index table from saga."""
        saga = parse_saga(
            str(HEXWISE / "docs" / "agile" / "sagas" / "S01-core.md")
        )
        epic_ids = [e["id"] for e in saga["epic_index"]]
        self.assertEqual(epic_ids, ["E-0101", "E-0102", "E-0103"])

    def test_parse_saga_sprint_allocation(self):
        """Parse sprint allocation table from saga."""
        saga = parse_saga(
            str(HEXWISE / "docs" / "agile" / "sagas" / "S01-core.md")
        )
        self.assertEqual(len(saga["sprint_allocation"]), 2)
        self.assertEqual(saga["sprint_allocation"][0]["sprint"], "Sprint 1")

    def test_update_sprint_allocation(self):
        """Update sprint allocation table in a saga."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            saga_path = self._copy_saga(Path(tmp))
            new_allocation = [
                {"sprint": "Sprint 1", "stories": "US-0101, US-0102", "sp": "11"},
                {"sprint": "Sprint 2", "stories": "US-0103, US-0104, US-0105, US-0106, US-0107, US-0108", "sp": "23"},
            ]
            update_sprint_allocation(str(saga_path), new_allocation)
            result = parse_saga(str(saga_path))
            self.assertEqual(result["sprint_allocation"][0]["stories"], "US-0101, US-0102")
            self.assertEqual(result["sprint_allocation"][0]["sp"], "11")

    def test_update_epic_index(self):
        """Update epic index from epic files."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            saga_path = self._copy_saga(Path(tmp))
            epics_dir = str(HEXWISE / "docs" / "agile" / "epics")
            update_epic_index(str(saga_path), epics_dir, saga_id="S01")
            result = parse_saga(str(saga_path))
            # Should still have 3 epics for S01
            self.assertEqual(len(result["epic_index"]), 3)


if __name__ == "__main__":
    unittest.main()
