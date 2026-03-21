# Bug Hunter Punchlist — Pass 9

> Generated: 2026-03-15 | Project: giles | Baseline: 508 pass, 0 fail, 0 skip (3.0s)

## Summary
| Severity | Open | Resolved | Deferred |
|----------|------|----------|----------|
| HIGH | 0 | 8 | 0 |
| MEDIUM | 0 | 15 | 0 |
| LOW | 0 | 4 | 0 |
| **Total** | **0** | **27** | **0** |

---

## Patterns

### Pattern: PAT-001: Tests That Verify The Mock, Not Production
**Instances:** BH-001, BH-007, BH-008
**Root Cause:** FakeGitHub returns pre-shaped or default data that trivially satisfies assertions. Tests pass because the test data matches expected output, not because production code is correct. Tautological assertions that are mathematically guaranteed to pass regardless of function behavior.
**Systemic Fix:** Each mock-dependent test needs a "perturbation check" — verify that changing the mock data causes the test to fail. For tautologies, replace generic equality checks with specific value assertions.
**Detection Rule:** `grep -rn "assertEqual.*report\[.missing.\], report\[.planned.\]\|assertEqual.*\[\], \[\]" tests/`

### Pattern: PAT-002: Missing Input Validation at Function Boundaries
**Instances:** BH-004, BH-005, BH-011, BH-012, BH-023
**Root Cause:** Functions accept external data (config values, CLI args, story dicts) without validating format, uniqueness, or safety. They assume callers provide well-formed input.
**Systemic Fix:** Add precondition checks for all public functions that accept external input. Use `.get()` with defaults for dict access. Validate CLI arg counts before indexing.
**Detection Rule:** `grep -rn "sys\.argv\[.\]" scripts/ skills/ | grep -v "len(sys.argv)"`

### Pattern: PAT-003: Doc Claims Without Code Reality
**Instances:** BH-006, BH-017, BH-018, BH-019, BH-020, BH-021, BH-027
**Root Cause:** Documentation was written ahead of implementation, or implementation changed without updating docs. No automated check catches doc-code drift for descriptions and paths.
**Systemic Fix:** Add a CI step that validates doc paths (file references in markdown resolve to real files) and runs doc-drift detection.
**Detection Rule:** `grep -rn "scripts/check_status.py\b" skills/ | grep -v "skills/sprint-monitor/scripts"`

### Pattern: PAT-004: Regex Under/Over-Match
**Instances:** BH-004, BH-009, BH-013, BH-014
**Root Cause:** Regular expressions that match more or less than intended — missing word boundaries, overly greedy patterns, or missing alternative patterns for valid inputs.
**Systemic Fix:** Every regex that parses user-facing data should have adversarial test cases (partial matches, interior matches, boundary cases). Consider a test helper that asserts both "matches X" and "does NOT match Y".
**Detection Rule:** `grep -rn "re\.search.*\\bsp\\b\|re\.sub.*DOTALL\|#\[test\]" scripts/ skills/`

---

## Items

### BH-001: FakeGitHub silently ignores --jq filtering (mock fidelity gap)
**Severity:** HIGH
**Category:** `test/mock-abuse`
**Location:** `tests/fake_github.py:93-95,113`
**Status:** 🟢 RESOLVED
**Pattern:** PAT-001

**Problem:** `--jq` is listed in `_KNOWN_FLAGS["api"]` and `_VALUE_BEARING_FLAGS` but the jq expression is never evaluated. Production code passes `--jq` expressions to reshape JSON (e.g., commits endpoint filtering, timeline `| first`). FakeGitHub returns raw unfiltered data for most endpoints. Tests pre-shape fixture data to match what `--jq` would produce, meaning the test verifies the fixture shape, not the jq filter correctness.

**Evidence:**
```python
# fake_github.py:113
"api": frozenset(("paginate", "f", "X", "jq")),  # jq accepted but never applied

# fake_github.py:271-272
# Return all stored commits; production --jq filtering is a no-op here
return self._ok(json.dumps(self.commits_data))
```

