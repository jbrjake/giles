# Pass 34: Core Files Audit

Four files were NOT audited in pass 33: `scripts/validate_config.py`,
`scripts/kanban.py`, `skills/sprint-setup/scripts/populate_issues.py`, and
`skills/sprint-setup/scripts/bootstrap_github.py`. This pass covers all four.

---

## File: scripts/validate_config.py

### Audited in pass 33? No
### Latest changes:
```
15694b0 fix: resolve all deferred items — atomic writes, dry-run, lock docs, test corrections
8527b9d fix: cross-component gap analysis — TOML unescape, boundary matching, test corrections
```

### Findings:

- **BUG (TOML parser, line 202): bare-key regex rejects hyphen-leading keys.**
  The regex `^([a-zA-Z0-9_][a-zA-Z0-9_-]*)` requires the first character to be
  `[a-zA-Z0-9_]`, excluding `-`. The TOML v1.0 spec allows bare keys to start
  with a hyphen (`-key = "val"` is legal TOML). The comment on line 201 says
  "BH20-002: Allow digit-start keys per TOML spec (bare keys are [A-Za-z0-9_-])"
  but the code does NOT allow hyphen-start. Any TOML file with a hyphen-leading
  key would trigger the unrecognized-line warning at line 219 and silently drop
  the key. Severity: low (hyphen-start keys are rare and the project template
  does not use them), but the comment is inaccurate.

- **BUG (TOML parser, line 179): section header regex also rejects hyphen-leading
  sections.** `^\[([a-zA-Z0-9_][a-zA-Z0-9_.-]*)` has the same first-char
  restriction. `[-my-section]` is valid TOML but would not be recognized as a
  section header — it would be silently ignored. Same severity as above.

- **BUG (line 336-337): double-quoted string parser accepts malformed strings.**
  `_parse_value` checks `raw.startswith('"') and raw.endswith('"')` but does not
  verify there are no unescaped `"` characters in the middle. Input like
  `"hello"world"` passes the check (starts and ends with `"`) and produces
  `hello"world` via `_unescape_toml_string("hello\"world")`. This silently
  accepts malformed TOML. Severity: low (only affects hand-edited TOML with
  typos; `_strip_inline_comment` would likely have already truncated the value
  at a bare `#` before reaching this point).

- **BUG (line 340-341): single-quoted literal string has the same issue.** A
  value like `'don't'` would be parsed as `don't` rather than raising an error.
  The middle `'` is treated as the closing quote by `_strip_inline_comment` in
  the comment-stripping pass, but in `_parse_value`'s string branch, the whole
  string still starts and ends with `'`, so `raw[1:-1]` yields `don'`. Severity:
  very low — real TOML parsers would reject this, but in practice project.toml
  values rarely contain apostrophes.

