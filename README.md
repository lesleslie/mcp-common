# mcp-common

**Version:** 2.0.0 (ACB-Native)
**Status:** Implementation Phase

---

## Overview

mcp-common is an **ACB-native foundation library** for building production-grade MCP (Model Context Protocol) servers. Built on the Asynchronous Component Base (ACB) framework, it provides battle-tested patterns extracted from 9 production servers including crackerjack, session-mgmt-mcp, and fastblocks.

**🎯 What This Library Provides:**
- **ACB Adapters** - HTTP client, rate limiter, security with lifecycle management
- **Structured Logging** - ACB Logger with context binding and correlation IDs
- **Rich Console UI** - Beautiful panels and notifications for server operations
- **Settings Management** - YAML + environment variable configuration
- **Dependency Injection** - Testable, modular architecture
- **Tool Patterns** - Proven organization from production servers

**⚠️ Prerequisites:** Understanding of ACB is required. See [`docs/ACB_FOUNDATION.md`](./docs/ACB_FOUNDATION.md) for:
- What ACB is and why it's required
- Core ACB concepts
- Getting started guide

**Design Principles:**
1. **ACB-Native** - Built on ACB's component system, not layered on top
2. **Production-Ready** - Extracted from real production systems
3. **Dependency Injection** - Uses ACB's `depends` throughout
4. **Rich UI** - Professional console output with Rich panels
5. **Type-safe** - Full type hints with crackerjack checking
6. **Well-Tested** - 90% coverage minimum

---

## 📚 Examples

See [`examples/`](./examples/) for a complete production-ready Weather MCP server demonstrating:
- HTTPClientAdapter with connection pooling (11x performance)
- MCPBaseSettings with YAML + environment configuration
- ServerPanels for beautiful terminal UI
- ACB dependency injection and lifecycle
- FastMCP tool integration

**Run the example:**
```bash
cd examples
python weather_server.py
```

**Full documentation:** [`examples/README.md`](./examples/README.md)

---

## Quick Start

### Installation

```bash
pip install mcp-common>=2.0.0
```

This automatically installs ACB and all required dependencies.

### Minimal Example

```python
# my_server/__init__.py
from acb import register_pkg

# Register package with ACB (REQUIRED)
register_pkg("my_server")

# my_server/settings.py
from mcp_common.config import MCPBaseSettings
from pydantic import Field

class MyServerSettings(MCPBaseSettings):
    """Server configuration using ACB Settings.

    Loads from:
    1. settings/local.yaml
    2. settings/my-server.yaml
    3. Environment variables MY_SERVER_*
    4. Defaults below
    """
    api_key: str = Field(description="API key for service")
    timeout: int = Field(default=30, description="Request timeout")

# my_server/main.py
from fastmcp import FastMCP
from acb.depends import depends
from mcp_common import ServerPanels, HTTPClientAdapter
from my_server.settings import MyServerSettings

# Initialize
mcp = FastMCP("MyServer")
settings = MyServerSettings()

# Define tools
@mcp.tool()
async def call_api():
    # Get adapter from DI container
    http = depends(HTTPClientAdapter)
    client = await http._create_client()

    # Make request
    response = await client.get("https://api.example.com")
    return response.json()

# Run server
if __name__ == "__main__":
    # Display startup panel
    ServerPanels.startup_success(
        server_name="My MCP Server",
        http_endpoint="http://localhost:8000",
        features=["HTTP Client", "Rate Limiting"]
    )

    mcp.run()
```

---

## Core Features

### 🔌 ACB Adapters with Lifecycle Management

**HTTP Client Adapter:**
- Connection pooling (11x faster than creating clients per request)
- Automatic initialization and cleanup
- Configurable via ACB Settings

```python
from acb.depends import depends
from mcp_common.adapters.http import HTTPClientAdapter

http = depends(HTTPClientAdapter)
client = await http._create_client()
```

**Rate Limiter Adapter:**
- Token bucket algorithm
- Per-identifier limiting (user, IP, API key)
- Structured logging of rate limit events

```python
from mcp_common.adapters.rate_limit import RateLimiterAdapter, rate_limit

@mcp.tool()
@rate_limit(requests=100, window=60)  # 100 req/min
async def expensive_operation():
    ...
```

### ⚙️ ACB Settings with YAML Support

- Extends `acb.config.Settings`
- Load from YAML files + environment variables
- Type validation with Pydantic
- Path expansion (`~` → home directory)

```python
from mcp_common.config import MCPBaseSettings

class ServerSettings(MCPBaseSettings):
    api_key: str  # Required
    timeout: int = 30  # Optional with default
```

### 📝 Structured Logging (ACB Logger)

- Automatic injection into adapters
- Context binding with correlation IDs
- JSON output for log aggregation

