# Cross-Module Data Flow Audit

Traced 5 data flows end-to-end across 9 scripts + FakeGitHub.

---

## Flow 1: Story ID Lifecycle

**Path:** milestone markdown -> `parse_milestone_stories()` -> `create_issue()` -> GitHub title -> `get_existing_issues()` -> `extract_story_id()` -> `sync_tracking.create_from_issue()` -> tracking YAML -> `update_burndown.build_rows()`

### Finding 1 — MEDIUM: Story ID format is consistent but fallback path diverges

The regex `r"([A-Z]+-\d+)"` is used identically in three places:
- `extract_story_id()` at validate_config.py:840
- `get_existing_issues()` at populate_issues.py:306
- `_DEFAULT_ROW_RE` at populate_issues.py:51 (anchored as `US-\d{4}`)

The consistency was fixed by BH-006 (earlier the `get_existing_issues` regex required a colon). However, the fallback path in `extract_story_id()` (lines 843-846) produces a lowercase slug (`re.sub(r"[^a-zA-Z0-9_-]", "-", prefix).strip("-").lower()`), while `get_existing_issues()` has no fallback at all -- it only matches `[A-Z]+-\d+`. This means:

- If someone creates a GitHub issue with title "Setup CI pipeline" (no ID prefix), `extract_story_id` returns slug `"setup-ci-pipeline"`, but `get_existing_issues()` won't detect it. Next sync run, `populate_issues` will try to create a duplicate.
- In practice this only triggers for manually-created issues without standard IDs, but it's a silent data loss path.

### Finding 2 — LOW: Unusual characters in story IDs are handled safely

The regex `[A-Z]+-\d+` constrains the format. Characters like spaces, colons, or Unicode won't appear in the extracted ID. The slug fallback path in `extract_story_id` strips non-alphanumeric characters and truncates to 40 chars. The `_yaml_safe()` function in sync_tracking.py quotes values containing YAML-sensitive characters. Round-tripping is tested.

### Finding 3 — MEDIUM: Custom `story_id_pattern` creates split-brain risk

`populate_issues._build_row_regex()` (line 62) accepts `[backlog] story_id_pattern` from config (e.g., `"PROJ-\\d{4}"`). But `extract_story_id()` in validate_config.py hardcodes `r"([A-Z]+-\d+)"`. If someone configures `story_id_pattern = "TASK-\\d{3}"` (3 digits), `populate_issues` creates issues with "TASK-001: Widget" titles. `extract_story_id` extracts "TASK-001" fine (matches `[A-Z]+-\d+`). But if they use a lowercase pattern like `"task-\\d{3}"`, the regex in `extract_story_id` won't match (requires uppercase `[A-Z]+`), falling back to a slug. Downstream sync and burndown will then use the slug instead of the real ID, breaking linkage.

### Finding 4 — MEDIUM: Story ID to tracking file name has lossy mapping

`create_from_issue()` at sync_tracking.py:288 computes `slug = slug_from_title(issue["title"])` for the filename. `slug_from_title()` strips all non-alphanumeric characters except spaces and hyphens, collapses whitespace, and lowercases. Two different stories like "US-0001: Add Auth" and "US-0001 - Add Auth!" would produce the same slug `"us-0001-add-auth"`, clobbering each other's tracking file. The story ID in the YAML frontmatter would be correct, but the second `write_tf()` call silently overwrites the first file.

---

## Flow 2: Sprint Number Lifecycle

**Path:** milestone file `### Sprint N:` heading -> `_collect_sprint_numbers()` -> `create_sprint_labels()` / `create_milestones_on_github()` -> GitHub milestone title "Sprint N: Name" -> `find_milestone()` regex `^Sprint {num}\b` -> `detect_sprint()` from SPRINT-STATUS.md `Current Sprint: N`

### Finding 5 — LOW: Non-sequential sprint numbers work correctly

All sprint number paths use set/dict storage, not array indexing. `_collect_sprint_numbers()` returns a `set[int]`. `build_milestone_title_map()` returns `dict[int, str]`. `find_milestone()` does a linear scan with regex matching. Sprint numbers 1, 3, 7 would work fine. Gaps cause no issues.

### Finding 6 — HIGH: Leading zeros cause silent data corruption

`int("07")` returns `7` in Python, so `### Sprint 07:` heading is parsed as sprint 7. But `find_milestone()` at validate_config.py:892 uses `re.match(rf"^Sprint {num}\b", title)` where `num = int(sprint_num)` = 7. If the milestone was created with title "Sprint 07: Name" (preserving the original heading text), the regex `^Sprint 7\b` won't match "Sprint 07: Name". The milestone becomes invisible to all downstream consumers.