**Acceptance Criteria:**
- [ ] FakeGitHub `_handle_api` applies basic jq expressions (at minimum `.` identity and `| first`)
- [ ] OR: tests that exercise jq-dependent code paths explicitly document they're testing the fixture shape (not jq), and add integration-level notes
- [ ] At minimum: a comment in FakeGitHub explaining which endpoints fake the jq behavior vs. which don't
- [ ] `check_direct_pushes` test verifies the jq filter contract, not just the pre-shaped data

**Validation Command:**
```bash
grep -n "jq" tests/fake_github.py | head -20
python -m unittest discover tests/ 2>&1 | grep -E "^(Ran|OK|FAIL)"
```

---

### BH-002: Golden test silently skips when recordings absent
**Severity:** HIGH
**Category:** `test/bogus`
**Location:** `tests/test_golden_run.py:102-109`
**Status:** 🟢 RESOLVED
**Pattern:** PAT-001

**Problem:** When `RECORD_MODE` is false and `replayer.has_recordings()` is false (every fresh checkout, every CI run without golden files), the test calls `self.skipTest()`. A `warnings.warn()` goes to stderr which is easily missed. The most valuable regression test in the suite provides zero protection by default.

**Evidence:**
```python
# test_golden_run.py:101-109
elif replayer.has_recordings():
    snapshot = replayer.load_snapshot(phase_name)
    diffs = check_fn(snapshot)
    self.assertEqual(diffs, [], f"{phase_name} mismatch: {diffs}")
else:
    import warnings
    warnings.warn("Golden recordings absent — run GOLDEN_RECORD=1 to create them")
    self.skipTest("No golden recordings found.")
```

**Acceptance Criteria:**
- [ ] When golden recordings are absent, the test either: (a) runs the pipeline and generates recordings inline (auto-record on first run), OR (b) falls through to the non-golden pipeline test assertions so SOMETHING is validated
- [ ] The test NEVER silently skips — it either passes with meaningful assertions or fails with a clear message
- [ ] CI job includes golden recording generation step, or golden recordings are committed

**Validation Command:**
```bash
python -m unittest tests.test_golden_run -v 2>&1 | grep -E "skip|SKIP|OK|FAIL"
```

---

### BH-003: get_milestone_numbers --jq . + --paginate = invalid concatenated JSON
**Severity:** HIGH
**Category:** `bug/logic`
**Location:** `skills/sprint-setup/scripts/populate_issues.py:279`
**Status:** 🟢 RESOLVED

**Problem:** `gh api repos/{owner}/{repo}/milestones --paginate --jq .` applies the jq identity filter per page. For multi-page results (30+ milestones), the output is `[...][...][...]` — three concatenated JSON arrays, not one valid JSON array. `json.loads()` at line 280 parses only the first `[...]` and raises `JSONDecodeError` on the rest.

**Evidence:**
```python
# populate_issues.py:279
raw = gh(["api", "repos/{owner}/{repo}/milestones", "--paginate", "--jq", "."])
return {m["title"]: m["number"] for m in json.loads(raw)} if raw else {}
```

**Acceptance Criteria:**
- [ ] `get_milestone_numbers()` works for repos with 30+ milestones (multi-page response)
- [ ] Remove `--jq .` (identity filter adds no value) OR remove `--paginate` and use `per_page=100`
- [ ] Test: verify the function handles concatenated JSON arrays (simulate multi-page)

**Validation Command:**
```bash
grep -n "jq.*paginate\|paginate.*jq" skills/sprint-setup/scripts/populate_issues.py
# After fix: should return 0 lines or show --paginate without --jq
```

---

### BH-004: extract_sp regex matches "sp" as substring (e.g., "wasp: 3" → 3 SP)
**Severity:** HIGH
**Category:** `bug/logic`
**Location:** `scripts/validate_config.py:674`
**Status:** 🟢 RESOLVED
**Pattern:** PAT-002, PAT-004

**Problem:** The regex `r"(?:story\s*points?|sp)\s*[:=]\s*(\d+)"` has no word boundary around `sp`. Text like "wasp: 3" or "BSP: 2" in an issue body would be matched, incorrectly extracting story points.

**Evidence:**
```python
# validate_config.py:674
if m := re.search(
    r"(?:story\s*points?|sp)\s*[:=]\s*(\d+)", body, re.IGNORECASE
):
```

