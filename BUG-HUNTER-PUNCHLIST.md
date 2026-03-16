# Bug Hunter Punchlist — Pass 19

> Generated: 2026-03-16 | Project: giles | Baseline: 758 pass, 0 fail, 0 skip | Coverage: 84%
> Method: End-to-end data flow tracing, error path exhaustive audit, FakeGitHub fidelity deep-dive, boundary value analysis, test theater detection

## Summary

| Severity | Open | Resolved | Deferred |
|----------|------|----------|----------|
| CRITICAL | 1    | 0        | 0        |
| HIGH     | 3    | 0        | 0        |
| MEDIUM   | 8    | 0        | 0        |
| LOW      | 3    | 0        | 0        |

## Patterns

### PAT-001: Silent degradation on API failure — callers proceed with empty data
**Instances:** BH19-001, BH19-003
**Root Cause:** Error handlers return empty lists/None instead of raising, and callers don't distinguish "no data" from "API failed"
**Systemic Fix:** Consider a sentinel value or logging that distinguishes "empty result" from "error result"
**Detection Rule:** `grep -n 'except RuntimeError' scripts/validate_config.py` — each handler that returns [] should log at WARNING level

### PAT-002: FakeGitHub quirks that mask real-world behavior
**Instances:** BH19-005, BH19-006, BH19-007
**Root Cause:** FakeGitHub was built incrementally to support specific test scenarios, not from a spec
**Systemic Fix:** Add fidelity assertions to high-traffic handlers; use strict mode enforcement
**Detection Rule:** Compare FakeGitHub handler return shapes against `gh` documentation

### PAT-003: Tests that claim coverage but don't exercise the path
**Instances:** BH19-002, BH19-004, BH19-010
**Root Cause:** Test names/docstrings describe behavior that the test setup doesn't trigger
**Systemic Fix:** Review test names against actual assertions; add coverage markers for untested defense-in-depth
**Detection Rule:** For each test with "failure" or "error" in the name, verify the test actually triggers the failure

## Items

### BH19-001: list_milestone_issues silently returns [] on API failure — all downstream consumers show 0 SP
**Severity:** CRITICAL
**Category:** `bug/silent-failure`
**Location:** `scripts/validate_config.py:968-982` (list_milestone_issues)
**Status:** 🔴 OPEN
**Pattern:** PAT-001

**Problem:** When `gh issue list` fails (auth error, network timeout, rate limit), `list_milestone_issues` catches `RuntimeError`, prints a warning to stderr, and returns `[]`. Callers (sync_tracking, update_burndown, check_milestone, sprint_analytics) receive an empty list and proceed normally — burndown shows 0/0 SP at 0%, sync shows "Everything in sync", analytics shows 0% velocity. There is no way for callers to distinguish "milestone has no issues" from "API call failed."

**Evidence:** Error path audit finding. No test covers this degradation path.

**Acceptance Criteria:**
- [ ] A test mocks `gh_json` to raise RuntimeError inside list_milestone_issues
- [ ] Verifies the empty list is returned (current behavior — documenting, not changing)
- [ ] A test verifies that sync_tracking.main with a failed milestone query prints a meaningful warning (not just "Everything in sync")
- [ ] OR: list_milestone_issues raises instead of swallowing, and callers handle it

**Validation Command:**
```bash
python -m pytest tests/ -k "list_milestone_issues" -v 2>&1 | tail -10
```

---

### BH19-002: TestBH021SyncBacklogPartialFailure is a fake test — never calls do_sync
**Severity:** HIGH
**Category:** `test/theater`
**Location:** `tests/test_bugfix_regression.py` (TestBH021SyncBacklogPartialFailure)
**Status:** 🔴 OPEN
**Pattern:** PAT-003

