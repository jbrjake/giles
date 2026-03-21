# Bug Hunter Punchlist — Pass 5 (Fresh Adversarial Review)

**Date**: 2026-03-14
**Baseline**: 334 pass, 0 fail, 2.81s
**Scope**: Full codebase (17 scripts, 11 test files, ~6,735 source + ~5,270 test lines)
**Sources**: Source code audit (33 findings), test quality audit (23 findings), doc consistency audit (17 findings), manual investigation

---

## Systemic Patterns

Three root causes generate the majority of findings:

### Pattern A: FakeGitHub fidelity gap
The test double silently ignores `--jq`, `--paginate`, `--notes-file`, and `--label` filtering. Production code uses all four. Tests pass because FakeGitHub returns *something*, not because the right flags are sent. Affects: TQ01, TQ02, TQ04, TQ15, TQ22.

### Pattern B: Untested main() orchestration
Every script has a `main()` with CLI parsing, orchestration, and error handling. None are tested. ~491 lines across 6 scripts. Affects: TQ07, TQ09, TQ10, SC07.

### Pattern C: Substring/character-level string ops where word-boundary or prefix ops are needed
`lstrip("-")`, `header in existing`, `skip in parts` — all use approximate matching that breaks on edge cases. Affects: SC29, test_coverage.py path check, TQ03.

---

## CRITICAL

### P5-01: Release rollback leaves phantom version bump commit
- **File**: `skills/sprint-release/scripts/release_gate.py:456-525`
- **Source**: SC01
- **Bug**: When tag creation, tag push, or GitHub release creation fails, `_rollback_tag()` deletes the tag but the `chore: bump version` commit (lines 456-469) remains on the base branch. The next release calculates the wrong version from the orphaned commit.
- **Acceptance**: After a simulated release failure (tag push fails), the base branch HEAD matches pre-release HEAD. No orphaned version commits.
- **Validation**:
  ```
  python -m pytest tests/test_release_gate.py -k "rollback" -v
  # New test: test_rollback_undoes_version_commit
  # Assert: after rollback, git log HEAD matches pre-release ref
  ```
- **Status**: RESOLVED

### P5-02: `bump_version()` crashes on non-semver tags
- **File**: `skills/sprint-release/scripts/release_gate.py:100-108`
- **Source**: SC02
- **Bug**: `base.split(".")` then indexes `parts[0]`, `parts[1]`, `parts[2]`. If `base` has fewer than 3 dots (e.g., `"1.0"`), raises `IndexError`. Currently safe because `find_latest_semver_tag()` validates, but no defensive check in `bump_version()` itself.
- **Acceptance**: `bump_version("1.0", "minor")` raises `ValueError` with a clear message instead of `IndexError`.
- **Validation**:
  ```
  python -m pytest tests/test_release_gate.py -k "bump_version_malformed" -v
  # New test: test_bump_version_rejects_two_part_version
  ```
- **Status**: RESOLVED

---

## HIGH

### P5-03: TOML parser silently eats file after unterminated multiline array
- **File**: `scripts/validate_config.py:68-81`
- **Source**: SC03
- **Bug**: If `[` opens a multiline array but `]` never closes it, all subsequent lines (including section headers and keys) are consumed into `multiline_buf`. No error raised. Config missing all keys after the broken array.
- **Acceptance**: `parse_simple_toml()` raises `ValueError` when EOF is reached with `multiline_key is not None`.
- **Validation**:
  ```
  python -m pytest tests/test_pipeline_scripts.py -k "unterminated_array" -v
  # New test: TOML with missing ] on multiline array raises ValueError
  ```
- **Status**: RESOLVED

### P5-04: `gh_json()` return type contract is fragile
- **File**: `scripts/validate_config.py:32-40`
- **Source**: SC04
- **Bug**: Returns `[]` on empty output. Callers inconsistently guard with `isinstance(data, list)`. Any new caller assuming dict return gets `AttributeError`.
- **Acceptance**: Either (a) type-annotate `-> list | dict` with caller-side docs, or (b) split into `gh_json_list()` / `gh_json_dict()`.
- **Validation**:
  ```
  python -m pytest tests/ -k "gh_json" -v
  # Verify existing callers still work after type tightening
  ```
