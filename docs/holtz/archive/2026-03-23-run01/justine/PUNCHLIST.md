# Justine Punchlist
> Generated: 2026-03-23 | Project: giles | Baseline: 1188 pass, 0 fail, 0 skip

## Summary
| Severity | Open | Resolved | Deferred |
|----------|------|----------|----------|
| CRITICAL | 0 | 0 | 0 |
| HIGH | 2 | 0 | 0 |
| MEDIUM | 3 | 0 | 0 |
| LOW | 2 | 0 | 0 |

## Patterns

## Pattern: PAT-001: Triple TOML Parser Divergence
**Instances:** BJ-001, BJ-002, BJ-003, BJ-007
**Root Cause:** Hooks intentionally avoid importing validate_config for isolation, but re-implement TOML parsing with less edge-case coverage. Each independent parser handles a different subset of the TOML spec.
**Systemic Fix:** Create a shared lightweight TOML reader in `hooks/_toml.py` that all hooks import, keeping hook isolation from validate_config while eliminating redundant parser implementations.
**Detection Rule:** `grep -rn 'def.*read_toml\|def.*_read_toml\|def.*_get_base_branch\|parse_simple_toml' hooks/ scripts/validate_config.py`

## Items

### BJ-001: session_context._read_toml_string returns empty for unquoted TOML values
**Severity:** HIGH
**Category:** bug/logic
**Location:** `hooks/session_context.py:39-47`
**Status:** OPEN
**Determinism:** deterministic
**Pattern:** PAT-001
**Predicted:** Prediction 2 (confidence: HIGH)
**Lens:** integration, data-flow

**Problem:** `_read_toml_string()` requires values to be enclosed in quotes (double or single). If a TOML value is unquoted (which `validate_config.parse_simple_toml()` accepts as a raw string), `_read_toml_string()` returns an empty string. This means if `project.toml` contains an unquoted `sprints_dir = sprints` instead of `sprints_dir = "sprints"`, the session_context hook silently fails to read the value and skips all context injection.

**Evidence:** Reproduction test -- `_read_toml_string('[paths]\nsprints_dir = sprints\n', 'paths', 'sprints_dir')` returns `''` while `parse_simple_toml` returns `{'paths': {'sprints_dir': 'sprints'}}`.

**Discovery Chain:** Three TOML parsers for one file format -> tested edge case (unquoted values) -> session_context regex requires quotes -> empty string returned silently

**Acceptance Criteria:**
- [ ] `_read_toml_string` returns `"sprints"` for unquoted `sprints_dir = sprints`
- [ ] Test added confirming unquoted value handling matches validate_config

**Validation Command:**
```bash
python3 -c "from hooks.session_context import _read_toml_string; assert _read_toml_string('[paths]\nsprints_dir = sprints\n', 'paths', 'sprints_dir') == 'sprints'"
```

### BJ-002: verify_agent_output._read_toml_key returns string for integer/boolean values
**Severity:** MEDIUM
**Category:** bug/type
**Location:** `hooks/verify_agent_output.py:143-148`
**Status:** OPEN
**Determinism:** deterministic
**Pattern:** PAT-001
**Predicted:** Prediction 1 (confidence: HIGH)
**Lens:** integration, data-flow

**Problem:** `_read_toml_key()` returns raw string `"42"` for integer values and `"true"` for boolean values, while `validate_config.parse_simple_toml()` returns int `42` and bool `True`. Currently hooks only read `check_commands` (array) and `smoke_command` (string), so the type divergence does not cause runtime bugs. But if any hook ever reads an integer or boolean key (e.g., a future `timeout` or `enabled` config), the type mismatch would cause silent failures.

**Evidence:** `_read_toml_key('[project]\nversion = 42\n', 'project', 'version')` returns `'42'` (str), `parse_simple_toml` returns `42` (int). `_read_toml_key('[project]\nenabled = true\n', 'project', 'enabled')` returns `'true'` (str), `parse_simple_toml` returns `True` (bool).

**Discovery Chain:** Triple TOML parser divergence predicted -> tested integer/boolean values -> type mismatch confirmed -> latent bug if new config keys added

