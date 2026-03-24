# Step 0a: Project Overview

**Run:** 6
**Date:** 2026-03-23

## Project

giles — Claude Code plugin for agile sprints with persona-based development.
Language: Python (stdlib-only for users, dev deps for testing).
31 production scripts (6984 LOC scripts/ + 1260 hooks/ + 1545 skills/*/scripts/ = ~9789 LOC production).
17 test files (~21191 LOC tests).
Test-to-production ratio: ~2.2:1.

## Structure

- `scripts/` (20 files) — shared business logic, validate_config.py is the hub (1247 LOC)
- `hooks/` (5 files + __init__) — independent subsystem with _common.py foundation
- `skills/*/scripts/` (6 files) — skill-specific scripts
- `tests/` (17 files) — pytest, hypothesis, fake_github, golden_replay
- `references/skeletons/` — 20 .tmpl files for scaffolding
- `skills/` — 5 skills with SKILL.md entry points

## Changes Since Run 5

**Zero code commits since Run 5.** The codebase is identical to the state audited in Run 5. All findings from runs 1-5 (22 total) have been resolved.

Most recent code changes (last 5 commits before run 5 artifacts):
- `ce946e0` feat: lint inventory check (new script + tests) — closes PAT-001 gap
- `ae2104e` fix: hooks in Makefile lint, gh wrapper invariant (BH-001, BH-002)
- `7b47c24` fix: integration entry guard and forced-done warning (SF-002, SF-003)
- `ae4fa33` fix: entry semantics for kanban state transitions
- `a475497` chore: Holtz run 4 artifacts

## Global Pattern Heuristic Results

| Pattern | Hits | Assessment |
|---------|------|-----------|
| code-fence-unaware-parsing | 27 | ~10 in production code regex on `content`/`body`/`text` vars. Worth checking if any parse markdown with embedded code fences. |
| dual-parser-divergence | 29 | PAT-003/004 resolved. Remaining parsers are distinct (TOML, markdown tables, YAML frontmatter, story IDs). No new duplicates. |
| regex-newline-leak | 40+ | Many `\s*`/`\s+` uses. Several on multi-line content (body, text). Worth auditing `validate_config.py:866` and `populate_issues.py:249`. |
| incomplete-layer-isolation | (not run) | Known: `gh()` wrapper with documented exception for auth check. |
| missing-edge-case-handling | (deferred to Phase 3) | Many dict accesses; assessed in prior runs. |
| doc-spec-drift | (deferred to Phase 1) | Doc audit covers this. |

## Architecture

Unchanged from baseline. Five layers: Skills → Skill scripts → Shared scripts → validate_config → Hooks (independent).
One documented exception: sync_backlog cross-skill import.
Hub: validate_config.py (imported by 20 of 25 production scripts).
