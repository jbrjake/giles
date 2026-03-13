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
| 456 | `get_prd_dir()` | PRD directory path from config (optional) |
| 465 | `get_test_plan_dir()` | Test plan directory path from config (optional) |
| 474 | `get_sagas_dir()` | Sagas directory path from config (optional) |
| 483 | `get_epics_dir()` | Epics directory path from config (optional) |
| 492 | `get_story_map()` | Story map file path from config (optional) |

### scripts/sprint_init.py
| Line | Function | Purpose |
|------|----------|---------|
| 35 | `RICH_PERSONA_HEADINGS` | Headings that signal a rich persona file |
| 60 | `ScanResult` | Dataclass with all detected fields |
| 89 | `ProjectScanner` | Auto-detects language, personas, milestones, rules, deep docs |
| 265 | `detect_persona_files()` | Persona files with rich-heading confidence scoring |
| 328 | `_walk_dirs()` | Walk directories up to max_depth for deep doc detection |
| 340 | `detect_prd_dir()` | Find PRD directory |
| 357 | `detect_test_plan_dir()` | Find test plan directory |
| 366 | `detect_sagas_dir()` | Find sagas directory |
| 375 | `detect_epics_dir()` | Find epics directory |
| 384 | `detect_story_map()` | Find story map file |
| 397 | `detect_team_topology()` | Find team topology file |
| 458 | `ProjectScanner.scan()` | Run full project scan |
| 492 | `ConfigGenerator` | Generates sprint-config/ from scan results |
| 673 | `_inject_giles()` | Copy Giles skeleton into sprint-config/team/ (not symlinked) |
| 736 | `generate_definition_of_done()` | Copy DoD skeleton into sprint-config/ |
| 741 | `generate_history_dir()` | Create team/history/ directory for Sprint History |
| 748 | `ConfigGenerator.generate()` | Execute generation |
| 770 | `print_scan_results()` | Human-readable scan output |

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
| 160 | `create_saga_labels()` | Create saga labels from backlog INDEX.md |
| 171 | `create_static_labels()` | Priority, kanban, type labels |
| 200 | `create_epic_labels()` | Create labels for epics from epics directory |
| 211 | `create_milestones_on_github()` | One GitHub milestone per milestone file |
| 253 | `main()` | Entry point: labels, milestones, epic labels |

### skills/sprint-setup/scripts/populate_issues.py
| Line | Function | Purpose |
|------|----------|---------|
| 21 | `Story` | Dataclass: story_id, title, saga, sp, priority, sprint, ACs |
| 59 | `_DEFAULT_ROW_RE` | Default regex for story table rows (optional Epic column) |
| 85 | `parse_milestone_stories()` | Extract stories from all milestone files |
| 127 | `_infer_sprint_number()` | Guess sprint number from filename |
| 146 | `_DETAIL_BLOCK_RE` | Regex for `### US-XXXX: title` detail block headers |
| 147 | `_META_ROW_RE` | Regex for `| key | value |` metadata rows in detail blocks |
| 150 | `parse_detail_blocks()` | Parse `### US-XXXX` detail sections into Story objects |
| 200 | `enrich_from_epics()` | Enrich stories with ACs, deps, test cases from epic files |
| 234 | `get_existing_issues()` | Fetch existing story IDs for idempotency |
| 254 | `get_milestone_numbers()` | Fetch milestone name-to-number mapping from GitHub |
| 267 | `_build_milestone_title_map()` | Map sprint num to milestone title (by content) |
| 297 | `format_issue_body()` | Build GitHub issue body markdown (structured sections) |
| 337 | `create_issue()` | Create single GitHub issue with labels + milestone |

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

### scripts/sprint_analytics.py
| Line | Function | Purpose |
|------|----------|---------|
| 56 | `find_milestone()` | Find GitHub milestone by sprint number |
| 70 | `extract_sp()` | Extract story points from labels or body |
| 87 | `extract_persona()` | Extract persona name from labels |
| 96 | `compute_velocity()` | Planned vs delivered SP for a milestone |
| 133 | `compute_review_rounds()` | Review events per PR in a milestone |
| 181 | `compute_workload()` | Stories per persona from issue labels |
| 204 | `format_report()` | Markdown analytics entry for one sprint |
| 239 | `main()` | CLI: compute + append to analytics.md |

