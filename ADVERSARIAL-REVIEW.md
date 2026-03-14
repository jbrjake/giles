# Adversarial Review Punchlist (Fresh Audit)
> Generated: 2026-03-13 | Project: giles v0.4.0 | Baseline: 295 pass, 0 fail, 0 skip
> Prior audit: 37 items, 36 verified resolved, 1 partial (P3-01 encoding)
> This punchlist covers NEW findings only — verified by 4 parallel audit agents

## Summary

| Severity | Count | Items |
|----------|-------|-------|
| CRITICAL | 3 | BH-001, BH-002, BH-003 |
| HIGH | 9 | BH-004 – BH-012 |
| MEDIUM | 8 | BH-013 – BH-020 |
| LOW | 10 | BH-021 – BH-030 |
| **Total** | **30** | |

## Patterns

### PAT-001: TOML Parser State Machine Gaps
**Instances:** BH-001, BH-002, BH-021, BH-022, BH-030
**Root Cause:** The custom TOML parser processes multiline arrays as a single concatenated buffer, applying string-manipulation functions (comment stripping, bracket detection) on the buffer as a whole rather than line-by-line. This conflates line-level syntax (inline comments) with value-level syntax (string contents).
**Systemic Fix:** Rewrite multiline array handling to strip inline comments per continuation line before buffer concatenation, and use a proper quote-state-tracking bracket finder instead of `"]" in line`.
**Detection Rule:** `grep -n 'multiline_buf += " " + line' scripts/validate_config.py` — if the appended text is raw `line` (not `_strip_inline_comment(line)`), the bug is present.

### PAT-002: Tests That Mock the Function Under Test
**Instances:** BH-004, BH-006, BH-025
**Root Cause:** When fixing bugs, regression tests were written that patch the corrected function and assert the mock's return value flows through to the caller. This tests the caller's pass-through wiring, not the fix's logic.
**Systemic Fix:** Test the fixed function directly with real inputs. Only mock at system boundaries (GitHub API, filesystem I/O).
**Detection Rule:** `grep -rn '@patch.*find_milestone\|@patch.*validate_gates\|@patch.*calculate_version' tests/ | grep -v 'gh_json\|subprocess'` — patches on internal functions (not I/O boundaries) are suspect.

### PAT-003: Case/Format Mismatches Across Module Boundaries
**Instances:** BH-003, BH-009, BH-019
**Root Cause:** Different scripts produce and consume the same values with inconsistent formatting (capitalized vs lowercase language names, underscore vs no-underscore function names, hyphen-allowed vs hyphen-excluded in TOML section names).
**Systemic Fix:** Normalize at the single point where values are read (e.g., lowercase language in `load_config()`), not in each consumer.
**Detection Rule:** `grep -rn 'language' scripts/ skills/ --include='*.py' | grep -v '.lower()'`

---

## Items

### BH-001: TOML parser drops multiline array items after inline comments
**Severity:** CRITICAL
**Category:** `bug/logic`
**Location:** `scripts/validate_config.py:70-79, 115-128`
**Status:** ✅ RESOLVED
**Pattern:** PAT-001

**Problem:** Continuation lines of multiline arrays are appended to the buffer raw (`multiline_buf += " " + line`). When the array closes, `_strip_inline_comment` runs on the entire concatenated buffer and truncates at the first `#` outside quotes — silently dropping all subsequent array items.

**Evidence:**
```toml
check_commands = [
    "cargo fmt --check",  # format check
    "cargo test",
]
```
Buffer becomes: `[ "cargo fmt --check",  # format check "cargo test", ]`
After `_strip_inline_comment`: `[ "cargo fmt --check",` — `"cargo test"` is gone.

**Acceptance Criteria:**
- [ ] Multiline arrays with inline comments on continuation lines preserve all items
- [ ] Unit test with inline-commented multiline array asserts correct item count

