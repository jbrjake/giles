# Code Audit Batch 2: Setup, Burndown, Epic/Saga Management, Traceability, and Anchors

**Scope:** 9 scripts in `skills/sprint-setup/scripts/`, `skills/sprint-run/scripts/`, and `scripts/`.
**Auditor:** Claude (adversarial code review)
**Date:** 2026-03-15

---

## Summary

| Severity | Count |
|----------|-------|
| HIGH     | 3     |
| MEDIUM   | 9     |
| LOW      | 6     |

---

## Findings

### Finding 1: Separator rows leak into metadata dict (manage_epics + manage_sagas)
- **File:** `scripts/manage_epics.py:70-86` and `scripts/manage_sagas.py:65-77`
- **Category:** bug/logic
- **Severity:** MEDIUM
- **Problem:** `_parse_header_table` in both scripts uses `TABLE_ROW` to match metadata rows and filters out fields named `"Field"`, `"---"`, or `""`. But markdown separator rows like `|-------|-------|` match `TABLE_ROW` with `field="-------"`, which is NOT in the filter set. This pollutes the metadata dict with a garbage key-value pair like `{"-------": "-------"}`.
- **Evidence:**
  ```python
  TABLE_ROW = re.compile(r'^\|\s*(.+?)\s*\|\s*(.+?)\s*\|')
  # ...
  if field not in ("Field", "---", ""):
      metadata[field] = value
  ```
  Tested: `TABLE_ROW.match("|-------|-------|")` produces `field="-------"`, `value="-------"`.
- **Impact:** The polluted metadata dict causes `_safe_int(metadata.get("-------", "0"))` to be harmless for integer lookups, but any code that iterates over `metadata.keys()` will see the separator row as a valid field. The `stories_count` and `total_sp` values are unaffected (they look up specific keys), but `parse_saga` returns the raw metadata in its section data, so consumers could be confused.

### Finding 2: `renumber_stories` is vulnerable to regex replacement injection
- **File:** `scripts/manage_epics.py:347-363`
- **Category:** bug/security
- **Severity:** HIGH
- **Problem:** `renumber_stories` uses `re.sub()` with user-supplied `new_ids` as the replacement string without escaping. In Python's `re.sub`, the replacement string interprets `\1`, `\2`, etc. as backreferences. If any `new_id` contains a backslash followed by a digit, `re.sub` raises `re.error` (crash) or silently performs unintended substitution.
- **Evidence:**
  ```python
  replacement = ", ".join(new_ids)
  new_lines.append(re.sub(rf'\b{re.escape(old_id)}\b', replacement, line))
  ```
  Tested: `new_ids = [r"US-01\1a"]` causes `re.error: invalid group reference 1 at position 6`.
- **Impact:** Crash on any story ID containing a backslash (admittedly unusual, but the CLI accepts arbitrary arguments). The fix is to use `replacement.replace("\\", "\\\\")` or use a lambda: `re.sub(pat, lambda m: replacement, line)`.

### Finding 3: `update_sprint_status` regex drops the last line when file lacks trailing newline
- **File:** `skills/sprint-run/scripts/update_burndown.py:108`
- **Category:** bug/logic
- **Severity:** MEDIUM
- **Problem:** The regex `r"## Active Stories[^\n]*\n(?:(?!\n## )[^\n]*\n)*"` requires each captured line to end with `\n`. If the Active Stories section is the last section in the file and the file doesn't end with a trailing newline, the final table row is NOT matched by the regex. After `re.sub`, the old final row persists as an orphan below the new table.
- **Evidence:**
  ```python
  pattern = r"## Active Stories[^\n]*\n(?:(?!\n## )[^\n]*\n)*"
  ```
  Tested: with input ending in `| US-0001: Setup | done | Alice | #1 |` (no trailing newline), the regex captures the header and separator rows but drops the last data row.
- **Impact:** Orphaned old table row appears below the freshly-generated table. The burndown.md file is fine (written fresh), but SPRINT-STATUS.md accumulates stale rows on repeated updates if the file lacks a trailing newline.

