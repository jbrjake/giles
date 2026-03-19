#!/usr/bin/env python3
"""Tests for FakeGitHub fidelity — verifying jq expressions and search predicates.

P13-006: Ensure jq expressions from production code produce correct output.
P13-019: Ensure FakeGitHub warns on unrecognized search predicates.
"""
from __future__ import annotations

import json
import unittest
import warnings

import jq as _jq  # required dev dependency

from fake_github import FakeGitHub


# ---------------------------------------------------------------------------
# P13-006: Verify production jq expressions against sample data
# ---------------------------------------------------------------------------

# The exact jq expression used by sync_tracking.get_linked_pr()
_TIMELINE_JQ = (
    '[.[] | select(.source?.issue?.pull_request?) '
    '| .source.issue]'
)


class TestTimelineJqExpression(unittest.TestCase):
    """P13-006: Verify the timeline jq expression matches FakeGitHub's pre-filter logic."""

    def _make_timeline_events(self) -> list[dict]:
        """Sample timeline events mimicking GitHub's /issues/{N}/timeline response."""
        return [
            # Non-PR event (should be filtered out)
            {"event": "labeled", "label": {"name": "kanban:dev"}},
            # Cross-reference to a PR (should be selected)
            {
                "event": "cross-referenced",
                "source": {
                    "issue": {
                        "number": 42,
                        "state": "open",
                        "pull_request": {
                            "merged_at": None,
                        },
                    },
                },
            },
            # Cross-reference to a non-PR issue (should be filtered out)
            {
                "event": "cross-referenced",
                "source": {
                    "issue": {
                        "number": 99,
                        "state": "open",
                        # No pull_request key
                    },
                },
            },
            # Another PR cross-reference (merged)
            {
                "event": "cross-referenced",
                "source": {
                    "issue": {
                        "number": 55,
                        "state": "closed",
                        "pull_request": {
                            "merged_at": "2026-03-10T12:00:00Z",
                        },
                    },
                },
            },
        ]

    def test_jq_expression_filters_correctly(self):
        """The production jq expression selects only PR cross-references."""
        events = self._make_timeline_events()
        result = _jq.first(_TIMELINE_JQ, events)
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 2)
        # Should contain PR #42 and PR #55
        numbers = {r["number"] for r in result}
        self.assertEqual(numbers, {42, 55})

    def test_jq_expression_empty_events(self):
        """Empty event list produces empty result."""
        result = _jq.first(_TIMELINE_JQ, [])
        self.assertEqual(result, [])

    def test_jq_expression_no_prs(self):
        """Events with no PR cross-references produce empty result."""
        events = [
            {"event": "labeled", "label": {"name": "kanban:dev"}},
            {"event": "commented", "body": "looks good"},
        ]
        result = _jq.first(_TIMELINE_JQ, events)
        self.assertEqual(result, [])

    def test_fakegithub_jq_matches_manual_filter(self):
        """FakeGitHub's jq path and manual pre-filter path produce equivalent results."""
        events = self._make_timeline_events()
        fake = FakeGitHub()
        fake.timeline_events[1] = events

        # Path 1: Through jq (when available)
        result_jq = fake.handle([
            "api", "repos/owner/repo/issues/1/timeline",
            "--paginate", "--jq", _TIMELINE_JQ,
        ])
        self.assertEqual(result_jq.returncode, 0)
        jq_data = json.loads(result_jq.stdout)

        # The jq path returns a list of issue objects
        if isinstance(jq_data, list):
            jq_numbers = {d["number"] for d in jq_data}
        else:
            jq_numbers = {jq_data["number"]}

        # Both PRs should be found
        self.assertIn(42, jq_numbers)
        self.assertIn(55, jq_numbers)


# ---------------------------------------------------------------------------
# P13-019: FakeGitHub warns on unrecognized search predicates
# ---------------------------------------------------------------------------


class TestSearchPredicateWarning(unittest.TestCase):
    """P13-019: FakeGitHub warns when --search has predicates beyond milestone."""

    def test_milestone_only_no_warning(self):
        """milestone:"X" alone produces no warning."""
        fake = FakeGitHub(strict=True)
        fake.prs = [
            {"number": 1, "title": "PR1", "state": "open",
             "milestone": {"title": "Sprint 1"}, "headRefName": "feat"},
        ]
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = fake.handle([
                "pr", "list", "--json", "number,title",
                "--search", 'milestone:"Sprint 1"',
            ])
        self.assertEqual(result.returncode, 0)
        search_warnings = [x for x in w if "search" in str(x.message).lower()]
        self.assertEqual(len(search_warnings), 0)

    def test_extra_predicates_warn(self):
        """Search with predicates beyond milestone emits a warning."""
        fake = FakeGitHub(strict=True)
        fake.prs = []
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = fake.handle([
                "pr", "list", "--json", "number",
                "--search", 'milestone:"Sprint 1" is:merged author:bot',
            ])
        self.assertEqual(result.returncode, 0)
        search_warnings = [x for x in w if "search predicate" in str(x.message).lower()]
        self.assertGreaterEqual(len(search_warnings), 1,
                                f"Expected warning about extra predicates, got: {[str(x.message) for x in w]}")


# ---------------------------------------------------------------------------
# BH-002: Milestone issue counters track create/close
# ---------------------------------------------------------------------------


