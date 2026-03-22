# Phase 0c — Test Baseline

**Date:** 2026-03-21
**Commit:** 65636ca (main)

## Test Framework

- **Runner:** pytest 9.0.2
- **Python:** 3.10.15
- **Plugins:** hypothesis 6.151.9, cov 7.0.0
- **Config files:** None (no pytest.ini, pyproject.toml, setup.cfg, or tox.ini). Only `ruff.toml` exists for linting.
- **conftest.py:** Adds all script directories to sys.path; enforces `jq` Python package availability.

## Results Summary

| Metric       | Value    |
|-------------|----------|
| Total tests  | 1184     |
| Passed       | 1184     |
| Failed       | 0        |
| Skipped      | 0        |
| Errors       | 0        |
| Subtests     | 19 (all passed) |
| Warnings     | 0        |
| Runtime      | 17.25s   |

**All 1184 tests pass. Zero failures, zero skips, zero warnings.**

## Failing Tests

None.
