"""Full MCP server example - production-ready with all features.

This example demonstrates the FullServer profile:
- Tool registration
- Resource management
- Prompt templates
- Authentication support
- Telemetry support
- Multi-worker support

Best for:
    - Production servers
    - Multi-user environments
    - Servers requiring authentication
    - Servers needing observability
    - High-traffic deployments

Usage:
    python examples/full_server.py
"""

from __future__ import annotations

import json
from typing import Any

from mcp_common.profiles import FullServer
from mcp_common.ui import ServerPanels


# Mock auth and telemetry backends (in production, import from actual modules)
class MockAuthBackend:
    """Mock authentication backend for demonstration."""

    def __init__(self, secret: str) -> None:
        self.secret = secret
        self.enabled = True

    def authenticate(self, token: str) -> bool:
        """Authenticate a token."""
        return token == self.secret


class MockTelemetryBackend:
    """Mock telemetry backend for demonstration."""

    def __init__(self, endpoint: str) -> None:
        self.endpoint = endpoint
        self.enabled = True

    def trace(self, operation: str) -> None:
        """Trace an operation."""
        pass


def create_full_server() -> FullServer:
    """Create a full-featured MCP server with all components.

    Returns:
        FullServer instance with tools, resources, and prompts

    Example:
        >>> auth = MockAuthBackend(secret="my-secret")
        >>> telemetry = MockTelemetryBackend(endpoint="http://jaeger:4317")
        >>> server = create_full_server()
        >>> server.run(workers=4)
    """
    # Create mock auth and telemetry backends
    auth = MockAuthBackend(secret="demo-secret")
    telemetry = MockTelemetryBackend(endpoint="http://jaeger:4317")

    # Create full server
    server = FullServer(
        name="full-server",
        description="Production-ready MCP Server with all features",
        auth=auth,
        telemetry=telemetry,
    )

    # Register tools using decorators
    @server.tool()
    def search(query: str, filters: dict[str, Any] | None = None) -> dict[str, Any]:
        """Search for items with optional filters.

        Args:
            query: Search query string
            filters: Optional filter criteria

        Returns:
            Dictionary with search results
        """
        # Mock search with authentication and telemetry hooks
        if server.auth:
            # In production: validate token
            pass

        if server.telemetry:
            # In production: trace this operation
            pass

        results = [
            {"id": 1, "title": f"Result 1 for '{query}'"},
            {"id": 2, "title": f"Result 2 for '{query}'"},
        ]

        if filters:
            results = [r for r in results if all(r.get(k) == v for k, v in filters.items())]

        return {"query": query, "results": results, "count": len(results), "filters": filters}

    @server.tool()
    def process_data(data: dict[str, Any], operations: list[str]) -> dict[str, Any]:
        """Process data with multiple operations.

        Args:
            data: Input data dictionary
            operations: List of operations to apply

        Returns:
            Processed data dictionary
        """
        result = data.copy()

        for op in operations:
            if op == "uppercase":
                result = {k: str(v).upper() if isinstance(v, str) else v for k, v in result.items()}
            elif op == "reverse":
                result = {k: str(v)[::-1] if isinstance(v, str) else v for k, v in result.items()}
            elif op == "count":
                result["_count"] = len(result)

        return {"original": data, "operations": operations, "result": result}

    # Register resource handlers
    @server.resource("config://{env}/{name}")
    def get_config(env: str, name: str) -> str:
        """Get configuration by environment and name.

        Args:
            env: Environment (dev, staging, prod)
            name: Configuration name

        Returns:
            Configuration as JSON string
        """
        # Mock environment-specific configs
        configs = {
            "dev": {
                "database": {"host": "localhost", "port": 5432, "name": "mydb_dev"},
                "api": {"endpoint": "http://localhost:8000", "timeout": 30},
            },
            "prod": {
                "database": {"host": "db.prod.example.com", "port": 5432, "name": "mydb_prod"},
                "api": {"endpoint": "https://api.example.com", "timeout": 10},
            },
        }
        return json.dumps(configs.get(env, {}).get(name, {}))

    @server.resource("data://{table}/{id}")
    def get_record(table: str, id: str) -> str:
        """Get a specific record from a table.

        Args:
            table: Table name
            id: Record ID

        Returns:
            Record data as JSON string
        """
        # Mock record data
        records = {
            "users": {
                "1": {"id": 1, "name": "Alice", "email": "alice@example.com"},
                "2": {"id": 2, "name": "Bob", "email": "bob@example.com"},
            },
            "products": {
                "1": {"id": 1, "name": "Product A", "price": 29.99},
                "2": {"id": 2, "name": "Product B", "price": 49.99},
            },
        }
        return json.dumps(records.get(table, {}).get(id, {}))

    # Register prompt templates
    @server.prompt("analyze")
    def analyze_prompt(data: str) -> str:
        """Generate a prompt for data analysis.

        Args:
            data: Data to analyze

        Returns:
            Analysis prompt string
        """
        return f"""Please analyze the following data:

{data}

Provide insights on:
1. Trends and patterns
2. Outliers and anomalies
3. Key takeaways
4. Recommendations
"""

    @server.prompt("summarize")
    def summarize_prompt(content: str, max_length: int = 200) -> str:
        """Generate a prompt for summarization.

        Args:
            content: Content to summarize
            max_length: Maximum summary length

        Returns:
            Summarization prompt string
        """
        return f"""Please summarize the following content in {max_length} words or less:

{content}

Focus on:
- Main points
- Key insights
- Action items
"""

    @server.prompt("code_review")
    def code_review_prompt(code: str, language: str = "Python") -> str:
        """Generate a prompt for code review.

        Args:
            code: Code to review
            language: Programming language

        Returns:
            Code review prompt string
        """
        return f"""Please review the following {language} code:

```{language.lower()}
{code}
```

Provide feedback on:
1. Code quality and readability
2. Potential bugs or issues
3. Performance considerations
4. Security concerns
5. Best practices
6. Suggestions for improvement
"""

    return server


