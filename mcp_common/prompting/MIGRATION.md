# Migration Guide: Prompting Adapter API Updates

This guide explains how to migrate code from the old API to the new improved API.

## Overview of Changes

### 1. Renamed Types
- **Old**: `PromptConfig` → **New**: `PromptAdapterSettings`
- Rationale: Align with Oneiric adapter naming conventions

### 2. Base Class Changed
- **Old**: `BaseModel` → **New**: `BaseSettings` (from pydantic-settings)
- Benefit: Environment variable support, Oneiric integration

### 3. Lifecycle Methods Added
- **New**: `initialize()` and `shutdown()` methods
- **New**: Context manager support (`async with`)
- Benefit: Explicit resource management

### 4. New Wrapper Class
- **New**: `PromptAdapter` class for direct instantiation
- Benefit: Simpler API for users who prefer class-based patterns

## Migration Examples

### Example 1: Basic Adapter Creation

#### Old Code
```python
from mcp_common.prompting import create_prompt_adapter, PromptConfig

# Create with default config
adapter = create_prompt_adapter()

# Create with custom config
config = PromptConfig(backend="pyobjc", timeout=30)
adapter = create_prompt_adapter(config=config)
```

#### New Code (Option A: Still Works)
```python
from mcp_common.prompting import create_prompt_adapter, PromptConfig

# Still works! PromptConfig is an alias for PromptAdapterSettings
adapter = create_prompt_adapter()

# But prefer the new name
config = PromptConfig(backend="pyobjc", timeout=30)
adapter = create_prompt_adapter(config=config)
```

#### New Code (Option B: Recommended)
```python
from mcp_common.prompting import create_prompt_adapter, PromptAdapterSettings

# Create with default config
adapter = create_prompt_adapter()
await adapter.initialize()

# Create with custom config
settings = PromptAdapterSettings(backend="pyobjc", timeout=30)
adapter = create_prompt_adapter(config=settings)
await adapter.initialize()

# Don't forget to cleanup
await adapter.shutdown()
```

### Example 2: Using Context Manager (Recommended)

#### Old Code
```python
from mcp_common.prompting import create_prompt_adapter

adapter = create_prompt_adapter()
result = await adapter.confirm("Continue?")
# No explicit cleanup
```

#### New Code (Recommended)
```python
from mcp_common.prompting import create_prompt_adapter

# Automatic cleanup with context manager
async with create_prompt_adapter() as adapter:
    result = await adapter.confirm("Continue?")
# Resources automatically cleaned up
```

### Example 3: Configuration from Environment Variables

#### Old Code
```python
from mcp_common.prompting import PromptConfig

# Had to manually load from environment
import os
backend = os.getenv("PROMPT_BACKEND", "auto")
timeout = int(os.getenv("PROMPT_TIMEOUT", "30"))
config = PromptConfig(backend=backend, timeout=timeout)
```

#### New Code (Automatic)
```python
from mcp_common.prompting import PromptAdapterSettings

# Automatically loads from environment variables
# Export: MCP_COMMON_PROMPT_BACKEND=pyobjc
# Export: MCP_COMMON_PROMPT_TIMEOUT=60
settings = PromptAdapterSettings()
# settings.backend and settings.timeout are loaded from env
```

### Example 4: Direct Class Instantiation

#### Old Code
```python
from mcp_common.prompting import create_prompt_adapter

# Only factory function available
adapter = create_prompt_adapter(backend="pyobjc")
```

#### New Code (New Feature)
```python
from mcp_common.prompting import PromptAdapter, PromptAdapterSettings

# Can now use class directly (more familiar to some users)
adapter = PromptAdapter(backend="pyobjc")
await adapter.initialize()
# Use adapter...
await adapter.shutdown()

# Or with settings
settings = PromptAdapterSettings(timeout=60)
adapter = PromptAdapter(settings=settings)
await adapter.initialize()
# Use adapter...
await adapter.shutdown()
```

