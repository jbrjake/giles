# Greppable Anchors Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace all `:NN` line-number references in CLAUDE.md and CHEATSHEET.md with stable `§`-prefixed greppable anchors that travel with the code.

**Architecture:** Two scripts — a permanent `validate_anchors.py` (check + autofix) and a throwaway `migrate_to_anchors.py` (reads old `:NN` refs, inserts anchors into source, rewrites docs). The migration script reuses `extract_refs()` from the existing `verify_line_refs.py`. After migration, both `migrate_to_anchors.py` and `verify_line_refs.py` are deleted.

**Tech Stack:** Python 3.10+ stdlib only (matching project conventions). unittest for tests.

**Spec:** `docs/superpowers/specs/2026-03-14-greppable-anchors-design.md`

---

## File Structure

| Action | File | Responsibility |
|--------|------|----------------|
| Create | `scripts/validate_anchors.py` | Permanent anchor validation + autofix |
| Create | `scripts/migrate_to_anchors.py` | One-time migration (deleted after use) |
| Create | `tests/test_validate_anchors.py` | Tests for validate_anchors.py |
| Create | `tests/test_migrate_anchors.py` | Tests for migrate_to_anchors.py |
| Modify | ~16 Python source files | Add `# §namespace.symbol` anchor comments |
| Modify | ~14 Markdown files | Add `<!-- §namespace.slug -->` anchor comments |
| Modify | `CLAUDE.md` | Replace `:NN` refs with `§` anchors |
| Modify | `CHEATSHEET.md` | Replace `Line` columns with `Anchor` columns |
| Modify | `Makefile` | Replace verify_line_refs.py with validate_anchors.py in lint target |
| Modify | `tests/test_pipeline_scripts.py` | Remove verify_line_refs test classes |
| Delete | `scripts/verify_line_refs.py` | Superseded by validate_anchors.py |
| Delete | `scripts/migrate_to_anchors.py` | One-time tool, removed after migration |

---

## Chunk 1: validate_anchors.py

The permanent validation script. Built first so we can use it to verify the migration.

### Task 1: Namespace map and resolver

**Files:**
- Create: `scripts/validate_anchors.py`
- Create: `tests/test_validate_anchors.py`

- [ ] **Step 1: Write failing test for namespace resolution**

```python
# tests/test_validate_anchors.py
#!/usr/bin/env python3
"""Tests for validate_anchors.py."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from validate_anchors import resolve_namespace, NAMESPACE_MAP


class TestNamespaceMap(unittest.TestCase):
    """Namespace-to-file resolution."""

    def test_shared_script_namespace(self):
        path = resolve_namespace("validate_config")
        self.assertEqual(path, "scripts/validate_config.py")

    def test_skill_script_namespace(self):
        path = resolve_namespace("bootstrap_github")
        self.assertEqual(path, "skills/sprint-setup/scripts/bootstrap_github.py")

    def test_skill_md_namespace(self):
        path = resolve_namespace("sprint-run")
        self.assertEqual(path, "skills/sprint-run/SKILL.md")

    def test_reference_md_namespace(self):
        path = resolve_namespace("ceremony-kickoff")
        self.assertEqual(path, "skills/sprint-run/references/ceremony-kickoff.md")

    def test_agent_namespace(self):
        path = resolve_namespace("implementer")
        self.assertEqual(path, "skills/sprint-run/agents/implementer.md")

    def test_unknown_namespace_raises(self):
        with self.assertRaises(KeyError):
            resolve_namespace("nonexistent")

    def test_all_mapped_files_exist(self):
        for ns, rel_path in NAMESPACE_MAP.items():
            full = ROOT / rel_path
            self.assertTrue(full.exists(), f"§{ns} -> {rel_path} does not exist")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_validate_anchors.py -v 2>&1 | head -20`
Expected: ImportError — validate_anchors module does not exist yet.

- [ ] **Step 3: Write minimal implementation**

```python
# scripts/validate_anchors.py
#!/usr/bin/env python3
"""Validate §-prefixed anchor references in documentation files.

Usage:
    python validate_anchors.py          # check mode (exit 0/1)
    python validate_anchors.py --fix    # insert missing anchors where possible

Scans CLAUDE.md and CHEATSHEET.md for §namespace.symbol references,
verifies each resolves to an anchor comment in the target source file.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# --- Namespace-to-file lookup table ---
# Maps the namespace part of §namespace.symbol to a relative file path.
# Python namespaces use underscores (matching file stems).
# Markdown namespaces may use hyphens (matching skill/reference names).
NAMESPACE_MAP: dict[str, str] = {
    # Shared scripts (scripts/)
    "validate_config": "scripts/validate_config.py",
    "sprint_init": "scripts/sprint_init.py",
    "sprint_teardown": "scripts/sprint_teardown.py",
    "sync_backlog": "scripts/sync_backlog.py",
    "sprint_analytics": "scripts/sprint_analytics.py",
    "team_voices": "scripts/team_voices.py",
    "traceability": "scripts/traceability.py",
    "test_coverage": "scripts/test_coverage.py",
    "manage_epics": "scripts/manage_epics.py",
    "manage_sagas": "scripts/manage_sagas.py",
    # Skill scripts (nested under skills/)
    "bootstrap_github": "skills/sprint-setup/scripts/bootstrap_github.py",
    "populate_issues": "skills/sprint-setup/scripts/populate_issues.py",
    "setup_ci": "skills/sprint-setup/scripts/setup_ci.py",
    "sync_tracking": "skills/sprint-run/scripts/sync_tracking.py",
    "update_burndown": "skills/sprint-run/scripts/update_burndown.py",
    "check_status": "skills/sprint-monitor/scripts/check_status.py",
    "release_gate": "skills/sprint-release/scripts/release_gate.py",
    # SKILL.md files (hyphenated)
    "sprint-setup": "skills/sprint-setup/SKILL.md",
    "sprint-run": "skills/sprint-run/SKILL.md",
    "sprint-monitor": "skills/sprint-monitor/SKILL.md",
    "sprint-release": "skills/sprint-release/SKILL.md",
    "sprint-teardown": "skills/sprint-teardown/SKILL.md",
    # Reference markdown
    "persona-guide": "skills/sprint-run/references/persona-guide.md",
    "ceremony-kickoff": "skills/sprint-run/references/ceremony-kickoff.md",
    "ceremony-demo": "skills/sprint-run/references/ceremony-demo.md",
    "ceremony-retro": "skills/sprint-run/references/ceremony-retro.md",
    "story-execution": "skills/sprint-run/references/story-execution.md",
    "tracking-formats": "skills/sprint-run/references/tracking-formats.md",
    "context-recovery": "skills/sprint-run/references/context-recovery.md",
    "kanban-protocol": "skills/sprint-run/references/kanban-protocol.md",
    "github-conventions": "skills/sprint-setup/references/github-conventions.md",
    "ci-workflow-template": "skills/sprint-setup/references/ci-workflow-template.md",
    "release-checklist": "skills/sprint-release/references/release-checklist.md",
    # Agent templates
    "implementer": "skills/sprint-run/agents/implementer.md",
    "reviewer": "skills/sprint-run/agents/reviewer.md",
    # This script itself (so CLAUDE.md can reference it)
    "validate_anchors": "scripts/validate_anchors.py",
}


def resolve_namespace(namespace: str) -> str:
    """Return the relative file path for a namespace, or raise KeyError."""
    return NAMESPACE_MAP[namespace]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_validate_anchors.py::TestNamespaceMap -v`
