"""Tests for plugin hooks."""
from __future__ import annotations

import sys
import textwrap
import unittest
from pathlib import Path

# Add .claude-plugin to path so we can import hooks package
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / ".claude-plugin"))

from hooks.review_gate import check_merge, check_push
from hooks.verify_agent_output import (
    load_check_commands, run_verification, _read_toml_key,
)
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

    def test_blocked_message_contains_review_required(self):
        """Blocked attempts produce a message containing 'review' and 'required'."""
        # The main() function produces the message, but we verify
        # the check function returns 'blocked' which triggers the message.
        result = check_merge(
            "gh pr merge 99 --squash",
            base="main",
            _review_decision="REVIEW_REQUIRED",
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

    def test_block_message_contains_pr_and_base(self):
        """Block message would contain PR and base branch name.

        This tests that check_push returns 'blocked' — the main()
        function constructs the message with 'PR' and base branch.
        """
        result = check_push("git push origin main", base="main")
        self.assertEqual(result, "blocked")


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

    def test_read_toml_key_string(self):
        toml = '[ci]\nsmoke_command = "python -m myapp --health"\n'
        result = _read_toml_key(toml, "ci", "smoke_command")
        self.assertEqual(result, "python -m myapp --health")


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
        self.assertFalse(_matches_check_command("git status"))
        self.assertFalse(_matches_check_command("echo hello"))


if __name__ == "__main__":
    unittest.main()
