# CLAUDE.md Doc-to-Implementation Audit

Auditor: Holtz run 3
Date: 2026-03-23

---

## 1. Script Table — Function Existence

### scripts/validate_config.py

| Claimed function | Verdict | Evidence |
|---|---|---|
| `parse_simple_toml()` | VERIFIED | Defined at line 135 |
| `validate_project()` | VERIFIED | Defined at line 484 |
| `load_config()` | VERIFIED | Defined at line 684 |
| `safe_int()` | VERIFIED | Defined at line 34 |
| `parse_iso_date()` | VERIFIED | Defined at line 41 |
| `gh()` | VERIFIED | Defined at line 66 |
| `gh_json()` | VERIFIED | Defined at line 82 |
| `extract_sp()` | VERIFIED | Defined at line 843 |
| `get_team_personas()` | VERIFIED | Defined at line 735 |
| `get_milestones()` | VERIFIED | Defined at line 764 |
| `get_base_branch()` | VERIFIED | Defined at line 790 |
| `get_sprints_dir()` | VERIFIED | Defined at line 797 |
| `get_prd_dir()` | VERIFIED | Defined at line 803 |
| `get_test_plan_dir()` | VERIFIED | Defined at line 813 |
| `get_sagas_dir()` | VERIFIED | Defined at line 823 |
| `get_epics_dir()` | VERIFIED | Defined at line 833 |
| `get_story_map()` | VERIFIED | Defined at line 879 |
| `extract_story_id()` | VERIFIED | Defined at line 972 |
| `kanban_from_labels()` | VERIFIED | Defined at line 1003 |
| `find_milestone()` | VERIFIED | Defined at line 1169 |
| `warn_if_at_limit()` | VERIFIED | Defined at line 1214 |
| `list_milestone_issues()` | VERIFIED | Defined at line 1193 |
| `detect_sprint()` | VERIFIED | Defined at line 959 |
| `get_ci_commands()` | VERIFIED | Defined at line 780 |
| `TF` | VERIFIED | Class defined at line 1049 |
| `read_tf()` | VERIFIED | Defined at line 1100 |
| `write_tf()` | VERIFIED | Defined at line 1145 |
| `slug_from_title()` | VERIFIED | Defined at line 1038 |
| `atomic_write_text()` | VERIFIED | Defined at line 1132 |

All 29 claimed entries present. No divergence.

### scripts/kanban.py

| Claimed function | Verdict | Evidence |
|---|---|---|
| `TRANSITIONS` | VERIFIED | Dict defined at line 48 |
| `validate_transition()` | VERIFIED | Defined at line 63 |
| `check_preconditions()` | VERIFIED | Defined at line 89 |
| `check_wip_limit()` | VERIFIED | Defined at line 248 |
| `_count_review_rounds()` | VERIFIED | Defined at line 309 |
| `do_transition()` | VERIFIED | Defined at line 329 |
| `do_assign()` | VERIFIED | Defined at line 432 |
| `do_update()` | VERIFIED | Defined at line 624 |
| `do_sync()` | VERIFIED | Defined at line 495 |
| `do_status()` | VERIFIED | Defined at line 654 |
| `find_story()` | VERIFIED | Defined at line 207 |
| `atomic_write_tf()` | VERIFIED | Defined at line 137 |
| `lock_story()` | VERIFIED | Defined at line 163 |
| `lock_sprint()` | VERIFIED | Defined at line 186 |

All 14 claimed entries present. No divergence.

### scripts/sprint_init.py

| Claimed function | Verdict | Evidence |
|---|---|---|
| `ProjectScanner` | VERIFIED | Class defined at line 94 |
| `ConfigGenerator` | VERIFIED | Class defined at line 535 |
| `main()` | VERIFIED | Defined at line 991 |

### skills/sprint-setup/scripts/bootstrap_github.py

| Claimed function | Verdict | Evidence |
|---|---|---|
| `create_label()` | VERIFIED | Defined at line 45 |
| `create_persona_labels()` | VERIFIED | Defined at line 66 |
| `_collect_sprint_numbers()` | VERIFIED | Defined at line 80 |
| `create_sprint_labels()` | VERIFIED | Defined at line 111 |
| `create_saga_labels()` | VERIFIED | Defined at line 160 |
| `create_static_labels()` | VERIFIED | Defined at line 192 |
| `create_epic_labels()` | VERIFIED | Defined at line 222 |
| `create_milestones_on_github()` | VERIFIED | Defined at line 234 |
| `main()` | VERIFIED | Defined at line 307 |

