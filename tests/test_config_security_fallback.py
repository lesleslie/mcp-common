import mcp_common.config.base as base_module
from mcp_common.config.base import MCPBaseSettings


class FallbackSettings(MCPBaseSettings):
    api_key: str | None = None


def test_validate_api_keys_fallback(monkeypatch) -> None:
    monkeypatch.setattr(base_module, "SECURITY_AVAILABLE", False)

    settings = FallbackSettings(api_key="  secret ")
    result = settings.validate_api_keys_at_startup()

    assert result == {"api_key": "secret"}


def test_get_masked_key_fallback(monkeypatch) -> None:
    monkeypatch.setattr(base_module, "SECURITY_AVAILABLE", False)

    settings = FallbackSettings(api_key="abcdef1234")

    assert settings.get_masked_key(visible_chars=4) == "...1234"
    assert settings.get_masked_key(visible_chars=20) == "***"


def test_validate_api_keys_fallback_skips_missing(monkeypatch) -> None:
    monkeypatch.setattr(base_module, "SECURITY_AVAILABLE", False)

    settings = FallbackSettings(api_key=None)
    result = settings.validate_api_keys_at_startup(key_fields=["missing_field"])

    assert result == {}


def test_validate_api_keys_fallback_skips_empty(monkeypatch) -> None:
    monkeypatch.setattr(base_module, "SECURITY_AVAILABLE", False)

    settings = FallbackSettings(api_key=None)
    result = settings.validate_api_keys_at_startup()

    assert result == {}


def test_validate_api_keys_fallback_validates_present_key(monkeypatch) -> None:
    monkeypatch.setattr(base_module, "SECURITY_AVAILABLE", False)

    settings = FallbackSettings(api_key="  key123456789012  ")
    result = settings.validate_api_keys_at_startup()

    assert result == {"api_key": "key123456789012"}