The specific path: `create_milestones_on_github()` at bootstrap_github.py:256 reads the `# heading` from the file for the milestone title. If the heading is `# Sprint 07: Walking Skeleton`, the GitHub milestone gets title "Sprint 07: Walking Skeleton". Later, `find_milestone(7)` generates regex `^Sprint 7\b` which does NOT match "Sprint 07:...". Result: sync_tracking, update_burndown, check_status, and sprint_analytics all fail to find the milestone.

The `_SPRINT_HEADER_RE` at populate_issues.py:57 captures `(\d+)` which converts "07" to int 7. But `build_milestone_title_map()` maps sprint 7 -> the file's `# heading` title, which might contain "07". The `create_issue()` function then uses this title to look up the milestone number, and that lookup would succeed (exact title match). But the reverse lookup in `find_milestone()` breaks.

### Finding 7 — MEDIUM: detect_sprint requires exact format; writers don't validate

`detect_sprint()` at validate_config.py:826 uses `r"Current Sprint:\s*(\d+)"`. This regex is applied to SPRINT-STATUS.md, which is written by the sprint-run SKILL.md ceremony (not by any script in this audit scope). If the file says "Current Sprint: 03" (with leading zero), `detect_sprint` returns 3, then `find_milestone(3)` looks for `^Sprint 3\b`. This works correctly IF the milestone title doesn't have a leading zero. But there's no validation that the writer and reader agree on format.

### Finding 8 — LOW: Sprint 0 is a valid parsed result but semantically invalid

`_infer_sprint_number()` at populate_issues.py:153 returns `1` as the default when no number is found. But `_most_common_sprint()` returns `0` for empty lists, and `enrich_from_epics()` at line 278 explicitly skips stories with `sprint == 0`. This is correctly handled with a warning message. However, if a milestone file has a heading `### Sprint 0: Prep`, it would be parsed as sprint 0, and issues would get `sprint:0` label and no milestone (since `build_milestone_title_map` would map 0 -> title, but `create_milestones_on_github` would create a milestone titled "Sprint 0: Prep" which find_milestone(0) would match).

---

## Flow 3: Config Path Resolution

**Path:** `project.toml` relative string -> `load_config()` -> `Path(config_dir).resolve().parent` -> absolute path in `config["paths"]`

### Finding 9 — LOW: Spaces in project root are handled correctly

`load_config()` at validate_config.py:651 uses `Path(config_dir).resolve().parent` and `str(project_root / val)` which produce properly quoted paths. All downstream uses go through `Path()` constructors. The `gh()` helper passes args as a list (not shell string), so spaces in paths are preserved correctly by `subprocess.run`.

### Finding 10 — MEDIUM: Symlink resolution changes the project root

`Path(config_dir).resolve()` at line 651 follows symlinks. If `sprint-config` is itself a symlink (e.g., `sprint-config -> /shared/configs/myproject`), then `.resolve().parent` returns `/shared/configs/` instead of the actual project root. All path resolution (`str(project_root / val)`) would be relative to the wrong directory. The config's `[paths]` values like `sprints_dir = "sprints"` would resolve to `/shared/configs/sprints` instead of the project's `sprints/` directory.

This is not hypothetical -- the CLAUDE.md architecture section says "Symlink-based config: sprint_init.py creates symlinks from sprint-config/ to existing project files." If the config_dir itself is symlinked (unlikely but possible), paths break silently.

### Finding 11 — MEDIUM: CWD assumption in non-load_config paths

Several functions use paths without going through the resolved config. `find_milestone()` at validate_config.py:885 uses `gh_json(["api", "repos/{owner}/{repo}/milestones"])` which depends on `gh`'s implicit repo detection (from the current git directory). If a script's CWD changes after `load_config()`, `gh` commands might fail or hit the wrong repo. In practice, none of the audited scripts change CWD, so this is theoretical.

---

## Flow 4: Label Lifecycle

**Path:** `bootstrap_github.create_static_labels()` creates `kanban:todo`, `kanban:dev`, etc. -> `populate_issues.create_issue()` applies `kanban:todo`, `sprint:N`, etc. -> `kanban_from_labels()` reads back -> `sync_tracking` uses them

### Finding 12 — HIGH: SP labels are never created but are expected by extract_sp

