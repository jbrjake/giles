---
name: sprint-setup
description: One-time project bootstrap for sprint process. Use when starting a project for the first time, setting up GitHub integration, creating labels/milestones/issues, or when someone asks how to initialize the sprint workflow. Also triggers on "setup sprints", "bootstrap project", "initialize GitHub", "create sprint board".
---

# Sprint Setup Skill

Bootstrap a project on GitHub: labels, milestones, issues, project board, CI, and
tracking files. Run once at project start; subsequent sprints use `sprint-run`.

---

## Phase 0: Project Initialization

Before checking prerequisites, verify that the project has a `sprint-config/`
directory with the required configuration files.

### Check for sprint-config/

If `sprint-config/` exists and passes validation:
- Run `scripts/validate_config.py` to confirm all required files are present and valid
- If validation passes, proceed to Step 1 (Prerequisites)
- If validation fails, show the errors and stop

If `sprint-config/` does not exist:
- Ask the user: "No sprint-config/ found. Want me to scan your project and set it up?"
- If yes: run `scripts/sprint_init.py` to auto-detect project structure and generate sprint-config/
- If no: show the expected directory structure and required file formats, then stop

### Load Configuration

Once sprint-config/ is validated, load `project.toml`:
```python
from validate_config import load_config
config = load_config()
```

All subsequent steps read paths, commands, and project info from this config.

---

## Step 1: Prerequisites Check

Verify every prerequisite before continuing. If any check fails, show the fix and
stop. Do not proceed with partial setup -- a half-bootstrapped repo is harder to
fix than a fresh start.

### 1. GitHub CLI (`gh`)

```bash
gh --version
```

If missing, install it:

- **macOS:** `brew install gh`
- **Linux (Debian/Ubuntu):**
  ```bash
  curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg \
    | sudo dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" \
    | sudo tee /etc/apt/sources.list.d/github-cli.list > /dev/null
  sudo apt update && sudo apt install gh
  ```
- **Linux (Fedora):** `sudo dnf install gh`

The `gh` CLI is how every subsequent step talks to GitHub. Without it, nothing
else works.

### 2. GitHub authentication

```bash
gh auth status
```

If not authenticated:

```bash
gh auth login
```

Follow the interactive prompts. Choose HTTPS and authenticate via browser. The
bootstrap scripts create labels, milestones, issues, and a project board -- all of
which require authenticated API access.

### 3. Superpowers plugin

Check for the superpowers plugin:

```bash
find ~/.claude/plugins -type d -name "superpowers" 2>/dev/null | head -1 | grep -q . && echo "OK" || echo "MISSING"
```

If missing, install it:

```
claude plugin add anthropic/superpowers
```

Superpowers provides TDD, code review, verification, and other process skills that
the sprint process orchestrates. The `sprint-run` skill delegates implementation
work to superpowers agents, so it needs to be present before you start sprinting.

### 4. Git remote

```bash
git remote -v
```

Verify a GitHub remote exists (e.g., `origin` pointing to
`github.com/<org>/<project>`). If not:

- **Existing repo:** `git remote add origin https://github.com/<org>/<project>.git`
- **New repo:** `gh repo create <org>/<project> --private --source=. --remote=origin`

The bootstrap scripts use `gh` commands that infer the repo from the git remote.
Without a remote, label/issue creation has no target.

### 5. Language toolchain

Read `project.toml` `[project]` `language` for toolchain requirements. Verify the
required toolchain is installed. For example:

- **Rust:** `rustup --version && cargo --version`
- **Python:** `python3 --version` (must meet minimum version in config)
- **Node.js:** `node --version && npm --version`

If the toolchain is missing, follow the installation instructions for the detected
language. The CI workflow this skill generates runs language-specific checks, so the
toolchain needs to be present for local validation.

### 6. Python venv

The sprint process scripts require Python 3.10+. Create a local venv:

```bash
python3 --version   # must be 3.10+
python3 -m venv .venv
source .venv/bin/activate
```

If Python 3.10+ is not available:

- **macOS:** `brew install python@3.12`
- **Linux:** `sudo apt install python3.12 python3.12-venv`

