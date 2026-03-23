# Phase 1: Doc-to-Implementation Audit (Run 4)

## Semantic-Fidelity Lens: State Descriptions vs Runtime

For each state, trace when the value is set across all callers and compare against the documented description.

### todo — "Story accepted into sprint, not yet started"
- **Set by:** do_sync (new story creation), create_from_issue (sync_tracking)
- **Runtime meaning:** Story exists in tracking file but no work has begun
- **Verdict:** ACCURATE ✓

### design — "Implementer creating branch, opening draft PR, writing design notes"
- **Set by:** do_transition (orchestrator: todo → design)
- **Entry guard:** implementer must be set
- **Runtime meaning:** Implementer has been assigned and dispatched. Design work is in progress.
- **Progressive form ("creating"):** Correctly implies ongoing work, not completion.
- **Verdict:** ACCURATE ✓

### dev — "TDD in progress: failing tests, implementation, green, push"
- **Set by:** do_transition (implementer: design → dev)
- **Entry guard:** branch and pr_number must exist (design deliverables)
- **Runtime meaning:** Design is complete, TDD implementation in progress.
- **Verdict:** ACCURATE ✓

### review — "Reviewer persona evaluating the PR"
- **Set by:** do_transition (orchestrator: dev → review)
- **Entry guard:** implementer and reviewer must be set
- **Runtime meaning:** Reviewer has been assigned and dispatched. PR review in progress.
- **Verdict:** ACCURATE ✓

### integration — "Review approved — verifying CI, merging, closing issue"
- **Set by:** do_transition (orchestrator: review → integration)
- **Entry guard:** NONE (no preconditions checked)
- **Runtime meaning:** Orchestrator has decided to proceed with integration. CI/merge work begins.
- **Gap:** Description says "Review approved" but code doesn't verify review status.
  This is documented intentional behavior (Rules: "process guidelines, not programmatically enforced").
- **Verdict:** ACCURATE in practice (orchestrator only transitions after approval), but NOT code-enforced.

### done — "Merged, issue closed, burndown updated"
- **Set by:** do_transition (orchestrator: integration → done), do_sync (forced close)
- **Entry guard:** pr_number must exist (code path); bypassed by do_sync forced close
- **Runtime meaning at entry:** PR is merged, issue IS closed (close happens inside do_transition). Burndown is NOT yet updated.
- **Gap:** "burndown updated" is post-transition work — happens in a separate step after the transition.
- **Verdict:** INACCURATE — burndown is not updated at the moment of entry. See SF-001.

## Semantic-Fidelity Lens: Entry Guards vs Transition Descriptions

| Transition | Documented condition | Code enforcement | Match? |
|------------|---------------------|------------------|--------|
| todo → design | "Implementer assigned, ready to begin" | implementer required | ✓ |
| design → dev | "Design deliverables ready (branch, draft PR, design notes)" | branch + pr_number required | Partial — "design notes" not checked |
| dev → review | "Implementation complete, PR ready, reviewer assigned" | implementer + reviewer required | Partial — "PR ready" not checked |
| review → dev | "Changes requested — returning to development" | (none) | Not enforced |
| review → integration | "Review approved by reviewer" | (none) | Not enforced |
| integration → done | "CI green, PR merged, issue closed" | pr_number required | Partial — merge/CI not checked |

**Pattern:** The code enforces FIELD PRESENCE (metadata exists) but not WORKFLOW STATE (work was actually done). This is consistent and intentional — the docs could be clearer about which conditions are code-enforced vs process-enforced.

## Temporal-Protocol Lens: Orchestration Flow Trace

### Normal lifecycle (no rework)
```
1. Orchestrator: assign --implementer → transition todo → design → dispatch implementer
   Work: design (branch, draft PR, notes)
2. Implementer: update --branch --pr-number → transition design → dev
   Work: TDD (tests, implementation, push, mark ready)
3. Implementer exits → Orchestrator: assign --reviewer → transition dev → review → dispatch reviewer
   Work: three-pass review
4. Reviewer approves → Orchestrator: transition review → integration
   Work: verify CI, squash-merge
5. Orchestrator: transition integration → done (closes issue inside transition)
   Post-transition: update burndown, sync tracking
```

- **Phantom states:** None. Each state has a non-zero work window.
- **Double-taps:** None. No consecutive transitions without intervening work.
- **Protocol drift:** None between kanban-protocol.md and story-execution.md — both now use consistent entry-semantics language.

### Rework loop (review → dev → review)
```
1. Reviewer requests changes → Orchestrator: transition review → dev
2. Orchestrator re-dispatches implementer with review feedback
3. Implementer fixes, pushes, marks ready, exits
4. Orchestrator: transition dev → review → dispatch new reviewer instance
```

- **Temporal gap:** Fresh implementer subagent must reconstruct context from PR reviews. This is by design but is a known fragility.
- **Entry guard re-check:** dev entry guard (branch + pr_number) was already satisfied from the first design phase. Re-entering dev doesn't re-validate.

### Forced-done via sync
```
1. Someone closes GitHub issue manually (any state)
2. do_sync detects closed issue → forces local state to "done"
3. Bypasses check_preconditions — tracking file may lack pr_number
```

- **Entry guard bypass:** Intentional (BH22-050). Downstream consumers handle gracefully.
- **Transition log:** Records as "external: GitHub sync" — traceable.

## Two-Sync-Path Temporal Analysis

| Aspect | kanban.py sync (do_sync) | sync_tracking.py (sync_one) |
|--------|--------------------------|------------------------------|
| Transition validation | Yes (validate_transition) | No |
| Entry guard enforcement | No | No |
| Illegal transition handling | Rejects with warning | Accepts silently |
| State regression | Rejects (e.g., review→todo) | Accepts |
| Stale metadata cleanup | N/A | No (BH39-103: "by design") |

**Gap:** kanban-protocol.md mentions "sync local tracking files with GitHub state" but doesn't differentiate the two paths or their enforcement levels. See TP-003.
