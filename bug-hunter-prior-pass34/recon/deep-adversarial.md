# Deep Adversarial Code Audit

Pass 5 — focused on subtle logic errors, missing edge-case handling, and data corruption risks in recently-added files.

---

## 1. commit_gate.py

### DA-001: `_working_tree_hash()` silently returns "" on empty repo (no HEAD)

**File:** `.claude-plugin/hooks/commit_gate.py:60-67`
**Severity:** Medium

`git diff HEAD` fails with exit code 128 when HEAD does not exist (brand-new repo with no commits). The function catches this via the blanket `except Exception`, but `result.stdout` is read before the exception path — `subprocess.run` itself does not raise on non-zero exit codes. So what actually happens is: `result.returncode` is 128, `result.stdout` is empty bytes (`b""`), and the function returns a hash of the empty bytestring: `sha256(b"").hexdigest()[:16]`.

This means every call in an empty repo returns the same fixed hash. `mark_verified()` stores that hash, and `needs_verification()` compares it. Because the hash is deterministic and stable, the gate never triggers in an empty repo — verification always appears to have passed. This is arguably the correct behavior (no code to test), but it is accidental, not intentional. If a user stages the very first source file and tries to commit, the hash of `git diff HEAD` (which now shows everything) will differ from the stored empty-diff hash, correctly blocking the commit. But if they run tests first, `mark_verified()` captures the new hash, unblocking commit — this works.

**How to trigger:** Initialize a repo with `git init`, don't commit anything, run a test command, stage a file, then commit. Works correctly by accident but for the wrong reasons.

**Suggested fix:** Detect the no-HEAD case explicitly and return a well-documented sentinel (e.g., `"no-head"`), with a comment explaining the empty-repo flow.

### DA-002: `_working_tree_hash()` ignores untracked files

**File:** `.claude-plugin/hooks/commit_gate.py:61-63`
**Severity:** High

`git diff HEAD` only shows differences between HEAD and the working tree for *tracked* files. Untracked files (new source files not yet added to git) are invisible. A developer can:

1. Run tests (mark_verified stores hash X).
2. Create a brand new `.py` file.
3. `git add` the new file.
4. `git commit` — the commit gate checks `_working_tree_hash()`, which returns hash X again because `git diff HEAD` does not include the content of newly-added-but-never-committed files in the diff when they haven't been added before `git diff HEAD` runs... actually wait — `git diff HEAD` *does* show staged new files. But `_has_staged_source_files` would return True.

Let me reconsider: `git diff HEAD` compares HEAD to the *working tree* (both staged and unstaged changes), and it *does* include newly staged files. So after `git add newfile.py`, `git diff HEAD` would show the new file's contents, changing the hash. This works correctly.

**Revised severity:** Not a bug. Retracted.

### DA-003: `_working_tree_hash()` does not check `returncode`

**File:** `.claude-plugin/hooks/commit_gate.py:61-65`
**Severity:** Low

When `git diff HEAD` fails (e.g., not a git repo, or git not installed), `result.returncode` is non-zero but `result.stdout` may contain partial output or be empty. The function hashes whatever is in `stdout` without checking the return code. If git writes an error message to stdout (unusual — git typically uses stderr for errors), the hash would be based on that error message, which could lead to a stable "always verified" state.

In practice git sends errors to stderr, so `stdout` would be empty bytes, producing the same deterministic hash as DA-001. Still, the lack of a returncode check means any git failure is silently treated as "no changes" rather than "unknown state."

**How to trigger:** Run outside a git repo.

**Suggested fix:** Check `result.returncode != 0` and return `""` explicitly in that case, letting the empty-string path in `mark_verified()` (which skips writing) handle it correctly.

### DA-004: Race between `mark_verified()` and `needs_verification()` via temp file

**File:** `.claude-plugin/hooks/commit_gate.py:88-106`
**Severity:** Low

`mark_verified()` uses `Path.write_text()` which is not atomic — it truncates the file before writing. If `needs_verification()` reads the file at exactly the moment it's being written, it could see a partial hash. In practice this is unlikely because these are called from sequential hook invocations, not concurrent processes. But the session ID is shared across subagents that could run in parallel.

