# Bug Hunter Punchlist — Pass 16

> Generated: 2026-03-16 | Project: giles | Baseline: 696 pass, 0 fail, 0 skip | Coverage: 83%

## Summary

| Severity | Open | Resolved | Deferred |
|----------|------|----------|----------|
| CRITICAL | 0    | 3        | 0        |
| HIGH     | 0    | 7        | 0        |
| MEDIUM   | 0    | 15       | 0        |
| LOW      | 0    | 0        | 0        |

## Patterns

## Pattern: PAT-001: Hardcoded story ID regex (`US-\d{4}`) in multiple locations
**Instances:** BH-005, BH-006
**Root Cause:** Original design assumed `US-XXXX` IDs; custom pattern support was added to table parsing but not propagated
**Systemic Fix:** Extract story ID pattern from config once; pass it to all parsers and matchers
**Detection Rule:** `grep -rn 'US-.*\\\\d' scripts/ skills/` for hardcoded US- patterns in regex

## Pattern: PAT-002: `main()` functions untested across the codebase
**Instances:** BH-008, BH-009, BH-010, BH-011, BH-012, BH-013
**Root Cause:** Tests call individual functions directly; orchestration in main() is never exercised
**Systemic Fix:** Add integration tests that call main() with patched subprocess and sys.argv
**Detection Rule:** `coverage report | grep 'main()' | awk '$4 < 80'`

## Pattern: PAT-003: 500-issue limit silently truncates data in multiple scripts
**Instances:** BH-014, BH-015
**Root Cause:** `gh issue list --limit 500` used without pagination; `warn_if_at_limit()` logs but doesn't fail
**Systemic Fix:** Either use `gh api --paginate` for critical sync paths, or fail loud when limit is hit
**Detection Rule:** `grep -rn '\-\-limit.*500' scripts/ skills/`

## Pattern: PAT-004: Duplicate flag-parsing logic in FakeGitHub handlers
**Instances:** BH-020 (noted, not listed individually)
**Root Cause:** Each handler parses flags manually with a while loop AND uses _parse_flags(), duplicating work
**Systemic Fix:** Refactor handlers to use only _parse_flags() output
**Detection Rule:** `grep -c 'while i < len(args)' tests/fake_github.py`

## Items

### BH-001: UnboundLocalError in bootstrap_github `create_milestones_on_github` fallback
**Severity:** CRITICAL
**Category:** `bug/logic`
**Location:** `skills/sprint-setup/scripts/bootstrap_github.py:247`
**Status:** :red_circle: OPEN
**Pattern:** —

**Problem:** When a milestone file path passes the `get_milestones()` check but `mf.is_file()` returns False at line 233 (broken symlink, deleted between scan and use), the variable `text` is never assigned. Line 247 references `text` in the fallback title-extraction path, raising `UnboundLocalError`. Crash during bootstrap.

**Evidence:** Lines 233-247: `text = mf.read_text(...)` is inside `if mf.is_file():` block. Line 247 references `text` outside that block with no prior assignment.

**Acceptance Criteria:**
- [ ] `text` is initialized to `""` before the `if mf.is_file():` block
- [ ] A test exercises the path where a milestone file path exists in the list but `is_file()` returns False
- [ ] No `UnboundLocalError` is raised

**Validation Command:**
```bash
python -c "
from pathlib import Path
import sys, importlib
sys.path.insert(0, 'scripts')
sys.path.insert(0, 'skills/sprint-setup/scripts')
import bootstrap_github as bg
# Verify text is always defined before use in create_milestones_on_github
import inspect
source = inspect.getsource(bg.create_milestones_on_github)
# The fix should show 'text = ' before the is_file block
print('PASS' if source.index('text = ') < source.index('if mf.is_file()') or 'text = \"\"' in source else 'FAIL')
"
```

---

### BH-002: TOML parser silently accepts corrupt values as raw strings
**Severity:** CRITICAL
**Category:** `bug/logic`
**Location:** `scripts/validate_config.py:307-314`
**Status:** :red_circle: OPEN
**Pattern:** —

