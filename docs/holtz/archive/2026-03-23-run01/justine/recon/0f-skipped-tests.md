# 0f: Skipped Tests

**Search:** `@pytest.mark.skip`, `pytest.skip`, `unittest.skip` in tests/

## Results

Zero skipped tests found. All 1188 tests are active.

## Assessment

No test debt from skips. Good hygiene. But 1188 active tests that all pass is exactly the surface area where rubber stamps hide -- tests that run but don't catch anything because they check format, not value.
