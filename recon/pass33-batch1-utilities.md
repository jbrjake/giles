# Pass 33 Batch 1: Utility Scripts Audit

## scripts/assign_dod_level.py
- BUG (minor, line 47): `counts[level] += 1` executes before the lock-protected
  check on line 49-52. If the file already has a `dod_level:` line written by a
  prior run, the count reflects the *current* classification, not the level
  actually stored in the file. If a story's keywords changed between runs, the
  printed summary will disagree with what is on disk. Fix: move the count
  increment inside the lock, reading the actual level from the file when it
  already exists.

## scripts/history_to_checklist.py
- CLEAN. Pattern matching, file iteration, and output formatting are
  straightforward with no silent failures or corruption paths.

## scripts/risk_register.py
- CLEAN. `_next_id` regex correctly requires R-IDs to fill an entire cell
  (bounded by pipes + optional whitespace). `_split_table_row` correctly handles
  escaped pipes. `resolve_risk` preserves escaping via `unescape=False`. Atomic
  writes use temp+rename. No issues found.

## scripts/smoke_test.py
- BUG (line 87): `write_history` interpolates the raw `command` string into a
  markdown table row without escaping pipe characters. Commands containing `|`
  (e.g., `cargo test 2>&1 | head -20`) produce a row with extra columns,
  corrupting the `smoke-history.md` table for all subsequent reads. Fix: escape
  `|` as `\|` in the command string before interpolation, or wrap the command
  value so pipes are neutralized (the backtick wrapping alone does not prevent
  table parsing breakage).

## scripts/team_voices.py
- BUG (minor, line 64+27): `VOICE_PATTERN` matches lines where the text after
  `**Name:**` is entirely whitespace, e.g., `> **Bob:**    `. The `(.+?)`
  non-greedy group captures a single space, and `\s*$` eats the rest. The
  `.strip()` on line 68 reduces this to an empty string, producing a voice entry
  with an empty quote. Not a crash, but creates ghost entries in the index.
  Fix: add a guard `if not quote:` after strip to skip empty results, or change
  the unquoted group to `(\S.+?)`.

## scripts/commit.py
- CLEAN. CC_RE correctly validates conventional commit format. Scope character
  class `[a-zA-Z0-9_.-]` handles dots and dashes as intended (dash is literal
  at end of class). Atomicity check correctly identifies top-level directories.
  Dry-run exits before commit. No silent failures.
