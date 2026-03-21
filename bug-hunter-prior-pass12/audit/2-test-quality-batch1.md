# Test Quality Audit — Batch 1

**Files audited:**
- `tests/test_release_gate.py` (source: `skills/sprint-release/scripts/release_gate.py`)
- `tests/test_pipeline_scripts.py` (multiple source scripts)
- `tests/test_gh_interactions.py` (tests GitHub interaction patterns)
- `tests/fake_github.py` (mock infrastructure)
- `tests/gh_test_helpers.py` (test helpers)

**Date:** 2026-03-15

---

## Executive Summary

The test suite is significantly above average for a project of this kind. The `FakeGitHub` infrastructure is thoughtful — strict mode flag enforcement, dispatch routing, and the `MonitoredMock`/`patch_gh` helper that warns when tests forget to verify call arguments. These are good defenses against the most common mock-based testing mistakes.

That said, there are real findings. The most consequential ones involve the `do_release()` tests, which mock so aggressively that the production code's orchestration logic is barely exercised. Several mock-based tests return exactly the data the assertion checks, never proving the production code actually queries or filters correctly. And `FakeGitHub` has fidelity gaps where its behavior diverges from what production code relies on.

**Finding count by severity:**
- HIGH: 5
- MEDIUM: 8
- LOW: 4

---

## Findings

### Finding 1: do_release happy path mocks away the code under test
- **File:** `tests/test_release_gate.py:527-591`
- **Anti-pattern:** The Mockingbird
- **Severity:** HIGH
- **Evidence:** `test_happy_path` patches 5 things: `calculate_version`, `write_version_to_toml`, `subprocess.run`, `find_milestone_number`, and `gh`. The test then asserts that these mocks were called in the right order with the right arguments. But it never verifies that `do_release()` actually orchestrates correctly — it verifies that the test's mock wiring is correct. The real `write_version_to_toml` never runs. The real `calculate_version` never runs. The real `generate_release_notes` runs but writes to a temp file that `gh` (mocked) ignores. The key assertion on line 562 is `self.assertGreaterEqual(mock_run.call_count, 6)` — a lower-bound check on call count, which would pass if extra commands were added or commands were duplicated.
- **Why it matters:** If `do_release()` reordered its steps (e.g., pushing before tagging, or closing the milestone before creating the release), all assertions would still pass. The test verifies the mock call sequence, not the actual release orchestration. The existing comment at line 489-496 acknowledges this trade-off but claims it "verifies the call sequence" — yet the sequence checks are position-based indexes into `mock_run.call_args_list` which would silently shift if any intermediate call was added or removed.

