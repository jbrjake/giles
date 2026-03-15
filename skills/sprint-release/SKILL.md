---
name: sprint-release
description: Release management for project milestones — tagging, building, CI monitoring, and release notes. Use when a milestone is complete, creating a release, tagging a version, generating release notes, or managing the release pipeline. Also triggers on "create release", "tag release", "milestone complete", "cut a release", "release notes".
---

## Quick Reference

| Phase | Read These First |
|-------|-----------------|
| Gate Validation | `references/release-checklist.md` |
| Scripts | `skills/sprint-release/scripts/release_gate.py --help` |

# Sprint Release Skill

Invoked at milestone boundaries (after the final sprint of a release completes).
Manage the full release process from gate validation to published GitHub Release.

---

## Prerequisites

Load `project.toml` and validate configuration before starting. Run
`scripts/validate_config.py` to confirm all required keys exist.

Verify all prerequisites before starting. If any check fails, report the failure
and stop.

1. **All sprint stories complete.** Read `SPRINT-STATUS.md` from the path
   specified by `project.toml [paths] sprints_dir` and confirm every sprint in
   the milestone shows status `Done` with final velocity recorded.

2. **CI passing on base branch.** Read `base_branch` from `project.toml [project] base_branch` (default: `main`). Run:
   ```bash
   gh run list --branch {base_branch} --limit 1
   ```
   Confirm the most recent workflow run has status `completed` and conclusion
   `success`. If CI is failing, do not proceed -- fix CI first.

3. **Release checklist loaded.** Read `skills/sprint-release/references/release-checklist.md` for
   milestone-specific gate criteria. Each milestone defines its own gates; do not
   assume gates from a different milestone apply.

4. **Conventional commits.** All commits since the last release tag must follow
   conventional commit format. The release script calculates the version from
   the commit log. Run `python {plugin_root}/scripts/commit.py --help` for format.

---

<!-- §sprint-release.step_1_gate_validation -->
<!-- §sprint-release.gate_validation -->
## Step 1: Gate Validation

Read `skills/sprint-release/references/release-checklist.md` and validate every gate for the target
milestone. Do not skip gates. If any gate fails, report exactly what failed and
stop.

### Gate Checks

The release script (`release_gate.py`) runs five hardcoded gates in sequence:

1. **Stories** — all issues in the milestone must be closed
2. **CI** — most recent CI run on base branch must pass
3. **PRs** — no open PRs targeting the milestone
4. **Tests** — all `check_commands` from `project.toml [ci]` must pass
5. **Build** — `build_command` from `project.toml [ci]` must succeed

### Gate Summary

Print a gate summary table before proceeding:

```
Gate                    | Status | Detail
------------------------|--------|-------
Stories                 | PASS   | All issues closed
CI                      | PASS   | CI: success
PRs                     | PASS   | No open PRs for milestone
Tests                   | PASS   | 3 command(s) passed
Build                   | PASS   | Build succeeded
```

If any row shows FAIL, stop and report. Do not proceed to tagging.

---

<!-- §sprint-release.step_2_tag_and_release -->
## Step 2: Tag and Release

Create an annotated tag and push it to origin.

### Version Scheme

Version is calculated automatically from conventional commits since the last
`vX.Y.Z` tag. Breaking changes bump major, features bump minor, fixes bump
patch. Base version is `0.1.0` when no tags exist.

### Tag

```bash
git tag -a v{version} -m "Release {version}: {milestone name}"
git push origin v{version}
```

Replace `{version}` and `{milestone name}` with the actual values (e.g.,
`v0.1.0` and `Walking Skeleton`).

---

<!-- §sprint-release.step_3_build_release_artifacts -->
<!-- §sprint-release.build_artifacts -->
## Step 3: Build Release Artifacts

Read `build_command` from `project.toml [ci]` and run it. If `binary_path` is
configured, verify the binary exists and report its size.

```bash
# Read build_command from project.toml [ci]
${build_command}

# Verify binary if binary_path is configured
binary_path="${binary_path}"
[ -f "$binary_path" ] && echo "$binary_path: $(stat -f%z "$binary_path" 2>/dev/null || stat -c%s "$binary_path") bytes"
```

---

<!-- §sprint-release.step_4_create_github_release -->
<!-- §sprint-release.github_release -->
## Step 4: Create GitHub Release

Generate release notes, then publish the release.

### Generate Release Notes

Collect release content from these sources:

1. **Sprint demo artifacts.** Read demo notes from each sprint directory under
   `project.toml [paths] sprints_dir`:
   ```bash
   ls ${sprints_dir}/sprint-*/demo.md 2>/dev/null
   ```

2. **Closed issues in the milestone.** Pull the list from GitHub:
   ```bash
   gh issue list --milestone "{milestone_title}" --state closed --limit 100
   ```

3. **Commit log since last release (or initial commit for the first milestone).**
   ```bash
   git log --oneline $(git describe --tags --abbrev=0 2>/dev/null || git rev-list --max-parents=0 HEAD)..HEAD
   ```

Assemble `release-notes.md` with these sections:

- **Highlights** -- 3-5 bullet points covering the most important changes
- **Features** -- complete list of user-facing features added
- **Breaking Changes** -- any incompatible changes
- **Known Limitations** -- documented constraints or missing functionality
- **Full Changelog** -- link to the GitHub compare view

### Publish

```bash
# Read project_name from project.toml [project] name
# Read binary_path from project.toml [ci]
gh release create v{version} \
  --title "${project_name} {version}" \
  --notes-file release-notes.md \
  "${binary_path}"
```

Attach the binary (if configured). Confirm the release URL is returned:

```bash
gh release view v{version} --json url --jq '.url'
```

---

<!-- §sprint-release.step_5_post_release_close_milestone_update_tracking -->
## Step 5: Post-Release

After the release is published, perform these housekeeping steps.

### Close the GitHub Milestone

```bash
milestone_number=$(gh api repos/{owner}/{repo}/milestones \
  --jq ".[] | select(.title == \"${milestone_title}\") | .number")
gh api repos/{owner}/{repo}/milestones/${milestone_number} \
  -X PATCH -f state=closed
```

Note: `{owner}` and `{repo}` are auto-expanded by `gh api` from the git remote. `${milestone_title}` is a shell variable.

### Update Tracking Files

1. **SPRINT-STATUS.md.** Add a release row to `SPRINT-STATUS.md` at the path
   from `project.toml [paths] sprints_dir`:
   ```
   | {milestone} Release | Released | {date} | — | v{version} |
   ```

2. **Project navigation docs.** If the release changes project navigation (new
   binaries, new commands, changed paths), update the navigation file specified
   by `project.toml [paths] cheatsheet` (if configured) to reflect the current
   state.

### Notify

Print the release summary:

```
Release {version} published: {release_url}
Milestone closed. Tracking files updated.
```

---

## CI Failure Response

If CI fails during any step of the release process, follow this procedure.

1. **Read the failure logs.**
   ```bash
   gh run list --branch {base_branch} --limit 1 --json databaseId --jq '.[0].databaseId'
   # then:
   gh run view {run_id} --log-failed
   ```

2. **Flaky test.** If the failure is a known flaky test (intermittent, unrelated
   to release changes), re-run:
   ```bash
   gh run rerun {run_id}
   ```
   Wait for completion and verify success before continuing.

3. **Real failure.** If the failure is legitimate:
   - Create a hotfix branch: `git checkout -b hotfix/release-{version}-fix`
   - Fix the issue, commit, open a PR, get it reviewed and merged
   - Return to Step 1 (Gate Validation) and restart the release process

4. **Track all CI interactions.** Record every CI failure, re-run, and hotfix in
   the release notes under a "Release Process Notes" section.

---

<!-- §sprint-release.rollback -->
<!-- §sprint-release.rollback_procedure -->
## Rollback

If a published release must be rolled back, execute these steps and document the
reason.

### Delete the Release and Tag

```bash
gh release delete v{version} --yes
git tag -d v{version}
git push origin :refs/tags/v{version}
```

### Document the Rollback

Add an entry to `SPRINT-STATUS.md` at the path from `project.toml [paths] sprints_dir`:

```
| {milestone} Release | Rolled Back | {date} | — | v{version} rolled back: {reason} |
```

### Re-release

After fixing the issue that caused the rollback, restart from Step 1 (Gate
Validation). Increment the patch version (e.g., v0.1.0 becomes v0.1.1).

---

## References

- `skills/sprint-release/references/release-checklist.md` -- milestone-specific gate criteria, required
  test counts, and acceptance thresholds
- `SPRINT-STATUS.md` (at `project.toml [paths] sprints_dir`) -- sprint
  completion status and velocity tracking
- `skills/sprint-release/scripts/release_gate.py` -- gate validation, version
  calculation, release notes, and publishing automation
