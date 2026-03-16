# Adversarial Audit: update_burndown.py & sprint_teardown.py

Date: 2026-03-16
Files under audit:
- `skills/sprint-run/scripts/update_burndown.py` (63% coverage)
- `scripts/sprint_teardown.py` (72% coverage)

---

## Findings

### update_burndown.py

#### 1. LOGIC BUG: `write_burndown` divides by zero when all issues have 0 SP

**Severity: Low (guarded but misleading)**
**Lines: 48**

When `total_sp == 0`, the ternary falls back to `pct = 0`. This is correct
defensively, but the scenario is real (a sprint of all spikes/research stories
with 0 SP). The burndown output will read "Planned: 0 SP / Completed: 0 SP /
Progress: 0%" which is accurate but uninformative. Not a crash, but it silently
produces a degenerate burndown. The *test* for this (`test_zero_sp_handled`)
only checks one 0-SP story marked "done" -- it does not verify what happens when
multiple 0-SP stories exist in mixed states (done vs not-done), which would
still report 0%.

#### 2. TEST GAP: `build_rows` has zero test coverage

**Severity: Medium**
**Lines: 157-181 (uncovered)**

`build_rows()` is the core transform from GitHub issues to burndown row dicts.
It is called in `main()` but never tested directly. Edge cases that are
untested:
- Issue title with no colon (falls back to full title as `short_title`)
- Issue with no labels (kanban_from_labels returns "todo")
- `extract_sp` returning 0 for malformed label
- `tracking` dict containing a story ID not present in issues (ignored) vs
  issue with no matching tracking entry (uses em-dash defaults)

#### 3. TEST GAP: `load_tracking_metadata` has zero test coverage

**Severity: Medium**
**Lines: 121-141 (uncovered)**

This function reads YAML-ish frontmatter from story tracking files. Untested
scenarios:
- Stories directory does not exist (returns empty dict -- covered by guard, but
  no test verifies this)
- Tracking file with no frontmatter (no `---` delimiters)
- Frontmatter with `pr_number` containing a URL instead of a number
- Frontmatter with quoted values containing escaped characters (the unescape
  logic at line 152 is inherited from sync_tracking but never tested here)
- Multiple tracking files with the same `story:` value (last-write-wins, silently)

#### 4. LOGIC BUG: `_fm_val` regex is injectable via frontmatter key

**Severity: Low**
**Lines: 144-153 (partially uncovered)**

`_fm_val` builds a regex from the `key` parameter using an f-string:
`rf"^{key}:\s*(.+)"`. The `key` values are hardcoded strings ("story",
"implementer", "pr_number") so this is not exploitable in practice. But if
anyone ever passes a key containing regex metacharacters, it would produce
unexpected matches. Defensive fix: `re.escape(key)`.

#### 5. TEST GAP: `main()` is entirely uncovered

**Severity: Medium**
**Lines: 187-240 (uncovered)**

The `main()` function is never tested. This means the following paths have
no coverage:
- Argument parsing (`-h`, `--help`, wrong args, non-digit sprint number)
- `ConfigError` from `load_config()` (exits with code 1, but no test)
- `find_milestone()` returning None (exits with code 1)
- `list_milestone_issues()` returning empty list (exits with code 1)
- The summary print at the end (lines 230-236)

#### 6. STALE DATA: `update_sprint_status` regex may match unintended sections

**Severity: Low**
**Lines: 109**

The regex `## Active Stories[^\n]*\n(?:(?!\n## )[^\n]*\n)*...` matches the
section heading and all lines until the next `## ` heading. If someone adds a
subsection like `### Notes` under Active Stories, it will be consumed and
replaced. This is probably the intended behavior, but it is undocumented and
untested. The existing tests only check flat table content under the heading.

#### 7. EDGE CASE: `write_burndown` creates sprint directories as a side effect

**Severity: Low**
**Lines: 41-42**

`sprint_dir.mkdir(parents=True, exist_ok=True)` creates
`sprints/sprint-{N}/` if it does not exist. This is documented as idempotent
but means calling `write_burndown` with a bogus sprint number (e.g., 999)
will create a phantom directory. No guard validates the sprint number against
known milestones.

#### 8. EDGE CASE: `write_burndown` with empty rows list

**Severity: Low**
**Lines: 45-48**

If `rows` is an empty list (possible if GitHub returns issues but
`build_rows` filters them all out due to malformed titles), the burndown file
will contain a table header with no data rows and "Planned: 0 SP / Progress:
0%". This is technically correct but could mask a real problem where issues
exist but failed to parse.

---

### sprint_teardown.py

#### 9. DESTRUCTIVE: `remove_empty_dirs` swallows all OSError silently

**Severity: Medium**
**Lines: 270-276 (uncovered)**

