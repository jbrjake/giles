# Bug Hunter Pass 35 — release_gate.py Audit

**Date:** 2026-03-21
**Target:** `skills/sprint-release/scripts/release_gate.py`
**Also reviewed:** `skills/sprint-release/references/release-checklist.md`, `tests/test_release_gate.py`

---

## BH35-001: write_version_to_toml corrupts TOML when [release] has no trailing newline

**File:** `skills/sprint-release/scripts/release_gate.py:314-320`
**Severity:** MEDIUM

When `[release]` exists at the end of the file with no trailing newline and
no `version` key, the insertion path concatenates the version key directly
after the closing bracket, producing invalid TOML.

**Trace through the bug:**

Given `text = "[release]"` (no trailing `\n`):

1. `insert_pos = start + len("[release]")` = 9
2. `nl = text.find("\n", 9)` returns `-1` (no newline found)
3. `nl = len(text)` = 9
4. `text[:nl + 1]` = `text[:10]` = `"[release]"` (Python clips to end)
5. Result: `"[release]version = \"1.0.0\"\n"` — no newline between header and key

**How to trigger:** Create a `project.toml` that ends with `[release]` and no
trailing newline, then run `do_release`. The written file will have
`[release]version = "X.Y.Z"` on a single line, which is not valid TOML.

**Why it matters:** The corrupted TOML file will fail to parse on the next
`load_config()` call, breaking all subsequent sprint operations. The version
bump commit would have already been made with the corrupted file.

**Fix:** After setting `nl = len(text)` when `find` returns -1, insert a
newline before the version key:

```python
if nl == -1:
    nl = len(text)
    text = text[:nl] + "\n" + f'version = "{version}"\n' + text[nl:]
else:
    text = text[:nl + 1] + f'version = "{version}"\n' + text[nl + 1:]
```

**Test gap:** No test covers `[release]` at EOF without trailing newline.

---

## BH35-002: write_version_to_toml creates duplicate key when existing version uses single quotes

**File:** `skills/sprint-release/scripts/release_gate.py:308-312`
**Severity:** MEDIUM

The version replacement regex `r'^version\s*=\s*"[^"]*"'` only matches
double-quoted values. If the existing `version` key uses single quotes
(`version = '1.0.0'`), the regex does not match, and the code falls through
to the `else` branch, inserting a second `version` line with double quotes.

**How to trigger:** A `project.toml` with:
```toml
[release]
version = '1.0.0'
```

After `write_version_to_toml("2.0.0", path)`, the file becomes:
```toml
[release]
version = "2.0.0"
version = '1.0.0'
```

This is a TOML duplicate key, which is invalid per the TOML spec. Different
parsers handle it differently — some use the first value, some the last.

**Why it matters:** The project's custom TOML parser (`parse_simple_toml`)
likely uses last-value-wins, so the OLD version would shadow the new one.
The release would appear to succeed, but the version in config would be stale.

**Fix:** Extend the regex to match both quote styles:
```python
version_re = re.compile(r'''^version\s*=\s*(?:"[^"]*"|'[^']*')''', re.MULTILINE)
```

**Test gap:** No test covers single-quoted version values.

---

## BH35-003: _rollback_tag attempts remote tag deletion when tag was never pushed

**File:** `skills/sprint-release/scripts/release_gate.py:608-615, 623-626`
**Severity:** LOW

When `git push origin base_branch v{new_ver}` fails (line 619-622), the
push never completed, so the tag exists only locally. But `_rollback_tag()`
unconditionally runs `git push --delete origin v{new_ver}` (line 608-609),
which will fail because the remote tag doesn't exist. The failure is caught
and prints a warning telling the user to "run manually: git push --delete
origin v{new_ver}" — but there's nothing to delete on the remote.

**How to trigger:** Any push failure (network error, auth failure, branch
protection) triggers `_rollback_tag()` which prints a misleading warning.

**Why it matters:** The warning is confusing but not harmful. The local tag
IS correctly deleted. The user might waste time trying to delete a non-existent
remote tag.

**Fix:** Track whether the push succeeded before attempting remote tag deletion,
or check if the tag exists on the remote before trying to delete it, or change
the warning message to be conditional:

```python
def _rollback_tag() -> None:
    subprocess.run(["git", "tag", "-d", f"v{new_ver}"], ...)
    if pushed_to_remote:
        subprocess.run(["git", "push", "--delete", "origin", f"v{new_ver}"], ...)
```

---

## BH35-004: generate_release_notes omits Full Changelog section entirely on true first release

**File:** `skills/sprint-release/scripts/release_gate.py:399-422`
**Severity:** LOW

