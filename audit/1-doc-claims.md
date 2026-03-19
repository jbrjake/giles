# Doc-to-Implementation Audit

Audited 2026-03-19. Cross-references documentation claims against actual
implementation code. Each finding has a doc source, code source, gap
description, and impact assessment.

---

## Verified (no gap)

These major claims were confirmed correct:

- CLAUDE.md config tree matches `_REQUIRED_FILES` for 6 required files
- CLAUDE.md TOML keys list matches `_REQUIRED_TOML_KEYS` (8 keys)
- kanban-protocol.md 6 states match `KANBAN_STATES` frozenset in validate_config.py:981
- kanban-protocol.md transition table matches `TRANSITIONS` dict in kanban.py:47-54
- kanban-protocol.md preconditions table matches `check_preconditions()` in kanban.py:88-128
- CLAUDE.md skeleton template count (19) matches actual file count
- CLAUDE.md `_SETUP_REGISTRY` and `_ENV_BLOCKS` references match setup_ci.py:66 and :81
- github-conventions.md label taxonomy (persona, sprint, saga, priority, kanban, type) matches bootstrap_github.py `create_*` functions
- github-conventions.md 6 kanban labels match `create_static_labels()` in bootstrap_github.py:202-211
- github-conventions.md 4 type labels match bootstrap_github.py:214-218
- github-conventions.md 3 priority labels (P0/P1/P2) match bootstrap_github.py:196-198
- release-checklist.md 5 gates match `validate_gates()` order in release_gate.py:258-264
- TF dataclass fields in validate_config.py:1034-1047 match tracking-formats.md YAML frontmatter
- write_tf() output at validate_config.py:1115-1135 matches tracking-formats.md field list
- SPRINT-STATUS.md format in tracking-formats.md matches `update_sprint_status()` in update_burndown.py:77-113
- All 5 SKILL.md files exist with correct frontmatter
- All scripts listed in CLAUDE.md exist and export the listed functions
- implementer.md and reviewer.md correctly reference `kanban.py` for state transitions
- ceremony-retro.md correctly references `sprint_analytics.py` (optional sprint arg, auto-detects)

---

## Findings

### [DOC-1] story-execution.md: update_burndown.py called without required argument
- **Doc:** `skills/sprint-run/references/story-execution.md:155` shows:
  `python "${CLAUDE_PLUGIN_ROOT}/skills/sprint-run/scripts/update_burndown.py"`
- **Code:** `skills/sprint-run/scripts/update_burndown.py:174` requires exactly one positional argument:
  `Usage: python update_burndown.py <sprint-number>` and exits with code 2 if not provided
- **Gap:** Doc shows the command with no arguments; script will print usage error and exit(2)
- **Impact:** Agent following story-execution.md will get a usage error when trying to update the burndown after merging a story. Needs `<sprint-number>` appended.

### [DOC-2] context-recovery.md: sync_tracking.py called without required argument
- **Doc:** `skills/sprint-run/references/context-recovery.md:15` shows:
  `"${CLAUDE_PLUGIN_ROOT}/skills/sprint-run/scripts/sync_tracking.py"` (no argument)
- **Code:** `skills/sprint-run/scripts/sync_tracking.py:220-225` requires exactly one positional argument:
  `Usage: python sync_tracking.py <sprint-number>` and exits with code 2 if not provided
- **Gap:** Doc omits the required `<sprint-number>` argument
- **Impact:** Agent recovering context will get a usage error. Must pass the sprint number detected from SPRINT-STATUS.md.

### [DOC-3] context-recovery.md: wrong label format in gh pr list command
- **Doc:** `skills/sprint-run/references/context-recovery.md:19` shows:
  `gh pr list --label "sprint-{N}"` (hyphen-separated)