### skills/sprint-release/scripts/release_gate.py

| Claimed function | Verdict | Evidence |
|---|---|---|
| `find_latest_semver_tag()` | VERIFIED | Defined at line 39 |
| `parse_commits_since()` | VERIFIED | Defined at line 60 |
| `calculate_version()` | VERIFIED | Defined at line 120 |
| `gate_stories()` | VERIFIED | Defined at line 143 |
| `gate_ci()` | VERIFIED | Defined at line 159 |
| `gate_prs()` | VERIFIED | Defined at line 184 |
| `gate_tests()` | VERIFIED | Defined at line 211 |
| `gate_build()` | VERIFIED | Defined at line 238 |
| `validate_gates()` | VERIFIED | Defined at line 260 |
| `write_version_to_toml()` | VERIFIED | Defined at line 299 |
| `generate_release_notes()` | VERIFIED | Defined at line 345 |
| `do_release()` | VERIFIED | Defined at line 455 |
| `main()` | VERIFIED | Defined at line 731 |

### scripts/smoke_test.py

| Claimed function | Verdict | Evidence |
|---|---|---|
| `run_smoke()` | VERIFIED | Defined at line 29 |
| `write_history()` | VERIFIED | Defined at line 60 |
| `main()` | VERIFIED | Defined at line 99 |

All 6 spot-checked scripts: every claimed function exists. No divergence found.

---

## 2. Required TOML Keys

**CLAUDE.md claims** (line 122):
> Required TOML keys: `project.name`, `project.repo`, `project.language`, `paths.team_dir`, `paths.backlog_dir`, `paths.sprints_dir`, `ci.check_commands`, `ci.build_command`

**Code** (`_REQUIRED_TOML_KEYS` at line 468 of validate_config.py):
```python
_REQUIRED_TOML_KEYS: list[tuple[str, ...]] = [
    ("project", "name"),
    ("project", "repo"),
    ("project", "language"),
    ("paths", "team_dir"),
    ("paths", "backlog_dir"),
    ("paths", "sprints_dir"),
    ("ci", "check_commands"),
    ("ci", "build_command"),
]
```

**Verdict: VERIFIED** -- Exact 1:1 match, same 8 keys in same order.

---

## 3. Hooks Section

**CLAUDE.md claims** (lines 20-26):
- hooks.json registers PreToolUse, PostToolUse, SubagentStop, SessionStart
- commit_gate.py: blocks commits until tests pass (PreToolUse + PostToolUse)
- review_gate.py: blocks unreviewed PR merges and direct pushes (PreToolUse)
- session_context.py: injects sprint context at session start (SessionStart)
- verify_agent_output.py: validates implementer subagent output (SubagentStop)
- _common.py: shared hook utilities (read_event, exit_ok/warn/block)

**hooks.json actual content:**

| Hook type | Scripts registered | Matcher |
|---|---|---|
| PreToolUse | review_gate.py, commit_gate.py | Bash |
| PostToolUse | commit_gate.py --post | Bash |
| SubagentStop | verify_agent_output.py | (none) |
| SessionStart | session_context.py | (none) |

**_common.py actual exports:** `read_event()`, `exit_ok()`, `exit_warn()`, `exit_block()` -- all present.

**Hook files on disk:** `_common.py`, `commit_gate.py`, `review_gate.py`, `session_context.py`, `verify_agent_output.py`, `__init__.py` -- all present.

**Verdict: VERIFIED** -- All 4 hook types match, all 4 hook scripts match their described roles, _common.py has the 3 claimed exit functions plus read_event.

---

## 4. Key Architectural Decisions

### 4a. Symlink-based config

**Claim:** `sprint_init.py` creates symlinks from `sprint-config/` to existing project files. Teardown removes symlinks without touching originals. Exception: Giles is copied (plugin-owned), not symlinked.