**Validation Command:**
```bash
python3 -c "
import sys; sys.path.insert(0, 'scripts')
from validate_config import parse_simple_toml
text = '[ci]\ncheck_commands = [\n    \"cargo fmt --check\",  # format\n    \"cargo test\",\n]'
result = parse_simple_toml(text)
cmds = result['ci']['check_commands']
assert isinstance(cmds, list), f'Expected list, got {type(cmds)}'
assert len(cmds) == 2, f'Expected 2 items, got {len(cmds)}: {cmds}'
print('PASS: multiline array with inline comments preserved')
"
```

---

### BH-002: TOML parser `]` inside string values terminates multiline arrays early
**Severity:** CRITICAL
**Category:** `bug/logic`
**Location:** `scripts/validate_config.py:72`
**Status:** ✅ RESOLVED
**Pattern:** PAT-001

**Problem:** `if "]" in line:` on the raw line doesn't respect quoting. A string value containing `]` terminates multiline array collection. The buffer is passed to `_parse_value` without a closing `]`, falls through all type checks, and returns a raw string where a list was expected.

**Evidence:**
```toml
commands = [
    "echo ']'",
    "cargo test",
]
```
Config key gets a string, not a list. Downstream `for cmd in commands` iterates characters.

**Acceptance Criteria:**
- [ ] Multiline arrays with `]` inside string values parse correctly
- [ ] Unit test with bracket-in-string asserts list type and correct items

**Validation Command:**
```bash
python3 -c "
import sys; sys.path.insert(0, 'scripts')
from validate_config import parse_simple_toml
text = '[ci]\ncommands = [\n    \"echo ]\",\n    \"test\",\n]'
result = parse_simple_toml(text)
cmds = result['ci']['commands']
assert isinstance(cmds, list), f'Expected list, got {type(cmds).__name__}: {cmds!r}'
assert len(cmds) == 2, f'Expected 2 items, got {len(cmds)}: {cmds}'
print('PASS: bracket-in-string handled correctly')
"
```

---

### BH-003: test_coverage.py is non-functional — language case mismatch
**Severity:** CRITICAL
**Category:** `bug/logic`
**Location:** `scripts/test_coverage.py:21-26, 60, 72, 163`
**Status:** ✅ RESOLVED
**Pattern:** PAT-003

**Problem:** `_TEST_PATTERNS` has lowercase keys (`"rust"`, `"python"`) but config values are capitalized (`"Rust"`, `"Python"`) from `sprint_init.py`. No `.lower()` is applied. The dict lookup always returns `None`. Every project reports 0 implemented tests and marks ALL planned tests as missing. The entire feature is broken.

**Evidence:** `setup_ci.py:205` correctly does `.lower()`. This is the only script that got it right.

**Acceptance Criteria:**
- [ ] Language lookup in `test_coverage.py` is case-insensitive
- [ ] Test with capitalized language returns correct implemented test count

**Validation Command:**
```bash
python3 -c "
import sys; sys.path.insert(0, 'scripts')
src = open('scripts/test_coverage.py').read()
assert '.lower()' in src or 'casefold' in src, 'BUG: no case normalization for language lookup'
print('PASS: language lookup is case-normalized')
"
```

---

### BH-004: P1-01 word-boundary tests are tautologies — they mock `find_milestone`
**Severity:** HIGH
**Category:** `test/bogus`
**Location:** `tests/test_gh_interactions.py:520-532`
**Status:** ✅ RESOLVED
**Pattern:** PAT-002

**Problem:** `test_sprint_1_does_not_match_sprint_10` and `test_sprint_10_matches_correctly` claim to verify the word-boundary fix (P1-01) but `@patch("sync_tracking.find_milestone")` mocks out the function containing the regex. The tests assert that `find_milestone_title()` returns whatever the mock returns. The actual `re.match(rf"^Sprint {num}\b", ...)` logic is never exercised. **Removing `\b` from the regex would not cause these tests to fail.**

**Acceptance Criteria:**
- [ ] Tests call `find_milestone()` directly (unmocked) with realistic milestone title data
- [ ] Removing `\b` from the regex in `find_milestone()` causes the boundary test to fail