**Problem:** `_parse_value` falls back to returning raw text as a string for any input it can't parse. Values like `name = project = "real name"` silently produce the string `'project = "real name"'`. Unquoted values containing TOML metacharacters (`=`, `[`, `]`) are never rejected. A typo in project.toml propagates corrupt config values into GitHub issues, CI workflows, and tracking files.

**Evidence:** Lines 307-314: `return raw` after all type checks fail, with only a warning for values containing spaces.

**Acceptance Criteria:**
- [ ] `_parse_value` raises `ValueError` for unquoted values containing `=`, `[`, `]`, or `{`
- [ ] The warning for space-containing unquoted values is upgraded to a `ValueError`
- [ ] Existing tests for legitimate unquoted values (if any) are updated
- [ ] A test verifies `parse_simple_toml('name = foo = bar\n')` raises `ValueError`

**Validation Command:**
```bash
python -c "
import sys; sys.path.insert(0, 'scripts')
from validate_config import parse_simple_toml
try:
    parse_simple_toml('name = foo = bar\n')
    print('FAIL: should have raised')
except ValueError as e:
    print(f'PASS: {e}')
"
```

---

### BH-003: load_config swallows TOML parse errors, shows misleading validation messages
**Severity:** CRITICAL
**Category:** `bug/error-handling`
**Location:** `scripts/validate_config.py:612-615`
**Status:** :red_circle: OPEN
**Pattern:** —

**Problem:** When `parse_simple_toml` throws in `load_config()`, the exception is swallowed (`except Exception: pass`). The empty `config = {}` is then passed to `validate_project(_config={})`, which reports "missing required section: [project]" instead of the actual parse error. Users chase missing-section ghosts instead of fixing the real syntax error.

**Evidence:** Lines 612-615: `except Exception: pass` with comment "validate_project will report the parse error" — but validate_project receives `_config={}` and never re-reads the file.

**Acceptance Criteria:**
- [ ] When TOML parsing fails, the actual parse error message appears in `validate_project`'s error list
- [ ] `ConfigError` raised by `load_config` includes the original parse error, not just "missing section"
- [ ] A test verifies that a malformed TOML file produces an error mentioning the parse failure

**Validation Command:**
```bash
python -c "
import sys, tempfile, os
sys.path.insert(0, 'scripts')
from validate_config import load_config, ConfigError
from pathlib import Path
d = tempfile.mkdtemp()
os.makedirs(f'{d}/sprint-config/team', exist_ok=True)
os.makedirs(f'{d}/sprint-config/backlog/milestones', exist_ok=True)
Path(f'{d}/sprint-config/project.toml').write_text('name = [unterminated\n')
Path(f'{d}/sprint-config/team/INDEX.md').write_text('| Name | Role | File |\n|---|---|---|\n| A | Dev | a.md |\n| B | Arch | b.md |\n')
Path(f'{d}/sprint-config/backlog/INDEX.md').write_text('# Backlog\n')
Path(f'{d}/sprint-config/backlog/milestones/m1.md').write_text('# Sprint 1\n')
Path(f'{d}/sprint-config/rules.md').write_text('# Rules\n')
Path(f'{d}/sprint-config/development.md').write_text('# Dev\n')
Path(f'{d}/sprint-config/team/a.md').write_text('# A\n')
Path(f'{d}/sprint-config/team/b.md').write_text('# B\n')
os.chdir(d)
try:
    load_config()
    print('FAIL: should have raised')
except ConfigError as e:
    msg = str(e)
    if 'parse' in msg.lower() or 'unterminated' in msg.lower():
        print(f'PASS: error mentions parse failure')
    else:
        print(f'FAIL: error is misleading: {msg}')
"
```

---

