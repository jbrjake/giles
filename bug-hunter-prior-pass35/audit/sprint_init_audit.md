# Bug Hunter Pass 35: sprint_init.py Audit

**File under audit:** `scripts/sprint_init.py` (~997 lines)
**Date:** 2026-03-21
**Scope:** Error paths, boundary conditions, regex, file I/O, logic errors, data flow, symlinks

---

## BH35-001: No-backlog projects fail self-validation (missing milestones/ dir)

**File:** `scripts/sprint_init.py:758-760`
**Severity:** HIGH

When `generate_backlog()` detects no backlog files, it copies only the `backlog/INDEX.md` skeleton and returns early. It does NOT create `backlog/milestones/`. But `validate_project()` in `validate_config.py:573-584` requires `backlog/milestones/` to exist as a directory, and requires at least one `.md` file inside it.

The `main()` function at line 982 calls `validate_project()` after generation and exits with code 1 on failure. So for any project with no detectable backlog files (e.g., a brand new project), `sprint_init` crashes with "Self-validation FAILED. This is a bug in sprint_init.py" and exits 1.

**How to trigger:** Run `sprint_init` on any project directory that has no markdown files with both sprint headers and story rows.

**Why it matters:** New projects are exactly the use case where sprint_init should succeed gracefully, scaffolding empty structures for the user to fill in. Instead, it fails its own validation and tells users to file a bug report.

**Fix:** In `generate_backlog()`, when no files are found, also create `backlog/milestones/` and copy a milestone skeleton template into it:
```python
if not files:
    self._copy_skeleton("backlog-index.md.tmpl", "backlog/INDEX.md")
    self._ensure_dir(self.config_dir / "backlog" / "milestones")
    self._copy_skeleton("milestone.md.tmpl", "backlog/milestones/milestone-1.md")
    return
```

**Test coverage gap:** No test generates config from a project with zero backlog files and then calls `validate_project`. `test_pipeline_scripts.py:1309` tests that detection returns empty, but never generates+validates.

---

## BH35-002: definition-of-done.md overwritten on re-run (data loss)

**File:** `scripts/sprint_init.py:807-810`
**Severity:** HIGH

`generate_definition_of_done()` unconditionally calls `_copy_skeleton()`, which overwrites any existing file. The DoD is documented as "evolving" content ("baseline + retro-driven additions" per CLAUDE.md). During retros, Giles appends new DoD criteria. Re-running `sprint_init` (e.g., after adding new personas or backlog files) silently destroys all retro-driven DoD additions.

Compare with `generate_project_toml()` (line 602-605) which has an explicit preservation check, and `_inject_giles()` (line 749-753) which preserves user-customized files. `generate_definition_of_done` has neither.

**How to trigger:** Run a few sprints with retros that add DoD criteria, then re-run `sprint_init` to add a new persona.

**Why it matters:** The DoD accumulates valuable project-specific quality criteria over multiple sprints. Losing it silently defeats the structured process improvement loop that's central to the plugin's value.

**Fix:** Add an existence check matching the pattern used by `generate_project_toml`:
```python
def generate_definition_of_done(self) -> None:
    dest = self.config_dir / "definition-of-done.md"
    if dest.is_file():
        self.skipped.append("  preserved  definition-of-done.md (already exists)")
        return
    self._copy_skeleton("definition-of-done.md.tmpl", "definition-of-done.md")
```

---

## BH35-003: Scanner does not exclude sprint-config/ from scans (false detections on re-run)

**File:** `scripts/sprint_init.py:28-31, 130-142`
**Severity:** MEDIUM

`EXCLUDED_DIRS` does not include `"sprint-config"`. On re-run, `_glob_md()` scans all markdown files under `sprint-config/`, including:

- `sprint-config/team/INDEX.md` has `| Name | ... | Role |` headers, matching `detect_team_index` (line 331)
- `sprint-config/team/giles.md` has `## Origin Story`, `## Professional Identity`, `## Personality and Quirks`, `## Improvisation Notes` (4 rich persona headings >= 3 threshold), matching `detect_persona_files`
- `sprint-config/backlog/milestones/*.md` are symlinks to real milestone files, so they'd be scanned twice by `detect_backlog_files`
- Skeleton stubs contain `## Requirements` and could match `detect_prd_dir`

The Giles detection is mitigated by the stem filter at line 714, but other detections are not. Double-counting milestone files inflates confidence scores. Generated INDEX files could be detected as the "real" team index.

