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


class _FakeNode:
    def __init__(
        self,
        node_type: str,
        *,
        children: list[_FakeNode] | None = None,
        fields: dict[str, _FakeNode | None] | None = None,
        text: str = "",
        start_byte: int = 0,
        end_byte: int | None = None,
        start_point: tuple[int, int] = (0, 0),
        end_point: tuple[int, int] = (0, 0),
    ) -> None:
        self.type = node_type
        self.children = children or []
        self._fields = fields or {}
        self.text = text
        self.start_byte = start_byte
        self.end_byte = len(text) if end_byte is None else end_byte
        self.start_point = start_point
        self.end_point = end_point

    def child_by_field_name(self, name: str) -> _FakeNode | None:
        return self._fields.get(name)


class _FakeTree:
    def __init__(self, root_node: _FakeNode) -> None:
        self.root_node = root_node


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

    def test_extract_decorated_function_and_nested_definitions(
        self,
        handler: PythonHandler,
        parser,
    ) -> None:
        code = b'''
@decorator
def outer(x: int):
    """Outer docstring."""
    total = 0

    def inner(y: int):
        return x and y

    return inner(total)
'''
        tree = parser.parse(code)
        symbols, relationships, imports = handler.extract(code, tree)
        metrics = handler.compute_complexity(code, tree)

        names = {symbol.name for symbol in symbols}
        assert "outer" in names
        assert "inner" in names
        outer = next(symbol for symbol in symbols if symbol.name == "outer")
        inner = next(symbol for symbol in symbols if symbol.name == "inner")
        assert outer.docstring == "Outer docstring."
        assert inner.kind == SymbolKind.METHOD
        assert any(symbol.kind == SymbolKind.VARIABLE for symbol in symbols)
        assert metrics["outer"].cyclomatic >= 2
        assert metrics["inner"].cyclomatic >= 1

    def test_extract_import_aliases_wildcards_and_assignments(
        self,
        handler: PythonHandler,
        parser,
    ) -> None:
        code = b'''
import os as operating_system
from math import *
from collections import deque as dq, Counter

CONSTANT_VALUE = 10
mutable_value = 20

class Config:
    CLASS_VALUE = 30
'''
        tree = parser.parse(code)
        symbols, relationships, imports = handler.extract(code, tree)

        import_modules = {imp.module for imp in imports}
        assert "os" in import_modules
        assert "math" in import_modules
        assert "collections" in import_modules

        math_import = next(imp for imp in imports if imp.module == "math")
        collections_import = next(imp for imp in imports if imp.module == "collections")
        assert "*" in math_import.names
        assert "deque" in collections_import.names
        assert "Counter" in collections_import.names

        constants = {symbol.name for symbol in symbols if symbol.kind == SymbolKind.CONSTANT}
        variables = {symbol.name for symbol in symbols if symbol.kind == SymbolKind.VARIABLE}
        assert "CONSTANT_VALUE" in constants
        assert "mutable_value" in variables
        assert "CLASS_VALUE" in variables

    def test_extract_default_parameter_and_single_alias_import(
        self,
        handler: PythonHandler,
        parser,
    ) -> None:
        code = b'''
from collections import deque as dq

def configure(level="debug"):
    return level
'''
        tree = parser.parse(code)
        symbols, relationships, imports = handler.extract(code, tree)

        assert any(imp.module == "collections" and "deque" in imp.names for imp in imports)
        configure = next(symbol for symbol in symbols if symbol.name == "configure")
        assert configure.parameters
        assert configure.parameters[0]["default"] == '"debug"'

    def test_compute_complexity_with_nested_control_flow(
        self,
        handler: PythonHandler,
        parser,
    ) -> None:
        code = b'''
def complex_logic(items, enabled):
    assert items
    total = 0

    with open("/tmp/data.txt") as handle:
        for item in items:
            while total < 3:
                if enabled and item:
                    total += 1 if item else 0
                try:
                    total += 1
                except ValueError:
                    total += 2

    return total
'''
        tree = parser.parse(code)
        metrics = handler.compute_complexity(code, tree)

        assert "complex_logic" in metrics
        assert metrics["complex_logic"].cyclomatic >= 8
        assert metrics["complex_logic"].num_returns == 1
        assert metrics["complex_logic"].cognitive > 0

    def test_private_extractors_handle_missing_fields(self, handler: PythonHandler) -> None:
        source = "def x():\n    pass\n"

        assert handler._extract_function(_FakeNode("function_definition"), source, None) is None
        assert handler._extract_class(_FakeNode("class_definition"), source, None) is None
        assert handler._extract_import(_FakeNode("import_statement"), source) is None
        assert (
            handler._extract_from_import(_FakeNode("import_from_statement"), source) is None
        )
        assert handler._extract_assignment(_FakeNode("assignment"), source, None) is None
        assert handler._extract_docstring(_FakeNode("function_definition"), source) is None

    def test_private_extractors_cover_alias_and_module_branches(self, handler: PythonHandler) -> None:
        source = "from pkg import thing as alias\n"

        aliased_import = _FakeNode(
            "aliased_import",
            fields={"name": _FakeNode("identifier", text="thing", start_byte=16, end_byte=21)},
        )
        import_node = _FakeNode(
            "import_from_statement",
            children=[
                _FakeNode("dotted_name", text="pkg", start_byte=5, end_byte=8),
                _FakeNode("import"),
                aliased_import,
            ],
            start_point=(0, 0),
        )
        imported = handler._extract_from_import(import_node, source)

        assert imported is not None
        assert imported.module == "pkg"
        assert imported.names == ("thing",)

        import_only_node = _FakeNode(
            "import_statement",
            children=[_FakeNode("aliased_import", fields={})],
            start_point=(0, 0),
        )
        assert handler._extract_import(import_only_node, source) is None

    def test_private_extractors_cover_import_list_and_single_quote_docstring(
        self,
        handler: PythonHandler,
    ) -> None:
        source = "from pkg import thing as alias\n\ndef single_quote():\n    'Doc'\n    return 1\n"

        import_list = _FakeNode(
            "import_list",
            children=[
                _FakeNode("identifier", text="thing", start_byte=16, end_byte=21),
                _FakeNode(
                    "aliased_import",
                    fields={"name": _FakeNode("identifier", text="alias", start_byte=25, end_byte=30)},
                ),
            ],
        )
        import_node = _FakeNode(
            "import_from_statement",
            children=[
                _FakeNode("dotted_name", text="pkg", start_byte=5, end_byte=8),
                _FakeNode("import"),
                import_list,
            ],
            start_point=(0, 0),
        )
        imported = handler._extract_from_import(import_node, source)

        assert imported is not None
        assert imported.module == "pkg"
        assert imported.names == ("thing", "alias")

        doc_start = source.index("'Doc'")
        func_node = _FakeNode(
            "function_definition",
            fields={
                "body": _FakeNode(
                    "block",
                    children=[
                        _FakeNode(
                            "expression_statement",
                            children=[
                                _FakeNode(
                                    "string",
                                    text="'Doc'",
                                    start_byte=doc_start,
                                    end_byte=doc_start + 5,
                                )
                            ],
                        )
                    ],
                )
            },
            start_byte=0,
            end_byte=len(source),
        )
        assert handler._extract_docstring(func_node, source) == "Doc"
