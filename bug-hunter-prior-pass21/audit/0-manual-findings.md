# Pass 15: Manual Findings

## F-001: CRITICAL — BH-014 regression: validate_project skips section/key checks when _config provided

**File:** scripts/validate_config.py:439-466
**Problem:** The BH-014 fix changed `if toml_path.is_file():` to `if _config is None and toml_path.is_file():`.
The "Required sections" and "Required keys" loops (lines 445-466) are INSIDE this if block.
When `load_config()` calls `validate_project(_config=config)`, these checks are bypassed.
A project.toml missing `[project]` or `[ci]` sections passes `load_config()` silently.

**Evidence:** The sections/keys checks at lines 445-466 are indented inside the `if _config is None` block.
Before BH-014, they were inside `if toml_path.is_file():` which was always True when the file existed.

**Impact:** load_config() returns invalid config dicts that downstream code assumes are valid.

## F-002: MEDIUM — _fm_val in update_burndown.py doesn't unescape backslashes (BH-007 incomplete)

**File:** skills/sprint-run/scripts/update_burndown.py:151
**Problem:** `_fm_val` unquotes with `.replace('\\"', '"')` but doesn't do `.replace('\\\\', '\\')`.
After BH-007, `_yaml_safe` now escapes backslashes, so `_fm_val` would read them back wrong.
sync_tracking.read_tf was updated (line 167) but update_burndown._fm_val was not.

**Impact:** LOW in practice — _fm_val reads story, implementer, pr_number (unlikely to have backslashes).
But it's inconsistent with read_tf and would break if any of those fields contained backslashes.
