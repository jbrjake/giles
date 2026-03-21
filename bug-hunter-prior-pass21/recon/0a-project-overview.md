# Project Overview: giles

Adversarial recon, pass 1. Comprehensive mapping of the codebase, architecture,
import chains, config system, claims to verify.

## 1. What It Is

A Claude Code plugin that orchestrates agile sprints with fictional team personas.
Version 0.4.0 (`.claude-plugin/plugin.json` line 4). MIT license.
Author: Jon Rubin / jbrjake.

Five skills: sprint-setup, sprint-run, sprint-monitor, sprint-release, sprint-teardown.
18 Python scripts (7,901 total lines). 19 skeleton templates. 15 test files.
One test fixture project (hexwise — a Rust color utility).

## 2. File Tree

```
.claude-plugin/
  plugin.json                     — manifest: name, version, 5 skill paths

scripts/                          — 12 shared scripts (stdlib-only Python 3.10+)
  validate_config.py              — TOML parser, config validation, gh wrappers, shared helpers (1045 lines)
  sprint_init.py                  — ProjectScanner + ConfigGenerator (997 lines)
  sprint_teardown.py              — classify/remove symlinks+generated files (498 lines)
  commit.py                       — conventional commit enforcement (157 lines)
  sync_backlog.py                 — debounce/throttle backlog sync (253 lines)
  sprint_analytics.py             — velocity, review rounds, workload (282 lines)
  team_voices.py                  — extract persona commentary (109 lines)
  traceability.py                 — story/PRD/test bidirectional mapping (223 lines)
  test_coverage.py                — planned vs actual test comparison (211 lines)
  manage_epics.py                 — epic CRUD (add/remove/reorder stories)
  manage_sagas.py                 — saga management (allocation/index/voices)
  validate_anchors.py             — section-anchor reference validation (337 lines)

skills/
  sprint-setup/
    SKILL.md                      — entry point: Phase 0 init, Step 1 prereqs, Step 2 bootstrap
    scripts/
      bootstrap_github.py         — create labels, milestones on GitHub (339 lines)
      populate_issues.py          — parse milestones -> GitHub issues (536 lines)
      setup_ci.py                 — generate .github/workflows/ci.yml (407 lines)
    references/
      github-conventions.md       — label taxonomy, issue/PR templates
      prerequisites-checklist.md  — prereq validation steps
      ci-workflow-template.md     — CI YAML skeleton reference
  sprint-run/
    SKILL.md                      — phase detection, kickoff, story execution, demo, retro
    scripts/
      sync_tracking.py            — reconcile local tracking <-> GitHub (398 lines)
      update_burndown.py          — burndown.md + SPRINT-STATUS.md from milestones (241 lines)
    agents/
      implementer.md              — subagent: TDD, PR creation, persona context
      reviewer.md                 — subagent: 3-pass review, confidence reading
    references/
      kanban-protocol.md          — 6 states, transitions, WIP limits
      persona-guide.md            — assignment rules, voice guidelines
      ceremony-kickoff.md         — kickoff ceremony protocol
      ceremony-demo.md            — demo ceremony protocol
      ceremony-retro.md           — retro ceremony protocol
      context-recovery.md         — 6-step state reconstruction
      story-execution.md          — story lifecycle through kanban states
      tracking-formats.md         — SPRINT-STATUS.md and story file formats
  sprint-monitor/
    SKILL.md                      — CI check, drift detection, PR watch, burndown
    scripts/
      check_status.py             — CI/PR/milestone/drift monitoring (438 lines)
  sprint-release/
    SKILL.md                      — gate validation, tag, release, rollback
    scripts/
      release_gate.py             — 5 gates, versioning, notes, publish (746 lines)
    references/
      release-checklist.md        — per-milestone gate criteria
  sprint-teardown/
    SKILL.md                      — safety principles, dry run, execute

references/skeletons/             — 19 .tmpl files for scaffolding sprint-config/
  Core (9): project.toml, team-index.md, persona.md, giles.md, backlog-index.md,
            milestone.md, rules.md, development.md, definition-of-done.md
  Deep (10): saga.md, epic.md, story-detail.md, prd-index.md, prd-section.md,
             test-plan-index.md, golden-path.md, test-case.md, story-map-index.md,
             team-topology.md

tests/                            — 15 test files + support infrastructure
  conftest.py                     — shared sys.path setup for all test files
  fake_github.py                  — FakeGitHub: in-memory gh CLI simulator
  mock_project.py                 — MockProject: temp dir Rust project scaffold
  gh_test_helpers.py              — shared test helper utilities
  golden_recorder.py              — record gh CLI interactions for replay
  golden_replay.py                — replay recorded interactions
  golden/recordings/              — 5 recorded golden test sequences
  fixtures/hexwise/               — full sample Rust project with personas, backlog, etc.
  test_lifecycle.py               — end-to-end lifecycle test
  test_hexwise_setup.py           — hexwise fixture integration test
  test_gh_interactions.py         — gh CLI interaction unit tests
  test_pipeline_scripts.py        — script pipeline tests
  test_sprint_runtime.py          — sprint execution tests
  test_bugfix_regression.py       — regression tests for specific bugs
  test_verify_fixes.py            — fix verification tests
  test_property_parsing.py        — hypothesis property-based tests
  test_fakegithub_fidelity.py     — FakeGitHub fidelity tests
  test_golden_run.py              — golden recording replay tests
  test_release_gate.py            — release gate tests
  test_sprint_analytics.py        — analytics script tests
  test_sprint_teardown.py         — teardown tests
  test_sync_backlog.py            — backlog sync tests
  test_validate_anchors.py        — anchor validation tests

evals/evals.json                  — 6 skill evaluation scenarios
Makefile                          — test, lint, venv targets
.github/workflows/ci.yml         — CI: Python 3.10-3.13 matrix, lint + test
```

