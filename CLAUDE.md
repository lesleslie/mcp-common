# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**mcp-common** is an ACB-native foundation library for building production-grade MCP (Model Context Protocol) servers. It provides battle-tested patterns extracted from 9 production servers including crackerjack, session-mgmt-mcp, and fastblocks.

**Current Status:** v2.0.0 - **Partially Implemented**

- ✅ Core package structure complete
- ✅ MCPBaseSettings with YAML + environment variable support
- ✅ HTTPClientAdapter with connection pooling (implemented)
- ✅ ServerPanels for Rich UI (implemented)
- ✅ Security utilities (API key validation, sanitization)
- ✅ Health check system (HTTP connectivity, component health)
- ✅ Exception hierarchy (MCPServerError, validation errors)
- ✅ ValidationMixin for Pydantic models
- ✅ Comprehensive test suite with 90%+ coverage
- 🚧 Complete example server (`examples/weather_server.py`)

## Critical Prerequisites

### ACB Framework Dependency

This library is **ACB-native**, meaning it is built **on top of ACB**, not as a standalone utility:

- **ACB (Asynchronous Component Base)** provides: adapters, dependency injection, structured logging, settings, console
- **mcp-common** provides: MCP-specific adapters built using ACB patterns
- **Relationship:** mcp-common extends ACB for MCP server use cases

**ACB is installed as an editable dependency** from `../acb`:

```toml
[tool.uv.sources]
acb = { path = "../acb", editable = true }
```

This means changes to the ACB project at `../acb` are immediately reflected in mcp-common.

**IMPORTANT:** Before implementing any adapter, read `docs/ACB_FOUNDATION.md` to understand:

- ACB adapter lifecycle (MODULE_ID, MODULE_STATUS, MODULE_METADATA)
- Dependency injection with `acb.depends`
- Logger injection via `LoggerProtocol`
- Settings extending `acb.config.Settings`

### Reference Implementations

The design is extracted from these production servers (located in `../` relative to this repo):

**Primary Pattern Sources:**

- **crackerjack** (`../crackerjack/mcp/`) - Rich UI panels (ServerPanels), MCP server structure, tool organization
- **session-mgmt-mcp** (`../session-mgmt-mcp/`) - ACB Settings with YAML configuration, comprehensive DI usage, adapter lifecycle patterns
- **fastblocks** (`../fastblocks/`) - ACB adapter organization, module structure

**Key Patterns from Production Servers:**

- **Rich UI Panels:** `crackerjack/ui/` - Professional console output with Rich library
- **Tool Registration:** `crackerjack/mcp/` - FastMCP tool organization patterns
- **Structured Logging:** Uses ACB logger with correlation IDs and context binding
- **MCP Server Structure:** Clean separation of concerns (tools, adapters, settings)

When implementing adapters, **always reference these codebases** for proven ACB patterns. Don't guess at ACB patterns - look at working production code.

## Development Commands

### Environment Setup

```bash
# Install with development dependencies (recommended)
uv sync --group dev

# Or with pip
pip install -e ".[dev]"
```

### Testing

```bash
# Run all tests with coverage (requires 90% minimum)
uv run pytest

# Run specific test file
uv run pytest tests/test_config.py -v

# Run with coverage report
uv run pytest --cov=mcp_common --cov-report=html

# Run only unit tests
uv run pytest -m unit

# Run only integration tests
uv run pytest -m integration

# Skip slow tests (performance benchmarks)
uv run pytest -m "not slow"

# Run specific test by name
uv run pytest tests/test_http_client.py::test_connection_pooling -v
```

### Code Quality

```bash
# Format code (Ruff)
uv run ruff format

# Check formatting without changes
uv run ruff format --check

# Lint code
uv run ruff check

# Auto-fix linting issues
uv run ruff check --fix

# Type checking (MyPy with strict mode)
uv run mypy mcp_common tests

# Security scan (Bandit)
uv run bandit -r mcp_common

# Run all quality checks (format + lint + type check + test)
uv run ruff format && uv run ruff check && uv run mypy mcp_common tests && uv run pytest
```

### Using Hatch Scripts (Alternative)

```bash
hatch run test           # Run tests
hatch run test-cov       # Tests with coverage
hatch run lint           # Lint only
hatch run format         # Format code
hatch run type-check     # Type check
hatch run security       # Security scan
hatch run all            # All checks
```

## Package Structure

