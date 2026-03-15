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


_REF_RE = re.compile(r"§([\w-]+\.[\w_]+)(?=[\s,|]|$)")


def find_anchor_refs(doc_path: Path) -> list[tuple[str, int]]:
    """Return [(anchor_name, line_number), ...] for all § refs in a doc file."""
    refs: list[tuple[str, int]] = []
    text = doc_path.read_text(encoding="utf-8")
    for i, line in enumerate(text.splitlines(), 1):
        for m in _REF_RE.finditer(line):
            refs.append((m.group(1), i))
    return refs


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
