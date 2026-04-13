"""MCP Common LLM - Shared LLM provider infrastructure for the Bodai ecosystem.

Provides a unified interface for ZAI, OpenAI, Qwen, and Ollama providers
with YAML-driven configuration, fallback chains, and circuit breakers.

Usage:
    >>> from mcp_common.llm import LLMSettings, FallbackChain, TaskType
    >>> settings = LLMSettings.from_yaml("settings/models.yaml")
    >>> chain = FallbackChain.from_settings(settings)
    >>> result = await chain.execute({"model": "glm-4.7", "messages": [...]})
"""

from __future__ import annotations

from .config import LLMSettings, ProviderConfig
from .exceptions import AllProvidersExhaustedError, LLMError, ProviderUnavailableError
from .fallback import CircuitBreaker, FallbackChain
from .provider import OpenAICompatibleProvider
from .types import TaskType

__all__ = [
    "AllProvidersExhaustedError",
    "CircuitBreaker",
    "FallbackChain",
    "LLMError",
    "LLMSettings",
    "OpenAICompatibleProvider",
    "ProviderConfig",
    "ProviderUnavailableError",
    "TaskType",
]
