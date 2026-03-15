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
        line = re.sub(r"(?:(?<=,\s)|(?<=\|\s))([A-Za-z][A-Za-z0-9 :()&/-]*?)\s+:(\d+)", repl_ref_section, line)

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
    # For SKILL.md files, use the parent dir name (e.g., "sprint-run") as namespace
    # For other files, use the file stem (e.g., "validate_config", "github-conventions")
    if Path(file_path).name == "SKILL.md":
        stem = Path(file_path).parent.name  # e.g., "sprint-run"
    else:
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
                    symbol = word_match.group(1) if word_match else row_match.group(1)
                    anchor = f"§{stem}.{symbol}"
            else:
                # Markdown section — derive slug from section name
                section_text = rest.split("|")[0].strip()
                slug = _slug_from_text(section_text)
                anchor = f"§{stem}.{slug}"

            result[i] = f"| {anchor} | {rest}"

    return result


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
        heading_file = None
        if section and re.match(r"^###\s+(skills/\S+\.md)", section[0]):
            heading_file = re.match(r"^###\s+(skills/\S+\.md)", section[0]).group(1)
        rewritten = []
        for line in section:
            if heading_file and re.search(r":\d+", line) and not line.startswith("###"):
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
    from verify_line_refs import extract_refs

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

    # Pass 1b: Insert anchors into source files
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
    cheatsheet = ROOT / "CHEATSHEET.md"
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
