# Phase 0c: Test Baseline — Pass 10

## Test Suite Run

**Unable to execute test runner** — bash permission denied for `python` commands in this session.

Prior pass recorded: **520 tests, 0 failures, 0 errors, 0 skips, 2.97s wall-clock**.

### To re-run manually

```bash
cd /Users/jonr/Documents/non-nitro-repos/giles && python -m unittest discover tests/ -v 2>&1
```

## Static Analysis (current codebase)

| Metric | Count |
|--------|-------|
| Test files | 11 |
| Test classes | 123 |
| `def test_*` methods | 524 |

### Per-file breakdown

| File | Classes | Methods |
|------|---------|---------|
| `test_gh_interactions.py` | 64 | 205 |
| `test_pipeline_scripts.py` | 14 | 136 |
| `test_release_gate.py` | 11 | 43 |
| `test_sprint_teardown.py` | 9 | 28 |
| `test_hexwise_setup.py` | 2 | 25 |
| `test_validate_anchors.py` | 5 | 25 |
| `test_verify_fixes.py` | 6 | 19 |
| `test_sync_backlog.py` | 5 | 18 |
| `test_lifecycle.py` | 1 | 13 |
| `test_sprint_analytics.py` | 5 | 11 |
| `test_golden_run.py` | 1 | 1 |

**Note:** Static `def test_` count (524) exceeds the prior run count (520). The 4 extra may be methods in non-TestCase classes, helper methods named `test_*`, or methods added since the last run. Actual unittest discovery count is authoritative.

## Comparison to Pass 9

- Pass 9 start: 508 tests, ended at 510
- Pass 10 prior run: 520 tests (10 more added since pass 9 end)
- Current static count: 524 `def test_*` methods

## Observations

- No coverage tool configured (no pytest-cov, no coverage.py in CI)
- No linter or type checker in test pipeline
- No test skips detected in prior run
- All tests run in-process (no subprocess spawning of test runner)
- Framework: stdlib `unittest` (no pytest)
- Runner: `python -m unittest discover tests/`
- No `__init__.py` in tests/ directory
- Several tests create real git repos in temp dirs and `os.chdir()` into them
- The golden-run test emits UserWarnings if golden recordings are absent (not errors)

## Warnings to Watch For

When running the suite, check stderr for:
1. **UserWarning from test_golden_run.py** — "Golden recordings absent" if `GOLDEN_RECORD` env not set and recordings missing (recordings are present in repo, so this should not appear)
2. **DeprecationWarnings** — possible from `datetime` usage (utcnow vs timezone-aware)
3. **stderr output from _parse_team_index** — test_verify_fixes.py intentionally triggers cell-count warnings on stderr
4. **stderr from _collect_sprint_numbers** — test_gh_interactions.py intentionally triggers "defaulting to sprint 1" warning
