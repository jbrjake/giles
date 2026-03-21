# Test Quality Audit — Batch 2

**Files audited:**
- `tests/test_gh_interactions.py` (415 lines)
- `tests/test_pipeline_scripts.py` (1512 lines)
- `tests/test_property_parsing.py` (473 lines)
- `tests/conftest.py` (25 lines)
- `tests/fake_github.py` (945 lines)

**Auditor:** Claude Opus 4.6 (adversarial review)
**Date:** 2026-03-16

---

## Summary

| Anti-pattern | Count | Severity |
|---|---|---|
| The Mockingbird | 3 | High |
| Happy Path Tourist | 4 | Medium |
| Rubber Stamp | 3 | Medium |
| FakeGitHub fidelity gap | 4 | High |
| Tautology Test | 1 | Medium |
| Inspector Clouseau | 2 | Low |
| Green Bar Addict | 1 | Medium |
| Permissive Validator | 2 | Medium |

Total: 20 findings

---

## test_gh_interactions.py

### Finding: gate_stories mock bypasses the real gh_json pipeline
**File:** test_gh_interactions.py:289-314
**Anti-pattern:** The Mockingbird
**Problem:** `TestGateStories` patches `release_gate.gh_json` to return canned data, which means the actual `gh_json()` function (which builds CLI args, calls `subprocess.run`, parses JSON) is never exercised. The gate logic itself is trivial — "is this list empty?" — so the test mostly validates that `gate_stories` calls `gh_json` with certain args. The real risk (malformed CLI args, JSON parse errors, unexpected response shapes) is untested.
**Evidence:**
```python
@patch("release_gate.gh_json")
def test_all_closed(self, mock_gh):
    mock_gh.return_value = []
    ok, detail = gate_stories("Sprint 1")
    self.assertTrue(ok)
```
**Mutation test:** If you changed `gate_stories` to hard-code `return True, "All issues closed"` without calling `gh_json` at all, the test would still pass (the call_args assertion would fail, but the core gate logic assertion would not). Conversely, if the real `gh_json` started returning `{"items": [...]}` (dict instead of list), the mock wouldn't catch it.

### Finding: gate_ci mock makes branch filtering invisible
**File:** test_gh_interactions.py:317-348
**Anti-pattern:** The Mockingbird
**Problem:** `gate_ci` in production calls `gh_json(["run", "list", "--branch", base_branch, "--limit", "1", ...])`. The test patches `gh_json` and then asserts the args contain `"--branch"` and `"main"`. But the mock returns a canned run list regardless of what branch was requested. If production accidentally passed `--branch ""` or `--branch "develop"`, the mock would still return the same canned success data.
**Evidence:**
```python
@patch("release_gate.gh_json")
def test_passing(self, mock_gh):
    mock_gh.return_value = [
        {"status": "completed", "conclusion": "success", "name": "CI"},
    ]
    ok, detail = gate_ci({"project": {}})
    self.assertTrue(ok)
```
**Mutation test:** Change `get_base_branch` to always return `"nonexistent"` — test still passes because mock ignores what branch was requested.

### Finding: gate_prs does not verify milestone filter is applied server-side
**File:** test_gh_interactions.py:350-386
**Anti-pattern:** The Mockingbird + Happy Path Tourist
**Problem:** In production, `gate_prs` fetches ALL open PRs (no milestone filter on the query) then filters client-side. The test mocks `gh_json` to return a list that already contains the matching milestone. There's no test for the edge case where production's client-side filter has a bug (e.g., comparing `None` to a string). Also, `test_pr_for_different_milestone` returns a single PR for "Sprint 2" but the mock always returns this regardless — the test verifies client-side filtering but only for one scenario.
**Evidence:**
```python
@patch("release_gate.gh_json")
def test_pr_for_different_milestone(self, mock_gh):
    mock_gh.return_value = [
        {"number": 10, "title": "feat: thing",
         "milestone": {"title": "Sprint 2"}},
    ]
    ok, _ = gate_prs("Sprint 1")
    self.assertTrue(ok)
```
**Mutation test:** Change `gate_prs` to skip the milestone filtering entirely (return `True` when list is non-empty but none match) — the `test_no_prs` test would still pass. Only `test_open_pr_for_milestone` would catch the regression.

