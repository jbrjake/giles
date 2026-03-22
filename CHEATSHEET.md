# Giles Cheatsheet

Quick-reference index with §-anchor references. Grep for section headers to find
what you need without reading entire files.

## Skill lifecycle

`sprint-setup` --> `sprint-run` (per sprint) --> `sprint-release` (at milestone end) --> `sprint-teardown`

`sprint-monitor` runs alongside `sprint-run` via `/loop 5m sprint-monitor`.

## Scripts -- function index

### scripts/validate_config.py
| Anchor | Function | Purpose |
|--------|----------|---------|
| §validate_config.gh | `gh()` | Shared GitHub CLI wrapper (raises RuntimeError on failure) |
| §validate_config.gh_json | `gh_json()` | Run gh CLI and parse JSON output |
| §validate_config.parse_simple_toml | `parse_simple_toml()` | Custom TOML parser (no tomllib dep) |
| §validate_config._REQUIRED_FILES | `_REQUIRED_FILES` | List of files config dir must contain |
| §validate_config._REQUIRED_TOML_KEYS | `_REQUIRED_TOML_KEYS` | Required keys: project.name, project.repo, etc. |
| §validate_config._REQUIRED_TOML_SECTIONS | `_REQUIRED_TOML_SECTIONS` | project, paths, ci |
| §validate_config.validate_project | `validate_project()` | Full config validation, returns error list |
| §validate_config._parse_team_index | `_parse_team_index()` | Parse team/INDEX.md table |
| §validate_config.load_config | `load_config()` | Load + validate, returns dict |
| §validate_config.get_team_personas | `get_team_personas()` | Personas from team/INDEX.md |
| §validate_config.get_milestones | `get_milestones()` | Milestone file paths from config |
| §validate_config.get_ci_commands | `get_ci_commands()` | CI check commands from [ci] section |
| §validate_config.get_base_branch | `get_base_branch()` | Base branch from config, defaults to 'main' |
| §validate_config.get_sprints_dir | `get_sprints_dir()` | Sprints directory path from config (required) |
| §validate_config.get_prd_dir | `get_prd_dir()` | PRD directory path from config (optional) |
| §validate_config.get_test_plan_dir | `get_test_plan_dir()` | Test plan directory path from config (optional) |
| §validate_config.get_sagas_dir | `get_sagas_dir()` | Sagas directory path from config (optional) |
| §validate_config.get_epics_dir | `get_epics_dir()` | Epics directory path from config (optional) |
| §validate_config.extract_sp | `extract_sp()` | Shared story point extraction from labels/body |
| §validate_config.get_story_map | `get_story_map()` | Story map file path from config (optional) |
| §validate_config.detect_sprint | `detect_sprint()` | Detect current sprint number from sprints directory |
| §validate_config.extract_story_id | `extract_story_id()` | Parse US-XXXX from issue title |
| §validate_config.KANBAN_STATES | `KANBAN_STATES` | Frozenset of 6 kanban states |
| §validate_config.kanban_from_labels | `kanban_from_labels()` | Derive kanban state from GitHub labels |
| §validate_config.find_milestone | `find_milestone()` | Look up GitHub milestone by sprint number |
| §validate_config.list_milestone_issues | `list_milestone_issues()` | Fetch all issues for a milestone (shared helper) |
| §validate_config.warn_if_at_limit | `warn_if_at_limit()` | Warn if API response is at pagination limit |
| §validate_config.TABLE_ROW | `TABLE_ROW` | Regex for markdown table rows in tracking files |
| §validate_config.TF | `TF` | Dataclass for tracking file state (story, title, status, fields, body_text, path) |
| §validate_config._yaml_safe | `_yaml_safe()` | Quote values with YAML-sensitive chars (bools, colons, numerics) |
| §validate_config.read_tf | `read_tf()` | Parse tracking file from disk into TF dataclass |
| §validate_config.write_tf | `write_tf()` | Serialize TF dataclass back to disk (YAML frontmatter + body) |
| §validate_config.frontmatter_value | `frontmatter_value()` | Extract single value from YAML frontmatter by key |
| §validate_config.short_title | `short_title()` | Strip story ID prefix from title (everything after first colon) |
| §validate_config.slug_from_title | `slug_from_title()` | Convert story title to URL-safe slug for branch names |
| §validate_config.safe_int | `safe_int()` | Parse int from string with default fallback |
| §validate_config.parse_iso_date | `parse_iso_date()` | Parse ISO date string to datetime |
| §validate_config.atomic_write_text | `atomic_write_text()` | Atomic file write via temp-then-rename (used by manage_epics/sagas) |