`bootstrap_github.create_static_labels()` creates priority, kanban, and type labels. `create_sprint_labels()` creates `sprint:N`. `create_saga_labels()` creates `saga:SNN`. But NOBODY creates `sp:N` labels. The `extract_sp()` function at validate_config.py:790 looks for `sp:N` in labels (case-insensitive). The `populate_issues.create_issue()` function at line 415 does NOT add sp labels -- it only adds sprint, type, kanban, and saga labels. SP information is embedded in the issue body via `format_issue_body()`.

This means `extract_sp()` will only find SP from body text (lines 793-802), never from labels, unless someone manually adds `sp:N` labels on GitHub. The label-check path (line 790) is dead code in the automated flow. If a user manually adds `sp:3` labels, those are "ghost labels" (no color, no description) because `bootstrap_github` never created them.

This isn't a correctness bug (body extraction works), but it's a fidelity gap: the label path exists and is tested, but the production flow never exercises it.

### Finding 13 — LOW: kanban_from_labels is case-sensitive for the kanban: prefix

`kanban_from_labels()` at validate_config.py:868 checks `name.startswith("kanban:")` (case-sensitive). `create_static_labels()` creates labels with lowercase `kanban:todo`, etc. GitHub preserves label case. If someone manually creates a `Kanban:Todo` label, `kanban_from_labels` won't recognize it. This is by design (labels are machine-created), but there's no defensive lowercasing.

### Finding 14 — MEDIUM: Deleted labels cause silent fallback, not errors

If a `kanban:dev` label is deleted from GitHub between creation and reading, `kanban_from_labels()` returns the fallback: `"done"` if the issue is closed, `"todo"` if open. There's no warning that the expected label was missing. A story actively in development (`kanban:dev`) whose label gets accidentally deleted would appear as `todo` in tracking and burndown, potentially triggering re-assignment.

### Finding 15 — LOW: Label filter in issue_list is exact-match only

`_issue_list` in FakeGitHub at line 593 uses `l["name"] == label_filter`, which is exact match. The real `gh issue list --label` does the same. No case-sensitivity issue here since both sides use the exact string.

---

## Flow 5: FakeGitHub Fidelity

### Finding 16 — HIGH: FakeGitHub does not validate label existence on issue create

Real `gh issue create --label nonexistent` auto-creates the label on GitHub (with default gray color). FakeGitHub's `_issue_create()` (line 494) accepts any label string without checking if it exists in `self.labels`. This means:

1. Tests never catch the case where `populate_issues.create_issue()` uses labels that `bootstrap_github` hasn't created yet. In the real flow, `gh` would silently auto-create them. But the timing assumption (bootstrap runs before populate) is never validated.
2. More importantly, the FakeGitHub label store and issue label lists are disconnected. `self.labels` is populated by `label create`, but `_issue_create` just stores raw strings. A test that checks `fake_gh.labels` won't see labels that were implicitly created via `issue create --label`.

### Finding 17 — HIGH: FakeGitHub milestone error message format differs from real API

`bootstrap_github.create_milestones_on_github()` at line 287 checks `"already_exists" in msg` to detect duplicate milestones. FakeGitHub returns `"Validation Failed: milestone title 'X' already exists"` which contains "already_exists" and works. But the real GitHub API returns a structured JSON error: `{"message": "Validation Failed", "errors": [{"code": "already_exists", ...}]}`. The `gh` CLI formats this differently depending on version. The string check happens to work with current `gh` CLI output, but it's fragile and the FakeGitHub test doesn't validate the real format -- it validates a different string that happens to contain the same substring.

### Finding 18 — MEDIUM: FakeGitHub milestones lack created_at field