**How to trigger:** Run `sprint_init` twice on the same project.

**Fix:** Add `"sprint-config"` to `EXCLUDED_DIRS`.

---

## BH35-004: binary_path TOML value not escaped

**File:** `scripts/sprint_init.py:674-675`
**Severity:** MEDIUM

The `binary_path` value in the generated TOML is constructed by string replacement without passing through `_esc()`:
```python
lines.append(
    f'binary_path = "{s.binary_path.value.replace("<name>", name)}"')
```

The `name` variable comes from `project_name.value`, which can be a directory name fallback (line 261). If the project name contains `"`, `\`, or newline characters, the resulting TOML is malformed and will fail to parse.

**How to trigger:** Create a Rust project in a directory whose name contains a backslash or double quote, then run `sprint_init`.

**Why it matters:** Invalid TOML causes `validate_project` to fail, and `load_config` to raise `ConfigError`. All skills become unusable until the user manually fixes the TOML.

**Fix:** Use `_esc()`:
```python
lines.append(
    f'binary_path = "{esc(s.binary_path.value.replace("<name>", name))}"')
```

---

## BH35-005: Persona stem collision silently overwrites symlinks

**File:** `scripts/sprint_init.py:720-732`
**Severity:** MEDIUM

`generate_team()` creates symlinks using only the file stem:
```python
name = Path(sf.path).stem
self._symlink(f"team/{name}.md", sf.path)
```

If two persona files in different directories have the same stem (e.g., `docs/team/alice.md` and `docs/personas/alice.md`), the second `_symlink` call silently unlinks the first and replaces it. The team INDEX would list both "Alice" entries pointing to `alice.md`, but the symlink only points to one of them.

**How to trigger:** Have two persona files with the same filename in different directories (e.g., a backup copy of a persona file in another location that also has the required headings).

**Why it matters:** A persona file that was detected and logged as "found" would silently not be available in the config. The INDEX would claim it exists but the symlink would point elsewhere.

**Fix:** Detect stem collisions and disambiguate (e.g., prepend parent directory name).

---

## BH35-006: detect_prd_dir content scan crashes on unreadable files

**File:** `scripts/sprint_init.py:386`
**Severity:** MEDIUM

The content scan in `detect_prd_dir` reads the first markdown file without error handling:
```python
sample = md_files[0].read_text(encoding="utf-8", errors="replace")[:2000]
```

If this file is unreadable (permissions, broken symlink), `read_text()` raises `OSError` and the entire `scan()` call crashes. Compare with `detect_backlog_files()` at line 344-346 which wraps its read in `try/except OSError`.

**How to trigger:** Have a directory matching PRD name candidates (`docs/prd`, etc.) that doesn't exist, but have a directory with 2+ markdown files where the first one is a broken symlink or permission-denied.

**Fix:** Wrap in try/except:
```python
try:
    sample = md_files[0].read_text(encoding="utf-8", errors="replace")[:2000]
except OSError:
    continue
```

---

## BH35-007: `_parse_workflow_runs` doesn't handle `|-` block scalar indicator

**File:** `scripts/sprint_init.py:219`
**Severity:** MEDIUM

The multiline block detection checks:
```python
if cmd in ("|", "", ">", ">-"):
```

This handles `|`, `>`, and `>-` but NOT `|-` (literal block with strip) or `|+` (literal block with keep). `|-` is commonly used in GitHub Actions workflows to strip trailing newlines from multiline run blocks.

When a workflow has `run: |-`, the code treats `"-"` as a literal single-line command and adds it to the CI commands list. This pollutes the generated `check_commands` array with an invalid `"-"` entry.

Wait -- re-reading the code: `cmd = run_line[4:].strip()` extracts everything after `run:`. For `run: |-`, `cmd` would be `"|-"`. Since `"|-"` is not in `("|", "", ">", ">-")`, it falls to the `else` branch and adds `"|-"` as a CI command.

**How to trigger:** Any GitHub Actions workflow using `run: |-` (a common pattern).

**Fix:** Extend the check to include `|-`, `|+`, `>+`:
```python
if cmd in ("|", "|-", "|+", "", ">", ">-", ">+"):
```
Or better, use a regex: `if re.match(r'^[|>][-+]?$', cmd) or cmd == "":`.

---

## BH35-008: Backlog INDEX.md links are relative to project root, not to the INDEX file

**File:** `scripts/sprint_init.py:767-769`
**Severity:** LOW

The generated `backlog/INDEX.md` contains links like:
```markdown
| [docs/backlog/milestones/ms1.md](docs/backlog/milestones/ms1.md) | ... |
```

These paths (`sf.path`) are relative to the project root, but the INDEX file lives at `sprint-config/backlog/INDEX.md`. Markdown renderers resolve relative links from the file's directory, so these links are broken. They should either be absolute paths or relative to the INDEX file's location.

**How to trigger:** Open the generated `sprint-config/backlog/INDEX.md` in any markdown renderer (GitHub, VS Code preview, etc.).

**Fix:** Use `milestones/{stem}.md` since the symlinked milestone files are in `sprint-config/backlog/milestones/`:
```python
for sf in files:
    stem = Path(sf.path).stem
    rows.append(f"| [milestones/{stem}.md](milestones/{stem}.md) | {sf.evidence} "
                f"| {sf.confidence:.0%} |")
