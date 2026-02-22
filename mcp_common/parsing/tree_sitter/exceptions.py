"""Structured exceptions for tree-sitter parsing."""

from __future__ import annotations

from typing import Any


class TreeSitterError(Exception):
    """Base exception for tree-sitter operations.

    All tree-sitter exceptions inherit from this class,
    allowing for unified error handling.
    """

    domain: str = "treesitter"
    code: str = "UNKNOWN"
    details: dict[str, Any] = {}

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        if code:
            self.code = code
        if details:
            self.details = details

    def to_dict(self) -> dict[str, Any]:
        """Convert exception to dictionary for API responses."""
        return {
            "domain": self.domain,
            "code": self.code,
            "message": str(self),
            "details": self.details,
        }


class LanguageNotSupportedError(TreeSitterError):
    """Language is not supported by the parser.

    Raised when:
    - File extension is not recognized
    - Language is not in SupportedLanguage enum
    - No handler is registered for the language
    """

    code = "LANGUAGE_NOT_SUPPORTED"

    def __init__(
        self,
        language: str,
        *,
        supported: list[str] | None = None,
    ) -> None:
        self.language = language
        message = f"Language not supported: {language}"
        details: dict[str, Any] = {"language": language}
        if supported:
            message += f". Supported: {', '.join(supported)}"
            details["supported"] = supported
        super().__init__(message, details=details)


class ParseSyntaxError(TreeSitterError):
    """Syntax error during parsing.

    Raised when tree-sitter encounters ERROR nodes
    or fatal parsing errors.
    """

    code = "SYNTAX_ERROR"

    def __init__(
        self,
        file_path: str,
        line: int,
        message: str,
        *,
        column: int | None = None,
        error_count: int = 1,
    ) -> None:
        self.file_path = file_path
        self.line = line
        self.column = column
        location = f"{file_path}:{line}"
        if column is not None:
            location += f":{column}"
        full_message = f"Syntax error at {location}: {message}"
        super().__init__(
            full_message,
            details={
                "file_path": file_path,
                "line": line,
                "column": column,
                "error_count": error_count,
            },
        )


class FileTooLargeError(TreeSitterError):
    """File exceeds size limit.

    Raised when a file is too large to parse safely.
    Default limit is 10MB.
    """

    code = "FILE_TOO_LARGE"

    def __init__(
        self,
        file_path: str,
        size_bytes: int,
        max_bytes: int,
    ) -> None:
        self.file_path = file_path
        self.size_bytes = size_bytes
        self.max_bytes = max_bytes
        super().__init__(
            f"File {file_path} ({size_bytes:,} bytes) exceeds limit ({max_bytes:,} bytes)",
            details={
                "file_path": file_path,
                "size_bytes": size_bytes,
                "max_bytes": max_bytes,
            },
        )


class QuerySyntaxError(TreeSitterError):
    """Syntax error in tree-sitter query.

    Raised when a query string is malformed.
    """

    code = "QUERY_SYNTAX_ERROR"

    def __init__(
        self,
        query: str,
        message: str,
        *,
        offset: int | None = None,
    ) -> None:
        self.query = query
        self.offset = offset
        details: dict[str, Any] = {"query": query[:100]}
        if offset is not None:
            details["offset"] = offset
        super().__init__(
            f"Query syntax error: {message}",
            details=details,
        )


class LanguageHandlerNotFoundError(TreeSitterError):
    """No handler registered for language.

    Raised when attempting to parse a language that
    has no registered handler in LanguageRegistry.
    """

    code = "HANDLER_NOT_FOUND"

    def __init__(self, language: str) -> None:
        self.language = language
        super().__init__(
            f"No handler registered for language: {language}",
            details={"language": language},
        )


class CacheError(TreeSitterError):
    """Error in caching layer.

    Base class for cache-related errors.
    """

    code = "CACHE_ERROR"


class ParseTimeoutError(TreeSitterError):
    """Parsing timed out.

    Raised when parsing exceeds the configured timeout.
    """

    code = "PARSE_TIMEOUT"

    def __init__(
        self,
        file_path: str,
        timeout_seconds: float,
    ) -> None:
        self.file_path = file_path
        self.timeout_seconds = timeout_seconds
        super().__init__(
            f"Parsing timed out after {timeout_seconds}s: {file_path}",
            details={
                "file_path": file_path,
                "timeout_seconds": timeout_seconds,
            },
        )
