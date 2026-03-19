# 0d -- Lint Results

**Date:** 2026-03-19
**Scope:** All `.py` files under `scripts/` (13 files) and `skills/*/scripts/` (7 files)

---

## 1. Linting Configuration

**No linting tools are configured for the project.** None of these files exist:

- `.flake8`, `.pylintrc`, `mypy.ini`, `ruff.toml`, `.ruff.toml`
- `pyproject.toml` (no file at all, so no `[tool.ruff]`, `[tool.mypy]`, etc.)
- `setup.cfg`, `tox.ini`

There is no automated lint check in CI (`setup_ci.py` generates a `docs-lint` job
that checks markdown link rot, but nothing for Python style).

**Verdict:** The project has zero automated Python linting or type checking.

---

## 2. Syntax Check (AST Parse)

Bash was unavailable to run `python -m py_compile` or `ast.parse()` directly. No
syntax errors were detected via manual inspection of all 20 production scripts.

---

## 3. Manual Lint Findings

### 3.1 Bare `except:` Clauses

**None found.** All except blocks specify an exception type.

### 3.2 Mutable Default Arguments

**None found.** All mutable defaults use `field(default_factory=...)` via dataclasses.

### 3.3 Star Imports (`from X import *`)

**None found.**

### 3.4 Shadowed Builtins

**None found.** No variables named `list`, `dict`, `str`, `type`, `id`, `input`,
`format`, `hash`, or `set` shadow builtins in any scope.

### 3.5 Unused Imports

**None found.** Every imported name is referenced in its module. Checked all 20
production scripts.

### 3.6 F-strings Without Interpolation

**None found.** All apparent matches were continuation lines of multi-line f-strings
that contain `{...}` interpolation on adjacent lines.

### 3.7 Broad `except Exception` (7 occurrences)

All are intentional resilience patterns with documented rationale:

| File | Line | Context |
|------|------|---------|
| `scripts/sync_backlog.py` | 226 | Catch-all around `do_sync()` -- must not crash the monitor loop; logs and retries |
| `scripts/kanban.py` | 278 | Rollback handler -- if disk write fails during GitHub error recovery |
| `scripts/kanban.py` | 342 | Same pattern for persona assignment rollback |
| `scripts/validate_config.py` | 505 | TOML parse failure -- converts to validation error message |
| `scripts/validate_config.py` | 686 | Same TOML parse path in `load_config()` |
| `skills/sprint-monitor/scripts/check_status.py` | 405 | `sync_backlog_main()` failure -- monitor must not crash |
| `skills/sprint-monitor/scripts/check_status.py` | 450 | Individual check failure -- monitor reports error and continues |

**Verdict:** Appropriate for a monitoring/orchestration tool. Each is documented
with a BH-bug-hunter ticket reference or inline comment.

### 3.8 `shell=True` in subprocess (2 occurrences)

Both in `skills/sprint-release/scripts/release_gate.py`:

- **Line 219:** `gate_tests()` -- runs user-configured `check_commands` from project.toml
- **Line 237:** `gate_build()` -- runs user-configured `build_command`

Both have a detailed trust model docstring (BH18-003) explaining that project.toml
is a trusted input. This is the correct approach for user-specified shell commands.

### 3.9 Comparison to Literal Values

**No `== True`, `== False`, or `== None`** found in production code. Proper use of
`is None`/`is not None` and truthiness checks throughout.

**No `len(x) == 0` or `len(x) > 0`** found. Proper use of `if not x` / `if x`
throughout.

A few `== ""` comparisons exist in table-parsing code (`validate_config.py:898`,
`manage_epics.py:101`) where they check `field.strip() == ""` -- these are correct
since they are testing string equality, not truthiness.

### 3.10 Global Variable Mutation

**No `global` keyword used** in any production script. Module-level constants
(all-caps names) are set once at import time and never mutated.

### 3.11 Assert in Production Code

**None found.** No `assert` statements in any production script (only in tests).

---

## 4. Style Consistency Findings

### 4.1 Inconsistent `from __future__ import annotations`

12 of 13 `scripts/*.py` files use `from __future__ import annotations`. Missing from:

- **`scripts/validate_config.py`** -- the most-imported module in the project

4 of 7 `skills/*/scripts/*.py` files use it. Missing from:

- **`skills/sprint-setup/scripts/setup_ci.py`**
- **`skills/sprint-setup/scripts/bootstrap_github.py`**
- **`skills/sprint-setup/scripts/populate_issues.py`**

Since the project targets Python 3.10+, this import is not *required* (the `list[str]`,
`dict[str, ...]`, and `X | Y` syntax are natively available). However, the
inconsistency is a style issue -- either all files should use it or none should.

**Severity:** Low (cosmetic). No runtime impact on 3.10+.

### 4.2 Mixed `os.path` and `pathlib` Usage

