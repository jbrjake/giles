# Shippable Giles v0.5 — Test Infrastructure & CI

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make all 90 tests discoverable with one command, add CI for the plugin itself, and consolidate test organization so regressions are caught automatically on every push.

**Architecture:** Move the two test files from `scripts/` into `tests/`, fix their import paths, add a local venv pinned to Python 3.10, add a `Makefile` with a single `make test` target, and create a GitHub Actions workflow that runs the full suite on push/PR. No framework changes — stay on stdlib `unittest`.

**Tech Stack:** Python 3.10 (venv, stdlib only, unittest), GNU Make, GitHub Actions

---

## Current State (v0.4.0)

- 90 tests across 4 files — **all pass**
- Hexwise end-to-end pipeline: **fully working**
- Golden recording/replay: **working**
- Test files split across two directories:
  - `tests/` — 14 tests (test_hexwise_setup.py, test_golden_run.py)
  - `scripts/` — 76 tests (test_gh_interactions.py, test_lifecycle.py)
- `python -m unittest discover` from root: **finds 0 tests**
- `python -m unittest discover -s tests`: **finds only 14 tests**
- No CI workflow for giles itself
- No unified test command
- No venv — tests run against whatever system Python is available

## File Structure

| Action | File | Purpose |
|--------|------|---------|
| Create | `.python-version` | Pin Python 3.10 for pyenv |
| Create | `Makefile` | venv setup + single `make test` entry point |
| Move | `scripts/test_gh_interactions.py` → `tests/test_gh_interactions.py` | Consolidate tests |
| Move | `scripts/test_lifecycle.py` → `tests/test_lifecycle.py` | Consolidate tests |
| Modify | `tests/test_gh_interactions.py` | Fix sys.path imports after move |
| Modify | `tests/test_lifecycle.py` | Fix sys.path imports after move |
| Modify | `.gitignore` | Add `.venv/` |
| Create | `.github/workflows/ci.yml` | Run tests on push/PR |

---

## Chunk 1: Venv & Consolidate Tests

### Task 0: Set up local venv with pinned Python version

**Files:**
- Create: `.python-version`
- Modify: `.gitignore`

- [ ] **Step 1: Create `.python-version`**

```
3.10
```

This tells pyenv to use Python 3.10 in this directory. The `from __future__ import annotations` usage across the codebase targets 3.10 as the minimum.

- [ ] **Step 2: Install Python 3.10 if needed**

```bash
pyenv install 3.10 --skip-existing
```

- [ ] **Step 3: Create the venv**

```bash
python3 -m venv .venv
```

- [ ] **Step 4: Add `.venv/` to `.gitignore`**

Append `.venv/` to the existing `.gitignore` if not already present.

- [ ] **Step 5: Verify the venv Python version**

```bash
.venv/bin/python --version
```

Expected: `Python 3.10.x`

- [ ] **Step 6: Commit**

```bash
git add .python-version .gitignore
git commit -m "chore: pin Python 3.10 via .python-version, add .venv to gitignore"
```

### Task 1: Move test_gh_interactions.py

**Files:**
- Move: `scripts/test_gh_interactions.py` → `tests/test_gh_interactions.py`
- Modify: `tests/test_gh_interactions.py` (fix import paths)

- [ ] **Step 1: Move the file**

```bash
git mv scripts/test_gh_interactions.py tests/test_gh_interactions.py
```

- [ ] **Step 2: Fix sys.path imports**

The file currently sets `SCRIPTS_DIR = Path(__file__).resolve().parent` (which was `scripts/`), then uses `SCRIPTS_DIR.parent / "skills" / ...` to reach skill scripts.

After moving to `tests/`, the file's parent is `tests/`, not `scripts/`. The fix:

1. Change `SCRIPTS_DIR` to compute the **project root**, then add `scripts/` explicitly:

```python
# Before (lines 23-24):
SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))

# After:
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
```

2. Update all `SCRIPTS_DIR.parent / "skills"` references to `ROOT / "skills"`:

```python
# Before (e.g. line 28-30):
sys.path.insert(0, str(
    SCRIPTS_DIR.parent / "skills" / "sprint-release" / "scripts"
))

# After:
sys.path.insert(0, str(
    ROOT / "skills" / "sprint-release" / "scripts"
))
```

Apply the same `SCRIPTS_DIR.parent` → `ROOT` change for all four skill path blocks:
- `ROOT / "skills" / "sprint-release" / "scripts"` (release_gate)
- `ROOT / "skills" / "sprint-monitor" / "scripts"` (check_status)
- `ROOT / "skills" / "sprint-setup" / "scripts"` (bootstrap_github, populate_issues)
- `ROOT / "skills" / "sprint-run" / "scripts"` (sync_tracking, update_burndown)

The actual import statements (`from commit import ...`, `from release_gate import ...`, etc.) stay the same — only the paths change.

