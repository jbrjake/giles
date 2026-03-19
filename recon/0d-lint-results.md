# 0d — Lint Results

## Tool Availability

| Tool | Installed | Config file |
|------|-----------|-------------|
| ruff | Unknown (could not verify — Bash blocked for `which`/`ruff --version`) | No `ruff.toml`, no `[tool.ruff]` in any config |
| flake8 | Unknown | No `.flake8`, no `setup.cfg` |
| pylint | Unknown | No `.pylintrc` |
| mypy | Unknown | No `mypy.ini`, no `.mypy.ini`, no `[tool.mypy]` |
| pyright | Unknown | No `pyrightconfig.json` |
| py_compile | Available (Python 3.10.15) | N/A |

**No `pyproject.toml` exists.** No lint or type-checking configuration of any kind is present in the project. The only dev tooling configured is in `requirements-dev.txt`: pytest, pytest-cov, jq, hypothesis.

> **Recommendation:** Add ruff to `requirements-dev.txt` and a minimal `ruff.toml` or `[tool.ruff]` in a new `pyproject.toml`. Ruff covers both linting and formatting in one tool.

## Runtime Lint Execution

Bash permission was intermittently denied during this recon, preventing execution of:
- `python -m py_compile` on all .py files
- `ruff check` / `flake8` runs
- Tool version checks (`which`, `--version`)

All findings below are from **static grep-based analysis** of the source files.

## Syntax Errors

**None detected via static analysis.** All 20 source files and 22 test files have consistent Python 3.10+ syntax (f-strings, `|` union types, walrus operator usage, dataclass patterns). No obvious syntax issues found through pattern scanning.

## Confirmed Issues

### F811 / Unused Import (1 instance)

| File | Line | Import | Status |
|------|------|--------|--------|
| `scripts/kanban.py` | 16 | `import json` | **Unused** — `json.` never appears; only `gh_json` (from validate_config) is used |

### E501 / Line Too Long (5 instances, >120 chars)

| File | Line | Length (approx) | Content summary |
|------|------|-----------------|-----------------|
| `scripts/manage_sagas.py` | 207 | ~135 | Chained `.get()/.split()` ternary |
| `skills/sprint-setup/scripts/bootstrap_github.py` | 15 | ~125 | Long `from validate_config import ...` |
| `skills/sprint-setup/scripts/populate_issues.py` | 122 | ~130 | Complex regex pattern |
| `skills/sprint-setup/scripts/populate_issues.py` | 430 | ~125 | f-string with many fields |
| `skills/sprint-monitor/scripts/check_status.py` | 23 | ~135 | Long `from validate_config import ...` |

### Consistency: `from __future__ import annotations`

16 of 20 source files use `from __future__ import annotations`. These 4 do not:

| File | Uses `X | None` syntax? | Risk |
|------|------------------------|------|
| `scripts/validate_config.py` | Yes (10 occurrences) | None on 3.10+ (PEP 604), but inconsistent with codebase |
| `skills/sprint-setup/scripts/setup_ci.py` | Yes (2 occurrences) | Same |
| `skills/sprint-setup/scripts/bootstrap_github.py` | No | Cosmetic only |
| `skills/sprint-setup/scripts/populate_issues.py` | Yes (2 occurrences) | Same |

Not a bug (Python 3.10 supports `X | Y` natively via PEP 604), but inconsistent with the rest of the codebase.

## Clean Patterns (no issues found)

| Check | Result |
|-------|--------|
| Bare `except:` (no exception type) | 0 instances |
| Wildcard imports (`from X import *`) | 0 instances |
| `== None` / `== True` / `== False` (should be `is`) | 0 instances |
| Mutable default arguments (`def f(x=[])`) | 0 instances |
| Shadowed builtins as variable names | 0 instances |
| `global` statements | 0 instances |
| Missing `if __name__ == "__main__"` guard | 0 files (all 20 have it) |
| `# type: ignore` comments | 2 instances (both in `sync_backlog.py`, justified for conditional import) |
| `# noqa` comments | 14 instances (all in `tests/`, justified for E402 path-dependent imports) |

## Broad Exception Handling

6 instances of `except Exception` across source files. All are intentional:

| File | Line | Context | Justified? |
|------|------|---------|------------|
| `scripts/sync_backlog.py` | 226 | Catch sync failure, skip state update for retry | Yes — logged, not swallowed |
| `scripts/kanban.py` | 277 | Rollback failure during transition | Yes — CRITICAL warning emitted |
| `scripts/kanban.py` | 334 | Rollback failure during assign | Yes — CRITICAL warning emitted |
| `scripts/validate_config.py` | 491 | TOML parse failure in validation | Yes — added to error list |
| `scripts/validate_config.py` | 672 | TOML parse failure in load_config | Yes — stored for reporting |
| `skills/sprint-monitor/scripts/check_status.py` | 396 | Monitor resilience — don't crash on one check | Yes — logged with traceback |

