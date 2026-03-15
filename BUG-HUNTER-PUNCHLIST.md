# Bug Hunter Punchlist — Pass 8

> Generated: 2026-03-15 | Project: giles | Baseline: 508 pass, 0 fail, 0 skip (2.7s)

## Summary
| Severity | Open | Resolved | Deferred |
|----------|------|----------|----------|
| CRITICAL | 0 | 2 | 0 |
| HIGH | 0 | 8 | 0 |
| MEDIUM | 0 | 8 | 0 |
| LOW | 0 | 5 | 0 |
| **Total** | **0** | **23** | **0** |

---

## Patterns

### Pattern: PAT-001: Quality Gatekeepers Have Blind Spots
**Instances:** BH-001, BH-007, BH-008, BH-009, BH-011
**Root Cause:** The project's own enforcement tooling (anchor validator, FakeGitHub mock, golden test) has gaps that silently pass invalid input. When the gatekeeper is broken, bugs accumulate undetected.
**Systemic Fix:** Each gatekeeper needs adversarial self-tests — tests that verify the gatekeeper REJECTS known-bad input, not just that it accepts known-good.
**Detection Rule:** `grep -rn "NOOP\|silently\|skip\|ignore" tests/fake_github.py scripts/validate_anchors.py`

### Pattern: PAT-002: Phantom Features in Docs
**Instances:** BH-013, BH-014, BH-015
**Root Cause:** SKILL.md and README.md describe aspirational features that were never implemented. Agents read these docs and try to use features that don't exist.
**Systemic Fix:** Automated doc-code sync check: every feature/config key mentioned in docs must map to a code reference. Sprint-monitor could run this as a drift check.
**Detection Rule:** `grep -rn "cycle.time\|sbom\|known.limitation" skills/ README.md`

### Pattern: PAT-003: Unvalidated String Construction
**Instances:** BH-005, BH-012, BH-006
**Root Cause:** Functions construct labels, YAML values, or file paths from user data without validating emptiness or special characters. The string is always built, even when the input is empty or problematic.
**Systemic Fix:** Add validation helpers that reject empty/invalid inputs at construction time rather than silently producing broken output.
**Detection Rule:** `grep -rn 'f"saga:{' scripts/ skills/`

---

## Items

### BH-001: `_REF_RE` regex misses anchor refs inside parentheses and before periods
**Severity:** CRITICAL
**Category:** `bug/logic`
**Location:** `scripts/validate_anchors.py:94`
**Status:** 🟢 RESOLVED
**Pattern:** PAT-001

**Problem:** The anchor reference regex `§([\w-]+\.[\w_]+)(?=[\s,|]|$)` requires whitespace, comma, pipe, or end-of-line after the anchor name. References inside parentheses `(see §foo.bar)` or before periods `§foo.bar.` are silently skipped. The validator reports "all resolved" while 4+ broken anchors exist undetected (BH-002).

**Evidence:**
```python
# validate_anchors.py:94
_REF_RE = re.compile(r"§([\w-]+\.[\w_]+)(?=[\s,|]|$)")
# Misses: "(see §validate_config.current)" — ')' not in lookahead
# Misses: "§implementer.conventions_checklist." — '.' not in lookahead
```

**Acceptance Criteria:**
- [ ] `_REF_RE` matches refs followed by `)`, `.`, `;`, `:`, and other punctuation
- [ ] `find_anchor_refs()` returns all 4 currently-missed refs from CLAUDE.md/CHEATSHEET.md
- [ ] New test: ref followed by `)` is found
- [ ] New test: ref followed by `.` is found
- [ ] New test: ref at end of line still works
- [ ] `python scripts/validate_anchors.py check` reports the broken anchors (will fail until BH-002 is fixed)

**Validation Command:**
```bash
python -c "
import re
pattern = re.compile(r'§([\w-]+\.[\w_]+)(?=[\s,.|;:)\]!?\x27\"]|$)')
assert pattern.search('(see §foo.bar)'), 'paren ref not found'
assert pattern.search('§foo.bar.'), 'period ref not found'
assert pattern.search('§foo.bar'), 'EOL ref not found'
print('PASS')
"
python -m unittest discover tests/ -v -k "anchor" 2>&1 | tail -3
```

