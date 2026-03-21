# Bug Hunter Punchlist — Pass 24 (Adversarial Legacy Audit)

> Generated: 2026-03-19 | Project: giles | Baseline: 889 pass, 0 fail, 0 skip, 85% coverage
> Method: Fresh adversarial audit — manual code review of all 20 scripts + 9 parallel agents
> Recon: `recon/0a-0g`, Audit: `audit/1-doc-claims.md`, `audit/2a-2c`, `audit/3a`

## Summary

| Severity | Open | Resolved | Deferred |
|----------|------|----------|----------|
| CRITICAL | 0    | 0        | 0        |
| HIGH     | 9    | 0        | 0        |
| MEDIUM   | 18   | 0        | 0        |
| LOW      | 19   | 0        | 0        |

---

## Tier 1 — Fix Now (HIGH)

### Concurrency & State Safety

| ID | Title | Category | Acceptance Criteria | Validation |
|----|-------|----------|---------------------|------------|
| BH24-001 | TOCTOU race: kanban.py reads TF before acquiring lock | bug/race | `find_story()` must be called INSIDE the `lock_story` context, not before it. kanban.py:604 reads, :612 locks — must be reversed. | Refactor main() so lock_story wraps find_story+operation. Test: thread A reads TF, thread B modifies TF, thread A writes stale — must be impossible after fix. |
| BH24-002 | sync_tracking.py writes TF without file locking | bug/race | sync_tracking.py must import and use lock_story before every `write_tf()` call (lines 271, 277) | `grep -n 'write_tf' skills/sprint-run/scripts/sync_tracking.py` — every hit must be inside a `with lock_story(...)` block. Integration test: concurrent kanban+sync writes produce correct state. |

### Doc-to-Implementation Gaps (Agent-Facing)

| ID | Title | Category | Acceptance Criteria | Validation |
|----|-------|----------|---------------------|------------|
| BH24-003 | story-execution.md calls update_burndown.py without required sprint arg | doc/broken | Command must include `<sprint-number>` argument | `grep 'update_burndown' skills/sprint-run/references/story-execution.md` shows `update_burndown.py {sprint_number}` |
| BH24-004 | context-recovery.md calls sync_tracking.py without required sprint arg | doc/broken | Command must include `<sprint-number>` argument | `grep 'sync_tracking' skills/sprint-run/references/context-recovery.md` shows sprint arg |
| BH24-005 | context-recovery.md uses wrong label format `sprint-{N}` instead of `sprint:{N}` | doc/broken | Label must use colon separator matching bootstrap_github.py | `grep 'sprint-' skills/sprint-run/references/context-recovery.md` returns 0 matches (all converted to `sprint:`) |

### Test Theater (Look Good, Prove Nothing)