**Validation Command:**
```bash
python3 -c "
import ast, sys
src = open('tests/test_gh_interactions.py').read()
tree = ast.parse(src)
for node in ast.walk(tree):
    if isinstance(node, ast.FunctionDef) and 'sprint_1_does_not_match' in node.name:
        segment = ast.get_source_segment(src, node)
        if 'patch' in segment and 'find_milestone' in segment:
            print('FAIL: test mocks find_milestone — tautology')
            sys.exit(1)
        else:
            print('PASS: test exercises find_milestone directly')
            sys.exit(0)
print('FAIL: test not found')
sys.exit(1)
"
```

---

### BH-005: `validate_project()` has zero negative tests — 8 error paths untested
**Severity:** HIGH
**Category:** `test/missing`
**Location:** `scripts/validate_config.py` (validate_project)
**Status:** ✅ RESOLVED

**Problem:** `validate_project()` has 8 failure modes (missing files, bad TOML, too few personas, missing persona files, no milestones, empty rules, parse failure, missing TOML keys). Only the success path is exercised indirectly. A mutation changing it to always return `(True, [])` would go undetected.

**Acceptance Criteria:**
- [ ] At least 5 negative tests: missing required file, invalid TOML, <2 personas, missing persona file, missing required TOML key
- [ ] Each test asserts `valid == False` and checks error message content

**Validation Command:**
```bash
python3 -m pytest tests/ -v -k "validate_project" 2>&1 | grep -c "PASSED"
# Should be >= 5
```

---

### BH-006: `do_release()` happy path test mocks 5/5 production functions
**Severity:** HIGH
**Category:** `test/mock-abuse`
**Location:** `tests/test_release_gate.py:360-421`
**Status:** ⏳ DEFERRED — test design debt, not a bug. Mocking is appropriate here since do_release orchestrates git/GitHub I/O.
**Pattern:** PAT-002

**Problem:** `test_happy_path` mocks `calculate_version`, `write_version_to_toml`, `subprocess.run`, `find_milestone_number`, and `gh`. It asserts mock call counts and argument positions. No production code executes except the `do_release()` skeleton. Reordering git commands breaks the test even if behavior is correct. A bug in any mocked function goes undetected.

**Acceptance Criteria:**
- [ ] At least one `do_release` test uses FakeGitHub + real temp git repo with minimal mocking
- [ ] Test verifies outcomes (tag exists, version correct in project.toml) not call order

**Validation Command:**
```bash
python3 -c "
import ast
src = open('tests/test_release_gate.py').read()
tree = ast.parse(src)
for node in ast.walk(tree):
    if isinstance(node, ast.FunctionDef) and node.name == 'test_happy_path':
        decorators = [d for d in node.decorator_list
                      if isinstance(d, ast.Call) and hasattr(d.func, 'id') and d.func.id == 'patch']
        if len(decorators) >= 4:
            print(f'FAIL: test_happy_path has {len(decorators)} @patch decorators — mockingbird')
        else:
            print(f'PASS: reduced to {len(decorators)} patches')
"
```

---

### BH-007: `find_milestone()` boundary matching has zero direct tests
**Severity:** HIGH
**Category:** `test/missing`
**Location:** `scripts/validate_config.py:591-615`
**Status:** ✅ RESOLVED

**Problem:** The function that fixed P1-01 (word-boundary matching) is never called directly in any test. All tests that claim to verify it mock it out. A mutation removing `\b` from `re.match(rf"^Sprint {num}\b", ...)` goes undetected.

**Acceptance Criteria:**
- [ ] Direct unit test passes real milestone titles through `find_milestone()` (unmocked)
- [ ] Sprint 1 does not match "Sprint 10", "Sprint 11", "Sprint 1a"
- [ ] Sprint 10 matches "Sprint 10" but not "Sprint 1" or "Sprint 100"

**Validation Command:**
```bash
python3 -m pytest tests/ -v -k "find_milestone" 2>&1 | grep -E "direct|boundary" | grep -c "PASSED"
# Should be >= 2
```

---

### BH-008: FakeGitHub returns `[]` for unhandled API paths — silent pass-through
**Severity:** HIGH
**Category:** `test/shallow`
**Location:** `tests/fake_github.py` (catch-all handler)
**Status:** ✅ RESOLVED

