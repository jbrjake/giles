# Step 0h: Predictive Recon

**Date:** 2026-03-23
**Inputs:** Recon 0a-0g, impact graph, prior audit patterns, churn data

## Predictions

### Prediction 1
**Target:** CLAUDE.md lines 57-62 (scripts table), 6 scripts missing §-anchors
**Predicted Issue:** doc/drift — CLAUDE.md references §-anchors that don't exist in source files
**Confidence:** HIGH
**Basis:** Lint results (0d) — 21 broken references confirmed. Direct observation.
**Lens:** contract
**Graph Support:** smoke_test, gap_scanner, test_categories, risk_register, assign_dod_level, history_to_checklist all have zero §-anchor definitions
**Outcome:** —

### Prediction 2
**Target:** Makefile lint target (lines 29-49)
**Predicted Issue:** doc/drift or design/inconsistency — Makefile py_compile list may be missing recently added scripts
**Confidence:** HIGH
**Basis:** 6 scripts referenced in CLAUDE.md lack §-anchors, suggesting they were added later and may not have been wired into all build targets. Churn data shows smoke_test.py had 4 changes in last 50 commits.
**Lens:** contract
**Graph Support:** —
**Outcome:** —

### Prediction 3
**Target:** hooks/hooks.json, tests/test_hooks.py
**Predicted Issue:** doc/drift or bug/state — stale references to old hook paths (`.claude-plugin/hooks/`) after recent refactor
**Confidence:** MEDIUM
**Basis:** Churn (0e) shows 18 changes to test_hooks.py, 10 to commit_gate.py. Recent commit `2dc773d` moved hooks. Structural change = high drift risk.
**Lens:** integration
**Graph Support:** hook_common → hook_* dependency chain
**Outcome:** —

### Prediction 4
**Target:** scripts/validate_config.py — TOML parser edge cases
**Predicted Issue:** bug/logic — TOML parser may have remaining edge cases in escape handling or type coercion
**Confidence:** MEDIUM
**Basis:** Prior passes found TOML parser issues (BH21, BH24). 1245 LOC with custom parser is inherently risky. Prior pattern: BH-021 (quoted keys), BH-024 (unquoted garbage).
**Lens:** component
**Graph Support:** validate_config has 20 dependents — any parser bug cascades
**Outcome:** —

### Prediction 5
**Target:** scripts/kanban.py ↔ skills/sprint-run/scripts/sync_tracking.py
**Predicted Issue:** bug/state — two-path state management may have edge cases where both paths write conflicting state
**Confidence:** MEDIUM
**Basis:** Both have 9 changes in churn (highest production files). Prior passes found lock coordination issues (BH24-002). Two writers to the same file = concurrency risk.
**Lens:** integration
**Graph Support:** sync_tracking→kanban imports edge, sync_tracking→validate_config imports edge
**Outcome:** —

### Prediction 6
**Target:** scripts/sync_backlog.py import handling
**Predicted Issue:** bug/error-handling — cross-skill import with try/except may silently degrade
**Confidence:** LOW
**Basis:** sync_backlog lines 27-35 catch ImportError and set modules to None. Callers must check for None before use. Single weak signal.
**Lens:** error-propagation
**Graph Support:** sync_backlog→bootstrap_github, sync_backlog→populate_issues edges
**Outcome:** —

### Prediction 7
**Target:** hooks/_common.py, hooks/session_context.py
**Predicted Issue:** bug/error-handling — hooks may not handle all error conditions cleanly after JSON protocol switch
**Confidence:** MEDIUM
**Basis:** Recent commit switched to JSON output protocol. New protocol = new failure modes. session_context has 9 changes in churn.
**Lens:** error-propagation
**Graph Support:** hook_session_context→hook_common edge
**Outcome:** —

### Prediction 8
**Target:** tests/test_new_scripts.py
**Predicted Issue:** test/shallow — newer scripts (smoke_test, gap_scanner, test_categories, risk_register, assign_dod_level, history_to_checklist) may have minimal test coverage
**Confidence:** MEDIUM
**Basis:** These 6 scripts all lack §-anchors, suggesting they were added as a batch. test_new_scripts.py is their test file. Name suggests catch-all test file.
**Lens:** component
**Graph Support:** —
**Outcome:** —
