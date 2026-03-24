# Living Punchlist

**Project:** giles
**Established:** 2026-03-23
**Last Updated:** 2026-03-23
**Audits Completed:** 6

## Active Vulnerability Model

### Patterns This Project Is Susceptible To

- **PAT-001:** Batch addition without full wiring — new scripts/modules added without updating all integration points
  - Instances: BH-001 (run 1, 3 scripts), BH-002 (run 1), BH-004 (run 1), BH-001 (run 5, 5 hooks)
  - Root cause: Now mitigated by `check_lint_inventory.py` (added after run 5, hardened in run 6)
  - Detection rule: `make lint` now runs `check_lint_inventory.py` automatically
  - First seen: Run 1 (2026-03-23)
  - **Status:** MITIGATED — automated check in place since commit `ce946e0`

### Risk Hotspots

| Node | Risk Score | Last Bug | Audit Count | Notes |
|------|-----------|----------|-------------|-------|
| `hooks/_common.py` | 0.4 | PAT-003/004 (Run 3) | 5 | TOML parser consolidation target; stable since run 3 |
| `hooks/commit_gate.py` | 0.3 | PAT-002 (Run 1) | 5 | Security hardening; stable since run 1 |
| `scripts/validate_config.py` | 0.2 | PAT-004 (Run 3) | 6 | Foundation hub; escape handling aligned in run 3 |

### Architectural Risks

(none at MEDIUM+ severity — all prior drift entries have been resolved)

### Persistent Gaps

- ~~**Makefile lint inventory validation**~~ **RESOLVED** — `check_lint_inventory.py` now runs as part of `make lint` (commit `ce946e0`). Run 6 hardened it with comment filtering and proper tests.

## Proactive Checks

### Check 1: Script inventory parity
**Source:** PAT-001
**Status:** AUTOMATED — `check_lint_inventory.py` runs in `make lint`
**Trigger:** Every lint run
**If triggered:** Script reports missing/stale entries and exits non-zero for missing.

### Check 2: Sibling hook hardening
**Source:** PAT-002
**Trigger:** Security fix applied to any hook file in `hooks/`
**Heuristic:** Check all other hook files for the same vulnerability class
**If triggered:** Apply the same fix to all sibling hooks.

## Prediction Accuracy

### Cumulative Accuracy

| Confidence | Predicted | Confirmed | Accuracy |
|------------|-----------|-----------|----------|
| HIGH | 5 | 3 | 60% |
| MEDIUM | 8 | 1 | 13% |
| LOW | 5 | 0 | 0% |
| **Total** | **18** | **4** | **22%** |

### Calibration Notes

- HIGH-confidence predictions from hotspots and pattern matches are reliable for early runs (100% in runs 1, 4) but lose accuracy as the codebase matures (0% in run 5)
- Run 6: HIGH confidence prediction on new code confirmed (1/1). New code is where predictions still have value on mature codebases.
- Predictions are most valuable in the first 2-3 runs on a codebase; after that, the easy bugs have been found
- Custom lenses (semantic-fidelity, temporal-protocol) produced 100% accuracy when introduced (run 4)

## History

### 2026-03-23: Run 6 completed
- Resolved: Persistent gap (Makefile lint validation) now automated and hardened
- PAT-001 status updated to MITIGATED
- Risk hotspot audit counts incremented
- 3 findings (1 HIGH test/bogus, 1 MEDIUM test/missing, 1 LOW bug/logic) — all in the new check_lint_inventory.py, all resolved
- Prediction accuracy: 1/4 (25%) — the HIGH prediction on new code confirmed, 3 others unconfirmed as expected for mature code
- Justine contributed 2 of 3 merged findings (BJ-002 stale path, BJ-003 comment regex)

### 2026-03-23: Run 5 completed
- Added: PAT-001 reoccurrence (hooks missing from Makefile lint)
- Removed: (nothing — all existing items still active)
- Calibration: prediction accuracy was 0% (0 of 8 predictions confirmed) — expected for mature codebase
- Notes: First run to create the living punchlist. Cumulative stats pulled from 5 run summaries. Risk scores estimated from audit history.