### Finding 4: CI command YAML injection via newlines in `check_commands`
- **File:** `skills/sprint-setup/scripts/setup_ci.py:94-113`
- **Category:** bug/security
- **Severity:** HIGH
- **Problem:** `generate_ci_yaml` interpolates CI commands from `project.toml` directly into YAML string concatenation without any escaping or quoting. If a command in `check_commands` contains a newline character, the resulting YAML would have arbitrary injected keys. Since `project.toml` is read from the project's own config (not untrusted input), this is a self-inflicted injection vector rather than an external attack, but it can produce an invalid or dangerous CI workflow.
- **Evidence:**
  ```python
  def _generate_check_job(name, command, setup, needs=None):
      return f"""\
    {slug}:
      ...
        run: {command}
  """
  ```
  A `command` value of `"cargo test\n    env:\n      SECRET: stolen"` would inject an `env:` block into the YAML.
- **Impact:** Generated CI workflow could contain unintended steps, environment variables, or syntax errors. The TOML parser may strip newlines from string values, reducing exploitability, but multi-line TOML strings (`"""..."""`) could bypass this.

### Finding 5: `check_prerequisites` is copy-pasted across 3 scripts
- **File:** `skills/sprint-setup/scripts/bootstrap_github.py:18-41`, `skills/sprint-setup/scripts/setup_ci.py:317-325`, `skills/sprint-setup/scripts/populate_issues.py:37-43`
- **Category:** design/duplication
- **Severity:** LOW
- **Problem:** Three separate scripts each define their own `check_prerequisites()` function with different subsets of checks (bootstrap_github checks gh + auth + remote; setup_ci checks git repo; populate_issues checks gh auth only). The shared `validate_config.py` already provides `gh()` which wraps the CLI, but there's no shared prerequisite checker. Each script's checks are slightly inconsistent: bootstrap_github uses raw `subprocess.run` while the rest of the code uses the shared `gh()` wrapper.
- **Evidence:** Three definitions of `check_prerequisites()` with different behaviors.
- **Impact:** If prerequisite checks need updating (e.g., to check minimum `gh` version), three files need changing independently.

### Finding 6: Rust test pattern misses functions with doc comments between `#[test]` and `fn`
- **File:** `scripts/test_coverage.py:23`
- **Category:** bug/logic
- **Severity:** MEDIUM
- **Problem:** The Rust test pattern `#\[(?:test|...)\]\s*(?:#\[.*\]\s*)*(?:async\s+)?fn\s+(\w+)` allows `#[...]` attributes between the test attribute and the function, but does not account for `///` doc comments or `//` line comments. In real Rust code, doc comments between `#[test]` and `fn` are valid and break the pattern.
- **Evidence:**
  ```python
  _TEST_PATTERNS["rust"] = re.compile(
      r'#\[(?:test|tokio::test|async_std::test)\]\s*(?:#\[.*\]\s*)*(?:async\s+)?fn\s+(\w+)'
  )
  ```
  Tested: `#[test]\n/// Documentation\nfn test_with_doc() {}` produces zero matches.
- **Impact:** Documented test functions in Rust projects are silently excluded from the coverage report, making coverage appear lower than it actually is.

### Finding 7: JavaScript test pattern misses template literals, `test.each`, and `it.skip`
- **File:** `scripts/test_coverage.py:25`
- **Category:** bug/logic
- **Severity:** MEDIUM
- **Problem:** The JavaScript test pattern `(?:it|test)\s*\(\s*[\'"]([^\'"]+)` only matches single/double-quoted test names. It misses: (1) template literal test names `` test(`name`) ``, (2) parameterized tests `test.each(...)('name')`, (3) modified tests `it.skip('name')`, `it.only('name')`.
- **Evidence:**
  ```python
  _TEST_PATTERNS["javascript"] = re.compile(r'(?:it|test)\s*\(\s*[\'"]([^\'"]+)')
  ```
  Tested: `test.each`, `it.skip`, and template literal patterns all return zero matches.
