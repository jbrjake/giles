# Bug Hunter Phase 2 — Test Quality Audit

**Date:** 2026-03-18
**Scope:** `tests/test_kanban.py` (primary), `tests/test_sprint_runtime.py`, `tests/test_verify_fixes.py`, `tests/test_property_parsing.py`
**Items:** BH22-050 through BH22-062

---

## Summary

The test suite is solid overall. The property tests (`test_property_parsing.py`) are genuinely rigorous. The `test_verify_fixes.py` integration tests are substantive. The new `test_kanban.py` has good coverage of the happy path and revert paths, but has specific gaps in: body-update verification, reviewer-only assign path, do_sync's "local absent from GitHub" path, atomic_write exception-safety, and a subtle structural flaw in the `_issue()` test helper. None of these are phantom bugs — each corresponds to real untested production behaviour.

---

### BH22-050: `_issue()` helper always hardcodes `state: "open"`, masking closed-issue kanban logic

**Severity:** MEDIUM
**Category:** `test/thin`
**Location:** `tests/test_kanban.py:426-430`

**Problem:** The `_issue()` helper in `TestSyncCommand` accepts a `state` parameter and uses it to auto-generate labels, but always returns `{"state": "open", ...}` regardless of what `state` was passed. `kanban_from_labels()` uses `issue.get("state") == "closed"` both as a fallback default and as an override that forces `"done"` on closed issues with stale labels (`BH21-012`). Neither branch of that logic is reachable from any sync test. If the closed-issue override logic regresses (e.g., a future change removes the override), no test catches it.

**Acceptance Criteria:**
- [ ] Add a test `test_sync_closed_issue_becomes_done` that passes an issue with `state: "closed"` and no kanban label, and asserts the local tracking file status becomes `"done"`.
- [ ] Add a test `test_sync_closed_issue_overrides_stale_label` that passes `state: "closed"` with `labels: ["kanban:dev"]` and asserts local status becomes `"done"` (BH21-012 path).
- [ ] Fix `_issue()` to propagate the `state` argument into the returned dict, or document the intentional mismatch.

---

### BH22-051: `test_assign_implementer` does not verify body-update was issued

**Severity:** MEDIUM
**Category:** `test/thin`
**Location:** `tests/test_kanban.py:373-392`

**Problem:** `do_assign()` has two distinct GitHub write operations when an implementer is set: (1) add persona label, and (2) update the issue body replacing `[Unassigned]` with the implementer name. The test provides a mock body that matches `_PERSONA_HEADER_PATTERN`, so the body-update branch IS exercised — but the test never asserts that `--body` appeared in any `gh` call. The body-update could be silently deleted or short-circuited and this test would still pass.

**Acceptance Criteria:**
- [ ] Add an assertion in `test_assign_implementer` that `"--body"` (or `"rae"`) appears in `str(mock_gh.call_args_list)` to verify the body-edit `gh` call was issued.
- [ ] Add a complementary test `test_assign_implementer_no_pattern_match_skips_body_update` that provides a body without the `[Unassigned]` pattern and asserts the `--body` call was NOT made.

---

### BH22-052: `test_assign_both` accesses `mock_json.call_args` only to satisfy MonitoredMock, not to verify behavior

**Severity:** LOW
**Category:** `test/mock-abuse`
**Location:** `tests/test_kanban.py:414-415`

**Problem:** The comment on line 414 reads `"# Satisfy MonitoredMock for mock_json"`. This is an explicit admission that the access to `mock_json.call_args` is there to silence a tool warning, not to assert anything meaningful. The check `self.assertIn("view", str(mock_json.call_args))` is incidentally correct, but it was added as boilerplate to appease `patch_gh`'s monitoring rather than as a deliberate assertion. This degrades the monitoring tool's signal — if `gh_json` is called without `"view"` for some other reason, the assertion would still pass because it only checks that "view" appears somewhere.

**Acceptance Criteria:**
- [ ] Replace the comment-led fake access with a purposeful assertion that verifies the issue number was passed to `gh_json`, e.g. `self.assertIn("43", str(mock_json.call_args))` (using the issue number from `_make_tf`).
- [ ] Remove the comment `# Satisfy MonitoredMock for mock_json` — if an assertion is needed there, it should be self-documenting.

