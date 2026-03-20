"""Tests for plugin hooks."""
from __future__ import annotations

import sys
import textwrap
import unittest
from pathlib import Path

# Add .claude-plugin to path so we can import hooks package
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / ".claude-plugin"))

from hooks.review_gate import check_merge, check_push, _log_blocked, _get_base_branch
from hooks.verify_agent_output import (
    load_check_commands, run_verification, _read_toml_key,
    update_tracking_verification, _is_implementer_output,
    _resolve_tracking_path,
)
from hooks._common import _find_project_root
from hooks.session_context import (
    extract_retro_action_items, extract_dod_retro_additions,
    extract_high_risks, format_context, _parse_action_items,
)
from hooks.commit_gate import (
    check_commit_allowed, is_source_file, _matches_check_command,
)


class TestCheckMerge(unittest.TestCase):
    """P0-HOOK-1: Review gate — merge blocking."""

    def test_blocked_when_no_review(self):
        """PR merge blocked when review decision is not APPROVED."""
        result = check_merge(
            "gh pr merge 42 --squash",
            base="main",
            _review_decision="",
        )
        self.assertEqual(result, "blocked")

    def test_blocked_when_changes_requested(self):
        result = check_merge(
            "gh pr merge 42 --squash",
            base="main",
            _review_decision="CHANGES_REQUESTED",
        )
        self.assertEqual(result, "blocked")

    def test_allowed_when_approved(self):
        """PR merge allowed when review decision is APPROVED."""
        result = check_merge(
            "gh pr merge 42 --squash",
            base="main",
            _review_decision="APPROVED",
        )
        self.assertEqual(result, "allowed")

    def test_allowed_for_non_merge_commands(self):
        result = check_merge("gh pr view 42", base="main")
        self.assertEqual(result, "allowed")

    def test_blocked_when_review_required(self):
        """REVIEW_REQUIRED decision also returns blocked."""
        result = check_merge(
            "gh pr merge 99 --squash",
            base="main",
            _review_decision="REVIEW_REQUIRED",
        )
        self.assertEqual(result, "blocked")

    def test_blocked_bare_merge_no_pr_number(self):
        """H-013: 'gh pr merge' without a PR number is blocked (fail closed)."""
        result = check_merge("gh pr merge", base="main")
        self.assertEqual(result, "blocked")

    def test_blocked_merge_with_flags_no_pr_number(self):
        """H-013: 'gh pr merge --squash' without a PR number is blocked."""
        result = check_merge("gh pr merge --squash", base="main")
        self.assertEqual(result, "blocked")

    def test_blocked_merge_with_delete_branch_no_pr_number(self):
        """H-013: 'gh pr merge --squash --delete-branch' without PR number is blocked."""
        result = check_merge(
            "gh pr merge --squash --delete-branch", base="main"
        )
        self.assertEqual(result, "blocked")


class TestCheckPush(unittest.TestCase):
    """P0-HOOK-1 / P1-HOOK-4: Direct push prevention."""

    def test_direct_push_to_base_blocked(self):
        """git push origin main is blocked when base is main."""
        result = check_push("git push origin main", base="main")
        self.assertEqual(result, "blocked")

    def test_feature_branch_push_allowed(self):
        """git push origin sprint-1/ST-0001-some-feature is allowed."""
        result = check_push(
            "git push origin sprint-1/ST-0001-some-feature",
            base="main",
        )
        self.assertEqual(result, "allowed")

    def test_feature_branch_push_with_u_allowed(self):
        """git push -u origin sprint-1/ST-0001-some-feature is allowed."""
        result = check_push(
            "git push -u origin sprint-1/ST-0001-some-feature",
            base="main",
        )
        self.assertEqual(result, "allowed")

    def test_push_to_non_default_base_blocked(self):
        """Block push to custom base branch."""
        result = check_push("git push origin develop", base="develop")
        self.assertEqual(result, "blocked")

    def test_non_push_command_allowed(self):
        result = check_push("git status", base="main")
        self.assertEqual(result, "allowed")

    def test_push_without_refspec_allowed(self):
        """git push origin (no explicit branch) is allowed."""
        result = check_push("git push origin", base="main")
        self.assertEqual(result, "allowed")

    def test_bare_push_warns(self):
        """BH25-004: git push with no args should return 'warn' — could push to base."""
        result = check_push("git push", base="main")
        self.assertEqual(result, "warn")


