"""Language handlers for tree-sitter parsing.

Each handler implements the LanguageHandler protocol for a specific language.
"""

from __future__ import annotations

from mcp_common.parsing.tree_sitter.handlers.python import PythonHandler

__all__ = [
    "PythonHandler",
]
