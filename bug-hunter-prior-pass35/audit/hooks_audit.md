# Bug Hunter Pass 35 — Hooks Subsystem Audit

**Date:** 2026-03-21
**Scope:** `.claude-plugin/hooks/` (4 files, highest-churn area)
**Test file:** `tests/test_hooks.py`

---

## BH35-001: review_gate push parser bypassed by `+` refspec prefix (HIGH)

**File:** `.claude-plugin/hooks/review_gate.py:166-169`

The `_check_push_single` function extracts the target branch from refspecs like `HEAD:main`. When no colon is present, the entire refspec is compared to the base branch. But git allows a `+` prefix on refspecs to force-push:

```
git push origin +main
```

The code does `target = refspec` when there's no `:`, giving `"+main"`. Since `"+main" != "main"`, the push is **allowed** instead of blocked.

**How to trigger:** `check_push("git push origin +main", base="main")` returns `"allowed"`.

**Why it matters:** Force-pushing to the base branch is more destructive than a regular push. The hook specifically blocks `--force` as a flag but misses the equivalent `+` refspec syntax.

**Fix:** Strip leading `+` from refspecs before comparison:
```python
target = target.lstrip("+")
```

---

## BH35-002: review_gate push parser bypassed by full ref path (HIGH)

**File:** `.claude-plugin/hooks/review_gate.py:166-169`

The parser compares refspec targets to the bare branch name (e.g., `"main"`), but git also accepts full ref paths:

```
git push origin refs/heads/main
```

Here `target = "refs/heads/main"`, which doesn't equal `"main"`, so the push is allowed.

**How to trigger:** `check_push("git push origin refs/heads/main", base="main")` returns `"allowed"`.

**Why it matters:** Any user or agent that knows to use the full ref path can bypass the branch protection.

**Fix:** Also check if target ends with `/{base}`:
```python
if target == base or target == f"refs/heads/{base}":
    return "blocked"
```

---

## BH35-003: review_gate push parser bypassed by `--repo` flag (MEDIUM)

**File:** `.claude-plugin/hooks/review_gate.py:138-147`

Unknown flags that lack `=` and aren't in the known-valueless set are assumed to take a separate value argument (`i += 2`). This is correct for flags like `--repo VALUE`, but it means the flag consumes the next positional argument:

```
git push --repo origin main
```

The parser treats `--repo` as a flag-with-value, consuming `origin` as its value. This leaves `positional = ["main"]`. Since `len(positional) < 2`, the refspec check at line 165 is skipped entirely, and the function returns `"allowed"`.

Semantically, `git push --repo origin main` pushes the `main` refspec to the remote named by `--repo`. The push to main should be blocked.

**How to trigger:** `check_push("git push --repo origin main", base="main")` returns `"allowed"`.

**Why it matters:** The `--repo` flag is a valid git push option. Any flag-with-value placed before the remote causes the base branch refspec to be treated as the remote name instead.

**Fix:** After parsing flags and positional args, also check if any positional arg equals the base branch, regardless of position. Or specifically handle `--repo` by recognizing it doesn't change the positional semantics.

---

## BH35-004: review_gate pipe operator not split in compound commands (MEDIUM)

**File:** `.claude-plugin/hooks/review_gate.py:117`

The `check_push` function splits compound commands on `&&`, `||`, and `;` — but not on `|` (single pipe). The docstring at line 113 claims pipe handling, but the regex `r'\s*(?:&&|\|\||;)\s*'` only matches `||`, not `|`.

```
echo ok | git push origin main
```

The whole string goes to `_check_push_single`, where `parts[0]` is `"echo"`, not `"git"`, so it returns `"allowed"`.

**How to trigger:** `check_push("echo ok | git push origin main", base="main")` returns `"allowed"`.

**Why it matters:** While pipe is an unusual way to structure a git push, the docstring claims support for it, and the gap is exploitable.

**Fix:** Add `|` to the split pattern: `r'\s*(?:&&|\|\||\||;)\s*'` — but be careful to match `||` before `|` (regex alternation is already ordered).

Actually, the current `\|\|` matches `||` by trying it first. Adding `\|` after would let `|` match single pipes: `r'\s*(?:&&|\|\||;|\|)\s*'`.

---

## BH35-005: review_gate `_get_base_branch` ignores single-quoted TOML strings (MEDIUM)

**File:** `.claude-plugin/hooks/review_gate.py:42`

The regex `r'\s*base_branch\s*=\s*"([^"]+)"'` only matches double-quoted strings. A project.toml with:

```toml
base_branch = 'develop'
```

