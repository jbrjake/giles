# Release Checklist

Gate criteria that must pass before each milestone release ships. Gate criteria
are defined per milestone in project.toml `[release]` milestones gate_file.
Each project defines its own gates.

## Per-Milestone Checklist Template

### Stories Gate

- [ ] All stories for this milestone complete
- [ ] All story tracking files show status: done
- [ ] All GitHub issues in relevant sprint milestones are closed

### Test Gate

- [ ] Golden path tests pass end-to-end
- [ ] All P0 test cases pass
- [ ] Full test suite passes with zero failures (use command from project.toml `[ci]`)
- [ ] No P0 bugs remain open

### Performance Gate

- [ ] Performance criteria defined in milestone gate file are met
- [ ] Platform-specific build targets pass (as defined in project.toml `[release]`)

### Platform Gate

- [ ] All target platform builds pass CI
- [ ] Graceful shutdown completes within configured timeout

### Milestone Acceptance

Acceptance criteria are defined in the milestone gate file. Walk through each
criterion and verify with evidence (test output, logs, measurements).

### Release Artifacts

- [ ] Release artifacts built for all target platforms
- [ ] Release notes generated from sprint demos
- [ ] Git tag created and pushed
- [ ] GitHub Release published with artifacts attached
