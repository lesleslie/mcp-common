"""Tests for tree-sitter core parser.

These tests require tree-sitter to be installed.
Run with: pytest tests/parsing/tree_sitter/test_core.py -v
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from mcp_common.parsing.tree_sitter import (
    ContentHashLRUCache,
    SupportedLanguage,
    TreeSitterParser,
)

# Skip all tests in this module if tree-sitter is not installed
pytest.importorskip("tree_sitter")


class TestTreeSitterParser:
    """Tests for TreeSitterParser."""

    @pytest.fixture
    def parser(self) -> TreeSitterParser:
        """Create parser instance."""
        return TreeSitterParser()

    def test_detect_language_python(self, parser: TreeSitterParser) -> None:
        assert parser.detect_language(Path("test.py")) == SupportedLanguage.PYTHON
        assert parser.detect_language(Path("test.pyi")) == SupportedLanguage.PYTHON

    def test_detect_language_go(self, parser: TreeSitterParser) -> None:
        assert parser.detect_language(Path("main.go")) == SupportedLanguage.GO

    def test_detect_language_javascript(self, parser: TreeSitterParser) -> None:
        assert parser.detect_language(Path("app.js")) == SupportedLanguage.JAVASCRIPT
        assert parser.detect_language(Path("app.mjs")) == SupportedLanguage.JAVASCRIPT

    def test_detect_language_typescript(self, parser: TreeSitterParser) -> None:
        assert parser.detect_language(Path("app.ts")) == SupportedLanguage.TYPESCRIPT
        assert parser.detect_language(Path("component.tsx")) == SupportedLanguage.TYPESCRIPT

    def test_detect_language_rust(self, parser: TreeSitterParser) -> None:
        assert parser.detect_language(Path("main.rs")) == SupportedLanguage.RUST

    def test_detect_language_unknown(self, parser: TreeSitterParser) -> None:
        assert parser.detect_language(Path("README.md")) == SupportedLanguage.UNKNOWN
        assert parser.detect_language(Path("config.yaml")) == SupportedLanguage.UNKNOWN

    @pytest.mark.asyncio
    async def test_parse_file_not_found(self, parser: TreeSitterParser) -> None:
        result = await parser.parse_file(Path("/nonexistent/file.py"))

        assert not result.success
        assert "File not found" in result.error

    @pytest.mark.asyncio
    async def test_parse_unsupported_language(self, parser: TreeSitterParser) -> None:
        with tempfile.NamedTemporaryFile(suffix=".md", delete=False) as f:
            f.write(b"# Markdown content")
            f.flush()

            with pytest.raises(Exception) as exc_info:
                await parser.parse_file(Path(f.name))

            assert "not supported" in str(exc_info.value).lower()

    def test_get_cache_stats(self, parser: TreeSitterParser) -> None:
        stats = parser.get_cache_stats()

        assert "hits" in stats
        assert "misses" in stats
        assert "hit_rate" in stats

    def test_clear_cache(self, parser: TreeSitterParser) -> None:
        count = parser.clear_cache()
        assert isinstance(count, int)

    def test_shutdown(self, parser: TreeSitterParser) -> None:
        # Should not raise
        parser.shutdown()


class TestTreeSitterParserWithGrammar:
    """Tests that require grammars to be loaded."""

    @pytest.fixture
    def parser_with_grammar(self) -> TreeSitterParser:
        """Create parser and load Python grammar."""
        parser = TreeSitterParser()

        # Load Python grammar
        from mcp_common.parsing.tree_sitter.grammars import load_python_grammar

        load_python_grammar()

        return parser

    @pytest.mark.asyncio
    async def test_parse_python_file(
        self,
        parser_with_grammar: TreeSitterParser,
    ) -> None:
        """Test parsing a Python file."""
        code = '''
def hello(name: str) -> str:
    """Say hello."""
    return f"Hello, {name}!"

class Greeter:
    def __init__(self, greeting: str):
        self.greeting = greeting

    def greet(self, name: str) -> str:
        return f"{self.greeting}, {name}!"
'''.encode()

        with tempfile.NamedTemporaryFile(suffix=".py", delete=False) as f:
            f.write(code)
            f.flush()

            result = await parser_with_grammar.parse_file(Path(f.name))

            assert result.success
            assert result.language == SupportedLanguage.PYTHON
            assert len(result.symbols) >= 2  # At least hello function and Greeter class

    @pytest.mark.asyncio
    async def test_parse_with_cache(
        self,
        parser_with_grammar: TreeSitterParser,
    ) -> None:
        """Test that caching works."""
        code = b"def foo(): pass"

        with tempfile.NamedTemporaryFile(suffix=".py", delete=False) as f:
            f.write(code)
            f.flush()

            # First parse
            result1 = await parser_with_grammar.parse_file(Path(f.name))
            assert not result1.from_cache

            # Second parse (should be cached)
            result2 = await parser_with_grammar.parse_file(Path(f.name))
            assert result2.from_cache
