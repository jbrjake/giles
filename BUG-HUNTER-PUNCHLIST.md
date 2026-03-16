# Bug Hunter Punchlist — Pass 17

> Generated: 2026-03-16 | Project: giles | Baseline: 739 pass, 0 fail, 0 skip | Coverage: 85%
> Method: Mutation testing (40 mutations across 12 files) + cross-module flow tracing + assertion quality audit

## Summary

| Severity | Open | Resolved | Deferred |
|----------|------|----------|----------|
| CRITICAL | 1    | 0        | 0        |
| HIGH     | 5    | 0        | 0        |
| MEDIUM   | 10   | 0        | 0        |
| LOW      | 0    | 0        | 0        |

## Patterns

## Pattern: PAT-001: Mutation survivors — tests check structure not values
**Instances:** BH-001, BH-002, BH-005, BH-006, BH-007
**Root Cause:** Tests assert presence/length/type but not computed values
**Systemic Fix:** For each surviving mutation, add an assertion that checks the exact value the mutation would corrupt
**Detection Rule:** Run mutation testing; any survivor indicates a test gap

## Pattern: PAT-002: FakeGitHub diverges from real API in undetected ways
**Instances:** BH-009, BH-010, BH-011
**Root Cause:** FakeGitHub was built incrementally; no systematic comparison against real API behavior
**Systemic Fix:** Add fidelity tests that compare FakeGitHub output format against documented GitHub API schemas
**Detection Rule:** `grep -n 'self\._ok\|self\._fail' tests/fake_github.py` and verify each response matches GitHub API format

## Pattern: PAT-003: Existence assertions mask value bugs
**Instances:** BH-012, BH-013
**Root Cause:** Tests written to "make CI green" rather than to catch regressions
**Systemic Fix:** Replace assertIsNotNone with assertEqual where expected value is knowable
**Detection Rule:** `grep -rn 'assertIsNotNone\|assertTrue(len' tests/`

## Items

### BH-001: Leading zeros in sprint headings cause silent milestone lookup failure
**Severity:** CRITICAL
**Category:** `bug/logic`
**Location:** `scripts/validate_config.py:892` (find_milestone), `skills/sprint-setup/scripts/bootstrap_github.py:256` (create_milestones_on_github)
**Status:** 🔴 OPEN
**Pattern:** —

**Problem:** `### Sprint 07: Walking Skeleton` creates a milestone titled "Sprint 07: Walking Skeleton". But `find_milestone(7)` generates regex `^Sprint 7\b` which does NOT match "Sprint 07:...". All downstream consumers (sync_tracking, update_burndown, check_status, sprint_analytics) fail to find the milestone silently.

**Evidence:** Cross-module flow audit Finding #6. `int("07")` = 7, but the milestone title preserves "07". `re.match(r"^Sprint 7\b", "Sprint 07: Walking Skeleton")` returns None.

**Acceptance Criteria:**
- [ ] `find_milestone()` matches sprint numbers with optional leading zeros (e.g., `^Sprint 0*{num}\b`)
- [ ] A test creates a milestone with "Sprint 07:" and verifies find_milestone(7) finds it
- [ ] A test creates "Sprint 7:" and verifies find_milestone(7) also finds it

**Validation Command:**
```bash
python -c "
import re
# Current regex fails:
assert re.match(r'^Sprint 7\b', 'Sprint 07: Walk') is None, 'Bug exists'
# Fixed regex should pass:
assert re.match(r'^Sprint 0*7\b', 'Sprint 07: Walk'), 'Fix works for 07'
assert re.match(r'^Sprint 0*7\b', 'Sprint 7: Walk'), 'Fix works for 7'
print('PASS')
"
```

---

### BH-002: sync_tracking main() write guard is untested — mutation survives
**Severity:** HIGH
**Category:** `test/missing`
**Location:** `skills/sprint-run/scripts/sync_tracking.py` (main loop)
**Status:** 🔴 OPEN
**Pattern:** PAT-001

**Problem:** Flipping `if dirty:` to `if not dirty:` in sync_tracking's main write loop (meaning changed files are NOT written to disk) does NOT cause any test to fail. The mutation survived because unit tests check in-memory TF objects and the integration test doesn't verify file-on-disk state after sync.

**Evidence:** Mutation test sync-tracking #1: SURVIVED.

