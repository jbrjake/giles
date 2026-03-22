# Phase 1 — Import Chain + Config Data Flow Audit (Pass 39)

**Date:** 2026-03-21
**Scope:** sys.path.insert correctness, config key access contracts, validate_config exports, cross-skill imports, ConfigError propagation, extract_story_id contract
**Method:** Empirical verification of every import chain and config access in every script (~25 production scripts, ~7 skill scripts)

---

## Summary

- **Seams audited:** 6 major categories
- **Issues found:** 3
- **Severity breakdown:** 0 HIGH, 2 MEDIUM, 1 LOW

The import chains and config data flow contracts are solid after 38 prior passes. Every sys.path.insert resolves correctly, every imported symbol exists, every ConfigError is caught, and all path resolution is consistent. The findings are at the contract edges: a dedup filter that silently drops custom-pattern stories, a broad net for non-story issues during kanban sync, and a minor type annotation mismatch.

---

## Findings

### BH39-001: populate_issues.get_existing_issues dedup filter silently drops custom-pattern story IDs (MEDIUM)
**Seam:** extract_story_id() ↔ get_existing_issues() ↔ create_issue() idempotency
**Evidence:**
- `scripts/validate_config.py:978` — `extract_story_id()` matches `[A-Z]+-\d+` (e.g., US-0001, PROJ-42), else falls back to a sanitized uppercase slug
- `skills/sprint-setup/scripts/populate_issues.py:370-375`:
  ```python
  sid = extract_story_id(title)
  if re.match(r"[A-Z]+-\d+", sid):
      existing.add(sid)
  ```
- `populate_issues.py:108-128` — `_build_row_regex()` allows custom `story_id_pattern` from config `[backlog]`. A pattern like `TASK\d{4}` (no hyphen) would produce IDs like `TASK0001` from the milestone table regex, but these IDs would fail the `[A-Z]+-\d+` filter in get_existing_issues
- Result: on re-run, those stories are not in the `existing` set, bypassing idempotency → duplicate GitHub issues created

**Impact:** Projects using custom `story_id_pattern` where IDs lack a hyphen between prefix and digits would get duplicate issues on every re-run of populate_issues.py. The standard `US-XXXX` pattern is unaffected.
**Suggested fix:** In get_existing_issues, also accept IDs matching the configured story_id_pattern, or broaden the filter to accept any non-"UNKNOWN" ID that extract_story_id produces.

### BH39-002: kanban.py do_sync and sync_tracking.py create tracking files for non-story issues in the milestone (MEDIUM)
**Seam:** extract_story_id() fallback ↔ kanban.py do_sync() / sync_tracking.py create_from_issue() ↔ file creation filter
**Evidence:**
- `scripts/validate_config.py:984-986` — fallback: `slug = re.sub(r"[^a-zA-Z0-9_-]", "-", prefix).strip("-").upper()` → returns slug[:40], only returns "UNKNOWN" for empty/whitespace input
- `scripts/kanban.py:563` — skips only `story_id == "UNKNOWN"`
- `skills/sprint-run/scripts/sync_tracking.py:185,290` — same: skips only when sid is "UNKNOWN" (line 563 equivalent is implicit — create_from_issue has no UNKNOWN check, but kanban.py do_sync does at line 563)
- An issue titled "Fix login timeout" (no standard ID) would produce slug "FIX-LOGIN-TIMEOUT", which is not "UNKNOWN", so a tracking file is created

Wait — sync_tracking.py at line 290 does:
```python
sid = extract_story_id(issue["title"])
```
Then at line 292:
```python
if sid.upper() in existing:
```
If not in existing, it calls `create_from_issue`. There is no "UNKNOWN" check in sync_tracking.py's main loop. Only kanban.py do_sync (line 563) checks for "UNKNOWN".

