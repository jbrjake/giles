# TOML Parser Audit (`parse_simple_toml`)

**File**: `scripts/validate_config.py` lines 125-397
**Method**: Static trace of all code paths (Bash denied; no runtime execution)
**Date**: 2026-03-16

---

## Test Results

### Test 1: Inline comments in strings
- **Input**: `key = "hello # world"`
- **Expected**: `{"key": "hello # world"}`
- **Actual (traced)**: `{"key": "hello # world"}`
- **Result**: PASS -- `_strip_inline_comment` correctly tracks quote state and ignores `#` inside double quotes.

### Test 2: Escaped quotes
- **Input**: `key = "say \"hello\""`
- **Expected**: `{"key": 'say "hello"'}`
- **Actual (traced)**: `{"key": 'say "hello"'}`
- **Result**: PASS -- `_strip_inline_comment` uses `_count_trailing_backslashes` to detect escaped quotes. `_unescape_toml_string` converts `\"` to `"`.

### Test 3: Single-quoted strings (literal, no escapes)
- **Input**: `key = 'no \n escapes'`
- **Expected**: `{"key": "no \\n escapes"}` (literal backslash-n, not newline)
- **Actual (traced)**: `{"key": "no \\n escapes"}`
- **Result**: PASS -- Single-quoted strings skip `_unescape_toml_string` and return `raw[1:-1]` verbatim, per TOML spec.

### Test 4: Mixed quote arrays
- **Input**: `arr = ["double", 'single']`
- **Expected**: `{"arr": ["double", "single"]}`
- **Actual (traced)**: `{"arr": ["double", "single"]}`
- **Result**: PASS -- `_split_array` tracks both quote types. Each element parsed independently.

### Test 5: Nested arrays
- **Input**: `arr = [["a", "b"], ["c"]]`
- **Expected**: `{"arr": [["a", "b"], ["c"]]}`
- **Actual (traced)**: `{"arr": [["a", "b"], ["c"]]}`
- **Result**: PASS -- `_split_array` tracks bracket depth; top-level comma splits correctly. `_parse_value` recurses on sub-arrays.

### Test 6: Empty array
- **Input**: `arr = []`
- **Expected**: `{"arr": []}`
- **Actual (traced)**: `{"arr": []}`
- **Result**: PASS -- Explicit empty-inner check on line 311.

### Test 7: Trailing comma
- **Input**: `arr = ["a", "b",]`
- **Expected**: `{"arr": ["a", "b"]}`
- **Actual (traced)**: `{"arr": ["a", "b"]}`
- **Result**: PASS -- `_split_array` produces a final empty part after the trailing comma. The empty part is discarded by `if current.strip()` (line 386) and `if part` (line 316).

### Test 8: Integer with leading zero
- **Input**: `val = 007`
- **Expected (TOML spec)**: ERROR (leading zeros forbidden on integers)
- **Actual (traced)**: `{"val": 7}` (Python `int("007")` silently strips zeros)
- **Result**: SPEC DEVIATION -- The parser accepts `007` and returns `7`. TOML spec forbids leading zeros on integers. Not likely to cause real bugs since the project doesn't use leading-zero integers in `project.toml`, but it means malformed TOML is silently accepted.

### Test 9: Negative integers
- **Input**: `val = -42`
- **Expected**: `{"val": -42}`
- **Actual (traced)**: `{"val": -42}`
- **Result**: PASS -- Python `int("-42")` succeeds.

### Test 10: Multiline array with inline comments
- **Input**:
  ```
  arr = [
    "a",  # first
    "b",  # second
  ]
  ```
- **Expected**: `{"arr": ["a", "b"]}`
- **Actual (traced)**: `{"arr": ["a", "b"]}`
- **Result**: PASS -- `_strip_inline_comment` removes comments per continuation line. Trailing comma handled. Closing `]` detected by `_has_closing_bracket`.

### Test 11: Key with hyphen
- **Input**: `my-key = "value"`
- **Expected**: `{"my-key": "value"}`
- **Actual (traced)**: `{"my-key": "value"}`
- **Result**: PASS -- Key regex `[a-zA-Z_][a-zA-Z0-9_-]*` allows hyphens after first char.

### Test 12: Section with hyphen
- **Input**: `[my-section]`
- **Expected**: Section `my-section` created
- **Actual (traced)**: Correctly matched by header regex `[a-zA-Z0-9_][a-zA-Z0-9_.-]*`
- **Result**: PASS

### Test 13: Dotted section
- **Input**: `[section.subsection]`
- **Expected**: `{"section": {"subsection": {}}}`
- **Actual (traced)**: Correctly splits on `.` and creates nested dicts via `setdefault`
- **Result**: PASS

### Test 14: Re-opening a section
- **Input**:
  ```
  [project]
  name = "foo"
  [other]
  x = 1
  [project]
  version = 2
  ```
- **Expected**: Merge -- `{"project": {"name": "foo", "version": 2}, "other": {"x": 1}}`
- **Actual (traced)**: Merge (correct) -- `setdefault` returns the existing dict, doesn't overwrite.
- **Result**: PASS -- Correct TOML behavior.

### Test 15: Value that looks like a section
- **Input**: `key = "[not a section]"`
- **Expected**: `{"key": "[not a section]"}`
- **Actual (traced)**: `{"key": "[not a section]"}`
- **Result**: PASS -- Line doesn't match section regex (starts with `key`, not `[`). Matched as key=value, quoted string parsed correctly.