class TestLogBlocked(unittest.TestCase):
    """H-003: _log_blocked only writes when giles is configured."""

    def test_no_log_without_project_toml(self):
        """_log_blocked should not create directories when project.toml is missing."""
        import os
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            orig = os.getcwd()
            try:
                os.chdir(td)
                _log_blocked("gh pr merge 42", "test reason")
                # sprint-config/ should NOT have been created
                self.assertFalse(Path("sprint-config").exists())
            finally:
                os.chdir(orig)

    def test_log_written_with_project_toml(self):
        """_log_blocked writes audit log when project.toml exists."""
        import os
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            orig = os.getcwd()
            try:
                os.chdir(td)
                sc = Path("sprint-config")
                sc.mkdir()
                (sc / "project.toml").write_text('[project]\nname = "test"\n')
                _log_blocked("gh pr merge 42", "test reason")
                log_path = sc / "sprints" / "hook-audit.log"
                self.assertTrue(log_path.exists())
                content = log_path.read_text()
                self.assertIn("BLOCKED", content)
                self.assertIn("test reason", content)
            finally:
                os.chdir(orig)


class TestGetBaseBranch(unittest.TestCase):
    """H-004: _get_base_branch only reads base_branch from [project] section."""

    def test_reads_base_branch_from_project_section(self):
        """base_branch in [project] is correctly returned."""
        import os
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            orig = os.getcwd()
            try:
                os.chdir(td)
                sc = Path("sprint-config")
                sc.mkdir()
                (sc / "project.toml").write_text(
                    '[project]\nname = "test"\nbase_branch = "develop"\n'
                )
                self.assertEqual(_get_base_branch(), "develop")
            finally:
                os.chdir(orig)

    def test_ignores_base_branch_in_wrong_section(self):
        """base_branch in a non-[project] section should be ignored."""
        import os
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            orig = os.getcwd()
            try:
                os.chdir(td)
                sc = Path("sprint-config")
                sc.mkdir()
                (sc / "project.toml").write_text(
                    '[project]\nname = "test"\n\n'
                    '[ci]\nbase_branch = "ci-branch"\n'
                )
                # Should return default "main", not "ci-branch"
                self.assertEqual(_get_base_branch(), "main")
            finally:
                os.chdir(orig)

    def test_defaults_to_main_when_no_file(self):
        """Returns 'main' when project.toml does not exist."""
        import os
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            orig = os.getcwd()
            try:
                os.chdir(td)
                self.assertEqual(_get_base_branch(), "main")
            finally:
                os.chdir(orig)

    def test_defaults_to_main_when_key_missing(self):
        """Returns 'main' when [project] exists but base_branch is absent."""
        import os
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            orig = os.getcwd()
            try:
                os.chdir(td)
                sc = Path("sprint-config")
                sc.mkdir()
                (sc / "project.toml").write_text(
                    '[project]\nname = "test"\nlanguage = "python"\n'
                )
                self.assertEqual(_get_base_branch(), "main")
            finally:
                os.chdir(orig)


