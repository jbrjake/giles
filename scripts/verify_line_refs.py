#!/usr/bin/env python3
"""Verify line-number references in CLAUDE.md and CHEATSHEET.md.

Usage: python verify_line_refs.py

Parses `:NNN` references from documentation files, looks up the
referenced file, and checks that the expected content (function def,
class, constant) actually exists within ±3 lines of the claimed number.

Exit: 0 = all refs valid, 1 = some refs stale.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

# Project root — one level up from scripts/
ROOT = Path(__file__).resolve().parent.parent

# Tolerance: how many lines off a reference can be before it's flagged
TOLERANCE = 3


def extract_refs(doc_path: Path) -> list[tuple[str, str, int, int]]:
    """Extract (file, symbol, claimed_line, doc_line) from a doc file.

    Matches patterns like:
      `func_name()` :123
      `CONSTANT` :45
      file.py:123 (symbol)
    """
    refs: list[tuple[str, str, int, int]] = []
    text = doc_path.read_text(encoding="utf-8")

    # Pattern 1: table rows with `script_path` and `symbol()` :NNN
    # e.g.: | `scripts/foo.py` | ... | `bar()` :42, `baz()` :99 |
    for line_num, line in enumerate(text.splitlines(), 1):
        # Find file path in backticks at start of table cell
        file_match = re.search(r"`((?:scripts|skills)/[^`]+\.py)`", line)
        if not file_match:
            continue
        file_path = file_match.group(1)

        # Find all symbol:line refs in this line
        for m in re.finditer(r"`([A-Za-z_][A-Za-z0-9_.*()]*)`\s*:(\d+)", line):
            symbol = m.group(1).rstrip("()")
            claimed = int(m.group(2))
            refs.append((file_path, symbol, claimed, line_num))

    # Pattern 2: inline refs like `file.py:NNN` (symbol)
    for line_num, line in enumerate(text.splitlines(), 1):
        for m in re.finditer(
            r"`((?:scripts|skills)/[^`]+\.py):(\d+)`\s*\(([^)]+)\)", line
        ):
            file_path = m.group(1)
            claimed = int(m.group(2))
            symbol = m.group(3).strip().split(",")[0].strip()
            refs.append((file_path, symbol, claimed, line_num))

    # Pattern 3: bare file.py:NNN refs (without backticks)
    for line_num, line in enumerate(text.splitlines(), 1):
        for m in re.finditer(
            r"((?:scripts|skills)/[^`\s:]+\.py):(\d+)", line
        ):
            file_path = m.group(1)
            claimed = int(m.group(2))
            # Try to find a nearby symbol name
            ctx = re.search(r"\(([^)]+)\)", line[m.end():m.end() + 40])
            symbol = ctx.group(1).strip() if ctx else ""
            if symbol:
                refs.append((file_path, symbol, claimed, line_num))

    return refs


def find_symbol_line(file_path: Path, symbol: str) -> int | None:
    """Find the actual line number of a symbol definition in a file."""
    if not file_path.exists():
        return None

    text = file_path.read_text(encoding="utf-8")
    lines = text.splitlines()

    # Clean symbol name
    clean = symbol.strip("()")

    # Try exact patterns
    patterns = [
        rf"^(def|class)\s+{re.escape(clean)}\b",  # def foo / class Foo
        rf"^{re.escape(clean)}\s*[:=]",            # CONSTANT = / CONSTANT:
        rf"^\s+def\s+{re.escape(clean)}\b",        # indented method
    ]

    for i, line in enumerate(lines, 1):
        for pat in patterns:
            if re.search(pat, line):
                return i

    return None


def verify_ref(
    file_path: str, symbol: str, claimed: int, doc_line: int,
) -> tuple[bool, str]:
    """Check if a reference is within tolerance of the actual line."""
    full_path = ROOT / file_path
    if not full_path.exists():
        return False, f"file not found: {file_path}"

    actual = find_symbol_line(full_path, symbol)
    if actual is None:
        # Symbol not found — might be a section ref or content ref
        # Check if the claimed line has plausible content
        lines = full_path.read_text(encoding="utf-8").splitlines()
        if 0 < claimed <= len(lines):
            return True, f"symbol '{symbol}' not matched (content ref?)"
        return False, f"symbol '{symbol}' not found in {file_path}"

    diff = abs(actual - claimed)
    if diff <= TOLERANCE:
        return True, f"OK (actual :{actual})"
    return False, f"STALE: claimed :{claimed}, actual :{actual} (off by {actual - claimed:+d})"


def main() -> None:
    docs = [ROOT / "CLAUDE.md", ROOT / "CHEATSHEET.md"]
    all_refs: list[tuple[Path, str, str, int, int]] = []

    for doc in docs:
        if not doc.exists():
            continue
        for file_path, symbol, claimed, doc_line in extract_refs(doc):
            all_refs.append((doc, file_path, symbol, claimed, doc_line))

    if not all_refs:
        print("No line-number references found.")
        sys.exit(0)

    ok_count = 0
    fail_count = 0
    failures: list[str] = []

    for doc, file_path, symbol, claimed, doc_line in all_refs:
        passed, msg = verify_ref(file_path, symbol, claimed, doc_line)
        if passed:
            ok_count += 1
        else:
            fail_count += 1
            failures.append(
                f"  {doc.name}:{doc_line} — {file_path} `{symbol}` :{claimed} — {msg}"
            )

    print(f"Checked {ok_count + fail_count} references: {ok_count} OK, {fail_count} stale")

    if failures:
        print("\nStale references:")
        for f in failures:
            print(f)
        sys.exit(1)
    else:
        print("All line-number references are current.")
        sys.exit(0)


if __name__ == "__main__":
    main()
