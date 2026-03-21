# Data Flow Trace: Four Critical Paths

Traced 2026-03-16 against commit 992a669 (main).

---

## Flow 1: Story ID Lifecycle

**Path:** milestone .md -> `parse_milestone_stories` -> `create_issue` (title) -> `get_existing_issues` (extract ID from title) -> `sync_tracking` (`extract_story_id` from title) -> tracking file (`story` field) -> `update_burndown` (`extract_story_id` again)

### Step-by-step transformations

1. **Milestone .md table row** (parsed by `_DEFAULT_ROW_RE`, populate_issues.py:50-52)
   - Regex: `\|\s*(US-\d{4})\s*\|...`
   - Captures group 1 as story_id. Assigned to `Story.story_id` at line 141.
   - Format assumption: `US-XXXX` (4 digits, uppercase prefix).

2. **`create_issue`** (populate_issues.py:452)
   - Writes title as `f"{story.story_id}: {story.title}"` -- always uses `: ` separator.

3. **`get_existing_issues`** (populate_issues.py:330-347)
   - Regex: `r"([A-Z]+-\d+)"` at line 344.
   - This matches `US-0001` from `"US-0001: Setup project"`.
   - **Consistent with `extract_story_id`** (validate_config.py:906): same regex `r"([A-Z]+-\d+)"`.

4. **`sync_tracking.main`** (sync_tracking.py:369)
   - Calls `extract_story_id(issue["title"])` -- uses the shared function from validate_config.

5. **`sync_tracking.create_from_issue`** (sync_tracking.py:285)
   - Calls `extract_story_id(issue["title"])` -- same shared function.
   - Stores as `tf.story = sid`.

6. **`update_burndown.build_rows`** (update_burndown.py:158)
   - Calls `extract_story_id(issue["title"])` -- same shared function.
   - Stores as `row["story_id"]`.

7. **`update_burndown.load_tracking_metadata`** (update_burndown.py:135)
   - Reads `story` from frontmatter via `_fm_val(fm, "story")`.
   - Uses `frontmatter_value` (validate_config.py:864-879) -- shared with sync_tracking.

### Findings

**A. Consistent ID extraction across all steps.** All consumers use the same `extract_story_id()` function from validate_config.py (line 900-912), or use the identical regex `r"([A-Z]+-\d+)"` (get_existing_issues). The only difference is `get_existing_issues` does not have the fallback-to-slug path, but that's fine because it only cares about known-format IDs.

**B. Title format variants:**
- `"US-0001: Title"` -- this is what `create_issue` produces. All consumers handle it.
- `"US-0001 - Title"` -- `extract_story_id` would match `US-0001` (the regex is anchored to start with `re.match`). The `-` would be part of the remaining title. Works correctly.
- `"US-0001"` (no separator) -- `extract_story_id` matches `US-0001`. The short_title extraction in `create_from_issue` (line 288-291) and `build_rows` (line 159-162) both use `issue["title"].split(":", 1)` -- if there's no colon, the full title is used. Consistent.

**C. Potential inconsistency: `get_existing_issues` uses `re.match` (line 344) while `extract_story_id` also uses `re.match` (line 906). Both anchor to start-of-string. Consistent.**

**D. No data loss detected in this flow.** The story ID string is preserved exactly through every transformation.

### Test coverage

- `extract_story_id`: 7 unit tests in test_pipeline_scripts.py (TestExtractStoryId), 5 property tests in test_property_parsing.py (TestExtractStoryId). Good coverage.
- `create_from_issue`: 3 unit tests in test_sprint_runtime.py (TestCreateFromIssue). Covers basic, with-PR, and closed-issue cases.
- `get_existing_issues` -> `extract_story_id` consistency: NOT directly tested. No test verifies that `get_existing_issues` and `extract_story_id` produce the same ID for the same title.
- **Full end-to-end flow** (milestone parse -> create issue -> sync_tracking -> burndown): NOT tested as a single path. Individual steps are well-tested.

---

## Flow 2: Story Point Lifecycle

**Path:** milestone .md (SP in table) -> `Story.sp` -> `format_issue_body` (writes SP to body) -> `extract_sp` (reads SP from body/labels) -> `_count_sp` / `build_rows` -> burndown.md

