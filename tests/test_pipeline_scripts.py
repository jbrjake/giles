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
sys.path.insert(0, str(ROOT / "skills" / "sprint-setup" / "scripts"))


# ---------------------------------------------------------------------------
# Task 0: Team Voices
# ---------------------------------------------------------------------------

from team_voices import extract_voices
from validate_config import parse_simple_toml
from setup_ci import generate_ci_yaml


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

    def test_extract_voices_from_epics_returns_empty(self):
        """Hexwise epic files have no team voice blocks — returns empty dict."""
        voices = extract_voices(
            epics_dir=str(HEXWISE / "docs" / "agile" / "epics"),
        )
        self.assertIsInstance(voices, dict)
        self.assertEqual(len(voices), 0, "Expected no voices in Hexwise epics")

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
        """With no test implementations, all planned tests are missing."""
        report = check_test_coverage(
            test_plan_dir=str(HEXWISE / "docs" / "test-plan"),
            project_root=str(HEXWISE),
            language="rust",
        )
        self.assertGreater(len(report["planned"]), 0)
        self.assertEqual(len(report["implemented"]), 0)
        # With no implementations, nothing can match — all planned are missing
        self.assertEqual(report["missing"], report["planned"])
        self.assertEqual(len(report.get("matched", [])), 0)

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
        """Fuzzy matching connects planned TC-001 to test_001_parse_hex."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            # Create a minimal test plan
            plan_dir = Path(tmp) / "plan"
            plan_dir.mkdir()
            (plan_dir / "tests.md").write_text(
                "### TC-001: Parse hex\n### TC-002: Parse RGB\n"
            )
            # Create actual test file — matches TC-001 via "001" slug
            test_dir = Path(tmp) / "project" / "tests"
            test_dir.mkdir(parents=True)
            (test_dir / "test_parse.py").write_text(
                "def test_tc_001_parse_hex():\n    pass\n"
            )
            report = check_test_coverage(
                test_plan_dir=str(plan_dir),
                project_root=str(Path(tmp) / "project"),
                language="python",
            )
            self.assertEqual(len(report["planned"]), 2)
            self.assertEqual(len(report["implemented"]), 1)
            self.assertIn("test_tc_001_parse_hex", report["implemented"])
            # TC-001 matched, TC-002 still missing
            self.assertIn("TC-001", report["matched"])
            self.assertNotIn("TC-001", report["missing"])
            self.assertIn("TC-002", report["missing"])


# ---------------------------------------------------------------------------
# Task 3: Epic Management
# ---------------------------------------------------------------------------

from manage_epics import parse_epic, add_story, remove_story, reorder_stories, renumber_stories


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

from manage_sagas import parse_saga, update_sprint_allocation, update_epic_index, update_team_voices


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


# ---------------------------------------------------------------------------
# Task 5: parse_simple_toml Edge Cases
# ---------------------------------------------------------------------------


class TestParseSimpleToml(unittest.TestCase):
    """Edge-case tests for the minimal TOML parser in validate_config.py."""

    def test_empty_input(self):
        """Empty string returns empty dict."""
        result = parse_simple_toml("")
        self.assertEqual(result, {})

    def test_malformed_quotes(self):
        """Unmatched quotes don't crash — value is returned as-is."""
        # Single unmatched opening quote: falls through to raw string fallback
        result = parse_simple_toml('key = "unterminated')
        self.assertIn("key", result)
        # The parser shouldn't raise; the value may be the raw string
        self.assertIsNotNone(result["key"])

    def test_multiline_arrays(self):
        """Arrays split across multiple lines parse correctly."""
        toml_text = (
            'items = [\n'
            '  "a",\n'
            '  "b",\n'
            ']'
        )
        result = parse_simple_toml(toml_text)
        self.assertEqual(result["items"], ["a", "b"])

    def test_inline_comments(self):
        """Trailing # comment after a value is stripped."""
        result = parse_simple_toml('key = "value" # this is a comment')
        self.assertEqual(result["key"], "value")

    def test_boolean_parsing(self):
        """Bare true/false parse to Python bools."""
        result = parse_simple_toml("enabled = true\ndisabled = false")
        self.assertIs(result["enabled"], True)
        self.assertIs(result["disabled"], False)

    def test_integer_parsing(self):
        """Bare integers parse to Python int."""
        result = parse_simple_toml("port = 42")
        self.assertEqual(result["port"], 42)
        self.assertIsInstance(result["port"], int)

    def test_nested_sections(self):
        """Dotted section header [a.b] creates nested dicts."""
        toml_text = "[a.b]\nkey = 1"
        result = parse_simple_toml(toml_text)
        self.assertEqual(result["a"]["b"]["key"], 1)

    def test_duplicate_sections(self):
        """A repeated [section] header merges keys, doesn't overwrite."""
        toml_text = (
            "[section]\n"
            "first = 1\n"
            "\n"
            "[section]\n"
            "second = 2\n"
        )
        result = parse_simple_toml(toml_text)
        self.assertEqual(result["section"]["first"], 1)
        self.assertEqual(result["section"]["second"], 2)

    def test_comments_only(self):
        """A file containing only comments returns empty dict."""
        toml_text = "# just a comment\n# another comment\n  # indented comment"
        result = parse_simple_toml(toml_text)
        self.assertEqual(result, {})


