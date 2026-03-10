# Shippable Giles — Design Spec

**Date:** 2026-03-10
**Goal:** Get the giles plugin into a shippable state for both personal use (Rust project with existing personas/sprints) and public distribution (via jbrjake/claude-plugin-marketplace).

## Context

- Plugin is structurally complete at v0.3.0: 5 skills, 14 scripts, 76 passing tests
- All scripts are stdlib-only Python 3.10+, config-driven via `sprint-config/project.toml`
- Target project is Rust with existing persona and sprint markdown files
- Distribution is via GitHub repo linked from jbrjake/claude-plugin-marketplace

## Workstream 1: Golden-Run Test Harness

### 1A: Mock Rust Project (`tests/fixtures/mock-rust-project/`)

A toy Rust CLI called **hexwise** — takes a hex color code, finds the closest named CSS color, prints a personality-driven description.

```
$ hexwise #ff6347
Tomato (#ff6347)
  "A red that went on vacation and came back with a tan."
  Closest CSS: tomato (exact match)
  RGB: 255, 99, 71 | HSL: 9, 100%, 64%
```

**Why hexwise:**
- One crate, no dependencies — pure color math (Euclidean distance in RGB space)
- Deterministic input/output, no I/O beyond stdin/stdout
- Two natural milestones:
  - M1 Core: parse hex, compute nearest CSS color, print result (3 stories)
  - M2 Polish: fun descriptions, `--format json`, error handling (3 stories)

**Dev team (3 personas):**

| Name | Role | Voice |
|------|------|-------|
| Rusti | Lead / Architect | Precise, idiomatic-Rust enthusiast. Cares about zero-copy and `clippy::pedantic`. |
| Palette | Feature Dev | Creative, user-focused. Thinks about CLI UX and delightful output. |
| Checker | QA / Reviewer | Skeptical, thorough. Writes the edge case tests everyone else forgets. |

**Fixture contents:**
- `Cargo.toml` with crate metadata
- `src/lib.rs` and `src/main.rs` (minimal stubs)
- `docs/team/` — 3 persona markdown files + INDEX.md
- `docs/backlog/milestones/` — 2 milestone files with story tables
- `docs/rules.md` and `docs/development.md`
- Initialized `.git` (no remote)

### 1B: FakeGitHub Extension

Extend the existing `FakeGitHub` mock (from `test_lifecycle.py`) to cover the full sprint lifecycle:
- Issue creation, assignment, label application
- PR creation, review submission, merge
- Milestone progress queries
- CI check status queries

### 1C: LLM Response Recorder

During the first live golden run, capture every LLM interaction at skill-phase granularity:

```
tests/golden/recordings/
  manifest.json              # run metadata, phase ordering
  01-kickoff.json            # kickoff ceremony responses
  02-story-HEX-001.json     # implementation + review per story
  03-story-HEX-002.json
  ...
  NN-demo.json               # demo ceremony
  NN-retro.json              # retro ceremony
```

Each recording captures:
- Input: prompt/context Claude received (skill content, file state, persona)
- Output: Claude's response (code, PR descriptions, review comments, ceremony output)
- Metadata: skill phase, persona, ordering

### 1D: Replay Harness

Test runner that:
1. Sets up mock Rust project from fixtures
2. Patches `gh` calls via FakeGitHub
3. Feeds recorded LLM responses instead of calling Claude live
4. Asserts file mutations, tracking updates, and GitHub API calls match golden state
5. Detects regressions when SKILL.md changes alter orchestration behavior

## Workstream 2: Progressive Disclosure Refactor

Each SKILL.md becomes a concise decision tree (~60-80 lines) that routes to focused reference files read on-demand.

**Pattern:**
- Phase detection / routing logic stays inline (it's the router)
- Procedural details move to reference files that Claude reads when needed
- Ceremony reference files already exist — stop duplicating, start pointing

**Per-skill scope:**
- `sprint-setup` — biggest win, heavy inline procedure moves to references
- `sprint-run` — route to existing ceremony-*.md files, extract story-execution.md
- `sprint-monitor` — light touch, already concise
- `sprint-release` — gate logic inline, release flow to reference
- `sprint-teardown` — likely fine as-is

## Workstream 3: README & Onboarding

**Target audience:** Someone discovering giles through the plugin marketplace.

**Structure:**
1. One-liner — agile sprints with persona-driven development in Claude Code
2. 30-second demo — annotated terminal transcript of sprint kickoff
3. Prerequisites — Claude Code, GitHub repo, `gh` CLI authenticated
4. Quickstart — install, run sprint-setup, what to expect, first sprint-run
5. Skill reference — one paragraph per skill with when to use it
6. Configuration — link to project.toml template, key sections explained
7. FAQ — common issues (no personas found, missing gh auth, etc.)

## Workstream 4: Distribution Hygiene

- Verify plugin.json has correct metadata for marketplace
- Ensure .gitignore covers .DS_Store, sprint-config/, .pytest_cache/
- Confirm LICENSE is present and correct (MIT)
- Tag release after all workstreams complete

## Approach

Outside-in (Approach A) with mock project from Approach C:

1. Build hexwise fixture + extended FakeGitHub
2. Run live golden run, record LLM responses at skill-phase level
3. Build replay harness from recordings
4. Progressive disclosure refactor of SKILL.md files
5. Expand test coverage (new tests + golden replay)
6. README and onboarding rewrite
7. Distribution hygiene and release tag

## Success Criteria

- `sprint-setup` runs end-to-end against hexwise fixture without errors
- `sprint-run` completes at least one full sprint cycle (kickoff through retro)
- Golden replay tests pass deterministically with no live LLM calls
- All SKILL.md files under 100 lines, routing to reference docs
- README gets a new user from install to first sprint kickoff
- All existing 76 tests continue passing
