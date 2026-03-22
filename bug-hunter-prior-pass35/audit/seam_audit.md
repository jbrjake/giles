# Seam Audit — Bug Hunter Pass 35

Cross-component integration seam audit. Only real bugs with concrete trigger paths.

---

## Seam 1: kanban.py ↔ sync_tracking.py (Two-path state management)

### BH35-001: lock_story and lock_sprint do not exclude each other — concurrent assign/update + sync can clobber writes

**Severity:** HIGH

**Files:**
- `scripts/kanban.py:805` — `do_assign` acquires `lock_story(tf.path)` (per-story `.lock` sentinel)
- `scripts/kanban.py:811` — `do_update` acquires `lock_story(tf.path)`
- `skills/sprint-run/scripts/sync_tracking.py:288` — entire sync loop acquires `lock_sprint(sprint_dir)` (sprint-wide `.kanban.lock` sentinel)
- `scripts/kanban.py:162-177` — `lock_story` uses `tracking_path.with_suffix(".lock")` (e.g., `sprint-1/stories/US-0001-foo.lock`)
- `scripts/kanban.py:180-194` — `lock_sprint` uses `sprint_dir / ".kanban.lock"` (e.g., `sprint-1/.kanban.lock`)

**What the bug is:**
`lock_story` and `lock_sprint` lock different sentinel files. They provide no mutual exclusion against each other. When `sync_tracking.py` holds `lock_sprint` and is writing a tracking file, a concurrent `kanban.py assign` or `kanban.py update` on the same story holds `lock_story` (a different lock) and writes the same file. Last writer wins — one set of changes is silently lost.

The comment at `kanban.py:499-504` (on `do_sync`) explicitly acknowledges this design gap: "Without the sprint lock, concurrent do_assign or do_update calls (which use lock_story) can race with the read-modify-write cycle here." But `sync_tracking.py` only acquires `lock_sprint`, not `lock_story`, before writing each file.

**How to trigger it:**
1. Run `python sync_tracking.py 1` (holds `lock_sprint`, iterates over issues)
2. While sync is running, run `kanban.py assign US-0042 --implementer Hexwise` (holds `lock_story`)
3. Both read the same `US-0042-*.md` file, modify different fields, and write it back
4. The sync write overwrites the assign, or vice versa — one set of changes is lost

**Likelihood:** Medium. This requires two concurrent CLI invocations on the same sprint, which happens when `sprint-monitor` triggers a sync while a user or agent is assigning stories.

---

### BH35-002: kanban.py non-WIP transitions (todo→design, integration→done) use lock_story while sync uses lock_sprint — no mutual exclusion

**Severity:** MEDIUM

**Files:**
- `scripts/kanban.py:789-798` — non-WIP transitions (else branch) use `lock_story`
- `scripts/kanban.py:756-757` — `kanban.py sync` uses `lock_sprint` then calls `do_sync`
- `skills/sprint-run/scripts/sync_tracking.py:288` — sync uses `lock_sprint`

**What the bug is:**
A `kanban.py transition US-0042 design` call acquires `lock_story`, reads the file, transitions to design, and writes back. Concurrently, `sync_tracking.py` (or `kanban.py sync`) holds `lock_sprint`, reads the same file, sees GitHub says `todo`, and overwrites the file back to `todo`. The transition is silently undone.

The WIP-limited transitions (dev/review/integration) correctly use `lock_sprint` (line 780), which provides mutual exclusion with sync. But the non-WIP transitions (todo→design, integration→done) use the per-story lock, which does not.

**How to trigger it:**
1. Run `kanban.py transition US-0042 design` while `sync_tracking.py` is running
2. kanban.py transitions the story to `design` locally and pushes the label to GitHub
3. sync_tracking.py, which fetched the issue list before the label was applied, sees `kanban:todo` and overwrites the local file back to `todo`
4. Local state and GitHub state diverge

**Likelihood:** Low-medium. The window is narrow — it requires the sync to have fetched issues before the label push but write the file after the transition. But the GitHub API call in `do_transition` (label swap) takes measurable time, widening the window.

---

## Seam 2: TOML parser divergence

### BH35-003: Inline TOML parsers fail on section headers with trailing comments

