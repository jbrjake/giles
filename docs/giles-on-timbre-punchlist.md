# Giles on Timbre — Punchlist

Actionable improvements distilled from the Timbre case study (`docs/giles-on-timbre.md`).
Sorted by descending priority within each enforcement mechanism group.

**Design principle:** Structural enforcement over behavioral aspiration.
Documents record lessons. Prompts enforce them. Hooks make enforcement inescapable.

**Autonomy constraint:** No item requires a human in the loop for validation.
Every acceptance criterion is programmatically verifiable.

---

## Group 1: Hooks (PreToolUse / SubagentStop / SessionStart)

Hooks are the highest-leverage items. They are structural constraints the LLM
cannot bypass. The plugin currently has zero hooks.

### P0-HOOK-1: Review Gate Hook (PreToolUse)

Intercept `gh pr merge` and direct pushes to the base branch. Block merge if
the PR has no APPROVED review. Direct fix for Sprint 1's 7/11 skipped reviews.

**Implementation steps:**
1. Create `.claude-plugin/hooks/review-gate.py`
2. Register as PreToolUse hook in `plugin.json` for Bash tool calls
3. Parse command arguments — detect `gh pr merge`, `git push origin {base_branch}`, `git merge`
4. For PR merges: query `gh pr view {number} --json reviewDecision` — block if not APPROVED
5. For direct pushes to base branch: block unconditionally with message directing to PR workflow
6. Allow bypass when the user (not the agent) has explicitly approved the PR via GitHub
7. Log all blocked attempts to `sprint-config/sprints/hook-audit.log`
8. Add tests using FakeGitHub pattern from existing test suite

**Acceptance criteria:**
- [ ] `python -c "from hooks.review_gate import check_merge; assert check_merge('gh pr merge 42 --squash', base='main') == 'blocked'" ` passes when PR #42 has no approved review (mocked)
- [ ] `python -c "from hooks.review_gate import check_merge; assert check_merge('gh pr merge 42 --squash', base='main') == 'allowed'"` passes when PR #42 has APPROVED review (mocked)
- [ ] `python -c "from hooks.review_gate import check_push; assert check_push('git push origin main', base='main') == 'blocked'"` passes for direct push to base branch
- [ ] Hook registered in `plugin.json` under `hooks` array with `event: "PreToolUse"`, `tool: "Bash"`
- [ ] Blocked attempts produce a message containing "review" and "required" (not a silent failure)

---

### P0-HOOK-2: SubagentStop Verification Hook

When an implementer or fix agent completes, automatically run the project's
`check_commands` and compare results against the agent's claims. If the agent
says "tests pass" but the suite fails, block acceptance and inject failure
output. Addresses Sprint 4's "prescribe-don't-verify" pattern.

**Implementation steps:**
1. Create `.claude-plugin/hooks/verify-agent-output.py`
2. Register as SubagentStop hook in `plugin.json`
3. On agent completion, read `sprint-config/project.toml` for `[ci] check_commands`
4. Run each check command, capture exit codes and stdout/stderr
5. If any command fails: inject failure output into conversation with "VERIFICATION FAILED: agent claimed completion but {command} exited {code}"
6. If all commands pass: inject "VERIFICATION PASSED: {N} check commands confirmed" as confirmation
7. Track verification results in the story's tracking file under a `verification` key
8. If `smoke_command` is configured (see P1-SCRIPT-1), run that too

**Acceptance criteria:**
- [ ] Hook registered in `plugin.json` with `event: "SubagentStop"`
- [ ] Given a project.toml with `check_commands = ["python -m pytest"]`, the hook runs pytest and captures the result
- [ ] When a check command exits non-zero, the hook output contains "VERIFICATION FAILED" and the command's stderr
- [ ] When all check commands exit zero, the hook output contains "VERIFICATION PASSED"
- [ ] Results are written to the story tracking file's YAML frontmatter under `verification.agent_stop`

---

### P0-HOOK-3: SessionStart Context Injection Hook

At conversation start, inject retro action items, DoD semantic additions, and
unresolved risk register entries as unavoidable prompt context. Addresses
"process documents don't change behavior" — makes retro learnings part of the
prompt, not a file the agent might skip.

**Implementation steps:**
1. Create `.claude-plugin/hooks/session-context.py`
2. Register as SessionStart hook in `plugin.json`
3. Read the most recent `{sprints_dir}/sprint-{N}/retro.md` — extract "Action Items for Next Sprint" table
4. Read `sprint-config/definition-of-done.md` — extract items marked as retro-driven additions
5. Read `sprint-config/risk-register.md` (see P2-STATE-2) — extract unresolved risks with severity >= high
6. Read integration debt metric from SPRINT-STATUS.md (see P1-SCRIPT-4)
7. Format as a compact summary (target: <50 lines to avoid context bloat)
8. Return as hook output that gets injected into conversation context

