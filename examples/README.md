# mcp-common Examples

This directory contains example MCP servers demonstrating best practices with the mcp-common foundation library.

## CLI Server (Oneiric-Native) - **NEW in v3.0**

A complete example demonstrating the **Oneiric CLI factory** for standardized MCP server lifecycle management.

### Quick Start

```bash
# Start the server (creates PID file and health snapshot)
python examples/cli_server.py start

# Check server status
python examples/cli_server.py status

# View server health
python examples/cli_server.py health

# Run live health probe
python examples/cli_server.py health --probe

# View configuration
python examples/cli_server.py config

# View cache paths
python examples/cli_server.py paths

# View statistics
python examples/cli_server.py stats

# Stop the server (graceful shutdown)
python examples/cli_server.py stop

# Restart (stop + start)
python examples/cli_server.py restart
```

### Features Demonstrated

1. **MCPServerCLIFactory** - Standardized CLI with 5 lifecycle commands

   - `start` - Start server with PID file creation
   - `stop` - Graceful shutdown with configurable timeout
   - `restart` - Stop + start in one command
   - `status` - Lightweight process check
   - `health` - Detailed health information (with optional live probe)

1. **MCPServerSettings** - YAML + environment variable configuration

   - Loads from `settings/example-server.yaml`
   - Environment variable overrides (`MCP_SERVER_*`)
   - Local overrides (`settings/local.yaml`, gitignored)

1. **Custom Handlers** - Server-specific lifecycle hooks

   - `start_handler()` - Initialize server after PID created
   - `stop_handler()` - Cleanup before shutdown
   - `health_probe_handler()` - Live health checks

1. **Signal Handling** - Graceful shutdown on SIGTERM/SIGINT

   - Automatic cleanup on Ctrl+C
   - PID file removal
   - Health snapshot updates

1. **Custom Commands** - Extend CLI with server-specific commands

   - `config` - Display server configuration
   - `paths` - Show cache file locations
   - `stats` - Server statistics

1. **Security-First** - Built-in safety features

   - File permissions (0o600 for PID/snapshots, 0o700 for cache dir)
   - Cache ownership validation
   - Process validation with command line checking
   - Stale PID detection and recovery

### Architecture Pattern

```python
from mcp_common.cli import MCPServerCLIFactory, MCPServerSettings

# 1. Load settings (YAML + env vars)
settings = MCPServerSettings.load("example-server")

# 2. Create CLI factory with custom handlers
factory = MCPServerCLIFactory(
    server_name="example-server",
    settings=settings,
    start_handler=start_server,  # Your server init
    stop_handler=stop_server,  # Your cleanup
    health_probe_handler=check_health,  # Optional health checks
)

# 3. Create Typer app with standard commands
app = factory.create_app()


# 4. Add custom commands
@app.command()
def custom():
    print("Custom command!")


# 5. Run CLI
app()
```

### Configuration

Edit `examples/settings/example-server.yaml`:

```yaml
server_name: "Example MCP Server"
cache_root: .oneiric_cache
health_ttl_seconds: 60.0
log_level: INFO

# Custom fields
custom_port: 8080
custom_feature_enabled: true
```

Or use environment variables:

```bash
export MCP_SERVER_LOG_LEVEL=DEBUG
export MCP_SERVER_CUSTOM_PORT=9090
python examples/cli_server.py start
```

### Exit Codes

The CLI uses standardized exit codes:

- `0` - Success
- `1` - General error
- `2` - Server not running (status/stop)
- `3` - Server already running (start)
- `4` - Health check failed
- `5` - Configuration error
- `6` - Permission error
- `7` - Timeout
- `8` - Stale PID file (use `--force`)

### Testing the Lifecycle

```bash
# Clean start
python examples/cli_server.py start
# Output: Server started (PID 12345)

# Check it's running
python examples/cli_server.py status
# Output: Server running (PID 12345, snapshot age: 2.3s, fresh: True)

# Try starting again (fails)
python examples/cli_server.py start
# Output: Error: Server already running (PID 12345)
# Exit code: 3

# Force restart
python examples/cli_server.py restart --force
# Output: Server stopped gracefully
#         Server started (PID 12346)

# Graceful shutdown
python examples/cli_server.py stop
# Output: Server stopped gracefully
```

______________________________________________________________________

## Weather MCP Server (Oneiric-Native) - v0.3.6

A production-ready weather API server showcasing Oneiric-native mcp-common components:

### Features Demonstrated

1. **HTTPClientAdapter** - Connection pooling for 11x performance improvement
1. **MCPBaseSettings** - YAML + environment variable configuration
1. **ServerPanels** - Beautiful Rich UI terminal output
1. **Global Instance Pattern** - Clean, direct instantiation
1. **FastMCP Integration** - MCP protocol tools and resources (optional; install separately)

### Quick Start

```bash
# Run the example server
cd examples
pip install fastmcp  # required to run the example
python weather_server.py
```

You'll see beautiful terminal output like this:

```
╭──────────────────────────── Weather MCP ────────────────────────────╮
│                                                                      │
│  ✅ Weather MCP started successfully!                                │
│  Version: 2.0.0                                                      │
│                                                                      │
│  Available Features:                                                 │
│    • Current weather by city                                         │
│    • 5-day weather forecast                                          │
│    • Multiple temperature units                                      │
│    • Connection pooling (11x faster)                                 │
│                                                                      │
│  Configuration:                                                      │
│    • Api Provider: OpenWeatherMap                                    │
│    • Http Pooling: 50 connections                                    │
│                                                                      │
│  Started at: 2025-10-26 22:45:00                                     │
│                                                                      │
╰──────────────────────────────────────────────────────────────────────╯
```

### Configuration

#### Option 1: YAML File (Recommended)

