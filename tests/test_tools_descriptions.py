"""Tests for mcp_common.tools.descriptions.trim_description."""

from __future__ import annotations

import pytest

from mcp_common.tools.descriptions import (
    MAX_DESCRIPTION_LENGTH,
    _STRIP_SECTIONS,
    trim_description,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

class TestConstants:
    """Verify exported constant values."""

    def test_max_description_length_value(self) -> None:
        assert MAX_DESCRIPTION_LENGTH == 200

    def test_strip_sections_includes_all_expected(self) -> None:
        expected = (
            "Args:",
            "Returns:",
            "Raises:",
            "Example:",
            "Examples:",
            "Note:",
            "Notes:",
        )
        for section in expected:
            assert section in _STRIP_SECTIONS

    def test_strip_sections_is_tuple(self) -> None:
        assert isinstance(_STRIP_SECTIONS, tuple)


# ---------------------------------------------------------------------------
# Edge-case inputs
# ---------------------------------------------------------------------------

class TestEdgeCaseInputs:
    """None, empty, and whitespace-only inputs."""

    def test_none_returns_empty_string(self) -> None:
        assert trim_description(None) == ""

    def test_empty_string_returns_empty_string(self) -> None:
        assert trim_description("") == ""

    def test_whitespace_only_returns_empty_string(self) -> None:
        assert trim_description("   \n\t  \n") == ""


# ---------------------------------------------------------------------------
# Simple descriptions
# ---------------------------------------------------------------------------

class TestSimpleDescriptions:
    """Single-line and short descriptions pass through unchanged."""

    def test_single_line_preserved(self) -> None:
        assert trim_description("Do the thing.") == "Do the thing."

    def test_single_line_with_trailing_whitespace_stripped(self) -> None:
        assert trim_description("Do the thing.   ") == "Do the thing."

    def test_short_description_under_limit(self) -> None:
        doc = "A short description of the tool."
        assert trim_description(doc) == doc

    def test_description_preserves_internal_whitespace_within_line(self) -> None:
        """The function joins multi-line paragraphs with spaces but does not
        collapse whitespace *within* a single line."""
        assert trim_description("Do   the    thing.") == "Do   the    thing."


# ---------------------------------------------------------------------------
# Multi-paragraph docstrings
# ---------------------------------------------------------------------------

class TestMultiParagraph:
    """Only the first non-empty paragraph is returned."""

    def test_returns_first_paragraph_only(self) -> None:
        doc = (
            "First paragraph of the description.\n"
            "\n"
            "Second paragraph that should be dropped."
        )
        result = trim_description(doc)
        assert result == "First paragraph of the description."

    def test_three_paragraphs_returns_first(self) -> None:
        doc = (
            "Line one.\n"
            "Line two.\n"
            "\n"
            "Second paragraph.\n"
            "\n"
            "Third paragraph."
        )
        result = trim_description(doc)
        assert result == "Line one. Line two."

    def test_first_paragraph_empty_returns_second(self) -> None:
        doc = (
            "\n"
            "\n"
            "This is the real first paragraph."
        )
        result = trim_description(doc)
        assert result == "This is the real first paragraph."


# ---------------------------------------------------------------------------
# Section stripping
# ---------------------------------------------------------------------------

class TestSectionStripping:
    """Args, Returns, Raises, Examples, Example, Note, Notes are stripped."""

    @pytest.mark.parametrize("section", list(_STRIP_SECTIONS))
    def test_section_stops_collection(self, section: str) -> None:
        doc = f"Description before section.\n\n{section}\n  param: int  The param."
        result = trim_description(doc)
        assert result == "Description before section."
        assert section not in result

    def test_args_section_stripped(self) -> None:
        doc = "Create a new record.\n\nArgs:\n    name: The record name."
        assert trim_description(doc) == "Create a new record."

    def test_returns_section_stripped(self) -> None:
        doc = "Calculate the total.\n\nReturns:\n    The sum as a float."
        assert trim_description(doc) == "Calculate the total."

    def test_raises_section_stripped(self) -> None:
        doc = "Parse the file.\n\nRaises:\n    ValueError if file is empty."
        assert trim_description(doc) == "Parse the file."

    def test_examples_section_stripped(self) -> None:
        doc = "Run the pipeline.\n\nExamples:\n    >>> run('test')"
        assert trim_description(doc) == "Run the pipeline."

    def test_note_section_stripped(self) -> None:
        doc = "Compress data.\n\nNote: This uses zlib internally."
        assert trim_description(doc) == "Compress data."

    def test_notes_section_stripped(self) -> None:
        doc = "Compress data.\n\nNotes: This uses zlib internally."
        assert trim_description(doc) == "Compress data."

    def test_section_inline_not_stripped(self) -> None:
        """A section keyword embedded mid-line (not at line start) is kept."""
        doc = "This mentions Args: in the middle of a sentence."
        result = trim_description(doc)
        assert result == "This mentions Args: in the middle of a sentence."


# ---------------------------------------------------------------------------
# Custom max_length
# ---------------------------------------------------------------------------

class TestCustomMaxLength:
    """Caller can pass a different max_length."""

    def test_shorter_max_length(self) -> None:
        doc = "A reasonably long description that exceeds the limit."
        result = trim_description(doc, max_length=20)
        assert len(result) <= 20

    def test_longer_max_length_preserves_more(self) -> None:
        doc = "Short."
        assert trim_description(doc, max_length=500) == "Short."

    def test_max_length_zero(self) -> None:
        doc = "Something."
        result = trim_description(doc, max_length=0)
        # With max_length 0, result[:0-3] => result[:-3] => first N-3 chars + "..."
        assert result.endswith("...")
        assert len(result) == 10  # "Somethi..."


# ---------------------------------------------------------------------------
# Truncation at sentence boundary
# ---------------------------------------------------------------------------

class TestSentenceBoundaryTruncation:
    """When text exceeds max_length, break at the last '. ' past 50%."""

    def test_truncates_at_period_within_range(self) -> None:
        # Build a string where the first sentence ends before 50% of max_length
        first_sentence = "A" * 60 + ". "  # 62 chars, well past 50% of 100
        second_sentence = "B" * 60
        doc = first_sentence + second_sentence
        result = trim_description(doc, max_length=100)
        assert result.endswith(".")
        assert "B" not in result

    def test_keeps_full_text_when_under_limit(self) -> None:
        doc = "A short description."
        assert trim_description(doc, max_length=200) == "A short description."

    def test_truncation_with_exclamation_mark(self) -> None:
        first = "A" * 60 + "! "
        second = "B" * 60
        doc = first + second
        result = trim_description(doc, max_length=100)
        assert result.endswith("!")
        assert "B" not in result

    def test_truncation_with_question_mark(self) -> None:
        first = "A" * 60 + "? "
        second = "B" * 60
        doc = first + second
        result = trim_description(doc, max_length=100)
        assert result.endswith("?")
        assert "B" not in result

    def test_sentence_boundary_before_50_percent_ignored(self) -> None:
        """If the sentence boundary is before 50% of max_length, it is not used."""
        # Sentence ends at char 10, which is < 50% of 100
        short_sentence = "AB. "
        rest = "C" * 110
        doc = short_sentence + rest
        result = trim_description(doc, max_length=100)
        # Should not break at char 10; should either find another boundary
        # or hard-truncate with "..."
        assert result != "AB."


# ---------------------------------------------------------------------------
# Hard truncation with "..."
# ---------------------------------------------------------------------------

class TestHardTruncation:
    """When no sentence boundary is found past 50%, append '...'."""

    def test_appends_ellipsis_when_no_sentence_boundary(self) -> None:
        # A long string with no sentence-ending punctuation
        doc = "A" * 250
        result = trim_description(doc, max_length=100)
        assert result.endswith("...")
        assert len(result) <= 100

    def test_ellipsis_result_within_max_length(self) -> None:
        doc = "x" * 300
        result = trim_description(doc, max_length=50)
        assert len(result) <= 50
        assert result.endswith("...")


# ---------------------------------------------------------------------------
# Whitespace handling
# ---------------------------------------------------------------------------

class TestWhitespaceHandling:
    """Leading/trailing whitespace stripped; internal whitespace collapsed."""

    def test_leading_whitespace_stripped(self) -> None:
        assert trim_description("   Hello world.") == "Hello world."

    def test_trailing_whitespace_stripped(self) -> None:
        assert trim_description("Hello world.   ") == "Hello world."

    def test_internal_multiple_spaces_preserved_within_line(self) -> None:
        """Whitespace within a single line is preserved; only inter-line
        joining collapses to single spaces."""
        assert trim_description("Hello     world.") == "Hello     world."

    def test_internal_newlines_in_paragraph_joined(self) -> None:
        doc = "Hello\nworld."
        result = trim_description(doc)
        assert result == "Hello world."

    def test_multiline_paragraph_joined_with_spaces(self) -> None:
        doc = (
            "Process the incoming\n"
            "data stream and\n"
            "emit results."
        )
        result = trim_description(doc)
        assert result == "Process the incoming data stream and emit results."

    def test_indented_docstring_handled(self) -> None:
        doc = (
            "    Indented first line.\n"
            "    Indented second line."
        )
        result = trim_description(doc)
        assert result == "Indented first line. Indented second line."