### scripts/sprint_init.py
| Anchor | Function | Purpose |
|--------|----------|---------|
| §sprint_init.RICH_PERSONA_HEADINGS | `RICH_PERSONA_HEADINGS` | Headings that signal a rich persona file |
| §sprint_init.ScanResult | `ScanResult` | Dataclass with all detected fields |
| §sprint_init.ProjectScanner | `ProjectScanner` | Auto-detects language, personas, milestones, rules, deep docs |
| §sprint_init.ConfigGenerator | `ConfigGenerator` | Generates sprint-config/ from scan results |
| §sprint_init._indicator | `_indicator()` | Confidence indicator character |
| §sprint_init.print_scan_results | `print_scan_results()` | Human-readable scan output |
| §sprint_init.print_generation_summary | `print_generation_summary()` | Summary of generated config files |
| §sprint_init.main | `main()` | CLI entry point |

### scripts/sprint_teardown.py
| Anchor | Function | Purpose |
|--------|----------|---------|
| §sprint_teardown.classify_entries | `classify_entries()` | Sort config entries: symlinks, generated, unknown |
| §sprint_teardown.collect_directories | `collect_directories()` | Collect directories for empty-dir cleanup |
| §sprint_teardown.remove_symlinks | `remove_symlinks()` | Delete symlinks, leave originals intact |
| §sprint_teardown.remove_generated | `remove_generated()` | Delete generated files (with --force flag) |
| §sprint_teardown.remove_empty_dirs | `remove_empty_dirs()` | Remove empty directories deepest-first |
| §sprint_teardown.check_active_loops | `check_active_loops()` | Warn about running /loop instances |
| §sprint_teardown.print_github_cleanup_hints | `print_github_cleanup_hints()` | Show manual GitHub cleanup steps |
| §sprint_teardown.main | `main()` | CLI entry point |

### skills/sprint-setup/scripts/bootstrap_github.py
| Anchor | Function | Purpose |
|--------|----------|---------|
| §bootstrap_github.create_label | `create_label()` | Create single label (idempotent, --force) |
| §bootstrap_github.create_persona_labels | `create_persona_labels()` | Labels from team/INDEX.md |
| §bootstrap_github._collect_sprint_numbers | `_collect_sprint_numbers()` | Scan milestone files for ### Sprint N: sections |
| §bootstrap_github.create_sprint_labels | `create_sprint_labels()` | One label per sprint found across all milestones |
| §bootstrap_github._parse_saga_labels_from_backlog | `_parse_saga_labels_from_backlog()` | Parse saga IDs from backlog/INDEX.md |
| §bootstrap_github.create_saga_labels | `create_saga_labels()` | Create saga labels from backlog INDEX.md |
| §bootstrap_github.create_static_labels | `create_static_labels()` | Priority, kanban, type labels |
| §bootstrap_github.create_epic_labels | `create_epic_labels()` | Create labels for epics from epics directory |
| §bootstrap_github.create_milestones_on_github | `create_milestones_on_github()` | One GitHub milestone per milestone file |
| §bootstrap_github.main | `main()` | Entry point: labels, milestones, epic labels |

### skills/sprint-setup/scripts/populate_issues.py
| Anchor | Function | Purpose |
|--------|----------|---------|
| §populate_issues.Story | `Story` | Dataclass: story_id, title, saga, sp, priority, sprint, ACs |
| §populate_issues._safe_compile_pattern | `_safe_compile_pattern()` | Validate user-supplied regex is safe to compile |
| §populate_issues._build_row_regex | `_build_row_regex()` | Build/validate story table row regex from config |
| §populate_issues.parse_milestone_stories | `parse_milestone_stories()` | Extract stories from all milestone files |
| §populate_issues._infer_sprint_number | `_infer_sprint_number()` | Guess sprint number from filename (content-first) |
| §populate_issues.parse_detail_blocks | `parse_detail_blocks()` | Parse `### US-XXXX` detail sections into Story objects |
| §populate_issues.enrich_from_epics | `enrich_from_epics()` | Enrich stories with ACs, deps, test cases from epic files |
| §populate_issues.get_existing_issues | `get_existing_issues()` | Fetch existing story IDs for idempotency |
| §populate_issues.get_milestone_numbers | `get_milestone_numbers()` | Fetch milestone name-to-number mapping from GitHub |
| §populate_issues.build_milestone_title_map | `build_milestone_title_map()` | Map sprint num to milestone title (by content) |
| §populate_issues.format_issue_body | `format_issue_body()` | Build GitHub issue body markdown (structured sections) |
| §populate_issues.create_issue | `create_issue()` | Create single GitHub issue with labels + milestone |
| §populate_issues._most_common_sprint | `_most_common_sprint()` | Find most common sprint number among stories in a milestone |
| — | `_build_detail_block_re()` | Build regex for matching story detail block headers |

