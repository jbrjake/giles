# Code Audit — Pass 10 (Raw Findings)

Auditor: Claude Opus 4.6, 2026-03-15
Scope: All 19 production scripts

---

## HIGH Severity

### H-01: `--paginate` with `--jq` produces concatenated JSON arrays — `json.loads` fails on multi-page responses

**Location:** `skills/sprint-setup/scripts/populate_issues.py:281-284`

**Description:** `get_milestone_numbers()` calls `gh api ... --paginate` without `--jq`, then does `json.loads(raw)`. When there are multiple pages, `gh --paginate` concatenates raw JSON arrays: `[...][...]` — this is not valid JSON and `json.loads()` will raise `JSONDecodeError` on multi-page responses.

**Evidence:**
```python
raw = gh(["api", "repos/{owner}/{repo}/milestones?per_page=100",
          "--paginate"], timeout=120)
milestones = json.loads(raw) if raw else []
```

**Trigger:** Any repo with more than 100 milestones, or when GitHub returns paginated responses even under 100 due to server-side decisions.

**Note:** This same concatenated-array bug also affects every `gh_json()` caller that uses `--paginate` without `--jq`, including:
- `validate_config.py:783-786` (`find_milestone`)
- `check_status.py:173-175` (`check_milestone`)
- `check_status.py:384-386` (milestone lookup for `since` date)
- `release_gate.py:408-410` (`find_milestone_number`)

The `gh_json()` wrapper at `validate_config.py:72-80` does not handle concatenated JSON arrays either. When `--paginate` produces `[...][...]`, `json.loads()` will only parse the first array and fail or silently drop the rest depending on the exact output format.

**Severity rationale:** Corrupts data silently or crashes. Any repo that crosses the pagination boundary will hit this.

---

### H-02: `get_linked_pr` timeline API with `--paginate` + `--jq` produces concatenated JSON arrays

**Location:** `skills/sprint-run/scripts/sync_tracking.py:62-68`

**Description:** Uses `--paginate` with `--jq` which produces concatenated JSON arrays on multi-page responses. The `json.loads(raw)` call will fail or produce incorrect data.

**Evidence:**
```python
raw = gh([
    "api",
    f"repos/{{owner}}/{{repo}}/issues/{issue_num}/timeline",
    "--paginate", "--jq",
    '[.[] | select(.source?.issue?.pull_request?) '
    '| .source.issue]',
])
if raw and raw != "null":
    linked = json.loads(raw)
```

**Trigger:** Issues with extensive timelines that span multiple API pages.

---

### H-03: `release_gate.do_release` references `_rollback_tag` and `_rollback_commit` from outer scope after dry-run branch

**Location:** `skills/sprint-release/scripts/release_gate.py:536-579`