### Step-by-step transformations

1. **Milestone .md table** (parsed by `_DEFAULT_ROW_RE`, populate_issues.py:50-52)
   - Regex group 5 captures the SP column: `\|\s*(\d+)\s*\|`
   - Assigned to `Story.sp = int(row.group(5))` at line 150.

2. **`format_issue_body`** (populate_issues.py:405-442)
   - Writes SP on line 412: `f"**{story.story_id}** — {story.title} | Sprint {story.sprint} | {story.sp} SP | {story.priority}"`
   - The SP appears in the format `| 3 SP |` within a pipe-delimited header line.
   - Note: No dedicated "Story Points: N" line is written. The SP is embedded in the story header.

3. **`extract_sp`** (validate_config.py:781-813) reads it back from the issue body.
   - Check order:
     1. Labels matching `sp:\s*(\d+)` (line 800) -- label path, not used by bootstrap
     2. Body regex `(?:story\s*points?|(?<![a-zA-Z])sp)\s*[:=]\s*(\d+)` (line 803-805) -- needs `:` or `=` after SP
     3. Body table `\|\s*SP\s*\|\s*(\d+)\s*\|` (line 807) -- matches `| SP | 3 |`
     4. Body table `\|\s*Story Points?\s*\|\s*(\d+)\s*\|` (line 809)
     5. Body table `\|\s*(\d+)\s*SP\s*\|` (line 811) -- matches `| 3 SP |`

   The format written by `format_issue_body` is `| 3 SP |`, which is matched by pattern 5 (line 811).

4. **`_count_sp`** (check_status.py:211-218) and **`build_rows`** (update_burndown.py:150-174)
   - Both call `extract_sp(issue)` on the same issue dict.

5. **`compute_velocity`** (sprint_analytics.py:40-75)
   - Also calls `extract_sp(iss)` at line 60.

6. **`write_burndown`** (update_burndown.py:37-73)
   - Sums `r["sp"]` from rows, writes to burndown.md.
   - Division: `round(done_sp / total_sp * 100) if total_sp else 0` (line 48).

### Findings

**A. SP round-trip is correct.** `format_issue_body` writes `| 3 SP |`; `extract_sp` pattern 5 (line 811) reads it back via `\|\s*(\d+)\s*SP\s*\|`. The value is preserved.

**B. Label vs body priority:** Labels win (checked first at line 793-801). This is documented in the docstring (line 785-791). If someone manually adds an `sp:5` label to an issue whose body says `| 3 SP |`, the label value (5) is returned. This is intentional but could surprise users.

**C. SP = 0 handling:**
- `extract_sp` returns 0 when no SP found (line 813).
- `write_burndown` line 48: `round(done_sp / total_sp * 100) if total_sp else 0` -- division by zero is guarded.
- `compute_velocity` line 67: `round(delivered_sp / planned_sp * 100) if planned_sp else 0` -- also guarded.
- `check_milestone` (check_status.py:193): `round(closed / total * 100) if total else 0` -- guarded.
- **All division-by-zero paths are guarded.** SP=0 does not cause crashes.

**D. Detail block format vs table format.** `parse_detail_blocks` (populate_issues.py:245) reads SP from metadata as `int(meta.get("story_points", "0"))`. If the detail block has `| Story Points | 3 |`, this gets parsed into `Story.sp = 3`. Then `format_issue_body` writes it as `| 3 SP |`. On read-back, `extract_sp` finds it via pattern 5. Consistent.

**E. SP is never written as a label by the automated flow.** `create_issue` (populate_issues.py:453) creates labels `[sprint:N, type:story, kanban:todo, saga:SXX, priority:PX]` -- no `sp:N` label. The label path in `extract_sp` exists only for manual use.

### Test coverage

- `extract_sp`: 12 unit tests in test_sprint_runtime.py (TestExtractSP), 4 adversarial tests (TestExtractSPWordBoundary), 8 property tests in test_property_parsing.py (TestExtractSp), 5 regression tests (TestBH011ExtractSpBoundary). Excellent coverage.
- `write_burndown` with SP=0: 1 test (test_sprint_runtime.py:1445). Confirms `Progress: 0%`.
- **Round-trip test** (format_issue_body -> extract_sp): NOT directly tested. No test creates a body via `format_issue_body` and then calls `extract_sp` on it.
- `compute_velocity` with all SP=0: NOT tested (would return `percentage: 0`).

