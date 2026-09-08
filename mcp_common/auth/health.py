"""AuthHealth — wiring-discipline §3 four-signal feed observability for auth."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from mcp_common.auth.provider import IdentityProvider, ProviderHealth


@dataclass
class AuthHealth:
    """Aggregated health snapshot for the auth surface.

    Mirrors wiring-discipline §3 shape:
    - entities_count: verifications served
    - last_updated_timestamp: last cycle timestamp
    - errors_total: verification failures
    - cycles_total: provider-health polls

    Surfaced via /health envelope's components[] array.
    """

    providers: dict[str, ProviderHealth]
    verifications_total: int
    errors_total: int
    last_successful_verification_at: datetime | None
    last_updated_timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    cycles_total: int = 0

    @classmethod
    async def from_providers(
        cls,
        *,
        providers: dict[str, IdentityProvider],
        verifications_total: int,
        errors_total: int,
        last_successful_verification_at: datetime | None,
    ) -> AuthHealth:
        """Construct from live providers; runs health() on each in parallel."""
        import asyncio

        provider_healths = await asyncio.gather(
            *(p.health() for p in providers.values())
        )
        providers_dict = dict(zip(providers.keys(), provider_healths))
        return cls(
            providers=providers_dict,
            verifications_total=verifications_total,
            errors_total=errors_total,
            last_successful_verification_at=last_successful_verification_at,
            cycles_total=1,  # this constructor represents one poll cycle
        )

    def is_degraded(self) -> bool:
        """Return True if any provider is not healthy."""
        return any(p.state != "healthy" for p in self.providers.values())

    def as_components(
        self,
        *,
        include_diagnostics: bool = False,
    ) -> list[dict[str, Any]]:
        """Render for /health envelope's components[] array.

        Returns a single component dict representing the entire auth surface,
        not one dict per provider (the providers are nested under
        `providers` for drill-down).

        api-security R2-2 fix: `last_error` strings are operator diagnostics
        and may leak internal failure details (JWKS endpoint URLs, secrets,
        stack-trace substrings). They are included only when the caller
        explicitly opts in via `include_diagnostics=True`. The default
        (False) is what `/health` should call for anonymous responses —
        `/health` is in `allow_anonymous_paths`, so the default must not
        leak operator details.
        """
        return [
            {
                "name": "auth",
                "state": "degraded" if self.is_degraded() else "healthy",
                "entities_count": self.verifications_total,
                "errors_total": self.errors_total,
                "cycles_total": self.cycles_total,
                "last_updated_timestamp": self.last_updated_timestamp.isoformat(),
                "last_successful_verification_at": (
                    self.last_successful_verification_at.isoformat()
                    if self.last_successful_verification_at
                    else None
                ),
                "providers": {
                    name: {
                        "state": p.state,
                        "last_check_at": p.last_check_at.isoformat()
                        if p.last_check_at
                        else None,
                        # api-security R2-2 fix: redact last_error from
                        # anonymous responses. Operators can call
                        # `as_components(include_diagnostics=True)` from
                        # an authenticated debug path.
                        **({"last_error": p.last_error} if include_diagnostics else {}),
                    }
                    for name, p in self.providers.items()
                },
            }
        ]
