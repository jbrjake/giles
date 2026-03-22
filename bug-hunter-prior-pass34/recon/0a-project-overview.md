# Recon 0a — Project Overview (scoped to 16 recent commits)

## Scope
16 commits since d974641, adding 2,838 lines across 28 files.

## New Subsystems
1. **Plugin hooks** (4 files in `.claude-plugin/hooks/`): commit gate, review gate, session context injection, agent output verification
2. **Utility scripts** (6 files in `scripts/`): smoke test runner, gap scanner, test category analyzer, risk register, DoD level assigner, history-to-checklist converter
3. **Kanban extensions** (1 modified file): WIP limits, review round counter with escalation, transition log

## Modified Integration Points
- `check_status.py`: added smoke check + integration debt tracking
- `sync_tracking.py`: added verification section template to create_from_issue
- `tracking-formats.md`: documented new fields
- Ceremony docs: added smoke gates, gap scan, structural encoding, standing questions
- Agent docs: added verification scope, raw evidence, review checklist items

## Key Architectural Observations
- Hooks deliberately avoid importing validate_config.py (lightweight, inline TOML parsing)
- New scripts follow project convention (sys.path.insert, load_config from validate_config)
- Kanban changes add parameters to do_transition() (force_review_round, force_wip, sprints_dir, sprint)
- Integration debt metric exists in monitor output but NOT in SPRINT-STATUS.md (format doc is ahead of implementation)
