# Pass 33 Batch 2: Analysis Scripts Audit

## scripts/traceability.py
- CLEAN. Solid structure. `REQ_TABLE_ROW` character class `[\w, –-]` looks odd (en-dash adjacent to hyphen) but Python treats both as literals since `-` is at end of class. `TABLE_ROW` import from validate_config keeps pattern in sync. `parse_stories` blank-line guard at `j > i + 1` (BH27-008 fix) correctly handles short metadata tables.

## scripts/validate_anchors.py
- **BUG (minor): `fix_missing_anchors` adds spurious trailing newline on each run.** Lines 279+292: `split('\n')` on a file ending with `\n` produces a trailing empty string; `"\n".join(lines) + "\n"` then outputs an extra blank line at EOF. Repeated `--fix` runs accumulate blank lines. Fix: strip the trailing empty element before join, or use `splitlines(keepends=True)`.
- **BUG (minor): `_find_heading_line` prefix match is overly broad.** Line 213: `slug.startswith(heading_slug)` without a `_` separator means heading slug "step" matches target slug "step1_foo" (no underscore boundary). The first disjunct `slug.startswith(heading_slug + "_")` already handles the proper case, so the bare `slug.startswith(heading_slug)` catches only cases where the heading slug is a character-level prefix. Only affects `--fix` mode, priority 2 (lower than exact/suffix matches). Risk is low but the condition is broader than documented.

## scripts/sprint_analytics.py
- CLEAN. Post-filters on milestone title (line 102) prevent over-inclusion from `--search`. Dedup check for analytics file uses word boundary `\b` (line 277) to avoid "Sprint 1" matching "Sprint 10". Zero-SP warning (line 69-71) handles the likely-missing-data case. No silent exception swallowing.

## scripts/gap_scanner.py
- CLEAN. `subprocess.run` uses list form (no shell injection risk). Exception from git diff is logged to stderr (line 108), not swallowed. `_path_matches_entry_point` (BH30-001) correctly avoids substring false positives by using stem matching for bare names. Body text matching uses `\b` word boundaries (line 88).

## scripts/sync_backlog.py
- **BUG (minor): `json.loads` not wrapped in try/except at CLI boundary.** Line 286 in `main()` calls `json.loads(alloc_json)` — wait, that's `manage_sagas.py`, not this file. Re-checking: `sync_backlog.py`'s `main()` has no raw JSON parsing from CLI args. `load_state` (line 74) wraps `json.loads` in try/except. Error path at line 237 saves state with `pending_hashes` set by `check_sync`, enabling correct retry on next run — the "state NOT updated" comment is misleading (pending_hashes WAS mutated, but file_hashes was not, which is the correct behavior for retry).
- CLEAN. Debounce/throttle logic is sound. Partial failure path correctly skips hash update to force retry.

## scripts/manage_sagas.py
- **BUG: `main()` CLI does not catch `json.JSONDecodeError`.** Lines 286 and 301: `json.loads(alloc_json)` and `json.loads(voices_json)` are called without try/except. Invalid JSON from the command line produces an unhandled traceback instead of a user-friendly error message. Should wrap in try/except with `sys.exit(1)`.
- **BUG (minor): `update_epic_index` filename parsing assumes E-NNNN format.** Lines 203-206: `parts = md_file.stem.split("-")` then `epic_id = f"{parts[0]}-{parts[1]}"`. If an epic file is named with extra hyphens in the prefix (e.g., `E-01-01-name.md`), `epic_id` would be `E-01` instead of `E-0101`. But this follows the documented convention and `parse_epic` would catch format issues, so risk is low.