**Acceptance criteria:**
- [ ] Hook registered in `plugin.json` with `event: "SessionStart"`
- [ ] Given a retro.md with 3 action items, the hook output contains all 3 items
- [ ] Given a risk-register.md with 2 high-severity open risks, the hook output contains both
- [ ] Hook output is under 60 lines (measured by `wc -l` on output)
- [ ] When no retro.md exists (first sprint), hook exits cleanly with no output

---

### P1-HOOK-4: Direct Push Prevention (PreToolUse)

Block `git push` to the base branch unless it's a merge-commit push from a PR.
Sprint-monitor currently detects direct pushes after the fact; this prevents
them.

**Implementation steps:**
1. Extend `.claude-plugin/hooks/review-gate.py` to handle direct push detection
2. Parse `git push` arguments for target ref matching base_branch from project.toml
3. Block with message: "Direct push to {base_branch} is not allowed. Create a PR."
4. Allow `git push origin {feature-branch}` (non-base-branch pushes) unconditionally
5. Allow `git push` when the current branch is not the base branch

**Acceptance criteria:**
- [ ] `git push origin main` (when main is base_branch) is blocked by hook
- [ ] `git push origin sprint-1/ST-0001-some-feature` is allowed
- [ ] `git push -u origin sprint-1/ST-0001-some-feature` is allowed
- [ ] Block message contains "PR" and the base branch name

---

### P1-HOOK-5: Commit Verification Hook (PreToolUse)

Before allowing `git commit`, verify that at least one check_command has been
run since the last code change. Enforces TDD discipline structurally — agents
cannot commit without running tests.

**Implementation steps:**
1. Create `.claude-plugin/hooks/commit-gate.py`
2. Register as PreToolUse hook for Bash tool calls matching `git commit` or `scripts/commit.py`
3. Track state: on Write/Edit tool calls to source files, set `needs_verification = true`
4. On Bash calls matching check_commands patterns, set `needs_verification = false`
5. On commit attempt: if `needs_verification == true`, block with "Tests have not been run since the last code change. Run check_commands before committing."
6. Use a temp file at `/tmp/giles-verification-state-{session}` for state tracking between hook invocations

**Acceptance criteria:**
- [ ] Hook blocks `git commit` when source files were modified but no check_command was run
- [ ] Hook allows `git commit` when check_commands were run after the last source modification
- [ ] Hook does not block commits when only non-source files changed (markdown, config)
- [ ] Source file detection uses language-appropriate patterns (`.py`, `.swift`, `.rs`, `.ts`, etc.)
- [ ] State file is session-scoped (cleaned up on session end)

---

## Group 2: Kanban State Machine Extensions (kanban.py)

Extending the existing hard enforcement with new preconditions and transition
rules.

### P0-KANBAN-1: Enforce REVIEW Gate (Block DEV → DONE / DEV → INTEGRATION)

Make the REVIEW state mandatory in the transition path. Currently the legal
transition set allows paths that skip REVIEW. Add strict enforcement: the only
path to DONE goes through REVIEW → INTEGRATION.

**Implementation steps:**
1. In `kanban.py`, modify `TRANSITIONS` dict: remove `dev` → `integration` and `dev` → `done` as legal transitions
2. Add `review` → `integration` and `integration` → `done` as the only forward path from `review`
3. Keep `dev` → `review` as the only forward transition from `dev`
4. Keep backward transitions (`review` → `dev` for fix rounds) as-is
5. Update `validate_transition()` to reject the removed paths with clear error messages
6. Add transition history to the tracking file YAML: `transition_log: [{from, to, timestamp}]`
7. Update tests in `test_kanban.py` to verify the new stricter transition rules

**Acceptance criteria:**
- [ ] `kanban.py transition {story} integration` from `dev` state exits non-zero with error containing "must pass through review"
- [ ] `kanban.py transition {story} done` from `dev` state exits non-zero with error containing "must pass through review"
- [ ] `kanban.py transition {story} review` from `dev` state succeeds
- [ ] `kanban.py transition {story} integration` from `review` state succeeds
- [ ] Transition log is written to tracking file and contains all state changes with timestamps
- [ ] All existing tests pass; new tests cover the blocked transitions

---

### P1-KANBAN-2: Review Round Counter with Escalation

Track review round count in the story tracking file. After 3
CHANGES_REQUESTED → DEV cycles, block the next transition and inject an
escalation message. Currently advisory in kanban-protocol.md.

**Implementation steps:**
1. Add `review_rounds: 0` to story tracking file YAML frontmatter
2. In `kanban.py do_transition()`, increment `review_rounds` on each `review` → `dev` transition
3. On the 4th `review` → `dev` attempt (round > 3), block the transition
4. Print escalation message: "Story {id} has had {N} review rounds. The review-dev cycle may indicate a design issue. Escalate to the user before continuing."
5. Add `--force-review-round` flag to allow the user to explicitly override
6. Report review round counts in `sprint_analytics.py compute_review_rounds()`

