# Bug Hunter Punchlist — Pass 7

## Summary
| Metric | Value |
|--------|-------|
| Total items | 22 |
| Priority P0 (blocks correctness) | 3 |
| Priority P1 (real bug, needs fix) | 5 |
| Priority P2 (hardening / coverage gap) | 10 |
| Priority P3 (doc / hygiene) | 4 |
| Baseline tests | 467 pass, 0 fail |
| Final tests | 508 pass, 0 fail |
| All items fixed | YES |

### Sources
- Direct code audit of all 19 production scripts (~7,200 LOC)
- Doc-to-implementation audit: `audit/1-doc-claims.md` (19 discrepancies, 17 verified correct)
- Test quality audit: `audit/2-test-quality.md` (15 findings across 286 test methods)
- Git churn analysis: `recon/0e-churn.md` (52% fix commits in last 50)

---

## P0 — Blocks Correctness

### P7-01: `_split_array` ignores single-quoted strings
- **File:** `scripts/validate_config.py:240-265`
- **Bug:** `_split_array()` only tracks `"` for string boundary detection. Single-quoted array elements containing commas (e.g., `['has, comma', 'ok']`) split incorrectly on the inner comma.
- **Root cause:** P6-12 added single-quote support to `_parse_value()` (line 213) but `_split_array()` is called first on array contents and doesn't know about single quotes.
- **Impact:** Any TOML array with single-quoted elements containing commas will silently produce wrong data. While generated configs use double quotes, user-authored TOML can use single quotes per spec.
- **Acceptance criteria:**
  1. `parse_simple_toml("items = ['has, comma', 'ok']")` returns `{"items": ["has, comma", "ok"]}`
  2. `parse_simple_toml("mixed = ['a, b', \"c, d\"]")` returns `{"mixed": ["a, b", "c, d"]}`
  3. Existing double-quote array tests still pass
- **Validation:**
  ```
  python -m unittest tests.test_pipeline_scripts -v -k "single_quote"
  python -m unittest tests.test_pipeline_scripts -v -k "toml"
  python -m unittest discover tests/ -v 2>&1 | tail -1
  ```
- **Status:** fixed

### P7-02: `_infer_sprint_number` greedy regex matches prose
- **File:** `skills/sprint-setup/scripts/populate_issues.py:141`
- **Bug:** `re.search(r"Sprint\s+(\d+)", text)` matches the FIRST occurrence of "Sprint N" anywhere in the file — including prose paragraphs, references to other sprints, or sentences like "this builds on Sprint 1 work." A milestone-2 file that mentions Sprint 1 in its description would be inferred as sprint 1.
- **Root cause:** No heading anchor (`^###\s+Sprint`) or section boundary check.
- **Impact:** Wrong sprint number → issues created under wrong milestone. The bootstrap_github equivalent (`_collect_sprint_numbers`) has the same pattern but uses `### Sprint (\d+):` with heading anchors.
- **Acceptance criteria:**
  1. `_infer_sprint_number(path, "# Milestone 2\n\n### Sprint 2: Core\nThis builds on Sprint 1.")` → `2` (matches heading, not prose)
  2. `_infer_sprint_number(path, "No heading here\nRefers to Sprint 3 work.")` → falls back to filename
  3. Existing sprint number inference behavior preserved for well-formed files
- **Validation:**
  ```
  python -m unittest tests.test_gh_interactions -v -k "sprint_number"
  python -m unittest discover tests/ -v 2>&1 | tail -1
  ```
- **Status:** fixed

### P7-03: `gate_prs` client-side filtering misses PRs beyond limit
- **File:** `skills/sprint-release/scripts/release_gate.py:166-180`
- **Bug:** `gate_prs()` fetches all open PRs with `--limit 500` and filters client-side by milestone title. If a repo has >500 open PRs, milestone-targeted PRs beyond page 500 won't be found, and the gate will falsely pass. The `warn_if_at_limit(prs, 500)` call warns but the function still returns `True` for the unchecked PRs.
- **Root cause:** `gh pr list` doesn't support server-side milestone filtering. The workaround fetches "enough" but has no guarantee.
- **Impact:** Release gate could pass when milestone PRs exist — shipping unreleased code.
- **Acceptance criteria:**
  1. When `warn_if_at_limit` triggers (len == 500), `gate_prs` returns `(False, ...)` with a message about potential truncation
  2. Test covers the limit-hit path
