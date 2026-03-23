# Step 0d: Lint Results

**Date:** 2026-03-23
**Command:** `make lint` (py_compile for all 19 scripts + validate_anchors.py)

## py_compile: PASS

All 19 production scripts compile without syntax errors.

## validate_anchors: 21 BROKEN REFERENCES

All broken references are in CLAUDE.md, referencing anchors in scripts that lack `§`-prefixed anchor definitions:

| Broken Namespace | Affected Scripts | Count |
|------------------|-----------------|-------|
| `smoke_test` | scripts/smoke_test.py | 3 refs |
| `gap_scanner` | scripts/gap_scanner.py | 3 refs |
| `test_categories` | scripts/test_categories.py | 4 refs |
| `risk_register` | scripts/risk_register.py | 5 refs |
| `assign_dod_level` | scripts/assign_dod_level.py | 3 refs |
| `history_to_checklist` | scripts/history_to_checklist.py | 3 refs |

**Root cause:** These 6 scripts were added but never received `§`-prefixed anchor comments in their source code that validate_anchors.py looks for.

## validate_anchors: 18 UNREFERENCED ANCHORS (info)

18 anchors are defined but never referenced from CLAUDE.md or CHEATSHEET.md. These are in:
- ceremony-demo.md (1)
- ceremony-kickoff.md (2)
- ceremony-retro.md (4)
- implementer.md (4)
- kanban-protocol.md (1)
- kanban.py (2)
- sprint-run SKILL.md (2)
- tracking-formats.md (2)

These are informational — anchors exist for potential future reference.

## ruff: NOT INSTALLED

ruff.toml exists but ruff is not in the venv. Config selects E+F rules, ignores E402/E501/E741.
