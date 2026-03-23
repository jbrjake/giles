# Hooks Subsystem Audit

Audited files:
- `hooks/_common.py`
- `hooks/commit_gate.py`
- `hooks/review_gate.py`
- `hooks/session_context.py`
- `hooks/verify_agent_output.py`
- `hooks/hooks.json`

---

## Finding H3-001: commit_gate --dry-run bypass in compound commands

- **Severity:** HIGH
- **Category:** bug/security
- **Location:** `hooks/commit_gate.py:143`

The `--dry-run` allowlist check searches the entire command string with `re.search`, without splitting on shell operators first. A compound command can smuggle `--dry-run` from a different subcommand to bypass the commit gate.

```python
# BH31-001: Allow --dry-run through -- it validates without committing
if re.search(r'--dry-run\b', command):
    return "allowed"
```

Three bypass vectors:

```
git commit --dry-run && git commit -m "real"   # dry-run on first, real commit on second
git stash --dry-run; git commit -m test        # dry-run on stash leaks to commit check
echo --dry-run | git commit -m test            # dry-run in echo leaks
```

In contrast, `review_gate.check_push` correctly splits compound commands on `&&`, `;`, `|` before checking each subcommand. `commit_gate.check_commit_allowed` does not split at all.

Fix: split command on shell operators before checking, matching review_gate's approach. Or check that `--dry-run` appears after `git commit` in the same subcommand.

---

## Finding H3-002: _log_blocked failure prevents exit_block from executing

- **Severity:** HIGH
- **Category:** bug/security
- **Location:** `hooks/review_gate.py:248-249, 259-260`

In `review_gate.main()`, `_log_blocked()` is called before `exit_block()`. The `_log_blocked` function opens a file for writing (line 221) with no try/except around the write. If the write fails (permission error, read-only filesystem, disk full), the exception propagates and `exit_block()` never runs. The hook crashes with non-zero exit and no JSON output, which Claude Code treats as a hook error rather than a block decision.

```python
# review_gate.py lines 248-249
_log_blocked(command, reason)    # <-- can raise PermissionError, OSError
exit_block(reason)               # <-- never reached if above raises
```

Same pattern on lines 259-260 for the push check.

Fix: wrap `_log_blocked` calls in try/except, or swap the call order (call `exit_block` first, but since it calls `sys.exit(0)`, the log would never write -- so wrapping is the correct fix).

---

## Finding H3-003: review_gate push check does not handle bash -c or eval wrappers

- **Severity:** MEDIUM
- **Category:** bug/security
- **Location:** `hooks/review_gate.py:127-130`

`_check_push_single` requires `parts[0] == "git"` and `parts[1] == "push"`. Commands wrapped in `bash -c`, `eval`, `sh -c`, or subshell `$(...)` are not detected because the first token is `bash`/`eval`/`sh`, not `git`.

```
bash -c "git push origin main"   -> parts[0]='bash', not 'git' -> allowed
eval "git push origin main"      -> parts[0]='eval', not 'git' -> allowed
sh -c "git push origin main"     -> parts[0]='sh', not 'git'   -> allowed
```

The compound-command splitting on `&&`/`;`/`|` does not help here because there's no shell operator -- the push is inside a quoted argument.

Similarly affects `check_merge` for the same wrappers, though the pre-filter `'gh' in command` would still match and the regex `r'gh\s+pr\s+merge\s+(\d+)'` would find the pattern inside the quoted string, so merge detection is accidentally resilient to this.

Fix: also check for push/merge patterns inside quoted arguments of `bash -c`, `sh -c`, and `eval`.

---

## Finding H3-004: No top-level exception handler in any hook main()

- **Severity:** MEDIUM
- **Category:** bug/error-handling
- **Location:** All hooks: `commit_gate.py:224`, `review_gate.py:229`, `session_context.py:182`, `verify_agent_output.py:345`

None of the hook `main()` functions have a top-level try/except. An unhandled exception causes the hook to exit non-zero without printing JSON. Under the JSON output protocol, the absence of valid JSON on stdout means Claude Code cannot determine the hook's decision.

For security-critical hooks (commit_gate, review_gate), this means a crash degrades to "allow" rather than "block" -- the opposite of fail-closed behavior.

Fix: wrap each `main()` in `try/except Exception` that calls `exit_ok()` (for non-security hooks) or `exit_block("internal hook error")` (for security hooks) as a fallback.

---

## Finding H3-005: post_main crashes if tool_output is not a dict

- **Severity:** MEDIUM
- **Category:** bug/error-handling
- **Location:** `hooks/commit_gate.py:250-253`

`post_main()` chains `.get()` calls on `tool_output`, but if the event payload has `tool_output` as a string (or other non-dict type), the `.get()` call raises `AttributeError`.

```python
tool_output = input_data.get("tool_output",
                input_data.get("tool_response",
                input_data.get("output", {})))
exit_code = tool_output.get("exit_code", tool_output.get("exitCode", -1))
# If tool_output is a string: AttributeError: 'str' object has no attribute 'get'
```

Fix: add `if not isinstance(tool_output, dict): tool_output = {}` before the `.get()` chain.

---

## Finding H3-006: Path traversal in verify_agent_output tracking file resolution

- **Severity:** LOW
- **Category:** bug/security
- **Location:** `hooks/verify_agent_output.py:324, 287-307`

`_TRACKING_PATH_PATTERN` uses `\S+` which matches any non-whitespace including `../`:

```python
_TRACKING_PATH_PATTERN = re.compile(r"sprint-\d+/stories/\S+\.md")
```

