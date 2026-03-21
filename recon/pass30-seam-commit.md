# Seam Audit: `scripts/commit.py` <-> `.claude-plugin/hooks/commit_gate.py`

**Auditor:** Claude Opus 4.6 (1M context)
**Date:** 2026-03-21
**Scope:** Interaction between the conventional commit wrapper and the commit verification hook.

---

## Architecture Summary

- **`commit.py`** is a CLI script invoked by agents via Bash (`python scripts/commit.py "feat: ..."`). It validates conventional commit format, checks atomicity (staged files don't span too many directories), and shells out to `git commit`.
- **`commit_gate.py`** is a Claude Code plugin hook registered as both PreToolUse and PostToolUse for the Bash tool. On PreToolUse it blocks `git commit` and `scripts/commit.py` invocations if tests haven't been run. On PostToolUse it records verification state when test commands succeed.

The two operate at different layers: commit_gate is infrastructure (hook), commit.py is application (script). The hook fires *before* the Bash tool runs the command, so commit_gate evaluates first.

---

## Question 1: Does commit_gate fire when commit.py is invoked?

**YES.** The hook registration in `plugin.json` (line 29-32) fires commit_gate on *every* PreToolUse of the Bash tool. When the agent runs `python scripts/commit.py "feat: add thing"`, the command string is passed to `check_commit_allowed()`, which matches on `re.search(r'scripts/commit\.py\b', command)` (line 128).

**Confirmed by test:** `test_blocks_commit_py` (test_hooks.py:561-567) tests exactly this scenario.

**No bypass.** commit.py calls `subprocess.run(["git", "commit", ...])` internally (line 98), but that subprocess is *not* visible to the Claude Code hook infrastructure. The hooks only see the top-level Bash tool command. So the inner `git commit` does not trigger a second hook evaluation. This is correct behavior -- the gate fires on the outer invocation.

---

## Question 2: Does commit_gate recognize commit.py invocations?

**YES.** Two patterns in `check_commit_allowed()` (lines 126-129):
```python
is_commit = (
    re.search(r'\bgit\s+commit\b', command) or
    re.search(r'scripts/commit\.py\b', command)
)
```

### BUG FOUND: Path sensitivity in regex

The regex `r'scripts/commit\.py\b'` matches relative paths like `scripts/commit.py` and absolute paths like `/path/to/scripts/commit.py`. However, the implementer agent template (implementer.md:165) instructs:

```
python "${CLAUDE_PLUGIN_ROOT}/scripts/commit.py" "type(scope): description"
```

This expands to something like `python /Users/jonr/Documents/non-nitro-repos/giles/scripts/commit.py "feat: ..."`. The regex `scripts/commit\.py\b` will match because it looks for the substring anywhere. **This works correctly.**

However, there is a **minor gap**: if someone invokes `python commit.py` from within the `scripts/` directory (using `cd scripts && python commit.py`), the regex would NOT match, and the gate would be bypassed. The inner `git commit` subprocess would also not be caught by the hook. This is a low-probability scenario since the agent templates always use the full path, but it is a defense-in-depth gap.

**Severity: LOW** -- agent templates always use full paths.

---

## Question 3: Do they agree on what constitutes a valid commit? Could they conflict?

They enforce **orthogonal concerns** with no overlap:

| Concern | commit.py | commit_gate.py |
|---------|-----------|----------------|
| Commit message format | YES (conventional commits) | NO |
| Atomicity (directory spread) | YES (3+ dirs requires --force) | NO |
| Tests run before commit | NO | YES (working tree hash) |
| Staged files exist | YES (check_atomicity rejects empty) | Indirectly (needs_verification checks for staged source files) |

**No conflict possible on validation logic.** They check completely different things.

### BUG FOUND: Execution order creates confusing UX on double-rejection

When commit_gate blocks (exit code 2 with message), the Bash tool command never executes. This means commit.py's own validations (bad message format, atomicity violation) are never reached. If the user then runs tests and retries with the same bad commit message, commit_gate allows it but commit.py rejects with a different error. The user gets **two different errors on two different attempts** for the same command, which could be confusing.

This is architectural -- commit_gate is a pre-flight check and commit.py is the actual validator. The double-gate pattern means errors are discovered serially, not all at once.

**Severity: LOW** -- this is inherent to the hook-before-script architecture and the errors are both actionable.

---

## Question 4: Does check_atomicity() interact with or duplicate commit_gate logic?

**No duplication.** `check_atomicity()` counts top-level directories of staged files. `commit_gate.py` checks whether tests have been run since the last code change using a working tree hash. They both happen to call `git diff --cached --name-only`, but for completely different purposes:

- commit.py: counts directories to enforce atomicity
- commit_gate.py (`_has_staged_source_files`): checks if any staged files are source files to decide if verification is needed

No functional overlap or conflict.

---

## Question 5: Edge cases where one succeeds but the other blocks

### Case A: commit_gate allows, commit.py rejects

Scenario: Tests were run (verification state is current), but the commit message is not conventional format.
- commit_gate: ALLOWED (tests are current)
- commit.py: REJECTED ("Invalid conventional commit")
- **Outcome: Correct.** The command runs but commit.py exits non-zero. No commit is made.

### Case B: commit_gate blocks, commit.py would have allowed

Scenario: Working tree changed since tests ran, but the commit message and atomicity are fine.
- commit_gate: BLOCKED (exit code 2, error message printed)
- commit.py: Never runs
- **Outcome: Correct.** Tests need to be re-run.

### Case C: Both would reject for different reasons

Scenario: Tests haven't been run AND the commit message is bad.
- commit_gate fires first, blocks with "Tests have not been run"
- User runs tests, retries with same bad message
- commit.py now rejects with "Invalid conventional commit"
- **Outcome: Confusing but correct.** (See Question 3 analysis above.)

### BUG FOUND: `--dry-run` bypasses commit_gate but reveals nothing useful

Scenario: `python scripts/commit.py --dry-run "feat: preview"` is caught by commit_gate's regex as a commit invocation. commit_gate will block it if tests haven't been run. But `--dry-run` explicitly does NOT commit -- it only validates the message and atomicity.

This means a user cannot use `--dry-run` to preview whether their commit would pass commit.py's checks without first satisfying commit_gate's test-verification requirement. The gate is overly aggressive for dry runs.

**Severity: MEDIUM** -- `--dry-run` is a validation-only mode that should arguably not require test verification. The hook has no way to distinguish `--dry-run` from actual commits because it only sees the raw command string.

### BUG FOUND: Working tree hash mismatch between test run and commit

The `_working_tree_hash()` function hashes `git diff HEAD` output (all staged + unstaged changes relative to HEAD). After tests pass, `mark_verified()` records this hash. But between test run and commit, the user typically stages files with `git add`. This changes the `git diff HEAD` output (staged files disappear from the diff if they match HEAD, or the diff content changes). So the hash after `git add` will differ from the hash at test-run time.

However, this is **not** actually a bug because: `git diff HEAD` captures ALL changes (staged and unstaged). Staging files does not change the total diff relative to HEAD. A file that was modified and then staged still appears in `git diff HEAD`. So the hash remains stable through `git add`.

The hash WOULD change if the user makes additional code edits after running tests but before committing, which is exactly the scenario commit_gate is designed to catch. **This is correct behavior.**

### BUG FOUND: `_load_config_check_commands` has a flawed inline TOML parser

In commit_gate.py lines 152-163, the `_load_config_check_commands` function has an inline TOML extraction that does:

```python
val = stripped.split("=", 1)[1] if "=" in stripped else ""
items = _re.findall(r'"([^"]*)"', val + text[text.find(stripped):])
```

The concatenation `val + text[text.find(stripped):]` means it searches from the `check_commands` line through the **entire rest of the file**, not just the array value. This could pick up quoted strings from completely unrelated TOML keys (like `smoke_command`, `build_command`, or strings in other sections).

Compare this to `verify_agent_output.py`'s `_read_toml_key()` which properly handles multi-line arrays by tracking brackets and respecting section boundaries. The two config parsers in the same hook package produce **different results** for the same config file in edge cases.

**Severity: MEDIUM** -- In practice, the `_matches_check_command` function extracts just the first word of each matched string and uses it as a regex, so false matches from unrelated TOML values could cause the gate to recognize non-test commands as test commands, potentially marking verification as passed when it shouldn't be. For example, if `build_command = "cargo build"` appears after `check_commands`, the parser might pick up `"cargo build"`, and then any `cargo` command would count as a check command.

### BUG FOUND: `_matches_check_command` regex injection from config values

In commit_gate.py line 184:
```python
if cfg_cmd and re.search(re.escape(cfg_cmd.split()[0]), command):
```

The `re.escape()` makes this safe from regex injection, but the logic of matching just the first word is overly broad. If `check_commands = ["pytest tests/"]`, then `cfg_cmd.split()[0]` is `"pytest"`, and ANY command containing "pytest" anywhere (even `echo "don't run pytest"`) would be treated as a test command. This is a defense-in-depth concern -- it could allow non-test commands to mark verification as passed.

Meanwhile, `verify_agent_output.py` runs the *exact* configured commands. So the two components disagree on what counts as "running tests":
- `commit_gate.py`: any Bash command whose first word matches a configured check command
- `verify_agent_output.py`: runs the literal configured commands

**Severity: LOW** -- in practice, false positives would require unusual command patterns.

---

## Test Coverage Assessment

The test file (`tests/test_hooks.py`) has solid coverage of commit_gate in isolation:

- `TestCommitGate`: 7 tests covering blocking, allowing, source detection, check command matching, state machine
- `TestPostToolUseVerification`: 4 tests covering PostToolUse recording
- `TestHookMainEntryPoints`: 3 tests for commit_gate main/post_main entry points
- `TestSessionIdConsistency`: 2 tests for state file path consistency
- Bridge tests (lines 299-333): 2 tests verifying verify_agent_output -> commit_gate bridging

### MISSING TEST: commit.py -> commit_gate interaction

There is **no test** that simulates the full flow where:
1. commit_gate fires as PreToolUse
2. Allows the command
3. commit.py then runs and validates the message
4. commit.py's inner `git commit` subprocess executes

The existing tests for commit.py (in `test_gh_interactions.py`, `test_verify_fixes.py`) test commit.py in isolation with mocked subprocess. The commit_gate tests use `_state_override` to bypass real state. **No test exercises the two components in sequence.**

### MISSING TEST: `--dry-run` blocked by commit_gate

No test verifies whether `python scripts/commit.py --dry-run "feat: preview"` is blocked by commit_gate or allowed.

### MISSING TEST: `_load_config_check_commands` vs `_read_toml_key` parity

No test compares the output of commit_gate's inline TOML parser against verify_agent_output's `_read_toml_key` for the same config file, which would catch the parser divergence described above.

---

## Summary of Findings

| ID | Severity | Description |
|----|----------|-------------|
| S30-001 | MEDIUM | `--dry-run` mode blocked by commit_gate despite not actually committing |
| S30-002 | MEDIUM | `_load_config_check_commands` inline parser reads past array boundary, may pick up unrelated TOML strings |
| S30-003 | LOW | `cd scripts && python commit.py` bypasses commit_gate regex |
| S30-004 | LOW | Serial error discovery (gate then script) gives users two different errors on two attempts |
| S30-005 | LOW | `_matches_check_command` first-word matching is overly broad; disagrees with verify_agent_output's exact command execution |
| S30-006 | -- | Missing integration test for commit.py -> commit_gate sequence |
| S30-007 | -- | Missing test for `--dry-run` + commit_gate interaction |
| S30-008 | -- | Missing parity test for the two TOML parsers in the hooks package |