**Evidence:**
- `sprint_init.py` has `_symlink()` method (line 556) that calls `link_path.symlink_to(rel)` (line 580).
- Persona files, milestones, doc files all route through `_symlink()` (lines 740, 786, 805, 818, 824, 828).
- Giles uses `_inject_giles()` (line 756) which calls `_copy_skeleton("giles.md.tmpl", ...)` (line 772) -- copy, not symlink.
- The code explicitly checks `if dest.is_symlink()` for Giles (line 767) to preserve user customizations.
- `sprint_teardown.py` has `classify_entries()` which separates symlinks from generated files, and `remove_symlinks()` (line 214) handles symlink-only removal.

**Verdict: VERIFIED** -- Symlink pattern for project files, copy for Giles, teardown separates symlinks.

### 4b. Custom TOML parser

**Claim:** Minimal TOML parser (no `tomllib` dependency) supporting double-quoted strings (with escape processing including `\uXXXX` and `\UXXXXXXXX`), single-quoted literal strings, ints, bools, arrays, bare keys, and sections. Floats are not supported (returned as raw strings).

**Evidence:**
- `parse_simple_toml()` at line 135, docstring confirms strings/ints/bools/arrays/sections/comments.
- `_unescape_toml_string()` (line 280) handles `\uXXXX` (line 301) and `\UXXXXXXXX` (line 308).
- Single-quoted literal strings handled at line 348-350 in `_parse_value()`.
- No `import tomllib` anywhere in the file.
- Float handling: `int()` is tried (line 366); if it fails, value falls through to raw string (line 379). No explicit float parsing exists.

**Verdict: VERIFIED** -- All claimed features present, float limitation confirmed.

### 4c. Scripts import chain

**Claim:** Skill scripts in `skills/*/scripts/` do `sys.path.insert(0, ...)` to reach `scripts/validate_config.py` four directories up. Scripts in the top-level `scripts/` directory use a single-level parent path.

**Evidence:**
- `skills/sprint-setup/scripts/bootstrap_github.py` line 14: `sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent / "scripts"))` -- 4 levels up.
- `skills/sprint-run/scripts/sync_tracking.py` line 27: `sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent / "scripts"))` -- 4 levels up.
- `scripts/kanban.py` line 33: `sys.path.insert(0, str(Path(__file__).resolve().parent))` -- 1 level (parent directory, i.e., scripts/).

**Verdict: VERIFIED** -- Four-level path for skill scripts, single-level for top-level scripts.

### 4d. Two-path state management

**Claim:** `kanban.py` is the mutation path (local-first, syncs to GitHub on every write). `sync_tracking.py` is the reconciliation path (accepts GitHub state). Both can write `status` -- kanban validates transitions, sync_tracking accepts any valid state from GitHub.

**Evidence:**
- `kanban.py do_transition()` calls `validate_transition()` (line 350) before state change, then syncs to GitHub via `gh()` calls (lines 406-408).
- `sync_tracking.py sync_one()` (line 128) explicitly documents it "intentionally accepts ANY valid GitHub state without transition validation" (lines 133-137).
- `sync_one()` writes status directly: `tf.status = gh_status` (line 154) with only a membership check (`gh_status in KANBAN_STATES`, line 148).
- The docstring in sync_tracking.py explicitly references the "Two-path state management" section of CLAUDE.md (line 138).

**Verdict: VERIFIED** -- kanban.py validates transitions + syncs to GitHub; sync_tracking.py accepts any valid GitHub state.

### 4e. Cross-skill dependency (bonus check)

**Claim:** `scripts/sync_backlog.py` imports `bootstrap_github` and `populate_issues` from `skills/sprint-setup/scripts/`.

**Evidence:** `sync_backlog.py` lines 28-29: `import bootstrap_github` / `import populate_issues`.

**Verdict: VERIFIED** -- Imports confirmed.

---

## Summary

| Area | Claims checked | Verified | Diverged |
|---|---|---|---|
| Script function table (6 scripts) | 72 functions | 72 | 0 |
| Required TOML keys | 8 keys | 8 | 0 |
| Hooks registration | 4 hook types, 5 files | all | 0 |
| Architectural decisions | 5 claims | 5 | 0 |
| **Total** | **~90 claims** | **90** | **0** |

No divergences found. CLAUDE.md is accurate against current implementation.
