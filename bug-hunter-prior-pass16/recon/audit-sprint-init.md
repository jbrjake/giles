# Adversarial Audit: sprint_init.py

**File:** `/Users/jonr/Documents/non-nitro-repos/giles/scripts/sprint_init.py`
**Scope:** 978 lines, 626 statements, 88% coverage (72 lines uncovered)
**Auditor:** Claude Opus 4.6, 2026-03-16

---

## Findings

### 1. MEDIUM — Symlink escape: no containment check on `_symlink` targets

**Location:** Lines 549-561 (`_symlink`)

The `_symlink` method joins `self.root / target_rel` without verifying that
the resolved path stays within the project root. If a `ScoredFile.path` value
somehow contained `../../etc/passwd` (e.g., via a maliciously crafted `.md`
filename with path separators), the symlink would point outside the project.

Currently, `target_rel` values come from `self._rel(p)` which calls
`p.relative_to(self.root)` — this would raise `ValueError` for paths outside
root, providing implicit containment. However, `_symlink` itself has no
explicit guard, and future callers could pass arbitrary strings.

**Mitigation:** Add an explicit assertion that
`(self.root / target_rel).resolve().is_relative_to(self.root)` before
creating the symlink.

**Risk in practice:** LOW. All current callers produce contained paths from
scanner methods that filter via `_glob_md()` and `_rel()`. But the defense is
absent, and the function signature invites misuse.

---

### 2. LOW — Symlink `_symlink` unconditionally overwrites existing files

**Location:** Lines 558-559

```python
if link_path.is_symlink() or link_path.exists():
    link_path.unlink()
```

If the user has manually created a regular file at the symlink destination
(not a symlink), `_symlink` deletes it without warning. This differs from
`_inject_giles` (lines 731-735), which explicitly preserves user-customized
regular files. The inconsistency means re-running `sprint_init` could
silently destroy user edits to files in `sprint-config/` that happen to
share names with symlink targets (e.g., `rules.md`, `development.md`,
persona files).

**Recommendation:** Mirror the `_inject_giles` pattern: if the destination is
a regular file (not a symlink), skip with a "preserved" message. Or at
minimum, log a warning.

---

### 3. MEDIUM — `binary_path` TOML value not escaped

**Location:** Lines 654-657

```python
if s.binary_path.value:
    name = s.project_name.value or "app"
    lines.append(
        f'binary_path = "{s.binary_path.value.replace("<name>", name)}"')
```

The `name` variable (from `project_name.value`) is interpolated into the
TOML value via `.replace("<name>", name)` **without** passing through
`_esc()`. If the project name contains a backslash, double-quote, or newline
(e.g., parsed from a malformed `Cargo.toml`), the generated TOML would be
syntactically broken or could inject additional TOML keys.

Compare with line 596 where `_esc()` is correctly used:
`lines.append(f'name = "{esc(s.project_name.value or "unknown")}"')`.

**Fix:** Wrap with `_esc()`:
```python
lines.append(f'binary_path = "{esc(s.binary_path.value.replace("<name>", esc(name)))}"')
```

---

### 4. LOW — `cheatsheet` and `architecture` TOML values not escaped

**Location:** Lines 625-628

```python
if s.cheatsheet.value:
    lines.append(f'cheatsheet = "{s.cheatsheet.value}"')
if s.architecture.value:
    lines.append(f'architecture = "{s.architecture.value}"')
```

These values are interpolated into TOML without `_esc()`. Currently safe
because `_find_first()` returns hardcoded candidate strings
(`"CHEATSHEET.md"`, `"docs/INDEX.md"`, etc.), so the values cannot contain
TOML-breaking characters. However, this is an inconsistency with the
escaping pattern used for `project_name`, `language`, `repo`, etc. If
`_find_first` candidates ever include user-derived values, this would become
a real injection vector.

---

### 5. MEDIUM — `_parse_workflow_runs` YAML parser can misparse nested structures

**Location:** Lines 196-240

The workflow parser uses a line-by-line heuristic to extract `run:` values
from GitHub Actions YAML. It cannot distinguish between:
- A `run:` key inside a `steps:` block (intended target)
- A `run:` key inside a matrix strategy, composite action, or reusable workflow

