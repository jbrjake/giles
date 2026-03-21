# Project Overview -- Pass 9 Adversarial Recon

Generated: 2026-03-15 (pass 9, fresh eyes)

---

## Identity

- **Name:** giles
- **Version:** 0.4.0 (per `.claude-plugin/plugin.json`)
- **Author:** Jon Rubin (jb.rubin@gmail.com)
- **Repo:** https://github.com/jbrjake/giles
- **License:** MIT
- **Tagline:** "A plugin for agile agentic coding that takes it too far"
- **Platform:** Claude Code plugin (`.claude-plugin/plugin.json` manifest with 5 skills)
- **Language:** Python 3.10+ (stdlib only, no pip dependencies)
- **CI:** GitHub Actions, matrix testing Python 3.10-3.13, lint + test

## What It Claims To Do

Giles is a Claude Code plugin that runs agile sprints with fictional team personas. It orchestrates:
1. GitHub issues, PRs, CI, kanban tracking
2. Sprint ceremonies (kickoff, demo, retro) facilitated by a built-in "Giles" scrum master persona
3. Persona-based implementation and code review via subagent dispatch
4. Release management with gate validation, semver tagging, release notes
5. Continuous monitoring via `/loop` integration

The lifecycle is: `sprint-setup` -> `sprint-run` (repeating) -> `sprint-release` -> `sprint-teardown`, with `sprint-monitor` running alongside via `/loop 5m`.

---

## Codebase Structure

### File Counts (from directory listings)

| Category | Files | Approx. Size (bytes from `ls -la`) |
|----------|-------|------|
| Core scripts (`scripts/`) | 12 .py files | ~164 KB |
| Skill scripts (`skills/*/scripts/`) | 6 .py files | ~83 KB |
| Skill entry points (`skills/*/SKILL.md`) | 5 files | ~39 KB |
| Agent templates (`skills/sprint-run/agents/`) | 2 .md files | ~15 KB |
| Reference docs (`skills/*/references/`) | 12 .md files | ~50 KB |
| Skeleton templates (`references/skeletons/`) | 19 .tmpl files | ~22 KB |
| Test files (`tests/`) | 11 test_*.py + 3 infra files | ~340 KB |
| Test fixtures (`tests/fixtures/hexwise/`) | ~30 files | Rust project fixture |
| Golden recordings (`tests/golden/recordings/`) | 6 JSON files | ~277 KB |
| Documentation (root) | CLAUDE.md, CHEATSHEET.md, README.md, etc. | ~105 KB |
| Evals | 1 JSON file | ~2 KB |
| Plugin manifest | 1 JSON file | ~0.6 KB |

### Prior LOC counts (from earlier recon, still accurate per file sizes)

| Script | LOC | Purpose |
|--------|-----|---------|
| `scripts/validate_config.py` | ~806 | Config validation, TOML parser, shared helpers |
| `scripts/sprint_init.py` | ~971 | Auto-detect project, generate sprint-config/ |
| `scripts/sprint_teardown.py` | ~473 | Safe removal of sprint-config/ |
| `scripts/manage_epics.py` | ~404 | Epic CRUD: add, remove, reorder stories |
| `scripts/validate_anchors.py` | ~336 | Validate section-anchor references in docs |
| `scripts/manage_sagas.py` | ~297 | Saga management |
| `scripts/sprint_analytics.py` | ~275 | Sprint metrics |
| `scripts/sync_backlog.py` | ~246 | Backlog auto-sync |
| `scripts/traceability.py` | ~222 | Story/PRD/test mapping |
| `scripts/test_coverage.py` | ~197 | Planned vs actual test coverage |
| `scripts/commit.py` | ~156 | Commit enforcement |
| `scripts/team_voices.py` | ~106 | Persona voice extraction |
| `skills/sprint-release/scripts/release_gate.py` | ~679 | Release gates, versioning |
| `skills/sprint-setup/scripts/populate_issues.py` | ~445 | Milestone -> GitHub issues |
| `skills/sprint-monitor/scripts/check_status.py` | ~434 | CI + PR + milestone check |
| `skills/sprint-setup/scripts/setup_ci.py` | ~384 | Generate CI workflow |
| `skills/sprint-run/scripts/sync_tracking.py` | ~358 | Local <-> GitHub reconciliation |
| `skills/sprint-setup/scripts/bootstrap_github.py` | ~301 | Create labels/milestones |
| `skills/sprint-run/scripts/update_burndown.py` | ~229 | Burndown from GitHub |
| **Total scripts** | **~7,319** | |

