# Pass 33 Batch 3: Pipeline & Hooks Audit

## setup_ci.py
- CLEAN. `_yaml_safe_command` properly truncates multiline commands, escapes internal quotes (BH23-227), and quotes YAML metacharacters. Job slug deduplication is correct. Language registry is comprehensive.

## release_gate.py
- BUG: `write_version_to_toml` regex `^(?!#)\[release\]` (line 298) fails to exclude lines like `##[release]` or `x[release]` that aren't valid TOML section headers but also aren't comments. Low severity — these aren't realistic TOML patterns and the function would just malform an already-malformed file.
- BUG: `do_release` line 375: `days_since // 14` was changed from `/` to `//` — wait, that's in `check_status.py`. In `release_gate.py`, `do_release` appends to SPRINT-STATUS.md without atomicity (line 696), but this is append-only to a markdown file so corruption risk is negligible.
- CLEAN otherwise. Rollback logic is thorough (revert-not-force-push for pushed commits, reset for unpushed). Tag existence check (BH23-235) prevents clobbering. Temp file cleanup in `finally` block is correct.

## update_burndown.py
- BUG: `update_sprint_status` regex pattern (line 107) `r"## Active Stories\n(?:(?!\n## )[^\n]*\n)*(?:(?!\n## )[^\n]+\n?)?"` — the negative lookahead `(?!\n## )` checks for `\n##` starting from the current position, but each `[^\n]*\n` match already consumed the preceding content and newline. The pattern actually works because `[^\n]*` matches a line and `\n` matches the newline, then `(?!\n## )` checks if the NEXT line starts with `## `. If the section is at EOF with no trailing newline, the final `(?:(?!\n## )[^\n]+\n?)?` handles it. Verified: CLEAN.
- CLEAN. Proper encoding on all file I/O. `extract_sp` and `kanban_from_labels` are delegated to validate_config.

## check_status.py
- BUG (minor): `check_smoke` rate limiting (line 290-291) uses naive `datetime.now()` while `smoke_test.write_history` also uses naive `datetime.now()`. Consistent within the codebase, but if the system timezone changes or DST transitions occur, the 10-minute rate limit could be off. The rest of `main()` uses `datetime.now(timezone.utc)`. Inconsistency, not a crash bug.
- BUG (minor): `check_integration_debt` line 374 uses naive `datetime.now()` for the same reason. Again consistent with how `smoke_test.py` writes timestamps, but inconsistent with the rest of `check_status.py` which uses UTC.
- BUG (minor): `check_smoke` line 338 catches bare `Exception` — the only `except Exception` in the checks pipeline. The other checks at line 585 intentionally narrow to `(RuntimeError, OSError, ValueError)` per BH24-019. The `check_smoke` internal catch is broader than the outer catch, meaning programming errors inside smoke execution (e.g. TypeError, KeyError) are silently swallowed.
- CLEAN otherwise. CI log truncation (BH21-019), false-positive filtering in `_first_error`, and error narrowing in main loop are all solid.

## review_gate.py
- BUG: `_check_push_single` (lines 130-164) does not include `--delete` or `-d` in its boolean-flag whitelist. For `git push --delete origin main`, the parser treats `--delete` as a flag-with-value, consuming `origin` as its argument. This leaves `main` as positional[0] (the "remote") with no refspecs, so the function returns `"allowed"` instead of `"blocked"`. Someone could delete the base branch and the hook would not prevent it. Fix: add `"--delete", "-d"` to the boolean flags tuple at line 141.
- BUG: `_check_push_single` also missing `--mirror` from the boolean flags. `git push --mirror origin` would consume `origin` as `--mirror`'s value, leaving no positionals, returning `"warn"` instead of analyzing the command. Minor severity since `--mirror` pushes are rare.
- CLEAN otherwise. The `check_merge` function correctly fails closed for `gh pr merge` without a PR number. Compound command splitting via `re.split` on `&&`, `||`, `;` is correct.

## _common.py
- CLEAN. Simple upward directory walk. Falls back to CWD when no config found, which is the correct behavior for non-giles projects. No file writes, no subprocess calls, no security concerns.

## sprint_init.py
- BUG (minor): `_parse_workflow_runs` (line 223) checks `lines[i].startswith("  ")` for multiline block continuation, but this uses a fixed 2-space indentation check. A YAML file with tab indentation or deeper nesting would be mishandled. Low severity — GitHub Actions YAML is almost always 2-space indented, and this is a best-effort heuristic.
- BUG (minor): `detect_story_id_pattern` regex `r"(US-\d{4}|[A-Z]{2,10}-\d+)"` at line 465 matches any 2-10 uppercase letter prefix followed by a dash and digits. This would false-positive on strings like `HTTP-200`, `UTF-8`, `ISO-8601`, etc. in documentation. The pattern then picks the most frequent one, so documentation noise could dominate. Low severity — incorrect story ID pattern in project.toml is user-editable and only informational.
- CLEAN otherwise. Path traversal protection in `_symlink` (BH18-014) is solid. TOML escaping in `_esc` covers all necessary characters. Manifest generation correctly tracks created/symlinked/directory entries.

## Summary

| File | Verdict |
|------|---------|
| setup_ci.py | CLEAN |
| release_gate.py | CLEAN (one theoretical regex edge case) |
| update_burndown.py | CLEAN |
| check_status.py | 2 minor bugs (naive datetime, broad exception catch) |
| review_gate.py | 1 real bug (`--delete` bypass), 1 minor (`--mirror`) |
| _common.py | CLEAN |
| sprint_init.py | 2 minor bugs (YAML heuristic, story ID false positives) |

**Priority fix:** `review_gate.py` `_check_push_single` missing `--delete` in boolean flags — allows `git push --delete origin main` to bypass the hook.