The `except OSError: pass` on line 275-276 catches *every* OS error during
directory removal, including permission denied (`EACCES`), read-only
filesystem (`EROFS`), and I/O errors. If a directory removal fails for a
reason other than "not empty", the user gets no feedback. The function should
at minimum distinguish `OSError(errno.ENOTEMPTY)` from other errors and log
the unexpected ones.

#### 10. DESTRUCTIVE: `remove_generated` exits silently on EOFError

**Severity: Medium**
**Lines: 243-245 (uncovered)**

When `input()` raises `EOFError` (piped stdin, CI environment, etc.), the
function prints a message to stderr and `break`s. But it does not return the
count of files already removed -- it falls through to `return removed` which
is correct. However, the *remaining* files in the list are silently skipped
with no summary. A user piping `echo "" | python sprint_teardown.py` would
have an incomplete teardown with no clear indication of what was skipped.

#### 11. LOGIC BUG: `print_dry_run` hardcodes `docs/dev-team/sprints` as fallback

**Severity: Low**
**Lines: 170-185 (uncovered)**

The preserved-items section in `print_dry_run` has a hardcoded fallback path
(`project_root / "docs" / "dev-team" / "sprints"`) for the sprints directory.
The TOML parsing at lines 179-183 attempts to read `sprints_dir` from
`project.toml`, but it does raw string splitting (`line.split("=", 1)`) which
will fail on values with inline comments (e.g., `sprints_dir = "foo" # comment`)
or multi-line values. More importantly, the function does NOT use
`validate_config.load_config()` or `get_sprints_dir()` like every other script
does. This is a duplicated, weaker TOML parser that can produce wrong results.

#### 12. LOGIC BUG: `print_dry_run` hardcodes verification paths in `main()`

**Severity: Low**
**Lines: 439-454 (uncovered in main)**

The post-teardown verification in `main()` checks hardcoded paths:
`RULES.md`, `DEVELOPMENT.md`, `docs/dev-team/`, `docs/dev-team/sprints/`.
These are not config-driven. If a project uses different paths (which
`project.toml` supports via `paths.sprints_dir`), the verification will
report false negatives ("MISSING") for files that are perfectly fine
elsewhere.

#### 13. TEST GAP: `check_active_loops` has zero test coverage

**Severity: Medium**
**Lines: 281-305 (uncovered)**