Edit `settings/weather.yaml`:

```yaml
api_key: "your_openweathermap_api_key"
base_url: "https://api.openweathermap.org/data/2.5"
timeout: 10
http_max_connections: 50
```

#### Option 2: Environment Variables

```bash
export WEATHER_API_KEY="your_openweathermap_api_key"
export WEATHER_TIMEOUT=30
export WEATHER_HTTP_MAX_CONNECTIONS=100
python weather_server.py
```

#### Option 3: Local Overrides (Gitignored)

Create `settings/local.yaml` for development:

```yaml
# settings/local.yaml - gitignored, won't be committed
api_key: "dev_key_here"
enable_debug_mode: true
log_level: "DEBUG"
```

### Available MCP Tools

#### `get_current_weather`

Get real-time weather data for any city:

```python
# MCP tool call
result = await get_current_weather(city="London", units="metric")

# Returns:
{
    "city": "London",
    "country": "GB",
    "temperature": 15.2,
    "feels_like": 13.8,
    "description": "cloudy",
    "humidity": 72,
    "wind_speed": 4.5,
    "units": "metric",
}
```

#### `get_forecast`

Get 1-5 day weather forecast:

```python
# MCP tool call
result = await get_forecast(city="New York", days=3, units="imperial")

# Returns list of forecasts:
[
    {"date": "2025-10-27", "temperature": 68.5, "description": "sunny", "humidity": 45},
    # ... more days
]
```

## Architecture Patterns

### 1. Oneiric Settings Pattern

```python
from mcp_common import MCPBaseSettings


class WeatherSettings(MCPBaseSettings):
    """Extends MCPBaseSettings for YAML + env var config."""

    api_key: str = "demo"
    base_url: str = "https://api.example.com"
    timeout: int = 10


# Load with layered configuration
settings = WeatherSettings.load("weather")
```

**Benefits:**

- Automatic YAML file loading from `settings/{name}.yaml`
- Environment variable overrides
- Type validation with Pydantic
- Path expansion (`~/` → home directory)

### 2. Connection-Pooled HTTP Client

```python
from mcp_common import HTTPClientAdapter, HTTPClientSettings

# Configure HTTP client
http_settings = HTTPClientSettings(
    timeout=10,
    max_connections=50,
    max_keepalive_connections=10,
)

# Create global adapter instance
http_adapter = HTTPClientAdapter(settings=http_settings)

# Use in tools - client is reused (11x faster!)
response = await http_adapter.get("https://api.example.com/data")

# Cleanup on shutdown
await http_adapter._cleanup_resources()
```

**Benefits:**

- 11x performance improvement vs per-request clients
- Automatic connection reuse
- Configurable pool size
- Built-in retry logic

### 3. Beautiful Terminal UI

```python
from mcp_common import ServerPanels

# Startup success panel
ServerPanels.startup_success(
    server_name="My MCP Server",
    version="1.0.0",
    features=["Feature 1", "Feature 2"],
)

# Error handling with suggestions
ServerPanels.error(
    title="API Error",
    message="Connection failed",
    suggestion="Check your API key",
    error_type="ConnectionError",
)

# Status tables
ServerPanels.status_table(
    title="Health Check",
    rows=[
        ("API", "✅ Healthy", "Response: 23ms"),
        ("Database", "✅ Healthy", "Connections: 5/20"),
    ],
)
```

**Benefits:**

- Consistent, professional UI across all MCP servers
- Rich formatting with colors and emojis
- Tables, panels, and status displays
- Error messages with actionable suggestions

### 4. Global Instance Pattern

```python
# Global instances (initialized in main())
settings: WeatherSettings
http_adapter: HTTPClientAdapter


async def main():
    global settings, http_adapter

    # Initialize settings
    settings = WeatherSettings.load("weather")

    # Create HTTP adapter
    http_settings = HTTPClientSettings(timeout=settings.timeout)
    http_adapter = HTTPClientAdapter(settings=http_settings)

    # Run server
    try:
        await mcp.run()
    finally:
        await http_adapter._cleanup_resources()


# Use in MCP tools - access global instances
@mcp.tool()
async def my_tool() -> dict:
    response = await http_adapter.get(settings.base_url)
    return response.json()
```

**Benefits:**

- Simple, direct instantiation
- Easy to understand and debug
- No framework magic
- Explicit lifecycle management
- Testable with standard mocking

## Testing Your Server

```python
import pytest
from unittest.mock import AsyncMock


@pytest.fixture
def mock_http_adapter():
    """Create mock HTTP adapter for testing."""
    mock = AsyncMock()
    mock.get.return_value.json.return_value = {
        "name": "London",
        "sys": {"country": "GB"},
        "main": {"temp": 15.2, "feels_like": 13.8, "humidity": 72},
        "weather": [{"description": "sunny"}],
        "wind": {"speed": 4.5},
    }
    return mock


@pytest.mark.asyncio
async def test_get_current_weather(mock_http_adapter):
    """Test weather tool with mocked HTTP client."""
    # Replace global instance with mock
    global http_adapter
    http_adapter = mock_http_adapter

    # Test tool
    result = await get_current_weather("London")

    assert result["temperature"] == 15.2
    assert result["description"] == "sunny"
    mock_http_adapter.get.assert_called_once()
```

## Next Steps

1. **Get an API Key**: Sign up at [OpenWeatherMap](https://openweathermap.org/api)
1. **Configure**: Update `settings/weather.yaml` or set `WEATHER_API_KEY` env var
1. **Run**: `python weather_server.py`
1. **Customize**: Adapt this example for your own MCP server

## Learn More

- [mcp-common Documentation](../README.md)
- [FastMCP](https://github.com/jlowin/fastmcp)
- [Model Context Protocol](https://modelcontextprotocol.io)
