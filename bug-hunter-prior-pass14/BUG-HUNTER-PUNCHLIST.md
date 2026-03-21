# Bug Hunter Punchlist — Pass 14
> Generated: 2026-03-16 | Project: giles | Baseline: 677 pass, 0 fail, 0 skip (9.15s)

## Summary
| Severity | Open | Resolved | Deferred |
|----------|------|----------|----------|
| CRITICAL | 0 | 1 | 0 |
| HIGH | 0 | 5 | 0 |
| MEDIUM | 0 | 6 | 0 |
| LOW | 0 | 3 | 0 |
| **Total** | **0** | **15** | **0** |

## Patterns

### Pattern: PAT-001: Golden replay discards recorded state depth
**Instances:** BH-003, BH-004
**Root Cause:** `golden_replay.py` records full GitHub state (label colors, issue bodies, milestone descriptions) but comparison methods only check names/titles. The rich data is captured but never verified.
**Systemic Fix:** Add content-level comparison to `assert_labels_match`, `assert_issues_match`, and `assert_milestones_match` — or at minimum compare a hash/fingerprint of the full recorded objects.
**Detection Rule:** `grep -c "\.get\(\"title\"" tests/golden_replay.py` — should be paired with content/body/color checks.

### Pattern: PAT-002: main() coverage theater
**Instances:** BH-005, BH-006
**Root Cause:** The `TestEveryScriptMainCovered` gate enforces that `module.main()` appears in test code, but doesn't distinguish between testing argparse error paths and testing actual functionality. This created a perverse incentive: 10 scripts got minimal error-path tests to satisfy the gate.
**Systemic Fix:** The gate test should require at least one test per script that calls `main()` with valid inputs and asserts on output/side-effects, not just exit codes.
**Detection Rule:** For each script in the gate, count tests that call `main()` with VALID args — should be >= 1.

### Pattern: PAT-003: Structural assertions where computed values are knowable
**Instances:** BH-008, BH-009
**Root Cause:** Tests check `assertIn(key, dict)` or `assertIn(substring, output)` when the test inputs are deterministic and exact values could be asserted. This lets silent value corruption pass undetected.
**Systemic Fix:** For tests with deterministic inputs, use `assertEqual` for known output values; reserve `assertIn` for variable-content checks.
**Detection Rule:** `grep -c "assertIn\|assertGreaterEqual" tests/test_lifecycle.py tests/test_verify_fixes.py` — high counts suggest rubber-stamp assertions.

---

## Items

### BH-001: release_gate.py — Local tag orphaned on push failure
**Severity:** CRITICAL
**Category:** `bug/logic`
**Location:** `skills/sprint-release/scripts/release_gate.py:581-583`
**Status:** ✅ RESOLVED

**Problem:** When `git push origin main v{new_ver}` fails at line 581, only `_rollback_commit()` is called. The local tag created at line 566-573 is NOT deleted because `_rollback_tag()` is defined at line 587 — after the push step — and isn't available in the push-failure code path. Next release attempt fails with "tag already exists." P12-001 fixed rollback for the GitHub Release failure path but missed the push failure path.

**Evidence:** `_rollback_tag()` defined at line 587, called only at line 636. Line 582 calls only `_rollback_commit()`. Existing test `test_push_tag_failure_resets_commit` (line 907) verifies `git reset --hard` but does NOT verify `git tag -d`.

**Acceptance Criteria:**
- [ ] When push fails after tag creation, both commit AND local tag are rolled back
- [ ] `_rollback_tag()` is defined before the push step (or a separate tag cleanup is called)
- [ ] Test asserts `git tag -d v{ver}` appears in subprocess calls after push failure
- [ ] Existing test `test_push_tag_failure_resets_commit` is extended to verify tag deletion

**Validation Command:**
```bash
python -m pytest tests/test_release_gate.py -k "push_tag_failure" -v && \
  grep -A 20 "def test_push_tag_failure" tests/test_release_gate.py | grep -c "tag.*-d\|delete.*tag"
```

---

### BH-002: FakeGitHub milestone counters never updated
**Severity:** HIGH
**Category:** `test/mock-abuse`
**Location:** `tests/fake_github.py:394-395,494-535,628-643`
**Status:** ✅ RESOLVED

