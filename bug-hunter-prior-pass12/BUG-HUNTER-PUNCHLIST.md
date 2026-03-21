# Bug Hunter Pass 12 — Adversarial Legacy Code Review

**Date:** 2026-03-15
**Scope:** Full project (19 scripts, 12 test files, 5 test infra files, all docs)
**Method:** Manual deep-read of all source + 3 parallel audit agents + cross-cutting analysis
**Sources:** audit/3-code-audit-cross-cutting.md, audit/3-code-audit-batch2.md, audit/2-test-quality-batch1.md, audit/2-test-quality-batch2.md, recon/0d-lint-results.md, recon/0f-skipped-tests.md

---

## Priority Legend

| Priority | Meaning |
|----------|---------|
| **P0** | Production logic bugs — wrong behavior in real usage |
| **P1** | Test infrastructure defeats its own purpose — provides false confidence |
| **P2** | Test quality issues that mask bugs — coverage looks good but isn't |
| **P3** | Code quality and minor correctness gaps |
| **P4** | Maintenance, style, and structural improvements |

---

## P0 — Production Logic Bugs

### P12-001: `do_release` rollback leaves orphaned commit on remote

- **File:** `skills/sprint-release/scripts/release_gate.py:482-488, 534-537, 590-594`
- **Bug:** When GitHub Release creation fails after the version bump commit was pushed, `_rollback_commit()` does `git reset --hard` locally but does NOT force-push to remove the commit from the remote. The tag is deleted (both local and remote via `_rollback_tag`), but the version bump commit remains on the remote branch.
- **Impact:** Remote has orphaned version bump commit (no release), local HEAD diverges from remote, next push fails, anyone pulling gets a version bump with no release.
- **Acceptance criteria:**
  1. After a failed GitHub Release, the remote branch must not contain the version bump commit
  2. OR the rollback must create a revert commit (safer than force-push) and push it
  3. Test must simulate: push succeeds → release creation fails → verify remote state is clean
- **Validation:** `grep -n "force\|revert\|push" skills/sprint-release/scripts/release_gate.py | grep -i rollback` should show the rollback function addresses the remote state. New test in `test_release_gate.py` must assert post-rollback remote state.

### P12-002: `get_linked_pr` returns first merged PR, not latest

- **File:** `skills/sprint-run/scripts/sync_tracking.py:73-81`
- **Bug:** The `break` on line 81 stops at the first merged PR in the timeline (chronologically oldest). For stories with multiple linked PRs (failed first attempt → successful redo), this returns the wrong PR. Pass 11 (BH-P11-101) flagged this but the "fix" only documented existing behavior — the `break` was not changed.
- **Impact:** Story tracking files link to the wrong PR. Status shown to user may reflect abandoned work instead of the actual implementation.
- **Acceptance criteria:**
  1. `get_linked_pr` must return the most recently merged PR when multiple exist
  2. If an open PR exists, prefer it over merged PRs (current behavior, correct)
  3. If no open PR, prefer the latest merged PR (not earliest)
- **Validation:** New test: create timeline with 2 merged PRs (merged_at timestamps differ), assert the one with the later `merged_at` is returned.
  ```
  python -m pytest tests/test_gh_interactions.py -k "linked_pr" -v
  ```

### P12-003: Sprint heading regex inconsistency across scripts

- **File:** Multiple: `populate_issues.py`, `bootstrap_github.py`, `sprint_init.py`
- **Bug:** Four different patterns parse sprint headers:
  - `_SPRINT_HEADER_RE` requires colon (`### Sprint (\d+):`)
  - `_collect_sprint_numbers` requires colon
  - `_infer_sprint_number` does NOT require colon (`^###\s+Sprint\s+(\d+)`)
  - `check_milestone` matches milestone title (`^Sprint {N}\b`)
  A heading `### Sprint 1` (no colon) would be detected by `_infer_sprint_number` for epic enrichment but NOT by `_SPRINT_HEADER_RE` for story parsing or by `_collect_sprint_numbers` for label creation. Stories get sprint numbers that don't have corresponding labels/milestones.
- **Acceptance criteria:**
  1. All sprint heading regexes must agree on whether the colon is required
  2. Either all require it (and document this as a format requirement) or none do
  3. Skeleton template `milestone.md.tmpl` must match the chosen format
