# Lint & Static Analysis Results

**Date:** 2026-03-15
**Scope:** `scripts/` (12 files), `skills/*/scripts/` (7 files), `tests/` (17 files) -- 36 Python files total
**Python version:** 3.10.15

## Tool Availability

| Tool | Available | Version | Notes |
|------|-----------|---------|-------|
| ruff | No | -- | Not installed |
| flake8 | Yes | at `/usr/local/bin/flake8` | Could not execute (sandbox restriction) |
| pylint | Yes | at `/usr/local/bin/pylint` | Could not execute (sandbox restriction) |
| mypy | No | -- | Not installed |
| pyright | No | -- | Not installed |
| py_compile | Yes | stdlib | Could not execute (sandbox restriction) |

**Note:** The sandbox environment blocked execution of Python interpreters and linting tools. All findings below are from manual static analysis (reading every source file and using regex-based pattern searches). This approach covers the categories ruff/flake8 would flag: unused imports, undefined names, bare excepts, type issues, style issues, security patterns, and code quality issues.

## Syntax Errors

None found. All 36 Python files appear syntactically valid based on manual review. No unclosed brackets, mismatched indentation, or invalid syntax constructs detected.

## Severity: HIGH -- Potential Bugs / Correctness

### H-1: Missing return type annotation on `_parse_value`
**File:** `scripts/validate_config.py:257`
```python
def _parse_value(raw: str):
```
This is the only function in the entire codebase missing a return type annotation. The function can return `bool`, `str`, `int`, or `list`, making it a union type. A type checker would flag every call site as potentially unsafe. (ruff: ANN201, mypy: no-untyped-def)

### H-2: Broad `except Exception` catches (3 instances)
These catch more than intended, potentially swallowing bugs:

1. **`scripts/validate_config.py:420`** -- catches all exceptions during TOML parsing. Could hide `MemoryError`, `KeyboardInterrupt` (in Python < 3.12 this is a BaseException, but `RecursionError` or similar would be swallowed).
2. **`scripts/sync_backlog.py:241`** -- top-level catch-all in `__main__`. Acceptable as a last-resort handler but could hide unexpected errors.
3. **`skills/sprint-monitor/scripts/check_status.py:370`** -- catches Exception from sync_backlog. Could hide import errors or attribute errors.

(ruff: BLE001, pylint: broad-except)

### H-3: `subprocess.run` calls without `timeout` parameter
Many `subprocess.run` calls lack a `timeout`, risking indefinite hangs:

- `scripts/commit.py:65` -- `git diff --cached --name-only` (no timeout)
- `scripts/commit.py:98` -- `git commit` (no timeout)
- `skills/sprint-setup/scripts/bootstrap_github.py:20,27,34` -- `gh --version`, `gh auth status`, `git remote -v` (no timeout on any)
- `skills/sprint-setup/scripts/populate_issues.py:39` -- `gh auth status` (no timeout)
- `skills/sprint-setup/scripts/setup_ci.py:337,362` -- `git rev-parse` (no timeout)
- `skills/sprint-release/scripts/release_gate.py:41,65,385,442,481,499,505,522,530,534,538,543,548,552,560,571,583,590` -- 18 calls without timeout (git tag, git log, git status, git push, etc.)

The `validate_config.gh()` function correctly uses `timeout=60`, but many direct `subprocess.run` calls bypass it. (ruff: S603 consideration)

### H-4: `shell=True` with user-configured commands
**File:** `skills/sprint-release/scripts/release_gate.py:209,225`
```python
r = subprocess.run(cmd, shell=True, ...)
```
Both `gate_tests` and `gate_build` pass user-configured commands (from `project.toml`) to `shell=True`. The code has inline comments acknowledging this is intentional. However, if `project.toml` is attacker-controlled (e.g., a malicious PR modifies it), this is a command injection vector. Severity is mitigated because the user controls their own config file. (ruff: S602, bandit: B602)

## Severity: MEDIUM -- Code Quality / Style

### M-1: Variable shadowing with `f` in f-strings
**File:** `skills/sprint-release/scripts/release_gate.py:364,370`
```python
for f in feats:
    lines.append(f"- {f}")
for f in fixes:
    lines.append(f"- {f}")
```
Using `f` as a loop variable inside f-strings is confusing to read, though it works correctly. The `f` in `f"- {f}"` refers to the loop variable, not the f-string prefix. A linter would flag this as ambiguous (pylint: E741 for single-letter variables, though `f` is technically allowed).

### M-2: Lines exceeding 120 characters (4 instances)
- `scripts/manage_sagas.py:224` (143 chars)
- `skills/sprint-setup/scripts/populate_issues.py:79` (~130 chars)
- `skills/sprint-setup/scripts/populate_issues.py:337` (~130 chars)
- `skills/sprint-monitor/scripts/check_status.py:23` (~140 chars, import line)

(flake8: E501 at line-length=120)