**Problem:** When milestones are created, `open_issues` and `closed_issues` are initialized to 0. When issues are created with a milestone or closed, these counters are never updated. Production code (`check_status.py:191-192`) reads these counters for sprint progress. Any test using FakeGitHub to verify milestone progress sees 0% completion regardless of activity.

**Evidence:** Neither `_issue_create` nor `_issue_close` updates milestone counters. `check_milestone()` uses `ms.get("open_issues", 0)` and `ms.get("closed_issues", 0)` which are always 0 in FakeGitHub.

**Acceptance Criteria:**
- [ ] `_issue_create` increments `open_issues` on the assigned milestone
- [ ] `_issue_close` decrements `open_issues` and increments `closed_issues`
- [ ] Test exists: create milestone, create 3 issues for it, close 1, verify counters are 3 open + 0 closed → 2 open + 1 closed
- [ ] `test_check_milestone` in test_sprint_runtime.py verifies non-zero progress percentages

**Validation Command:**
```bash
python -m pytest tests/test_fakegithub_fidelity.py tests/test_sprint_runtime.py -k "milestone" -v && echo "PASS"
```

---

### BH-003: Golden replay assert_labels_match ignores colors and descriptions
**Severity:** HIGH
**Category:** `test/shallow`
**Location:** `tests/golden_replay.py:46-70`
**Status:** ✅ RESOLVED
**Pattern:** PAT-001

**Problem:** `assert_labels_match` extracts label names into sets and compares them. The recorded snapshot stores full label data including colors and descriptions, but the comparison discards all of it. A regression that changes every label color from correct to `"000000"` passes the golden test.

**Evidence:** Line 53: `recorded_labels = set(gh_state.get("labels", {}).keys())` — only names. Same for `assert_issues_match` (titles only) and `assert_milestones_match` (titles only).

**Acceptance Criteria:**
- [ ] `assert_labels_match` compares at least color + name (not just name)
- [ ] `assert_issues_match` compares at least title + label set (not just title)
- [ ] `assert_milestones_match` compares at least title + description
- [ ] Test exists proving a color-change regression is caught by golden replay

**Validation Command:**
```bash
grep -c "color\|description\|body\|labels" tests/golden_replay.py | head -1
# Should show matches in the assert_* methods, not just in other code
```

---

### BH-004: Golden Phase 5 (CI) snapshot is recorded but never replayed
**Severity:** HIGH
**Category:** `test/bogus`
**Location:** `tests/test_golden_run.py:192-203`
**Status:** ✅ RESOLVED
**Pattern:** PAT-001

**Problem:** Phase 5 records a "05-setup-ci" snapshot when in RECORD_MODE but never calls `_check_or_record` during replay. The generated CI YAML is only checked by two `assertIn("cargo test", ...)` substring checks. A regression that changes action versions, removes the permissions block, or corrupts YAML structure goes undetected.

**Evidence:** Lines 192-203: `if RECORD_MODE:` records the snapshot. No corresponding replay comparison call. Compare with Phases 1-4 which all have `self._check_or_record(...)` calls.

**Acceptance Criteria:**
- [ ] Phase 5 CI snapshot is compared during replay (same pattern as Phases 1-4)
- [ ] OR: Phase 5 assertions are strengthened beyond 2 substring checks (validate YAML structure, action versions, permissions block)

**Validation Command:**
```bash
grep -c "05-setup-ci\|check_or_record.*05" tests/test_golden_run.py
# Should be >= 1 (currently 0 for replay, only 1 for record)
```

---

### BH-005: 10 main() tests are pure argparse-error coverage — no happy paths
**Severity:** HIGH
**Category:** `test/shallow`
**Location:** `tests/test_verify_fixes.py:857-1121`
**Status:** ✅ RESOLVED
**Pattern:** PAT-002

**Problem:** Ten `main()` test classes for 7 scripts follow an identical template: test `--help exits 0`, `missing config exits 1`, `bad args exits 2`. None test the happy path where `main()` actually does real work. The `TestEveryScriptMainCovered` gate is satisfied by these error-only tests, creating the illusion of coverage.