### Test 16: Boolean keywords
- **Input A**: `val = true` -- **Actual**: `True` (bool) -- **PASS**
- **Input B**: `val = false` -- **Actual**: `False` (bool) -- **PASS**
- **Input C**: `val = True` -- **Actual**: `"True"` (string)
- **Result**: SPEC DEVIATION on input C. TOML booleans are case-sensitive (`true`/`false` only). `True` is invalid TOML and should error. Parser silently returns the raw string `"True"`. Downstream code using `if config["val"]:` gets truthy from the non-empty string, so behavior accidentally works but for the wrong reason. Code using `config["val"] is True` or `== True` would fail silently.

### Test 17: Unquoted string with equals
- **Input**: `key = foo = bar`
- **Expected**: Error
- **Actual (traced)**: `ValueError` raised -- metacharacter check finds `=` in the raw value.
- **Result**: PASS -- BH-002 guard works correctly.

---

## Additional Findings

### Finding A: Keys starting with digits are silently ignored (BUG)

The key regex on line 182 is:
```
^([a-zA-Z_][a-zA-Z0-9_-]*)\s*=\s*(.*)$
```

The first character class `[a-zA-Z_]` excludes digits. A line like `1key = "val"` would not match the key regex, and it also wouldn't match the section header or comment patterns, so it is **silently ignored** -- no error, no warning, the key just disappears.

TOML spec allows bare keys to start with digits: the allowed bare key characters are `[A-Za-z0-9_-]`. For example, `1st = "first"` is valid TOML.

**Severity**: Low for this project (no `project.toml` keys start with digits), but violates TOML spec silently. If someone added such a key, it would vanish with no error message.

**Fix**: Change the key regex first character class to `[a-zA-Z0-9_]` to match the TOML spec, or add an else-branch that warns about unparseable lines.

### Finding B: Inconsistent first-char rules between keys and section headers

Section header regex (line 170): `[a-zA-Z0-9_]` -- allows digit-start.
Key regex (line 182): `[a-zA-Z_]` -- forbids digit-start.

This means `[1section]` is accepted as a valid section, but `1key = "val"` under it is silently dropped. Inconsistent.

### Finding C: `current_section` is a dead variable

`current_section` is assigned on lines 138 and 176 but never read after assignment. All key storage goes through `_set_nested(root, section_path, key, value)` which navigates from `root` using `section_path`. The `current_section` variable exists in the code but serves no purpose. It's not harmful (no bug), but it's misleading -- a reader might think it's used for key storage.

### Finding D: Unparseable lines are silently dropped

If a line matches neither the comment/blank check, the section header regex, nor the key-value regex, it falls through with no action and no warning. Examples of silently dropped lines:
- `1key = "val"` (digit-start key, as noted above)
- `key with spaces = "val"` (spaces in key name)
- `= "no key"` (missing key)
- `just some random text` (no `=` sign)

A strict parser would error. A lenient parser should at least warn. This parser does neither.

**Severity**: Low to medium. Most malformed lines are likely to be caught during manual review, but a typo that breaks a key name would cause silent config loss.

### Finding E: Float values are parsed as strings

Input like `val = 3.14` would fail `int("3.14")`, contain no metacharacters, and fall through to the raw-string return. Result: string `"3.14"`, not float `3.14`.

The project doesn't use floats in `project.toml`, so this is a known limitation rather than a bug. Documented here for completeness.

### Finding F: Multiline string detection is incomplete

The parser checks for `"""` and `'''` at the START of a value (line 294) and raises ValueError. But the TOML multiline string syntax is `"""..."""` and `'''...'''`. If someone wrote:

```
key = "not triple" """but this follows"""
```

The value starts with `"`, not `"""`, so it would hit the double-quote path and produce a mangled result. This is an extreme edge case unlikely to occur in practice.

### Finding G: Inline table syntax `{}` is not supported

TOML allows inline tables: `key = {a = 1, b = 2}`. The parser has no inline table handling. If encountered, the `{` would be caught by the metacharacter check (line 328) and raise ValueError. This is correct behavior (fail loudly rather than silently) for an unsupported feature.

---

## Summary

| # | Scenario | Result |
|---|----------|--------|
| 1 | Inline comments in strings | PASS |
| 2 | Escaped quotes | PASS |
| 3 | Single-quoted strings | PASS |
| 4 | Mixed quote arrays | PASS |
| 5 | Nested arrays | PASS |
| 6 | Empty array | PASS |
| 7 | Trailing comma | PASS |
| 8 | Leading zero integer | SPEC DEVIATION (accepts `007` as `7`) |
| 9 | Negative integers | PASS |
| 10 | Multiline array + comments | PASS |
| 11 | Key with hyphen | PASS |
| 12 | Section with hyphen | PASS |
| 13 | Dotted section | PASS |
| 14 | Re-opening section | PASS (merges correctly) |
| 15 | Value looks like section | PASS |
| 16 | Boolean case sensitivity | SPEC DEVIATION (`True` -> string, not error) |
| 17 | Unquoted string with `=` | PASS (raises ValueError) |

**Bugs found**: 1 (digit-start keys silently ignored -- Finding A)
**Spec deviations**: 2 (leading-zero integers, case-insensitive booleans)
**Code quality**: 1 dead variable (`current_section`), silent drop of unparseable lines
**Known limitations**: no floats, no inline tables, no multiline strings (all by design)

All findings are based on static code tracing. Runtime confirmation recommended.
