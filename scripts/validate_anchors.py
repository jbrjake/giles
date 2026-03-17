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
    "commit": "scripts/commit.py",
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


# §validate_anchors.resolve_namespace
def resolve_namespace(namespace: str) -> str:
    """Return the relative file path for a namespace, or raise KeyError."""
    return NAMESPACE_MAP[namespace]


# Regex patterns for anchor definitions
_PY_ANCHOR_RE = re.compile(r"^# §([\w]+\.[\w]+)$")
_MD_ANCHOR_RE = re.compile(r"^<!-- §([\w-]+\.[\w_]+) -->$")


# §validate_anchors.find_anchor_defs
def find_anchor_defs(file_path: Path) -> dict[str, int]:
    """Return {anchor_name: line_number} for all anchors defined in a file."""
    defs: dict[str, int] = {}
    text = file_path.read_text(encoding="utf-8")
    for i, line in enumerate(text.split('\n'), 1):
        stripped = line.strip()
        m = _PY_ANCHOR_RE.match(stripped) or _MD_ANCHOR_RE.match(stripped)
        if m:
            defs[m.group(1)] = i
    return defs


_REF_RE = re.compile(r"§([\w-]+\.[\w_]+)(?=[\s,|.;:)\]!?'\"]|$)")


# §validate_anchors.find_anchor_refs
def find_anchor_refs(doc_path: Path) -> list[tuple[str, int]]:
    """Return [(anchor_name, line_number), ...] for all § refs in a doc file."""
    refs: list[tuple[str, int]] = []
    text = doc_path.read_text(encoding="utf-8")
    for i, line in enumerate(text.split('\n'), 1):
        for m in _REF_RE.finditer(line):
            refs.append((m.group(1), i))
    return refs


DOC_FILES = ["CLAUDE.md", "CHEATSHEET.md"]


# §validate_anchors.check_anchors
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


def _find_symbol_line(file_path: Path, symbol: str) -> int | None:
    """Find line number of a symbol definition (def/class/constant)."""
    text = file_path.read_text(encoding="utf-8")
    lines = text.split('\n')
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

    Slug matching uses multiple strategies in priority order:
    1. Exact match: heading slug == target slug
    2. Suffix match: heading slug ends with '_' + target slug
    3. Containment: all target slug words appear in heading slug in order
    This handles both short refs (phase_1_kickoff) and verbose refs
    (phase_1_sprint_kickoff_interactive) against the same heading.
    """
    text = file_path.read_text(encoding="utf-8")
    slug_parts = slug.split("_")

    # Collect candidates with match quality
    best: tuple[int, int] | None = None  # (priority, line)

    for i, line in enumerate(text.split('\n'), 1):
        if not line.startswith("#"):
            continue
        heading_text = re.sub(r"^#+\s*", "", line).strip()
        heading_slug = re.sub(r"[^a-z0-9]+", "_", heading_text.lower()).strip("_")

        if heading_slug == slug:
            return i  # exact match, return immediately
        if heading_slug.endswith("_" + slug):
            if best is None or best[0] > 1:
                best = (1, i)
        # Prefix: heading slug is a prefix of target (verbose CHEATSHEET slugs)
        elif slug.startswith(heading_slug + "_") or slug.startswith(heading_slug):
            if best is None or best[0] > 2:
                best = (2, i)
        # Containment: all slug parts appear in heading slug in order
        elif len(slug_parts) >= 2:
            h_parts = heading_slug.split("_")
            j = 0
            for hp in h_parts:
                if j < len(slug_parts) and hp == slug_parts[j]:
                    j += 1
            if j == len(slug_parts) and (best is None or best[0] > 3):
                best = (3, i)

    return best[1] if best else None


# §validate_anchors.fix_missing_anchors
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
        lines = full.read_text(encoding="utf-8").split('\n')
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


# §validate_anchors.main
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