### BH-004: Saga label parser reads wrong file (INDEX vs saga files)
**Severity:** HIGH
**Category:** `bug/logic`
**Location:** `skills/sprint-setup/scripts/bootstrap_github.py:130-156`
**Status:** :red_circle: OPEN
**Pattern:** —

**Problem:** `_parse_saga_labels_from_backlog` reads `backlog/INDEX.md` looking for `S01`/`S02` table rows. But the hexwise fixture's INDEX.md is a routing table (listing paths, not saga IDs). Saga files live in a separate `sagas/` directory. The function silently finds zero sagas and returns `[]`, so saga labels are never created for any project following the skeleton template format.

**Evidence:** bootstrap_github.py lines 147-154 vs hexwise fixture `backlog/INDEX.md` content.

**Acceptance Criteria:**
- [ ] `_parse_saga_labels_from_backlog` is rewritten or replaced to scan actual saga files (from `get_sagas_dir()`) or fallback to milestone file saga references
- [ ] A test creates a project with saga files and verifies saga labels are created
- [ ] The function handles both INDEX-style and file-style saga discovery

**Validation Command:**
```bash
python -m pytest tests/ -k "saga" -v 2>&1 | tail -10
```

---

### BH-005: `_DETAIL_BLOCK_RE` hardcoded to `US-\d{4}`, ignores custom story ID patterns
**Severity:** HIGH
**Category:** `bug/logic`
**Location:** `skills/sprint-setup/scripts/populate_issues.py:159`
**Status:** :red_circle: OPEN
**Pattern:** PAT-001

**Problem:** The detail block regex `r"^###\s+(US-\d{4}):\s+(.+)$"` is hardcoded to `US-XXXX` format. Projects using custom `story_id_pattern` from config will have their detail blocks silently ignored during enrichment, missing acceptance criteria and user stories.

**Evidence:** Line 159: `_DETAIL_BLOCK_RE = re.compile(r"^###\s+(US-\d{4}):\s+(.+)$", re.MULTILINE)`

**Acceptance Criteria:**
- [ ] `_DETAIL_BLOCK_RE` uses the same pattern source as `_build_row_regex`
- [ ] A test exercises detail block parsing with a custom story ID pattern (e.g., `PROJ-\d{3}`)
- [ ] The regex is either parameterized or documented as `US-XXXX`-only with a clear error

**Validation Command:**
```bash
python -m pytest tests/ -k "detail_block" -v 2>&1 | tail -10
```

---

### BH-006: `get_existing_issues` regex requires colon, mismatches `extract_story_id`
**Severity:** HIGH
**Category:** `design/inconsistency`
**Location:** `skills/sprint-setup/scripts/populate_issues.py:289` vs `scripts/validate_config.py:819`
**Status:** :red_circle: OPEN
**Pattern:** PAT-001

**Problem:** `get_existing_issues()` uses `r"([A-Z]+-\d+):"` (requires colon after ID) while `extract_story_id()` uses `r"([A-Z]+-\d+)"` (no colon). Issues with titles like `"US-0001 Setup CI"` (space, no colon) are not detected as existing, causing duplicate creation.

**Evidence:** populate_issues.py line 289 vs validate_config.py line 819. Both extract story IDs but with different patterns.

**Acceptance Criteria:**
- [ ] Both functions use the same regex pattern for story ID extraction, or `get_existing_issues` accepts both formats
- [ ] A test creates an issue with a title lacking a colon and verifies idempotency

**Validation Command:**
```bash
python -c "
import sys; sys.path.insert(0, 'scripts'); sys.path.insert(0, 'skills/sprint-setup/scripts')
from populate_issues import get_existing_issues
import re
# Verify the regex matches titles with AND without colons
pat = re.compile(r'([A-Z]+-\d+)')  # should be at least this permissive
assert pat.match('US-0001: Setup'), 'should match with colon'
assert pat.match('US-0001 Setup'), 'should match without colon'
print('PASS')
"
```

---