### skills/sprint-setup/scripts/setup_ci.py
| Anchor | Function | Purpose |
|--------|----------|---------|
| §setup_ci._rust_setup_steps | `_rust_setup_steps()` | Rust toolchain + cache steps |
| §setup_ci._python_setup_steps | `_python_setup_steps()` | Python setup steps |
| §setup_ci._node_setup_steps | `_node_setup_steps()` | Node.js setup (default 22) |
| §setup_ci._go_setup_steps | `_go_setup_steps()` | Go setup steps |
| §setup_ci._SETUP_REGISTRY | `_SETUP_REGISTRY` | Language -> setup function mapping |
| §setup_ci._ENV_BLOCKS | `_ENV_BLOCKS` | Per-language env vars (CARGO_TERM_COLOR, etc.) |
| §setup_ci._LANG_EXTENSIONS | `_LANG_EXTENSIONS` | File extensions per language (for doc lint) |
| §setup_ci.generate_ci_yaml | `generate_ci_yaml()` | Build complete workflow YAML from config |

### scripts/kanban.py
| Anchor | Function | Purpose |
|--------|----------|---------|
| §kanban.TRANSITIONS | `TRANSITIONS` | Allowed state transitions dict (source → list of targets) |
| §kanban.validate_transition | `validate_transition()` | Raise ValueError if transition is not in TRANSITIONS |
| §kanban.check_preconditions | `check_preconditions()` | Check required field preconditions before transition (implementer, branch, etc.) |
| §kanban.check_wip_limit | `check_wip_limit()` | Enforce WIP limits per state (1 dev/persona, 2 review/reviewer, 3 integration) |
| §kanban._count_review_rounds | `_count_review_rounds()` | Count review → dev transitions in the transition log |
| §kanban.append_transition_log | `append_transition_log()` | Append timestamped transition entry to tracking file body |
| §kanban.lock_story | `lock_story()` | Exclusive POSIX lock via sentinel file for per-story serialization |
| §kanban.lock_sprint | `lock_sprint()` | Exclusive POSIX lock via sentinel file for sprint-level serialization |
| §kanban.find_story | `find_story()` | Locate tracking file by story ID across sprint directories |
| §kanban.atomic_write_tf | `atomic_write_tf()` | Write tracking file atomically via temp file + rename |
| §kanban.do_transition | `do_transition()` | Validate + update tracking file + sync GitHub label |
| §kanban.do_assign | `do_assign()` | Set implementer/reviewer in tracking file + GitHub labels |
| §kanban.do_update | `do_update()` | Update individual tracking file fields (pr_number, branch, etc.) |
| §kanban.do_sync | `do_sync()` | Pull external GitHub label changes into local tracking files |
| §kanban.do_status | `do_status()` | Print kanban board (stories grouped by state) |
| §kanban.main | `main()` | CLI entry point: transition, assign, sync, status subcommands |

### skills/sprint-run/scripts/sync_tracking.py
| Anchor | Function | Purpose |
|--------|----------|---------|
| _(removed: BH21-016)_ | `find_milestone()` | Uses shared `validate_config.find_milestone()` directly |
| §sync_tracking._fetch_all_prs | `_fetch_all_prs()` | Batch-fetch all PRs (one API call for entire sync) |
| §sync_tracking.get_linked_pr | `get_linked_pr()` | Find PR linked to issue via timeline, fallback to branch |
| §sync_tracking.sync_one | `sync_one()` | Reconcile one story: GitHub vs local |
| §sync_tracking.create_from_issue | `create_from_issue()` | Create local tracking file from GitHub issue |

### skills/sprint-run/scripts/update_burndown.py
| Anchor | Function | Purpose |
|--------|----------|---------|
| §update_burndown.closed_date | `closed_date()` | Extract close date from issue data |
| §update_burndown.build_rows | `build_rows()` | Build burndown table rows from milestone issues (date, SP remaining) |
| §update_burndown.write_burndown | `write_burndown()` | Generate burndown.md from milestone data |
| §update_burndown.update_sprint_status | `update_sprint_status()` | Update SPRINT-STATUS.md active stories table |
| §update_burndown.load_tracking_metadata | `load_tracking_metadata()` | Read story tracking files for assignee/PR data |
| §update_burndown.main | `main()` | CLI entry point |

### scripts/sync_backlog.py
| Anchor | Function | Purpose |
|--------|----------|---------|
| §sync_backlog.THROTTLE_FLOOR_SECONDS | `THROTTLE_FLOOR_SECONDS` | 600s (10 min) — minimum interval between syncs |
| §sync_backlog.STATE_FILENAME | `STATE_FILENAME` | `.sync-state.json` — persisted in sprint-config/ |
| §sync_backlog.hash_milestone_files | `hash_milestone_files()` | SHA-256 hash each milestone file for change detection |
| §sync_backlog._default_state | `_default_state()` | Fresh state dict: file_hashes, pending_hashes, last_sync_at |
| §sync_backlog.load_state | `load_state()` | Load .sync-state.json, return defaults on missing/corrupt |
| §sync_backlog.save_state | `save_state()` | Write state as pretty-printed JSON |
| §sync_backlog.SyncResult | `SyncResult` | Dataclass: status, should_sync, message |
| §sync_backlog._is_throttled | `_is_throttled()` | Check if last sync was within throttle floor |
| §sync_backlog.check_sync | `check_sync()` | Decision engine: debounce + throttle + revert detection |
| §sync_backlog.do_sync | `do_sync()` | Uses bootstrap_github + populate_issues (module-level import with fallback), runs sync |
| §sync_backlog.main | `main()` | Full cycle: load config, hash, decide, sync, save state |