**How to trigger:** Two subagents running tests and committing simultaneously in the same session.

**Suggested fix:** Write to a temp file and rename (like `atomic_write_tf` does).

### DA-005: `_has_staged_source_files` and `_working_tree_hash` have different failure semantics

**File:** `.claude-plugin/hooks/commit_gate.py:70-84, 94-106`
**Severity:** Medium

When `_working_tree_hash()` fails (returns `""`), `mark_verified()` skips writing (line 90: `if h:`). So the state file is never created. Then `needs_verification()` finds no state file, calls `_has_staged_source_files()`.

If `_has_staged_source_files()` *also* fails (returns False because of an exception), the commit is *allowed* even though no verification actually happened. Both git commands failed, yet the commit proceeds silently.

**How to trigger:** Run outside a git repo, or with a broken git installation. Stage a source file some other way (unlikely in practice but the logic flow is wrong).

**Suggested fix:** When `_working_tree_hash()` returns `""`, `needs_verification()` should return True (assume verification needed) rather than falling through to `_has_staged_source_files()`.

---

## 2. verify_agent_output.py

### DA-006: `_read_toml_key` matches key names as unanchored prefix

**File:** `.claude-plugin/hooks/verify_agent_output.py:38`
**Severity:** Medium

The regex `rf'{key}\s*=\s*(.*)'` is applied to `stripped` (the full line), but `key` is interpolated as a literal string without anchoring to the start of the line. If a TOML file has a key like `smoke_check_commands`, and you search for `key="check_commands"`, the regex would match because `check_commands` appears as a substring.

Wait — actually `re.match` anchors at the start of the string by default. So this is fine for a bare key. However, if the key name contains regex metacharacters (e.g., a key named `build.command`), the dot would match any character. The actual keys searched are `check_commands`, `smoke_command`, which have no metacharacters. So this is a latent bug, not an active one.

**How to trigger:** Search for a TOML key whose name contains regex metacharacters (`.`, `+`, `*`, etc.). Not currently done.

**Suggested fix:** Use `re.escape(key)` in the pattern: `rf'{re.escape(key)}\s*=\s*(.*)'`.

### DA-007: `_read_toml_key` does not handle inline comments

**File:** `.claude-plugin/hooks/verify_agent_output.py:39-51`
**Severity:** Medium

TOML allows inline comments: `check_commands = ["pytest"] # run tests`. The `val` extracted on line 40 would be `["pytest"] # run tests`. For array values (line 41: `val.startswith("[")`), the `re.findall(r'"([^"]*)"', array_text)` on line 47 would match the quoted string inside the comment too — but only if the comment contains quoted strings. For non-array string values (line 49-50), the comment text would be included in the returned value.

For example: `smoke_command = "make smoke" # quick check` would return `"make smoke" # quick check` (with the quote stripping producing `make smoke" # quick check` — only the leading quote is stripped because the value does not *end* with `"`).

Wait — line 49 checks `val.startswith('"') and val.endswith('"')`. With a comment, val would be `"make smoke" # quick check`, which starts with `"` but ends with `k`, so the string-stripping branch is skipped and the raw value `"make smoke" # quick check` is returned. This would cause a smoke command invocation of literal `"make smoke" # quick check` — which would fail.

**How to trigger:** Add an inline comment to any string value in `project.toml`: `smoke_command = "make smoke" # optional`.

**Suggested fix:** Strip inline comments before processing the value. After extracting `val`, strip everything after an unquoted `#`: handle the case where `#` appears inside quotes vs. outside.

### DA-008: `_read_toml_key` treats `[[double.bracket]]` as a section match

**File:** `.claude-plugin/hooks/verify_agent_output.py:31-32`
**Severity:** Low

