# MCP Common Dependencies

This document describes the dependency architecture of mcp-common, including runtime requirements, optional dependencies, and usage across the ecosystem.

## Overview

mcp-common is designed as a **lightweight foundation library** with minimal dependencies. It leverages the Oneiric configuration system and provides battle-tested patterns extracted from production MCP servers.

**Design Philosophy:**

- **Minimal Core**: Only essential runtime dependencies
- **Optional Features**: Advanced features via optional dependencies
- **No Framework Lock-in**: Works with FastMCP, raw MCP SDK, or custom implementations
- **Production-Ready**: All dependencies are stable, well-maintained libraries

## Required Runtime Dependencies

### Core Dependencies

These dependencies are **automatically installed** with `pip install mcp-common`:

| Package | Version | Purpose | Why This Library |
|---------|---------|---------|------------------|
| **oneiric** | >=0.3.6 | Configuration & HTTP client | Oneiric patterns for YAML + env var config, connection pooling |
| **pydantic** | >=2.12.5 | Data validation | Type-safe settings with validation |
| **pyyaml** | >=6.0.3 | YAML parsing | Configuration file loading |
| **rich** | >=14.2.0 | Terminal UI | Beautiful console output |
| **typer** | >=0.21.0 | CLI framework | Server lifecycle management |
| **psutil** | >=7.2.1 | System utilities | Process monitoring for PID management |

### Dependency Explanations

#### oneiric (Configuration & HTTP Client)

**Purpose**: Provides `MCPBaseSettings` configuration patterns and `HTTPClientAdapter` connection pooling.

**What it provides**:

- `MCPBaseSettings` - Base class for YAML + environment variable configuration
- `HTTPClientAdapter` - HTTP client with connection pooling (11x performance)
- `HTTPClientSettings` - Configuration for HTTP adapter
- Layered configuration loading (defaults → YAML → env vars)

**Why it's extracted**: Shared across 9 production MCP servers for consistent patterns.

**Usage in mcp-common**:

```python
from oneiric.adapters.http import HTTPClientAdapter, HTTPClientSettings
from mcp_common.config import MCPBaseSettings
```

#### pydantic (Data Validation)

**Purpose**: Type-safe settings with validation, coercion, and serialization.

**What it provides**:

- `BaseModel` - Base class for settings models
- `Field()` - Field configuration with validators
- Type validation and coercion
- Environment variable parsing

**Why it's required**: All configuration classes use Pydantic for validation.

**Usage in mcp-common**:

```python
from pydantic import Field, field_validator

class Settings(MCPBaseSettings):
    api_key: str = Field(description="API key")
    timeout: int = Field(default=30, ge=1, le=300)
```

#### rich (Terminal UI)

**Purpose**: Beautiful console output for server operations.

**What it provides**:

- `Console` - Rich console output
- `Panel` - Decorated panels
- `Table` - Formatted tables
- Colors and emojis for visual clarity

**Why it's required**: `ServerPanels` uses Rich for all UI components.

**Usage in mcp-common**:

```python
from rich.console import Console
from rich.panel import Panel

console = Console()
console.print(Panel("Hello!", title="Server"))
```

#### typer (CLI Framework)

**Purpose**: Type-safe CLI command creation for server lifecycle management.

**What it provides**:

- `Typer` - CLI app creation
- Command decorators (`@app.command()`)
- Automatic help generation
- Parameter validation

**Why it's required**: `MCPServerCLIFactory` uses Typer for CLI commands.

**Usage in mcp-common**:

```python
import typer

app = typer.Typer()

@app.command()
def start():
    """Start the server."""
    print("Server started!")

if __name__ == "__main__":
    app()
```

#### psutil (System Utilities)

**Purpose**: Process monitoring and management for PID file handling.

**What it provides**:

- `Process` - Process information and control
- PID validation
- Process existence checking
- Command line inspection

**Why it's required**: CLI factory needs to verify process identity and detect stale PIDs.

**Usage in mcp-common**:

