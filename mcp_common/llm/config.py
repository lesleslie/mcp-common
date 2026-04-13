"""YAML-driven LLM provider configuration."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, SecretStr, model_validator

logger = logging.getLogger(__name__)


class ProviderConfig(BaseModel):
    """Configuration for a single LLM provider."""

    name: str = ""
    enabled: bool = True
    base_url: str = ""
    api_key: SecretStr = SecretStr("")
    models: dict[str, str] = {}
    priority: int = 1
    timeout: int = 30
    max_retries: int = 2
    task_routing: dict[str, str] = {}
    fallback: dict[str, str] = {}

    model_config = {"extra": "forbid"}

    @model_validator(mode="after")
    def resolve_env_vars(self) -> ProviderConfig:
        """Resolve ${ENV_VAR} patterns in api_key and base_url."""
        if self.base_url.startswith("${") and self.base_url.endswith("}"):
            env_var = self.base_url[2:-1]
            resolved = os.getenv(env_var, "")
            if resolved:
                self.base_url = resolved

        raw_key = self.api_key.get_secret_value()
        if raw_key.startswith("${") and raw_key.endswith("}"):
            env_var = raw_key[2:-1]
            resolved = os.getenv(env_var, "")
            if resolved:
                self.api_key = SecretStr(resolved)

        return self

    def get_model_for_task(self, task_type: str) -> str | None:
        """Get the model ID for a given task type."""
        return self.task_routing.get(task_type)


class LLMSettings(BaseModel):
    """Loaded from settings/models.yaml or equivalent."""

    providers: dict[str, dict[str, Any]] = {}
    default_provider: str = "zai"
    fallback_chain: list[str] = ["zai", "ollama"]
    free_tier_provider: str = "zai-free"

    model_config = {"extra": "forbid"}

    @classmethod
    def from_yaml(cls, path: str | Path) -> LLMSettings:
        """Load settings from a YAML file.

        Args:
            path: Path to the YAML configuration file.

        Returns:
            LLMSettings instance with parsed provider configs.
        """
        path = Path(path)
        if not path.exists():
            logger.warning("LLM config file not found: %s", path)
            return cls()

        with open(path) as f:
            raw = yaml.safe_load(f) or {}

        providers = {}
        skip_keys = {"default_provider", "fallback_chain", "free_tier_provider"}
        for key, value in raw.items():
            if key in skip_keys or not isinstance(value, dict):
                continue
            if key.startswith("#"):
                continue
            value_copy = dict(value)
            value_copy["name"] = key
            providers[key] = value_copy

        return cls(
            providers=providers,
            default_provider=raw.get("default_provider", "zai"),
            fallback_chain=raw.get("fallback_chain", ["zai", "ollama"]),
            free_tier_provider=raw.get("free_tier_provider", "zai-free"),
        )

    def get_provider(self, name: str) -> ProviderConfig | None:
        """Get a resolved provider configuration by name.

        Args:
            name: Provider name (e.g., "zai", "ollama").

        Returns:
            ProviderConfig if found and enabled, None otherwise.
        """
        raw = self.providers.get(name)
        if not raw:
            return None
        config = ProviderConfig(**raw)
        if not config.enabled:
            return None
        return config

    def get_enabled_providers(self) -> list[ProviderConfig]:
        """Get all enabled providers sorted by priority."""
        configs = []
        for name in self.fallback_chain:
            config = self.get_provider(name)
            if config:
                configs.append(config)
        configs.sort(key=lambda c: c.priority)
        return configs
