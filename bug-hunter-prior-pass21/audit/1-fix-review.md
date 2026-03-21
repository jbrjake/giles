# Pass 14 Adversarial Fix Review

Reviewed all 17 files modified across 10 commits in pass 14.
Methodology: read every diff, examined full context of changed code,
traced edge cases through escape/unescape sequences, checked test coverage.

---

## Findings

### Finding: BH-014 — validate_project skips section/key validation when _config is provided
**File:** scripts/validate_config.py:439-466
**Issue:** The entire required-sections and required-keys validation (lines 445-466) is inside the `if _config is None` block. When `load_config()` calls `validate_project(config_dir, _config=config)`, `_config` is not `None`, so lines 445-466 are never executed. This means the most common code path (every script calling `load_config()`) no longer validates that `[project]`, `[paths]`, `[ci]` sections exist, or that required keys like `project.name`, `ci.check_commands` are present.
**Evidence:**
```python
config: dict = _config if _config is not None else {}
if _config is None and toml_path.is_file():   # <-- False when called from load_config
    ...
    # Required sections   <-- SKIPPED
    for section in _REQUIRED_TOML_SECTIONS:
        ...
    # Required keys       <-- SKIPPED
    for key_path in _REQUIRED_TOML_KEYS:
        ...
```
Additionally, when TOML parsing fails in `load_config()` (line 612), `config` remains `{}`. The `except` block's comment says "validate_project will report the parse error" — but it won't, because the parse-error path is also inside the `if _config is None` block. A malformed TOML file would pass validation silently through `load_config()`, then crash later with a confusing KeyError.
**Severity:** CRITICAL

### Finding: BH-011 — strict warnings are printed but never asserted
**File:** tests/test_lifecycle.py:67-70, tests/test_hexwise_setup.py:330-333
**Issue:** The BH-011 fix adds code to print `_strict_warnings` to stderr in `tearDown()`, but never calls `self.fail()` or any assertion. If FakeGitHub silently ignores a flag, the test still passes. The fix is cosmetic — warnings go to stderr where they're easily missed in CI output.
**Evidence:**
```python
def tearDown(self):
    if hasattr(self, 'fake_gh') and self.fake_gh._strict_warnings:
        print(f"FakeGitHub strict warnings: {self.fake_gh._strict_warnings}",
              file=sys.stderr)
    # No self.fail() or assertion — test passes regardless
```
**Severity:** MEDIUM

### Finding: BH-006 — test claims to verify release notes sections but doesn't
**File:** tests/test_release_gate.py:1253-1276
**Issue:** `test_release_notes_contain_correct_sections` provides commits with feat, fix, and breaking change types, but never inspects the actual release notes content. It only checks that a release was created and the tag is correct. The docstring says "Verify release notes have correct sections for commit types" but the test body does not verify any sections, headings, or commit categorization in the notes.
**Evidence:**
```python
# What the test checks:
self.assertTrue(len(self.fake.releases) >= 1)
self.assertEqual(self.fake.releases[0]["tag_name"], "v2.0.0")
# What it claims to check but doesn't:
# - "Breaking Changes" section exists
# - "Features" section contains "new dashboard"
# - "Bug Fixes" section contains "login crash"
```
**Severity:** MEDIUM

### Finding: BH-002 — milestone counters not updated on issue_edit milestone reassignment
**File:** tests/fake_github.py:628-631
**Issue:** When `_issue_edit` changes an issue's milestone via `--milestone`, the old milestone's `open_issues` is not decremented and the new milestone's `open_issues` is not incremented. Only `_issue_create` and `_issue_close` update counters. If a test scenario moves an issue between milestones, the counters will be wrong.
**Evidence:**
```python
def _issue_edit(self, args):
    ...
    if "milestone" in flags:
        ms_title = flags["milestone"][0]
        issue["milestone"] = {"title": ms_title} if ms_title else None
        # No counter update here
```
**Severity:** MEDIUM