**Acceptance Criteria:**
- [ ] `extract_sp({"body": "The wasp: 3 project..."})` returns 0, not 3
- [ ] `extract_sp({"body": "sp: 5"})` still returns 5
- [ ] `extract_sp({"body": "SP = 8"})` still returns 8
- [ ] `extract_sp({"body": "story points: 13"})` still returns 13
- [ ] New test: adversarial body text with "sp" as substring

**Validation Command:**
```bash
python -c "
import sys; sys.path.insert(0, 'scripts')
from validate_config import extract_sp
assert extract_sp({'body': 'The wasp: 3 project'}) == 0, 'substring match!'
assert extract_sp({'body': 'sp: 5'}) == 5, 'legit sp not found'
assert extract_sp({'body': 'BSP: 2 value'}) == 0, 'BSP matched as sp!'
print('PASS')
"
```

---

### BH-005: _format_story_section crashes on missing dict keys
**Severity:** HIGH
**Category:** `bug/error-handling`
**Location:** `scripts/manage_epics.py:174`
**Status:** 🟢 RESOLVED
**Pattern:** PAT-002

**Problem:** `_format_story_section` accesses `story_data['id']`, `story_data['title']`, `story_data['story_points']`, `story_data['priority']` via direct dict indexing. If any key is missing (e.g., when called from CLI with a minimal dict), it raises `KeyError`.

**Evidence:**
```python
# manage_epics.py:173-179
lines = [
    f"### {story_data['id']}: {story_data['title']}",  # KeyError if 'id' missing
    "",
    "| Field | Value |",
    "|-------|-------|",
    f"| Story Points | {story_data['story_points']} |",  # KeyError
    f"| Priority | {story_data['priority']} |",  # KeyError
]
```

**Acceptance Criteria:**
- [ ] `_format_story_section({})` does not raise — returns a section with placeholder values
- [ ] `_format_story_section({"id": "US-001", "title": "Foo"})` works (missing SP/priority get defaults)
- [ ] New test: call with minimal/empty dict, verify no crash

**Validation Command:**
```bash
python -c "
import sys; sys.path.insert(0, 'scripts')
from manage_epics import _format_story_section
result = _format_story_section({'id': 'US-001', 'title': 'Test'})
print(result[:50])
print('PASS' if 'US-001' in result else 'FAIL')
"
```

---

### BH-006: sprint-monitor SKILL.md Quick Reference has wrong script path
**Severity:** HIGH
**Category:** `doc/drift`
**Location:** `skills/sprint-monitor/SKILL.md:10`
**Status:** 🟢 RESOLVED
**Pattern:** PAT-003

**Problem:** The Quick Reference table says `scripts/check_status.py [sprint-number]` but the actual file is at `skills/sprint-monitor/scripts/check_status.py`. An agent following the Quick Reference will get "file not found". The correct path appears 200+ lines further down.

**Evidence:**
```markdown
## Quick Reference
| Step | Script |
|------|--------|
| Full status check | `scripts/check_status.py [sprint-number]` |
```
Correct path in body text at line 237: `python3 skills/sprint-monitor/scripts/check_status.py`

**Acceptance Criteria:**
- [ ] Quick Reference table path matches the actual file location
- [ ] `ls skills/sprint-monitor/scripts/check_status.py` succeeds

**Validation Command:**
```bash
grep "scripts/check_status.py" skills/sprint-monitor/SKILL.md | head -5
ls -la skills/sprint-monitor/scripts/check_status.py
```

---

### BH-007: test_coverage_no_actual_tests has tautological assertions
**Severity:** HIGH
**Category:** `test/bogus`
**Location:** `tests/test_pipeline_scripts.py:165-175`
**Status:** 🟢 RESOLVED
**Pattern:** PAT-001

**Problem:** `self.assertEqual(report["missing"], report["planned"])` is a tautology when `implemented` is empty. With zero implementations, `missing` will always equal `planned` by definition — the assertion can never fail regardless of what `check_test_coverage` returns. The test appears to verify coverage detection but actually verifies a mathematical identity.

**Evidence:**
```python
# test_pipeline_scripts.py:173-175
self.assertEqual(len(report["implemented"]), 0)
# With no implementations, nothing can match — all planned are missing
self.assertEqual(report["missing"], report["planned"])
```

