# Adversarial Audit: bootstrap_github.py

**File:** `skills/sprint-setup/scripts/bootstrap_github.py` (317 lines)
**Coverage:** 51% (88/179 statements missed)
**Date:** 2026-03-16
**Uncovered lines:** 20-41, 70-71, 90, 113-120, 130-156, 162-168, 204-210, 221-222, 247-252, 267, 285-311, 317

---

## Finding 1: UnboundLocalError in `create_milestones_on_github` fallback path

**File:** `bootstrap_github.py`, line 247
**Severity:** CRITICAL
**Covered by tests:** No (lines 247-252 are uncovered)

When a milestone file has no `# heading` (line 235 regex fails, so `title` stays `None`), the code falls through to line 247:

```python
if title is None:
    sprint_m = re.search(r"Sprint\s+(\d+)", text if mf.is_file() else "")
```

But `text` is only assigned inside the `if mf.is_file():` block (line 234). If the file path exists but `mf.is_file()` returns False (e.g., it's a directory, or a broken symlink), `text` is **never assigned**, and referencing it on line 247 raises `UnboundLocalError`.

Even when the file does exist, the condition `mf.is_file()` on line 247 is redundant -- it was already `True` on line 233, so the `else ""` branch is dead code in that case. But the real danger is when it's a path that fails `is_file()` on both line 233 AND 247: then `text` is completely unbound.

**Impact:** Crash during bootstrap for any milestone path that points to a non-file (directory, broken symlink, `.md` entry that was deleted after `get_milestones()` scanned).

---

## Finding 2: `check_prerequisites` calls `subprocess.run` directly, bypassing `gh()` wrapper

**File:** `bootstrap_github.py`, lines 20-41
**Severity:** MEDIUM
**Covered by tests:** No (lines 20-41 are fully uncovered)

`check_prerequisites()` calls `subprocess.run` three times directly (for `gh --version`, `gh auth status`, `git remote -v`) instead of using the shared `gh()` wrapper from `validate_config.py`. This means:

1. **No timeout protection.** If `gh auth status` hangs (e.g., interactive auth prompt), the process blocks indefinitely. The `gh()` wrapper has a 60-second timeout.
2. **Not testable via FakeGitHub.** All pipeline tests skip `check_prerequisites()` entirely because patching `subprocess.run` would interfere with the real git calls in the same function. This is why lines 20-41 have zero coverage.
3. **`sys.exit(1)` makes it hostile to test.** Hard exits prevent unit testing without process-level isolation.

**Impact:** Untestable function with no timeout protection. If called during CI or automated runs, a hanging `gh auth status` will block indefinitely.

---

## Finding 3: `_parse_saga_labels_from_backlog` hardcodes `backlog_dir` default instead of using config resolver

**File:** `bootstrap_github.py`, lines 130-131
**Severity:** MEDIUM
**Covered by tests:** No (lines 130-156 are fully uncovered)

```python
paths = config.get("paths", {})
backlog_dir = paths.get("backlog_dir", "sprint-config/backlog")
```

The default value `"sprint-config/backlog"` is hardcoded here. After `load_config()` runs, `paths.backlog_dir` is resolved to an **absolute path** (see `validate_config.py` line 634: `config["paths"][key] = str(project_root / val)`). But if `_parse_saga_labels_from_backlog` is called with a raw config dict (before `load_config()` resolves paths), it falls back to a relative path that may not resolve correctly depending on cwd.

Also, `_parse_saga_labels_from_backlog` duplicates the path-resolution logic instead of using `get_milestones()`-style helpers, creating a maintenance burden.

---

## Finding 4: `_parse_saga_labels_from_backlog` pattern fails for real hexwise fixture

**File:** `bootstrap_github.py`, lines 147-154
**Severity:** HIGH
**Covered by tests:** No (lines 130-156 are fully uncovered)

The function parses `backlog/INDEX.md` looking for saga table rows like `| S01 | Walking Skeleton |`. But the hexwise fixture's `backlog/INDEX.md` contains:

```
| Artifact | Path |
|----------|------|
| Milestones | `milestones/` |
| Sagas | `../agile/sagas/` |
```

There are no `S01`/`S02` rows. The regex patterns on lines 147 and 152 will match zero rows, so `create_saga_labels` will print "(none found)" and return.

This means saga labels are **never created** for the hexwise fixture despite it having sagas (S01, S02). The function looks in the wrong place -- it should parse the saga *files* themselves (like `S01-core.md`), not the backlog INDEX which is just a routing table.

**Impact:** Saga labels are silently not created for any project that follows the hexwise-style INDEX format (which is what the skeleton template generates). This is a functional gap, not just a coverage gap.

---

## Finding 5: `create_epic_labels` is never called in pipeline tests

**File:** `bootstrap_github.py`, lines 204-210
**Severity:** MEDIUM
**Covered by tests:** No (lines 204-210 are uncovered)

The `main()` function calls `create_epic_labels(epics_dir)` only when `get_epics_dir(config)` returns a non-None path. But none of the pipeline tests exercise this path because:

1. `test_lifecycle` uses MockProject which may not generate an `epics_dir` path.
2. `test_hexwise_setup.test_full_setup_pipeline` calls individual bootstrap functions but never calls `create_epic_labels`.
3. `test_golden_run` similarly skips it.

The function itself has a subtle issue: the regex `r"(E-\d{4})"` on line 204 requires exactly 4 digits. If any epic file is named `E-01.md` or `E-12345.md`, it will be silently skipped. The hexwise fixture uses `E-0101`, `E-0102` etc. which do match, but this is an implicit coupling to the naming convention.

---

## Finding 6: `create_milestones_on_github` uses `already_exists` string check for idempotency

**File:** `bootstrap_github.py`, line 266-267
**Severity:** MEDIUM
**Covered by tests:** No (line 267 is uncovered)

```python
if "already_exists" in msg:
    print(f"  = {title} (already exists)")
```

The idempotency of milestone creation depends on the GitHub API error message containing the literal string `"already_exists"`. The FakeGitHub implementation (line 387) returns `"Validation Failed: milestone title '...' already exists"` which does contain this substring, but:

1. The actual GitHub API returns a JSON error body with `"errors": [{"code": "already_exists"}]`. The `gh()` wrapper returns `r.stderr.strip()`, so the match depends on `gh` CLI formatting, which could change across `gh` versions.
2. The test for idempotency (`TestBootstrapMilestonesIdempotent`) does exercise this path via FakeGitHub, but the **actual line 267 is still marked as uncovered** in the coverage report, suggesting the FakeGitHub handling may short-circuit differently than expected.

**Impact:** If `gh` CLI changes its error message format, milestone creation will fail noisily instead of being idempotent.

---

## Finding 7: `main()` is completely untested (lines 285-311)

**File:** `bootstrap_github.py`, lines 285-311, 317
**Severity:** LOW
**Covered by tests:** No (lines 285-311 and 317 are uncovered)

The `main()` function is never called by any test. It contains the full orchestration:
- Load config (line 289)
- Print project name (line 292-294)
- Call `check_prerequisites()` (line 295)
- Create all label categories (lines 298-306)
- Create milestones (line 308)

Instead, tests call individual functions directly. This means:
1. The `load_config()` error path on line 290-291 (`except ConfigError: sys.exit(1)`) is untested.
2. The `--help` flag handling on line 285-287 is untested.
3. The orchestration order is untested -- if someone reorders the calls, no test will catch it.

---

## Finding 8: `create_sprint_labels` and `create_saga_labels` are never called in isolation tests

**File:** `bootstrap_github.py`, lines 111-120 (sprint labels), 160-168 (saga labels)
**Severity:** MEDIUM
**Covered by tests:** No (lines 113-120 and 162-168 are uncovered)

`create_sprint_labels` calls `get_milestones(config)` then `_collect_sprint_numbers()`, then creates labels. While `_collect_sprint_numbers` has 3 dedicated tests, the `create_sprint_labels` wrapper that calls it and actually creates the labels is never tested. Similarly, `create_saga_labels` is never tested.

This means:
1. The "no sprints found" path on line 116 is untested.
2. The label name format `sprint:{n}` (line 120) is untested.
3. The label color `0075ca` is untested.
4. The saga label creation loop (lines 167-168) is untested.

---

## Finding 9: No persona found path is untested

**File:** `bootstrap_github.py`, lines 70-71
**Severity:** LOW
**Covered by tests:** No

When `get_team_personas(config)` returns an empty list (no team INDEX.md or no persona rows), lines 70-71 handle this:

```python
print("  (no personas found in team index)")
return
```

This defensive path is never tested. While the code is straightforward, a project with a malformed or empty team INDEX could hit this silently, and the user would only see a print message with no error escalation.

---

## Finding 10: `_collect_sprint_numbers` skips non-files silently (line 90)

**File:** `bootstrap_github.py`, line 90
**Severity:** LOW
**Covered by tests:** No (line 90 is uncovered)

```python
if not mf.is_file():
    continue
```

If a milestone path in the list points to a directory or non-existent file, it's silently skipped with no warning. Given that `get_milestones()` already filters for `.is_file()` and `.suffix == ".md"`, this check is defensive redundancy -- but it means a TOCTOU race (file deleted between `get_milestones()` and `_collect_sprint_numbers()`) would be silently swallowed rather than reported.

---

## Finding 11: `create_milestones_on_github` description extraction is fragile

**File:** `bootstrap_github.py`, lines 239-243
**Severity:** LOW
**Covered by tests:** Partially (the happy path is tested, but edge cases are not)

```python
for line in text.splitlines():
    line = line.strip()
    if line and not line.startswith("#") and not line.startswith("|"):
        description = line
        break
```

This takes the **first non-heading, non-table line** as the milestone description. For the hexwise fixture, this grabs the narrative paragraph. But:

1. If the file starts with blank lines followed by a YAML frontmatter block (`---`), the `---` line itself becomes the description.
2. If there's a blockquote (`> quote`) or bullet list before prose, that becomes the description.
3. The description is not length-limited before being sent to the GitHub API.

---

## Finding 12: `create_milestones_on_github` does not return count of already-existing milestones

**File:** `bootstrap_github.py`, lines 266-267
**Severity:** LOW
**Covered by tests:** No

The function's docstring says "Returns the number of milestones successfully created." When a milestone already exists, it prints a message but does not increment `created`. This is technically correct per the docstring, but callers cannot distinguish between "0 milestones created because they all existed already" (success) and "0 milestones created because all failed" (failure). The `errors` count is only used for a warning print, not returned.

---

## Finding 13: Command injection via milestone title in API call

**File:** `bootstrap_github.py`, lines 254-258
**Severity:** LOW (mitigated by `gh()` wrapper using list args)
**Covered by tests:** Partially

```python
api_args = [
    "api", "repos/{owner}/{repo}/milestones",
    "-f", f"title={title}",
    "-f", f"description={description}",
    "-f", "state=open",
]
```

The `title` comes from parsing the first heading in a milestone file (`heading.group(1).strip()`). The `description` comes from the first non-heading line. Both are user-controlled content from markdown files.

Since `gh()` uses `subprocess.run(["gh", *args], ...)` with list arguments (not shell=True), shell injection is prevented. However, the values are passed as `-f key=value` arguments to `gh api`, which serializes them as JSON fields. If a title contains characters like `"`, `\n`, or `=`, the `-f` flag parsing in `gh` CLI may behave unexpectedly. The `gh` CLI handles this correctly by treating everything after the first `=` as the value, but it's worth noting.

---

## Finding 14: `create_milestones_on_github` returns `created` count but no caller uses it

**File:** `bootstrap_github.py`, line 279
**Severity:** LOW
**Covered by tests:** The return value is tested in `test_lifecycle.py` test_05 (indirectly via milestones list length), but the actual `int` return is never asserted on.

The function returns `created` (int), but `main()` on line 308 calls it without capturing the return value:

```python
create_milestones_on_github(config)  # return value discarded
```

This is a dead-code smell. Either the return value should be used (e.g., for summary output) or it should be removed.

---

## Finding 15: `_parse_saga_labels_from_backlog` regex allows false positives

**File:** `bootstrap_github.py`, lines 147, 152
**Severity:** LOW
**Covered by tests:** No (lines 130-156 are fully uncovered)

Pattern 1: `r"\|\s*(S\d{2})\s*\|\s*(.+?)\s*\|"` -- matches any table row containing a cell with `S` followed by exactly 2 digits. This would false-positive on cells containing strings like "S3D rendering" if they happen to be in a table.

Pattern 2: `r"(S\d{2})[:\s]+(.+?)(?:\s*\|)"` -- even looser, would match `S01` anywhere in a table row followed by text and a pipe. Strings like "Supports S01 format" would match.

---

## Finding 16: `create_milestones_on_github` silently shadows loop variable `line`

**File:** `bootstrap_github.py`, line 240
**Severity:** LOW (Python scoping makes this technically fine, but confusing)
**Covered by tests:** Yes (indirectly through pipeline tests)

```python
for line in text.splitlines():
    line = line.strip()  # shadows the loop variable
```

This reassigns the loop variable inside the loop body. While Python handles this correctly (the `for` re-binds on each iteration regardless), it's a readability issue and could confuse maintenance developers.

---

## Summary

| # | Finding | Severity | Tested |
|---|---------|----------|--------|
| 1 | UnboundLocalError in fallback title path | CRITICAL | No |
| 2 | `check_prerequisites` bypasses `gh()`, no timeout, untestable | MEDIUM | No |
| 3 | Hardcoded default path in `_parse_saga_labels_from_backlog` | MEDIUM | No |
| 4 | Saga label parser looks in wrong place (INDEX vs saga files) | HIGH | No |
| 5 | `create_epic_labels` never exercised in pipeline tests | MEDIUM | No |
| 6 | `already_exists` string check fragile against gh CLI changes | MEDIUM | No |
| 7 | `main()` completely untested | LOW | No |
| 8 | `create_sprint_labels` and `create_saga_labels` never tested | MEDIUM | No |
| 9 | Empty persona list path untested | LOW | No |
| 10 | Non-file milestone path silently skipped | LOW | No |
| 11 | Description extraction fragile for non-standard markdown | LOW | Partial |
| 12 | No way to distinguish "all existed" from "all failed" | LOW | No |
| 13 | User-controlled content in API args (mitigated by list args) | LOW | Partial |
| 14 | Return value of `create_milestones_on_github` never used | LOW | No |
| 15 | Saga label regex allows false positives | LOW | No |
| 16 | Loop variable shadowing in description extraction | LOW | Yes |

**Recommended priorities:**
1. Fix Finding 1 (CRITICAL) immediately -- initialize `text = ""` before the `if mf.is_file()` block.
2. Fix Finding 4 (HIGH) -- rewrite saga label discovery to scan saga files or the sagas_dir, not the backlog INDEX.
3. Add tests for Findings 2, 3, 5, 6, 8 to bring coverage above 80%.