**Impact:** During sync_tracking.py runs, manually-filed issues in the milestone (bugs, chores, spikes without standard IDs) will get tracking files with slug-based IDs. These files clutter the sprint directory and may confuse status reporting. kanban.py do_sync is slightly better (skips "UNKNOWN") but still creates files for titled issues like "Fix bug" → "FIX-BUG". Both paths are consistent with each other, limiting the blast radius.
**Suggested fix:** Add a label filter to only sync issues with `type:story` or `kanban:*` labels, or filter out IDs that don't match `[A-Z]+-\d+` (matching populate_issues' convention).

### BH39-003: smoke_test.write_history type annotation says str but callers pass Path (LOW)
**Seam:** smoke_test.py write_history() ↔ callers
**Evidence:**
- `scripts/smoke_test.py:60` — `def write_history(sprints_dir: str, ...)`
- `scripts/smoke_test.py:124` — `sprints_dir = get_sprints_dir(config)` returns `Path`; line 126 passes it directly: `write_history(sprints_dir, ...)`
- `skills/sprint-monitor/scripts/check_status.py:306` — correctly passes `str(sprints_dir)`
- Inside write_history, line 63: `Path(sprints_dir)` works with both str and Path

**Impact:** No runtime failure — `Path(a_path_object)` returns an equivalent Path. Static analysis tools would flag this as a type error. check_status.py already works around it by casting to str.
**Suggested fix:** Change signature to `sprints_dir: str | Path` or change smoke_test.py:126 to `write_history(str(sprints_dir), ...)`.

---

## Clean (verified correct)

### A. sys.path.insert correctness — ALL 22 SCRIPTS VERIFIED CORRECT

