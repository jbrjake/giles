#!/usr/bin/env python3
"""Generate GitHub Actions CI workflow from project config.

Config-driven: reads language, CI commands, and build command from
project.toml via validate_config.load_config(). Supports Rust, Python,
Node.js, and Go out of the box. No hardcoded project-specific values.
"""

import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

# -- Import shared config ----------------------------------------------------
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent / "scripts"))
from validate_config import load_config, get_ci_commands


# -- Language-specific CI templates ------------------------------------------

def _rust_setup_steps() -> str:
    """Rust toolchain setup steps."""
    return """\
      - uses: dtolnay/rust-toolchain@stable
        with:
          components: rustfmt, clippy
      - uses: Swatinem/rust-cache@v2"""


def _python_setup_steps(version: str = "3.12") -> str:
    """Python setup steps."""
    return f"""\
      - uses: actions/setup-python@v6
        with:
          python-version: "{version}"
      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt || true"""


def _node_setup_steps(version: str = "22") -> str:
    """Node.js setup steps."""
    return f"""\
      - uses: actions/setup-node@v6
        with:
          node-version: "{version}"
          cache: npm
      - run: npm ci"""


def _go_setup_steps(version: str = "1.22") -> str:
    """Go setup steps."""
    return (
        "      - uses: actions/setup-go@v6\n"
        "        with:\n"
        f'          go-version: "{version}"'
    )


_SETUP_REGISTRY: dict[str, Callable] = {
    "rust": _rust_setup_steps,
    "python": _python_setup_steps,
    "node": _node_setup_steps,
    "nodejs": _node_setup_steps,
    "node.js": _node_setup_steps,
    "javascript": _node_setup_steps,
    "typescript": _node_setup_steps,
    "go": _go_setup_steps,
    "golang": _go_setup_steps,
}

# -- Environment variables by language --------------------------------------

_ENV_BLOCKS: dict[str, str] = {
    "rust": """\
env:
  CARGO_TERM_COLOR: always
  RUSTFLAGS: "-D warnings"
""",
    "go": """\
env:
  CGO_ENABLED: "0"
""",
}


def _generate_check_job(
    name: str, command: str, setup: str, needs: list[str] | None = None
) -> str:
    """Generate a single CI job that runs one check command."""
    slug = name.lower().replace(" ", "-").replace("/", "-")
    needs_line = ""
    if needs:
        needs_list = ", ".join(needs)
        needs_line = f"\n    needs: [{needs_list}]"

    return f"""\
  {slug}:
    name: {name}
    runs-on: ubuntu-latest{needs_line}
    steps:
      - uses: actions/checkout@v6
{setup}
      - name: {name}
        run: {command}
"""


def _generate_test_job(
    command: str, setup: str, multi_os: bool = True
) -> str:
    """Generate a test job, optionally with OS matrix."""
    if multi_os:
        return f"""\
  test:
    name: Test
    strategy:
      matrix:
        os: [ubuntu-latest, macos-latest]
    runs-on: ${{{{ matrix.os }}}}
    steps:
      - uses: actions/checkout@v6
{setup}
      - name: Test
        run: {command}
"""
    return f"""\
  test:
    name: Test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v6
{setup}
      - name: Test
        run: {command}
"""


def _generate_build_job(
    command: str, setup: str, needs: list[str] | None = None
) -> str:
    """Generate a build job."""
    needs_line = ""
    if needs:
        needs_list = ", ".join(needs)
        needs_line = f"\n    needs: [{needs_list}]"

    return f"""\
  build:
    name: Build
    runs-on: ubuntu-latest{needs_line}
    steps:
      - uses: actions/checkout@v6
{setup}
      - name: Build
        run: {command}
"""


_LANG_EXTENSIONS: dict[str, list[str]] = {
    "rust": [".md", ".rs"],
    "python": [".md", ".py"],
    "node": [".md", ".ts", ".tsx", ".js"],
    "nodejs": [".md", ".ts", ".tsx", ".js"],
    "node.js": [".md", ".ts", ".tsx", ".js"],
    "javascript": [".md", ".ts", ".tsx", ".js"],
    "typescript": [".md", ".ts", ".tsx", ".js"],
    "go": [".md", ".go"],
    "golang": [".md", ".go"],
}


def _docs_lint_job(language: str = "") -> str:
    """Standard doc-size-limit job with language-appropriate extensions."""
    extensions = _LANG_EXTENSIONS.get(language.lower(), [".md"])
    find_args = " -o ".join(f"-name '*{ext}'" for ext in extensions)
    ext_display = " and ".join(extensions)
    return f"""\
  docs-lint:
    name: Doc Size Limits
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v6
      - name: Check {ext_display} files under 750 lines
        run: |
          FAILED=0
          while IFS= read -r -d '' file; do
            LINES=$(wc -l < "$file")
            if [ "$LINES" -gt 750 ]; then
              echo "FAIL: $file has $LINES lines (limit: 750)"
              FAILED=1
            fi
          done < <(find . -type f \\( {find_args} \\) -not -path './.git/*' -print0)
          if [ "$FAILED" -eq 1 ]; then
            echo "One or more files exceed the 750-line hard limit."
            exit 1
          fi
          echo "PASS: All {ext_display} files within 750-line limit."
"""