- **Validation:**
  ```bash
  grep -rn "Sprint.*\\\\d\|Sprint.*[0-9]" scripts/ skills/ --include="*.py" | grep -i "re\.\|_RE\|pattern\|regex\|match"
  ```
  All patterns should be consistent. New test: parse a milestone file with `### Sprint 1` (no colon) through the full pipeline, verify labels AND issues are created.

### P12-029: `renumber_stories` crashes on backslash-containing IDs (regex injection)

- **File:** `scripts/manage_epics.py:347-363`
- **Bug:** `re.sub()` uses user-supplied `new_ids` as the replacement string without escaping. In Python's `re.sub`, the replacement string interprets `\1`, `\2`, etc. as backreferences. A story ID containing `\1` causes `re.error: invalid group reference`.
- **Impact:** Crash when renumbering stories with backslash-containing IDs. CLI accepts arbitrary arguments.
- **Acceptance criteria:**
  1. `renumber_stories` must not crash on IDs containing backslashes
  2. Use `lambda m: replacement` instead of raw replacement string, or escape backslashes
- **Validation:** New test: call `renumber_stories` with `new_ids=[r"US-01\1a"]`, verify no crash and correct substitution.

### P12-030: CI YAML injection via newline-containing commands in `check_commands`

- **File:** `skills/sprint-setup/scripts/setup_ci.py:94-113`
- **Bug:** `generate_ci_yaml` interpolates CI commands from `project.toml` directly into YAML string concatenation. A command containing a newline character produces an invalid or dangerous CI workflow (e.g., injecting an `env:` block with secrets).
- **Impact:** Generated `.github/workflows/ci.yml` could contain unintended steps. Self-inflicted (config is local), but could produce silent CI breakage or security issues.
- **Acceptance criteria:**
  1. Commands must be quoted or escaped before YAML interpolation
  2. Newline characters in commands must be rejected or properly handled
  3. Test must verify a command with embedded newline doesn't produce raw YAML injection
- **Validation:** New test: `generate_ci_yaml` with `check_commands=["cargo test\n    env:\n      SECRET: x"]`, verify the output is valid YAML and the injected `env:` block is NOT present as a separate YAML key.

### P12-031: `create_milestones_on_github` uses `{owner}/{repo}` template variables inconsistently

- **File:** `skills/sprint-setup/scripts/bootstrap_github.py:249-254`
- **Bug:** Milestone creation uses `gh api repos/{owner}/{repo}/milestones` — relying on `gh api`'s template variable expansion. Label creation uses `gh label create` — a higher-level command that auto-detects the repo. If `gh api` template expansion fails (wrong git remote, detached HEAD), milestone creation gets a 404 while label creation succeeds, producing a partial bootstrap.
- **Impact:** Partial bootstrap state — labels exist, milestones don't. Subsequent populate_issues fails because it can't find milestones.
- **Acceptance criteria:**
  1. Either both use `gh api` with template variables, or both use higher-level commands
  2. OR add error handling that detects partial bootstrap and reports which step failed
- **Validation:** New test: FakeGitHub test that verifies label and milestone creation succeed together, and that a milestone creation failure produces a clear error (not silent partial state).

---

## P1 — Test Infrastructure Defeats Its Own Purpose

### P12-004: Golden replay compares file names only, not content

- **File:** `tests/golden_replay.py:137-175`
- **Bug:** `assert_files_match()` compares only the set of relative file paths between recorded and current state. The recorder (`golden_recorder.py:78-101`) captures full file contents, but the replayer never reads or compares them. The entire purpose of golden testing — catching content regressions — is defeated.
- **Impact:** A production regression that changes generated file content (wrong TOML structure, malformed persona template, broken symlink target) passes the golden test as long as the same files exist.
- **Acceptance criteria:**
  1. `assert_files_match` must compare file contents, not just paths
  2. Content comparison must handle expected differences (timestamps, absolute paths) via an allowlist or normalization
  3. A test must prove: change a recorded file's content → golden replay fails
- **Validation:**
  ```bash
  grep -n "read_text\|content\|compare" tests/golden_replay.py
  ```
  Should show content comparison logic in `assert_files_match`. Regression test: modify a golden recording's file content, run `python -m pytest tests/test_golden_run.py -v`, expect failure.

