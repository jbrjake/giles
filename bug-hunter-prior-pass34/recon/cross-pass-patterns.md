# Cross-Pass Pattern Analysis

> Generated: 2026-03-20 | Sources: Pass 25, Pass 26, Pass 27 punchlists + 4 recon audits
> Method: Finding deduplication, fix verification against current code, gap cross-reference

---

## Component Boundary Map

The system has five major component boundaries where bugs cluster.
Listed by density of findings (most problematic first).

### 1. Hooks <-> Config System (11 findings)

The hooks (commit_gate, review_gate, verify_agent_output, session_context)
cannot import validate_config.py due to plugin process isolation. Each hook
reimplements a subset of TOML parsing with different capabilities.

| Finding | Source | Status | Issue |
|---------|--------|--------|-------|
| BH25-002 | Pass 25 | FIXED | `_read_toml_key` multi-line arrays |
| BH25-005 | Pass 25 | FIXED | commit_gate hardcoded patterns -> now reads config |
| BH26-001 | Pass 26 | OPEN | verify_agent_output tracking path never resolves against sprints_dir |
| BH26-005 | Pass 26 | OPEN | `_has_unquoted_bracket`/`_strip_inline_comment` ignore backslash-escaped quotes |
| BH27-002 | Pass 27 | FIXED | session_context paths now resolved against project root |
| BH27-004 | Pass 27 | FIXED | commit_gate now reads config + keeps hardcoded fallback |
| hooks-audit FINDING-4 | Recon | OPEN | session_context `_read_toml_string` only handles double quotes |
| hooks-audit FINDING-6 | Recon | FIXED | commit_gate now reads config |
| hooks-audit FINDING-7 | Recon | OPEN | review_gate `_log_blocked` writes to hardcoded sprints path |
| hooks-audit FINDING-10 | Recon | OPEN | session_context doesn't handle subsections (low risk) |
| PAT-27-002 | Pass 27 | STRUCTURAL | Each hook has its own config reader with different capabilities |

**Current state:** The most severe config issues (BH25-005, BH27-002, BH27-004) are fixed.
The structural problem remains: four independent TOML parsers with divergent capabilities.
`session_context._read_toml_string` is the weakest (double-quotes only, no escape handling).
`verify_agent_output._read_toml_key` is the strongest but still has the escaped-quote bracket
bug (BH26-005). The main parser in `validate_config.parse_simple_toml` handles all cases.

### 2. Hooks <-> Hooks (5 findings)

The hooks run as independent processes with no shared state beyond the filesystem.

| Finding | Source | Status | Issue |
|---------|--------|--------|-------|
| BH27-001 | Pass 27 | FIXED | commit_gate PreToolUse timing -> PostToolUse hook added |
| BH27-003 | Pass 27 | FIXED | verify_agent_output now bridges to commit_gate.mark_verified() |
| hooks-audit FINDING-1 | Recon | FIXED | Same as BH27-001 |
| hooks-audit FINDING-3 | Recon | FIXED | Same as BH27-003 |
| hooks-audit FINDING-11 | Recon | LIKELY OK | Two PreToolUse/Bash hooks share stdin — separate processes |

**Current state:** The critical hook isolation issues are resolved. `commit_gate.py`
now has both `main()` (PreToolUse, blocking only) and `post_main()` (PostToolUse, state
recording). `verify_agent_output.py` bridges to `commit_gate.mark_verified()` at line 201.
Plugin.json has the PostToolUse registration at line 33-37.

### 3. Kanban <-> Sync Tracking (7 findings)

Two code paths manage the same tracking files with different locking, atomicity,
and validation strategies.

| Finding | Source | Status | Issue |
|---------|--------|--------|-------|
| integration-audit FINDING-1 | Recon | FIXED | sync_tracking now uses lock_sprint (line 279) |
| integration-audit FINDING-2 | Recon | FIXED | sync_tracking now uses atomic_write_tf (lines 288, 294) |
| integration-audit FINDING-3 | Recon | OPEN | kanban do_sync reads all files upfront without per-story locks (within lock_sprint) |
| integration-audit FINDING-4 | Recon | OPEN | sync_tracking accepts any state; kanban validates transitions |
| integration-audit FINDING-7 | Recon | OPEN | Two sync paths create TFs with different body content |
| integration-audit FINDING-9 | Recon | FIXED | sync_tracking now normalizes to uppercase (line 262) |
| BH26-002 | Pass 26 | FIXED | sync_one now called under lock_sprint |