# ---------------------------------------------------------------------------
# P2-05: Non-Rust CI Generation
# ---------------------------------------------------------------------------


class TestCIGeneration(unittest.TestCase):
    """Verify CI YAML generation for Python, Node.js, and Go."""

    def test_python_ci_yaml(self):
        """Python config produces YAML with pip install, pytest, python."""
        config = {
            "project": {"name": "test", "language": "Python", "repo": "o/r"},
            "ci": {
                "check_commands": ["ruff check .", "pytest"],
                "build_command": "python -m build",
            },
        }
        yaml = generate_ci_yaml(config)
        self.assertIn("pip install", yaml)
        self.assertIn("pytest", yaml)
        self.assertIn("python", yaml)

    def test_node_ci_yaml(self):
        """Node config produces YAML with npm and node references."""
        config = {
            "project": {"name": "test", "language": "Node.js", "repo": "o/r"},
            "ci": {
                "check_commands": ["eslint .", "npm test"],
                "build_command": "npm run build",
            },
        }
        yaml = generate_ci_yaml(config)
        self.assertIn("npm", yaml)
        self.assertIn("node", yaml)

    def test_go_ci_yaml(self):
        """Go config produces YAML with go test and go vet."""
        config = {
            "project": {"name": "test", "language": "Go", "repo": "o/r"},
            "ci": {
                "check_commands": ["go vet ./...", "go test ./..."],
                "build_command": "go build ./...",
            },
        }
        yaml = generate_ci_yaml(config)
        self.assertIn("go test", yaml)
        self.assertIn("go vet", yaml)


# ---------------------------------------------------------------------------
# P2-08: Update Team Voices
# ---------------------------------------------------------------------------


class TestUpdateTeamVoices(unittest.TestCase):
    """Test update_team_voices in manage_sagas."""

    def _make_saga(self, tmp_path: Path) -> Path:
        """Create a minimal saga file with a Team Voices section."""
        saga = tmp_path / "S99-test.md"
        saga.write_text(
            "# S99 — Test Saga\n"
            "\n"
            "Introductory paragraph.\n"
            "\n"
            "## Team Voices\n"
            "\n"
            "> **Old Voice:** \"Placeholder.\"\n"
            "\n"
            "## Epic Index\n"
            "\n"
            "| Epic | Name | Stories | SP |\n"
            "|------|------|---------|-----|\n"
            "| E-9901 | Testing | 2 | 5 |\n",
            encoding="utf-8",
        )
        return saga

    def test_single_voice(self):
        """Single voice appears in blockquote; surrounding content preserved."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            saga_path = self._make_saga(Path(tmp))
            update_team_voices(str(saga_path), {"Ada": "I love types"})
            content = saga_path.read_text(encoding="utf-8")
            # Voice appears in blockquote format
            self.assertIn('> **Ada:** "I love types"', content)
            # Surrounding content preserved
            self.assertIn("# S99", content)
            self.assertIn("Introductory paragraph.", content)
            self.assertIn("## Epic Index", content)
            self.assertIn("E-9901", content)

    def test_multiple_voices(self):
        """Multiple voices all appear in the Team Voices section."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            saga_path = self._make_saga(Path(tmp))
            voices = {
                "Ada": "Types are everything",
                "Bob": "Ship it fast",
                "Cara": "Test it twice",
            }
            update_team_voices(str(saga_path), voices)
            content = saga_path.read_text(encoding="utf-8")
            self.assertIn('> **Ada:** "Types are everything"', content)
            self.assertIn('> **Bob:** "Ship it fast"', content)
            self.assertIn('> **Cara:** "Test it twice"', content)
            # Surrounding content still intact
            self.assertIn("## Epic Index", content)
            self.assertIn("E-9901", content)


