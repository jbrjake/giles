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
from sprint_init import ProjectScanner


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

from traceability import build_traceability, parse_stories, parse_requirements, format_report


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

    def test_format_report_includes_gaps(self):
        """BH23-117: format_report lists uncovered stories by name."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            epic = Path(tmp) / "E-0101-test.md"
            epic.write_text(
                "### US-8888: Untested Feature\n\n"
                "| Field | Value |\n|---|---|\n| Story Points | 5 |\n"
            )
            report = build_traceability(epics_dir=tmp)
            formatted = format_report(report)
            self.assertIn("Stories Without Test Coverage", formatted)
            self.assertIn("US-8888", formatted)
            self.assertIn("Untested Feature", formatted)


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
        # Verify specific planned IDs appear in missing, not just that sets match
        planned_ids = set(report["planned"])
        missing_ids = set(report["missing"])
        self.assertTrue(planned_ids, "Expected non-empty planned test cases")
        self.assertEqual(planned_ids, missing_ids,
                         "All planned tests should be missing when none implemented")
        # Spot-check: at least one known test case ID from the hexwise fixture
        self.assertTrue(
            any(tc_id.startswith("TC-") or tc_id.startswith("GP-")
                for tc_id in planned_ids),
            f"Expected TC-/GP-prefixed IDs, got: {planned_ids}",
        )
        self.assertEqual(len(report.get("matched", [])), 0)

    def test_coverage_language_detection_rust(self):
        """Detect #[test] fn patterns in Rust."""
        funcs = detect_test_functions("rust", '#[test]\nfn test_parsing() {')
        self.assertEqual(funcs, ["test_parsing"])

    def test_coverage_rust_tokio_test(self):
        """BH-014: detect #[tokio::test] async fn in Rust."""
        funcs = detect_test_functions("rust", '#[tokio::test]\nasync fn test_async_thing() {')
        self.assertEqual(funcs, ["test_async_thing"])

    def test_coverage_rust_async_std_test(self):
        """BH-014: detect #[async_std::test] async fn in Rust."""
        funcs = detect_test_functions("rust", '#[async_std::test]\nasync fn test_another() {')
        self.assertEqual(funcs, ["test_another"])

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

    def test_remove_story_nonexistent_id(self):
        """Removing a story ID that doesn't exist should not crash or alter the file."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            epic_path = self._copy_epic(Path(tmp))
            original_content = epic_path.read_text()
            # remove_story with a non-existent ID should return silently
            remove_story(str(epic_path), "US-9999")
            after_content = epic_path.read_text()
            self.assertEqual(original_content, after_content)
            # All original stories should still be present
            result = parse_epic(str(epic_path))
            story_ids = [s["id"] for s in result["stories"]]
            self.assertIn("US-0101", story_ids)
            self.assertIn("US-0102", story_ids)

    def test_parse_epic_empty_file(self):
        """Parsing an empty file should return a valid structure without crashing."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            empty_path = Path(tmp) / "empty-epic.md"
            empty_path.write_text("")
            result = parse_epic(str(empty_path))
            self.assertEqual(result["title"], "")
            self.assertEqual(result["stories"], [])
            self.assertEqual(result["raw_sections"], [])
            self.assertEqual(result["stories_count"], 0)
            self.assertEqual(result["total_sp"], 0)


    def test_format_story_section_missing_keys(self):
        """BH-005: _format_story_section with missing keys uses defaults."""
        from manage_epics import _format_story_section
        result = _format_story_section({"id": "US-001", "title": "Test"})
        self.assertIn("US-001", result)
        self.assertIn("Test", result)
        # Should have defaults for missing fields
        self.assertIn("Story Points", result)

    def test_format_story_section_empty_dict(self):
        """BH-005: _format_story_section({}) does not crash."""
        from manage_epics import _format_story_section
        result = _format_story_section({})
        self.assertIn("US-XXXX", result)
        self.assertIn("Untitled", result)

    def test_add_story_duplicate_raises(self):
        """BH-011: adding a story with an existing ID raises ValueError."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            epic_path = self._copy_epic(Path(tmp))
            with self.assertRaises(ValueError) as ctx:
                add_story(str(epic_path), {
                    "id": "US-0101",  # already exists
                    "title": "Duplicate",
                    "story_points": 1,
                    "priority": "P2",
                })
            self.assertIn("US-0101", str(ctx.exception))


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

    def test_parse_saga_malformed_file(self):
        """Parsing a file with no proper saga structure should not crash."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            malformed_path = Path(tmp) / "bad-saga.md"
            malformed_path.write_text(
                "This is just random text.\n"
                "No tables, no headings, no structure.\n"
                "Just plain prose that is not a saga.\n"
            )
            result = parse_saga(str(malformed_path))
            self.assertEqual(result["title"], "This is just random text.")
            self.assertEqual(result["stories_count"], 0)
            self.assertEqual(result["epics_count"], 0)
            self.assertEqual(result["total_sp"], 0)
            self.assertEqual(result["epic_index"], [])
            self.assertEqual(result["sprint_allocation"], [])
            self.assertEqual(result["section_ranges"], {})


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
        """Unmatched quotes don't crash — value is returned as raw string."""
        # Single unmatched opening quote: falls through to raw string fallback
        result = parse_simple_toml('key = "unterminated')
        self.assertIn("key", result)
        # No closing quote → not parsed as string → returned as raw fallback
        self.assertEqual(result["key"], '"unterminated')

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

    def test_escaped_backslash_before_quote(self):
        """BH3-05: Even backslashes before quote end the string correctly.

        TOML ``"hello\\\\\\\\"`` has two escaped backslashes (``\\\\`` each),
        yielding the Python string ``hello\\\\`` after unescape.
        """
        result = parse_simple_toml(r'items = ["hello\\"]')
        self.assertIn("items", result)
        self.assertEqual(result["items"], ["hello\\"])

    def test_escaped_quote_in_array(self):
        """Odd backslashes before quote → escaped quote, not end of string."""
        result = parse_simple_toml(r'items = ["say \"hi\"", "ok"]')
        self.assertEqual(len(result["items"]), 2)
        self.assertEqual(result["items"][1], "ok")

    def test_unterminated_multiline_array_raises(self):
        """P5-03: EOF with open multiline array raises ValueError."""
        toml_text = (
            '[section]\n'
            'items = [\n'
            '  "a",\n'
            '  "b"\n'
            # missing closing ]
        )
        with self.assertRaises(ValueError) as ctx:
            parse_simple_toml(toml_text)
        self.assertIn("items", str(ctx.exception))

    def test_unterminated_array_at_end_of_file(self):
        """P5-03: Multiline array at end of file with no closing bracket."""
        toml_text = (
            'name = "test"\n'
            'items = [\n'
            '  "a",\n'
            '  "b"\n'
        )
        with self.assertRaises(ValueError):
            parse_simple_toml(toml_text)

    def test_single_quote_preserves_hash(self):
        """P6-12: Single-quoted TOML literal string preserves # inside."""
        result = parse_simple_toml("key = 'has # inside'")
        self.assertEqual(result["key"], "has # inside")

    def test_single_quote_with_double_inside(self):
        """P6-12: Single-quoted string containing double quotes."""
        result = parse_simple_toml("key = 'say \"hi\"'")
        self.assertEqual(result["key"], 'say "hi"')

    def test_double_quote_with_single_inside(self):
        """P6-12: Double-quoted string containing single quotes."""
        result = parse_simple_toml("key = \"it's fine\"")
        self.assertEqual(result["key"], "it's fine")

    def test_unquoted_string_accepted(self):
        """P6-13: Unquoted values accepted as raw strings (intentional leniency)."""
        result = parse_simple_toml("key = hello world")
        self.assertEqual(result["key"], "hello world")

    # -- P7-01: Single-quoted arrays ----------------------------------------

    def test_single_quote_array_with_comma(self):
        """P7-01: Single-quoted array element containing a comma."""
        result = parse_simple_toml("items = ['has, comma', 'ok']")
        self.assertEqual(result["items"], ["has, comma", "ok"])

    def test_mixed_quote_array(self):
        """P7-01: Array with mixed single- and double-quoted elements."""
        result = parse_simple_toml("mixed = ['a, b', \"c, d\"]")
        self.assertEqual(result["mixed"], ["a, b", "c, d"])

    # -- P7-09: Direct _split_array tests -----------------------------------

    def test_split_array_empty_input(self):
        """P7-09: _split_array on empty string returns empty list."""
        from validate_config import _split_array
        self.assertEqual(_split_array(""), [])

    def test_split_array_single_element(self):
        """P7-09: _split_array with one unquoted element."""
        from validate_config import _split_array
        self.assertEqual(_split_array('"hello"'), ['"hello"'])

    def test_split_array_trailing_comma(self):
        """P7-09: _split_array ignores trailing comma (empty tail)."""
        from validate_config import _split_array
        self.assertEqual(_split_array('"a", "b",'), ['"a"', ' "b"'])

    def test_split_array_escaped_quote_inside_string(self):
        """P7-09: _split_array with escaped quote inside double-quoted string."""
        from validate_config import _split_array
        result = _split_array(r'"say \"hi\"", "ok"')
        self.assertEqual(len(result), 2)

    def test_split_array_single_quotes_with_comma(self):
        """P7-09: _split_array respects single-quoted strings with commas."""
        from validate_config import _split_array
        result = _split_array("'has, comma', 'ok'")
        self.assertEqual(len(result), 2)

    def test_split_array_mixed_quotes(self):
        """P7-09: _split_array with mixed quote types."""
        from validate_config import _split_array
        result = _split_array("'a, b', \"c, d\"")
        self.assertEqual(len(result), 2)

    def test_split_array_whitespace_only(self):
        """P7-09: _split_array with whitespace-only input returns empty list."""
        from validate_config import _split_array
        self.assertEqual(_split_array("   "), [])


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

    def test_unsupported_language_produces_todo_comment(self):
        """Unsupported language (e.g. Haskell) produces a TODO setup comment, not a crash."""
        config = {
            "project": {"name": "test", "language": "Haskell", "repo": "o/r"},
            "ci": {
                "check_commands": ["cabal test"],
                "build_command": "cabal build",
            },
        }
        yaml = generate_ci_yaml(config)
        # Should not crash and should produce valid YAML structure
        self.assertIn("name: CI", yaml)
        self.assertIn("jobs:", yaml)
        # Should contain a TODO comment for the unsupported language
        self.assertIn("TODO", yaml)
        self.assertIn("haskell", yaml.lower())
        # The check commands should still appear
        self.assertIn("cabal test", yaml)

    def test_generated_yaml_has_valid_structure(self):
        """BH24-007: Validate YAML structure beyond keyword presence.

        Checks that generated CI YAML has proper top-level keys, job
        structure (runs-on, steps), and consistent indentation — without
        importing a YAML parser.
        """
        config = {
            "project": {"name": "test", "language": "Python", "repo": "o/r"},
            "ci": {
                "check_commands": ["ruff check .", "pytest"],
                "build_command": "python -m build",
            },
        }
        yaml = generate_ci_yaml(config)
        lines = yaml.splitlines()

        # Top-level: must start with "name: CI"
        self.assertTrue(
            lines[0].startswith("name:"),
            f"YAML should start with 'name:' key, got: {lines[0]!r}",
        )

        # Required top-level keys (no leading whitespace)
        top_keys = [l.split(":")[0] for l in lines if l and not l[0].isspace() and ":" in l]
        self.assertIn("name", top_keys)
        self.assertIn("on", top_keys)
        self.assertIn("jobs", top_keys)

        # "jobs:" must appear and the next non-blank line must be indented
        jobs_idx = next(i for i, l in enumerate(lines) if l.strip() == "jobs:")
        next_content = next(
            (l for l in lines[jobs_idx + 1:] if l.strip()), None,
        )
        self.assertIsNotNone(next_content, "Expected content after 'jobs:'")
        self.assertTrue(
            next_content.startswith("  "),
            f"Job definition should be indented under 'jobs:', got: {next_content!r}",
        )

        # At least one job must have "runs-on:" and "steps:"
        self.assertTrue(
            any(l.strip().startswith("runs-on:") for l in lines),
            "Generated YAML should contain 'runs-on:' in a job definition",
        )
        self.assertTrue(
            any(l.strip().startswith("steps:") for l in lines),
            "Generated YAML should contain 'steps:' in a job definition",
        )

        # Steps should use "- name:" or "- uses:" entries (standard GHA format)
        step_entries = [l for l in lines if l.strip().startswith("- name:") or l.strip().startswith("- uses:")]
        self.assertGreaterEqual(
            len(step_entries), 1,
            "Expected at least one step with '- name:' or '- uses:'",
        )

        # Indentation consistency: no tabs (YAML best practice)
        for i, line in enumerate(lines, 1):
            self.assertNotIn(
                "\t", line,
                f"Line {i} contains a tab character; YAML should use spaces",
            )


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

    def test_multiple_voices_separate_blockquotes(self):
        """BH-P11-113: Multiple voices must be separate blockquotes, not merged."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            saga_path = self._make_saga(Path(tmp))
            voices = {"Ada": "Types matter", "Bob": "Speed matters"}
            update_team_voices(str(saga_path), voices)
            lines = saga_path.read_text(encoding="utf-8").splitlines()
            # Find the voice lines
            ada_idx = next(i for i, l in enumerate(lines) if "Ada" in l)
            bob_idx = next(i for i, l in enumerate(lines) if "Bob" in l)
            # Between them there must be a non-blockquote line (empty line)
            between = lines[ada_idx + 1:bob_idx]
            has_separator = any(not line.startswith(">") for line in between)
            self.assertTrue(has_separator,
                            f"Voices should be separate blockquotes, but got: {between}")


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

    def test_renumber_body_text_multiple_references(self):
        """BH23-214: Comma-joined replacement in body text is parseable."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            epic = tmp + "/E-body.md"
            Path(epic).write_text(
                "# E-body\n\n"
                "---\n\n"
                "### US-0050: Story\n\n"
                "| Field | Value |\n"
                "|-------|-------|\n"
                "| Blocked By | US-0050 |\n"
                "| Blocks | US-0050 |\n",
                encoding="utf-8",
            )
            renumber_stories(epic, "US-0050", ["US-0050a", "US-0050b"])
            content = Path(epic).read_text(encoding="utf-8")
            # Heading preserved
            self.assertIn("### US-0050: Story", content)
            # Both metadata fields replaced with comma-joined IDs
            lines = [l for l in content.splitlines() if "US-0050" in l and "|" in l]
            for line in lines:
                self.assertIn("US-0050a, US-0050b", line)


