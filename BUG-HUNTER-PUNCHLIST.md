# Bug Hunter Punchlist — Pass 21 (Adversarial Legacy Review)

> Generated: 2026-03-16 | Project: giles | Baseline: 773 pass, 0 fail, 0 skip | Coverage: 85%
> Method: 10 parallel audit agents — project structure, test infra, test baseline, churn, skipped tests, test quality, code logic, doc consistency, FakeGitHub fidelity, duplication/dead code

## Summary

| Severity | Open | Resolved | Deferred |
|----------|------|----------|----------|
| CRITICAL | 0    | 3        | 0        |
| HIGH     | 0    | 8        | 0        |
| MEDIUM   | 1    | 10       | 0        |
| LOW      | 4    | 2        | 0        |

## Patterns

### Pattern: PAT-001: Hand-rolled parsers churn forever
**Instances:** BH21-003, BH21-004, BH21-005
**Root Cause:** Custom TOML parser and YAML emitter try to handle a real format spec with regex+loops. Every new edge case reveals another gap. 22 fix commits for validate_config.py in 50 commits.
**Systemic Fix:** Either (a) replace parse_simple_toml with tomllib (Python 3.11+) or a vendored parser, or (b) property-test the remaining surface exhaustively and freeze the spec to "subset of TOML we support."
**Detection Rule:** `grep -rn 'splitlines\|parse_simple_toml\|_yaml_safe' scripts/ skills/`

### Pattern: PAT-002: Duplicated business logic diverges silently
**Instances:** BH21-012, BH21-013, BH21-014, BH21-015, BH21-016
**Root Cause:** Multiple scripts independently implement the same parsing/extraction logic with inline code rather than calling shared helpers.
**Systemic Fix:** Extract to shared functions in validate_config.py. The pattern was partially followed (BH18-005 created frontmatter_value, BH18-012 created parse_header_table) but wasn't applied consistently.
**Detection Rule:** `grep -rn 'kanban_from_labels.*closed\|split.*:.*1.*-1.*strip\|_collect_sprint_numbers\|_infer_sprint' scripts/ skills/`

### Pattern: PAT-003: Tests pass without exercising the code path they claim to cover
**Instances:** BH21-001, BH21-002, BH21-007, BH21-008, BH21-009
**Root Cause:** Mock-return-value testing, jq fallback degradation, and unittest discover vs pytest incompatibility create tests that appear green but don't verify real behavior.
**Systemic Fix:** (a) Switch CI test runner to pytest, (b) make jq a required dev dep, (c) use MonitoredMock pattern more widely.
**Detection Rule:** `grep -rn 'mock.*return_value.*=.*\n.*assertEqual.*mock' tests/`

---

## Items

### BH21-001: 26 property tests invisible to CI — unittest discover can't find pytest-style classes
**Severity:** CRITICAL
**Category:** `test/bogus`
**Location:** `tests/test_property_parsing.py:37-498` + `Makefile:13`
**Status:** 🔴 OPEN
**Pattern:** PAT-003

**Problem:** All 5 test classes in test_property_parsing.py use bare pytest-style classes (no `unittest.TestCase` inheritance). The CI Makefile runs `python -m unittest discover`, which only finds TestCase subclasses. 26 hypothesis tests (covering the 5 most bug-prone parsing functions, running ~7,200 examples total) are completely invisible to CI. These tests have historically found real bugs (BH20-001 U+2028 crash was discovered by hypothesis).

**Evidence:**
```
$ grep -n 'class Test' tests/test_property_parsing.py
37:class TestExtractStoryId:
102:class TestExtractSp:
173:class TestYamlSafe:
293:class TestParseSimpleToml:
454:class TestParseTeamIndexProperties:
```
None inherit from unittest.TestCase. Makefile uses `python -m unittest discover`.

**Acceptance Criteria:**
- [ ] CI runs pytest (not unittest discover) OR test classes inherit from TestCase
- [ ] `make test` exit code reflects hypothesis test results
- [ ] A failing hypothesis test causes CI to fail (verified by temporarily breaking a property)

**Validation Command:**
```bash
python -m unittest discover -s tests -v 2>&1 | grep -c "test_property_parsing"
# Should be >0 after fix. Currently 0.
```

