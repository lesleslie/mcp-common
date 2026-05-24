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
    api_key_env: str | None = None
    require_auth: bool = True
    models: dict[str, str] = {}
    priority: int = 1
    timeout: int = 30
    timeout_seconds: int = 30
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

        # Sync timeout_seconds from legacy timeout if not explicitly set
        if self.timeout_seconds == 30 and self.timeout != 30:
            self.timeout_seconds = self.timeout

        return self

    def get_model_for_task(self, task_type: str) -> str | None:
        """Get the model ID for a given task type."""
        return self.task_routing.get(task_type)


class LLMSettings(BaseModel):
    """Loaded from settings/models.yaml or equivalent."""

    providers: dict[str, dict[str, Any]] = {}
    default_provider: str = "minimax"
    fallback_chain: list[str] = ["minimax", "llama_server", "ollama"]

    model_config = {"extra": "forbid"}

    @classmethod
    def from_yaml(cls, path: str | Path) -> LLMSettings:
        """Load settings from a YAML file.

        Accepts both the legacy flat schema (top-level provider keys) and
        the new schema (providers: + fallback_chain:). Both shapes coexist
        during the transition period.

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
            data: dict[str, Any] = yaml.safe_load(f) or {}

        reserved = {
            "default_provider",
            "fallback_chain",
            "free_tier_provider",
            "bifrost",
            "providers",
        }
        providers: dict[str, Any] = data.get("providers", {})
        if not providers:
            # Legacy flat schema: extract provider configs from top-level keys
            for key, val in data.items():
                if key in reserved or key.startswith("#") or not isinstance(val, dict):
                    continue
                val_copy = dict(val)
                val_copy["name"] = key
                providers[key] = val_copy
            if providers:
                logger.debug(
                    "Loaded LLM settings using legacy flat schema — "
                    "migrate to 'providers:' top-level key."
                )

        return cls(
            providers=providers,
            default_provider=data.get("default_provider", "minimax"),
            fallback_chain=data.get(
                "fallback_chain", ["minimax", "llama_server", "ollama"]
            ),
        )

    def get_provider(self, name: str) -> ProviderConfig | None:
        """Get a resolved provider configuration by name.

        Args:
            name: Provider name (e.g., "minimax", "ollama").

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
        """Return providers in fallback_chain order, excluding disabled or key-missing ones."""
        result = []
        for name in self.fallback_chain:
            raw = self.providers.get(name)
            if raw is None:
                logger.warning(
                    "Provider %s in fallback_chain not found in config", name
                )
                continue
            cfg = ProviderConfig(**raw)
            if not cfg.enabled:
                continue
            # Fail-closed: skip cloud providers that require auth but have no token configured
            if cfg.require_auth:
                key = cfg.api_key.get_secret_value()
                env_name = cfg.api_key_env or ""
                if not key or not key.strip() or key.startswith("${"):
                    logger.warning(
                        "Provider %s skipped: env var %s is not set.",
                        name,
                        env_name or "unknown",
                    )
                    continue
            result.append(cfg)
        return result
