"""Property-based tests for regex/parsing functions.

Uses hypothesis to generate random inputs and verify invariants that must
always hold, regardless of input. These functions were identified as the
top 5 regex/parsing hotspots across 11 bug-hunter passes (22 regex bugs).

Targets:
  - extract_story_id  (validate_config.py)
  - extract_sp        (validate_config.py)
  - _yaml_safe        (sync_tracking.py)
  - _parse_team_index (validate_config.py) — via table-shaped text
  - parse_simple_toml (validate_config.py)
"""
from __future__ import annotations

import re
import tempfile
from pathlib import Path

import pytest
from hypothesis import given, assume, settings, example
from hypothesis import strategies as st

from validate_config import (
    extract_story_id,
    extract_sp,
    parse_simple_toml,
    _parse_team_index,
    frontmatter_value,
)
from sync_tracking import _yaml_safe


# ============================================================================
# 1. extract_story_id — must always return a non-empty string
# ============================================================================

class TestExtractStoryId:
    """Property tests for extract_story_id."""

    @given(st.text(min_size=0, max_size=200))
    @settings(max_examples=500)
    def test_never_returns_empty(self, title: str):
        """extract_story_id must return a non-empty string for any input."""
        result = extract_story_id(title)
        assert isinstance(result, str)
        assert len(result) > 0, f"Empty result for title={title!r}"

    @given(
        prefix=st.from_regex(r"[A-Z]{1,5}", fullmatch=True),
        num=st.integers(min_value=0, max_value=99999),
        suffix=st.text(max_size=100),
    )
    @settings(max_examples=300)
    def test_standard_ids_extracted(self, prefix: str, num: int, suffix: str):
        """Titles starting with PREFIX-NNN always extract that ID."""
        story_id = f"{prefix}-{num}"
        title = f"{story_id}: {suffix}"
        result = extract_story_id(title)
        assert result == story_id

    @given(st.text(min_size=0, max_size=200))
    @settings(max_examples=300)
    def test_result_is_safe_for_filenames(self, title: str):
        """Fallback slugs must be filename-safe (no weird characters)."""
        result = extract_story_id(title)
        # Standard IDs are PREFIX-NNN — always safe
        if re.match(r"^[A-Z]+-\d+$", result):
            return
        # Fallback slugs or "UNKNOWN" — must be uppercase alphanumeric + dash/underscore
        assert re.match(
            r"^[A-Z0-9_-]+$", result
        ), f"Unsafe slug {result!r} for title={title!r}"

    @given(st.text(min_size=0, max_size=200))
    @settings(max_examples=300)
    def test_result_max_length(self, title: str):
        """Result is never longer than 40 chars (fallback limit) or the ID itself."""
        result = extract_story_id(title)
        if re.match(r"^[A-Z]+-\d+$", result):
            # Standard IDs have no length limit but are bounded by input
            assert len(result) <= len(title) + 1
        else:
            assert len(result) <= 40

    @example("")
    @example("   ")
    @example("::::")
    @example("---")
    @example("🎉🎊🎈")
    @given(st.text(max_size=50))
    @settings(max_examples=200)
    def test_never_crashes(self, title: str):
        """Must never raise an exception and always returns str."""
        result = extract_story_id(title)
        assert isinstance(result, str)


# ============================================================================
# 2. extract_sp — must always return a non-negative integer
# ============================================================================