```
mcp_common/
├── __init__.py              # Package registration, public API exports
├── adapters/
│   ├── __init__.py          # HTTPClientAdapter exports
│   └── http/
│       ├── __init__.py
│       └── client.py        # ✅ HTTPClientAdapter (connection pooling)
├── config/
│   ├── __init__.py          # MCPBaseSettings, ValidationMixin exports
│   ├── base.py              # ✅ MCPBaseSettings (YAML + env vars)
│   └── validation_mixin.py  # ✅ ValidationMixin for Pydantic models
├── middleware/               # [Removed] No centralized middleware in this lib
├── security/
│   ├── __init__.py          # Security utilities exports
│   ├── api_keys.py          # ✅ APIKeyValidator (format validation)
│   └── sanitization.py      # ✅ Sanitize user inputs, filter data
├── ui/
│   ├── __init__.py          # ServerPanels exports
│   └── panels.py            # ✅ ServerPanels (Rich UI panels)
├── exceptions.py            # ✅ Custom exception hierarchy
├── health.py                # ✅ Health check models (HealthStatus, ComponentHealth)
└── http_health.py           # ✅ HTTP health check functions

tests/
├── conftest.py              # Shared pytest fixtures
├── test_config.py           # MCPBaseSettings tests
├── test_config_security.py  # Security integration tests
├── test_config_validation_mixin.py  # ValidationMixin tests
├── test_health.py           # Health check system tests
├── test_http_client.py      # HTTPClientAdapter tests
├── test_http_health.py      # HTTP health check tests
├── test_security_api_keys.py  # API key validation tests
├── test_security_sanitization.py  # Sanitization tests
├── test_ui_panels.py        # ServerPanels tests
├── test_version.py          # Version import tests
└── performance/             # Performance benchmarks
    └── test_http_pooling.py

examples/
├── README.md                # Example documentation
├── settings/
│   └── weather.yaml         # Example YAML configuration
└── weather_server.py        # ✅ Complete working Weather MCP server
```

**Note:** There is NO `logging/` directory - ACB logger is used directly via `LoggerProtocol` injection.

## Architecture Overview

### ACB-Native Adapter Pattern

All adapters in this library follow the ACB adapter pattern:

```python
from acb.config import AdapterBase, Settings
from acb.adapters.logger import LoggerProtocol
from acb.adapters import AdapterStatus, AdapterMetadata, AdapterCapability
from uuid import UUID
from contextlib import suppress

# Static UUID7 - generated once, hardcoded forever (NEVER use uuid4())
MODULE_ID = UUID("01947e12-3b4c-7d8e-9f0a-1b2c3d4e5f6a")
MODULE_STATUS = AdapterStatus.STABLE  # Enum, not string

MODULE_METADATA = AdapterMetadata(
    module_id=MODULE_ID,
    name="Example Adapter",
    category="category",
    provider="provider",
    version="1.0.0",
    acb_min_version="0.19.0",
    status=MODULE_STATUS,
    capabilities=[AdapterCapability.ASYNC_OPERATIONS],
    required_packages=["package>=1.0.0"],
    description="Adapter description",
)


class ExampleAdapter(AdapterBase):
    settings: ExampleSettings | None = None
    logger: LoggerProtocol  # Injected by ACB - NEVER create Logger()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)  # REQUIRED: Call parent constructor
        if self.settings is None:
            self.settings = ExampleSettings()

    async def _create_client(self):
        """Lazy initialization lifecycle method."""
        # Initialize resources
        self.logger.info("Resource initialized")

    async def _cleanup_resources(self):
        """Cleanup on shutdown lifecycle method."""
        # Close resources
        self.logger.info("Resource closed")


# Auto-register with DI container at module level
with suppress(Exception):
    depends.set(ExampleAdapter)
```

### Critical Pattern Rules

1. **MODULE_ID must be static UUID7** - Generated once during implementation, then hardcoded forever (NOT `uuid4()`)
1. **MODULE_STATUS is enum** - Use `AdapterStatus.STABLE`, not string `"stable"`
1. **Logger is injected** - Type hint `logger: LoggerProtocol`, ACB injects automatically
1. \*\*Always call super().__init__(**kwargs)** - Required for ACB lifecycle
1. **Implement lifecycle methods** - `_create_client()` and `_cleanup_resources()`
1. **DI registration at module level** - Use `with suppress(Exception): depends.set()`

## Implementation Guidelines

### When Implementing a New Adapter

1. **Read `docs/ACB_FOUNDATION.md`** for ACB fundamentals (adapters, DI, lifecycle)
1. **Read relevant documentation** in `docs/` for the specific feature
1. **Generate static UUID7** for MODULE_ID (use `uuidv7` CLI or Python uuid7 library)
1. **Create MODULE_METADATA** with all required fields
1. **Reference production code** in `../crackerjack`, `../session-mgmt-mcp`, or `../fastblocks`
   - For rate limiting: Study `crackerjack/mcp/rate_limiter.py`
   - For Rich UI: Study `crackerjack/ui/panels.py`
   - For ACB patterns: Study `session-mgmt-mcp/adapters/`
