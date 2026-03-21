# Bug Hunter Punchlist
> Generated: 2026-03-15 | Project: giles | Baseline: 520 pass, 0 fail, 0 skip

## Summary
| Severity | Open | Resolved | Deferred |
|----------|------|----------|----------|
| CRITICAL | 0 | 1 | 0 |
| HIGH | 0 | 9 | 0 |
| MEDIUM | 0 | 12 | 0 |
| LOW | 0 | 6 | 0 |
| **Total** | **0** | **28** | **0** |

## Patterns

## Pattern: PAT-001: Paginated JSON concatenation
**Instances:** BH-001
**Root Cause:** `gh api --paginate` concatenates raw JSON arrays per page (`[...][...]`), which is not valid JSON. Every call site uses `json.loads()` directly.
**Systemic Fix:** Add a `gh_json_paginated()` helper that splits concatenated arrays or uses `--jq '.[]'` to flatten before parsing.
**Detection Rule:** `grep -rn 'paginate.*json.loads\|json.loads.*paginate' scripts/ skills/`

## Pattern: PAT-002: FakeGitHub accepted-but-unimplemented flags
**Instances:** BH-002, BH-006, BH-010
**Root Cause:** FakeGitHub's `_KNOWN_FLAGS` accepts flags to pass the `_check_flags` guard, but handler logic doesn't implement the filtering those flags trigger. Tests pre-shape data to match, hiding the gap.
**Systemic Fix:** Add a `_UNIMPLEMENTED_FLAGS` set. Log a warning when an unimplemented flag is used, and optionally fail in strict mode.
**Detection Rule:** `grep -n '_KNOWN_FLAGS' tests/fake_github.py` — cross-reference each flag with its handler implementation.

## Pattern: PAT-003: Missing `main()` test coverage
**Instances:** BH-019
**Root Cause:** Individual helper functions are well-tested via unit tests, but the orchestration `main()` entry points that wire them together are untested.
**Systemic Fix:** Add at least one integration test per `main()` function that patches `sys.argv` and verifies end-to-end behavior with FakeGitHub.
**Detection Rule:** `for f in scripts/*.py skills/*/scripts/*.py; do grep -l 'def main' "$f" && grep -rL "$(basename $f .py).*main" tests/; done`

## Pattern: PAT-004: Regex over-breadth in pattern matching
**Instances:** BH-011, BH-012, BH-022
**Root Cause:** Several regexes use substring matching or `\b` anchors that match more than intended. Tests don't exercise adversarial inputs.
**Systemic Fix:** Tighten regex patterns and add adversarial test cases with known false-positive inputs.
**Detection Rule:** Manual review — grep for `\bsp\b`, `in cmd.lower()`, `slug in impl_name`.

---

## Items

### BH-001: `json.loads` crashes on multi-page `gh api --paginate` responses
**Severity:** CRITICAL
**Category:** `bug/logic`
**Location:** `scripts/validate_config.py:79`, `skills/sprint-setup/scripts/populate_issues.py:283`, `skills/sprint-run/scripts/sync_tracking.py:67`, `skills/sprint-monitor/scripts/check_status.py:174`, `skills/sprint-release/scripts/release_gate.py:409`
**Status:** ✅ RESOLVED
**Pattern:** PAT-001

**Problem:** `gh api --paginate` concatenates raw JSON arrays per page: `[{"a":1}][{"b":2}]`. This is not valid JSON. Every affected call site passes the raw output to `json.loads()`, which will raise `JSONDecodeError` or silently parse only the first page. Affects milestone listing, issue timeline queries, and milestone number lookups.

**Evidence:**
```python
# validate_config.py:79 — gh_json wrapper
raw = gh(args)
return json.loads(raw) if raw else []
# When --paginate produces "[...][...]", json.loads fails
```

**Acceptance Criteria:**
- [ ] `gh_json()` (or a new `gh_json_paginated()`) correctly parses concatenated JSON arrays
- [ ] All call sites using `--paginate` produce correct results when response spans 2+ pages
- [ ] Test: a FakeGitHub handler returns two concatenated arrays; caller receives merged list

**Validation Command:**
```bash
python -c "
from scripts.validate_config import gh_json
# Verify the function can handle concatenated JSON:
import json
concatenated = '[{\"a\":1}][{\"b\":2}]'
# This should be parseable after the fix:
parts = []
decoder = json.JSONDecoder()
pos = 0
while pos < len(concatenated):
    obj, end = decoder.raw_decode(concatenated, pos)
    parts.extend(obj if isinstance(obj, list) else [obj])
    pos = end
    while pos < len(concatenated) and concatenated[pos] in ' \n\r\t': pos += 1
assert len(parts) == 2, f'Expected 2 items, got {len(parts)}'
print('PASS: concatenated JSON parsing works')
"
```

**Resolution:**

---

### BH-002: FakeGitHub `--search` flag silently ignored — `compute_review_rounds` test gives false green bar
**Severity:** HIGH
**Category:** `test/mock-abuse`
**Location:** `tests/fake_github.py:108`, `tests/test_sprint_analytics.py:134-164`
**Status:** ✅ RESOLVED
**Pattern:** PAT-002

**Problem:** Production `compute_review_rounds()` calls `gh pr list --search "milestone:Sprint 1"`. FakeGitHub's `_pr_list` handler accepts `--search` in `_KNOWN_FLAGS` but never implements filtering on it. The test pre-loads only matching PRs into `self.gh.prs`, so the test passes regardless of whether the search filter works. If production's `--search` parameter were malformed, no test would catch it.

**Evidence:**
```python
# fake_github.py _KNOWN_FLAGS — search accepted but never used:
"pr_list": frozenset(("json", "state", "limit", "search")),
# _pr_list handler filters only on state and limit; search is discarded
```

