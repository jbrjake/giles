# Phase 0b: Test Infrastructure

## Framework & Runner

**Framework:** `unittest` (Python stdlib). Every test file subclasses `unittest.TestCase`.
No pytest fixtures, markers, or parametrize decorators are used anywhere.

**Runner:** `python -m unittest discover -s tests -v` (via `make test`). The Makefile
defines the canonical runner. Despite this, pytest 9.0.2 has been used at least once
locally — `__pycache__` contains `.cpython-310-pytest-9.0.2.pyc` files for all 10 test
modules. The tests are unittest-style but pytest-compatible (no conflicts observed).

**CI runner:** `.github/workflows/ci.yml` runs `make test` (i.e., `unittest discover`)
across a Python matrix: 3.10, 3.11, 3.12, 3.13. No coverage reporting in CI.

**Lint step:** `make lint` runs `py_compile` on every script (18 files) and then
runs `scripts/verify_line_refs.py`. No ruff, flake8, mypy, or type-checking.

**No test configuration files:** No `conftest.py`, `pytest.ini`, `setup.cfg`,
`pyproject.toml`, or `.coveragerc` exist anywhere in the repo.


## Test Files & Coverage Map

| Test File | Tests Source File(s) | Pattern | Test Count |
|-----------|---------------------|---------|------------|
| `test_verify_fixes.py` | `validate_config.py`, `sprint_init.py`, `setup_ci.py`, agents | unit | 13 |
| `test_lifecycle.py` | `sprint_init.py`, `bootstrap_github.py`, `populate_issues.py`, `release_gate.py`, `update_burndown.py`, `commit.py` | integration (end-to-end pipeline with MockProject + FakeGitHub) | 13 |
| `test_hexwise_setup.py` | `sprint_init.py`, `validate_config.py`, `bootstrap_github.py`, `populate_issues.py`, `setup_ci.py` | integration (hexwise fixture) | 25 |
| `test_golden_run.py` | Same pipeline as above | integration/regression (golden snapshot record/replay) | 1 |
| `test_gh_interactions.py` | `commit.py`, `release_gate.py`, `check_status.py`, `bootstrap_github.py`, `populate_issues.py`, `sync_tracking.py`, `update_burndown.py`, `sprint_analytics.py` | unit (FakeGitHub or `unittest.mock.patch`) | 142 |
| `test_release_gate.py` | `release_gate.py` | unit + integration (FakeGitHub + mock subprocess) | 30 |
| `test_sprint_teardown.py` | `sprint_teardown.py` | unit (temp dirs with real symlinks) | 28 |
| `test_pipeline_scripts.py` | `team_voices.py`, `traceability.py`, `test_coverage.py`, `manage_epics.py`, `manage_sagas.py`, `validate_config.py`, `setup_ci.py`, `sprint_init.py` | unit + integration (hexwise fixture) | 122 |
| `test_sync_backlog.py` | `sync_backlog.py` | unit (FakeGitHub) | 18 |
| `test_sprint_analytics.py` | `sprint_analytics.py` | unit (FakeGitHub) | 11 |

**Total: 403 `def test_` methods across 10 test files.**


## Test Doubles

### FakeGitHub (`tests/fake_github.py`) — Core Mock

**What it is:** An in-memory simulation of the GitHub API, intercepted at the
`subprocess.run` level. Production code calls `subprocess.run(["gh", ...])` and
`make_patched_subprocess(fake_gh)` returns a replacement function that routes
`gh` invocations to `FakeGitHub.handle()` while passing non-gh commands (e.g.,
`git`) through to the real `subprocess.run`.

**Architecture:**
- Dispatch-dict routing: `_DISPATCH` maps top-level gh commands (`label`, `api`,
  `issue`, `run`, `pr`, `release`, `auth`, `--version`) to handler methods.
- In-memory state: `labels` (dict), `milestones` (list), `issues` (list),
  `prs` (list), `reviews` (list), `releases` (list), `runs` (list).
  Auto-incrementing IDs for issues, milestones, PRs.