- **Code:** github-conventions.md:17, implementer.md:88, bootstrap_github.py:120 all use format `sprint:{N}` (colon-separated)
- **Gap:** `sprint-{N}` is not a valid label; the actual label format is `sprint:{N}`
- **Impact:** The `gh pr list` command will return zero results because the label name is wrong. Should be `gh pr list --label "sprint:{N}"`.

### [DOC-4] kanban-protocol.md and story-execution.md: omit --sprint flag from kanban.py commands
- **Doc:** `skills/sprint-run/references/kanban-protocol.md:73-82` and `story-execution.md:42,83,108,147-159` show kanban.py commands without `--sprint N`
- **Code:** `scripts/kanban.py:540-561` accepts `--sprint` on all subcommands. Without it, auto-detection via `detect_sprint()` is used.
- **Gap:** Not a bug per se -- auto-detection works. But implementer.md:133-134 correctly uses `--sprint {sprint_number}`, creating an inconsistency between doc files. Agents dispatched from story-execution.md will rely on auto-detection while agents dispatched from implementer.md will pass explicit sprint numbers.
- **Impact:** Low. Auto-detection works when SPRINT-STATUS.md exists. But if two sprints overlap (rare but possible), the explicit flag avoids ambiguity. The docs should be consistent.

### [DOC-5] CLAUDE.md: bootstrap_github.py function list is incomplete
- **Doc:** `CLAUDE.md:42` lists 5 functions: `create_persona_labels`, `_collect_sprint_numbers`, `create_static_labels`, `create_epic_labels`, `create_milestones_on_github`, `main`
- **Code:** `skills/sprint-setup/scripts/bootstrap_github.py` also exports: `create_sprint_labels` (line 111), `create_saga_labels` (line 160), `_parse_saga_labels_from_backlog` (line 124), `create_label` (line 45), `check_prerequisites` (line 18)
- **Gap:** 5 public functions are not listed in CLAUDE.md's summary table
- **Impact:** An agent looking up bootstrap_github functions from CLAUDE.md won't find `create_sprint_labels` or `create_saga_labels`. These are called by `main()` and by `sync_backlog.py` (cross-skill dependency). Missing from the lookup table means agents may not realize these exist when debugging sync issues.

### [DOC-6] CLAUDE.md: config tree shows team/giles.md as REQUIRED but validate_config.py doesn't check it
- **Doc:** `CLAUDE.md:100` marks `team/giles.md` as `REQUIRED -- built-in scrum master (copied, not symlinked)`
- **Code:** `scripts/validate_config.py:438-451` `_REQUIRED_FILES` does not include `team/giles.md`. The check is in `skills/sprint-run/SKILL.md:28` as a manual prerequisite.
- **Gap:** "REQUIRED" in CLAUDE.md implies programmatic validation, but `validate_config.py` won't flag a missing giles.md. Only sprint-run's SKILL.md instructs the agent to check.
- **Impact:** Low -- sprint-setup creates giles.md, and sprint-run checks for it. But `validate_project()` won't catch the error, so sprint-monitor or sprint-release could run without giles.md and fail confusingly downstream.

### [DOC-7] CLAUDE.md: config tree shows team/{name}.md as REQUIRED but validation only warns
- **Doc:** `CLAUDE.md:99` marks `team/{name}.md` as `REQUIRED -- persona files`
- **Code:** `scripts/validate_config.py:548-563` checks persona files exist but only adds them to `errors[]` -- it doesn't appear in `_REQUIRED_FILES`. The validation does fail if persona files are missing, so this is technically enforced.
- **Gap:** Technically no functional gap -- the persona file check at line 562 does add errors. But the enforcement is in a separate validation block (step 4), not in `_REQUIRED_FILES` (step 1). The CLAUDE.md "REQUIRED" label is accurate, just the enforcement mechanism is different than what a reader might expect.
- **Impact:** None. Validation catches missing persona files.

