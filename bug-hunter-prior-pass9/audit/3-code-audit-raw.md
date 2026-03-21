# Code Audit Pass 9 — Raw Findings

Date: 2026-03-15
Auditor: Adversarial code review (Claude Opus 4.6)
Scope: All 18 production Python scripts, full read

---

## Table of Contents

1. [validate_config.py](#1-scriptsvalidate_configpy)
2. [sprint_init.py](#2-scriptssprint_initpy)
3. [sprint_teardown.py](#3-scriptssprint_teardownpy)
4. [commit.py](#4-scriptscommitpy)
5. [validate_anchors.py](#5-scriptsvalidate_anchorspy)
6. [sync_backlog.py](#6-scriptssync_backlogpy)
7. [sprint_analytics.py](#7-scriptssprint_analyticspy)
8. [traceability.py](#8-scriptstraceabilitypy)
9. [test_coverage.py](#9-scriptstest_coveragepy)
10. [team_voices.py](#10-scriptsteam_voicespy)
11. [manage_epics.py](#11-scriptsmanage_epicspy)
12. [manage_sagas.py](#12-scriptsmanage_sagaspy)
13. [bootstrap_github.py](#13-bootstrap_githubpy)
14. [populate_issues.py](#14-populate_issuespy)
15. [setup_ci.py](#15-setup_cipy)
16. [sync_tracking.py](#16-sync_trackingpy)
17. [update_burndown.py](#17-update_burndownpy)
18. [release_gate.py](#18-release_gatepy)
19. [check_status.py](#19-check_statuspy)
20. [Cross-Cutting Issues](#20-cross-cutting-issues)

---

## 1. scripts/validate_config.py

### CA-001: `gh_json` returns `[]` on empty output, but callers may expect a dict

- **File:** `scripts/validate_config.py`, line 55
- **What it does:** When `gh()` returns an empty string, `gh_json` returns `[]` (empty list).
- **What's wrong:** Several callers expect a dict response (e.g., `find_milestone` at line 758 which does `if not isinstance(milestones, list)`). If the API returns a JSON object (non-list), that's handled. But if the API returns empty, the `[]` fallback silently masks errors. For endpoints like `repos/{owner}/{repo}/compare/...` (used in `check_status.py` line 238), the result is always a dict, never a list. If that API returns empty for some reason, the caller gets `[]` and skips all processing with no error.
- **How to trigger:** Call `gh_json` against an endpoint that normally returns a dict, when the API returns nothing (network glitch, rate limiting with empty body).
- **Severity:** Low
- **Suggested fix:** Consider returning `None` on empty output and making callers handle `None`, or add an `expect_type` parameter.

### CA-002: `load_config` parses TOML twice

- **File:** `scripts/validate_config.py`, lines 515-524
- **What it does:** `validate_project()` parses `project.toml` at line 353. Then `load_config()` parses it again at line 524.
- **What's wrong:** Double file I/O and double parsing. Not a bug, but wasteful. If the file changes between the two reads (TOCTOU), validation could pass on one version and `load_config` could return a different version.
- **How to trigger:** Edit `project.toml` while `load_config()` is running (narrow window).
- **Severity:** Low
- **Suggested fix:** Have `validate_project` return the parsed config dict alongside the errors, so `load_config` doesn't re-parse.

### CA-003: `_parse_value` fallback accepts arbitrary unquoted strings silently

- **File:** `scripts/validate_config.py`, lines 239-242
- **What it does:** If a value isn't a boolean, quoted string, array, or integer, it falls through to being returned as a raw string.
- **What's wrong:** Typos in TOML like `language = Rust` (missing quotes) silently produce `"Rust"` as a string. This is intentional leniency per the comment, but it means malformed TOML never produces a warning. A user who writes `check_commands = cargo test` (missing array brackets and quotes) gets the string `"cargo test"` instead of `["cargo test"]`, and `get_ci_commands` at line 594-596 wraps it in a list — so it works by accident. But this breaks the invariant that `check_commands` is always a list in the parsed TOML.
- **How to trigger:** Any unquoted value in project.toml.
- **Severity:** Low
- **Suggested fix:** Add a warning to stderr when the fallback is used for values that look like they should be quoted or arrayed.

### CA-004: `_parse_team_index` does not guard against empty `cells` list

- **File:** `scripts/validate_config.py`, line 449
- **What it does:** Strips `|` from both ends and splits on `|`.
- **What's wrong:** If a line is just `|` or `||`, `cells` could be `['']` or `['', '']`. The `headers` check `if not headers` would then set headers to `['']`, causing all subsequent rows to have malformed key mappings. The separator-row check `all(re.match(r"^[-:]+$", c) for c in cells)` would also match `['']` via `all()` on an empty iterable... wait, no: `re.match(r"^[-:]+$", '')` returns `None`, so `['']` wouldn't pass. But `cells = ['']` after strip/split is possible. The issue is that `headers = ['']` is then treated as a valid header row, and all subsequent data rows will have `row = {'': 'first_cell_value'}`.
- **How to trigger:** A markdown file with a line containing only `|` characters.
- **Severity:** Low
- **Suggested fix:** Add `if not any(cells): continue` after the cells split.

### CA-005: `find_milestone` always queries ALL milestones with `--paginate`

- **File:** `scripts/validate_config.py`, line 758
- **What it does:** Fetches all milestones from GitHub with `--paginate`.
- **What's wrong:** For large repos with many milestones, this fetches every page. There's no `state=open` filter, so closed milestones are included too. The function is called from `update_burndown.py`, `sprint_analytics.py`, `check_status.py`, and `sync_tracking.py` — sometimes multiple times per run (once in `main` and once transitively). Each call makes a separate API request.
- **How to trigger:** Any sprint operation on a repo with 100+ milestones.
- **Severity:** Low (performance)
- **Suggested fix:** Add `"-f", "state=all", "-f", "per_page=100"` and consider caching per process.

### CA-006: `list_milestone_issues` calls `gh` directly then `json.loads`, duplicating `gh_json`

- **File:** `scripts/validate_config.py`, lines 771-779
- **What it does:** Calls `gh()` then `json.loads()` manually.
- **What's wrong:** This duplicates the pattern in `gh_json()`. Using `gh_json` directly would be more consistent and handle the empty-output case.
- **How to trigger:** N/A — code smell, not a bug.
- **Severity:** Low
- **Suggested fix:** Replace with `gh_json(["issue", "list", ...])`.

### CA-007: `extract_sp` regex can match unintended body text

- **File:** `scripts/validate_config.py`, lines 673-675
- **What it does:** Searches the issue body for patterns like `sp: 5` or `story points: 8`.
- **What's wrong:** The regex `(?:story\s*points?|sp)\s*[:=]\s*(\d+)` can match things like "... this maps the SP: 0 baseline..." or "suspend processing: 42" (matching `sp` as a substring of "suspend" — wait, no, the regex requires `sp` at word start? Actually no, `re.search` finds it anywhere). `sp` is extremely short and could match substrings like "wasp: 3" in a comment. The `re.IGNORECASE` flag makes it even more promiscuous.
- **How to trigger:** An issue body containing text like "The WASP: 3 project..." would incorrectly extract 3 as the story point value.
- **Severity:** Medium
- **Suggested fix:** Add `\b` word boundaries: `r"\b(?:story\s*points?|sp)\b\s*[:=]\s*(\d+)"`.

### CA-008: `warn_if_at_limit` warning is advisory only — no mechanism to actually handle truncation

- **File:** `scripts/validate_config.py`, lines 783-788
- **What it does:** Prints a warning if results hit the limit.
- **What's wrong:** The warning goes to stderr but the caller continues processing potentially incomplete data. In `release_gate.py` line 181, the PR gate correctly fails if the limit is hit. But in `sprint_analytics.py`, `sync_tracking.py`, and `update_burndown.py`, truncated data silently produces wrong metrics (undercounted velocity, missing tracking files, wrong burndown).
- **How to trigger:** A milestone with 500+ issues.
- **Severity:** Medium
- **Suggested fix:** Return a boolean or raise an exception so callers can decide.

---

## 2. scripts/sprint_init.py

### CA-009: `_parse_workflow_runs` multiline detection heuristic is fragile

- **File:** `scripts/sprint_init.py`, lines 196-237
- **What it does:** Extracts `run:` values from GitHub Actions YAML.
- **What's wrong:** The `while i < len(lines) and (lines[i].startswith("  ") or lines[i].strip() == ""):` check at line 221 uses a fixed 2-space indent. GitHub Actions YAML can use any indentation level. A workflow with 4-space base indentation would cause the continuation to eat lines from the next step. Also, the `re.match(r'^\s*- ', lines[i])` break condition at line 223 doesn't distinguish between a new YAML list item at the correct nesting level vs. a continuation line that happens to contain `- `.
- **How to trigger:** A workflow file with non-standard indentation or multiline `run:` blocks that contain markdown lists.
- **Severity:** Low (only affects CI command detection during setup, which is advisory).
- **Suggested fix:** Track the indentation level of the `run:` line and use it for continuation detection.

### CA-010: `_symlink` follows symlinks when checking existence, masking broken links

- **File:** `scripts/sprint_init.py`, lines 555-557
- **What it does:** Checks `link_path.is_symlink() or link_path.exists()` before unlinking.
- **What's wrong:** This is actually correct — it handles both valid symlinks and broken symlinks. No bug here. (False alarm.)
- **Severity:** N/A

### CA-011: `_esc` doesn't handle single quotes, which can appear in project names

- **File:** `scripts/sprint_init.py`, lines 574-581
- **What it does:** Escapes characters for TOML basic strings (double-quoted).
- **What's wrong:** Per TOML spec, single quotes inside double-quoted strings don't need escaping, so this is correct. However, `_esc` is also used for values that end up in code comments or descriptions, where `'` followed by `s` could cause confusion. Not a real bug.
- **Severity:** N/A

### CA-012: `detect_story_id_pattern` regex has a non-capturing group that can return `None`

- **File:** `scripts/sprint_init.py`, lines 462-478
- **What it does:** Scans backlog files for story ID patterns.
- **What's wrong:** At line 472, `prefix = re.match(r"([A-Z#]+-?)", m)` can return `None` if the match starts with a digit (e.g., for `#123`, the first char `#` is in the character class, so it matches — OK). But for a pattern like `US-0001`, the match is `US-` which works. Actually, the `patterns` regex at line 462 is `(US-\d{4}|[A-Z]{2,10}-\d+|#\d+)` — all alternatives start with `[A-Z]` or `#`, so the prefix match will always succeed. No bug.
- **Severity:** N/A

### CA-013: `generate_project_toml` uses `subprocess.run` without timeout for `git rev-parse`

- **File:** `scripts/sprint_init.py`, lines 596-602
- **What it does:** Detects current branch for `base_branch` default.
- **What's wrong:** No `timeout` parameter. If git hangs (e.g., locked `.git/index`), the script hangs indefinitely.
- **How to trigger:** Run `sprint_init.py` while another git process holds the lock.
- **Severity:** Low
- **Suggested fix:** Add `timeout=5`.

### CA-014: `_write_manifest` parses the `self.created` list using string splitting, which is fragile

- **File:** `scripts/sprint_init.py`, lines 797-833
- **What it does:** Parses entries like `"  generated  project.toml"` to extract file paths.
- **What's wrong:** The parsing relies on `entry.split(None, 1)[1]` to get the path. If a path contains parentheses (like in `"skeleton   dest_rel (from skeleton_name)"`), the `split(" (")[0]` at line 813 correctly strips the provenance. But if a file path itself contains ` (` (e.g., `docs/notes (old)/file.md`), the path would be truncated. This is unlikely in practice but the parsing approach is brittle.
- **How to trigger:** A file path containing the literal string ` (`.
- **Severity:** Low
- **Suggested fix:** Track created items as structured data (list of tuples) instead of parsing display strings.

---

## 3. scripts/sprint_teardown.py

### CA-015: `classify_entries` uses `dirs.remove(d)` which mutates a list during iteration

- **File:** `scripts/sprint_teardown.py`, line 68
- **What it does:** Removes symlinked directories from the `dirs` list during `os.walk`.
- **What's wrong:** `for d in list(dirs):` creates a copy for iteration, but `dirs.remove(d)` mutates the original. This is the correct pattern for `os.walk` (you modify `dirs` in-place to control descent). No bug here — the `list(dirs)` copy is for iteration safety.
- **Severity:** N/A

### CA-016: `check_active_loops` only checks crontab, not Claude Code `/loop` state

- **File:** `scripts/sprint_teardown.py`, lines 278-303
- **What it does:** Checks crontab for sprint-related entries.
- **What's wrong:** The function's docstring says "Detect active /loop commands related to sprint-monitor" but Claude Code's `/loop` doesn't use crontab — it's an in-process scheduling mechanism. The function will almost never find anything, making the loop cleanup guidance misleading. The `print_loop_cleanup_hints` function at line 306 does show manual `/loop stop` instructions regardless, so the user still gets guidance.
- **How to trigger:** Always — the detection is always empty for Claude Code users.
- **Severity:** Low (misleading but harmless — the instructions are still shown).
- **Suggested fix:** Remove the crontab check or rename the function to clarify it's best-effort.

### CA-017: `remove_generated` prompts on stdin without checking if stdin is a TTY

- **File:** `scripts/sprint_teardown.py`, line 243
- **What it does:** Calls `input()` to prompt for confirmation.
- **What's wrong:** If the script is invoked non-interactively (piped, from a subprocess), `input()` will raise `EOFError` (if stdin is closed) or read from the pipe (potentially consuming data meant for something else). There's no try/except around `input()`.
- **How to trigger:** `echo "" | python sprint_teardown.py` or calling from a subprocess.
- **Severity:** Medium
- **Suggested fix:** Wrap `input()` in try/except EOFError or check `sys.stdin.isatty()` before prompting.

---

## 4. scripts/commit.py

### CA-018: `check_atomicity` threshold of 3 directories is arbitrary and not configurable

- **File:** `scripts/commit.py`, line 78
- **What it does:** Rejects commits spanning 3+ top-level directories unless `--force` is used.
- **What's wrong:** The threshold is hardcoded. A monorepo with `src/`, `tests/`, and `docs/` would trigger this warning on almost every commit. The threshold should probably be configurable or smarter (e.g., `tests/` and `docs/` shouldn't count as separate concerns from the code they test/document).
- **How to trigger:** Any commit touching files in 3+ top-level directories (extremely common).
- **Severity:** Medium
- **Suggested fix:** Exclude known ancillary directories (`tests`, `docs`, `__pycache__`) from the directory count, or make the threshold configurable.

### CA-019: `run_commit` passes user-controlled message directly as command argument

- **File:** `scripts/commit.py`, lines 95-98
- **What it does:** Runs `git commit -m <message>`.
- **What's wrong:** The message is passed as a list argument to `subprocess.run` (no `shell=True`), so there's no command injection risk. This is correct and safe.
- **Severity:** N/A

---

## 5. scripts/validate_anchors.py

### CA-020: `_PY_ANCHOR_RE` is too strict — requires exactly `word.word` format

- **File:** `scripts/validate_anchors.py`, line 77
- **What it does:** Matches Python anchor comments like `# §validate_config.gh`.
- **What's wrong:** The regex `r"^# §([\w]+\.[\w]+)$"` requires exactly one dot with word characters on each side. An anchor like `# §validate_config._REQUIRED_FILES` works because `_` is a `\w` char. But a hypothetical anchor like `# §validate_config.my.nested` wouldn't match. This matches the current convention (single dot), so it's correct for this project.
- **Severity:** N/A

### CA-021: `_MD_ANCHOR_RE` is inconsistent with `_PY_ANCHOR_RE` in character classes

- **File:** `scripts/validate_anchors.py`, line 78
- **What it does:** Matches markdown anchor comments like `<!-- §sprint-run.phase_1 -->`.
- **What's wrong:** The regex `r"^<!-- §([\w-]+\.[\w_]+) -->$"` allows hyphens in the namespace part (`[\w-]+`) but only underscores in the symbol part (`[\w_]+`). Since `\w` already includes `_`, the `[\w_]` is equivalent to `\w`. But the symbol part doesn't allow hyphens, while the namespace does. An anchor like `<!-- §sprint-run.phase-1 -->` (hyphen in symbol) wouldn't match.
- **How to trigger:** Create an anchor with a hyphen in the symbol name.
- **Severity:** Low
- **Suggested fix:** Use `[\w-]+` for the symbol part too, or document the convention that symbols use underscores.

### CA-022: `fix_missing_anchors` can insert duplicate anchors on re-run

- **File:** `scripts/validate_anchors.py`, lines 229-293
- **What it does:** Inserts missing anchor comments into source files.
- **What's wrong:** If the function is run, it inserts anchors. If then a reference is removed from the doc file and the function is run again, the previously-inserted anchor remains (orphaned but harmless). More importantly, if the function is run twice without the first run completing (e.g., interrupted), partial insertions would shift line numbers. But the real concern is: after inserting an anchor at line N, the next call to `_find_symbol_line` for a different anchor in the same file could find the wrong line because the line numbers shifted. The code sorts fixes in reverse line order (line 282) to handle this correctly within a single file, which is good. No actual bug.
- **Severity:** N/A

### CA-023: `_REF_RE` lookahead doesn't include `/` or `-`, so `§namespace.symbol-foo` is partially matched

- **File:** `scripts/validate_anchors.py`, line 94
- **What it does:** Matches `§namespace.symbol` references followed by specific terminators.
- **What's wrong:** The regex `r"§([\w-]+\.[\w_]+)(?=[\s,|.;:)\]!?'\"]|$)"` expects the match to be followed by whitespace, punctuation, or end-of-string. If a reference is followed by `/` (e.g., in a URL-like context `§validate_config.gh/api`), the `/` isn't in the lookahead set, so the match would fail entirely. This is arguably correct — you don't want to match partial URLs — but the behavior might surprise someone.
- **Severity:** Low (edge case in markdown writing).

---

## 6. scripts/sync_backlog.py

### CA-024: `hash_milestone_files` uses file basename as key, causing collisions

- **File:** `scripts/sync_backlog.py`, lines 43-52
- **What it does:** Creates a dict mapping `Path.name` to SHA-256 hash.
- **What's wrong:** If two milestone files in different directories have the same filename (e.g., `backlog/milestones/sprint-1.md` and `backlog/milestones/old/sprint-1.md`), the second would overwrite the first in the dict. In practice, `get_milestones()` only returns files from a single directory, so this won't happen. But the function's interface (accepting arbitrary `list[str]`) doesn't enforce this.
- **How to trigger:** Pass file paths from different directories with the same basename.
- **Severity:** Low
- **Suggested fix:** Use the full relative path as the key instead of just the filename.

### CA-025: `do_sync` calls `populate_issues.get_existing_issues()` and `get_milestone_numbers()` which can raise

- **File:** `scripts/sync_backlog.py`, lines 181-183
- **What it does:** Fetches existing issues and milestone numbers.
- **What's wrong:** Both `get_existing_issues()` and `get_milestone_numbers()` re-raise `RuntimeError` and `json.JSONDecodeError` on failure (see `populate_issues.py` lines 264-266, 281-283). In `do_sync`, these exceptions are not caught, so they propagate to `main()` which catches all `Exception` at line 242. This means a GitHub API failure during sync causes the entire check to fail, and `save_state` at line 235 is never called. The state will then remain with `pending_hashes` set, triggering a re-sync attempt on the next loop iteration — which is actually the correct behavior (retry on failure).
- **Severity:** Low (accidental correctness).

### CA-026: `check_sync` mutates `state` in place even when returning `should_sync=False`

- **File:** `scripts/sync_backlog.py`, lines 115-152
- **What it does:** Updates `state["pending_hashes"]` during debounce decisions.
- **What's wrong:** The caller at line 235 always calls `save_state`, which persists the mutated state. This is correct — the debounce state needs to persist across invocations. Not a bug, but the in-place mutation pattern is worth noting for maintainability.
- **Severity:** N/A

---

## 7. scripts/sprint_analytics.py

### CA-027: `compute_review_rounds` fetches ALL PRs in the repo, not just milestone PRs

- **File:** `scripts/sprint_analytics.py`, lines 83-87
- **What it does:** Fetches up to 500 PRs with `gh pr list --state all`.
- **What's wrong:** There's no `--milestone` filter on `gh pr list` (because the `gh pr list` CLI doesn't support milestone filtering). The code filters client-side at lines 93-97. For repos with 500+ PRs, the `--limit 500` truncates the result set, potentially missing some sprint PRs. The `warn_if_at_limit` call at line 89 alerts to this, but the metrics are silently wrong.
- **How to trigger:** A repo with 500+ total PRs (not uncommon).
- **Severity:** Medium
- **Suggested fix:** Use `--search` with a milestone filter, or paginate fully.

### CA-028: `compute_velocity` includes non-story issues in SP count

- **File:** `scripts/sprint_analytics.py`, lines 44-52
- **What it does:** Fetches all issues in a milestone and sums story points.
- **What's wrong:** Bug reports, spikes, and chores in the milestone would all be counted. If they have 0 SP (no `sp:N` label or body text), they inflate `story_count` but not `planned_sp`, making the velocity percentage misleading. A milestone with 10 stories (50 SP) and 5 bug reports (0 SP) would show `story_count=15` but `planned_sp=50`.
- **How to trigger:** Any milestone with non-story issues.
- **Severity:** Low
- **Suggested fix:** Filter by `type:story` label before counting.

---

## 8. scripts/traceability.py

### CA-029: `parse_stories` scan stops at first blank line after 2 table rows, potentially missing metadata

- **File:** `scripts/traceability.py`, lines 65-67
- **What it does:** Scans metadata table rows after a `### US-XXXX:` heading, stopping at a blank line if `j > i + 2`.
- **What's wrong:** The condition `j > i + 2` means it only breaks on blank lines after the 2nd row (positions i+1 and i+2 are the first two non-heading lines). If the metadata table has exactly 2 rows followed by a blank line, it stops. But if there's a blank line between the heading and the table (which is common in markdown), the first non-heading line is blank, and `j > i + 2` is false at `j = i + 2`, so it doesn't break, continues to `j = i + 3`, finds the table, and works. This is actually fine for the common case. But if the heading is immediately followed by two blank lines before the table, the scanner would miss the table entirely because it would break on the second blank line.
- **How to trigger:** Two consecutive blank lines between a story heading and its metadata table.
- **Severity:** Low
- **Suggested fix:** Only break on blank lines after seeing at least one table row.

### CA-030: `REQ_TABLE_ROW` regex uses `[\w, –-]` which includes an em-dash literal

- **File:** `scripts/traceability.py`, line 28
- **What it does:** Matches PRD reference table rows with story ID mappings.
- **What's wrong:** The character class `[\w, –-]` contains `–` (en-dash, U+2013) and `-` (hyphen). The range `–-` is from U+2013 to U+002D, which is backwards (U+2013 > U+002D) and would be an invalid range in some regex engines. However, Python's `re` module interprets this as three literal characters: `–`, `,`, and `-` because `-` at the end of a character class is literal. Actually wait — the class is `[\w, –-]`: the characters are `\w`, ` ` (space), `,`, ` ` (space), `–` (en-dash), `-` (hyphen). The `-` is at the end, so it's literal. This works but is fragile and hard to read.
- **How to trigger:** Not a runtime bug, but confusing for maintenance.
- **Severity:** Low
- **Suggested fix:** Use explicit escaping: `[\w, \u2013\-]` or place `-` at the start.

### CA-031: `parse_requirements` only scans files named `reference.md`

- **File:** `scripts/traceability.py`, line 114
- **What it does:** Uses `prd_path.rglob("reference.md")` to find PRD reference files.
- **What's wrong:** Only files literally named `reference.md` are scanned. This is extremely specific — a PRD directory with files like `requirements.md`, `prd-section-1.md`, or `reference-auth.md` would all be ignored. The function silently returns empty results for non-conforming directory structures.
- **How to trigger:** Name your PRD reference file anything other than `reference.md`.
- **Severity:** Medium
- **Suggested fix:** Accept a configurable glob pattern, or scan all `.md` files.

---

## 9. scripts/test_coverage.py

### CA-032: Rust test pattern requires `#[test]` immediately before `fn`, missing `#[tokio::test]`

- **File:** `scripts/test_coverage.py`, line 23
- **What it does:** Matches Rust test functions with `#\[test\]\s*(?:#\[.*\]\s*)*fn\s+(\w+)`.
- **What's wrong:** The pattern requires `#[test]` specifically. Rust async tests use `#[tokio::test]` or `#[async_std::test]`, which won't match. The `(?:#\[.*\]\s*)*` part allows additional attributes between `#[test]` and `fn`, but `#[tokio::test]` is the test marker itself, not `#[test]` followed by something else.
- **How to trigger:** Any Rust project using async tests.
- **Severity:** Medium
- **Suggested fix:** Change to `#\[(?:test|tokio::test|async_std::test)\]` or more generically `#\[.*test.*\]`.

### CA-033: Fuzzy matching in `check_test_coverage` can produce false positives

- **File:** `scripts/test_coverage.py`, lines 119-129
- **What it does:** Matches planned test cases to implemented tests by substring matching.
- **What's wrong:** A planned test `TC-A-001` normalized to `tc_a_001` would match any test function containing that substring, like `test_tc_a_001_setup` (correct) but also `test_extract_tc_a_0014_parsing` (incorrect — `tc_a_001` is a substring of `tc_a_0014`). The slug fallback at line 126 (`slug = parts[1]` → `"a_001"`) is even more promiscuous — `a_001` could match `data_0010_tests` (contains `a_001` as a substring? No — `a_001` is not in `data_0010_tests`. But `a_001` IS in `extra_001_test`).
- **How to trigger:** Test case IDs that are substrings of other test function names.
- **Severity:** Low
- **Suggested fix:** Use word boundary matching (`_` + normalized + `_` or end-of-string).

### CA-034: `scan_project_tests` for Rust scans all `src/**/*.rs` files, not just test modules

- **File:** `scripts/test_coverage.py`, line 32
- **What it does:** Glob pattern `**/src/**/*.rs` matches all Rust source files.
- **What's wrong:** The Rust test pattern `#[test]` only appears in test modules (either `tests/` or `#[cfg(test)]` blocks within `src/`), but scanning all `src/**/*.rs` is correct because Rust unit tests live inside the source files themselves. This is actually correct.
- **Severity:** N/A

---

## 10. scripts/team_voices.py

### CA-035: `VOICE_PATTERN` doesn't match multi-line quoted text

- **File:** `scripts/team_voices.py`, lines 26-28
- **What it does:** Matches blockquote voice lines like `> **Name:** "quote"`.
- **What's wrong:** The regex `r'^>\s*\*\*([^*]+?):\*\*\s*(?:"(.+?)"|(.+?))\s*$'` uses `.+?` which doesn't match newlines. This is correct because the continuation handling at lines 70-78 collects multi-line blockquotes separately. But the `(.+?)` for unquoted text is non-greedy and anchored to `$`, so it matches everything to the end of the line. A line like `> **Name:** text with "inner quotes" more text` would match group 2 (quoted) as `inner quotes`, not the full text. The `|` alternation tries quoted first, so the `"inner quotes"` path would win.
- **How to trigger:** A voice line with quotes that aren't at the boundaries: `> **Name:** she said "hello" loudly`.
- **Severity:** Medium
- **Suggested fix:** Match the full text after the colon first, then optionally strip outer quotes: `r'^>\s*\*\*([^*]+?):\*\*\s*(.+?)\s*$'` and strip quotes in post-processing.

### CA-036: Voice continuation lines don't handle nested blockquotes

- **File:** `scripts/team_voices.py`, lines 70-78
- **What it does:** Collects continuation lines that start with `>` but don't match `VOICE_PATTERN`.
- **What's wrong:** If a blockquote contains a sub-blockquote (e.g., `>> nested`), the `lstrip(">")` at line 75 would strip all leading `>` characters, losing the nesting. This is probably fine since saga/epic files don't typically nest blockquotes.
- **Severity:** Low

---

## 11. scripts/manage_epics.py

### CA-037: `add_story` doesn't validate that the story ID is unique within the epic

- **File:** `scripts/manage_epics.py`, lines 224-236
- **What it does:** Appends a new story section to an epic file.
- **What's wrong:** If you call `add_story(path, {"id": "US-0001", ...})` and US-0001 already exists in the file, you get a duplicate section. The function doesn't parse the existing file to check.
- **How to trigger:** Call `add_story` with an ID that already exists.
- **Severity:** Medium
- **Suggested fix:** Parse the epic first and check `raw_sections` for duplicate IDs.

### CA-038: `remove_story` walk-back can eat the separator from the *previous* story

- **File:** `scripts/manage_epics.py`, lines 256-260
- **What it does:** Removes blank lines and `---` separators before the story being deleted.
- **What's wrong:** The walk-back loop `while sep_start > 0 and walked < 3 and lines[sep_start - 1].strip() in ("", "---"):` removes up to 3 lines of blank/separator content before the story. If the previous story has no trailing content after its last line and immediately before the `---`, the walk-back could eat the previous story's trailing separator. The `sep_start += 1` at line 263 "keeps at least one blank line" but this adjustment happens unconditionally, even if no walk-back occurred, potentially leaving `sep_start == start + 1` which then skips the first line of the story.
- **How to trigger:** Remove the first story in a file with a minimal separator.
- **Severity:** Low (output is slightly different formatting but no data loss).

### CA-039: `renumber_stories` uses `re.sub` with word boundaries, which can match partial IDs

- **File:** `scripts/manage_epics.py`, line 352
- **What it does:** Replaces `\bUS-0102\b` with `US-0102a, US-0102b`.
- **What's wrong:** The `\b` word boundary in regex considers `-` as a non-word character. So `\bUS-0102\b` would match `US-0102` in `US-01020` because the boundary between `2` and `0` exists. Wait — `\b` matches between a word character and a non-word character. In `US-01020`, after `0102` comes `0`, which is also a word character, so `\b` does NOT match there. So `US-0102` would NOT match in `US-01020`. This is correct.
- **Severity:** N/A

### CA-040: `_format_story_section` doesn't handle missing required keys gracefully

- **File:** `scripts/manage_epics.py`, lines 171-220
- **What it does:** Formats a story dict as markdown.
- **What's wrong:** The function accesses `story_data['id']`, `story_data['title']`, `story_data['story_points']`, `story_data['priority']` without `.get()`. If any of these keys are missing (e.g., when called from `add_story` with a minimal dict from the CLI), it raises `KeyError`.
- **How to trigger:** `manage_epics.py add epic.md '{}'` — the empty dict `{}` would crash at line 174 with `KeyError: 'id'`.
- **Severity:** Medium
- **Suggested fix:** Use `.get()` with defaults for all keys.

---

## 12. scripts/manage_sagas.py

### CA-041: `_parse_header_table` in manage_sagas.py stops at `##` headings, missing `###` headings

- **File:** `scripts/manage_sagas.py`, line 73
- **What it does:** Parses the saga metadata table, stopping at `##` headings.
- **What's wrong:** The check `if line.startswith("##"):` would also match `###`, `####`, etc. If the saga file has `### Notes` before `## Epic Index`, the header table parsing would stop prematurely. Since the saga format uses `## ` (double-hash) for main sections and the header table comes before any section heading, this is probably fine in practice. But it's more strict than intended — `##Header` (no space) would also trigger the break.
- **How to trigger:** A saga file with a `###` heading between the metadata table and the first `## ` section.
- **Severity:** Low

### CA-042: `update_sprint_allocation` and `update_epic_index` can produce files with no trailing newline

- **File:** `scripts/manage_sagas.py`, lines 178-179, 234-235
- **What it does:** Joins lines with `\n` and writes.
- **What's wrong:** `"\n".join(new_lines)` produces a string where the last line has no trailing newline. For files that previously had a trailing newline, this changes the file. This is a POSIX compliance issue — files should end with a newline.
- **How to trigger:** Any call to `update_sprint_allocation` or `update_epic_index`.
- **Severity:** Low
- **Suggested fix:** Append `+ "\n"` to the write call.

### CA-043: `update_team_voices` separator logic is broken for first voice

- **File:** `scripts/manage_sagas.py`, lines 252-256
- **What it does:** Adds `>` separator between voice blocks.
- **What's wrong:** The `if new_section[-1] != "":` check at line 254 looks at the last element, which after initialization at line 252 is `""`. So for the first voice, `new_section[-1]` is `""`, the condition is false, and no separator is added. This is correct — you don't want a `>` before the first voice. For subsequent voices, `new_section[-1]` is the previous voice line (not `""`), so the separator `>` is added. This is actually correct behavior.
- **Severity:** N/A

### CA-044: `update-index` command crashes if `sys.argv[3]` is missing

- **File:** `scripts/manage_sagas.py`, line 280
- **What it does:** Accesses `sys.argv[3]` for the `epics_dir` argument.
- **What's wrong:** There's no length check before accessing `sys.argv[3]`. If the user runs `manage_sagas.py update-index saga.md` without the epics_dir argument, it raises `IndexError`.
- **How to trigger:** `python manage_sagas.py update-index saga.md`
- **Severity:** Medium
- **Suggested fix:** Add `if len(sys.argv) < 4:` guard like the other commands have.

---

## 13. bootstrap_github.py

### CA-045: `create_milestones_on_github` uses `text` variable before it might be defined

- **File:** `skills/sprint-setup/scripts/bootstrap_github.py`, line 242
- **What it does:** Uses `text` in the fallback title logic.
- **What's wrong:** At line 242, `sprint_m = re.search(r"Sprint\s+(\d+)", text if mf.is_file() else "")`. The `text` variable is only defined at line 229 inside the `if mf.is_file():` block. If `mf.is_file()` is False (line 228), the code skips lines 229-238 (setting `title` and `description`), so `title` remains `None`, and the fallback at line 241 `if title is None:` is entered. The `text if mf.is_file() else ""` at line 242 correctly handles this — if the file doesn't exist, it uses `""`. But if `mf.is_file()` returned True at line 228 but returns False at line 242 (TOCTOU — file deleted between checks), `text` would be defined from line 229 and `mf.is_file()` would be False, so it would use `""` — this is fine too. No actual bug.
- **Severity:** N/A

### CA-046: `_parse_saga_labels_from_backlog` pattern `S\d{2}` is too restrictive

- **File:** `skills/sprint-setup/scripts/bootstrap_github.py`, line 147
- **What it does:** Matches saga IDs like `S01`, `S02`.
- **What's wrong:** The pattern requires exactly 2 digits. A project with 100+ sagas (e.g., `S100`) wouldn't be detected. This is by design (the convention is 2-digit saga IDs), but could be surprising.
- **How to trigger:** A project with saga ID `S100` or higher.
- **Severity:** Low

---

## 14. populate_issues.py

### CA-047: `_build_row_regex` injection via `story_id_pattern` config value

- **File:** `skills/sprint-setup/scripts/populate_issues.py`, lines 63-86
- **What it does:** Builds a regex from a user-configured pattern.
- **What's wrong:** The function checks for unescaped capturing groups (line 74) and wraps the pattern in a larger regex. However, the user-supplied `pattern` is inserted directly into a regex string at line 80 via an f-string. A malicious or broken pattern could contain regex modifiers, lookaheads, or other constructs that break the surrounding regex. The `try/except re.error` at line 82 catches compile errors, but a pattern like `.*` would compile fine and match everything, causing the table parser to match non-table lines. While this is a config file the user controls (so "attacking yourself"), the pattern has no validation beyond the capturing-group check.
- **How to trigger:** Set `story_id_pattern = ".*"` in project.toml.
- **Severity:** Low (self-inflicted misconfiguration).

### CA-048: `get_milestone_numbers` uses `--jq .` which may not paginate correctly

- **File:** `skills/sprint-setup/scripts/populate_issues.py`, line 279
- **What it does:** Fetches milestones and parses as JSON.
- **What's wrong:** The `--jq .` flag combined with `--paginate` may produce multiple JSON arrays concatenated, not a single valid JSON. The GitHub CLI's `--paginate` with `--jq` applies the jq filter per page, so `--jq "."` on 3 pages produces `[...][...][...]` which is not valid JSON. `json.loads()` would only parse the first array and raise an error on the rest (or succeed if there's only one page).
- **How to trigger:** A repo with more than 30 milestones (default per_page for the milestones API).
- **Severity:** High
- **Suggested fix:** Remove `--jq .` and use `--paginate` alone (which concatenates JSON arrays correctly), or remove `--paginate` and use a high `per_page` value.

### CA-049: `enrich_from_epics` uses `max(set(known_sprints), key=known_sprints.count)` which can crash

- **File:** `skills/sprint-setup/scripts/populate_issues.py`, line 232
- **What it does:** Finds the most common sprint number among stories in an epic file.
- **What's wrong:** If `known_sprints` is empty (no story IDs from this epic match existing parsed stories), the ternary falls through to `0`, which is handled correctly at line 244. But the expression `max(set(known_sprints), key=known_sprints.count)` is O(n*m) where n is the number of unique sprints and m is the total — not a bug, just inefficient. More importantly, `set(known_sprints)` is used as the iterable for `max()`, but `known_sprints.count` counts in the original list. This is correct and is a standard Python idiom for mode-finding.
- **Severity:** N/A

### CA-050: `format_issue_body` uses literal Unicode characters that could be mangled by encoding conversions

- **File:** `skills/sprint-setup/scripts/populate_issues.py`, lines 322-326
- **What it does:** Includes `\u00b7` (middle dot) and `\u2014` (em-dash) in issue bodies.
- **What's wrong:** The `gh issue create --body ...` command passes these characters through. If the user's terminal or locale doesn't support UTF-8, the `gh` command might mangle them. However, GitHub's API is UTF-8, so this should work in practice.
- **Severity:** Low

---

## 15. setup_ci.py

### CA-051: Generated YAML may have invalid indentation when `setup` is empty

- **File:** `skills/sprint-setup/scripts/setup_ci.py`, lines 104-113
- **What it does:** Generates CI job YAML.
- **What's wrong:** When no language setup function is found (line 222), `setup` is `"      # TODO: Add setup steps for {language}"` — a single indented comment line. This line gets inserted at the `{setup}` position in the template at line 110, which already has the correct indentation. But the template at line 110 uses `{setup}` flush-left within the f-string, meaning the indentation comes from the `setup` string itself. If `setup` is empty string `""`, the YAML would have an empty line between `checkout` and the `run` step, which is valid YAML. No actual bug.
- **Severity:** N/A

### CA-052: `_docs_lint_job` generates shell script with unescaped variables

- **File:** `skills/sprint-setup/scripts/setup_ci.py`, lines 181-207
- **What it does:** Generates a doc-size-limit CI job with inline shell.
- **What's wrong:** The generated shell script uses `$file`, `$LINES`, `$FAILED` which are bash variables. The YAML uses `run: |` (literal block scalar) so these are passed through to the shell correctly. The f-string interpolation with `{find_args}` and `{ext_display}` at lines 201 and 206 is also safe because these come from the `_LANG_EXTENSIONS` dict (trusted source). No injection risk.
- **Severity:** N/A

### CA-053: `_generate_test_job` uses double-escaped braces for GitHub Actions expressions

- **File:** `skills/sprint-setup/scripts/setup_ci.py`, line 127
- **What it does:** Generates `${{ matrix.os }}` in an f-string.
- **What's wrong:** The expression `${{{{ matrix.os }}}}` uses quadruple braces because f-strings require `{{` to produce a literal `{`. This produces `${{ matrix.os }}` in the output, which is correct for GitHub Actions. No bug.
- **Severity:** N/A

---

## 16. sync_tracking.py

### CA-054: `read_tf` YAML parser doesn't handle multi-line values

- **File:** `skills/sprint-run/scripts/sync_tracking.py`, lines 136-162
- **What it does:** Parses YAML-like frontmatter from tracking files.
- **What's wrong:** The regex `rf"^{k}:\s*(.+)"` matches only single-line values. If a title or branch name contains a newline (which shouldn't happen but could via a bug), the parser would only capture the first line. More importantly, if a value is empty (e.g., `implementer: ` with trailing space), `.+` requires at least one character, so the match fails and `v()` returns `""`. This is actually correct behavior for empty values.
- **Severity:** N/A

### CA-055: `_yaml_safe` doesn't handle all YAML special values

- **File:** `skills/sprint-run/scripts/sync_tracking.py`, lines 165-180
- **What it does:** Quotes values that contain YAML-sensitive characters.
- **What's wrong:** The function doesn't quote values that YAML would interpret as non-string types: `true`, `false`, `yes`, `no`, `null`, `~`, or bare numbers like `123`. A story title like "Yes: this is done" would have `: ` detected and quoted. But a title of just "true" or "null" would not be quoted, and a YAML parser would interpret it as a boolean or null. Since the reader (`read_tf`) uses regex (not a YAML parser), it would read "true" as the string "true" anyway. But if someone later switches to a real YAML parser, these values would break.
- **How to trigger:** A story with title "true", "false", "null", "yes", or "no".
- **Severity:** Low
- **Suggested fix:** Add YAML reserved words to the quoting check.

### CA-056: `get_linked_pr` timeline API query uses `first` which returns only the first linked PR

- **File:** `skills/sprint-run/scripts/sync_tracking.py`, lines 60-78
- **What it does:** Queries the issue timeline API to find linked PRs.
- **What's wrong:** The `--jq` filter ends with `| first`, which returns only the first linked PR. If an issue has multiple linked PRs (e.g., an initial PR that was closed and a replacement), only the first (chronologically oldest) is returned. This might be the closed/superseded PR rather than the active one.
- **How to trigger:** An issue with multiple linked PRs.
- **Severity:** Medium
- **Suggested fix:** Use `| last` or sort by state/date to prefer open/merged PRs.

### CA-057: `create_from_issue` generates branch name from slug, which could conflict

- **File:** `skills/sprint-run/scripts/sync_tracking.py`, lines 258-281
- **What it does:** Generates a tracking file with `branch=f"sprint-{sprint}/{slug}"`.
- **What's wrong:** Two issues with similar titles could generate the same slug and therefore the same branch name. The `slug_from_title` function at line 96 sanitizes the title, but two titles like "US-0001: Add auth" and "US-0001: Add authentication" would both produce different slugs (fine). But "Add auth!" and "Add auth?" would both produce "add-auth". Since the branch is only used as metadata in the tracking file (not actually created by this script), the impact is cosmetic.
- **Severity:** Low

---

## 17. update_burndown.py

### CA-058: `_fm_val` strip-quote logic doesn't handle escaped quotes

- **File:** `skills/sprint-run/scripts/update_burndown.py`, lines 148-156
- **What it does:** Strips surrounding quotes from frontmatter values.
- **What's wrong:** The check `if len(val) >= 2 and val[0] == val[-1] and val[0] in ('"', "'"):` strips quotes, but doesn't handle escaped quotes. A value like `"she said \"hello\""` would have `val[0] = '"'` and `val[-1] = '"'`, so it would strip to `she said \"hello\"` — leaving the backslash escapes. The sync_tracking `read_tf` function at line 152 does handle `\\"` → `"` replacement, so the two parsers are inconsistent in their quote handling.
- **How to trigger:** A tracking file with escaped quotes in values.
- **Severity:** Low
- **Suggested fix:** Use the same quote-stripping logic as `sync_tracking.read_tf`.

### CA-059: `update_sprint_status` regex replacement is greedy across sections

- **File:** `skills/sprint-run/scripts/update_burndown.py`, lines 113-115
- **What it does:** Replaces the `## Active Stories` section in SPRINT-STATUS.md.
- **What's wrong:** The regex `r"## Active Stories.*?(?=\n## |\Z)"` uses `.*?` (non-greedy) with `re.DOTALL`. Non-greedy means it matches as little as possible, but `(?=\n## |\Z)` is the lookahead for the next section or end-of-file. With `re.DOTALL`, `.*?` matches everything between `## Active Stories` and the next `\n## ` or end-of-file, which is correct. However, if SPRINT-STATUS.md has no other `## ` sections after Active Stories, the `\Z` anchor matches end-of-string, consuming everything to the end. The `.rstrip()` at line 115 then removes trailing whitespace from the replacement. If there's content after the Active Stories section that doesn't start with `## `, it would be consumed.
- **How to trigger:** SPRINT-STATUS.md with non-heading content after the Active Stories section.
- **Severity:** Medium
- **Suggested fix:** Make the section boundary more explicit or use a line-by-line parser.

---

## 18. release_gate.py

### CA-060: `gate_tests` and `gate_build` use `shell=True` with config-derived commands

- **File:** `skills/sprint-release/scripts/release_gate.py`, lines 205, 221
- **What it does:** Runs CI check commands and build commands from config with `shell=True`.
- **What's wrong:** The commands come from `project.toml` which the user controls. The code correctly documents this as intentional (lines 203-204, 219-220). However, if a malicious actor gains write access to `project.toml`, they could inject arbitrary shell commands. Since `project.toml` is a project config file (equivalent to a Makefile or CI config), this is an accepted risk. But it's worth noting that the `shell=True` + `timeout=300` combination means a malicious command has up to 5 minutes of execution time.
- **How to trigger:** Modify `project.toml` to contain `check_commands = ["rm -rf /"]`.
- **Severity:** Low (accepted risk, documented).

### CA-061: `do_release` rollback is incomplete — version commit can be pushed before tag push fails

- **File:** `skills/sprint-release/scripts/release_gate.py`, lines 515-534
- **What it does:** Creates version commit, pushes tag, creates GitHub release.
- **What's wrong:** The flow is: write version → commit → tag → push tag → create release. If `push tag` fails (line 531), `_rollback_commit()` resets local HEAD, but the version bump commit was already made locally. Since there's no `git push` of the commit itself (only the tag is pushed), the commit stays local. But if the user runs `git push` later (or has auto-push configured), the orphan version bump commit would be pushed. The `_rollback_commit` function does `git reset --hard` which undoes the commit, so subsequent pushes would be fine as long as the user doesn't push before the reset.
- **How to trigger:** Tag push fails after commit succeeds.
- **Severity:** Low (rollback handles it correctly).

### CA-062: `_rollback_tag` is defined as a closure inside the `else` branch but called from outside it

- **File:** `skills/sprint-release/scripts/release_gate.py`, lines 536-545, 578
- **What it does:** Defines `_rollback_tag` inside the `if not dry_run: else:` branch.
- **What's wrong:** Wait — let me re-read the code structure. At line 465, `if dry_run:` prints messages. At line 470, `else:` begins the real release flow. `_rollback_tag` is defined at line 536 inside this `else` block. Then at line 578, `_rollback_tag()` is called inside `except RuntimeError`. And at line 548 (the `# 6. Generate release notes` section), we're outside the `else` block. At line 555, `else:` starts again for the non-dry-run path of the release notes section. At line 578, `_rollback_tag()` is called. Since `_rollback_tag` was defined in the first `else` block (line 470), and line 578 is inside a nested `else` block that's only entered when `not dry_run`, the closure is available. This is correct but confusing due to the deeply nested structure.

    But wait — at line 578-579, `_rollback_tag()` and `_rollback_commit()` are called. `_rollback_commit` is also defined inside the first `else` block. In dry-run mode, these functions would not be defined, but lines 578-579 are inside `else:` (not dry_run) at line 555, so they'd only be called when `not dry_run`. This is correct.

    However, there's a subtle issue: at line 578, after a `RuntimeError` from `gh(release_args)`, the code calls `_rollback_tag()` then `_rollback_commit()`. The `_rollback_tag` function at line 537 deletes the tag locally (`git tag -d`) and remotely (`git push --delete origin`). But `_rollback_commit` at line 478 does `git reset --hard pre_release_sha`. If the tag was successfully pushed but the release failed, the local reset would remove the version bump commit, but the tag would point to a commit that no longer exists in the local repo (but exists on remote, and `_rollback_tag` deleted it from remote too). This is correct — both are rolled back.

- **Severity:** N/A (correct but complex)

### CA-063: `write_version_to_toml` regex for finding next section is fragile

- **File:** `skills/sprint-release/scripts/release_gate.py`, lines 283-284
- **What it does:** Finds the end of the `[release]` section by searching for the next section header.
- **What's wrong:** The regex `r"^\[(?![\s\"\'])"` at line 284 matches a `[` at the start of a line, followed by anything that isn't whitespace, `"`, or `'`. This is meant to match section headers like `[project]` but not array lines like `["a", "b"]`. However, it would also match `[a` in code comments or content. In a TOML file, lines outside of multiline values are either comments, section headers, or key=value pairs. A comment like `# [note]` wouldn't match because `#` would be parsed first by the TOML parser, but in `write_version_to_toml`, we're doing raw text manipulation, not TOML parsing. A comment like `# [next]` wouldn't match because `#` is at position 0, not `[`. This is correct.
- **Severity:** N/A

### CA-064: `generate_release_notes` has a variable shadow: `f` used for both file and fix item

- **File:** `skills/sprint-release/scripts/release_gate.py`, lines 360-367
- **What it does:** Iterates over `feats` and `fixes` using `for f in feats:` and `for f in fixes:`.
- **What's wrong:** Both loops use `f` as the loop variable. This is fine in Python (no closure capture issue here), but could cause a subtle bug if someone later adds code after the loops that references `f` — it would reference the last item from the `fixes` loop, not `feats`. Additionally, `f` shadows the builtin `filter`. Actually, `f` doesn't shadow anything meaningful.
- **Severity:** Low (code style)
- **Suggested fix:** Use distinct names like `feat` and `fix` for the loop variables.

### CA-065: First release produces `base_ver == new_ver` when no tags exist and no commits

- **File:** `skills/sprint-release/scripts/release_gate.py`, lines 124-132
- **What it does:** Calculates version from commit log.
- **What's wrong:** When `find_latest_semver_tag()` returns `None`, `base` is `"0.1.0"`. If there are no commits (`parse_commits_since(None)` returns all commits — but in a new repo, that could be many commits). Actually, `parse_commits_since(None)` at line 127 calls `git log --format=...` without a tag range, returning ALL commits ever. The `determine_bump` then calculates from all historical commits. If the repo has 1000 commits, all of them are analyzed. This is correct but slow. For the "no commits" case, `bump_type` is `"none"` and the function returns `(base, base, "none", [])` — version stays at 0.1.0 and `do_release` at line 451 prints "Nothing to release."
- **Severity:** Low (performance on first release of old repos).

---

## 19. check_status.py

### CA-066: `check_ci` uses `conclusion` field which may not be set for in-progress runs

- **File:** `skills/sprint-monitor/scripts/check_status.py`, lines 45-46
- **What it does:** Counts passing and failing runs.
- **What's wrong:** The `passing` count at line 45 checks `conclusion == "success"`. In-progress runs have `conclusion = None`. The `failing` list at line 46 checks `conclusion == "failure"`. The `in_prog` list at lines 47-50 checks `status in ("in_progress", "queued")`. A run that completed with `conclusion = "cancelled"` or `conclusion = "skipped"` would be counted in none of these categories and would be silently ignored in the report.
- **How to trigger:** A cancelled or skipped CI run.
- **Severity:** Low

### CA-067: `_first_error` returns the first line containing "error" (case-insensitive), which may be a false positive

- **File:** `skills/sprint-monitor/scripts/check_status.py`, lines 80-88
- **What it does:** Finds the first error-like line in CI log output.
- **What's wrong:** Searching for "error" case-insensitively would match lines like "Downloading error-handling-1.0.0" or "No errors found" or "error_chain = true". The keywords list (`error`, `failed`, `panicked`, `assert`) is fairly broad.
- **How to trigger:** CI log containing "No errors found" as its first match.
- **Severity:** Low
- **Suggested fix:** Use more specific patterns or check for error-indicating context.

### CA-068: `check_branch_divergence` constructs API URL with unsanitized branch names

- **File:** `skills/sprint-monitor/scripts/check_status.py`, line 239
- **What it does:** Calls `repos/{repo}/compare/{base_branch}...{branch}`.
- **What's wrong:** Branch names are user-controlled strings. A branch name containing `/` or `..` could potentially alter the API path. However, the `gh` CLI handles URL encoding, and the GitHub API's compare endpoint expects branch names with slashes (e.g., `feature/my-branch`). The `gh api` command URL-encodes the arguments. Not a real vulnerability.
- **Severity:** N/A

### CA-069: `write_log` uses `sorted(d.glob(...))` which sorts by full path, then `pop(0)` removes oldest by name

- **File:** `skills/sprint-monitor/scripts/check_status.py`, lines 316-318
- **What it does:** Keeps only the 10 most recent log files.
- **What's wrong:** The files are named `monitor-YYYYMMDD-HHMMSS.log`, so lexicographic sorting equals chronological sorting. The `while len(logs) > MAX_LOGS: logs.pop(0).unlink()` loop removes the oldest (first in sorted order). This is correct.
- **Severity:** N/A

---

## 20. Cross-Cutting Issues

### CA-070: `sys.path.insert(0, ...)` used inconsistently across all skill scripts

- **Files:** All skill scripts under `skills/*/scripts/`
- **What it does:** Inserts the shared `scripts/` directory at the front of `sys.path`.
- **What's wrong:** The pattern `sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent / "scripts"))` is duplicated in 7 scripts. This hardcodes the directory depth (4 levels up from the script). If any script is moved to a different directory level, the import silently fails. Additionally, `sys.path.insert(0, ...)` puts the scripts dir FIRST in the path, which could shadow standard library modules if any script has a conflicting name (e.g., a script named `json.py` would shadow the stdlib `json`).
- **How to trigger:** Name a script `json.py`, `re.py`, `subprocess.py`, etc.
- **Severity:** Medium (fragile architecture)
- **Suggested fix:** Use a package structure with `__init__.py` or a single top-level `setup.py` for importability.

### CA-071: No script uses `if __name__ == "__main__"` guard consistently with imports

- **Files:** `sync_backlog.py`, `check_status.py`
- **What it does:** These scripts import other scripts at module level.
- **What's wrong:** `sync_backlog.py` does `import bootstrap_github` and `import populate_issues` at lines 28-29 (with try/except). `check_status.py` does `from sync_backlog import main as sync_backlog_main` at line 26. When `sync_backlog.py` is imported, it triggers `sys.path.insert(0, ...)` for the setup scripts directory, potentially polluting the import path for the importing script. This side-effect import is fragile.
- **How to trigger:** Import `sync_backlog` from a script that already has a different `scripts/` on `sys.path`.
- **Severity:** Low

### CA-072: Multiple scripts duplicate the "age" / "closed date" formatting logic

- **Files:** `sync_tracking.py` (`_parse_closed`), `update_burndown.py` (`closed_date`), `check_status.py` (`_hours`, `_age`)
- **What it does:** Parses ISO 8601 dates and formats them.
- **What's wrong:** Three different implementations of ISO date parsing across the codebase. `_parse_closed` (sync_tracking.py:104) does `iso.replace("Z", "+00:00")`. `closed_date` (update_burndown.py:35) does the same. `_hours` (check_status.py:153) does the same. These should be a single helper in `validate_config.py`.
- **Severity:** Low (code duplication, not a bug)
- **Suggested fix:** Add a `parse_iso_date` helper to `validate_config.py`.

### CA-073: No script handles `KeyboardInterrupt` gracefully

- **Files:** All scripts
- **What it does:** N/A
- **What's wrong:** If the user presses Ctrl+C during a `gh` API call or file write, the script terminates with a stack trace. For scripts that modify files (e.g., `sync_tracking.py`, `manage_epics.py`), this could leave files in a partially-written state. The `release_gate.py` script is especially vulnerable — an interrupt between tag creation and GitHub release creation would leave an orphan tag.
- **How to trigger:** Ctrl+C during any script execution.
- **Severity:** Medium
- **Suggested fix:** Add `try/except KeyboardInterrupt` in `main()` functions, with cleanup for critical sections.

### CA-074: `gh()` helper has a 30-second timeout that's too short for some operations

- **File:** `scripts/validate_config.py`, line 35
- **What it does:** Runs `gh` CLI commands with a 30-second timeout.
- **What's wrong:** `gh issue create` with a long body, `gh release create` with a binary artifact upload, or `gh api` with `--paginate` on a large dataset could easily exceed 30 seconds. The timeout would raise `RuntimeError` and abort the operation.
- **How to trigger:** Create an issue with a very long body on a slow connection, or paginate through 1000+ results.
- **Severity:** Medium
- **Suggested fix:** Allow callers to pass a custom timeout, or increase the default to 60-120 seconds.

### CA-075: Duplicated `_safe_int` function in manage_epics.py and manage_sagas.py

- **Files:** `scripts/manage_epics.py` line 27, `scripts/manage_sagas.py` line 26
- **What it does:** Extracts leading digits from a string, returning 0 if none found.
- **What's wrong:** Exact same implementation copy-pasted. Should be shared.
- **Severity:** Low (code duplication)
- **Suggested fix:** Move to `validate_config.py` or a shared utils module.

### CA-076: Duplicated `TABLE_ROW` regex pattern

- **Files:** `scripts/manage_epics.py` line 23, `scripts/manage_sagas.py` line 22, `scripts/traceability.py` line 24
- **What it does:** Matches markdown table rows: `^\|\s*(.+?)\s*\|\s*(.+?)\s*\|`
- **What's wrong:** Same pattern defined in three places. These are technically different regexes compiled independently, but they match the same pattern. Also, this pattern only captures the first two cells. A table row with 6 cells would match, but only the first two cells are captured. Any code relying on "all cells" from this regex would silently lose data.
- **Severity:** Low (duplication)

### CA-077: No input validation on file paths passed as CLI arguments

- **Files:** `manage_epics.py`, `manage_sagas.py`
- **What it does:** Accepts file paths from `sys.argv` and reads/writes them.
- **What's wrong:** No path traversal checks. A user could pass `../../../etc/passwd` as the epic file path, and while it wouldn't parse as an epic (no story headings), any write operation would create/modify that file. Since these are CLI tools run by the developer (not a web service), this is an accepted risk. But the `add_story` function would happily append markdown to any file.
- **How to trigger:** `python manage_epics.py add /etc/motd '{}'`
- **Severity:** Low (CLI tool, user-controlled)

### CA-078: `populate_issues.py` `_SPRINT_HEADER_RE` regex uses `\Z` which matches before trailing newline

- **File:** `skills/sprint-setup/scripts/populate_issues.py`, line 58
- **What it does:** Matches sprint sections with `(?=\n### Sprint |\n## |\Z)` lookahead.
- **What's wrong:** `\Z` in Python matches at the very end of the string, but also before a final `\n` at the end of the string. Combined with `re.DOTALL`, the `.*?` before `(?=\n## |\Z)` could match up to the final newline. The actual behavior here is: the content between sprint headers is captured by `(.*?)` with `re.DOTALL`, stopping at the next `### Sprint` or `## ` heading or end of string. This is correct for the intended use case.
- **Severity:** N/A

### CA-079: `validate_config.py` lacks a `_REQUIRED_TOML_SECTIONS` enforcement issue

- **File:** `scripts/validate_config.py`, lines 320-321, 358-362
- **What it does:** Checks that `project`, `paths`, `ci` sections exist.
- **What's wrong:** The required-sections check at lines 358-362 reports missing sections. The required-keys check at lines 365-378 also implicitly checks sections (by traversing the key path). If a section is missing, both checks report an error — the section error and all the key errors within it. This produces redundant error messages. Not a bug, but noisy.
- **Severity:** Low (UX)

### CA-080: `release_gate.py` `calculate_version` returns `(base, base, "none", commits)` when no commits, but `base` is "0.1.0" for first release

- **File:** `skills/sprint-release/scripts/release_gate.py`, lines 128-129
- **What it does:** Returns the current version when there are no new commits.
- **What's wrong:** When `commits` is empty (line 128), it returns `(base, base, "none", commits)`. The `new_version` and `base_version` are the same. In `do_release` at line 451, `bump_type == "none"` causes "Nothing to release." and returns False. This is correct behavior — no commits means no release. But if `base` is "0.1.0" (no previous tag), there might be a first commit that somehow isn't returned by `git log` (e.g., an orphan branch). This edge case would prevent the first release.
- **Severity:** Low

---

## Summary by Severity

### Critical: 0

### High: 1
- **CA-048:** `get_milestone_numbers` `--jq .` + `--paginate` produces invalid JSON for multi-page results

### Medium: 10
- **CA-007:** `extract_sp` regex matches substrings like "wasp" as "sp"
- **CA-008:** `warn_if_at_limit` advisory-only, truncated data silently wrong
- **CA-017:** `remove_generated` prompts stdin without TTY check
- **CA-018:** `check_atomicity` hardcoded threshold too aggressive for common workflows
- **CA-027:** `compute_review_rounds` fetches ALL PRs, truncated at 500
- **CA-031:** `parse_requirements` only scans `reference.md` files
- **CA-032:** Rust test pattern misses `#[tokio::test]` async tests
- **CA-035:** `VOICE_PATTERN` misparses lines with interior quotes
- **CA-037:** `add_story` doesn't check for duplicate story IDs
- **CA-040:** `_format_story_section` crashes on missing keys
- **CA-044:** `update-index` command missing argument validation
- **CA-056:** `get_linked_pr` returns first (oldest) linked PR, not active one
- **CA-059:** `update_sprint_status` regex can eat content after Active Stories section
- **CA-070:** `sys.path.insert(0, ...)` fragile import pattern
- **CA-073:** No scripts handle `KeyboardInterrupt`
- **CA-074:** `gh()` 30-second timeout too short for some operations

### Low: 25
- CA-001, CA-002, CA-003, CA-004, CA-005, CA-006, CA-009, CA-013, CA-014, CA-016, CA-021, CA-023, CA-024, CA-028, CA-029, CA-030, CA-033, CA-036, CA-038, CA-041, CA-042, CA-046, CA-050, CA-055, CA-057, CA-058, CA-064, CA-065, CA-066, CA-067, CA-071, CA-072, CA-075, CA-076, CA-077, CA-079, CA-080

### N/A (false alarms / non-issues): 14
- CA-010, CA-011, CA-012, CA-019, CA-020, CA-022, CA-026, CA-034, CA-039, CA-043, CA-045, CA-049, CA-051, CA-052, CA-053, CA-062, CA-063, CA-068, CA-069, CA-078

---

## Top 10 Recommended Fixes (by impact)

1. **CA-048 (HIGH):** Fix `get_milestone_numbers` pagination — remove `--jq .` or remove `--paginate`.
2. **CA-007 (MEDIUM):** Add `\b` word boundaries to `extract_sp` regex to prevent false matches.
3. **CA-074 (MEDIUM):** Increase `gh()` default timeout to 60s and add optional timeout parameter.
4. **CA-056 (MEDIUM):** Change `get_linked_pr` to prefer open/merged PRs over first-chronological.
5. **CA-059 (MEDIUM):** Fix `update_sprint_status` section replacement to not eat trailing content.
6. **CA-040 (MEDIUM):** Add `.get()` with defaults to `_format_story_section` for robustness.
7. **CA-044 (MEDIUM):** Add missing `sys.argv` length check for `update-index` command.
8. **CA-037 (MEDIUM):** Add duplicate ID check to `add_story` before appending.
9. **CA-032 (MEDIUM):** Extend Rust test pattern to match `#[tokio::test]` and similar.
10. **CA-017 (MEDIUM):** Wrap `input()` in try/except EOFError for non-interactive use.
