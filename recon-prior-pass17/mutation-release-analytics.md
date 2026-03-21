# Mutation Testing: release_gate.py, sprint_analytics.py, manage_epics.py

Date: 2026-03-16

## Summary

| # | File | Function | Mutation | Result |
|---|------|----------|----------|--------|
| 1 | release_gate.py | `bump_version()` | patch `+1` -> `+2` | KILLED |
| 2 | release_gate.py | `determine_bump()` | swap feat (minor) / fix (patch) | KILLED |
| 3 | release_gate.py | `gate_stories()` | invert pass/fail logic | KILLED |
| 4 | release_gate.py | `gate_ci()` | always return `(True, "CI passed")` | KILLED |
| 5 | release_gate.py | `gate_prs()` | check closed PRs instead of open | KILLED |
| 6 | sprint_analytics.py | `compute_velocity()` | count all issues as delivered (ignore state) | KILLED |
| 7 | sprint_analytics.py | `compute_review_rounds()` | count ALL reviews as rounds (not just CHANGES_REQUESTED/APPROVED) | **SURVIVED** |
| 8 | sprint_analytics.py | `format_report()` | omit the velocity line | KILLED |
| 9 | manage_epics.py | `add_story()` | don't add `---` separator before new story | **SURVIVED** |
| 10 | manage_epics.py | `remove_story()` | remove ALL stories instead of just the target | KILLED |

**Killed: 8 / 10 | Survived: 2 / 10**

## Survivor Analysis

### Mutation 7 — `compute_review_rounds()`: count ALL reviews as rounds

**Why it survived:** The test creates reviews only via `gh pr review --approve` and
`gh pr review --request-changes`, which produce review states `APPROVED` and
`CHANGES_REQUESTED` respectively. Both of these states pass the production filter
(`state in ("CHANGES_REQUESTED", "APPROVED")`). No test creates a review with a
non-matching state like `COMMENTED`, `DISMISSED`, or `PENDING`, so counting all
reviews produces identical results to counting only the filtered subset.

**Fix:** Add a test that includes a `COMMENTED` review (via `gh pr review` without
`--approve` or `--request-changes`) alongside real review rounds. Assert that the
COMMENTED review is NOT counted as a round.

### Mutation 9 — `add_story()`: omit `---` separator

**Why it survived:** `test_add_story_to_epic` verifies that the new story ID and
title appear in the file and that `parse_epic()` finds the story, but it never
checks for the `---` separator between stories. The parser itself doesn't require
`---` separators (it finds stories by `### US-XXXX:` headings), so omitting the
separator doesn't break parsing.

**Fix:** Add an assertion in `test_add_story_to_epic` that checks the raw file
content contains `---` before the newly added story section, e.g.:
`self.assertIn("---\n\n### US-0110:", content)`.
