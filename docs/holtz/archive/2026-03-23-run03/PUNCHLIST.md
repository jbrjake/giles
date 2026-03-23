# Holtz Punchlist (Run 3 — Merged)
> Generated: 2026-03-23 | Project: giles | Baseline: 1205 pass, 0 fail, 0 skip

## Summary
| Severity | Open | Resolved | Deferred |
|----------|------|----------|----------|
| CRITICAL | 0 | 0 | 0 |
| HIGH | 0 | 0 | 0 |
| MEDIUM | 0 | 3 | 0 |
| LOW | 0 | 2 | 0 |

## Patterns

(Inherited from prior runs: PAT-001 batch wiring, PAT-002 hook inconsistency, PAT-003 TOML divergence — all code-level resolved)

## Pattern: PAT-004: Dual Parser Divergence (hooks vs scripts)
**Instances:** BK-002, BK-003
**Root Cause:** hooks/_common.py was consolidated from individual hooks (BH-009) but was never fully aligned with validate_config.py's TOML parser. The hooks parser is a lightweight subset — intentional for isolation, but the subset has gaps for edge-case inputs.
**Systemic Fix:** Add missing escape sequences to _common.py's _unescape_basic_string. The inline comment stripping divergence is theoretical and lower priority.
**Detection Rule:** `grep -rn 'def _unescape' --include='*.py'` — if >1 result, compare escape handling.

## Items

### BK-001: Stale backward-compat comments from BH-009 TOML consolidation
**Severity:** LOW
**Category:** doc/drift
**Location:** `hooks/verify_agent_output.py:29-36`, `hooks/session_context.py:20`
**Status:** RESOLVED
**Pattern:** PAT-003 (residual artifact)
**Lens:** component
**Predicted:** Prediction 1 (confidence: HIGH)

**Problem:** Two hooks contain stale comments claiming their TOML wrapper functions exist for backward compatibility with commit_gate imports. After the BH-009 fix in Run 2, commit_gate no longer imports from verify_agent_output — it imports `read_toml_key` directly from `_common.py`. The aliases/wrappers are used internally but the stated rationale is misleading.

**Evidence:**
- `verify_agent_output.py:29`: "Legacy wrappers kept for backward compatibility with commit_gate import"
- `commit_gate.py:20`: Actually imports `read_toml_key` from `_common` (not verify_agent_output)

**Discovery Chain:** Architecture drift scan → checked commit_gate imports → confirmed commit_gate imports from _common → backward-compat comments are stale

**Acceptance Criteria:**
- [ ] Comments accurately describe the actual purpose of each wrapper/alias
- [ ] No test regressions

**Validation Command:**
```bash
grep -n "backward compat" hooks/verify_agent_output.py hooks/session_context.py | grep -c "commit_gate"
# Expected: 0
```

**Resolution:** Updated comments in both files to accurately describe the purpose of each wrapper/alias. Removed stale references to commit_gate backward compatibility.

### BK-002: Hooks TOML unescape missing \b, \f, \uXXXX, \UXXXXXXXX escape sequences
**Severity:** MEDIUM
**Category:** design/inconsistency
**Location:** `hooks/_common.py:109`
**Status:** RESOLVED
**Pattern:** PAT-004
**Lens:** contract
**Source:** Justine (BJ-001)

**Problem:** `_common.py:_unescape_basic_string` handles 5 TOML escape sequences (`\"`, `\\`, `\n`, `\t`, `\r`). `validate_config.py:_unescape_toml_string` handles 9 (adds `\b`, `\f`, `\uXXXX`, `\UXXXXXXXX`). Both parse values from the same `project.toml` file. If a config value contains `\u00e9`, hooks read the literal string while scripts read the character.

**Evidence:** `hooks/_common.py:109-138` handles 5 escapes. `scripts/validate_config.py:280-324` handles all 9.

**Discovery Chain:** Justine cross-module comparison → _common.py handles 5 escapes → validate_config.py handles 9 → divergent output for same input on Unicode escapes

**Acceptance Criteria:**
- [ ] `_common.py:_unescape_basic_string` handles `\b`, `\f`, `\uXXXX`, and `\UXXXXXXXX`
- [ ] Test: `\u00e9` in a TOML value produces same result through both parsers

**Validation Command:**
```bash
python3 -c "
import sys; sys.path.insert(0, 'hooks'); sys.path.insert(0, 'scripts')
from _common import _unescape_basic_string
from validate_config import _unescape_toml_string
s = r'caf\u00e9'
a, b = _unescape_basic_string(s), _unescape_toml_string(s)
assert a == b, f'Divergence: {a!r} != {b!r}'
print('PASS')
"
```

**Resolution:** Added `\b`, `\f`, `\uXXXX`, `\UXXXXXXXX` escape handling to `_common.py:_unescape_basic_string`. 5 new tests (parity, backspace/formfeed, unicode-4, unicode-8, invalid-preserved). 1211 tests pass.

### BK-003: session_context.extract_high_risks uses raw pipe split
**Severity:** MEDIUM
**Category:** bug/logic
**Location:** `hooks/session_context.py:114`
**Status:** RESOLVED
**Determinism:** deterministic
**Lens:** data-flow
**Source:** Justine (BJ-003)

