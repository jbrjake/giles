# 0b: Test Infrastructure

**Runner:** pytest
**Config:** conftest.py centralizes sys.path setup
**Style:** mix of unittest.TestCase classes and pytest-style (hypothesis)
**Test Files:** 18 files in tests/
**Support Files:** conftest.py, fake_github.py, gh_test_helpers.py, golden_recorder.py, golden_replay.py, mock_project.py
**Dependencies:** hypothesis, jq (Python), pyjq
**Coverage Tool:** None configured (no pytest-cov in evidence)

## Key Test Infrastructure

- **FakeGitHub:** Full mock of gh CLI with jq filtering (tests/fake_github.py). Major effort -- enables offline testing of all GitHub interactions.
- **gh_test_helpers.py:** patch_gh context manager that redirects gh() and gh_json() to FakeGitHub.
- **mock_project.py:** Creates realistic project scaffolding in temp dirs.
- **golden_recorder/replay:** Record and replay full sprint-setup runs.
- **Property tests:** hypothesis-based tests for TOML parser, story ID extraction, YAML safe quoting. Strong.

## Observations

- No code coverage measurement configured
- jq Python package is a hard requirement for tests (checked in conftest.py)
- Tests are comprehensive but coverage of error/edge paths varies
