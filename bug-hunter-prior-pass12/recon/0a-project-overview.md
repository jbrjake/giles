# Recon 0a: Project Overview

**Date:** 2026-03-15
**Subject:** Adversarial recon of the giles Claude Code plugin

---

## What This Project Does

Giles (v0.4.0, MIT license, by Jon Rubin / jbrjake) is a Claude Code plugin that simulates a full agile development team. It manages sprint ceremonies (kickoff, demo, retro), creates and tracks GitHub issues, dispatches subagent implementers and reviewers who work in-character as fictional personas, monitors CI/PR status, and handles milestone releases. The scrum master persona is named Giles -- a librarian/butler character.

The tagline is "agile agentic development that takes it too far," which is accurate. The project is ambitious: it is an LLM prompt orchestration layer dressed up as an agile process tool, where the primary "runtime" is the Claude Code agent reading markdown instructions and executing Python scripts.

**Key insight for anyone inheriting this:** The SKILL.md files are not code. They are prompt instructions for a Claude Code agent. The Python scripts are the actual logic. The SKILL.md files tell the agent what scripts to run and how to interpret their output. This is a critical distinction -- bugs in SKILL.md are prompt bugs, not code bugs, and they manifest as behavioral issues in an LLM conversation, not as stack traces.

---

## File Organization

### Top-level layout

```
.claude-plugin/plugin.json   -- Plugin manifest (5 skills registered)
scripts/                     -- 12 shared Python scripts (stdlib-only)
skills/                      -- 5 skill directories, each with SKILL.md entry point
  sprint-setup/              -- One-time bootstrap (labels, milestones, issues, CI)
  sprint-run/                -- Sprint execution (ceremonies + story dispatch)
  sprint-monitor/            -- Continuous CI/PR/burndown monitoring (for /loop)
  sprint-release/            -- Milestone release management
  sprint-teardown/           -- Safe removal of sprint-config/
references/skeletons/        -- 19 .tmpl files for scaffolding sprint-config/
tests/                       -- 17 Python test files (~11,400 lines)
evals/evals.json             -- 6 evaluation scenarios
```

### Script inventory (19 Python scripts, ~7,500 lines)

**Shared scripts (scripts/):**

| Script | Lines | Purpose |
|--------|-------|---------|
| validate_config.py | 886 | God object. TOML parser, config validation, all shared helpers (gh, gh_json, extract_sp, kanban_from_labels, etc.) |
| sprint_init.py | 976 | Project auto-detection + sprint-config/ scaffolding |
| sprint_teardown.py | 476 | Safe removal of sprint-config/ |
| sync_backlog.py | 245 | Backlog auto-sync with debounce/throttle |
| sprint_analytics.py | ~300 | Sprint metrics (velocity, review rounds, workload) |
| team_voices.py | ~100 | Extract persona commentary from saga/epic files |
| traceability.py | ~200 | Bidirectional story/PRD/test mapping with gap detection |
| test_coverage.py | ~150 | Compare planned test cases vs actual test files |
| manage_epics.py | ~200 | Epic CRUD: add, remove, reorder stories |
| manage_sagas.py | ~200 | Saga management: allocation, index, voices |
| commit.py | ~150 | Conventional commit enforcement + atomicity check |
| validate_anchors.py | ~300 | Validate section-anchor references in docs |

**Skill-level scripts (7 scripts, 4 skills):**

| Script | Skill | Lines | Purpose |
|--------|-------|-------|---------|
| bootstrap_github.py | sprint-setup | 302 | Create GitHub labels/milestones |
| populate_issues.py | sprint-setup | 456 | Parse milestone markdown -> GitHub issues |
| setup_ci.py | sprint-setup | ~200 | Generate .github/workflows/ci.yml |
| sync_tracking.py | sprint-run | ~300 | Reconcile local tracking with GitHub state |
| update_burndown.py | sprint-run | ~200 | Update burndown from GitHub milestones |
| check_status.py | sprint-monitor | 441 | CI + PR + milestone + drift checks |
| release_gate.py | sprint-release | 694 | Release gates, versioning, notes, publishing |

### Test infrastructure

The test suite is substantial (~11,400 lines across 17 files). Key components:

- `fake_github.py` (904 lines) -- In-memory GitHub simulator that intercepts `subprocess.run(["gh", ...])` calls. Implements labels, milestones, issues, PRs, releases, reviews, runs, timeline events, comparisons, and commits. Supports `--jq` filtering when the `jq` Python package is installed.
- `test_gh_interactions.py` (3,078 lines) -- The big one. Tests individual script behavior against FakeGitHub.
- `test_pipeline_scripts.py` (1,511 lines) -- Script pipeline integration tests.
- `test_release_gate.py` (1,318 lines) -- Release gate testing.
- `test_verify_fixes.py` (963 lines) -- Regression tests for 20+ named bug fixes (BH-001 through BH-025+).
- `mock_project.py` -- Creates temporary filesystem fixtures (sprint-config/ with project.toml, team, backlog).
- `golden_recorder.py` / `golden_replay.py` -- Record/replay testing for golden snapshot tests.