**Acceptance Criteria:**
- [ ] Document that `_read_toml_key` is string-only and should not be used for integer/boolean keys
- [ ] OR update `_read_toml_key` to handle int/bool types matching validate_config

**Validation Command:**
```bash
python3 -c "from hooks.verify_agent_output import _read_toml_key; r = _read_toml_key('[ci]\ntimeout = 42\n', 'ci', 'timeout'); print(type(r), r)"
```

### BJ-003: Triple TOML parser divergence -- systemic design risk
**Severity:** HIGH
**Category:** design/inconsistency
**Location:** `hooks/verify_agent_output.py:111`, `hooks/session_context.py:23`, `hooks/review_gate.py:29`, `scripts/validate_config.py:135`
**Status:** OPEN
**Pattern:** PAT-001
**Predicted:** Predictions 1, 2, 3 (confidence: HIGH)
**Lens:** integration, contract

**Problem:** Three independent TOML parsers exist for reading `project.toml`. Each handles a different subset of the TOML spec. When the file format evolves (new keys, different quoting, inline comments), each parser must be updated independently -- and historically they have diverged (BH35-005 added comment handling to hooks but not identically to validate_config). This is the textbook "dual-parser-divergence" pattern from the global pattern library, but with THREE parsers instead of two.

**Evidence:** session_context fails on unquoted values (BJ-001), verify_agent_output returns wrong types (BJ-002), review_gate has the simplest parser. All confirmed by direct testing.

**Discovery Chain:** Pattern library match (dual-parser-divergence) -> code inspection found THREE parsers -> edge case testing confirmed divergent behavior

**Acceptance Criteria:**
- [ ] Either consolidate to a single shared parser OR document the contract each hook parser must satisfy and add divergence tests
- [ ] If consolidation: hooks import a shared lightweight parser (not full validate_config to maintain hook isolation)

**Validation Command:**
```bash
python3 -c "
import sys; sys.path.insert(0, 'scripts'); sys.path.insert(0, 'hooks')
from validate_config import parse_simple_toml
from verify_agent_output import _read_toml_key
from session_context import _read_toml_string
toml = '[paths]\nsprints_dir = sprints\n'
assert _read_toml_string(toml, 'paths', 'sprints_dir') == parse_simple_toml(toml)['paths']['sprints_dir'], 'session_context diverges from validate_config on unquoted values'
print('PASS: all parsers agree')
"
```

### BJ-004: Unused json import in hooks after refactor
**Severity:** LOW
**Category:** design/dead-code
**Location:** `hooks/commit_gate.py:12`, `hooks/verify_agent_output.py:13`
**Status:** OPEN
**Lens:** component

**Problem:** Both hook files import `json` but never use it. The JSON output is handled by `_common.py` helpers (`exit_ok`, `exit_warn`, `exit_block`). These became dead imports when the hooks were refactored to use the JSON output protocol in `_common.py`.

**Evidence:** `ruff check hooks/` reports F401 for both files.

**Discovery Chain:** Ruff lint -> F401 unused import -> confirmed by reading code (json used in _common.py, not in hook files directly)

**Acceptance Criteria:**
- [ ] Remove `import json` from both files
- [ ] Ruff check passes clean

**Validation Command:**
```bash
python -m ruff check hooks/commit_gate.py hooks/verify_agent_output.py
```

### BJ-005: commit_gate working tree hash does not cover untracked files
**Severity:** MEDIUM
**Category:** design/inconsistency
**Location:** `hooks/commit_gate.py:57-79`
**Status:** OPEN
**Determinism:** deterministic
**Predicted:** Prediction 5 (confidence: MEDIUM)
**Lens:** security, data-flow

**Problem:** `_working_tree_hash()` uses `git diff HEAD` which only captures differences between HEAD and the working tree for TRACKED files. New untracked files are not included. If tests pass, then a new source file is created and staged, the hash from `git diff HEAD` changes (staging changes the diff), so the commit gate correctly detects the change. However, if an agent runs tests, then creates a new file, and `git add`s it, the `git diff HEAD` output changes and blocks the commit. This is correct behavior. The narrower risk: if an agent runs tests in a working tree that already has unstaged new files, those files are invisible to the hash. The commit gate would allow a commit that includes untested new files added BEFORE the test run, because they were never part of the diff.