## 3. Script Interconnections (Import Chain)

### Central Hub: validate_config.py

Every script in the project imports from `scripts/validate_config.py`. It provides:
- `parse_simple_toml()` — custom TOML parser (no tomllib dependency)
- `load_config()` / `validate_project()` — config loading + validation
- `gh()` / `gh_json()` — gh CLI wrappers
- Shared helpers: `extract_sp()`, `kanban_from_labels()`, `find_milestone()`,
  `extract_story_id()`, `detect_sprint()`, `frontmatter_value()`, `parse_header_table()`
- Constants: `KANBAN_STATES`, `TABLE_ROW`

### Import Paths

All skill scripts reach validate_config.py via sys.path.insert hack:
```python
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent / "scripts"))
```
This navigates 4 directories up from `skills/<skill>/scripts/` to the repo root, then into `scripts/`.

Shared scripts (in `scripts/`) use simpler paths:
```python
sys.path.insert(0, str(Path(__file__).resolve().parent))
```

### Cross-Skill Dependency

`scripts/sync_backlog.py` (line 24) also adds sprint-setup/scripts to sys.path:
```python
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "skills" / "sprint-setup" / "scripts"))
```
Then imports `bootstrap_github` and `populate_issues` for reuse. This is the only
cross-skill import. CLAUDE.md acknowledges this as intentional coupling (line 129).

`skills/sprint-monitor/scripts/check_status.py` (line 27) imports `sync_backlog`:
```python
from sync_backlog import main as sync_backlog_main
```
This works because conftest.py adds scripts/ to sys.path, but in production the
script's own sys.path.insert handles it (line 22 adds the `scripts/` parent).

### Shared Helpers Extracted to validate_config.py

Several helpers were consolidated into validate_config.py (noted by BH18-* comments):
- `frontmatter_value()` (BH18-005) — shared by sync_tracking and update_burndown
- `parse_header_table()` / `TABLE_ROW` (BH18-012/013) — shared by manage_epics/sagas/traceability
- `safe_int()` — imported by manage_epics, manage_sagas

### Import Diagram

```
validate_config.py  <-- every script imports from here
  |
  +-- sprint_init.py (also imports validate_project directly)
  +-- sprint_teardown.py (standalone, no validate_config import)
  +-- sync_backlog.py --> bootstrap_github.py + populate_issues.py
  +-- commit.py (standalone, no validate_config import)
  +-- sprint_analytics.py
  +-- team_voices.py
  +-- traceability.py
  +-- test_coverage.py
  +-- manage_epics.py (imports safe_int, TABLE_ROW, parse_header_table)
  +-- manage_sagas.py (imports safe_int, TABLE_ROW, parse_header_table)
  +-- validate_anchors.py (standalone reference map, no validate_config)
  |
  +-- bootstrap_github.py (setup skill)
  +-- populate_issues.py (setup skill)
  +-- setup_ci.py (setup skill)
  +-- sync_tracking.py (run skill)
  +-- update_burndown.py (run skill)
  +-- check_status.py (monitor skill) --> sync_backlog.py
  +-- release_gate.py (release skill)
```

