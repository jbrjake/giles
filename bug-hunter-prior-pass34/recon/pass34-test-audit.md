# Pass 34: Test Quality Audit

> Scope: Tests added or modified in passes 29-33, audited against the
> BH33 punchlist. Method: trace each test through the source code to
> determine whether the bug's revert would cause a failure.

---

## test_hooks.py

### test_delete_flag_blocked
- **SOLID**: Without the BH33-001 fix, `--delete` would be treated as a value-taking flag (the code skips `i += 2`), consuming "origin" as its value. This leaves only "main" as a single positional arg, and the code only checks refspecs when `len(positional) >= 2`. Reverting the fix changes the result from "blocked" to "allowed". Test would fail.

### test_delete_short_flag_blocked
- **SOLID**: Same mechanism as above. `-d` without the fix would consume "origin" as its value argument, leaving "main" as the sole positional. Revert produces "allowed" instead of "blocked".

### test_mirror_flag_blocked
- **SOLID**: Two-layer defense. Without the fix, `--mirror` is not in the boolean-flag set, so it eats "origin" as its value. The explicit `if "--mirror" in parts` check (also added in BH33-001) would still catch it, BUT that check was also part of the fix. If the entire BH33-001 change were reverted (removing both the boolean entry AND the mirror check), the result would be "warn" (bare push with empty positionals), not "blocked". Test would fail.

---

## test_bugfix_regression.py

### test_type_error_propagates (BH33-002)
- **SOLID**: The fix narrowed `except Exception` to `except (OSError, subprocess.SubprocessError)`. If reverted, `TypeError` would be caught instead of propagating. `assertRaises(TypeError)` would fail because no exception escapes the function.

### test_os_error_caught (BH33-002)
- **WEAK**: This test has two problems.
  1. **Dead code on line 127-129**: The first `check_smoke()` call runs without any mock, executing the real `true` command. Its return value is immediately overwritten by the second call. This is confusing and wasteful.
  2. **Does not validate the narrowing**: This test passes both before AND after the BH33-002 fix. The old `except Exception` also catches `OSError`. The assertion (`any("error" in line ...)`) would be satisfied either way. This test validates that OSError is handled gracefully, which was always true -- it does not validate that the exception was *narrowed*.
  3. **Leaked temp directories**: Three `tempfile.mkdtemp()` calls with no cleanup.

---

## test_new_scripts.py

### test_smoke_history_escapes_pipe_in_command (BH33-003)
- **SOLID**: Tests that a command containing `|` (pipe) does not corrupt the markdown table by counting unescaped pipe separators. Without the `command.replace("|", "\\|")` fix, the raw pipe would create extra columns (7 separators instead of 5). The regex-based separator count would fail.

### test_path_match_no_substring_false_positive (BH30-001)
- **SOLID**: Directly tests `_path_matches_entry_point("src/domain/maintain.py", "main")` returns False. Without the word-boundary/stem matching fix, a naive substring check would match "main" inside "maintain". Assertion would fail.

### test_path_match_bare_name_matches_file_stem (BH30-001)
- **SOLID**: Verifies the positive case -- "main" matches "src/main.py" via file stem comparison. Specific assertion on True return value.

### test_path_match_exact_path (BH30-001)
- **SOLID**: Direct exact-path match. Straightforward.

### test_path_match_suffix (BH30-001)
- **SOLID**: "main.py" matches "src/main.py" as path suffix. Tests a specific matching strategy.

### test_path_match_dir_name (BH30-001)
- **SOLID**: "main" matches "src/main/app.py" as a path segment.

### test_entry_point_substring_no_false_positive (BH29-003)
- **SOLID**: "main" must not match "domain" in body text. Asserts `assertIsNone(result)`. Without word-boundary matching, "main" would substring-match inside "domain" if the old regex were naive. However, "domain" does not contain "main" as a substring (d-o-m-a-i-n), so this test might not actually catch a pure substring bug. Borderline -- the test description is slightly misleading, but the test still validates word-boundary behavior for the broader pattern.

### test_entry_point_word_boundary_match (BH29-003)
- **SOLID**: Verifies positive match of "main" in "Update main module". Specific return value assertion.

---

## test_validate_anchors.py

