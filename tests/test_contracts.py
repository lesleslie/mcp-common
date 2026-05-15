from __future__ import annotations


def test_contract_facade_exports_canonical_primitives() -> None:
    from mcp_common.auth.core import create_service_token as auth_create_service_token
    from mcp_common.auth.core import verify_token as auth_verify_token
    from mcp_common.contracts import (
        FastMCPOpenTelemetryMiddleware,
        HealthStatus,
        TokenPayload,
        WebSocketProtocol,
        create_service_token,
        verify_token,
    )
    from mcp_common.health import HealthStatus as health_status
    from mcp_common.server.telemetry import (
        FastMCPOpenTelemetryMiddleware as telemetry_middleware,
    )
    from mcp_common.websocket.protocol import (
        WebSocketProtocol as websocket_protocol,
    )

    assert HealthStatus is health_status
    assert WebSocketProtocol is websocket_protocol
    assert FastMCPOpenTelemetryMiddleware is telemetry_middleware
    assert create_service_token is auth_create_service_token
    assert verify_token is auth_verify_token
    assert TokenPayload.__name__ == "TokenPayload"

