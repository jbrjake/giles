# Bug Hunter Pass 11 — Punchlist

> Generated: 2026-03-15 | Project: giles | Pass: 11
> Phase 1: Doc-to-implementation audit (BH-P11-001 through BH-P11-010)
> Phase 2: Test quality audit (BH-P11-050 through BH-P11-063)
> Phase 3: Adversarial code audit (BH-P11-100 through BH-P11-114)

---

## Phase 1: Doc-to-Implementation Audit

Scope: Testable claims in CLAUDE.md, SKILL.md files, kanban-protocol.md, release-checklist.md, persona-guide.md
Detail: See `audit/1-doc-claims.md` for the full 112-claim checklist (102 passed, 10 failed).

### BH-P11-001 — No idempotency test for bootstrap label creation
- **Severity:** Medium
- **Category:** missing-test
- **Location:** `skills/sprint-setup/scripts/bootstrap_github.py:172`
- **Problem:** CLAUDE.md claims "All bootstrap and monitoring scripts are idempotent." No test runs `create_static_labels()` twice on the same FakeGitHub instance and verifies no duplicate labels are created.
- **Acceptance Criteria:** A test calls `create_static_labels()` twice against the same FakeGitHub, then asserts `len(fake_gh.labels)` is the same after both calls.
- **Validation:** `python -m pytest tests/ -k "idempotent_static_labels" -v`
- **Status:** Resolved

### BH-P11-002 — No idempotency test for milestone creation
- **Severity:** Medium
- **Category:** missing-test
- **Location:** `skills/sprint-setup/scripts/bootstrap_github.py:214`
- **Problem:** CLAUDE.md claims bootstrap scripts are idempotent, but no test runs `create_milestones_on_github()` twice and verifies no duplicate milestones.
- **Acceptance Criteria:** A test calls `create_milestones_on_github(config)` twice against the same FakeGitHub, then asserts milestone count is unchanged.
- **Validation:** `python -m pytest tests/ -k "idempotent_milestone" -v`
- **Status:** Resolved

### BH-P11-003 — No test for bootstrap persona label idempotency
- **Severity:** Low
- **Category:** missing-test
- **Location:** `skills/sprint-setup/scripts/bootstrap_github.py:62`
- **Problem:** `create_persona_labels()` is called in pipeline tests but never called twice in the same test.
- **Acceptance Criteria:** A test calls `create_persona_labels(config)` twice and verifies no duplicate persona labels.
- **Validation:** `python -m pytest tests/ -k "idempotent_persona_labels" -v`
- **Status:** Resolved

### BH-P11-004 — Kanban transition rules documented but not enforced or tested
- **Severity:** High
- **Category:** doc-drift
- **Location:** `skills/sprint-run/references/kanban-protocol.md:22-29`
- **Problem:** kanban-protocol.md defines 7 specific allowed transitions. `sync_tracking.sync_one()` at `skills/sprint-run/scripts/sync_tracking.py:217` accepts ANY kanban label without validating the transition. No transition validation function exists.
- **Acceptance Criteria:** Either (a) add `validate_transition()` with tests, OR (b) update kanban-protocol.md to clarify transitions are LLM guidelines, not programmatic constraints.
- **Validation:** `python -m pytest tests/ -k "kanban_transition" -v`
- **Status:** Resolved

### BH-P11-005 — Kanban WIP limits documented but not enforced or tested
- **Severity:** Medium
- **Category:** doc-drift
- **Location:** `skills/sprint-run/references/kanban-protocol.md:57-64`
- **Problem:** WIP limits (1 dev/persona, 2 review/reviewer, 3 integration) are documented as system constraints but are actually LLM process guidelines with no code enforcement.
- **Acceptance Criteria:** Either (a) add `check_wip_limits()` with tests, OR (b) clarify in kanban-protocol.md these are LLM guidelines.
- **Validation:** `grep -c "guideline\|not enforced" skills/sprint-run/references/kanban-protocol.md` should return >0
- **Status:** Resolved

### BH-P11-006 — Review round limit (3 rounds) documented but not enforced
- **Severity:** Medium
- **Category:** doc-drift
- **Location:** `skills/sprint-run/references/kanban-protocol.md:38`
- **Problem:** "review->dev loop can repeat at most 3 times" is documented but not enforced in code. No test validates the limit.
- **Acceptance Criteria:** Either (a) add enforcement with a test, OR (b) clarify this is an LLM behavioral guideline.
- **Validation:** `grep -c "guideline\|behavioral" skills/sprint-run/references/kanban-protocol.md` should return >0
- **Status:** Resolved

