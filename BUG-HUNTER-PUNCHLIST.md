# Bug Hunter Punchlist — Pass 32 (AC Verification)

> Generated: 2026-03-21 | Project: giles | Baseline: 1148 pass, 0 fail
> Focus: Close remaining open items from Pass 30 with acceptance-criteria tests

## Summary

| Severity | Open | Resolved | Deferred |
|----------|------|----------|----------|
| HIGH     | 0    | 0        | 0        |
| MEDIUM   | 0    | 5        | 0        |
| LOW      | 0    | 0        | 0        |

---

## Resolved (Pass 32)

| ID | Title | Resolution | Validating Test |
|----|-------|------------|-----------------|
| BH30-001 | gap_scanner path matching | Code fix + 5 tests already in place | `test_new_scripts.py::test_path_matches_*` (5 tests) |
| BH30-002 | TOML parser array boundary bleed | Code delegated to `_read_toml_key`; AC test added | `test_hooks.py::test_read_toml_key_does_not_bleed_past_array` |
| BH30-003 | story ID regex \d{4} vs \d+ | Regex aligned to \d+; AC test added | `test_hexwise_setup.py::test_parse_detail_blocks_five_digit_id` |
| BH30-004 | session_context "retro" substring | Word boundary match; AC test added | `test_hooks.py::test_retro_extraction_rejects_retroactive_substring` |
| BH30-005 | AC format mismatch epics↔populate | AC-NN prefix format + round-trip test | `test_pipeline_scripts.py::test_format_story_section_ac_prefix_format` |

---

## Deferred (from Pass 30, resolved in Pass 31)

| Finding | Resolution |
|---------|------------|
| S30-001: --dry-run blocked | commit_gate now allows --dry-run through (Pass 31) |
| Pattern-A: misleading test docstrings | Docstrings corrected, tests strengthened (Pass 31) |

---

## Pattern Blocks (from Pass 30, all resolved)

### PATTERN-30-A: Incomplete fix propagation (BH29-003 → BH30-001)
**Status:** RESOLVED — path matching fixed + tested

### PATTERN-30-B: Cross-component format contracts (epics pipeline)
**Status:** RESOLVED — regex aligned (BH30-003), AC format aligned (BH30-005), round-trip test added

### PATTERN-30-C: Parser divergence continues (CLASS-1 pass 30)
**Status:** RESOLVED — commit_gate now delegates to verify_agent_output._read_toml_key (BH30-002)