Dev dependencies in `requirements-dev.txt`: pytest>=9.0, jq>=1.11, hypothesis>=6.

---

## External Dependencies / Tools

**Hard runtime requirements:**
- Python 3.10+ (stdlib only -- zero pip install for users)
- `gh` CLI (GitHub CLI) -- must be installed and authenticated
- `git` -- repo operations, branching, tagging
- Claude Code with "superpowers" plugin -- for subagent dispatch

**All GitHub interaction goes through two functions:** `validate_config.gh()` and `validate_config.gh_json()`, both of which call `subprocess.run(["gh", ...])`. No `requests`, no `urllib`, no HTTP clients.

**Test-only:** pytest, hypothesis, jq (Python package). All declared in requirements-dev.txt.

---

## Architecture Patterns

### 1. The config system

Everything flows from `sprint-config/project.toml`, parsed by a hand-rolled TOML parser (`parse_simple_toml()` in validate_config.py). The parser supports the subset of TOML the project uses: sections, strings, ints, bools, arrays (including multiline). It does not support nested tables, inline tables, dates, or multiline strings.

Config is loaded via `load_config()`, which validates the directory structure, parses the TOML, and resolves all `[paths]` values relative to the project root.

The config directory (`sprint-config/`) is scaffolded by `sprint_init.py`, which auto-detects project characteristics (language, repo, CI commands, persona files, backlog files, deep docs) and generates symlinks to existing files plus skeleton templates for anything missing.

### 2. The import chain

All skill-level scripts (in `skills/*/scripts/`) import from the shared `scripts/` directory using `sys.path.insert(0, ...)`:

```python
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent / "scripts"))
from validate_config import load_config, ConfigError, gh, gh_json, ...
```

This hardcodes that skill scripts are exactly 4 directory levels below the plugin root. The pattern appears in every skill script.

### 3. GitHub CLI wrapping

All GitHub interaction goes through `gh()` and `gh_json()` in validate_config.py. `gh()` runs a subprocess and returns stdout. `gh_json()` parses the JSON output, with special handling for `gh api --paginate` which concatenates raw JSON arrays (`[...][...]`).

The project uses `gh`'s `{owner}/{repo}` template variables in API paths (e.g., `repos/{owner}/{repo}/milestones`), which `gh` expands from the git remote configuration. This is clever but means the scripts must always run in a directory with a git remote.

### 4. Idempotent operations

Bootstrap scripts (labels, milestones, issues) skip resources that already exist. This is enforced by checking GitHub state before creating. The pattern is: fetch existing, check for matches, skip duplicates.

### 5. State persistence

- `SPRINT-STATUS.md` -- markdown file in the sprints directory, tracks current sprint, phase, velocity
- `.sync-state.json` -- JSON file in sprint-config/, tracks backlog sync state (hashes, timestamps)
- `.sprint-init-manifest.json` -- JSON file in sprint-config/, records what sprint-init created (for teardown)
- GitHub itself -- issues, PRs, milestones, labels are the source of truth

### 6. The skill/agent/reference split

```
SKILL.md           -- High-level prompt instructions for the Claude Code agent
  references/      -- Detailed protocol documents (kanban states, ceremony scripts)
  agents/          -- Subagent prompt templates (implementer.md, reviewer.md)
  scripts/         -- Python automation
```

The SKILL.md tells the agent what to do. The references give it detailed instructions for specific tasks. The agent templates define how subagents should behave. The scripts handle the mechanical work (GitHub API calls, file parsing, state tracking).

---

## What Looks Well-Designed

1. **The FakeGitHub test double.** This is the most impressive piece of engineering in the project. It intercepts subprocess calls at the `subprocess.run` level, routes `gh` commands to an in-memory state store, supports flag parsing, validates unknown flags in strict mode, and optionally evaluates `--jq` filters using the real jq package. It is 904 lines of careful simulation with explicit documentation of what is and isn't implemented. The `_KNOWN_FLAGS` / `_IMPLEMENTED_FLAGS` / strict-mode warning system is particularly thoughtful -- it prevents tests from silently ignoring query parameters that should affect results.

2. **The symlink-based config system.** Using symlinks from sprint-config/ to existing project files is a clean separation. The original files are never modified. Teardown is safe because removing a symlink doesn't touch the target. The manifest file records what was created. The classification system (symlink / generated / unknown) in sprint_teardown.py handles edge cases well.

3. **The config validation system.** `validate_project()` checks for required files, parses TOML, validates required sections and keys, checks for minimum persona count, verifies persona files exist, and checks for milestone files. It returns structured errors rather than crashing. `load_config()` wraps this with path resolution. Every script calls this before doing anything else.

