# mcp-common

![Coverage](https://img.shields.io/badge/coverage-99.2%25-brightgreen)
**Version:** 0.3.6 (Oneiric-Native)
**Status:** Production Ready

______________________________________________________________________

## Overview

mcp-common is an **Oneiric-native foundation library** for building production-grade MCP (Model Context Protocol) servers. It provides battle-tested patterns extracted from 9 production servers including crackerjack, session-mgmt-mcp, and fastblocks.

**🎯 What This Library Provides:**

- **Oneiric CLI Factory** (v0.3.3+) - Standardized server lifecycle with start/stop/restart/status/health commands
- **HTTP Client Adapter** - Connection pooling with httpx for 11x performance
- **Security Utilities** - API key validation and input sanitization
- **Rich Console UI** - Beautiful panels and notifications for server operations
- **Settings Management** - YAML + environment variable configuration (Pydantic-based)
- **Health Check System** - Production-ready health monitoring
- **Type-Safe** - Full Pydantic validation and type hints

**Design Principles:**

1. **Oneiric-Native** - Direct Pydantic, Rich library, and standard patterns
1. **Production-Ready** - Extracted from real production systems
1. **Layered Configuration** - YAML files + environment variables with clear priority
1. **Rich UI** - Professional console output with Rich panels
1. **Type-safe** - Full type hints with strict MyPy checking
1. **Well-Tested** - 90% coverage minimum

______________________________________________________________________

## 📚 Examples

See [`examples/`](./examples/) for complete production-ready examples:

### 1. CLI Server (Oneiric-Native) - NEW in v0.3.3

Demonstrates the **CLI factory** for standardized server lifecycle management:

- 5 lifecycle commands (start, stop, restart, status, health)
- PID file management with security validation
- Runtime health snapshots
- Graceful shutdown with signal handling
- Custom lifecycle handlers

```bash
cd examples
python cli_server.py start
python cli_server.py status
python cli_server.py health
python cli_server.py stop
```

### 2. Weather MCP Server (Oneiric-Native)

Demonstrates **HTTP adapters** and **FastMCP integration**:

- HTTPClientAdapter with connection pooling (11x performance)
- MCPBaseSettings with YAML + environment configuration
- ServerPanels for beautiful terminal UI
- Oneiric configuration patterns (direct instantiation)
- FastMCP tool integration (optional; install separately)

```bash
cd examples
python weather_server.py
```

**Full documentation:** [`examples/README.md`](./examples/README.md)

______________________________________________________________________

## Quick Start

### Installation

```bash
pip install mcp-common>=0.3.6
```

This automatically installs Pydantic, Rich, and all required dependencies.

If you plan to run an MCP server (e.g., the examples), install a protocol host such as FastMCP separately:

```bash
pip install fastmcp
# or
uv add fastmcp
```

### Minimal Example

```python
# my_server/settings.py
from mcp_common.config import MCPBaseSettings
from pydantic import Field


class MyServerSettings(MCPBaseSettings):
    """Server configuration following Oneiric pattern.

    Loads from (priority order):
    1. settings/local.yaml (gitignored)
    2. settings/my-server.yaml
    3. Environment variables MY_SERVER_*
    4. Defaults below
    """

    api_key: str = Field(description="API key for service")
    timeout: int = Field(default=30, description="Request timeout")


# my_server/main.py
from fastmcp import FastMCP  # Optional: install fastmcp separately
from mcp_common import ServerPanels, HTTPClientAdapter, HTTPClientSettings
from my_server.settings import MyServerSettings

# Initialize
mcp = FastMCP("MyServer")
settings = MyServerSettings.load("my-server")

# Initialize HTTP adapter
http_settings = HTTPClientSettings(timeout=settings.timeout)
http_adapter = HTTPClientAdapter(settings=http_settings)


# Define tools
@mcp.tool()
async def call_api():
    # Use the global adapter instance
    response = await http_adapter.get("https://api.example.com")
    return response.json()


# Run server
if __name__ == "__main__":
    # Display startup panel
    ServerPanels.startup_success(
        server_name="My MCP Server",
        version="1.0.0",
        features=["HTTP Client", "YAML Configuration"],
    )

    mcp.run()
```

______________________________________________________________________

## Core Features

### 🔌 HTTP Client Adapter

**Connection Pooling with httpx:**

- 11x faster than creating clients per request
- Automatic initialization and cleanup
- Configurable timeouts, retries, connection limits

```python
from mcp_common import HTTPClientAdapter, HTTPClientSettings

# Configure HTTP adapter
http_settings = HTTPClientSettings(
    timeout=30,
    max_connections=50,
    retry_attempts=3,
)

# Create adapter
http_adapter = HTTPClientAdapter(settings=http_settings)

# Make requests
response = await http_adapter.get("https://api.example.com")
```

Note: Rate limiting is not provided by this library. If you use FastMCP, its built-in `RateLimitingMiddleware` can be enabled; otherwise, use project-specific configuration.

### 🎯 Oneiric CLI Factory (NEW in v0.3.3)

**Production-Ready Server Lifecycle Management:**

The `MCPServerCLIFactory` provides standardized CLI commands for managing MCP server lifecycles, inspired by Oneiric's operational patterns. It handles process management, health monitoring, and graceful shutdown out of the box.

**Features:**

- **5 Standard Commands** - `start`, `stop`, `restart`, `status`, `health`
- **Security-First** - Secure PID files (0o600), cache directories (0o700), ownership validation
- **Process Validation** - Detects stale PIDs, prevents race conditions, validates process identity
- **Health Monitoring** - Runtime health snapshots with configurable TTL
- **Signal Handling** - Graceful shutdown on SIGTERM/SIGINT
- **Custom Handlers** - Extensible lifecycle hooks for server-specific logic
- **Dual Output** - Human-readable and JSON output modes
- **Standard Exit Codes** - Shell-scriptable with semantic exit codes

**Quick Example:**

```python
from mcp_common.cli import MCPServerCLIFactory, MCPServerSettings

# 1. Load settings (YAML + env vars)
settings = MCPServerSettings.load("my-server")


# 2. Define lifecycle handlers
def start_server():
    print("Server initialized!")
    # Your server startup logic here


def stop_server(pid: int):
    print(f"Stopping PID {pid}")
    # Your cleanup logic here


def check_health():
    # Return current health snapshot
    return RuntimeHealthSnapshot(
        orchestrator_pid=os.getpid(),
        watchers_running=True,
    )


# 3. Create CLI factory
factory = MCPServerCLIFactory(
    server_name="my-server",
    settings=settings,
    start_handler=start_server,
    stop_handler=stop_server,
    health_probe_handler=check_health,
)

# 4. Create and run Typer app
app = factory.create_app()

if __name__ == "__main__":
    app()
```

**Command Usage:**

```bash
# Start server (creates PID file and health snapshot)
python my_server.py start

# Check status (lightweight process check)
python my_server.py status
# Output: Server running (PID 12345, snapshot age: 2.3s, fresh: True)

# View health (detailed health information)
python my_server.py health

# Live health probe
python my_server.py health --probe

# Stop server (graceful shutdown with SIGTERM)
python my_server.py stop

# Force stop with timeout
python my_server.py stop --timeout 5 --force

# Restart (stop + start)
python my_server.py restart

# JSON output for automation
python my_server.py status --json
```

**Configuration:**

Settings are loaded from multiple sources (priority order):

1. `settings/local.yaml` (gitignored, for development)
1. `settings/{server-name}.yaml` (checked into repo)
1. Environment variables `MCP_SERVER_*`
1. Defaults in `MCPServerSettings`

Example `settings/my-server.yaml`:

```yaml
server_name: "My MCP Server"
cache_root: .oneiric_cache
health_ttl_seconds: 60.0
log_level: INFO
```

**Exit Codes:**

- `0` - Success
- `1` - General error
- `2` - Server not running (status/stop)
- `3` - Server already running (start)
- `4` - Health check failed
- `5` - Configuration error
- `6` - Permission error
- `7` - Timeout
- `8` - Stale PID file (use `--force`)

**Full Example:**

See [`examples/cli_server.py`](./examples/cli_server.py) for a complete working example with custom commands and health probes.

### ⚙️ Settings with YAML Support (Oneiric Pattern)

- Pure Pydantic BaseModel
- Layered configuration: YAML files + environment variables
- Type validation with Pydantic
- Path expansion (`~` → home directory)

```python
from mcp_common.config import MCPBaseSettings


class ServerSettings(MCPBaseSettings):
    api_key: str  # Required
    timeout: int = 30  # Optional with default


# Load with layered configuration
settings = ServerSettings.load("my-server")
# Loads from:
# 1. settings/my-server.yaml
# 2. settings/local.yaml
# 3. Environment variables MY_SERVER_*
# 4. Defaults
```

### 📝 Standard Python Logging

mcp-common uses standard Python logging. Configure as needed for your server:

```python
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)
logger.info("Server started")
```

### 🎨 Rich Console UI

- Beautiful startup panels
- Error displays with context
- Statistics tables
- Progress bars

```python
from mcp_common.ui import ServerPanels

ServerPanels.startup_success(
    server_name="Mailgun MCP",
    http_endpoint="http://localhost:8000",
    features=["Rate Limiting", "Security Filters"],
)
```

### 🧪 Testing Utilities

- Mock MCP clients
- HTTP response mocking
- Shared fixtures
- DI-friendly testing

```python
from mcp_common.testing import MockMCPClient, mock_http_response


async def test_tool():
    with mock_http_response(status=200, json={"ok": True}):
        result = await my_tool()
    assert result["success"]
```

______________________________________________________________________

## Documentation

- **[examples/README.md](./examples/README.md)** - **START HERE** - Example servers and usage patterns
- **[ONEIRIC_CLI_FACTORY\_\*.md](./docs/)** - CLI factory documentation and implementation guides

______________________________________________________________________

## Complete Example

See [`examples/`](./examples/) for a complete production-ready Weather MCP server demonstrating mcp-common patterns.

### Key Patterns Demonstrated:

1. **Oneiric Settings** - YAML + environment variable configuration with `.load()`
1. **HTTP Adapter** - HTTPClientAdapter with connection pooling
1. **Rich UI** - ServerPanels for startup/errors/status
1. **Tool Organization** - Modular tool registration with FastMCP
1. **Configuration Layering** - Multiple config sources with clear priority
1. **Type Safety** - Full Pydantic validation throughout
1. **Error Handling** - Graceful error display with ServerPanels

______________________________________________________________________

## Performance Benchmarks

### HTTP Client Adapter (vs new client per request)

```
Before: 100 requests in 45 seconds, 500MB memory
After:  100 requests in 4 seconds, 50MB memory

Result: 11x faster, 10x less memory
```

### Rate Limiter Overhead

```
Without: 1000 requests in 1.2 seconds
With:    1000 requests in 1.25 seconds

Result: +4% overhead (negligible vs network I/O)
```

______________________________________________________________________

## Usage Patterns

### Pattern 1: Configure Settings with YAML

```python
from mcp_common.config import MCPBaseSettings
from pydantic import Field


class MySettings(MCPBaseSettings):
    api_key: str = Field(description="API key")
    timeout: int = Field(default=30, description="Timeout")


# Load from settings/my-server.yaml + env vars
settings = MySettings.load("my-server")

# Access configuration
print(f"Using API key: {settings.get_masked_key()}")
```

### Pattern 2: Use HTTP Client Adapter

```python
from mcp_common import HTTPClientAdapter, HTTPClientSettings


# Configure HTTP client
http_settings = HTTPClientSettings(
    timeout=30,
    max_connections=50,
    retry_attempts=3,
)

# Create adapter
http = HTTPClientAdapter(settings=http_settings)


# Make requests
@mcp.tool()
async def call_api():
    response = await http.get("https://api.example.com/data")
    return response.json()


# Cleanup when done
await http._cleanup_resources()
```

### Pattern 3: Display Rich UI Panels

```python
from mcp_common import ServerPanels

# Startup panel
ServerPanels.startup_success(
    server_name="My Server",
    version="1.0.0",
    features=["Feature 1", "Feature 2"],
)

# Error panel
ServerPanels.error(
    title="API Error",
    message="Failed to connect",
    suggestion="Check your API key",
)

# Status table
ServerPanels.status_table(
    title="Health Check",
    rows=[
        ("API", "✅ Healthy", "200 OK"),
        ("Database", "⚠️ Degraded", "Slow queries"),
    ],
)
```

______________________________________________________________________

## Development

### Setup

```bash
git clone https://github.com/lesaker/mcp-common.git
cd mcp-common
pip install -e ".[dev]"
```

### Running Tests

```bash
# Run all tests with coverage
pytest --cov=mcp_common --cov-report=html

# Run specific test
pytest tests/test_http_adapter.py -v

# Run with ACB integration tests
pytest tests/integration/ -v
```

### Code Quality

```bash
# Format code
ruff format

# Lint code
ruff check

# Type checking
mypy mcp_common tests

# Run all quality checks
crackerjack --all
```

______________________________________________________________________

## Versioning

**Recent Versions:**

- **0.3.6** - Oneiric-native (removed ACB dependency)
- **0.3.3** - Added Oneiric CLI Factory
- **0.3.0** - Initial Oneiric patterns
- **2.0.0** - Previous ACB-native version (deprecated)

**Compatibility:**

- Requires Python 3.13+
- Optional: compatible with FastMCP 2.0+
- Uses Pydantic 2.12+, Rich 14.2+

______________________________________________________________________

## Success Metrics

**Current Status:**

1. ✅ Professional Rich UI in all components
1. ✅ 90%+ test coverage maintained
1. ✅ Zero production incidents
1. ✅ Oneiric-native patterns throughout
1. ✅ Standardized CLI lifecycle management
1. ✅ Clean dependency tree (no framework lock-in)

______________________________________________________________________

## License

BSD-3-Clause License - See [LICENSE](./LICENSE) for details

______________________________________________________________________

## Contributing

Contributions are welcome! Please:

1. Read [`examples/README.md`](./examples/README.md) for usage patterns
1. Follow Oneiric patterns (see examples)
1. Fork and create feature branch
1. Add tests (coverage ≥90%)
1. Ensure all quality checks pass (`ruff format && ruff check && mypy && pytest`)
1. Submit pull request

______________________________________________________________________

## Acknowledgments

Built with patterns extracted from 9 production MCP servers:

**Primary Pattern Sources:**

- **crackerjack** - MCP server structure, Rich UI panels, CLI patterns
- **session-mgmt-mcp** - Configuration patterns, health checks
- **fastblocks** - Adapter organization, settings management

**Additional Contributors:**

- raindropio-mcp (HTTP client patterns)
- excalidraw-mcp (testing patterns)
- opera-cloud-mcp
- mailgun-mcp
- unifi-mcp

______________________________________________________________________

## Support

For support, please check the documentation in the `docs/` directory or create an issue in the repository.

______________________________________________________________________

**Ready to get started?** Check out [`examples/`](./examples/) for working examples demonstrating all features!