```python
import psutil

def is_process_running(pid: int) -> bool:
    """Check if process is running."""
    try:
        return psutil.Process(pid).is_running()
    except psutil.NoSuchProcess:
        return False
```

## Optional Dependencies

### Development Dependencies

Install with `pip install mcp-common[dev]`:

| Package | Purpose |
|---------|---------|
| **crackerjack** | Quality control and CI/CD automation |
| **pytest-benchmark** | Performance benchmarking |
| **uv-bump** | Version bumping automation |

### Optional Runtime Dependencies

These are **NOT installed** with mcp-common but can be used by your server:

| Package | Purpose | Installation |
|---------|---------|--------------|
| **fastmcp** | MCP server framework | `pip install fastmcp` |
| **httpx** | Async HTTP client (included via oneiric) | Automatic |
| **pyjwt** | JWT authentication | `pip install pyjwt` |
| **opentelemetry** | Distributed tracing | `pip install opentelemetry-api` |

## Dependency Tree

```
mcp-common (0.7.0)
├── oneiric (>=0.3.6)
│   ├── pydantic (>=2.12.5)
│   ├── pyyaml (>=6.0.3)
│   ├── httpx (>=0.27.0)
│   └── rich (>=14.2.0)
├── pydantic (>=2.12.5)
├── pyyaml (>=6.0.3)
├── rich (>=14.2.0)
├── typer (>=0.21.0)
│   └── rich (>=14.2.0) [already listed]
└── psutil (>=7.2.1)
```

**Note**: `httpx` is included transitively via `oneiric` for HTTP client functionality.

## Version Compatibility

### Python Version

**Required**: Python >=3.13

**Why**: mcp-common uses modern Python features:

- Type hint improvements (PEP 695)
- Match statements (PEP 634)
- Pydantic V2 features

### Dependency Version Policy

mcp-common uses **compatible release clauses** (`~=`) for stable dependencies:

```toml
dependencies = [
    "oneiric>=0.3.6",      # Minimum version, allows updates
    "pydantic>=2.12.5",    # Stable API, allows patch/minor updates
    "rich>=14.2.0",        # Stable API
    "typer>=0.21.0",       # Stable API
    "psutil>=7.2.1",       # Stable API
]
```

**Why not `~=` (compatible release)**:

- Allows security updates without version bumps
- Dependencies are stable with backward compatibility
- More flexible for downstream consumers

## Usage in Ecosystem

mcp-common is the **foundation library** for the Mahavishnu ecosystem. These projects depend on mcp-common:

### Core Ecosystem Projects

| Project | Role | Usage |
|---------|------|-------|
| **Mahavishnu** | Orchestrator | Configuration management, CLI lifecycle, Rich UI |
| **Session-Buddy** | Session Manager | Settings, HTTP client, server panels |
| **Dhruva** | Adapter Curator | Configuration patterns, CLI factory |
| **Akosha** | Pattern Recognition | Settings management, HTTP pooling |
| **Crackerjack** | Quality Inspector | Server lifecycle, health checks |

### Community Projects

| Project | Purpose | Usage |
|---------|---------|-------|
| **mailgun-mcp** | Mailgun integration | HTTP client, configuration |
| **raindropio-mcp** | Bookmark management | HTTP pooling, Rich UI |
| **unifi-mcp** | Network management | Settings, CLI factory |
| **excalidraw-mcp** | Diagram collaboration | Configuration, validation |
| **fastblocks** | Web framework | Settings, HTTP client |

### Dependency Impact

When mcp-common updates, these projects benefit from:

- **Bug fixes**: Applied to all ecosystem projects
- **Performance improvements**: HTTP client optimizations, validation caching
- **New features**: CLI enhancements, security improvements
- **Documentation**: Better examples and guides

## Security Considerations

### Vulnerability Scanning

mcp-common uses **Crackerjack** for automated security scanning:

```bash
# Run security audit
crackerjack run security

# Manual scan with bandit
bandit -r mcp_common/

# Check for known vulnerabilities
safety check
```