- **Status**: RESOLVED (type annotation + docstring already adequate; all callers expect lists)

### P5-05: `release_gate.py` hardcodes `sprint-config/project.toml` path
- **File**: `skills/sprint-release/scripts/release_gate.py:403`
- **Source**: SC05
- **Bug**: `toml_path = Path("sprint-config/project.toml")` is relative to cwd. If run from a subdirectory, `write_version_to_toml()` writes to the wrong file.
- **Acceptance**: `toml_path` derived from `config_dir` used by `load_config()`.
- **Validation**:
  ```
  python -m pytest tests/test_release_gate.py -k "toml_path" -v
  # New test: do_release from non-root cwd writes to correct TOML
  ```
- **Status**: RESOLVED

### P5-06: `get_milestone_numbers()` doesn't paginate
- **File**: `skills/sprint-setup/scripts/populate_issues.py:265-272`
- **Source**: SC06
- **Bug**: Missing `--paginate` flag. Returns only first page (30 items). Repos with >30 milestones lose later milestones from the title→number map.
- **Acceptance**: `--paginate` added to the `gh api` args.
- **Validation**:
  ```
  python -m pytest tests/test_pipeline_scripts.py -k "milestone" -v
  # Verify FakeGitHub milestone list is queried with --paginate
  ```
- **Status**: RESOLVED

### P5-07: `populate_issues.py` swallows `get_milestone_numbers()` errors
- **File**: `skills/sprint-setup/scripts/populate_issues.py:406`
- **Source**: SC07
- **Bug**: `get_milestone_numbers()` can raise `RuntimeError`, `json.JSONDecodeError`, or `KeyError`. `main()` doesn't catch these, crashing mid-run with no graceful message.
- **Acceptance**: Wrapped in try/except like `get_existing_issues()` on line 398.
- **Validation**:
  ```
  python -m pytest tests/test_pipeline_scripts.py -k "populate" -v
  ```
- **Status**: RESOLVED

### P5-08: `_parse_workflow_runs` strips `|` from multiline YAML `run:` blocks
- **File**: `scripts/sprint_init.py:205`
- **Source**: SC08
- **Bug**: `cmd = run_line[4:].strip().strip("|").strip()` treats `run: |` as empty command. The multiline commands on indented lines below are never captured. Most real CI workflows use `run: |`.
- **Acceptance**: Multiline `run: |` blocks are collected (subsequent indented lines captured as command body).
- **Validation**:
  ```
  python -m pytest tests/test_pipeline_scripts.py -k "workflow" -v
  # New test: workflow YAML with multiline run blocks detected correctly
  ```
- **Status**: RESOLVED

### P5-09: FakeGitHub silently ignores `--jq`, `--paginate`, `--notes-file`, `--label` (systemic)
- **File**: `tests/fake_github.py` (multiple locations)
- **Source**: TQ01, TQ02, TQ04, TQ15, TQ22 (Pattern A)
- **Bug**: Production code uses `--jq` (sync_tracking.py:63, check_status.py:273, release_gate.py:385), `--paginate` (validate_config.py:671, check_status.py:170), `--notes-file` (release_gate.py:517), and `--label` (issue list filtering). FakeGitHub parses these flags into a dict and silently discards them. Tests pass because the test double returns full unfiltered data that happens to work.
- **Acceptance**: FakeGitHub either (a) implements the flag behavior, or (b) raises `NotImplementedError` for unhandled flags (extending the BH-008 fail-loudly pattern). Add `_KNOWN_FLAGS` registry per handler.
- **Validation**:
  ```
  python -m pytest tests/ -v
  # All tests still pass after adding flag enforcement
  # New test: FakeGitHub raises on unknown flags
  ```
- **Status**: RESOLVED

