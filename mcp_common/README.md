# mcp_common Package

## Purpose

`mcp_common` provides Oneiric-native primitives for Model Context Protocol servers: HTTP client with connection pooling, strongly-typed settings with YAML + environment variables, security helpers, and Rich-based console UI.

## Layout

- `adapters/` — HTTP client adapter with connection pooling (HTTPClientAdapter)
- `cli/` — CLI factory for standardized server lifecycle (MCPServerCLIFactory)
- `config/` — `MCPBaseSettings` for YAML + environment configuration
- `security/` — API key validation and input sanitization helpers
- `ui/` — Rich panel components via `ServerPanels`
- `health.py` / `http_health.py` — Health check models and HTTP probes
- `exceptions.py` — Canonical exception hierarchy for MCP servers

## Usage

Typical servers use direct instantiation with global instances:

```python
from mcp_common import MCPBaseSettings, HTTPClientAdapter, ServerPanels

# Load settings
settings = MCPBaseSettings.load("my-server")

# Create HTTP adapter
http_adapter = HTTPClientAdapter(settings=HTTPClientSettings())

# Display startup panel
ServerPanels.startup_success(server_name="My MCP Server", features=["Feature 1", "Feature 2"])
```

## Development Notes

Keep new modules aligned with the directory structure above. This library provides foundation components - avoid framework dependencies to maintain simplicity.
