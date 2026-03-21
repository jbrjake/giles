# Audit 5: Duplication, Dead Code, and Unnecessary Complexity

Systematic analysis of all 19 Python scripts in `scripts/` and `skills/*/scripts/`.

---

## 1. Duplicated Parsing Logic

### 1A. Story ID Extraction — Two Independent Implementations

`populate_issues.get_existing_issues()` at `skills/sprint-setup/scripts/populate_issues.py:344`
reimplements the same regex as `validate_config.extract_story_id()` at
`scripts/validate_config.py:925`:

```python
# populate_issues.py:344
m = re.match(r"([A-Z]+-\d+)", issue.get("title", ""))

# validate_config.py:925
m = re.match(r"([A-Z]+-\d+)", title)
```

The comment at line 343 even says "consistent with extract_story_id() in
validate_config.py" — acknowledging the duplication without fixing it. The
function is imported by `sync_tracking.py` and `update_burndown.py` but not
by `populate_issues.py`, which inlines the same logic.

**Impact:** Low risk today (identical regex), but a divergence hazard if
either copy is modified without updating the other.

### 1B. Closed-Issue Override Logic — Triplicated

Three scripts independently check whether a closed issue has a stale kanban
label and override it to `"done"`:

- `sync_tracking.py:241` — in `sync_one()`
- `sync_tracking.py:291` — in `create_from_issue()`
- `update_burndown.py:170` — in `build_rows()`

All three use the same pattern:
```python
status = kanban_from_labels(issue)
if issue.get("state") == "closed" and status != "done":
    status = "done"
```

`kanban_from_labels()` at `validate_config.py:942` already has a
closed-issue fallback (line 948: `fallback = "done" if issue.get("state") ==
"closed" else "todo"`), but it only activates when NO kanban labels exist.
The callers add a second layer of override for the case where stale kanban
labels are present on a closed issue.

**Recommendation:** Add a `force_done_if_closed=True` parameter to
`kanban_from_labels()` to centralize this logic. All three call sites would
then just call `kanban_from_labels(issue)` with the default behavior.

### 1C. Short Title Extraction — Duplicated

Two scripts extract the short title after ":" in issue titles with identical
logic:

- `sync_tracking.py:293-296` in `create_from_issue()`
- `update_burndown.py:159-162` in `build_rows()`

Both do:
```python
short = (
    issue["title"].split(":", 1)[-1].strip()
    if ":" in issue["title"]
    else issue["title"]
)
```

**Recommendation:** Extract to a `short_title(title: str) -> str` helper in
`validate_config.py`.

### 1D. YAML Frontmatter Parsing — Two Regex Sites

Two scripts parse `---` delimited YAML frontmatter independently:

- `sync_tracking.py:160` — `re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)", content, re.DOTALL)`
- `update_burndown.py:131` — `re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)`

These differ subtly: `sync_tracking` captures the body text after the second
`---`, while `update_burndown` does not. The value extraction was previously
duplicated too, but was correctly consolidated into `frontmatter_value()` at
`validate_config.py:883` (BH18-005). The regex for *splitting* the
frontmatter from the body remains duplicated.

**Recommendation:** Create a `parse_frontmatter(text) -> (frontmatter_str,
body_str)` helper in `validate_config.py`.

### 1E. Sprint Number Inference — Two Independent Implementations

Two functions infer sprint numbers from milestone files:

- `bootstrap_github._collect_sprint_numbers()` at line 80 — scans for
  `### Sprint (\d+):` patterns, falls back to filename digits
- `populate_issues._infer_sprint_number()` at line 172 — scans for
  `### Sprint (\d+):` patterns, falls back to filename digits

Both implement the same content-first-then-filename strategy. The comment at
`populate_issues.py:175` says "Priority matches
bootstrap_github._collect_sprint_numbers: content-first" — again,
acknowledging the duplication.

**Recommendation:** Extract to a shared helper in `validate_config.py`.

### 1F. `find_milestone` vs `find_milestone_number` — Near-Duplicate

