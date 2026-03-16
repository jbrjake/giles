#!/usr/bin/env python3
"""Unit tests for commit.py and release_gate.py helper functions.

Tests commit message validation, atomicity checking, version calculation,
gate validation, TOML writing, and release notes generation.

Sprint runtime tests: test_sprint_runtime.py
Regression tests: test_bugfix_regression.py

Run: python -m pytest tests/test_gh_interactions.py -v
"""
from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from commit import validate_message, check_atomicity
from release_gate import (
    determine_bump, write_version_to_toml, generate_release_notes,
    gate_stories, gate_ci, gate_prs,
)


# ---------------------------------------------------------------------------
# commit.py tests
# ---------------------------------------------------------------------------

class TestValidateMessage(unittest.TestCase):
    """Test conventional commit message validation."""

    def test_valid_feat(self):
        ok, err = validate_message("feat: add login")
        self.assertTrue(ok)
        self.assertEqual(err, "")

    def test_valid_fix_with_scope(self):
        ok, err = validate_message("fix(parser): handle nulls")
        self.assertTrue(ok)

    def test_valid_breaking(self):
        ok, err = validate_message("feat!: remove old API")
        self.assertTrue(ok)

    def test_valid_breaking_with_scope(self):
        ok, err = validate_message("refactor(core)!: rewrite engine")
        self.assertTrue(ok)

    def test_all_valid_types(self):
        for t in ("feat", "fix", "refactor", "test", "docs",
                   "chore", "ci", "perf", "build", "style"):
            ok, _ = validate_message(f"{t}: do something")
            self.assertTrue(ok, f"Type '{t}' should be valid")

    def test_invalid_type(self):
        ok, err = validate_message("feature: add login")
        self.assertFalse(ok)
        self.assertIn("Invalid conventional commit", err)

    def test_missing_colon(self):
        ok, err = validate_message("feat add login")
        self.assertFalse(ok)

    def test_empty_description(self):
        ok, err = validate_message("feat: ")
        self.assertFalse(ok)
        # Regex requires .+ after ": ", so empty desc fails as invalid format
        self.assertIn("Invalid conventional commit", err)

    def test_empty_message(self):
        ok, err = validate_message("")
        self.assertFalse(ok)

    def test_no_type_prefix(self):
        ok, err = validate_message("just a regular message")
        self.assertFalse(ok)


class TestCheckAtomicity(unittest.TestCase):
    """Test atomicity enforcement."""

    @patch("commit.subprocess.run")
    def test_no_staged_changes(self, mock_run):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr="",
        )
        ok, msg = check_atomicity()
        self.assertFalse(ok)
        self.assertIn("No staged changes", msg)

    @patch("commit.subprocess.run")
    def test_single_directory(self, mock_run):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="src/foo.py\nsrc/bar.py\n", stderr="",
        )
        ok, msg = check_atomicity()
        self.assertTrue(ok)

    @patch("commit.subprocess.run")
    def test_three_directories_without_force(self, mock_run):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0,
            stdout="src/a.py\ntests/b.py\ndocs/c.md\n", stderr="",
        )
        ok, msg = check_atomicity(force=False)
        self.assertFalse(ok)
        self.assertIn("3 directories", msg)

    @patch("commit.subprocess.run")
    def test_three_directories_with_force(self, mock_run):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0,
            stdout="src/a.py\ntests/b.py\ndocs/c.md\n", stderr="",
        )
        ok, msg = check_atomicity(force=True)
        self.assertTrue(ok)

    @patch("commit.subprocess.run")
    def test_root_files(self, mock_run):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0,
            stdout="README.md\nCLAUDE.md\n", stderr="",
        )
        ok, msg = check_atomicity()
        self.assertTrue(ok)  # both in (root), only 1 dir


# ---------------------------------------------------------------------------
# release_gate.py -- version calculation tests
# ---------------------------------------------------------------------------

