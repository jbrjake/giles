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
        def repl_section(m):
            section_text = m.group(1).strip()
            slug = _slug_from_text(section_text)
            return f"{m.group(1)} §{skill_name}.{slug}"
        line = re.sub(r"(?:(?<=,\s)|(?<=\|\s))([A-Za-z][A-Za-z0-9 :()-]*?)\s+:(\d+)", repl_section, line)

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
        if raw_path.startswith(("scripts/", "skills/")):
            if (ROOT / raw_path).exists():
                return raw_path
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