**Correction**: sprint_teardown.py and commit.py do NOT import validate_config.
validate_anchors.py also does not import validate_config. These are self-contained.

## 4. Configuration System

### sprint-config/ Directory (Generated, .gitignored)

Created by `sprint_init.py`. Structure:
```
sprint-config/
  project.toml          — main config ([project], [paths], [ci], [conventions], [release])
  definition-of-done.md — evolving DoD
  team/
    INDEX.md            — persona table (Name | Role | File)
    {name}.md           — persona files (symlinks to project originals)
    giles.md            — built-in scrum master (COPIED, not symlinked)
    history/            — sprint history files per persona
    insights.md         — motivation distillation (generated at kickoff)
  backlog/
    INDEX.md            — saga routing table
    milestones/         — symlinks to milestone files
    sagas/              — symlink to sagas dir (optional)
    epics/              — symlink to epics dir (optional)
  rules.md              — symlink to project rules
  development.md        — symlink to dev guide
  .sprint-init-manifest.json — what init created (for teardown)
  .sync-state.json      — backlog sync state
```

### Required TOML Keys (validate_config.py line 426-435)

```
project.name, project.repo, project.language
paths.team_dir, paths.backlog_dir, paths.sprints_dir
ci.check_commands, ci.build_command
```

### Optional TOML Keys

```
project.base_branch (default: "main")
paths.prd_dir, paths.test_plan_dir, paths.sagas_dir, paths.epics_dir
paths.story_map, paths.team_topology
conventions.branch_pattern, conventions.commit_style
```

### Required Files (validate_config.py line 410-423)

```
{config_dir}/project.toml
{config_dir}/team/INDEX.md
{config_dir}/backlog/INDEX.md
{config_dir}/rules.md
{config_dir}/development.md
{config_dir}/definition-of-done.md
```

### Validation Rules (validate_project, line 442-562)

1. All 6 required files must exist
2. project.toml must parse and have required sections (project, paths, ci)
3. Required TOML keys must be present
4. team/INDEX.md must list at least 2 non-Giles personas
5. Each persona in INDEX must have a corresponding .md file
6. At least one milestone file must exist in backlog/milestones/
7. rules.md and development.md must be non-empty

### Symlink Architecture

- `sprint_init.py` creates symlinks from sprint-config/ to actual project files
- Giles persona is COPIED (plugin-owned), not symlinked
- Teardown removes symlinks (safe, targets untouched) and generated files (with confirmation)
- Manifest file tracks what was created for precise teardown

### TOML Parser (validate_config.py line 125-208)

Custom parser supporting: strings (double/single quoted), ints, bools, arrays,
sections, multiline arrays, inline comments. Does NOT support:
- Dotted keys (`a.b = "value"`)
- Multi-line strings (`"""..."""`)
- Inline tables (`{key = "value"}`)
- Array of tables (`[[section]]`)

Notable hardening (bug-hunter fixes):
- BH20-001: Uses `split('\n')` not `splitlines()` to avoid U+2028/U+2029 corruption
- BH20-002: Allows digit-start TOML keys
- BH20-004: Warns on unrecognized lines
- BH-001: Inline comment stripping on multiline array continuation
- BH-002: Quote-aware bracket detection
- BH-007: Rejects `"""` and `'''` multi-line strings with clear error

## 5. Plugin Manifest (.claude-plugin/plugin.json)

```json
{
  "name": "giles",
  "description": "A plugin for agile agentic coding that takes it too far",
  "version": "0.4.0",
  "author": { "name": "Jon Rubin" },
  "repository": "https://github.com/jbrjake/giles",
  "license": "MIT",
  "skills": [
    "skills/sprint-setup/SKILL.md",
    "skills/sprint-run/SKILL.md",
    "skills/sprint-monitor/SKILL.md",
    "skills/sprint-release/SKILL.md",
    "skills/sprint-teardown/SKILL.md"
  ]
}
```

All 5 skill paths exist. Each SKILL.md has YAML frontmatter with name/description.

## 6. Skeleton Template System