Test files total approximately 8,671 LOC across 14 files.

---

## Skills -- What Each Claims To Do

### sprint-setup (SKILL.md: 101 lines)
- Phase 0: Check/create sprint-config/ via `sprint_init.py`
- Step 1: Verify prerequisites (gh CLI, auth, superpowers, git remote, toolchain, Python 3.10+)
- Step 2: Bootstrap GitHub (labels, milestones, issues, CI workflow)
- **Scripts:** `bootstrap_github.py`, `populate_issues.py`, `setup_ci.py`
- **References:** `prerequisites-checklist.md`, `github-conventions.md`, `ci-workflow-template.md`

### sprint-run (SKILL.md: 146 lines)
- Phase detection from SPRINT-STATUS.md
- Phase 1: Kickoff ceremony (interactive, Giles facilitates)
- Phase 2: Story execution (autonomous per-story, interactive at gates)
- Mid-sprint check-in
- Context assembly for subagent dispatch (PRD, test plan, saga, insights injection)
- Phase 3: Demo ceremony (interactive)
- Phase 4: Retro ceremony (interactive)
- **Scripts:** `sync_tracking.py`, `update_burndown.py`
- **Agents:** `implementer.md`, `reviewer.md`
- **References:** 8 reference docs (kanban, personas, ceremonies, tracking, context recovery, story execution)

### sprint-monitor (SKILL.md: 326 lines)
- Step 0: Backlog sync (debounce/throttle)
- Step 1: CI status check
- Step 1.5: Drift detection (branch divergence, direct pushes)
- Step 2: PR checks (stale, needs review, approved, conflicts)
- Step 2.5: Mid-sprint check-in (threshold-triggered)
- Step 3: Sprint status (milestone progress)
- Step 4: Report (one-line summary)
- Rate limiting and deduplication
- **Scripts:** `check_status.py`

### sprint-release (SKILL.md: 284 lines)
- Step 1: Gate validation (stories, CI, PRs, tests, build)
- Step 2: Tag and release (semver from conventional commits)
- Step 3: Build release artifacts
- Step 4: Create GitHub Release (notes, artifacts)
- Step 5: Post-release (close milestone, update tracking)
- Rollback procedure
- **Scripts:** `release_gate.py`
- **References:** `release-checklist.md`

### sprint-teardown (SKILL.md: 212 lines)
- Safety principles (never delete original files, symlinks safe, generated need confirmation)
- Step 1: Stop active /loop instances
- Step 2: Locate sprint-config/
- Step 3: Dry run (classify: symlink/generated/unknown)
- Step 4: Execute teardown (remove symlinks, prompt for generated, clean empty dirs)
- Step 5: Report + GitHub cleanup hints
- **Scripts:** Uses `scripts/sprint_teardown.py` (no own scripts directory)

---

## Architecture Claims vs Reality

### CLAIM: "stdlib only, no external deps"
**REALITY: TRUE.** All Python scripts import only from stdlib. No `requirements.txt`, no `setup.py`, no pip dependencies. The `.venv` is only used for running tests via `unittest`. The Makefile confirms: `python3 -m venv` with no pip install step.

### CLAIM: "Custom TOML parser"
**REALITY: TRUE, and it's been through multiple bug-fix passes.** `parse_simple_toml()` in `validate_config.py` handles strings, ints, bools, arrays (including multiline), sections, and inline comments with quote-aware stripping. The ADVERSARIAL-REVIEW.md documents at least 3 critical bugs that were found and fixed in the TOML parser (BH-001 through BH-003). The parser now includes `_strip_inline_comment()`, `_has_closing_bracket()`, and `_count_trailing_backslashes()` -- all added as bug fixes.

