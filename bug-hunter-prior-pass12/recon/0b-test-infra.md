# Recon 0b: Test Infrastructure

## Test Framework

**Primary framework:** Python `unittest` (stdlib) for 11 of 12 test files.
**Secondary framework:** `pytest` + `hypothesis` for `test_property_parsing.py` (property-based tests).

**Runner:** pytest 9.0.2 via `.venv/bin/python -m pytest tests/`

**Python version:** 3.10.15 (via `.venv`)

**No conftest.py, no pytest.ini, no pyproject.toml, no setup.cfg.**

The test suite has no formal configuration file. pytest auto-discovers `test_*.py` files. The `.venv` contains pytest and hypothesis as dev dependencies.

---

## Test File Inventory

12 test files, 5 helper/support files.

### Test Files (sorted by line count)

| File | Lines | Test methods | Focus |
|------|-------|-------------|-------|
| `test_gh_interactions.py` | 3,078 | 257 | Unit tests: commit validation, release gates, check_status, bootstrap, populate, sync_tracking, burndown, TOML parsing, FakeGitHub flag enforcement, BH-series regression tests |
| `test_pipeline_scripts.py` | 1,511 | 137 | team_voices, traceability, test_coverage, manage_epics, manage_sagas, TOML parsing, CI generation, ProjectScanner |
| `test_release_gate.py` | 1,318 | 46 | calculate_version, validate_gates, gate_tests, gate_build, do_release, find_milestone_number |
| `test_verify_fixes.py` | 963 | 43 | Config generation validation, CI generation, agent frontmatter, load_config errors, team index parsing, teardown interactive prompts, gate test for main() coverage |
| `test_sprint_teardown.py` | 525 | 28 | classify_entries, collect_directories, remove_symlinks, remove_generated, remove_empty_dirs, full teardown flow, main() dry-run/execute |
| `test_lifecycle.py` | 465 | 13 | End-to-end lifecycle: init -> bootstrap -> populate -> version -> release notes -> monitoring pipeline |
| `test_property_parsing.py` | 458 | 30 | Hypothesis property-based tests: extract_story_id, extract_sp, _yaml_safe, parse_simple_toml, team index parsing |
| `test_hexwise_setup.py` | 447 | 25 | Scanner detection, config generation, optional paths, Giles persona, definition-of-done, full setup pipeline against hexwise fixture |
| `test_sprint_analytics.py` | 442 | 15 | Persona extraction, velocity, review rounds, workload, report formatting, main() integration |
| `test_sync_backlog.py` | 298 | 18 | File hashing, state persistence, debounce/throttle scheduling, do_sync, main() end-to-end |
| `test_validate_anchors.py` | 285 | 25 | Namespace resolution, anchor definition scanning, anchor reference scanning, check/fix mode |
| `test_golden_run.py` | 217 | 1 | Golden snapshot regression (single test method covering 5 pipeline phases sequentially) |

**Totals: 10,007 lines of test code, 638 test methods across 12 test files**

### Helper/Support Files

| File | Lines | Purpose |
|------|-------|---------|
| `fake_github.py` | 905 | In-memory GitHub API simulator intercepting `subprocess.run` calls to `gh` |
| `golden_replay.py` | 176 | Loads golden snapshots and asserts consistency against current state |
| `mock_project.py` | 148 | Creates minimal mock Rust project for fast tests |
| `gh_test_helpers.py` | 106 | `MonitoredMock` + `patch_gh` context manager to prevent "mock returns what you assert" anti-pattern |
| `golden_recorder.py` | 103 | Records FakeGitHub + file-tree state snapshots for golden testing |

**Total support code: 1,438 lines**
**Grand total test infra: 11,445 lines**

---

## Custom Test Doubles

### FakeGitHub (`tests/fake_github.py`)

Central test double that simulates the GitHub API by intercepting `subprocess.run` calls to `gh`. This is the backbone of the entire test strategy.

**Architecture:**
- `FakeGitHub` class: in-memory state store with dispatch-dict routing
- `make_patched_subprocess(fake_gh)`: returns a `subprocess.run` replacement that routes `gh` calls to FakeGitHub while allowing real subprocess calls (e.g., `git`) to pass through
- Used via `unittest.mock.patch("subprocess.run", make_patched_subprocess(self.fake_gh))`