The project consistently uses `pathlib.Path` everywhere, except in `scripts/sprint_init.py`:

- **Line 570:** `os.path.relpath(target_abs, link_path.parent)`
- **Line 965:** `os.path.abspath(root)`
- **Line 967:** `os.path.isdir(root)`

These could be `Path.relative_to()`, `Path.resolve()`, and `Path.is_dir()` for
consistency. The `os.path.relpath` usage is actually necessary because
`Path.relative_to()` does not compute `../` relative paths (it raises ValueError
when the target is not a descendant), so this specific usage is correct.

**Severity:** Low (the `os.path.relpath` is necessary; the others are cosmetic).

### 4.3 Long Lines (>120 characters)

Only 5 lines across all production scripts exceed 120 characters:

| File | Line | Length | Content |
|------|------|--------|---------|
| `skills/sprint-monitor/scripts/check_status.py` | 23 | ~155 | Long `from validate_config import ...` line |
| `skills/sprint-setup/scripts/bootstrap_github.py` | 15 | ~122 | Long `from validate_config import ...` line |
| `skills/sprint-setup/scripts/populate_issues.py` | 122 | ~127 | Complex regex pattern |
| `skills/sprint-setup/scripts/populate_issues.py` | 435 | ~130 | f-string building issue body |
| `scripts/manage_sagas.py` | 207 | ~128 | Chained ternary expression |

**Severity:** Low. No lines exceed 150 characters.

### 4.4 `sys.path.insert` Proliferation

Every script that imports from `validate_config.py` manipulates `sys.path` at module
level. This is documented as an architectural decision in CLAUDE.md, and test files
use a `conftest.py` to centralize it. Not a bug, but worth noting.

### 4.5 TODO/FIXME Markers

Found in production code (not tests):

| File | Line | Marker |
|------|------|--------|
| `scripts/sprint_init.py` | 585 | `<!-- TODO: populate ... -->` (template content, not code TODO) |
| `scripts/sprint_init.py` | 629 | `'repo = "TODO-owner/repo"'` (placeholder in generated config) |
| `scripts/sprint_init.py` | 671 | `'build_command = "TODO-build-command"'` (placeholder in generated config) |
| `skills/sprint-setup/scripts/setup_ci.py` | 246 | `# TODO: Add setup steps for {language}` (fallback for unknown languages) |

These are all intentional placeholder text for user-facing generated files, not
forgotten code changes.

---

## 5. Resource Safety

### 5.1 File Handle Management

**All `open()` calls use `with` statements.** No file handle leaks found.

### 5.2 Encoding

**All `.read_text()`, `.write_text()`, and `open()` calls specify `encoding="utf-8"`.**
No implicit encoding reliance.

### 5.3 File Locking

`scripts/kanban.py` properly uses `fcntl.flock()` with `LOCK_EX`/`LOCK_UN` for
story and sprint file locking. Lock files use `.lock` suffix convention.

---

## 6. Exception Handling Quality

### 6.1 Silent Exception Swallowing (`except ...: pass`)

Found in 12 locations across production code. All are appropriate:

- **`validate_config.py:100,358`** -- fallback parsing (try JSON, fall through to raw string)
- **`sprint_init.py:239,347,472`** -- skip unreadable files during project scanning
- **`sprint_teardown.py:56,185,200,306,455`** -- ignore missing files during cleanup (idempotent teardown)
- **`populate_issues.py:217`** -- ignore invalid regex pattern (falls back to default)
- **`check_status.py:240,418,431`** -- ignore GitHub API failures in monitoring (best-effort checks)

### 6.2 Exception Chaining

Only one explicit `from None` usage (`validate_config.py:74`). Other re-raises use
bare `raise` (preserving the original exception). No cases of re-raising a different
exception type without `from exc` or `from None` were found.

---

## 7. Summary

| Category | Findings | Severity |
|----------|----------|----------|
| Linting tools configured | None | Medium -- no guardrails |
| Bare `except:` | 0 | -- |
| Mutable default args | 0 | -- |
| Star imports | 0 | -- |
| Shadowed builtins | 0 | -- |
| Unused imports | 0 | -- |
| F-strings without interpolation | 0 | -- |
| `from __future__` inconsistency | 4 files missing | Low |
| Mixed os.path / pathlib | 3 lines in 1 file | Low |
| Lines > 120 chars | 5 lines | Low |
| Broad `except Exception` | 7 occurrences (all documented) | Info |
| Silent `except: pass` | 12 occurrences (all appropriate) | Info |
| `shell=True` | 2 occurrences (trust model documented) | Info |

**Overall assessment:** The codebase is remarkably clean for a project with no
automated linting. Zero classic Python anti-patterns (no bare excepts, no mutable
defaults, no star imports, no shadowed builtins, no unused imports). The only
actionable finding is the lack of any linting tooling -- adding `ruff` with a
minimal config would codify the existing high standards and prevent regressions.
