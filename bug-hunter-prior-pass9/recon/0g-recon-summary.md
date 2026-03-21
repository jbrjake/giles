# Phase 0g: Recon Summary — Pass 9

## Project Profile
- **32 Python files** (~16K LOC): 18 production scripts (7,319 LOC) + 14 test files (8,671 LOC)
- **508 tests, 0 failures, 3.0s** — all stdlib unittest, no pytest
- **Single author**, 44% fix commits in last 50 — late-stage hardening continues
- **No coverage tool, no linter, no type checker configured**
- **8 prior bug-hunter passes** — project has been through extensive auditing

## Architecture Highlights
- Hub dependency: `validate_config.py` (806 LOC) imported by every script
- Custom TOML parser — persistent bug magnet (13+ changes across passes)
- FakeGitHub test double (736 LOC) — central mock with known fidelity gaps
- Symlink-based config, GitHub CLI as sole external interface
- All scripts stdlib-only Python 3.10+, no pip dependencies

## Risk Heatmap (from churn + audit findings)
1. **FakeGitHub** — mock fidelity gaps (--jq no-op, pagination no-op) cascade to every test
2. **validate_config.py** — extract_sp regex too greedy, gh() timeout too short
3. **populate_issues.py** — --jq + --paginate invalid JSON for multi-page results
4. **manage_epics.py** — crashes on incomplete dicts, no duplicate ID check
5. **update_burndown.py** — regex eats trailing content in SPRINT-STATUS.md
6. **test quality** — ~50 duplicate tests, 3 tautological tests, golden test silently skips

## Key New Findings (not in prior passes)
1. FakeGitHub --jq no-op has known fidelity gaps (documented in comments but no test mitigation)
2. Golden test silently skips on fresh checkouts — zero regression protection by default
3. extract_sp regex matches "sp" as substring ("wasp: 3" → 3)
4. _format_story_section crashes with KeyError on incomplete dicts
5. ~50 duplicate tests across test files inflate count by ~15%
6. 15+ production functions have zero direct test coverage
7. 7 doc drift items (wrong paths, stale descriptions, missing features)
8. VOICE_PATTERN regex misparses lines with interior quotes
9. Rust test scanner misses async tests (#[tokio::test])
10. manage_sagas update-index missing argument validation