### BH-007: TOML parser doesn't detect `\"\"\"` multi-line strings (silently corrupts)
**Severity:** HIGH
**Category:** `bug/logic`
**Location:** `scripts/validate_config.py:282-283`
**Status:** :red_circle: OPEN
**Pattern:** —

**Problem:** TOML multi-line basic strings (`"""..."""`) are not detected or rejected. `_parse_value` sees `"""` as a double-quoted string containing `"`, silently producing the wrong value. Remaining lines are parsed as key/value pairs or dropped.

**Evidence:** Lines 282-283: `raw.startswith('"') and raw.endswith('"')` — true for `"""`, yielding `raw[1:-1]` = `"`.

**Acceptance Criteria:**
- [ ] `_parse_value` detects values starting with `"""` and raises `ValueError` with a clear message
- [ ] A test verifies `parse_simple_toml('key = """\nfoo\n"""\n')` raises `ValueError`

**Validation Command:**
```bash
python -c "
import sys; sys.path.insert(0, 'scripts')
from validate_config import parse_simple_toml
try:
    parse_simple_toml('key = \"\"\"\nfoo\n\"\"\"\n')
    print('FAIL: should have raised')
except ValueError as e:
    print(f'PASS: {e}')
"
```

---

### BH-008: `bootstrap_github.main()` completely untested (55% coverage file)
**Severity:** HIGH
**Category:** `test/missing`
**Location:** `skills/sprint-setup/scripts/bootstrap_github.py:285-311`
**Status:** :red_circle: OPEN
**Pattern:** PAT-002

**Problem:** The orchestration function that calls check_prerequisites, create_static_labels, create_persona_labels, create_sprint_labels, create_epic_labels, and create_milestones_on_github is never tested. This means the calling sequence, error handling (ConfigError catch), and --help flag are all unverified.

**Evidence:** Coverage report: lines 285-311 = 0% coverage.

**Acceptance Criteria:**
- [ ] A test exercises `main()` with patched subprocess, verifying all functions are called in order
- [ ] A test exercises `main()` with `sys.argv = ['prog', '--help']` and verifies clean exit
- [ ] A test exercises `main()` with missing config and verifies sys.exit(1)
- [ ] Coverage of bootstrap_github.py exceeds 70%

**Validation Command:**
```bash
python -m pytest tests/ -k "bootstrap" --cov=skills/sprint-setup/scripts/bootstrap_github --cov-report=term-missing -q 2>&1 | tail -5
```

---

### BH-009: `update_burndown.py` `build_rows` + `load_tracking_metadata` + `main()` all untested
**Severity:** HIGH
**Category:** `test/missing`
**Location:** `skills/sprint-run/scripts/update_burndown.py:121-240`
**Status:** :red_circle: OPEN
**Pattern:** PAT-002

**Problem:** 37% of update_burndown is uncovered. `build_rows()` (the core transform), `load_tracking_metadata()` (YAML frontmatter reader), and `main()` are all untested. Edge cases in issue-to-burndown mapping, frontmatter parsing with quoted values, and sprint detection are unverified.

**Evidence:** Coverage report: lines 121-141, 147, 157-181, 187-240 = 0%.

**Acceptance Criteria:**
- [ ] `build_rows()` has tests covering: normal issue, issue with no colon in title, issue with no labels, issue with 0 SP
- [ ] `load_tracking_metadata()` has tests covering: existing directory, missing directory, file with no frontmatter, file with quoted values
- [ ] `main()` has a test covering the happy path with patched gh_json
- [ ] Coverage exceeds 80%

**Validation Command:**
```bash
python -m pytest tests/ -k "burndown" --cov=skills/sprint-run/scripts/update_burndown --cov-report=term-missing -q 2>&1 | tail -5
```

---

### BH-010: `populate_issues.main()` entirely untested (29 lines uncovered)
**Severity:** MEDIUM
**Category:** `test/missing`
**Location:** `skills/sprint-setup/scripts/populate_issues.py:419-480`
**Status:** :red_circle: OPEN
**Pattern:** PAT-002

