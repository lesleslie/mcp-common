# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**mcp-common** is an Oneiric-native foundation library for building production-grade MCP (Model Context Protocol) servers. It provides battle-tested patterns extracted from 9 production servers including crackerjack, session-mgmt-mcp, and fastblocks.

**Current Status:** v0.3.6 - **Oneiric-Native (Production Ready)**

- ✅ Core package structure complete
- ✅ MCPBaseSettings with YAML + environment variable support
- ✅ HTTPClientAdapter with connection pooling (implemented)
- ✅ ServerPanels for Rich UI (implemented)
- ✅ Security utilities (API key validation, sanitization)
- ✅ Health check system (HTTP connectivity, component health)
- ✅ Exception hierarchy (MCPServerError, validation errors)
- ✅ ValidationMixin for Pydantic models
- ✅ Comprehensive test suite with 90%+ coverage
- ✅ Complete example server (`examples/weather_server.py`)
- ✅ Oneiric CLI Factory with lifecycle management (NEW in v0.3.3)
- ✅ CLI example server (`examples/cli_server.py`)

## Architecture

### Oneiric Design Patterns

This library follows **Oneiric patterns**, using standard Python libraries directly:

- **Pydantic BaseModel** for settings validation
- **Rich Console** for terminal UI
- **httpx** for HTTP with connection pooling
- **YAML + env vars** for layered configuration
- **Standard Python logging** (no custom wrappers)

**No framework dependencies** - just clean Python with Pydantic and Rich.

**Key Benefits:**

- Zero framework lock-in
- Direct library usage (easier to understand)
- Standard Python patterns
- Minimal dependency tree

### Reference Implementations

The design is extracted from these production servers (located in `../` relative to this repo):

**Primary Pattern Sources:**

- **crackerjack** (`../crackerjack/mcp/`) - Rich UI panels (ServerPanels), MCP server structure, tool organization
- **session-mgmt-mcp** (`../session-mgmt-mcp/`) - YAML configuration patterns, settings management
- **fastblocks** (`../fastblocks/`) - Adapter organization, module structure

**Key Patterns from Production Servers:**

- **Rich UI Panels:** `crackerjack/ui/` - Professional console output with Rich library
- **Tool Registration:** `crackerjack/mcp/` - FastMCP tool organization patterns
- **Configuration Layering:** YAML + environment variables with clear priority
- **MCP Server Structure:** Clean separation of concerns (tools, adapters, settings)

When implementing features, **always reference these codebases** for proven patterns. Look at working production code for guidance.

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

# Run property-based tests only
uv run pytest -k "PropertyBased" -v

# Run concurrency tests only
uv run pytest tests/test_concurrency.py -v

# Run performance optimization tests
uv run pytest tests/test_performance_optimizations.py -v
```

**Test Suite Composition (v0.6.0):**

| Test Type | Count | Description |
|-----------|-------|-------------|
| Property-Based | 20 | Hypothesis tests with random inputs |
| Concurrency | 10 | Thread-safety and race condition tests |
| Performance | 7 | Benchmark and optimization verification |
| Unit/Integration | 578 | Traditional tests |
| **Total** | **615** | 100% pass rate, 99%+ coverage |

**Testing Best Practices:**

1. **Property-Based Testing** - Use Hypothesis for edge case discovery

   ```python
   from hypothesis import given, strategies as st


   @given(st.text(min_size=16, max_size=100))
   def test_validate_random_strings(key: str) -> None:
       """Test validation with random inputs."""
       result = validate_api_key_format(key, provider="generic")
       assert isinstance(result, str)
   ```

1. **Concurrency Testing** - Verify thread-safety with async tests

   ```python
   @pytest.mark.asyncio
   async def test_concurrent_sanitization() -> None:
       """Test concurrent sanitization is thread-safe."""
       data = {"api_key": "sk-test-key"}
       tasks = [asyncio.to_thread(sanitize_output, data) for _ in range(100)]
       results = await asyncio.gather(*tasks)
       assert all(r == results[0] for r in results)
   ```

1. **Performance Testing** - Use pytest-benchmark for optimizations

   ```python
   @pytest.mark.benchmark(group="sanitization", min_rounds=100)
   def test_sanitize_no_match(benchmark) -> None:
       """Benchmark clean text sanitization."""
       text = "Regular message with no sensitive data"
       result = benchmark(sanitize_output, text)
       assert result == text
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

