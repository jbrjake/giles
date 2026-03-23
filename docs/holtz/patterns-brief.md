# Holtz Pattern Brief

> Read this before starting any audit work. These patterns were discovered
> in prior audits of this project. Check for them in the code you're reviewing.

## PAT-001: Batch addition without full wiring (Run 1, 2026-03-23)
**What to look for:** New scripts or modules added to the project without updating all integration points (Makefile lint lists, namespace maps, cheatsheet indices, test coverage).
**Detection heuristic:** `find scripts/ hooks/ skills/*/scripts/ -name "*.py" ! -name "__init__.py" | wc -l` vs `grep -c "py_compile" Makefile` — if they differ, scripts are missing from lint.
**Example:** Run 1 found 6 scripts missing from NAMESPACE_MAP and Makefile lint. Run 5 found 5 hook scripts missing from Makefile lint after they were moved to the plugin root.

## PAT-002: Inconsistent security hardening across parallel hooks (Run 1, 2026-03-23)
**What to look for:** When one hook or module receives a security fix (compound command splitting, crash safety, input validation), sibling hooks with the same attack surface may not have the fix applied.
**Detection heuristic:** Identify all hooks/modules that share a pattern (e.g., command parsing). If one has a defense that another lacks, flag it.
**Example:** Run 1 found commit_gate missing compound command splitting and crash-before-block safety that review_gate already had.

## PAT-003: Triple TOML parser divergence (Run 1, 2026-03-23, RESOLVED Run 2)
**What to look for:** Multiple independent parsers for the same format (TOML, YAML, markdown tables) with different edge-case handling.
**Detection heuristic:** `grep -rnP "(def|function)\s+(parse|extract|read|load)\w*" --include="*.py" .` — group by what they parse. If two functions parse the same format differently, flag it.
**Example:** Three TOML parsers (validate_config, session_context, verify_agent_output) handled quoting, escapes, and unquoted values differently. Consolidated into shared _common.read_toml_key in run 2.

## PAT-004: Dual parser divergence hooks vs scripts (Run 3, 2026-03-23, RESOLVED Run 3)
**What to look for:** After consolidating parsers within a subsystem (PAT-003), check for divergence between subsystems — the hooks' lightweight parser may lag behind the scripts' full parser.
**Detection heuristic:** Compare escape sequence handling, comment stripping, and edge case behavior between the two parsers. Run parity tests.
**Example:** _common.py was missing 4 TOML escape sequences (\b, \f, \uXXXX, \UXXXXXXXX) that validate_config had. Aligned in run 3.