### [DOC-8] CLAUDE.md: config tree shows team/history/ and team/insights.md as "runtime" but they're never validated
- **Doc:** `CLAUDE.md:101-102` marks `team/history/` and `team/insights.md` as `runtime` artifacts
- **Code:** No validation anywhere for these. implementer.md:40-50 and :52-59 say "if it exists... skip this section" and reviewer.md:11-19 says "if it exists"
- **Gap:** Not really a gap -- "runtime" means created during execution. But the docs could more clearly state these are optional files created by ceremony scripts, not validated by anything.
- **Impact:** None. The agent instructions handle the "doesn't exist" case.

### [DOC-9] story-execution.md: transition order during integration shows merge before state transition
- **Doc:** `skills/sprint-run/references/story-execution.md:141-152` shows this order:
  1. `gh pr checks {pr_number} --watch`
  2. Invoke verification
  3. `gh pr merge {pr_number} --squash --delete-branch`
  3.5. `kanban.py transition {story_id} integration`
  4. Confirm merge, then `kanban.py transition {story_id} done`
- **Code:** `kanban.py:47-54` TRANSITIONS dict requires `review -> integration -> done`. The precondition for `done` requires `pr_number` (already set).
- **Gap:** The merge happens BEFORE the transition to `integration`. If the merge succeeds but the transition to `integration` fails (GitHub label sync error), the story is merged but stuck in `review` state locally. The `kanban.py sync` would eventually fix this, but the doc ordering creates a window of inconsistency.
- **Impact:** Low. The sync mechanism catches this. But the ideal order would be: transition to integration, THEN merge, THEN transition to done. This way, a merge failure doesn't leave the story in `integration` with no merged PR, and a transition failure doesn't leave a merged PR in `review` state.

### [DOC-10] sprint-monitor SKILL.md: step numbering inconsistency
- **Doc:** `skills/sprint-monitor/SKILL.md:21-28` lists "seven steps" (0, 1, 1.5, 2, 2.5, 3, 4)
- **Code:** `skills/sprint-monitor/scripts/check_status.py:438-444` runs 5 checks in order: check_ci, check_branch_divergence, check_prs, check_direct_pushes, check_milestone
- **Gap:** SKILL.md calls them "seven steps" but the numbering has half-steps (1.5, 2.5) making it really 7 numbered items. The Python script runs 5 check functions (it collapses step 0 into the sync_backlog import, and step 4 is just formatting the output). The step counts don't directly correspond but are functionally equivalent.
- **Impact:** None functional. Minor documentation clarity issue.

### [DOC-11] sprint-monitor SKILL.md: tells agent NOT to run individual gh commands, then shows individual gh commands
- **Doc:** `skills/sprint-monitor/SKILL.md:247-248` says "Running `check_status.py` covers Steps 0-3, so the agent should NOT also run individual `gh` commands for the same checks."
- **Doc:** But Steps 1-2.5 (lines 79-227) show detailed individual `gh` commands for each check
- **Gap:** The SKILL.md presents two modes: (1) run check_status.py which does everything, (2) detailed manual steps. It says to use mode 1 but documents mode 2 in detail. An agent might run both, doubling API calls.
- **Impact:** Low -- redundant API calls waste rate limit quota but don't break anything. The doc should more clearly delineate the two modes.

### [DOC-12] reviewer.md: inline comment API uses {owner}/{repo} placeholder instead of config value
- **Doc:** `skills/sprint-run/agents/reviewer.md:143-144` shows:
  `gh api repos/{owner}/{repo}/pulls/{pr_number}/comments -f body="..." -f path="..." -F line={N} -f side=RIGHT`
- **Code:** `gh api` auto-expands `{owner}/{repo}` from the git remote, so this actually works
- **Gap:** None -- `gh api` handles the template. But the comment at line 143 says "Read repo from project.toml [project] repo" which is misleading since `gh api` handles it natively.
- **Impact:** None functional. The instruction to "read repo from project.toml" is unnecessary overhead for the agent.