**scripts/*.py** (15 scripts): All use `Path(__file__).resolve().parent` → resolves to `giles/scripts/` containing validate_config.py. Verified: kanban.py:33, sync_backlog.py:23, sprint_analytics.py:19, gap_scanner.py:20, manage_epics.py:20, risk_register.py:20, test_coverage.py:17, smoke_test.py:20, team_voices.py:19, test_categories.py:20, traceability.py:18, history_to_checklist.py:16, assign_dod_level.py:16, manage_sagas.py:20, sprint_init.py:25.

**skills/*/scripts/*.py** (7 scripts): All use `parent.parent.parent.parent / "scripts"` (4 levels). From e.g. `giles/skills/sprint-setup/scripts/foo.py`: parent=scripts → parent.parent=sprint-setup → parent.parent.parent=skills → parent.parent.parent.parent=giles → `/ "scripts"` = `giles/scripts/`. Verified: bootstrap_github.py:14, populate_issues.py:15, setup_ci.py:16, sync_tracking.py:27, update_burndown.py:20, check_status.py:23, release_gate.py:26-28.

**Cross-skill import** (sync_backlog.py:24): Also inserts `parent.parent / "skills" / "sprint-setup" / "scripts"` — resolves from `giles/scripts/` to `giles/skills/sprint-setup/scripts/`. Correct.

**Why this matters:** A single wrong parent count would silently import a wrong module or crash at startup. All 22 are correct.

### B. Config key access consistency — ALL CORRECT

**Required keys guaranteed by _REQUIRED_TOML_KEYS** (validate_config.py:468-477): project.name, project.repo, project.language, paths.team_dir, paths.backlog_dir, paths.sprints_dir, ci.check_commands, ci.build_command. All 8 enforced before load_config returns.

**Path resolution:** load_config (lines 721-725) resolves ALL `[paths]` string values to absolute paths relative to project root. No consumer re-resolves. Accessor functions (get_sprints_dir, get_milestones, etc.) use the already-resolved values.

**Optional keys** (base_branch, sagas_dir, epics_dir, prd_dir, test_plan_dir, story_map, smoke_command, smoke_timeout, binary_path, workflow, story_id_pattern): All accessed via `.get()` with appropriate defaults. No script assumes an optional key exists.

### C. validate_config export contract — ALL 30+ SYMBOLS VERIFIED

Every symbol imported by every consumer exists in validate_config.py. Complete verification:

ConfigError(:25), load_config(:684), validate_project(:484), parse_simple_toml(:135), safe_int(:34), parse_iso_date(:41), gh(:66), gh_json(:82), get_team_personas(:735), get_milestones(:764), get_ci_commands(:780), get_base_branch(:790), get_sprints_dir(:797), get_epics_dir(:833), get_sagas_dir(:823), extract_sp(:843), extract_story_id(:972), short_title(:990), KANBAN_STATES(:996), kanban_from_labels(:1003), TF(:1049), read_tf(:1100), write_tf(:1145), _yaml_safe(:1066), slug_from_title(:1038), find_milestone(:1169), list_milestone_issues(:1191), warn_if_at_limit(:1212), detect_sprint(:959), TABLE_ROW(:893), parse_header_table(:897), frontmatter_value(:926), atomic_write_text(:1132).

No script imports a symbol that doesn't exist. No symbol has been renamed without updating importers.

### D. Cross-skill import chain (sync_backlog → bootstrap_github, populate_issues) — CORRECT

- sys.path manipulation at sync_backlog.py:23-24 correctly reaches both `scripts/` and `skills/sprint-setup/scripts/`
- Module-level try/except ImportError (lines 27-35) sets failed imports to None
- do_sync (line 165) gates on `bootstrap_github is None or populate_issues is None`
- All 6 functions called from these modules exist and match their calling signatures:
  - `bootstrap_github.create_milestones_on_github(config)` — exists at :234, takes dict, returns int
  - `populate_issues.parse_milestone_stories(milestone_files, config)` — exists at :132
  - `populate_issues.enrich_from_epics(stories, config)` — exists at :295
  - `populate_issues.get_existing_issues()` — exists at :346, takes no args
  - `populate_issues.get_milestone_numbers()` — exists at :380, takes no args
  - `populate_issues.build_milestone_title_map(milestone_files)` — exists at :394
  - `populate_issues.create_issue(story, milestone_numbers, milestone_titles)` — exists at :475

### E. ConfigError propagation — ALL 17 SCRIPTS CORRECT

Every script that imports ConfigError handles it in main():

| Pattern | Scripts |
|---------|---------|
| `except ConfigError: sys.exit(1)` | kanban.py:736, bootstrap_github.py:314, populate_issues.py:510, setup_ci.py:367, check_status.py:501, sync_tracking.py:247, update_burndown.py:185, release_gate.py:750, sprint_analytics.py:209, smoke_test.py:108, gap_scanner.py:176, test_coverage.py:189, test_categories.py:188, traceability.py:214, assign_dod_level.py:72, team_voices.py:95 |
| `except ConfigError: <fallback>` | history_to_checklist.py:98, risk_register.py:30 |
| `except (ConfigError, RuntimeError, ImportError)` | sync_backlog.py:263 |

No ConfigError goes uncaught. load_config always prints human-readable errors via _print_errors before raising.

### F. extract_story_id() contract — FUNCTIONALLY CORRECT (edge cases noted in BH39-001/002)

- Always returns non-empty string (property-tested in test_property_parsing.py)
- Returns "UNKNOWN" only for empty/whitespace-only input
- Standard path (`[A-Z]+-\d+`) works everywhere
- Fallback path (sanitized slug) is handled by kanban.py (skips "UNKNOWN"), sync_tracking.py (no filter but consistent with kanban.py), and populate_issues.py (filters to standard pattern only — see BH39-001)
- update_burndown.py uses raw return for display in burndown table — acceptable, shows the best available ID

### Additional verified seams

- **sync_tracking.py imports from kanban.py** (line 34): `lock_sprint`, `atomic_write_tf`, `append_transition_log` — all exist in kanban.py. sys.path already includes `scripts/` where kanban.py lives.
- **assign_dod_level.py imports from kanban.py** (line 22): `lock_sprint` — exists. Same sys.path.
- **check_status.py imports from sync_backlog and smoke_test** (lines 28-35): Both guarded by try/except ImportError with graceful fallback to None. Callers check for None before use.
- **`_config_dir` internal key**: Set by load_config at line 717. Used by sync_backlog.py:216, release_gate.py:467, risk_register.py:28 — all with `.get("_config_dir", "sprint-config")` fallback. Consistent.
