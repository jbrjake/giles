# Phase 0a: Project Overview Recon

> Generated: 2026-03-16 | Project: giles v0.4.0 | Branch: main

## 1. Project Purpose

**giles** is a Claude Code plugin that orchestrates agile sprints with persona-based development. It manages GitHub issues, PRs, CI, kanban tracking, and sprint ceremonies (kickoff, demo, retro) using fictional team personas that implement and review code in-character. The built-in scrum master is a librarian named Giles.

- **Author:** Jon Rubin (jbrjake)
- **License:** MIT
- **Plugin manifest:** `.claude-plugin/plugin.json`
- **Tagline:** "agile agentic development that takes it too far"

## 2. Directory Structure (Top 3 Levels)

```
giles/
├── .claude-plugin/
│   └── plugin.json                    # Plugin manifest (name, version, skills)
├── .claude/
│   ├── settings.json
│   └── settings.local.json
├── .github/
│   └── workflows/
│       └── ci.yml                     # CI: Python 3.10-3.13, lint + test
├── docs/
│   └── superpowers/
│       ├── plans/                     # Design plans (12 files)
│       └── specs/                     # Design specs (5 files)
├── evals/
│   └── evals.json                     # 6 skill evaluation scenarios
├── references/
│   └── skeletons/                     # 19 .tmpl skeleton files
├── scripts/                           # 12 shared Python scripts
├── skills/
│   ├── sprint-setup/                  # SKILL.md + scripts/ + references/
│   ├── sprint-run/                    # SKILL.md + scripts/ + agents/ + references/
│   ├── sprint-monitor/                # SKILL.md + scripts/
│   ├── sprint-release/                # SKILL.md + scripts/ + references/
│   └── sprint-teardown/               # SKILL.md only (delegates to scripts/)
├── tests/                             # 15 test files + 5 test infrastructure files
│   ├── fixtures/hexwise/              # Full fixture project
│   └── golden/recordings/             # Golden test recordings
├── CLAUDE.md                          # Agent instructions (comprehensive)
├── CHEATSHEET.md                      # Anchor-indexed quick reference
├── ADVERSARIAL-REVIEW.md              # Prior audit findings (30 items)
├── Makefile                           # test, lint, clean targets
├── README.md                          # Full project documentation
├── requirements-dev.txt               # pytest, pytest-cov, jq, hypothesis
└── LICENSE
```

## 3. File Counts by Category

### Python Scripts (source — not in .venv or tests)

| Location | Files | Approx Lines | Description |
|----------|-------|-------------|-------------|
| `scripts/` | 12 | ~5,500 | Shared utilities (validate_config, sprint_init, etc.) |
| `skills/sprint-setup/scripts/` | 3 | ~1,500 | bootstrap_github, populate_issues, setup_ci |
| `skills/sprint-run/scripts/` | 2 | ~800 | sync_tracking, update_burndown |
| `skills/sprint-monitor/scripts/` | 1 | ~300 | check_status |
| `skills/sprint-release/scripts/` | 1 | ~600 | release_gate |
| **Source total** | **19** | **~8,700** | |

### Test Files

| File | Approx Lines | Focus |
|------|-------------|-------|
| `test_pipeline_scripts.py` | ~1,230 | team_voices, traceability, manage_epics, manage_sagas, scanner heuristics |
| `test_bugfix_regression.py` | ~1,395 | BH-xxx regression tests (audit-driven) |
| `test_gh_interactions.py` | ~419 | commit.py, release_gate.py helpers |
| `test_hexwise_setup.py` | ~441 | End-to-end setup against hexwise fixture |
| `test_lifecycle.py` | ~441 | Full sprint lifecycle flow |
| `test_release_gate.py` | ~419 | Release gate validation |
| `test_sprint_analytics.py` | ~300 | Velocity, review rounds, workload |
| `test_sprint_runtime.py` | ~300 | Sprint runtime scripts |
| `test_sprint_teardown.py` | ~300 | Teardown safety |
| `test_sync_backlog.py` | ~300 | Backlog sync debounce/throttle |
| `test_validate_anchors.py` | ~300 | Anchor validation |
| `test_golden_run.py` | ~200 | Golden recording replay |
| `test_property_parsing.py` | ~200 | Hypothesis property tests (TOML/regex) |
| `test_fakegithub_fidelity.py` | ~200 | FakeGitHub behavior fidelity |
| `test_verify_fixes.py` | ~200 | Fix verification |
| **Test total** | **15 test files** | **~6,145** |

