# Deferred Item Re-evaluation — Pass 35

Re-evaluating 6 items deferred from pass 34. No code has changed since pass 34.

## Verdict: All remain LOW / deferred

| # | Finding | Re-evaluation | Verdict |
|---|---------|---------------|---------|
| 1 | TOML parser rejects hyphen-leading bare keys | Regex `^([a-zA-Z0-9_][a-zA-Z0-9_-]*)` blocks `-foo` style keys. Valid TOML but no project template uses them. No user-facing config uses them. Would need to change `[a-zA-Z0-9_]` to `[a-zA-Z0-9_-]` to fix. | DEFER — no trigger path |
| 2 | TOML parser accepts malformed quoted strings | `_parse_value` doesn't validate escape sequences in double-quoted strings beyond basic processing. Only affects hand-edited TOML with invalid escape chars like `\q`. | DEFER — no trigger path |
| 3 | kanban.py WIP lock API contract | `check_wip_limit()` returns error message but doesn't block. Callers must check. All CLI and script callers do check. No external API consumers. | DEFER — internal API |
| 4 | kanban.py case-sensitive persona comparison | `getattr(other, persona_field) == persona_name` at kanban.py:286. Persona names flow from team/INDEX.md through do_assign. No normalization path introduces case differences. | DEFER — consistent by construction |
| 5 | bootstrap_github.py milestone title length | GitHub API truncates at 255 chars. Milestone titles come from `### Milestone N: Title` headings in markdown, which are always short. | DEFER — theoretical |
| 6 | populate_issues.py ARG_MAX | Issue bodies from `format_issue_body()` go through `gh issue create --body`. Bodies are well under 1KB from markdown parsing. ARG_MAX is 256KB on macOS. | DEFER — 250x margin |

**Conclusion:** No severity changes. All 6 remain correctly deferred. Moving to code audit findings.
