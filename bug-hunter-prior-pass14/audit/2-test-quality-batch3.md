# Test Quality Audit — Batch 3

Adversarial review of 11 test files for anti-patterns that create the appearance
of coverage without the substance.

**Files reviewed:** test_golden_run.py, golden_replay.py, golden_recorder.py,
test_bugfix_regression.py, test_sprint_teardown.py, test_sync_backlog.py,
test_sprint_analytics.py, test_hexwise_setup.py, test_validate_anchors.py,
test_property_parsing.py

---

## SPECIAL FOCUS: golden_replay.py

### Finding: assert_labels_match compares only label NAMES, not colors or descriptions
**File:** golden_replay.py:46-70
**Anti-pattern:** Permissive Validator
**Problem:** `assert_labels_match` extracts label *names* (dict keys) into sets and
compares them. The recorded snapshot from `dump_state()` stores full label data
including colors (e.g., `{"color": "0075ca", "description": "..."}`) but the
replay comparison discards all of it. If production code changed every label's
color from green to red, or corrupted all label descriptions, this test would
still pass.
**Evidence:**
```python
recorded_labels = set(gh_state.get("labels", {}).keys())  # only names
current_labels = set(fake_gh.labels.keys())                # only names
```
The `labels` dict in `dump_state()` is `dict(self.labels)` which maps
`name -> {"color": ..., "description": ...}`. The recorded JSON has this
rich data. The replayer throws it away.
**Mutation test:** Change `create_static_labels()` to assign all labels color
`"000000"` instead of their correct colors. The golden test still passes.

---

### Finding: assert_issues_match compares only titles, not bodies, labels, or milestones
**File:** golden_replay.py:97-135
**Anti-pattern:** Permissive Validator
**Problem:** `assert_issues_match` checks issue *count* and issue *titles* (as
sets). It ignores issue bodies, labels, milestone assignments, and story point
data. The golden recording stores the full issue objects (with body, labels,
milestone, etc.), but the replayer never inspects them. A regression that
corrupts all issue bodies, or assigns every issue to the wrong milestone, or
strips all labels, would pass undetected.
**Evidence:**
```python
recorded_titles = sorted(iss.get("title", "") for iss in recorded_issues)
current_titles = sorted(iss.get("title", "") for iss in current_issues)
# set comparison — no body, label, or milestone check
```
**Mutation test:** Change `format_issue_body()` to return an empty string.
Change `create_issue()` to skip all label assignments. Golden replay still
passes because it only compares title sets.

---

### Finding: assert_milestones_match compares only titles, ignoring all other milestone fields
**File:** golden_replay.py:72-95
**Anti-pattern:** Permissive Validator
**Problem:** `assert_milestones_match` extracts only the `title` field from
each milestone and compares sorted lists. Milestone descriptions, due dates,
sprint counts, and other metadata stored in the golden recording are ignored.
**Evidence:**
```python
recorded_titles = sorted(ms.get("title", "") for ms in gh_state.get("milestones", []))
current_titles = sorted(ms.get("title", "") for ms in fake_gh.milestones)
```
**Mutation test:** Change milestone creation to set `description` to empty string
for all milestones. The golden test still passes.

---

### Finding: assert_files_match silently skips unreadable files instead of failing
**File:** golden_replay.py:181-184
**Anti-pattern:** Permissive Validator
**Problem:** When a file exists in both the recorded and current sets but
`read_text()` throws `OSError` or `UnicodeDecodeError`, the comparison
silently `continue`s -- reporting no diff. A file that was readable when
recorded but becomes unreadable on replay (e.g., permissions issue, encoding
corruption) would be treated as matching.
**Evidence:**
```python
try:
    actual_content = actual_path.read_text(encoding="utf-8")
except (OSError, UnicodeDecodeError):
    continue  # skip unreadable files
```
**Mutation test:** Replace a golden-tracked file with a binary blob. No diff
reported because the exception is swallowed.

---

## SPECIAL FOCUS: test_property_parsing.py