# ---------------------------------------------------------------------------
# P2-04: Scanner Heuristic Fixtures — Python Project
# ---------------------------------------------------------------------------


class TestScannerPythonProject(unittest.TestCase):
    """Scanner heuristics against a Python project layout.

    Fixture: pyproject.toml at root, tests/ dir, docs/prd/ for PRDs,
    docs/test-plan/ for test plans, no sagas or epics.
    """

    def setUp(self):
        import tempfile
        self._tmpdir = tempfile.mkdtemp()
        root = Path(self._tmpdir)

        # Language marker
        (root / "pyproject.toml").write_text(
            '[project]\nname = "widgetlib"\nversion = "0.1.0"\n',
            encoding="utf-8",
        )

        # Source directory
        (root / "src" / "widgetlib").mkdir(parents=True)
        (root / "src" / "widgetlib" / "__init__.py").write_text(
            '"""widgetlib — widget utilities."""\n', encoding="utf-8",
        )

        # Test directory
        (root / "tests").mkdir()
        (root / "tests" / "test_widget.py").write_text(
            "def test_create_widget():\n    assert True\n", encoding="utf-8",
        )

        # PRD directory (matches candidate "docs/prd")
        (root / "docs" / "prd").mkdir(parents=True)
        (root / "docs" / "prd" / "widget-spec.md").write_text(
            "# Widget PRD\n\n## Requirements\n\nREQ-W-001: Widgets must spin.\n",
            encoding="utf-8",
        )

        # Test plan directory (matches candidate "docs/test-plan")
        (root / "docs" / "test-plan").mkdir(parents=True)
        (root / "docs" / "test-plan" / "functional.md").write_text(
            "# Functional Tests\n\n### TC-W-001: Widget spins clockwise\n",
            encoding="utf-8",
        )

        # A rules file
        (root / "CONTRIBUTING.md").write_text(
            "# Contributing\n\nPlease follow PEP 8.\n", encoding="utf-8",
        )

        # Team persona file with enough headings to be detected
        (root / "docs" / "team").mkdir(parents=True)
        (root / "docs" / "team" / "alice.md").write_text(
            "# Alice\n\n"
            "## Role\nSenior Backend Engineer\n\n"
            "## Voice\nDirect, prefers data over anecdotes.\n\n"
            "## Domain\nDistributed systems\n\n"
            "## Background\n10 years Python.\n\n"
            "## Review Focus\nPerformance and error handling.\n",
            encoding="utf-8",
        )

        # Team index with Name | File | Role columns (matches regex pattern)
        (root / "docs" / "team" / "INDEX.md").write_text(
            "# Team\n\n| Name | File | Role |\n|------|------|------|\n"
            "| Alice | alice.md | Senior Backend Engineer |\n",
            encoding="utf-8",
        )

        self.scanner = ProjectScanner(root)

    def tearDown(self):
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def test_detect_language_python(self):
        """pyproject.toml triggers Python detection."""
        det = self.scanner.detect_language()
        self.assertEqual(det.value, "Python")
        self.assertGreaterEqual(det.confidence, 1.0)

    def test_detect_project_name(self):
        """Project name parsed from pyproject.toml [project] section."""
        det = self.scanner.detect_project_name("Python")
        self.assertEqual(det.value, "widgetlib")
        self.assertEqual(det.confidence, 1.0)

    def test_detect_ci_commands_defaults(self):
        """Without workflow files, falls back to Python CI defaults."""
        det = self.scanner.detect_ci_commands("Python")
        self.assertIn("pytest", det.value)
        self.assertIn("ruff check .", det.value)
        self.assertEqual(det.confidence, 0.5)

    def test_detect_build_command(self):
        """Python build command defaults to python -m build."""
        det = self.scanner.detect_build_command("Python")
        self.assertEqual(det.value, "python -m build")

    def test_detect_prd_dir(self):
        """docs/prd/ with content is detected."""
        det = self.scanner.detect_prd_dir()
        self.assertIsNotNone(det)
        self.assertEqual(det.value, "docs/prd")
        self.assertGreaterEqual(det.confidence, 0.9)

    def test_detect_test_plan_dir(self):
        """docs/test-plan/ with content is detected."""
        det = self.scanner.detect_test_plan_dir()
        self.assertIsNotNone(det)
        self.assertEqual(det.value, "docs/test-plan")
        self.assertGreaterEqual(det.confidence, 0.9)

    def test_detect_sagas_dir_none(self):
        """No sagas directory present — returns None."""
        det = self.scanner.detect_sagas_dir()
        self.assertIsNone(det)

    def test_detect_epics_dir_none(self):
        """No epics directory present — returns None."""
        det = self.scanner.detect_epics_dir()
        self.assertIsNone(det)

    def test_detect_story_map_none(self):
        """No story map index present — returns None."""
        det = self.scanner.detect_story_map()
        self.assertIsNone(det)

    def test_detect_team_topology_none(self):
        """No team topology file present — returns None."""
        det = self.scanner.detect_team_topology()
        self.assertIsNone(det)

    def test_detect_persona_files(self):
        """Persona file with 5 matching headings is detected."""
        personas = self.scanner.detect_persona_files()
        self.assertEqual(len(personas), 1)
        self.assertIn("alice.md", personas[0].path)
        self.assertGreaterEqual(personas[0].confidence, 0.6)

    def test_detect_team_index(self):
        """Team INDEX.md with Name|Role table is detected."""
        det = self.scanner.detect_team_index()
        self.assertIsNotNone(det.value)
        self.assertIn("INDEX.md", det.value)
        self.assertGreaterEqual(det.confidence, 0.9)

    def test_detect_rules_file(self):
        """CONTRIBUTING.md is picked up as rules file."""
        det = self.scanner.detect_rules_file()
        self.assertEqual(det.value, "CONTRIBUTING.md")
        self.assertEqual(det.confidence, 1.0)

    def test_detect_backlog_files_empty(self):
        """No milestone files with sprint headers — returns empty list."""
        backlog = self.scanner.detect_backlog_files()
        self.assertEqual(backlog, [])