### P12-005: Property tests for `_parse_team_index` test a reimplemented parser

- **File:** `tests/test_property_parsing.py:394-458`
- **Bug:** The test admits (line 392): "We can't easily call _parse_team_index with hypothesis because it reads from a file. Instead, we test the regex logic it uses by extracting the core parsing into test cases that use the same patterns." The test reimplements the parsing loop inline and asserts against its own reimplementation. If production `_parse_team_index` diverges (which it already has — BH-P11-109 added whitespace-stripping), these tests still pass.
- **Impact:** Testing a copy-paste of the algorithm, not the actual production code. Any production bug not replicated in the test copy goes undetected.
- **Acceptance criteria:**
  1. Property tests must call the actual `_parse_team_index` function
  2. Strategy generates valid team index markdown → writes to temp file → calls production function → asserts structural invariants
  3. Remove the inline reimplementation
- **Validation:**
  ```bash
  grep -n "_parse_team_index" tests/test_property_parsing.py
  ```
  Should show direct imports and calls to the production function, not inline reimplementation.

### P12-006: Property test TOML strategy avoids the hardest characters

- **File:** `tests/test_property_parsing.py:264-270`
- **Bug:** The `_toml_string_val` strategy blacklists `'"\\#\n\r'` — the exact characters that require escaping in TOML and are the most likely to trigger parser bugs. The custom TOML parser is a documented complexity hotspot. Property tests that systematically avoid the hardest cases provide false confidence.
- **Impact:** Strings like `value = "path\\to\\file"` or `value = "say \"hello\""` are never generated. Parser bugs with escape sequences go untested by the fuzz engine.
- **Acceptance criteria:**
  1. Remove the character blacklist from `_toml_string_val`
  2. The `_toml_line` helper must properly escape special characters in generated TOML
  3. Property tests must exercise strings containing `\`, `"`, `#`, and newlines (within quoted values)
  4. If the custom parser can't handle these (known limitation), document it and add skip logic, don't silently avoid them
- **Validation:** Run hypothesis with increased examples and verify special characters are tested:
  ```bash
  python -m pytest tests/test_property_parsing.py -k "toml" -v --hypothesis-seed=0
  ```

### P12-007: 12 core scripts in `_KNOWN_UNTESTED` — coverage gate is too permissive

- **File:** `tests/test_verify_fixes.py:864-877`
- **Bug:** The `TestEveryScriptMainCovered._KNOWN_UNTESTED` frozenset grandfathers 12 scripts including: `release_gate`, `bootstrap_github`, `populate_issues`, `setup_ci`, `update_burndown`, `validate_config`. These are the most critical pipeline scripts. The gate test prevents NEW scripts from bypassing testing but doesn't address the existing gap.
- **Impact:** These 12 scripts could have bugs in main() entry points (argument parsing, error handling, exit codes) that no test exercises. `release_gate.main()` orchestrates versioning, tagging, and release publishing.
- **Acceptance criteria:**
  1. Add main() integration tests for at least the 4 highest-risk scripts: `release_gate`, `bootstrap_github`, `populate_issues`, `validate_config`
  2. Remove those 4 from `_KNOWN_UNTESTED`
  3. Each new main() test must verify: correct exit code, expected stdout/stderr content, no unhandled exceptions
- **Validation:**
  ```bash
  python -c "
  import ast, sys
  tree = ast.parse(open('tests/test_verify_fixes.py').read())
  for node in ast.walk(tree):
      if isinstance(node, ast.Assign):
          for t in node.targets:
              if hasattr(t, 'attr') and t.attr == '_KNOWN_UNTESTED':
                  print(ast.literal_eval(node.value))
  "
  ```
  Should show 8 or fewer scripts (down from 12).

---

## P2 — Test Quality Issues That Mask Bugs

### P12-008: `do_release` happy path mocks away the code under test