---

### BH21-002: jq Python package not enforced in CI — FakeGitHub silently degrades all jq-dependent tests
**Severity:** CRITICAL
**Category:** `test/bogus`
**Location:** `tests/fake_github.py:120-133`, `requirements-dev.txt`
**Status:** 🔴 OPEN
**Pattern:** PAT-003

**Problem:** When the `jq` Python package is absent, FakeGitHub's `_maybe_apply_jq()` returns unfiltered data. Tests pass but don't verify jq expression correctness. One explicit skipTest guard exists (`test_sprint_runtime.py:1193`), but all other jq-dependent code paths silently degrade. `jq` IS listed in requirements-dev.txt, but the Makefile `venv` target doesn't install it, and CI doesn't verify it's available.

**Evidence:** `requirements-dev.txt` lists `jq>=1.11`. But `fake_github.py:120-133` returns unfiltered data on `_check_jq()` failure with no test failure. The `check_direct_pushes` jq filter reshaping is never verified without the package.

**Acceptance Criteria:**
- [ ] CI installs `jq` from requirements-dev.txt before running tests
- [ ] A conftest.py check or import-time assertion fails if `jq` is missing
- [ ] `test_jq_filters_merge_commits` runs (not skips) in CI

**Validation Command:**
```bash
python -c "import jq; print('jq available')" && echo "PASS" || echo "FAIL: jq not installed"
```

---

### BH21-003: TOML parser silently drops quoted keys
**Severity:** CRITICAL
**Category:** `bug/logic`
**Location:** `scripts/validate_config.py:182`
**Status:** 🔴 OPEN
**Pattern:** PAT-001

**Problem:** The key regex `^([a-zA-Z0-9_][a-zA-Z0-9_-]*)\s*=` only matches bare keys. TOML spec allows `"quoted key" = "value"`. A quoted key in project.toml is silently dropped — no error, no warning, the config appears to parse successfully but is missing data. Combined with BH20-004 (unrecognized line warnings), a warning IS emitted, but it says "unrecognized line" rather than "quoted keys not supported."

**Evidence:**
```python
>>> parse_simple_toml('"my key" = "value"')
{}  # Key silently dropped
```

**Acceptance Criteria:**
- [ ] `parse_simple_toml('"my key" = "value"')` either parses correctly or raises ValueError with "quoted keys not supported"
- [ ] The warning/error message specifically mentions quoted keys
- [ ] A test verifies both single-quoted and double-quoted key handling

**Validation Command:**
```bash
python -c "
import sys; sys.path.insert(0, 'scripts')
from validate_config import parse_simple_toml
try:
    result = parse_simple_toml('\"my key\" = \"value\"')
    # Either it parses or raises - both acceptable
    if not result:
        print('FAIL: quoted key silently dropped')
        sys.exit(1)
    print('PASS: key parsed')
except ValueError as e:
    if 'quoted' in str(e).lower() or 'key' in str(e).lower():
        print(f'PASS: clear error: {e}')
    else:
        print(f'FAIL: unclear error: {e}')
        sys.exit(1)
"
```

---

### BH21-004: TOML escape sequences silently corrupt strings — Windows paths become garbage
**Severity:** HIGH
**Category:** `bug/logic`
**Location:** `scripts/validate_config.py:280-281`
**Status:** 🔴 OPEN
**Pattern:** PAT-001

**Problem:** Unknown escape sequences like `\q` are kept as-is (`\q` → literal `\q`), but valid TOML escape sequences like `\n` are interpreted. A Windows path `"C:\new_folder"` becomes `"C:<newline>ew_folder"`. TOML spec says unknown escapes are errors. The parser should either reject them or use raw strings.

**Evidence:** `_unescape_toml_string` at line 280: `result.append(s[i:i + 2])` for unknown escapes, but `\n`, `\t`, `\r` are processed on lines 268-275.

**Acceptance Criteria:**
- [ ] `parse_simple_toml('path = "C:\\\\new_folder"')` returns `{"path": "C:\\new_folder"}` (escaped backslash)
- [ ] `parse_simple_toml("path = 'C:\\new_folder'")` returns `{"path": "C:\\new_folder"}` (single-quoted, no escape processing per TOML spec)
- [ ] A test verifies single-quoted strings are NOT escape-processed