**Acceptance criteria:**
- [ ] After 3 `review` → `dev` transitions, the 4th is blocked with escalation message
- [ ] `kanban.py transition {story} dev --force-review-round` overrides the block
- [ ] `review_rounds` field is present and accurate in the story tracking file
- [ ] `sprint_analytics.py` reports max and average review rounds per sprint

---

### P1-KANBAN-3: WIP Limit Enforcement

Before allowing a story to transition to DEV, check how many stories the
assigned implementer already has in DEV state. Block if the persona already
has one in-flight.

**Implementation steps:**
1. In `kanban.py check_preconditions()`, add a check for the `dev` target state
2. Read all tracking files in the sprint directory
3. Count stories where `status: dev` and `implementer` matches the current story's implementer
4. If count >= 1, block with "WIP limit reached: {persona} already has {story_id} in dev. Complete or park it first."
5. Add `--force-wip` flag for explicit user override
6. Make the WIP limit configurable: read from project.toml `[conventions] wip_limit = 1` (default 1)

**Acceptance criteria:**
- [ ] With one story in `dev` for persona X, transitioning a second story to `dev` for persona X is blocked
- [ ] The block message names the conflicting story
- [ ] `--force-wip` overrides the block
- [ ] Different personas are independent (persona Y can enter dev while persona X has a story in dev)
- [ ] WIP limit reads from project.toml if configured, defaults to 1

---

## Group 3: New Scripts

New capabilities the plugin doesn't have today.

### P0-SCRIPT-1: Smoke Test Runner (`scripts/smoke_test.py`)

Reads `[ci] smoke_command` from project.toml, runs it, reports pass/fail. The
autonomous equivalent of "launch the app and see if it works." This is the
single most important new script — it closes the integration verification gap
without requiring a human to look at a screen.

**Implementation steps:**
1. Create `scripts/smoke_test.py`
2. Add `smoke_command` as optional key under `[ci]` in `validate_config.py` schema
3. Read smoke_command from project.toml via `load_config()`
4. Execute the command with a configurable timeout (default 30s, configurable via `[ci] smoke_timeout`)
5. Capture exit code, stdout, stderr
6. Report: `SMOKE PASS` (exit 0) or `SMOKE FAIL` (exit non-zero) with output
7. If smoke_command is not configured, report `SMOKE SKIP: no smoke_command in project.toml`
8. Write result to `{sprints_dir}/smoke-history.md` with timestamp, commit hash, and result
9. Add `smoke_command` to `references/skeletons/project.toml.tmpl` with a comment explaining its purpose
10. Wire into sprint-monitor (`check_status.py`) as a new step
11. Wire into demo ceremony as a pre-demo gate

**Acceptance criteria:**
- [ ] `python scripts/smoke_test.py --config sprint-config/project.toml` runs the configured command and prints SMOKE PASS or SMOKE FAIL
- [ ] Exit code is 0 for PASS, 1 for FAIL, 2 for SKIP (not configured)
- [ ] Timeout kills the process and reports SMOKE FAIL with "timed out after {N}s"
- [ ] Smoke history file is appended with each run (not overwritten)
- [ ] `validate_config.py` accepts `smoke_command` as an optional string key under `[ci]`
- [ ] `project.toml.tmpl` includes a commented-out `smoke_command` example

---

### P0-SCRIPT-2: Gap Scanner (`scripts/gap_scanner.py`)

Analyze the current sprint's stories against the codebase entry points.
Flag sprints where stories modify subsystems but no story touches the
integration layer. Catches the "all components, no wiring" blindspot.

**Implementation steps:**
1. Create `scripts/gap_scanner.py`
2. Add optional `[project] entry_points` list to project.toml schema (list of file paths)
3. Read all story tracking files for the current sprint — extract acceptance criteria text and modified-file hints
4. For each entry point, check: does any story's acceptance criteria or branch diff touch this file?
5. Keyword scan: if sprint stories contain words like "visible," "display," "render," "launch," "screen," "user" but no story touches entry point files, flag a gap
6. Report format: `GAP DETECTED: N stories modify subsystems, 0 stories touch entry points [{files}]`
7. Report format (clean): `NO GAP: story {id} touches entry point {file}`
8. Integrate with kickoff ceremony — sprint-run SKILL.md calls gap_scanner after story walk

**Acceptance criteria:**
- [ ] Given entry_points = ["src/main.py"] and 5 stories none of which touch src/main.py, output contains "GAP DETECTED"
- [ ] Given entry_points = ["src/main.py"] and 1 story that touches src/main.py, output contains "NO GAP"
- [ ] When entry_points is not configured, output contains "SKIP: no entry_points configured"
- [ ] Keyword scan detects stories with user-facing language that lack integration wiring
- [ ] Exit code: 0 for no gap or skip, 1 for gap detected

---

### P1-SCRIPT-3: Test Category Analyzer (`scripts/test_categories.py`)