def generate_ci_yaml(config: dict) -> str:
    """Generate a complete CI workflow YAML from config."""
    language = config.get("project", {}).get("language", "").lower()
    check_commands = get_ci_commands(config)
    build_command = config.get("ci", {}).get("build_command", "")

    # Determine language setup
    setup_fn = _SETUP_REGISTRY.get(language)
    if setup_fn:
        setup = setup_fn()
    else:
        setup = f"      # TODO: Add setup steps for {language}"

    base_branch = config.get("project", {}).get("base_branch", "main")

    # Header
    lines = [
        "name: CI",
        "",
        "on:",
        "  push:",
        f"    branches: [{base_branch}]",
        "  pull_request:",
        f"    branches: [{base_branch}]",
        "",
        "permissions:",
        "  contents: read",
        "",
    ]

    # Environment variables
    env_block = _ENV_BLOCKS.get(language, "")
    if env_block:
        lines.append(env_block)

    lines.append("jobs:")

    # Identify test command early so we can skip it from check jobs
    test_cmd = _find_test_command(check_commands)

    # Check jobs (linting, formatting, etc.) — skip test commands
    # since they get a dedicated cross-OS matrix job below
    job_names: list[str] = []
    seen_slugs: set[str] = set()
    for i, cmd in enumerate(check_commands):
        if test_cmd and cmd == test_cmd:
            continue
        name = _job_name_from_command(cmd, i)
        slug = name.lower().replace(" ", "-").replace("/", "-")
        # Deduplicate: append index if slug already used
        if slug in seen_slugs:
            name = f"{name} {i + 1}"
            slug = f"{slug}-{i + 1}"
        seen_slugs.add(slug)
        job = _generate_check_job(name, cmd, setup)
        lines.append(job)
        job_names.append(slug)

    # Test job -- cross-OS matrix is more valuable than a single-OS check
    if test_cmd:
        multi_os = language in ("rust", "go", "python")
        lines.append(_generate_test_job(test_cmd, setup, multi_os))
        job_names.append("test")

    # Build job
    if build_command:
        lines.append(_generate_build_job(build_command, setup, job_names[:]))

    # Docs lint (always included, language-aware extensions)
    lines.append(_docs_lint_job(language))

    return "\n".join(lines)


def _job_name_from_command(cmd: str, index: int) -> str:
    """Derive a human-readable job name from a CLI command."""
    cmd_lower = cmd.lower()
    if "fmt" in cmd_lower or "format" in cmd_lower or "black" in cmd_lower:
        return "Format"
    if "clippy" in cmd_lower:
        return "Clippy"
    if "pylint" in cmd_lower:
        return "Pylint"
    if "eslint" in cmd_lower:
        return "ESLint"
    if "lint" in cmd_lower:
        return "Lint"
    if "type" in cmd_lower or "mypy" in cmd_lower:
        return "Type Check"
    if "test" in cmd_lower or "pytest" in cmd_lower:
        return "Test"
    if "audit" in cmd_lower:
        return "Audit"
    if "vet" in cmd_lower:
        return "Vet"
    return f"Check {index + 1}"


def _find_test_command(commands: list[str]) -> str:
    """Find the test command among check commands, if any."""
    for cmd in commands:
        if "test" in cmd.lower() or "pytest" in cmd.lower():
            return cmd
    return ""


def check_prerequisites() -> None:
    """Verify we are in a git repo."""
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print("Error: Not in a git repository.")
        sys.exit(1)


def main() -> None:
    """Generate the CI workflow file from config."""
    if len(sys.argv) > 1 and sys.argv[1] in ("-h", "--help"):
        print(__doc__.strip())
        sys.exit(0)
    config = load_config()
    project_name = config.get("project", {}).get("name", "Project")
    language = config.get("project", {}).get("language", "unknown")

    print(f"=== {project_name} CI Setup ({language}) ===\n")
    check_prerequisites()

    # Determine workflow path relative to git root
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True, text=True,
    )
    repo_root = Path(result.stdout.strip()).resolve()
    workflow_path = repo_root / ".github" / "workflows" / "ci.yml"

    if workflow_path.exists():
        print(f"CI workflow already exists at: {workflow_path}")
        print("To regenerate, delete it first and re-run this script.")
        print("  rm", workflow_path)
        return

    # Generate and write
    ci_yaml = generate_ci_yaml(config)
    workflow_path.parent.mkdir(parents=True, exist_ok=True)
    workflow_path.write_text(ci_yaml)

    print(f"Created: {workflow_path}")
    print()

    # Summarize what was generated
    check_commands = get_ci_commands(config)
    build_command = config.get("ci", {}).get("build_command", "")
    print("Workflow includes:")
    for cmd in check_commands:
        print(f"  - {cmd}")
    if build_command:
        print(f"  - Build: {build_command}")
    extensions = _LANG_EXTENSIONS.get(language.lower(), [".md"])
    ext_display = " and ".join(extensions)
    print(f"  - Doc size limits ({ext_display} < 750 lines)")
    print()
    print("Next steps:")
    print(f"  git add {workflow_path.relative_to(repo_root)}")
    print("  git commit -m 'ci: add GitHub Actions workflow'")
    print("  git push")


if __name__ == "__main__":
    main()
