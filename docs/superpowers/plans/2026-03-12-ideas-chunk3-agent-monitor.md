# Chunk 3: Agent Infrastructure + Monitor — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restructure reviewer into multi-pass review, add pair review for high-risk stories, add context budget guidance and confidence signals to agent templates, implement mid-sprint check-in and drift detection in sprint-monitor.

**Architecture:** Agent template changes are prompt restructuring (no scripts). Pair review adds dispatch logic to sprint-run SKILL.md. Mid-sprint check-in is a monitor threshold that triggers a Giles-voiced ceremony. Drift detection adds two functions to check_status.py.

**Tech Stack:** Markdown (agent templates, SKILL.md, monitor SKILL.md), Python 3.10+ stdlib (check_status.py additions)

**Spec:** `docs/superpowers/specs/2026-03-12-ideas-implementation-design.md` — Chunk 3 section

**Depends on:** Chunk 1 (Giles persona exists, Giles voice in monitor output)

---

## File Structure

### Files to Modify

| File | Changes |
|------|---------|
| `skills/sprint-run/agents/reviewer.md` | Three-pass review, read confidence section, pair review note |
| `skills/sprint-run/agents/implementer.md` | Context budget section, confidence section in PR template |
| `skills/sprint-run/SKILL.md` | Pair review dispatch logic, mid-sprint check-in phase |
| `skills/sprint-run/references/story-execution.md` | Pair review variant in REVIEW transition |
| `skills/sprint-run/references/ceremony-demo.md` | Confidence signal probing in Q&A |
| `skills/sprint-monitor/SKILL.md` | Mid-sprint check-in detection, drift detection steps |
| `skills/sprint-monitor/scripts/check_status.py` | `check_branch_divergence()`, `check_direct_pushes()` |

---

## Task 0: Restructure Reviewer for Multi-Pass Review

**Files:**
- Modify: `skills/sprint-run/agents/reviewer.md`

- [ ] **Step 1: Read current reviewer.md**

Read `skills/sprint-run/agents/reviewer.md` (133 lines). Note the current single-pass review structure under "### 2. Read the Diff".

- [ ] **Step 2: Restructure into three passes**

Replace the current "### 2. Read the Diff" section with:

```markdown
### 2. Read the Diff (Three-Pass Review)

Review the diff in three focused passes. This is how good human reviewers
work — they don't catch everything in one read. Neither will you.

```bash
gh pr diff {pr_number}
```

**Pass 1 — Correctness:**
Focus exclusively on whether the code does what it's supposed to.
- Do the changes implement the acceptance criteria?
- Are there logical errors or edge cases missed?
- Does the code handle the scenarios described in the story?
- Read the Confidence section in the PR description first — spend
  proportionally more time on areas marked low-confidence.

**Pass 2 — Conventions:**
Focus exclusively on whether the code follows the rules.
- Read `{rules_file}` for project conventions. Verify compliance.
- File sizes under project limits (500 target, 750 hard limit)
- Commit messages follow conventional format
- Progressive disclosure docs updated if new files/concepts added
- Security: no secrets in code or logs

**Pass 3 — Testing:**
Focus exclusively on whether the tests are adequate.
- Tests exist for all acceptance criteria
- Tests use meaningful assertions (not just "doesn't panic")
- Both success and error paths tested
- Property-based tests for algebraic invariants where appropriate
- Test plan coverage verified (if test cases referenced in story)

After all three passes, synthesize your findings into a single review.
Note which pass each finding came from — it helps the implementer
prioritize. Correctness findings are blockers. Convention findings are
important. Testing findings depend on coverage gap severity.
```

- [ ] **Step 3: Add confidence section reading**

Add before the three passes:

```markdown
Before starting, read the `## Confidence` section in the PR description.
The implementer has rated their confidence per area (high/medium/low).
Low-confidence areas get the most scrutiny in Pass 1. This is metadata
that makes your review smarter — trust the implementer's self-assessment
as a starting point, then verify.
```

- [ ] **Step 4: Commit**

```bash
git add skills/sprint-run/agents/reviewer.md
git commit -m "feat: restructure reviewer into three-pass review with confidence reading"
```

---

## Task 1: Add Context Budget and Confidence to Implementer

**Files:**
- Modify: `skills/sprint-run/agents/implementer.md`

- [ ] **Step 1: Read current implementer.md**

Read `skills/sprint-run/agents/implementer.md`. Note the PR description template and the process steps.

- [ ] **Step 2: Add Context Management section**

Add after "Your Process" heading, before "### 1. Create Branch":

```markdown
## Context Management

Large stories consume a lot of context. Manage it deliberately:

- Load your persona file and `{rules_file}` at the start — these are
  always relevant and relatively small.
- Load PRD excerpts during design phase. After you've made design
  decisions, summarize the relevant PRD content into your design notes
  and stop carrying the full PRD text. You've internalized it.
- For stories 5 SP or above, write a brief design summary after the
  design phase and before starting implementation. This summary replaces
  the raw story requirements in your working context.
- If you notice your responses becoming less precise or you're losing
  track of earlier decisions, that's a context signal. Stop, summarize
  your progress in the story tracking file, and continue from the summary.