### Finding: check_atomicity tests mock subprocess.run but don't verify the command
**File:** test_gh_interactions.py:81-128
**Anti-pattern:** Inspector Clouseau
**Problem:** All four `TestCheckAtomicity` tests patch `commit.subprocess.run` but never assert what command was passed. If the production code changed from `git diff --cached --name-only` to `git status --porcelain`, the tests would still pass because the mock returns canned stdout regardless.
**Evidence:**
```python
@patch("commit.subprocess.run")
def test_single_directory(self, mock_run):
    mock_run.return_value = subprocess.CompletedProcess(
        args=[], returncode=0, stdout="src/foo.py\nsrc/bar.py\n", stderr="",
    )
    ok, msg = check_atomicity()
    self.assertTrue(ok)
```
**Mutation test:** Replace `["git", "diff", "--cached", "--name-only"]` with `["echo", "src/foo.py"]` in production — all tests pass.

### Finding: generate_release_notes assertions only check section headers exist
**File:** test_gh_interactions.py:389-411
**Anti-pattern:** Rubber Stamp
**Problem:** `test_basic_notes` asserts that the output contains `"## Features"` and `"## Fixes"` but never checks that the actual commit messages appear in the right sections. A bug that puts all commits under "Other" but still emits the section headers would pass.
**Evidence:**
```python
def test_basic_notes(self):
    commits = [
        {"subject": "feat: add login", "body": ""},
        {"subject": "fix: typo in config", "body": ""},
    ]
    config = {"project": {"repo": "test/repo"}}
    notes = generate_release_notes("0.2.0", "0.1.0", commits, "Sprint 1", config)
    self.assertIn("v0.2.0", notes)
    self.assertIn("## Features", notes)
    self.assertIn("## Fixes", notes)
```
**Mutation test:** Change `generate_release_notes` to emit `"## Features\n\n## Fixes\n"` with no actual content under them — test passes. Also change it to put "feat: add login" under Fixes — test passes.

### Finding: validate_message tests don't check error message content for all failure modes
**File:** test_gh_interactions.py:62-78
**Anti-pattern:** Happy Path Tourist
**Problem:** `test_missing_colon` and `test_empty_message` assert `assertFalse(ok)` but don't verify the error message is helpful. `test_no_type_prefix` doesn't verify the error message at all. A regression that changes the error message to an empty string or a misleading message would go undetected.
**Evidence:**
```python
def test_missing_colon(self):
    ok, err = validate_message("feat add login")
    self.assertFalse(ok)
    # No assertion on err content

def test_empty_message(self):
    ok, err = validate_message("")
    self.assertFalse(ok)
    # No assertion on err content
```
**Mutation test:** Return `(False, "")` for all invalid messages — tests pass.

---

## test_pipeline_scripts.py

### Finding: CI generation tests only check for keyword presence, not structure
**File:** test_pipeline_scripts.py:680-741
**Anti-pattern:** Rubber Stamp
**Problem:** `TestCIGeneration` tests for Python, Node.js, and Go only verify that certain keywords appear somewhere in the generated YAML (e.g., `"pip install"`, `"pytest"`, `"npm"`, `"node"`). They don't verify the YAML is valid, that commands appear in the right section, or that the structure matches the expected workflow format.
**Evidence:**
```python
def test_python_ci_yaml(self):
    config = {
        "project": {"name": "test", "language": "Python", "repo": "o/r"},
        "ci": {"check_commands": ["ruff check .", "pytest"],
               "build_command": "python -m build"},
    }
    yaml = generate_ci_yaml(config)
    self.assertIn("pip install", yaml)
    self.assertIn("pytest", yaml)
    self.assertIn("python", yaml)
```
**Mutation test:** Generate YAML that puts `pip install` in a comment and `pytest` in the `name:` field instead of `run:` — test passes. Generate malformed YAML (broken indentation) — test passes.

### Finding: test_extract_voices_from_epics is a Green Bar test
**File:** test_pipeline_scripts.py:49-54
**Anti-pattern:** Green Bar Addict
**Problem:** This test asserts `len(voices) == 0` for the Hexwise epics directory, meaning it only verifies that the function returns an empty dict. It doesn't test any actual voice extraction logic — it just confirms the fixture has no voices in its epic files. If `extract_voices` was changed to always return `{}`, this test would still pass.
**Evidence:**
```python
def test_extract_voices_from_epics(self):
    """Extract team voices from Hexwise epic files."""
    voices = extract_voices(
        epics_dir=str(HEXWISE / "docs" / "agile" / "epics"),
    )
    self.assertIsInstance(voices, dict)
    self.assertEqual(len(voices), 0, "Expected no voices in Hexwise epics")
```
**Mutation test:** Replace `extract_voices` with `lambda **kw: {}` — test passes.

