# Bug Hunter Pass 4 — Fresh Adversarial Audit Punchlist

Audit date: 2026-03-13 (fourth pass — independent full-codebase review)
Codebase: giles v0.4.0 — 19 scripts (~7,000 LOC), 11 test files (~3,800 LOC), 26 reference docs
Prior audits: Three complete passes (77 items), all resolved. This punchlist covers NEW findings only.

---

## Status Summary

| ID | Title | Severity | Status |
|----|-------|----------|--------|
| P4-01 | `test_coverage.py` completely broken — language case mismatch | **CRITICAL** | RESOLVED |
| P4-02 | `extract_sp` crashes on None/int labels | HIGH | RESOLVED |
| P4-03 | `_parse_stories` unbounded metadata scan reads into story body | HIGH | RESOLVED |
| P4-04 | `manage_epics.py` double-read TOCTOU in remove/reorder | HIGH | RESOLVED |
| P4-05 | `_parse_workflow_runs` misses `- run:` YAML format | MEDIUM | RESOLVED |
| P4-06 | `generate_release_notes` dead compare link on first release | MEDIUM | RESOLVED |
| P4-07 | `get_milestone_numbers` silent failure loses milestone assignment | MEDIUM | RESOLVED |
| P4-08 | `slug_from_title` produces empty string / `.md` filename | MEDIUM | RESOLVED |
| P4-09 | `compute_velocity` division by zero when planned_sp == 0 | MEDIUM | RESOLVED |
| P4-10 | `parse_commits_since` delimiter collision with commit messages | MEDIUM | RESOLVED |
| P4-11 | `sprint_init.py` generates broken TOML when values contain quotes | MEDIUM | RESOLVED |
| P4-12 | `_glob_md` excludes all files when project path contains "build"/"dist" | MEDIUM | RESOLVED |
| P4-13 | `_build_row_regex` injects unvalidated user regex | MEDIUM | RESOLVED |
| P4-14 | `parse_epic` int crash on non-numeric metadata ("TBD", "~30") | MEDIUM | RESOLVED |
| P4-15 | `do_release` partial failure leaves tag but no GitHub Release | MEDIUM | RESOLVED |
| P4-16 | Sprint number inference in opposite order in 2 scripts | MEDIUM | RESOLVED |
| P4-17 | check_status.py phantom flags `--ci-only`/`--pr-only` etc. | MEDIUM | RESOLVED |
| P4-18 | FakeGitHub `_run_list` ignores `--status` filter | MEDIUM | RESOLVED |
| P4-19 | FakeGitHub reviews stored globally, not per-PR | MEDIUM | RESOLVED |
| P4-20 | `test_label_error_handled` has zero explicit assertions | MEDIUM | RESOLVED |
| P4-21 | `list_issues` / `list_milestone_issues` identical functions | MEDIUM | RESOLVED |
| P4-22 | `check_branch_divergence`/`check_direct_pushes` silently swallow errors | LOW | RESOLVED |
| P4-23 | `compute_review_rounds` accepts unused `repo` parameter | LOW | RESOLVED |
| P4-24 | `_extract_sp` pointless alias in check_status.py | LOW | RESOLVED |
| P4-25 | `import os` unused in validate_config.py | LOW | RESOLVED |
| P4-26 | Redundant `import re` inside `extract_sp()` | LOW | RESOLVED |
| P4-27 | `test_do_sync` partially tautological assertions | LOW | RESOLVED |
| P4-28 | FakeGitHub allows duplicate milestone titles | LOW | RESOLVED |
| P4-29 | 5 call sites bypass `gh_json()` with manual `json.loads` | LOW | ACCEPTED |
| P4-30 | `TABLE_ROW` regex defined identically in 3 files | LOW | ACCEPTED |
| P4-31 | `paths.feedback_dir` phantom documentation (no implementation) | LOW | RESOLVED |
| P4-32 | tracking-formats.md missing `integration` from status list | LOW | RESOLVED |
| P4-33 | 50+ stale line references in CLAUDE.md and CHEATSHEET.md | HIGH | RESOLVED |
| P4-34 | CHEATSHEET attributes `extract_story_id`/`kanban_from_labels` to wrong file | MEDIUM | RESOLVED |
| P4-35 | No `get_sprints_dir()` helper despite 5 inline dict-access duplicates | LOW | RESOLVED |
| P4-36 | validate_config.py shared utilities missing from CLAUDE.md function table | LOW | RESOLVED |
| P4-37 | `manage_sagas.py` lstrip("# ") strips chars not prefix | LOW | RESOLVED |
| P4-38 | `get_linked_pr` fetches ALL PRs per issue (API waste) | MEDIUM | RESOLVED |

---

## Priority 0: Critical — Entire Feature Broken

### P4-01: `test_coverage.py` is completely non-functional due to language case mismatch
- **Location**: `scripts/test_coverage.py:163`
- **Bug**: `_TEST_PATTERNS` and `_TEST_FILE_PATTERNS` use lowercase keys (`"rust"`, `"python"`) but `sprint_init.py` generates `project.toml` with capitalized values (`"Rust"`, `"Python"`, `"Go"`). The `main()` function reads `language` without lowercasing, so `_TEST_PATTERNS.get("Rust")` returns `None`. Result: `scan_project_tests()` always returns empty. `detect_test_functions()` always returns empty. The coverage report shows 0 implemented tests for every project.
- **Impact**: The entire test coverage feature is dead. Every planned test is reported as missing regardless of how many are implemented. This was reported in a prior audit as NEW-03 and was never fixed.
- **Acceptance criteria**: `test_coverage.py` correctly detects test functions when the language in `project.toml` is capitalized.
- **Validation**:
  ```bash
  python3 -c "
  import sys; sys.path.insert(0, 'scripts')
  from test_coverage import _TEST_PATTERNS, _TEST_FILE_PATTERNS
  # Simulate what main() does with capitalized language
  language = 'Rust'  # As generated by sprint_init.py
  patterns = _TEST_PATTERNS.get(language)
  file_patterns = _TEST_FILE_PATTERNS.get(language)
  if patterns is None or file_patterns is None:
      print(f'CRITICAL: lookup with {language!r} returns None (keys are {list(_TEST_PATTERNS.keys())})')
  else:
      print('PASS')
  "
  # Should print PASS after fix
  ```

