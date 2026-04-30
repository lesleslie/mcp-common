import os
import pytest
from mcp_common.auth.decorator import require_auth
from mcp_common.auth.config import AuthConfig
from mcp_common.auth.core import create_service_token
from mcp_common.auth.permissions import Permission
from mcp_common.auth.exceptions import InsufficientPermissionError

SECRET = "decorator-test-secret-that-is-long-enough-ab"


@pytest.fixture
def config(monkeypatch):
    monkeypatch.setenv("DEC_TEST_SECRET", SECRET)
    return AuthConfig(service_name="test-service", secret_env_var="DEC_TEST_SECRET")


@pytest.fixture
def read_token():
    return create_service_token(
        secret=SECRET,
        issuer="mahavishnu",
        audience="test-service",
        permissions=[Permission.READ],
    )


@pytest.fixture
def write_token():
    return create_service_token(
        secret=SECRET,
        issuer="mahavishnu",
        audience="test-service",
        permissions=[Permission.READ, Permission.WRITE],
    )


@pytest.mark.asyncio
async def test_passes_when_auth_disabled(monkeypatch):
    monkeypatch.delenv("BODAI_SHARED_SECRET", raising=False)
    monkeypatch.delenv("DEC_DISABLED_SECRET", raising=False)
    disabled_cfg = AuthConfig(service_name="svc", secret_env_var="DEC_DISABLED_SECRET")

    @require_auth(Permission.WRITE, config=disabled_cfg)
    async def my_tool(**kwargs):
        return "ok"

    result = await my_tool()
    assert result == "ok"


@pytest.mark.asyncio
async def test_passes_with_sufficient_permission(config, write_token):
    @require_auth(Permission.WRITE, config=config, service_name="test-service")
    async def my_tool(**kwargs):
        return "ok"

    result = await my_tool(__auth_token__=write_token)
    assert result == "ok"


@pytest.mark.asyncio
async def test_raises_with_insufficient_permission(config, read_token):
    @require_auth(Permission.WRITE, config=config, service_name="test-service")
    async def my_tool(**kwargs):
        return "ok"

    with pytest.raises(InsufficientPermissionError):
        await my_tool(__auth_token__=read_token)


@pytest.mark.asyncio
async def test_defaults_to_read_permission(config, read_token):
    @require_auth(config=config, service_name="test-service")
    async def my_tool(**kwargs):
        return "ok"

    result = await my_tool(__auth_token__=read_token)
    assert result == "ok"


@pytest.mark.asyncio
async def test_denied_token_emits_audit_event(config, read_token):
    from mcp_common.auth.audit import AuditLogger

    received = []

    class CaptureSink:
        def emit(self, event):
            received.append(event)

    alog = AuditLogger()
    alog.register_sink(CaptureSink())

    @require_auth(Permission.WRITE, config=config, service_name="test-service", audit_logger=alog)
    async def my_tool(**kwargs):
        return "ok"

    with pytest.raises(InsufficientPermissionError):
        await my_tool(__auth_token__=read_token)

    assert len(received) == 1
    assert received[0].result == "denied"
    assert received[0].permission == Permission.WRITE
