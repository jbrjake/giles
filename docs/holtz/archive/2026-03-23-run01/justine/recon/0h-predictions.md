# 0h: Predictions

## Prediction 1
**Target:** `hooks/verify_agent_output._read_toml_key()` vs `validate_config.parse_simple_toml()`
**Predicted Issue:** dual-parser-divergence -- TOML edge cases handled by validate_config but NOT by hooks mini-parser
**Confidence:** HIGH
**Basis:** Global pattern library match (`dual-parser-divergence.md`) + three independent parsers confirmed in recon
**Lens:** integration, contract
**Graph Support:** diverges_from edge in impact graph
**Outcome:** CONFIRMED -- type divergence on int/bool values (BJ-002), systemic pattern (BJ-003)

## Prediction 2
**Target:** `hooks/session_context._read_toml_string()` vs `validate_config.parse_simple_toml()`
**Predicted Issue:** dual-parser-divergence -- session_context string parser fails on unquoted values
**Confidence:** HIGH
**Basis:** Global pattern library match + direct code comparison shows different escape tables
**Lens:** integration, data-flow
**Graph Support:** diverges_from edge in impact graph
**Outcome:** CONFIRMED -- empty string returned for unquoted values (BJ-001)

## Prediction 3
**Target:** `hooks/review_gate._get_base_branch()` inline TOML parser
**Predicted Issue:** dual-parser-divergence -- inline regex parser does not handle all edge cases
**Confidence:** HIGH
**Basis:** Pattern match + code shows simplest of three parsers
**Lens:** integration, contract
**Graph Support:** diverges_from edge in impact graph
**Outcome:** CONFIRMED -- section comments handled (BH35-005 fix), but unquoted values still fail silently. Part of PAT-001 pattern (BJ-003, BJ-007).

## Prediction 4
**Target:** `hooks/commit_gate.py:12`, `hooks/verify_agent_output.py:13`
**Predicted Issue:** dead code -- unused `json` imports
**Confidence:** HIGH
**Basis:** Ruff lint confirmed F401
**Lens:** component
**Graph Support:** --
**Outcome:** CONFIRMED -- BJ-004

## Prediction 5
**Target:** `hooks/commit_gate._working_tree_hash()` -- git diff HEAD
**Predicted Issue:** Working tree hash does not cover untracked files
**Confidence:** MEDIUM
**Basis:** Code analysis
**Lens:** security, data-flow
**Graph Support:** --
**Outcome:** CONFIRMED (narrower than predicted) -- BJ-005. The risk is limited to files already staged before test run, not new files staged after.

## Prediction 6
**Target:** `hooks/session_context.extract_high_risks()` -- table parsing
**Predicted Issue:** Column index shift on empty cells
**Confidence:** MEDIUM
**Basis:** Code analysis of cell parsing logic
**Lens:** data-flow, error-propagation
**Graph Support:** --
**Outcome:** CONFIRMED -- BJ-006. Empty cell causes risk to be silently dropped.

## Prediction 7
**Target:** `hooks/review_gate._log_blocked()` -- sprints_dir parsing
**Predicted Issue:** Inline parser fails on unquoted values
**Confidence:** LOW
**Basis:** Code analysis
**Lens:** contract
**Graph Support:** --
**Outcome:** CONFIRMED -- BJ-007. Part of PAT-001 pattern.

## Prediction 8
**Target:** Test suite -- rubber stamp anti-pattern
**Predicted Issue:** Tests check format without checking value
**Confidence:** MEDIUM
**Basis:** Anti-pattern #11 (Rubber Stamp)
**Lens:** contract
**Graph Support:** --
**Outcome:** UNCONFIRMED -- Test analysis shows heavy use of assertEqual (value checks). Tests are not rubber stamps. The test suite checks specific values, not just format.
