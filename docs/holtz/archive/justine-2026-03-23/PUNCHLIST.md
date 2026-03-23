# Holtz Punchlist
> Generated: 2026-03-23 | Project: giles | Baseline: 1205 pass, 0 fail, 0 skip

## Summary
| Severity | Open | Resolved | Deferred |
|----------|------|----------|----------|
| HIGH | 2 | 0 | 0 |
| MEDIUM | 1 | 0 | 0 |
| LOW | 1 | 0 | 0 |

## Patterns

## Pattern: PAT-001: Dual Parser Divergence
**Instances:** BJ-001, BJ-002
**Root Cause:** hooks/_common.py has its own TOML parser (read_toml_key) that was consolidated from individual hooks (BH-009) but never aligned with validate_config.py's full TOML parser. The escape processing and inline comment stripping differ.
**Systemic Fix:** Either have hooks import validate_config.py's parser, or synchronize the escape handling in _common.py to match validate_config.py exactly.
**Detection Rule:** `grep -rn 'def _unescape' --include='*.py'` -- if >1 result, investigate divergence.

## Items

### BJ-001: Hooks TOML unescape missing \b, \f, \uXXXX, \UXXXXXXXX escape sequences
**Severity:** HIGH
**Category:** design/inconsistency
**Location:** `hooks/_common.py:109`
**Status:** OPEN
**Pattern:** PAT-001
**Lens:** contract
**Predicted:** Prediction 1 (confidence: HIGH)

**Problem:** `_common.py:_unescape_basic_string` handles 5 TOML escape sequences (`\"`, `\\`, `\n`, `\t`, `\r`). `validate_config.py:_unescape_toml_string` handles 9 (adds `\b`, `\f`, `\uXXXX`, `\UXXXXXXXX`). Both parse values from the same `project.toml` file. If a config value contains `\u00e9` (e.g., an accented character in a project name), hooks will read the literal string `\u00e9` while scripts will read the character. This is a data-flow divergence at the contract boundary between hooks and scripts.

**Evidence:** `hooks/_common.py:109-138` -- the function explicitly handles only 5 escape types. Compare with `scripts/validate_config.py:280-324` which handles all 9 TOML-spec escapes.

**Discovery Chain:** read _common.py:_unescape_basic_string -> compared with validate_config.py:_unescape_toml_string -> 4 escape types missing in hooks -> data divergence on same input

**Acceptance Criteria:**
- [ ] `_common.py:_unescape_basic_string` handles `\b`, `\f`, `\uXXXX`, and `\UXXXXXXXX` escape sequences
- [ ] A test with `\u00e9` in a TOML value passes through both parsers and produces the same result

**Validation Command:**
```bash
python -c "
from hooks._common import _unescape_basic_string
from scripts.validate_config import _unescape_toml_string
s = r'caf\u00e9'
assert _unescape_basic_string(s) == _unescape_toml_string(s), f'Divergence: {_unescape_basic_string(s)!r} != {_unescape_toml_string(s)!r}'
print('OK')
"
```

### BJ-002: Hooks and validate_config have divergent inline comment stripping
**Severity:** LOW
**Category:** design/inconsistency
**Location:** `hooks/_common.py:141` vs `scripts/validate_config.py:239`
**Status:** OPEN
**Pattern:** PAT-001
**Lens:** contract
**Predicted:** Prediction 4 (confidence: HIGH)

**Problem:** Two separate `_strip_inline_comment` functions exist. The _common.py version uses `while i < len(val)` and tracks `in_quote`/`quote_char`. The validate_config.py version uses `for i, ch in enumerate(val)` and tracks `quote_char` (None vs set). Both handle escape processing differently: _common.py skips 2 chars on backslash-in-double-quote, validate_config.py uses `_count_trailing_backslashes` for even/odd parity check. The even/odd approach is more correct for edge cases like `\\\"` (escaped backslash before quote).

However, both produce the same results for all realistic TOML values in project.toml. The divergence is theoretical — it would require a value with an odd number of trailing backslashes before an inline comment, which is pathological input. Severity LOW because the practical impact is near-zero, but the code duplication is a maintenance risk.

**Evidence:** Compare `hooks/_common.py:141-159` with `scripts/validate_config.py:239-252`. Different loop styles, different escape tracking.

**Discovery Chain:** found two `_strip_inline_comment` functions -> compared implementations -> different escape tracking approaches -> theoretical divergence on pathological input

**Acceptance Criteria:**
- [ ] Single `_strip_inline_comment` function used by both codebases, OR documented reason for the divergence
- [ ] Test covering `value = '"test\\\\"  # comment'` (escaped backslash before closing quote followed by comment) passes through both

