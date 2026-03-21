# Recon 0g: Summary — Pass 11

## Project Profile
- Claude Code plugin for agile sprints with persona-based development
- 19 Python scripts (stdlib only), 5 skills, 19 skeleton templates
- 546 tests in 11 test files, all passing in 2.7s
- Zero external dependencies; GitHub CLI (`gh`) as sole external integration
- 10 prior bug-hunter passes have fixed 100+ issues; codebase is deep in audit-fix mode

## Test Infrastructure
- unittest-only (no pytest in production), FakeGitHub mock intercepts `subprocess.run`
- FakeGitHub: dispatch-dict routing, known-flags enforcement, but `--jq` NOT evaluated
- Golden snapshot tests degrade silently when recordings absent (warn, don't fail)
- No coverage measurement whatsoever
- MockProject duplicated across test_lifecycle.py and test_verify_fixes.py

## Highest-Risk Files (by churn + bug history)

### Tier 1: Structural risk
1. **`scripts/validate_config.py`** (20 mods/100 commits, fixed in 8 passes) — TOML parser, shared helpers
2. **`tests/fake_github.py`** (11 mods, 6 passes) — mock fidelity gaps, silent flag acceptance
3. **`skills/sprint-release/scripts/release_gate.py`** (16 mods, 7 passes) — complex release flow, rollback

### Tier 2: Parsing fragility
4. **`skills/sprint-setup/scripts/populate_issues.py`** (15 mods, 6 passes) — markdown table parsing
5. **`scripts/sprint_init.py`** (12 mods) — auto-detection heuristics

### Tier 3: State management
6. **`skills/sprint-run/scripts/sync_tracking.py`** (14 mods, 6 passes) — GitHub-to-local reconciliation
7. **`skills/sprint-run/scripts/update_burndown.py`** (11 mods) — section replacement, frontmatter

### Tier 4: Fix magnets (created recently, fixed every pass since)
8. **`scripts/sprint_analytics.py`** (14 mods) — created Mar 11, fixed 5/5 passes since
9. **`scripts/manage_epics.py`** (12 mods) — renumber, duplicate IDs
10. **`scripts/manage_sagas.py`** (11 mods) — subsection handling

## Recurring Bug Patterns (from churn analysis)
1. **Regex over/under-matching** (8+ instances) — happy-path regexes broken by adversarial input
2. **FakeGitHub fidelity gaps** (6+) — flags accepted but not implemented; tests pre-shape data
3. **TOML parser edge cases** (5+) — keeps hitting spec corners
4. **Doc-code drift** (7+) — docs aspirational, code diverges
5. **Test quality** (6+) — tautological assertions, mock-shape verification

## Test Coverage Gaps
- Scripts with no dedicated test file: portions of commit.py, traceability.py, test_coverage.py
- Scripts tested only through pipeline tests (indirect): manage_epics, manage_sagas, team_voices
- FakeGitHub `--jq` never evaluated — tests verify pre-shaped fixture data
- `shell=True` in gate_tests/gate_build untested for command injection
- Pagination not tested (warn_if_at_limit warns but doesn't paginate)

## Audit Priority Order
1. **validate_config.py** — TOML parser edge cases, gh_json incremental decoder, shared helpers
2. **release_gate.py** — gate validation, rollback, version bumping, error recovery
3. **fake_github.py** — unimplemented flags, endpoint fidelity, jq gap
4. **populate_issues.py** — markdown parsing, milestone mapping
5. **sync_tracking.py / update_burndown.py** — state reconciliation, frontmatter consistency
6. **sprint_analytics.py** — review round data path, search query construction
7. **check_status.py** — CI check logic, error keyword filtering
8. **sprint_init.py** — auto-detection edge cases
9. **Test quality sweep** — assertion strength, mock abuse, duplicate tests
