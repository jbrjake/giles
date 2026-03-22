# Phase 3 — Adversarial Code Audit

**Pass:** BH38
**Date:** 2026-03-21
**Focus:** Error paths, boundaries, state transitions, data integrity, security
**Files audited:** validate_config.py, kanban.py, sync_tracking.py, release_gate.py, sprint_init.py, commit_gate.py, review_gate.py, session_context.py, verify_agent_output.py, _common.py, sprint_teardown.py

---

## Findings

### BH38-200 — lock_sprint fails on nonexistent sprint directory in kanban.py sync
**Severity:** MEDIUM
**File:** scripts/kanban.py:750-756
**Phase:** Phase 3 (adversarial)
**Description:** `kanban.py sync` calls `lock_sprint(sprint_dir)` where `sprint_dir = sprints_dir / f"sprint-{sprint}"`. Inside `lock_sprint`, `lock_file.touch(exist_ok=True)` is called, which raises `FileNotFoundError` if `sprint_dir` does not exist. `sync_tracking.py` avoids this by creating `stories_dir` (and implicitly `sprint_dir`) with `mkdir(parents=True)` BEFORE calling `lock_sprint`. `kanban.py sync` does not — `do_sync` creates the directory inside the lock, but the lock acquisition itself fails first.

**Trigger:** Run `kanban.py sync --sprint N` where sprint-N directory has never been created.

**Fix:** Add `sprint_dir.mkdir(parents=True, exist_ok=True)` before the `with lock_sprint(sprint_dir):` call at line 756, matching how sync_tracking.py does it.

---

### BH38-201 — commit_gate false-positive verification from non-test commands
**Severity:** MEDIUM
**File:** .claude-plugin/hooks/commit_gate.py:182-188
**Phase:** Phase 3 (adversarial)
**Description:** `_matches_check_command` matches only the first word of a configured check_command against the full command string. If `check_commands = ["python -m pytest"]`, then `cfg_cmd.split()[0]` is `"python"`, and any command containing `\bpython\b` (e.g., `python myscript.py`, `python -c "print(1)"`) would match. This marks the working tree as "verified", allowing commits through the gate without tests actually running.

The word-boundary fix (BH35-010) prevents substring matches like "cpython" but does not prevent matching the wrong invocation of the same binary.

**Trigger:** Configure `check_commands = ["python -m pytest"]`. Run `python some_script.py` successfully. The commit gate now considers tests as having been run.

**Fix:** Match the full configured command (all words), not just the first word. For example, check if all space-separated tokens of `cfg_cmd` appear in order in the command string, or use a more restrictive prefix match.

---

### BH38-202 — verify_agent_output _has_unquoted_bracket lacks nesting depth tracking
**Severity:** LOW
**File:** .claude-plugin/hooks/verify_agent_output.py:84-106
**Phase:** Phase 3 (adversarial)
**Description:** The `_has_unquoted_bracket` function in verify_agent_output.py returns `True` on the first `]` found outside quotes, without tracking bracket nesting depth. In contrast, the equivalent `_has_closing_bracket` in validate_config.py (lines 255-277) correctly tracks `depth` for nested brackets.

This means a TOML array value like `check_commands = ["a", ["b"]]` would incorrectly terminate parsing at the inner `]` when using `_read_toml_key`, producing a truncated array.

**Trigger:** Configure `check_commands = ["cmd1", ["nested"]]` in project.toml and invoke verify_agent_output.

**Impact:** Low in practice — project.toml arrays are flat (no nested arrays). But the inconsistency between the two parsers is a maintenance risk.

**Fix:** Add bracket depth tracking to `_has_unquoted_bracket`, matching the logic in validate_config.py's `_has_closing_bracket`.

---