**Evidence:** TestTeamVoicesMain: 1 test (error). TestManageEpicsMain: 1 test (error). TestManageSagasMain: 1 test (error). TestTestCoverageMain: 1 test (error). TestSetupCiMain: 2 tests (error + help). TestSprintInitMain: 2 tests (error + help). TestTraceabilityMain: 1 test (error). You could replace the body of each script's `main()` with `sys.exit(0)` for help / `sys.exit(1)` for errors and all tests pass.

**Acceptance Criteria:**
- [ ] At least 4 of the 7 affected scripts have a happy-path main() test that calls main() with valid inputs and asserts on output or side effects
- [ ] Priority targets: setup_ci (verify YAML output), sprint_init (verify config generated), team_voices (verify voice extraction output), traceability (verify report output)

**Validation Command:**
```bash
# Count tests that call main() without assertRaises(SystemExit)
grep -c "\.main()" tests/test_verify_fixes.py && \
  grep -c "assertRaises.*SystemExit" tests/test_verify_fixes.py
# Second number should be less than first (some main() calls should be happy-path)
```

---

### BH-006: do_release tests verify call sequence via index, not behavior
**Severity:** HIGH
**Category:** `test/mock-abuse`
**Location:** `tests/test_release_gate.py:641-714`
**Status:** ✅ RESOLVED

**Problem:** `TestDoRelease` (7 tests, ~300 lines) patches 5 functions and verifies subprocess call sequences by index position: `run_cmds[0]` must be git status, `run_cmds[2]` must be git add, etc. This is fragile (any reordering breaks) and incomplete (index [3] is skipped, meaning the commit step has no assertion). The companion `TestDoReleaseFakeGH` (1 test) tests actual state changes — but the ratio is 7:1 in favor of the fragile mock tests.

**Evidence:** Lines 678-692 assert on specific indices. Gap at index [3] (commit) means the most important step is unverified. Adding a diagnostic git command shifts all indices.

**Acceptance Criteria:**
- [ ] At least 2 additional `TestDoReleaseFakeGH` tests covering: (a) version bump is written, (b) release notes contain correct sections, (c) milestone is closed
- [ ] The index-based assertions in `test_happy_path` are replaced with command-matching assertions (search for the command regardless of position)
- [ ] The commit step (index [3]) is explicitly verified

**Validation Command:**
```bash
python -m pytest tests/test_release_gate.py -k "FakeGH" -v && \
  grep -c "class TestDoReleaseFakeGH" tests/test_release_gate.py
```

---

### BH-007: _yaml_safe doesn't escape backslashes — roundtrip test is coupled to the bug
**Severity:** MEDIUM
**Category:** `bug/logic`
**Location:** `skills/sprint-run/scripts/sync_tracking.py:179-200`
**Status:** ✅ RESOLVED

**Problem:** `_yaml_safe` escapes double-quotes (`value.replace('"', '\\"')`) but does NOT escape backslashes. A value containing a literal backslash (e.g., a Windows path `C:\Users\name`) would be quoted as `"C:\Users\name"` — a YAML parser would interpret `\U` as a unicode escape, producing wrong data. The property test's roundtrip verifier uses the same naive unquoting logic, so it's coupled to the bug: fixing the bug would break the test.

**Evidence:** Line 198: `escaped = value.replace('"', '\\"')` — no `value.replace('\\', '\\\\')` precedes it.

**Acceptance Criteria:**
- [ ] `_yaml_safe` escapes backslashes before escaping quotes: `value.replace('\\', '\\\\').replace('"', '\\"')`
- [ ] The property test roundtrip uses the real `read_tf` to verify (not hand-rolled unquoting)
- [ ] Test exists: `_yaml_safe('C:\\Users')` produces `"C:\\\\Users"`, and `read_tf` recovers `C:\Users`

**Validation Command:**
```bash
python -c "
import sys; sys.path.insert(0, 'skills/sprint-run/scripts')
from sync_tracking import _yaml_safe
assert '\\\\\\\\' in _yaml_safe('C:\\\\Users'), 'Backslash not escaped'
print('PASS')
"
```

---

