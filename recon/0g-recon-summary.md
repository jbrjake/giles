# 0g — Recon Summary (Pass 23)

## Baseline
- **854 tests**, 0 fail, 0 skip, 13.95s
- **86% coverage** (scripts/), 3 files under 80% (test_coverage 68%, sprint_teardown 76%, manage_sagas 78%)
- **~8,400 LOC** production Python, **~15,500 LOC** test Python

## Hot Zones (audit priority order)
1. **validate_config.py** (1190 LOC, 14 changes/50 commits) — god module: TOML parser, config loader, gh wrappers, TF I/O, kanban state, slug generation. Every script imports from it.
2. **kanban.py** (612 LOC, 9 changes) — new state machine with locking, atomic writes, rollback. Fresh code, many recent fixes.
3. **sync_tracking.py** (280 LOC, 9 changes) — reconciliation path, tension with kanban.py's mutation path.
4. **populate_issues.py** (553 LOC, 4 changes) — markdown table parsing, sprint inference.
5. **release_gate.py** (745 LOC) — semver calc, multi-gate validation, rollback orchestration.
6. **sprint_init.py** (996 LOC) — heuristic project scanner, many detection paths.

## Test Infrastructure
- FakeGitHub (992 LOC) reimplements gh CLI — major fidelity risk
- MonitoredMock prevents unchecked mock returns — good anti-pattern defense
- MockProject scaffolds temp projects — well-structured
- Golden recording/replay — covers full setup pipeline
- No pytest configuration, no type checking, coverage not wired into CI

## Key Risk Vectors
1. **Custom TOML parser** — subset impl, edge cases in escaping/quoting/multiline
2. **Custom YAML frontmatter parser** — `frontmatter_value` regex + `_yaml_safe` roundtrip
3. **Shell injection surface** — 8 files shell out via subprocess, user-controlled values in args
4. **Two-path state management** — kanban.py (local-first) vs sync_tracking.py (GitHub-first), both write same files
5. **sys.path.insert chain** — fragile import mechanism, 4 dirs deep
6. **FakeGitHub fidelity** — tests may pass while production breaks differently
7. **No linting/type checking** — only py_compile in CI, no static analysis

## Clean Areas (lower priority)
- 0 skipped tests, 0 xfail, empty _KNOWN_UNTESTED
- No bare excepts, no wildcard imports, no mutable defaults
- All scripts have `if __name__ == "__main__"` guards
- 91% return-type annotation coverage in scripts/
- All broad exception catches are justified and logged
