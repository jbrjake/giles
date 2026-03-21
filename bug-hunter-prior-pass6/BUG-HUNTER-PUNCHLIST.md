# Bug Hunter Punchlist — Pass 6 (Legacy Code Adversarial Review)

**Date**: 2026-03-14
**Baseline**: 399 pass, 0 fail, 2.83s
**Scope**: Full codebase — 17 scripts, 10 test files, ~12,100 LOC total
**Perspective**: New developer inheriting "legacy" code after 5 prior audit passes

---

## Systemic Patterns

Four root causes generate the majority of findings:

### Pattern A: FakeGitHub behavioral fidelity gaps (still)
Pass 5 added `_KNOWN_FLAGS` enforcement for `--` prefixed flags. But production code
uses single-dash flags (`-f`, `-X`) that bypass `_parse_flags` entirely. And multiple
API endpoints are unhandled, so tests silently take error paths. Affects: P6-01, P6-02,
P6-03, P6-05, P6-11.

### Pattern B: Untested monitoring features
`check_branch_divergence`, `check_direct_pushes`, and `get_linked_pr` timeline API
all hit unhandled FakeGitHub endpoints. Tests pass because RuntimeError is caught. The
actual functionality is zero-percent tested. Affects: P6-02, P6-05, P6-06.

### Pattern C: Doc claims exceed implementation
`merge_strategy` is documented as configurable in 3 places and generated in config,
but no script reads it. Several SKILL.md sections describe behavior that doesn't
exist in code. Affects: P6-09, P6-10, P6-15, P6-16.

### Pattern D: Error recovery paths untested
`do_release` has careful rollback logic that was tested in Pass 5, but new gaps remain:
notes file not cleaned up on failure, hardcoded paths, and no integration test of the
full release pipeline against FakeGitHub. Affects: P6-03, P6-04, P6-08.

---

## HIGH

### P6-01: `_parse_flags` silently skips single-dash flags, bypassing `_check_flags` enforcement
- **File**: `tests/fake_github.py:122-135`
- **Bug**: `_parse_flags` only processes args starting with `--`. Production code uses `-f` (bootstrap_github.py:234, check_status.py:272, release_gate.py:564) and `-X` (release_gate.py:564). These single-dash flags are silently skipped (fall to `i += 1`). `_check_flags` never sees them. The `_KNOWN_FLAGS["api"]` entries for "f" and "X" are dead code that can never match.
- **Impact**: The Pass 5 flag enforcement mechanism has a hole. Any new production code using short flags gets free green bar.
- **Acceptance**: `_parse_flags` captures both `--flag` and `-flag` variants. Test: pass an unknown `-z` flag to an API handler and verify `NotImplementedError` is raised.
- **Validation**:
  ```
  python -m pytest tests/ -k "test_parse_flags_short" -v
  # New test: FakeGitHub._parse_flags captures -f, -X
  # New test: _check_flags raises on unknown short flag -z
  # All 399 existing tests still pass
  ```
- **Status**: RESOLVED (f42139c)

### P6-02: `check_branch_divergence` and `check_direct_pushes` are zero-percent tested
- **File**: `skills/sprint-monitor/scripts/check_status.py:222-294`
- **Bug**: Both functions call `gh_json` with API endpoints (`repos/{repo}/compare/...` and `repos/{repo}/commits`) that FakeGitHub doesn't handle. FakeGitHub returns `_fail("unhandled API path")` which causes `gh()` to raise `RuntimeError`. The callers catch this silently. Tests pass because the error paths produce empty report/action lists. ~73 lines of branch divergence + direct push detection have never been exercised.
- **Impact**: If these features have bugs (wrong thresholds, bad JSON parsing, broken formatting), no test would catch them.
- **Acceptance**: FakeGitHub handles `repos/{repo}/compare/{base}...{branch}` and `repos/{repo}/commits` endpoints. At least 2 tests per function: happy path (drift detected) and clean path (no drift).
- **Validation**:
  ```
  python -m pytest tests/test_gh_interactions.py -k "branch_divergence or direct_push" -v
  # New tests: check_branch_divergence returns HIGH drift for >20 behind
  # New tests: check_direct_pushes detects non-merge commits
  # Verify FakeGitHub raises on unknown compare/ sub-paths
  ```