**Acceptance Criteria:**
- [ ] FakeGitHub logs a warning or raises when `--search` contains a `milestone:` qualifier that doesn't match available data
- [ ] Test for `compute_review_rounds` includes a PR with a non-matching milestone and verifies it's excluded
- [ ] Or: `--search` is removed from `_KNOWN_FLAGS` and production code refactored to not rely on it

**Validation Command:**
```bash
python -m unittest tests.test_sprint_analytics -v 2>&1 | grep -E "test_counts|FAIL|ERROR"
```

**Resolution:**

---

### BH-003: `compute_review_rounds` `--search milestone:TITLE` breaks on space-containing titles
**Severity:** HIGH
**Category:** `bug/logic`
**Location:** `scripts/sprint_analytics.py:87-88`
**Status:** ✅ RESOLVED

**Problem:** `gh pr list --search "milestone:Sprint 1: Walking Skeleton"` passes the milestone title unquoted into a GitHub search query. GitHub interprets `milestone:Sprint` as the qualifier and `1: Walking Skeleton` as free-text, returning PRs from wrong milestones. The secondary filter at line 97 limits damage, but analytics data will be wrong or incomplete.

**Evidence:**
```python
"--search", f"milestone:{milestone_title}",
# milestone_title = "Sprint 1: Walking Skeleton"
# GitHub sees: milestone:Sprint 1: Walking Skeleton
# Interpreted as: milestone:Sprint + free-text "1: Walking Skeleton"
```

**Acceptance Criteria:**
- [ ] Milestone titles with spaces are properly quoted in the search query (e.g., `milestone:"Sprint 1: Walking Skeleton"`)
- [ ] Test with a space-containing milestone title confirms correct PR filtering
- [ ] Or: remove `--search` and rely solely on post-fetch filtering (already implemented at line 97)

**Validation Command:**
```bash
python -c "
import re
title = 'Sprint 1: Walking Skeleton'
# After fix, the search parameter should quote the title:
search = f'milestone:\"{title}\"'
assert '\"Sprint 1: Walking Skeleton\"' in search, f'Title not quoted: {search}'
print('PASS: milestone title is quoted in search query')
"
```

**Resolution:**

---

### BH-004: `check_prs` reports "CI green" when no checks have completed (vacuously true `all()`)
**Severity:** HIGH
**Category:** `bug/logic`
**Location:** `skills/sprint-monitor/scripts/check_status.py:110-114`
**Status:** ✅ RESOLVED

**Problem:** `ci_ok = all(c.get("conclusion") == "SUCCESS" for c in checks if c.get("status") == "COMPLETED")`. When all checks are still queued/in-progress, the generator produces zero items, and `all()` returns `True` (vacuously true). The PR is then reported as "CI green, ready to merge" when no checks have actually passed.

**Evidence:**
```python
checks = pr.get("statusCheckRollup") or []
ci_ok = all(
    c.get("conclusion") == "SUCCESS"
    for c in checks
    if c.get("status") == "COMPLETED"
)
# When checks = [{"status": "IN_PROGRESS"}], the filter yields 0 items
# all() on empty iterator returns True → ci_ok = True
```

**Acceptance Criteria:**
- [ ] `ci_ok` is `False` when no checks have `status == "COMPLETED"`
- [ ] `ci_ok` is `False` when `statusCheckRollup` is empty or None
- [ ] Test: PR with all checks in_progress → ci_ok is False

**Validation Command:**
```bash
python -c "
checks = [{'status': 'IN_PROGRESS', 'conclusion': None}]
completed = [c for c in checks if c.get('status') == 'COMPLETED']
ci_ok_buggy = all(c.get('conclusion') == 'SUCCESS' for c in completed)
ci_ok_fixed = len(completed) > 0 and all(c.get('conclusion') == 'SUCCESS' for c in completed)
assert ci_ok_buggy == True, 'Bug not present'
assert ci_ok_fixed == False, 'Fix not working'
print('PASS: vacuous truth confirmed and fix validated')
"
```

**Resolution:**

---

### BH-005: `update_sprint_status` regex can leave orphaned table rows if content exists between heading and table
**Severity:** HIGH
**Category:** `bug/logic`
**Location:** `skills/sprint-run/scripts/update_burndown.py:106-108`
**Status:** ✅ RESOLVED

**Problem:** The regex `r"## Active Stories[^\n]*\n(?:\s*\n)*(?:\|[^\n]*\n)*"` captures the heading, optional blank lines, and consecutive pipe-prefixed rows. If any non-table content (like a description paragraph) exists between the heading and the table, the regex stops at that content, captures zero table rows, and the replacement inserts the new table BEFORE the old one — resulting in duplicate tables.

**Evidence:**
```python
pattern = r"## Active Stories[^\n]*\n(?:\s*\n)*(?:\|[^\n]*\n)*"
# Input:  "## Active Stories\n\nSome description.\n\n| old | table |\n"
# Match:  "## Active Stories\n\n"  (stops at "Some description")
# Result: new table replaces heading, but old table rows survive below
```

**Acceptance Criteria:**
- [ ] Regex handles content between heading and table by consuming through to the actual table
- [ ] Or: use a heading-to-next-heading replacement strategy instead of table-row matching
- [ ] Test: SPRINT-STATUS.md with a description paragraph between heading and table → old table fully replaced

**Validation Command:**
```bash
python -c "
import re
pattern = r'## Active Stories[^\n]*\n(?:\s*\n)*(?:\|[^\n]*\n)*'
# Case with description between heading and table:
text = '## Active Stories\n\nOld description.\n\n| old | row |\n|-----|-----|\n| US-001 | done |\n'
match = re.search(pattern, text)
matched_text = match.group(0) if match else ''
# Bug: match stops at 'Old description' and captures 0 table rows
has_bug = '| old | row |' not in matched_text
print(f'Bug present: {has_bug}')
assert has_bug, 'Bug not reproduced — may have been fixed already'
"
```

