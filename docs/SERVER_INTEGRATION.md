# MCP Server Integration Guide

This guide explains how to integrate mcp-common into MCP servers using the enhanced CLI factory and server utilities.

## Overview

mcp-common v0.4.0 provides two major enhancements for MCP servers:

1. **Server Module** (`mcp_common.server/`) - Reusable lifecycle components
1. **Enhanced CLI Factory** - Single factory for all MCP servers (handler + server class patterns)

### Architecture Patterns

All MCP servers should use `mcp_common.cli.MCPServerCLIFactory`.

#### Pattern 1: Server Class (Simple MCP Servers)

Best for: mailgun-mcp, raindropio-mcp, opera-cloud-mcp, unifi-mcp, excalidraw-mcp

**Characteristics:**

- OOP approach with server class
- Clean lifecycle methods (`startup()`, `shutdown()`)
- Uses Oneiric runtime components

**Example:**

```python
from mcp_common.cli import MCPServerCLIFactory
from mcp_common.server import BaseOneiricServerMixin, create_runtime_components
from oneiric.core.config import OneiricMCPConfig

class MyConfig(OneiricMCPConfig):
    http_port: int = 3040

class MyMCPServer(BaseOneiricServerMixin):
    def __init__(self, config):
        self.config = config
        self.runtime = create_runtime_components("my-server", ".oneiric_cache")

    async def startup(self):
        await self.runtime.initialize()
        await self._create_startup_snapshot(custom_components={
            "api": {"status": "connected"}
        })

    async def shutdown(self):
        await self._create_shutdown_snapshot()
        await self.runtime.cleanup()

    async def health_check(self):
        base_components = await self._build_health_components()
        base_components.extend([
            self.runtime.health_monitor.create_component_health(
                name="api",
                status=HealthStatus.HEALTHY,
                details={"endpoint": self.config.api_url}
            )
        ])
        return self.runtime.health_monitor.create_health_response(base_components)

    def get_app(self):
        return self.mcp.http_app

def main():
    factory = MCPServerCLIFactory.create_server_cli(
        server_class=MyMCPServer,
        config_class=MyConfig,
        name="my-server",
    )
    factory.run()
```

#### Pattern 2: Handler Functions (Complex Servers)

Best for: crackerjack, session-buddy

**Characteristics:**

- Procedural approach with handler functions
- Custom lifecycle management
- Direct control over startup/shutdown

**Example:**

```python
from mcp_common.cli import MCPServerCLIFactory

def start_handler():
    # Custom startup logic
    config = MyConfig()
    server = MyServer(config)
    asyncio.run(server.startup())

def stop_handler(signum):
    # Custom shutdown logic
    asyncio.run(server.shutdown())

factory = MCPServerCLIFactory(
    server_name="complex-server",
    start_handler=start_handler,
    stop_handler=stop_handler,
)
app = factory.create_app()
app()
```

## Migration from oneiric.core.cli

### Before (oneiric.core.cli)

```python
from oneiric.core.cli import MCPServerCLIFactory
from oneiric.core.config import OneiricMCPConfig
from oneiric.runtime.cache import RuntimeCacheManager
from oneiric.runtime.mcp_health import HealthMonitor, HealthStatus
from oneiric.runtime.snapshot import RuntimeSnapshotManager

class MyConfig(OneiricMCPConfig):
    http_port: int = 3040

class MyMCPServer:
    def __init__(self, config):
        self.config = config
        self.app = create_app()

        # Manual runtime initialization (30 lines)
        self.snapshot_manager = RuntimeSnapshotManager(
            cache_dir=".oneiric_cache",
            server_name="my-server",
        )
        self.cache_manager = RuntimeCacheManager(
            cache_dir=".oneiric_cache",
            server_name="my-server",
        )
        self.health_monitor = HealthMonitor(server_name="my-server")

    async def startup(self):
        await self.snapshot_manager.initialize()
        await self.cache_manager.initialize()

        # Manual snapshot creation (20 lines)
        components = {
            "server": {
                "status": "started",
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "config": {
                    "http_port": self.config.http_port,
                    "http_host": self.config.http_host,
                },
            },
        }
        await self.snapshot_manager.create_snapshot(components)

    async def health_check(self):
        # Manual component building (15 lines)
        cache_stats = await self.cache_manager.get_cache_stats()
        components = [
            self.health_monitor.create_component_health(
                name="cache",
                status=HealthStatus.HEALTHY,
                details={
                    "entries": cache_stats["total_entries"],
                    "initialized": cache_stats["initialized"],
                },
            ),
        ]
        return self.health_monitor.create_health_response(components)

def main():
    cli_factory = MCPServerCLIFactory(
        server_class=MyMCPServer,
        config_class=MyConfig,
        name="my-server",
        use_subcommands=True,
        legacy_flags=False,
    )
    cli_factory.run()
```