**State tracked:**
- `labels` (dict), `milestones` (list), `issues` (list), `releases` (list), `runs` (list), `prs` (list), `reviews` (list)
- `timeline_events` (dict: issue# -> events), `comparisons` (dict: branch -> data), `commits_data` (list)
- Auto-incrementing IDs: `_next_issue`, `_next_ms`, `_next_pr`

**Handlers (dispatched by first arg):**
- `label create`, `api` (milestones CRUD, compare, commits, timeline), `issue create/list/edit/close`, `run list/view`, `pr list/create/review/merge`, `release create/view`, `auth`, `--version`

**Safety features:**
- `_KNOWN_FLAGS` registry per handler: unknown flags raise `NotImplementedError`
- `_IMPLEMENTED_FLAGS` subset: strict mode warns on flags that are accepted but don't filter results
- `_VALUE_BEARING_FLAGS`: ensures correct arg consumption
- Unhandled API paths fail loudly (prevents silent false-pass)
- `_filter_json_fields()`: respects `--json` field selection
- `_maybe_apply_jq()`: real jq evaluation when `pyjq` package is available, graceful fallback otherwise
- `dump_state()`: returns full snapshot dict for golden testing

### MonitoredMock / patch_gh (`tests/gh_test_helpers.py`)

Anti-pattern prevention tool (BH-P11-201). Wraps `unittest.mock.patch` and emits a `UserWarning` if a mock is called but `call_args` is never inspected. This catches tests that verify mock return values (always pass) instead of verifying the production code called the mock correctly.

### MockProject (`tests/mock_project.py`)

Creates a minimal mock Rust project in a temp directory:
- Cargo.toml, fake .git/config or real git repo, 2-3 personas, 1 milestone with 2 stories, RULES.md, DEVELOPMENT.md
- Used for fast tests where the full hexwise fixture is overkill

### Golden Recorder/Replayer (`tests/golden_recorder.py`, `tests/golden_replay.py`)

Snapshot-based regression testing:
- Recorder captures FakeGitHub state + file tree at pipeline phase boundaries
- Replayer loads snapshots and asserts labels, milestones, issues, and file trees match
- 5 recorded phases in `tests/golden/recordings/`: init, labels, milestones, issues, CI

---

## Test Fixtures

### Hexwise Fixture (`tests/fixtures/hexwise/`)

A realistic mock Rust project used by 3 test files (hexwise_setup, golden_run, pipeline_scripts):
- `Cargo.toml`, `src/lib.rs`, `src/main.rs` (Rust project structure)
- `docs/team/` — 4 personas (rusti, palette, checker, giles) + INDEX.md + history/ + team-topology.md
- `docs/backlog/` — INDEX.md + 3 milestones with 17 stories
- `docs/agile/sagas/` — 2 saga files, `docs/agile/epics/` — 6 epic files
- `docs/prd/` — 3 sections with INDEX.md
- `docs/test-plan/` — 4 test plan files
- `docs/user-stories/story-map/INDEX.md`
- `RULES.md`, `DEVELOPMENT.md`

### Golden Recordings (`tests/golden/recordings/`)

5 JSON snapshot files + manifest.json. Record mode: `GOLDEN_RECORD=1 python tests/test_golden_run.py -v`

---

## Test Patterns and Conventions

1. **No conftest.py / shared test setup.** Each file independently configures `sys.path` with 3-5 `sys.path.insert(0, ...)` calls. Duplication across all 12 files.

2. **FakeGitHub-centric mocking.** All GitHub interactions go through `patch("subprocess.run", make_patched_subprocess(self.fake_gh))`. Real `git` commands (init, commit, tag) pass through to actual git.

3. **Temp directory pattern.** Most tests create temp directories, copy fixtures, `os.chdir()` into them, and clean up in `tearDown`. Some use `addCleanup()` for cwd restoration, others rely on try/finally.

4. **No parameterized tests** (except hypothesis). All unittest test variations are individual methods, even when they follow repetitive patterns.

5. **Integration tests create real git repos** in temp directories (git init, add remote, commit) so scripts that call git work correctly.

6. **BH-series regression tests** in test_gh_interactions.py (BH-001 through BH-023, BH-P11-* series) correspond to specific bug-hunter findings and are clearly labeled with docstrings explaining what they prevent.

7. **Gate test for main() coverage** (`TestEveryScriptMainCovered`): auto-discovers all scripts with `def main()` and asserts each has a test calling `module.main()`. Scripts without tests are explicitly listed in `_KNOWN_UNTESTED` (12 scripts currently).

8. **Property-based testing** via hypothesis in `test_property_parsing.py` targets 5 regex/parsing hotspots with ~4,500 generated examples total (configurable via `max_examples`).

---

## Potential Concerns

1. **`os.chdir()` in tests:** Many tests change the working directory. If a test fails before tearDown, it can corrupt subsequent tests. Some files use `addCleanup()` properly; others rely on tearDown only.

2. **No coverage measurement:** No pytest-cov, coverage.py, or any coverage tooling configured.

3. **FakeGitHub jq fidelity:** `--jq` is evaluated when the `jq` Python package is available, but falls back to pre-shaped data otherwise. Tests may pass differently depending on whether `jq` is installed.

4. **No test isolation enforcement:** Tests share module-level imports and mutate `sys.path`. Module-level state in imported scripts could theoretically leak between tests.

5. **Golden snapshot brittleness:** Golden recordings are committed to the repo. Any change to label names, milestone structure, or issue format requires re-recording.

6. **Lint target is minimal:** Only `py_compile` (syntax check) + anchor validation. No type checking (mypy), no style linting (ruff/flake8), no import sorting.

7. **12 scripts in `_KNOWN_UNTESTED`** lack main() integration tests: team_voices, sprint_init, traceability, validate_config, manage_sagas, manage_epics, test_coverage, setup_ci, bootstrap_github, populate_issues, update_burndown, release_gate.