class TestVerifyAgentOutput(unittest.TestCase):
    """P0-HOOK-2: SubagentStop verification hook."""

    def test_load_check_commands_from_toml(self):
        """Given a project.toml with check_commands, they are loaded."""
        import tempfile
        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            f.write('[ci]\ncheck_commands = ["python -m pytest"]\n')
            f.flush()
            cmds, smoke = load_check_commands(f.name)
        self.assertEqual(cmds, ["python -m pytest"])
        self.assertIsNone(smoke)

    def test_verification_passed_all_exit_zero(self):
        """When all check commands exit zero, report contains VERIFICATION PASSED."""
        report, passed = run_verification(["true"])
        self.assertTrue(passed)
        self.assertIn("VERIFICATION PASSED", report)

    def test_verification_failed_nonzero_exit(self):
        """When a check command exits non-zero, report contains VERIFICATION FAILED."""
        report, passed = run_verification(["false"])
        self.assertFalse(passed)
        self.assertIn("VERIFICATION FAILED", report)

    def test_verification_failed_includes_stderr(self):
        """Failed command stderr appears in the report."""
        report, passed = run_verification(
            ["bash -c 'echo badness >&2; exit 1'"]
        )
        self.assertFalse(passed)
        self.assertIn("badness", report)

    def test_verification_skipped_no_commands(self):
        """No check_commands configured results in SKIPPED."""
        report, passed = run_verification([])
        self.assertTrue(passed)
        self.assertIn("VERIFICATION SKIPPED", report)

    def test_read_toml_key_array(self):
        toml = '[ci]\ncheck_commands = ["pytest", "ruff check ."]\n'
        result = _read_toml_key(toml, "ci", "check_commands")
        self.assertEqual(result, ["pytest", "ruff check ."])

    def test_read_toml_key_multiline_array(self):
        """BH25-002: Multi-line arrays must be parsed correctly."""
        toml = (
            '[ci]\n'
            'check_commands = [\n'
            '    "python -m pytest tests/",\n'
            '    "ruff check .",\n'
            ']\n'
        )
        result = _read_toml_key(toml, "ci", "check_commands")
        self.assertEqual(result, ["python -m pytest tests/", "ruff check ."])

    def test_read_toml_key_string(self):
        toml = '[ci]\nsmoke_command = "python -m myapp --health"\n'
        result = _read_toml_key(toml, "ci", "smoke_command")
        self.assertEqual(result, "python -m myapp --health")

    def test_read_toml_key_inline_comment(self):
        """DA-007: Inline comments should be stripped."""
        toml = '[ci]\nsmoke_command = "make smoke" # quick check\n'
        result = _read_toml_key(toml, "ci", "smoke_command")
        self.assertEqual(result, "make smoke")

    def test_read_toml_key_single_quoted(self):
        """DA-010: Single-quoted strings should work."""
        toml = "[ci]\ncheck_commands = ['pytest', 'ruff check']\n"
        result = _read_toml_key(toml, "ci", "check_commands")
        self.assertEqual(result, ["pytest", "ruff check"])

    def test_read_toml_key_bracket_inside_quotes(self):
        """DA-009: ] inside quoted string should not end array."""
        toml = (
            '[ci]\n'
            'check_commands = [\n'
            '    "pytest -k \'test[param]\'",\n'
            '    "ruff check",\n'
            ']\n'
        )
        result = _read_toml_key(toml, "ci", "check_commands")
        self.assertEqual(result, ["pytest -k 'test[param]'", "ruff check"])


    def test_read_toml_key_escaped_quote_with_bracket(self):
        """BH26-005: Backslash-escaped quote with ] inside should parse correctly."""
        toml = (
            '[ci]\n'
            'check_commands = [\n'
            '    "pytest -k \\"test[param]\\"",\n'
            '    "ruff check",\n'
            ']\n'
        )
        result = _read_toml_key(toml, "ci", "check_commands")
        self.assertEqual(len(result), 2)
        self.assertEqual(result[1], "ruff check")

    def test_read_toml_key_inline_comment_after_escaped_quote(self):
        """BH26-005: Inline comment after escaped-quote value should be stripped."""
        toml = '[ci]\nsmoke_command = "echo \\"hello\\"" # a comment\n'
        result = _read_toml_key(toml, "ci", "smoke_command")
        self.assertEqual(result, 'echo \\"hello\\"')