class TestExtractSp:
    """Property tests for extract_sp."""

    @given(st.dictionaries(st.text(max_size=20), st.text(max_size=200)))
    @settings(max_examples=300)
    def test_always_returns_int(self, issue: dict):
        """extract_sp must return an integer >= 0 for any dict input."""
        result = extract_sp(issue)
        assert isinstance(result, int)
        assert result >= 0

    @given(sp_value=st.integers(min_value=0, max_value=999))
    @settings(max_examples=200)
    def test_label_extraction(self, sp_value: int):
        """sp:N labels are always correctly extracted."""
        issue = {"labels": [{"name": f"sp:{sp_value}"}]}
        assert extract_sp(issue) == sp_value

    @given(sp_value=st.integers(min_value=0, max_value=999))
    @settings(max_examples=200)
    def test_body_text_extraction(self, sp_value: int):
        """'story points: N' in body is always extracted."""
        issue = {"body": f"Some text\nstory points: {sp_value}\nmore text"}
        assert extract_sp(issue) == sp_value

    @given(sp_value=st.integers(min_value=0, max_value=999))
    @settings(max_examples=200)
    def test_body_table_extraction(self, sp_value: int):
        """| SP | N | table format is always extracted."""
        issue = {"body": f"| SP | {sp_value} |"}
        assert extract_sp(issue) == sp_value

    @given(sp_value=st.integers(min_value=0, max_value=999))
    @settings(max_examples=200)
    def test_sp_equals_extraction(self, sp_value: int):
        """'sp = N' in body is always extracted."""
        issue = {"body": f"sp = {sp_value}"}
        assert extract_sp(issue) == sp_value

    def test_no_false_positives_on_words(self):
        """Words containing 'sp' should not trigger false matches."""
        issue = {"body": "This is a special display of a spectrum"}
        assert extract_sp(issue) == 0

    @given(
        sp_label=st.integers(min_value=1, max_value=99),
        sp_body=st.integers(min_value=1, max_value=99),
    )
    @settings(max_examples=100)
    def test_label_takes_precedence(self, sp_label: int, sp_body: int):
        """When both label and body have SP, label wins."""
        assume(sp_label != sp_body)
        issue = {
            "labels": [{"name": f"sp:{sp_label}"}],
            "body": f"story points: {sp_body}",
        }
        assert extract_sp(issue) == sp_label

    @given(st.text(max_size=200))
    @settings(max_examples=200)
    def test_never_crashes_on_body(self, body: str):
        """Random body text never causes a crash and returns int >= 0."""
        result = extract_sp({"body": body, "labels": []})
        assert isinstance(result, int)
        assert result >= 0


# ============================================================================
# 3. _yaml_safe — roundtrip: quoted values must be parseable back
# ============================================================================