# ---------------------------------------------------------------------------
# P2-04: Scanner Heuristic Fixtures — Minimal Project
# ---------------------------------------------------------------------------


class TestScannerMinimalProject(unittest.TestCase):
    """Scanner heuristics against a bare-bones project.

    Fixture: Only src/ with one source file, no manifest, no docs,
    no personas, no backlog. All deep-doc detect_* should return None.
    """

    def setUp(self):
        import tempfile
        self._tmpdir = tempfile.mkdtemp()
        root = Path(self._tmpdir)

        # Bare source directory with one file — no language manifest
        (root / "src").mkdir()
        (root / "src" / "main.c").write_text(
            '#include <stdio.h>\nint main() { return 0; }\n',
            encoding="utf-8",
        )

        self.scanner = ProjectScanner(root)

    def tearDown(self):
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def test_detect_language_unknown(self):
        """No manifest file — language is Unknown with zero confidence."""
        det = self.scanner.detect_language()
        self.assertEqual(det.value, "Unknown")
        self.assertEqual(det.confidence, 0.0)

    def test_detect_project_name_fallback(self):
        """No manifest — falls back to directory name."""
        det = self.scanner.detect_project_name("Unknown")
        # Value should be the temp dir name (varies), confidence low
        self.assertEqual(det.confidence, 0.3)
        self.assertEqual(det.evidence, "directory name fallback")

    def test_detect_ci_commands_empty(self):
        """No workflows, unknown language — no CI commands."""
        det = self.scanner.detect_ci_commands("Unknown")
        self.assertEqual(det.value, [])
        self.assertEqual(det.confidence, 0.0)

    def test_detect_build_command_none(self):
        """Unknown language — no build command."""
        det = self.scanner.detect_build_command("Unknown")
        self.assertIsNone(det.value)
        self.assertEqual(det.confidence, 0.0)

    def test_detect_prd_dir_none(self):
        """No PRD directory — returns None."""
        self.assertIsNone(self.scanner.detect_prd_dir())

    def test_detect_test_plan_dir_none(self):
        """No test plan directory — returns None."""
        self.assertIsNone(self.scanner.detect_test_plan_dir())

    def test_detect_sagas_dir_none(self):
        """No sagas directory — returns None."""
        self.assertIsNone(self.scanner.detect_sagas_dir())

    def test_detect_epics_dir_none(self):
        """No epics directory — returns None."""
        self.assertIsNone(self.scanner.detect_epics_dir())

    def test_detect_story_map_none(self):
        """No story map — returns None."""
        self.assertIsNone(self.scanner.detect_story_map())

    def test_detect_team_topology_none(self):
        """No team topology file — returns None."""
        self.assertIsNone(self.scanner.detect_team_topology())

    def test_detect_persona_files_empty(self):
        """No markdown files — no personas detected."""
        self.assertEqual(self.scanner.detect_persona_files(), [])

    def test_detect_team_index_none(self):
        """No team index — value is None."""
        det = self.scanner.detect_team_index()
        self.assertIsNone(det.value)

    def test_detect_backlog_files_empty(self):
        """No backlog files — returns empty list."""
        self.assertEqual(self.scanner.detect_backlog_files(), [])

    def test_detect_rules_file_none(self):
        """No RULES.md / CONVENTIONS.md / CONTRIBUTING.md — value is None."""
        det = self.scanner.detect_rules_file()
        self.assertIsNone(det.value)
        self.assertEqual(det.confidence, 0.0)

    def test_detect_dev_guide_none(self):
        """No DEVELOPMENT.md / CONTRIBUTING.md / HACKING.md — value is None."""
        det = self.scanner.detect_dev_guide()
        self.assertIsNone(det.value)
        self.assertEqual(det.confidence, 0.0)

    def test_detect_architecture_none(self):
        """No architecture doc — value is None."""
        det = self.scanner.detect_architecture()
        self.assertIsNone(det.value)

    def test_detect_story_id_pattern_none(self):
        """No backlog files — no story ID pattern detected."""
        det = self.scanner.detect_story_id_pattern([])
        self.assertIsNone(det.value)
        self.assertEqual(det.confidence, 0.0)

    def test_detect_binary_path_unknown(self):
        """Unknown language — no binary path."""
        det = self.scanner.detect_binary_path("Unknown")
        self.assertIsNone(det.value)
        self.assertEqual(det.confidence, 0.0)