Actual imports this file uses (for verification):
- `scripts/commit.py` — `validate_message`, `check_atomicity`
- `skills/sprint-release/scripts/release_gate.py` — `determine_bump`, `bump_version`, `calculate_version`, `find_latest_semver_tag`, `parse_commits_since`, `write_version_to_toml`, `generate_release_notes`, `gate_stories`, `gate_ci`, `gate_prs`, `validate_gates`, `print_gate_summary`
- `skills/sprint-monitor/scripts/check_status.py` — module import
- `skills/sprint-setup/scripts/bootstrap_github.py` — module import
- `skills/sprint-setup/scripts/populate_issues.py` — module import
- `skills/sprint-run/scripts/sync_tracking.py` — module import
- `skills/sprint-run/scripts/update_burndown.py` — module import

- [ ] **Step 3: Update the docstring run command (line 11)**

```python
# Before:
# Run: python scripts/test_gh_interactions.py -v

# After:
# Run: python -m unittest tests.test_gh_interactions -v
```

- [ ] **Step 4: Run the moved file to verify all 63 tests pass**

```bash
.venv/bin/python -m unittest tests.test_gh_interactions -v
```

Expected: 63 tests, all OK.

- [ ] **Step 5: Commit**

```bash
git add tests/test_gh_interactions.py
git commit -m "refactor: move test_gh_interactions.py to tests/ directory"
```

### Task 2: Move test_lifecycle.py

**Files:**
- Move: `scripts/test_lifecycle.py` → `tests/test_lifecycle.py`
- Modify: `tests/test_lifecycle.py` (fix import paths)

- [ ] **Step 1: Move the file**

```bash
git mv scripts/test_lifecycle.py tests/test_lifecycle.py
```

- [ ] **Step 2: Fix sys.path imports**

The file currently uses two base variables:
```python
SCRIPTS_DIR = Path(__file__).resolve().parent  # was scripts/
PLUGIN_ROOT = SCRIPTS_DIR.parent               # was project root
```

After moving to `tests/`, `SCRIPTS_DIR.parent` would be the project root anyway, but `SCRIPTS_DIR` itself is now `tests/` not `scripts/`. The fix:

```python
# Before (lines 22-25):
SCRIPTS_DIR = Path(__file__).resolve().parent
PLUGIN_ROOT = SCRIPTS_DIR.parent
sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, str(PLUGIN_ROOT / "tests"))

# After:
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
```

The `sys.path.insert(0, str(PLUGIN_ROOT / "tests"))` line is no longer needed — `fake_github.py` is now in the same directory as the test file, so `from fake_github import ...` works directly.

Update all `PLUGIN_ROOT / "skills"` references to `ROOT / "skills"`:
- `ROOT / "skills" / "sprint-release" / "scripts"` (release_gate)
- `ROOT / "skills" / "sprint-setup" / "scripts"` (bootstrap_github, populate_issues)
- `ROOT / "skills" / "sprint-run" / "scripts"` (update_burndown)

Actual imports this file uses (for verification):
- `scripts/validate_config.py` — `parse_simple_toml`, `validate_project`
- `scripts/sprint_init.py` — `ProjectScanner`, `ConfigGenerator`
- `scripts/commit.py` — `validate_message`, `check_atomicity`
- `tests/fake_github.py` — `FakeGitHub`, `make_patched_subprocess` (now same directory)
- `skills/sprint-release/scripts/release_gate.py` — `determine_bump`, `bump_version`, `write_version_to_toml`, `generate_release_notes`
- `skills/sprint-setup/scripts/bootstrap_github.py` — module import
- `skills/sprint-setup/scripts/populate_issues.py` — module import
- `skills/sprint-run/scripts/update_burndown.py` — module import

- [ ] **Step 3: Update the docstring run command (line 8)**

```python
# Before:
# Run: python scripts/test_lifecycle.py -v

# After:
# Run: python -m unittest tests.test_lifecycle -v
```

- [ ] **Step 4: Run the moved file to verify all 13 tests pass**

```bash
.venv/bin/python -m unittest tests.test_lifecycle -v
```

Expected: 13 tests, all OK.

- [ ] **Step 5: Commit**

```bash
git add tests/test_lifecycle.py
git commit -m "refactor: move test_lifecycle.py to tests/ directory"
```

### Task 3: Verify unified test discovery

- [ ] **Step 1: Run full discovery from project root**

```bash
.venv/bin/python -m unittest discover -s tests -v
```

Expected: 90 tests found and all pass. The output should include tests from all 4 files:
- `test_gh_interactions` (63)
- `test_lifecycle` (13)
- `test_hexwise_setup` (13)
- `test_golden_run` (1)

