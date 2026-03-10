# Giles Plugin: Maximum Confidence Ship

**Date:** 2026-03-09
**Goal:** Get giles into a shippable state with full release automation, enforced conventional commits, auto-calculated semver, comprehensive mock tests, and a full lifecycle integration harness.

**Repository:** jbrjake/giles
**Marketplace:** jbrjake/claude-plugin-marketplace

## Context

The prior ship-giles plan (v0.2.0) fixed 5 bugs in config generation, added self-validation, agent frontmatter, and generic evals. The plugin is structurally complete but missing:

- Release automation script (sprint-release is the only skill without a backing script)
- Enforced conventional commits across all skills
- Automatic semantic versioning from commit log
- `--help` on all scripts
- A getting-started doc for humans
- Mock-based tests for gh CLI interactions
- End-to-end lifecycle test harness

A full gh CLI command audit was performed against current docs. All commands are correct except one jq expansion bug in sprint-release/SKILL.md:173 and a `repos/${repo}/` vs `repos/{owner}/{repo}/` inconsistency.

## Section 1: Commit Convention Enforcement

### 1a. `scripts/commit.py` — Conventional Commit Wrapper

Every skill in giles that makes a commit uses this script instead of raw `git commit`.

**CLI:**
```
python scripts/commit.py "feat: add user authentication"
python scripts/commit.py "fix(parser): handle empty input"
python scripts/commit.py --dry-run "feat!: redesign API surface"
python scripts/commit.py --body "BREAKING CHANGE: removed old API" "feat!: new API"
python scripts/commit.py --force "refactor: broad cleanup"
```

**Validation (strict):**
- Message MUST match: `<type>[optional scope][!]: <description>`
- Allowed types: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`, `ci`, `perf`, `build`, `style`
- `!` after type/scope = breaking change
- Body/footer supported via `--body` flag for `BREAKING CHANGE:` trailers
- Rejects if no staged changes

**Atomicity enforcement:**
- Checks `git diff --cached --stat`
- Groups staged files by top-level directory
- If files span 3+ top-level directories, prints warning and requires `--force`
- Heuristic, not hard block — cross-cutting changes (e.g., skill + script + reference) are common and `--force` is the expected escape

**Git commit invocation:**
- Runs `subprocess.run(["git", "commit", "-m", message])` (list args, not shell string)
- With `--body`: `subprocess.run(["git", "commit", "-m", title, "-m", body])`
- With `--dry-run`: prints what would be committed but does not run `git commit`
- With `--force --dry-run`: shows the atomicity warning but indicates commit would proceed

**Dual interface — CLI and importable:**
- CLI: `python scripts/commit.py "feat: ..."` (skills and agents invoke this way)
- Import: `from commit import validate_message, check_atomicity` (for `release_gate.py` and tests)
- `release_gate.py` imports and calls `validate_message()` + runs `subprocess.run(["python", commit_py_path, message])` to get the full CLI behavior including the actual `git commit`

**Uses argparse** (new script with flags).

### 1b. Version Calculation in `release_gate.py`

Version is calculated, not stored. Computed at release time:

1. Find latest semver tag: `git tag --list 'v*' --sort=-version:refname`, filter to valid `vX.Y.Z`. If none found, use `0.1.0` as the **base** to bump from (not the result).
2. Parse all commits since that tag (or all commits if no tag): `git log v{base}..HEAD --format="%s%n%b---COMMIT---"` (use `git log --format=...` with no range if no prior tag).
3. Determine bump:
   - `BREAKING CHANGE:` trailer or `!` suffix -> major
   - `feat:` or `feat(...):` -> minor
   - Everything else -> patch
   - Highest wins
4. Calculate next version: base + bump. Examples: base `0.1.0` + feat -> `0.2.0`. Base `0.1.0` + fix only -> `0.1.1`. Base `1.2.3` + breaking -> `2.0.0`.
5. Write to `project.toml [release] version` using regex replacement on the raw file: find `version = "..."` in `[release]` section and replace. If `[release]` section doesn't exist, append it. No full TOML serializer needed — just targeted line replacement (same approach `update_burndown.py` uses for SPRINT-STATUS.md regex patching).
6. Commit via `commit.py`: `chore: bump version to X.Y.Z`

## Section 2: `release_gate.py` — Full Release Flow

**Location:** `skills/sprint-release/scripts/release_gate.py`

**Import pattern:** Same `sys.path.insert(0, ...)` four levels up to `scripts/validate_config.py`.

**CLI:**
```
python release_gate.py validate "Sprint 1: Walking Skeleton"
python release_gate.py release "Sprint 1: Walking Skeleton"
python release_gate.py --dry-run release "Sprint 1: Walking Skeleton"
python release_gate.py --help
```

**Uses argparse** (subcommands + flags).

### Gate Validation (sequential, first failure stops)

| Gate | Method | Pass Criteria |
|------|--------|---------------|
| Stories | `gh issue list --milestone <title> --state open` | Zero open issues |
| CI | `gh run list --branch main --limit 1 --json status,conclusion` | `conclusion == "success"` |
| PRs | `gh pr list` + filter by milestone | None open targeting milestone |
| Tests | Run each `project.toml [ci] check_commands` | All exit 0 |
| Build | Run `project.toml [ci] build_command` | Exit 0, binary at `binary_path` if configured |

Gate summary table printed before proceeding (matches SKILL.md format).

### Release Flow (after gates pass)

1. Calculate version from commit log (Section 1b)
2. Write version to `project.toml [release] version`
3. Commit via `commit.py`: `chore: bump version to X.Y.Z`
4. Create annotated tag: `git tag -a vX.Y.Z -m "Release X.Y.Z: {milestone title}"`
5. Push tag: `git push origin vX.Y.Z`
6. Generate `release-notes.md`:
   - **Highlights** — 3-5 bullet points covering the most important changes
   - **Features** — grouped `feat:` commits
   - **Fixes** — grouped `fix:` commits
   - **Breaking Changes** — any `!` or `BREAKING CHANGE` commits (omit section if none)
   - **Full Changelog** — GitHub compare link `v{prev}...v{new}`
7. `gh release create vX.Y.Z --title "{project_name} X.Y.Z" --notes-file release-notes.md` (plus binary if configured)
8. Close milestone: `gh api repos/{owner}/{repo}/milestones/{N} -X PATCH -f state=closed`
9. Update SPRINT-STATUS.md with release row
10. Print release URL from `gh release view vX.Y.Z --json url --jq '.url'`

### Dry-run Behavior

Gates (read-only) execute normally. All mutations print `[DRY-RUN] would ...` with exact commands. Release notes generated and printed to stdout but not written.

**Exit codes:** 0 = success, 1 = gate failure, 2 = usage error.

## Section 3: `--help` for All Scripts

Each existing script's `main()` gets a guard:

```python
if len(sys.argv) > 1 and sys.argv[1] in ("-h", "--help"):
    print(__doc__.strip())
    sys.exit(0)
