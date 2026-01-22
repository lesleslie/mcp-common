"""Structured Output Validation Utilities.

This module provides validation utilities for ensuring MCP tool outputs conform
to expected schemas, following the Structured Output Specification pattern from
awesome-agentic-patterns.

The key benefit is catching schema violations early with clear error messages,
making debugging easier for both humans and agents.

Example:
    >>> from mcp_common.schemas import ToolResponse
    >>> from mcp_common.validation import validate_output
    >>>
    >>> # Validate tool output against schema
    >>> output = {"success": True, "message": "Done", "data": {...}}
    >>> validated = validate_output(output, ToolResponse)
"""

from __future__ import annotations

import json
from typing import TypeVar

from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)


def validate_output(output: dict[str, object], schema: type[T]) -> T:  # noqa: UP047
    """Validate tool output against a Pydantic schema.

    This function ensures that tool outputs conform to expected schemas, catching
    type mismatches, missing fields, and validation errors early with clear
    error messages.

    Args:
        output: Raw tool output as dictionary (from MCP tool execution)
        schema: Pydantic model class to validate against (e.g., ToolResponse)

    Returns:
        Validated and parsed schema instance

    Raises:
        ValueError: If validation fails with detailed error context

    Example:
        >>> from mcp_common.schemas import ToolResponse
        >>>
        >>> # Valid output
        >>> output = {"success": True, "message": "Success"}
        >>> validated = validate_output(output, ToolResponse)
        >>> assert validated.success is True
        >>>
        >>> # Invalid output (missing required field)
        >>> output = {"data": {...}}  # Missing 'success' and 'message'
        >>> try:
        ...     validated = validate_output(output, ToolResponse)
        >>> except ValueError as e:
        ...     print(f"Validation failed: {e}")
    """
    try:
        return schema(**output)
    except ValidationError as e:
        # Create helpful error message with context
        error_lines = [
            f"Tool output validation failed for schema '{schema.__name__}':",
            "",
            "Received output:",
            f"  {output}",
            "",
            "Validation errors:",
        ]

        # Format each validation error
        for error in e.errors():
            loc = " -> ".join(str(part) for part in error["loc"])
            error_lines.append(f"  - {loc}: {error['msg']}")

        # Add expected schema info
        import json

        error_lines.extend(
            [
                "",
                "Expected schema:",
                f"  {json.dumps(schema.model_json_schema(), indent=2)}",
            ]
        )

        raise ValueError("\n".join(error_lines)) from e


def validate_input(input_data: dict[str, object], schema: type[T]) -> T:  # noqa: UP047
    """Validate tool input against a Pydantic schema.

    Similar to validate_output but for input validation. Use this when tools
    receive parameters that need validation before processing.

    Args:
        input_data: Raw tool input as dictionary (from MCP protocol)
        schema: Pydantic model class to validate against

    Returns:
        Validated and parsed schema instance

    Raises:
        ValueError: If validation fails with detailed error context

    Example:
        >>> from pydantic import BaseModel, Field
        >>>
        >>> class SearchInput(BaseModel):
        ...     query: str = Field(..., min_length=1)
        ...     limit: int = Field(default=10, ge=1, le=100)
        >>>
        >>> # Valid input
        >>> input_data = {"query": "alice", "limit": 5}
        >>> validated = validate_input(input_data, SearchInput)
        >>>
        >>> # Invalid input
        >>> input_data = {"query": "", "limit": 200}
        >>> try:
        ...     validated = validate_input(input_data, SearchInput)
        >>> except ValueError as e:
        ...     print(f"Validation failed: {e}")
    """
    try:
        return schema(**input_data)
    except ValidationError as e:
        # Create helpful error message
        error_lines = [
            f"Tool input validation failed for schema '{schema.__name__}':",
            "",
            "Received input:",
            f"  {input_data}",
            "",
            "Validation errors:",
        ]

        for error in e.errors():
            loc = " -> ".join(str(part) for part in error["loc"])
            error_lines.append(f"  - {loc}: {error['msg']}")

        error_lines.extend(
            [
                "",
                "Expected schema:",
                f"  {json.dumps(schema.model_json_schema(), indent=2)}",
            ]
        )

        raise ValueError("\n".join(error_lines)) from e


__all__ = ["validate_output", "validate_input"]