### Example 5: Oneiric Integration

#### Old Code
```python
from mcp_common.prompting import PromptConfig
from oneiric import load_config

# Manual integration
oneiric_config = load_config()
prompt_config = oneiric_config.get("prompting", {})
config = PromptConfig(**prompt_config)
```

#### New Code (Built-in)
```python
from mcp_common.prompting import PromptAdapterSettings

# Automatic Oneiric integration with env overrides
settings = PromptAdapterSettings.from_settings()
# Loads from Oneiric, then applies MCP_COMMON_PROMPT_* env vars
```

## Breaking Changes

### None! Backward Compatibility Maintained

All old code continues to work:

1. **`PromptConfig` alias**: Still available, maps to `PromptAdapterSettings`
2. **Factory function**: `create_prompt_adapter()` still works the same
3. **No required changes**: Existing code works without modifications

### Recommended Updates (Optional)

While old code works, we recommend:

1. **Use lifecycle methods**: Call `initialize()` and `shutdown()` for explicit resource management
2. **Use context managers**: Prefer `async with` for automatic cleanup
3. **Update type names**: Use `PromptAdapterSettings` instead of `PromptConfig` in new code
4. **Leverage env vars**: Use environment variables for configuration

## Checklist for Migration

- [ ] **Read this guide** ✓
- [ ] **Test existing code** with new version (should work without changes)
- [ ] **Optional**: Update to use context managers where appropriate
- [ ] **Optional**: Add `initialize()`/`shutdown()` calls for explicit resource management
- [ ] **Optional**: Switch from `PromptConfig` to `PromptAdapterSettings` in new code
- [ ] **Optional**: Leverage environment variables for configuration
- [ ] **Run tests**: Verify everything still works

## API Quick Reference

### Old API (Still Supported)
```python
from mcp_common.prompting import create_prompt_adapter, PromptConfig

config = PromptConfig(backend="auto", timeout=30)
adapter = create_prompt_adapter(config=config)
result = await adapter.confirm("Continue?")
```

### New API (Recommended)
```python
from mcp_common.prompting import create_prompt_adapter, PromptAdapterSettings

# Option 1: Factory with lifecycle
settings = PromptAdapterSettings(backend="auto", timeout=30)
adapter = create_prompt_adapter(config=settings)
await adapter.initialize()
try:
    result = await adapter.confirm("Continue?")
finally:
    await adapter.shutdown()

# Option 2: Context manager (most recommended)
async with create_prompt_adapter(backend="auto") as adapter:
    result = await adapter.confirm("Continue?")

# Option 3: Direct class instantiation
from mcp_common.prompting import PromptAdapter

adapter = PromptAdapter(backend="auto")
await adapter.initialize()
try:
    result = await adapter.confirm("Continue?")
finally:
    await adapter.shutdown()
```

## Need Help?

- **Documentation**: See `README.md` in this directory
- **Examples**: Check `examples/` directory
- **Tests**: See `tests/unit/test_prompting/` for usage patterns
- **Issues**: Report problems on GitHub

## Summary

| Feature | Old API | New API | Migration Required |
|---------|---------|---------|-------------------|
| Factory function | ✅ `create_prompt_adapter()` | ✅ Same | ❌ No |
| Config class | ✅ `PromptConfig` | ✅ `PromptAdapterSettings` | ❌ No (alias provided) |
| Lifecycle methods | ❌ None | ✅ `initialize()`, `shutdown()` | ⚠️ Optional (recommended) |
| Context manager | ❌ None | ✅ `async with` | ⚠️ Optional (recommended) |
| Direct instantiation | ❌ None | ✅ `PromptAdapter` class | ⚠️ Optional |
| Environment variables | ❌ Manual | ✅ Automatic | ⚠️ Optional |
| Oneiric integration | ⚠️ Manual | ✅ Built-in | ⚠️ Optional |