# ---------------------------------------------------------------------------
# P2-09: Renumber Stories
# ---------------------------------------------------------------------------


class TestRenumberStories(unittest.TestCase):
    """Test renumber_stories in manage_epics."""

    def _make_epic(self, tmp_path: Path) -> Path:
        """Create a minimal epic with stories for renumber testing."""
        epic = tmp_path / "E-0101-test.md"
        epic.write_text(
            "# E-0101 — Test Epic\n"
            "\n"
            "| Field | Value |\n"
            "|-------|-------|\n"
            "| Saga | S01 |\n"
            "| Stories | 2 |\n"
            "| Total SP | 6 |\n"
            "\n"
            "---\n"
            "\n"
            "### US-0102: Parse RGB Input\n"
            "\n"
            "| Field | Value |\n"
            "|-------|-------|\n"
            "| Story Points | 3 |\n"
            "| Priority | P1 |\n"
            "| Blocked By | US-0101 |\n"
            "| Blocks | US-0102, US-0104 |\n"
            "| Test Cases | TC-PAR-002 |\n"
            "\n"
            "---\n"
            "\n"
            "### US-0100: Detect Format\n"
            "\n"
            "| Field | Value |\n"
            "|-------|-------|\n"
            "| Story Points | 3 |\n"
            "| Priority | P0 |\n"
            "| Blocked By | US-0102 |\n"
            "| Test Cases | TC-DET-001 |\n",
            encoding="utf-8",
        )
        return epic

    def test_renumber_preserves_headings(self):
        """Headings (### lines) are NOT modified; table rows ARE updated."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            epic_path = self._make_epic(Path(tmp))
            renumber_stories(
                str(epic_path), "US-0102", ["US-0102a", "US-0102b"]
            )
            content = epic_path.read_text(encoding="utf-8")
            # Heading for US-0102 is preserved unchanged
            self.assertIn("### US-0102: Parse RGB Input", content)
            # Table row referencing US-0102 in Blocks is renumbered
            self.assertIn("US-0102a, US-0102b", content)
            # Blocked By in the second story that references US-0102 is updated
            lines = content.splitlines()
            second_story_blocked = [
                l for l in lines
                if "Blocked By" in l and "US-0102" in l
                and not l.startswith("### ")
            ]
            # The second story's "Blocked By | US-0102" should be renumbered
            for bl in second_story_blocked:
                self.assertIn("US-0102a, US-0102b", bl)

    def test_renumber_word_boundary(self):
        """Renaming US-01 does NOT corrupt US-0100 or US-0102."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            # Create an epic that has US-01 and US-0100 references
            epic = tmp + "/E-test.md"
            Path(epic).write_text(
                "# E-test\n"
                "\n"
                "| Field | Value |\n"
                "|-------|-------|\n"
                "| Stories | 2 |\n"
                "\n"
                "---\n"
                "\n"
                "### US-01: First Story\n"
                "\n"
                "| Field | Value |\n"
                "|-------|-------|\n"
                "| Blocks | US-01, US-0100 |\n"
                "\n"
                "---\n"
                "\n"
                "### US-0100: Hundredth Story\n"
                "\n"
                "| Field | Value |\n"
                "|-------|-------|\n"
                "| Blocked By | US-01 |\n",
                encoding="utf-8",
            )
            renumber_stories(epic, "US-01", ["US-01a", "US-01b"])
            content = Path(epic).read_text(encoding="utf-8")
            # US-0100 in headings and table rows must be untouched
            self.assertIn("### US-0100: Hundredth Story", content)
            # US-0100 in table rows must NOT be corrupted
            # (word boundary ensures US-01 doesn't match US-0100)
            self.assertIn("US-0100", content)
            # Check that US-0100 was not turned into US-01a, US-01b00
            self.assertNotIn("US-01a, US-01b00", content)
            # The Blocked By for US-0100 that references US-01 IS updated
            lines = content.splitlines()
            blocked_by_lines = [
                l for l in lines if "Blocked By" in l and not l.startswith("### ")
            ]
            # Should have US-01a, US-01b in the blocked-by reference
            self.assertTrue(
                any("US-01a, US-01b" in l for l in blocked_by_lines),
                f"Expected 'US-01a, US-01b' in blocked-by lines: {blocked_by_lines}",
            )


if __name__ == "__main__":
    unittest.main()
