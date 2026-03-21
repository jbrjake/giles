# Bug Hunter Punchlist — Pass 25 (Systems & Integration Audit)

> Generated: 2026-03-20 | Project: giles | Baseline: 1050 pass, 0 fail
> Focus: Systems/integration issues + all code from past hour (16 commits)

## Summary

| Severity | Open | Resolved | Deferred |
|----------|------|----------|----------|
| HIGH     | 3    | 0        | 0        |
| MEDIUM   | 10   | 0        | 0        |
| LOW      | 6    | 0        | 0        |

---

## Tier 1 — Fix Now (HIGH)

### Hook System Failures

| ID | Title | Category | Acceptance Criteria | Validation |
|----|-------|----------|---------------------|------------|
| BH25-001 | commit_gate.py mark_needs_verification() is never called — hook fundamentally broken | bug/integration | The commit gate must track source file modifications. Either: (a) register a PostToolUse hook for Write/Edit that calls mark_needs_verification, or (b) check git diff status instead of a state file. Currently, no Write/Edit hook is registered in plugin.json, so the state file is never created, and the gate never blocks. | Test: modify a .py file via Write tool → `needs_verification()` returns True → commit is blocked until tests run |
| BH25-002 | verify_agent_output.py _read_toml_key() can't parse multi-line TOML arrays | bug/integration | `_read_toml_key()` returns `[]` for multi-line arrays like `check_commands = [\n"pytest",\n]`. The hook silently skips verification for all projects using multi-line array format (the standard template). Must handle multi-line arrays or use validate_config.load_config(). | Test: `_read_toml_key('[ci]\ncheck_commands = [\n"pytest",\n"ruff",\n]\n', 'ci', 'check_commands')` returns `['pytest', 'ruff']` |
| BH25-003 | assign_dod_level.py writes tracking files without file locking | bug/race | `assign_levels()` calls `read_tf()`/`write_tf()` outside any lock context. Same TOCTOU pattern fixed in BH24-001/002. Concurrent kanban transitions or sync_tracking could corrupt state. | Import and use `lock_story` from kanban.py around the read/modify/write cycle |

---

## Tier 2 — Fix Soon (MEDIUM)

### Hook Logic Gaps

| ID | Title | Category | Acceptance Criteria | Validation |
|----|-------|----------|---------------------|------------|
| BH25-004 | review_gate.py check_push() allows `git push` with no args when on base branch | bug/bypass | `git push` with no remote and no refspec pushes to the upstream tracking branch. If the current branch is `main` with upstream `origin/main`, this bypasses protection. Must block or warn when `positional` is empty and current branch equals base. | Test: `check_push("git push", base="main")` should return "blocked" or "warn" |
| BH25-005 | commit_gate.py uses hardcoded test patterns instead of project.toml check_commands | design/fragile | `_matches_check_command()` hardcodes pytest/cargo/npm/etc. Projects using `bazel test`, `make test`, or custom runners won't clear verification state. Should read from `[ci] check_commands` if available. | Test: `_matches_check_command("bazel test //...")` returns True after config loaded |
| BH25-006 | verify_agent_output.py update_tracking_verification() bypasses write_tf — no locking, no escaping | bug/integration | Writes directly to YAML frontmatter by splitting on `---`, outside any lock context. Could corrupt tracking files if concurrent with kanban transitions. Has zero tests. | Function tested with roundtrip: write verification → read_tf → verify field present |

### Code Quality

| ID | Title | Category | Acceptance Criteria | Validation |
|----|-------|----------|---------------------|------------|
| BH25-007 | kanban.py _count_review_rounds() has redundant `import re` | code/dead | `re` is already imported at module level (kanban.py:11). Remove the inline import. | `grep -c 'import re' scripts/kanban.py` returns 1 |
| BH25-008 | kanban.py do_transition() has inline `from datetime import datetime` | code/style | Import should be at module level. The function is called frequently during transitions. | `from datetime import datetime` at module level, not inside function body |
| BH25-009 | check_status.py check_smoke() has inline `import subprocess, json` | code/dead | Both modules are already available at module level (subprocess via gh(), json via json.loads in other functions). | Remove inline import; verify module-level imports cover both |