class TestDetermineBump(unittest.TestCase):

    def test_feat_is_minor(self):
        commits = [{"subject": "feat: add login", "body": ""}]
        self.assertEqual(determine_bump(commits), "minor")

    def test_fix_is_patch(self):
        commits = [{"subject": "fix: typo", "body": ""}]
        self.assertEqual(determine_bump(commits), "patch")

    def test_breaking_bang_is_major(self):
        commits = [{"subject": "feat!: remove API", "body": ""}]
        self.assertEqual(determine_bump(commits), "major")

    def test_breaking_trailer_is_major(self):
        commits = [{"subject": "refactor: redo", "body": "BREAKING CHANGE: old API removed"}]
        self.assertEqual(determine_bump(commits), "major")

    def test_breaking_wins_over_feat(self):
        commits = [
            {"subject": "feat: add thing", "body": ""},
            {"subject": "fix: stuff", "body": "BREAKING CHANGE: old removed"},
        ]
        self.assertEqual(determine_bump(commits), "major")

    def test_feat_wins_over_fix(self):
        commits = [
            {"subject": "fix: typo", "body": ""},
            {"subject": "feat: new feature", "body": ""},
            {"subject": "fix: another", "body": ""},
        ]
        self.assertEqual(determine_bump(commits), "minor")

    def test_chore_is_patch(self):
        commits = [{"subject": "chore: update deps", "body": ""}]
        self.assertEqual(determine_bump(commits), "patch")

    def test_scoped_feat(self):
        commits = [{"subject": "feat(auth): add oauth", "body": ""}]
        self.assertEqual(determine_bump(commits), "minor")

    def test_scoped_breaking(self):
        commits = [{"subject": "refactor(core)!: rewrite", "body": ""}]
        self.assertEqual(determine_bump(commits), "major")


# TestBumpVersion removed — comprehensive version with error cases
# lives in test_release_gate.py:TestBumpVersion (6 tests).


class TestWriteVersionToToml(unittest.TestCase):

    def test_append_release_section(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".toml", delete=False,
        ) as f:
            f.write('[project]\nname = "test"\n')
            path = Path(f.name)
        try:
            write_version_to_toml("1.0.0", path)
            text = path.read_text()
            self.assertIn('[release]', text)
            self.assertIn('version = "1.0.0"', text)
            self.assertIn('[project]', text)
            self.assertIn('name = "test"', text)
        finally:
            path.unlink()

    def test_update_existing_version(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".toml", delete=False,
        ) as f:
            f.write('[project]\nname = "test"\n\n[release]\nversion = "0.1.0"\n')
            path = Path(f.name)
        try:
            write_version_to_toml("0.2.0", path)
            text = path.read_text()
            self.assertIn('version = "0.2.0"', text)
            self.assertNotIn('version = "0.1.0"', text)
        finally:
            path.unlink()

    def test_add_version_to_existing_release_section(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".toml", delete=False,
        ) as f:
            f.write('[project]\nname = "test"\n\n[release]\ngate_file = "gates.md"\n')
            path = Path(f.name)
        try:
            write_version_to_toml("0.3.0", path)
            text = path.read_text()
            self.assertIn('version = "0.3.0"', text)
            self.assertIn('gate_file = "gates.md"', text)
        finally:
            path.unlink()

    def test_array_of_tables_after_release(self):
        """BH-P11-106: [[plugins]] after [release] must not split the section."""
        toml_content = (
            '[release]\nversion = "1.0"\n\n'
            '[[plugins]]\nname = "foo"\n'
        )
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".toml", delete=False,
        ) as f:
            f.write(toml_content)
            path = Path(f.name)
        try:
            write_version_to_toml("2.0.0", path)
            text = path.read_text()
            self.assertIn('version = "2.0.0"', text)
            # [[plugins]] must be preserved intact
            self.assertIn('[[plugins]]', text)
            self.assertIn('name = "foo"', text)
        finally:
            path.unlink()

    def test_multiline_array_in_release_section(self):
        """P7-07/P7-13: Multiline array in [release] must not corrupt next section."""
        toml_content = (
            '[release]\n'
            'gate_checks = [\n'
            '  "check1",\n'
            '  "check2"\n'
            ']\n'
            '\n'
            '[other]\n'
            'key = 1\n'
        )
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".toml", delete=False,
        ) as f:
            f.write(toml_content)
            path = Path(f.name)
        try:
            write_version_to_toml("2.0.0", path)
            text = path.read_text()
            self.assertIn('version = "2.0.0"', text)
            # [other] section must still be intact
            self.assertIn('[other]', text)
            self.assertIn('key = 1', text)
            # Version should be in [release], not [other]
            other_idx = text.index('[other]')
            version_idx = text.index('version = "2.0.0"')
            self.assertLess(version_idx, other_idx)
        finally:
            path.unlink()


# ---------------------------------------------------------------------------
# release_gate.py -- gate validation tests (mocked gh)
# ---------------------------------------------------------------------------