**Acceptance Criteria:**
- [ ] Test asserts specific planned test case IDs are present in the missing list (not just that missing == planned)
- [ ] Test also verifies that when implementations DO exist, `missing` shrinks appropriately
- [ ] New test: partial implementations — some planned tests match, some don't

**Validation Command:**
```bash
python -m unittest tests.test_pipeline_scripts.TestCoverage -v 2>&1 | tail -5
```

---

### BH-008: test_api_error_handled tests mock default, not error handling
**Severity:** HIGH
**Category:** `test/bogus`
**Location:** `tests/test_gh_interactions.py:1215-1222`
**Status:** 🟢 RESOLVED
**Pattern:** PAT-001

**Problem:** `TestCheckBranchDivergenceFakeGH.test_api_error_handled` claims to verify "Branch not in comparisons still returns default." But FakeGitHub's `_handle_api` returns `{"behind_by": 0, "ahead_by": 0}` as a default for unknown branches. The test asserts `report == []` and `actions == []`, which is exactly what "no drift" looks like — not an error. The test name promises error handling coverage that doesn't exist.

**Evidence:**
```python
# The test name says "error_handled" but it's testing the happy path of "no drift"
# A real API error (HTTP 404, network timeout) would raise an exception, not return defaults
```

**Acceptance Criteria:**
- [ ] Rename the test to reflect what it actually tests (e.g., `test_unknown_branch_returns_no_drift`)
- [ ] Add a real error handling test: mock `gh_json` to raise `RuntimeError`, verify `check_branch_divergence` handles it gracefully
- [ ] The new error test must verify either: the error is reported in the action items, or the function raises a clear exception

**Validation Command:**
```bash
python -m unittest tests.test_gh_interactions.TestCheckBranchDivergenceFakeGH -v 2>&1 | tail -5
```

---

### BH-009: update_sprint_status regex eats content after Active Stories section
**Severity:** MEDIUM
**Category:** `bug/logic`
**Location:** `skills/sprint-run/scripts/update_burndown.py:113`
**Status:** 🟢 RESOLVED
**Pattern:** PAT-004

**Problem:** The regex `r"## Active Stories.*?(?=\n## |\Z)"` with `re.DOTALL` replaces everything between `## Active Stories` and the next `## ` heading or end-of-file. If there's content after the Active Stories section that doesn't start with `## ` (e.g., plain text, notes, horizontal rules), it gets deleted.

**Evidence:**
```python
# update_burndown.py:113-115
pattern = r"## Active Stories.*?(?=\n## |\Z)"
if re.search(pattern, text, re.DOTALL):
    text = re.sub(pattern, new_table.rstrip(), text, flags=re.DOTALL)
```

**Acceptance Criteria:**
- [ ] Content after the Active Stories table that is NOT a `## ` heading is preserved
- [ ] Test: SPRINT-STATUS.md with notes after Active Stories — verify notes survive update
- [ ] Alternative: use `\n---\n` or `\n\n` as section terminator instead of relying on `## `

**Validation Command:**
```bash
python -c "
import re
text = '## Active Stories\n| old |\n\nSome notes here\n'
pattern = r'## Active Stories.*?(?=\n## |\Z)'
result = re.sub(pattern, '## Active Stories\n| new |', text, flags=re.DOTALL)
print(repr(result))
assert 'Some notes here' in result, 'Content eaten!'
print('PASS')
" 2>&1
```

---

### BH-010: get_linked_pr returns oldest PR, not the active one
**Severity:** MEDIUM
**Category:** `bug/logic`
**Location:** `skills/sprint-run/scripts/sync_tracking.py:60-78`
**Status:** 🟢 RESOLVED

**Problem:** The timeline API `--jq` filter ends with `| first`, returning the chronologically oldest linked PR. If an issue has an initial PR that was closed (abandoned) and a replacement PR, `get_linked_pr` returns the closed/abandoned one.

**Evidence:**
```python
# sync_tracking.py uses --jq '... | first' in the timeline query
# FakeGitHub mimics this by returning the first event with source.issue.pull_request
```

**Acceptance Criteria:**
- [ ] When an issue has multiple linked PRs, the open or most recently merged one is preferred
- [ ] Test: issue with 2 linked PRs (one closed, one open) — verify the open PR is returned
- [ ] If no open PR exists, fall back to the most recently updated one

