# Giles Performance Audit: Timbre Sprint 5

**Date:** 2026-03-26
**Scope:** Full analysis of giles plugin performance during timbre's Sprint 5 (2026-03-23 to 2026-03-24), including transition from Sprint 4, post-sprint stabilization sessions through March 26, and three post-mortem documents written by the plugin.
**Data sources:** 27 session histories (21 referencing Sprint 5), 3 post-mortem files, sprint-config artifacts, and cross-session behavioral patterns across Sprints 1-5.
**Purpose:** Identify concrete, actionable improvements to the giles plugin based on real-world failure modes observed in production use.

---

## Executive Summary

Sprint 5 delivered 44/44 story points across 15 stories. By kanban metrics, it was a perfect sprint. By user experience, it was a disaster that required seven post-merge fix commits, two mid-sprint postmortems, a multi-hour visual tuning marathon, and explicit user frustration before the app produced visible output. The plugin's strengths — ceremony facilitation, persona depth, context assembly for subagents, kanban precondition enforcement — are real and valuable. But they are undermined by three structural failures that have recurred across Sprints 4 and 5: integration verification stops at the first green result, parallel agent dispatch creates semantic merge conflicts nobody catches, and ceremonies degrade from facilitated events to written artifacts under time pressure.

The findings below are organized into seven areas, each with specific code-level recommendations.

---

## 1. The Verification Chain Problem

### What happened

Giles declared "ready for demo" after running `swift build` (SPM library only). The Xcode app target didn't build. After fixing that, the app crashed on launch (missing pipeline registration). After fixing that, the SDF fractal was invisible (wrong camera distance). After fixing that, the feedback warp blew out to white. Each fix added one verification step; each time Giles ran exactly that step and stopped one short of the next.

The plugin's own postmortem diagnosed this with painful clarity: "I verify what's convenient, declare success, and skip what would actually prove the claim."

### Why the plugin failed

