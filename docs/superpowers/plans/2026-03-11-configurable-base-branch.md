# Configurable Base Branch Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make all git/GitHub operations use a configurable base branch instead of hardcoding `main`, and make every CLI call in agent templates explicit.

**Architecture:** Add `base_branch` to `[project]` in project.toml (defaulting to `main`). Thread it through every skill doc and script that references a branch. Replace all implicit "do X on GitHub" prose in agent templates with exact `gh` commands. Add a helper `get_base_branch(config)` to validate_config.py for scripts.

**Tech Stack:** Python 3.10+ stdlib, gh CLI, Markdown templates

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `scripts/validate_config.py` | Modify | Add `get_base_branch()` helper |
| `references/skeletons/project.toml.tmpl` | Modify | Add `base_branch` key to `[project]` |
| `scripts/sprint_init.py` | Modify | Auto-detect current branch, write to config |
| `skills/sprint-setup/scripts/setup_ci.py` | Modify | Read `base_branch` from config for CI trigger |
| `skills/sprint-run/agents/implementer.md` | Modify | Use `{base_branch}`, add explicit gh commands |
| `skills/sprint-run/references/story-execution.md` | Modify | Use `{base_branch}`, add explicit gh commands |
| `skills/sprint-release/SKILL.md` | Modify | Replace hardcoded `main` with config value |
| `skills/sprint-monitor/SKILL.md` | Modify | Already uses `{merge_strategy}`, just audit |
| `tests/test_gh_interactions.py` | Modify | Add test for `get_base_branch()` |
| `tests/test_hexwise_setup.py` | Modify | Verify CI yaml uses configured branch |
| `CLAUDE.md` | Modify | Document `base_branch` in config section |
| `CHEATSHEET.md` | Modify | Update line numbers |

---

## Chunk 1: Config layer + CI generation

### Task 1: Add `get_base_branch()` helper to validate_config.py

**Files:**
- Modify: `scripts/validate_config.py` (after `get_ci_commands()` around line 441)
- Test: `tests/test_gh_interactions.py`

- [ ] **Step 1: Write failing test for `get_base_branch()`**

Add to `tests/test_gh_interactions.py`:

```python
class TestGetBaseBranch(unittest.TestCase):
    def test_returns_configured_branch(self):
        config = {"project": {"base_branch": "develop"}}
        from validate_config import get_base_branch
        self.assertEqual(get_base_branch(config), "develop")

    def test_defaults_to_main(self):
        config = {"project": {"name": "test"}}
        from validate_config import get_base_branch
        self.assertEqual(get_base_branch(config), "main")

    def test_empty_string_defaults_to_main(self):
        config = {"project": {"base_branch": ""}}
        from validate_config import get_base_branch
        self.assertEqual(get_base_branch(config), "main")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m unittest tests.test_gh_interactions.TestGetBaseBranch -v`