### Finding: BH-001 — _rollback_tag unconditionally tries to delete remote tag when push hasn't happened
**File:** skills/sprint-release/scripts/release_gate.py:576-592
**Issue:** When the push fails (line 600), `_rollback_tag()` is called. This function always attempts `git push --delete origin v{new_ver}` (line 585-587), even though the tag was never pushed to the remote (the push just failed). This produces a spurious warning message to stderr: "Warning: failed to delete remote tag...". While not a data-loss bug (it's guarded), it produces confusing output for the user.
**Evidence:** The `_rollback_tag` function does not check `pushed_to_remote` before attempting remote deletion. The variable exists (line 604) but is only set to `True` after a successful push, which hasn't happened yet when rollback fires at line 601.
**Severity:** LOW

### Finding: BH-003 — milestone description comparison is asymmetric and misaligns on count differences
**File:** tests/golden_replay.py:113-122
**Issue:** Two problems: (1) The `zip(recorded, current)` on line 114 silently truncates to the shorter list when milestone counts differ. If the recording has 3 milestones and current has 4, the 4th is never compared. (2) The check `if rec_desc and rec_desc != cur_desc` on line 119 is asymmetric — it only detects changes when the recorded description is non-empty. If the recording had an empty description but current has a non-empty one, no mismatch is reported.
**Evidence:**
```python
for rec_ms, cur_ms in zip(recorded, current):  # truncates to shorter
    ...
    if rec_desc and rec_desc != cur_desc:  # skips when rec_desc is ""
```
**Severity:** LOW

### Finding: BH-009 — overwrite warning has no test coverage
**File:** skills/sprint-setup/scripts/populate_issues.py:331-337
**Issue:** The BH-009 fix adds warning messages when a sprint number is mapped to multiple milestone titles, but no test exercises this warning path. A grep for the warning text across all test files finds zero matches. The fix could be deleted without any test failing.
**Evidence:** `grep -r "Warning.*Sprint.*mapped\|overwrite.*milestone\|build_milestone_title_map.*overwrite" tests/` returns no results.
**Severity:** LOW

---

## Files with no issues found

- **skills/sprint-run/scripts/sync_tracking.py (BH-007):** Backslash escaping fix is correct. The escape order (backslashes before quotes in `_yaml_safe`, quotes before backslashes in `read_tf`) is the correct approach. Traced multiple edge cases including `\`, `\"`, `\\`, and boolean keywords through the roundtrip — all produce correct results. Tests are thorough including combo cases.
- **tests/test_sprint_runtime.py (BH-007):** Tests cover backslash, backslash+quote combo, and boolean keyword roundtrips. Good edge case coverage.
- **tests/test_property_parsing.py (BH-012):** Split between random-text fuzz test and valid-TOML structural test is correct. The new `test_valid_toml_never_raises` properly generates only well-formed TOML and asserts parsing never raises. The `_YAML_BOOL_KEYWORDS` addition and backslash check in `test_dangerous_chars_get_quoted` correctly mirrors the production code.
- **tests/test_golden_run.py (BH-004):** Fix correctly moves CI file writing outside the `RECORD_MODE` branch and adds a replay assertion. The `_check_or_record` call for `05-setup-ci` will now actually validate file content in replay mode.
- **tests/test_bugfix_regression.py (BH-010):** The rewrite correctly tests the actual `gh_json` function through a mock subprocess instead of reimplementing the JSON decode loop. This validates the real code path.
- **tests/test_fakegithub_fidelity.py (BH-002):** Tests cover create-increments-open, close-moves-counter, full lifecycle, and no-milestone-no-update scenarios. Good coverage.
- **skills/sprint-setup/scripts/setup_ci.py (BH-008):** Truncation warning correctly logs the first line and original line count to stderr. Clean implementation.
- **CLAUDE.md (BH-015):** Anchor reference additions are correct (`_most_common_sprint`, `build_rows`).

---

## Summary

| Severity | Count | Key issue |
|----------|-------|-----------|
| CRITICAL | 1     | BH-014 skips all TOML section/key validation through load_config() |
| MEDIUM   | 3     | BH-011 warnings never fail tests; BH-006 test doesn't verify what it claims; BH-002 counters miss edit path |
| LOW      | 3     | Spurious remote tag delete warning; asymmetric milestone desc check; no test for overwrite warning |

The CRITICAL finding (BH-014) is a regression that defeats the purpose of config validation for every script that uses `load_config()`. The required-sections and required-keys checks (lines 445-466 of validate_config.py) are entirely inside the `if _config is None` branch, which is never taken when called from `load_config()`. The fix needs to move those checks outside the conditional, or add an `else` branch that validates the pre-parsed config.