### BH-008: setup_ci.py _yaml_safe_command silently truncates multiline commands
**Severity:** MEDIUM
**Category:** `bug/logic`
**Location:** `skills/sprint-setup/scripts/setup_ci.py:100-102`
**Status:** ✅ RESOLVED
**Pattern:** PAT-003

**Problem:** If a TOML multiline string produces `check_commands` with embedded newlines, `_yaml_safe_command` silently keeps only the first line. No warning is emitted. The user gets a CI workflow with a truncated command.

**Evidence:** Lines 100-102: `command = command.split("\n")[0].split("\r")[0]` — no `print(..., file=sys.stderr)`.

**Acceptance Criteria:**
- [ ] `_yaml_safe_command` emits a warning to stderr when truncating
- [ ] Test exists: command with `\n` produces warning on stderr and truncated output
- [ ] OR: multiline commands are converted to YAML `run: |` blocks instead of truncated

**Validation Command:**
```bash
python -m pytest tests/test_pipeline_scripts.py -k "yaml_safe" -v && echo "PASS"
```

---

### BH-009: populate_issues.build_milestone_title_map silently overwrites on duplicate sprints
**Severity:** MEDIUM
**Category:** `bug/logic`
**Location:** `skills/sprint-setup/scripts/populate_issues.py:329-332`
**Status:** ✅ RESOLVED
**Pattern:** PAT-003

**Problem:** If two milestone files both contain `### Sprint 1:` sections, `result[int(n)] = title` silently overwrites the first title with the second. Issues created for Sprint 1 get assigned to the wrong milestone.

**Evidence:** Line 332: `result[int(n)] = title` — no duplicate check. No warning.

**Acceptance Criteria:**
- [ ] `build_milestone_title_map` warns to stderr when overwriting a sprint→title mapping
- [ ] Test exists: two files with `### Sprint 1:` headers produce a warning
- [ ] OR: the function raises ValueError on duplicate sprint numbers

**Validation Command:**
```bash
python -m pytest tests/test_pipeline_scripts.py -k "milestone_title_map" -v && echo "PASS"
```

---

### BH-010: BH-001 concatenated JSON test reimplements production code instead of calling it
**Severity:** MEDIUM
**Category:** `test/bogus`
**Location:** `tests/test_bugfix_regression.py:304-324`
**Status:** ✅ RESOLVED

**Problem:** `test_concatenated_json_arrays` reimplements the `json.JSONDecoder().raw_decode` loop from `gh_json()` in the test body, then asserts on the reimplementation. It never calls the actual `gh_json()` function. If the concatenation handling in `gh_json()` were broken or removed, this test would still pass.

**Evidence:** The test body contains its own decode loop. The companion test `test_normal_json_still_works` calls `gh_json` via FakeGitHub but only with a single array (not concatenated).

**Acceptance Criteria:**
- [ ] Test calls actual `gh_json()` (via FakeGitHub or mock subprocess) with concatenated JSON output
- [ ] Remove the reimplemented decode loop from the test
- [ ] Test verifies that `gh_json` returns a merged list from concatenated arrays

**Validation Command:**
```bash
python -m pytest tests/test_bugfix_regression.py -k "concatenated" -v && \
  grep -c "raw_decode" tests/test_bugfix_regression.py
# raw_decode count should be 0 (production code only, not in test)
```

---

### BH-011: FakeGitHub strict-mode warnings not leveraged in integration tests
**Severity:** MEDIUM
**Category:** `test/shallow`
**Location:** `tests/test_sprint_runtime.py`, `tests/test_lifecycle.py`, `tests/test_golden_run.py`
**Status:** ✅ RESOLVED

**Problem:** FakeGitHub has strict mode that warns when tests use flags it doesn't evaluate. The mechanism is tested in isolation (`test_bugfix_regression.py`) but no integration test asserts `fake._strict_warnings == []` after running. A production code change that passes a new flag FakeGitHub silently ignores would go undetected.

**Evidence:** `grep -r "_strict_warnings" tests/test_sprint_runtime.py tests/test_lifecycle.py tests/test_golden_run.py tests/test_hexwise_setup.py` returns 0 matches.