- **BUG (line 292-298, 299-305): `\uXXXX` / `\UXXXXXXXX` boundary check is
  off by one.** For `\u`, the check is `i + 6 <= len(s)`, meaning the string
  needs at least 6 chars remaining from position `i` (which is the `\`). The
  slice `s[i+2:i+6]` takes 4 hex digits. For a string ending with exactly
  `\uABCD` (i.e., `\` at position `len(s)-6`), the check `i + 6 <= len(s)`
  passes and the slice is correct. For `\u` at position `len(s)-5` (only 3 hex
  digits available), `i + 6 <= len(s)` fails, falling through to append the raw
  `\u` — correct. For `\u` at position `len(s)-2` (no hex digits at all),
  `i + 6 > len(s)` fails, fallthrough appends `\u` — correct. Actually, on
  careful re-examination, the boundary math is correct. **CLEAN (false alarm).**

- **BUG (minor, line 1079): `_yaml_safe` numeric string regex catches dotted
  versions.** The regex `^\d+\.?\d*$` matches strings like `1.0` and `22` but
  also `1.2.3` — wait, no, `.` is not `\.?` repeated. `^\d+\.?\d*$` only
  matches zero or one dot. `1.2.3` would NOT match. So `_yaml_safe` would not
  quote a version string like `1.2.3`. But `1.2.3` does not need quoting in
  YAML anyway. **CLEAN.**

- **BUG (minor, doc inconsistency, line 93-94): `kanban-protocol.md` says
  review (2/reviewer) and integration (3/team) WIP limits are "Behavioral"
  (not code-enforced), but `kanban.py check_wip_limit()` (lines 261-268)
  enforces all three in code.** The docstring at line 247 says "Enforced limits
  (from kanban-protocol.md)" but the protocol doc at line 98-99 says review and
  integration limits are "Behavioral". The code is stricter than the docs
  promise. This is a doc/code mismatch, not a runtime bug — the code behavior
  is the safer of the two. Fix: update kanban-protocol.md WIP table to mark
  review and integration as code-enforced, or add `--force-wip` guidance.

- **CLEAN: `_strip_inline_comment` and `_has_closing_bracket`** — quote tracking
  correctly handles escaped double quotes via `_count_trailing_backslashes`. The
  logic for single-quoted literals correctly skips escape checking (TOML spec:
  literal strings have no escapes).

- **CLEAN: `frontmatter_value`** — the `[^\n]*` fix (BH22-060) correctly
  prevents cross-line matching. The single-pass unescape via `re.sub` avoids
  order-dependent bugs.

- **CLEAN: `gh_json` paginate handling** — incremental JSON decoding with
  `raw_decode` correctly merges concatenated arrays from `--paginate`. Error
  path wraps `JSONDecodeError` with a `RuntimeError` including a preview.

- **CLEAN: `write_tf` / `read_tf` round-trip** — `_yaml_safe` quoting and
  `frontmatter_value` unescaping are symmetric. The `\b` (backspace) escape is
  handled in `_unescape_toml_string` and in `frontmatter_value`'s `_UNESCAPE`
  dict.

---

## File: scripts/kanban.py

### Audited in pass 33? No
### Latest changes:
```
15694b0 fix: resolve all deferred items — atomic writes, dry-run, lock docs, test corrections
e49c5b5 fix(kanban): close-first ordering for done transition, e2e hook tests
6eda7ab fix(sync): unify lock scope, atomic writes, case normalization across sync paths
6b5d6c2 fix(kanban): rename append_transition_log to public, consistent WIP warning
```

### Findings:

- **BUG (line 172, lock_story): lock file opened read-only (`"r"`) while
  lock_sprint (line 189) opens read-write (`"r+"`).** The asymmetry is
  cosmetic for `fcntl.flock` (which only needs a valid fd, not write
  permission), but if the lock file has mode 0444 (read-only permissions), the
  `"r+"` open in `lock_sprint` would raise `PermissionError` while `lock_story`
  would succeed. Inconsistent behavior on read-only filesystems or restrictive
  permissions. Severity: low — `.lock` and `.kanban.lock` files are created by
  `.touch()` with default permissions (0644), so the write mode should always
  be available. But `"r"` would be safer and more consistent for both.

- **BUG (line 400-404, do_transition): `done` transition closes issue then
  swaps labels in a non-atomic sequence.** If label swap fails (e.g., network
  error), the issue is closed with a `kanban:dev` (or whatever old status)
  label still on it. The code comment (BH28-001) acknowledges this and argues
  close-first is intentional because "next sync will fix" the stale label.
  However, `kanban_from_labels` (validate_config.py line 1019) overrides to
  "done" for closed issues, so this is indeed self-healing. **CLEAN by design
  (acknowledged trade-off).**

- **BUG (line 281, check_wip_limit): reads all story files without holding a
  lock.** `check_wip_limit` is called from within `do_transition`, which in
  the CLI path is called under `lock_sprint` for WIP-limited states (line 780).
  But the API-level caller could call `do_transition` without `lock_sprint`,
  in which case the WIP count would be a TOCTOU race. The docstring on
  `do_transition` (line 331) says "Caller must hold lock_story(tf.path)" but
  does NOT say callers must hold lock_sprint for WIP-limited transitions. The
  CLI handles this correctly (line 777-788), but the API contract is incomplete.
  Severity: medium for API callers, zero for CLI users.

- **BUG (line 313, append_transition_log): uses naive `datetime.now()` instead
  of UTC.** This is consistent with the rest of the file but inconsistent with
  `check_status.py` which uses `datetime.now(timezone.utc)` for its main loop.
  Transition log timestamps will shift if the system timezone changes. Severity:
  cosmetic — timestamps are for human reading, not programmatic comparison.

- **BUG (minor, line 286, check_wip_limit): `getattr(other, persona_field)`
  comparison is case-sensitive.** If one tracking file has `implementer: alice`
  and another has `implementer: Alice`, the WIP check treats them as different
  personas. The `find_story` function (line 216-221) normalizes to uppercase,
  but persona names in tracking files are not normalized. Severity: low —
  persona assignment comes from `do_assign` which preserves the case given by
  the caller, and sprint-run skills are consistent about case.

- **BUG (minor, line 597-606, do_sync prune): pruning deletes `.lock` files
  for orphaned stories, but if another process holds that lock, the delete
  succeeds (unlink removes the directory entry) but the locking fd remains
  valid until the other process releases it.** On POSIX, this is fine — the
  inode persists until the last fd closes. The lock sentinel approach (line 170)
  means a new `.lock` file could be created immediately, with a different inode,
  so the old holder's lock becomes meaningless. Severity: very low — pruning
  while another process is actively modifying the same story is an unusual
  concurrent scenario. **CLEAN (POSIX semantics handle this correctly).**

- **CLEAN: lock_story sentinel approach.** Using `.lock` suffix instead of
  locking the tracking file itself correctly avoids the inode-replacing rename
  from `atomic_write_tf` invalidating the lock.

- **CLEAN: do_transition rollback.** On GitHub failure, local state is reverted
  to old_status and old_body. The nested try/except for rollback failure
  (BH23-201) correctly restores in-memory state even when disk rollback fails.

- **CLEAN: do_sync case normalization.** Both `local_by_id` keys (line 514)
  and `story_id` from GitHub (line 521) are `.upper()`, preventing case
  mismatches.

- **CLEAN: do_update field whitelist.** `_UPDATABLE_FIELDS` prevents mutation
  of immutable fields (path, story, sprint, status).

---

## File: skills/sprint-setup/scripts/populate_issues.py

### Audited in pass 33? No
### Latest changes:
```
2768f12 fix: pattern siblings + cross-component seam fixes
d9e874b fix: heading injection, silent defaults, missing warnings, doc accuracy
069ab46 fix: narrow exception handling, substring match, branch length, YAML escaping
```

### Findings:

- **BUG (line 148-160, `_add_story` closure): captures `seen_ids` and
  `stories` from the enclosing scope correctly, but `row_re` group indices
  are hardcoded to (1)=id, (2)=title, (3)=epic, (4)=saga, (5)=sp, (6)=priority.**
  If a custom `story_id_pattern` contains its own groups (despite the
  `_safe_compile_pattern` check rejecting capturing groups), the indices would
  shift. The `_safe_compile_pattern` at line 72 checks for `(?<!\\)\((?!\?)` —
  this catches `(...)` but allows `(?:...)` non-capturing groups. If a user
  provides a pattern like `(?:US|PROJ)-\d{4}`, the non-capturing group does NOT
  create a numbered group, so indices remain correct. **CLEAN.**

- **BUG (line 51, `_DEFAULT_ROW_RE`): epic column detection `(?:(E-\d{4})\s*\|\s*)?`
  is greedy-optional.** For a 5-column row without an epic column, the regex
  correctly skips the optional group. For a 6-column row WITH an epic column,
  the E-XXXX pattern captures correctly. But if a title cell happens to start
  with `E-XXXX` (e.g., `E-Commerce Platform`), the regex would try to match it
  as an epic.** Actually, the epic group appears AFTER the title group:
  `\|\s*(.+?)\s*\|\s*(?:(E-\d{4})\s*\|\s*)?(S\d{2})\s*\|`. The title is
  `(.+?)` which is non-greedy. Given `| US-0001 | E-Commerce Platform | S01 | 3 | P1 |`,
  the non-greedy `(.+?)` would match `E-Commerce Platform` only if backtracking
  shows that matching less does not satisfy the rest. The epic group `(E-\d{4})`
  would try to match `S01`, which fails. So the title would be `E-Commerce Platform`
  and epic would be empty. **CLEAN (regex backtracking handles this correctly).**

  Actually, wait. Let me re-examine. The non-greedy `(.+?)` would first try to
  match just `E` for the title. Then `\s*\|\s*` would need a `|`. The input after
  `E` is `-Commerce Platform | S01 | 3 | P1 |` which does not start with `|`.
  So the regex engine extends the non-greedy match: `E-` -> try `|` -> no. Keep
  going: `E-C` -> no. Eventually `E-Commerce Platform` -> `\s*\|\s*` matches
  ` | ` -> then `(?:(E-\d{4})\s*\|\s*)?` tries `S01` which fails, so it's
  skipped -> `(S\d{2})` matches `S01`. Correct.

- **BUG (line 257): `int(meta.get("story_points", "0"))` raises ValueError on
  non-numeric story_points.** If a detail block has `| Story Points | TBD |`,
  `int("TBD")` raises ValueError with an unhandled traceback. Should use
  `safe_int` from validate_config. Severity: medium — affects any milestone
  file with non-numeric story points in detail blocks.

- **BUG (line 488, `create_issue`): issue body passed via `--body` can fail
  for very long bodies.** The `gh` helper uses `subprocess.run(["gh", ...])`,
  which passes the body as a command-line argument. On Linux, `ARG_MAX` is
  typically ~2MB, but on macOS it can be lower for individual arguments. Very
  large issue bodies (e.g., stories with extensive acceptance criteria) could
  hit the limit. Severity: low — issue bodies from `format_issue_body` are
  typically well under 1KB.

- **CLEAN: `_safe_compile_pattern` ReDoS protection.** Tests multiple character
  classes (not just `"a"`) to catch patterns that fast-fail on some inputs but
  backtrack on others. The 0.5s threshold with 25-char input is a reasonable
  heuristic.

- **CLEAN: `build_milestone_title_map`.** Content-first sprint detection
  correctly handles multi-sprint milestone files. Warning on conflicting
  sprint-to-title mappings is helpful.

- **CLEAN: `get_existing_issues` idempotency check.** Uses `extract_story_id`
  + regex filter to only track proper story IDs, preventing false dedup from
  slug-based fallbacks.

---

## File: skills/sprint-setup/scripts/bootstrap_github.py

### Audited in pass 33? No
### Latest changes:
```
2768f12 fix: pattern siblings + cross-component seam fixes
d9e874b fix: heading injection, silent defaults, missing warnings, doc accuracy
069ab46 fix: narrow exception handling, substring match, branch length, YAML escaping
```

### Findings:

- **BUG (line 276-277, `create_milestones_on_github`): title/description
  sanitization strips control characters but does not limit length.** GitHub
  milestone titles have a 255-character limit. A very long `# Heading` line
  would produce an API error. Severity: very low — milestone file headings are
  short in practice.

- **BUG (minor, line 278-283): milestone API call uses `-f` (form field)
  instead of `-F` (typed JSON field).** With `-f`, all values are strings. The
  GitHub API accepts `state` as a string, so this works, but if additional
  fields were added that require non-string types (e.g., `due_on` as a date),
  `-f` would send them as quoted strings rather than JSON types. Severity:
  none currently — all three fields (`title`, `description`, `state`) are
  strings.

- **BUG (minor, line 147-148, `_parse_saga_labels_from_backlog`): saga ID regex
  `(S\d{2})` requires exactly 2 digits.** A saga `S100` would not be matched.
  The backlog format uses `S01`-`S99`, so this is correct for the documented
  convention, but the regex silently drops `S100+` sagas without warning.
  Severity: low — 99 sagas is more than any realistic project would have.

- **BUG (minor, line 97-99, `_collect_sprint_numbers`): filename-based sprint
  inference `re.search(r"(\d+)", mf.stem)` matches the first digit sequence.**
  A file named `v2-milestone-3.md` would yield sprint number `2` (from the
  `v2` prefix) instead of `3`. Severity: low — milestone filenames in practice
  follow the convention `milestone-N.md`.

- **CLEAN: `create_label` uses `--force` flag**, which updates existing labels
  rather than failing. Idempotent.

- **CLEAN: `create_milestones_on_github` correctly handles `already_exists`**
  error by checking the error message string. The API returns a 422 with
  "already_exists" validation error.

- **CLEAN: `create_epic_labels` scans for `E-\d{4}` in filenames**, which is
  the documented convention from the skeleton templates.

- **CLEAN: saga file fallback** (BH-004) correctly reads heading from saga
  files when INDEX.md has no saga rows.

---

## Cross-file findings

- **Doc/Code mismatch: kanban-protocol.md vs kanban.py WIP limits.** The
  protocol doc says review (2/reviewer) and integration (3/team-wide) WIP
  limits are "Behavioral" (meaning guidelines, not code-enforced), but
  `kanban.py check_wip_limit()` enforces all three limits in code. The `--force-wip`
  flag bypasses them, but the default behavior is stricter than documented.

- **Inconsistent datetime usage across kanban.py and check_status.py.**
  `kanban.py` uses naive `datetime.now()` for transition logs.
  `check_status.py` uses `datetime.now(timezone.utc)` for its main loop but
  naive `datetime.now()` for smoke test rate limiting. This inconsistency was
  already noted in pass 33 for check_status.py but the kanban.py side was not.

---

## Summary

| File | Verdict |
|------|---------|
| validate_config.py | 2 minor bugs (hyphen-start keys, malformed string acceptance), 1 doc mismatch |
| kanban.py | 1 medium bug (API contract for WIP lock), 2 minor (naive datetime, case-sensitive persona), 1 doc mismatch |
| populate_issues.py | 1 medium bug (ValueError on non-numeric story_points in detail blocks) |
| bootstrap_github.py | CLEAN (3 theoretical edge cases, no practical bugs) |

**Priority fix:** `populate_issues.py` line 257 — `int(meta.get("story_points", "0"))` should use `safe_int()` to handle non-numeric values gracefully.

**Doc fix:** `kanban-protocol.md` WIP limits table should mark review and integration as code-enforced (matching actual `check_wip_limit` behavior), or note the `--force-wip` override.
