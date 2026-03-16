# Bug Hunter Punchlist — Pass 18

> Generated: 2026-03-16 | Project: giles | Baseline: 750 pass, 0 fail, 0 skip | Coverage: 85%
> Method: Adversarial legacy-code review — cross-module analysis, security audit, duplication scan, test quality deep-read, doc-code drift

## Summary

| Severity | Open | Resolved | Deferred |
|----------|------|----------|----------|
| CRITICAL | 0    | 2        | 0        |
| HIGH     | 2    | 2        | 0        |
| MEDIUM   | 7    | 1        | 0        |
| LOW      | 2    | 2        | 0        |

## Patterns

### PAT-001: check_status.py builds its own milestone logic instead of reusing validate_config helpers
**Instances:** BH18-001, BH18-002, BH18-009
**Root Cause:** check_status.py was written before find_milestone() was hardened (BH-001 leading-zero fix). It duplicates milestone querying and regex matching without benefiting from shared fixes.
**Systemic Fix:** Refactor check_status.py to use find_milestone() and list_milestone_issues() from validate_config.py
**Detection Rule:** `grep -n 'rf"\\^Sprint' skills/sprint-monitor/scripts/check_status.py` — any regex matching sprint titles should use the 0* pattern

### PAT-002: Duplicated frontmatter/table parsing logic across modules
**Instances:** BH18-007, BH18-012, BH18-013
**Root Cause:** Multiple scripts independently parse markdown tables and YAML frontmatter instead of sharing a parser from validate_config.py
**Systemic Fix:** Extract TABLE_ROW regex and _parse_header_table into validate_config.py as shared helpers
**Detection Rule:** `grep -rn 'TABLE_ROW.*compile' scripts/ skills/` — should return exactly 1 hit

### PAT-003: User-controlled TOML values flow into dangerous operations without guardrails
**Instances:** BH18-003, BH18-004
**Root Cause:** project.toml is treated as trusted input even though it could be modified by a malicious contributor in a shared repo
**Systemic Fix:** Add documentation of the trust model; consider confirmation prompt for shell execution
**Detection Rule:** `grep -n 'shell=True' skills/ scripts/` — each hit should have a justification comment

## Items

### BH18-001: check_status.py milestone regex missing leading-zero tolerance — real functional bug
**Severity:** CRITICAL
**Category:** `bug/logic`
**Location:** `skills/sprint-monitor/scripts/check_status.py:184` (check_milestone), `skills/sprint-monitor/scripts/check_status.py:398` (main)
**Status:** ✅ RESOLVED
**Pattern:** PAT-001

**Problem:** `check_status.py` builds its own milestone-matching regex `^Sprint {sprint_num}\b` in two places. This was hardened in `validate_config.find_milestone()` (BH-001 fix: `^Sprint 0*{num}\b`) but the fix was never propagated to check_status.py. When a milestone is titled "Sprint 07: Walking Skeleton", `check_milestone(7)` silently returns "no milestone for Sprint 7" and `main()` uses the 14-day fallback for drift detection instead of the milestone start date.

**Evidence:**
```python
# validate_config.py:896 (FIXED):
re.match(rf"^Sprint 0*{num}\b", title)

# check_status.py:184 (BROKEN):
re.match(rf"^Sprint {sprint_num}\b", m.get("title", ""))

# check_status.py:398 (BROKEN):
re.match(rf"^Sprint {sprint_num}\b", m.get("title", ""))
```

**Acceptance Criteria:**
- [ ] Both regex patterns in check_status.py include `0*` for leading-zero tolerance
- [ ] OR: refactor check_status.py to call `find_milestone()` instead of inline regex
- [ ] A test creates a milestone "Sprint 07: Test" and calls check_milestone(7) — must find it
- [ ] A test creates "Sprint 7: Test" and calls check_milestone(7) — must also find it

