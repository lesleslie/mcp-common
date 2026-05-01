"""Tests for mcp_common.parsing.tree_sitter.exceptions."""

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


# ---------------------------------------------------------------------------
# 1. TreeSitterError base
# ---------------------------------------------------------------------------


class TestTreeSitterError:
    """Base exception for tree-sitter operations."""

    def test_defaults(self) -> None:
        err = TreeSitterError("something went wrong")
        assert err.domain == "treesitter"
        assert err.code == "UNKNOWN"
        assert err.details == {}
        assert str(err) == "something went wrong"

    def test_custom_code(self) -> None:
        err = TreeSitterError("oops", code="CUSTOM_001")
        assert err.code == "CUSTOM_001"

    def test_custom_details(self) -> None:
        details = {"key": "value", "nested": {"a": 1}}
        err = TreeSitterError("oops", details=details)
        assert err.details == details

    def test_empty_code_is_not_overridden(self) -> None:
        """An explicit empty string for code should NOT override the default."""
        err = TreeSitterError("oops", code="")
        # The implementation uses `if code:` which is falsy for empty string,
        # so the class-level default remains.
        assert err.code == "UNKNOWN"

    def test_message_propagation(self) -> None:
        msg = "detailed failure message"
        err = TreeSitterError(msg)
        assert str(err) == msg
        assert err.args[0] == msg

    def test_to_dict_format(self) -> None:
        err = TreeSitterError("fail", code="C1", details={"x": 1})
        d = err.to_dict()
        assert d == {
            "domain": "treesitter",
            "code": "C1",
            "message": "fail",
            "details": {"x": 1},
        }

    def test_isinstance_base(self) -> None:
        err = TreeSitterError("x")
        assert isinstance(err, TreeSitterError)
        assert isinstance(err, Exception)

    def test_isinstance_subclass(self) -> None:
        err = LanguageNotSupportedError("cobol")
        assert isinstance(err, TreeSitterError)
        assert isinstance(err, Exception)


# ---------------------------------------------------------------------------
# 2. LanguageNotSupportedError
# ---------------------------------------------------------------------------


class TestLanguageNotSupportedError:
    def test_code(self) -> None:
        err = LanguageNotSupportedError("brainfuck")
        assert err.code == "LANGUAGE_NOT_SUPPORTED"

    def test_language_attr(self) -> None:
        err = LanguageNotSupportedError("brainfuck")
        assert err.language == "brainfuck"

    def test_message_without_supported(self) -> None:
        err = LanguageNotSupportedError("brainfuck")
        assert str(err) == "Language not supported: brainfuck"

    def test_message_with_supported(self) -> None:
        err = LanguageNotSupportedError("brainfuck", supported=["python", "go"])
        assert str(err) == "Language not supported: brainfuck. Supported: python, go"

    def test_details_without_supported(self) -> None:
        err = LanguageNotSupportedError("brainfuck")
        assert err.details == {"language": "brainfuck"}

    def test_details_with_supported(self) -> None:
        err = LanguageNotSupportedError("brainfuck", supported=["python", "go"])
        assert err.details == {"language": "brainfuck", "supported": ["python", "go"]}


# ---------------------------------------------------------------------------
# 3. ParseSyntaxError
# ---------------------------------------------------------------------------


class TestParseSyntaxError:
    def test_code(self) -> None:
        err = ParseSyntaxError("main.py", 42, "unexpected token")
        assert err.code == "SYNTAX_ERROR"

    def test_message_with_column(self) -> None:
        err = ParseSyntaxError("main.py", 42, "unexpected token", column=10)
        assert str(err) == "Syntax error at main.py:42:10: unexpected token"

    def test_message_without_column(self) -> None:
        err = ParseSyntaxError("main.py", 42, "unexpected token")
        assert str(err) == "Syntax error at main.py:42: unexpected token"

    def test_attrs(self) -> None:
        err = ParseSyntaxError("main.py", 42, "unexpected token", column=10, error_count=3)
        assert err.file_path == "main.py"
        assert err.line == 42
        assert err.column == 10

    def test_details(self) -> None:
        err = ParseSyntaxError("main.py", 42, "unexpected token", column=10, error_count=3)
        assert err.details == {
            "file_path": "main.py",
            "line": 42,
            "column": 10,
            "error_count": 3,
        }

    def test_column_none_in_details(self) -> None:
        err = ParseSyntaxError("main.py", 42, "unexpected token")
        assert err.details["column"] is None
        assert err.column is None

    def test_default_error_count(self) -> None:
        err = ParseSyntaxError("main.py", 42, "unexpected token")
        assert err.details["error_count"] == 1