**Lines of code:** ~170 lines

### After (mcp_common.cli)

```python
from mcp_common.cli import MCPServerCLIFactory
from mcp_common.server import BaseOneiricServerMixin, create_runtime_components
from oneiric.core.config import OneiricMCPConfig

class MyConfig(OneiricMCPConfig):
    http_port: int = 3040

class MyMCPServer(BaseOneiricServerMixin):
    def __init__(self, config):
        self.config = config
        self.app = create_app()

        # Helper initialization (1 line)
        self.runtime = create_runtime_components("my-server", ".oneiric_cache")

    async def startup(self):
        await self.runtime.initialize()

        # Template method with customization (3 lines)
        await self._create_startup_snapshot(custom_components={
            "api": {"status": "connected"}
        })

    async def health_check(self):
        # Template method (3 lines)
        base_components = await self._build_health_components()
        return self.runtime.health_monitor.create_health_response(base_components)

    def get_app(self):
        return self.app.http_app

def main():
    cli_factory = MCPServerCLIFactory.create_server_cli(
        server_class=MyMCPServer,
        config_class=MyConfig,
        name="my-server",
    )
    cli_factory.run()
```

**Lines of code:** ~80 lines

**Reduction:** ~90 lines (~53% reduction)

## New Features

### 1. BaseOneiricServerMixin

Provides reusable template methods for common operations:

**`_init_runtime_components(server_name, cache_dir=None)`**

- Initialize runtime components
- Returns `RuntimeComponents` container
- Uses `self.config.cache_dir` if cache_dir not provided

**`_create_startup_snapshot(custom_components=None)`**

- Create startup snapshot with standard + custom components
- Standard components: server status, timestamp, config
- Merge in custom components via dict

**`_create_shutdown_snapshot()`**

- Create shutdown snapshot
- Marks server as stopped

**`_build_health_components()`**

- Build standard health check components
- Returns list of component health objects
- Add server-specific components before calling `create_health_response()`

**`_extract_config_snapshot()`**

- Extract config values for snapshots
- Override to add server-specific fields
- Automatically includes http_port, http_host, debug, etc.

### 2. Runtime Components Factory

**`create_runtime_components(server_name, cache_dir)`**

Factory function that creates and initializes:

- `RuntimeSnapshotManager` - State snapshots
- `RuntimeCacheManager` - Cached data with TTL
- `HealthMonitor` - Component health tracking

**Before (30 lines):**

```python
self.snapshot_manager = RuntimeSnapshotManager(
    cache_dir=".oneiric_cache",
    server_name="my-server",
)
self.cache_manager = RuntimeCacheManager(
    cache_dir=".oneiric_cache",
    server_name="my-server",
)
self.health_monitor = HealthMonitor(server_name="my-server")

await self.snapshot_manager.initialize()
await self.cache_manager.initialize()
```

**After (3 lines):**

```python
self.runtime = create_runtime_components("my-server", ".oneiric_cache")
await self.runtime.initialize()
```

### 3. Availability Check Helpers

Centralized optional dependency detection:

```python
from mcp_common.server import (
    check_serverpanels_available,
    check_security_available,
    check_rate_limiting_available,
    get_availability_status,
)

# Check individual dependencies
if check_serverpanels_available():
    from mcp_common.ui import ServerPanels
    ServerPanels.startup_success("my-server", ["Feature 1"])

# Get all availability status
status = get_availability_status()
if status["security"]:
    from mcp_common.security import sanitize_user_input
```

**Before (duplicated across 6 projects):**

```python
import importlib.util

SERVERPANELS_AVAILABLE = (
    importlib.util.find_spec("mcp_common.ui") is not None
)
SECURITY_AVAILABLE = (
    importlib.util.find_spec("mcp_common.security") is not None
)
RATE_LIMITING_AVAILABLE = (
    importlib.util.find_spec("fastmcp.server.middleware.rate_limiting") is not None
)
```

**After (centralized in mcp-common):**

```python
from mcp_common.server import get_availability_status

status = get_availability_status()
# {"serverpanels": True, "security": True, "rate_limiting": False}
```

### 4. Enhanced CLI Factory

**`MCPServerCLIFactory.create_server_cli()`**

Class method that bridges server_class pattern to handler pattern:

```python
factory = MCPServerCLIFactory.create_server_cli(
    server_class=MyMCPServer,
    config_class=MyConfig,
    name="my-server",
    description="My MCP Server",
)
```