**Severity:** MEDIUM

**Files:**
- `scripts/validate_config.py:179` — full parser: `re.match(r"^\[([a-zA-Z0-9_][a-zA-Z0-9_.-]*)\]\s*(?:#.*)?$", line)` — handles `[ci] # comment`
- `.claude-plugin/hooks/verify_agent_output.py:117` — `stripped == f"[{section}]"` — fails on `[ci] # comment`
- `.claude-plugin/hooks/session_context.py:30` — `stripped == f"[{section}]"` — fails on `[ci] # comment`
- `.claude-plugin/hooks/review_gate.py:196` — `in_paths = s == "[paths]"` — fails on `[paths] # comment`

**What the bug is:**
`validate_config.parse_simple_toml` correctly strips inline comments from section headers, so `[ci] # CI configuration` is recognized as section `ci`. All three inline parsers use exact string equality (`stripped == f"[{section}]"`), which fails when the section header has a trailing comment. The key lookup silently returns `None`/empty string, falling back to defaults.

**How to trigger it:**
1. Add a comment after any section header in `project.toml`: `[ci] # CI configuration`
2. `validate_config.load_config()` parses it correctly — `check_commands` are found
3. `commit_gate._load_config_check_commands()` → `_read_toml_key(text, "ci", "check_commands")` → never enters the `ci` section → returns `None` → falls back to empty list
4. The commit gate never detects check commands, so `_matches_check_command` falls back to hardcoded patterns only. If the project uses a non-standard test runner (e.g., `make check`), verification recording silently stops working.
5. Similarly, `session_context._read_toml_string` fails to find `sprints_dir` and `team_dir`, so no retro context is injected at session start.

**Likelihood:** Medium. While current `sprint_init.py` templates don't add comments after section headers, users editing `project.toml` by hand commonly add them.

---

### BH35-004: session_context._read_toml_string mishandles escape sequences — \n becomes literal 'n', \t becomes literal 't'

**Severity:** LOW

**Files:**
- `.claude-plugin/hooks/session_context.py:38` — `return re.sub(r'\\(.)', lambda x: x.group(1), m.group(1))`
- `scripts/validate_config.py:271-315` — `_unescape_toml_string` correctly maps `\n`→newline, `\t`→tab, `\uXXXX`→Unicode char

**What the bug is:**
`session_context._read_toml_string` treats ALL backslash escapes as "remove the backslash, keep the next character." So `\n` becomes literal `n`, `\t` becomes literal `t`, `\u0041` becomes `u0041`. The full parser in `validate_config.py` correctly interprets these per the TOML spec.

If a path value in `project.toml` contains `\t` (e.g., a Windows-style path fragment `C:\tools`), `validate_config` would produce `C:<TAB>ools` (correct per TOML spec — user should use single quotes for literal backslashes), while `session_context` would produce `C:tools` (wrong — dropped the backslash and kept literal 't'). More practically, if a value contains `\"` (escaped quote), `validate_config` produces `"` while `session_context` also produces `"` — that case works.