**Validation Command:**
```bash
python -c "
import re
# Current broken pattern:
assert re.match(rf'^Sprint {7}\b', 'Sprint 07: Walking Skeleton') is None, 'Bug confirmed'
# Fixed pattern:
assert re.match(rf'^Sprint 0*{7}\b', 'Sprint 07: Walking Skeleton'), 'Fix works'
assert re.match(rf'^Sprint 0*{7}\b', 'Sprint 7: Walking Skeleton'), 'Fix works for plain'
print('PASS: check_status milestone regex bug confirmed')
"
```

---

### BH18-002: check_status.py makes redundant milestone API calls — should reuse find_milestone()
**Severity:** CRITICAL
**Category:** `design/duplication`
**Location:** `skills/sprint-monitor/scripts/check_status.py:174-184` (check_milestone), `skills/sprint-monitor/scripts/check_status.py:392-404` (main)
**Status:** ✅ RESOLVED
**Pattern:** PAT-001

**Problem:** check_status.py queries the milestones API independently in two places (check_milestone at :174 and main at :392) instead of calling `find_milestone()` from validate_config.py. This causes: (a) 2 extra API calls per monitoring cycle, (b) the leading-zero bug in BH18-001, (c) divergent behavior when find_milestone gets future fixes. The main() function also queries milestones AGAIN for the sprint start date (`created_at`), when find_milestone() already returns the full milestone dict including created_at.

**Acceptance Criteria:**
- [ ] check_milestone() calls find_milestone(sprint_num) instead of querying milestones API directly
- [ ] main() calls find_milestone() once and reuses the result for both milestone progress and created_at
- [ ] Total milestone API calls reduced from 3 to 1 per monitoring cycle
- [ ] All existing check_status tests still pass

**Validation Command:**
```bash
python -m pytest tests/ -k "check_status or check_milestone" -v 2>&1 | tail -10
```

---

### BH18-003: gate_tests and gate_build use shell=True with TOML-sourced commands — supply chain risk
**Severity:** HIGH
**Category:** `security/injection`
**Location:** `skills/sprint-release/scripts/release_gate.py:209` (gate_tests), `skills/sprint-release/scripts/release_gate.py:229` (gate_build)
**Status:** 🔴 OPEN
**Pattern:** PAT-003

**Problem:** `gate_tests()` passes `config["ci"]["check_commands"]` to `subprocess.run(cmd, shell=True)`. These strings come from project.toml via the custom TOML parser. A malicious PR that modifies project.toml can execute arbitrary shell commands on any developer who runs `sprint-release`. The code has a justification comment, but no guardrails (no confirmation prompt, no allowlist, no sandboxing).

**Evidence:** Security audit finding S1. Real-world vector: attacker modifies project.toml in a PR, reviewer runs sprint-release to validate gates before merge, attacker's commands execute.

**Acceptance Criteria:**
- [ ] Document the trust model for project.toml in SKILL.md or the release flow
- [ ] Add a confirmation prompt showing the exact commands before executing them (unless --yes flag)
- [ ] OR: Add a `[ci] trusted = true` flag that must be set manually (not by sprint-init) to enable shell execution
- [ ] A test verifies that gate_tests refuses to execute if the trust mechanism is missing

**Validation Command:**
```bash
grep -n 'shell=True' skills/sprint-release/scripts/release_gate.py
# Should be accompanied by trust/confirmation mechanism
```

---

### BH18-004: _build_row_regex accepts user regex pattern without ReDoS protection
**Severity:** HIGH
**Category:** `security/redos`
**Location:** `skills/sprint-setup/scripts/populate_issues.py:78` (_build_row_regex)
**Status:** 🔴 OPEN
**Pattern:** PAT-003

**Problem:** `_build_row_regex()` compiles `config["backlog"]["story_id_pattern"]` into a regex. It rejects capturing groups but does NOT check for catastrophic backtracking patterns (e.g., `(?:a+)+b`). A malicious story_id_pattern in project.toml could cause exponential backtracking when applied to milestone files, hanging CI or developer machines.

