# Phase 0g: Recon Summary — Pass 6

## Baseline
- 399 tests, 0 fail, 2.83s
- 17 production scripts (~6,800 LOC), 10 test files + 3 helpers (~5,300 LOC)
- 167 total commits, 127 in last 4 days (64% fixes)
- No skipped tests, no empty stubs, no catch-all exception swallowing

## Systemic Observations

### 1. FakeGitHub validation has a blind spot for short flags
`_parse_flags` only processes `--` prefixed flags. Production code uses `-f` and `-X`
for `gh api` calls. The `_KNOWN_FLAGS["api"]` includes "f" and "X" but `_parse_flags`
never captures them, so `_check_flags` validation is bypassed entirely for short flags.
The `_handle_api` method has inline parsing that works, but the enforcement layer is broken.

### 2. Several API endpoints are completely untested
`check_branch_divergence` and `check_direct_pushes` use API endpoints (compare, commits)
that FakeGitHub doesn't handle. These always fail silently via RuntimeError catch, so
tests pass but the actual functionality is never exercised.

### 3. `--jq` accepted as no-op changes response shape
FakeGitHub returns full JSON when production code expects jq-filtered output. This means
code that parses jq-shaped responses works in tests (full JSON superset) but could fail
if the response shape assumptions ever tightened.

### 4. `merge_strategy` is a phantom feature
Generated in config, referenced in 3 docs, consumed by zero scripts. P5-29 was marked
resolved but the underlying issue (no code reads the key) persists.

### 5. Sprint-run phase has zero integration coverage
init → bootstrap → populate is tested. sync_tracking → update_burndown → check_status
(the monitoring pipeline) is never tested as a connected flow.

### 6. Error recovery gaps in release flow
`release-notes.md` not cleaned up on failure. Notes file path hardcoded to cwd.
