# mcp_common Package

## Purpose
`mcp_common` provides the ACB-native primitives used by Model Context Protocol servers: adapters with lifecycle management, strongly-typed settings, security helpers, and Rich-based console UI. Importing the package automatically registers it with ACB via `register_pkg("mcp_common")`, unlocking dependency injection and settings discovery.

## Layout
- `adapters/` — Connection-pooled HTTP client patterns and future transport adapters.
- `config/` — `MCPBaseSettings` and mixins for YAML + environment configuration.
- `middleware/` — Shared rate limit profiles and helper utilities for request shaping.
- `security/` — API key validation and payload sanitization helpers.
- `ui/` — Rich panel components surfaced via `ServerPanels`.
- `health.py` / `http_health.py` — Health check orchestration and HTTP probes.
- `exceptions.py` — Canonical exception taxonomy for downstream servers.

## Usage
Typical servers pull adapters and settings through ACB's DI container:

```python
from acb.depends import depends
from mcp_common import HTTPClientAdapter, ServerPanels

http = depends(HTTPClientAdapter)
client = await http._create_client()
ServerPanels.startup_success(server_name="Weather MCP", http_endpoint="http://localhost:8000")
```

## Development Notes
Keep new modules aligned with the directory structure above. When introducing an adapter, expose it from `mcp_common/__init__.py` and document it in the relevant directory README. Tests that exercise these components should live under `tests/` and mirror the package path (for example, `tests/test_http_client.py` for `adapters/http/client.py`).
