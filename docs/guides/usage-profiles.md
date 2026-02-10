# MCP Common Usage Profiles Guide

This guide explains the three usage profiles available in mcp-common and helps you choose the right one for your MCP server.

## Overview

MCP Common provides three pre-configured server profiles for different use cases:

| Profile | Features | Use Case | Complexity |
|---------|----------|----------|------------|
| **MinimalServer** | Basic tools only | Simple servers | Lowest |
| **StandardServer** | Tools + Resources | Most servers | Medium |
| **FullServer** | All features (tools, resources, prompts, auth, telemetry) | Production servers | Highest |

## Profile Comparison

### MinimalServer

**Features:**
- Basic tool registration
- Simple configuration
- Fast startup
- Minimal dependencies

**What's Included:**
- Tools: Yes
- Resources: No
- Prompts: No
- Auth: No
- Telemetry: No
- Health checks: Basic

**Best For:**
- Quick prototypes
- Simple utility servers
- Stateless tools
- Development environments
- Learning MCP basics

**Example:**
```python
from mcp_common.profiles import MinimalServer

server = MinimalServer(name="minimal-server")

@server.tool()
def hello(name: str) -> str:
    return f"Hello {name}"

server.run()
```

**When to Choose Minimal:**
- You only need to expose a few simple functions
- You don't need dynamic resources or configuration management
- You want the fastest possible startup time
- You're building a prototype or proof-of-concept
- You're learning MCP server development

### StandardServer

**Features:**
- Tool registration
- Resource management
- Enhanced configuration
- Rich UI support

**What's Included:**
- Tools: Yes
- Resources: Yes
- Prompts: No
- Auth: No
- Telemetry: No
- Health checks: Enhanced

**Best For:**
- Production servers (most common)
- Servers with dynamic resources
- Servers needing configuration management
- Data access servers
- API integration servers

**Example:**
```python
from mcp_common.profiles import StandardServer

server = StandardServer(
    name="standard-server",
    description="Standard MCP server"
)

@server.tool()
def search(query: str) -> dict:
    return {"results": [...]}

@server.resource("config://{name}")
def get_config(name: str) -> dict:
    return load_config(name)

server.run()
```

**When to Choose Standard:**
- You need to expose dynamic resources (config, data, status)
- You want a good balance of features and simplicity
- You're building a production server for internal use
- You need configuration management capabilities
- This is your first production MCP server

### FullServer

**Features:**
- Tool registration
- Resource management
- Prompt templates
- Authentication
- Telemetry/observability
- Multi-worker support

**What's Included:**
- Tools: Yes
- Resources: Yes
- Prompts: Yes
- Auth: Yes (JWT)
- Telemetry: Yes (OpenTelemetry)
- Health checks: Comprehensive
- Workers: Multi-worker support

**Best For:**
- Production servers
- Multi-user environments
- Servers requiring authentication
- Servers needing observability
- High-traffic deployments
- Enterprise environments

**Example:**
```python
from mcp_common.profiles import FullServer
from mcp_common.auth import JWTAuth
from mcp_common.telemetry import OpenTelemetry

auth = JWTAuth(secret="your-secret")
telemetry = OpenTelemetry(endpoint="http://jaeger:4317")

server = FullServer(
    name="full-server",
    auth=auth,
    telemetry=telemetry
)

@server.tool()
def process_data(data: dict) -> dict:
    return transform(data)

@server.resource("data://{id}")
def get_data(id: str) -> str:
    return fetch_data(id)

@server.prompt("analyze")
def analyze_prompt(data: str) -> str:
    return f"Analyze this data: {data}"

server.run(workers=4)
```

**When to Choose Full:**
- You need multiple users with authentication
- You require observability (tracing, metrics)
- You need to handle high traffic
- You want prompt templates for reusable AI interactions
- You're building an enterprise-grade solution
- You need multi-worker scaling

## Decision Tree

Use this decision tree to choose the right profile:

```
Start
  │
  ├─ Do you need authentication?
  │   ├─ Yes → FullServer
  │   └─ No  ↓
  │
  ├─ Do you need observability/telemetry?
  │   ├─ Yes → FullServer
  │   └─ No  ↓
  │
  ├─ Do you need prompt templates?
  │   ├─ Yes → FullServer
  │   └─ No  ↓
  │
  ├─ Do you need resources (config, data, status)?
  │   ├─ Yes → StandardServer
  │   └─ No  ↓
  │
  └─ MinimalServer
```

