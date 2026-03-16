"""Shared test helpers for gh/gh_json mock verification and pipeline setup.

Provides MonitoredMock and patch_gh to structurally prevent the
"mock-returns-what-you-assert" anti-pattern (BH-P11-201).

Usage::

    from gh_test_helpers import patch_gh

    class TestMyFunction(unittest.TestCase):
        def test_queries_correct_milestone(self):
            with patch_gh("my_module.gh_json", return_value=[]) as mock:
                my_function("Sprint 1")
                # This check is required — without it, patch_gh warns on exit
                self.assertIn("Sprint 1", str(mock.call_args))

If the test calls the mock but never inspects call_args, call_args_list,
assert_called_with, or assert_called_once_with, a UserWarning is emitted
on context exit.  This makes the gap visible in test output without
breaking existing tests.
"""
from __future__ import annotations

import warnings
from contextlib import contextmanager
from unittest.mock import patch


# Attributes on the mock that count as "verifying call args"
_VERIFICATION_ATTRS = frozenset((
    "call_args",
    "call_args_list",
    "assert_called_with",
    "assert_called_once_with",
    "assert_any_call",
    "assert_has_calls",
))


class MonitoredMock:
    """Proxy around a MagicMock that tracks whether call args are inspected.

    Delegates all attribute access to the underlying mock.  When the test
    accesses call_args (or any verification attribute), sets _args_checked
    so patch_gh can verify on cleanup.
    """

    def __init__(self, mock):
        object.__setattr__(self, "_mock", mock)
        object.__setattr__(self, "_args_checked", False)

    def __getattr__(self, name):
        if name in _VERIFICATION_ATTRS:
            object.__setattr__(self, "_args_checked", True)
        return getattr(object.__getattribute__(self, "_mock"), name)

    def __setattr__(self, name, value):
        setattr(object.__getattribute__(self, "_mock"), name, value)

    def __call__(self, *args, **kwargs):
        return object.__getattribute__(self, "_mock")(*args, **kwargs)

    @property
    def args_checked(self) -> bool:
        return object.__getattribute__(self, "_args_checked")


@contextmanager
def patch_gh(target: str, *, return_value=None, side_effect=None):
    """Patch a gh/gh_json function and verify call args are inspected.

    Works like ``unittest.mock.patch`` but wraps the mock in a
    MonitoredMock that tracks whether the test checks call arguments.
    On context exit, if the mock was called but call_args was never
    accessed, emits a UserWarning.

    Args:
        target: Dot-path to the function to patch (e.g., "module.gh_json").
        return_value: Value the mock should return when called.
        side_effect: Side effect for the mock.

    Yields:
        MonitoredMock proxy wrapping the patched mock.

    Example::

        with patch_gh("release_gate.gh_json", return_value=[]) as mock:
            result = gate_stories("Sprint 1")
            # Verify the query — without this, you'll get a warning
            self.assertIn("--milestone", str(mock.call_args))
    """
    with patch(target, return_value=return_value, side_effect=side_effect) as mock:
        monitored = MonitoredMock(mock)
        yield monitored

    # Post-exit verification
    if mock.called and not monitored.args_checked:
        warnings.warn(
            f"Mock for '{target}' was called {mock.call_count} time(s) but "
            f"call_args was never inspected. This test may be verifying mock "
            f"behavior rather than production behavior. Access mock.call_args "
            f"or use mock.assert_called_with() to verify query parameters.",
            UserWarning,
            stacklevel=2,
        )


# ---------------------------------------------------------------------------
# Pipeline test helper: shared issue population logic (P12-023)
# ---------------------------------------------------------------------------

def populate_test_issues(fake_gh, config, populate_issues_mod):
    """Parse milestone stories and create issues on FakeGitHub.

    Extracts the duplicated issue-population block used by test_hexwise_setup,
    test_lifecycle, and test_golden_run into a single function.

    Args:
        fake_gh: FakeGitHub instance (subprocess.run must already be patched).
        config: Project config dict (from parse_simple_toml).
        populate_issues_mod: The imported populate_issues module.

    Returns:
        Tuple of (milestone_files, stories) for further assertions.
    """
    import sys
    from pathlib import Path

    ROOT = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(ROOT / "scripts"))
    from validate_config import get_milestones

    milestone_files = get_milestones(config)
    stories = populate_issues_mod.parse_milestone_stories(
        milestone_files, config,
    )

    ms_numbers = {
        ms["title"]: ms["number"]
        for ms in fake_gh.milestones
    }
    ms_titles = {}
    for i, _mf in enumerate(milestone_files, 1):
        if i <= len(fake_gh.milestones):
            ms_titles[i] = fake_gh.milestones[i - 1]["title"]
        else:
            ms_titles[i] = f"Sprint {i}"

    existing = populate_issues_mod.get_existing_issues()
    for story in stories:
        if story.story_id not in existing:
            populate_issues_mod.create_issue(story, ms_numbers, ms_titles)

    return milestone_files, stories
