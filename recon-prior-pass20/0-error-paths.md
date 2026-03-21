# Error Path Audit — 19 Production Files

Audited: all `try/except`, early-return guards (`if X is None: return`),
and `sys.exit()` calls in every production Python file.

Only HIGH and MEDIUM findings listed.

---

## scripts/validate_config.py

### try/except blocks

| Location | Handler | Tested | Severity | Notes |
|----------|---------|--------|----------|-------|
| L43-48 `parse_iso_date` | `except (ValueError, TypeError): return default` | YES (via update_burndown, sync_tracking roundtrips) | — | |
| L58-65 `gh()` | `except TimeoutExpired: raise RuntimeError` | YES (test_sprint_runtime) | — | |
| L88-91 `gh_json` | `except JSONDecodeError: pass` (falls through to incremental decoder) | NO | MEDIUM | Silent `pass` on malformed JSON — falls through to raw_decode which could raise unhandled `JSONDecodeError` if the data is truly garbage (not just concatenated arrays). The incremental decoder has no outer try/except. |
| L249-254 `_unescape_toml_string` | `except (ValueError, OverflowError): append raw` | NO | MEDIUM | Invalid `\uXXXX` / `\UXXXXXXXX` sequences silently produce raw text instead of raising. No test covers malformed unicode escapes. |
| L309-312 `_parse_value` int fallback | `except ValueError: pass` | YES (property tests) | — | |
| L457-460 `validate_project` | `except Exception as exc: errors.append(...)` | PARTIAL | MEDIUM | Catches bare `Exception` on TOML parse — could swallow unexpected errors (e.g., PermissionError reading the file). Only tested via `load_config` path, not the direct `validate_project` path with a corrupt file. |
| L637-640 `load_config` | `except Exception as exc: _parse_error = ...` | PARTIAL | MEDIUM | Same broad `Exception` catch as above. Tested that ConfigError is raised, but the catch breadth is not tested (e.g., PermissionError on project.toml). |
| L970-978 `list_milestone_issues` | `except RuntimeError: print warning, return []` | NO | HIGH | API failure silently returns empty list. Callers (sync_tracking, update_burndown) proceed with no issues — burndown shows 0 SP, sync shows "Everything in sync". No test covers this silent degradation path. |

### Early-return guards

| Location | Guard | Tested | Severity | Notes |
|----------|-------|--------|----------|-------|
| L682 `get_team_personas` | `if not index_path.is_file(): return []` | NO | MEDIUM | Caller gets empty persona list silently. No test covers missing INDEX.md via this function. |
| L708 `get_milestones` | `if not milestones_dir.is_dir(): return []` | NO | MEDIUM | Silent empty return. Callers (bootstrap, burndown) proceed with no milestones. |
| L741-747 `get_prd_dir` | `if not val: return None` / `if not p.is_dir(): return None` | NO | MEDIUM | None return when configured dir doesn't exist on disk. No test covers the "configured but missing" case. |
| L751-757 `get_test_plan_dir` | Same pattern | NO | MEDIUM | Same issue. |
| L761-767 `get_sagas_dir` | Same pattern | NO | MEDIUM | Same issue. |
| L771-777 `get_epics_dir` | Same pattern | NO | MEDIUM | Same issue. |
| L887-896 `detect_sprint` | Returns `None` if no status file or no match | YES | — | |
| L943-961 `find_milestone` | Returns `None` if API returns non-list or no match | PARTIAL | MEDIUM | The "non-list" guard (L953) is not directly tested. Only the "no match" path is tested. |

### sys.exit() calls

| Location | Exit code | Tested | Severity | Notes |
|----------|-----------|--------|----------|-------|
| L1007 | 0 (help) | NO | LOW | |
| L1015 | 1 (validation failure) | NO | MEDIUM | `main()` CLI entrypoint has no tests. |

---

## scripts/sprint_init.py

### try/except blocks