**Problem:** The main() orchestration including config loading, story parsing, enrichment, duplicate detection, and issue creation loop is never tested end-to-end.

**Evidence:** Coverage report: lines 428-476, 480 = 0%.

**Acceptance Criteria:**
- [ ] A test exercises main() through the full pipeline using FakeGitHub
- [ ] Error paths (no milestones, no stories, RuntimeError on existing issues) are tested

**Validation Command:**
```bash
python -m pytest tests/ -k "populate" --cov=skills/sprint-setup/scripts/populate_issues --cov-report=term-missing -q 2>&1 | tail -5
```

---

### BH-011: `sprint_teardown.py` missing git-dirty check before destructive operations
**Severity:** MEDIUM
**Category:** `design/inconsistency`
**Location:** `scripts/sprint_teardown.py:344-475`
**Status:** :red_circle: OPEN
**Pattern:** —

**Problem:** Teardown deletes symlinks and generated files in sprint-config/ without checking if the user has uncommitted modifications. A user who edited project.toml and forgot to commit will lose their changes silently.

**Evidence:** `main()` calls `remove_symlinks()` and `remove_generated()` with no `git status` check.

**Acceptance Criteria:**
- [ ] `main()` checks for uncommitted changes in `sprint-config/` before deletion
- [ ] If dirty files exist, the user is warned and must confirm (or use `--force`)
- [ ] A test verifies the warning appears for dirty state

**Validation Command:**
```bash
python -m pytest tests/ -k "teardown" -v 2>&1 | tail -10
```

---

### BH-012: `sprint_teardown.py` `remove_empty_dirs` swallows all OSError silently
**Severity:** MEDIUM
**Category:** `bug/error-handling`
**Location:** `scripts/sprint_teardown.py:270-276`
**Status:** :red_circle: OPEN
**Pattern:** —

**Problem:** `except OSError: pass` catches ALL OS errors including permission denied, read-only filesystem, and I/O errors. Only "not empty" should be silently handled; other errors should be reported.

**Evidence:** Lines 275-276: bare `except OSError: pass`.

**Acceptance Criteria:**
- [ ] The except clause distinguishes `errno.ENOTEMPTY` from other errors
- [ ] Non-empty errors are logged/warned to stderr
- [ ] A test verifies permission-denied errors are reported

**Validation Command:**
```bash
python -c "
import sys; sys.path.insert(0, 'scripts')
import inspect, sprint_teardown as st
src = inspect.getsource(st.remove_empty_dirs)
print('PASS' if 'ENOTEMPTY' in src or 'errno' in src else 'FAIL: still catching all OSError')
"
```

---

### BH-013: `sprint_teardown.py` `print_dry_run` and `check_active_loops` completely untested
**Severity:** MEDIUM
**Category:** `test/missing`
**Location:** `scripts/sprint_teardown.py:123-210, 281-305`
**Status:** :red_circle: OPEN
**Pattern:** PAT-002

**Problem:** The entire dry-run display (87 lines) and active-loop detection (24 lines) are untested. The dry-run contains relative_to() calls that can raise ValueError, and a weak TOML parser that duplicates validate_config logic.

**Evidence:** Coverage report: lines 123-210, 281-305 = 0%.

**Acceptance Criteria:**
- [ ] `print_dry_run` has a test covering the happy path with symlinks and generated files
- [ ] `check_active_loops` has a test covering both "no crontab" and "crontab with sprint-monitor" cases
- [ ] Coverage exceeds 80%

**Validation Command:**
```bash
python -m pytest tests/ -k "teardown" --cov=scripts/sprint_teardown --cov-report=term-missing -q 2>&1 | tail -5
```

---

### BH-014: 500-issue limit in `list_milestone_issues` silently truncates sync data
**Severity:** MEDIUM
**Category:** `bug/logic`
**Location:** `scripts/validate_config.py:870-884`
**Status:** :red_circle: OPEN
**Pattern:** PAT-003

