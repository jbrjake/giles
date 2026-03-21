"""Tests for new scripts: smoke_test.py, gap_scanner.py, test_categories.py."""
from __future__ import annotations

import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from smoke_test import run_smoke, write_history
from gap_scanner import (
    scan_for_gaps, has_user_facing_keywords, get_entry_points,
    story_touches_entry_point, _path_matches_entry_point,
)
from test_categories import (
    classify_test_file, count_test_functions, analyze, format_report,
)
from assign_dod_level import classify_story
from history_to_checklist import extract_checklist_items, generate_checklists


class TestSmokeTest(unittest.TestCase):
    """P0-SCRIPT-1: Smoke test runner."""

    def test_smoke_pass_exit_zero(self):
        status, code, _, _ = run_smoke("true")
        self.assertEqual(status, "SMOKE PASS")
        self.assertEqual(code, 0)

    def test_smoke_fail_exit_nonzero(self):
        status, code, _, _ = run_smoke("false")
        self.assertEqual(status, "SMOKE FAIL")
        self.assertEqual(code, 1)

    def test_smoke_skip_not_configured(self):
        status, code, _, _ = run_smoke("")
        self.assertEqual(status, "SMOKE SKIP")
        self.assertEqual(code, 2)

    def test_smoke_timeout(self):
        status, code, _, stderr = run_smoke("sleep 60", timeout=1)
        self.assertEqual(status, "SMOKE FAIL")
        self.assertEqual(code, 1)
        self.assertIn("timed out", stderr)

    def test_smoke_history_appends(self):
        """Smoke history file is appended, not overwritten."""
        with tempfile.TemporaryDirectory() as td:
            write_history(td, "SMOKE PASS", "true")
            write_history(td, "SMOKE FAIL", "false")
            history = (Path(td) / "smoke-history.md").read_text()
            self.assertIn("SMOKE PASS", history)
            self.assertIn("SMOKE FAIL", history)
            self.assertEqual(history.count("SMOKE"), 2)

    def test_smoke_history_creates_file(self):
        """History file is created if it doesn't exist."""
        with tempfile.TemporaryDirectory() as td:
            write_history(td, "SMOKE PASS", "echo ok")
            path = Path(td) / "smoke-history.md"
            self.assertTrue(path.is_file())
            content = path.read_text()
            self.assertIn("Smoke Test History", content)

    def test_smoke_history_escapes_pipe_in_command(self):
        """BH33-003: Pipe chars in command must be escaped to prevent table corruption."""
        with tempfile.TemporaryDirectory() as td:
            write_history(td, "SMOKE PASS", "cargo test 2>&1 | head -20")
            content = (Path(td) / "smoke-history.md").read_text()
            # The last data row should have exactly 4 columns (Date, Commit, Command, Result)
            data_lines = [l for l in content.splitlines()
                          if l.startswith("|") and "---" not in l
                          and "Date" not in l]
            self.assertEqual(len(data_lines), 1)
            # Count unescaped pipes (column separators) — should be 5 for 4 columns
            row = data_lines[0]
            # Pipes preceded by backslash are escaped, not separators
            import re
            separators = re.findall(r'(?<!\\)\|', row)
            self.assertEqual(len(separators), 5)  # |col1|col2|col3|col4|