### Test Infrastructure

| File | Purpose |
|------|---------|
| `conftest.py` | sys.path setup for all test files |
| `fake_github.py` | In-memory GitHub state double (~949 lines) |
| `gh_test_helpers.py` | Patch helpers for gh CLI mocking |
| `mock_project.py` | Project fixture helpers |
| `golden_recorder.py` | Golden test recording |
| `golden_replay.py` | Golden test replay |

### Other File Types

| Category | Count | Notes |
|----------|-------|-------|
| SKILL.md files | 5 | One per skill |
| Reference .md files | 10 | Kanban protocol, persona guide, ceremonies, etc. |
| Agent .md files | 2 | implementer.md, reviewer.md |
| Skeleton .tmpl files | 19 | Templates for sprint-config scaffolding |
| Fixture .md files | ~30 | Under tests/fixtures/hexwise/ |

## 4. Key Architectural Decisions

1. **Config-driven:** All project-specific values from `sprint-config/project.toml`; nothing hardcoded.
2. **Custom TOML parser:** `parse_simple_toml()` in validate_config.py — no `tomllib` dependency. Supports strings, ints, bools, arrays, sections. Has had multiple bug fixes (BH-001, BH-002, BH-021, BH-022, BH-030 from prior audit).
3. **Symlink-based config:** `sprint_init.py` symlinks from `sprint-config/` to project files. Teardown removes symlinks only. Exception: Giles is copied, not symlinked.
4. **Scripts import chain:** All skill scripts do `sys.path.insert(0, ...)` to reach shared `scripts/validate_config.py`.
5. **GitHub as source of truth:** `sync_tracking.py` treats GitHub issue/PR state as authoritative.
6. **Idempotent scripts:** All bootstrap and monitoring scripts safe to re-run.
7. **Cross-skill dependency:** `sync_backlog.py` imports from `skills/sprint-setup/scripts/` (intentional coupling).
8. **Stdlib-only runtime:** No pip packages required for users. Dev dependencies (pytest, hypothesis, jq) are test-only.
9. **FakeGitHub test double:** ~949-line in-memory GitHub simulation (issues, PRs, milestones, labels, runs, releases, reviews) with jq expression evaluation. Central to test infrastructure.

## 5. CI Configuration

- GitHub Actions, runs on push/PR to main
- Matrix: Python 3.10, 3.11, 3.12, 3.13
- Steps: checkout, venv, lint (py_compile + validate_anchors), test (unittest discover)
- Actions pinned to `@v6` (Node 24 runtime)
- Dev deps: `pytest>=9.0`, `pytest-cov>=6.0`, `jq>=1.11`, `hypothesis>=6`

## 6. TODO/FIXME/HACK/XXX Audit

### In Source Code (scripts/*.py, skills/*/scripts/*.py)

| File | Line | Content | Assessment |
|------|------|---------|------------|
| `setup_ci.py` | 244 | `"# TODO: Add setup steps for {language}"` | **Generated output**, not actual deferred work. Emitted into CI YAML for unsupported languages. |
| `sprint_init.py` | 572 | `"<!-- TODO: populate {dest_rel} -->"` | **Generated stub content** for user to fill in. |
| `sprint_init.py` | 616 | `'repo = "TODO-owner/repo"'` | **Placeholder** in generated project.toml when repo can't be detected. |
| `sprint_init.py` | 658 | `'build_command = "TODO-build-command"'` | **Placeholder** in generated project.toml when build command can't be detected. |

**Assessment:** Zero actual TODO/FIXME/HACK items in source code. All instances are intentional placeholder text emitted into generated files for user completion.

