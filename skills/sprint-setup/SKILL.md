---
name: sprint-setup
description: One-time project bootstrap for sprint process. Use when starting a project for the first time, setting up GitHub integration, creating labels/milestones/issues, or when someone asks how to initialize the sprint workflow. Also triggers on "setup sprints", "bootstrap project", "initialize GitHub", "create sprint board".
---

# Sprint Setup Skill

Bootstrap a project on GitHub: labels, milestones, issues, project board, CI, and
tracking files. Run once at project start; subsequent sprints use `sprint-run`.

## Quick Reference

| Phase | Read These First |
|-------|-----------------|
| Prerequisites | `references/prerequisites-checklist.md` |
| Labels & Conventions | `references/github-conventions.md` |
| CI Workflow | `references/ci-workflow-template.md` |
| Scripts | `scripts/bootstrap_github.py`, `scripts/populate_issues.py`, `scripts/setup_ci.py` |

---

## Phase 0: Project Initialization

If `sprint-config/` exists — run `scripts/validate_config.py`. Pass → Step 1. Fail → show errors, stop.

If `sprint-config/` does not exist — ask the user, then run `scripts/sprint_init.py` to
auto-detect project structure and generate config. Load `project.toml` via
`validate_config.load_config()` before continuing.

---

## Step 1: Check Prerequisites

Read `references/prerequisites-checklist.md` and verify each item:
1. `gh` CLI installed and authenticated
2. Superpowers plugin installed
3. Git remote configured
4. Language toolchain available (detected from `project.toml`)
5. Python 3.10+ venv created and activated

If any prerequisite fails, follow the install/fix instructions in the checklist.
Proceed to Step 2 only when all checks pass.

---

## Step 2: GitHub Bootstrap

All scripts are idempotent — safe to re-run. They read `sprint-config/project.toml`
from cwd (no flags needed).

#### 2.1 Create Labels

Read `references/github-conventions.md` for the full label taxonomy (persona, sprint,
saga, priority, kanban, type categories).

```bash
source .venv/bin/activate
python skills/sprint-setup/scripts/bootstrap_github.py
```

#### 2.2 Create Milestones & Project Board

Also handled by `bootstrap_github.py` — creates one milestone per sprint (due dates
from current date) and a GitHub Projects (v2) board with 6 kanban columns.

#### 2.3 Populate Issues

```bash
python skills/sprint-setup/scripts/populate_issues.py
```

Creates one GitHub issue per story from `backlog/milestones/` with labels, milestone,
and full requirements.

#### 2.4 Generate CI Workflow

Read `references/ci-workflow-template.md` for the workflow structure.

```bash
python skills/sprint-setup/scripts/setup_ci.py
```

Supported languages: Rust, Python, Node.js, Go. Review `.github/workflows/ci.yml`
before committing.

#### 2.5 Initialize Tracking & Verify

Create sprint directories and `docs/dev-team/sprints/SPRINT-STATUS.md` (one row per
sprint). Verify label/milestone/issue counts and project board existence. If any count
is off, re-run the corresponding script — they are idempotent.

---

## Next Steps

1. **Start Sprint 1:** Invoke `sprint-run`.
2. **Enable monitoring (optional):** `/loop 5m sprint-monitor`