- Returns `subprocess.CompletedProcess` objects with `returncode`, `stdout`,
  `stderr` — production code sees the same types it would get from real `subprocess.run`.
- `dump_state()` returns a full snapshot dict for test assertions and golden recording.

**Supported commands:**
| Command | Subcommands | Notes |
|---------|------------|-------|
| `label` | `create` | `--color`, `--description`, `--force` |
| `api` | milestones (create/list/close) | `-f` for field params, `-X` for PATCH |
| `issue` | `create`, `list`, `edit`, `close` | Filtering by state, milestone, labels, limit |
| `run` | `list`, `view` | Filtering by branch, status, limit |
| `pr` | `list`, `create`, `review`, `merge` | Review states (APPROVED/CHANGES_REQUESTED/COMMENTED) |
| `release` | `create`, `view` | Positional tag arg, flag parsing |
| `auth` | (status) | Always succeeds |
| `--version` | — | Returns fake version string |

**Safety mechanism — flag enforcement:**
- `_KNOWN_FLAGS` registry maps each handler to its recognized flags.
- `_ACCEPTED_NOOP_FLAGS` lists flags accepted but ignored (`paginate`, `jq`, `notes-file`).
- `_check_flags()` raises `NotImplementedError` if production code sends a flag that
  FakeGitHub doesn't handle — prevents tests from silently passing when new flags
  are added to production code.

**Capabilities:**
- JSON field filtering via `--json` flag (`_filter_json_fields`)
- Duplicate milestone rejection (returns error like real GitHub)
- Issue state transitions (open/closed) with `closedAt` timestamps
- PR review state tracking with `reviewDecision` on PR objects
- PR merge with state/merged/timestamp updates
- Limit support on list operations

**Limitations observed:**
- `api` handler only supports milestones path — any other API path fails loudly
  (intentional, per BH-008 comment).
- No `issue view` support — only create/list/edit/close.
- No `pr view` support — only list/create/review/merge.
- No `release list` or `release delete` support.
- `_handle_label` does its own ad-hoc flag parsing (not using `_parse_flags`/
  `_check_flags`), so the flag enforcement safety net doesn't apply to labels.
- `--jq` is accepted as a no-op, meaning tests won't catch bugs in jq filter
  expressions used by production code.
- No authentication/permissions simulation — `auth` always succeeds.
- `_parse_flags` treats all `--flag` args with a following non-`--` arg as
  key-value pairs. A flag like `--squash` that should be boolean but happens
  to be followed by a non-flag positional arg would incorrectly consume it.

### MockProject (`test_lifecycle.py`, `test_verify_fixes.py`)

Two independent `MockProject` classes create minimal Rust projects in temp
directories. `test_lifecycle.py`'s version creates a real git repo with
`git init` + `git remote add`; `test_verify_fixes.py`'s version creates a
fake `.git/config` file (no real git repo). This means `test_verify_fixes.py`
exercises a different code path for repo detection.

### `make_patched_subprocess()` (`fake_github.py`)

Factory that wraps `subprocess.run` — routes `gh` calls to FakeGitHub while
letting real `subprocess.run` handle everything else (git commands, etc.).
Optional `verbose=True` prints intercepted commands. Tests use this via
`unittest.mock.patch("subprocess.run", make_patched_subprocess(fake_gh))`.

### Golden Recorder/Replayer (`golden_recorder.py`, `golden_replay.py`)

- `GoldenRecorder` captures FakeGitHub state + file tree at named phase
  checkpoints, writes JSON to `tests/golden/recordings/`.
- `GoldenReplayer` loads those snapshots and compares against current state.
- 5 recorded phases: `01-setup-init` through `05-setup-ci`.
- Activated by `GOLDEN_RECORD=1` env var; otherwise replays and asserts match.
- Comparison methods: `assert_labels_match`, `assert_milestones_match`,
  `assert_issues_match`, `assert_files_match`.


## Test Configuration

