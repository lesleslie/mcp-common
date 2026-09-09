______________________________________________________________________

## status: active role: canonical date: 2026-07-16 last_reviewed: 2026-07-17 superseded_by: null blocks_on: [] topic: lifecycle

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
| **oneiric** | >=0.16.0 | Configuration & HTTP client | Oneiric patterns for YAML + env var config, connection pooling |
| **pydantic** | >=2.13.4 | Data validation | Type-safe settings with validation |
| **pydantic-settings** | >=2.14.1 | Settings management | Pydantic-based settings with env var loading |
| **pyyaml** | >=6.0.3 | YAML parsing | Configuration file loading |
| **rich** | >=15.0.0 | Terminal UI | Beautiful console output |
| **typer** | >=0.26.7 | CLI framework | Server lifecycle management |
| **psutil** | >=7.2.2 | System utilities | Process monitoring for PID management |
| **PyJWT** | >=2.8.0 | JWT auth | JWT token verification (auth subsystem) |
| **cryptography** | >=48.0.0 | Crypto primitives | Required by JWT signing/verification |
| **websockets** | >=16.0 | WebSocket client/server | Real-time server + client + TLS |
| **fastmcp** | >=3.4.0 | MCP server framework | FastMCP tool/middleware integration |

### Dependency Explanations

#### oneiric (Configuration & HTTP Client)

**Purpose**: Provides `MCPBaseSettings` configuration patterns and `HTTPClientAdapter` connection pooling.

**What it provides**:

- `MCPBaseSettings` - Base class for YAML + environment variable configuration
- `HTTPClientAdapter` - HTTP client with connection pooling (11x performance)
- `HTTPClientSettings` - Configuration for HTTP adapter
- Layered configuration loading (defaults → YAML → env vars)

**Why it's extracted**: Shared across 8 production MCP servers for consistent patterns.

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

### Development Dependency Group

Install with `uv sync --group dev` (PEP 735 dependency groups; the legacy
`pip install mcp-common[dev]` extras were removed when the project migrated
to PEP 735 in v0.25.0):

| Package | Version | Purpose |
|---------|---------|---------|
| **crackerjack** | >=0.65.3 | Quality control and CI/CD automation |
| **pytest-benchmark** | >=5.2.3 | Performance benchmarking |
| **respx** | >=0.23.1 | HTTP mocking for tests |
| **uv-bump** | >=0.5.0 | Version bumping automation |

### Optional Dependency Groups (PEP 735)

These are **NOT installed** with `mcp-common` by default. Install per-group
with `uv sync --group <name>`:

| Group | Purpose | Notable packages |
|-------|---------|------------------|
| **treesitter** | Tree-sitter parsing (used by session-buddy, mahavishnu, etc.) | `tree-sitter>=0.25.2`, `tree-sitter-python>=0.25.0`, `tree-sitter-go>=0.25.0` |
| **llm** | OpenAI-compatible LLM provider | `openai>=2.41.0` |
| **macos-prompts** | macOS native prompts via pyobjc | `pyobjc-core>=12.2` |
| **terminal-prompts** | Terminal prompting backends | (see `pyproject.toml [dependency-groups]`) |

**Migration note**: prior versions exposed `[treesitter,llm]` extras. Those
extras were removed in v0.25.0; downstream repos must now include the
`tree-sitter` and `openai` deps directly in their own `dependency-groups`.

### Optional Runtime Dependencies (transitive / not in pyproject)

| Package | Source | Notes |
|---------|--------|-------|
| **httpx** | Transitive via `oneiric` | Async HTTP client; pulled in by `oneiric.adapters.http` |

There is **no** optional `opentelemetry` distribution in this package —
mcp-common does not emit OpenTelemetry traces directly. Consumers wanting
tracing should add `opentelemetry-api` to their own dependencies.

## Dependency Tree

