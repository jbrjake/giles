# Holtz Audit Summary (Run 4 — Targeted)

**Date:** 2026-03-23
**Project:** giles (Claude Code agile sprint plugin)
**Mode:** Targeted — kanban state flow + custom lenses (semantic-fidelity, temporal-protocol)
**Scope:** Commit ae4fa33 ("fix: apply entry semantics to kanban state transitions")
**Baseline:** 1220 tests, 0 failures, lint clean, 16.65s
**Final:** 1220 tests, 0 failures, lint clean, 16.82s

## Results

| Severity | Found | Resolved | Deferred |
|----------|-------|----------|----------|
| CRITICAL | 0 | 0 | 0 |
| HIGH | 0 | 0 | 0 |
| MEDIUM | 0 | 0 | 0 |
| LOW | 4 | 2 | 2 |
| **Total** | **4** | **2** | **2** |

**Tests:** 1220 → 1220 (no change — doc-only fixes)
**Lint:** clean → clean

## Key Assessment

The entry-semantics documentation change (ae4fa33) was **overwhelmingly accurate**. The commit updated 6 documentation files to frame the kanban state machine as using "entry semantics" — states are entered when work BEGINS, not when it ends. The code was already implementing this correctly; the commit documented what was already true.

The custom lenses found two small doc inaccuracies that standard lenses would have missed:

### SF-001: `done` description claimed "burndown updated" at entry (RESOLVED)
The `done` state description said "Merged, issue closed, burndown updated" but burndown is updated in a separate post-transition step. Changed to "Merged and issue closed — terminal state."

### TP-001: Two sync paths not documented in protocol reference (RESOLVED)
kanban-protocol.md's "GitHub Label Sync" section only mentioned `kanban.py` commands, omitting that `sync_tracking.py` is a complementary path with different enforcement. Added a blockquote noting the two-path design.

### SF-002: `integration` has no entry guard (DEFERRED — intentional design)
All working states except `integration` have code-enforced entry guards. The `integration` state's condition ("Review approved") is purely process-enforced. Documented in the Rules section as intentional.

### SF-003: Forced-done via sync bypasses entry guard (DEFERRED — intentional design)
`do_sync` can force a story to `done` without `pr_number` when GitHub issue is closed externally. Downstream consumers handle the missing field gracefully with fallback defaults.

## Custom Lens Value Assessment

| Lens | Findings | Standard lens equivalent |
|------|----------|------------------------|
| semantic-fidelity | 3 (SF-001, SF-002, SF-003) | 0 — standard lenses don't reason about temporal truthfulness of labels |
| temporal-protocol | 1 (TP-001) + confirmation that entry semantics are clean | 0 — standard lenses don't trace multi-file orchestration sequences |

The custom lenses proved their value: 4 findings that no standard lens would have caught. The `semantic-fidelity` lens is particularly useful for state machines — it asks "does this label tell the truth right now?" which surfaces documentation-reality mismatches that only manifest during execution.

## Prediction Accuracy

| Confidence | Predicted | Confirmed | Accuracy |
|------------|-----------|-----------|----------|
| HIGH | 1 | 1 | 100% |
| MEDIUM | 1 | 1 | 100% |
| LOW | 1 | 1 | 100% |
| **Total** | **3** | **3** | **100%** |

High accuracy reflects a well-scoped targeted audit with specific, testable predictions derived from the custom lens definitions.

## Recommendation

The entry-semantics documentation is now accurate and consistent across all files. The two doc fixes align the protocol reference with the actual runtime behavior. The deferred items are documented intentional design choices that don't need code changes.

The custom lenses (`semantic-fidelity` and `temporal-protocol`) are strong candidates for the standard lens registry — they found genuine issues that four runs of standard lenses never caught.
