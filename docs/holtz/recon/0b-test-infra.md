# 0b: Test Infrastructure (Run 3)

**Framework:** pytest 9.0.2
**Runner:** `python3 -m pytest tests/ -v`
**Build system:** None (stdlib-only plugin, no build step)
**Coverage:** Not configured (no pytest-cov)
**Test helpers:** conftest.py, fake_github.py, gh_test_helpers.py, golden_recorder.py, golden_replay.py, mock_project.py
**Test files:** 16 test files covering hooks, kanban, sprint lifecycle, pipeline scripts, property parsing, bugfix regression, release gate, analytics, sync_backlog, anchors, golden runs, and verify-fixes

No changes since Run 2.
