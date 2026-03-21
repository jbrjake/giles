# Hooks Integration Audit

Audited 2026-03-20. Four hook files, one shared helper, plus plugin.json registration.
Re-audited against current code (post prior fixes for H-004, H-006, H-008, H-013, H-014, H-017).

---

### FINDING-1: commit_gate marks verification BEFORE the test command runs — failed tests still count as "verified"

**Files:** `.claude-plugin/hooks/commit_gate.py`, `.claude-plugin/plugin.json`
**Severity:** HIGH
**Description:**
`commit_gate.py` is registered as a `PreToolUse` hook for the Bash tool (plugin.json line 29-32). When a check command like `pytest` is about to run, `main()` calls `mark_verified()` at line 171 *before the Bash tool executes the command*. This records the working-tree hash unconditionally. If the test command fails (non-zero exit), the hash is still stored as "verified." A subsequent `git commit` compares the current hash against the stored one, finds a match, and allows the commit.

The hook has no access to the command's exit code because PreToolUse fires before execution. There is no corresponding PostToolUse hook registered to check the result.

**Evidence:**
```python
# commit_gate.py lines 169-172
# If running a check command, record current working tree state
if _matches_check_command(command):
    mark_verified()       # <-- runs BEFORE pytest executes
    sys.exit(0)
```
Plugin.json has no PostToolUse registration for commit_gate.

---

### FINDING-2: session_context.py uses relative paths for DoD and risk register, ignoring project root

**Files:** `.claude-plugin/hooks/session_context.py`
**Severity:** HIGH
**Description:**
`_get_config_paths()` correctly uses `_find_project_root()` to locate `project.toml` (line 39). But `main()` passes the TOML values directly to extraction functions without prepending the project root:

1. `extract_retro_action_items(sprints_dir)` at line 174 receives the raw TOML value (e.g., `"sprints"`), which is a path relative to the project root. If CWD is not the project root, this resolves to the wrong directory.

2. `extract_dod_retro_additions()` at line 175 defaults to `config_dir="sprint-config"` (a relative path). It does not use `_find_project_root()`.

3. `extract_high_risks()` at line 176 also defaults to `config_dir="sprint-config"` (a relative path). Same problem.

The result: `_get_config_paths()` successfully finds and reads the TOML via `_find_project_root()`, but the data extracted from the TOML is then used with relative path resolution against CWD, not the project root. The hook silently returns no context when CWD differs from the project root.

**Evidence:**
```python
# session_context.py lines 167-176
def main() -> None:
    paths = _get_config_paths()          # uses _find_project_root()
    if not paths:
        sys.exit(0)
    sprints_dir = paths.get("sprints_dir", "")
    action_items = extract_retro_action_items(sprints_dir) if sprints_dir else []
    dod_additions = extract_dod_retro_additions()  # defaults to relative "sprint-config"
    risks = extract_high_risks()                   # defaults to relative "sprint-config"
```

---

### FINDING-3: verify_agent_output.py runs check_commands but doesn't update commit_gate verification state

**Files:** `.claude-plugin/hooks/verify_agent_output.py`, `.claude-plugin/hooks/commit_gate.py`
**Severity:** HIGH
**Description:**
When an implementer agent completes, `verify_agent_output.py` runs all `check_commands` from `project.toml` (line 314). If all pass, it reports "VERIFICATION PASSED." But it never calls `commit_gate.mark_verified()` to record that the working tree has been verified. This means:

1. Agent finishes implementation and commits code.
2. `verify_agent_output.py` runs check_commands and they pass.
3. The orchestrator may then attempt another `git commit` (e.g., for follow-up changes).
4. `commit_gate.py` doesn't know about the verification from step 2 and blocks the commit.

The two hooks operate on completely independent state. `verify_agent_output.py` doesn't import or reference `commit_gate` at all.

**Evidence:**
```
$ grep -r "commit_gate\|mark_verified" .claude-plugin/hooks/verify_agent_output.py
(no matches)
```

---

