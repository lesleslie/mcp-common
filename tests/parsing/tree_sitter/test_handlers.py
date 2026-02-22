"""Tests for Python language handler.

These tests require tree-sitter and tree-sitter-python to be installed.
"""

from __future__ import annotations

import pytest

from mcp_common.parsing.tree_sitter.handlers.python import PythonHandler
from mcp_common.parsing.tree_sitter.models import SupportedLanguage, SymbolKind

# Skip if dependencies not installed
pytest.importorskip("tree_sitter")
pytest.importorskip("tree_sitter_python")


class TestPythonHandler:
    """Tests for PythonHandler."""

    @pytest.fixture
    def handler(self) -> PythonHandler:
        """Create handler instance."""
        return PythonHandler()

    @pytest.fixture
    def parser(self):
        """Create tree-sitter parser with Python grammar."""
        import tree_sitter_python as tspython
        from tree_sitter import Language, Parser

        language = Language(tspython.language())
        return Parser(language)

    def test_language_attribute(self, handler: PythonHandler) -> None:
        assert handler.language == SupportedLanguage.PYTHON

    def test_extract_simple_function(
        self,
        handler: PythonHandler,
        parser,
    ) -> None:
        code = b'''
def hello(name: str) -> str:
    """Say hello."""
    return f"Hello, {name}!"
'''
        tree = parser.parse(code)
        symbols, relationships, imports = handler.extract(code, tree)

        assert len(symbols) == 1
        assert symbols[0].name == "hello"
        assert symbols[0].kind == SymbolKind.FUNCTION
        assert symbols[0].signature is not None
        assert "def hello" in symbols[0].signature
        assert symbols[0].docstring == "Say hello."
        assert symbols[0].return_type == "str"

    def test_extract_class_with_methods(
        self,
        handler: PythonHandler,
        parser,
    ) -> None:
        code = b'''
class Calculator:
    """A simple calculator."""

    def add(self, a: int, b: int) -> int:
        return a + b

    def multiply(self, a: int, b: int) -> int:
        return a * b
'''
        tree = parser.parse(code)
        symbols, relationships, imports = handler.extract(code, tree)

        # Should have class and methods
        assert len(symbols) >= 3

        class_sym = next(s for s in symbols if s.kind == SymbolKind.CLASS)
        assert class_sym.name == "Calculator"
        assert class_sym.docstring == "A simple calculator."

        method_names = {s.name for s in symbols if s.kind == SymbolKind.METHOD}
        assert "add" in method_names
        assert "multiply" in method_names

    def test_extract_imports(
        self,
        handler: PythonHandler,
        parser,
    ) -> None:
        code = b'''
import os
import sys as system
from pathlib import Path
from typing import List, Dict, Optional
'''
        tree = parser.parse(code)
        symbols, relationships, imports = handler.extract(code, tree)

        # Should extract at least the basic imports
        assert len(imports) >= 2

        os_import = next((i for i in imports if i.module == "os"), None)
        assert os_import is not None

        # Check that we have typing imports
        typing_imports = [i for i in imports if i.module == "typing"]
        assert len(typing_imports) >= 1

    def test_extract_inheritance(
        self,
        handler: PythonHandler,
        parser,
    ) -> None:
        code = b'''
class Animal:
    pass

class Dog(Animal):
    pass

class Cat(Animal):
    pass
'''
        tree = parser.parse(code)
        symbols, relationships, imports = handler.extract(code, tree)

        # Should have extends relationships
        extends_rels = [r for r in relationships if r.relationship_type == "extends"]
        assert len(extends_rels) == 2

        dog_extends = next((r for r in extends_rels if r.from_symbol == "Dog"), None)
        assert dog_extends is not None
        assert dog_extends.to_symbol == "Animal"

    def test_extract_async_function(
        self,
        handler: PythonHandler,
        parser,
    ) -> None:
        code = b'''
async def fetch_data(url: str) -> dict:
    """Fetch data from URL."""
    pass
'''
        tree = parser.parse(code)
        symbols, relationships, imports = handler.extract(code, tree)

        assert len(symbols) == 1
        assert "async" in symbols[0].modifiers

    def test_compute_complexity_simple(
        self,
        handler: PythonHandler,
        parser,
    ) -> None:
        code = b'''
def simple():
    return 1
'''
        tree = parser.parse(code)
        metrics = handler.compute_complexity(code, tree)

        assert "simple" in metrics
        assert metrics["simple"].cyclomatic == 1
        assert metrics["simple"].num_returns == 1

    def test_compute_complexity_with_conditions(
        self,
        handler: PythonHandler,
        parser,
    ) -> None:
        code = b'''
def check_value(x):
    if x > 0:
        return "positive"
    elif x < 0:
        return "negative"
    else:
        return "zero"
'''
        tree = parser.parse(code)
        metrics = handler.compute_complexity(code, tree)

        assert "check_value" in metrics
        # Should have some complexity from conditionals
        assert metrics["check_value"].cyclomatic >= 2

    def test_compute_complexity_with_loops(
        self,
        handler: PythonHandler,
        parser,
    ) -> None:
        code = b'''
def process_items(items):
    result = []
    for item in items:
        if item.valid:
            result.append(item)
    return result
'''
        tree = parser.parse(code)
        metrics = handler.compute_complexity(code, tree)

        assert "process_items" in metrics
        # Should account for for loop and if statement
        assert metrics["process_items"].cyclomatic >= 2