---

### BH22-053: No test for `do_assign` with reviewer-only (no implementer)

**Severity:** MEDIUM
**Category:** `test/missing`
**Location:** `tests/test_kanban.py:346-415`

**Problem:** `do_assign()` has a distinct code path when only `reviewer` is provided and `implementer` is empty: it skips the `gh_json` body-view call entirely and only adds the `persona:reviewer` label. No test covers this path. `test_assign_both` always sets both. `test_assign_implementer` always sets implementer. If the reviewer-only path regresses (e.g., accidentally requiring `gh_json`), nothing catches it.

**Acceptance Criteria:**
- [ ] Add `test_assign_reviewer_only` that calls `do_assign(tf, reviewer="chen")` with no implementer, using `patch_gh("kanban.gh")` only (no `kanban.gh_json` patch), and asserts: `result is True`, local `reviewer == "chen"`, `"persona:chen"` is in `gh` call args, and `"view"` is NOT in any `gh` call (confirming `gh_json` was never called).

---

### BH22-054: `test_transition_reverts_on_github_failure` verifies revert with a thin call-args check

**Severity:** LOW
**Category:** `test/thin`
**Location:** `tests/test_kanban.py:309-320`

**Problem:** Line 320: `self.assertIn("issue", str(mock.call_args))` only confirms that the gh mock was called with something containing the string `"issue"`. Every `gh(["issue", ...])` call would satisfy this. It does not verify the label names, the issue number, or the transition direction. The local-revert assertion (line 317-318) is the genuinely valuable check here, but the call-args check adds no additional signal.

**Acceptance Criteria:**
- [ ] Strengthen the call-args check to assert the specific issue number (`"42"`) was in the args, e.g. `self.assertIn("42", str(mock.call_args))`.
- [ ] Optionally assert `"kanban:design"` appears in the call args (the failed label that triggered the revert), to prove the test knows WHAT call failed.

---

### BH22-055: `test_atomic_write_no_partial_state` does not test exception-safety path

**Severity:** MEDIUM
**Category:** `test/missing`
**Location:** `tests/test_kanban.py:187-199`

**Problem:** `atomic_write_tf()` uses a write-to-`.tmp`-then-rename strategy. The test only verifies the happy path (no `.tmp` after two successful writes). There is no test for the exception-safety path: if `write_tf()` raises mid-write, the `.tmp` file should be left in place (or cleaned up), but crucially the destination file should retain its previous content. The `atomic_write_tf` implementation does NOT clean up the `.tmp` on failure — it uses a bare `finally` that only restores `tf.path`, not removes the `.tmp`. This means a failed write leaves a `.tmp` orphan, which could cause `read_tf` to ignore it silently. No test exposes this.

**Acceptance Criteria:**
- [ ] Add `test_atomic_write_exception_leaves_original_intact` that: writes a valid file, then patches `write_tf` to raise `OSError` during the second `atomic_write_tf` call, and asserts the original file still contains the old data.
- [ ] Add an assertion that either the `.tmp` file is absent (cleaned up) or that `read_tf` of the original path succeeds with old data regardless.

---

### BH22-056: No test for `do_sync` "local story absent from GitHub" warning path

**Severity:** LOW
**Category:** `test/missing`
**Location:** `tests/test_kanban.py:418-487`

**Problem:** `do_sync()` emits a `WARNING: local story {ID} not found on GitHub` entry in the changes list when a local tracking file has no corresponding GitHub issue. This is the last loop in the function (lines 375-380 in kanban.py). No test covers it. A regression that silently drops this warning would go undetected.

**Acceptance Criteria:**
- [ ] Add `test_sync_warns_about_local_story_absent_from_github` that: writes a local tracking file for `US-0099`, calls `do_sync` with an empty issues list, and asserts the returned changes contain `"WARNING"` and `"US-0099"`.

---

### BH22-057: `find_story` tests missing case-sensitivity and prefix-collision coverage

**Severity:** LOW
**Category:** `test/missing`
**Location:** `tests/test_kanban.py:234-272`