### Finding 2: gate_prs does not verify milestone filtering in production code
- **File:** `tests/test_gh_interactions.py:377-401`
- **Anti-pattern:** Happy Path Tourist + Permissive Validator
- **Severity:** HIGH
- **Evidence:** `gate_prs()` in production (line 174-193 of `release_gate.py`) fetches ALL open PRs and then filters client-side by milestone title. The test `test_pr_for_different_milestone` (line 394-401) returns `[{"number": 10, "title": "feat: thing", "milestone": {"title": "Sprint 2"}}]` from the mock and asserts `gate_prs("Sprint 1")` passes. This is correct but insufficient — it never tests what happens when the mock returns PRs for BOTH Sprint 1 AND Sprint 2 in the same list. More critically, the mock at line 379 patches `release_gate.gh_json` to return a fixed list. If production code changed its `gh_json` query to add `--milestone` filtering (which it currently doesn't have), or changed the `--json` fields, or removed the `--limit 500` safety cap, all tests would still pass because they never verify the query parameters. The `test_limit_hit_fails_gate` test at line 405 patches away `warn_if_at_limit` entirely — good that it tests the 500-PR edge case, but it means the warn function's interaction with gate_prs is never tested.
- **Why it matters:** `gate_prs` is a release gate. A silent regression in the query (e.g., accidentally requesting `--state all` instead of default `open`) could let the gate pass incorrectly. The production code's client-side filtering is the actual safety net, and only `test_open_pr_for_milestone` validates it — with a single PR in the list.

### Finding 3: check_ci tests never verify the query parameters match production
- **File:** `tests/test_gh_interactions.py:444-479`
- **Anti-pattern:** The Mockingbird
- **Severity:** MEDIUM
- **Evidence:** `TestCheckCI.test_all_passing` (line 455) patches `check_status.gh_json` with a return value, then checks that `call_args` contains `"run"` and `"--json"`. But look at the production code (check_status.py line 39-41): it queries `run list --limit 5 --json status,conclusion,name,headBranch,databaseId`. The test never verifies that `--limit 5` is passed, never verifies the specific JSON fields requested. The test mock returns `[{"status": "completed", "conclusion": "success", "name": "CI", "headBranch": "main", "databaseId": 1}]` — which happens to contain all the fields the production code needs. But if production code added a field (e.g., `createdAt`), the test would still pass because the mock always returns whatever you told it to. Conversely, if production code removed a field from the `--json` request, the test would still pass because it doesn't verify the query.
- **Why it matters:** The test provides false confidence that the correct GitHub API query is being made. The `BH-P11-063` comment on line 463 shows awareness of this problem, but the assertion (`self.assertIn("run", call_args)`) is too weak to be useful — "run" is the command, not a meaningful filter parameter.

### Finding 4: FakeGitHub _issue_list ignores --search for non-milestone patterns
- **File:** `tests/fake_github.py:497-554`
- **Anti-pattern:** Shallow End (Tier 3)
- **Severity:** MEDIUM
- **Evidence:** `_issue_list` (line 497) parses `--search` via `_extract_search_milestone`, which only understands the `milestone:"X"` pattern. Production code in `sprint_analytics.compute_review_rounds` uses `--search 'milestone:"Sprint 1"'`, which FakeGitHub handles. But any other `--search` pattern (e.g., `label:bug`, `is:pr`, or compound queries like `milestone:"Sprint 1" label:sp:3`) would be silently ignored — the issues would be returned unfiltered. FakeGitHub's strict mode warns about unimplemented flags but `--search` IS in `_IMPLEMENTED_FLAGS` (line 192), so no warning is emitted even though the implementation only handles one sub-pattern.
- **Why it matters:** If production code adds search queries beyond `milestone:`, tests using FakeGitHub will silently return unfiltered results, creating false passes. The `_IMPLEMENTED_FLAGS` registration is overgenerous — it claims `search` is implemented when it's only partially implemented.

### Finding 5: check_direct_pushes FakeGitHub test does not exercise the jq filter
- **File:** `tests/test_gh_interactions.py:1491-1565`
- **Anti-pattern:** Shallow End
- **Severity:** HIGH
- **Evidence:** Production `check_direct_pushes` (check_status.py line 284-291) passes a complex `--jq` filter: `'[.[] | select(.parents | length == 1) | {sha: .sha[:8], message: .commit.message, author: .commit.author.name, date: .commit.author.date}]'`. This filter does two critical things: (1) selects only commits with exactly 1 parent (direct pushes, not merges), and (2) reshapes the output into `{sha, message, author, date}` objects. The `TestCheckDirectPushesFakeGH.test_direct_pushes_detected` test (line 1502) sets up `self.fake.commits_data` with commits containing `parents` arrays — but when `jq` is not installed (common in CI), FakeGitHub falls through to `_maybe_apply_jq` which returns the raw unfiltered JSON. The production code then receives full commit objects (not the `{sha, message, author, date}` shape) and must handle the structural difference. When `jq` IS installed, the filter runs, but the test's assertions at line 1536 (`self.assertIn("2 direct push", report[0])`) don't distinguish between the two code paths. The test passes either way, meaning it can't detect if the jq filter is broken.
- **Why it matters:** A broken jq expression in production (e.g., a typo in the select clause) would only be caught if jq is installed during testing AND the test verifies the filtered vs unfiltered path separately. Currently, neither condition is guaranteed. The merge commit at line 1523-1530 (2 parents) should be filtered out by jq but would still appear in the no-jq path — yet the test asserts "2 direct push" without confirming the merge commit was actually excluded.

### Finding 6: TestDoRelease patches generate_release_notes indirectly and never verifies its output
- **File:** `tests/test_release_gate.py:525-600`
- **Anti-pattern:** Happy Path Tourist
- **Severity:** MEDIUM
- **Evidence:** In `test_happy_path`, `generate_release_notes` runs with real production code but its output goes to a temp file which is passed to `mock_gh` via `--notes-file`. The test asserts `any("--notes-file" in str(arg) ... for arg in gh_calls[0])` (line 588-590) — checking that the flag was passed, but never reading or verifying the content of the notes file. Meanwhile, `generate_release_notes` calls `subprocess.run(["git", "rev-parse", "--verify", ...])` to check tag existence (line 381-384 of release_gate.py), which hits the global `mock_run` and always returns success — meaning the compare link path is non-deterministically tested depending on what `mock_run.side_effect` returns for that specific command shape.
- **Why it matters:** A bug in `generate_release_notes` that produces empty or malformed notes would not be caught by the do_release happy path test. The test in `TestGenerateReleaseNotes` (line 416-438 in test_gh_interactions.py) does test the function directly, so coverage exists, but the integration between note generation and the release flow is untested.

### Finding 7: TestValidateGates test_all_pass vacuous truth for Tests and Build gates
- **File:** `tests/test_release_gate.py:146-163`
- **Anti-pattern:** Green Bar Addict
- **Severity:** MEDIUM
- **Evidence:** `test_all_pass` (line 146) sets `config["ci"]["check_commands"]` to `[]` and `config["ci"]["build_command"]` to `""`. This means `gate_tests` and `gate_build` both immediately return `(True, "No check_commands configured")` and `(True, "No build_command configured")` respectively. The test then asserts `self.assertTrue(all(r[1] for r in results))` — but two of the five gates passed vacuously. The assertion `self.assertEqual(len(results), 5)` on line 162 confirms 5 gates ran, but doesn't verify that Tests and Build actually tested anything. The test `test_all_pass_with_real_commands` (line 218) fixes this by providing actual commands, which is good — but `test_all_pass` is still listed as a passing test that validates "all gates pass" when 40% of the gates didn't actually execute.
- **Why it matters:** On its own this finding is low severity since `test_all_pass_with_real_commands` covers the non-vacuous case. But `test_all_pass` inflates the apparent coverage of `validate_gates`, and someone reading the test names might assume the basic test covers the full flow. Renaming to `test_all_pass_with_empty_ci_config` would clarify intent.

### Finding 8: Copy-paste setup across TestDoRelease test methods
- **File:** `tests/test_release_gate.py:527-994`
- **Anti-pattern:** Copy-Paste Archipelago
- **Severity:** LOW
- **Evidence:** Tests 1-9 in `TestDoRelease` all follow the same pattern: `@patch` 3-5 decorators, set `mock_calc.return_value = (version, base, bump, commits)`, set `mock_write_toml.return_value = None`, set `mock_run.side_effect = _make_subprocess_side_effect(...)`, create a `config` dict. The config dict `{"project": {"name": "TestProject", "repo": "owner/repo"}, "ci": {}, "paths": {"sprints_dir": "sprints"}}` appears 6+ times with minor variations. The decorator stacking (`@patch("release_gate.gh")`, `@patch("release_gate.find_milestone_number")`, `@patch("release_gate.subprocess.run")`, etc.) is repeated verbatim across tests.
- **Why it matters:** When a new dependency is added to `do_release()` (e.g., a new function call), every test must be updated individually. The `_make_subprocess_side_effect` helper shows the right instinct, but the overall setup burden makes it fragile to maintain.

### Finding 9: TestCheckMilestone uses call-order-based mock dispatch
- **File:** `tests/test_gh_interactions.py:1922-1978`
- **Anti-pattern:** Inspector Clouseau
- **Severity:** MEDIUM
- **Evidence:** `TestCheckMilestone._mock_gh_json` (line 1925) returns different data based on call order (`call_count[0] == 1` → milestones, else → issues). This tightly couples the test to the production code's call sequence. If `check_milestone()` were refactored to query issues before milestones, or to make an additional API call, the test would silently break — the second call would get milestone data instead of issue data, producing wrong but possibly-passing results. The production code at check_status.py queries milestones first via `find_milestone` and then issues via `gh_json`, so the ordering is currently correct, but the test doesn't validate WHAT is being queried — only that two calls happen in a specific order.
- **Why it matters:** Call-order-based mocking is one of the most fragile patterns. Refactoring production code to cache results, add logging calls, or change query order would break these tests in ways that are hard to diagnose.

### Finding 10: FakeGitHub PATCH milestone always returns empty object
- **File:** `tests/fake_github.py:362-364`
- **Anti-pattern:** Rubber Stamp
- **Severity:** MEDIUM
- **Evidence:** When `_handle_api` detects a PATCH on milestones (line 362-364), it returns `self._ok("{}")` without actually modifying the milestone's state. Production code at `release_gate.py:607-609` calls `gh(["api", f"repos/{{owner}}/{{repo}}/milestones/{ms_num}", "-X", "PATCH", "-f", "state=closed"])` to close a milestone. FakeGitHub accepts this call and returns success, but the milestone remains `"state": "open"` in `self.milestones`. Any test that later queries milestone state after a PATCH will see stale data.
- **Why it matters:** The `TestDoRelease.test_happy_path` test (test_release_gate.py:532) uses global mocks, not FakeGitHub, so this specific gap doesn't cause a current test failure. But `TestCheckStatusMainIntegration` (test_gh_interactions.py:2672) and other FakeGitHub-backed tests could be silently wrong if they assume milestone state is updated after a close operation. If someone writes a test that verifies "milestone is closed after release," FakeGitHub will report it as still open.

### Finding 11: gate_stories test asserts "closed" in detail but doesn't verify state=open filter
- **File:** `tests/test_gh_interactions.py:318-328`
- **Anti-pattern:** Permissive Validator
- **Severity:** MEDIUM
- **Evidence:** `TestGateStories.test_all_closed` (line 319) mocks `gh_json` to return `[]` and then asserts `self.assertIn("closed", detail.lower())`. The assertion checks the human-readable message, not the correctness of the query. The call_args check at line 325-328 verifies `"--milestone"` and `"Sprint 1"` and `"--state"` are in the args list, but never verifies that the state value is `"open"`. Production code (release_gate.py:142) passes `"--state", "open"` — if this were changed to `"--state", "all"`, the test would still pass because it only checks for the presence of `"--state"`, not its value.
- **Why it matters:** The `--state open` filter is the semantic core of `gate_stories` — it asks "are there any open issues?" If someone changed it to `--state all` or `--state closed`, the gate would produce nonsensical results, but the test would still be green.

### Finding 12: FakeGitHub _issue_create does not update milestone open_issues count
- **File:** `tests/fake_github.py:454-495`
- **Anti-pattern:** Shallow End
- **Severity:** LOW
- **Evidence:** When `_issue_create` adds an issue to a milestone, it does not increment the milestone's `open_issues` counter. Similarly, `_issue_close` (line 588-603) sets `issue["state"]` to `"closed"` but does not decrement `open_issues` or increment `closed_issues` on the associated milestone. Production code in `check_milestone` (check_status.py) reads `ms["open_issues"]` and `ms["closed_issues"]` from the milestone to compute progress. Tests must pre-populate these counters manually (e.g., line 2692-2695 in test_gh_interactions.py sets `open_issues: 1, closed_issues: 1`), which means the test fixture and the actual issue list can disagree. In `TestCheckStatusMainIntegration`, the milestone says `open_issues: 1, closed_issues: 1` but 2 issues are added (1 closed, 1 open) — which happens to match, but only by coincidence.
- **Why it matters:** If a test creates issues via FakeGitHub and then calls `check_milestone`, the progress numbers will reflect the manually set milestone counters, not the actual issue states. This inconsistency can mask bugs where production code assumes issue counts and milestone counters are in sync.

### Finding 13: TestSyncOneGitHubAuthoritative spy could miss async gh calls
- **File:** `tests/test_gh_interactions.py:1615-1661`
- **Anti-pattern:** Permissive Validator
- **Severity:** LOW
- **Evidence:** `TestSyncOneGitHubAuthoritative.test_no_gh_calls_on_status_disagreement` (line 1623) patches `subprocess.run` with a spy that records all `gh` CLI calls. It then asserts that no `gh issue` or `gh label` calls were made. The spy checks `args[0] == "gh"` and `args[1] in ("issue", "label")`, which would miss `gh api` calls that modify state (e.g., `gh api repos/.../issues/5 -X PATCH`). If `sync_one` were refactored to use the API endpoint directly instead of `gh issue edit`, the test would still pass despite the function making a state-modifying call to GitHub.
- **Why it matters:** The test's intent is "sync_one must not push state to GitHub." The check should verify NO gh calls at all (not just `issue`/`label` subcommands), since any gh call in sync_one would be a violation of the GitHub-as-source-of-truth principle.

### Finding 14: TestDoReleaseDryRunIntegration mock does not simulate commit format correctly
- **File:** `tests/test_release_gate.py:1090-1155`
- **Anti-pattern:** The Mockingbird
- **Severity:** HIGH
- **Evidence:** `TestDoReleaseDryRunIntegration._make_side_effect` (line 1114-1136) simulates `git log` output as `"abc1234 feat: add new feature\ndef5678 fix: resolve bug\n"`. But production `parse_commits_since` (release_gate.py:59-79) uses a custom format: `--format="%s\n%b\x00--END--\x00"` which produces commit subjects and bodies separated by `\x00--END--\x00`. The mock's output (`"abc1234 feat: add new feature\n..."`) does not contain the `\x00--END--\x00` delimiter, so `parse_commits_since` will parse it as a single commit with the subject `"abc1234 feat: add new feature"` and the body containing the rest. The `abc1234` hash prefix will be part of the subject, making it fail the conventional commit regex in `determine_bump`. The `calculate_version` call in `do_release` will then return `bump_type = "patch"` (default for unrecognized commits) instead of the expected `"minor"` for a feat commit. The test asserts `self.assertIn("1.0.0", output)` (line 1151) and `self.assertIn("DRY-RUN", output)` (line 1152) — both of which pass regardless of what version was calculated, since `"1.0.0"` appears in the base version output line.
- **Why it matters:** This integration test claims to exercise "version calc + notes generation" (line 1139) but the mock produces garbled git log output that the parser handles wrong, and the assertions are too loose to detect the parsing failure. The test provides false confidence in the dry-run integration path.

### Finding 15: test_pipeline_scripts TestCoverage assertions too structural
- **File:** `tests/test_pipeline_scripts.py:162-186`
- **Anti-pattern:** Rubber Stamp
- **Severity:** LOW
- **Evidence:** `test_coverage_no_actual_tests` (line 165) asserts `len(report["planned"]) > 0`, `len(report["implemented"]) == 0`, and `planned_ids == missing_ids`. The check at line 181 (`any(tc_id.startswith("TC-") or tc_id.startswith("GP-") for tc_id in planned_ids)`) only verifies that at least one planned ID has the right prefix — it doesn't verify the actual count or specific IDs. If `parse_planned_tests` silently dropped half the test cases due to a regex bug, this test would still pass as long as at least one TC- or GP- prefixed ID survived.
- **Why it matters:** The test verifies structure ("there are planned tests and they're all missing") but not correctness ("the specific 23 planned tests from the Hexwise fixture are all accounted for"). The `test_parse_stories_finds_all` test in TestTraceability (line 101-107) does this correctly by checking `len(story_ids) == 17`.

### Finding 16: MonitoredMock intercepts attribute access but not item access
- **File:** `tests/gh_test_helpers.py:40-65`
- **Anti-pattern:** Shallow End
- **Severity:** MEDIUM
- **Evidence:** `MonitoredMock.__getattr__` (line 52) intercepts `mock.call_args`, `mock.call_args_list`, etc. But if a test accesses call arguments via `mock.call_args[0][0]` (item access on the result), the `__getattr__` is called for `call_args` (setting `_args_checked = True`). This works correctly. However, the `__call__` method (line 60-61) delegates to the inner mock directly: `return object.__getattribute__(self, "_mock")(*args, **kwargs)`. This means the MonitoredMock does not track whether the mock's return value was used or discarded — a test could call the production function, receive a result through the mock, and never check that result. The `patch_gh` warning only fires if `call_args` was never accessed, not if the production function's return value was never validated.
- **Why it matters:** A test like `with patch_gh("module.gh_json", return_value=[{"x": 1}]) as mock: result = production_fn(); _ = mock.call_args` would pass the MonitoredMock audit but never assert anything about `result`. The tool catches "forgot to check the query" but misses "forgot to check the answer." This is a minor gap since the tool's stated purpose is query verification, not result verification.

### Finding 17: Time Bomb in test fixtures
- **File:** `tests/test_gh_interactions.py:499,1013,1043`
- **Anti-pattern:** Time Bomb
- **Severity:** LOW
- **Evidence:** Multiple tests use hardcoded dates like `"createdAt": "2026-03-09T00:00:00Z"` (line 499), `"merged_at": "2026-03-10T12:00:00Z"` (line 1013), `"date": "2026-03-10T12:00:00Z"` (line 1512). These are future dates (as of writing) which works fine, but the `_hours` and `_age` tests (lines 1881-1914) compute deltas from `datetime.now(timezone.utc)`, making them sensitive to when the test is run. While these time-relative tests use `timedelta` correctly (they compute a relative time, not hardcoded timestamps), the hardcoded `"2026-03-09T00:00:00Z"` dates in PR fixtures could cause age-related assertions to produce unexpected values if the test suite is ever run after those dates have passed and some test starts computing ages from them.
- **Why it matters:** Low practical risk since none of the hardcoded dates are used in age calculations, but it's a maintenance concern. Using relative timestamps or a frozen-time utility would be more robust.

---

## Mock-to-Assertion Ratio Analysis

| File | Mock setup lines (approx) | Assertion lines (approx) | Ratio |
|------|--------------------------|--------------------------|-------|
| test_release_gate.py (TestDoRelease) | ~180 | ~120 | 1.5:1 |
| test_gh_interactions.py (gate tests) | ~80 | ~60 | 1.3:1 |
| test_gh_interactions.py (check_status) | ~100 | ~90 | 1.1:1 |
| test_gh_interactions.py (bootstrap) | ~60 | ~40 | 1.5:1 |
| test_pipeline_scripts.py | ~30 | ~180 | 0.2:1 |

The ratio is generally healthy (under 3:1 everywhere). `test_pipeline_scripts.py` has the best ratio because it mostly tests pure functions against fixture files with no mocking. `TestDoRelease` is the worst because of the heavy patching, but still under the 3:1 threshold.

---

## FakeGitHub Fidelity Assessment

### What it faithfully reproduces:
- Issue CRUD (create, list, edit, close) with state/milestone/label filtering
- PR lifecycle (create, review, merge) with state tracking
- Label idempotency (--force flag via dict-based storage)
- Milestone create with duplicate rejection
- Run list with branch/status/limit filtering
- Release create and view
- Timeline events for PR linking
- Compare endpoint for branch divergence
- Commits endpoint with since-date filtering
- jq evaluation when pyjq is installed
- Flag enforcement (unknown flags raise, unimplemented flags warn in strict mode)

### What it does NOT faithfully reproduce:
1. **Milestone state mutation** — PATCH milestone returns `{}` without updating state
2. **Issue count tracking** — Creating/closing issues doesn't update milestone `open_issues`/`closed_issues`
3. **Search query parsing** — Only `milestone:"X"` is parsed; other search predicates are silently ignored
4. **Pagination** — All data is returned at once; `--paginate` is a no-op. Real `gh` may return concatenated JSON arrays
5. **Error responses** — Failed API paths return generic error strings, not realistic GitHub API error shapes
6. **Rate limiting** — No simulation of GitHub API rate limits
7. **Issue-PR linking** — Timeline events must be manually populated; no automatic linking when PR body mentions `#N`

---

## Recommendations (prioritized)

1. **Fix Finding 14 (HIGH):** The dry-run integration test's mock produces invalid git log output. Either fix the mock to produce `\x00--END--\x00`-delimited output, or tighten assertions to verify the actual calculated version.

2. **Fix Finding 5 (HIGH):** Split `test_direct_pushes_detected` into two tests: one that skips when jq is unavailable (testing the graceful degradation path), and one that requires jq and verifies merge commits are excluded. Use `@unittest.skipUnless(FakeGitHub._check_jq(), "jq not installed")` for the jq-dependent test.

3. **Fix Finding 1 (HIGH):** Add at least one do_release test that uses FakeGitHub instead of global mocks, verifying actual state changes (release created, milestone closed, status file updated). The existing `test_all_pass_with_real_commands` in TestValidateGates shows this pattern working.

4. **Fix Finding 11 (MEDIUM):** In `test_all_closed`, assert `"open" in call_args` (not just `"--state" in call_args`) to verify the state filter value.

5. **Fix Finding 10 (MEDIUM):** Implement milestone state mutation in FakeGitHub's PATCH handler so tests that close milestones can verify the state change.

6. **Fix Finding 4 (MEDIUM):** Either downgrade `search` from `_IMPLEMENTED_FLAGS` to just `_KNOWN_FLAGS` (so strict mode warns), or document the partial implementation with an inline comment that names the supported pattern.

7. **Consider Finding 9 (MEDIUM):** Replace call-order-based mocking in TestCheckMilestone with argument-inspecting side effects that return milestones or issues based on what's being queried.