class TestYamlSafe:
    """Property tests for _yaml_safe (sync_tracking.py)."""

    @given(st.text(max_size=200))
    @settings(max_examples=500)
    def test_never_crashes(self, value: str):
        """Must handle any string without raising and always returns str."""
        result = _yaml_safe(value)
        assert isinstance(result, str)

    @given(st.text(min_size=1, max_size=200))
    @settings(max_examples=500)
    def test_nonempty_input_produces_nonempty_output(self, value: str):
        """Non-empty input produces non-empty output."""
        result = _yaml_safe(value)
        assert len(result) > 0

    def test_empty_string_passthrough(self):
        """Empty string passes through unchanged."""
        assert _yaml_safe("") == ""

    @given(st.text(min_size=1, max_size=200))
    @settings(max_examples=500)
    def test_quoting_roundtrip(self, value: str):
        """If _yaml_safe quotes the value, unquoting must recover the original.

        BH-007: Uses the same unescape logic as read_tf (unescape quotes
        first, then backslashes) instead of a hand-rolled reverse.
        """
        result = _yaml_safe(value)
        if result.startswith('"') and result.endswith('"'):
            # Unquote using single-pass unescape to avoid \\n vs \n confusion
            # (BH-007, BH21-005). Simple chained .replace() can't handle
            # strings containing literal backslash+n vs escaped newlines.
            _ESCAPE_MAP = {'\\': '\\', '"': '"', 'n': '\n', 'r': '\r'}
            inner = re.sub(
                r'\\(.)',
                lambda m: _ESCAPE_MAP.get(m.group(1), m.group(0)),
                result[1:-1],
            )
            assert inner == value, (
                f"Roundtrip failed: {value!r} -> {result!r} -> {inner!r}"
            )
        else:
            # Not quoted — must be identical
            assert result == value

    @given(st.text(min_size=1, max_size=200))
    @settings(max_examples=500)
    def test_dangerous_chars_get_quoted(self, value: str):
        """Values with YAML-dangerous characters must be quoted."""
        _YAML_BOOL_KEYWORDS = {
            "true", "false", "yes", "no", "on", "off", "null",
        }
        dangerous = (
            ': ' in value
            or value.endswith(':')
            or (value and value[0] in '\'\"[{>|*&!%@`')
            or '#' in value
            or value.startswith('- ')
            or value.startswith('? ')
            or value.lower() in _YAML_BOOL_KEYWORDS  # BH-007
            or '\\' in value  # BH-007
        )
        result = _yaml_safe(value)
        if dangerous:
            assert result.startswith('"') and result.endswith('"'), (
                f"Dangerous value not quoted: {value!r} -> {result!r}"
            )

    @example('hello "world"')
    @example('"already quoted"')
    @example('value: with colon')
    @example('# comment-like')
    @example('- list item')
    @example('? mapping key')
    @given(st.text(min_size=1, max_size=100))
    @settings(max_examples=300)
    def test_no_unescaped_quotes_inside(self, value: str):
        """Quoted output must not have unescaped double quotes in the middle."""
        result = _yaml_safe(value)
        if result.startswith('"') and result.endswith('"'):
            inner = result[1:-1]
            # Walk the inner string: every " must be preceded by \
            i = 0
            while i < len(inner):
                if inner[i] == '"':
                    assert i > 0 and inner[i - 1] == '\\', (
                        f"Unescaped \" at position {i} in {result!r}"
                    )
                i += 1

    @given(st.from_regex(r"^\d+\.?\d*$", fullmatch=True))
    @settings(max_examples=200)
    def test_numeric_strings_always_quoted(self, value: str):
        """BH23-115: Numeric-looking strings must be quoted to prevent YAML type coercion."""
        result = _yaml_safe(value)
        assert result.startswith('"') and result.endswith('"'), (
            f"Numeric string not quoted: {value!r} -> {result!r}"
        )

    @given(st.text(min_size=0, max_size=200))
    @settings(max_examples=500)
    def test_frontmatter_value_roundtrip(self, value: str):
        """BH23-205: _yaml_safe -> frontmatter_value must recover original value."""
        safe = _yaml_safe(value)
        if not value:
            return  # empty string returns None from frontmatter_value
        recovered = frontmatter_value(f"key: {safe}", "key")
        assert recovered == value, (
            f"Round-trip failed: {value!r} -> {safe!r} -> {recovered!r}"
        )


# ============================================================================
# 4. parse_simple_toml — structural invariants
# ============================================================================

# Strategies for generating valid TOML fragments
_toml_key = st.from_regex(r"[a-zA-Z_][a-zA-Z0-9_-]{0,20}", fullmatch=True)
_toml_string_val = st.text(
    alphabet=st.characters(
        whitelist_categories=("L", "N", "P", "S", "Z"),
        # Allow all TOML-sensitive characters — _toml_line must escape them
        blacklist_characters='\r',  # carriage returns not supported in basic TOML strings
    ),
    max_size=50,
)
_toml_int_val = st.integers(min_value=-9999, max_value=9999)
_toml_bool_val = st.booleans()


def _toml_line(key: str, value) -> str:
    """Build a single TOML key=value line with proper TOML escaping."""
    if isinstance(value, bool):
        return f'{key} = {"true" if value else "false"}'
    elif isinstance(value, int):
        return f"{key} = {value}"
    else:
        s = str(value)
        # Escape in TOML order: backslashes first, then quotes, then newlines
        s = s.replace("\\", "\\\\")
        s = s.replace('"', '\\"')
        s = s.replace("\n", "\\n")
        s = s.replace("\t", "\\t")
        return f'{key} = "{s}"'


