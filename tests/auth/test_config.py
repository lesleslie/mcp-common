import os
import pytest
from mcp_common.auth.config import AuthConfig, IdentityProviderConfig
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


def test_auth_config_is_pydantic_basemodel():
    """B8 fix: AuthConfig is now a Pydantic BaseModel (was plain class)."""
    config = AuthConfig(
        enabled=True,
        secret="x" * 40,
        service_name="test",
    )
    assert hasattr(config, "model_dump")  # Pydantic v2 marker


def test_auth_config_secret_min_length_validator():
    """I-6 fix: preserve the existing 32-char minimum secret length check."""
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        AuthConfig(enabled=True, secret="short", service_name="test")


def test_auth_config_rejects_placeholder_secrets():
    """I-6 fix: preserve placeholder secret rejection."""
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        AuthConfig(enabled=True, secret="changeme", service_name="test")


# --- Task 8b: trusted_issuers, identity_providers, default_provider, allow_anonymous_paths ---


def test_auth_config_has_trusted_issuers_field():
    config = AuthConfig(
        enabled=True,
        secret="x" * 40,
        service_name="test",
        trusted_issuers=["mahavishnu", "session-buddy"],
    )
    assert config.trusted_issuers == ["mahavishnu", "session-buddy"]


def test_auth_config_has_default_provider_field():
    config = AuthConfig(
        enabled=True,
        secret="x" * 40,
        service_name="test",
        default_provider="jwt",
    )
    assert config.default_provider == "jwt"


def test_auth_config_default_allow_anonymous_paths():
    config = AuthConfig(enabled=True, secret="x" * 40, service_name="test")
    assert "/health" in config.allow_anonymous_paths
    assert "/readyz" in config.allow_anonymous_paths


def test_identity_provider_config_basic():
    p = IdentityProviderConfig(name="anthropic", type="oauth", client_id="abc")
    assert p.name == "anthropic"
    assert p.type == "oauth"
    assert p.client_id == "abc"


def test_identity_provider_config_type_is_literal():
    """M-2 fix: type is Literal, not str (catches typos at config-parse time)."""
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        IdentityProviderConfig(name="bad", type="OAUTH")  # not in Literal["jwt", "oauth"]
