# Phase 3 — Adversarial Code Audit (Bug Hunter Pass 37)

Pass date: 2026-03-21

---

## BH37-001: sync_tracking.py case-insensitive lookup mismatch in main()

**File:** `skills/sprint-run/scripts/sync_tracking.py:292`
**Bug type:** Key normalization inconsistency (latent)
**Severity:** MEDIUM

**Description:** In `main()`, the `existing` dict is built with `key = tf.story.upper()` (line 271), so all keys are uppercase. However, when looking up issues at line 292, the check `if sid in existing` uses the raw output of `extract_story_id()`. Currently `extract_story_id` always returns uppercase (for standard IDs via the regex match, and for fallback slugs via `.upper()` at line 976), so this works. But the inconsistency means if `extract_story_id` is ever changed to preserve case, sync_tracking would silently create duplicate tracking files instead of updating existing ones.

**Suggested fix:** Normalize with `.upper()` at the lookup site:
```python
key = sid.upper()
if key in existing:
```

---

## BH37-005: TOML parser _has_closing_bracket lacks bracket depth tracking, breaks multiline nested arrays

**File:** `scripts/validate_config.py:255-268`
**Bug type:** Missing nesting depth in bracket detection
**Severity:** MEDIUM

**Description:** `_has_closing_bracket` returns True on the first unquoted `]` it finds, without tracking bracket depth. This means multiline arrays containing nested arrays terminate collection too early.

**Reproduction:**
```toml
[ci]
check_commands = [
    ["lint", "test"],
    "build",
]
```

Trace: The continuation line `["lint", "test"],` causes `_has_closing_bracket` to return True at the `]` after "test" (which closes the inner array, not the outer one). The multiline buffer becomes `[ ["lint", "test"],` and `_parse_value` receives a string starting with `[` but not ending with `]`, causing a `ValueError` from the metacharacter check at line 363.

The existing test at `tests/test_bugfix_regression.py:450` only covers single-line nested arrays (`[["a", "b"], ["c", "d"]]`), which bypass the multiline path entirely.

**Suggested fix:** Add bracket depth tracking:
```python
def _has_closing_bracket(s: str) -> bool:
    quote_char = None
    depth = 0
    for i, ch in enumerate(s):
        if quote_char is None:
            if ch in ('"', "'"):
                quote_char = ch
            elif ch == '[':
                depth += 1
            elif ch == ']':
                if depth == 0:
                    return True
                depth -= 1
        elif ch == quote_char:
            if quote_char == '"' and _count_trailing_backslashes(s, i) % 2 != 0:
                continue
            quote_char = None
    return False
```

---

## BH37-007: session_context.py _read_toml_string unescape is too aggressive

**File:** `.claude-plugin/hooks/session_context.py:40`
**Bug type:** Incorrect TOML escape processing
**Severity:** MEDIUM

**Description:** Line 40 uses `re.sub(r'\\(.)', lambda x: x.group(1), m.group(1))` which maps ANY `\X` sequence to just `X`. Per TOML spec, `\n` should become a newline, `\t` should become a tab, `\uXXXX` should become a Unicode character, and unknown escapes should be errors. This implementation converts `\n` to literal `n`, `\t` to literal `t`, etc.

The comment says "Unescape \" and \\\\" but the regex is not limited to those. Compare with `verify_agent_output.py:_unescape_basic_string` (lines 27-56) which correctly handles each escape type individually, and `validate_config.py:_unescape_toml_string` (lines 271-315) which handles the full spec.

Currently this function only reads `sprints_dir` and `team_dir` path values, which are unlikely to contain `\n` or `\t`. But a path containing a literal backslash would be corrupted: `C:\\Users\\data` would become `C:\Users\data` which looks correct on a single-char level but `\\n` in a path like `sprint-config\\new-team` would become `sprint-config\new-team` with the `\n` interpreted as just `n` (correct by accident) rather than as a newline (wrong). However, `\\t` in `sprint-config\\team` would become `sprint-config\team` with `\t` becoming `t` (correct by accident). The real failure would be a path like `data\notes` written as `"data\\notes"` in TOML -- this would become `datanotes` (wrong, should be `data\notes`). Wait, actually: `\\` -> `\` (first backslash is escape), so `"data\\notes"` in TOML means the literal string `data\notes`. The regex would process `\\` -> `\` (correct) and `n` is not preceded by `\`, so `data\notes` is correct. The bug only manifests for unknown escapes like `\a` (which should be an error per TOML spec but here becomes `a`).

In practice, this is a minor spec violation rather than a functional bug for current usage.

**Suggested fix:** Replace the catch-all regex with a proper escape map:
```python
_ESCAPES = {'"': '"', '\\': '\\', 'n': '\n', 'r': '\r', 't': '\t'}
return re.sub(r'\\(.)', lambda x: _ESCAPES.get(x.group(1), x.group(0)), m.group(1))
```

---

## BH37-014: sprint_init.py generate_team writes wrong filename in INDEX.md when stem collision occurs

**File:** `scripts/sprint_init.py:729-746`
**Bug type:** Filename mismatch between symlink and INDEX table
**Severity:** MEDIUM

**Description:** When stem collisions are detected (lines 729-737), symlinks are created with disambiguated names (e.g., `team/subdir-alice.md`). But the INDEX.md generation at lines 742-746 uses `Path(sf.path).stem + ".md"` -- the ORIGINAL stem, not the disambiguated one.

**Reproduction:** Two persona files with the same stem in different directories:
- `docs/team/alice.md`
- `docs/personas/alice.md`

Result: Symlinks created correctly as `team/alice.md` and `team/personas-alice.md`. But INDEX.md lists `alice.md` for both rows. The second persona's file reference is wrong -- it should be `personas-alice.md`.

**Suggested fix:** Track the disambiguated stem per persona and use it when building the INDEX:
```python
# Build display info during symlink creation
display_info = {}
for sf in personas:
    stem = Path(sf.path).stem
    if stem in seen_stems:
        parent = Path(sf.path).parent.name
        stem = f"{parent}-{stem}"
    seen_stems[stem] = sf.path
    display_info[sf.path] = stem
    self._symlink(f"team/{stem}.md", sf.path)

