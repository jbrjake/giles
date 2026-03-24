# Phase 1: Doc-to-Implementation Claims

## HIGH Priority Claims (Predictions 1, 5)

### C-01: populate_issues.py regex on body content is code-fence safe
**Source:** CLAUDE.md says scripts parse milestone docs with story tables
**Verdict:** PARTIAL CONCERN — `us_match` at line 249 applies `re.search(r"\*\*As a\*\*\s+(.+?)...", body, re.DOTALL)` where body is the text between detail block headings. If a code block in a story detail contains `**As a**`, this would match inside the fence. However, the risk is LOW because: (a) the regex matches bold markdown syntax (`**As a**`) which is unlikely inside a code fence, (b) `parse_detail_blocks` splits on `### US-XXXX:` headings first, so `body` is one story's section, not the whole file.
**Finding:** No punchlist item — false positive. The `**As a**` pattern is markdown-specific syntax that would not appear in code fences in practice.

### C-02: check_status.py CI error parsing handles conflicting patterns
**Source:** Prediction 5 — `_first_error` uses `_FALSE_POSITIVE` and `_ERROR_KW` patterns
**Verdict:** SAFE — The implementation at lines 109-132 correctly handles the case: if both patterns match the same line, `_FALSE_POSITIVE` (which matches "0 errors" / "no failures") takes precedence via `continue`, and the error keyword is skipped. The code processes line-by-line (no cross-line leakage). The `_ANSI_RE` stripping ensures ANSI color codes don't break matching.
**Finding:** No punchlist item — prediction not confirmed.

## MEDIUM Priority Claims (Predictions 2, 3, 4, 7, 8)

### C-03: release_gate.py write_version_to_toml handles edge cases
**Source:** Prediction 2 — TOML section parsing
**Verdict:** SAFE — The regex at line 308 `r"^(?!#)\[release\]"` correctly excludes comments. The next-section detection at line 314 `r"^\[(?![\[\s\"\'])"` handles array-of-tables, quoted keys, and spaced headers. The version regex at line 319 handles both single and double quoted values.
**Finding:** No punchlist item — well-defended code.

### C-04: validate_config.py read_tf frontmatter parsing
**Source:** Prediction 3 — `re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)", content, re.DOTALL)`
**Verdict:** SAFE — The regex anchors to `^---` which requires the file to START with `---`. A `---` inside a code fence in the body would not match because `(.*?)` is non-greedy and stops at the first `\n---\s*\n`. BOM handling is present. Edge case: what if frontmatter contains a line that is exactly `---`? The non-greedy `(.*?)` would stop at that line, truncating the frontmatter. However, `---` is a YAML document separator and should not appear in valid frontmatter values. The `_yaml_safe` function would quote any value containing `---`.
**Finding:** CONCERN — If a frontmatter VALUE somehow contains a literal `---` on its own line, `read_tf` would truncate the frontmatter. However, `_yaml_safe` quotes values with YAML-sensitive characters, and `---` would need quoting. Let me check: does `_yaml_safe` quote `---`?

### C-05: extract_sp body regex on arbitrary markdown
**Source:** Prediction 3 — body may contain code blocks
**Verdict:** LOW RISK — The regexes search for specific patterns like `| SP | N |` and `story points: N`. These could theoretically match inside code blocks, but the patterns are specific enough (table format with pipes, or "story points" keyword) that false matches are unlikely in practice.
**Finding:** No punchlist item — acceptable risk.

### C-06: kanban-protocol.md preconditions match check_preconditions()
**Source:** Prediction 7 — semantic-fidelity lens
**Verdict:** MATCH — The protocol doc (lines 67-74) and check_preconditions (lines 89-134) agree on all required fields for each state. The integration entry guard (SF-002 from run 4) is present in both.
**Finding:** No punchlist item — aligned after run 4 fixes.

### C-07: Two-path state management documented vs actual behavior
**Source:** Prediction 8 — temporal-protocol lens
**Verdict:** The documentation in kanban-protocol.md (lines 96-101) and CLAUDE.md accurately describe the two-path behavior. kanban.py `do_sync` validates transitions. sync_tracking.py accepts any valid state. Both use `lock_sprint` for mutual exclusion. The `sync_tracking.sync_one` docstring at line 133 explicitly states the design difference.
**Finding:** No punchlist item — well-documented.

### C-08: _yaml_safe does not quote `---` separator
**Source:** Follow-up from C-04
**Verdict:** Checking _yaml_safe (lines 1066-1096): The function quotes values containing `: `, `#`, `,`, `\`, `\n`, `\r`, `\t`, trailing `:`, leading special chars, YAML bool keywords, numeric strings, or leading/trailing whitespace. The string `---` does NOT trigger any of these conditions. So if a frontmatter field value is literally `---`, it would be written unquoted as `field: ---`, and `read_tf` would see `---` as the frontmatter terminator, truncating all subsequent fields.
**Finding:** PUNCHLIST ITEM — `_yaml_safe` does not quote values that would be parsed as YAML document separators.

### C-09: CLAUDE.md claims all gh calls go through gh()/gh_json() wrappers
**Source:** CLAUDE.md Invariants: "All `gh` CLI calls go through `validate_config.gh()` or `validate_config.gh_json()` wrappers"
**Verdict:** Need to verify — `populate_issues.py` line 39 calls `subprocess.run(["gh", "auth", "status"])` directly, bypassing the wrapper.
**Finding:** PUNCHLIST ITEM — direct subprocess.run(["gh", ...]) bypasses the wrapper.

### C-10: CLAUDE.md says "Giles is copied (plugin-owned), not symlinked"
**Source:** CLAUDE.md Configuration System section
**Verdict:** Need to verify in sprint_init.py

### C-11: Makefile lint target covers all production scripts
**Source:** Run 1 (PAT-001) identified this gap. Run 1 added all scripts.
**Verdict:** Let me count.
