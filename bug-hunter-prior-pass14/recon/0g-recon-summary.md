# Phase 0g: Recon Summary — Pass 14

## Project Overview
Claude Code plugin for agile sprints with persona-based development. 19 production scripts
(stdlib only), 5 skills, 15+ test files. No external runtime dependencies.

## Test Baseline
- **677 passed**, 0 failed, 0 skip — 9.15s
- Framework: pytest running unittest-style classes
- Test files: 15 (largest: test_sprint_runtime.py at 1,854 lines)
- _KNOWN_UNTESTED: empty frozenset — all scripts have main() tests
- `jq` Python package available, fidelity tests in test_fakegithub_fidelity.py
- `pytest-cov` NOT installed — no coverage measurement

## Prior Passes
- 12 prior passes (4→13), 35 items in pass 12, 24 in pass 13
- Pass 13 open items: P13-001 (rollback), P13-005-006 (FakeGitHub jq)
- Most prior items resolved. Key progress: test file split, jq fidelity tests,
  conftest.py, _KNOWN_UNTESTED emptied, golden replay content comparison

## Key Architecture Facts
- Custom TOML parser (no tomllib) with unicode escapes, multiline arrays
- GitHub as source of truth via `gh` CLI
- FakeGitHub mock (944 lines) for offline testing
- Config-driven: everything reads from sprint-config/project.toml
- Symlink-based config: sprint-config/ → project files
- Anchor validation (§namespace.symbol) for doc-code consistency (477 refs)

## Areas of Concern
1. **Release rollback logic** — F-001: local tag not cleaned up on push failure
2. **No coverage measurement** — pytest-cov not installed, no .coveragerc
3. **Test mock density** — do_release tests patch 5+ things, some test only mock interactions
4. **Silent data loss** — milestone title overwrite, saga section dedup
5. **TOCTOU in load_config** — TOML parsed twice (validation + load)