# ---------------------------------------------------------------------------
# 4. FileTooLargeError
# ---------------------------------------------------------------------------


class TestFileTooLargeError:
    def test_code(self) -> None:
        err = FileTooLargeError("big.py", 15_000_000, 10_000_000)
        assert err.code == "FILE_TOO_LARGE"

    def test_message_formatted_bytes(self) -> None:
        err = FileTooLargeError("big.py", 15_000_000, 10_000_000)
        assert str(err) == "File big.py (15,000,000 bytes) exceeds limit (10,000,000 bytes)"

    def test_small_values(self) -> None:
        err = FileTooLargeError("a.txt", 500, 100)
        assert str(err) == "File a.txt (500 bytes) exceeds limit (100 bytes)"

    def test_attrs(self) -> None:
        err = FileTooLargeError("big.py", 15_000_000, 10_000_000)
        assert err.file_path == "big.py"
        assert err.size_bytes == 15_000_000
        assert err.max_bytes == 10_000_000

    def test_details(self) -> None:
        err = FileTooLargeError("big.py", 15_000_000, 10_000_000)
        assert err.details == {
            "file_path": "big.py",
            "size_bytes": 15_000_000,
            "max_bytes": 10_000_000,
        }


# ---------------------------------------------------------------------------
# 5. QuerySyntaxError
# ---------------------------------------------------------------------------


class TestQuerySyntaxError:
    def test_code(self) -> None:
        err = QuerySyntaxError("(function_definition", "missing closing paren")
        assert err.code == "QUERY_SYNTAX_ERROR"

    def test_query_attr(self) -> None:
        q = "(function_definition"
        err = QuerySyntaxError(q, "missing closing paren")
        assert err.query == q

    def test_message(self) -> None:
        err = QuerySyntaxError("(function_definition", "missing closing paren")
        assert str(err) == "Query syntax error: missing closing paren"

    def test_details_without_offset(self) -> None:
        err = QuerySyntaxError("(function_definition", "missing closing paren")
        assert err.details == {"query": "(function_definition"}
        assert err.offset is None

    def test_details_with_offset(self) -> None:
        err = QuerySyntaxError("(function_definition", "missing closing paren", offset=5)
        assert err.details == {"query": "(function_definition", "offset": 5}
        assert err.offset == 5

    def test_query_truncated_in_details(self) -> None:
        long_query = "x" * 150
        err = QuerySyntaxError(long_query, "bad")
        # query in details should be truncated to 100 chars
        assert len(err.details["query"]) == 100
        assert err.details["query"] == "x" * 100

    def test_short_query_not_truncated(self) -> None:
        q = "(function_declaration name: (identifier))"
        err = QuerySyntaxError(q, "bad")
        assert err.details["query"] == q

    def test_exact_100_char_query(self) -> None:
        q = "a" * 100
        err = QuerySyntaxError(q, "bad")
        assert err.details["query"] == q


# ---------------------------------------------------------------------------
# 6. LanguageHandlerNotFoundError
# ---------------------------------------------------------------------------


class TestLanguageHandlerNotFoundError:
    def test_code(self) -> None:
        err = LanguageHandlerNotFoundError("rust")
        assert err.code == "HANDLER_NOT_FOUND"

    def test_language_attr(self) -> None:
        err = LanguageHandlerNotFoundError("rust")
        assert err.language == "rust"

    def test_message(self) -> None:
        err = LanguageHandlerNotFoundError("rust")
        assert str(err) == "No handler registered for language: rust"

    def test_details(self) -> None:
        err = LanguageHandlerNotFoundError("rust")
        assert err.details == {"language": "rust"}


# ---------------------------------------------------------------------------
# 7. CacheError
# ---------------------------------------------------------------------------


class TestCacheError:
    def test_code(self) -> None:
        err = CacheError("cache miss")
        assert err.code == "CACHE_ERROR"

    def test_inherits_from_base(self) -> None:
        err = CacheError("cache miss")
        assert isinstance(err, TreeSitterError)
        assert isinstance(err, Exception)

    def test_message_propagation(self) -> None:
        err = CacheError("disk full", details={"path": "/tmp/cache"})
        assert str(err) == "disk full"
        assert err.details == {"path": "/tmp/cache"}


# ---------------------------------------------------------------------------
# 8. ParseTimeoutError
# ---------------------------------------------------------------------------