**Validation Command:**
```bash
python -c "
import sys; sys.path.insert(0, 'scripts')
from validate_config import parse_simple_toml
# Single-quoted string should NOT process escapes (TOML spec)
result = parse_simple_toml(\"path = 'C:\\\new_folder'\")
val = result.get('path', '')
if '\n' in val:
    print(f'FAIL: newline in path: {val!r}')
    sys.exit(1)
print(f'Value: {val!r}')
print('PASS')
"
```

---

### BH21-005: _yaml_safe doesn't escape newlines — GitHub titles with newlines corrupt tracking files
**Severity:** HIGH
**Category:** `bug/logic`
**Location:** `skills/sprint-run/scripts/sync_tracking.py:181-204`
**Status:** 🔴 OPEN
**Pattern:** PAT-001

**Problem:** `_yaml_safe` quotes values containing `: `, `#`, `[`, etc., but does not check for newline characters. If a GitHub issue title contains a literal newline (possible via API), the YAML frontmatter breaks and `read_tf` fails to parse the file on next read, losing tracking data.

**Acceptance Criteria:**
- [ ] `_yaml_safe("line1\nline2")` returns a safely quoted string with no raw newlines
- [ ] A tracking file written with a newline-containing title can be round-tripped through `read_tf` → `write_tf` → `read_tf`

**Validation Command:**
```bash
python -c "
import sys; sys.path.insert(0, 'scripts'); sys.path.insert(0, 'skills/sprint-run/scripts')
from sync_tracking import _yaml_safe
result = _yaml_safe('line1\nline2')
if '\n' in result and not result.startswith('\"'):
    print(f'FAIL: raw newline in output: {result!r}')
    sys.exit(1)
print(f'Result: {result!r}')
print('PASS')
"
```

---

### BH21-006: BOM-prefixed tracking files silently lose all metadata
**Severity:** HIGH
**Category:** `bug/logic`
**Location:** `skills/sprint-run/scripts/sync_tracking.py:160`
**Status:** 🔴 OPEN

**Problem:** `read_tf` uses `re.match(r"^---\s*\n", content)` to find frontmatter. A UTF-8 BOM (`\xef\xbb\xbf`) before the `---` causes the regex to fail, treating the entire file as body text with no frontmatter. All fields default to empty/zero. BOM-prefixed files are common from Windows editors.

**Acceptance Criteria:**
- [ ] `read_tf` strips BOM before matching frontmatter
- [ ] A test verifies a BOM-prefixed tracking file round-trips correctly

**Validation Command:**
```bash
python -c "
import sys, tempfile, os; sys.path.insert(0, 'scripts'); sys.path.insert(0, 'skills/sprint-run/scripts')
from sync_tracking import read_tf
tf = tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, encoding='utf-8-sig')
tf.write('---\nstory: US-0001\ntitle: Test\nsprint: 1\n---\nBody\n')
tf.close()
result = read_tf(tf.name)
os.unlink(tf.name)
if result.story != 'US-0001':
    print(f'FAIL: story={result.story!r} (expected US-0001)')
    sys.exit(1)
print('PASS')
"
```

---

### BH21-007: 8 mock-return-value tests provide false coverage of version calculation, label creation, and milestone lookup
**Severity:** HIGH
**Category:** `test/mock-abuse`
**Location:** `tests/test_release_gate.py:43-83`, `tests/test_sprint_runtime.py:121-143,461-471`
**Status:** 🔴 OPEN
**Pattern:** PAT-003

**Problem:** `TestCalculateVersion` (4 tests) mocks both `find_latest_semver_tag` and `parse_commits_since`, then asserts the transformation of mock data. The actual tag-finding and commit-parsing functions are never exercised. `TestFindMilestoneTitle` (2 tests) mocks `find_milestone` then asserts the mock's return value. `TestCreateLabel` checks `gh` was called but not with correct color/description args.

**Evidence:** See audit/2-test-quality.md §AP-1 for full analysis with code samples.