- **Validation:**
  ```
  python -m unittest tests.test_gh_interactions -v -k "gate_prs"
  python -m unittest tests.test_release_gate -v -k "gate_prs"
  python -m unittest discover tests/ -v 2>&1 | tail -1
  ```
- **Status:** fixed

---

## P1 — Real Bug, Needs Fix

### P7-04: `_yaml_safe` misses trailing-colon values
- **File:** `skills/sprint-run/scripts/sync_tracking.py:165-179`
- **Bug:** `_yaml_safe()` checks for `': '` (colon-space) but not a trailing colon without space. A value like `"http:"` or `"note:"` wouldn't be quoted, but YAML parsers treat lines ending with `:` as mapping keys.
- **Impact:** Tracking files with trailing-colon values produce malformed YAML that would fail on re-parse.
- **Acceptance criteria:**
  1. `_yaml_safe("http:")` returns `'"http:"'`
  2. `_yaml_safe("note:")` returns `'"note:"'`
  3. `_yaml_safe("normal")` still returns `"normal"` (no quoting)
  4. Existing `_yaml_safe` tests still pass
- **Validation:**
  ```
  python -m unittest tests.test_gh_interactions -v -k "yaml_safe"
  python -m unittest discover tests/ -v 2>&1 | tail -1
  ```
- **Status:** fixed

### P7-05: Bare `except Exception` on sync_backlog import
- **File:** `skills/sprint-monitor/scripts/check_status.py:25-29`
- **Bug:** `except Exception as _import_err` catches ALL exceptions during import of `sync_backlog`, including `SyntaxError`, `NameError`, `TypeError`. A broken `sync_backlog.py` would be silently degraded to `None` with only a stderr warning, and the monitor would run without backlog sync — potentially missing backlog changes.
- **Root cause:** Import was wrapped in try/except for deployment flexibility, but the exception scope is too broad.
- **Impact:** Syntax errors or import chain bugs in sync_backlog or its transitive imports (validate_config, bootstrap_github, populate_issues) would be silently swallowed.
- **Acceptance criteria:**
  1. Change to `except ImportError` (the legitimate failure case — module not found)
  2. Other exceptions propagate normally
  3. Test verifies `ImportError` is still caught gracefully
  4. Test verifies `SyntaxError` is NOT caught (propagates)
- **Validation:**
  ```
  python -m unittest tests.test_gh_interactions -v -k "check_status"
  python -m unittest discover tests/ -v 2>&1 | tail -1
  ```
- **Status:** fixed

### P7-06: `_collect_sprint_numbers` silent fallback to sprint 1
- **File:** `skills/sprint-setup/scripts/bootstrap_github.py:96-98`
- **Bug:** When a milestone file has no `### Sprint N:` sections AND the filename contains no digits, `re.search(r"(\d+)", mf.stem)` returns None, and the fallback is `sprint_nums.add(1)`. This silently creates a "sprint:1" label from a file that has no sprint association, potentially masking a misconfigured milestone file.
- **Impact:** Milestone files without sprint sections get silently mapped to Sprint 1. If multiple such files exist, they all collapse to the same sprint label, hiding the problem.
- **Acceptance criteria:**
  1. When a milestone file has no sprint sections AND no number in filename, log a warning (to stderr or print) rather than silently defaulting to 1
  2. Test covers the warning path
  3. Existing sprint number extraction still works for well-formed files
- **Validation:**
  ```
  python -m unittest tests.test_gh_interactions -v -k "sprint"
  python -m unittest tests.test_hexwise_setup -v
  python -m unittest discover tests/ -v 2>&1 | tail -1
  ```
- **Status:** fixed