1. **Implement lifecycle methods** (`_create_client()`, `_cleanup_resources()`)
1. **Write tests first** (TDD approach, target 90%+ coverage)
1. **Register at module level** with `suppress(Exception): depends.set()`
1. **Run quality checks** with `uv run pytest` and linting

**Development Cycle:**

```bash
# 1. Implement feature
vim mcp_common/adapters/rate_limit/limiter.py

# 2. Write tests
vim tests/test_rate_limiter.py

# 3. Run tests
uv run pytest tests/test_rate_limiter.py -v

# 4. Run quality checks
uv run ruff format
uv run ruff check
uv run mypy mcp_common tests

# 5. Run full test suite with coverage
uv run pytest --cov=mcp_common
```

### Settings Pattern

All settings extend ACB's `acb.config.Settings`, not raw Pydantic:

```python
from mcp_common.config import MCPBaseSettings
from pydantic import Field


class MyServerSettings(MCPBaseSettings):
    """Server configuration using ACB Settings.

    Loads from (in order):
    1. settings/local.yaml (gitignored)
    2. settings/my-server.yaml
    3. Environment variables MY_SERVER_*
    4. Defaults below
    """

    api_key: str = Field(description="API key")
    timeout: int = Field(default=30, description="Timeout in seconds")
```

### Dependency Injection Usage

All adapters use ACB's dependency injection:

```python
from acb.depends import depends
from mcp_common.adapters.http import HTTPClientAdapter


@mcp.tool()
async def my_tool():
    # Get adapter from DI container (singleton)
    http = depends(HTTPClientAdapter)
    client = await http._create_client()
    response = await client.get("https://api.example.com")
    return response.json()
```

### Testing with DI

Tests can mock adapters via dependency injection:

```python
from acb.depends import depends
import pytest


@pytest.fixture
def mock_http():
    """Create mock HTTP adapter."""
    mock = MockHTTPClientAdapter()
    depends.set(HTTPClientAdapter, mock)
    return mock


async def test_my_tool(mock_http):
    """Test uses mock automatically via DI."""
    result = await my_tool()
    assert mock_http.called
```

## Quality Standards

This project follows **strict quality standards** enforced by test suite and linting:

- **Test Coverage:** Minimum 90% (enforced by pytest with `--cov-fail-under=90`)
- **Type Safety:** Strict MyPy (`strict = true` in pyproject.toml)
  - Full type hints required for all functions and methods
  - No `Any` types without justification
  - Type stubs (`.pyi`) for external dependencies if needed
- **Code Style:** Ruff with comprehensive rule set (136 enabled rules - see pyproject.toml)
  - Line length: 100 characters
  - Python 3.13+ target
  - Google-style docstrings
- **Security:** Bandit security scanning (no security issues tolerated)
- **Documentation:**
  - Google-style docstrings required for all public APIs
  - Type hints serve as primary documentation for parameters/returns
  - Complex logic requires inline comments explaining "why", not "what"

**Before committing, always run:**

```bash
# Format + lint + type check + test
uv run ruff format && uv run ruff check && uv run mypy mcp_common tests && uv run pytest
```

## Key Documentation Files

- **`README.md`** - User-facing documentation with quickstart and examples
- **`docs/ACB_FOUNDATION.md`** - **START HERE** - ACB prerequisite guide (MUST READ before implementing)
- **`docs/ARCHITECTURE.md`** - Complete technical design (if exists - check docs/)
- **`docs/IMPLEMENTATION_PLAN.md`** - Phased implementation roadmap (if exists)
- **`docs/MCP_ECOSYSTEM_CRITICAL_AUDIT.md`** - Analysis of 9 production servers that informed design
- **`docs/SECURITY_IMPLEMENTATION.md`** - Security features and patterns
- **`docs/PHASE3_*.md`** - Phase-specific implementation documentation
- **`examples/README.md`** - Example server documentation

## Common Pitfalls to Avoid

1. **Using `uuid4()` for MODULE_ID** - Must be static UUID7, generated once and hardcoded
1. **Creating Logger manually** - Logger is injected by ACB via `LoggerProtocol`
1. **String for MODULE_STATUS** - Must use `AdapterStatus.STABLE` enum
1. **Forgetting `super().__init__(**kwargs)`** - Required for ACB lifecycle
1. **Missing MODULE_METADATA** - Required for ACB component discovery
1. **DI registration in `__init__`** - Must be at module level with `suppress(Exception)`
1. **Not implementing lifecycle methods** - `_create_client()` and `_cleanup_resources()` required
1. **Ignoring test coverage** - Must maintain 90%+ coverage (enforced by CI)
1. **Skipping type hints** - Strict MyPy requires full type coverage