**Current state:** The locking gap (FINDING-1) and atomicity gap (FINDING-2) are the
two most important fixes and both are done. The remaining semantic divergences
(FINDING-4: transition validation policy, FINDING-7: body content differences) are
real but lower severity — they create inconsistency, not corruption.

### 4. Scripts <-> Kanban Locking Discipline (6 findings)

Scripts that write tracking files or sprint-config files outside the kanban
locking/atomicity pattern.

| Finding | Source | Status | Issue |
|---------|--------|--------|-------|
| BH25-003 | Pass 25 | OPEN | assign_dod_level.py writes TF without file locking |
| BH25-006 | Pass 25 | OPEN | verify_agent_output update_tracking_verification bypasses write_tf |
| scripts-audit FINDING-44 | Recon | OPEN | 5 scripts use non-atomic Path.write_text() |
| scripts-audit FINDING-45 | Recon | OPEN | manage_epics.py and manage_sagas.py have no file locking |
| PAT-25-002 | Pass 25 | STRUCTURAL | New code doesn't follow kanban locking pattern |
| PAT-27-003 | Pass 27 | STRUCTURAL | Scripts lack locking/atomicity discipline |

**Current state:** The kanban core is well-locked. Everything around it is not.
`assign_dod_level.py` does acquire a lock (scripts-audit FINDING-32 confirms it
re-reads under lock), but the `classify_story()` call still happens pre-lock.
`manage_epics.py`, `manage_sagas.py`, and `risk_register.py` have zero locking.

### 5. GitHub API <-> Local State (4 findings)

Partial failure during multi-step GitHub API calls leaves state split between
local files and GitHub.

| Finding | Source | Status | Issue |
|---------|--------|--------|-------|
| integration-audit FINDING-5 | Recon | OPEN | done transition: label swap + close — partial failure leaves stale label |
| integration-audit FINDING-11 | Recon | OPEN | Rollback doesn't reverse GitHub label changes |
| integration-audit FINDING-10 | Recon | OPEN | sync_backlog marks complete even on partial issue creation failure |
| integration-audit FINDING-6 | Recon | OPEN | sync_backlog import error swallowed |

**Current state:** These are all still open. The `done` transition partial-failure
scenario (FINDING-5/11) is the most likely to hit users in practice. It requires
a specific failure mode (label succeeds, close fails), but when it happens, the
divergent state propagates through subsequent syncs.

---

## Recurring Bug Classes

### CLASS-1: Parser Divergence (7 instances)

The most prolific bug class. Every time a component needs to read TOML config,
it reimplements parsing with different capabilities.

| Instance | Component | What diverges |
|----------|-----------|---------------|
| BH25-002 | verify_agent_output | Multi-line arrays (FIXED) |
| BH26-005 | verify_agent_output | Backslash-escaped quotes in bracket detection |
| hooks-audit FINDING-4 | session_context | Single-quoted strings not supported |
| hooks-audit FINDING-10 | session_context | Subsections not handled |
| BH27-004 | commit_gate | Config-based commands (FIXED, now reads config) |
| scripts-audit FINDING-40 | test_categories | Rust `#[test]` counting vs fn definitions |
| BH27-007 | test_coverage | Rust `#[test]\s*fn` doesn't span newlines |

Root cause: The stdlib-only constraint means hooks can't import `validate_config.py`.
Each hook builds its own mini-parser. The parsers diverge because they're tested
against different inputs.

Systemic fix needed: Extract a shared `_toml_helpers.py` into the hooks directory
that all hooks import. It doesn't need to be the full `parse_simple_toml` — just
the subset needed for hooks (string/array reading, path resolution).

### CLASS-2: Lock Scope Mismatch / Missing Locks (8 instances)

