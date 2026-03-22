# Phase 0g — Recon Summary (Pass 39 — Seam-Focused)

## Baseline

| Metric | Value |
|--------|-------|
| Python files | 56 (32 source, 24 test) |
| Total LOC | ~31,800 |
| Tests | 1184 pass, 0 fail, 0 skip |
| Runtime | ~17.25s |
| Lint issues | 0 (ruff clean) |
| Skipped tests | 0 (1 conditional self.skipTest in golden_run) |

## Audit Focus: Inter-Component Seams

After 38 converged passes, individual components are well-tested. This pass targets the **contracts between components** — the assumptions one module makes about another's behavior.

## Top 10 Seams (priority order)

### 1. Config Path Resolution Chain (HIGH)
load_config() resolves all [paths] values relative to project root. Every downstream consumer must use these absolute paths. Any re-resolution = breakage.

### 2. TF Dataclass Round-Trip Integrity (HIGH)
read_tf() → TF → write_tf(). _yaml_safe() escaping must handle every value. Data loss on round-trip = silent corruption.

### 3. SPRINT-STATUS.md State Contract (HIGH)
detect_sprint() regex returns int or None. Multiple scripts call it. None handling varies.

### 4. kanban.py ↔ sync_tracking.py Divergence (MODERATE)
Two mutation paths, different validation rules, shared lock_sprint(). Both write TF files.

### 5. GitHub API Error Propagation (MODERATE)
gh_json() → [] | dict | list | RuntimeError. Callers must handle all cases.

### 6. Cross-Skill Import Chain (MODERATE)
sync_backlog.py → bootstrap_github + populate_issues via sys.path. Graceful fallback to None.

### 7. Template/ConfigGenerator Variable Contract (MODERATE)
_esc() must escape all TOML specials. String formatting injects into project.toml.

### 8. Lock File Lifecycle (MODERATE)
lock_story() + lock_sprint(). Directory must exist before lock. Process death = stale lock.

### 9. Hooks ↔ Sprint Config (MODERATE)
session_context, commit_gate, review_gate all read sprint-config. Must handle missing config.

### 10. extract_story_id() Consumers (LOW)
Fallback slug generation may collide. What do callers do with UNKNOWN?

## Churn Hotspots (seam-relevant)
1. kanban.py (12 commits) — state machine seam
2. sync_tracking.py (10 commits) — reconciliation seam
3. Hook files (8-10 each) — hooks↔config seam

## Audit Plan
- Phase 1: Import chains + config data flow (seams 1, 5, 6, 7, 10)
- Phase 2: File system + state machine (seams 2, 3, 4, 8)
- Phase 3: GitHub API + hooks + templates (seams 5, 9, remaining)