# ---------------------------------------------------------------------------
# BH-005: validate_project negative tests
# ---------------------------------------------------------------------------

import tempfile
import os
from validate_config import validate_project, detect_sprint, extract_story_id, kanban_from_labels


class TestValidateProjectNegative(unittest.TestCase):
    """BH-005: Negative tests for validate_project error paths."""

    def setUp(self):
        self._tmpdir = tempfile.mkdtemp()
        self.config_dir = Path(self._tmpdir) / "sprint-config"
        self.config_dir.mkdir()

    def tearDown(self):
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def _write_minimal_config(self):
        """Create a minimal valid config for selective invalidation."""
        (self.config_dir / "project.toml").write_text(
            '[project]\nname = "Test"\nrepo = "o/r"\nlanguage = "Python"\n'
            '[paths]\nteam_dir = "sprint-config/team"\n'
            'backlog_dir = "sprint-config/backlog"\n'
            'sprints_dir = "sprints"\n'
            '[ci]\ncheck_commands = ["pytest"]\nbuild_command = "pip install ."\n',
            encoding="utf-8",
        )
        (self.config_dir / "rules.md").write_text("# Rules\n", encoding="utf-8")
        (self.config_dir / "development.md").write_text("# Dev\n", encoding="utf-8")
        team = self.config_dir / "team"
        team.mkdir()
        (team / "INDEX.md").write_text(
            "| Name | Role | File |\n|---|---|---|\n"
            "| Alice | Dev | alice.md |\n| Bob | Rev | bob.md |\n",
            encoding="utf-8",
        )
        (team / "alice.md").write_text("# Alice\n", encoding="utf-8")
        (team / "bob.md").write_text("# Bob\n", encoding="utf-8")
        backlog = self.config_dir / "backlog"
        backlog.mkdir()
        (backlog / "INDEX.md").write_text("# Backlog\n", encoding="utf-8")
        ms_dir = backlog / "milestones"
        ms_dir.mkdir()
        (ms_dir / "m1.md").write_text("# Sprint 1\n", encoding="utf-8")
        (self.config_dir / "definition-of-done.md").write_text(
            "# Definition of Done\n- Tests pass\n", encoding="utf-8",
        )

    def test_missing_required_file(self):
        """Missing project.toml causes validation failure."""
        valid, errors = validate_project(str(self.config_dir))
        self.assertFalse(valid)
        self.assertTrue(any("project.toml" in e for e in errors))

    def test_invalid_toml(self):
        """Unparseable project.toml causes validation failure."""
        self._write_minimal_config()
        (self.config_dir / "project.toml").write_text(
            "not valid toml content [[[\n", encoding="utf-8"
        )
        valid, errors = validate_project(str(self.config_dir))
        self.assertFalse(valid)
        # Should report missing required sections/keys
        self.assertTrue(any("missing required" in e.lower() for e in errors))

    def test_too_few_personas(self):
        """Fewer than 2 non-Giles personas triggers validation error."""
        self._write_minimal_config()
        (self.config_dir / "team" / "INDEX.md").write_text(
            "| Name | Role | File |\n|---|---|---|\n| Solo | Dev | solo.md |\n",
            encoding="utf-8",
        )
        (self.config_dir / "team" / "solo.md").write_text("# Solo\n", encoding="utf-8")
        valid, errors = validate_project(str(self.config_dir))
        self.assertFalse(valid)
        self.assertTrue(any("at least 2 non-Giles personas" in e for e in errors))

    def test_one_persona_plus_giles_still_fails(self):
        """BH18-008: 1 dev + Giles (2 rows total) should fail validation."""
        self._write_minimal_config()
        (self.config_dir / "team" / "INDEX.md").write_text(
            "| Name | Role | File |\n|---|---|---|\n"
            "| Solo | Dev | solo.md |\n"
            "| Giles | Scrum Master | giles.md |\n",
            encoding="utf-8",
        )
        (self.config_dir / "team" / "solo.md").write_text("# Solo\n", encoding="utf-8")
        (self.config_dir / "team" / "giles.md").write_text("# Giles\n", encoding="utf-8")
        valid, errors = validate_project(str(self.config_dir))
        self.assertFalse(valid, "1 dev + Giles should fail: need 2+ non-Giles")
        self.assertTrue(any("non-Giles" in e for e in errors))

    def test_missing_persona_file(self):
        """Referenced persona file not on disk triggers error."""
        self._write_minimal_config()
        # Remove alice.md but keep her in INDEX
        (self.config_dir / "team" / "alice.md").unlink()
        valid, errors = validate_project(str(self.config_dir))
        self.assertFalse(valid)
        self.assertTrue(any("alice" in e.lower() for e in errors))

    def test_missing_required_toml_key(self):
        """Missing [ci] section triggers error."""
        self._write_minimal_config()
        (self.config_dir / "project.toml").write_text(
            '[project]\nname = "Test"\nrepo = "o/r"\nlanguage = "Py"\n'
            '[paths]\nteam_dir = "t"\nbacklog_dir = "b"\nsprints_dir = "s"\n',
            encoding="utf-8",
        )
        valid, errors = validate_project(str(self.config_dir))
        self.assertFalse(valid)
        self.assertTrue(any("ci" in e.lower() for e in errors))

    def test_empty_rules_file(self):
        """Empty rules.md triggers validation error."""
        self._write_minimal_config()
        (self.config_dir / "rules.md").write_text("", encoding="utf-8")
        valid, errors = validate_project(str(self.config_dir))
        self.assertFalse(valid)
        self.assertTrue(any("empty" in e.lower() for e in errors))

    def test_no_milestone_files(self):
        """Empty milestones directory triggers error."""
        self._write_minimal_config()
        for f in (self.config_dir / "backlog" / "milestones").iterdir():
            f.unlink()
        valid, errors = validate_project(str(self.config_dir))
        self.assertFalse(valid)
        self.assertTrue(any("milestone" in e.lower() for e in errors))

    def test_valid_config_passes(self):
        """Sanity check: a well-formed config passes validation."""
        self._write_minimal_config()
        valid, errors = validate_project(str(self.config_dir))
        self.assertTrue(valid, f"Expected valid config, got errors: {errors}")


