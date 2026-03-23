# Step 0h: Predictive Recon (Run 2)

**Date:** 2026-03-23
**Context:** Post-fix audit. Run 1 resolved 10 items. Focus shifts to residual issues and new code introduced by fixes.

## Predictions

### Prediction 1
**Target:** hooks/commit_gate.py `_check_commit_single()`, hooks/session_context.py `_read_toml_string()`
**Predicted Issue:** bug/logic — run 1 fixes introduced new code that may have its own edge cases
**Confidence:** MEDIUM
**Basis:** New code (compound splitting, unquoted TOML) hasn't been audited by a fresh pass. Run 1 tested the happy path but edge cases in the new code are untested.
**Lens:** component
**Graph Support:** hook_commit_gate node, hook_session_context node
**Outcome:** —

### Prediction 2
**Target:** hooks/commit_gate.py ↔ hooks/verify_agent_output.py circular dependency
**Predicted Issue:** design/coupling — bidirectional deferred imports create fragile coupling
**Confidence:** HIGH
**Basis:** Architecture drift detection found circular dependency. Impact graph now has bidirectional imports edges. PAT-003 (TOML divergence) adds to the coupling concern.
**Lens:** integration
**Graph Support:** hook_commit_gate→hook_verify_agent (imports), hook_verify_agent→hook_commit_gate (imports)
**Outcome:** —

### Prediction 3
**Target:** hooks/ TOML parsers (session_context._read_toml_string, verify_agent_output._read_toml_key, review_gate._get_base_branch)
**Predicted Issue:** design/inconsistency — remaining TOML divergence beyond what run 1 fixed
**Confidence:** HIGH
**Basis:** Run 1's BJ-001 fix added unquoted value support to session_context, but review_gate and verify_agent_output still have limited parsers. Recommendation escalated from 2 summaries.
**Lens:** contract
**Graph Support:** diverges_from edges between hook_commit_gate/hook_session_context and hook_verify_agent
**Outcome:** —

### Prediction 4
**Target:** hooks/review_gate.py `_get_base_branch()` line 44
**Predicted Issue:** bug/logic — unquoted base_branch value not handled (same class as BJ-001)
**Confidence:** HIGH
**Basis:** PAT-003 sibling. Run 1 fixed session_context but review_gate's inline parser at line 44 still requires quotes.
**Lens:** contract
**Graph Support:** PAT-003 pattern
**Outcome:** —

### Prediction 5
**Target:** tests/test_hooks.py — new compound command tests
**Predicted Issue:** test/shallow — run 1 added 5 compound tests but may not cover pipe (|) or double-pipe (||)
**Confidence:** LOW
**Basis:** review_gate already handles pipe splitting; commit_gate's new splitting should too. Single weak signal.
**Lens:** component
**Graph Support:** —
**Outcome:** —