On the very first release (no previous tags exist), `calculate_version`
returns `base = "0.1.0"` and `new_version = "0.2.0"`. These are different,
so `prev_tag = "v0.1.0"` (non-empty), and the function correctly checks
whether the tag exists in git (it doesn't), falling through to "initial
release" text. This path works.

However, there is a different scenario: when the first release is a pure
patch (all commits are `chore:` or `docs:`). Then `bump_version("0.1.0",
"patch")` returns `"0.1.1"`. Again `prev_version != version`, so it checks
for tag `v0.1.0` — which doesn't exist — and shows "initial release". OK.

The subtle case: when `calculate_version` finds no tags AND all commits are
patches, the base is `"0.1.0"` and version is `"0.1.1"`. The release notes
say "initial release (v0.1.1)" which is technically correct but the compare
link section says "This is the initial release (v0.1.1)" even though it's
a patch. Not wrong, just potentially surprising.

Actually, after re-examination this works correctly. Downgrading to
informational — no fix needed.

---

## BH35-005: determine_bump matches BREAKING CHANGE anywhere in body, not just as a trailer

**File:** `skills/sprint-release/scripts/release_gate.py:93`
**Severity:** LOW

The check `"BREAKING CHANGE:" in body` uses substring matching rather than
checking for a proper conventional commit footer/trailer. A commit body like:

```
This change is unrelated to the BREAKING CHANGE: mentioned in issue #42.
```

would be detected as a breaking change, triggering a major version bump.

**How to trigger:** Any commit whose body contains the literal string
`BREAKING CHANGE:` anywhere (not just as a footer at the start of a line
after a blank line).

**Why it matters:** Could cause an unexpected major version bump based on
a passing mention of "BREAKING CHANGE:" in a commit body. In practice this
is unlikely because developers rarely write that exact string in non-footer
positions, but it violates the conventional commits spec which defines
`BREAKING CHANGE` as a footer token.

**Fix (if desired):** Use a regex that matches the start of a line:
```python
if re.search(r"^BREAKING[ -]CHANGE:", body, re.MULTILINE):
    return "major"
```

This is a common simplification across many conventional-commit tools, so
fixing it is optional.

---

## BH35-006: gate_ci passes based on ANY workflow, not the project's CI workflow

**File:** `skills/sprint-release/scripts/release_gate.py:159-171`
**Severity:** MEDIUM

`gate_ci` fetches the single most recent workflow run on the base branch
(`--limit 1`) without filtering by workflow name. If a repo has multiple
workflows (e.g., CI, docs-deploy, nightly-cron), the most recent run might
be from a non-CI workflow. A successful docs-deploy run would cause the CI
gate to pass even if the actual CI workflow failed.

Conversely, a failed cron job could block a release even though CI is green.

**How to trigger:** Have any workflow run complete after the CI workflow.
For example, a docs-deploy workflow triggered by the same push completes
after the CI workflow. `--limit 1` returns the most recent one.

**Why it matters:** This is a false-pass risk (non-CI workflow masquerading
as CI success) or a false-fail risk (non-CI workflow failure blocking
release). Both undermine the gate's purpose.

**Fix:** Filter by workflow name or file. The `gh run list` command
supports `--workflow` to filter by workflow file:

```python
def gate_ci(config: dict) -> tuple[bool, str]:
    base_branch = get_base_branch(config)
    workflow = config.get("ci", {}).get("workflow", "")
    cmd = [
        "run", "list", "--branch", base_branch, "--limit", "1",
        "--json", "status,conclusion,name",
    ]
    if workflow:
        cmd.extend(["--workflow", workflow])
    runs = gh_json(cmd)
    ...
```

**Test gap:** No test verifies that gate_ci checks the correct workflow. All
tests use a single mock run.

---

## BH35-007: Release checklist claims gates check things the code does not

**File:** `skills/sprint-release/references/release-checklist.md:12-13, 28-30`
**Severity:** LOW

The release checklist specifies gate criteria that are NOT implemented in code:

1. **Stories Gate** (line 12-13): Checklist says "All story tracking files
   show status: done" — `gate_stories()` only checks GitHub issues, never
   reads local tracking files.

2. **Tests Gate** (line 29-30): Checklist says "Golden path tests pass
   end-to-end" and "No P0 bugs remain open" — `gate_tests()` only runs
   `check_commands` from config, with no special handling for golden path
   tests or P0 bug queries.

**Why it matters:** The checklist creates expectations that the automated
gates check things they don't. A release could pass all automated gates
while violating checklist criteria that a human reviewer would expect to be
enforced.

**Fix:** Either:
- Add the missing checks to the gate functions, or
- Annotate the checklist to distinguish automated gates from manual checks:
  `- [ ] [MANUAL] All story tracking files show status: done`

---

## Coverage Gaps in tests/test_release_gate.py

The test file is thorough (2100+ lines) but has these gaps:

1. **No test for `[release]` at EOF without trailing newline** (BH35-001)
2. **No test for single-quoted version values** (BH35-002)
3. **No test for `gate_ci` with non-CI workflow runs** (BH35-006)
4. **No test for `gate_stories` with exactly 500 open issues** (truncation
   behavior, though gate correctly fails regardless)
5. **No test for `determine_bump` with BREAKING CHANGE substring in
   non-footer position** (BH35-005)
6. **No test for `write_version_to_toml` idempotency** (calling it twice
   with different versions)
7. **No test for `bump_version` with non-numeric parts** (e.g.,
   `"1.2.beta"` — would raise `ValueError` from `int()` but not caught
   with a clean message)
8. **No test for `gate_ci` when `conclusion` is null (in-progress run)**

---

## Summary

| ID | Severity | Description |
|----|----------|-------------|
| BH35-001 | MEDIUM | write_version_to_toml corrupts TOML when [release] has no trailing newline |
| BH35-002 | MEDIUM | write_version_to_toml creates duplicate key for single-quoted version |
| BH35-003 | LOW | _rollback_tag prints misleading warning about remote tag that was never pushed |
| BH35-005 | LOW | BREAKING CHANGE detected via substring match, not footer position |
| BH35-006 | MEDIUM | gate_ci checks most recent workflow run regardless of workflow name |
| BH35-007 | LOW | Release checklist claims automated checks that code does not implement |
