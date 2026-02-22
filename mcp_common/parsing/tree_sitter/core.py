"""Core tree-sitter parser with async support and ProcessPoolExecutor.

Design decisions:
- ProcessPoolExecutor: Bypasses GIL for CPU-bound parsing
- Content-hash caching: Prevents redundant parsing
- Lazy language loading: Only loads grammars when needed
- Thread-safe: Uses asyncio locks for concurrent access
"""

from __future__ import annotations

import asyncio
import time
from concurrent.futures import ProcessPoolExecutor
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

from mcp_common.parsing.tree_sitter.cache import ContentHashLRUCache, ParseResultCache
from mcp_common.parsing.tree_sitter.exceptions import (
    FileTooLargeError,
    LanguageHandlerNotFoundError,
    LanguageNotSupportedError,
    ParseSyntaxError,
)
from mcp_common.parsing.tree_sitter.models import (
    ComplexityMetrics,
    ImportInfo,
    ParseResult,
    SupportedLanguage,
    SymbolInfo,
    SymbolKind,
    SymbolRelationship,
)

if TYPE_CHECKING:
    import tree_sitter


class LanguageHandler(Protocol):
    """Protocol for language-specific handlers."""

    language: SupportedLanguage

    def extract(
        self,
        content: bytes,
        tree: tree_sitter.Tree,
    ) -> tuple[
        list[SymbolInfo],
        list[SymbolRelationship],
        list[ImportInfo],
    ]:
        """Extract symbols, relationships, and imports from parsed tree."""
        ...

    def compute_complexity(
        self,
        content: bytes,
        tree: tree_sitter.Tree,
    ) -> dict[str, ComplexityMetrics]:
        """Compute complexity metrics for code units."""
        ...


# Default file size limit (10MB)
DEFAULT_MAX_FILE_SIZE = 10 * 1024 * 1024


def _count_error_nodes(node: tree_sitter.Node) -> int:
    """Count ERROR nodes in tree (module-level for pickling).

    Args:
        node: Root node to search

    Returns:
        Number of ERROR nodes found
    """
    count = 0
    if node.type == "ERROR":
        count = 1

    for child in node.children:
        count += _count_error_nodes(child)

    return count


def _parse_sync(
    file_path: Path,
    content: bytes,
    language: SupportedLanguage,
) -> ParseResult:
    """Synchronous parsing (module-level for pickling).

    This function is designed to run in a ProcessPoolExecutor.
    It loads grammars on-demand in the worker process.

    Args:
        file_path: Path for context
        content: Raw bytes to parse
        language: Language to use

    Returns:
        ParseResult
    """
    start_time = time.perf_counter()

    # Load grammar in this process if not already loaded
    from mcp_common.parsing.tree_sitter.grammars import ensure_language_loaded

    if not ensure_language_loaded(language):
        return ParseResult(
            success=False,
            file_path=str(file_path),
            language=language,
            error=f"Failed to load grammar for {language.value}",
        )

    handler = LanguageRegistry.get(language)
    if handler is None:
        return ParseResult(
            success=False,
            file_path=str(file_path),
            language=language,
            error=f"No handler for {language.value}",
        )

    grammar = LanguageRegistry.get_grammar(language)
    if grammar is None:
        return ParseResult(
            success=False,
            file_path=str(file_path),
            language=language,
            error=f"Grammar not loaded for {language.value}",
        )

    try:
        import tree_sitter

        parser = tree_sitter.Parser(grammar)
        tree = parser.parse(content)

        # Count ERROR nodes
        error_count = _count_error_nodes(tree.root_node)

        # Extract symbols, relationships, imports
        symbols, relationships, imports = handler.extract(content, tree)

        # Compute complexity
        complexity = handler.compute_complexity(content, tree)

        parse_time_ms = (time.perf_counter() - start_time) * 1000

        return ParseResult(
            success=True,
            file_path=str(file_path),
            language=language,
            symbols=tuple(symbols),
            relationships=tuple(relationships),
            imports=tuple(imports),
            complexity=complexity,
            parse_time_ms=parse_time_ms,
            error_node_count=error_count,
        )
    except Exception as e:
        return ParseResult(
            success=False,
            file_path=str(file_path),
            language=language,
            error=str(e),
        )


class LanguageRegistry:
    """Registry for language handlers.

    Uses class-level storage for singleton-like behavior.
    Thread-safe through lazy initialization.
    """

    _handlers: dict[SupportedLanguage, LanguageHandler] = {}
    _grammars: dict[SupportedLanguage, tree_sitter.Language] = {}
    _initialized: bool = False

    @classmethod
    def register(cls, handler: LanguageHandler) -> None:
        """Register a language handler."""
        cls._handlers[handler.language] = handler

    @classmethod
    def get(cls, language: SupportedLanguage) -> LanguageHandler | None:
        """Get handler for language."""
        return cls._handlers.get(language)

    @classmethod
    def get_grammar(cls, language: SupportedLanguage) -> tree_sitter.Language | None:
        """Get grammar for language (lazy loaded)."""
        return cls._grammars.get(language)

    @classmethod
    def set_grammar(
        cls,
        language: SupportedLanguage,
        grammar: tree_sitter.Language,
    ) -> None:
        """Set grammar for language."""
        cls._grammars[language] = grammar

    @classmethod
    def supported_languages(cls) -> list[SupportedLanguage]:
        """List supported languages."""
        return list(cls._handlers.keys())

    @classmethod
    def is_supported(cls, language: SupportedLanguage) -> bool:
        """Check if language is supported."""
        return language in cls._handlers and language != SupportedLanguage.UNKNOWN


