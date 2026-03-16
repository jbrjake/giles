# Adversarial Audit: `scripts/validate_config.py`

**Target:** `/Users/jonr/Documents/non-nitro-repos/giles/scripts/validate_config.py`
**Coverage:** 93% (467 statements, ~33 uncovered lines)
**Date:** 2026-03-16

---

## Summary

14 findings total. 2 CRITICAL, 4 HIGH, 5 MEDIUM, 3 LOW.

The module is well-defended against the most common bugs thanks to 15 prior
bug-hunter passes and property-based testing via hypothesis. The remaining
attack surface is concentrated in the TOML parser's handling of TOML features
it explicitly doesn't support, validation gaps when `_config` is an empty dict,
and a class of silent-corruption issues in `_parse_value` fallback behavior.

---

## Findings

### 1. CRITICAL: `_parse_value` silently accepts unquoted strings containing `=`, `[`, and other TOML metacharacters

**Lines:** 307-314
**Severity:** CRITICAL

When `_parse_value` fails to match a string, integer, boolean, or array, it
falls back to returning the raw text as a string. While this is documented as
"intentional leniency," it means malformed TOML silently produces wrong
results instead of raising.

```toml
name = project = "real name"
```

This parses as `{"name": 'project = "real name"'}` — the entire RHS becomes
the string value. No error. The user thinks they have `name = "project"` and
a separate key `= "real name"` (which is itself invalid). The warning on
line 311-313 only fires for values with spaces and no `#`, so single-word
unquoted values like `name = true_ish` silently become the string `"true_ish"`
rather than erroring.

**Impact:** A typo in project.toml could pass validation silently and propagate
corrupt config values into GitHub issues, CI workflows, and tracking files.

**Recommendation:** At minimum, reject unquoted values that contain `=`, `[`,
`]`, or `{` — these are always TOML syntax errors. Consider making the
warning a hard error for values that look like they should be quoted.

---

### 2. CRITICAL: TOML parser silently corrupts strings with embedded unescaped quotes

**Lines:** 282-283
**Severity:** CRITICAL

`_parse_value` checks `raw.startswith('"') and raw.endswith('"')` to detect
double-quoted strings. If a value has a quote that isn't properly escaped:

```toml
name = "She said "hello""
```

After `_strip_inline_comment`, `raw` is `"She said "hello""`. The check
`startswith('"') and endswith('"')` passes, then `raw[1:-1]` yields
`She said "hello"` — which looks correct but only by coincidence. The real
problem is the intermediate parsing state: `_strip_inline_comment` doesn't
know where the string ends (it sees the second `"` as closing the string,
then `hello` becomes a comment-free zone, then another string opens).

For the slightly different case:

```toml
name = "She said "hello" world"
```

`_strip_inline_comment` will close the string at the second `"`, see `hello`
outside quotes, and if there's a `#` after it, strip the comment incorrectly.

**Impact:** Config values with embedded unescaped quotes silently produce
garbage. This is a spec violation (TOML requires `\"` for embedded quotes)
but the parser doesn't detect or report it.

**Recommendation:** After stripping the outer quotes, scan for unescaped `"`
characters. If found, raise `ValueError` with guidance to use `\"`.

---

### 3. HIGH: `load_config` swallows TOML parse exceptions, then `validate_project` may not re-detect the error

**Lines:** 612-615
**Severity:** HIGH

In `load_config`, lines 612-615:

```python
try:
    config = parse_simple_toml(toml_path.read_text(encoding="utf-8"))
except Exception:
    pass  # validate_project will report the parse error
```

