"""LLM-Friendly API Response Models.

This module provides Pydantic models for creating MCP tool responses that are
optimized for LLM consumption, following the LLM-Friendly API Design pattern
from awesome-agentic-patterns.

The key principles are:
1. Structured output with clear field descriptions
2. Self-documenting error messages
3. Suggested follow-up actions
4. Consistent schema for all tools

Example:
    >>> from mcp_common.schemas import ToolResponse, ToolInput
    >>>
    >>> # In an MCP tool
    >>> @mcp.tool()
    >>> async def my_tool(param: str) -> ToolResponse:
    >>>     result = do_something(param)
    >>>     return ToolResponse(
    >>>         success=True,
    >>>         message="Operation completed successfully",
    >>>         data={"result": result},
    >>>         next_steps=["Verify the result", "Check logs"]
    >>>     )
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


def _encode_set(v: Any) -> list[Any]:
    """Encoder for set objects to convert them to sorted lists."""
    return sorted(v) if isinstance(v, set) else list(v)


class ToolResponse(BaseModel):
    """Standardized LLM-friendly tool response following the Dual-Use pattern.

    This model provides a consistent structure for all MCP tool outputs, making
    it easier for LLMs to understand and process tool results.

    Attributes:
        success: Whether the operation succeeded
        message: Human-readable result message (self-documenting)
        data: Structured output data (for agent consumption)
        error: Error details if failed (helpful debugging info)
        next_steps: Suggested follow-up actions (guides agent behavior)

    Example:
        >>> # Successful operation
        >>> ToolResponse(
        ...     success=True,
        ...     message="Created 3 new records",
        ...     data={"records": [...]},
        ...     next_steps=["Verify records in database", "Check for duplicates"]
        ... )
        >>>
        >>> # Failed operation
        >>> ToolResponse(
        ...     success=False,
        ...     message="Failed to create records",
        ...     error="Database connection timeout after 30s",
        ...     next_steps=["Check database connectivity", "Retry with timeout=60"]
        ... )
    """

    success: bool = Field(description="Whether the operation succeeded (true/false)")
    message: str = Field(
        description="Human-readable result message explaining what happened"
    )
    data: dict[str, Any] | None = Field(
        default=None,
        description="Structured output data for agent consumption (results, metrics, etc.)",
    )
    error: str | None = Field(
        default=None,
        description="Error details if operation failed (helpful debugging information)",
    )
    next_steps: list[str] | None = Field(
        default=None,
        description="Suggested follow-up actions for the agent to take next",
    )

    model_config = {
        "json_encoders": {  # Proper Pydantic v2 syntax
            set: _encode_set
        },
        "json_schema_extra": {
            "examples": [
                {
                    "success": True,
                    "message": "Successfully created 3 user records",
                    "data": {
                        "records": [
                            {"id": "1", "name": "Alice"},
                            {"id": "2", "name": "Bob"},
                            {"id": "3", "name": "Charlie"},
                        ]
                    },
                    "error": None,
                    "next_steps": [
                        "Verify records in database",
                        "Send confirmation emails",
                    ],
                },
                {
                    "success": False,
                    "message": "Failed to connect to database",
                    "data": None,
                    "error": "Connection timeout after 30s - check database connectivity",
                    "next_steps": [
                        "Check database status",
                        "Verify network connectivity",
                        "Retry with increased timeout",
                    ],
                },
            ]
        },
    }


class ToolInput(BaseModel):
    """Standardized LLM-friendly tool input schema.

    This model provides a consistent structure for defining tool inputs, making it
    easier for LLMs to understand how to use tools correctly.

    The to_example() method generates usage examples for LLM prompting.

    Attributes:
        name: Tool name (snake_case)
        description: Clear description of what the tool does
        parameters: JSON Schema of parameters
        example: Example usage with realistic values

    Example:
        >>> ToolInput(
        ...     name="search_users",
        ...     description="Search for users by name or email",
        ...     parameters={
        ...         "type": "object",
        ...         "properties": {
        ...             "query": {
        ...                 "type": "string",
        ...                 "description": "Search query (name or email)"
        ...             }
        ...         },
        ...         "required": ["query"]
        ...     },
        ...     example={"query": "alice@example.com"}
        ... )
    """

    name: str = Field(description="Tool name (snake_case)")
    description: str = Field(
        description="Clear description of what the tool does and when to use it"
    )
    parameters: dict[str, Any] = Field(
        description="JSON Schema of tool parameters (types, required fields, descriptions)"
    )
    example: dict[str, Any] = Field(
        description="Example usage with realistic values for LLM prompting"
    )

    def to_example(self) -> dict[str, Any]:
        """Generate formatted example for LLM prompting.

        Returns:
            Dictionary with description, parameters, and example

        Example:
            >>> input_schema = ToolInput(...)
            >>> example = input_schema.to_example()
            >>> print(example)
            {
                "description": "Search for users...",
                "parameters": {...},
                "example": {"query": "..."}
            }
        """
        return {
            "description": self.description,
            "parameters": self.parameters,
            "example": self.example,
        }

    model_config = {"json_encoders": {set: _encode_set}}


__all__ = ["ToolResponse", "ToolInput"]
