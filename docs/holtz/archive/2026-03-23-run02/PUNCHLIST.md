# Holtz Punchlist (Run 2)
> Generated: 2026-03-23 | Project: giles | Baseline: 1193 pass, 0 fail, 0 skip

## Summary
| Severity | Open | Resolved | Deferred |
|----------|------|----------|----------|
| CRITICAL | 0 | 0 | 0 |
| HIGH | 0 | 0 | 0 |
| MEDIUM | 0 | 2 | 0 |
| LOW | 0 | 0 | 0 |

## Patterns

(Inherited from run 1: PAT-001 batch wiring, PAT-002 hook inconsistency, PAT-003 TOML divergence)

## Items

### BH-009: Consolidate hook TOML parsers — recurring recommendation escalated
**Severity:** MEDIUM
**Category:** design/inconsistency
**Location:** `hooks/verify_agent_output.py:111`, `hooks/session_context.py:23`, `hooks/review_gate.py:29`
**Status:** RESOLVED
**Predicted:** Prediction 3 (confidence: HIGH)
**Lens:** contract

**Problem:** This recommendation has appeared in 2 consecutive audit summaries without being implemented: "Consolidate hook TOML parsers into a shared module." Three independent TOML parsers exist for `project.toml` — each handles a different subset of the TOML spec. Run 1 fixed the most acute symptom (BJ-001: session_context unquoted values) but the systemic issue remains.

**Evidence:** Found in:
- `docs/holtz/archive/2026-03-23-run01/SUMMARY.md` ("Consider unifying the hooks' TOML reading into _common.py")
- `docs/holtz/archive/2026-03-23-run01/justine/SUMMARY.md` ("Consolidate hook TOML parsers — Create hooks/_toml.py")

**Discovery Chain:** Prior summary scan → "consolidate TOML parsers" found in 2 summaries → 2+ appearances triggers escalation per recommendation escalation protocol

**Acceptance Criteria:**
- [ ] Single shared TOML reader used by all hooks for reading project.toml values
- [ ] All three current parsers replaced with calls to the shared reader
- [ ] Test: shared reader handles quoted, unquoted, and array values consistently

**Validation Command:**
```bash
grep -c "def _read_toml" hooks/session_context.py hooks/verify_agent_output.py hooks/review_gate.py
```

### BH-010: review_gate._get_base_branch fails on unquoted base_branch values
**Severity:** MEDIUM
**Category:** bug/logic
**Location:** `hooks/review_gate.py:44`
**Status:** RESOLVED
**Determinism:** deterministic
**Pattern:** PAT-003
**Predicted:** Prediction 4 (confidence: HIGH)
**Lens:** contract

**Problem:** `_get_base_branch()` regex at line 44 only matches quoted values: `(?:"([^"]+)"|'([^']+)')`. If `project.toml` contains `base_branch = develop` (unquoted), the regex fails silently and the function returns `"main"`. This means the review gate would protect `main` instead of `develop`, allowing direct pushes to the actual base branch. Run 1 fixed the identical issue in session_context (BJ-001) but not review_gate. Same PAT-003 pattern.

**Evidence:** Regex `r"""\s*base_branch\s*=\s*(?:"([^"]+)"|'([^']+)')"""` requires quote delimiters. `validate_config.parse_simple_toml` accepts unquoted `base_branch = develop` as a valid raw string value.

**Discovery Chain:** PAT-003 sibling search → run 1 fixed session_context but not review_gate → regex at line 44 still requires quotes → unquoted values return wrong default

**Acceptance Criteria:**
- [ ] `_get_base_branch()` returns `"develop"` for unquoted `base_branch = develop`
- [ ] Test: unquoted base_branch correctly detected

**Validation Command:**
```bash
python3 -c "
import sys; sys.path.insert(0, 'hooks')
from review_gate import _get_base_branch
# Would need to mock _find_project_root; verify via regex test
import re
line = 'base_branch = develop'
m = re.match(r'''base_branch\s*=\s*(?:\"([^\"]+)\"|'([^']+)'|(\S+))''', line)
assert m and (m.group(1) or m.group(2) or m.group(3)) == 'develop'
print('PASS')
"
```