---

### BH-002: Four broken § anchor references in CLAUDE.md and CHEATSHEET.md
**Severity:** HIGH
**Category:** `doc/drift`
**Location:** `CLAUDE.md:107`, `CHEATSHEET.md:437,446,447`
**Status:** 🟢 RESOLVED
**Pattern:** PAT-001

**Problem:** Four anchor references point to definitions that don't exist:
1. `§validate_config.current` in CLAUDE.md — no such anchor in validate_config.py
2. `§implementer.conventions_checklist` in CHEATSHEET.md — no anchor comment in implementer.md
3. `§reviewer.pass_3_testing` in CHEATSHEET.md — no anchor comment in reviewer.md
4. `§reviewer.commit_format` in CHEATSHEET.md — no anchor comment in reviewer.md

**Evidence:**
```
grep -rn "§validate_config.current" scripts/validate_config.py  → 0 matches
grep -rn "§implementer.conventions_checklist" skills/sprint-run/agents/implementer.md  → 0 matches
```

**Acceptance Criteria:**
- [ ] Either add missing anchor definitions in target files OR update refs to point to correct existing anchors
- [ ] `python scripts/validate_anchors.py check` exits 0 (requires BH-001 fix first)

**Validation Command:**
```bash
python scripts/validate_anchors.py check
```

---

### BH-003: `gh()` doesn't catch `subprocess.TimeoutExpired`
**Severity:** CRITICAL
**Category:** `bug/error-handling`
**Location:** `scripts/validate_config.py:33-37`
**Status:** 🟢 RESOLVED

**Problem:** `subprocess.run(..., timeout=30)` raises `subprocess.TimeoutExpired` on timeout, which is NOT a subclass of `RuntimeError`. Every caller that catches `RuntimeError` will miss timeouts, causing an unhelpful crash with a raw subprocess traceback. This affects every script that uses `gh()` or `gh_json()`.

**Evidence:**
```python
# validate_config.py:33-37
r = subprocess.run(
    ["gh", *args], capture_output=True, text=True, timeout=30,
)
if r.returncode != 0:
    raise RuntimeError(f"gh {' '.join(args)}: {r.stderr.strip()}")
# subprocess.TimeoutExpired is NOT caught here — propagates raw
```

**Acceptance Criteria:**
- [ ] `gh()` catches `subprocess.TimeoutExpired` and wraps it in `RuntimeError` with a clear message including the command and timeout value
- [ ] Test: mock `subprocess.run` to raise `TimeoutExpired` → verify `RuntimeError` is raised
- [ ] Existing `gh()` tests still pass

**Validation Command:**
```bash
python -c "
import subprocess, unittest.mock as m
with m.patch('subprocess.run', side_effect=subprocess.TimeoutExpired(['gh'], 30)):
    import scripts.validate_config as vc
    try:
        vc.gh(['api', 'test'])
        print('FAIL: no exception raised')
    except RuntimeError as e:
        assert 'timeout' in str(e).lower(), f'Missing timeout in message: {e}'
        print('PASS')
    except subprocess.TimeoutExpired:
        print('FAIL: TimeoutExpired not wrapped')
"
python -m unittest discover tests/ 2>&1 | tail -1
```

---

### BH-004: `create_issue` creates empty labels (`saga:`, `priority:`)
**Severity:** HIGH
**Category:** `bug/logic`
**Location:** `skills/sprint-setup/scripts/populate_issues.py:366-367`
**Status:** 🟢 RESOLVED
**Pattern:** PAT-003

**Problem:** When `story.saga` or `story.priority` is empty, the label list produces `saga:` and `priority:` — empty labels that are meaningless on GitHub. GitHub creates these on-the-fly, polluting the label namespace.

**Evidence:**
```python
# populate_issues.py:366-367
labels = [f"saga:{story.saga}", f"sprint:{story.sprint}",
          f"priority:{story.priority}", "type:story", "kanban:todo"]
# If story.saga == "" → label is "saga:" (empty value)
```

