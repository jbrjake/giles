# Giles Cheatsheet

Quick-reference index with line numbers. Grep for section headers to find what
you need without reading entire files.

## Skill lifecycle

`sprint-setup` --> `sprint-run` (per sprint) --> `sprint-release` (at milestone end) --> `sprint-teardown`

`sprint-monitor` runs alongside `sprint-run` via `/loop 5m sprint-monitor`.

## Scripts -- function index

### scripts/validate_config.py
| Line | Function | Purpose |
|------|----------|---------|
| 21 | `parse_simple_toml()` | Custom TOML parser (no tomllib dep) |
| 164 | `_REQUIRED_FILES` | List of files config dir must contain |
| 177 | `_REQUIRED_TOML_KEYS` | Required keys: project.name, project.repo, etc. |
| 188 | `_REQUIRED_TOML_SECTIONS` | project, paths, ci |
| 191 | `validate_project()` | Full config validation, returns error list |
| 300 | `_parse_team_index()` | Parse team/INDEX.md table |
| 368 | `load_config()` | Load + validate, returns dict |
| 398 | `get_team_personas()` | Personas from team/INDEX.md |
| 426 | `get_milestones()` | Milestone file paths from config |
| 441 | `get_ci_commands()` | CI check commands from [ci] section |
| 450 | `get_base_branch()` | Base branch from config, defaults to 'main' |

### scripts/sprint_init.py
| Line | Function | Purpose |
|------|----------|---------|
| 79 | `ProjectScanner` | Auto-detects language, personas, milestones, rules |
| 349 | `ProjectScanner.scan()` | Run full project scan |
| 380 | `ConfigGenerator` | Generates sprint-config/ from scan results |
| 499 | `ConfigGenerator.generate()` | Execute generation |
| 584 | `print_scan_results()` | Human-readable scan output |

### scripts/sprint_teardown.py
| Line | Function | Purpose |
|------|----------|---------|
| 19 | `classify_entries()` | Sort config entries: symlinks, generated, unknown |
| 190 | `remove_symlinks()` | Delete symlinks, leave originals intact |
| 203 | `remove_generated()` | Delete generated files (with --force flag) |
| 285 | `check_active_loops()` | Warn about running /loop instances |
| 331 | `print_github_cleanup_hints()` | Show manual GitHub cleanup steps |

### skills/sprint-setup/scripts/bootstrap_github.py
| Line | Function | Purpose |
|------|----------|---------|
| 55 | `create_label()` | Create single label (idempotent, --force) |
| 78 | `create_persona_labels()` | Labels from team/INDEX.md |
| 91 | `_collect_sprint_numbers()` | Scan milestone files for ### Sprint N: sections |
| 113 | `create_sprint_labels()` | One label per sprint found across all milestones |
| 125 | `_parse_saga_labels_from_backlog()` | Parse saga IDs from backlog/INDEX.md |
| 171 | `create_static_labels()` | Priority, kanban, type labels |
| 200 | `create_milestones_on_github()` | One GitHub milestone per milestone file |

### skills/sprint-setup/scripts/populate_issues.py
| Line | Function | Purpose |
|------|----------|---------|
| 21 | `Story` | Dataclass: story_id, title, saga, sp, priority, sprint, ACs |
| 84 | `parse_milestone_stories()` | Extract stories from all milestone files |
| 126 | `_infer_sprint_number()` | Guess sprint number from filename |
| 151 | `enrich_from_epics()` | Add user stories, ACs, deps from epic files |
| 205 | `get_existing_issues()` | Fetch existing story IDs for idempotency |
| 238 | `_build_milestone_title_map()` | Map sprint num to milestone title (by content) |
| 268 | `format_issue_body()` | Build GitHub issue body markdown |
| 298 | `create_issue()` | Create single GitHub issue with labels + milestone |

### skills/sprint-setup/scripts/setup_ci.py
| Line | Function | Purpose |
|------|----------|---------|
| 20 | `_rust_setup_steps()` | Rust toolchain + cache steps |
| 29 | `_python_setup_steps()` | Python setup steps |
| 41 | `_node_setup_steps()` | Node.js setup (default 22) |
| 51 | `_go_setup_steps()` | Go setup steps |
| 60 | `_SETUP_REGISTRY` | Language -> setup function mapping |
| 74 | `_ENV_BLOCKS` | Per-language env vars (CARGO_TERM_COLOR, etc.) |
| 160 | `_LANG_EXTENSIONS` | File extensions per language (for doc lint) |
| 202 | `generate_ci_yaml()` | Build complete workflow YAML from config |

