# Scripts Audit — Batch 3

Audited scripts (5 high-value production scripts):
- `scripts/sync_backlog.py` (267 LOC)
- `scripts/sprint_init.py` (1027 LOC)
- `skills/sprint-monitor/scripts/check_status.py` (616 LOC)
- `skills/sprint-release/scripts/release_gate.py` (776 LOC)
- `skills/sprint-setup/scripts/populate_issues.py` (565 LOC)

---

## Finding H3-001: Stem collision disambiguator only fixes the second file

**Severity:** MEDIUM
**Category:** Logic error
**Location:** `scripts/sprint_init.py:728-739` (`generate_team`)

**Problem:** When two persona files share the same stem (e.g., `docs/team/alice.md` and `design/team/alice.md`), only the *second* file gets disambiguated with a parent-directory prefix. The first file keeps the bare stem. This creates an asymmetric and confusing result: `team/alice.md` (symlink to docs/team/alice.md) and `team/design-alice.md` (symlink to the other). Worse, the first file's symlink is never retroactively renamed.

Additionally, if a *third* file also collides and its disambiguated stem matches one already in `seen_stems`, `seen_stems[stem]` silently overwrites the entry for the first file, losing the path mapping.

**Evidence:**
```python
for sf in personas:
    stem = Path(sf.path).stem
    if stem in seen_stems:
        parent = Path(sf.path).parent.name
        stem = f"{parent}-{stem}"
    seen_stems[stem] = sf.path       # overwrites if disambiguated stem collides
    resolved_stems[sf.path] = stem
```

Consider: `team/alice.md`, `design/alice.md`, `team-alice.md` (a file that already has this stem). The second `alice` gets disambiguated to `design-alice`, then `team-alice.md` keeps its stem `team-alice`. But if the order were different and `team-alice.md` came first, it would grab the `team-alice` stem, and then disambiguating the second `alice` to `team-alice` would collide again without detection.

---

## Finding H3-002: Partial failure in sync_backlog leaves ambiguous state

**Severity:** LOW
**Category:** State management
**Location:** `scripts/sync_backlog.py:239-251` (`main`)

**Problem:** When `do_sync` partially succeeds (some issues created, some failed), the code prints the failure count to stderr but then *also* prints the success count to stdout on line 250-251 unconditionally (outside the `if failed` block). The stdout message always runs, so a partial failure produces two messages: one to stderr saying "state NOT updated for retry" and one to stdout reporting the creation count. The stdout message does not indicate failure, which could mislead a monitor reading stdout.

**Evidence:**
```python
if failed:
    print(f"sync: created {counts['issues']} issues, "
          f"{failed} failed — state NOT updated for retry",
          file=sys.stderr)
else:
    state["file_hashes"] = current_hashes
    ...
print(f"sync: created {counts['issues']} issues, "   # always runs
      f"synced {counts['milestones']} milestones")
```

The second `print` at line 250 is not inside the `else` block. It runs for both success and partial failure.

---

## Finding H3-003: `_first_error` compiles regexes on every call

**Severity:** LOW
**Category:** Performance
**Location:** `skills/sprint-monitor/scripts/check_status.py:109-132` (`_first_error`)

**Problem:** `_first_error` is called once per failing CI run. Inside the function body, `_FALSE_POSITIVE`, `_ERROR_KW`, and `_ANSI_RE` are defined as local variables with `re.compile()`. Despite appearing constant, they are recompiled on every invocation because they are local assignments, not module-level constants. Python's internal regex cache (maxsize 512) mitigates this for small workloads, but the placement inside the function body is misleading — they look like constants but behave like locals.

This is cosmetic/performance, not a correctness bug.

---

## Finding H3-004: `parse_commits_since` with no tag fetches entire repo history

**Severity:** MEDIUM
**Category:** Resource exhaustion
**Location:** `skills/sprint-release/scripts/release_gate.py:60-80` (`parse_commits_since`)

**Problem:** When `find_latest_semver_tag()` returns `None` (no semver tags exist), `parse_commits_since(None)` runs `git log --format=...` with no range constraint. For large repositories, this fetches the entire commit history. The function then splits the entire output by a string delimiter and iterates every commit. On a repo with thousands of commits, this could consume significant memory and time.