class TestGateStories(unittest.TestCase):

    @patch("release_gate.gh_json")
    def test_all_closed(self, mock_gh):
        mock_gh.return_value = []
        ok, detail = gate_stories("Sprint 1")
        self.assertTrue(ok)
        self.assertIn("closed", detail.lower())
        # BH-P11-052: Verify query includes milestone filter
        call_args = mock_gh.call_args[0][0]
        self.assertIn("--milestone", call_args)
        self.assertIn("Sprint 1", call_args)
        # Verify the --state value is "open" (not "all" or "closed")
        state_idx = call_args.index("--state")
        self.assertEqual(call_args[state_idx + 1], "open")

    @patch("release_gate.gh_json")
    def test_open_issues(self, mock_gh):
        mock_gh.return_value = [
            {"number": 1, "title": "US-0101: Setup"},
            {"number": 2, "title": "US-0102: Feature"},
        ]
        ok, detail = gate_stories("Sprint 1")
        self.assertFalse(ok)
        self.assertIn("2 open", detail)
        # BH-P11-052: Verify query includes milestone filter
        call_args = mock_gh.call_args[0][0]
        self.assertIn("Sprint 1", call_args)


class TestGateCI(unittest.TestCase):

    @patch("release_gate.gh_json")
    def test_passing(self, mock_gh):
        mock_gh.return_value = [
            {"status": "completed", "conclusion": "success", "name": "CI"},
        ]
        ok, detail = gate_ci({"project": {}})
        self.assertTrue(ok)
        # BH-P11-053: Verify query includes branch filter
        call_args = mock_gh.call_args[0][0]
        self.assertIn("--branch", call_args)
        self.assertIn("main", call_args)  # default base_branch

    @patch("release_gate.gh_json")
    def test_failing(self, mock_gh):
        mock_gh.return_value = [
            {"status": "completed", "conclusion": "failure", "name": "CI"},
        ]
        ok, detail = gate_ci({"project": {}})
        self.assertFalse(ok)
        self.assertIn("failure", detail)
        # BH-P11-053: Verify query includes branch filter
        call_args = mock_gh.call_args[0][0]
        self.assertIn("--branch", call_args)

    @patch("release_gate.gh_json")
    def test_no_runs(self, mock_gh):
        mock_gh.return_value = []
        ok, detail = gate_ci({"project": {}})
        self.assertFalse(ok)


class TestGatePRs(unittest.TestCase):

    @patch("release_gate.gh_json")
    def test_no_prs(self, mock_gh):
        mock_gh.return_value = []
        ok, _ = gate_prs("Sprint 1")
        self.assertTrue(ok)

    @patch("release_gate.gh_json")
    def test_open_pr_for_milestone(self, mock_gh):
        mock_gh.return_value = [
            {"number": 10, "title": "feat: thing",
             "milestone": {"title": "Sprint 1"}},
        ]
        ok, detail = gate_prs("Sprint 1")
        self.assertFalse(ok)

    @patch("release_gate.gh_json")
    def test_pr_for_different_milestone(self, mock_gh):
        mock_gh.return_value = [
            {"number": 10, "title": "feat: thing",
             "milestone": {"title": "Sprint 2"}},
        ]
        ok, _ = gate_prs("Sprint 1")
        self.assertTrue(ok)

    @patch("release_gate.gh_json")
    @patch("release_gate.warn_if_at_limit")
    def test_limit_hit_fails_gate(self, mock_warn, mock_gh):
        """P7-03/P7-12: When 500 PRs returned, gate fails due to truncation risk."""
        mock_gh.return_value = [
            {"number": i, "title": f"PR {i}", "milestone": None}
            for i in range(500)
        ]
        ok, detail = gate_prs("Sprint 1")
        self.assertFalse(ok)
        self.assertIn("truncated", detail)


class TestGenerateReleaseNotes(unittest.TestCase):

    def test_basic_notes(self):
        commits = [
            {"subject": "feat: add login", "body": ""},
            {"subject": "fix: typo in config", "body": ""},
        ]
        config = {"project": {"repo": "test/repo"}}
        notes = generate_release_notes("0.2.0", "0.1.0", commits, "Sprint 1", config)
        self.assertIn("v0.2.0", notes)
        self.assertIn("## Features", notes)
        self.assertIn("## Fixes", notes)
        # In test env the prior tag doesn't exist, so we get initial release text
        self.assertIn("## Full Changelog", notes)

    def test_breaking_changes(self):
        commits = [
            {"subject": "feat!: new API", "body": "BREAKING CHANGE: old removed"},
        ]
        config = {"project": {"repo": "test/repo"}}
        notes = generate_release_notes("1.0.0", "0.5.0", commits, "Sprint 3", config)
        self.assertIn("## Breaking Changes", notes)


if __name__ == "__main__":
    unittest.main()
