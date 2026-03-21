# Coverage Holes Audit

Coverage run: `python -m pytest tests/ --cov=scripts --cov=skills --cov-report=term-missing`
773 passed, overall 85%. Audit date: 2026-03-16.

Bottom 6 modules examined below.

---

## 1. test_coverage.py — 68% (31/96 lines uncovered)

### Lines 51, 87-88: ValueError fallback in scan_project_tests

```
87  except ValueError:
88      parts = test_file.parts
```

- **Classification: OK**
- What: `relative_to(root)` raises ValueError if the file is not under root. This is a defensive guard for an edge case that shouldn't happen with `root.glob()`.
- Scenario: Only reachable if glob somehow returns a path not relative to root (shouldn't happen in practice).
- Bug risk: None. The fallback is correct.
- Test needed: No.

### Lines 142-143: slug_re match in check_test_coverage

```
141  if slug_re and slug_re.search(impl_name):
142      matched.add(tc_id)
143      break
```

- **Classification: IMPORTANT**
- What: Secondary fuzzy matching — when the full normalized TC ID doesn't match, it tries just the slug portion (e.g., "par_001" from "tc_par_001").
- Scenario: A test function named `test_par_001_parsing` would match TC-PAR-001 only via this slug path.
- Bug risk: If the slug regex is wrong, planned tests would appear as "missing" even when they have matching implementations. The 4-char minimum guard (line 134) could incorrectly exclude short slugs.
- Test needed: Yes — a test that exercises the slug fallback path to verify fuzzy matching works for non-trivial cases.

### Lines 158-181: format_report function (entire body)

```
158-181  format_report()
```

- **Classification: IMPORTANT**
- What: The entire `format_report()` function that generates the markdown coverage report is untested. Includes conditional sections for "Implemented Test Functions" and "Planned Tests (Not Yet Matched)".
- Scenario: Called by `main()` and by any skill that wants a human-readable coverage report.
- Bug risk: Formatting bugs would produce garbled output. The `planned_details` key lookup (line 177) could KeyError if the dict structure changes.
- Test needed: Yes — at least one test with both implemented and missing tests to verify the output format.

### Lines 191-206, 210: main() function

```
191-206  main()
210      main()
```

- **Classification: MAIN-ONLY**
- What: CLI orchestration: loads config, finds test_plan_dir, calls check_test_coverage, prints report.
- Bug risk: Low. The interesting logic is in the functions it calls.
- Test needed: No (CLI wrapper).

---

## 2. bootstrap_github.py — 71% (57/194 lines uncovered)

### Lines 20-41: check_prerequisites (entire function)

```
20-41  check_prerequisites()
```

- **Classification: MAIN-ONLY**
- What: Runs `gh --version`, `gh auth status`, `git remote -v` and exits if any fail.
- Bug risk: Low — straightforward subprocess checks.
- Test needed: No (real CLI interaction).

### Lines 70-71: No-personas guard in create_persona_labels

```
70  print("  (no personas found in team index)")
71  return
```

- **Classification: OK**
- What: Early return when team INDEX.md has no persona rows.
- Bug risk: None.
- Test needed: No.

### Line 90: Milestone file not-found guard in _collect_sprint_numbers

```
90  continue
```

- **Classification: OK**
- What: Skips non-existent milestone files during sprint number collection.
- Bug risk: None — defensive guard.
- Test needed: No.

### Lines 113-120: create_sprint_labels (full function body)

```
113-120  create_sprint_labels()
```

- **Classification: IMPORTANT**
- What: Iterates sprint numbers from `_collect_sprint_numbers()` and creates `sprint:N` labels. Includes a "no sprints found" guard (lines 115-117).
- Scenario: Called during GitHub bootstrap to create sprint labels.
- Bug risk: If `_collect_sprint_numbers` returns wrong numbers, labels would be wrong. The sorted() iteration means labels are created in order, but there's no deduplication beyond what the set provides.
- Test needed: Moderate — the logic is thin (delegates to `_collect_sprint_numbers` + `create_label`), but verifying the label naming format would catch regressions.

### Line 135: INDEX.md not-found guard in _parse_saga_labels_from_backlog

```
135  return []
```

- **Classification: OK**
- What: Returns empty list when backlog/INDEX.md doesn't exist.
- Test needed: No.

### Lines 145, 149-150, 154: Saga parsing branches in _parse_saga_labels_from_backlog

```
145  continue  (line doesn't start with |)
149  sagas.append(...)  (Pattern 1 match)
150  continue
154  sagas.append(...)  (Pattern 2 match)
```

- **Classification: IMPORTANT**
- What: The two regex patterns for extracting saga IDs from the backlog INDEX table. Pattern 1 handles `| S01 | Walking Skeleton |` format, Pattern 2 handles embedded `S01: Walking Skeleton` format.
- Scenario: These are the core extraction paths for saga labels from backlog files.
- Bug risk: If these regexes are wrong, saga labels won't be created during bootstrap. Pattern 2 is particularly fragile — the `(?:\s*\|)` lookahead could miss edge cases.
- Test needed: Yes — both patterns need coverage with representative INDEX.md content.

### Lines 180-181, 184-185: Saga label fallback (scan saga files directly)

```
180  except (OSError, IndexError):
181      saga_name = m.group(2).replace("-", " ").title()
184  print("\nSaga labels: (none found)")
185  return
```

- **Classification: IMPORTANT**
- What: Lines 180-181 are the error fallback when reading a saga file heading fails (uses filename-based title). Lines 184-185 are the "no sagas at all" path.
- Scenario: Line 180-181: saga file exists but is empty or unreadable. Line 184-185: no sagas found in INDEX or saga files.
- Bug risk: Line 181 could produce weird titles if the filename pattern doesn't match expectations (e.g., `S01-my_weird-saga` becomes "My Weird Saga" via `.title()` but hyphens become spaces first).
- Test needed: Yes for 180-181 (error resilience). No for 184-185 (simple guard).

### Lines 224-230: create_epic_labels (full function body)

```
224-230  create_epic_labels()
```

- **Classification: IMPORTANT**
- What: Scans epics directory for files matching `E-NNNN` pattern and creates `epic:E-NNNN` labels.
- Scenario: Called when `epics_dir` is configured. Creates labels needed for issue tagging.
- Bug risk: The regex `(E-\d{4})` in `f.stem` could miss files with extra segments (e.g., `E-0101-parsing.md` stem is `E-0101-parsing`, the regex matches `E-0101` which is correct). Low risk.
- Test needed: Moderate — a basic test would confirm the label naming pattern.

### Lines 241-242: Milestone creation error counter

```
241  print(f"  = {title} (already exists)")
242  (implicit: fall through without incrementing errors)
```

- **Classification: OK**
- What: Already-exists detection in milestone creation. Not a functional gap.
- Test needed: No.

### Line 270: Fallback title from filename when milestone file has no heading

```
270  title = f"Sprint {sprint_m.group(1)}"
```

- **Classification: OK**
- What: Fallback milestone title when the heading can't be parsed.
- Test needed: No.

### Line 288: Error handling in milestone creation (non-already_exists error)

```
288  print(f"  = {title} (already exists)")
```

- **Classification: OK**
- What: Already-exists milestone handling (idempotent skip).
- Test needed: No.

### Lines 318-332, 338: main() function

```
318-332  main()
338      main()
```

- **Classification: MAIN-ONLY**
- What: CLI orchestration: load config, call all create_* functions, print summary.
- Test needed: No.

---

## 3. populate_issues.py — 76% (77/316 lines uncovered)

### Lines 39-43: check_prerequisites (entire function)

```
39-43  check_prerequisites()
```

- **Classification: MAIN-ONLY**
- What: `gh auth status` check, exits on failure.
- Test needed: No.

### Lines 116-119: Row regex compilation fallback in _build_row_regex

```
116  except re.error as exc:
117      print(f"Warning: invalid story_id_pattern ...")
118                  ...
119      return _DEFAULT_ROW_RE
```

- **Classification: OK**
- What: Fallback to default regex when the custom pattern (that passed `_safe_compile_pattern`) still fails when embedded in the full row regex.
- Scenario: Pattern like `PROJ-\d{4}` passes safety check alone but fails when embedded (theoretically possible with complex patterns).
- Bug risk: Low — the double-validation means this is very unlikely. But if hit, it correctly falls back.
- Test needed: No.

### Lines 135-136: Missing milestone file warning

```
135  print(f"  Warning: Milestone file not found: {mf}")
136  continue
```

- **Classification: OK**
- What: Skips non-existent milestone files with a warning.
- Test needed: No.

### Lines 143-145: Duplicate story ID warning

```
143  print(f"  Warning: duplicate story ID {sid} ...")
144                  ...
145  return
```

- **Classification: IMPORTANT**
- What: Detects duplicate story IDs across milestone files and skips the duplicate.
- Scenario: Two milestone files both contain US-0001. Without this guard, duplicate GitHub issues would be created.
- Bug risk: The guard is correct, but it's untested. If this code were accidentally removed, the `seen_ids` set would still prevent adding to `stories`, but the warning would be lost. More importantly, the `return` on line 145 is inside the nested `_add_story` closure — if it were changed to `continue` by mistake, the story would still be added.
- Test needed: Yes — verify that duplicate IDs in input produce only one story in output.

### Lines 164-166: Whole-file scanning fallback (no sprint sections)

```
164  sprint_num = _infer_sprint_number(mf, content)
165  for row in row_re.finditer(content):
166      _add_story(row, sprint_num, mf)
```

- **Classification: IMPORTANT**
- What: When a milestone file has no `### Sprint N:` sections, falls back to scanning the entire file for story rows and infers a sprint number.
- Scenario: Simple milestone files that have stories in a flat table without sprint section headers.
- Bug risk: `_infer_sprint_number` could return the wrong number, causing stories to be assigned to the wrong sprint/milestone. If both content and filename inference fail, defaults to sprint 1 — could mis-assign stories.
- Test needed: Yes — at least one test with a flat milestone file (no sprint sections).

### Lines 206-209: _build_detail_block_re fallback

```
206  try:
207      return re.compile(...)
208  except re.error:
209      pass
```

- **Classification: OK**
- What: Fallback to default detail block regex on compilation error.
- Test needed: No.

### Line 225: parse_detail_blocks bounds check

```
225  break
```

- **Classification: OK**
- What: Guard against malformed split results (incomplete group of 3 elements).
- Test needed: No.

### Line 290: enrich_from_epics early return (no epics_dir found)

```
290  return stories
```

- **Classification: OK**
- What: Skips enrichment when epics directory doesn't exist.
- Test needed: No.

### Line 324: New story from epic (not in milestone table)

```
324  new_stories.append(ps)
```

- **Classification: IMPORTANT**
- What: When a story appears in an epic file but not in any milestone table, it's added as a new story.
- Scenario: Epic files can introduce stories that weren't in the original milestone tables. This is the "additive enrichment" path.
- Bug risk: If sprint inference fails (returns 0), the BH-011 guard on line 316-322 prevents orphaned issues. But if sprint inference returns a wrong non-zero number, the story gets created with the wrong sprint.
- Test needed: Yes — verify that stories from epics that don't exist in milestones are correctly added.

### Line 335: get_existing_issues non-list guard

```
335  raise RuntimeError(...)
```

- **Classification: CRITICAL**
- What: Validates that `gh_json` returns a list. If GitHub returns unexpected JSON (e.g., an error object), this prevents silently processing garbage data.
- Scenario: GitHub API returns a JSON object instead of array (authentication error, rate limiting).
- Bug risk: Without this check, iterating a non-list would either crash with a confusing error or silently produce no results — leading to duplicate issue creation.
- Test needed: Yes — verify that a non-list response raises RuntimeError.

### Lines 357, 359-361: get_milestone_numbers error handling

```
357  raise RuntimeError(...)  (non-list response)
359  except (RuntimeError, KeyError) as exc:
360      print(f"Error: could not fetch milestones: {exc}")
361      raise
```

- **Classification: CRITICAL**
- What: Validates milestone API response and handles missing keys. If milestone data is corrupt (e.g., a milestone without a "title" or "number" key), the KeyError is caught and re-raised.
- Scenario: GitHub API returns milestones with unexpected schema.
- Bug risk: Without the type check on line 357, a non-list response would crash in the dict comprehension on line 358. Without KeyError handling, a malformed milestone would crash the entire run.
- Test needed: Yes — verify both the type guard and the KeyError path.

### Line 378: Milestone file not-found guard in build_milestone_title_map

```
378  continue
```

- **Classification: OK**
- Test needed: No.

### Lines 389, 397: Duplicate sprint-milestone mapping warnings

```
389  print(f"Warning: Sprint {sn} mapped to ...")
397  print(f"Warning: Sprint {num} mapped to ...")
```

- **Classification: IMPORTANT**
- What: Warns when two different milestone files claim the same sprint number, mapping it to different titles. Uses "last wins" semantics.
- Scenario: Two milestone files both contain `### Sprint 1:` sections but have different `# heading` titles.
- Bug risk: The warning fires but the behavior is "last file wins" — could silently assign stories to the wrong milestone.
- Test needed: Yes — verify the warning fires and the last-wins behavior is correct.

### Lines 469-471: create_issue error path

```
469  except RuntimeError as exc:
470      print(f"  ! {story.story_id}: {exc}")
471      return False
```

- **Classification: IMPORTANT**
- What: When `gh issue create` fails (network error, permission error, etc.), logs the error and returns False.
- Scenario: GitHub API failure during issue creation.
- Bug risk: The error is printed but not re-raised — the script continues creating other issues. If the failure is transient (rate limiting), some issues are created and others aren't, leading to partial state.
- Test needed: Moderate — the behavior is correct (continue on individual failure), but worth testing to confirm the False return is handled by the caller.

### Lines 483-531, 535: main() function

```
483-531  main()
535      main()
```

- **Classification: MAIN-ONLY**
- What: Full CLI orchestration: config loading, milestone parsing, enrichment, duplicate checking, issue creation loop, summary.
- Test needed: No.

---

## 4. update_burndown.py — 75% (25/102 lines uncovered)

### Line 133: _fm_val None check (already covered by delegation)

```
133  continue  (no frontmatter match)
```

- **Classification: OK**
- What: Skips tracking files without YAML frontmatter.
- Test needed: No.

### Lines 198-233: main() function (entire body)

```
198-233  main()
```

- **Classification: MAIN-ONLY**
- What: CLI orchestration: parse sprint number from argv, load config, query GitHub milestone, build rows, write burndown/status files, print summary.
- Scenario: `python update_burndown.py 3`
- Bug risk: Lines 208-214 are notable — if `find_milestone()` returns None (no matching GitHub milestone), the script exits with an error. Lines 216-222: if `list_milestone_issues()` returns empty, the script exits. These are reasonable guards.
- Test needed: No (CLI wrapper). The interesting logic (build_rows, write_burndown, update_sprint_status) is tested through the library functions.

### Line 240: `if __name__ == "__main__"` guard

```
240  main()
```

- **Classification: MAIN-ONLY**
- Test needed: No.

---

## 5. sprint_teardown.py — 76% (75/311 lines uncovered)

### Lines 52-56: Manifest parsing in classify_entries

```
52  try:
53      manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
54      manifest_files = set(manifest.get("generated_files", []))
55  except (json.JSONDecodeError, OSError):
56      pass
```

- **Classification: IMPORTANT**
- What: Reads `.sprint-init-manifest.json` to precisely classify generated files. On error, falls back to the `generated_names` set.
- Scenario: Manifest exists but is corrupted JSON, or has wrong permissions.
- Bug risk: If the manifest is corrupt, the fallback to `generated_names` could misclassify files — some generated files not in the hardcoded set would be classified as "unknown" and skipped during teardown, leaving sprint-config partially removed.
- Test needed: Yes — test with a corrupted manifest file to verify fallback behavior.

### Lines 112-113: resolve_symlink_target error handling

```
112  except (OSError, ValueError):
113      return None
```

- **Classification: OK**
- What: Returns None for broken or error-prone symlinks.
- Test needed: No.

### Lines 180-185: Dry-run print — reading sprints_dir from project.toml

```
180  val = line.split("=", 1)[1].strip().strip('"').strip("'")
181  candidate = project_root / val
182  if candidate not in sprints_candidates:
183      sprints_candidates.insert(0, candidate)
184  except OSError:
185      pass
```

- **Classification: OK**
- What: Best-effort reading of sprints_dir from project.toml for the dry-run display.
- Bug risk: None — display only.
- Test needed: No.

### Lines 189-190: Sprint tracking display in dry run

```
189  print(f"  {sp.relative_to(project_root)}/  (sprint tracking data)")
190  break
```

- **Classification: OK**
- What: Display-only in dry run.
- Test needed: No.

### Line 202: Many-symlink-targets truncation in dry run

```
202  print(f"  ... ({len(symlinks) - 3} more symlink targets)")
```

- **Classification: OK**
- What: Display formatting when more than 3 symlink targets exist.
- Test needed: No.

### Lines 222-223: Symlink removal error path

```
222  except OSError as e:
223      print(f"  ✗ failed to remove {s.relative_to(project_root)}: {e}")
```

- **Classification: IMPORTANT**
- What: Error handling when `os.unlink()` fails for a symlink (permissions, filesystem issues).
- Scenario: Symlink is on a read-only filesystem or has restrictive permissions.
- Bug risk: The function continues but returns a count that doesn't include the failed removal. If the caller relies on the count for verification, partial failures could be missed.
- Test needed: Moderate — mocking a permission error would verify the count is correct.

### Lines 243-245: EOFError in interactive prompt

```
243  except EOFError:
244      print("  Non-interactive mode ...")
245      break
```

- **Classification: IMPORTANT**
- What: When running non-interactively (piped input, CI), `input()` raises EOFError. The handler breaks the loop, leaving remaining generated files in place.
- Scenario: `echo "" | python sprint_teardown.py` or running in a CI pipeline without --force.
- Bug risk: Generated files that haven't been prompted yet are silently skipped. The user isn't told which files were left behind.
- Test needed: Yes — verify that EOFError terminates gracefully and reports what was skipped.

### Lines 260-261: Generated file removal OSError

```
260  except OSError as e:
261      print(f"  ✗ failed to remove {rel}: {e}")
```

- **Classification: OK**
- What: Error handling for individual generated file removal failure.
- Test needed: No (similar to symlink error path).

### Lines 275-279: Directory removal error handling (BH-012)

```
275  except OSError as e:
276      import errno
277      if e.errno not in (errno.ENOTEMPTY, errno.ENOENT):
278          print(f"  ✗ cannot remove {d}: {e}", file=sys.stderr)
279          (implicit: swallow ENOTEMPTY/ENOENT)
```

- **Classification: IMPORTANT**
- What: Only reports unexpected OS errors during directory removal. ENOTEMPTY (dir not empty) and ENOENT (already gone) are silently ignored.
- Scenario: A permission error or filesystem corruption during directory cleanup.
- Bug risk: The errno check is correct, but the `import errno` inside the except block is unusual. If os.walk yields a stale path and the rmdir raises an unexpected error, this correctly reports it. The inline import is fine but could be moved to module level.
- Test needed: Moderate — test with a directory that can't be removed (e.g., permission denied).

### Lines 298-304: Cron entry detection in check_active_loops

```
298  for line in result.stdout.splitlines():
299      line_lower = line.lower()
300      if any(kw in line_lower for kw in [...]):
301-302              ...
303-304      findings.append(...)
```

- **Classification: OK**
- What: Scans crontab for sprint-related entries. Best-effort detection.
- Bug risk: None — informational only.
- Test needed: No.

### Lines 315-322: Active loop cleanup hints (truthy branch)

```
315  print("  Active sprint-related scheduled tasks found:")
316  for finding in active_loops:
317      print(finding)
...
322      print("    /loop stop")
```

- **Classification: OK**
- What: Display hints when active loops are found.
- Test needed: No.

### Lines 351-352: Help flag in main

```
351  print(__doc__.strip())
352  sys.exit(0)
```

- **Classification: OK**
- Test needed: No.

### Lines 361-364: Custom project_root from CLI arg

```
361  candidate = Path(arg)
362  if candidate.is_dir():
363      project_root = candidate.resolve()
364      break
```

- **Classification: IMPORTANT**
- What: Allows passing a custom project root as a positional argument to teardown.
- Scenario: `python sprint_teardown.py /path/to/project`
- Bug risk: If a non-existent path is passed, it falls through silently and uses cwd instead. Could tear down the wrong project's config.
- Test needed: Yes — verify that a custom project root is respected.

### Lines 373-374: sprint-config is not a directory

```
373  print(f"sprint-config exists but is not a directory: {config_dir}")
374  sys.exit(1)
```

- **Classification: OK**
- What: Guard against sprint-config being a file instead of directory.
- Test needed: No.

### Lines 382-388: Empty sprint-config handling

```
382  print("sprint-config/ is empty. Removing it.")
383  try:
384      config_dir.rmdir()
385      print("  ✓ removed sprint-config/")
386  except OSError as e:
387      print(f"  ✗ could not remove sprint-config/: {e}")
388  sys.exit(0)
```

- **Classification: OK**
- What: Handles the edge case where sprint-config/ exists but is empty.
- Test needed: No.

### Lines 424-425: Phase 1 symlink removal print

```
424  print(f"Removing {len(symlinks)} symlinks:")
425  sym_count = remove_symlinks(symlinks, project_root)
```

- **Classification: OK**
- Test needed: No (display).

### Lines 434, 438-440: Phase 2/3 execution

```
434  gen_count = 0  (no generated files path)
438  print("\nUnknown files (skipped — remove manually if desired):")
439  for u in unknown:
440      print(f"  {u.relative_to(project_root)}")
```

- **Classification: OK**
- What: Display unknown files during execution.
- Test needed: No.

### Lines 450-458: Phase 5 verify targets

```
450  if target and target.exists():
451      try:
452          target.relative_to(project_root)
453      except ValueError:
454          pass
455-456  ...
457      print(f"  ✗ {target} — MISSING (was target of {symlink_path.name})")
458      all_ok = False
```

- **Classification: IMPORTANT**
- What: Post-teardown verification that symlink targets still exist. If a symlink target is gone, this flags it as MISSING.
- Scenario: A symlink points to a file that was also under sprint-config/ (shouldn't happen with proper setup, but could with manual edits).
- Bug risk: If a symlink target was accidentally deleted during teardown (shouldn't happen since symlinks are unlinked, not targets), this would detect it but the damage is already done.
- Test needed: Moderate — testing the verification step would confirm it catches missing targets.

### Lines 466-467: Missing RULES.md/DEVELOPMENT.md check

```
466  print(f"  {name}  ✗ MISSING")
467  all_ok = False
```

- **Classification: OK**
- What: Post-teardown verification that key project files still exist.
- Test needed: No (verification display).

### Lines 471-472, 476: Sprint dir verification

```
471  count = len(list(dev_team.glob("*.md")))
472  print(f"  docs/dev-team/  ✓ {count} files intact")
476  print("  docs/dev-team/sprints/  ✓ exists (tracking data preserved)")
```

- **Classification: OK**
- Test needed: No (display).

### Lines 487, 497: Summary + __name__ guard

```
487  print(f"  {len(unknown)} unknown files skipped")
497  main()
```

- **Classification: MAIN-ONLY**
- Test needed: No.

---

## 6. manage_sagas.py — 78% (31/140 lines uncovered)

### Lines 127-130: Duplicate section heading deduplication

```
127  n = 2
128  while f"{heading} ({n})" in ranges:
129      n += 1
130  heading = f"{heading} ({n})"
```

- **Classification: IMPORTANT**
- What: Handles saga files with duplicate `## ` section headings by appending a counter suffix.
- Scenario: A saga file has two `## Notes` sections. Without deduplication, the first section's range would be overwritten.
- Bug risk: If the deduplication is wrong, section ranges would be incorrect, causing `update_sprint_allocation` or `update_epic_index` to overwrite the wrong part of the file — **data corruption**.
- Test needed: Yes — test with a saga file containing duplicate section headings to verify both get independent ranges.

### Line 153: "Sprint Allocation" section not found guard

```
153  return
```

- **Classification: OK**
- What: Early return when saga file doesn't have a Sprint Allocation section.
- Test needed: No.

### Lines 190, 199: Epic index update internals

```
190  return  (no Epic Index section)
199  continue  (filename doesn't match E-NNNN pattern)
```

- **Classification: OK**
- What: Guards in `update_epic_index`.
- Test needed: No.

### Line 239: "Team Voices" section not found guard

```
239  return
```

- **Classification: OK**
- What: Early return when saga file doesn't have a Team Voices section.
- Test needed: No.

### Lines 261-287: main() CLI dispatch

```
261-287  main()
```

- **Classification: MAIN-ONLY**
- What: CLI subcommand dispatch for update-allocation, update-index, update-voices.
- Bug risk: Line 265 — `alloc_json` defaults to `"[]"` if no arg provided, which is safe. Line 280 — `voices_json` defaults to `"{}"`. Both are parsed with `json.loads` — a malformed JSON arg would crash with an unhandled exception.
- Test needed: No (CLI wrapper), though the unhandled `json.JSONDecodeError` is worth noting.

### Line 291: `__name__` guard

```
291  main()
```

- **Classification: MAIN-ONLY**
- Test needed: No.

---

## Summary: Priority Test Recommendations

### CRITICAL (2 items)

| Module | Lines | What | Why |
|--------|-------|------|-----|
| populate_issues.py | 335 | `get_existing_issues` non-list guard | If GitHub returns non-list JSON, without this check duplicate issues get created silently |
| populate_issues.py | 357, 359-361 | `get_milestone_numbers` validation | Malformed milestone data would crash the dict comprehension or produce wrong milestone mapping |

### IMPORTANT (12 items)

| Module | Lines | What | Why |
|--------|-------|------|-----|
| test_coverage.py | 142-143 | Slug fallback in fuzzy matching | Wrong slug matching hides planned tests from coverage reports |
| test_coverage.py | 158-181 | `format_report()` entire body | Zero test coverage on the report generator |
| bootstrap_github.py | 113-120 | `create_sprint_labels()` | Sprint label creation logic completely untested |
| bootstrap_github.py | 145-154 | Saga parsing from INDEX.md | Both regex patterns for saga extraction untested |
| bootstrap_github.py | 180-181 | Saga file heading error fallback | Filename-based title fallback on read error |
| bootstrap_github.py | 224-230 | `create_epic_labels()` | Epic label creation logic completely untested |
| populate_issues.py | 143-145 | Duplicate story ID detection | Guard that prevents duplicate GitHub issues |
| populate_issues.py | 164-166 | Flat milestone file scanning | Fallback path for milestone files without sprint sections |
| populate_issues.py | 389, 397 | Duplicate sprint-milestone mapping | Warning but "last wins" could silently mis-assign |
| manage_sagas.py | 127-130 | Duplicate section heading dedup | Wrong dedup could cause section range corruption |
| sprint_teardown.py | 52-56 | Manifest corruption fallback | Corrupt manifest causes misclassification of files |
| sprint_teardown.py | 243-245 | EOFError in interactive prompt | Non-interactive teardown silently skips files |

### MAIN-ONLY (6 items)

| Module | Lines | Description |
|--------|-------|-------------|
| test_coverage.py | 191-210 | main() CLI wrapper |
| bootstrap_github.py | 20-41, 318-338 | check_prerequisites + main() |
| populate_issues.py | 39-43, 483-535 | check_prerequisites + main() |
| update_burndown.py | 198-240 | main() CLI wrapper |
| sprint_teardown.py | 351-497 (partial) | main() execution flow |
| manage_sagas.py | 261-291 | main() CLI dispatch |

### OK (remaining items)

Defensive guards, display-only code, and unreachable edge cases — no tests needed.
