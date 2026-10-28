"""
Code Graph Analyzer - Shared infrastructure for codebase analysis.

Exports CodeGraphAnalyzer for use by Session Buddy and Mahavishnu.
"""

from mcp_common._version import __version__

from .analyzer import (
    ClassNode,
    CodeGraphAnalyzer,
    CodeNode,
    FileNode,
    FunctionNode,
    ImportNode,
)

__all__ = [
    "ClassNode",
    "CodeGraphAnalyzer",
    "CodeNode",
    "FileNode",
    "FunctionNode",
    "ImportNode",
    "__version__",
]
