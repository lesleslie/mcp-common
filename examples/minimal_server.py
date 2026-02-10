"""Minimal MCP server example - tools only.

This example demonstrates the MinimalServer profile:
- Basic tool registration
- Simple configuration
- Fast startup
- Minimal dependencies

Best for:
    - Quick prototypes
    - Simple utility servers
    - Stateless tools
    - Development environments

Usage:
    python examples/minimal_server.py
"""

from __future__ import annotations

from mcp_common.profiles import MinimalServer
from mcp_common.ui import ServerPanels


def create_minimal_server() -> MinimalServer:
    """Create a minimal MCP server with basic tools.

    Returns:
        MinimalServer instance with registered tools

    Example:
        >>> server = create_minimal_server()
        >>> server.run()
    """
    # Create minimal server
    server = MinimalServer(name="minimal-server")

    # Register tools using decorators
    @server.tool()
    def hello(name: str) -> str:
        """Say hello to someone.

        Args:
            name: Person's name

        Returns:
            Greeting message
        """
        return f"Hello, {name}!"

    @server.tool()
    def add(a: int, b: int) -> int:
        """Add two numbers.

        Args:
            a: First number
            b: Second number

        Returns:
            Sum of the numbers
        """
        return a + b

    @server.tool()
    def multiply(a: int, b: int) -> int:
        """Multiply two numbers.

        Args:
            a: First number
            b: Second number

        Returns:
            Product of the numbers
        """
        return a * b

    @server.tool()
    def reverse_string(text: str) -> str:
        """Reverse a string.

        Args:
            text: Text to reverse

        Returns:
            Reversed text
        """
        return text[::-1]

    return server


def main() -> None:
    """Main entry point for minimal server example."""
    # Create server
    server = create_minimal_server()

    # Display startup panel
    ServerPanels.startup_success(
        server_name="Minimal MCP Server",
        version="1.0.0",
        features=[
            "Basic Tools",
            "Simple Configuration",
            "Fast Startup",
            "Minimal Dependencies",
        ],
    )

    # Show available tools
    tools = server.list_tools()
    print(f"\nAvailable tools: {', '.join(tools)}")

    # Show health check
    health = server.health_check()
    print(f"\nHealth status: {health['status']}")
    print(f"Server: {health['server']}")
    print(f"Tools registered: {health['tools']}")

    # In a real implementation, you would call server.run() here
    # which would start the actual MCP server (e.g., FastMCP)
    print("\nNote: This is a profile demonstration.")
    print("In production, you would integrate with FastMCP or native MCP server.")
    print("\nExample integration:")
    print("    from fastmcp import FastMCP")
    print("    mcp = FastMCP('minimal-server')")
    print("    for name, tool in server._tools.items():")
    print("        mcp.add_tool(tool)")
    print("    mcp.run()")


if __name__ == "__main__":
    main()