**How to trigger it:**
1. Set `sprints_dir = "path\\to\\sprints"` in `project.toml` (double backslash = literal backslash per TOML)
2. `validate_config` returns `path\to\sprints` (correct)
3. `session_context` returns `pathtosprints` (wrong — `\\` → `\` is correct, but only by accident since it strips the first `\` and keeps the second `\`, then strips that `\` and keeps the next char)

Actually, re-examining: `re.sub(r'\\(.)', ...)` on `\\t` would match `\t` (backslash + t) and replace with `t`. The first `\` is consumed as the regex escape. Wait — the raw string `r'\\(.)'` is the regex `\\(.)` which matches a literal backslash followed by any character. On input `\\t` (two characters: `\` and `t`), it matches and returns `t`. That's wrong — `\\` in TOML means a literal backslash, so the result should be `\` followed by whatever comes next parsed independently.

For the paths that `session_context` actually reads (`sprints_dir`, `team_dir`), these are simple relative paths like `"sprints"` that never contain escape sequences in practice.

**Likelihood:** Very low. Path values in `project.toml` are simple relative paths. But the bug is real if a path ever contains a backslash.

---

### BH35-005: review_gate._get_base_branch only matches double-quoted strings — single-quoted base_branch is silently ignored

**Severity:** LOW

**Files:**
- `.claude-plugin/hooks/review_gate.py:42` — `re.match(r'\s*base_branch\s*=\s*"([^"]+)"', line)` — double quotes only
- `scripts/validate_config.py:336-341` — `_parse_value` handles both `"double"` and `'single'` quoted strings
- `.claude-plugin/hooks/session_context.py:35-42` — `_read_toml_string` handles both quote types

**What the bug is:**
If `project.toml` has `base_branch = 'develop'` (single-quoted, which is valid TOML), `review_gate._get_base_branch` returns `"main"` (the default). The review gate then blocks pushes to `main` but allows direct pushes to `develop` — the actual base branch. This silently defeats the direct-push protection.

**How to trigger it:**
1. Set `base_branch = 'develop'` in `project.toml` (single-quoted)
2. `review_gate` reads `main` as the base branch
3. `git push origin develop` is allowed through — not blocked
4. `git push origin main` is blocked — but `main` isn't even the base branch

**Likelihood:** Low. The `sprint_init.py` generator uses double quotes, so projects bootstrapped by giles won't hit this. Manual edits could.

---

## Seam 3: populate_issues.py ↔ manage_epics.py story format contract

### BH35-006: manage_epics.STORY_HEADING uses \s* (optional space) after colon, populate_issues._DETAIL_BLOCK_RE uses \s+ (required space) — stories with no space after colon are invisible to populate_issues

**Severity:** MEDIUM

**Files:**
- `scripts/manage_epics.py:23` — `STORY_HEADING = re.compile(r'^(###\s+(US-\d+):\s*(.+))')` — `\s*` after colon (space optional)
- `skills/sprint-setup/scripts/populate_issues.py:207` — `_DETAIL_BLOCK_RE = re.compile(r"^###\s+(US-\d+):\s+(.+)$", re.MULTILINE)` — `\s+` after colon (space required)

**What the bug is:**
`manage_epics.STORY_HEADING` accepts headings like `### US-0042:Title` (no space after colon) via `\s*`. If `manage_epics.add_story` is given a story whose heading ends up as `### US-0042:Title` (because the input title has no leading space, and `_format_story_section` at line 161 writes `f"### {sid}: {title}"` — wait, that always adds a space).

Let me re-check: `_format_story_section` writes `f"### {sid}: {title}"` (line 161), which always has a space after the colon. So `manage_epics` always WRITES with a space. But `manage_epics.STORY_HEADING` READS with `\s*`, meaning it can parse files that were manually edited to omit the space, while `populate_issues._DETAIL_BLOCK_RE` cannot.

The real risk is manual edits or third-party tools writing `### US-0042:Title` format. `manage_epics` can read and manipulate these sections, but `populate_issues.parse_detail_blocks` silently skips them — their acceptance criteria, user stories, and metadata are lost from GitHub issues.

**How to trigger it:**
1. Manually edit an epic file to have `### US-0042:Fix login bug` (no space after colon)
2. `manage_epics.py parse epic.md` parses it successfully (STORY_HEADING matches with `\s*`)
3. `populate_issues.py` runs enrichment via `enrich_from_epics` → `parse_detail_blocks`
4. `_DETAIL_BLOCK_RE` does not match (requires `\s+` after colon)
5. Story US-0042's detail block is silently dropped — no acceptance criteria, no user story in the GitHub issue

**Likelihood:** Low-medium. Only triggered by manual edits that omit the space. The code paths themselves always write with a space.

---

### BH35-007: manage_epics._format_story_section omits Saga and Epic fields from the metadata table — populate_issues.parse_detail_blocks reads empty saga/epic for add_story-created sections

**Severity:** MEDIUM

**Files:**
- `scripts/manage_epics.py:160-188` — `_format_story_section` writes: Story Points, Priority, Personas, Blocked By, Blocks, Test Cases — but NOT Saga or Epic
- `skills/sprint-setup/scripts/populate_issues.py:258-259` — `parse_detail_blocks` reads `saga = meta.get("saga", "")` and `epic = meta.get("epic", "")` from the metadata table

**What the bug is:**
When a story is added to an epic file via `manage_epics.add_story`, the formatted section never includes `| Saga | S01 |` or `| Epic | E-0001 |` rows in the metadata table, even if `story_data` contains `saga` and `epic` keys. The `_format_story_section` function at lines 160-188 hardcodes which fields to emit and omits saga/epic.

When `populate_issues.parse_detail_blocks` later parses this section, `meta.get("saga", "")` and `meta.get("epic", "")` return empty strings. If this story only exists in the epic file (not in any milestone table), it gets created as a GitHub issue with no saga label and no epic reference.

Note: `manage_epics._parse_stories` DOES read saga and epic from the table (lines 124-125: `story_meta.get("Saga", "")`, `story_meta.get("Epic", "")`), so the round-trip within manage_epics itself is broken too — a story added with saga/epic data, then immediately re-parsed, loses those fields.

**How to trigger it:**
1. Run `manage_epics.py add epic.md '{"id": "US-0099", "title": "New feature", "saga": "S01", "epic": "E-0001", "story_points": 3, "priority": "P1"}'`
2. The written section has no `| Saga | S01 |` or `| Epic | E-0001 |` rows
3. Re-parsing with `manage_epics.parse_epic` returns `saga: ""` and `epic: ""` for that story
4. `populate_issues` creates a GitHub issue without saga label or epic reference

**Likelihood:** High whenever `add_story` is used with saga/epic data. The fields are silently dropped on write.

---

### BH35-008: manage_epics._sanitize_md strips # from story IDs — story IDs containing # (e.g., custom patterns) become unparseable

**Severity:** LOW

**Files:**
- `scripts/manage_epics.py:148-151` — `_sanitize_md` strips all `#` characters
- `scripts/manage_epics.py:156` — `sid = _sanitize_md(story_data.get("id", "US-XXXX"))` — sanitizes the story ID before writing the heading

**What the bug is:**
`_sanitize_md` strips ALL `#` characters from the value. If a custom story ID pattern includes `#` (e.g., a project using `#123` as story IDs, which `extract_story_id` supports via its fallback path), `_format_story_section` writes a heading like `### 123: Title` instead of `### #123: Title`. Neither `manage_epics.STORY_HEADING` nor `populate_issues._DETAIL_BLOCK_RE` would match this heading (both require `US-\d+` format), so the section becomes invisible to both parsers.

The `_sanitize_md` function was added in BH24-034 to prevent heading injection, but stripping `#` from all fields including the story ID is overly aggressive. The story ID is used in a `### {sid}: {title}` heading where additional `#` characters in `sid` would not create injection (they'd just be content after the `### ` prefix).

**How to trigger it:**
1. Call `manage_epics.add_story(path, {"id": "#42", "title": "Fix"})` — unlikely with standard US-XXXX IDs, but possible with custom patterns
2. The written heading is `### 42: Fix` (# stripped from ID)
3. The story is lost on re-parse since `42` doesn't match `US-\d+`

**Likelihood:** Very low. Standard `US-XXXX` IDs don't contain `#`. Only custom ID patterns starting with `#` would be affected.

---

## Summary

| ID | Seam | Severity | Description |
|----|------|----------|-------------|
| BH35-001 | 1 | HIGH | lock_story and lock_sprint provide no mutual exclusion — concurrent assign/update + sync clobber writes |
| BH35-002 | 1 | MEDIUM | Non-WIP transitions use lock_story while sync uses lock_sprint — transition can be silently undone |
| BH35-003 | 2 | MEDIUM | Inline TOML parsers fail on section headers with trailing comments |
| BH35-004 | 2 | LOW | session_context._read_toml_string mishandles \n, \t, \\ escape sequences |
| BH35-005 | 2 | LOW | review_gate only matches double-quoted base_branch — single-quoted silently falls back to 'main' |
| BH35-006 | 3 | MEDIUM | STORY_HEADING uses \s* (optional space) but _DETAIL_BLOCK_RE uses \s+ (required space) after colon |
| BH35-007 | 3 | MEDIUM | _format_story_section omits Saga and Epic fields — data lost on write, never round-trips |
| BH35-008 | 3 | LOW | _sanitize_md strips # from story IDs, breaking custom ID patterns that use # |