## Type Annotation Coverage

### scripts/ (13 files)

| File | Functions | With return type | Coverage |
|------|-----------|-----------------|----------|
| `scripts/sprint_init.py` | 51 | 51 | 100% |
| `scripts/validate_config.py` | 42 | 40 | 95% |
| `scripts/kanban.py` | 13 | 12 | 92% |
| `scripts/sprint_teardown.py` | 12 | 11 | 92% |
| `scripts/manage_epics.py` | 9 | 9 | 100% |
| `scripts/sync_backlog.py` | 8 | 7 | 88% |
| `scripts/manage_sagas.py` | 8 | 6 | 75% |
| `scripts/validate_anchors.py` | 8 | 6 | 75% |
| `scripts/traceability.py` | 6 | 5 | 83% |
| `scripts/test_coverage.py` | 6 | 5 | 83% |
| `scripts/sprint_analytics.py` | 6 | 2 | 33% |
| `scripts/commit.py` | 4 | 4 | 100% |
| `scripts/team_voices.py` | 3 | 2 | 67% |
| **Total** | **176** | **160** | **91%** |

### skills/*/scripts/ (7 files)

| File | Functions | With return type | Coverage |
|------|-----------|-----------------|----------|
| `skills/sprint-release/scripts/release_gate.py` | 20 | 17 | 85% |
| `skills/sprint-setup/scripts/populate_issues.py` | 16 | 12 | 75% |
| `skills/sprint-setup/scripts/setup_ci.py` | 14 | 11 | 79% |
| `skills/sprint-monitor/scripts/check_status.py` | 12 | 8 | 67% |
| `skills/sprint-setup/scripts/bootstrap_github.py` | 11 | 11 | 100% |
| `skills/sprint-run/scripts/update_burndown.py` | 6 | 2 | 33% |
| `skills/sprint-run/scripts/sync_tracking.py` | 5 | 2 | 40% |
| **Total** | **84** | **63** | **75%** |

### tests/ (22 files)

64 of 1084 functions have return type annotations (6%). Typical for test files — pytest test functions rarely annotate returns.

## File Size (lines of code, largest first)

| File | Lines |
|------|-------|
| `scripts/validate_config.py` | 1,190 |
| `scripts/sprint_init.py` | 996 |
| `skills/sprint-release/scripts/release_gate.py` | 745 |
| `scripts/kanban.py` | 612 |
| `skills/sprint-setup/scripts/populate_issues.py` | 553 |
| `scripts/sprint_teardown.py` | 497 |
| `skills/sprint-monitor/scripts/check_status.py` | 464 |
| `scripts/manage_epics.py` | 410 |
| `skills/sprint-setup/scripts/setup_ci.py` | 406 |
| `skills/sprint-setup/scripts/bootstrap_github.py` | 338 |

## TODO/FIXME Comments

3 genuine TODOs in source (all in `sprint_init.py`, used as placeholder values in generated config):
- Line 585: `<!-- TODO: populate {dest_rel} -->` (skeleton content)
- Line 629: `repo = "TODO-owner/repo"` (fallback when repo detection fails)
- Line 671: `build_command = "TODO-build-command"` (fallback when build detection fails)

These are intentional placeholders for users to fill in, not deferred work.

## Summary

The codebase is remarkably clean for a project with no linting configuration:

- **0 syntax errors** (static analysis)
- **1 unused import** (`json` in `kanban.py`)
- **5 lines over 120 chars** (all in import statements or complex expressions)
- **4 files** missing `from __future__ import annotations` (cosmetic inconsistency)
- **91% return-type annotation coverage** in scripts/, **75%** in skills/
- **No** bare excepts, wildcard imports, identity comparison errors, mutable defaults, or shadowed builtins

### Files With Most Issues

1. `scripts/kanban.py` — unused `json` import, 2 broad exception catches (both justified)
2. `skills/sprint-monitor/scripts/check_status.py` — long import line, broad exception catch (justified)
3. `skills/sprint-setup/scripts/populate_issues.py` — 2 long lines, missing `__future__` import

### Action Items

| Priority | Item |
|----------|------|
| LOW | Add ruff + minimal config to dev tooling |
| LOW | Remove unused `import json` from `kanban.py` |
| LOW | Add `from __future__ import annotations` to the 4 missing files for consistency |
| LOW | Break up 5 long lines (>120 chars) |
