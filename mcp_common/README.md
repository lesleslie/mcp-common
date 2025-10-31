# mcp_common Package

## Purpose

`mcp_common` provides the ACB-native primitives used by Model Context Protocol servers: adapters with lifecycle management, strongly-typed settings, security helpers, and Rich-based console UI. Importing the package automatically registers it with ACB via `register_pkg("mcp_common")`, unlocking dependency injection and settings discovery.

## Layout

- `adapters/` — Adapter stubs. Use ACB adapters (e.g., requests) in projects.
- `config/` — `MCPBaseSettings` and mixins for YAML + environment configuration.
- `middleware/` — [Removed] Use project-specific middleware. If you use FastMCP, it provides rate limiting.
- `security/` — API key validation and payload sanitization helpers.
- `ui/` — Rich panel components surfaced via `ServerPanels`.
- `health.py` / `http_health.py` — Health check orchestration and HTTP probes.
- `exceptions.py` — Canonical exception taxonomy for downstream servers.

## Usage

Typical servers pull adapters and settings through ACB's DI container:

```python
from mcp_common.ui import ServerPanels

ServerPanels.startup_success(server_name="Weather MCP", http_endpoint="http://localhost:8000")
```

## Development Notes

Keep new modules aligned with the directory structure above. Prefer ACB-provided adapters in consuming projects rather than bundling them here.