### Finding: traceability gap detection test uses synthetic data instead of realistic edge case
**File:** test_pipeline_scripts.py:123-133
**Anti-pattern:** Happy Path Tourist
**Problem:** `test_traceability_detects_gaps` creates a minimal epic with a story that has NO test cases field at all. This tests the "completely missing" case. But the more dangerous bug would be a story with an empty test cases field (`| Test Cases | |`) or a malformed one (`| Test Cases | TC- |`). These realistic partial-failure modes are not tested.
**Evidence:**
```python
def test_traceability_detects_gaps(self):
    with tempfile.TemporaryDirectory() as tmp:
        epic = Path(tmp) / "E-0101-test.md"
        epic.write_text(
            "### US-9999: Untested Story\n\n"
            "| Field | Value |\n|---|---|\n| Story Points | 3 |\n"
        )
        report = build_traceability(epics_dir=tmp)
        self.assertIn("US-9999", report["stories_without_tests"])
```
**Mutation test:** Change `build_traceability` to only flag stories with 0 table fields (not stories with empty Test Cases) — test still passes.

### Finding: parse_epic_empty_file asserts specific default values without testing behavior
**File:** test_pipeline_scripts.py:356-368
**Anti-pattern:** Tautology Test
**Problem:** This test asserts that `parse_epic("")` returns specific default values (`title=""`, `stories=[]`, etc.). But these are just the implementation's chosen defaults — there's no specification that says an empty file MUST return empty string for title. The test is asserting what the code does rather than what it should do. If someone changed the default title to `"Untitled Epic"`, this test would fail but the code might be correct.
**Evidence:**
```python
def test_parse_epic_empty_file(self):
    result = parse_epic(str(empty_path))
    self.assertEqual(result["title"], "")
    self.assertEqual(result["stories"], [])
    self.assertEqual(result["raw_sections"], [])
    self.assertEqual(result["stories_count"], 0)
    self.assertEqual(result["total_sp"], 0)
```
**Mutation test:** This is more of a design question. The test would catch changes but doesn't validate behavior — it validates the current implementation's choice of defaults.

### Finding: Scanner "None" tests are trivially correct
**File:** test_pipeline_scripts.py:1061-1079, 1161-1226
**Anti-pattern:** Happy Path Tourist (inverted — only tests the absence case)
**Problem:** Both `TestScannerPythonProject` and `TestScannerMinimalProject` have a combined ~15 tests that just assert `detect_X()` returns `None` when the relevant directory/file is absent. These tests are useful but trivially pass — they only verify the "nothing to find" path. The "found but wrong format" path is mostly untested (e.g., what happens when `docs/sagas/` exists but contains non-saga files?).
**Evidence:**
```python
def test_detect_sagas_dir_none(self):
    det = self.scanner.detect_sagas_dir()
    self.assertIsNone(det)

def test_detect_epics_dir_none(self):
    det = self.scanner.detect_epics_dir()
    self.assertIsNone(det)
```
**Mutation test:** Replace every `detect_*` method with `return None` — 15 tests pass. The Python project scanner tests do test positive detection for some methods (language, name, CI) but the deep-doc detectors are only tested for None returns.

### Finding: update_sprint_allocation only checks first row
**File:** test_pipeline_scripts.py:443-455
**Anti-pattern:** Permissive Validator
**Problem:** `test_update_sprint_allocation` writes two sprint rows but only verifies the first row's values (`sprint_allocation[0]["stories"]` and `sprint_allocation[0]["sp"]`). The second row is not checked at all. If `update_sprint_allocation` truncated the table to one row, or corrupted the second row, the test would still pass.
**Evidence:**
```python
def test_update_sprint_allocation(self):
    new_allocation = [
        {"sprint": "Sprint 1", "stories": "US-0101, US-0102", "sp": "11"},
        {"sprint": "Sprint 2", "stories": "US-0103, ...", "sp": "23"},
    ]
    update_sprint_allocation(str(saga_path), new_allocation)
    result = parse_saga(str(saga_path))
    self.assertEqual(result["sprint_allocation"][0]["stories"], "US-0101, US-0102")
    self.assertEqual(result["sprint_allocation"][0]["sp"], "11")
    # No assertion on result["sprint_allocation"][1]
```
**Mutation test:** Change `update_sprint_allocation` to only write the first row — test passes.

---

## test_property_parsing.py