**Acceptance Criteria:**
- [ ] Labels with empty values (e.g., `saga:`, `priority:`) are excluded from the label list
- [ ] Test: story with `saga=""` produces labels list without `saga:` entry
- [ ] Test: story with all fields populated produces full label list (regression check)

**Validation Command:**
```bash
python -m unittest discover tests/ -v -k "create_issue or format_issue" 2>&1 | tail -5
python -m unittest discover tests/ 2>&1 | tail -1
```

---

### BH-005: `manage_epics.remove_story` leaves residual line for non-last sections
**Severity:** HIGH
**Category:** `bug/logic`
**Location:** `scripts/manage_epics.py:106,164,252,265`
**Status:** 🟢 RESOLVED

**Problem:** `end_line` has inconsistent semantics: for non-last sections it's `i-1` (inclusive, pointing to the last content line), for the last section it's `len(lines)` (exclusive, past-the-end). `remove_story` uses `lines[end:]` which for non-last sections includes the line at `end_line` (the last line of the removed section) in the output.

**Evidence:**
```python
# Line 106: Non-last section: end_line = i - 1 (inclusive)
raw_sections[-1]["end_line"] = i - 1
# Line 164: Last section: end_line = len(lines) (exclusive)
raw_sections[-1]["end_line"] = len(lines)
# Line 265: remove uses lines[end:] — for non-last, end = i-1, keeps line i-1
new_lines = lines[:sep_start] + lines[end:]
```

**Acceptance Criteria:**
- [ ] `end_line` is consistently exclusive (past-the-end) for all sections, OR `remove_story` uses `lines[end+1:]` for non-last sections
- [ ] Test: remove a non-last story section → verify no residual content from removed section remains
- [ ] Test: remove the last story section → verify file is clean
- [ ] Existing manage_epics tests pass

**Validation Command:**
```bash
python -m unittest discover tests/ -v -k "manage_epic" 2>&1 | tail -5
python -m unittest discover tests/ 2>&1 | tail -1
```

---

### BH-006: `_fm_val` doesn't strip surrounding quotes from YAML values
**Severity:** HIGH
**Category:** `bug/logic`
**Location:** `skills/sprint-run/scripts/update_burndown.py:148-150`
**Status:** 🟢 RESOLVED
**Pattern:** PAT-003

**Problem:** When `_yaml_safe()` quotes a value (e.g., `implementer: "Kai: Backend"`), `_fm_val()` returns `'"Kai: Backend"'` with quotes included. This produces burndown tables with spurious `"` characters. The `read_tf.v()` function in sync_tracking.py correctly strips quotes, but `_fm_val` doesn't.

**Evidence:**
```python
# update_burndown.py:148-150
def _fm_val(frontmatter: str, key: str) -> str | None:
    m = re.search(rf"^{key}:\s*(.+)", frontmatter, re.MULTILINE)
    return m.group(1).strip() if m else None
# Returns '"Kai: Backend"' instead of 'Kai: Backend'

# sync_tracking.py v() strips quotes:
#   val = val.strip('"').strip("'")
```

**Acceptance Criteria:**
- [ ] `_fm_val` strips surrounding `"` and `'` from returned values
- [ ] Test: frontmatter with `implementer: "Kai: Backend"` → returns `Kai: Backend`
- [ ] Test: frontmatter with unquoted `implementer: Kai` → returns `Kai` (no regression)

**Validation Command:**
```bash
python -m unittest discover tests/ -v -k "burndown" 2>&1 | tail -5
python -m unittest discover tests/ 2>&1 | tail -1
```

---

### BH-007: FakeGitHub silently ignores `--jq` expressions
**Severity:** HIGH
**Category:** `test/mock-abuse`
**Location:** `tests/fake_github.py:93,111,113`
**Status:** 🟢 RESOLVED
**Pattern:** PAT-001

**Problem:** FakeGitHub accepts `--jq` as a known flag but does not apply the jq expression. Tests pre-shape data to match what jq *would* produce. If a production `--jq` expression has a syntax error or selects wrong fields, tests still pass. The validator-for-tests can't validate the thing it's supposed to validate.

