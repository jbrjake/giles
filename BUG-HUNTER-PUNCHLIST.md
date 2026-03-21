# Bug Hunter Punchlist — Pass 37

> Generated: 2026-03-21 | Project: giles | Baseline: 1178 pass, 0 fail, 83% coverage
> Focus: Clean-slate full audit after 36 converged passes

## Summary

| Severity | Open | Resolved | Closed |
|----------|------|----------|--------|
| HIGH     | 0    | 5        | 0      |
| MEDIUM   | 0    | 14       | 0      |
| LOW      | 0    | 13       | 0      |

---

## Open

None — all 32 items resolved.

---

### BH37-029 — Unquoted TOML numeric values may cause TypeError downstream

**File:** `scripts/validate_config.py:356-359`
**Phase:** Phase 3 (adversarial)
**Note:** Design limitation — unquoted ints are correct per TOML spec. Downstream consumers should guard.

### BH37-033 — Test name promises behavior assertions don't verify

**File:** `tests/test_verify_fixes.py:2036-2057`
**Phase:** Phase 2 (test quality L1)
**Note:** Minor — classification IS tested, just not the print output.

---

## Resolved

| ID | Title | Severity | Commit |
|----|-------|----------|--------|
| BH37-001 | Shadowed TestWriteBurndown → renamed to TestWriteBurndownEdgeCases | HIGH | d7f79ed |
| BH37-005 | TOML parser _has_closing_bracket → added bracket depth tracking | HIGH | d7f79ed |
| BH37-006 | Assertion-free teardown tests → added stdout capture + assertions | HIGH | d7f79ed |
| BH37-007 | Assertion-free team_voices test → added stdout capture + assertions | HIGH | d7f79ed |
| BH37-009 | sprint_init INDEX.md stem collision → track disambiguated stems | MEDIUM | d7f79ed |
| BH37-010 | check_ci/check_prs assertions strengthened with content checks | MEDIUM | f6a0eca |
| BH37-011 | Dead f-prefix in release_gate.py → removed | MEDIUM | d7f79ed |
| BH37-012 | sync_tracking case-insensitive lookup → .upper() | MEDIUM | d7f79ed |
| BH37-013 | session_context.py TOML unescape → proper escape map | MEDIUM | d7f79ed |
| BH37-014 | Contract tests now verify argument ordering | MEDIUM | f6a0eca |
| BH37-015 | check_milestone test verifies actual SP totals | MEDIUM | 391dcee |
| BH37-016 | Added 4 boundary tests for divergence thresholds | MEDIUM | f6a0eca |
| BH37-017 | Deduplicated TestKanbanFromLabels, merged unique tests | MEDIUM | 3bf08a5 |
| BH37-018 | Replaced fragile stringified call_args with direct inspection | MEDIUM | f6a0eca |
| BH37-019 | assertTrue(len==1) → assertEqual for better messages | MEDIUM | f6a0eca |
| BH37-020 | Template count 19→20, added risk-register.md.tmpl | MEDIUM | (doc batch) |
| BH37-021 | CHEATSHEET missing functions → added 14+ entries | MEDIUM | (doc batch) |
| BH37-022 | Dangling § anchors → added to 6 scripts | MEDIUM | (doc batch) |
| BH37-023 | Unused imports (4 of 6) removed + noqa for re-exports | LOW | d7f79ed |
| BH37-024 | Reimported modules — kept, harmless due to import cache | LOW | (closed) |
| BH37-025 | commit_gate.py empty repo → fallback to git diff --cached | LOW | 391dcee |
| BH37-026 | sync_tracking collision → case-insensitive comparison | LOW | 391dcee |
| BH37-030 | CHEATSHEET check_preconditions description fixed | LOW | (doc batch) |
| BH37-031 | TRANSITIONS type corrected to "list" | LOW | (doc batch) |
| BH37-032 | CLAUDE.md [conventions]/[release] marked optional | LOW | (doc batch) |
| BH37-034 | Duplicate assertion removed | LOW | 391dcee |
| BH37-035 | assertTrue(result) → assertIs(result, True) | LOW | 391dcee |
| BH37-008 | Double-fault test → added complementary real-write test | HIGH | 20eb868 |
| BH37-027 | Smoke timestamps → added Z suffix, updated parser | LOW | 20eb868 |
| BH37-028 | First release → uses 0.1.0 without bumping | LOW | 20eb868 |
| BH37-029 | TOML numeric guard → str() on binary_path | LOW | 20eb868 |
| BH37-033 | Unknown files test → stdout capture + assertion | LOW | 20eb868 |
| BH37-023 | frontmatter_value removed from sync_tracking | LOW | 20eb868 |

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
