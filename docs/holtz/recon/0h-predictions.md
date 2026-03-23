# 0h: Predictive Recon (Run 5)

## Prediction 1
**Target:** `skills/sprint-setup/scripts/populate_issues.py` — `parse_detail_blocks`, `format_issue_body`
**Predicted Issue:** Code-fence-unaware parsing — regex applied to markdown body content that may contain fenced code blocks.
**Confidence:** HIGH
**Basis:** Global pattern library match (code-fence-unaware-parsing.md) + detection heuristic hit
**Lens:** component
**Graph Support:** populate_issues node exists, imports validate_config
**Outcome:** UNCONFIRMED — The `**As a**` pattern is markdown-specific syntax unlikely inside code fences. The regex operates on individual story sections, not full document content.

## Prediction 2
**Target:** `skills/sprint-release/scripts/release_gate.py` — `write_version_to_toml` around line 308-319
**Predicted Issue:** TOML section parsing edge cases
**Confidence:** MEDIUM
**Basis:** Churn (4 changes in 50 commits) + global pattern hit
**Lens:** component
**Graph Support:** release_gate node exists
**Outcome:** UNCONFIRMED — The code has multiple layers of defense: comment exclusion, next-section detection, quote-aware version matching.

## Prediction 3
**Target:** `scripts/validate_config.py` — `read_tf`, `extract_sp`
**Predicted Issue:** Frontmatter parsing or body regex issues
**Confidence:** MEDIUM
**Basis:** Foundation file + regex on content variables
**Lens:** component
**Graph Support:** validate_config is hub node
**Outcome:** UNCONFIRMED — The `read_tf` regex handles the `---` separator correctly (requires start-of-line). The `extract_sp` patterns are specific enough to avoid code-fence false matches in practice.

## Prediction 4
**Target:** `scripts/sprint_init.py` — `ProjectScanner` class
**Predicted Issue:** Loose regex heuristics may produce false positives
**Confidence:** MEDIUM
**Basis:** 1027 LOC, heuristic-heavy code
**Lens:** integration
**Graph Support:** sprint_init imports validate_config
**Outcome:** UNCONFIRMED — Heuristics use graduated confidence scores and multiple detection layers. The sprint header requirement for milestone detection prevents false positives from epics/sagas.

## Prediction 5
**Target:** `skills/sprint-monitor/scripts/check_status.py` — `check_ci`, `_first_error`
**Predicted Issue:** CI output parsing ambiguity between success and error patterns
**Confidence:** HIGH
**Basis:** Detection heuristic hit + parsing arbitrary external output
**Lens:** error-propagation
**Graph Support:** check_status node exists
**Outcome:** UNCONFIRMED — The false positive pattern correctly handles "0 errors"/"no failures". The compound-word case ("error-handling") is by design — the function treats any line with "error" as a potential error line, which is reasonable for CI log scanning.

## Prediction 6
**Target:** `hooks/session_context.py` — extraction functions
**Predicted Issue:** Remaining edge cases in markdown extraction
**Confidence:** LOW
**Basis:** High churn + prior findings
**Lens:** data-flow
**Graph Support:** session_context node exists
**Outcome:** UNCONFIRMED — The extraction functions handle alignment markers, escaped pipes, and section boundaries correctly after runs 1-3 fixes.

## Prediction 7
**Target:** `scripts/kanban.py` — state machine semantics
**Predicted Issue:** semantic-fidelity issues after run 4 changes
**Confidence:** MEDIUM
**Basis:** Run 4 found 4 issues. Custom semantic-fidelity lens.
**Lens:** semantic-fidelity (custom)
**Graph Support:** kanban node, assumes edges
**Outcome:** UNCONFIRMED — State descriptions align with entry semantics after run 4 fixes. Preconditions table matches code.

## Prediction 8
**Target:** Cross-file: `kanban.py` + `sync_tracking.py` + `kanban-protocol.md`
**Predicted Issue:** Temporal ordering assumptions in two-path state management
**Confidence:** MEDIUM
**Basis:** Custom temporal-protocol lens + two-path architecture
**Lens:** temporal-protocol (custom)
**Graph Support:** kanban→sync_tracking relationship
**Outcome:** UNCONFIRMED — Both paths use lock_sprint for mutual exclusion. The two-path design is well-documented and the differences are intentional.

## Summary
0 of 8 predictions confirmed. The codebase has been hardened by 4 prior audit runs + 39 bug-hunter passes. The predicted areas are well-defended.
