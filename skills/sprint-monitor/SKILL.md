---
name: sprint-monitor
description: Continuous CI/PR/burndown monitoring for active sprints, designed for /loop. Use when setting up automated monitoring, checking CI status, babysitting PRs, or updating burndown progress. Also triggers on "monitor sprint", "check CI", "babysit PRs", "update burndown", "sprint status", "what's the sprint status".
---

## Quick Reference

| Step | Script |
|------|--------|
| Full status check | `scripts/check_status.py [sprint-number]` |
| Burndown update | `skills/sprint-run/scripts/update_burndown.py` |

# Sprint Monitor

## Overview

This skill is designed for use with `/loop 5m sprint-monitor`. Run it
autonomously on each invocation: check GitHub state, take action where needed,
and report. Invoke manually for a one-time status check.

Each invocation performs seven steps in order:
0. Sync backlog to GitHub (milestones + issues)
1. Check CI status
1.5. Drift detection (branch divergence + direct pushes)
2. Check open PRs
2.5. Mid-sprint check-in
3. Check sprint status
4. Report a one-line summary

## Prerequisites

- Run `scripts/validate_config.py` first. Load `project.toml` for paths.
- `gh` CLI authenticated with repo access.
- `SPRINT-STATUS.md` exists at the path specified by `project.toml [paths] sprints_dir`.
- A sprint is active (phase = development).

If any prerequisite is missing, report what is missing and exit cleanly. Do not
error -- `/loop` will call again.

```bash
# Verify prerequisites
gh auth status
# Read SPRINT-STATUS.md from config [paths] sprints_dir
test -f "${sprints_dir}/SPRINT-STATUS.md" || echo "SPRINT-STATUS.md missing"
grep -q "phase:.*development" "${sprints_dir}/SPRINT-STATUS.md" || echo "No active development phase"
```

## Step 0 -- Sync Backlog

Run the backlog sync engine to detect new or changed milestone files and
create corresponding GitHub milestones and issues:

```bash
python3 scripts/sync_backlog.py
```

This script:
- Hashes milestone files and compares against cached state.
- **Debounce:** waits one iteration after detecting a change before syncing
  (in case the user is still editing).
- **Throttle:** syncs at most once per 10 minutes.
- Delegates to the idempotent `bootstrap_github.create_milestones_on_github()`
  and `populate_issues.create_issue()` functions.
- Prints a one-line status: `sync: no changes detected`, `sync: change detected,
  debouncing`, `sync: throttled, will sync later`, or `sync: created N issues,
  synced M milestones`.

If the script fails, log the error and continue with Step 1. The sync is
best-effort and must not block monitoring.

## Step 1 -- Check CI Status

Query the five most recent workflow runs:

```bash
gh run list --limit 5 --json status,conclusion,name,headBranch,databaseId
```

### If all runs pass

Log "CI: all green" and move to Step 2.

### If any run is failing

For each failing run:

1. Read the failure logs:
   ```bash
   gh run view {id} --log-failed
   ```
2. Identify the error category: compile error, test failure, lint/fmt issue, or
   other.
3. If the fix is simple (fmt, clippy, single test assertion):
   - Check out the branch.
   - Apply the fix, commit with a message like `fix: resolve clippy warning in
     {file}`.
   - Push the branch. CI will re-trigger automatically.
4. If the fix is complex:
   - Post a comment on the associated PR describing the failure, the relevant
     log lines, and what needs attention.
   - Do not attempt an automated fix.
5. Update the story tracking file with the CI status (`CI: failing`,
   `CI: fix pushed`, or `CI: needs manual attention`).

## Step 1.5 -- Drift Detection

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

## Step 2 -- Check Open PRs

Query all open pull requests:

```bash
gh pr list --json number,title,reviewDecision,labels,mergeable,statusCheckRollup,createdAt,url
```

Process each PR according to its state:

### PRs awaiting review