**Acceptance Criteria:**
- [ ] Add a timeout or complexity check on the compiled pattern (e.g., test it against a 1000-char string with 1-second timeout)
- [ ] OR: Restrict the pattern to a safe subset (e.g., only allow `\d`, `\w`, `[A-Z]`, `+`, `{n,m}`, literal chars)
- [ ] A test verifies that a known ReDoS pattern like `(?:a+)+b` is rejected or doesn't hang

**Validation Command:**
```bash
python -c "
import re, signal

def timeout_handler(signum, frame):
    raise TimeoutError('ReDoS detected')

# This is the kind of pattern that should be rejected:
pattern = r'(?:a+)+b'
signal.signal(signal.SIGALRM, timeout_handler)
signal.alarm(2)
try:
    compiled = re.compile(rf'\|\s*({pattern})\s*\|')
    compiled.search('| ' + 'a' * 30 + ' |')
    print('Pattern completed (safe or not checked)')
except TimeoutError:
    print('CONFIRMED: ReDoS pattern hangs without protection')
finally:
    signal.alarm(0)
"
```

---

### BH18-005: _fm_val in update_burndown.py duplicates sync_tracking frontmatter parsing — coupling hazard
**Severity:** HIGH
**Category:** `design/coupling`
**Location:** `skills/sprint-run/scripts/update_burndown.py:144-153` (_fm_val), `skills/sprint-run/scripts/sync_tracking.py:162-171` (v() closure)
**Status:** ✅ RESOLVED — extracted frontmatter_value() into validate_config.py
**Pattern:** PAT-002

**Problem:** `update_burndown._fm_val()` and `sync_tracking.read_tf.v()` both parse YAML-ish frontmatter with identical regex and quote-stripping logic. The escape/unescape convention must stay synchronized: `_yaml_safe` escapes backslashes then quotes, and both readers must unescape in reverse order. A comment in update_burndown.py:149 says "matches sync_tracking.read_tf behavior" but there is no enforcement — if either changes, the other silently produces wrong values.

**Acceptance Criteria:**
- [ ] Extract `_fm_val` logic into validate_config.py or sync_tracking.py as a shared function
- [ ] Both update_burndown and sync_tracking import and use the shared function
- [ ] A round-trip test writes a tracking file with adversarial content (backslashes, quotes, colons) via write_tf, then reads it with both _fm_val and read_tf, and asserts both produce identical results
- [ ] Removing _yaml_safe from write_tf causes the shared test to fail

**Validation Command:**
```bash
python -m pytest tests/ -k "roundtrip or yaml_safe or fm_val" -v 2>&1 | tail -10
```

---

### BH18-006: compute_review_rounds counts COMMENTED reviews as 1 round via fallback
**Severity:** HIGH
**Category:** `bug/logic`
**Location:** `scripts/sprint_analytics.py:107-113` (compute_review_rounds)
**Status:** ✅ RESOLVED — removed COMMENTED fallback, added test
**Pattern:** —

**Problem:** The review round counting has a "minimum 1 round" fallback at line 112: `if reviews and round_count == 0: round_count = 1`. This means a PR with only COMMENTED reviews (no APPROVED/CHANGES_REQUESTED) gets counted as 1 review round. The docstring says "each CHANGES_REQUESTED or APPROVED counts as a round" — COMMENTED should not count. This inflates review round metrics for PRs that only have comment-only reviews.

**Evidence:** Pass 17 identified this (BH-007) as test/shallow. But it's actually a logic bug: the fallback conflates "has reviews" with "has review rounds." A PR with 5 COMMENTED reviews should show 0 rounds, not 1.

**Acceptance Criteria:**
- [ ] Remove the `if reviews and round_count == 0: round_count = 1` fallback
- [ ] OR: Change to only count as 1 round if there's at least one APPROVED or CHANGES_REQUESTED
- [ ] A test creates a PR with only COMMENTED reviews and asserts round_count == 0
- [ ] A test creates a PR with COMMENTED + APPROVED and asserts round_count == 1 (not 2)

**Validation Command:**
```bash
python -m pytest tests/ -k "review_rounds" -v 2>&1 | tail -10
```

---

