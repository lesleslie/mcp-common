"""Fallback chain with circuit breaker for LLM providers."""

from __future__ import annotations

import logging
import time
from typing import Any

from .config import LLMSettings
from .exceptions import AllProvidersExhaustedError
from .provider import OpenAICompatibleProvider

logger = logging.getLogger(__name__)


class CircuitBreaker:
    """Simple circuit breaker for a single provider.

    Opens after `failure_threshold` consecutive failures, resets after
    `reset_timeout` seconds. Half-open state allows a single probe.
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        reset_timeout: float = 60.0,
    ) -> None:
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self._failure_count = 0
        self._last_failure_time: float = 0

    @property
    def is_open(self) -> bool:
        """Whether the circuit breaker is open (provider should be skipped)."""
        if self._failure_count < self.failure_threshold:
            return False
        elapsed = time.monotonic() - self._last_failure_time
        if elapsed >= self.reset_timeout:
            return False  # Half-open: allow one attempt
        return True

    def record_success(self) -> None:
        """Record a successful call — resets the breaker."""
        self._failure_count = 0

    def record_failure(self) -> None:
        """Record a failed call — increments failure count."""
        self._failure_count += 1
        self._last_failure_time = time.monotonic()


class FallbackChain:
    """Ordered provider list with circuit breaker per provider.

    Tries providers in order, falling back on failure. Each provider
    has its own circuit breaker to avoid hammering a down provider.
    """

    def __init__(self, providers: list[OpenAICompatibleProvider]) -> None:
        self._providers = providers
        self._circuit_breakers: dict[str, CircuitBreaker] = {
            p.name: CircuitBreaker(failure_threshold=5, reset_timeout=60.0)
            for p in providers
        }

    @classmethod
    def from_settings(cls, settings: LLMSettings) -> FallbackChain:
        """Create a FallbackChain from LLMSettings.

        Args:
            settings: LLMSettings with provider configurations.

        Returns:
            FallbackChain with providers ordered by fallback_chain.
        """
        providers = []
        for provider_config in settings.get_enabled_providers():
            providers.append(OpenAICompatibleProvider(provider_config))
        return cls(providers)

    async def execute(self, task: dict[str, Any]) -> dict[str, Any]:
        """Try providers in order, falling back on failure.

        Args:
            task: Dict with 'model', 'messages', and optional params.

        Returns:
            Dict with 'content', 'provider', 'model', 'usage'.

        Raises:
            AllProvidersExhaustedError: When all providers fail.
        """
        last_error: Exception | None = None

        for provider in self._providers:
            breaker = self._circuit_breakers[provider.name]
            if breaker.is_open:
                logger.debug(
                    "Skipping provider %s (circuit breaker open)", provider.name
                )
                continue

            try:
                result = await provider.execute(task)
                breaker.record_success()
                return result
            except Exception as e:
                last_error = e
                breaker.record_failure()
                logger.warning(
                    "Provider %s failed: %s", provider.name, e, exc_info=True
                )

        raise AllProvidersExhaustedError(
            f"All {len(self._providers)} providers failed"
        ) from last_error