## Migration Paths

You can easily migrate between profiles as your needs evolve:

### Minimal → Standard

Add resources to your minimal server:

```python
# Before (MinimalServer)
server = MinimalServer(name="my-server")

@server.tool()
def get_data() -> dict:
    return fetch_data()

# After (StandardServer)
server = StandardServer(name="my-server")

@server.tool()
def search(query: str) -> dict:
    return search_data(query)

@server.resource("data://{id}")
def get_data(id: str) -> str:
    return json.dumps(fetch_data(id))
```

### Standard → Full

Add authentication and telemetry:

```python
# Before (StandardServer)
server = StandardServer(name="my-server")

# After (FullServer)
auth = JWTAuth(secret=os.getenv("JWT_SECRET"))
telemetry = OpenTelemetry(endpoint=os.getenv("JAEGER_ENDPOINT"))

server = FullServer(
    name="my-server",
    auth=auth,
    telemetry=telemetry
)
```

## Configuration Examples

### Minimal Server Configuration

`settings/minimal-server.yaml`:
```yaml
server_name: "Minimal MCP Server"
log_level: INFO
```

### Standard Server Configuration

`settings/standard-server.yaml`:
```yaml
server_name: "Standard MCP Server"
description: "My standard server"
log_level: INFO
enable_http_transport: true
http_port: 8000
```

### Full Server Configuration

`settings/full-server.yaml`:
```yaml
server_name: "Full MCP Server"
description: "Production-ready server"
log_level: INFO
enable_http_transport: true
http_port: 8000
auth_enabled: true
telemetry_enabled: true
workers: 4
```

## Performance Considerations

| Profile | Startup Time | Memory Usage | Throughput |
|---------|--------------|--------------|------------|
| Minimal | Fastest | Lowest | Medium |
| Standard | Medium | Medium | High |
| Full | Slowest | Highest | Highest (with workers) |

**Recommendations:**
- Use **Minimal** for development and testing
- Use **Standard** for most production servers
- Use **Full** for high-traffic or multi-user scenarios

## Best Practices

### 1. Start Simple

Begin with MinimalServer and upgrade as needed:

```python
# Phase 1: Prototype
server = MinimalServer(name="my-server")

# Phase 2: Add resources
server = StandardServer(name="my-server")

# Phase 3: Add auth and telemetry
server = FullServer(name="my-server", auth=auth, telemetry=telemetry)
```

### 2. Use Profile-Specific Features

Each profile has unique features - use them:

**Minimal:**
```python
@server.tool()
def simple_function(arg: str) -> str:
    return arg
```

**Standard:**
```python
@server.resource("config://{name}")
def get_config(name: str) -> str:
    return json.dumps(load_config(name))
```

**Full:**
```python
@server.prompt("analyze")
def analyze_prompt(data: str) -> str:
    return f"Analyze: {data}"
```

### 3. Configure for Your Environment

Use YAML files for environment-specific config:

```yaml
# settings/my-server-prod.yaml
auth_enabled: true
telemetry_enabled: true
workers: 4

# settings/my-server-dev.yaml
auth_enabled: false
telemetry_enabled: false
workers: 1
```

### 4. Monitor Health

Use health checks appropriate for your profile:

```python
# Minimal
health = server.health_check()
assert health["status"] == "healthy"

# Standard
health = server.health_check()
assert health["tools"] > 0
assert health["resources"] > 0

# Full
health = server.health_check()
assert health["auth"]["enabled"] == True
assert health["telemetry"]["enabled"] == True
```

## Examples

See the `examples/` directory for complete working examples:

- `examples/minimal_server.py` - Minimal server with basic tools
- `examples/standard_server.py` - Standard server with tools and resources
- `examples/full_server.py` - Full server with all features

Run them:

```bash
python examples/minimal_server.py
python examples/standard_server.py
python examples/full_server.py
```

## Summary

Choose your profile based on your needs:

- **MinimalServer**: Quick prototypes and simple tools
- **StandardServer**: Most production servers (recommended default)
- **FullServer**: Enterprise-grade with auth and observability

All profiles share the same basic API, making it easy to migrate as your needs evolve.

For more information, see:
- [README.md](../../README.md) - Main documentation
- [examples/README.md](../../examples/README.md) - Example servers