**Acceptance Criteria:**
- [ ] `TestCalculateVersion` tests use real git tags+commits in a temp repo (git commands not mocked, only `gh` commands)
- [ ] `TestCreateLabel` asserts that `--color` and `--description` args are correct
- [ ] No test has a pattern of `mock.return_value = X` → `assert result == f(X)` where `f` is trivial

**Validation Command:**
```bash
# After fix: verify no mock.return_value == assertion pattern
grep -A5 'return_value' tests/test_release_gate.py | grep -c 'assertEqual.*mock\|assertEqual.*None\|assertEqual.*0.1.0'
# Should be 0 for version calculation tests
```

---

### BH21-008: get_existing_issues fetches only 500 issues — duplicate GitHub issues created for large repos
**Severity:** HIGH
**Category:** `bug/logic`
**Location:** `skills/sprint-setup/scripts/populate_issues.py:333`
**Status:** 🔴 OPEN

**Problem:** `get_existing_issues()` queries `--limit 500`. Projects with >500 issues have incomplete dedup data. The `warn_if_at_limit` warning fires but the script continues, creating duplicate issues for stories that exist beyond the 500-issue window.

**Acceptance Criteria:**
- [ ] Either use `--paginate` for complete results, or abort with a clear error when truncated
- [ ] A test verifies behavior when issue count exceeds the limit

**Validation Command:**
```bash
python -c "
import sys; sys.path.insert(0, 'scripts'); sys.path.insert(0, 'skills/sprint-setup/scripts')
from populate_issues import get_existing_issues
# Verify the function signature/implementation uses paginate or handles truncation
import inspect
src = inspect.getsource(get_existing_issues)
if '--paginate' in src or 'abort' in src.lower() or 'raise' in src:
    print('PASS: handles large repos')
else:
    print('FAIL: still uses --limit 500 without abort')
    sys.exit(1)
"
```

---

### BH21-009: FakeGitHub missing PR fields — tests must manually inject statusCheckRollup, createdAt, reviews
**Severity:** HIGH
**Category:** `test/shallow`
**Location:** `tests/fake_github.py` (`_pr_create` method)
**Status:** 🔴 OPEN
**Pattern:** PAT-003

**Problem:** `_pr_create()` doesn't include `statusCheckRollup`, `createdAt`, or `reviews` fields. Production code requests these via `--json`. Tests work around this by manually injecting fields into fixture data, meaning test authors must remember to do this or tests silently pass with `None` values.

**Acceptance Criteria:**
- [ ] `_pr_create()` includes `statusCheckRollup: []`, `createdAt: <iso-timestamp>`, `reviews: []`
- [ ] Existing tests that manually inject these fields still pass
- [ ] A test creates a PR via FakeGitHub and verifies these fields are present

**Validation Command:**
```bash
python -c "
import sys; sys.path.insert(0, 'tests')
from fake_github import FakeGitHub
fg = FakeGitHub('owner/repo')
fg.handle(['gh', 'pr', 'create', '--title', 'Test', '--body', 'Body', '--base', 'main', '--head', 'feat'])
pr = fg.prs[0]
for field in ['statusCheckRollup', 'createdAt', 'reviews']:
    if field not in pr:
        print(f'FAIL: {field} missing from PR')
        sys.exit(1)
print('PASS')
"
```

---

### BH21-010: Makefile test target uses unittest discover instead of pytest
**Severity:** HIGH
**Category:** `test/integration-gap`
**Location:** `Makefile:13`
**Status:** 🔴 OPEN

**Problem:** The Makefile `test` target runs `python -m unittest discover`, but pytest is the required runner for hypothesis tests and is listed as a dev dependency. This means CI misses property tests (BH21-001), doesn't generate coverage reports, and doesn't use pytest's superior failure reporting. The fix for BH21-001 (making property tests visible to CI) depends on either switching to pytest OR adding TestCase inheritance.

**Acceptance Criteria:**
- [ ] `make test` runs pytest (with hypothesis) and produces coverage output
- [ ] All 773+ tests are collected (including property tests)
- [ ] CI output shows hypothesis test results

**Validation Command:**
```bash
# Count tests collected by each runner
echo "unittest:" && python -m unittest discover -s tests 2>&1 | tail -1
echo "pytest:" && python -m pytest tests/ --collect-only -q 2>&1 | tail -1
# pytest should collect >= unittest count + 26 property tests
```