Line 31 checks `stripped.startswith("[")`, then line 32 checks `stripped == f"[{section}]"`. If the TOML file contains a TOML array-of-tables `[[ci]]`, the `startswith("[")` check triggers, but `stripped == "[ci]"` would be False because `stripped` is `"[[ci]]"`. So `in_section` is set to False, which means any keys under `[[ci]]` would be invisible. This is actually the correct behavior (TOML array-of-tables is different from a table), but it means the parser would exit the `[ci]` section prematurely if `[[ci]]` appears after `[ci]`.

More importantly: `[ci.extended]` (a nested table) also starts with `[`, and `stripped == "[ci]"` is False, so `in_section` is correctly set to False. Nested sections are handled properly by accident.

**Revised severity:** Not a bug — works correctly. Retracted.

### DA-009: `_read_toml_key` multi-line array stops at first `]` even inside quoted strings

**File:** `.claude-plugin/hooks/verify_agent_output.py:44`
**Severity:** Low

The multi-line array accumulation loop checks `while "]" not in array_text`. If a command string contains a literal `]` character (e.g., `"pytest -k 'test[param]'"`), the loop terminates early, potentially dropping subsequent commands in the array.

**How to trigger:**
```toml
check_commands = [
    "pytest -k 'test[param]'",
    "ruff check",
]
```
The first line contains `]` inside the quoted value, so the loop stops after accumulating just the first line. `re.findall(r'"([^"]*)"', ...)` then only finds `pytest -k 'test[param]'`, missing `ruff check`.

**Suggested fix:** Track quote state when scanning for the closing bracket, or count bracket depth while accounting for quoted strings.

### DA-010: `_read_toml_key` does not handle single-quoted TOML strings

**File:** `.claude-plugin/hooks/verify_agent_output.py:47-50`
**Severity:** Medium

TOML supports both single-quoted literal strings (`'value'`) and double-quoted strings (`"value"`). The array extractor on line 47 uses `r'"([^"]*)"'` — only matching double-quoted values. Single-quoted commands would be invisible:

```toml
check_commands = ['pytest', 'ruff check']
```

Returns an empty list. Similarly, line 49-50 only strips double quotes.

The main `parse_simple_toml()` in `validate_config.py` handles both quote styles (per CLAUDE.md), but this lightweight parser does not.

**How to trigger:** Use single quotes in `project.toml` for `check_commands` or `smoke_command`.

**Suggested fix:** Also match single-quoted strings: `r"""['"]([^'"]*)['"]\s*"""` or handle both patterns.

### DA-011: `update_tracking_verification` corrupts file if frontmatter contains `---` in content

**File:** `.claude-plugin/hooks/verify_agent_output.py:152-167`
**Severity:** Low

`text.split("---", 2)` splits on the first two occurrences of `---`. If the YAML frontmatter or body contains `---` as part of its content (e.g., a horizontal rule in the body, or a value containing `---`), the split could misidentify the frontmatter boundary.

In practice, tracking files use YAML frontmatter delimited by `---` at lines 1 and N, and the body may contain `---` as a horizontal rule. The `split("---", 2)` with `maxsplit=2` yields at most 3 parts: `["", frontmatter, rest_of_file]`. If the body contains `---`, it's part of `parts[2]` (the rest), which is written back intact. So this is actually correct for well-formed files.

However, if the opening `---` is preceded by content (e.g., a BOM was stripped but whitespace remains), `parts[0]` would be non-empty and is silently discarded on line 167: `"---" + yaml_section + "---" + parts[2]`. Any content before the first `---` is lost.

**How to trigger:** A tracking file with leading whitespace or content before the `---` delimiter.

**Suggested fix:** Preserve `parts[0]` in the reconstruction: `parts[0] + "---" + yaml_section + "---" + parts[2]`.

---

## 3. kanban.py (lines 240-370)

### DA-012: `check_wip_limit` reads every `.md` file in `stories/`, including non-tracking files

**File:** `scripts/kanban.py:258`
**Severity:** Low

`stories_dir.glob("*.md")` matches all markdown files, not just tracking files. If someone puts a `README.md` or `NOTES.md` in the stories directory, `read_tf()` would parse it, find no frontmatter, and return a default TF with `status="todo"` and `implementer=""`. These defaults would not match the `dev` status or the implementer name, so they'd be harmlessly skipped. Not a functional bug, but it wastes I/O parsing non-tracking files.