### P7-07: `write_version_to_toml` section boundary matches array lines
- **File:** `skills/sprint-release/scripts/release_gate.py:266`
- **Bug:** `re.search(r"^\[", text[start + 1:], re.MULTILINE)` uses `^\[` to find the next TOML section after `[release]`. But in TOML, multiline arrays have lines starting with `[` that are array elements, not section headers. If the `[release]` section contained a multiline array value, the section boundary would be detected too early, and version insertion would corrupt the file.
- **Root cause:** No distinction between `[section]` headers and `[array, content]` lines.
- **Impact:** Low probability in practice (generated TOML uses inline arrays), but a correctness bug in a release-path function. If a user adds a multiline array to `[release]`, the version write corrupts the TOML.
- **Acceptance criteria:**
  1. `write_version_to_toml` correctly handles a `[release]` section followed by a multiline array key before the next section
  2. Test verifies: `[release]\ngate_checks = [\n  "check1",\n  "check2"\n]\n\n[other]\nkey = 1` — version insertion doesn't corrupt `[other]`
- **Validation:**
  ```
  python -m unittest tests.test_gh_interactions -v -k "version_to_toml"
  python -m unittest tests.test_release_gate -v -k "version"
  python -m unittest discover tests/ -v 2>&1 | tail -1
  ```
- **Status:** fixed

### P7-08: `check_branch_divergence` silently skips list responses
- **File:** `skills/sprint-monitor/scripts/check_status.py:242-243`
- **Bug:** `if isinstance(data, list): continue` — when the GitHub API returns a list instead of a dict (which can happen with certain `--jq` filters or API error shapes), the branch is silently skipped with no report entry. The user never learns that divergence data was unavailable for that branch.
- **Impact:** Branch drift could go undetected if the API response format changes or is unexpected.
- **Acceptance criteria:**
  1. When `data` is a list, add a warning to the report (e.g., "Could not parse divergence data for {branch}")
  2. Test covers the list-response path
- **Validation:**
  ```
  python -m unittest tests.test_gh_interactions -v -k "branch_divergence"
  python -m unittest discover tests/ -v 2>&1 | tail -1
  ```
- **Status:** fixed

---

## P2 — Hardening / Coverage Gap

### P7-09: `_split_array` has zero direct test coverage
- **File:** `scripts/validate_config.py:240-265`, `tests/test_pipeline_scripts.py`
- **Gap:** `_split_array()` is only tested indirectly through `parse_simple_toml` array tests. No test directly exercises the function's edge cases: empty strings, nested quotes, escaped characters at boundaries, trailing commas, whitespace-only elements.
- **Acceptance criteria:**
  1. Direct tests for `_split_array` covering: empty input, single element, trailing comma, escaped quote inside string, mixed quote types, whitespace-only element
  2. At least 6 new test methods
- **Validation:**
  ```
  python -m unittest tests.test_pipeline_scripts -v -k "split_array"
  python -m unittest discover tests/ -v 2>&1 | tail -1
  ```
- **Status:** fixed

### P7-10: `_infer_sprint_number` has zero test coverage
- **File:** `skills/sprint-setup/scripts/populate_issues.py:133-149`
- **Gap:** This function is only exercised indirectly through `parse_milestone_stories()`. No test covers: heading-based inference, prose-mention false positive, filename fallback, or the default-to-1 path.
- **Acceptance criteria:**
  1. Direct tests for `_infer_sprint_number` covering: heading match, prose-only mention, filename with number, filename without number, content parameter passthrough
  2. At least 5 new test methods
- **Validation:**
  ```
  python -m unittest tests.test_gh_interactions -v -k "infer_sprint"
  python -m unittest discover tests/ -v 2>&1 | tail -1
  ```
- **Status:** fixed

### P7-11: `_parse_workflow_runs` has zero test coverage
- **File:** `scripts/sprint_init.py:~215`
- **Gap:** The multiline workflow `run:` block detection uses an indentation heuristic that joins continued lines. No test covers: single-line runs, multiline runs, mixed indentation, empty run blocks.
- **Acceptance criteria:**
  1. Direct tests for `_parse_workflow_runs` (or `_extract_ci_commands` which calls it) covering: simple one-liner `run: cmd`, multiline `run: |\n  cmd1\n  cmd2`, and mixed cases
  2. At least 3 new test methods