A subagent output containing `sprint-1/stories/../../etc/shadow.md` would match, and `_resolve_tracking_path` would resolve it via path joining. If the traversed path points to an existing file with YAML frontmatter, `update_tracking_verification` would write a `verification_agent_stop: passed/failed` line into it.

Mitigating factors:
- Target file must already exist
- Target file must contain YAML frontmatter (`---` delimiters)
- Only writes a fixed `verification_agent_stop: passed/failed` line
- Attack vector is subagent output text, which comes from Claude (not external)

Fix: validate that the resolved path stays within the sprints directory using `Path.resolve()` and checking `is_relative_to()`.

---

## Finding H3-007: Three inconsistent TOML parsers across hook files

- **Severity:** LOW
- **Category:** design/duplication
- **Location:** `hooks/review_gate.py:29-49`, `hooks/session_context.py:23-48`, `hooks/verify_agent_output.py:29-150`

Three different TOML parsing implementations exist across the hooks:

| Hook | Function | Escapes | Arrays | Inline comments | re.escape(key) |
|------|----------|---------|--------|-----------------|----------------|
| review_gate | `_get_base_branch` | No | No | No | N/A (hardcoded) |
| session_context | `_read_toml_string` | Yes (regex lambda) | No | Implicit | No |
| verify_agent_output | `_read_toml_key` | Yes (char-by-char) | Yes | Yes (`_strip_inline_comment`) | Yes |

The comment at the top of each says "lightweight, no validate_config import" -- this is an intentional design choice to avoid importing the main scripts/ module from hooks. But the three parsers handle edge cases differently (escape sequences, inline comments, `re.escape` of key names).

`commit_gate._load_config_check_commands` (line 164) imports `_read_toml_key` from `verify_agent_output`, creating a cross-hook dependency. This is the right direction -- `_read_toml_key` is the most complete parser and other hooks should reuse it.

Fix: consolidate into a single TOML reader in `_common.py` (or in `verify_agent_output` as the canonical one), imported by all hooks.

---

## Finding H3-008: commit_gate does not split compound commands (inconsistency with review_gate)

- **Severity:** LOW
- **Category:** design/consistency
- **Location:** `hooks/commit_gate.py:125-149`

`review_gate.check_push` splits compound commands on `&&`, `;`, `|`, `||` before checking each subcommand. `commit_gate.check_commit_allowed` checks the entire command string as a unit with `re.search`.

For the basic commit detection (`re.search(r'\bgit\s+commit\b', command)`), this works because `re.search` scans the entire string. But the `--dry-run` check (H3-001) and any future per-subcommand logic would need splitting.

This is partly a design concern (inconsistent approach) and partly the root cause of H3-001.

---

## Finding H3-009: format_context output is unbounded despite docstring claim

- **Severity:** LOW
- **Category:** bug/logic
- **Location:** `hooks/session_context.py:148-175`

The docstring says `"<50 lines target"` but the function applies no truncation. With a retro containing 100 action items, the output would be 103+ lines. The test (line 634 of test_hooks.py) only checks `< 60 lines` with capped input (20+10+10 items).

In practice, retros rarely have more than ~10 action items, so this is unlikely to trigger. But as a SessionStart hook, large output could bloat the context window.

Fix: cap each section (e.g., top 10 items per category) with a "... and N more" trailer.

---

## Finding H3-010: review_gate allows `git push origin` with remote-only positional

- **Severity:** LOW
- **Category:** design/false-negative
- **Location:** `hooks/review_gate.py:164-165`

When the command is `git push origin` (remote name only, no refspec), `positional = ["origin"]`. The code checks `"origin" == base` which is false (base is typically "main"), so the result is "allowed". This is correct behavior -- git will push the current branch's default refspec, which may or may not be the base branch.

However, if the current branch IS the base branch, this command would push directly to base, and the hook would not catch it. The bare `git push` (no arguments at all) returns "warn", but `git push origin` (remote only) returns "allowed". The inconsistency means the warning only fires for `git push` but not `git push origin`.

Fix: return "warn" when only a remote name is provided (one positional, no refspec).

---

## Non-findings (confirmed correct)

1. **hooks.json paths**: All commands use `${CLAUDE_PLUGIN_ROOT}/hooks/` which resolves to the plugin root's `hooks/` directory. File locations match.

2. **JSON protocol compliance**: All `exit_ok`, `exit_warn`, `exit_block` functions print valid JSON and exit 0. Protocol is correctly implemented.

3. **read_event graceful degradation**: Catches `json.JSONDecodeError`, `EOFError`, `ValueError` (which covers `UnicodeDecodeError`). Returns empty dict on failure.

4. **exit_ok PreToolUse hookSpecificOutput**: Correctly includes `permissionDecision: "allow"` only for PreToolUse hooks, preventing phantom "hook error" labels.

5. **_find_project_root resolution chain**: Environment variable -> walk upward -> CWD fallback. Sensible and defensive.

6. **Working tree hash comparison**: Uses `git diff HEAD` with fallback to `git diff --cached` for empty repos. Hash comparison is collision-resistant (SHA-256, 16 hex chars).

7. **Compound command splitting in review_gate**: Correctly handles `&&`, `||`, `|`, `;` operators. Tested extensively.

8. **Force-push detection**: `+refspec`, `refs/heads/`, `--mirror`, `--all`, `--force`, `--delete` are all caught.

---

**Verdict: DONE_WITH_CONCERNS**

Two high-severity findings (H3-001, H3-002) affect the security properties of the hooks. H3-001 allows bypassing the commit gate via compound commands with `--dry-run`. H3-002 can turn a merge/push block into an allow if the audit log write fails. Both have straightforward fixes.
