# MCP Common Quickstart (5 minutes)

MCP Common is the foundational library for building MCP servers in the Mahavishnu ecosystem. It provides battle-tested patterns extracted from 9 production servers.

## Choose Your Server Profile

MCP Common provides **three usage profiles** for different needs:

| Profile | Features | Best For |
|---------|----------|----------|
| **MinimalServer** | Basic tools only | Quick prototypes, simple tools |
| **StandardServer** | Tools + Resources | Most production servers (recommended) |
| **FullServer** | All features (auth, telemetry, prompts) | Enterprise, multi-user, high-traffic |

**Quick decision:**

- New to MCP? Start with **MinimalServer**
- Building a production server? Use **StandardServer** (recommended default)
- Need auth, telemetry, or multi-user? Use **FullServer**

See [Usage Profiles Guide](docs/guides/usage-profiles.md) for detailed comparison.

## Level 1: Minimal Server (1 minute)

The fastest way to get started with MCP Common:

```python
from mcp_common.profiles import MinimalServer

# Create minimal server
server = MinimalServer(name="minimal-server")

@server.tool()
def hello(name: str) -> str:
    return f"Hello {name}!"

@server.tool()
def add(a: int, b: int) -> int:
    return a + b

# Run server (integrate with FastMCP or native MCP)
server.run()
```

**Or use FastMCP directly:**

```bash
# Install mcp-common
pip install mcp-common

# Create basic server
cat > my_server.py << 'EOF'
from mcp_common import MCPBaseSettings
from fastmcp import FastMCP

class Settings(MCPBaseSettings):
    api_key: str = "demo"

# Load configuration (YAML + env vars)
settings = Settings.load("my-server")

# Create MCP server
mcp = FastMCP("My Server")

@mcp.tool()
def hello(name: str) -> str:
    return f"Hello {name}!"

if __name__ == "__main__":
    mcp.run()
EOF

# Run server
python my_server.py
```

## Level 2: Standard Server (2 minutes)

Add resources and enhanced configuration for production:

```python
from mcp_common.profiles import StandardServer
from mcp_common.ui import ServerPanels
from fastmcp import FastMCP

# Create standard server with tools and resources
server = StandardServer(
    name="standard-server",
    description="My MCP Server"
)

@server.tool()
def search(query: str) -> dict:
    """Search for items."""
    results = [
        {"id": 1, "title": f"Result 1 for '{query}'"},
        {"id": 2, "title": f"Result 2 for '{query}'"},
    ]
    return {"query": query, "results": results, "count": len(results)}

@server.resource("config://{name}")
def get_config(name: str) -> str:
    """Get configuration by name."""
    import json
    configs = {
        "database": {"host": "localhost", "port": 5432},
        "api": {"endpoint": "https://api.example.com"},
    }
    return json.dumps(configs.get(name, {}))

# Display startup panel
ServerPanels.startup_success(
    server_name="Standard MCP Server",
    version="1.0.0",
    features=["Tools", "Resources", "Rich UI"],
)

# Run server
server.run()
```

**With HTTP client pooling:**

```python
from mcp_common import (
    HTTPClientAdapter,
    HTTPClientSettings,
    ServerPanels,
)
from mcp_common.profiles import StandardServer

server = StandardServer(name="standard-server")

# Create HTTP adapter with connection pooling (11x faster!)
http_settings = HTTPClientSettings(
    timeout=30,
    max_connections=50,
)
http = HTTPClientAdapter(settings=http_settings)

@server.tool()
async def search_api(query: str) -> dict:
    """Search API with connection pooling."""
    response = await http.get(f"https://api.example.com/search?q={query}")
    return response.json()

ServerPanels.startup_success(
    server_name="My Server",
    version="1.0.0",
    features=["HTTP Pooling", "Resources", "Rich UI"],
)

server.run()
```

## Level 3: Full Server (2 minutes)

Add authentication, telemetry, and prompt templates for enterprise:

```python
from mcp_common.profiles import FullServer
from mcp_common.ui import ServerPanels

# Create mock auth and telemetry (in production, use real backends)
class MockAuth:
    def __init__(self, secret: str):
        self.secret = secret

class MockTelemetry:
    def __init__(self, endpoint: str):
        self.endpoint = endpoint

# Create full server with all features
server = FullServer(
    name="full-server",
    description="Enterprise MCP Server",
    auth=MockAuth(secret="your-secret"),
    telemetry=MockTelemetry(endpoint="http://jaeger:4317"),
)

@server.tool()
async def process_data(data: dict) -> dict:
    """Process data with automatic auth and telemetry."""
    # Auth check and telemetry tracing happen automatically
    return {"processed": True, "data": data}

@server.resource("data://{id}")
async def get_data(id: str) -> str:
    """Get data with automatic auth."""
    import json
    return json.dumps({"id": id, "value": "sample"})

@server.prompt("analyze")
def analyze_prompt(data: str) -> str:
    """Reusable prompt template for analysis."""
    return f"Please analyze this data: {data}"

ServerPanels.startup_success(
    server_name="Full MCP Server",
    version="1.0.0",
    features=["Tools", "Resources", "Prompts", "Auth", "Telemetry"],
)

# Run with multiple workers
server.run(workers=4)
```

## Level 4: Production Deployment (CLI Factory)

Add CLI lifecycle management, health checks, and monitoring:

```python
import os
from mcp_common import (
    MCPServerCLIFactory,
    MCPServerSettings,
    RuntimeHealthSnapshot,
    ServerPanels,
)

# Load settings
settings = MCPServerSettings.load("my-server")

# Define lifecycle handlers
def start_server():
    """Initialize server with PID file already created."""
    ServerPanels.startup_success(
        server_name="My Server",
        version="1.0.0",
        features=["CLI Factory", "Health Checks"],
    )
    # Start your actual server here
    import time
    while True:
        time.sleep(1)

def stop_server(pid: int):
    """Cleanup before shutdown."""
    print(f"Stopping PID {pid}")
    # Cleanup resources

def check_health():
    """Return current health snapshot."""
    return RuntimeHealthSnapshot(
        orchestrator_pid=os.getpid(),
        watchers_running=True,
    )

# Create CLI factory
factory = MCPServerCLIFactory(
    server_name="my-server",
    settings=settings,
    start_handler=start_server,
    stop_handler=stop_server,
    health_probe_handler=check_health,
)

# Create and run CLI
app = factory.create_app()

if __name__ == "__main__":
    app()
```

**Usage:**

```bash
# Start server with PID file management
python my_server.py start

# Check server status
python my_server.py status

# View health information
python my_server.py health

# Graceful shutdown
python my_server.py stop

# Restart server
python my_server.py restart
```

## Key Features

### 1. Usage Profiles

Choose the right profile for your needs:

```python
from mcp_common.profiles import MinimalServer, StandardServer, FullServer

# Minimal: Fast and simple
server = MinimalServer(name="my-server")

# Standard: Balanced features (recommended)
server = StandardServer(name="my-server")

# Full: Enterprise-grade
server = FullServer(name="my-server", auth=auth, telemetry=telemetry)
```

**Profile Comparison:**

| Feature | Minimal | Standard | Full |
|---------|---------|----------|------|
| Tools | Yes | Yes | Yes |
| Resources | No | Yes | Yes |
| Prompts | No | No | Yes |
| Auth | No | No | Yes |
| Telemetry | No | No | Yes |
| Multi-worker | No | No | Yes |

### 2. Oneiric Configuration Pattern

Layered configuration loading (priority order):

1. `settings/local.yaml` (gitignored, local dev)
1. `settings/{server-name}.yaml` (committed)
1. Environment variables `{SERVER_NAME}_*`
1. Default values in code

```yaml
# settings/my-server.yaml
api_key: "production-key"
timeout: 30
max_connections: 50
```

```bash
# Override with environment variables
export MY_SERVER_API_KEY="dev-key"
export MY_SERVER_TIMEOUT=60
```

### 3. HTTP Client Adapter

Connection pooling for 11x performance improvement:

```python
from mcp_common import HTTPClientAdapter, HTTPClientSettings

# Configure pooling
http_settings = HTTPClientSettings(
    timeout=30,
    max_connections=50,
    retry_attempts=3,
)

# Create adapter (client reused across requests)
http = HTTPClientAdapter(settings=http_settings)

# Use in tools
response = await http.get("https://api.example.com/data")
```

### 4. Rich Console UI

Beautiful terminal output:

```python
from mcp_common import ServerPanels

# Startup panel
ServerPanels.startup_success(
    server_name="My Server",
    version="1.0.0",
    features=["Feature 1", "Feature 2"],
)

# Error panel with suggestions
ServerPanels.error(
    title="API Error",
    message="Connection failed",
    suggestion="Check your API key",
)

# Status table
ServerPanels.status_table(
    title="Health Check",
    rows=[
        ("API", "Healthy", "200 OK"),
        ("Database", "Degraded", "Slow queries"),
    ],
)
```

### 5. CLI Factory (Production-Ready)

Standardized server lifecycle management:

- **5 lifecycle commands**: start, stop, restart, status, health
- **Security-first**: Secure PID files (0o600), cache directories (0o700)
- **Process validation**: Detects stale PIDs, prevents race conditions
- **Health monitoring**: Runtime health snapshots with TTL
- **Signal handling**: Graceful shutdown on SIGTERM/SIGINT
- **Exit codes**: Shell-scriptable with semantic exit codes

### 6. Input Validation

Pydantic-based validation for all inputs:

```python
from mcp_common import validate_input

@mcp.tool()
@validate_input(str, min_length=1)
def search(query: str) -> dict:
    """Query is validated before execution."""
    return {"results": [...]}

# Validation errors are caught and displayed nicely
result = await search("")  # Raises ValidationError
```

### 7. Security Utilities

API key validation and input sanitization:

```python
from mcp_common.security import validate_api_key, sanitize_input

# API key validation (with 90% faster caching)
validate_api_key("sk-1234567890abcdef")

# Input sanitization (2x faster with early exit)
clean = sanitize_input(user_input, remove_secrets=True)
```

## Configuration Examples

### Minimal Configuration

```python
from mcp_common.profiles import MinimalServer

server = MinimalServer(name="my-server")
```

### Standard Configuration

```python
from mcp_common.profiles import StandardServer

server = StandardServer(
    name="my-server",
    description="My production server"
)
```

### Full Configuration

```yaml
# settings/my-server.yaml
server_name: "My MCP Server"
description: "Production-ready server"
log_level: INFO
auth_enabled: true
telemetry_enabled: true
workers: 4
```

```python
from mcp_common.profiles import FullServer
from mcp_common.auth import JWTAuth
from mcp_common.telemetry import OpenTelemetry

auth = JWTAuth(secret=os.getenv("JWT_SECRET"))
telemetry = OpenTelemetry(endpoint=os.getenv("JAEGER_ENDPOINT"))

server = FullServer(
    name="my-server",
    auth=auth,
    telemetry=telemetry
)
```

## Testing Your Server

```python
import pytest
from unittest.mock import AsyncMock

@pytest.fixture
def mock_http():
    """Mock HTTP adapter for testing."""
    mock = AsyncMock()
    mock.get.return_value.json.return_value = {"ok": True}
    return mock

@pytest.mark.asyncio
async def test_search_tool(mock_http):
    """Test with mocked HTTP client."""
    # Replace global adapter with mock
    global http_adapter
    http_adapter = mock_http

    # Test tool
    result = await search("test")
    assert result["ok"] is True
    mock_http.get.assert_called_once()
```

## Next Steps

### Learn More

- **[Usage Profiles Guide](docs/guides/usage-profiles.md)** - Detailed profile comparison and selection
- **[Full Documentation](README.md)** - Complete feature documentation
- **[Examples](examples/README.md)** - Working server examples
- **[API Reference](docs/)** - Detailed API documentation

### Run Example Servers

```bash
# Minimal server example
python examples/minimal_server.py

# Standard server example
python examples/standard_server.py

# Full server example
python examples/full_server.py

# CLI server example (with lifecycle management)
python examples/cli_server.py start
python examples/cli_server.py status
python examples/cli_server.py stop
```

### Ecosystem Projects

See mcp-common in action:

- **[Mahavishnu](https://github.com/lesleslie/mahavishnu)** - Orchestration platform
- **[Session-Buddy](https://github.com/lesleslie/session-buddy)** - Session manager
- **[Crackerjack](https://github.com/lesleslie/crackerjack)** - Quality inspector

### Advanced Topics

- **[CLI Factory Guide](docs/ONEIRIC_CLI_FACTORY_IMPLEMENTATION.md)** - Lifecycle management
- **[Security Implementation](docs/SECURITY_IMPLEMENTATION.md)** - Security features
- **[Server Integration](docs/SERVER_INTEGRATION.md)** - Integration patterns

## Quick Reference

| Feature | Import | Usage |
|---------|--------|-------|
| **Minimal Profile** | `from mcp_common.profiles import MinimalServer` | `MinimalServer(name)` |
| **Standard Profile** | `from mcp_common.profiles import StandardServer` | `StandardServer(name)` |
| **Full Profile** | `from mcp_common.profiles import FullServer` | `FullServer(name, auth, telemetry)` |
| **Configuration** | `from mcp_common import MCPBaseSettings` | `Settings.load("name")` |
| **HTTP Client** | `from mcp_common import HTTPClientAdapter` | `HTTPClientAdapter(settings)` |
| **Rich UI** | `from mcp_common import ServerPanels` | `ServerPanels.startup_success()` |
| **CLI Factory** | `from mcp_common import MCPServerCLIFactory` | `MCPServerCLIFactory(settings)` |
| **Validation** | `from mcp_common import validate_input` | `@validate_input(str)` |
| **Security** | `from mcp_common.security import validate_api_key` | `validate_api_key(key)` |

## Performance Tips

1. **Choose the Right Profile** - Start with Minimal, upgrade as needed
1. **Use HTTP Client Adapter** - 11x faster than creating clients per request
1. **Enable API Key Caching** - 90% faster validation (automatic)
1. **Use Early-Exit Sanitization** - 2x faster for clean text (automatic)
1. **Configure Connection Pools** - Match pool size to expected load

## Common Patterns

### Pattern 1: Start Simple, Upgrade Later

```python
# Phase 1: Prototype (Minimal)
from mcp_common.profiles import MinimalServer
server = MinimalServer(name="my-server")

# Phase 2: Add resources (Standard)
from mcp_common.profiles import StandardServer
server = StandardServer(name="my-server")

# Phase 3: Add auth and telemetry (Full)
from mcp_common.profiles import FullServer
server = FullServer(name="my-server", auth=auth, telemetry=telemetry)
```

### Pattern 2: Global Instances

```python
# Global instances (initialized in main)
settings: Settings
http_adapter: HTTPClientAdapter

async def main():
    global settings, http_adapter
    settings = Settings.load("my-server")
    http_adapter = HTTPClientAdapter(...)
    try:
        await mcp.run()
    finally:
        await http_adapter._cleanup_resources()

# Use in tools
@mcp.tool()
async def my_tool():
    response = await http_adapter.get(settings.api_url)
    return response.json()
```

### Pattern 3: CLI with Custom Commands

```python
factory = MCPServerCLIFactory(...)
app = factory.create_app()

@app.command()
def custom_command():
    """Add server-specific commands."""
    print("Custom command!")

if __name__ == "__main__":
    app()
```

### Pattern 4: Error Handling with Rich UI

```python
from mcp_common import ServerPanels

try:
    response = await http.get(url)
    response.raise_for_status()
except httpx.HTTPStatusError as e:
    ServerPanels.error(
        title="HTTP Error",
        message=f"Request failed: {e.response.status_code}",
        suggestion="Check API endpoint and credentials",
        error_type="HTTPStatusError",
    )
    raise
```

## Troubleshooting

### Import Errors

```bash
# If you see: ImportError: cannot import name 'HTTPClientAdapter'
pip install mcp-common[dev]
```

### Configuration Not Loading

```python
# Check configuration is being loaded
settings = Settings.load("my-server")
print(f"Loaded config: {settings.model_dump()}")

# Verify YAML files exist
ls settings/my-server.yaml
ls settings/local.yaml  # Optional, for local dev
```

### PID File Issues

```bash
# If server won't start due to stale PID
python my_server.py stop --force

# Or manually remove PID file
rm .oneiric_cache/my-server.pid
```

## Support

- **Documentation**: [README.md](README.md)
- **Usage Profiles**: [docs/guides/usage-profiles.md](docs/guides/usage-profiles.md)
- **Examples**: [examples/](examples/)
- **Issues**: [GitHub Issues](https://github.com/lesleslie/mcp-common/issues)

**Ready to build your MCP server?** Choose a profile and start with the examples in `examples/` directory!
