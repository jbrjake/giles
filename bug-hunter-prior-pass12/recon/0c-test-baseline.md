# Recon 0c: Test Baseline

## Test Run Results

**Date:** 2026-03-15
**Command:** `.venv/bin/python -m pytest tests/ --tb=short`
**Python:** 3.10.15, pytest 9.0.2, hypothesis 6.151.9

| Metric | Value |
|--------|-------|
| Collected | 634 |
| Passed | 632 |
| Failed | 2 |
| Errors | 0 |
| Skipped | 0 |
| Duration | 9.4s |
| Warnings | 0 (in summary) |

---

## Failing Tests (2)

### 1. `TestCheckDirectPushesFakeGH::test_direct_pushes_detected`

**File:** `tests/test_gh_interactions.py:1536`

**Assertion:**
```
self.assertIn("2 direct push", report[0])
```

**Actual output:**
```
'  Drift: 3 direct push(es) to main since 2026-03-01T00:00:00Z'
```

**Root cause:** The test expects "2 direct push" but the actual report says "3 direct push(es)". The FakeGitHub `commits_data` fixture has 3 commits and the assertion count is wrong. The test was likely written when there were 2 commits in the fixture, then a third was added.

### 2. `TestFakeGitHubStrictMode::test_jq_evaluates_on_release_view`

**File:** `tests/test_gh_interactions.py:2930`

**Assertion:**
```
self.assertNotIn("{", result.stdout)  # not JSON, raw string
```

**Actual output:**
```
'{"url": "https://github.com/testowner/testrepo/releases/tag/v1.0.0"}'
```

**Root cause:** The test expects that when jq is available, `--jq '.url'` on a release view returns a raw string (not JSON). But the `jq` Python package is not installed in the current `.venv`, so FakeGitHub falls back to returning the full JSON object. The test was written assuming `pyjq` (now `jq`) would be installed. Without it, the fallback returns unfiltered JSON, which contains `{`.

---

## Timing Analysis

### Slowest Tests (top 10)

| Test | Duration | Category |
|------|----------|----------|
| `TestParseSimpleToml::test_multiple_sections_independent` | 0.70s | hypothesis (200 examples) |
| `TestParseSimpleToml::test_section_nesting` | 0.58s | hypothesis (300 examples) |
| `TestParseSimpleToml::test_single_kv_roundtrip` | 0.52s | hypothesis (300 examples) |
| `TestExtractStoryId::test_standard_ids_extracted` | 0.49s | hypothesis (300 examples) |
| `TestExtractSp::test_always_returns_int` | 0.35s | hypothesis (300 examples) |
| `TestParseSimpleToml::test_multiline_array` | 0.30s | hypothesis (200 examples) |
| `TestGoldenRun::test_golden_full_setup_pipeline` | 0.21s | integration (5 phases, git init + FakeGitHub) |
| `TestHexwisePipeline::test_full_setup_pipeline` | 0.21s | integration (fixture copy + git init + FakeGitHub) |
| `TestHexwisePipeline::test_ci_workflow_uses_configured_branch` | 0.21s | integration |
| `TestHexwisePipeline::test_ci_workflow_has_cargo` | 0.20s | integration |

### Fast Tests

1,840 tests ran in < 0.005s each. These are primarily unittest tests in `test_gh_interactions.py` and `test_pipeline_scripts.py`.

**No suspiciously fast integration tests.** The integration tests (lifecycle, hexwise, golden) all take 0.10-0.21s, which is reasonable given they create temp directories, run `git init`, copy fixtures, and execute multi-phase pipelines.

---

## Mock Coverage Assessment

### What is mocked

- **GitHub API:** All `gh` CLI calls are intercepted by FakeGitHub. This is the correct approach since production code shells out to `gh`.
- **subprocess.run:** Patched at the call site; real `git` commands pass through.
- **builtins.input:** Patched in teardown interactive tests.
- **sys.argv:** Patched for main() integration tests.
- **sys.stdout:** Patched (via `io.StringIO`) to capture output in main() tests.
- **Various module functions:** `load_config`, `find_milestone` patched in sprint_analytics tests.

### What is NOT mocked (runs for real)

- **git operations:** `git init`, `git add`, `git commit`, `git remote add`, `git tag` all run against real temp repos.
- **File system:** All temp directory creation, file writing, symlink creation, and cleanup is real.
- **Python imports:** Scripts are imported via `sys.path.insert`; their module-level code executes.
- **Config parsing:** `parse_simple_toml()`, `validate_project()`, `load_config()` run against real files.
- **Project scanning:** `ProjectScanner.scan()` runs against real fixture files.
- **Config generation:** `ConfigGenerator.generate()` creates real files and symlinks.

### Assessment

The mocking strategy is well-designed. FakeGitHub is a high-fidelity test double that simulates GitHub at the subprocess boundary, which is exactly where the production code interfaces with GitHub. Everything below that boundary (parsing, file I/O, config validation, project scanning) runs for real, providing genuine integration coverage.

The `MonitoredMock` / `patch_gh` helper is a notably thoughtful anti-pattern prevention tool -- it detects tests that verify mock return values instead of verifying production code called the mock correctly.

---

## Missing Dev Dependency

**hypothesis** was not installed in `.venv` at the start of this run. After `pip install hypothesis`, all 30 property-based tests in `test_property_parsing.py` passed. This dependency should be documented or added to a dev requirements file.

Similarly, the `jq` Python package is referenced by FakeGitHub for jq filter evaluation but is not installed, causing the `test_jq_evaluates_on_release_view` test to fail.

---

## Summary

The test suite is in good shape: 632 of 634 tests pass, with 2 minor failures (off-by-one count and missing `jq` package). The 9.4s total runtime is fast. The test infrastructure is thorough -- FakeGitHub is a ~900-line high-fidelity test double, golden snapshot regression testing catches pipeline drift, property-based tests cover parsing hotspots, and the `TestEveryScriptMainCovered` gate test enforces that new scripts get main() tests.

Key gaps: no coverage measurement, no type checking, 12 scripts lack main() integration tests (tracked in `_KNOWN_UNTESTED`), and dev dependencies (hypothesis, jq) are not formally declared.
