"""Additional branch-focused tests for mcp_common.llm."""

from __future__ import annotations

import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import SecretStr

from mcp_common.llm._security import sanitize_error
from mcp_common.llm.config import LLMSettings, ProviderConfig


class TestLLMSecuritySanitizer:
    @pytest.mark.parametrize(
        ("message", "expected"),
        [
            (
                "failed with sk-abcdefghijklmnopqrstuvwxyz1234",
                "failed with <redacted>",
            ),
            (
                "token=eyJhbGciOiJIUzI1NiJ9.abc123def456ghi789",
                "token=<redacted>",
            ),
            (
                "Authorization: Bearer abcdefghijklmnopqrstuvwxyz123456",
                "Authorization: <redacted>",
            ),
            (
                'payload="1234567890abcdef1234567890abcdef"',
                "payload=<redacted>",
            ),
        ],
    )
    def test_sanitize_error_redacts_secret_patterns(self, message: str, expected: str) -> None:
        assert sanitize_error(message) == expected


class TestProviderConfigLegacyTimeout:
    def test_timeout_seconds_syncs_from_legacy_timeout(self) -> None:
        config = ProviderConfig(timeout=45)
        assert config.timeout_seconds == 45


class TestLLMSettingsFallbackChainWarnings:
    def test_missing_fallback_chain_entry_is_skipped(self, caplog: pytest.LogCaptureFixture) -> None:
        settings = LLMSettings(
            providers={
                "available": {
                    "name": "available",
                    "enabled": True,
                    "base_url": "",
                    "api_key": "",
                    "require_auth": False,
                },
            },
            fallback_chain=["missing", "available"],
        )

        enabled = settings.get_enabled_providers()

        assert [provider.name for provider in enabled] == ["available"]
        assert "missing in fallback_chain not found in config" in caplog.text


def _mock_openai_module() -> MagicMock:
    module = MagicMock()
    module.AsyncOpenAI = MagicMock(return_value=MagicMock())
    return module


class TestOpenAICompatibleProviderNoAuth:
    def test_constructor_uses_no_auth_headers_when_auth_disabled(self) -> None:
        from mcp_common.llm.provider import OpenAICompatibleProvider

        config = ProviderConfig(
            name="ollama",
            base_url="http://localhost:11434/v1",
            require_auth=False,
        )
        mock_openai = _mock_openai_module()

        with patch.dict(sys.modules, {"openai": mock_openai}):
            provider = OpenAICompatibleProvider(config)

        assert provider.name == "ollama"
        mock_openai.AsyncOpenAI.assert_called_once_with(
            api_key="no-auth",
            base_url="http://localhost:11434/v1",
            default_headers={"Authorization": ""},
            max_retries=0,
            timeout=30,
        )


class TestHailuoAdapterAdditionalBranches:
    def test_constructor_raises_when_httpx_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from mcp_common.llm import hailuo

        monkeypatch.setattr(hailuo, "httpx", None)

        with pytest.raises(ImportError, match="httpx package required"):
            hailuo.HailuoAdapter(api_key="test-key")

    @pytest.mark.asyncio
    async def test_generate_wraps_submit_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from mcp_common.llm import hailuo
        from mcp_common.llm.exceptions import LLMError

        submit_error = RuntimeError("submit boom")
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=submit_error)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        adapter = hailuo.HailuoAdapter(api_key="test-key", poll_interval=0.01)

        with patch.object(hailuo.httpx, "AsyncClient", return_value=mock_client):
            with pytest.raises(LLMError, match="Hailuo submit failed"):
                await adapter.generate(prompt="a rocket launch")

    @pytest.mark.asyncio
    async def test_generate_wraps_poll_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from mcp_common.llm import hailuo
        from mcp_common.llm.exceptions import LLMError

        submit_resp = SimpleNamespace(
            json=lambda: {"task_id": "task-1", "base_resp": {"status_code": 0}},
            raise_for_status=lambda: None,
        )
        poll_error = RuntimeError("poll boom")

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=submit_resp)
        mock_client.get = AsyncMock(side_effect=poll_error)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        adapter = hailuo.HailuoAdapter(api_key="test-key", poll_interval=0.01)

        with patch.object(hailuo.httpx, "AsyncClient", return_value=mock_client):
            with pytest.raises(LLMError, match="Hailuo poll failed"):
                await adapter.generate(prompt="a rocket launch")
