# Test Quality Audit — Adversarial Review

**Date:** 2026-03-16
**Scope:** All 15 test files in `tests/` (696 tests total)
**Auditor:** Claude Opus 4.6

---

## Executive Summary

The giles test suite is **above average** for a project of this nature. Most tests exercise real production code through a well-designed `FakeGitHub` test double, assertions check computed values (not just types), and edge cases are covered systematically. The property-based tests in `test_property_parsing.py` are genuinely strong.

That said, the audit found **23 suspicious tests** across 7 anti-pattern categories. The worst offenders are a cluster of Inspector Clouseau tests that inspect source code instead of behavior, and several Shallow End tests that verify structure without checking correctness.

**Severity breakdown:**
- Tier 1 (Actively Harmful): 5 findings
- Tier 2 (False Security): 4 findings
- Tier 3 (Missed Opportunities): 14 findings

---

## Tier 1: Actively Harmful

### 1. Inspector Clouseau — Source code inspection instead of behavioral test

**File:** `test_bugfix_regression.py`
**Class:** `TestCheckStatusImportGuard`
**Method:** `test_import_guard_uses_import_error` (line 65)

```python
source = inspect.getsource(check_status)
import_block = source[source.index("Import sync engine"):source.index("MAX_LOGS")]
self.assertIn("except ImportError", import_block)
self.assertNotIn("except Exception", import_block)
```