**Problem:** The test class `TestBH021SyncBacklogPartialFailure` has test method `test_state_not_updated_on_do_sync_failure`. The name and docstring promise: "BH-021: State file must NOT be updated when do_sync() fails." But the test body never calls `do_sync()` or triggers any failure. It just saves a state dict, loads it back, and checks it roundtrips. This is a state-file I/O test masquerading as a failure-path test. The BH-021 fix (don't update state on sync failure) is effectively untested.

**Evidence:** Test theater audit finding #16. The real BH-021 fix is in `sync_backlog.main()` lines 226-231 where `do_sync` failure skips state update.

**Acceptance Criteria:**
- [ ] Rewrite the test to: mock `do_sync` to raise, call `main()`, verify state file was NOT updated with new hashes
- [ ] The test must actually call `sync_backlog.main()` (or the equivalent logic)
- [ ] Flipping the BH-021 fix (always updating state) must cause this test to fail

**Validation Command:**
```bash
python -m pytest tests/test_bugfix_regression.py -k "BH021" -v 2>&1 | tail -10
```

---

### BH19-003: kanban_from_labels crashes on None label element
**Severity:** HIGH
**Category:** `bug/crash`
**Location:** `scripts/validate_config.py:930-940` (kanban_from_labels)
**Status:** 🔴 OPEN
**Pattern:** —

**Problem:** `kanban_from_labels` uses `label if isinstance(label, str) else label.get("name", "")`. If a label element is `None` (possible in malformed/partial API responses), `isinstance(label, str)` is False and `None.get("name", "")` raises `AttributeError`. By contrast, `extract_sp` has a safer pattern: `isinstance(label, str)` / `isinstance(label, dict)` / `else: continue`.

**Evidence:** Boundary value audit finding 4.1.

**Acceptance Criteria:**
- [ ] `kanban_from_labels` handles `None`, `int`, and other non-str/non-dict label types without crashing
- [ ] A test passes `{"labels": [None, {"name": "kanban:dev"}], "state": "open"}` and gets "dev" back
- [ ] A test passes `{"labels": [42, True], "state": "open"}` and gets the fallback ("todo")

**Validation Command:**
```bash
python -c "
import sys; sys.path.insert(0, 'scripts')
from validate_config import kanban_from_labels
# This currently crashes:
try:
    result = kanban_from_labels({'labels': [None, {'name': 'kanban:dev'}], 'state': 'open'})
    print(f'Result: {result}')
except AttributeError as e:
    print(f'CRASH: {e}')
"
```

---

### BH19-004: BH18-014 path traversal protection in _symlink is completely untested
**Severity:** HIGH
**Category:** `test/missing`
**Location:** `scripts/sprint_init.py:549-572` (_symlink)
**Status:** 🔴 OPEN
**Pattern:** PAT-003

**Problem:** Pass 18 added path traversal validation to `_symlink()` (resolves target, checks relative_to project root). But no test was written for it. If the containment check has a logic error (e.g., symlink-based bypass, edge case with `..`), the vulnerability it's supposed to prevent remains open.

**Acceptance Criteria:**
- [ ] A test calls `_symlink("link.md", "../../etc/passwd")` on a ConfigGenerator instance
- [ ] Verifies the symlink is NOT created (check skipped list for "REJECTED")
- [ ] A test calls `_symlink("link.md", "docs/rules.md")` (valid intra-project target) and verifies it IS created
- [ ] A test with a path that resolves inside the root after normalization (e.g., "subdir/../valid.md") succeeds

**Validation Command:**
```bash
python -m pytest tests/ -k "symlink_traversal or symlink_reject" -v 2>&1 | tail -10
```

---

### BH19-005: FakeGitHub PR state is lowercase but real gh returns uppercase
**Severity:** MEDIUM
**Category:** `test-infra/fidelity`
**Location:** `tests/fake_github.py:803` (_pr_create), `tests/fake_github.py:867` (_pr_merge)
**Status:** 🔴 OPEN
**Pattern:** PAT-002

**Problem:** FakeGitHub stores PR state as `"open"`, `"closed"` (lowercase) but real `gh pr list --json state` returns `"OPEN"`, `"CLOSED"`, `"MERGED"` (uppercase). Any production code that compares `pr["state"]` directly would work in tests but fail in production.

**Acceptance Criteria:**
- [ ] FakeGitHub stores PR state in uppercase: `"OPEN"`, `"CLOSED"`, `"MERGED"`
- [ ] All tests that set PR state directly (outside FakeGitHub) use uppercase
- [ ] `_pr_list` `--state` filter is case-insensitive (matches both "open" and "OPEN")
- [ ] A fidelity test verifies `_pr_create` sets state to `"OPEN"`

**Validation Command:**
```bash
python -c "
from tests.fake_github import FakeGitHub
fg = FakeGitHub()
fg.handle(['pr', 'create', '--title', 'test', '--head', 'feat'])
print('PR state:', fg.prs[0]['state'])
# Should be 'OPEN' after fix
"
```

---

### BH19-006: FakeGitHub issue edit --milestone does not update milestone counters
**Severity:** MEDIUM
**Category:** `test-infra/fidelity`
**Location:** `tests/fake_github.py:637-639` (_issue_edit milestone handling)
**Status:** 🔴 OPEN
**Pattern:** PAT-002

**Problem:** When an issue's milestone is changed via `issue edit --milestone "New Milestone"`, FakeGitHub updates the issue's milestone field but does NOT decrement the old milestone's `open_issues` or increment the new milestone's `open_issues`. check_milestone() reads these counters (check_status.py:190-191), so tests that edit milestones then check progress get stale counts.

**Acceptance Criteria:**
- [ ] `_issue_edit` with `--milestone` updates counters on both old and new milestones
- [ ] A test creates an issue in Milestone A, edits it to Milestone B, and verifies both milestone counters are correct

**Validation Command:**
```bash
python -m pytest tests/test_fakegithub_fidelity.py -v 2>&1 | tail -10
```

---

### BH19-007: FakeGitHub uses separate counters for issues and PRs — real GitHub shares them
**Severity:** MEDIUM
**Category:** `test-infra/fidelity`
**Location:** `tests/fake_github.py:35-37` (_next_issue, _next_ms, _next_pr)
**Status:** 🔴 OPEN
**Pattern:** PAT-002

**Problem:** Real GitHub uses a single shared counter for issues and PRs (creating issue #1 then a PR gives it #2). FakeGitHub has separate `_next_issue = 1` and `_next_pr = 1`, so creating issue #1 then PR #1 gives overlapping numbers. This could mask bugs where code assumes issue and PR numbers are unique across both.

**Acceptance Criteria:**
- [ ] FakeGitHub uses a single `_next_number` counter shared between issues and PRs
- [ ] A test creates issue then PR and verifies numbers are sequential (1, 2, not 1, 1)

**Validation Command:**
```bash
python -c "
from tests.fake_github import FakeGitHub
fg = FakeGitHub()
fg.handle(['api', 'repos/o/r/milestones', '-f', 'title=Sprint 1'])
fg.handle(['issue', 'create', '--title', 'Issue 1', '--milestone', 'Sprint 1'])
fg.handle(['pr', 'create', '--title', 'PR 1', '--head', 'feat'])
print(f'Issue number: {fg.issues[0][\"number\"]}')
print(f'PR number: {fg.prs[0][\"number\"]}')
# Currently both are 1; should be 1 and 2
"
```

---

### BH19-008: No roundtrip test for format_issue_body → extract_sp
**Severity:** MEDIUM
**Category:** `test/missing`
**Location:** `skills/sprint-setup/scripts/populate_issues.py:405` (format_issue_body), `scripts/validate_config.py:781` (extract_sp)
**Status:** 🔴 OPEN
**Pattern:** —

**Problem:** `format_issue_body` writes SP in the format `| 5 SP | P1` and `extract_sp` reads it back via pattern `\|\s*(\d+)\s*SP\s*\|`. Each function has thorough unit tests, but no test verifies the full roundtrip. If either format changes (e.g., format_issue_body switches to `SP: 5`), the other would break silently.

**Acceptance Criteria:**
- [ ] A test calls `format_issue_body(story)` for stories with SP values 0, 1, 5, 13, 100
- [ ] For each, calls `extract_sp({"body": body, "labels": []})` and asserts the extracted SP equals the original
- [ ] The test fails if either format changes independently

**Validation Command:**
```bash
python -m pytest tests/ -k "sp_roundtrip" -v 2>&1 | tail -10
```

---

### BH19-009: build_milestone_title_map has NO direct unit tests
**Severity:** MEDIUM
**Category:** `test/missing`
**Location:** `skills/sprint-setup/scripts/populate_issues.py:365-401` (build_milestone_title_map)
**Status:** 🔴 OPEN
**Pattern:** —

**Problem:** `build_milestone_title_map` maps sprint numbers to milestone titles by reading markdown headings. It's critical for issue creation (determines which milestone to assign). It's exercised indirectly by the full pipeline tests, but has no direct tests for: multi-sprint files, fallback to filename, heading vs filename sprint number conflict, duplicate sprint number warning.

**Acceptance Criteria:**
- [ ] A test with a file containing `### Sprint 1:` and `### Sprint 2:` sections returns `{1: "Title", 2: "Title"}`
- [ ] A test with a file named `milestone-3.md` (no sprint sections) falls back to sprint 3
- [ ] A test with conflicting sprint numbers from two files produces a warning

**Validation Command:**
```bash
python -m pytest tests/ -k "milestone_title_map" -v 2>&1 | tail -10
```

---

### BH19-010: _format_story_section doesn't sanitize pipe chars in titles — corrupts markdown tables
**Severity:** MEDIUM
**Category:** `bug/data-corruption`
**Location:** `scripts/manage_epics.py:167-223` (_format_story_section)
**Status:** 🔴 OPEN
**Pattern:** —

**Problem:** `_format_story_section` sanitizes newlines in `sid` and `title` (line 172-173) but does NOT sanitize pipe characters `|`. A story title like "Auth | OAuth flow" would produce `| Auth | OAuth flow |` in the metadata table, corrupting the table structure. `parse_epic` would then parse the corrupted table incorrectly.

**Acceptance Criteria:**
- [ ] Pipe characters in story titles/IDs are escaped or replaced before table insertion
- [ ] A roundtrip test: add_story with title "Auth | OAuth" → parse_epic → verify title matches
- [ ] Table structure is valid after add_story with pipe-containing title

**Validation Command:**
```bash
python -m pytest tests/ -k "pipe_in_title or sanitize_pipe" -v 2>&1 | tail -10
```

---

### BH19-011: gh_json incremental decoder has no outer try/except for truly garbage JSON
**Severity:** MEDIUM
**Category:** `bug/unhandled-exception`
**Location:** `scripts/validate_config.py:93-109` (gh_json slow path)
**Status:** 🔴 OPEN
**Pattern:** —

**Problem:** When `json.loads(raw)` fails (line 88-91), `gh_json` falls through to the incremental `raw_decode` path (lines 93-109). If the raw data is truly garbage (not just concatenated JSON arrays), `decoder.raw_decode(raw, pos)` will raise `json.JSONDecodeError` with no handler. The fast-path JSONDecodeError is caught and falls through, but the slow-path one propagates uncaught.

**Acceptance Criteria:**
- [ ] A test passes garbage data (e.g., `"<html>Not Found</html>"`) through the `gh_json` slow path
- [ ] Verifies it either returns `[]` or raises a clear error (not an unhandled JSONDecodeError with a confusing "Expecting value" message)

**Validation Command:**
```bash
python -c "
import sys; sys.path.insert(0, 'scripts')
from validate_config import gh_json
from unittest.mock import patch
# Simulate gh returning garbage HTML
with patch('validate_config.gh', return_value='<html>Not Found</html>'):
    try:
        result = gh_json(['api', 'test'])
        print(f'Result: {result}')
    except Exception as e:
        print(f'UNHANDLED: {type(e).__name__}: {e}')
"
```

---

### BH19-012: generate_project_toml preservation of existing file is untested
**Severity:** MEDIUM
**Category:** `test/missing`
**Location:** `scripts/sprint_init.py:602-606` (generate_project_toml BH-017 guard)
**Status:** 🔴 OPEN
**Pattern:** PAT-003

**Problem:** `generate_project_toml` has a guard: if `project.toml` already exists, it's preserved (not overwritten). This BH-017 fix is important — user edits to project.toml should survive re-runs of sprint_init. But no test verifies this behavior.

**Acceptance Criteria:**
- [ ] A test runs ConfigGenerator.generate() on a project that already has sprint-config/project.toml
- [ ] Verifies the existing project.toml content is preserved
- [ ] Verifies the skipped list contains "preserved  project.toml"

**Validation Command:**
```bash
python -m pytest tests/ -k "preserve_toml or existing_toml" -v 2>&1 | tail -10
```

---

### BH19-013: get_existing_issues uses --limit 500 — duplicate issues possible on large projects
**Severity:** LOW
**Category:** `design/scalability`
**Location:** `skills/sprint-setup/scripts/populate_issues.py:330-347` (get_existing_issues)
**Status:** 🔴 OPEN
**Pattern:** —

**Problem:** `get_existing_issues()` fetches up to 500 issues to build the dedup set. On projects with >500 issues, the `existing` set is incomplete. `create_issue` would attempt to create stories that already exist beyond position 500. GitHub would reject exact duplicate titles, but the script would report errors and the output would be confusing.

**Acceptance Criteria:**
- [ ] Use `--paginate` with `gh api` endpoint instead of `--limit 500` to fetch all issues
- [ ] OR: Add `--limit` to `1000` with `warn_if_at_limit` (matching `list_milestone_issues`)
- [ ] A test verifies warn_if_at_limit is called on the result

**Validation Command:**
```bash
grep -n 'limit.*500' skills/sprint-setup/scripts/populate_issues.py
```

---

### BH19-014: patch_gh MonitoredMock only used in 6 of ~30 gh_json mock sites
**Severity:** LOW
**Category:** `test/quality`
**Location:** `tests/gh_test_helpers.py` (patch_gh), various test files
**Status:** 🔴 OPEN
**Pattern:** —

**Problem:** The `patch_gh` context manager with `MonitoredMock` was created (BH-P11-201) to detect mock-returns-what-you-assert anti-pattern. But it's only used in 6 test methods in `test_bugfix_regression.py`. The other ~30 `@patch` sites for `gh_json` across `test_sprint_runtime.py`, `test_gh_interactions.py`, and `test_release_gate.py` use raw `unittest.mock.patch` with no call-args verification. The anti-pattern detector exists but has near-zero adoption.

**Acceptance Criteria:**
- [ ] Convert at least the HIGH-traffic mock sites (gate_stories, gate_ci, check_ci, check_prs) to use `patch_gh`
- [ ] OR: Make `patch_gh` warnings into test failures (filterwarnings = error in conftest.py)
- [ ] Document the convention in a test README or conftest comment

**Validation Command:**
```bash
echo "patch_gh usage:"; grep -rn 'patch_gh' tests/ | wc -l
echo "raw @patch gh_json:"; grep -rn '@patch.*gh_json\|patch.object.*gh_json' tests/ | wc -l
```

---

### BH19-015: find_milestone regex is case-sensitive — "sprint 1" wouldn't match
**Severity:** LOW
**Category:** `design/fragility`
**Location:** `scripts/validate_config.py:959` (find_milestone)
**Status:** 🔴 OPEN
**Pattern:** —

**Problem:** `find_milestone` uses `re.match(rf"^Sprint 0*{num}\b", title)` which requires exact capitalization "Sprint". A milestone titled "sprint 1" or "SPRINT 1" would not match. The skeleton templates use "Sprint N" capitalization, so this is unlikely in practice, but a case-insensitive match would be more robust.

**Acceptance Criteria:**
- [ ] Add `re.IGNORECASE` to the find_milestone regex
- [ ] A test verifies "sprint 7" and "SPRINT 7" both match find_milestone(7)

**Validation Command:**
```bash
python -c "
import re
# Current regex (case-sensitive):
assert re.match(r'^Sprint 0*7\b', 'sprint 7') is None, 'Case-sensitive confirmed'
# Fixed regex (case-insensitive):
assert re.match(r'^Sprint 0*7\b', 'sprint 7', re.IGNORECASE), 'Case-insensitive works'
print('PASS')
"
```