- **Impact:** Test function count is under-reported for JavaScript/TypeScript projects using these common Jest/Vitest patterns.

### Finding 8: JavaScript test file patterns miss `__tests__` directory convention
- **File:** `scripts/test_coverage.py:33`
- **Category:** bug/logic
- **Severity:** LOW
- **Problem:** `_TEST_FILE_PATTERNS["javascript"]` only includes `**/*.test.*` and `**/*.spec.*` glob patterns. Projects using the `__tests__/` directory convention (common in React/Jest) where test files are named `component.ts` (without `.test.` or `.spec.`) are not scanned.
- **Evidence:**
  ```python
  "javascript": ["**/*.test.*", "**/*.spec.*"],
  ```
- **Impact:** Test functions in `__tests__/` directory-based projects are invisible to the coverage checker unless they also use `.test.` or `.spec.` in their filenames.

### Finding 9: Rust test pattern misses `rstest` and `proptest` frameworks
- **File:** `scripts/test_coverage.py:23`
- **Category:** bug/logic
- **Severity:** LOW
- **Problem:** The Rust test pattern only recognizes `#[test]`, `#[tokio::test]`, and `#[async_std::test]`. The `rstest` crate (`#[rstest]`) and `proptest!` macro are popular test frameworks that are not detected.
- **Evidence:**
  ```python
  re.compile(r'#\[(?:test|tokio::test|async_std::test)\]...')
  ```
  Tested: `#[rstest]\nfn test_rstest() {}` returns zero matches.
- **Impact:** Projects using `rstest` for parameterized testing have those tests excluded from coverage reports.

### Finding 10: `_find_section_ranges` silently overwrites duplicate section headings
- **File:** `scripts/manage_sagas.py:126-147`
- **Category:** bug/logic
- **Severity:** MEDIUM
- **Problem:** `_find_section_ranges` builds a dict keyed by section heading text. If a saga file has two `## Team Voices` sections (e.g., one per epic sub-section), only the LAST section's range is retained. The first section's range is silently lost. Any subsequent `update_team_voices` call would only modify the second section, orphaning the first.
- **Evidence:**
  ```python
  ranges: dict[str, tuple[int, int]] = {}
  # ...
  ranges[current_section] = (current_start, i)
  ```
  Tested: duplicate `## Team Voices` headings result in only the second one being stored.
- **Impact:** Section updates silently target the wrong (last) section. Content in earlier duplicate sections becomes stale and unreachable by update functions.

### Finding 11: `update_epic_index` epic ID extraction assumes `E-NNNN` filename format
- **File:** `scripts/manage_sagas.py:206-210`
- **Category:** bug/logic
- **Severity:** LOW
- **Problem:** The epic filename parsing splits on `-` and reconstructs the ID as `f"{parts[0]}-{parts[1]}"`. This works for `E-0101-name.md` but produces incorrect IDs for any non-standard filename that has more than one meaningful segment before the numeric part (e.g., `my-epic-0101.md` produces `my-epic` instead of `epic-0101`).
- **Evidence:**
  ```python
  parts = md_file.stem.split("-")
  if len(parts) < 2:
      continue
  epic_id = f"{parts[0]}-{parts[1]}"
  ```
- **Impact:** Non-standard epic filenames produce wrong epic IDs in the saga's Epic Index table. The `E-NNNN` convention is documented, so this is a low-priority edge case, but the code doesn't validate the format before constructing the ID.

