# Tracking File Formats

<!-- §tracking-formats.sprint_status_md_format -->
<!-- §tracking-formats.sprint_status_md -->
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

## Integration Debt: 0 sprints
```

The `Integration Debt` line is populated by `sprint-monitor` (`check_status.py`),
not by `update_burndown.py`. It tracks sprints since the last smoke test pass.

<!-- §tracking-formats.story_file_yaml_frontmatter -->
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
`review`, `integration`, `done`. Local tracking files are the source of
truth for story state; `kanban.py` syncs changes to GitHub on every
mutation. Use `kanban.py sync` to accept legal external GitHub changes.

<!-- §tracking-formats.verification_section -->
## Verification Section (story file body)

New story tracking files include a verification section in the body text:

```markdown
## Verification
- agent: ["swift build", "swift test"]
- orchestrator: ["smoke_test.py"]
- unverified: ["xcodebuild", "app launch"]
```

The SubagentStop hook (verify_agent_output.py) populates `agent` automatically.
The `unverified` list is populated from the implementer's Verification Scope
section in the PR description.

<!-- §tracking-formats.transition_log -->
## Transition Log (story file body)

`kanban.py do_transition()` appends a log entry to body text on each state
change. The log is used by `_count_review_rounds()` for the 3-round
escalation limit.

```markdown
## Transition Log
- 2026-03-20T09:00: todo → design
- 2026-03-20T10:30: design → dev
- 2026-03-20T14:00: dev → review
```

Log entries are rolled back if the GitHub sync fails. External transitions
via `do_sync` or `sync_tracking` do not currently append log entries.

<!-- §tracking-formats.file_map_where_each_tracking_file_lives -->
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