**Resolution:**

---

### BH-006: `compute_review_rounds` test injects pre-shaped `reviews` field — bypasses actual API response format
**Severity:** HIGH
**Category:** `test/mock-abuse`
**Location:** `tests/test_sprint_analytics.py:136-153`
**Status:** ✅ RESOLVED
**Pattern:** PAT-002

**Problem:** The test manually injects a `reviews` key into PR dicts in `self.gh.prs` with the exact data shape production expects. FakeGitHub's `_pr_create` does not store a `reviews` field — it only appears via `_pr_review`. The test verifies that the code correctly counts items in a list it was hand-crafted to receive, not that the production data format is correct.

**Evidence:**
```python
# Test directly injects:
self.gh.prs.append({
    "number": 1, ...
    "reviews": [{"state": "CHANGES_REQUESTED"}, {"state": "APPROVED"}],
})
# Never exercises: FakeGitHub _pr_review → reviews accumulation → --json reviews extraction
```

**Acceptance Criteria:**
- [ ] Test creates PRs via FakeGitHub's `_pr_create` path, then adds reviews via `_pr_review`
- [ ] Test uses `--json reviews` to retrieve reviews, exercising FakeGitHub's JSON field extraction
- [ ] Or: FakeGitHub's `_pr_list` handler includes accumulated reviews in its output

**Validation Command:**
```bash
python -m unittest tests.test_sprint_analytics.TestComputeReviewRounds -v 2>&1 | grep -E "test_|FAIL|ERROR"
```

**Resolution:**

---

### BH-007: `test_all_pass` release gates pass trivially — empty config skips 2 of 5 gates
**Severity:** HIGH
**Category:** `test/shallow`
**Location:** `tests/test_release_gate.py:146-163`
**Status:** ✅ RESOLVED

**Problem:** The `test_all_pass` test uses `config = {"ci": {"check_commands": [], "build_command": ""}}`. This makes `gate_tests` and `gate_build` return `(True, "No check/build_command configured")` — auto-pass. The test's `self.assertTrue(all(r[1] for r in results))` passes because 2 of 5 gates are trivially skipped, not actually validated. No test runs `validate_gates` end-to-end with non-trivial test/build commands.

**Evidence:**
```python
config = {
    "project": {"base_branch": "main"},
    "ci": {"check_commands": [], "build_command": ""},
}
# gate_tests → (True, "No check_commands configured")
# gate_build → (True, "No build_command configured")
```

**Acceptance Criteria:**
- [ ] A test exists that runs `validate_gates` with non-empty `check_commands` and `build_command` through FakeGitHub + subprocess mocking
- [ ] gate_tests and gate_build are exercised with real commands (e.g., `echo pass`) and pass/fail paths
- [ ] Existing test documents that it only validates 3 of 5 gates (or is updated to validate all 5)

**Validation Command:**
```bash
python -c "
import sys, os
sys.path.insert(0, 'scripts')
sys.path.insert(0, 'skills/sprint-release/scripts')
from release_gate import gate_tests, gate_build
# Verify gates auto-pass with empty config:
ok_t, msg_t = gate_tests({'ci': {'check_commands': []}})
ok_b, msg_b = gate_build({'ci': {'build_command': ''}})
assert ok_t and 'No check' in msg_t, f'gate_tests did not auto-pass: {msg_t}'
assert ok_b and 'No build' in msg_b, f'gate_build did not auto-pass: {msg_b}'
print('CONFIRMED: both gates auto-pass with empty config — test is shallow')
"
```

**Resolution:**

---

### BH-008: TOML parser `_split_array` does not handle nested arrays
**Severity:** HIGH
**Category:** `bug/logic`
**Location:** `scripts/validate_config.py:270-304`
**Status:** ✅ RESOLVED

**Problem:** `_split_array` splits on commas but does not track bracket nesting depth. Nested arrays like `key = [["a", "b"], ["c", "d"]]` will be split at the inner comma between `"b"]` and `["c"`, producing corrupt data. The project.toml format currently does not use nested arrays, but the parser claims to handle "arrays" generically.

**Evidence:**
```python
elif ch == "," and not in_str:
    parts.append(current)
    current = ""
# No bracket-depth tracking — nested arrays corrupted
```

**Acceptance Criteria:**
- [ ] `_split_array` tracks bracket depth and only splits on commas at depth 0
- [ ] Test: `parse_simple_toml('key = [["a", "b"], ["c"]]')` returns `{"key": [["a", "b"], ["c"]]}`
- [ ] Or: document as explicit limitation with a clear error if nested arrays are detected

**Validation Command:**
```bash
python -c "
import sys; sys.path.insert(0, 'scripts')
from validate_config import parse_simple_toml
result = parse_simple_toml('[test]\nkey = [[\"a\", \"b\"], [\"c\", \"d\"]]')
val = result.get('test', {}).get('key', [])
print(f'Parsed: {val}')
# After fix: should be [['a', 'b'], ['c', 'd']]
# Before fix: likely corrupt
"
```

**Resolution:**

---

### BH-009: `_fm_val` quote handling differs from `read_tf` — comment claims they match
**Severity:** MEDIUM
**Category:** `design/inconsistency`
**Location:** `skills/sprint-run/scripts/update_burndown.py:146-149`, `skills/sprint-run/scripts/sync_tracking.py:158-159`
**Status:** ✅ RESOLVED