- **Validation:**
  ```
  python -m unittest tests.test_pipeline_scripts -v -k "workflow_run"
  python -m unittest discover tests/ -v 2>&1 | tail -1
  ```
- **Status:** fixed

### P7-12: `gate_prs` limit-hit path untested
- **File:** `skills/sprint-release/scripts/release_gate.py:172`, `tests/test_gh_interactions.py`
- **Gap:** `gate_prs` tests mock `gh_json` to return 0-1 PRs. No test verifies behavior when `warn_if_at_limit(prs, 500)` triggers (len(prs) == 500). Combined with P7-03, this means the truncation risk is both unhandled AND untested.
- **Acceptance criteria:**
  1. Test with exactly 500 PRs returned from mock
  2. Verify warning is emitted (or gate fails per P7-03 fix)
- **Validation:**
  ```
  python -m unittest tests.test_gh_interactions -v -k "gate_prs"
  python -m unittest discover tests/ -v 2>&1 | tail -1
  ```
- **Status:** fixed

### P7-13: `write_version_to_toml` multiline array test missing
- **File:** `tests/test_gh_interactions.py:225-267`
- **Gap:** All three `write_version_to_toml` tests use simple flat TOML structures. No test has a `[release]` section followed by a multiline array before the next section header, which would trigger the section-boundary regex bug (P7-07).
- **Acceptance criteria:**
  1. Test with TOML containing: `[release]\nkeys = [\n  "a",\n  "b"\n]\n\n[other]\nfoo = 1`
  2. Verify version is inserted in `[release]` without corrupting `[other]`
- **Validation:**
  ```
  python -m unittest tests.test_gh_interactions -v -k "version_to_toml"
  python -m unittest discover tests/ -v 2>&1 | tail -1
  ```
- **Status:** fixed

### P7-16: `format_issue_body()` has zero test coverage
- **File:** `skills/sprint-setup/scripts/populate_issues.py:317`
- **Gap:** `format_issue_body()` generates the full GitHub issue body markdown (user story, acceptance criteria checkboxes, task breakdown, metadata table). Integration tests create issues and check titles, but NEVER inspect body content. A regression in body formatting would pass all tests.
- **Acceptance criteria:**
  1. Direct test creates a `Story` with acceptance criteria, tasks, epic ref, saga ref
  2. Asserts body contains `- [ ] AC-` checkboxes, task list, metadata table
  3. At least 2 test methods (happy path + minimal story)
- **Validation:**
  ```
  python -m unittest tests.test_gh_interactions -v -k "format_issue_body"
  python -m unittest discover tests/ -v 2>&1 | tail -1
  ```
- **Status:** fixed

### P7-17: `find_latest_semver_tag()` and `parse_commits_since()` untested
- **File:** `skills/sprint-release/scripts/release_gate.py:39,57`
- **Gap:** These two functions are critical to release correctness — they determine the previous version and the commit diff. Both have zero direct tests. `calculate_version` tests mock these functions out entirely, so the actual git-tag parsing and commit extraction logic is never exercised.
- **Acceptance criteria:**
  1. Test `find_latest_semver_tag()` with: no tags, one tag, multiple tags (verifies sorting)
  2. Test `parse_commits_since()` with: tag exists, no tag (from root), empty range
  3. At least 4 new test methods
- **Validation:**
  ```
  python -m unittest tests.test_release_gate -v -k "semver_tag or commits_since"
  python -m unittest discover tests/ -v 2>&1 | tail -1
  ```
- **Status:** fixed

### P7-18: `create_issue()` missing-milestone KeyError path untested
- **File:** `skills/sprint-setup/scripts/populate_issues.py`
- **Gap:** `create_issue()` receives `ms_numbers` and `ms_titles` dicts keyed by sprint number. No test covers the case where a story's sprint number is NOT in these dicts. This would raise a `KeyError` in production.
- **Acceptance criteria:**
  1. Test calling `create_issue()` with a story whose sprint number has no milestone mapping
  2. Verify it raises `KeyError` or handles gracefully (whichever is the intended behavior)
