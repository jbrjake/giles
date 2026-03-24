#!/usr/bin/env python3
"""Verify every Python script in the project is covered by ``make lint``.

Scans scripts/, skills/\\*/scripts/, and hooks/ for .py files, then
compares against py_compile entries in the Makefile.  Exits non-zero
if any script is missing from the lint target.

Addresses PAT-001 (batch addition without full wiring) — the recurring
pattern where new scripts are added but not wired into the Makefile.
"""

import re
import sys
from pathlib import Path

# Directories to scan for Python scripts.
_SCAN_DIRS = ("scripts", "hooks")
_SCAN_GLOBS = ("skills/*/scripts",)


# §check_lint_inventory.extract_lint_files
def extract_lint_files(makefile: Path) -> set[str]:
    """Extract file paths from py_compile lines in the Makefile."""
    text = makefile.read_text()
    return set(re.findall(r"py_compile\s+(\S+\.py)", text))


# §check_lint_inventory.discover_scripts
def discover_scripts(root: Path) -> set[str]:
    """Find all .py files in script and hook directories."""
    found: set[str] = set()
    for d in _SCAN_DIRS:
        target = root / d
        if target.is_dir():
            for f in target.rglob("*.py"):
                if f.name == "__init__.py":
                    continue
                found.add(str(f.relative_to(root)))
    for pattern in _SCAN_GLOBS:
        for d in root.glob(pattern):
            if d.is_dir():
                for f in d.rglob("*.py"):
                    if f.name == "__init__.py":
                        continue
                    found.add(str(f.relative_to(root)))
    return found


# §check_lint_inventory.main
def main() -> int:
    root = Path(__file__).resolve().parent.parent
    makefile = root / "Makefile"

    if not makefile.exists():
        print("lint-inventory: no Makefile found", file=sys.stderr)
        return 1

    lint_files = extract_lint_files(makefile)
    disk_files = discover_scripts(root)

    missing = sorted(disk_files - lint_files)
    stale = sorted(lint_files - disk_files)

    ok = True
    if missing:
        ok = False
        print(f"lint-inventory: {len(missing)} script(s) not in Makefile lint:")
        for f in missing:
            print(f"  + {f}")
    if stale:
        print(f"lint-inventory: {len(stale)} stale Makefile lint entry(s):")
        for f in stale:
            print(f"  - {f}")

    if ok and not stale:
        print("lint-inventory: OK")

    return 1 if not ok else 0


if __name__ == "__main__":
    sys.exit(main())