**Problem:** `find_story` uppercases both the search ID and the stem (`prefix = story_id.upper()`), making the match case-insensitive. No test verifies this. Additionally, the guard `stem.startswith(prefix + "-")` is designed to prevent `US-0042` from matching `US-00420`. There is no test for the false-positive scenario (searching for `US-0042` with a file `US-00420-something.md` present alongside `US-0042-thing.md`). Without this test, a regression that drops the `+ "-"` guard would be invisible.

**Acceptance Criteria:**
- [ ] Add `test_find_story_case_insensitive` that writes a file named `us-0010-lowercase.md` (lowercase prefix) and searches for `"US-0010"`, asserting it is found.
- [ ] Add `test_find_story_no_prefix_collision` that creates both `US-0042-real.md` and `US-00420-other.md` in the same stories dir, searches for `"US-0042"`, and asserts only `US-0042` is returned (not `US-00420`).

---

### BH22-058: `test_transition_updates_local_and_github` verifies label names via string conversion of `call_args_list`

**Severity:** LOW
**Category:** `test/thin`
**Location:** `tests/test_kanban.py:294-307`

**Problem:** Lines 305-307 use `str(mock.call_args_list)` to check that `"kanban:todo"` and `"kanban:design"` both appear. String-conversion of a mock's call list is brittle: if argument ordering changes, or if the labels appear in a different call (e.g., a retry), the assertion still passes. More critically, it does not verify that `--remove-label kanban:todo` and `--add-label kanban:design` appeared in the SAME call (as the production code requires). A regression that makes two separate calls each with one label would satisfy this check.

**Acceptance Criteria:**
- [ ] Refactor to check individual calls by index: `mock.call_args_list[0]` should contain both `"--remove-label"` and `"kanban:todo"`, and `"--add-label"` and `"kanban:design"`.
- [ ] Alternatively, use `mock.assert_called_once_with(["issue", "edit", "42", "--remove-label", "kanban:todo", "--add-label", "kanban:design"])` to pin the exact call signature.

---

### BH22-059: `test_main_status_no_config` is coverage theater

**Severity:** LOW
**Category:** `test/thin`
**Location:** `tests/test_kanban.py:547-558`

**Problem:** This test patches `sys.argv` and calls `kanban.main()`, expecting a `SystemExit(1)` because `load_config()` finds no `sprint-config/`. It tests the CLI plumbing, but the assertion `ctx.exception.code == 1` is satisfied by the very first line of `main()` that calls `load_config()`. This test validates `load_config` raises `ConfigError` (already covered by `TestLoadConfigRaisesConfigError` in `test_verify_fixes.py`), not anything kanban-specific. The docstring claim "Exits 1 because load_config() fails" is explicit that this is purely an infrastructure test.

This is not harmful, but it provides no additional confidence about kanban logic. If the only reason to keep it is meta-coverage, it should be labelled as such or promoted to a real integration test that exercises a kanban subcommand with a real config.

**Acceptance Criteria:**
- [ ] Either: extend this test to use a real temp `sprint-config/` directory and assert that `do_status` output appears in stdout, OR
- [ ] Rename the class to `TestCLIInfrastructure` and document explicitly that it is a plumbing test, not a kanban-logic test, so future audits don't flag it.

---

### BH22-060: No test for `frontmatter_value` with an empty-string value field

**Severity:** MEDIUM
**Category:** `test/missing`
**Location:** `tests/test_kanban.py` (all `read_tf`/`write_tf` round-trip tests)

**Problem:** `frontmatter_value()` uses the regex `^{key}:\s*(.+)` with `re.MULTILINE`. The `.+` requires at least one character — it will NOT match `implementer: ` (empty value, possibly trailing whitespace). When an empty string is written by `write_tf` (which does NOT call `_yaml_safe` on `implementer`, `reviewer`, `status`, `pr_number`, `issue_number`), it writes `implementer: ` (empty value). `frontmatter_value` returns `None`, `read_tf` calls `or ""` to get an empty string, and the round-trip appears to work. However, if any of these empty fields contain a whitespace-only value (e.g. `"  "`), `_yaml_safe` would return `"  "` unchanged (no quoting for spaces alone), and the `.+` regex would match `"  "` then strip it to `""` — a silent data loss that collapses whitespace-only values to empty string. The existing round-trip tests use non-empty strings and never exercise this. Since these are real-world tracking file fields, the gap is latent.