class TestSessionContext(unittest.TestCase):
    """P0-HOOK-3: SessionStart context injection hook."""

    def test_parse_action_items_from_retro(self):
        """Given a retro.md with 3 action items, all 3 are extracted."""
        retro = textwrap.dedent("""\
            # Sprint 1 Retro

            ## Action Items for Next Sprint
            | Item | Owner | Due |
            |---|---|---|
            | Add integration tests | rae | Sprint 2 |
            | Update CI timeout | chen | Sprint 2 |
            | Fix flaky test | sana | Sprint 2 |

            ## Velocity
        """)
        items = _parse_action_items(retro)
        self.assertEqual(len(items), 3)
        self.assertIn("Add integration tests", items)
        self.assertIn("Fix flaky test", items)

    def test_extract_retro_from_sprint_dir(self):
        """Finds the most recent retro.md in sprint directories."""
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            s1 = Path(td) / "sprint-1"
            s1.mkdir()
            (s1 / "retro.md").write_text(textwrap.dedent("""\
                # Sprint 1 Retro
                ## Action Items for Next Sprint
                | Item | Owner | Due |
                |---|---|---|
                | Old item | x | y |
            """))
            s2 = Path(td) / "sprint-2"
            s2.mkdir()
            (s2 / "retro.md").write_text(textwrap.dedent("""\
                # Sprint 2 Retro
                ## Action Items for Next Sprint
                | Item | Owner | Due |
                |---|---|---|
                | New item | a | b |
            """))
            items = extract_retro_action_items(td)
            self.assertEqual(items, ["New item"])

    def test_extract_high_risks(self):
        """Given a risk-register.md with 2 high-severity open risks, both extracted."""
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            risk_path = Path(td) / "risk-register.md"
            risk_path.write_text(textwrap.dedent("""\
                # Risk Register
                | ID | Title | Severity | Status | Raised |
                |----|-------|----------|--------|--------|
                | R1 | No integration tests | High | Open | Sprint 1 |
                | R2 | Missing smoke test | High | Open | Sprint 1 |
                | R3 | Minor doc gap | Low | Open | Sprint 1 |
                | R4 | Resolved risk | High | Resolved | Sprint 1 |
            """))
            risks = extract_high_risks(td)
            self.assertEqual(len(risks), 2)
            self.assertTrue(any("No integration tests" in r for r in risks))
            self.assertTrue(any("Missing smoke test" in r for r in risks))

    def test_no_retro_exits_cleanly(self):
        """When no retro.md exists (first sprint), returns empty list."""
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            items = extract_retro_action_items(td)
            self.assertEqual(items, [])

    def test_format_context_under_60_lines(self):
        """Hook output stays compact."""
        output = format_context(
            ["item1", "item2", "item3"],
            ["dod1"],
            ["risk1", "risk2"],
        )
        line_count = len(output.strip().splitlines())
        self.assertLess(line_count, 60)
        self.assertIn("item1", output)
        self.assertIn("risk1", output)

    def test_format_context_empty_when_no_data(self):
        """No data produces empty output."""
        output = format_context([], [], [])
        self.assertEqual(output, "")