```python
# In adapters - logger is injected automatically
from acb.adapters.logger import LoggerProtocol

class MyAdapter(AdapterBase):
    logger: LoggerProtocol  # ACB injects this

    async def do_work(self):
        self.logger.info("Processing", item_id="abc123")
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
    features=["Rate Limiting", "Security Filters"]
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

---

## Documentation

- **[ACB_FOUNDATION.md](./docs/ACB_FOUNDATION.md)** - **START HERE** - ACB prerequisites and concepts
- **[ARCHITECTURE.md](./ARCHITECTURE.md)** - Technical design and ACB patterns
- **[IMPLEMENTATION_PLAN.md](./IMPLEMENTATION_PLAN.md)** - Adoption roadmap and migration guide
- **[docs/MCP_ECOSYSTEM_CRITICAL_AUDIT.md](./docs/MCP_ECOSYSTEM_CRITICAL_AUDIT.md)** - Analysis of 9 production servers

---

## Complete Example

See [`examples/complete_server/`](./examples/complete_server/) for a full working MCP server using mcp-common v2.0 patterns.

### Key Patterns Demonstrated:

1. **Package Registration** - `register_pkg("server_name")`
2. **ACB Settings** - YAML + environment variable configuration
3. **Adapter Usage** - HTTPClientAdapter from DI
4. **Rate Limiting** - `@rate_limit` decorator
5. **Structured Logging** - ACB Logger with context
6. **Rich UI** - ServerPanels for startup/errors
7. **Tool Organization** - Modular tool registration
8. **Testing** - DI-based testing patterns

---

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

---

## ACB Integration Patterns

### Pattern 1: Creating an Adapter

```python
# my_server/adapters/email.py
from acb.config import AdapterBase, Settings
from acb.adapters.logger import LoggerProtocol
from acb.adapters import AdapterStatus
from uuid import UUID
from contextlib import suppress

# Static UUID7 - generated once, hardcoded
MODULE_ID = UUID("01947e12-5678-7abc-9def-1a2b3c4d5e6f")
MODULE_STATUS = AdapterStatus.STABLE

class EmailSettings(Settings):
    smtp_host: str = "smtp.example.com"
    smtp_port: int = 587

class EmailAdapter(AdapterBase):
    settings: EmailSettings | None = None
    logger: LoggerProtocol  # ACB injects

    def __init__(self, **kwargs):
        super().__init__(**kwargs)  # REQUIRED
        if self.settings is None:
            self.settings = EmailSettings()

    async def _create_client(self):
        """Lazy initialization."""
        # Initialize SMTP client
        self.logger.info("SMTP client initialized")

    async def _cleanup_resources(self):
        """Cleanup on shutdown."""
        # Close SMTP connection
        self.logger.info("SMTP client closed")

# Auto-register
with suppress(Exception):
    depends.set(EmailAdapter)
```

### Pattern 2: Using Adapters in Tools

```python
from acb.depends import depends
from mcp_common.adapters.http import HTTPClientAdapter
from mcp_common.adapters.rate_limit import rate_limit

@mcp.tool()
@rate_limit(requests=100, window=60)
async def send_request():
    # Get adapter from DI
    http = depends(HTTPClientAdapter)

    # Use adapter
    client = await http._create_client()
    response = await client.post("https://api.example.com")

    return {"success": response.status_code == 200}
```

### Pattern 3: Testing with DI

```python
from acb.depends import depends

def test_my_tool():
    # Create mock adapter
    mock_http = MockHTTPClientAdapter()

    # Override in DI container
    depends.set(HTTPClientAdapter, mock_http)

    # Test uses mock
    result = await my_tool()
    assert mock_http.called
```

---

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

---

## Migration from v1.x

**Breaking Changes in v2.0:**
- ACB is now **required** (was optional in v1.x)
- HTTP client is now `HTTPClientAdapter` (was `get_http_client()` function)
- Logging uses ACB Logger (no custom `MCPLogger` wrapper)
- Rate limiting is an adapter (not standalone decorator)
- Settings extend `acb.config.Settings` (not raw Pydantic)

**Migration Guide:** See [IMPLEMENTATION_PLAN.md](./IMPLEMENTATION_PLAN.md) for step-by-step migration instructions.

---

## Versioning

**Semantic Versioning:**
- **2.0.0** - ACB-native redesign (current)
- **2.1.0** - Additional adapters (security, caching)
- **2.2.0** - Enhanced testing utilities
- **3.0.0** - Breaking changes (if needed)

**ACB Compatibility:**
- Requires `acb>=0.19.0`
- Compatible with FastMCP 2.0+
- Python 3.13+ required

---

## Success Metrics

**v2.0 is successful if:**
1. ✅ All 9 MCP servers adopt ACB-native patterns
2. ✅ Zero production incidents caused by mcp-common
3. ✅ Ecosystem health improves from 74/100 to 85/100
4. ✅ Test coverage >90%
5. ✅ Professional Rich UI in all servers
6. ✅ Unified logging/settings/console across ecosystem

---

## License

BSD-3-Clause License - See [LICENSE](./LICENSE) for details

---

## Contributing

Contributions are welcome! Please:
1. Read [`docs/ACB_FOUNDATION.md`](./docs/ACB_FOUNDATION.md) first
2. Follow ACB patterns (see examples)
3. Fork and create feature branch
4. Add tests (coverage ≥90%)
5. Ensure all quality checks pass
6. Submit pull request

---

## Acknowledgments

Built with patterns extracted from 9 production MCP servers:

**Primary Pattern Sources:**
- **crackerjack** - MCP server structure, Rich UI panels, rate limiting
- **session-mgmt-mcp** - ACB Settings patterns, DI configuration
- **fastblocks** - ACB adapter organization

**Additional Contributors:**
- raindropio-mcp (HTTP client patterns)
- excalidraw-mcp (testing patterns)
- opera-cloud-mcp
- mailgun-mcp
- unifi-mcp
- ACB core (component system)

Special thanks to the ACB framework for providing the foundation that makes this library possible.

---

## Support

- **Documentation:** [`docs/`](./docs/)
- **Issues:** [GitHub Issues](https://github.com/lesaker/mcp-common/issues)
- **Discussions:** [GitHub Discussions](https://github.com/lesaker/mcp-common/discussions)

---

**Ready to get started?** Read [`docs/ACB_FOUNDATION.md`](./docs/ACB_FOUNDATION.md) to understand ACB fundamentals, then check out [`examples/complete_server/`](./examples/complete_server/) for a working example!