**Evidence:**
```python
# fake_github.py:93 — comment acknowledges the gap
# --jq: FakeGitHub returns full JSON; callers must handle both formats.

# fake_github.py:111,113 — jq accepted but no-op
"release_view": frozenset(("json", "jq")),
"api": frozenset(("paginate", "f", "X", "jq")),
```

**Acceptance Criteria:**
- [ ] At minimum: FakeGitHub validates jq expression syntax (import `subprocess` to run `echo '{}' | jq '<expr>'` or use a regex for basic syntax)
- [ ] OR: add targeted unit tests for each production `--jq` expression against known input shapes
- [ ] Inventory: list all production `--jq` usages (grep `--jq` in scripts/) and verify each has a direct test

**Validation Command:**
```bash
grep -rn '"--jq"' scripts/ skills/*/scripts/ | grep -v __pycache__ | wc -l
# Each usage should have a corresponding test that validates the jq expression
python -m unittest discover tests/ 2>&1 | tail -1
```

---

### BH-008: FakeGitHub `_parse_flags` misparses values starting with dashes
**Severity:** HIGH
**Category:** `test/mock-abuse`
**Location:** `tests/fake_github.py:_parse_flags`
**Status:** 🟢 RESOLVED
**Pattern:** PAT-001

**Problem:** The flag parser treats any argument starting with `-` as a flag, not a value. `--title "-1 Fix"` would parse `-1` as a short flag rather than the value for `--title`. The real `gh` CLI handles this correctly because it knows which flags take values.

**Evidence:**
```python
# fake_github.py _parse_flags:
# if i + 1 < len(args) and not args[i + 1].startswith("-"):
#     parsed[flag_name] = args[i + 1]
# A value like "-1 Fix" would be treated as flag "-1", not as --title's value
```

**Acceptance Criteria:**
- [ ] `_parse_flags` recognizes that known value-bearing flags (--title, --body, --milestone, --jq) always consume the next argument regardless of prefix
- [ ] Test: `_parse_flags(["--title", "-1 Fix bug"])` → `{"title": "-1 Fix bug"}`
- [ ] Existing tests still pass

**Validation Command:**
```bash
python -m unittest discover tests/ -v -k "parse_flag" 2>&1 | tail -5
python -m unittest discover tests/ 2>&1 | tail -1
```

---

### BH-009: FakeGitHub `_issue_create` doesn't validate milestone existence
**Severity:** HIGH
**Category:** `test/mock-abuse`
**Location:** `tests/fake_github.py:_issue_create`
**Status:** 🟢 RESOLVED
**Pattern:** PAT-001

**Problem:** When `--milestone "Sprint 1"` is passed to issue creation, FakeGitHub stores it without checking that a milestone with that title exists. The real GitHub API returns an error for non-existent milestones. Production code that references a typo'd milestone name would silently succeed in tests.

**Evidence:**
```python
# FakeGitHub stores milestone as {"title": milestone_name} without validation
# Real GitHub API returns 422 for non-existent milestones
```

**Acceptance Criteria:**
- [ ] FakeGitHub `_issue_create` validates that the milestone exists in `self.milestones` before accepting
- [ ] On missing milestone: raise or return error matching GitHub's behavior
- [ ] Test: creating issue with non-existent milestone → error

**Validation Command:**
```bash
python -m unittest discover tests/ 2>&1 | tail -1
```

---

### BH-010: `sync_backlog` derives config_dir from backlog_dir parent
**Severity:** HIGH
**Category:** `bug/logic`
**Location:** `scripts/sync_backlog.py:212`
**Status:** 🟢 RESOLVED

**Problem:** `config_dir = Path(backlog_dir).parent` assumes backlog_dir is always directly inside sprint-config/. If `backlog_dir` is configured to a non-standard path (e.g., `docs/backlog`), the sync state file goes to `docs/.sync-state.json` instead of `sprint-config/.sync-state.json`, and state is lost across config changes.

**Evidence:**
```python
# sync_backlog.py:212
config_dir = Path(backlog_dir).parent  # assumes backlog is inside sprint-config/
# If backlog_dir = "docs/planning/backlog" → config_dir = "docs/planning" (wrong)
```