```

---

## BH35-009: CONTRIBUTING.md can be symlinked as both rules.md AND development.md

**File:** `scripts/sprint_init.py:451-455`
**Severity:** LOW

`detect_rules_file` and `detect_dev_guide` both include `CONTRIBUTING.md` as a fallback candidate:
```python
def detect_rules_file(self) -> Detection:
    return self._find_first("RULES.md", "CONVENTIONS.md", "CONTRIBUTING.md")

def detect_dev_guide(self) -> Detection:
    return self._find_first("DEVELOPMENT.md", "CONTRIBUTING.md", "HACKING.md")
```

If a project has only `CONTRIBUTING.md` (no RULES.md, no DEVELOPMENT.md), both detectors return the same file. The generator creates `sprint-config/rules.md -> CONTRIBUTING.md` and `sprint-config/development.md -> CONTRIBUTING.md` -- two different config files pointing to the same source. This is semantically incorrect and could confuse skills that expect distinct content in rules vs. development docs.

**Fix:** Track which files have been claimed by earlier detectors and skip them in subsequent detection. Or only use `CONTRIBUTING.md` in one detector.

---

## BH35-010: detect_prd_dir can return "." when project root matches heuristic

**File:** `scripts/sprint_init.py:383-389`
**Severity:** LOW

`_walk_dirs` includes the project root itself (depth 0). If the root directory has 2+ markdown files and the first one contains both `## Requirements` and `## Design`, `detect_prd_dir` returns:
```python
rel = str(d.relative_to(self.root))  # returns "."
return Detection(".", f"PRD content in {d.name}/", 0.7)
```

This produces a Detection with value `"."`. The generator then calls `_symlink("prd", ".")`, creating `sprint-config/prd -> ..` (a symlink to the project root). This makes the entire project tree accessible under `sprint-config/prd/`, which is incorrect and could confuse downstream tools.

**How to trigger:** Have 2+ markdown files in the project root where the first (alphabetically) contains both `## Requirements` and `## Design`.

**Fix:** Skip the root directory in the content scan:
```python
for d in self._walk_dirs(max_depth=3):
    if d == self.root:
        continue
```

---

## Summary

| ID | Severity | Summary |
|----|----------|---------|
| BH35-001 | HIGH | No-backlog projects fail self-validation (missing milestones/ dir) |
| BH35-002 | HIGH | definition-of-done.md overwritten on re-run (data loss) |
| BH35-003 | MEDIUM | Scanner doesn't exclude sprint-config/ (false detections on re-run) |
| BH35-004 | MEDIUM | binary_path TOML value not escaped |
| BH35-005 | MEDIUM | Persona stem collision silently overwrites symlinks |
| BH35-006 | MEDIUM | detect_prd_dir content scan crashes on unreadable files |
| BH35-007 | MEDIUM | `|-` block scalar indicator not handled in workflow parser |
| BH35-008 | LOW | Backlog INDEX links broken (relative to root, not to INDEX file) |
| BH35-009 | LOW | CONTRIBUTING.md can be dual-symlinked as rules + development |
| BH35-010 | LOW | detect_prd_dir can return "." for project root |

### Test Coverage Gaps

1. **No test generates config from a project with zero backlog files** and validates the result. The "no backlog" path in `generate_backlog()` is untested end-to-end.
2. **No test re-runs sprint_init** on an already-initialized project to verify preservation of user-edited files (DoD, project.toml, giles.md).
3. **No test for persona stem collisions** (same filename in different directories).
4. **No test for `|-` YAML block scalar** in workflow parsing.
5. **No test for `detect_prd_dir` content scan** with unreadable files.
