# Phase 1: Documentation Claims Audit (BH23)

Auditor: Claude Opus 4.6 (1M context)
Date: 2026-03-19
Scope: CLAUDE.md, kanban-protocol.md, story-execution.md, tracking-formats.md, implementer.md, reviewer.md, ceremony docs

---

## Summary

- **13 findings** total
- **3 HIGH** (functional gaps that would block agents)
- **5 MEDIUM** (drift that misleads but has workarounds)
- **5 LOW** (minor drift, cosmetic)

---

### BH23-001: kanban.py update subcommand undocumented in all reference docs
**Severity:** HIGH
**Category:** doc/missing
**Location:** `skills/sprint-run/references/kanban-protocol.md:55`
**Problem:** The kanban protocol says "Use `kanban.py assign` to set fields before `kanban.py transition`." But `assign` only sets `implementer` and `reviewer`. The `dev` state precondition requires `branch` and `pr_number` (kanban-protocol.md line 60), yet no reference doc mentions the `kanban.py update` subcommand that actually sets those fields. The `update` subcommand exists in kanban.py (line 444, `do_update`) and is registered in the CLI parser (line 534), but is invisible to agents following the documented workflow.
**Evidence:** Grepped all files in `skills/sprint-run/references/` and `skills/sprint-run/agents/` for `kanban.py update` -- zero matches. The implementer.md (line 131) says "update the tracking file with `pr_number` and `branch` fields" without providing the command to do so.
**Acceptance Criteria:**
- [ ] kanban-protocol.md documents the `update` subcommand alongside `assign` and `transition`
- [ ] story-execution.md DESIGN->DEV section includes the `kanban.py update` command before the `transition dev` command
- [ ] implementer.md step 1 includes the `kanban.py update` command after PR creation

---

### BH23-002: kanban-protocol.md claims transitions update 3 artifacts, but kanban.py only updates 2
**Severity:** MEDIUM
**Category:** doc/drift
**Location:** `skills/sprint-run/references/kanban-protocol.md:46-49`
**Problem:** The protocol states "Every transition updates three artifacts: 1. GitHub issue label, 2. Story tracking file in `{sprints_dir}/sprint-{N}/`, 3. Sprint status file." However, `do_transition()` in kanban.py (lines 241-282) only performs two updates: it writes the local tracking file via `atomic_write_tf()` (line 261) and swaps GitHub labels (lines 264-266). It never touches SPRINT-STATUS.md or any sprint status file.
**Evidence:** Read kanban.py `do_transition` in full -- no reference to sprint status, burndown, or SPRINT-STATUS.md. The burndown is updated by a separate script (`update_burndown.py`).
**Acceptance Criteria:**
- [ ] kanban-protocol.md accurately describes what `kanban.py transition` actually updates (2 artifacts: local tracking file + GitHub issue label)
- [ ] Document that SPRINT-STATUS.md / burndown updates are a separate step (update_burndown.py)

---

### BH23-003: story-execution.md applies kanban label directly via gh pr edit, contradicting kanban protocol
**Severity:** LOW
**Category:** doc/drift
**Location:** `skills/sprint-run/references/story-execution.md:40-41`
**Problem:** Step 4 of TODO->DESIGN runs `gh pr edit {pr_number} --add-label "persona:{persona},sprint:{N},saga:{saga},priority:{pri},kanban:design"` which applies a `kanban:design` label directly via gh CLI. The kanban protocol (line 76) says "Never use raw `gh issue edit` for kanban labels -- always use `kanban.py`." While technically this labels the PR (not the issue), kanban labels on PRs is confusing and inconsistent with the protocol's intent of centralized state management.
**Evidence:** Read kanban-protocol.md line 76 and story-execution.md line 40. The labels string includes `kanban:design` alongside persona/sprint labels.
**Acceptance Criteria:**
- [ ] story-execution.md removes `kanban:design` from the direct `gh pr edit` label list (the subsequent `kanban.py transition` on line 41 handles the issue label)
- [ ] OR document that PR labels are separate from issue labels and the protocol only governs issue labels