# ---------------------------------------------------------------------------
# BH-010: Tests for previously uncovered utility functions
# ---------------------------------------------------------------------------


class TestDetectSprint(unittest.TestCase):
    """Direct tests for detect_sprint()."""

    def test_reads_sprint_number_from_status(self):
        with tempfile.TemporaryDirectory() as d:
            sd = Path(d)
            (sd / "SPRINT-STATUS.md").write_text(
                "# Status\nCurrent Sprint: 3\n", encoding="utf-8"
            )
            self.assertEqual(detect_sprint(sd), 3)

    def test_returns_none_when_no_status_file(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertIsNone(detect_sprint(Path(d)))

    def test_returns_none_when_no_sprint_number(self):
        with tempfile.TemporaryDirectory() as d:
            sd = Path(d)
            (sd / "SPRINT-STATUS.md").write_text(
                "# Status\nNo sprint info here\n", encoding="utf-8"
            )
            self.assertIsNone(detect_sprint(sd))


class TestExtractStoryId(unittest.TestCase):
    """Direct tests for extract_story_id()."""

    def test_standard_format(self):
        self.assertEqual(extract_story_id("US-0001: Setup project"), "US-0001")

    def test_non_standard_prefix(self):
        self.assertEqual(extract_story_id("PROJ-42: Widget"), "PROJ-42")

    def test_no_match_falls_back_to_slug(self):
        """P5-19: Fallback produces a sanitized uppercase slug, not raw text."""
        self.assertEqual(extract_story_id("setup: init project"), "SETUP")

    def test_no_colon_returns_sanitized_slug(self):
        """P5-19: Full title without colon becomes an uppercase slug."""
        result = extract_story_id("no colon here")
        self.assertEqual(result, "NO-COLON-HERE")
        # Slug should be filesystem-safe
        self.assertRegex(result, r'^[A-Z0-9_-]+$')

    def test_special_chars_sanitized(self):
        """P5-19: Special characters become dashes in the slug."""
        result = extract_story_id("Add authentication: security module")
        self.assertEqual(result, "ADD-AUTHENTICATION")

    def test_empty_title_returns_unknown(self):
        """P5-19: Empty title returns 'UNKNOWN' as fallback."""
        self.assertEqual(extract_story_id(""), "UNKNOWN")

    def test_slug_truncated_at_40(self):
        """P5-19: Long slugs are truncated to prevent filesystem issues."""
        long_title = "a" * 60
        result = extract_story_id(long_title)
        self.assertLessEqual(len(result), 40)


class TestKanbanFromLabels(unittest.TestCase):
    """Direct tests for kanban_from_labels()."""

    def test_kanban_label_dict(self):
        issue = {"labels": [{"name": "kanban:dev"}], "state": "open"}
        self.assertEqual(kanban_from_labels(issue), "dev")

    def test_kanban_label_string(self):
        issue = {"labels": ["kanban:review"], "state": "open"}
        self.assertEqual(kanban_from_labels(issue), "review")

    def test_no_kanban_label_open(self):
        issue = {"labels": [{"name": "type:story"}], "state": "open"}
        self.assertEqual(kanban_from_labels(issue), "todo")

    def test_no_kanban_label_closed(self):
        issue = {"labels": [], "state": "closed"}
        self.assertEqual(kanban_from_labels(issue), "done")

    def test_empty_labels(self):
        issue = {"labels": [], "state": "open"}
        self.assertEqual(kanban_from_labels(issue), "todo")

    def test_multiple_labels_first_kanban_wins(self):
        issue = {"labels": [
            {"name": "type:story"},
            {"name": "kanban:review"},
            {"name": "sp:3"},
        ], "state": "open"}
        self.assertEqual(kanban_from_labels(issue), "review")

    def test_invalid_kanban_label_falls_back(self):
        """BH3-03: Invalid kanban label values fall back to todo/done."""
        issue = {"labels": [{"name": "kanban:blocked"}], "state": "open"}
        self.assertEqual(kanban_from_labels(issue), "todo")


# ---------------------------------------------------------------------------
# P7-11: _parse_workflow_runs direct tests
# ---------------------------------------------------------------------------

class TestParseWorkflowRuns(unittest.TestCase):
    """P7-11: Direct tests for ProjectScanner._parse_workflow_runs."""

    def setUp(self):
        import tempfile
        self._tmpdir = tempfile.mkdtemp()
        self.root = Path(self._tmpdir)
        self.scanner = ProjectScanner(self.root)

    def tearDown(self):
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def test_single_line_run(self):
        """Single-line run: command is extracted."""
        yml = self.root / "ci.yml"
        yml.write_text("    - run: cargo test\n", encoding="utf-8")
        result = self.scanner._parse_workflow_runs(yml)
        self.assertEqual(result, ["cargo test"])

    def test_multiline_run_block(self):
        """Multiline run: | block joins continued lines."""
        yml = self.root / "ci.yml"
        yml.write_text(
            "    - run: |\n"
            "        cargo fmt --check\n"
            "        cargo test\n",
            encoding="utf-8",
        )
        result = self.scanner._parse_workflow_runs(yml)
        self.assertEqual(len(result), 1)
        self.assertIn("cargo fmt --check", result[0])
        self.assertIn("cargo test", result[0])

    def test_multiple_single_line_runs(self):
        """Multiple single-line runs extracted correctly."""
        yml = self.root / "ci.yml"
        yml.write_text(
            "    - run: echo hello\n"
            "    - run: npm run lint\n",
            encoding="utf-8",
        )
        result = self.scanner._parse_workflow_runs(yml)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0], "echo hello")
        self.assertEqual(result[1], "npm run lint")

    def test_empty_file(self):
        """Empty file returns no runs."""
        yml = self.root / "ci.yml"
        yml.write_text("", encoding="utf-8")
        result = self.scanner._parse_workflow_runs(yml)
        self.assertEqual(result, [])


# ---------------------------------------------------------------------------
# BH24-015: bootstrap_github.py — check_prerequisites failure paths and
# create_milestones_on_github error handling
# ---------------------------------------------------------------------------

import tempfile
import subprocess as _subprocess
from unittest.mock import patch, MagicMock

import bootstrap_github
import populate_issues


