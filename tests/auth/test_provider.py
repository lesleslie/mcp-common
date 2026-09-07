from __future__ import annotations

from datetime import UTC, datetime

import pytest

from mcp_common.auth.provider import IdentityProvider, ProviderHealth


def test_provider_health_default_state_is_healthy():
    h = ProviderHealth(name="test-provider")
    assert h.state == "healthy"
    assert h.last_check_at is None
    assert h.last_error is None


def test_provider_health_records_error():
    h = ProviderHealth(
        name="test-provider",
        state="degraded",
        last_check_at=datetime.now(UTC),
        last_error="JWKS rotation timed out",
    )
    assert h.state == "degraded"
    assert h.last_error == "JWKS rotation timed out"


@pytest.mark.asyncio
async def test_identity_provider_protocol_runtime_checkable():
    """IdentityProvider is a Protocol; concrete impls must satisfy it."""
    class MockProvider:
        name = "mock"

        async def verify_token(self, token, *, expected_audience=None): ...
        async def health(self): ...

    # isinstance check works at runtime via Protocol
    assert isinstance(MockProvider(), IdentityProvider)


@pytest.mark.asyncio
async def test_identity_provider_missing_verify_token_not_satisfied():
    class IncompleteProvider:
        name = "incomplete"
        async def health(self): ...

    assert not isinstance(IncompleteProvider(), IdentityProvider)