```

- [ ] **Step 3: Add Confidence section to PR description template**

In the PR creation command (the `--body` heredoc), add after `## Design Decisions`:

```markdown
## Confidence
{Rate your confidence per area of the implementation:}
- **{area 1}:** High / Medium / Low — {brief rationale}
- **{area 2}:** High / Medium / Low — {brief rationale}

{Focus on areas where you're less certain. "High on the API layer, medium
on the serialization logic, low on the edge case handling in parse_header."
The reviewer will spend proportionally more time on low-confidence areas.}
```

- [ ] **Step 4: Commit**

```bash
git add skills/sprint-run/agents/implementer.md
git commit -m "feat: implementer gains context budget guidance and confidence signals"
```

---

## Task 2: Add Pair Review to Sprint-Run

**Files:**
- Modify: `skills/sprint-run/SKILL.md`
- Modify: `skills/sprint-run/references/story-execution.md`

- [ ] **Step 1: Read current story-execution.md REVIEW section**

Read `skills/sprint-run/references/story-execution.md` lines 80-99 (DEVELOPMENT → REVIEW).

- [ ] **Step 2: Add pair review variant to story-execution.md**

Add after the existing DEVELOPMENT → REVIEW section:

```markdown
### Pair Review (High-Risk Stories)

When a story meets BOTH of these criteria, dispatch two reviewer subagents:
1. Story points >= 5
2. Story touches files owned by multiple personas (check domain keywords
   in team INDEX.md against the files changed in the PR)

Each reviewer brings their domain expertise. Dispatch as separate subagents
so context costs are isolated.

The implementer addresses both reviews. If the reviewers disagree, the
implementer reconciles — both perspectives are valid, and the implementer
is closest to the code. If reconciliation isn't possible, escalate to the
user.

Pair review produces two GitHub reviews on the same PR. Both must approve
before proceeding to integration.
```

- [ ] **Step 3: Add pair review detection to SKILL.md Phase 2**

In the Phase 2 story execution table, update the `dev → review` row:

```markdown
| dev | DEV --> REVIEW | Dispatch reviewer (or pair reviewers for SP >= 5 + multi-domain). See story-execution.md |
```

- [ ] **Step 4: Commit**

```bash
git add skills/sprint-run/SKILL.md skills/sprint-run/references/story-execution.md
git commit -m "feat: pair review for high-risk stories (SP >= 5 + multi-domain)"
```

---

## Task 3: Add Confidence Probing to Demo Ceremony

**Files:**
- Modify: `skills/sprint-run/references/ceremony-demo.md`

- [ ] **Step 1: Add confidence probing to Team Q&A**

In the "### 4. Team Q&A" section, add:

```markdown
Giles reads the Confidence section from each story's PR description before
the demo. During Q&A, he probes low-confidence areas harder:

- "Your PR noted low confidence on the edge case handling. Walk us through
  what you tested and what you didn't."
- "Medium confidence on the serialization logic — did the reviewer's
  second pass catch anything there?"

This ensures the demo doesn't just celebrate what worked — it examines
what might not have.
```

- [ ] **Step 2: Commit**

```bash
git add skills/sprint-run/references/ceremony-demo.md
git commit -m "feat: demo ceremony probes low-confidence areas from PR signals"
```

---

## Task 4: Add Mid-Sprint Check-In to Monitor

**Files:**
- Modify: `skills/sprint-monitor/SKILL.md`
- Modify: `skills/sprint-run/SKILL.md`

- [ ] **Step 1: Read current sprint-monitor SKILL.md**

Read `skills/sprint-monitor/SKILL.md` (242 lines). Note the five-step structure.

- [ ] **Step 2: Add Step 2.5 — Mid-Sprint Check-In**

Add between Step 2 (Check Open PRs) and Step 3 (Update Burndown):

```markdown
## Step 2.5 — Mid-Sprint Check-In

Check whether the sprint has crossed the halfway mark:

```bash
# Count done vs total stories from SPRINT-STATUS.md
# If done >= total / 2 AND no check-in has been recorded this sprint:
```

If threshold is crossed and no check-in file exists at
`{sprints_dir}/sprint-{N}/mid-sprint-checkin.md`:

1. Compute current velocity vs plan (stories done, SP delivered so far)
2. Identify stories taking longer than expected (in dev or review for
   more than double the average cycle time)
3. Output a Giles-voiced check-in:

```
Mid-Sprint Check-In — Sprint {N}

Right, we're past the halfway mark. Here's where we stand.

Velocity: {done}/{total} stories, {done_sp}/{total_sp} SP
On track: {yes/no — compare actual vs expected at this point}
{If behind:} We're behind by {X} SP. Stories {ids} are taking longer
than expected. {If a story is stuck in review:} {story} has been in
review for {hours} — worth checking whether the review feedback is
actionable or if we need to escalate.

{If design decisions need revisiting:} Two stories are building in
different directions on {topic}. Worth a quick alignment before more
code gets written.
```

4. Write the check-in to `{sprints_dir}/sprint-{N}/mid-sprint-checkin.md`
   to prevent duplicate check-ins.

This check-in is informational. It does not block story execution.
If the user invokes sprint-run while a check-in is pending, Giles
presents it before resuming work.
```