**No configuration files exist.** No `conftest.py`, `pytest.ini`, `setup.cfg`,
`pyproject.toml`, or `.coveragerc`.

**Module import pattern:** Every test file does manual `sys.path.insert(0, ...)`
to reach the scripts and tests directories. The path manipulation chains are
typically 3-4 `sys.path.insert` calls at module level to reach:
- `scripts/` (for `validate_config.py`, `sprint_init.py`, etc.)
- `tests/` (for `fake_github.py`)
- `skills/<skill>/scripts/` (for skill-specific scripts)

**Makefile targets:**
- `make test` — all tests via `unittest discover`
- `make test-unit` — `test_gh_interactions` only
- `make test-integration` — `test_lifecycle` + `test_hexwise_setup`
- `make test-golden` — `test_golden_run`
- `make test-golden-record` — record new golden snapshots

**CI matrix:** Python 3.10, 3.11, 3.12, 3.13 on ubuntu-latest.

**No coverage tooling** configured anywhere — no `coverage`, no `pytest-cov`,
no `.coveragerc`.


## Observations

1. **Duplicate MockProject classes.** `test_lifecycle.py:49` and
   `test_verify_fixes.py:25` each define their own `MockProject` class with
   nearly identical code. The `test_verify_fixes.py` version uses a fake
   `.git/config` file instead of `git init`, so they exercise different code
   paths for repo detection without this being documented.

2. **`sys.path.insert` sprawl.** All 10 test files and both helpers do manual
   `sys.path.insert(0, ...)` — there is no shared import mechanism. This is
   fragile and order-dependent. A `conftest.py` or package structure would
   eliminate this pattern.

3. **Hybrid unittest-written / pytest-compatible.** The code is pure unittest
   but the `__pycache__` shows pytest 9.0.2 has been used locally. The Makefile
   and CI use `unittest discover`. No pytest features are leveraged (no
   fixtures, markers, parametrize, capsys, tmp_path, etc.).

4. **Label handler bypasses flag safety.** `_handle_label` in `FakeGitHub`
   parses flags with its own ad-hoc loop instead of calling `_parse_flags` +
   `_check_flags`. This means unrecognized flags passed to `gh label create`
   would be silently ignored in tests.

5. **`--jq` is a no-op.** FakeGitHub accepts `--jq` but does nothing with it.
   If production code relies on jq expressions to filter/transform output,
   tests won't catch errors in those expressions.

6. **No negative testing of FakeGitHub itself.** There is a
   `TestFakeGitHubFlagEnforcement` class in `test_gh_interactions.py` that tests
   the flag safety mechanism, but there are no tests verifying that FakeGitHub's
   state machine correctly rejects invalid operations (e.g., merging a
   non-existent PR, closing an already-closed issue).

7. **`os.chdir` in setUp/tearDown.** Several test classes (`test_lifecycle.py`,
   `test_hexwise_setup.py`, `test_golden_run.py`, `test_sync_backlog.py`,
   `test_sprint_teardown.py`) change the working directory in setUp and restore
   it in tearDown. If a test raises before tearDown, `addClassCleanup` is used
   in one place (`test_hexwise_setup.py:69`) but not consistently elsewhere.
   A test failure that prevents tearDown from running could leave the working
   directory changed for subsequent tests.

8. **No coverage tracking.** No `.coveragerc`, no `pytest-cov`, no coverage
   reporting in CI. The Makefile `lint` target does `py_compile` syntax checks
   but nothing measures which lines of production code are exercised by tests.

9. **`make test-unit` is misleading.** It runs only `test_gh_interactions`,
   but `test_sprint_teardown`, `test_sprint_analytics`, and portions of
   `test_pipeline_scripts` are also pure unit tests. The label is a subset
   of the actual unit tests.

10. **Golden recordings are committed to the repo.** The 5 JSON snapshot files
    in `tests/golden/recordings/` are version-controlled. Any change to the
    pipeline output format requires re-recording (`make test-golden-record`),
    which is a manual step that could be forgotten.