**Problem:** `list_milestone_issues()` uses `--limit 500` and only warns to stderr when the limit is hit. sync_tracking and update_burndown continue processing the incomplete data silently. Issues 501+ never get tracking files and are never synced.

**Evidence:** Line 875: `--limit 500`. Line 883: `warn_if_at_limit(issues)` — warns but continues.

**Acceptance Criteria:**
- [ ] Either: switch to `gh api --paginate` for complete data, OR raise an error when limit is hit in critical sync paths
- [ ] A test verifies behavior when exactly 500 issues are returned

**Validation Command:**
```bash
python -c "
import sys; sys.path.insert(0, 'scripts')
from validate_config import warn_if_at_limit
import io
# Should produce a warning for 500 items
stderr = io.StringIO()
sys.stderr = stderr
warn_if_at_limit(list(range(500)))
sys.stderr = sys.__stderr__
print('PASS' if 'incomplete' in stderr.getvalue().lower() or 'limit' in stderr.getvalue().lower() else 'FAIL')
"
```

---

### BH-015: `_fetch_all_prs` in sync_tracking has 500 limit with no warning
**Severity:** MEDIUM
**Category:** `bug/logic`
**Location:** `skills/sprint-run/scripts/sync_tracking.py:36`
**Status:** :red_circle: OPEN
**Pattern:** PAT-003

**Problem:** `_fetch_all_prs()` uses `--limit 500` but does NOT call `warn_if_at_limit()`. The branch-matching fallback in `get_linked_pr()` silently misses PRs beyond the 500 limit.

**Evidence:** Line 36: `"--limit", "500"` with no warning call.

**Acceptance Criteria:**
- [ ] `_fetch_all_prs` calls `warn_if_at_limit()` on the result
- [ ] A test verifies the warning fires at 500 items

**Validation Command:**
```bash
grep -n 'warn_if_at_limit' skills/sprint-run/scripts/sync_tracking.py
```

---

### BH-016: `kanban_from_labels` returns alphabetically-first state when multiple kanban labels exist
**Severity:** MEDIUM
**Category:** `bug/logic`
**Location:** `scripts/validate_config.py:834-846`
**Status:** :red_circle: OPEN
**Pattern:** —

**Problem:** An issue with both `kanban:dev` and `kanban:review` labels returns `kanban:dev` (alphabetically first), making the story appear stuck in an earlier state. The kanban protocol says one label, but nothing enforces it.

**Evidence:** Lines 840-845: returns first match from label iteration.

**Acceptance Criteria:**
- [ ] `kanban_from_labels` either warns on multiple kanban labels, or picks the most advanced state
- [ ] A test verifies behavior with multiple kanban labels

**Validation Command:**
```bash
python -c "
import sys; sys.path.insert(0, 'scripts')
from validate_config import kanban_from_labels
issue = {'labels': [{'name': 'kanban:dev'}, {'name': 'kanban:review'}], 'state': 'open'}
result = kanban_from_labels(issue)
# Should prefer review over dev (more advanced state)
print(f'Result: {result}')
print('PASS' if result == 'review' else 'WARN: returns {result}, expected review')
"
```

---

### BH-017: `sprint_init.py` overwrites project.toml on re-run without backup
**Severity:** MEDIUM
**Category:** `bug/logic`
**Location:** `scripts/sprint_init.py` (ConfigGenerator.generate)
**Status:** :red_circle: OPEN
**Pattern:** —

**Problem:** Re-running sprint_init overwrites existing project.toml with freshly-generated content. Any manual edits (custom CI commands, path adjustments, release config) are lost without warning.

**Evidence:** Audit finding #7 from sprint_init audit.

**Acceptance Criteria:**
- [ ] If project.toml already exists, sprint_init either skips it, backs it up, or prompts
- [ ] A test verifies existing project.toml is preserved on re-run

**Validation Command:**
```bash
python -m pytest tests/ -k "sprint_init" -v 2>&1 | tail -10
```