### skills/sprint-monitor/scripts/check_status.py
| Line | Function | Purpose |
|------|----------|---------|
| 49 | `detect_sprint()` | Read current sprint from SPRINT-STATUS.md |
| 62 | `check_ci()` | Check recent workflow runs for failures |
| 118 | `check_prs()` | Check open PRs: stale, needs review, approved |
| 194 | `check_milestone()` | Milestone progress: SP done vs total |
| 258 | `check_branch_divergence()` | Detect branches far behind base (>10/20 commits) |
| 296 | `check_direct_pushes()` | Detect non-merge commits pushed to base branch |
| 335 | `write_log()` | Append timestamped entry to monitor log |

### scripts/team_voices.py
| Line | Function | Purpose |
|------|----------|---------|
| 24 | `VOICE_PATTERN` | Regex: `> **Name:** "text"` (colon inside bold markers) |
| 29 | `extract_voices()` | Scan saga/epic dirs, return `{persona: [{file, section, quote}]}` |
| 49 | `_extract_from_file()` | Extract voice blocks from a single markdown file |
| 83 | `main()` | CLI: load config, extract, print voice index |

### scripts/traceability.py
| Line | Function | Purpose |
|------|----------|---------|
| 22 | `STORY_HEADING` | Regex: `### US-XXXX: title` |
| 24 | `TEST_CASE_HEADING` | Regex: `### TC-*/GP-*: title` |
| 25 | `REQ_TABLE_ROW` | Regex: `\| REQ-* \| US-* \|` table rows |
| 29 | `parse_stories()` | Extract story IDs + test case links from epic files |
| 76 | `parse_test_cases()` | Extract TC/GP IDs from test plan files |
| 97 | `parse_requirements()` | Extract REQ-* IDs from PRD reference files |
| 122 | `build_traceability()` | Build bidirectional maps, find gaps |
| 165 | `format_report()` | Markdown traceability report |
| 198 | `main()` | CLI: load config, build report, print |

### scripts/test_coverage.py
| Line | Function | Purpose |
|------|----------|---------|
| 21 | `_TEST_PATTERNS` | Language-specific test function regexes (Rust/Python/JS/Go) |
| 29 | `_TEST_FILE_PATTERNS` | Language-specific test file globs |
| 40 | `parse_planned_tests()` | Extract TC/GP IDs from test plan files |
| 58 | `detect_test_functions()` | Find test function names in source code by language |
| 66 | `scan_project_tests()` | Walk project tree, find all test files and functions |
| 90 | `check_test_coverage()` | Compare planned vs actual, return coverage report |
| 118 | `format_report()` | Markdown coverage report |
| 146 | `main()` | CLI: load config, check coverage, print |

### scripts/manage_epics.py
| Line | Function | Purpose |
|------|----------|---------|
| 26 | `parse_epic()` | Parse epic file: metadata + stories list + raw sections |
| 53 | `_parse_header_table()` | Epic-level metadata table (Saga, Stories, Total SP) |
| 72 | `_parse_stories()` | All `### US-XXXX` sections with metadata, ACs, tasks |
| 136 | `_format_story_section()` | Format story data dict as markdown section |
| 188 | `add_story()` | Append new story section to epic file |
| 203 | `remove_story()` | Remove story section by ID |
| 233 | `reorder_stories()` | Reorder story sections to match given ID list |
| 276 | `renumber_stories()` | Replace story ID references (for splits) |
| 287 | `main()` | CLI: add, remove, reorder, renumber subcommands |

### scripts/manage_sagas.py
| Line | Function | Purpose |
|------|----------|---------|
| 31 | `parse_saga()` | Parse saga file: metadata + epic index + sprint allocation |
| 60 | `_parse_header_table()` | Saga-level metadata table |
| 75 | `_parse_epic_index()` | Epic Index table (ID, name, stories, SP) |
| 97 | `_parse_sprint_allocation()` | Sprint Allocation table |
| 118 | `_find_section_ranges()` | Line ranges for each ## section |
| 137 | `update_sprint_allocation()` | Rewrite Sprint Allocation table |
| 169 | `update_epic_index()` | Recalculate Epic Index from epic files |
| 224 | `update_team_voices()` | Update Team Voices blockquote section |
| 247 | `main()` | CLI: update-allocation, update-index, update-voices |

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
| 23 | Config and prerequisites |
| 29 | Phase detection (reads SPRINT-STATUS.md) |
| 44 | Phase 1: Sprint kickoff (INTERACTIVE) |
| 50 | Phase 2: Story execution (AUTONOMOUS per-story) |
| 54 | Mid-sprint check-in (Giles presents if check-in file exists) |
| 62 | Story Dispatch (kanban state table) |
| 75 | Context Assembly for Agent Dispatch (includes insights.md) |
| 98 | Insights injection for implementer dispatch |
| 105 | Insights injection for reviewer dispatch |
| 109 | Phase 3: Sprint demo (INTERACTIVE) |
| 115 | Phase 4: Sprint retro (INTERACTIVE) |

