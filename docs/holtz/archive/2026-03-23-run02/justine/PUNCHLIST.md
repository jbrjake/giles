# Justine Punchlist (Run 2)
> Generated: 2026-03-23 | Project: giles | Baseline: 1193 pass, 0 fail, 0 skip

## Summary
| Severity | Open | Resolved | Deferred |
|----------|------|----------|----------|
| CRITICAL | 0 | 0 | 0 |
| HIGH | 0 | 0 | 0 |
| MEDIUM | 1 | 0 | 0 |
| LOW | 1 | 0 | 0 |

## Patterns

(Inherited from run 1: PAT-001 batch wiring, PAT-002 hook inconsistency, PAT-003 TOML divergence)

## Items

### BJ-010: format_context has no truncation despite documented line count target
**Severity:** MEDIUM
**Category:** doc/drift
**Location:** `hooks/session_context.py:158`
**Status:** OPEN
**Predicted:** Prediction 1 (confidence: HIGH)
**Lens:** contract

**Problem:** `format_context()` docstring says "compact summary (<50 lines target)" but the function does no truncation. With 20 action items, 10 DoD additions, and 10 risks (the test input), output is 47 lines. With 50+30+20 items (realistic for a long-running project), output is 107 lines. The test at `tests/test_hooks.py:628-635` only validates the claim for its specific 40-item input, not the general contract. The function should either truncate to enforce the target or the docstring should be corrected to remove the claim.

**Evidence:** Direct reproduction:
```python
format_context([f"a{i}" for i in range(50)], [f"d{i}" for i in range(30)], [f"r{i}" for i in range(20)])
```
produces 107 lines, well above the 50-line target.

**Discovery Chain:** docstring claims <50 lines target -> function has no truncation code -> test uses input that happens to fit -> larger input exceeds target

**Acceptance Criteria:**
- [ ] Either add truncation logic (e.g., show top N items per section with "and M more") or update docstring to remove line count claim
- [ ] Test validates behavior with inputs that would exceed any stated limit

**Validation Command:**
```bash
python3 -c "from hooks.session_context import format_context; o = format_context([f'a{i}' for i in range(50)], [f'd{i}' for i in range(30)], [f'r{i}' for i in range(20)]); print(len(o.strip().splitlines()))"
```

### BJ-011: Compound command splitting in commit_gate and review_gate does not respect shell quoting
**Severity:** LOW
**Category:** design/inconsistency
**Location:** `hooks/commit_gate.py:137`, `hooks/review_gate.py:120`
**Status:** OPEN
**Determinism:** deterministic
**Predicted:** Prediction 2 (confidence: MEDIUM)
**Lens:** security

**Problem:** Both `check_commit_allowed` and `check_push` split compound commands using `re.split(r'\s*(?:&&|\|\||\||;)\s*', command)`, which does not respect shell quoting. A commit message like `git commit -m "fix: test && verify"` splits on the `&&` inside the quoted string, producing fragments. This does not create a security vulnerability because the split produces MORE subcommands (not fewer), and the hook checks each subcommand independently. The security direction is fail-closed: the gate might incorrectly block (false positive) but never incorrectly allow (false negative). The practical impact is nil because commit messages containing `&&` or `;` are rare, and the gate still correctly identifies the commit command in one of the fragments.

**Evidence:**
```python
check_commit_allowed('git commit -m "fix: test && verify"', _state_override=True)
# Returns "blocked" (correct result, even though split is technically wrong)
```

**Discovery Chain:** regex split has no quote awareness -> tested with operators inside quotes -> split produces fragments -> each fragment checked independently -> fail-closed behavior confirmed

**Acceptance Criteria:**
- [ ] Document the limitation in code comments (quoting not respected, but fail-closed)
- [ ] OR implement quote-aware splitting (complexity may not be worth it for this use case)

**Validation Command:**
```bash
python3 -c "from hooks.commit_gate import check_commit_allowed; r = check_commit_allowed('git commit -m \"fix: a && b\"', _state_override=True); assert r == 'blocked', f'Expected blocked, got {r}'; print('PASS: still blocks correctly')"
```