---

### BH21-011: ReDoS protection in _safe_compile_pattern is bypassable
**Severity:** MEDIUM
**Category:** `bug/security`
**Location:** `skills/sprint-setup/scripts/populate_issues.py:82-96`
**Status:** 🔴 OPEN

**Problem:** The ReDoS check tests a fixed string `"a" * 25`. A pattern like `(b+)+$` completes instantly on all-`a` input (fast fail, no match) but catastrophically backtracks on `"bbb...!"`. The test string needs to match the pattern's vulnerable character class to detect backtracking. Note: project.toml is trusted input (same trust model as shell=True in release_gate.py), so exploitation requires a malicious committer.

**Acceptance Criteria:**
- [ ] ReDoS check uses a pattern-aware test string (or uses `re.fullmatch` with timeout)
- [ ] A test verifies that `(b+)+$` is rejected as catastrophic
- [ ] A test verifies that legitimate patterns like `[A-Z]+-\d{4}` pass the check

**Validation Command:**
```bash
python -c "
import sys; sys.path.insert(0, 'scripts'); sys.path.insert(0, 'skills/sprint-setup/scripts')
from populate_issues import _safe_compile_pattern
try:
    _safe_compile_pattern('(b+)+$')
    print('FAIL: catastrophic pattern accepted')
    sys.exit(1)
except ValueError:
    print('PASS: catastrophic pattern rejected')
"
```

---

### BH21-012: Closed-issue kanban override triplicated — divergence risk
**Severity:** MEDIUM
**Category:** `design/duplication`
**Location:** `sync_tracking.py:241`, `sync_tracking.py:291`, `update_burndown.py:170`
**Status:** 🔴 OPEN
**Pattern:** PAT-002

**Problem:** Three places independently check `if state == "closed" and status != "done": status = "done"`. `kanban_from_labels()` already handles the no-label case but not the stale-label case. If the override logic changes (e.g., adding "cancelled" state), three places need updating.

**Acceptance Criteria:**
- [ ] `kanban_from_labels()` handles the closed-issue override internally (or a wrapper does)
- [ ] All three call sites use the shared implementation
- [ ] A test verifies a closed issue with stale `kanban:dev` label returns "done"

**Validation Command:**
```bash
grep -rn 'closed.*done\|done.*closed' scripts/validate_config.py skills/sprint-run/scripts/sync_tracking.py skills/sprint-run/scripts/update_burndown.py | wc -l
# Should be 1 (in kanban_from_labels) after fix, not 4
```

---

### BH21-013: Short-title extraction duplicated in sync_tracking and update_burndown
**Severity:** MEDIUM
**Category:** `design/duplication`
**Location:** `sync_tracking.py:293-296`, `update_burndown.py:159-162`
**Status:** 🔴 OPEN
**Pattern:** PAT-002

**Problem:** Both scripts inline `issue["title"].split(":", 1)[-1].strip()` for short-title extraction. If the title format changes (e.g., `US-0001 — Title`), both need updating.

**Acceptance Criteria:**
- [ ] A shared `short_title(title: str) -> str` function exists in validate_config.py
- [ ] Both call sites use the shared function
- [ ] A test verifies edge cases: no colon, multiple colons, empty after colon

**Validation Command:**
```bash
grep -rn "split.*:.*1.*-1.*strip" skills/sprint-run/scripts/ | wc -l
# Should be 0 after fix
```

---

### BH21-014: Sprint number inference duplicated between bootstrap_github and populate_issues
**Severity:** MEDIUM
**Category:** `design/duplication`
**Location:** `skills/sprint-setup/scripts/bootstrap_github.py:80`, `skills/sprint-setup/scripts/populate_issues.py:172`
**Status:** 🔴 OPEN
**Pattern:** PAT-002

**Problem:** `_collect_sprint_numbers()` and `_infer_sprint_number()` both scan for `### Sprint N:` headings then fall back to filename digits. The comment in populate_issues acknowledges this: "Priority matches bootstrap_github._collect_sprint_numbers: content-first."

**Acceptance Criteria:**
- [ ] A shared sprint-number inference function exists (in validate_config.py or as a shared helper)
- [ ] Both call sites use the shared function
- [ ] A test verifies content-first, filename-fallback priority