**Benefits over oneiric.core.cli:**

- ✅ Production features (PID files, signal handling, health persistence)
- ✅ Automatic uvicorn integration
- ✅ Graceful shutdown with cleanup
- ✅ Health probe support
- ✅ Same factory for all MCP servers

## Server Requirements

When using `create_server_cli()`, your server class must have:

### Required Methods

1. **`__init__(config)`** - Initialize with config object

   ```python
   def __init__(self, config):
       self.config = config
       # ... initialize server ...
   ```

1. **`async startup()`** - Startup lifecycle

   ```python
   async def startup(self):
       await self.runtime.initialize()
       # ... startup logic ...
   ```

1. **`async shutdown()`** - Shutdown lifecycle

   ```python
   async def shutdown(self):
       await self._create_shutdown_snapshot()
       await self.runtime.cleanup()
   ```

1. **`get_app()`** - Return ASGI application

   ```python
   def get_app(self):
       return self.mcp.http_app
   ```

### Optional Methods

5. **`async health_check()`** - Health check probe
   ```python
   async def health_check(self) -> HealthCheckResponse:
       components = await self._build_health_components()
       # Add server-specific components
       return self.runtime.health_monitor.create_health_response(components)
   ```

## CLI Commands

All servers get these standard commands:

```bash
# Start the server
python -m my_server start

# Stop the server
python -m my_server stop

# Restart the server
python -m my_server restart

# Check status
python -m my_server status

# Health check
python -m my_server health

# Health check with probe
python -m my_server health --probe
```

### JSON Output Mode

All commands support `--json` flag for programmatic output:

```bash
python -m my_server status --json
# {"status": "running", "pid": 12345, "uptime": 3600}

python -m my_server health --json
# {"status": "healthy", "components": [...]}
```

## Configuration

### Settings File (YAML)

Create `settings/<server-name>.yaml`:

```yaml
# settings/my-server.yaml
http_port: 3040
http_host: "127.0.0.1"
enable_http_transport: true
cache_dir: ".oneiric_cache"
log_level: "INFO"
```

### Environment Variables

Override with environment variables:

```bash
export MY_SERVER_HTTP_PORT=3040
export MY_SERVER_CACHE_DIR="/var/cache/my-server"
python -m my_server start
```

### Environment Variable Prefix

The prefix is derived from the config class:

```python
class MyConfig(OneiricMCPConfig):
    class Config:
        env_prefix = "MY_SERVER_"  # Prefix for environment variables
```

## Testing

### Unit Tests

Test server components in isolation:

```python
import pytest
from unittest.mock import AsyncMock

@pytest.fixture
def mock_runtime():
    runtime = AsyncMock()
    runtime.initialize = AsyncMock()
    runtime.snapshot_manager.create_snapshot = AsyncMock()
    return runtime

@pytest.mark.asyncio
async def test_startup(mock_runtime):
    server = MyMCPServer(config)
    server.runtime = mock_runtime

    await server.startup()

    mock_runtime.initialize.assert_called_once()
    mock_runtime.snapshot_manager.create_snapshot.assert_called_once()
```

### Integration Tests

Test CLI commands:

```bash
# Test start command
python -m my_server start &
PID=$!

# Wait for startup
sleep 2

# Test status command
python -m my_server status

# Test health command
python -m my_server health --probe

# Cleanup
kill $PID
```

## Migration Checklist

Use this checklist when migrating an existing server:

### Step 1: Update Dependencies

```bash
cd /path/to/your-mcp-server
uv add mcp-common>=0.4.0
```

### Step 2: Update Imports

```python
# Remove old imports
- from oneiric.core.cli import MCPServerCLIFactory
- from oneiric.runtime.cache import RuntimeCacheManager
- from oneiric.runtime.mcp_health import HealthMonitor, HealthStatus
- from oneiric.runtime.snapshot import RuntimeSnapshotManager

# Add new imports
+ from mcp_common.cli import MCPServerCLIFactory
+ from mcp_common.server import (
+     BaseOneiricServerMixin,
+     create_runtime_components,
+ )
+ from oneiric.core.config import OneiricMCPConfig
```

### Step 3: Refactor Server Class

1. Add `BaseOneiricServerMixin` to inheritance
1. Replace manual runtime init with `create_runtime_components()`
1. Replace manual snapshot creation with `_create_startup_snapshot()`
1. Replace manual health component building with `_build_health_components()`
1. Remove `RuntimeSnapshotManager`, `RuntimeCacheManager`, `HealthMonitor` attributes

### Step 4: Update main()

