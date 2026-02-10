"""Tests for PromptBackend abstract base class."""

from __future__ import annotations

import inspect

import pytest

from mcp_common.prompting.base import PromptBackend
from mcp_common.prompting.models import DialogResult, NotificationLevel, PromptAdapterSettings


@pytest.mark.unit
class TestPromptBackendInterface:
    """Tests for PromptBackend abstract interface."""

    def test_prompt_backend_is_abstract(self) -> None:
        """Test PromptBackend cannot be instantiated directly."""
        with pytest.raises(TypeError):
            PromptBackend()  # type: ignore

    def test_prompt_backend_has_abstract_methods(self) -> None:
        """Test PromptBackend defines required abstract methods."""
        abstract_methods = PromptBackend.__abstractmethods__

        required_methods = {
            "alert",
            "confirm",
            "prompt_text",
            "prompt_choice",
            "notify",
            "select_file",
            "select_directory",
            "is_available",
        }

        assert required_methods.issubset(abstract_methods)

    def test_prompt_backend_method_signatures(self) -> None:
        """Test PromptBackend method signatures are correct."""
        # Check alert method
        alert_sig = inspect.signature(PromptBackend.alert)
        assert "title" in alert_sig.parameters
        assert "message" in alert_sig.parameters
        assert "detail" in alert_sig.parameters
        assert "buttons" in alert_sig.parameters
        assert "default_button" in alert_sig.parameters
        assert "style" in alert_sig.parameters

        # Check confirm method
        confirm_sig = inspect.signature(PromptBackend.confirm)
        assert "title" in confirm_sig.parameters
        assert "message" in confirm_sig.parameters
        assert "default" in confirm_sig.parameters
        assert "yes_label" in confirm_sig.parameters
        assert "no_label" in confirm_sig.parameters

        # Check prompt_text method
        prompt_text_sig = inspect.signature(PromptBackend.prompt_text)
        assert "title" in prompt_text_sig.parameters
        assert "message" in prompt_text_sig.parameters
        assert "default" in prompt_text_sig.parameters
        assert "placeholder" in prompt_text_sig.parameters
        assert "secure" in prompt_text_sig.parameters

        # Check notify method
        notify_sig = inspect.signature(PromptBackend.notify)
        assert "title" in notify_sig.parameters
        assert "message" in notify_sig.parameters
        assert "level" in notify_sig.parameters
        assert "sound" in notify_sig.parameters

        # Check select_file method
        select_file_sig = inspect.signature(PromptBackend.select_file)
        assert "title" in select_file_sig.parameters
        assert "allowed_types" in select_file_sig.parameters
        assert "multiple" in select_file_sig.parameters

        # Check select_directory method
        select_dir_sig = inspect.signature(PromptBackend.select_directory)
        assert "title" in select_dir_sig.parameters

    def test_prompt_backend_has_backend_name_property(self) -> None:
        """Test PromptBackend has backend_name as abstract property."""
        # backend_name should be a property, not a method
        assert isinstance(PromptBackend.backend_name, property)


@pytest.mark.unit
class TestPromptBackendCompliance:
    """Tests that concrete backends comply with PromptBackend interface."""

    @pytest.mark.asyncio
    async def test_mock_backend_implements_all_methods(self) -> None:
        """Test that a mock backend can implement all required methods."""

        class MockPromptBackend(PromptBackend):
            """Mock implementation for testing."""

            def __init__(self) -> None:
                self.backend_name_value = "mock"

            async def alert(
                self,
                title: str,
                message: str,
                detail: str | None = None,
                buttons: list[str] | None = None,
                default_button: str | None = None,
                style: str = "info",
            ) -> DialogResult:
                return DialogResult(button_clicked="OK")

            async def confirm(
                self,
                title: str,
                message: str,
                default: bool = False,
                yes_label: str = "Yes",
                no_label: str = "No",
            ) -> bool:
                return default

            async def prompt_text(
                self,
                title: str,
                message: str,
                default: str = "",
                placeholder: str = "",
                secure: bool = False,
            ) -> str | None:
                return default

            async def prompt_choice(
                self,
                title: str,
                message: str,
                choices: list[str],
                default: str | None = None,
            ) -> str | None:
                return default if default else (choices[0] if choices else None)

            async def notify(
                self,
                title: str,
                message: str,
                level: NotificationLevel = NotificationLevel.INFO,
                sound: bool = True,
            ) -> bool:
                return True

            async def select_file(
                self,
                title: str,
                allowed_types: list[str] | None = None,
                multiple: bool = False,
            ) -> list | None:
                return []

            async def select_directory(self, title: str) -> str | None:
                return None

            async def initialize(self) -> None:
                """Initialize mock backend (no-op)."""
                pass

            async def shutdown(self) -> None:
                """Cleanup mock backend (no-op)."""
                pass

            def is_available(self) -> bool:
                return True

            @property
            def backend_name(self) -> str:
                return self.backend_name_value

        # Test that mock backend can be instantiated and used
        backend = MockPromptBackend()
        assert backend.is_available() is True
        assert backend.backend_name == "mock"

        # Test all methods can be called
        result = await backend.alert("Test", "Message")
        assert result.button_clicked == "OK"

        result = await backend.confirm("Test", "Message")
        assert isinstance(result, bool)

        result = await backend.prompt_text("Test", "Message")
        assert isinstance(result, str | None)

        result = await backend.prompt_choice("Test", "Message", ["A", "B"])
        assert isinstance(result, str | None)

        result = await backend.notify("Test", "Message")
        assert result is True

        result = await backend.select_file("Test")
        assert isinstance(result, list | None)

        result = await backend.select_directory("Test")
        assert isinstance(result, str | None)


@pytest.mark.unit
class TestPromptBackendDocumentation:
    """Tests for PromptBackend documentation completeness."""

    def test_alert_method_has_docstring(self) -> None:
        """Test alert method has documentation."""
        assert PromptBackend.alert.__doc__ is not None
        assert len(PromptBackend.alert.__doc__) > 0

    def test_confirm_method_has_docstring(self) -> None:
        """Test confirm method has documentation."""
        assert PromptBackend.confirm.__doc__ is not None
        assert len(PromptBackend.confirm.__doc__) > 0

    def test_prompt_text_method_has_docstring(self) -> None:
        """Test prompt_text method has documentation."""
        assert PromptBackend.prompt_text.__doc__ is not None
        assert len(PromptBackend.prompt_text.__doc__) > 0

    def test_notify_method_has_docstring(self) -> None:
        """Test notify method has documentation."""
        assert PromptBackend.notify.__doc__ is not None
        assert len(PromptBackend.notify.__doc__) > 0

    def test_select_file_method_has_docstring(self) -> None:
        """Test select_file method has documentation."""
        assert PromptBackend.select_file.__doc__ is not None
        assert len(PromptBackend.select_file.__doc__) > 0

    def test_select_directory_method_has_docstring(self) -> None:
        """Test select_directory method has documentation."""
        assert PromptBackend.select_directory.__doc__ is not None
        assert len(PromptBackend.select_directory.__doc__) > 0
