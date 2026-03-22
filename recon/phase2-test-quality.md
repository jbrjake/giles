# Phase 2 -- File System + State Machine Boundary Audit (Pass 39)

**Date:** 2026-03-21
**Scope:** TF round-trip, SPRINT-STATUS.md contract, kanban/sync_tracking divergence, lock lifecycle, directory creation, atomic writes.
**Method:** Static analysis, tracing data flows through all read/write paths.

## Summary

| Category | Count |
|----------|-------|
| Findings total | 5 |
| HIGH severity | 0 |
| MEDIUM severity | 2 |
| LOW severity | 3 |

---

## Findings

### BH39-100: tracking-formats.md falsely claims sync paths do not append transition log entries (MEDIUM)
**Seam:** `tracking-formats.md` documentation <-> `kanban.py append_transition_log` <-> `sync_tracking.py sync_one` <-> `kanban.py do_sync`
**Evidence:**
- `skills/sprint-run/references/tracking-formats.md:85` states: "External transitions via `do_sync` or `sync_tracking` do not currently append log entries."
- `kanban.py:537` and `kanban.py:549`: `append_transition_log(tf, old, ...)` is called in `do_sync` for both closed-issue forced transitions and validated external transitions.
- `sync_tracking.py:146`: `append_transition_log(tf, old_status, gh_status, "external: GitHub sync")` is called in `sync_one`.
- All three paths tag entries with `"external: GitHub sync"`.
**Impact:** A developer reading tracking-formats.md would believe external syncs leave no log trail, and might add logging code that duplicates what already exists. More critically, `_count_review_rounds` (kanban.py:306) counts `review -> dev` transitions in the log. If a developer assumes sync doesn't write log entries and doesn't account for externally-logged `review -> dev` transitions, the 3-round escalation limit could trigger unexpectedly.
**Suggested fix:** Update tracking-formats.md:84-85 to: "Log entries are rolled back if the GitHub sync fails. External transitions via `do_sync` and `sync_tracking` append log entries tagged with `(external: GitHub sync)`."

### BH39-101: assign_dod_level.py uses non-atomic write_tf under lock_sprint (LOW)
**Seam:** `assign_dod_level.py` <-> `write_tf()` <-> concurrent readers (e.g., `do_status`)
**Evidence:**
- `scripts/assign_dod_level.py:59` calls `write_tf(tf)` directly.
- Every other production writer (`kanban.py do_transition`, `do_assign`, `do_update`, `do_sync`, `sync_tracking.py`) calls `atomic_write_tf(tf)` which writes to a `.tmp` file then renames.
- `kanban.py:662-663` (`do_status`) reads tracking files without holding any lock.
**Impact:** A `do_status` read concurrent with `assign_dod_level` write could see a partially-written tracking file. `read_tf` handles malformed files gracefully (returns default TF with empty `story`), so the effect is a momentary garbled status display, not data corruption. The window is very small (milliseconds during file write).
**Suggested fix:** Replace `write_tf(tf)` with `atomic_write_tf(tf)` in `assign_dod_level.py:59`. Import `atomic_write_tf` from `kanban` (already imported for `lock_sprint`).

### BH39-102: update_burndown writes SPRINT-STATUS.md non-atomically without locks (LOW)
**Seam:** `update_burndown.update_sprint_status()` <-> `release_gate.do_release()` <-> `detect_sprint()`
**Evidence:**
- `skills/sprint-run/scripts/update_burndown.py:85-113`: Reads SPRINT-STATUS.md, modifies the Active Stories section via regex replacement, writes the entire file back with `status_file.write_text(...)`.
- `skills/sprint-release/scripts/release_gate.py:710`: Appends a row using `open(status_file, "a")`.
- Neither uses locks. Neither uses `atomic_write_text`.
- If both run simultaneously (extremely unlikely in practice -- they serve different sprint phases), the append from `release_gate` could be lost because `update_burndown` overwrites the entire file.
**Impact:** SPRINT-STATUS.md is a display-only file, not critical state. A lost release row is easily noticed and re-added. The "Current Sprint:" line (consumed by `detect_sprint`) is never modified by either writer, so sprint detection is unaffected.
**Suggested fix:** Use `atomic_write_text` in `update_sprint_status`. No lock needed given the phase separation between these writers.