# In INDEX generation:
for sf in personas:
    stem = display_info[sf.path]
    name = stem.replace("-", " ").replace("_", " ").title()
    role = self._infer_role(sf.path)
    filename = f"{stem}.md"
    rows.append(f"| {name} | {role} | {filename} |")
```

---

## BH37-003: Smoke test rate limiting timestamps lack explicit timezone, creating fragile UTC assumption

**File:** `skills/sprint-monitor/scripts/check_status.py:289-291`, `scripts/smoke_test.py:62`
**Bug type:** Implicit timezone in serialized timestamps
**Severity:** LOW

**Description:** `smoke_test.py:write_history()` writes timestamps as `datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")` -- UTC value but no timezone marker in the string. `check_status.py:check_smoke()` parses these with `datetime.strptime(...).replace(tzinfo=timezone.utc)`, assuming UTC. If any code path ever writes a local-time timestamp to the same file, the rate limiting would be wrong (blocking for too long or not long enough depending on timezone offset).

**Suggested fix:** Include a `Z` suffix in the format string to make UTC explicit: `"%Y-%m-%d %H:%MZ"`. Update the parser to strip the `Z` before parsing.

---

## BH37-008: commit_gate.py _working_tree_hash fails on repos with no commits

**File:** `.claude-plugin/hooks/commit_gate.py:62-68`
**Bug type:** Unhandled edge case in empty repository
**Severity:** LOW

**Description:** `_working_tree_hash()` runs `git diff HEAD`, which fails when HEAD doesn't exist (no commits yet). The function returns `""` on failure, causing `needs_verification()` to return `True`, which blocks all commits with "Tests have not been run since the last code change." This makes it impossible to create the initial commit in a new repository when the commit gate hook is active.

**Suggested fix:** Fall back to `git diff --cached` when `git diff HEAD` fails (which shows staged changes without requiring HEAD).

---

## BH37-010: sync_tracking.py create_from_issue slug collision check is case-sensitive

**File:** `skills/sprint-run/scripts/sync_tracking.py:200`
**Bug type:** Case-sensitive comparison after case-insensitive normalization
**Severity:** LOW

**Description:** The collision check at line 200 does `existing.story != sid` where `sid` is from `extract_story_id()` (always uppercase). If a tracking file was manually created with a lowercase story ID, this comparison would be True even for the same story, triggering the collision fallback and creating a duplicate filename.

**Suggested fix:** `if existing.story and existing.story.upper() != sid.upper():`

---

## BH37-016: First release version can never be v0.1.0

**File:** `skills/sprint-release/scripts/release_gate.py:120-133`
**Bug type:** Version calculation edge case
**Severity:** LOW

**Description:** When no semver tags exist, `base` is set to `"0.1.0"`. If there are any commits (always true for a first release), the version is bumped from 0.1.0, producing at minimum v0.1.1 (patch) or v0.2.0 (minor). The base version 0.1.0 itself is never assignable as a release tag.

**Suggested fix:** Add a `--initial-version` flag or treat the first release as the base version without bumping.

---

## BH37-002: Unquoted TOML numeric values become Python int, may cause TypeError downstream

**File:** `scripts/validate_config.py:356-359`
**Bug type:** Type confusion on unquoted numeric values
**Severity:** LOW

**Description:** `_parse_value` converts any all-digit unquoted value to `int`. Downstream code like `release_gate.py:gate_build` (line 251) does `Path(binary)` where `binary` comes from config. If `binary_path = 123` (unquoted), `Path(123)` raises `TypeError`. The error message would be confusing -- no indication it's a TOML quoting issue.

**Suggested fix:** Add type guards in downstream consumers, or have `_parse_value` warn when an unquoted value looks numeric but is in a string-expected context.

---

## Summary

| ID | File | Severity | Type | Status |
|----|------|----------|------|--------|
| BH37-005 | validate_config.py:255-268 | MEDIUM | Missing bracket depth in multiline array detection | Confirmed, reproducible |
| BH37-014 | sprint_init.py:729-746 | MEDIUM | INDEX filename wrong on stem collision | Confirmed, reproducible |
| BH37-001 | sync_tracking.py:292 | MEDIUM | Key normalization inconsistency (latent) | Confirmed, defensive fix |
| BH37-007 | session_context.py:40 | MEDIUM | Over-broad TOML escape processing | Confirmed, spec violation |
| BH37-003 | check_status.py:289-291 | LOW | Timezone ambiguity in rate limiting | Confirmed, fragile |
| BH37-008 | commit_gate.py:62-68 | LOW | Empty repo breaks working tree hash | Confirmed, edge case |
| BH37-010 | sync_tracking.py:200 | LOW | Case-sensitive collision check | Confirmed, edge case |
| BH37-016 | release_gate.py:120-133 | LOW | First release can never be v0.1.0 | Confirmed, design limitation |
| BH37-002 | validate_config.py:356-359 | LOW | Unquoted numeric int coercion | Confirmed, type safety |

**4 MEDIUM, 5 LOW.** No HIGH-severity issues found. The codebase is well-hardened from 36 prior bug-hunter passes.
