"""Shared MockProject for test fixtures.

Creates a minimal mock Rust project in a temp directory.  Used by
test_lifecycle.py (with real git) and test_verify_fixes.py (with fake git).

Extracted from duplicate MockProject classes (BH-P11-062).
"""
from __future__ import annotations

import subprocess
import textwrap
from pathlib import Path


class MockProject:
    """Create a minimal mock Rust project in a temp directory.

    Parameters
    ----------
    root : Path
        Directory to create the project in.
    real_git : bool
        If True, run ``git init`` and create a real git repository with an
        initial commit.  If False, create a fake ``.git/config`` that
        satisfies repo-detection heuristics without needing git.
    extra_personas : bool
        If True, create a third persona (Carol, QA Lead) with the inline
        ``## Role: QA Lead`` format.  Useful for testing role-parsing
        variants.
    """

    def __init__(self, root: Path, *, real_git: bool = False,
                 extra_personas: bool = False):
        self.root = root
        self._real_git = real_git
        self._extra_personas = extra_personas

    def create(self) -> None:
        # Cargo.toml (language detection)
        (self.root / "Cargo.toml").write_text(textwrap.dedent("""\
            [package]
            name = "test-project"
            version = "0.1.0"
            edition = "2021"
        """))

        if self._real_git:
            subprocess.run(
                ["git", "init", "-b", "main"], cwd=str(self.root),
                capture_output=True, text=True,
            )
            subprocess.run(
                ["git", "remote", "add", "origin",
                 "https://github.com/testowner/testrepo.git"],
                cwd=str(self.root), capture_output=True, text=True,
            )
            subprocess.run(
                ["git", "add", "."], cwd=str(self.root),
                capture_output=True, text=True,
            )
            subprocess.run(
                ["git", "-c", "user.name=Test", "-c", "user.email=test@test.com",
                 "commit", "-m", "feat: initial project setup"],
                cwd=str(self.root), capture_output=True, text=True,
            )
        else:
            # Fake .git/config for repo detection without real git
            (self.root / ".git").mkdir()
            (self.root / ".git" / "config").write_text(textwrap.dedent("""\
                [remote "origin"]
                    url = https://github.com/testowner/testrepo.git
                    fetch = +refs/heads/*:refs/remotes/origin/*
            """))

        # Persona files
        docs = self.root / "docs" / "dev-team"
        docs.mkdir(parents=True)
        for name, role in [("alice", "Senior Engineer"),
                           ("bob", "Systems Architect")]:
            (docs / f"{name}.md").write_text(textwrap.dedent(f"""\
                # {name.title()}

                ## Role
                {role}

                ## Voice
                Direct and technical.

                ## Domain
                Backend systems.

                ## Background
                10 years experience.

                ## Review Focus
                Performance and correctness.
            """))

        if self._extra_personas:
            # Carol uses inline role format: "## Role: QA Lead"
            (docs / "carol.md").write_text(textwrap.dedent("""\
                # Carol

                ## Role: QA Lead

                ## Voice
                Thorough and cautious.

                ## Domain
                Testing and validation.

                ## Background
                8 years in QA.

                ## Review Focus
                Test coverage and edge cases.
            """))

        # Backlog with milestone
        backlog = self.root / "docs" / "backlog"
        backlog.mkdir(parents=True)
        milestones = backlog / "milestones"
        milestones.mkdir()
        (milestones / "milestone-1.md").write_text(textwrap.dedent("""\
            # Sprint 1: Walking Skeleton

            ### Sprint 1: Foundation

            | US-0101 | Basic setup | S01 | 3 | P0 |
            | US-0102 | Core feature | S01 | 5 | P1 |
        """))

        # Rules and dev guide
        (self.root / "RULES.md").write_text("# Rules\nNo panics in production.\n")
        (self.root / "DEVELOPMENT.md").write_text("# Development\nUse TDD.\n")

    def add_and_commit(self, msg: str) -> None:
        """Stage all and commit in the temp repo.  Requires real_git=True."""
        subprocess.run(
            ["git", "add", "-A"], cwd=str(self.root),
            capture_output=True, text=True,
        )
        subprocess.run(
            ["git", "-c", "user.name=Test", "-c", "user.email=test@test.com",
             "commit", "-m", msg, "--allow-empty"],
            cwd=str(self.root), capture_output=True, text=True,
        )
