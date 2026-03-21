# Bug Hunter Punchlist — Pass 30 (Pattern Siblings + Unexplored Seams)

> Generated: 2026-03-21 | Project: giles | Baseline: 1137 pass, 0 fail
> Focus: Pattern siblings from Pass 29 + first-ever seam audits of commit/epics pipelines

## Summary

| Severity | Open | Resolved | Deferred |
|----------|------|----------|----------|
| HIGH     | 0    | 0        | 0        |
| MEDIUM   | 5    | 0        | 2        |
| LOW      | 0    | 0        | 0        |

---

## Tier 2 — Fix Soon (MEDIUM)

| ID | Title | Category | Acceptance Criteria | Validation |
|----|-------|----------|---------------------|------------|
| BH30-001 | gap_scanner `if ep in changed_file` — incomplete BH29-003 fix | bug/incomplete-fix | The BH29-003 fix changed body-text matching to `re.search` with word boundaries, but left the file-path matching (6 lines later) using bare `in`. Entry point `"main"` still matches file `"domain/maintain.py"`. **Fix:** Use path-component or substring-in-filename matching instead of bare `in`. | Test: entry point `"main"` does NOT match changed file `"src/domain/maintain.py"` but DOES match `"src/main.py"`. |
| BH30-002 | commit_gate `_load_config_check_commands` reads past array boundary | bug/parser-divergence | The inline TOML parser concatenates `val + text[text.find(stripped):]` which searches through the entire rest of the file, picking up quoted strings from unrelated keys. A `build_command = "cargo build"` after `check_commands` causes any `cargo` command to be recognized as a test command. **Fix:** Replace with proper array-bounded parsing that stops at `]`. | Test: config with `check_commands = ["pytest"]` followed by `build_command = "cargo build"` → `_load_config_check_commands` returns only `["pytest"]`, not `["pytest", "cargo build"]`. |
| BH30-003 | populate_issues story ID regex uses `\d{4}` while manage_epics uses `\d+` | bug/format-mismatch | `populate_issues._DETAIL_BLOCK_RE` uses `US-\d{4}` (exactly 4 digits). `manage_epics.STORY_HEADING` uses `US-\d+` (any digits). Stories with 5+ digit IDs are invisible to populate_issues. Also `\s+` vs `\s*` after the colon. **Fix:** Align populate_issues to use `\d+` and `\s+` (the more permissive pattern). | Test: `parse_detail_blocks` correctly parses `### US-01021: Extended ID Story`. |
| BH30-004 | session_context "retro" substring matches "retroactive", "retrospective" | bug/substring-false-positive | `extract_dod_retro_additions()` uses `"retro" in line.lower()` which matches any word containing "retro" as a substring. A DoD item like "Ensure retroactive compatibility" would be injected as a retro-driven addition. **Fix:** Use `re.search(r'\bretro\b', line.lower())` or match "retro" as a standalone word/prefix. | Test: `"- Ensure retroactive compatibility"` is NOT extracted as a retro addition. `"- Added in retro: check CI before merge"` IS extracted. |
| BH30-005 | AC format mismatch: manage_epics emits `` `text` ``, populate_issues expects `` `AC-NN`: text `` | bug/format-mismatch | `_format_story_section` emits `` - [ ] `Do the thing` `` but `parse_detail_blocks` expects `` - [ ] `AC-01`: Do the thing ``. Stories added via `add_story()` silently lose all acceptance criteria during issue creation. **Fix:** Update `_format_story_section` to emit the `AC-NN:` prefix format to match populate_issues' parser. | Test: `add_story()` output contains `` `AC-01`: `` prefix; `parse_detail_blocks` finds all ACs. |

---

## Deferred

| Finding | Why deferred |
|---------|-------------|
| S30-001: --dry-run blocked by commit_gate | Design limitation of hook architecture — hooks see raw command strings, can't distinguish dry-run from real commits. Low impact. |
| Pattern-A MEDIUM findings: _state_override test docstrings, format_context weak test | Test quality issues that don't mask bugs. Real behavior is tested in adjacent tests. |

---

## Pattern Blocks

### PATTERN-30-A: Incomplete fix propagation (BH29-003 → BH30-001)

**Items:** BH30-001
**Root cause:** BH29-003 fixed body-text `in` operator to use `re.search` with word
boundaries, but the file-path `in` operator 6 lines later was left unchanged. Fixes
that address one instance of a pattern need a systematic sweep of the surrounding code.

### PATTERN-30-B: Cross-component format contracts (epics pipeline)

**Items:** BH30-003, BH30-005
**Root cause:** `manage_epics.py` and `populate_issues.py` parse the same markdown
files with different regex patterns, different format expectations, and no shared
constants. There are no cross-component tests that feed one's output into the other.

### PATTERN-30-C: Parser divergence continues (CLASS-1 pass 30)

**Items:** BH30-002
**Root cause:** `commit_gate._load_config_check_commands` has yet another hand-rolled
TOML parser that diverges from the proper parsers in `verify_agent_output._read_toml_key`
and `validate_config.parse_simple_toml`. This is the same CLASS-1 pattern identified in
Pass 25 — each component that needs config builds its own parser.