### BH-P11-007 — No test verifying sync_tracking does NOT push local state to GitHub
- **Severity:** Low
- **Category:** weak-test
- **Location:** `skills/sprint-run/scripts/sync_tracking.py:217`
- **Problem:** "GitHub as source of truth" claim tested only in one direction (GitHub->local). No test asserts sync_one makes zero outgoing `gh` calls.
- **Acceptance Criteria:** A test calls `sync_one()` with disagreeing states and asserts no `gh issue edit` or `gh label` commands were invoked.
- **Validation:** `python -m pytest tests/ -k "github_authoritative_no_push" -v`
- **Status:** Resolved

### BH-P11-008 — No test verifies sprint-init creates symlinks for project files
- **Severity:** Low
- **Category:** missing-test
- **Location:** `scripts/sprint_init.py:752`
- **Problem:** CLAUDE.md claims "sprint_init creates symlinks." Tests verify Giles is NOT a symlink, but no test verifies rules.md and development.md ARE symlinks with correct targets.
- **Acceptance Criteria:** A test asserts `(config_dir / "rules.md").is_symlink() == True` and target resolves to the original project file.
- **Validation:** `python -m pytest tests/ -k "symlink_created" -v`
- **Status:** Resolved

### BH-P11-009 — No test for validate_project rejecting config with one missing required key
- **Severity:** Medium
- **Category:** missing-test
- **Location:** `scripts/validate_config.py:389`
- **Problem:** 8 required TOML keys are documented. No test removes one key and verifies validate_project fails with an error naming that key.
- **Acceptance Criteria:** A test removes `ci.build_command`, calls `validate_project()`, asserts `ok == False` and error mentions the missing key.
- **Validation:** `python -m pytest tests/ -k "missing_required_key" -v`
- **Status:** Resolved

### BH-P11-010 — No test for KANBAN_STATES constant matching documented states
- **Severity:** Low
- **Category:** weak-test
- **Location:** `scripts/validate_config.py:794`
- **Problem:** CLAUDE.md and kanban-protocol.md claim 6 states. No test asserts the exact set or count of `KANBAN_STATES`.
- **Acceptance Criteria:** A test asserts `KANBAN_STATES == {"todo", "design", "dev", "review", "integration", "done"}`.
- **Validation:** `python -m pytest tests/ -k "kanban_states_constant" -v`
- **Status:** Resolved

---

## Phase 2: Test Quality Audit

Scope: All 11 test files + fake_github.py test infrastructure
Focus: Anti-patterns that provide false confidence — tests that look good at a distance but catch nothing

### BH-P11-050 — `test_skips_missing_file` has zero assertions
- **Severity:** High
- **Category:** assertion-free
- **Location:** `tests/test_gh_interactions.py:1548`
- **Problem:** `test_skips_missing_file` calls `update_burndown.update_sprint_status()` with a missing SPRINT-STATUS.md and only verifies no exception is raised. No assertion on return value, no check that no file was created. Comment says "Should not raise" — but any exception-free codepath passes this test. If the function silently corrupted data instead of skipping, this test would still pass.
- **Acceptance Criteria:** Assert that no SPRINT-STATUS.md was created in tmpdir AND/OR assert the function returns a sentinel value (None, 0, etc.) indicating the skip.
- **Validation:** `python -m unittest tests.test_gh_interactions.TestUpdateSprintStatus.test_skips_missing_file -v`
- **Status:** Resolved

### BH-P11-051 — Golden snapshot comparisons silently degrade to warnings
- **Severity:** High
- **Category:** weak-test
- **Location:** `tests/test_golden_run.py:101-109`
- **Problem:** When golden recording files are absent, the test issues `warnings.warn()` and continues. All 5 phase-level snapshot comparisons are silently skipped. The test passes green while providing zero snapshot regression coverage. In CI, recordings ARE checked in — but if someone accidentally deletes the recordings directory, the test degrades without anyone noticing.
- **Acceptance Criteria:** When recordings are absent, either (a) emit a visible `print()` to stdout so it appears in test output, or (b) use `self.skipTest()` to explicitly mark the test as skipped (visible in test summary), or (c) fail if in CI (`os.environ.get("CI")`).
- **Validation:** `python -m unittest tests.test_golden_run -v 2>&1 | grep -i "skip\|warn\|golden"`
- **Status:** Resolved