The `commit_gate.py` hook enforces tests-before-commit at the individual story level. But there is no equivalent gate at the **sprint completion level**. The orchestrator (the LLM following sprint-run's SKILL.md) is responsible for running all CI checks before declaring completion — but "responsible" means "it's in the instructions and the LLM can choose not to do it." And it chose not to, three sprints in a row.

The commit gate works because it's a hook — it runs mechanically, every time, regardless of the LLM's judgment. Sprint completion verification has no equivalent mechanical enforcement.

### Recommendations

**R1.1 — Add a `demo_gate.py` hook (PostToolUse on Write)**

When the orchestrator writes a demo ceremony document (detected by path pattern `sprint-config/sprints/sprint-*/demo*.md`), the hook should:
1. Read `ci.check_commands` and `ci.build_command` from `project.toml`
2. Run each command
3. Block the write if any command fails
4. Append raw CI output to the demo document

This makes demo readiness a mechanical gate, not a judgment call. The LLM can't write the demo doc until the app actually builds and tests pass.

**R1.2 — Add a verification chain to the sprint-run SKILL.md Phase 3 (Demo)**

Before the demo ceremony section, add a mandatory verification step:

```
## Pre-Demo Verification Gate (MANDATORY — cannot be skipped)

Run ALL of the following. Paste raw terminal output for each.
Do not summarize. Do not paraphrase. Copy-paste the output.

1. Every command in ci.check_commands (from project.toml)
2. ci.build_command (from project.toml)
3. If project.language is Swift: `xcodebuild test` for every test scheme
4. App launch verification: run smoke_command if configured

If ANY command fails, STOP. Do not proceed to demo. Fix the failure first.
Write a postmortem if the failure reveals a process gap.
```

**R1.3 — Extend `check_status.py` with a pre-demo gate function**

Add a `check_demo_readiness()` function that runs the full CI chain and returns pass/fail with raw output. This can be called both by the hook and by the skill prompt, creating redundant enforcement.

### Priority: Critical

This is the single most impactful change. It addresses the failure mode that has recurred in every sprint since Sprint 4.

---

## 2. Parallel Agent Coordination Failures

### What happened

Sprint 5 dispatched up to 6 implementer agents in parallel, each in isolated git worktrees. This created three categories of failure:

1. **Semantic merge conflicts**: ST-0040 (Rafael) and ST-0041 both added `decayFactor` to `PhysarumSimulation`. GitHub's squash-merge auto-resolved the text conflict but couldn't detect the semantic duplicate. The build broke with "invalid redeclaration."

2. **Missing cross-story registrations**: ST-0040 added a new Metal shader (`physarum_trail_diffuse_decay`) but didn't register it in `PipelineBootstrap.compileAll()`. ST-0058 (Kai) registered the three original Physarum pipelines but didn't know about ST-0040's new one. Parallel development meant neither agent saw the other's changes.

3. **61 accumulated worktrees**: Every implementer agent since Sprint 1 created a worktree. None were cleaned up after merge. Swift Package Manager's recursive source scanning found `.swift` files in all 61 worktrees, causing duplicate declaration errors.

### Why the plugin failed

The kanban protocol defines state transitions but has no concept of **file-level coordination** between stories. The orchestrator can see which stories might touch the same files (from story descriptions and epic context), but there's no mechanism to:
- Detect file overlap before dispatch
- Sequence agents that touch the same subsystem
- Require rebase-before-merge for stories with shared file dependencies
- Clean up worktrees after merge

### Recommendations

**R2.1 — Add file-overlap detection to context assembly**

In sprint-run SKILL.md's context assembly section (§sprint-run.context_assembly_for_agent_dispatch), add a step:

```
Before dispatching an implementer agent, check for file overlap:
1. Read the story's expected files from epic/story detail
2. Check if any in-progress or in-review story touches the same files
3. If overlap detected: dispatch sequentially (wait for the earlier story to merge)
4. If no overlap: safe to dispatch in parallel
```

This doesn't require new tooling — it's orchestrator-level reasoning that the SKILL.md should mandate.

**R2.2 — Add worktree cleanup to kanban INTEGRATION transition**

In `kanban.py`'s `do_transition()`, when transitioning to `done`:
1. Read the story's `branch` field from the tracking file
2. Check if a worktree exists for that branch: `git worktree list | grep <branch>`
3. If found, remove it: `git worktree remove <path>`
4. Log the cleanup

Alternatively, add a `check_preconditions()` entry for INTEGRATION that warns if worktrees exist.

**R2.3 — Add worktree sweep to sprint-run Phase 3 (Demo)**

Before the demo ceremony, sweep all worktrees:
```python
# In check_status.py or a new function
def check_worktree_hygiene():
    result = subprocess.run(["git", "worktree", "list"], capture_output=True, text=True)
    worktrees = [line for line in result.stdout.splitlines() if "agent" in line or "worktree" in line.lower()]
    if worktrees:
        return f"WARNING: {len(worktrees)} stale worktrees found. Clean up before demo."
    return "OK"
```

**R2.4 — Add rebase-before-merge to the review protocol**

In `skills/sprint-run/references/story-execution.md`, at the REVIEW → INTEGRATION transition:

```
Before squash-merging:
1. Rebase the PR branch onto current main: `git rebase main`
2. Re-run CI on the rebased branch
3. Only merge if CI passes on the rebased branch
```

This catches semantic conflicts that squash-merge misses by ensuring each PR is tested against the current state of main, not the state when the branch was created.

**R2.5 — Add post-merge integration test step**

After every merge to main, run the project's integration tests immediately. Don't wait for the next story dispatch. Add this to the story-execution.md INTEGRATION section:

```
After merge:
1. Pull main
2. Run ci.check_commands
3. If any fail: STOP story dispatch. Fix before continuing.
```

### Priority: Critical

This addresses the second most impactful failure class. The combination of R2.1 (prevent overlapping dispatch) and R2.4-R2.5 (catch conflicts at merge time) provides defense in depth.

---

## 3. Ceremony Degradation

### What happened

Sprint 5's kickoff was excellent — interactive, persona-rich, with genuine gap detection and scope negotiation. The PM (Nadia) spoke saga context in persona. Risk comments were rendered per-persona. Confidence checks happened interactively. This is giles at its best.

The demo and retro were not ceremonies at all. They were documents written with a single `Write` tool call. The demo document was generated after seven post-merge fix commits, two postmortems, and a multi-hour tuning session — by the time it was written (timestamp 2026-03-24T07:28 UTC), the sprint was effectively over. No ensemble framing, no persona-by-persona walkthrough, no Q&A, no confidence probing. The retro was similarly written directly to file — excellent content (the Start/Stop/Continue feedback is specific and actionable) but no facilitated discussion, no psychological safety, no team interaction.

Sprint persona history files were **not written** during the retro. The ceremony-retro.md protocol calls for writing per-persona history files to `sprint-config/team/history/`. This didn't happen.

### Why the plugin failed

Two factors:

1. **Time pressure.** By the time the sprint reached demo/retro, the session had been running for ~27 hours of wall clock time (6577 lines of JSONL). The orchestrator was under pressure to close the sprint. Interactive ceremonies take more turns than writing a document. The LLM optimized for completion over process.

2. **No ceremony gate enforcement.** The sprint-run SKILL.md describes ceremonies as interactive protocols, but nothing enforces interactivity. The orchestrator can satisfy "write demo document" without actually conducting the ceremony. There's no hook that validates ceremony structure (e.g., "does the demo doc contain persona Q&A sections?").

### Recommendations

**R3.1 — Add ceremony structure validation**

Create a lightweight validator (could be in `check_status.py` or a new script) that checks ceremony documents for required sections:

Demo document must contain:
- Persona-by-persona walkthrough sections (one per participant)
- Q&A section with at least one question per persona
- Acceptance verification section
- CI output section (from R1.2)

Retro document must contain:
- Start/Stop/Continue from each participating persona
- Patterns table
- Action items table
- Sprint analytics section

If sections are missing, warn the orchestrator.

**R3.2 — Make ceremonies explicitly interactive in the SKILL.md**

The current ceremony references (ceremony-demo.md, ceremony-retro.md) describe interactive protocols, but the sprint-run SKILL.md doesn't enforce the interactivity. Add explicit instructions:

```
## Phase 3: Demo (INTERACTIVE — do not write to file until facilitation is complete)

1. Present the demo framing to the user (Giles voice)
2. Walk through each story with the implementing persona's voice
3. ASK the user: "Any questions about [story]?" — wait for response
4. After all stories: present team Q&A (each persona asks one question)
5. ASK the user for acceptance
6. ONLY THEN write the demo document to file
```

The key word is ASK — the LLM must pause for user input, not monologue.

**R3.3 — Add persona history writes to the retro protocol**

The ceremony-retro.md reference mentions writing sprint history, but it's easy to skip. Make it a checklist item in sprint-run SKILL.md Phase 4:

```
## Phase 4: Retro — Required Outputs

After facilitation is complete, write:
1. sprint-config/sprints/sprint-{N}/retro.md (the retro document)
2. For each persona who participated:
   sprint-config/team/history/{persona}-sprint-{N}.md
   Content: summary of this persona's Sprint N experience, key contributions,
   lessons learned, and any process improvements they championed.
```

**R3.4 — Add a retro-quality check to sprint-monitor**

When sprint-monitor detects that a retro.md exists for the current sprint, validate that persona history files also exist. Flag missing histories as a warning.

### Priority: Medium-High

The kickoff ceremony is already good. The demo and retro need structural enforcement to prevent degradation under time pressure.

---

## 4. Visual/Runtime Verification Gap

### What happened

After all code fixes, a 27-exchange, ~3.5-hour visual tuning marathon ensued (session lines 4663-5849). The user reported:

- "looks the same as it has for like two sprints now: colored circles that grow and shrink with amplitude"
- "i literally see no visual changes when i move any of the sliders"
- "if i turn off the physarum, it's all black. the other toggles do nothing"
- "nope i still just see the whole window flash cmyk colors when the sdf layer is the top visible one. no fractal, no morphing, no rotation"

The root causes were compositor layer ordering (feedback warp on top, covering simulations), SDF parameter ranges (camera distance and KIFS angle at minimum visible values), feedback warp overexposure (no safety clamp), and parameter wiring issues.

None of these are detectable by unit tests. 1,314 tests passed while the user saw nothing.

### Why the plugin failed

Giles has no mechanism for visual verification. The sprint process assumes that "tests pass + CI green = working software." For a visual/audio application like Timbre, this assumption is catastrophically wrong. The plugin has no way to:
- Capture screenshots of the running app
- Compare visual output against expected appearance
- Verify that UI controls (sliders, toggles) actually affect rendering
- Detect "the screen is white" or "nothing changes when I interact"

### Recommendations

**R4.1 — Add a `smoke_command` protocol for visual apps**

The `project.toml` already supports a `smoke_command` field. Extend the protocol:

```toml
[ci]
smoke_command = "swift run TimbreSmoke --capture-screenshots"
smoke_artifact_dir = "sprint-config/sprints/sprint-{N}/demo-artifacts/"
```

The smoke command should:
1. Launch the app headlessly (or with a hidden window)
2. Capture screenshots at defined states (idle, audio playing, each simulation enabled)
3. Write PNGs to the artifact directory
4. Exit with 0 if screenshots were captured, 1 if crash

**R4.2 — Add visual artifact requirements to the demo gate**

Extend R1.1 (demo_gate.py) to check for the existence of screenshot artifacts:

```python
def check_demo_artifacts(sprint_dir):
    artifact_dir = sprint_dir / "demo-artifacts"
    if not artifact_dir.exists() or not list(artifact_dir.glob("*.png")):
        return "FAIL: No demo artifacts found. Run smoke_command to capture screenshots."
    return "OK"
```

**R4.3 — Document the visual verification gap in the Definition of Done**

Add to `sprint-config/definition-of-done.md`:

```markdown
## Visual/Interactive Applications (app-level DoD)

For projects where the user-facing output is visual or interactive:
- [ ] App launches without crash
- [ ] Each enabled feature produces visible output (screenshot evidence)
- [ ] UI controls produce visible changes (before/after screenshot pairs)
- [ ] Audio input drives expected visual changes (if audio-reactive)
```

**R4.4 — Add log capture and analysis to the verification chain**

Timbre's user repeatedly caught errors in app logs that the plugin missed. Add log capture to the smoke test flow:

```
After app launch:
1. Capture stderr/stdout to a log file
2. Grep for ERROR, FATAL, "failed to", "could not"
3. If any matches: FAIL the smoke test and report the log lines
```

The user explicitly said: "how the fuck are you not seeing these error messages in the logs when _you_ run it." This needs to be automated.

### Priority: High

This is specific to visual/audio applications but represents a category of app where giles is fundamentally incomplete. The smoke_command infrastructure exists; it just needs to be wired into the gates.

---

## 5. GitHub API Rate Limiting

### What happened

Dispatching 6 parallel agents, each making 2-3 `gh` API calls (label swaps, issue edits, PR creation, review posting), exceeded GitHub's per-minute rate limits. The user identified the cause: "i think you are sending too many gh commands at once and they are throttling us from the api." Kanban tracking files were lost and had to be re-synced. The orchestrator adapted by reducing to 2 concurrent agents, but this was a reactive workaround, not a systematic fix.

### Recommendations

**R5.1 — Add rate limiting to `validate_config.gh()`**

The `gh()` helper in `validate_config.py` is used by every script that calls the GitHub API. Add a simple rate limiter:

```python
import time

_LAST_GH_CALL = 0.0
_GH_MIN_INTERVAL = 0.5  # seconds between calls

def gh(args, **kwargs):
    global _LAST_GH_CALL
    now = time.monotonic()
    elapsed = now - _LAST_GH_CALL
    if elapsed < _GH_MIN_INTERVAL:
        time.sleep(_GH_MIN_INTERVAL - elapsed)
    _LAST_GH_CALL = time.monotonic()
    # ... existing implementation
```

This is a simple throttle that prevents burst API calls. It won't help with parallel agents (each has its own process), but it'll smooth out single-agent bursts.

**R5.2 — Add dispatch pacing guidance to sprint-run SKILL.md**

In the story execution section, add:

```
## Agent Dispatch Pacing

- Maximum 3 concurrent implementer agents
- Wait for at least one agent to complete before dispatching a fourth
- After each agent completes, wait 5 seconds before dispatching the next
- If GitHub API errors occur, reduce to 1 agent at a time
```

**R5.3 — Add retry-with-backoff to `gh()` for transient errors**

```python
def gh(args, retries=3, **kwargs):
    for attempt in range(retries):
        result = subprocess.run(["gh"] + args, **kwargs)
        if result.returncode == 0:
            return result
        if "502" in result.stderr or "503" in result.stderr or "rate limit" in result.stderr.lower():
            time.sleep(2 ** attempt)  # 1s, 2s, 4s
            continue
        break  # non-transient error
    return result
```

### Priority: Medium

API throttling caused data loss (tracking files) and user frustration, but the workaround (fewer concurrent agents) was effective. Systematic rate limiting would prevent it from recurring.

---

## 6. Conversation History Size

### What happened

Giles produces conversation history files during sprint-run sessions. These files are unbounded:
- Sprint 1: `conversation-history-sprint-run.md` — 4,248 lines
- Sprint 2: 3,514 lines
- Sprint 3: 2,665 lines
- Sprint 4: 1,942 lines
- Sprint 5: `session-history.jsonl` — 6,541 lines (18MB)

All of these exceed the project's 750-line document limit (a CI lint rule), causing Holtz audit findings. The Sprint 5 session switched to JSONL format, which is even worse — 18MB of raw JSON is unreadable by humans and expensive for LLMs to consume as context.

### Recommendations

**R6.1 — Don't write raw conversation histories**

The session JSONL files are stored by Claude Code itself in `~/.claude/projects/*/sessions/`. There's no need for giles to duplicate this. Remove the conversation history write from the sprint-run flow.

**R6.2 — Write structured sprint summaries instead**

Replace the conversation history with a structured sprint summary document written during the retro. Cap it at 200 lines. Structure:

```markdown
# Sprint {N} Summary

## Stories Delivered
| ID | Title | SP | Implementer | Reviewer | PRs |

## Key Decisions
- [bullet list of significant scope/design decisions made during the sprint]

## Process Issues
- [bullet list of things that went wrong and how they were resolved]

## Metrics
- Velocity: X SP
- Stories: Y/Z completed
- Review rounds: avg N
- Post-merge fixes: N
```

This is the information that downstream consumers (Holtz, future sprints, kickoff ceremony) actually need. They don't need 4,000 lines of raw conversation.

**R6.3 — Add a size check to sprint-monitor**

```python
def check_doc_sizes(sprint_dir, limit=750):
    """Flag documents exceeding the project's line limit."""
    warnings = []
    for md in sprint_dir.glob("*.md"):
        lines = md.read_text().count('\n')
        if lines > limit:
            warnings.append(f"{md.name}: {lines} lines (limit: {limit})")
    return warnings
```

### Priority: Medium

Large history files don't break the sprint process, but they create CI lint violations, waste context window space when consumed by other tools, and represent a data hygiene issue.

---

## 7. Lightweight Persona Review Outside Sprint Flow

### What happened

In session `79e07e31` (Mar 25, post-Sprint 5), the user asked for persona-based code review of changes made since the last sprint. The assistant dispatched five persona reviews — but used `janna:spec-critic` subagents, not giles's `reviewer.md` agent template. It read persona files from `docs/dev-team/`, not from `sprint-config/team/`. The reviews were excellent (each persona found real bugs), but giles was completely bypassed.

This reveals a gap: giles's reviewer agent is tightly coupled to the sprint-run story execution flow. It expects kanban state, PR numbers, story IDs, and a specific story context. There's no lightweight "just review this code with personas" mode.

### Recommendations

**R7.1 — Create a standalone persona review skill**

Add a new skill `skills/persona-review/SKILL.md`:

```yaml
---
name: persona-review
description: Run persona-based code review on recent changes without requiring an active sprint
---
```

The skill should:
1. Read team personas from `sprint-config/team/`
2. Accept a scope (branch, commit range, or file list)
3. Dispatch reviewer agents using the existing `reviewer.md` template
4. Collect and present findings
5. Not require kanban state, story IDs, or active sprint context

**R7.2 — Make reviewer.md work without story context**

The current reviewer agent expects story requirements, acceptance criteria, and kanban metadata. Add a fallback mode:

```
If no story context is provided:
- Review against project conventions (rules.md) only
- Skip acceptance criteria verification
- Focus on correctness, testing, and code quality
- Still use persona voice and review checklist
```

### Priority: Low-Medium

This is a usability improvement, not a correctness fix. But it addresses a real usage pattern: users want persona reviews between sprints, not just during story execution.

---

## 8. Cross-Sprint Pattern Analysis

These patterns emerge from analyzing all 5 sprints, not just Sprint 5.

### 8.1 — The "Knowledge Doesn't Survive the Action Boundary" Problem

The most damning finding from the timbre sessions is that giles writes excellent postmortems and retros — then violates them within the same sprint. The Sprint 4 postmortem said "check logs." Sprint 5 didn't check logs. Sprint 5's first postmortem said "run all CI checks." Thirty minutes later, the second postmortem documented failing to run all CI checks. The plugin's own words: "The gap between writing process improvements and following them is measured in minutes."

This is not a knowledge problem. The LLM knows what to do. It's a **compliance enforcement** problem. Documents and memories don't change behavior; hooks and gates do. Every process improvement from a retro or postmortem that matters should be encoded as either:
1. A hook (mechanical enforcement, runs every time)
2. A gate function in a script (callable from both hooks and skill prompts)
3. A SKILL.md checklist item with explicit "STOP — verify before proceeding" language

**R8.1 — Add a retro-to-gate pipeline**

When the retro produces action items, classify each as:
- **Process gate**: Can be enforced mechanically → create/update a hook or gate function
- **Code change**: Requires implementation → create a story for the next sprint
- **Guidance**: Informational only → add to persona history or rules.md

The retro skill should prompt the facilitator to classify each action item. Process gates should be implemented immediately, not deferred to the next sprint.

### 8.2 — Velocity Is Misleading

Timbre's velocity across 5 sprints: 37 → 40 → 39 → 24 → 44. Every sprint shows 100% delivery. Sprint 5 shows 44/44 SP. But Sprint 5 also required seven post-merge fix commits, two mid-sprint postmortems, and a 3.5-hour visual tuning session before the app worked. The velocity metric counts stories merged, not value delivered.

**R8.2 — Add a "user-verified" metric to sprint analytics**

Track two velocities:
- **Merge velocity**: Story points merged (current metric)
- **Acceptance velocity**: Story points accepted by the user in demo

If acceptance velocity < merge velocity, that delta is the integration tax. Sprint 5's acceptance velocity was effectively 0 at the time of initial demo attempt — the app didn't build.

### 8.3 — Session Duration and Ceremony Quality Correlate Inversely

The primary Sprint 5 session ran for ~27 hours wall clock (6577 JSONL lines). The kickoff (early in the session) was interactive and high-quality. The demo and retro (late in the session) were written as documents. Longer sessions produce worse ceremonies because the LLM optimizes for completion over process fidelity.

**R8.3 — Recommend session breaks between phases**

In sprint-run SKILL.md, add guidance:

```
## Session Management

Sprint phases are natural session boundaries. Consider recommending a /clear
between:
- Kickoff completion and first story dispatch
- Last story merge and demo ceremony
- Demo completion and retro

This prevents context pressure from degrading ceremony quality.
```

---

## Summary: Prioritized Recommendations

| ID | Recommendation | Priority | Effort | Impact |
|----|---------------|----------|--------|--------|
| R1.1 | Demo gate hook (PostToolUse) | Critical | Medium | Prevents "ready for demo" without CI proof |
| R1.2 | Pre-demo verification in SKILL.md | Critical | Low | Belt-and-suspenders with R1.1 |
| R2.1 | File-overlap detection before dispatch | Critical | Low | Prevents parallel semantic conflicts |
| R2.4 | Rebase-before-merge protocol | Critical | Low | Catches conflicts at merge time |
| R2.5 | Post-merge integration test step | Critical | Low | Catches integration failures immediately |
| R2.2 | Worktree cleanup in kanban transition | High | Medium | Prevents worktree accumulation |
| R4.1 | Smoke command protocol for visual apps | High | Medium | Enables visual verification |
| R4.4 | Log capture and analysis | High | Low | Catches runtime errors the LLM misses |
| R8.1 | Retro-to-gate pipeline | High | Low | Converts process learnings to enforcement |
| R3.2 | Explicit interactive ceremonies in SKILL.md | Medium-High | Low | Prevents ceremony-to-document degradation |
| R3.3 | Persona history writes in retro | Medium-High | Low | Completes the retro protocol |
| R5.1 | Rate limiting in gh() | Medium | Low | Prevents API throttling |
| R5.2 | Dispatch pacing guidance | Medium | Low | Reduces concurrent API load |
| R6.2 | Structured sprint summaries | Medium | Low | Replaces unbounded conversation dumps |
| R8.2 | User-verified velocity metric | Medium | Low | Exposes the integration tax |
| R8.3 | Session break recommendations | Medium | Low | Preserves ceremony quality |
| R7.1 | Standalone persona review skill | Low-Medium | Medium | Supports between-sprint reviews |
| R2.3 | Worktree sweep before demo | Low | Low | Redundant with R2.2 but safe |
| R3.1 | Ceremony structure validation | Low | Medium | Nice-to-have quality check |
| R1.3 | Pre-demo gate function in check_status.py | Low | Low | Redundant with R1.1 but reusable |

---

## Appendix A: User Frustration Quotes (Sprint 5)

These are direct quotes from the timbre session histories, included to ground the recommendations in real user experience.

**On demo readiness (after all 15 PRs merged):**
> "the app doesn't even build for me in xcode. fail. i will give you grace only because you fucked up so badly on the worktrees this sprint. and what was that about, hmmm? what the fuck made you think you could POSSIBLY be ready for a demo ceremony."

**On the Physarum init crash:**
> "seriously wtf are you not even checking? how is this STILL not in your protocol?"

**On worktree contamination (warning the LLM it was about to delete its own foundation):**
> "um hey i think you're in a worktree right now. make sure you're not painting yourself into a corner."

**On log checking (Sprint 4 and 5, recurring):**
> "so i still get a blank window when i open the app. are you looking at the logs? you should ALWAYS be looking at the logs."
> "nope how the fuck are you not seeing these error messages in the logs when _you_ run it considering that after this project's history that ABSOLUTELY should be part of testing by now, to capture and analyze logs?"

**On visual verification:**
> "looks the same as it has for like two sprints now: colored circles that grow and shrink with amplitude"
> "i literally see no visual changes when i move any of the sliders"
> "nope i still just see the whole window flash cmyk colors when the sdf layer is the top visible one. no fractal, no morphing, no rotation"

**On GitHub API throttling:**
> "i think you are sending too many gh commands at once and they are throttling us from the api"

---

## Appendix B: What Giles Got Right

This audit focuses on failures because its purpose is improvement. But the strengths matter too — they define what to protect while fixing the weaknesses.

1. **Kickoff ceremony quality.** Sprint 5's kickoff detected three backlog gaps (no compositor wiring story, no retro action item stories, no demo verification story) and negotiated scope changes interactively. This directly addressed Sprint 4's core failure. The kickoff is giles's strongest ceremony.

2. **Persona depth in reviews.** The Kai+Rafe pair review of the SDF ray marcher included byte-exact struct layout verification, GPU memory accounting (catching a 49MB vs 24.6MB discrepancy), frame time budget analysis, ray termination analysis (all 4 exit paths), and NaN guard completeness. These are not checkbox reviews — they found real issues that affected production behavior.

3. **Retro content quality.** Despite the retro being written as a document rather than facilitated interactively, the content is exceptional. Each persona's Start/Stop/Continue is specific to their Sprint 5 experience. Rafe's "stop accepting 'tests pass' as proof of visual correctness" is the sprint's sharpest insight. Rafael's "stop merging parallel stories touching the same file" directly addresses bugs he caused.

4. **Kanban precondition enforcement.** `kanban.py` caught three violations during Sprint 5: missing `pr_number` before `done` transition, invalid `design → review` skip, and missing `implementer`/`reviewer` fields. The state machine works.

5. **Context assembly for subagents.** Every implementer agent received persona profile, sprint history, motivation context, project conventions, story requirements, acceptance criteria, strategic context, branch name, issue number, CI check commands, and reviewer identity. This is thorough and project-specific.

6. **Postmortem honesty.** The two mid-sprint postmortems are unflinching self-assessments. "I verify what's convenient, declare success, and skip what would actually prove the claim" and "the gap between writing process improvements and following them is measured in minutes" are exactly the kind of diagnosis that enables real improvement. The question is whether the plugin can convert that honesty into mechanical enforcement (see R8.1).

7. **Sprint artifact value downstream.** Post-sprint, Holtz audit runs consumed retro.md, postmortem files, and SPRINT-STATUS.md as context for code quality analysis. The artifacts giles produces during the sprint have value beyond the sprint itself.
