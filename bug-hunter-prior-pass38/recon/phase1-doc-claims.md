# BH38 Phase 1 — Doc-to-Implementation Audit

**Date:** 2026-03-21
**Scope:** CLAUDE.md, CHEATSHEET.md, reference docs, SKILL.md files
**Method:** Extract testable claims, verify against source code

---

## Summary

- **Claims verified:** 47
- **Issues found:** 6
- **Severity breakdown:** 1 HIGH, 3 MEDIUM, 2 LOW

Most doc claims are accurate. The required TOML keys, skeleton template count (20),
KANBAN_STATES (6 states), transition table, and function existence claims all check out.
The issues found are primarily stale doc text, missing CHEATSHEET entries, and one
misleading description.

---

## Verified Claims (no issues)

| Claim | Source | Status |
|-------|--------|--------|
| 20 skeleton templates in references/skeletons/ | CLAUDE.md:124 | PASS (counted 20) |
| 5 skills with SKILL.md entry points | CLAUDE.md:13 | PASS |
| Required TOML keys match _REQUIRED_TOML_KEYS | CLAUDE.md:115 | PASS (8 keys match exactly) |
| Required TOML sections: project, paths, ci | CLAUDE.md:102 | PASS |
| KANBAN_STATES = 6 states (todo, design, dev, review, integration, done) | CLAUDE.md:81, kanban-protocol.md:6 | PASS |
| Transition table matches kanban.py TRANSITIONS dict | kanban-protocol.md:22 | PASS |
| WIP limits 1/2/3 match check_wip_limit() code | kanban-protocol.md:94 | PASS (table matches code) |
| parse_simple_toml supports \uXXXX escape | CLAUDE.md:132 | PASS |
| parse_simple_toml supports single-quoted literal strings | CLAUDE.md:132 | PASS |
| Floats returned as raw strings | CLAUDE.md:132 | PASS (fail int(), fall through) |
| Skill scripts use 4x parent to reach scripts/ | CLAUDE.md:133 | PASS |
| Top-level scripts use single parent path | CLAUDE.md:133 | PASS |
| sync_backlog imports from skills/sprint-setup/scripts/ | CLAUDE.md:136 | PASS |
| _REQUIRED_FILES has 6 entries | validate_config.py:452 | PASS |
| All reference files in CLAUDE.md exist | CLAUDE.md:79-94 | PASS |
| plugin.json exists at .claude-plugin/plugin.json | CLAUDE.md:12 | PASS |
| evals/evals.json exists | CLAUDE.md:21 | PASS |
| kanban.py preconditions match kanban-protocol.md table | kanban-protocol.md:58 | PASS |
| validate_project checks persona files (step 4) | CLAUDE.md:104-105 | PASS |
| validate_project checks milestones dir (step 5) | CLAUDE.md:110 | PASS |
| setup_ci._SETUP_REGISTRY covers Rust/Python/Node/Go | CLAUDE.md:45 | PASS |
| All §-anchored functions in CHEATSHEET exist in code | CHEATSHEET.md | PASS (spot-checked 30+) |
| check_branch_divergence thresholds (>10 medium, >20 high) | CHEATSHEET.md:188 | PASS |
| TF dataclass fields match read_tf/write_tf serialization | CHEATSHEET.md:45 | PASS |
| THROTTLE_FLOOR_SECONDS = 600 in sync_backlog | CHEATSHEET.md:160 | PASS |

---

## Issues Found

### BH38-001 — kanban-protocol.md Note contradicts its own WIP table and code
**Severity:** MEDIUM
**File:** skills/sprint-run/references/kanban-protocol.md:90-92
**Phase:** Phase 1 (doc-to-implementation)
**Description:** The blockquote Note says: "The dev WIP limit (1 per persona) is enforced by `kanban.py check_wip_limit()`. Review and integration limits remain behavioral guidelines." But the table directly below (lines 98-99) shows review and integration as "Code (`check_wip_limit`)" enforcement, and `kanban.py check_wip_limit()` (lines 255-268) does enforce all three: dev (1/persona), review (2/reviewer), integration (3/team). The Note is stale from before review/integration enforcement was added. Fix: update the Note to say all three WIP limits are code-enforced.