The `calculate_version` function at line 132 has partial mitigation: if there's no tag, it returns `base` without bumping. But `parse_commits_since(tag)` has already been called and has fully parsed every commit in the repo. The parsed commits are passed to `generate_release_notes`, which iterates them all and categorizes them.

**Evidence:**
```python
if tag:
    cmd = ["git", "log", f"{tag}..HEAD", f"--format={fmt}"]
else:
    cmd = ["git", "log", f"--format={fmt}"]  # entire history
```

A reasonable mitigation: add `--max-count=500` or similar limit when no tag exists.

---

## Finding H3-005: `_COMMIT_DELIM` can appear in commit messages

**Severity:** LOW
**Category:** Fragile parsing
**Location:** `skills/sprint-release/scripts/release_gate.py:54-56`

**Problem:** The commit delimiter `---@@END-COMMIT@@---` is a plain text string. While unlikely, nothing prevents a commit message from containing this exact string (e.g., copy-pasting from this source file, or a commit that documents the release process). If it appears in a commit body, `parse_commits_since` would split the body into two chunks, producing a phantom commit with a corrupted subject line.

The comment acknowledges this: "must not appear in commit messages." But there is no validation or escaping to enforce this invariant. Git's `--format=%x00` (null byte) delimiter would be ideal but is correctly avoided due to Python subprocess limitations noted in the comment.

Practical risk is low — the delimiter is unusual enough that accidental collision is unlikely.

---

## Finding H3-006: `determine_bump` misses `feat!:` as a breaking change

**Severity:** LOW
**Category:** Spec compliance
**Location:** `skills/sprint-release/scripts/release_gate.py:83-100` (`determine_bump`)

**Problem:** The breaking change regex `^[a-z]+(\([^)]+\))?!:` correctly matches `feat!:` and `fix(scope)!:`. The feature regex `^feat(\([^)]+\))?:` matches `feat:` and `feat(scope):` but NOT `feat!:` (the `!` before `:` prevents the match). This means a `feat!:` commit is classified as a breaking change (correct) but is NOT added to the `feats` list in `generate_release_notes` (line 378: `^feat(\([^)]+\))?!?:`), which DOES include the `!?`. Wait — checking the release notes generator at line 378: `^feat(\([^)]+\))?!?:` — this one does have `!?`. So the classification in `generate_release_notes` is correct, but `determine_bump` at line 98 uses `^feat(\([^)]+\))?:` without `!?`, which means a `feat!:` commit won't set `bump` to `minor`. However, this is actually harmless because `feat!:` also matches the breaking change pattern at line 95, which immediately returns `"major"`, bypassing the feature check.

After further analysis: this is not actually a bug. The control flow is correct — `feat!:` triggers the breaking-change early return before the feature check. Withdrawing this as a finding; leaving it documented for completeness since the inconsistency between the two regexes (`determine_bump` vs `generate_release_notes`) could cause confusion during maintenance.

**Status:** NOT A BUG (false positive after deeper analysis)

---

## Finding H3-007: `extract_story_id` misses custom patterns without hyphens

**Severity:** MEDIUM
**Category:** Feature gap / silent wrong behavior
**Location:** `scripts/validate_config.py:972-986` (`extract_story_id`)

**Problem:** `extract_story_id` uses `^([A-Z]+-\d+)` as its primary regex — requiring a hyphen between the prefix and the number. Projects using custom story IDs without hyphens (e.g., `TASK1234` matching pattern `TASK\d{4}`) will fail this regex and fall through to the slug fallback. The slug fallback (`title.split(":")[0]`) will produce `TASK1234` by happenstance for well-formed titles like `TASK1234: Implement feature`, so it works accidentally. But for malformed titles it may produce wrong results.

This function is used by `get_existing_issues` (populate_issues.py:371) for deduplication. The comment at line 372 (BH39-001) explicitly accepts "any non-UNKNOWN ID" for this reason. But `extract_story_id` itself is a shared utility that other callers may use with different expectations.

