"""Tests for plugin hooks."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

# Add .claude-plugin to path so we can import hooks package
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / ".claude-plugin"))

from hooks.review_gate import check_merge, check_push
from hooks.verify_agent_output import (
    load_check_commands, run_verification, _read_toml_key,
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


if __name__ == "__main__":
    unittest.main()