---

## Priority 1: Code Bugs

### P4-02: `extract_sp` crashes on None/int labels
- **Location**: `scripts/validate_config.py:583-584`
- **Bug**: The label type check `label if isinstance(label, str) else label.get("name", "")` only handles `str` vs `dict`. If `label` is `None` or `int` (which GitHub's API can return for malformed issues), `.get()` raises `AttributeError`.
- **Impact**: Any issue with a non-dict, non-string label crashes the entire sprint analytics / burndown pipeline.
- **Acceptance criteria**: The function handles all label types without crashing — `None`, `int`, `bool`, `list` all produce `""` instead of an exception.
- **Validation**:
  ```bash
  python3 -c "
  import sys; sys.path.insert(0, 'scripts')
  from validate_config import extract_sp
  # Should not crash on any of these
  for bad_labels in [[None], [42], [True], [{'name': 'sp:3'}], ['sp:5']]:
      try:
          result = extract_sp({'labels': bad_labels})
          print(f'OK: {bad_labels} -> {result}')
      except Exception as e:
          print(f'CRASH: {bad_labels} -> {type(e).__name__}: {e}')
  "
  # Should print OK for all 5, no CRASH lines
  ```

### P4-02: `_parse_workflow_runs` misses standard `- run:` YAML format
- **Location**: `scripts/sprint_init.py:194`
- **Bug**: `stripped.startswith("run:")` fails to match the standard GitHub Actions format `- run: command` because after `strip()`, the `- ` prefix remains. Only bare `run:` lines (inside `name:` blocks without list syntax) are captured.
- **Impact**: The scanner under-detects CI commands, falling back to language defaults. Result is correct but the detection heuristic misses ~66% of run commands in typical workflows.
- **Acceptance criteria**: Parser captures both `run: command` and `- run: command` formats.
- **Validation**:
  ```bash
  python3 -c "
  import tempfile, os, sys
  sys.path.insert(0, 'scripts')
  from sprint_init import ProjectScanner

  yml = '''jobs:
    build:
      steps:
        - run: echo hello
        - name: Test
          run: pytest
        - run: |
            cargo build
  '''
  with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
      f.write(yml)
      f.flush()
      scanner = ProjectScanner.__new__(ProjectScanner)
      result = scanner._parse_workflow_runs(f.name)
      os.unlink(f.name)

  print(f'Found {len(result)} commands: {result}')
  if len(result) < 2:
      print('BUG: missed - run: format commands')
  else:
      print('PASS')
  "
  ```

### P4-03: `generate_release_notes` creates dead GitHub compare link on first release
- **Location**: `skills/sprint-release/scripts/release_gate.py:348`
- **Bug**: When `base_ver` is the initial version (e.g., `"0.1.0"`), the generated compare link `https://github.com/{repo}/compare/v{base_ver}...v{new_ver}` points to a tag `v0.1.0` that was never created, producing a 404.
- **Impact**: First release notes contain a broken compare link. Subsequent releases are fine.
- **Acceptance criteria**: If no prior tag exists (first release), either omit the compare link or note it's the initial release.
- **Validation**:
  ```bash
  python3 -c "
  import sys; sys.path.insert(0, 'skills/sprint-release/scripts')
  sys.path.insert(0, 'scripts')
  from release_gate import generate_release_notes
  notes = generate_release_notes('1.0.0', '0.1.0', 'owner/repo',
      [{'type': 'feat', 'scope': '', 'description': 'init', 'breaking': False, 'hash': 'abc1234'}])
  if '/compare/v0.1.0' in notes:
      print('BUG: compare link references never-created tag v0.1.0')
  else:
      print('PASS: no dead compare link')
  "
  ```

### P4-04: `get_milestone_numbers` silent failure causes issues without milestone assignment
- **Location**: `skills/sprint-setup/scripts/populate_issues.py:254-260`
- **Bug**: `except (RuntimeError, json.JSONDecodeError, KeyError): return {}` — when the GitHub milestone API fails, the function silently returns an empty dict. The caller at line 380 does `milestone_numbers.get(ms_title)`, gets `None`, and creates issues without any milestone. Unlike `get_existing_issues` (which was fixed in BH3-02 to re-raise), this function still silently swallows errors.
- **Impact**: If GitHub is temporarily unavailable during issue creation, all issues are created without milestone assignment, requiring manual cleanup.
- **Acceptance criteria**: API failure either raises to halt issue creation, or prints a warning and the caller checks for the error.
- **Validation**:
  ```bash
  python3 -c "
  import ast
  src = open('skills/sprint-setup/scripts/populate_issues.py').read()
  tree = ast.parse(src)
  for node in ast.walk(tree):
      if isinstance(node, ast.FunctionDef) and node.name == 'get_milestone_numbers':
          for handler in ast.walk(node):
              if isinstance(handler, ast.ExceptHandler):
                  for ret in ast.walk(handler):
                      if isinstance(ret, ast.Return) and isinstance(ret.value, ast.Dict):
                          if not ret.value.keys:  # empty dict literal
                              print('BUG: still silently returns {} on API failure')
          break
  "
  # Should print nothing after fix
  ```

### P4-05: `slug_from_title` produces empty string for empty/special-char input
- **Location**: `skills/sprint-run/scripts/sync_tracking.py:96-100`
- **Bug**: For titles containing only special characters (e.g., `"!!!"`, `""`, `"   "`), the function returns an empty string, which would create a tracking file named `.md` — a hidden file that breaks filesystem assumptions.
- **Impact**: Garbage GitHub issue titles could create hidden/invalid tracking files. Unlikely in normal operation but possible with manual issue creation.
- **Acceptance criteria**: Empty/whitespace/special-char-only titles produce a safe fallback slug (e.g., `"untitled"` or the issue number).
- **Validation**:
  ```bash
  python3 -c "
  import sys; sys.path.insert(0, 'skills/sprint-run/scripts')
  sys.path.insert(0, 'scripts')
  from sync_tracking import slug_from_title
  for title in ['', '   ', '!!!', '🎉🎉🎉']:
      slug = slug_from_title(title)
      if not slug or slug.startswith('.'):
          print(f'BUG: slug_from_title({title!r}) = {slug!r}')
      else:
          print(f'PASS: slug_from_title({title!r}) = {slug!r}')
  "
  ```

### P4-08: `compute_velocity` division by zero when planned_sp == 0
- **Location**: `scripts/sprint_analytics.py:67-68`
- **Bug**: `pct = round(done_sp / planned_sp * 100)` divides by zero if no stories have SP labels or all SP values are 0.
- **Impact**: Sprint analytics crashes on sprints with no story point labels assigned.
- **Acceptance criteria**: When `planned_sp == 0`, return 0% completion instead of crashing.
- **Validation**:
  ```bash
  python3 -c "
  import sys; sys.path.insert(0, 'scripts')
  from sprint_analytics import compute_velocity
  # Sprint with no SP labels -> planned_sp == 0
  issues = [{'state': 'open', 'labels': [{'name': 'story'}], 'closedAt': None}]
  try:
      result = compute_velocity(issues)
      print(f'PASS: {result}')
  except ZeroDivisionError:
      print('BUG: ZeroDivisionError when planned_sp == 0')
  "
  ```

### P4-03: `_parse_stories` unbounded metadata scan reads into story body
- **Location**: `scripts/manage_epics.py:94-105`
- **Bug**: The inner loop scanning for metadata table rows only breaks on `###` headings. If the story body contains lines matching `| something | something |` (e.g., acceptance criteria comparison tables, markdown tables within task descriptions), those lines are silently parsed as metadata key-value pairs, corrupting `story_meta`.
- **Impact**: Wrong metadata values (story points, priority) parsed from stories with tables in their body text. Silent data corruption.
- **Acceptance criteria**: Metadata scan stops after the first non-table, non-separator, non-blank line following the heading, or after encountering a blank line after table rows.
- **Validation**:
  ```bash
  python3 -c "
  import sys, tempfile; sys.path.insert(0, 'scripts')
  from manage_epics import parse_epic
  from pathlib import Path

  content = '''# Epic: Test

| Field | Value |
|-------|-------|
| Stories | 1 |

### US-01: Story With Table

| Field | Value |
|-------|-------|
| SP | 5 |

Some description with a table:

| Feature | Expected | Actual |
|---------|----------|--------|
| Login   | Works    | Broken |
'''
  d = tempfile.mkdtemp()
  p = Path(d) / 'epic.md'
  p.write_text(content)
  epic = parse_epic(str(p))
  story = epic['raw_sections'][0]
  meta = story.get('meta', {})
  if 'Feature' in meta or 'Login' in meta:
      print(f'BUG: story body table leaked into metadata: {meta}')
  else:
      print(f'PASS: metadata is clean: {meta}')
  import shutil; shutil.rmtree(d)
  "
  ```

### P4-04: `manage_epics.py` double-read TOCTOU in remove_story/reorder_stories
- **Location**: `scripts/manage_epics.py:203-230`
- **Bug**: `remove_story` reads the file twice independently — once via `splitlines()` (line 205) and once via `parse_epic()` (line 206). `parse_epic` returns `start_line`/`end_line` indices from its own read, but these are used to slice the `lines` list from the first read. If the file is modified between reads, the indices won't match. Same pattern in `reorder_stories` (lines 235-236).
- **Impact**: Under concurrent editing, slicing with mismatched indices corrupts the file. Even without concurrency, it's wasteful (redundant read).
- **Acceptance criteria**: Read the file once and use the same content for both parsing and slicing.
- **Validation**:
  ```bash
  python3 -c "
  import ast
  src = open('scripts/manage_epics.py').read()
  tree = ast.parse(src)
  for node in ast.walk(tree):
      if isinstance(node, ast.FunctionDef) and node.name == 'remove_story':
          # Count file read operations (read_text, parse_epic both read)
          reads = []
          for child in ast.walk(node):
              if isinstance(child, ast.Call):
                  if hasattr(child.func, 'attr') and child.func.attr == 'read_text':
                      reads.append('read_text')
                  if hasattr(child.func, 'id') and child.func.id == 'parse_epic':
                      reads.append('parse_epic')
          if len(reads) > 1:
              print(f'BUG: remove_story reads file {len(reads)} times: {reads}')
          else:
              print('PASS')
          break
  "
  ```

### P4-10: `parse_commits_since` delimiter collision with commit messages
- **Location**: `skills/sprint-release/scripts/release_gate.py:53-72`
- **Bug**: The sentinel `---COMMIT---` in `git log --format=%s%n%b---COMMIT---` is used as a split delimiter. If any commit message body contains the literal text `---COMMIT---`, the split produces phantom commits with garbled subjects. A phantom starting with `feat:` triggers a wrong version bump.
- **Impact**: Incorrect version bump decisions. Unlikely but undetectable when it happens.
- **Acceptance criteria**: Use a more unique delimiter (e.g., null bytes via `%x00`) or a UUID-based sentinel.
- **Validation**:
  ```bash
  python3 -c "
  src = open('skills/sprint-release/scripts/release_gate.py').read()
  if '---COMMIT---' in src:
      print('WARNING: still using ---COMMIT--- delimiter (collision risk)')
  else:
      print('PASS')
  "
  ```

### P4-11: `sprint_init.py` generates broken TOML when values contain double quotes
- **Location**: `scripts/sprint_init.py:545-561`
- **Bug**: `f'name = \"{s.project_name.value}\"'` — if the value contains a double quote (e.g., project name `my "cool" project`), the generated TOML is invalid. Same for CI commands containing quotes (more likely: `cargo test -- --test-threads=1`).
- **Impact**: Config file generation produces invalid TOML, breaking all downstream scripts.
- **Acceptance criteria**: Double quotes in values are escaped before interpolation.
- **Validation**:
  ```bash
  python3 -c "
  src = open('scripts/sprint_init.py').read()
  # Count f-string lines that interpolate into double-quoted TOML values
  import re
  # Lines like: name = \\\"{value}\\\"
  unescaped = re.findall(r'f.*?=.*?\\\"{.*?}\\\"', src)
  # Check if any have .replace('\\\"', ...) nearby
  if unescaped:
      # Check if there's escaping logic
      if 'replace' in src and '\\\\\\\"' in src:
          print('PASS: escaping detected')
      else:
          print(f'BUG: {len(unescaped)} unescaped interpolations into TOML strings')
  "
  ```

### P4-12: `_glob_md` excludes all files when project path contains "build"/"dist"
- **Location**: `scripts/sprint_init.py:127-134`
- **Bug**: `any(part in EXCLUDED_DIRS for part in p.parts)` checks ALL path components including parent directories. If the project lives in `/home/user/build/my-project/`, ALL markdown files are excluded because `"build"` is in `EXCLUDED_DIRS` and in `p.parts`.
- **Impact**: Scanner finds zero markdown files, producing empty scan results. Common directory names like `build` and `dist` trigger this.
- **Acceptance criteria**: Only check path parts relative to `self.root`, not the full absolute path.
- **Validation**:
  ```bash
  python3 -c "
  import ast
  src = open('scripts/sprint_init.py').read()
  # Check if _glob_md uses relative_to before checking parts
  if 'relative_to' in src and 'EXCLUDED_DIRS' in src:
      print('PASS: uses relative path for exclusion check')
  elif 'p.parts' in src and 'EXCLUDED_DIRS' in src:
      print('BUG: checks absolute p.parts against EXCLUDED_DIRS')
  "
  ```

### P4-13: `_build_row_regex` injects unvalidated user regex from config
- **Location**: `skills/sprint-setup/scripts/populate_issues.py:60-73`
- **Bug**: The `story_id_pattern` from project.toml is interpolated directly into a regex via `rf\"\\|\\s*({pattern})\\s*\\|...\"`. A malformed pattern crashes with `re.error`. A pattern with capturing groups `(...)` shifts all group numbers, causing the wrong columns to be extracted.
- **Impact**: Crash or silent data corruption from user config values.
- **Acceptance criteria**: Wrap in `try/except re.error` with fallback. Reject patterns containing unescaped groups.
- **Validation**:
  ```bash
  python3 -c "
  import sys; sys.path.insert(0, 'skills/sprint-setup/scripts')
  sys.path.insert(0, 'scripts')
  from populate_issues import _build_row_regex
  # Malformed regex should not crash
  try:
      _build_row_regex({'backlog': {'story_id_pattern': '[unclosed'}})
      print('BUG: no error on malformed regex')
  except Exception as e:
      if 'error' in type(e).__name__.lower():
          print(f'BUG: crashes with {type(e).__name__}: {e}')
      else:
          print(f'Handled: {type(e).__name__}')
  "
  ```

### P4-14: `parse_epic` int conversion crashes on non-numeric metadata ("TBD", "~30")
- **Location**: `scripts/manage_epics.py:45-46`
- **Bug**: `int(metadata.get("Stories", "0"))` — if the "Stories" or "Total SP" value contains non-numeric text (e.g., `"TBD"`, `"~30"`, `"12 stories"`), `int()` raises `ValueError`. Same in `manage_sagas.py:51-53`.
- **Impact**: Script crashes when user-authored epic files have freeform text in metadata.
- **Acceptance criteria**: Safe int parsing that extracts digits or defaults to 0.
- **Validation**:
  ```bash
  python3 -c "
  import sys, tempfile; sys.path.insert(0, 'scripts')
  from manage_epics import parse_epic
  from pathlib import Path

  content = '''# Epic: Test

| Field | Value |
|-------|-------|
| Stories | TBD |
| Total SP | ~30 |
'''
  d = tempfile.mkdtemp()
  p = Path(d) / 'epic.md'
  p.write_text(content)
  try:
      epic = parse_epic(str(p))
      print(f'PASS: parsed with stories={epic[\"stories_count\"]}, sp={epic[\"total_sp\"]}')
  except ValueError as e:
      print(f'BUG: crashes with ValueError: {e}')
  import shutil; shutil.rmtree(d)
  "
  ```

### P4-15: `do_release` partial failure leaves tag but no GitHub Release
- **Location**: `skills/sprint-release/scripts/release_gate.py:453-493`
- **Bug**: Rollback logic only exists for the commit step (lines 428-449). If `gh release create` fails after the tag is created and pushed, the release is in a broken state: tag exists on remote, no Release object. No rollback attempted for tag push.
- **Impact**: Manual cleanup required: `git tag -d vX.Y.Z && git push --delete origin vX.Y.Z`.
- **Acceptance criteria**: Either roll back the tag on failure, or clearly document what to clean up.
- **Validation**:
  ```bash
  python3 -c "
  src = open('skills/sprint-release/scripts/release_gate.py').read()
  if 'push --delete' in src or 'tag -d' in src:
      print('PASS: tag rollback logic exists')
  else:
      print('NOTE: no tag rollback on release failure (document cleanup steps)')
  "
  ```

### P4-38: `get_linked_pr` fetches ALL PRs per issue (API waste)
- **Location**: `skills/sprint-run/scripts/sync_tracking.py:73-90`
- **Bug**: The fallback PR search runs `gh pr list --state all --limit 100` once per issue. For 20 stories, that's 20 API calls each returning up to 100 PRs. The `--limit 100` cap also means repos with 100+ PRs may silently miss linked PRs.
- **Impact**: API rate exhaustion on larger projects; missed PR linkages.
- **Acceptance criteria**: Fetch PR list once and reuse across all issues in the sync.
- **Validation**:
  ```bash
  python3 -c "
  src = open('skills/sprint-run/scripts/sync_tracking.py').read()
  # Check if get_linked_pr is called inside a loop with its own gh call
  if 'def get_linked_pr' in src and 'gh([' in src.split('def get_linked_pr')[1].split('def ')[0]:
      print('NOTE: get_linked_pr makes its own API call (should be batched)')
  else:
      print('PASS: no per-issue API call')
  "
  ```

---

## Priority 2: Design Hardening

### P4-06: `check_branch_divergence`/`check_direct_pushes` silently swallow RuntimeError
- **Location**: `skills/sprint-monitor/scripts/check_status.py:248,277`
- **Bug**: Both functions catch `RuntimeError` and return a neutral report instead of warning the user. If `gh` or `git` fails (auth issue, network error), the monitoring report silently omits these checks with no indication they were skipped.
- **Impact**: Sprint monitor reports appear clean when monitoring is actually broken.
- **Acceptance criteria**: Caught errors produce a warning line in the report (e.g., "Drift check skipped: {error}").
- **Validation**:
  ```bash
  python3 -c "
  src = open('skills/sprint-monitor/scripts/check_status.py').read()
  import re
  # Find except RuntimeError blocks that return without printing/warning
  blocks = re.findall(r'except RuntimeError.*?(?=\n    def |\nclass |\Z)', src, re.DOTALL)
  for b in blocks:
      if 'return' in b and 'warn' not in b.lower() and 'skip' not in b.lower() and 'error' not in b.lower():
          print(f'BUG: silent error swallow found')
  "
  ```

### P4-07: `compute_review_rounds` accepts unused `repo` parameter
- **Location**: `scripts/sprint_analytics.py:76`
- **Bug**: `def compute_review_rounds(repo: str, milestone_title: str)` — the `repo` parameter is never referenced in the function body. `gh pr list` infers the repo from the working directory.
- **Impact**: Dead parameter misleads callers into thinking repo matters. Minor.
- **Acceptance criteria**: Remove the `repo` parameter from the function signature and its call sites.
- **Validation**:
  ```bash
  python3 -c "
  import ast
  src = open('scripts/sprint_analytics.py').read()
  tree = ast.parse(src)
  for node in ast.walk(tree):
      if isinstance(node, ast.FunctionDef) and node.name == 'compute_review_rounds':
          params = [a.arg for a in node.args.args]
          if 'repo' in params:
              print('BUG: compute_review_rounds still has unused repo parameter')
          else:
              print('PASS')
          break
  "
  ```

### P4-12: FakeGitHub `_run_list` ignores `--status` filter
- **Location**: `tests/fake_github.py:355-356`
- **Bug**: `_run_list` parses `--status` but does not filter workflow runs by status. If production code passes `--status completed`, FakeGitHub returns all runs.
- **Impact**: Tests could pass when production code would see different data from GitHub.
- **Acceptance criteria**: `_run_list` filters runs by status when `--status` is provided.
- **Validation**:
  ```bash
  python3 -c "
  import sys; sys.path.insert(0, 'tests')
  from fake_github import FakeGitHub
  fg = FakeGitHub('owner/repo')
  fg.runs = [
      {'status': 'completed', 'conclusion': 'success', 'name': 'ci', 'headBranch': 'main', 'event': 'push', 'url': 'u1'},
      {'status': 'in_progress', 'conclusion': '', 'name': 'ci', 'headBranch': 'main', 'event': 'push', 'url': 'u2'},
  ]
  result = fg.handle(['run', 'list', '--json', 'status,conclusion,name,headBranch,event,url', '--status', 'completed'])
  import json
  runs = json.loads(result)
  if len(runs) != 1:
      print(f'BUG: --status completed returned {len(runs)} runs, expected 1')
  else:
      print('PASS')
  "
  ```

### P4-14: FakeGitHub reviews stored globally, not per-PR
- **Location**: `tests/fake_github.py:446-476`
- **Bug**: `_pr_review` stores reviews in `self.reviews` (a flat list), not associated with specific PRs. Production code querying reviews through a PR object would not find them through FakeGitHub's PR list response.
- **Impact**: Tests that rely on review data work around this by manually attaching reviews to PR dicts in test setup, bypassing FakeGitHub's review mechanism.
- **Acceptance criteria**: `_pr_review` stores reviews on the specific PR object, and `_pr_list` includes reviews in PR JSON output.
- **Validation**:
  ```bash
  python3 -c "
  import sys; sys.path.insert(0, 'tests')
  from fake_github import FakeGitHub
  fg = FakeGitHub('owner/repo')
  fg.handle(['pr', 'create', '--title', 'Test PR', '--body', 'desc', '--base', 'main', '--head', 'feat'])
  fg.handle(['pr', 'review', '1', '--approve', '--body', 'LGTM'])
  import json
  prs = json.loads(fg.handle(['pr', 'list', '--json', 'number,title,reviews']))
  if prs and 'reviews' in prs[0] and len(prs[0]['reviews']) > 0:
      print('PASS: reviews attached to PR')
  else:
      print('BUG: reviews not attached to PR object')
  "
  ```

### P4-15: `test_label_error_handled` has zero explicit assertions
- **Location**: `tests/test_gh_interactions.py:456-460`
- **Bug**: Test only verifies "does not raise". The function could silently swallow all errors with no logging and this test would still pass.
- **Impact**: False confidence that error handling works correctly.
- **Acceptance criteria**: Test asserts that the function either logs a warning or returns a specific sentinel value on error.
- **Validation**:
  ```bash
  python3 -c "
  import ast
  src = open('tests/test_gh_interactions.py').read()
  tree = ast.parse(src)
  for node in ast.walk(tree):
      if isinstance(node, ast.FunctionDef) and node.name == 'test_label_error_handled':
          assertions = [n for n in ast.walk(node) if isinstance(n, ast.Call) and hasattr(n.func, 'attr') and n.func.attr.startswith('assert')]
          if not assertions:
              print(f'BUG: test has {len(assertions)} assertions')
          else:
              print(f'PASS: test has {len(assertions)} assertions')
          break
  "
  ```

### P4-17: `list_issues` / `list_milestone_issues` are identical functions
- **Location**: `skills/sprint-run/scripts/sync_tracking.py:37` and `skills/sprint-run/scripts/update_burndown.py:28`
- **Bug**: Two character-for-character identical functions in two files. Both call `gh(["issue", "list", ...])` with the same args, parse with `json.loads(raw) if raw else []`, call `warn_if_at_limit()`, and return the list.
- **Impact**: Changes to one won't propagate to the other. Maintenance hazard.
- **Acceptance criteria**: Single shared function (e.g., in `validate_config.py`) used by both callers.
- **Validation**:
  ```bash
  python3 -c "
  import ast
  # Check that both files no longer define their own list function
  for path, fname in [
      ('skills/sprint-run/scripts/sync_tracking.py', 'list_issues'),
      ('skills/sprint-run/scripts/update_burndown.py', 'list_milestone_issues')
  ]:
      src = open(path).read()
      tree = ast.parse(src)
      local_defs = [n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == fname]
      if local_defs:
          print(f'DUP: {path} still defines {fname}()')
      else:
          print(f'PASS: {path} no longer defines {fname}()')
  "
  ```

### P4-20: Sprint number inference in opposite order in 2 scripts
- **Location**: `skills/sprint-setup/scripts/bootstrap_github.py:77` and `skills/sprint-setup/scripts/populate_issues.py:118`
- **Bug**: `_collect_sprint_numbers` prefers content headings, falls back to filenames. `_infer_sprint_number` prefers filenames, falls back to content headings. A file named `milestone-1.md` containing `### Sprint 3:` would produce different sprint numbers depending on which script processes it.
- **Impact**: Milestone↔sprint mapping could disagree between label creation and issue creation, assigning stories to wrong sprints.
- **Acceptance criteria**: Both functions use the same priority order (content-first or filename-first, consistently).
- **Validation**:
  ```bash
  python3 -c "
  import tempfile, os, sys
  sys.path.insert(0, 'skills/sprint-setup/scripts')
  sys.path.insert(0, 'scripts')
  from pathlib import Path

  # Create a file with conflicting name vs content
  d = tempfile.mkdtemp()
  p = Path(d) / 'milestone-1.md'
  p.write_text('# Milestone\n\n### Sprint 3: Test\n\n| ID | Title | SP |\n|---|---|---|\n| US-01 | Story | 3 |\n')

  from bootstrap_github import _collect_sprint_numbers
  from populate_issues import _infer_sprint_number

  bs_nums = _collect_sprint_numbers(Path(d))
  pi_num = _infer_sprint_number(p)

  os.unlink(p)
  os.rmdir(d)

  print(f'bootstrap: {bs_nums}, populate: {pi_num}')
  if bs_nums and pi_num and list(bs_nums)[0] != pi_num:
      print('BUG: different sprint numbers from same file')
  else:
      print('PASS: consistent')
  "
  ```

### P4-22: check_status.py phantom flags documented in SKILL.md
- **Location**: `skills/sprint-monitor/SKILL.md:309-313` vs `skills/sprint-monitor/scripts/check_status.py`
- **Bug**: SKILL.md documents `--ci-only`, `--pr-only`, `--burndown-only`, `--dry-run` flags that do not exist in `check_status.py`. The script only accepts a sprint number.
- **Impact**: Agents following SKILL.md would pass flags that are silently ignored (they'd be treated as the sprint number argument and cause a crash or wrong sprint selection).
- **Acceptance criteria**: Either implement the flags, or remove them from SKILL.md.
- **Validation**:
  ```bash
  grep -c '\-\-ci-only\|--pr-only\|--burndown-only\|--dry-run' skills/sprint-monitor/scripts/check_status.py
  grep -c '\-\-ci-only\|--pr-only\|--burndown-only\|--dry-run' skills/sprint-monitor/SKILL.md
  # First should be >= 4 (if implementing) OR second should be 0 (if removing)
  ```

---

## Priority 3: Dead Code & Cleanup

### P4-09: `_extract_sp` pointless alias in check_status.py
- **Location**: `skills/sprint-monitor/scripts/check_status.py:217`
- **Bug**: `_extract_sp = extract_sp` creates a module-level alias that adds no value. Used in `_count_sp()` but could call `extract_sp` directly.
- **Acceptance criteria**: Alias removed, direct call to `extract_sp` used.
- **Validation**:
  ```bash
  grep -c '_extract_sp' skills/sprint-monitor/scripts/check_status.py
  # Should be 0 after fix
  ```

### P4-10: `import os` unused in validate_config.py
- **Location**: `scripts/validate_config.py:12`
- **Bug**: `os` is imported but never referenced. All file operations use `pathlib.Path`.
- **Acceptance criteria**: Remove the import.
- **Validation**:
  ```bash
  python3 -c "
  src = open('scripts/validate_config.py').read()
  import ast
  tree = ast.parse(src)
  names = set()
  for node in ast.walk(tree):
      if isinstance(node, ast.Name):
          names.add(node.id)
  # Check if os is used as a Name anywhere other than import
  imports = [n for n in ast.walk(tree) if isinstance(n, ast.Import)]
  for imp in imports:
      for alias in imp.names:
          if alias.name == 'os' and 'os' not in names - {'os'}:
              # Need better check - look for os.X usage
              pass
  # Simple check:
  lines = [l for l in src.split('\n') if 'os.' in l or 'os,' in l or 'os)' in l]
  non_import = [l for l in lines if 'import' not in l]
  if not non_import:
      print('CONFIRMED: import os is unused')
  else:
      print(f'os used at: {non_import}')
  "
  ```

### P4-11: Redundant `import re` inside `extract_sp()`
- **Location**: `scripts/validate_config.py:587`
- **Bug**: `re` is already imported at module level (line 13). The function-level `import re` is dead — it shadows the module-level import with the same module.
- **Acceptance criteria**: Remove the function-level import.
- **Validation**:
  ```bash
  python3 -c "
  import ast
  src = open('scripts/validate_config.py').read()
  tree = ast.parse(src)
  for node in ast.walk(tree):
      if isinstance(node, ast.FunctionDef) and node.name == 'extract_sp':
          for child in ast.walk(node):
              if isinstance(child, ast.Import):
                  for alias in child.names:
                      if alias.name == 're':
                          print('BUG: redundant import re inside extract_sp()')
          break
  "
  # Should print nothing after fix
  ```

---

## Priority 4: Documentation Drift

### P4-24: 50+ stale line references in CLAUDE.md and CHEATSHEET.md
- **Location**: `CLAUDE.md` and `CHEATSHEET.md` throughout
- **Bug**: Line references have drifted due to code changes. Key patterns:
  - `validate_config.py`: Everything from `_REQUIRED_FILES` onward is off by 17 (16 entries)
  - `sprint_init.py`: CHEATSHEET entries from `detect_persona_files()` onward off by 5 (14 entries)
  - `bootstrap_github.py`: CHEATSHEET entries off by 14 (10 entries)
  - `sync_tracking.py`: CHEATSHEET entries off by 3-25 (8 entries)
  - `sprint_teardown.py`: 3 entries off by 35
  - `populate_issues.py`: 4 entries off by 1
  - `sprint-monitor/SKILL.md`: 7 of 8 section refs off by 1-2
  - `kanban-protocol.md`: 3 entries off by 5
  - `persona-guide.md`: 4 entries off by 1
- **Impact**: Developers navigating by line reference land on wrong code.
- **Acceptance criteria**: All line references in CLAUDE.md and CHEATSHEET.md match actual code.
- **Validation**:
  ```bash
  python3 scripts/verify_line_refs.py CLAUDE.md
  python3 scripts/verify_line_refs.py CHEATSHEET.md
  # Both should report 0 mismatches
  ```

### P4-25: CHEATSHEET attributes 2 functions to wrong file
- **Location**: `CHEATSHEET.md` sync_tracking.py section
- **Bug**: Lists `extract_story_id()` :108 and `kanban_from_labels()` :113 as being in `sync_tracking.py`. They are actually defined in `validate_config.py` (lines 631 and 640). `sync_tracking.py` imports them.
- **Impact**: Developers looking for these functions in sync_tracking.py won't find them.
- **Acceptance criteria**: CHEATSHEET correctly attributes these functions to `validate_config.py`.
- **Validation**:
  ```bash
  python3 -c "
  import ast
  src = open('skills/sprint-run/scripts/sync_tracking.py').read()
  tree = ast.parse(src)
  local_fns = [n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
  for name in ['extract_story_id', 'kanban_from_labels']:
      if name in local_fns:
          print(f'PASS: {name} defined in sync_tracking.py')
      else:
          cheatsheet = open('CHEATSHEET.md').read()
          if f'sync_tracking' in cheatsheet and name in cheatsheet:
              # Check if it's listed under sync_tracking section
              print(f'CHECK: {name} may still be attributed to sync_tracking.py in CHEATSHEET')
  "
  ```

### P4-21: `paths.feedback_dir` phantom documentation
- **Location**: `CLAUDE.md:107`
- **Bug**: Listed as an optional TOML key but no `get_feedback_dir()` function exists and no script references `feedback_dir`.
- **Acceptance criteria**: Either implement the functionality or remove from CLAUDE.md.
- **Validation**:
  ```bash
  grep -r 'feedback_dir' scripts/ skills/ --include='*.py' | grep -v '__pycache__'
  # Should either find implementation or be empty (if removed from docs)
  ```

### P4-23: tracking-formats.md missing `integration` from status list
- **Location**: `skills/sprint-run/references/tracking-formats.md:41`
- **Bug**: Lists 5 kanban states (`todo`, `design`, `dev`, `review`, `done`) but there are 6 — `integration` is missing.
- **Acceptance criteria**: All 6 states listed.
- **Validation**:
  ```bash
  grep -c 'integration' skills/sprint-run/references/tracking-formats.md
  # Should be >= 1
  ```

### P4-27: validate_config.py shared utilities missing from CLAUDE.md function table
- **Location**: `CLAUDE.md:37-54` vs `scripts/validate_config.py`
- **Bug**: CLAUDE.md's function table for validate_config.py omits 5 shared utilities used across multiple scripts: `detect_sprint()`, `extract_story_id()`, `kanban_from_labels()`, `find_milestone()`, `warn_if_at_limit()`.
- **Acceptance criteria**: All shared utility functions listed in the CLAUDE.md table.
- **Validation**:
  ```bash
  for fn in detect_sprint extract_story_id kanban_from_labels find_milestone warn_if_at_limit; do
    if ! grep -q "$fn" CLAUDE.md; then
      echo "MISSING from CLAUDE.md: $fn"
    fi
  done
  ```

---

## Priority 5: Test Coverage Gaps (existing tests pass, but missing negative paths)

### Missing negative tests (not individually tracked — batch fix)

| Script | Missing Test | Severity |
|--------|-------------|----------|
| `sprint_analytics.py` | Malformed SP label (e.g., `sp:abc`, `sp:`) | MODERATE |
| `setup_ci.py` | Unsupported language (e.g., "Haskell") | MODERATE |
| `sync_backlog.py` | `do_sync` when subprocess calls raise exceptions | MODERATE |
| `manage_epics.py` | `remove_story` with non-existent story ID | MODERATE |
| `manage_epics.py` | `add_story` with duplicate ID | MODERATE |
| `manage_epics.py` | `parse_epic` on empty file | MODERATE |
| `manage_sagas.py` | `parse_saga` on malformed file | MODERATE |
| `populate_issues.py` | `parse_milestone_stories` with malformed markdown tables | MODERATE |
| `test_release_gate.py` | `do_release` when `gh release create` fails | MODERATE |

---

## Pattern Analysis

| Pattern | Items | Root Cause |
|---------|-------|------------|
| PAT-A: Silent error returns defeat caller assumptions | P4-02, P4-07, P4-22 | Defensive `except: return default` without logging |
| PAT-B: Phantom documentation (claims unimplemented features) | P4-17, P4-31 | Aspirational docs not synced with implementation |
| PAT-C: Line references drift after code changes | P4-33, P4-34 | No automated sync between code and doc line numbers |
| PAT-D: Duplicated implementations diverge over time | P4-16, P4-21 | Copy-paste without extraction to shared module |
| PAT-E: Test doubles too permissive (accept anything) | P4-18, P4-19, P4-28 | FakeGitHub doesn't enforce real API constraints |
| PAT-F: Unvalidated user input passed to parsers/regex | P4-11, P4-13, P4-14 | Config values interpolated without escaping/validation |
| PAT-G: Unbounded parsers scan past intended boundaries | P4-03, P4-37 | Loop continues matching until wrong delimiter instead of stopping at blank line |
| PAT-H: Case sensitivity mismatches | P4-01 | Dict keys lowercase, config values capitalized |

---

## Audit Metrics

| Category | Count |
|----------|-------|
| Critical (broken feature) | 1 (P4-01) |
| Code bugs (HIGH) | 2 (P4-02, P4-03, P4-04) |
| Code bugs (MEDIUM) | 12 (P4-05 through P4-16, P4-38) |
| Design hardening | 7 (P4-17 through P4-21, P4-22, P4-23) |
| Dead code / cleanup | 5 (P4-24 through P4-28) |
| Documentation drift | 6 (P4-31 through P4-36) |
| Test gaps (batch) | 9 individual gaps |
| Duplication (informational) | 4 (P4-29, P4-30, P4-35, P4-37) |
| **Total tracked items** | **38** |

### By Severity
| Severity | Count | Items |
|----------|-------|-------|
| CRITICAL | 1 | P4-01 |
| HIGH | 3 | P4-02, P4-03, P4-04, P4-33 |
| MEDIUM | 18 | P4-05 through P4-21, P4-34, P4-38 |
| LOW | 16 | P4-22 through P4-32, P4-35 through P4-37 |