…would silently fall through to the default `"main"`. All push protection would target `main` instead of the actual base branch `develop`, meaning pushes to `develop` would be allowed.

**How to trigger:** Set `base_branch = 'develop'` in project.toml (single-quoted, valid TOML). Pushes to `develop` pass through unblocked while pushes to `main` are blocked unnecessarily.

**Why it matters:** `verify_agent_output._read_toml_key` and `session_context._read_toml_string` both handle single-quoted strings. This parser is the only one that doesn't, creating a silent misconfiguration.

**Fix:** Add a single-quoted match:
```python
m = re.match(r"\s*base_branch\s*=\s*'([^']+)'", line)
if m:
    return m.group(1)
```

---

## BH35-006: Hook TOML parsers use `splitlines()` instead of `split('\n')` (MEDIUM)

**File:** `verify_agent_output.py:112`, `review_gate.py:36`, `review_gate.py:193`, `session_context.py:27`

The main TOML parser in `validate_config.py` specifically uses `text.split('\n')` instead of `splitlines()` to avoid BH20-001: Python's `splitlines()` treats U+2028 (Line Separator) and U+2029 (Paragraph Separator) as line breaks, which corrupts TOML strings containing these unicode characters.

All four hook files use `splitlines()` for their inline TOML parsing. If a TOML value contains U+2028 or U+2029 (e.g., in a path or string value), the hook parser would split the value across multiple lines, causing incorrect parsing.

**How to trigger:** Set a TOML value containing U+2028: `smoke_command = "echo \u2028done"`. The hook parser splits this into two lines mid-value.

**Why it matters:** The same bug class was already identified and fixed in the main parser (BH20-001). The fix wasn't propagated to the hook parsers.

**Fix:** Replace all `text.splitlines()` with `text.split('\n')` in TOML-parsing code paths within hooks.

---

## BH35-007: session_context `_read_toml_string` unescape converts `\n` to literal `n` (LOW)

**File:** `.claude-plugin/hooks/session_context.py:38`

The unescape logic `re.sub(r'\\(.)', lambda x: x.group(1), m.group(1))` treats all `\X` escape sequences as just the character `X`. This means:

- `\n` becomes `n` (literal character), not a newline
- `\t` becomes `t`, not a tab
- `\uXXXX` becomes `uXXXX`, not the unicode character

This differs from both `verify_agent_output._unescape_basic_string` (which correctly maps `\n` -> newline, `\t` -> tab) and `validate_config._unescape_toml_string` (which additionally handles `\b`, `\f`, `\uXXXX`, `\UXXXXXXXX`).

**How to trigger:** Set `sprints_dir = "path\nwith\nnewlines"` in project.toml. The session_context parser would produce `"pathnwithnewlines"` while the other parsers would produce the string with actual newlines.

**Why it matters:** In practice this only affects `sprints_dir` and `team_dir` values, which rarely contain escape sequences. But it represents a spec-compliance divergence that could cause subtle path resolution bugs.

**Fix:** Replace the regex substitution with proper escape handling matching `_unescape_basic_string`.

---

## BH35-008: commit_gate `_matches_check_command` has no word boundaries on config commands (MEDIUM)

**File:** `.claude-plugin/hooks/commit_gate.py:179`

The config-based check command matching uses `re.search(re.escape(cfg_cmd.split()[0]), command)` without word boundary assertions. If the configured check command starts with `"python"`, then any command containing the substring `"python"` would match — including `echo "python is great"` or `grep python requirements.txt`.

A false positive here causes `mark_verified()` to run, which records the working tree hash. This could let an untested commit through if the agent runs an innocuous command containing a check-command substring right before committing.

**How to trigger:** Configure `check_commands = ["python -m pytest"]`. Then the agent runs `echo python` (exit 0). The PostToolUse hook matches `python` in the command and marks the tree as verified. The next commit is allowed without tests actually running.

**Why it matters:** The hardcoded patterns at lines 183-191 correctly use `\b` boundaries. The config-based path at line 179 does not, making it more permissive than intended.

**Fix:** Add word boundaries:
```python
if cfg_cmd and re.search(r'\b' + re.escape(cfg_cmd.split()[0]) + r'\b', command):
```

---

## BH35-009: verify_agent_output multi-line array accumulation doesn't strip inline comments from continuation lines (LOW)

**File:** `.claude-plugin/hooks/verify_agent_output.py:129-131`

When accumulating a multi-line TOML array, the code appends raw continuation lines without stripping inline comments:

```python
while not _has_unquoted_bracket(array_text) and i + 1 < len(lines):
    i += 1
    array_text += " " + lines[i].strip()
```