| Location | Handler | Tested | Severity | Notes |
|----------|---------|--------|----------|-------|
| L135-138 `_glob_md` | `except ValueError: continue` | NO | MEDIUM | `relative_to` failure silently skips files. No test triggers this. |
| L149-153 `_read_head` | `except OSError: return []` | NO | MEDIUM | Silent empty return on file read failure. All persona/backlog detection that depends on `_read_head` would silently miss files. No test covers this. |
| L164-170 `detect_repo` | `except (FileNotFoundError, TimeoutExpired): return Detection(None, ...)` | NO | MEDIUM | No test covers git not being available during scan. |
| L238-239 `_parse_workflow_runs` | `except OSError: pass` | NO | MEDIUM | Silent skip on workflow file read error. No test covers unreadable workflow file. |
| L279-283 `_parse_json_name` | `except (OSError, ValueError): return None` | NO | MEDIUM | Malformed package.json returns None silently. No test covers corrupt JSON. |
| L559-565 `_symlink` BH18-014 | `except ValueError: skipped.append(REJECTED)` | NO | HIGH | Path traversal rejection is defense-in-depth but completely untested. If the check has a bug, symlinks could escape the project root. |
| L617-624 `generate_project_toml` | `except (CalledProcessError, FileNotFoundError): _current_branch = "main"` | NO | MEDIUM | Silent fallback to "main" when git not available. Untested. |
| L691-694 `_infer_role` | `except OSError: return "Team Member"` | NO | MEDIUM | Silently returns generic role on file read error. No test. |

### Early-return guards

| Location | Guard | Tested | Severity | Notes |
|----------|-------|--------|----------|-------|
| L603 `generate_project_toml` | `if toml_path.is_file(): skipped, return` | NO | MEDIUM | Preservation of existing project.toml is untested. |

### sys.exit() calls

| Location | Exit code | Tested | Severity | Notes |
|----------|-----------|--------|----------|-------|
| L963 | 0 (help) | NO | LOW | |
| L969 | 1 (not a directory) | NO | MEDIUM | CLI error path untested. |
| L992 | 1 (self-validation failed) | NO | MEDIUM | Post-generation validation failure path untested. |

---

## scripts/sprint_teardown.py

### try/except blocks

| Location | Handler | Tested | Severity | Notes |
|----------|---------|--------|----------|-------|
| L52-56 `classify_entries` | `except (JSONDecodeError, OSError): pass` | NO | MEDIUM | Corrupt manifest file silently falls back to name-based classification. No test covers corrupt `.sprint-init-manifest.json`. |
| L107-113 `resolve_symlink_target` | `except (OSError, ValueError): return None` | YES | — | |
| L222-223 `remove_symlinks` | `except OSError as e: print error` | NO | MEDIUM | Symlink removal failure prints error but continues. No test covers permission-denied on symlink removal. |
| L256-261 `remove_generated` | `except OSError as e: print error` | NO | MEDIUM | Same pattern — untested failure case. |
| L270-280 `remove_empty_dirs` | `except OSError as e: errno check` | NO | MEDIUM | BH-012 errno handling is untested. |
| L293-306 `check_active_loops` | `except (FileNotFoundError, TimeoutExpired, OSError): pass` | NO | MEDIUM | Silent skip when crontab not available. Always mocked out in tests. |
| L401-417 `main` git diff check | `except (TimeoutExpired, OSError): pass` | NO | MEDIUM | Silent skip of uncommitted-changes warning when git unavailable. No test covers this. |

### Early-return guards

| Location | Guard | Tested | Severity | Notes |
|----------|-------|--------|----------|-------|
| L243-244 `remove_generated` | `except EOFError: break` | NO | MEDIUM | Non-interactive mode (piped stdin) stops prompting and skips remaining files. Could leave generated files behind. Untested. |

### sys.exit() calls