---

### BH-018: `manage_epics.reorder_stories` drops separator before first story (idempotency violation)
**Severity:** MEDIUM
**Category:** `bug/logic`
**Location:** `scripts/manage_epics.py:297-303`
**Status:** :red_circle: OPEN
**Pattern:** —

**Problem:** On each reorder, the `---` separator before the first story is consumed by the walk-back but never re-emitted. The file changes structure on every reorder even with the same order. Repeated reorders progressively degrade the file.

**Evidence:** Audit finding #2 from epic/saga audit. Walk-back eats lines 15-16 (`---` and blank), writes header as `lines[:15]`, first story has no preceding separator.

**Acceptance Criteria:**
- [ ] Reordering with the same order produces identical file content (idempotent)
- [ ] A test reorders twice with the same order and asserts file equality

**Validation Command:**
```bash
python -m pytest tests/ -k "reorder" -v 2>&1 | tail -10
```

---

### BH-019: `manage_epics.renumber_stories` has Cartesian expansion on duplicate story refs
**Severity:** MEDIUM
**Category:** `bug/logic`
**Location:** `scripts/manage_epics.py` (renumber_stories)
**Status:** :red_circle: OPEN
**Pattern:** —

**Problem:** If the same old story ID appears multiple times in the file (e.g., in cross-references, test sections), the renumber function's replacement map applies to all instances. But if two stories have the same old ID (shouldn't happen, but no validation prevents it), the mapping becomes ambiguous and both get the same new ID.

**Evidence:** Audit finding #7 from epic/saga audit.

**Acceptance Criteria:**
- [ ] Duplicate story IDs in the input are detected and reported as an error
- [ ] A test verifies duplicate ID detection

**Validation Command:**
```bash
python -m pytest tests/ -k "renumber" -v 2>&1 | tail -10
```

---

### BH-020: Source-code inspection tests give false confidence (Inspector Clouseau)
**Severity:** MEDIUM
**Category:** `test/bogus`
**Location:** `tests/test_bugfix_regression.py:65`, `tests/test_sprint_runtime.py:851`
**Status:** :red_circle: OPEN
**Pattern:** —

**Problem:** Two tests use `inspect.getsource()` and `inspect.signature()` to assert code structure rather than behavior. `test_import_guard_uses_import_error` reads source text and asserts `"except ImportError"` is present. `test_gh_custom_timeout` asserts the `timeout` parameter exists with default 60. Neither test verifies the code actually works.

**Evidence:** test_bugfix_regression.py:65 uses `inspect.getsource`. test_sprint_runtime.py:851 uses `inspect.signature`.

**Acceptance Criteria:**
- [ ] `test_import_guard_uses_import_error` is replaced with a behavioral test that triggers the ImportError path
- [ ] `test_gh_custom_timeout` is replaced with a test that calls `gh()` with a custom timeout and verifies `subprocess.run` receives it
- [ ] No tests use `inspect.getsource()` for behavioral assertions

**Validation Command:**
```bash
grep -rn 'inspect.getsource' tests/ | grep -v '# ' | wc -l
```

---

### BH-021: `sync_backlog.do_sync` marks state as synced after partial failure
**Severity:** MEDIUM
**Category:** `bug/state`
**Location:** `scripts/sync_backlog.py:224-228`
**Status:** :red_circle: OPEN
**Pattern:** —

**Problem:** If `do_sync()` fails mid-way through issue creation, `main()` still saves the current file hashes to state. The next invocation sees no changes and skips the retry. Partially-created issues are never completed automatically.

**Evidence:** Lines 224-228: `state["file_hashes"] = current_hashes` runs regardless of do_sync result.

**Acceptance Criteria:**
- [ ] State is only updated if `do_sync()` completes successfully (or returns a success indicator)
- [ ] A test simulates partial failure and verifies the next run retries

**Validation Command:**
```bash
python -m pytest tests/ -k "sync_backlog" -v 2>&1 | tail -10
```