class TestGapScanner(unittest.TestCase):
    """P0-SCRIPT-2: Gap scanner."""

    def test_skip_no_entry_points(self):
        """When entry_points not configured, output contains SKIP."""
        config = {"project": {"name": "test"}, "paths": {"sprints_dir": "/tmp"}}
        report, code = scan_for_gaps(config, 1)
        self.assertIn("SKIP", report)
        self.assertEqual(code, 0)

    def test_gap_detected(self):
        """Stories that don't touch entry points trigger GAP DETECTED."""
        from validate_config import TF, write_tf
        with tempfile.TemporaryDirectory() as td:
            stories_dir = Path(td) / "sprints" / "sprint-1" / "stories"
            stories_dir.mkdir(parents=True)
            # Create 5 stories, none touching src/main.py
            for i in range(1, 6):
                tf = TF(
                    path=stories_dir / f"US-{i:04d}-test.md",
                    story=f"US-{i:04d}", title="Test story",
                    sprint=1, status="dev",
                )
                tf.body_text = "Implement parser for module X"
                write_tf(tf)
            config = {
                "project": {"entry_points": ["src/main.py"]},
                "paths": {"sprints_dir": str(Path(td) / "sprints")},
            }
            report, code = scan_for_gaps(config, 1)
            self.assertIn("GAP DETECTED", report)
            self.assertIn("5 stories", report)
            self.assertIn("src/main.py", report)
            self.assertEqual(code, 1)

    def test_no_gap_when_story_touches_entry_point(self):
        """Story referencing entry point in body produces NO GAP."""
        from validate_config import TF, write_tf
        with tempfile.TemporaryDirectory() as td:
            stories_dir = Path(td) / "sprints" / "sprint-1" / "stories"
            stories_dir.mkdir(parents=True)
            tf = TF(
                path=stories_dir / "US-0001-test.md",
                story="US-0001", title="Integration", sprint=1,
            )
            tf.body_text = "Wire up src/main.py to load the new parser"
            write_tf(tf)
            config = {
                "project": {"entry_points": ["src/main.py"]},
                "paths": {"sprints_dir": str(Path(td) / "sprints")},
            }
            report, code = scan_for_gaps(config, 1)
            self.assertIn("NO GAP", report)
            self.assertEqual(code, 0)

    def test_user_facing_keywords(self):
        """Keyword scanner detects user-facing language."""
        story = {"title": "Add visible bloom effect", "body": "user sees it on screen"}
        self.assertTrue(has_user_facing_keywords(story))

    def test_no_user_facing_keywords(self):
        story = {"title": "Refactor parser internals", "body": "module cleanup"}
        self.assertFalse(has_user_facing_keywords(story))

    def test_get_entry_points_from_config(self):
        config = {"project": {"entry_points": ["src/main.py", "src/app.py"]}}
        self.assertEqual(get_entry_points(config), ["src/main.py", "src/app.py"])

    def test_get_entry_points_missing(self):
        config = {"project": {"name": "test"}}
        self.assertEqual(get_entry_points(config), [])

    def test_entry_point_substring_no_false_positive(self):
        """BH29-003: Entry point 'main' must not match 'domain' in body text."""
        result = story_touches_entry_point(
            {"body": "Implement domain controller logic", "branch": ""},
            ["main"],
        )
        self.assertIsNone(result)

    def test_entry_point_word_boundary_match(self):
        """BH29-003: Entry point 'main' should match 'update main module'."""
        result = story_touches_entry_point(
            {"body": "Update main module for new feature", "branch": ""},
            ["main"],
        )
        self.assertEqual(result, "main")

    def test_entry_point_path_match_in_body(self):
        """BH29-003: Entry point 'src/main.py' matches as word-boundary."""
        result = story_touches_entry_point(
            {"body": "Wire up src/main.py for integration", "branch": ""},
            ["src/main.py"],
        )
        self.assertEqual(result, "src/main.py")

    def test_path_match_no_substring_false_positive(self):
        """BH30-001: 'main' must not match file 'domain/maintain.py'."""
        self.assertFalse(_path_matches_entry_point("src/domain/maintain.py", "main"))

    def test_path_match_bare_name_matches_file_stem(self):
        """BH30-001: 'main' matches file 'src/main.py' via stem."""
        self.assertTrue(_path_matches_entry_point("src/main.py", "main"))

    def test_path_match_exact_path(self):
        """BH30-001: 'src/main.py' matches 'src/main.py' exactly."""
        self.assertTrue(_path_matches_entry_point("src/main.py", "src/main.py"))

    def test_path_match_suffix(self):
        """BH30-001: 'main.py' matches 'src/main.py' as suffix."""
        self.assertTrue(_path_matches_entry_point("src/main.py", "main.py"))

    def test_path_match_dir_name(self):
        """BH30-001: 'main' matches directory 'src/main/app.py' as segment."""
        self.assertTrue(_path_matches_entry_point("src/main/app.py", "main"))


