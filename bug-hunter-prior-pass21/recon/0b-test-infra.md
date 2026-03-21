# 0b — Test Infrastructure Recon

## Test Framework and Runner

**Primary framework:** `unittest` (stdlib). 14 out of 15 test files use `unittest.TestCase` exclusively.

**Secondary framework:** `pytest` + `hypothesis` for property-based tests. Only `test_property_parsing.py` uses `pytest`-style classes (no `TestCase` subclass) with `@given` decorators.

**Runner:** The Makefile (`/Makefile`) runs `python -m unittest discover -s tests -v`. Individual docstrings in test files suggest both `python -m unittest tests.test_foo -v` and `python -m pytest tests/test_foo.py -v` are used. There is no `pyproject.toml`, no `pytest.ini`, no `setup.cfg`, and no `tox.ini` -- zero pytest configuration.

**Dev dependencies** (`/requirements-dev.txt`):
- `pytest>=9.0`
- `pytest-cov>=6.0`
- `jq>=1.11` (Python bindings for jq expression evaluation in FakeGitHub)
- `hypothesis>=6`

**Venv:** `.venv/` exists with Python 3.10. The `.hypothesis/` directory (untracked) has ~100 constants files, indicating heavy hypothesis usage.

## conftest.py

Single file: `/tests/conftest.py` (25 lines).

All it does is add script directories to `sys.path`:
- `tests/`
- `scripts/`
- `skills/sprint-setup/scripts/`
- `skills/sprint-run/scripts/`
- `skills/sprint-monitor/scripts/`
- `skills/sprint-release/scripts/`

No shared fixtures, no pytest markers, no parametrize, no autouse. This is the entire conftest hierarchy -- there are no nested conftest files.

Despite the conftest doing path setup, most test files redundantly do their own `sys.path.insert(0, ...)` at the top. The conftest path setup only matters when running via `pytest`; the redundant imports are needed for `python -m unittest`.

## Test Files (15 files, ~784 test methods across ~205 test classes)

| File | Tests | Classes | Focus |
|------|-------|---------|-------|
| `test_sprint_runtime.py` | 168 | 39 | check_status, bootstrap_github, populate_issues, sync_tracking, update_burndown, kanban helpers, extract_sp |
| `test_pipeline_scripts.py` | 138 | 16 | team_voices, traceability, test_coverage, manage_epics, manage_sagas, CI generation |
| `test_verify_fixes.py` | 111 | 47 | Config generation, TOML parser, team index parsing, sync_tracking, update_burndown, manage_epics |
| `test_bugfix_regression.py` | 93 | 42 | Arg-parsing, FakeGitHub infra, BH-001 through BH-023 regressions, check_status.main(), sync_tracking.main() |
| `test_release_gate.py` | 56 | 14 | calculate_version, validate_gates, gate_tests, gate_build, do_release, find_milestone_number |
| `test_gh_interactions.py` | 40 | 8 | commit.py validation, release_gate version calc, gate validation |
| `test_property_parsing.py` | 36 | 5 | Property-based: extract_story_id, extract_sp, _yaml_safe, parse_simple_toml, _parse_team_index |
| `test_sprint_teardown.py` | 32 | 10 | classify_entries, collect_directories, remove_symlinks, remove_generated, main() dry-run/execute |
| `test_hexwise_setup.py` | 25 | 2 | ProjectScanner, ConfigGenerator, full pipeline against hexwise fixture |
| `test_validate_anchors.py` | 25 | 5 | resolve_namespace, find_anchor_defs, find_anchor_refs, check_anchors, fix_missing_anchors |
| `test_sync_backlog.py` | 18 | 5 | hash_milestone_files, state persistence, check_sync debounce/throttle, do_sync, main() |
| `test_sprint_analytics.py` | 15 | 6 | Velocity, review rounds, workload, report formatting, main() integration |
| `test_lifecycle.py` | 13 | 1 | End-to-end: init -> bootstrap -> populate -> version -> release notes -> monitoring pipeline |
| `test_fakegithub_fidelity.py` | 10 | 3 | jq expression verification, search predicate warnings, milestone counters |
| `test_golden_run.py` | 4 | 2 | Golden snapshot recording/replay of full setup pipeline + adversarial assert_files_match tests |

## Test Helpers (5 files)

### `fake_github.py` (987 lines) — The Central Test Double