---

## Flow 3: Milestone Title Lifecycle

**Path:** milestone .md heading -> `create_milestones_on_github` (title from heading) -> `find_milestone` (regex match) -> `list_milestone_issues` (title as filter) -> `check_milestone` / `sprint_analytics`

### Step-by-step transformations

1. **Milestone .md heading** (read by `create_milestones_on_github`, bootstrap_github.py:256-258)
   - Regex: `r"^#\s+(.+)"` with `re.MULTILINE`.
   - Calls `.strip()` on the captured group.
   - Fallback if no heading: constructs `f"Sprint {N}"` from content or filename.

2. **GitHub API creates milestone** (bootstrap_github.py:276-277)
   - Passes title as `-f title={title}`.
   - The title is stored on GitHub as-is.

3. **`build_milestone_title_map`** (populate_issues.py:365-401)
   - Same heading regex: `r"^#\s+(.+)"` with `re.MULTILINE`, `.strip()`.
   - Maps sprint number -> title for issue creation.

4. **`find_milestone`** (validate_config.py:943-961)
   - Queries all milestones via API, then regex-matches: `r"^Sprint 0*{num}\b"`.
   - This expects the title to START with "Sprint N" (with optional leading zeros).
   - **Critical assumption:** milestone titles always start with "Sprint N".

5. **`list_milestone_issues`** (validate_config.py:965-982)
   - Passes `milestone_title` as `--milestone` flag to `gh issue list`.
   - `gh` CLI does exact string matching on milestone title.

6. **`check_milestone`** (check_status.py:172-208)
   - Calls `find_milestone(sprint_num)` to get the milestone dict.
   - Then uses `_ms["title"]` in `gh issue list --milestone`.

7. **`compute_velocity` / `compute_review_rounds` / `compute_workload`** (sprint_analytics.py)
   - All receive `milestone_title` as a string parameter.
   - Pass it to `gh issue list --milestone` or `gh pr list --search milestone:"..."`.

### Findings

**A. INCONSISTENCY: `find_milestone` uses a regex, but `list_milestone_issues` uses exact string match.**
- `find_milestone` (line 959): `re.match(rf"^Sprint 0*{num}\b", title)` -- matches "Sprint 07:" when looking for sprint 7.
- `list_milestone_issues` uses `--milestone <title>` which requires exact title match.
- These are actually compatible because `find_milestone` returns the full title string from the API, and that same string is then passed to `list_milestone_issues`. The regex is only used to FIND the right milestone; once found, the exact title is used downstream. **No inconsistency in practice.**

**B. Trailing whitespace in headings.**
- `create_milestones_on_github` does `.strip()` on the heading (line 258).
- `build_milestone_title_map` does `.strip()` on the heading (line 381).
- Both strip trailing whitespace. **Consistent.**

**C. Capitalization sensitivity.**
- `find_milestone` regex `^Sprint 0*{num}\b` is case-SENSITIVE. A title like "sprint 1" or "SPRINT 1" would NOT match.
- `create_milestones_on_github` preserves the heading's case.
- `build_milestone_title_map` preserves the heading's case.
- `list_milestone_issues` uses `--milestone` which is case-sensitive in gh CLI.
- **If the milestone .md heading says "sprint 1" instead of "Sprint 1", `find_milestone` would fail to find it.** This is a latent fragility. In practice, the skeleton template uses "Sprint N" capitalization, so real users are guided toward the right format.

**D. Milestone titles that don't start with "Sprint N" are invisible to `find_milestone`.**
- If a milestone file has heading `# Alpha Release`, `create_milestones_on_github` creates a milestone titled "Alpha Release".
- `find_milestone(1)` looks for `^Sprint 0*1\b` and will not match "Alpha Release".
- All downstream consumers (`sync_tracking.find_milestone_title`, `update_burndown`, `check_milestone`, `sprint_analytics`) would fail to find the milestone.
- **This is a real gap for non-"Sprint N" milestone titles.** However, `build_milestone_title_map` handles this case for issue creation -- it maps sprint numbers to milestone titles by reading the heading directly. Only the runtime query path (`find_milestone`) has this limitation.