4. **The backlog sync debounce/throttle.** `sync_backlog.py` implements a proper debounce (wait for file hashes to stabilize across invocations) and throttle (minimum 10 minutes between syncs). The state machine is clean: no_changes -> debouncing -> sync, with throttle as a gate. The TOCTOU window is documented and mitigated.

5. **The release gate system.** Five sequential gates (stories, CI, PRs, tests, build), each returning (passed, detail). First failure stops. Version calculation from conventional commits. Rollback on failure at any step (undo tag, undo commit). Dry-run mode. This is solid release engineering.

6. **Bug-fix traceability.** Bug fixes are tagged with identifiers (BH-001, BH-002, etc.) in code comments, and there are dedicated regression tests for each. The test_verify_fixes.py file contains 963 lines of regression tests. This level of traceability is uncommon and valuable.

---

## What Raises Concerns (Adversarial Notes)

### Architectural Concerns

1. **validate_config.py is a god object.** At 886 lines, it contains the TOML parser, config validation, GitHub CLI wrappers, story point extraction, kanban state management, milestone lookup, sprint detection, and various helpers. Every script in the project depends on it. Any change to this file has blast radius across the entire codebase. It should be split into at least 3 modules: toml_parser, config_validation, github_helpers.

2. **The sys.path.insert import chain is brittle.** Every skill script hardcodes `Path(__file__).resolve().parent.parent.parent.parent / "scripts"` to find validate_config.py. This breaks silently if anyone reorganizes the directory structure. There is no package, no setup.py, no pyproject.toml for the plugin's own code. The project could use a simple `__init__.py` or a pyproject.toml with `[tool.setuptools.packages.find]` to make imports work properly. The fact that `sync_backlog.py` also inserts a *second* path (`skills/sprint-setup/scripts`) to import bootstrap_github and populate_issues makes this even more fragile.

3. **The custom TOML parser is a maintenance liability.** It is ~230 lines of hand-rolled parsing that handles a subset of TOML. Python 3.11 shipped `tomllib` in October 2022. The project targets 3.10, but 3.10 reaches end-of-life in October 2026. The custom parser has already required bug fixes (BH-001, BH-002 for quote-aware bracket detection and inline comment stripping). Each new TOML feature the project needs will require more parser work. The `_parse_value()` fallback of returning unquoted text as a raw string is particularly suspicious -- it silently accepts malformed TOML.

4. **No proper package structure.** The project has scripts/ and skills/ at the top level, but no `__init__.py` files, no package installation, no entry points. Test discovery works via `unittest discover` with fragile path manipulation. The Makefile lint target individually `py_compile`s each script file. This is fine for a small project but does not scale well.

5. **Two different test runners.** The Makefile uses `unittest discover`, but requirements-dev.txt includes pytest. The .pytest_cache directory exists. Some tests may only work with one runner. The Makefile test targets reference specific test modules by name (`tests.test_gh_interactions`).

### Code-Level Concerns

6. **shell=True in release_gate.py.** `gate_tests()` and `gate_build()` run user-configured commands with `shell=True`. The commands come from project.toml, which is user-controlled, so this is not a security issue per se -- but it is a code smell and makes error handling harder. If a user puts `rm -rf /` in their build_command, the plugin will happily execute it.

7. **Regex-based markdown parsing everywhere.** Every script that touches markdown has its own regex patterns. `populate_issues.py` has `_DEFAULT_ROW_RE`, `_SPRINT_HEADER_RE`, `_DETAIL_BLOCK_RE`, `_META_ROW_RE`. `bootstrap_github.py` has patterns for saga parsing. `sprint_init.py` has patterns for persona detection, backlog detection, story ID detection. `extract_sp()` in validate_config.py has 5 different regex patterns for finding story points. None of these share a common markdown table parser. If the markdown format changes slightly, multiple scripts break in different ways.

8. **The 500-item limit pattern.** Many GitHub queries use `--limit 500`. `warn_if_at_limit()` prints a stderr warning but does not paginate. For projects with more than 500 issues, PRs, or labels, data will be silently truncated. The `gh_json()` function handles `--paginate` for API calls, but the `gh issue list` and `gh pr list` calls do not use pagination. This is a time bomb for any serious project.

9. **Pagination inconsistency.** `gh_json()` has special handling for concatenated JSON arrays from `gh api --paginate`, but many callers use `gh issue list` / `gh pr list` which use `--limit` instead of `--paginate`. There is no equivalent pagination handling for these commands.

10. **Missing error propagation in check_status.py.** The `main()` function wraps each check in a try/except that catches RuntimeError but lets other exceptions crash the monitor. The SKILL.md says "Never crash. Always exit cleanly so /loop can call again on schedule." The code does not fully deliver on this promise -- a KeyError, TypeError, or AttributeError in any check function would crash the entire monitor.