`check_status.py` at line 401 reads `ms.get("created_at")` from milestone data to determine the "since" date for direct push detection. FakeGitHub's milestone dicts (line 389) don't include `created_at`. Any test exercising check_status will always fall through to the 14-day fallback, never testing the milestone-date path. The code handles this gracefully (it's a fallback), but the milestone-date code path is untested.

### Finding 19 — MEDIUM: FakeGitHub issue close doesn't set closedAt to UTC ISO format

`_issue_close()` at fake_github.py:648 sets `issue["closedAt"] = datetime.now(timezone.utc).isoformat()`. Python's `datetime.isoformat()` produces `"2026-03-16T12:00:00+00:00"` format. The real GitHub API returns `"2026-03-16T12:00:00Z"` (Z suffix, no offset). `parse_iso_date()` in validate_config.py handles both (it does `.replace("Z", "+00:00")`), so this doesn't cause bugs. But the FakeGitHub format diverges from production.

### Finding 20 — MEDIUM: FakeGitHub PR list --state "all" doesn't include merged PRs as distinct state

Real `gh pr list --state all` returns PRs in states: open, closed, merged. FakeGitHub's `_pr_list()` at line 759 filters on `pr.get("state")`. After `_pr_merge()`, a PR has `state = "closed"` and `merged = True`. The `--state all` filter works correctly (no filtering). But `--state merged` would not work because FakeGitHub never sets `state = "merged"` -- it sets `state = "closed"` with `merged = True`. This diverges from real `gh pr list --state merged` which would return merged PRs. No current code uses `--state merged`, so this is latent.

### Finding 21 — LOW: FakeGitHub timeline endpoint returns failure for missing events

`_handle_api()` at fake_github.py:458 returns `self._fail(...)` when `timeline_events` has no entry for an issue number. The real GitHub API returns `200 OK` with an empty array `[]`. This means `get_linked_pr()` in sync_tracking.py catches the RuntimeError (from `gh()` raising on non-zero exit), triggering the branch-name fallback. The behavior is functionally equivalent but the error path is different -- tests exercise the error path, production exercises the empty-array path.

### Finding 22 — MEDIUM: FakeGitHub --search only implements milestone predicate

`_pr_list()` and `_issue_list()` in FakeGitHub support `--search` but only extract the `milestone:"X"` predicate. Any other search predicates (labels, author, created date ranges) are silently ignored with a warning. `sprint_analytics.compute_review_rounds()` at line 87 uses `--search f'milestone:"{milestone_title}"'`, which works. But if future code adds more search predicates, FakeGitHub won't filter them, causing false-passing tests.

### Finding 23 — LOW: FakeGitHub pr create doesn't validate milestone existence

`_pr_create()` at line 778 accepts any `--milestone` value without checking if the milestone exists. Real `gh pr create --milestone "nonexistent"` would fail. Tests using PR creation with milestones don't catch this discrepancy.

---

## Summary Table

| # | Severity | Flow | Finding |
|---|----------|------|---------|
| 1 | MEDIUM | Story ID | Fallback slug path in extract_story_id diverges from get_existing_issues (no fallback), risking duplicates for non-standard titles |
| 2 | LOW | Story ID | Unusual characters handled safely by regex + YAML quoting |
| 3 | MEDIUM | Story ID | Custom story_id_pattern with lowercase IDs breaks extract_story_id linkage |
| 4 | MEDIUM | Story ID | slug_from_title can produce collisions for similar titles, clobbering tracking files |
| 5 | LOW | Sprint # | Non-sequential sprint numbers work correctly (set/dict storage) |
| 6 | HIGH | Sprint # | Leading zeros in sprint headings cause milestone lookup failures across all downstream consumers |
| 7 | MEDIUM | Sprint # | detect_sprint and milestone writers have no shared format validation |
| 8 | LOW | Sprint # | Sprint 0 handled correctly with explicit skip + warning |
| 9 | LOW | Config | Spaces in paths handled correctly via Path and list-based subprocess |
| 10 | MEDIUM | Config | Symlink resolution on config_dir changes project_root to wrong directory |
| 11 | MEDIUM | Config | gh commands depend on CWD for repo detection, not config |
| 12 | HIGH | Labels | SP labels never created by bootstrap; extract_sp label path is dead code in automated flow |
| 13 | LOW | Labels | kanban_from_labels is case-sensitive (by design, labels are machine-created) |
| 14 | MEDIUM | Labels | Deleted labels cause silent fallback to todo/done, no warning |
| 15 | LOW | Labels | Label filtering is exact-match, consistent across real and fake |
| 16 | HIGH | FakeGH | Does not validate label existence on issue create (real gh auto-creates labels) |
| 17 | HIGH | FakeGH | Milestone duplicate error format differs from real API; tested substring happens to match |
| 18 | MEDIUM | FakeGH | Milestones lack created_at field; check_status milestone-date path untested |
| 19 | MEDIUM | FakeGH | closedAt format diverges (Python isoformat vs GitHub Z-suffix) |
| 20 | MEDIUM | FakeGH | PR merge sets state="closed" not "merged"; --state merged would fail |
| 21 | LOW | FakeGH | Timeline returns error for missing events vs real API returns empty array |
| 22 | MEDIUM | FakeGH | --search only supports milestone predicate; other predicates silently ignored |
| 23 | LOW | FakeGH | PR create doesn't validate milestone existence |

**HIGH findings (4):** #6 (leading zeros), #12 (SP labels dead code), #16 (label validation gap), #17 (error format fragility)
**MEDIUM findings (11):** #1, #3, #4, #7, #10, #11, #14, #18, #19, #20, #22
**LOW findings (8):** #2, #5, #8, #9, #13, #15, #21, #23
