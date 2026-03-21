# Pass 29 — Cross-Component Gap Synthesis

> Date: 2026-03-21 | Sources: Passes 25-28, 6 recon audits, 4 verification agents

---

## The Shape of What Remains

After 28 passes and 25+ items fixed, the remaining open findings fall into three
distinct patterns. Each pattern has a structural root cause that explains why the
bugs weren't caught sooner and why they persist.

### Pattern A: Test ↔ Code Agreement on Wrong Answers

**Instances:**
- test-audit FINDING-5: `_read_toml_key` escaped-quote test asserts the bug
- test-audit FINDING-7: `test_status_wip_limit_warning` promises a WIP warning feature that doesn't exist
- test-audit FINDING-8: `test_update_no_changes` claims no write verification without verifying

**Root cause:** Tests were written to describe *what the code does* rather than
*what the code should do*. When the test and the code agree on wrong behavior,
the green suite becomes a shield against fixes — a developer who corrects the
parser sees a "regression" and reverts. This is the most insidious category
because it actively blocks future correctness work.

**Cross-component nature:** The test files (`tests/`) and the production code
(`hooks/`, `scripts/`) form a closed loop of mutual validation. Neither can
catch errors in the other because they encode the same assumptions.

### Pattern B: Uncontrolled Boundaries (no validation at edges)

**Instances:**
- gap_scanner substring matching: `"main"` matches `"domain"`, `"maintenance"`
- gap_scanner silent failure: deleted branches produce no warning, just false negatives
- renumber_stories code block unawareness: regex replaces inside ```` ``` ```` fences

**Root cause:** Functions that process text from external sources (git diff output,
markdown bodies, TOML config) don't validate input boundaries. The `in` operator
is used where line-by-line or word-boundary matching is needed. Exception handlers
swallow rather than report. These are all boundary validation failures — the code
trusts its inputs more than it should.

**Cross-component nature:** gap_scanner feeds into sprint monitoring and
traceability. When it produces false negatives (says no entry point was touched),
downstream reports are silently wrong. The error propagates across component
boundaries without detection.

### Pattern C: Incomplete Propagation of Good Patterns

**Instances:**
- `_yaml_safe` handles `\n`, `\r`, `\\` but not `\t`
- `session_context._read_toml_string` handles single quotes but not `\"` escapes
- 4 scripts still use bare `write_text()` (only risk_register was converted to atomic)
- manage_epics/sagas have no locking (kanban's locking pattern never propagated)

**Root cause:** When a fix is applied to one instance of a pattern, the fix is
correct locally but the same pattern exists in other files. Each pass catches and
fixes one instance, but the class remains. This is the "fix gradient" — correctness
radiates outward from the most-fixed module (kanban) but attenuates with distance.

**Cross-component nature:** The kanban module's locking and atomicity discipline
was never designed as a shared library. Each surrounding script independently
chooses whether to adopt it. The result is a codebase where data safety depends
on which code path reaches a shared file first.

---

## Verified Status of All Prior Open Findings

| Category | Total Open | Now Fixed | Still Open | By Design |
|----------|-----------|-----------|------------|-----------|
| Hooks ↔ Config | 5 verified | 4 FIXED | 1 LOW | — |
| Kanban ↔ Sync | 6 verified | 2 FIXED | 2 LOW | 2 (intentional) |
| Scripts | 8 verified | 3 FIXED | 4 MEDIUM, 1 PARTIAL | — |
| Test Quality | 6 verified | 3 FIXED | 3 MEDIUM | — |
| **Total** | **25** | **12 FIXED** | **11 open** | **2** |

---

## Actionable Items for Pass 29 Punchlist

See `BUG-HUNTER-PUNCHLIST.md` for the full list. Items prioritized by:
1. Whether they actively mask other bugs (Pattern A)
2. Whether they produce silently wrong outputs (Pattern B)
3. Whether they're a straightforward code fix vs. structural change (Pattern C)