The multiline block detection (line 223) treats any line starting with
two spaces as a continuation, but YAML indentation is context-dependent.
A workflow with deeply nested `run:` commands (e.g., inside `if:` conditions
or nested composite steps) will produce incorrect CI command lists.

Additionally, the `- run: cmd` stripping on line 213-214 could misfire on
non-step YAML list items that happen to start with `- run:`.

**Impact:** Incorrect CI commands in generated `project.toml`. Not a security
issue, but a correctness issue that could cause CI failures.

---

### 6. LOW — `detect_rules_file` and `detect_dev_guide` share CONTRIBUTING.md

**Location:** Lines 451-455

```python
def detect_rules_file(self) -> Detection:
    return self._find_first("RULES.md", "CONVENTIONS.md", "CONTRIBUTING.md")

def detect_dev_guide(self) -> Detection:
    return self._find_first("DEVELOPMENT.md", "CONTRIBUTING.md", "HACKING.md")
```

If a project has only `CONTRIBUTING.md` (no `RULES.md` or `DEVELOPMENT.md`),
both `rules_file` and `dev_guide` will detect the same file. Two symlinks
in `sprint-config/` will point to the same target. This is wasteful but not
harmful. However, it may confuse users who see both `rules.md` and
`development.md` being identical.

---

### 7. MEDIUM — Idempotency gap: `generate_project_toml` always overwrites

**Location:** Lines 587-666 (`generate_project_toml`), and
lines 839-847 (`generate`)

The `generate()` method calls `generate_project_toml()` unconditionally,
which calls `_write("project.toml", ...)`. The `_write` method overwrites
without checking if the file already exists. This means re-running
`sprint_init` after the user has customized `project.toml` (added `[release]`
milestones, adjusted CI commands, etc.) will **destroy all manual edits**.

This is the most impactful idempotency issue. Compare with `_inject_giles`
which correctly preserves user-customized files. The same pattern should be
applied to `project.toml` at minimum.

**Contrast:** `_symlink` at least re-creates symlinks idempotently (symlink
target is the same). But `_write` for generated files like `project.toml`,
`team/INDEX.md`, and `backlog/INDEX.md` will clobber any edits.

---

### 8. LOW — `_write_manifest` parsing is fragile and coupled to log format

**Location:** Lines 801-837

The manifest writer parses the `self.created` list by string-splitting
human-readable log entries like `"  generated  project.toml"` and
`"  skeleton   team/giles.md (from giles.md.tmpl)"`. This couples the
machine-readable manifest to the display format. If anyone changes the
log message format (e.g., adds an emoji, changes spacing), the manifest
will silently produce incorrect entries.

Specifically, line 817 does `entry.split(None, 1)[1].split(" (")[0]` which
will break if a file path contains ` (` (unlikely for generated paths, but
a latent bug).

**Recommendation:** Track created files in a structured list alongside the
human-readable log, rather than parsing the log entries.

---

### 9. LOW — Scanner `detect_backlog_files` reads entire file into memory

**Location:** Lines 336-361

```python
text = p.read_text(encoding="utf-8", errors="replace")
```

For backlog detection, the scanner reads the entire contents of every `.md`
file. For projects with very large markdown files (e.g., auto-generated
API docs), this could consume significant memory. The `detect_prd_dir`
method (line 386) correctly limits to `[:2000]` characters, but
`detect_backlog_files` does not.

---

### 10. MEDIUM — No atomicity in `generate()` — partial failures leave broken state

**Location:** Lines 839-847

The `generate()` method runs six generators sequentially. If any step fails
mid-way (e.g., permission error on a symlink, disk full), the sprint-config
directory is left in a partially generated state. There is no rollback
mechanism, and a subsequent re-run will overwrite some files but not others,
potentially creating inconsistencies.

The self-validation at lines 962-974 in `main()` catches this for CLI usage,
but programmatic callers (like tests) that call `gen.generate()` directly
do not get validation.

---

### 11. LOW — `detect_story_id_pattern` regex matches too broadly

