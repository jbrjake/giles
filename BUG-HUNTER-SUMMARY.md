# Bug Hunter Summary — Pass 39

**Date:** 2026-03-21
**Project:** giles (Claude Code agile sprint plugin)
**Baseline:** 1184 tests, 0 failures, lint-clean, 17.25s
**Focus:** Systemic adversarial review of inter-component seams — zero trust

## Results

| Category | Found | Resolved | Closed | Remaining |
|----------|-------|----------|--------|-----------|
| HIGH | 0 | 0 | 0 | 0 |
| MEDIUM | 7 | 5 | 2 | 0 |
| LOW | 7 | 4 | 3 | 0 |
| INFO | 1 | 0 | 1 | 0 |
| **Total** | **16** | **9** | **7** | **0** |

**Tests:** 1184 → 1188 (+4 new)
**Lint:** 0 → 0 (stayed clean)

## Notable Fixes

### 1. check_prs() truncated at 30 PRs (BH39-201, MEDIUM)
`check_status.check_prs()` called `gh pr list` without `--limit`, defaulting to 30 results. Projects with >30 open PRs had silently incomplete PR monitoring. Every other PR-listing call in the codebase used `--limit 500`. Added `--limit 500`, `isinstance` guard, and `warn_if_at_limit`.

### 2. sprint_analytics undercounts review rounds (BH39-202, MEDIUM)
`compute_review_rounds` used `--search milestone:"title"` which routes through GitHub search API — unreliable for merged PRs, subject to indexing limits, and ignores `--state all` on some gh versions. Post-filter caught over-inclusion but not under-inclusion. Removed `--search`, now fetches all PRs and post-filters client-side, matching the pattern used by `gate_prs`.

### 3. populate_issues drops custom story ID patterns (BH39-001, MEDIUM)
`get_existing_issues()` filtered dedup IDs with `re.match(r"[A-Z]+-\d+", sid)`, silently dropping custom story IDs without hyphens (e.g., TASK0001). On re-run, those stories weren't in the existing set → duplicate GitHub issues. Broadened filter to accept any non-"UNKNOWN" ID from `extract_story_id()`.

### 4. tracking-formats.md stale sync logging claim (BH39-100, MEDIUM)
Documentation claimed external syncs (do_sync, sync_tracking) "do not currently append log entries." Both paths have appended transition log entries since the BH27 fixes. Updated to reflect reality — critical because `_count_review_rounds` counts these entries for escalation.

### 5. assign_dod_level non-atomic writes (BH39-101, LOW)
Only production writer using `write_tf()` instead of `atomic_write_tf()`. Concurrent readers could see partial files. Swapped to `atomic_write_tf` and updated imports.

### 6. Milestone API efficiency (BH39-207, LOW)
`find_milestone` and `find_milestone_number` queried milestones without `per_page=100` (default 30), causing extra API calls for repos with >30 milestones. Added `?per_page=100` matching `populate_issues.get_milestone_numbers`.

## Patterns Discovered

### PATTERN-39-A: Missing API limits/guards
3 items where new gh_json call sites didn't inherit defensive patterns (--limit, isinstance guard, warn_if_at_limit) from similar calls elsewhere. **Lesson:** When adding a new gh_json call, check existing calls for the defensive posture and copy it.

### PATTERN-39-B: Doc/code semantic drift at seam boundaries
3 items where documentation described pre-change behavior that code had since evolved. Same pattern as PATTERN-38-A from prior pass — recurring theme in a rapidly-evolving codebase. **Lesson:** When modifying behavior at a seam, grep for documentation of the old behavior.

### PATTERN-39-C: Dedup filter inconsistency
`extract_story_id()` has a broad fallback (sanitized slug) but consumers filtered its output inconsistently. **Lesson:** When a function has multiple output paths, document the consumer contract.

## Seams Verified Clean

The audit verified these critical seams are correct:
- **All 22 sys.path.insert computations** resolve correctly
- **All 30+ imported symbols** from validate_config.py exist and match
- **TF dataclass round-trip** through _yaml_safe/frontmatter_value is lossless
- **All detect_sprint() callers** handle None return correctly
- **kanban ↔ sync_tracking lock coordination** is correct (both hold lock_sprint)
- **All directory creation contracts** use mkdir(parents=True, exist_ok=True)
- **Atomic write correctness** — same-filesystem guarantee, partial write safety
- **Label format write/read consistency** across all 5 categories
- **All 5 hooks** degrade gracefully with missing config
- **ConfigError propagation** — all 17 scripts catch appropriately

## Recommendation

The codebase is converged after 39 passes. The seam audit found no HIGH severity issues — individual component boundaries are well-guarded after 38 prior passes. The MEDIUM findings were all at the "second-order" seam level: API call sites missing defensive patterns that exist elsewhere, documentation lagging behind behavior changes, and inconsistent consumer contracts for shared functions. These are maintenance-layer bugs, not design-layer bugs. The recurring PATTERN-39-B (doc drift on behavior change) suggests adding a grep step to the code review process: when changing behavior at a module boundary, verify documentation reflects the change.
