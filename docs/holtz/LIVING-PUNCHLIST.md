# Living Punchlist

**Project:** giles
**Established:** 2026-03-23
**Last Updated:** 2026-03-23
**Audits Completed:** 5

## Active Vulnerability Model

### Patterns This Project Is Susceptible To

- **PAT-001:** Batch addition without full wiring — new scripts/modules added without updating all integration points
  - Instances: BH-001 (run 1, 3 scripts), BH-002 (run 1), BH-004 (run 1), BH-001 (run 5, 5 hooks)
  - Root cause: No automated check validates that new scripts appear in all wiring points (Makefile, NAMESPACE_MAP, etc.)
  - Detection rule: `find scripts/ hooks/ skills/*/scripts/ -name "*.py" ! -name "__init__.py" | wc -l` vs `grep -c "py_compile" Makefile`
  - First seen: Run 1 (2026-03-23)

### Risk Hotspots

| Node | Risk Score | Last Bug | Audit Count | Notes |
|------|-----------|----------|-------------|-------|
| `hooks/_common.py` | 0.4 | PAT-003/004 (Run 3) | 4 | TOML parser consolidation target; stable since run 3 |
| `hooks/commit_gate.py` | 0.3 | PAT-002 (Run 1) | 4 | Security hardening; stable since run 1 |
| `scripts/validate_config.py` | 0.2 | PAT-004 (Run 3) | 5 | Foundation hub; escape handling aligned in run 3 |

### Architectural Risks

(none at MEDIUM+ severity — all prior drift entries have been resolved)

### Persistent Gaps

- **Makefile lint inventory validation**
  - First identified: Run 1 (2026-03-23)
  - Still present as of: Run 5 (2026-03-23)
  - Impact: PAT-001 instances — new scripts miss lint coverage until manually caught by audit
  - Recommended fix: Add CI check comparing `find` output against Makefile py_compile entries

## Proactive Checks

### Check 1: Script inventory parity
**Source:** PAT-001
**Trigger:** New `.py` file added to `scripts/`, `hooks/`, or `skills/*/scripts/`
**Heuristic:** `diff <(find scripts/ hooks/ skills/*/scripts/ -name "*.py" ! -name "__init__.py" | sort) <(grep "py_compile" Makefile | sed 's/.*py_compile //' | sort)`
**If triggered:** Add the new script to Makefile lint target.

### Check 2: Sibling hook hardening
**Source:** PAT-002
**Trigger:** Security fix applied to any hook file in `hooks/`
**Heuristic:** Check all other hook files for the same vulnerability class
**If triggered:** Apply the same fix to all sibling hooks.

## Prediction Accuracy

### Cumulative Accuracy

| Confidence | Predicted | Confirmed | Accuracy |
|------------|-----------|-----------|----------|
| HIGH | 4 | 2 | 50% |
| MEDIUM | 7 | 1 | 14% |
| LOW | 3 | 0 | 0% |
| **Total** | **14** | **3** | **21%** |

(Note: Run 4 was targeted with custom lenses — 3/3 confirmed. Runs 1-3 averaged ~45% accuracy. Run 5 was 0/8 — expected for a mature codebase.)

### Calibration Notes

- HIGH-confidence predictions from hotspots and pattern matches are reliable for early runs (100% in runs 1, 4) but lose accuracy as the codebase matures (0% in run 5)
- Predictions are most valuable in the first 2-3 runs on a codebase; after that, the easy bugs have been found
- Custom lenses (semantic-fidelity, temporal-protocol) produced 100% accuracy when introduced (run 4) because they target a dimension standard lenses miss — recalibrate when applying new lens types

## History

### 2026-03-23: Run 5 completed
- Added: PAT-001 reoccurrence (hooks missing from Makefile lint)
- Removed: (nothing — all existing items still active)
- Calibration: prediction accuracy was 0% (0 of 8 predictions confirmed) — expected for mature codebase
- Notes: First run to create the living punchlist. Cumulative stats pulled from 5 run summaries. Risk scores estimated from audit history. The only persistent gap (Makefile lint validation) has recurred across 2 runs and should be automated.
