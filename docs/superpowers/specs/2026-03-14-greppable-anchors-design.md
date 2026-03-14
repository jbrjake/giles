# Greppable Anchors Design

Replace brittle line-number references with stable, greppable `§` anchors across
documentation and source files.

## Problem

CLAUDE.md and CHEATSHEET.md reference ~200 line numbers in Python scripts and
SKILL.md files. Any code edit that shifts lines makes these references silently
wrong. There is no drift detection. Every refactor requires a manual doc-update
pass that often gets skipped.

## Decisions

| Decision | Choice |
|----------|--------|
| Scope | CLAUDE.md, CHEATSHEET.md, all 5 SKILL.md files, referenced .md files |
| Python anchor format | `# §file_stem.symbol_name` on the line above the target |
| Markdown anchor format | `<!-- §name.section_slug -->` on the line above the heading |
| Doc reference format | `function()` §file.function (bare, no backticks around §) |
| Naming convention | `§<file_stem>.<symbol>` for Python; `§<skill-name>.<slug>` for SKILL.md; `§<file_stem>.<slug>` for other .md |
| Slugs | snake_case, derived from heading text |
| Validation | `scripts/validate_anchors.py` with `--fix` autofix mode |
| Migration | One-time script that reads old `:NN` refs, inserts anchors, rewrites docs |

## Anchor Format

### Python files

```python
# §validate_config.parse_simple_toml
def parse_simple_toml(text):
    ...
```

```python
# §validate_config.KANBAN_STATES
KANBAN_STATES = frozenset({...})
```

**Class-level only.** Anchors target classes, not individual methods. Use
`§sprint_init.ProjectScanner`, not `§sprint_init.ProjectScanner.scan_language`.
This matches how CLAUDE.md currently references classes. If a method-level anchor
becomes necessary in the future, extend to three-level dotted names then.

### Markdown files

```markdown
<!-- §sprint-run.phase_detection -->
## Phase Detection
```

### Doc-side references (CLAUDE.md, CHEATSHEET.md)

References use bare `§` tokens (no backticks around the anchor). This avoids
rendering as inline code on GitHub and keeps grep straightforward.

CLAUDE.md tables:
```
| `scripts/validate_config.py` | ... | `parse_simple_toml()` §validate_config.parse_simple_toml, `load_config()` §validate_config.load_config |
```

CHEATSHEET.md tables (Line column replaced with Anchor):
```
| Anchor | Function | Purpose |
|--------|----------|---------|
| §validate_config.gh | `gh()` | Shared GitHub CLI wrapper |
```

**Line-range references** (e.g., `sprint_init.py:608-614`) become a single anchor
at the start of the range, targeting whatever symbol/section begins there.

## Scope

### Source files receiving anchors

| Category | Files | Est. anchors |
|----------|-------|-------------|
| Shared scripts | `validate_config.py`, `sprint_init.py`, `sprint_teardown.py`, `sync_backlog.py`, `sprint_analytics.py`, `team_voices.py`, `traceability.py`, `test_coverage.py`, `manage_epics.py`, `manage_sagas.py` | ~80 |
| Skill scripts | `bootstrap_github.py`, `populate_issues.py`, `setup_ci.py`, `sync_tracking.py`, `update_burndown.py`, `check_status.py`, `release_gate.py` | ~40 |
| SKILL.md files | All 5 skills | ~25 |
| Reference/agent .md | `persona-guide.md`, `ceremony-kickoff.md`, `ceremony-demo.md`, `ceremony-retro.md`, `implementer.md`, `reviewer.md` | ~20 |

### Doc files updated

- CLAUDE.md: all `:NN` refs replaced with `§` anchors
- CHEATSHEET.md: `Line` column replaced with `Anchor` column

### Out of scope

- Bug-hunter / adversarial-review files (ephemeral artifacts)
- Reference files not currently referenced by `:NN` anywhere (e.g.,
  `github-conventions.md`, `ci-workflow-template.md`, `release-checklist.md`)
- Python test files
- `scripts/commit.py` (not referenced from docs)

## Parsing Rules

### Anchor definitions

