# 0d — Lint Results (BH37)

**Date:** 2026-03-21
**Tools:** ruff 0.x (default rules), py_compile
**No linter config** (no pyproject.toml, ruff.toml, .flake8, etc.) — ran ruff with defaults.

## Summary

| Category | Count | Severity |
|----------|-------|----------|
| **Syntax errors** (py_compile) | 0 | — |
| **F401** — unused imports | 30 | LOW (cleanup) |
| **F841** — unused variables | 20 | LOW (cleanup) |
| **F811** — redefined-while-unused | 6 | MEDIUM (potential confusion) |
| **F541** — f-string missing placeholders | 3 | LOW (dead f-prefix) |
| **E741** — ambiguous variable name (`l`) | 35 | LOW (style) |
| **E402** — import not at top of file | 76 | NOISE (by-design, sys.path.insert pattern) |
| **E401** — multiple imports on one line | 4 | LOW (style) |
| **Total** | **174** | |

## Verdict

No syntax errors. No undefined-name (F821) issues. The codebase compiles cleanly.

Most issues are noise or low-severity cleanup. The E402 violations are structural (scripts must `sys.path.insert` before importing project modules) and should be suppressed project-wide.

The items worth acting on are the **unused imports in production scripts** (not tests) and the **f-string without placeholders** bug.

---

## Production Script Issues (Worth Fixing)

### F401 — Unused imports in scripts

| File | Line | Import |
|------|------|--------|
| `scripts/kanban.py` | 39 | `_yaml_safe` from validate_config |
| `scripts/manage_sagas.py` | 24 | `TABLE_ROW` from validate_config |
| `skills/sprint-monitor/scripts/check_status.py` | 15 | `json` |
| `skills/sprint-run/scripts/sync_tracking.py` | 30 | `frontmatter_value` from validate_config |
| `skills/sprint-run/scripts/sync_tracking.py` | 32 | `write_tf` from validate_config |
| `skills/sprint-run/scripts/sync_tracking.py` | 32 | `_yaml_safe` from validate_config |

### F541 — f-string without placeholders (bug)

| File | Line | Detail |
|------|------|--------|
| `skills/sprint-release/scripts/release_gate.py` | 547 | `f"Run manually: git revert HEAD && git push"` — f-prefix is dead, no `{}` |
| `tests/test_lifecycle.py` | 190 | f-string with no placeholders |

### F811 — Redefined-while-unused (production)

None in production scripts. All 6 are in test files (see below).

### E741 — Ambiguous variable name in production

| File | Line | Var |
|------|------|-----|
| `skills/sprint-monitor/scripts/check_status.py` | 283 | `l` in list comprehension |
| `skills/sprint-monitor/scripts/check_status.py` | 361 | `l` in list comprehension |

---

## Test File Issues (Lower Priority)

### F401 — Unused imports in tests

| File | Line | Import |
|------|------|--------|
| `tests/test_bugfix_regression.py` | 19 | `subprocess` |
| `tests/test_golden_run.py` | 30 | `get_milestones` |
| `tests/test_hooks.py` | 831 | `needs_verification`, `_has_staged_source_files` |
| `tests/test_kanban.py` | 6 | `textwrap` |
| `tests/test_kanban.py` | 79 | `TRANSITIONS` |
| `tests/test_kanban.py` | 83 | `_UPDATABLE_FIELDS` |
| `tests/test_lifecycle.py` | 27 | `validate_message`, `check_atomicity` |
| `tests/test_new_scripts.py` | 349 | `list_open_risks` |
| `tests/test_sprint_analytics.py` | 13 | `json` |
| `tests/test_sprint_runtime.py` | 13 | `json` |
| `tests/test_sprint_runtime.py` | 15 | `subprocess` |
| `tests/test_sync_backlog.py` | 5 | `json` |
| `tests/test_validate_anchors.py` | 142 | `os` |
| `tests/test_verify_fixes.py` | 12 | `subprocess` |
| `tests/test_verify_fixes.py` | 1841 | `ProjectScanner` |

### F841 — Unused variables in tests

| File | Line | Variable |
|------|------|----------|
| `tests/test_bugfix_regression.py` | 632 | `ctx` |
| `tests/test_bugfix_regression.py` | 896 | `mock` |
| `tests/test_kanban.py` | 1123 | `changes` |
| `tests/test_kanban.py` | 1136 | `changes` |
| `tests/test_lifecycle.py` | 274 | `config` |
| `tests/test_lifecycle.py` | 335 | `config` |
| `tests/test_lifecycle.py` | 476 | `config` |
| `tests/test_sprint_runtime.py` | 1345 | `changes` |
| `tests/test_sprint_runtime.py` | 1418 | `changes` |
| `tests/test_sprint_runtime.py` | 2153 | `fake` |
| `tests/test_sync_backlog.py` | 270, 287, 304 | `config_dir` |
| `tests/test_verify_fixes.py` | 2493 | `result` |
| `tests/test_verify_fixes.py` | 2526 | `result` |
| `tests/test_verify_fixes.py` | 2776 | `original_unlink` |

### F811 — Redefined-while-unused in tests

| File | Line | Symbol | Original line |
|------|------|--------|---------------|
| `tests/test_sprint_runtime.py` | 2365 | `TestWriteBurndown` (class) | 1546 |
| `tests/test_verify_fixes.py` | 389 | `patch` | 17 |
| `tests/test_verify_fixes.py` | 883 | `populate_issues` | 31 |
| `tests/test_verify_fixes.py` | 1007 | `update_burndown` | 35 |
| `tests/test_verify_fixes.py` | 1011 | `manage_epics` | 40 |

Note: `TestWriteBurndown` class redefinition at line 2365 in `test_sprint_runtime.py` means the first class's tests (line 1546) are **silently shadowed** and never run. This is a real bug.

### E741 — Ambiguous variable `l` in tests

35 occurrences across `tests/fake_github.py`, `tests/golden_replay.py`, `tests/test_fakegithub_fidelity.py`, `tests/test_hexwise_setup.py`, `tests/test_kanban.py`, `tests/test_new_scripts.py`, `tests/test_pipeline_scripts.py`, `tests/test_validate_anchors.py`, `tests/test_verify_fixes.py`. All are `l` used in list comprehensions. Cosmetic.

### E401 — Multiple imports on one line

| File | Line |
|------|------|
| `tests/test_hooks.py` | 903 |
| `tests/test_sprint_runtime.py` | 338 |
| `tests/test_pipeline_scripts.py` | 466 |
| `tests/test_pipeline_scripts.py` | 281 |

---

## Suppressed / By-Design (E402)

76 E402 violations. All caused by the `sys.path.insert(0, ...)` pattern that must precede project imports. This is the intended architecture (see CLAUDE.md: "Scripts import chain"). Recommend adding a `ruff.toml` or `[tool.ruff]` in `pyproject.toml` to suppress E402 project-wide, or per-file `# noqa: E402` where already present.

---

## Recommendations

1. **Fix now:** Remove 6 unused imports in production scripts (kanban.py, manage_sagas.py, check_status.py, sync_tracking.py).
2. **Fix now:** Remove dead `f` prefix in `release_gate.py:547`.
3. **Fix now:** Rename duplicate `TestWriteBurndown` class in `test_sprint_runtime.py:2365` — first class's tests are silently lost.
4. **Configure ruff:** Add `ruff.toml` with `ignore = ["E402"]` to suppress the 76 structural false positives.
5. **Cleanup pass:** Remove unused imports/variables in test files (30+ items, auto-fixable with `ruff check --fix`).