---

### BH23-004: implementer.md hardcodes sprints_dir path instead of using config placeholder
**Severity:** LOW
**Category:** doc/drift
**Location:** `skills/sprint-run/agents/implementer.md:138`
**Problem:** Line 138 says "Write design notes in the story tracking file at `docs/dev-team/sprints/sprint-{N}/stories/{story_file}`." This hardcodes `docs/dev-team/sprints/` instead of using the config-driven `{sprints_dir}` placeholder used elsewhere in the same file and in all other reference docs.
**Evidence:** The `sprints_dir` path comes from `project.toml [paths] sprints_dir` and could be any directory. All other references (story-execution.md, tracking-formats.md, ceremony docs) correctly use `{sprints_dir}`.
**Acceptance Criteria:**
- [ ] implementer.md line 138 uses `{sprints_dir}/sprint-{N}/stories/{story_file}` instead of the hardcoded path

---

### BH23-005: sprint_teardown.py hardcodes docs/dev-team paths in verification phase
**Severity:** MEDIUM
**Category:** doc/drift
**Location:** `scripts/sprint_teardown.py:469-476`
**Problem:** The verification phase after teardown hardcodes `project_root / "docs" / "dev-team"` and `project_root / "docs" / "dev-team" / "sprints"` for integrity checks. CLAUDE.md claims "Config-driven: Nothing is hardcoded to a specific project" but these paths don't read from project.toml. The `print_dry_run` function (lines 170-185) at least attempts to read `sprints_dir` from project.toml, but the main teardown verification doesn't.
**Evidence:** Read sprint_teardown.py lines 469-476 -- the paths are string literals, not config-derived. Compare with `print_dry_run` (lines 170-185) which does attempt config lookup.
**Acceptance Criteria:**
- [ ] Verification phase reads `sprints_dir` from project.toml (or accepts it couldn't parse config since it's being torn down)
- [ ] OR hardcoded paths are documented as fallback heuristics, not assumed to be correct

---

### BH23-006: story-execution.md REVIEW->INTEGRATION step 6 is redundant with kanban.py transition done
**Severity:** LOW
**Category:** doc/drift
**Location:** `skills/sprint-run/references/story-execution.md:148-156`
**Problem:** Step 4 runs `kanban.py transition {story_id} done` which already sets the tracking file status to "done" via `do_transition`. Step 6 then says "Update story tracking file: set status = done, record completion date." The status update is redundant. The completion date is NOT set by kanban.py -- it's only set by sync_tracking.py when it reconciles with GitHub's `closedAt` field. So step 6 is half-redundant and half-impossible via the documented tools.
**Evidence:** Read kanban.py `do_transition` (sets status) and sync_tracking.py `sync_one` (lines 137-141, sets `completed` from `closedAt`). No documented command sets `completed` directly -- `kanban.py update` could do it but is undocumented (see BH23-001).
**Acceptance Criteria:**
- [ ] Step 6 is removed or clarified: status is already set by step 4, completion date is set by sync_tracking.py after issue closure

---

### BH23-007: kanban-protocol.md does not document the update subcommand needed for dev preconditions
**Severity:** HIGH
**Category:** doc/missing
**Location:** `skills/sprint-run/references/kanban-protocol.md:55-63`
**Problem:** The preconditions table says `dev` requires `branch` and `pr_number`. The protocol says "Use `kanban.py assign` to set fields before `kanban.py transition`." But `assign` only handles `implementer` and `reviewer` -- it cannot set `branch` or `pr_number`. The only way to set those fields programmatically is via `kanban.py update --pr-number N --branch NAME`, which is undocumented in the protocol. An agent following the kanban protocol exactly would be unable to satisfy the `dev` precondition.
**Evidence:** Read kanban.py `do_assign` (lines 286-338) -- only accepts `implementer` and `reviewer` params. Read `build_parser` (lines 523-526) -- the `assign` subparser only has `--implementer` and `--reviewer` args. The `update` subparser (lines 534-538) has `--pr-number` and `--branch`.
**Acceptance Criteria:**
- [ ] kanban-protocol.md preconditions section documents how to set `branch` and `pr_number` (via `kanban.py update`)
- [ ] OR kanban-protocol.md explicitly states which subcommand sets each field type