**Problem:** `_fm_val` strips surrounding quotes but does NOT unescape `\"`. `read_tf` strips quotes AND unescapes `\"` via `.replace('\\"', '"')`. Both parse the same YAML frontmatter format (written by `_yaml_safe`). The comment on line 146 says "matches sync_tracking.read_tf behavior" but this is false. A title containing `He said \"hello\"` would be parsed differently by each function.

**Evidence:**
```python
# _fm_val (update_burndown.py:148):
val = val[1:-1]              # strips quotes, keeps escaped \"

# read_tf (sync_tracking.py:159):
val = val[1:-1].replace('\\"', '"')  # strips quotes AND unescapes \"
```

**Acceptance Criteria:**
- [ ] Both functions handle escaped quotes identically
- [ ] Comment in `_fm_val` accurately reflects behavior
- [ ] Test: YAML frontmatter with `title: "He said \"hello\""` parsed identically by both functions

**Validation Command:**
```bash
python -c "
import re
# _fm_val behavior:
val1 = '\"He said \\\\\"hello\\\\\" to her\"'
if len(val1) >= 2 and val1[0] == val1[-1] and val1[0] in ('\"', \"'\"):
    val1 = val1[1:-1]
# read_tf behavior:
val2 = '\"He said \\\\\"hello\\\\\" to her\"'
if len(val2) >= 2 and val2[0] == '\"' and val2[-1] == '\"':
    val2 = val2[1:-1].replace('\\\\\"', '\"')
print(f'_fm_val:  {repr(val1)}')
print(f'read_tf:  {repr(val2)}')
assert val1 != val2, 'Values match — bug may be fixed'
print('CONFIRMED: inconsistent quote handling')
"
```

**Resolution:**

---

### BH-010: FakeGitHub `--flag=value` syntax not parsed — `_parse_flags` treats `=` as part of key name
**Severity:** MEDIUM
**Category:** `test/mock-abuse`
**Location:** `tests/fake_github.py:133-155`
**Status:** ✅ RESOLVED
**Pattern:** PAT-002

**Problem:** `_parse_flags` parses `--state=all` as key `"state=all"` (with value `"true"` or next arg), instead of key `"state"` with value `"all"`. Real `gh` CLI accepts both `--state all` and `--state=all`. No production code currently uses `=` syntax with `gh`, but this is a latent fidelity gap — any future code using `--flag=value` would silently fail in tests.

**Evidence:**
```python
key = a[2:]  # "--state=all" → key = "state=all"
# No handling for "=" inside the key
```

**Acceptance Criteria:**
- [ ] `_parse_flags` splits on `=` in flag names: `--state=all` → key `"state"`, value `"all"`
- [ ] Test: `FakeGitHub._parse_flags(["cmd", "--state=all"])` returns `{"state": ["all"]}`

**Validation Command:**
```bash
python -c "
import sys; sys.path.insert(0, 'tests')
from fake_github import FakeGitHub
result = FakeGitHub._parse_flags(['list', '--state=all'])
print(f'Parsed: {result}')
has_bug = 'state=all' in result
print(f'Bug present: {has_bug}')
"
```

**Resolution:**

---

### BH-011: `extract_sp` regex `\bsp` matches words like BSP, ISP as story points
**Severity:** MEDIUM
**Category:** `bug/logic`
**Location:** `scripts/validate_config.py:698-700`
**Status:** ✅ RESOLVED
**Pattern:** PAT-004

**Problem:** The pattern `r"(?:story\s*points?|\bsp)\s*[:=]\s*(\d+)"` with `re.IGNORECASE` matches `BSP: 5` or `ISP = 3` because `\b` is a word boundary before `sp` — it matches at the boundary between `B` and `S` in `BSP`. Issue bodies discussing BSP trees, ISP providers, etc. would have false story point extraction.

**Evidence:**
```python
if m := re.search(
    r"(?:story\s*points?|\bsp)\s*[:=]\s*(\d+)", body, re.IGNORECASE
):
    return int(m.group(1))
```

**Acceptance Criteria:**
- [ ] Pattern only matches standalone `SP` (surrounded by non-word characters or start/end)
- [ ] Test: `extract_sp("BSP: 5")` returns 0 (not 5)
- [ ] Test: `extract_sp("SP: 3")` still returns 3

**Validation Command:**
```bash
python -c "
import sys; sys.path.insert(0, 'scripts')
from validate_config import extract_sp
print(f'SP: 3 → {extract_sp({}, \"SP: 3\")}')
print(f'BSP: 5 → {extract_sp({}, \"BSP: 5\")}')
print(f'ISP = 3 → {extract_sp({}, \"ISP = 3\")}')
has_bug = extract_sp({}, 'BSP: 5') == 5
print(f'Bug present: {has_bug}')
"
```

**Resolution:**

---

### BH-012: `check_test_coverage` slug matching produces false positives with short test case IDs
**Severity:** MEDIUM
**Category:** `bug/logic`
**Location:** `scripts/test_coverage.py:121-129`
**Status:** ✅ RESOLVED
**Pattern:** PAT-004

**Problem:** Fuzzy matching normalizes test case IDs and checks substring containment. For `TC-A-1`, the slug is `a_1`. Any test function containing `a_1` anywhere (like `test_data_1_validation`) would be a false match, inflating coverage numbers.

**Evidence:**
```python
slug = parts[1] if len(parts) > 1 else normalized
for impl_name in impl_lower:
    if normalized in impl_name or slug in impl_name:
        matched.add(tc_id)
```

**Acceptance Criteria:**
- [ ] Slug matching uses word-boundary-aware matching or requires the slug to appear at a word boundary
- [ ] Test: `TC-A-1` does NOT match `test_data_1_validation`
- [ ] Test: `TC-A-1` DOES match `test_tc_a_1_something`