```

Uses existing module docstrings. No argparse for existing scripts (simple CLIs).

New scripts (`release_gate.py`, `commit.py`) use argparse from the start.

**Scripts affected:** `validate_config.py`, `sprint_init.py`, `sprint_teardown.py`, `bootstrap_github.py`, `populate_issues.py`, `setup_ci.py`, `check_status.py`, `sync_tracking.py`, `update_burndown.py`.

**Compatibility:** The guard intercepts `-h`/`--help` before any existing argument parsing. No existing script uses `-h` as a meaningful argument, so this is safe. Scripts that accept `sys.argv[1]` as a positional arg (e.g., `validate_config.py [config-dir]`) will show help instead of treating `--help` as a path.

## Section 4: SKILL.md gh Command Fixes

### Bug: `sprint-release/SKILL.md:173-176`

`{milestone_title}` inside single-quoted `--jq` won't expand. Fix:

```bash
milestone_number=$(gh api repos/{owner}/{repo}/milestones \
  --jq ".[] | select(.title | contains(\"${milestone_title}\")) | .number")
```

### Inconsistency: `repos/${repo}/` vs `repos/{owner}/{repo}/`

Update `sprint-release/SKILL.md` lines 173, 175 and `sprint-monitor/SKILL.md` line 139 to use `repos/{owner}/{repo}/` (gh auto-placeholder) for consistency with all scripts.

### Conventional commit references

Update all SKILL.md files and agent templates to reference `scripts/commit.py` instead of raw `git commit -m`.

## Section 5: README.md

**Audience:** Users with a project that has personas and backlogs, who need to know what to do before the plugin starts guiding.

**Structure:**

1. **What is giles** — 2 sentences
2. **Prerequisites** — Claude Code, `gh` CLI + auth, git repo with GitHub remote, Python 3.10+, superpowers plugin
3. **Install giles** — `claude plugin add jbrjake/giles` (from jbrjake/claude-plugin-marketplace)
4. **Prepare your project** — persona files (required headings), milestone docs (story table format), optional docs
5. **First run** — `sprint-setup` then `sprint-run`
6. **Lifecycle overview** — `sprint-setup -> sprint-run (repeat) -> sprint-release -> sprint-teardown`
7. **Commit conventions** — giles enforces conventional commits via `commit.py`, versions auto-calculated from commit log

## Section 6: Mock-Based Unit Tests

**Location:** `scripts/test_gh_interactions.py`

Monkey-patch at the function level using `unittest.mock.patch`. stdlib `unittest` only.

**Mock contract by function signature:**
- `gh(args) -> str` (used by check_status.py, sync_tracking.py, update_burndown.py, release_gate.py): mock returns a string (JSON or plain text). Raise `RuntimeError` to simulate failure.
- `run_gh(args, check) -> subprocess.CompletedProcess` (used by bootstrap_github.py, populate_issues.py): mock returns `subprocess.CompletedProcess(args=[], returncode=0, stdout="...", stderr="")`. Set `returncode=1` and `stderr="already_exists"` to simulate failures.

### Coverage

| Script | Functions Tested | Key Scenarios |
|--------|-----------------|---------------|
| `release_gate.py` | `validate_gates()`, `calculate_version()`, `create_release()` | All gates pass, each gate fails individually, version calculation (no tags, feat, fix, breaking) |
| `commit.py` | `validate_message()`, `check_atomicity()` | All types accepted, missing prefix rejected, `!` accepted, 3+ dirs warned |
| `check_status.py` | `check_ci()`, `check_prs()`, `check_milestone()` | Passing/failing runs, PR states, milestone progress |
| `bootstrap_github.py` | `create_label()`, `create_milestones_on_github()` | Success, already-exists |
| `populate_issues.py` | `create_issue()`, `get_existing_issues()` | Creation, idempotency |
| `sync_tracking.py` | `find_milestone_title()`, `list_issues()`, `get_linked_pr()` | Sync changes, no changes |
| `update_burndown.py` | `find_milestone()`, `list_milestone_issues()` | SP calculation, burndown output |

### Key `release_gate.py` scenarios

- All gates pass -> release proceeds
- One open issue -> stories gate fails, stops
- CI failing -> CI gate fails
- No semver tags + only `fix:` commits -> version 0.1.1 (bumps from base 0.1.0)
- No semver tags + `feat:` commit -> version 0.2.0 (bumps from base 0.1.0)
- Mix of `feat:` and `fix:` -> minor bump
- `feat!:` -> major bump
- `--dry-run` -> no mutations

## Section 7: Integration Test Harness

**Location:** `scripts/test_lifecycle.py`

### FakeGitHub Backend

```python
class FakeGitHub:
    labels: dict[str, dict]
    milestones: dict[str, dict]
    issues: dict[int, dict]
    releases: dict[str, dict]
    runs: list[dict]
    prs: list[dict]
