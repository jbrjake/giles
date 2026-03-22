# Bug Hunter Punchlist — Pass 38

> Generated: 2026-03-21 | Project: giles | Baseline: 1182 pass, 0 fail, 83% coverage
> Focus: Clean-slate full audit after pass 37 converged + ruff cleanup

## Summary

| Severity | Open | Resolved | Closed |
|----------|------|----------|--------|
| HIGH     | 0    | 2        | 0      |
| MEDIUM   | 0    | 8        | 3      |
| LOW      | 0    | 9        | 7      |

---

## Open

None — all 26 items resolved or closed.

---

## Resolved

| ID | Title | Severity | Batch |
|----|-------|----------|-------|
| BH38-100 | Tautological assertion → assertIsInstance(output, str) | HIGH | 1 |
| BH38-006 | sync_backlog "lazy imports" → fixed docstring + CHEATSHEET | HIGH | 3 |
| BH38-200 | kanban.py sync → mkdir before lock_sprint | MEDIUM | 1 |
| BH38-201 | commit_gate → match all command tokens, not just first word | MEDIUM | 1 |
| BH38-206 | session_context separator → regex for alignment variants | MEDIUM | 1 |
| BH38-205 | sync_tracking → .upper() on all dict key accesses | MEDIUM | 1 |
| BH38-107 | Dead FakeGitHub() → removed | MEDIUM | 1 |
| BH38-106 | do_release assertTrue → assertIs(result, True) (5 sites) | MEDIUM | 2 |
| BH38-108 | Lock cleanup → added lock release verification test | MEDIUM | 2 |
| BH38-109 | Smoke error path → added nonexistent command test | LOW | 2 |
| BH38-001 | kanban-protocol.md WIP Note → all three limits code-enforced | MEDIUM | 3 |
| BH38-002 | CHEATSHEET check_integration_debt → "sprints since last smoke pass" | MEDIUM | 3 |
| BH38-003 | CHEATSHEET → added _most_common_sprint, _build_detail_block_re | LOW | 3 |
| BH38-004 | CLAUDE.md + CHEATSHEET → added atomic_write_text + safe_int + parse_iso_date | MEDIUM | 3 |
| BH38-005 | CLAUDE.md → added \UXXXXXXXX mention | LOW | 3 |

---

## Closed (won't fix)

| ID | Title | Severity | Reason |
|----|-------|----------|--------|
| BH38-101 | assertTrue(result) on bools (21 instances) | MEDIUM | Cross-cutting style change, pass 37 already upgraded the worst cases |
| BH38-102 | assertTrue(len(x) > 0) (15 instances) | LOW | Style improvement only, tests still correct |
| BH38-103 | Assertion-light lock tests | MEDIUM | Companion tests exist; new BH38-108 test closes the real gap |
| BH38-104 | 101 os.chdir calls | MEDIUM | Architectural — forced by hooks' CWD dependency |
| BH38-105 | Documented pipeline overlap | LOW | Intentional, well-documented |
| BH38-110 | Fragile exception test | LOW | Extremely unlikely ConfigError/SystemExit diamond |
| BH38-111 | Mock-heavy do_release | MEDIUM | Partially mitigated by TestDoReleaseIntegration |
| BH38-202 | verify_agent_output bracket depth | LOW | Arrays are flat in practice |
| BH38-203 | Unlocked tracking write | LOW | Timing makes concurrent write practically impossible |
| BH38-204 | review_gate path traversal | LOW | Attacker needs TOML control, writes benign log |
| BH38-207 | Triple stem collision | LOW | Extremely unlikely scenario |

---

## Pattern Blocks

### PATTERN-38-A: Doc/code semantic drift
**Items:** BH38-001, BH38-002, BH38-006
**Root cause:** Documentation describes historical behavior that was later changed without updating the prose. The code is correct; the docs are stale.
**Lesson:** When modifying code behavior (adding enforcement, changing import strategy), grep for the old behavior description in docs/docstrings.

### PATTERN-38-B: First-token matching
**Items:** BH38-201
**Root cause:** Command matching by extracting the first word loses specificity — `python -m pytest` becomes just `python`, matching any Python invocation.
**Lesson:** When matching structured commands, preserve structure. Match the full command prefix, not just the binary name.