**Validation Command:**
```bash
grep -rn '_collect_sprint_numbers\|_infer_sprint_number' skills/sprint-setup/scripts/ | wc -l
# Should be reduced to 1 definition + imports after fix
```

---

### BH21-015: Story ID extraction regex inlined in populate_issues instead of using extract_story_id()
**Severity:** MEDIUM
**Category:** `design/duplication`
**Location:** `skills/sprint-setup/scripts/populate_issues.py:344`
**Status:** 🔴 OPEN
**Pattern:** PAT-002

**Problem:** `get_existing_issues()` uses `re.match(r"([A-Z]+-\d+)", ...)` inline with a comment "consistent with extract_story_id() in validate_config.py" — acknowledging the duplication without fixing it.

**Acceptance Criteria:**
- [ ] `get_existing_issues()` calls `extract_story_id()` instead of inline regex
- [ ] All tests pass unchanged

**Validation Command:**
```bash
grep -n 'A-Z.*\\d\+' skills/sprint-setup/scripts/populate_issues.py | grep -v 'import\|extract_story_id'
# Should be 0 after fix (no inline story ID regex)
```

---

### BH21-016: Dead wrapper functions add indirection without value
**Severity:** MEDIUM
**Category:** `design/dead-code`
**Location:** `update_burndown.py:144`, `sync_tracking.py:30`, `sync_tracking.py:132`
**Status:** 🔴 OPEN

**Problem:** Three one-line wrappers that just delegate to another function:
- `_fm_val()` → calls `frontmatter_value()` (3 call sites in update_burndown)
- `find_milestone_title()` → calls `find_milestone()["title"]` (1 call site)
- `_parse_closed()` → calls `parse_iso_date()` (2 call sites)

**Acceptance Criteria:**
- [ ] Call sites use the underlying function directly
- [ ] Wrapper functions are removed
- [ ] All tests pass unchanged

**Validation Command:**
```bash
grep -n '_fm_val\|find_milestone_title\|_parse_closed' skills/sprint-run/scripts/sync_tracking.py skills/sprint-run/scripts/update_burndown.py
# Should only show import lines (if any) after fix, not function definitions
```

---

### BH21-017: Epic enrichment hardcodes US-\d{4} pattern, ignoring custom story_id_pattern
**Severity:** MEDIUM
**Category:** `bug/logic`
**Location:** `skills/sprint-setup/scripts/populate_issues.py:301`
**Status:** 🔴 OPEN

**Problem:** `enrich_from_epics()` uses `re.findall(r"US-\d{4}", content)` to find story references in epic files. Projects with custom story ID patterns (e.g., `PROJ-\d{4}`) get no epic enrichment — stories from epics that only appear in detail blocks are silently skipped.

**Acceptance Criteria:**
- [ ] `enrich_from_epics()` uses the configured `story_id_pattern` (or `extract_story_id`)
- [ ] A test verifies epic enrichment works with a non-US- pattern

**Validation Command:**
```bash
grep -n 'US-.*\\d{4}' skills/sprint-setup/scripts/populate_issues.py
# After fix: the hardcoded pattern should be replaced or removed
```

---

### BH21-018: CHEATSHEET.md has 2 broken anchor references + 4 unreferenced anchors
**Severity:** MEDIUM
**Category:** `doc/drift`
**Location:** `CHEATSHEET.md:207,221`
**Status:** 🔴 OPEN

**Problem:** `§manage_epics._parse_header_table` and `§manage_sagas._parse_header_table` reference functions removed during BH18-012/013 refactoring. The shared replacement `§validate_config.parse_header_table` exists but isn't referenced. Additionally, 4 newer anchors (TABLE_ROW, frontmatter_value, parse_header_table, _safe_compile_pattern) aren't indexed.

**Acceptance Criteria:**
- [ ] `python scripts/validate_anchors.py --check` reports 0 broken references
- [ ] All shared helper anchors are indexed in CHEATSHEET.md

**Validation Command:**
```bash
python scripts/validate_anchors.py --check 2>&1 | grep -c "broken"
# Should be 0 after fix
```

---