**Description:** `_rollback_tag()` and `_rollback_commit()` are defined inside the `else` (non-dry-run) branch. But `_rollback_tag()` is called at line 578 in code that executes AFTER the if/else block, during the GitHub Release creation step. If that step is reached in non-dry-run mode, the function exists. But `_rollback_commit()` at line 579 is also in scope. The real bug: if the GitHub Release creation fails, `_rollback_tag()` is called but was defined inside the `else` block — it IS accessible because Python closures work at function scope, not block scope. However, if for any reason the `else` block was skipped (it wouldn't be because `dry_run` is False at that point), these would be `NameError`.

Actually wait — re-reading: the `_rollback_tag` and `_rollback_commit` calls at lines 578-579 are inside the `else` branch's `try` block (the non-dry-run path), so they ARE in scope. Let me re-examine...

The `try/finally` at line 562 is inside the `else` block. The `_rollback_tag()` call at 578 is inside that try block. So this is actually fine. Withdrawing this finding.

---

### H-03 (revised): `_format_story_section` shadows outer `sp` variable with loop variable

**Location:** `scripts/manage_epics.py:171,218`

**Description:** Variable `sp` is used for story points at line 171, then reused as a loop variable inside the tasks block at line 218 (`sp = task.get("sp", 1)`). This shadows the outer `sp` and if the tasks block runs before any code that uses `sp` for story points after it, the value is corrupted.

**Evidence:**
```python
sp = story_data.get("story_points", 0)  # line 171
# ...
lines.append(f"| Story Points | {sp} |")  # line 178 — uses correct sp
# ...
for task in story_data["tasks"]:
    tid = task.get("id", "T-XXXX-01")
    desc = task.get("description", "")
    sp = task.get("sp", 1)  # line 218 — shadows outer sp
    lines.append(f"- [ ] `{tid}`: {desc} ({sp} SP)")
```

**Trigger:** Currently harmless because `sp` for story points is used at line 178 before the tasks loop. But any future refactoring that uses `sp` after the tasks loop would get a wrong value. This is a latent bug / code smell rather than an active crash.

**Revised severity:** LOW — no active bug, but the shadowing is a maintenance hazard.

---

### H-03 (actual): `check_sync` never transitions from `debouncing` to `sync` when pending matches current

**Location:** `scripts/sync_backlog.py:128-152`

**Description:** The `check_sync` function has a logic path where stabilized files correctly trigger sync, but the state machine has an edge: if `current_hashes != stored` AND `current_hashes == pending`, it falls through the `if current_hashes != stored` block without entering either sub-branch (since `pending is not None` and `current_hashes == pending`). Then it reaches line 149 which checks throttle and returns sync.

Actually, let me re-trace:
- `current_hashes != stored` is True
- `pending is not None` is True (from the first detection)
- `current_hashes != pending` is False (they match now)
- So neither sub-branch of the `if current_hashes != stored` block executes
- Falls through to line 149: `_is_throttled` check
- If not throttled, returns `sync`

This is actually correct — the debounce has stabilized. No bug here.

---

### H-03 (actual): `_parse_value` strips inline comments before checking for closing quote, corrupting strings containing `#`

**Location:** `scripts/validate_config.py:228-230`

**Description:** `_parse_value` calls `_strip_inline_comment(raw).strip()` at the very start. But `_strip_inline_comment` is quote-aware, so this is actually safe for strings with `#` inside quotes. No bug here either.

Let me re-examine more carefully...

---

### H-03 (actual): `_split_array` does not handle nested arrays

**Location:** `scripts/validate_config.py:270-304`

**Description:** The TOML parser's `_split_array` splits on commas but does not track bracket nesting depth. If a TOML array contains nested arrays like `key = [[1, 2], [3, 4]]`, the comma between `2` and `[3` would incorrectly split at the inner boundary.

**Evidence:**
```python
elif ch == "," and not in_str:
    parts.append(current)
    current = ""
```

No bracket-depth tracking exists.

**Trigger:** `key = [["a", "b"], ["c", "d"]]` — will be split as `["a"`, `"b"]`, `["c"`, `"d"]` rather than `["a", "b"]`, `["c", "d"]`.

**Severity rationale:** The project.toml format currently does not use nested arrays, so this is latent. But the parser claims to handle "arrays" generically, and any user who adds nested arrays will get silent data corruption.

---

### H-04: `sprint_analytics.compute_review_rounds` uses `--search` flag that does not filter by milestone server-side

**Location:** `scripts/sprint_analytics.py:83-88`

**Description:** The `gh pr list --search "milestone:TITLE"` syntax passes the milestone filter as a GitHub search query. But the `milestone:` search qualifier uses the milestone's exact title, which may contain spaces and special characters. The `--search` flag is then combined with the `--state all` flag. However, the real issue is that `gh pr list --search` performs a GitHub Issues search, not a PR-specific milestone filter. The results are then further filtered at line 97 by checking `ms.get("title") == milestone_title`, so the search is just an optimization hint. If the search returns no results (e.g., milestone title has special characters), the function returns empty data rather than crashing — so it degrades gracefully. Still, milestone titles with spaces like `"Sprint 1: Walking Skeleton"` will cause the `milestone:` search qualifier to only match on `Sprint`, potentially returning PRs from other milestones.

**Evidence:**
```python
prs = gh_json([
    "pr", "list", "--state", "all",
    "--json", "number,title,labels,milestone,reviews",
    "--limit", "500",
    "--search", f"milestone:{milestone_title}",
])
```

**Trigger:** Milestone title `"Sprint 1: Walking Skeleton"` — the search becomes `milestone:Sprint 1: Walking Skeleton` which GitHub interprets as `milestone:Sprint` plus free-text `1: Walking Skeleton`.

**Severity rationale:** Results in wrong or incomplete data for analytics, but does not crash. Graceful degradation via the secondary filter at line 97 limits the damage.

---

### H-05: `update_sprint_status` regex replacement pattern is fragile — can match and destroy non-table content

**Location:** `skills/sprint-run/scripts/update_burndown.py:106-108`

**Description:** The regex `r"## Active Stories[^\n]*\n(?:\s*\n)*(?:\|[^\n]*\n)*"` matches the section header followed by optional blank lines and table rows. But `(?:\|[^\n]*\n)*` will match zero rows (the `*` quantifier), so the replacement can fire even if there are no table rows, replacing the header itself with the new table. More critically, the pattern stops at the first non-pipe-prefixed line, but if content between "## Active Stories" and the table (like a paragraph description) starts without `|`, the table rows after it won't be captured and will remain as orphaned content.

**Evidence:**
```python
pattern = r"## Active Stories[^\n]*\n(?:\s*\n)*(?:\|[^\n]*\n)*"
if re.search(pattern, text):
    text = re.sub(pattern, new_table.rstrip() + "\n", text)
```

**Trigger:** A SPRINT-STATUS.md where the "## Active Stories" section has a descriptive paragraph before the table. The paragraph survives, and the old table rows after it also survive, resulting in duplicate tables.

---

## MEDIUM Severity

### M-01: `list_milestone_issues` uses `gh issue list` (not `gh_json`) and manually calls `json.loads`

**Location:** `scripts/validate_config.py:796-804`

**Description:** `list_milestone_issues` calls `gh()` (which returns a string) and then manually parses JSON. If the output is not valid JSON (e.g., gh returns an error message on stderr but exits 0), this will crash with `json.JSONDecodeError` without a try/except.

**Evidence:**
```python
raw = gh([
    "issue", "list", "--milestone", milestone_title, "--state", "all",
    "--json", "number,title,state,labels,closedAt,body", "--limit", "500",
])
issues = json.loads(raw) if raw else []
```

The `gh()` function raises `RuntimeError` on non-zero exit, but if `gh` exits 0 with non-JSON output (unlikely but possible with gh CLI bugs), `json.loads` will raise an unhandled exception.

**Severity:** MEDIUM — defensive code should wrap this in try/except like `get_existing_issues` does.

---

### M-02: `extract_sp` body regex matches `\bsp` which can match words ending in `sp` like `clasp`

**Location:** `scripts/validate_config.py:698-700`

**Description:** The pattern `r"(?:story\s*points?|\bsp)\s*[:=]\s*(\d+)"` uses `\bsp` which matches at a word boundary before `sp`. This means text like `"clasp: 5"` would NOT match (no word boundary before `sp` in `clasp`). But `"BSP: 5"` (case insensitive) WOULD match since there's a word boundary before `BSP`. The `re.IGNORECASE` flag means any occurrence of `sp:` or `sp=` preceded by a word boundary will match, which could produce false positives in issue bodies discussing things like "BSP tree", "ISP = 3", etc.

**Evidence:**
```python
if m := re.search(
    r"(?:story\s*points?|\bsp)\s*[:=]\s*(\d+)", body, re.IGNORECASE
):
    return int(m.group(1))
```

**Trigger:** Issue body containing `"ISP = 3"` or `"BSP: 5"` — would extract 3 or 5 as story points.

---

### M-03: `check_test_coverage` slug matching is too aggressive — short slugs cause false positives

**Location:** `scripts/test_coverage.py:121-129`

**Description:** The fuzzy matching normalizes test case IDs and checks if they appear as substrings in implemented test function names. Then it also checks just the "slug portion" after the first underscore. For a test case like `TC-A-1`, the normalized form is `tc_a_1` and the slug is `a_1`. Any test function containing `a_1` anywhere in its name (like `test_data_1_validation`) would match.

**Evidence:**
```python
normalized = tc_id.lower().replace("-", "_")
parts = normalized.split("_", 1)
slug = parts[1] if len(parts) > 1 else normalized
for impl_name in impl_lower:
    if normalized in impl_name or slug in impl_name:
        matched.add(tc_id)
        break
```

**Trigger:** Test case `TC-A-1` with slug `a_1` matches `test_data_1_helper` — false positive.

---

### M-04: `_parse_workflow_runs` multiline detection breaks on indented comments or non-step YAML

**Location:** `scripts/sprint_init.py:221`

**Description:** The multiline run block collector continues as long as lines start with two spaces or are blank. But it also checks `if re.match(r'^\s*- ', lines[i]):` to break on new YAML steps. The problem: YAML comments inside a multiline run block (e.g., `  # this is a comment`) start with two spaces and don't match the break condition, so they're included as commands. Also, YAML keys inside the block that aren't shell commands (like `  timeout: 10`) would be captured.

**Evidence:**
```python
while i < len(lines) and (lines[i].startswith("  ") or lines[i].strip() == ""):
    if re.match(r'^\s*- ', lines[i]):
        break
    line_content = lines[i].strip()
    if line_content:
        multiline_cmds.append(line_content)
    i += 1
```

**Trigger:** A workflow YAML with a multiline `run: |` block that contains comments. The comments will be treated as commands and added to the CI command list.

---

### M-05: `manage_sagas.update_team_voices` inserts spurious `>` separator line for the first voice

**Location:** `scripts/manage_sagas.py:250-252`

**Description:** The loop checks `if new_section[-1] != ""` before appending a `>` separator. On the first iteration, `new_section[-1]` is `""` (the empty line added at line 248), so the `>` is NOT added for the first voice. This is correct. But for subsequent voices, a bare `>` line is added between entries. In markdown, `>` on its own line creates an empty blockquote which is rendered as a blank line inside the blockquote — this might look odd but is not technically wrong.

Actually, this is working as intended — the `>` creates visual separation between blockquotes. Withdrawing.

---

### M-05 (revised): `manage_sagas._find_section_ranges` does not handle `### ` subsections — subsection headers are treated as section content

**Location:** `scripts/manage_sagas.py:126-142`

**Description:** `_find_section_ranges` only looks for `## ` headers (line.startswith("## ")). If a section contains `### ` subsections, those are ignored and treated as part of the parent section's content. This is probably intentional, but the `update_sprint_allocation` and `update_epic_index` functions replace entire section ranges (from `## Section` to the next `## Section`), which means any subsections within the replaced range are silently deleted.

**Evidence:**
```python
for i, line in enumerate(lines):
    if line.startswith("## "):
        if current_section:
            ranges[current_section] = (current_start, i)
```

**Trigger:** A saga file where the `## Sprint Allocation` section has a `### Notes` subsection — calling `update_sprint_allocation` will delete the subsection.

---

### M-06: `bootstrap_github.create_milestones_on_github` uses variable `text` before it's guaranteed to be defined

**Location:** `skills/sprint-setup/scripts/bootstrap_github.py:242`

**Description:** If `title is None` after parsing, the fallback code at line 242 references `text` in the expression `text if mf.is_file() else ""`. But `text` is only assigned at line 229 inside `if mf.is_file():`. If `mf.is_file()` returned False at line 228, then `title` would be `None` (since `heading` search wouldn't run), and the fallback at line 242 would check `mf.is_file()` again — which would be False, so `text` is not accessed. So this is technically safe due to the conditional, but it's fragile — a refactor that changes the file-existence check could cause `UnboundLocalError`.

**Evidence:**
```python
if mf.is_file():
    text = mf.read_text(encoding="utf-8")
    # ...
if title is None:
    sprint_m = re.search(r"Sprint\s+(\d+)", text if mf.is_file() else "")
```

**Trigger:** Currently unreachable due to the double `mf.is_file()` guard, but a maintenance hazard.

---

### M-07: `populate_issues.build_milestone_title_map` calls `_infer_sprint_number(mf)` without `content` argument, causing unnecessary file re-read

**Location:** `skills/sprint-setup/scripts/populate_issues.py:316-317`

**Description:** When no sprint sections are found in a milestone file, the code calls `_infer_sprint_number(mf)` without passing the `content` that was already read at line 305. This causes the file to be read a second time inside `_infer_sprint_number`. This is a performance issue, not a correctness bug. However, there's a TOCTOU window: the file could change between the two reads, causing inconsistent behavior.

**Evidence:**
```python
text = mf.read_text(encoding="utf-8")
# ...
sprint_nums = re.findall(r"### Sprint (\d+):", text)
if sprint_nums:
    # ...
else:
    num = _infer_sprint_number(mf)  # reads file again
```

---

### M-08: `release_gate.gate_tests` uses `shell=True` with user-configured commands — documented but still a risk

**Location:** `skills/sprint-release/scripts/release_gate.py:205-207`

**Description:** `gate_tests` runs each command from `config["ci"]["check_commands"]` with `shell=True`. The comment acknowledges this is intentional. However, `project.toml` is a local config file that could be modified by a malicious contributor. If the repo is a fork and the PR modifies `sprint-config/project.toml` to add `check_commands = ["rm -rf /"]`, the release gate would execute it.

**Evidence:**
```python
r = subprocess.run(
    cmd, shell=True, capture_output=True, text=True, timeout=300,
)
```

**Severity:** MEDIUM — the threat model assumes trust of `project.toml` authors, but this should be documented as a security boundary.

---

### M-09: `sync_tracking.get_linked_pr` timeline API `--jq` wraps results in array, but multi-page responses produce `[...][...]`

**Location:** `skills/sprint-run/scripts/sync_tracking.py:62-68`

**Description:** (Same as H-02 but clarified.) The `--jq` filter wraps selected items in `[...]`. With `--paginate`, each page produces its own `[...]` wrapper, resulting in concatenated arrays like `[{...}][{...}]`. `json.loads()` will parse only the first array or fail entirely.

This was already captured as H-02. Noting here for completeness in the MEDIUM section as it affects data correctness.

---

### M-10: `check_status.check_prs` uses `statusCheckRollup` which may be `None` or contain items without `status`/`conclusion` fields

**Location:** `skills/sprint-monitor/scripts/check_status.py:109-114`

**Description:** The `ci_ok` calculation uses `all()` on the check rollup, filtering for `status == "COMPLETED"`. If ALL checks are still pending (none have `status == "COMPLETED"`), `all()` returns `True` (vacuously true on empty iterator), meaning `ci_ok` would be `True` even when no checks have actually passed.

**Evidence:**
```python
checks = pr.get("statusCheckRollup") or []
ci_ok = all(
    c.get("conclusion") == "SUCCESS"
    for c in checks
    if c.get("status") == "COMPLETED"
)
```

**Trigger:** A PR with all status checks still queued/in-progress. `ci_ok` will be `True`, and the PR will be reported as "CI green, ready to merge" when no checks have actually completed.

---

### M-11: `_parse_value` with empty `raw` input — `_strip_inline_comment` processes empty string harmlessly, but `int("")` would fail

**Location:** `scripts/validate_config.py:228-267`

**Description:** If `_parse_value("")` is called (e.g., from a malformed TOML line like `key = `), after `_strip_inline_comment("").strip()` produces `""`, none of the early returns match (not "true", not "false", no quotes, not "["), so `int("")` is attempted and raises `ValueError`, which is caught. Then the fallback returns `""`. This path works correctly. Not a bug.

---

### M-12: `sprint_analytics.compute_review_rounds` can fail with `max()` on empty sequence

**Location:** `scripts/sprint_analytics.py:119`

**Description:** The code checks `if not sprint_prs: return ...` at line 100, but `rounds_per_pr` is built from `sprint_prs`. If every PR in `sprint_prs` has zero reviews (no CHANGES_REQUESTED or APPROVED), `rounds_per_pr` will be a list of `(title, 0)` tuples. The `max()` call will succeed (it finds the max of 0s). No bug here.

Wait — actually, `rounds_per_pr` is always the same length as `sprint_prs` since it's populated in a loop over `sprint_prs`. Since `sprint_prs` is non-empty at this point (we already returned if empty), `rounds_per_pr` is non-empty. The `max()` is safe. Not a bug.

---

### M-12 (revised): `enrich_from_epics` infers sprint number using mode of known sprints — ties broken arbitrarily

**Location:** `skills/sprint-setup/scripts/populate_issues.py:232`

**Description:** When enriching stories from epic files, the sprint number is inferred by finding the most common sprint number among stories already known from milestone files. `max(set(known_sprints), key=known_sprints.count)` picks the mode, but if there's a tie (e.g., 2 stories from sprint 1 and 2 from sprint 2), `max()` returns the largest value. This could assign new stories to the wrong sprint.

**Evidence:**
```python
sprint = max(set(known_sprints), key=known_sprints.count) if known_sprints else 0
```

**Trigger:** An epic file containing stories from multiple sprints in equal numbers. The sprint with the highest number wins the tie, which may not be the intended assignment.

---

### M-13: `reorder_stories` adds separator before first story even when header ends with content

**Location:** `scripts/manage_epics.py:326-334`

**Description:** In `reorder_stories`, the reassembly loop at line 330 checks `if i > 0 or new_lines:` — this is always true since `new_lines` is initialized from `header` (which is non-empty for any valid file). So every story, including the first, gets a separator (`---`) prepended. This means the first story will have `\n---\n` between the header and itself, which may differ from the original formatting.

**Evidence:**
```python
new_lines = list(header)
for i, sid in enumerate(story_ids):
    if sid not in section_map:
        continue
    if i > 0 or new_lines:  # always True since header is non-empty
        new_lines.append("")
        new_lines.append("---")
        new_lines.append("")
    new_lines.extend(section_map[sid])
```

**Trigger:** Any call to `reorder_stories` — the first story always gets a `---` separator even if the original file didn't have one before it.

---

### M-14: `validate_anchors._MD_ANCHOR_RE` requires exactly `<!-- §ns.sym -->` but anchor names with hyphens won't match

**Location:** `scripts/validate_anchors.py:78`

**Description:** `_MD_ANCHOR_RE = re.compile(r"^<!-- §([\w-]+\.[\w_]+) -->$")` — The namespace part `[\w-]+` allows hyphens (for skill names like `sprint-run`), but the symbol part `[\w_]+` does not allow hyphens. If a markdown anchor uses a hyphenated symbol like `<!-- §sprint-run.mid-sprint-check -->`, the regex won't match and the anchor won't be found.

Meanwhile, `_REF_RE` at line 94 uses `[\w_]+` for the symbol part too, so references with hyphens in the symbol also won't be found. This means the system is consistent (both defs and refs use the same limitation), but it prevents using hyphens in symbol names.

**Evidence:**
```python
_MD_ANCHOR_RE = re.compile(r"^<!-- §([\w-]+\.[\w_]+) -->$")
_REF_RE = re.compile(r"§([\w-]+\.[\w_]+)(?=[\s,|.;:)\]!?'\"]|$)")
```

**Trigger:** Currently all anchors use underscores in symbol names, so this is not actively broken. But the asymmetry between namespace patterns (allows hyphens) and symbol patterns (doesn't) could confuse contributors.

**Severity:** LOW (downgraded — consistent behavior, just a documentation gap).

---

### M-15: `release_gate.do_release` rollback of tag on github-release failure calls `_rollback_tag()` which may not be defined

**Location:** `skills/sprint-release/scripts/release_gate.py:578-579`

**Description:** Inside the `else` (non-dry-run) branch, `_rollback_tag` is defined at line 536. The GitHub Release creation `try` block at line 562 calls `_rollback_tag()` on failure at line 578. Since `_rollback_tag` is defined in the same `else` block earlier (line 536), it IS in scope due to Python's function-level scoping. No bug here.

Actually wait — `_rollback_tag` is defined at line 536, AFTER the tag push succeeds at line 534. The GitHub Release creation at line 576 is inside a nested `try` block starting at line 562. If the tag push at line 529 fails, execution jumps to line 531-533 which calls `_rollback_commit()` and returns. So `_rollback_tag` is never called if it wasn't defined. This is fine.

Withdrawing this finding.

---

### M-15 (revised): `release_gate.generate_release_notes` produces empty output when `prev_version == version`

**Location:** `skills/sprint-release/scripts/release_gate.py:378`

**Description:** When `prev_version == version` (which happens when `calculate_version` returns the same version for both — i.e., `bump_type == "none"`), the `prev_tag` is set to empty string, and the "Full Changelog" section is entirely skipped. But `bump_type == "none"` causes `do_release` to return False at line 452, so `generate_release_notes` is never called in that case. Not a bug.

---

### M-15 (actual): `release_gate.do_release` pushes the version bump commit to the base branch implicitly

**Location:** `skills/sprint-release/scripts/release_gate.py:486-534`

**Description:** The release flow creates a version bump commit and a tag, then pushes only the tag (`git push origin v{new_ver}`). The commit itself is NOT pushed. This means the version bump in `project.toml` exists only locally and in the tag. After release, the base branch on the remote does not contain the version bump commit. The next developer who pulls will not see the version change unless they fetch the tag.

**Evidence:**
```python
# Lines 518-534: only the tag is pushed
r = subprocess.run(
    ["git", "push", "origin", f"v{new_ver}"],
    capture_output=True, text=True,
)
```

No `git push` for the commit on the current branch.

**Trigger:** Every release — the version bump commit stays local.

**Severity rationale:** This is likely intentional design (don't auto-push to the base branch), but it means the `write_version_to_toml` step has no lasting effect on the remote repo. The tag captures the commit, but the branch history diverges.

---

## LOW Severity

### L-01: `team_voices.main` always truncates quotes with `...` even when quote is shorter than 80 chars

**Location:** `scripts/team_voices.py:102`

**Description:** The display format always appends `...` to the output: `f"{q['quote'][:80]}..."`. Even for quotes shorter than 80 characters, the `...` is appended, making it look truncated when it's actually complete.

**Evidence:**
```python
print(f"  - [{q['file']}:{q['section']}] {q['quote'][:80]}...")
```

**Trigger:** Any voice quote shorter than 80 characters.

---

### L-02: `_parse_team_index` skips separator row detection with heuristic that can match data rows

**Location:** `scripts/validate_config.py:482`

**Description:** The separator detection `all(re.match(r"^[-:]+$", c) for c in cells)` matches rows where ALL cells are separator-like (`---`, `:--:`, etc.). But if a data row has all cells containing only hyphens and colons (unlikely but possible), it would be treated as a separator and skipped.

**Trigger:** A team index table row like `| -- | :--: | --- |` would be skipped.

**Severity:** LOW — extremely unlikely in practice.

---

### L-03: `sprint_init.detect_story_id_pattern` regex allows `#\d+` which matches GitHub issue references, not story IDs

**Location:** `scripts/sprint_init.py:462`

**Description:** The pattern `(US-\d{4}|[A-Z]{2,10}-\d+|#\d+)` includes `#\d+` which matches GitHub issue references like `#123`. These are not story IDs and would pollute the story ID pattern detection.

**Evidence:**
```python
patterns = re.compile(r"(US-\d{4}|[A-Z]{2,10}-\d+|#\d+)")
```

**Trigger:** Backlog files that reference GitHub issues with `#N` syntax. The `#NNNN` pattern could win the count and be returned as the "detected story ID pattern."

---

### L-04: `parse_simple_toml` key regex `[a-zA-Z_][a-zA-Z0-9_]*` does not allow hyphens in keys

**Location:** `scripts/validate_config.py:141`

**Description:** TOML allows hyphens in bare keys (e.g., `base-branch = "main"`), but the parser's key regex `^([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*(.*)$` only allows underscores. Any TOML key with hyphens will be silently ignored.

**Evidence:**
```python
kv_match = re.match(r"^([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*(.*)$", line)
```

**Trigger:** `base-branch = "main"` in project.toml — would be silently ignored. The project uses `base_branch` with underscores, so this is currently not triggered, but it violates TOML spec.

---

### L-05: `traceability.parse_stories` inner loop scans metadata table but has no `in_meta_table` guard like `manage_epics._parse_stories`

**Location:** `scripts/traceability.py:54-70`

**Description:** The metadata table scanner at line 54-70 starts scanning right after the story heading. It matches any `| Field | Value |` row, including rows that are part of the story body (not metadata). The only guard is `elif lines[j].strip() == "" and j > i + 2:` which breaks on blank lines after at least 2 lines. But the `j > i + 2` check means the first blank line immediately after the heading won't break the scan, potentially matching body content as metadata.

**Trigger:** A story with content like:
```
### US-0001: My Story
| Field | Value |
|-------|-------|
| SP | 3 |

Some paragraph...

| Another Table | Data |
```
The second table after the paragraph won't be reached because the blank line breaks the scan. This is actually safe. Minor fragility but not an active bug.

---

### L-06: `manage_epics._parse_header_table` uses `in_table` flag but never sets it to `True` before the first match

**Location:** `scripts/manage_epics.py:70-86`

**Description:** The `in_table` flag is initialized to `False` and set to `True` when a table row is found. The `elif in_table and line.strip() == ""` check breaks on blank lines after the table. But on the first row, `in_table` is `False`, so a blank line between the heading and the table won't trigger the break. This is actually correct behavior — it allows blank lines before the table. Not a bug.

---

### L-07: `sprint_init.ConfigGenerator.generate_project_toml` does not escape `binary_path` value

**Location:** `scripts/sprint_init.py:652-653`

**Description:** The `binary_path` value is interpolated directly into the TOML without escaping: `f'binary_path = "{s.binary_path.value.replace("<name>", name)}"'`. If the binary path contains backslashes (Windows paths) or quotes, the generated TOML would be malformed.

**Evidence:**
```python
lines.append(
    f'binary_path = "{s.binary_path.value.replace("<name>", name)}"')
```

The `esc()` function is not called on this value, unlike all other string values.

**Trigger:** A project with a binary path containing backslashes or quotes.

---

### L-08: `check_status._first_error` returns the first line containing error keywords — may return a false-positive match

**Location:** `skills/sprint-monitor/scripts/check_status.py:80-88`

**Description:** The function matches any line containing "error", "failed", "panicked", or "assert" (case-insensitive) in CI logs. This could match lines like "0 errors" or "no assertions failed" as the "first error."

**Evidence:**
```python
for line in log.splitlines():
    if any(
        kw in line.lower()
        for kw in ("error", "failed", "panicked", "assert")
    ):
        cleaned = re.sub(r"\x1b\[[0-9;]*m", "", line).strip()
        return cleaned[:117] + "..." if len(cleaned) > 117 else cleaned
```

**Trigger:** CI log output like `"Tests: 42 passed, 0 errors"` would be returned as the "error" line.

---

### L-09: `setup_ci._docs_lint_job` generates shell `find` command with unescaped single quotes in variable interpolation

**Location:** `skills/sprint-setup/scripts/setup_ci.py:184`

**Description:** The `find_args` construction uses `f"-name '*{ext}'"` which embeds the extension inside single quotes in the shell command. If an extension contained a single quote (unlikely for file extensions), the generated shell command would break.

**Trigger:** Not triggerable with standard file extensions, but the pattern is fragile.

---

### L-10: `sprint_teardown.print_dry_run` counts symlink targets shown incorrectly

**Location:** `scripts/sprint_teardown.py:203-204`

**Description:** The code prints up to 3 symlink targets, then says `({len(symlinks) - targets_shown} more symlink targets)`. But `targets_shown` only increments for targets that resolve inside the project root (the `try/except ValueError` block). If targets resolve outside the project root, they're skipped but still counted against the total, so the "more" count would be wrong.

**Evidence:**
```python
targets_shown = 0
for s in symlinks[:3]:
    target = resolve_symlink_target(s)
    if target:
        try:
            rel = target.relative_to(project_root)
            print(f"  {rel}  exists")
            targets_shown += 1
        except ValueError:
            pass
if len(symlinks) > 3:
    print(f"  ... ({len(symlinks) - targets_shown} more symlink targets)")
```

**Trigger:** Symlinks pointing outside the project root. The count `len(symlinks) - targets_shown` would overcount.

---

### L-11: `validate_config.load_config` resolves paths relative to `config_dir.parent`, not necessarily the project root

**Location:** `scripts/validate_config.py:556`

**Description:** `project_root = Path(config_dir).resolve().parent` assumes that the project root is the parent of the config directory. This is correct for the standard `sprint-config/` layout, but if someone nests the config directory deeper (e.g., `foo/bar/sprint-config/`), the resolved project root would be `foo/bar/` instead of the actual project root.

**Trigger:** Non-standard config directory path like `subdir/sprint-config`.

---

### L-12: `_has_closing_bracket` in TOML parser doesn't handle escaped single quotes

**Location:** `scripts/validate_config.py:188-201`

**Description:** `_has_closing_bracket` tracks quote state for both `"` and `'`. For double quotes, it checks for escape sequences (`_count_trailing_backslashes`). For single quotes, it does NOT check for escapes — which is actually correct per TOML spec, where single-quoted (literal) strings have no escape sequences. This is correct behavior.

---

### L-13: `check_status.check_branch_divergence` does not URL-encode branch names with special characters

**Location:** `skills/sprint-monitor/scripts/check_status.py:238-241`

**Description:** Branch names are interpolated directly into the API URL: `f"repos/{repo}/compare/{base_branch}...{branch}"`. If a branch name contains characters like `/` (common in git branch names like `sprint-1/US-0001-feature`), the GitHub API should handle this correctly since it expects branch names. But branches with other special characters (spaces, `#`, `?`) would break the URL.

**Evidence:**
```python
data = gh_json([
    "api", f"repos/{repo}/compare/{base_branch}...{branch}",
    "--jq", "{behind_by: .behind_by, ahead_by: .ahead_by}",
])
```

**Trigger:** Branch names with URL-unsafe characters (unlikely but possible).

---

### L-14: `manage_epics.renumber_stories` replaces ALL occurrences of old_id in non-heading lines, including prose text

**Location:** `scripts/manage_epics.py:360`

**Description:** The function uses `re.sub(rf'\b{re.escape(old_id)}\b', replacement, line)` which replaces the old story ID everywhere in non-heading lines. If the old ID appears in prose text (e.g., "This story was split from US-0102"), it would be replaced with the comma-separated list of new IDs, potentially creating ungrammatical text.

**Evidence:**
```python
new_lines.append(re.sub(rf'\b{re.escape(old_id)}\b', replacement, line))
```

**Trigger:** Epic file with prose mentioning the story ID being renumbered.

---

### L-15: `populate_issues._SPRINT_HEADER_RE` uses `\Z` anchor which includes trailing newline — `group(2)` may start with newline

**Location:** `skills/sprint-setup/scripts/populate_issues.py:57-58`

**Description:** The regex `### Sprint (\d+):.*?\n(.*?)(?=\n### Sprint |\n## |\Z)` uses `re.DOTALL` and `\Z` (matches at end of string, before trailing newline). The captured `group(2)` content starts immediately after the `\n` following the sprint header line. This is correct. Not a bug.

---

### L-16: `traceability.REQ_TABLE_ROW` uses en-dash and em-dash in character class which may not match all dash variants

**Location:** `scripts/traceability.py:28`

**Description:** The regex `r'^\|\s*(REQ-[\w-]+)\s*\|\s*(US-[\w, \u2013-]+)\s*\|'` — looking at the actual regex in the file: `r'^\|\s*(REQ-[\w-]+)\s*\|\s*(US-[\w, –-]+)\s*\|'`. The `–` in the character class is a literal en-dash (U+2013). In a character class `[...]`, this creates a range from `,` (U+002C) and ` ` (space, U+0020) to `-` (U+002D). Actually, the character class is `[\w, \u2013-]` which is `\w` or `,` or ` ` or `\u2013` or `-`. The `-` at the end is treated as literal. This is correct.

Actually wait — looking more carefully at the raw text: `US-[\w, –-]+` — the characters between the brackets are: `\w`, `,`, ` ` (space), `–` (en-dash U+2013), `-` (hyphen). In a regex character class, `–-` creates a range from en-dash (U+2013) to hyphen (U+002D). But U+2013 > U+002D, so this is an invalid range and would cause a `re.error` in strict mode. Actually in Python's `re` module, the range `–-` (U+2013 to U+002D) is reversed and would raise an error.

Let me check this more carefully...

**Evidence:**
```python
REQ_TABLE_ROW = re.compile(r'^\|\s*(REQ-[\w-]+)\s*\|\s*(US-[\w, –-]+)\s*\|')
```

The `–-` in the character class (en-dash followed by hyphen) — if this is `\u2013-` in a character class, Python's `re` treats `-` at the end of a class as literal. So the class is `\w`, `,`, ` `, `\u2013`, `-`. This should be fine since `-` is at the end.

Wait, actually in `[\w, –-]`, the content is: `\w`, `,`, ` `, `–` (en-dash), `-`. The `-` is at the end of the character class (before `]`), so it's literal. This is correct. Not a bug.

---

### L-17: `sync_backlog.main` catches `Exception` broadly but `do_sync` could raise `ImportError` which is handled differently at module level

**Location:** `scripts/sync_backlog.py:240-243`

**Description:** The `__main__` block catches all exceptions with `except Exception as exc`. The `do_sync` function raises `ImportError` if the bootstrap/populate modules aren't available (line 163). This `ImportError` would be caught by the broad handler and printed as a generic error, losing the specific context about missing dependencies.

**Trigger:** Running `sync_backlog.py` when `bootstrap_github.py` or `populate_issues.py` are not importable.

---

### L-18: `setup_ci.generate_ci_yaml` identifies test commands by checking if "test" appears in the command string — overly broad

**Location:** `skills/sprint-setup/scripts/setup_ci.py:310-314`

**Description:** `_find_test_command` checks `if "test" in cmd.lower()` which would match commands like `cargo test`, but also `npm run contest` or `python -m pytest --contest-mode`. The `_job_name_from_command` function has the same issue — `"test" in cmd_lower` at line 300 would match non-test commands.

**Evidence:**
```python
def _find_test_command(commands: list[str]) -> str:
    for cmd in commands:
        if "test" in cmd.lower() or "pytest" in cmd.lower():
            return cmd
    return ""
```

**Trigger:** CI command like `make integration-contest` would be treated as the test command.

---

### L-19: `check_status.py` imports `sync_backlog.main` as `sync_backlog_main` — naming collision risk

**Location:** `skills/sprint-monitor/scripts/check_status.py:26-29`

**Description:** The import `from sync_backlog import main as sync_backlog_main` works, but if the import fails (line 27-29), `sync_backlog_main` is set to `None`. At line 361, the check `if sync_backlog_main is not None` guards the call. If someone later adds a `sync_backlog_main` function in local scope, the guard would pass even when the import failed. Minor naming concern.

---

### L-20: `populate_issues.parse_detail_blocks` splits content on `_DETAIL_BLOCK_RE` — story IDs that appear in body text create phantom entries

**Location:** `skills/sprint-setup/scripts/populate_issues.py:164`

**Description:** `_DETAIL_BLOCK_RE.split(content)` splits on ALL `### US-XXXX: Title` occurrences. If a story's body text contains a reference like `### US-0099: See also this related story`, it would be treated as a new story block, and the content after it would be parsed as that phantom story's metadata.

**Evidence:**
```python
parts = _DETAIL_BLOCK_RE.split(content)
# parts: [preamble, id1, title1, body1, id2, title2, body2, ...]
for i in range(1, len(parts), 3):
```

**Trigger:** Epic file body text containing `### US-XXXX:` formatted references.

---

### L-21: `validate_config.parse_simple_toml` section header regex allows trailing dots in section names

**Location:** `scripts/validate_config.py:129`

**Description:** The regex `r"^\[([a-zA-Z0-9_][a-zA-Z0-9_.-]*)\]\s*(?:#.*)?$"` allows section names ending with `.` or `-`. A section like `[project.]` would be parsed as section `["project", ""]`, creating an empty-string key in the nested dict. This would cause silent data corruption when looking up keys.

**Evidence:**
```python
header_match = re.match(r"^\[([a-zA-Z0-9_][a-zA-Z0-9_.-]*)\]\s*(?:#.*)?$", line)
```

**Trigger:** `[project.]` in project.toml — creates `root["project"][""] = {}`.

---

## Summary

| Severity | Count | Key Themes |
|----------|-------|------------|
| HIGH | 5 | Paginated JSON parsing (H-01, H-02), milestone search query (H-04), regex replacement fragility (H-05), nested array handling (H-03) |
| MEDIUM | 10 | Vacuous truth in CI check (M-10), shell=True risk (M-08), sprint inference tie-breaking (M-12), subsection deletion (M-05), separator insertion (M-13) |
| LOW | 21 | Display bugs (L-01, L-10), pattern matching over-breadth (L-03, L-08, L-18), TOML spec gaps (L-04, L-21), escaping omissions (L-07) |
