# Audit 4: FakeGitHub Fidelity

Adversarial review of `tests/fake_github.py` against every `gh()` and
`gh_json()` call site in production code.

---

## 1. Command Coverage Matrix

### 1.1 `gh label create`

| Call site | Flags used | FakeGitHub handles? | Notes |
|-----------|-----------|---------------------|-------|
| `bootstrap_github.create_label()` | `--color`, `--description`, `--force` | Yes | All flags implemented. |

**Verdict:** Full coverage.

---

### 1.2 `gh issue create`

| Call site | Flags used | FakeGitHub handles? | Notes |
|-----------|-----------|---------------------|-------|
| `populate_issues.create_issue()` | `--title`, `--body`, `--label` (multiple), `--milestone` | Yes | Labels auto-created (BH-009). Milestone validated. |

**Verdict:** Full coverage.

---

### 1.3 `gh issue list`

| Call site | Flags used | FakeGitHub handles? | Notes |
|-----------|-----------|---------------------|-------|
| `populate_issues.get_existing_issues()` | `--limit 500`, `--json title`, `--state all` | Yes | |
| `validate_config.list_milestone_issues()` | `--milestone`, `--state all`, `--json number,title,state,labels,closedAt,body`, `--limit 1000` | Yes | |
| `release_gate.gate_stories()` | `--milestone`, `--state open`, `--json number,title`, `--limit 500` | Yes | |
| `sprint_analytics.compute_velocity()` | `--milestone`, `--state all`, `--json state,labels,body,title`, `--limit 500` | Yes | |
| `sprint_analytics.compute_workload()` | `--milestone`, `--state all`, `--json labels`, `--limit 500` | Yes | |
| `check_status.check_milestone()` | `--milestone`, `--state all`, `--json state,labels,body`, `--limit 500` | Yes | |

**Finding F01 (Low): `--jq` not in `issue_list` `_KNOWN_FLAGS`.**
The test `test_bugfix_regression.py:215` passes `--jq` to `issue list`, but
`_KNOWN_FLAGS["issue_list"]` does not include `"jq"`. This means the test
should raise `NotImplementedError` from `_check_flags`. However, the test
fixture directly manipulates `fake.issues` and calls `fake.handle()` — if
this call actually runs, it would blow up. *No production code currently
passes `--jq` to `issue list`*, so this is a test-only latent error, not a
production fidelity gap.

**Verdict:** Functionally complete for all production call patterns.

---

### 1.4 `gh issue edit`

| Call site | Flags used | FakeGitHub handles? | Notes |
|-----------|-----------|---------------------|-------|
| SKILL.md instructions (manual use) | `--add-label`, `--remove-label`, `--milestone` | Yes | Milestone counter updates implemented (BH19-006). |

**Verdict:** Full coverage. Note: `issue edit` is used by skill prompts
(sprint-run kanban transitions), not by Python scripts. FakeGitHub's
implementation handles the label and milestone mutations correctly.

---

### 1.5 `gh issue close`

| Call site | Flags used | FakeGitHub handles? | Notes |
|-----------|-----------|---------------------|-------|
| SKILL.md instructions (manual use) | `<number>` | Yes | Milestone counters updated (BH-002). |

**Verdict:** Full coverage.

---

### 1.6 `gh pr list`

| Call site | Flags used | FakeGitHub handles? | Notes |
|-----------|-----------|---------------------|-------|
| `sync_tracking._fetch_all_prs()` | `--state all`, `--json number,state,headRefName,mergedAt`, `--limit 500` | Partial | See F02. |
| `release_gate.gate_prs()` | `--json number,title,milestone`, `--limit 500` | Yes | Default state filter = "open" matches. |
| `sprint_analytics.compute_review_rounds()` | `--state all`, `--json number,title,labels,milestone,reviews`, `--limit 500`, `--search milestone:"X"` | Partial | See F03. |
| `check_status.check_prs()` | `--json number,title,reviewDecision,labels,statusCheckRollup,createdAt` | Partial | See F04. |
| `check_status.main()` | `--json headRefName` | Yes | |

