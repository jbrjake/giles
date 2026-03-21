# Recon Summary — Pass 18

## Project State
- 19 production scripts, 16 test files, 750 tests, 85% coverage
- 279 commits, 44% fixes, 17 prior bug-hunter passes
- Single contributor project (Claude Code plugin for agile sprints)

## Test Infrastructure
- pytest + unittest, FakeGitHub test double intercepts subprocess.run
- hypothesis property tests (36), golden/snapshot tests (4)
- MonitoredMock helper catches mock-returns-what-you-assert anti-pattern

## Key Findings

### Real Bugs
1. **check_status.py leading-zero milestone regex** (BH18-001) — 2 regex patterns missing `0*`, silently fails for "Sprint 07"
2. **compute_review_rounds COMMENTED fallback** (BH18-006) — counts COMMENTED-only PRs as 1 round when it should be 0

### Security
3. **shell=True with TOML commands** (BH18-003) — gate_tests/gate_build, supply chain risk
4. **User regex in _build_row_regex** (BH18-004) — ReDoS vector via story_id_pattern

### Design/Coupling
5. **check_status.py redundant API calls** (BH18-002, BH18-009) — 3 milestone queries per cycle instead of 1
6. **_fm_val / _yaml_safe coupling** (BH18-005) — duplicated escape logic must stay in sync
7. **TABLE_ROW regex in 3 files** (BH18-012) — identical regex copy-pasted
8. **_parse_header_table in 2 files** (BH18-013) — identical function copy-pasted

### Doc-Code Drift
9. **definition-of-done.md not in _REQUIRED_FILES** (BH18-007) — documented as required, not validated
10. **Persona count check too low** (BH18-008) — allows 1 dev + Giles, needs 2+ devs
11. **CHEATSHEET.md line numbers stale** (BH18-018) — 279 commits since creation

### Test Gaps
12. **No leading-zero test for check_milestone** (BH18-011) — why BH18-001 survived 17 passes
13. **test_coverage.py at 68% coverage** (BH18-017) — the coverage checker has the worst coverage
