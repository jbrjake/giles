# giles

Agile sprint orchestration plugin for Claude Code. Runs sprints with persona-based
development — fictional team members implement stories, review PRs, and run
ceremonies in character.

## Prerequisites

Before installing giles, make sure you have:

- **Claude Code** — [claude.ai/code](https://claude.ai/code)
- **GitHub CLI** — installed and authenticated (`gh auth login`)
- **Git** — with a GitHub remote configured
- **Python 3.10+** — for scripts (stdlib only, no pip packages needed)
- **Superpowers plugin** — install with `claude plugin add anthropic/superpowers`

## Install

```bash
claude plugin add jbrjake/giles
```

Available from [jbrjake/claude-plugin-marketplace](https://github.com/jbrjake/claude-plugin-marketplace).

## Prepare Your Project

giles auto-detects your project structure, but works best when you have:

### Team Personas

Markdown files with these headings (one file per persona):

```markdown
# Persona Name

## Role
Senior Engineer

## Voice
Direct and technical.

## Domain
Backend systems.

## Background
10 years experience.

## Review Focus
Performance and correctness.
```

### Sprint Backlog

Milestone docs with story tables:

```markdown
# Sprint 1: Walking Skeleton

### Sprint 1: Foundation

| US-0101 | Basic setup | S01 | 3 | P0 |
| US-0102 | Core feature | S01 | 5 | P1 |
```

Columns: Story ID | Title | Saga | Story Points | Priority

### Optional Files

- **Rules doc** — project conventions and constraints
- **Development guide** — dev process documentation
- **Architecture doc** — system design reference

## First Run

1. **Setup** — run the `sprint-setup` skill. It will:
   - Auto-detect your project and generate `sprint-config/`
   - Create GitHub labels, milestones, and issues
   - Generate a CI workflow

2. **Sprint** — run the `sprint-run` skill. It will:
   - Run a kickoff ceremony with persona assignments
   - Execute stories with TDD and in-persona PR reviews
   - Run demo and retrospective ceremonies

## Lifecycle

```
sprint-setup → sprint-run (repeat per sprint) → sprint-release → sprint-teardown
```

- **sprint-setup** — one-time project bootstrap
- **sprint-run** — kickoff, stories, demo, retro (repeats each sprint)
- **sprint-monitor** — continuous CI/PR/burndown checks (use with `/loop 5m`)
- **sprint-release** — gate validation, versioning, GitHub Release
- **sprint-teardown** — safe removal of sprint-config/

## Commit Conventions

giles enforces [conventional commits](https://www.conventionalcommits.org/) via
`scripts/commit.py`. All skills use this wrapper instead of raw `git commit`.

```
feat: add user authentication
fix(parser): handle empty input
feat!: redesign API (breaking change)
```

Versions are auto-calculated from the commit log at release time:
- `feat:` → minor bump
- `fix:` → patch bump
- `!` or `BREAKING CHANGE:` → major bump
- Base version: `0.1.0` if no semver tags exist

## License

MIT