- [ ] **Step 3: Add check-in awareness to sprint-run SKILL.md**

Add to Phase 2 (Story Execution), before the kanban state table:

```markdown
### Mid-Sprint Check-In

Before dispatching the next story, check if
`{sprints_dir}/sprint-{N}/mid-sprint-checkin.md` exists but has not been
acknowledged. If so, Giles presents the check-in to the user and the PM
persona. The PM answers any product questions. Giles adjusts the plan if
needed (reorder stories, flag at-risk scope). Then resume story execution.
```

- [ ] **Step 4: Commit**

```bash
git add skills/sprint-monitor/SKILL.md skills/sprint-run/SKILL.md
git commit -m "feat: mid-sprint check-in triggered by monitor, presented by Giles"
```

---

## Task 5: Add Drift Detection to Monitor

**Files:**
- Modify: `skills/sprint-monitor/SKILL.md`
- Modify: `skills/sprint-monitor/scripts/check_status.py`

- [ ] **Step 1: Read current check_status.py**

Read `skills/sprint-monitor/scripts/check_status.py`. Note the existing `check_ci()`, `check_prs()`, and `check_milestone()` functions.

- [ ] **Step 2: Add drift detection functions to check_status.py**

Add two new functions:

```python
def check_branch_divergence(repo: str, base_branch: str, sprint_branches: list[str]) -> list[dict]:
    """Check if any sprint branch has diverged significantly from base.

    Returns list of {branch, behind_count, ahead_count, risk} dicts.
    Risk is 'high' if behind_count > 20 commits, 'medium' if > 10.
    """
    results = []
    for branch in sprint_branches:
        # gh api repos/{repo}/compare/{base}...{branch}
        cmd = ["gh", "api", f"repos/{repo}/compare/{base_branch}...{branch}",
               "--jq", "{behind_by: .behind_by, ahead_by: .ahead_by}"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            data = json.loads(result.stdout)
            risk = "high" if data["behind_by"] > 20 else "medium" if data["behind_by"] > 10 else "low"
            if risk != "low":
                results.append({
                    "branch": branch,
                    "behind_count": data["behind_by"],
                    "ahead_count": data["ahead_by"],
                    "risk": risk
                })
    return results


def check_direct_pushes(repo: str, base_branch: str, since: str) -> list[dict]:
    """Check for commits pushed directly to base branch since a given date.

    Returns list of {sha, message, author, date} dicts for non-merge commits.
    """
    cmd = ["gh", "api", f"repos/{repo}/commits",
           "-f", f"sha={base_branch}", "-f", f"since={since}",
           "--jq", '[.[] | select(.parents | length == 1) | {sha: .sha[:8], message: .commit.message, author: .commit.author.name, date: .commit.author.date}]']
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        return json.loads(result.stdout)
    return []
```

- [ ] **Step 3: Add drift detection steps to monitor SKILL.md**

Add a new Step 1.5 after CI check:

```markdown
## Step 1.5 — Drift Detection

Check for two types of drift that can silently derail a sprint:

### Branch divergence

For each open PR's head branch, check how far behind the base branch it is:

```bash
gh api repos/{owner}/{repo}/compare/{base_branch}...{head_branch} --jq '.behind_by'
```

- If behind by > 20 commits: HIGH risk. Post a Giles-voiced comment:
  "{branch} is {N} commits behind {base_branch}. A rebase before the
  next review round would be prudent. I say this from experience."
- If behind by > 10 commits: MEDIUM risk. Note in status report.
- Check existing comments before posting to avoid duplicates.

### Direct pushes to base branch

Check for non-merge commits on the base branch since the sprint started:

```bash
gh api repos/{owner}/{repo}/commits -f sha={base_branch} -f since={sprint_start_date} --jq '...'
```

If any direct pushes found, flag in Giles's voice:
"Someone appears to have pushed directly to {base_branch}. I won't say
who, but I will say it's making the merge queue nervous."
```

- [ ] **Step 4: Write tests for drift detection**

Add tests with mocked `gh` output for both functions:
- `check_branch_divergence` with branches at various divergence levels
- `check_direct_pushes` with and without direct commits

- [ ] **Step 5: Run tests and commit**

```bash
python -m unittest discover -s tests -v
git add skills/sprint-monitor/SKILL.md skills/sprint-monitor/scripts/check_status.py tests/
git commit -m "feat: drift detection in sprint-monitor (branch divergence + direct pushes)"
```

---

## Task 6: Update CLAUDE.md and CHEATSHEET.md

- [ ] **Step 1: Update CLAUDE.md**

Note multi-pass review in reviewer description. Note confidence signals. Note mid-sprint check-in in sprint-monitor. Note drift detection functions in check_status.py.

- [ ] **Step 2: Update CHEATSHEET.md**

Add line-number indices for new check_status.py functions. Update agent template section descriptions. Update monitor SKILL.md step references.

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md CHEATSHEET.md
git commit -m "docs: update CLAUDE.md and CHEATSHEET.md for Chunk 3 additions"
```