**Validation Command:**
```bash
grep -n "first" skills/sprint-run/scripts/sync_tracking.py | head -5
```

---

### BH-011: add_story allows duplicate story IDs within an epic
**Severity:** MEDIUM
**Category:** `bug/logic`
**Location:** `scripts/manage_epics.py:224-236`
**Status:** 🟢 RESOLVED
**Pattern:** PAT-002

**Problem:** `add_story` appends a new story section to an epic file without checking if a story with the same ID already exists. Calling `add_story(path, {"id": "US-0001", ...})` twice produces a duplicate section.

**Evidence:**
```python
# manage_epics.py:224-236 — no existence check before appending
def add_story(path: str, story_data: dict) -> None:
    content = Path(path).read_text(encoding="utf-8")
    new_section = _format_story_section(story_data)
    # ... appends without checking for duplicates
```

**Acceptance Criteria:**
- [ ] `add_story` raises or warns when the story ID already exists in the file
- [ ] Test: attempt to add a duplicate story ID, verify rejection
- [ ] Existing functionality (adding unique stories) still works

**Validation Command:**
```bash
python -c "
import sys; sys.path.insert(0, 'scripts')
from manage_epics import parse_epic, add_story
# Would need a temp file to fully validate
print('Manual test required')
"
```

---

### BH-012: manage_sagas update-index crashes if sys.argv[3] missing
**Severity:** MEDIUM
**Category:** `bug/error-handling`
**Location:** `scripts/manage_sagas.py:280`
**Status:** 🟢 RESOLVED
**Pattern:** PAT-002

**Problem:** The `update-index` command accesses `sys.argv[3]` for the `epics_dir` argument without checking `len(sys.argv)`. Running `manage_sagas.py update-index saga.md` without the third arg raises `IndexError`.

**Evidence:**
```python
# manage_sagas.py:280
# No length guard before: epics_dir = sys.argv[3]
```

**Acceptance Criteria:**
- [ ] Running `manage_sagas.py update-index saga.md` (missing arg) prints a usage message, not IndexError
- [ ] Test: verify clean error on missing argument

**Validation Command:**
```bash
python scripts/manage_sagas.py update-index /dev/null 2>&1; echo "exit: $?"
# Should show usage error, not IndexError traceback
```

---

### BH-013: VOICE_PATTERN misparses lines with interior quotes
**Severity:** MEDIUM
**Category:** `bug/logic`
**Location:** `scripts/team_voices.py:26-28`
**Status:** 🟢 RESOLVED
**Pattern:** PAT-004

**Problem:** The regex alternation tries quoted text first: `(?:"(.+?)"|(.+?))`. A line like `> **Name:** she said "hello" loudly` matches group 2 as `she said "hello"` (capturing to the first closing quote) instead of the full text, because the `"(.+?)"` alternative matches first.

**Evidence:**
```python
# team_voices.py:26-28
VOICE_PATTERN = re.compile(
    r'^>\s*\*\*([^*]+?):\*\*\s*(?:"(.+?)"|(.+?))\s*$'
)
```

**Acceptance Criteria:**
- [ ] Voice line `> **Name:** she said "hello" loudly` extracts `she said "hello" loudly` as the full text
- [ ] Voice line `> **Name:** "clean quote"` still extracts `clean quote` (quotes stripped)
- [ ] Test: adversarial voice lines with interior quotes

**Validation Command:**
```bash
python -c "
import re
pat = re.compile(r'^>\s*\*\*([^*]+?):\*\*\s*(?:\"(.+?)\"|(.+?))\s*$')
m = pat.match('> **Name:** she said \"hello\" loudly')
text = m.group(2) or m.group(3) if m else None
print(f'Matched: {text!r}')
assert text == 'she said \"hello\" loudly', f'Wrong match: {text}'
print('PASS')
"
```

---

### BH-014: Rust test scanner misses #[tokio::test] async tests
**Severity:** MEDIUM
**Category:** `bug/logic`
**Location:** `scripts/test_coverage.py:23`
**Status:** 🟢 RESOLVED
**Pattern:** PAT-004

**Problem:** The Rust test pattern `#\[test\]\s*(?:#\[.*\]\s*)*fn\s+(\w+)` requires `#[test]` specifically. Async tests using `#[tokio::test]` or `#[async_std::test]` don't match, causing the coverage scanner to miss them.

