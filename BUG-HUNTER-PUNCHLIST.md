# Bug Hunter Punchlist — Fresh Adversarial Audit

Audit date: 2026-03-13 (third pass — independent reviewer)
Codebase: giles v0.4.0 — 19 scripts (~7,000 LOC), 11 test files (~3,800 LOC), 26 reference docs
Prior audits: Two complete passes (37 + 30 items), all resolved. This punchlist covers NEW findings only.

---

## Status Summary

| ID | Title | Severity | Status |
|----|-------|----------|--------|
| BH3-01 | do_release rollback leaves git index dirty | MEDIUM | FIXED |
| BH3-02 | get_existing_issues silent error defeats idempotency | MEDIUM | FIXED |
| BH3-03 | create_from_issue accepts invalid kanban states | LOW | FIXED |
| BH3-04 | verify_targets is a stub that verifies nothing | LOW | FIXED |
| BH3-05 | TOML _split_array doesn't handle escaped backslashes | LOW | FIXED |
| BH3-06 | TOCTOU window in sync_backlog between hash and sync | LOW | FIXED |
| BH3-07 | CLAUDE.md missing 3 reference files from index | MEDIUM | FIXED |
| BH3-08 | [conventions] config keys undocumented | MEDIUM | FIXED |
| BH3-09 | sprint-monitor SKILL.md claims PR auto-merge that doesn't exist | MEDIUM | FIXED |
| BH3-10 | shell=True in gate_tests/gate_build undocumented | LOW | FIXED |

---

## Priority 1: Code Bugs

### BH3-01: do_release rollback leaves git index dirty after failed commit
- **Location**: `skills/sprint-release/scripts/release_gate.py:433-438`
- **Bug**: When `commit.py` fails, the rollback at lines 434-438 does TWO things: (1) restores file content from `original_toml`, then (2) runs `git checkout -- <file>`. But `git add` at line 423 already staged the modified file. Restoring the file content does NOT unstage it. The subsequent `git checkout` is redundant with the file restore but also doesn't clean the index. Result: the git index contains a staged change to `project.toml` that doesn't match the working tree.
- **Impact**: After a failed release, the repo is in a confusing state — `git status` shows staged changes the user didn't make. The next `git commit` could accidentally include the version bump.
- **Acceptance criteria**: After a failed commit step, the git index matches the working tree (no staged changes remain). Either use `git reset HEAD -- <file>` to unstage, or use `git checkout --` alone (which handles both index and working tree).
- **Validation**:
  ```bash
  python3 -c "
  import ast, re
  src = open('skills/sprint-release/scripts/release_gate.py').read()
  tree = ast.parse(src)
  for node in ast.walk(tree):
      if isinstance(node, ast.FunctionDef) and node.name == 'do_release':
          body = ast.get_source_segment(src, node)
          # After commit failure, should unstage with git reset or checkout alone
          if 'write_text(original_toml' in body and 'git checkout' in body:
              if 'git reset' not in body:
                  print('BUG: rollback writes file + checkout but never unstages (git reset HEAD)')
          break
  "
  # Should print nothing after fix
  ```

### BH3-02: get_existing_issues silently returns empty set on GitHub API failure
- **Location**: `skills/sprint-setup/scripts/populate_issues.py:243-244`
- **Bug**: `except (RuntimeError, json.JSONDecodeError): return set()` — when the GitHub API fails (network error, rate limit, auth issue), the function silently returns an empty set. The caller then creates ALL issues, causing duplicates.
- **Impact**: If GitHub is temporarily unavailable during `populate_issues`, every story gets created as a duplicate issue. The script is supposed to be idempotent; this breaks idempotency silently.
- **Acceptance criteria**: API failure either (a) raises to halt issue creation, or (b) prints a clear warning and returns a sentinel that the caller checks before proceeding.
- **Validation**:
  ```bash
  python3 -c "
  import ast
  src = open('skills/sprint-setup/scripts/populate_issues.py').read()
  tree = ast.parse(src)
  for node in ast.walk(tree):
      if isinstance(node, ast.FunctionDef) and node.name == 'get_existing_issues':
          # Check that except blocks don't silently return empty set
          for handler in ast.walk(node):
              if isinstance(handler, ast.ExceptHandler):
                  for ret in ast.walk(handler):
                      if isinstance(ret, ast.Return) and isinstance(ret.value, ast.Call):
                          if hasattr(ret.value.func, 'id') and ret.value.func.id == 'set':
                              print('BUG: still silently returns empty set on API failure')
          break
  "
  # Should print nothing after fix
  ```
- **Fix**: Re-raise the exception, or at minimum print a warning and set a flag that `main()` checks before creating issues.

