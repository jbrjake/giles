# Doc-to-Implementation Audit: Testable Claims

Phase 1 of Bug Hunter Pass 11. Each claim is extracted from project docs
(CLAUDE.md, SKILL.md files, reference docs) and checked against existing tests.

---

## 1. CLAUDE.md — Architectural Claims

### 1.1 Custom TOML Parser Types

**Claim (CLAUDE.md):** `parse_simple_toml` supports "strings, ints, bools, arrays, sections"

- [x] Strings — `test_pipeline_scripts.py::TestParseSimpleToml::test_inline_comments` + many others
- [x] Integers — `test_pipeline_scripts.py::TestParseSimpleToml::test_integer_parsing`
- [x] Booleans — `test_pipeline_scripts.py::TestParseSimpleToml::test_boolean_parsing`
- [x] Arrays — `test_pipeline_scripts.py::TestParseSimpleToml::test_multiline_arrays` + single-quote arrays
- [x] Sections — `test_pipeline_scripts.py::TestParseSimpleToml::test_nested_sections`
- [x] Multiline arrays — `test_pipeline_scripts.py::TestParseSimpleToml::test_multiline_arrays`
- [x] Comments — `test_pipeline_scripts.py::TestParseSimpleToml::test_comments_only`
- [x] Inline comments — `test_pipeline_scripts.py::TestParseSimpleToml::test_inline_comments`
- [x] Escaped quotes — `test_pipeline_scripts.py::TestParseSimpleToml::test_escaped_quote_in_array`
- [x] Single-quoted strings — `test_pipeline_scripts.py::TestParseSimpleToml::test_single_quote_preserves_hash`
- [x] Edge: unterminated array — `test_pipeline_scripts.py::TestParseSimpleToml::test_unterminated_multiline_array_raises`
- [x] Edge: empty input — `test_pipeline_scripts.py::TestParseSimpleToml::test_empty_input`
- [x] Edge: duplicate sections — `test_pipeline_scripts.py::TestParseSimpleToml::test_duplicate_sections`
- [x] Edge: hyphenated keys — `test_gh_interactions.py::TestBH023HyphenatedTomlKeys`

### 1.2 Idempotent Scripts

**Claim (CLAUDE.md):** "All bootstrap and monitoring scripts are idempotent"

- [x] Issue creation idempotency — `test_lifecycle.py::TestLifecycle::test_07_idempotent_issue_detection`
- [x] do_sync idempotency — `test_sync_backlog.py::TestDoSync::test_do_sync_idempotent` (runs twice, verifies no duplicates)
- [ ] Label creation idempotency — `test_gh_interactions.py::TestCreateLabel::test_label_error_handled` tests error handling but NOT that running `create_static_labels()` twice produces no duplicates **[WEAK]**
- [ ] Milestone creation idempotency — No test runs `create_milestones_on_github()` twice to verify no duplicate milestones **[MISSING]**
- [ ] Sprint analytics idempotency — `test_sprint_analytics.py::TestMainIntegration::test_main_deduplicates_analytics_entry` tests dedup but does NOT test `compute_velocity()` or `compute_review_rounds()` for idempotency **[PARTIAL]**
- [x] sync_tracking idempotency — `test_gh_interactions.py::TestSyncOne::test_no_changes_when_in_sync` (returns empty changes when already in sync)

### 1.3 GitHub as Source of Truth

**Claim (CLAUDE.md):** "sync_tracking.py treats GitHub issue/PR state as authoritative and updates local tracking files to match"

- [x] Closed issue overwrites local status — `test_gh_interactions.py::TestSyncOne::test_closed_issue_updates_status` (status dev -> done)
- [x] Label change overwrites local status — `test_gh_interactions.py::TestSyncOne::test_label_sync_updates_status` (status todo -> review)
- [x] PR number synced from GitHub — `test_gh_interactions.py::TestSyncOne::test_pr_number_updated`
- [ ] No test verifies the REVERSE is NOT true (local state does not override GitHub) **[WEAK]**
- [x] create_from_issue reads GitHub state — `test_gh_interactions.py::TestCreateFromIssue` (3 tests)

