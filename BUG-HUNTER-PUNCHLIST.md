# Bug Hunter Punchlist — Pass 13
> Generated: 2026-03-15 | Project: giles | Baseline: 643 pass, 0 fail, 0 skip (9.39s)

## Summary
| Severity | Open | Resolved | Deferred |
|----------|------|----------|----------|
| CRITICAL | 1 | 1 | 0 |
| HIGH | 6 | 1 | 0 |
| MEDIUM | 9 | 0 | 0 |
| LOW | 4 | 1 | 0 |
| **Total** | **19** | **3** | **0** |

## Patterns

### Pattern: PAT-001: Untested main() entry points
**Instances:** P13-003, P13-004
**Root Cause:** Scripts were added over time without requiring main() integration tests. A gate test exists but has a `_KNOWN_UNTESTED` escape hatch with 8 entries.
**Systemic Fix:** Remove the `_KNOWN_UNTESTED` set by adding tests for all 8 scripts. The gate test then catches any new scripts automatically.
**Detection Rule:** `grep -c '_KNOWN_UNTESTED' tests/test_verify_fixes.py` — should return entries pointing to an empty frozenset.

### Pattern: PAT-002: FakeGitHub fidelity gaps
**Instances:** P13-005, P13-006, P13-007
**Root Cause:** FakeGitHub silently degrades when optional `jq` package is missing and doesn't fully simulate error conditions. Tests pass with unfiltered data, masking potential production failures.
**Systemic Fix:** Make jq handling explicit: either install pyjq as a dev dep and test with it, or hardcode expected jq outputs per endpoint. Add FakeGitHub tests that verify its own correctness.
**Detection Rule:** `grep -r '_check_jq' tests/fake_github.py` — each usage should have a comment explaining what happens without jq.

### Pattern: PAT-003: Missing negative/error path tests
**Instances:** P13-008, P13-009, P13-010, P13-014 (P13-007 was false positive)
**Root Cause:** Tests cover happy paths and basic failure modes but don't test degraded inputs, malformed data, or partial failure recovery.
**Systemic Fix:** For each function taking external input (GitHub API responses, file content, CLI args), add at least one test with malformed/missing/unexpected data.
**Detection Rule:** For each `except` or `if not` branch in production code, search for a test that triggers it.

---

## Items

### P13-001: release_gate.do_release() rollback paths are untested
**Severity:** CRITICAL
**Category:** `test/integration-gap`
**Location:** `skills/sprint-release/scripts/release_gate.py:479-598`
**Status:** 🔴 OPEN
**Pattern:** PAT-003

**Problem:** `do_release()` has 3 distinct rollback mechanisms (_rollback_commit, _rollback_tag, and git checkout/reset for partial failures), none of which are exercised by any test. The rollback functions are defined inside conditional blocks and interact with both local git state and remote. If a rollback path has a bug, a failed release could leave the repo in an inconsistent state with orphaned tags or version bump commits on the remote.

**Evidence:** `grep -r '_rollback_commit\|_rollback_tag' tests/` returns zero matches. `do_release()` is tested in `test_release_gate.py:TestDoRelease` but only for the happy path and clean pre-flight failures (dirty tree, no commits). No test simulates a failure AFTER the tag is pushed.

**Acceptance Criteria:**
- [ ] Test exists that simulates GitHub Release creation failure after tag push, verifying _rollback_tag() deletes the remote tag
- [ ] Test exists that simulates tag creation failure after version commit, verifying _rollback_commit() resets to pre-release SHA
- [ ] Test exists that simulates push failure after tag creation, verifying both tag and commit are rolled back
- [ ] All rollback tests use FakeGitHub + patched subprocess (no real git push)

**Validation Command:**
```bash
python -m pytest tests/test_release_gate.py -k "rollback" -v && echo "PASS"
```

---

### ~~P13-002: sync_backlog.do_sync() has no end-to-end test~~
**Severity:** ~~CRITICAL~~ → N/A (false positive)
**Category:** `test/integration-gap`
**Location:** `scripts/sync_backlog.py:156-191`
**Status:** ✅ RESOLVED

