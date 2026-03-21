# Test Infrastructure Recon

## Framework and Runner

- **Framework:** `unittest` (stdlib). No pytest, no third-party test dependencies.
- **Runner:** `python -m unittest discover tests/ -v`
- **No `__init__.py`** in `tests/` — discovery relies on `discover` and module-level `sys.path.insert()` hacks.
- **No conftest.py, no pytest fixtures, no pyproject.toml test config.**

## File Inventory

| File | Test classes | Test methods | What it covers |
|------|-------------|-------------|----------------|
| `test_gh_interactions.py` | 64 | 205 | Mega-file. commit.py, release_gate.py, check_status.py, bootstrap_github.py, populate_issues.py, sync_tracking.py, update_burndown.py, validate_config helpers, FakeGitHub self-tests |
| `test_pipeline_scripts.py` | 14 | 136 | team_voices, traceability, test_coverage, manage_epics, manage_sagas, parse_simple_toml, CI generation, scanner (Python+minimal projects), validate_project negative cases, detect_sprint, extract_story_id, kanban_from_labels |
| `test_release_gate.py` | 11 | 43 | calculate_version, bump_version, validate_gates, gate_tests, gate_build, find_milestone_number, do_release (full pipeline), dry-run integration, find_latest_semver_tag, parse_commits_since |
| `test_sprint_teardown.py` | 9 | 28 | classify_entries, collect_directories, resolve_symlink_target, remove_symlinks, remove_generated, remove_empty_dirs, full teardown flow, main() dry-run + execute |
| `test_hexwise_setup.py` | 2 | 25 | Scanner + ConfigGenerator against hexwise fixture, full pipeline (init -> labels -> milestones -> issues), CI generation, state dump |
| `test_validate_anchors.py` | 5 | 25 | resolve_namespace, find_anchor_defs, find_anchor_refs, check_anchors, fix_missing_anchors |
| `test_verify_fixes.py` | 6 | 19 | Config generation correctness, CI generation, agent frontmatter, evals generic check, load_config error handling, team index cell count warning |
| `test_sync_backlog.py` | 5 | 18 | hash_milestone_files, state file persistence, check_sync debounce/throttle algorithm, do_sync, main() multi-call sequence |
| `test_lifecycle.py` | 1 | 13 | End-to-end lifecycle: init -> bootstrap -> populate -> version calc -> release notes -> TOML write -> monitoring pipeline (sync_tracking -> burndown -> check_status) |
| `test_sprint_analytics.py` | 5 | 11 | Persona extraction, velocity computation, review rounds, workload distribution, report formatting |
| `test_golden_run.py` | 1 | 1 | Single test method that runs all 5 pipeline phases sequentially, recording/replaying golden snapshots |
| **Totals** | **123** | **524** | |

## FakeGitHub Mock (`tests/fake_github.py`)

Central mock for `gh` CLI calls. Intercepts `subprocess.run` when `args[0] == "gh"`.

### What it fakes

- **Labels:** create (with `--force`), stored in `self.labels` dict
- **Milestones:** create via API (`-f title=...`), list, PATCH (close), duplicate rejection
- **Issues:** create (with milestone validation), list (state/milestone/label/json filtering, --limit), edit (add-label, remove-label, milestone), close (sets closedAt)
- **PRs:** create (with all flags), list (state/json/limit filtering), review (approve/request-changes), merge (sets merged/mergedAt/closedAt)
- **Runs:** list (branch/json/limit/status filtering), view (stub)
- **Releases:** create (positional tag + flags), view (stub)
- **API endpoints:** compare (branch divergence), commits (direct push detection), timeline (linked PR lookup via issue timeline events)
- **Auth/version:** stub handlers returning success

### What it does NOT fake

- **`gh` search queries** -- `--search` flag on `pr list` is accepted but NOT filtered against (ignored)
- **`--jq` evaluation** -- accepted as a known flag but NOT executed; tests must pre-shape data to match expected jq output. Documented in comments: timeline (`| first`) and commits (`.[].sha`) rely on pre-shaped fixture data.
- **`--paginate`** -- accepted as no-op; FakeGitHub returns all data in one shot.
- **`--notes-file`** -- accepted as no-op.
- **Issue search** (no `gh search` command handler)
- **PR diff/checks** (no `pr diff`, `pr checks` handlers)
- **Workflow dispatch** or other advanced API endpoints
- **Rate limiting / pagination** behavior
- **Error modes:** no simulation of network timeouts, 403s, 5xx responses (only basic "not found" errors)
- **Repo/org-level operations** (no `repo` command handler)

### Safety mechanism: unknown flag enforcement