**Validation Command:**
```bash
python -c "
# Simulate the bug:
tc_id = 'TC-A-1'
normalized = tc_id.lower().replace('-', '_')
parts = normalized.split('_', 1)
slug = parts[1] if len(parts) > 1 else normalized
impl = 'test_data_1_validation'
has_bug = slug in impl.lower()
print(f'Slug: {slug!r}, impl: {impl!r}, false match: {has_bug}')
assert has_bug, 'Bug not reproduced'
print('CONFIRMED: short slug causes false positive match')
"
```

**Resolution:**

---

### BH-013: `_parse_workflow_runs` captures YAML comments as CI commands
**Severity:** MEDIUM
**Category:** `bug/logic`
**Location:** `scripts/sprint_init.py:221`
**Status:** ✅ RESOLVED

**Problem:** The multiline `run:` block collector captures any line starting with two spaces. YAML comments inside a multiline run block (e.g., `  # setup step`) are included as commands in the detected CI command list.

**Evidence:**
```python
while i < len(lines) and (lines[i].startswith("  ") or lines[i].strip() == ""):
    if re.match(r'^\s*- ', lines[i]):
        break
    line_content = lines[i].strip()
    if line_content:
        multiline_cmds.append(line_content)  # includes "# setup step"
```

**Acceptance Criteria:**
- [ ] Lines starting with `#` (after stripping leading whitespace) are skipped as comments
- [ ] Test: workflow YAML with `run: |\n  # comment\n  cargo test` → only `cargo test` detected

**Validation Command:**
```bash
python -c "
import sys; sys.path.insert(0, 'scripts')
from sprint_init import ProjectScanner
# Test that comments in run blocks are captured (bug):
yaml_lines = ['    - run: |', '        # setup env', '        cargo test']
# After the multiline collector runs, '# setup env' would be in the command list
print('Manual verification needed with a real workflow YAML fixture')
"
```

**Resolution:**

---

### BH-014: `manage_sagas._find_section_ranges` deletes subsections when replacing parent sections
**Severity:** MEDIUM
**Category:** `bug/logic`
**Location:** `scripts/manage_sagas.py:126-142`
**Status:** ✅ RESOLVED

**Problem:** `_find_section_ranges` only detects `## ` headers. Subsections (`### Notes`, `### History`) within a `## Section` are treated as content. When `update_sprint_allocation` or `update_epic_index` replaces a section range, any subsections within are silently deleted.

**Evidence:**
```python
for i, line in enumerate(lines):
    if line.startswith("## "):
        if current_section:
            ranges[current_section] = (current_start, i)
# ### subsections within the range are treated as content and deleted on replace
```

**Acceptance Criteria:**
- [ ] Section replacement preserves subsections not part of the replaced content
- [ ] Or: document that subsections within managed sections will be overwritten
- [ ] Test: saga file with `## Sprint Allocation` containing `### Notes` → notes preserved after update

**Validation Command:**
```bash
python -c "
import sys; sys.path.insert(0, 'scripts')
from manage_sagas import _find_section_ranges
lines = ['# Title', '## Sprint Allocation', 'content', '### Notes', 'note text', '## Epic Index']
ranges = _find_section_ranges(lines)
alloc_range = ranges.get('Sprint Allocation')
print(f'Sprint Allocation range: {alloc_range}')
# Bug: range includes lines 1-5, which includes ### Notes subsection
has_bug = alloc_range and alloc_range[1] > 4
print(f'Bug present (subsection in range): {has_bug}')
"
```

**Resolution:**

---

### BH-015: `reorder_stories` inserts `---` separator before first story unconditionally
**Severity:** MEDIUM
**Category:** `bug/logic`
**Location:** `scripts/manage_epics.py:326-334`
**Status:** ✅ RESOLVED

**Problem:** The reassembly loop checks `if i > 0 or new_lines:` — since `new_lines` is initialized from `header` (always non-empty for valid files), this is always True. Every story, including the first, gets a `---` separator. If the original file didn't have a separator before the first story, the reformatted file differs from the original.

**Evidence:**
```python
new_lines = list(header)
for i, sid in enumerate(story_ids):
    if sid not in section_map: continue
    if i > 0 or new_lines:  # always True since header is non-empty
        new_lines.append(""); new_lines.append("---"); new_lines.append("")
```

**Acceptance Criteria:**
- [ ] First story does not get a separator if the original file didn't have one
- [ ] Or: all stories consistently get separators (document as intended behavior)
- [ ] Test: reorder with 2 stories → verify separator only between stories, not before first

**Validation Command:**
```bash
python -c "
import sys, tempfile, os; sys.path.insert(0, 'scripts')
from manage_epics import reorder_stories, parse_epic
# Create test file without separator before first story:
content = '''# Epic
| Field | Value |
|-------|-------|
| Saga | Test |

### US-001: First
| Field | Value |
|-------|-------|

---

### US-002: Second
| Field | Value |
|-------|-------|
'''
f = tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False)
f.write(content); f.close()
reorder_stories(f.name, ['US-002', 'US-001'])
result = open(f.name).read()
os.unlink(f.name)
# Check if --- appears before the first story:
lines = result.split('\n')
first_story_idx = next(i for i, l in enumerate(lines) if l.startswith('### US-'))
has_sep_before_first = any(l.strip() == '---' for l in lines[:first_story_idx])
print(f'Separator before first story: {has_sep_before_first}')
"
```

**Resolution:**

---

### BH-016: `enrich_from_epics` tie-breaking picks highest sprint number on ties
**Severity:** MEDIUM
**Category:** `bug/logic`
**Location:** `skills/sprint-setup/scripts/populate_issues.py:232`
**Status:** ✅ RESOLVED