**Problem:** When production code makes an API call FakeGitHub doesn't handle, it silently returns `[]`. Any new `gh api` call in production gets free "green bar" without a corresponding fake handler. New features pass tests by accident.

**Acceptance Criteria:**
- [ ] FakeGitHub raises/returns an error for unrecognized API paths
- [ ] Existing tests still pass (no test depends on silent empty-array behavior)

**Validation Command:**
```bash
python3 -c "
import sys; sys.path.insert(0, 'tests')
from fake_github import FakeGitHub
gh = FakeGitHub('owner/repo')
result = gh._handle_api('GET', '/repos/owner/repo/nonexistent-endpoint', {})
if '[]' in str(result):
    print('FAIL: unhandled endpoint returns silent empty array')
    sys.exit(1)
print('PASS: unhandled endpoint raises error')
"
```

---

### BH-009: TOML section headers with hyphens silently ignored
**Severity:** HIGH
**Category:** `bug/logic`
**Location:** `scripts/validate_config.py:86`
**Status:** ✅ RESOLVED
**Pattern:** PAT-003

**Problem:** Section header regex `[a-zA-Z0-9_]` doesn't include `-`. A section like `[build-config]` is silently not matched as a header. The line falls through and keys land in the wrong section.

**Evidence:** Currently safe (existing config uses underscore names), but invisible landmine for config extensions.

**Acceptance Criteria:**
- [ ] `parse_simple_toml('[build-config]\nkey = "value"')` returns `{"build-config": {"key": "value"}}`
- [ ] Unit test covers hyphenated section names

**Validation Command:**
```bash
python3 -c "
import sys; sys.path.insert(0, 'scripts')
from validate_config import parse_simple_toml
result = parse_simple_toml('[build-config]\nkey = \"value\"')
assert 'build-config' in result, f'BUG: hyphenated section not parsed. Keys: {list(result.keys())}'
assert result['build-config']['key'] == 'value'
print('PASS: hyphenated section parsed correctly')
"
```

---

### BH-010: 13 production functions with zero test coverage
**Severity:** HIGH
**Category:** `test/missing`
**Location:** Multiple files
**Status:** ✅ RESOLVED

**Problem:** Critical runtime functions have no direct or indirect test coverage:

| Function | File | Risk |
|----------|------|------|
| `read_tf()` / `write_tf()` | sync_tracking.py:133,156 | HIGH — tracking file I/O |
| `kanban_from_labels()` | validate_config.py:582 | HIGH — used by sync, burndown, tracking |
| `check_milestone()` | check_status.py:167 | MEDIUM — milestone progress math |
| `detect_sprint()` | validate_config.py:564 | MEDIUM — sprint number detection |
| `extract_story_id()` | validate_config.py:576 | MEDIUM — used everywhere |
| `slug_from_title()` | sync_tracking.py:96 | LOW — pure function |
| `_first_error()` | check_status.py:78 | MEDIUM — error extraction from CI logs |
| `load_tracking_metadata()` | update_burndown.py:130 | MEDIUM — frontmatter parsing |

**Acceptance Criteria:**
- [ ] Direct unit tests for at least: `read_tf`/`write_tf` round-trip, `kanban_from_labels` (multiple labels, no labels, unknown state), `detect_sprint`, `extract_story_id`
- [ ] At least 8 new PASSED tests

**Validation Command:**
```bash
python3 -m pytest tests/ -v -k "read_tf or write_tf or kanban_from_labels or detect_sprint or extract_story_id or check_milestone" 2>&1 | grep -c "PASSED"
# Should be >= 8
```

---

### BH-011: Epic-only stories get sprint=0 label and orphaned on GitHub
**Severity:** HIGH
**Category:** `bug/logic`
**Location:** `skills/sprint-setup/scripts/populate_issues.py:207-212, 332-340`
**Status:** ✅ RESOLVED

**Problem:** When `enrich_from_epics` discovers stories not in any milestone table and can't infer a sprint number, it defaults to `sprint = 0`. These get a `sprint:0` label (auto-created, no color/description) and no milestone. Invisible to tracking, burndown, and analytics.