class TestMilestoneCounters(unittest.TestCase):
    """BH-002: Milestone open_issues/closed_issues must update on issue lifecycle."""

    def setUp(self):
        self.fake = FakeGitHub()
        # Create a milestone
        self.fake.handle([
            "api", "repos/owner/repo/milestones",
            "-f", "title=Sprint 1", "-f", "description=test",
        ])

    def test_create_increments_open(self):
        """Creating an issue with a milestone increments open_issues."""
        self.fake.handle([
            "issue", "create", "--title", "US-0001: Story",
            "--body", "body", "--milestone", "Sprint 1",
        ])
        ms = self.fake.milestones[0]
        self.assertEqual(ms["open_issues"], 1)
        self.assertEqual(ms["closed_issues"], 0)

    def test_close_moves_counter(self):
        """Closing an issue decrements open_issues and increments closed_issues."""
        self.fake.handle([
            "issue", "create", "--title", "US-0001: Story",
            "--body", "body", "--milestone", "Sprint 1",
        ])
        self.fake.handle([
            "issue", "create", "--title", "US-0002: Story 2",
            "--body", "body", "--milestone", "Sprint 1",
        ])
        ms = self.fake.milestones[0]
        self.assertEqual(ms["open_issues"], 2)

        self.fake.handle(["issue", "close", "1"])
        ms = self.fake.milestones[0]
        self.assertEqual(ms["open_issues"], 1)
        self.assertEqual(ms["closed_issues"], 1)

    def test_full_lifecycle(self):
        """Create 3 issues, close 2 — counters should be 1 open, 2 closed."""
        for i in range(3):
            self.fake.handle([
                "issue", "create", "--title", f"US-{i:04d}: Story {i}",
                "--body", "body", "--milestone", "Sprint 1",
            ])
        self.fake.handle(["issue", "close", "1"])
        self.fake.handle(["issue", "close", "2"])

        ms = self.fake.milestones[0]
        self.assertEqual(ms["open_issues"], 1)
        self.assertEqual(ms["closed_issues"], 2)

    def test_no_milestone_no_update(self):
        """Issue without milestone doesn't affect any counters."""
        self.fake.handle([
            "issue", "create", "--title", "US-9999: No milestone",
            "--body", "body",
        ])
        ms = self.fake.milestones[0]
        self.assertEqual(ms["open_issues"], 0)
        self.assertEqual(ms["closed_issues"], 0)


# ---------------------------------------------------------------------------
# BH23-122: Issue label manipulation fidelity
# ---------------------------------------------------------------------------


class TestIssueLabelOps(unittest.TestCase):
    """BH23-122: FakeGitHub add-label and remove-label match real gh behavior."""

    def setUp(self):
        self.fake = FakeGitHub()
        self.fake.handle([
            "issue", "create", "--title", "US-0001: Test",
            "--body", "body", "--label", "kanban:todo",
        ])

    def test_add_label(self):
        """issue edit --add-label adds to existing labels."""
        self.fake.handle(["issue", "edit", "1", "--add-label", "persona:rae"])
        issue = self.fake.issues[0]
        label_names = {l["name"] for l in issue["labels"]}
        self.assertIn("kanban:todo", label_names)
        self.assertIn("persona:rae", label_names)

    def test_remove_label(self):
        """issue edit --remove-label removes from existing labels."""
        self.fake.handle(["issue", "edit", "1", "--add-label", "persona:rae"])
        self.fake.handle(["issue", "edit", "1", "--remove-label", "kanban:todo"])
        issue = self.fake.issues[0]
        label_names = {l["name"] for l in issue["labels"]}
        self.assertNotIn("kanban:todo", label_names)
        self.assertIn("persona:rae", label_names)

    def test_add_multiple_labels_separate_flags(self):
        """Multiple --add-label flags each add their label (production pattern)."""
        self.fake.handle([
            "issue", "edit", "1",
            "--add-label", "sprint:1",
            "--add-label", "saga:S01",
        ])
        issue = self.fake.issues[0]
        label_names = {l["name"] for l in issue["labels"]}
        self.assertIn("sprint:1", label_names)
        self.assertIn("saga:S01", label_names)
        self.assertIn("kanban:todo", label_names)  # original preserved


# ---------------------------------------------------------------------------
# BH23-122: Release creation fidelity
# ---------------------------------------------------------------------------


class TestReleaseCreateFidelity(unittest.TestCase):
    """BH23-122: FakeGitHub release create returns expected fields."""

    def setUp(self):
        self.fake = FakeGitHub()

    def test_release_create_returns_url(self):
        """release create returns a URL string (like real gh)."""
        result = self.fake.handle([
            "release", "create", "v1.0.0",
            "--title", "v1.0.0",
            "--notes", "Release notes",
        ])
        self.assertIsInstance(result.stdout, str)
        self.assertIn("v1.0.0", result.stdout)

    def test_release_stored_with_tag(self):
        """Release stored with correct tag_name in state."""
        self.fake.handle([
            "release", "create", "v2.0.0",
            "--title", "v2.0.0",
            "--notes", "Notes",
        ])
        self.assertEqual(len(self.fake.releases), 1)
        self.assertEqual(self.fake.releases[0]["tag_name"], "v2.0.0")


if __name__ == "__main__":
    unittest.main()