**Location:** Lines 464-481

```python
patterns = re.compile(r"(US-\d{4}|[A-Z]{2,10}-\d+)")
```

The `[A-Z]{2,10}-\d+` arm matches any SCREAMING_CASE prefix followed by a
dash and digits. This will match things like `RFC-2616`, `ISO-8601`,
`HTTP-200`, `SHA-256`, `PR-42`, `GH-123` — none of which are story IDs.
In a project with many references to standards, this could produce a
misleading story ID pattern.

---

### 12. INFO — Uncovered lines analysis

The 72 uncovered lines fall into these categories:

**Error/edge-case handlers (never triggered in test fixtures):**
- Lines 137-138, 140: `_glob_md` ValueError catch and EXCLUDED_DIRS skip
- Lines 152-153: `_read_head` OSError handler
- Lines 169-170: `detect_repo` git not available
- Lines 177: `detect_repo` non-GitHub remote
- Lines 238-239: `_parse_workflow_runs` OSError handler
- Lines 270, 275: `_parse_cargo_name` section-end break, return None
- Lines 278-284: `_parse_json_name` error handlers
- Lines 293, 298: `_parse_pyproject_name` section-end break, return None
- Lines 346-347: `detect_backlog_files` OSError handler
- Lines 471-472: `detect_story_id_pattern` OSError handler
- Lines 555-556: `_symlink` target-missing handler
- Lines 672, 675-676: `_infer_role` file-not-found / OSError handlers
- Lines 699-701: `generate_team` empty personas branch (no personas detected)

**Display/reporting code (tested implicitly but not asserted):**
- Lines 890, 897: "no persona/backlog files detected" messages
- Lines 906-908: skipped items display
- Lines 916, 919, 922, 925, 928, 931-932: suggestion messages for low-confidence detections

**CLI entry point:**
- Lines 968-974: self-validation failure path in `main()`
- Line 978: `__name__ == "__main__"` guard

**Deep doc paths in TOML generation:**
- Lines 626, 628, 653: cheatsheet/architecture/build_command fallback paths

**Key testing gaps:**
- Lines 184-187, 189: workflow directory iteration with `.yml`/`.yaml` suffix
  filtering — only tested indirectly via hexwise fixture. No test with mixed
  file types in `.github/workflows/`.
- Line 226: multiline run block terminated by `- ` step pattern — no direct test.
- Lines 388-389: PRD content-scan fallback (only candidate-directory match tested).
- Line 488: Go binary path detection (`"./<name>"`) — no Go fixture.
- Lines 731-735: `_inject_giles` symlink-removal and preservation branches.
  The symlink case (line 732) has no test — only the "no giles exists" case
  and the regular-file preservation case are tested.
- Lines 689: `_infer_role` heading-terminates-scan-at-next-heading — not
  directly tested.

---

### 13. LOW — `_parse_workflow_runs` swallows OSError silently

**Location:** Lines 238-239

```python
except OSError:
    pass
```

If a workflow file cannot be read (permissions, encoding, etc.), the error
is silently swallowed. The caller gets an empty list and proceeds with
language defaults. This could mask real problems — a user might have
valid workflow files that are unreadable due to permissions, and init would
silently ignore them and generate incorrect CI defaults.

---

### 14. INFO — Story map symlink creates directory symlink from file path

**Location:** Lines 779-783

```python
story_map_path = self.scan.story_map.value
story_map_dir = str(Path(story_map_path).parent)
self._symlink("backlog/story-map", story_map_dir)
```

The code detects a specific file (`INDEX.md`) but symlinks its parent
directory. This is intentional (the TOML path points to the INDEX.md
inside the symlinked directory), but it means the symlink exposes the
entire parent directory contents, not just the story map files. If the
parent directory contains sensitive files, they would be visible through
the symlink.

---

### 15. LOW — `generate_team` INDEX.md injects unsanitized persona names/roles

**Location:** Lines 706-714

```python
for sf in personas:
    name = Path(sf.path).stem.replace("-", " ").replace("_", " ").title()
    role = self._infer_role(sf.path)
    filename = Path(sf.path).stem + ".md"
    rows.append(f"| {name} | {role} | {filename} |")
```