Code that mutates shared files without proper lock acquisition.

| Instance | Component | Issue |
|----------|-----------|-------|
| BH25-003 | assign_dod_level | Writes TF with partial lock coverage |
| BH25-006 | verify_agent_output | Writes tracking YAML outside any lock |
| BH26-002 | sync_tracking | Modifies TF in memory before lock (FIXED — now under lock_sprint) |
| integration-audit FINDING-3 | kanban do_sync | Reads all files at start, no per-story lock |
| scripts-audit FINDING-44 | 5 scripts | Non-atomic write_text() |
| scripts-audit FINDING-45 | manage_epics, manage_sagas | Zero file locking |
| scripts-audit FINDING-6 | smoke_test | write_history appends without locking |
| scripts-audit FINDING-12 | sprint_analytics | Analytics append not atomic |

Root cause: `kanban.py` established locking discipline in the BH24 fixes, but
that discipline was never propagated to the surrounding scripts.

### CLASS-3: PreToolUse Timing (3 instances, all FIXED)

Recording state before knowing the outcome of the tool execution.

| Instance | Status |
|----------|--------|
| BH27-001 | FIXED — PostToolUse hook added |
| hooks-audit FINDING-1 | FIXED — same fix |
| BH27-003 | FIXED — verify_agent_output bridges to commit_gate |

This class is fully resolved. The fix is clean: `main()` handles PreToolUse
(detection/blocking only), `post_main()` handles PostToolUse (state recording
after exit code check).

### CLASS-4: Tests That Assert Return Values, Not Side Effects (9 instances)

Tests check "blocked"/"allowed" return values or boolean results but don't
verify the file mutations, log writes, or error messages that are the actual
purpose of the code.

| Instance | Test file | What's missing |
|----------|-----------|----------------|
| BH25-012 | test_hooks | Duplicate test, no message content check |
| BH25-013 | test_hooks | Duplicate test, no message content check |
| BH25-014 | test_hooks | update_tracking_verification has zero tests |
| test-audit FINDING-1 | test_hooks | _state_override bypasses real state machine |
| test-audit FINDING-3 | test_sprint_runtime | sync_one tests: in-memory only, no disk roundtrip |
| test-audit FINDING-7 | test_kanban | WIP warning test doesn't check warning text |
| test-audit FINDING-8 | test_kanban | "no changes" test doesn't verify no write |
| test-audit FINDING-11 | test_sprint_runtime | Mixed PR states: doesn't verify which PR generated action |
| test-audit FINDING-17 | test_kanban | Error message test doesn't check message content |

Root cause: Tests were written to prove the function runs without crashing,
not to pin the contract. The `_state_override` pattern in commit_gate tests
is particularly problematic — it bypasses the exact logic the test claims to verify.

### CLASS-5: Hardcoded/Relative Paths (5 instances)

Scripts or hooks that hardcode paths instead of reading from config.

| Instance | Component | Path |
|----------|-----------|------|
| BH25-010 | risk_register | `sprint-config/risk-register.md` |
| scripts-audit FINDING-2 | risk_register | Same — _REGISTER_PATH relative to CWD |
| hooks-audit FINDING-7 | review_gate | `sprint-config/sprints/hook-audit.log` |
| BH27-002 | session_context | Relative sprints_dir (FIXED) |
| scripts-audit FINDING-42 | cross-cutting | 4 different config-loading patterns across 11 scripts |

---

## Unresolved Findings (from recon audits, not addressed in any punchlist)

These findings were flagged by recon audit agents but do NOT appear in any
pass 25-27 punchlist as items to fix.

### From integration-audit.md