Categorize tests as unit/component/integration/smoke by heuristic. Report the
distribution. Flag when integration test count is zero.

**Implementation steps:**
1. Create `scripts/test_categories.py`
2. Accept test output (from check_commands) or scan test directories
3. Categorize by heuristic: directory structure (`tests/integration/`, `tests/e2e/`), import graph depth (single module = unit, multiple = integration), test naming patterns (`test_integration_*`, `test_e2e_*`), and configurable overrides in project.toml `[testing] integration_dirs`, `[testing] smoke_dirs`
4. Report distribution: `Unit: 487 (66%), Component: 252 (34%), Integration: 0 (0%), Smoke: 0 (0%)`
5. Flag: `WARNING: 0 integration tests detected` when integration count is zero
6. Track skipped tests separately: `GPU-skipped: 115 (not executed in CI)`
7. Wire into `sprint_analytics.py` to include in sprint analytics report
8. Wire into demo ceremony to include in demo metrics

**Acceptance criteria:**
- [ ] Given a test directory with `tests/unit/` and `tests/integration/` subdirs, correctly counts tests in each category
- [ ] When integration test count is 0, output contains "WARNING" and "0 integration"
- [ ] Skipped tests (detected by parsing test output for "skipped" or "skip") are reported separately
- [ ] Exit code: 0 for healthy distribution, 1 for zero integration tests
- [ ] Output is machine-parseable (one key: value pair per line or JSON)

---

### P1-SCRIPT-4: Integration Debt Metric (extend `update_burndown.py`)

Track the number of sprints since the product was last verified to work via
smoke test. Display in SPRINT-STATUS.md. Sprint-monitor escalates when
debt > 2 sprints.

**Implementation steps:**
1. Add `integration_debt` field to SPRINT-STATUS.md format
2. In `update_burndown.py`, read smoke history file (`smoke-history.md`)
3. Find the most recent SMOKE PASS entry. Count sprints since that entry.
4. Write `Integration Debt: {N} sprints` to SPRINT-STATUS.md
5. In `check_status.py`, read integration_debt. If > 2, report as HIGH severity finding.
6. If smoke_command is not configured, report integration_debt as "unknown (no smoke_command)"

**Acceptance criteria:**
- [ ] SPRINT-STATUS.md contains `Integration Debt: N sprints` line
- [ ] When the most recent smoke pass was 3 sprints ago, debt = 3
- [ ] When smoke passed this sprint, debt = 0
- [ ] `check_status.py` output contains "HIGH" when debt > 2
- [ ] When no smoke history exists, debt is reported as "unknown"

---

### P1-SCRIPT-5: Integration Health in Sprint Monitor (extend `check_status.py`)

Add a step to sprint-monitor that runs the smoke command on the base branch
after each merge. Track pass/fail history. Flag the exact merge that broke
integration health.

**Implementation steps:**
1. Add `check_smoke()` function to `check_status.py`
2. After `check_ci()` and before `check_prs()`, run `smoke_test.py`
3. Compare result against the last smoke check result (from smoke-history.md)
4. If smoke transitioned from PASS to FAIL, identify the most recent merge to base branch and flag it: `INTEGRATION REGRESSION: smoke test failed after PR #{N} ({title})`
5. Include smoke status in the monitor's summary output
6. Add rate limiting: only run smoke check if it hasn't been run in the last 10 minutes (to avoid redundant builds during rapid merges)

**Acceptance criteria:**
- [ ] `check_status.py` output includes smoke test result when smoke_command is configured
- [ ] When smoke test transitions PASS → FAIL, output contains "INTEGRATION REGRESSION" and the causal PR number
- [ ] Smoke check respects rate limiting (does not re-run within 10 minutes of last check)
- [ ] When smoke_command is not configured, the step is silently skipped

---

## Group 4: Ceremony Prompt Modifications

Changes to ceremony reference files. Less reliable than hooks but still
high-value — they shape the LLM's attention during the most important
decision points.

### P0-CEREMONY-1: Kickoff — Mandatory User-Facing Delta Question

Before the story walk, PM must answer: "What does the user see or experience
after this sprint that they didn't before?" If the answer is "nothing" and
the sprint is not explicitly declared foundational, flag a gap.

**Implementation steps:**
1. In `ceremony-kickoff.md`, add a new section before "Story Walk" titled "User-Facing Delta"
2. Template: "**PM declares the user-facing delta:** After this sprint, the user will see/experience: ___. If the delta is 'nothing new' (foundational sprint), declare it: 'This sprint is foundational. No user-visible change expected.'"
3. Add to exit criteria: "User-facing delta has been declared and at least one story maps to it (unless foundational)"
4. In `SKILL.md` phase detection, reference the new section
5. If the sprint is declared foundational, record it in SPRINT-STATUS.md as `type: foundational`

