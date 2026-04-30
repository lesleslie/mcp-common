from __future__ import annotations

import logging
import os

from mcp_common.auth.exceptions import SecretNotConfiguredError

logger = logging.getLogger(__name__)

_PLACEHOLDER_SECRETS: frozenset[str] = frozenset({
    "changeme", "secret", "test", "test-secret", "change-me",
    "placeholder", "example", "none", "null",
})
_MIN_SECRET_LENGTH = 32


class AuthConfig:
    def __init__(self, *, service_name: str, secret_env_var: str) -> None:
        self._service_name = service_name
        self._secret_env_var = secret_env_var
        self._secret: str | None = self._load_secret()

    def _load_secret(self) -> str | None:
        raw = (
            os.environ.get(self._secret_env_var)
            or os.environ.get("BODAI_SHARED_SECRET")
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
        return self._secret is not None

    @property
    def service_name(self) -> str:
        return self._service_name

    @property
    def secret(self) -> str:
        if self._secret is None:
            raise SecretNotConfiguredError(
                f"No secret configured for service {self._service_name!r}. "
                f"Set {self._secret_env_var} or BODAI_SHARED_SECRET."
            )
        return self._secret