### BH21-019: Unbounded CI log fetching in check_status can consume excessive memory
**Severity:** MEDIUM
**Category:** `bug/error-handling`
**Location:** `skills/sprint-monitor/scripts/check_status.py:69`
**Status:** 🔴 OPEN

**Problem:** `check_ci()` calls `gh(["run", "view", str(run_id), "--log-failed"])` with no output size limit. Failed CI logs can be megabytes. The entire output is captured into a string and scanned line by line. For a test suite with thousands of failure lines, this is slow and memory-intensive.

**Acceptance Criteria:**
- [ ] CI log output is truncated to a reasonable limit (e.g., first 500 lines or 100KB)
- [ ] A test verifies the truncation works

**Validation Command:**
```bash
grep -n 'log-failed\|log.*limit\|truncat' skills/sprint-monitor/scripts/check_status.py
# After fix: should show truncation logic near the --log-failed call
```

---

### BH21-020: Happy-path-only tests for 5 scripts — no error/edge case coverage for main()
**Severity:** MEDIUM
**Category:** `test/missing`
**Location:** `scripts/team_voices.py`, `scripts/traceability.py`, `scripts/test_coverage.py`, `scripts/manage_epics.py`, `scripts/manage_sagas.py`
**Status:** 🔴 OPEN

**Problem:** Five scripts have unit tests for their core functions but only "exits 1 on bad config" tests for `main()`. No test exercises the full `main()` → `load_config()` → process → output pipeline with valid input. A bug in argument parsing, file I/O, or output formatting would escape.

**Acceptance Criteria:**
- [ ] Each script has at least one happy-path `main()` test with valid config
- [ ] Tests verify output content (not just exit code)

**Validation Command:**
```bash
# Count main() tests per script (beyond exit-code tests)
for s in team_voices traceability test_coverage manage_epics manage_sagas; do
  echo -n "$s: "; grep -rn "def test.*main.*$s\|def test.*${s}.*main" tests/ | grep -v "exit" | wc -l
done
# Each should be >= 1 after fix
```

---

### BH21-021: splitlines() vs split('\n') inconsistency despite explicit policy
**Severity:** MEDIUM
**Category:** `design/inconsistency`
**Location:** `scripts/test_coverage.py:54`, `scripts/sprint_init.py:696`, `scripts/sprint_teardown.py:178`, `scripts/validate_anchors.py:86,102,170,200,278`
**Status:** 🔴 OPEN

**Problem:** BH20-001 established that `split('\n')` should be used instead of `splitlines()` to avoid U+2028/U+2029 corruption. The TOML parser and markdown parsers were fixed, but 5+ other files still use `splitlines()`.

**Acceptance Criteria:**
- [ ] All `.py` files in scripts/ and skills/ use `split('\n')` instead of `splitlines()` for user content
- [ ] A grep check verifies no `splitlines()` calls remain in content-parsing code

**Validation Command:**
```bash
grep -rn 'splitlines()' scripts/ skills/ --include='*.py' | grep -v '\.pyc' | wc -l
# Should be 0 after fix
```

---

### BH21-022: write_log deletion loop crashes monitor on permission error
**Severity:** LOW
**Category:** `bug/error-handling`
**Location:** `skills/sprint-monitor/scripts/check_status.py:321-322`
**Status:** 🔴 OPEN

**Problem:** `write_log` deletes old logs in a while loop with `logs.pop(0).unlink()`. If any `unlink()` fails (permission denied, file in use), the exception propagates and the entire status check fails after completing all work. The OSError handler on line 428 catches write errors but not deletion errors.

**Acceptance Criteria:**
- [ ] `unlink()` failures are caught and logged, not propagated
- [ ] A test verifies the monitor continues when log deletion fails

**Validation Command:**
```bash
grep -A2 'unlink' skills/sprint-monitor/scripts/check_status.py | grep -c 'except\|try'
# Should be >0 after fix (error handling around unlink)
```

---

### BH21-023: _first_error false positive filter can mask real errors
**Severity:** LOW
**Category:** `bug/logic`
**Location:** `skills/sprint-monitor/scripts/check_status.py:82-83`
**Status:** 🔴 OPEN

