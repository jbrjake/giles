# Pass 34: Fix Audit of b03ccbe

Adversarial review of every source-file change in commit b03ccbe
("convergence sweep -- review_gate bypass, exception narrowing, data corruption fixes").

---

## .claude-plugin/hooks/review_gate.py (BH33-001)

**Change:** Added `--delete`, `-d`, `--mirror` to the boolean-flag tuple in `_check_push_single`, plus an unconditional block on `--mirror` after the parse loop.

### Verdict: BUG -- `--all` not blocked, same gap as `--mirror`

The fix correctly identifies `--mirror` as dangerous and unconditionally blocks it.
But `--all` (already present in the boolean-flag tuple before this commit) has the
same class of problem: `git push --all origin` pushes **every local branch** to the
remote, including `main`. With `--all`:

- `--all` is a boolean flag -> `i += 1`
- `origin` -> `positional[0]`
- No `positional[1:]` to check -> returns `"allowed"`

This is a **pre-existing gap**, not introduced by this commit. But the commit's
`--mirror` block establishes a pattern (check destructive flags after parsing)
that should have been applied to `--all` and `--tags` too. Noting as a
newly-visible inconsistency created by the fix's own pattern.

### Verdict: CLEAN on `-d` / `--delete` handling

`git push -d origin main` -> `-d` is boolean (i+=1), `origin` -> positional[0],
`main` -> positional[1], `target == base` -> blocked. Correct.

`git push origin --delete main` -> same analysis (--delete boolean, then positional
parsing catches `main`). Correct.

### Verdict: CLEAN on `--mirror` handling

The `--mirror` block at line 155 checks `"--mirror" in parts` (the raw split),
which is redundant with the boolean-flag parsing but harmless. An attacker can't
sneak `--mirror` past the raw string check.

### Minor: `-d` collision with other git subcommands

In `git push`, `-d` is indeed `--delete` (boolean, no value). No collision.
The code only runs when `parts[1] == "push"`, so `-d` meaning something else
in other git subcommands is irrelevant.

**Summary: CLEAN for the commit itself. Pre-existing gap on `--all` exposed by new pattern.**

---

## skills/sprint-monitor/scripts/check_status.py (BH33-002)

**Change:** Narrowed `except Exception` to `except (OSError, subprocess.SubprocessError)`.

### Verdict: CLEAN

- `subprocess.TimeoutExpired` is already caught by a dedicated handler on line 333.
- `subprocess.SubprocessError` is the parent of `CalledProcessError` and
  `TimeoutExpired`, so it covers all subprocess errors.