- **File:** `tests/test_release_gate.py:527-591`
- **Bug:** `test_happy_path` patches 5 things: `calculate_version`, `write_version_to_toml`, `subprocess.run`, `find_milestone_number`, and `gh`. Then asserts the mocks were called in order. Never verifies actual orchestration — if `do_release` reordered steps (pushed before tagging), all assertions still pass.
- **Impact:** False confidence that the release flow works end-to-end.
- **Acceptance criteria:**
  1. At least one `do_release` test uses FakeGitHub instead of global mocks
  2. Test verifies actual state changes: release created, milestone closed, version file updated
  3. Existing mock-based test can remain as a call-sequence check, but must not be the only test
- **Validation:** `grep -n "FakeGitHub\|fake_gh" tests/test_release_gate.py` should show FakeGitHub usage in at least one do_release test.

### P12-009: Dry-run integration test mock produces invalid git log format

- **File:** `tests/test_release_gate.py:1090-1155`
- **Bug:** `_make_side_effect` simulates `git log` as `"abc1234 feat: add new feature\n..."`. But production `parse_commits_since` uses `--format="%s\n%b\x00--END--\x00"`. The mock's output lacks the `\x00--END--\x00` delimiter, so `parse_commits_since` parses it as a single malformed commit. The `"abc1234"` hash prefix becomes part of the subject, breaking conventional commit detection. Test asserts `"1.0.0" in output` which passes regardless because "1.0.0" appears in the base version output.
- **Acceptance criteria:**
  1. Mock must produce `\x00--END--\x00`-delimited output matching the real `git log --format` string
  2. Assertion must verify the calculated version (e.g., `assertIn("1.1.0", output)` for a feat commit → minor bump)
  3. OR the test must be rewritten to use real git commits in a temp repo
- **Validation:** The calculated version in the dry-run output must reflect the commit types (feat → minor, fix → patch).

### P12-010: `check_direct_pushes` jq filter path not tested

- **File:** `tests/test_gh_interactions.py:1491-1565`
- **Bug:** Production uses a complex `--jq` filter that selects commits with exactly 1 parent (direct pushes, not merges) and reshapes output. When `jq` is not installed, FakeGitHub falls back to raw JSON. The test passes either way without distinguishing which code path ran. A broken jq expression would go undetected.
- **Acceptance criteria:**
  1. Split into two tests: one that requires jq (skips if unavailable), one that tests the no-jq fallback
  2. The jq test must verify merge commits ARE excluded from the count
  3. The no-jq test must verify the graceful degradation path
- **Validation:** `python -m pytest tests/test_gh_interactions.py -k "direct_push" -v` should show 2+ test methods.

### P12-011: `gate_stories` test doesn't verify `--state open` filter value

- **File:** `tests/test_gh_interactions.py:318-328`
- **Bug:** `test_all_closed` checks `"--state" in call_args` but never verifies the value is `"open"`. If production changed to `--state all` or `--state closed`, the gate would produce wrong results but the test would still pass.
- **Acceptance criteria:**
  1. Assert both `"--state"` and `"open"` are consecutive in `call_args`
  2. OR assert the full argument list fragment `["--state", "open"]` is a subsequence
- **Validation:** `grep -A2 "state.*call_args\|call_args.*state" tests/test_gh_interactions.py` should show value verification.

### P12-012: FakeGitHub PATCH milestone doesn't update state

- **File:** `tests/fake_github.py:362-364`
- **Bug:** PATCH on milestones returns `self._ok("{}")` without modifying the milestone's state. Production code calls PATCH to close milestones after release. Any test that queries milestone state after a PATCH sees stale data.
- **Acceptance criteria:**
  1. `_handle_api` PATCH for milestones must update the milestone's `state` field
  2. Also update `closed_at` timestamp when state changes to "closed"
  3. Test: create milestone → PATCH state=closed → query milestone → assert state=="closed"
- **Validation:** `grep -A5 "PATCH.*milestone\|milestone.*PATCH" tests/fake_github.py` should show state mutation logic.

### P12-013: FakeGitHub `--search` only handles `milestone:` pattern

- **File:** `tests/fake_github.py:497-554`
- **Bug:** `_issue_list` parses `--search` via `_extract_search_milestone`, which only understands `milestone:"X"`. Any other search pattern (label, state compound queries) is silently ignored — issues returned unfiltered. But `--search` is registered as `_IMPLEMENTED_FLAGS`, so strict mode doesn't warn.
- **Acceptance criteria:**
  1. Either downgrade `search` from `_IMPLEMENTED_FLAGS` to `_KNOWN_FLAGS` (strict mode warns on use)
  2. OR document the partial implementation with an inline comment listing supported patterns
  3. If left as _IMPLEMENTED, add a strict-mode warning when an unrecognized search predicate is used