**Evidence:**
```python
# test_coverage.py:23
"rust": (r"#\[test\]\s*(?:#\[.*\]\s*)*fn\s+(\w+)", ...)
```

**Acceptance Criteria:**
- [ ] Pattern matches `#[tokio::test] async fn test_foo()`
- [ ] Pattern matches `#[async_std::test] async fn test_bar()`
- [ ] Pattern still matches `#[test] fn test_baz()`
- [ ] Test: Rust file with async test functions detected correctly

**Validation Command:**
```bash
python -c "
import re
pattern = r'#\[test\]\s*(?:#\[.*\]\s*)*fn\s+(\w+)'
assert re.search(pattern, '#[test]\nfn test_foo()'), 'basic failed'
result = re.search(pattern, '#[tokio::test]\nasync fn test_bar()')
print(f'tokio::test match: {result}')
print('FAIL — tokio::test not matched' if not result else 'PASS')
"
```

---

### BH-015: ~50 duplicate tests across files inflate count without adding coverage
**Severity:** MEDIUM
**Category:** `test/fragile`
**Location:** `tests/test_gh_interactions.py`, `tests/test_lifecycle.py`, `tests/test_release_gate.py`
**Status:** 🟢 RESOLVED

**Problem:** At least 20 test methods are pure duplicates across files: `TestExtractSP` (13 in test_gh_interactions + 3 in test_lifecycle), `TestValidateMessage` (9 + 6), `TestBumpVersion` (5 in test_gh_interactions + 6 in test_release_gate). Additionally, `TestCheckBranchDivergence` and its FakeGH variant duplicate ~8 tests. This creates CI noise (all copies fail on the same bug) and inflates the test count.

**Evidence:**
```
test_gh_interactions.py: TestExtractSP (13), TestValidateMessage (9), TestBumpVersion (5)
test_lifecycle.py: test_11_extract_sp (3 cases), test_12_commit_validation (6 cases)
test_release_gate.py: TestBumpVersion (6 overlapping cases)
```

**Acceptance Criteria:**
- [ ] Each production function is tested in exactly ONE test file (the most thorough one)
- [ ] Duplicate test methods in other files are removed or converted to regression-specific tests with distinct scenarios
- [ ] Total test count drops by ~20-30 but no coverage is lost
- [ ] All remaining tests pass

**Validation Command:**
```bash
grep -rn "def test_.*extract_sp\|def test_.*validate_message\|def test_.*bump_version" tests/ | wc -l
# After fix: each function tested in one file only
```

---

### BH-016: gh() 30-second timeout too short for paginated queries
**Severity:** MEDIUM
**Category:** `bug/logic`
**Location:** `scripts/validate_config.py:35`
**Status:** 🟢 RESOLVED

**Problem:** The `gh()` helper uses `timeout=30`. Operations like `gh issue create` with long bodies, `gh release create` with binary uploads, or `gh api --paginate` on large datasets can exceed 30 seconds, raising `RuntimeError` and aborting the operation.

**Evidence:**
```python
# validate_config.py:35
result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
```

**Acceptance Criteria:**
- [ ] `gh()` accepts an optional `timeout` parameter with a sensible default (60-120s)
- [ ] Callers that do pagination or large uploads pass higher timeouts
- [ ] Test: verify custom timeout is propagated to subprocess.run

**Validation Command:**
```bash
grep -n "timeout=" scripts/validate_config.py | head -5
```

---

### BH-017: CHEATSHEET.md + CLAUDE.md say "line numbers" but content uses § anchors
**Severity:** MEDIUM
**Category:** `doc/drift`
**Location:** `CHEATSHEET.md:3`, `CLAUDE.md:32-33`
**Status:** 🟢 RESOLVED
**Pattern:** PAT-003

**Problem:** Both files describe CHEATSHEET.md as providing "line-number indices" but the actual content uses § anchor references exclusively. No line numbers appear in the file.

**Acceptance Criteria:**
- [ ] Description updated to say "anchor-based indices" or "§-anchor indices" instead of "line-number indices"
- [ ] Both CLAUDE.md and CHEATSHEET.md are consistent in their description

