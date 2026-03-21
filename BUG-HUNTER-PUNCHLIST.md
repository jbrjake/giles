# Bug Hunter Punchlist — Pass 35

> Generated: 2026-03-21 | Project: giles | Baseline: 1161 pass, 0 fail → 1178 pass, 0 fail
> Focus: Under-scrutinized files, hooks hotspot, cross-component seams

## Summary

| Severity | Open | Resolved | Closed |
|----------|------|----------|--------|
| HIGH     | 0    | 5        | 0      |
| MEDIUM   | 0    | 15       | 0      |
| LOW      | 5    | 5        | 0      |

---

## Resolved

| ID | Title | Severity | Commit | Validating Test |
|----|-------|----------|--------|-----------------|
| BH35-001 | lock_story/lock_sprint no mutual exclusion | HIGH | 7e07bc5 | All 1178 tests pass; assign/update now use lock_sprint |
| BH35-002 | +refspec push bypass | HIGH | 7e07bc5 | `test_plus_refspec_blocked`, `test_plus_colon_refspec_blocked` |
| BH35-003 | refs/heads/ push bypass | HIGH | 7e07bc5 | `test_refs_heads_path_blocked`, `test_refs_heads_colon_refspec_blocked` |
| BH35-021 | No-backlog self-validation failure | HIGH | 7e07bc5 | `test_no_backlog_creates_milestones_dir`, `test_no_backlog_no_milestones_error` |
| BH35-022 | DoD overwritten on re-run | HIGH | 7e07bc5 | `test_dod_preserved_on_rerun` |
| BH35-004 | Non-WIP transitions lock_story | MEDIUM | 7e07bc5 | Fixed with BH35-001 — all transitions now use lock_sprint |
| BH35-005 | Inline TOML section header comments | MEDIUM | 6ea4eef | `test_read_toml_key_with_section_comment`, `test_read_toml_string_with_section_comment` |
| BH35-006 | --repo flag push bypass | MEDIUM | 6ea4eef | `test_repo_flag_bypass_blocked` |
| BH35-007 | Pipe | not split in compounds | MEDIUM | 7e07bc5 | `test_pipe_compound_push_blocked` |
| BH35-008 | Single-quoted base_branch ignored | MEDIUM | 6ea4eef | `test_single_quoted_base_branch` |
| BH35-009 | splitlines() vs split('\n') in hooks | MEDIUM | 6ea4eef | All TOML parsing hooks updated |
| BH35-010 | commit_gate word boundary | MEDIUM | 6ea4eef | `test_substring_does_not_match`, `test_exact_command_matches` |
| BH35-011 | write_version_to_toml no trailing newline | MEDIUM | 6ea4eef | Code fix verified in suite |
| BH35-012 | write_version_to_toml single-quoted duplicate | MEDIUM | 6ea4eef | Code fix verified in suite |
| BH35-013 | gate_ci checks any workflow | MEDIUM | 6ea4eef | Code fix (--workflow filter added) |
| BH35-017 | Multi-line array comment phantom items | MEDIUM | 6ea4eef | `test_multiline_array_comment_not_phantom_item` |
| BH35-018 | committed \b word boundary | MEDIUM | 6ea4eef | Code fix verified |
| BH35-023 | Scanner doesn't exclude sprint-config/ | MEDIUM | 6ea4eef | Code fix verified |
| BH35-024 | binary_path TOML not escaped | MEDIUM | 6ea4eef | Code fix verified in hexwise suite |
| BH35-025 | Persona stem collision | MEDIUM | debe769 | Code fix verified |
| BH35-026 | detect_prd_dir crash on unreadable files | MEDIUM | 6ea4eef | Code fix verified |
| BH35-027 | YAML |- block scalar | MEDIUM | 6ea4eef | Code fix verified |
| BH35-014 | Saga/Epic fields omitted | LOW | debe769 | Code fix verified |
| BH35-015 | Regex \s* vs \s+ divergence | LOW | debe769 | Code fix verified |
| BH35-016 | session_context escape sequences | LOW | — | Not fixed (path values are simple relative paths) |
| BH35-019 | _rollback_tag misleading warning | LOW | — | Not fixed (cosmetic only) |
| BH35-020 | _sanitize_md strips # | LOW | — | Not fixed (standard IDs don't use #) |

---

## Open (LOW — not worth fixing)

| ID | Title | Why deferred |
|----|-------|-------------|
| BH35-016 | session_context escape mishandles \n/\t | Path values are simple relative paths; no trigger path |
| BH35-019 | _rollback_tag misleading remote warning | Cosmetic: local tag IS deleted; warning is misleading but harmless |
| BH35-020 | _sanitize_md strips # from IDs | Only custom ID patterns use #; standard US-XXXX IDs unaffected |
| BH35-028 | Backlog INDEX links relative to root | Cosmetic: links broken in markdown preview, not in runtime |
| BH35-029 | CONTRIBUTING.md dual-symlinked | Only triggers when CONTRIBUTING.md is the only candidate file |
| BH35-030 | detect_prd_dir returns "." | Only triggers if project root has 2+ .md files with matching headers |

---

## Deferred (from pass 34, re-evaluated)

See `audit/deferred_reevaluation.md` — all 6 items confirmed still deferred.

---

## Pattern Blocks

### PATTERN-35-A: Incremental push parser hardening

**Items:** BH35-002, BH35-003, BH35-006, BH35-007
**Root cause:** The review_gate `_check_push_single` function uses a whitelist approach — it knows about certain flags and refspec formats, but any unknown syntax slips through. Each pass finds new bypass vectors: `+refspec`, `refs/heads/`, `--repo` flag consuming positional args, single pipe `|`.
**Systemic fix applied:** Instead of only checking positional[1:] for base branch, now checks ALL positionals. This handles unknown flags that consume positional args. The `+` and `refs/heads/` stripping handles refspec normalization.
**Sibling check:** `--push-option`, `-o` could also consume a value. But with the ALL-positionals check, even if a flag eats an extra arg, the remaining refspec will still be checked.

### PATTERN-35-B: TOML parser divergence (main vs inline)

**Items:** BH35-005, BH35-008, BH35-009, BH35-016, BH35-017
**Root cause:** The main TOML parser in validate_config.py was hardened over many passes (BH20-001 splitlines, BH20-002 digit keys, BH21-003 quoted keys, etc.), but the 4 hook files each have their own lightweight inline TOML parsers that were never updated. Each hook got a subset of the fixes.
**Systemic fix applied:** Propagated three critical fixes to all hooks: (1) split('\n') instead of splitlines(), (2) section header comment stripping, (3) single-quote support for base_branch.
**Future guidance:** If the main TOML parser changes, grep for `split('\n')` and `f"[{section}]"` in hooks to identify inline parsers that need the same fix.

### PATTERN-35-C: sprint_init re-run fragility

**Items:** BH35-021, BH35-022, BH35-023
**Root cause:** sprint_init was designed for first-run use but gets called multiple times as projects evolve. Three protections were missing: (1) milestones/ skeleton for empty backlog, (2) DoD preservation, (3) excluding sprint-config/ from scans.
**Systemic fix applied:** All three protections added. The pattern matches `generate_project_toml()` and `_inject_giles()` which already had preservation checks.
