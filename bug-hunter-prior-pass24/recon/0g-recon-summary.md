# 0g - Recon Summary (Pass 24)

## Project Profile
- 20 Python scripts, ~8700 lines production code
- 16 test files, ~15200 lines test code, 889 tests, 85% coverage
- All tests pass, 0 skipped, 0 failures
- 22 prior bug-hunting passes, ~140+ fixes applied (BH-prefix comments)

## High-Risk Areas (from churn + coverage analysis)
1. **kanban.py** (82% coverage, 12 touches in 50 commits, 9+ distinct bug fixes)
2. **validate_config.py** (94% coverage but TOML parser + YAML writer repeatedly patched)
3. **sync_tracking.py** (88% coverage, 5 touches, concurrent write path with kanban.py)
4. **release_gate.py** (89% coverage, complex rollback chain, had P0 null-byte crash)

## Lowest Coverage Modules (targets for test audit)
- test_coverage.py: 68%
- bootstrap_github.py: 71%
- update_burndown.py: 74%
- sprint_teardown.py: 76%
- populate_issues.py: 77%
- manage_sagas.py: 78%

## Structural Concerns
- Two parallel write paths to tracking files (kanban.py + sync_tracking.py)
- Only kanban.py uses file locking; sync_tracking.py doesn't
- TOCTOU window: kanban.py reads TF before acquiring lock in main()
- Custom TOML parser with 10+ patches across 4 bug-hunting passes
- _yaml_safe/frontmatter_value must be exact inverses (complex invariant)
- 6 MonitoredMock warnings suggest unchecked mock contracts in test_kanban.py
