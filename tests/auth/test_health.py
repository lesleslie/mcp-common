from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from mcp_common.auth.health import AuthHealth
from mcp_common.auth.provider import IdentityProvider, ProviderHealth


class MockProvider:
    def __init__(self, name: str, state: str = "healthy", error: str | None = None):
        self._name = name
        self._state = state
        self._error = error

    @property
    def name(self) -> str:
        return self._name

    async def verify_token(self, token, *, expected_audience=None):
        raise NotImplementedError

    async def health(self) -> ProviderHealth:
        return ProviderHealth(
            name=self._name,
            state=self._state,  # type: ignore[arg-type]
            last_check_at=datetime.now(UTC),
            last_error=self._error,
        )


@pytest.mark.asyncio
async def test_auth_health_aggregates_providers():
    providers = {
        "jwt": MockProvider("jwt", state="healthy"),
        "anthropic": MockProvider("anthropic", state="degraded", error="JWKS timeout"),
    }
    health = await AuthHealth.from_providers(
        providers=providers,
        verifications_total=42,
        errors_total=3,
        last_successful_verification_at=datetime.now(UTC) - timedelta(seconds=10),
    )
    assert health.providers["jwt"].state == "healthy"
    assert health.providers["anthropic"].state == "degraded"
    assert health.verifications_total == 42
    assert health.errors_total == 3
    assert health.cycles_total == 1  # one poll cycle just ran


def test_auth_health_as_components_returns_wiring_discipline_shape():
    health = AuthHealth(
        providers={"jwt": ProviderHealth(name="jwt", state="healthy")},
        verifications_total=10,
        errors_total=0,
        last_successful_verification_at=datetime.now(UTC),
        last_updated_timestamp=datetime.now(UTC),
        cycles_total=5,
    )
    components = health.as_components()
    assert len(components) == 1
    auth_component = components[0]
    assert auth_component["name"] == "auth"
    assert auth_component["entities_count"] == 10
    assert auth_component["errors_total"] == 0
    assert auth_component["cycles_total"] == 5
    assert "last_updated_timestamp" in auth_component


def test_auth_health_reports_degraded_when_any_provider_dead():
    health = AuthHealth(
        providers={
            "jwt": ProviderHealth(name="jwt", state="healthy"),
            "anthropic": ProviderHealth(name="anthropic", state="dead"),
        },
        verifications_total=10,
        errors_total=5,
        last_successful_verification_at=None,
        last_updated_timestamp=datetime.now(UTC),
        cycles_total=5,
    )
    assert health.is_degraded() is True