| Finding | Severity | One-line | Why it matters |
|---------|----------|----------|----------------|
| FINDING-3 | MEDIUM | kanban do_sync reads all files upfront, no per-story lock during iteration | With lock_sprint held, this is safe against sync_tracking (also uses lock_sprint). But concurrent `assign` and `update` (which use lock_story) can still collide. The window is shorter now but not eliminated. |
| FINDING-4 | MEDIUM | sync_tracking accepts any state; kanban validates transitions | Running `sync_tracking.py` before `kanban.py sync` can accept illegal transitions. Design decision or bug depends on intent — currently undocumented. |
| FINDING-5 | MEDIUM | done transition partial failure leaves stale GitHub label | No punchlist item addresses the label-swap-then-close two-step failure mode. |
| FINDING-7 | LOW | Two sync paths create TFs with different body content | kanban do_sync creates bare TFs; sync_tracking creates TFs with Verification section. First-writer determines whether the story gets a Verification block. |
| FINDING-8 | LOW | _yaml_safe doesn't escape tab characters | Roundtrip corruption for tab-containing values. |
| FINDING-10 | LOW | sync_backlog partial issue creation failure marks sync complete | Failed issues silently dropped, not retried. |

### From hooks-audit.md

| Finding | Severity | One-line | Why it matters |
|---------|----------|----------|----------------|
| FINDING-4 | MEDIUM | session_context `_read_toml_string` only handles double quotes | If sprint_init ever emits single-quoted TOML values, session context injection silently breaks. |
| FINDING-7 | LOW | review_gate audit log uses hardcoded path | Custom sprints_dir projects get no audit log. |
| FINDING-8 | LOW | check_push misclassifies unknown git push flags | `--mirror`, `--prune`, `--atomic` cause positional arg skipping. |
| FINDING-13 | MEDIUM | No test for hook main() functions end-to-end | The stdin-parse -> dispatch -> exit-code pipeline is untested. |

### From scripts-audit.md

| Finding | Severity | One-line | Why it matters |
|---------|----------|----------|----------------|
| FINDING-1 | MEDIUM | resolve_risk() legacy rows with raw `|` cause mis-split | Pre-fix rows can corrupt the register on resolve. |
| FINDING-9 | MEDIUM | sprint_analytics `--search milestone:` is unreliable | Under-includes from stale GitHub search index. |
| FINDING-20 | MEDIUM | manage_epics reorder_stories walk-back eats header blanks | Metadata table can merge with story content. |
| FINDING-21 | MEDIUM | manage_epics renumber_stories replaces IDs inside code blocks | Code blocks, URLs, comments get corrupted. |
| FINDING-25 | MEDIUM | manage_sagas epic ID extraction assumes filename convention | Non-standard epic filenames produce wrong IDs. |
| FINDING-29 | MEDIUM | gap_scanner git diff fails silently for deleted branches | Returns "no entry point touched" for merged/deleted branches. |
| FINDING-30 | MEDIUM | gap_scanner entry point substring matching produces false positives | Entry point "main" matches "mainly", "domain", etc. |

### From test-audit.md

| Finding | Severity | One-line | Why it matters |
|---------|----------|----------|----------------|
| FINDING-2 | HIGH | TestCheckStatusImportGuard never makes sync_backlog unavailable | The "unavailable" code path is completely untested. |
| FINDING-5 | HIGH | _read_toml_key escaped-quote test asserts the bug, not the spec | Test passes when behavior is wrong — actively masks the BH26-005 bug. |
| FINDING-9 | MEDIUM | Lock tests don't verify mutual exclusion | Only test acquire/release, not concurrent serialization. |
| MISSING-3 | MEDIUM | No integration test for hook main() functions | Same as hooks-audit FINDING-13. |

---

## Regression Risk Assessment

### Fixes that may have introduced new issues

#### 1. sync_tracking.py lock_sprint upgrade (fixing integration-audit FINDING-1)

**Change:** sync_tracking.py switched from `lock_story` per-file to `lock_sprint`
for the entire sync loop (line 279).

**Risk:** The sync loop now holds the sprint-wide lock for the entire duration,
which includes `_fetch_all_prs()` (a GitHub API call that could take seconds or
timeout). If the API call hangs, the lock blocks ALL concurrent kanban operations
for that sprint. Previously, only individual story files were blocked during their
specific write.