**Validation Command:**
```bash
python -c "
from hooks._common import _strip_inline_comment as h_strip
from scripts.validate_config import _strip_inline_comment as v_strip
test = '\"test\\\\\\\\\"  # comment'
assert h_strip(test) == v_strip(test), f'Divergence: {h_strip(test)!r} != {v_strip(test)!r}'
print('OK')
"
```

### BJ-003: session_context.extract_high_risks uses raw pipe split while risk_register uses escaped-pipe-aware split
**Severity:** MEDIUM
**Category:** bug/logic
**Location:** `hooks/session_context.py:114`
**Status:** OPEN
**Determinism:** deterministic
**Lens:** data-flow
**Predicted:** Prediction 5 (confidence: MEDIUM)

**Problem:** `session_context.py:extract_high_risks` splits markdown table rows using `line.split("|")`, which treats escaped pipes (`\|`) the same as column delimiters. `risk_register.py:_split_table_row` correctly uses `re.split(r'(?<!\\)\|', line)` to respect escaped pipes. If a risk title contains a literal pipe character (escaped as `\|`), session_context will split it into extra columns, shifting the severity and status columns and potentially misidentifying a risk as high-severity or missing it entirely.

**Evidence:** `hooks/session_context.py:114`: `cells = [c.strip() for c in line.split("|")]` -- raw split. `scripts/risk_register.py:74`: `cells = [c.strip() for c in re.split(r'(?<!\\)\|', line)]` -- escaped-pipe-aware split.

**Discovery Chain:** session_context reads risk-register.md -> risk_register writes risk-register.md with escaped pipes -> session_context splits on all pipes -> column positions shift when title contains `\|`

**Acceptance Criteria:**
- [ ] `session_context.extract_high_risks` uses escaped-pipe-aware splitting consistent with `risk_register._split_table_row`
- [ ] Test: a risk with title `"Auth \| AuthZ boundary"` and severity HIGH is correctly extracted by session_context

**Validation Command:**
```bash
python -c "
from hooks.session_context import extract_high_risks
import tempfile, os
with tempfile.TemporaryDirectory() as td:
    risk_md = os.path.join(td, 'risk-register.md')
    with open(risk_md, 'w') as f:
        f.write('# Risk Register\n\n')
        f.write('| ID | Title | Severity | Status | Raised | Sprints Open | Resolution |\n')
        f.write('|----|-------|----------|--------|--------|-------------|------------|\n')
        f.write('| R1 | Auth \| AuthZ boundary | High | Open | 2026-03-01 | 1 | |\n')
    risks = extract_high_risks(td)
    assert len(risks) == 1, f'Expected 1 risk, got {len(risks)}: {risks}'
    print('OK')
"
```

### BJ-004: test_hexwise_setup assertIsNotNone checks are rubber stamps
**Severity:** HIGH
**Category:** test/shallow
**Location:** `tests/test_hexwise_setup.py:161-175`
**Status:** OPEN
**Lens:** contract
**Predicted:** Prediction 2 (confidence: HIGH)

**Problem:** Lines 161-175 of test_hexwise_setup.py contain 12 `assertIsNotNone` assertions checking deep doc detection results (prd_dir, test_plan_dir, sagas_dir, epics_dir, story_map). These assertions verify that detection returned something but not that it returned the CORRECT path. A detection that returned `/tmp/wrong/path` would pass these tests. This is anti-pattern #11 (Rubber Stamp) — the test checks structure (not None) without checking value (correct path).

**Evidence:**
```python
self.assertIsNotNone(get_prd_dir(config))      # line 161
self.assertIsNotNone(get_test_plan_dir(config))  # line 162
self.assertIsNotNone(get_sagas_dir(config))      # line 163
self.assertIsNotNone(get_epics_dir(config))      # line 164
self.assertIsNotNone(get_story_map(config))      # line 165
```

These should assert the specific paths, e.g., `assertEqual(get_prd_dir(config), Path(...))`.

**Discovery Chain:** scanned test files for assertIsNotNone pattern -> found 12 instances checking detection results -> none verify the actual path returned -> rubber stamp: pass with any non-None value

**Acceptance Criteria:**
- [ ] Each `assertIsNotNone` for deep doc detection is replaced with `assertEqual` checking the expected path
- [ ] Tests would fail if a detection returned an incorrect but non-None path

**Validation Command:**
```bash
python -m pytest tests/test_hexwise_setup.py -v -k "deep_doc" 2>&1 | tail -5
```