`FakeGitHub` is an in-memory simulation of `gh` CLI. It intercepts `subprocess.run` calls via `make_patched_subprocess()` which patches `subprocess.run` to route `gh` commands to `FakeGitHub.handle()`.

**What it simulates:**
- `gh label create` (with `--color`, `--description`, `--force`)
- `gh issue create/list/edit/close` (with `--milestone`, `--label`, `--state`, `--search`, `--json`, `--limit`)
- `gh pr create/list/review/merge` (with `--milestone`, `--search`, `--state`, `--json`)
- `gh run list` (with `--branch`, `--json`, `--limit`, `--status`)
- `gh release create/view`
- `gh api` for milestones (create/list/patch), compare endpoints, commits, and timeline events
- `gh auth` and `gh --version` (stubs)
- `--jq` filtering via the Python `jq` package (with graceful fallback if not installed)

**What it does NOT simulate:**
- `git` commands (real git runs against temp repos in integration tests)
- `gh pr diff`, `gh pr checkout`, `gh pr checks`
- `gh repo` commands
- `gh project` (GitHub Projects)
- API endpoints beyond milestones/compare/commits/timeline (unhandled paths return an error via BH-008)
- Rate limiting, pagination semantics (returns all data at once)
- Issue/PR number sequencing across types (fixed in BH19-007: shared `_next_number` counter)
- Webhook events, GitHub Actions workflow dispatch

**Strict mode** (on by default): Warns when tests pass flags that FakeGitHub accepts but doesn't actually use to filter results. The `_KNOWN_FLAGS`, `_IMPLEMENTED_FLAGS`, and `_ACCEPTED_NOOP_FLAGS` registries enforce this. Strict warnings cause test failures in `tearDown` of `TestLifecycle` and `TestHexwisePipeline`.

**Key concern:** The `_parse_flags` method (lines 243-283) handles both `--long` and `-short` flags with value-bearing vs bare flag logic. This is hand-rolled CLI parsing that could diverge from real `gh` flag behavior.

### `mock_project.py` (148 lines)

`MockProject` creates a minimal mock Rust project in a temp directory:
- `Cargo.toml`, persona files (alice/bob, optionally carol), milestone, RULES.md, DEVELOPMENT.md
- Can use real git (`real_git=True`) or fake `.git/config` for repo detection
- Used by `test_lifecycle.py` and `test_verify_fixes.py`

### `gh_test_helpers.py` (155 lines)

Contains:
- **`MonitoredMock`**: Proxy around `MagicMock` that tracks whether `call_args` was ever inspected. Warns if a mock was called but its arguments were never verified (anti-pattern: "mock returns what you assert").
- **`patch_gh()`**: Context manager wrapping `unittest.mock.patch` with `MonitoredMock`.
- **`populate_test_issues()`**: Shared helper for the duplicated issue-population block used by test_hexwise_setup, test_lifecycle, and test_golden_run.

### `golden_recorder.py` (103 lines) + `golden_replay.py` (248 lines)

Golden snapshot system:
- **Recorder** captures FakeGitHub state + file tree at named phases, writes JSON to `tests/golden/recordings/`
- **Replayer** loads snapshots and compares labels (names + colors), milestones (titles + descriptions), issues (titles + labels + milestones), and file contents
- 5 recorded snapshots exist: `01-setup-init`, `02-setup-labels`, `03-setup-milestones`, `04-setup-issues`, `05-setup-ci`

## Fixtures

### `tests/fixtures/hexwise/` — Rich Rust Project Fixture

A complete "hexwise" (hex color utility) Rust project with:
- `Cargo.toml`, `src/main.rs`, `src/lib.rs`
- `RULES.md`, `DEVELOPMENT.md`
- 4 personas: rusti, palette, checker, giles (in `docs/team/`)
- 3 milestones (in `docs/backlog/milestones/`)
- 6 epics (in `docs/agile/epics/`)
- 2 sagas (in `docs/agile/sagas/`)
- PRD documents (in `docs/prd/`)
- Test plan documents (in `docs/test-plan/`)
- Story map (in `docs/user-stories/story-map/`)
- Team topology and history files

Used by: `test_hexwise_setup.py`, `test_golden_run.py`, `test_pipeline_scripts.py`

### `tests/golden/recordings/` — Golden Snapshots

6 JSON files (manifest + 5 phase snapshots) recorded against the hexwise fixture.

## Hypothesis Configuration

