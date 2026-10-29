"""OpenAI-compatible LLM provider for MiniMax and llama-server."""

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
            # ``openai`` is an optional dependency from the ``llm`` PEP 735 group;
            # the runtime ``ImportError`` below gives a clear install hint.
            # The ``ty: unresolved-import`` suppression is needed in clean venvs
            # where the optional dep is not installed; locally ty resolves it
            # via venv bleed and reports the directive as unused (warning only,
            # does not fail the gate).
            import openai  # type: ignore[import-not-found]  # ty: ignore[unresolved-import, unused-ignore-comment]
        except ImportError as e:
            msg = (
                "openai package required for OpenAICompatibleProvider. "
                "Install with: pip install mcp-common[llm]"
            )
            raise ImportError(msg) from e

        self.name = config.name
        self.timeout_seconds = config.timeout_seconds
        self._config = config

        # Caller-supplied headers are merged with the SDK's own, never
        # substituted for them: ``Authorization`` still comes from
        # ``api_key``. The Bifrost gateway path uses this to carry the
        # gateway virtual key (``x-bf-vk``) and the cache headers.
        extra_headers = config.default_headers.copy()

        if config.require_auth:
            self._client = openai.AsyncOpenAI(
                api_key=config.api_key.get_secret_value(),
                base_url=config.base_url,
                max_retries=0,  # retries handled by FallbackChain
                timeout=config.timeout_seconds,
                default_headers=extra_headers,
            )
        else:
            # Local no-auth provider (llama-server) —
            # send empty Authorization header so the SDK doesn't inject "Bearer no-auth"
            self._client = openai.AsyncOpenAI(
                api_key="no-auth",
                base_url=config.base_url,
                default_headers={"Authorization": ""} | extra_headers,
                max_retries=0,
                timeout=config.timeout_seconds,
            )

        logger.info(
            "Initialized provider %s: base_url=%s", config.name, config.base_url
        )

    def _resolve_model(self, task: dict[str, Any]) -> str:
        """Pick model: task_routing[task_type] if configured, else task['model']."""
        task_type = task.get("task_type")
        if task_type and self._config.task_routing:
            routed = self._config.task_routing.get(task_type)
            if routed:
                return routed
        return task.get("model") or ""

    async def execute(self, task: dict[str, Any]) -> dict[str, Any]:
        """Execute a chat completion request.

        Args:
            task: Dict with 'model', 'messages', and optional
                  'task_type', 'max_tokens', 'temperature'.
                  When 'task_type' is present and this provider has a
                  matching task_routing entry, that model is used instead
                  of task['model'], enabling per-provider model selection
                  from a single FallbackChain call.

        Returns:
            Dict with 'content', 'provider', 'model', 'usage'.

        Raises:
            LLMError: If the API call fails.
        """
        model = self._resolve_model(task)
        try:
            create_kwargs: dict[str, Any] = {
                "model": model,
                "messages": task["messages"],
                "max_tokens": task.get("max_tokens", 4096),
                "temperature": task.get("temperature", 0.7),
            }
            # Per-call headers, for callers that need to vary them per
            # request (e.g. a per-tenant cache bucket). Omitted entirely
            # when absent so the SDK call shape is unchanged.
            call_headers = task.get("extra_headers")
            if call_headers:
                create_kwargs["extra_headers"] = dict(call_headers)
            response = await self._client.chat.completions.create(**create_kwargs)
            return {
                "content": response.choices[0].message.content or "",
                "provider": self.name,
                "model": model,
                "usage": response.usage.model_dump() if response.usage else {},
            }
        except Exception as e:
            logger.warning("Provider %s failed: %s", self.name, _sanitize_error(str(e)))
            raise LLMError(
                f"Provider {self.name} failed: {_sanitize_error(str(e))}"
            ) from e

    async def health_check(self) -> bool:
        """Lightweight health check by listing models.

        Returns:
            True if provider is reachable, False otherwise.
        """
        try:
            await self._client.models.list()
            return True
        except (
            OSError,
            TimeoutError,
            ValueError,
            TypeError,
            AttributeError,
            KeyError,
            IndexError,
            RuntimeError,
        ) as e:
            logger.warning(
                "Health check failed for %s: %s", self.name, _sanitize_error(str(e))
            )
            return False
