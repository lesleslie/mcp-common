"""Tests for tree-sitter exceptions."""

from __future__ import annotations

import pytest

from mcp_common.parsing.tree_sitter.exceptions import (
    CacheError,
    FileTooLargeError,
    LanguageHandlerNotFoundError,
    LanguageNotSupportedError,
    ParseSyntaxError,
    ParseTimeoutError,
    QuerySyntaxError,
    TreeSitterError,
)


class TestTreeSitterError:
    """Tests for base TreeSitterError."""

    def test_base_exception(self) -> None:
        error = TreeSitterError("Something went wrong")
        assert str(error) == "Something went wrong"
        assert error.domain == "treesitter"
        assert error.code == "UNKNOWN"

    def test_custom_code(self) -> None:
        error = TreeSitterError("Error", code="CUSTOM")
        assert error.code == "CUSTOM"

    def test_to_dict(self) -> None:
        error = TreeSitterError("Error", code="TEST", details={"key": "value"})
        d = error.to_dict()
        assert d["domain"] == "treesitter"
        assert d["code"] == "TEST"
        assert d["message"] == "Error"
        assert d["details"]["key"] == "value"


class TestLanguageNotSupportedError:
    """Tests for LanguageNotSupportedError."""

    def test_basic_error(self) -> None:
        error = LanguageNotSupportedError("ruby")
        assert error.language == "ruby"
        assert "ruby" in str(error)
        assert error.code == "LANGUAGE_NOT_SUPPORTED"

    def test_with_supported_list(self) -> None:
        error = LanguageNotSupportedError(
            "ruby",
            supported=["python", "go"],
        )
        assert "python, go" in str(error)


class TestParseSyntaxError:
    """Tests for ParseSyntaxError."""

    def test_basic_error(self) -> None:
        error = ParseSyntaxError(
            file_path="test.py",
            line=10,
            message="Invalid syntax",
        )
        assert error.file_path == "test.py"
        assert error.line == 10
        assert "test.py:10" in str(error)
        assert error.code == "SYNTAX_ERROR"

    def test_with_column(self) -> None:
        error = ParseSyntaxError(
            file_path="test.py",
            line=10,
            message="Invalid syntax",
            column=5,
        )
        assert "test.py:10:5" in str(error)


class TestFileTooLargeError:
    """Tests for FileTooLargeError."""

    def test_basic_error(self) -> None:
        error = FileTooLargeError(
            file_path="large.py",
            size_bytes=20_000_000,
            max_bytes=10_000_000,
        )
        assert error.file_path == "large.py"
        assert error.size_bytes == 20_000_000
        assert error.max_bytes == 10_000_000
        assert error.code == "FILE_TOO_LARGE"
        assert "exceeds limit" in str(error)


class TestQuerySyntaxError:
    """Tests for QuerySyntaxError."""

    def test_basic_error(self) -> None:
        error = QuerySyntaxError(
            query="(function_definition",
            message="Unclosed parenthesis",
        )
        assert error.query == "(function_definition"
        assert error.code == "QUERY_SYNTAX_ERROR"


class TestLanguageHandlerNotFoundError:
    """Tests for LanguageHandlerNotFoundError."""

    def test_basic_error(self) -> None:
        error = LanguageHandlerNotFoundError("rust")
        assert error.language == "rust"
        assert error.code == "HANDLER_NOT_FOUND"


class TestParseTimeoutError:
    """Tests for ParseTimeoutError."""

    def test_basic_error(self) -> None:
        error = ParseTimeoutError(
            file_path="slow.py",
            timeout_seconds=30.0,
        )
        assert error.file_path == "slow.py"
        assert error.timeout_seconds == 30.0
        assert error.code == "PARSE_TIMEOUT"


class TestCacheError:
    """Tests for CacheError."""

    def test_basic_error(self) -> None:
        error = CacheError("Cache write failed")
        assert error.code == "CACHE_ERROR"
