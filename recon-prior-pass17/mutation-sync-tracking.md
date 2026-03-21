# Mutation Testing: sync_tracking / update_burndown / sync_backlog

**Date:** 2026-03-16
**Baseline:** 385 tests passing (excluding 3 pre-existing failures unrelated to these files)

Pre-existing failures (excluded from mutation runs):
- `TestSyncOne::test_no_changes_when_in_sync` -- `kanban_from_labels` defaults to "dev" when no labels, test expects "todo"
- `TestGetBaseBranch::test_defaults_to_main` / `test_empty_string_defaults_to_main` -- returns "master" not "main"

## Results Summary

| # | File | Function | Mutation | Result | Failures |
|---|------|----------|----------|--------|----------|
| 1 | sync_tracking.py | main() | Flip write guard: `if changes:` -> `if not changes:` (writes when clean, skips when dirty) | **SURVIVED** | 0 |
| 2 | sync_tracking.py | sync_one() | Remove `completed` field update when status is "done" | KILLED | 1 |
| 3 | sync_tracking.py | write_tf() | Remove `_yaml_safe()` call on title field | **SURVIVED** | 0 |
| 4 | sync_tracking.py | get_linked_pr() | Return `None` unconditionally (skip timeline API + fallback) | KILLED | 9 |
| 5 | sync_tracking.py | create_from_issue() | Hardcode status to "dev" instead of `kanban_from_labels(issue)` | KILLED | 3 |
| 6 | update_burndown.py | write_burndown() | Swap `done_sp` and `total_sp` assignments | KILLED | 1 |
| 7 | update_burndown.py | write_burndown() | Remove table header line (`| Story | SP | Status | Completed |`) | **SURVIVED** | 0 |
| 8 | update_burndown.py | update_sprint_status() | Break regex for "Active Stories" section (change to nonexistent section name) | KILLED | 3 |
| 9 | sync_backlog.py | check_sync() | Always return `SyncResult("sync", True, ...)` (bypass debounce/throttle) | KILLED | 7 |
| 10 | sync_backlog.py | hash_milestone_files() | Hash file path instead of file content | KILLED | 2 |

**Score: 7 killed / 10 total = 70% detection rate**
**3 mutations survived**

## Analysis of Survived Mutations

### Mutation 1: Write guard flip in main() -- SURVIVED

The `main()` function in sync_tracking.py guards file writes with `if changes: write_tf(...)`. Flipping this to `if not changes:` means:
- Files with actual changes are NOT written to disk
- Files with no changes ARE (pointlessly) written to disk

**Why it survived:** Unit tests call `sync_one()` directly and verify the returned TF object's fields in memory. They never check that `write_tf()` was actually called after `sync_one()`. The integration test (`test_main_idempotent_sync`) checks stdout output for "Everything in sync" on the second run, but with the flipped guard, the first run's changes are never persisted to disk (so the second run re-detects them as new and creates fresh files via `create_from_issue` instead of syncing existing ones). The integration test happens to still pass because `create_from_issue` writes unconditionally and the output includes "Sync complete".

**Fix needed:** Integration test that:
1. Runs main() with a status change (e.g., issue closed)
2. Reads the tracking file from disk afterward
3. Asserts the file reflects the updated status

### Mutation 3: Remove _yaml_safe() on title -- SURVIVED

Removing the `_yaml_safe()` wrapper from the title field in `write_tf()` means YAML-sensitive characters in titles are written unescaped.

**Why it survived:** The `read_tf()` parser uses regex (`^title:\s*(.+)`) not a YAML library. The greedy `.+` captures everything after `title: `, including colons, hashes, and brackets. The test inputs (`"Feat: Add auth"`, `"[WIP] Feature"`, `"Fix #42 bug"`) all round-trip correctly because the regex handles them fine even without quoting. The quoting is defensive against potential future YAML parser use or edge cases like values starting with `---` or containing newlines.

**Fix needed:** Test with a title that genuinely breaks regex round-trip without quoting. Candidates:
- A title that starts with `---` (would confuse frontmatter parsing)
- A title containing literal newlines (would break single-line regex match)
- Property-based test that exercises `write_tf`/`read_tf` round-trips with adversarial strings

### Mutation 7: Remove burndown table header -- SURVIVED

The markdown table header (`| Story | SP | Status | Completed |`) was removed, leaving only the separator line. The output is still valid-ish markdown (just missing column labels).

**Why it survived:** `test_creates_burndown_file` checks for "Sprint 1 Burndown", "Planned: 8 SP", "Completed: 3 SP", and story IDs -- all in the summary section below the table. No test asserts the table header row exists.

**Fix needed:** Assert that the burndown output contains the table header string `"| Story | SP | Status | Completed |"`.

## Recommendations

1. **High priority:** Add integration test for sync_tracking.main() that verifies file-on-disk state after a sync with changes (Mutation 1).
2. **Medium priority:** Add assertion for burndown table header (Mutation 7) -- simple one-liner.
3. **Low priority:** Add property test for write_tf/read_tf with adversarial title strings (Mutation 3) -- the regex parser is naturally resilient, but _yaml_safe exists for correctness if parsing ever changes.