### BH18-007: validate_project does not check for definition-of-done.md — doc-code drift
**Severity:** MEDIUM
**Category:** `design/gap`
**Location:** `scripts/validate_config.py:392-403` (_REQUIRED_FILES)
**Status:** ✅ RESOLVED — added to _REQUIRED_FILES, updated test fixtures
**Pattern:** —

**Problem:** CLAUDE.md documents `definition-of-done.md` as part of the sprint-config structure. sprint_init.py generates it. Ceremony references (retro, demo) depend on it. But `_REQUIRED_FILES` does not include it, so `validate_project()` won't catch a missing definition-of-done.md. A user who deletes it won't get a validation error.

**Acceptance Criteria:**
- [ ] Add `("{config_dir}/definition-of-done.md", "Definition of Done (baseline + retro additions)")` to _REQUIRED_FILES
- [ ] A test verifies that removing definition-of-done.md causes validate_project to fail
- [ ] Existing tests still pass (sprint_init generates the file, so fixtures should have it)

**Validation Command:**
```bash
python -c "
import sys; sys.path.insert(0, 'scripts')
from validate_config import _REQUIRED_FILES
dod = any('definition-of-done' in f for f, _ in _REQUIRED_FILES)
print(f'definition-of-done.md in _REQUIRED_FILES: {dod}')
assert dod, 'FAIL: definition-of-done.md should be required'
"
```

---

### BH18-008: validate_project requires "at least 2 personas" but should require 2+ non-Giles personas
**Severity:** MEDIUM
**Category:** `bug/logic`
**Location:** `scripts/validate_config.py:492-496` (validate_project persona check)
**Status:** 🔴 OPEN
**Pattern:** —

**Problem:** validate_project checks `len(persona_rows) < 2` but sprint_init always injects Giles (scrum master). A project with only 1 human persona + Giles has 2 rows and passes validation. But sprint-run requires at least 2 different personas for implementer/reviewer assignment. With only 1 non-Giles persona, the same person would implement and review their own code.

**Acceptance Criteria:**
- [ ] Either: require `len(persona_rows) >= 3` (2 devs + Giles)
- [ ] OR: require at least 2 persona rows whose name is NOT "Giles" (case-insensitive)
- [ ] A test with exactly 1 persona + Giles fails validation with a clear error message
- [ ] A test with 2 personas + Giles passes validation

**Validation Command:**
```bash
python -m pytest tests/ -k "validate_project or persona" -v 2>&1 | tail -10
```

---

### BH18-009: check_status.main() queries milestones 3 times per monitoring cycle
**Severity:** MEDIUM
**Category:** `design/performance`
**Location:** `skills/sprint-monitor/scripts/check_status.py:174,392,417`
**Status:** 🔴 OPEN
**Pattern:** PAT-001

**Problem:** In a single monitoring cycle, check_status.main() makes 3 separate milestones API calls: (1) in check_milestone:174 to find the milestone, (2) in main:392 to get created_at for drift detection, (3) implicitly via check_milestone's issue query. With rate-limited GitHub APIs and the monitor running every 5 minutes, this wastes 2 API calls per cycle.

**Acceptance Criteria:**
- [ ] main() calls find_milestone() once and passes the result to check_milestone() and uses created_at from it
- [ ] Total milestones API calls per monitoring cycle reduced from 3 to 1
- [ ] check_milestone() accepts an optional pre-fetched milestone dict

**Validation Command:**
```bash
python -m pytest tests/ -k "check_status" -v 2>&1 | tail -10
```

---

### BH18-010: get_linked_pr branch-name fallback is overly broad
**Severity:** MEDIUM
**Category:** `bug/edge-case`
**Location:** `skills/sprint-run/scripts/sync_tracking.py:106`
**Status:** 🔴 OPEN
**Pattern:** —

**Problem:** `get_linked_pr()` fallback searches pre-fetched PRs by `re.search(rf"\b{re.escape(story_id)}\b", branch, re.IGNORECASE)`. Story ID "US-0001" would match branch `sprint-2/us-0001-follow-up` even if that branch belongs to a different sprint's issue. The branch-name convention is `sprint-{N}/US-{ID}-{slug}`, but the search ignores the sprint prefix.