19 templates in `references/skeletons/`. Used by `sprint_init.py` ConfigGenerator:
- `_copy_skeleton(skeleton_name, dest_rel)` copies template content to sprint-config/
- `_write(rel_path, content)` writes generated content
- `_symlink(link_rel, target_rel)` creates relative symlinks

Generation order (ConfigGenerator.generate, line 857-865):
1. project.toml (generated from scan results, or preserved if exists)
2. team/ (symlinks to persona files + generated INDEX.md + copied giles.md)
3. backlog/ (symlinks to milestone files + generated INDEX.md)
4. doc symlinks (rules.md, development.md, deep docs)
5. definition-of-done.md (skeleton copy)
6. team/history/ directory
7. .sprint-init-manifest.json

**Verify**: CLAUDE.md claims 19 templates (9 core + 10 deep). Actual count: 19 files.
Matches the claim.

## 7. Testing Infrastructure

### Test Doubles

- **FakeGitHub** (`tests/fake_github.py`): In-memory gh CLI simulator. Maintains
  labels, milestones, issues, PRs, releases, runs, reviews, timeline events,
  comparisons, and commits. Uses dispatch-dict routing. Shared issue/PR number
  counter (matches real GitHub behavior, BH19-007).

- **MockProject** (`tests/mock_project.py`): Creates temp dir with Cargo.toml,
  persona files, milestone files, backlog INDEX, rules, development guide. Can
  optionally init a real git repo.

- **Golden recordings** (`tests/golden/recordings/`): 5 recorded gh CLI interaction
  sequences for replay testing (01-setup-init through 05-setup-ci).

### CI

`.github/workflows/ci.yml`: Python 3.10-3.13 matrix on ubuntu-latest.
Runs `make lint` (py_compile all scripts + validate_anchors.py) and `make test`
(unittest discover).

### Dev Dependencies

`requirements-dev.txt`: pytest>=9.0, pytest-cov>=6.0, jq>=1.11, hypothesis>=6.
These are NOT needed for runtime (stdlib-only policy for user scripts).

## 8. Claims to Verify

### From CLAUDE.md

| # | Claim | Location | Notes |
|---|-------|----------|-------|
| 1 | "stdlib only, no external deps" for all scripts | CLAUDE.md line 35 | Need to grep all scripts for non-stdlib imports |
| 2 | "Scripts import chain: four directories up" | CLAUDE.md line 126 | Verified in bootstrap_github.py line 14. But shared scripts use 1 dir up. |
| 3 | "Idempotent scripts" | CLAUDE.md line 128 | Need to verify each bootstrap/monitor script handles duplicates |
| 4 | "Giles is copied, not symlinked" | CLAUDE.md line 124 | Verified: sprint_init.py line 738-754 uses _copy_skeleton |
| 5 | "19 templates" | CLAUDE.md line 117 | Verified: 19 files in references/skeletons/ |
| 6 | "GitHub as source of truth" | CLAUDE.md line 127 | Verified in sync_tracking.py docstring and logic |
| 7 | "6 kanban states" | CLAUDE.md line 74 | Verified: KANBAN_STATES frozenset line 935 |
| 8 | Requires "at least 2 non-Giles personas" | validate_config.py line 517-522 | Verified in code |

### From README.md

| # | Claim | Location | Notes |
|---|-------|----------|-------|
| 9 | "Rust, Python, Node.js, and Go out of the box" for CI | README.md line 397 | Verified: setup_ci._SETUP_REGISTRY has these 4 (+aliases) |
| 10 | "review -> dev loop caps at 3 rounds" | README.md line 182-183 | Need to verify in kanban-protocol.md — not enforced in scripts |
| 11 | "One story per persona in dev at a time" | README.md line 181 | Need to verify WIP enforcement in sprint-run logic |
| 12 | "Symlink architecture means teardown never touches originals" | README.md line 359 | Verified: teardown only unlinks symlinks |
| 13 | "Install: claude plugin add jbrjake/giles" | README.md line 315 | Cannot verify without Claude Code registry access |
| 14 | "Python 3.10+" | README.md line 429 | Uses `list[str]` type hints (3.9+), `match` statement in check_status.py (3.10+) |
| 15 | "retro produces no doc changes is a failed retro" | README.md line 215 | Need to verify in ceremony-retro.md |
| 16 | "Context recovery" | README.md line 307-309 | Need to verify context-recovery.md content vs sprint-run SKILL.md |