**Validation Command:**
```bash
grep -in "line.number" CHEATSHEET.md CLAUDE.md
# After fix: no matches
```

---

### BH-018: CLAUDE.md claims tracking-formats.md has "burndown format" — it doesn't
**Severity:** MEDIUM
**Category:** `doc/drift`
**Location:** `CLAUDE.md:81`
**Status:** 🟢 RESOLVED
**Pattern:** PAT-003

**Problem:** CLAUDE.md Reference Files table says tracking-formats.md contains "SPRINT-STATUS.md format, story tracking file YAML frontmatter, burndown format". The file has SPRINT-STATUS.md format and story YAML frontmatter, but no burndown format definition. The burndown format is defined only implicitly by `update_burndown.py`.

**Acceptance Criteria:**
- [ ] Either: add a burndown format section to tracking-formats.md, OR: remove "burndown format" from CLAUDE.md description
- [ ] CLAUDE.md accurately reflects tracking-formats.md content

**Validation Command:**
```bash
grep -i "burndown" skills/sprint-run/references/tracking-formats.md | head -5
```

---

### BH-019: CHEATSHEET.md config structure missing team/insights.md
**Severity:** MEDIUM
**Category:** `doc/drift`
**Location:** `CHEATSHEET.md:481-493`
**Status:** 🟢 RESOLVED
**Pattern:** PAT-003

**Problem:** CHEATSHEET.md's config structure listing omits `team/insights.md`, which CLAUDE.md correctly includes. The insights file is created during kickoff and referenced by implementer.md and reviewer.md agent templates.

**Acceptance Criteria:**
- [ ] CHEATSHEET.md config structure includes `team/insights.md`
- [ ] Both CLAUDE.md and CHEATSHEET.md config structures are consistent

**Validation Command:**
```bash
grep "insights" CHEATSHEET.md
# After fix: should show insights.md in config structure
```

---

### BH-020: README story table format omits optional epic column
**Severity:** MEDIUM
**Category:** `doc/drift`
**Location:** `README.md:353`
**Status:** 🟢 RESOLVED
**Pattern:** PAT-003

**Problem:** README shows 5-column story table format: `| US-NNNN | title | saga | SP | priority |`. Code supports an optional 6th column for epic (E-XXXX). Users won't discover epic column support from the README alone.

**Acceptance Criteria:**
- [ ] README shows both 5-column and 6-column formats, noting the epic column is optional
- [ ] Example includes at least one row with the epic column

**Validation Command:**
```bash
grep -A3 "US-NNNN\|US-0" README.md | head -10
```

---

### BH-021: README sprint-monitor description omits drift detection and mid-sprint check-in
**Severity:** MEDIUM
**Category:** `doc/drift`
**Location:** `README.md:342,265-280`
**Status:** 🟢 RESOLVED
**Pattern:** PAT-003

**Problem:** README describes sprint-monitor as "Checks CI status, open PRs, and burndown." The actual skill also includes Step 1.5 (branch divergence + direct push detection) and Step 2.5 (mid-sprint check-in ceremony). Two monitoring features are invisible in user-facing docs.

**Acceptance Criteria:**
- [ ] README mentions drift detection (branch divergence monitoring)
- [ ] README mentions mid-sprint check-in capability
- [ ] Skills table row updated to reflect full feature set

**Validation Command:**
```bash
grep -i "drift\|diverge\|mid-sprint" README.md
# After fix: should show mentions of these features
```

---

### BH-022: 15+ production functions have zero test coverage
**Severity:** MEDIUM
**Category:** `test/missing`
**Location:** multiple files
**Status:** 🟢 RESOLVED

**Problem:** At least 15 production functions are never directly tested: `validate_config.main()`, `sprint_init.main()`, `commit.run_commit()`, `commit.main()`, `sprint_analytics.main()`, `validate_config.list_milestone_issues()`, `validate_config._print_errors()`, `validate_config.get_ci_commands()`, and several TOML parser internal functions (`_has_closing_bracket`, `_count_trailing_backslashes`, `_unescape_toml_string`, `_strip_inline_comment`, `_parse_value`). Additionally, `check_prerequisites()` has 3 copies across skill scripts, none tested.

