"""Fallback chain with circuit breaker for LLM providers."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from ._security import sanitize_error as _sanitize_error
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
    """Ordered provider list with per-tier retry and circuit breaker.

    Tries providers in order with up to `max_attempts_per_tier` retries
    per provider before advancing to the next tier. Circuit breakers count
    per tier-call (after all retries exhausted), not per attempt.
    asyncio.CancelledError always propagates immediately.
    """

    def __init__(
        self,
        providers: list[OpenAICompatibleProvider],
        max_attempts_per_tier: int = 3,
    ) -> None:
        self._providers = providers
        self._max_attempts = max_attempts_per_tier
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
        providers = [
            OpenAICompatibleProvider(provider_config)
            for provider_config in settings.get_enabled_providers()
        ]
        return cls(providers)

    async def execute(self, task: dict[str, Any]) -> dict[str, Any]:
        """Try providers in order with per-tier retry before advancing.

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
                logger.debug("Skipping %s (circuit breaker open)", provider.name)
                continue

            tier_succeeded = False
            timeout = getattr(provider, "timeout_seconds", 30)

            for attempt in range(self._max_attempts):
                try:
                    result = await asyncio.wait_for(
                        provider.execute(task),
                        timeout=timeout,
                    )
                    if result.get("content"):
                        breaker.record_success()
                        tier_succeeded = True
                        return result
                    raise ValueError("Provider returned empty content")

                except asyncio.CancelledError:
                    raise  # never swallow

                except Exception as e:
                    last_error = e
                    sanitized = _sanitize_error(str(e))
                    if attempt < self._max_attempts - 1:
                        backoff = 2**attempt  # 1s, 2s, 4s
                        logger.debug(
                            "Provider %s attempt %d/%d failed (%s), retrying in %ds",
                            provider.name,
                            attempt + 1,
                            self._max_attempts,
                            sanitized,
                            backoff,
                        )
                        await asyncio.sleep(backoff)
                    else:
                        logger.warning(
                            "Provider %s exhausted %d attempts: %s",
                            provider.name,
                            self._max_attempts,
                            sanitized,
                        )

            if not tier_succeeded:
                breaker.record_failure()  # counts once per tier-call

        sanitized_last = _sanitize_error(str(last_error)) if last_error else "unknown"
        raise AllProvidersExhaustedError(
            f"All {len(self._providers)} providers failed. Last: {sanitized_last}"
        ) from last_error