def main() -> None:
    """Main entry point for full server example."""
    # Create server
    server = create_full_server()

    # Display startup panel
    ServerPanels.startup_success(
        server_name="Full MCP Server",
        version="1.0.0",
        features=[
            "Tools (search, process)",
            "Resources (config, data)",
            "Prompts (analyze, summarize, code_review)",
            "Authentication",
            "Telemetry",
            "Multi-worker support",
        ],
    )

    # Show all available components
    tools = server.list_tools()
    resources = server.list_resources()
    prompts = server.list_prompts()

    print(f"\nAvailable tools: {', '.join(tools)}")
    print(f"Available resources: {', '.join(resources)}")
    print(f"Available prompts: {', '.join(prompts)}")

    # Show comprehensive health check
    health = server.health_check()
    print(f"\nHealth status: {health['status']}")
    print(f"Server: {health['server']}")
    print(f"Description: {health['description']}")
    print(f"Tools: {health['tools']}")
    print(f"Resources: {health['resources']}")
    print(f"Prompts: {health['prompts']}")
    print(f"Auth enabled: {health['auth']['enabled']}")
    print(f"Telemetry enabled: {health['telemetry']['enabled']}")
    print(f"Workers: {health['workers']}")

    # Demonstrate prompt templates
    print("\n--- Prompt Template Examples ---")
    analyze_prompt = server.get_prompt("analyze")
    if analyze_prompt:
        prompt = analyze_prompt(data="Sample data for analysis")
        print(f"\nAnalyze prompt preview:\n{prompt[:200]}...")

    # In a real implementation, you would call server.run() here
    print("\n" + "=" * 80)
    print("Note: This is a profile demonstration.")
    print("In production, you would integrate with FastMCP or native MCP server.")
    print("\nExample integration:")
    print("    from fastmcp import FastMCP")
    print("    mcp = FastMCP('full-server')")
    print("    for name, tool in server._tools.items():")
    print("        mcp.add_tool(tool)")
    print("    for uri, handler in server._resources.items():")
    print("        mcp.add_resource(uri, handler)")
    print("    for name, template in server._prompts.items():")
    print("        mcp.add_prompt(name, template)")
    print("    mcp.run()")
    print("\nWith auth and telemetry:")
    print("    # Auth middleware would check tokens")
    print("    # Telemetry middleware would trace operations")
    print("    server.run(workers=4)")


if __name__ == "__main__":
    main()
