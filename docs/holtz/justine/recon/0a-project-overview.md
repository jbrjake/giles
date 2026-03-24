# 0a: Project Overview (Run 6 — Focused)

**Scope:** Run 6 is a focused audit on new code since run 5:
- `scripts/check_lint_inventory.py` (82 LOC) — new script
- `tests/test_check_lint_inventory.py` (124 LOC) — new test file
- Minor 1-line change in `scripts/validate_anchors.py`
- Makefile additions (2 lines)
- CHEATSHEET.md and CLAUDE.md updates

**Architecture context:** check_lint_inventory.py is standalone (no imports from validate_config). Fits Layer 3 in architecture baseline. Already added to baseline drift log.

**Purpose:** Prevents PAT-001 drift by automating the check that all .py scripts appear in Makefile lint targets.

**Integration points:**
1. Called by `make lint` (line 63)
2. `main()` hardcodes root as `Path(__file__).resolve().parent.parent` — assumes script lives in `scripts/`
3. Uses regex `py_compile\s+(\S+\.py)` to extract lint entries from Makefile
4. Uses `rglob("*.py")` for disk scanning