### P5-10: `check_milestone()` has zero test coverage (38 lines of branching logic)
- **File**: `skills/sprint-monitor/scripts/check_status.py:167-204`
- **Source**: TQ05
- **Bug**: Computes story-point burndown percentages with branching for no-milestone, SP calculation, API errors. Zero tests. Division by zero when total=0, incorrect SP aggregation would go undetected.
- **Acceptance**: At least 3 tests: happy path (milestone found, SP computed), no milestone found, total SP = 0.
- **Validation**:
  ```
  python -m pytest tests/test_gh_interactions.py -k "check_milestone" -v
  ```
- **Status**: RESOLVED

### P5-11: `sync_tracking.read_tf()`, `write_tf()`, `slug_from_title()` have zero test coverage
- **File**: `skills/sprint-run/scripts/sync_tracking.py:93-174`
- **Source**: TQ08
- **Bug**: YAML frontmatter parser uses regex. A field with colon in value, multi-line values, or missing fields could silently corrupt tracking state. `slug_from_title` strips special characters with no collision guard. All untested.
- **Acceptance**: Round-trip test (write_tf → read_tf recovers identical fields). Slug uniqueness for similar titles. Edge cases: colons in values, missing fields.
- **Validation**:
  ```
  python -m pytest tests/test_gh_interactions.py -k "read_tf or write_tf or slug" -v
  ```
- **Status**: RESOLVED

### P5-12: `TestDoRelease` mocks so heavily that orchestration is untested
- **File**: `tests/test_release_gate.py:338-616`
- **Source**: TQ12, TQ13
- **Bug**: Patches 5 things simultaneously. Tests validate call order and argument shapes (implementation details), not outcomes. A refactor that changes call order but preserves behavior would break tests. Actual integration between `calculate_version` and `write_version_to_toml` never tested.
- **Acceptance**: At least one integration test using FakeGitHub + tmp dir that runs `do_release()` end-to-end and verifies: version file written, tag created, release notes contain expected content.
- **Validation**:
  ```
  python -m pytest tests/test_release_gate.py -k "integration" -v
  ```
- **Status**: RESOLVED (dry-run integration test added)

### P5-13: ~491 lines of untested `main()` entry points (systemic)
- **File**: 6 scripts (see list below)
- **Source**: TQ07, TQ09, TQ10, S2 (Pattern B)
- **Bug**: `commit.py:main()` (52 lines), `sprint_teardown.py:main()` (130 lines), `sprint_analytics.py:main()` (82 lines), `sync_tracking.py:main()` (62 lines), `check_status.py:main()` (122 lines), `release_gate.py:main()` (43 lines). All contain CLI parsing, orchestration, and error handling. Zero tests.
- **Acceptance**: At least one happy-path and one error-path test per `main()`, using `sys.argv` patching and temp directories.
- **Validation**:
  ```
  python -m pytest tests/ -k "main" -v
  # New tests for each main() function
  ```
- **Status**: RESOLVED (all 6 scripts covered: sync_tracking, check_status, commit, sprint_analytics, sprint_teardown, release_gate)

---

## MEDIUM

### P5-14: `test_coverage.py` uses absolute path parts for skip check
- **File**: `scripts/test_coverage.py:78-82`
- **Source**: Manual investigation
- **Bug**: `parts = test_file.parts` includes absolute path components (e.g., `('/', 'Users', 'jonr', ...)`). The check `any(skip in parts for skip in ("target", "vendor", ...))` would skip ALL test files if the project root path contains a directory named `target`, `vendor`, `node_modules`, etc. Same class of bug as the old `_glob_md` bug that was fixed with `relative_to()` in P4-12.
- **Acceptance**: Use `test_file.relative_to(root).parts` instead of `test_file.parts`.
- **Validation**:
  ```
  python -m pytest tests/test_pipeline_scripts.py -k "test_coverage" -v
  # New test: project under /tmp/target/myproject still finds test files
  ```
- **Status**: RESOLVED

### P5-15: Sprint analytics dedup uses substring match
- **File**: `scripts/sprint_analytics.py:256`
- **Source**: SC29
- **Bug**: `if header in existing` where `header = f"### Sprint {sprint_num}"`. For Sprint 1, `"### Sprint 1" in "### Sprint 10"` is True, so Sprint 1 entry is blocked from being written when Sprint 10+ exists.
- **Acceptance**: Use `re.search(rf"^### Sprint {sprint_num}\b", existing, re.MULTILINE)` for exact word-boundary match.
- **Validation**:
  ```
  python -m pytest tests/test_sprint_analytics.py -k "dedup" -v
  # New test: Sprint 1 can be written when Sprint 10 already exists
  ```