- Check whether a reviewer persona has been assigned.
- If the PR has been waiting longer than 1 hour with no review activity, post a
  reminder comment:
  ```
  This PR has been open for >1h with no review. Flagging for attention.
  ```
- Do not post duplicate reminders -- check existing comments first:
  ```bash
  gh pr view {number} --json comments --jq '.comments[].body'
  ```

### PRs with review feedback

- Check if changes were requested.
- If the implementer has not responded, note it in the status report.
- Do not take automated action -- review responses require human judgment.

### PRs approved + CI green

- Report that the PR is ready to merge (sprint-run handles the actual merge
  during story execution using the strategy from `project.toml [conventions] merge_strategy`).
- Note any linked issues that will close on merge:
  ```bash
  gh pr view {number} --json closingIssuesReferences --jq '.closingIssuesReferences[].number'
  ```

### PRs with merge conflicts

- Post a comment noting the conflict:
  ```
  This PR has merge conflicts that need resolution before it can be merged.
  ```
- Check existing comments first to avoid duplicates.

## Step 2.5 -- Mid-Sprint Check-In

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

## Step 3 -- Check Sprint Status

Run the status check script (path relative to skill install location):

```bash
python3 skills/sprint-monitor/scripts/check_status.py
```

This script:
- Queries GitHub milestones for open/closed issue counts.
- Checks CI status for the base branch.
- Outputs a status summary to stdout.

Note: `check_status.py` is read-only — it queries and reports but does not write
burndown or tracking files. For actual burndown file updates, use
`skills/sprint-run/scripts/update_burndown.py`.

If the script is missing or fails, reconstruct status manually:

```bash
# Read repo from project.toml [project] repo
gh api repos/{owner}/{repo}/milestones --jq '.[] | select(.title | startswith("Sprint")) | {title, open_issues, closed_issues}'
```

## Step 4 -- Report

Output a single status line summarizing the sprint:

```
Sprint {N} | {done}/{total} stories done | {done_sp}/{total_sp} SP | CI: {status} | PRs: {open} open, {needs_review} needs review
```

Example:
```
Sprint 1 | 3/6 stories done | 22/44 SP | CI: green | PRs: 2 open, 1 needs review
```

If any action was taken (fix pushed, PR merged, comment posted), add a second
line listing the actions:

```
Actions: merged PR #42, pushed CI fix to feature/parser, flagged PR #45 for review
```

## Rate Limiting

### Action deduplication

Do not take the same action on the same issue or PR twice within 30 minutes.
Before acting, check timestamps in tracking files or PR comment history. If the
last action was within 30 minutes, skip it.

### GitHub API rate limits

Before running checks, verify remaining API quota:

```bash
gh api rate_limit --jq '.rate.remaining'
```

- If remaining < 100: skip non-critical checks (burndown update, reminder
  comments). Run only CI status and merge-ready PR checks.
- If remaining < 20: skip all checks, report "rate limited", and exit cleanly.

### Idempotency

All actions are idempotent. Running the monitor repeatedly produces the same
result -- duplicate comments are never posted, already-merged PRs are skipped,
and fixes are not re-applied to passing CI.

## Error Handling

- If a `gh` command fails, log the error and continue with remaining checks.
  Do not abort the entire run for a single failure.
- If tracking files (`SPRINT-STATUS.md`, burndown) are missing, attempt to
  reconstruct from GitHub state using the milestone API.
- If reconstruction also fails, report what is missing and continue with
  whatever checks are possible.
- Never crash. Always exit cleanly so `/loop` can call again on schedule.
- Catch and log all exceptions. An unhandled error in one step must not prevent
  the remaining steps from running.

## Manual Invocation

When invoked outside of `/loop`, run all seven steps once and output the full
report. Accept optional flags:

- `--ci-only` -- run only Step 1.
- `--pr-only` -- run only Step 2.
- `--burndown-only` -- run only Step 3.
- `--dry-run` -- check status but take no actions (no merges, no comments, no
  pushes).