- `validate_config.find_milestone()` at line 968 — queries milestones API,
  returns the full dict or None
- `release_gate.find_milestone_number()` at line 422 — queries the same
  milestones API, returns just the number or None

Both fetch the exact same API endpoint
(`repos/{owner}/{repo}/milestones --paginate`) and iterate the results.
`find_milestone_number` could trivially be implemented as:
```python
ms = find_milestone(sprint_num)
return ms["number"] if ms else None
```
...except it takes a title string instead of a sprint number. But the
underlying API call and iteration logic is the same.

### 1G. `_parse_closed` vs `closed_date` — Same Operation, Different Names

- `sync_tracking._parse_closed()` at line 132 — calls `parse_iso_date(iso)`
- `update_burndown.closed_date()` at line 29 — calls
  `parse_iso_date(issue.get("closedAt", ""), default="—")`

Both are thin wrappers around `parse_iso_date()` with slightly different
defaults. The only real difference is `closed_date` passes `default="—"`
while `_parse_closed` uses the default `default=""`.

### 1H. Test Case Heading Regex — Duplicated

- `traceability.py:26` — `TEST_CASE_HEADING = re.compile(r'^###\s+((?:TC|GP)-[\w-]+):\s*(.+)')`
- `test_coverage.py:39` — `_PLAN_TC_HEADING = re.compile(r'^###\s+((?:TC|GP)-[\w-]+):\s*(.+)')`

Identical regex, two different variable names.

---

## 2. Dead Code

### 2A. `_fm_val` Wrapper — Unnecessary Indirection

`update_burndown._fm_val()` at line 144:
```python
def _fm_val(frontmatter: str, key: str) -> str | None:
    # BH18-005: Delegate to shared frontmatter_value in validate_config.
    return frontmatter_value(frontmatter, key)
```

This is a one-line wrapper that adds no value. It exists solely because the
old function was refactored to delegate to the shared implementation but the
call sites weren't updated to call `frontmatter_value` directly. Call sites
at lines 135, 138, 139 all use `_fm_val`.

### 2B. `find_milestone_title` Wrapper — Unnecessary Indirection

`sync_tracking.find_milestone_title()` at line 30:
```python
def find_milestone_title(sprint_num: int) -> str | None:
    ms = find_milestone(sprint_num)
    return ms["title"] if ms else None
```

Another one-line wrapper. Only called from `main()` at line 347. The caller
could directly use `find_milestone()` and access `.get("title")`.

### 2C. `resolve_namespace` — Only Called by Tests

`validate_anchors.resolve_namespace()` at line 71 is a one-liner:
```python
def resolve_namespace(namespace: str) -> str:
    return NAMESPACE_MAP[namespace]
```

It's only ever called from `tests/test_validate_anchors.py`. The function
itself is just a dict lookup — `NAMESPACE_MAP[namespace]` — and doesn't add
any logic over directly accessing the dict. The internal code in
`check_anchors()` accesses `namespace_map[ns]` directly (line 154) without
using this function.

### 2D. `get_prd_dir`, `get_test_plan_dir`, `get_story_map` — Unused Outside Tests

These three functions in `validate_config.py` are defined but never called
from any production code:

- `get_prd_dir()` at line 760 — only used in `tests/test_hexwise_setup.py:156`
- `get_test_plan_dir()` at line 770 — only used in `tests/test_hexwise_setup.py:157`
- `get_story_map()` at line 836 — only used in `tests/test_hexwise_setup.py:160`

All three follow the same pattern as `get_epics_dir()` and `get_sagas_dir()`
(which ARE used by `bootstrap_github.py`). The scripts that consume these
paths (`traceability.py`, `test_coverage.py`, `team_voices.py`) access
`config.get("paths", {}).get("prd_dir")` directly instead of using the
accessor functions.

**Status:** Not dead code per se — they exist as a public API for skill
prompts and future use. But the inconsistency between scripts using accessors
vs raw dict access is notable.