11. **Path resolution inconsistency.** `load_config()` resolves `[paths]` values relative to the project root (parent of config_dir). But some scripts also construct paths manually. `check_status.py` uses `get_sprints_dir(config)` which returns a Path from the resolved config. `sprint_init.py` uses its own path logic. `sprint_teardown.py` looks for `sprint-config/` in the current directory. If the working directory is not the project root, things may break.

12. **`__pycache__` directories committed to repo.** The `.gitignore` has `__pycache__/` but the file listing shows `__pycache__` directories under both `scripts/` and `skills/*/scripts/`. These contain `.cpython-310.pyc` and `.cpython-312.pyc` files. They appear to be local artifacts that are not tracked by git (the .gitignore covers them), but their presence indicates the project has been run with at least two different Python versions (3.10 and 3.12).

13. **Several untracked directories.** The git status shows `.hypothesis/`, `audit/`, `bug-hunter-prior-*`, `IDEAS.md`, `IDEAS-accepted.md`, `BUG-HUNTER-SUMMARY.md`, and `recon/` as untracked. This is a lot of working debris. Some of it (IDEAS-accepted.md, the bug-hunter archives) looks like it should either be committed or cleaned up.

14. **`_PERSONA_COLORS` in bootstrap_github.py.** Hardcoded list of 20 hex colors for persona labels. If a project has more than 20 personas, colors wrap with modulo. Not a real concern for practical use (20 personas is plenty), but it is a magic constant with no validation.

### Testing Concerns

15. **FakeGitHub fidelity gap.** The FakeGitHub test double is impressive, but it is a ~900-line reimplementation of GitHub's API behavior. Every behavior difference between FakeGitHub and real GitHub is a potential false positive in tests. The strict mode helps, but the real risk is in *what FakeGitHub doesn't simulate at all*: rate limiting, eventual consistency, network errors, partial responses, authentication failures with meaningful error messages.

16. **Scripts without dedicated test files.** `manage_epics.py`, `manage_sagas.py`, `team_voices.py`, `traceability.py`, `test_coverage.py`, `commit.py`, `setup_ci.py`, `sync_tracking.py`, `update_burndown.py` have no obviously dedicated test files. Some may be tested indirectly through integration tests, but this is hard to verify.

17. **Golden snapshot tests are fragile.** `test_golden_run.py` (217 lines) replays recorded responses. If the scripts change behavior, the golden snapshots need to be re-recorded with `GOLDEN_RECORD=1`. There is no CI enforcement of golden test freshness -- a stale snapshot will pass if the replay format still matches, even if the underlying behavior has changed.

18. **Hypothesis tests.** `test_property_parsing.py` (458 lines) uses property-based testing for regex/parsing hotspots. This is good. But the hypothesis settings are not tuned (no `@settings(max_examples=...)` visible in the filename), which means default settings may not find edge cases in CI.

### Documentation Concerns

19. **CLAUDE.md and CHEATSHEET.md with line-number references.** CLAUDE.md references specific function names with `§`-anchored identifiers (e.g., `§validate_config.parse_simple_toml`). CHEATSHEET.md contains detailed line-number indices. These are inherently fragile -- any code change shifts line numbers, requiring manual updates. The `validate_anchors.py` script mitigates this by checking anchor references, but it runs as part of `make lint`, not as a pre-commit hook.

20. **Massive CLAUDE.md.** At 142 lines with dense tables, CLAUDE.md is doing a lot of work. It is both the architecture guide and the function reference. For a Claude Code plugin, this is the primary "onboarding document" for the agent, so density is acceptable -- but it means any agent conversation starts by consuming ~5,000 tokens of context just from CLAUDE.md.

---

## Summary Assessment

This is a well-engineered hobby/side project that has received significant quality attention (11+ bug-hunting passes, property-based testing, a serious test double, regression tests with traceability). The architecture is sound for what it is: a prompt-orchestration layer with Python automation underneath.

The main risks for someone inheriting this code are:

1. **The god object** (validate_config.py) -- too much in one file, too many reasons to change it.
2. **The import hack** (sys.path.insert) -- fragile, undiscoverable, breaks if anything moves.
3. **Regex-based markdown parsing** -- no shared parser, each script rolls its own, formatting changes break multiple scripts in different ways.
4. **The 500-item limit** -- queries will silently return incomplete data for projects above this threshold.
5. **The custom TOML parser** -- a maintenance burden that will grow as TOML needs grow, and Python 3.10 EOL approaches.

The project is not production-critical infrastructure -- it is a creative tool for agentic development workflows. The bugs that matter most are the ones that cause the agent to do the wrong thing silently (bad parsing, incomplete GitHub data, stale state) rather than the ones that crash loudly.