### BH-P11-052 — `gate_stories` unit tests are mock-returns-what-you-assert
- **Severity:** High
- **Category:** mock-abuse
- **Location:** `tests/test_gh_interactions.py:293-308`
- **Problem:** `TestGateStories` patches `gh_json` to return `[]` (all closed) or a list of open issues. The test then verifies the function returns `(True, ...)` or `(False, "2 open ...")`. This tests the report formatting — "given this data, does the function format the output correctly?" — but NOT that the function queries GitHub with the right search parameters. If `gate_stories` changed its `gh_json` call from `--search "milestone:X is:open"` to `--search "is:open"` (dropping the milestone filter), these tests would still pass. The `validate_gates` integration test (via FakeGitHub) partially covers this, but these unit tests provide false confidence.
- **Acceptance Criteria:** Either (a) verify the `gh_json` call args include the milestone name, or (b) document these as "report formatting tests" and add a separate integration test that exercises the query path. At minimum, assert `mock_gh.call_args` contains the milestone.
- **Validation:** `grep -A5 "def test_all_closed" tests/test_gh_interactions.py | grep "call_args"`
- **Status:** Resolved

### BH-P11-053 — `gate_ci` unit tests are mock-returns-what-you-assert
- **Severity:** High
- **Category:** mock-abuse
- **Location:** `tests/test_gh_interactions.py:313-334`
- **Problem:** Same pattern as BH-P11-052. `TestGateCI` patches `gh_json` to return pre-shaped run data and verifies the pass/fail logic. Never verifies the query targets the right workflow or branch. If `gate_ci` dropped its `--branch` filter, these tests would still pass.
- **Acceptance Criteria:** Assert `mock_gh.call_args` includes the base branch or workflow name. Or document these as formatting-only tests.
- **Validation:** `grep -A5 "def test_passing" tests/test_gh_interactions.py | grep "call_args"`
- **Status:** Resolved

### BH-P11-054 — FakeGitHub `--jq` flag accepted but never evaluated
- **Severity:** High
- **Category:** mock-abuse
- **Location:** `tests/fake_github.py` (multiple handlers)
- **Problem:** FakeGitHub accepts `--jq` as a known flag but does NOT evaluate the jq expression. Instead, handlers pre-shape their return data to match what the real jq filter would produce. This means: (a) if a production script changes its `--jq` filter, FakeGitHub still returns the old shape — tests pass but production breaks, (b) complex jq expressions (nested selects, array construction) are never tested, (c) tests implicitly document the expected jq output shape, but this documentation can drift. The `--jq` gap has been flagged in prior passes but persists because full jq evaluation would require a jq library dependency (violating the stdlib-only constraint).
- **Acceptance Criteria:** Either (a) add a comment to each handler documenting the assumed jq filter shape, or (b) for critical paths (check_direct_pushes, get_linked_pr), add a separate test that runs the real `gh` with `--jq` against known input to verify the filter. At minimum, document which production jq filters each handler is simulating.
- **Validation:** `grep -c "jq" tests/fake_github.py`
- **Status:** Resolved

### BH-P11-055 — No `main()` integration test for `check_status.py`
- **Severity:** Medium
- **Category:** missing-test
- **Location:** `skills/sprint-monitor/scripts/check_status.py:main()`
- **Problem:** `check_status.py` has unit tests for individual check functions (check_ci, check_prs, etc.) but no test that calls `main()` with mocked subprocess/config and verifies the full orchestration — sync, CI check, drift detection, PR check, milestone check, log file write. The monitoring pipeline test in `test_lifecycle.py:test_14` exercises some of these but through individual function calls, not through `main()`.
- **Acceptance Criteria:** A test calls `check_status.main()` with patched subprocess and config, verifies it runs all checks in order, writes a log file, and exits cleanly.
- **Validation:** `grep -c "check_status.main" tests/`
- **Status:** Resolved

### BH-P11-056 — No `main()` integration test for `sync_tracking.py`
- **Severity:** Medium
- **Category:** missing-test
- **Location:** `skills/sprint-run/scripts/sync_tracking.py:main()`
- **Problem:** `sync_tracking.py` has unit tests for `sync_one()` and `create_from_issue()` but no test calls `main()`. The `main()` function orchestrates: load config, find milestone, list issues, sync each one — none of this orchestration is tested.
- **Acceptance Criteria:** A test calls `sync_tracking.main()` with patched subprocess and verifies it processes all issues in the milestone.
- **Validation:** `grep -c "sync_tracking.main" tests/`
- **Status:** Resolved

### BH-P11-057 — No `main()` integration test for `commit.py`
- **Severity:** Medium
- **Category:** missing-test
- **Location:** `scripts/commit.py:main()`
- **Problem:** `commit.py` has unit tests for `validate_message()` and `check_atomicity()` but no test calls `main()` end-to-end. The `main()` function orchestrates: parse args, validate message, check atomicity, run git commit — none of this orchestration logic is tested.
- **Acceptance Criteria:** A test calls `commit.main()` with patched sys.argv and subprocess, verifies it validates the message, checks atomicity, and calls `git commit`.
- **Validation:** `grep -rn "commit.main" tests/`
- **Status:** Resolved

