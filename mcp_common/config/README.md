# Configuration Layer

## Purpose

The configuration layer standardizes settings management for MCP servers by extending ACB's `Settings` base class. It adds YAML loading, environment overrides, path expansion, and reusable validation helpers.

## Key Components

- `MCPBaseSettings` — Base class that loads from `settings/*.yaml`, validates display metadata, and offers helpers like `get_api_key()` and `get_data_dir()`.
- `ValidationMixin` — Shared mixin for enforcing field-level invariants across settings models.

## Usage

```python
from pathlib import Path
from mcp_common.config import MCPBaseSettings
from pydantic import Field


class WeatherSettings(MCPBaseSettings):
    api_key: str = Field(description="Weather API key")
    cache_dir: Path = Field(default=Path("~/.weather/cache"))


settings = WeatherSettings()
api_key = settings.get_api_key()
cache_dir = settings.get_data_dir("cache_dir")
```

Security helpers integrate automatically when available, ensuring API keys pass the validations defined in `mcp_common.security`.