### M-3: Nested function `_add_story` captures mutable closure
**File:** `skills/sprint-setup/scripts/populate_issues.py:105-117`
```python
def _add_story(row: re.Match, sprint_num: int) -> None:
    sid = row.group(1)
    if sid in seen_ids:  # captures seen_ids from outer scope
```
This inner function captures `seen_ids`, `stories`, and `mf` from the enclosing scope. While functional, it makes the control flow harder to follow. A linter would not flag this, but it's a refactoring candidate.

### M-4: `type: ignore` comments
**File:** `scripts/sync_backlog.py:31-32`
```python
bootstrap_github = None  # type: ignore[assignment]
populate_issues = None  # type: ignore[assignment]
```
These are properly scoped suppression comments for the optional import pattern. Not a bug, but signals that a type checker would need these annotations.

### M-5: `_YAML_BOOL_KEYWORDS` defined inside function body
**File:** `skills/sprint-run/scripts/sync_tracking.py:184`
The set `_YAML_BOOL_KEYWORDS` is defined inside `_yaml_safe()`, meaning it's re-created on every call. This should be a module-level constant for performance. (ruff: B023 consideration)

### M-6: Unused imports detected by convention analysis
After checking all import statements against usage in each file:
- **No actual unused imports found.** All imports in all 36 files are used. The `json` import in `manage_epics.py` is used in `main()` for `json.loads`. The `subprocess` import in `sprint_teardown.py` is used in `check_active_loops()`. All `noqa: E402` comments in test files are correct -- they suppress the "module-level import not at top" warning for imports after `sys.path.insert()`.

## Severity: LOW -- Style / Conventions

### L-1: Inconsistent `from __future__ import annotations` usage
12 of 19 source files use `from __future__ import annotations`. Files that do NOT use it:
- `scripts/validate_config.py` (still uses `list[str]`, `dict[str, str]` etc. directly -- works on Python 3.10+ but inconsistent)
- All 3 `skills/sprint-setup/scripts/*.py` files (bootstrap_github, populate_issues, setup_ci)

This is not a bug on Python 3.10+, but inconsistency could cause issues if the project ever needs to support 3.9. (ruff: FA100)

### L-2: Print statements used for logging (166 instances across scripts/)
All scripts use `print()` for output rather than the `logging` module. This is documented as intentional (plugin scripts are CLI tools), but it means there's no way to control verbosity levels. Not a defect given the use case.

### L-3: `# noqa` comments (14 instances)
All in test files, all correct (E402 for imports after `sys.path.insert()`). One in `tests/fake_github.py:102` for F401 (unused import check). All are properly justified.

### L-4: TODO comments (3 instances in source, not counting tests)
- `skills/sprint-setup/scripts/setup_ci.py:240` -- "TODO: Add setup steps for {language}" (generated output, not actual TODO)
- `scripts/sprint_init.py:570` -- "TODO: populate {dest_rel}" (generated stub content)
- `scripts/sprint_init.py:608,650` -- "TODO-owner/repo" and "TODO-build-command" (placeholder values)

All are intentional placeholder values in generated output, not forgotten work items.

### L-5: No `__all__` exports defined
No source file defines `__all__`. For library code, this means `from module import *` would export everything. Since these are all CLI scripts/internal modules, this is acceptable. (ruff: F822 related)

## Undefined Names / Type Issues

**None found.** All name references resolve correctly. The `sys.path.insert()` pattern used across all skill scripts correctly adds the shared `scripts/` directory to the path before importing `validate_config`. Cross-module imports (e.g., `manage_sagas` importing `manage_epics.parse_epic`) are done at function-call time, avoiding circular import issues.

## Security-Adjacent Patterns

| Pattern | Count | Assessment |
|---------|-------|------------|
| `eval()`/`exec()` | 0 | Clean |
| `os.system()` | 0 | Clean |
| Bare `except:` | 0 | Clean |
| `shell=True` | 2 | Documented/intentional (release_gate.py) |
| `.format()` on user strings | 1 | `validate_config.py:567` uses `.format()` but only with controlled `config_dir` value; line 407 explicitly avoids `.format()` in favor of `.replace()` for safety |
| `global` statements | 0 | Clean |

## Summary

| Severity | Count | Category |
|----------|-------|----------|
| HIGH | 4 | Missing type annotation (1), broad except catches (3 locations), subprocess timeout gaps (~25 calls), shell=True with config input (2 calls) |
| MEDIUM | 6 | Variable shadowing (1), long lines (4), closure capture (1), type:ignore (2), constant-in-function (1), -- but no unused imports (0) |
| LOW | 5 | Inconsistent future annotations (7 files), print-logging (166 uses), noqa comments (14), TODOs (3), no __all__ |

**Overall assessment:** The codebase is in solid shape for a plugin project. No syntax errors, no undefined names, no unused imports, no bare excepts, no eval/exec, no mutable default arguments. The most actionable findings are the missing subprocess timeouts (H-3) and the single missing return type annotation (H-1). The broad exception catches (H-2) are borderline -- two of the three are in top-level error handlers where they're arguably appropriate.