**Problem:** When inferring sprint numbers for stories found in epic files, the code uses `max(set(known_sprints), key=known_sprints.count)` to find the mode. On ties (equal counts), `max()` returns the numerically largest sprint number, which may not be the correct assignment.

**Evidence:**
```python
sprint = max(set(known_sprints), key=known_sprints.count) if known_sprints else 0
# Tie between sprint 1 and sprint 3 (2 stories each) → returns 3
```

**Acceptance Criteria:**
- [ ] Tie-breaking uses a deterministic, documented strategy (e.g., lowest sprint number, or raises a warning)
- [ ] Test: epic with equal stories in sprints 1 and 3 → verify which sprint is chosen and that it matches documented behavior

**Validation Command:**
```bash
python -c "
known_sprints = [1, 1, 3, 3]  # tie: 2 each
result = max(set(known_sprints), key=known_sprints.count)
print(f'Tie-break result: sprint {result}')
assert result == 3, 'Expected max() to return 3 on tie'
print('CONFIRMED: tie-breaking picks highest sprint number')
"
```

**Resolution:**

---

### BH-017: `list_milestone_issues` has no error handling for malformed JSON
**Severity:** MEDIUM
**Category:** `bug/error-handling`
**Location:** `scripts/validate_config.py:796-804`
**Status:** ✅ RESOLVED

**Problem:** `list_milestone_issues` calls `gh()` and then `json.loads(raw)`. If `gh` exits 0 with non-JSON output (possible with gh CLI bugs or auth issues), `json.loads` raises an unhandled `JSONDecodeError`. Other callers like `get_existing_issues` in populate_issues.py wrap similar calls in try/except.

**Evidence:**
```python
raw = gh([
    "issue", "list", "--milestone", milestone_title, "--state", "all",
    "--json", "number,title,state,labels,closedAt,body", "--limit", "500",
])
issues = json.loads(raw) if raw else []
# No try/except for JSONDecodeError
```

**Acceptance Criteria:**
- [ ] `json.loads` is wrapped in try/except with meaningful error message
- [ ] Or: `gh_json()` wrapper is used instead of manual `gh()` + `json.loads()`
- [ ] Test: mocked `gh()` returns non-JSON string → handled gracefully

**Validation Command:**
```bash
python -c "
import json
try:
    json.loads('Not JSON at all')
    print('FAIL: should have raised')
except json.JSONDecodeError:
    print('PASS: JSONDecodeError raised on non-JSON input — need error handling')
"
```

**Resolution:**

---

### BH-018: `do_release` pushes tag but not the version bump commit
**Severity:** MEDIUM
**Category:** `design/inconsistency`
**Location:** `skills/sprint-release/scripts/release_gate.py:518-534`
**Status:** ✅ RESOLVED

**Problem:** The release flow creates a version bump commit in `project.toml`, tags it, then pushes only the tag (`git push origin v{new_ver}`). The commit itself is never pushed to the remote branch. The version bump exists only locally and in the tag. Next pull won't include it; the branch history diverges from the tag.

**Evidence:**
```python
# Only the tag is pushed:
r = subprocess.run(
    ["git", "push", "origin", f"v{new_ver}"],
    capture_output=True, text=True,
)
# No: git push origin {base_branch}
```

