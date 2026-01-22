"""Dual-Use Tool Interfaces for MCP Servers.

This module provides protocols and utilities for creating tools that work seamlessly
via both CLI and MCP interfaces, following the Dual-Use Tool Design pattern from
awesome-agentic-patterns.

The key insight is that tools should be designed for both human interaction (CLI)
and agent interaction (MCP protocol) without duplication or inconsistency.

Example:
    @ensure_dual_use
    class MyTool:
        @staticmethod
        def cli(args: list[str]) -> str:
            return "CLI output"

        @staticmethod
        async def mcp(**kwargs) -> dict:
            return {"success": True, "message": "MCP output"}
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class DualUseTool(Protocol):
    """Protocol for tools that work via both CLI and MCP interfaces.

    A dual-use tool implements two execution methods:
    - cli(args: list[str]) -> str: For human interaction via command-line
    - mcp(**kwargs) -> dict: For agent interaction via MCP protocol

    Both methods should produce equivalent results, just formatted appropriately
    for their target audience (humans vs. agents).

    Example:
        class SearchTool:
            @staticmethod
            def cli(args: list[str]) -> str:
                query = " ".join(args)
                results = search(query)
                return format_for_human(results)

            @staticmethod
            async def mcp(**kwargs) -> dict:
                query = kwargs.get("query", "")
                results = search(query)
                return format_for_agent(results)
    """

    @staticmethod
    def cli(args: list[str]) -> str:
        """Execute tool via command-line interface for human users.

        Args:
            args: Command-line arguments (already parsed by shell)

        Returns:
            Human-readable string output
        """
        ...

    @staticmethod
    async def mcp(**kwargs: Any) -> dict[str, Any]:
        """Execute tool via MCP interface for AI agents.

        Args:
            **kwargs: Tool parameters from MCP protocol

        Returns:
            Structured dict following ToolResponse schema
        """
        ...


def ensure_dual_use(tool_class: type) -> type:
    """Decorator to verify a class implements the DualUseTool protocol.

    This decorator checks that the class has both cli() and mcp() methods
    with appropriate signatures. Raises TypeError if validation fails.

    Args:
        tool_class: Class to validate

    Returns:
        The same class if validation passes

    Raises:
        TypeError: If class doesn't implement required methods

    Example:
        @ensure_dual_use
        class MyTool:
            @staticmethod
            def cli(args: list[str]) -> str:
                return "CLI output"

            @staticmethod
            async def mcp(**kwargs) -> dict:
                return {"success": True}
    """
    # Check for cli method
    if not hasattr(tool_class, "cli"):
        raise TypeError(
            f"Tool class {tool_class.__name__} must implement 'cli(args: list[str]) -> str' method"
        )

    # Check for mcp method
    if not hasattr(tool_class, "mcp"):
        raise TypeError(
            f"Tool class {tool_class.__name__} must implement 'async mcp(**kwargs) -> dict' method"
        )

    # Validate cli signature (basic check)
    cli_method = getattr(tool_class, "cli")
    if not callable(cli_method):
        raise TypeError(f"Tool class {tool_class.__name__}.cli must be callable")

    # Validate mcp signature (basic check)
    mcp_method = getattr(tool_class, "mcp")
    if not callable(mcp_method):
        raise TypeError(f"Tool class {tool_class.__name__}.mcp must be callable")

    # Check if mcp is async
    if not hasattr(mcp_method, "__wrapped__") and not hasattr(mcp_method, "__func__"):
        # For methods, check if they're defined as async
        import inspect

        if not inspect.iscoroutinefunction(mcp_method):
            raise TypeError(
                f"Tool class {tool_class.__name__}.mcp must be an async method"
            )

    return tool_class


__all__ = ["DualUseTool", "ensure_dual_use"]
