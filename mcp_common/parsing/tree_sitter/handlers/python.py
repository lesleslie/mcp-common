"""Python language handler for tree-sitter.

Extracts symbols, relationships, and complexity metrics from Python source code.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from mcp_common.parsing.tree_sitter.models import (
    ComplexityMetrics,
    ImportInfo,
    SupportedLanguage,
    SymbolInfo,
    SymbolKind,
    SymbolRelationship,
)

if TYPE_CHECKING:
    import tree_sitter


class PythonHandler:
    """Handler for Python source code.

    Extracts:
    - Functions, classes, methods, variables
    - Import statements
    - Class hierarchies (inheritance)
    - Function calls and references
    - Complexity metrics
    """

    language = SupportedLanguage.PYTHON

    def extract(
        self,
        content: bytes,
        tree: tree_sitter.Tree,
    ) -> tuple[
        list[SymbolInfo],
        list[SymbolRelationship],
        list[ImportInfo],
    ]:
        """Extract symbols, relationships, and imports from Python code.

        Args:
            content: Raw source bytes
            tree: Parsed tree-sitter tree

        Returns:
            Tuple of (symbols, relationships, imports)
        """
        symbols: list[SymbolInfo] = []
        relationships: list[SymbolRelationship] = []
        imports: list[ImportInfo] = []
        source = content.decode("utf-8", errors="replace")

        self._extract_from_node(
            tree.root_node,
            source,
            symbols,
            relationships,
            imports,
            parent_context=None,
        )

        return symbols, relationships, imports

    def _extract_from_node(
        self,
        node: tree_sitter.Node,
        source: str,
        symbols: list[SymbolInfo],
        relationships: list[SymbolRelationship],
        imports: list[ImportInfo],
        parent_context: str | None,
    ) -> None:
        """Recursively extract from AST node."""
        node_type = node.type

        if node_type == "function_definition":
            symbol = self._extract_function(node, source, parent_context)
            if symbol:
                symbols.append(symbol)
                # Continue into function body for nested definitions
                for child in node.children:
                    if child.type in ("block", "suite"):
                        self._extract_from_node(
                            child,
                            source,
                            symbols,
                            relationships,
                            imports,
                            symbol.name,
                        )

        elif node_type == "class_definition":
            symbol = self._extract_class(node, source, parent_context)
            if symbol:
                symbols.append(symbol)
                # Extract inheritance relationships
                self._extract_inheritance(node, source, symbol.name, relationships)
                # Continue into class body
                for child in node.children:
                    if child.type == "block":
                        self._extract_from_node(
                            child,
                            source,
                            symbols,
                            relationships,
                            imports,
                            symbol.name,
                        )

        elif node_type == "import_statement":
            imp = self._extract_import(node, source)
            if imp:
                imports.append(imp)

        elif node_type == "import_from_statement":
            imp = self._extract_from_import(node, source)
            if imp:
                imports.append(imp)

        elif node_type == "assignment":
            symbol = self._extract_assignment(node, source, parent_context)
            if symbol:
                symbols.append(symbol)

        elif node_type == "decorated_definition":
            # Handle decorated functions/classes
            for child in node.children:
                if child.type in ("function_definition", "class_definition"):
                    self._extract_from_node(
                        child,
                        source,
                        symbols,
                        relationships,
                        imports,
                        parent_context,
                    )

        else:
            # Recurse into children
            for child in node.children:
                self._extract_from_node(
                    child,
                    source,
                    symbols,
                    relationships,
                    imports,
                    parent_context,
                )

    def _extract_function(
        self,
        node: tree_sitter.Node,
        source: str,
        parent_context: str | None,
    ) -> SymbolInfo | None:
        """Extract function definition."""
        name_node = node.child_by_field_name("name")
        if not name_node:
            return None

        name = self._get_text(name_node, source)
        params_node = node.child_by_field_name("parameters")
        return_node = node.child_by_field_name("return_type")

        # Build signature
        params_text = self._get_text(params_node, source) if params_node else "()"
        return_text = self._get_text(return_node, source) if return_node else None
        signature = f"def {name}{params_text}"
        if return_text:
            signature += f" -> {return_text}"

        # Extract parameters
        parameters = []
        if params_node:
            for child in params_node.children:
                if child.type in ("identifier", "typed_parameter", "default_parameter"):
                    param_text = self._get_text(child, source)
                    param_info: dict[str, str] = {"raw": param_text}
                    if ":" in param_text:
                        parts = param_text.split(":")
                        param_info["name"] = parts[0].strip()
                        param_info["type"] = parts[1].strip()
                    elif "=" in param_text:
                        parts = param_text.split("=")
                        param_info["name"] = parts[0].strip()
                        param_info["default"] = parts[1].strip()
                    else:
                        param_info["name"] = param_text
                    parameters.append(param_info)

        # Determine kind (function or method)
        kind = SymbolKind.METHOD if parent_context else SymbolKind.FUNCTION

        # Extract docstring
        docstring = self._extract_docstring(node, source)

        # Check for async
        modifiers = []
        for child in node.children:
            if child.type == "async":
                modifiers.append("async")

        return SymbolInfo(
            name=name,
            kind=kind,
            language=SupportedLanguage.PYTHON,
            file_path="",  # Set by caller
            line_start=node.start_point[0] + 1,
            line_end=node.end_point[0] + 1,
            column_start=node.start_point[1],
            column_end=node.end_point[1],
            signature=signature,
            docstring=docstring,
            modifiers=tuple(modifiers),
            parameters=tuple(parameters),
            return_type=return_text,
            parent_context=parent_context,
        )

    def _extract_class(
        self,
        node: tree_sitter.Node,
        source: str,
        parent_context: str | None,
    ) -> SymbolInfo | None:
        """Extract class definition."""
        name_node = node.child_by_field_name("name")
        if not name_node:
            return None

        name = self._get_text(name_node, source)

        # Extract docstring
        docstring = self._extract_docstring(node, source)

        return SymbolInfo(
            name=name,
            kind=SymbolKind.CLASS,
            language=SupportedLanguage.PYTHON,
            file_path="",  # Set by caller
            line_start=node.start_point[0] + 1,
            line_end=node.end_point[0] + 1,
            column_start=node.start_point[1],
            column_end=node.end_point[1],
            signature=f"class {name}",
            docstring=docstring,
            parent_context=parent_context,
        )

    def _extract_inheritance(
        self,
        node: tree_sitter.Node,
        source: str,
        class_name: str,
        relationships: list[SymbolRelationship],
    ) -> None:
        """Extract class inheritance relationships."""
        arg_list = node.child_by_field_name("superclasses")
        if not arg_list:
            return

        for child in arg_list.children:
            if child.type in ("identifier", "attribute", "subscript"):
                base_class = self._get_text(child, source)
                relationships.append(
                    SymbolRelationship(
                        from_symbol=class_name,
                        to_symbol=base_class,
                        relationship_type="extends",
                    )
                )

    def _extract_import(self, node: tree_sitter.Node, source: str) -> ImportInfo | None:
        """Extract import statement."""
        names: list[str] = []
        for child in node.children:
            if child.type == "dotted_name":
                names.append(self._get_text(child, source))
            elif child.type == "aliased_import":
                name_node = child.child_by_field_name("name")
                alias_node = child.child_by_field_name("alias")
                if name_node:
                    names.append(self._get_text(name_node, source))

        if not names:
            return None

        return ImportInfo(
            module=names[0],
            names=tuple(names[1:]) if len(names) > 1 else tuple(),
            line=node.start_point[0] + 1,
        )

    def _extract_from_import(
        self,
        node: tree_sitter.Node,
        source: str,
    ) -> ImportInfo | None:
        """Extract from ... import statement."""
        module_name = None
        names: list[str] = []
        found_import_keyword = False

        for child in node.children:
            if child.type == "dotted_name":
                if not found_import_keyword:
                    # First dotted_name is the module
                    module_name = self._get_text(child, source)
                else:
                    # After 'import', these are the imported names
                    names.append(self._get_text(child, source))
            elif child.type == "import":
                found_import_keyword = True
            elif child.type == "wildcard_import":
                names.append("*")
            elif child.type == "import_list":
                for item in child.children:
                    if item.type in ("identifier", "dotted_name"):
                        names.append(self._get_text(item, source))
                    elif item.type == "aliased_import":
                        name_node = item.child_by_field_name("name")
                        if name_node:
                            names.append(self._get_text(name_node, source))
            elif child.type == "aliased_import" and found_import_keyword:
                # Handle aliased imports like 'from x import y as z'
                name_node = child.child_by_field_name("name")
                if name_node:
                    names.append(self._get_text(name_node, source))

        if not module_name:
            return None

        return ImportInfo(
            module=module_name,
            names=tuple(names),
            line=node.start_point[0] + 1,
        )

    def _extract_assignment(
        self,
        node: tree_sitter.Node,
        source: str,
        parent_context: str | None,
    ) -> SymbolInfo | None:
        """Extract variable assignment (module/class level constants)."""
        left = node.child_by_field_name("left")
        if not left or left.type != "identifier":
            return None

        name = self._get_text(left, source)

        # Check if it's a constant (ALL_CAPS) at module level
        if not parent_context and name.isupper():
            kind = SymbolKind.CONSTANT
        else:
            kind = SymbolKind.VARIABLE

        return SymbolInfo(
            name=name,
            kind=kind,
            language=SupportedLanguage.PYTHON,
            file_path="",  # Set by caller
            line_start=node.start_point[0] + 1,
            line_end=node.end_point[0] + 1,
            column_start=node.start_point[1],
            column_end=node.end_point[1],
            parent_context=parent_context,
        )

    def _extract_docstring(self, node: tree_sitter.Node, source: str) -> str | None:
        """Extract docstring from function/class body."""
        body = node.child_by_field_name("body")
        if not body:
            return None

        for child in body.children:
            if child.type == "expression_statement":
                for expr_child in child.children:
                    if expr_child.type == "string":
                        docstring = self._get_text(expr_child, source)
                        # Remove quotes
                        if docstring.startswith(('"""', "'''")):
                            docstring = docstring[3:-3]
                        elif docstring.startswith(('"', "'")):
                            docstring = docstring[1:-1]
                        return docstring.strip()

        return None

    def _get_text(self, node: tree_sitter.Node, source: str) -> str:
        """Get text content of node."""
        return source[node.start_byte : node.end_byte]

    def compute_complexity(
        self,
        content: bytes,
        tree: tree_sitter.Tree,
    ) -> dict[str, ComplexityMetrics]:
        """Compute complexity metrics for functions and methods.

        Calculates:
        - Cyclomatic complexity (decision points + 1)
        - Cognitive complexity (nested structures weighted)
        - Nesting depth
        - Lines of code
        - Parameter count
        """
        metrics: dict[str, ComplexityMetrics] = {}
        source = content.decode("utf-8", errors="replace")

        self._compute_complexity_for_node(tree.root_node, source, metrics)

        return metrics

    def _compute_complexity_for_node(
        self,
        node: tree_sitter.Node,
        source: str,
        metrics: dict[str, ComplexityMetrics],
        depth: int = 0,
    ) -> None:
        """Recursively compute complexity for functions."""
        if node.type == "function_definition":
            name_node = node.child_by_field_name("name")
            if name_node:
                name = self._get_text(name_node, source)
                metrics[name] = self._calculate_function_complexity(node, source)

        elif node.type == "decorated_definition":
            # Handle decorated functions
            for child in node.children:
                if child.type == "function_definition":
                    name_node = child.child_by_field_name("name")
                    if name_node:
                        name = self._get_text(name_node, source)
                        metrics[name] = self._calculate_function_complexity(child, source)

        # Recurse into children
        for child in node.children:
            self._compute_complexity_for_node(child, source, metrics, depth + 1)

    def _calculate_function_complexity(
        self,
        node: tree_sitter.Node,
        source: str,
    ) -> ComplexityMetrics:
        """Calculate complexity for a single function."""
        cyclomatic = 1  # Base complexity
        cognitive = 0
        max_nesting = 0
        num_returns = 0
        num_params = 0

        # Count parameters
        params_node = node.child_by_field_name("parameters")
        if params_node:
            for child in params_node.children:
                if child.type in ("identifier", "typed_parameter", "default_parameter"):
                    num_params += 1

        # Analyze body
        body = node.child_by_field_name("body")
        if body:
            cyclo_add, cognitive, max_nesting, num_returns = self._analyze_complexity(
                body,
                source,
                depth=0,
            )
            cyclomatic += cyclo_add  # Add to base complexity of 1

        # Count lines
        lines = source[node.start_byte : node.end_byte].count("\n") + 1

        return ComplexityMetrics(
            cyclomatic=cyclomatic,
            cognitive=cognitive,
            nesting_depth=max_nesting,
            lines_of_code=lines,
            num_parameters=num_params,
            num_returns=num_returns,
        )

    def _analyze_complexity(
        self,
        node: tree_sitter.Node,
        source: str,
        depth: int,
    ) -> tuple[int, int, int, int]:
        """Analyze complexity of a code block.

        Returns (cyclomatic_additions, cognitive, max_nesting, returns).
        """
        cyclomatic = 0
        cognitive = 0
        max_nesting = depth
        returns = 0

        # Decision points that add cyclomatic complexity
        decision_types = {
            "if_statement": 1,
            "elif_clause": 1,
            "for_statement": 1,
            "while_statement": 1,
            "try_statement": 1,
            "except_clause": 1,
            "with_statement": 1,
            "assert_statement": 1,
            "boolean_operator": 1,  # and/or
            "conditional_expression": 1,  # ternary
        }

        if node.type == "return_statement":
            returns = 1

        if node.type in decision_types:
            cyclomatic += decision_types[node.type]
            # Cognitive complexity increases with nesting
            if depth > 0:
                cognitive += depth

        # Check for boolean operators (and/or)
        if node.type == "boolean_operator":
            cyclomatic += 1

        # Recurse into children
        for child in node.children:
            child_cyclo, child_cog, child_nesting, child_returns = self._analyze_complexity(
                child,
                source,
                depth + 1 if node.type in decision_types else depth,
            )
            cyclomatic += child_cyclo
            cognitive += child_cog
            max_nesting = max(max_nesting, child_nesting)
            returns += child_returns

        return cyclomatic, cognitive, max_nesting, returns
