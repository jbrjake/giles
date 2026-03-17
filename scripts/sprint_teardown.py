#!/usr/bin/env python3
"""Safely remove sprint-config/ without damaging project files.

Symlinks are removed (they are pointers, not data). Generated files are
removed only after confirmation. Sprint tracking data and GitHub artifacts
are never touched.

No external dependencies — stdlib only.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


# §sprint_teardown.classify_entries
def classify_entries(config_dir: Path) -> tuple[list[Path], list[Path], list[Path]]:
    """Walk config_dir and classify every entry.

    Returns (symlinks, generated_files, unknown_files).
    Regular directories are handled separately after file removal.
    Directory symlinks are treated as symlinks (safe to unlink).
    """
    symlinks: list[Path] = []
    generated: list[Path] = []
    unknown: list[Path] = []

    # Known generated file names (created by sprint_init.py)
    # These are regular files written by _write() or _copy_skeleton().
    # Symlinks are already caught by the is_symlink() check above.
    generated_names = {
        "project.toml",
        "INDEX.md",
        "giles.md",
        "rules.md",
        "development.md",
        "architecture.md",
        "cheatsheet.md",
        "definition-of-done.md",
        ".sync-state.json",
        ".sprint-init-manifest.json",
    }

    # If a manifest exists, use it for more precise classification
    manifest_path = config_dir / ".sprint-init-manifest.json"
    manifest_files: set[str] = set()
    if manifest_path.is_file():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest_files = set(manifest.get("generated_files", []))
        except (json.JSONDecodeError, OSError):
            pass

    # First pass: catch directory symlinks before os.walk follows them.
    # os.walk follows symlinked dirs by default, so we need to find them
    # at each level before descending.
    for root, dirs, files in os.walk(config_dir, followlinks=False):
        root_path = Path(root)
        # Check subdirectories for symlinks (os.walk won't list these as files)
        for d in list(dirs):
            entry = root_path / d
            if entry.is_symlink():
                symlinks.append(entry)
                dirs.remove(d)  # Don't descend into symlinked dirs
        for name in files:
            entry = root_path / name
            # Compute path relative to config_dir for manifest lookup
            rel = str(entry.relative_to(config_dir))
            if entry.is_symlink():
                symlinks.append(entry)
            elif rel in manifest_files or name in generated_names:
                generated.append(entry)
            else:
                unknown.append(entry)

    symlinks.sort()
    generated.sort()
    unknown.sort()
    return symlinks, generated, unknown


# §sprint_teardown.collect_directories
def collect_directories(config_dir: Path) -> list[Path]:
    """Return all real directories under config_dir, deepest first (for safe rmdir)."""
    dirs: list[Path] = []
    for root, dirnames, _ in os.walk(config_dir, followlinks=False):
        # Skip symlinked directories — they are handled as symlinks, not dirs
        for d in list(dirnames):
            entry = Path(root) / d
            if entry.is_symlink():
                dirnames.remove(d)
            else:
                dirs.append(entry)
    # Add config_dir itself
    dirs.append(config_dir)
    # Sort deepest first so children are removed before parents
    dirs.sort(key=lambda p: len(p.parts), reverse=True)
    return dirs


def resolve_symlink_target(symlink: Path) -> Path | None:
    """Resolve what a symlink points to (the real file), or None if broken."""
    try:
        target = symlink.resolve()
        if target.exists():
            return target
        return None
    except (OSError, ValueError):
        return None


def symlink_display(symlink: Path, project_root: Path) -> str:
    """Format a symlink for display: relative_path → target."""
    rel = symlink.relative_to(project_root)
    raw_target = os.readlink(symlink)
    return f"  {rel} → {raw_target}"


def print_dry_run(
    config_dir: Path,
    project_root: Path,
    symlinks: list[Path],
    generated: list[Path],
    unknown: list[Path],
    directories: list[Path],
) -> None:
    """Print what would happen without making changes."""
    print("Sprint teardown — dry run\n")

    # Symlinks
    if symlinks:
        print(f"Symlinks (will be removed, targets untouched): [{len(symlinks)}]")
        for s in symlinks:
            print(symlink_display(s, project_root))
        print()
    else:
        print("Symlinks: none found\n")

    # Generated files
    if generated:
        print(f"Generated files (will be removed after confirmation): [{len(generated)}]")
        for g in generated:
            print(f"  {g.relative_to(project_root)}")
        print()
    else:
        print("Generated files: none found\n")

    # Unknown files
    if unknown:
        print(f"Unknown files (will be SKIPPED — you decide): [{len(unknown)}]")
        for u in unknown:
            print(f"  {u.relative_to(project_root)}")
        print()

    # Directories
    removable = [d for d in directories if d != config_dir or not unknown]
    if removable:
        print(f"Directories (will be removed if empty after cleanup): [{len(removable)}]")
        for d in removable:
            print(f"  {d.relative_to(project_root)}/")
        print()

    # Preserved
    print("Preserved (not touched):")
    # Check for sprints_dir
    sprints_candidates = [
        project_root / "docs" / "dev-team" / "sprints",
    ]
    # Try to read from project.toml if it exists
    toml_path = config_dir / "project.toml"
    if toml_path.exists():
        try:
            text = toml_path.read_text(encoding="utf-8")
            for line in text.split('\n'):
                if "sprints_dir" in line and "=" in line:
                    val = line.split("=", 1)[1].strip().strip('"').strip("'")
                    candidate = project_root / val
                    if candidate not in sprints_candidates:
                        sprints_candidates.insert(0, candidate)
        except OSError:
            pass

    for sp in sprints_candidates:
        if sp.exists():
            print(f"  {sp.relative_to(project_root)}/  (sprint tracking data)")
            break

    # Symlink targets
    for s in symlinks[:3]:
        target = resolve_symlink_target(s)
        if target:
            try:
                rel = target.relative_to(project_root)
                print(f"  {rel}  ✓ exists")
            except ValueError:
                pass
    if len(symlinks) > 3:
        print(f"  ... ({len(symlinks) - 3} more symlink targets)")

    print("  GitHub labels, milestones, issues, PRs (use gh CLI to clean up)")

    # Check for active loops
    active_loops = check_active_loops()
    print_loop_cleanup_hints(active_loops)

    print("\nNo changes made. Run without --dry-run to proceed.")


# §sprint_teardown.remove_symlinks
def remove_symlinks(symlinks: list[Path], project_root: Path) -> int:
    """Remove all symlinks. Returns count removed."""
    removed = 0
    for s in symlinks:
        try:
            os.unlink(s)
            print(f"  ✓ removed symlink: {s.relative_to(project_root)}")
            removed += 1
        except OSError as e:
            print(f"  ✗ failed to remove {s.relative_to(project_root)}: {e}")
    return removed


# §sprint_teardown.remove_generated
def remove_generated(generated: list[Path], project_root: Path, force: bool) -> int:
    """Remove generated files, prompting unless force=True. Returns count removed."""
    if not generated:
        return 0

    removed = 0
    remove_all = force

    for g in generated:
        rel = g.relative_to(project_root)
        if remove_all:
            do_remove = True
        else:
            try:
                answer = input(f"  Remove {rel}? [y/n/a(ll)] ").strip().lower()
            except EOFError:
                print("  Non-interactive mode — skipping remaining prompts.", file=sys.stderr)
                break
            if answer == "a":
                remove_all = True
                do_remove = True
            elif answer == "y":
                do_remove = True
            else:
                do_remove = False
                print(f"  — skipped {rel}")

        if do_remove:
            try:
                os.unlink(g)
                print(f"  ✓ removed: {rel}")
                removed += 1
            except OSError as e:
                print(f"  ✗ failed to remove {rel}: {e}")
    return removed


# §sprint_teardown.remove_empty_dirs
def remove_empty_dirs(directories: list[Path], project_root: Path) -> int:
    """Remove directories if empty, deepest first. Returns count removed."""
    removed = 0
    for d in directories:
        try:
            if d.exists() and not any(d.iterdir()):
                d.rmdir()
                print(f"  ✓ removed empty dir: {d.relative_to(project_root)}/")
                removed += 1
        except OSError as e:
            # BH-012: Only silence "not empty" errors; report others
            import errno
            if e.errno not in (errno.ENOTEMPTY, errno.ENOENT):
                print(f"  ✗ cannot remove {d}: {e}", file=sys.stderr)
    return removed


# §sprint_teardown.check_active_loops
def check_active_loops() -> list[str]:
    """Detect active /loop commands related to sprint-monitor.

    Returns a list of descriptions of active loops found.
    Detection is best-effort — we check common indicators.
    """
    findings: list[str] = []

    # Check for cron entries that reference sprint-monitor or check_status
    try:
        result = subprocess.run(
            ["crontab", "-l"], capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                line_lower = line.lower()
                if any(kw in line_lower for kw in [
                    "sprint-monitor", "sprint_monitor", "check_status",
                    "sprint-teardown", "sprint_teardown",
                ]):
                    findings.append(f"  crontab entry: {line.strip()}")
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass

    return findings


def print_loop_cleanup_hints(active_loops: list[str]) -> None:
    """Print guidance for stopping /loop commands."""
    print("\n/loop cleanup:")
    if active_loops:
        print("  Active sprint-related scheduled tasks found:")
        for finding in active_loops:
            print(finding)
        print()
        print("  Stop active /loop commands in Claude Code:")
        print("    /loop stop sprint-monitor")
        print("  Or stop all loops:")
        print("    /loop stop")
    else:
        print("  No sprint-related cron entries detected.")
        print("  If you have an active /loop in Claude Code, stop it:")
        print("    /loop stop sprint-monitor")
        print("    /loop stop  (stops all loops)")


# §sprint_teardown.print_github_cleanup_hints
def print_github_cleanup_hints() -> None:
    """Print manual GitHub cleanup commands."""
    print("\nGitHub cleanup (manual — not executed):")
    print("  Remove sprint labels:")
    print('    gh label list --limit 500 --json name --jq \'')
    print('      .[] | select(.name | test("^(kanban:|priority:|type:|persona:|sprint:|saga:)")) | .name\'')
    print("    | while read label; do gh label delete \"$label\" --yes; done")
    print()
    print("  Close milestones:")
    print("    gh api repos/{owner}/{repo}/milestones --jq '.[] | \"\\(.number) \\(.title)\"'")
    print()
    print("  Delete project board:")
    print("    gh project list --owner {owner}")
    print("    gh project delete {N} --owner {owner}")


# §sprint_teardown.main
def main() -> None:
    """Entry point."""
    if len(sys.argv) > 1 and sys.argv[1] in ("-h", "--help"):
        print(__doc__.strip())
        sys.exit(0)
    # Parse args
    dry_run = "--dry-run" in sys.argv
    force = "--force" in sys.argv or "-f" in sys.argv

    # Determine project root (current directory or arg)
    project_root = Path.cwd()
    for arg in sys.argv[1:]:
        if not arg.startswith("-"):
            candidate = Path(arg)
            if candidate.is_dir():
                project_root = candidate.resolve()
                break

    config_dir = project_root / "sprint-config"

    if not config_dir.exists():
        print("No sprint-config/ found. Nothing to tear down.")
        sys.exit(0)

    if not config_dir.is_dir():
        print(f"sprint-config exists but is not a directory: {config_dir}")
        sys.exit(1)

    # Classify everything
    symlinks, generated, unknown = classify_entries(config_dir)
    directories = collect_directories(config_dir)

    total_items = len(symlinks) + len(generated) + len(unknown)
    if total_items == 0 and not directories:
        print("sprint-config/ is empty. Removing it.")
        try:
            config_dir.rmdir()
            print("  ✓ removed sprint-config/")
        except OSError as e:
            print(f"  ✗ could not remove sprint-config/: {e}")
        sys.exit(0)

    # Record symlink targets before removal (for verification after)
    symlink_targets: list[tuple[Path, Path | None]] = []
    for s in symlinks:
        symlink_targets.append((s, resolve_symlink_target(s)))

    if dry_run:
        print_dry_run(config_dir, project_root, symlinks, generated,
                      unknown, directories)
        sys.exit(0)

    # BH-011: Warn about uncommitted changes before deletion
    try:
        r = subprocess.run(
            ["git", "diff", "--name-only", str(config_dir)],
            capture_output=True, text=True, timeout=10,
        )
        dirty_files = [f for f in r.stdout.strip().splitlines() if f]
        if dirty_files:
            print(f"\n⚠ Warning: {len(dirty_files)} uncommitted change(s) in {config_dir}/:",
                  file=sys.stderr)
            for f in dirty_files[:5]:
                print(f"    {f}", file=sys.stderr)
            if not force:
                print("Use --force to proceed anyway, or commit/stash first.",
                      file=sys.stderr)
                sys.exit(1)
    except (subprocess.TimeoutExpired, OSError):
        pass  # Not in a git repo, or git not available — proceed

    # Execute teardown
    print("Sprint teardown\n")

    # Phase 1: symlinks
    if symlinks:
        print(f"Removing {len(symlinks)} symlinks:")
        sym_count = remove_symlinks(symlinks, project_root)
    else:
        sym_count = 0

    # Phase 2: generated files
    if generated:
        print(f"\nGenerated files ({len(generated)}):")
        gen_count = remove_generated(generated, project_root, force)
    else:
        gen_count = 0

    # Phase 3: unknown files
    if unknown:
        print("\nUnknown files (skipped — remove manually if desired):")
        for u in unknown:
            print(f"  {u.relative_to(project_root)}")

    # Phase 4: empty directories
    print("\nCleaning up empty directories:")
    dir_count = remove_empty_dirs(directories, project_root)

    # Phase 5: verify targets
    print("\nVerifying project files are intact:")
    all_ok = True
    for symlink_path, target in symlink_targets:
        if target and target.exists():
            try:
                target.relative_to(project_root)
                # Only show a few to avoid noise
            except ValueError:
                pass
        elif target and not target.exists():
            print(f"  ✗ {target} — MISSING (was target of {symlink_path.name})")
            all_ok = False

    # Show key files
    for name in ["RULES.md", "DEVELOPMENT.md"]:
        path = project_root / name
        if path.exists():
            print(f"  {name}  ✓ exists")
        else:
            print(f"  {name}  ✗ MISSING")
            all_ok = False

    dev_team = project_root / "docs" / "dev-team"
    if dev_team.exists():
        count = len(list(dev_team.glob("*.md")))
        print(f"  docs/dev-team/  ✓ {count} files intact")

    sprints_dir = project_root / "docs" / "dev-team" / "sprints"
    if sprints_dir.exists():
        print("  docs/dev-team/sprints/  ✓ exists (tracking data preserved)")

    if all_ok:
        print("  All project files intact.")

    # Summary
    print("\nSprint teardown complete.")
    print(f"  {sym_count} symlinks removed")
    print(f"  {gen_count} generated files removed")
    print(f"  {dir_count} empty directories removed")
    if unknown:
        print(f"  {len(unknown)} unknown files skipped")

    # Check for active loops
    active_loops = check_active_loops()
    print_loop_cleanup_hints(active_loops)

    print_github_cleanup_hints()


if __name__ == "__main__":
    main()