### 2E. `_parse_closed` — Trivial Wrapper

`sync_tracking._parse_closed()` at line 132:
```python
def _parse_closed(iso: str) -> str:
    return parse_iso_date(iso)
```

A one-liner that just calls `parse_iso_date` with default arguments. Could
be replaced with `parse_iso_date(iso)` at the two call sites (lines 253,
319).

---

## 3. Unnecessary Complexity

### 3A. `check_prerequisites()` — Three Independent Implementations

Three scripts in `skills/sprint-setup/scripts/` each define their own
`check_prerequisites()` function:

- `bootstrap_github.py:18` — checks `gh --version`, `gh auth status`, `git remote -v`
- `populate_issues.py:37` — checks only `gh auth status`
- `setup_ci.py:339` — checks only `git rev-parse --show-toplevel`

Each runs `subprocess.run()` directly instead of using the shared `gh()`
helper. The checks overlap: bootstrap checks gh + auth + git remote;
populate_issues checks only auth; setup_ci checks only git.

**Recommendation:** Create one shared `check_prerequisites(needs_gh=True,
needs_git=True, needs_remote=True)` function. The existing `gh()` helper
already raises `RuntimeError` on failure, so the auth check is redundant —
the first `gh()` call will fail with a clear error if auth is missing.

### 3B. `splitlines()` vs `split('\n')` Inconsistency

The codebase has an explicit policy (documented in BH20-001 and BH20-005)
that `split('\n')` should be used instead of `splitlines()` to avoid
U+2028/U+2029 issues in TOML/markdown parsing. However, several scripts
still use `splitlines()`:

Using `splitlines()` (potential issue):
- `test_coverage.py:54` — parsing test plan markdown files
- `sprint_init.py:696` — parsing persona files
- `sprint_teardown.py:178` — parsing project.toml
- `validate_anchors.py:86,102,170,200,278` — parsing source files

Using `split('\n')` (correct per policy):
- `validate_config.py:146` — TOML parsing
- `validate_config.py:573` — team index parsing
- `traceability.py:44,92,115` — epic/test plan parsing
- `manage_epics.py:64` — epic parsing
- `manage_sagas.py:45` — saga parsing
- `team_voices.py:55` — voice extraction
- `bootstrap_github.py:142,177,260` — backlog/milestone parsing

The `splitlines()` uses may be safe in practice (these files are unlikely to
contain U+2028/U+2029), but the inconsistency is a maintenance hazard.

### 3C. `_count_sp` in check_status.py — Reimplements compute_velocity Logic

`check_status._count_sp()` at line 211 counts total and done SP from
issues:
```python
def _count_sp(issues):
    t = d = 0
    for i in issues:
        sp = extract_sp(i)
        t += sp
        if i.get("state") == "closed":
            d += sp
    return t, d
```

This is a simplified version of `sprint_analytics.compute_velocity()` at
line 40, which does the same SP counting plus story counts. The
`check_milestone()` function (line 172) also independently fetches the
issue list with `--json state,labels,body` — the same fields
`compute_velocity` needs.

---

## 4. Inconsistencies Between Scripts

### 4A. Naming: "story" vs "issue" vs "title" in Different Contexts

The codebase uses these terms inconsistently:

- `populate_issues.py` uses `Story` dataclass, `story_id`, `stories`
- `sync_tracking.py` uses `TF.story` (story ID), but `issue` for the GitHub
  dict
- `update_burndown.py` uses `sid` for story ID but `issues` for the list
- `check_status.py` uses `issues` throughout
- `sprint_analytics.py` uses `iss` for individual issues, `issues` for list

This is mostly a readability concern. The most confusing case is
`sync_tracking.py` where `issue` (GitHub API dict) and `tf.story` (story
ID string) are both in scope.

### 4B. Error Handling: `RuntimeError` vs Silent Skip vs `sys.exit(1)`

Different scripts handle `gh()` failures differently:

- `check_status.py` — catches `RuntimeError` with try/except, reports and
  continues checking other things (resilient approach)
- `sprint_analytics.py` — lets `RuntimeError` propagate, caught in `main()`
  which calls `sys.exit(1)`
- `sync_tracking.py` — returns empty list on failure
  (`_fetch_all_prs():48-49`)
- `release_gate.py` — each gate function handles its own errors, returns
  `(False, error_message)` tuple

The inconsistency is justified by the different use cases (monitor should
keep running; release gate should fail fast), but the pattern in
`_fetch_all_prs()` (silently returning `[]`) could mask real failures.

### 4C. Issue Fetching: Different JSON Fields Requested

Different scripts request different fields when fetching milestone issues:

- `list_milestone_issues()` at `validate_config.py:997`:
  `--json number,title,state,labels,closedAt,body`
- `compute_velocity()` at `sprint_analytics.py:47`:
  `--json state,labels,body,title`
- `check_milestone()` at `check_status.py:198`:
  `--json state,labels,body`

`sprint_analytics.compute_velocity()` and `compute_workload()` (line 135)
both fetch the same milestone's issues independently with different field
lists. `list_milestone_issues()` was created (BH-014) as a shared function
to avoid this, but `sprint_analytics.py` and `check_status.py` still use
their own `gh_json()` calls.

**Recommendation:** `sprint_analytics.compute_velocity()` and
`compute_workload()` should use `list_milestone_issues()` (which includes
all the fields they need) and share the result between them.

### 4D. Limit Values: 500 vs 1000

- `list_milestone_issues()` uses `--limit 1000` (validate_config.py:998)
- `compute_velocity()` uses `--limit 500` (sprint_analytics.py:48)
- `compute_workload()` uses `--limit 500` (sprint_analytics.py:139)
- `get_existing_issues()` uses `--limit 500` (populate_issues.py:333)
- `gate_stories()` uses `--limit 500` (release_gate.py:142)
- `gate_prs()` uses `--limit 500` (release_gate.py:177)

The shared `list_milestone_issues()` was upgraded to 1000 as part of
BH-014, but the scripts that don't use it still have the old 500 limit.

### 4E. Persona Label Parsing — Similar but Different

- `sprint_analytics.extract_persona()` at line 30 — extracts persona from
  `persona:name` labels, handling both string and dict label formats
- `kanban_from_labels()` at `validate_config.py:942` — extracts kanban
  state from `kanban:state` labels, handling both string and dict formats

Both functions iterate issue labels with the same pattern:
```python
for label in issue.get("labels", []):
    if isinstance(label, str):
        name = label
    elif isinstance(label, dict):
        name = label.get("name", "")
    else:
        continue
```

The label-name-extraction boilerplate is duplicated. A helper like
`label_names(issue) -> list[str]` would eliminate this.

---

## 5. Summary of Actionable Findings

### High Priority (Duplication with Divergence Risk)
1. Story ID extraction regex in `populate_issues.py:344` vs
   `validate_config.extract_story_id()` — should use the shared function
2. Closed-issue override triplicated across `sync_tracking` (2x) and
   `update_burndown` — should be in `kanban_from_labels()`
3. Sprint number inference duplicated between `bootstrap_github` and
   `populate_issues` — should be a shared helper

### Medium Priority (Dead Code / Unnecessary Wrappers)
4. `update_burndown._fm_val()` — delete, replace 3 call sites with
   `frontmatter_value()`
5. `sync_tracking.find_milestone_title()` — inline into caller
6. `sync_tracking._parse_closed()` — inline into callers
7. Test case heading regex duplicated between `traceability.py` and
   `test_coverage.py`

### Low Priority (Inconsistencies / Cleanup)
8. `check_prerequisites()` x3 — consolidate
9. `splitlines()` vs `split('\n')` inconsistency
10. Different `--limit` values (500 vs 1000)
11. `sprint_analytics` functions should use `list_milestone_issues()`
12. Label name extraction boilerplate could be a shared helper