class TestCommitGate(unittest.TestCase):
    """P1-HOOK-5: Commit verification hook."""

    def test_blocks_commit_when_unverified(self):
        """Block git commit when source files modified but no check run."""
        result = check_commit_allowed("git commit -m 'fix'", _state_override=True)
        self.assertEqual(result, "blocked")

    def test_allows_commit_when_verified(self):
        """Allow git commit when checks have been run."""
        result = check_commit_allowed("git commit -m 'fix'", _state_override=False)
        self.assertEqual(result, "allowed")

    def test_allows_non_commit_commands(self):
        """Non-commit commands are always allowed."""
        result = check_commit_allowed("git status", _state_override=True)
        self.assertEqual(result, "allowed")

    def test_blocks_commit_py(self):
        """Also blocks scripts/commit.py invocations."""
        result = check_commit_allowed(
            'python scripts/commit.py "feat: add thing"',
            _state_override=True,
        )
        self.assertEqual(result, "blocked")

    def test_source_file_detection(self):
        """Source files vs non-source files."""
        self.assertTrue(is_source_file("src/main.py"))
        self.assertTrue(is_source_file("lib/parser.rs"))
        self.assertTrue(is_source_file("app.swift"))
        self.assertTrue(is_source_file("handler.ts"))
        self.assertFalse(is_source_file("README.md"))
        self.assertFalse(is_source_file("config.toml"))
        self.assertFalse(is_source_file("data.json"))

    def test_matches_check_commands(self):
        """Recognizes common test/check commands."""
        self.assertTrue(_matches_check_command("pytest"))
        self.assertTrue(_matches_check_command("python -m pytest tests/"))
        self.assertTrue(_matches_check_command("cargo test"))
        self.assertTrue(_matches_check_command("npm test"))
        self.assertTrue(_matches_check_command("ruff check ."))
        self.assertTrue(_matches_check_command("make test"))
        self.assertTrue(_matches_check_command("bazel test //..."))
        self.assertFalse(_matches_check_command("git status"))
        self.assertFalse(_matches_check_command("echo hello"))

    def test_mark_verified_then_commit_allowed(self):
        """H3: Test the actual state machine, not just _state_override."""
        from hooks.commit_gate import mark_verified, needs_verification, _state_file
        sf = _state_file()
        # Clean up any leftover state
        if sf.exists():
            sf.unlink()
        try:
            # After mark_verified, the hash is recorded and commit is allowed
            # (working tree hasn't changed since mark)
            mark_verified()
            self.assertFalse(needs_verification(),
                             "Working tree should match the hash we just recorded")
            result = check_commit_allowed("git commit -m 'fix'")
            self.assertEqual(result, "allowed")
        finally:
            if sf.exists():
                sf.unlink()

    def test_stale_hash_blocks_commit(self):
        """Commit is blocked when state file hash doesn't match working tree."""
        from hooks.commit_gate import needs_verification, _state_file
        sf = _state_file()
        try:
            # Write a stale hash that doesn't match current working tree
            sf.write_text("stale_hash_that_wont_match", encoding="utf-8")
            self.assertTrue(needs_verification(),
                            "Stale hash should trigger needs_verification")
            result = check_commit_allowed("git commit -m 'fix'")
            self.assertEqual(result, "blocked")
        finally:
            if sf.exists():
                sf.unlink()


class TestUpdateTrackingVerification(unittest.TestCase):
    """BH25-014: update_tracking_verification writes to YAML frontmatter."""

    def _make_tracking_file(self, tmp_dir, content):
        """Helper: write a tracking file and return its path."""
        p = Path(tmp_dir) / "US-0001.md"
        p.write_text(content, encoding="utf-8")
        return str(p)

    def test_writes_verification_passed(self):
        """Writing passed verification adds verification_agent_stop: passed."""
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            path = self._make_tracking_file(td, textwrap.dedent("""\
                ---
                story: US-0001
                title: "Test story"
                sprint: 1
                status: dev
                ---
                body text
            """))
            update_tracking_verification(path, True, "VERIFICATION PASSED")
            content = Path(path).read_text(encoding="utf-8")
            self.assertIn("verification_agent_stop: passed", content)
            # Body text must survive
            self.assertIn("body text", content)

    def test_writes_verification_failed(self):
        """Writing failed verification adds verification_agent_stop: failed."""
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            path = self._make_tracking_file(td, textwrap.dedent("""\
                ---
                story: US-0001
                title: "Test story"
                sprint: 1
                status: dev
                ---
                body text
            """))
            update_tracking_verification(path, False, "VERIFICATION FAILED")
            content = Path(path).read_text(encoding="utf-8")
            self.assertIn("verification_agent_stop: failed", content)

    def test_update_does_not_duplicate_field(self):
        """Writing verification twice updates the field, not duplicates it."""
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            path = self._make_tracking_file(td, textwrap.dedent("""\
                ---
                story: US-0001
                title: "Test story"
                sprint: 1
                status: dev
                ---
                body text
            """))
            update_tracking_verification(path, True, "VERIFICATION PASSED")
            update_tracking_verification(path, False, "VERIFICATION FAILED")
            content = Path(path).read_text(encoding="utf-8")
            self.assertIn("verification_agent_stop: failed", content)
            self.assertNotIn("verification_agent_stop: passed", content)
            # Must appear exactly once
            count = content.count("verification_agent_stop:")
            self.assertEqual(count, 1,
                             f"Expected 1 occurrence, found {count}")

    def test_no_frontmatter_is_noop(self):
        """File without YAML frontmatter is left unchanged."""
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            path = self._make_tracking_file(td, "just plain text\n")
            update_tracking_verification(path, True, "VERIFICATION PASSED")
            content = Path(path).read_text(encoding="utf-8")
            self.assertEqual(content, "just plain text\n")

    def test_missing_file_is_noop(self):
        """Non-existent file does not raise."""
        update_tracking_verification("/tmp/nonexistent-tracking.md", True, "ok")