### [DOC-13] CLAUDE.md: "Floats are not supported (returned as raw strings)" -- VERIFIED CORRECT
- **Doc:** `CLAUDE.md:126` claims floats are "returned as raw strings"
- **Code:** `scripts/validate_config.py:317-375` `_parse_value()` tries `int(raw)` at line 355, catches ValueError, then falls through to raw string return at line 375. A float like `1.5` would fail int parse and return as the string `"1.5"`.
- **Gap:** None. Claim is accurate.
- **Impact:** N/A -- verified correct.

### [DOC-14] kanban-protocol.md: says "Every transition updates two artifacts" but kanban.py only updates one
- **Doc:** `skills/sprint-run/references/kanban-protocol.md:46-50` says every transition updates:
  1. Story tracking file in `{sprints_dir}/sprint-{N}/stories/`
  2. GitHub issue label
  Then says "Burndown and SPRINT-STATUS.md are updated separately by `update_burndown.py`"
- **Code:** `scripts/kanban.py:242-286` `do_transition()` updates (1) local tracking file via `atomic_write_tf` and (2) GitHub issue label via `gh issue edit`. This matches.
- **Gap:** None. The doc is accurate. The "two artifacts" matches what the code does.
- **Impact:** N/A -- verified correct.

### [DOC-15] ceremony-kickoff.md: exit criteria shows kanban.py sync without --sprint flag
- **Doc:** `skills/sprint-run/references/ceremony-kickoff.md:258` shows:
  `python "${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py" sync --sprint {N}`
- **Code:** `scripts/kanban.py:548-551` accepts `--sprint` flag
- **Gap:** None -- this is correct. The kickoff doc correctly includes `--sprint {N}`.
- **Impact:** N/A -- verified correct. (This contrasts with kanban-protocol.md which omits the flag.)

### [DOC-16] sprint-release SKILL.md: manual tag/push commands vs automated do_release()
- **Doc:** `skills/sprint-release/SKILL.md:103-106` shows manual git tag and push commands
- **Code:** `skills/sprint-release/scripts/release_gate.py:438-707` `do_release()` automates tag creation, push, version writing, and GitHub Release creation in one flow
- **Gap:** SKILL.md shows both the automated script path (Step 1 gate validation) and manual commands (Step 2 tag). An agent might run `release_gate.py release` which does everything, then also run the manual tag commands from Step 2, creating duplicate tags.
- **Impact:** The duplicate tag creation would fail harmlessly (tag already exists). But the SKILL.md should clarify that Steps 2-5 are handled by `release_gate.py release` and the manual commands are only for reference/fallback.

### [DOC-17] CLAUDE.md: populate_issues.py function list is incomplete
- **Doc:** `CLAUDE.md:44` lists 7 functions for populate_issues.py
- **Code:** `skills/sprint-setup/scripts/populate_issues.py` also has: `_safe_compile_pattern` (line 62), `_build_row_regex` (line 108), `_infer_sprint_number` (line 180), `_build_detail_block_re` (line 207), `get_existing_issues` (line 340), `get_milestone_numbers` (line 374), `check_prerequisites` (line 37)
- **Gap:** 7 additional functions not listed. Most are private helpers (`_` prefix), but `get_existing_issues` and `get_milestone_numbers` are public API used by sync_backlog.py's cross-skill import.
- **Impact:** Low. The CLAUDE.md table is documented as a "summary" not exhaustive. But `get_existing_issues` is important for understanding the idempotency mechanism.

### [DOC-18] SPRINT-STATUS.md phase field: docs reference "phase" but format shows "Sprint Phase"
- **Doc:** `skills/sprint-run/SKILL.md:48` says "Read SPRINT-STATUS.md and route" based on "phase"
- **Doc:** `skills/sprint-run/references/tracking-formats.md:12` shows format: `## Sprint Phase: development`
- **Doc:** `skills/sprint-monitor/SKILL.md:46` shows: `grep -q "phase:.*development"` which would NOT match `## Sprint Phase: development`
- **Gap:** sprint-monitor SKILL.md uses a grep pattern `phase:.*development` that won't match the actual format `## Sprint Phase: development` (the `##` prefix and space make it a markdown heading, not a key:value pair)
- **Impact:** Medium. An agent literally running that grep command will get no match and incorrectly conclude there's no active development phase. The grep should be `grep -q "Sprint Phase:.*development"` or similar.