The comment says "validate_project will report the parse error" but when
`_config=config` is passed (line 617), `validate_project` receives `config`
which is still `{}` (the initial value from line 610). The code at line 439
checks `if _config is None`, which is False (it's `{}`), so the TOML file
is never re-read. The section/key checks then run on the empty dict and
report "missing required section" errors — not the actual parse error.

The user sees "project.toml missing required section: [project]" instead of
"Failed to parse project.toml: Unterminated multiline array for key 'x'".
The real error is swallowed.

**Impact:** Parse errors in project.toml produce misleading validation
messages. Users chase missing-section ghosts instead of fixing the actual
syntax error.

**Recommendation:** When `parse_simple_toml` throws in `load_config`, either
re-raise immediately or pass the exception to `validate_project` so it can
include the real error message.

---

### 4. HIGH: No multi-line basic string support (`"""..."""`)

**Lines:** 117-190
**Severity:** HIGH

TOML supports multi-line basic strings delimited by `"""`. The parser has no
handling for these. If someone writes:

```toml
description = """
This is a multi-line
description.
"""
```

The parser sees `description = """` — the `_parse_value` call gets `"""`,
which starts and ends with `"`, so `raw[1:-1]` gives `"` — a single quote
character. The remaining lines are parsed as keys/values or silently dropped.

**Impact:** Any project.toml that uses TOML multi-line strings will silently
corrupt. The parser already documents it doesn't support this, but there is
no detection or error — it just produces wrong values.

**Recommendation:** Detect `"""` at the start of a value and raise
`ValueError("Multi-line strings (\"\"\"...\"\"\") are not supported by this parser")`.

---

### 5. HIGH: Section header regex rejects valid TOML section names with leading digits after dots

**Lines:** 158
**Severity:** HIGH

The regex for section headers:

```python
re.match(r"^\[([a-zA-Z0-9_][a-zA-Z0-9_.-]*)\]\s*(?:#.*)?$", line)
```

This allows the *first* character of the entire section path to be a digit
(e.g., `[1project]` matches), which is actually invalid in bare-key TOML.
Meanwhile, it accepts dotted sections like `[a.b]`, but the *first character*
check applies to the whole string `a.b`, not to each segment individually.
So `[a.1b]` passes because `a.1b` matches `[a-zA-Z0-9_][a-zA-Z0-9_.-]*`.

However, the regex does NOT allow section names starting with a hyphen:
`[-my-section]` fails because `-` is not in the first character class
`[a-zA-Z0-9_]`. This is correct per TOML spec, but confusing since the
key regex on line 170 allows hyphens in keys.

This is more of a spec-correctness note than a practical bug for this
project, since all sections used are `[project]`, `[paths]`, `[ci]`,
`[conventions]`, `[release]`.

**Impact:** Low practical impact currently, but a landmine for future TOML
section names. The regex also allows `[1]` as a section name, which is
invalid TOML but would silently pass.

---

### 6. HIGH: `validate_project` with `_config={}` skips file-existence checks for team/persona files

**Lines:** 447, 473-494
**Severity:** HIGH

When `_config={}` is passed (empty dict, which happens when `load_config`
catches a parse error), line 447 evaluates:

```python
if toml_path.is_file() or _config is not None:
```

Since `_config` is `{}` (not None), this is True. The section/key checks
run on the empty dict and correctly report missing sections.

However, team persona validation (lines 473-494) depends on parsing the
team INDEX.md. The `team_dir` path is derived from config at lines 649-651
in `get_team_personas`, defaulting to `"sprint-config/team"`. This part
works correctly because it reads the filesystem directly.

The real issue: if someone calls `validate_project("sprint-config", _config={})`
directly (not through `load_config`), the TOML file exists on disk but the
empty `_config` means all TOML-based validation reports "missing key" errors
that are misleading. The function signature allows this but the semantics
are confusing — `_config={}` means "I parsed it and it was empty" while
`_config=None` means "please parse it yourself."

**Impact:** Internal API confusion. Not exploitable externally but could
cause bugs in future code that calls `validate_project` with `_config`.

---

### 7. MEDIUM: No shell injection — but `gh()` leaks argument values in error messages

**Lines:** 56-68
**Severity:** MEDIUM

The `gh()` function correctly uses `subprocess.run(["gh", *args])` with a
list (no `shell=True`), which prevents shell injection entirely. There are
no uses of `shell=True` anywhere in the codebase. This is good.

However, line 67:

```python
raise RuntimeError(f"gh {' '.join(args)}: {r.stderr.strip()}")
```

This leaks the full argument list into the error message. If `args` contains
a token or sensitive value (unlikely in this codebase, since `gh` uses its
own auth), it would appear in error logs. The same applies to line 64.

**Impact:** Very low. GitHub CLI handles its own authentication via
`gh auth login`, not via arguments. But worth noting for defense-in-depth.

**Recommendation:** No action needed. The current approach is standard.

---

### 8. MEDIUM: `_parse_team_index` does not validate separator row position

**Lines:** 525-561
**Severity:** MEDIUM

`_parse_team_index` treats the first `|`-delimited row as headers and skips
rows matching `^[-:]+$` (separator rows). But it doesn't require the
separator to be the second row. If a file has:

```
| Name | Role | File |
| Alice | Developer | alice.md |
| --- | --- | --- |
| Bob | Architect | bob.md |
```

Alice's row is treated as the header (since it's the first `|` row after
the current empty `headers`), the actual header row is silently consumed as
data with incorrect column mapping. The separator row is correctly skipped.
Bob's row is then parsed with Alice's row as headers.

