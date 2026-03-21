# Cross-Cutting Adversarial Findings (Manual Review)

Findings from reading all source scripts holistically, focusing on
inter-module interactions, subtle logic errors, and systemic patterns.

---

## Finding 1: `do_release` rollback leaves orphaned commit on remote

- **File:** skills/sprint-release/scripts/release_gate.py:592-594
- **Category:** bug/logic
- **Severity:** HIGH

When the GitHub Release API call fails at line 590-594, the code calls
`_rollback_tag()` (deletes tag from local + remote) and `_rollback_commit()`
(resets local HEAD to pre-release SHA). But the version bump commit and tag
were already pushed to the remote at line 534-537. `_rollback_commit()` only
does a local `git reset --hard` — it does NOT force-push to remove the
version bump commit from the remote.

**Impact:** After a failed GitHub Release:
- Remote base branch has an orphaned version bump commit (no release)
- Local HEAD is behind remote → next `git push` will fail
- Someone pulling the branch gets a version bump with no corresponding release
- Recovery requires a manual `git push --force origin main` or revert commit

**Evidence:** `_rollback_commit()` (line 482-488) does `git reset --hard`,
but there is no corresponding `git push --force` to the remote.

---

## Finding 2: `get_linked_pr` returns first merged PR, not latest

- **File:** skills/sprint-run/scripts/sync_tracking.py:73-81
- **Category:** bug/logic
- **Severity:** MEDIUM

When iterating over timeline-linked PRs, the code `break`s at the first
merged PR (chronologically oldest). But for stories with multiple linked PRs
(e.g., a failed first attempt and a successful redo), the correct PR is the
most recent merged one.

**Evidence:**
```python
best = linked[-1]  # default to last
for d in linked:
    if d.get("state") == "open":
        best = d
        break
    if (d.get("pull_request", {}).get("merged_at") is not None):
        best = d
        break  # ← stops at FIRST merged, should find LAST
```

Note: Pass 11 (BH-P11-101) flagged this but the "fix" just documented the
existing behavior — the `break` logic was not actually changed.

---

## Finding 3: Sprint heading regex inconsistency across scripts

- **File:** Multiple scripts
- **Category:** design/inconsistency
- **Severity:** MEDIUM

Four different scripts parse sprint section headings with subtly different patterns:

| Script | Pattern | Requires colon? |
|--------|---------|-----------------|
| populate_issues.py `_SPRINT_HEADER_RE` | `### Sprint (\d+):.*?` | YES |
| bootstrap_github.py `_collect_sprint_numbers` | `### Sprint (\d+):` | YES |
| populate_issues.py `_infer_sprint_number` | `^###\s+Sprint\s+(\d+)` | NO |
| update_burndown.py / check_status.py `check_milestone` | `^Sprint {N}\b` | NO (milestone title) |

A heading like `### Sprint 1` (no colon) would be detected by
`_infer_sprint_number` but NOT by `_SPRINT_HEADER_RE` or
`_collect_sprint_numbers`. This means stories could be assigned to
sprint numbers that don't get GitHub labels or milestones.

---

## Finding 4: `_yaml_safe` doesn't quote YAML boolean keywords

- **File:** skills/sprint-run/scripts/sync_tracking.py:171-186
- **Category:** bug/logic
- **Severity:** LOW

`_yaml_safe()` checks for various YAML-sensitive characters but doesn't
check for YAML boolean keywords (`true`, `false`, `yes`, `no`, `on`, `off`,
`null`). If any field value happened to be one of these words, it would be
parsed as a boolean/null when read back, not as a string.

Practical risk is low (story IDs are like "US-0101", branches are
"sprint-1/US-0101-slug"), but it's a correctness gap that could bite in
edge cases (e.g., a story title containing only "null").

---

## Finding 5: `enrich_from_epics` sprint inference breaks on ties

- **File:** skills/sprint-setup/scripts/populate_issues.py:231-234
- **Category:** bug/logic
- **Severity:** LOW

The sprint number inference uses a complex `min()` with a generator
that filters by most-common count. On ties (e.g., 3 stories in sprint 1
and 3 in sprint 2), it picks the numerically lowest sprint, which may
be wrong for epic files that span multiple sprints.

```python
sprint = min(
    (s for s in set(known_sprints)
     if known_sprints.count(s) == max(known_sprints.count(x) for x in set(known_sprints))),
) if known_sprints else 0
```

Also: this is O(n²) per epic file due to repeated `.count()` calls. Not
a performance issue at typical scale but symptomatic of rushed code.

---

## Finding 6: `parse_requirements` only scans `reference.md` files

- **File:** scripts/traceability.py:114
- **Category:** bug/logic
- **Severity:** MEDIUM

`parse_requirements()` uses `prd_path.rglob("reference.md")` — it only
looks for files literally named `reference.md`. If a project uses different
naming conventions (e.g., `requirements.md`, `prd-01.md`, `spec.md`), all
requirements will be silently missed and the traceability report will show
0 requirements, giving false confidence that everything is traced.

The function docstring says "PRD reference files" but the implementation
is hardcoded to one filename.

---

## Finding 7: `_parse_workflow_runs` misses YAML folded style

- **File:** scripts/sprint_init.py:203
- **Category:** doc/drift
- **Severity:** LOW

The docstring explicitly says "Known limitation: `run: >` and `run: >-`
(YAML folded style) are NOT detected — only literal block style (`|`) is
supported." This is documented, but it means CI command detection will be
incomplete for projects that use folded style in their workflow YAML.

More importantly, `run: >` blocks will be silently skipped — the command
on the next line will be ignored, and the detected CI commands list will be
incomplete, leading to an incorrect `project.toml` [ci] section.

---

## Finding 8: Multiple scripts don't validate `gh_json` return type

- **File:** Multiple
- **Category:** bug/error-handling
- **Severity:** LOW

Some scripts check `isinstance(result, list)` after `gh_json()` calls,
others don't. For example:

- `compute_velocity` (sprint_analytics.py:50): checks `isinstance`
- `_fetch_all_prs` (sync_tracking.py:43): checks `isinstance`
- `gate_stories` (release_gate.py:141-148): does NOT check — directly iterates
- `gate_prs` (release_gate.py:174-193): does NOT check — directly iterates

If `gh_json` returns a dict (single object) instead of a list, `gate_stories`
would iterate over dict keys rather than issues, producing wrong results.

---

## Finding 9: `write_version_to_toml` regex assumes `[release]` is not in a comment

- **File:** skills/sprint-release/scripts/release_gate.py:280
- **Category:** bug/logic
- **Severity:** LOW

The regex `r"^\[release\]"` to find the release section doesn't exclude
matches inside comments. A TOML comment like `# See [release] notes` would
be matched, and the version would be written at the wrong position.

---

## Finding 10: No duplicate story ID detection in `parse_milestone_stories`

- **File:** skills/sprint-setup/scripts/populate_issues.py:93-128
- **Category:** bug/logic
- **Severity:** MEDIUM

If the same US-XXXX story ID appears in multiple milestone files (or
multiple times in the same file), `parse_milestone_stories` silently
creates duplicate Story objects. These duplicates flow through to
`create_issue`, where idempotency via `get_existing_issues()` would
catch the second creation attempt — but only after the first one was
created with potentially wrong metadata (whichever was parsed first).

`enrich_from_epics` handles duplicates via a `by_id` dict (last wins),
but `parse_milestone_stories` doesn't — it appends blindly.