### scripts/sprint_analytics.py
| Anchor | Function | Purpose |
|--------|----------|---------|
| §sprint_analytics.extract_persona | `extract_persona()` | Extract persona name from labels |
| §sprint_analytics.compute_velocity | `compute_velocity()` | Planned vs delivered SP for a milestone |
| §sprint_analytics.compute_review_rounds | `compute_review_rounds()` | Review events per PR in a milestone |
| §sprint_analytics.compute_workload | `compute_workload()` | Stories per persona from issue labels |
| §sprint_analytics.format_report | `format_report()` | Markdown analytics entry for one sprint |
| §sprint_analytics.main | `main()` | CLI: compute + append to analytics.md |

### skills/sprint-monitor/scripts/check_status.py
| Anchor | Function | Purpose |
|--------|----------|---------|
| §check_status.check_ci | `check_ci()` | Check recent workflow runs for failures |
| §check_status.check_prs | `check_prs()` | Check open PRs: stale, needs review, approved |
| §check_status.check_milestone | `check_milestone()` | Milestone progress: SP done vs total |
| §check_status.check_branch_divergence | `check_branch_divergence()` | Detect branches far behind base (>10/20 commits) |
| §check_status.check_direct_pushes | `check_direct_pushes()` | Detect non-merge commits pushed to base branch |
| §check_status.check_smoke | `check_smoke()` | Run smoke test and report pass/fail/skip |
| §check_status.check_integration_debt | `check_integration_debt()` | Detect integration debt: sprints since last smoke pass |
| §check_status.write_log | `write_log()` | Append timestamped entry to monitor log |
| §check_status.main | `main()` | CLI entry point |

### scripts/team_voices.py
| Anchor | Function | Purpose |
|--------|----------|---------|
| §team_voices.VOICE_PATTERN | `VOICE_PATTERN` | Regex: `> **Name:** "text"` (colon inside bold markers) |
| §team_voices.extract_voices | `extract_voices()` | Scan saga/epic dirs, return `{persona: [{file, section, quote}]}` |
| §team_voices._extract_from_file | `_extract_from_file()` | Extract voice blocks from a single markdown file |
| §team_voices.main | `main()` | CLI: load config, extract, print voice index |

### scripts/traceability.py
| Anchor | Function | Purpose |
|--------|----------|---------|
| §traceability.STORY_HEADING | `STORY_HEADING` | Regex: `### US-XXXX: title` |
| §traceability.TEST_CASE_HEADING | `TEST_CASE_HEADING` | Regex: `### TC-*/GP-*: title` |
| §traceability.REQ_TABLE_ROW | `REQ_TABLE_ROW` | Regex: `\| REQ-* \| US-* \|` table rows |
| §traceability.parse_stories | `parse_stories()` | Extract story IDs + test case links from epic files |
| §traceability.parse_test_cases | `parse_test_cases()` | Extract TC/GP IDs from test plan files |
| §traceability.parse_requirements | `parse_requirements()` | Extract REQ-* IDs from PRD reference files |
| §traceability.build_traceability | `build_traceability()` | Build bidirectional maps, find gaps |
| §traceability.format_report | `format_report()` | Markdown traceability report |
| §traceability.main | `main()` | CLI: load config, build report, print |

### scripts/test_coverage.py
| Anchor | Function | Purpose |
|--------|----------|---------|
| §test_coverage._TEST_PATTERNS | `_TEST_PATTERNS` | Language-specific test function regexes (Rust/Python/JS/Go) |
| §test_coverage._TEST_FILE_PATTERNS | `_TEST_FILE_PATTERNS` | Language-specific test file globs |
| §test_coverage.parse_planned_tests | `parse_planned_tests()` | Extract TC/GP IDs from test plan files |
| §test_coverage.detect_test_functions | `detect_test_functions()` | Find test function names in source code by language |
| §test_coverage.scan_project_tests | `scan_project_tests()` | Walk project tree, find all test files and functions |
| §test_coverage.check_test_coverage | `check_test_coverage()` | Compare planned vs actual, return coverage report |
| §test_coverage.format_report | `format_report()` | Markdown coverage report |
| §test_coverage.main | `main()` | CLI: load config, check coverage, print |