- **Validation:** `grep -B2 -A2 "search.*IMPLEMENTED\|IMPLEMENTED.*search" tests/fake_github.py` should show the fix.

---

## P3 — Code Quality and Minor Correctness

### P12-014: `parse_requirements` hardcoded to `reference.md` filename

- **File:** `scripts/traceability.py:114`
- **Bug:** `prd_path.rglob("reference.md")` only finds files literally named `reference.md`. Other naming conventions silently produce 0 requirements.
- **Acceptance criteria:** Either scan for `*.md` files in the PRD directory, or make the filename pattern configurable in `project.toml`.
- **Validation:** `grep -n "rglob\|glob" scripts/traceability.py` should show a broader pattern or configuration.

### P12-015: No duplicate story ID detection in `parse_milestone_stories`

- **File:** `skills/sprint-setup/scripts/populate_issues.py:93-128`
- **Bug:** Same US-XXXX story ID in multiple milestone files silently creates duplicate Story objects. Idempotency in `create_issue` catches the duplicate creation, but the first one may have wrong metadata.
- **Acceptance criteria:** `parse_milestone_stories` should warn or deduplicate when the same story ID appears multiple times.
- **Validation:** New test: parse milestone files with duplicate story ID, verify warning is emitted or only one Story object is returned.

### P12-016: `_yaml_safe` doesn't quote YAML boolean keywords

- **File:** `skills/sprint-run/scripts/sync_tracking.py:171-186`
- **Bug:** Values like `true`, `false`, `yes`, `no`, `null` pass through unquoted. Read back, they'd be parsed as booleans/null, not strings.
- **Acceptance criteria:** `_yaml_safe` must quote YAML boolean keywords (case-insensitive: true, false, yes, no, on, off, null).
- **Validation:** `python -c "from sync_tracking import _yaml_safe; assert _yaml_safe('true').startswith('\"')"` (after adding to sys.path).

### P12-017: `write_version_to_toml` regex matches `[release]` in comments

- **File:** `skills/sprint-release/scripts/release_gate.py:280`
- **Bug:** `r"^\[release\]"` matches lines like `# See [release] notes`.
- **Acceptance criteria:** Regex should exclude lines starting with `#` (TOML comments).
- **Validation:** New test: TOML with `# [release]` comment before actual `[release]` section, verify version is written at correct position.

### P12-018: `gh_json` return type not validated in gate functions

- **File:** `skills/sprint-release/scripts/release_gate.py:141-148, 174-193`
- **Bug:** `gate_stories` and `gate_prs` directly iterate `gh_json()` results without `isinstance(result, list)` check. If `gh_json` returns a dict, iteration would produce dict keys.
- **Acceptance criteria:** Both functions should validate `isinstance(result, list)` and handle the error case.
- **Validation:** `grep -A3 "gh_json" skills/sprint-release/scripts/release_gate.py | grep -c "isinstance"` should be >= 2.

### P12-019: 11 unused imports across 9 files

- **File:** See `recon/0d-lint-results.md` for full list
- **Bug:** Dead imports indicate incomplete refactoring. `sync_tracking.py` has 4 unused imports.
- **Acceptance criteria:** Remove all 11 unused imports.
- **Validation:** `python -m py_compile <file>` still passes for each file. `flake8 --select=F401 scripts/ skills/ --exclude=__pycache__` returns 0 results.

### P12-020: `do_sync` counts milestone files, not actual creations

- **File:** `scripts/sync_backlog.py:173`
- **Bug:** `result["milestones"] = len(milestone_files)` counts files, not milestones actually created on GitHub. If creation partially fails, the count is wrong.
- **Acceptance criteria:** Count should reflect actual GitHub milestones created (return value from `create_milestones_on_github`).
- **Validation:** New test: simulate partial milestone creation failure, verify `do_sync` returns the correct (lower) count.

### P12-021: Empty f-string in `populate_issues.py:74`