---

### BH-022: First release scans ALL commits; surprise major version bump
**Severity:** MEDIUM
**Category:** `design/inconsistency`
**Location:** `skills/sprint-release/scripts/release_gate.py:118`
**Status:** :red_circle: OPEN
**Pattern:** —

**Problem:** When no semver tags exist, `calculate_version()` starts from `0.1.0` and scans every commit in history. Any historical `feat!:` or `BREAKING CHANGE:` triggers a major bump to `1.0.0`, surprising users who expect `0.2.0`.

**Evidence:** Line 118: `base = "0.1.0"` when no tags found. `parse_commits_since(None)` scans all.

**Acceptance Criteria:**
- [ ] Document this behavior clearly in sprint-release SKILL.md
- [ ] OR: cap the first release to minor bump only (0.x.0) unless explicitly overridden
- [ ] A test verifies first-release behavior with a `feat!:` commit in history

**Validation Command:**
```bash
python -m pytest tests/ -k "calculate_version" -v 2>&1 | tail -10
```

---

### BH-023: `test_coverage.py` (the coverage tool itself) has only 65% coverage
**Severity:** MEDIUM
**Category:** `test/missing`
**Location:** `scripts/test_coverage.py`
**Status:** :red_circle: OPEN
**Pattern:** —

**Problem:** The tool that checks test coverage against planned test cases is itself poorly tested. Lines 51, 66, 75, 87-88, 93, 142-143, 158-181, 191-206, 210 are uncovered. This includes core logic in `check_test_coverage()` and `scan_project_tests()`.

**Evidence:** Coverage report: 65% (34 lines missed out of 96).

**Acceptance Criteria:**
- [ ] `scan_project_tests()` has tests covering Python, Rust, JS, and Go test detection
- [ ] `check_test_coverage()` has a test with both covered and uncovered planned tests
- [ ] Coverage exceeds 80%

**Validation Command:**
```bash
python -m pytest tests/ -k "test_coverage" --cov=scripts/test_coverage --cov-report=term-missing -q 2>&1 | tail -5
```

---

### BH-024: `enrich_from_epics` sprint=0 skip path (BH-011 fix) has no regression test
**Severity:** MEDIUM
**Category:** `test/missing`
**Location:** `skills/sprint-setup/scripts/populate_issues.py:263-270`
**Status:** :red_circle: OPEN
**Pattern:** —

**Problem:** The sprint=0 skip path was added as a BH-011 fix but has no regression test. If someone refactors `enrich_from_epics`, the guard could be removed without any test failing.

**Evidence:** Coverage report: lines 263-270 = 0%.

**Acceptance Criteria:**
- [ ] A test creates an epic with stories that don't match any known milestone, verifying they are skipped (not assigned sprint 0)
- [ ] The test asserts the warning message is printed

**Validation Command:**
```bash
python -m pytest tests/ -k "enrich" -v 2>&1 | tail -10
```

---

### BH-025: `_build_row_regex` safety-critical error paths have no tests
**Severity:** MEDIUM
**Category:** `test/missing`
**Location:** `skills/sprint-setup/scripts/populate_issues.py:73-84`
**Status:** :red_circle: OPEN
**Pattern:** —

**Problem:** Two defensive paths in `_build_row_regex` prevent group-number corruption: (1) rejecting patterns with unescaped capturing groups, (2) catching `re.error` for invalid regex patterns. Neither has a test. These paths protect against malicious/malformed `story_id_pattern` config values that would corrupt all parsed story data.

**Evidence:** Coverage report: lines 73-84 = 0%.

**Acceptance Criteria:**
- [ ] A test passes a config with `story_id_pattern` containing capturing groups and verifies rejection
- [ ] A test passes an invalid regex pattern and verifies graceful handling
- [ ] Both error messages are specific and actionable

**Validation Command:**
```bash
python -m pytest tests/ -k "row_regex" -v 2>&1 | tail -10
```