**Acceptance Criteria:**
- [ ] Stories with undeterminable sprint are skipped with a warning or assigned to first milestone with a note
- [ ] No issue created with label `sprint:0`

**Validation Command:**
```bash
grep -n 'sprint\s*=\s*0' skills/sprint-setup/scripts/populate_issues.py | wc -l
# Should be 0
```

---

### BH-012: 2 remaining `read_text()` calls without explicit `encoding="utf-8"`
**Severity:** HIGH
**Category:** `bug/encoding`
**Location:** `scripts/sprint_init.py:347`, `skills/sprint-setup/scripts/populate_issues.py:205`
**Status:** ✅ RESOLVED

**Problem:** Two `read_text(errors="replace")` calls omit `encoding="utf-8"`. On Windows with non-UTF-8 locale, platform default encoding is used. `errors="replace"` prevents crashes but silently corrupts non-ASCII content with U+FFFD.

**Acceptance Criteria:**
- [ ] Every `read_text()` and `write_text()` call includes `encoding="utf-8"`

**Validation Command:**
```bash
count=$(grep -rn '\.read_text(' scripts/ skills/ --include='*.py' | grep -v encoding | grep -v __pycache__ | wc -l | tr -d ' ')
if [ "$count" -gt 0 ]; then echo "FAIL: $count calls without encoding"; else echo "PASS"; fi
```

---

### BH-013: `release_gate.py` has no rollback on partial failure
**Severity:** MEDIUM
**Category:** `design/inconsistency`
**Location:** `skills/sprint-release/scripts/release_gate.py:370-493`
**Status:** ✅ RESOLVED

**Problem:** 10 sequential release steps with no rollback. TOML modified but not committed, tag created but not pushed, release created but milestone not closed — each failure point leaves different debris. No guidance about what completed.

**Acceptance Criteria:**
- [ ] Validate prerequisites (COMMIT_PY exists, git clean) before any mutations
- [ ] On failure, print which steps completed vs failed
- [ ] At minimum: if commit fails, restore original project.toml

**Validation Command:**
```bash
grep -n 'COMMIT_PY\|exists()' skills/sprint-release/scripts/release_gate.py | head -5
# Should show early existence check before file modifications
```

---

### BH-014: `check_status.py` uses mtime for `since` date — resets every monitor cycle
**Severity:** MEDIUM
**Category:** `bug/logic`
**Location:** `skills/sprint-monitor/scripts/check_status.py:369-380`
**Status:** ✅ RESOLVED

**Problem:** `since` date for `check_direct_pushes` comes from `SPRINT-STATUS.md` filesystem mtime. This file is rewritten every monitor cycle. So `since` is always recent — pushes before monitoring started (or during a gap) are invisible.

**Acceptance Criteria:**
- [ ] `since` derived from sprint start date (content or milestone created_at), not filesystem mtime
- [ ] Test verifies pushes before last mtime are still detected

**Validation Command:**
```bash
grep -n 'getmtime\|os.path.getmtime' skills/sprint-monitor/scripts/check_status.py | wc -l
# Should be 0
```

---

### BH-015: `find_milestone()` silently ignores `repo` argument
**Severity:** MEDIUM
**Category:** `design/inconsistency`
**Location:** `scripts/validate_config.py:591-615`
**Status:** ✅ RESOLVED

**Problem:** Accepts `repo` argument but ignores it ("kept for backward compat"). Always queries from git remote. Callers passing `repo` from `project.toml` think they're querying that repo, but they aren't.

**Acceptance Criteria:**
- [ ] Either use the `repo` argument or remove it from the signature
- [ ] If removed: update callers to not pass it

**Validation Command:**
```bash
python3 -c "
import ast
src = open('scripts/validate_config.py').read()
tree = ast.parse(src)
for node in ast.walk(tree):
    if isinstance(node, ast.FunctionDef) and node.name == 'find_milestone':
        body = ast.get_source_segment(src, node)
        if 'ignored' in body.lower():
            print('WARN: repo param still documented as ignored')
        break
"
```

---