### [DOC-19] story-execution.md: design transition happens BEFORE branch and PR creation
- **Doc:** `skills/sprint-run/references/story-execution.md:18-43` shows the TODO->DESIGN transition including:
  1. Write design notes
  2. Create branch
  3. Open draft PR
  4. `kanban.py transition {story_id} design` (step 4)
- **Doc:** `kanban-protocol.md:60-61` says design requires `implementer` field set
- **Code:** `kanban.py:102-104` check_preconditions for "design" only requires `implementer`
- **Gap:** None -- the transition to `design` only needs `implementer` (not branch/PR). The branch and PR are created during the design phase, and `branch`+`pr_number` are needed for the `dev` transition. The doc ordering is correct.
- **Impact:** N/A -- verified correct.

### [DOC-20] story-execution.md: design->dev transition requires branch and pr_number but doc shows them set AFTER transition
- **Doc:** `skills/sprint-run/references/story-execution.md:79-84` shows:
  ```
  git push origin {branch_name}
  gh pr ready {pr_number}
  kanban.py update {story_id} --pr-number {pr_number} --branch {branch_name}
  kanban.py transition {story_id} dev
  ```
- **Code:** `kanban.py:105-114` check_preconditions for "dev" requires both `branch` and `pr_number`
- **Gap:** None -- the doc correctly shows `update` BEFORE `transition`. The update sets the fields, then the transition checks them.
- **Impact:** N/A -- verified correct.

### [DOC-21] implementer.md: shows --label "kanban:design" on PR creation but kanban labels are managed by kanban.py
- **Doc:** `skills/sprint-run/agents/implementer.md:89` shows:
  `--label "kanban:design"` in the `gh pr create` command
- **Doc:** `skills/sprint-run/references/story-execution.md:39` says:
  "Kanban labels are managed by `kanban.py`, not applied directly to PRs."
- **Doc:** `skills/sprint-run/references/kanban-protocol.md:85` says:
  "Never use raw `gh issue edit` for kanban labels -- always use `kanban.py`."
- **Gap:** The implementer.md applies a `kanban:design` label directly via `gh pr create`, bypassing the kanban.py state machine. However, this is a PR label, not an issue label. kanban.py manages issue labels. PR labels are separate.
- **Impact:** Low. The label on the PR is informational. The authoritative kanban state is on the issue, managed by kanban.py. But it could cause confusion if someone reads the PR label as the kanban state. Also, the PR label won't auto-update when the story moves to `dev` or `review`.

---

## Summary

| Severity | Count | IDs |
|----------|-------|-----|
| Medium   | 4     | DOC-1, DOC-2, DOC-3, DOC-18 |
| Low      | 5     | DOC-4, DOC-5, DOC-9, DOC-16, DOC-17 |
| Info     | 5     | DOC-10, DOC-11, DOC-12, DOC-21, DOC-6 |
| Verified | 19+   | (see Verified section) |

**Critical path issues:** DOC-1, DOC-2, DOC-3, and DOC-18 are the most likely to cause agent failures:
- DOC-1: update_burndown.py will exit(2) without sprint number
- DOC-2: sync_tracking.py will exit(2) without sprint number
- DOC-3: gh pr list with wrong label format returns empty results during context recovery
- DOC-18: grep pattern won't match actual SPRINT-STATUS.md format

**Low-impact issues:** DOC-4 through DOC-17 are documentation clarity or
completeness issues that won't cause failures but may cause confusion or
redundant work.