Expected: FAIL — `ImportError` or `AttributeError` (function doesn't exist)

- [ ] **Step 3: Implement `get_base_branch()`**

Add after `get_ci_commands()` in `scripts/validate_config.py`:

```python
def get_base_branch(config: dict) -> str:
    """Return the base branch from config, defaulting to 'main'."""
    branch = config.get("project", {}).get("base_branch", "main")
    return branch if branch else "main"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m unittest tests.test_gh_interactions.TestGetBaseBranch -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add scripts/validate_config.py tests/test_gh_interactions.py
git commit -m "feat: add get_base_branch() helper with main default"
```

---

### Task 2: Add `base_branch` to project.toml template and sprint_init.py

**Files:**
- Modify: `references/skeletons/project.toml.tmpl`
- Modify: `scripts/sprint_init.py` (ConfigGenerator, around line 440-460)

- [ ] **Step 1: Add `base_branch` to skeleton template**

In `references/skeletons/project.toml.tmpl`, add after the `language` line:

```toml
base_branch = "main"          # branch that PRs target and CI watches
```

- [ ] **Step 2: Add `base_branch` to sprint_init.py ConfigGenerator**

In `scripts/sprint_init.py`, in the `[project]` section generation (around line 440-445), add a line that auto-detects the current branch:

```python
# After the language line, add:
# Detect current branch for base_branch default
try:
    result = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True, text=True, check=True)
    current_branch = result.stdout.strip()
except (subprocess.CalledProcessError, FileNotFoundError):
    current_branch = "main"
lines.append(f'base_branch = "{current_branch}"')
```

Also add `import subprocess` to the top of the file if not already present.

- [ ] **Step 3: Run full test suite**

Run: `.venv/bin/python -m unittest discover -s tests -v`
Expected: all 108+ tests PASS (no behavioral change yet)

- [ ] **Step 4: Commit**

```bash
git add references/skeletons/project.toml.tmpl scripts/sprint_init.py
git commit -m "feat: add base_branch to project.toml template with auto-detection"
```

---

### Task 3: Thread `base_branch` through setup_ci.py

**Files:**
- Modify: `skills/sprint-setup/scripts/setup_ci.py:220-223`
- Modify: `tests/test_hexwise_setup.py`

- [ ] **Step 1: Write failing test**

Add to `tests/test_hexwise_setup.py`:

```python
def test_ci_workflow_uses_configured_branch(self):
    """setup_ci uses base_branch from config instead of hardcoded main."""
    config = self._generate_config()
    config["project"]["base_branch"] = "develop"
    sys.path.insert(0, str(_REPO_ROOT / "skills" / "sprint-setup" / "scripts"))
    from setup_ci import generate_ci_yaml
    yaml_content = generate_ci_yaml(config)
    self.assertIn("branches: [develop]", yaml_content)
    self.assertNotIn("branches: [main]", yaml_content)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m unittest tests.test_hexwise_setup.TestHexwiseSetup.test_ci_workflow_uses_configured_branch -v`
Expected: FAIL — still contains `branches: [main]`

- [ ] **Step 3: Update `generate_ci_yaml()` to read `base_branch`**

In `skills/sprint-setup/scripts/setup_ci.py`, in `generate_ci_yaml()`, change lines 220-223 from:

```python
        "  push:",
        "    branches: [main]",
        "  pull_request:",
        "    branches: [main]",
```

to:

```python
        "  push:",
        f"    branches: [{base_branch}]",
        "  pull_request:",
        f"    branches: [{base_branch}]",
```

And at the top of `generate_ci_yaml()`, add:

```python
    base_branch = config.get("project", {}).get("base_branch", "main")
```

- [ ] **Step 4: Run tests to verify pass**

Run: `.venv/bin/python -m unittest tests.test_hexwise_setup -v`
Expected: all hexwise tests PASS (existing test still works because default is `main`)

- [ ] **Step 5: Commit**

```bash
git add skills/sprint-setup/scripts/setup_ci.py tests/test_hexwise_setup.py
git commit -m "feat: setup_ci reads base_branch from config for CI triggers"
```

---

## Chunk 2: Explicit CLI commands in agent templates

### Task 4: Rewrite implementer.md with explicit commands and `{base_branch}`

**Files:**
- Modify: `skills/sprint-run/agents/implementer.md`

Every GitHub operation must be an explicit `gh` or `git` command. Replace all prose like "Open a draft PR" with the actual command. Use `{base_branch}` instead of `main`.

- [ ] **Step 1: Replace branch creation (line 35)**

Change:
```bash
git checkout -b {branch_name} main
```
to:
```bash
git checkout -b {branch_name} {base_branch}
```

- [ ] **Step 2: Add explicit PR creation command after line 36**

Replace "Open a draft PR with full context." with:

```bash
git push -u origin {branch_name}
gh pr create --draft --base {base_branch} --head {branch_name} \
  --title "{story_id}: {story_title}" \
  --body "$(cat <<'EOF'
> **{persona_name}** · {persona_role} · Implementation

## Story
**{story_id}** — {story_title} | Sprint {sprint_number} | {sp} SP | {priority}

## Acceptance Criteria
{acceptance_criteria}

## PRD Context
{relevant_prd_excerpts}

## Design Decisions
{design_notes}
EOF
)"
```

- [ ] **Step 3: Add explicit commands to section 5 "Push and Mark Ready" (lines 65-76)**

Replace the prose with explicit commands:

```bash
# Push all commits
git push origin {branch_name}

# Mark PR as ready for review
gh pr ready {pr_number}

# Add reviewer persona label
gh pr edit {pr_number} --add-label "persona:{reviewer_name}"

# Update story tracking file status
# (edit {sprints_dir}/sprint-{N}/stories/{story_file} — set status: review)

# Update GitHub issue label
gh issue edit {issue_number} --remove-label "kanban:dev" --add-label "kanban:review"
```

- [ ] **Step 4: Add explicit commands to section 6 "Respond to Review Feedback" (lines 78-84)**

Replace prose with:

```bash
# Push fixes
git push origin {branch_name}

# Re-request review
gh pr edit {pr_number} --add-reviewer {reviewer_github_handle}
```

- [ ] **Step 5: Verify file renders correctly, commit**

```bash
git add skills/sprint-run/agents/implementer.md
git commit -m "feat: explicit gh commands in implementer agent, use {base_branch}"
```

---

### Task 5: Rewrite story-execution.md with explicit commands and `{base_branch}`

**Files:**
- Modify: `skills/sprint-run/references/story-execution.md`

- [ ] **Step 1: Add explicit commands to TO-DO --> DESIGN (lines 17-29)**

After "Create branch using the pattern from config", add:

```bash
git checkout -b {branch_name} {base_branch}
git push -u origin {branch_name}
```

After "Open a draft PR", add:

```bash
gh pr create --draft --base {base_branch} --head {branch_name} \
  --title "{story_id}: {story_title}" \
  --body "{pr_description}"
```

After "Apply labels", add:

```bash
gh pr edit {pr_number} --add-label "persona:{persona},sprint:{N},saga:{saga},priority:{pri},kanban:design"
gh issue edit {issue_number} --remove-label "kanban:todo" --add-label "kanban:design"
```

- [ ] **Step 2: Add explicit commands to DESIGN --> DEVELOPMENT (lines 60-61)**

After "Push commits to the branch. Mark PR as ready for review.", add:

```bash
git push origin {branch_name}
gh pr ready {pr_number}
gh issue edit {issue_number} --remove-label "kanban:design" --add-label "kanban:dev"
```

- [ ] **Step 3: Rewrite REVIEW --> INTEGRATION (lines 86-96)**

Replace prose with explicit commands:

```bash
# 1. Confirm CI green
gh pr checks {pr_number} --watch

# 2. Run verification
# (invoke superpowers:verification-before-completion)

# 3. Squash-merge to base branch
gh pr merge {pr_number} --squash --delete-branch

# 4. Close the GitHub issue
gh issue close {issue_number}

# 5. Update burndown
python skills/sprint-run/scripts/update_burndown.py

# 6-7. Update tracking files
# (edit story file: status = done, completion_date = today)
# (update SPRINT-STATUS.md)

# 8. Update GitHub issue label
gh issue edit {issue_number} --remove-label "kanban:review" --add-label "kanban:done"
```

Note: line 91 changes from "Squash-merge the PR to main" to `gh pr merge` (which targets the PR's base branch automatically — already set to `{base_branch}` at creation time).

- [ ] **Step 4: Commit**

```bash
git add skills/sprint-run/references/story-execution.md
git commit -m "feat: explicit gh commands in story-execution, remove hardcoded main"
```

---

### Task 6: Update sprint-release/SKILL.md to use `{base_branch}`

**Files:**
- Modify: `skills/sprint-release/SKILL.md:32-35, 221`

- [ ] **Step 1: Replace line 32-35**

Change:
```markdown
2. **CI passing on main.** Run:
   ```bash
   gh run list --branch main --limit 1
   ```
```
to:
```markdown
2. **CI passing on base branch.** Read `base_branch` from `project.toml [project] base_branch` (default: `main`). Run:
   ```bash
   gh run list --branch {base_branch} --limit 1
   ```
```

- [ ] **Step 2: Replace line 221**

Change:
```bash
gh run list --branch main --limit 1 --json databaseId --jq '.[0].databaseId'
```
to:
```bash
gh run list --branch {base_branch} --limit 1 --json databaseId --jq '.[0].databaseId'
```

- [ ] **Step 3: Commit**

```bash
git add skills/sprint-release/SKILL.md
git commit -m "feat: sprint-release uses {base_branch} instead of hardcoded main"
```

---

### Task 7: Update docs (CLAUDE.md, CHEATSHEET.md)

**Files:**
- Modify: `CLAUDE.md`
- Modify: `CHEATSHEET.md`

- [ ] **Step 1: Add `base_branch` to CLAUDE.md config docs**

In the "Configuration System" section, add `base_branch` to the Required TOML keys note (or note it as optional with default). In the project.toml structure comment, add: `# base_branch = "main"  — branch PRs target (default: main)`.

- [ ] **Step 2: Update CHEATSHEET.md line numbers**

Update any line number references that shifted due to edits in earlier tasks. Add `get_base_branch()` to the validate_config.py function index.

- [ ] **Step 3: Run full test suite**

Run: `.venv/bin/python -m unittest discover -s tests -v`
Expected: all tests PASS

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md CHEATSHEET.md
git commit -m "docs: document base_branch config, update line refs"
```