| Location | Exit code | Tested | Severity | Notes |
|----------|-----------|--------|----------|-------|
| L352 | 0 (help) | NO | LOW | |
| L370 | 0 (no config dir) | NO | LOW | |
| L374 | 1 (not a directory) | NO | MEDIUM | Untested. |
| L388 | 0 (empty dir removed) | NO | MEDIUM | Untested. |
| L398 | 0 (dry run) | PARTIAL | — | |
| L415 | 1 (uncommitted changes, no --force) | NO | MEDIUM | Untested. |

---

## scripts/commit.py

### sys.exit() calls

| Location | Exit code | Tested | Severity | Notes |
|----------|-----------|--------|----------|-------|
| L128 | 1 (invalid message) | YES | — | |
| L137 | 1 (atomicity failure) | YES | — | |
| L146 | 0 (dry run) | YES | — | |
| L151 | 1 (commit failed) | NO | MEDIUM | `run_commit` failure at the CLI level is untested (function tested, CLI path not). |

---

## scripts/sprint_analytics.py

### try/except blocks

| Location | Handler | Tested | Severity | Notes |
|----------|---------|--------|----------|-------|
| L202-205 `main` | `except ConfigError: sys.exit(1)` | YES | — | |

### Early-return guards / sys.exit()

| Location | Guard | Tested | Severity | Notes |
|----------|-------|--------|----------|-------|
| L222-228 | `if sprint_num is None: sys.exit(2)` | YES (mocked) | — | |
| L230-232 | `if not repo: sys.exit(1)` | NO | MEDIUM | Empty repo string path untested. |
| L236-238 | `if ms is None: sys.exit(1)` | YES | — | |

---

## scripts/sync_backlog.py

### try/except blocks

| Location | Handler | Tested | Severity | Notes |
|----------|---------|--------|----------|-------|
| L27-32 module-level | `except ImportError: bootstrap_github = None` | YES (test_bugfix_regression) | — | |
| L71-82 `load_state` | `except (JSONDecodeError, OSError): return _default_state()` | PARTIAL | MEDIUM | JSONDecodeError tested indirectly. OSError (permission denied on state file) untested. |
| L224-231 `main` do_sync failure | `except Exception as exc: print error, save_state, return "error"` | YES (BH-021 test) | — | But note: catches bare `Exception`. |
| L246-252 `__main__` | `except (ConfigError, RuntimeError, ImportError) as exc: sys.exit(1)` | NO | MEDIUM | CLI error handling untested. |

---

## scripts/validate_anchors.py

### sys.exit() calls

| Location | Exit code | Tested | Severity | Notes |
|----------|-----------|--------|----------|-------|
| L332 | 1 (broken references) | YES | — | |

No untested error paths of significance.

---

## scripts/team_voices.py

### try/except blocks

| Location | Handler | Tested | Severity | Notes |
|----------|---------|--------|----------|-------|
| L91-94 `main` | `except ConfigError: sys.exit(1)` | YES | — | |

No untested error paths of significance.

---

## scripts/test_coverage.py

### Early-return guards

| Location | Guard | Tested | Severity | Notes |
|----------|-------|--------|----------|-------|
| L65 `detect_test_functions` | `if not pattern: return []` | NO | MEDIUM | Unknown language silently returns empty. No test for unsupported language. |
| L74 `scan_project_tests` | `if not root.is_dir(): return []` | NO | MEDIUM | Non-existent project root silently returns empty. |
| L87-88 `scan_project_tests` | `except ValueError: parts = test_file.parts` | NO | MEDIUM | `relative_to` failure untested. |

### sys.exit() calls

| Location | Exit code | Tested | Severity | Notes |
|----------|-----------|--------|----------|-------|
| L190 | 1 (ConfigError) | YES | — | |
| L196 | 1 (no test_plan_dir) | NO | MEDIUM | CLI path untested. |

---

## scripts/traceability.py

No untested error paths of significance. All early returns are for absent directories (returns empty dicts).

---

## scripts/manage_epics.py

### sys.exit() calls

