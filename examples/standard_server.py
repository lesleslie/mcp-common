"""Standard MCP server example - tools + resources.

This example demonstrates the StandardServer profile:
- Tool registration
- Resource management
- Enhanced configuration
- Rich UI support

Best for:
    - Production servers
    - Servers with dynamic resources
    - Servers needing configuration management
    - Data access servers

Usage:
    python examples/standard_server.py
"""

from __future__ import annotations

import json
import operator
from typing import Any

from mcp_common.profiles import StandardServer
from mcp_common.ui import ServerPanels


# Safe calculation operations
OPERATIONS = {
    "+": operator.add,
    "-": operator.sub,
    "*": operator.mul,
    "/": operator.truediv,
}


def safe_calculate(expression: str) -> dict[str, Any]:
    """Safely calculate a simple mathematical expression.

    Only supports basic operations (+, -, *, /) on integers.

    Args:
        expression: Mathematical expression (e.g., "2 + 2")

    Returns:
        Dictionary with expression and result
    """
    try:
        parts = expression.split()
        if len(parts) != 3:
            return {"expression": expression, "result": None, "error": "Invalid format"}

        a, op, b = parts
        a_int = int(a)
        b_int = int(b)

        if op not in OPERATIONS:
            return {"expression": expression, "result": None, "error": "Unsupported operation"}

        result = OPERATIONS[op](a_int, b_int)
        return {"expression": expression, "result": result, "error": None}
    except Exception as e:
        return {"expression": expression, "result": None, "error": str(e)}


def create_standard_server() -> StandardServer:
    """Create a standard MCP server with tools and resources.

    Returns:
        StandardServer instance with registered tools and resources

    Example:
        >>> server = create_standard_server()
        >>> server.run()
    """
    # Create standard server
    server = StandardServer(
        name="standard-server",
        description="Standard MCP Server with tools and resources"
    )

    # Register tools using decorators
    @server.tool()
    def search(query: str) -> dict[str, Any]:
        """Search for items.

        Args:
            query: Search query string

        Returns:
            Dictionary with search results
        """
        # Mock search results
        results = [
            {"id": 1, "title": f"Result 1 for '{query}'"},
            {"id": 2, "title": f"Result 2 for '{query}'"},
            {"id": 3, "title": f"Result 3 for '{query}'"},
        ]
        return {"query": query, "results": results, "count": len(results)}

    @server.tool()
    def calculate(expression: str) -> dict[str, Any]:
        """Safely calculate a simple mathematical expression.

        Args:
            expression: Mathematical expression (e.g., "2 + 2")

        Returns:
            Dictionary with expression and result
        """
        return safe_calculate(expression)

    @server.tool()
    def format_json(data: dict[str, Any]) -> str:
        """Format a dictionary as JSON.

        Args:
            data: Dictionary to format

        Returns:
            Formatted JSON string
        """
        return json.dumps(data, indent=2)

    # Register resource handlers
    @server.resource("config://{name}")
    def get_config(name: str) -> str:
        """Get configuration by name.

        Args:
            name: Configuration name

        Returns:
            Configuration as JSON string
        """
        # Mock configuration data
        configs = {
            "database": {"host": "localhost", "port": 5432, "name": "mydb"},
            "api": {"endpoint": "https://api.example.com", "timeout": 30},
            "features": {"feature_a": True, "feature_b": False},
        }
        return json.dumps(configs.get(name, {}))

    @server.resource("data://{table}")
    def get_table_data(table: str) -> str:
        """Get data from a table.

        Args:
            table: Table name

        Returns:
            Table data as JSON string
        """
        # Mock table data
        data = {
            "users": [
                {"id": 1, "name": "Alice", "email": "alice@example.com"},
                {"id": 2, "name": "Bob", "email": "bob@example.com"},
            ],
            "products": [
                {"id": 1, "name": "Product A", "price": 29.99},
                {"id": 2, "name": "Product B", "price": 49.99},
            ],
        }
        return json.dumps(data.get(table, []))

    @server.resource("status://{component}")
    def get_component_status(component: str) -> str:
        """Get status of a component.

        Args:
            component: Component name

        Returns:
            Component status as JSON string
        """
        # Mock component status
        statuses = {
            "database": {"status": "healthy", "connections": 10, "latency_ms": 5},
            "cache": {"status": "healthy", "hit_rate": 0.95, "memory_mb": 128},
            "api": {"status": "degraded", "response_time_ms": 500, "error_rate": 0.02},
        }
        return json.dumps(statuses.get(component, {"status": "unknown"}))

    return server


def main() -> None:
    """Main entry point for standard server example."""
    # Create server
    server = create_standard_server()

    # Display startup panel
    ServerPanels.startup_success(
        server_name="Standard MCP Server",
        version="1.0.0",
        features=[
            "Tools (search, calculate, format)",
            "Resources (config, data, status)",
            "Enhanced Configuration",
            "Rich UI Support",
        ],
    )

    # Show available tools and resources
    tools = server.list_tools()
    resources = server.list_resources()

    print(f"\nAvailable tools: {', '.join(tools)}")
    print(f"Available resources: {', '.join(resources)}")

    # Show health check
    health = server.health_check()
    print(f"\nHealth status: {health['status']}")
    print(f"Server: {health['server']}")
    print(f"Description: {health['description']}")
    print(f"Tools registered: {health['tools']}")
    print(f"Resources registered: {health['resources']}")

    # Demonstrate tool usage
    print("\n--- Tool Examples ---")
    search_tool = server.get_tool("search")
    if search_tool:
        result = search_tool(query="test")
        print(f"Search result: {json.dumps(result, indent=2)}")

    # Demonstrate resource usage
    print("\n--- Resource Examples ---")
    config_resource = server.get_resource("config://{name}")
    if config_resource:
        result = config_resource(name="database")
        print(f"Config resource: {result}")

    # In a real implementation, you would call server.run() here
    print("\nNote: This is a profile demonstration.")
    print("In production, you would integrate with FastMCP or native MCP server.")
    print("\nExample integration:")
    print("    from fastmcp import FastMCP")
    print("    mcp = FastMCP('standard-server')")
    print("    for name, tool in server._tools.items():")
    print("        mcp.add_tool(tool)")
    print("    for uri, handler in server._resources.items():")
    print("        mcp.add_resource(uri, handler)")
    print("    mcp.run()")


if __name__ == "__main__":
    main()