---

### BH23-008: CLAUDE.md claims parse_simple_toml supports "strings, ints, bools, arrays, sections" -- missing float support
**Severity:** LOW
**Category:** doc/drift
**Location:** `CLAUDE.md:126`
**Problem:** CLAUDE.md says parse_simple_toml supports "strings, ints, bools, arrays, sections." The actual implementation (validate_config.py lines 126-219) also handles literal strings (single-quoted), unicode escapes (\u, \U), and unquoted bare strings as a fallback. It does NOT support floats (the `int()` conversion at line 342 would fail, and it falls through to the raw-string fallback). The doc is not wrong per se, but it under-documents the actual capabilities and omits the float gap.
**Evidence:** Read `_parse_value` (lines 303-361). The int path tries `int(raw)` and falls through. There is no float path. Bare unquoted values fall back to raw strings.
**Acceptance Criteria:**
- [ ] CLAUDE.md documents the actual type support: strings (double-quoted with escape processing, single-quoted literal), ints, bools, arrays, bare keys, sections
- [ ] OR note that floats are not supported (returned as raw strings)

---

### BH23-009: CLAUDE.md "Scripts import chain" claim says "four directories up" but this only applies to skill scripts, not all scripts
**Severity:** LOW
**Category:** doc/drift
**Location:** `CLAUDE.md:127`
**Problem:** CLAUDE.md says "All skill scripts do `sys.path.insert(0, ...)` to reach `scripts/validate_config.py` four directories up." This is accurate for skill scripts in `skills/*/scripts/` (e.g., sync_tracking.py, check_status.py, bootstrap_github.py). However, the wording "All skill scripts" is slightly misleading because shared scripts in `scripts/` (kanban.py, sync_backlog.py, sprint_analytics.py, etc.) use `Path(__file__).resolve().parent` (one level), and sync_backlog.py additionally inserts the sprint-setup scripts path.
**Evidence:** Grepped `sys.path.insert` across all Python files. kanban.py uses `.parent` (1 level). sync_backlog.py uses `.parent` + `parent.parent / "skills" / "sprint-setup" / "scripts"`. Only the 5 scripts inside `skills/*/scripts/` use the 4-parent chain.
**Acceptance Criteria:**
- [ ] CLAUDE.md clarifies that the "four directories up" pattern applies specifically to scripts inside `skills/*/scripts/`, not to scripts in the top-level `scripts/` directory

---

### BH23-010: Two-path state management: sync_tracking.py also corrects stale statuses, which overlaps with kanban.py's role
**Severity:** MEDIUM
**Category:** doc/drift
**Location:** `CLAUDE.md:128`
**Problem:** CLAUDE.md says sync_tracking.py is "the reconciliation path (accepts GitHub state for PR linkage, branch, and completion metadata)." But sync_tracking.py's `sync_one` function (line 131) also corrects stale statuses: `if gh_status != tf.status and gh_status in KANBAN_STATES: ... tf.status = gh_status`. This means sync_tracking.py ALSO mutates kanban state (status), which overlaps with kanban.py's documented exclusive role as "the mutation path." The CLAUDE.md description was recently updated to say "For filling in PR/branch fields and correcting stale statuses, use sync_tracking.py" which helps, but the tension remains: both paths can set `status`.
**Evidence:** Read sync_tracking.py `sync_one` lines 130-135 -- status is set directly from GitHub labels without validating the transition is legal. Compare kanban.py `do_transition` which validates transitions. The two paths can produce conflicting states if run concurrently.
**Acceptance Criteria:**
- [ ] CLAUDE.md explicitly acknowledges that both paths can write `status` and documents the precedence rule (sync_tracking accepts any GitHub state; kanban.py validates transitions)
- [ ] OR sync_tracking.py defers status changes to kanban.py (current design intentionally accepts GitHub state)

