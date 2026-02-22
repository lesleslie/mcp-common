"""Pre-built tree-sitter queries for common operations.

These queries use tree-sitter's S-expression query syntax.
"""

from __future__ import annotations


# Python queries
PYTHON_QUERIES = {
    # Find all function definitions
    "functions": """
        (function_definition
            name: (identifier) @name
            parameters: (parameters) @params
            return_type: (type)? @return_type)
    """,
    # Find all class definitions
    "classes": """
        (class_definition
            name: (identifier) @name
            superclasses: (argument_list)? @supers)
    """,
    # Find all imports
    "imports": """
        [
            (import_statement
                name: (dotted_name) @module)
            (import_from_statement
                module_name: (dotted_name) @module
                name: (import_list) @names)
        ]
    """,
    # Find function calls
    "calls": """
        (call
            function: (identifier) @name)
    """,
    # Find method calls
    "method_calls": """
        (call
            function: (attribute
                object: (identifier) @object
                attribute: (identifier) @method))
    """,
    # Find decorators
    "decorators": """
        (decorator
            (identifier) @name)
    """,
    # Find docstrings
    "docstrings": """
        (function_definition
            body: (block
                (expression_statement
                    (string) @docstring)))
    """,
    # Find variable assignments (module level)
    "assignments": """
        (module
            (expression_statement
                (assignment
                    left: (identifier) @name)))
    """,
}

# Go queries
GO_QUERIES = {
    # Find function definitions
    "functions": """
        (function_declaration
            name: (field_identifier) @name
            parameters: (parameter_list) @params
            result: (type)? @return_type)
    """,
    # Find method definitions
    "methods": """
        (method_declaration
            receiver: (parameter_list) @receiver
            name: (field_identifier) @name)
    """,
    # Find type declarations
    "types": """
        (type_declaration
            (type_spec
                name: (type_identifier) @name
                type: (type) @type))
    """,
    # Find struct definitions
    "structs": """
        (type_declaration
            (type_spec
                name: (type_identifier) @name
                type: (struct_type
                    (field_declaration_list) @fields)))
    """,
    # Find interface definitions
    "interfaces": """
        (type_declaration
            (type_spec
                name: (type_identifier) @name
                type: (interface_type) @body))
    """,
    # Find imports
    "imports": """
        (import_declaration
            (import_spec
                path: (raw_string_literal) @path))
    """,
}


def get_query(language: str, query_name: str) -> str | None:
    """Get a pre-built query for a language.

    Args:
        language: Language name (python, go)
        query_name: Name of the query

    Returns:
        Query string or None if not found
    """
    queries_map = {
        "python": PYTHON_QUERIES,
        "go": GO_QUERIES,
    }
    queries = queries_map.get(language.lower())
    if queries is None:
        return None
    return queries.get(query_name)


def list_queries(language: str) -> list[str]:
    """List available queries for a language.

    Args:
        language: Language name (python, go)

    Returns:
        List of query names
    """
    queries_map = {
        "python": PYTHON_QUERIES,
        "go": GO_QUERIES,
    }
    queries = queries_map.get(language.lower())
    if queries is None:
        return []
    return list(queries.keys())