class TestResolveTrackingPath(unittest.TestCase):
    """BH26-001: _resolve_tracking_path resolves sprint-relative paths."""

    def test_resolves_via_sprints_dir(self):
        """Path resolves against sprints_dir from project.toml."""
        import os
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            orig = os.getcwd()
            try:
                os.chdir(td)
                sc = Path("sprint-config")
                sc.mkdir()
                (sc / "project.toml").write_text(
                    '[project]\nname = "test"\n\n'
                    '[paths]\nsprints_dir = "sprints"\n'
                )
                stories = Path("sprints/sprint-1/stories")
                stories.mkdir(parents=True)
                tf = stories / "US-0001-feat.md"
                tf.write_text("---\nstory: US-0001\nstatus: dev\n---\nbody\n")
                resolved = _resolve_tracking_path("sprint-1/stories/US-0001-feat.md")
                self.assertIsNotNone(resolved)
                self.assertTrue(Path(resolved).is_file())
            finally:
                os.chdir(orig)

    def test_resolves_direct_under_root(self):
        """Fallback: path found directly under project root."""
        import os
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            orig = os.getcwd()
            try:
                os.chdir(td)
                sc = Path("sprint-config")
                sc.mkdir()
                (sc / "project.toml").write_text('[project]\nname = "test"\n')
                stories = Path("sprint-1/stories")
                stories.mkdir(parents=True)
                tf = stories / "US-0001-feat.md"
                tf.write_text("---\nstory: US-0001\nstatus: dev\n---\nbody\n")
                resolved = _resolve_tracking_path("sprint-1/stories/US-0001-feat.md")
                self.assertIsNotNone(resolved)
                self.assertTrue(Path(resolved).is_file())
            finally:
                os.chdir(orig)

    def test_returns_none_when_not_found(self):
        """Returns None when the file doesn't exist anywhere."""
        import os
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            orig = os.getcwd()
            try:
                os.chdir(td)
                resolved = _resolve_tracking_path("sprint-1/stories/US-0001.md")
                self.assertIsNone(resolved)
            finally:
                os.chdir(orig)

    def test_integration_with_update_tracking(self):
        """BH26-001: End-to-end — resolve path then update verification field."""
        import os
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            orig = os.getcwd()
            try:
                os.chdir(td)
                sc = Path("sprint-config")
                sc.mkdir()
                (sc / "project.toml").write_text(
                    '[project]\nname = "test"\n\n'
                    '[paths]\nsprints_dir = "sprints"\n'
                )
                stories = Path("sprints/sprint-1/stories")
                stories.mkdir(parents=True)
                tf = stories / "US-0001-feat.md"
                tf.write_text("---\nstory: US-0001\nstatus: dev\n---\nbody\n")
                resolved = _resolve_tracking_path("sprint-1/stories/US-0001-feat.md")
                self.assertIsNotNone(resolved)
                update_tracking_verification(resolved, True, "PASSED")
                content = tf.read_text()
                self.assertIn("verification_agent_stop: passed", content)
            finally:
                os.chdir(orig)


