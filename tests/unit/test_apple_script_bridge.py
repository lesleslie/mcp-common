import pytest
from mcp_common.apple_script.bridge import escape_for_applescript, build_applescript_string


def test_escape_backslash():
    assert escape_for_applescript("a\\b") == 'a\\\\b'


def test_escape_double_quote():
    assert escape_for_applescript('a"b') == 'a\\"b'


def test_escape_single_quote():
    assert escape_for_applescript("a'b") == "a\\'b"


def test_escape_tab():
    assert escape_for_applescript("a\tb") == "a\\tb"


def test_escape_carriage_return_removed():
    assert escape_for_applescript("a\rb") == "ab"


def test_build_single_line_string():
    result = build_applescript_string("hello world")
    assert result == '"hello world"'


def test_build_multi_line_string():
    result = build_applescript_string("line1\nline2")
    expected = '"line1" & return & "line2"'
    assert result == expected


def test_build_empty_string():
    result = build_applescript_string("")
    assert result == '""'