This is unlikely in practice but the parser would silently produce wrong
data rather than detecting the malformed table.

**Impact:** Low practical impact. All tables are generated by `sprint_init.py`
which produces correctly structured tables.

---

### 9. MEDIUM: `kanban_from_labels` returns first match, not most specific

**Lines:** 834-846
**Severity:** MEDIUM

`kanban_from_labels` iterates labels and returns the first `kanban:*` label
found. If an issue accidentally has two kanban labels (e.g., `kanban:dev`
and `kanban:review`), the function returns whichever appears first in the
labels list, which depends on GitHub's label ordering (typically alphabetical
by name).

This means `kanban:dev` would always win over `kanban:review` due to
alphabetical ordering, which is the opposite of what you'd want (the more
advanced state should win).

**Impact:** Could cause a story to appear stuck in an earlier state when
it actually has multiple kanban labels. The kanban protocol reference doc
says issues should have exactly one kanban label, but nothing enforces this.

**Recommendation:** Either warn when multiple kanban labels exist, or pick
the most advanced state (based on KANBAN_STATES ordering).

---

### 10. MEDIUM: `detect_sprint` regex is fragile — requires exact "Current Sprint: N" format

**Lines:** 800-809
**Severity:** MEDIUM

```python
m = re.search(r"Current Sprint:\s*(\d+)", status_file.read_text(encoding="utf-8"))
```

This requires the exact string "Current Sprint:" (case-sensitive, with that
exact capitalization and spacing). If SPRINT-STATUS.md uses a different
format like "**Current Sprint:** 3" (bold markdown), the regex still works
because `\s*` handles the space. But "current sprint: 3" (lowercase) would
fail. "Current Sprint #3" would also fail.

**Impact:** Low. The format is generated by the tooling itself
(`update_burndown.py`), so it's consistent. But if a user manually edits
SPRINT-STATUS.md, sprint detection silently fails (returns None).

---

### 11. MEDIUM: `find_milestone` calls `gh_json` with `{owner}/{repo}` template without config

**Lines:** 850-866
**Severity:** MEDIUM

```python
milestones = gh_json([
    "api", "repos/{owner}/{repo}/milestones", "--paginate",
])
```

This relies on the `gh` CLI's template expansion of `{owner}/{repo}`. This
works when `gh` has a configured repository context (i.e., you're in a git
repo with a GitHub remote). But if called from a directory without a git
remote, `gh` will fail with an unhelpful error.

The function takes only `sprint_num` — it has no access to the config dict
or `project.repo` value. Other places in the codebase that call `gh` use
the `repo` from config, but `find_milestone` doesn't.

**Impact:** `find_milestone` silently depends on `gh`'s implicit repo
detection. If the working directory changes, it breaks. This is a latent
fragility, not a current bug.

---

### 12. LOW: Uncovered lines reveal dead/defensive code paths

**Uncovered lines from coverage report:**

