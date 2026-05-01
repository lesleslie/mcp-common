"""Comprehensive tests for the mcp_common.llm module.

Covers exceptions, types, config (ProviderConfig, LLMSettings), provider
(OpenAICompatibleProvider), and fallback (CircuitBreaker, FallbackChain).
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import yaml
from pydantic import SecretStr, ValidationError

from mcp_common.llm.config import LLMSettings, ProviderConfig
from mcp_common.llm.exceptions import (
    AllProvidersExhaustedError,
    LLMError,
    ProviderUnavailableError,
)
from mcp_common.llm.fallback import CircuitBreaker
from mcp_common.llm.types import TaskType


# ---------------------------------------------------------------------------
# 1. Exceptions
# ---------------------------------------------------------------------------


class TestExceptions:
    """Tests for the LLM exception hierarchy."""

    def test_llm_error_is_base_exception(self) -> None:
        err = LLMError("something went wrong")
        assert isinstance(err, Exception)
        assert str(err) == "something went wrong"

    def test_llm_error_can_be_raised_and_caught(self) -> None:
        with pytest.raises(LLMError):
            raise LLMError("base error")

    def test_provider_unavailable_inherits_llm_error(self) -> None:
        err = ProviderUnavailableError("provider down")
        assert isinstance(err, LLMError)
        assert isinstance(err, Exception)
        assert str(err) == "provider down"

    def test_provider_unavailable_caught_as_llm_error(self) -> None:
        with pytest.raises(LLMError):
            raise ProviderUnavailableError("down")

    def test_all_providers_exhausted_inherits_llm_error(self) -> None:
        err = AllProvidersExhaustedError("all failed")
        assert isinstance(err, LLMError)
        assert isinstance(err, Exception)
        assert str(err) == "all failed"

    def test_all_providers_exhausted_caught_as_llm_error(self) -> None:
        with pytest.raises(LLMError):
            raise AllProvidersExhaustedError("exhausted")

    def test_exception_hierarchy_chain(self) -> None:
        """AllProvidersExhaustedError -> LLMError -> Exception."""
        causes = AllProvidersExhaustedError.__mro__
        assert LLMError in causes
        assert Exception in causes

    def test_provider_unavailable_different_from_exhausted(self) -> None:
        assert ProviderUnavailableError is not AllProvidersExhaustedError


# ---------------------------------------------------------------------------
# 2. TaskType StrEnum
# ---------------------------------------------------------------------------


class TestTaskType:
    """Tests for the TaskType StrEnum."""

    def test_all_expected_values_exist(self) -> None:
        expected = [
            "CODE_GENERATION",
            "CODE_REVIEW",
            "DEBUGGING",
            "REFACTORING",
            "TESTING",
            "REASONING",
            "DOCUMENTATION",
            "ANALYSIS",
            "GENERAL",
            "SWARM",
            "VISION",
            "QUICK",
            "EMBEDDING",
            "CREATIVE",
        ]
        for name in expected:
            assert hasattr(TaskType, name), f"Missing TaskType.{name}"

    def test_total_member_count(self) -> None:
        assert len(TaskType) == 14

    def test_str_values_match_snake_case(self) -> None:
        assert TaskType.CODE_GENERATION == "code_generation"
        assert TaskType.CODE_REVIEW == "code_review"
        assert TaskType.DEBUGGING == "debugging"
        assert TaskType.REFACTORING == "refactoring"
        assert TaskType.TESTING == "testing"
        assert TaskType.REASONING == "reasoning"
        assert TaskType.DOCUMENTATION == "documentation"
        assert TaskType.ANALYSIS == "analysis"
        assert TaskType.GENERAL == "general"
        assert TaskType.SWARM == "swarm"
        assert TaskType.VISION == "vision"
        assert TaskType.QUICK == "quick"
        assert TaskType.EMBEDDING == "embedding"
        assert TaskType.CREATIVE == "creative"

    def test_is_str_enum(self) -> None:
        """TaskType values are directly comparable to strings."""
        assert TaskType.CODE_GENERATION == "code_generation"
        assert isinstance(TaskType.CODE_GENERATION, str)

    def test_iteration(self) -> None:
        members = list(TaskType)
        assert len(members) == 14
        assert TaskType.GENERAL in members

    def test_from_string(self) -> None:
        task = TaskType("code_generation")
        assert task is TaskType.CODE_GENERATION

    def test_invalid_value_raises(self) -> None:
        with pytest.raises(ValueError):
            TaskType("nonexistent_task")


# ---------------------------------------------------------------------------
# 3. ProviderConfig
# ---------------------------------------------------------------------------


class TestProviderConfig:
    """Tests for ProviderConfig Pydantic model."""

    def test_defaults(self) -> None:
        config = ProviderConfig()
        assert config.name == ""
        assert config.enabled is True
        assert config.base_url == ""
        assert config.api_key == SecretStr("")
        assert config.models == {}
        assert config.priority == 1
        assert config.timeout == 30
        assert config.max_retries == 2
        assert config.task_routing == {}
        assert config.fallback == {}

    def test_explicit_values(self) -> None:
        config = ProviderConfig(
            name="zai",
            enabled=True,
            base_url="https://api.z.ai/v4",
            api_key=SecretStr("sk-test"),
            models={"glm-4.7": "glm-4.7"},
            priority=1,
            timeout=60,
            max_retries=3,
            task_routing={"code_generation": "glm-4.7"},
            fallback={"reasoning": "ollama"},
        )
        assert config.name == "zai"
        assert config.enabled is True
        assert config.base_url == "https://api.z.ai/v4"
        assert config.api_key.get_secret_value() == "sk-test"
        assert config.models == {"glm-4.7": "glm-4.7"}
        assert config.priority == 1
        assert config.timeout == 60
        assert config.max_retries == 3
        assert config.task_routing == {"code_generation": "glm-4.7"}
        assert config.fallback == {"reasoning": "ollama"}

    def test_extra_fields_forbidden(self) -> None:
        with pytest.raises(ValidationError):
            ProviderConfig(name="zai", unknown_field="oops")

    def test_get_model_for_task_found(self) -> None:
        config = ProviderConfig(
            name="zai",
            task_routing={"code_generation": "glm-4.7", "reasoning": "glm-5.1"},
        )
        assert config.get_model_for_task("code_generation") == "glm-4.7"
        assert config.get_model_for_task("reasoning") == "glm-5.1"

    def test_get_model_for_task_missing(self) -> None:
        config = ProviderConfig(name="zai")
        assert config.get_model_for_task("nonexistent") is None

    def test_get_model_for_task_empty_routing(self) -> None:
        config = ProviderConfig(name="zai", task_routing={})
        assert config.get_model_for_task("code_generation") is None

    def test_resolve_env_vars_base_url(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("LLM_BASE_URL", "https://resolved.example.com")
        config = ProviderConfig(base_url="${LLM_BASE_URL}")
        assert config.base_url == "https://resolved.example.com"

    def test_resolve_env_vars_api_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("LLM_API_KEY", "sk-resolved-key")
        config = ProviderConfig(api_key=SecretStr("${LLM_API_KEY}"))
        assert config.api_key.get_secret_value() == "sk-resolved-key"

    def test_resolve_env_vars_both(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("MY_URL", "https://api.test.com")
        monkeypatch.setenv("MY_KEY", "key-123")
        config = ProviderConfig(
            base_url="${MY_URL}",
            api_key=SecretStr("${MY_KEY}"),
        )
        assert config.base_url == "https://api.test.com"
        assert config.api_key.get_secret_value() == "key-123"

    def test_resolve_env_vars_unset_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """When the env var is not set, the raw ${VAR} pattern is preserved."""
        monkeypatch.delenv("NONEXISTENT_VAR", raising=False)
        config = ProviderConfig(base_url="${NONEXISTENT_VAR}")
        # Env var not set, so base_url stays as the raw pattern
        assert config.base_url == "${NONEXISTENT_VAR}"

    def test_resolve_env_vars_non_pattern_untouched(self) -> None:
        """Non-${...} values are left alone."""
        config = ProviderConfig(
            base_url="https://plain.url.com",
            api_key=SecretStr("plain-key"),
        )
        assert config.base_url == "https://plain.url.com"
        assert config.api_key.get_secret_value() == "plain-key"

    def test_resolve_env_vars_partial_match(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Only exact ${VAR} patterns (entire field) are resolved."""
        monkeypatch.setenv("PREFIX", "https://prefix")
        config = ProviderConfig(base_url="https://api.com/${PREFIX}")
        # The field does not start with ${ and end with }, so it is not resolved
        assert config.base_url == "https://api.com/${PREFIX}"

    def test_secret_str_repr_does_not_leak(self) -> None:
        config = ProviderConfig(api_key=SecretStr("super-secret"))
        assert "super-secret" not in repr(config.api_key)


