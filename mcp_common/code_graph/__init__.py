"""
Code Graph Analyzer - Shared infrastructure for codebase analysis.

Exports CodeGraphAnalyzer for use by Session Buddy and Mahavishnu.
"""

from .analyzer import (
    ClassNode,
    CodeGraphAnalyzer,
    CodeNode,
    FileNode,
    FunctionNode,
    ImportNode,
)

__all__ = [
    "CodeGraphAnalyzer",
    "CodeNode",
    "FunctionNode",
    "ClassNode",
    "ImportNode",
    "FileNode",
]

__version__ = "0.4.0"
