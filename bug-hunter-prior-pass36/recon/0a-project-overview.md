# Pass 36 — Phase 0a: Project Overview

> Baseline: pass 35, commits 8852009..d8d2185 (4 commits, 10 Python files changed)
> Test baseline (pass 35 exit): 1178 pass, 0 fail

## Commit Range

| Commit | Description |
|--------|-------------|
| 7e07bc5 | fix: HIGH items BH35-001..003, BH35-021, BH35-022 |
| 6ea4eef | fix: MEDIUM items — hooks hardening, release_gate, sprint_init |
| debe769 | fix: remaining MEDIUM/LOW — persona collision, saga/epic fields, regex align |
| d8d2185 | chore: recon reports, punchlist, status |

## Files Modified (Regression Risk Targets)

| File | Lines changed | What changed |
|------|--------------|--------------|
| `scripts/kanban.py` | -43/+34 | All mutations switched from `lock_story` to `lock_sprint` (BH35-001/004) |
| `scripts/sprint_init.py` | +40 | Re-run protections: exclude sprint-config/ from scans, DoD preservation, milestones skeleton for empty backlog, YAML block scalar variants, detect_prd_dir crash guard, binary_path TOML escaping, persona stem collision disambiguation |
| `.claude-plugin/hooks/review_gate.py` | +33/-8 | Push parser: +refspec, refs/heads/, --repo bypass, pipe split, TOML parser fixes (split/section-comment/single-quote) |
| `.claude-plugin/hooks/commit_gate.py` | +4/-1 | Word boundary on check_command matching |
| `.claude-plugin/hooks/session_context.py` | +6 | TOML parser: split('\n'), section comment stripping |
| `.claude-plugin/hooks/verify_agent_output.py` | +12 | TOML parser: split('\n'), section comment, multiline array comment stripping, \bcommitted\b word boundary |
| `scripts/manage_epics.py` | +9 | Saga/Epic fields in story sections, `\s+` regex alignment |
| `skills/sprint-release/scripts/release_gate.py` | +20 | gate_ci workflow filter, write_version_to_toml single-quote and EOF fixes |
| `tests/test_hooks.py` | +109 (new) | Tests for push bypass vectors |
| `tests/test_verify_fixes.py` | +78 (new) | Tests for BH35 fix verification |

## Key Patterns Applied in Pass 35

### PATTERN-A: Lock unification (kanban.py)
All three mutation paths (`transition`, `assign`, `update`) now use `lock_sprint` instead of mixed `lock_story`/`lock_sprint`. This eliminates the cross-lock-file race with `sync_tracking.py`.

**Audit risk:** The `lock_story` function is now unused from `main()`. Is it still used elsewhere? Is there dead code? Did the lock scope change cause any new contention issues (all mutations now serialize against the same sprint-level lock)?

### PATTERN-B: TOML parser propagation to hooks
Three fixes propagated to all 4 hook inline parsers:
1. `split('\n')` instead of `splitlines()` (BH20-001 parity)
2. Section header comment stripping: `stripped.split('#')[0].strip()`
3. Single-quote support for `base_branch`

**Audit risk:** The comment-stripping approach `s.split('#')[0]` is naive — it would break on `key = "value # with hash"`. The main parser handles this correctly; the hook parsers do not. Check if any TOML values in project.toml could legitimately contain `#`.

### PATTERN-C: Push parser hardening (review_gate.py)
- Checks ALL positionals (not just [1:]) against base branch
- Strips `+` prefix and `refs/heads/` from refspecs before comparison
- Splits on `|` (single pipe) in addition to `&&`, `||`, `;`

**Audit risk:** Checking ALL positionals means the remote name itself is checked against base. If remote is named "main" (unusual but valid), any push would be blocked. Also: does `|` splitting cause false positives on commands that pipe non-push output?

### PATTERN-D: sprint_init re-run protections
- DoD preserved if file already exists
- milestones/ skeleton created for empty backlog
- sprint-config/ excluded from project scans
- Persona stem collision disambiguation with parent dir prefix

**Audit risk:** The stem collision logic uses `parent.name` — what if two personas have the same stem AND the same parent dir name? Also verify the milestones skeleton doesn't cause downstream issues (populate_issues seeing template content).

### PATTERN-E: release_gate hardening
- `gate_ci` filters by workflow name if `ci.workflow` configured
- `write_version_to_toml` handles single-quoted values and EOF without newline

**Audit risk:** The `ci.workflow` key is new — not in `_REQUIRED_TOML_KEYS` (correctly optional), but is it documented anywhere? Also verify the EOF fix doesn't double-newline in the normal case.

## What to Audit in Pass 36

### 1. Fix verification
- Confirm each BH35 fix actually works as described (not just that tests pass)
- Check for off-by-one or edge cases in the new code paths

### 2. Sibling search
- `lock_story` usage: is it now dead code in kanban.py? Any other callers?
- `split('#')[0]` in hook TOML parsers: does the main parser do this too, or differently?
- `\s+` vs `\s*` regex alignment: manage_epics changed to `\s+`, did all siblings?
- `_esc()` method used for binary_path: are there other TOML value writes that don't escape?
- Pipe splitting in review_gate: does commit_gate also need it?

### 3. Convergence check
- Are the 4 hook inline TOML parsers now truly converged, or do differences remain?
- Is `lock_story` still called anywhere, or is it dead code that should be removed?
- Are there other `positional[1:]` patterns in the codebase that should be `positional`?

### 4. New test quality
- test_hooks.py and test_verify_fixes.py are new — check they test the right things and aren't tautological
- Check for missing negative test cases (e.g., "main" as remote name)

### 5. Under-scrutinized files
- `scripts/manage_epics.py` got a small change — has it been fully audited before?
- `skills/sprint-release/scripts/release_gate.py` has accumulated fixes across many passes — check for interaction effects