`_check_flags()` raises `NotImplementedError` if production code sends a flag FakeGitHub doesn't recognize. Prevents silent green-bar on unhandled functionality. Each handler has a `_KNOWN_FLAGS` entry listing all recognized flags.

### Integration pattern

```python
from fake_github import FakeGitHub, make_patched_subprocess

fake_gh = FakeGitHub()
with patch("subprocess.run", make_patched_subprocess(fake_gh)):
    # production code runs, gh calls intercepted
    ...
# Assert on fake_gh.issues, fake_gh.labels, etc.
```

`make_patched_subprocess()` returns a function that intercepts `subprocess.run` calls where `args[0] == "gh"` and passes the rest to `fake_gh.handle()`. Non-gh subprocess calls fall through to real `subprocess.run`. Optional `verbose=True` prints each intercepted command.

## Golden Recording System

Two helper files support snapshot-based regression testing:

- **`golden_recorder.py` (`GoldenRecorder`):** Captures FakeGitHub state + file tree at named phase checkpoints. Writes JSON snapshots to `tests/golden/recordings/`. Currently 5 recorded phases: `01-setup-init`, `02-setup-labels`, `03-setup-milestones`, `04-setup-issues`, `05-setup-ci`.
- **`golden_replay.py` (`GoldenReplayer`):** Loads golden snapshots and compares against current FakeGitHub/file-tree state. Has `assert_labels_match`, `assert_milestones_match`, `assert_issues_match`, `assert_files_match`.
- **Recording mode:** `GOLDEN_RECORD=1 python tests/test_golden_run.py -v`
- **Replay mode (default):** compares current pipeline output to recorded snapshots; warns if no recordings exist.
- **Used by:** `test_golden_run.py` only (1 test class, 1 test method).

## MockProject Helper

Defined in both `test_lifecycle.py` and `test_verify_fixes.py` (duplicated, not shared). Creates a minimal mock Rust project with:
- `Cargo.toml`, git repo with remote, persona files (alice/bob), milestone file, RULES.md, DEVELOPMENT.md.
- `test_lifecycle.py` version creates a real git repo; `test_verify_fixes.py` version fakes `.git/config`.

## Hexwise Fixture

Rich test fixture at `tests/fixtures/hexwise/`. A realistic Rust project with:
- 3 personas (Rusti Ferris, Palette Jones, Checker Macready) + deep docs (sagas, epics, PRDs, test plans, story maps)
- 3 milestones, 17 stories across epics
- Used by: `test_hexwise_setup.py`, `test_golden_run.py`, `test_pipeline_scripts.py`

## Import Patterns

All test files use the same pattern:
```python
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "skills" / "<skill>" / "scripts"))
```
No proper package structure. Imports are side-effectful (`sys.path.insert` at module level).

## Mocking Patterns

1. **FakeGitHub + `make_patched_subprocess`:** Patches `subprocess.run` globally. Used in integration/pipeline tests.
2. **`@patch("module.gh_json")` / `@patch("module.gh")`:** Patches the shared helper functions directly. Used in unit tests.
3. **`@patch("module.subprocess.run")`:** Patches subprocess at the module level. Used for commit.py tests.
4. **`@patch("builtins.input")`:** Used for interactive teardown tests.
5. **`@patch("sys.argv")`:** Used for main() function tests.
6. **`tempfile.mkdtemp()` / `tempfile.TemporaryDirectory()`:** All file-based tests create temp directories. Cleanup in `tearDown()` or context manager.

## Unusual Patterns and Concerns

1. **`test_gh_interactions.py` is 2100+ lines with 64 test classes.** A mega-file that mixes unit tests for 10+ different scripts. Hard to navigate and maintain.
2. **MockProject is duplicated** in `test_lifecycle.py` and `test_verify_fixes.py` with slight differences (real git vs fake .git/config).
3. **`os.chdir()` in setUp/tearDown:** Multiple test files change the working directory, which can cause cascading failures if a test errors before tearDown runs. Some use `addCleanup()` (hexwise_setup), some don't.
4. **No test isolation for module-level imports:** `sys.path.insert(0, ...)` at module scope means import ordering matters and could cause cross-contamination between test modules.
5. **Golden recordings are checked in** at `tests/golden/recordings/`. Changes to production code may silently produce different output without failing tests (golden replay only warns if recordings are absent, doesn't fail).
6. **test_golden_run.py has only 1 test method** but runs an entire 5-phase pipeline sequentially within it. If an early phase fails, all subsequent phases are untested.
7. **No test markers, tags, or categories.** Cannot selectively run "fast" vs "slow" tests. Every test creates temp dirs and/or git repos.
8. **`setUpClass` + `os.chdir`** in `test_hexwise_setup.py` — shared class-level setup with `addClassCleanup` for cwd restoration. If class setup fails, cleanup may not restore cwd.
