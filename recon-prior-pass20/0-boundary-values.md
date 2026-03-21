# Boundary Value Analysis

Systematic audit of all production modules in `scripts/` and `skills/*/scripts/`.

Severity scale:
- **HIGH** = Would crash or corrupt data in realistic usage
- **MEDIUM** = Would produce wrong results or confusing behavior
- **LOW** = Cosmetic or unlikely-to-hit edge case
- **OK** = Handled in production code

---

## 1. Empty/Zero Inputs

### 1.1 Zero stories in a milestone

| Module | Behavior | Tested? | Severity |
|--------|----------|---------|----------|
| `sprint_analytics.compute_velocity` | `planned_sp` guarded: `if planned_sp else 0`. Returns 0% velocity. | Partially (test_zero_sp_handled) | **OK** |
| `update_burndown.write_burndown` | `total_sp` guarded: `if total_sp else 0`. Empty table written. | Not directly tested with 0 rows | **OK** |
| `update_burndown.main` | Exits with `sys.exit(1)` if `not issues`. | Not tested | **OK** |
| `check_status.check_milestone` | `total` guarded: `if total else 0`. Reports "0/0 stories done (0%)". | Tested (test_zero_total_stories) | **OK** |
| `sync_tracking.main` | Prints "No issues in milestone" and returns. | Not directly tested | **OK** |
| `populate_issues.main` | Exits with `sys.exit(1)` if no stories parsed. | Not tested | **OK** |

### 1.2 Zero milestones

| Module | Behavior | Tested? | Severity |
|--------|----------|---------|----------|
| `validate_config.validate_project` | Reports "No milestone files found" error. | Tested | **OK** |
| `bootstrap_github.create_milestones_on_github` | Returns 0, prints "No milestone files". | Not tested | **OK** |
| `sync_backlog.do_sync` | Returns `{"milestones": 0, "issues": 0}` when `get_milestones` returns []. | Not directly tested | **OK** |

### 1.3 Zero personas

| Module | Behavior | Tested? | Severity |
|--------|----------|---------|----------|
| `validate_config.validate_project` | Reports error if < 2 non-Giles personas. | Tested (BH18-008) | **OK** |
| `bootstrap_github.create_persona_labels` | Prints "(no personas found)" and returns. | Not tested | **OK** |
| `sprint_init.generate_team` | Falls back to skeleton template. | Tested | **OK** |

### 1.4 Zero/empty CI commands

| Module | Behavior | Tested? | Severity |
|--------|----------|---------|----------|
| `get_ci_commands` | Returns `[]` for missing key, wraps non-list in `[str(commands)]`. | Tested | **OK** |
| `setup_ci.generate_ci_yaml` | Generates YAML with no check jobs; build job still included. | Not directly tested with empty | **LOW** |
| `release_gate.gate_tests` | Returns `(True, "No check_commands configured")`. | Not tested | **OK** |

### 1.5 Empty strings in titles, bodies, labels