The function is not config-aware — it cannot read `story_id_pattern` from project.toml. Adding that would require a breaking signature change.

---

## Finding H3-008: `find_milestone_number` only checks open milestones

**Severity:** MEDIUM
**Category:** API misuse
**Location:** `skills/sprint-release/scripts/release_gate.py:443-451` (`find_milestone_number`)

**Problem:** The GitHub milestones API defaults to `state=open`. If a milestone has already been closed (e.g., by a previous partial release attempt, or by manual action), `find_milestone_number` will not find it, and the release flow will print a warning but not close it (it's already closed, so this is actually fine). However, the `validate_gates` -> `gate_stories` check at the beginning of the release flow queries issues by milestone *title*, which works regardless of milestone state. This means a release could theoretically pass gate validation against a closed milestone and then fail to find it for the close step.

More importantly, `validate_config.find_milestone` (used by check_status.py) makes the same API call and also defaults to open milestones. If someone manually closes a milestone mid-sprint, the monitor's `check_milestone` will report "no milestone for Sprint N" even though the milestone exists (just closed).

**Evidence:**
```python
milestones = gh_json([
    "api", "repos/{owner}/{repo}/milestones?per_page=100", "--paginate",
])
# No state=all parameter — only returns open milestones
```

Neither `find_milestone_number` nor `find_milestone` passes `state=all`.

---

## Finding H3-009: `check_smoke` runs shell commands from config without trust-model documentation

**Severity:** LOW
**Category:** Security documentation gap
**Location:** `skills/sprint-monitor/scripts/check_status.py:301-305`

**Problem:** `check_smoke` executes `smoke_cmd` from the config with `shell=True`. The release_gate functions `gate_tests` and `gate_build` both have explicit trust-model documentation (BH18-003) explaining why `shell=True` is used and what the security implications are. `check_smoke` and `scripts/smoke_test.py:42` lack this documentation. The trust model is identical (user-configured commands in project.toml), but the documentation gap means a security reviewer might flag these as unreviewed.

Not a code bug — a documentation consistency gap.

---

## Finding H3-010: `_parse_workflow_runs` multiline block detection is fragile

**Severity:** LOW
**Category:** Parsing robustness
**Location:** `scripts/sprint_init.py:197-243` (`_parse_workflow_runs`)

**Problem:** The multiline run-block parser uses `lines[i].startswith("  ")` (2-space indent) to detect continuation lines. GitHub Actions YAML typically uses deeper indentation for run blocks (6-8 spaces), so this works in practice. But the parser also stops at blank lines *only if* they are followed by a non-indented line. A blank line within a multiline run block (common in shell scripts) would terminate collection prematurely — the `while` loop condition is `lines[i].startswith("  ") or lines[i].strip() == ""`, so blank lines continue the loop. Wait, re-reading: blank lines DO continue the loop (`lines[i].strip() == ""`), and are then skipped by the `if line_content` check. The actual exit condition is a non-indented, non-blank line.

The real fragility is the `re.match(r'^\s*- ', lines[i])` check that breaks on lines starting with `- ` inside a run block. A shell script in a run block like `run: |\n  echo "items:"\n  - item1` would incorrectly break. This is unlikely in practice but is a parsing robustness issue.

After analysis: risk is low because this is only used for CI command *detection* during `sprint-init` (not for execution), and the detected commands are presented to the user for review.

---

## Finding H3-011: `_build_detail_block_re` allows non-capturing groups that shift `split()` offsets

**Severity:** MEDIUM
**Category:** Regex injection / logic error
**Location:** `skills/sprint-setup/scripts/populate_issues.py:211-222, 233-238`

**Problem:** `_build_detail_block_re` wraps the user's pattern in a capturing group: `rf"^###\s+({pattern}):\s+(.+)$"`. This regex is used with `re.split()` at line 233: `parts = detail_re.split(content)`. When `re.split` uses a regex with capturing groups, the captured text is included in the result list. The default regex has 2 capturing groups (story_id, title), producing parts in groups of 3: `[preamble, id, title, body, id, title, body, ...]`. The iteration at line 235 (`range(1, len(parts), 3)`) depends on this exact grouping.

If the user's `story_id_pattern` contains non-capturing groups (which `_safe_compile_pattern` explicitly allows), the outer wrapping `({pattern})` is still just one capturing group, so `split()` still produces groups of 3. This is actually correct.

However, if the user's pattern were empty string `""`, `_safe_compile_pattern("")` would return `True` (empty string compiles, passes ReDoS probes), and the resulting regex `^###\s+():\s+(.+)$` would match lines like `### : title` with an empty story ID. This would create stories with empty `story_id` fields.

**Evidence:** `_safe_compile_pattern("")` returns True because:
- `re.search(r'(?<!\\)\((?!\?)', "")` finds no capturing groups
- `re.compile("")` succeeds
- The ReDoS probes all pass instantly

The empty-pattern case is unlikely (a user would need `story_id_pattern = ""` in their TOML, which is the default/absent value anyway — `backlog.get("story_id_pattern", "")` returns `""` and the caller checks `if pattern:` before calling). So the actual risk is zero because of the `if pattern:` guard at line 117. But the `_safe_compile_pattern` function itself does not reject empty patterns, which is a latent issue if called from a different context.

**Status:** Latent (guarded by caller, not by the function itself)

---

## Finding H3-012: `do_sync` calls `get_existing_issues` / `get_milestone_numbers` which can raise

**Severity:** LOW
**Category:** Error handling gap
**Location:** `scripts/sync_backlog.py:183-184` (`do_sync`)

**Problem:** `do_sync` calls `populate_issues.get_existing_issues()` and `populate_issues.get_milestone_numbers()`, both of which raise `RuntimeError` on API failure (lines 360-364 and 386-391 in populate_issues.py). These exceptions are not caught inside `do_sync` — they propagate to `main()` where `do_sync` is wrapped in a broad `except Exception` at line 233. This is technically handled, but the error message will be generic ("do_sync failed — ...") rather than indicating which specific API call failed.

This is minor because the `main()` catch-all does handle it. But if the API for existing issues fails, the sync correctly aborts rather than creating duplicates, which is the right behavior.

---

## Finding H3-013: `check_branch_divergence` passes `--jq` with `gh api` but result may be a string

**Severity:** LOW
**Category:** Type confusion
**Location:** `skills/sprint-monitor/scripts/check_status.py:406-418`

**Problem:** The `--jq` filter `{behind_by: .behind_by, ahead_by: .ahead_by}` produces a JSON object, which `gh_json` will parse into a dict. The function then checks `isinstance(data, list)` as an error case. But `gh_json` returns `list | dict`, and the `--jq` filter should always produce a dict. If the API returns an error (e.g., 404 for a deleted branch), `gh()` inside `gh_json` would raise `RuntimeError`, caught at line 432. If the API succeeds but the compare endpoint returns an unexpected shape, `--jq` would produce `null` values for the fields, and `data.get("behind_by", 0)` would return `None`, not `0`. Then `behind > 20` would raise `TypeError` because `None > 20` is not valid.

**Evidence:**
```python
data = gh_json([
    "api", f"repos/{repo}/compare/{base_branch}...{branch}",
    "--jq", "{behind_by: .behind_by, ahead_by: .ahead_by}",
])
# ...
behind = data.get("behind_by", 0)  # could be None if jq field is null
if behind > 20:                      # TypeError: '>' not supported for NoneType
```

The `except (RuntimeError, OSError, ValueError)` in `main()` at line 590 would NOT catch `TypeError`, which would crash the entire monitor.

---

## Finding H3-014: Release rollback on GitHub Release failure leaves tag on remote

**Severity:** LOW
**Category:** Incomplete rollback
**Location:** `skills/sprint-release/scripts/release_gate.py:672-678`

**Problem:** When the GitHub Release creation fails (line 674), the code calls `_rollback_tag()` and `_rollback_commit()`. The `_rollback_tag` function deletes the tag locally and from the remote. But the version bump commit has already been pushed (line 634-641, `pushed_to_remote = True`). The `_rollback_commit` will then do a `git revert HEAD` and push. This creates a sequence: push commit, push tag, delete tag from remote, revert commit, push revert. The result is correct but leaves a revert commit in the history. This is the documented behavior ("Revert is safer than force-push for shared branches") and is acceptable.

However, there is a subtle race: if another developer pulls between the push at line 634 and the rollback at line 675, they will have the version bump commit and the tag. The revert will arrive later, but the tag deletion might fail if someone has already fetched it. This is inherent to the revert approach and is not fixable without force-push, which the code correctly avoids.

**Status:** Accepted design tradeoff (documented)

---

## Finding H3-015: `_infer_sprint_number` silent fallback to sprint 1

**Severity:** LOW
**Category:** Silent wrong behavior
**Location:** `skills/sprint-setup/scripts/populate_issues.py:180-200`

**Problem:** When a milestone file has no `### Sprint N:` headings and no number in its filename, `_infer_sprint_number` defaults to sprint 1 with a warning. Stories from this file will all be assigned to sprint 1. If sprint 1 already exists with its own stories, these orphaned stories will be mixed in, potentially assigned to the wrong milestone on GitHub.

The function does print a warning (BH24-035), so the user has visibility. But the warning goes to stderr, which may not be visible in all contexts (e.g., when called from `sync_backlog`).

---

## Finding H3-016: `hash_milestone_files` uses filename as key, losing path context

**Severity:** LOW
**Category:** Key collision
**Location:** `scripts/sync_backlog.py:46-55` (`hash_milestone_files`)

**Problem:** The hash dict uses `p.name` (filename only) as the key. If two milestone files in different directories have the same filename (e.g., `backlog/milestones/sprint-1.md` and `backlog/archive/sprint-1.md`), only the last one's hash would be stored. In practice this is unlikely because `get_milestones()` only reads from a single `milestones/` directory, but the function signature accepts any `list[str]` of paths.

---

## Summary

| ID | Severity | Location | Problem |
|----|----------|----------|---------|
| H3-001 | MEDIUM | sprint_init.py:728-739 | Stem collision disambiguator only fixes second file; triple collision undetected |
| H3-002 | LOW | sync_backlog.py:239-251 | Partial failure prints success message to stdout alongside error to stderr |
| H3-003 | LOW | check_status.py:109-132 | Regex constants compiled per call inside function body |
| H3-004 | MEDIUM | release_gate.py:60-80 | No-tag case fetches entire repo history into memory |
| H3-005 | LOW | release_gate.py:54-56 | Commit delimiter could appear in commit messages |
| H3-006 | — | release_gate.py:83-100 | WITHDRAWN: `feat!:` handling is correct after control flow analysis |
| H3-007 | MEDIUM | validate_config.py:972-986 | `extract_story_id` not config-aware; works accidentally for unhyphenated IDs |
| H3-008 | MEDIUM | release_gate.py:443-451 | `find_milestone_number` only returns open milestones |
| H3-009 | LOW | check_status.py:301-305 | Shell command trust model undocumented (documented in release_gate but not here) |
| H3-010 | LOW | sprint_init.py:197-243 | Workflow parser fragile on shell-script-like content in run blocks |
| H3-011 | MEDIUM | populate_issues.py:211-238 | Empty pattern latent issue in `_safe_compile_pattern` (guarded by caller) |
| H3-012 | LOW | sync_backlog.py:183-184 | API errors in `do_sync` produce generic messages |
| H3-013 | LOW | check_status.py:406-418 | `None` from jq null fields causes `TypeError` crash, uncaught by exception handler |
| H3-014 | LOW | release_gate.py:672-678 | Accepted: rollback leaves revert commit in history |
| H3-015 | LOW | populate_issues.py:180-200 | Silent fallback to sprint 1 may misfile stories |
| H3-016 | LOW | sync_backlog.py:46-55 | Hash key uses filename only, losing directory context |

**Counts:** 4 MEDIUM, 11 LOW, 1 WITHDRAWN
**Top-priority fixes:** H3-001 (stem collision), H3-004 (unbounded git log), H3-008 (open-only milestones), H3-013 (TypeError crash in monitor)