**Acceptance Criteria:**
- [ ] Fallback search also checks that the branch matches the expected sprint pattern (e.g., `sprint-{current}/`)
- [ ] OR: match only at the beginning of the slug portion (after the last `/`)
- [ ] A test creates two PRs with branches `sprint-1/us-0001-setup` and `sprint-2/us-0001-follow-up`, and verifies that sync_tracking for sprint 1 only links the first PR

**Validation Command:**
```bash
python -m pytest tests/ -k "linked_pr" -v 2>&1 | tail -10
```

---

### BH18-011: No test exercises check_milestone with leading-zero milestone title
**Severity:** MEDIUM
**Category:** `test/missing`
**Location:** `tests/test_sprint_runtime.py:1647-1664` (TestCheckMilestone)
**Status:** 🔴 OPEN
**Pattern:** PAT-001

**Problem:** All TestCheckMilestone tests use "Sprint 1" (no leading zero). No test verifies check_milestone(7) finds "Sprint 07: Walking Skeleton". This is why BH18-001 survived 17 audit passes — the bug is never exercised.

**Acceptance Criteria:**
- [ ] A test creates milestone titled "Sprint 07: Leading Zero Test"
- [ ] Calls check_milestone(7) and asserts it finds the milestone (not "no milestone")
- [ ] Report includes milestone progress, not the "no milestone" fallback message

**Validation Command:**
```bash
python -m pytest tests/ -k "leading_zero and check_milestone" -v 2>&1 | tail -10
```

---

### BH18-012: TABLE_ROW regex defined identically in 3 separate files
**Severity:** MEDIUM
**Category:** `design/duplication`
**Location:** `scripts/manage_epics.py:23`, `scripts/manage_sagas.py:22`, `scripts/traceability.py:24`
**Status:** 🔴 OPEN
**Pattern:** PAT-002

**Problem:** `TABLE_ROW = re.compile(r'^\|\s*(.+?)\s*\|\s*(.+?)\s*\|')` is copy-pasted into three files. If the pattern needs updating (e.g., to handle escaped pipes), all three must change in sync.

**Acceptance Criteria:**
- [ ] Move TABLE_ROW to validate_config.py as a shared constant
- [ ] All 3 files import it from validate_config
- [ ] `grep -rn 'TABLE_ROW.*compile' scripts/` returns exactly 1 hit (in validate_config.py)

**Validation Command:**
```bash
grep -rn 'TABLE_ROW.*compile' scripts/ skills/ | wc -l
# Should be 1 after fix
```

---

### BH18-013: _parse_header_table duplicated between manage_epics.py and manage_sagas.py
**Severity:** MEDIUM
**Category:** `design/duplication`
**Location:** `scripts/manage_epics.py:70`, `scripts/manage_sagas.py:65`
**Status:** 🔴 OPEN
**Pattern:** PAT-002

**Problem:** Both files define `_parse_header_table(lines)` with nearly identical logic. The only difference is the stop condition (`###` in epics vs `##` in sagas). This could be parameterized.

**Acceptance Criteria:**
- [ ] Extract a shared `parse_header_table(lines, stop_heading="###")` function
- [ ] Both manage_epics and manage_sagas call it with their respective stop heading
- [ ] Both existing test suites pass unchanged

**Validation Command:**
```bash
python -m pytest tests/test_pipeline_scripts.py -k "epic or saga" -v 2>&1 | tail -10
```

---

### BH18-014: symlink targets in sprint_init.py not validated against project root
**Severity:** MEDIUM
**Category:** `security/path-traversal`
**Location:** `scripts/sprint_init.py:549-561` (_symlink)
**Status:** 🔴 OPEN
**Pattern:** —

**Problem:** `ConfigGenerator._symlink()` creates symlinks from sprint-config/ to targets without validating the resolved target is within the project root. While targets come from scanner detections (not directly from TOML), a future change to accept TOML-sourced paths could introduce path traversal. Defense in depth says validate now.

