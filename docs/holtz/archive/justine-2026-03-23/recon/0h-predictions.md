# 0h: Predictions

## Prediction 1
**Target:** `hooks/_common.py:_unescape_basic_string` vs `scripts/validate_config.py:_unescape_toml_string`
**Predicted Issue:** Dual parser divergence — hooks TOML unescape missing \b, \f, \uXXXX, \UXXXXXXXX
**Confidence:** HIGH
**Basis:** Global pattern library match (`dual-parser-divergence.md`) + code comparison confirms divergent escape handling
**Lens:** contract
**Graph Support:** _common.py -> validate_config.py (both parse project.toml)
**Outcome:** CONFIRMED

## Prediction 2
**Target:** `tests/test_hexwise_setup.py:161-175`, `tests/test_pipeline_scripts.py:1258-1301`
**Predicted Issue:** Rubber Stamp (anti-pattern #11) — assertIsNotNone checks existence but not correctness of deep doc detection results
**Confidence:** HIGH
**Basis:** 12+ assertIsNotNone calls checking detection results without verifying the detected PATH or VALUE
**Lens:** contract
**Graph Support:** —
**Outcome:** CONFIRMED

## Prediction 3
**Target:** `tests/test_property_parsing.py:42-95`
**Predicted Issue:** Rubber Stamp (anti-pattern #11) — property tests for extract_story_id check isinstance(result, str) and len > 0, but `test_never_returns_empty` and `test_never_crashes` do not check value correctness
**Confidence:** MEDIUM
**Basis:** Property tests that verify type and non-emptiness are crash-fuzz tests, which are valuable, but they are not value tests. Other tests in the same class DO check values (test_standard_ids_extracted). The crash-fuzz tests are not themselves rubber stamps — they serve a different purpose. Downgrading from initial HIGH.
**Lens:** contract
**Graph Support:** —
**Outcome:** UNCONFIRMED — crash-fuzz tests are intentionally structural, not rubber stamps

## Prediction 4
**Target:** `hooks/_common.py:_strip_inline_comment` vs `scripts/validate_config.py:_strip_inline_comment`
**Predicted Issue:** Dual parser divergence — different implementations of inline comment stripping
**Confidence:** HIGH
**Basis:** Two separate `_strip_inline_comment` functions exist with different implementation approaches (enumerate vs while-loop, different escape tracking)
**Lens:** contract
**Graph Support:** Both consume TOML from project.toml
**Outcome:** CONFIRMED

## Prediction 5
**Target:** `scripts/risk_register.py:_split_table_row` and `hooks/session_context.py:extract_high_risks`
**Predicted Issue:** Markdown table parsing inconsistency — risk_register uses escaped-pipe-aware split, session_context uses raw split
**Confidence:** MEDIUM
**Basis:** risk_register.py:68 uses `re.split(r'(?<!\\)\|', line)` (escaped-pipe aware), but session_context.py:114 uses `line.split("|")` (raw split). If a risk title contains `\|`, session_context will split incorrectly.
**Lens:** data-flow
**Graph Support:** Both read the same risk-register.md file
**Outcome:** CONFIRMED

## Prediction 6
**Target:** `scripts/validate_config.py:kanban_from_labels` and its callers
**Predicted Issue:** kanban_from_labels returns "done" for closed issues even when kanban label says otherwise. sync_tracking.py accepts this without transition validation. This is documented and intentional, but the STATE REGRESSION path (review->todo) leaves stale metadata.
**Confidence:** LOW
**Basis:** Documented at BH39-103 in sync_tracking.py. The comment says "by design". Not a bug — a known design limitation.
**Lens:** data-flow
**Graph Support:** —
**Outcome:** UNCONFIRMED — documented design decision, not a bug