| Location | Exit code | Tested | Severity | Notes |
|----------|-----------|--------|----------|-------|
| L367 | 1 (too few args) | YES | — | |
| L381 | 1 (remove: missing arg) | NO | MEDIUM | Untested CLI error path. |
| L389 | 1 (reorder: missing arg) | NO | MEDIUM | Untested CLI error path. |
| L397 | 1 (renumber: missing arg) | NO | MEDIUM | Untested CLI error path. |
| L405 | 1 (unknown command) | NO | MEDIUM | Untested CLI error path. |

### Error handling gaps

| Location | Issue | Tested | Severity | Notes |
|----------|-------|--------|----------|-------|
| L373-374 `main` add | `json.loads(story_json)` | NO | HIGH | If user passes malformed JSON, unhandled `JSONDecodeError` crashes with stack trace. No validation or try/except around user input. |
| L390 `main` reorder | `sys.argv[3].split(",")` | NO | MEDIUM | No validation that IDs are valid format. |

---

## scripts/manage_sagas.py

### Error handling gaps

| Location | Issue | Tested | Severity | Notes |
|----------|-------|--------|----------|-------|
| L265-266 `main` update-allocation | `json.loads(alloc_json)` | NO | HIGH | Malformed JSON from CLI crashes with unhandled `JSONDecodeError`. |
| L280-281 `main` update-voices | `json.loads(voices_json)` | NO | HIGH | Same issue. |

### Early-return guards

| Location | Guard | Tested | Severity | Notes |
|----------|-------|--------|----------|-------|
| L152-153 `update_sprint_allocation` | `if "Sprint Allocation" not in section_ranges: return` | NO | MEDIUM | Silently does nothing if section missing. No test. |
| L189 `update_epic_index` | `if "Epic Index" not in section_ranges: return` | NO | MEDIUM | Same. |
| L238-239 `update_team_voices` | `if "Team Voices" not in section_ranges: return` | NO | MEDIUM | Same. |

---

## skills/sprint-setup/scripts/bootstrap_github.py

### try/except blocks

| Location | Handler | Tested | Severity | Notes |
|----------|---------|--------|----------|-------|
| L47-52 `create_label` | `except RuntimeError: print warning` | YES (via FakeGitHub) | — | |
| L176-181 `create_saga_labels` | `except (OSError, IndexError): saga_name fallback` | NO | MEDIUM | Empty saga file or read error falls back to filename-based name. Untested. |
| L281-291 `create_milestones_on_github` | `except RuntimeError: check "already_exists"` | YES | — | |

### sys.exit() calls

| Location | Exit code | Tested | Severity | Notes |
|----------|-----------|--------|----------|-------|
| L25 | 1 (gh not installed) | NO | MEDIUM | `check_prerequisites` never tested directly (always mocked). |
| L31 | 1 (gh not authenticated) | NO | MEDIUM | Same. |
| L39 | 1 (no git remote) | NO | MEDIUM | Same. |

---

## skills/sprint-setup/scripts/populate_issues.py

### try/except blocks

| Location | Handler | Tested | Severity | Notes |
|----------|---------|--------|----------|-------|
| L77-81 `_safe_compile_pattern` | `except re.error: print warning, return False` | YES | — | |
| L112-119 `_build_row_regex` | `except re.error: return _DEFAULT_ROW_RE` | NO | MEDIUM | Second compile failure (after safety check passed) untested. Edge case. |
| L207-209 `_build_detail_block_re` | `except re.error: pass` | NO | MEDIUM | Same pattern. |
| L332-339 `get_existing_issues` | `except RuntimeError: print, raise` | YES (tested in main path) | — | |
| L353-361 `get_milestone_numbers` | `except (RuntimeError, KeyError): print, raise` | YES | — | |
| L465-471 `create_issue` | `except RuntimeError: print, return False` | YES | — | |

### sys.exit() calls

