# 0g: Recon Summary (Run 5)

**Project:** giles — Claude Code agile sprint plugin
**Baseline:** 1224 tests, 0 failures, 17.37s
**Prior runs:** 4 (22 findings resolved total)
**Impact graph:** 31 nodes, 35 edges, no drift

## Key Observations

1. **Mature, heavily-tested codebase.** 4 prior Holtz runs + 39 bug-hunter passes. Test-to-production ratio is ~1.8:1 by LOC. Hard to find surface bugs.

2. **Hooks remain highest-churn subsystem.** 4 hook files accumulated 21 changes in 50 commits. Most prior findings clustered here. The TOML consolidation (runs 2-3) addressed the main defects, but churn suggests continued evolution.

3. **Large, complex scripts.** validate_config.py (1247 LOC) and sprint_init.py (1027 LOC) are the two largest files. kanban.py (826 LOC) has complex state machine logic. These are where deep bugs hide.

4. **Global pattern detection:**
   - **Code-fence-unaware-parsing:** Multiple regex patterns applied to `content`/`body`/`text` variables without fence masking. Targets: populate_issues.py, update_burndown.py, bootstrap_github.py, check_status.py, release_gate.py.
   - **Regex-newline-leak:** `\s*` / `\s+` in many regexes applied to multi-line input. Most are in line-by-line contexts (safe), but some operate on full text (e.g., `extract_sp`, `read_tf`, populate_issues body parsing).
   - **Dual-parser-divergence:** After 3 runs of consolidation, the hooks/scripts TOML parsers should be aligned. However, there are still multiple `parse_*` and `extract_*` functions for the same data — need to verify they agree.

5. **Custom lenses found issues that 3 prior standard runs missed.** semantic-fidelity and temporal-protocol must be applied throughout this run.

6. **Recommendation escalation:** No recommendations appeared in 2+ prior summaries. Skipped.

## Risk Areas for This Run

1. **populate_issues.py** (565 LOC) — heavy regex, parses markdown with code blocks, high code-fence risk
2. **release_gate.py** (776 LOC) — TOML parsing, version calculation, gate logic
3. **check_status.py** (616 LOC) — CI output parsing, pattern matching against arbitrary output
4. **sprint_init.py** (1027 LOC) — project scanning, config generation, many heuristics
5. **validate_config.py** (1247 LOC) — foundation. Any bug here propagates everywhere.
6. **kanban.py** (826 LOC) — state machine. Run 4 found semantic-fidelity issues.