class TestTestCategories(unittest.TestCase):
    """P1-SCRIPT-3: Test category analyzer."""

    def test_classify_unit_by_default(self):
        self.assertEqual(
            classify_test_file(Path("tests/test_parser.py")), "unit"
        )

    def test_classify_integration_by_dir(self):
        self.assertEqual(
            classify_test_file(Path("tests/integration/test_api.py")),
            "integration",
        )

    def test_classify_e2e_as_integration(self):
        self.assertEqual(
            classify_test_file(Path("tests/e2e/test_flow.py")),
            "integration",
        )

    def test_classify_smoke_by_dir(self):
        self.assertEqual(
            classify_test_file(Path("tests/smoke/test_launch.py")),
            "smoke",
        )

    def test_classify_by_name_pattern(self):
        self.assertEqual(
            classify_test_file(Path("tests/test_integration_api.py")),
            "integration",
        )

    def test_count_python_test_functions(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False
        ) as f:
            f.write(textwrap.dedent("""\
                def test_one():
                    pass
                def test_two():
                    pass
                def helper():
                    pass
            """))
            f.flush()
            self.assertEqual(count_test_functions(Path(f.name)), 2)

    def test_warning_zero_integration(self):
        counts = {"unit": 10, "component": 5, "integration": 0, "smoke": 0}
        report = format_report(counts)
        self.assertIn("WARNING", report)
        self.assertIn("0 integration", report)

    def test_format_report_percentages(self):
        counts = {"unit": 60, "component": 30, "integration": 10, "smoke": 0}
        report = format_report(counts)
        self.assertIn("unit: 60 (60%)", report)
        self.assertIn("integration: 10 (10%)", report)

    def test_format_report_zero_tests(self):
        """M2: Edge case — no tests found produces specific message."""
        counts = {"unit": 0, "component": 0, "integration": 0, "smoke": 0}
        report = format_report(counts)
        self.assertEqual(report, "No tests found")

    def test_analyze_with_dirs(self):
        """Analyze correctly categorizes tests in subdirectories."""
        with tempfile.TemporaryDirectory() as td:
            # Create unit test
            unit_dir = Path(td) / "tests"
            unit_dir.mkdir()
            (unit_dir / "test_unit.py").write_text(
                "def test_one(): pass\ndef test_two(): pass\n"
            )
            # Create integration test
            int_dir = Path(td) / "tests" / "integration"
            int_dir.mkdir()
            (int_dir / "test_int.py").write_text(
                "def test_api(): pass\n"
            )
            counts = analyze(Path(td))
            self.assertEqual(counts["unit"], 2)
            self.assertEqual(counts["integration"], 1)


class TestRiskRegister(unittest.TestCase):
    """P1-STATE-2: Risk register management."""

    def setUp(self):
        self._td = tempfile.mkdtemp()
        self._mock_path = Path(self._td) / "risk-register.md"
        self._patcher = patch("risk_register._register_path",
                              return_value=self._mock_path)
        self._patcher.start()

    def tearDown(self):
        self._patcher.stop()
        import shutil
        shutil.rmtree(self._td, ignore_errors=True)

    def test_add_risk(self):
        from risk_register import add_risk, _register_path
        rid = add_risk("No integration tests", "high", "1")
        self.assertEqual(rid, "R1")
        content = _register_path().read_text()
        self.assertIn("No integration tests", content)
        self.assertIn("high", content)

    def test_list_open_risks(self):
        from risk_register import add_risk, list_open_risks
        add_risk("Risk A", "high", "1")
        add_risk("Risk B", "low", "1")
        risks = list_open_risks()
        self.assertEqual(len(risks), 2)

    def test_escalate_overdue(self):
        from risk_register import escalate_overdue, _register_path
        # Manually write a risk with sprints_open > 2
        _register_path().parent.mkdir(parents=True, exist_ok=True)
        _register_path().write_text(
            "# Risk Register\n"
            "| ID | Title | Severity | Status | Raised | Sprints Open | Resolution |\n"
            "|----|-------|----------|--------|--------|-------------|------------|\n"
            "| R1 | Old risk | high | Open | Sprint 1 | 3 | |\n",
            encoding="utf-8",
        )
        overdue = escalate_overdue(threshold=2)
        self.assertEqual(len(overdue), 1)
        self.assertEqual(overdue[0]["id"], "R1")

    def test_resolve_risk(self):
        """BH25: resolve_risk sets status to Resolved and adds resolution text."""
        from risk_register import add_risk, resolve_risk, list_open_risks
        add_risk("Test risk", "high", "1")
        self.assertEqual(len(list_open_risks()), 1)
        result = resolve_risk("R1", "Fixed in sprint 2")
        self.assertTrue(result)
        self.assertEqual(len(list_open_risks()), 0)

    def test_resolve_nonexistent_risk(self):
        from risk_register import resolve_risk
        result = resolve_risk("R999", "doesn't exist")
        self.assertFalse(result)

    def test_pipe_roundtrip(self):
        """DA-021/022: Pipes in title and resolution survive add→resolve→list."""
        from risk_register import add_risk, resolve_risk, list_open_risks, _parse_rows, _register_path
        add_risk("Risk A | Risk B", "high", "1")
        # Title should be escaped in file but readable via _parse_rows
        rows = _parse_rows(_register_path().read_text())
        self.assertEqual(rows[0]["title"], "Risk A | Risk B")
        # Resolve with a pipe in resolution
        resolve_risk("R1", "fixed | workaround applied")
        rows = _parse_rows(_register_path().read_text())
        self.assertEqual(rows[0]["resolution"], "fixed | workaround applied")
        self.assertEqual(rows[0]["status"], "Resolved")

    def test_add_risk_sanitizes_pipes(self):
        """BH25: Pipe characters in title don't break table."""
        from risk_register import add_risk, _register_path
        add_risk("Risk with | pipe", "high", "1")
        content = _register_path().read_text()
        # Each row should have exactly 8 pipe characters (7 cells)
        data_lines = [l for l in content.splitlines()
                      if l.strip().startswith("|") and "R1" in l]
        self.assertTrue(len(data_lines) == 1)

    def test_template_in_skeletons(self):
        tmpl = Path(__file__).resolve().parent.parent / "references/skeletons/risk-register.md.tmpl"
        self.assertTrue(tmpl.is_file())