**Mitigation check:** Looking at the code, `_fetch_all_prs()` is called BEFORE
the `lock_sprint` context (line 272 vs 279). The API call is outside the lock.
**Risk is mitigated.** But the sync loop itself iterates over all issues and
calls `sync_one` + `atomic_write_tf` for each, which could still be slow for
large sprints. This is acceptable — the alternative (per-story locks) had the
proven concurrency bug.

#### 2. commit_gate PostToolUse addition (fixing BH27-001)

**Change:** Added `post_main()` as a PostToolUse hook, and removed `mark_verified()`
from `main()`.

**Risk:** If Claude Code's PostToolUse payload format differs from what `post_main()`
expects (e.g., `exit_code` vs `exitCode` key name), verification recording silently
fails and the gate becomes permanently blocking. The code handles both key names
(line 262: `tool_output.get("exit_code", tool_output.get("exitCode", -1))`), which
is good. But if the actual key is something else entirely, the default `-1` means
`exit_code != 0` and verification is never recorded.

**Risk level:** LOW — the fallback handles the two known key name conventions.

#### 3. verify_agent_output bridge to commit_gate (fixing BH27-003)

**Change:** After successful verification, `verify_agent_output.py` imports and
calls `commit_gate.mark_verified()` (line 201).

**Risk:** The import is inside a try/except (line 200-204), so failure is silent.
If the import path changes or `mark_verified` is renamed, the bridge silently
breaks. More subtly: `verify_agent_output` runs as a SubagentStop hook (separate
process), but `commit_gate.mark_verified()` writes to a session-scoped state file
based on `CLAUDE_SESSION_ID`. If the SubagentStop process has a different session
ID (or no session ID), the state file written by verify_agent_output won't be
found by commit_gate's PreToolUse process.

**Risk level:** MEDIUM — depends on whether Claude Code propagates CLAUDE_SESSION_ID
to SubagentStop hook processes. If not, this bridge is silently broken.

#### 4. manage_sagas.py blank-line stripping (fixing BH27-006)

**Change:** Added `while remainder and remainder[0].strip() == "": remainder.pop(0)`
before reassembly (line 172).

**Risk:** If the remainder starts with content that has meaningful leading blank
lines (e.g., a section that intentionally starts with a blank line for visual
separation), those blank lines are now stripped. In practice, the remainder starts
at the next `##` heading, which shouldn't have leading blank lines. **Risk is low.**

#### 5. sync_tracking.py uppercase normalization (fixing integration-audit FINDING-9)

**Change:** `existing` dict now keyed by `tf.story.upper()` (line 262).

**Risk:** None identified. The lookup side already used uppercase via
`extract_story_id()`. This just aligns the dict key side.

---

## Remaining Gaps — Ranked by Risk

### RANK 1 (Critical): Hook TOML parser escaped-quote bug — BH26-005

**Files:** `.claude-plugin/hooks/verify_agent_output.py` lines 51-72 (`_has_unquoted_bracket`, `_strip_inline_comment`)

**Why this is #1:** This bug affects `verify_agent_output.py`, which is the
safety-critical hook that runs check_commands after agent completion. If a
project's `check_commands` array contains a value with escaped quotes and
brackets (e.g., `'pytest -k "test[param]"'`), the `_has_unquoted_bracket`
function treats the `]` inside the quoted string as a closing bracket,
truncating the array prematurely. This silently drops check commands from
the verification list.

The bug is *masked* by test-audit FINDING-5: the test for escaped quotes
(`test_read_toml_key_inline_comment_after_escaped_quote`, test_hooks.py line 338)
asserts the current (wrong) behavior as correct. So the test suite will not
catch a fix — in fact, a correct fix will break the existing test. Any
developer who runs the tests and sees green will believe this code is correct.

**Blast radius:** Any project using `pytest -k "test[param]"` or similar
bracket-in-quotes commands in `check_commands` will have incomplete verification.
The hook will think it ran all commands when it actually skipped some.

**Fix:** Update `_has_unquoted_bracket()` and `_strip_inline_comment()` to
properly handle `\"` escape sequences inside double-quoted strings. Update
test_hooks.py line 338 to assert the correct unescaped value.

### RANK 2 (High): done transition partial failure — integration-audit FINDING-5/11