Expected: All 7 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/validate_anchors.py tests/test_validate_anchors.py
git commit -m "feat: add namespace map and resolver for anchor validation"
```

---

### Task 2: Anchor definition scanner

Scans source files for `# §...` and `<!-- §... -->` anchor comments.

**Files:**
- Modify: `tests/test_validate_anchors.py`
- Modify: `scripts/validate_anchors.py`

- [ ] **Step 1: Write failing tests for anchor scanning**

Append to `tests/test_validate_anchors.py`:

```python
import tempfile
import textwrap

from validate_anchors import find_anchor_defs


class TestFindAnchorDefs(unittest.TestCase):
    """Scan files for anchor definition comments."""

    def test_python_function_anchor(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(textwrap.dedent("""\
                # §mymod.my_func
                def my_func():
                    pass
            """))
            f.flush()
            defs = find_anchor_defs(Path(f.name))
        self.assertEqual(defs, {"mymod.my_func": 1})

    def test_markdown_heading_anchor(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write(textwrap.dedent("""\
                # Title
                <!-- §sprint-run.kickoff -->
                ## Kickoff
            """))
            f.flush()
            defs = find_anchor_defs(Path(f.name))
        self.assertEqual(defs, {"sprint-run.kickoff": 2})

    def test_multiple_anchors(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(textwrap.dedent("""\
                # §mod.func_a
                def func_a():
                    pass

                # §mod.CONST_B
                CONST_B = 42
            """))
            f.flush()
            defs = find_anchor_defs(Path(f.name))
        self.assertEqual(len(defs), 2)
        self.assertIn("mod.func_a", defs)
        self.assertIn("mod.CONST_B", defs)

    def test_no_anchors_returns_empty(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("def plain_func():\n    pass\n")
            f.flush()
            defs = find_anchor_defs(Path(f.name))
        self.assertEqual(defs, {})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_validate_anchors.py::TestFindAnchorDefs -v 2>&1 | head -10`
Expected: ImportError — `find_anchor_defs` not defined.

- [ ] **Step 3: Write implementation**

Add to `scripts/validate_anchors.py`:

```python
# Regex patterns for anchor definitions
_PY_ANCHOR_RE = re.compile(r"^# §([\w]+\.[\w]+)$")
_MD_ANCHOR_RE = re.compile(r"^<!-- §([\w-]+\.[\w_]+) -->$")


def find_anchor_defs(file_path: Path) -> dict[str, int]:
    """Return {anchor_name: line_number} for all anchors defined in a file."""
    defs: dict[str, int] = {}
    text = file_path.read_text(encoding="utf-8")
    for i, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        m = _PY_ANCHOR_RE.match(stripped) or _MD_ANCHOR_RE.match(stripped)
        if m:
            defs[m.group(1)] = i
    return defs
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_validate_anchors.py::TestFindAnchorDefs -v`
Expected: All 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/validate_anchors.py tests/test_validate_anchors.py
git commit -m "feat: add anchor definition scanner"
```

---

### Task 3: Reference scanner

Scans doc files (CLAUDE.md, CHEATSHEET.md) for `§namespace.symbol` references.

**Files:**
- Modify: `tests/test_validate_anchors.py`
- Modify: `scripts/validate_anchors.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_validate_anchors.py`:

```python
from validate_anchors import find_anchor_refs


