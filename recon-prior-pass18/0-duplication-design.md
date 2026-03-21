# Audit: Duplication, Dead Code, and Design Inconsistencies

Scope: all 19 Python scripts in `scripts/` and `skills/*/scripts/`.

---

## 1. Duplicated Functionality

### 1A. `_parse_header_table` — copy-pasted across 2 files [MEDIUM]

`manage_epics.py:70` and `manage_sagas.py:65` both define `_parse_header_table(lines)` with nearly identical logic: iterate lines, match `TABLE_ROW`, collect field/value pairs, stop at `###` (epics) or `##` (sagas). The only difference is the stop condition (`###` vs `##`).

Both also define the identical `TABLE_ROW` regex:
- `manage_epics.py:23`: `TABLE_ROW = re.compile(r'^\|\s*(.+?)\s*\|\s*(.+?)\s*\|')`
- `manage_sagas.py:22`: `TABLE_ROW = re.compile(r'^\|\s*(.+?)\s*\|\s*(.+?)\s*\|')`
- `traceability.py:24`: `TABLE_ROW = re.compile(r'^\|\s*(.+?)\s*\|\s*(.+?)\s*\|')`

Three scripts define the exact same regex. This is the most clear-cut duplication in the codebase.

### 1B. `STORY_HEADING` regex — defined twice [LOW]

- `manage_epics.py:22`: `STORY_HEADING = re.compile(r'^(###\s+(US-\d+):\s*(.+))')`
- `traceability.py:23`: `STORY_HEADING = re.compile(r'^###\s+(US-\d+):\s*(.+)')`

Slightly different (manage_epics has an outer capture group), but matching the same content. These serve different purposes (parsing vs. tracing), so co-location would be awkward, but the pattern itself is project-level knowledge that could live in `validate_config.py`.

### 1C. `check_prerequisites` — 3 independent implementations [LOW]

- `bootstrap_github.py:18` — checks gh version, gh auth, git remote (most thorough)
- `populate_issues.py:37` — checks gh auth only
- `setup_ci.py:339` — checks git rev-parse only

Each checks a different subset. These could share a common base, but the different requirements per script make full dedup tricky. The inconsistency is more noteworthy than the duplication.

### 1D. Milestone query — re-implemented in `check_status.py` instead of reusing `find_milestone` [MEDIUM]

`validate_config.py:880` provides `find_milestone(sprint_num)` which queries milestones and matches by regex `^Sprint 0*{num}\b`.

But `check_status.py` does its own milestone query in two places:
- `check_status.py:174-184` (in `check_milestone`) — queries milestones API directly, matches with `^Sprint {sprint_num}\b` (missing `0*` for leading-zero tolerance)
- `check_status.py:392-398` (in `main`) — queries milestones API again for sprint start date, same regex without `0*`