**Acceptance Criteria:**
- [ ] config_dir is determined from the known sprint-config directory (e.g., from `load_config()`'s config path parameter), not derived from backlog_dir
- [ ] Test: non-standard backlog_dir → state file still goes to sprint-config/
- [ ] Existing sync_backlog tests pass

**Validation Command:**
```bash
python -m unittest discover tests/ -v -k "sync_backlog" 2>&1 | tail -5
python -m unittest discover tests/ 2>&1 | tail -1
```

---

### BH-011: Golden test silently skips in fresh checkout
**Severity:** MEDIUM
**Category:** `test/bogus`
**Location:** `tests/test_golden_run.py`
**Status:** 🟢 RESOLVED
**Pattern:** PAT-001

**Problem:** When golden recordings don't exist (no `manifest.json`), the test calls `self.skipTest()`. In a fresh checkout, or if recordings are gitignored, the entire golden regression test does nothing. The suite reports "508 pass" but one of those is a silent skip.

**Evidence:**
```python
# test_golden_run.py: checks for manifest, skips if not found
# `skipTest` makes unittest count it as "skipped" but the default runner shows "OK"
```

**Acceptance Criteria:**
- [ ] Golden test prints a visible warning (not just skipTest) when recordings are absent
- [ ] OR: golden recordings are committed to the repo so the test always runs
- [ ] Document in CLAUDE.md how to generate golden recordings (`GOLDEN_RECORD=1`)

**Validation Command:**
```bash
python -m unittest tests.test_golden_run -v 2>&1
```

---

### BH-012: `write_tf` doesn't pass `story` field through `_yaml_safe`
**Severity:** MEDIUM
**Category:** `bug/logic`
**Location:** `skills/sprint-run/scripts/sync_tracking.py:187`
**Status:** 🟢 RESOLVED
**Pattern:** PAT-003

**Problem:** `write_tf` applies `_yaml_safe()` to `title` and `branch` but writes `story: {tf.story}` raw. If a story ID contains YAML-sensitive characters (e.g., `PROJ:ITEM-001` with a colon), the tracking file frontmatter would be malformed.

**Evidence:**
```python
# sync_tracking.py:184-189
lines = [
    "---",
    f"story: {tf.story}",        # NO _yaml_safe
    f"title: {_yaml_safe(tf.title)}",  # quoted
    f"sprint: {tf.sprint}",
    f"branch: {_yaml_safe(tf.branch)}", # quoted
```

**Acceptance Criteria:**
- [ ] `story` field is passed through `_yaml_safe()` in `write_tf`
- [ ] Test: story ID containing `:` is correctly quoted
- [ ] Existing sync_tracking tests pass

**Validation Command:**
```bash
python -m unittest discover tests/ -v -k "sync_tracking or sync_one" 2>&1 | tail -5
python -m unittest discover tests/ 2>&1 | tail -1
```

---

### BH-013: README + ceremony-retro claim "cycle times" — not implemented
**Severity:** MEDIUM
**Category:** `doc/drift`
**Location:** `README.md:224,237`, `skills/sprint-run/references/ceremony-retro.md:113,120`
**Status:** 🟢 RESOLVED
**Pattern:** PAT-002

**Problem:** ceremony-retro.md instructs Giles to report cycle times and includes a format template `**Cycle time:** avg {X} hours from design to done`. But `sprint_analytics.py` has only velocity, review rounds, and workload. No cycle time computation exists. README also references cycle times as a feature.

**Evidence:**
```bash
grep -n "cycle.time" skills/sprint-run/references/ceremony-retro.md
# Line 113: "review round counts, velocity, and cycle times"
# Line 120: "**Cycle time:** avg {X} hours from design to done"
grep -c "cycle" scripts/sprint_analytics.py
# 0 matches
```

**Acceptance Criteria:**
- [ ] Either implement `compute_cycle_time()` in sprint_analytics.py OR remove cycle time references from ceremony-retro.md and README.md
- [ ] If removing: no remaining `cycle.time` references in docs

**Validation Command:**
```bash
grep -rni "cycle.time" skills/ README.md | grep -v "audit\|bug-hunter\|prior" | wc -l
# Should be 0 (if removing) or >0 with matching implementation
```

---

### BH-014: README claims SBOM generation — not implemented
**Severity:** MEDIUM
**Category:** `doc/drift`
**Location:** `README.md:289`
**Status:** 🟢 RESOLVED
**Pattern:** PAT-002

**Problem:** README lists "SBOM generation — if your toolchain supports it" as a release feature. No SBOM code exists anywhere in the codebase.

**Evidence:**
```bash
grep -rn "sbom" scripts/ skills/*/scripts/ README.md
# Only match: README.md:289
```

**Acceptance Criteria:**
- [ ] Remove SBOM claim from README.md

**Validation Command:**
```bash
grep -ci "sbom" README.md  # should be 0
```

---

### BH-015: sprint-release SKILL.md describes "Known Limitations" release notes section — not generated
**Severity:** MEDIUM
**Category:** `doc/drift`
**Location:** `skills/sprint-release/SKILL.md:157`
**Status:** 🟢 RESOLVED
**Pattern:** PAT-002

**Problem:** SKILL.md lists "Known Limitations" as one of the sections in assembled release notes. `generate_release_notes()` produces: Highlights, Features, Fixes, Breaking Changes, Full Changelog — no "Known Limitations."

**Evidence:**
```python
# release_gate.py generate_release_notes() — sections produced:
# "## Highlights", "## Features", "## Fixes", "## Breaking Changes", "## Full Changelog"
# No "Known Limitations" section
```

**Acceptance Criteria:**
- [ ] Remove "Known Limitations" from SKILL.md OR implement it in generate_release_notes()

**Validation Command:**
```bash
grep -ci "known.limitation" skills/sprint-release/SKILL.md  # should be 0 if removing
```

---

### BH-016: CLAUDE.md missing `get_ci_commands()` in scripts table
**Severity:** MEDIUM
**Category:** `doc/missing`
**Location:** `CLAUDE.md:39`
**Status:** 🟢 RESOLVED

**Problem:** `get_ci_commands()` exists in validate_config.py with anchor `§validate_config.get_ci_commands` and is documented in CHEATSHEET.md, but is absent from CLAUDE.md's scripts table.

**Acceptance Criteria:**
- [ ] `get_ci_commands()` listed in CLAUDE.md validate_config.py row with § anchor
- [ ] `python scripts/validate_anchors.py check` passes

**Validation Command:**
```bash
grep -c "get_ci_commands" CLAUDE.md  # should be >= 1
python scripts/validate_anchors.py check
```

---

### BH-017: `prerequisites-checklist.md` undocumented in reference tables
**Severity:** MEDIUM
**Category:** `doc/missing`
**Location:** `CLAUDE.md:78-90`, `CHEATSHEET.md`
**Status:** 🟢 RESOLVED

**Problem:** `skills/sprint-setup/references/prerequisites-checklist.md` (104 lines — covers gh CLI, auth, superpowers plugin, git remote, toolchain, Python version checks) exists but is not listed in CLAUDE.md's Reference Files table or CHEATSHEET.md.

**Acceptance Criteria:**
- [ ] Listed in CLAUDE.md Reference Files table under sprint-setup
- [ ] Listed in CHEATSHEET.md reference file index

**Validation Command:**
```bash
grep -c "prerequisites-checklist" CLAUDE.md  # should be >= 1
grep -c "prerequisites-checklist" CHEATSHEET.md  # should be >= 1
```

---

### BH-018: sprint-monitor SKILL.md understates check_status.py scope
**Severity:** MEDIUM
**Category:** `doc/drift`
**Location:** `skills/sprint-monitor/SKILL.md:234-247`
**Status:** 🟢 RESOLVED

**Problem:** SKILL.md Step 3 describes check_status.py as only doing milestone + CI checks. The script actually runs: backlog sync, CI check, branch divergence, PR check, direct push detection, and milestone check. The SKILL.md also presents steps 0-2.5 as separate agent-driven actions, but check_status.py bundles them all. An agent could double-run checks.

**Acceptance Criteria:**
- [ ] SKILL.md Step 3 description matches check_status.py's actual scope (all 6 checks)
- [ ] Clarify that running check_status.py covers steps 0-3, so the agent should NOT also run individual gh commands

**Validation Command:**
```bash
# Manual review — verify SKILL.md Step 3 mentions all: sync_backlog, check_ci,
# check_branch_divergence, check_prs, check_direct_pushes, check_milestone
```

---

### BH-019: `test_config_has_two_milestones` name says two, asserts three
**Severity:** LOW
**Category:** `test/bogus`
**Location:** `tests/test_hexwise_setup.py`
**Status:** 🟢 RESOLVED

**Problem:** Test method is named `test_config_has_two_milestones` but asserts `assertEqual(len(md_files), 3)`. The name was presumably written when hexwise had 2 milestone files and never updated.

**Acceptance Criteria:**
- [ ] Rename to `test_config_has_three_milestones` or similar

**Validation Command:**
```bash
python -m unittest discover tests/ -v -k "milestone" 2>&1 | grep -c "two_milestones"  # should be 0
python -m unittest discover tests/ 2>&1 | tail -1
```

---

### BH-020: `test_hashes_single_file` checks hash length, not hash value
**Severity:** LOW
**Category:** `test/shallow`
**Location:** `tests/test_sync_backlog.py`
**Status:** 🟢 RESOLVED

**Problem:** The test asserts `len(result["milestone-1.md"]) == 64` (SHA-256 hex length) but never verifies the hash matches the expected SHA-256 of the input. The test would pass if the function returned any 64-character string.

**Acceptance Criteria:**
- [ ] Assert the actual hash value matches `hashlib.sha256(b"# Sprint 1\nstories here").hexdigest()` (or whatever the fixture content is)

**Validation Command:**
```bash
python -m unittest discover tests/ -v -k "hashes_single" 2>&1 | tail -3
```

---

### BH-021: `do_release` happy path test doesn't verify tag or notes content
**Severity:** LOW
**Category:** `test/shallow`
**Location:** `tests/test_release_gate.py:TestDoRelease.test_happy_path`
**Status:** 🟢 RESOLVED

**Problem:** The test verifies mock call counts and that the first call was `release create`, but never checks the actual tag value (`v1.1.0`), release notes content, or `--notes-file` argument contents.

**Acceptance Criteria:**
- [ ] Assert the release tag matches expected version
- [ ] Assert release notes contain at least one feature/fix entry from the commit list

**Validation Command:**
```bash
python -m unittest discover tests/ -v -k "happy_path" 2>&1 | tail -3
python -m unittest discover tests/ 2>&1 | tail -1
```

---

### BH-022: `_parse_workflow_runs` multiline detection can consume adjacent YAML steps
**Severity:** LOW
**Category:** `bug/logic`
**Location:** `scripts/sprint_init.py:221-228`
**Status:** 🟢 RESOLVED

**Problem:** The multiline block detection consumes blank lines and any line starting with 2+ spaces. A blank line between YAML steps followed by the next step's `- run:` (which starts with spaces) would be consumed as part of the previous multiline block, pulling in unrelated content.

**Evidence:**
```yaml
      - run: |
          echo "hello"
                            # blank line consumed
      - run: echo "world"   # starts with "  " → also consumed
```

**Acceptance Criteria:**
- [ ] Multiline block detection stops at lines that match a new step pattern (e.g., `^\s*- `)
- [ ] Test: two adjacent `run:` blocks → correctly detected as separate commands

**Validation Command:**
```bash
python -m unittest discover tests/ -v -k "workflow_run" 2>&1 | tail -5
python -m unittest discover tests/ 2>&1 | tail -1
```

---

### BH-023: Dead variable `header` in sprint_analytics.py
**Severity:** LOW
**Category:** `design/dead-code`
**Location:** `scripts/sprint_analytics.py:265`
**Status:** 🟢 RESOLVED

**Problem:** `header = f"### Sprint {sprint_num}"` is assigned but never used. The dedup check uses the regex directly.

**Acceptance Criteria:**
- [ ] Remove the dead variable

**Validation Command:**
```bash
python -m unittest discover tests/ -v -k "analytics" 2>&1 | tail -3
python -m unittest discover tests/ 2>&1 | tail -1
```