### Finding 12: `create_milestones_on_github` uses `repos/{owner}/{repo}` API path template
- **File:** `skills/sprint-setup/scripts/bootstrap_github.py:249-254`
- **Category:** bug/logic
- **Severity:** HIGH
- **Problem:** The API call uses `repos/{owner}/{repo}/milestones` as the endpoint path. The `gh api` command expands `{owner}` and `{repo}` template variables automatically only when using `gh api` (it's a feature of the `gh` CLI). However, the `gh()` wrapper in `validate_config.py` passes these as raw subprocess args. If the `gh` CLI's template expansion ever changes or if the shell context doesn't have the right git remote, the literal string `{owner}/{repo}` is sent to the API, resulting in a 404 error. Meanwhile, `create_label` uses `gh label create` (a higher-level subcommand that auto-detects the repo), creating an inconsistency in how the repo is resolved.
- **Evidence:**
  ```python
  api_args = [
      "api", "repos/{owner}/{repo}/milestones",
      "-f", f"title={title}",
      "-f", f"description={description}",
      "-f", "state=open",
  ]
  gh(api_args)
  ```
- **Impact:** Milestone creation fails with a confusing 404 if `gh api` cannot resolve the template variables. The `label create` commands succeed because they use a different code path. This inconsistency means a partial bootstrap can occur (labels created, milestones fail).

### Finding 13: `VOICE_PATTERN` doesn't handle multi-line quoted text
- **File:** `scripts/team_voices.py:27`
- **Category:** bug/logic
- **Severity:** LOW
- **Problem:** `VOICE_PATTERN` is anchored to `$` (end of line) and only matches a single line. If a persona quote spans multiple lines within a blockquote (without a continuation `>`), the initial match captures only the first line. The continuation logic (lines 70-78) does handle `>` continuation lines, but a multi-line quote without `>` prefixes on subsequent lines would lose the trailing content.
- **Evidence:**
  ```python
  VOICE_PATTERN = re.compile(
      r'^>\s*\*\*([^*]+?):\*\*\s*(?:"(.+)"|(.+?))\s*$'
  )
  ```
  The continuation loop checks `lines[i + 1].startswith(">")`, so non-blockquote continuation lines are ignored.
- **Impact:** Persona quotes that wrap across lines without blockquote markers are truncated. This is likely rare given the expected markdown format, but possible with manual editing.

### Finding 14: `validate_anchors.py` missing `prerequisites-checklist` from `NAMESPACE_MAP`
- **File:** `scripts/validate_anchors.py:23-67`
- **Category:** doc/drift
- **Severity:** LOW
- **Problem:** `CLAUDE.md` references `prerequisites-checklist.md` in its Reference Files table, but `NAMESPACE_MAP` in `validate_anchors.py` does not include a mapping for `prerequisites-checklist`. If any `§prerequisites-checklist.*` anchors are added to CLAUDE.md or CHEATSHEET.md, the validator would report them as "unknown namespace" errors. This is currently a latent issue since no `§` references to this namespace exist yet, but it represents drift between the documented file set and the validator's awareness.
- **Evidence:** `NAMESPACE_MAP` has entries for `github-conventions`, `ci-workflow-template`, and `release-checklist` but not `prerequisites-checklist`.
- **Impact:** No current breakage, but anchor references to `prerequisites-checklist.md` would be unresolvable by the validator.

### Finding 15: `_parse_stories` in manage_epics doesn't handle separator rows in story metadata tables
- **File:** `scripts/manage_epics.py:90-163`
- **Category:** bug/logic
- **Severity:** MEDIUM
- **Problem:** The story metadata parser within `_parse_stories` has a dedicated check for separator rows (`re.match(r'^\|[-:\s|]+\|$', lines[j])`), but the `TABLE_ROW` regex on line 117 fires FIRST for rows like `|-------|-------|` (since it matches before the separator check on line 126). This means the separator row's content (`"-------"`) is stored as a metadata field before the separator-specific branch can execute.
- **Evidence:**
  ```python
  while j < len(lines):
      row = TABLE_ROW.match(lines[j])  # Line 117 - matches separator!
      if row:
          field = row.group(1).strip()
          # ...stores "-------" as a field
      elif re.match(r'^\|[-:\s|]+\|$', lines[j]):  # Line 126 - never reached
          in_meta_table = True
  ```
  The `elif` on line 126 is dead code because `TABLE_ROW` always matches separator rows first.
- **Impact:** Story metadata dicts contain garbage entries from separator rows. Since the metadata is accessed by specific key names (`"Story Points"`, `"Priority"`, etc.), the garbage entries are typically ignored, but they pollute the data structure.

### Finding 16: `parse_requirements` only scans files named exactly `reference.md`
- **File:** `scripts/traceability.py:114`
- **Category:** design/inconsistency
- **Severity:** MEDIUM
- **Problem:** `parse_requirements` uses `prd_path.rglob("reference.md")` to find PRD files. This means it ONLY scans files named exactly `reference.md` in subdirectories. Files named `requirements.md`, `prd-section-1.md`, or any other convention are silently ignored. The docstring says "PRD reference files" but doesn't clarify this naming constraint.
- **Evidence:**
  ```python
  for md_file in sorted(prd_path.rglob("reference.md")):
  ```
- **Impact:** Projects that organize their PRD files with different naming conventions get zero requirements in the traceability report, with no warning. The requirement count shows 0 and all requirements appear to "have story links" (vacuously true).

### Finding 17: `check_test_coverage` fuzzy slug matching produces false positives on short IDs
- **File:** `scripts/test_coverage.py:121-134`
- **Category:** bug/logic
- **Severity:** MEDIUM
- **Problem:** The fuzzy matching splits test case IDs into a "slug" by removing the prefix before the first underscore. For short IDs like `TC-E-1`, the slug becomes `e_1`. The word-boundary regex `(?:^|_)e_1(?:$|_)` can match unrelated test functions like `test_type_e_1_setup` where `e_1` appears as a coincidental substring between underscores.
- **Evidence:**
  ```python
  parts = normalized.split("_", 1)
  slug = parts[1] if len(parts) > 1 else normalized
  slug_re = re.compile(r"(?:^|_)" + re.escape(slug) + r"(?:$|_)")
  ```
  Tested: `TC-E-1` with slug `e_1` matches `test_type_e_1_setup` (false positive).
- **Impact:** Short test case IDs report false coverage matches, making it appear that tests are implemented when they are not. This undermines the purpose of the coverage checker.

### Finding 18: `bootstrap_github.py` uses raw `subprocess.run` alongside shared `gh()` wrapper
- **File:** `skills/sprint-setup/scripts/bootstrap_github.py:20-39`
- **Category:** design/inconsistency
- **Severity:** LOW
- **Problem:** `check_prerequisites` in `bootstrap_github.py` uses raw `subprocess.run(["gh", ...])` for three separate checks, while the rest of the script (and the codebase) uses the shared `gh()` wrapper from `validate_config.py`. The wrapper provides consistent timeout handling and error formatting. Using raw subprocess bypasses these guarantees.
- **Evidence:**
  ```python
  result = subprocess.run(["gh", "--version"], capture_output=True, text=True)
  # vs.
  gh(["label", "create", name, ...])
  ```
- **Impact:** Inconsistent error handling. If `gh` hangs during prerequisite checks, there's no timeout, unlike the rest of the script which has a 60-second timeout via the wrapper.

---

## Cross-Cutting Observations

### TABLE_ROW regex is fragile across the codebase
The pattern `r'^\|\s*(.+?)\s*\|\s*(.+?)\s*\|'` is used in both `manage_epics.py` and `manage_sagas.py` (and also in `traceability.py`). It matches markdown separator rows as data rows, and the downstream filters (`field not in ("Field", "---", "")`) fail to catch all separator formats. A shared utility function with proper separator detection would fix this across all scripts.

### Test coverage detection has significant language-specific gaps
The `test_coverage.py` script covers the happy path for each language but misses real-world patterns: Rust doc-commented tests, JavaScript parameterized tests, template literals, and directory-based test conventions. The fuzzy matching strategy (slug substring) can produce both false positives and false negatives depending on ID length and test naming conventions.

### Section-based markdown editing is fragile
Both `manage_sagas.py` and `update_burndown.py` use regex or line-range based section replacement. These approaches break on edge cases: duplicate headings, missing trailing newlines, extra text in heading lines. A shared section-editing utility with normalization would improve reliability.