**Files:** `scripts/kanban.py` lines 390-401

**Why this is high risk:** When transitioning to `done`, the label swap
succeeds but the issue close fails. Local state is rolled back, but GitHub
now has `kanban:done` label with the issue still open. The next sync run
sees `kanban:done` label and accepts the transition — the user's issue
is marked done locally even though it was never properly closed. There is
no warning that the close failed and propagated anyway.

**Fix:** Either (a) reverse the label on failed close, or (b) close first,
then swap labels, so the more critical operation happens first.

### RANK 3 (High): No end-to-end tests for hook main() entry points

**Files:** `tests/test_hooks.py`

**Why this is high risk:** This gap appears in both hooks-audit FINDING-13
and test-audit MISSING-3. The hook `main()` functions parse JSON from stdin,
dispatch to check functions, and set exit codes. None of this is tested.
The `review_gate.main()` line 194 uses substring matching (`"gh" in command`)
while `check_merge` uses regex (`gh\s+pr\s+merge\s+(\d+)`). These two layers
of filtering use different matching logic, and the mismatch is untested.

Since the hooks are the primary safety mechanism (blocking bad commits,
pushes, and merges), the lack of end-to-end tests means the wiring between
components could break without detection.

### RANK 4 (Medium): CLAUDE_SESSION_ID propagation uncertainty in verify_agent_output bridge

**Files:** `.claude-plugin/hooks/verify_agent_output.py` line 201, `.claude-plugin/hooks/commit_gate.py` line 39

**Why this matters:** The fix for BH27-003 (verify_agent_output bridging to
commit_gate.mark_verified) depends on both hooks sharing the same
`CLAUDE_SESSION_ID` environment variable. The state file path is
`/tmp/giles-verification-state-{session_id}`. If SubagentStop hooks run in
a different process environment than PreToolUse/PostToolUse hooks, the bridge
writes to a different state file and the commit gate never sees it. This would
make BH27-003's fix silently non-functional.

This cannot be verified by reading code alone — it depends on Claude Code's
hook execution model.

### RANK 5 (Medium): Five scripts write shared files without atomic writes or locking

**Files:** `risk_register.py`, `manage_epics.py`, `manage_sagas.py`, `sprint_analytics.py`, `smoke_test.py`

**Why this matters:** These scripts perform read-modify-write on markdown files
that other scripts and hooks also read. A crash during `Path.write_text()` leaves
a truncated file. Concurrent execution (e.g., two processes calling `add_story()`
on the same epic) silently drops one update. The kanban system solved this with
`atomic_write_tf()` and `lock_story()`, but the pattern was never propagated.

### RANK 6 (Medium): sync_tracking accepts any state transition, kanban validates

**Files:** `scripts/kanban.py` line 529, `skills/sprint-run/scripts/sync_tracking.py` line 135

**Why this matters:** The two sync paths have different transition policies.
Running sync_tracking before kanban sync can permanently accept illegal
transitions from GitHub (e.g., someone manually labeling todo -> done).
The CLAUDE.md documents this as intentional, but the consequence is that
the local state depends on *which sync runs first*, which is unpredictable
in practice.

### RANK 7 (Medium): Rust test detection is broken in test_coverage.py

**Files:** `scripts/test_coverage.py` line 23

**Why this matters:** The `#[test]\s*fn` regex requires `#[test]` and `fn` on
the same line, but standard Rust puts them on separate lines. This means
test_coverage.py reports 0% coverage for all Rust projects, which generates
false-alarm traceability gaps. Confirmed independently by both Pass 27 (BH27-007)
and scripts-audit (FINDING-16).

### RANK 8 (Low): session_context `_read_toml_string` only handles double quotes

**File:** `.claude-plugin/hooks/session_context.py` line 31

**Why this is low (not medium):** `sprint_init.py` currently always generates
double-quoted TOML values, so this parser limitation doesn't hit in practice.
It becomes a problem only if the TOML generation changes or if a user manually
edits project.toml with single quotes. But the session context hook is non-critical
(it injects retro context, not safety gates), so silent failure is inconvenient
rather than dangerous.