class TestAssignDodLevel(unittest.TestCase):
    """P2-STATE-5: Automated DoD level assignment."""

    def test_app_level_for_user_facing(self):
        self.assertEqual(
            classify_story("user sees bloom effect on screen"), "app"
        )

    def test_library_level_for_internal(self):
        self.assertEqual(
            classify_story("FFT buffer size configurable"), "library"
        )

    def test_app_level_from_title(self):
        self.assertEqual(
            classify_story("internal details", title="Add visible indicator"), "app"
        )

    def test_word_boundary_username_is_library(self):
        """H4: 'username' should not trigger 'user' keyword."""
        self.assertEqual(classify_story("validate username field"), "library")

    def test_case_insensitive_UI(self):
        """H4: Case-insensitive matching for 'UI'."""
        self.assertEqual(classify_story("update UI layout"), "app")

    def test_displaying_is_app(self):
        """'display' keyword with word boundary."""
        self.assertEqual(classify_story("display the results"), "app")


class TestHistoryToChecklist(unittest.TestCase):
    """P2-STATE-6: Persona history → review checklist generator."""

    def test_extract_from_history(self):
        """Given history with 2 bug-keyword lines, generates 2 items."""
        history = (
            "### Sprint 1 — feature\n"
            "Caught ARC callback violation in audio capture pipeline.\n"
            "Fixed the memory leak in buffer management.\n"
        )
        items = extract_checklist_items(history, "sana")
        self.assertEqual(len(items), 2, f"Expected 2 items, got {items}")
        self.assertTrue(all("sana" in i for i in items))
        self.assertTrue(any("ARC callback" in i for i in items))
        self.assertTrue(any("memory leak" in i for i in items))

    def test_empty_history(self):
        """Empty history produces no items."""
        items = extract_checklist_items("", "test")
        self.assertEqual(items, [])

    def test_generate_from_directory(self):
        """Scans history directory for persona files."""
        with tempfile.TemporaryDirectory() as td:
            history_dir = Path(td) / "history"
            history_dir.mkdir()
            (history_dir / "rae.md").write_text(
                "### Sprint 1\nFound a regression in the parser.\n"
            )
            (history_dir / "chen.md").write_text(
                "### Sprint 1\nAll good, no issues.\n"
            )
            checklists = generate_checklists(td)
            self.assertIn("rae", checklists)
            # chen had no bug keywords, so no items
            self.assertNotIn("chen", checklists)

    def test_missing_history_dir(self):
        """Missing history directory handled gracefully."""
        with tempfile.TemporaryDirectory() as td:
            checklists = generate_checklists(td)
            self.assertEqual(checklists, {})


if __name__ == "__main__":
    unittest.main()
