# mcp-common Examples

This directory contains example ACB-native MCP servers demonstrating best practices with the mcp-common foundation library.

## Weather MCP Server

A production-ready weather API server showcasing all mcp-common components:

### Features Demonstrated

1. **HTTPClientAdapter** - Connection pooling for 11x performance improvement
1. **MCPBaseSettings** - YAML + environment variable configuration
1. **ServerPanels** - Beautiful Rich UI terminal output
1. **ACB Dependency Injection** - Testable, modular architecture
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

### 1. ACB-Native Settings

```python
from mcp_common import MCPBaseSettings


class WeatherSettings(MCPBaseSettings):
    """Extends MCPBaseSettings for YAML + env var config."""

    api_key: str = "demo"
    base_url: str = "https://api.example.com"
    timeout: int = 10
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

# Create adapter (registers with ACB DI)
http_adapter = HTTPClientAdapter(settings=http_settings)
depends.set(http_adapter)

# Use in tools - client is reused (11x faster!)
response = await http_adapter.get("https://api.example.com/data")
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

### 4. Dependency Injection

```python
from acb.depends import depends

# Register components
depends.set(settings)
depends.set(http_adapter)


# Use in MCP tools
@mcp.tool()
async def my_tool() -> dict:
    # Get from DI container (no global state!)
    settings = depends.get_sync(WeatherSettings)
    http = depends.get_sync(HTTPClientAdapter)

    # Use components
    response = await http.get(settings.base_url)
    return response.json()
```

**Benefits:**

- No global state or singletons
- Easy testing with mock dependencies
- Modular, testable architecture
- Automatic lifecycle management

## Testing Your Server

```python
import pytest
from unittest.mock import Mock


@pytest.fixture
def mock_http_adapter():
    """Create mock HTTP adapter for testing."""
    adapter = Mock(spec=HTTPClientAdapter)
    adapter.get = Mock(return_value=Mock(json=lambda: {"temp": 15.2, "description": "sunny"}))
    return adapter


@pytest.mark.asyncio
async def test_get_current_weather(mock_http_adapter):
    """Test weather tool with mocked HTTP client."""
    # Inject mock
    depends.set(mock_http_adapter)

    # Test tool
    result = await get_current_weather("London")

    assert result["temperature"] == 15.2
    assert mock_http_adapter.get.called
```

## Next Steps

1. **Get an API Key**: Sign up at [OpenWeatherMap](https://openweathermap.org/api)
1. **Configure**: Update `settings/weather.yaml` or set `WEATHER_API_KEY` env var
1. **Run**: `python weather_server.py`
1. **Customize**: Adapt this example for your own MCP server

## Learn More

- [mcp-common Documentation](../README.md)
- [ACB Framework](https://github.com/lesleslie/acb)
- [FastMCP](https://github.com/jlowin/fastmcp)
- [Model Context Protocol](https://modelcontextprotocol.io)