**E. The heading regex `r"^#\s+(.+)"` matches the FIRST `#`-level heading.**
- If a milestone file has multiple `#` headings, only the first is used.
- `re.search` with `re.MULTILINE` finds the first match. Correct behavior.

### Test coverage

- `find_milestone`: Tested indirectly via integration tests that mock `gh_json`. The leading-zero handling is tested in test_bugfix_regression.py (BH-001).
- `build_milestone_title_map`: NO direct unit tests.
- `create_milestones_on_github`: Tested via integration tests in test_hexwise_setup.py and test_golden_run.py.
- **Title consistency across create/find/list**: NOT directly tested as a flow. No test verifies that a title created by `create_milestones_on_github` is correctly found by `find_milestone` and correctly filters in `list_milestone_issues`.

---

## Flow 4: Kanban State Lifecycle

**Path:** `create_issue` sets `kanban:todo` label -> issue edit adds/removes kanban labels -> `kanban_from_labels` reads labels -> `sync_tracking` writes status -> `update_burndown` reads status

### Step-by-step transformations

1. **`create_issue`** (populate_issues.py:453)
   - Sets labels: `["sprint:{N}", "type:story", "kanban:todo"]`.
   - Every new issue starts as `kanban:todo`.

2. **Manual/automated label changes on GitHub**
   - During sprint execution, labels are changed (e.g., `kanban:dev`, `kanban:review`).
   - Old kanban labels may or may not be removed (this is where multiple-label issues arise).

3. **`kanban_from_labels`** (validate_config.py:922-939)
   - Sets `fallback = "done" if issue.get("state") == "closed" else "todo"` (line 929).
   - Iterates all labels looking for `kanban:*` prefixed labels.
   - BH-016: Returns the MOST ADVANCED state when multiple kanban labels exist (line 936-938).
   - Invalid labels (e.g., `kanban:blocked`) are silently ignored.
   - Returns fallback only when NO valid kanban labels are found.

4. **`sync_tracking.sync_one`** (sync_tracking.py:234-278)
   - Line 239: `gh_status = kanban_from_labels(issue)`
   - Line 241-250: **Closed-issue override:**
     ```
     if issue["state"] == "closed" and tf.status != "done":
         tf.status = "done"
     elif gh_status != tf.status and gh_status in KANBAN_STATES:
         tf.status = gh_status
     ```
   - The `closed` state check takes priority over kanban labels.

5. **`sync_tracking.create_from_issue`** (sync_tracking.py:282-315)
   - Line 287: `status = kanban_from_labels(issue)` -- uses the label-derived status.
   - Line 313: `if tf.status == "done": tf.completed = ...`

6. **`update_burndown.build_rows`** (update_burndown.py:150-174)
   - Line 169: `"status": kanban_from_labels(issue)` -- directly from labels.

### Findings

**A. BUG: `create_from_issue` does NOT override kanban labels for closed issues.**
- In `sync_one` (line 241), closed issues are forced to "done" regardless of kanban labels.
- But in `create_from_issue` (line 287), the status comes from `kanban_from_labels(issue)`.
- If a closed issue has `kanban:dev` label, `kanban_from_labels` returns "dev" (it found a valid label, so the "done" fallback is not used).
- `create_from_issue` would create a tracking file with `status=dev` for a closed issue.
- The `completed` date would NOT be set (line 313: `if tf.status == "done"` fails).
- **Impact:** A tracking file for a closed issue could show `status=dev` instead of `status=done`, and have no `completed` date. This would only happen if the issue was closed without removing the old kanban label.
- **Severity:** Low in practice -- `sync_one` would correct this on the next sync run (the `if issue["state"] == "closed"` check catches it). But the first-time creation would be wrong.

**B. BUG: `update_burndown.build_rows` does NOT override kanban labels for closed issues.**
- Line 169: `"status": kanban_from_labels(issue)` -- same issue as above.
- A closed issue with `kanban:dev` label would appear as "dev" in the burndown, not "done".
- The burndown summary counts `r["status"] == "done"` (line 46) -- this issue would NOT be counted as done.
- **Impact:** Burndown progress would be understated for closed issues with stale kanban labels.
- **Severity:** Medium -- the burndown is a primary visibility artifact.

