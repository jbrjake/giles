# 0h: Predictive Recon (Run 3)

## Input Sources
- Pattern Brief: none (no patterns-brief.md from prior runs)
- Impact Graph: 31 nodes, 35 edges (stable)
- Git churn: hooks remain highest-churn subsystem
- Prior findings: 12 resolved across 2 runs (PAT-001 batch wiring, PAT-002 hook inconsistency, PAT-003 TOML divergence — all resolved)
- Recon observations: minimal code delta, stale comments, baseline inaccuracies
- Global pattern library: all 6 heuristics clean

## Predictions

### Prediction 1
**Target:** `hooks/verify_agent_output.py:29-36`
**Predicted Issue:** Stale comment/code — backward-compat rationale references a dependency that was eliminated in Run 2
**Confidence:** HIGH
**Basis:** Direct observation during recon (0a drift detection). commit_gate no longer imports _read_toml_key from verify_agent_output.
**Lens:** component
**Graph Support:** verify_agent → commit_gate edge (one-way after Run 2 fix)
**Outcome:** CONFIRMED — BK-001

### Prediction 2
**Target:** `hooks/session_context.py` — `_add_section()` and `format_context()` refactoring
**Predicted Issue:** Edge cases in truncation logic (empty lists, exactly-at-limit, negative remaining)
**Confidence:** MEDIUM
**Basis:** New code since Run 2 (BJ-010 fix). Refactoring introduces _MAX_ITEMS_PER_SECTION truncation. New helper functions are prime candidates for edge-case gaps.
**Lens:** component
**Graph Support:** session_context node (risk_score stable)
**Outcome:** UNCONFIRMED — code and tests are solid, no edge-case gaps

### Prediction 3
**Target:** `hooks/verify_agent_output.py:125-131` — `mark_verified()` bridge
**Predicted Issue:** Silent failure if commit_gate module has import errors (try/except ImportError swallows all errors)
**Confidence:** LOW
**Basis:** Deferred import inside try/except with bare `pass`. If commit_gate has a syntax error or broken import chain, the bridge silently fails. This was acceptable as a safety net but could mask real failures.
**Lens:** error-propagation
**Graph Support:** verify_agent → commit_gate edge
**Outcome:** UNCONFIRMED — except ImportError is appropriate narrowing; SyntaxError/RuntimeError correctly propagate