**Acceptance Criteria:**
- [ ] At minimum: `run_commit()`, `sprint_analytics.main()`, and `list_milestone_issues()` have direct tests
- [ ] At minimum: the 3 `check_prerequisites()` copies have at least one test
- [ ] TOML parser internals are exercised through adversarial `parse_simple_toml` tests (edge cases for escaping, brackets, comments)

**Validation Command:**
```bash
grep -rn "def run_commit\|def list_milestone_issues\|def check_prerequisites" scripts/ skills/ | wc -l
grep -rn "run_commit\|list_milestone_issues\|check_prerequisites" tests/ | wc -l
```

---

### BH-023: remove_generated prompts stdin without TTY check
**Severity:** MEDIUM
**Category:** `bug/error-handling`
**Location:** `scripts/sprint_teardown.py:243`
**Status:** 🟢 RESOLVED
**Pattern:** PAT-002

**Problem:** `remove_generated` calls `input()` for confirmation without checking if stdin is a TTY. If invoked non-interactively (piped, from a subprocess), `input()` raises `EOFError` with no handler.

**Acceptance Criteria:**
- [ ] `input()` call is wrapped in `try/except EOFError` or guarded by `sys.stdin.isatty()`
- [ ] Non-interactive invocation produces a clear error message, not a traceback

**Validation Command:**
```bash
grep -n "input()" scripts/sprint_teardown.py
# After fix: should show try/except or isatty guard
```

---

### BH-024: compute_review_rounds fetches ALL PRs, silently truncated at 500
**Severity:** LOW
**Category:** `bug/logic`
**Location:** `scripts/sprint_analytics.py:83-87`
**Status:** 🟢 RESOLVED

**Problem:** `gh pr list --state all --limit 500` fetches all PRs repo-wide, then filters client-side for milestone PRs. For repos with 500+ PRs, results are silently truncated and metrics are wrong.

**Acceptance Criteria:**
- [ ] Either: use `--search "milestone:N"` to filter server-side, OR: document the 500 PR limitation
- [ ] `warn_if_at_limit` result is checked and surfaced in the report

**Validation Command:**
```bash
grep -n "pr list" scripts/sprint_analytics.py | head -5
```

---

### BH-025: Duplicate _safe_int function in manage_epics.py and manage_sagas.py
**Severity:** LOW
**Category:** `design/duplication`
**Location:** `scripts/manage_epics.py:27`, `scripts/manage_sagas.py:26`
**Status:** 🟢 RESOLVED

**Problem:** Identical `_safe_int` implementations in two files. Should be shared.

**Acceptance Criteria:**
- [ ] Single `_safe_int` in `validate_config.py` (or left as-is if the duplication is intentional for independence)
- [ ] Both callers use the shared version

**Validation Command:**
```bash
grep -rn "_safe_int" scripts/
```

---

### BH-026: Duplicate ISO date parsing in 3 scripts
**Severity:** LOW
**Category:** `design/duplication`
**Location:** `skills/sprint-run/scripts/sync_tracking.py:104`, `skills/sprint-run/scripts/update_burndown.py:35`, `skills/sprint-monitor/scripts/check_status.py:153`
**Status:** 🟢 RESOLVED

**Problem:** Three different scripts implement `iso.replace("Z", "+00:00")` date parsing independently. Should be a shared helper.

**Acceptance Criteria:**
- [ ] Single `parse_iso_date` helper in `validate_config.py`
- [ ] All three callers use the shared version

**Validation Command:**
```bash
grep -rn 'replace.*"Z".*"+00:00"' scripts/ skills/
```

---

### BH-027: CLAUDE.md check_status.py row missing write_log() and main()
**Severity:** LOW
**Category:** `doc/drift`
**Location:** `CLAUDE.md:50`
**Status:** 🟢 RESOLVED
**Pattern:** PAT-003

**Problem:** CLAUDE.md Scripts table for check_status.py lists 5 functions but omits `write_log()` and `main()`, which have § anchors and are listed in CHEATSHEET.md.

**Acceptance Criteria:**
- [ ] CLAUDE.md check_status.py row includes `write_log()` and `main()`
- [ ] OR: consistent policy applied — if some scripts omit `main()`, none should list it

**Validation Command:**
```bash
grep "check_status" CLAUDE.md | head -3
```

---