### CLAIM: "19 skeleton templates"
**REALITY: TRUE.** Exactly 19 `.tmpl` files confirmed in `references/skeletons/`. The CLAUDE.md claim of 9 core + 10 deep-doc matches the actual file list.

### CLAIM: "5 skills"
**REALITY: TRUE.** `plugin.json` lists exactly 5 SKILL.md paths. All 5 files exist.

### CLAIM: "GitHub as source of truth"
**REALITY: PARTIALLY TRUE.** `sync_tracking.py` does treat GitHub as authoritative. But the system has a second, conflicting truth source: the local markdown files in `backlog/milestones/` that `populate_issues.py` reads. `sync_backlog.py` reconciles by pushing local changes TO GitHub (local -> GitHub direction), while `sync_tracking.py` pulls state FROM GitHub (GitHub -> local direction). This creates a bidirectional sync where "source of truth" is actually "source of truth for issue state" (GitHub) but "source of truth for backlog content" (local files).

### CLAIM: "Symlink-based config"
**REALITY: TRUE.** `sprint_init.py` creates symlinks. `sprint_teardown.py` classifies entries and removes symlinks without touching targets. Exception: `giles.md` is copied (confirmed in code).

### CLAIM: "Idempotent scripts"
**REALITY: MOSTLY TRUE.** Bootstrap scripts check for existing labels/milestones/issues before creating. However, idempotency depends on correct state detection -- if the detection logic has bugs (e.g., wrong label name matching, wrong milestone title comparison), re-runs could create duplicates.

### CLAIM: "Scripts import chain -- all skill scripts do sys.path.insert 4 directories up"
**REALITY: TRUE for skill scripts.** Scripts in `skills/*/scripts/` navigate up 4 levels to reach the root `scripts/` directory. Scripts in the root `scripts/` directory add their own directory to sys.path. `sync_backlog.py` is the unique case -- it also adds `skills/sprint-setup/scripts/` to import `populate_issues`.

### CLAIM: "sprint-monitor designed for /loop"
**REALITY: PROMPT-ONLY.** There is no code that implements `/loop` integration. The SKILL.md just instructs the Claude agent to be called via `/loop 5m sprint-monitor`. The `/loop` command is a Claude Code platform feature, not something the plugin implements.

### CLAIM: "Superpowers plugin required"
**REALITY: HARD DEPENDENCY, EXTERNAL.** The `sprint-run` skill and its agent templates reference `superpowers:test-driven-development`, `superpowers:verification-before-completion`, and `superpowers:dispatching-parallel-agents`. These are assumed to exist as another Claude Code plugin. If superpowers is not installed, the TDD workflow, verification step, and parallel dispatch all fail. Prerequisites checklist checks for it, but the check is just a `find` command looking for a directory name.

---

## What the Tests Actually Cover

### Test Infrastructure
- `fake_github.py` (~715 LOC) -- mock GitHub CLI server that intercepts `gh` calls
- `golden_recorder.py` / `golden_replay.py` -- record/replay infrastructure for golden tests
- Tests run via `make test` using `python -m unittest discover`

### Test Modules (11 files, ~8,671 LOC)
| Module | Approximate LOC | What It Tests |
|--------|----------------|---------------|
| `test_gh_interactions.py` | ~2,091 | GitHub CLI interactions via FakeGitHub |
| `test_pipeline_scripts.py` | ~1,443 | Pipeline scripts (init, teardown, analytics, etc.) |
| `test_release_gate.py` | ~1,148 | Release gate logic |
| `test_lifecycle.py` | ~593 | End-to-end sprint lifecycle |
| `test_sprint_teardown.py` | ~525 | Teardown logic |
| `test_hexwise_setup.py` | ~447 | Setup with the hexwise fixture project |
| `test_verify_fixes.py` | ~394 | Regression tests for prior bug fixes |
| `test_sync_backlog.py` | ~296 | Backlog sync logic |
| `test_validate_anchors.py` | ~285 | Anchor validation |
| `test_sprint_analytics.py` | ~249 | Sprint analytics |
| `test_golden_run.py` | ~208 | Golden test replay |