class TestFindAnchorRefs(unittest.TestCase):
    """Scan doc files for §-prefixed references."""

    def test_table_cell_refs(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("| `scripts/foo.py` | `bar()` §foo.bar, `baz()` §foo.baz |\n")
            f.flush()
            refs = find_anchor_refs(Path(f.name))
        names = [r[0] for r in refs]
        self.assertEqual(names, ["foo.bar", "foo.baz"])

    def test_anchor_column_ref(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("| §validate_config.gh | `gh()` | Wrapper |\n")
            f.flush()
            refs = find_anchor_refs(Path(f.name))
        self.assertEqual(refs[0][0], "validate_config.gh")

    def test_prose_ref(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("See §sprint-run.kickoff for details.\n")
            f.flush()
            refs = find_anchor_refs(Path(f.name))
        self.assertEqual(refs[0][0], "sprint-run.kickoff")

    def test_no_refs_returns_empty(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("No anchor references here.\n")
            f.flush()
            refs = find_anchor_refs(Path(f.name))
        self.assertEqual(refs, [])

    def test_ref_includes_line_number(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("line one\n§foo.bar on line two\n")
            f.flush()
            refs = find_anchor_refs(Path(f.name))
        self.assertEqual(refs[0], ("foo.bar", 2))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_validate_anchors.py::TestFindAnchorRefs -v 2>&1 | head -10`
Expected: ImportError — `find_anchor_refs` not defined.

- [ ] **Step 3: Write implementation**

Add to `scripts/validate_anchors.py`:

```python
_REF_RE = re.compile(r"§([\w-]+\.[\w_]+)(?=[\s,|]|$)")


def find_anchor_refs(doc_path: Path) -> list[tuple[str, int]]:
    """Return [(anchor_name, line_number), ...] for all § refs in a doc file."""
    refs: list[tuple[str, int]] = []
    text = doc_path.read_text(encoding="utf-8")
    for i, line in enumerate(text.splitlines(), 1):
        for m in _REF_RE.finditer(line):
            refs.append((m.group(1), i))
    return refs
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_validate_anchors.py::TestFindAnchorRefs -v`
Expected: All 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/validate_anchors.py tests/test_validate_anchors.py
git commit -m "feat: add anchor reference scanner"
```

---

### Task 4: Check mode orchestrator

Ties together namespace resolution, definition scanning, and reference scanning.
Reports broken references and unreferenced anchors.

**Files:**
- Modify: `tests/test_validate_anchors.py`
- Modify: `scripts/validate_anchors.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_validate_anchors.py`:

```python
import os

from validate_anchors import check_anchors


class TestCheckAnchors(unittest.TestCase):
    """End-to-end check mode."""

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        # Create a minimal source file with an anchor
        src = self.tmpdir / "scripts"
        src.mkdir()
        (src / "mymod.py").write_text(
            "# §mymod.my_func\ndef my_func():\n    pass\n"
        )
        # Create a doc file referencing it
        (self.tmpdir / "DOC.md").write_text(
            "| `scripts/mymod.py` | `my_func()` §mymod.my_func |\n"
        )

    def test_all_refs_resolve(self):
        ns_map = {"mymod": "scripts/mymod.py"}
        broken, unreferenced = check_anchors(
            root=self.tmpdir,
            doc_files=["DOC.md"],
            namespace_map=ns_map,
        )
        self.assertEqual(broken, [])

    def test_broken_ref_detected(self):
        (self.tmpdir / "DOC.md").write_text("See §mymod.nonexistent\n")
        ns_map = {"mymod": "scripts/mymod.py"}
        broken, unreferenced = check_anchors(
            root=self.tmpdir,
            doc_files=["DOC.md"],
            namespace_map=ns_map,
        )
        self.assertEqual(len(broken), 1)
        self.assertIn("nonexistent", broken[0])

    def test_unknown_namespace_is_broken(self):
        (self.tmpdir / "DOC.md").write_text("See §typomod.func\n")
        ns_map = {"mymod": "scripts/mymod.py"}
        broken, _ = check_anchors(
            root=self.tmpdir,
            doc_files=["DOC.md"],
            namespace_map=ns_map,
        )
        self.assertEqual(len(broken), 1)
        self.assertIn("typomod", broken[0])

    def test_unreferenced_anchor_reported(self):
        (self.tmpdir / "DOC.md").write_text("No refs here.\n")
        ns_map = {"mymod": "scripts/mymod.py"}
        _, unreferenced = check_anchors(
            root=self.tmpdir,
            doc_files=["DOC.md"],
            namespace_map=ns_map,
        )
        self.assertEqual(len(unreferenced), 1)
        self.assertIn("mymod.my_func", unreferenced[0])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_validate_anchors.py::TestCheckAnchors -v 2>&1 | head -10`
Expected: ImportError — `check_anchors` not defined.

- [ ] **Step 3: Write implementation**

Add to `scripts/validate_anchors.py`:

```python
DOC_FILES = ["CLAUDE.md", "CHEATSHEET.md"]


def check_anchors(
    root: Path | None = None,
    doc_files: list[str] | None = None,
    namespace_map: dict[str, str] | None = None,
) -> tuple[list[str], list[str]]:
    """Check all § references resolve to anchor definitions.

    Returns (broken_messages, unreferenced_messages).
    """
    root = root or ROOT
    doc_files = doc_files or DOC_FILES
    namespace_map = namespace_map or NAMESPACE_MAP

    # Collect all anchor definitions from all mapped files
    all_defs: set[str] = set()
    for ns, rel_path in namespace_map.items():
        full = root / rel_path
        if full.exists():
            for anchor_name in find_anchor_defs(full):
                all_defs.add(anchor_name)

    # Collect all references from doc files
    all_refs: list[tuple[str, str, int]] = []  # (anchor, doc_file, line)
    for doc_name in doc_files:
        doc_path = root / doc_name
        if doc_path.exists():
            for anchor_name, line_num in find_anchor_refs(doc_path):
                all_refs.append((anchor_name, doc_name, line_num))

    # Check each reference
    broken: list[str] = []
    referenced: set[str] = set()
    for anchor_name, doc_name, line_num in all_refs:
        ns = anchor_name.split(".")[0]
        if ns not in namespace_map:
            broken.append(
                f"{doc_name}:{line_num} — §{anchor_name} — unknown namespace '{ns}'"
            )
            continue
        referenced.add(anchor_name)
        if anchor_name not in all_defs:
            broken.append(
                f"{doc_name}:{line_num} — §{anchor_name} — anchor not found in {namespace_map[ns]}"
            )

    # Find unreferenced anchors (info only)
    unreferenced: list[str] = []
    for anchor_name in sorted(all_defs - referenced):
        ns = anchor_name.split(".")[0]
        rel_path = namespace_map.get(ns, "?")
        unreferenced.append(f"§{anchor_name} in {rel_path}")

    return broken, unreferenced
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_validate_anchors.py::TestCheckAnchors -v`
Expected: All 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/validate_anchors.py tests/test_validate_anchors.py
git commit -m "feat: add check mode orchestrator for anchor validation"
```

---

### Task 5: Fix mode

Finds missing anchors in source files and inserts them.

**Files:**
- Modify: `tests/test_validate_anchors.py`
- Modify: `scripts/validate_anchors.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_validate_anchors.py`:

```python
from validate_anchors import fix_missing_anchors


class TestFixMode(unittest.TestCase):
    """Autofix inserts missing anchor comments."""

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        src = self.tmpdir / "scripts"
        src.mkdir()
        # Source file WITHOUT anchor, but with the function
        (src / "mymod.py").write_text(
            "def my_func():\n    pass\n\nCONST = 42\n"
        )
        self.ns_map = {"mymod": "scripts/mymod.py"}

    def test_fix_inserts_python_anchor(self):
        (self.tmpdir / "DOC.md").write_text("§mymod.my_func\n")
        fixed = fix_missing_anchors(
            root=self.tmpdir,
            doc_files=["DOC.md"],
            namespace_map=self.ns_map,
        )
        self.assertEqual(fixed, 1)
        content = (self.tmpdir / "scripts" / "mymod.py").read_text()
        self.assertIn("# §mymod.my_func", content)

    def test_fix_inserts_above_definition(self):
        (self.tmpdir / "DOC.md").write_text("§mymod.my_func\n")
        fix_missing_anchors(
            root=self.tmpdir,
            doc_files=["DOC.md"],
            namespace_map=self.ns_map,
        )
        lines = (self.tmpdir / "scripts" / "mymod.py").read_text().splitlines()
        anchor_idx = next(i for i, l in enumerate(lines) if "§mymod.my_func" in l)
        self.assertIn("def my_func", lines[anchor_idx + 1])

    def test_fix_skips_existing_anchor(self):
        # Add anchor manually first
        (self.tmpdir / "scripts" / "mymod.py").write_text(
            "# §mymod.my_func\ndef my_func():\n    pass\n"
        )
        (self.tmpdir / "DOC.md").write_text("§mymod.my_func\n")
        fixed = fix_missing_anchors(
            root=self.tmpdir,
            doc_files=["DOC.md"],
            namespace_map=self.ns_map,
        )
        self.assertEqual(fixed, 0)

    def test_fix_markdown_heading(self):
        md_dir = self.tmpdir / "skills" / "sprint-run"
        md_dir.mkdir(parents=True)
        (md_dir / "SKILL.md").write_text("# Title\n## Kickoff\nContent\n")
        ns_map = {"sprint-run": "skills/sprint-run/SKILL.md"}
        (self.tmpdir / "DOC.md").write_text("§sprint-run.kickoff\n")
        fixed = fix_missing_anchors(
            root=self.tmpdir,
            doc_files=["DOC.md"],
            namespace_map=ns_map,
        )
        self.assertEqual(fixed, 1)
        content = (md_dir / "SKILL.md").read_text()
        self.assertIn("<!-- §sprint-run.kickoff -->", content)

    def test_fix_reports_unfixable(self):
        (self.tmpdir / "DOC.md").write_text("§mymod.nonexistent\n")
        fixed = fix_missing_anchors(
            root=self.tmpdir,
            doc_files=["DOC.md"],
            namespace_map=self.ns_map,
        )
        self.assertEqual(fixed, 0)  # nothing to fix — symbol doesn't exist
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_validate_anchors.py::TestFixMode -v 2>&1 | head -10`
Expected: ImportError — `fix_missing_anchors` not defined.

- [ ] **Step 3: Write implementation**

Add to `scripts/validate_anchors.py`:

```python
def _find_symbol_line(file_path: Path, symbol: str) -> int | None:
    """Find line number of a symbol definition (def/class/constant)."""
    text = file_path.read_text(encoding="utf-8")
    lines = text.splitlines()
    clean = symbol.strip("()")
    patterns = [
        rf"^(def|class)\s+{re.escape(clean)}\b",
        rf"^{re.escape(clean)}\s*[:=]",
        rf"^\s+(def|class)\s+{re.escape(clean)}\b",
    ]
    for i, line in enumerate(lines, 1):
        for pat in patterns:
            if re.search(pat, line):
                return i
    return None


def _find_heading_line(file_path: Path, slug: str) -> int | None:
    """Find line number of a markdown heading matching a slug.

    Slug matching: 'kickoff' matches '## Kickoff', '## Phase 1: Kickoff', etc.
    Converts heading text to slug (lowercase, spaces/special chars -> underscore)
    and checks if the heading slug ends with the target slug or matches exactly.
    Suffix-only matching avoids false positives (e.g., 'check' won't match
    'pre_flight_check_ci').
    """
    text = file_path.read_text(encoding="utf-8")
    for i, line in enumerate(text.splitlines(), 1):
        if line.startswith("#"):
            heading_text = re.sub(r"^#+\s*", "", line).strip()
            heading_slug = re.sub(r"[^a-z0-9]+", "_", heading_text.lower()).strip("_")
            if heading_slug == slug or heading_slug.endswith("_" + slug):
                return i
    return None


def fix_missing_anchors(
    root: Path | None = None,
    doc_files: list[str] | None = None,
    namespace_map: dict[str, str] | None = None,
) -> int:
    """Insert missing anchor comments into source files. Returns count fixed."""
    root = root or ROOT
    doc_files = doc_files or DOC_FILES
    namespace_map = namespace_map or NAMESPACE_MAP

    # Collect existing anchors
    existing: set[str] = set()
    for ns, rel_path in namespace_map.items():
        full = root / rel_path
        if full.exists():
            existing.update(find_anchor_defs(full).keys())

    # Collect references that need fixing
    needed: set[str] = set()
    for doc_name in doc_files:
        doc_path = root / doc_name
        if doc_path.exists():
            for anchor_name, _ in find_anchor_refs(doc_path):
                if anchor_name not in existing:
                    ns = anchor_name.split(".")[0]
                    if ns in namespace_map:
                        needed.add(anchor_name)

    # Group by file for efficient insertion
    fixes_by_file: dict[str, list[tuple[str, int]]] = {}
    for anchor_name in needed:
        ns, symbol = anchor_name.split(".", 1)
        rel_path = namespace_map[ns]
        full = root / rel_path
        if not full.exists():
            continue

        if rel_path.endswith(".py"):
            target_line = _find_symbol_line(full, symbol)
        else:
            target_line = _find_heading_line(full, symbol)

        if target_line is not None:
            fixes_by_file.setdefault(rel_path, []).append((anchor_name, target_line))

    # Apply fixes (insert anchor comments, working bottom-up to preserve line numbers)
    fixed_count = 0
    for rel_path, fixes in fixes_by_file.items():
        full = root / rel_path
        lines = full.read_text(encoding="utf-8").splitlines()
        is_python = rel_path.endswith(".py")

        # Sort by line number descending so insertions don't shift later targets
        for anchor_name, target_line in sorted(fixes, key=lambda x: x[1], reverse=True):
            idx = target_line - 1  # 0-based
            if is_python:
                anchor_comment = f"# §{anchor_name}"
            else:
                anchor_comment = f"<!-- §{anchor_name} -->"
            lines.insert(idx, anchor_comment)
            fixed_count += 1

        full.write_text("\n".join(lines) + "\n", encoding="utf-8")

    return fixed_count
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_validate_anchors.py::TestFixMode -v`
Expected: All 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/validate_anchors.py tests/test_validate_anchors.py
git commit -m "feat: add fix mode for inserting missing anchors"
```

---

### Task 6: CLI entry point

Wire up `main()` with `--fix` flag and output formatting.

**Files:**
- Modify: `scripts/validate_anchors.py`

- [ ] **Step 1: Write the CLI entry point**

Add to `scripts/validate_anchors.py`:

```python
def main() -> None:
    fix_mode = "--fix" in sys.argv

    if fix_mode:
        fixed = fix_missing_anchors()
        if fixed:
            print(f"Fixed {fixed} missing anchor(s).")
        # Re-check after fixing
        broken, unreferenced = check_anchors()
        if broken:
            print(f"\n{len(broken)} broken reference(s) (manual fix needed):")
            for msg in broken:
                print(f"  {msg}")
    else:
        broken, unreferenced = check_anchors()

    if not broken:
        # Count total refs for summary
        total = 0
        for doc_name in DOC_FILES:
            doc_path = ROOT / doc_name
            if doc_path.exists():
                total += len(find_anchor_refs(doc_path))
        print(f"{total} reference(s) checked, all resolved.")

    if unreferenced:
        print(f"\n{len(unreferenced)} anchor(s) defined but unreferenced (info):")
        for msg in unreferenced:
            print(f"  {msg}")

    if broken:
        if not fix_mode:
            print(f"\n{len(broken)} broken reference(s):")
            for msg in broken:
                print(f"  {msg}")
        sys.exit(1)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Smoke-test the CLI**

Run: `python scripts/validate_anchors.py 2>&1 | head -5`
Expected: `0 reference(s) checked, all resolved.` (no `§` refs exist in docs yet).

- [ ] **Step 3: Commit**

```bash
git add scripts/validate_anchors.py
git commit -m "feat: add CLI entry point for validate_anchors"
```

---

## Chunk 2: migrate_to_anchors.py

The one-time migration script. Reads old `:NN` references, inserts anchors into
source files, and rewrites documentation.

### Task 7: Source-side anchor insertion from old refs

Reads `:NN` references from verify_line_refs.py's `extract_refs()`, builds
anchor names, and inserts anchor comments into source files.

**Files:**
- Create: `scripts/migrate_to_anchors.py`
- Create: `tests/test_migrate_anchors.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_migrate_anchors.py
#!/usr/bin/env python3
"""Tests for migrate_to_anchors.py."""
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from migrate_to_anchors import insert_source_anchors, build_anchor_name


class TestBuildAnchorName(unittest.TestCase):
    """Derive §namespace.symbol from file path and symbol name."""

    def test_shared_script(self):
        name = build_anchor_name("scripts/validate_config.py", "parse_simple_toml")
        self.assertEqual(name, "validate_config.parse_simple_toml")

    def test_skill_script(self):
        name = build_anchor_name(
            "skills/sprint-setup/scripts/bootstrap_github.py", "create_label"
        )
        self.assertEqual(name, "bootstrap_github.create_label")

    def test_strips_parens(self):
        name = build_anchor_name("scripts/validate_config.py", "gh()")
        self.assertEqual(name, "validate_config.gh")

    def test_strips_asterisks(self):
        name = build_anchor_name("scripts/validate_config.py", "_REQUIRED_FILES")
        self.assertEqual(name, "validate_config._REQUIRED_FILES")


class TestInsertSourceAnchors(unittest.TestCase):
    """Insert # §... comments into Python source files."""

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        src = self.tmpdir / "scripts"
        src.mkdir()
        (src / "mymod.py").write_text(textwrap.dedent("""\
            import os

            def my_func():
                pass

            class MyClass:
                pass

            MY_CONST = 42
        """))

    def test_inserts_anchor_above_function(self):
        refs = [("scripts/mymod.py", "my_func", 3, 1)]
        count = insert_source_anchors(refs, root=self.tmpdir)
        self.assertEqual(count, 1)
        content = (self.tmpdir / "scripts" / "mymod.py").read_text()
        lines = content.splitlines()
        anchor_idx = next(i for i, l in enumerate(lines) if "§mymod.my_func" in l)
        self.assertIn("def my_func", lines[anchor_idx + 1])

    def test_skips_if_anchor_exists(self):
        (self.tmpdir / "scripts" / "mymod.py").write_text(
            "# §mymod.my_func\ndef my_func():\n    pass\n"
        )
        refs = [("scripts/mymod.py", "my_func", 2, 1)]
        count = insert_source_anchors(refs, root=self.tmpdir)
        self.assertEqual(count, 0)

    def test_handles_multiple_refs_same_file(self):
        refs = [
            ("scripts/mymod.py", "my_func", 3, 1),
            ("scripts/mymod.py", "MyClass", 6, 2),
            ("scripts/mymod.py", "MY_CONST", 9, 3),
        ]
        count = insert_source_anchors(refs, root=self.tmpdir)
        self.assertEqual(count, 3)
        content = (self.tmpdir / "scripts" / "mymod.py").read_text()
        self.assertIn("# §mymod.my_func", content)
        self.assertIn("# §mymod.MyClass", content)
        self.assertIn("# §mymod.MY_CONST", content)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_migrate_anchors.py -v 2>&1 | head -10`
Expected: ImportError — module does not exist.

- [ ] **Step 3: Write implementation**

```python
# scripts/migrate_to_anchors.py
#!/usr/bin/env python3
"""One-time migration: insert § anchors and rewrite doc references.

Usage:
    python migrate_to_anchors.py              # dry run (print what would change)
    python migrate_to_anchors.py --apply      # apply changes

Reuses extract_refs() from verify_line_refs.py to read existing :NN references.
Delete this script after successful migration.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from validate_anchors import NAMESPACE_MAP, find_anchor_defs, _find_symbol_line
from verify_line_refs import extract_refs

# Reverse lookup: file stem -> full relative path (for bare filename refs)
_STEM_TO_PATH = {Path(v).stem: v for v in NAMESPACE_MAP.values()}


def build_anchor_name(file_path: str, symbol: str) -> str:
    """Derive §namespace.symbol from a file path and symbol name."""
    stem = Path(file_path).stem  # e.g., "validate_config"
    clean = symbol.strip("()*")
    return f"{stem}.{clean}"


def insert_source_anchors(
    refs: list[tuple[str, str, int, int]],
    root: Path | None = None,
) -> int:
    """Insert # §... anchor comments into source files.

    Args:
        refs: [(rel_file_path, symbol, claimed_line, doc_line), ...]
        root: Project root directory.

    Returns: Number of anchors inserted.
    """
    root = root or ROOT

    # Deduplicate: same file+symbol may be referenced multiple times
    unique: dict[str, tuple[str, int]] = {}  # anchor_name -> (file_path, claimed_line)
    for file_path, symbol, claimed_line, _ in refs:
        anchor_name = build_anchor_name(file_path, symbol)
        if anchor_name not in unique:
            unique[anchor_name] = (file_path, claimed_line)

    # Group by file
    by_file: dict[str, list[tuple[str, int]]] = {}  # file -> [(anchor_name, line)]
    for anchor_name, (file_path, claimed_line) in unique.items():
        full = root / file_path
        if not full.exists():
            continue

        # Check if anchor already exists
        existing = find_anchor_defs(full)
        if anchor_name in existing:
            continue

        # Find actual symbol line (may have drifted from claimed)
        symbol = anchor_name.split(".", 1)[1]
        actual_line = _find_symbol_line(full, symbol)
        if actual_line is None:
            # Fall back to claimed line if symbol search fails
            actual_line = claimed_line

        by_file.setdefault(file_path, []).append((anchor_name, actual_line))

    # Insert anchors (bottom-up to preserve line numbers)
    total = 0
    for file_path, anchors in by_file.items():
        full = root / file_path
        lines = full.read_text(encoding="utf-8").splitlines()
        for anchor_name, target_line in sorted(anchors, key=lambda x: x[1], reverse=True):
            idx = target_line - 1
            if idx < 0 or idx > len(lines):
                continue
            if file_path.endswith(".py"):
                lines.insert(idx, f"# §{anchor_name}")
            else:
                lines.insert(idx, f"<!-- §{anchor_name} -->")
            total += 1
        full.write_text("\n".join(lines) + "\n", encoding="utf-8")

    return total
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_migrate_anchors.py -v`
Expected: All 7 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/migrate_to_anchors.py tests/test_migrate_anchors.py
git commit -m "feat: add source-side anchor insertion for migration"
```

---

### Task 8: Doc-side rewriter for CLAUDE.md

Rewrites `:NN` references in CLAUDE.md to `§` anchor references.

**Files:**
- Modify: `tests/test_migrate_anchors.py`
- Modify: `scripts/migrate_to_anchors.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_migrate_anchors.py`:

```python
from migrate_to_anchors import rewrite_claude_md_refs


class TestRewriteClaudeMd(unittest.TestCase):
    """Rewrite :NN refs in CLAUDE.md-style tables."""

    def test_table_symbol_ref(self):
        line = "| `scripts/validate_config.py` | desc | `parse_simple_toml()` :47, `load_config()` :457 |"
        result = rewrite_claude_md_refs(line)
        self.assertIn("§validate_config.parse_simple_toml", result)
        self.assertIn("§validate_config.load_config", result)
        self.assertNotIn(":47", result)
        self.assertNotIn(":457", result)

    def test_skill_entry_point_ref(self):
        line = "| sprint-run | `skills/sprint-run/SKILL.md` | Phase detection :29, Phase 1: Kickoff :44 |"
        result = rewrite_claude_md_refs(line)
        self.assertNotIn(":29", result)
        self.assertNotIn(":44", result)

    def test_prose_file_ref(self):
        line = "see `validate_config.py:260`"
        result = rewrite_claude_md_refs(line)
        self.assertNotIn(":260", result)

    def test_no_ref_unchanged(self):
        line = "This line has no references."
        result = rewrite_claude_md_refs(line)
        self.assertEqual(result, line)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_migrate_anchors.py::TestRewriteClaudeMd -v 2>&1 | head -10`
Expected: ImportError — `rewrite_claude_md_refs` not defined.

- [ ] **Step 3: Write implementation**

Add to `scripts/migrate_to_anchors.py`:

```python
def _symbol_to_anchor(file_path: str, symbol: str) -> str:
    """Convert a file path + symbol into a §anchor reference."""
    stem = Path(file_path).stem
    clean = symbol.strip("()*")
    return f"§{stem}.{clean}"


def _slug_from_text(text: str) -> str:
    """Convert heading/section text to a snake_case slug."""
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def rewrite_claude_md_refs(line: str) -> str:
    """Rewrite a single line of CLAUDE.md, replacing :NN refs with § anchors.

    Handles:
    - `symbol()` :NNN in table rows with a file path
    - `file.py:NNN` inline refs
    - bare Section Name :NNN in skill entry point tables
    """
    # Pattern A: table row with file path and `symbol()` :NNN
    file_match = re.search(r"`((?:scripts|skills)/[^`]+\.py)`", line)
    if file_match:
        file_path = file_match.group(1)
        # Replace `symbol()` :NNN -> `symbol()` §ns.symbol
        def repl_symbol(m):
            symbol = m.group(1).strip("()")
            return f"`{m.group(1)}` {_symbol_to_anchor(file_path, symbol)}"
        line = re.sub(r"`([A-Za-z_][A-Za-z0-9_.*()]*)`\s*:(\d+)", repl_symbol, line)

    # Pattern A2: SKILL.md entry point table — Section Name :NNN
    skill_match = re.search(r"`(skills/([^/]+)/SKILL\.md)`", line)
    if skill_match:
        skill_name = skill_match.group(2)  # e.g., "sprint-run"
        # Replace Section Name :NNN -> Section Name §skill.slug
        # Note: char class excludes ':' to avoid matching fragments like "Phase 1:"
        # Delimiter requires comma, pipe, or start-of-segment before section name
        def repl_section(m):
            section_text = m.group(1).strip()
            slug = _slug_from_text(section_text)
            return f"{m.group(1)} §{skill_name}.{slug}"
        line = re.sub(r"(?:(?<=,\s)|(?<=\|\s))([A-Za-z][A-Za-z0-9 ()-]*?)\s+:(\d+)", repl_section, line)

    # Pattern B: reference .md table — Section Name :NNN
    ref_match = re.search(r"`(skills/[^`]+/(?:references|agents)/([^`]+)\.md)`", line)
    if ref_match and not file_match and not skill_match:
        ref_stem = ref_match.group(2)  # e.g., "ceremony-kickoff"
        def repl_ref_section(m):
            section_text = m.group(1).strip()
            slug = _slug_from_text(section_text)
            return f"{m.group(1)} §{ref_stem}.{slug}"
        line = re.sub(r"([A-Za-z][A-Za-z0-9 :()-]*?)\s+:(\d+)", repl_ref_section, line)

    # Pattern C: `file.py:NNN` inline refs (with or without path prefix)
    def _resolve_file_path(raw_path: str) -> str | None:
        """Resolve a possibly-bare filename to its full relative path."""
        # Already has prefix? Use as-is if it exists.
        if raw_path.startswith(("scripts/", "skills/")):
            if (ROOT / raw_path).exists():
                return raw_path
        # Bare filename — reverse lookup from NAMESPACE_MAP
        stem = Path(raw_path).stem
        return _STEM_TO_PATH.get(stem)

    def repl_inline(m):
        raw_path = m.group(1)
        claimed = int(m.group(2))
        file_path = _resolve_file_path(raw_path)
        if not file_path:
            return m.group(0)
        full = ROOT / file_path
        if full.exists():
            lines = full.read_text(encoding="utf-8").splitlines()
            if 0 < claimed <= len(lines):
                target = lines[claimed - 1]
                sym_m = re.match(r"(?:def|class)\s+(\w+)|(\w+)\s*[:=]", target.strip())
                if sym_m:
                    symbol = sym_m.group(1) or sym_m.group(2)
                    return _symbol_to_anchor(file_path, symbol)
        return m.group(0)  # fallback: leave unchanged

    # Backtick-wrapped refs (with or without path prefix)
    line = re.sub(r"`([^`]+\.py):(\d+)(?:-\d+)?`", repl_inline, line)
    # Bare refs (no backticks, with or without path prefix)
    line = re.sub(r"(?<!\`)(\w[\w/.-]*\.py):(\d+)(?:-\d+)?(?![\d`])", repl_inline, line)

    return line
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_migrate_anchors.py::TestRewriteClaudeMd -v`
Expected: All 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/migrate_to_anchors.py tests/test_migrate_anchors.py
git commit -m "feat: add CLAUDE.md doc-side rewriter for migration"
```

---

### Task 9: Doc-side rewriter for CHEATSHEET.md

Rewrites CHEATSHEET.md tables: `| Line |` column → `| Anchor |` column.

**Files:**
- Modify: `tests/test_migrate_anchors.py`
- Modify: `scripts/migrate_to_anchors.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_migrate_anchors.py`:

```python
from migrate_to_anchors import rewrite_cheatsheet_table


class TestRewriteCheatsheet(unittest.TestCase):
    """Rewrite CHEATSHEET.md Line-based tables to Anchor-based."""

    def test_script_function_table(self):
        """| Line | Function | → | Anchor | Function |"""
        lines = [
            "### scripts/validate_config.py",
            "| Line | Function | Purpose |",
            "|------|----------|---------|",
            "| 22 | `gh()` | Shared GitHub CLI wrapper |",
            "| 47 | `parse_simple_toml()` | Custom TOML parser |",
        ]
        result = rewrite_cheatsheet_table(lines)
        self.assertIn("| Anchor |", result[1])
        self.assertIn("§validate_config.gh", result[3])
        self.assertIn("§validate_config.parse_simple_toml", result[4])
        self.assertNotIn("| 22 |", result[3])

    def test_section_table(self):
        """| Line | Section | → | Anchor | Section |"""
        lines = [
            "### skills/sprint-setup/references/github-conventions.md",
            "| Line | Section |",
            "|------|---------|",
            "| 5 | Label taxonomy |",
        ]
        result = rewrite_cheatsheet_table(lines)
        self.assertIn("§github-conventions.label_taxonomy", result[3])

    def test_non_table_lines_unchanged(self):
        lines = [
            "### scripts/validate_config.py",
            "Some prose text.",
        ]
        result = rewrite_cheatsheet_table(lines)
        self.assertEqual(result[1], "Some prose text.")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_migrate_anchors.py::TestRewriteCheatsheet -v 2>&1 | head -10`
Expected: ImportError.

- [ ] **Step 3: Write implementation**

Add to `scripts/migrate_to_anchors.py`:

```python
def rewrite_cheatsheet_table(lines: list[str]) -> list[str]:
    """Rewrite a CHEATSHEET.md section's tables from Line-based to Anchor-based.

    Input is a list of lines for one ### section (starting with the ### heading).
    """
    if not lines:
        return lines

    result = list(lines)  # copy

    # Extract namespace from heading: ### path/to/file.ext
    heading = lines[0]
    heading_match = re.match(r"^###\s+(.+)$", heading)
    if not heading_match:
        return result
    file_path = heading_match.group(1).strip()
    stem = Path(file_path).stem  # e.g., "validate_config" or "github-conventions"

    # Determine if this is a Python script or markdown reference file
    is_python = file_path.endswith(".py")

    for i in range(1, len(result)):
        line = result[i]

        # Rewrite header row
        if re.match(r"\|\s*Line\s*\|", line):
            result[i] = line.replace("Line", "Anchor", 1)
            continue

        # Rewrite separator row (widen for anchor column)
        if re.match(r"\|\s*-+\s*\|", line):
            result[i] = re.sub(r"\|(\s*-+\s*)\|", "|--------|", line, count=1)
            continue

        # Rewrite data rows: | NNN | content... |
        row_match = re.match(r"\|\s*(\d+)\s*\|\s*(.+)", line)
        if row_match:
            line_num = row_match.group(1)
            rest = row_match.group(2)

            if is_python:
                # Extract function/constant name from backticks
                sym_match = re.search(r"`([A-Za-z_]\w*(?:\(\))?)`", rest)
                if sym_match:
                    symbol = sym_match.group(1).strip("()")
                    anchor = f"§{stem}.{symbol}"
                else:
                    # Constant or non-backtick name
                    word_match = re.search(r"([A-Z_][A-Z0-9_]+)", rest)
                    symbol = word_match.group(1) if word_match else line_num
                    anchor = f"§{stem}.{symbol}"
            else:
                # Markdown section — derive slug from section name
                # rest looks like: "Label taxonomy |" or "Label taxonomy (details) |"
                section_text = rest.split("|")[0].strip()
                slug = _slug_from_text(section_text)
                anchor = f"§{stem}.{slug}"

            result[i] = f"| {anchor} | {rest}"

    return result
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_migrate_anchors.py::TestRewriteCheatsheet -v`
Expected: All 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/migrate_to_anchors.py tests/test_migrate_anchors.py
git commit -m "feat: add CHEATSHEET.md table rewriter for migration"
```

---

### Task 10: Migration CLI entry point

Wire up the full migration pipeline: extract old refs → insert anchors → rewrite docs.

**Files:**
- Modify: `scripts/migrate_to_anchors.py`

- [ ] **Step 1: Write the main() function**

Add to `scripts/migrate_to_anchors.py`:

```python
def rewrite_cheatsheet_file(cheatsheet_path: Path) -> str:
    """Rewrite entire CHEATSHEET.md file. Returns new content."""
    text = cheatsheet_path.read_text(encoding="utf-8")
    lines = text.splitlines()

    # Split into sections by ### headings
    sections: list[list[str]] = []
    current: list[str] = []
    for line in lines:
        if line.startswith("### ") and current:
            sections.append(current)
            current = [line]
        else:
            current.append(line)
    if current:
        sections.append(current)

    # Rewrite sections that have ### file-path headings
    result_lines: list[str] = []
    for section in sections:
        if section and re.match(r"^###\s+(scripts|skills)/", section[0]):
            section = rewrite_cheatsheet_table(section)
        # For prose sections under ### file headings, inject file context
        # so rewrite_claude_md_refs can resolve inline :NN refs.
        # This handles the subagent template prose (implementer.md, reviewer.md)
        # which have inline "Section :NN" refs but no file path on the same line.
        heading_file = None
        if section and re.match(r"^###\s+(skills/\S+\.md)", section[0]):
            heading_file = re.match(r"^###\s+(skills/\S+\.md)", section[0]).group(1)
        rewritten = []
        for line in section:
            if heading_file and re.search(r":\d+", line) and not line.startswith("###"):
                # Inject file context for rewrite_claude_md_refs Pattern B
                ref_stem = Path(heading_file).stem
                def repl_prose_ref(m):
                    section_text = m.group(1).strip()
                    slug = _slug_from_text(section_text)
                    return f"{m.group(1)} §{ref_stem}.{slug}"
                line = re.sub(
                    r"(?:(?<=,\s)|(?<=:\s)|(?<=\|\s))([A-Za-z][A-Za-z0-9 ()-]*?)\s+:(\d+)",
                    repl_prose_ref, line,
                )
            else:
                line = rewrite_claude_md_refs(line)
            rewritten.append(line)
        result_lines.extend(rewritten)

    return "\n".join(result_lines) + "\n"


def main() -> None:
    apply = "--apply" in sys.argv

    # Pass 1: Extract old refs
    doc_files = [ROOT / "CLAUDE.md", ROOT / "CHEATSHEET.md"]
    all_refs: list[tuple[str, str, int, int]] = []
    for doc in doc_files:
        if doc.exists():
            all_refs.extend(extract_refs(doc))

    print(f"Found {len(all_refs)} old :NN references.")

    if not all_refs:
        print("Nothing to migrate.")
        return

    # Also extract refs from CHEATSHEET.md section tables (not caught by extract_refs)
    # extract_refs only catches Python file refs; we need markdown section refs too
    cheatsheet = ROOT / "CHEATSHEET.md"
    if cheatsheet.exists():
        text = cheatsheet.read_text(encoding="utf-8")
        for line in text.splitlines():
            # Match ### skills/.../references/name.md or ### skills/.../SKILL.md
            hdr = re.match(r"^###\s+(skills/[^\s]+\.md)$", line)
            if hdr:
                file_path = hdr.group(1)
                # These are handled by rewrite_cheatsheet_table, not insert_source_anchors
                pass

    # Pass 1: Insert anchors into source files
    if apply:
        count = insert_source_anchors(all_refs)
        print(f"Inserted {count} anchor(s) into source files.")
    else:
        print("[Dry run] Would insert anchors into source files.")

    # Pass 2: Rewrite CLAUDE.md
    claude_md = ROOT / "CLAUDE.md"
    if claude_md.exists():
        original = claude_md.read_text(encoding="utf-8")
        rewritten_lines = [rewrite_claude_md_refs(line) for line in original.splitlines()]
        new_content = "\n".join(rewritten_lines) + "\n"
        changes = sum(1 for a, b in zip(original.splitlines(), new_content.splitlines()) if a != b)
        if apply:
            claude_md.write_text(new_content, encoding="utf-8")
            print(f"Rewrote {changes} line(s) in CLAUDE.md.")
        else:
            print(f"[Dry run] Would rewrite {changes} line(s) in CLAUDE.md.")

    # Pass 2b: Rewrite CHEATSHEET.md
    if cheatsheet.exists():
        original = cheatsheet.read_text(encoding="utf-8")
        new_content = rewrite_cheatsheet_file(cheatsheet)
        changes = sum(1 for a, b in zip(original.splitlines(), new_content.splitlines()) if a != b)
        if apply:
            cheatsheet.write_text(new_content, encoding="utf-8")
            print(f"Rewrote {changes} line(s) in CHEATSHEET.md.")
        else:
            print(f"[Dry run] Would rewrite {changes} line(s) in CHEATSHEET.md.")

    # Pass 3: Validate
    if apply:
        print("\nRunning validation...")
        from validate_anchors import check_anchors
        broken, unreferenced = check_anchors()
        if broken:
            print(f"\n{len(broken)} broken reference(s) — manual fix needed:")
            for msg in broken:
                print(f"  {msg}")
        else:
            print("All references resolved.")
    else:
        print("\n[Dry run] No changes made. Run with --apply to execute.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Smoke-test dry run**

Run: `python scripts/migrate_to_anchors.py 2>&1 | head -10`
Expected: Shows ref count and "[Dry run]" messages.

- [ ] **Step 3: Commit**

```bash
git add scripts/migrate_to_anchors.py
git commit -m "feat: add migration CLI with dry-run and apply modes"
```

---

## Chunk 3: Execute migration and cleanup

### Task 11: Insert anchors into markdown source files

The migration script's `insert_source_anchors` only handles Python files
referenced from CLAUDE.md/CHEATSHEET.md via `extract_refs()`. Markdown files
(SKILL.md, reference .md, agent .md) need anchors too, but their references
come from CHEATSHEET.md section tables and CLAUDE.md skill/reference tables.

These are best handled by `validate_anchors.py --fix` AFTER the doc-side
rewrite, since the rewritten docs will contain the `§` references that
`--fix` knows how to resolve.

- [ ] **Step 1: Run migration dry run**

Run: `python scripts/migrate_to_anchors.py`
Review output. Verify ref count matches expectations (~150+).

- [ ] **Step 2: Run migration for real**

Run: `python scripts/migrate_to_anchors.py --apply`
Expected: Reports anchors inserted and lines rewritten.

- [ ] **Step 3: Run autofix for markdown anchors**

Run: `python scripts/validate_anchors.py --fix`
Expected: Inserts `<!-- §... -->` anchors into SKILL.md and reference .md files.

- [ ] **Step 4: Run full validation**

Run: `python scripts/validate_anchors.py`
Expected: All references resolved.

- [ ] **Step 5: Manual review of the diff**

Run: `git diff --stat && git diff CLAUDE.md | head -80`
Review: anchors inserted correctly, doc references rewritten cleanly.

- [ ] **Step 6: Commit the migration**

Review `git status` to verify only expected files are modified. Stage explicitly:

```bash
git add scripts/ skills/ CLAUDE.md CHEATSHEET.md
git commit -m "feat: migrate all line-number references to greppable § anchors"
```

---

### Task 12: Cleanup

Delete throwaway files and update all references to the old system.

**Files that reference `verify_line_refs.py` (must fix):**
- `Makefile` (lint target, lines 46-47)
- `tests/test_pipeline_scripts.py` (TestExtractRefs, TestFindSymbolLine, TestVerifyRef classes)
- `CLAUDE.md` / `CHEATSHEET.md` (any remaining mentions)

Ephemeral files that mention it (skip): `ADVERSARIAL-REVIEW.md`, `BUG-HUNTER-PUNCHLIST.md`, `recon/` files.

- [ ] **Step 1: Delete verify_line_refs.py**

```bash
git rm scripts/verify_line_refs.py
```

- [ ] **Step 2: Delete migrate_to_anchors.py**

```bash
git rm scripts/migrate_to_anchors.py
```

- [ ] **Step 3: Delete migration tests**

```bash
git rm tests/test_migrate_anchors.py
```

- [ ] **Step 4: Update Makefile**

Replace the two `verify_line_refs.py` lines in the `lint` target:
```makefile
# Remove these two lines:
$(PYTHON) -m py_compile scripts/verify_line_refs.py
$(PYTHON) scripts/verify_line_refs.py
# Replace with:
$(PYTHON) -m py_compile scripts/validate_anchors.py
$(PYTHON) scripts/validate_anchors.py
```

- [ ] **Step 5: Remove verify_line_refs tests from test_pipeline_scripts.py**

Delete the `TestExtractRefs`, `TestFindSymbolLine`, and `TestVerifyRef` test
classes and the `from verify_line_refs import ...` line. Run tests to confirm:

Run: `python -m pytest tests/test_pipeline_scripts.py -v 2>&1 | tail -5`
Expected: All remaining tests pass with no ImportError.

- [ ] **Step 6: Update CLAUDE.md and CHEATSHEET.md**

Add `validate_anchors.py` to the scripts table in CLAUDE.md with anchor refs.
Update the CHEATSHEET.md header text ("Quick-reference index with line numbers"
→ "Quick-reference index with greppable anchors"). Remove any remaining
mentions of `verify_line_refs.py`.

- [ ] **Step 7: Run final validation**

Run: `python scripts/validate_anchors.py`
Expected: All references resolved, zero broken.

Run: `python -m pytest tests/ -v 2>&1 | tail -10`
Expected: Full test suite passes.

- [ ] **Step 8: Commit cleanup**

```bash
git add scripts/validate_anchors.py Makefile tests/test_pipeline_scripts.py CLAUDE.md CHEATSHEET.md
git commit -m "chore: remove verify_line_refs.py and migration script, update docs"
```

---

### Known manual fixups

Some edge-case reference patterns may survive automated migration. After Task 12,
grep for any remaining `:NN` patterns and fix manually:

```bash
grep -nE ':\d{2,3}[^0-9]' CLAUDE.md CHEATSHEET.md | grep -v '§'
```

Known patterns that may need manual attention:
- `.md` file references in Common Modifications table (e.g., `kanban-protocol.md:6`)
- Standalone continuation refs (e.g., bare `:266` without a filename prefix)
- Any refs the automated rewriter could not resolve to a symbol