### FINDING-4: session_context.py `_read_toml_string` doesn't handle single-quoted strings or inline comments

**Files:** `.claude-plugin/hooks/session_context.py`
**Severity:** MEDIUM
**Description:**
`_read_toml_string` (line 21-34) only matches double-quoted TOML strings via `re.match(rf'{key}\s*=\s*"([^"]*)"', stripped)`. It fails for:

- Single-quoted literal strings: `sprints_dir = 'sprints'` (valid TOML)
- Inline comments: `sprints_dir = "sprints" # sprint directory` (the regex captures the full value including the comment as part of the string since `[^"]*` stops at the closing quote... actually this specific case works. But escaped quotes would break it.)
- Bare string values: `sprints_dir = sprints` (not valid TOML, but the main parser accepts bare values as strings in some contexts)

In contrast, `verify_agent_output.py`'s `_read_toml_key` (line 76-109) handles both quote styles, inline comments, and multi-line arrays. The two hooks have different TOML parsing capabilities for the same config file.

If `sprint_init.py` ever generates single-quoted values in project.toml, `session_context.py` would silently return empty strings for `sprints_dir` and `team_dir`, causing the hook to inject no context.

**Evidence:**
```python
# session_context.py line 31 — only double quotes
m = re.match(rf'{key}\s*=\s*"([^"]*)"', stripped)

# verify_agent_output.py line 101 — handles both quote styles
items = re.findall(r'"((?:[^"\\]|\\.)*)"|\'([^\']*)\'', array_text)
```

---

### FINDING-5: review_gate.py check_push is bypassable with compound shell commands

**Files:** `.claude-plugin/hooks/review_gate.py`
**Severity:** MEDIUM
**Description:**
`check_push()` splits the command on whitespace with `command.split()` (line 113). This fails for compound shell commands that Claude Code's Bash tool commonly produces:

- `cd /tmp && git push origin main` — `parts[0]` is `cd`, not `git`. Returns "allowed".
- `git push origin $(echo main)` — refspec is `$(echo`, doesn't match base. Returns "allowed".
- `git add . && git push origin main` — `parts` includes `&&` and subsequent tokens as positional args. The function happens to work by accident here because `main` ends up in positional args, but `&&` also becomes a positional arg.

The PreToolUse hook receives the full Bash command string, which can contain pipes, semicolons, and subshells.

**Evidence:**
```python
# review_gate.py line 113
parts = command.split()
if len(parts) < 2 or parts[0] != "git" or parts[1] != "push":
    return "allowed"
```

---

### FINDING-6: commit_gate.py `_matches_check_command` uses hardcoded patterns instead of reading project.toml

**Files:** `.claude-plugin/hooks/commit_gate.py`
**Severity:** MEDIUM
**Description:**
`_matches_check_command()` (lines 139-150) checks against a hardcoded list of test runner patterns (`pytest`, `cargo test`, `npm test`, etc.). The project's actual `check_commands` from `project.toml` are ignored. If a project uses a custom check command (e.g., `./run_tests.sh`, `tox`, `nox`, `gradlew test`), running that command won't trigger `mark_verified()`, and the commit gate won't recognize that tests have been run.

Meanwhile, `verify_agent_output.py` correctly reads `check_commands` from `project.toml` via `load_check_commands()`. The two hooks use completely different mechanisms to identify check commands.

**Evidence:**
```python
# commit_gate.py lines 141-150 — hardcoded patterns
patterns = [
    r'\bpytest\b', r'\bpython\s+-m\s+pytest\b',
    r'\bcargo\s+test\b', r'\bcargo\s+clippy\b',
    r'\bnpm\s+test\b', r'\bnpm\s+run\s+test\b',
    ...
]

# verify_agent_output.py lines 112-128 — reads from project.toml
def load_check_commands(config_path=None):
    ...
    check = _read_toml_key(text, "ci", "check_commands")
```

---

### FINDING-7: review_gate.py `_log_blocked` writes to hardcoded `sprint-config/sprints/` instead of reading `sprints_dir`