### Finding: _yaml_safe roundtrip test has a naive unquote that masks a real backslash bug
**File:** test_property_parsing.py:196-207
**Anti-pattern:** Rubber Stamp (test verifier reimplements production logic incorrectly)
**Problem:** The roundtrip test unquotes by doing `inner.replace('\\"', '"')`.
But the production `_yaml_safe` function does NOT escape backslashes --
it only escapes double quotes (`value.replace('"', '\\"')`). This means a
value like `hello\` becomes `hello\` (unquoted, returned as-is), which is
fine. But a value like `hello\"` (containing literal backslash-quote) becomes
`"hello\\\""` -- wait, no, the production code does
`value.replace('"', '\\"')` which turns `hello\"` into `hello\\"`. Wrapped
in quotes: `"hello\\"`. Now the test's unquote does
`'hello\\'.replace('\\"', '"')` = `hello\\` which is NOT equal to `hello\"`.
Actually, let's trace more carefully:
- Input: `hello\"` (4 chars in Python: h, e, l, l, o, \\, ")
- Production: `value.replace('"', '\\"')` -> `hello\\"` (h, e, l, l, o, \\, \\, ")
- Wrapped: `"hello\\""`
- Test unquote: strip outer quotes -> `hello\\"`, then `.replace('\\"', '"')` -> `hello\"` = original

The test's naive unquote actually works for this case. However, the
`_yaml_safe` function does NOT escape backslashes, which means a YAML parser
would interpret `\"` as an escaped quote, but `\\` would also be interpreted
as an escaped backslash. A value containing a literal backslash followed by a
non-quote character (e.g., `hello\n`) is passed through unquoted but would be
interpreted as a YAML escape sequence by a real YAML parser. The property test
claims to verify "roundtrip" but the unquote side is not a real YAML parser --
it's a hand-rolled reverse of the production function. It verifies internal
consistency, not actual YAML correctness.
**Evidence:** Production `_yaml_safe` does `value.replace('"', '\\"')` without
first doing `value.replace('\\', '\\\\')`. The test unquote is
`inner.replace('\\"', '"')`. Neither side handles backslash escaping, so
they agree -- but both are wrong from a YAML perspective.
**Mutation test:** Change `_yaml_safe` to also escape backslashes (correct YAML
behavior). The roundtrip test would BREAK because the test-side unquote
doesn't unescape backslashes. The test is coupled to the bug, not to the spec.

---

### Finding: test_dangerous_chars_get_quoted omits YAML boolean keywords from its danger check
**File:** test_property_parsing.py:209-225
**Anti-pattern:** Permissive Validator (incomplete danger predicate)
**Problem:** The property test defines its own `dangerous` predicate that
checks for structural YAML metacharacters but omits YAML boolean keywords
(`true`, `false`, `yes`, `no`, `on`, `off`, `null`) which the production
`_yaml_safe` DOES quote (line 195: `value.lower() in _YAML_BOOL_KEYWORDS`).
This means the test's predicate is strictly weaker than the production
predicate. The test only checks one direction: "if dangerous, must be quoted."
It does NOT check "if not dangerous by my definition, should NOT be quoted."
So the omission doesn't cause false failures -- but it means the test never
verifies that boolean keywords are quoted.
**Evidence:**
```python
dangerous = (
    ': ' in value
    or value.endswith(':')
    or (value and value[0] in '\'\"[{>|*&!%@`')
    or '#' in value
    or value.startswith('- ')
    or value.startswith('? ')
    # Missing: value.lower() in _YAML_BOOL_KEYWORDS
)
```
**Mutation test:** Remove the `_YAML_BOOL_KEYWORDS` check from production
`_yaml_safe` so it stops quoting `true`/`false`/`null`. This property test
still passes because it never asserts those values must be quoted.

---

### Finding: parse_simple_toml property test swallows ValueError as acceptable
**File:** test_property_parsing.py:287-295
**Anti-pattern:** Permissive Validator
**Problem:** `test_returns_dict_or_raises_valueerror` accepts *any* ValueError
as valid behavior. If a regression introduced a ValueError on valid TOML input,
this test would silently accept it. The test generates completely random text
(not valid TOML), so it's exercising the "garbage in" path almost exclusively.
The test provides no coverage guarantee for valid input being parsed correctly.
**Evidence:**
```python
try:
    result = parse_simple_toml(text)
    assert isinstance(result, dict)
except ValueError:
    pass  # Unterminated multiline arrays raise ValueError — that's fine
```
**Mutation test:** Change `parse_simple_toml` to unconditionally raise
`ValueError("broken")`. This test passes 100% of the time because every
`ValueError` is silently accepted.

---

## test_bugfix_regression.py

### Finding: TestBH001PaginatedJson.test_concatenated_json_arrays reimplements parsing instead of calling production code
**File:** test_bugfix_regression.py:304-324
**Anti-pattern:** Mockingbird / Reimplementation
**Problem:** The test for BH-001 (concatenated JSON arrays from `--paginate`)
does NOT call `gh_json()` with concatenated output. Instead, it reimplements
the JSON decode loop from scratch in the test body using `json.JSONDecoder().raw_decode`.
If the production `gh_json()` function's concatenation handling were broken
or removed, this test would still pass because it's testing its own copy of
the algorithm, not the production code.
**Evidence:**
```python
def test_concatenated_json_arrays(self):
    # Directly test the parsing logic
    import json
    raw = '[{"a":1},{"a":2}][{"a":3}]'
    decoder = json.JSONDecoder()
    # ... reimplements the decode loop ...
```
The companion `test_normal_json_still_works` DOES call `gh_json()` via
FakeGitHub, but only with a single array (non-concatenated), so it doesn't
test the actual bug fix.
**Mutation test:** Remove the concatenated-array handling from `gh_json()`.
`test_concatenated_json_arrays` still passes (it's self-contained).
`test_normal_json_still_works` also still passes (single array).

---

### Finding: TestCheckStatusImportGuard inspects source code instead of testing behavior
**File:** test_bugfix_regression.py:62-75
**Anti-pattern:** Inspector Clouseau
**Problem:** The test uses `inspect.getsource()` to verify that the import
guard in `check_status.py` uses `except ImportError` rather than
`except Exception`. This tests implementation, not behavior. If someone
refactored the import to use a different safe pattern (e.g., `importlib` with
explicit error handling), this test would fail even though the behavior is
correct.
**Evidence:**
```python
source = inspect.getsource(check_status)
import_block = source[source.index("Import sync engine"):source.index("MAX_LOGS")]
self.assertIn("except ImportError", import_block)
self.assertNotIn("except Exception", import_block)
```
**Mutation test:** Refactor `check_status.py` to use `importlib.import_module`
with a try/except `ModuleNotFoundError`. Behavior is identical but this test
fails because it grepped for the wrong string.

---

### Finding: TestBH004VacuousTruth tests rely on string matching in report output
**File:** test_bugfix_regression.py:327-362
**Anti-pattern:** Happy Path Tourist (partially)
**Problem:** These tests verify the BH-004 fix (CI not falsely reported green
when checks are in-progress or empty) by searching for substrings in the
report output. The assertions check `assertNotIn("CI green", full)` and
`assertIn("CI pending", full)`. This couples the test to exact phrasing.
If someone rewrites the message to "CI status: passing" or "Checks are still
running," the test passes (no "CI green" found) even if the logic is broken.
More importantly, the test patches `check_status.gh_json` directly (not going
through FakeGitHub subprocess interception), so it doesn't exercise the real
data path.
**Evidence:**
```python
full = "\n".join(report)
self.assertNotIn("CI green", full)
self.assertIn("CI pending", full)
```
**Mutation test:** Change `check_prs` to always report "CI status: all clear"
instead of "CI green." The test passes because it only checks for the literal
string "CI green."

---

## test_golden_run.py

### Finding: Phase 5 (CI) has no replay assertion, only record
**File:** test_golden_run.py:192-203
**Anti-pattern:** Green Bar Addict
**Problem:** The final phase of the golden run (Phase 5: CI workflow generation)
only records the snapshot when `RECORD_MODE` is True. When replaying, Phase 5
is never compared against the golden recording because `_check_or_record` is
never called -- only `recorder.snapshot("05-setup-ci")` inside the
`if RECORD_MODE:` block. The 05-setup-ci.json file exists in golden/recordings/
but is never loaded or compared during replay.
**Evidence:**
```python
# Phase 5: CI workflow generation
yaml_content = setup_ci.generate_ci_yaml(config)
self.assertIn("cargo test", yaml_content)
self.assertIn("cargo clippy", yaml_content)

if RECORD_MODE:
    ci_path = self.project / ".github" / "workflows" / "ci.yml"
    ci_path.parent.mkdir(parents=True, exist_ok=True)
    ci_path.write_text(yaml_content)
    recorder.snapshot("05-setup-ci")
    recorder.write_manifest()
```
No `self._check_or_record(recorder, replayer, "05-setup-ci", ...)` call.
Phase 5 CI regression is tested only by two `assertIn` substring checks.
**Mutation test:** Change `generate_ci_yaml` to omit the `permissions:` block
or change action versions. Golden replay does not catch it; only the two
substring checks for "cargo test" / "cargo clippy" guard against regression.

---

## test_sprint_teardown.py

### Finding: TestTeardownMainExecute does not verify sprint-config directory is removed
**File:** test_sprint_teardown.py:498-507
**Anti-pattern:** Happy Path Tourist
**Problem:** `test_execute_removes_generated` asserts that the generated file
(`project.toml`) is gone, but does not assert that the `sprint-config/`
directory itself was removed. The teardown is supposed to clean up the entire
directory. The test only checks one file was removed, not the full directory.
**Evidence:**
```python
def test_execute_removes_generated(self):
    # ...
    sprint_teardown.main()
    self.assertFalse((self.config_dir / "project.toml").exists())
    # No assertion on self.config_dir.exists()
```
**Mutation test:** Change `remove_empty_dirs` to be a no-op. The test still
passes because it only checks the file, not the directory.

---

## test_sync_backlog.py

### Finding: TestDoSync does not verify issue CONTENT, only counts
**File:** test_sync_backlog.py:180-191
**Anti-pattern:** Happy Path Tourist
**Problem:** `test_do_sync_creates_milestones_and_issues` asserts that the
right number of milestones (1) and issues (2) were created and that the return
value matches. It does not verify issue titles, bodies, labels, story points,
or milestone assignment. A regression that creates 2 blank issues with no
content would pass.
**Evidence:**
```python
self.assertEqual(len(fake_gh.milestones), 1)
self.assertEqual(len(fake_gh.issues), 2)
self.assertEqual(created["milestones"], len(fake_gh.milestones))
self.assertEqual(created["issues"], len(fake_gh.issues))
```
**Mutation test:** Change `create_issue()` to create issues with empty titles
and no labels. The test still passes because it only counts.

---

## test_sprint_analytics.py

### Finding: TestComputeWorkload doesn't verify issue STATE filtering
**File:** test_sprint_analytics.py:246-259
**Anti-pattern:** Happy Path Tourist
**Problem:** All test issues in `test_counts_per_persona` are set to
`"state": "closed"`. The test never verifies whether `compute_workload` counts
only closed issues, only open issues, or all issues. If the function's
filtering logic were removed (or it started counting issues regardless of
state), the test would still pass.
**Evidence:** All 3 issues have `"state": "closed"`. No issue with a different
state is present to verify filtering.
**Mutation test:** Change `compute_workload` to ignore the `state` field
entirely. This test still passes because all test data is already closed.

---

## test_hexwise_setup.py

### Finding: test_full_setup_pipeline uses assertGreaterEqual for label count instead of exact
**File:** test_hexwise_setup.py:369
**Anti-pattern:** Permissive Validator
**Problem:** The label count assertion uses `assertGreaterEqual(len(...), 17)`
instead of an exact count. If a regression added 50 duplicate labels, or if
a code change dropped half the labels but still produced 17, the test passes.
The exact expected count should be asserted for a deterministic fixture.
**Evidence:**
```python
self.assertGreaterEqual(len(self.fake_gh.labels), 17,
                        "Should have static + persona + sprint labels")
```
**Mutation test:** Double-call `create_static_labels()` to create duplicates
(if the code allows it). The test still passes because >= 17 is satisfied.

---

### Finding: test_state_dump uses assertGreaterEqual instead of exact count
**File:** test_hexwise_setup.py:423
**Anti-pattern:** Permissive Validator
**Problem:** Same pattern: `assertGreaterEqual(len(state["labels"]), 13)`.
For a deterministic fixture, the exact label count should be known and asserted.
**Evidence:**
```python
self.assertGreaterEqual(len(state["labels"]), 13)  # static labels minimum
```
**Mutation test:** Same as above -- surplus or duplicate labels pass undetected.

---

## test_validate_anchors.py

### Finding: Temporary files are not cleaned up (delete=False without explicit unlink)
**File:** test_validate_anchors.py:54-96
**Anti-pattern:** (Not a test quality anti-pattern per se, but a test hygiene issue that can cause flaky behavior)
**Problem:** `TestFindAnchorDefs` and `TestFindAnchorRefs` create temporary files
with `delete=False` but never call `os.unlink()` or use `addCleanup()` to
remove them. Over many test runs, these accumulate in `/tmp`.
**Evidence:**
```python
with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
    # ... write content ...
    defs = find_anchor_defs(Path(f.name))
# f.name is never unlinked
```
This pattern repeats in `test_python_function_anchor`, `test_markdown_heading_anchor`,
`test_multiple_anchors`, `test_no_anchors_returns_empty`, and all of
`TestFindAnchorRefs`.

---

## test_property_parsing.py (additional findings)

### Finding: TestParseTeamIndexProperties avoids hard characters in name generation
**File:** test_property_parsing.py:431-455
**Anti-pattern:** Happy Path Tourist (strategy avoidance)
**Problem:** The `name` strategy restricts characters to `min_codepoint=65,
max_codepoint=122`, which is A-Z, some punctuation ([, \, ], ^, _, `), and
a-z. But it also uses `whitelist_categories=("L", "N")` which further limits
to letters and numbers. This means the test never generates names containing
pipe characters (`|`), which would break markdown table parsing. It never
generates names with leading/trailing whitespace. It never generates names
with newlines. These are exactly the inputs most likely to reveal parsing bugs
in `_parse_team_index`.
**Evidence:**
```python
name=st.text(
    alphabet=st.characters(whitelist_categories=("L", "N"),
                           min_codepoint=65, max_codepoint=122),
    min_size=1, max_size=20,
),
```
**Mutation test:** Change `_parse_team_index` to not strip whitespace from
cell contents. This test still passes because names never contain whitespace.