**Suggested fix:** No change needed. Documenting for completeness.

### DA-013: `check_wip_limit` compares stories by `tf.story` string, not by file path

**File:** `scripts/kanban.py:260-262`
**Severity:** Low

The check `other.story != tf.story` compares story ID strings. If `tf.story` is empty (malformed tracking file), every other file with an empty story ID would match, and none would be excluded. This could produce a false positive WIP limit block. In practice, `do_transition` is only called after `find_story` succeeds, so `tf.story` is always set. But a direct API call to `check_wip_limit` with an empty-story TF would behave unexpectedly.

**Suggested fix:** Return `None` early if `tf.story` is empty.

### DA-014: `_count_review_rounds` uses a literal Unicode arrow, fragile against body edits

**File:** `scripts/kanban.py:276`
**Severity:** Medium

The function searches for `"review → dev"` (with a Unicode right arrow `→`, U+2192). The transition log is written on line 336 as `f"- {timestamp}: {old_status} → {target}"` — also using `→`. So the match is consistent *within this code*. But if a human edits the tracking file and uses `->` or `-->` instead, or if `sync_tracking.py` writes transitions with different formatting, the count would be wrong, and the review round escalation limit would not trigger.

**How to trigger:** Manually edit a tracking file's transition log to use `->` instead of `→`.

**Suggested fix:** Match both patterns: `r"review (→|->|-->|->) dev"`, or normalize the search.

### DA-015: `do_transition` appends log entry with `.rstrip()` but does not ensure trailing newline

**File:** `scripts/kanban.py:337-341`
**Severity:** Low

When appending to an existing transition log (line 338), `tf.body_text.rstrip() + "\n" + log_entry` strips all trailing whitespace then adds one newline before the entry. This works. But the result has no trailing newline after the log entry. When `write_tf()` is called, it does `tf.body_text.strip()` (line 1138 of validate_config.py), which strips the trailing content, then appends `""` to `lines` (adding a final newline). So the file is well-formed. No bug.

**Revised:** Retracted.

### DA-016: `do_transition` rollback restores `tf.body_text` but the `.tmp` file may linger

**File:** `scripts/kanban.py:342-368`
**Severity:** Low

`atomic_write_tf` writes to `tf.path.with_suffix(".tmp")` then renames. If the rename on line 153 succeeds (the main write), but the GitHub sync fails, the rollback calls `atomic_write_tf` again, which writes a new `.tmp` and renames. This works correctly — no stale `.tmp` files.

But if `atomic_write_tf` itself fails on the *rollback* write (the `except Exception as rollback_exc` path at line 359), a `.tmp` file from the rollback attempt could linger. This is noted in the error message but not cleaned up.

**How to trigger:** Disk full during rollback write.

**Suggested fix:** Best-effort cleanup of the `.tmp` file in the rollback exception handler.

### DA-017: `do_transition` does not hold lock — caller must lock

**File:** `scripts/kanban.py:280-368`
**Severity:** Medium (documentation/API design)

`do_transition` mutates `tf` and writes to disk but does not acquire a lock itself. The CLI's `main()` correctly acquires `lock_story()` before calling `do_transition`. But `do_transition` is a public API function — any caller that forgets to lock will have a race condition. The WIP limit check (which reads other stories' files) is especially vulnerable: between the check and the write, another process could transition a different story into dev.

**How to trigger:** Call `do_transition` from code (not CLI) without acquiring `lock_story` first.

**Suggested fix:** Either have `do_transition` acquire the lock internally, or add a prominent docstring warning. Currently the docstring does not mention locking.

### DA-018: `check_wip_limit` does not hold sprint lock — TOCTOU with concurrent transitions

**File:** `scripts/kanban.py:243-270`
**Severity:** Medium