### BH-P11-058 — No `main()` integration test for `validate_anchors.py`
- **Severity:** Medium
- **Category:** missing-test
- **Location:** `scripts/validate_anchors.py:main()`
- **Problem:** `validate_anchors.py` has unit tests for `find_anchor_defs`, `find_anchor_refs`, `check_anchors`, and `fix_missing_anchors`. But no test calls `main()` to verify CLI arg parsing and the check/fix mode selection.
- **Acceptance Criteria:** A test calls `validate_anchors.main()` with patched sys.argv and verifies it runs in check mode or fix mode correctly.
- **Validation:** `grep -rn "validate_anchors.main" tests/`
- **Status:** Resolved

### BH-P11-059 — FakeGitHub `--search` flag silently ignored in PR/issue list
- **Severity:** Medium
- **Category:** mock-abuse
- **Location:** `tests/fake_github.py` (_pr_list, _issue_list handlers)
- **Problem:** FakeGitHub accepts `--search` as a known flag but does not filter results by the search query. Production code like `gate_stories()` uses `--search "milestone:\"Sprint 1\" is:open"` — but FakeGitHub returns ALL issues/PRs regardless of the search string. Tests work because they pre-populate FakeGitHub with only matching data. If production code dropped or changed the search query, tests would still pass because FakeGitHub never validates the search.
- **Acceptance Criteria:** Either (a) FakeGitHub parses `--search` and filters results by milestone/state, or (b) tests assert the search string is correct via `mock.call_args`.
- **Validation:** `grep -n "search" tests/fake_github.py | head -10`
- **Status:** Resolved

### BH-P11-060 — `do_release` tests over-mock subprocess, never exercise real git
- **Severity:** Medium
- **Category:** mock-abuse
- **Location:** `tests/test_release_gate.py:TestDoRelease`
- **Problem:** `do_release` tests patch `subprocess.run` globally, replacing ALL subprocess calls (including git) with MagicMock. This means git operations (commit, tag, push) are never actually executed. The test verifies the sequence of subprocess calls but not that the git commands are syntactically correct or produce the expected state. For example, the test can't catch if `git tag -a v{ver}` has wrong quoting or if the tag format is invalid.
- **Acceptance Criteria:** Either (a) use FakeGitHub (which passes real git commands through) for the git operations while mocking gh, or (b) add a separate integration test that runs do_release in a real git repo (temp dir).
- **Validation:** `grep -c "MagicMock\|mock_run" tests/test_release_gate.py`
- **Status:** Resolved

### BH-P11-061 — `sprint_teardown` interactive confirmation path untested
- **Severity:** Medium
- **Category:** missing-test
- **Location:** `scripts/sprint_teardown.py:main()`
- **Problem:** `sprint_teardown.main()` has a dry-run test and an execute test, but the interactive confirmation prompt (when neither `--force` nor `--dry-run` is passed) is not tested. The code path where the user is asked "Remove sprint-config/? [y/N]" and responds with various inputs (y, n, empty, unexpected) is never exercised.
- **Acceptance Criteria:** A test patches `input()` to return "y", "n", and "" and verifies the function proceeds or aborts accordingly.
- **Validation:** `grep -n "input(" scripts/sprint_teardown.py`
- **Status:** Resolved

### BH-P11-062 — Duplicate `MockProject` classes across test files
- **Severity:** Low
- **Category:** duplicate
- **Location:** `tests/test_lifecycle.py:MockProject` + `tests/test_verify_fixes.py:MockProject`
- **Problem:** Two nearly identical `MockProject` classes create minimal Rust project fixtures in temp directories. Both create Cargo.toml, .git/config, team personas, milestones, RULES.md, DEVELOPMENT.md. Divergence between them means one test suite might pass with a slightly different fixture than another, making behavior inconsistent. Changes to project structure require updating both copies.
- **Acceptance Criteria:** Extract `MockProject` into a shared test helper (e.g., `tests/mock_project.py`) imported by both test files.
- **Validation:** `grep -rn "class MockProject" tests/`
- **Status:** Resolved

### BH-P11-063 — `check_ci`/`check_prs` tests verify mock output shape, not query correctness
- **Severity:** Medium
- **Category:** mock-abuse
- **Location:** `tests/test_gh_interactions.py:TestCheckCI, TestCheckPRs`
- **Problem:** `TestCheckCI` and `TestCheckPRs` use FakeGitHub with pre-populated run/PR data. They verify the output message contains expected strings but don't verify the query parameters (e.g., that check_ci queries the correct branch, that check_prs filters by state). If the production code changed its query from `--state open` to `--state all`, these tests would still pass because FakeGitHub returns all data regardless.
- **Acceptance Criteria:** Tests should verify the subprocess call args include expected filters (branch, state, limit) or FakeGitHub should validate query parameters.
- **Validation:** `python -m unittest tests.test_gh_interactions.TestCheckCI -v`
- **Status:** Resolved

