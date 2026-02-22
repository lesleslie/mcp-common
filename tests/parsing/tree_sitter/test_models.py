"""Tests for tree-sitter models."""

from __future__ import annotations

import pytest

from mcp_common.parsing.tree_sitter.models import (
    ComplexityMetrics,
    ImportInfo,
    ParseResult,
    SymbolInfo,
    SymbolKind,
    SymbolRelationship,
    SupportedLanguage,
)


class TestSupportedLanguage:
    """Tests for SupportedLanguage enum."""

    def test_python_value(self) -> None:
        assert SupportedLanguage.PYTHON.value == "python"

    def test_go_value(self) -> None:
        assert SupportedLanguage.GO.value == "go"

    def test_unknown_value(self) -> None:
        assert SupportedLanguage.UNKNOWN.value == "unknown"


class TestSymbolInfo:
    """Tests for SymbolInfo model."""

    def test_minimal_symbol(self) -> None:
        symbol = SymbolInfo(
            name="foo",
            kind=SymbolKind.FUNCTION,
            language=SupportedLanguage.PYTHON,
            file_path="test.py",
            line_start=1,
            line_end=5,
        )
        assert symbol.name == "foo"
        assert symbol.kind == SymbolKind.FUNCTION
        assert symbol.language == SupportedLanguage.PYTHON
        assert symbol.line_start == 1
        assert symbol.line_end == 5
        assert symbol.signature is None
        assert symbol.docstring is None
        assert symbol.modifiers == ()
        assert symbol.parameters == ()

    def test_full_symbol(self) -> None:
        symbol = SymbolInfo(
            name="add",
            kind=SymbolKind.FUNCTION,
            language=SupportedLanguage.PYTHON,
            file_path="math.py",
            line_start=10,
            line_end=15,
            column_start=0,
            column_end=20,
            signature="def add(a: int, b: int) -> int",
            docstring="Add two numbers.",
            modifiers=("async",),
            parameters=({"name": "a", "type": "int"}, {"name": "b", "type": "int"}),
            return_type="int",
            parent_context="Calculator",
        )
        assert symbol.name == "add"
        assert symbol.signature == "def add(a: int, b: int) -> int"
        assert symbol.modifiers == ("async",)
        assert len(symbol.parameters) == 2

    def test_frozen_model(self) -> None:
        symbol = SymbolInfo(
            name="foo",
            kind=SymbolKind.FUNCTION,
            language=SupportedLanguage.PYTHON,
            file_path="test.py",
            line_start=1,
            line_end=5,
        )
        with pytest.raises(Exception):  # Pydantic generates FrozenInstanceError
            symbol.name = "bar"

    def test_line_end_validation(self) -> None:
        with pytest.raises(ValueError, match="line_end must be >= line_start"):
            SymbolInfo(
                name="foo",
                kind=SymbolKind.FUNCTION,
                language=SupportedLanguage.PYTHON,
                file_path="test.py",
                line_start=10,
                line_end=5,  # Invalid: less than line_start
            )

    def test_valid_line_end(self) -> None:
        symbol = SymbolInfo(
            name="foo",
            kind=SymbolKind.FUNCTION,
            language=SupportedLanguage.PYTHON,
            file_path="test.py",
            line_start=1,
            line_end=1,
        )
        assert symbol.line_end == 1


class TestSymbolRelationship:
    """Tests for SymbolRelationship model."""

    def test_imports_relationship(self) -> None:
        rel = SymbolRelationship(
            from_symbol="module_a",
            to_symbol="module_b",
            relationship_type="imports",
        )
        assert rel.from_symbol == "module_a"
        assert rel.to_symbol == "module_b"
        assert rel.relationship_type == "imports"
        assert rel.strength == 1.0

    def test_strength_validation(self) -> None:
        rel = SymbolRelationship(
            from_symbol="a",
            to_symbol="b",
            relationship_type="calls",
            strength=0.5,
        )
        assert rel.strength == 0.5


class TestComplexityMetrics:
    """Tests for ComplexityMetrics model."""

    def test_default_metrics(self) -> None:
        metrics = ComplexityMetrics()
        assert metrics.cyclomatic == 1
        assert metrics.cognitive == 0
        assert metrics.nesting_depth == 0
        assert metrics.lines_of_code == 0

    def test_custom_metrics(self) -> None:
        metrics = ComplexityMetrics(
            cyclomatic=10,
            cognitive=15,
            nesting_depth=4,
            lines_of_code=50,
            num_parameters=5,
            num_returns=3,
        )
        assert metrics.cyclomatic == 10
        assert metrics.cognitive == 15
        assert metrics.nesting_depth == 4


class TestImportInfo:
    """Tests for ImportInfo model."""

    def test_simple_import(self) -> None:
        imp = ImportInfo(module="os", line=1)
        assert imp.module == "os"
        assert imp.alias is None
        assert imp.names == ()
        assert imp.is_relative is False

    def test_from_import(self) -> None:
        imp = ImportInfo(
            module="typing",
            names=("List", "Dict", "Optional"),
            line=5,
        )
        assert imp.module == "typing"
        assert imp.names == ("List", "Dict", "Optional")


class TestParseResult:
    """Tests for ParseResult model."""

    def test_success_result(self) -> None:
        result = ParseResult(
            success=True,
            file_path="test.py",
            language=SupportedLanguage.PYTHON,
            symbols=(
                SymbolInfo(
                    name="foo",
                    kind=SymbolKind.FUNCTION,
                    language=SupportedLanguage.PYTHON,
                    file_path="test.py",
                    line_start=1,
                    line_end=5,
                ),
            ),
            parse_time_ms=10.5,
        )
        assert result.success
        assert result.symbol_count == 1
        assert not result.has_errors
        assert result.from_cache is False

    def test_error_result(self) -> None:
        result = ParseResult(
            success=False,
            file_path="test.py",
            language=SupportedLanguage.PYTHON,
            error="Parse error",
            error_node_count=2,
        )
        assert not result.success
        assert result.has_errors
        assert result.error == "Parse error"

    def test_from_cache_flag(self) -> None:
        result = ParseResult(
            success=True,
            file_path="test.py",
            language=SupportedLanguage.PYTHON,
            from_cache=True,
        )
        assert result.from_cache
