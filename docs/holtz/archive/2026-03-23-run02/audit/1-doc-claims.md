# Phase 1: Doc-to-Implementation Claims (Run 2)

## Focus: Verify run 1 fixes and remaining divergence

### HIGH confidence predictions

- [x] **Prediction 2: Circular hook dependency** → CONFIRMED (drift log entry, BH-009 scope)
- [x] **Prediction 3: Remaining TOML divergence** → CONFIRMED
  - session_context: fixed (unquoted values handled)
  - verify_agent_output: handles unquoted (line 147: bare return val)
  - review_gate._get_base_branch: STILL BROKEN for unquoted → BH-010
  - review_gate._log_blocked sprints_dir: STILL BROKEN for unquoted (LOW, BJ-007 from run 1)
- [x] **Prediction 4: review_gate unquoted base_branch** → CONFIRMED → BH-010

### MEDIUM confidence predictions

- [x] **Prediction 1: New code edge cases** → UNCONFIRMED
  - _check_commit_single: correct extraction from old logic, no new edge cases found
  - session_context unquoted handler: \S+ correctly matches non-space, quoted matchers take priority, inline comments stripped

### LOW confidence predictions

- [x] **Prediction 5: Pipe splitting** → UNCONFIRMED
  - Regex `(?:&&|\|\||\||;)` handles pipe. Same regex as review_gate.

## Summary

2 CONFIRMED / 3 UNCONFIRMED — 40% accuracy. The TOML divergence PAT-003 continues to produce siblings.
