from __future__ import annotations

import logging
import os
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr, model_validator

from mcp_common.auth.exceptions import SecretNotConfiguredError
from mcp_common.auth.identity import IdentityProviderSpec

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


class IdentityProviderConfig(BaseModel):
    """Configuration for a single identity provider (Task 8b).

    M-2 fix: ``type`` is ``Literal["jwt", "oauth"]`` (not ``str``) so a typo
    like ``"OAUTH"`` is rejected at config-parse time rather than failing
    the first auth request.
    """

    name: str
    type: Literal["jwt", "oauth"]
    client_id: str | None = None
    client_secret: SecretStr | None = None
    oauth_token_url: str | None = None
    jwks_url: str | None = None
    audience: str | None = None
    jwks_cache_seconds: int = 3600
    timeout_seconds: float = 5.0

    model_config = ConfigDict(arbitrary_types_allowed=True)


class AuthConfig(BaseModel):
    """Authentication configuration for an MCP service.

    Task 8a: Converted from plain Python class to Pydantic v2 ``BaseModel``.
    Preserves env-var loading (``secret_env_var`` / ``BODAI_SHARED_SECRET``),
    placeholder rejection, and 32-char minimum length. The new ``secret``
    parameter accepts a direct value (alternative to env-var lookup).

    Task 8b: Added ``trusted_issuers`` (now ``list[str]``), ``default_provider``,
    and ``allow_anonymous_paths`` (defaults to ``["/health", "/readyz"]``).
    """

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid")

    service_name: str
    secret_env_var: str | None = None
    resolved_secret: str | None = Field(default=None, alias="secret")
    enabled: bool | None = None
    default_provider: str | None = None
    trusted_issuers: list[str] = Field(default_factory=list)
    identity_providers: dict[str, IdentityProviderSpec] | None = None
    allow_anonymous_paths: list[str] = Field(
        default_factory=lambda: ["/health", "/readyz"]
    )

    @model_validator(mode="before")
    @classmethod
    def _resolve_secret(cls, data: Any) -> Any:
        """Resolve and validate the secret at init time.

        Resolution order:
        1. Explicit ``secret=`` parameter (direct value).
        2. ``secret_env_var=`` + env lookup (with ``BODAI_SHARED_SECRET`` fallback).
        3. ``{SERVICE_NAME}_SECRET`` env var + ``BODAI_SHARED_SECRET`` fallback.

        On success, stores the resolved secret in ``resolved_secret`` and
        derives ``enabled`` from secret presence when ``enabled`` was not
        explicitly provided.
        """
        if not isinstance(data, dict):
            return data

        secret_env_var = data.get("secret_env_var")
        explicit_secret = data.get("secret")
        service_name = data.get("service_name", "")
        resolved: str | None = None

        if explicit_secret is not None:
            resolved = str(explicit_secret)
        elif secret_env_var is not None:
            raw = os.environ.get(secret_env_var) or os.environ.get("BODAI_SHARED_SECRET")
            if raw is not None:
                if raw == os.environ.get("BODAI_SHARED_SECRET"):
                    logger.warning(
                        "Service %r is using the shared dev secret (BODAI_SHARED_SECRET). "
                        "Set %s for production.",
                        service_name,
                        secret_env_var,
                    )
                resolved = raw
        else:
            raw = (
                os.environ.get(f"{str(service_name).upper()}_SECRET")
                or os.environ.get("BODAI_SHARED_SECRET")
            )
            if raw is not None:
                if raw == os.environ.get("BODAI_SHARED_SECRET"):
                    logger.warning(
                        "Service %r is using the shared dev secret (BODAI_SHARED_SECRET).",
                        service_name,
                    )
                resolved = raw

        if resolved is not None:
            if resolved.lower() in _PLACEHOLDER_SECRETS:
                raise ValueError(
                    f"Secret for {service_name!r} uses a known placeholder value {resolved!r}. "
                    "Generate a real secret with: python -c 'import secrets; print(secrets.token_urlsafe(48))'"
                )
            if len(resolved) < _MIN_SECRET_LENGTH:
                raise ValueError(
                    f"Secret for {service_name!r} is too short ({len(resolved)} chars). "
                    f"Minimum {_MIN_SECRET_LENGTH} characters required."
                )
            data["secret"] = resolved

        if data.get("enabled") is None:
            data["enabled"] = resolved is not None

        return data

    @property
    def secret(self) -> str:
        if self.resolved_secret is None:
            raise SecretNotConfiguredError(
                f"No secret configured for service {self.service_name!r}. "
                f"Set {self.secret_env_var} or BODAI_SHARED_SECRET."
            )
        return self.resolved_secret
