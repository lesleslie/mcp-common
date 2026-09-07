from __future__ import annotations

import logging
import os

from mcp_common.auth.exceptions import SecretNotConfiguredError

logger = logging.getLogger(__name__)

_PLACEHOLDER_SECRETS: frozenset[str] = frozenset(
    {
        "changeme",
        "secret",
        "test",
        "test-secret",
        "change-me",
        "placeholder",
        "example",
        "none",
        "null",
    }
)
_MIN_SECRET_LENGTH = 32


class AuthConfig:
    """Auth configuration for an MCP service.

    Path B / compat (Task 6 — Task 8a has not landed yet):
    - Existing callers: ``AuthConfig(service_name=..., secret_env_var=...)``.
      ``enabled`` is derived from secret presence (current behavior).
    - New callers: ``AuthConfig(enabled=True, service_name=..., default_provider=...)``.
      Explicit ``enabled`` overrides the secret-derivation; ``default_provider``
      and ``trusted_issuers`` are honored by ``BearerTokenMiddleware`` and
      ``validate_auth_config()`` (Task 7) once it lands.

    Both call shapes coexist; the existing constructor signature is preserved.
    """

    def __init__(
        self,
        *,
        service_name: str,
        secret_env_var: str | None = None,
        enabled: bool | None = None,
        default_provider: str | None = None,
        trusted_issuers: tuple[str, ...] = (),
    ) -> None:
        self._service_name = service_name
        self._secret_env_var = secret_env_var
        self._secret: str | None = (
            self._load_secret() if secret_env_var is not None else None
        )
        # ``enabled`` defaults to ``True`` for new explicit-shape callers and to
        # secret presence for legacy callers. When both ``secret_env_var`` and
        # ``enabled`` are supplied, ``enabled`` wins (explicit override).
        if enabled is None:
            self._enabled = self._secret is not None
        else:
            self._enabled = enabled
        self._default_provider = default_provider
        self._trusted_issuers: tuple[str, ...] = tuple(trusted_issuers)

    def _load_secret(self) -> str | None:
        raw = os.environ.get(self._secret_env_var or "") or os.environ.get(
            "BODAI_SHARED_SECRET"
        )
        if raw is None:
            return None
        if raw.lower() in _PLACEHOLDER_SECRETS:
            raise ValueError(
                f"Secret for {self._service_name!r} uses a known placeholder value {raw!r}. "
                "Generate a real secret with: python -c 'import secrets; print(secrets.token_urlsafe(48))'"
            )
        if len(raw) < _MIN_SECRET_LENGTH:
            raise ValueError(
                f"Secret for {self._service_name!r} is too short ({len(raw)} chars). "
                f"Minimum {_MIN_SECRET_LENGTH} characters required."
            )
        if raw == os.environ.get("BODAI_SHARED_SECRET"):
            logger.warning(
                "Service %r is using the shared dev secret (BODAI_SHARED_SECRET). "
                "Set %s for production.",
                self._service_name,
                self._secret_env_var,
            )
        return raw

    @property
    def enabled(self) -> bool:
        """Auth enforcement flag. False short-circuits middleware + decorator."""
        return self._enabled

    @property
    def service_name(self) -> str:
        return self._service_name

    @property
    def default_provider(self) -> str | None:
        """Preferred provider name for multi-provider deployments."""
        return self._default_provider

    @property
    def trusted_issuers(self) -> tuple[str, ...]:
        """Allow-list of issuer identifiers; empty tuple means default-deny."""
        return self._trusted_issuers

    @property
    def secret(self) -> str:
        if self._secret is None:
            raise SecretNotConfiguredError(
                f"No secret configured for service {self._service_name!r}. "
                f"Set {self._secret_env_var} or BODAI_SHARED_SECRET."
            )
        return self._secret