**Acceptance Criteria:**
- [ ] An integration test runs sync_tracking.main() with a status change (e.g., issue closed)
- [ ] The test reads the tracking file from disk afterward
- [ ] The test asserts the file reflects the updated status
- [ ] Flipping the write guard causes the test to fail

**Validation Command:**
```bash
python -m pytest tests/ -k "sync_tracking" -v 2>&1 | tail -10
```

---

### BH-003: write_tf _yaml_safe() removal survives mutation — no adversarial round-trip test
**Severity:** HIGH
**Category:** `test/shallow`
**Location:** `skills/sprint-run/scripts/sync_tracking.py` (write_tf)
**Status:** 🔴 OPEN
**Pattern:** PAT-001

**Problem:** Removing `_yaml_safe()` from the title field in `write_tf()` does not cause any test to fail. Tests use simple titles that round-trip without quoting. Adversarial titles (starting with `---`, containing newlines, YAML-sensitive chars like `: `) are never tested.

**Evidence:** Mutation test sync-tracking #3: SURVIVED.

**Acceptance Criteria:**
- [ ] A test writes and reads a tracking file with a title containing `: ` and `#`
- [ ] A test writes and reads a tracking file with a title starting with `---`
- [ ] Both tests assert the round-tripped title matches the original exactly
- [ ] Removing `_yaml_safe()` causes at least one test to fail

**Validation Command:**
```bash
python -m pytest tests/ -k "yaml_safe or roundtrip" -v 2>&1 | tail -10
```

---

### BH-004: update_burndown table header removal survives mutation
**Severity:** HIGH
**Category:** `test/shallow`
**Location:** `skills/sprint-run/scripts/update_burndown.py` (write_burndown)
**Status:** 🔴 OPEN
**Pattern:** PAT-001

**Problem:** Removing the markdown table header row (`| Story | SP | Status | Completed |`) from the burndown output does NOT cause any test to fail. Tests check the summary section (SP counts, progress) but never verify the table header.

**Evidence:** Mutation test sync-tracking #7: SURVIVED.

**Acceptance Criteria:**
- [ ] A test asserts that burndown output contains `"| Story | SP | Status |"` (or equivalent header)
- [ ] Removing the table header line causes the test to fail

**Validation Command:**
```bash
python -m pytest tests/ -k "burndown" -v 2>&1 | tail -10
```

---

### BH-005: format_issue_body SP field removal survives mutation
**Severity:** HIGH
**Category:** `test/shallow`
**Location:** `skills/sprint-setup/scripts/populate_issues.py` (format_issue_body)
**Status:** 🔴 OPEN
**Pattern:** PAT-001

**Problem:** Removing the story-point information from the issue body does NOT cause any test to fail. No test asserts "SP" content in `format_issue_body()` output.

**Evidence:** Mutation test populate-bootstrap #3: SURVIVED.

**Acceptance Criteria:**
- [ ] A test asserts `f"{story.sp} SP"` appears in `format_issue_body()` output
- [ ] Removing the SP line causes the test to fail

**Validation Command:**
```bash
python -m pytest tests/ -k "format_issue_body" -v 2>&1 | tail -10
```

---

### BH-006: setup_ci Python version "2.7" mutation survives — no version assertion
**Severity:** HIGH
**Category:** `test/shallow`
**Location:** `skills/sprint-setup/scripts/setup_ci.py` (_python_setup_steps)
**Status:** 🔴 OPEN
**Pattern:** PAT-001

**Problem:** Changing the default Python version from "3.12" to "2.7" in CI generation does NOT cause any test to fail. Tests check for `setup-python@v6` presence but not the version string.

**Evidence:** Mutation test populate-bootstrap #9: SURVIVED.

**Acceptance Criteria:**
- [ ] A test generates CI YAML for a Python project and asserts `python-version: "3.` (prefix)
- [ ] The test also asserts `"2.7"` does NOT appear in the output
- [ ] Changing the version causes the test to fail

**Validation Command:**
```bash
python -m pytest tests/ -k "ci" -v 2>&1 | tail -10
```

---

### BH-007: compute_review_rounds COMMENTED reviews are not excluded in test
**Severity:** MEDIUM
**Category:** `test/shallow`
**Location:** `scripts/sprint_analytics.py` (compute_review_rounds)
**Status:** 🔴 OPEN
**Pattern:** PAT-001

**Problem:** Counting ALL reviews as rounds (instead of just CHANGES_REQUESTED/APPROVED) produces identical results because tests only create APPROVED/CHANGES_REQUESTED reviews. No test creates a COMMENTED review to verify it's excluded.