# ---------------------------------------------------------------------------
# 4. LLMSettings
# ---------------------------------------------------------------------------


class TestLLMSettings:
    """Tests for LLMSettings."""

    def test_defaults(self) -> None:
        settings = LLMSettings()
        assert settings.providers == {}
        assert settings.default_provider == "zai"
        assert settings.fallback_chain == ["zai", "ollama"]
        assert settings.free_tier_provider == "zai-free"

    def test_extra_fields_forbidden(self) -> None:
        with pytest.raises(ValidationError):
            LLMSettings(unknown="value")

    def test_from_yaml_nonexistent_path(self, tmp_path: Path) -> None:
        settings = LLMSettings.from_yaml(tmp_path / "nonexistent.yaml")
        assert settings.providers == {}
        assert settings.default_provider == "zai"

    def test_from_yaml_empty_file(self, tmp_path: Path) -> None:
        path = tmp_path / "empty.yaml"
        path.write_text("")
        settings = LLMSettings.from_yaml(path)
        assert settings.providers == {}

    def test_from_yaml_with_providers(self, tmp_path: Path) -> None:
        content = {
            "default_provider": "zai",
            "fallback_chain": ["zai", "ollama"],
            "free_tier_provider": "zai-free",
            "zai": {
                "enabled": True,
                "base_url": "https://api.z.ai/v4",
                "api_key": "sk-test",
                "models": {"glm-4.7": "glm-4.7"},
                "priority": 1,
                "timeout": 30,
                "max_retries": 2,
                "task_routing": {"code_generation": "glm-4.7"},
            },
            "ollama": {
                "enabled": True,
                "base_url": "http://localhost:11434",
                "api_key": "",
                "priority": 2,
            },
        }
        path = tmp_path / "models.yaml"
        path.write_text(yaml.dump(content))

        settings = LLMSettings.from_yaml(path)
        assert settings.default_provider == "zai"
        assert settings.fallback_chain == ["zai", "ollama"]
        assert settings.free_tier_provider == "zai-free"
        assert "zai" in settings.providers
        assert "ollama" in settings.providers

    def test_from_yaml_strips_comments(self, tmp_path: Path) -> None:
        """Keys starting with '#' are skipped."""
        content = {
            "# This is a comment": {"ignored": True},
            "zai": {"enabled": True},
        }
        path = tmp_path / "commented.yaml"
        path.write_text(yaml.dump(content))

        settings = LLMSettings.from_yaml(path)
        assert "# This is a comment" not in settings.providers
        assert "zai" in settings.providers

    def test_from_yaml_non_dict_values_skipped(self, tmp_path: Path) -> None:
        """Top-level non-dict values (except reserved keys) are skipped."""
        content = {
            "default_provider": "zai",
            "some_string_value": "hello",
            "some_int_value": 42,
            "zai": {"enabled": True},
        }
        path = tmp_path / "mixed.yaml"
        path.write_text(yaml.dump(content))

        settings = LLMSettings.from_yaml(path)
        assert "some_string_value" not in settings.providers
        assert "some_int_value" not in settings.providers
        assert "zai" in settings.providers

    def test_from_yaml_provider_name_injected(self, tmp_path: Path) -> None:
        """The provider dict key is injected as the 'name' field."""
        content = {"my_provider": {"enabled": True, "priority": 5}}
        path = tmp_path / "name_inject.yaml"
        path.write_text(yaml.dump(content))

        settings = LLMSettings.from_yaml(path)
        assert settings.providers["my_provider"]["name"] == "my_provider"

    def test_get_provider_found(self, tmp_path: Path) -> None:
        content = {
            "zai": {
                "enabled": True,
                "base_url": "https://api.z.ai/v4",
                "api_key": "sk-test",
                "priority": 1,
            },
        }
        path = tmp_path / "models.yaml"
        path.write_text(yaml.dump(content))
        settings = LLMSettings.from_yaml(path)

        provider = settings.get_provider("zai")
        assert provider is not None
        assert provider.name == "zai"
        assert provider.enabled is True
        assert provider.base_url == "https://api.z.ai/v4"

    def test_get_provider_not_found(self) -> None:
        settings = LLMSettings()
        assert settings.get_provider("nonexistent") is None

    def test_get_provider_disabled_returns_none(self, tmp_path: Path) -> None:
        content = {
            "disabled_provider": {
                "enabled": False,
                "base_url": "https://example.com",
                "api_key": "",
            },
        }
        path = tmp_path / "disabled.yaml"
        path.write_text(yaml.dump(content))
        settings = LLMSettings.from_yaml(path)

        assert settings.get_provider("disabled_provider") is None

    def test_get_enabled_providers_follows_fallback_chain_order(
        self, tmp_path: Path
    ) -> None:
        content = {
            "fallback_chain": ["ollama", "zai"],
            "zai": {"enabled": True, "priority": 1, "base_url": "", "api_key": ""},
            "ollama": {"enabled": True, "priority": 2, "base_url": "", "api_key": ""},
            "unlisted": {"enabled": True, "priority": 0, "base_url": "", "api_key": ""},
        }
        path = tmp_path / "ordering.yaml"
        path.write_text(yaml.dump(content))
        settings = LLMSettings.from_yaml(path)

        enabled = settings.get_enabled_providers()
        names = [p.name for p in enabled]
        # Providers not in fallback_chain are excluded
        assert "unlisted" not in names
        # All providers in fallback_chain are included
        assert set(names) == {"zai", "ollama"}

    def test_get_enabled_providers_sorted_by_priority(self, tmp_path: Path) -> None:
        content = {
            "fallback_chain": ["low", "high", "mid"],
            "low": {"enabled": True, "priority": 10, "base_url": "", "api_key": ""},
            "high": {"enabled": True, "priority": 1, "base_url": "", "api_key": ""},
            "mid": {"enabled": True, "priority": 5, "base_url": "", "api_key": ""},
        }
        path = tmp_path / "priority.yaml"
        path.write_text(yaml.dump(content))
        settings = LLMSettings.from_yaml(path)

        enabled = settings.get_enabled_providers()
        priorities = [p.priority for p in enabled]
        assert priorities == [1, 5, 10]
        assert enabled[0].name == "high"

    def test_get_enabled_providers_excludes_disabled(self, tmp_path: Path) -> None:
        content = {
            "fallback_chain": ["active", "disabled"],
            "active": {"enabled": True, "priority": 1, "base_url": "", "api_key": ""},
            "disabled": {"enabled": False, "priority": 0, "base_url": "", "api_key": ""},
        }
        path = tmp_path / "excludes_disabled.yaml"
        path.write_text(yaml.dump(content))
        settings = LLMSettings.from_yaml(path)

        enabled = settings.get_enabled_providers()
        names = [p.name for p in enabled]
        assert names == ["active"]


