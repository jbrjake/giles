# Ship Giles: Bugfix + Contract Enforcement + Eval Update

**Date:** 2026-03-09
**Goal:** Get the giles plugin into a shippable state by fixing all identified bugs, preventing the root cause from recurring, and making evals project-agnostic.

## Context

Full audit of the giles plugin revealed 5 bugs (2 critical, 2 moderate, 1 design), plus stale evals. The plugin is structurally complete (3,400+ lines of Python, 14 reference docs, 7 templates, 5 skills) but the auto-init path is broken — the config generator produces output that fails its own validation.

The target user has a Rust project with existing team personas and backlog docs. The critical path is: `sprint_init.py` scan -> generate config -> validate -> bootstrap GitHub.

## Bug Fixes

### Bug 1: `sprint_init.py` generates incompatible config (CRITICAL)

**Root cause:** `ConfigGenerator.generate_project_toml()` was written with different section/key names than what `validate_config.py` requires.

**What's wrong:**
- Generates `[build] command` — validator expects `[ci] build_command`
- Generates `[ci] steps` — validator expects `[ci] check_commands`
- Missing `[paths]` section entirely (no `team_dir`, `backlog_dir`, `sprints_dir`)
- Missing `[conventions]` section

**Fix:** Rewrite `generate_project_toml()` to produce output matching `_REQUIRED_TOML_KEYS`:
- `[project]` with `name`, `repo`, `language`
- `[paths]` with `team_dir`, `backlog_dir`, `sprints_dir` (and optional `rules_file`, `dev_guide`, `cheatsheet`, `architecture`)
- `[ci]` with `check_commands` (array) and `build_command` (string)
- `[conventions]` with `branch_pattern`, `commit_style`, `merge_strategy`

**Files:** `scripts/sprint_init.py` (ConfigGenerator.generate_project_toml, ~lines 424-448)

### Bug 2: Generated team INDEX.md missing Role column (CRITICAL)

**Root cause:** `ConfigGenerator.generate_team()` creates `Name | File | Confidence` but `_parse_team_index()` expects `Name | Role | File`.

**Fix:**
- Change generated columns to `Name | Role | File`
- Infer Role from persona file content: look for `## Role` heading and extract the first line after it
- If Role can't be inferred, use "Team Member" as fallback
- Drop the Confidence column (internal signal, not useful in the output)

**Files:** `scripts/sprint_init.py` (ConfigGenerator.generate_team, ~lines 450-467)

### Bug 3: Superpowers plugin check path wrong (MODERATE)

**Root cause:** `sprint-setup/SKILL.md` hardcodes a path that doesn't match actual plugin install location.

**Fix:** Replace the specific path check with a command that searches common plugin locations:
```bash
find ~/.claude/plugins -name "superpowers" -type d 2>/dev/null | head -1
```
Or better: check for the presence of superpowers skills by looking for its SKILL.md files.

**Files:** `skills/sprint-setup/SKILL.md` (~line 91)

### Bug 4: Doc lint job hardcodes `.rs` file extension (MODERATE)

**Root cause:** `_docs_lint_job()` in setup_ci.py checks `*.md` and `*.rs` regardless of project language.

**Fix:** Make `_docs_lint_job()` accept a language parameter and pick extensions dynamically:
- Rust: `.md`, `.rs`
- Python: `.md`, `.py`
- Node/TypeScript: `.md`, `.ts`, `.tsx`, `.js`
- Go: `.md`, `.go`
- Default: `.md` only

**Files:** `skills/sprint-setup/scripts/setup_ci.py` (_docs_lint_job, ~line 160)

### Bug 5: Duplicate test job in generated CI (MODERATE)

**Root cause:** `generate_ci_yaml()` creates individual check jobs for every command in `check_commands`, then also creates a separate test matrix job for any command containing "test". If `cargo test` is in `check_commands`, it runs twice.

**Fix:** When generating check jobs, skip commands that `_find_test_command()` will pick up for the matrix test job. The test matrix job is more valuable (cross-OS) so it should win.

**Files:** `skills/sprint-setup/scripts/setup_ci.py` (generate_ci_yaml, ~line 186)

## Contract Enforcement

### Self-validation in generator

After `ConfigGenerator.generate()` writes all files, call `validate_project()` on the generated `sprint-config/` directory. If validation fails, print the errors and exit with a clear message: "Generated config failed self-validation. This is a bug in sprint_init.py."

This catches any future drift between the generator and validator at generation time rather than at first use.

**Files:** `scripts/sprint_init.py` (ConfigGenerator.generate and/or main)

## Design Fix

### Agent frontmatter

Add YAML frontmatter to both agent template files. These are prompt templates with `{placeholder}` syntax, not standalone auto-discovered agents. The frontmatter makes them visible to Claude Code's agent discovery while preserving their template nature.

**implementer.md:**
```yaml
---
name: implementer
description: Story implementation subagent — TDD, PR creation, and in-persona development. Dispatched by sprint-run for each story in the sprint.
---
```

**reviewer.md:**
```yaml
---
name: reviewer
description: Code review subagent — in-persona PR review with checklist validation. Dispatched by sprint-run after implementation is complete.
---
```

**Files:** `skills/sprint-run/agents/implementer.md`, `skills/sprint-run/agents/reviewer.md`

## Eval Update

### Make evals project-agnostic

Current evals reference "Dreamcatcher project", "Rachel", "cargo build", and other project-specific details. Update to use generic descriptions that work against any configured project.

**Changes:**
- Replace "Dreamcatcher" with "the configured project" or similar generic phrasing
- Replace persona names with role descriptions ("the PM persona", "team members")
- Replace `cargo build` / `cargo test` with "the build command from project.toml" / "the check commands"
- Keep the same 6 eval scenarios — they cover the right phases

**Files:** `evals/evals.json`

## Files Changed (Summary)

| File | Change Type |
|------|------------|
| `scripts/sprint_init.py` | Bug fixes #1, #2 + self-validation |
| `skills/sprint-setup/SKILL.md` | Bug fix #3 |
| `skills/sprint-setup/scripts/setup_ci.py` | Bug fixes #4, #5 |
| `skills/sprint-run/agents/implementer.md` | Add frontmatter |
| `skills/sprint-run/agents/reviewer.md` | Add frontmatter |
| `evals/evals.json` | Make project-agnostic |

## Out of Scope

- No new features or skills
- No changes to validate_config.py (it's correct — the generator was wrong)
- No changes to skeleton templates (they already have the correct schema)
- No changes to sprint-run, sprint-monitor, sprint-release, or sprint-teardown skills
- No venv changes (intentional design decision for Python version consistency)

## Verification

After all fixes:
1. `python3 -m py_compile` passes on all 9 scripts
2. Running `sprint_init.py` on a test directory produces config that passes `validate_config.py`
3. Generated team INDEX.md has Name | Role | File columns
4. Generated CI YAML has no duplicate test jobs
5. Doc lint job uses language-appropriate extensions
6. Agent files have valid YAML frontmatter
7. Evals contain no project-specific references