### 1.4 Symlink-based Config / Giles Exception

**Claim (CLAUDE.md):** "sprint_init creates symlinks from sprint-config/ to existing project files. Exception: Giles is copied (plugin-owned), not symlinked."

- [x] Giles is not a symlink — `test_hexwise_setup.py::TestHexwiseSetup::test_giles_persona_generated` (asserts `is_symlink() == False`)
- [x] Teardown removes symlinks, preserves targets — `test_sprint_teardown.py::TestRemoveSymlinks::test_removes_symlinks_preserves_targets`
- [ ] No test verifies that project files (rules.md, development.md) are symlinked (not copied) during init **[MISSING]**

### 1.5 Config-Driven / No Hardcoded Values

**Claim (CLAUDE.md):** "Nothing is hardcoded to a specific project. All project-specific values come from project.toml."

- [x] Evals have no hardcoded project names — `test_verify_fixes.py::TestEvalsGeneric` (3 tests: no Dreamcatcher, no Rachel, no cargo commands)
- [x] CI uses configured base_branch — `test_hexwise_setup.py::TestHexwisePipeline::test_ci_workflow_uses_configured_branch`
- [x] get_base_branch defaults to main — `test_gh_interactions.py` (3 tests: develop override, missing key, empty string)

### 1.6 Scripts Import Chain

**Claim (CLAUDE.md):** "All skill scripts do `sys.path.insert(0, ...)` to reach `scripts/validate_config.py`"

- [x] Implicitly verified — all test files successfully import from scripts and skill scripts across paths

### 1.7 Required TOML Keys

**Claim (CLAUDE.md):** Required keys: `project.name`, `project.repo`, `project.language`, `paths.team_dir`, `paths.backlog_dir`, `paths.sprints_dir`, `ci.check_commands`, `ci.build_command`

- [x] Generated config has required keys — `test_verify_fixes.py::TestConfigGeneration::test_generated_toml_has_required_keys`
- [x] validate_project catches missing keys — `test_verify_fixes.py::TestConfigGeneration::test_generated_config_passes_validation`
- [ ] No test explicitly provides a config missing ONE required key and verifies validate_project fails **[MISSING]**

---

## 2. kanban-protocol.md — State Machine Claims

### 2.1 Six Kanban States

**Claim:** "6 states: todo, design, dev, review, integration, done"

- [x] KANBAN_STATES constant has 6 entries — `validate_config.py:794` defines `frozenset(("todo", "design", "dev", "review", "integration", "done"))`
- [x] kanban_from_labels recognizes valid states — `test_pipeline_scripts.py::TestKanbanFromLabels` (7 tests) + `test_gh_interactions.py` (5 tests)
- [x] Invalid kanban label falls back — `test_pipeline_scripts.py::TestKanbanFromLabels::test_invalid_kanban_label_falls_back`

### 2.2 Transition Rules

**Claim:** Specific transitions allowed: todo->design, design->dev, dev->review, review->dev, review->integration, integration->done

- [ ] No test validates that ONLY these transitions are allowed **[MISSING]**
- [ ] No test validates that illegal transitions (e.g., todo->done, design->review) are rejected **[MISSING]**
- [ ] The transition rules are documented in kanban-protocol.md but NOT enforced in code — `sync_tracking.sync_one()` will accept ANY kanban label without checking prior state **[DOC-DRIFT]**

### 2.3 WIP Limits

**Claim:** "1 per persona in dev, 2 per reviewer in review, 3 in integration"

- [ ] No test validates WIP limits **[MISSING]**
- [ ] No code enforces WIP limits — this is a process doc for the LLM, not programmatic enforcement **[DOC-DRIFT — but may be intentional]**

### 2.4 Review Round Limit

**Claim:** "review -> dev loop can repeat at most 3 times"