| Module | Behavior | Tested? | Severity |
|--------|----------|---------|----------|
| `extract_story_id("")` | Returns `"unknown"` (tested). | Tested | **OK** |
| `slug_from_title("")` | Returns `"untitled"` (explicit guard). | Tested | **OK** |
| `extract_sp({})` | Returns 0 (body defaults to `""`). | Tested | **OK** |
| `kanban_from_labels({})` | Returns `"todo"` fallback. | Tested | **OK** |
| `_yaml_safe("")` | Returns empty string (first `if not value` guard). | Tested | **OK** |
| `frontmatter_value("", key)` | Returns `None` (regex won't match). | Tested | **OK** |

### 1.6 Empty TOML sections

| Module | Behavior | Tested? | Severity |
|--------|----------|---------|----------|
| `parse_simple_toml("")` | Returns `{}`. | Tested (test_empty_input) | **OK** |
| `load_config` with empty project.toml | Validation fails with missing section errors. | Tested | **OK** |
| `parse_simple_toml` with `[section]` but no keys | Returns `{"section": {}}`. Key validation catches missing keys. | Tested | **OK** |

### 1.7 Division by zero

All percentage calculations are guarded with ternary checks:
- `sprint_analytics.py:67` — `if planned_sp else 0`
- `update_burndown.py:48` — `if total_sp else 0`
- `update_burndown.py:225` — `if total_sp else 0`
- `check_status.py:193` — `if total else 0`

| Finding | Severity |
|---------|----------|
| All division paths are guarded. | **OK** |

---

## 2. Unicode and Special Characters

### 2.1 Story titles with unicode

| Module | Behavior | Tested? | Severity |
|--------|----------|---------|----------|
| `extract_story_id` | Regex `[A-Z]+-\d+` won't match unicode; falls back to slug sanitization with `re.sub(r"[^a-zA-Z0-9_-]", "-", ...)`. Unicode chars become hyphens. | Property-tested (test_never_returns_empty) | **OK** |
| `slug_from_title` | `re.sub(r"[^a-zA-Z0-9\s-]", "", title)` strips all unicode chars. Title "Fix 🐛 bug" becomes "fix--bug". | Tested (test_special_chars_removed) | **OK** |
| `_format_story_section` | Sanitizes newlines in sid/title (`replace("\n", " ")`), but does NOT sanitize pipe chars `|` in titles. | Not tested for pipe chars | **MEDIUM** — A title containing `|` would corrupt the markdown table in the story section. |

### 2.2 TOML values with unicode

| Module | Behavior | Tested? | Severity |
|--------|----------|---------|----------|
| `_unescape_toml_string` | Handles `\uXXXX` and `\UXXXXXXXX` escapes. Invalid escapes preserved. | Tested (test_unicode_escape_4digit, test_unicode_escape_8digit) | **OK** |
| `parse_simple_toml` | Raw unicode in string values (e.g., `name = "项目"`) works — just passed through. | Not tested | **OK** (Python strings handle UTF-8 natively) |

### 2.3 YAML frontmatter with special chars

| Module | Behavior | Tested? | Severity |
|--------|----------|---------|----------|
| `_yaml_safe` | Quotes values containing `: `, `#`, `[`, `{`, `>`, `*`, `!`, `%`, `@`, `` ` ``, `\`, YAML booleans. Escapes `\` then `"`. | Tested (test_yaml_safe_special_start_chars, test_branch_with_special_chars_roundtrips) | **OK** |
| `frontmatter_value` | Strips surrounding double quotes and unescapes `\"` then `\\`. | Tested | **OK** |
| **Gap: unquoted colons in values** | If a frontmatter value like `title: US-0001: Fix thing` is written WITHOUT `_yaml_safe`, `frontmatter_value("title")` returns `"US-0001: Fix thing"` correctly because the regex `^key:\s*(.+)` is greedy. But `write_tf` always uses `_yaml_safe`, which would quote it. | Tested roundtrip | **OK** |

### 2.4 File paths with spaces

| Module | Behavior | Tested? | Severity |
|--------|----------|---------|----------|
| `sprint_init._symlink` | Uses `os.path.relpath` which handles spaces. | Not specifically tested | **OK** |
| `gh()` helper | Passes args as list (not shell string), so spaces in args are safe. | Implicit | **OK** |
| `sprint_teardown` | Uses `Path` objects throughout; `os.unlink(s)` handles spaces. | Not tested | **OK** |

---

## 3. Large Inputs

### 3.1 1000+ issues in a milestone

| Module | Behavior | Tested? | Severity |
|--------|----------|---------|----------|
| `list_milestone_issues` | Uses `--limit 1000`, calls `warn_if_at_limit(issues, 1000)`. **Warning only** — data silently truncated at 1000. | Not tested at limit | **MEDIUM** — Projects with >1000 issues per milestone would get silently incomplete data. Burndown, sync, and analytics would all undercount. The warning goes to stderr but nothing stops or retries. |
| `get_existing_issues` in `populate_issues` | Uses `--limit 500`, warns at limit. Could create duplicate issues if the real set > 500 since older issues wouldn't be seen. | Not tested | **MEDIUM** — On re-run after hitting the limit, stories already created beyond position 500 wouldn't be in the `existing` set, causing `create_issue` to attempt duplicates. GitHub would reject exact title duplicates but the script doesn't check for that. |
| `release_gate.gate_prs` | Explicitly fails the gate when `len(prs) >= 500`. | Tested | **OK** — This is the correct approach. |

### 3.2 Very long story titles

| Module | Behavior | Tested? | Severity |
|--------|----------|---------|----------|
| `slug_from_title` | No length limit on the slug. Very long titles produce very long filenames. | Not tested | **LOW** — Could hit OS filename length limits (255 bytes). The tracking file path would be `sprints/sprint-N/stories/very-long-slug.md`. |
| `extract_story_id` fallback | Truncates slug to 40 chars with `slug[:40]`. | Tested | **OK** |
| `gh()` commands | Story titles passed as `--title` arg; no shell escaping issues since args are list-based. | Implicit | **OK** |

### 3.3 Many milestone files

| Module | Behavior | Tested? | Severity |
|--------|----------|---------|----------|
| `get_milestones` | Uses `iterdir()` which returns all files. No limit. | Not tested | **OK** — Python handles large directories fine. |
| `parse_milestone_stories` | Iterates all files sequentially. O(files * stories). | Not tested | **LOW** — Performance only; no correctness issue. |

### 3.4 Deeply nested TOML sections

| Module | Behavior | Tested? | Severity |
|--------|----------|---------|----------|
| `parse_simple_toml` | Supports `[section.subsection]` via `_set_nested`. Arbitrary nesting depth works. | Not tested for deep nesting | **OK** — `setdefault` chain is safe. |

---

## 4. Type Confusion

### 4.1 Labels as strings vs dicts

| Module | Behavior | Tested? | Severity |
|--------|----------|---------|----------|
| `extract_sp` | Handles both: `isinstance(label, str)` and `isinstance(label, dict)`. | Tested | **OK** |
| `kanban_from_labels` | Handles both: `label if isinstance(label, str) else label.get("name", "")`. | Tested | **OK** |
| `extract_persona` in `sprint_analytics` | Same pattern. | Tested | **OK** |
| **Gap: label as int/bool/None** | If a label in the list is `None` or an integer (malformed API response), `isinstance(label, str)` and `isinstance(label, dict)` both return False, so the `continue` in `extract_sp` handles it. `kanban_from_labels` would call `None.get()` — wait, no, the ternary `label if isinstance(label, str) else label.get("name", "")` would call `.get()` on `None`. | Not tested | **MEDIUM** — If a label element is `None` (possible in malformed/mocked API response), `kanban_from_labels` would raise `AttributeError: 'NoneType' object has no attribute 'get'`. `extract_sp` is safer because it has an explicit `else: continue`. |

### 4.2 JSON responses as list vs dict vs None

| Module | Behavior | Tested? | Severity |
|--------|----------|---------|----------|
| `gh_json` | Returns `[]` on empty output. Fast-path `json.loads`, fallback incremental decoder. | Tested | **OK** |
| `compute_velocity` | Checks `if not isinstance(issues, list): issues = []`. | Not tested directly | **OK** |
| `find_milestone` | Checks `if not isinstance(milestones, list): return None`. | Tested | **OK** |
| `list_milestone_issues` | Checks `if not isinstance(issues, list): return []`. | Not tested | **OK** |
| `check_branch_divergence` | Checks `if isinstance(data, list)` for unexpected response shape. | Tested | **OK** |

### 4.3 Integer vs string sprint numbers

| Module | Behavior | Tested? | Severity |
|--------|----------|---------|----------|
| `safe_int` | Extracts leading digits from any string, returns 0 if none. | Tested | **OK** |
| `find_milestone` | Coerces to int with `int(sprint_num)`. | Tested | **OK** |
| `detect_sprint` | Returns `int(m.group(1))`. | Tested | **OK** |
| `sync_tracking.main` | Validates `sys.argv[1].isdigit()` before `int()`. | Tested | **OK** |
| **Gap: _infer_sprint_number fallback** | Returns `1` when no sprint number found in content or filename. This is reasonable but could be surprising for projects where the first sprint is not sprint 1. | Not tested for ambiguous fallback | **LOW** |

---

## 5. Concurrent/Repeated Execution

### 5.1 sync_tracking runs twice simultaneously

| Module | Behavior | Tested? | Severity |
|--------|----------|---------|----------|
| `sync_tracking.main` | No file locking. Two concurrent runs would both read the same tracking files, both detect the same issues as "new", and both call `write_tf` for the same files. | Not tested | **MEDIUM** — The last writer wins. Since both runs see the same GitHub state and produce the same output, the result would be correct. But there's a TOCTOU window: if one run reads a file between another run's read and write, it could revert a change. In practice, this is mitigated by the sprint-monitor calling sync_tracking sequentially, not in parallel. |
| `sync_backlog` | Has debounce/throttle state in `.sync-state.json`. Two concurrent runs could both read the same state, both decide to sync, and both write state. Last writer wins. | Not tested | **LOW** — The debounce mechanism makes this very unlikely in practice (requires two invocations within the same ~100ms window). Even if it happens, the result is just a redundant idempotent sync. |

### 5.2 sprint_init on already-initialized project

| Module | Behavior | Tested? | Severity |
|--------|----------|---------|----------|
| `ConfigGenerator.generate_project_toml` | Checks `if toml_path.is_file()` and skips with "preserved" message. | Tested | **OK** |
| `ConfigGenerator._inject_giles` | Preserves existing non-symlink giles.md. Replaces symlink giles.md. | Tested | **OK** |
| `ConfigGenerator._symlink` | Unlinks existing symlink/file before creating new one. | Tested | **OK** |
| Self-validation at the end catches any breakage. | Tested | **OK** |

### 5.3 update_burndown before sync_tracking

| Module | Behavior | Tested? | Severity |
|--------|----------|---------|----------|
| `update_burndown.load_tracking_metadata` | Returns empty dict `{}` if `stories_dir` doesn't exist. All stories get "—" for assignee/PR. | Not tested | **OK** — Graceful degradation. Burndown still shows SP/status from GitHub. |
| `update_burndown.write_burndown` | Creates `sprint_dir` with `mkdir(parents=True, exist_ok=True)`. | Implicit | **OK** |

---

## 6. Additional Boundary Findings

### 6.1 `_format_story_section` pipe chars in values

**File:** `scripts/manage_epics.py:147-203`

The function formats story data into markdown tables. While it sanitizes newlines in `sid` and `title`, it does not sanitize pipe characters `|`. A story title like `"Parse JSON | XML"` would produce:

```
### US-0001: Parse JSON | XML

| Field | Value |
|-------|-------|
| Story Points | 3 |
```

The heading line is fine (not a table), but if a persona name, blocked_by, or test_cases value contained `|`, it would corrupt the markdown table row.

**Severity:** **MEDIUM** — Pipe chars in metadata values would corrupt the epic file's table structure. The data is user-provided (from JSON on CLI), so it's plausible.

**Tested?** No test for pipe characters in story metadata values.

### 6.2 `kanban_from_labels` with None label element

**File:** `scripts/validate_config.py:923-939`

```python
name = label if isinstance(label, str) else label.get("name", "")
```

If `label` is `None`, `int`, `bool`, or any non-str/non-dict type, this calls `.get()` on it, which raises `AttributeError`.

**Severity:** **MEDIUM** — While GitHub API normally returns labels as either strings or dicts, a malformed response or test mock could include `None` in the labels list. The `extract_sp` function at line 793-799 handles this correctly with `else: continue`, but `kanban_from_labels` does not.

**Tested?** Not tested for non-str/non-dict labels in `kanban_from_labels`.

### 6.3 `manage_sagas.parse_saga` with empty file

**File:** `scripts/manage_sagas.py:33-59`

```python
"title": re.sub(r'^#+\s*', '', lines[0]).strip() if lines else "",
```

This is safe for empty files (`lines` would be `[]`). But if the file contains only blank lines, `lines[0]` would be `""` and `re.sub` would return `""`. This is acceptable.

**Severity:** **OK**

### 6.4 `sync_tracking.create_from_issue` with title missing colon

**File:** `skills/sprint-run/scripts/sync_tracking.py:288-291`

```python
short = (
    issue["title"].split(":", 1)[-1].strip()
    if ":" in issue["title"]
    else issue["title"]
)
```

Direct `issue["title"]` access (not `.get()`) will raise `KeyError` if the dict has no "title" key. Same at lines 158-162 in `update_burndown.py` and line 285-286 in `sync_tracking.py`.

**Severity:** **LOW** — `list_milestone_issues` requests `title` in the `--json` fields, so GitHub always includes it. A `KeyError` here would indicate a deeper API problem. The direct access is intentional (fail fast if the contract is broken).

### 6.5 `sprint_analytics.compute_review_rounds` with zero PRs after filtering

**File:** `scripts/sprint_analytics.py:100-127`

```python
if not sprint_prs:
    return {"avg_rounds": 0.0, "max_rounds": 0, "max_story": "", "pr_count": 0}
```

This is handled. But note line 118:

```python
max_story, max_rounds = max(rounds_per_pr, key=lambda x: x[1])
```

If `sprint_prs` is non-empty but ALL reviews are empty (no APPROVED or CHANGES_REQUESTED), then `rounds_per_pr` is non-empty (has entries), all with `round_count=0`. The `max()` call works fine (returns one of the zero entries). Lines 119-120 handle this:

```python
if max_rounds == 0:
    max_story = "none"
```

**Severity:** **OK** — Tested (test_all_zero_rounds_max_story_is_none).

### 6.6 `setup_ci.generate_ci_yaml` with unknown language

**File:** `skills/sprint-setup/scripts/setup_ci.py:240-244`

```python
setup_fn = _SETUP_REGISTRY.get(language)
if setup_fn:
    setup = setup_fn()
else:
    setup = f"      # TODO: Add setup steps for {language}"
```

**Severity:** **OK** — Graceful fallback with TODO comment.

### 6.7 `release_gate.bump_version` with non-semver input

**File:** `skills/sprint-release/scripts/release_gate.py:101-114`

```python
parts = base.lstrip("v").split(".")
if len(parts) != 3:
    raise ValueError(f"Expected 3-part semver (X.Y.Z), got: {base!r}")
```

**Severity:** **OK** — Tested (test_empty_raises_valueerror).

### 6.8 `check_status._first_error` false positive filter

**File:** `skills/sprint-monitor/scripts/check_status.py:82-90`

The false positive regex `r"\b(?:0|no)\s+(?:error|fail)"` skips lines like "0 errors" but would NOT skip a line like "Error: no such file". The function only returns the first matching error line.

**Severity:** **OK** — Tested (test_zero_errors_skipped).

### 6.9 `write_version_to_toml` with `[release]` in a comment

**File:** `skills/sprint-release/scripts/release_gate.py:296`

```python
release_section = re.search(r"^(?!#)\[release\]", text, re.MULTILINE)
```

The negative lookahead `(?!#)` prevents matching `# [release]` comments. However, it would still match a line like `  [release]` (indented — invalid TOML but the regex matches it). This is unlikely in practice.

**Severity:** **LOW**

### 6.10 `sprint_init._parse_workflow_runs` multiline block detection

**File:** `scripts/sprint_init.py:222-233`

The multiline run block detection breaks on a new YAML step: `if re.match(r'^\s*- ', lines[i])`. But it also continues on blank lines (`lines[i].strip() == ""`). If a workflow has a blank line at the end of a `run: |` block followed by unindented content, the parser would consume too many lines.

**Severity:** **LOW** — Only affects CI command detection, which is informational. The generated `project.toml` can be manually corrected.

### 6.11 `populate_issues.parse_detail_blocks` with malformed content

**File:** `skills/sprint-setup/scripts/populate_issues.py:221-264`

```python
parts = detail_re.split(content)
for i in range(1, len(parts), 3):
    if i + 2 > len(parts):
        break
    story_id, title, body = parts[i], parts[i+1].strip(), parts[i+2]
```

The `split` on a regex with 2 capture groups produces groups in triples. If the regex has a different number of groups (e.g., from a custom `story_id_pattern`), the stride of 3 would misalign.

The `_safe_compile_pattern` function rejects patterns with capturing groups, which prevents this. But the default `_DETAIL_BLOCK_RE` has 2 groups `(US-\d{4})` and `(.+)`, and the custom pattern adds 1 group for the ID. Wait — the custom pattern replaces only the ID part: `rf"^###\s+({pattern}):\s+(.+)$"`. Since `_safe_compile_pattern` rejects patterns WITH capturing groups, the custom `{pattern}` itself has 0 groups, and the outer regex has 2 groups. So the stride of 3 is correct (preamble, group1, group2, body, group1, group2, body...).

**Severity:** **OK** — The guard in `_safe_compile_pattern` prevents group-count mismatch.

### 6.12 `check_status.main` sync_backlog exception handling

**File:** `skills/sprint-monitor/scripts/check_status.py:365-371`

```python
if sync_backlog_main is not None:
    try:
        sync_status = sync_backlog_main()
        report_lines.append(f"Sync: {sync_status}")
    except Exception as exc:
        report_lines.append(f"Sync: error — {exc}")
```

This catches `Exception` broadly, which includes `KeyboardInterrupt`... wait, no, `KeyboardInterrupt` inherits from `BaseException`, not `Exception`. So this is fine.

**Severity:** **OK**

### 6.13 `sync_tracking.write_tf` and `update_burndown` concurrent writes to SPRINT-STATUS.md

**File:** `skills/sprint-run/scripts/update_burndown.py:81-115`

`update_sprint_status` reads the entire SPRINT-STATUS.md, does a regex replacement, and writes the whole file back. If `sync_tracking` and `update_burndown` both modify SPRINT-STATUS.md at the same time, one's changes would be lost.

**Severity:** **LOW** — In practice, these are called sequentially by the skill orchestrator. The sprint-monitor calls them in order. But there's no file-level locking to prevent concurrent invocation.

### 6.14 `_collect_sprint_numbers` with no sprint sections and no number in filename

**File:** `skills/sprint-setup/scripts/bootstrap_github.py:100-106`

Falls back to `sprint_nums.add(1)` with a stderr warning. This means a file named `overview.md` in the milestones directory would cause a spurious "sprint:1" label.

**Severity:** **LOW** — The milestones directory should only contain milestone files, and the validate_project check ensures they exist.

### 6.15 `release_gate.do_release` rollback with pushed_to_remote closure

**File:** `skills/sprint-release/scripts/release_gate.py:498-537`

The `_rollback_commit` closure captures `pushed_to_remote` from the enclosing scope. But `pushed_to_remote` is set to `True` only at line 610, after the push succeeds. The closure is called at lines 578 and 608-609. At line 578 (tag creation failure), `pushed_to_remote` is still `False`, so it correctly does a local reset. At line 608 (push failure), the push hasn't succeeded yet, so it's also `False`. This is correct.

**Severity:** **OK**

### 6.16 `manage_sagas.update_epic_index` filename parsing

**File:** `scripts/manage_sagas.py:197-200`

```python
parts = md_file.stem.split("-")
if len(parts) < 2:
    continue
epic_id = f"{parts[0]}-{parts[1]}"
```

A file named `E-0101-parsing-complex-data.md` would produce `epic_id = "E-0101"` (correct). But a file named `something-else.md` would produce `epic_id = "something-else"` (wrong format). The guard `len(parts) < 2` only skips single-part names.

**Severity:** **LOW** — The function is scanning an epics directory; non-epic files would produce wrong IDs but the saga's Epic Index table would just have a bogus row. The `saga_id` filter (line 203) provides a secondary guard.

### 6.17 `populate_issues.get_existing_issues` with 500+ existing issues

**File:** `skills/sprint-setup/scripts/populate_issues.py:330-347`

Uses `--limit 500`. If a project has more than 500 issues, earlier issues won't be in the `existing` set. The script would attempt to re-create them. GitHub would fail with "already_exists" if the exact title matches, but the `create_issue` function treats any `RuntimeError` as a failure and prints `! story_id: error`.

**Severity:** **MEDIUM** — On large projects, re-running `populate_issues` after the first 500 issues would generate a wall of false-positive error messages for issues that already exist. The creation wouldn't succeed (GitHub rejects exact duplicates), but the UX is bad and the exit wouldn't indicate partial success.

---

## 7. Summary of Actionable Findings

### HIGH severity: none found

All division-by-zero, crash-on-empty, and data-corruption paths are guarded.

### MEDIUM severity (5 findings):

| # | Module | Finding | Impact |
|---|--------|---------|--------|
| M1 | `validate_config.kanban_from_labels` | `label.get("name", "")` crashes on non-str/non-dict label (e.g., `None`). Unlike `extract_sp` which has `else: continue`. | `AttributeError` on malformed label data |
| M2 | `manage_epics._format_story_section` | Pipe chars `\|` in story metadata values corrupt markdown table rows. | Epic file table corruption |
| M3 | `validate_config.list_milestone_issues` | 1000-issue limit is warn-only; data silently truncated. Downstream consumers (burndown, sync, analytics) produce incomplete results. | Incorrect metrics on large projects |
| M4 | `populate_issues.get_existing_issues` | 500-issue limit means re-runs on large projects produce false "creation failed" noise for already-existing issues. | Bad UX, confusing error output |
| M5 | `sync_tracking` | No file locking; concurrent runs could race on tracking file writes. | Unlikely data inconsistency |

### LOW severity (6 findings):

| # | Module | Finding |
|---|--------|---------|
| L1 | `slug_from_title` | No length limit on generated slugs; could hit OS filename limits |
| L2 | `_infer_sprint_number` | Falls back to sprint 1 when no number found anywhere |
| L3 | `write_version_to_toml` | Matches indented `[release]` (invalid TOML) |
| L4 | `sprint_init._parse_workflow_runs` | Multiline block detection can over-consume lines |
| L5 | `_collect_sprint_numbers` | Non-milestone files in milestones/ dir get sprint 1 default |
| L6 | `manage_sagas.update_epic_index` | Non-epic filenames parsed into bogus epic IDs |