This means:
1. Two extra API calls that `find_milestone` would have handled
2. Missing leading-zero tolerance (the `0*` in validate_config's regex) — `check_status` will fail to find "Sprint 07" when looking for sprint 7

### 1E. `find_milestone_number` vs `find_milestone` — overlapping but different [LOW]

- `validate_config.py:880` `find_milestone(sprint_num)` — finds milestone by sprint number, returns full dict
- `release_gate.py:416` `find_milestone_number(milestone_title)` — finds milestone by title, returns number

These serve different lookup directions (number->dict vs title->number) so they aren't true duplicates, but they both independently query the milestones API with identical calls. A shared "fetch all milestones" function would eliminate the redundancy.

### 1F. SP counting — `_count_sp` in check_status vs `compute_velocity` in sprint_analytics [LOW]

- `check_status.py:212` `_count_sp(issues)` — loops issues, sums `extract_sp()`, returns `(total, done)`
- `sprint_analytics.py:40` `compute_velocity(milestone_title)` — fetches issues, loops them, sums `extract_sp()`, returns dict

Both count story points from issue lists using `extract_sp()`. The analytics version fetches its own data; check_status receives issues as a parameter. The actual SP-counting loop is duplicated.

### 1G. Frontmatter value parsing — `_fm_val` in update_burndown vs `v()` closure in sync_tracking [MEDIUM]

- `update_burndown.py:144` `_fm_val(frontmatter, key)` — regex match, unquote
- `sync_tracking.py:162-171` `v(k)` closure inside `read_tf()` — regex match, unquote

Both parse YAML-ish frontmatter keys with identical regex and quote-stripping logic. The update_burndown version exists because it needs to read tracking metadata without importing the full sync_tracking module, but the parsing logic is duplicated. The unescape order (quotes then backslashes) must stay in sync between them — a latent maintenance risk.

### 1H. `sync_backlog.py` does NOT duplicate `populate_issues.py` [CONFIRMED OK]

`sync_backlog.py` explicitly imports and calls `bootstrap_github.create_milestones_on_github()` and `populate_issues.parse_milestone_stories()` / `create_issue()`. This is intentional reuse, documented as a design decision in CLAUDE.md. No duplication here.

### 1I. `check_status.py` does NOT duplicate `sync_tracking.py` [CONFIRMED OK]

These scripts have different responsibilities: `check_status.py` monitors CI/PRs/milestone progress for alerts, while `sync_tracking.py` reconciles local tracking files with GitHub. They share helpers from `validate_config.py` (good) and don't duplicate each other's logic.

---

## 2. Dead Code

### 2A. `_KANBAN_STATES` backward-compat alias — only used internally [LOW]

`validate_config.py:853`: `_KANBAN_STATES = KANBAN_STATES  # Backward compat alias`

`_KANBAN_STATES` is only referenced at `validate_config.py:872` (inside `kanban_from_labels`). No external script imports `_KANBAN_STATES`. The alias serves no backward-compat purpose — it could be replaced with `KANBAN_STATES` directly.

### 2B. `resolve_namespace` — only called in tests [INFO]

`validate_anchors.py:71` `resolve_namespace()` is a trivial dict lookup. It's called only in test files (`test_validate_anchors.py`), never in production code. The `check_anchors()` function accesses `NAMESPACE_MAP` directly. Not truly dead — it's part of the public API for the anchor-validation module — but worth noting it has zero production callers.

### 2C. `get_prd_dir`, `get_test_plan_dir`, `get_story_map` — no production callers [INFO]

These helper functions in `validate_config.py` (lines 733, 743, 809) are only exercised in `test_hexwise_setup.py`. No skill script imports or calls them. They exist as convenience accessors for SKILL.md prompts that read config directly, so they're "API surface for LLM callers" rather than dead code. But they are never imported by any Python script.

### 2D. `extract_persona` — used only in sprint_analytics [INFO]

`sprint_analytics.py:30` `extract_persona()` extracts persona labels. It's only used within `compute_workload()` in the same file. No other script needs persona extraction. Not dead, but narrowly scoped — could be inlined.

### 2E. No unused imports detected [CLEAN]

Every import in every script is used. The codebase is clean on this front.

---

## 3. Design Inconsistencies

### 3A. Sprint milestone regex — inconsistent leading-zero handling [HIGH]

- `validate_config.py:896`: `re.match(rf"^Sprint 0*{num}\b", title)` — handles "Sprint 07" matching sprint 7
- `check_status.py:184`: `re.match(rf"^Sprint {sprint_num}\b", m.get("title", ""))` — NO leading-zero handling
- `check_status.py:398`: same pattern, no `0*`

The BH-001 fix added leading-zero tolerance to `find_milestone()` but `check_status.py` builds its own milestone-matching regex without this fix. This is a functional bug: `check_status` will miss milestones titled "Sprint 07:" when looking for sprint 7.

### 3B. `sys.path.insert` patterns — 3 different approaches [MEDIUM]

Scripts import `validate_config` via three different `sys.path` manipulation patterns:

1. **Same-directory scripts** (`team_voices.py`, `traceability.py`, `test_coverage.py`, `manage_epics.py`, `manage_sagas.py`, `sprint_init.py`, `sprint_analytics.py`):
   ```python
   SCRIPTS_DIR = Path(__file__).resolve().parent
   sys.path.insert(0, str(SCRIPTS_DIR))
   ```

2. **Skill scripts** (`bootstrap_github.py`, `populate_issues.py`, `setup_ci.py`, `check_status.py`, `sync_tracking.py`, `update_burndown.py`):
   ```python
   sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent / "scripts"))
   ```

3. **Hybrid** (`sync_backlog.py`):
   ```python
   sys.path.insert(0, str(Path(__file__).resolve().parent))
   sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "skills" / "sprint-setup" / "scripts"))
   ```

4. **Release gate** (`release_gate.py`):
   ```python
   _PLUGIN_ROOT = Path(__file__).resolve().parent.parent.parent.parent
   _SCRIPTS_DIR = _PLUGIN_ROOT / "scripts"
   sys.path.insert(0, str(_SCRIPTS_DIR))
   ```

The four-level `parent.parent.parent.parent` chain is fragile — any directory restructuring breaks all skill scripts silently (ImportError at runtime, not at load time).

### 3C. Error handling patterns — mixed conventions [MEDIUM]

Three patterns are used for handling config load failures:

**Pattern 1: Catch ConfigError, sys.exit(1)** (most scripts):
```python
try:
    config = load_config()
except ConfigError:
    sys.exit(1)
```
Used by: `sprint_analytics.py`, `check_status.py`, `update_burndown.py`, `sync_tracking.py`, `bootstrap_github.py`, `populate_issues.py`, `setup_ci.py`, `release_gate.py`, `team_voices.py`, `traceability.py`, `test_coverage.py`.

**Pattern 2: Bare except with generic error** (`sync_backlog.py:246-250`):
```python
except Exception as exc:
    print(f"sync: error — {exc}", file=sys.stderr)
    sys.exit(1)
```

**Pattern 3: No try/except, let it crash** — none, all scripts guard this.

The consistency is actually good here. The notable exception is `sync_backlog.main()` which catches `Exception` instead of `ConfigError`, which could swallow unexpected bugs.

### 3D. Exit code conventions — mostly consistent but one oddity [LOW]

Most scripts use: 0 = success, 1 = error, 2 = usage error.

Scripts with exit code 2: `sprint_analytics.py`, `check_status.py`, `update_burndown.py`, `sync_tracking.py`.

Scripts that use only 0/1: all others.

`check_status.py` has a unique semantic: exit 1 means "action needed" (not error), exit 0 means "no action needed." This is documented but inverts the typical convention.

### 3E. Return value conventions — tuple vs dict vs None [LOW]

Function return patterns:
- **Validation functions**: `(bool, str)` tuples — `validate_message()`, `check_atomicity()`, `gate_*()` functions
- **Query functions**: `dict | None` — `find_milestone()`, `get_linked_pr()`
- **Report functions**: `dict` — `compute_velocity()`, `build_traceability()`
- **Sync functions**: `list[str]` (change descriptions) — `sync_one()`

This is actually well-organized by function type. No inconsistency within categories.

### 3F. `check_prerequisites` — three scripts, three different scopes [LOW]

As noted in 1C:
- `bootstrap_github.py:18`: checks gh CLI version, auth, and git remote (3 checks, `sys.exit(1)` on failure)
- `populate_issues.py:37`: checks gh auth only (1 check, `sys.exit(1)` on failure)
- `setup_ci.py:339`: checks git repo only (1 check, `sys.exit(1)` on failure)

All use `subprocess.run` directly instead of the shared `gh()` wrapper. The scopes are different enough that sharing is debatable, but the inconsistency in what "prerequisites" means per script is confusing.

### 3G. `_yaml_safe` vs `_yaml_safe_command` — different purposes, similar names [INFO]

- `sync_tracking.py:183` `_yaml_safe(value)` — quotes YAML frontmatter values
- `setup_ci.py:94` `_yaml_safe_command(command)` — sanitizes CI commands for YAML

Different purposes despite similar naming. Not a bug, but could cause confusion during maintenance.

---

## 4. Cross-Script Coupling

### 4A. Import graph

```
validate_config.py (hub — imported by all scripts)
    ^
    |--- sprint_init.py (imports validate_project)
    |--- sprint_analytics.py (imports load_config, extract_sp, gh_json, detect_sprint, find_milestone, get_sprints_dir, warn_if_at_limit)
    |--- team_voices.py (imports load_config, ConfigError)
    |--- traceability.py (imports load_config, ConfigError)
    |--- test_coverage.py (imports load_config, ConfigError)
    |--- manage_epics.py (imports safe_int)
    |--- manage_sagas.py (imports safe_int)
    |--- commit.py (standalone — no validate_config import)
    |--- sprint_teardown.py (standalone — no validate_config import)
    |--- validate_anchors.py (standalone — no validate_config import)
    |--- sync_backlog.py (imports load_config, get_milestones)
    |        \--- bootstrap_github.py (cross-skill import)
    |        \--- populate_issues.py (cross-skill import)
    |--- bootstrap_github.py (imports load_config, get_team_personas, get_milestones, get_epics_dir, get_sagas_dir, gh)
    |--- populate_issues.py (imports load_config, ConfigError, get_milestones, gh, gh_json, warn_if_at_limit)
    |--- setup_ci.py (imports load_config, ConfigError, get_ci_commands)
    |--- check_status.py (imports load_config, ConfigError, extract_sp, gh, gh_json, get_base_branch, get_sprints_dir, detect_sprint, warn_if_at_limit)
    |        \--- sync_backlog.main (cross-skill import)
    |--- sync_tracking.py (imports load_config, ConfigError, gh_json, extract_story_id, get_sprints_dir, kanban_from_labels, find_milestone, list_milestone_issues, parse_iso_date, KANBAN_STATES, warn_if_at_limit)
    |--- update_burndown.py (imports load_config, ConfigError, extract_sp, get_sprints_dir, find_milestone, extract_story_id, kanban_from_labels, list_milestone_issues, parse_iso_date)
    |--- release_gate.py (imports load_config, ConfigError, get_base_branch, get_sprints_dir, gh, gh_json, warn_if_at_limit)

manage_sagas.py ---imports--> manage_epics.py (update_epic_index calls parse_epic)
```

### 4B. Cross-skill coupling — intentional but documented [OK]

Two cross-skill imports:
1. `sync_backlog.py` imports from `skills/sprint-setup/scripts/` (bootstrap_github, populate_issues)
2. `check_status.py` imports from `scripts/sync_backlog.py`

Both are documented as intentional in CLAUDE.md. The `try/except ImportError` guard in `sync_backlog.py:27-32` and `check_status.py:26-31` handles missing dependencies gracefully.

### 4C. Fragile `sys.path` chains [MEDIUM]

All skill scripts depend on the exact directory nesting depth (`parent.parent.parent.parent`) to find `scripts/`. This is the most fragile coupling in the codebase. If any script is moved to a different nesting depth, its imports silently break at runtime.

### 4D. `update_burndown._fm_val` assumes `sync_tracking` frontmatter format [MEDIUM]

`update_burndown.py:144` `_fm_val()` parses frontmatter written by `sync_tracking.py:210` `write_tf()`. The quote escaping convention (backslash-then-quote in `_yaml_safe`, reverse in `_fm_val`) must stay synchronized. A comment in `update_burndown.py:149-150` notes "matches sync_tracking.read_tf behavior" but there's no enforcement. If `_yaml_safe` changes its escaping, `_fm_val` will silently produce wrong values.

### 4E. `check_status.py` duplicates `find_milestone` regex — coupling gap [HIGH]

As described in 3A, `check_status.py` builds its own milestone-matching regex instead of calling `find_milestone()` from `validate_config.py`. This means check_status is coupled to the milestone naming convention but doesn't benefit from fixes applied to `find_milestone()` (like the leading-zero fix BH-001).

---

## Severity Summary

| # | Finding | Severity | Category |
|---|---------|----------|----------|
| 3A | `check_status.py` milestone regex missing `0*` for leading zeros | HIGH | Design inconsistency / bug |
| 4E | `check_status.py` duplicates `find_milestone` instead of calling it | HIGH | Coupling gap |
| 1A | `_parse_header_table` copy-pasted in manage_epics + manage_sagas | MEDIUM | Duplication |
| 1D | Milestone query re-implemented in check_status instead of reusing find_milestone | MEDIUM | Duplication |
| 1G | `_fm_val` in update_burndown duplicates frontmatter parsing from sync_tracking | MEDIUM | Duplication |
| 3B | Three different sys.path.insert patterns | MEDIUM | Design inconsistency |
| 3C | sync_backlog catches Exception instead of ConfigError | MEDIUM | Design inconsistency |
| 4C | Fragile 4-level parent chain for imports | MEDIUM | Coupling |
| 4D | _fm_val must stay in sync with _yaml_safe but has no enforcement | MEDIUM | Coupling |
| 1B | STORY_HEADING regex defined in 2 files | LOW | Duplication |
| 1C | check_prerequisites has 3 different implementations | LOW | Duplication |
| 1E | find_milestone_number vs find_milestone overlap | LOW | Duplication |
| 1F | SP counting duplicated in check_status vs sprint_analytics | LOW | Duplication |
| 2A | _KANBAN_STATES alias serves no purpose | LOW | Dead code |
| 3D | Exit code 1 means "action needed" in check_status but "error" elsewhere | LOW | Design inconsistency |
| 3F | check_prerequisites scope varies by script | LOW | Design inconsistency |
| 2B | resolve_namespace has zero production callers | INFO | Dead code |
| 2C | get_prd_dir, get_test_plan_dir, get_story_map have no script callers | INFO | Dead code (API surface) |
| 2D | extract_persona is narrowly scoped | INFO | Dead code |
| 3E | Return value conventions are actually consistent per category | INFO | Clean |
| 3G | _yaml_safe vs _yaml_safe_command naming | INFO | Naming |
| 1H | sync_backlog reuses populate_issues correctly | OK | Confirmed clean |
| 1I | check_status and sync_tracking don't overlap | OK | Confirmed clean |
| 2E | No unused imports found | OK | Clean |