- **Validation:**
  ```
  python -m unittest tests.test_gh_interactions -v -k "create_issue"
  python -m unittest discover tests/ -v 2>&1 | tail -1
  ```
- **Status:** fixed

### P7-19: Weak assertions mask regressions in deterministic fixtures
- **File:** `tests/test_lifecycle.py`, `tests/test_hexwise_setup.py`, `tests/test_sync_backlog.py`
- **Gap:** ~10 locations use `assertGreater(len(...), 0)` or `assertGreaterEqual(len(...), N)` where the fixture is deterministic and the exact count is known. A regression that drops 90% of data would still pass. Examples: `test_lifecycle.py:230` (should be `== 1`), `test_lifecycle.py:245` (should be `== 2`), `test_hexwise_setup.py:93` (should be `== 3`).
- **Acceptance criteria:**
  1. Replace all `assertGreater(len(...), 0)` / `assertGreaterEqual` with `assertEqual` where fixture counts are deterministic
  2. Identify at least 8 locations and fix
- **Validation:**
  ```
  grep -rn "assertGreater\|assertGreaterEqual" tests/ | grep "len(" | wc -l  # should decrease
  python -m unittest discover tests/ -v 2>&1 | tail -1
  ```
- **Status:** fixed

---

## P3 — Documentation / Hygiene

### P7-14: `commit.py` and `validate_anchors.py` missing from CLAUDE.md
- **File:** `CLAUDE.md` (Scripts table)
- **Gap:** Two production scripts (`scripts/commit.py`, `scripts/validate_anchors.py`) are not listed in the CLAUDE.md "Scripts" table. Both are standalone scripts with their own test files. `commit.py` is used by the release pipeline. `validate_anchors.py` maintains the greppable anchor system that CLAUDE.md itself depends on.
- **Acceptance criteria:**
  1. Both scripts appear in the CLAUDE.md "Scripts (all stdlib-only Python 3.10+)" table
  2. Key functions listed with `§` anchors matching the pattern used for other scripts
  3. `validate_anchors.py` check mode passes after the update
- **Validation:**
  ```
  grep -c "commit.py" CLAUDE.md  # should be >= 1
  grep -c "validate_anchors.py" CLAUDE.md  # should be >= 1
  python scripts/validate_anchors.py check  # should exit 0
  ```
- **Status:** fixed

### P7-15: `_parse_workflow_runs` multiline join uses indentation heuristic
- **File:** `scripts/sprint_init.py:~215`
- **Doc gap:** The scanner's CI command extraction uses an undocumented indentation-based heuristic to detect multiline `run:` blocks in GitHub Actions YAML. This is fragile (a `run:` value that uses `>` or `>-` folded style instead of `|` literal style would not be detected). Should be documented as a known limitation in CLAUDE.md or in the function docstring.
- **Acceptance criteria:**
  1. Docstring for `_parse_workflow_runs` (or `_extract_ci_commands`) mentions the multiline detection strategy and its limitations (literal block only, no folded style)
  2. CLAUDE.md "Key Architectural Decisions" or the scanner's entry notes this limitation
- **Validation:**
  ```
  grep -A2 "_parse_workflow_runs\|_extract_ci_commands" scripts/sprint_init.py | head -10
  ```
- **Status:** fixed

### P7-20: `release_gate.py` missing from CLAUDE.md and CHEATSHEET.md
- **File:** `CLAUDE.md`, `CHEATSHEET.md`
- **Gap:** `release_gate.py` is the primary automation script for the sprint-release skill (658 LOC, highest churn at 8 changes). It is completely absent from CLAUDE.md's Scripts table and CHEATSHEET.md's function index. An agent reading the docs cannot discover it. Meanwhile, `sprint-release/SKILL.md` references it at line 12.
- **Acceptance criteria:**
  1. `release_gate.py` appears in CLAUDE.md Scripts table with key functions and `§` anchors
  2. CHEATSHEET.md has a complete function index for `release_gate.py`
  3. `validate_anchors.py check` passes after update