### BH3-03: create_from_issue accepts invalid kanban states without validation
- **Location**: `skills/sprint-run/scripts/sync_tracking.py:233,244`
- **Bug**: `kanban_from_labels()` (validate_config.py:620) returns whatever string follows `kanban:` in a label — no validation. `create_from_issue()` at line 244 stores this directly as `status`. A label like `kanban:garbage` creates a tracking file with `status=garbage`, which is not in `KANBAN_STATES`. Note: `sync_one()` at line 193 defensively checks `gh_status in KANBAN_STATES`, but `create_from_issue` does not.
- **Impact**: Low — requires a deliberately bad GitHub label. But tracking files with invalid states confuse downstream processing (burndown, sprint status).
- **Acceptance criteria**: Either `kanban_from_labels()` validates against allowed states, or `create_from_issue()` clamps to the nearest valid state (defaulting to "todo").
- **Validation**:
  ```bash
  python3 -c "
  import sys; sys.path.insert(0, 'scripts')
  from validate_config import kanban_from_labels
  # Simulate an issue with a bogus kanban label
  issue = {'labels': [{'name': 'kanban:garbage'}], 'state': 'open'}
  result = kanban_from_labels(issue)
  if result not in ('todo', 'design', 'dev', 'review', 'integration', 'done'):
      print(f'BUG: kanban_from_labels returned invalid state: {result!r}')
  else:
      print(f'PASS: returned valid state: {result!r}')
  "
  ```

### BH3-04: verify_targets is a stub that verifies nothing
- **Location**: `scripts/sprint_teardown.py:273-305`
- **Bug**: Lines 279-282 contain a comment acknowledging the function is broken: "Symlink is gone now, so we need to reconstruct the target path from the raw link value we can no longer read. We stored nothing." The function then falls back to checking hardcoded filenames (`RULES.md`, `DEVELOPMENT.md`) rather than actual symlink targets. The loop at lines 277-282 iterates over `symlinks` but does nothing useful — `_target` is always `None` because the symlinks have already been removed.
- **Impact**: Low — the function runs after teardown and is informational only. But it provides false confidence that targets are intact.
- **Acceptance criteria**: Either (a) store symlink targets before removal (in the remove step) and pass them to verify_targets, or (b) remove the function and its call site since it's misleading.
- **Validation**:
  ```bash
  python3 -c "
  src = open('scripts/sprint_teardown.py').read()
  if 'We stored nothing' in src:
      print('BUG: verify_targets still contains stub comment')
  else:
      print('PASS: stub comment removed')
  "
  ```

---

## Priority 2: Design Hardening (not broken, but fragile)

### BH3-05: TOML _split_array doesn't handle escaped backslashes before quotes
- **Location**: `scripts/validate_config.py:206`
- **Bug**: `current[-1] != "\\"` checks for a single preceding backslash but doesn't handle `\\\"` (escaped backslash + literal quote). In TOML, `\\` is an escaped backslash, so `\\"` should end the string, but this code treats it as an escaped quote.
- **Impact**: Very low — the project uses simple string values with no escape sequences. No current config triggers this. But it's a latent parser bug.
- **Acceptance criteria**: Either (a) count consecutive backslashes (odd count = escaped quote, even count = end of string), or (b) document the limitation in a comment.
- **Validation**:
  ```bash
  python3 -c "
  import sys; sys.path.insert(0, 'scripts')
  from validate_config import parse_simple_toml
  # Escaped backslash before closing quote
  result = parse_simple_toml('key = \"hello\\\\\\\\\"')
  # Should parse as: hello\\\\ (4 chars: h,e,l,l,o,\\,\\)
  # Bug: parser may not close the string correctly
  print(f'Parsed: {result}')
  "
  ```

### BH3-06: TOCTOU window in sync_backlog between hash check and sync execution
- **Location**: `scripts/sync_backlog.py:200-207`
- **Bug**: `hash_milestone_files()` at line 200 computes hashes, then `do_sync()` at line 207 re-reads those files. If a file changes between lines 200 and 207, the saved hashes don't match the synced content.
- **Impact**: Low — the debounce mechanism requires hashes to be stable across multiple invocations before syncing, which makes the race window very narrow. Only possible if a file is edited during the ~100ms between hash and sync.
- **Acceptance criteria**: Either (a) accept the risk and add a comment documenting it, or (b) re-hash after sync and warn if they differ.
- **Validation**: Not programmatically testable (race condition). Document the design choice.

### BH3-10: shell=True in gate_tests/gate_build is intentional but undocumented
- **Location**: `skills/sprint-release/scripts/release_gate.py:180-181,193-194`
- **Note**: `check_commands` and `build_command` from project.toml are run with `shell=True`. This is **intentional** — these are user-configured shell commands like `cargo test` or `npm run build` that require shell interpretation. Since this is a local plugin running on the user's own machine with their own config, this is not a security vulnerability.
- **Acceptance criteria**: Add a comment at each `shell=True` call explaining this is intentional and that commands come from the user's own project.toml.
- **Validation**:
  ```bash
  grep -A1 'shell=True' skills/sprint-release/scripts/release_gate.py | grep -c '# '
  # Should be >= 2 (comments above or on each shell=True line)
  ```

---

## Priority 3: Documentation Gaps