### skills/sprint-monitor/SKILL.md
| Line | Section |
|------|---------|
| 46 | Step 0: Sync backlog (debounce + throttle) |
| 69 | Step 1: Check CI status |
| 103 | Step 1.5: Drift detection (branch divergence + direct pushes) |
| 133 | Step 2: Check open PRs |
| 182 | Step 2.5: Mid-sprint check-in (threshold-triggered Giles ceremony) |
| 223 | Step 3: Update burndown |
| 246 | Step 4: Report |
| 266 | Rate limiting and deduplication |

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
| 44 | Giles rules (always facilitator, never implementer/reviewer) |
| 56 | PM persona role clarification |

### skills/sprint-run/references/ceremony-kickoff.md
| Line | Section |
|------|---------|
| 10 | Facilitation: Giles/PM split |
| 20 | Sprint theme (hardening, feature, star-vehicle, ensemble) |
| 34 | Agenda: opening, team read, saga context, goal, story walk, risks, questions, commitment |
| 41 | Team Read: distill personas into insights.md |
| 61 | Saga context step (renumbered 1.7) |
| 78 | Process context (Giles reads analytics before story walk) |
| 108 | Motivation awareness in story walk |
| 141 | Confidence check (Giles reads the room) |
| 161 | Scope negotiation (value/dependency 2x2) |
| 198 | Output template (kickoff.md) |
| 231 | Exit criteria |

### skills/sprint-run/references/ceremony-demo.md
| Line | Section |
|------|---------|
| 11 | Facilitation: Giles/PM split |
| 17 | Ensemble framing (star-vehicle vs ensemble time allocation) |
| 28 | Per-story flow: context, live demo, AC verification, Q&A |
| 37 | Live demonstration requirements (real artifacts) |
| 54 | Acceptance verification procedure |
| 65 | Test plan verification (if test plan configured) |
| 75 | Team Q&A (Giles manages flow, insights awareness, confidence probing) |
| 81 | Insights in Q&A: call on personas about protected domains |
| 102 | Output template (demo.md) |
| 133 | Rules (no incomplete stories, artifact links required) |

### skills/sprint-run/references/ceremony-retro.md
| Line | Section |
|------|---------|
| 14 | Facilitation: Giles facilitates, PM participates as team member |
| 25 | Psychological safety framing |
| 30 | Insights in psychological safety: acknowledge emotional impact |
| 39 | Start / Stop / Continue format (Giles manages turn-taking) |
| 60 | Feedback distillation (identify patterns, propose doc changes) |
| 84 | PRD feedback loop (retro can update PRD open questions) |
| 90 | User approval gate |
| 95 | Apply changes to project docs |
| 101 | Sprint analytics (run sprint_analytics.py, Giles adds commentary) |
| 118 | Write Sprint History (Giles appends per-persona entries) |
| 136 | Emotional shift tracking in history entries |
| 141 | Definition of Done review (Giles proposes retro-driven additions) |
| 153 | Examples of retro-driven doc changes |
| 171 | Output template (retro.md) |
| 210 | Rules (must produce at least one doc change) |

### skills/sprint-run/references/story-execution.md
| Line | Section |
|------|---------|
| 12 | TODO --> DESIGN (read PRDs, create branch, design notes) |
| 46 | Commit convention |
| 59 | DESIGN --> DEVELOPMENT (TDD via superpowers) |
| 81 | DEVELOPMENT --> REVIEW (PR ready, dispatch reviewer) |
| 100 | Pair Review (SP >= 5 + multi-domain, dual reviewer dispatch) |
| 120 | REVIEW --> INTEGRATION (CI green, squash-merge) |
| 146 | Parallel dispatch for independent stories |

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
character. Sections: Strategic Context :31, Test Plan Context :34, Sprint History :37,
Motivation Context :49 (insights.md distillation), Context Management :57
(budget guidance for large stories), Design :124, Implement with TDD :128,
Progressive Disclosure Docs :139, Confidence :106 (self-rated per area in PR
template), Conventions Checklist :185.

