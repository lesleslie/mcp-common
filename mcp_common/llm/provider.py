"""OpenAI-compatible LLM provider for ZAI, Qwen, OpenAI."""

from __future__ import annotations

import logging
from typing import Any

from .config import ProviderConfig
from .exceptions import LLMError

logger = logging.getLogger(__name__)


class OpenAICompatibleProvider:
    """Single provider for ZAI, Qwen, OpenAI — all use the same API.

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
        self._config = config
        self._client = openai.AsyncOpenAI(
            api_key=config.api_key.get_secret_value(),
            base_url=config.base_url,
            max_retries=config.max_retries,
            timeout=config.timeout,
        )
        logger.info(
            "Initialized provider %s: base_url=%s",
            config.name,
            config.base_url,
        )

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
            logger.warning("Provider %s failed: %s", self.name, e)
            raise LLMError(f"Provider {self.name} failed: {e}") from e

    async def health_check(self) -> bool:
        """Lightweight health check by listing models.

        Returns:
            True if provider is reachable, False otherwise.
        """
        try:
            await self._client.models.list()
            return True
        except Exception as e:
            logger.warning("Health check failed for %s: %s", self.name, e)
            return False