### scripts/manage_epics.py
| Anchor | Function | Purpose |
|--------|----------|---------|
| §validate_config.safe_int | `_safe_int()` | Imported from validate_config — extract leading digits, 0 on failure |
| §manage_epics._parse_epic_from_lines | `_parse_epic_from_lines()` | Parse epic from pre-read lines (avoids TOCTOU) |
| §manage_epics.parse_epic | `parse_epic()` | Parse epic file: metadata + stories list + raw sections |
| §validate_config.parse_header_table | `parse_header_table()` | Shared metadata table parser (imported by manage_epics, manage_sagas) |
| §manage_epics._parse_stories | `_parse_stories()` | All `### US-XXXX` sections with metadata, ACs, tasks |
| §manage_epics._format_story_section | `_format_story_section()` | Format story data dict as markdown section |
| §manage_epics.add_story | `add_story()` | Append new story section to epic file |
| §manage_epics.remove_story | `remove_story()` | Remove story section by ID |
| §manage_epics.reorder_stories | `reorder_stories()` | Reorder story sections to match given ID list |
| §manage_epics.renumber_stories | `renumber_stories()` | Replace story ID references (for splits) |
| §manage_epics.main | `main()` | CLI: add, remove, reorder, renumber subcommands |

### scripts/manage_sagas.py
| Anchor | Function | Purpose |
|--------|----------|---------|
| §validate_config.safe_int | `_safe_int()` | Imported from validate_config — extract leading digits, 0 on failure |
| §manage_sagas.parse_saga | `parse_saga()` | Parse saga file: metadata + epic index + sprint allocation |
| _(see §validate_config.parse_header_table)_ | `parse_header_table()` | Imported from validate_config (BH18-012 refactor) |
| §manage_sagas._parse_epic_index | `_parse_epic_index()` | Epic Index table (ID, name, stories, SP) |
| §manage_sagas._parse_sprint_allocation | `_parse_sprint_allocation()` | Sprint Allocation table |
| §manage_sagas._find_section_ranges | `_find_section_ranges()` | Line ranges for each ## section |
| §manage_sagas.update_sprint_allocation | `update_sprint_allocation()` | Rewrite Sprint Allocation table |
| §manage_sagas.update_epic_index | `update_epic_index()` | Recalculate Epic Index from epic files |
| §manage_sagas.update_team_voices | `update_team_voices()` | Update Team Voices blockquote section |
| §manage_sagas.main | `main()` | CLI: update-allocation, update-index, update-voices |

### scripts/commit.py
| Anchor | Function | Purpose |
|--------|----------|---------|
| §commit.validate_message | `validate_message()` | Validate conventional commit format |
| §commit.check_atomicity | `check_atomicity()` | Check staged files don't span too many directories |
| §commit.run_commit | `run_commit()` | Execute git commit with message/body |
| §commit.main | `main()` | CLI: parse args, validate, commit |

### scripts/validate_anchors.py
| Anchor | Function | Purpose |
|--------|----------|---------|
| §validate_anchors.resolve_namespace | `resolve_namespace()` | Map namespace to file path via NAMESPACE_MAP |
| §validate_anchors.find_anchor_defs | `find_anchor_defs()` | Find all § anchor comments in a source file |
| §validate_anchors.find_anchor_refs | `find_anchor_refs()` | Find all § references in a doc file |
| §validate_anchors.check_anchors | `check_anchors()` | Verify all refs resolve to anchor defs |
| §validate_anchors.fix_missing_anchors | `fix_missing_anchors()` | Auto-insert missing anchor comments |
| §validate_anchors.main | `main()` | CLI: check or --fix mode |

### skills/sprint-release/scripts/release_gate.py
| Anchor | Function | Purpose |
|--------|----------|---------|
| §release_gate.find_latest_semver_tag | `find_latest_semver_tag()` | Find most recent vX.Y.Z tag |
| §release_gate.parse_commits_since | `parse_commits_since()` | Parse commits since tag (or all) |
| §release_gate.calculate_version | `calculate_version()` | Calculate next semver from commit log |
| §release_gate.gate_stories | `gate_stories()` | Gate: all milestone issues must be closed |
| §release_gate.gate_ci | `gate_ci()` | Gate: CI must pass on base branch |
| §release_gate.gate_prs | `gate_prs()` | Gate: no open PRs targeting milestone |
| §release_gate.gate_tests | `gate_tests()` | Gate: all check_commands must pass |
| §release_gate.gate_build | `gate_build()` | Gate: build_command must succeed |
| §release_gate.validate_gates | `validate_gates()` | Run all gates sequentially |
| §release_gate.write_version_to_toml | `write_version_to_toml()` | Write version to [release] section |
| §release_gate.generate_release_notes | `generate_release_notes()` | Generate markdown release notes |
| §release_gate.do_release | `do_release()` | Full release flow: gates, version, tag, publish |
| §release_gate.main | `main()` | CLI: --dry-run, --milestone args |

## Skill entry points -- section index

### skills/sprint-setup/SKILL.md
| Anchor | Section |
|--------|---------|
| §sprint-setup.phase_0_project_initialization | Phase 0: Project initialization |
| §sprint-setup.step_1_check_prerequisites | Step 1: Check prerequisites |
| §sprint-setup.step_2_github_bootstrap_labels_milestones_issues_ci | Step 2: GitHub bootstrap (labels, milestones, issues, CI) |

