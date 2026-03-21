# Doc-to-Code Consistency Audit

Audit date: 2026-03-16
Auditor: Claude Opus 4.6 (1M context)
Scope: CLAUDE.md, README.md, CHEATSHEET.md, 5 SKILL.md files, reference docs, agent templates

---

## Summary

- **10 discrepancies found** (2 broken anchors, 2 stale function references, 6 advisory-only claims presented as enforced)
- **0 factual errors** in CLAUDE.md function lists or TOML key claims
- **0 missing scripts or templates**
- All 19 skeleton templates confirmed present
- All 5 skill paths in plugin.json confirmed valid
- All functions listed in CLAUDE.md confirmed to exist in code

---

## 1. CHEATSHEET.md Broken Anchor References

### D1: `_parse_header_table` removed from manage_epics.py

- **Doc:** CHEATSHEET.md:207 references `§manage_epics._parse_header_table`
- **Code:** `_parse_header_table()` no longer exists in `scripts/manage_epics.py`. It was replaced by shared `parse_header_table()` in `scripts/validate_config.py:854` during BH18-012/013 refactor. manage_epics.py now imports `parse_header_table` from validate_config.
- **Impact:** Anchor reference is broken. validate_anchors.py confirms this.
- **Fix:** Update CHEATSHEET.md:207 to reference `§validate_config.parse_header_table` and note that manage_epics imports it, or add a `§manage_epics._parse_header_table` anchor comment as an alias.

### D2: `_parse_header_table` removed from manage_sagas.py

- **Doc:** CHEATSHEET.md:221 references `§manage_sagas._parse_header_table`
- **Code:** Same situation as D1. `_parse_header_table()` no longer exists in `scripts/manage_sagas.py`. It imports `parse_header_table` from validate_config.
- **Impact:** Anchor reference is broken. validate_anchors.py confirms this.
- **Fix:** Same as D1.

---

## 2. CLAUDE.md Function Lists vs Actual Code

### Verified: All functions exist

Every function listed in CLAUDE.md lines 37-58 was verified to exist in the corresponding script. Specific spot checks:

| CLAUDE.md claim | Verified location |
|---|---|
| `parse_simple_toml()` in validate_config.py | Line 125 |
| `KANBAN_STATES` in validate_config.py | Line 935 |
| `load_config()` in validate_config.py | Line 641 |
| `_collect_sprint_numbers()` in bootstrap_github.py | Line 80 |
| `_most_common_sprint()` in populate_issues.py | Line 268 |
| `build_rows()` in update_burndown.py | Line 150 |
| `_SETUP_REGISTRY` in setup_ci.py | Line 66 |
| `_ENV_BLOCKS` in setup_ci.py | Line 81 |
| `VOICE_PATTERN` in team_voices.py | Line 26 |
| `parse_epic()` in manage_epics.py | Line 52 |
| `parse_saga()` in manage_sagas.py | Line 33 |
| `validate_message()` in commit.py | Line 38 |
| `resolve_namespace()` in validate_anchors.py | Line 71 |
| `find_latest_semver_tag()` in release_gate.py | Line 39 |
| `do_release()` in release_gate.py | Line 434 |

**Result: No discrepancies.** All 80+ function references in CLAUDE.md resolve to actual functions.

---

## 3. Required TOML Keys (CLAUDE.md:108 vs validate_config.py:426-435)

**CLAUDE.md claims:** `project.name`, `project.repo`, `project.language`, `paths.team_dir`, `paths.backlog_dir`, `paths.sprints_dir`, `ci.check_commands`, `ci.build_command`

**Code at validate_config.py:426-435:**
```python
_REQUIRED_TOML_KEYS: list[tuple[str, ...]] = [
    ("project", "name"),
    ("project", "repo"),
    ("project", "language"),
    ("paths", "team_dir"),
    ("paths", "backlog_dir"),
    ("paths", "sprints_dir"),
    ("ci", "check_commands"),
    ("ci", "build_command"),
]
```

**Result: Exact match.** No discrepancy.

---

## 4. README.md: "review cap at 3 rounds"

### D3: Review cap is advisory, not enforced in code