**Note:** This library uses standard Python logging - configure as needed for your server.

## Usage Patterns

### Oneiric Adapter Pattern

Adapters in this library follow simple, direct patterns with no framework overhead:

```python
from mcp_common.adapters.http import HTTPClientSettings, HTTPClientAdapter
import logging

logger = logging.getLogger(__name__)


class MyAdapter:
    """Example adapter using Oneiric patterns."""

    def __init__(self, settings: MySettings):
        self.settings = settings
        self._client = None

    async def initialize(self):
        """Initialize resources."""
        # Create client/connections
        logger.info("Resource initialized")

    async def cleanup(self):
        """Cleanup on shutdown."""
        # Close resources
        if self._client:
            await self._client.aclose()
        logger.info("Resource closed")
```

### Key Principles

1. **Direct instantiation** - No dependency injection required, use direct object creation
1. **Standard Python logging** - Use `logging.getLogger(__name__)` for logging
1. **Simple lifecycle** - Implement `initialize()` and `cleanup()` as needed
1. **Type hints everywhere** - Full type coverage for clarity
1. **Settings via constructor** - Pass settings directly during initialization

## Implementation Guidelines

### When Implementing a New Feature

1. **Read relevant documentation** in `docs/` or `README.md` for the specific feature
1. **Reference production code** in `../crackerjack`, `../session-mgmt-mcp`, or `../fastblocks`
   - For Rich UI: Study `crackerjack/ui/panels.py`
   - For configuration: Study `session-mgmt-mcp` settings patterns
   - For HTTP clients: Study `examples/weather_server.py`
1. **Implement with type safety** - Full type hints required
1. **Write tests first** (TDD approach, target 90%+ coverage)
1. **Use direct instantiation** - No dependency injection needed
1. **Run quality checks** with `uv run pytest` and linting

**Development Cycle:**

```bash
# 1. Implement feature
vim mcp_common/adapters/my_feature.py

# 2. Write tests
vim tests/test_my_feature.py

# 3. Run tests
uv run pytest tests/test_my_feature.py -v

# 4. Run quality checks
uv run ruff format
uv run ruff check
uv run mypy mcp_common tests

# 5. Run full test suite with coverage
uv run pytest --cov=mcp_common
```

### Settings Pattern

All settings extend `MCPBaseSettings` (which extends Pydantic BaseModel):

```python
from mcp_common.config import MCPBaseSettings
from pydantic import Field


class MyServerSettings(MCPBaseSettings):
    """Server configuration using Oneiric pattern.

    Loads from (priority order):
    1. settings/my-server.yaml
    2. settings/local.yaml (gitignored)
    3. Environment variables MY_SERVER_*
    4. Defaults below
    """

    api_key: str = Field(description="API key")
    timeout: int = Field(default=30, description="Timeout in seconds")


# Load configuration
settings = MyServerSettings.load("my-server")
```

### HTTP Client Usage

Use HTTP client adapters via direct instantiation:

```python
from mcp_common.adapters.http import HTTPClientAdapter, HTTPClientSettings

# Create HTTP client with settings
http_settings = HTTPClientSettings(
    timeout=30,
    max_connections=50,
    retry_attempts=3,
)
http_adapter = HTTPClientAdapter(settings=http_settings)


# Use in tools
@mcp.tool()
async def my_tool():
    # Use the adapter directly
    response = await http_adapter.get("https://api.example.com")
    return response.json()


# Cleanup on shutdown
await http_adapter._cleanup_resources()
```

**Global Instance Pattern:**

```python
# Global instances (initialized in main())
settings: MySettings
http_adapter: HTTPClientAdapter


async def main():
    global settings, http_adapter

    # Initialize settings
    settings = MySettings.load("my-server")

    # Create HTTP adapter
    http_settings = HTTPClientSettings(timeout=settings.timeout)
    http_adapter = HTTPClientAdapter(settings=http_settings)

    # Run server
    try:
        await mcp.run()
    finally:
        await http_adapter._cleanup_resources()
```

