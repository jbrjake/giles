# Bug Hunter Punchlist — Pass 37

> Generated: 2026-03-21 | Project: giles | Baseline: 1178 pass, 0 fail, 83% coverage
> Focus: Clean-slate full audit after 36 converged passes

## Summary

| Severity | Open | Resolved | Closed |
|----------|------|----------|--------|
| HIGH     | 2    | 3        | 0      |
| MEDIUM   | 9    | 5        | 0      |
| LOW      | 12   | 1        | 0      |

---

## Open — HIGH

### BH37-008 — Mock pollution in kanban double-fault test

**File:** `tests/test_kanban.py:471-486`
**Phase:** Phase 2 (test quality H3)
**Impact:** `atomic_write_tf` is mocked, so the test only verifies in-memory state restoration, never disk state. The "double-fault" scenario (GitHub + disk failure) is only tested at memory level.
**Fix:** Add a complementary test that allows the real first write and only mocks the rollback write.

### BH37-010 — Weakened assertTrue(len>0) hides which action items are wrong

**File:** `tests/test_sprint_runtime.py:77, 157`
**Phase:** Phase 2 (test quality H4)
**Impact:** `TestCheckCI.test_failing_run` and `TestCheckPRs.test_mixed_review_states` only check `len(actions) > 0` without verifying action content matches setup.
**Fix:** Assert action content references expected branch/PR/run names.

---

## Open — MEDIUM

### BH37-010 — Weakened assertTrue(len>0) hides which action items are wrong

**File:** `tests/test_sprint_runtime.py:77, 157`
**Phase:** Phase 2 (test quality H4)
**Impact:** `TestCheckCI.test_failing_run` and `TestCheckPRs.test_mixed_review_states` only check `len(actions) > 0` without verifying action content matches setup.
**Fix:** Assert action content references expected branch/PR/run names.

### BH37-014 — Contract tests verify list element presence not argument ordering

**File:** `tests/test_sprint_runtime.py:58-64, 115-117`
**Phase:** Phase 2 (test quality M1)
**Impact:** `assertIn("run", call_args)` passes even if args are reordered to invalid CLI syntax.
**Fix:** Assert positional arguments: `assertEqual(call_args[:2], ["run", "list"])`.

### BH37-015 — check_milestone SP test never verifies actual totals

**File:** `tests/test_sprint_runtime.py:1833-1846`
**Phase:** Phase 2 (test quality M2)
**Impact:** Only checks "3/5" and "SP" strings appear, never verifies correct SP summation.
**Fix:** Assert specific SP totals in report.

### BH37-016 — Missing boundary tests for branch divergence thresholds

**File:** `tests/test_sprint_runtime.py:1039-1080`
**Phase:** Phase 2 (test quality M3)
**Impact:** Production thresholds >10 MEDIUM, >20 HIGH. Tests use 3/15/25 — no exact-boundary tests. Threshold change from `>10` to `>=10` would be undetected.
**Fix:** Add tests for values 10, 11, 20, 21.

### BH37-017 — Duplicate TestKanbanFromLabels across two test files

**File:** `tests/test_sprint_runtime.py:1674` and `tests/test_pipeline_scripts.py:1641`
**Phase:** Phase 2 (test quality M4)
**Impact:** Inflates test count without adding coverage. Not a shadowing bug (different files), but redundant.
**Fix:** Remove one copy.

### BH37-018 — assertIn on stringified mock.call_args is fragile

**File:** `tests/test_kanban.py:466-468`, `tests/test_sprint_runtime.py:89`
**Phase:** Phase 2 (test quality M5)
**Impact:** `assertIn("42", str(mock.call_args))` — "42" could match any repr artifact. Should inspect args directly.
**Fix:** Use `mock.call_args[0][0]` to check specific arguments.

### BH37-019 — assertTrue(len==1) instead of assertEqual

**File:** `tests/test_new_scripts.py:368`
**Phase:** Phase 2 (test quality M6)
**Impact:** Produces unhelpful "False is not True" failure message.
**Fix:** Use `assertEqual(len(data_lines), 1)`.

### BH37-020 — Skeleton template count wrong (19 vs 20)

**File:** CLAUDE.md line 124, CHEATSHEET.md line 473
**Phase:** Phase 1 (doc audit)
**Impact:** `risk-register.md.tmpl` exists but isn't listed. Developer adding templates would miss it.
**Fix:** Update both docs to say 20 templates, add risk-register to the list.

### BH37-021 — CHEATSHEET missing 14+ anchored functions across 4 files

**Files:** CHEATSHEET.md (kanban.py: 5 missing, validate_config.py: 7 missing, check_status.py: 2 missing, update_burndown.py: 1 missing)
**Phase:** Phase 1 (doc audit)
**Impact:** Developers can't find `check_wip_limit`, `TF`, `read_tf`, `write_tf`, etc. via the index.
**Fix:** Add missing entries to CHEATSHEET.md.

### BH37-022 — CLAUDE.md dangling § anchors for 6 scripts

**Files:** smoke_test.py, gap_scanner.py, risk_register.py, test_categories.py, assign_dod_level.py, history_to_checklist.py
**Phase:** Phase 1 (doc audit)
**Impact:** CLAUDE.md references §-anchors that don't exist in source files. `validate_anchors.py` would report false negatives.
**Fix:** Add anchor comments to the 6 source files, or run `validate_anchors.py --fix`.

---

## Open — LOW

### BH37-023 — Unused imports in production scripts (partially resolved)