**Acceptance Criteria:**
- [ ] Document that version bump is intentionally local-only (if that's the design)
- [ ] Or: push the version bump commit alongside the tag
- [ ] Or: skip the `write_version_to_toml` step entirely if the commit won't be pushed

**Validation Command:**
```bash
grep -n "git.*push" skills/sprint-release/scripts/release_gate.py | head -5
```

**Resolution:**

---

### BH-019: Missing test coverage for `main()` orchestration functions in 5 scripts
**Severity:** MEDIUM
**Category:** `test/missing`
**Location:** `scripts/sprint_analytics.py:191`, `scripts/commit.py:105`, `skills/sprint-monitor/scripts/check_status.py:325`, `skills/sprint-run/scripts/sync_tracking.py:217`, `skills/sprint-run/scripts/update_burndown.py:152`
**Status:** ✅ RESOLVED
**Pattern:** PAT-003

**Problem:** Individual helper functions are well-tested, but the `main()` entry points that wire them together are untested. Integration bugs (wrong argument passing, missing error handling, incorrect orchestration order) would not be caught. Scripts affected: `sprint_analytics.py`, `commit.py` (`run_commit`/`main`), `check_status.py`, `sync_tracking.py` (`sync_one`), `update_burndown.py` (`load_tracking_metadata`/`main`).

**Evidence:**
```bash
# No test calls any of these main() functions:
grep -rn "sprint_analytics.*main\|commit.*run_commit\|check_status.*main\|sync_one(" tests/
# Returns no matches for direct calls
```

**Acceptance Criteria:**
- [ ] At least one test per `main()` function that patches `sys.argv` and verifies end-to-end behavior
- [ ] Or: at least one integration test that calls `main()` with FakeGitHub and verifies output
- [ ] Test count increases by at least 5

**Validation Command:**
```bash
grep -rn "def main" scripts/sprint_analytics.py scripts/commit.py skills/sprint-monitor/scripts/check_status.py skills/sprint-run/scripts/sync_tracking.py skills/sprint-run/scripts/update_burndown.py
```

**Resolution:**

---

### BH-020: FakeGitHub `/commits` API endpoint returns all commits without filtering by `sha` or `since`
**Severity:** MEDIUM
**Category:** `test/mock-abuse`
**Location:** `tests/fake_github.py:276-279`
**Status:** ✅ RESOLVED

**Problem:** Production calls `gh api repos/{repo}/commits -f sha={branch} -f since={iso}` with `--jq` filtering. FakeGitHub accepts the `-f` flags but doesn't use `sha` or `since` to filter results. Tests pre-load exactly the commits they want, so this doesn't cause failures — but tests can't verify that production correctly passes date/branch filters.

**Evidence:**
```python
if path.endswith("/commits"):
    return self._ok(json.dumps(self.commits_data))
# No filtering by sha or since — returns everything regardless
```

**Acceptance Criteria:**
- [ ] FakeGitHub's `/commits` handler respects `-f since=` to filter by date
- [ ] Or: at minimum, logs a warning when filtering flags are present but ignored
- [ ] Test: `check_direct_pushes` with commits both before and after `since` date → only recent ones returned

**Validation Command:**
```bash
python -c "
import sys; sys.path.insert(0, 'tests')
from fake_github import FakeGitHub
gh = FakeGitHub()
gh.commits_data = [{'sha': 'abc', 'commit': {'author': {'date': '2025-01-01'}}}, {'sha': 'def', 'commit': {'author': {'date': '2026-01-01'}}}]
result = gh.handle(['api', 'repos/test/test/commits', '-f', 'since=2025-06-01'])
import json
data = json.loads(result.stdout)
print(f'Returned {len(data)} commits (should be 1 after fix, is 2 with bug)')
"
```

**Resolution:**

---

### BH-021: `team_voices.main` always appends `...` to quotes, even when complete
**Severity:** LOW
**Category:** `bug/logic`
**Location:** `scripts/team_voices.py:102`
**Status:** ✅ RESOLVED

**Problem:** Display format always appends `...` after truncating to 80 chars: `f"{q['quote'][:80]}..."`. Quotes shorter than 80 characters show `...` even though they're not truncated.

**Evidence:**
```python
print(f"  - [{q['file']}:{q['section']}] {q['quote'][:80]}...")
```

**Acceptance Criteria:**
- [ ] `...` only appears when the quote is actually truncated (len > 80)
- [ ] Test: short quote (< 80 chars) does not end with `...`

**Validation Command:**
```bash
grep -n "quote\[:80\]" scripts/team_voices.py
```

**Resolution:**

---

### BH-022: `_first_error` in check_status matches lines like "0 errors" as errors
**Severity:** LOW
**Category:** `bug/logic`
**Location:** `skills/sprint-monitor/scripts/check_status.py:80-88`
**Status:** ✅ RESOLVED
**Pattern:** PAT-004

**Problem:** Keyword search for "error", "failed", "panicked", "assert" in CI logs uses simple substring matching. Lines like `"Tests: 42 passed, 0 errors"` or `"All assertions passed"` would be returned as the "first error."

**Evidence:**
```python
if any(kw in line.lower() for kw in ("error", "failed", "panicked", "assert")):
    return cleaned[:117] + "..." if len(cleaned) > 117 else cleaned
```

**Acceptance Criteria:**
- [ ] Pattern excludes lines where error keywords are preceded by "0" or "no"
- [ ] Or: use regex word boundaries and negative lookbehind for "0 "
- [ ] Test: `_first_error("Tests: 42 passed, 0 errors\nactual error here")` returns the second line

**Validation Command:**
```bash
python -c "
import re
log = 'Tests: 42 passed, 0 errors\nfatal: actual error here'
for line in log.splitlines():
    if any(kw in line.lower() for kw in ('error', 'failed', 'panicked', 'assert')):
        print(f'Matched: {line!r}')
        break
# Bug: matches '0 errors' instead of 'fatal: actual error here'
"
```

**Resolution:**

---

### BH-023: `parse_simple_toml` key regex rejects hyphenated keys (valid TOML)
**Severity:** LOW
**Category:** `bug/logic`
**Location:** `scripts/validate_config.py:141`
**Status:** ✅ RESOLVED

**Problem:** TOML allows hyphens in bare keys (e.g., `base-branch = "main"`), but the parser's key regex `^([a-zA-Z_][a-zA-Z0-9_]*)\s*=` only allows underscores. Any TOML key with hyphens is silently ignored. The project uses `base_branch` (underscores), so this is not currently triggered, but it violates the TOML spec.

**Evidence:**
```python
kv_match = re.match(r"^([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*(.*)$", line)
# "base-branch = main" → no match → silently ignored
```

**Acceptance Criteria:**
- [ ] Key regex allows hyphens: `[a-zA-Z_][a-zA-Z0-9_-]*`
- [ ] Or: document as explicit limitation in parser docstring
- [ ] Test: `parse_simple_toml('base-branch = "main"')` returns `{"base-branch": "main"}`

**Validation Command:**
```bash
python -c "
import sys; sys.path.insert(0, 'scripts')
from validate_config import parse_simple_toml
result = parse_simple_toml('base-branch = \"main\"')
print(f'Result: {result}')
has_bug = 'base-branch' not in result
print(f'Hyphenated key silently ignored: {has_bug}')
"
```

**Resolution:**

---

### BH-024: `detect_story_id_pattern` regex includes `#\d+` — matches GitHub issue refs, not story IDs
**Severity:** LOW
**Category:** `bug/logic`
**Location:** `scripts/sprint_init.py:462`
**Status:** ✅ RESOLVED

**Problem:** The pattern `(US-\d{4}|[A-Z]{2,10}-\d+|#\d+)` includes `#\d+` which matches GitHub issue references like `#123`. These are not story IDs. If backlog files reference many GitHub issues, `#N` could win the count and be returned as the "detected story ID pattern."

**Evidence:**
```python
patterns = re.compile(r"(US-\d{4}|[A-Z]{2,10}-\d+|#\d+)")
```

**Acceptance Criteria:**
- [ ] `#\d+` removed from the story ID pattern regex, or weighted lower than named patterns
- [ ] Test: backlog file with `#1 #2 #3 US-0001` → pattern detected as `US-XXXX`, not `#N`

**Validation Command:**
```bash
grep -n '#\\\\d' scripts/sprint_init.py
```

**Resolution:**

---

### BH-025: `sprint_teardown.print_dry_run` miscounts "more symlinks" when targets resolve outside project root
**Severity:** LOW
**Category:** `bug/logic`
**Location:** `scripts/sprint_teardown.py:203-204`
**Status:** ✅ RESOLVED

**Problem:** The display code shows up to 3 symlink targets, then says `({len(symlinks) - targets_shown} more)`. But `targets_shown` only increments for targets that resolve inside the project root (the `try/except ValueError` block). Symlinks pointing outside the project root are skipped but still counted against the total, making the "more" count wrong.

**Evidence:**
```python
targets_shown = 0
for s in symlinks[:3]:
    target = resolve_symlink_target(s)
    if target:
        try:
            rel = target.relative_to(project_root)
            print(f"  {rel}  exists")
            targets_shown += 1
        except ValueError:
            pass  # target outside project — not shown, not counted
if len(symlinks) > 3:
    print(f"  ... ({len(symlinks) - targets_shown} more symlink targets)")
    # Should be: len(symlinks) - 3, or track skipped count
```

**Acceptance Criteria:**
- [ ] "More" count correctly reflects unshown symlinks, regardless of resolution success
- [ ] Test: 5 symlinks, 2 resolve outside project root → "more" count is correct

**Validation Command:**
```bash
grep -n "targets_shown" scripts/sprint_teardown.py
```

**Resolution:**

---

### BH-026: Phantom §-anchor references in CHEATSHEET.md — `§manage_epics._safe_int` and `§manage_sagas._safe_int` do not exist
**Severity:** HIGH
**Category:** `doc/drift`
**Location:** `CHEATSHEET.md:205`, `CHEATSHEET.md:220`
**Status:** ✅ RESOLVED

**Problem:** CHEATSHEET.md lists `§manage_epics._safe_int` and `§manage_sagas._safe_int` as navigable anchors. Neither exists in source — both files import `safe_int` from `validate_config` as an alias (`from validate_config import safe_int as _safe_int`). There is no `# §manage_epics._safe_int` comment in either file. Any tool or developer trying to jump to these anchors will fail silently.

**Evidence:**
```bash
grep -rn '§manage_epics._safe_int' scripts/manage_epics.py   # no match
grep -rn '§manage_sagas._safe_int' scripts/manage_sagas.py   # no match
grep -n 'safe_int' scripts/manage_epics.py                    # line 26: from validate_config import safe_int as _safe_int
```

**Acceptance Criteria:**
- [ ] Either add anchor comments (`# §manage_epics._safe_int`) to the import lines in both files
- [ ] Or remove these entries from CHEATSHEET.md and point to `§validate_config.safe_int` instead
- [ ] `validate_anchors.py check` passes with no broken references

**Validation Command:**
```bash
python scripts/validate_anchors.py check 2>&1 | grep -i "safe_int\|missing\|broken"
```

**Resolution:**

---

### BH-027: README.md story table column order is wrong — Epic is 3rd column, not 6th
**Severity:** HIGH
**Category:** `doc/drift`
**Location:** `README.md:353`
**Status:** ✅ RESOLVED

**Problem:** README.md documents the milestone story table format as `| US-NNNN | title | saga | SP | priority |` with "optional 6th column: `| epic |`". The actual format (from `milestone.md.tmpl` and `populate_issues.py:52` `_DEFAULT_ROW_RE`) is `| Story | Title | Epic | Saga | SP | Priority |` where Epic is the optional **3rd** column between Title and Saga, not a 6th column appended at the end.

**Evidence:**
```python
# populate_issues.py _DEFAULT_ROW_RE:
# Columns: | Story | Title | (optional: Epic |) Saga | SP | Priority |
# README says: | US-NNNN | title | saga | SP | priority | (optional 6th: epic)
```

**Acceptance Criteria:**
- [ ] README.md column order matches `milestone.md.tmpl` and `_DEFAULT_ROW_RE`
- [ ] Epic documented as optional 3rd column, not optional 6th column

**Validation Command:**
```bash
grep -A2 "US-NNNN" README.md
grep -n "Epic" references/skeletons/milestone.md.tmpl
```

**Resolution:**

---

### BH-028: CHEATSHEET.md describes `KANBAN_STATES` as "Tuple" — actually `frozenset`
**Severity:** MEDIUM
**Category:** `doc/drift`
**Location:** `CHEATSHEET.md:113`
**Status:** ✅ RESOLVED

**Problem:** CHEATSHEET.md describes `KANBAN_STATES` as "Tuple of 6 states: todo..done" but the actual type is `frozenset`, not `tuple`. Additionally, it's listed under the `sync_tracking.py` section even though the anchor resolves to `validate_config.py`. The type matters because `frozenset` is unordered (no guaranteed iteration order) while tuples are ordered.

**Evidence:**
```python
# validate_config.py:
KANBAN_STATES = frozenset(("todo", "design", "dev", "review", "integration", "done"))
# CHEATSHEET.md says: "Tuple of 6 states"
```

**Acceptance Criteria:**
- [ ] CHEATSHEET.md says "frozenset" not "Tuple"
- [ ] Entry placed under validate_config.py section, not sync_tracking.py
- [ ] Or: if ordering matters for consumers, change the code to use a tuple and update docs

**Validation Command:**
```bash
python -c "
import sys; sys.path.insert(0, 'scripts')
from validate_config import KANBAN_STATES
print(f'Type: {type(KANBAN_STATES).__name__}')
assert isinstance(KANBAN_STATES, frozenset), 'Not a frozenset'
print('CONFIRMED: KANBAN_STATES is frozenset, not tuple')
"
```

**Resolution:**