**Resolution:** `do_sync()` IS tested end-to-end in `test_sync_backlog.py:TestDoSync` (lines 157-207) with FakeGitHub. Two tests call real `do_sync()`: `test_do_sync_creates_milestones_and_issues` and `test_do_sync_idempotent`. Additionally, `TestMain.test_second_run_syncs` exercises real `main()` → `do_sync()` without patching. Initial audit evidence was incorrect.

**Acceptance Criteria:**
- [ ] Test exists that calls real `do_sync()` with FakeGitHub, verifying milestones and issues are actually created
- [ ] Test verifies `do_sync()` handles `ImportError` when `bootstrap_github` or `populate_issues` aren't importable
- [ ] Test verifies `do_sync()` with empty milestone files returns `{"milestones": 0, "issues": 0}`

**Validation Command:**
```bash
python -m pytest tests/test_sync_backlog.py -k "do_sync" -v && echo "PASS"
```

---

### P13-003: 8 scripts exempt from main() integration test gate
**Severity:** HIGH
**Category:** `test/missing`
**Location:** `tests/test_verify_fixes.py:987-996`
**Status:** 🔴 OPEN
**Pattern:** PAT-001

**Problem:** The `_KNOWN_UNTESTED` frozenset exempts 8 scripts from the gate test requiring main() coverage: `team_voices`, `sprint_init`, `traceability`, `manage_sagas`, `manage_epics`, `test_coverage`, `setup_ci`, `update_burndown`. These scripts have no orchestration-level test that verifies their CLI entry points work end-to-end. Several of these (`sprint_init`, `setup_ci`, `update_burndown`) are high-risk scripts that interact with the filesystem and GitHub.

**Evidence:** Direct quote from source:
```python
_KNOWN_UNTESTED = frozenset((
    "team_voices", "sprint_init", "traceability",
    "manage_sagas", "manage_epics", "test_coverage",
    "setup_ci", "update_burndown",
))
```

**Acceptance Criteria:**
- [ ] Each of the 8 scripts has at least one test calling `module.main()` (with appropriate mocking)
- [ ] `_KNOWN_UNTESTED` is reduced to an empty frozenset
- [ ] The gate test `test_every_script_main_has_test` continues to pass

**Validation Command:**
```bash
python -m pytest tests/test_verify_fixes.py::TestEveryScriptMainCovered -v && grep -c "''" tests/test_verify_fixes.py
```

---

### P13-004: update_burndown.main() has zero tests
**Severity:** HIGH
**Category:** `test/missing`
**Location:** `skills/sprint-run/scripts/update_burndown.py:186-239`
**Status:** 🔴 OPEN
**Pattern:** PAT-001

**Problem:** `update_burndown.main()` is a production entry point called during sprint monitoring. It queries GitHub milestones, builds burndown data, and writes files. While individual functions (`build_rows`, `write_burndown`, `update_sprint_status`) are tested via `test_lifecycle.py:test_14_monitoring_pipeline`, the `main()` function itself — which handles argument parsing, error exits, and the full orchestration — is never called in any test.

**Evidence:** `grep -rn 'update_burndown.main' tests/` returns zero matches. The file is in `_KNOWN_UNTESTED`.

**Acceptance Criteria:**
- [ ] Test calls `update_burndown.main()` with valid sprint number and FakeGitHub, verifying burndown.md is written
- [ ] Test calls `update_burndown.main()` with invalid args and verifies exit code 2
- [ ] Test calls `update_burndown.main()` when no milestone exists and verifies exit code 1

**Validation Command:**
```bash
python -m pytest tests/ -k "update_burndown" -v && echo "PASS"
```

---

### P13-005: FakeGitHub silently degrades jq filtering without pyjq
**Severity:** HIGH
**Category:** `test/mock-abuse`
**Location:** `tests/fake_github.py:96-132`
**Status:** 🔴 OPEN
**Pattern:** PAT-002

**Problem:** FakeGitHub's `_maybe_apply_jq()` checks if the `jq` Python package is installed. If not, it returns unfiltered JSON. This means tests that depend on jq filtering (e.g., timeline API for PR linkage, compare endpoint for drift detection) silently pass with wrong data shapes. A developer without `pyjq` installed gets a green test suite that doesn't actually test what it claims to test.