class TestCheckPrerequisitesFailures(unittest.TestCase):
    """BH24-015: check_prerequisites() exits on gh/git failures."""

    def _make_run_result(self, returncode=0, stdout="", stderr=""):
        result = MagicMock()
        result.returncode = returncode
        result.stdout = stdout
        result.stderr = stderr
        return result

    @patch("subprocess.run")
    def test_gh_not_installed_exits_1(self, mock_run):
        """Exit 1 when gh --version fails (gh not installed)."""
        mock_run.return_value = self._make_run_result(returncode=1)
        with self.assertRaises(SystemExit) as ctx:
            bootstrap_github.check_prerequisites()
        self.assertEqual(ctx.exception.code, 1)
        # Should have only called gh --version (stopped there)
        self.assertEqual(mock_run.call_count, 1)
        self.assertEqual(mock_run.call_args[0][0], ["gh", "--version"])

    @patch("subprocess.run")
    def test_gh_not_authenticated_exits_1(self, mock_run):
        """Exit 1 when gh auth status fails (not logged in)."""
        def side_effect(cmd, **kwargs):
            if cmd == ["gh", "--version"]:
                return self._make_run_result(returncode=0)
            if cmd == ["gh", "auth", "status"]:
                return self._make_run_result(returncode=1)
            return self._make_run_result(returncode=0)
        mock_run.side_effect = side_effect
        with self.assertRaises(SystemExit) as ctx:
            bootstrap_github.check_prerequisites()
        self.assertEqual(ctx.exception.code, 1)
        self.assertEqual(mock_run.call_count, 2)

    @patch("subprocess.run")
    def test_no_git_remote_exits_1(self, mock_run):
        """Exit 1 when git remote -v returns empty (no remote configured)."""
        def side_effect(cmd, **kwargs):
            if cmd == ["gh", "--version"]:
                return self._make_run_result(returncode=0)
            if cmd == ["gh", "auth", "status"]:
                return self._make_run_result(returncode=0)
            if cmd == ["git", "remote", "-v"]:
                return self._make_run_result(returncode=0, stdout="")
            return self._make_run_result(returncode=0)
        mock_run.side_effect = side_effect
        with self.assertRaises(SystemExit) as ctx:
            bootstrap_github.check_prerequisites()
        self.assertEqual(ctx.exception.code, 1)
        self.assertEqual(mock_run.call_count, 3)

    @patch("subprocess.run")
    def test_git_remote_fails_exits_1(self, mock_run):
        """Exit 1 when git remote -v itself fails (returncode != 0)."""
        def side_effect(cmd, **kwargs):
            if cmd == ["gh", "--version"]:
                return self._make_run_result(returncode=0)
            if cmd == ["gh", "auth", "status"]:
                return self._make_run_result(returncode=0)
            if cmd == ["git", "remote", "-v"]:
                return self._make_run_result(returncode=1, stdout="")
            return self._make_run_result(returncode=0)
        mock_run.side_effect = side_effect
        with self.assertRaises(SystemExit) as ctx:
            bootstrap_github.check_prerequisites()
        self.assertEqual(ctx.exception.code, 1)

    @patch("subprocess.run")
    def test_all_pass_prints_ok(self, mock_run):
        """No exit when all checks pass; prints confirmation."""
        def side_effect(cmd, **kwargs):
            if cmd == ["git", "remote", "-v"]:
                return self._make_run_result(returncode=0, stdout="origin\tgit@github.com:o/r.git (fetch)")
            return self._make_run_result(returncode=0)
        mock_run.side_effect = side_effect
        # Should NOT raise
        bootstrap_github.check_prerequisites()
        self.assertEqual(mock_run.call_count, 3)


class TestCreateMilestonesErrorHandling(unittest.TestCase):
    """BH24-015: create_milestones_on_github() error and edge-case paths."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="giles-bh24015-")
        self.root = Path(self.tmpdir)
        backlog = self.root / "backlog" / "milestones"
        backlog.mkdir(parents=True)
        (backlog / "milestone-1.md").write_text(
            "# Milestone Alpha\n\nFirst milestone.\n\n"
            "### Sprint 1: Foundation\n\n"
            "| US-0101 | Setup | S01 | 3 | P0 |\n",
            encoding="utf-8",
        )
        (backlog / "milestone-2.md").write_text(
            "# Milestone Beta\n\nSecond milestone.\n\n"
            "### Sprint 2: Polish\n\n"
            "| US-0201 | Polish | S01 | 2 | P1 |\n",
            encoding="utf-8",
        )
        self.config = {
            "project": {"name": "test", "repo": "owner/repo"},
            "paths": {"backlog_dir": str(self.root / "backlog")},
        }

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    @patch("bootstrap_github.gh")
    def test_runtime_error_non_duplicate_counts_as_error(self, mock_gh):
        """Non-duplicate RuntimeError increments error count and warns on stderr."""
        mock_gh.side_effect = RuntimeError("403 Forbidden")
        import io, contextlib
        captured = io.StringIO()
        with contextlib.redirect_stderr(captured):
            created = bootstrap_github.create_milestones_on_github(self.config)
        self.assertEqual(created, 0)
        self.assertIn("failed to create", captured.getvalue())

    @patch("bootstrap_github.gh")
    def test_already_exists_not_counted_as_error(self, mock_gh):
        """RuntimeError with 'already_exists' is silently noted, not an error."""
        mock_gh.side_effect = RuntimeError("already_exists")
        import io, contextlib
        captured = io.StringIO()
        with contextlib.redirect_stderr(captured):
            created = bootstrap_github.create_milestones_on_github(self.config)
        self.assertEqual(created, 0)
        # No warning printed to stderr
        self.assertNotIn("failed to create", captured.getvalue())

    @patch("bootstrap_github.gh")
    def test_mixed_success_and_error(self, mock_gh):
        """One milestone succeeds, one fails — returns correct count."""
        call_count = [0]
        def side_effect(args):
            call_count[0] += 1
            if call_count[0] == 1:
                return "created"
            raise RuntimeError("rate limited")
        mock_gh.side_effect = side_effect
        created = bootstrap_github.create_milestones_on_github(self.config)
        self.assertEqual(created, 1)

    def test_no_milestone_files(self):
        """Returns 0 and prints message when no milestone files exist."""
        empty_config = {
            "project": {"name": "test", "repo": "owner/repo"},
            "paths": {"backlog_dir": str(self.root / "nonexistent")},
        }
        created = bootstrap_github.create_milestones_on_github(empty_config)
        self.assertEqual(created, 0)

    @patch("bootstrap_github.gh")
    def test_milestone_file_missing_heading_uses_fallback_title(self, mock_gh):
        """Milestone file without # heading falls back to filename-based title."""
        mock_gh.return_value = "created"
        # Overwrite milestone file with no heading
        backlog = self.root / "backlog" / "milestones"
        (backlog / "milestone-1.md").write_text(
            "No heading here, just text.\n\n"
            "### Sprint 1: Foundation\n",
            encoding="utf-8",
        )
        config = {
            "project": {"name": "test", "repo": "owner/repo"},
            "paths": {"backlog_dir": str(self.root / "backlog")},
        }
        # Only use milestone-1 to isolate the test
        from validate_config import get_milestones
        with patch("bootstrap_github.get_milestones",
                    return_value=[str(backlog / "milestone-1.md")]):
            created = bootstrap_github.create_milestones_on_github(config)
        self.assertEqual(created, 1)
        # The title should contain "Sprint 1" (from content) or "1" (from filename)
        call_args = mock_gh.call_args[0][0]
        title_idx = call_args.index("title=Sprint 1") if "title=Sprint 1" in call_args else -1
        # Verify title arg was passed (it's in the -f flag)
        title_args = [a for a in call_args if a.startswith("title=")]
        self.assertEqual(len(title_args), 1)
        self.assertIn("Sprint 1", title_args[0])


# ---------------------------------------------------------------------------
# BH24-016: populate_issues.py — enrich_from_epics conflicting sprints and
# create_issue failure path
# ---------------------------------------------------------------------------