**Files:** sync_tracking.py:30 (frontmatter_value still unused)
**Phase:** Recon (lint F401)
**Note:** 4 of 6 resolved. kanban._yaml_safe, manage_sagas.TABLE_ROW, check_status.json removed. sync_tracking.write_tf and _yaml_safe kept as intentional re-exports (noqa: F401). frontmatter_value still unused.
**Fix:** Remove `frontmatter_value` from sync_tracking import.

### BH37-024 — Reimported modules in test_verify_fixes.py

**File:** `tests/test_verify_fixes.py:389, 883, 1007, 1011`
**Phase:** Recon (lint F811)
**Fix:** Remove redundant imports or add noqa.

### BH37-025 — commit_gate.py blocks all commits in empty repos

**File:** `.claude-plugin/hooks/commit_gate.py:62-68`
**Phase:** Phase 3 (adversarial)
**Fix:** Fall back to `git diff --cached` when HEAD doesn't exist.

### BH37-026 — sync_tracking case-sensitive collision check

**File:** `skills/sprint-run/scripts/sync_tracking.py:200`
**Phase:** Phase 3 (adversarial)
**Fix:** Use `.upper()` comparison.

### BH37-027 — Smoke test timestamps lack explicit timezone marker

**File:** `check_status.py:289-291`, `smoke_test.py:62`
**Phase:** Phase 3 (adversarial)
**Fix:** Add `Z` suffix to UTC timestamps.

### BH37-028 — First release version can never be v0.1.0

**File:** `skills/sprint-release/scripts/release_gate.py:120-133`
**Phase:** Phase 3 (adversarial)
**Fix:** Add `--initial-version` flag or don't bump on first release.

### BH37-029 — Unquoted TOML numeric values may cause TypeError downstream

**File:** `scripts/validate_config.py:356-359`
**Phase:** Phase 3 (adversarial)
**Fix:** Add type guards in downstream consumers.

### BH37-030 — CHEATSHEET: check_preconditions description wrong (claims WIP enforcement)

**File:** CHEATSHEET.md line 120
**Phase:** Phase 1 (doc audit)
**Fix:** Fix description, separate WIP limit function.

### BH37-031 — CHEATSHEET: TRANSITIONS described as "dict of sets" not "list"

**File:** CHEATSHEET.md line 118
**Phase:** Phase 1 (doc audit)
**Fix:** Change "set" to "list".

### BH37-032 — CLAUDE.md config structure implies optional sections required

**File:** CLAUDE.md line 102
**Phase:** Phase 1 (doc audit)
**Fix:** Annotate `[conventions]` and `[release]` as optional.

### BH37-033 — Test name promises behavior assertions don't verify

**File:** `tests/test_verify_fixes.py:2036-2057`
**Phase:** Phase 2 (test quality L1)
**Fix:** Capture print_dry_run output and assert unknown file is reported.

### BH37-034 — Redundant duplicate assertion in test_verify_fixes.py

**File:** `tests/test_verify_fixes.py:87, 92`
**Phase:** Phase 2 (test quality L2)
**Fix:** Remove duplicate `assertIn("build_command", config["ci"])`.

### BH37-035 — assertTrue(result) on non-boolean return value

**File:** `tests/test_sprint_runtime.py:408`
**Phase:** Phase 2 (test quality L5)
**Fix:** Assert URL string content, not just truthiness.

---

## Resolved

| ID | Title | Severity | Validating Test |
|----|-------|----------|-----------------|
| BH37-001 | Shadowed TestWriteBurndown → renamed to TestWriteBurndownEdgeCases | HIGH | 1182 pass (+4); unshadowed tests now run |
| BH37-005 | TOML parser _has_closing_bracket → added bracket depth tracking | HIGH | test_multiline_nested_arrays_parsed |
| BH37-006 | Assertion-free teardown tests → added stdout capture + assertions | HIGH | test_dry_run_with_symlinks_and_generated, test_dry_run_empty_lists |
| BH37-007 | Assertion-free team_voices test → added stdout capture + assertions | HIGH | test_runs_with_no_voices |
| BH37-009 | sprint_init INDEX.md stem collision → track disambiguated stems | MEDIUM | test_index_uses_disambiguated_stems |
| BH37-011 | Dead f-prefix in release_gate.py → removed f prefix | MEDIUM | lint clean |
| BH37-012 | sync_tracking case-insensitive lookup → added .upper() | MEDIUM | suite passes |
| BH37-013 | session_context.py TOML unescape → proper escape map | MEDIUM | suite passes |
| BH37-023 | Unused imports (4 of 6) → removed + noqa for re-exports | LOW | suite passes + test_property_parsing import fix |

---

## Pattern Blocks

### PATTERN-37-A: Re-export coupling

**Items:** BH37-023, test_property_parsing, test_bugfix_regression
**Root cause:** sync_tracking re-exported `write_tf` and `_yaml_safe` from validate_config. Tests accessed these through sync_tracking's namespace instead of the source module. Removing "unused" imports broke downstream tests.
**Lesson:** Before removing an import flagged as unused, grep for `module.symbol` in tests to check for re-export coupling.

### PATTERN-37-B: INDEX/display divergence from data transformation

**Items:** BH37-009
**Root cause:** When code transforms data (e.g., disambiguating stems), the display/output code must use the transformed result, not re-derive from the original input.
**Lesson:** After any data transformation loop, ensure subsequent loops reference the transformed output, not the raw input.
