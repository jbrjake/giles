# Holtz Punchlist
> Generated: 2026-03-23 | Project: giles | Baseline: 1188 pass, 0 fail, 0 skip

## Summary
| Severity | Open | Resolved | Deferred |
|----------|------|----------|----------|
| CRITICAL | 0 | 0 | 0 |
| HIGH | 0 | 2 | 0 |
| MEDIUM | 0 | 4 | 0 |
| LOW | 0 | 0 | 1 |

## Patterns

(None yet)

## Items

### BH-001: NAMESPACE_MAP missing 6 script entries — validate_anchors reports false broken refs
**Severity:** HIGH
**Category:** bug/logic
**Location:** `scripts/validate_anchors.py:23`
**Status:** RESOLVED
**Predicted:** Prediction 1 (confidence: HIGH)
**Lens:** contract

**Problem:** `NAMESPACE_MAP` in validate_anchors.py is missing entries for 6 scripts: `smoke_test`, `gap_scanner`, `test_categories`, `risk_register`, `assign_dod_level`, `history_to_checklist`. These scripts all have valid `§`-anchor definitions in their source code, but the namespace resolver can't find them, causing `make lint` to report 21 broken references and exit non-zero.

**Evidence:** `make lint` outputs "21 broken reference(s)" — all pointing to CLAUDE.md lines 57-62. Scripts themselves contain `# §smoke_test.run_smoke`, `# §gap_scanner.scan_for_gaps`, etc. but `NAMESPACE_MAP` at line 23 has no entries for these namespaces.

**Discovery Chain:** `make lint` fails with 21 broken refs → all refs target 6 specific namespaces → those namespaces are absent from NAMESPACE_MAP → scripts have valid anchor defs

**Acceptance Criteria:**
- [ ] All 6 missing namespaces added to NAMESPACE_MAP
- [ ] `make lint` exits 0 (only info-level unreferenced anchors, no broken refs)

**Validation Command:**
```bash
.venv/bin/python scripts/validate_anchors.py 2>&1 | grep "broken"
```

### BH-002: Makefile lint target missing 7 production scripts from py_compile list
**Severity:** MEDIUM
**Category:** doc/drift
**Location:** `Makefile:30`
**Status:** RESOLVED
**Predicted:** Prediction 2 (confidence: HIGH)
**Lens:** contract

**Problem:** The Makefile `lint` target runs `py_compile` on 19 scripts, but 7 production scripts are missing: `assign_dod_level.py`, `gap_scanner.py`, `history_to_checklist.py`, `kanban.py`, `risk_register.py`, `smoke_test.py`, `test_categories.py`. These scripts are not syntax-checked during `make lint`.

**Evidence:** `comm -23` between actual scripts and Makefile list shows 7 files missing. kanban.py (815 LOC) is notably the 3rd largest script and is not syntax-checked.

**Discovery Chain:** CLAUDE.md lists 25 scripts → Makefile py_compile has 19 → diff reveals 7 missing → kanban.py (3rd largest) among them

**Acceptance Criteria:**
- [ ] All 7 missing scripts added to Makefile lint target
- [ ] `make lint` compiles all production scripts

**Validation Command:**
```bash
make lint 2>&1 | grep -c "py_compile"
```

### BH-003: CLAUDE.md Plugin Structure section omits hooks/ directory entirely
**Severity:** MEDIUM
**Category:** doc/missing
**Location:** `CLAUDE.md:9`
**Status:** RESOLVED
**Predicted:** Prediction 3 (confidence: MEDIUM)
**Lens:** contract

**Problem:** CLAUDE.md's Plugin Structure section lists `.claude-plugin/plugin.json`, `skills/`, `scripts/`, `references/skeletons/`, and `evals/evals.json` — but does not mention `hooks/` or `hooks/hooks.json` at all. The hooks subsystem (4 hooks + _common.py + hooks.json) is completely undocumented in the project guide. The word "hooks" does not appear anywhere in CLAUDE.md.

**Evidence:** `grep "hooks" CLAUDE.md` returns no matches. `hooks/` contains 5 Python files and hooks.json. hooks.json registers 4 hooks (PreToolUse, PostToolUse, SubagentStop, SessionStart).

**Discovery Chain:** Plugin Structure lists 5 directories → hooks/ not listed → grep confirms "hooks" absent from CLAUDE.md → hooks/ exists with 5 .py files and hooks.json

**Acceptance Criteria:**
- [ ] `hooks/` directory added to Plugin Structure section
- [ ] hooks.json and individual hook purposes documented
- [ ] Quick File Lookup table updated with hooks

**Validation Command:**
```bash
grep -c "hooks" CLAUDE.md
```

### BH-004: test_new_scripts.py missing main() and write-path coverage for 6 scripts
**Severity:** LOW
**Category:** test/shallow
**Location:** `tests/test_new_scripts.py`
**Status:** OPEN
**Predicted:** Prediction 8 (confidence: MEDIUM)
**Lens:** component

**Problem:** test_new_scripts.py covers 6 newer scripts (smoke_test, gap_scanner, test_categories, risk_register, assign_dod_level, history_to_checklist) but never exercises their `main()` entry points. Additionally, `assign_levels()` (the write path in assign_dod_level.py) is never called in any test. The functions tested are primarily parsing and classification logic.

**Evidence:** No test function calls `main()` for any of the 6 scripts. `assign_levels` does not appear in any assertion or call in the test suite (grep returns 0 matches in tests/).