### BH3-07: CLAUDE.md Reference Files table missing 3 files
- **Location**: `CLAUDE.md:66-79` (Reference Files table)
- **Bug**: The table lists 8 reference files but the `skills/sprint-run/references/` directory contains 8 files. Three are missing from CLAUDE.md:
  - `context-recovery.md` — referenced in sprint-run SKILL.md:19
  - `story-execution.md` — referenced in sprint-run SKILL.md:16
  - `tracking-formats.md` — referenced in sprint-run SKILL.md and CHEATSHEET.md:352
- **Impact**: Developers reading CLAUDE.md won't discover these files.
- **Acceptance criteria**: All 8 reference files listed in the Reference Files table.
- **Validation**:
  ```bash
  for f in context-recovery story-execution tracking-formats; do
    if ! grep -q "$f" CLAUDE.md; then
      echo "MISSING from CLAUDE.md: $f.md"
    fi
  done
  # Should print nothing
  ```

### BH3-08: [conventions] config keys undocumented in CLAUDE.md
- **Location**: `CLAUDE.md:92-103` (Configuration System section)
- **Bug**: CLAUDE.md mentions `[conventions]` in the config tree diagram (line 87) but never documents the keys:
  - `branch_pattern` — used by story-execution.md:20
  - `commit_style` — generated by sprint_init.py:611
  - `merge_strategy` — used by sprint-monitor SKILL.md:166

  These are generated by `sprint_init.py:608-614` and referenced in skill docs, but CLAUDE.md doesn't list them as optional keys or describe their purpose.
- **Impact**: Users and agents don't know these config options exist.
- **Acceptance criteria**: `[conventions]` keys documented alongside other optional keys in CLAUDE.md.
- **Validation**:
  ```bash
  grep -c 'branch_pattern\|commit_style\|merge_strategy' CLAUDE.md
  # Should be >= 3
  ```

### BH3-09: sprint-monitor SKILL.md claims PR auto-merge that check_status.py doesn't implement
- **Location**: `skills/sprint-monitor/SKILL.md:164-169` vs `skills/sprint-monitor/scripts/check_status.py`
- **Bug**: SKILL.md line 166 says "Merge using the strategy from `project.toml [conventions] merge_strategy`" implying sprint-monitor auto-merges approved PRs. But `check_status.py` only REPORTS approved PRs (check_prs function) — it never calls `gh pr merge`. The merge is actually done by sprint-run during story execution.
- **Impact**: Agents following sprint-monitor SKILL.md will expect auto-merging that doesn't happen. The SKILL.md describes functionality that doesn't exist in the script.
- **Acceptance criteria**: SKILL.md accurately describes what check_status.py does (reports approval status) and directs merge responsibility to sprint-run.
- **Validation**:
  ```bash
  grep -c 'pr merge\|gh pr merge' skills/sprint-monitor/scripts/check_status.py
  # Should be 0 (confirms no merge implementation)
  grep -c 'Merge using' skills/sprint-monitor/SKILL.md
  # Should be 0 after fix (removed false claim)
  ```

---

## Pattern Analysis

| Pattern | Items | Root Cause |
|---------|-------|------------|
| PAT-A: Rollback operations that miss git index state | BH3-01 | File-level rollback without considering git staging area |
| PAT-B: Silent error returns that break downstream assumptions | BH3-02, BH3-03 | Defensive `except: return default` that defeats caller invariants |
| PAT-C: Stub functions that pass without doing real work | BH3-04 | Code written as placeholder, never completed, called in production flow |
| PAT-D: Doc claims exceeding implementation | BH3-09 | SKILL.md written aspirationally; code didn't catch up |

---

## Audit Metrics

| Category | Count |
|----------|-------|
| Code bugs | 4 |
| Design hardening | 3 |
| Documentation gaps | 3 |
| **Total** | **10** |

### By Severity
| Severity | Count | Items |
|----------|-------|-------|
| CRITICAL | 0 | — |
| MEDIUM | 5 | BH3-01, BH3-02, BH3-07, BH3-08, BH3-09 |
| LOW | 5 | BH3-03, BH3-04, BH3-05, BH3-06, BH3-10 |

### Test Suite Health
- **319 tests, all passing, 3.1s**
- All prior audit findings (67 total across 2 passes) verified as resolved
- No tautological tests, no coverage padding, no skipped tests
- FakeGitHub implements --limit and --state filtering
- Edge case coverage for TOML parser (9 tests), CI generation (3 languages), scanner (multiple fixtures)
- Release pipeline (`do_release`) has 4 comprehensive tests

### What the Prior Audits Got Right
The prior two passes were thorough and effective. They caught and fixed: sprint matching bugs, data-loss in reorder, dead code, hardcoded values, template naming, missing function calls, tautological tests, coverage padding, bogus assertions, FakeGitHub fidelity gaps, all stale line references, encoding issues, and documentation inconsistencies. The codebase is substantially more robust as a result.

### What This Audit Found That They Missed
The prior audits focused on data correctness, test quality, and doc accuracy. This audit found issues in: **error recovery** (git index state after rollback), **silent failure modes** (API errors defeating idempotency), **stub code** (function that claims to verify but doesn't), and **doc-to-code gaps** (SKILL.md describing unimplemented features).