No global hypothesis settings profile. Each `@given` decorator in `test_property_parsing.py` sets `@settings(max_examples=N)` individually, with N ranging from 100 to 500. Total of 26 property tests across 5 test classes targeting:
1. `extract_story_id` — 6 properties (never empty, standard IDs extracted, filename-safe, max length, never crashes)
2. `extract_sp` — 8 properties (always int, label/body/table extraction, no false positives, label precedence, never crashes)
3. `_yaml_safe` — 5 properties (never crashes, non-empty preserved, quoting roundtrip, dangerous chars quoted, no unescaped internal quotes)
4. `parse_simple_toml` — 10 properties (random text fuzz, valid TOML never raises, single KV roundtrip, section nesting, string arrays, multiline arrays, multiple sections, unicode escapes, warnings)
5. `_parse_team_index` — 2 properties (row extraction, row count fidelity)

The `.hypothesis/constants/` directory has ~100+ entries, indicating the hypothesis database is actively maintained across runs.

## Observations for Adversarial Attention

### 1. No pytest configuration at all
No markers, no parametrize, no fixtures, no conftest hierarchy. The conftest.py only does sys.path manipulation. Tests could benefit from pytest fixtures for common setup patterns (FakeGitHub + temp dir + config generation appears in at least 6 test files).

### 2. FakeGitHub fidelity gaps
- PR state values are uppercase (`"OPEN"`, `"MERGED"`) per BH19-005, but issue states are lowercase (`"open"`, `"closed"`). This asymmetry could mask bugs.
- The `_parse_flags` method is a hand-rolled CLI parser that could diverge from actual `gh` behavior on edge cases (e.g., `=` in values, consecutive flags without values).
- `--search` only evaluates the `milestone:` predicate. All other search predicates are silently ignored (with a warning in strict mode). Tests using `--search` with anything beyond `milestone:` are testing a no-op.
- The `_issue_create` method manually parses `--title`, `--body`, `--label`, `--milestone` with its own loop (lines 497-517) separate from `_parse_flags`. This duplication means flag parsing is inconsistent between handlers.

### 3. Duplicated test setup patterns
Multiple test files independently create temp dirs, copy the hexwise fixture, `git init`, set up FakeGitHub, run `ProjectScanner`/`ConfigGenerator`, and chdir. This pattern appears in: `test_lifecycle.py`, `test_hexwise_setup.py`, `test_golden_run.py`, `test_sprint_analytics.py`, `test_bugfix_regression.py`, `test_verify_fixes.py`. The `MockProject` helper partially addresses this but only for synthetic projects, not hexwise.

### 4. test_verify_fixes.py and test_bugfix_regression.py are suspiciously large
- `test_verify_fixes.py`: 111 tests across 47 classes. Originally a "verify all bugfixes" file, it has grown into a grab-bag of TOML parser tests, config validation tests, sync_tracking tests, and manage_epics tests. Many of these overlap with `test_sprint_runtime.py` and `test_pipeline_scripts.py`.
- `test_bugfix_regression.py`: 93 tests across 42 classes. Covers arg-parsing, FakeGitHub infrastructure, and BH-series regressions. The "BH-xxx" naming convention suggests these were written in response to specific bugs, but the boundaries between "regression test" and "unit test" are blurred.

### 5. No negative/error-path testing for FakeGitHub itself
`test_fakegithub_fidelity.py` only has 10 tests covering jq expressions, search predicates, and milestone counters. There is no systematic test of FakeGitHub's error responses, what happens with malformed input, or whether its strict mode catches all the gaps it claims to.

### 6. Golden test degradation
`test_golden_run.py` silently skips (not fails) when golden recordings are absent in non-CI environments (line 116: `self.skipTest(...)`). In CI it would fail, but locally a developer could lose golden coverage without noticing. The GOLDEN_RECORD=1 recording step is manual and easily forgotten.

### 7. The Makefile `test` target uses unittest discover, not pytest
Despite having pytest in requirements-dev.txt, the Makefile runs `python -m unittest discover`. This means pytest-cov coverage reporting is not invoked by the default test target, hypothesis tests may behave differently (pytest collects them; unittest discover would miss pytest-style classes without TestCase), and the `.coverage` file in the repo root was likely generated separately.

### 8. scripts/test_coverage.py is NOT a test
`/scripts/test_coverage.py` is a production script that compares planned test cases vs actual test files. It is not a test file and should not be confused with one despite the `test_` prefix in the filename.