Always activate the venv before running any sprint scripts. The `.venv/`
directory should be in `.gitignore` (the setup script adds it if missing).

### Checklist summary

Print this checklist and confirm all items pass before proceeding:

```
[x] 1. gh CLI installed
[x] 2. gh authenticated
[x] 3. superpowers plugin installed
[x] 4. Git remote configured
[x] 5. Language toolchain installed (per project.toml)
[x] 6. Python venv created and activated
[x] 7. sprint-config/ validated (Phase 0)
```

If any item shows `[ ]`, fix it and re-run the check. Do not continue.

---

## Step 2: GitHub Bootstrap

With prerequisites satisfied, run the bootstrap scripts in order. Each script is
idempotent -- re-running skips resources that already exist.

### 2.1 Create label taxonomy

```bash
source .venv/bin/activate
python skills/sprint-setup/scripts/bootstrap_github.py
```

This creates the full label taxonomy on the GitHub repo. Labels are read from
`sprint-config/` rather than hardcoded:

**Persona labels** (one per team member voice):
Read `team/INDEX.md` for persona labels. The bootstrap script parses this file
and creates one `persona:<name>` label per listed team member.

**Sprint labels:**
Read `backlog/INDEX.md` for sprint count. Creates `sprint:1` through `sprint:N`
based on the number of milestones defined.

**Saga labels:**
Read `backlog/INDEX.md` for saga labels. Creates one `saga:<id>` label per saga
listed in the backlog index.

**Priority labels**:
`priority:P0`, `priority:P1`, `priority:P2`

Maps directly to the priority definitions in the backlog README: P0 blocks release,
P1 blocks GA, P2 tracks for later.

**Kanban labels** (workflow stages):
`kanban:todo`, `kanban:design`, `kanban:dev`, `kanban:review`,
`kanban:integration`, `kanban:done`

These drive the project board columns and are how `sprint-monitor` tracks velocity.

**Type labels**:
`type:story`, `type:bug`, `type:spike`, `type:chore`

Stories carry user value; bugs fix regressions; spikes reduce uncertainty; chores
are maintenance.

### 2.2 Create milestones

The script reads milestone definitions from `backlog/milestones/` and creates one
GitHub milestone per sprint, with durations specified in the milestone files.

Milestone due dates are calculated from the current date at bootstrap time.

### 2.3 Create GitHub Project board

```bash
# Included in bootstrap_github.py
```

Creates a GitHub Projects (v2) board with columns matching the kanban stages:

1. **Todo** -- accepted into sprint, not yet started
2. **Design** -- architecture/API design in progress
3. **Dev** -- implementation underway
4. **Review** -- PR open, awaiting review
5. **Integration** -- merged, awaiting integration test pass
6. **Done** -- all acceptance criteria verified

The board gives a single view of sprint progress. The `sprint-monitor` skill reads
this board to report velocity and detect blocked work.

### 2.4 Populate issues

```bash
python skills/sprint-setup/scripts/populate_issues.py
```

Parses milestone files from `backlog/milestones/` and creates one GitHub issue per
story. Each issue contains:

- **Title:** `US-XXXX: Story title` (e.g., `US-0101: <story name>`)
- **Body:** Full story requirements including:
  - User story ("As a ... I want ... so that ...")
  - Acceptance criteria (as a task list)
  - PRD cross-references
  - Related/blocked-by stories
  - Story point estimate
- **Labels:** saga (e.g., `saga:S01`), sprint (e.g., `sprint:1`), priority
  (e.g., `priority:P0`), type (`type:story`)
- **Milestone:** the corresponding sprint milestone

The script preserves traceability from the backlog docs through to GitHub issues.
Every story ID in the milestone file becomes a trackable, assignable issue.

### 2.5 Set up GitHub Actions CI

```bash
python skills/sprint-setup/scripts/setup_ci.py
```

Generates `.github/workflows/ci.yml` by reading the `[ci]` section of
`project.toml`. The config specifies:

- **Runner image** (`ci.runner`, default: `ubuntu-latest`)
- **Toolchain setup steps** (`ci.toolchain_steps`)
- **Check commands** (`ci.checks`) -- e.g., formatting, linting, tests
- **Post-build validations** (`ci.validations`) -- e.g., artifact size checks

Example structure generated for a Rust project (when `project.toml` specifies
`language = "rust"`):

```yaml
name: CI
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  check:
    runs-on: ubuntu-latest  # from ci.runner
    steps:
      - uses: actions/checkout@v4
      # toolchain steps from ci.toolchain_steps
      # check commands from ci.checks
      # validations from ci.validations
```

The exact steps, commands, and validations are all driven by `project.toml`, not
hardcoded. This ensures the CI workflow matches the actual project language and
build system.

Commit the generated workflow using:
`python {plugin_root}/scripts/commit.py "ci: add GitHub Actions workflow"`

### 2.6 Initialize tracking files

Create the sprint tracking structure. Read the sprint count from
`backlog/INDEX.md` to determine how many sprint directories to create:

```bash
mkdir -p docs/dev-team/sprints/sprint-1
```

**`docs/dev-team/sprints/SPRINT-STATUS.md`** -- initial state generated from
the milestone definitions in `backlog/milestones/`:

```markdown
# Sprint Status

| Sprint | Status | Start | End | Velocity (SP) |
|--------|--------|-------|-----|---------------|
| Sprint 1 | Not Started | — | — | — |
| Sprint 2 | Not Started | — | — | — |
...
```

The number of rows matches the sprint count from the backlog. Each sprint
directory is created empty, ready for:
- Sprint retrospective notes
- Daily standup logs
- Burndown data

These files give the `sprint-run` and `sprint-monitor` skills a known location to
read and write sprint state.

### 2.7 Verify setup

After all scripts complete, verify the bootstrap succeeded:

```bash
# Count labels
echo "Labels: $(gh label list --limit 200 | wc -l)"

# Count milestones
echo "Milestones: $(gh api repos/{owner}/{repo}/milestones | jq length)"

# Count issues
echo "Issues: $(gh issue list --limit 200 | wc -l)"

# Check project board exists
gh project list --owner <org>

# Check CI workflow exists
ls -la .github/workflows/ci.yml
```

Expected counts depend on your project configuration:
- **Labels:** Sum of persona + sprint + saga + priority + kanban + type labels
- **Milestones:** One per sprint (read from backlog/)
- **Issues:** One per story across all milestone files
- **Project board:** 1 with 6 columns (kanban stages)
- **CI workflow:** present at `.github/workflows/ci.yml`

If any count is off, re-run the corresponding script. They are idempotent and will
create only what is missing.

---

## Step 3: Post-Setup

Setup is complete. The GitHub repo now has:

- A full label taxonomy matching the backlog structure
- Milestones for all sprints defined in backlog/
- GitHub issues for all stories with labels, milestones, and full requirements
- A project board with kanban columns for workflow tracking
- CI enforcing project-specific checks on every PR (driven by project.toml)
- Sprint tracking files ready for `sprint-run` to populate

### Next steps

1. **Start Sprint 1:** Invoke `sprint-run` to begin the first sprint. It will
   move stories to the Todo column, assign work, and orchestrate implementation
   through the superpowers agents.

2. **Enable continuous monitoring (optional):** Start the sprint monitor loop:
   ```
   /loop 5m sprint-monitor
   ```
   This checks CI status, reviews open PRs, detects blocked issues, and reports
   velocity every 5 minutes. Useful during active development to catch problems
   early.

---

## References

- `skills/sprint-setup/references/github-conventions.md` -- full label taxonomy, color codes,
  PR templates, issue templates, and branch naming conventions
- `skills/sprint-setup/references/ci-workflow-template.md` -- the complete GitHub Actions YAML
  with commentary on each step and guidance for extending it
- `backlog/milestones/` -- source of truth for sprint stories, acceptance
  criteria, and sprint assignments
- `backlog/INDEX.md` -- backlog structure, numbering conventions, and
  story format specification
- `sprint-config/project.toml` -- project configuration driving all
  bootstrap decisions (language, CI, paths)
