# 0a: Project Overview

**Project:** giles
**Language:** Python 3.10+ (stdlib only at runtime)
**Type:** Claude Code plugin for agile sprints with persona-based development
**Structure:** Skills (SKILL.md entry points) -> Scripts (Python) -> validate_config (foundation)

## Architecture

- 5 skills: sprint-setup, sprint-run, sprint-monitor, sprint-release, sprint-teardown
- 25 production Python scripts, 4 hook scripts, 18 test files
- Central hub: `scripts/validate_config.py` (~1200 LOC) -- imported by 20+ scripts
- State management: local tracking files (YAML frontmatter) synced to GitHub via `gh` CLI
- Two-path mutation: kanban.py (transitions), sync_tracking.py (reconciliation)
- Hooks: independent subsystem (commit_gate, review_gate, session_context, verify_agent_output)

## Key Boundaries (Integration Audit Targets)

1. **validate_config <-> kanban**: shared TF dataclass, read_tf/write_tf, KANBAN_STATES
2. **kanban <-> sync_tracking**: dual write paths to same tracking files, lock_sprint coordination
3. **hooks <-> validate_config**: hooks have INDEPENDENT mini TOML parsers (not shared)
4. **sync_backlog <-> bootstrap_github + populate_issues**: cross-skill import coupling
5. **TOML parsers**: THREE independent TOML parsers exist:
   - validate_config.parse_simple_toml() -- full parser
   - hooks/verify_agent_output._read_toml_key() -- minimal array/string parser
   - hooks/session_context._read_toml_string() -- minimal string parser
   - hooks/review_gate._get_base_branch() -- inline regex parser

## Risk Signals

- **Triple TOML parser divergence**: Three independent parsers reading the same file format. Divergence is the #1 integration risk.
- **High churn in hooks**: test_hooks.py (19 changes in 50 commits), commit_gate.py (10 changes)
- **Working tree state comparison**: commit_gate uses git diff HEAD hash -- fragile against concurrent edits
- **Shell=True in verify_agent_output**: subprocess.run with shell=True for check_commands