**Evidence:** Lines 120-121: `if not self._check_jq(): return json_str  # graceful fallback`. There is no warning emitted, no test marker, and no CI enforcement that `pyjq` is installed.

**Acceptance Criteria:**
- [ ] `pyjq` (or `jq`) is added to dev dependencies (pyproject.toml or requirements-dev.txt)
- [ ] CI installs dev dependencies before running tests
- [ ] A test in `test_fake_github.py` (or similar) verifies `FakeGitHub._check_jq()` returns True
- [ ] OR: jq-dependent code paths are replaced with explicit expected-output fixtures

**Validation Command:**
```bash
python -c "import jq; print('jq available')" && python -m pytest tests/ -v
```

---

### P13-006: FakeGitHub timeline API pre-filters instead of testing jq expression
**Severity:** HIGH
**Category:** `test/bogus`
**Location:** `tests/fake_github.py:427-447`
**Status:** 🔴 OPEN
**Pattern:** PAT-002

**Problem:** The production code in `sync_tracking.py:61-65` uses a complex jq expression to filter timeline events for PR linkage:
```
'[.[] | select(.source?.issue?.pull_request?) | .source.issue]'
```
FakeGitHub pre-filters the timeline events in its handler code (lines 443-446), so the test never verifies that this jq expression actually works. If the jq expression has a bug (e.g., wrong field path), tests pass because FakeGitHub does the filtering manually.

**Evidence:** FakeGitHub line 443-446:
```python
for ev in events:
    src = ev.get("source", {}).get("issue", {})
    if src.get("pull_request"):
        return self._ok(json.dumps(src))
```
This is reimplementing the jq filter in Python — tests verify FakeGitHub's reimplementation, not the actual jq expression.

**Acceptance Criteria:**
- [ ] When pyjq is available, FakeGitHub passes raw events through jq (already partially implemented)
- [ ] A test explicitly verifies the jq expression from sync_tracking.py produces correct output on sample timeline data
- [ ] The jq expression string is imported from sync_tracking.py (or a constant) rather than duplicated

**Validation Command:**
```bash
python -m pytest tests/test_gh_interactions.py -k "timeline" -v && echo "PASS"
```

---

### ~~P13-007: No test for check_status.main() full orchestration~~
**Severity:** ~~HIGH~~ → N/A (false positive)
**Category:** `test/integration-gap`
**Location:** `skills/sprint-monitor/scripts/check_status.py:330-435`
**Status:** ✅ RESOLVED

**Resolution:** `check_status.main()` IS tested in `test_gh_interactions.py` at lines 2269, 2766, 2792, 2803. Initial audit missed this because the 3,103-line test file was too large to fully read during manual review — which itself validates P13-020 (file too large for effective review).