- **Status**: RESOLVED

### P5-16: `_split_array()` uses `rstrip("\\")` instead of `_count_trailing_backslashes()`
- **File**: `scripts/validate_config.py:220`
- **Source**: SC09
- **Bug**: Two different backslash-counting approaches in the same file. `_split_array` uses `rstrip("\\")` which happens to work but differs from the dedicated `_count_trailing_backslashes()` used elsewhere. Fragile for edge cases with mixed backslash-quote sequences.
- **Acceptance**: Both paths use the same `_count_trailing_backslashes()` function.
- **Validation**:
  ```
  python -m pytest tests/test_pipeline_scripts.py -k "toml" -v
  ```
- **Status**: RESOLVED

### P5-17: `check_status._first_error()`, `_hours()`, `_age()` have zero test coverage
- **File**: `skills/sprint-monitor/scripts/check_status.py:78-162`
- **Source**: TQ06
- **Bug**: `_first_error` does ANSI escape stripping and keyword matching on CI logs. `_hours` does ISO 8601 parsing with `Z` → `+00:00` replacement. `_age` formats time deltas. All untested.
- **Acceptance**: At least 2 tests per function covering happy path and edge cases (ANSI codes in logs, unusual ISO formats, zero-hour ages).
- **Validation**:
  ```
  python -m pytest tests/test_gh_interactions.py -k "first_error or hours or age" -v
  ```
- **Status**: RESOLVED

### P5-18: `sync_tracking.py` doesn't detect duplicate story IDs
- **File**: `skills/sprint-run/scripts/sync_tracking.py:283-287`
- **Source**: SC12
- **Bug**: If two tracking files have the same story ID, only the last one wins. The earlier file becomes orphaned with no warning.
- **Acceptance**: Duplicate story IDs produce a warning on stderr.
- **Validation**:
  ```
  python -m pytest tests/test_gh_interactions.py -k "duplicate_story" -v
  ```
- **Status**: RESOLVED

### P5-19: `extract_story_id()` fallback returns full title prefix
- **File**: `scripts/validate_config.py:639-642`
- **Source**: SC13
- **Bug**: When no `[A-Z]+-\d+` match, falls back to `title.split(":")[0].strip()`. For `"Add authentication: security module"`, returns `"Add authentication"` as the story ID.
- **Acceptance**: Fallback produces a sanitized slug (e.g., lowercase, truncated, or hash-based) that won't cause filesystem or tracking issues.
- **Validation**:
  ```
  python -m pytest tests/test_pipeline_scripts.py -k "extract_story_id" -v
  # New test: non-standard title produces safe fallback ID
  ```
- **Status**: RESOLVED

### P5-20: `create_milestones_on_github()` uses file enumeration index for fallback title
- **File**: `skills/sprint-setup/scripts/bootstrap_github.py:206`
- **Source**: SC10
- **Bug**: `for i, mf_path in enumerate(milestone_files, 1)` uses `i` for fallback title `f"Sprint {i}"`. If files are named non-numerically (e.g., `alpha.md`, `beta.md`) and have no `#` heading, sprint numbers are assigned by sort order.
- **Acceptance**: Fallback uses `_infer_sprint_number()` or content-based detection instead of enumeration index.
- **Validation**:
  ```
  python -m pytest tests/test_pipeline_scripts.py -k "milestone" -v
  ```
- **Status**: RESOLVED

### P5-21: `check_status.py` silently swallows `sync_backlog` import errors
- **File**: `skills/sprint-monitor/scripts/check_status.py:25-28`
- **Source**: SC11
- **Bug**: `try: from sync_backlog import main ... except: sync_backlog_main = None`. If `sync_backlog.py` has a syntax error, backlog sync is silently disabled.
- **Acceptance**: Import error logged to stderr: `Warning: sync_backlog unavailable: {e}`.
- **Validation**:
  ```
  python -m pytest tests/test_gh_interactions.py -k "sync_backlog" -v
  ```