### skills/sprint-run/SKILL.md
| Anchor | Section |
|--------|---------|
| §sprint-run.state_management | State management (kanban.py integration) |
| §sprint-run.config_prerequisites | Config and prerequisites |
| §sprint-run.phase_detection_reads_sprint_status_md | Phase detection (reads SPRINT-STATUS.md) |
| §sprint-run.phase_1_sprint_kickoff_interactive | Phase 1: Sprint kickoff (INTERACTIVE) |
| §sprint-run.phase_2_story_execution_autonomous_per_story_interactive_at_gates | Phase 2: Story execution (AUTONOMOUS per-story) |
| §sprint-run.mid_sprint_check_in_giles_presents_if_check_in_file_exists | Mid-sprint check-in (Giles presents if check-in file exists) |
| §sprint-run.story_dispatch_kanban_state_table | Story Dispatch (kanban state table) |
| §sprint-run.context_assembly_for_agent_dispatch | Context Assembly for Agent Dispatch (includes insights.md) |
| §sprint-run.context_assembly_for_agent_dispatch | Insights injection for implementer dispatch |
| §sprint-run.context_assembly_for_agent_dispatch | Insights injection for reviewer dispatch |
| §sprint-run.phase_3_sprint_demo_interactive | Phase 3: Sprint demo (INTERACTIVE) |
| §sprint-run.phase_4_sprint_retro_interactive | Phase 4: Sprint retro (INTERACTIVE) |

### skills/sprint-monitor/SKILL.md
| Anchor | Section |
|--------|---------|
| §sprint-monitor.step_0_sync_backlog_debounce_throttle | Step 0: Sync backlog (debounce + throttle) |
| §sprint-monitor.step_1_check_ci_status | Step 1: Check CI status |
| §sprint-monitor.step_1_5_drift_detection_branch_divergence_direct_pushes | Step 1.5: Drift detection (branch divergence + direct pushes) |
| §sprint-monitor.step_2_check_open_prs | Step 2: Check open PRs |
| §sprint-monitor.step_2_5_mid_sprint_check_in_threshold_triggered_giles_ceremony | Step 2.5: Mid-sprint check-in (threshold-triggered Giles ceremony) |
| §sprint-monitor.step_3_check_sprint_status | Step 3: Check sprint status |
| §sprint-monitor.step_4_report | Step 4: Report |
| §sprint-monitor.rate_limiting_and_deduplication | Rate limiting and deduplication |

### skills/sprint-release/SKILL.md
| Anchor | Section |
|--------|---------|
| §sprint-release.step_1_gate_validation | Step 1: Gate validation |
| §sprint-release.step_2_tag_and_release | Step 2: Tag and release |
| §sprint-release.step_3_build_release_artifacts | Step 3: Build release artifacts |
| §sprint-release.step_4_create_github_release | Step 4: Create GitHub Release |
| §sprint-release.step_5_post_release_close_milestone_update_tracking | Step 5: Post-release (close milestone, update tracking) |
| §sprint-release.rollback_procedure | Rollback procedure |

## Reference files -- section index

### skills/sprint-run/references/kanban-protocol.md
| Anchor | Section |
|--------|---------|
| §kanban-protocol.states_6_todo_design_dev_review_integration_done | States (6: todo, design, dev, review, integration, done) |
| §kanban-protocol.transitions_allowed_state_changes | Transitions (allowed state changes) |
| §kanban-protocol.rules_one_story_per_persona_in_dev_3_round_review_limit | Rules (one story per persona in dev, 3-round review limit) |
| §kanban-protocol.github_label_sync_procedure | GitHub label sync procedure |
| §kanban-protocol.wip_limits_1_dev_persona_2_review_reviewer_3_integration | WIP limits (1 dev/persona, 2 review/reviewer, 3 integration) |
| §kanban-protocol.blocked_stories | Blocked story handling |

### skills/sprint-run/references/persona-guide.md
| Anchor | Section |
|--------|---------|
| §persona-guide.persona_assignment_rules_domain_keywords | Persona assignment rules (domain keywords) |
| §persona-guide.voice_guidelines | Voice guidelines |
| §persona-guide.persona_header_format_for_github | GitHub header format for PRs and reviews |
| §persona-guide.giles_scrum_master | Giles rules (always facilitator, never implementer/reviewer) |
| §persona-guide.pm_persona_role_clarification | PM persona role clarification |

### skills/sprint-run/references/ceremony-kickoff.md
| Anchor | Section |
|--------|---------|
| §ceremony-kickoff.facilitation_giles_pm_split | Facilitation: Giles/PM split |
| §ceremony-kickoff.sprint_theme_hardening_feature_star_vehicle_ensemble | Sprint theme (hardening, feature, star-vehicle, ensemble) |
| §ceremony-kickoff.agenda_opening_team_read_saga_context_goal_story_walk_risks_questions_commitment | Agenda: opening, team read, saga context, goal, story walk, risks, questions, commitment |
| §ceremony-kickoff.1_5_team_read_write_insights | Team Read: distill personas into insights.md |
| §ceremony-kickoff.1_7_saga_context_if_sagas_configured | Saga context step (renumbered 1.7) |
| §ceremony-kickoff.2_5_process_context_if_analytics_exist | Process context (Giles reads analytics before story walk) |
| §ceremony-kickoff.3_story_walk | Motivation awareness in story walk |
| §ceremony-kickoff.4_5_confidence_check | Confidence check (Giles reads the room) |
| §ceremony-kickoff.5_5_scope_negotiation | Scope negotiation (value/dependency 2x2) |
| §ceremony-kickoff.output_template_kickoff_md | Output template (kickoff.md) |
| §ceremony-kickoff.exit_criteria | Exit criteria |

