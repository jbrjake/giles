# Holtz Punchlist — Run 6

**Project:** giles
**Date:** 2026-03-23

## Items

### BH-001: test_main_returns_one_when_missing doesn't test main()
**Severity:** MEDIUM
**Category:** test/shallow
**Location:** `tests/test_check_lint_inventory.py:104-124`
**Status:** OPEN
**Lens:** component
**Predicted:** Prediction 1 (confidence: HIGH)

**Problem:** The test claims to verify that `main()` returns 1 when scripts are missing from the Makefile, but it never calls `main()`. It uses `mock.patch.object(check_lint_inventory, "main", wraps=None)` which replaces main with a mock, then manually calls `extract_lint_files()` and `discover_scripts()` — functions already tested separately. The error exit path of `main()` (stdout output, stale detection, return code) is untested.

**Evidence:**
```python
# lines 115-124 of test_check_lint_inventory.py
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
The mock.patch replaces `main` but the test body never calls `main()`. It directly calls the helper functions instead.

**Discovery Chain:** Prediction 1 flagged test quality for new script → read test → mock.patch(wraps=None) on main but main() never called inside with block → test verifies `missing` set which is already covered by TestDiscoverScripts → error exit path untested

**Acceptance Criteria:**
- [ ] `main()` is actually called in the test and returns 1
- [ ] The test exercises `main()` with a controlled filesystem where scripts are missing from Makefile
- [ ] Stale detection path is also exercised (optional enhancement)

**Validation Command:**
```bash
.venv/bin/python -m pytest tests/test_check_lint_inventory.py::TestMain -v
```
