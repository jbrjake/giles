# Phase 1: Doc-to-Implementation Audit — Bug Hunter Pass 37

Systematic comparison of documentation claims against actual code behavior.

---

## Finding 1: Skeleton template count is wrong

**Doc:** CLAUDE.md line 124, CHEATSHEET.md line 473
**Claim:** "19 templates: 9 core + 10 deep-doc"
**Reality:** There are **20** templates. `risk-register.md.tmpl` exists in
`references/skeletons/` but is not listed in the template inventory. Neither
CLAUDE.md nor CHEATSHEET.md mentions it.
**Severity:** MEDIUM — a developer adding or modifying templates would miss
this file, and sprint_init.py may or may not wire it in.

---

## Finding 2: CHEATSHEET describes `check_preconditions` incorrectly

**Doc:** CHEATSHEET.md line 120
**Claim:** `check_preconditions()` — "Enforce WIP limits and other
preconditions before transition"
**Reality:** `check_preconditions()` (kanban.py line 89) only checks field
requirements (implementer, branch, pr_number, reviewer). WIP limits are
enforced by a **separate** function `check_wip_limit()` (kanban.py line 242),
which is not listed in the CHEATSHEET at all.
**Severity:** MEDIUM — a developer looking for WIP limit enforcement would
find the wrong function, and would not find the right one via CHEATSHEET.

---

## Finding 3: CHEATSHEET missing 5 anchored kanban.py functions

**Doc:** CHEATSHEET.md, kanban.py section (lines 115-130)
**Claim:** Lists 13 functions for kanban.py
**Reality:** The code has 18 anchored items. Missing from CHEATSHEET:
- `§kanban.check_wip_limit` / `check_wip_limit()` — WIP limit enforcement
- `§kanban._count_review_rounds` / `_count_review_rounds()` — review escalation
- `§kanban.append_transition_log` / `append_transition_log()` — transition logging
- `§kanban.build_parser` / `build_parser()` — CLI arg parser
- `§kanban._PERSONA_HEADER_PATTERN` / `_PERSONA_HEADER_PATTERN` — regex const

**Severity:** MEDIUM — `check_wip_limit` and `append_transition_log` are
called by external code (sync_tracking.py imports `append_transition_log`),
so developers tracing cross-module calls would not find them via the index.

---

## Finding 4: CHEATSHEET missing check_status.py functions

**Doc:** CHEATSHEET.md, check_status.py section (lines 175-184)
**Claim:** Lists 7 functions
**Reality:** Code has 9 anchored functions. Missing:
- `§check_status.check_smoke` / `check_smoke()` — smoke test runner
- `§check_status.check_integration_debt` / `check_integration_debt()` — debt tracker

CLAUDE.md correctly lists these, but the CHEATSHEET does not.
**Severity:** LOW — CLAUDE.md is the primary reference and is correct.

---

## Finding 5: CHEATSHEET missing update_burndown.py `build_rows`

**Doc:** CHEATSHEET.md, update_burndown.py section (lines 141-148)
**Claim:** Lists 5 functions
**Reality:** `§update_burndown.build_rows` / `build_rows()` exists in code
(line 142) and is listed in CLAUDE.md but missing from CHEATSHEET.
**Severity:** LOW — CLAUDE.md is correct.

---

## Finding 6: CHEATSHEET missing validate_config.py functions

**Doc:** CHEATSHEET.md, validate_config.py section (lines 14-47)
**Claim:** Lists 31 items
**Reality:** Code has 38 anchored items. Missing from CHEATSHEET:
- `§validate_config.safe_int` (listed only under manage_epics/manage_sagas imports)
- `§validate_config.parse_iso_date`
- `§validate_config.slug_from_title`
- `§validate_config.TF` (the tracking file dataclass)
- `§validate_config.read_tf`
- `§validate_config.write_tf`
- `§validate_config.atomic_write_text`