The `name` (from filename) and `role` (from file content) are interpolated
directly into a markdown table without sanitizing pipe characters (`|`).
A persona file named `alice|bob.md` or a role line containing `| injected |`
would break the table formatting. Unlikely in practice, but unhandled.

---

### 16. MEDIUM — `generate_backlog` INDEX.md injects raw `sf.evidence` into markdown

**Location:** Lines 749-751

```python
rows.append(f"| [{sf.path}]({sf.path}) | {sf.evidence} "
            f"| {sf.confidence:.0%} |")
```

The `evidence` field is constructed from strings like
`"3 story rows, 2 sprint headers"` which are safe. But `sf.path` is used
in a markdown link `[path](path)` — if a path contains `)` or `]`, it
could break the markdown link syntax. Not a security issue (this is local
markdown), but a rendering correctness issue.

---

### 17. INFO — `detect_repo` regex does not handle SSH URLs with custom ports

**Location:** Line 174

```python
m = re.search(r"github\.com[:/]([^/]+/[^/\s]+?)(?:\.git)?\s", result.stdout)
```

This regex handles `github.com:owner/repo.git` (SSH) and
`github.com/owner/repo.git` (HTTPS). It does not handle:
- `ssh://git@github.com:22/owner/repo.git` (SSH with port)
- GitHub Enterprise (`github.mycompany.com`)
- URLs with `www.github.com`

For non-GitHub remotes, the function correctly returns confidence 0.2
with `"remote is not GitHub"`.

---

### 18. LOW — No test for re-run idempotency with existing sprint-config

While individual tests verify generation works once, no test verifies the
contract that running `sprint_init` twice produces the same result (or
preserves user edits). The `_inject_giles` preservation logic (lines 731-735)
is partially tested, but there is no integration test that:
1. Generates config
2. Modifies `project.toml`
3. Re-generates config
4. Verifies the modification was preserved (or clobbered with warning)

This is particularly important given finding #7 (project.toml always
overwrites).

---

### 19. INFO — `_glob_md` follows symlinks during scanning

**Location:** Lines 130-142

`Path.rglob("*.md")` follows symlinks by default. If the project contains
a symlink loop (e.g., `docs -> .`), the scanner could enter an infinite
loop or consume excessive resources. Python 3.13+ raises `RecursionError`
for symlink loops in `rglob`, but earlier versions may hang.

Additionally, if `sprint-config/` already exists from a previous run and
contains symlinks back to project files, the scanner would scan those
symlinked files too, potentially double-counting personas and backlog files.

---

### 20. LOW — `detect_prd_dir` content scan only samples first file

**Location:** Lines 383-389

```python
md_files = list(d.glob("*.md"))
if len(md_files) >= 2:
    sample = md_files[0].read_text(...)[:2000]
```

The PRD content scan only reads the first markdown file in each directory.
If the first file is a README or index that does not contain
`## Requirements` and `## Design`, the directory is skipped even though
other files in it would match. The `glob("*.md")` order is
filesystem-dependent, making this detection nondeterministic across
platforms.

---

## Summary

| Severity | Count | Key Issues |
|----------|-------|------------|
| MEDIUM   | 4     | #1 symlink containment, #3 binary_path unescaped, #7 project.toml clobber, #10 no atomicity |
| LOW      | 9     | #2 overwrite, #4 unescaped paths, #6 shared CONTRIBUTING, #8 manifest parsing, #9 memory, #11 regex, #13 silent OSError, #15 unsanitized names, #18 no re-run test |
| INFO     | 4     | #12 uncovered lines, #14 dir exposure, #17 regex gaps, #19 symlink loops, #20 first-file sampling |

**Most impactful to fix:**
1. **Finding #7** (project.toml clobber on re-run) — this will bite real users
2. **Finding #3** (binary_path escaping) — trivial one-line fix
3. **Finding #1** (symlink containment) — defense-in-depth
4. **Finding #2** (regular file overwrite) — consistency with _inject_giles pattern