class TestFindProjectRoot(unittest.TestCase):
    """H-012: _find_project_root searches upward for sprint-config/project.toml."""

    def test_finds_root_in_cwd(self):
        """When sprint-config/project.toml is in CWD, returns CWD."""
        import os
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            orig = os.getcwd()
            try:
                os.chdir(td)
                sc = Path("sprint-config")
                sc.mkdir()
                (sc / "project.toml").write_text('[project]\nname = "test"\n')
                root = _find_project_root()
                self.assertTrue(
                    (root / "sprint-config" / "project.toml").is_file()
                )
            finally:
                os.chdir(orig)

    def test_finds_root_in_parent(self):
        """When CWD is a subdirectory, walks up to find project root."""
        import os
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            orig = os.getcwd()
            try:
                sc = Path(td) / "sprint-config"
                sc.mkdir()
                (sc / "project.toml").write_text('[project]\nname = "test"\n')
                subdir = Path(td) / "src" / "deep"
                subdir.mkdir(parents=True)
                os.chdir(subdir)
                root = _find_project_root()
                self.assertTrue(
                    (root / "sprint-config" / "project.toml").is_file()
                )
            finally:
                os.chdir(orig)

    def test_falls_back_to_cwd(self):
        """When no sprint-config/project.toml exists, returns CWD."""
        import os
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            orig = os.getcwd()
            try:
                os.chdir(td)
                root = _find_project_root()
                self.assertEqual(root, Path.cwd())
            finally:
                os.chdir(orig)

    def test_env_var_override(self):
        """CLAUDE_PROJECT_DIR env var takes precedence."""
        import os
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            orig = os.getcwd()
            orig_env = os.environ.get("CLAUDE_PROJECT_DIR")
            try:
                sc = Path(td) / "sprint-config"
                sc.mkdir()
                (sc / "project.toml").write_text('[project]\nname = "test"\n')
                os.environ["CLAUDE_PROJECT_DIR"] = td
                root = _find_project_root()
                self.assertEqual(root, Path(td))
            finally:
                os.chdir(orig)
                if orig_env is None:
                    os.environ.pop("CLAUDE_PROJECT_DIR", None)
                else:
                    os.environ["CLAUDE_PROJECT_DIR"] = orig_env


class TestIsImplementerOutput(unittest.TestCase):
    """H-014: _is_implementer_output filters non-implementer agents."""

    def test_implementer_with_commit_keyword(self):
        """Output mentioning 'commit' with check_commands is implementer."""
        self.assertTrue(
            _is_implementer_output("I committed the changes", ["pytest"])
        )

    def test_implementer_with_pr_keyword(self):
        """Output mentioning 'PR #' with check_commands is implementer."""
        self.assertTrue(
            _is_implementer_output("Created PR #42", ["pytest"])
        )

    def test_implementer_with_pushed_keyword(self):
        """Output mentioning 'pushed' with check_commands is implementer."""
        self.assertTrue(
            _is_implementer_output("I pushed to the branch", ["pytest"])
        )

    def test_not_implementer_no_keywords(self):
        """Output without implementation keywords is not implementer."""
        self.assertFalse(
            _is_implementer_output("I reviewed the code and it looks good", ["pytest"])
        )

    def test_not_implementer_no_check_commands(self):
        """Even with keywords, no check_commands means not implementer."""
        self.assertFalse(
            _is_implementer_output("I committed the changes", [])
        )

    def test_not_implementer_empty_output(self):
        """Empty output is not implementer."""
        self.assertFalse(
            _is_implementer_output("", ["pytest"])
        )

    def test_implementer_with_merge_keyword(self):
        """BH26-004: Output mentioning 'merged' is implementer."""
        self.assertTrue(
            _is_implementer_output("I merged the branch", ["pytest"])
        )

    def test_implementer_with_branch_keyword(self):
        """BH26-004: Output mentioning 'branch' creation is implementer."""
        self.assertTrue(
            _is_implementer_output("Created branch sprint-1/US-0001", ["pytest"])
        )

    def test_implementer_with_tests_pass(self):
        """BH26-004: Output mentioning test results is implementer."""
        self.assertTrue(
            _is_implementer_output("All tests pass, changes ready", ["pytest"])
        )

    def test_not_implementer_reviewer_mentioning_commit(self):
        """BH26-008: Reviewer saying 'the commit looks good' is NOT implementer."""
        self.assertFalse(
            _is_implementer_output("I reviewed the commit and it looks good", ["pytest"])
        )

    def test_not_implementer_reviewer_mentioning_implementation(self):
        """BH26-008: Reviewer saying 'implementation is solid' is NOT implementer."""
        self.assertFalse(
            _is_implementer_output("The implementation is solid, approved", ["pytest"])
        )


if __name__ == "__main__":
    unittest.main()
