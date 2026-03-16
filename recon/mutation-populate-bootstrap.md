# Mutation Testing: populate_issues.py, bootstrap_github.py, setup_ci.py

**Date:** 2026-03-16
**Test suite:** 739 tests (1 pre-broken: `test_middle_failure_pr_gate`; some flaky sprint_runtime tests)
**Baseline:** 738 pass, 1 fail (pre-existing)

## Results Summary

| # | File | Function | Mutation | Result | Killing test(s) |
|---|------|----------|----------|--------|-----------------|
| 1 | populate_issues.py | `create_issue()` | Remove `"kanban:todo"` from labels list | **KILLED** | `test_golden_run::test_golden_full_setup_pipeline` (golden snapshot diff) |
| 2 | populate_issues.py | `parse_milestone_stories()` | Add 1 to every sprint number | **KILLED** | `test_golden_run::test_golden_full_setup_pipeline` (sprint labels shifted) |
| 3 | populate_issues.py | `format_issue_body()` | Remove SP from issue body line | **SURVIVED** | -- |
| 4 | populate_issues.py | `get_existing_issues()` | Return empty set always | **KILLED** | `test_lifecycle::test_07_idempotent_issue_detection`, `test_sprint_runtime::TestGetExistingIssues` (2 tests), `test_sync_backlog::test_do_sync_idempotent` |
| 5 | populate_issues.py | `enrich_from_epics()` | Skip merge step (don't update existing stories) | **KILLED** | `test_hexwise_setup::test_populate_issues_parses_epic_stories` |
| 6 | bootstrap_github.py | `create_label()` | Swap color and description arguments | **KILLED** | `test_lifecycle::test_03_bootstrap_creates_labels`, `test_golden_run::test_golden_full_setup_pipeline` |
| 7 | bootstrap_github.py | `_collect_sprint_numbers()` | Return `{1}` always | **KILLED** | `test_sprint_runtime::TestCollectSprintNumbers` (3 tests: heading, filename, warning) |
| 8 | bootstrap_github.py | `create_milestones_on_github()` | Remove description from API call | **KILLED** | `test_golden_run::test_golden_full_setup_pipeline` (golden snapshot diff) |
| 9 | setup_ci.py | `_python_setup_steps()` | Change default Python from "3.12" to "2.7" | **SURVIVED** | -- |
| 10 | setup_ci.py | `_find_test_command()` | Return `""` always (no test job) | **KILLED** | `test_verify_fixes::TestCIGeneration::test_no_duplicate_test_job` |

## Score

- **Killed:** 8 / 10
- **Survived:** 2 / 10
- **Kill rate:** 80%

## Survived Mutations: Analysis

### Mutation 3: SP removed from `format_issue_body()` output

The line `**US-0101** -- Title | Sprint 1 | 3 SP | P0` was changed to omit `3 SP`.
No test asserts on SP presence in the issue body. The closest test (`test_lifecycle::test_06_populate_creates_issues`) checks `"Story" in body` and `len(body) > 20`, but neither verifies the SP field specifically.

**Gap:** No test asserts `"SP"` or story-point content in `format_issue_body()` output.

**Suggested fix:** Add assertion in `test_06_populate_creates_issues` or a dedicated `test_format_issue_body` unit test:
```python
body = populate_issues.format_issue_body(story)
self.assertIn(f"{story.sp} SP", body)
```

### Mutation 9: Python version changed from "3.12" to "2.7"

The Hexwise fixture is a Rust project, so `_python_setup_steps()` is never exercised by the hexwise pipeline tests. The `test_pipeline_scripts.py::TestCIGeneration` tests generate CI for Python projects but only check for `setup-python@v6` and `pip install`, not the version string.

**Gap:** No test asserts the default Python version in generated CI YAML.

**Suggested fix:** Add a test for Python CI generation that checks the version:
```python
def test_python_ci_default_version(self):
    config = {"project": {"language": "python"}, "ci": {"check_commands": ["pytest"], "build_command": ""}}
    yaml = generate_ci_yaml(config)
    self.assertIn('python-version: "3.', yaml)
    self.assertNotIn("2.7", yaml)
```
