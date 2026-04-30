import os
import pytest
from mcp_common.auth.config import AuthConfig
from mcp_common.auth.exceptions import SecretNotConfiguredError


def test_auth_disabled_when_no_secret(monkeypatch):
    monkeypatch.delenv("BODAI_SHARED_SECRET", raising=False)
    monkeypatch.delenv("TEST_SERVICE_SECRET", raising=False)
    cfg = AuthConfig(service_name="test-service", secret_env_var="TEST_SERVICE_SECRET")
    assert cfg.enabled is False


def test_auth_enabled_when_env_var_set(monkeypatch):
    monkeypatch.setenv("TEST_SERVICE_SECRET", "a" * 32)
    cfg = AuthConfig(service_name="test-service", secret_env_var="TEST_SERVICE_SECRET")
    assert cfg.enabled is True
    assert cfg.secret == "a" * 32


def test_shared_secret_fallback(monkeypatch):
    monkeypatch.delenv("TEST_SERVICE_SECRET", raising=False)
    monkeypatch.setenv("BODAI_SHARED_SECRET", "b" * 32)
    cfg = AuthConfig(service_name="test-service", secret_env_var="TEST_SERVICE_SECRET")
    assert cfg.enabled is True
    assert cfg.secret == "b" * 32


def test_rejects_secret_shorter_than_32(monkeypatch):
    monkeypatch.setenv("TEST_SERVICE_SECRET", "tooshort")
    with pytest.raises(ValueError, match="32"):
        AuthConfig(service_name="test-service", secret_env_var="TEST_SERVICE_SECRET")


def test_rejects_known_placeholder(monkeypatch):
    for placeholder in ("changeme", "secret", "test", "test-secret"):
        monkeypatch.setenv("TEST_SERVICE_SECRET", placeholder)
        with pytest.raises(ValueError, match="placeholder"):
            AuthConfig(service_name="test-service", secret_env_var="TEST_SERVICE_SECRET")


def test_get_secret_raises_when_disabled(monkeypatch):
    monkeypatch.delenv("BODAI_SHARED_SECRET", raising=False)
    monkeypatch.delenv("TEST_SERVICE_SECRET", raising=False)
    cfg = AuthConfig(service_name="test-service", secret_env_var="TEST_SERVICE_SECRET")
    with pytest.raises(SecretNotConfiguredError):
        _ = cfg.secret
