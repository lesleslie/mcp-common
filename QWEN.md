# mcp-common Project Context

## Overview

mcp-common is an ACB-native foundation library for building production-grade MCP (Model Context Protocol) servers. Built on the Asynchronous Component Base (ACB) framework, it provides battle-tested patterns extracted from 9 production servers including crackerjack, session-mgmt-mcp, and fastblocks.

**Key Purpose:** To provide standardized, reusable components for MCP servers with dependency injection, structured logging, and lifecycle management.

## Core Architecture

The library is built around ACB (Asynchronous Component Base) framework patterns and includes:

### 1. ACB Adapters with Lifecycle Management

- **HTTPClientAdapter**: Connection-pooled HTTP client with structured logging
- **Settings Management**: YAML + environment variable configuration via ACB Settings
- **Structured Logging**: ACB Logger with context binding and correlation IDs

### 2. Key Modules

- `mcp_common.adapters.http`: HTTP client with connection pooling (11x performance improvement)
- `mcp_common.config`: Base settings with YAML + environment variable support
- `mcp_common.ui.panels`: Rich console UI components for server operations
- `mcp_common.health`: Health check infrastructure for production deployments

## Core Components

### HTTP Client Adapter

- Implements connection pooling (vs creating clients per request)
- Provides lifecycle management (initialization and cleanup)
- Includes structured logging with correlation IDs
- Configurable via ACB Settings (timeout, connection pool size, etc.)

### Configuration System

- `MCPBaseSettings`: Base class extending ACB Settings
- Supports loading from YAML files and environment variables
- Provides API key validation and secure handling
- Includes path expansion and type validation

### Rich UI Components

- `ServerPanels`: Beautiful Rich-based terminal UI components
- Provides consistent output for startup, errors, warnings, and status
- Includes tables, panels, and formatted messages

### Health Checks

- Standardized health check responses with component-level detail
- Supports production deployments with Docker and Kubernetes
- Includes HealthStatus enum (HEALTHY, DEGRADED, UNHEALTHY)

## Development Setup

The project uses:

- Python 3.13+
- ACB framework (Asynchronous Component Base)
- Rich for terminal UI components
- Pydantic for settings validation
- Optional: FastMCP as the MCP protocol host (install separately)

### Installation

```bash
pip install -e ".[dev]"
```

### Testing

```bash
pytest --cov=mcp_common --cov-report=html
```

### Code Quality

```bash
# Format
ruff format

# Lint
ruff check

# Type check
mypy mcp_common tests

# Run all quality checks
crackerjack --all
```

## Key Design Patterns

### ACB Adapter Pattern

- Use `AdapterBase` for lifecycle management
- Dependencies injected via `acb.depends`
- Lazy initialization with `_create_client()` pattern
- Automatic cleanup with `_cleanup_resources()`

### Dependency Injection Usage

```python
from acb.depends import depends
from mcp_common.adapters.http import HTTPClientAdapter

http = depends(HTTPClientAdapter)
client = await http._create_client()
```

### Settings Configuration

```python
from mcp_common.config import MCPBaseSettings


class MyServerSettings(MCPBaseSettings):
    api_key: str = Field(description="API key for service")
    timeout: int = Field(default=30, description="Request timeout")
```

## Project Structure

- `mcp_common/` - Main source code
- `examples/` - Complete working examples of MCP servers
- `docs/` - Documentation files
- `tests/` - Test suite (not shown in current view)
- `pyproject.toml` - Project configuration and dependencies

## Prerequisites

- Understanding of ACB (Asynchronous Component Base) framework is required
- Familiarity with dependency injection patterns
- Optional: Knowledge of FastMCP if you plan to run an MCP host

## Versioning

- Current version: 2.0.0 (ACB-native redesign)
- Requires `acb>=0.19.0`
- Optional: compatible with FastMCP 2.0+

## Use Cases

The library is designed for creating MCP (Model Context Protocol) servers that need:

- Standardized HTTP client functionality with connection pooling
- Configuration management with YAML and environment variables
- Professional Rich UI in terminal applications
- Structured logging with correlation IDs
- Dependency injection for testability
- Health check endpoints for production deployment