**Finding F02 (Medium): Missing `mergedAt` field in `_pr_create` default schema.**
`sync_tracking._fetch_all_prs()` requests `--json number,state,headRefName,mergedAt`.
FakeGitHub's `_pr_create()` sets `"mergedAt": None` (line 827), and `_pr_merge()` sets
it to an ISO timestamp (line 888). This is correct. However, the production code at
`sync_tracking.py:115` checks `pr.get("mergedAt")` from the *raw gh output* where
the field name should be `mergedAt`. FakeGitHub correctly uses this casing. **No bug.**

**Finding F03 (Low): `reviews` field not populated by `_pr_create`.**
`sprint_analytics.compute_review_rounds()` requests `--json ...reviews...`. FakeGitHub's
`_pr_create()` does not include a `reviews` key in the default PR dict. The `reviews`
field is only added via `pr.setdefault("reviews", [])` in `_pr_review()` (line 867).
This means PRs that were never reviewed will return `None` for `pr.get("reviews")`,
which production code handles with `pr.get("reviews") or []` (line 105 of
sprint_analytics.py). **Functionally OK but semantically sloppy** — real gh returns
`[]` (empty list), not a missing key.

**Finding F04 (Medium): Missing `statusCheckRollup` and `createdAt` fields.**
`check_status.check_prs()` requests `--json number,title,reviewDecision,labels,statusCheckRollup,createdAt`.
FakeGitHub's `_pr_create()` does NOT include `statusCheckRollup` or `createdAt` in the
created PR dict. Tests that exercise `check_prs()` (e.g., `test_sprint_runtime.py:88`)
work around this by manually injecting these fields into the fixture data. This means:
- Any test that creates PRs via FakeGitHub's `_pr_create` and then calls `check_prs()` would
  get `None` for these fields (gracefully handled by production code's `or []` and `.get("", "")` patterns).
- The `_filter_json_fields()` method would include them as `None` values, which does
  not match real gh behavior (real gh returns empty arrays `[]` for rollup and ISO strings for dates).
- **Risk:** Test authors must remember to manually add these fields. FakeGitHub
  should include them in `_pr_create()` with sensible defaults.

---

### 1.7 `gh pr create`

| Call site | Flags used | FakeGitHub handles? | Notes |
|-----------|-----------|---------------------|-------|
| SKILL.md (sprint-run story execution) | `--title`, `--body`, `--base`, `--head`, `--label`, `--milestone` | Yes | |

**Verdict:** Full coverage.

---

### 1.8 `gh pr review`

| Call site | Flags used | FakeGitHub handles? | Notes |
|-----------|-----------|---------------------|-------|
| SKILL.md (sprint-run review phase) | `--approve`, `--request-changes`, `--body` | Yes | Sets `reviewDecision` on PR. |

**Verdict:** Full coverage.

---

### 1.9 `gh pr merge`

| Call site | Flags used | FakeGitHub handles? | Notes |
|-----------|-----------|---------------------|-------|
| SKILL.md (sprint-run integration phase) | `--squash`, `--merge`, `--rebase` | Yes | |

**Finding F05 (Medium): Merging a PR does NOT close linked issues.**
In real GitHub, merging a PR that contains "Closes #N" or "Fixes #N" in the body
automatically closes the linked issue. FakeGitHub's `_pr_merge()` updates the PR
state to `MERGED` but does not scan the PR body for "Closes #N" patterns and does
not update any linked issues or milestone counters. This means:
- Tests that rely on the "merge PR -> issue closes" flow will not see the issue
  state change unless they explicitly call `issue close` separately.
- Milestone `open_issues` / `closed_issues` counters will be wrong after a merge
  that should have closed issues.

**Severity assessment:** Medium. Production code (sprint-run SKILL.md) explicitly
closes issues via `gh issue close` in the kanban transition to `done`, so the
implicit close-on-merge behavior is not relied upon. But it's a fidelity gap.

---

### 1.10 `gh run list`

| Call site | Flags used | FakeGitHub handles? | Notes |
|-----------|-----------|---------------------|-------|
| `check_status.check_ci()` | `--limit 5`, `--json status,conclusion,name,headBranch,databaseId` | Partial | See F06. |
| `release_gate.gate_ci()` | `--branch`, `--limit 1`, `--json status,conclusion,name` | Yes | |

**Finding F06 (Low): `databaseId` not in FakeGitHub run schema.**
`check_status.check_ci()` requests `databaseId` in `--json` fields. FakeGitHub's
run objects don't include `databaseId` by default. Tests work around this by
manually injecting the field (e.g., `test_sprint_runtime.py:51`). The
`_filter_json_fields()` method returns `None` for missing keys, which production
code handles with `run.get("databaseId")` (returns `None`, skips the `run view` call).
**No crash, but the `run view --log-failed` path is never exercised when using
FakeGitHub-created runs.**

---

### 1.11 `gh run view`

| Call site | Flags used | FakeGitHub handles? | Notes |
|-----------|-----------|---------------------|-------|
| `check_status.check_ci()` | `<run_id>`, `--log-failed` | Partial | See F07. |

**Finding F07 (Medium): `run view` returns hardcoded "no logs" and ignores all flags.**
Production code passes `--log-failed` and a run ID. FakeGitHub returns `_ok("no logs")`
regardless of the run ID or flags passed. The `--log-failed` flag is not registered
in `_KNOWN_FLAGS` (there is no `"run_view"` entry). This means:
- The flag is silently accepted (the handler doesn't call `_check_flags`).
- The returned "no logs" string is parsed by `_first_error()` which finds no error
  keywords and returns `""`, so the code path falls through to the generic
  "could not read logs" action.
- **Tests never exercise the CI log error-extraction logic** through FakeGitHub.

---

### 1.12 `gh release create`

| Call site | Flags used | FakeGitHub handles? | Notes |
|-----------|-----------|---------------------|-------|
| `release_gate.do_release()` | `<tag>` (positional), `--title`, `--notes-file`, optional binary (positional) | Partial | See F08. |

**Finding F08 (Medium): `--notes-file` accepted but not read; binary arg silently ignored.**
Production code passes `--notes-file <path>` instead of `--notes`. FakeGitHub has
`notes-file` in `_ACCEPTED_NOOP_FLAGS` (line 180), so it's silently accepted. The
release body is always empty `""` because `flags.get("notes", [""])[0]` doesn't find
`notes` (it was passed as `notes-file`). The binary positional argument at the end
of `release_args` is consumed as a plain positional arg and ignored by `_parse_flags`.
- **Impact:** Tests that assert on `release.body` or `release["body"]` will get empty
  strings even when production would have full release notes.
- Tests that check whether the binary was uploaded to the release will always see
  nothing, because FakeGitHub doesn't model upload assets at all.

---

### 1.13 `gh release view`

| Call site | Flags used | FakeGitHub handles? | Notes |
|-----------|-----------|---------------------|-------|
| `release_gate.do_release()` | `<tag>`, `--json url`, `--jq .url` | Yes | jq evaluated when package available. Returns URL string. |

**Verdict:** Full coverage.

---

### 1.14 `gh api` (milestones)

| Call site | Flags used | FakeGitHub handles? | Notes |
|-----------|-----------|---------------------|-------|
| `bootstrap_github.create_milestones_on_github()` | `repos/{owner}/{repo}/milestones`, `-f title=...`, `-f description=...`, `-f state=open` | Partial | See F09. |
| `validate_config.find_milestone()` | `repos/{owner}/{repo}/milestones`, `--paginate` | Yes | |
| `release_gate.find_milestone_number()` | `repos/{owner}/{repo}/milestones`, `--paginate` | Yes | |
| `release_gate.do_release()` | `repos/{owner}/{repo}/milestones/{N}`, `-X PATCH`, `-f state=closed` | Yes | |
| `populate_issues.get_milestone_numbers()` | `repos/{owner}/{repo}/milestones?per_page=100`, `--paginate` | Yes (partial) | See F10. |

**Finding F09 (Low): `-f state=open` ignored during milestone creation.**
`bootstrap_github.create_milestones_on_github()` passes `-f state=open` when
creating milestones. FakeGitHub's milestone creation handler only reads `title=`
and `description=` from `-f` flags. The `state` field is hardcoded to `"open"` in
the created milestone dict, so the behavior matches. But if production ever passed
a different state, FakeGitHub would silently ignore it.

**Finding F10 (Low): URL query params not stripped from API path.**
`populate_issues.get_milestone_numbers()` passes
`repos/{owner}/{repo}/milestones?per_page=100`. FakeGitHub checks `"milestones" in path`,
which matches because the query param is part of the path string. This works by
accident but is fragile — if FakeGitHub ever used exact path matching, it would break.

---

### 1.15 `gh api` (compare)

| Call site | Flags used | FakeGitHub handles? | Notes |
|-----------|-----------|---------------------|-------|
| `check_status.check_branch_divergence()` | `repos/{repo}/compare/{base}...{branch}`, `--jq {behind_by: .behind_by, ahead_by: .ahead_by}` | Yes | jq evaluated when package available. Comparisons dict pre-populated. |

**Verdict:** Full coverage. The `--jq` filter reshapes the comparison data, which
FakeGitHub handles via `_maybe_apply_jq`.

---

### 1.16 `gh api` (commits)

| Call site | Flags used | FakeGitHub handles? | Notes |
|-----------|-----------|---------------------|-------|
| `check_status.check_direct_pushes()` | `repos/{repo}/commits`, `-f sha=...`, `-f since=...`, `--jq [complex expression]` | Yes | `since` filtering implemented. jq evaluated when package available. |

**Verdict:** Full coverage.

---

### 1.17 `gh api` (timeline)

| Call site | Flags used | FakeGitHub handles? | Notes |
|-----------|-----------|---------------------|-------|
| `sync_tracking.get_linked_pr()` | `repos/{owner}/{repo}/issues/{N}/timeline`, `--paginate`, `--jq [complex expression]` | Yes | Dual-path: jq when available, manual pre-filter fallback. |

**Verdict:** Full coverage.

---

### 1.18 `gh auth status`

| Call site | FakeGitHub handles? | Notes |
|-----------|---------------------|-------|
| `bootstrap_github.check_prerequisites()` | Yes (via `_handle_auth`) | Returns success. |
| `populate_issues.check_prerequisites()` | Yes | |

**Verdict:** Full coverage.

---

### 1.19 `gh --version`

| Call site | FakeGitHub handles? | Notes |
|-----------|---------------------|-------|
| `bootstrap_github.check_prerequisites()` | Yes (via `_handle_version`) | Returns fake version string. |

**Verdict:** Full coverage.

---

## 2. State Consistency Issues

### 2.1 Issue state casing

| Component | State values | Notes |
|-----------|-------------|-------|
| FakeGitHub issues | `"open"`, `"closed"` (lowercase) | Matches real `gh issue list --json state` |
| Production code | Compares against `"open"`, `"closed"` (lowercase) | Consistent with FakeGitHub |

**Verdict:** Consistent. No casing bug.

### 2.2 PR state casing

| Component | State values | Notes |
|-----------|-------------|-------|
| FakeGitHub PRs | `"OPEN"`, `"MERGED"` (uppercase) | Matches real `gh pr list --json state` |
| Production `_pr_list` filter | Case-insensitive comparison via `.upper()` (line 786) | Correct |
| Production `sync_tracking` | Uses `pr.get("mergedAt")` truthy check, not state string | Not affected |
| Production `check_status.check_prs` | Does not filter by state (uses default "open") | Not affected |

**Finding F11 (Low): FakeGitHub never creates `"CLOSED"` state PRs.**
`_pr_merge()` transitions PRs directly from `OPEN` to `MERGED`. There is no
`_pr_close()` handler, so PRs closed without merging cannot be simulated.
Production code (`release_gate.gate_prs()`) filters by default state `"open"`,
so closed-but-not-merged PRs are not a concern. But if a test wanted to simulate
a closed PR, it would need to manually set `pr["state"] = "CLOSED"`.

### 2.3 Milestone counter consistency

| Operation | Counter update? | Notes |
|-----------|----------------|-------|
| `issue create --milestone X` | `open_issues += 1` | Correct (BH-002) |
| `issue close N` | `open_issues -= 1`, `closed_issues += 1` | Correct (BH-002) |
| `issue edit N --milestone X` | Adjusts both old and new milestone counters | Correct (BH19-006) |
| `pr merge N` | No counter update | See F05 — merge doesn't close linked issues |
| Milestone PATCH state=closed | Sets `closed_at` if missing | Correct |

**Verdict:** Counters are maintained correctly for direct issue operations.
The gap is only in the implicit close-on-merge path (F05).

---

## 3. `--jq` Handling

### 3.1 Production jq expressions

| Call site | jq expression | FakeGitHub evaluation |
|-----------|--------------|----------------------|
| `sync_tracking.get_linked_pr()` | `'[.[] \| select(.source?.issue?.pull_request?) \| .source.issue]'` | Dual-path: evaluated when `jq` package installed; manual pre-filter fallback |
| `check_status.check_branch_divergence()` | `'{behind_by: .behind_by, ahead_by: .ahead_by}'` | Evaluated via `_maybe_apply_jq` when `jq` available |
| `check_status.check_direct_pushes()` | `'[.[] \| select(.parents \| length == 1) \| {sha: .sha[:8], ...}]'` | Evaluated via `_maybe_apply_jq` when `jq` available |
| `release_gate.do_release()` | `'.url'` | Evaluated via `_maybe_apply_jq` when `jq` available |

### 3.2 What happens when jq is not installed?

**Finding F12 (High): Silent test degradation when `jq` Python package is missing.**

When the `jq` Python package is not installed:
1. `_check_jq()` returns `False` and emits a single `warnings.warn()`.
2. `_maybe_apply_jq()` returns the unfiltered JSON string.
3. For the **timeline endpoint**, there is a manual pre-filter fallback (lines 470-474)
   that returns the first PR cross-reference. This fallback is **not equivalent** to
   the jq expression:
   - jq returns a **list** of all matching PRs
   - fallback returns a **single dict** (the first match)
   - Production code at `sync_tracking.py:70-72` handles both: `if isinstance(linked, dict): linked = [linked]`
   - But the fallback only returns the *first* PR, silently dropping subsequent ones.
4. For **compare, commits, and release view** endpoints, the unfiltered full JSON
   is returned. This means:
   - `check_branch_divergence()` would get the full compare object instead of
     `{behind_by: N, ahead_by: N}`. Production code calls `data.get("behind_by", 0)`
     which works on the full object too. **No functional bug.**
   - `check_direct_pushes()` would get the full commit objects. Production code
     expects a list of `{sha, message, author, date}` dicts after jq filtering.
     Without jq, it gets full commit objects where `.sha` is the full SHA (not
     truncated to 8 chars) and `.commit.message` is nested differently. **Tests
     pass because test fixtures use the pre-shaped format, not because jq is
     evaluated.** This is a silent fidelity gap.
   - `do_release()` release view would get `{"url": "..."}` (the full object)
     instead of just the URL string. Production calls `gh()` (not `gh_json()`),
     so it gets the raw stdout. Without jq: stdout is `{"url": "..."}` (JSON).
     With jq: stdout is the bare URL string. Production prints this as-is in
     `f"Release published: {url}"`. **With jq missing, the output would include
     JSON braces in the log message.** Not a test failure, but wrong behavior.

**Severity:** High for test trustworthiness. The `jq` package is a dev dependency
and should be required in the test environment. Tests that pass without `jq` are
not actually testing the jq expression correctness — they're testing the fallback
path or pre-shaped fixture data. The existing `test_fakegithub_fidelity.py` requires
`import jq` at module level and would fail to import without it, but other test
files that use FakeGitHub do NOT require `jq` and would silently degrade.

### 3.3 `--jq` flag acceptance by handler

| Handler | `--jq` in `_KNOWN_FLAGS`? | `--jq` evaluated? |
|---------|---------------------------|-------------------|
| `api` | Yes | Yes (via `_maybe_apply_jq`) |
| `release_view` | Yes | Yes (via `_maybe_apply_jq`) |
| `issue_list` | **No** | No |
| `pr_list` | **No** | No |
| `run_list` | **No** | No |

No production code currently passes `--jq` to `issue list`, `pr list`, or `run list`,
so this is not a gap. But a test that tried to use `--jq` with these handlers would
get `NotImplementedError`.

---

## 4. `--search` Handling

### 4.1 Production search predicates

| Call site | `--search` value | What FakeGitHub evaluates |
|-----------|-----------------|--------------------------|
| `sprint_analytics.compute_review_rounds()` | `milestone:"Sprint 1"` | `milestone:` predicate extracted and filtered. |

This is the **only** production use of `--search`. The `_extract_search_milestone()`
helper correctly parses the milestone title from quoted and unquoted forms.

### 4.2 Unevaluated predicates

**Finding F13 (Medium): Only `milestone:` predicate is evaluated; all others silently ignored.**

`_extract_search_milestone()` (line 147) warns when predicates beyond `milestone:`
are present in the search string (P13-019). But this warning goes to Python's
`warnings` module, which tests must explicitly capture with `warnings.catch_warnings`.
In normal test runs, the warning is emitted but may not cause test failure.

**Current production risk:** None, because the only production `--search` use is
`milestone:"Sprint 1"` with no other predicates.

**Future risk:** If someone adds `--search 'milestone:"Sprint 1" is:merged'` to
a production call, FakeGitHub would return all PRs for that milestone regardless
of merge status, and the test would silently pass. The warning would be the only
signal, and it's easy to miss in noisy test output.

### 4.3 Issue list search

`_issue_list()` also calls `_extract_search_milestone()` (line 596-601), providing
parity with `_pr_list()`. No production code currently uses `--search` on `issue list`.

---

## 5. Pagination

### 5.1 Production pagination usage

| Call site | Uses `--paginate`? | Relies on pagination? |
|-----------|-------------------|----------------------|
| `validate_config.find_milestone()` | Yes | Yes — milestones can span multiple pages |
| `release_gate.find_milestone_number()` | Yes | Yes |
| `populate_issues.get_milestone_numbers()` | Yes | Yes |
| `sync_tracking.get_linked_pr()` | Yes | Yes — timeline events can be paginated |
| All `issue list` / `pr list` calls | No | Use `--limit` instead |

### 5.2 FakeGitHub pagination model

**Finding F14 (Low): FakeGitHub does not model pagination at all.**

FakeGitHub returns all data in a single response. `--paginate` is in
`_ACCEPTED_NOOP_FLAGS` (line 180), meaning it's silently accepted without effect.

This is documented and intentional: "FakeGitHub returns all data, so pagination
is implicit." The approach is sound for unit tests — pagination is a transport
concern, not a logic concern.

**However**, `gh_json()` in `validate_config.py` has special handling for
concatenated JSON arrays (`[...][...]`) from paginated responses (lines 92-117).
This pagination-merging logic is **never exercised** by FakeGitHub because
FakeGitHub always returns well-formed single JSON. The concatenation handling
is separately tested in `test_bugfix_regression.py:296` via direct string
manipulation, which is sufficient.

---

## 6. Missing Fields Summary

Fields that production code requests via `--json` but FakeGitHub's create
handlers do not include in the default object schema:

| Object | Missing field | Production accessor | Impact |
|--------|--------------|---------------------|--------|
| PR | `statusCheckRollup` | `pr.get("statusCheckRollup") or []` | Returns `None`, treated as empty list. Tests must manually add. |
| PR | `createdAt` | `pr.get("createdAt", "")` | Returns `None`, treated as empty string. Age calculation returns 0. |
| PR | `reviews` | `pr.get("reviews") or []` | Returns `None` (not `[]`). Only present after `_pr_review`. |
| Run | `databaseId` | `run.get("databaseId")` | Returns `None`. `run view` path skipped. |

**Recommendation:** Add these fields to `_pr_create()` and the run creation
path with sensible defaults:
```python
# In _pr_create:
"statusCheckRollup": [],
"createdAt": datetime.now(timezone.utc).isoformat(),
"reviews": [],

# Runs should include databaseId when added to self.runs
# (but runs are added externally, not via a handler)
```

---

## 7. Findings Ranked by Severity

| ID | Severity | Finding |
|----|----------|---------|
| F12 | **High** | Silent test degradation when `jq` package missing — tests pass but don't verify jq expressions |
| F04 | Medium | Missing `statusCheckRollup` and `createdAt` in PR schema |
| F05 | Medium | PR merge does not close linked issues or update milestone counters |
| F07 | Medium | `run view` ignores `--log-failed` flag and returns hardcoded string; CI log extraction never tested via FakeGitHub |
| F08 | Medium | `--notes-file` accepted as noop; release body always empty; binary uploads not modeled |
| F13 | Medium | Only `milestone:` search predicate evaluated; warning exists but easy to miss |
| F01 | Low | `--jq` not in `issue_list` `_KNOWN_FLAGS` (no production use, test-only latent error) |
| F02 | Low | `mergedAt` casing — actually correct, no bug |
| F03 | Low | `reviews` field missing from default PR dict (gracefully handled) |
| F06 | Low | `databaseId` not in run schema defaults (gracefully handled) |
| F09 | Low | `-f state=open` ignored in milestone creation (behavior matches anyway) |
| F10 | Low | URL query params in API path matched by substring (fragile but works) |
| F11 | Low | No way to simulate closed-but-not-merged PRs |
| F14 | Low | Pagination not modeled (intentional, documented, tested separately) |

---

## 8. Recommendations

### Must fix (test trustworthiness)
1. **F12:** Make `jq` a required test dependency. Add a conftest.py or CI check
   that fails if `jq` is not installed. The existing `test_fakegithub_fidelity.py`
   already imports `jq` at module level, but other test files silently degrade.

### Should fix (fidelity gaps)
2. **F04:** Add `statusCheckRollup`, `createdAt`, and `reviews` fields to
   `_pr_create()` with default values.
3. **F07:** Add `_KNOWN_FLAGS["run_view"]` entry and make the handler accept
   `--log-failed`. Optionally allow test fixtures to set per-run log content.
4. **F08:** Read `--notes-file` content (if the path exists) and store it as
   the release body.

### Nice to have (completeness)
5. **F05:** Optionally scan PR body for `Closes #N` / `Fixes #N` patterns
   on merge and close the linked issues.
6. **F06:** Include `databaseId` in run objects (auto-generated).
7. **F11:** Add a `_pr_close()` handler for completeness.
