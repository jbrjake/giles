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
| Doc reference format | `function()` `§file.function` (full anchor, copy-paste-to-grep) |
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

### Markdown files

```markdown
<!-- §sprint-run.phase_detection -->
## Phase Detection
```

### Doc-side references (CLAUDE.md, CHEATSHEET.md)

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

## Scope

### Source files receiving anchors

| Category | Files | Est. anchors |
|----------|-------|-------------|
| Shared scripts | `validate_config.py`, `sprint_init.py`, `sprint_teardown.py`, `sync_backlog.py`, `sprint_analytics.py`, `team_voices.py`, `traceability.py`, `test_coverage.py`, `manage_epics.py`, `manage_sagas.py` | ~80 |
| Skill scripts | `bootstrap_github.py`, `populate_issues.py`, `setup_ci.py`, `sync_tracking.py`, `update_burndown.py`, `check_status.py` | ~40 |
| SKILL.md files | All 5 skills | ~25 |
| Reference/agent .md | `persona-guide.md`, `ceremony-kickoff.md`, `ceremony-demo.md`, `ceremony-retro.md`, `implementer.md`, `reviewer.md` | ~20 |

### Doc files updated

- CLAUDE.md: all `:NN` refs replaced with `§` anchors
- CHEATSHEET.md: `Line` column replaced with `Anchor` column

### Out of scope

- Bug-hunter / adversarial-review files (ephemeral artifacts)
- Reference files not currently referenced by `:NN` anywhere
- Python test files

## Validation Script

`scripts/validate_anchors.py` -- stdlib-only, ~120-150 lines.

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

### Pass 1: Seed anchors into source files

A one-time migration script reads every `:NN` reference in CLAUDE.md and
CHEATSHEET.md, looks up what exists at that line number in the source file, and
inserts the appropriate anchor comment above it.

### Pass 2: Rewrite doc references

Same migration script rewrites the doc side:
- `parse_simple_toml() :47` becomes `parse_simple_toml()` `§validate_config.parse_simple_toml`
- CHEATSHEET.md `Line` column becomes `Anchor` column
- Inline prose refs like `validate_config.py:260` become `§validate_config._REQUIRED_TOML_KEYS`

### Pass 3: Validate

Run `validate_anchors.py` to confirm zero broken references. Manual review of
the diff.

### After migration

The migration script is deleted. `validate_anchors.py` remains as the permanent
guardian.

## Ongoing Maintenance

- **Adding a function**: add `# §file.function` above it, add `§` ref to docs.
- **Renaming/removing**: update or remove the anchor, run `validate_anchors.py`.
- **Refactoring**: move code freely. Anchors travel with the code. No doc updates
  needed unless the function itself is renamed.