`check_wip_limit` reads all story files in the sprint to count how many are in `dev`. But the CLI only acquires `lock_story` (per-story lock), not `lock_sprint` (sprint-wide lock). Two concurrent transitions for different stories by the same implementer could both pass the WIP check simultaneously because each reads the other's pre-transition state.

Sequence:
1. Process A: `check_wip_limit` for story X — reads all files, sees 0 in dev. Passes.
2. Process B: `check_wip_limit` for story Y — reads all files, sees 0 in dev. Passes.
3. Process A: writes story X status to `dev`.
4. Process B: writes story Y status to `dev`.

Now the implementer has 2 stories in dev, violating the WIP limit of 1.

**How to trigger:** Two concurrent `kanban.py transition` commands for different stories by the same persona.

**Suggested fix:** Use `lock_sprint` instead of `lock_story` when transitioning to dev, or re-check WIP after acquiring the story lock and before writing.

---

## 4. risk_register.py

### DA-019: `_parse_rows` skips the header row by checking `cells[0] not in ("ID", "---")` but does not skip separator rows reliably

**File:** `scripts/risk_register.py:55-64`
**Severity:** Medium

Line 55 skips lines where the stripped line starts with `|--`. But the actual TOML template on line 29 has `|----|---...`, which starts with `|----` — `line.strip().startswith("|--")` matches this correctly because `"|----"` starts with `"|--"`.

However, the `cells[0] not in ("ID", "---")` check on line 64 is redundant with the separator check and uses `"---"` as a sentinel. A cell containing exactly `---` would be skipped, but separator lines have cells like `----`, not `---`. If a row somehow had a cell with value `---` (unlikely), it would be silently dropped. The real issue: the `"ID"` check matches the header row but is case-sensitive. A header with `id` (lowercase) would be parsed as data. Not a practical concern since the template uses uppercase `ID`.

**Suggested fix:** No change needed — works for the template format. Documenting for completeness.

### DA-020: `resolve_risk` reconstructs the table row without preserving original column alignment

**File:** `scripts/risk_register.py:108`
**Severity:** Low

`lines[i] = "| " + " | ".join(cells) + " |"` rebuilds the row from the parsed cells. This loses any original padding/alignment. If the table was manually formatted with aligned columns, resolve_risk would break the visual alignment. Not a functional bug but degrades readability.

**Suggested fix:** Accept this as a trade-off, or pad cells to original widths.

### DA-021: `resolve_risk` does not escape `|` in the resolution text

**File:** `scripts/risk_register.py:107`
**Severity:** High

`cells[6] = resolution` sets the resolution text directly into the cell array, which is then joined with ` | `. If the resolution text contains a literal pipe character `|`, the reconstructed row will have too many columns, corrupting the table structure.

Compare with `add_risk` on line 81: `title = title.replace("|", "\\|")` — the title is escaped, but the resolution is not.

**How to trigger:** `risk_register.py resolve_risk --id R1 --resolution "fixed | workaround applied"`. The resulting row would have 8+ columns instead of 7, breaking all subsequent parsing.

**Suggested fix:** Add `resolution = resolution.replace("|", "\\|")` before `cells[6] = resolution`.

### DA-022: `_parse_rows` does not unescape `\|` when parsing cells

**File:** `scripts/risk_register.py:58`
**Severity:** Medium