## Implemented Components (v2.0.0)

### ✅ Core Configuration (mcp_common/config/)

- **MCPBaseSettings** - YAML + environment variable configuration
  - Extends `acb.config.Settings`
  - Automatic YAML loading from `settings/{name}.yaml`
  - Environment variable overrides
  - Path expansion (`~` → home directory)
  - API key validation methods (`get_api_key()`, `get_api_key_secure()`, `get_masked_key()`)
- **MCPServerSettings** - Extended settings with common MCP server fields
- **ValidationMixin** - Reusable Pydantic validation logic

### ✅ HTTP Client Adapter (mcp_common/adapters/http/)

- **HTTPClientAdapter** - Connection pooling with httpx
  - 11x performance improvement vs per-request clients
  - Automatic lifecycle management
  - Configurable pool size, timeouts, retries
  - ACB-native with DI registration

### ✅ Security Utilities (mcp_common/security/)

- **APIKeyValidator** - Format validation for API keys
  - Provider-specific patterns (OpenAI, Anthropic, Mailgun, etc.)
  - Format validation with detailed error messages
  - Key masking for safe logging
- **Sanitization** - Input sanitization and data filtering
  - HTML/SQL injection prevention
  - Path traversal protection
  - Data redaction for sensitive fields

### ✅ Health Checks (mcp_common/health.py, mcp_common/http_health.py)

- **HealthStatus** - Enum for component health states
- **ComponentHealth** - Model for component health information
- **HealthCheckResponse** - Comprehensive health check responses
- **HTTP Health Functions** - Check HTTP connectivity and client health

### ✅ Rich UI Panels (mcp_common/ui/panels.py)

- **ServerPanels** - Professional console output with Rich
  - `startup_success()` - Startup panel with features list
  - `error()` - Error display with suggestions
  - `status_table()` - Status tables with health indicators
  - `notification()` - General notification panels

### ✅ Exception Hierarchy (mcp_common/exceptions.py)

- **MCPServerError** - Base exception for all MCP errors
- **ServerConfigurationError** - Configuration validation errors
- **ServerInitializationError** - Startup failures
- **DependencyMissingError** - Missing required dependencies
- **CredentialValidationError** - API key/credential errors
- **APIKeyMissingError** - Missing API keys
- **APIKeyFormatError** - Invalid API key format
- **APIKeyLengthError** - API key length validation

### 🚧 Rate Limiting (mcp_common/middleware/rate_limit_config.py)

- **RateLimitConfig** - Configuration model for rate limiting
- **Needs Migration:** Convert to ACB adapter pattern with MODULE_ID/STATUS/METADATA
- **Reference:** `crackerjack/mcp/rate_limiter.py` for token bucket implementation

## Working Example

See `examples/weather_server.py` for a complete working MCP server demonstrating:

- HTTPClientAdapter with connection pooling
- MCPBaseSettings with YAML configuration
- ServerPanels for startup UI
- ACB dependency injection
- FastMCP tool integration (optional)
- Error handling and validation

**Run the example:**

```bash
cd examples
python weather_server.py
```

## Version and Release Information

- **Current Version:** 2.0.0 (partially implemented)
- **Breaking Changes from v1.x:**
  - ACB is now required (was optional)
  - HTTP client is `HTTPClientAdapter` via DI (was `get_http_client()` function)
  - Logging uses ACB Logger (no `MCPLogger` wrapper)
  - Rate limiting will be `RateLimiterAdapter` (migration in progress)
  - Settings extend `acb.config.Settings` (not raw Pydantic)

## External Dependencies and Their Roles

- **ACB (acb>=0.19.0)** - Core framework (adapters, DI, logger, settings, console) - **editable install from ../acb**
- **httpx>=0.27.0** - HTTP client with async support (used in HTTPClientAdapter)
- **pydantic>=2.10.0** - Data validation (used with ACB Settings)
- **Rich** (via acb.console) - Terminal UI for ServerPanels
- Optional: **fastmcp** - MCP protocol host to run servers and examples (install separately)

## Development Dependencies

- **pytest>=8.3.0** - Test framework
- **pytest-asyncio>=0.24.0** - Async test support
- **pytest-cov>=6.0.0** - Coverage reporting
- **pytest-mock>=3.14.0** - Mocking utilities
- **hypothesis>=6.122.0** - Property-based testing
- **ruff>=0.8.0** - Linting and formatting
- **mypy>=1.13.0** - Static type checking
- **bandit>=1.8.0** - Security scanning
- **respx>=0.21.0** - HTTP mocking for httpx
- **crackerjack** - Reference implementation
- **session-mgmt-mcp** - Reference implementation