| ID | Title | Category | Acceptance Criteria | Validation |
|----|-------|----------|---------------------|------------|
| BH24-006 | test_release_notes_contain_correct_sections asserts tag_name not notes content | test/rubber-stamp | Test must read release notes file and verify section headers (## Features, ## Fixes, etc.) | Test assertion references `notes` content, not just `tag_name` |
| BH24-007 | CI generation tests check keyword presence, not YAML validity | test/green-bar | At least one CI test must parse output YAML and validate structure (valid YAML, has `jobs:`, `runs-on:`) | `import yaml; yaml.safe_load(output)` in test doesn't raise |
| BH24-008 | TestSyncOneGitHubAuthoritative spy is tautologically true | test/vacuous | The test claims sync_one doesn't call GitHub, but the spy can never fire because sync_one never calls subprocess. Must patch `sync_tracking.gh` or `sync_tracking.gh_json` instead. | Replace subprocess spy with mock of `sync_tracking.gh_json`; assert `mock.assert_not_called()` |
| BH24-009 | Property test _yaml_safe predicate is stale — missing 4 production conditions | test/stale-mirror | The `_should_be_quoted` predicate in test_property_parsing.py:224-242 is missing comma, newline, CR, and whitespace conditions added in BH21-005/BH22-108/BH23-200/BH23-205. Hypothesis can't catch regressions in these conditions. | Predicate in test must match production `_yaml_safe` exactly. Test: remove comma quoting from prod → property test fails. |

---

## Tier 2 — Fix Soon (MEDIUM)

### Roundtrip Fragility

| ID | Title | Category | Acceptance Criteria | Validation |
|----|-------|----------|---------------------|------------|
| BH24-010 | _yaml_safe and frontmatter_value escape sets don't match | bug/roundtrip | Define escape/unescape in ONE shared dict. Both functions derive from it. | `_YAML_ESCAPES` dict exists in validate_config.py; `_yaml_safe` and `frontmatter_value` both reference it |
| BH24-011 | frontmatter_value _UNESCAPE missing `\t` and `\b` | bug/roundtrip | Add 't': '\t', 'b': '\b' to _UNESCAPE to match _unescape_toml_string | Test: `frontmatter_value('title: "has\\ttab"', 'title')` returns string with real tab |
| BH24-012 | kanban.py test round-trip only verifies 4 of 10 TF fields | test/shallow | Round-trip test must assert ALL TF fields: story, title, sprint, implementer, reviewer, status, branch, pr_number, issue_number, started, completed | Count of assertions ≥ 10 in test_round_trip |

### Coverage Gaps (6 modules under 80%)

| ID | Title | Category | Acceptance Criteria | Validation |
|----|-------|----------|---------------------|------------|
| BH24-013 | test_coverage.py at 68% — ironic | test/missing | Tests for scan_project_tests(), detect_test_functions() | `pytest --cov=scripts/test_coverage -q` ≥ 85% |
| BH24-014 | update_burndown.py at 74% | test/missing | Tests for empty milestone, all-closed, mixed SP | `pytest --cov=skills/sprint-run/scripts/update_burndown -q` ≥ 85% |
| BH24-015 | bootstrap_github.py at 71% | test/missing | Tests for prereq failures, milestone errors | `pytest --cov=skills/sprint-setup/scripts/bootstrap_github -q` ≥ 80% |
| BH24-016 | populate_issues.py at 77% | test/missing | Tests for enrich_from_epics conflicts, create_issue failure | `pytest --cov=skills/sprint-setup/scripts/populate_issues -q` ≥ 85% |
| BH24-017 | manage_sagas.py at 78% | test/missing | Tests for update_sprint_allocation, update_voices | `pytest --cov=scripts/manage_sagas -q` ≥ 85% |
| BH24-018 | sprint_teardown.py at 76% | test/missing | Tests for symlink/file classification, error during removal | `pytest --cov=scripts/sprint_teardown -q` ≥ 85% |

### Logic & Error Handling

| ID | Title | Category | Acceptance Criteria | Validation |
|----|-------|----------|---------------------|------------|
| BH24-019 | check_status.py catches bare Exception masking programming errors | bug/error-handling | Replace `except Exception` at L405 and L450 with specific types | `grep -c 'except Exception' skills/sprint-monitor/scripts/check_status.py` returns 0 |
| BH24-020 | enrich_from_epics substring-matches story IDs (US-001 matches US-0012) | bug/logic | Use word-boundary regex `\bUS-001\b` instead of `sid in content` | Test: epic mentioning US-0012 doesn't false-match US-001 |
| BH24-021 | generate_release_notes never directly tested (7 formatting branches) | test/missing | Add TestGenerateReleaseNotes with cases for feats, fixes, breaking, compare link, initial release | ≥ 5 tests in a dedicated class |
| BH24-022 | MonitoredMock warnings: 6 test_kanban tests don't verify call_args | test/shallow | Assert call_args or add explicit `# call_args intentionally unchecked: <reason>` | `python -m pytest tests/test_kanban.py -W error::UserWarning` exits 0 |
| BH24-023 | determine_bump never directly tested (edge cases: empty list, breaking fix, docs-only) | test/missing | Add TestDetermineBump with ≥ 5 edge cases | Tests exist for empty commits, `fix!:`, docs-only, multiple commits with mixed types |
| BH24-024 | enrich_from_epics substring match: US-001 matches inside US-0012 | bug/logic | Use word-boundary regex `\bUS-001\b` instead of `sid in content` | Test: epic mentioning US-0012 doesn't false-match US-001's sprint |
| BH24-025 | 7 scripts have argparse-only main() tests (--help/no-args) that satisfy gate but test nothing | test/paper-tiger | update_burndown, manage_epics, manage_sagas need main() tests that exercise core logic paths | TestEveryScriptMainCovered should require non-argparse assertions |

---

## Tier 3 — Fix When Convenient (LOW)

### Doc Drift (Non-Breaking)

| ID | Title | Category | Acceptance Criteria | Validation |
|----|-------|----------|---------------------|------------|
| BH24-030 | CLAUDE.md bootstrap_github function list missing 5 functions | doc/drift | Add create_sprint_labels, create_saga_labels, create_label, _parse_saga_labels_from_backlog, check_prerequisites | `grep -c 'create_sprint_labels\|create_saga_labels' CLAUDE.md` ≥ 2 |
| BH24-031 | CLAUDE.md marks team/giles.md REQUIRED but validate_config doesn't check it | doc/drift | Either add giles.md to _REQUIRED_FILES or change CLAUDE.md to "runtime" | Consistent labeling between CLAUDE.md and _REQUIRED_FILES |
| BH24-032 | kanban-protocol.md omits --sprint flag from commands (inconsistent with implementer.md) | doc/inconsistency | All kanban.py examples should show --sprint flag or document auto-detection | Consistent --sprint usage across all reference docs |

### Edge Cases & Hardening

| ID | Title | Category | Acceptance Criteria | Validation |
|----|-------|----------|---------------------|------------|
| BH24-033 | create_from_issue doesn't validate branch name length | bug/logic | Branch names from long titles must be truncated ≤ 255 bytes | Test: 300-char title → branch ≤ 255 bytes |
| BH24-034 | _sanitize_md doesn't strip # characters (heading injection) | bug/security | Story IDs with ### are escaped | Test: `_format_story_section(id="US ### Inject")` has no extra heading |
| BH24-035 | _infer_sprint_number silently defaults to 1 | bug/default | Should warn when falling back | Test: _infer_sprint_number("backlog.md") with no sprint headers produces stderr warning |
| BH24-036 | validate_project doesn't check definition-of-done.md is non-empty | test/missing | Empty DoD should fail validation (like rules.md) | Test: empty DoD file → validation error |
| BH24-037 | setup_ci _job_name_from_command: "lint-test" matches as "Test" | bug/logic | Substring match should require word boundary | Test: `_job_name_from_command("npm run lint-test", 0)` → "Lint" |
| BH24-038 | generate_ci_yaml doesn't escape base_branch for YAML | bug/injection | Metachar branch names produce valid YAML | Test: branch "main]" doesn't break YAML syntax |
| BH24-039 | do_assign returns True when body update can't find [Unassigned] header | bug/logic | Should return False or warning flag on body-update failure | Test: do_assign on already-assigned issue → distinct return value |
| BH24-040 | compute_velocity shows 0% when all SP=0 (missing data, not zero velocity) | design/inconsistency | Should warn when planned_sp==0 | Test: all-zero-SP milestone → warning on stderr |
| BH24-041 | check_ci doesn't catch RuntimeError from gh_json (can crash monitor) | bug/error-handling | Wrap gh_json call in try/except | Test: mock gh_json raising RuntimeError → graceful report line |
| BH24-042 | test_lifecycle.py has zero error-path tests | test/missing | Add ≥ 2 error-path tests (e.g., FakeGitHub error, missing config) | Error-path test methods exist |
| BH24-043 | gate_prs 500-limit truncation safety gate is untested | test/missing | Add test returning 500 milestone-matching PRs → gate fails | Dedicated test for the truncation path at release_gate.py:186-190 |
| BH24-044 | get_linked_pr isinstance(linked, dict) normalization path never tested | test/missing | Test with timeline API returning single dict instead of list | Test exercises the `isinstance(linked, dict)` branch at sync_tracking.py:75-76 |
| BH24-045 | release notes markdown injection from commit subjects | bug/security | Commit subjects with `[link](url)` syntax should be escaped in notes | Test: commit with markdown link → notes contain escaped or literal text |
| BH24-046 | do_status empty sprint directory path untested | test/missing | Test with nonexistent stories dir → "(no stories found)" | Assertion on exact output string |
| BH24-047 | read_tf catches FileNotFoundError but not PermissionError | bug/error-handling | Add PermissionError to except clause, or document that it propagates | Test: read_tf on unreadable file → graceful fallback or documented exception |

---

## Emerging Patterns

### PAT-24-001: Locking discipline inconsistent across write paths
**Instances:** BH24-001, BH24-002
**Root Cause:** kanban.py introduced file locking but the TOCTOU gap (read before lock) and sync_tracking.py (no locks at all) mean concurrent writes can corrupt state.
**Systemic Fix:** Read-under-lock pattern: acquire lock FIRST, then read, modify, write. sync_tracking.py imports lock_story from kanban.py.
**Detection Rule:** `grep -rn 'write_tf\|atomic_write_tf' scripts/ skills/ --include='*.py'` — every hit must be traceable to a lock context.

### PAT-24-002: Coverage ≤78% in 6 modules, 80% floor not enforced
**Instances:** BH24-013 through BH24-018
**Root Cause:** Test suite grew reactively (regression tests for specific bugs) not proactively (branch coverage per module). main() and prereq paths are the common gap.
**Systemic Fix:** Add `--cov-fail-under=80` to CI. Test main() dispatch via `sys.argv` mocking.
**Detection Rule:** `pytest --cov --cov-fail-under=80` in CI gate.

### PAT-24-003: _yaml_safe / frontmatter_value are mathematical inverses that evolved separately
**Instances:** BH24-010, BH24-011, BH24-012, plus 8+ prior-pass fixes
**Root Cause:** Escape set and unescape set maintained in different locations. Patches to one don't automatically propagate to the other.
**Systemic Fix:** Single `_YAML_ESCAPES` mapping, both functions derived from it. Hypothesis roundtrip test generating ALL edge characters.
**Detection Rule:** Property test in test_property_parsing.py with `@given(st.text())` covering the full write_tf→read_tf cycle.

### PAT-24-004: Doc commands give agents broken invocations
**Instances:** BH24-003, BH24-004, BH24-005
**Root Cause:** Script CLI interfaces evolved (required args added) without updating all reference docs that invoke them.
**Systemic Fix:** Automated doc-command validation: extract command strings from reference docs, dry-run them, verify exit code 0.
**Detection Rule:** Script that parses `python ...` and `gh ...` commands from `skills/*/references/*.md` and validates argument counts.

### PAT-24-005: Tests that look like coverage but prove nothing
**Instances:** BH24-006, BH24-007, BH24-008, BH24-009, BH24-025
**Root Cause:** Tests assert structural presence (keywords, types, non-None) rather than behavioral correctness. Mock spies verify call sequences not outcomes. Property tests duplicate production predicates instead of referencing them (stale mirror). Gate tests count invocations not substance.
**Systemic Fix:** For every HIGH/MEDIUM test fix: write the failing test first, then verify the existing code passes it. If the existing code passes a tautological assertion, the assertion is wrong. Property test predicates must be derived from production code, not hand-rolled mirrors.
**Detection Rule:** Review all `assertIn(keyword, output)` patterns — replace with structural parsing where output has structure (YAML, JSON, markdown).