**Problem:** `_FALSE_POSITIVE = re.compile(r"\b(?:0|no)\s+(?:error|fail)", re.IGNORECASE)` filters "no errors" and "0 failures" but could also match strings like "Error: module 'no-fail' not found" where "no" and "fail" appear near each other.

**Acceptance Criteria:**
- [ ] False positive regex is tightened (e.g., require end-of-phrase boundary)
- [ ] A test verifies "no errors" is filtered AND "Error: module 'no-fail'" is NOT filtered

**Validation Command:**
```bash
python -c "
import re
fp = re.compile(r'\b(?:0|no)\s+(?:error|fail)', re.IGNORECASE)
# Should NOT match (real error):
if fp.search('Error: cannot find module no-fail'):
    print('FAIL: false positive on real error')
else:
    print('PASS')
"
```

---

### BH21-024: sync_backlog hash_milestone_files uses filename as key — collisions possible
**Severity:** LOW
**Category:** `bug/logic`
**Location:** `scripts/sync_backlog.py:51`
**Status:** 🔴 OPEN

**Problem:** `hash_milestone_files` uses `p.name` (filename only) as the hash dict key. If two milestone files in different subdirectories have the same filename, only one hash is stored. Changes to the shadowed file are never detected.

**Acceptance Criteria:**
- [ ] Hash key uses relative path (not just filename)
- [ ] A test verifies files with the same name in different dirs are tracked independently

**Validation Command:**
```bash
grep -n 'p.name' scripts/sync_backlog.py | head -5
# After fix: should use p.relative_to() or str(p) instead of p.name
```

---

### BH21-025: test_coverage.py (the coverage checker itself) has only 68% coverage
**Severity:** LOW
**Category:** `test/missing`
**Location:** `scripts/test_coverage.py:158-181`
**Status:** 🔴 OPEN

**Problem:** `check_test_coverage()` and `format_report()` (the core functions of the test coverage tool) are almost entirely untested. The tool that checks whether tests exist... doesn't have tests for its own main functionality.

**Acceptance Criteria:**
- [ ] `check_test_coverage()` has at least one end-to-end test with valid input
- [ ] `format_report()` has a test verifying markdown structure
- [ ] Coverage for test_coverage.py reaches ≥ 80%

**Validation Command:**
```bash
python -m pytest tests/ --cov=scripts/test_coverage --cov-report=term-missing 2>&1 | grep 'test_coverage'
# Coverage should show >= 80% after fix
```

---

### BH21-026: load_config assumes sprint-config/ is direct child of project root
**Severity:** LOW
**Category:** `bug/logic`
**Location:** `scripts/validate_config.py:678`
**Status:** 🔴 OPEN

**Problem:** `load_config` sets `project_root = Path(config_dir).resolve().parent`. If config_dir is nested (e.g., `foo/bar/sprint-config`), the "project root" becomes `foo/bar/` instead of the actual root. Every `[paths]` value resolves incorrectly. The default usage (`sprint-config/`) works fine, but `main()` accepts `sys.argv[1]` as config_dir.

**Acceptance Criteria:**
- [ ] Either document that config_dir must be a direct child of project root, or use git root detection
- [ ] A test verifies behavior with a nested config_dir

**Validation Command:**
```bash
grep -n 'project_root\|config_dir.*parent' scripts/validate_config.py | head -5
# After fix: should show either git root detection or validation that config_dir.parent is project root
```

---

### BH21-027: gate_prs fetches all open PRs without milestone filter — fails on repos with 500+ PRs
**Severity:** LOW
**Category:** `bug/logic`
**Location:** `skills/sprint-release/scripts/release_gate.py:175-178`
**Status:** 🔴 OPEN

**Problem:** `gate_prs()` fetches ALL open PRs with `--limit 500`, then filters client-side for the target milestone. For repos with >500 open PRs, the gate always fails even if none of the milestone PRs are in the truncated set.

**Acceptance Criteria:**
- [ ] `gate_prs()` uses `--search "milestone:X"` to filter server-side, or uses `--paginate`
- [ ] A test verifies behavior with milestone-filtered PR fetching

**Validation Command:**
```bash
grep -A5 'gate_prs' skills/sprint-release/scripts/release_gate.py | grep -c 'search\|milestone\|paginate'
# Should be >0 after fix
```

---