---

### BH23-011: implementer.md does not tell agents to use kanban.py update for PR/branch metadata
**Severity:** HIGH
**Category:** doc/missing
**Location:** `skills/sprint-run/agents/implementer.md:131`
**Problem:** After step 1 (Create Branch and Draft PR), the implementer.md says "After creating the draft PR, update the tracking file with `pr_number` and `branch` fields. Then transition." But it provides no command for HOW to update those fields. The next command shown is `kanban.py transition {story_id} design` which will succeed (design only requires `implementer`). Later, `kanban.py transition {story_id} dev` (line 142) will FAIL because `dev` requires `branch` and `pr_number` which were never programmatically set. An agent following these instructions literally would get stuck at the dev transition.
**Evidence:** The `kanban.py update` command (kanban.py line 534: `up = sub.add_parser("update", ...)` with `--pr-number` and `--branch` args) exists and works, but is never mentioned in implementer.md. The gap between "update the tracking file" (line 131) and the actual transition command is unbridged.
**Acceptance Criteria:**
- [ ] implementer.md includes `kanban.py update {story_id} --pr-number {N} --branch {branch_name}` after the `gh pr create` step
- [ ] The transition to `dev` follows AFTER the update command

---

### BH23-012: kanban-protocol.md "Rules" section claims sync_tracking.py accepts any kanban label, but kanban.py do_sync validates transitions
**Severity:** MEDIUM
**Category:** doc/drift
**Location:** `skills/sprint-run/references/kanban-protocol.md:36-37`
**Problem:** The Rules section note says "Scripts like `sync_tracking.py` accept any kanban label -- enforcement is the responsibility of the LLM orchestrating the sprint, not the tooling." However, kanban.py's `do_sync` function (lines 342-441) DOES validate transitions from external GitHub state changes: at line 390, it calls `validate_transition(tf.status, github_state)` and rejects illegal transitions with a WARNING. The claim that scripts accept any label is only true for sync_tracking.py's `sync_one`, not for kanban.py's `do_sync`. Since both are used for reconciliation, the blanket statement is misleading.
**Evidence:** kanban.py `do_sync` lines 389-402 calls `validate_transition()` and ignores illegal external transitions. sync_tracking.py `sync_one` lines 130-135 accepts any KANBAN_STATES value without validation.
**Acceptance Criteria:**
- [ ] kanban-protocol.md clarifies that `kanban.py sync` validates transitions while `sync_tracking.py` accepts any valid state
- [ ] OR note that the two sync paths have different validation strictness

---

### BH23-013: CLAUDE.md Configuration System section omits team/history/ and team/insights.md from required structure diagram
**Severity:** MEDIUM
**Category:** doc/drift
**Location:** `CLAUDE.md:94-107`
**Problem:** The Configuration System directory tree shows `team/history/` and `team/insights.md` as part of the config structure, but the `_REQUIRED_FILES` list in validate_config.py (lines 424-437) does not include them. The team/history/ directory is created by `ConfigGenerator.generate_history_dir()` (sprint_init.py line 812) but is never validated. The `insights.md` file is created during kickoff ceremony (not during init). This is actually fine behavior -- they're optional runtime files, not required config. But the diagram presents them alongside required files without distinguishing required from optional.
**Evidence:** Read `_REQUIRED_FILES` (validate_config.py lines 424-437): lists project.toml, team/INDEX.md, backlog/INDEX.md, rules.md, development.md, definition-of-done.md. No history/ or insights.md. The directory tree in CLAUDE.md lists them at the same indentation level as required files.
**Acceptance Criteria:**
- [ ] CLAUDE.md directory tree annotates which entries are required vs. created at runtime
- [ ] OR add a note distinguishing required (validated at startup) from runtime (created during ceremonies)