### skills/sprint-run/references/ceremony-demo.md
| Anchor | Section |
|--------|---------|
| §ceremony-demo.facilitation_giles_pm_split | Facilitation: Giles/PM split |
| §ceremony-demo.facilitation | Ensemble framing (star-vehicle vs ensemble time allocation) |
| §ceremony-demo.for_each_story | Per-story flow: context, live demo, AC verification, Q&A |
| §ceremony-demo.2_live_demonstration_must_produce_real_artifacts | Live demonstration requirements (real artifacts) |
| §ceremony-demo.3_acceptance_verification | Acceptance verification procedure |
| §ceremony-demo.test_plan_verification_if_test_plan_configured | Test plan verification (if test plan configured) |
| §ceremony-demo.4_team_q_a_in_persona | Team Q&A (Giles manages flow, insights awareness, confidence probing) |
| §ceremony-demo.4_team_q_a_in_persona | Insights in Q&A: call on personas about protected domains |
| §ceremony-demo.output_template_demo_md | Output template (demo.md) |
| §ceremony-demo.rules_no_incomplete_stories_artifact_links_required | Rules (no incomplete stories, artifact links required) |

### skills/sprint-run/references/ceremony-retro.md
| Anchor | Section |
|--------|---------|
| §ceremony-retro.facilitation_giles_facilitates_pm_participates_as_team_member | Facilitation: Giles facilitates, PM participates as team member |
| §ceremony-retro.facilitation | Psychological safety framing |
| §ceremony-retro.facilitation | Insights in psychological safety: acknowledge emotional impact |
| §ceremony-retro.format_start_stop_continue | Start / Stop / Continue format (Giles manages turn-taking) |
| §ceremony-retro.feedback_distillation_identify_patterns_propose_doc_changes | Feedback distillation (identify patterns, propose doc changes) |
| §ceremony-retro.2_propose_doc_changes | PRD feedback loop (retro can update PRD open questions) |
| §ceremony-retro.3_get_user_approval | User approval gate |
| §ceremony-retro.4_apply_changes | Apply changes to project docs |
| §ceremony-retro.5_sprint_analytics | Sprint analytics (run sprint_analytics.py, Giles adds commentary) |
| §ceremony-retro.6_write_sprint_history | Write Sprint History (Giles appends per-persona entries) |
| §ceremony-retro.6_write_sprint_history | Emotional shift tracking in history entries |
| §ceremony-retro.7_definition_of_done_review | Definition of Done review (Giles proposes retro-driven additions) |
| §ceremony-retro.examples_of_retro_driven_doc_changes | Examples of retro-driven doc changes |
| §ceremony-retro.output_template_retro_md | Output template (retro.md) |
| §ceremony-retro.rules_must_produce_at_least_one_doc_change | Rules (must produce at least one doc change) |

### skills/sprint-run/references/story-execution.md
| Anchor | Section |
|--------|---------|
| §story-execution.to_do_design | TODO --> DESIGN (read PRDs, create branch, design notes) |
| §story-execution.commit_convention | Commit convention |
| §story-execution.design_development_tdd_via_superpowers | DESIGN --> DEVELOPMENT (TDD via superpowers) |
| §story-execution.development_review_pr_ready_dispatch_reviewer | DEVELOPMENT --> REVIEW (PR ready, dispatch reviewer) |
| §story-execution.pair_review_high_risk_stories | Pair Review (SP >= 5 + multi-domain, dual reviewer dispatch) |
| §story-execution.review_integration_ci_green_squash_merge | REVIEW --> INTEGRATION (CI green, squash-merge) |
| §story-execution.parallel_dispatch_for_independent_stories | Parallel dispatch for independent stories |

### skills/sprint-run/references/tracking-formats.md
| Anchor | Section |
|--------|---------|
| §tracking-formats.sprint_status_md_format | SPRINT-STATUS.md format |
| §tracking-formats.story_file_yaml_frontmatter | Story file format (YAML frontmatter) |
| §tracking-formats.file_map_where_each_tracking_file_lives | File map (where each tracking file lives) |

### skills/sprint-run/references/context-recovery.md
| Anchor | Section |
|--------|---------|
| §context-recovery.context_recovery_6_step_state_reconstruction_after_context_loss | Context Recovery (6-step state reconstruction after context loss) |

