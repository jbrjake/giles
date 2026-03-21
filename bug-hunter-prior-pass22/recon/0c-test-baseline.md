# 0c — Test Baseline

## Run command

```
cd /Users/jonr/Documents/non-nitro-repos/giles && python -m pytest tests/ -v --tb=short
```

## Environment

- Python 3.10.15
- pytest 9.0.2
- pluggy 1.6.0
- plugins: hypothesis-6.151.9, cov-7.0.0

## Results

**839 passed, 0 failed, 0 skipped** in 14.72s

## Per-file counts (from non-verbose run)

| Test file | Result |
|---|---|
| test_bugfix_regression.py | all passed |
| test_fakegithub_fidelity.py | all passed |
| test_gh_interactions.py | all passed |
| test_golden_run.py | all passed (4 tests) |
| test_hexwise_setup.py | all passed |
| test_kanban.py | all passed |
| test_lifecycle.py | all passed |
| test_pipeline_scripts.py | all passed |
| test_property_parsing.py | all passed |
| test_release_gate.py | all passed |
| test_sprint_analytics.py | all passed |
| test_sprint_runtime.py | all passed |
| test_sprint_teardown.py | all passed |
| test_sync_backlog.py | all passed |
| test_validate_anchors.py | all passed |
| test_verify_fixes.py | all passed |

## Warnings

None. No warnings emitted during test run.

## Notes

- Hypothesis (property-based) tests included in count; they run with default profile.
- No test marks configured (no `pytest.ini`, no `[tool.pytest.ini_options]`).
- All 839 tests use the patched-subprocess / FakeGitHub approach — no real network calls.
- Lifecycle tests (`test_lifecycle.py`) use real git via `MockProject(real_git=True)`.
