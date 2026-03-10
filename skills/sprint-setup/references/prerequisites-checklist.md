# Prerequisites Checklist

Verify every item before continuing. If any check fails, show the fix and stop.
Do not proceed with partial setup — a half-bootstrapped repo is harder to fix than a fresh start.

## 1. GitHub CLI (`gh`)

```bash
gh --version
```

If missing:
- **macOS:** `brew install gh`
- **Linux (Debian/Ubuntu):**
  ```bash
  curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg \
    | sudo dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" \
    | sudo tee /etc/apt/sources.list.d/github-cli.list > /dev/null
  sudo apt update && sudo apt install gh
  ```
- **Linux (Fedora):** `sudo dnf install gh`

The `gh` CLI is how every subsequent step talks to GitHub. Without it, nothing else works.

## 2. GitHub Authentication

```bash
gh auth status
```

If not authenticated:
```bash
gh auth login
```

Follow the interactive prompts. Choose HTTPS and authenticate via browser. The
bootstrap scripts create labels, milestones, issues, and a project board — all of
which require authenticated API access.

## 3. Superpowers Plugin

```bash
find ~/.claude/plugins -type d -name "superpowers" 2>/dev/null | head -1 | grep -q . && echo "OK" || echo "MISSING"
```

If missing:
```
claude plugin add anthropic/superpowers
```

Superpowers provides TDD, code review, verification, and other process skills that
the sprint process orchestrates. The `sprint-run` skill delegates implementation
work to superpowers agents, so it needs to be present before you start sprinting.

## 4. Git Remote

```bash
git remote -v
```

Verify a GitHub remote exists (e.g., `origin` pointing to `github.com/<org>/<project>`). If not:
- **Existing repo:** `git remote add origin https://github.com/<org>/<project>.git`
- **New repo:** `gh repo create <org>/<project> --private --source=. --remote=origin`

The bootstrap scripts use `gh` commands that infer the repo from the git remote.
Without a remote, label/issue creation has no target.

## 5. Language Toolchain

Read `project.toml` `[project]` `language` for toolchain requirements:
- **Rust:** `rustup --version && cargo --version`
- **Python:** `python3 --version` (must meet minimum version in config)
- **Node.js:** `node --version && npm --version`

If the toolchain is missing, follow the installation instructions for the detected
language. The CI workflow this skill generates runs language-specific checks, so the
toolchain needs to be present for local validation.

## 6. Python venv

The sprint process scripts require Python 3.10+:

```bash
python3 --version   # must be 3.10+
python3 -m venv .venv
source .venv/bin/activate
```

If Python 3.10+ is not available:
- **macOS:** `brew install python@3.12`
- **Linux:** `sudo apt install python3.12 python3.12-venv`

Always activate the venv before running any sprint scripts.

## Summary

Print this checklist and confirm all items pass before proceeding:

```
[x] 1. gh CLI installed
[x] 2. gh authenticated
[x] 3. superpowers plugin installed
[x] 4. Git remote configured
[x] 5. Language toolchain installed (per project.toml)
[x] 6. Python venv created and activated
[x] 7. sprint-config/ validated (Phase 0)
```

If any item shows `[ ]`, fix it and re-run the check. Do not continue.
