# Bug Hunter Punchlist — Pass 20

> Generated: 2026-03-16 | Project: giles | Baseline: 773 pass, 0 fail (1 hypothesis failure pre-fix) | Coverage: 85%
> Method: Hypothesis-discovered bugs, TOML parser edge cases, coverage hole analysis, skeleton template validation

## Summary

| Severity | Open | Resolved | Deferred |
|----------|------|----------|----------|
| CRITICAL | 0    | 1        | 0        |
| HIGH     | 0    | 0        | 0        |
| MEDIUM   | 0    | 3        | 1        |
| LOW      | 0    | 0        | 3        |

## Items

### BH20-001: parse_simple_toml splitlines() treats U+2028/U+2029 as line breaks — crashes on unicode strings
**Severity:** CRITICAL
**Category:** `bug/crash`
**Location:** `scripts/validate_config.py:143` (parse_simple_toml)
**Status:** ✅ RESOLVED — replaced splitlines() with split('\n')

**Problem:** Python's `str.splitlines()` treats U+2028 (Line Separator) and U+2029 (Paragraph Separator) as line boundaries. A TOML string containing these characters would be split mid-value, causing the parser to see an unterminated multiline array and raise ValueError.

**Evidence:** Found by hypothesis property test `test_string_array` — falsifying example: `['\u2028']`.

**Validation Command:**
```bash
python -c "
import sys; sys.path.insert(0, 'scripts')
from validate_config import parse_simple_toml
result = parse_simple_toml('arr = [\"\u2028\"]')
assert result == {'arr': ['\u2028']}, f'Failed: {result}'
print('PASS')
"
```

---

### BH20-002: TOML parser silently ignores keys starting with digits
**Severity:** MEDIUM
**Category:** `bug/silent-failure`
**Location:** `scripts/validate_config.py:182` (key regex)
**Status:** 🔴 OPEN

**Problem:** The key regex `^([a-zA-Z_][a-zA-Z0-9_-]*)` requires keys to start with a letter or underscore. TOML spec allows bare keys to start with digits (`[A-Za-z0-9_-]`). A line like `1key = "val"` is silently dropped — no error, no warning, the key vanishes. The section header regex at line 170 correctly allows digit-start (`[a-zA-Z0-9_]`), making this inconsistent.

**Acceptance Criteria:**
- [ ] Key regex first character class includes digits: `[a-zA-Z0-9_]`
- [ ] A test verifies `parse_simple_toml('1st = "first"')` returns `{"1st": "first"}`
- [ ] A test verifies `parse_simple_toml('007 = "bond"')` returns `{"007": "bond"}`

**Validation Command:**
```bash
python -c "
import sys; sys.path.insert(0, 'scripts')
from validate_config import parse_simple_toml
result = parse_simple_toml('1key = \"val\"')
assert '1key' in result, f'Digit-start key dropped: {result}'
print('PASS')
"
```

---

### BH20-003: TOML parser has dead variable `current_section`
**Severity:** MEDIUM
**Category:** `design/dead-code`
**Location:** `scripts/validate_config.py:138,176` (current_section)
**Status:** 🔴 OPEN

**Problem:** `current_section` is assigned on lines 138 and 176 but never read. All key storage goes through `_set_nested(root, section_path, key, value)` which navigates from `root`. The variable is misleading — a reader might think it's used for key storage.

**Acceptance Criteria:**
- [ ] Remove `current_section` variable and all assignments to it
- [ ] All tests pass unchanged (proving it was dead code)

**Validation Command:**
```bash
grep -n 'current_section' scripts/validate_config.py
# Should be 0 after fix
```

---

### BH20-004: TOML parser silently drops unparseable lines (no warning)
**Severity:** MEDIUM
**Category:** `design/silent-failure`
**Location:** `scripts/validate_config.py:182-194` (parse_simple_toml main loop)
**Status:** 🔴 OPEN