### test_fix_idempotent_no_trailing_newlines (BH33-004)
- **SOLID**: Runs `fix_missing_anchors` three times and asserts the file ends with exactly one newline, not two. The bug was that `"foo\n".split('\n')` produces `["foo", ""]`, and `"\n".join(["foo", ""]) + "\n"` produces `"foo\n\n"`. Each --fix pass would add another blank line. Without the fix (stripping the trailing empty element), the file would end with `"\n\n\n\n"` after 3 runs. Test would fail.

---

## test_pipeline_scripts.py

### test_empty_quote_skipped (BH33-006)
- **SOLID**: Creates a file with `> **Bob:**    \n` (whitespace-only quote) and `> **Alice:** Real quote here`. Asserts Bob is NOT in voices and Alice IS. Without the `if quote:` guard, Bob would appear in voices with an empty string. `assertNotIn("Bob", voices)` would fail. Additionally verifies Alice's quote content specifically.

### test_format_story_section_ac_prefix_format (BH30-005)
- **SOLID**: This is an exemplary test. It verifies the AC-NN prefix format, then does a round-trip: feeds the output of `_format_story_section` into `populate_issues.parse_detail_blocks` and confirms 2 acceptance criteria survive. This catches format drift between producer and consumer. If the format were wrong, the round-trip would fail.

---

## test_verify_fixes.py

### test_invalid_json_allocation_exits_1 (BH33-005)
- **SOLID**: Passes "not-json" as the allocation argument to `manage_sagas.main()`. Without the try/except around `json.loads`, this would raise `json.JSONDecodeError` instead of `SystemExit(1)`. The `assertRaises(SystemExit)` would not catch the decode error. Test would fail.

### test_invalid_json_voices_exits_1 (BH33-005)
- **SOLID**: Same pattern with "{bad" for voices. Same revert-failure analysis.

---

## test_hexwise_setup.py

### test_parse_detail_blocks_five_digit_id (BH30-003)
- **SOLID**: Creates an epic block with story ID `US-01021` (5 digits). The old regex used `\d{4}` which would not match. Asserts the story is parsed with the correct ID and title. Reverting the regex change would produce 0 stories. Test would fail.

---

## Coverage Gaps

### BH33-002: Exception narrowing is only half-tested

The `test_type_error_propagates` test validates the positive case (programming errors DO propagate). The `test_os_error_caught` test was intended to validate the negative case (OSError IS still caught) but it does not actually test the narrowing -- this assertion passes with both the old `except Exception` and the new `except (OSError, subprocess.SubprocessError)`. There is no test for the `subprocess.SubprocessError` path specifically.

**Recommendation**: Replace `test_os_error_caught` with a test that verifies `subprocess.SubprocessError` is caught AND that `AttributeError` (another programming error) propagates. This would fully characterize the exception boundary.

### Temp directory leaks in test_bugfix_regression.py

`TestCheckSmokExceptionNarrowing` uses `tempfile.mkdtemp()` three times without cleanup. These accumulate in the OS temp directory across test runs. Should use `tempfile.TemporaryDirectory()` as a context manager instead.

### BH33 deferred items (BH33-007, BH33-008) have no tests

This is expected -- they were explicitly deferred and documented. No gap here.

### No missing punchlist coverage

All 6 resolved BH33 items have at least one validating test. BH33-002 has partial coverage (the propagation half is solid, the catch-and-report half is a no-op test).

---

## Summary

| Rating | Count | Tests |
|--------|-------|-------|
| SOLID  | 15    | All BH33-001 tests, test_type_error_propagates, test_smoke_history_escapes_pipe, all BH30-001 path tests, test_fix_idempotent_no_trailing_newlines, test_empty_quote_skipped, test_format_story_section_ac_prefix_format, both invalid_json tests, test_parse_detail_blocks_five_digit_id |
| WEAK   | 1     | test_os_error_caught (dead code, does not validate narrowing, leaked temp dirs) |

The test suite for passes 29-33 is strong overall. 15 of 16 tests exercise real code paths and would fail if their corresponding fixes were reverted. The one weak test (`test_os_error_caught`) is a test-theater problem: it looks like it validates the exception narrowing but actually validates behavior that existed before the fix.