class TestParseTimeoutError:
    def test_code(self) -> None:
        err = ParseTimeoutError("huge.py", 30.0)
        assert err.code == "PARSE_TIMEOUT"

    def test_file_path_attr(self) -> None:
        err = ParseTimeoutError("huge.py", 30.0)
        assert err.file_path == "huge.py"

    def test_timeout_seconds_attr(self) -> None:
        err = ParseTimeoutError("huge.py", 30.0)
        assert err.timeout_seconds == 30.0

    def test_message(self) -> None:
        err = ParseTimeoutError("huge.py", 30.0)
        assert str(err) == "Parsing timed out after 30.0s: huge.py"

    def test_message_integer_timeout(self) -> None:
        err = ParseTimeoutError("huge.py", 5)
        assert str(err) == "Parsing timed out after 5s: huge.py"

    def test_details(self) -> None:
        err = ParseTimeoutError("huge.py", 30.0)
        assert err.details == {
            "file_path": "huge.py",
            "timeout_seconds": 30.0,
        }


# ---------------------------------------------------------------------------
# 9. Catch-as-base
# ---------------------------------------------------------------------------


class TestCatchAsBase:
    """All concrete exceptions should be catchable as TreeSitterError."""

    @pytest.mark.parametrize(
        "exc_factory",
        [
            lambda: LanguageNotSupportedError("x"),
            lambda: ParseSyntaxError("f.py", 1, "err"),
            lambda: FileTooLargeError("f.py", 100, 50),
            lambda: QuerySyntaxError("q", "bad"),
            lambda: LanguageHandlerNotFoundError("x"),
            lambda: CacheError("miss"),
            lambda: ParseTimeoutError("f.py", 10),
        ],
    )
    def test_catchable_as_base(self, exc_factory) -> None:
        with pytest.raises(TreeSitterError):
            raise exc_factory()


# ---------------------------------------------------------------------------
# 10. to_dict works for all exception types
# ---------------------------------------------------------------------------


class TestToDictAllTypes:
    """Every exception type should produce a valid to_dict output."""

    def test_tree_sitter_error(self) -> None:
        err = TreeSitterError("base", code="B1", details={"a": 1})
        d = err.to_dict()
        assert d["domain"] == "treesitter"
        assert d["code"] == "B1"
        assert d["message"] == "base"
        assert d["details"] == {"a": 1}

    def test_language_not_supported_error(self) -> None:
        err = LanguageNotSupportedError("x", supported=["py"])
        d = err.to_dict()
        assert d["domain"] == "treesitter"
        assert d["code"] == "LANGUAGE_NOT_SUPPORTED"
        assert "Language not supported: x" in d["message"]
        assert d["details"]["language"] == "x"
        assert d["details"]["supported"] == ["py"]

    def test_parse_syntax_error(self) -> None:
        err = ParseSyntaxError("f.py", 3, "bad", column=7, error_count=2)
        d = err.to_dict()
        assert d["domain"] == "treesitter"
        assert d["code"] == "SYNTAX_ERROR"
        assert "f.py:3:7" in d["message"]
        assert d["details"]["error_count"] == 2

    def test_file_too_large_error(self) -> None:
        err = FileTooLargeError("big.py", 5_000_000, 1_000_000)
        d = err.to_dict()
        assert d["domain"] == "treesitter"
        assert d["code"] == "FILE_TOO_LARGE"
        assert "5,000,000" in d["message"]
        assert d["details"]["size_bytes"] == 5_000_000

    def test_query_syntax_error(self) -> None:
        err = QuerySyntaxError("(fn", "bad", offset=2)
        d = err.to_dict()
        assert d["domain"] == "treesitter"
        assert d["code"] == "QUERY_SYNTAX_ERROR"
        assert d["details"]["query"] == "(fn"
        assert d["details"]["offset"] == 2

    def test_language_handler_not_found_error(self) -> None:
        err = LanguageHandlerNotFoundError("go")
        d = err.to_dict()
        assert d["domain"] == "treesitter"
        assert d["code"] == "HANDLER_NOT_FOUND"
        assert d["details"]["language"] == "go"

    def test_cache_error(self) -> None:
        err = CacheError("eviction failure", details={"key": "k1"})
        d = err.to_dict()
        assert d["domain"] == "treesitter"
        assert d["code"] == "CACHE_ERROR"
        assert d["details"]["key"] == "k1"

    def test_parse_timeout_error(self) -> None:
        err = ParseTimeoutError("slow.py", 60.5)
        d = err.to_dict()
        assert d["domain"] == "treesitter"
        assert d["code"] == "PARSE_TIMEOUT"
        assert d["details"]["timeout_seconds"] == 60.5