- **Validation:**
  ```
  grep -c "release_gate.py" CLAUDE.md  # should be >= 1
  grep -c "release_gate" CHEATSHEET.md  # should be >= 1
  python scripts/validate_anchors.py check
  ```
- **Status:** fixed

### P7-21: sprint-release SKILL.md describes phantom features
- **File:** `skills/sprint-release/SKILL.md:59-60,90-91,122-125`
- **Gap:** The SKILL.md describes features that don't exist in `release_gate.py`:
  1. Config-driven gates (`[release] milestones`, `gate_file`) — gates are actually hardcoded
  2. Config-driven versioning — versions are actually calculated from conventional commits
  3. SBOM generation (`sbom_command`) — not implemented
  4. Multi-platform builds — single `build_command` only
- **Acceptance criteria:**
  1. Rewrite affected SKILL.md sections to match `release_gate.py`'s actual capabilities
  2. Or implement the described features (much larger scope)
  3. No phantom config keys referenced that aren't read by code
- **Validation:**
  ```
  grep -n "sbom_command\|gate_file\|milestones.*=\|per.*platform" skills/sprint-release/SKILL.md | wc -l  # should be 0 after fix
  ```
- **Status:** fixed

### P7-22: README.md references phantom `feedback_dir` config key
- **File:** `README.md`
- **Gap:** README.md lists `feedback_dir` as an optional deep-doc path key. No Python script reads this key. No `get_feedback_dir()` function exists. The skeleton template has it commented out. Previously identified as P4-31.
- **Acceptance criteria:**
  1. Remove `feedback_dir` from README.md's config key list
  2. Or implement `get_feedback_dir()` in validate_config.py
- **Validation:**
  ```
  grep -c "feedback_dir" README.md  # should be 0 after fix
  ```
- **Status:** fixed

---

## Patterns Identified

### Pattern A: Single-Quote Blind Spots
P7-01 and P7-09 both stem from the same root: when P6-12 added single-quote support to `_parse_value`, the downstream `_split_array` wasn't updated. This is a "fix one layer, miss the next" pattern. **Sibling check:** Are there other functions that process TOML string content without single-quote awareness? `_strip_inline_comment()` — appears safe (operates on raw line, not inside quotes). No other siblings found.

### Pattern B: Regex Overreach in Parsers
P7-02, P7-07, and P7-15 all involve regex patterns that match too broadly: `Sprint\s+(\d+)` matching prose, `^\[` matching array lines, and indentation heuristics for multiline blocks. The project leans heavily on regex parsing of structured formats (TOML, YAML, Markdown) where a proper parser would be more robust. Given the stdlib-only constraint, this is an accepted trade-off, but each regex parser needs more edge case tests.

### Pattern C: Silent Degradation
P7-05, P7-06, and P7-08 share a pattern of silently continuing when data is unexpected: bare `except Exception`, default-to-1 fallback, and `if isinstance(data, list): continue`. The monitoring and bootstrap scripts prefer availability over correctness, which means bugs manifest as missing data rather than errors. Recommendation: prefer logging a warning + continuing over pure silent skip.

### Pattern D: Doc-Code Drift in SKILL.md Files
P7-20, P7-21, and P7-22 reveal that SKILL.md files and README.md describe aspirational features that were never implemented. The sprint-release SKILL.md is the worst offender — it describes config-driven gates, config-driven versioning, SBOM generation, and multi-platform builds that are all phantom. This pattern is dangerous because agents read SKILL.md to understand what's possible. When the doc says "read gate_file from config" but the code has hardcoded gates, agents will waste time looking for config keys that don't exist.

### Pattern E: Coverage Theater in Integration Tests
P7-16, P7-17, P7-18, and P7-19 share a pattern where integration tests exercise code paths but assert on the wrong things — checking that issues were created (by title count) but never inspecting body content, checking that versions were calculated but mocking out the git-tag parsing that determines the input. Functions look "covered" in a trace but their actual behavior is unvalidated. The `assertGreater(len(...), 0)` pattern is the most visible symptom: it asserts "something happened" without checking what.