class TestEnrichFromEpicsConflictingSprints(unittest.TestCase):
    """BH24-016: enrich_from_epics when epic references stories from different sprints."""

    def test_conflicting_sprints_uses_most_common(self):
        """When an epic references stories from different sprints,
        new stories use the most common sprint number."""
        tmpdir = tempfile.mkdtemp(prefix="giles-bh24016-")
        try:
            epics_dir = Path(tmpdir) / "epics"
            epics_dir.mkdir()

            # Epic file referencing stories from sprints 1 and 2,
            # with sprint 1 being more common, plus a new story
            epic_content = (
                "# E-0001 — Mixed Sprint Epic\n"
                "\n"
                "References: US-0001, US-0002, US-0003\n"
                "\n"
                "### US-0099: New Story From Epic\n"
                "\n"
                "| Field | Value |\n"
                "|-------|-------|\n"
                "| Saga | S01 |\n"
                "| Story Points | 5 |\n"
                "| Priority | P2 |\n"
                "\n"
            )
            (epics_dir / "E-0001-mixed.md").write_text(epic_content, encoding="utf-8")

            # Existing stories: 2 in sprint 1, 1 in sprint 2
            existing_stories = [
                populate_issues.Story(
                    story_id="US-0001", title="First", saga="S01",
                    sp=3, priority="P1", sprint=1,
                ),
                populate_issues.Story(
                    story_id="US-0002", title="Second", saga="S01",
                    sp=2, priority="P1", sprint=1,
                ),
                populate_issues.Story(
                    story_id="US-0003", title="Third", saga="S01",
                    sp=4, priority="P2", sprint=2,
                ),
            ]
            config = {"paths": {"epics_dir": str(epics_dir)}}

            result = populate_issues.enrich_from_epics(existing_stories, config)
            # US-0099 should be added with sprint=1 (most common)
            new_story = next((s for s in result if s.story_id == "US-0099"), None)
            self.assertIsNotNone(new_story, "US-0099 should be added from epic")
            self.assertEqual(new_story.sprint, 1,
                             "New story should use most common sprint (1)")
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_enrich_merges_detail_into_existing_story(self):
        """Detail block fields (user_story, AC) merge into existing stories."""
        tmpdir = tempfile.mkdtemp(prefix="giles-bh24016-merge-")
        try:
            epics_dir = Path(tmpdir) / "epics"
            epics_dir.mkdir()

            epic_content = (
                "# E-0001 — Enrichment Epic\n"
                "\n"
                "### US-0001: Setup Project\n"
                "\n"
                "**As a** developer **I want to** set up the project "
                "**so that** I can start coding\n"
                "\n"
                "**Acceptance Criteria:**\n"
                "- [ ] `AC-1`: Project compiles\n"
                "- [ ] `AC-2`: Tests pass\n"
                "\n"
            )
            (epics_dir / "E-0001-setup.md").write_text(epic_content, encoding="utf-8")

            existing = [
                populate_issues.Story(
                    story_id="US-0001", title="Setup Project", saga="S01",
                    sp=3, priority="P1", sprint=1,
                ),
            ]
            config = {"paths": {"epics_dir": str(epics_dir)}}

            result = populate_issues.enrich_from_epics(existing, config)
            enriched = next(s for s in result if s.story_id == "US-0001")
            self.assertIn("developer", enriched.user_story)
            self.assertEqual(len(enriched.acceptance_criteria), 2)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_enrich_no_epics_dir_returns_unchanged(self):
        """When epics_dir is not configured, stories are returned unchanged."""
        stories = [
            populate_issues.Story(
                story_id="US-0001", title="Solo", saga="S01",
                sp=1, priority="P1", sprint=1,
            ),
        ]
        config = {"paths": {}}
        result = populate_issues.enrich_from_epics(stories, config)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].story_id, "US-0001")


class TestCreateIssueFailurePath(unittest.TestCase):
    """BH24-016: create_issue() returns False on gh failure."""

    @patch("populate_issues.gh")
    def test_gh_runtime_error_returns_false(self, mock_gh):
        """create_issue returns False when gh raises RuntimeError."""
        mock_gh.side_effect = RuntimeError("API rate limit exceeded")
        story = populate_issues.Story(
            story_id="US-0042", title="Doomed Story",
            saga="S01", sp=3, priority="P1", sprint=1,
        )
        result = populate_issues.create_issue(
            story, milestone_numbers={}, milestone_titles={},
        )
        self.assertFalse(result)

    @patch("populate_issues.gh")
    def test_gh_success_returns_true(self, mock_gh):
        """create_issue returns True on success."""
        mock_gh.return_value = "https://github.com/owner/repo/issues/42"
        story = populate_issues.Story(
            story_id="US-0042", title="Good Story",
            saga="S01", sp=3, priority="P1", sprint=1,
        )
        result = populate_issues.create_issue(
            story, milestone_numbers={"Sprint 1": 1},
            milestone_titles={1: "Sprint 1"},
        )
        self.assertTrue(result)
        # Verify --milestone was passed since sprint mapping exists
        call_args = mock_gh.call_args[0][0]
        self.assertIn("--milestone", call_args)

    @patch("populate_issues.gh")
    def test_create_issue_includes_labels(self, mock_gh):
        """create_issue passes correct labels including saga and priority."""
        mock_gh.return_value = "https://github.com/owner/repo/issues/1"
        story = populate_issues.Story(
            story_id="US-0001", title="Labelled Story",
            saga="S01", sp=2, priority="P1", sprint=1, epic="E-0101",
        )
        populate_issues.create_issue(
            story, milestone_numbers={}, milestone_titles={},
        )
        call_args = mock_gh.call_args[0][0]
        # Collect all label arguments
        label_indices = [i for i, a in enumerate(call_args) if a == "--label"]
        labels = [call_args[i + 1] for i in label_indices]
        self.assertIn("sprint:1", labels)
        self.assertIn("type:story", labels)
        self.assertIn("kanban:todo", labels)
        self.assertIn("saga:S01", labels)
        self.assertIn("priority:P1", labels)


# ---------------------------------------------------------------------------
# BH24-017: manage_sagas.py — update_sprint_allocation table structure and
# update_team_voices table structure
# ---------------------------------------------------------------------------