class TestParseSimpleToml:
    """Property tests for parse_simple_toml."""

    @given(st.text(max_size=500))
    @settings(max_examples=300)
    def test_random_text_returns_dict_or_raises_valueerror(self, text: str):
        """Random text either returns a dict or raises ValueError (fuzz test)."""
        try:
            result = parse_simple_toml(text)
            assert isinstance(result, dict)
        except ValueError:
            pass  # Unterminated multiline arrays raise ValueError — that's fine

    @given(
        key=_toml_key,
        value=st.one_of(_toml_string_val, _toml_int_val, _toml_bool_val),
    )
    @settings(max_examples=300)
    def test_valid_toml_never_raises(self, key: str, value):
        """BH-012: Well-formed TOML must parse without ValueError.

        Separate from the random-text fuzz test: this generates only valid
        TOML lines and asserts they NEVER raise, closing the gap where
        the fuzz test accepted ValueError on valid input.
        """
        line = _toml_line(key, value)
        result = parse_simple_toml(line)
        assert isinstance(result, dict), f"Expected dict from valid TOML: {line!r}"
        assert key in result, f"Key {key!r} missing from parsed result"

    @given(
        key=_toml_key,
        value=st.one_of(_toml_string_val, _toml_int_val, _toml_bool_val),
    )
    @settings(max_examples=300)
    def test_single_kv_roundtrip(self, key: str, value):
        """A single key=value line must roundtrip correctly."""
        line = _toml_line(key, value)
        result = parse_simple_toml(line)
        assert key in result
        if isinstance(value, str):
            assert result[key] == value, f"{line!r} -> {result!r}"
        elif isinstance(value, bool):
            assert result[key] is value
        else:
            assert result[key] == value

    @given(
        section=st.from_regex(r"[a-zA-Z][a-zA-Z0-9_]{0,10}", fullmatch=True),
        key=_toml_key,
        value=_toml_string_val,
    )
    @settings(max_examples=300)
    def test_section_nesting(self, section: str, key: str, value: str):
        """[section] header creates nested dict."""
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        toml_text = f'[{section}]\n{key} = "{escaped}"'
        result = parse_simple_toml(toml_text)
        assert section in result
        assert isinstance(result[section], dict)
        assert result[section][key] == value

    @given(
        items=st.lists(_toml_string_val, min_size=0, max_size=5),
    )
    @settings(max_examples=200)
    def test_string_array(self, items: list):
        """Arrays of strings must roundtrip."""
        escaped_items = [
            '"' + v.replace("\\", "\\\\").replace('"', '\\"') + '"'
            for v in items
        ]
        line = f'arr = [{", ".join(escaped_items)}]'
        result = parse_simple_toml(line)
        assert result["arr"] == items

    def test_empty_input(self):
        """Empty string produces empty dict."""
        assert parse_simple_toml("") == {}

    def test_comments_only(self):
        """Comment-only input produces empty dict."""
        assert parse_simple_toml("# just a comment\n# another") == {}

    def test_unquoted_value_with_spaces_warns(self):
        """P13-008: Unquoted multi-word value emits a warning."""
        import io
        from contextlib import redirect_stderr
        buf = io.StringIO()
        with redirect_stderr(buf):
            result = parse_simple_toml("key = hello world")
        assert result["key"] == "hello world"
        assert "unquoted" in buf.getvalue().lower()

    def test_quoted_value_no_warning(self):
        """P13-008: Properly quoted value does not warn."""
        import io
        from contextlib import redirect_stderr
        buf = io.StringIO()
        with redirect_stderr(buf):
            result = parse_simple_toml('key = "hello world"')
        assert result["key"] == "hello world"
        assert buf.getvalue() == ""

    def test_unicode_escape_4digit(self):
        """P13-017: \\uXXXX produces correct unicode character."""
        result = parse_simple_toml('name = "caf\\u00e9"')
        assert result["name"] == "café"

    def test_unicode_escape_8digit(self):
        """P13-017: \\UXXXXXXXX produces correct unicode character."""
        result = parse_simple_toml('emoji = "\\U0001F600"')
        assert result["emoji"] == "\U0001F600"

    def test_unicode_escape_basic_latin(self):
        """P13-017: \\u0041 produces 'A'."""
        result = parse_simple_toml('letter = "\\u0041"')
        assert result["letter"] == "A"

    def test_invalid_unicode_escape_preserved(self):
        """P13-017: Invalid hex digits are kept as-is."""
        result = parse_simple_toml('bad = "\\uZZZZ"')
        assert result["bad"] == "\\uZZZZ"

    @given(
        key=_toml_key,
        items=st.lists(_toml_string_val, min_size=1, max_size=4),
    )
    @settings(max_examples=200)
    def test_multiline_array(self, key: str, items: list):
        """Multiline arrays (bracket on next lines) must roundtrip."""
        inner_lines = [
            '  "' + v.replace("\\", "\\\\").replace('"', '\\"') + '",'
            for v in items
        ]
        toml_text = f"{key} = [\n" + "\n".join(inner_lines) + "\n]"
        result = parse_simple_toml(toml_text)
        assert result[key] == items

    @given(
        s1=st.from_regex(r"[a-zA-Z][a-zA-Z0-9_]{0,8}", fullmatch=True),
        s2=st.from_regex(r"[a-zA-Z][a-zA-Z0-9_]{0,8}", fullmatch=True),
        k1=_toml_key,
        k2=_toml_key,
    )
    @settings(max_examples=200)
    def test_multiple_sections_independent(self, s1: str, s2: str, k1: str, k2: str):
        """Two different sections don't overwrite each other."""
        assume(s1 != s2)
        toml_text = f'[{s1}]\n{k1} = "a"\n[{s2}]\n{k2} = "b"'
        result = parse_simple_toml(toml_text)
        assert s1 in result
        assert s2 in result
        assert result[s1][k1] == "a"
        assert result[s2][k2] == "b"


