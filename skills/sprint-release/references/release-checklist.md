# Release Checklist

Gate criteria that must pass before each milestone release ships.
These gates map to `release_gate.py validate_gates()`. Each gate
runs in order; first failure stops the pipeline.

## Per-Milestone Checklist Template

<!-- §release-checklist.stories_gate_gate_stories -->
### Stories Gate (`gate_stories`)

- [ ] All GitHub issues in the milestone are closed
- [ ] All story tracking files show status: done

<!-- §release-checklist.ci_gate_gate_ci -->
### CI Gate (`gate_ci`)

- [ ] Most recent CI run on base branch passes (status: success)

<!-- §release-checklist.prs_gate_gate_prs -->
### PRs Gate (`gate_prs`)

- [ ] No open PRs target this milestone

<!-- §release-checklist.tests_gate_gate_tests -->
### Tests Gate (`gate_tests`)

- [ ] All `check_commands` from project.toml `[ci]` pass
- [ ] Golden path tests pass end-to-end
- [ ] No P0 bugs remain open

<!-- §release-checklist.build_gate_gate_build -->
### Build Gate (`gate_build`)

- [ ] `build_command` from project.toml `[ci]` succeeds
- [ ] Binary exists at `binary_path` (if configured)

<!-- §release-checklist.post_gate_release_steps -->
## Post-Gate Release Steps

After all gates pass, `do_release()` handles:

1. Calculate next semantic version from conventional commits
2. Write version to project.toml `[release]`
3. Commit, tag, and push
4. Generate release notes
5. Create GitHub Release with artifacts
6. Close the milestone