### Integration Consistency

| ID | Title | Category | Acceptance Criteria | Validation |
|----|-------|----------|---------------------|------------|
| BH25-010 | risk_register.py uses hardcoded _REGISTER_PATH instead of config | design/inconsistency | All other scripts read paths from project.toml. risk_register.py hardcodes `sprint-config/risk-register.md`. Should accept --config arg or read from project.toml. | Accept --config path or derive from config paths.backlog_dir |
| BH25-011 | tracking-formats.md documents Integration Debt field but update_burndown.py doesn't write it | doc/drift | Either remove from format doc (it's in check_status.py monitor output only) or add to update_burndown.py. Currently format doc is aspirational. | Format doc matches what update_burndown.py actually writes |

---

## Tier 3 — Fix When Convenient (LOW)

### Test Quality

| ID | Title | Category | Acceptance Criteria | Validation |
|----|-------|----------|---------------------|------------|
| BH25-012 | test_hooks.py test_blocked_message_contains_review_required duplicates test_blocked_when_no_review | test/duplicate | Lines 58-67 test the same assertion (result == "blocked") as lines 28-35. Either test message content or remove duplicate. | Test asserts on message content, not just "blocked" return value |
| BH25-013 | test_hooks.py test_block_message_contains_pr_and_base duplicates test_direct_push_to_base_blocked | test/duplicate | Lines 108-115 duplicate lines 73-76. Either test actual message string or remove. | Distinct assertion in each test |
| BH25-014 | test_hooks.py has no test for verify_agent_output.update_tracking_verification() | test/missing | The most dangerous function (direct YAML frontmatter mutation) has zero tests. | At least 2 tests: success path, already-exists path |
| BH25-015 | No test for risk_register.resolve_risk() | test/missing | Complex regex-based row replacement logic untested. | Test: add risk → resolve → list_open returns empty |
| BH25-016 | test_hooks.py test_load_check_commands_from_toml only tests single-line array | test/gap | Doesn't test multi-line array format, which is why BH25-002 wasn't caught. | Test with multi-line array format |
| BH25-017 | test_hooks.py test_push_without_refspec_allowed doesn't test bare `git push` | test/gap | Tests `git push origin` (remote, no refspec) but not `git push` (no args at all), which is the bypass in BH25-004. | Test: `check_push("git push", base="main")` |

---

## Emerging Patterns

### PAT-25-001: Hooks bypass validate_config.py, creating parser divergence
**Instances:** BH25-002, BH25-005
**Root Cause:** Hooks use lightweight inline TOML parsing to avoid import dependencies, but the inline parser is weaker than validate_config.parse_simple_toml(). Multi-line arrays, escape sequences, and complex values are not handled.
**Systemic Fix:** Either make hooks import validate_config.py (add sys.path.insert) or extract a shared minimal parser module that both use.
**Detection Rule:** Compare hook TOML parsing against validate_config capabilities. Any feature validate_config handles that the hook parser doesn't is a bug.

### PAT-25-002: New file-writing code doesn't use file locking
**Instances:** BH25-003, BH25-006
**Root Cause:** BH24-001/002 established locking discipline for kanban.py and sync_tracking.py, but new code written in the same session doesn't follow the pattern.
**Systemic Fix:** Add linting rule or code review checklist item: "any write_tf() call must be inside a lock_story() context."

### PAT-25-003: Tests verify return values but not side effects
**Instances:** BH25-012, BH25-013, BH25-014
**Root Cause:** Tests check that functions return "blocked"/"allowed" but don't verify the message strings, audit logs, or file mutations that are the actual purpose of the hook.