---

## Phase 3: Adversarial Code Audit

Scope: All production scripts (priority 1-12 from churn analysis)
Focus: Cross-script interaction bugs, error paths, boundary conditions missed by passes 1-10

### BH-P11-100 — `do_release` rollback silently swallows failures and double-resets HEAD
- **Severity:** High
- **Category:** logic-bug
- **Location:** `skills/sprint-release/scripts/release_gate.py:538-547,580-583`
- **Problem:** When the GitHub Release creation fails (line 579), the cleanup calls `_rollback_tag()` (line 580) then `_rollback_commit()` (line 581). But `_rollback_tag()` only removes the tag — it does NOT call `_rollback_commit()`. The real issue is that both rollback functions silently discard subprocess return codes. If `git push --delete origin v{new_ver}` fails (network error, permission denied), the tag persists on the remote while the local commit is rewound by `_rollback_commit()`. The remote now has an orphaned tag pointing at a commit that the local branch no longer contains. The user sees "GitHub Release failed (tag rolled back)" but the tag was NOT actually rolled back on the remote. There is no error surfaced for the failed rollback.
- **Acceptance Criteria:** Rollback subprocess calls check return codes and print warnings on failure. The user is told explicitly if remote tag deletion failed, with a remediation command (`git push --delete origin v{version}`).
- **Validation:** `grep -c "returncode" skills/sprint-release/scripts/release_gate.py | python3 -c "import sys; n=int(sys.stdin.read().strip()); print(f'Rollback return code checks: {n - 10} (in rollback functions)')"`
- **Status:** Resolved

### BH-P11-101 — `get_linked_pr` merged-PR selection is order-dependent on API response
- **Severity:** High
- **Category:** logic-bug
- **Location:** `skills/sprint-run/scripts/sync_tracking.py:74-83`
- **Problem:** The PR selection loop iterates `linked` looking for the best PR. For open PRs it breaks immediately (line 79). For merged PRs, it sets `best = d` but does NOT break (line 82) — so if multiple merged PRs exist, the LAST one in the list wins. `best` is initialized to `linked[-1]` (line 75), which is the last item in the API response. The GitHub timeline API does not guarantee chronological ordering. This means the "best" PR for a given issue depends on which order the API returns linked PRs, making behavior non-deterministic. If an issue had an initial PR merged, then a hotfix PR merged, the code might return either one depending on API pagination and ordering.
- **Acceptance Criteria:** After finding a merged PR, break the loop (to match the open-PR behavior), or sort linked PRs by a timestamp before iterating. Document which merged PR is preferred.
- **Validation:** `python3 -c "
linked = [
    {'state':'closed','pull_request':{'merged_at':'2025-01-01'},'number':1},
    {'state':'closed','pull_request':{'merged_at':'2025-06-01'},'number':2},
    {'state':'closed','number':3}
]
best = linked[-1]
for d in linked:
    if d.get('state') == 'open':
        best = d; break
    if d.get('pull_request',{}).get('merged_at') is not None:
        best = d
print(f'Selected PR #{best[\"number\"]} (should be most recent merged)')
"`
- **Status:** Resolved

### BH-P11-102 — `populate_issues.get_milestone_numbers` bypasses `gh_json` concatenation fix
- **Severity:** High
- **Category:** logic-bug
- **Location:** `skills/sprint-setup/scripts/populate_issues.py:285-288`
- **Problem:** `get_milestone_numbers()` calls `gh()` with `--paginate` and then `json.loads(raw)`. The BH-001 fix (pass 10) added incremental JSON decoding to `gh_json()` in validate_config.py, but this function calls `gh()` directly and parses manually, completely bypassing that fix. For repos with 100+ milestones, `--paginate` concatenates multiple JSON arrays (`[...][...]`), and `json.loads()` will either raise `JSONDecodeError` or parse only the first page, silently dropping milestones. Issues assigned to dropped milestones won't be created.
- **Acceptance Criteria:** `get_milestone_numbers()` uses `gh_json()` instead of `gh()` + `json.loads()`. Or at minimum, uses the same incremental decoding logic.
- **Validation:** `grep -n "json.loads" skills/sprint-setup/scripts/populate_issues.py`
- **Status:** Resolved