### skills/sprint-run/scripts/sync_tracking.py
| Line | Function | Purpose |
|------|----------|---------|
| 27 | `KANBAN_STATES` | Tuple of 6 states: todo..done |
| 39 | `find_milestone_title()` | Look up milestone title by sprint number |
| 103 | `extract_story_id()` | Parse US-XXXX from issue title |
| 108 | `kanban_from_labels()` | Derive kanban state from GitHub labels |
| 137 | `TF` | Tracking file dataclass (story metadata) |
| 153 | `read_tf()` | Parse YAML frontmatter from story file |
| 176 | `write_tf()` | Write story file with frontmatter |
| 201 | `sync_one()` | Reconcile one story: GitHub vs local |
| 248 | `create_from_issue()` | Create local tracking file from GitHub issue |

### skills/sprint-run/scripts/update_burndown.py
| Line | Function | Purpose |
|------|----------|---------|
| 38 | `find_milestone()` | Find GitHub milestone for sprint number |
| 59 | `extract_sp()` | Get story points from issue labels or body |
| 77 | `kanban_status()` | Derive status from issue labels |
| 100 | `write_burndown()` | Generate burndown.md from milestone data |
| 139 | `update_sprint_status()` | Update SPRINT-STATUS.md active stories table |

### scripts/sync_backlog.py
| Line | Function | Purpose |
|------|----------|---------|
| 28 | `THROTTLE_FLOOR_SECONDS` | 600s (10 min) — minimum interval between syncs |
| 29 | `STATE_FILENAME` | `.sync-state.json` — persisted in sprint-config/ |
| 32 | `hash_milestone_files()` | SHA-256 hash each milestone file for change detection |
| 44 | `_default_state()` | Fresh state dict: file_hashes, pending_hashes, last_sync_at |
| 53 | `load_state()` | Load .sync-state.json, return defaults on missing/corrupt |
| 72 | `save_state()` | Write state as pretty-printed JSON |
| 78 | `SyncResult` | Dataclass: status, should_sync, message |
| 86 | `_is_throttled()` | Check if last sync was within throttle floor |
| 98 | `check_sync()` | Decision engine: debounce + throttle + revert detection |
| 138 | `do_sync()` | Lazy-imports bootstrap_github + populate_issues, runs sync |
| 181 | `main()` | Full cycle: load config, hash, decide, sync, save state |

### skills/sprint-monitor/scripts/check_status.py
| Line | Function | Purpose |
|------|----------|---------|
| 43 | `detect_sprint()` | Read current sprint from SPRINT-STATUS.md |
| 56 | `check_ci()` | Check recent workflow runs for failures |
| 112 | `check_prs()` | Check open PRs: stale, needs review, approved |
| 188 | `check_milestone()` | Milestone progress: SP done vs total |
| 252 | `write_log()` | Append timestamped entry to monitor log |

## Skill entry points -- section index

### skills/sprint-setup/SKILL.md
| Line | Section |
|------|---------|
| 22 | Phase 0: Project initialization |
| 32 | Step 1: Check prerequisites |
| 46 | Step 2: GitHub bootstrap (labels, milestones, issues, CI) |

### skills/sprint-run/SKILL.md
| Line | Section |
|------|---------|
| 22 | Config and prerequisites |
| 28 | Phase detection (reads SPRINT-STATUS.md) |
| 43 | Phase 1: Sprint kickoff (INTERACTIVE) |
| 49 | Phase 2: Story execution (AUTONOMOUS per-story) |
| 64 | Phase 3: Sprint demo (INTERACTIVE) |
| 70 | Phase 4: Sprint retro (INTERACTIVE) |

### skills/sprint-monitor/SKILL.md
| Line | Section |
|------|---------|
| 46 | Step 0: Sync backlog (debounce + throttle) |
| 69 | Step 1: Check CI status |
| 103 | Step 2: Check open PRs |
| 152 | Step 3: Update burndown |
| 175 | Step 4: Report |
| 195 | Rate limiting and deduplication |

### skills/sprint-release/SKILL.md
| Line | Section |
|------|---------|
| 49 | Step 1: Gate validation |
| 81 | Step 2: Tag and release |
| 102 | Step 3: Build release artifacts |
| 124 | Step 4: Create GitHub Release |
| 176 | Step 5: Post-release (close milestone, update tracking) |
| 243 | Rollback procedure |

## Reference files -- section index

### skills/sprint-run/references/kanban-protocol.md
| Line | Section |
|------|---------|
| 6 | States (6: todo, design, dev, review, integration, done) |
| 17 | Transitions (allowed state changes) |
| 28 | Rules (one story per persona in dev, 3-round review limit) |
| 47 | GitHub label sync procedure |
| 56 | WIP limits (1 dev/persona, 2 review/reviewer, 3 integration) |
| 68 | Blocked story handling |

### skills/sprint-run/references/persona-guide.md
| Line | Section |
|------|---------|
| 5 | Persona assignment rules (domain keywords) |
| 17 | Voice guidelines |
| 23 | GitHub header format for PRs and reviews |

### skills/sprint-run/references/ceremony-kickoff.md
| Line | Section |
|------|---------|
| 15 | Agenda: goal, story walk, risks, questions, commitment |
| 68 | Output template (kickoff.md) |
| 98 | Exit criteria |

