# Recon Summary — Pass 21

## Project: 18 Python scripts, 19 templates, 15 test files, 773 tests, 85% coverage

## Three Systemic Problems

1. **Hand-rolled parsers churn forever (PAT-001):** Custom TOML parser (validate_config.py) has 22 fix-commit touches in 50 commits. Custom YAML emitter (sync_tracking.py) has 16. Each bug-hunter pass finds new edge cases. The parsers will never converge without property testing or replacement.

2. **Duplicated logic diverges silently (PAT-002):** Closed-issue override is triplicated. Short-title extraction, sprint-number inference, story-ID extraction, and frontmatter parsing are each duplicated 2-3x. Comments acknowledge duplication ("consistent with X") without fixing it.

3. **Tests that don't test what they claim (PAT-003):** 26 hypothesis tests invisible to CI. jq-dependent tests silently degrade. 8 mock-return-value tests cover trivial orchestration while bypassing the complex functions. FakeGitHub returns unfiltered data when jq is missing.

## Biggest Surprise: CI runs 0 of 26 property tests
The Makefile uses `python -m unittest discover` which can't find pytest-style classes. The hypothesis tests that have been finding real bugs for 20 passes only run when developers use `pytest` locally. CI has been green without them.

## Coverage Gaps (6 files below 80%)
- test_coverage.py: 68% (the coverage checker itself)
- bootstrap_github.py: 71%
- update_burndown.py: 75%
- populate_issues.py: 76%
- sprint_teardown.py: 76%
- manage_sagas.py: 78%

Gaps cluster around `main()` entry points and functions that call `gh` directly.

## Documentation: Mostly Clean
- All 80+ function references in CLAUDE.md verified
- All 19 skeleton templates present
- All 5 skill paths valid
- Only 2 broken CHEATSHEET.md anchors (from BH18 refactoring)
- README.md says "caps at 3 rounds" and "WIP limits" are advisory, not code-enforced (honest in kanban-protocol.md)

## FakeGitHub: Good but has fidelity gaps
- 987 lines, handles 19 gh subcommands
- Missing: PR statusCheckRollup/createdAt/reviews fields, close-on-merge, run view logs
- jq fallback silently degrades quality of 4+ code paths
- Strict mode with flag registries is a strong pattern

## Churn Analysis
- 50 commits in 25 hours (64% fix commits, 1 feature)
- validate_config.py: #1 churn (22 fix touches)
- sync_tracking.py: #2 churn (16 fix touches)
- fake_github.py: #3 churn (12 fix touches)
- The bug-hunting treadmill has stalled feature work