- [ ] **Step 2: Verify no leftover test files in scripts/**

```bash
ls scripts/test_*.py
```

Expected: No files found (both moved).

- [ ] **Step 3: Commit (if any fixups needed)**

Only if additional fixes were required to pass discovery.

---

## Chunk 2: Makefile & CI

### Task 4: Create Makefile

**Files:**
- Create: `Makefile`

- [ ] **Step 1: Write the Makefile**

```makefile
VENV := .venv
PYTHON := $(VENV)/bin/python

.PHONY: test test-unit test-integration test-golden lint venv help

venv: $(VENV)/bin/activate  ## Create local venv (Python 3.10)

$(VENV)/bin/activate:
	python3 -m venv $(VENV)
	@echo "venv created at $(VENV)/"

test: venv  ## Run all tests
	$(PYTHON) -m unittest discover -s tests -v

test-unit: venv  ## Run only fast unit tests
	$(PYTHON) -m unittest tests.test_gh_interactions -v

test-integration: venv  ## Run lifecycle + hexwise integration tests
	$(PYTHON) -m unittest tests.test_lifecycle tests.test_hexwise_setup -v

test-golden: venv  ## Run golden recording replay
	$(PYTHON) -m unittest tests.test_golden_run -v

test-golden-record: venv  ## Re-record golden snapshots
	GOLDEN_RECORD=1 $(PYTHON) -m unittest tests.test_golden_run -v

lint: venv  ## Check Python syntax (stdlib only, no linter deps)
	$(PYTHON) -m py_compile scripts/validate_config.py
	$(PYTHON) -m py_compile scripts/sprint_init.py
	$(PYTHON) -m py_compile scripts/sprint_teardown.py
	$(PYTHON) -m py_compile scripts/commit.py
	$(PYTHON) -m py_compile skills/sprint-setup/scripts/bootstrap_github.py
	$(PYTHON) -m py_compile skills/sprint-setup/scripts/populate_issues.py
	$(PYTHON) -m py_compile skills/sprint-setup/scripts/setup_ci.py
	$(PYTHON) -m py_compile skills/sprint-run/scripts/sync_tracking.py
	$(PYTHON) -m py_compile skills/sprint-run/scripts/update_burndown.py
	$(PYTHON) -m py_compile skills/sprint-monitor/scripts/check_status.py
	$(PYTHON) -m py_compile skills/sprint-release/scripts/release_gate.py

clean:  ## Remove venv and __pycache__
	rm -rf $(VENV) **/__pycache__

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'
```

- [ ] **Step 2: Verify `make test` runs all 90**

```bash
make test
```

Expected: Creates venv if needed, then 90 tests, all OK.

- [ ] **Step 3: Verify `make lint` passes**

```bash
make lint
```

Expected: No output (all files compile cleanly).

- [ ] **Step 4: Commit**

```bash
git add Makefile
git commit -m "feat: add Makefile with venv, test, and lint targets"
```

### Task 5: Create GitHub Actions CI workflow

**Files:**
- Create: `.github/workflows/ci.yml`

- [ ] **Step 1: Create the workflow directory**

```bash
mkdir -p .github/workflows
```

- [ ] **Step 2: Write the CI workflow**

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.10", "3.11", "3.12"]

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python ${{ matrix.python-version }}
        uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}

      - name: Create venv
        run: python -m venv .venv

      - name: Lint (syntax check)
        run: make lint

      - name: Run tests
        run: make test
```

Note: No `pip install` step needed — all scripts are stdlib-only. The `setup-python` action provides the matrix version; `make` targets use `.venv/bin/python` which inherits from it.

- [ ] **Step 3: Verify YAML is valid**

```bash
python3 -c "
with open('.github/workflows/ci.yml') as f:
    content = f.read()
    assert 'on:' in content
    assert 'make test' in content
    assert 'python-m venv' not in content  # catch typos
    print('CI workflow looks valid')
"
```

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: add GitHub Actions workflow for tests on Python 3.10-3.12"
```

### Task 6: Final verification

- [ ] **Step 1: Clean and rebuild venv to test from scratch**

```bash
make clean && make test
```

Expected: venv recreated, 90 tests pass.

- [ ] **Step 2: Verify project is clean**

```bash
git status
```

Expected: Clean working tree (`.venv/` and `__pycache__/` in `.gitignore`).

- [ ] **Step 3: Tag release**

```bash
git tag -a v0.5.0 -m "v0.5.0: unified test suite, venv, CI, Makefile"
```

Hold on pushing/tagging until user confirms.

---

## What This Does NOT Cover (and why)

| Omission | Reason |
|----------|--------|
| pytest migration | Stdlib unittest works fine, no need for a dependency |
| pyproject.toml | No packages to install, Makefile + .python-version is sufficient |
| Coverage reporting | Can add later; 90 tests already cover the critical paths |
| Evals runner | evals.json is for Claude Code's eval framework, not something we invoke directly |
| Agent registration in plugin.json | Agents are referenced inline from SKILL.md — this is the correct pattern for subagent templates |
| New features | This plan is infrastructure-only — making what exists shippable |
