# Project Overview — giles

## Purpose

giles is a Claude Code plugin that runs agile sprints with persona-based development. It
orchestrates GitHub issues, PRs, CI, kanban tracking, and sprint ceremonies (kickoff, demo,
retro) using fictional team personas that implement and review code in-character. The tagline:
"agile agentic development that takes it too far."

## Plugin Structure

```
.claude-plugin/plugin.json   — manifest (name, version, author)
skills/                      — 5 skill entry points (each has a SKILL.md)
  sprint-setup/              — one-time bootstrap: GitHub labels, milestones, issues, CI
  sprint-run/                — sprint execution: kickoff → stories → demo → retro
  sprint-monitor/            — designed for /loop 5m; checks CI/PR/burndown/drift
  sprint-release/            — milestone gates, semver tag, GitHub Release
  sprint-teardown/           — safe symlink removal without touching originals
scripts/                     — shared Python scripts (all stdlib-only)
references/skeletons/        — 19 .tmpl files used by sprint_init.py to scaffold sprint-config/
evals/evals.json             — skill evaluation scenarios
```

**Skill lifecycle:** sprint-setup → sprint-run (repeats) → sprint-release → sprint-teardown

## Key Scripts and Responsibilities

| Script | Responsibility |
|--------|---------------|
| `scripts/validate_config.py` | TOML parser, config loader, shared helpers (gh(), gh_json(), TF dataclass, read_tf/write_tf, kanban_from_labels, detect_sprint, etc.) |
| `scripts/kanban.py` | Kanban state machine CLI: transition, assign, sync, status |
| `scripts/sprint_init.py` | Auto-detect project layout → generate sprint-config/ with symlinks |
| `scripts/sprint_teardown.py` | Classify and safely remove sprint-config/ entries |
| `scripts/sync_backlog.py` | Debounced/throttled backlog auto-sync; imports bootstrap_github + populate_issues (intentional cross-skill coupling) |
| `scripts/sprint_analytics.py` | Velocity, review-round counts, workload metrics |
| `skills/sprint-setup/scripts/bootstrap_github.py` | Create GitHub labels and milestones (idempotent) |
| `skills/sprint-setup/scripts/populate_issues.py` | Parse milestone .md files → create GitHub issues |
| `skills/sprint-setup/scripts/setup_ci.py` | Generate .github/workflows/ci.yml for Rust/Python/Node/Go |
| `skills/sprint-run/scripts/sync_tracking.py` | Reconcile local tracking files with GitHub (GitHub is source of truth for sprint-run) |
| `skills/sprint-run/scripts/update_burndown.py` | Update burndown from GitHub milestone progress |
| `skills/sprint-monitor/scripts/check_status.py` | CI status, open PRs, milestone progress, branch divergence, direct-push detection |
| `skills/sprint-release/scripts/release_gate.py` | Gate checks, semver calculation, release notes, GitHub Release publishing |

## The New kanban.py State Machine

**File:** `scripts/kanban.py`

**Source of truth:** local tracking files (`sprint-{N}/stories/*.md`). GitHub is a downstream
reflection, synced on every mutation. This inverts the direction used by sync_tracking.py
(where GitHub is authoritative) — kanban.py owns writes, sync_tracking.py reads.

**State machine (6 states, linear with one loop-back):**
```
todo → design → dev → review → integration → done
                 ↑       |
                 └───────┘  (review can return to dev)
```

**TRANSITIONS dict** enforces legal edges. `validate_transition()` is pure (no I/O).

**Preconditions per target state:**
- `design` — implementer must be set
- `dev` — branch and pr_number must be set
- `review` — implementer and reviewer must be set
- `done` — pr_number must be set
- `todo`, `integration` — no preconditions

**Concurrency:** POSIX `fcntl` file locking. `lock_story()` locks a single tracking file;
`lock_sprint()` locks a sentinel `.kanban.lock` file to serialize all sprint mutations.
Fails fast on non-POSIX (e.g., plain Windows without WSL).