**Files:** `.claude-plugin/hooks/review_gate.py`
**Severity:** LOW
**Description:**
`_log_blocked()` (line 167) writes the audit log to `sprint-config/sprints/hook-audit.log`. This path is hardcoded and doesn't read `paths.sprints_dir` from `project.toml`. If the project uses a custom sprints directory (e.g., `docs/sprints/`), the audit log goes to the wrong location.

The guard at line 165 correctly checks for `project.toml` existence before writing (this was fixed from the prior audit), but the path itself is still wrong for custom configurations.

**Evidence:**
```python
# review_gate.py lines 167-169
log_dir = root / "sprint-config" / "sprints"  # hardcoded, not from config
log_dir.mkdir(parents=True, exist_ok=True)
log_path = log_dir / "hook-audit.log"
```

---

### FINDING-8: review_gate.py `check_push` misclassifies unknown git-push flags, skipping positional args

**Files:** `.claude-plugin/hooks/review_gate.py`
**Severity:** LOW
**Description:**
The flag-parsing logic at lines 126-133 has a heuristic: flags not in the known-standalone list and without `=` are assumed to take a value argument (`i += 2`). This skips the next token. For git push flags that are actually standalone (e.g., `--mirror`, `--prune`, `--atomic`, `--progress`), this causes the next positional argument (the remote name) to be consumed as a flag value.

Example: `git push --mirror origin main`
- `--mirror` is not in the known-standalone list
- Code does `i += 2`, skipping `origin`
- `positional = ["main"]`
- `len(positional) >= 2` is False, so push is allowed

This is a whitelist vs blacklist design flaw: the code blacklists known standalone flags but treats everything else as taking a value.

**Evidence:**
```python
# review_gate.py lines 127-133
if "=" not in part and part not in (
    "--force", "-f", "--force-with-lease",
    "--no-verify", "--verbose", "-v",
    "--dry-run", "-n", "--tags", "--all",
):
    i += 2  # skip flag + value — WRONG for --mirror, --prune, --atomic, etc.
    continue
```

---

### FINDING-9: commit_gate.py `_working_tree_hash` returns empty string for initial commits, disabling the gate

**Files:** `.claude-plugin/hooks/commit_gate.py`
**Severity:** LOW
**Description:**
`_working_tree_hash()` runs `git diff HEAD` (line 63). In a fresh repository with no commits, `HEAD` doesn't exist, so `git diff HEAD` fails with a non-zero exit code. The function returns `""`. When `mark_verified()` is called, it checks `if h:` (line 93) — an empty string is falsy, so nothing is written to the state file. The gate is effectively disabled for initial commits in new repositories.

For `needs_verification()`, if the state file doesn't exist and `_working_tree_hash()` returns `""`, the fallback is `_has_staged_source_files()` (line 107), which correctly detects staged source files. So the gate would block initial commits if there are staged source files but `mark_verified()` can never clear the block (because the hash is always empty). This creates a deadlock where you can never commit in a fresh repo.

**Evidence:**
```python
# commit_gate.py lines 90-94
def mark_verified() -> None:
    h = _working_tree_hash()    # returns "" for repos with no commits
    if h:                        # "" is falsy — nothing is written
        _state_file().write_text(h, encoding="utf-8")

# commit_gate.py lines 105-113
def needs_verification() -> bool:
    sf = _state_file()
    if not sf.exists():
        return _has_staged_source_files()  # returns True if source files staged
    ...
```

---

### FINDING-10: session_context.py `_read_toml_string` doesn't handle subsections like `[paths.extra]`

**Files:** `.claude-plugin/hooks/session_context.py`
**Severity:** LOW
**Description:**
The section detection at line 26-27 uses exact string equality: `stripped == f"[{section}]"`. This means a TOML section like `[paths]` is correctly matched. But if the TOML file has a subsection like `[paths.extra]`, the code sees `[paths.extra]` as a new section and exits the `[paths]` scope. This is actually correct TOML behavior. However, if a key appears after a subsection in the same file:

```toml
[paths]
team_dir = "sprint-config/team"
[paths.extra]
foo = "bar"
sprints_dir = "sprints"    # this is in [paths.extra], NOT [paths]
```

The code would miss `sprints_dir` because it's under the wrong section. This is unlikely to happen with the current project.toml structure but is a latent correctness gap vs the main parser.

**Evidence:**
```python
# session_context.py lines 26-27
if stripped.startswith("["):
    in_section = stripped == f"[{section}]"
```

---

### FINDING-11: Two PreToolUse/Bash hooks share stdin but both try to read it independently

**Files:** `.claude-plugin/plugin.json`, `.claude-plugin/hooks/review_gate.py`, `.claude-plugin/hooks/commit_gate.py`
**Severity:** LOW
**Description:**
`plugin.json` registers two separate `PreToolUse` hooks for the `Bash` tool (lines 15-18 and 28-32). Both hooks call `json.load(sys.stdin)` in their `main()` function. If Claude Code invokes hooks as separate processes (each gets its own copy of stdin), this is fine. But if hooks are invoked sequentially in the same process or share a single stdin pipe, the second hook would get an empty or EOF stdin after the first hook consumed it.

Given that the hooks are registered as separate `command` entries (each spawning a new Python process), this is likely not a real issue. But the behavior depends on Claude Code's plugin hook execution model, which is not documented in the plugin.json.

**Evidence:**
```json
// plugin.json lines 15-18 — first PreToolUse/Bash hook
{"event": "PreToolUse", "tool": "Bash",
 "command": "python ...review_gate.py"}

// plugin.json lines 28-32 — second PreToolUse/Bash hook
{"event": "PreToolUse", "tool": "Bash",
 "command": "python ...commit_gate.py"}
```

---

### FINDING-12: commit_gate.py matches `scripts/commit.py` but not when invoked via python path variants

**Files:** `.claude-plugin/hooks/commit_gate.py`
**Severity:** LOW
**Description:**
`check_commit_allowed()` uses `re.search(r'scripts/commit\.py\b', command)` (line 128) to detect the custom commit script. This matches `python scripts/commit.py "feat: ..."` but not:

- `python3 scripts/commit.py` (some systems use `python3`)
- `python "${CLAUDE_PLUGIN_ROOT}/scripts/commit.py"` (the actual invocation pattern from SKILL.md)
- `/absolute/path/to/scripts/commit.py`

The `${CLAUDE_PLUGIN_ROOT}` pattern is what skill entry points use (per implementer.md line 165). When expanded, the path becomes something like `/Users/.../giles/scripts/commit.py`, which does match the regex. But the `"${CLAUDE_PLUGIN_ROOT}/scripts/commit.py"` literal string (if not expanded by the shell before the hook sees it) would also match since `scripts/commit.py` appears as a substring.

This is a minor robustness concern. The regex works for the common cases.

**Evidence:**
```python
# commit_gate.py line 128
re.search(r'scripts/commit\.py\b', command)

# implementer.md line 165 — actual invocation pattern
# python "${CLAUDE_PLUGIN_ROOT}/scripts/commit.py" "type(scope): description"
```

---

### FINDING-13: No test coverage for hook `main()` functions or end-to-end event flow

**Files:** `tests/test_hooks.py`
**Severity:** MEDIUM
**Description:**
The test file tests individual functions (`check_merge`, `check_push`, `check_commit_allowed`, etc.) in isolation with test doubles (`_state_override`, `_review_decision`). No tests exercise the `main()` entry points that:

1. Parse JSON from stdin
2. Dispatch to the correct check function
3. Print output and set exit codes

This means the following integration paths are untested:

- `commit_gate.main()`: The interaction between `_matches_check_command()` and `mark_verified()` in the PreToolUse flow (where mark_verified runs before the command executes).
- `review_gate.main()`: The `"gh" in command and "pr" in command and "merge" in command` guard (line 194) which uses substring checks rather than the regex in `check_merge`, creating a potential mismatch.
- `verify_agent_output.main()`: The `_is_implementer_output` filter followed by `run_verification` followed by `update_tracking_verification` pipeline.
- `session_context.main()`: The `_get_config_paths()` to extraction function pipeline.