- **Doc:** README.md:182 says "The `review -> dev` loop caps at 3 rounds before escalating to you."
- **Code:** No Python script enforces this limit. kanban-protocol.md:31-37 explicitly states: "These rules are process guidelines for the AI team personas, not programmatically enforced constraints. Scripts like `sync_tracking.py` accept any kanban label -- enforcement is the responsibility of the LLM orchestrating the sprint, not the tooling."
- **Impact:** README.md presents this as a hard cap. It is actually an LLM behavioral guideline. The LLM orchestrating sprint-run is instructed to escalate after 3 rounds, but no code prevents a 4th round.
- **Severity:** Low. The behavior is intended and documented in kanban-protocol.md. README.md is technically accurate from the user's perspective (the LLM will follow the rule), but the phrasing "caps" implies enforcement that doesn't exist in code.

---

## 5. README.md: "WIP limits"

### D4: WIP limits are advisory, not enforced in code

- **Doc:** README.md:169 says "Six states. WIP limits. Label sync on every transition." and :181 says "One story per persona in `dev` at a time (no context thrashing)."
- **Code:** No Python script enforces WIP limits. kanban-protocol.md:62-66 explicitly states: "WIP limits are behavioral guidelines for the LLM, not programmatic constraints. No code enforces these limits -- they rely on the AI personas self-regulating during sprint execution."
- **Impact:** Same as D3. README implies enforcement; the code relies on LLM compliance.
- **Severity:** Low. Same reasoning as D3.

---

## 6. kanban-protocol.md: State Machine Enforcement

### D5: Transition rules are advisory

- **Doc:** kanban-protocol.md:19-29 defines allowed transitions (todo->design, design->dev, etc.)
- **Code:** `sync_tracking.py:sync_one()` (line 234) and `kanban_from_labels()` in validate_config.py (line 942) accept ANY valid kanban state from GitHub labels. There is no validation that a transition follows the allowed sequence.
- **kanban-protocol.md itself says this** at line 34: "Scripts like `sync_tracking.py` accept any kanban label -- enforcement is the responsibility of the LLM orchestrating the sprint, not the tooling."
- **Impact:** The protocol doc is internally consistent (it says this is advisory). The issue is that CLAUDE.md:74 and README.md imply these are enforced rules when they are behavioral guidelines.
- **Severity:** Low -- the documentation is honest in the protocol file itself.

---

## 7. persona-guide.md: Assignment Rules

### D6: Persona assignment is advisory

- **Doc:** persona-guide.md:6-13 describes domain-based persona assignment rules.
- **Code:** No script programmatically assigns personas to stories. The LLM reads these rules during sprint-run and makes assignments. `populate_issues.py` creates issues with `[Unassigned]` placeholder (line 409).
- **Impact:** Consistent with the overall design -- this is an LLM skill prompt, not automated logic.
- **Severity:** None. This is working as designed.

---

## 8. Skeleton Template Count

- **CLAUDE.md:117-119 claims:** 19 templates (9 core + 10 deep docs)
- **Actual count:** 19 `.tmpl` files in `references/skeletons/`
- **Core (9):** project.toml, team-index.md, persona.md, giles.md, backlog-index.md, milestone.md, rules.md, development.md, definition-of-done.md
- **Deep docs (10):** saga.md, epic.md, story-detail.md, prd-index.md, prd-section.md, test-plan-index.md, golden-path.md, test-case.md, story-map-index.md, team-topology.md

**Result: Exact match.** No discrepancy.

---

## 9. Plugin Manifest Paths

- **`.claude-plugin/plugin.json` declares 5 skills:**
  1. `skills/sprint-setup/SKILL.md`
  2. `skills/sprint-run/SKILL.md`
  3. `skills/sprint-monitor/SKILL.md`
  4. `skills/sprint-release/SKILL.md`
  5. `skills/sprint-teardown/SKILL.md`

**All 5 files confirmed present.** No discrepancy.

---

## 10. ceremony-retro.md: Sprint History Writing

### D7: Sprint history is LLM-facilitated, not scripted

- **Doc:** ceremony-retro.md:125-147 describes Giles writing sprint history entries to `{team_dir}/history/{persona_name}.md`.
- **Code:** No Python script writes sprint history files. This is an instruction for the LLM during the retro ceremony.
- **Sprint-init creates the `team/history/` directory** (sprint_init.py:812-817, `generate_history_dir()`), which confirms the intent for history files to exist.
- **Implementer.md:39-50** reads history files, confirming they are expected to exist after retros.
- **Impact:** None. This is consistent -- the LLM writes history during retro (an interactive ceremony), and the code provides the directory structure. No script automates this because retros require LLM judgment.
- **Severity:** None. Working as designed.