**Discovery Chain:** Prediction 8 flagged test_new_scripts as potentially shallow → subagent audit confirms main() untested for all 6 → assign_levels write path also untested

**Acceptance Criteria:**
- [ ] At least one main() integration test per script (or documented reason to skip)
- [ ] assign_levels() write path tested with mock filesystem

**Validation Command:**
```bash
grep -c "main\(\)" tests/test_new_scripts.py
```

### BH-005: commit_gate bypassed by compound commands containing --dry-run
**Severity:** HIGH
**Category:** bug/security
**Location:** `hooks/commit_gate.py:143`
**Status:** RESOLVED
**Determinism:** deterministic
**Lens:** security

**Problem:** `check_commit_allowed()` checks `re.search(r'--dry-run\b', command)` against the entire command string without splitting compound commands. A command like `git stash --dry-run; git commit -m "evil"` passes both the `is_commit` check (matches `git commit`) AND the `--dry-run` check (matches `--dry-run` from the first part). The real commit is allowed through. review_gate splits on `&&`/`;`/`|` (line 120) but commit_gate does not.

**Evidence:** review_gate.py:120 has `re.split(r'\s*(?:&&|\|\||\||;)\s*', command)` for compound command handling. commit_gate.py has no equivalent — `check_commit_allowed` operates on the raw command string.

**Discovery Chain:** compare review_gate vs commit_gate → review_gate splits compound commands → commit_gate does not → --dry-run from one subcommand allows commit in another

**Acceptance Criteria:**
- [ ] commit_gate splits compound commands before checking each subcommand
- [ ] Test: compound command `"git stash --dry-run; git commit -m test"` is blocked

**Validation Command:**
```bash
.venv/bin/python -m pytest tests/test_hooks.py -k "compound" -v
```

### BH-006: review_gate _log_blocked crash prevents exit_block from executing
**Severity:** MEDIUM
**Category:** bug/error-handling
**Location:** `hooks/review_gate.py:248`
**Status:** RESOLVED
**Determinism:** theoretical
**Lens:** error-propagation

**Problem:** `_log_blocked(command, reason)` is called before `exit_block(reason)` at lines 248-249 and 259-260. If `_log_blocked` raises (PermissionError from `mkdir` at line 218 or `open` at line 221), `exit_block` never executes. The hook crashes with non-zero exit and no JSON output. Under the JSON protocol, hooks must exit 0 — behavior for a crashing hook is undefined.

**Evidence:** Lines 248-249: `_log_blocked(command, reason)` then `exit_block(reason)` — no try/except around `_log_blocked`. Lines 218-222: `mkdir` and `open` can raise PermissionError/OSError.

**Discovery Chain:** review_gate blocks a push → calls _log_blocked first → _log_blocked can raise on filesystem error → exit_block never runs → hook crashes → block decision lost

**Acceptance Criteria:**
- [ ] `_log_blocked` wrapped in try/except, or called after `exit_block`
- [ ] Test: _log_blocked raising doesn't prevent blocking

**Validation Command:**
```bash
.venv/bin/python -m pytest tests/test_hooks.py -k "log_blocked" -v
```

### BH-007: find_milestone only queries open milestones — closed milestones invisible
**Severity:** MEDIUM
**Category:** bug/logic
**Location:** `scripts/validate_config.py:1177`
**Status:** RESOLVED
**Determinism:** deterministic
**Lens:** data-flow

**Problem:** `find_milestone()` queries `repos/{owner}/{repo}/milestones?per_page=100` without `state=all`. GitHub API defaults to `state=open`. After a milestone is closed (end of sprint), `find_milestone` returns None. Downstream callers (check_status, update_burndown, sync_tracking) silently skip work for closed milestones.

**Evidence:** Line 1177: `"api", "repos/{owner}/{repo}/milestones?per_page=100"` — no `state=all`. GitHub REST API docs: "state: Indicates the state of the issues to return. Default: open".

**Discovery Chain:** check_status calls find_milestone → find_milestone queries GitHub API → API defaults to state=open → closed milestones return None → downstream silently skips

**Acceptance Criteria:**
- [ ] `find_milestone` includes `state=all` in the API URL
- [ ] Test: find_milestone finds a milestone with `state: "closed"`

**Validation Command:**
```bash
.venv/bin/python -m pytest tests/test_sprint_runtime.py -k "find_milestone" -v
```

### BH-008: commit_gate post_main crashes if tool_output is a string
**Severity:** MEDIUM
**Category:** bug/error-handling
**Location:** `hooks/commit_gate.py:253`
**Status:** RESOLVED
**Determinism:** deterministic
**Lens:** error-propagation

**Problem:** `post_main()` at line 253 calls `tool_output.get("exit_code", ...)` — assumes tool_output is a dict. If Claude Code sends a string value for tool_output (which can happen for some tool responses), this raises `AttributeError: 'str' object has no attribute 'get'`. The crash prevents verification state from being recorded, keeping the commit gate in "needs verification" state (fail-safe, but still a crash).

**Evidence:** Line 250-253: `tool_output = input_data.get("tool_output", input_data.get("tool_response", input_data.get("output", {})))` then `exit_code = tool_output.get(...)` — no isinstance check.

**Discovery Chain:** post_main reads tool_output from event → assumes dict → string input raises AttributeError → verification not recorded → commit gate stays blocked (fail-safe)

**Acceptance Criteria:**
- [ ] isinstance check before calling .get() on tool_output
- [ ] Test: string tool_output doesn't crash post_main

**Validation Command:**
```bash
.venv/bin/python -m pytest tests/test_hooks.py -k "post" -v
```