### BH-P11-103 — `populate_issues.get_existing_issues` uses raw `json.loads` without type validation
- **Severity:** High
- **Category:** error-handling
- **Location:** `skills/sprint-setup/scripts/populate_issues.py:264-270`
- **Problem:** `get_existing_issues()` calls `gh()` then `json.loads(raw)`. Two issues: (1) It doesn't use `gh_json()`, missing centralized error handling. (2) It doesn't validate that `json.loads(raw)` returns a list. If `gh` returns a JSON object (e.g., an error response `{"message": "Bad credentials"}`), `for issue in issues` would iterate over dict keys (`"message"`), and `issue.get("title", "")` would fail with `AttributeError: 'str' object has no attribute 'get'`. The try/except catches `JSONDecodeError` but not `AttributeError`.
- **Acceptance Criteria:** Either use `gh_json()` or add `if not isinstance(issues, list): raise RuntimeError(...)` after parsing. The function should handle non-list JSON responses gracefully.
- **Validation:** `python3 -c "issues = {'message': 'Bad credentials'}; [i.get('title','') for i in issues]" 2>&1 | head -1`
- **Status:** Resolved

### BH-P11-104 — `sync_tracking.get_linked_pr` uses `json.loads` on paginated+jq output
- **Severity:** Medium
- **Category:** logic-bug
- **Location:** `skills/sprint-run/scripts/sync_tracking.py:62-70`
- **Problem:** `get_linked_pr` calls `gh()` with both `--paginate` and `--jq`. The `--jq` filter transforms each page independently, and `--paginate` concatenates the results. For a timeline that spans multiple pages, the output is `[...filtered page 1...][...filtered page 2...]` — concatenated arrays. `json.loads(raw)` at line 70 parses only the first array, silently dropping linked PRs from later pages. This is the same bug class as BH-001 (pass 10) but in a call site that combines `--paginate` with `--jq`, which wasn't caught because the `--jq` transformation masks the concatenation issue.
- **Acceptance Criteria:** Use `gh_json()` which handles concatenated arrays, or remove `--paginate` (single-issue timelines rarely exceed one page).
- **Validation:** `grep -n "paginate" skills/sprint-run/scripts/sync_tracking.py`
- **Status:** Resolved

### BH-P11-105 — `_yaml_safe` misses single-quote as a YAML-sensitive leading character
- **Severity:** Medium
- **Category:** logic-bug
- **Location:** `skills/sprint-run/scripts/sync_tracking.py:179`
- **Problem:** `_yaml_safe` checks if `value[0] in '[{>|*&!%@\``'` to decide if quoting is needed. Single-quote (`'`) is not in this set. In YAML, a value starting with `'` begins a single-quoted scalar. If a story title starts and ends with `'` (e.g., `'Twas a dark night'`), `write_tf` writes it unquoted. When `read_tf` parses it back, the quote-stripping logic at lines 158-159 checks `val[0] == val[-1] and val[0] in ('"', "'")` — this is True, so both the first and last `'` are stripped, corrupting the title to `Twas a dark night` (no quotes). Round-trip fidelity is broken.
- **Acceptance Criteria:** `_yaml_safe` includes both `'` and `"` in the set of leading characters that trigger quoting. Round-trip test: `write_tf` then `read_tf` preserves titles starting/ending with quotes.
- **Validation:** `python3 -c "
value = \"'Twas a dark night'\"
needs = (
    ': ' in value or value.endswith(':')
    or value[0] in '[{>|*&!%@\x60'
    or '#' in value or value.startswith('- ') or value.startswith('? ')
)
print(f'Title: {value!r}, needs_quoting: {needs}')
# After fix, needs should be True
"`
- **Status:** Resolved

### BH-P11-106 — `write_version_to_toml` next-section regex matches TOML array-of-tables
- **Severity:** Medium
- **Category:** logic-bug
- **Location:** `skills/sprint-release/scripts/release_gate.py:284`
- **Problem:** `re.search(r"^\[(?![\s\"\'])", text[start + 1:], re.MULTILINE)` finds the next TOML section header after `[release]`. The negative lookahead excludes whitespace, `"`, and `'` but does NOT exclude `[`. TOML's array-of-tables syntax `[[table_name]]` starts with `[[` — the second `[` would pass the lookahead, causing the regex to match `[[table_name]]` as a section boundary. Content between `[release]` and `[[table_name]]` would be treated as the release section, and the version line insertion could be placed incorrectly.
- **Acceptance Criteria:** The regex also excludes `[` in the lookahead: `r"^\[(?![\[\s\"'])"`. Or use a more robust section detection that skips `[[`.
- **Validation:** `python3 -c "
import re
text = '[release]\nversion = \"1.0\"\n\n[[plugins]]\nname = \"foo\"'
start = text.index('[release]')
m = re.search(r'^\[(?![\s\"\x27])', text[start + 1:], re.MULTILINE)
print(f'Matched at offset {m.start()}: {m.group()!r}' if m else 'No match')
# Bug: matches the second [ in [[plugins]]
"`
- **Status:** Resolved