### Finding: TOML roundtrip test silently skips non-string values
**File:** test_property_parsing.py:297-312
**Anti-pattern:** Permissive Validator
**Problem:** `test_single_kv_roundtrip` generates `st.one_of(_toml_string_val, _toml_int_val, _toml_bool_val)` but the `_toml_line` helper always produces valid TOML. The test verifies roundtrip but never tests what happens with values that are ambiguous between types (e.g., `"true"` as a string vs `true` as a bool). The TOML parser's handling of edge cases between types isn't exercised.
**Evidence:**
```python
@given(
    key=_toml_key,
    value=st.one_of(_toml_string_val, _toml_int_val, _toml_bool_val),
)
def test_single_kv_roundtrip(self, key: str, value):
    line = _toml_line(key, value)  # Always produces valid TOML
    result = parse_simple_toml(line)
    assert key in result
```
The `_toml_line` helper properly quotes strings and formats bools/ints, so the parser only ever sees well-formed input. The interesting bugs occur with malformed or ambiguous input (e.g., `key = true` when the user meant a string, or `key = 42abc`). These are tested elsewhere (the unittest `TestParseSimpleToml` class covers some edge cases) but the property test doesn't contribute to that coverage.
**Mutation test:** Not a false positive per se, but the property test is weaker than it appears — it tests the happy path across many random inputs but never the parse-error paths.