**Acceptance Criteria:**
- [ ] At least 2 integration test classes (test_lifecycle.py, test_hexwise_setup.py) assert `self.fake_gh._strict_warnings == []` in tearDown or at test end
- [ ] When a production script passes a flag FakeGitHub can't evaluate, the integration test fails

**Validation Command:**
```bash
grep -c "_strict_warnings" tests/test_lifecycle.py tests/test_hexwise_setup.py
# Should be >= 1 per file
```

---

### BH-012: Property test for parse_simple_toml accepts any ValueError as valid
**Severity:** MEDIUM
**Category:** `test/bogus`
**Location:** `tests/test_property_parsing.py:287-295`
**Status:** ✅ RESOLVED

**Problem:** `test_returns_dict_or_raises_valueerror` accepts ANY ValueError as valid behavior. The test generates random text (not valid TOML), so it exclusively exercises the "garbage in" path. A regression that raises ValueError on valid TOML input would be silently accepted.

**Evidence:** Lines 293-294: `except ValueError: pass`. You could replace `parse_simple_toml` with `raise ValueError("broken")` and this test passes 100% of the time.

**Acceptance Criteria:**
- [ ] The test should generate VALID TOML strings (via the `_toml_line` helper) AND assert they parse without ValueError
- [ ] The random-text path should remain but be a separate test method
- [ ] Separate test: `test_valid_toml_never_raises_valueerror` generates well-formed TOML and asserts it parses

**Validation Command:**
```bash
python -m pytest tests/test_property_parsing.py -k "toml" -v && echo "PASS"
```

---

### BH-013: No pytest-cov — coverage blind spots can't be measured
**Severity:** LOW
**Category:** `test/missing`
**Location:** Project-wide
**Status:** ✅ RESOLVED

**Problem:** `pytest-cov` is not installed. No `.coveragerc`. No coverage reporting. The project has 677 tests but no way to know which lines of production code they exercise. The `_KNOWN_UNTESTED` gate is a manual approximation that only checks `main()`, not line coverage.

**Acceptance Criteria:**
- [ ] `pip install pytest-cov` added to dev setup
- [ ] `python -m pytest tests/ --cov=scripts --cov-report=term-missing` runs successfully
- [ ] Coverage report shows which modules are below 80% line coverage

**Validation Command:**
```bash
python -m pytest tests/ --cov=scripts --cov-report=term-missing 2>&1 | tail -30
```

---

### BH-014: validate_config.load_config() parses TOML twice (TOCTOU)
**Severity:** LOW
**Category:** `design/duplication`
**Location:** `scripts/validate_config.py:601,610`
**Status:** ✅ RESOLVED

**Problem:** `validate_project()` at line 437 parses the TOML file. Then `load_config()` at line 610 parses it again. Architecturally unclean: two reads of the same file, and a theoretical TOCTOU if the file changes between reads.

**Acceptance Criteria:**
- [ ] `load_config()` reuses the config dict from `validate_project()` instead of re-parsing
- [ ] OR: `validate_project()` accepts an optional pre-parsed dict to avoid redundant I/O
- [ ] Tests still pass after refactoring

**Validation Command:**
```bash
python -m pytest tests/ -v && echo "PASS"
```

---

### BH-015: 2 unreferenced anchor definitions
**Severity:** LOW
**Category:** `doc/drift`
**Location:** `scripts/validate_anchors.py` output
**Status:** ✅ RESOLVED

**Problem:** Two anchor comments exist in source but are not referenced in CLAUDE.md or CHEATSHEET.md:
- `§populate_issues._most_common_sprint` in populate_issues.py
- `§update_burndown.build_rows` in update_burndown.py

These were added as part of prior-pass fixes but never wired into the documentation index.

**Acceptance Criteria:**
- [ ] Both anchors are referenced in CLAUDE.md's function table or CHEATSHEET.md
- [ ] OR: anchors are removed if the functions don't need documentation-level visibility
- [ ] `python scripts/validate_anchors.py` reports 0 unreferenced anchors

**Validation Command:**
```bash
python scripts/validate_anchors.py 2>&1 | grep "unreferenced"
# Should report "0 anchor(s) defined but unreferenced"
```