### Architectural Claims to Stress-Test

| # | Claim | Risk | Where to look |
|---|-------|------|---------------|
| 17 | Custom TOML parser handles all project.toml patterns | Edge cases in nested arrays, escaped quotes, unicode | validate_config.py parse_simple_toml |
| 18 | gh_json handles paginated output | Concatenated JSON arrays `[...][...]` | validate_config.py line 82-117 |
| 19 | sync_backlog debounce/throttle is correct | Race conditions, state corruption | sync_backlog.py check_sync |
| 20 | release_gate rollback is complete | Partial failures leave clean state | release_gate.py do_release |
| 21 | populate_issues duplicate detection is reliable | Story ID extraction edge cases | populate_issues.py get_existing_issues |
| 22 | shell=True in gate_tests/gate_build | Trust model: project.toml is trusted input | release_gate.py line 203-223 |
| 23 | Path traversal protection in symlinks | BH18-014 defense | sprint_init.py line 558-565 |
| 24 | extract_sp handles all body formats | 4 regex patterns in sequence | validate_config.py line 800-832 |

## 9. Bug-Hunter Trail (BH-* Fixes)

The codebase has extensive bug-fix annotations. Major categories:

- **BH-001 through BH-021**: Original bug-hunting passes. Fixes for comment stripping,
  bracket detection, parse errors, multi-line string rejection, YAML escaping, etc.
- **BH18-***: Pass 18 fixes. Shared helpers extraction (BH18-005, BH18-012/013),
  persona validation (BH18-008), path traversal defense (BH18-014), ReDoS protection
  (BH18-004), review rounds counting (BH18-006).
- **BH19-***: Pass 19 fixes. Shared GitHub number counter (BH19-007), label safety
  (BH19-003), dataflow fixes for closed issue status.
- **BH20-***: Pass 20 fixes. Unicode line splitting (BH20-001), digit-start TOML
  keys (BH20-002), unrecognized line warnings (BH20-004), team INDEX parsing (BH20-005).
- **BH-P11-***: Planning pass 11 fixes. Format string injection (P11-110), argparse
  note (P11-111), git binary check (P11-112), root commit filter (P11-114).
- **P13-***: Planning pass 13 fixes. Multiline run block parsing (P13-021).

## 10. Key Design Patterns

### Config-Driven Everything

No script hardcodes project-specific values. All come from `sprint-config/project.toml`
via `load_config()`. This means the plugin works for any project that provides the
required config structure.

### Idempotency

All creation functions check for existing resources before creating:
- `create_label()` uses `--force` flag
- `create_milestones_on_github()` catches "already_exists" errors
- `get_existing_issues()` fetches current issues for dedup before `create_issue()`
- `sync_tracking.sync_one()` only writes when fields differ
- `sprint_analytics.main()` checks for existing sprint entry before appending

### Error Handling Pattern

Scripts follow a consistent pattern:
1. Load config via `load_config()` (raises ConfigError on failure)
2. Query GitHub via `gh()` / `gh_json()` (raises RuntimeError on failure)
3. Process data, write output
4. `sys.exit(1)` on error, `sys.exit(0)` on success

### Frontmatter Convention

Story tracking files use YAML frontmatter (`---` delimited). The parser is
hand-rolled (`read_tf` in sync_tracking.py, `frontmatter_value` in validate_config.py)
rather than using a YAML library, consistent with the stdlib-only policy.

## 11. Notable Complexity Points

1. **populate_issues.py** — Most complex parsing: story tables, detail blocks,
   epic enrichment, sprint number inference, custom story ID patterns with ReDoS
   protection. Multiple regex patterns for different table formats.

2. **release_gate.py** — Most complex error handling: 10-step release flow with
   rollback at each step, tag deletion, commit revert, remote push recovery.

3. **parse_simple_toml()** — Hand-rolled parser with 7 helper functions for
   quote-aware comment stripping, bracket detection, escape processing, array
   splitting. Most hardened code in the project (5+ bug-fix passes).

4. **sync_tracking.py get_linked_pr()** — Complex PR linkage: timeline API with
   fallback to branch name matching, preference ordering (open > merged > last).

5. **check_status.py main()** — Orchestrates 5 monitoring checks with cached
   milestone data, 14-day fallback for drift detection, sync_backlog integration.