### Finding: _yaml_safe roundtrip test has a quoting logic gap
**File:** test_property_parsing.py:194-207
**Anti-pattern:** Inspector Clouseau
**Problem:** `test_quoting_roundtrip` checks that if `_yaml_safe` quotes a value, unquoting recovers the original. But it only tests the simplest unescaping (replace `\"` with `"`). If `_yaml_safe` ever needed to escape backslashes (which it doesn't currently but could in a future fix), this roundtrip logic would be wrong: `\\\"` would be unescaped incorrectly. The test encodes assumptions about the escaping strategy rather than testing the actual YAML parse behavior.
**Evidence:**
```python
def test_quoting_roundtrip(self, value: str):
    result = _yaml_safe(value)
    if result.startswith('"') and result.endswith('"'):
        inner = result[1:-1].replace('\\"', '"')
        assert inner == value
```
A value like `hello\` would become `"hello\"` if `_yaml_safe` didn't escape backslashes, and the test's unquoting would produce `hello"` which != `hello\`, catching the bug. But a value like `hello\"world` would become `"hello\\\"world"` if backslash-escaping were added, and the test's simplistic `replace('\\"', '"')` would produce `hello\"world` instead of `hello\"world` — potentially masking the issue depending on the escaping order.
**Mutation test:** This is more of a fragility concern than a current bug. If `_yaml_safe` is enhanced to also escape `\`, this test must be updated or it will give false failures.

---

## fake_github.py — FakeGitHub Fidelity

### Finding: FakeGitHub never updates milestone issue counts
**File:** fake_github.py:394-395, 523-535, 628-643
**Anti-pattern:** FakeGitHub fidelity gap
**Problem:** When milestones are created, `open_issues` and `closed_issues` are initialized to 0. When issues are created with a milestone or when issues are closed, these counters are never updated. Production code (`check_status.py:191-192`) reads these counters to compute sprint progress. Any test using FakeGitHub to verify milestone progress will see 0% completion regardless of how many issues are created and closed.
**Evidence:**
```python
# Milestone created with zeroed counters
ms = {
    "number": self._next_ms,
    "title": title,
    ...
    "open_issues": 0,
    "closed_issues": 0,
}
# _issue_create and _issue_close never update ms["open_issues"] or ms["closed_issues"]
```
**Mutation test:** Change `check_milestone` to always report 100% progress — tests using FakeGitHub wouldn't catch it because the counters are always 0.

### Finding: `run view` returns hardcoded string regardless of run ID
**File:** fake_github.py:659-660
**Anti-pattern:** FakeGitHub fidelity gap
**Problem:** `gh run view <id>` always returns `_ok("no logs")` regardless of what run ID is requested or whether that run exists. Real GitHub returns structured JSON with run details or an error if the run doesn't exist. While `run view` isn't currently used in production Python scripts (search confirmed no usage), FakeGitHub silently returns success for a potentially invalid run, which could mask bugs if production ever starts using it.
**Evidence:**
```python
elif sub == "view":
    return self._ok("no logs")
```
**Mutation test:** Any test calling `gh run view` with an invalid ID will get a success response.

### Finding: FakeGitHub release view returns synthetic URL, not stored release data
**File:** fake_github.py:864-878
**Anti-pattern:** FakeGitHub fidelity gap
**Problem:** `gh release view <tag>` constructs a URL from the tag argument but never looks up the tag in `self.releases`. It returns `{"url": "https://.../<tag>"}` for ANY tag, even ones that were never created. Real GitHub would return a 404 for nonexistent releases. If production code uses `release view` to verify a release exists before proceeding, FakeGitHub would never catch the "release doesn't exist" error path.
**Evidence:**
```python
elif sub == "view":
    # ...
    json_str = json.dumps({
        "url": f"https://github.com/testowner/testrepo/releases/tag/{tag}"
    })
    return self._ok(self._maybe_apply_jq(json_str, flags))
```
**Mutation test:** Call `gh release view v99.99.99` on a FakeGitHub with no releases — returns success URL instead of error.

### Finding: FakeGitHub issue create doesn't update milestone's open_issues counter
**File:** fake_github.py:494-535
**Anti-pattern:** FakeGitHub fidelity gap (related to Finding about milestone counts)
**Problem:** When `_issue_create` is called with `--milestone "Sprint 1"`, it validates the milestone exists but doesn't increment the milestone's `open_issues` counter. Similarly, `_issue_close` doesn't decrement `open_issues` or increment `closed_issues`. This means FakeGitHub's milestone state is permanently frozen at `open_issues=0, closed_issues=0` regardless of activity. This is the root cause of the milestone progress gap described above.
**Evidence:** Neither `_issue_create` (line 494) nor `_issue_close` (line 628) contains any code to update milestone counters. The `_handle_api` milestone PATCH handler (line 354) can set arbitrary fields via `-f` flags, but this is only used for explicit milestone state changes, not automatic counter tracking.
**Mutation test:** Write a test that creates a milestone, creates 5 issues for it, closes 3, then queries the milestone API. `open_issues` would be 0 and `closed_issues` would be 0, not 2 and 3.

---

## conftest.py

### Finding: conftest.py path ordering creates subtle import shadowing risk
**File:** conftest.py:12-24
**Anti-pattern:** Not a test quality issue per se, but a test infrastructure concern
**Problem:** The conftest inserts `ROOT / "tests"` as the first path, before all script directories. If any test helper file in `tests/` shares a name with a production module (e.g., a `tests/validate_config.py` helper), it would shadow the real module. Currently no such collision exists, but the ordering creates a latent risk. The `tests/` directory being first means `from validate_config import ...` would find a test version before the real one if one were accidentally created.
**Evidence:**
```python
_SCRIPT_PATHS = [
    ROOT / "tests",          # <-- inserted before production scripts
    ROOT / "scripts",
    ROOT / "skills" / "sprint-setup" / "scripts",
    ...
]
```
**Mutation test:** Create `tests/validate_config.py` with a stub `parse_simple_toml` that always returns `{}` — all tests importing from `validate_config` would silently use the stub.

---

## Cross-file Patterns

### Finding: Heavy reliance on `assertIn` for string content verification
**Files:** test_gh_interactions.py, test_pipeline_scripts.py (throughout)
**Anti-pattern:** Rubber Stamp (systemic)
**Problem:** Many tests use `assertIn("keyword", output)` as their primary assertion strategy. This checks that a substring exists somewhere in the output but doesn't verify where it appears, in what context, or what's around it. For generated content like release notes, CI YAML, and saga/epic markdown, this means structural errors go undetected.
**Evidence:** Count of `assertIn` usage:
- test_gh_interactions.py: ~25 assertions, most are `assertIn` on strings
- test_pipeline_scripts.py: ~60 assertions, majority are `assertIn` on strings or `assertIsInstance`/`assertEqual` on types
**Mutation test:** A production function that concatenates all its output into a single line with keywords but wrong structure would pass most of these tests.

### Finding: Strict mode warnings only tested in isolation, not applied to production-path tests
**Files:** All test files using FakeGitHub (except test_bugfix_regression.py)
**Anti-pattern:** Happy Path Tourist
**Problem:** FakeGitHub has an elaborate strict-mode warning system (`_check_flags`, `_strict_warnings`) that warns when tests use flags that FakeGitHub doesn't actually evaluate. The strict mode mechanism itself IS tested in `test_bugfix_regression.py` (5 assertions on `_strict_warnings`). However, none of the production-path tests (test_sprint_runtime.py, test_lifecycle.py, test_golden_run.py, etc.) assert that `fake._strict_warnings == []` after their test runs. This means if a production code path starts passing a flag that FakeGitHub silently ignores, the warning fires but no test catches it. The strict mode infrastructure is validated in isolation but not leveraged as a guard in integration tests.
**Evidence:** `test_bugfix_regression.py:759-833` tests the strict mode mechanism directly. But a search for `_strict_warnings` in `test_sprint_runtime.py`, `test_lifecycle.py`, `test_golden_run.py`, `test_hexwise_setup.py` returns zero hits.
**Mutation test:** Add a new flag to a production `gh_json` call that FakeGitHub silently ignores — only the warning is emitted, no test fails.
