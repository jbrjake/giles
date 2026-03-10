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

Each invocation performs four steps in order:
1. Check CI status
2. Check open PRs
3. Update burndown
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

- Merge using the strategy from `project.toml [conventions] merge_strategy`:
  ```bash
  gh pr merge {number} --{merge_strategy} --delete-branch
  ```
- Close the linked issue if one exists:
  ```bash
  gh pr view {number} --json closingIssuesReferences --jq '.closingIssuesReferences[].number'
  ```
- Update the story tracking file to mark the story as done.

### PRs with merge conflicts

- Post a comment noting the conflict:
  ```
  This PR has merge conflicts that need resolution before it can be merged.
  ```
- Check existing comments first to avoid duplicates.

## Step 3 -- Update Burndown

Run the status check script (path relative to skill install location):

```bash
python3 skills/sprint-monitor/scripts/check_status.py
```

This script:
- Queries GitHub milestones for open/closed issue counts.
- Updates the sprint burndown file with current numbers.
- Updates `SPRINT-STATUS.md` with current story states.
- Posts a brief status summary to stdout.

If the script is missing or fails, reconstruct status manually:

```bash
# Read repo from project.toml [project] repo
gh api repos/{owner}/{repo}/milestones --jq '.[] | select(.title | startswith("Sprint")) | {title, open_issues, closed_issues}'
```

Update `SPRINT-STATUS.md` directly with the counts.

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

When invoked outside of `/loop`, run all four steps once and output the full
report. Accept optional flags:

- `--ci-only` -- run only Step 1.
- `--pr-only` -- run only Step 2.
- `--burndown-only` -- run only Step 3.
- `--dry-run` -- check status but take no actions (no merges, no comments, no
  pushes).
