# Recon Summary — Pass 22

## Baseline
- **839 tests, 0 fail, 0 skip, 14.7s** on Python 3.10.15
- pytest 9.0 + hypothesis 6 + jq (enforced)
- No linter configured beyond py_compile + validate_anchors.py
- **23 broken anchor refs** from kanban refactor (stale sync_tracking.* + new kanban.* not resolving)

## Architecture
- 5 skills, ~15 scripts, all stdlib-only Python 3.10+
- Shared library: `scripts/validate_config.py` (1183 lines, highest churn — 14 changes in 50 commits)
- New: `scripts/kanban.py` (512 lines) — centralized state machine, least battle-tested code
- Tracking file I/O (TF, read_tf, write_tf, _yaml_safe) recently extracted from sync_tracking.py into validate_config.py
- Two data flow directions: kanban.py writes local → GitHub (authoritative), sync_tracking.py reads GitHub → local (legacy, may conflict)
- POSIX-only file locking (fcntl) — no Windows support

## High-Risk Areas (audit priority)
1. **kanban.py** — brand new, 37 tests but untested in real sprint workflows
2. **validate_config.py** — shared library hotspot, TF extraction may have subtle breakage
3. **sync_tracking.py** — partially replaced by kanban.py, dual data flow direction is confusing
4. **Broken anchors** — 23 refs in CLAUDE.md/CHEATSHEET.md point to moved or missing code
5. **frontmatter_value()** — known bug where \s* crosses newlines on empty values (found during kanban dev)

## Test Infrastructure
- FakeGitHub: in-memory gh CLI interceptor (strict mode)
- MonitoredMock/patch_gh: prevents mock-asserting-mock anti-pattern
- MockProject: temp-dir scaffold
- _KNOWN_UNTESTED is empty (all scripts must have main() tests)
- No skipped or disabled tests

## Recent Changes (last 10 commits)
- Kanban state machine: new scripts/kanban.py, tests/test_kanban.py
- TF extraction: validate_config.py grew 115 lines, sync_tracking.py shrunk 113 lines
- Doc updates: 6 prompt/reference files updated to reference kanban.py
- CLAUDE.md + CHEATSHEET.md updated with new kanban entries