**Acceptance criteria:**
- [ ] `ceremony-kickoff.md` contains a "User-Facing Delta" section with the template text
- [ ] Exit criteria list includes user-facing delta verification
- [ ] The word "foundational" appears as an explicit option in the template

---

### P0-CEREMONY-2: Kickoff — Gap Scan Integration

After the story walk, run `gap_scanner.py` and present results. Gaps must be
addressed (add integration story or explicitly defer with rationale) before
commitment.

**Implementation steps:**
1. In `ceremony-kickoff.md`, add a section after "Story Walk" titled "Integration Gap Scan"
2. Instruction: "Run `python scripts/gap_scanner.py --config sprint-config/project.toml --sprint {N}`. Present results. If GAP DETECTED, discuss: add an integration story, or defer with explicit rationale recorded in kickoff notes."
3. Add to exit criteria: "Gap scanner has run. Any detected gaps have been addressed or explicitly deferred."
4. Reference `gap_scanner.py` in `SKILL.md` context assembly

**Acceptance criteria:**
- [ ] `ceremony-kickoff.md` contains "Integration Gap Scan" section
- [ ] Section references the gap_scanner.py script with correct invocation
- [ ] Exit criteria include gap scanner verification

---

### P0-CEREMONY-3: Demo — Smoke Test Gate Before Story Presentations

Before story presentations, run smoke_test.py. If it fails, the demo opens
with "the product does not run" — not with story showcases.

**Implementation steps:**
1. In `ceremony-demo.md`, add a new Step 0 before "Build Verification" titled "Smoke Gate"
2. Instruction: "Run `python scripts/smoke_test.py`. If SMOKE FAIL, the demo cannot proceed to story presentations. Open with: 'The product does not run. Before we discuss individual stories, we need to address this.' If SMOKE SKIP (not configured), note it and proceed."
3. Add smoke test result to demo-artifacts/ as `smoke-result.txt`
4. If smoke passes, record in demo doc: "Smoke gate: PASSED"

**Acceptance criteria:**
- [ ] `ceremony-demo.md` contains "Smoke Gate" as Step 0 (before Build Verification)
- [ ] Section specifies that SMOKE FAIL blocks story presentations
- [ ] Smoke result is saved to demo-artifacts/

---

### P1-CEREMONY-4: Kickoff — Previous Sprint Verification

Before discussing new stories, run `smoke_test.py` to verify the previous
sprint's output still works. If it fails, that's the first agenda item.

**Implementation steps:**
1. In `ceremony-kickoff.md`, add a section before "User-Facing Delta" titled "Previous Sprint Health"
2. Instruction: "Run `python scripts/smoke_test.py`. If SMOKE FAIL, discuss immediately: the foundation is broken and must be fixed before new work begins. Add a fix story to the sprint."
3. Also run check_commands and report any failures

**Acceptance criteria:**
- [ ] `ceremony-kickoff.md` contains "Previous Sprint Health" section as the first substantive step
- [ ] Section runs smoke_test.py and check_commands

---

### P1-CEREMONY-5: Retro — Structural Encoding Step

After producing action items, classify each as "structural" (encodable as a
hook, script, precondition, or prompt change) or "behavioral" (requires LLM
discipline). For structural items, specify WHERE the encoding should happen.

**Implementation steps:**
1. In `ceremony-retro.md`, add a section after "Action Items" titled "Structural Encoding"
2. Template: "For each action item, classify: **Structural** (can be enforced by hook/script/precondition — specify which file to modify) or **Behavioral** (relies on LLM discipline — mark as at-risk). Target: >50% structural."
3. Record classification in retro output table with columns: Item | Classification | Encoding Target
4. Feed into SessionStart hook (P0-HOOK-3): unresolved behavioral items are injected as warnings

**Acceptance criteria:**
- [ ] `ceremony-retro.md` contains "Structural Encoding" section after action items
- [ ] Template includes classification options with encoding target field
- [ ] Template includes the >50% structural target

---

### P1-CEREMONY-6: Retro — Principle Extraction Step

Instead of O(n) rules per mistake, extract O(1) principles per category.
Template asks: "These action items are instances of what broader category?"
Stores the principle alongside the specific items.

**Implementation steps:**
1. In `ceremony-retro.md`, add a section after "Structural Encoding" titled "Principle Extraction"
2. Template: "Review the action items as a group. Are any of them instances of the same broader principle? If so, name the principle and record it. Principles are more durable than rules — 'the app target is a different artifact than the library' catches multiple bugs that individual rules would catch one at a time."
3. Record principles in a `## Principles` section of the retro doc
4. Principles carry forward to SessionStart hook context alongside action items

**Acceptance criteria:**
- [ ] `ceremony-retro.md` contains "Principle Extraction" section
- [ ] Template includes the example principle from the Timbre case study
- [ ] Principles section is a distinct output artifact in the retro doc format

---

### P1-CEREMONY-7: Retro — Standing Integration Questions

Add permanent questions that force system-level reflection every retro,
regardless of whether anyone thinks to ask them.

