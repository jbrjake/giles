# Tracking File Formats

## SPRINT-STATUS.md

```markdown
# Project Status

## Current Sprint: 1

## Sprint Phase: development

## Velocity History

| Sprint | Planned SP | Completed SP |
|--------|-----------|-------------|

## Active Stories

| Story | Status | Assignee | PR |
|-------|--------|----------|----|
```

## Story File (YAML frontmatter)

```yaml
---
story: US-0101
title: Short description
sprint: 1
implementer: persona-slug
reviewer: persona-slug
status: dev
branch: sprint-1/US-0101-short-slug
pr_number: 3
issue_number: 1
started: 2026-03-10
completed:
---
```

The `status` field mirrors kanban states: `todo`, `design`, `dev`,
`review`, `done`. GitHub is the source of truth for story state;
`sync_tracking.py` updates local tracking files to match GitHub.
If they diverge, GitHub wins.

## File Map

Files this skill creates or updates during a sprint. All paths are
resolved from `config [paths] sprints_dir` (shown here as `{sprints_dir}`):

| File | Created | Phase |
|------|---------|-------|
| `{sprints_dir}/SPRINT-STATUS.md` | By sprint-setup | All |
| `{sprints_dir}/sprint-{N}/kickoff.md` | By this skill | Kickoff |
| `{sprints_dir}/sprint-{N}/stories/US-XXXX-slug.md` | Per story | Design |
| `{sprints_dir}/sprint-{N}/burndown.md` | Updated per story | Development |
| `{sprints_dir}/sprint-{N}/demo-artifacts/` | Demo outputs | Demo |
| `{sprints_dir}/sprint-{N}/demo.md` | By this skill | Demo |
| `{sprints_dir}/sprint-{N}/retro.md` | By this skill | Retro |