Compare with `validate_config.py` line 163-164 which strips comments on each continuation line:
```python
stripped_line = _strip_inline_comment(line)
multiline_buf += " " + stripped_line
```

If a continuation line's inline comment contains a quoted string, the regex at line 134 would match it as an array item:

```toml
check_commands = [
    "pytest",  # the "main" test runner
    "ruff check",
]
```

The accumulated text includes `# the "main" test runner`, and the regex `re.findall(r'"((?:[^"\\]|\\.)*)"|...')` matches `"main"` as an additional array item, producing `["pytest", "main", "ruff check"]` instead of `["pytest", "ruff check"]`.

**How to trigger:** Add an inline comment containing a quoted string on a continuation line of a multi-line array.

**Why it matters:** Phantom array items from comments would cause unexpected commands to run during verification, or cause check_command matching to produce false positives.

**Fix:** Strip inline comments from each continuation line before accumulating.

---

## BH35-010: `_is_implementer_output` "committed" pattern lacks word boundary (LOW)

**File:** `.claude-plugin/hooks/verify_agent_output.py:306`

The regex pattern `committed` (line 306 in the verbose regex) has no `\b` word boundary, unlike all other patterns (`\bpushed\b`, `\bmerged\b`, etc.). This means it matches as a substring within words like:

- `"uncommitted"` — a reviewer saying "there are uncommitted changes"
- `"recommitted"` — less common but valid
- `"committee"` — `committed` is a substring of `committee`

**How to trigger:** A reviewer agent output containing "uncommitted changes should be addressed" would be misidentified as implementer output, triggering verification unnecessarily.

**Why it matters:** False-positive implementer detection causes unnecessary test runs (wasted time, not a safety issue). But in combination with BH35-008, a false positive could mark the tree as verified when it shouldn't be.

**Fix:** Add word boundary: `\bcommitted\b`.

---

## BH35-011: `session_context._read_toml_string` has no test coverage (LOW)

**File:** `tests/test_hooks.py` — search for `_read_toml_string` returns 0 results.

The `_read_toml_string` function in `session_context.py` is untested. It has different behavior from the tested `_read_toml_key` in `verify_agent_output.py`:
- Different escape handling (BH35-007)
- No support for arrays, unquoted values, or inline comments
- Uses `splitlines()` (BH35-006)

**Why it matters:** Without tests, the divergences documented in BH35-006 and BH35-007 went unnoticed. Dedicated tests would catch regressions.

---

## BH35-012: `format_context` has no truncation despite "<50 lines target" claim (LOW)

**File:** `.claude-plugin/hooks/session_context.py:145`

The docstring says `"<50 lines target"` but the function has no truncation logic. With enough action items, DoD additions, or risks, the output can grow unboundedly. The test at line 519-526 uses 40 total items and asserts `< 60` lines, but nothing prevents 100+ items in production.

**How to trigger:** A project with 50+ retro action items or open risks would produce output well over 50 lines.

**Why it matters:** Excessively long hook output wastes context window tokens in the Claude session. The stated 50-line target is not enforced.

---

## Summary

| ID | File | Severity | Category |
|----|------|----------|----------|
| BH35-001 | review_gate.py:166 | HIGH | Push bypass via `+` refspec |
| BH35-002 | review_gate.py:166 | HIGH | Push bypass via `refs/heads/` path |
| BH35-003 | review_gate.py:138 | MEDIUM | Push bypass via `--repo` flag eating positional |
| BH35-004 | review_gate.py:117 | MEDIUM | Pipe `\|` not split in compound commands |
| BH35-005 | review_gate.py:42 | MEDIUM | Single-quoted `base_branch` ignored |
| BH35-006 | all hooks | MEDIUM | `splitlines()` vs `split('\n')` — BH20-001 not propagated |
| BH35-007 | session_context.py:38 | LOW | `\n`/`\t` unescape divergence |
| BH35-008 | commit_gate.py:179 | MEDIUM | Config check command match lacks `\b` boundary |
| BH35-009 | verify_agent_output.py:129 | LOW | Multi-line array doesn't strip comments from continuations |
| BH35-010 | verify_agent_output.py:306 | LOW | `committed` pattern matches `uncommitted`/`committee` |
| BH35-011 | test_hooks.py | LOW | `_read_toml_string` untested |
| BH35-012 | session_context.py:145 | LOW | `format_context` has no truncation logic |

**HIGH:** 2 | **MEDIUM:** 4 | **LOW:** 4 | **Coverage gap:** 2