### skills/sprint-setup/references/github-conventions.md
| Anchor | Section |
|--------|---------|
| §github-conventions.label_taxonomy_persona_sprint_saga_priority_kanban_type | Label taxonomy (persona, sprint, saga, priority, kanban, type) |
| §github-conventions.issue_template | Issue template |
| §github-conventions.pr_template | PR template |
| §github-conventions.pr_review_template | PR review template |

### skills/sprint-setup/references/prerequisites-checklist.md
Prerequisites validation checklist for sprint-setup: gh CLI presence, auth status, superpowers plugin, git remote, toolchain detection, Python version checks.

### skills/sprint-setup/references/ci-workflow-template.md
| Anchor | Section |
|--------|---------|
| §ci-workflow-template.workflow_template_yaml_skeleton | Workflow Template (YAML skeleton) |
| §ci-workflow-template.notes_customization_guidance | Notes (customization guidance) |

### skills/sprint-release/references/release-checklist.md
| Anchor | Section |
|--------|---------|
| §release-checklist.stories_gate_gate_stories | Stories gate (gate_stories) |
| §release-checklist.ci_gate_gate_ci | CI gate (gate_ci) |
| §release-checklist.prs_gate_gate_prs | PRs gate (gate_prs) |
| §release-checklist.tests_gate_gate_tests | Tests gate (gate_tests) |
| §release-checklist.build_gate_gate_build | Build gate (gate_build) |
| §release-checklist.post_gate_release_steps | Post-gate release steps |

## Subagent templates

### skills/sprint-run/agents/implementer.md
Dispatched per story. Receives: persona context, story assignment, requirements,
PRD context. Follows TDD, creates PR with self-contained description, stays in
character. Sections: Strategic Context §implementer.strategic_context, Test Plan Context §implementer.test_plan_context, Sprint History §implementer.sprint_history,
Motivation Context §implementer.motivation_context (insights.md distillation), Context Management §implementer.context_management
(budget guidance for large stories), Design §implementer.design, Implement with TDD §implementer.implement_with_tdd,
Progressive Disclosure Docs, Confidence §implementer.confidence (self-rated per area in PR
template), Conventions Checklist §implementer.conventions_checklist.

### skills/sprint-run/agents/reviewer.md
Dispatched after implementation. Different persona from implementer. Three-pass
review: correctness, conventions, testing (each pass focused, not all-at-once).
Reads confidence section from PR to prioritize scrutiny. Posts review via
`gh pr review` with persona header. Reads own + implementer's Sprint History
for callbacks. Sections: Sprint History §reviewer.review_process, Motivation insights §reviewer.review_process, Read PR §reviewer.read_pr,
Three-Pass Review §reviewer.2_read_the_diff_three_pass_review (confidence reading, Pass 1 correctness, Pass 2
conventions, Pass 3 testing §reviewer.pass_3_testing), Test Coverage Verification §reviewer.2_5_verify_test_coverage_if_test_plan_context_provided, Post
Review, Commit Format §reviewer.commit_format.

## Skeleton templates

All in `references/skeletons/`. Used by `sprint_init.py` when project files
are missing. 20 templates: 9 core + 11 deep-doc.

| Template | Creates |
|--------|---------|
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
| `risk-register.md.tmpl` | Risk register: persistent risk tracking across sprints |

## Config structure

```
sprint-config/
  project.toml          -- [project], [paths], [ci] (required); [conventions], [release] (optional)
  definition-of-done.md -- evolving DoD (baseline + retro-driven additions)
  team/INDEX.md          -- Name | Role | File
  team/{name}.md         -- persona profiles (often symlinks)
  team/giles.md          -- built-in scrum master (copied, not symlinked)
  team/insights.md       -- motivation distillation (generated at kickoff)
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
`paths.epics_dir`, `paths.story_map`, `paths.team_topology`.

See §validate_config._REQUIRED_TOML_KEYS for the full list.

## Common modifications

| Want to... | Edit |
|--------|------|
| Add new skill | Create `skills/<name>/SKILL.md` with YAML frontmatter |
| Change config validation | §validate_config._REQUIRED_FILES, §validate_config._REQUIRED_TOML_KEYS |
| Add label category | §bootstrap_github.create_static_labels |
| Add language to CI gen | §setup_ci._SETUP_REGISTRY, §setup_ci._ENV_BLOCKS |
| Add kanban state | §kanban-protocol.states, §validate_config.KANBAN_STATES |
| Change tracking format | §tracking-formats.sprint_status_md, §sync_tracking.sync_one, §update_burndown.write_burndown |
| Add skeleton template | `references/skeletons/<name>.tmpl`, wire in §sprint_init.ConfigGenerator |
| Change story ID pattern | §populate_issues.parse_milestone_stories, or set [backlog] story_id_pattern in TOML |
| Add deep doc support | Set optional paths in TOML (`prd_dir`, `test_plan_dir`, `sagas_dir`, `epics_dir`, `story_map`, `team_topology`). §sprint-run.context_assembly_for_agent_dispatch handles injection. |