**Anti-pattern:** Inspector Clouseau (#4). This test reads the source code of `check_status` and asserts that a specific string appears in a specific region. It tests *how* the code is written, not *what* it does. A developer could refactor the import guard to use a completely valid alternative (e.g., `try/except (ImportError, ModuleNotFoundError)`) and this test would fail. Conversely, the code could catch `ImportError` but handle it incorrectly, and this test would still pass.

**Would pass if broken:** Yes. If the except clause caught ImportError but silently corrupted state, this test would be green.

**Fix:** Replace with a behavioral test that actually triggers the ImportError path (e.g., temporarily hide the sync_backlog module) and verifies the code degrades gracefully.

---

### 2. Inspector Clouseau — Signature inspection

**File:** `test_sprint_runtime.py`
**Class:** `TestSharedHelpers`
**Method:** `test_gh_custom_timeout` (line 851)

```python
sig = inspect.signature(gh)
self.assertIn("timeout", sig.parameters)
self.assertEqual(sig.parameters["timeout"].default, 60)
```

**Anti-pattern:** Inspector Clouseau (#4). Tests that `gh()` has a parameter named `timeout` with default 60, but never calls `gh()` with a custom timeout to verify it actually works. The parameter could exist but be completely ignored in the function body.

**Would pass if broken:** Yes. If `gh()` accepted `timeout` but never passed it to `subprocess.run`, this test would be green.

**Fix:** Call `gh()` with a custom timeout and verify `subprocess.run` receives the correct `timeout` kwarg.

---

### 3. The Mockingbird — So much mocked that behavior is untestable

**File:** `test_release_gate.py`
**Class:** `TestDoRelease`
**Method:** `test_happy_path` (line 646)

```python
@patch("release_gate.gh")
@patch("release_gate.find_milestone_number")
@patch("release_gate.subprocess.run")
@patch("release_gate.write_version_to_toml")
@patch("release_gate.calculate_version")
def test_happy_path(self, mock_calc, mock_write_toml, mock_run, mock_ms, mock_gh):
```

**Anti-pattern:** The Mockingbird (#3). Five nested mocks replace nearly every dependency of `do_release()`. What remains is essentially testing the *wiring* — that `do_release` calls things in the right order with the right args. The test verifies `mock_run.call_args_list` indices (e.g., `run_cmds[4][1] == "tag"`), which means any reordering of git commands would break the test even if the release logic is still correct.

**Mitigating factor:** The docstring at line 600-611 explicitly acknowledges this trade-off and states integration tests cover real behavior. This is a conscious design choice, not an accident. The test *does* catch real regressions (wrong git commands, missing steps). But the mock density means a significant bug in the orchestration logic could hide.

**Would pass if broken:** Partially. If `write_version_to_toml` silently wrote the wrong version, or if `generate_release_notes` produced garbage, these tests would pass because both are mocked.

---

### 4. Inspector Clouseau — Asserting constant identity instead of behavior

**File:** `test_verify_fixes.py`
**Class:** `TestKanbanStatesConstant`
**Method:** `test_kanban_states_is_frozenset` (line 734)

```python
self.assertIsInstance(KANBAN_STATES, frozenset, ...)
```

**Anti-pattern:** Inspector Clouseau (#4). Testing that a constant is a `frozenset` rather than testing that the code *using* it behaves correctly with invalid states. The type of the container is an implementation detail.

**Would pass if broken:** Yes. If `KANBAN_STATES` contained the wrong states (e.g., missing "integration"), this specific test would still pass as long as it remained a frozenset.

**Mitigating factor:** The companion test `test_kanban_states_match_documented` does check the actual values, so this is more "redundant" than "harmful."

---

### 5. Tautology Test — Asserting what the code does, not what it should do

**File:** `test_pipeline_scripts.py`
**Class:** `TestScannerMinimalProject`
**Methods:** `test_detect_sagas_dir_none`, `test_detect_epics_dir_none`, `test_detect_story_map_none`, `test_detect_team_topology_none`, `test_detect_prd_dir_none`, `test_detect_test_plan_dir_none` (lines 1061-1083, 1161-1183)

These 10+ tests all follow the same pattern:
```python
def test_detect_sagas_dir_none(self):
    self.assertIsNone(self.scanner.detect_sagas_dir())
```

**Anti-pattern:** Tautology (#1) bordering on Green Bar Addict (#2). Each test creates a bare-minimum project (one C file), then asserts every optional detection method returns None. This is just confirming the obvious — "if the directory doesn't exist, the scanner doesn't find it." The tests would pass even if `detect_sagas_dir()` was hardcoded to `return None`.

**Would pass if broken:** Yes. If `detect_sagas_dir()` always returned None (even when sagas exist), all these tests would pass.

**Mitigating factor:** There are corresponding positive tests in `TestScannerPythonProject` that test detection *succeeds*. These None-tests mostly serve as documentation of the expected behavior. Still, they inflate test count without adding confidence.

---

## Tier 2: False Security

### 6. Happy Path Tourist — Only tests success or trivial cases

**File:** `test_sprint_runtime.py`
**Class:** `TestCreateLabel`
**Method:** `test_creates_label` (line 122)

```python
@patch("bootstrap_github.gh")
def test_creates_label(self, mock_gh):
    mock_gh.return_value = ""
    bootstrap_github.create_label("test-label", "ff0000", "A test label")
    mock_gh.assert_called_once()
```

**Anti-pattern:** Happy Path Tourist (#5). Mocks `gh()` to return empty string, verifies it was called. Never tests what happens with invalid color codes, empty label names, rate limiting, or network errors. The companion `test_label_error_handled` does test the error path, but only for "already exists" — not for other failure modes.

---

### 7. Time Bomb — Hardcoded dates that will become stale

**File:** `test_sprint_runtime.py`
**Class:** `TestHours`
**Method:** `test_recent_iso_returns_small_hours` (line 1567)

```python
def test_recent_iso_returns_small_hours(self):
    recent = (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat()
    h = check_status._hours(recent)
    self.assertAlmostEqual(h, 0.5, delta=0.1)
```

**Anti-pattern:** Time Bomb (#6). This test is actually well-written (uses `datetime.now()` rather than hardcoded dates). NOT a real finding — included here for completeness to note that this test suite generally handles time correctly.

However, the FakeGitHub fixture data throughout the suite uses hardcoded dates like `"2026-03-10T12:00:00Z"` and `"2026-03-01T00:00:00Z"`. These are fine for deterministic data, but any test that *computes age from these dates* (like "recent PR" logic) will behave differently over time. Currently no such tests exist, so this is only a latent risk.

---

### 8. Permissive Validator — Overly broad assertion

**File:** `test_sprint_runtime.py`
**Class:** `TestCheckCI`
**Method:** `test_failing_run` (line 63)

```python
def test_failing_run(self, mock_gh_json, mock_gh):
    ...
    self.assertIn("1 failing", report[0])
    self.assertTrue(len(actions) > 0)
```

**Anti-pattern:** Permissive Validator (#10). `assertTrue(len(actions) > 0)` only verifies that *some* actions exist, not that they contain the correct remediation advice. The actions list could contain garbage strings and this test would pass.

**Scope of issue:** This pattern (`assertTrue(len(...) > 0)` or `assertGreaterEqual(len(...), 1)`) appears in ~8 places across the test suite. While not catastrophic, each instance is a missed opportunity to verify the actual content.

---

### 9. Permissive Validator — Counting not content

**File:** `test_lifecycle.py`
**Class:** `TestLifecycle`
**Method:** `test_13_full_pipeline` (line 289)

```python
self.assertGreaterEqual(len(self.fake_gh.labels), 15, ...)
self.assertEqual(len(self.fake_gh.milestones), 1, ...)
self.assertEqual(len(self.fake_gh.issues), 2, ...)
```

**Anti-pattern:** Permissive Validator (#10). Checks counts only, not that the right labels/milestones/issues were created. If `create_static_labels()` created 15 labels all named "garbage", this test passes.

**Mitigating factor:** The docstring explicitly states this is "intentionally loose" because it complements `test_hexwise_setup.test_full_setup_pipeline` which does exact assertions. This is a conscious test design strategy, not an oversight.

---

## Tier 3: Missed Opportunities

### 10. Shallow End — Checks structure not computed values

**File:** `test_verify_fixes.py`
**Class:** `TestAgentFrontmatter`
**Methods:** `test_implementer_has_frontmatter`, `test_reviewer_has_frontmatter` (lines 182-188)

```python
def _check_frontmatter(self, path: Path):
    self.assertTrue(path.exists())
    text = path.read_text()
    self.assertTrue(text.startswith("---"))
    end = text.index("---", 3)
    fm = text[3:end]
    self.assertIn("name:", fm)
    self.assertIn("description:", fm)
```

**Anti-pattern:** Shallow End (#8). Verifies the agent files have YAML frontmatter with `name:` and `description:` keys, but never checks the values. The frontmatter could say `name: ""` or `description: "TODO"` and the test would pass. These are static file checks, not logic tests.

---

### 11. Shallow End — Checking key existence not values

**File:** `test_verify_fixes.py`
**Class:** `TestConfigGeneration`
**Method:** `test_generated_toml_has_required_keys` (line 50)

```python
self.assertIn("name", config["project"])
self.assertIn("repo", config["project"])
self.assertIn("language", config["project"])
```

**Anti-pattern:** Shallow End (#8). Verifies keys exist in the generated TOML but not that they have correct values. `name` could be empty, `repo` could be "invalid", and the test passes.

**Mitigating factor:** `test_generated_config_passes_validation` (line 103) runs the full validator which does check values. This test is more about "the shape is right" than "the content is right."

---

### 12. Rubber Stamp — Asserts structure not correctness

**File:** `test_verify_fixes.py`
**Class:** `TestEvalsGeneric`
**Methods:** `test_no_hardcoded_project_names`, `test_no_hardcoded_persona_names`, `test_no_hardcoded_cargo_commands` (lines 194-212)

```python
def test_no_hardcoded_project_names(self):
    evals_path = ROOT / "evals" / "evals.json"
    text = evals_path.read_text()
    self.assertNotIn("Dreamcatcher", text)
```

**Anti-pattern:** Rubber Stamp (#9). These are deny-list tests that check specific old values were removed, not that the current values are correct. They catch regressions for exactly the strings listed, but if someone hardcodes a *different* project name (e.g., "Hexwise"), these tests don't catch it.

---

### 13. Shallow End — Golden replay skip path hides gaps

**File:** `test_golden_run.py`
**Class:** `TestGoldenRun`
**Method:** `_check_or_record` (line 93)

```python
def _check_or_record(self, recorder, replayer, phase_name, check_fn):
    if RECORD_MODE:
        recorder.snapshot(phase_name)
    elif replayer.has_recordings():
        snapshot = replayer.load_snapshot(phase_name)
        diffs = check_fn(snapshot)
        self.assertEqual(diffs, [], ...)
    else:
        if os.environ.get("CI"):
            self.fail(...)
        else:
            self.skipTest(...)
```

**Anti-pattern:** Shallow End (#8). In non-CI, non-RECORD mode, if golden recordings don't exist, the test silently skips. A developer running `pytest` locally with no recordings gets `skipTest` — no failure, no feedback. The CI guard catches this in CI, but local development gets false confidence.

**Mitigating factor:** The code explicitly handles this with a warning and `skipTest`, and CI will fail. This is a known limitation, not a bug.

---

### 14. Rubber Stamp — Testing FakeGitHub instead of production code

**File:** `test_bugfix_regression.py`
**Classes:** `TestFakeGitHubFlagEnforcement`, `TestFakeGitHubShortFlags`, `TestFakeGitHubJqHandlerScoped`, `TestFakeGitHubIssueLabelFilter`, `TestFakeGitHubStrictMode`
**Lines:** 119-831 (approximately 25 tests)

**Anti-pattern:** Not exactly an anti-pattern, but these ~25 tests are testing the test infrastructure (FakeGitHub) rather than production code. They're useful for maintaining the fake, but they inflate the test count without directly verifying product behavior.

**Mitigating factor:** `test_fakegithub_fidelity.py` exists for exactly this purpose. The tests in `test_bugfix_regression.py` overlap with that file's purpose. This is intentional infrastructure testing, which is valid — but should be counted separately from product tests when assessing coverage.

---

### 15. Happy Path Tourist — Missing error path for critical function

**File:** `test_sprint_runtime.py`
**Class:** `TestFormatIssueBody`

**What's tested:** Full story with all fields, minimal story with no fields.
**What's missing:** Stories with malformed acceptance criteria, stories with None values for optional fields, stories where `user_story` is empty but `acceptance_criteria` is populated. The function `format_issue_body` constructs GitHub issue bodies — malformed output could break downstream parsing by `parse_detail_blocks`.

---

### 16. Shallow End — Partial round-trip verification

**File:** `test_sprint_runtime.py`
**Class:** `TestSyncTrackingIO`
**Method:** `test_roundtrip` (line 1680)

The round-trip test checks most fields but uses `assertIn("Some body text", recovered.body_text)` instead of `assertEqual`. This means the body text could have extra garbage prepended/appended and the test would pass.

---

### 17. Shallow End — Velocity percentage not independently verified

**File:** `test_sprint_analytics.py`
**Class:** `TestComputeVelocity`
**Method:** `test_partial_delivery` (line 69)

```python
self.assertEqual(result["percentage"], 62)
```

The test checks that 5/8 = 62%, which is correct. But this is a specific expected value — there's no test for the *formula*. If the code switched from integer division to float division (producing 62.5) or to ceiling (63), the test would catch it. This is fine for a regression test, but there's no property test verifying the formula `percentage = delivered_sp * 100 // planned_sp`.

---

### 18-23. Shallow End — Scanner heuristic tests only check detection, not rejection

**File:** `test_pipeline_scripts.py`
**Classes:** `TestScannerPythonProject`, `TestScannerMinimalProject`

The scanner tests verify that detection methods return the right values for matching inputs. But there are no adversarial tests:
- A Go project with a `pyproject.toml` in a subdirectory (should NOT detect Python)
- A `docs/prd/` directory containing only images (should NOT be detected as PRD dir)
- A team INDEX.md with a table that has wrong column headers

These would test the *specificity* of the detection heuristics, which is where false positives hide.

---

## Tests That Are Genuinely Strong

To be fair, many tests in this suite are well-crafted. Highlights:

1. **`test_property_parsing.py`** — All 36 property-based tests are excellent. They generate random inputs, verify structural invariants, and test round-trip correctness. The `test_quoting_roundtrip` test for `_yaml_safe` is particularly good.

2. **`test_bugfix_regression.py` BH-series** — These regression tests are precise, test specific edge cases that caused real bugs, and have clear docstrings explaining the bug they prevent.

3. **`test_hexwise_setup.py::test_full_setup_pipeline`** — Exact count assertions, verifies all 17 story IDs by name, checks persona label counts. A thorough integration test.

4. **`test_sync_backlog.py::TestCheckSync`** — Tests the debounce/throttle state machine through all 6 transitions. Well-structured, verifies both return values and state mutations.

5. **`test_sprint_runtime.py::TestSyncOneGitHubAuthoritative`** — Installs a spy on subprocess.run to verify sync_one NEVER calls gh CLI to modify GitHub state. This is a behavioral contract test that catches a dangerous architectural violation.

6. **`test_release_gate.py::TestValidateGates`** — Uses real FakeGitHub state instead of mocking individual gate functions. Tests the gate orchestration with actual state setup.

---

## Statistical Summary

| Category | Count | % of Total |
|----------|-------|-----------|
| Tests with genuine behavioral assertions | ~640 | 92% |
| Inspector Clouseau (implementation details) | 4 | 0.6% |
| Shallow End / Rubber Stamp | 14 | 2% |
| Permissive Validator | 3 | 0.4% |
| Tautology / Green Bar Addict | 10+ | 1.5% |
| Mockingbird (over-mocked) | 1 | 0.1% |
| Test infrastructure tests (FakeGitHub) | ~25 | 3.6% |

---

## Recommendations

1. **Replace source inspection tests** (findings #1, #2) with behavioral tests. These are the highest-priority fixes because they give false confidence while being fragile.

2. **Tighten permissive assertions** (finding #8). Replace `assertTrue(len(actions) > 0)` with assertions on action content. This is low-effort, high-value.

3. **Add adversarial scanner tests** (findings #18-23). Test that heuristics reject near-misses, not just accept matches.

4. **Don't count FakeGitHub tests as product coverage.** They're valid infrastructure tests, but should be tracked separately.

5. **The Mockingbird in `TestDoRelease` is acceptable** given the explicit documentation. The real risk is covered by integration tests elsewhere.