```

`fake_gh()` routes commands to handlers. Injected by patching `subprocess.run` matching `["gh", ...]`.

### Stages Tested

| Stage | Script | Assertions |
|-------|--------|------------|
| Init | `sprint_init.py` | Config generated, self-validates |
| Bootstrap | `bootstrap_github.py` | Labels, milestones in fake |
| Populate | `populate_issues.py` | Issues with correct labels/milestones |
| Monitor | `check_status.py` | Correct counts from fake |
| Sync | `sync_tracking.py` | Tracking files match fake state |
| Burndown | `update_burndown.py` | Burndown reflects fake progress |
| Release (dry) | `release_gate.py --dry-run` | Gates evaluated, version calculated, no mutations |
| Release (live) | `release_gate.py release` | Tag created, release in fake, milestone closed |
| Commit | `commit.py` | Messages validated/rejected |

### What stays real

Git operations (init, add, commit, tag) run against a real temp repo via `subprocess.run(["git", ...])`. Only `gh` is faked — the `subprocess.run` patch matches on `args[0] == "gh"` and passes through all other commands. `commit.py` also uses `subprocess.run(["git", ...])`, so its git operations are real too.

**Test runner:** `python scripts/test_lifecycle.py -v` (same as `verify_fixes.py` — no test runner config needed).

## Files Changed (Summary)

| File | Change |
|------|--------|
| `scripts/commit.py` | NEW — conventional commit wrapper |
| `skills/sprint-release/scripts/release_gate.py` | NEW — gate validation + release automation |
| `scripts/test_gh_interactions.py` | NEW — mock-based unit tests |
| `scripts/test_lifecycle.py` | NEW — full lifecycle integration harness |
| `README.md` | NEW — getting-started doc |
| `scripts/validate_config.py` | Add `--help` guard |
| `scripts/sprint_init.py` | Add `--help` guard |
| `scripts/sprint_teardown.py` | Add `--help` guard |
| `skills/sprint-setup/scripts/bootstrap_github.py` | Add `--help` guard |
| `skills/sprint-setup/scripts/populate_issues.py` | Add `--help` guard |
| `skills/sprint-setup/scripts/setup_ci.py` | Add `--help` guard |
| `skills/sprint-monitor/scripts/check_status.py` | Add `--help` guard |
| `skills/sprint-run/scripts/sync_tracking.py` | Add `--help` guard |
| `skills/sprint-run/scripts/update_burndown.py` | Add `--help` guard |
| `skills/sprint-release/SKILL.md` | Fix jq bug, use auto-placeholders, reference commit.py |
| `skills/sprint-monitor/SKILL.md` | Fix `repos/` placeholder inconsistency |
| `skills/sprint-run/SKILL.md` | Reference commit.py |
| `skills/sprint-run/agents/implementer.md` | Reference commit.py |
| `skills/sprint-run/agents/reviewer.md` | Reference commit.py |
| `skills/sprint-setup/SKILL.md` | Reference commit.py |

## Out of Scope

- No changes to `validate_config.py` logic (only `--help` guard)
- No changes to skeleton templates
- No new skills
- No pre-commit git hooks (enforcement is via `commit.py`, not git hooks)