### Fixture Data
- `tests/fixtures/hexwise/` -- A complete mock Rust project with team personas, milestones, epics, sagas, PRDs, test plans, and story maps. This is the canonical test project.

---

## Red Flags and Suspicious Items

### RF-01: `definition-of-done.md` not validated
CLAUDE.md and the config structure docs list `definition-of-done.md` as part of `sprint-config/`. `sprint_init.py` generates it (line 787-788). But `validate_config.py`'s `_REQUIRED_FILES` list does NOT include it. The retro ceremony (`ceremony-retro.md` line 152) tells Giles to read it. If the file is missing, the retro will silently fail to review the DoD. Either the file should be in `_REQUIRED_FILES` or the ceremony instructions should handle the missing-file case.

### RF-02: Evals are stale/incomplete
`evals/evals.json` contains 6 evaluation scenarios but uses `"skill_name": "sprint-process"` -- a name that does not match any actual skill name. The eval expectations are high-level ("Checks for gh CLI installation") with no automated verification mechanism. The evals appear to be aspirational documentation rather than executable tests.

### RF-03: No end-to-end test of the skill SKILL.md instructions
All tests exercise the Python scripts directly. No test verifies that the SKILL.md instructions, when followed by Claude, produce correct results. The SKILL.md files are essentially untested prompts. If a SKILL.md instruction references a wrong script path, wrong flag, or wrong output format, tests won't catch it.

### RF-04: sprint-monitor SKILL.md describes 7 steps but then says "check_status.py covers Steps 0-3"
Lines 246-248 of sprint-monitor SKILL.md say: "Running check_status.py covers Steps 0-3, so the agent should NOT also run individual gh commands for the same checks." But Step 0 is backlog sync (handled by `sync_backlog.py`), and `check_status.py` does NOT handle backlog sync. The instruction is misleading -- `check_status.py` covers Steps 1, 1.5, 2, and 3, not Step 0.

### RF-05: CHEATSHEET.md anchor references may be stale
CHEATSHEET.md provides line-number references, but these are maintained manually. After 8 passes of bug fixes, the line numbers have likely drifted. The `validate_anchors.py` script validates section-anchor references (the `§` system) but not line numbers. CLAUDE.md even warns: "see CHEATSHEET.md" but does not verify its accuracy.

### RF-06: `sprint-teardown` skill has no scripts directory
All other skills have a `scripts/` subdirectory. `sprint-teardown` uses `scripts/sprint_teardown.py` from the root scripts directory. This is a minor inconsistency but could confuse the sys.path logic if someone tries to follow the pattern.

### RF-07: `.pyc` files checked into working tree
Multiple `__pycache__/` directories with `.pyc` files exist in the working tree (visible in `ls -la` output for `skills/*/scripts/__pycache__/` and `scripts/__pycache__/`). The `.gitignore` excludes `__pycache__/` and `*.pyc`, so they shouldn't be in git, but their presence suggests developers may not be cleaning build artifacts. Two Python versions' bytecode exist (3.10 and 3.12), suggesting testing on multiple versions.

### RF-08: Multiple prior bug-hunting artifacts in working tree
Untracked directories: `audit/`, `bug-hunter-prior-2026-03-14/`, `bug-hunter-prior-pass5/`, `bug-hunter-prior-pass6/`, `bug-hunter-prior-pass7/`, `bug-hunter-prior-pass8/`, `recon/`. This project has been through extensive automated bug hunting. Prior passes found 30+ bugs including 3 CRITICAL. The question is: are there still patterns of bugs that the prior passes' approach would not have caught?

### RF-09: `test_verify_fixes.py` -- regression tests for PRIOR bugs
This file (394 LOC) contains regression tests specifically for bugs found in prior passes. Its existence confirms that prior bug fixes were not always accompanied by tests when initially fixed -- the regression tests were added after the fact. This is a healthy pattern but worth auditing for coverage gaps.

