"""Tree-sitter parsing utilities for mcp-common.

Provides multi-language code parsing with:
- Content-hash caching
- ProcessPoolExecutor for CPU-bound parsing
- Structured Pydantic models
- Async API

Example:
    >>> from mcp_common.parsing.tree_sitter import TreeSitterParser
    >>> parser = TreeSitterParser()
    >>> result = await parser.parse_file(Path("example.py"))
    >>> for symbol in result.symbols:
    ...     print(f"{symbol.kind.value}: {symbol.name}")
"""

from __future__ import annotations

from mcp_common.parsing.tree_sitter.cache import (
    CacheEntry,
    CacheStats,
    ContentHashLRUCache,
    ParseResultCache,
)
from mcp_common.parsing.tree_sitter.core import (
    LanguageHandler,
    LanguageRegistry,
    TreeSitterParser,
    get_parser,
)
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
from mcp_common.parsing.tree_sitter.exceptions import (
    LanguageNotSupportedError as UnsupportedLanguageError,
)
from mcp_common.parsing.tree_sitter.grammars import (
    ensure_language_loaded,
    get_loaded_languages,
    is_language_loaded,
    load_all_grammars,
    load_go_grammar,
    load_python_grammar,
)
from mcp_common.parsing.tree_sitter.models import (
    ComplexityMetrics,
    ImportInfo,
    ParseResult,
    QueryMatch,
    QueryResult,
    SupportedLanguage,
    SymbolInfo,
    SymbolKind,
    SymbolRelationship,
)
from mcp_common.parsing.tree_sitter.queries import (
    GO_QUERIES,
    PYTHON_QUERIES,
    get_query,
    list_queries,
)

__all__ = [
    # Queries
    "GO_QUERIES",
    "PYTHON_QUERIES",
    # Cache
    "CacheEntry",
    # Exceptions
    "CacheError",
    "CacheStats",
    # Models
    "ComplexityMetrics",
    "ContentHashLRUCache",
    "FileTooLargeError",
    "ImportInfo",
    # Core
    "LanguageHandler",
    "LanguageHandlerNotFoundError",
    "LanguageNotSupportedError",
    "LanguageRegistry",
    "ParseResult",
    "ParseResultCache",
    "ParseSyntaxError",
    "ParseTimeoutError",
    "QueryMatch",
    "QueryResult",
    "QuerySyntaxError",
    "SupportedLanguage",
    "SymbolInfo",
    "SymbolKind",
    "SymbolRelationship",
    "TreeSitterError",
    "TreeSitterParser",
    "UnsupportedLanguageError",
    # Grammars
    "ensure_language_loaded",
    "get_loaded_languages",
    "get_parser",
    "get_query",
    "is_language_loaded",
    "list_queries",
    "load_all_grammars",
    "load_go_grammar",
    "load_python_grammar",
]