### Testing

Tests use standard pytest mocking:

```python
import pytest
from unittest.mock import AsyncMock


@pytest.fixture
def mock_http():
    """Create mock HTTP adapter."""
    mock = AsyncMock()
    mock.get.return_value.json.return_value = {"ok": True}
    return mock


async def test_my_tool(mock_http):
    """Test with mocked HTTP client."""
    # Replace global instance with mock
    global http_adapter
    http_adapter = mock_http

    result = await my_tool()
    assert result["ok"] is True
    mock_http.get.assert_called_once()
```

**Advanced Testing Patterns (v0.6.0):**

The test suite includes three advanced testing approaches:

1. **Property-Based Testing** (20 tests)

   - Uses Hypothesis to generate random inputs
   - Discovers edge cases automatically
   - Tests invariants across thousands of examples
   - Located in: `tests/test_security_*.py`, `tests/test_health.py`

1. **Concurrency Testing** (10 tests)

   - Verifies thread-safety with async/await
   - Tests 100+ concurrent operations
   - Validates no race conditions
   - Located in: `tests/test_concurrency.py`

1. **Performance Testing** (7 tests)

   - Uses pytest-benchmark for measurements
   - Verifies optimization claims
   - Tracks performance regressions
   - Located in: `tests/test_performance_optimizations.py`

## Quality Standards

This project follows **strict quality standards** enforced by test suite and linting:

- **Test Coverage:** 99%+ (up from 94% in v0.5.2)
  - 615 total tests (up from 564 in v0.5.2)
  - Property-based testing with Hypothesis
  - Concurrency testing for thread-safety
  - Performance testing for optimization verification
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

- **`README.md`** - **START HERE** - User-facing documentation with quickstart and examples
- **`examples/README.md`** - Complete example server documentation
- **`docs/ARCHITECTURE.md`** - Complete technical design (if exists - check docs/)
- **`docs/MCP_ECOSYSTEM_CRITICAL_AUDIT.md`** - Analysis of 9 production servers that informed design
- **`docs/SECURITY_IMPLEMENTATION.md`** - Security features and patterns
- **`docs/ONEIRIC_CLI_FACTORY_*.md`** - CLI factory documentation and implementation guides

## Common Pitfalls to Avoid

1. **Forgetting to call `.load()`** - Always use `MySettings.load("server-name")` not `MySettings()`
1. **Missing cleanup** - Always cleanup resources in `finally` blocks (HTTP clients, etc.)
1. **Not validating API keys** - Use `get_api_key()` or `get_api_key_secure()` for validation
1. **Hardcoding paths** - Use Path expansion (`~` → home) via MCPBaseSettings
1. **Creating new clients per request** - Use HTTPClientAdapter for connection pooling
1. **Ignoring test coverage** - Must maintain 90%+ coverage (enforced by CI)
1. **Skipping type hints** - Strict MyPy requires full type coverage
1. **Missing docstrings** - All public APIs need Google-style docstrings
1. **Not using ServerPanels** - Use Rich UI for professional console output

## Implemented Components (v0.3.6)

### ✅ Core Configuration (mcp_common/config/)

- **MCPBaseSettings** - YAML + environment variable configuration
  - Extends Pydantic `BaseModel`
  - Automatic YAML loading from `settings/{name}.yaml` via `.load()`
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
  - Direct instantiation (no DI required)

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

### 🚧 Rate Limiting

- Not currently provided by this library
- If using FastMCP, its built-in `RateLimitingMiddleware` can be enabled
- For other frameworks, implement project-specific rate limiting
- **Reference:** `crackerjack/mcp/rate_limiter.py` for token bucket implementation examples

## Working Example

See `examples/weather_server.py` for a complete working MCP server demonstrating:

- HTTPClientAdapter with connection pooling
- MCPBaseSettings with YAML configuration via `.load()`
- ServerPanels for startup UI
- Global instance pattern (no dependency injection)
- FastMCP tool integration (optional)
- Error handling and validation

**Run the example:**

```bash
cd examples
python weather_server.py
```