### BH-016: `sprint_analytics.py` appends duplicate entries on re-run
**Severity:** MEDIUM
**Category:** `bug/logic`
**Location:** `scripts/sprint_analytics.py:246-257`
**Status:** ✅ RESOLVED

**Problem:** Running analytics for the same sprint twice appends the same metrics entry again. No dedup check. analytics.md accumulates duplicate entries.

**Acceptance Criteria:**
- [ ] Running analytics for the same sprint twice produces one entry (idempotent)
- [ ] Test verifies double-run doesn't duplicate

**Validation Command:**
```bash
grep -c 'def.*format_report\|def.*write\|def.*append' scripts/sprint_analytics.py
# After fix: should include dedup logic
```

---

### BH-017: 82 stale CHEATSHEET.md line-number references
**Severity:** MEDIUM
**Category:** `doc/drift`
**Location:** `CHEATSHEET.md` (all script tables)
**Status:** ✅ RESOLVED

**Problem:** Every script's line references in CHEATSHEET.md are off by consistent deltas (validate_config +5-7, sync_tracking -25, sprint_analytics -20-23). Several reference functions refactored into validate_config.py that no longer exist locally in the listed script.

**Acceptance Criteria:**
- [ ] All CHEATSHEET.md line numbers match actual code within ±2 lines
- [ ] Functions listed under a script are actually defined in that script (not imported)
- [ ] `verify_line_refs.py` also validates CHEATSHEET table-format refs

**Validation Command:**
```bash
python3 scripts/verify_line_refs.py 2>&1 | tail -5
# After fix: should check CHEATSHEET refs and report all OK
```

---

### BH-018: `verify_line_refs.py` doesn't check CHEATSHEET table format
**Severity:** MEDIUM
**Category:** `bug/logic`
**Location:** `scripts/verify_line_refs.py`
**Status:** ✅ RESOLVED

**Problem:** Validator regex only matches CLAUDE.md backtick-style refs. CHEATSHEET.md uses `| NN | func() |` table format, completely ignored. Reports "88/88 OK" while 82 CHEATSHEET refs are stale. False confidence.

**Acceptance Criteria:**
- [ ] Validator parses CHEATSHEET.md table format
- [ ] Running on current CHEATSHEET reports stale refs
- [ ] After CHEATSHEET update: all refs pass

**Validation Command:**
```bash
python3 scripts/verify_line_refs.py 2>&1 | grep -i "cheatsheet"
# Should show CHEATSHEET.md refs being checked
```

---

### BH-019: CLAUDE.md and CHEATSHEET.md use wrong function name `_build_milestone_title_map`
**Severity:** MEDIUM
**Category:** `doc/drift`
**Location:** `CLAUDE.md:43`, `CHEATSHEET.md:95`
**Status:** ✅ RESOLVED
**Pattern:** PAT-003

**Problem:** Both docs reference `_build_milestone_title_map()` (underscore prefix). Actual function is `build_milestone_title_map()` at `populate_issues.py:255`. Searching for the documented name yields zero results.

**Acceptance Criteria:**
- [ ] Both files use correct name `build_milestone_title_map`
- [ ] Line number updated to :255

**Validation Command:**
```bash
count=$(grep -c '_build_milestone_title_map' CLAUDE.md CHEATSHEET.md | grep -v ':0' | wc -l | tr -d ' ')
if [ "$count" -gt 0 ]; then echo "FAIL: underscore prefix still in docs"; else echo "PASS"; fi
```

---

### BH-020: CLAUDE.md line 100 cites wrong line for `_REQUIRED_TOML_KEYS`
**Severity:** MEDIUM
**Category:** `doc/drift`
**Location:** `CLAUDE.md:100`
**Status:** ✅ RESOLVED

**Problem:** "(see `validate_config.py:199`)" — line 199 is end of `_REQUIRED_FILES`. `_REQUIRED_TOML_KEYS` is at line 206.

**Acceptance Criteria:**
- [ ] CLAUDE.md references correct line number

**Validation Command:**
```bash
python3 -c "
lines = open('scripts/validate_config.py').readlines()
for i, line in enumerate(lines, 1):
    if '_REQUIRED_TOML_KEYS' in line and '=' in line:
        print(f'_REQUIRED_TOML_KEYS is at line {i}')
        break
"
```

