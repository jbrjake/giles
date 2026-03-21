# Recon Summary — Pass 10

## Codebase at a Glance

- **19 production Python scripts** (~7,374 LOC), all stdlib-only (Python 3.10+)
- **11 test files**, 520 tests, 0 failures, 0 skips, ~3s runtime
- **1 test double**: `fake_github.py` (743 lines) — mocks `gh` CLI via subprocess patching
- **1 golden test system**: recordings checked in (6 snapshots), replay comparisons active
- **Central hub**: `validate_config.py` — imported by 16 of 19 scripts
- **No linter, type checker, or coverage tool configured**

## High-Risk Areas (from churn + manual review)

1. **FakeGitHub fidelity**: Accepts flags it doesn't implement (`--search`, `--jq` not evaluated, `--paginate` is no-op). Tests pre-shape data to match expected output, bypassing mock validation.
2. **Paginated JSON handling**: Multiple scripts use `--paginate` with `gh api`. When responses span pages, `gh` concatenates raw JSON arrays (`[...][...]`), which `json.loads()` can't parse.
3. **validate_config.py**: Central hub with custom TOML parser. Nested arrays unsupported. Hyphenated keys silently ignored.
4. **update_burndown.py**: `_fm_val` quote handling differs from `read_tf` in sync_tracking.py (doesn't unescape `\"`).
5. **check_status.py**: `check_prs` CI check uses `all()` with filter — vacuously true when no checks completed.

## Test Quality Concerns

- FakeGitHub's `--search` flag is silently ignored → `compute_review_rounds` test gives false green bar
- Several tests mock at `gh_json` level, skipping argument construction validation
- Missing test coverage for `main()` / orchestration in 5 scripts
- `test_all_pass` in release_gate tests uses empty config → gates auto-pass

## No Skipped Tests, No Disabled Tests

All 520 tests are active. Prior passes cleaned up tautologies and duplicates.