**C. No kanban label (open issue):**
- `kanban_from_labels` returns "todo" (fallback for open issues). Correct behavior.
- All consumers handle this correctly.

**D. No kanban label (closed issue):**
- `kanban_from_labels` returns "done" (fallback for closed issues). Correct behavior.
- `sync_one` also catches this via the `issue["state"] == "closed"` check.
- `create_from_issue` would correctly set `status=done` (since `kanban_from_labels` returns "done").
- `build_rows` would correctly show "done" (since `kanban_from_labels` returns "done").
- **This case works correctly** because the fallback path triggers.

**E. Two kanban labels (e.g., `kanban:dev` AND `kanban:review`):**
- `kanban_from_labels` returns the most advanced state per BH-016.
- `_KANBAN_ORDER = ("todo", "design", "dev", "review", "integration", "done")` (line 919).
- "review" (index 3) > "dev" (index 2), so "review" is returned.
- This is tested in test_bugfix_regression.py (TestBH016KanbanMultipleLabels).
- **Consistent across all consumers** since they all call the same function.

**F. `kanban_from_labels` does NOT check `issue["state"] == "closed"` for override.**
- It only uses `state` for the FALLBACK (when no kanban labels found).
- If labels ARE present, it returns the label-derived state regardless of closed status.
- This means the caller must independently check closed status if they want "done" to override.
- `sync_one` does this (line 241). `create_from_issue` and `build_rows` do NOT.

### Test coverage

- `kanban_from_labels`: 9 unit tests across test_pipeline_scripts.py (TestKanbanFromLabels), test_sprint_runtime.py (TestKanbanFromLabels), test_bugfix_regression.py (TestBH016KanbanMultipleLabels). Good coverage of valid states, invalid states, multiple labels, and open/closed fallbacks.
- `sync_one`: 6 unit tests (TestSyncOne) + 1 GitHub-authoritative test (TestSyncOneGitHubAuthoritative). Tests closed-issue override.
- `create_from_issue`: 3 unit tests (TestCreateFromIssue). Tests basic, with-PR, and closed-issue cases.
- **Missing test: closed issue WITH a non-done kanban label in `create_from_issue`.** The existing `test_creation_for_closed_issue` uses `labels: []`, so the fallback path produces "done". A test with `labels: [{"name": "kanban:dev"}]` and `state: "closed"` would reveal the bug described in finding A.
- **Missing test: closed issue with kanban label in `build_rows`.** Same gap as above.

---

## Summary of Issues Found

| # | Flow | Severity | Description |
|---|------|----------|-------------|
| 1 | Kanban (4A) | Low | `create_from_issue` does not force "done" for closed issues with stale kanban labels. First-time tracking file creation would have wrong status; corrected on next sync. |
| 2 | Kanban (4B) | Medium | `build_rows` (burndown) does not force "done" for closed issues with stale kanban labels. Burndown progress could be understated. |
| 3 | Milestone (3D) | Medium | `find_milestone` only matches titles starting with "Sprint N". Non-standard milestone titles (e.g., "Alpha Release") are invisible to all runtime query paths. |
| 4 | Milestone (3C) | Low | `find_milestone` is case-sensitive. A milestone titled "sprint 1" would not be found. Mitigated by skeleton templates guiding correct capitalization. |

## Summary of Test Gaps

| # | Flow | Gap |
|---|------|-----|
| 1 | Story ID (1) | No test verifies `get_existing_issues` and `extract_story_id` produce the same ID for the same title. |
| 2 | Story ID (1) | No end-to-end test from milestone parse -> issue creation -> sync_tracking -> burndown. |
| 3 | SP (2) | No round-trip test: `format_issue_body` -> `extract_sp`. |
| 4 | SP (2) | No test for `compute_velocity` when all issues have SP=0. |
| 5 | Milestone (3) | No direct unit tests for `build_milestone_title_map`. |
| 6 | Milestone (3) | No test verifying title consistency across create_milestones_on_github -> find_milestone -> list_milestone_issues. |
| 7 | Kanban (4) | No test for `create_from_issue` with a closed issue that has a non-done kanban label. |
| 8 | Kanban (4) | No test for `build_rows` with a closed issue that has a non-done kanban label. |