**Current Status**: ✅ Zero critical vulnerabilities (as of v0.7.0)

### Dependency Updates

mcp-common follows **semantic versioning** for breaking changes:

- **Patch releases** (0.7.0 → 0.7.1): Bug fixes, no API changes
- **Minor releases** (0.7.0 → 0.8.0): New features, backward compatible
- **Major releases** (0.7.0 → 1.0.0): Breaking changes (documented in CHANGELOG)

**Update Policy**:

- Dependencies are updated for security patches within 7 days
- Minor updates are tested in CI before release
- Breaking changes are documented in migration guides

## Performance Impact

### Dependency Overhead

| Component | Memory | CPU | Startup Time |
|-----------|--------|-----|--------------|
| **Pydantic** | ~5MB | Minimal | ~10ms |
| **Rich** | ~8MB | Minimal | ~15ms |
| **Typer** | ~2MB | Minimal | ~5ms |
| **psutil** | ~3MB | Low | ~20ms |
| **oneiric** | ~10MB | Low | ~50ms |
| **Total** | ~28MB | Low | ~100ms |

**Conclusion**: Minimal overhead for production servers.

### HTTP Client Performance

HTTP client adapter (via oneiric) provides:

- **11x faster** than creating new clients per request
- **10x less memory** usage
- **Connection pooling** with configurable limits

## Installation Methods

### Standard Installation

```bash
# Install mcp-common with runtime dependencies
pip install mcp-common

# Install with development dependencies
pip install mcp-common[dev]

# Install from git
pip install git+https://github.com/lesleslie/mcp-common.git
```

### Installation in Ecosystem Projects

```bash
# Using pip (recommended)
pip install mcp-common>=0.7.0

# Using uv (faster)
uv add mcp-common>=0.7.0

# Using poetry
poetry add mcp-common>=0.7.0
```

### Version Pinning

```bash
# Pin to specific version
pip install mcp-common==0.7.0

# Pin to minor version (allows patches)
pip install mcp-common~=0.7.0

# Minimum version (allows updates)
pip install "mcp-common>=0.7.0"
```

## Troubleshooting

### Import Errors

**Problem**: `ImportError: cannot import name 'HTTPClientAdapter'`

**Solution**:

```bash
# HTTPClientAdapter is from oneiric, re-exported by mcp-common
pip install --upgrade mcp-common oneiric
```

### Version Conflicts

**Problem**: `ERROR: pip's dependency resolver does not currently take into account all the packages that are installed`

**Solution**:

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install fresh
pip install --upgrade pip
pip install mcp-common
```

### Missing Optional Dependencies

**Problem**: `ModuleNotFoundError: No module named 'fastmcp'`

**Solution**:

```bash
# fastmcp is optional, install separately
pip install fastmcp
```

## Contributing

When contributing to mcp-common:

1. **Keep dependencies minimal**: Only add if absolutely necessary
1. **Document new dependencies**: Update this file with rationale
1. **Check ecosystem impact**: Test with Mahavishnu, Session-Buddy, etc.
1. **Run security scans**: Ensure no vulnerabilities introduced
1. **Update requirements**: Pin versions in `pyproject.toml`

## See Also

- **[README.md](../README.md)** - Main project documentation
- **[CHANGELOG.md](../CHANGELOG.md)** - Version history and changes
- **[examples/README.md](../examples/README.md)** - Example servers
- **[Oneiric Documentation](https://github.com/lesleslie/oneiric)** - Configuration patterns

## Summary

mcp-common provides a **minimal, production-ready foundation** for MCP servers with:

- **6 core dependencies** (oneiric, pydantic, pyyaml, rich, typer, psutil)
- **~28MB memory overhead** (minimal impact)
- **~100ms startup time** (fast initialization)
- **Zero security vulnerabilities** (as of v0.7.0)
- **9 ecosystem projects** using mcp-common in production

**Ready to build?** See [QUICKSTART.md](../QUICKSTART.md) for 5-minute getting started guide!
