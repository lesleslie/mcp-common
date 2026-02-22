"""Pydantic models for tree-sitter parsing results."""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class SupportedLanguage(str, Enum):
    """Languages supported by tree-sitter parsing."""

    PYTHON = "python"
    GO = "go"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    RUST = "rust"
    UNKNOWN = "unknown"


class SymbolKind(str, Enum):
    """Types of code symbols that can be extracted."""

    FUNCTION = "function"
    CLASS = "class"
    METHOD = "method"
    VARIABLE = "variable"
    IMPORT = "import"
    CONSTANT = "constant"
    INTERFACE = "interface"
    STRUCT = "struct"
    MODULE = "module"
    PROPERTY = "property"
    ENUM = "enum"
    TRAIT = "trait"


class SymbolInfo(BaseModel):
    """Extracted symbol with full metadata.

    Immutable (frozen=True) for safe caching and concurrency.
    """

    model_config = {"frozen": True}

    name: str
    kind: SymbolKind
    language: SupportedLanguage
    file_path: str
    line_start: int = Field(ge=1)
    line_end: int = Field(ge=1)
    column_start: int = Field(ge=0, default=0)
    column_end: int = Field(ge=0, default=0)
    signature: str | None = None
    docstring: str | None = None
    modifiers: tuple[str, ...] = Field(default_factory=tuple)
    parameters: tuple[dict[str, str], ...] = Field(default_factory=tuple)
    return_type: str | None = None
    parent_context: str | None = None

    @field_validator("line_end")
    @classmethod
    def line_end_gte_start(cls, v: int, info: Any) -> int:
        """Ensure line_end is >= line_start."""
        if "line_start" in info.data and v < info.data["line_start"]:
            raise ValueError("line_end must be >= line_start")
        return v


class SymbolRelationship(BaseModel):
    """Relationship between symbols.

    Used for building code graphs and dependency analysis.
    """

    model_config = {"frozen": True}

    from_symbol: str
    to_symbol: str
    relationship_type: Literal[
        "imports",
        "calls",
        "extends",
        "implements",
        "contains",
        "references",
        "overrides",
        "uses",
    ]
    strength: float = Field(default=1.0, ge=0.0, le=1.0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ComplexityMetrics(BaseModel):
    """Complexity metrics for a code unit.

    Used for code quality analysis and refactoring recommendations.
    """

    model_config = {"frozen": True}

    cyclomatic: int = Field(default=1, ge=1, description="Cyclomatic complexity")
    cognitive: int = Field(default=0, ge=0, description="Cognitive complexity")
    nesting_depth: int = Field(default=0, ge=0, description="Maximum nesting depth")
    lines_of_code: int = Field(default=0, ge=0, description="Lines of code")
    num_parameters: int = Field(default=0, ge=0, description="Number of parameters")
    num_returns: int = Field(default=0, ge=0, description="Number of return statements")


class ImportInfo(BaseModel):
    """Information about an import statement."""

    model_config = {"frozen": True}

    module: str
    alias: str | None = None
    names: tuple[str, ...] = Field(default_factory=tuple)
    is_relative: bool = False
    line: int = Field(ge=1)


class ParseResult(BaseModel):
    """Result of parsing source code.

    Contains all extracted symbols, relationships, and metadata.
    Immutable for safe caching.
    """

    model_config = {"frozen": True}

    success: bool
    file_path: str
    language: SupportedLanguage
    symbols: tuple[SymbolInfo, ...] = Field(default_factory=tuple)
    relationships: tuple[SymbolRelationship, ...] = Field(default_factory=tuple)
    imports: tuple[ImportInfo, ...] = Field(default_factory=tuple)
    complexity: dict[str, ComplexityMetrics] = Field(default_factory=dict)
    parse_time_ms: float = Field(default=0.0, ge=0.0)
    from_cache: bool = False
    error: str | None = None
    error_node_count: int = Field(default=0, ge=0, description="Number of ERROR nodes")

    @property
    def has_errors(self) -> bool:
        """Check if parsing encountered errors."""
        return self.error is not None or self.error_node_count > 0

    @property
    def symbol_count(self) -> int:
        """Get total symbol count."""
        return len(self.symbols)


class QueryMatch(BaseModel):
    """A match from a tree-sitter query."""

    model_config = {"frozen": True}

    pattern_index: int
    captures: dict[str, tuple[str, int, int]]  # name -> (text, start_byte, end_byte)
    start_point: tuple[int, int]  # (row, column)
    end_point: tuple[int, int]  # (row, column)


class QueryResult(BaseModel):
    """Result of a tree-sitter query."""

    model_config = {"frozen": True}

    success: bool
    query: str
    file_path: str
    matches: tuple[QueryMatch, ...] = Field(default_factory=tuple)
    match_count: int = Field(default=0)
    error: str | None = None