---

### Finding: TestParseTeamIndexProperties.test_table_row_extraction leaks temporary files
**File:** test_property_parsing.py:447-455
**Anti-pattern:** (Test hygiene)
**Problem:** Uses `NamedTemporaryFile(delete=False)` inside a hypothesis
`@given` loop (200 examples). Each example creates a temp file and unlinks it
after, but if an assertion fails mid-example, the `Path(f.name).unlink()` on
line 451 is never reached (it's not in a `finally` block), leaving orphan files.
**Evidence:**
```python
with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
    f.write(table)
    f.flush()
    rows = _parse_team_index(Path(f.name))
Path(f.name).unlink()  # Not in finally — skipped on assertion failure
```

---

## Summary

| Severity | Count | Key Theme |
|----------|-------|-----------|
| HIGH     | 3     | Golden replay compares names/titles only, ignoring content (labels, issues, milestones) |
| HIGH     | 1     | BH-001 concatenated JSON test reimplements production logic instead of calling it |
| HIGH     | 1     | Phase 5 (CI) golden snapshot is recorded but never replayed |
| MEDIUM   | 2     | Property test for _yaml_safe roundtrip is coupled to the bug, not the YAML spec |
| MEDIUM   | 2     | Permissive >= assertions where exact counts are known |
| MEDIUM   | 1     | test_dangerous_chars_get_quoted omits YAML boolean keywords |
| MEDIUM   | 1     | Source inspection test (Inspector Clouseau) |
| LOW      | 3     | Happy path only — no negative/boundary cases for state, content |
| LOW      | 2     | Temp file leaks in validate_anchors and property tests |

The most critical finding is the golden replay infrastructure: it records rich
state (full issue objects, label colors, file contents) but the replay
comparisons check only surface-level properties (names, titles, file presence).
The `assert_files_match` method is the one exception -- it DOES compare file
contents (lines 176-188). But the GitHub state comparisons (labels, milestones,
issues) discard the majority of the recorded data. A content-level regression
in issue bodies, label colors, or milestone metadata would pass the golden
tests undetected.