### BH38-203 — verify_agent_output writes tracking files without locking
**Severity:** LOW
**File:** .claude-plugin/hooks/verify_agent_output.py:254-278
**Phase:** Phase 3 (adversarial)
**Description:** `update_tracking_verification` reads a tracking file, modifies its YAML frontmatter, and writes it back with `p.write_text()`. This is:
1. Not atomic (uses `write_text` instead of `atomic_write_tf`'s temp-then-rename)
2. Not locked (no `lock_sprint` or `lock_story`)

If a concurrent `kanban.py` transition or `sync_tracking.py` sync writes to the same file, either write could be lost.

**Trigger:** SubagentStop hook fires while kanban.py or sync_tracking.py is writing to the same tracking file.

**Impact:** Low in practice — the SubagentStop hook typically runs after agent completion, which doesn't overlap with kanban mutations. The written field (`verification_agent_stop`) is also not read by kanban.py or sync_tracking.py.

**Fix:** Use `lock_sprint` and `atomic_write_tf` (or at minimum the atomic write pattern) for tracking file updates.

---

### BH38-204 — review_gate _log_blocked has no path traversal check on sprints_dir
**Severity:** LOW
**File:** .claude-plugin/hooks/review_gate.py:197-220
**Phase:** Phase 3 (adversarial)
**Description:** `_log_blocked` reads `sprints_dir` from project.toml and constructs `root / sprints_dir` at line 215, then creates directories with `mkdir(parents=True)` and writes a log file. If `sprints_dir` contains `../../../tmp/evil`, the function would create directories and write files outside the project root.

Unlike `sprint_init.py`'s `_symlink` method (which has BH18-014 defense checking `target_abs.relative_to(self.root)`), this path is not validated against the project root.

**Trigger:** Set `sprints_dir = "../../somewhere"` in project.toml, then trigger a blocked push/merge.

**Impact:** Low — the attacker must control project.toml, and the written content is a benign audit log. But inconsistent with the defense-in-depth approach.

**Fix:** Resolve `root / sprints_dir` and verify it's within `root` before writing.

---

### BH38-205 — sync_tracking.py uses unguarded dict key (relies on extract_story_id always returning uppercase)
**Severity:** LOW
**File:** skills/sprint-run/scripts/sync_tracking.py:292-297
**Phase:** Phase 3 (adversarial)
**Description:** The `existing` dict is built with `tf.story.upper()` as keys (line 271). At line 292, the check uses `sid.upper() in existing`, but lines 294-297 use `existing[sid]` without `.upper()`. This works only because `extract_story_id()` always returns uppercase strings (the regex matches `[A-Z]+-\d+` and the fallback path calls `.upper()`).

If `extract_story_id` were ever changed to preserve the original case (e.g., to support lowercase story IDs like `us-0001`), these dict lookups would fail with `KeyError`.

**Trigger:** Not currently triggerable — `extract_story_id` always returns uppercase. But any change to that function's case behavior would break sync_tracking.

**Fix:** Use `sid.upper()` consistently: `existing[sid.upper()] = read_tf(existing[sid.upper()].path)`.

---

### BH38-206 — session_context _parse_action_items doesn't filter all markdown separator row formats
**Severity:** LOW
**File:** .claude-plugin/hooks/session_context.py:100-104
**Phase:** Phase 3 (adversarial)
**Description:** The separator row filter checks `not line.strip().startswith("|--")` and `cells[0] not in ("Item", "---")`. This handles `|---|---|---|` rows and plain `---` cells, but misses markdown alignment variants like `| :--- |` (left-align), `| ---: |` (right-align), and `| :---: |` (center-align). These would produce cells like `:---`, `---:`, or `:---:` which are not in the filter set, causing them to appear as action items.

**Trigger:** A retro.md with `| :--- | :--- | :--- |` separator rows in the Action Items table.

**Impact:** A spurious `:---` action item injected into session context. Cosmetic but confusing.

**Fix:** Use a regex check like `re.match(r'^:?-+:?$', cell)` instead of exact string matching for separator row detection.

---

### BH38-207 — sprint_init stem collision handling doesn't handle triple collisions
**Severity:** LOW
**File:** scripts/sprint_init.py:730-739
**Phase:** Phase 3 (adversarial)
**Description:** Stem collision handling disambiguates by prefixing the parent directory name (e.g., `alice.md` in `other/` becomes `other-alice.md`). But if a third persona already has the stem `other-alice`, the disambiguated name collides with it. The code at line 738 silently overwrites the `seen_stems` entry and the symlink at line 740 overwrites the previous one.

The resulting team INDEX would list both personas with the same filename, and only the last symlink would survive.

**Trigger:** Three persona files: `docs/team/alice.md`, `other/alice.md`, `third/other-alice.md`.

**Impact:** Very low — triple stem collisions across different directories are extremely unlikely in real projects. If it occurs, one persona's symlink is silently lost.

**Fix:** After disambiguation, check again if the new stem is already in `seen_stems` and append a counter suffix (e.g., `other-alice-2.md`).

---

## Summary

| ID | Severity | File | Category |
|----|----------|------|----------|
| BH38-200 | MEDIUM | kanban.py:750 | Error path — lock on nonexistent dir |
| BH38-201 | MEDIUM | commit_gate.py:187 | False positive — overly broad command match |
| BH38-202 | LOW | verify_agent_output.py:84 | Parser inconsistency — missing depth tracking |
| BH38-203 | LOW | verify_agent_output.py:254 | Concurrency — unlocked write |
| BH38-204 | LOW | review_gate.py:215 | Security — unvalidated path |
| BH38-205 | LOW | sync_tracking.py:294 | Fragile — implicit case assumption |
| BH38-206 | LOW | session_context.py:100 | Parser — incomplete separator filter |
| BH38-207 | LOW | sprint_init.py:734 | Edge case — triple collision |

**Total: 8 findings (2 MEDIUM, 6 LOW)**

## Areas Audited With No Issues Found

- **TOML parser** (validate_config.py): Extensively tested string escaping, multiline arrays, inline comment stripping, bracket nesting, and round-trip `_yaml_safe`/`frontmatter_value`. The parser is robust for its intended subset of TOML.
- **Kanban state machine** (kanban.py): Transition validation, precondition checks, WIP limit enforcement, and review round counting are all correct. The locking strategy (lock_sprint for all mutations) eliminates TOCTOU races.
- **Release gate versioning** (release_gate.py): `bump_version`, `determine_bump`, `write_version_to_toml`, and rollback logic are correct. The `_COMMIT_DELIM` collision risk is theoretical only.
- **Review gate push detection** (review_gate.py): Correctly handles force-push prefixes, refs/heads/ paths, compound commands, --mirror/--all, and refspec targets.
- **Symlink path traversal** (sprint_init.py): The BH18-014 check in `_symlink` correctly prevents targets outside the project root.
- **Sprint teardown** (sprint_teardown.py): Correctly classifies symlinks/generated/unknown files, handles directory symlinks, and uses manifest-based classification when available.