**Evidence:** Mutation test release-analytics #7: SURVIVED.

**Acceptance Criteria:**
- [ ] A test creates a PR with reviews including COMMENTED, APPROVED, CHANGES_REQUESTED
- [ ] The test asserts COMMENTED is NOT counted as a round
- [ ] Counting all reviews would produce a different (wrong) result

**Validation Command:**
```bash
python -m pytest tests/ -k "review_rounds" -v 2>&1 | tail -10
```

---

### BH-008: add_story separator omission survives mutation
**Severity:** MEDIUM
**Category:** `test/shallow`
**Location:** `scripts/manage_epics.py` (add_story)
**Status:** 🔴 OPEN
**Pattern:** PAT-001

**Problem:** Omitting the `---` separator before a newly added story section does NOT cause any test to fail. The parser finds stories by `### US-XXXX:` headings, not by separators.

**Evidence:** Mutation test release-analytics #9: SURVIVED.

**Acceptance Criteria:**
- [ ] A test adds a story and asserts `"---\n\n### US-"` appears in the raw file content before the new story
- [ ] Removing the separator causes the test to fail

**Validation Command:**
```bash
python -m pytest tests/ -k "add_story" -v 2>&1 | tail -10
```

---

### BH-009: FakeGitHub does not validate label existence on issue create
**Severity:** MEDIUM
**Category:** `design/inconsistency`
**Location:** `tests/fake_github.py:494` (_issue_create)
**Status:** 🔴 OPEN
**Pattern:** PAT-002

**Problem:** Real `gh issue create --label nonexistent` auto-creates the label. FakeGitHub accepts any label without validation. Tests never catch the case where `populate_issues` uses labels that `bootstrap_github` hasn't created yet.

**Evidence:** Cross-module flow audit Finding #16.

**Acceptance Criteria:**
- [ ] FakeGitHub._issue_create validates that each --label exists in self.labels OR auto-creates it (matching real gh behavior)
- [ ] A test verifies that creating an issue with a label that doesn't exist in strict mode produces a warning

**Validation Command:**
```bash
python -m pytest tests/test_fakegithub_fidelity.py -v 2>&1 | tail -10
```

---

### BH-010: FakeGitHub milestone error format doesn't match real API
**Severity:** MEDIUM
**Category:** `design/inconsistency`
**Location:** `tests/fake_github.py:387`, `skills/sprint-setup/scripts/bootstrap_github.py:287`
**Status:** 🔴 OPEN
**Pattern:** PAT-002

**Problem:** FakeGitHub returns `"Validation Failed: milestone title 'X' already exists"` while real GitHub API returns structured JSON `{"message":"Validation Failed","errors":[{"code":"already_exists"}]}`. The `"already_exists" in msg` check works by string-matching coincidence. If gh CLI changes its error format, milestone idempotency breaks.

**Evidence:** Cross-module flow audit Finding #17.

**Acceptance Criteria:**
- [ ] Document the expected error format with a comment
- [ ] Add a FakeGitHub fidelity test that asserts the error message contains "already_exists"
- [ ] Consider using error code instead of string matching

**Validation Command:**
```bash
python -m pytest tests/test_fakegithub_fidelity.py -v 2>&1 | tail -10
```

---

### BH-011: FakeGitHub milestones lack created_at — check_status date path untested
**Severity:** MEDIUM
**Category:** `test/missing`
**Location:** `tests/fake_github.py:389`, `skills/sprint-monitor/scripts/check_status.py:401`
**Status:** 🔴 OPEN
**Pattern:** PAT-002

**Problem:** `check_status.py` reads `ms.get("created_at")` from milestones to determine the "since" date for direct push detection. FakeGitHub's milestone dicts don't include `created_at`. Tests always exercise the 14-day fallback, never the milestone-date code path.

**Evidence:** Cross-module flow audit Finding #18.

**Acceptance Criteria:**
- [ ] FakeGitHub milestone dicts include `created_at` field (ISO 8601 format)
- [ ] A test exercises check_status with a milestone that has created_at set

**Validation Command:**
```bash
python -m pytest tests/ -k "check_status" -v 2>&1 | tail -10
```

---

### BH-012: detect_sprint regex is too permissive — mutation survives
**Severity:** MEDIUM
**Category:** `test/shallow`
**Location:** `scripts/validate_config.py:827` (detect_sprint)
**Status:** 🔴 OPEN
**Pattern:** PAT-003