- **File:** `skills/sprint-setup/scripts/populate_issues.py:74`
- **Bug:** f-string with no `{}` placeholders — either a bug (intended interpolation) or leftover.
- **Acceptance criteria:** Either add the intended placeholder or convert to a regular string.
- **Validation:** `flake8 --select=F541 skills/sprint-setup/scripts/populate_issues.py` returns 0 results.

### P12-022: Unused variable `sprint_dir` in `check_status.py:387`

- **File:** `skills/sprint-monitor/scripts/check_status.py:387`
- **Bug:** Variable assigned but never used.
- **Acceptance criteria:** Remove the unused assignment.
- **Validation:** `flake8 --select=F841 skills/sprint-monitor/scripts/check_status.py` returns 0 results.

### P12-032: Separator rows leak into metadata dicts in epic/saga parsers

- **File:** `scripts/manage_epics.py:70-86`, `scripts/manage_sagas.py:65-77`
- **Bug:** `TABLE_ROW` regex matches markdown separator rows (`|-------|-------|`) as data rows. The downstream filter checks for `"Field"`, `"---"`, `""` but not `"-------"` (7 dashes). Metadata dicts get polluted with `{"-------": "-------"}`.
- **Acceptance criteria:** Filter must catch all separator-like values (e.g., `field.strip("-") == ""`).
- **Validation:** New test: parse an epic with separator row, verify metadata dict has no dash-only keys.

### P12-033: `update_sprint_status` drops last table row if file lacks trailing newline

- **File:** `skills/sprint-run/scripts/update_burndown.py:108`
- **Bug:** Regex `r"## Active Stories[^\n]*\n(?:(?!\n## )[^\n]*\n)*"` requires each line to end with `\n`. If the Active Stories section is last and the file has no trailing newline, the final data row is not matched and becomes an orphan below the new table.
- **Acceptance criteria:** Regex must handle files with or without trailing newlines.
- **Validation:** New test: write SPRINT-STATUS.md without trailing newline, run `update_sprint_status`, verify no orphaned rows.

### P12-034: Short test case IDs produce false positive coverage matches

- **File:** `scripts/test_coverage.py:121-134`
- **Bug:** Fuzzy slug matching for `TC-E-1` produces slug `e_1`. The word-boundary regex `(?:^|_)e_1(?:$|_)` matches unrelated functions like `test_type_e_1_setup`.
- **Acceptance criteria:** Fuzzy matching must require the slug to match a meaningful portion of the function name (not just a substring between underscores).
- **Validation:** New test: `TC-E-1` should NOT match `test_type_e_1_setup`.

### P12-035: Duplicate section headings in saga files cause silent data loss

- **File:** `scripts/manage_sagas.py:126-147`
- **Bug:** `_find_section_ranges` builds a dict keyed by heading text. Duplicate `## Team Voices` sections → only the last one is retained. Updates target the wrong section.
- **Acceptance criteria:** Either warn on duplicate headings or use a list-based approach that preserves all sections.
- **Validation:** New test: saga with two `## Team Voices` sections, verify both are accessible.

---

## P4 — Maintenance and Structural Improvements

### P12-023: Pipeline test code duplicated 3x across test files

- **File:** `tests/test_hexwise_setup.py:341-407`, `tests/test_lifecycle.py:275-327`, `tests/test_golden_run.py:115-214`
- **Issue:** Nearly identical pipeline orchestration code (config → labels → milestones → issues) copy-pasted across three test files. When the pipeline API changes, all three must be updated.
- **Acceptance criteria:** Extract shared `run_full_pipeline(fake_gh, config)` helper. All three test files use it.
- **Validation:** `grep -rn "create_static_labels\|create_persona_labels\|create_milestones" tests/test_*.py | wc -l` should decrease by ~60%.

### P12-024: `TestCheckMilestone` uses call-order-based mock dispatch

- **File:** `tests/test_gh_interactions.py:1922-1978`
- **Issue:** `_mock_gh_json` returns different data based on `call_count[0]`, coupling the test to production code's call sequence. Refactoring production to query in different order would silently break tests.
- **Acceptance criteria:** Replace call-order dispatch with argument-inspecting side effects that return milestones or issues based on what's being queried.

### P12-025: Three "never crashes" hypothesis tests have zero assertions