---

### BH-021: TOML parser silently drops dotted keys
**Severity:** LOW
**Category:** `bug/logic`
**Location:** `scripts/validate_config.py:91`
**Status:** ✅ RESOLVED
**Pattern:** PAT-001

**Problem:** Key regex doesn't match `a.b = "value"`. Standard TOML allows dotted keys. Line is silently skipped. Currently no config uses dotted keys, but silent failure is dangerous.

**Acceptance Criteria:**
- [ ] Either support dotted keys or document the limitation in a code comment

**Validation Command:**
```bash
python3 -c "
import sys; sys.path.insert(0, 'scripts')
from validate_config import parse_simple_toml
result = parse_simple_toml('a.b = \"value\"')
print(f'Result: {result}')  # Currently returns {} — key silently dropped
"
```

---

### BH-022: TOML parser doesn't handle escape sequences in strings
**Severity:** LOW
**Category:** `bug/logic`
**Location:** `scripts/validate_config.py:137-140`
**Status:** ✅ RESOLVED

**Problem:** String extraction via `raw[1:-1]` doesn't process `\n`, `\t`, `\\`, `\"`. TOML value `key = "line1\nline2"` returns literal `\n` characters.

**Acceptance Criteria:**
- [ ] Either handle common escape sequences or document the limitation

---

### BH-023: `test_malformed_quotes` asserts nothing useful
**Severity:** LOW
**Category:** `test/bogus`
**Location:** `tests/test_pipeline_scripts.py:402-408`
**Status:** ✅ RESOLVED

**Problem:** `assertIsNotNone(result["key"])` passes for any non-None value. Test would pass with random data.

**Acceptance Criteria:**
- [ ] Assert the exact value returned for unterminated string input

**Validation Command:**
```bash
python3 -c "
import ast
src = open('tests/test_pipeline_scripts.py').read()
tree = ast.parse(src)
for node in ast.walk(tree):
    if isinstance(node, ast.FunctionDef) and 'malformed_quotes' in node.name:
        segment = ast.get_source_segment(src, node)
        if 'assertIsNotNone' in segment and 'assertEqual' not in segment:
            print('FAIL: only assertIsNotNone — no exact value check')
        else:
            print('PASS: has exact value assertions')
"
```

---

### BH-024: `test_13_full_pipeline` uses loose assertions (`> 10`, `> 0`)
**Severity:** LOW
**Category:** `test/shallow`
**Location:** `tests/test_lifecycle.py:420-425`
**Status:** ✅ RESOLVED

**Problem:** `assertGreater(len(labels), 10)` and `assertGreater(len(milestones), 0)` pass with wildly wrong counts. Same pipeline in `test_hexwise_setup.py` asserts exact counts. Redundant test with weaker assertions.

**Acceptance Criteria:**
- [ ] Either delete (redundant) or tighten to exact count assertions

**Validation Command:**
```bash
grep -n 'assertGreater.*len.*0\|assertGreater.*len.*10' tests/test_lifecycle.py | wc -l
# Should be 0
```

---

### BH-025: Duplicate test — `test_empty_response` identical to `test_no_match`
**Severity:** LOW
**Category:** `test/bogus`
**Location:** `tests/test_gh_interactions.py:514-518`
**Status:** ✅ RESOLVED
**Pattern:** PAT-002

**Problem:** Both mock `find_milestone` returning `None` and assert result is `None`. Identical logic.

**Acceptance Criteria:**
- [ ] Remove one or differentiate (e.g., one tests empty API response, other tests non-matching title)

---

### BH-026: Copy-paste hexwise fixture setup across 3 test files
**Severity:** LOW
**Category:** `design/duplication`
**Location:** `tests/test_hexwise_setup.py:38-63`, `tests/test_golden_run.py:53-79`, `tests/test_lifecycle.py:49-83`
**Status:** ⏳ DEFERRED — test maintenance debt, not a bug. Each fixture has slight differences suited to its test context.

