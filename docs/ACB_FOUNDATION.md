# ACB Foundation for mcp-common

**Version:** 1.0.0
**Audience:** Developers using mcp-common v2.0
**Prerequisites:** Python 3.13+, basic async/await knowledge

______________________________________________________________________

## What is ACB?

**ACB (Asynchronous Component Base)** is a foundational framework for building modular, production-grade Python applications. It provides:

- **Adapters** - Reusable components with lifecycle management
- **Dependency Injection** - Testable, decoupled architecture
- **Structured Logging** - Context-aware logging with correlation IDs
- **Rich Console** - Beautiful terminal UI with Rich integration
- **Settings Management** - YAML + environment variable configuration
- **Actions** - Reusable business logic patterns

**Origin:** ACB is the core framework developed for production systems including:

- **crackerjack** - Python code quality automation
- **session-mgmt-mcp** - Claude session management server
- **fastblocks** - Web component framework

**Repository:** [acb on GitHub](https://github.com/yourusername/acb) *(adjust link)*

______________________________________________________________________

## Why mcp-common Requires ACB

**mcp-common v2.0 is ACB-native**, meaning it's built **on top of ACB**, not as a standalone utility library. This architectural decision provides:

### 1. **Unified Logging Across All MCP Servers**

```python
# Every server uses the same structured logger
from acb.adapters.logger import LoggerProtocol


class MyAdapter(AdapterBase):
    logger: LoggerProtocol  # Injected automatically

    def do_work(self):
        # Structured logging with context
        self.logger.info("Processing request", request_id="req-123", user_id="user-456")
```

**Benefits:**

- Consistent log format across all 9 MCP servers
- Automatic correlation IDs for request tracking
- JSON output for log aggregation (e.g., ELK stack)

### 2. **Consistent Settings Management**

```python
# YAML + environment variable configuration
from acb.config import Settings


class ServerSettings(Settings):
    api_key: str  # From YAML or env var
    timeout: int = 30  # Default value
```

**Benefits:**

- Load from `settings/{name}.yaml` files
- Override with environment variables
- Type validation with Pydantic
- Path expansion (`~/.claude/data` → `/Users/you/.claude/data`)

### 3. **Rich Console UI**

```python
# Beautiful terminal output
from acb.console import console
from rich.panel import Panel

panel = Panel("✅ Server started successfully!", title="Mailgun MCP", border_style="green")
console.print(panel)
```

**Benefits:**

- Professional UI like crackerjack
- Consistent styling across servers
- Progress bars, tables, syntax highlighting

### 4. **Dependency Injection for Testability**

```python
# Adapters registered automatically
from acb.depends import depends
from mcp_common.adapters.http import HTTPClientAdapter


@mcp.tool()
async def send_email():
    # Get adapter from DI container
    http_adapter = depends(HTTPClientAdapter)
    client = await http_adapter._create_client()
    # ... use client
```

**Benefits:**

- Easy to mock in tests
- No global state
- Automatic lifecycle management

### 5. **Module Registration and Discovery**

```python
# Automatic component discovery
from acb import register_pkg

register_pkg("mailgun_mcp")  # Makes adapters discoverable
```

**Benefits:**

- Adapters auto-register when imported
- Component metadata tracking
- Version compatibility checks

______________________________________________________________________

## Core ACB Concepts

### 1. **Adapters** - Stateful Components

**What:** Adapters are reusable components with lifecycle management (initialization, operation, cleanup).

**Base Class:**

```python
from acb.config import AdapterBase
from uuid import UUID
from acb.adapters import AdapterStatus


class MyAdapter(AdapterBase):
    """Adapter for doing something useful."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)  # REQUIRED
        # Your initialization

    async def _create_client(self):
        """Create resources (lazy initialization)."""
        # Initialize connections, clients, etc.

    async def _cleanup_resources(self):
        """Cleanup on shutdown."""
        # Close connections, release resources
```

**Key Properties:**

- `MODULE_ID` - Static UUID7 identifier (never changes)
- `MODULE_STATUS` - Maturity level (stable/beta/alpha)
- `logger` - Injected logger (use directly, don't create)
- `settings` - Configuration object

**Example from mcp-common:**

```python
# mcp_common/adapters/http/client.py
from uuid import UUID
from acb.config import AdapterBase, Settings
from acb.adapters import AdapterStatus

# Static ID - generated once, hardcoded forever
MODULE_ID = UUID("01947e12-3b4c-7d8e-9f0a-1b2c3d4e5f6a")
MODULE_STATUS = AdapterStatus.STABLE


class HTTPClientAdapter(AdapterBase):
    settings: HTTPClientSettings | None = None
    logger: LoggerProtocol  # Injected by ACB

    async def _create_client(self):
        # Initialize httpx.AsyncClient with pooling
        ...

    async def _cleanup_resources(self):
        # Close client, release connections
        ...
```

### 2. **Dependency Injection** - The `depends` System

**What:** ACB provides a DI container that automatically provides dependencies to your code.

**Registration (in adapter modules):**

```python
from contextlib import suppress
from acb.depends import depends

# At module level, after class definition
with suppress(Exception):
    depends.set(HTTPClientAdapter)
```

**Why `suppress(Exception)`?** Prevents errors if adapter already registered (e.g., re-imports).

**Usage (in tools):**

```python
from acb.depends import depends


@mcp.tool()
async def my_tool():
    # Get adapter from DI container
    http_adapter = depends(HTTPClientAdapter)

    # Use it
    client = await http_adapter._create_client()
    response = await client.get("https://api.example.com")
```

**Testing with DI:**

```python
from acb.depends import depends


def test_my_tool():
    # Create mock adapter
    mock_adapter = MockHTTPClientAdapter()

    # Override in DI container
    depends.set(HTTPClientAdapter, mock_adapter)

    # Test uses mock
    result = await my_tool()
    assert mock_adapter.called
```

### 3. **Structured Logging** - ACB Logger

**What:** Context-aware logging with automatic correlation IDs.

**Usage in Adapters:**

```python
from acb.config import AdapterBase
from acb.adapters.logger import LoggerProtocol


class MyAdapter(AdapterBase):
    logger: LoggerProtocol  # ACB injects this - don't create it

    async def do_work(self):
        # Simple log
        self.logger.info("Starting work")

        # Structured log with context
        self.logger.info("Processing item", item_id="abc123", user_id="user-456", duration_ms=234)

        # Bind context for multiple logs
        request_logger = self.logger.bind(request_id="req-789")
        request_logger.info("Request started")
        request_logger.info("Request completed")
```

**Usage in Non-Adapter Code:**

```python
from acb.depends import depends
from acb.adapters import import_adapter


async def standalone_function():
    # Get logger from DI
    Logger = import_adapter("logger")
    logger = depends.get_sync(Logger)

    logger.info("Message", context="value")
```

**Log Output:**

```json
{
  "timestamp": "2025-10-26T12:34:56.789Z",
  "level": "INFO",
  "message": "Processing item",
  "item_id": "abc123",
  "user_id": "user-456",
  "duration_ms": 234,
  "correlation_id": "cor-xyz-123",
  "service": "mailgun-mcp",
  "adapter": "http_client"
}
```

### 4. **Settings** - Configuration Management

**What:** Type-safe configuration with YAML + environment variable support.

**Base Class:**

```python
from acb.config import Settings
from pydantic import Field


class MySettings(Settings):
    """Server configuration.

    Loads from:
    1. settings/local.yaml (highest priority)
    2. settings/my-server.yaml
    3. Environment variables MY_SERVER_*
    4. Defaults below (lowest priority)
    """

    # Required field (no default)
    api_key: str = Field(description="API key for authentication")

    # Optional field (has default)
    timeout: int = Field(default=30, description="Request timeout in seconds")

    # Nested settings
    logging: LoggingSettings = LoggingSettings()
```

**YAML Configuration:**

```yaml
# settings/my-server.yaml
api_key: "${MY_API_KEY}"  # From environment
timeout: 60

logging:
  level: "INFO"
  format: "json"
```

**Environment Variables:**

```bash
# Override YAML values
export MY_SERVER_API_KEY="secret-key"
export MY_SERVER_TIMEOUT="90"
```

**Loading:**

```python
# Automatically loads from YAML + env vars
settings = MySettings()

# Access values
print(settings.api_key)  # "secret-key" (from env)
print(settings.timeout)  # 90 (from env override)
```

### 5. **Console** - Rich Terminal UI

**What:** Beautiful terminal output using Rich library.

**Import:**

```python
from acb.console import console  # Pre-configured singleton
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
```

**Usage:**

```python
# Simple colored text
console.print("[green]Success![/green]")
console.print("[red]Error occurred[/red]")

# Panel
panel = Panel("Server started successfully", title="Mailgun MCP", border_style="green")
console.print(panel)

# Table
table = Table(title="Server Stats")
table.add_column("Metric", style="cyan")
table.add_column("Value", style="white")
table.add_row("Requests", "1234")
table.add_row("Errors", "12")
console.print(table)

# Progress bar
from rich.progress import Progress

with Progress() as progress:
    task = progress.add_task("[cyan]Processing...", total=100)
    for i in range(100):
        # Do work
        progress.update(task, advance=1)
```

### 6. **Package Registration** - Component Discovery

**What:** Makes your package's adapters discoverable by ACB.

**Required in `__init__.py`:**

```python
# mailgun_mcp/__init__.py
from acb import register_pkg

# MUST be called before importing adapters
register_pkg("mailgun_mcp")

# Now import your modules
from .main import mcp
from .settings import MailgunSettings
```

**What it does:**

- Registers package with ACB's component system
- Enables adapter auto-discovery
- Tracks package metadata and versions

______________________________________________________________________

## ACB vs mcp-common Boundaries

Understanding what comes from ACB vs mcp-common:

| Feature | Provided By | When to Use |
|---------|-------------|-------------|
| **`AdapterBase`** | ACB Core | Building any custom adapter |
| **`HTTPClientAdapter`** | mcp-common | Need HTTP client with connection pooling |
| | | |
| **`Settings`** | ACB Core | Basic configuration needs |
| **`MCPBaseSettings`** | mcp-common | MCP server configuration (extends `Settings`) |
| **`Logger`** | ACB Core | All logging |
| **`depends`** | ACB Core | All dependency injection |
| **`console`** | ACB Core | All terminal output |
| **`ServerPanels`** | mcp-common | MCP server startup/notification panels |
| **`register_pkg()`** | ACB Core | Package registration |

**Rule of Thumb:**

- **ACB** provides the **foundation** (adapters, DI, logging, settings)
- **mcp-common** provides **MCP-specific implementations** (HTTP client, server panels)

**Example - Custom Adapter:**

```python
# Use ACB base classes
from acb.config import AdapterBase, Settings
from acb.adapters.logger import LoggerProtocol


# Extend for your specific needs
class MyCustomAdapter(AdapterBase):
    logger: LoggerProtocol  # From ACB
    settings: MySettings | None = None  # Your settings

    # Your custom logic
    async def do_custom_work(self):
        self.logger.info("Doing custom work")
        ...
```

**Example - MCP Server:**

```python
# Use mcp-common for standard patterns
from mcp_common import (
    HTTPClientAdapter,  # Standard HTTP client
    # Rate limiting is handled by FastMCP (not part of mcp-common)
    MCPBaseSettings,  # MCP server settings
    ServerPanels,  # Server UI
)

# Use ACB for foundation
from acb.depends import depends
from acb.console import console


# Your MCP-specific logic
@mcp.tool()
async def send_email():
    http = depends(HTTPClientAdapter)
    # ... your logic
```

______________________________________________________________________

## Getting Started with ACB

### Installation

```bash
# ACB is a required dependency of mcp-common
pip install mcp-common>=2.0.0

# This automatically installs ACB
```

**Or install ACB separately:**

```bash
pip install acb>=0.16.0
```

### Minimal ACB Example

```python
# example_adapter.py
from acb.config import AdapterBase, Settings
from acb.depends import depends
from acb.adapters.logger import LoggerProtocol
from contextlib import suppress
from uuid import UUID

# Static module identifier
MODULE_ID = UUID("01947e12-1234-7abc-9def-1a2b3c4d5e6f")


class ExampleSettings(Settings):
    message: str = "Hello, ACB!"


class ExampleAdapter(AdapterBase):
    settings: ExampleSettings | None = None
    logger: LoggerProtocol  # Injected by ACB

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if self.settings is None:
            self.settings = ExampleSettings()

    async def greet(self):
        self.logger.info("Greeting", message=self.settings.message)
        return self.settings.message


# Auto-register
with suppress(Exception):
    depends.set(ExampleAdapter)
```

```python
# example_usage.py
from acb import register_pkg
from acb.depends import depends
from example_adapter import ExampleAdapter

register_pkg("example")


async def main():
    # Get adapter from DI
    adapter = depends(ExampleAdapter)

    # Use it
    message = await adapter.greet()
    print(message)  # "Hello, ACB!"


# Run
import asyncio

asyncio.run(main())
```

### Learning Path

1. **Read This Document** - Understand ACB fundamentals ✅
1. **Review ACB Examples** - See patterns in action
   - `crackerjack/mcp/` - Complex MCP server
   - `session-mgmt-mcp/` - Settings patterns
   - `fastblocks/adapters/` - Adapter examples
1. **Read mcp-common ARCHITECTURE.md** - Understand MCP patterns
1. **Try Complete Example** - `examples/complete_server/` in mcp-common
1. **Build Your MCP Server** - Use mcp-common + ACB

______________________________________________________________________

## Common Patterns

### Pattern 1: Creating an MCP Server

Note: Running an MCP server requires a protocol host such as FastMCP, which is not bundled with mcp-common. Install it separately with `pip install fastmcp` or `uv add fastmcp`.

```python
# my_server/__init__.py
from acb import register_pkg

register_pkg("my_server")

# my_server/settings.py
from mcp_common.config import MCPBaseSettings
from pydantic import Field


class MyServerSettings(MCPBaseSettings):
    api_key: str = Field(description="API key")
    timeout: int = Field(default=30)


# my_server/main.py
from fastmcp import FastMCP  # install separately
from mcp_common import ServerPanels
from mcp_common.adapters.http import HTTPClientAdapter
from acb.depends import depends

mcp = FastMCP("MyServer")
settings = MyServerSettings()


@mcp.tool()
async def my_tool():
    http = depends(HTTPClientAdapter)
    client = await http._create_client()
    # ... use client


if __name__ == "__main__":
    ServerPanels.startup_success(server_name="My MCP Server", features=["HTTP Client"])
    mcp.run()
```

### Pattern 2: Testing with ACB

```python
# tests/test_my_tool.py
from acb.depends import depends
from my_server.main import my_tool
import pytest


@pytest.fixture
def mock_http_client():
    """Mock HTTP client adapter."""

    class MockHTTPAdapter:
        async def _create_client(self):
            # Return mock client
            return MockAsyncClient()

    # Override in DI container
    mock = MockHTTPAdapter()
    depends.set(HTTPClientAdapter, mock)
    return mock


async def test_my_tool(mock_http_client):
    """Test tool with mocked HTTP client."""
    result = await my_tool()
    assert result["success"]
    assert mock_http_client.called
```

### Pattern 3: Custom Adapter

```python
# my_server/adapters/email.py
from acb.config import AdapterBase, Settings
from acb.adapters.logger import LoggerProtocol
from uuid import UUID
from contextlib import suppress

MODULE_ID = UUID("01947e12-5678-7abc-9def-fedcba987654")


class EmailSettings(Settings):
    smtp_host: str = "smtp.example.com"
    smtp_port: int = 587


class EmailAdapter(AdapterBase):
    settings: EmailSettings | None = None
    logger: LoggerProtocol

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if self.settings is None:
            self.settings = EmailSettings()
        self._smtp_client = None

    async def _create_client(self):
        """Create SMTP client."""
        if self._smtp_client is None:
            # Initialize SMTP connection
            self.logger.info("SMTP client initialized")
        return self._smtp_client

    async def _cleanup_resources(self):
        """Close SMTP connection."""
        if self._smtp_client:
            await self._smtp_client.close()
            self.logger.info("SMTP client closed")


with suppress(Exception):
    depends.set(EmailAdapter)
```

______________________________________________________________________

## FAQ

### Q: Do I need to learn all of ACB to use mcp-common?

**A:** No. You need to understand:

- How to extend `AdapterBase` (if creating custom adapters)
- How to use `depends()` to get adapters
- How `Settings` work (YAML + env vars)
- That `logger` is injected (don't create it)
- How to use `console` for Rich output

The rest of ACB is used internally by mcp-common.

### Q: Can I use mcp-common without ACB?

**A:** No. mcp-common v2.0 is ACB-native and requires ACB as a core dependency.

If you need a standalone library without ACB, consider:

- Using mcp-common v1.0 (if it exists)
- Building your own utilities
- Requesting a standalone version

### Q: What if I already have a custom logger/settings system?

**A:** You should migrate to ACB patterns for consistency:

- Replace custom logger with ACB Logger
- Migrate settings to `Settings` base class
- Use ACB dependency injection

Benefits: Consistency with ecosystem, better testability, Rich UI support.

### Q: How do I debug ACB dependency injection?

```python
# Check what's registered
from acb.depends import depends

# Try to get adapter
try:
    adapter = depends(HTTPClientAdapter)
    print(f"Adapter found: {adapter}")
except Exception as e:
    print(f"Adapter not found: {e}")

# List all registered dependencies (if ACB provides this)
# (Check ACB documentation for introspection APIs)
```

### Q: Where is the ACB documentation?

**A:** ACB documentation locations:

- **GitHub:** `github.com/yourusername/acb` *(adjust link)*
- **README:** See ACB project README
- **Examples:** Look at `crackerjack`, `session-mgmt-mcp`, `fastblocks`
- **Source Code:** ACB is well-documented in code comments

______________________________________________________________________

## Next Steps

Now that you understand ACB fundamentals:

1. **✅ Read ARCHITECTURE.md** - Understand mcp-common's ACB-native design
1. **✅ Review Examples** - See `examples/complete_server/` in mcp-common
1. **✅ Try Tutorial** - Build a simple MCP server with mcp-common
1. **✅ Read IMPLEMENTATION_PLAN.md** - Understand migration strategy
1. **✅ Build Your Server** - Apply patterns to your MCP server

**Questions?** Check ACB documentation or mcp-common examples.

______________________________________________________________________

**Document Status:** ✅ Complete
**Last Updated:** 2025-10-26
**Next:** Read ARCHITECTURE.md for mcp-common patterns