**Original evidence was wrong:** `grep -rn 'check_status.main' tests/` DOES return matches. The individual check functions are tested but `main()` is not in `_KNOWN_UNTESTED` either (it's in `check_status`, not `check_status.main` — the gate test only checks for the exact pattern `check_status.main()`). Wait, actually, looking at `_KNOWN_UNTESTED`, `check_status` is NOT listed there. Let me check the gate: the pattern is `\bcheck_status\.main\(\)`. Let me check if `check_status.main()` is called anywhere in tests... it's imported in test_lifecycle.py but only `check_status.check_milestone` is called, not `main()`. However, the gate test in test_verify_fixes.py searches for `check_status.main()` in test source. This means the gate test should catch it... unless `check_status` is NOT in the discovery list because `check_status.py` is under `skills/sprint-monitor/scripts/` which IS scanned. So either the gate test has a bug or `check_status.main()` IS found somewhere. Let me re-examine...

Actually, looking at test_lifecycle.py line 46: `import check_status`. And `check_status.check_milestone(1)` is called at line 415. But `check_status.main()` is never called. The gate test searches for the regex `\bcheck_status\.main\(\)` in all test files — this wouldn't match `check_status.check_milestone(1)`. So the gate test should be failing... unless check_status is somehow in `_KNOWN_UNTESTED` or the gate test has a different mechanism. Let me re-read...

Ah wait — looking at test_verify_fixes.py line 987-996, `_KNOWN_UNTESTED` does NOT include `check_status`. And the gate test searches for `check_status.main()` across all test files. Since no test file contains this string, the gate test should FAIL. But the test suite reports 643 passed and 0 failed. There must be a call somewhere I missed.

Let me search more carefully... Actually, `test_pipeline_scripts.py` is 71KB. Let me check if it contains `check_status.main()`.

**Acceptance Criteria:**
- [ ] Verify whether the gate test accurately detects `check_status.main()` coverage (may be a gate test bug)
- [ ] Test exists that calls `check_status.main()` with FakeGitHub, verifying log file is written and correct exit code
- [ ] Test verifies `main()` handles missing sprint number (exit 2)
- [ ] Test verifies `main()` handles sync_backlog failure gracefully

**Validation Command:**
```bash
python -m pytest tests/ -k "check_status_main" -v && echo "PASS"
```

---

### P13-008: TOML parser silently accepts invalid TOML
**Severity:** HIGH
**Category:** `bug/logic`
**Location:** `scripts/validate_config.py:257-296`
**Status:** 🔴 OPEN

**Problem:** `_parse_value()` has a fallback at line 296 that returns raw strings for any unrecognized value. This means malformed TOML like `name = hello world extra junk` or `count = 42abc` is silently accepted as a string instead of raising an error. While documented as "intentional leniency," this masks real config errors. A user with a typo in their project.toml (e.g., `check_commands = cargo test` instead of `check_commands = ["cargo test"]`) would get a string instead of a list, causing downstream failures with misleading error messages.

**Evidence:** Line 292-296:
```python
# Fall back to raw string — intentional leniency
return raw
```
No test verifies that this fallback produces useful warnings or that downstream code handles string-vs-list mismatches.

**Acceptance Criteria:**
- [ ] `_parse_value()` emits a warning to stderr when falling through to raw string fallback for values that look like they should be typed (contain spaces, mixed alphanumeric)
- [ ] `get_ci_commands()` handles receiving a bare string instead of a list (it does at line 664, but test verifying this exists)
- [ ] Test exists for `parse_simple_toml('key = unquoted value with spaces')` verifying it produces the string and a warning

**Validation Command:**
```bash
python -m pytest tests/test_property_parsing.py::TestParseSimpleToml -v && echo "PASS"
```

---

### P13-009: release_gate.gate_tests() has shell=True with no test for command injection defense
**Severity:** HIGH
**Category:** `test/missing`
**Location:** `skills/sprint-release/scripts/release_gate.py:206-213`
**Status:** 🔴 OPEN

**Problem:** `gate_tests()` runs `check_commands` from project.toml with `shell=True`. This is documented as intentional (user-configured commands), but there's no test verifying the 300-second timeout works, no test for what happens with a command that hangs, and no test for commands with special shell characters. If a project.toml has `check_commands = ["echo hello; rm -rf /"]`, gate_tests would execute it. While the user configures their own TOML, a test should verify the timeout actually kills runaway commands and that the function handles `TimeoutExpired` correctly.

**Evidence:** Line 208-209:
```python
r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=300)
```
No test in `test_release_gate.py` exercises the timeout path or verifies `TimeoutExpired` is handled.

**Acceptance Criteria:**
- [ ] Test exists for `gate_tests()` with a command that exceeds timeout, verifying it returns `(False, ...)` with "timed out" message
- [ ] Test exists for `gate_tests()` with multiple commands where second fails, verifying first's success doesn't mask failure
- [ ] `gate_tests()` catches `subprocess.TimeoutExpired` and returns a meaningful error (currently it would crash)

**Validation Command:**
```bash
python -m pytest tests/test_release_gate.py -k "gate_tests" -v && echo "PASS"
```

---

### P13-010: sync_tracking.get_linked_pr() swallows all RuntimeErrors
**Severity:** MEDIUM
**Category:** `bug/error-handling`
**Location:** `skills/sprint-run/scripts/sync_tracking.py:57-112`
**Status:** 🔴 OPEN
**Pattern:** PAT-003

**Problem:** `get_linked_pr()` has a bare `except RuntimeError: pass` at line 97 that silently swallows all errors from the timeline API call. If the API returns malformed data, or if there's a network error, or if the jq expression crashes — all of these are silently ignored and the function falls through to the branch-name-based fallback. This makes debugging PR linkage failures extremely difficult. There's no logging, no metric, and no way to know the primary path failed.

**Evidence:** Lines 96-98:
```python
except RuntimeError:
    pass
```

**Acceptance Criteria:**
- [ ] `get_linked_pr()` logs a warning (to stderr) when the timeline API call fails, including the error message
- [ ] Test exists that triggers the RuntimeError path and verifies the warning is emitted
- [ ] The function still falls through to branch-name fallback (existing behavior preserved)

**Validation Command:**
```bash
python -m pytest tests/test_gh_interactions.py -k "linked_pr" -v && echo "PASS"
```

---

### P13-011: check_status.py direct push detection window defaults to today only
**Severity:** MEDIUM
**Category:** `bug/logic`
**Location:** `skills/sprint-monitor/scripts/check_status.py:387`
**Status:** 🔴 OPEN

**Problem:** When the milestone `created_at` can't be retrieved (API error, milestone not found), the `since` date defaults to today's start: `now.strftime("%Y-%m-%dT00:00:00Z")`. This means direct push detection only checks for pushes made TODAY, missing any unauthorized pushes from earlier in the sprint. For a 2-week sprint, this could miss 13 days of direct pushes.

**Evidence:** Line 387: `since = now.strftime("%Y-%m-%dT00:00:00Z")`. The fallback is only used when the milestone API query fails (line 388-401), but there's no warning that the detection window is artificially narrow.

**Acceptance Criteria:**
- [ ] When milestone `created_at` can't be determined, use a wider fallback (e.g., 14 days ago) instead of just today
- [ ] Emit a warning when using the fallback date, so the user knows detection coverage is reduced
- [ ] Test exists verifying the fallback date logic

**Validation Command:**
```bash
python -m pytest tests/test_gh_interactions.py -k "direct_push" -v && echo "PASS"
```

---

### P13-012: populate_issues.enrich_from_epics() sprint inference is opaque and fragile
**Severity:** MEDIUM
**Category:** `bug/logic`
**Location:** `skills/sprint-setup/scripts/populate_issues.py:231-240`
**Status:** 🔴 OPEN

**Problem:** The sprint inference logic in `enrich_from_epics()` uses a complex nested expression to find the "most common sprint among known stories, with ties broken by lowest number." If an epic file references stories from multiple sprints equally, the logic picks the lowest sprint number — but this is a semantic decision that isn't documented or tested. The one-liner at line 237-240 is difficult to read and could silently produce wrong results.

**Evidence:** Lines 237-240:
```python
sprint = min(
    (s for s in set(known_sprints)
     if known_sprints.count(s) == max(known_sprints.count(x) for x in set(known_sprints))),
) if known_sprints else 0
```

**Acceptance Criteria:**
- [ ] The sprint inference logic is extracted to a named helper function with a docstring explaining the tiebreaking behavior
- [ ] Test exists with an epic referencing stories from 2 sprints equally, verifying the lowest sprint is chosen
- [ ] Test exists with an epic referencing stories from 3 sprints with a clear winner, verifying the most common is chosen

**Validation Command:**
```bash
python -m pytest tests/test_pipeline_scripts.py -k "enrich" -v && echo "PASS"
```

---

### P13-013: No conftest.py — sys.path manipulation is fragile and duplicated
**Severity:** MEDIUM
**Category:** `design/duplication`
**Location:** Every test file (12 files)
**Status:** 🔴 OPEN

**Problem:** Every test file independently manipulates `sys.path` with `sys.path.insert(0, ...)` to import production code. This is duplicated across 12+ files, is fragile (import order matters), and can cause silent import shadowing if two modules have the same name. A single conftest.py could centralize path setup and fixtures.

**Evidence:** `grep -c 'sys.path.insert' tests/test_*.py` shows 2-5 insertions per file, totaling ~40 sys.path manipulations.

**Acceptance Criteria:**
- [ ] `tests/conftest.py` exists with shared path setup and common fixtures (FakeGitHub, MockProject, tmp_project)
- [ ] At least 6 of 12 test files remove their `sys.path.insert` calls in favor of conftest.py
- [ ] All tests still pass after migration

**Validation Command:**
```bash
test -f tests/conftest.py && python -m pytest tests/ -v && echo "PASS"
```

---

### P13-014: release_gate.gate_tests() doesn't catch TimeoutExpired
**Severity:** MEDIUM
**Category:** `bug/error-handling`
**Location:** `skills/sprint-release/scripts/release_gate.py:206-213`
**Status:** 🔴 OPEN
**Pattern:** PAT-003

**Problem:** `gate_tests()` passes `timeout=300` to `subprocess.run()`, but doesn't catch `subprocess.TimeoutExpired`. If a test command hangs for 5+ minutes, the function crashes with an unhandled exception instead of returning a clean `(False, "timed out")` tuple. This would propagate up through `validate_gates()` and crash the entire release flow.

**Evidence:** Line 208 passes `timeout=300` but the only error handling is checking `returncode != 0` (line 210-211). `subprocess.TimeoutExpired` is not in a try/except. Same issue exists in `gate_build()` at line 225.

**Acceptance Criteria:**
- [ ] `gate_tests()` catches `subprocess.TimeoutExpired` and returns `(False, f"'{cmd}' timed out after 300s")`
- [ ] `gate_build()` catches `subprocess.TimeoutExpired` similarly
- [ ] Test exists verifying both functions handle timeout correctly

**Validation Command:**
```bash
python -m pytest tests/test_release_gate.py -k "timeout" -v && echo "PASS"
```

---

### P13-015: sync_backlog.py architectural coupling to skill-specific scripts
**Severity:** MEDIUM
**Category:** `design/coupling`
**Location:** `scripts/sync_backlog.py:24,27-32`
**Status:** 🔴 OPEN

**Problem:** `sync_backlog.py` lives in the shared `scripts/` directory but imports `bootstrap_github` and `populate_issues` from `skills/sprint-setup/scripts/` via `sys.path.insert`. This creates an unexpected dependency from a shared utility to a specific skill's internals. If the sprint-setup skill is reorganized or the scripts are renamed, sync_backlog silently breaks. The dependency is also invisible in CLAUDE.md's architecture description.

**Evidence:** Lines 24, 27-32:
```python
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "skills" / "sprint-setup" / "scripts"))
import bootstrap_github
import populate_issues
```

**Acceptance Criteria:**
- [ ] The dependency is documented in CLAUDE.md's architecture section (at minimum)
- [ ] Consider moving the shared functions (`create_milestones_on_github`, `create_issue`, `parse_milestone_stories`) to a shared module in `scripts/` if they need to be called from outside sprint-setup

**Validation Command:**
```bash
grep -q "sync_backlog.*bootstrap_github\|sync_backlog.*populate_issues" CLAUDE.md && echo "DOCUMENTED"
```

---

### P13-016: No test for write_version_to_toml() with existing [release] section
**Severity:** MEDIUM
**Category:** `test/shallow`
**Location:** `skills/sprint-release/scripts/release_gate.py:275-308`
**Status:** 🔴 OPEN

**Problem:** `write_version_to_toml()` has 3 code paths: (1) [release] section exists with version key → replace, (2) [release] section exists without version → insert, (3) no [release] section → append. Only path (3) is tested in `test_lifecycle.py:test_10_version_written_to_toml`. Paths (1) and (2) are untested. If the regex for finding the existing version key is wrong, updates silently corrupt the TOML file.

**Evidence:** `grep -n 'write_version_to_toml' tests/` shows only one test calling this function, and it starts with a freshly generated TOML (no [release] section).

**Acceptance Criteria:**
- [ ] Test for path 1: TOML has `[release]\nversion = "0.1.0"`, calling `write_version_to_toml("0.2.0")` replaces it
- [ ] Test for path 2: TOML has `[release]` but no version key, calling `write_version_to_toml("0.2.0")` inserts it
- [ ] Test for edge case: TOML has `# [release]` comment, which should NOT be treated as a section header
- [ ] Test verifies other sections are not corrupted after version write

**Validation Command:**
```bash
python -m pytest tests/test_release_gate.py -k "write_version" -v && echo "PASS"
```

---

### P13-017: TOML parser doesn't handle \uXXXX unicode escapes
**Severity:** MEDIUM
**Category:** `bug/logic`
**Location:** `scripts/validate_config.py:233-254`
**Status:** 🔴 OPEN

**Problem:** `_unescape_toml_string()` handles `\n`, `\t`, `\\`, and `\"` but does NOT handle `\uXXXX` or `\UXXXXXXXX` unicode escapes, which are valid in TOML basic strings. A project.toml with `name = "caf\u00e9"` would produce the literal string `caf\u00e9` instead of `café`. While unlikely in a sprint config, this violates the TOML spec and could cause subtle bugs if a project name or path contains unicode.

**Evidence:** Lines 238-253 handle only 4 escape sequences. The TOML spec defines 8 (including `\u`, `\U`, `\b`, `\f`, `\r`).

**Acceptance Criteria:**
- [ ] `_unescape_toml_string()` handles `\uXXXX` (4-digit) and `\UXXXXXXXX` (8-digit) unicode escapes
- [ ] Test exists: `parse_simple_toml('name = "caf\\u00e9"')` returns `{"name": "café"}`
- [ ] OR: the function emits a warning for unrecognized escapes (current behavior silently passes them through)

**Validation Command:**
```bash
python -c "from scripts.validate_config import parse_simple_toml; assert parse_simple_toml('name = \"caf\\\\u00e9\"')['name'] == 'café'"
```

---

### P13-018: update_burndown.update_sprint_status() regex could match wrong section
**Severity:** MEDIUM
**Category:** `bug/logic`
**Location:** `skills/sprint-run/scripts/update_burndown.py:109`
**Status:** 🔴 OPEN

**Problem:** The regex pattern for finding the "Active Stories" section is complex and uses a non-obvious approach: `r"## Active Stories[^\n]*\n(?:(?!\n## )[^\n]*\n)*(?:(?!\n## )[^\n]+\n?)?"`. This negative lookahead pattern is fragile — it matches until the next `\n## ` boundary, but if the SPRINT-STATUS.md file has `## Active Stories` followed by content with no subsequent `## ` heading, the regex could match more than intended, or fail to match the final line if it doesn't end with a newline. No test verifies the regex against edge cases like trailing content without a trailing newline.

**Evidence:** Only one test exercises `update_sprint_status()` (in `test_lifecycle.py:test_14_monitoring_pipeline`), and it uses a simple status file with a trailing `## ` heading.

**Acceptance Criteria:**
- [ ] Test with SPRINT-STATUS.md where "Active Stories" is the LAST section (no following ## heading)
- [ ] Test with SPRINT-STATUS.md where the file doesn't end with a newline
- [ ] Test verifying replacement preserves content after the Active Stories section

**Validation Command:**
```bash
python -m pytest tests/ -k "sprint_status" -v && echo "PASS"
```

---

### P13-019: sprint_analytics.compute_review_rounds() uses --search which FakeGitHub partially implements
**Severity:** LOW
**Category:** `test/shallow`
**Location:** `scripts/sprint_analytics.py:83-88`
**Status:** 🔴 OPEN

**Problem:** `compute_review_rounds()` uses `--search milestone:"Sprint 1"` to filter PRs. FakeGitHub implements this with `_extract_search_milestone()`, which only handles the milestone pattern. If sprint_analytics adds other search predicates in the future, FakeGitHub would silently ignore them, creating false test passes.

**Evidence:** FakeGitHub comment at line 193: `# search: only milestone:"X" pattern is evaluated; other predicates are silently ignored`.

**Acceptance Criteria:**
- [ ] FakeGitHub emits a warning (or raises in strict mode) if `--search` contains predicates beyond `milestone:"X"`
- [ ] Test exists verifying `compute_review_rounds()` produces correct counts with FakeGitHub

**Validation Command:**
```bash
python -m pytest tests/test_sprint_analytics.py -k "review_rounds" -v && echo "PASS"
```

---

### P13-020: test_gh_interactions.py is 3,103 lines — too large for effective review
**Severity:** LOW
**Category:** `design/inconsistency`
**Location:** `tests/test_gh_interactions.py`
**Status:** 🔴 OPEN

**Problem:** At 3,103 lines and 30 touches in 100 commits, this is the highest-churn file in the project. It contains tests for sync_tracking, update_burndown, check_status, sprint_analytics, and bootstrap_github — responsibilities that should be in separate test files. The file's size makes code review difficult and increases merge conflict risk.

**Evidence:** Git churn analysis shows 30 touches in 100 commits. The file covers 5+ distinct modules.

**Acceptance Criteria:**
- [ ] File is split into at most 3 files, each covering related modules
- [ ] All 643 tests continue to pass after split
- [ ] No individual test file exceeds 1,500 lines

**Validation Command:**
```bash
wc -l tests/test_gh_interactions.py && python -m pytest tests/ -v
```

---

### P13-021: _parse_workflow_runs() doesn't handle YAML folded style (run: >)
**Severity:** LOW
**Category:** `bug/logic`
**Location:** `scripts/sprint_init.py:196-238`
**Status:** 🔴 OPEN

**Problem:** `_parse_workflow_runs()` only handles `run: |` (literal block style) for multiline commands. `run: >` and `run: >-` (folded styles) are silently ignored, meaning CI commands using these YAML styles won't be detected during project scanning. The function's docstring documents this limitation, but there's no test for it and no warning when it's encountered.

**Evidence:** Line 203 docstring: `Known limitation: run: > and run: >- (YAML folded style) are NOT detected`. No test verifies this behavior.

**Acceptance Criteria:**
- [ ] Test exists verifying `run: >` blocks are handled (either parsed or warned about)
- [ ] If not parsed: emit a warning so the user knows CI detection was incomplete
- [ ] If parsed: add folded style handling alongside literal style

**Validation Command:**
```bash
python -m pytest tests/ -k "workflow" -v && echo "PASS"
```

---

### P13-022: No test coverage metrics or enforcement
**Severity:** LOW
**Category:** `test/missing`
**Location:** Project-wide
**Status:** 🔴 OPEN

**Problem:** No code coverage tool is configured (pytest-cov, coverage.py). The project has 643 tests but no way to measure what percentage of production code they exercise. The `_KNOWN_UNTESTED` gate test is a manual approximation. Without coverage data, new code can be added without tests and no one would know.

**Evidence:** No `pytest-cov` in any config. No `.coveragerc`. No coverage reporting in CI template. `grep -r 'pytest.*cov\|coverage' pyproject.toml setup.cfg pytest.ini` returns nothing.

**Acceptance Criteria:**
- [ ] `pytest-cov` is added to dev dependencies
- [ ] `python -m pytest --cov=scripts --cov=skills --cov-report=term-missing` runs and produces output
- [ ] Coverage report shows which modules are below 80% line coverage

**Validation Command:**
```bash
python -m pytest tests/ --cov=scripts --cov-report=term-missing 2>&1 | tail -30
```

---

### P13-023: populate_issues._add_story closure captures loop variable
**Severity:** LOW
**Category:** `bug/logic`
**Location:** `skills/sprint-setup/scripts/populate_issues.py:105-117`
**Status:** 🔴 OPEN

**Problem:** `_add_story` is defined as a closure inside a for loop over milestone files. It captures `mf` (the loop variable) by reference. While the current code only uses `mf.name` in a warning message (so the impact is cosmetic), this is a classic Python closure bug pattern. If future code modifies `_add_story` to use `mf` for other purposes, the bug would silently emerge.

**Evidence:** Line 105-117: `def _add_story(row, sprint_num)` is defined inside `for mf_path in milestone_files:` and references `mf` from the outer scope.

**Acceptance Criteria:**
- [ ] `_add_story` is refactored to accept `mf` as a parameter instead of capturing it from the enclosing scope
- [ ] OR: the closure is documented with a comment explaining why it's safe in this specific case

**Validation Command:**
```bash
python -m pytest tests/ -k "milestone_stories" -v && echo "PASS"
```

---

### ~~P13-024: check_status.main() gate test may have a coverage blind spot~~
**Severity:** ~~LOW~~ → N/A (false positive)
**Category:** `test/bogus`
**Status:** ✅ RESOLVED

**Resolution:** `check_status.main()` is tested in `test_gh_interactions.py` (4 calls). The gate test is correct. The false positive in this audit was caused by the same issue flagged in P13-020: the 3,103-line test file is too large for manual review.