**Implementation steps:**
1. In `ceremony-retro.md`, add a "Standing Questions" section (always asked, not conditional)
2. Questions:
   - "Did we verify the product launches this sprint? What was the smoke test result?"
   - "What test categories are missing? (Check test_categories.py output)"
   - "Which retro action items from last sprint were structurally encoded vs merely documented?"
   - "What failure mode have we not yet experienced but could? (Forward-looking risk)"
3. Record answers in retro output

**Acceptance criteria:**
- [ ] `ceremony-retro.md` contains "Standing Questions" section with all 4 questions
- [ ] Section is marked as mandatory (not conditional on sprint outcomes)

---

### P2-CEREMONY-8: Retro — Within-Sprint Failure Analysis

For each time during the sprint that something was claimed fixed but wasn't,
analyze the pattern. Separate from Start/Stop/Continue — this is about the
fix-verify-fix loop.

**Implementation steps:**
1. In `ceremony-retro.md`, add "Fix Failure Analysis" section
2. Template: "For each failed fix attempt this sprint: What was claimed? What evidence supported the claim? What evidence would have refuted it? What is the general principle? What checklist item prevents the category?"
3. Feed identified principles into Principle Extraction step

**Acceptance criteria:**
- [ ] `ceremony-retro.md` contains "Fix Failure Analysis" section with the 5-question template
- [ ] Section appears before "Principle Extraction" so its output feeds into principle identification

---

## Group 5: Agent Prompt Modifications

Changes to implementer.md and reviewer.md that add required verification
steps and structural self-awareness.

### P0-AGENT-1: Implementer — Verification Scope Declaration

Require the implementer's completion message to include an explicit
"Verification Scope" section listing what was tested and what was NOT tested.

**Implementation steps:**
1. In `implementer.md`, add to the "Completion" section: "Your completion message MUST include a Verification Scope section with two lists: VERIFIED (commands you ran and their results) and NOT VERIFIED (things you did not check — other build targets, app launch, system logs, etc.)"
2. Specify format: `## Verification Scope\n### Verified\n- swift build (exit 0)\n- swift test (109 passed)\n### Not Verified\n- xcodebuild (app target)\n- app launch\n- system logs`
3. The SubagentStop hook (P0-HOOK-2) can parse this section to determine verification scope coverage

**Acceptance criteria:**
- [ ] `implementer.md` contains "Verification Scope" requirement in the completion section
- [ ] Template includes both VERIFIED and NOT VERIFIED lists with examples
- [ ] The NOT VERIFIED list is explicitly required (not optional)

---

### P0-AGENT-2: Implementer — Raw Evidence Requirement

Require the implementer's completion message to include actual command output,
not interpretation. "Tests pass" is interpretation. The raw test output is
evidence.

**Implementation steps:**
1. In `implementer.md`, add: "Your completion message MUST include the raw output of the last test/build run. Do not summarize. Paste the actual output. If the output exceeds 50 lines, include the first 10 and last 10 lines with a count of omitted lines."
2. Specify: "Statements like 'tests pass' or 'clean build' without raw output will be rejected by the verification hook."

**Acceptance criteria:**
- [ ] `implementer.md` contains raw evidence requirement
- [ ] Requirement specifies truncation rules for long output (first 10 + last 10)
- [ ] Requirement explicitly says "do not summarize"

---

### P1-AGENT-3: Reviewer — Integration Impact Check

Add to the reviewer checklist: "Does this story modify a subsystem that an
entry point depends on? If yes, is there evidence that the entry point still
works?"

**Implementation steps:**
1. In `reviewer.md`, add checklist item 10: "**Integration impact:** If this story modifies code that the app entry point depends on (check `[project] entry_points` in project.toml), verify that the entry point still compiles/runs. If you cannot verify this, flag it in your review as 'integration impact not verified.'"
2. Add to the three-pass review structure: this belongs in Pass 1 (Correctness)

**Acceptance criteria:**
- [ ] `reviewer.md` contains integration impact checklist item
- [ ] Checklist item references `entry_points` from project.toml
- [ ] Checklist item specifies what to do when verification is not possible (flag it)

---

### P1-AGENT-4: Reviewer — Abstraction Fit Check

For stories adding protocol conformers or interface implementations, verify
the abstraction works for the new conforming type — not just that it compiles.

**Implementation steps:**
1. In `reviewer.md`, add checklist item 11: "**Abstraction fit:** If this story adds a conformer to a protocol/interface, verify: Does the protocol's contract (method signatures, documented semantics) actually make sense for this conforming type? Flag cases where the conformer technically compiles but the semantics are wrong (e.g., `outputTexture` returning velocity data when the protocol says 'result for compositing')."

**Acceptance criteria:**
- [ ] `reviewer.md` contains abstraction fit checklist item
- [ ] Checklist item includes the Timbre example (outputTexture/velocity) as illustration

---