| Lines | Code | Analysis |
|-------|------|----------|
| 62-63 | `TimeoutExpired` handler | Defensive: real gh calls rarely timeout in tests. Covered by the timeout value being passed, but the exception path itself is never triggered. |
| 100, 102, 107 | `gh_json` paginated decode (whitespace skip, break, dict append) | The dict-append path (line 107) means paginated `gh api` returned a JSON object (not array). Only triggered by unusual API responses. |
| 241, 243 | `_unescape_toml_string` `\n` and `\t` | Escape sequences in TOML values are uncommon in project.toml. |
| 260-263 | `_unescape_toml_string` `\U` (8-digit unicode) and unknown escapes | Very rare escape sequences. |
| 442-443 | `parse_simple_toml` parse error in `validate_project` | Only triggered when project.toml exists but has syntax errors. |
| 491-492 | Persona file fallback (no `file` column) | Only triggered when INDEX.md lacks a File column. |
| 614-615 | `load_config` parse error swallowing | See finding #3 above. |
| 654, 665-666 | `get_team_personas` empty/missing paths | Defensive returns for missing team index. |
| 680, 695, 716, 726, 736, 746 | Various `get_*_dir` returns for missing dirs | All are `return []` / `return None` for optional config paths. |
| 768 | `extract_sp` non-string/non-dict label `continue` | Defensive: handles unexpected label types. |
| 790 | `get_story_map` early return None | Optional path not configured. |
| 877-880, 882 | `list_milestone_issues` error handler | RuntimeError from `gh_json` caught and logged. |
| 891 | `warn_if_at_limit` body | Only triggers when exactly 500 results returned. |
| 916 | `if __name__ == "__main__"` | CLI entry point, not exercised in unit tests. |

Most of these are defensive branches for edge cases. The concerning ones are
lines 614-615 (finding #3) and the `_unescape_toml_string` branches which
could hide bugs in escape handling since they're never tested.

**Recommendation:** Add targeted unit tests for:
- `_unescape_toml_string` with `\n`, `\t`, `\U`, and unknown escape sequences
- `list_milestone_issues` with a failing `gh_json`
- `validate_project` when project.toml has a parse error
- `extract_sp` with a label that is neither string nor dict (e.g., int, list)
- `gh` with a timeout scenario (mock `TimeoutExpired`)

---

### 13. LOW: `_split_array` string builder uses concatenation, not list append

**Lines:** 328-361
**Severity:** LOW (performance)

`_split_array` builds strings with `current += ch` character by character.
In CPython, this is O(n^2) for long strings because strings are immutable.
For the small arrays in project.toml configs, this is irrelevant. But if
someone has a 10KB array value, it would be noticeably slow.

**Impact:** Negligible for all realistic inputs. A `list`/`join` pattern
would be more idiomatic but is not worth changing.

---

### 14. LOW: No circular import risk, but global mutable state via `KANBAN_STATES`

**Lines:** 829-830
**Severity:** LOW

`KANBAN_STATES` is a `frozenset`, so it's immutable. There is no mutable
global state in this module. The `_KANBAN_STATES` backward-compat alias
is just a reference to the same frozen object. No circular import issues
exist — the module has no internal imports and all skill scripts import
from it unidirectionally.

The import chain is clean: validate_config imports only stdlib modules
(json, re, subprocess, sys, datetime, pathlib). No skill script imports
validate_config at module scope in a way that could create cycles.

**Impact:** None. This is a clean bill of health for architecture.

---

## Missing Test Coverage Summary

The following function/branch combinations have zero test coverage and
represent the highest-value targets for new tests:

1. `gh()` timeout path (lines 62-63) — mock `subprocess.TimeoutExpired`
2. `gh_json()` dict-in-paginated-response path (line 107) — mock concatenated `{...}{...}` JSON
3. `_unescape_toml_string()` for `\n`, `\t`, unknown escapes (lines 241-263)
4. `validate_project()` when TOML file exists but fails to parse (lines 442-443)
5. `extract_sp()` with non-string/non-dict labels (line 768)
6. `list_milestone_issues()` when `gh_json` raises (lines 877-880)
7. `main()` CLI entry point (line 916)

---

## Architecture Assessment

The module is well-designed as a shared dependency:

- No mutable global state
- No circular import risk
- No shell injection vectors (all subprocess calls use list args)
- Clean separation between parsing, validation, and query helpers
- Idempotent validation (can be called multiple times safely)

The main risk is the TOML parser's "forgiving" behavior — it silently
accepts many forms of invalid TOML rather than raising errors. This is
a deliberate design choice (documented in comments) but it means config
errors can propagate silently through the system. The parser is adequate
for the narrow subset of TOML actually used by project.toml files, but
it would be dangerous to rely on it for arbitrary TOML.