- `OSError` covers command-not-found (`FileNotFoundError` is a subclass).
- `subprocess.run()` without `check=True` doesn't raise `CalledProcessError`,
  so the `SubprocessError` arm mainly covers `TimeoutExpired` if it somehow
  leaks past the earlier catch (it won't -- order is correct).
- Programming errors (`TypeError`, `ValueError`, `KeyError`) will now propagate
  up instead of being silently swallowed. This is the correct behavior.

No regressions.

---

## scripts/smoke_test.py (BH33-003)

**Change:** `command.replace("|", "\\|")` before writing to the markdown table.

### Verdict: MINOR GAP -- `status` column not escaped

The fix escapes `command` but not the `status` parameter. The function signature
is `write_history(sprints_dir, status, command, stdout, stderr)`. Callers pass
status values like `"SMOKE PASS"` and `"SMOKE FAIL"` -- these are hardcoded
strings that never contain `|`. So this is not a real bug today.

However, the `timestamp` and `commit` variables are also written unescaped.
A commit hash won't contain `|`, and the timestamp format is fixed. So in
practice, **only `command` can contain user-controlled pipe characters**.

### Verdict: CLEAN on the actual fix

The `replace("|", "\\|")` correctly escapes pipes inside backtick-delimited
code spans. Markdown renderers will show `\|` literally inside backticks, but
the table structure is preserved, which is the goal.

Edge case: commands with existing `\|` (already escaped) would become `\\|`,
rendering as a literal backslash + pipe. This is a non-issue in practice --
shell commands don't use `\|`.

---

## scripts/validate_anchors.py (BH33-004)

**Change:** After `text.split('\n')`, pop the trailing empty element if present.

### Verdict: CLEAN

Traced through all scenarios:

1. **File ends with `\n` (normal):** split produces trailing `''`, pop removes it,
   `"\n".join(lines) + "\n"` restores exactly one trailing newline. Correct.
2. **File without trailing `\n`:** last element is content, not `''`, no pop.
   Write adds `\n`. Normalizes the file. Acceptable.
3. **Multiple trailing newlines:** e.g., `"a\n\n"` -> `['a', '', '']`, pop the
   last `''` -> `['a', '']`, write -> `"a\n\n"`. Preserves exactly what was there.
   On re-run: same split, same pop, same write. **Idempotent.**
4. **Empty file:** `""` -> `['']`, pop -> `[]`, write -> `"\n"`. Converts empty
   to single newline. Harmless for source files.

The fix correctly prevents blank-line accumulation on repeated `--fix` runs.

### Subtle consideration: line number shift

The `_find_symbol_line` and `_find_heading_line` functions enumerate with
`enumerate(text.split('\n'), 1)` -- they read the file independently and return
1-based line numbers. The `lines` array in `fix_missing_anchors` is 0-based after
the pop. The `idx = target_line - 1` conversion is correct regardless of whether
the trailing empty element was popped, because the pop only removes a phantom
element that corresponds to no real line.

---

## scripts/manage_sagas.py (BH33-005)

**Change:** Wrapped `json.loads()` in try/except `json.JSONDecodeError` for both
`update-allocation` and `update-voices` subcommands.

### Verdict: CLEAN

- Error message goes to stderr. Correct.
- Exit code 1. Correct.
- The `update-index` subcommand doesn't take JSON, so no change needed there.
- The default values (`"[]"` for allocation, `"{}"` for voices) are valid JSON,
  so the fallback path when `sys.argv[3]` is missing won't trigger the error.

No side effects on other callers. The functions `update_sprint_allocation()` and
`update_team_voices()` still receive parsed Python objects, not raw strings.

---

## scripts/team_voices.py (BH33-006)

**Change:** Skip voice entries where `quote` is empty after stripping.

### Verdict: CLEAN

The `quote` variable is built from `(match.group(2) or match.group(3) or "").strip()`,
then continuation lines are appended with `" " + continuation` only if `continuation`
is truthy. So `quote` can be empty only if:

1. The initial match groups are all None/empty, AND
2. All continuation lines are empty after stripping.

This means the blockquote was `> **Name:**` with no text, or `> **Name:** ""`.
Skipping these is correct -- they carry no information and would create entries
with empty `quote` fields that downstream consumers would need to guard against.

The `if quote:` check is placed after the continuation-line loop, so multi-line
blockquotes where only continuation lines have content are still captured.
Wait -- actually, if the initial match has empty groups, `quote = ""`, then
a continuation line with content would make `quote = " content"` which is truthy
after the strip in the match but the outer `quote` is built by concatenation:
`quote += " " + continuation` = `" content"`. This is truthy, so it would still
be included. However, the leading space is a minor cosmetic issue (pre-existing).

---

## Summary

| File | Fix ID | Verdict | Notes |
|------|--------|---------|-------|
| review_gate.py | BH33-001 | **CLEAN** (commit) / **PRE-EXISTING GAP** | `--all` not blocked; same class as `--mirror` |
| check_status.py | BH33-002 | **CLEAN** | Exception narrowing is correct |
| smoke_test.py | BH33-003 | **CLEAN** | Only `command` needs escaping; other fields are controlled |
| validate_anchors.py | BH33-004 | **CLEAN** | Idempotent across all file-ending scenarios |
| manage_sagas.py | BH33-005 | **CLEAN** | Straightforward error handling |
| team_voices.py | BH33-006 | **CLEAN** | Empty-quote skip is correct |

### New issues to track

| ID | Severity | File | Description |
|----|----------|------|-------------|
| BH34-001 | MEDIUM | review_gate.py | `git push --all origin` bypasses base-branch protection (pre-existing, but now inconsistent with `--mirror` block pattern) |
| BH34-002 | LOW | smoke_test.py | Leading space in continuation-only voice quotes (pre-existing cosmetic, in team_voices.py) |

### Conclusion

All six fixes in b03ccbe are correct and do not introduce new bugs. The commit
is safe. One pre-existing gap (`--all` not blocked) is now more visible because
the `--mirror` block establishes a pattern that `--all` should follow.
