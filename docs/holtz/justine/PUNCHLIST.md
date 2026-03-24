# Holtz Punchlist
> Generated: 2026-03-23 | Project: giles | Baseline: 1232 pass, 0 fail, 0 skip

## Summary
| Severity | Open | Resolved | Deferred |
|----------|------|----------|----------|
| CRITICAL | 0 | 0 | 0 |
| HIGH | 1 | 0 | 0 |
| MEDIUM | 1 | 0 | 0 |
| LOW | 1 | 0 | 0 |

## Patterns

(none yet)

## Items

### BJ-001: test_main_returns_one_when_missing mocks the function under test and never verifies main() return code
**Severity:** HIGH
**Category:** test/bogus
**Location:** `tests/test_check_lint_inventory.py:104-124`
**Status:** OPEN
**Lens:** component

**Problem:** The test `test_main_returns_one_when_missing` claims to verify that `main()` returns 1 when a script is missing from the Makefile, but it never actually calls `main()`. It uses `mock.patch.object(check_lint_inventory, "main", wraps=None)` which replaces `main` with a MagicMock, then manually calls `extract_lint_files()` and `discover_scripts()` and checks the set difference. The test name and docstring promise a return-code check that does not happen. If `main()` had a logic error in its return statement (e.g., always returning 0), this test would still pass.

**Evidence:**
```python
# lines 115-124 — mock replaces main, then test calls component functions directly
with mock.patch.object(
    check_lint_inventory,
    "main",
    wraps=None,
):
    # Call the real logic with a patched root
    lint_files = extract_lint_files(makefile)
    disk_files = discover_scripts(root)
    missing = disk_files - lint_files
    self.assertEqual(missing, {"scripts/orphan.py"})
```
No call to `main()`, no assertion on return value. The mock.patch is a no-op since nothing calls the patched function.

**Discovery Chain:** test name says "returns_one_when_missing" → read test body → main() is mocked with wraps=None → no call to main() exists → return code never checked → test is bogus

**Acceptance Criteria:**
- [ ] Test actually calls `main()` (or equivalent) with a controlled root directory
- [ ] Test asserts the return value equals 1 when scripts are missing
- [ ] Test would fail if `main()` always returned 0

**Validation Command:**
```bash
python -m pytest tests/test_check_lint_inventory.py::TestMain::test_main_returns_one_when_missing -v
```

### BJ-002: No test coverage for stale Makefile entries path
**Severity:** MEDIUM
**Category:** test/missing
**Location:** `scripts/check_lint_inventory.py:70-74`
**Status:** OPEN
**Lens:** component

**Problem:** The `main()` function has a code path for stale entries (Makefile references scripts that don't exist on disk) at lines 70-74. This path prints a warning but returns 0 (success). No test exercises this path. The stale-entry behavior is a design decision worth testing: currently stale entries are informational-only (exit 0), meaning dead entries can accumulate in the Makefile without causing CI failures. Whether this is intentional or not, it should be tested to prevent regression.

**Evidence:**
```python
# lines 70-78 — stale path prints but doesn't fail
if stale:
    print(f"lint-inventory: {len(stale)} stale Makefile lint entry(s):")
    for f in stale:
        print(f"  - {f}")

if ok and not stale:
    print("lint-inventory: OK")

return 1 if not ok else 0  # stale-only case returns 0
```
Grep for "stale" in test file returns zero matches.

**Discovery Chain:** read main() logic → stale entries print but return 0 → grep test file for "stale" → zero matches → untested code path

**Acceptance Criteria:**
- [ ] Test creates a temp Makefile with py_compile entries for files that don't exist on disk
- [ ] Test verifies main() returns 0 for stale-only case (documenting current behavior)
- [ ] Test verifies the warning message is printed to stdout

**Validation Command:**
```bash
python -m pytest tests/test_check_lint_inventory.py -k stale -v
```

### BJ-003: extract_lint_files regex matches py_compile in Makefile comments
**Severity:** LOW
**Category:** bug/logic
**Location:** `scripts/check_lint_inventory.py:25`
**Status:** OPEN
**Determinism:** deterministic
**Lens:** data-flow

**Problem:** The regex `py_compile\s+(\S+\.py)` at line 25 does not exclude Makefile comment lines (lines starting with `#`). A comment like `# py_compile scripts/old.py` would be falsely counted as a lint entry, inflating the set of "covered" scripts and potentially masking a missing entry. Currently the Makefile has no such comments, so this is theoretical. However, if someone comments out a py_compile line (a natural editing pattern), the script would still count it as covered.

**Evidence:**
```python
>>> import re
>>> text = "# py_compile scripts/commented.py\n\t$(PYTHON) -m py_compile scripts/real.py"
>>> set(re.findall(r"py_compile\s+(\S+\.py)", text))
{'scripts/commented.py', 'scripts/real.py'}
```
The commented entry is falsely included.

**Discovery Chain:** read extract_lint_files regex → no line-level filtering → test with comment prefix → comment content matches → false positive possible

**Acceptance Criteria:**
- [ ] Regex or pre-filtering excludes Makefile comment lines (lines where first non-whitespace character is `#`)
- [ ] Test verifies commented-out py_compile lines are not matched

**Validation Command:**
```bash
python3 -c "
import re
text = '# py_compile scripts/old.py\n\t\$(PYTHON) -m py_compile scripts/real.py'
result = set(re.findall(r'py_compile\s+(\S+\\.py)', text))
assert 'scripts/old.py' not in result, f'Comment matched: {result}'
print('PASS')
"
```