**Problem:** Lines that match neither comment/blank, section header, nor key-value regex are silently dropped. A typo that breaks a key name (e.g., `key with spaces = "val"`) would cause silent config loss with no error or warning. Combined with BH20-002 (digit-start keys), this means a user could write valid TOML that the parser silently ignores.

**Acceptance Criteria:**
- [ ] Lines that don't match any pattern emit a warning to stderr
- [ ] A test verifies `parse_simple_toml('garbage line')` produces a warning
- [ ] Valid TOML still parses without warnings

**Validation Command:**
```bash
python -c "
import sys, io; sys.path.insert(0, 'scripts')
from contextlib import redirect_stderr
from validate_config import parse_simple_toml
buf = io.StringIO()
with redirect_stderr(buf):
    parse_simple_toml('valid = \"ok\"\ngarbage no equals here')
assert 'unrecognized' in buf.getvalue().lower() or 'warning' in buf.getvalue().lower(), \
    f'No warning for garbage line: {buf.getvalue()!r}'
print('PASS')
"
```

---

### BH20-005: Unparseable lines silently ignored across 30+ splitlines() call sites
**Severity:** MEDIUM
**Category:** `design/fragility`
**Location:** Multiple files (see recon)
**Status:** 🔴 OPEN

**Problem:** 30+ `splitlines()` calls across scripts/ and skills/ would all misparse content containing U+2028/U+2029. While the TOML parser (BH20-001) was the most critical, `_parse_team_index`, `manage_epics`, `manage_sagas`, `traceability`, and `bootstrap_github` all parse user-authored markdown with `splitlines()`. A U+2028 in an epic title or saga description would corrupt parsing.

**Acceptance Criteria:**
- [ ] `_parse_team_index` uses `split('\n')` instead of `splitlines()`
- [ ] `manage_epics.parse_epic` and related functions use `split('\n')`
- [ ] `manage_sagas.parse_saga` and related functions use `split('\n')`
- [ ] All tests pass unchanged

**Validation Command:**
```bash
grep -rn 'splitlines()' scripts/ skills/ | grep -v '\.pyc' | wc -l
# Should decrease significantly after fix
```

---

### BH20-006: format_report() in test_coverage.py is entirely untested
**Severity:** LOW
**Category:** `test/gap`
**Location:** `scripts/test_coverage.py:158-181`
**Status:** 🔴 OPEN

**Problem:** The entire `format_report()` function (24 lines) that generates the markdown coverage report has zero test coverage. It includes conditional sections and dict key lookups that could KeyError.

**Acceptance Criteria:**
- [ ] A test calls `format_report()` with both implemented and missing tests
- [ ] Verifies the output contains expected markdown structure

---

### BH20-007: _parse_saga_labels_from_backlog regex patterns untested
**Severity:** LOW
**Category:** `test/gap`
**Location:** `skills/sprint-setup/scripts/bootstrap_github.py:145-154`
**Status:** 🔴 OPEN

**Problem:** The two saga-parsing regex patterns (Pattern 1: `| S01 | Name |`, Pattern 2: `S01: Name`) have zero test coverage. If these regexes are wrong, saga labels won't be created during bootstrap.

**Acceptance Criteria:**
- [ ] A test with a backlog INDEX containing `| S01 | Walking Skeleton |` verifies Pattern 1
- [ ] A test with `S01: Walking Skeleton` verifies Pattern 2

---

### BH20-008: create_epic_labels() entirely untested
**Severity:** LOW
**Category:** `test/gap`
**Location:** `skills/sprint-setup/scripts/bootstrap_github.py:224-230`
**Status:** 🔴 OPEN

**Problem:** `create_epic_labels()` scans epics directory for `E-NNNN` files and creates labels. Zero direct test coverage. The hexwise pipeline tests exercise `create_static_labels` + `create_persona_labels` + `create_milestones` but NOT `create_epic_labels`.

**Acceptance Criteria:**
- [ ] A test with a temp directory containing `E-0101-parsing.md` verifies `epic:E-0101` label is created