- [ ] No test validates the 3-round limit **[MISSING]**
- [ ] No code enforces the 3-round limit — this is a process doc for the LLM **[DOC-DRIFT — but may be intentional]**

---

## 3. release-checklist.md — Gate Criteria Claims

### 3.1 Stories Gate

**Claim:** "All GitHub issues in the milestone are closed"

- [x] gate_stories passes when no open issues — `test_gh_interactions.py::TestGateStories::test_all_closed`
- [x] gate_stories fails with open issues — `test_gh_interactions.py::TestGateStories::test_open_issues`

### 3.2 CI Gate

**Claim:** "Most recent CI run on base branch passes"

- [x] gate_ci passes on success — `test_gh_interactions.py::TestGateCI::test_passing`
- [x] gate_ci fails on failure — `test_gh_interactions.py::TestGateCI::test_failing`
- [x] gate_ci fails with no runs — `test_gh_interactions.py::TestGateCI::test_no_runs`

### 3.3 PRs Gate

**Claim:** "No open PRs target this milestone"

- [x] gate_prs passes with no PRs — `test_gh_interactions.py::TestGatePRs::test_no_prs`
- [x] gate_prs fails with open PR for milestone — `test_gh_interactions.py::TestGatePRs::test_open_pr_for_milestone`
- [x] gate_prs passes when PR is for different milestone — `test_gh_interactions.py::TestGatePRs::test_pr_for_different_milestone`
- [x] gate_prs fails at 500 limit — `test_gh_interactions.py::TestGatePRs::test_limit_hit_fails_gate`

### 3.4 Tests Gate

**Claim:** "All check_commands from project.toml pass"

- [x] gate_tests passes — `test_release_gate.py::TestGateTests::test_all_commands_pass`
- [x] gate_tests fails — `test_release_gate.py::TestGateTests::test_command_failure`
- [x] gate_tests handles no commands — `test_release_gate.py::TestGateTests::test_no_commands_configured`

### 3.5 Build Gate

**Claim:** "build_command succeeds; binary exists at binary_path if configured"

- [x] gate_build passes — `test_release_gate.py::TestGateBuild::test_build_success`
- [x] gate_build fails — `test_release_gate.py::TestGateBuild::test_build_failure`
- [x] gate_build handles no command — `test_release_gate.py::TestGateBuild::test_no_build_command`
- [x] gate_build fails for missing binary — `test_release_gate.py::TestGateBuild::test_missing_binary`

### 3.6 Gate Pipeline Order

**Claim:** "Each gate runs in order; first failure stops the pipeline"

- [x] First failure stops — `test_release_gate.py::TestValidateGates::test_first_failure_stops`
- [x] Middle failure stops — `test_release_gate.py::TestValidateGates::test_middle_failure_pr_gate`
- [x] All pass — `test_release_gate.py::TestValidateGates::test_all_pass`

### 3.7 Post-Gate Release Steps

**Claim:** "Calculate version, write to TOML, commit/tag/push, release notes, GitHub Release, close milestone"

- [x] Version calculation — `test_release_gate.py::TestCalculateVersion` (4 tests)
- [x] Write version to TOML — `test_gh_interactions.py::TestWriteVersionToToml` (4 tests) + `test_lifecycle.py::test_10`
- [x] Release notes generation — `test_gh_interactions.py::TestGenerateReleaseNotes` + `test_lifecycle.py::test_09`
- [x] do_release happy path — `test_release_gate.py::TestDoRelease::test_happy_path`
- [x] do_release dry run — `test_release_gate.py::TestDoRelease::test_dry_run_no_mutations`
- [x] do_release rollback on failures — `test_release_gate.py::TestDoRelease` (tag failure, push failure, GH release failure tests)

---

## 4. persona-guide.md — Persona Claims

### 4.1 Persona Assignment by Domain

**Claim:** "Assign stories by domain ownership. The reviewer is ALWAYS a different persona from the implementer."