### P1-AGENT-5: Implementer — Silent Failure Audit

Before marking a story complete, the implementer must ask: "What would happen
if this code silently failed? Would there be any observable symptom?" If the
answer is "no symptom," add a log statement or assertion.

**Implementation steps:**
1. In `implementer.md`, add to the pre-completion checklist: "**Silent failure audit:** For each new code path, ask: 'If this silently fails (returns nil, no-ops, throws and is caught), would anything observable happen?' If the answer is no, add a log statement at warning level or a precondition assertion. Silent failures are the hardest bugs to find."

**Acceptance criteria:**
- [ ] `implementer.md` contains silent failure audit step
- [ ] Step is in the pre-completion checklist (before PR creation, not after)

---

### P1-AGENT-6: Implementer — Generalization Reflex for Fix Stories

After fixing a bug, the implementer must ask: "This bug is an instance of
what broader category? What other things in the same category might be wrong?"
and sweep for related issues.

**Implementation steps:**
1. In `implementer.md`, add a section for fix stories: "**For fix stories only — Generalization Reflex:** After fixing the specific bug, ask: 'This is an instance of what broader category?' Then search the codebase for other instances of the same category. Example: fixing a missing plist key should trigger checking for ALL required plist keys, not just the one that was missing."
2. Require the sweep results to be included in the PR description

**Acceptance criteria:**
- [ ] `implementer.md` contains "Generalization Reflex" section
- [ ] Section is conditional on fix stories (not required for feature stories)
- [ ] Section requires sweep results in PR description

---

## Group 6: Config Schema & Persistent State

New fields and files that enable the enforcement mechanisms above.

### P0-STATE-1: project.toml — `smoke_command` and `entry_points` Fields

Add the config fields that multiple scripts and hooks depend on.

**Implementation steps:**
1. In `validate_config.py`, add `smoke_command` as optional string key under `[ci]`
2. Add `smoke_timeout` as optional int key under `[ci]` (default 30)
3. Add `entry_points` as optional list key under `[project]`
4. Update `references/skeletons/project.toml.tmpl` with commented examples:
   ```
   # smoke_command = "python -m myapp --health-check"
   # smoke_timeout = 30
   ```
   and:
   ```
   # entry_points = ["src/main.py", "src/app.py"]
   ```
5. Update CLAUDE.md tables to document the new keys

**Acceptance criteria:**
- [ ] `validate_config.py` accepts `smoke_command`, `smoke_timeout`, and `entry_points` without error
- [ ] Missing keys do not cause validation failure (they are optional)
- [ ] `project.toml.tmpl` contains commented examples for all three keys
- [ ] `load_config()` returns the new keys when present

---

### P1-STATE-2: Risk Register (`sprint-config/risk-register.md`)

Persistent file tracking risks across sprints. SessionStart hook reads it.
Kickoff ceremony reviews it. Sprint-monitor reports unresolved high risks.

**Implementation steps:**
1. Create `references/skeletons/risk-register.md.tmpl` with format:
   ```
   # Risk Register
   | ID | Title | Severity | Status | Raised | Sprints Open | Resolution |
   |----|-------|----------|--------|--------|-------------|------------|
   ```
2. In `sprint_init.py`, generate risk-register.md from template during setup
3. Add helper functions in a new `scripts/risk_register.py`: `add_risk()`, `resolve_risk()`, `list_open_risks()`, `escalate_overdue(threshold=2)`
4. Wire into `ceremony-kickoff.md`: review open risks at kickoff
5. Wire into `ceremony-retro.md`: add new risks identified during sprint
6. Wire into SessionStart hook: inject high-severity open risks
7. Wire into `check_status.py`: report overdue risks (open > 2 sprints)

**Acceptance criteria:**
- [ ] `risk_register.py add_risk --title "No integration tests" --severity high` adds a row to risk-register.md
- [ ] `risk_register.py list_open_risks` outputs open risks in table format
- [ ] `risk_register.py escalate_overdue --threshold 2` exits non-zero when risks are overdue
- [ ] risk-register.md template is in skeletons/

---

### P1-STATE-3: Verification Scope in Story Tracking Files

Add a `verification` section to story tracking file YAML to make scope gaps
visible as structured data.

**Implementation steps:**
1. In `sync_tracking.py create_from_issue()`, add `verification: {agent: [], orchestrator: [], unverified: []}` to the tracking file template
2. In `kanban.py do_update()`, support updating verification fields: `kanban.py update {story} --set verification.agent="swift build,swift test"`
3. SubagentStop hook (P0-HOOK-2) writes to `verification.agent` automatically
4. Document the verification fields in `tracking-formats.md`

**Acceptance criteria:**
- [ ] New story tracking files contain a `verification` section in YAML frontmatter
- [ ] `kanban.py update` can set verification fields
- [ ] `tracking-formats.md` documents the verification section format

---

### P1-STATE-4: Session-Level Learning Checklist