**Problem:** Changing `r"Current Sprint:\s*(\d+)"` to `r"Sprint:\s*(\d+)"` (less specific) does NOT cause any test to fail. No test has a SPRINT-STATUS.md containing both "Sprint N" (in narrative text) and "Current Sprint: M" where the two numbers differ.

**Evidence:** Mutation test validate-config #9: SURVIVED.

**Acceptance Criteria:**
- [ ] A test has a status file with `"Sprint 2 recap\nCurrent Sprint: 3"` and verifies detect_sprint returns 3, not 2
- [ ] The less-specific regex would return 2 (wrong), failing the test

**Validation Command:**
```bash
python -m pytest tests/ -k "detect_sprint" -v 2>&1 | tail -10
```

---

### BH-013: Scanner deep-doc detection uses assertIsNotNone instead of value checks
**Severity:** MEDIUM
**Category:** `test/shallow`
**Location:** `tests/test_hexwise_setup.py` (multiple assertions)
**Status:** 🔴 OPEN
**Pattern:** PAT-003

**Problem:** 12+ assertions use `assertIsNotNone(result.prd_dir)` etc. without checking the actual path. If the scanner confused `prd_dir` with `sagas_dir`, no test would catch it.

**Evidence:** Assertion quality audit findings 1.1-1.4.

**Acceptance Criteria:**
- [ ] Each assertIsNotNone for deep-doc paths is supplemented with a path-content check (e.g., `self.assertTrue(str(result.prd_dir).endswith("docs/prd"))`)
- [ ] Scanner returning the wrong directory for any field causes a test failure

**Validation Command:**
```bash
python -m pytest tests/test_hexwise_setup.py -v 2>&1 | tail -10
```

---

### BH-014: SP labels are dead code in the automated flow
**Severity:** MEDIUM
**Category:** `design/dead-code`
**Location:** `scripts/validate_config.py:790` (extract_sp label path)
**Status:** 🔴 OPEN
**Pattern:** —

**Problem:** `extract_sp()` checks for `sp:N` labels first, then falls back to body text. But `bootstrap_github` never creates `sp:N` labels, and `populate_issues.create_issue()` never adds them. The label path is dead code in the automated flow.

**Evidence:** Cross-module flow audit Finding #12.

**Acceptance Criteria:**
- [ ] Either: add sp:N label creation to bootstrap_github + create_issue, OR: document the label path as "for manual use" and add a comment
- [ ] If adding label creation: a test verifies sp labels are created and applied

**Validation Command:**
```bash
grep -n 'sp:' scripts/validate_config.py skills/sprint-setup/scripts/populate_issues.py skills/sprint-setup/scripts/bootstrap_github.py
```

---

### BH-015: gate_prs and gate_ci detail messages ignored in tests
**Severity:** MEDIUM
**Category:** `test/shallow`
**Location:** `tests/test_gh_interactions.py` (multiple test methods)
**Status:** 🔴 OPEN
**Pattern:** PAT-003

**Problem:** 4+ tests discard the `detail` return value from gate functions (`ok, _ = gate_prs(...)`). If the function returned `(True, "ERROR: something broke")`, these tests would still pass.

**Evidence:** Assertion quality audit findings 4.7, 4.8.

**Acceptance Criteria:**
- [ ] Tests that check gate function return values also assert on the detail message content
- [ ] `detail` is never ignored with `_` in gate tests

**Validation Command:**
```bash
grep -n 'ok, _' tests/test_gh_interactions.py
```

---

### BH-016: Tracking file slug collisions for similar titles
**Severity:** MEDIUM
**Category:** `bug/logic`
**Location:** `skills/sprint-run/scripts/sync_tracking.py` (create_from_issue / slug_from_title)
**Status:** 🔴 OPEN
**Pattern:** —

**Problem:** `slug_from_title` strips non-alphanumeric characters and lowercases. Two stories like "US-0001: Add Auth" and "US-0001 - Add Auth!" produce the same slug `"us-0001-add-auth"`, silently clobbering tracking files.

**Evidence:** Cross-module flow audit Finding #4.

**Acceptance Criteria:**
- [ ] create_from_issue checks if a tracking file already exists with a different issue number before writing
- [ ] A test creates two issues with similar titles and verifies both get unique tracking files

**Validation Command:**
```bash
python -m pytest tests/ -k "create_from_issue" -v 2>&1 | tail -10
```
