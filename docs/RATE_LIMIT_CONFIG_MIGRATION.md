# Rate Limit Configuration Migration Guide

**Phase 3.3 M1**: Migrate from hardcoded rate limits to centralized configuration

**Status**: ✅ Module created, 36/36 tests passing

---

## Overview

This guide shows how to migrate MCP servers from hardcoded rate limit values to the centralized `RateLimitConfig` system in mcp-common.

**Benefits**:
- ✅ **Eliminates magic numbers** - All rate limits in one place
- ✅ **Type-safe configuration** - Validated at creation time
- ✅ **Standardized profiles** - Conservative/Moderate/Aggressive
- ✅ **Server-specific configs** - Predefined for all 9 Phase 3 servers
- ✅ **Custom configs** - Easy to create new configurations
- ✅ **Immutable** - Frozen dataclasses prevent accidental modification

---

## Quick Migration Examples

### Example 1: Using Server-Specific Config

**Before** (hardcoded values):
```python
from fastmcp.server.middleware.rate_limiting import RateLimitingMiddleware

# Hardcoded magic numbers
rate_limiter = RateLimitingMiddleware(
    max_requests_per_second=10.0,
    burst_capacity=30,
    global_limit=True,
)
mcp.add_middleware(rate_limiter)
```

**After** (using server config):
```python
from fastmcp.server.middleware.rate_limiting import RateLimitingMiddleware
from mcp_common.middleware import get_config_for_server

# Get predefined config for this server
config = get_config_for_server("session-mgmt-mcp")

rate_limiter = RateLimitingMiddleware(
    max_requests_per_second=config.max_requests_per_second,
    burst_capacity=config.burst_capacity,
    global_limit=config.global_limit,
)
mcp.add_middleware(rate_limiter)
```

### Example 2: Using Profile

**Before** (hardcoded):
```python
rate_limiter = RateLimitingMiddleware(
    max_requests_per_second=15.0,  # What does 15 mean?
    burst_capacity=40,  # Why 40?
    global_limit=True,
)
```

**After** (using profile):
```python
from mcp_common.middleware import get_profile_config, RateLimitProfile

# Semantic profile selection
config = get_profile_config(RateLimitProfile.AGGRESSIVE)  # Clear intent!

rate_limiter = RateLimitingMiddleware(
    max_requests_per_second=config.max_requests_per_second,
    burst_capacity=config.burst_capacity,
    global_limit=config.global_limit,
)
```

### Example 3: Custom Configuration

**Before** (hardcoded):
```python
rate_limiter = RateLimitingMiddleware(
    max_requests_per_second=20.0,
    burst_capacity=50,
    global_limit=False,  # Per-client limiting
)
```

**After** (validated custom config):
```python
from mcp_common.middleware import create_custom_config

# Validated custom configuration
config = create_custom_config(
    max_requests_per_second=20.0,
    burst_capacity=50,
    global_limit=False,
    description="Custom per-client rate limiting for high-throughput API",
)

rate_limiter = RateLimitingMiddleware(
    max_requests_per_second=config.max_requests_per_second,
    burst_capacity=config.burst_capacity,
    global_limit=config.global_limit,
)
```

---

## Available Profiles

### 1. Conservative Profile

**Use for**: Email APIs, external services with strict limits

```python
from mcp_common.middleware import RateLimitProfile, get_profile_config

config = get_profile_config(RateLimitProfile.CONSERVATIVE)
# Result: 5.0 req/sec, burst 15
```

**Examples**: mailgun-mcp

### 2. Moderate Profile

**Use for**: Standard APIs, balanced throughput/stability

```python
config = get_profile_config(RateLimitProfile.MODERATE)
# Result: 10.0 req/sec, burst 20
```

**Examples**: session-mgmt-mcp, opera-cloud-mcp, unifi-mcp

### 3. Aggressive Profile

**Use for**: Core infrastructure, local frameworks, high throughput

```python
config = get_profile_config(RateLimitProfile.AGGRESSIVE)
# Result: 15.0 req/sec, burst 40
```

**Examples**: acb, fastblocks

---

## Server-Specific Configurations

All 9 Phase 3 servers have predefined configurations:

```python
from mcp_common.middleware import SERVER_CONFIGS

# View all server configs
for server_name, config in SERVER_CONFIGS.items():
    print(f"{server_name}: {config.max_requests_per_second} req/sec, burst {config.burst_capacity}")
```

**Output**:
```
acb: 15.0 req/sec, burst 40
fastblocks: 15.0 req/sec, burst 40 (inherits from ACB)
session-mgmt-mcp: 12.0 req/sec, burst 16
crackerjack: 12.0 req/sec, burst 35 (higher burst for test/lint)
opera-cloud-mcp: 10.0 req/sec, burst 20
unifi-mcp: 10.0 req/sec, burst 20
raindropio-mcp: 8.0 req/sec, burst 16
mailgun-mcp: 5.0 req/sec, burst 15
excalidraw-mcp: 12.0 req/sec, burst 16
```

---

## Step-by-Step Migration

### Step 1: Add mcp-common Dependency

```bash
# If not already added
uv add mcp-common
```

### Step 2: Import Configuration Module

```python
# Add to imports
from mcp_common.middleware import get_config_for_server
# Or for profiles:
from mcp_common.middleware import get_profile_config, RateLimitProfile
# Or for custom:
from mcp_common.middleware import create_custom_config
```

### Step 3: Replace Hardcoded Values

Find rate limiter initialization:
```python
# OLD (find this pattern):
rate_limiter = RateLimitingMiddleware(
    max_requests_per_second=10.0,  # ❌ Magic number
    burst_capacity=20,  # ❌ Magic number
    global_limit=True,
)
```

Replace with configuration lookup:
```python
# NEW (replace with this):
config = get_config_for_server("your-server-name")  # ✅ Semantic
rate_limiter = RateLimitingMiddleware(
    max_requests_per_second=config.max_requests_per_second,
    burst_capacity=config.burst_capacity,
    global_limit=config.global_limit,
)
```

### Step 4: Update ServerPanels (Optional)

Show configuration source in server panels:
```python
from mcp_common.ui import ServerPanels

panels = ServerPanels(
    server_name="My Server",
    version="1.0.0",
    transport="stdio",
)

# Add rate limiting with config source
config = get_config_for_server("my-server")
panels.add_rate_limiting(
    max_requests_per_second=config.max_requests_per_second,
    burst_capacity=config.burst_capacity,
    description=f"{config.description} (from SERVER_CONFIGS)",
)
```

### Step 5: Test Configuration

```python
# Verify configuration loads correctly
config = get_config_for_server("your-server")
print(f"Rate limit config: {config.max_requests_per_second} req/sec, burst {config.burst_capacity}")
print(f"Description: {config.description}")

# Config is immutable (will raise AttributeError)
try:
    config.max_requests_per_second = 999
except AttributeError:
    print("✅ Config is properly immutable")
```

---

## Adding New Servers

If your server is not in `SERVER_CONFIGS`, you have two options:

### Option 1: Use a Profile (Recommended for new servers)

```python
from mcp_common.middleware import get_profile_config, RateLimitProfile

# Choose appropriate profile
if is_email_api:
    config = get_profile_config(RateLimitProfile.CONSERVATIVE)
elif is_core_infrastructure:
    config = get_profile_config(RateLimitProfile.AGGRESSIVE)
else:
    config = get_profile_config(RateLimitProfile.MODERATE)
```

### Option 2: Add to SERVER_CONFIGS

Edit `mcp_common/middleware/rate_limit_config.py`:

```python
SERVER_CONFIGS: dict[str, RateLimitConfig] = {
    # ... existing servers ...

    # Add your server
    "my-new-server": RateLimitConfig(
        max_requests_per_second=10.0,
        burst_capacity=20,
        global_limit=True,
        description="My new server - moderate rate limiting",
    ),
}
```

Then submit a PR to mcp-common.

### Option 3: Create Custom Config

```python
from mcp_common.middleware import create_custom_config

# For server-specific needs
my_config = create_custom_config(
    max_requests_per_second=25.0,
    burst_capacity=60,
    global_limit=False,  # Per-client
    description="Custom config for my-new-server with per-client limiting",
)
```

---

## Configuration Validation

The `RateLimitConfig` dataclass automatically validates:

### 1. Positive Request Rate
```python
# ❌ Will raise ValueError
RateLimitConfig(max_requests_per_second=0.0, burst_capacity=10)
RateLimitConfig(max_requests_per_second=-5.0, burst_capacity=10)

# ✅ Valid
RateLimitConfig(max_requests_per_second=10.0, burst_capacity=20)
```

### 2. Valid Burst Capacity
```python
# ❌ Will raise ValueError
RateLimitConfig(max_requests_per_second=10.0, burst_capacity=0)
RateLimitConfig(max_requests_per_second=10.0, burst_capacity=-5)

# ✅ Valid
RateLimitConfig(max_requests_per_second=10.0, burst_capacity=20)
```

### 3. Burst ≥ Rate
```python
# ❌ Will raise ValueError (burst should be >= rate)
RateLimitConfig(max_requests_per_second=20.0, burst_capacity=10)

# ✅ Valid
RateLimitConfig(max_requests_per_second=10.0, burst_capacity=20)
```

---

## Testing Your Migration

After migrating, verify:

```python
def test_rate_limiting_config():
    """Test that rate limiting uses centralized configuration."""
    from mcp_common.middleware import get_config_for_server

    # Get your server's config
    config = get_config_for_server("your-server")

    # Verify values are loaded
    assert config.max_requests_per_second > 0
    assert config.burst_capacity >= config.max_requests_per_second
    assert config.description  # Should have meaningful description

    # Verify immutability
    with pytest.raises(AttributeError):
        config.max_requests_per_second = 999
```

---

## Common Patterns by Server Type

### External API Servers (with authentication)
- **Pattern**: Use `get_config_for_server()` with server name
- **Example**: mailgun-mcp, opera-cloud-mcp, raindropio-mcp

```python
config = get_config_for_server("my-api-server")
```

### Local Framework Servers (no external APIs)
- **Pattern**: Use `RateLimitProfile.AGGRESSIVE` or inherit from parent
- **Example**: acb, crackerjack, fastblocks

```python
config = get_profile_config(RateLimitProfile.AGGRESSIVE)
```

### Hybrid Servers (optional external APIs)
- **Pattern**: Use moderate profile with custom description
- **Example**: session-mgmt-mcp (Ollama vs OpenAI/Gemini)

```python
config = get_config_for_server("session-mgmt-mcp")
# Or create custom:
config = create_custom_config(
    max_requests_per_second=12.0,
    burst_capacity=16,
    description="Hybrid local + optional external API",
)
```

---

## Troubleshooting

### Issue: `KeyError` when getting server config

**Problem**:
```python
config = get_config_for_server("my-server")
# KeyError: 'my-server'
```

**Solution**: Use a profile or create custom config:
```python
# Option 1: Use profile
config = get_profile_config(RateLimitProfile.MODERATE)

# Option 2: Create custom
config = create_custom_config(10.0, 20)
```

### Issue: `ValueError` during config creation

**Problem**:
```python
config = RateLimitConfig(max_requests_per_second=-5.0, burst_capacity=10)
# ValueError: max_requests_per_second must be positive
```

**Solution**: Use valid positive values:
```python
config = RateLimitConfig(max_requests_per_second=10.0, burst_capacity=20)
```

### Issue: Config values don't update

**Problem**: Configs are immutable (frozen dataclasses)

**Solution**: Create a new config instead of modifying:
```python
# ❌ Won't work
config.max_requests_per_second = 15.0

# ✅ Create new config
config = create_custom_config(15.0, 40)
```

---

## Migration Checklist

- [ ] Add mcp-common dependency
- [ ] Import configuration module
- [ ] Replace hardcoded rate limit values
- [ ] Update ServerPanels to show config source
- [ ] Test configuration loads correctly
- [ ] Verify rate limiting still works
- [ ] Add tests for configuration usage
- [ ] Update documentation to reference centralized config
- [ ] Remove magic number comments (no longer needed!)

---

## See Also

- **[Rate Limit Load Testing](./RATE_LIMIT_LOAD_TESTING.md)**: Test your rate limiting
- **[Phase 3 Consolidated Review](./PHASE3_CONSOLIDATED_REVIEW.md)**: M1 issue details
- **[Integration Tracking](../INTEGRATION_TRACKING.md)**: Phase 3 server status

---

**Created**: 2025-01-27 (Phase 3.3 M1)
**Status**: ✅ Module ready, migration guide complete
**Tests**: 36/36 passing