- **File:** `tests/test_property_parsing.py:103-106, 173-175, 186-189`
- **Issue:** Call production function but assert nothing about the return value. `extract_story_id` returning `None` for all inputs would pass.
- **Acceptance criteria:** Add at minimum return-type assertions (e.g., result is `str | None`, result is `int`).

### P12-026: `test_lifecycle` reimplements burndown row-building logic

- **File:** `tests/test_lifecycle.py:400-461`
- **Issue:** Phase 2 of the monitoring pipeline test manually builds burndown rows instead of calling production code. Tests the shared utility functions individually but assembles them in a test-specific way.
- **Acceptance criteria:** Call production burndown-building function instead of reimplementing the assembly.

### P12-027: Golden test silently skips when recordings absent (locally)

- **File:** `tests/test_golden_run.py:93-113`
- **Issue:** Missing golden recordings → `self.skipTest()` locally, only fails in CI. A developer could run the full suite, see green, and push without golden coverage.
- **Acceptance criteria:** Either always fail on missing recordings, or print a prominent warning that's hard to miss.

### P12-028: `test_verify_fixes.test_source_uses_replace_not_format` inspects source code

- **File:** `tests/test_verify_fixes.py:605-612`
- **Issue:** Uses `inspect.getsource()` to check implementation details. Companion behavior tests already verify the actual safety property. This test breaks on valid refactors.
- **Acceptance criteria:** Remove the source inspection test; the behavior tests at lines 587-603 are sufficient.

---

## Metrics

| Category | Count | Resolved |
|----------|-------|----------|
| P0 (production bugs) | 6 | 6 |
| P1 (test infra defeats purpose) | 4 | 4 |
| P2 (test quality masks bugs) | 6 | 6 |
| P3 (code quality / minor) | 13 | 13 |
| P4 (maintenance / structural) | 6 | 6 |
| **Total** | **35** | **35** |

## Resolution Summary

All 35 items resolved across 8 commits:

1. `c1d6ace` — Phase 1: Remove 11 unused imports across 9 files (P12-019, P12-021, P12-022)
2. `d147850` — Phase 2: Fix P3 code quality bugs (P12-014 thru P12-018, P12-032 thru P12-035)
3. `8044428` — Phase 3: Fix P0 production logic bugs (P12-001 thru P12-003, P12-029 thru P12-031)
4. `5f7f168` — Phase 4 batch 1: Test infra fixes (P12-004 thru P12-006, P12-011 thru P12-013)
5. `6a9e1b4` — Phase 4 batch 2: Hypothesis assertions + source inspection removal (P12-009, P12-025, P12-028)
6. `c98a9d6` — FakeGitHub do_release test + direct push test split (P12-008, P12-010)
7. `5d92e12` — main() integration tests for 4 critical scripts (P12-007)
8. `7e4c3cf` — Shared pipeline helper + structural fixes (P12-023, P12-024, P12-026, P12-027)

Test count: 634 → 643 (+9 net new tests). All passing.

---

## Validation Gate (run after all fixes)

```bash
# 1. Full test suite must pass
python -m pytest tests/ --tb=short -q

# 2. No unused imports
flake8 --select=F401,F541,F841 scripts/ skills/ --exclude=__pycache__ 2>/dev/null || echo "flake8 not available"

# 3. Anchor validation
python scripts/validate_anchors.py

# 4. Verify _KNOWN_UNTESTED shrank
python -c "
import ast
tree = ast.parse(open('tests/test_verify_fixes.py').read())
for node in ast.walk(tree):
    if isinstance(node, ast.Assign):
        for t in node.targets:
            if hasattr(t, 'attr') and t.attr == '_KNOWN_UNTESTED':
                untested = ast.literal_eval(node.value)
                print(f'_KNOWN_UNTESTED: {len(untested)} scripts: {sorted(untested)}')
                assert len(untested) <= 8, f'Expected <=8, got {len(untested)}'
"

# 5. Golden replay includes content comparison
python -c "
import inspect
from tests.golden_replay import GoldenReplay
src = inspect.getsource(GoldenReplay.assert_files_match)
assert 'read_text' in src or 'content' in src, 'assert_files_match must compare file contents'
"
```