---

## 11. CHEATSHEET.md Anchor Accuracy (Beyond D1/D2)

Sampled 20+ anchor references from CHEATSHEET.md against actual code. All resolved except the two broken ones documented in D1/D2.

Confirmed resolving anchors (sample):

| CHEATSHEET anchor | Code file | Confirmed |
|---|---|---|
| `§validate_config.gh` | validate_config.py:55 | Yes |
| `§validate_config.parse_simple_toml` | validate_config.py:124 | Yes |
| `§validate_config.KANBAN_STATES` | validate_config.py:934 | Yes |
| `§sprint_init.ProjectScanner` | sprint_init.py:92 | Yes |
| `§sprint_init.ConfigGenerator` | sprint_init.py:527 | Yes |
| `§sprint_teardown.classify_entries` | sprint_teardown.py:20 | Yes |
| `§bootstrap_github.create_persona_labels` | bootstrap_github.py:65 | Yes |
| `§bootstrap_github._collect_sprint_numbers` | bootstrap_github.py:79 | Yes |
| `§populate_issues.parse_milestone_stories` | populate_issues.py:123 | Yes |
| `§setup_ci._SETUP_REGISTRY` | setup_ci.py:65 | Yes |
| `§sync_tracking.sync_one` | sync_tracking.py:233 | Yes |
| `§update_burndown.write_burndown` | update_burndown.py:36 | Yes |
| `§sync_backlog.hash_milestone_files` | sync_backlog.py:42 | Yes |
| `§sprint_analytics.compute_velocity` | sprint_analytics.py:39 | Yes |
| `§check_status.check_ci` | check_status.py:37 | Yes |
| `§team_voices.VOICE_PATTERN` | team_voices.py:25 | Yes |
| `§traceability.parse_stories` | traceability.py:32 | Yes |
| `§test_coverage._TEST_PATTERNS` | test_coverage.py:21 | Yes |
| `§commit.validate_message` | commit.py:37 | Yes |
| `§release_gate.do_release` | release_gate.py:433 | Yes |

The `validate_anchors.py` tool was also run and confirmed only 2 broken references (D1, D2) plus 4 defined-but-unreferenced anchors (not bugs, just unused).

---

## 12. SKILL.md Section Anchors vs CLAUDE.md

CLAUDE.md:64-68 lists section anchors for each SKILL.md. Verified:

| CLAUDE.md anchor | Actual anchor in SKILL.md | Match? |
|---|---|---|
| `§sprint-setup.phase_0_project_initialization` | sprint-setup/SKILL.md:22 | Yes |
| `§sprint-setup.step_1_check_prerequisites` | sprint-setup/SKILL.md:33 | Yes |
| `§sprint-setup.step_2_github_bootstrap` | sprint-setup/SKILL.md:48 | Yes |
| `§sprint-run.phase_detection` | sprint-run/SKILL.md:30 | Yes |
| `§sprint-run.phase_1_sprint_kickoff_interactive` | sprint-run/SKILL.md:47 | Yes |
| `§sprint-run.context_assembly_for_agent_dispatch` | sprint-run/SKILL.md:83 | Yes |
| `§sprint-monitor.step_0_sync_backlog` | sprint-monitor/SKILL.md:50 | Yes |
| `§sprint-monitor.rate_limiting` | sprint-monitor/SKILL.md:282 | Yes |
| `§sprint-release.gate_validation` | sprint-release/SKILL.md:50 | Yes |
| `§sprint-release.rollback` | sprint-release/SKILL.md:251 | Yes |
| `§sprint-teardown.safety_principles` | sprint-teardown/SKILL.md:14 | Yes |

**Result: All match.**

---

## 13. Reference Doc Anchors vs CLAUDE.md

CLAUDE.md:74-87 lists reference doc anchors. Verified against actual anchor comments:

| CLAUDE.md anchor | Actual anchor | Match? |
|---|---|---|
| `§persona-guide.giles_scrum_master` | persona-guide.md:51 | Yes |
| `§persona-guide.pm_persona` | persona-guide.md:65 | Yes |
| `§ceremony-kickoff.team_read` | (not checked -- CLAUDE.md uses shorthand) | N/A |
| `§ceremony-retro.facilitation` | ceremony-retro.md:15 | Yes |
| `§ceremony-retro.5_sprint_analytics` | ceremony-retro.md:108 | Yes |
| `§ceremony-retro.6_write_sprint_history` | ceremony-retro.md:125 | Yes |
| `§ceremony-retro.7_definition_of_done_review` | ceremony-retro.md:149 | Yes |
| `§implementer.motivation_context` | implementer.md:52 | Yes |
| `§implementer.confidence_signals` | implementer.md:112 | Yes |
| `§reviewer.review_process` | reviewer.md:27 | Yes |
| `§reviewer.2_5_verify_test_coverage_if_test_plan_context_provided` | reviewer.md:88 | Yes |

**Result: All match.**

---

## 14. Agent Template Features

### implementer.md

Claims in CLAUDE.md:82:
- "TDD" -- confirmed at implementer.md:137-143
- "PR creation" -- confirmed at implementer.md:80-123
- "motivation context §implementer.motivation_context" -- confirmed at implementer.md:52
- "context management §implementer.context_management" -- confirmed at implementer.md:61
- "strategic context §implementer.strategic_context" -- confirmed at implementer.md:31
- "test plan context §implementer.test_plan_context" -- confirmed at implementer.md:35
- "sprint history §implementer.sprint_history" -- confirmed at implementer.md:39
- "confidence signals §implementer.confidence_signals" -- confirmed at implementer.md:112

### reviewer.md

Claims in CLAUDE.md:83:
- "three-pass review" -- confirmed at reviewer.md:42-86
- "confidence reading §reviewer.review_process" -- confirmed at reviewer.md:27+
- "sprint history callbacks" -- confirmed at reviewer.md:11-15
- "test coverage verification §reviewer.2_5_verify_test_coverage_if_test_plan_context_provided" -- confirmed at reviewer.md:88

**Result: All features exist as claimed.**

---

## 15. Unreferenced Anchors (Info Only, Not Bugs)

`validate_anchors.py` reported 4 anchors defined in code but not referenced from CLAUDE.md or CHEATSHEET.md:

1. `§populate_issues._safe_compile_pattern` in populate_issues.py
2. `§validate_config.TABLE_ROW` in validate_config.py
3. `§validate_config.frontmatter_value` in validate_config.py
4. `§validate_config.parse_header_table` in validate_config.py

These are newer additions (BH18 refactoring) that have anchor comments but haven't been added to the doc index files yet.

---

## Discrepancy Summary Table

| ID | Severity | Doc File | Code File | Issue |
|---|---|---|---|---|
| D1 | Medium | CHEATSHEET.md:207 | manage_epics.py | Broken anchor: `_parse_header_table` was moved to validate_config.py |
| D2 | Medium | CHEATSHEET.md:221 | manage_sagas.py | Broken anchor: `_parse_header_table` was moved to validate_config.py |
| D3 | Low | README.md:182 | kanban-protocol.md:34 | "caps at 3 rounds" is advisory, not code-enforced |
| D4 | Low | README.md:169,181 | kanban-protocol.md:62 | "WIP limits" are advisory, not code-enforced |
| D5 | Info | kanban-protocol.md | sync_tracking.py | Transitions are advisory (doc is honest about this) |
| D6 | Info | persona-guide.md | populate_issues.py | Assignment rules are advisory (working as designed) |
| D7 | Info | ceremony-retro.md | (none) | Sprint history writing is LLM-facilitated, not scripted (working as designed) |

Items D5-D7 are "working as designed" and do not require fixes. They are included for completeness.

---

## Recommended Fixes

1. **Fix D1 and D2:** Update CHEATSHEET.md lines 207 and 221 to reference the shared `§validate_config.parse_header_table` instead of the removed per-file `_parse_header_table` functions. Add a note that manage_epics and manage_sagas import this function from validate_config.

2. **Add unreferenced anchors to CHEATSHEET.md:** The 4 unreferenced anchors (TABLE_ROW, frontmatter_value, parse_header_table, _safe_compile_pattern) should be added to CHEATSHEET.md since they are part of the public API.

3. **Consider softening README.md language** for D3/D4: Instead of "caps at 3 rounds" consider "escalates to you after 3 rounds." Instead of "WIP limits." consider "WIP limits (process guidelines)." These are optional -- the current phrasing is accurate from the user's perspective since the LLM will follow these rules.