**Evidence:** `git diff HEAD` does not include untracked files. The hash comparison is between test-time state and commit-time state, so any change (including staging new files) is detected. The edge case is files added to the index BEFORE tests ran.

**Discovery Chain:** git diff HEAD analysis -> does not include untracked files -> staging changes diff -> risk narrower than predicted -> edge case: pre-existing staged files not covered

**Acceptance Criteria:**
- [ ] Document the limitation that the hash covers tracked/staged files only, not untracked files
- [ ] Consider `git diff HEAD --staged` or `git status --porcelain` to broaden coverage

**Validation Command:**
```bash
echo "Design documentation item"
```

### BJ-006: session_context.extract_high_risks column index shift on empty cells
**Severity:** MEDIUM
**Category:** bug/logic
**Location:** `hooks/session_context.py:132-144`
**Status:** OPEN
**Determinism:** deterministic
**Predicted:** Prediction 6 (confidence: MEDIUM)
**Lens:** data-flow, error-propagation

**Problem:** `extract_high_risks()` splits table rows by `|`, filters empty strings with `[c for c in cells if c]`, then accesses by index (cells[2] for severity, cells[3] for status). If a cell in the middle is empty, filtering removes it, shifting indices. For example, `| R1 |  | High | Open |` would have cells = ['R1', 'High', 'Open'] after filtering, so cells[2] = 'Open' (status) would be checked as severity.

**Evidence:** Direct reproduction: `extract_high_risks()` with a risk register containing `| R1 |  | High | Open |` returns `[]` instead of finding the high-severity risk. Confirmed by test.

**Discovery Chain:** Risk table parser indexes by position -> empty cell filter shifts indices -> severity/status read from wrong column -> high-severity risk silently dropped

**Acceptance Criteria:**
- [ ] Use positional indexing based on the original split, not the filtered list (remove empty-string filter, or use pre-filter indexing)
- [ ] Test with a table row containing an empty cell

**Validation Command:**
```bash
python3 -c "
from hooks.session_context import extract_high_risks
import tempfile; from pathlib import Path
with tempfile.TemporaryDirectory() as td:
    Path(td, 'risk-register.md').write_text('| ID | Title | Severity | Status |\n|----|-------|----------|--------|\n| R1 |  | High | Open |\n')
    r = extract_high_risks(td)
    assert len(r) == 1, f'Expected 1 risk, got {len(r)}: {r}'
    print('PASS')
"
```

### BJ-007: review_gate._log_blocked sprints_dir parser silently fails on unquoted values
**Severity:** LOW
**Category:** bug/logic
**Location:** `hooks/review_gate.py:211`
**Status:** OPEN
**Determinism:** theoretical
**Pattern:** PAT-001
**Predicted:** Prediction 7 (confidence: LOW)
**Lens:** contract

**Problem:** The regex at line 211 `sprints_dir\s*=\s*["\']([^"\']*)["\']` requires quotes around the value. If `sprints_dir = sprints` is unquoted (which validate_config accepts), the regex fails silently and falls back to the default `sprint-config/sprints`. The audit log would be written to the wrong directory. Low severity because: (1) sprint_init.py always generates quoted values, (2) the audit log location being wrong is a minor inconvenience, not a security issue.

**Evidence:** Regex pattern at review_gate.py:211 requires quote delimiters. Same class of bug as BJ-001 (PAT-001).

**Discovery Chain:** PAT-001 pattern -> review_gate also has inline parser -> regex requires quotes -> unquoted values fall back to default path -> audit log in wrong location

**Acceptance Criteria:**
- [ ] Ensure sprints_dir in project.toml is always quoted (document requirement) OR add unquoted fallback

**Validation Command:**
```bash
echo "Low severity -- theoretical risk from unlikely TOML format"
```