**Atomic writes:** `atomic_write_tf()` writes to a `.tmp` sibling then `os.rename()` — no
partial-write window observable by concurrent readers.

**do_sync():** Bidirectional. Accepts legal external GitHub transitions; warns on illegal
ones. Creates local tracking files for stories that appear on GitHub but have no local file.
Warns about local stories absent from GitHub (does not delete them).

**do_assign():** Updates local TF, adds persona labels on GitHub, rewrites the `[Unassigned]`
header in the issue body to the implementer's name.

**Integration point:** kanban.py imports `TF`, `read_tf`, `write_tf`, `slug_from_title`, and
`KANBAN_STATES` from validate_config.py. The TF dataclass and its I/O routines now live in
the shared module.

## TF Dataclass and I/O (validate_config.py, lines 1006–1103)

`TF` is a dataclass holding all tracking-file fields: `story`, `title`, `sprint`,
`implementer`, `reviewer`, `status`, `branch`, `pr_number`, `issue_number`, `started`,
`completed`, `body_text`, plus `path` (used by write_tf for the target file).

`read_tf(path)` — parses YAML frontmatter (handles BOM, uses `frontmatter_value()` helper).
`write_tf(tf)` — serializes fields using `_yaml_safe()` to quote YAML-sensitive characters.
`slug_from_title(title)` — URL-safe slug for tracking file names.
`_yaml_safe(value)` — quotes strings containing `: `, `#`, boolean keywords, backslashes,
and embedded newlines (fixes for BH-007, BH21-005).

## Configuration System

All skills load `sprint-config/project.toml` via `validate_config.load_config()`.

**Required TOML keys:** `project.name`, `project.repo`, `project.language`,
`paths.team_dir`, `paths.backlog_dir`, `paths.sprints_dir`, `ci.check_commands`,
`ci.build_command`.

**Optional:** `project.base_branch` (defaults to `main`); `[conventions]` keys
(`branch_pattern`, `commit_style`) are informational only — not read by scripts.

**Optional deep-doc keys:** `paths.prd_dir`, `paths.test_plan_dir`, `paths.sagas_dir`,
`paths.epics_dir`, `paths.story_map`, `paths.team_topology`.

**sprint-config/ layout:** symlinks to existing project files (teardown-safe). Giles's
persona file is copied, not symlinked (plugin-owned). `definition-of-done.md` evolves
through retro sessions.

## Dependency Policy

**Runtime (user-facing scripts):** stdlib-only Python 3.10+. No pip installs required.
Custom TOML parser (`parse_simple_toml`) avoids `tomllib`. External CLI tools (`gh`, `jq`)
are acceptable runtime dependencies — the prerequisites checklist detects and guides install.

**Dev/test:** hypothesis, pyjq, and similar tools are fine as dev dependencies.

## Key Architectural Decisions

1. **Config-driven** — nothing hardcoded to a specific project; all values from project.toml.
2. **Symlink-based config** — sprint-config/ symlinks to project files; teardown removes
   symlinks without touching originals.
3. **Scripts import chain** — all skill scripts do `sys.path.insert(0, ...)` to reach
   `scripts/validate_config.py` (which is four directories up from skill scripts).
4. **Dual source-of-truth** — kanban.py makes local TF the authoritative state and pushes
   to GitHub; sync_tracking.py reads GitHub as authoritative and updates local files. These
   are complementary, not contradictory — kanban.py is used during active story work,
   sync_tracking.py reconciles after external changes.
5. **Idempotent bootstrap** — all setup scripts skip resources that already exist.
6. **Cross-skill coupling** — sync_backlog.py imports bootstrap_github and populate_issues
   intentionally, reusing their idempotent creation logic.
7. **POSIX-only locking** — kanban.py uses fcntl and will refuse to run on plain Windows.
8. **GitHub label-driven kanban** — `kanban_from_labels()` derives story state from
   `kanban:*` labels; closed issues override to `done` regardless of label (BH21-012).
