# Test Quality Verification (2026-03-21)

Verification of open findings from prior test-audit passes against current code.

---

## FINDING-2: TestCheckStatusImportGuard never makes sync_backlog unavailable

**Status: FIXED**

The class now has two tests (`tests/test_bugfix_regression.py` lines 62-101):

1. `test_import_guard_uses_import_error` -- checks the attribute exists and is callable when sync_backlog is available.
2. `test_import_guard_failure_path` (BH28) -- actually hides `sync_backlog` by setting `sys.modules["sync_backlog"] = None`, reloads `check_status`, and asserts `check_status.sync_backlog_main is None`. This properly tests the unavailable path.

---

## FINDING-5: _read_toml_key escaped-quote test asserts the bug, not the spec

**Status: STILL OPEN**

`tests/test_hooks.py` line 395-399:

```python
def test_read_toml_key_inline_comment_after_escaped_quote(self):
    toml = '[ci]\nsmoke_command = "echo \\"hello\\"" # a comment\n'
    result = _read_toml_key(toml, "ci", "smoke_command")
    self.assertEqual(result, 'echo \\"hello\\"')
```

The test asserts the returned value is `echo \"hello\"` (with literal backslashes retained). Per TOML spec, double-quoted strings process escape sequences, so `\"` inside a double-quoted string represents a literal `"`. The correct unescaped value should be `echo "hello"` (backslashes consumed). However, `_read_toml_key` (in `verify_agent_output.py` line 103-104) strips the outer quotes with `val[1:-1]` but does **not** process `\"` escapes, so it returns the raw inner content with backslashes intact. The test asserts the current (buggy) behavior rather than the TOML-spec-correct behavior.

---

## FINDING-9: Lock tests don't verify mutual exclusion

**Status: FIXED**

`tests/test_kanban.py` lines 309-337 now includes `test_concurrent_lock_serializes` (BH23-114). This test uses two threads: a `holder` thread that acquires the lock, signals an event, sleeps 0.2s, then appends "holder-done"; and a `waiter` thread that waits for the signal then tries to acquire the same lock, appending "waiter-done". The test asserts `results == ["holder-done", "waiter-done"]`, proving the lock serializes concurrent access (the waiter cannot proceed until the holder releases).

---

## FINDING-7: WIP warning test doesn't check warning text

**Status: STILL OPEN**

`tests/test_kanban.py` lines 1316-1330:

```python
def test_status_wip_limit_warning(self):
    """BH23-126: 4+ stories in DEV triggers WIP limit context."""
    ...
    output = do_status(sprints_dir, 1)
    self.assertIn("DEV", output)
    for i in range(4):
        self.assertIn(f"US-{i:04d}", output)
```

The test only checks that `do_status` output contains "DEV" and the story IDs. It does **not** check for any WIP warning text. Moreover, `do_status()` (kanban.py lines 642-674) does not produce any WIP warning -- it simply groups stories by state with a count header like `DEV (4):`. The test name and docstring claim it tests a WIP limit warning, but no such warning is generated or asserted. The test is effectively just a `do_status` formatting test.

---

## FINDING-8: do_update "no changes" test doesn't verify no write occurred

**Status: STILL OPEN**

`tests/test_kanban.py` lines 1221-1226:

```python
def test_update_no_changes(self):
    """When values match current state, no write is performed."""
    with tempfile.TemporaryDirectory() as td:
        tf = self._make_tf(td, pr_number="42")
        ok = do_update(tf, pr_number="42")
        self.assertTrue(ok)
```

The docstring says "no write is performed" but the test only checks the return value is `True`. It does not verify that no disk write occurred (e.g., by checking the file's mtime before and after, or by mocking `atomic_write_tf` and asserting it was not called). The `do_update` code (kanban.py lines 620-638) does skip the write when there are no changes, but the test doesn't prove it.

---

## FINDING-17: error message test doesn't check message content

**Status: FIXED**

`tests/test_kanban.py` lines 663-678:

```python
def test_dev_to_integration_error_mentions_review(self):
    """P0-KANBAN-1: dev->integration error mentions 'must pass through review'."""
    ...
    stderr_capture = io.StringIO()
    with _patch("sys.stderr", stderr_capture):
        with patch_gh("kanban.gh"):
            result = do_transition(tf, "integration")
    self.assertFalse(result)
    loaded = read_tf(tf.path)
    self.assertEqual(loaded.status, "dev")  # unchanged
    # The error message must mention 'review'
    self.assertIn("review", stderr_capture.getvalue().lower())
```

The test now captures stderr, verifies the transition fails, confirms status is unchanged, and asserts the error message contains "review". This fully addresses the finding.

---

## Summary

| # | Finding | Status |
|---|---------|--------|
| 2 | ImportGuard never makes sync_backlog unavailable | FIXED |
| 5 | _read_toml_key escaped-quote test asserts the bug | STILL OPEN |
| 7 | WIP warning test doesn't check warning text | STILL OPEN |
| 8 | do_update "no changes" test doesn't verify no write | STILL OPEN |
| 9 | Lock tests don't verify mutual exclusion | FIXED |
| 17 | Error message test doesn't check message content | FIXED |

**3 FIXED, 3 STILL OPEN**