```python
# Before
def main():
    cli_factory = MCPServerCLIFactory(
        server_class=MyMCPServer,
        config_class=MyConfig,
        name="my-server",
        use_subcommands=True,
        legacy_flags=False,
    )
    cli_factory.run()

# After
def main():
    cli_factory = MCPServerCLIFactory.create_server_cli(
        server_class=MyMCPServer,
        config_class=MyConfig,
        name="my-server",
    )
    cli_factory.run()
```

### Step 5: Test Thoroughly

```bash
# Test all CLI commands
python -m my_server start --help
python -m my_server status
python -m my_server health --probe

# Test with Claude Desktop
# Add to .mcp.json, invoke tools, verify functionality
```

## Troubleshooting

### Server Won't Start

**Problem:** Server fails to start with import error

**Solution:** Ensure mcp-common is installed:

```bash
uv add mcp-common>=0.4.0
uv sync
```

### Health Check Fails

**Problem:** Health check returns "unhealthy"

**Solution:** Ensure `health_check()` method returns `HealthCheckResponse`:

```python
async def health_check(self) -> HealthCheckResponse:
    components = await self._build_health_components()
    return self.runtime.health_monitor.create_health_response(components)
```

### Runtime Components Not Initialized

**Problem:** `AttributeError: 'RuntimeComponents' object has no attribute 'snapshot_manager'`

**Solution:** Call `await runtime.initialize()` before using components:

```python
async def startup(self):
    await self.runtime.initialize()  # Must call first!
    await self._create_startup_snapshot()
```

### Config Not Loading

**Problem:** Server uses default values instead of YAML config

**Solution:** Ensure config class has correct `env_prefix`:

```python
class MyConfig(OneiricMCPConfig):
    class Config:
        env_prefix = "MY_SERVER_"
        env_file = ".env"
```

## Examples

See `examples/` directory for complete working examples:

- **`examples/weather_server.py`** - Simple weather MCP server
- **`examples/cli_server.py`** - Complete CLI example with all features

## Performance Considerations

### Connection Pooling

Use `HTTPClientAdapter` for HTTP connections:

```python
from mcp_common.adapters.http import HTTPClientAdapter

class MyServer(BaseOneiricServerMixin):
    def __init__(self, config):
        self.config = config
        self.http_adapter = HTTPClientAdapter(
            timeout=self.config.timeout,
            max_connections=50,
        )
```

### Caching

Use runtime cache for expensive operations:

```python
async def fetch_data(self, key: str):
    # Check cache first
    cached = await self.runtime.cache_manager.get(key)
    if cached:
        return cached

    # Fetch from API
    data = await self.http_adapter.get(url)

    # Cache with TTL
    await self.runtime.cache_manager.set(key, data, ttl=3600)
    return data
```

### Rate Limiting

Use FastMCP rate limiting middleware:

```python
from mcp_common.server import check_rate_limiting_available

if check_rate_limiting_available():
    from fastmcp.server.middleware.rate_limiting import RateLimitingMiddleware

    rate_limiter = RateLimitingMiddleware(
        max_requests_per_second=10.0,
        burst_capacity=20,
    )
    app._mcp_server.add_middleware(rate_limiter)
```

## Best Practices

### 1. Use Template Methods

Leverage `_create_startup_snapshot()` and `_build_health_components()`:

```python
async def startup(self):
    await self.runtime.initialize()
    # Use template method
    await self._create_startup_snapshot(custom_components={
        "api": {"status": "connected"}
    })
```

### 2. Override for Customization

Override `_extract_config_snapshot()` to add custom fields:

```python
def _extract_config_snapshot(self):
    base = super()._extract_config_snapshot()
    base["custom_field"] = self.config.custom_value
    return base
```

### 3. Use Availability Checks

Check optional dependencies before importing:

```python
from mcp_common.server import check_serverpanels_available

if check_serverpanels_available():
    from mcp_common.ui import ServerPanels
    ServerPanels.startup_success("my-server", ["Feature 1"])
```

### 4. Handle Errors Gracefully

Use try-except in lifecycle methods:

```python
async def startup(self):
    try:
        await self.runtime.initialize()
        await self._create_startup_snapshot()
    except Exception as e:
        logger.error(f"Startup failed: {e}")
        await self.runtime.cleanup()
        raise
```

## Additional Resources

- **`README.md`** - Package overview and quickstart
- **`examples/README.md`** - Example server documentation
- **`docs/ARCHITECTURE.md`** - Technical design details
- **`docs/SECURITY_IMPLEMENTATION.md`** - Security features guide

## Support

For issues or questions:

1. Check existing issues in GitHub
1. Review example servers in `examples/`
1. Consult this documentation
1. Check Oneiric documentation for runtime details