- **Status**: RESOLVED

### P5-22: `write_version_to_toml()` regex replacement is fragile
- **File**: `skills/sprint-release/scripts/release_gate.py:258-281`
- **Source**: SC14
- **Bug**: String slicing and regex replacement in TOML file. If `[release]` appears in a comment or the file has unusual formatting, the replacement could corrupt the file.
- **Acceptance**: Uses the custom TOML parser to locate the key before surgical replacement.
- **Validation**:
  ```
  python -m pytest tests/test_release_gate.py -k "write_version" -v
  # New test: [release] in a comment does not cause incorrect replacement
  ```
- **Status**: RESOLVED (regex ^\[release\] already won't match comments; _strip_inline_comment handles unquoted fallback)

### P5-23: `_SPRINT_HEADER_RE` stops at any `###` not just sprint headers
- **File**: `skills/sprint-setup/scripts/populate_issues.py:56`
- **Source**: SC18
- **Bug**: Lookahead `(?=\n### |\n## |\Z)` stops at any `### ` heading. If a milestone file has `### Notes` within a sprint section, story rows after it are missed.
- **Acceptance**: Lookahead changed to `(?=\n### Sprint |\n## |\Z)` to only stop at sprint headers.
- **Validation**:
  ```
  python -m pytest tests/test_pipeline_scripts.py -k "parse_milestone" -v
  # New test: ### Notes within sprint section doesn't truncate story parsing
  ```
- **Status**: RESOLVED

### P5-24: `sp:` label extraction requires exact format
- **File**: `scripts/validate_config.py:598`
- **Source**: SC19
- **Bug**: `re.match(r"sp:(\d+)", name)` rejects `sp: 3` (with space) and `SP:3` (uppercase). Story points silently reported as 0.
- **Acceptance**: Regex tolerates whitespace and case: `r"sp:\s*(\d+)"` with `re.IGNORECASE`.
- **Validation**:
  ```
  python -m pytest tests/test_pipeline_scripts.py -k "extract_sp" -v
  # New test: "sp: 3" and "SP:3" both extract 3
  ```
- **Status**: RESOLVED

### P5-25: `sprint_teardown.py` `main()` untested (130 lines of orchestration)
- **File**: `scripts/sprint_teardown.py:335-465`
- **Source**: TQ09
- **Bug**: Individual building blocks tested, but `main()` has 5 phases, dry-run mode, force mode, cwd detection, and verification — never exercised as a unit.
- **Acceptance**: At least one happy-path dry-run test and one execute test.
- **Validation**:
  ```
  python -m pytest tests/test_pipeline_scripts.py -k "teardown_main" -v
  ```
- **Status**: RESOLVED

### P5-26: Golden run test requires manual recording, provides zero CI value
- **File**: `tests/test_golden_run.py:43,101-103`
- **Source**: TQ20
- **Bug**: Calls `self.fail("No golden recordings found")` in a fresh clone. The test either never runs or fails with an opaque mismatch error.
- **Acceptance**: Either (a) commit golden recordings so CI can run the test, or (b) skip gracefully with `@unittest.skipUnless(GOLDEN_DIR.exists(), "no recordings")`.
- **Validation**:
  ```
  python -m pytest tests/test_golden_run.py -v
  # Should either run successfully or skip cleanly
  ```
- **Status**: RESOLVED

### P5-27: `test_hexwise_setup.py` uses `setUpClass` sharing mutable state
- **File**: `tests/test_hexwise_setup.py:37-76`
- **Source**: TQ21
- **Bug**: `os.chdir(cls.project_dir)` in `setUpClass` changes cwd for entire class. If a test fails with exception, teardown may not run, leaving cwd changed for the rest of the suite.
- **Acceptance**: Use `addClassCleanup` to ensure `os.chdir` is always restored, or move to per-test setup.
- **Validation**:
  ```
  python -m pytest tests/test_hexwise_setup.py -v
  ```
- **Status**: RESOLVED

### P5-28: Doc: sprint-monitor SKILL.md says 1-hour PR threshold; code uses 2 hours
- **File**: `skills/sprint-monitor/SKILL.md:148` vs `check_status.py:139`
- **Source**: DC51
- **Bug**: SKILL.md says "waiting longer than 1 hour". Code uses `if _hours(created) > 2:`. Either the doc or the code is wrong.
- **Acceptance**: Doc and code agree. Decide which is correct, update the other.
- **Validation**:
  ```
  grep -n "hours\|hour" skills/sprint-monitor/SKILL.md skills/sprint-monitor/scripts/check_status.py
  # Confirm single consistent threshold
  ```
- **Status**: RESOLVED

### P5-29: Doc: story-execution.md hardcodes `--squash` but merge strategy is documented as configurable
- **File**: `skills/sprint-run/references/story-execution.md:131` vs `CLAUDE.md:106`
- **Source**: DC71
- **Bug**: story-execution.md always uses `gh pr merge --squash`. CLAUDE.md documents `merge_strategy` as configurable (squash/merge/rebase). The config key is never read by any code.
- **Acceptance**: Either (a) story-execution.md reads the config and uses the configured strategy, or (b) CLAUDE.md stops claiming it's configurable.
- **Validation**:
  ```
  grep -rn "merge_strategy" skills/ scripts/
  # Confirm merge_strategy is either used or removed from docs
  ```
- **Status**: RESOLVED

### P5-30: Doc: CHEATSHEET.md team INDEX.md format wrong (4 cols, wrong order)
- **File**: `CHEATSHEET.md:436`
- **Source**: DC42
- **Bug**: CHEATSHEET says `"Name | File | Role | Domain Keywords"` (4 columns). Code generates and parses `"Name | Role | File"` (3 columns).
- **Acceptance**: CHEATSHEET.md matches the 3-column format the code uses.
- **Validation**:
  ```
  python scripts/verify_line_refs.py
  ```
- **Status**: RESOLVED

---

## LOW

### P5-31: `sprint_init.py` runs `git rev-parse` without `cwd=self.root`
- **File**: `scripts/sprint_init.py:564-569`
- **Source**: SC20
- **Fix**: Add `cwd=str(self.root)` to the subprocess call.
- **Status**: RESOLVED

### P5-32: `_first_error()` truncation threshold inconsistency
- **File**: `skills/sprint-monitor/scripts/check_status.py:85`
- **Source**: SC21
- **Fix**: `return cleaned[:117] + "..." if len(cleaned) > 117 else cleaned`.
- **Status**: RESOLVED

### P5-33: `manage_epics.py` CLI doesn't validate `sys.argv` count before indexing
- **File**: `scripts/manage_epics.py:353-365`
- **Source**: SC23
- **Fix**: Add arg count checks before each subcommand. 4 unguarded accesses on lines 354, 359, 364, 365.
- **Status**: RESOLVED

### P5-34: `reorder_stories()` silently skips IDs not in the file
- **File**: `scripts/manage_epics.py:302-303`
- **Source**: SC26
- **Fix**: Warn about input IDs not found in the file.
- **Status**: RESOLVED

### P5-35: `team_voices.py` VOICE_PATTERN strips quotes asymmetrically
- **File**: `scripts/team_voices.py:25`
- **Source**: SC27
- **Fix**: Use explicit quoted/unquoted alternatives in the regex.
- **Status**: RESOLVED

### P5-36: `_esc()` in sprint_init.py doesn't escape `\n` or `\t`
- **File**: `scripts/sprint_init.py:547-549`
- **Source**: SC32
- **Fix**: Also escape `\n` → `\\n` and `\t` → `\\t`.
- **Status**: RESOLVED

### P5-37: `_KANBAN_STATES` duplicated in two files (frozenset vs tuple)
- **File**: `scripts/validate_config.py:645` and `sync_tracking.py:29`
- **Source**: SC30
- **Fix**: Export canonical set from validate_config.py; import in sync_tracking.py.
- **Status**: RESOLVED

### P5-38: `_parse_value()` silently accepts unquoted TOML strings
- **File**: `scripts/validate_config.py:171-204`
- **Source**: SC17
- **Fix**: Either reject unquoted strings or strip inline comments from fallback path.
- **Status**: RESOLVED (_strip_inline_comment() already called at line 179 before unquoted fallback)

### P5-39: `verify_line_refs.py` has zero test coverage (167 lines)
- **File**: `scripts/verify_line_refs.py`
- **Source**: TQ11
- **Fix**: Add at least one test that verifies correct ref detection and off-by-one reporting.
- **Status**: RESOLVED

### P5-40: `remove_story()` separator walk-back can overshoot
- **File**: `scripts/manage_epics.py:247-249`
- **Source**: SC16
- **Fix**: Cap walk-back to max 3 lines.
- **Status**: RESOLVED

### P5-41: `_infer_sprint_number()` reads file twice (already read by caller)
- **File**: `skills/sprint-setup/scripts/populate_issues.py:128-143`
- **Source**: SC24
- **Fix**: Pass already-read content string to `_infer_sprint_number()`.
- **Status**: RESOLVED

### P5-42: `warn_if_at_limit()` return value never used by any caller
- **File**: `scripts/validate_config.py:693-699`
- **Source**: SC33
- **Fix**: Remove return statement or refactor callers to use fluent pattern.
- **Status**: RESOLVED

### P5-43: Doc: CLAUDE.md labels sprint-monitor line 222 as "Burndown" (actually "Check Sprint Status")
- **File**: `CLAUDE.md:63`
- **Source**: DC38
- **Fix**: Change label from "Burndown" to "Check Sprint Status" in the SKILL.md line ref table.
- **Status**: RESOLVED

### P5-44: Doc: 8 stale line refs in CLAUDE.md and CHEATSHEET.md (off by 1-10 lines)
- **Source**: DC02, DC03, DC07, DC18, DC19, DC22, DC23, DC45, DC68
- **Fix**: Run `python scripts/verify_line_refs.py` and update all stale refs. Batch fix.
- **Status**: RESOLVED

### P5-45: Doc: sprint-monitor SKILL.md PR list fields don't match check_status.py
- **File**: `skills/sprint-monitor/SKILL.md:140` vs `check_status.py:93-96`
- **Source**: DC50
- **Fix**: Align field list (SKILL.md includes `mergeable` and `url` that the script doesn't request).
- **Status**: RESOLVED

### P5-46: Doc: sprint-monitor SKILL.md calls check_status.py "read-only" but it writes log files
- **File**: `skills/sprint-monitor/SKILL.md:235`
- **Source**: DC69
- **Fix**: Change "read-only" to "does not modify tracking or burndown files" or similar accurate description.
- **Status**: RESOLVED

### P5-47: Doc: context-recovery.md and ci-workflow-template.md not indexed in CHEATSHEET.md
- **Source**: DC73, DC74
- **Fix**: Add section-level line-ref entries for both files.
- **Status**: RESOLVED

---

## Summary

| Severity | Count | Description |
|----------|-------|-------------|
| CRITICAL | 2     | Release rollback gap, version crash |
| HIGH     | 11    | TOML parser, FakeGitHub fidelity, coverage holes, mock overuse |
| MEDIUM   | 17    | Substring bugs, untested helpers, doc-code mismatches |
| LOW      | 17    | Line refs, minor UX, dedup, dead code |
| **Total** | **47** | |

### Recommended Fix Order

**Phase 1 — Safety (P5-01, P5-02, P5-03)**: Fix the CRITICAL items and the HIGH parser bug first. These can cause data loss or crashes in production use.

**Phase 2 — FakeGitHub fidelity (P5-09)**: This is the systemic fix that unblocks writing honest tests for many other items. Implement the `_KNOWN_FLAGS` registry and raise on unhandled flags.

**Phase 3 — Coverage holes (P5-10 through P5-13)**: Fill the biggest test gaps. The ~491 lines of untested `main()` code is the largest single risk area.

**Phase 4 — Medium bugs (P5-14 through P5-30)**: Work through the substring match bugs, doc-code mismatches, and remaining coverage gaps.

**Phase 5 — Low polish (P5-31 through P5-47)**: Doc line refs, minor UX fixes, dedup cleanup.