The substring guard in `review_gate.main()` (line 194) is particularly concerning: `if "gh" in command and "pr" in command and "merge" in command` would match `echo "gh pr merge" > log.txt`, but `check_merge` would return "allowed" since it doesn't match the `gh\s+pr\s+merge` regex pattern. The two layers of filtering use different matching logic.

**Evidence:**
```python
# review_gate.py line 194 — substring matching
if "gh" in command and "pr" in command and "merge" in command:
    result = check_merge(command, base=base)
    # ...

# review_gate.py line 88 — regex matching inside check_merge
m = re.search(r'gh\s+pr\s+merge\s+(\d+)', command)
```

No test calls `main()` with simulated stdin JSON.

---

### FINDING-14: `_find_project_root()` falls back to CWD without sprint-config, making hooks silently inert

**Files:** `.claude-plugin/hooks/_common.py`, all hooks
**Severity:** LOW
**Description:**
When `_find_project_root()` can't find `sprint-config/project.toml` anywhere in the directory tree, it returns `Path.cwd()` (line 32). All hooks then attempt to read `sprint-config/project.toml` under this fallback path, fail, and silently degrade to defaults. This is correct behavior (hooks shouldn't crash in non-giles projects), but it means there's no diagnostic output when a giles-configured project fails to be detected due to an unexpected CWD.

The `CLAUDE_PROJECT_DIR` environment variable check (line 19) provides a more reliable mechanism, but only if Claude Code sets this variable. If it doesn't, the hook relies entirely on CWD-relative directory walking.

**Evidence:**
```python
# _common.py lines 31-32
# 3. Fall back to CWD
return Path.cwd()
```

---

## Summary

| Severity | Count | IDs |
|----------|-------|-----|
| HIGH | 3 | FINDING-1, FINDING-2, FINDING-3 |
| MEDIUM | 3 | FINDING-4, FINDING-5, FINDING-6 |
| LOW | 8 | FINDING-7, FINDING-8, FINDING-9, FINDING-10, FINDING-11, FINDING-12, FINDING-13, FINDING-14 |

Wait, FINDING-13 is MEDIUM. Corrected:

| Severity | Count | IDs |
|----------|-------|-----|
| HIGH | 3 | FINDING-1, FINDING-2, FINDING-3 |
| MEDIUM | 4 | FINDING-4, FINDING-5, FINDING-6, FINDING-13 |
| LOW | 7 | FINDING-7, FINDING-8, FINDING-9, FINDING-10, FINDING-11, FINDING-12, FINDING-14 |

### Critical path

**FINDING-1** is the most impactful: the commit gate records verification *before* the test command executes, so failed tests still count as "verified." This completely undermines the gate's purpose. Fixing this requires either a PostToolUse hook to check the exit code, or moving verification recording to a different trigger.

**FINDING-2** silently disables session context injection whenever CWD is not the project root, which can happen in worktrees or when Claude Code runs hooks from a subdirectory.

**FINDING-3** means the two verification systems (commit_gate and verify_agent_output) operate in complete isolation. The SubagentStop hook runs the full test suite but the commit gate doesn't know about it.

### Prior findings status

From the prior audit, the following have been fixed in current code:
- H-004 (base_branch section tracking) -- fixed, `_get_base_branch` now tracks sections
- H-006 (update_tracking_verification never called) -- fixed, main() now calls it
- H-008 (multi-line arrays) -- fixed, `_read_toml_key` now accumulates multi-line arrays
- H-013 (bare `gh pr merge`) -- fixed, now returns "blocked" for no-PR-number case
- H-014 (non-implementer agents) -- fixed, `_is_implementer_output` filter added
- H-017 (loose sprint dir matching) -- fixed, now uses `^sprint-\d+$` regex
