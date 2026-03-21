# 0e — Git Churn Analysis (Pass 36)

Generated: 2026-03-21

## Last 4 commits (Pass 35 fixes)

```
d8d2185 chore: bug-hunter pass 35 — recon reports, punchlist, status
debe769 fix: remaining MEDIUM/LOW — persona collision, saga/epic fields, regex align
6ea4eef fix: MEDIUM items — hooks hardening, release_gate, sprint_init
7e07bc5 fix: HIGH items BH35-001 through BH35-003, BH35-021, BH35-022
```

Net: +297 / -5186 lines (bulk deletion of old recon reports).

## Source files changed (pass 35 fixes only)

| File | Lines changed | What changed |
|------|--------------|--------------|
| `scripts/kanban.py` | 43 | All mutation commands (transition/assign/update) switched from `lock_story` to `lock_sprint` |
| `.claude-plugin/hooks/review_gate.py` | 33 | Push-check refactored: `+refspec` strip, `refs/heads/` strip, pipe splitting, single-quoted TOML, inline comments |
| `skills/sprint-release/scripts/release_gate.py` | 20 | `gate_ci` workflow filter, `write_version_to_toml` single-quote support, EOF handling |
| `scripts/sprint_init.py` | 40 | Exclude `sprint-config/` from scan, YAML multiline block variants, PRD OSError guard, persona stem collision, empty backlog scaffold, DoD preservation |
| `.claude-plugin/hooks/verify_agent_output.py` | 12 | `splitlines()` -> `split('\n')`, inline section comments, continuation-line comment stripping, `\bcommitted\b` word boundary |
| `scripts/manage_epics.py` | 9 | Story heading regex alignment `\s+` after colon, Saga/Epic fields in formatted output |
| `.claude-plugin/hooks/session_context.py` | 6 | `splitlines()` -> `split('\n')`, inline section comments |
| `.claude-plugin/hooks/commit_gate.py` | 4 | Word-boundary matching for config check commands |
| `tests/test_hooks.py` | 109 added | Tests for push bypass variants, single-quoted TOML, inline comments, word boundaries |
| `tests/test_verify_fixes.py` | 78 added | Regression tests for BH35 fixes |

## Top 10 churn files (last 10 commits)

| Touches | File |
|---------|------|
| 6 | `tests/test_hooks.py` |
| 4 | `.claude-plugin/hooks/review_gate.py` |
| 3 | `scripts/sprint_init.py` |
| 3 | `scripts/kanban.py` |
| 2 | `tests/test_verify_fixes.py` |
| 2 | `tests/test_pipeline_scripts.py` |
| 2 | `tests/test_hexwise_setup.py` |
| 2 | `skills/sprint-monitor/scripts/check_status.py` |
| 2 | `scripts/smoke_test.py` |
| 2 | `scripts/manage_sagas.py` |

## Focus areas for regression audit

### 1. kanban.py lock scope change (HIGH risk)

All three mutation commands (transition, assign, update) were moved from
`lock_story()` to `lock_sprint()`. This is a correctness fix (prevents
sync_tracking clobbering) but changes the granularity of locking:

- **Regression risk**: Two stories in different sprints no longer run
  concurrently if one uses `lock_sprint`. However, the code keys on the
  sprint number (`sprints_dir / f"sprint-{sprint}"`), so cross-sprint
  locking is not an issue. Within the same sprint, all mutations are now
  serialized, which is strictly safer but slower.
- **Audit**: Verify `lock_story()` is no longer called anywhere in the
  main() dispatch. Confirm `lock_sprint()` acquires the same `.lock` file
  that `sync_tracking.py` uses.

### 2. review_gate.py push-check refactor (HIGH risk)

The push-block logic changed in three ways simultaneously:
1. All positional args checked against base (not just `[1:]`)
2. `+` prefix stripping for force-push refspecs
3. `refs/heads/` prefix stripping

- **Regression risk**: Checking positional[0] (the remote name) against
  base could false-positive if a remote happens to be named the same as
  the base branch (e.g., remote named "main"). This seems unlikely but
  is worth verifying.
- **Audit**: Review whether `origin` or other common remote names could
  ever equal `base`. Check that the pipe-splitting regex `\|\||\ |` does
  not break on legitimate pipe characters inside quoted strings.

### 3. sprint_init.py persona stem collision (MEDIUM risk)

New logic disambiguates persona files with the same stem by prefixing
with the parent directory name (`{parent}-{stem}.md`).

- **Regression risk**: Downstream code that reads persona filenames from
  `team/INDEX.md` or symlinks may not expect the `{parent}-{stem}` pattern.
  The team index is regenerated with the new names, but any hardcoded
  assumptions about persona file naming could break.
- **Audit**: Check `get_team_personas()` and persona lookup in
  `sprint-run` to confirm they read from INDEX.md rather than assuming
  filenames.

### 4. sprint_init.py DoD preservation (MEDIUM risk)

`generate_definition_of_done()` now skips if the file already exists.

- **Regression risk**: If the skeleton template is updated with new
  baseline items, re-running init will not propagate them to existing
  projects. This is intentional (preserving retro additions) but should
  be documented.
- **Audit**: Confirm no tests expect DoD to be overwritten on re-run.

### 5. Inline TOML parsing consistency (MEDIUM risk)

Three hooks (`review_gate`, `session_context`, `verify_agent_output`)
all received the same two fixes: `splitlines()` -> `split('\n')` and
inline section-comment stripping (`s.split('#')[0].strip()`).

- **Regression risk**: The `split('#')` approach for stripping comments
  is naive — it would break if a TOML value contains a literal `#`
  character inside quotes (e.g., `name = "C# Project"`). The hooks only
  read specific keys (`base_branch`, `sprints_dir`, `check_commands`)
  where `#` in values is unlikely, so practical risk is low.
- **Audit**: Search for any TOML values in skeleton templates or test
  fixtures that contain `#` characters.

### 6. verify_agent_output.py continuation-line comment stripping (LOW risk)

New `_strip_inline_comment()` call on array continuation lines prevents
phantom items from comments containing quoted strings.

- **Audit**: Verify `_strip_inline_comment()` correctly handles strings
  containing `#` (should only strip comments outside quotes). Check for
  edge cases like `"value # with hash"  # actual comment`.

### 7. manage_epics.py story heading regex (LOW risk)

Changed from `\s*` (optional space) to `\s+` (required space) after the
colon in `### US-NNN: Title` headings.

- **Regression risk**: Any existing milestone file with `### US-001:Title`
  (no space after colon) would no longer be matched.
- **Audit**: Check whether `populate_issues.py` always emits a space
  after the colon (it should, since the regex was aligned to match it).