class TestUpdateSprintAllocationStructure(unittest.TestCase):
    """BH24-017: Verify update_sprint_allocation rewrites table correctly."""

    def _make_saga(self, tmp_path: Path) -> Path:
        """Create a minimal saga with Sprint Allocation section."""
        saga = tmp_path / "S01-test.md"
        saga.write_text(
            "# S01 — Test Saga\n"
            "\n"
            "| Field | Value |\n"
            "|-------|-------|\n"
            "| Stories | 4 |\n"
            "| Epics | 2 |\n"
            "| Total SP | 20 |\n"
            "\n"
            "## Epic Index\n"
            "\n"
            "| Epic | Name | Stories | SP |\n"
            "|------|------|---------|-----|\n"
            "| E-0101 | Parser | 2 | 8 |\n"
            "\n"
            "## Sprint Allocation\n"
            "\n"
            "| Sprint | Stories | SP |\n"
            "|--------|---------|-----|\n"
            "| Sprint 1 | US-0101 | 5 |\n"
            "| Sprint 2 | US-0102 | 8 |\n"
            "\n"
            "## Team Voices\n"
            "\n"
            "> **Ada:** \"Types first.\"\n",
            encoding="utf-8",
        )
        return saga

    def test_table_header_structure(self):
        """Rewritten table has proper markdown header and separator rows."""
        with tempfile.TemporaryDirectory() as tmp:
            saga_path = self._make_saga(Path(tmp))
            new_alloc = [
                {"sprint": "Sprint 1", "stories": "US-0101, US-0102", "sp": "10"},
                {"sprint": "Sprint 2", "stories": "US-0103", "sp": "5"},
                {"sprint": "Sprint 3", "stories": "US-0104, US-0105", "sp": "12"},
            ]
            update_sprint_allocation(str(saga_path), new_alloc)
            content = saga_path.read_text(encoding="utf-8")
            lines = content.split("\n")

            # Find the Sprint Allocation section
            alloc_idx = next(i for i, l in enumerate(lines) if l.strip() == "## Sprint Allocation")
            # Next non-blank line should be the table header
            table_lines = [l for l in lines[alloc_idx + 1:] if l.strip()]
            self.assertEqual(table_lines[0], "| Sprint | Stories | SP |")
            self.assertEqual(table_lines[1], "|--------|---------|-----|")
            # Data rows
            self.assertIn("US-0101, US-0102", table_lines[2])
            self.assertIn("US-0103", table_lines[3])
            self.assertIn("US-0104, US-0105", table_lines[4])

    def test_three_rows_written(self):
        """Correct number of data rows written."""
        with tempfile.TemporaryDirectory() as tmp:
            saga_path = self._make_saga(Path(tmp))
            new_alloc = [
                {"sprint": "Sprint 1", "stories": "US-0101", "sp": "3"},
                {"sprint": "Sprint 2", "stories": "US-0102", "sp": "5"},
                {"sprint": "Sprint 3", "stories": "US-0103", "sp": "8"},
            ]
            update_sprint_allocation(str(saga_path), new_alloc)
            result = parse_saga(str(saga_path))
            self.assertEqual(len(result["sprint_allocation"]), 3)
            self.assertEqual(result["sprint_allocation"][2]["sprint"], "Sprint 3")
            self.assertEqual(result["sprint_allocation"][2]["sp"], "8")

    def test_surrounding_sections_preserved(self):
        """Epic Index and Team Voices sections survive sprint allocation rewrite."""
        with tempfile.TemporaryDirectory() as tmp:
            saga_path = self._make_saga(Path(tmp))
            new_alloc = [{"sprint": "Sprint 1", "stories": "US-0001", "sp": "5"}]
            update_sprint_allocation(str(saga_path), new_alloc)
            content = saga_path.read_text(encoding="utf-8")
            self.assertIn("## Epic Index", content)
            self.assertIn("E-0101", content)
            self.assertIn("## Team Voices", content)
            self.assertIn("Ada", content)
            self.assertIn("# S01", content)

    def test_empty_allocation_produces_empty_table(self):
        """An empty allocation list produces a table with headers but no data rows."""
        with tempfile.TemporaryDirectory() as tmp:
            saga_path = self._make_saga(Path(tmp))
            update_sprint_allocation(str(saga_path), [])
            result = parse_saga(str(saga_path))
            self.assertEqual(result["sprint_allocation"], [])
            # Headers should still be present in the file
            content = saga_path.read_text(encoding="utf-8")
            self.assertIn("## Sprint Allocation", content)
            self.assertIn("| Sprint | Stories | SP |", content)

    def test_no_sprint_allocation_section_is_noop(self):
        """If the saga has no Sprint Allocation section, nothing changes."""
        with tempfile.TemporaryDirectory() as tmp:
            saga_path = Path(tmp) / "no-alloc.md"
            original = (
                "# S99 — No Allocation\n\n"
                "## Team Voices\n\n"
                "> **Ada:** \"Hello.\"\n"
            )
            saga_path.write_text(original, encoding="utf-8")
            update_sprint_allocation(str(saga_path), [{"sprint": "Sprint 1", "stories": "US-0001", "sp": "5"}])
            self.assertEqual(saga_path.read_text(encoding="utf-8"), original)


class TestUpdateTeamVoicesStructure(unittest.TestCase):
    """BH24-017: Verify update_team_voices rewrites blockquotes correctly."""

    def _make_saga(self, tmp_path: Path) -> Path:
        """Create a saga with Team Voices and surrounding sections."""
        saga = tmp_path / "S01-test.md"
        saga.write_text(
            "# S01 — Test Saga\n"
            "\n"
            "Metadata paragraph.\n"
            "\n"
            "## Sprint Allocation\n"
            "\n"
            "| Sprint | Stories | SP |\n"
            "|--------|---------|-----|\n"
            "| Sprint 1 | US-0101 | 5 |\n"
            "\n"
            "## Team Voices\n"
            "\n"
            "> **Original:** \"Old quote.\"\n"
            "\n"
            "## Dependency Graph\n"
            "\n"
            "Dependencies go here.\n",
            encoding="utf-8",
        )
        return saga

    def test_voices_use_blockquote_format(self):
        """Each voice uses > **Name:** \"quote\" format."""
        with tempfile.TemporaryDirectory() as tmp:
            saga_path = self._make_saga(Path(tmp))
            voices = {"Rusti": "Ownership matters", "Palette": "Make it beautiful"}
            update_team_voices(str(saga_path), voices)
            content = saga_path.read_text(encoding="utf-8")
            self.assertIn('> **Rusti:** "Ownership matters"', content)
            self.assertIn('> **Palette:** "Make it beautiful"', content)

    def test_old_voices_removed(self):
        """Previous voice content is replaced, not appended."""
        with tempfile.TemporaryDirectory() as tmp:
            saga_path = self._make_saga(Path(tmp))
            update_team_voices(str(saga_path), {"New": "Fresh take"})
            content = saga_path.read_text(encoding="utf-8")
            self.assertNotIn("Original", content)
            self.assertNotIn("Old quote", content)
            self.assertIn("New", content)

    def test_surrounding_sections_preserved(self):
        """Sprint Allocation and Dependency Graph survive voice rewrite."""
        with tempfile.TemporaryDirectory() as tmp:
            saga_path = self._make_saga(Path(tmp))
            update_team_voices(str(saga_path), {"Ada": "Types rule"})
            content = saga_path.read_text(encoding="utf-8")
            self.assertIn("## Sprint Allocation", content)
            self.assertIn("US-0101", content)
            self.assertIn("## Dependency Graph", content)
            self.assertIn("Dependencies go here.", content)
            self.assertIn("# S01", content)

    def test_empty_voices_clears_section(self):
        """Empty voices dict clears the section content but keeps the heading."""
        with tempfile.TemporaryDirectory() as tmp:
            saga_path = self._make_saga(Path(tmp))
            update_team_voices(str(saga_path), {})
            content = saga_path.read_text(encoding="utf-8")
            self.assertIn("## Team Voices", content)
            self.assertNotIn("Original", content)
            self.assertNotIn("> **", content)

    def test_no_team_voices_section_is_noop(self):
        """If the saga has no Team Voices section, nothing changes."""
        with tempfile.TemporaryDirectory() as tmp:
            saga_path = Path(tmp) / "no-voices.md"
            original = (
                "# S99 — No Voices\n\n"
                "## Sprint Allocation\n\n"
                "| Sprint | Stories | SP |\n"
                "|--------|---------|-----|\n"
                "| Sprint 1 | US-0001 | 5 |\n"
            )
            saga_path.write_text(original, encoding="utf-8")
            update_team_voices(str(saga_path), {"Ada": "Hello"})
            self.assertEqual(saga_path.read_text(encoding="utf-8"), original)

    def test_markdown_injection_sanitized(self):
        """BH23-224: Newlines and bold markers in voice inputs are sanitized."""
        with tempfile.TemporaryDirectory() as tmp:
            saga_path = self._make_saga(Path(tmp))
            voices = {
                "Evil\nName": "quote with\nnewline",
                "**Bold**": 'say "hello"',
            }
            update_team_voices(str(saga_path), voices)
            content = saga_path.read_text(encoding="utf-8")
            # Newlines in name/quote should be replaced with spaces
            self.assertNotIn("Evil\nName", content)
            self.assertIn("Evil Name", content)
            self.assertNotIn("quote with\nnewline", content)
            # Bold markers in name should be stripped
            self.assertNotIn("****Bold****", content)
            # Double quotes in quote should be replaced with single quotes
            self.assertIn("say 'hello'", content)


if __name__ == "__main__":
    unittest.main()