# ============================================================================
# 5. _parse_team_index — table parsing invariants (calls production code)
# ============================================================================

class TestParseTeamIndexProperties:
    """Property tests for team INDEX.md table parsing via production _parse_team_index."""

    @given(
        name=st.text(
            alphabet=st.characters(whitelist_categories=("L", "N"), min_codepoint=65, max_codepoint=122),
            min_size=1,
            max_size=20,
        ),
        role=st.sampled_from(["Developer", "Reviewer", "Designer", "QA", "PM"]),
    )
    @settings(max_examples=200)
    def test_table_row_extraction(self, name: str, role: str):
        """Production parser extracts name, role, and file from a table row."""
        table = (
            "| Name | Role | File |\n"
            "| --- | --- | --- |\n"
            f"| {name} | {role} | {name.lower()}.md |\n"
        )
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write(table)
            f.flush()
            rows = _parse_team_index(Path(f.name))
        Path(f.name).unlink()
        assert len(rows) == 1
        assert rows[0]["name"] == name
        assert rows[0]["role"] == role
        assert rows[0]["file"] == f"{name.lower()}.md"

    @given(
        n_rows=st.integers(min_value=0, max_value=10),
    )
    @settings(max_examples=100)
    def test_row_count_fidelity(self, n_rows: int):
        """Number of data rows parsed by production code equals rows in input."""
        header = "| Name | Role | File |"
        sep = "| --- | --- | --- |"
        rows = [f"| Person{i} | Dev | person{i}.md |" for i in range(n_rows)]
        table = "\n".join([header, sep] + rows) + "\n"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write(table)
            f.flush()
            parsed = _parse_team_index(Path(f.name))
        Path(f.name).unlink()
        assert len(parsed) == n_rows
