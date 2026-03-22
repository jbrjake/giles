# Hooks / Config Verification (2026-03-21)

Verification of open findings against current code in `.claude-plugin/hooks/`.

---

## 1. BH26-005 / hooks-audit FINDING-4: TOML parser escaped-quote and single-quote issues

### verify_agent_output.py — `_has_unquoted_bracket()` and `_strip_inline_comment()`

**FIXED.**

Both functions now walk character-by-character tracking quote state. They handle:
- Backslash-escaped quotes inside double-quoted strings (`\"`) — lines 37-38 and 62-63 skip the next character after a backslash when inside a double-quoted string.
- Single-quoted literal strings (no escape processing, per TOML spec) — lines 40, 65.
- `]` or `#` only match when `in_quote` is False.

Tests exist covering these cases: `test_read_toml_key_escaped_quote_with_bracket` (BH26-005) and `test_read_toml_key_inline_comment_after_escaped_quote` (BH26-005) in `tests/test_hooks.py`.

### session_context.py — `_read_toml_string`

**PARTIALLY FIXED.**

Single-quoted strings are now handled (line 39: `rf"{key}\s*=\s*'([^']*)'"`). However, the double-quoted regex on line 35 is `r'{key}\s*=\s*"([^"]*)"'` — the `[^"]*` capture group does NOT handle escaped quotes (`\"`). A TOML value like `name = "say \"hello\""` would fail to match entirely (the regex would match up to the first escaped `"` and then fail because the closing `"` doesn't follow immediately).

**Practical impact: Low.** The only keys read by this function are `sprints_dir` and `team_dir` from `[paths]`, which are directory paths unlikely to contain escaped quotes. But the parser is technically incorrect for the general case.

**Evidence:** Line 35: `m = re.match(rf'{key}\s*=\s*"([^"]*)"', stripped)` — `[^"]*` rejects any `"` character, even escaped ones.

---

## 2. hooks-audit FINDING-7: review_gate `_log_blocked` hardcoded sprints path

**FIXED.**

`_log_blocked()` (review_gate.py lines 171-203) now reads `sprints_dir` from the `[paths]` section of `project.toml` (lines 183-196). The hardcoded `"sprint-config/sprints"` on line 182 is only a fallback used when config reading fails (exception handler or missing file). This is the correct pattern — config-first with a safe fallback.

**Evidence:** Lines 183-196 parse `sprints_dir` from `[paths]` section before using it.

---

## 3. hooks-audit FINDING-10: session_context `_read_toml_string` doesn't handle subsections

**STILL OPEN (low severity).**

`_read_toml_string` checks `stripped == f"[{section}]"` (line 30), which is an exact-match comparison. When it encounters a subsection like `[paths.extra]`, the check `stripped.startswith("[")` on line 29 fires, then `stripped == "[paths]"` is False, so `in_section` is set to False. This means:

1. A subsection `[paths.extra]` would be correctly excluded (keys under it won't be read as if they belong to `[paths]`).
2. However, if a TOML file has keys for `[paths]` *after* a `[paths.extra]` subsection (unusual but valid TOML), those keys would be missed.

**Practical impact: Negligible.** Standard TOML files don't interleave parent-section keys after subsection headers. The giles `project.toml` template doesn't use subsections under `[paths]`.

**Evidence:** Line 30: `in_section = stripped == f"[{section}]"` — strict equality means any subsection header resets `in_section` to False permanently.

---

## 4. DA-007: verify_agent_output `_read_toml_key` inline comments

**FIXED.**

Line 92 of `_read_toml_key`: `val = _strip_inline_comment(m.group(1).strip())` — the function calls `_strip_inline_comment` on every value before further processing. The `_strip_inline_comment` function properly walks characters respecting quoted strings (both single and double, with escape handling).

Test exists: `test_read_toml_key_inline_comment` (DA-007) in `tests/test_hooks.py`.

**Evidence:** Line 92 calls `_strip_inline_comment()`, which is a quote-aware comment stripper (lines 26-48).

---

## 5. DA-009: Multi-line array stops at first `]` even inside quoted strings

**FIXED.**

The multi-line array accumulation loop (lines 94-98) uses `_has_unquoted_bracket()` to detect the closing `]`. As verified in Finding 1 above, `_has_unquoted_bracket` correctly tracks quote state for both single-quoted and double-quoted strings (including `\"` escape handling). A `]` inside a quoted string will not terminate the loop.

Test exists: `test_read_toml_key_bracket_inside_quotes` (DA-009) in `tests/test_hooks.py`, which tests `"pytest -k 'test[param]'"` as an array element.

**Evidence:** Line 96 calls `_has_unquoted_bracket(array_text)` which is quote-aware (lines 51-73).

---

## Summary

| # | Finding | Status | Severity if open |
|---|---------|--------|-----------------|
| 1 | BH26-005: escaped-quote handling in verify_agent_output | FIXED | — |
| 1b | BH26-005: escaped-quote handling in session_context | PARTIALLY FIXED | Low |
| 2 | FINDING-7: hardcoded sprints path in review_gate | FIXED | — |
| 3 | FINDING-10: subsections in session_context | STILL OPEN | Negligible |
| 4 | DA-007: inline comments in _read_toml_key | FIXED | — |
| 5 | DA-009: multi-line array bracket-in-quotes | FIXED | — |

### Remaining items

- **session_context.py `_read_toml_string` line 35:** The double-quoted regex `[^"]*` doesn't handle `\"` escapes. Low practical impact since only path values are read, but technically incorrect. No test coverage for this function.
- **session_context.py `_read_toml_string` subsection handling:** Strict section match means keys after a subsection won't be found. Negligible practical impact.
