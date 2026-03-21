# Recon 0d: Lint Results

**Date:** 2026-03-15
**Pass:** 12

## Linter Availability

| Linter | Available? | Notes |
|--------|-----------|-------|
| ruff | No | Not installed (system or venv) |
| flake8 | System only | `/usr/local/bin/flake8` -- broken interpreter (points to dead python2.7 path) |
| mypy | No | Not installed |
| pylint | System only | `/usr/local/bin/pylint` -- broken interpreter (points to dead python3.7 path), but still runs via pyenv shim |

No linter is configured in the project itself (no `ruff.toml`, `.flake8`, `pyproject.toml`, or `setup.cfg` with lint config). The `requirements-dev.txt` does not include any linters.

## `make lint` Results

The Makefile `lint` target runs two things:
1. `py_compile` on 19 Python scripts (syntax check only)
2. `validate_anchors.py` (checks section-anchor references in docs)

**Result:** Clean.
- All 19 scripts compile without errors.
- `validate_anchors.py`: 477 references checked, all resolved.

### What `make lint` does NOT do

- No style linting (no flake8/ruff)
- No type checking (no mypy/pyright)
- No import checking (no isort)
- No dead code detection
- No security scanning (no bandit)

The "lint" target is misleadingly named -- it is a syntax check, not a lint.

## flake8 Results (ad hoc run)

Ran flake8 with `--max-line-length=120` across all script directories. **35 issues found:**

### By category

| Code | Count | Description |
|------|-------|-------------|
| E402 | 15 | Module-level import not at top of file |
| F401 | 11 | Imported but unused |
| E501 | 4 | Line too long (>120 chars) |
| F541 | 1 | f-string missing placeholders |
| F841 | 1 | Local variable assigned but never used |
| E127 | 1 | Continuation line over-indented |
| E302 | 1 | Expected 2 blank lines |
| E303 | 1 | Too many blank lines |

### E402 (imports not at top) -- structural, not fixable

All 15 E402 violations are caused by the `sys.path.insert(0, ...)` pattern that skill scripts use to reach `scripts/validate_config.py`. This is an architectural decision (documented in CLAUDE.md) and cannot be eliminated without restructuring the import chain. **Not actionable.**

### F401 (unused imports) -- real issues

| File | Unused import |
|------|--------------|
| `scripts/sprint_analytics.py:20` | `validate_config.gh` |
| `scripts/validate_config.py:15` | `datetime.timezone` |
| `scripts/sprint_init.py:19` | `dataclasses.field` |
| `scripts/sync_backlog.py:25` | `validate_config.ConfigError` |
| `skills/sprint-monitor/scripts/check_status.py:23` | `validate_config.parse_iso_date` |
| `skills/sprint-release/scripts/release_gate.py:18` | `json` |
| `skills/sprint-run/scripts/sync_tracking.py:18` | `datetime.datetime`, `datetime.timezone` |
| `skills/sprint-run/scripts/sync_tracking.py:23` | `validate_config.gh`, `validate_config.warn_if_at_limit` |
| `skills/sprint-run/scripts/update_burndown.py:14` | `json` |

**9 files with 11 unused imports total.** These are low-severity but indicate possible dead code or incomplete refactoring. The `sync_tracking.py` file has 4 unused imports, the most of any file.

### F541 (empty f-string) -- possible bug

`skills/sprint-setup/scripts/populate_issues.py:74` -- an f-string with no `{}` placeholders. This is either a bug (intended to interpolate a variable) or a leftover from refactoring. Worth investigating.

### F841 (unused variable) -- dead code

`skills/sprint-monitor/scripts/check_status.py:387` -- `sprint_dir` is assigned but never used. Likely leftover from refactoring.

## pylint Results (ad hoc run)

Ran pylint with only unused-import/variable warnings enabled.

**Rating: 9.98/10**

Confirmed the same 4 unused imports that flake8 found (subset -- pylint only checked `scripts/`, not `skills/`).

## py_compile Results (all scripts)

All 19 scripts pass syntax check:

```
scripts/validate_config.py        OK
scripts/sprint_init.py             OK
scripts/sprint_teardown.py         OK
scripts/validate_anchors.py        OK
scripts/sync_backlog.py            OK
scripts/sprint_analytics.py        OK
scripts/commit.py                  OK
scripts/traceability.py            OK
scripts/test_coverage.py           OK
scripts/manage_epics.py            OK
scripts/manage_sagas.py            OK
scripts/team_voices.py             OK
skills/sprint-setup/scripts/bootstrap_github.py    OK
skills/sprint-setup/scripts/populate_issues.py     OK
skills/sprint-setup/scripts/setup_ci.py            OK
skills/sprint-run/scripts/sync_tracking.py         OK
skills/sprint-run/scripts/update_burndown.py       OK
skills/sprint-monitor/scripts/check_status.py      OK
skills/sprint-release/scripts/release_gate.py      OK
```

## Actionable Findings

| # | Severity | File | Issue |
|---|----------|------|-------|
| L1 | Low | 9 files | 11 unused imports (F401) -- cleanup opportunity |
| L2 | Low | `populate_issues.py:74` | f-string with no placeholders (F541) -- possible bug |
| L3 | Low | `check_status.py:387` | Unused variable `sprint_dir` (F841) -- dead code |
| L4 | Info | Project | No linter configured in project -- `make lint` is syntax-check-only |
