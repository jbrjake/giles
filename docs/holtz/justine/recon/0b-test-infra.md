# 0b: Test Infrastructure (Run 6 — Focused)

**Framework:** pytest + hypothesis (property tests)
**Runner:** `make test` -> `pytest tests/ -v`
**Baseline:** 1232 passing, 0 fail, 0 skip, 17.91s

**New test file:** `tests/test_check_lint_inventory.py`
- 4 test classes, 7 test methods
- Mix of unit tests (extract_lint_files, discover_scripts) and integration tests (live inventory, main)
- Uses tempfile for isolation
- TestMain.test_main_returns_one_when_missing uses mock but doesn't actually test main() — tests component functions instead