class TreeSitterParser:
    """Multi-language tree-sitter parser.

    Features:
    - Async I/O for file reading
    - ProcessPoolExecutor for CPU-bound parsing (bypasses GIL)
    - Content-hash caching for deduplication
    - Automatic language detection
    - Error-tolerant parsing

    Example:
        >>> parser = TreeSitterParser()
        >>> result = await parser.parse_file(Path("example.py"))
        >>> print(result.symbols)
    """

    def __init__(
        self,
        cache: ParseResultCache | None = None,
        max_workers: int = 4,
        max_file_size: int = DEFAULT_MAX_FILE_SIZE,
    ) -> None:
        """Initialize parser.

        Args:
            cache: Optional cache instance (creates new if not provided)
            max_workers: Maximum process pool workers
            max_file_size: Maximum file size in bytes
        """
        self._cache = cache or ContentHashLRUCache[ParseResult]()
        self._max_workers = max_workers
        self._max_file_size = max_file_size
        self._executor: ProcessPoolExecutor | None = None
        self._lock = asyncio.Lock()

    def _get_executor(self) -> ProcessPoolExecutor:
        """Get or create process pool executor."""
        if self._executor is None:
            self._executor = ProcessPoolExecutor(max_workers=self._max_workers)
        return self._executor

    def detect_language(self, file_path: Path) -> SupportedLanguage:
        """Detect language from file extension.

        Args:
            file_path: Path to source file

        Returns:
            Detected language or UNKNOWN
        """
        suffix_map: dict[str, SupportedLanguage] = {
            ".py": SupportedLanguage.PYTHON,
            ".pyi": SupportedLanguage.PYTHON,
            ".go": SupportedLanguage.GO,
            ".js": SupportedLanguage.JAVASCRIPT,
            ".mjs": SupportedLanguage.JAVASCRIPT,
            ".cjs": SupportedLanguage.JAVASCRIPT,
            ".ts": SupportedLanguage.TYPESCRIPT,
            ".tsx": SupportedLanguage.TYPESCRIPT,
            ".rs": SupportedLanguage.RUST,
        }
        return suffix_map.get(file_path.suffix.lower(), SupportedLanguage.UNKNOWN)

    async def parse_file(
        self,
        file_path: Path,
        language: SupportedLanguage | None = None,
    ) -> ParseResult:
        """Parse a file asynchronously.

        Uses async I/O for reading, ProcessPoolExecutor for parsing.

        Args:
            file_path: Path to source file
            language: Optional language override (auto-detected if not provided)

        Returns:
            ParseResult with extracted symbols and metadata

        Raises:
            LanguageNotSupportedError: If language cannot be determined
            FileTooLargeError: If file exceeds size limit
        """
        if language is None:
            language = self.detect_language(file_path)

        if language == SupportedLanguage.UNKNOWN:
            raise LanguageNotSupportedError(
                str(file_path.suffix),
                supported=[l.value for l in LanguageRegistry.supported_languages()],
            )

        # Async file read
        try:
            content = await asyncio.to_thread(file_path.read_bytes)
        except FileNotFoundError:
            return ParseResult(
                success=False,
                file_path=str(file_path),
                language=language,
                error=f"File not found: {file_path}",
            )

        # Check file size
        if len(content) > self._max_file_size:
            raise FileTooLargeError(
                str(file_path),
                len(content),
                self._max_file_size,
            )

        # Check cache first
        cached = self._cache.get(content)
        if cached is not None:
            return cached.model_copy(update={"from_cache": True})

        # Parse in process pool (bypasses GIL)
        # Use module-level function to avoid pickling self
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            self._get_executor(),
            _parse_sync,
            file_path,
            content,
            language,
        )

        # Cache result
        self._cache.set(content, result)

        return result

    def parse_bytes(
        self,
        content: bytes,
        language: SupportedLanguage,
        file_path: str = "<string>",
    ) -> ParseResult:
        """Parse bytes synchronously.

        This method is synchronous for direct use without process pool.

        Args:
            content: Raw bytes to parse
            language: Language to use for parsing
            file_path: Virtual file path for context

        Returns:
            ParseResult with extracted symbols
        """
        return _parse_sync(Path(file_path), content, language)

    def get_cache_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        return self._cache.get_stats().to_dict()

    def clear_cache(self) -> int:
        """Clear the parse cache.

        Returns:
            Number of entries cleared
        """
        return self._cache.clear()

    def shutdown(self) -> None:
        """Shutdown process pool executor."""
        if self._executor is not None:
            self._executor.shutdown(wait=True)
            self._executor = None


# Global parser instance (lazy initialization)
_global_parser: TreeSitterParser | None = None


def get_parser() -> TreeSitterParser:
    """Get global parser instance.

    Creates parser on first call, returns cached instance thereafter.
    """
    global _global_parser
    if _global_parser is None:
        _global_parser = TreeSitterParser()
    return _global_parser