| Location | Exit code | Tested | Severity | Notes |
|----------|-----------|--------|----------|-------|
| L41-42 `check_prerequisites` | 1 (gh not auth'd) | NO | MEDIUM | Always mocked in tests. |
| L490 | 1 (no milestone files) | NO | MEDIUM | CLI path untested. |
| L497 | 1 (no stories) | NO | MEDIUM | CLI path untested. |
| L510 | 1 (can't fetch existing issues) | NO | MEDIUM | CLI path untested. |
| L517 | 1 (can't fetch milestones) | NO | MEDIUM | CLI path untested. |

---

## skills/sprint-setup/scripts/setup_ci.py

### sys.exit() calls

| Location | Exit code | Tested | Severity | Notes |
|----------|-----------|--------|----------|-------|
| L347 | 1 (not in git repo) | NO | MEDIUM | `check_prerequisites` untested. |

No other untested error paths.

---

## skills/sprint-run/scripts/sync_tracking.py

### try/except blocks

| Location | Handler | Tested | Severity | Notes |
|----------|---------|--------|----------|-------|
| L38-49 `_fetch_all_prs` | `except RuntimeError: return []` | NO | HIGH | API failure silently returns empty PR list. All stories lose PR linkage — tracking files written with empty `pr_number`. No test covers this degradation. |
| L61-102 `get_linked_pr` | `except RuntimeError: print warning` (timeline API) | YES (warning printed) | — | |

### Early-return guards

| Location | Guard | Tested | Severity | Notes |
|----------|-------|--------|----------|-------|
| L343-345 `main` | `if not mt: sys.exit(1)` | YES (via mocked find_milestone returning None) | — | |

### sys.exit() calls

| Location | Exit code | Tested | Severity | Notes |
|----------|-----------|--------|----------|-------|
| L329 | 2 (wrong args) | NO | MEDIUM | CLI usage error path untested. |

---

## skills/sprint-run/scripts/update_burndown.py

### Early-return guards

| Location | Guard | Tested | Severity | Notes |
|----------|-------|--------|----------|-------|
| L82-83 `update_sprint_status` | `if not status_file.exists(): return` | YES (implicitly) | — | |

### sys.exit() calls

| Location | Exit code | Tested | Severity | Notes |
|----------|-----------|--------|----------|-------|
| L189 | 2 (wrong args) | NO | MEDIUM | CLI path untested. |
| L196 | 1 (ConfigError) | YES | — | |
| L207 | 1 (no milestone) | NO | MEDIUM | CLI path untested. |
| L215 | 1 (no issues) | NO | MEDIUM | CLI path untested. |

---

## skills/sprint-monitor/scripts/check_status.py

### try/except blocks

| Location | Handler | Tested | Severity | Notes |
|----------|---------|--------|----------|-------|
| L26-30 module-level | `except ImportError: sync_backlog_main = None` | YES | — | |
| L68-77 `check_ci` | `except RuntimeError: actions.append(...)` | NO | MEDIUM | Failed log fetch adds action without actual error detail. Not directly tested. |
| L196-207 `check_milestone` SP calc | `except RuntimeError: pass` | NO | HIGH | SP calculation failure silently omits SP from report. The milestone progress line shows no SP data, which could be mistaken for "0 SP planned". No test covers API failure during SP fetch. |
| L263-264 `check_branch_divergence` | `except RuntimeError: report.append(skipped)` | YES | — | |
| L305-306 `check_direct_pushes` | `except RuntimeError: report.append(skipped)` | YES | — | |
| L366-371 `main` sync_backlog call | `except Exception: report, traceback` | NO | HIGH | Catches bare `Exception` from sync_backlog. Could swallow SystemExit, KeyboardInterrupt. The traceback is printed to stderr but the script continues — if sync_backlog corrupts state, check_status proceeds with stale data. No test covers sync failure during monitoring. |
| L381-382 `main` PR fetch | `except RuntimeError: pass` | NO | MEDIUM | Silent empty branch list on API failure. Drift detection skipped entirely without reporting. |
| L389-395 `main` milestone fetch | `except RuntimeError: pass` | NO | MEDIUM | Milestone fetch failure silently falls back to 14-day window. No test. |
| L410-415 `main` check loop | `except RuntimeError: report.append(...)` | YES | — | |
| L425-431 `main` write_log | `except OSError: print warning` | NO | MEDIUM | Log write failure only warns. Untested. |

### sys.exit() calls

| Location | Exit code | Tested | Severity | Notes |
|----------|-----------|--------|----------|-------|
| L348 | 2 (bad args) | NO | MEDIUM | CLI path untested. |
| L358 | 2 (can't detect sprint) | NO | MEDIUM | CLI path untested. |
| L433 | 1 if actions, 0 otherwise | YES | — | |

---

## skills/sprint-release/scripts/release_gate.py

### try/except blocks

| Location | Handler | Tested | Severity | Notes |
|----------|---------|--------|----------|-------|
| L215-220 `gate_tests` | `except TimeoutExpired: return False, "timed out"` | YES | — | |
| L233-238 `gate_build` | `except TimeoutExpired: return False, "timed out"` | YES | — | |
| L453-460 `do_release` | `except FileNotFoundError: return False` (git missing) | YES | — | |
| L641-647 `do_release` | `except RuntimeError: _rollback_tag, _rollback_commit, return False` (GH release fail) | YES | — | |

### Error handling gaps

| Location | Issue | Tested | Severity | Notes |
|----------|-------|--------|----------|-------|
| L500-537 `_rollback_commit` | Revert or reset failure prints warning but doesn't raise | PARTIAL | MEDIUM | Rollback paths are exercised in some tests, but the specific "revert pushed + push revert fails" path (L521-526) is untested. User could be left with a dangling version bump on remote. |
| L584-598 `_rollback_tag` | Tag deletion failure prints warning | NO | MEDIUM | `_rollback_tag` is called but the inner failure paths (local tag delete fail, remote tag delete fail) are not tested. |

---

## Summary

### Counts by severity

| Severity | Count |
|----------|-------|
| HIGH | 7 |
| MEDIUM | 65 |

### HIGH findings (untested + data loss / silent failure risk)

1. **validate_config.py:970** `list_milestone_issues` — API failure returns `[]` silently. Burndown shows 0 SP; sync says "all synced".
2. **sync_tracking.py:38** `_fetch_all_prs` — API failure returns `[]` silently. All PR linkages lost in tracking files.
3. **check_status.py:196** `check_milestone` SP calc — API failure silently omits SP data from progress report.
4. **check_status.py:366** `main` sync_backlog — catches bare `Exception`. Could swallow KeyboardInterrupt; continues with stale data.
5. **sprint_init.py:559** `_symlink` BH18-014 — path traversal defense is completely untested.
6. **manage_epics.py:373** `main` add command — unhandled `JSONDecodeError` on malformed user input crashes with stack trace.
7. **manage_sagas.py:265,280** `main` update-allocation/update-voices — same unhandled `JSONDecodeError` issue.

### Pattern observations

- **Broad except clauses**: `except Exception` appears in 4 places (validate_config L459/639, sync_backlog L226, check_status L369). The sync_backlog one is the most concerning because it runs in a loop context.
- **Silent empty returns on API failure**: `list_milestone_issues`, `_fetch_all_prs`, and several `gh_json` callers return `[]` on failure. Downstream code treats empty lists as "nothing to do" rather than "something went wrong".
- **CLI main() functions largely untested**: Most `main()` functions have sys.exit paths that are never directly tested (bootstrap_github, populate_issues, setup_ci, sync_tracking, update_burndown, check_status, sprint_analytics). They are integration-level but the error branches are skipped.
- **check_prerequisites() never tested**: All three implementations (bootstrap_github, populate_issues, setup_ci) are always mocked in tests. Actual gh/git detection failures are untested.
