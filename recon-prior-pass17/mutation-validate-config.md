# Mutation Testing: `scripts/validate_config.py`

**Date:** 2026-03-16
**Baseline:** 739 tests passing
**Method:** Manual single-mutation, run full suite, revert after each

## Results

| # | Mutation | Location | Result | Which test caught it |
|---|----------|----------|--------|---------------------|
| 1 | `raw[1:-1]` -> `raw[2:-1]` (double-quoted string slicing) | `_parse_value` L290 | **KILLED** | `test_bugfix_regression.py::TestBH008NestedArrays::test_nested_arrays_parsed` |
| 2 | Fallback `"todo"` -> `"dev"` for open issues | `kanban_from_labels` L864 | **KILLED** | `test_pipeline_scripts.py::TestKanbanFromLabels::test_empty_labels` |
| 3 | `return int(m.group(1))` -> `return int(m.group(1)) + 1` (label SP) | `extract_sp` L791 | **KILLED** | `test_golden_run.py::TestGoldenRun::test_golden_full_setup_pipeline`, `test_property_parsing.py::TestExtractSp::test_label_extraction` |
| 4 | `slug[:40]` -> `slug[:5]` (truncate story ID slug) | `extract_story_id` L846 | **KILLED** | `test_pipeline_scripts.py::TestExtractStoryId::test_no_colon_returns_sanitized_slug`, `test_golden_run.py` |
| 5 | `len(persona_rows) < 2` -> `len(persona_rows) < 1` (allow single persona) | `validate_project` L492 | **KILLED** | `test_pipeline_scripts.py::TestValidateProjectNegative::test_too_few_personas` |
| 6 | Default `"main"` -> `"master"` | `get_base_branch` L722 | **KILLED** | `test_sprint_runtime.py::TestGetBaseBranch::test_defaults_to_main` |
| 7 | Remove `("ci", "build_command")` from `_REQUIRED_TOML_KEYS` | `_REQUIRED_TOML_KEYS` L414 | **KILLED** | `test_verify_fixes.py::TestValidateProjectMissingKey::test_missing_build_command_fails` |
| 8 | `.resolve().parent` -> `.resolve()` (wrong project root) | `load_config` L651 | **KILLED** | `test_hexwise_setup.py::TestHexwiseSetup::test_optional_paths_present` |
| 9 | Regex `r"Current Sprint:\s*(\d+)"` -> `r"Sprint:\s*(\d+)"` (less specific) | `detect_sprint` L827 | **SURVIVED** | -- |
| 10 | Swap `('"', "'")` to `("'", '"')` in quote detection | `_strip_inline_comment` L206 | **SURVIVED** | -- (equivalent mutation: `in` tuple order is irrelevant) |

## Summary

- **KILLED:** 8/10
- **SURVIVED:** 2/10
- **Equivalent mutations:** 1 (mutation 10 -- tuple member order has no semantic effect)
- **True survivors:** 1 (mutation 9)

## Analysis of Surviving Mutations

### Mutation 9 -- `detect_sprint` regex relaxation (TRUE GAP)

The test in `test_pipeline_scripts.py::TestDetectSprint::test_reads_sprint_number_from_status`
uses `"Current Sprint: 3"` as input, which matches both `r"Current Sprint:\s*(\d+)"` and
`r"Sprint:\s*(\d+)"`. No test provides a SPRINT-STATUS.md with content like
`"Sprint 2 recap\nCurrent Sprint: 3"` where the less-specific regex would incorrectly
match "Sprint 2" instead of "Current Sprint: 3".

**Recommended fix:** Add a test case with a status file containing both "Sprint N" (in a
heading or narrative) and "Current Sprint: M" to verify only the latter is matched.

### Mutation 10 -- Quote order swap (EQUIVALENT)

Swapping the order of elements in `ch in ('"', "'")` to `ch in ("'", '"')` is a no-op.
Python `in` checks membership regardless of tuple order. This is not a test gap.