**Acceptance Criteria:**
- [ ] `_symlink()` resolves target_abs and asserts it starts with self.root
- [ ] If target is outside project root, skip with a warning
- [ ] A test attempts to create a symlink targeting `../../etc/passwd` and verifies it's rejected

**Validation Command:**
```bash
python -m pytest tests/ -k "sprint_init or symlink" -v 2>&1 | tail -10
```

---

### BH18-015: sync_backlog.py catches Exception instead of ConfigError
**Severity:** LOW
**Category:** `design/error-handling`
**Location:** `scripts/sync_backlog.py:246-250`
**Status:** ✅ RESOLVED — narrowed to ConfigError, RuntimeError, ImportError
**Pattern:** —

**Problem:** The main() `except Exception` block catches everything including KeyboardInterrupt, MemoryError, and unexpected bugs. Every other script catches `ConfigError` specifically. This inconsistency could swallow bugs.

**Acceptance Criteria:**
- [ ] Change `except Exception` to `except (ConfigError, RuntimeError)` or similar specific exceptions
- [ ] Add a comment explaining why broader exception handling is needed (if it is)
- [ ] Existing sync_backlog tests pass

**Validation Command:**
```bash
grep -n 'except Exception' scripts/sync_backlog.py
# Should be 0 after fix (or have a justification comment)
```

---

### BH18-016: _KANBAN_STATES backward-compat alias is unused externally
**Severity:** LOW
**Category:** `design/dead-code`
**Location:** `scripts/validate_config.py:853`
**Status:** ✅ RESOLVED — alias removed, direct reference used
**Pattern:** —

**Problem:** `_KANBAN_STATES = KANBAN_STATES  # Backward compat alias` is only used internally in `kanban_from_labels()` at line 872. No external script imports `_KANBAN_STATES`. The alias adds confusion without value.

**Acceptance Criteria:**
- [ ] Replace `_KANBAN_STATES` usage at line 872 with `KANBAN_STATES`
- [ ] Remove the `_KANBAN_STATES` alias line
- [ ] All tests pass

**Validation Command:**
```bash
grep -rn '_KANBAN_STATES' scripts/ skills/ tests/
# Should be 0 after fix
```

---

### BH18-017: test_coverage.py (the coverage checker) has the lowest test coverage at 68%
**Severity:** LOW
**Category:** `test/gap`
**Location:** `scripts/test_coverage.py`
**Status:** 🔴 OPEN
**Pattern:** —

**Problem:** The script whose job is to check test coverage has the lowest coverage of any module at 68%. Missing coverage: `scan_project_tests()` main loop, `check_test_coverage()` report formatting, several edge-case paths. This is both ironic and a real gap — if the coverage checker itself has bugs, it could miss gaps in the project it's monitoring.

**Acceptance Criteria:**
- [ ] Add tests for `scan_project_tests()` with a mock project directory
- [ ] Add tests for `check_test_coverage()` report output format
- [ ] Coverage for test_coverage.py reaches at least 85%

**Validation Command:**
```bash
python -m pytest tests/ --cov=scripts/test_coverage --cov-report=term-missing 2>&1 | grep test_coverage
```

---

### BH18-018: CHEATSHEET.md line numbers likely stale after 17 bug-hunter passes
**Severity:** LOW
**Category:** `docs/drift`
**Location:** `CHEATSHEET.md`
**Status:** 🔴 OPEN
**Pattern:** —

**Problem:** CHEATSHEET.md contains line-number indices for all functions and sections. After 279 commits (44% of which are fixes that change line numbers), many of these references are likely stale. The project has validate_anchors.py for §-anchor validation but no automated check for line-number accuracy.

**Acceptance Criteria:**
- [ ] Run a verification pass: for each `line N` reference in CHEATSHEET.md, check if the referenced function/section still exists at that line
- [ ] Update stale line numbers
- [ ] OR: Consider switching from line numbers to §-anchors (which don't drift)

**Validation Command:**
```bash
python scripts/validate_anchors.py 2>&1 | tail -5
# Only checks §-anchors, not line numbers — this is the gap
```