```
mcp-common (0.25.1)
├── oneiric (>=0.16.0)
│   ├── pydantic (>=2.13.4)
│   ├── pydantic-settings (>=2.14.1)
│   ├── pyyaml (>=6.0.3)
│   ├── httpx (transitive)
│   └── rich (>=15.0.0)
├── pydantic (>=2.13.4)
├── pydantic-settings (>=2.14.1)
├── pyyaml (>=6.0.3)
├── rich (>=15.0.0)
├── typer (>=0.26.7)
│   └── rich (>=15.0.0) [already listed]
├── psutil (>=7.2.2)
├── PyJWT (>=2.8.0)
│   └── cryptography (>=48.0.0)
├── cryptography (>=48.0.0) [already listed]
├── websockets (>=16.0)
└── fastmcp (>=3.4.0)
```

**Note**: `httpx` is included transitively via `oneiric` for HTTP client
functionality. Optional PEP 735 groups (`treesitter`, `llm`, `macos-prompts`,
`terminal-prompts`) are not part of the runtime tree — install with
`uv sync --group <name>`.

## Version Compatibility

### Python Version

**Required**: Python >=3.14

**Why**: mcp-common uses modern Python features:

- Type hint improvements (PEP 695)
- Match statements (PEP 634)
- Pydantic V2 features

### Dependency Version Policy

mcp-common uses **compatible release clauses** (`~=`) for stable dependencies:

```toml
[project]
dependencies = [
    "oneiric>=0.16.0",
    "pydantic>=2.13.4",
    "pydantic-settings>=2.14.1",
    "psutil>=7.2.2",
    "pyyaml>=6.0.3",
    "rich>=15.0.0",
    "typer>=0.26.7",
    "PyJWT>=2.8.0",
    "cryptography>=48.0.0",
    "websockets>=16.0",
    "fastmcp>=3.4.0",
]

[dependency-groups]
dev = [
    "crackerjack>=0.65.3",
    "pytest-benchmark>=5.2.3",
    "respx>=0.23.1",
    "uv-bump>=0.5.0",
]
treesitter = ["tree-sitter>=0.25.2", "tree-sitter-python>=0.25.0", "tree-sitter-go>=0.25.0"]
llm = ["openai>=2.41.0"]
macos-prompts = ["pyobjc-core>=12.2"]
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
| **Dhara** | Curator (State) | Configuration patterns, CLI factory |
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

**Current Status**: ✅ Zero critical vulnerabilities (as of v0.25.1)

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

# Install with development dependencies (PEP 735 group)
uv sync --group dev

# Install from git
pip install git+https://github.com/lesleslie/mcp-common.git
```

### Installation in Ecosystem Projects

```bash
# Using pip (recommended)
pip install mcp-common>=0.25.0

# Using uv (faster)
uv add mcp-common>=0.25.0

# Using poetry
poetry add mcp-common>=0.25.0
```

### Version Pinning

```bash
# Pin to specific version
pip install mcp-common==0.25.1

# Pin to minor version (allows patches)
pip install mcp-common~=0.25.0

# Minimum version (allows updates)
pip install "mcp-common>=0.25.0"
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

- **[README.md](../../README.md)** - Main project documentation
- **[CHANGELOG.md](../../CHANGELOG.md)** - Version history and changes
- **[examples/README.md](../../examples/README.md)** - Example servers
- **[Oneiric Documentation](https://github.com/lesleslie/oneiric)** - Configuration patterns

## Summary

mcp-common provides a **minimal, production-ready foundation** for MCP servers with:

- **11 core dependencies** (oneiric, pydantic, pydantic-settings, pyyaml, rich, typer, psutil, PyJWT, cryptography, websockets, fastmcp)
- **~28MB memory overhead** (minimal impact)
- **~100ms startup time** (fast initialization)
- **Zero security vulnerabilities** (as of v0.25.1)
- **10 ecosystem projects** using mcp-common in production

**Ready to build?** See [QUICKSTART.md](../../QUICKSTART.md) for 5-minute getting started guide!