### BH38-002 — CHEATSHEET describes check_integration_debt incorrectly
**Severity:** MEDIUM
**File:** CHEATSHEET.md:191
**Phase:** Phase 1 (doc-to-implementation)
**Description:** CHEATSHEET says `check_integration_debt` purpose is "Detect stories in integration state too long." The actual implementation (check_status.py:344-383) measures *sprints since last smoke pass* — it reads smoke-history.md and computes time since last SMOKE PASS, not time stories have spent in integration state. Fix: update CHEATSHEET description to "Detect integration debt: sprints since last smoke pass."

### BH38-003 — CHEATSHEET missing _most_common_sprint and _build_detail_block_re for populate_issues
**Severity:** LOW
**File:** CHEATSHEET.md (populate_issues section, lines 90-104)
**Phase:** Phase 1 (doc-to-implementation)
**Description:** Two anchored functions exist in populate_issues.py but are missing from CHEATSHEET.md: `_most_common_sprint()` (line 280, anchor §populate_issues._most_common_sprint) and `_build_detail_block_re()` (line 211, anchor §populate_issues._build_detail_block_re — actually this one has no anchor, just a def). CLAUDE.md does list `_most_common_sprint` but CHEATSHEET omits it. Fix: add both to CHEATSHEET populate_issues table.

### BH38-004 — validate_config.atomic_write_text missing from CLAUDE.md and CHEATSHEET.md
**Severity:** MEDIUM
**File:** scripts/validate_config.py:1131-1141
**Phase:** Phase 1 (doc-to-implementation)
**Description:** `atomic_write_text()` is an anchored public utility (§validate_config.atomic_write_text) at line 1131 that provides temp-then-rename atomic writes for shared markdown files. It is used by manage_epics.py and manage_sagas.py. Both CLAUDE.md and CHEATSHEET.md omit it from the validate_config function index. Fix: add to both docs.

### BH38-005 — CLAUDE.md parse_simple_toml claim omits \U (8-digit Unicode) support
**Severity:** LOW
**File:** CLAUDE.md:132
**Phase:** Phase 1 (doc-to-implementation)
**Description:** CLAUDE.md says the TOML parser supports "escape processing including `\uXXXX`" but the code (_unescape_toml_string, line 308) also supports `\UXXXXXXXX` (8-digit Unicode codepoints). This is a minor omission — the parser supports both TOML Unicode escape forms. Fix: update to mention both `\uXXXX` and `\UXXXXXXXX`.

### BH38-006 — CHEATSHEET sync_backlog.do_sync description says "lazy-imports" but imports are at module level
**Severity:** HIGH
**File:** CHEATSHEET.md:169, scripts/sync_backlog.py:27-35
**Phase:** Phase 1 (doc-to-implementation)
**Description:** CHEATSHEET says do_sync "Lazy-imports bootstrap_github + populate_issues, runs sync." The do_sync docstring (line 162) also says "Imports bootstrap_github and populate_issues lazily." But the actual imports happen at MODULE LEVEL (lines 27-35) inside a try/except. The do_sync function just checks if the module variables are None. This matters because the docstring is misleading — if the imports fail at module load, do_sync will never work, and the error surfaces at import time rather than at sync time. The CHEATSHEET should say "Uses bootstrap_github + populate_issues (imported at module level with graceful fallback)." The do_sync docstring should also be updated.

---

## Near-Misses (cosmetic, not filing as issues)

1. **CLAUDE.md sprint_teardown summary only lists 2 of 12 functions** — classify_entries and main. Missing: collect_directories, resolve_symlink_target, symlink_display, print_dry_run, remove_symlinks, remove_generated, remove_empty_dirs, check_active_loops, print_loop_cleanup_hints, print_github_cleanup_hints. CHEATSHEET lists the full set. This is by design (CLAUDE.md is summary, CHEATSHEET is exhaustive).

2. **CLAUDE.md omits _parse_saga_labels_from_backlog from bootstrap_github** — listed in CHEATSHEET but not CLAUDE.md. Same rationale: summary vs complete index.

3. **history_to_checklist.format_checklist() has no § anchor** — Public function at line 70 without anchor comment or doc listing. Minor.

4. **release_gate.py has undocumented public functions** — determine_bump(), bump_version(), print_gate_summary(), find_milestone_number() all lack § anchors and doc listings. They are meaningful public API surface.

5. **TF CHEATSHEET description uses "fields" as shorthand** — Says "(story, title, status, fields, body_text, path)" but actual dataclass has 12 named fields. Not wrong but imprecise.
