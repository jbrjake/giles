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