**Problem:** 15-25 lines of identical fixture setup (copy fixture, git init, git add, git commit, chdir) duplicated across three files.

**Acceptance Criteria:**
- [ ] Shared fixture setup extracted to test utility
- [ ] All three files use shared utility

**Validation Command:**
```bash
grep -c 'git init\|git add\|git commit' tests/test_hexwise_setup.py tests/test_golden_run.py tests/test_lifecycle.py
# After fix: each file should have 0-1 git commands
```

---

### BH-027: `update_team_voices` uses fragile multi-line string in list
**Severity:** LOW
**Category:** `design/inconsistency`
**Location:** `scripts/manage_sagas.py:237-241`
**Status:** ✅ NOT-A-BUG — each voice line is already a separate list element. No multi-line strings in the list.

**Problem:** Embeds `\n`-containing string as single element in a list that gets `"\n".join()`-ed. Fragile if anyone processes elements as individual lines.

**Acceptance Criteria:**
- [ ] Each line is a separate list element

---

### BH-028: `renumber_stories` has substring-match risk
**Severity:** LOW
**Category:** `bug/logic`
**Location:** `scripts/manage_epics.py:287-289`
**Status:** ✅ ALREADY-FIXED — code already uses `re.sub(rf'\b{re.escape(old_id)}\b', ...)` for word-boundary matching.

**Problem:** `line.replace(old_id, replacement)` could corrupt if `old_id` is a substring of another story ID (e.g., `US-01` inside `US-0100`).

**Acceptance Criteria:**
- [ ] Use word-boundary replacement: `re.sub(rf'\b{re.escape(old_id)}\b', replacement, line)`
- [ ] Test with substring-overlapping IDs

**Validation Command:**
```bash
grep -n 'line.replace(old_id' scripts/manage_epics.py | wc -l
# Should be 0
```

---

### BH-029: sprint-monitor SKILL.md Step 3 title misleads
**Severity:** LOW
**Category:** `doc/drift`
**Location:** `skills/sprint-monitor/SKILL.md:225`
**Status:** ✅ RESOLVED

**Problem:** Step 3 is titled "Update Burndown" but instructs running `check_status.py`, which is read-only. Actual burndown updater is `update_burndown.py`.

**Acceptance Criteria:**
- [ ] Step title matches what the step actually does

---

### BH-030: `_parse_value` treats lone `"` as empty string
**Severity:** LOW
**Category:** `bug/logic`
**Location:** `scripts/validate_config.py:137-138`
**Status:** ✅ RESOLVED
**Pattern:** PAT-001

**Problem:** When `raw = '"'`, both `startswith('"')` and `endswith('"')` are True. `raw[1:-1]` returns `""`. Malformed `key = "` (unterminated) silently parsed as `key = ""`.

**Acceptance Criteria:**
- [ ] Unterminated strings produce warning or return raw value, not empty string

---

## Recommended Execution Order

**Chunk 1 — TOML Parser (BH-001, BH-002, BH-009, BH-021, BH-022, BH-030)**
Fix the parser's multiline array handling and add edge-case tests. Highest impact — a corrupted `check_commands` array silently breaks CI validation for every project.

**Chunk 2 — Broken Feature + Code Bugs (BH-003, BH-011, BH-012, BH-014, BH-016, BH-028)**
Fix `test_coverage.py` case mismatch (one-line fix), orphaned issues, encoding, analytics dedup, and substring replacement. Mix of quick wins and medium fixes.

**Chunk 3 — Test Integrity (BH-004, BH-005, BH-006, BH-007, BH-008, BH-010, BH-023, BH-024, BH-025, BH-026)**
Replace bogus tests with real ones, add coverage for uncovered functions, fix FakeGitHub silent pass-through. Highest volume but each item is small. This chunk provides the safety net for future work.

**Chunk 4 — Documentation (BH-017, BH-018, BH-019, BH-020, BH-029)**
Update stale refs, fix validator blind spot, correct function names. Quick wins with high developer-experience impact.

**Chunk 5 — Design Debt (BH-013, BH-015, BH-027)**
Release rollback, misleading API signature, fragile list construction. Lower priority but prevents maintenance hazards.