### BH39-103: sync_tracking can set states that violate kanban preconditions, leaving stale metadata (MEDIUM)
**Seam:** `sync_tracking.py sync_one` <-> `kanban.py check_preconditions` <-> TF field semantics
**Evidence:**
- `sync_tracking.py:143-150`: Accepts any valid kanban state from GitHub labels without validating transitions or preconditions. If someone manually changes a GitHub label from `kanban:review` to `kanban:todo`, `sync_one` sets `tf.status = "todo"` while leaving `implementer`, `reviewer`, `branch`, `pr_number` populated from the prior dev cycle.
- `kanban.py check_preconditions:89-129`: Only enforces entry preconditions (e.g., `implementer` must be set for `design`). It does NOT enforce that a `todo` story should have empty fields.
- Subsequent kanban transitions would work (the extra fields are harmless), but the story would carry stale metadata from a prior cycle.
**Impact:** The stale fields (`branch`, `pr_number`) on a reset-to-`todo` story could confuse the implementer or reviewer subagents, who might reference an old branch/PR. `do_status` would display stale persona assignments. Functionally, the kanban state machine works correctly because preconditions only check forward-entry requirements, not invariants.
**Suggested fix:** Document this as expected behavior in the "Two-path state management" section of CLAUDE.md. Optionally, `sync_one` could clear `branch`/`pr_number`/`started`/`completed` when the status regresses to `todo`, but this changes the semantics (currently sync_tracking only adds/updates metadata, never removes it).

### BH39-104: lock_story is dead code in production (LOW)
**Seam:** `kanban.py lock_story` <-> production callers
**Evidence:**
- `kanban.py:163-177` defines `lock_story()`.
- Per BH35-001/BH35-004 (documented at `kanban.py:777-780`), all production mutation paths were moved from `lock_story` to `lock_sprint` to prevent concurrent clobbering between kanban.py and sync_tracking.py.
- Grep for `lock_story` in production code: zero callers. Only test code (`tests/test_kanban.py:278-318`) and the definition itself.
- The function is still exported (used by tests), but the docstring doesn't indicate it's deprecated.
**Impact:** No functional impact. The dead code adds maintenance burden and could confuse someone who thinks it should be used instead of `lock_sprint`. The tests that exercise `lock_story` are testing unused code paths.
**Suggested fix:** Add a deprecation note to the `lock_story` docstring: "Deprecated: all production mutations now use lock_sprint (BH35-001). Retained for backward compatibility and testing."

---

## Clean (verified correct)

### A. TF dataclass round-trip integrity -- CLEAN
- **Every TF field** is correctly serialized by `write_tf()` and deserialized by `read_tf()`. All string fields pass through `_yaml_safe()` for quoting on write and `frontmatter_value()` for unquoting on read. The `sprint` field (int) is written as a bare integer and parsed with `int()`. The `status` field is written bare (always a safe kanban slug) and read back correctly. The `body_text` field round-trips with minor whitespace normalization (`.strip()` on write, captures with leading newline on read) that is stable across cycles.
- **`_yaml_safe()` escape handling** is correct: escapes `\` before `"` (preventing double-escape of `\"`), then escapes `\n`, `\r`, `\t`. The `frontmatter_value()` unescape uses a single-pass regex with a lookup map, correctly reversing all escape sequences. Traced manually with: colons, embedded quotes, backslashes, newlines, tabs, YAML boolean keywords, numeric strings, leading/trailing whitespace, and compound cases (backslash-before-newline, quotes-inside-quoted-string). All round-trip correctly.
- **Unknown frontmatter fields** are silently dropped on `read_tf` (only TF-known fields are parsed). This is by design: TF defines the schema. Extra fields from manual edits are lost on next `write_tf`. Documented as expected behavior.
- **Verified at:** `scripts/validate_config.py:1066-1096` (_yaml_safe), `scripts/validate_config.py:926-951` (frontmatter_value), `scripts/validate_config.py:1100-1128` (read_tf), `scripts/validate_config.py:1145-1165` (write_tf).

### B. SPRINT-STATUS.md contract -- CLEAN
- **`detect_sprint()` returns `int | None`.** Verified that ALL callers handle `None`:
  - `kanban.py:740-743`: checks `sprint is None`, prints error, exits.
  - `sprint_analytics.py:225-233`: checks `sprint_num is None`, prints error, exits.
  - `check_status.py:516-524`: checks `sprint_num is None`, prints error, exits.
  - `assign_dod_level.py:76-79`: checks `sprint is None`, prints error, exits.
  - `gap_scanner.py:180-183`: checks `sprint is None`, prints error, exits.
