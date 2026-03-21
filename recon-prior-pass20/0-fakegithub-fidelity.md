# FakeGitHub Fidelity Audit

Audit of `tests/fake_github.py` against real `gh` CLI behavior.
Existing coverage in `tests/test_fakegithub_fidelity.py` noted where applicable.

---

## 1. Response Format Divergences

### 1A. PR state casing: lowercase vs uppercase

**Real gh**: `gh pr list --json state` returns uppercase values: `"OPEN"`, `"CLOSED"`, `"MERGED"`.

**FakeGitHub**: `_pr_create` sets `"state": "open"` (line 803), `_pr_merge` sets `"state": "closed"` (line 867). All lowercase, no `"MERGED"` state.

**Production code affected**: `sync_tracking.py` line 116 compares `pr["state"]` against string values. `check_status.check_prs()` uses `pr.get("reviewDecision")` not `pr.get("state")` for PR filtering, but the `--state` filter path in `_pr_list` compares `pr.get("state") == state_filter` (line 772) which means `--state open` works because both the filter and the stored state are lowercase. However, if production code ever reads the `state` field from PR JSON output directly, it would see "OPEN" from real gh but "open" from FakeGitHub.

**Risk**: Low for current code (production uses `--state` filter and doesn't compare PR state values directly after fetching). But any new code comparing `pr["state"] == "OPEN"` would fail against FakeGitHub.

**Tests that depend on this quirk**: `test_sprint_analytics.py` lines 195, 229 set `pr["state"] = "closed"` manually, which matches FakeGitHub's lowercase convention but diverges from real gh's `"CLOSED"`.

### 1B. Issue create returns URL, but no newline

**Real gh**: `gh issue create` prints `https://github.com/owner/repo/issues/N\n` to stdout.

**FakeGitHub**: Returns the URL without trailing newline (line 549-550). This is correct because `validate_config.gh()` calls `.strip()` on stdout (line 68), so trailing newline doesn't matter.

**Status**: Correct behavior. No divergence that matters.

### 1C. Milestone API response missing `due_on`, `html_url`, `updated_at` fields

**Real GitHub API**: `/repos/{owner}/{repo}/milestones` returns objects with fields including `number`, `title`, `description`, `state`, `open_issues`, `closed_issues`, `created_at`, `updated_at`, `due_on`, `closed_at`, `html_url`, `url`, `labels_url`, `id`, `node_id`, `creator`.

**FakeGitHub**: Milestone creation (line 389-401) only sets `number`, `title`, `description`, `state`, `open_issues`, `closed_issues`, `created_at`. Missing `due_on`, `html_url`, `updated_at`, `url`, `id`, `node_id`, `creator`, `closed_at` (only set on PATCH close).

**Risk**: Low. Production code only reads `number`, `title`, `state`, `open_issues`, `closed_issues`, `created_at`. No current code reads missing fields.

### 1D. Issue objects missing `url`, `html_url`, `assignees`, `created_at`, `updated_at`

**Real gh**: `gh issue list --json` can return many fields. The issue object structure from `gh` includes `url`, `createdAt`, `updatedAt`, `assignees`, `author`, `comments`, etc.

**FakeGitHub**: Issue objects (line 532-540) contain `number`, `title`, `body`, `state`, `labels`, `milestone`, `closedAt`. No `createdAt`, `url`, `assignees`, `author`.

**Risk**: Low currently. Production code requests specific `--json` fields and FakeGitHub's `_filter_json_fields` returns only those. But tests that inject issues directly into `self.gh.issues` (bypassing `_issue_create`) can set arbitrary fields and would miss this gap.

### 1E. `gh release create` returns URL to stdout, not JSON

**Real gh**: `gh release create` outputs `https://github.com/owner/repo/releases/tag/vX.Y.Z` to stdout.

**FakeGitHub**: Same behavior (line 930-932). Correct.

### 1F. `gh api` milestones path with query string

**Real gh**: `gh api repos/{owner}/{repo}/milestones?per_page=100` works because gh passes the full path+query to the API.

**FakeGitHub**: Uses `if "milestones" in path` (line 404) which matches `milestones?per_page=100` as a substring. Works by accident, not by design. The `?per_page=100` query parameter is silently ignored -- FakeGitHub always returns all milestones regardless.

**Risk**: None currently. But if someone adds a path like `milestones/1/labels` it would incorrectly match the milestones handler.

### 1G. `gh release view` JSON output shape

**Real gh**: `gh release view TAG --json url` returns `{"url": "https://..."}`.

**FakeGitHub**: Returns the same shape (line 898-900), then applies `--jq` if the jq package is available. When production code does `gh(["release", "view", ..., "--json", "url", "--jq", ".url"])`, it expects a plain URL string.

**Status**: Correct when jq package is installed. Falls back to returning the JSON object when jq is unavailable, which would cause production code to get `{"url": "..."}` instead of `"..."`.

---

## 2. Missing Behavior

### 2A. `--label` only matches single label, not comma-separated

**Real gh**: `gh issue list --label "bug,enhancement"` treats the comma-separated string as multiple labels (AND logic).

**FakeGitHub**: `_issue_list` (line 601-604) matches `label_filter` as a single string against each label name. If production code ever passes `--label "bug,enhancement"`, FakeGitHub would look for a label literally named `"bug,enhancement"` and find nothing.

**Production code**: Uses `--label X` with a single label per flag (e.g., `populate_issues.create_issue` uses `args.extend(["--label", label])` for each label). No current production code uses comma-separated labels.

**Risk**: Low currently, but FakeGitHub silently fails on comma-separated labels rather than splitting them.

### 2B. Multiple `--label` flags on `issue list` not supported

**Real gh**: `gh issue list --label bug --label docs` filters to issues with BOTH labels (AND logic).

**FakeGitHub**: `_issue_list` only reads the first `--label` flag value (line 569-571 uses a while loop that overwrites `label_filter` each time). So `--label bug --label docs` would only filter by `docs`.

**Production code**: No production code uses multiple `--label` on `issue list`. But tests do: `test_bugfix_regression.py` line 229 creates an issue with `--label bug --label priority` (which is `issue create`, not `issue list`, so this is OK).

**Risk**: Medium. FakeGitHub's label filter behavior differs from real gh when multiple `--label` flags are used on `issue list`.

### 2C. `--paginate` is a no-op (documented)

**FakeGitHub**: `--paginate` is in `_ACCEPTED_NOOP_FLAGS` (line 179). All data is returned in one response. This is documented in the comment.

**Real gh**: `--paginate` iterates all pages and concatenates results. `gh_json()` in `validate_config.py` handles concatenated arrays from pagination.

**Risk**: None. FakeGitHub returns all data at once, which is equivalent to paginated full results.

### 2D. `issue edit --milestone` does NOT update milestone counters

**FakeGitHub**: `_issue_edit` (line 637-639) changes the issue's milestone field but does NOT update `ms["open_issues"]` or `ms["closed_issues"]` on either the old or new milestone.

By contrast, `_issue_create` (line 544-548) increments `open_issues` and `_issue_close` (line 658-665) decrements `open_issues`/increments `closed_issues`.

**Real gh**: Editing an issue's milestone updates the counters on both the old and new milestones.

**Risk**: Medium. If tests reassign issues between milestones via `issue edit --milestone`, the milestone counters will be stale. Production code uses `list_milestone_issues()` to count, not milestone counters directly, but `check_milestone()` reads `open_issues`/`closed_issues` from the milestone object (check_status.py line 190-191).

### 2E. `gh pr merge` does not update milestone counters or linked issue state

**Real GitHub**: Merging a PR does not automatically close linked issues unless the PR body contains "closes #N" or similar keywords. The milestone counters reflect issue state, not PR state.

**FakeGitHub**: `_pr_merge` (line 853-871) sets the PR state to "closed" and "merged" but does not affect any linked issues or milestone counters.

**Risk**: Low. This matches real GitHub behavior correctly -- PR merge does not auto-close issues in the API. Issue closure is handled separately.

### 2F. `gh issue list --search` only supports `milestone:` predicate

**FakeGitHub**: `_extract_search_milestone()` (line 146-173) only handles the `milestone:"X"` predicate. Other predicates like `is:merged`, `author:bot`, `review:approved` are silently ignored with a warning.

**Production code**: `sprint_analytics.compute_review_rounds()` uses `--search 'milestone:"Sprint 1"'` which is fully supported. No other search predicates are used.

**Status**: Covered by `test_fakegithub_fidelity.py::TestSearchPredicateWarning`. Warning is emitted for unrecognized predicates.

### 2G. `gh run list` has no `--status` filter in some handlers

**FakeGitHub**: `_run_list` does implement `--status` filtering (line 717-720). It compares against `r.get("status")`.

**Real gh**: `--status` accepts values like `completed`, `in_progress`, `queued`, `failure`, `success`.

**Note**: Real gh's `--status` is about workflow run status (queued/in_progress/completed), while `conclusion` is the result (success/failure/etc.). FakeGitHub correctly filters by `status` field, not by `conclusion`.

### 2H. No `gh issue view` or `gh pr view` support

**FakeGitHub**: Neither `issue view` nor `pr view` subcommands are implemented. Any production code using these would get `"issue view not supported"` or `"pr view not supported"`.

**Production code**: No current production code uses `gh issue view` or `gh pr view` directly.

### 2I. No `gh label list` support

**FakeGitHub**: Only `label create` is supported (line 324). `label list` would return `"only label create supported"`.

**Production code**: No current code uses `gh label list`.

---

## 3. State Consistency Issues

### 3A. `issue edit --milestone` does not update milestone counters (detailed above in 2D)

When an issue is moved between milestones via `issue edit --milestone`, neither the old milestone's counters nor the new milestone's counters are updated. The counters only change on `issue create` (increment open) and `issue close` (decrement open, increment closed).

### 3B. Issue/PR numbers are monotonically increasing -- CORRECT

`_next_issue`, `_next_ms`, and `_next_pr` counters start at 1 and increment. Numbers are never reused. This matches real GitHub behavior.

### 3C. Issue numbers and PR numbers use separate counters

**Real GitHub**: Issues and PRs share a single monotonic counter. Issue #1, PR #2, Issue #3, etc.

**FakeGitHub**: Uses separate counters (`_next_issue` and `_next_pr`). So you can have both Issue #1 and PR #1, which is impossible on real GitHub.

**Risk**: Low-medium. Production code doesn't rely on issue/PR number uniqueness across types. But it means FakeGitHub state could contain `issue.number == pr.number`, which would never happen on real GitHub. If timeline events link an issue to a PR by number, the number collision could cause confusion.

### 3D. Milestone counters are correct for create + close lifecycle

**Status**: Covered by `test_fakegithub_fidelity.py::TestMilestoneCounters`. Create increments `open_issues`, close moves from `open_issues` to `closed_issues`.

### 3E. Closing an issue without a milestone: no crash

**FakeGitHub**: `_issue_close` checks if `ms_title` exists before updating counters (line 659-665). An issue without a milestone can be closed without error.

**Status**: Covered by `test_fakegithub_fidelity.py::TestMilestoneCounters::test_no_milestone_no_update`.

### 3F. Labels auto-created on `issue create` but not on `issue edit --add-label`

**FakeGitHub**: `_issue_create` auto-creates labels that don't exist (line 527-531, BH-009). But `_issue_edit` with `--add-label` does NOT auto-create labels (line 627-630 just appends `{"name": label_name}` without checking `self.labels`).

**Real gh**: `gh issue edit --add-label` does not auto-create labels; it fails if the label doesn't exist.

**Risk**: Low. The divergence in `issue create` (auto-create) matches real gh behavior. The `issue edit` behavior is actually correct -- real gh would fail on non-existent labels, and FakeGitHub silently adds them to the issue's label list without adding to `self.labels`. This means `self.labels` may be out of sync with labels actually on issues, but no production code queries `self.labels` after initial bootstrap.

---

## 4. Test Dependencies on FakeGitHub Quirks

### 4A. Tests inject issues directly, bypassing `_issue_create`

Multiple tests (e.g., `test_sprint_analytics.py` lines 47-59, `test_lifecycle.py` lines 351-388, `test_bugfix_regression.py` lines 537-550) populate `self.gh.issues` by direct list assignment or `.append()` rather than calling `fake.handle(["issue", "create", ...])`.

**Impact**: These tests bypass:
- Milestone counter updates (BH-002)
- Label auto-creation (BH-009)
- Milestone existence validation
- Issue number assignment (they set `"number"` manually)

This means tests using direct injection are testing against a richer schema than what `_issue_create` produces, and they skip the validation that real `gh issue create` performs.

**Mitigation**: These tests are testing metric computation, not issue creation. Direct injection is intentional for setup speed. But it means the tests would pass even if `_issue_create` were completely broken.

### 4B. Tests set PR `reviews` directly, bypassing `_pr_review`

**Fixed**: `test_sprint_analytics.py::TestComputeReviewRounds::test_counts_review_events` (BH-006) now uses `gh pr review` to add reviews. This is good.

But `test_release_gate.py` (line 198-200) directly sets `self.fake.prs.append({...})` with an incomplete PR object (no `reviews` key, no `merged`, no `mergedAt`). The PR gate test at line 189-200 adds a PR directly to the list.

### 4C. `compute_review_rounds` depends on FakeGitHub's `--search` `milestone:` support

`sprint_analytics.compute_review_rounds()` uses `--search 'milestone:"Sprint 1"'` on `pr list`. FakeGitHub extracts the milestone from the search string and filters by it. Then production code ALSO filters by milestone (line 96-98 in sprint_analytics.py). This double-filter means the test passes even if FakeGitHub's search filter doesn't work -- the post-fetch filter catches everything.

**Risk**: This means FakeGitHub's `--search milestone:` support is untested in effect. If FakeGitHub didn't implement it, the production code's post-fetch filter would still produce correct results. The test cannot detect whether FakeGitHub's search filter is working.

### 4D. `gate_prs` depends on FakeGitHub defaulting to `--state open`

`release_gate.gate_prs()` (line 175-177) calls `pr list` without `--state`, relying on the default of "open". FakeGitHub correctly defaults to "open" for both `_issue_list` and `_pr_list`. This is correct behavior, not a quirk dependency.

### 4E. `_handle_api` path matching is substring-based

FakeGitHub uses `if "milestones" in path` (line 404), `if "/compare/" in path` (line 409), `if path.endswith("/commits")` (line 425), `if "/timeline" in path` (line 453). This means:

- `repos/{owner}/{repo}/milestones?per_page=100` matches the milestones handler (correct by accident)
- A hypothetical path like `repos/o/r/milestones/1/labels` would also match milestones (incorrect)
- The ordering matters: PATCH check (line 354) comes before create check (line 373) which comes before list (line 404)

Tests pass because production code only uses well-known paths that happen to match correctly.

### 4F. Timeline fallback pre-filters to FIRST PR only

**FakeGitHub**: When jq is unavailable, the timeline handler (line 469-472) returns only the FIRST PR cross-reference event. When jq IS available, it returns all matching events as a list.

**Production code**: `sync_tracking.get_linked_pr()` (line 71-73) handles both dict and list returns: `if isinstance(linked, dict): linked = [linked]`. But the fallback path only finds one PR, while the jq path finds all.

**Risk**: Low. The fallback is documented as a graceful degradation. But tests running without jq would not exercise the multi-PR selection logic in `get_linked_pr`.

---

## 5. Already Covered in test_fakegithub_fidelity.py

- P13-006: jq expression fidelity for timeline events
- P13-019: Search predicate warnings
- BH-002: Milestone counter lifecycle (create/close)

---

## 6. Summary of Highest-Priority Gaps

| # | Gap | Severity | Bug-masking risk |
|---|-----|----------|-----------------|
| 1 | PR state casing (lowercase vs uppercase) | Medium | Would mask any code comparing `pr["state"] == "OPEN"` |
| 2 | `issue edit --milestone` doesn't update counters | Medium | Stale counters after milestone reassignment |
| 3 | Issue/PR share one counter on real GH, separate in FakeGitHub | Low-Medium | Number collision possible in FakeGitHub |
| 4 | Multiple `--label` on `issue list` only uses last | Medium | AND-logic label filtering not tested |
| 5 | Double-filter on `--search milestone:` makes search filter untestable | Low | Search bugs masked by post-fetch filter |
| 6 | Direct issue/PR injection bypasses validation and counter logic | Low | Tests pass with inconsistent state |
| 7 | `_handle_api` substring path matching fragile | Low | Correct by accident for current paths |