`add_risk` escapes pipes in titles as `\|` (line 81), but `_parse_rows` uses `line.split("|")` which splits on *all* pipe characters including escaped ones. A title like `risk A \| risk B` would be split into two cells: `risk A \` and ` risk B`.

This means:
1. The title would be truncated to `risk A \`.
2. All subsequent cell indices would be shifted by one.
3. The row might now have 8 cells, and the parser would read incorrect values for severity, status, raised, etc.

**How to trigger:** `risk_register.py add_risk --title "risk A | risk B" --severity high`. The add succeeds (pipe is escaped to `\|`), but subsequent reads via `_parse_rows` or `resolve_risk` corrupt the data.

**Suggested fix:** Use a pipe-aware split that respects `\|` escapes. For example: `re.split(r'(?<!\\)\|', line)` to split on unescaped pipes, then unescape cells with `.replace("\\|", "|")`.

### DA-023: `_next_id` can produce duplicate IDs after `resolve_risk` modifies the file

**File:** `scripts/risk_register.py:42-48`
**Severity:** Low

`_next_id` scans the entire file for `R\d+` patterns in table cells. Since resolved risks remain in the table (they just get status "Resolved"), their IDs are still counted. So new IDs are always monotonically increasing. This is correct.

However, if someone manually deletes a risk row from the file, and then another risk is added, the ID counter could reuse a deleted ID if the deleted ID was the highest. For example: delete R5, then `_next_id` finds R4 as the max, and assigns R5 to the next risk. If external systems reference the old R5, this creates ambiguity.

**How to trigger:** Manually delete the highest-numbered risk row, then add a new risk.

**Suggested fix:** Accept this as known behavior, or add a comment noting that IDs should never be reused and rows should not be deleted.

### DA-024: `_parse_rows` requires `len(cells) >= 6` but accesses `cells[6]` unconditionally in the dict

**File:** `scripts/risk_register.py:64-73`
**Severity:** Low

Line 64 checks `len(cells) >= 6`, but line 72 accesses `cells[6]` with a guard: `cells[6] if len(cells) > 6 else ""`. This is correct — the `>` vs `>=` distinction means `cells[6]` is only accessed when there are 7+ cells. However, a row with exactly 6 cells (missing the Resolution column entirely) would be parsed with `resolution: ""`. This is acceptable behavior.

**Revised:** Not a bug. Retracted.

### DA-025: `escalate_overdue` uses `> threshold` not `>= threshold`

**File:** `scripts/risk_register.py:132`
**Severity:** Low

`if sprints > threshold` means that with the default threshold of 2, a risk must be open for 3+ sprints to be flagged as overdue. The CLI help says `--threshold 2` and the docstring says "open longer than threshold sprints." The behavior matches the description ("longer than" = strictly greater than), but users might intuitively expect a threshold of 2 to flag risks open for 2 sprints. This is a design choice, not a bug, but worth documenting.

**Suggested fix:** Clarify in the `--help` text: "Flag risks open for MORE than N sprints (default: 2, flags at 3+)."

### DA-026: `add_risk` does not validate severity input when called as library function

**File:** `scripts/risk_register.py:77`
**Severity:** Low

The CLI validates severity via `choices=["high", "medium", "low", "critical"]` (line 148), but the `add_risk()` function itself accepts any string. A library caller could pass `severity="banana"` and it would be written to the register. Not a practical concern since the CLI is the primary interface.

**Suggested fix:** Add validation inside `add_risk()` for defense-in-depth.

---

## Summary by Severity

| Severity | Count | IDs |
|----------|-------|-----|
| High | 2 | DA-021, DA-022 |
| Medium | 6 | DA-001, DA-005, DA-007, DA-010, DA-017, DA-018 |
| Low | 7 | DA-003, DA-004, DA-006, DA-009, DA-011, DA-016, DA-020, DA-023, DA-025, DA-026 |

### Top 3 Findings (actionable, high-impact)

1. **DA-021 + DA-022**: `risk_register.py` pipe escaping is asymmetric. `add_risk` escapes `|` in titles, but `resolve_risk` does not escape `|` in resolutions, and `_parse_rows` does not handle `\|` escapes during parsing. Together these create a data-corruption round-trip: adding a risk with a pipe in the title, then resolving it, produces a broken table.

2. **DA-018**: `check_wip_limit` in `kanban.py` is vulnerable to TOCTOU — concurrent transitions for different stories can both pass the WIP check, violating the limit. The per-story lock is insufficient; a sprint-level lock is needed when checking cross-story constraints.

3. **DA-007 + DA-010**: `_read_toml_key` in `verify_agent_output.py` does not handle inline comments or single-quoted strings. The main parser in `validate_config.py` handles both, but this lightweight copy diverges. If a user's `project.toml` uses either pattern, the verification hook silently gets wrong values or empty command lists.
