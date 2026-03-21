# Phase 0g: Recon Summary — Pass 7

## Project Profile
- **19 production scripts** (~7,200 LOC), stdlib-only Python 3.10+
- **12 test files** (11 suites + FakeGitHub infra), **467 tests, 0 failures, 3.18s**
- **Single author**, 52% fix commits in last 50 — hardening phase
- **No coverage tool, no linter configured**

## Architecture Highlights
- Config-driven: everything from `sprint-config/project.toml` via custom TOML parser
- Symlink-based config: `sprint-config/` → project files
- GitHub CLI (`gh`) as sole external interface; FakeGitHub test double intercepts it
- Import chain: all skill scripts `sys.path.insert` to reach shared `validate_config.py`

## Risk Heatmap (from churn + fix history)
1. **validate_config.py** (9 changes, TOML parser edge cases, config contract)
2. **release_gate.py** (8 changes, release-path severity, CRITICAL fix history)
3. **fake_github.py** (4 changes, 4 fix commits about fidelity — mock bugs = false test confidence)
4. **populate_issues.py** (7 changes, regex-based parsing)
5. **sync_tracking.py** (7 changes, state reconciliation)
6. **check_status.py** (5 changes, monitoring edge cases)

## Key Findings from Code Audit
1. `_split_array()` only tracks `"` for string boundaries, not `'` — single-quoted array elements with commas split incorrectly
2. `_infer_sprint_number()` greedy regex matches ANY "Sprint N" in prose, not just headings
3. `gate_prs()` fetches ALL open PRs and filters client-side — misses PRs beyond 500 limit
4. `write_version_to_toml()` section boundary regex `r"^\["` could match multiline array lines
5. Bare `except Exception` on sync_backlog import masks syntax errors
6. `_yaml_safe()` missing trailing-colon case (`value:` without space)
7. `_collect_sprint_numbers()` silent fallback to sprint 1 when no number in filename
8. `_parse_workflow_runs()` fragile multiline detection (indentation heuristic)
9. `commit.py` and `validate_anchors.py` not documented in CLAUDE.md script tables

## Test Coverage Gaps (confirmed by grep)
- `_split_array()` — ZERO direct tests (single-quote array bug completely untested)
- `_infer_sprint_number()` — ZERO direct tests
- `_parse_workflow_runs()` — ZERO direct tests
- `_yaml_safe()` — tests exist but miss trailing-colon edge case
- `gate_prs()` — tests mock gh_json directly, never test the 500-limit warn path
- `write_version_to_toml()` — tests use simple TOML, never test multiline arrays

## Test Quality
- Zero skipped/disabled tests — clean discipline
- FakeGitHub has `_KNOWN_FLAGS` enforcement (good)
- Golden-run regression testing (good)
- Dual mocking approaches (FakeGitHub vs @patch) — not a problem but noted
- Several `assertGreaterEqual` assertions test shape but not content
