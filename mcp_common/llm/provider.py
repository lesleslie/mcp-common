"""OpenAI-compatible LLM provider for MiniMax, llama-server, Ollama."""

from __future__ import annotations

import logging
from typing import Any

from ._security import sanitize_error as _sanitize_error
from .config import ProviderConfig
from .exceptions import LLMError

logger = logging.getLogger(__name__)


class OpenAICompatibleProvider:
    """Single provider using the OpenAI-compatible API.

    The `openai` package is an optional dependency. It is lazy-imported
    and a clear ImportError is raised if not installed.
    """

    def __init__(self, config: ProviderConfig) -> None:
        try:
            import openai
        except ImportError as e:
            msg = (
                "openai package required for OpenAICompatibleProvider. "
                "Install with: pip install mcp-common[llm]"
            )
            raise ImportError(msg) from e

        self.name = config.name
        self.timeout_seconds = config.timeout_seconds
        self._config = config

        if config.require_auth:
            self._client = openai.AsyncOpenAI(
                api_key=config.api_key.get_secret_value(),
                base_url=config.base_url,
                max_retries=0,  # retries handled by FallbackChain
                timeout=config.timeout_seconds,
            )
        else:
            # Local no-auth provider (e.g. ollama, llama-server) —
            # send empty Authorization header so the SDK doesn't inject "Bearer no-auth"
            self._client = openai.AsyncOpenAI(
                api_key="no-auth",
                base_url=config.base_url,
                default_headers={"Authorization": ""},
                max_retries=0,
                timeout=config.timeout_seconds,
            )

        logger.info("Initialized provider %s: base_url=%s", config.name, config.base_url)

    async def execute(self, task: dict[str, Any]) -> dict[str, Any]:
        """Execute a chat completion request.

        Args:
            task: Dict with 'model', 'messages', and optional
                  'max_tokens', 'temperature'.

        Returns:
            Dict with 'content', 'provider', 'model', 'usage'.

        Raises:
            LLMError: If the API call fails.
        """
        try:
            response = await self._client.chat.completions.create(
                model=task["model"],
                messages=task["messages"],
                max_tokens=task.get("max_tokens", 4096),
                temperature=task.get("temperature", 0.7),
            )
            return {
                "content": response.choices[0].message.content or "",
                "provider": self.name,
                "model": task["model"],
                "usage": response.usage.model_dump() if response.usage else {},
            }
        except Exception as e:
            logger.warning("Provider %s failed: %s", self.name, _sanitize_error(str(e)))
            raise LLMError(f"Provider {self.name} failed: {_sanitize_error(str(e))}") from e

    async def health_check(self) -> bool:
        """Lightweight health check by listing models.

        Returns:
            True if provider is reachable, False otherwise.
        """
        try:
            await self._client.models.list()
            return True
        except Exception as e:
            logger.warning("Health check failed for %s: %s", self.name, _sanitize_error(str(e)))
            return False