- **Status**: RESOLVED (92822ca)

### P6-03: `do_release` doesn't clean up `release-notes.md` on failure
- **File**: `skills/sprint-release/scripts/release_gate.py:526-554`
- **Bug**: `notes_path = Path("release-notes.md")` is written at line 533. Cleaned up at line 554 after success. But if `gh(release_args)` raises RuntimeError at line 545, the except block (546-550) calls `_rollback_tag()` and `_rollback_commit()` but never calls `notes_path.unlink()`. A stale `release-notes.md` remains in the working directory.
- **Impact**: After a failed release, the working tree is not clean. The next `do_release` pre-flight check (`git status --porcelain`) will fail because of the leftover file.
- **Acceptance**: After a simulated release failure (GitHub release creation fails), `release-notes.md` does not exist in the working directory. The _fail path includes cleanup.
- **Validation**:
  ```
  python -m pytest tests/test_release_gate.py -k "gh_release_failure_cleans_notes" -v
  # New test: after gh release create fails, cwd has no release-notes.md
  ```
- **Status**: RESOLVED (34d7c9b)

### P6-04: `release-notes.md` path is hardcoded to cwd
- **File**: `skills/sprint-release/scripts/release_gate.py:526`
- **Bug**: `notes_path = Path("release-notes.md")` writes to current working directory. If run from a subdirectory or if a file named `release-notes.md` already exists (e.g., user's existing notes), it gets overwritten without warning. Should use a temp file.
- **Impact**: Data loss if user has a `release-notes.md` in their project root. Also, cwd-relative path is fragile (see P5-05 precedent for the same class of bug).
- **Acceptance**: `notes_path` uses `tempfile.NamedTemporaryFile` or a path derived from config. No hardcoded filename in cwd.
- **Validation**:
  ```
  python -m pytest tests/test_release_gate.py -k "notes_file_temp" -v
  # New test: do_release doesn't write release-notes.md to cwd
  # New test: existing release-notes.md in cwd is not overwritten
  ```
- **Status**: RESOLVED (34d7c9b)

### P6-05: `get_linked_pr` timeline API always fails in tests — fallback is the only tested path
- **File**: `skills/sprint-run/scripts/sync_tracking.py:57-89`
- **Bug**: The timeline API call (`repos/{owner}/{repo}/issues/{N}/timeline`) at line 59-63 hits an unhandled FakeGitHub endpoint. It always raises RuntimeError, so the except block at line 74 fires, and the function falls back to branch-name matching. The primary PR-linking mechanism (timeline API) has zero test coverage.
- **Impact**: If the timeline API response parsing has bugs (wrong JSON path, missing fields), no test would catch them. The jq filter `'[.[] | select(.source?.issue?.pull_request?) | .source.issue] | first'` is complex and untested.
- **Acceptance**: FakeGitHub handles the timeline API endpoint. At least one test verifies timeline-based PR linking works. At least one test verifies the fallback path is taken when timeline returns no match.
- **Validation**:
  ```
  python -m pytest tests/test_gh_interactions.py -k "timeline_pr_link" -v
  # New test: timeline API returns linked PR → get_linked_pr returns it
  # New test: timeline API returns no match → fallback to branch name
  ```
- **Status**: RESOLVED (92822ca)

### P6-06: `get_linked_pr` fallback uses substring matching for story IDs
- **File**: `skills/sprint-run/scripts/sync_tracking.py:79`
- **Bug**: `re.search(re.escape(story_id), branch, re.IGNORECASE)` matches story_id as a substring of the branch name. Story ID `"US-01"` would match branch `"sprint-1/US-010-feature"` because `"US-01"` is a substring of `"US-010"`. This produces a false positive PR link.
- **Impact**: During sync, a story could be incorrectly linked to another story's PR. The tracking file would show the wrong PR number.
- **Acceptance**: Use word boundary matching: `rf"\b{re.escape(story_id)}\b"`. Test that `US-01` does NOT match `US-010` branch but DOES match `US-01-feature`.
- **Validation**:
  ```
  python -m pytest tests/test_gh_interactions.py -k "pr_link_boundary" -v
  # New test: get_linked_pr("US-01") does not match branch "sprint-1/US-010-feature"
  # New test: get_linked_pr("US-01") matches branch "sprint-1/US-01-setup"
  ```
- **Status**: RESOLVED (92822ca)

### P6-07: `_ACCEPTED_NOOP_FLAGS` includes `--jq` but `--jq` changes response shape
- **File**: `tests/fake_github.py:92`
- **Bug**: `--jq` is listed as a no-op flag, but in production `gh --jq <expr>` transforms the JSON output shape. FakeGitHub returns full JSON, while production returns jq-filtered JSON. Code that depends on the filtered shape works in tests (full JSON is a superset) but the test doesn't verify the code handles the exact production response shape.
- **Specific cases**: `check_branch_divergence` (check_status.py:237) expects `{behind_by, ahead_by}` from `--jq`. `get_linked_pr` (sync_tracking.py:62) expects a single issue object from `--jq '[...] | first'`. `check_direct_pushes` (check_status.py:274) expects `[{sha, message, author, date}]`.
- **Impact**: Tests provide false confidence. If production jq output differs from what the code expects, no test would catch it.
- **Acceptance**: Either (a) FakeGitHub applies `--jq` transforms for known patterns, or (b) move `--jq` out of `_ACCEPTED_NOOP_FLAGS` and into handler-specific implementations, or (c) test explicitly with the expected response shape (mock the pre-filtered data).
- **Validation**:
  ```
  python -m pytest tests/ -v
  # All tests pass after --jq handling change
  # New tests verify response shapes match production --jq output
  ```
- **Status**: RESOLVED (f42139c)

### P6-08: No integration test covers the sprint-run monitoring pipeline
- **File**: N/A (missing test)
- **Bug**: The test suite covers init → bootstrap → populate (test_lifecycle.py) but never tests sync_tracking → update_burndown → check_status as a connected pipeline. Each script is unit-tested individually, but the data flow between them (tracking files written by sync_tracking, read by update_burndown, milestone progress checked by check_status) is never verified end-to-end.
- **Impact**: State-passing bugs between scripts (wrong file formats, missing fields, path derivation errors) would go undetected. Pass 5 identified this as the #1 area for Pass 6 to probe.
- **Acceptance**: One integration test that: (1) creates issues in FakeGitHub with a milestone, (2) runs sync_tracking to create tracking files, (3) runs update_burndown to create burndown.md, (4) runs check_status to verify milestone progress reporting. All against FakeGitHub + temp directory.
- **Validation**:
  ```
  python -m pytest tests/test_lifecycle.py -k "monitoring_pipeline" -v
  # New test: sync_tracking -> update_burndown -> check_status pipeline
  # Verify: tracking files created, burndown.md written, status report contains progress %
  ```
- **Status**: RESOLVED (031f2c8)

---

## MEDIUM

### P6-09: `merge_strategy` is a phantom feature — documented but never consumed
- **File**: `CLAUDE.md:106`, `skills/sprint-monitor/SKILL.md:167`, `skills/sprint-run/references/story-execution.md:128`, `scripts/sprint_init.py:647`
- **Bug**: P5-29 was marked "RESOLVED" but the fix was incomplete. The key is generated in config (`sprint_init.py:647`) and documented in 3 places as configurable, but no Python script reads `config.get("conventions", {}).get("merge_strategy")`. `story-execution.md:128` says "Merge the PR using the configured strategy" but the skill prompt doesn't inject the config value.
- **Impact**: Users who change `merge_strategy` to "rebase" in their config will see no effect. The documentation claims a capability that doesn't exist.
- **Acceptance**: Either (a) story-execution.md injects `merge_strategy` from config into the merge command, or (b) all docs are updated to say merge strategy is always squash (removing the false configurability claim).
- **Validation**:
  ```
  grep -rn "merge_strategy" skills/ scripts/ --include="*.py" | grep -v "test\|golden\|bug-hunter"
  # If option (a): at least one script reads merge_strategy from config
  # If option (b): zero doc references to merge_strategy as "configurable"
  ```
- **Status**: RESOLVED (0d8445b)

### P6-10: `branch_pattern` and `commit_style` are also phantom features
- **File**: `scripts/sprint_init.py:645-646`, `CLAUDE.md:106`
- **Bug**: Same pattern as P6-09. `branch_pattern` and `commit_style` are generated in config and documented as convention keys, but no script reads them. The story-execution.md reference file hardcodes branch pattern `sprint-{N}/US-{ID}-{slug}` and commit.py enforces conventional commits regardless of what `commit_style` says.
- **Impact**: Config keys that do nothing erode trust. Users who customize these expecting behavior changes will be confused.
- **Acceptance**: Either implement the keys or remove them from generated config and docs.
- **Validation**:
  ```
  grep -rn "branch_pattern\|commit_style" scripts/ skills/ --include="*.py" | grep -v "init\|test\|golden\|bug-hunter"
  # Zero results = phantom keys confirmed
  ```
- **Status**: RESOLVED (0d8445b)

### P6-11: FakeGitHub `_issue_list` doesn't implement `--label` filtering
- **File**: `tests/fake_github.py:287-324`
- **Bug**: `_KNOWN_FLAGS["issue_list"]` includes "label" and `_check_flags` accepts it. But `_issue_list` only filters by `--state`, `--milestone`, `--json`, and `--limit`. The `--label` flag is parsed but not applied. If any future production code uses `gh issue list --label`, tests will return unfiltered results.
- **Impact**: Latent — no current production code uses `--label` with `issue list`. But the flag registry falsely claims it's "known" when it's actually silently ignored.
- **Acceptance**: Either (a) implement label filtering in `_issue_list`, or (b) remove "label" from `_KNOWN_FLAGS["issue_list"]` so it raises NotImplementedError if used.
- **Validation**:
  ```
  python -m pytest tests/ -k "issue_list_label_filter" -v
  # If (a): new test verifying label filter returns only matching issues
  # If (b): new test verifying --label raises NotImplementedError
  ```
- **Status**: RESOLVED (f42139c)

### P6-12: `_strip_inline_comment` doesn't handle single-quoted TOML strings
- **File**: `scripts/validate_config.py:131-139`
- **Bug**: Only tracks `"` (double-quote) for string boundaries. TOML also supports literal strings with `'` (single quotes). A value like `key = 'hello # world'` would have `# world'` stripped as a comment, resulting in `key = 'hello`.
- **Impact**: Low — the generated `project.toml` only uses double quotes, and the parser docs say "minimal subset." But if a user hand-edits the TOML with single quotes, values would silently truncate.
- **Acceptance**: `_strip_inline_comment` tracks both `'` and `"` as string delimiters. Test: `parse_simple_toml("key = 'has # inside'")` returns `{"key": "has # inside"}`.
- **Validation**:
  ```
  python -m pytest tests/test_pipeline_scripts.py -k "single_quote_comment" -v
  # New test: single-quoted string with # is preserved
  ```
- **Status**: RESOLVED (806dfbb)

### P6-13: `_parse_value` silently accepts unquoted strings, masking config errors
- **File**: `scripts/validate_config.py:209-210`
- **Bug**: When a value doesn't match bool, string, array, or int, it falls through to `return raw`. This means `key = hello world` (without quotes) is silently accepted as the string `"hello world"`. TOML spec requires strings to be quoted. This lenience masks config errors.
- **Impact**: Users who forget to quote values won't get an error. The value might work by accident or produce subtle bugs if it contains TOML metacharacters.
- **Acceptance**: Either (a) log a warning for unquoted string values, or (b) document the lenient behavior as intentional in the parser docstring.
- **Validation**:
  ```
  python -m pytest tests/test_pipeline_scripts.py -k "unquoted_string" -v
  # If (a): test verifies warning is emitted for unquoted strings
  # If (b): test documents and asserts the lenient behavior
  ```
- **Status**: RESOLVED (806dfbb)

### P6-14: Multiple test files use `os.chdir` without `addCleanup` safety net
- **File**: `tests/test_lifecycle.py:154`, `tests/test_release_gate.py:395`
- **Bug**: Both files save cwd in setUp and restore in tearDown. But if setUp fails AFTER `os.chdir()` but BEFORE the test runs (or if the test method itself crashes in a way that prevents tearDown), cwd remains changed for subsequent test classes. Pass 5 fixed this in `test_hexwise_setup.py` with `addClassCleanup` but the same pattern persists in 2 other test files.
- **Impact**: A test crash could leave cwd changed, causing cascading failures in subsequent tests. Flaky on CI.
- **Acceptance**: Both files use `self.addCleanup(os.chdir, saved_cwd)` immediately after `os.chdir()` to guarantee restoration.
- **Validation**:
  ```
  grep -n "os.chdir" tests/test_lifecycle.py tests/test_release_gate.py
  # Every os.chdir should be immediately followed by addCleanup
  python -m pytest tests/ -v  # All still pass
  ```
- **Status**: RESOLVED (f409f15)

### P6-15: sprint-monitor SKILL.md describes auto-merge behavior that doesn't exist
- **File**: `skills/sprint-monitor/SKILL.md:167`
- **Bug**: SKILL.md says to merge PRs "using the strategy from `project.toml [conventions] merge_strategy`". But `check_status.py` only REPORTS approved PRs — it never calls `gh pr merge`. The merge is done by sprint-run during story execution, not by sprint-monitor.
- **Impact**: Anyone reading the SKILL.md would think sprint-monitor auto-merges PRs, which it does not.
- **Acceptance**: SKILL.md language clarified to say "report ready-to-merge PRs" rather than implying it performs the merge.
- **Validation**:
  ```
  grep -n "merge" skills/sprint-monitor/SKILL.md
  # No language implying sprint-monitor performs merges
  ```
- **Status**: RESOLVED (0d8445b)

### P6-16: `load_config()` calls `sys.exit(1)` instead of raising an exception
- **File**: `scripts/validate_config.py:468`
- **Bug**: `load_config()` is a library function used by 8+ scripts. On validation failure, it calls `sys.exit(1)` instead of raising an exception. This makes it impossible to use in library context, difficult to test without catching SystemExit, and violates the principle that only `main()` should call sys.exit.
- **Impact**: Any script that wants to handle config errors gracefully (e.g., retry, use defaults, show UI) can't — the function kills the process. Tests must use `self.assertRaises(SystemExit)`.
- **Acceptance**: `load_config()` raises `ConfigError` (or `ValueError`) on failure. The `sys.exit(1)` moves to each script's `main()` function. Existing behavior preserved — scripts still exit on bad config.
- **Validation**:
  ```
  python -m pytest tests/ -k "load_config" -v
  # New test: load_config with bad config raises ValueError, not SystemExit
  # All existing tests still pass (callers catch the exception or it propagates to main)
  ```
- **Status**: RESOLVED (e22e0e1)

### P6-17: `write_tf` frontmatter doesn't escape values containing YAML-sensitive characters
- **File**: `skills/sprint-run/scripts/sync_tracking.py:153-173`
- **Bug**: `write_tf` writes `key: {value}` directly. If `tf.title` contains a colon-space sequence like `"Feat: Add auth"`, the written frontmatter is `title: Feat: Add auth`. `read_tf` uses `re.search(rf"^title:\s*(.+)")` which correctly captures everything after `title:` as one value. But if a value starts with YAML special chars (`[`, `{`, `>`, `|`, `*`, `&`), YAML-aware tools that read the same frontmatter could misinterpret it.
- **Impact**: Low for giles itself (it uses regex parsing, not YAML). But if users or external tools parse tracking files as YAML, values could be misinterpreted. Defensive quoting would make the format robust.
- **Acceptance**: Values containing `: ` or YAML special chars are quoted in the frontmatter output. Round-trip test: write → read recovers identical values for edge-case titles.
- **Validation**:
  ```
  python -m pytest tests/test_gh_interactions.py -k "write_tf_escaping" -v
  # New test: title with colons round-trips correctly
  # New test: title starting with [ or { round-trips correctly
  ```
- **Status**: RESOLVED (a82ecf5)

---

## LOW

### P6-18: `_parse_workflow_runs` joins multiline blocks with `&&` incorrectly
- **File**: `scripts/sprint_init.py:218`
- **Bug**: Multiline `run: |` blocks are collected and joined with `" && "`. But a multiline run block could contain a single multi-line command (e.g., a heredoc, a Python one-liner with `\`, or a pipe chain). Joining all lines with `&&` turns them into separate commands.
- **Fix**: Join with `\n` or `;` instead of `&&`, or skip multiline blocks and only extract single-line `run:` values.
- **Status**: RESOLVED (e6a1f72)

### P6-19: `generate_release_notes` compare link branch never tested with real prior tag
- **File**: `skills/sprint-release/scripts/release_gate.py:361-378`
- **Bug**: `git rev-parse --verify refs/tags/{prev_tag}` runs against real git (not FakeGitHub). In test environments, temp repos never have prior semver tags, so the code always takes the "initial release" path (line 373-378). The "compare link" path (lines 366-371) is never exercised.
- **Fix**: Test_lifecycle or test_release_gate should create a v0.1.0 tag in the temp repo before testing release notes generation with a v0.2.0 release.
- **Status**: RESOLVED (c744749)

### P6-20: `do_release` pre-flight doesn't handle git errors gracefully
- **File**: `skills/sprint-release/scripts/release_gate.py:416-420`
- **Bug**: `r = subprocess.run(["git", "status", "--porcelain"], ...)`. If git is not installed or not a git repo, `r.returncode != 0` catches it, but the error message ("working tree is not clean") is misleading — the actual problem is "not a git repository."
- **Fix**: Separate the "not a git repo" and "dirty working tree" error messages.
- **Status**: RESOLVED (129e979)

### P6-21: `do_sync` uses runtime `sys.path` mutation for lazy imports
- **File**: `scripts/sync_backlog.py:145-149`
- **Bug**: Appends to `sys.path` and imports `bootstrap_github` and `populate_issues` at call time. If these modules were previously imported with a different path (e.g., from a test that manipulated sys.path), Python's module cache returns the stale import.
- **Fix**: Use a consistent import strategy. Either import at module level with a guarded `try/except`, or use `importlib` for explicit reloading.
- **Status**: RESOLVED (6b7a52e)

### P6-22: `_parse_team_index` doesn't validate row cell count vs header count
- **File**: `scripts/validate_config.py:414-418`
- **Bug**: If a data row has fewer cells than headers, the row dict silently misses some keys. If it has more cells, extras are dropped. Downstream code uses `.get()` with defaults so it doesn't crash, but a malformed INDEX.md could produce personas with empty names.
- **Fix**: Log a warning if cell count doesn't match header count.
- **Status**: RESOLVED (ee72a3a)

### P6-23: Batch fix commits from Mar 13 are impossible to bisect
- **File**: Git history
- **Bug**: Not a code bug — a process issue. Commits like "fix: batch resolve P5-05/06/.../40" touch 18+ punchlist items in one commit. If any of those fixes introduced a regression, `git bisect` would point at the mega-commit and require manual triage.
- **Fix**: Future fix passes should commit one item per commit (or small related groups of 2-3).
- **Status**: ACKNOWLEDGED (process note)

### P6-24: Line-number index files (CLAUDE.md, CHEATSHEET.md) are churn amplifiers
- **File**: `CLAUDE.md`, `CHEATSHEET.md`
- **Bug**: Not a code bug — a design tradeoff. These files contain line-number references (`:47`, `:280`) that go stale with every code change. They account for 23 of the last 50 file changes (46% of churn). The `verify_line_refs.py` script mitigates this but doesn't prevent the churn.
- **Impact**: Every code change requires a doc update. Reviewers must check line-number drift. The maintenance cost may exceed the navigation benefit.
- **Fix**: Consider replacing line-number references with function-name references or grep-able anchors (e.g., `# ANCHOR: parse_simple_toml`) that don't drift when surrounding code changes.
- **Status**: ACKNOWLEDGED (process/design note)

---

## Summary

| Severity | Count | Description |
|----------|-------|-------------|
| HIGH     | 8     | FakeGitHub blind spots, untested monitoring features, release error recovery, integration gap |
| MEDIUM   | 9     | Phantom features, TOML parser gaps, test safety, doc-code mismatch |
| LOW      | 7     | Workflow parsing, process issues, design considerations |
| **Total** | **24** | |

### Recommended Fix Order

**Phase 1 — FakeGitHub fidelity (P6-01, P6-07, P6-11)**: Fix the test double's blind spots first. This unblocks honest testing for many other items. The single-dash flag fix is foundational.

**Phase 2 — Untested monitoring features (P6-02, P6-05, P6-06)**: Add FakeGitHub endpoints for compare, commits, and timeline APIs. Write tests that actually exercise branch divergence, direct push detection, and timeline-based PR linking.

**Phase 3 — Error recovery (P6-03, P6-04)**: Fix the release notes cleanup gap and hardcoded path. These are small, surgical fixes with clear acceptance criteria.

**Phase 4 — Integration test (P6-08)**: Add the sprint-run monitoring pipeline integration test. This is the highest-value new test — it covers the data flow between 3 scripts that has never been verified.

**Phase 5 — Phantom features (P6-09, P6-10, P6-15)**: Decide: implement `merge_strategy`/`branch_pattern`/`commit_style` or remove them. Either way, eliminate the doc-code mismatch.

**Phase 6 — Remaining medium + low items**: Work through P6-12 through P6-24 in order.

### What's Different About Pass 6

Pass 5 caught surface bugs (off-by-one, missing coverage, substring matches). Pass 6 found structural issues that require understanding how the system works as a whole:

1. **The test double has a blind spot in its own enforcement mechanism.** `_check_flags` was Pass 5's big fix, but it only works for `--` flags. Short flags bypass it entirely.

2. **Three monitoring features exist in production code but have zero test coverage.** They silently fail in tests because FakeGitHub doesn't handle their API endpoints. The tests pass because the error is caught. This is the most dangerous kind of "coverage" — it looks covered at a distance but is completely hollow.

3. **Three config keys are generated, documented, and never consumed.** This is the "phantom feature" pattern — it erodes trust in documentation and config.

4. **The sprint-run monitoring phase has never been tested as a pipeline.** Each script works in isolation, but the data flow between them is unverified. This is where integration bugs hide.