## Version and Release Information

- **Current Version:** 0.3.6 (Oneiric-Native - production ready)
- **New in v0.3.6:**
  - Oneiric-native implementation - pure Pydantic + Rich
  - Direct library usage (no framework lock-in)
  - Simplified adapter patterns
  - Standard Python logging (no custom wrappers)
- **New in v0.3.3:**
  - Oneiric CLI Factory for server lifecycle management
  - MCPServerSettings with YAML configuration
  - RuntimeHealthSnapshot for health monitoring
  - SignalHandler for graceful shutdown
  - Security utilities (PID validation, cache ownership)
  - Complete CLI example server
  - Standard Python logging (not custom wrappers)
  - Rate limiting not included (use FastMCP middleware or project-specific)

## External Dependencies and Their Roles

- **pydantic>=2.12.4** - Data validation and settings management (MCPBaseSettings)
- **rich>=14.2.0** - Terminal UI for beautiful console output (ServerPanels)
- **httpx>=0.27.0** - HTTP client with async support (HTTPClientAdapter)
- **pyyaml>=6.0.0** - YAML configuration file parsing
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

<!-- CRACKERJACK INTEGRATION START -->

This project uses crackerjack for Python project management and quality assurance.

For optimal development experience with this crackerjack - enabled project, use these specialized agents:

- **🏗️ crackerjack-architect**: Expert in crackerjack's modular architecture and Python project management patterns. **Use PROACTIVELY** for all feature development, architectural decisions, and ensuring code follows crackerjack standards from the start.

- **🐍 python-pro**: Modern Python development with type hints, async/await patterns, and clean architecture

- **🧪 pytest-hypothesis-specialist**: Advanced testing patterns, property-based testing, and test optimization

- **🧪 crackerjack-test-specialist**: Advanced testing specialist for complex testing scenarios and coverage optimization

- **🏗️ backend-architect**: System design, API architecture, and service integration patterns

- **🔒 security-auditor**: Security analysis, vulnerability detection, and secure coding practices

```bash

Task tool with subagent_type ="crackerjack-architect" for feature planning


Task tool with subagent_type ="python-pro" for code implementation


Task tool with subagent_type ="pytest-hypothesis-specialist" for test development


Task tool with subagent_type ="security-auditor" for security analysis
```

**💡 Pro Tip**: The crackerjack-architect agent automatically ensures code follows crackerjack patterns from the start, eliminating the need for retrofitting and quality fixes.

This project follows crackerjack's clean code philosophy:

- **EVERY LINE OF CODE IS A LIABILITY**: The best code is no code

- **DRY (Don't Repeat Yourself)**: If you write it twice, you're doing it wrong

- **YAGNI (You Ain't Gonna Need It)**: Build only what's needed NOW

- **KISS (Keep It Simple, Stupid)**: Complexity is the enemy of maintainability

- \*\*Cognitive complexity ≤15 \*\*per function (automatically enforced)

- **Coverage ratchet system**: Never decrease coverage, always improve toward 100%

- **Type annotations required**: All functions must have return type hints

- **Security patterns**: No hardcoded paths, proper temp file handling

- **Python 3.13+ modern patterns**: Use `|` unions, pathlib over os.path

```bash

python -m crackerjack


python -m crackerjack - t


python -m crackerjack - - ai - agent - t


python -m crackerjack - a patch
```

1. **Plan with crackerjack-architect**: Ensure proper architecture from the start
1. **Implement with python-pro**: Follow modern Python patterns
1. **Test comprehensively**: Use pytest-hypothesis-specialist for robust testing
1. **Run quality checks**: `python -m crackerjack -t` before committing
1. **Security review**: Use security-auditor for final validation

- **Use crackerjack-architect agent proactively** for all significant code changes
- **Never reduce test coverage** - the ratchet system only allows improvements
- **Follow crackerjack patterns** - the tools will enforce quality automatically
- **Leverage AI agent auto-fixing** - `python -m crackerjack --ai-agent -t` for autonomous quality fixes

______________________________________________________________________

- This project is enhanced by crackerjack's intelligent Python project management.\*

<!-- CRACKERJACK INTEGRATION END -->