### RF-10: Two-truth problem in backlog management
`sync_backlog.py` pushes local milestone file changes to GitHub. `sync_tracking.py` pulls GitHub issue state to local tracking files. `populate_issues.py` creates GitHub issues from local milestone files. But there is no mechanism to pull CHANGES made on GitHub (e.g., someone closing an issue, changing a label) back INTO the local milestone files. The milestone files are write-only from the local perspective. If someone edits issue descriptions on GitHub, the local backlog files become stale.

### RF-11: The `gh_json()` return type is `list | dict`
The `gh_json()` function returns `[]` (empty list) when the command produces no output, but callers that expect a dict will get a list instead. This was noted as a prior bug fix (the docstring says "Callers should handle both list and dict return types"), but it's a permanent API hazard.

### RF-12: CLAUDE.md CHEATSHEET.md anchors use § prefix extensively
The entire cross-referencing system depends on `§`-prefixed anchors in HTML comments (e.g., `<!-- §validate_config.gh -->`). This is a custom convention with a custom validator (`validate_anchors.py`). If someone adds a new function without an anchor, or renames a function without updating the anchor, the cross-reference system breaks silently until `validate_anchors.py` is explicitly run.

### RF-13: No type checking
No `mypy.ini`, `pyrightconfig.json`, or type checking in CI. The code uses type hints (`list[str]`, `dict[str, str]`, etc.) but they are never verified. Functions return `Any` in several places (e.g., `_parse_value`). Type errors would not be caught until runtime.

### RF-14: Test test uses unittest, not pytest
Despite having a `.pytest_cache/` directory (suggesting pytest was tried), the Makefile runs `python -m unittest discover`. The test files import `unittest.TestCase`. This limits test features (no parametrize, no fixtures, no plugins).

### RF-15: Large test files
`test_gh_interactions.py` at ~2,091 LOC is extremely large for a single test file. Large test files are hard to maintain and suggest the tests may have grown organically without refactoring. Worth checking for duplicate test logic and test quality.

### RF-16: sprint-monitor claims to write to a log file
`check_status.py` CHEATSHEET.md entry lists `write_log()` function ("Append timestamped entry to monitor log"). But the SKILL.md says the script "does not modify tracking or burndown files -- it queries GitHub and reports to stdout." Need to verify whether `write_log()` actually writes to a file or just prints.

### RF-17: The Makefile lint target runs `validate_anchors.py`
Line 47 of the Makefile: `$(PYTHON) scripts/validate_anchors.py`. This means `make lint` both compiles all Python files AND validates anchors. If anchors are broken, lint fails. This is good for catching anchor drift, but it means lint failures could be non-obvious ("why did lint fail? oh, it's an anchor issue, not a Python issue").

### RF-18: `team/insights.md` is a volatile runtime artifact
The `insights.md` file is written by Giles during kickoff ceremony, referenced during story dispatch, demo, and retro -- but it is never validated, never tested, and never generated by any Python script. It is entirely a prompt-directed artifact. If the ceremony prompt changes or the LLM generates it in a different format, downstream consumers would silently get wrong data.

---

## Import Dependency Graph (verified from code)

`validate_config.py` is the central hub. Every other script imports from it.

Notable cross-imports:
- `sync_backlog.py` imports from both `scripts/validate_config.py` AND `skills/sprint-setup/scripts/populate_issues.py`
- `sprint_init.py` imports `validate_project` from `validate_config.py` but NOT `load_config`
- All skill scripts use `sys.path.insert(0, ...)` with 4-level parent traversal

---

## Summary of Gaps Between Claims and Code

| Claim | Reality | Risk |
|-------|---------|------|
| `definition-of-done.md` is part of config structure | Generated by init, not validated | Retro ceremony may fail silently |
| `check_status.py` covers Steps 0-3 | Does NOT cover Step 0 (backlog sync) | Agent may skip backlog sync |
| Evals test the skill behavior | Evals are non-executable documentation | No skill-level testing |
| GitHub is the source of truth | True for issue STATE, not for backlog CONTENT | Bidirectional sync ambiguity |
| All scripts are idempotent | Idempotency depends on correct state detection | Bugs in detection = duplicates |
| Line numbers in CHEATSHEET.md are accurate | Manually maintained, likely stale after 8 fix passes | Developer confusion |