# ---------------------------------------------------------------------------
# 5. OpenAICompatibleProvider
#
# We mock the openai import at the sys.modules level. Instead of using
# importlib.reload (which breaks pytest-asyncio auto detection), we
# construct the provider class inline after patching sys.modules.
# ---------------------------------------------------------------------------


def _build_provider_with_mock_openai(
    config: ProviderConfig,
    mock_openai: MagicMock,
) -> Any:
    """Build an OpenAICompatibleProvider with a mocked openai module.

    This avoids importlib.reload which breaks pytest-asyncio's coroutine
    detection. Instead, we patch sys.modules and re-import the class.
    """
    with patch.dict("sys.modules", {"openai": mock_openai}):
        # Remove cached module references so the import picks up the mock
        import sys

        for mod_key in list(sys.modules.keys()):
            if mod_key == "mcp_common.llm.provider" or mod_key.startswith(
                "mcp_common.llm.provider."
            ):
                del sys.modules[mod_key]

        from mcp_common.llm.provider import OpenAICompatibleProvider

        return OpenAICompatibleProvider(config)


class TestOpenAICompatibleProvider:
    """Tests for OpenAICompatibleProvider with mocked openai import."""

    @pytest.fixture
    def mock_openai_module(self) -> MagicMock:
        """Provide a mocked openai module."""
        mock_module = MagicMock()
        mock_async_client = MagicMock()
        mock_module.AsyncOpenAI = MagicMock(return_value=mock_async_client)
        mock_module._async_client = mock_async_client
        return mock_module

    def test_constructor_raises_import_error_without_openai(self) -> None:
        """If openai is not importable, constructor raises ImportError."""
        config = ProviderConfig(
            name="test",
            base_url="https://api.test.com",
            api_key=SecretStr("sk-test"),
        )
        # Use None to simulate openai not being installed
        with pytest.raises(ImportError, match="openai package required"):
            _build_provider_with_mock_openai(config, None)  # type: ignore[arg-type]

    def test_constructor_creates_client(self, mock_openai_module: MagicMock) -> None:
        """Constructor initializes AsyncOpenAI with correct params."""
        config = ProviderConfig(
            name="zai",
            base_url="https://api.z.ai/v4",
            api_key=SecretStr("sk-test"),
            max_retries=3,
            timeout=60,
        )
        provider = _build_provider_with_mock_openai(config, mock_openai_module)
        assert provider.name == "zai"
        mock_openai_module.AsyncOpenAI.assert_called_once_with(
            api_key="sk-test",
            base_url="https://api.z.ai/v4",
            max_retries=3,
            timeout=60,
        )

    @pytest.mark.asyncio
    async def test_execute_success(self, mock_openai_module: MagicMock) -> None:
        """execute returns content, provider, model, and usage on success."""
        mock_message = MagicMock()
        mock_message.content = "Hello, world!"
        mock_choice = MagicMock()
        mock_choice.message = mock_message
        mock_usage = MagicMock()
        mock_usage.model_dump.return_value = {"total_tokens": 42}
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.usage = mock_usage

        mock_client = mock_openai_module._async_client
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        config = ProviderConfig(
            name="zai",
            base_url="https://api.z.ai/v4",
            api_key=SecretStr("sk-test"),
        )
        provider = _build_provider_with_mock_openai(config, mock_openai_module)
        result = await provider.execute(
            {
                "model": "glm-4.7",
                "messages": [{"role": "user", "content": "Hi"}],
            }
        )
        assert result["content"] == "Hello, world!"
        assert result["provider"] == "zai"
        assert result["model"] == "glm-4.7"
        assert result["usage"] == {"total_tokens": 42}

    @pytest.mark.asyncio
    async def test_execute_passes_optional_params(
        self, mock_openai_module: MagicMock
    ) -> None:
        """execute forwards max_tokens and temperature to the API."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="ok"))]
        mock_response.usage = None

        mock_client = mock_openai_module._async_client
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        config = ProviderConfig(
            name="zai", base_url="https://api.z.ai/v4", api_key=SecretStr("sk-test")
        )
        provider = _build_provider_with_mock_openai(config, mock_openai_module)
        await provider.execute(
            {
                "model": "glm-4.7",
                "messages": [{"role": "user", "content": "Hi"}],
                "max_tokens": 1024,
                "temperature": 0.5,
            }
        )
        mock_client.chat.completions.create.assert_called_once_with(
            model="glm-4.7",
            messages=[{"role": "user", "content": "Hi"}],
            max_tokens=1024,
            temperature=0.5,
        )

    @pytest.mark.asyncio
    async def test_execute_defaults_for_optional_params(
        self, mock_openai_module: MagicMock
    ) -> None:
        """execute uses default max_tokens=4096 and temperature=0.7."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="ok"))]
        mock_response.usage = None

        mock_client = mock_openai_module._async_client
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        config = ProviderConfig(
            name="zai", base_url="https://api.z.ai/v4", api_key=SecretStr("sk-test")
        )
        provider = _build_provider_with_mock_openai(config, mock_openai_module)
        await provider.execute(
            {
                "model": "glm-4.7",
                "messages": [{"role": "user", "content": "Hi"}],
            }
        )
        _, kwargs = mock_client.chat.completions.create.call_args
        assert kwargs["max_tokens"] == 4096
        assert kwargs["temperature"] == 0.7

    @pytest.mark.asyncio
    async def test_execute_wraps_errors_as_llm_error(
        self, mock_openai_module: MagicMock
    ) -> None:
        """execute wraps any exception in LLMError."""
        mock_client = mock_openai_module._async_client
        mock_client.chat.completions.create = AsyncMock(
            side_effect=RuntimeError("API timeout")
        )

        config = ProviderConfig(
            name="zai", base_url="https://api.z.ai/v4", api_key=SecretStr("sk-test")
        )
        provider = _build_provider_with_mock_openai(config, mock_openai_module)
        with pytest.raises(LLMError, match="Provider zai failed"):
            await provider.execute(
                {
                    "model": "glm-4.7",
                    "messages": [{"role": "user", "content": "Hi"}],
                }
            )

    @pytest.mark.asyncio
    async def test_execute_wraps_llm_error_itself(
        self, mock_openai_module: MagicMock
    ) -> None:
        """If the underlying API raises LLMError, it is re-wrapped."""
        mock_client = mock_openai_module._async_client
        mock_client.chat.completions.create = AsyncMock(
            side_effect=LLMError("inner LLM error")
        )

        config = ProviderConfig(
            name="zai", base_url="https://api.z.ai/v4", api_key=SecretStr("sk-test")
        )
        provider = _build_provider_with_mock_openai(config, mock_openai_module)
        with pytest.raises(LLMError, match="Provider zai failed"):
            await provider.execute(
                {
                    "model": "glm-4.7",
                    "messages": [{"role": "user", "content": "Hi"}],
                }
            )

    @pytest.mark.asyncio
    async def test_health_check_success(self, mock_openai_module: MagicMock) -> None:
        """health_check returns True when models.list succeeds."""
        mock_client = mock_openai_module._async_client
        mock_client.models.list = AsyncMock(return_value=MagicMock())

        config = ProviderConfig(
            name="zai", base_url="https://api.z.ai/v4", api_key=SecretStr("sk-test")
        )
        provider = _build_provider_with_mock_openai(config, mock_openai_module)
        assert await provider.health_check() is True

    @pytest.mark.asyncio
    async def test_health_check_failure(self, mock_openai_module: MagicMock) -> None:
        """health_check returns False when models.list raises."""
        mock_client = mock_openai_module._async_client
        mock_client.models.list = AsyncMock(
            side_effect=ConnectionError("unreachable")
        )

        config = ProviderConfig(
            name="zai", base_url="https://api.z.ai/v4", api_key=SecretStr("sk-test")
        )
        provider = _build_provider_with_mock_openai(config, mock_openai_module)
        assert await provider.health_check() is False

    @pytest.mark.asyncio
    async def test_execute_handles_null_usage(
        self, mock_openai_module: MagicMock
    ) -> None:
        """execute returns empty usage dict when response.usage is None."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="text"))]
        mock_response.usage = None

        mock_client = mock_openai_module._async_client
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        config = ProviderConfig(
            name="zai", base_url="https://api.z.ai/v4", api_key=SecretStr("sk-test")
        )
        provider = _build_provider_with_mock_openai(config, mock_openai_module)
        result = await provider.execute(
            {
                "model": "glm-4.7",
                "messages": [{"role": "user", "content": "Hi"}],
            }
        )
        assert result["usage"] == {}


# ---------------------------------------------------------------------------
# 6. CircuitBreaker
# ---------------------------------------------------------------------------


class TestCircuitBreaker:
    """Tests for CircuitBreaker."""

    def test_is_closed_by_default(self) -> None:
        cb = CircuitBreaker()
        assert cb.is_open is False

    def test_stays_closed_below_threshold(self) -> None:
        cb = CircuitBreaker(failure_threshold=5)
        for _ in range(4):
            cb.record_failure()
        assert cb.is_open is False

    def test_opens_at_threshold(self) -> None:
        cb = CircuitBreaker(failure_threshold=3)
        for _ in range(3):
            cb.record_failure()
        assert cb.is_open is True

    def test_opens_above_threshold(self) -> None:
        cb = CircuitBreaker(failure_threshold=2)
        for _ in range(10):
            cb.record_failure()
        assert cb.is_open is True

    def test_resets_after_success(self) -> None:
        cb = CircuitBreaker(failure_threshold=3)
        for _ in range(2):
            cb.record_failure()
        assert cb.is_open is False
        cb.record_success()
        assert cb._failure_count == 0

    def test_success_resets_open_breaker(self) -> None:
        cb = CircuitBreaker(failure_threshold=2, reset_timeout=60.0)
        cb.record_failure()
        cb.record_failure()
        assert cb.is_open is True
        cb.record_success()
        assert cb.is_open is False

    def test_half_open_after_timeout(self) -> None:
        cb = CircuitBreaker(failure_threshold=2, reset_timeout=0.1)
        cb.record_failure()
        cb.record_failure()
        assert cb.is_open is True
        time.sleep(0.15)
        # After reset_timeout, breaker should be half-open (is_open=False)
        assert cb.is_open is False

    def test_reopens_after_half_open_failure(self) -> None:
        cb = CircuitBreaker(failure_threshold=2, reset_timeout=0.1)
        cb.record_failure()
        cb.record_failure()
        assert cb.is_open is True
        time.sleep(0.15)
        assert cb.is_open is False  # half-open
        # A single failure in half-open should re-open (count goes to 3 >= 2)
        cb.record_failure()
        assert cb.is_open is True

    def test_custom_failure_threshold(self) -> None:
        cb = CircuitBreaker(failure_threshold=10)
        for _ in range(9):
            cb.record_failure()
        assert cb.is_open is False
        cb.record_failure()
        assert cb.is_open is True

    def test_custom_reset_timeout(self) -> None:
        cb = CircuitBreaker(failure_threshold=1, reset_timeout=1.0)
        cb.record_failure()
        assert cb.is_open is True
        # Immediately: still open
        assert cb.is_open is True
        time.sleep(1.05)
        assert cb.is_open is False


# ---------------------------------------------------------------------------
# 7. FallbackChain
# ---------------------------------------------------------------------------


def _make_mock_provider(
    name: str,
    *,
    succeed: bool = True,
    return_value: dict[str, Any] | None = None,
    error: Exception | None = None,
) -> MagicMock:
    """Create a mock OpenAICompatibleProvider."""
    provider = MagicMock()
    provider.name = name
    if succeed:
        provider.execute = AsyncMock(
            return_value=return_value
            or {
                "content": f"response from {name}",
                "provider": name,
                "model": "test-model",
                "usage": {},
            }
        )
    else:
        provider.execute = AsyncMock(
            side_effect=error or LLMError(f"{name} failed")
        )
    return provider


class TestFallbackChain:
    """Tests for FallbackChain."""

    @pytest.mark.asyncio
    async def test_execute_returns_first_provider_result(self) -> None:
        from mcp_common.llm.fallback import FallbackChain

        p1 = _make_mock_provider("primary")
        p2 = _make_mock_provider("secondary")
        chain = FallbackChain([p1, p2])

        result = await chain.execute({"model": "m", "messages": []})
        assert result["provider"] == "primary"
        p1.execute.assert_awaited_once()
        p2.execute.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_execute_falls_back_on_failure(self) -> None:
        from mcp_common.llm.fallback import FallbackChain

        p1 = _make_mock_provider("primary", succeed=False)
        p2 = _make_mock_provider("secondary")
        chain = FallbackChain([p1, p2])

        result = await chain.execute({"model": "m", "messages": []})
        assert result["provider"] == "secondary"
        p1.execute.assert_awaited_once()
        p2.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_execute_skips_open_circuit_breaker(self) -> None:
        from mcp_common.llm.fallback import FallbackChain

        p1 = _make_mock_provider("primary", succeed=False)
        p2 = _make_mock_provider("secondary")
        chain = FallbackChain([p1, p2])

        # Trip the breaker for p1
        for _ in range(5):
            chain._circuit_breakers["primary"].record_failure()

        result = await chain.execute({"model": "m", "messages": []})
        assert result["provider"] == "secondary"
        p1.execute.assert_not_awaited()
        p2.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_execute_raises_all_providers_exhausted(self) -> None:
        from mcp_common.llm.fallback import FallbackChain

        p1 = _make_mock_provider("primary", succeed=False)
        p2 = _make_mock_provider("secondary", succeed=False)
        chain = FallbackChain([p1, p2])

        with pytest.raises(AllProvidersExhaustedError, match="All 2 providers failed"):
            await chain.execute({"model": "m", "messages": []})

    @pytest.mark.asyncio
    async def test_execute_records_success_on_breaker(self) -> None:
        from mcp_common.llm.fallback import FallbackChain

        p1 = _make_mock_provider("primary")
        chain = FallbackChain([p1])

        await chain.execute({"model": "m", "messages": []})
        breaker = chain._circuit_breakers["primary"]
        assert breaker._failure_count == 0

    @pytest.mark.asyncio
    async def test_execute_records_failure_on_breaker(self) -> None:
        from mcp_common.llm.fallback import FallbackChain

        p1 = _make_mock_provider("primary", succeed=False)
        p2 = _make_mock_provider("secondary")
        chain = FallbackChain([p1, p2])

        await chain.execute({"model": "m", "messages": []})
        assert chain._circuit_breakers["primary"]._failure_count == 1
        assert chain._circuit_breakers["secondary"]._failure_count == 0

    @pytest.mark.asyncio
    async def test_execute_all_open_raises(self) -> None:
        from mcp_common.llm.fallback import FallbackChain

        p1 = _make_mock_provider("p1")
        p2 = _make_mock_provider("p2")
        chain = FallbackChain([p1, p2])

        # Trip both breakers
        for _ in range(5):
            chain._circuit_breakers["p1"].record_failure()
            chain._circuit_breakers["p2"].record_failure()

        with pytest.raises(AllProvidersExhaustedError):
            await chain.execute({"model": "m", "messages": []})
        p1.execute.assert_not_awaited()
        p2.execute.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_execute_preserves_chain_of_cause(self) -> None:
        from mcp_common.llm.fallback import FallbackChain

        p1 = _make_mock_provider("p1", succeed=False, error=ValueError("boom"))
        chain = FallbackChain([p1])

        with pytest.raises(AllProvidersExhaustedError) as exc_info:
            await chain.execute({"model": "m", "messages": []})

        assert exc_info.value.__cause__ is not None

    @pytest.mark.asyncio
    async def test_execute_empty_provider_list_raises(self) -> None:
        from mcp_common.llm.fallback import FallbackChain

        chain = FallbackChain([])
        with pytest.raises(AllProvidersExhaustedError, match="All 0 providers failed"):
            await chain.execute({"model": "m", "messages": []})

    def test_circuit_breakers_initialized_per_provider(self) -> None:
        from mcp_common.llm.fallback import FallbackChain

        p1 = _make_mock_provider("a")
        p2 = _make_mock_provider("b")
        chain = FallbackChain([p1, p2])
        assert "a" in chain._circuit_breakers
        assert "b" in chain._circuit_breakers
        assert len(chain._circuit_breakers) == 2

    def test_from_settings(self, tmp_path: Path) -> None:
        content = {
            "default_provider": "zai",
            "fallback_chain": ["zai", "ollama"],
            "zai": {
                "enabled": True,
                "base_url": "https://api.z.ai/v4",
                "api_key": "sk-test",
                "priority": 1,
            },
            "ollama": {
                "enabled": True,
                "base_url": "http://localhost:11434",
                "api_key": "",
                "priority": 2,
            },
        }
        path = tmp_path / "models.yaml"
        path.write_text(yaml.dump(content))
        settings = LLMSettings.from_yaml(path)

        mock_openai = MagicMock()
        mock_openai.AsyncOpenAI = MagicMock(return_value=MagicMock())

        with patch.dict("sys.modules", {"openai": mock_openai}):
            import sys

            # Only clear provider module; re-import fallback which will
            # pick up the freshly mocked openai via its own import of
            # OpenAICompatibleProvider.
            for mod_key in list(sys.modules.keys()):
                if mod_key == "mcp_common.llm.provider" or mod_key.startswith(
                    "mcp_common.llm.provider."
                ):
                    del sys.modules[mod_key]

            from mcp_common.llm.fallback import FallbackChain as FC

            chain = FC.from_settings(settings)
            provider_names = [p.name for p in chain._providers]
            assert set(provider_names) == {"zai", "ollama"}

    def test_from_settings_skips_disabled_providers(self, tmp_path: Path) -> None:
        content = {
            "fallback_chain": ["zai", "ollama"],
            "zai": {"enabled": True, "base_url": "", "api_key": "", "priority": 1},
            "ollama": {"enabled": False, "base_url": "", "api_key": "", "priority": 2},
        }
        path = tmp_path / "models.yaml"
        path.write_text(yaml.dump(content))
        settings = LLMSettings.from_yaml(path)

        mock_openai = MagicMock()
        mock_openai.AsyncOpenAI = MagicMock(return_value=MagicMock())

        with patch.dict("sys.modules", {"openai": mock_openai}):
            import sys

            for mod_key in list(sys.modules.keys()):
                if mod_key == "mcp_common.llm.provider" or mod_key.startswith(
                    "mcp_common.llm.provider."
                ):
                    del sys.modules[mod_key]

            from mcp_common.llm.fallback import FallbackChain as FC

            chain = FC.from_settings(settings)
            provider_names = [p.name for p in chain._providers]
            assert provider_names == ["zai"]