Within a sprint-run session, maintain a running checklist of verification
steps learned from within-session failures. Reviewed before every claim
to the user.

**Implementation steps:**
1. In `sprint-run/SKILL.md`, add a "Session Learning" section
2. Instruction: "Maintain a session checklist. When a fix attempt fails, add the verification step that would have caught it. Before every subsequent claim to the user, review the checklist. The checklist does not persist to disk — it exists only in the current session's context."
3. Template: `## Session Checklist\n- [ ] Check system logs after every fix\n- [ ] Verify all build targets, not just the library`
4. The checklist starts empty and grows as the session encounters failures

**Acceptance criteria:**
- [ ] `sprint-run/SKILL.md` contains "Session Learning" section with checklist instructions
- [ ] Template specifies that the checklist is context-only (not persisted to disk)
- [ ] Template specifies review timing: "before every claim to the user"

---

### P2-STATE-5: Automated DoD Level Assignment

Keyword analysis of story acceptance criteria at kickoff. Stories mentioning
user-facing keywords get app DoD (heavier verification). Others get library
DoD.

**Implementation steps:**
1. Create `scripts/assign_dod_level.py`
2. Read story tracking files for the current sprint
3. Scan acceptance criteria text for keywords: "visible," "display," "launch," "screen," "render," "user," "window," "UI," "app"
4. Assign `dod_level: app` (if keywords found) or `dod_level: library` (if not)
5. Write assignment to tracking file YAML
6. Report: "Sprint {N}: {X} stories at app DoD, {Y} stories at library DoD"
7. Wire into kickoff ceremony: run after story walk, before commitment
8. At story completion, SubagentStop hook checks dod_level and runs smoke_command for `app` level stories

**Acceptance criteria:**
- [ ] Given a story with acceptance criteria "user sees bloom effect on screen," `dod_level` is assigned as `app`
- [ ] Given a story with acceptance criteria "FFT window size configurable," `dod_level` is assigned as `library`
- [ ] Assignment is written to tracking file YAML
- [ ] Report output shows counts of each level

---

### P2-STATE-6: Persona History → Review Checklist Generator

Parse persona history files and auto-generate domain-specific review
checklist items. If Sana's history says "ARC callback bug in audio capture,"
her reviews automatically include "check for ARC traffic in callback paths."

**Implementation steps:**
1. Create `scripts/history_to_checklist.py`
2. Read `{team_dir}/history/{persona}.md` for each persona
3. Extract patterns: look for "bug," "issue," "caught," "fixed," "found" near technical terms
4. Generate checklist items: "{persona} history: check for {pattern} (from Sprint {N})"
5. Output as a markdown checklist that can be injected into the reviewer's context
6. Wire into sprint-run agent dispatch: when dispatching a reviewer, include their generated checklist
7. Update with each retro as new history entries are written

**Acceptance criteria:**
- [ ] Given a history file containing "Sprint 1: caught ARC callback violation in audio capture," generates a checklist item containing "ARC" and "callback"
- [ ] Output is valid markdown checklist format
- [ ] Script handles missing or empty history files gracefully

---

### P2-STATE-7: Escalation Protocol for Repeated Failures

After 2 failures in the same category within a sprint, stop story execution
and trigger a mini-retro before attempting fix #3.

**Implementation steps:**
1. In `sprint-run/SKILL.md`, add "Escalation Protocol" section
2. Instruction: "Track fix attempt failures during the session. When the same category of failure occurs twice (e.g., 'app does not launch' twice, 'test still fails' twice), STOP. Do not attempt fix #3. Instead: enumerate the two failures, identify the common category, ask what the first two attempts missed, and decide on a different approach before proceeding."
3. Define failure categories: build failure, test failure, launch failure, runtime error, verification mismatch
4. The session learning checklist (P1-STATE-4) feeds into this — repeated entries indicate repeated failures

**Acceptance criteria:**
- [ ] `sprint-run/SKILL.md` contains "Escalation Protocol" section
- [ ] Section defines the 2-failure threshold and the required pause
- [ ] Section lists failure categories
- [ ] Section explicitly says "do not attempt fix #3" without the pause

---

## Summary

| Group | Count | Enforcement Level |
|-------|-------|-------------------|
| Hooks | 5 | Structural (cannot bypass) |
| Kanban | 3 | Structural (code-enforced) |
| Scripts | 5 | Automated (run on demand or by hooks) |
| Ceremony | 8 | Prompt-shaped (strong guidance) |
| Agent Prompts | 6 | Prompt-shaped (strong guidance) |
| Config/State | 7 | Enabling infrastructure |
| **Total** | **34** | |

**Priority distribution:**
- P0 (do first): 12 items — hooks, review gate, smoke test, gap scanner, core ceremony changes
- P1 (do next): 17 items — kanban extensions, monitoring, prompt changes, state files
- P2 (do after): 5 items — DoD levels, persona history, escalation, ceremony refinements
