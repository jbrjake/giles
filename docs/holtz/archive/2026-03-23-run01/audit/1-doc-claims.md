# Phase 1: Doc-to-Implementation Claims Checklist

## CLAUDE.md Claims (prioritized by prediction confidence)

### HIGH confidence predictions (verified first)

- [x] **CLAIM: §-anchors exist for all scripts listed in CLAUDE.md** → FAIL
  - 6 scripts have anchors in source but NAMESPACE_MAP missing entries → BH-001
- [x] **CLAIM: Makefile lint covers all production scripts** → FAIL
  - 7 scripts missing from py_compile list → BH-002
- [x] **CLAIM: Plugin Structure accurately reflects directory layout** → FAIL
  - `hooks/` directory and `hooks.json` not mentioned at all → BH-003

### MEDIUM confidence predictions (verified second)

- [x] **CLAIM: "5 skills, each with SKILL.md entry point"** → PASS (5 SKILL.md files found)
- [x] **CLAIM: "20 templates" (9 core + 11 deep docs)** → PASS (20 .tmpl files, count matches)
- [x] **CLAIM: Skill scripts use sys.path.insert 4 dirs up** → PASS (all 7 skill scripts verified)
- [x] **CLAIM: Top-level scripts use single-level parent path** → PASS (16 scripts verified)
- [x] **CLAIM: Required TOML keys match code** → PASS (_REQUIRED_TOML_KEYS matches doc exactly)
- [x] **CLAIM: "6 states" kanban** → PASS (KANBAN_STATES = todo, design, dev, review, integration, done)
- [x] **CLAIM: validate_config.load_config() single entry point** → PASS (all scripts use it)
- [x] **CLAIM: Idempotent scripts** → PASS (documented, verified in bootstrap_github, populate_issues)
- [x] **CLAIM: Cross-skill dependency sync_backlog** → PASS (imports bootstrap_github, populate_issues)
- [x] **CLAIM: Custom TOML parser, no tomllib** → PASS (parse_simple_toml in validate_config.py)
- [x] **CLAIM: Symlink-based config** → PASS (documented, tested in test_sprint_runtime)
- [x] **CLAIM: Two-path state management** → PASS (kanban.py + sync_tracking.py documented)

### Unchecked (lower priority)

- [ ] Template file names match CLAUDE.md's core/deep-docs lists
- [ ] Reference files all exist at documented paths
- [ ] evals/evals.json has valid scenarios

## Summary

3 FAIL / 12 PASS = 80% doc accuracy. All failures are in the "recently changed" category — hooks refactor + batch script additions.