This function shells out to `crontab -l` and parses the output. Never tested.
Edge cases:
- `crontab -l` returns non-zero when no crontab exists (prints "no crontab
  for user" to stderr) -- the `returncode == 0` check handles this, but
  untested
- The keyword list does not include `giles` or the actual plugin name
- `subprocess.TimeoutExpired` is caught but the timeout is 5 seconds, which
  could slow teardown on a hung crontab

#### 14. TEST GAP: `print_dry_run` has zero test coverage

**Severity: Medium**
**Lines: 123-210 (uncovered)**

The entire dry-run display function is untested. It contains:
- Path relative_to() calls that can raise ValueError if paths are not
  relative (line 147, 156, 164, 189, 197)
- The TOML-parsing fallback (finding 11)
- The active-loops check integration
- Truncation of symlink targets (lines 193-202)

#### 15. TEST GAP: `main()` missing-config-dir-as-file path untested

**Severity: Low**
**Lines: 369-371 (uncovered)**

The branch where `sprint-config` exists but is a file (not a directory) is
never tested. This would be a very unusual situation but the code handles it
with `sys.exit(1)`.

#### 16. TEST GAP: `main()` empty config dir fast path untested

**Severity: Low**
**Lines: 378-385 (uncovered)**

When `sprint-config/` exists but contains zero files and zero directories
(other than itself), `main()` attempts to `rmdir()` it directly. This path
is untested. The `OSError` catch at line 383-384 handles the case where rmdir
fails, but there is no test verifying either the success or failure branch.

#### 17. LOGIC BUG: `classify_entries` manifest lookup uses relative paths inconsistently

**Severity: Medium**
**Lines: 48-56 (partially uncovered), 72-75**

The manifest stores paths relative to `config_dir` (e.g., `"team/INDEX.md"`).
The lookup at line 75 computes `rel = str(entry.relative_to(config_dir))`.
This works on Unix but on Windows, `relative_to()` uses backslashes while
the manifest (written by `json.dumps`) uses forward slashes. This means
manifest-based classification would silently fail on Windows, falling through
to the `name in generated_names` check. Not a bug on the target platform
(macOS/Linux) but a portability hazard.

More critically: the manifest's `generated_files` list is populated from
`self.created` entries that are formatted as `"  written   team/INDEX.md"` --
the manifest builder parses these with `entry.split(None, 1)[1]` to extract
the path. But if the path itself contains whitespace, this parsing breaks.

#### 18. LOGIC BUG: `collect_directories` considers config_dir removable even with unknowns

**Severity: Low**
**Lines: 98-99**

`collect_directories()` always includes `config_dir` in the returned list.
In `print_dry_run()` (line 160), there is a filter:
`removable = [d for d in directories if d != config_dir or not unknown]`.
But in the actual teardown (`main()`), `remove_empty_dirs(directories, ...)`
is called with the *full* list including `config_dir`. If all symlinks and
generated files are removed but unknown files remain, `remove_empty_dirs`
will attempt to remove `config_dir` but fail (it's not empty). This is
harmless because `d.iterdir()` catches it, but it means the "directories
removed" count may be misleading -- the user sees `config_dir` listed as a
candidate in dry-run but it silently fails in execution.

#### 19. TEST GAP: `remove_symlinks` error path untested

**Severity: Low**
**Lines: 222-223 (uncovered)**

The `OSError` handler when `os.unlink()` fails is never tested. This would
trigger on permission errors, read-only filesystems, or if the symlink was
already removed by another process between classification and removal.

#### 20. TEST GAP: `remove_generated` error path untested

**Severity: Low**
**Lines: 260-261 (uncovered)**

Same as finding 19 -- the `OSError` handler in `remove_generated()` when
`os.unlink()` fails is never tested.

#### 21. EDGE CASE: `symlink_display` can raise if symlink is broken or outside project root

**Severity: Low**
**Lines: 116-120**

`os.readlink(symlink)` works on broken symlinks (returns the target path
string). But `symlink.relative_to(project_root)` will raise `ValueError` if
the symlink is somehow outside the project root. This is called from
`print_dry_run` which has no try/except around it.

#### 22. STATE BUG: `update_sprint_status` regex replacement can duplicate trailing newlines

**Severity: Low**
**Lines: 111**

`re.sub(pattern, new_table.rstrip() + "\n", text)` replaces the matched
section. If the original text had extra blank lines after the Active Stories
table, those blank lines are consumed by the regex match. But the replacement
adds exactly one `\n`. Over multiple runs, this is *idempotent* (good). But
if the section is followed immediately by another `##` heading with no blank
line separator, the replacement will produce `| row |\n## Other` with no
blank line between them. The tests don't verify blank-line preservation
between sections.

#### 23. PROCESS BUG: Teardown does not check for dirty git state

**Severity: Medium**
**Lines: 344-475**

`main()` never checks if the working tree has uncommitted changes to files
inside `sprint-config/`. If a user has modified `project.toml` or other
config files and not committed, teardown will delete them without warning.
The `--dry-run` mode shows what will be removed but does not flag dirty state.
For a tool that claims "safe removal," checking `git status sprint-config/`
before destructive operations would be prudent.

---

## Summary

| # | File | Severity | Category | Lines |
|---|------|----------|----------|-------|
| 1 | update_burndown | Low | Edge case | 48 |
| 2 | update_burndown | Medium | Test gap | 157-181 |
| 3 | update_burndown | Medium | Test gap | 121-141 |
| 4 | update_burndown | Low | Defensive code | 144-153 |
| 5 | update_burndown | Medium | Test gap | 187-240 |
| 6 | update_burndown | Low | Edge case | 109 |
| 7 | update_burndown | Low | Side effect | 41-42 |
| 8 | update_burndown | Low | Edge case | 45-48 |
| 9 | sprint_teardown | Medium | Swallowed error | 270-276 |
| 10 | sprint_teardown | Medium | Silent skip | 243-245 |
| 11 | sprint_teardown | Low | Hardcoded path | 170-185 |
| 12 | sprint_teardown | Low | Hardcoded path | 439-454 |
| 13 | sprint_teardown | Medium | Test gap | 281-305 |
| 14 | sprint_teardown | Medium | Test gap | 123-210 |
| 15 | sprint_teardown | Low | Test gap | 369-371 |
| 16 | sprint_teardown | Low | Test gap | 378-385 |
| 17 | sprint_teardown | Medium | Portability/parsing | 48-56, 72-75 |
| 18 | sprint_teardown | Low | Logic | 98-99, 160 |
| 19 | sprint_teardown | Low | Test gap | 222-223 |
| 20 | sprint_teardown | Low | Test gap | 260-261 |
| 21 | sprint_teardown | Low | Edge case | 116-120 |
| 22 | update_burndown | Low | Edge case | 111 |
| 23 | sprint_teardown | Medium | Process safety | 344-475 |

**Totals:** 23 findings. 8 Medium, 15 Low. Zero High/Critical.

**Priority fixes:**
1. Findings 2, 3, 5: Write tests for `build_rows`, `load_tracking_metadata`, and `main()` -- these are the core uncovered logic paths in update_burndown.
2. Finding 9: Distinguish "not empty" from other OSErrors in `remove_empty_dirs`.
3. Finding 23: Add a git-dirty check before destructive teardown operations.
4. Finding 13, 14: Test `check_active_loops` and `print_dry_run` to cover the remaining 28% of sprint_teardown.