- **SPRINT-STATUS.md writers**: `update_burndown.update_sprint_status()` only patches the Active Stories table (never touches `Current Sprint:` line). `release_gate.do_release()` only appends to EOF. Neither can corrupt the `detect_sprint` regex target.
- **Format consistency**: The template in `tracking-formats.md:10` matches the `detect_sprint` regex `r"Current Sprint:\s*(\d+)"`. The file is created by the LLM following the template, which is a mild fragility (case-sensitivity), but has been flagged in prior audits (pass 17) and accepted as low-risk given the explicit template.
- **Verified at:** `scripts/validate_config.py:959-968`, all caller sites listed above, `skills/sprint-run/references/tracking-formats.md:10`.

### C. kanban.py <-> sync_tracking.py lock coordination -- CLEAN
- **Both paths hold `lock_sprint`** for all mutations. `kanban.py main()` acquires `lock_sprint` at lines 757, 782, 797, 803. `sync_tracking.py main()` acquires `lock_sprint` at line 288. No path exists where either script writes a tracking file without holding `lock_sprint`.
- **No deadlock potential**: Neither script holds two locks simultaneously. `lock_sprint` is the sole lock used in production. `lock_story` is dead code (BH39-104).
- **Transition log consistency**: Both paths call the same `append_transition_log` function (imported by sync_tracking from kanban). External transitions are tagged with `"external: GitHub sync"`. The `_count_review_rounds` regex correctly matches these entries.
- **Verified at:** `kanban.py:180-194` (lock_sprint), `kanban.py:757,782,797,803` (callers), `sync_tracking.py:288` (caller), `kanban.py:309-320` (append_transition_log).

### D. Lock file lifecycle -- CLEAN
- **Directory creation**: `lock_sprint` calls `lock_file.touch(exist_ok=True)` which requires the parent directory to exist. All callers ensure `sprint_dir` exists before calling `lock_sprint` (via explicit `mkdir` or by finding files in the directory first).
- **Stale locks**: `fcntl.flock()` is a process-level advisory lock on the file descriptor, not the file itself. When a process dies, the OS closes all file descriptors, automatically releasing the lock. No stale lock problem exists.
- **Lock file cleanup**: `.kanban.lock` sentinel files persist in the sprint directory. This is by design -- they are empty sentinel files that take negligible space. Story-level `.lock` files (from dead `lock_story`) are cleaned up during `--prune` operations (`kanban.py:598-599`).
- **Verified at:** `kanban.py:180-194`, all caller mkdir paths documented in finding BH39-101.

### E. Directory creation contracts -- CLEAN
- **`sprint-{N}/stories/`**: Created by `kanban.py do_sync:507` (`stories_dir.mkdir(parents=True, exist_ok=True)`) and `sync_tracking.py main:252`. Also created defensively by `atomic_write_tf:147` and `write_tf:1164` (via `tf.path.parent.mkdir`).
- **`sprint-{N}/`**: Created by `kanban.py main:751` (for sync), `sync_tracking.py main:252` (as parent of stories/), `update_burndown.write_burndown:42`, and defensively by atomic write paths.
- **No script assumes a directory exists without creation**: Every writer creates parents with `parents=True, exist_ok=True`. The `find_story` function at `kanban.py:212` returns `None` if the directory doesn't exist (graceful degradation).
- **Verified at:** All `mkdir` calls listed in the grep results.

### F. Atomic write correctness -- CLEAN
- **Same-filesystem guarantee**: Both `atomic_write_tf` (kanban.py:148) and `atomic_write_text` (validate_config.py:1139) create the temp file via `path.with_suffix(".tmp")`, which produces a path in the **same directory** as the target. `os.rename()` on POSIX is atomic within a filesystem. Since temp and target are in the same directory, they are on the same filesystem.
- **Temp file already exists**: `write_text` overwrites any existing `.tmp` file. `os.rename` overwrites the target. Both are safe.
- **Partial write on disk full**: If `write_text` raises mid-write, `os.rename` never executes, leaving the original file intact. The partial `.tmp` file is harmless (overwritten on next write).
- **Verified at:** `kanban.py:137-153` (atomic_write_tf), `validate_config.py:1132-1141` (atomic_write_text).