**Acceptance Criteria:**
- [ ] Add `test_round_trip_empty_fields` in `TestTrackingFileIO` that writes a `TF` with `implementer=""`, `reviewer=""`, `branch=""`, `pr_number=""` and asserts all read back as `""`.
- [ ] Add `test_round_trip_whitespace_only_value` that writes a `TF` with `title="  "` (whitespace) and asserts the round-trip either preserves `"  "` or documents the known-lossy behaviour so it cannot silently regress.

---

### BH22-061: `test_sprint_runtime.py` — `TestCheckCI.test_failing_run` does not verify log-fetch call args

**Severity:** LOW
**Category:** `test/thin`
**Location:** `tests/test_sprint_runtime.py:63-72`

**Problem:** `test_failing_run` patches both `check_status.gh_json` (returns a failing run) and `check_status.gh` (returns a log string). It asserts `"1 failing"` is in the report and `len(actions) > 0`. The `mock_gh` (the log-fetcher) is never inspected — the test doesn't verify that the log-fetch call included the run ID (`42`) or used the correct subcommand. The mock is set up and called but its arguments are ignored, which violates the `MonitoredMock` contract and should emit a `UserWarning` on test exit.

**Acceptance Criteria:**
- [ ] Add `self.assertIn("42", str(mock_gh.call_args))` to verify the failing run's database ID was used in the log fetch.
- [ ] Verify no `UserWarning` is emitted from `patch_gh` for this test (currently `patch` is used directly, not `patch_gh`, so MonitoredMock isn't active — but the principle applies).

---

### BH22-062: `test_property_parsing.py` — `TestYamlSafe.test_empty_preserves_empty` has a misleading name and incorrect invariant

**Severity:** LOW
**Category:** `test/bogus`
**Location:** `tests/test_property_parsing.py:183-188`

**Problem:** The test is named `test_empty_preserves_empty` but it uses `st.text(min_size=1)` — it never actually tests empty input. The docstring says "Non-empty input produces non-empty output", which is accurate for what the test does, but the name implies the empty-string case is covered. The actual empty-string case is tested by `test_empty_string_passthrough` (line 190-192). The mismatch creates confusion and a false sense of coverage for the empty-input path in this property-based test.

**Acceptance Criteria:**
- [ ] Rename `test_empty_preserves_empty` to `test_nonempty_input_produces_nonempty_output` to match what the test actually asserts.
- [ ] Confirm `test_empty_string_passthrough` is sufficient for the empty-input path (it is — `_yaml_safe("")` returns `""` immediately).

---

## Coverage Map

| Area | Tests | Gaps |
|------|-------|------|
| `validate_transition` | Full (legal, illegal, same-state, unknown) | None |
| `check_preconditions` | Good (all target states with both pass/fail) | None |
| `atomic_write_tf` | Happy path only | Exception-safety path (BH22-055) |
| `lock_story` / `lock_sprint` | Acquire/release cycle | No contention test (acceptable) |
| `find_story` | Basic match, prefix-with-slug, missing | Case insensitivity, near-ID collision (BH22-057) |
| `do_transition` | Update + revert + close-issue | Label call structure brittle (BH22-058), revert check thin (BH22-054) |
| `do_assign` | Implementer, both, revert | Reviewer-only (BH22-053), body-update verification (BH22-051), mock satisfaction pattern (BH22-052) |
| `do_sync` | Accept legal, reject illegal, create new | Closed-issue override (BH22-050), local-absent warning (BH22-056) |
| `do_status` | Three-state board render | Empty sprint dir (covered by production code returning early) |
| `kanban_from_labels` | Indirectly via do_sync | Closed-issue path not reachable from tests (BH22-050) |
| `frontmatter_value` | Indirectly via round-trip | Empty/whitespace values (BH22-060) |
