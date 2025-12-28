"""MCP Server settings with layered configuration.

Provides Pydantic-based settings with YAML + environment variable loading
following the Oneiric configuration pattern.
"""

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field


class MCPServerSettings(BaseModel):
    """MCP Server configuration with layered loading.

    Settings are loaded in priority order (highest to lowest):
    1. CLI flags (passed directly to factory)
    2. Environment variables (MCP_SERVER_*)
    3. settings/local.yaml (gitignored, developer overrides)
    4. settings/{server_name}.yaml (checked into repo)
    5. Defaults defined below

    Example:
        >>> settings = MCPServerSettings.load("my-server")
        >>> print(settings.pid_path())
        .oneiric_cache/mcp_server.pid

    Attributes:
        server_name: Server identifier (e.g., 'session-buddy', 'crackerjack')
        cache_root: Cache directory for PID files and snapshots
        health_ttl_seconds: Snapshot freshness threshold in seconds
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
        log_file: Optional log file path (None = stdout only)
    """

    server_name: str = Field(description="Server identifier")
    cache_root: Path = Field(
        default=Path(".oneiric_cache"), description="Cache directory for PID and snapshots"
    )
    health_ttl_seconds: float = Field(
        default=60.0, ge=1.0, description="Snapshot freshness threshold (seconds)"
    )
    log_level: str = Field(default="INFO", description="Logging level")
    log_file: Path | None = Field(default=None, description="Optional log file path")

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def pid_path(self) -> Path:
        """Get PID file path.

        Returns:
            Path to PID file (.oneiric_cache/mcp_server.pid)
        """
        return self.cache_root / "mcp_server.pid"

    def health_snapshot_path(self) -> Path:
        """Get runtime health snapshot path.

        Returns:
            Path to health snapshot (.oneiric_cache/runtime_health.json)
        """
        return self.cache_root / "runtime_health.json"

    def telemetry_snapshot_path(self) -> Path:
        """Get runtime telemetry snapshot path.

        Returns:
            Path to telemetry snapshot (.oneiric_cache/runtime_telemetry.json)
        """
        return self.cache_root / "runtime_telemetry.json"

    @classmethod
    def load(
        cls,
        server_name: str,
        config_path: Path | None = None,
        env_prefix: str = "MCP_SERVER",
    ) -> "MCPServerSettings":
        """Load settings with layered configuration.

        Priority (highest to lowest):
        1. Explicit config_path (if provided)
        2. Environment variables ({env_prefix}_{FIELD})
        3. settings/local.yaml (gitignored)
        4. settings/{server_name}.yaml
        5. Defaults

        Args:
            server_name: Server identifier (e.g., 'session-buddy')
            config_path: Optional explicit config file path
            env_prefix: Environment variable prefix (default: 'MCP_SERVER')

        Returns:
            Loaded settings instance with all layers applied

        Example:
            >>> # Load with defaults
            >>> settings = MCPServerSettings.load("my-server")
            >>>
            >>> # Override with environment
            >>> os.environ["MCP_SERVER_LOG_LEVEL"] = "DEBUG"
            >>> settings = MCPServerSettings.load("my-server")
            >>> assert settings.log_level == "DEBUG"
            >>>
            >>> # Override with explicit config
            >>> settings = MCPServerSettings.load(
            ...     "my-server",
            ...     config_path=Path("custom_config.yaml")
            ... )
        """
        data: dict[str, Any] = {"server_name": server_name}

        # Load all configuration layers
        cls._load_server_yaml_layer(data, server_name)
        cls._load_local_yaml_layer(data)
        cls._load_environment_layer(data, env_prefix)
        cls._load_explicit_config_layer(data, config_path)

        return cls(**data)

    @classmethod
    def _load_server_yaml_layer(cls, data: dict[str, Any], server_name: str) -> None:
        """Load Layer 1: Server defaults (settings/{server_name}.yaml)."""
        server_yaml = Path("settings") / f"{server_name}.yaml"
        if server_yaml.exists():
            with server_yaml.open() as f:
                yaml_data: dict[str, Any] = yaml.safe_load(f) or {}
                data.update(yaml_data)

    @classmethod
    def _load_local_yaml_layer(cls, data: dict[str, Any]) -> None:
        """Load Layer 2: Local overrides (settings/local.yaml)."""
        local_yaml = Path("settings") / "local.yaml"
        if local_yaml.exists():
            with local_yaml.open() as f:
                local_data: dict[str, Any] = yaml.safe_load(f) or {}
                data.update(local_data)

    @classmethod
    def _load_environment_layer(cls, data: dict[str, Any], env_prefix: str) -> None:
        """Load Layer 3: Environment variables."""
        for field_name in cls.model_fields:
            env_var = f"{env_prefix}_{field_name.upper()}"
            if env_var in os.environ:
                raw_env_value = os.environ[env_var]
                # Type coercion for common types
                if field_name == "health_ttl_seconds":
                    data[field_name] = float(raw_env_value)
                elif field_name in ("cache_root", "log_file"):
                    data[field_name] = Path(raw_env_value) if raw_env_value else None
                else:
                    data[field_name] = raw_env_value

    @classmethod
    def _load_explicit_config_layer(cls, data: dict[str, Any], config_path: Path | None) -> None:
        """Load Layer 4: Explicit config path (highest priority)."""
        if config_path is not None and config_path.exists():
            with config_path.open() as f:
                explicit_data: dict[str, Any] = yaml.safe_load(f) or {}
                data.update(explicit_data)