### In Skeleton Templates (references/skeletons/*.tmpl)

~120 instances of "TODO" across 17 template files. All are placeholder markers for users to fill in (e.g., `"TODO: Full Name"`, `"TODO: Saga Name"`, `"TODO-owner/repo"`). This is the expected pattern for scaffolding templates.

### In Test Code

Zero FIXME/HACK/XXX. The only "TODO" references in test files are assertions verifying that generated output contains the expected TODO placeholder text.

## 7. Prior Audit History

The project has been through extensive bug-hunting:
- `ADVERSARIAL-REVIEW.md`: 30-item audit (3 CRITICAL, 9 HIGH, 8 MEDIUM, 10 LOW), all marked RESOLVED
- `recon-prior-pass17/`: Most recent prior recon (mutation testing + cross-module flow tracing)
- `bug-hunter-prior-*`: 12 prior audit directories (passes 5-16, plus pre-2026-03-14)
- Recent commits reference P17 (pass 17) fixes

Three systemic patterns identified in prior audit:
- **PAT-001:** TOML parser state machine gaps (multiline arrays + inline comments)
- **PAT-002:** Tests that mock the function under test (testing wiring, not logic)
- **PAT-003:** Case/format mismatches across module boundaries (language capitalization)

## 8. Initial Impressions / Smell Checks

### Strengths
- **Well-documented:** CLAUDE.md, CHEATSHEET.md, and README.md are comprehensive and internally consistent.
- **Thorough test infrastructure:** FakeGitHub is a serious test double (~949 lines), not a trivial mock. Golden recordings, property-based tests (hypothesis), and fixture projects provide good coverage diversity.
- **Config validation is defensive:** validate_project() catches missing files, bad TOML, missing keys. Error messages include actionable guidance.
- **Extensive prior auditing:** 17+ bug-hunter passes have already exercised most obvious failure paths. Regression tests exist for each fix.

### Potential Concerns
- **Custom TOML parser complexity:** Despite multiple rounds of fixes, `parse_simple_toml()` is a hand-rolled parser handling multiline arrays, inline comments, quote escaping, and type coercion. This remains the highest-risk code area. The ADVERSARIAL-REVIEW.md PAT-001 pattern identified 5 issues in this parser alone.
- **sys.path manipulation:** Every skill script and test file manipulates sys.path. conftest.py centralizes this for tests, but skill scripts each do their own `sys.path.insert(0, ...)`. This is fragile if directory structures change.
- **Large test files:** `test_bugfix_regression.py` (~1,395 lines) and `test_pipeline_scripts.py` (~1,230 lines) are getting long. They contain regression tests from multiple audit passes, which is natural but makes navigation harder.
- **FakeGitHub surface area:** At ~949 lines, FakeGitHub is itself a significant codebase. Fidelity bugs in FakeGitHub can mask real production bugs (this was identified as PAT-002 in prior audits).
- **Makefile lint is py_compile only:** No real linter (ruff, flake8, mypy). The lint target does syntax checking + anchor validation but no style/type enforcement.
- **No type checking:** No mypy, pyright, or type annotations enforcement in CI. Scripts use type hints (e.g., `dict | None`) but these are never verified.
- **Test runner is unittest, not pytest:** Despite `pytest` being in requirements-dev.txt, `make test` uses `unittest discover`. Some pytest features (fixtures, parametrize) are not leveraged.
- **validate_config.py is a kitchen sink:** Contains the TOML parser, config validation, path resolution, GitHub CLI wrappers, story point extraction, kanban state logic, milestone lookup, and team index parsing. This file handles too many responsibilities.

### Quantitative Summary

| Metric | Value |
|--------|-------|
| Source scripts | 19 files |
| Test files | 15 files |
| Test infrastructure files | 6 files |
| SKILL.md files | 5 |
| Skeleton templates | 19 |
| Reference docs | 12 |
| Eval scenarios | 6 |
| CI matrix size | 4 Python versions |
| Prior audit passes | 17+ |
| TODOs in source | 0 (all are generated placeholder text) |
| FIXMEs/HACKs/XXXs | 0 |