### skills/sprint-run/agents/reviewer.md
Dispatched after implementation. Different persona from implementer. Three-pass
review: correctness, conventions, testing (each pass focused, not all-at-once).
Reads confidence section from PR to prioritize scrutiny. Posts review via
`gh pr review` with persona header. Reads own + implementer's Sprint History
for callbacks. Sections: Sprint History :11, Motivation insights :17, Read PR :29,
Three-Pass Review :39 (confidence reading :41, Pass 1 correctness :54, Pass 2
conventions :61, Pass 3 testing :71), Test Coverage Verification :84, Post
Review :95, Commit Format :123.

## Skeleton templates

All in `references/skeletons/`. Used by `sprint_init.py` when project files
are missing. 19 templates: 9 core + 10 deep-doc.

| Template | Creates |
|----------|---------|
| `project.toml.tmpl` | Config file with [project], [paths], [ci], [conventions] |
| `team-index.md.tmpl` | Team INDEX.md with persona table |
| `persona.md.tmpl` | Persona profile: Role, Domain, Voice, Review Focus, Background |
| `giles.md.tmpl` | Built-in scrum master persona (fully written, not TODO-filled) |
| `backlog-index.md.tmpl` | Backlog INDEX.md with saga table |
| `milestone.md.tmpl` | Milestone file with sprint sections and story tables |
| `rules.md.tmpl` | Project rules and conventions |
| `development.md.tmpl` | Development process guide |
| `definition-of-done.md.tmpl` | Evolving DoD (mechanical baseline + retro-driven semantic) |
| `saga.md.tmpl` | Saga: goal, team voices, epic list |
| `epic.md.tmpl` | Epic: user stories table, ACs, dependencies |
| `story-detail.md.tmpl` | Detailed story block with metadata table |
| `prd-index.md.tmpl` | PRD index: links to PRD section files |
| `prd-section.md.tmpl` | PRD section: requirements, design, open questions |
| `test-plan-index.md.tmpl` | Test plan index: golden paths, functional, adversarial |
| `golden-path.md.tmpl` | Golden path test case template |
| `test-case.md.tmpl` | Test case template: steps, expected, edge cases |
| `story-map-index.md.tmpl` | Story map: activities, user steps, stories |
| `team-topology.md.tmpl` | Team topology: interaction modes, boundaries |

## Config structure

```
sprint-config/
  project.toml          -- [project], [paths], [ci], [conventions], [release]
  definition-of-done.md -- evolving DoD (baseline + retro-driven additions)
  team/INDEX.md          -- Name | File | Role | Domain Keywords
  team/{name}.md         -- persona profiles (often symlinks)
  team/giles.md          -- built-in scrum master (copied, not symlinked)
  team/history/          -- Sprint History files (written by Giles during retro)
  backlog/INDEX.md       -- saga routing table
  backlog/milestones/    -- one .md per milestone with story tables
  rules.md               -- project conventions (often symlink)
  development.md         -- dev process guide (often symlink)
```

Required TOML keys: `project.name`, `project.repo`, `project.language`,
`paths.team_dir`, `paths.backlog_dir`, `paths.sprints_dir`,
`ci.check_commands`, `ci.build_command`.

Optional deep-doc keys: `paths.prd_dir`, `paths.test_plan_dir`, `paths.sagas_dir`,
`paths.epics_dir`, `paths.story_map`, `paths.team_topology`, `paths.feedback_dir`.

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
| Add skeleton template | `references/skeletons/<name>.tmpl`, wire in `sprint_init.py:748` (ConfigGenerator.generate) |
| Change story ID pattern | `populate_issues.py:58` (_DEFAULT_ROW_RE), or set [backlog] story_id_pattern in TOML |
| Add deep doc support | Set optional paths in TOML (`prd_dir`, `test_plan_dir`, `sagas_dir`, `epics_dir`, `story_map`, `team_topology`). Context Assembly in sprint-run SKILL.md:65 handles injection. |