The TF dataclass and read_tf/write_tf are fundamental to the tracking system.
**Severity:** MEDIUM — TF, read_tf, and write_tf are imported by nearly every
script. A developer looking up how tracking files work would not find the
dataclass definition via the CHEATSHEET.

---

## Finding 7: CHEATSHEET says TRANSITIONS is "dict of sets" — it's lists

**Doc:** CHEATSHEET.md line 118
**Claim:** `TRANSITIONS` — "Allowed state transitions dict (source -> set of
targets)"
**Reality:** kanban.py line 48 declares `TRANSITIONS: dict[str, list[str]]`.
The values are **lists**, not **sets**.
**Severity:** LOW — the behavioral difference is negligible (both are iterable
and checked with `in`), but a developer writing code that depends on set
properties (e.g., deduplication) would be misled.

---

## Finding 8: Dangling anchor references in CLAUDE.md for 6 scripts

**Doc:** CLAUDE.md lines 57-62
**Claim:** References anchors like `§smoke_test.run_smoke`,
`§gap_scanner.scan_for_gaps`, `§risk_register.add_risk`,
`§test_categories.classify_test_file`, `§assign_dod_level.classify_story`,
`§history_to_checklist.extract_checklist_items`
**Reality:** These 6 scripts have **no anchor comments** in their source code:
- `scripts/smoke_test.py`
- `scripts/gap_scanner.py`
- `scripts/risk_register.py`
- `scripts/test_categories.py`
- `scripts/assign_dod_level.py`
- `scripts/history_to_checklist.py`

The functions themselves exist and are named correctly, but the `§`-prefixed
anchor comments that CLAUDE.md references do not exist in the source files.
`validate_anchors.py --fix` would need to add them.
**Severity:** MEDIUM — the anchor system is designed for cross-reference
validation. These dangling references would cause `validate_anchors.py` to
report false negatives (refs that can't resolve to defs).

---

## Finding 9: CLAUDE.md config structure implies [conventions] and [release] are required

**Doc:** CLAUDE.md line 102
**Claim:** `project.toml — REQUIRED — [project], [paths], [ci], [conventions], [release]`
**Reality:** `_REQUIRED_TOML_SECTIONS` (validate_config.py line 471) is
`["project", "paths", "ci"]`. The `[conventions]` and `[release]` sections
are **optional**. CLAUDE.md line 117 later clarifies that `[conventions]` keys
are optional, but the configuration structure listing on line 102 reads as
though all five sections are required.
**Severity:** MEDIUM — a user reading the config structure would believe they
must include `[conventions]` and `[release]` sections. If they create a
minimal project.toml with only required sections, the listing would make them
think they're missing something.

---

## Summary

| # | Finding | Severity | Action |
|---|---------|----------|--------|
| 1 | Template count 19 vs actual 20 (risk-register.md.tmpl) | MEDIUM | Update CLAUDE.md and CHEATSHEET.md |
| 2 | CHEATSHEET: check_preconditions description wrong | MEDIUM | Fix description, add check_wip_limit |
| 3 | CHEATSHEET: 5 kanban.py functions missing | MEDIUM | Add missing entries |
| 4 | CHEATSHEET: 2 check_status.py functions missing | LOW | Add missing entries |
| 5 | CHEATSHEET: build_rows missing from update_burndown | LOW | Add missing entry |
| 6 | CHEATSHEET: 7 validate_config.py items missing | MEDIUM | Add TF, read_tf, write_tf, etc. |
| 7 | CHEATSHEET: TRANSITIONS described as "set" not "list" | LOW | Fix description |
| 8 | CLAUDE.md: 6 scripts have dangling § anchors | MEDIUM | Add anchor comments to source |
| 9 | CLAUDE.md: config structure implies optional sections required | MEDIUM | Annotate optional sections |

**Totals:** 6 MEDIUM, 3 LOW, 0 HIGH

No HIGH-severity issues found. The codebase is well-aligned between docs and
implementation for behavior-critical claims (state machine transitions,
preconditions, WIP limits, tracking file format, config validation keys).
The gaps are in index completeness and a misleading description.
