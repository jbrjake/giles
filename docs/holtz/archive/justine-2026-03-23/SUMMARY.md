# Justine Audit Summary

**Project:** giles
**Date:** 2026-03-23
**Run:** 3 (parallel dispatch alongside Holtz run 3)
**Auditor:** Justine (breadth-first adversarial)

## Totals

| Category | Count |
|----------|-------|
| Findings | 4 |
| CRITICAL | 0 |
| HIGH | 2 |
| MEDIUM | 1 |
| LOW | 1 |
| Patterns | 1 |
| Convergence iterations | 1 |
| Areas examined | 31 scripts + 18 test files |

## Findings Summary

| ID | Severity | Category | Title |
|----|----------|----------|-------|
| BJ-001 | HIGH | design/inconsistency | Hooks TOML unescape missing \b, \f, \uXXXX, \UXXXXXXXX escape sequences |
| BJ-002 | LOW | design/inconsistency | Hooks and validate_config have divergent inline comment stripping |
| BJ-003 | MEDIUM | bug/logic | session_context.extract_high_risks uses raw pipe split while risk_register uses escaped-pipe-aware split |
| BJ-004 | HIGH | test/shallow | test_hexwise_setup assertIsNotNone checks are rubber stamps |

## Patterns

### PAT-001: Dual Parser Divergence (2 instances)
The hooks subsystem (_common.py) and the scripts subsystem (validate_config.py) each implement their own TOML parsing. The BH-009 consolidation moved parsing into _common.py for hooks but did not align the escape-sequence handling with validate_config.py. This creates a contract divergence: the same `project.toml` value is interpreted differently depending on whether it is read by a hook or a script. Global pattern library match: `dual-parser-divergence.md`.

## Prediction Accuracy

| Confidence | Predicted | Confirmed | Accuracy |
|------------|-----------|-----------|----------|
| HIGH       | 4         | 3         | 75%      |
| MEDIUM     | 2         | 1         | 50%      |
| LOW        | 0         | 0         | -        |
| **Total**  | **6**     | **4**     | **67%**  |

Notes on unconfirmed predictions:
- Prediction 3 (MEDIUM): property test crash-fuzz assertions are intentionally structural, not rubber stamps. Correctly downgraded.
- Prediction 6 (LOW, initially): documented design limitation, not a bug.

## Recommendations

1. **Consolidate TOML escape handling:** Either have _common.py import validate_config.py's `_unescape_toml_string`, or copy the missing escape sequences (\b, \f, \uXXXX, \UXXXXXXXX) into _common.py's `_unescape_basic_string`. The former is cleaner but creates a cross-subsystem dependency. The latter maintains isolation.

2. **Fix session_context pipe splitting:** Replace `line.split("|")` with a pipe-aware split that respects `\|` escaping, consistent with risk_register.py. This is a one-line fix with direct data-flow impact.

3. **Strengthen deep doc detection tests:** Replace `assertIsNotNone` assertions with `assertEqual` or `assertIn` checks that verify the detected PATH, not just its existence. This prevents regressions where detection returns a wrong-but-non-None path.

4. **Consider adding code coverage:** The project has 1205 tests but no coverage measurement. Adding pytest-cov would reveal untested paths systematically rather than relying on manual audit.

## Before/After Metrics

| Metric | Baseline | Post-Audit |
|--------|----------|------------|
| Tests passing | 1205 | 1205 |
| Tests failing | 0 | 0 |
| Tests skipped | 0 | 0 |
| Known divergences documented | 0 | 2 |
| Test anti-patterns flagged | 0 | 1 |
| Logic bugs identified | 0 | 1 |

## Convergence Notes

Convergence achieved on first pass. The codebase is mature and well-tested (1205 tests, all passing, extensive property tests, full FakeGitHub mock infrastructure). The findings are at the seams between subsystems, not within individual components. This is consistent with a project that has had multiple prior audit runs (2 Holtz runs archived) and addressed component-level issues.

The remaining findings are integration-level: two parsers that diverge, a table splitter that disagrees with its writer, and tests that check existence but not correctness. These are the bugs that survive because nobody's job is to look at the whole surface.