| File type | Regex | Example match |
|-----------|-------|---------------|
| Python | `^# §([\w]+\.[\w]+)$` | `# §validate_config.parse_simple_toml` |
| Markdown | `^<!-- §([\w-]+\.[\w_]+) -->$` | `<!-- §sprint-run.phase_detection -->` |

Anchor names: `§<namespace>.<symbol>` where namespace is `[\w-]+` (allows
hyphens for skill names) and symbol is `[\w]+` (letters, digits, underscore).

### Anchor references in docs

Pattern: `§[\w][\w.-]*\.[\w]+` preceded by whitespace, pipe, or start-of-cell,
followed by whitespace, comma, pipe, or end-of-line.

Concrete regex for extraction: `(?:^|[\s|,])§([\w-]+\.[\w_]+)(?=[\s,|]|$)`

Unknown namespaces (not in the lookup table) are treated as errors, not silently
skipped. This catches typos like `§validate_confg.gh`.

## Validation Script

`scripts/validate_anchors.py` -- stdlib-only, ~120-150 lines.

**Replaces** `scripts/verify_line_refs.py`, which is deleted after migration.

### Check mode (default)

```
python scripts/validate_anchors.py

  165 references checked, all resolved
  3 anchors defined but unreferenced (info, not error)
```

Exit 0 if all refs resolve, exit 1 if any broken.

### Autofix mode

```
python scripts/validate_anchors.py --fix

Fixed 3 missing anchors:
  + scripts/validate_config.py: added §validate_config.parse_simple_toml above line 47
  + scripts/sprint_init.py: added §sprint_init.ProjectScanner above line 90

1 broken reference (manual fix needed):
  CLAUDE.md: §validate_config.old_function -> no matching definition found
```

**What autofix handles:**
- Missing anchor in Python source: function exists but has no anchor comment --
  inserts `# §file.function` on the line above the definition.
- Missing anchor in markdown: heading exists but has no anchor comment --
  inserts `<!-- §name.slug -->` on the line above.
- Orphaned doc references: reports only (human decision).

**What autofix does not do:**
- Guess which definition a broken reference was meant to target.
- Rename anchors.
- Add new doc-side references.

### Namespace-to-file mapping

The script maintains a lookup table mapping anchor namespaces to file paths,
since the mapping is not always 1:1 (e.g., `§bootstrap_github` lives under
`skills/sprint-setup/scripts/`). This table is defined once in the script and
updated when new scripts are added.

## Migration Strategy

### Migration script

`scripts/migrate_to_anchors.py` -- one-time, stdlib-only, deleted after use.

Reuses `extract_refs()` from `scripts/verify_line_refs.py` to parse existing
`:NN` references. This gives us the exact (file, symbol, line_number) tuples
that need anchors.

The script is idempotent: re-running it skips anchors that already exist and
does not duplicate doc-side rewrites.

### Pass 1: Seed anchors into source files

For each extracted reference, the migration script:
1. Opens the source file
2. Reads the line at the claimed number
3. Derives the anchor name: `§<file_stem>.<symbol>`
4. Inserts `# §file.symbol` (Python) or `<!-- §name.slug -->` (markdown) on
   the line above, if not already present

Line-range references (`:608-614`) anchor at the symbol starting at the first
line of the range.

### Pass 2: Rewrite doc references

Same script rewrites the doc side:
- `parse_simple_toml() :47` becomes `parse_simple_toml()` §validate_config.parse_simple_toml
- CHEATSHEET.md `Line` column becomes `Anchor` column, numbers become `§` refs
- Inline prose refs like `validate_config.py:260` become §validate_config._REQUIRED_TOML_KEYS

### Pass 3: Validate

Run `validate_anchors.py` to confirm zero broken references. Manual review of
the diff.

### After migration

- `scripts/migrate_to_anchors.py` is deleted (one-time tool).
- `scripts/verify_line_refs.py` is deleted (superseded by `validate_anchors.py`).
- `validate_anchors.py` remains as the permanent guardian.

## Ongoing Maintenance

- **Adding a function**: add `# §file.function` above it, add `§` ref to docs.
- **Renaming/removing**: update or remove the anchor, run `validate_anchors.py`.
- **Refactoring**: move code freely. Anchors travel with the code. No doc updates
  needed unless the function itself is renamed.