### skills/sprint-run/references/ceremony-demo.md
| Line | Section |
|------|---------|
| 16 | Per-story flow: context, live demo, AC verification, Q&A |
| 25 | Live demonstration requirements (real artifacts) |
| 42 | Acceptance verification procedure |
| 60 | Output template (demo.md) |
| 85 | Rules (no incomplete stories, artifact links required) |

### skills/sprint-run/references/ceremony-retro.md
| Line | Section |
|------|---------|
| 18 | Start / Stop / Continue format |
| 36 | Feedback distillation (identify patterns, propose doc changes) |
| 57 | User approval gate |
| 62 | Apply changes to project docs |
| 68 | Examples of retro-driven doc changes |
| 82 | Output template (retro.md) |
| 119 | Rules (must produce at least one doc change) |

### skills/sprint-run/references/story-execution.md
| Line | Section |
|------|---------|
| 12 | TODO --> DESIGN (read PRDs, create branch, design notes) |
| 47 | Commit convention |
| 60 | DESIGN --> DEVELOPMENT (TDD via superpowers) |
| 83 | DEVELOPMENT --> REVIEW (PR ready, dispatch reviewer) |
| 104 | REVIEW --> INTEGRATION (CI green, squash-merge) |
| 133 | Parallel dispatch for independent stories |

### skills/sprint-run/references/tracking-formats.md
| Line | Section |
|------|---------|
| 3 | SPRINT-STATUS.md format |
| 23 | Story file format (YAML frontmatter) |
| 46 | File map (where each tracking file lives) |

### skills/sprint-setup/references/github-conventions.md
| Line | Section |
|------|---------|
| 5 | Label taxonomy (persona, sprint, saga, priority, kanban, type) |
| 44 | Issue template |
| 73 | PR template |
| 108 | PR review template |

### skills/sprint-release/references/release-checklist.md
| Line | Section |
|------|---------|
| 9 | Stories gate |
| 15 | Test gate |
| 22 | Performance gate |
| 32 | Milestone acceptance |
| 37 | Release artifacts |

## Subagent templates

### skills/sprint-run/agents/implementer.md
Dispatched per story. Receives: persona context, story assignment, requirements,
PRD context. Follows TDD, creates PR with self-contained description, stays in
character.

### skills/sprint-run/agents/reviewer.md
Dispatched after implementation. Different persona from implementer. Reviews
from PR description + diff only (validates PR description sufficiency). Posts
review via `gh pr review` with persona header.

## Skeleton templates

All in `references/skeletons/`. Used by `sprint_init.py` when project files
are missing.

| Template | Creates |
|----------|---------|
| `project.toml.tmpl` | Config file with [project], [paths], [ci], [conventions] |
| `team-index.md.tmpl` | Team INDEX.md with persona table |
| `persona.md.tmpl` | Persona profile: Role, Domain, Voice, Review Focus, Background |
| `backlog-index.md.tmpl` | Backlog INDEX.md with saga table |
| `milestone.md.tmpl` | Milestone file with sprint sections and story tables |
| `rules.md.tmpl` | Project rules and conventions |
| `development.md.tmpl` | Development process guide |

## Config structure

```
sprint-config/
  project.toml          -- [project], [paths], [ci], [conventions], [release]
  team/INDEX.md          -- Name | File | Role | Domain Keywords
  team/{name}.md         -- persona profiles (often symlinks)
  backlog/INDEX.md       -- saga routing table
  backlog/milestones/    -- one .md per milestone with story tables
  rules.md               -- project conventions (often symlink)
  development.md         -- dev process guide (often symlink)
```

Required TOML keys: `project.name`, `project.repo`, `project.language`,
`paths.team_dir`, `paths.backlog_dir`, `paths.sprints_dir`,
`ci.check_commands`, `ci.build_command`.

See `validate_config.py:177` for the full list.

## Common modifications

| Want to... | Edit |
|-----------|------|
| Add new skill | Create `skills/<name>/SKILL.md` with YAML frontmatter |
| Change config validation | `scripts/validate_config.py:164` (_REQUIRED_FILES), `:177` (_REQUIRED_TOML_KEYS) |
| Add label category | `bootstrap_github.py:171` (create_static_labels) |
| Add language to CI gen | `setup_ci.py:60` (_SETUP_REGISTRY), `:74` (_ENV_BLOCKS) |
| Add kanban state | `kanban-protocol.md:6`, `sync_tracking.py:27` (KANBAN_STATES) |
| Change tracking format | `tracking-formats.md:3`, `sync_tracking.py:137` (TF), `update_burndown.py:100` |
| Add skeleton template | `references/skeletons/<name>.tmpl`, wire in `sprint_init.py:380` (ConfigGenerator) |
| Change story ID pattern | `populate_issues.py:58` (_DEFAULT_ROW_RE), or set [backlog] story_id_pattern in TOML |