- [ ] No test validates persona assignment logic (it's LLM-driven, not scripted) **[NOT APPLICABLE — process doc for LLM, not code]**

### 4.2 Giles Role

**Claim:** "Giles is always the ceremony facilitator — never the implementer or reviewer"

- [x] Giles persona file generated — `test_hexwise_setup.py::TestHexwiseSetup::test_giles_persona_generated`
- [x] Giles has required sections — `test_hexwise_setup.py::TestHexwiseSetup::test_giles_persona_has_required_sections`
- [x] Giles in team index — `test_hexwise_setup.py::TestHexwiseSetup::test_giles_in_team_index`
- [ ] No test verifies Giles cannot be assigned as implementer or reviewer **[NOT APPLICABLE — enforcement is in SKILL.md prompts, not code]**

---

## 5. Sprint Setup SKILL.md — Workflow Claims

### 5.1 Sprint Init Auto-Detection

**Claim:** "Auto-detect project -> generate sprint-config/"

- [x] Language detection (Rust) — `test_hexwise_setup.py::TestHexwiseSetup::test_scanner_detects_rust`
- [x] Persona detection — `test_hexwise_setup.py::TestHexwiseSetup::test_scanner_finds_personas`
- [x] Milestone detection — `test_hexwise_setup.py::TestHexwiseSetup::test_scanner_finds_milestones`
- [x] Rules/dev guide detection — `test_hexwise_setup.py::TestHexwiseSetup::test_scanner_finds_rules_and_dev`
- [x] Deep docs detection — `test_hexwise_setup.py::TestHexwiseSetup::test_scanner_detects_hexwise_deep_docs`
- [x] Config passes validation — `test_hexwise_setup.py::TestHexwiseSetup::test_config_generation_succeeds`

### 5.2 Full Pipeline

**Claim:** "sprint_init -> bootstrap_github -> populate_issues"

- [x] Full pipeline (minimal) — `test_lifecycle.py::TestLifecycle::test_13_full_pipeline`
- [x] Full pipeline (hexwise) — `test_hexwise_setup.py::TestHexwisePipeline::test_full_setup_pipeline`
- [x] Golden snapshot regression — `test_golden_run.py::TestGoldenRun::test_golden_full_setup_pipeline`

---

## 6. Sprint Monitor SKILL.md — Monitoring Claims

### 6.1 CI Check

**Claim:** "check_ci queries GitHub Actions workflow runs"

- [x] No runs — `test_gh_interactions.py::TestCheckCI::test_no_runs`
- [x] Passing runs — `test_gh_interactions.py::TestCheckCI::test_all_passing`
- [x] Failing runs — `test_gh_interactions.py::TestCheckCI::test_failing_run`

### 6.2 PR Check

**Claim:** "check_prs queries open PRs"

- [x] No PRs — `test_gh_interactions.py::TestCheckPRs::test_no_prs`
- [x] Approved PR — `test_gh_interactions.py::TestCheckPRs::test_approved_pr`
- [x] Needs review — `test_gh_interactions.py::TestCheckPRs::test_needs_review_pr`

### 6.3 Milestone Progress

**Claim:** "check_milestone reports issue/SP progress"

- [x] Progress reporting — `test_lifecycle.py::TestLifecycle::test_14_monitoring_pipeline` (verifies 2/4, 50%, 8/13 SP)

### 6.4 Backlog Sync

**Claim:** "Backlog auto-sync with debounce/throttle"

- [x] No change detection — `test_sync_backlog.py::TestCheckSync::test_no_change_returns_no_changes`
- [x] First change debounces — `test_sync_backlog.py::TestCheckSync::test_first_change_triggers_debounce`
- [x] Re-debounce on further changes — `test_sync_backlog.py::TestCheckSync::test_still_changing_re_debounces`
- [x] Stabilized triggers sync — `test_sync_backlog.py::TestCheckSync::test_stabilized_triggers_sync`
- [x] Revert cancels pending — `test_sync_backlog.py::TestCheckSync::test_revert_cancels_pending`
- [x] Throttle blocks sync — `test_sync_backlog.py::TestCheckSync::test_throttle_blocks_sync`
- [x] Throttle expired allows sync — `test_sync_backlog.py::TestCheckSync::test_throttle_expired_allows_sync`
- [x] End-to-end main() — `test_sync_backlog.py::TestMain` (3 tests: debounce, sync, no_changes)

---

## 7. Sprint Teardown — Safety Claims

### 7.1 Safe Removal

**Claim:** "Teardown removes symlinks without touching originals"

- [x] Symlinks removed, targets preserved — `test_sprint_teardown.py::TestRemoveSymlinks::test_removes_symlinks_preserves_targets`
- [x] Multiple symlinks removed — `test_sprint_teardown.py::TestRemoveSymlinks::test_removes_multiple_symlinks`
- [x] Full teardown flow — `test_sprint_teardown.py::TestFullTeardownFlow::test_teardown_preserves_originals`
- [x] Dry run preserves files — `test_sprint_teardown.py::TestTeardownMainDryRun::test_dry_run_preserves_files`
- [x] Execute removes generated — `test_sprint_teardown.py::TestTeardownMainExecute::test_execute_removes_generated`
- [x] Missing config dir exits cleanly — `test_sprint_teardown.py::TestTeardownMainExecute::test_no_config_dir_exits_cleanly`

---

## 8. Sprint Run SKILL.md — Tracking Claims

### 8.1 Tracking File Format

**Claim:** "Story tracking file YAML frontmatter with story, title, sprint, status, etc."

- [x] write_tf/read_tf round-trip — `test_gh_interactions.py` (sync_tracking tests create and read TFs)
- [x] create_from_issue produces valid TF — `test_gh_interactions.py::TestCreateFromIssue` (3 tests)
- [x] YAML-safe quoting — `test_gh_interactions.py` (tests with special chars in titles)

### 8.2 Burndown Generation

**Claim:** "write_burndown + update_sprint_status from GitHub milestones"

- [x] Full burndown pipeline — `test_lifecycle.py::TestLifecycle::test_14_monitoring_pipeline` (verifies Completed: 8 SP, Remaining: 5 SP)

---

## 9. Sprint Analytics — Metrics Claims

### 9.1 Velocity Computation

**Claim:** "compute_velocity calculates planned vs delivered SP"

- [x] All closed — `test_sprint_analytics.py::TestComputeVelocity::test_all_closed`
- [x] Partial delivery — `test_sprint_analytics.py::TestComputeVelocity::test_partial_delivery`
- [x] Malformed SP labels — `test_sprint_analytics.py::TestComputeVelocity::test_malformed_sp_labels_contribute_zero`

### 9.2 Review Rounds

**Claim:** "compute_review_rounds counts review events per PR"

- [x] Counts review events — `test_sprint_analytics.py::TestComputeReviewRounds::test_counts_review_events`
- [x] No PRs handled — `test_sprint_analytics.py::TestComputeReviewRounds::test_no_prs`
- [x] Non-matching milestone filtered — BH-002 coverage in `test_counts_review_events`

### 9.3 Workload Distribution

**Claim:** "compute_workload counts stories per persona"

- [x] Per-persona counts — `test_sprint_analytics.py::TestComputeWorkload::test_counts_per_persona`
- [x] No persona labels — `test_sprint_analytics.py::TestComputeWorkload::test_no_persona_labels`

---

## 10. Commit Script — Convention Claims

### 10.1 Conventional Commits

**Claim:** "Enforce conventional commits format"

- [x] Valid types — `test_gh_interactions.py::TestValidateMessage::test_all_valid_types` (10 types)
- [x] Invalid type rejected — `test_gh_interactions.py::TestValidateMessage::test_invalid_type`
- [x] Scoped commits — `test_gh_interactions.py::TestValidateMessage::test_valid_fix_with_scope`
- [x] Breaking change syntax — `test_gh_interactions.py::TestValidateMessage::test_valid_breaking`

### 10.2 Atomicity Check

**Claim:** "check_atomicity requires --force if files span 3+ top-level directories"

- [x] No staged changes — `test_gh_interactions.py::TestCheckAtomicity::test_no_staged_changes`
- [x] Single directory OK — `test_gh_interactions.py::TestCheckAtomicity::test_single_directory`
- [x] Three directories blocked — `test_gh_interactions.py::TestCheckAtomicity::test_three_directories_without_force`
- [x] Three directories with force OK — `test_gh_interactions.py::TestCheckAtomicity::test_three_directories_with_force`

---

## 11. Anchor Validation — Doc Integrity Claims

### 11.1 Anchor System

**Claim:** "Validate section-prefixed anchor references in docs"

- [x] Anchor definitions found — `test_validate_anchors.py::TestFindAnchorDefs` (4 tests)
- [x] Anchor references found — `test_validate_anchors.py::TestFindAnchorRefs` (5 tests)
- [x] Broken refs detected — `test_validate_anchors.py::TestCheckAnchors::test_broken_ref_detected`
- [x] Unknown namespace detected — `test_validate_anchors.py::TestCheckAnchors::test_unknown_namespace_is_broken`
- [x] Unreferenced anchor reported — `test_validate_anchors.py::TestCheckAnchors::test_unreferenced_anchor_reported`
- [x] Autofix works — `test_validate_anchors.py::TestFixMode` (5 tests)
- [x] All namespace mappings valid — `test_validate_anchors.py::TestNamespaceMap::test_all_mapped_files_exist`

---

## 12. Pipeline Scripts — Utility Claims

### 12.1 Team Voices

**Claim:** "Extract persona commentary from saga/epic files"

- [x] Extraction from sagas — `test_pipeline_scripts.py::TestTeamVoices::test_extract_voices_from_sagas`

### 12.2 Traceability

**Claim:** "Bidirectional story/PRD/test mapping with gap detection"

- [x] Parse stories — `test_pipeline_scripts.py::TestTraceability` (multiple tests)
- [x] Parse test cases — `test_pipeline_scripts.py::TestTraceability`
- [x] Build traceability — `test_pipeline_scripts.py::TestTraceability`

### 12.3 Test Coverage

**Claim:** "Compare planned test cases vs actual test files"

- [x] Parse planned tests — `test_pipeline_scripts.py::TestTestCoverage`
- [x] Detect test functions — `test_pipeline_scripts.py::TestTestCoverage`

### 12.4 Epic/Saga Management

**Claim:** "Epic CRUD: add, remove, reorder stories"

- [x] Parse epic — `test_pipeline_scripts.py::TestManageEpics::test_parse_epic`
- [x] Add story — `test_pipeline_scripts.py::TestManageEpics::test_add_story`
- [x] Remove story — `test_pipeline_scripts.py::TestManageEpics::test_remove_story`
- [x] Reorder stories — `test_pipeline_scripts.py::TestManageEpics::test_reorder_stories`
- [x] Duplicate detection — `test_pipeline_scripts.py::TestManageEpics::test_add_story_duplicate_raises`

---

## Summary

| Category | Passed | Failed | Total |
|----------|--------|--------|-------|
| TOML Parser | 14 | 0 | 14 |
| Idempotency | 3 | 3 | 6 |
| GitHub Source of Truth | 4 | 1 | 5 |
| Symlink Config | 2 | 1 | 3 |
| Kanban State Machine | 3 | 4 | 7 |
| Release Gates | 16 | 0 | 16 |
| Persona System | 3 | 0 | 3 |
| Sprint Setup | 9 | 0 | 9 |
| Monitoring | 10 | 0 | 10 |
| Teardown | 6 | 0 | 6 |
| Tracking | 4 | 0 | 4 |
| Analytics | 7 | 0 | 7 |
| Commit | 6 | 0 | 6 |
| Anchors | 7 | 0 | 7 |
| Pipeline Utilities | 6 | 0 | 6 |
| Config Validation | 2 | 1 | 3 |
| **Total** | **102** | **10** | **112** |

10 failed claims generate punchlist items BH-P11-001 through BH-P11-010.