**Problem:** `session_context.extract_high_risks` splits markdown table rows using `line.split("|")`, which treats escaped pipes (`\|`) the same as column delimiters. `risk_register.py:_split_table_row` uses `re.split(r'(?<!\\)\|', line)` to respect escaped pipes. If a risk title contains a literal pipe character, session_context will misparse column positions and may miss high-severity risks or misidentify them.

**Evidence:** `hooks/session_context.py:114`: `cells = [c.strip() for c in line.split("|")]` — raw split. `scripts/risk_register.py:74`: `re.split(r'(?<!\\)\|', line)` — escaped-pipe-aware.

**Discovery Chain:** Justine cross-module comparison → session_context reads risk-register.md → risk_register writes with escaped pipes → raw split shifts columns on pipe-containing titles

**Acceptance Criteria:**
- [ ] `session_context.extract_high_risks` handles escaped pipes in risk titles
- [ ] Test: a risk with title containing `\|` is correctly identified as HIGH severity

**Validation Command:**
```bash
python3 -c "
import sys, tempfile, os; sys.path.insert(0, 'hooks')
from session_context import extract_high_risks
with tempfile.TemporaryDirectory() as td:
    rp = os.path.join(td, 'risk-register.md')
    with open(rp, 'w') as f:
        f.write('# Risk Register\n\n| ID | Title | Severity | Status | Raised | Sprints Open | Resolution |\n|----|-------|----------|--------|--------|-------------|------------|\n')
        f.write('| R1 | Auth \| AuthZ boundary | High | Open | 2026-03-01 | 1 | |\n')
    risks = extract_high_risks(td)
    assert len(risks) == 1, f'Expected 1 risk, got {len(risks)}: {risks}'
    print('PASS')
"
```

**Resolution:** Replaced `line.split("|")` with `re.split(r'(?<!\\)\|', line)` in `session_context.extract_high_risks`. 1 new test for escaped-pipe risk titles. 1211 tests pass.

### BK-004: test_hexwise_setup deep doc assertions are rubber stamps
**Severity:** MEDIUM
**Category:** test/shallow
**Location:** `tests/test_hexwise_setup.py:161-165`
**Status:** RESOLVED
**Lens:** contract
**Source:** Justine (BJ-004)

**Problem:** `test_generated_config_has_deep_doc_paths` (lines 161-165) uses 5 `assertIsNotNone` checks for deep doc detection results. These verify that detection returned something but not the correct paths. A detection that returned `/tmp/wrong/path` would pass. The sister test `test_scanner_detects_hexwise_deep_docs` (lines 171-179) has both `assertIsNotNone` AND `assertIn` content checks (BH-013), but the config test does not.

**Evidence:** Lines 161-165: bare `assertIsNotNone(get_prd_dir(config))` etc. Compare with lines 177-179 which add `assertIn("prd", ...)`.

**Discovery Chain:** Justine test audit → assertIsNotNone pattern scan → 5 instances with no value verification → sister test has content checks but this test does not → rubber stamp

**Acceptance Criteria:**
- [ ] Each `assertIsNotNone` in `test_generated_config_has_deep_doc_paths` replaced with or supplemented by value assertions
- [ ] Tests would fail if detection returned an incorrect but non-None path

**Validation Command:**
```bash
python3 -m pytest tests/test_hexwise_setup.py::TestHexwiseSetup::test_generated_config_has_deep_doc_paths -v 2>&1 | tail -5
```

**Resolution:** Replaced 5 `assertIsNotNone` with `assertIsNotNone` + `assertIn` checking expected directory names (prd, test-plan, sagas, epics, story-map). 1211 tests pass.

### BK-005: Two separate _strip_inline_comment implementations with divergent escape handling
**Severity:** LOW
**Category:** design/inconsistency
**Location:** `hooks/_common.py:141` vs `scripts/validate_config.py:239`
**Status:** RESOLVED
**Pattern:** PAT-004
**Lens:** contract
**Source:** Justine (BJ-002)

**Problem:** Two `_strip_inline_comment` functions exist with different escape tracking. `_common.py` uses `while` loop with `in_quote`/`quote_char` and skips 2 chars on backslash. `validate_config.py` uses `for`/`enumerate` with `_count_trailing_backslashes` parity check. The parity check is more correct for edge cases like `\\\\"` (even number of trailing backslashes). Theoretical divergence only — would require pathological TOML input.

**Evidence:** Different loop styles and escape tracking in the two implementations.

**Discovery Chain:** Justine cross-module comparison → two `_strip_inline_comment` functions → different escape handling strategies → theoretical divergence on edge cases

**Acceptance Criteria:**
- [ ] Either consolidated into one function, or documented reason for the divergence
- [ ] Test covering edge case with consecutive backslashes before inline comment

**Validation Command:**
```bash
python3 -c "
import sys; sys.path.insert(0, 'hooks'); sys.path.insert(0, 'scripts')
from _common import _strip_inline_comment as h
from validate_config import _strip_inline_comment as v
test = '\"val\\\\\\\\\"  # comment'
assert h(test) == v(test), f'Divergence: {h(test)!r} != {v(test)!r}'
print('PASS')
"
```

**Resolution:** Replaced _common.py's skip-2-chars approach with validate_config.py's parity-check algorithm. Added `_count_trailing_backslashes` to _common.py. 9 new parity tests. 1220 tests pass.