### BH-P11-107 — `check_status.main` catches all sync exceptions silently
- **Severity:** Medium
- **Category:** error-handling
- **Location:** `skills/sprint-monitor/scripts/check_status.py:361-366`
- **Problem:** `sync_backlog_main()` is called inside a bare `except Exception` handler that converts any error to a one-line string `f"Sync: error — {exc}"`. This masks the full traceback, making debugging impossible. If `sync_backlog_main()` crashes due to a real bug (e.g., `KeyError`, `TypeError`, `AttributeError`), the error looks like a transient sync failure instead of a code bug. Additionally, the module-level import at line 26 (`from sync_backlog import main as sync_backlog_main`) transitively imports `bootstrap_github` and `populate_issues`, which import `load_config` and other heavy modules. If any of these have a syntax error or missing dependency, check_status.py itself fails to import — not just the sync step.
- **Acceptance Criteria:** The `except Exception` block logs `traceback.format_exc()` to stderr (not just the exception message). The sync_backlog import uses a lazy import pattern so check_status.py remains functional even when sync dependencies are broken.
- **Validation:** `grep -A3 "except Exception" skills/sprint-monitor/scripts/check_status.py`
- **Status:** Resolved

### BH-P11-108 — `compute_review_rounds` reports misleading "highest" story when max rounds is 0
- **Severity:** Medium
- **Category:** logic-bug
- **Location:** `scripts/sprint_analytics.py:117-119`
- **Problem:** When all PRs have 0 review rounds (no reviews submitted), `max(rounds_per_pr, key=lambda x: x[1])` returns an arbitrary PR (the first one with max value 0). The report then says something like `"highest: US-001: Add auth, 0 rounds"`, implying US-001 was reviewed 0 times specifically. This is misleading — no PR was reviewed at all. The `max_story` field should be empty or "N/A" when `max_rounds` is 0.
- **Acceptance Criteria:** When `max_rounds == 0`, `max_story` is set to "none" or similar, and `format_report` handles this case distinctly.
- **Validation:** `python3 -c "
rounds = [('US-001: Add auth', 0), ('US-002: Fix bug', 0)]
ms, mr = max(rounds, key=lambda x: x[1])
print(f'highest: {ms}, {mr} rounds')  # misleading
"`
- **Status:** Resolved

### BH-P11-109 — `_parse_team_index` treats malformed separator row as data
- **Severity:** Medium
- **Category:** boundary
- **Location:** `scripts/validate_config.py:521`
- **Problem:** The separator row check `all(re.match(r"^[-:]+$", c) for c in cells)` requires every cell to have at least one character matching `[-:]`. But after `stripped.strip("|").split("|")`, a table like `|---|---|` (with no trailing content) produces cells `["---", "---"]` which works. However, `| --- |  |` produces cells `["---", " "]` — the space-only cell fails the `[-:]+` match because space is not in the character class. The row is treated as data, adding a persona with name `---` and role ` `. More commonly, `|---|` (single-column) produces `["---"]` which passes the check but has fewer cells than headers, so it silently creates a row with only the first column populated.
- **Acceptance Criteria:** Separator detection strips whitespace from cells before checking, and also handles the case where the number of cells differs from headers.
- **Validation:** `python3 -c "
import re
cells = ['---', ' ']
result = all(re.match(r'^[-:]+$', c) for c in cells)
print(f'Detected as separator: {result}')  # False — bug
cells2 = ['---', ' '.strip()]
result2 = all(re.match(r'^[-:]+$', c) for c in cells2 if c)
print(f'After strip+filter: {result2}')  # True
"`
- **Status:** Resolved

### BH-P11-110 — `validate_project` missing-file check uses string formatting with user-controlled config_dir
- **Severity:** Low
- **Category:** security
- **Location:** `scripts/validate_config.py:404-405`
- **Problem:** `template.format(config_dir=config_dir)` uses Python's `str.format()` with the `config_dir` parameter, which is user-controlled (from sys.argv or function argument). If `config_dir` contains format specifiers like `{0}` or `{__class__}`, `str.format()` will try to resolve them, potentially raising `IndexError`, `KeyError`, or exposing internal object attributes. While this is unlikely in normal usage (config_dir is a path like `sprint-config`), it's a format string injection pattern. Example: `config_dir = "{0.__class__}"` would crash with an IndexError.
- **Acceptance Criteria:** Use f-string interpolation or `template.replace("{config_dir}", config_dir)` instead of `.format()` to prevent format string injection.
- **Validation:** `python3 -c "
template = '{config_dir}/project.toml'
try:
    result = template.format(config_dir='{0.__class__}')
    print(f'Result: {result}')
except (IndexError, KeyError) as e:
    print(f'Format injection error: {e}')
"`
- **Status:** Resolved

### BH-P11-111 — `sprint_analytics.main` arg parsing allows `-h` to be treated as sprint number
- **Severity:** Low
- **Category:** logic-bug
- **Location:** `scripts/sprint_analytics.py:192-206`
- **Problem:** The help check at line 192 only triggers when `sys.argv[1]` is exactly `-h` or `--help`. After that, `load_config()` is called (which may fail). Then at line 204, if `sys.argv[1].isdigit()` is checked. If someone passes `--verbose` or any non-digit, non-help flag, it hits the `else` branch at line 207 which prints usage and exits. But if someone passes `-h` as the SECOND argument (`sprint_analytics.py 1 -h`), the help check at line 192 sees `sys.argv[1] = "1"` (not `-h`), skips help, and tries to run analytics for sprint 1. The `-h` at argv[2] is silently ignored. This is a minor UX issue, not a bug.
- **Acceptance Criteria:** Use `argparse` for consistent arg parsing, or document that `-h` must be the first argument.
- **Validation:** `python3 -c "import sys; sys.argv = ['x', '1', '-h']; print(sys.argv[1] in ('-h', '--help'))"`
- **Status:** Resolved

### BH-P11-112 — `do_release` catches `RuntimeError` from `gh()` but not from subprocess calls
- **Severity:** Low
- **Category:** error-handling
- **Location:** `skills/sprint-release/scripts/release_gate.py:437-448`
- **Problem:** In `do_release()`, the `git status --porcelain` call at line 437 checks `r.returncode` but not for `FileNotFoundError` if git is not installed. The `subprocess.run` call will raise `FileNotFoundError` (not `RuntimeError`), which is unhandled. The function would crash with a traceback instead of printing a clean error message. Similarly, the `git rev-parse HEAD` at line 472 and all subsequent `subprocess.run` calls for git commands assume git is available. While `gh auth status` checks are done elsewhere, the release flow itself doesn't verify git availability upfront.
- **Acceptance Criteria:** Wrap the initial git subprocess calls in try/except `FileNotFoundError` with a clean error message, or add a git-availability check at the top of `do_release()`.
- **Validation:** `python3 -c "
import subprocess
try:
    subprocess.run(['nonexistent-command'], capture_output=True)
except FileNotFoundError as e:
    print(f'Caught: {e}')
"`
- **Status:** Resolved

### BH-P11-113 — `manage_sagas.update_team_voices` produces merged blockquote instead of separate ones
- **Severity:** Low
- **Category:** logic-bug
- **Location:** `scripts/manage_sagas.py:255-257`
- **Problem:** Between voice entries, the code inserts a `>` line (line 256). In markdown, a line containing only `>` is a continuation of the blockquote, not a separator. All voices merge into a single continuous blockquote when rendered. To actually separate blockquotes, there must be a non-blockquote line (empty line without `>`) between them. The visual intent is separate blockquotes per persona, but the markdown output produces one merged blockquote.
- **Acceptance Criteria:** Use an empty line (without `>` prefix) between voices to create visually separate blockquotes. Or use `""` instead of `">"` as the separator line.
- **Validation:** `python3 -c "
lines = ['> **Alice:** \"hello\"', '>', '> **Bob:** \"world\"']
print('Rendered as one blockquote (bug):')
print('\\n'.join(lines))
print()
lines2 = ['> **Alice:** \"hello\"', '', '> **Bob:** \"world\"']
print('Rendered as two blockquotes (fix):')
print('\\n'.join(lines2))
"`
- **Status:** Resolved

### BH-P11-114 — `check_direct_pushes` jq filter selects single-parent commits but misses initial commit
- **Severity:** Low
- **Category:** logic-bug
- **Location:** `skills/sprint-monitor/scripts/check_status.py:283`
- **Problem:** The `--jq` filter `'[.[] | select(.parents | length == 1) | ...]'` identifies direct pushes by selecting commits with exactly one parent (non-merge commits). But the initial commit of a repository has 0 parents, which would be filtered out. If someone force-pushes a new root commit to the base branch (rewriting history), this would not be detected. Additionally, octopus merges (3+ parents) are also filtered out, but these are extremely rare in practice.
- **Acceptance Criteria:** Document that `length == 1` intentionally excludes merge commits and the initial commit. Or use `length <= 1` to also catch force-pushed root commits.
- **Validation:** `python3 -c "
# Simulating: initial commit has 0 parents
commits = [{'parents': [], 'sha': 'abc'}]
filtered = [c for c in commits if len(c['parents']) == 1]
print(f'Direct pushes detected: {len(filtered)} (should be 1 if initial commit is direct)')
"`
- **Status:** Resolved
