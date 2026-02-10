"""Tests for prompting adapter data models."""

from __future__ import annotations

import pytest

from mcp_common.prompting.models import (
    ButtonConfig,
    DialogResult,
    NotificationLevel,
    PromptConfig,
    PromptRequest,
    PromptStyle,
)


@pytest.mark.unit
class TestNotificationLevel:
    """Tests for NotificationLevel enum."""

    def test_notification_level_values(self) -> None:
        """Test NotificationLevel has correct values."""
        assert NotificationLevel.INFO.value == "info"
        assert NotificationLevel.WARNING.value == "warning"
        assert NotificationLevel.ERROR.value == "error"
        assert NotificationLevel.SUCCESS.value == "success"

    def test_notification_level_count(self) -> None:
        """Test NotificationLevel has 4 levels."""
        assert len(NotificationLevel) == 4

    def test_notification_level_from_string(self) -> None:
        """Test creating NotificationLevel from string."""
        level = NotificationLevel("info")
        assert level == NotificationLevel.INFO


@pytest.mark.unit
class TestPromptStyle:
    """Tests for PromptStyle enum."""

    def test_prompt_style_values(self) -> None:
        """Test PromptStyle has correct values."""
        assert PromptStyle.DEFAULT.value == "default"
        assert PromptStyle.DANGER.value == "danger"
        assert PromptStyle.WARNING.value == "warning"
        assert PromptStyle.INFO.value == "info"
        assert PromptStyle.SUCCESS.value == "success"

    def test_prompt_style_count(self) -> None:
        """Test PromptStyle has 5 styles."""
        assert len(PromptStyle) == 5


@pytest.mark.unit
class TestButtonConfig:
    """Tests for ButtonConfig model."""

    def test_button_config_with_required_fields(self) -> None:
        """Test ButtonConfig with only required field."""
        button = ButtonConfig(label="OK")
        assert button.label == "OK"
        assert button.is_default is False
        assert button.is_cancel is False

    def test_button_config_with_all_fields(self) -> None:
        """Test ButtonConfig with all fields."""
        button = ButtonConfig(label="Confirm", is_default=True, is_cancel=False)
        assert button.label == "Confirm"
        assert button.is_default is True
        assert button.is_cancel is False

    def test_button_config_is_cancel(self) -> None:
        """Test ButtonConfig with is_cancel flag."""
        button = ButtonConfig(label="Cancel", is_cancel=True)
        assert button.is_cancel is True


@pytest.mark.unit
class TestDialogResult:
    """Tests for DialogResult model."""

    def test_empty_dialog_result(self) -> None:
        """Test DialogResult with no fields set."""
        result = DialogResult()
        assert result.button_clicked is None
        assert result.text_input is None
        assert result.cancelled is False
        assert result.selected_choice is None
        assert result.selected_files is None
        assert result.selected_directory is None

    def test_dialog_result_with_button_clicked(self) -> None:
        """Test DialogResult with button_clicked."""
        result = DialogResult(button_clicked="OK")
        assert result.button_clicked == "OK"
        assert result.cancelled is False

    def test_dialog_result_with_text_input(self) -> None:
        """Test DialogResult with text_input."""
        result = DialogResult(text_input="Hello World")
        assert result.text_input == "Hello World"
        assert result.cancelled is False

    def test_dialog_result_cancelled(self) -> None:
        """Test DialogResult with cancelled flag."""
        result = DialogResult(cancelled=True)
        assert result.cancelled is True

    def test_dialog_result_with_selected_choice(self) -> None:
        """Test DialogResult with selected_choice."""
        result = DialogResult(selected_choice="Option A")
        assert result.selected_choice == "Option A"

    def test_dialog_result_with_selected_files(self) -> None:
        """Test DialogResult with selected_files."""
        files = ["/path/to/file1.txt", "/path/to/file2.txt"]
        result = DialogResult(selected_files=files)
        assert result.selected_files == files
        assert len(result.selected_files) == 2

    def test_dialog_result_with_selected_directory(self) -> None:
        """Test DialogResult with selected_directory."""
        result = DialogResult(selected_directory="/path/to/dir")
        assert result.selected_directory == "/path/to/dir"

    def test_dialog_result_with_multiple_fields(self) -> None:
        """Test DialogResult with multiple fields."""
        result = DialogResult(
            button_clicked="OK",
            text_input="Test input",
            selected_choice="Choice 1",
        )
        assert result.button_clicked == "OK"
        assert result.text_input == "Test input"
        assert result.selected_choice == "Choice 1"


@pytest.mark.unit
class TestPromptConfig:
    """Tests for PromptConfig model."""

    def test_default_prompt_config(self) -> None:
        """Test PromptConfig with defaults."""
        config = PromptConfig()
        assert config.backend == "auto"
        assert config.timeout is None
        assert config.macos_icon is None
        assert config.macos_sound == "default"
        assert config.tui_theme == "default"
        assert config.default_style == PromptStyle.DEFAULT

    def test_prompt_config_with_backend(self) -> None:
        """Test PromptConfig with backend specified."""
        config = PromptConfig(backend="pyobjc")
        assert config.backend == "pyobjc"

    def test_prompt_config_with_timeout(self) -> None:
        """Test PromptConfig with timeout."""
        config = PromptConfig(timeout=30)
        assert config.timeout == 30

    def test_prompt_config_with_macos_settings(self) -> None:
        """Test PromptConfig with macOS-specific settings."""
        config = PromptConfig(
            macos_icon="/path/to/icon.icns",
            macos_sound="ping",
        )
        assert config.macos_icon == "/path/to/icon.icns"
        assert config.macos_sound == "ping"

    def test_prompt_config_with_tui_settings(self) -> None:
        """Test PromptConfig with TUI settings."""
        config = PromptConfig(tui_theme="dark")
        assert config.tui_theme == "dark"

    def test_prompt_config_with_style(self) -> None:
        """Test PromptConfig with custom style."""
        config = PromptConfig(default_style=PromptStyle.DANGER)
        assert config.default_style == PromptStyle.DANGER

    def test_prompt_config_extra_fields_allowed(self) -> None:
        """Test PromptConfig allows extra fields."""
        config = PromptConfig(custom_field="custom_value")
        assert config.custom_field == "custom_value"  # type: ignore


@pytest.mark.unit
class TestPromptRequest:
    """Tests for PromptRequest model."""

    def test_prompt_request_minimal(self) -> None:
        """Test PromptRequest with minimal required fields."""
        request = PromptRequest(title="Test", message="Test message")
        assert request.title == "Test"
        assert request.message == "Test message"
        assert request.detail is None
        assert request.default is None
        assert request.placeholder is None
        assert request.choices is None
        assert request.buttons is None
        assert request.secure is False
        assert request.style is None

    def test_prompt_request_with_detail(self) -> None:
        """Test PromptRequest with detail."""
        request = PromptRequest(
            title="Test",
            message="Test message",
            detail="Additional details",
        )
        assert request.detail == "Additional details"

    def test_prompt_request_with_default(self) -> None:
        """Test PromptRequest with default value."""
        request = PromptRequest(
            title="Test",
            message="Test message",
            default="default_value",
        )
        assert request.default == "default_value"

    def test_prompt_request_with_placeholder(self) -> None:
        """Test PromptRequest with placeholder."""
        request = PromptRequest(
            title="Test",
            message="Test message",
            placeholder="Enter text here",
        )
        assert request.placeholder == "Enter text here"

    def test_prompt_request_with_choices(self) -> None:
        """Test PromptRequest with choices."""
        choices = ["Option A", "Option B", "Option C"]
        request = PromptRequest(
            title="Test",
            message="Test message",
            choices=choices,
        )
        assert request.choices == choices
        assert len(request.choices) == 3

    def test_prompt_request_with_buttons(self) -> None:
        """Test PromptRequest with buttons."""
        buttons = ["OK", "Cancel", "Help"]
        request = PromptRequest(
            title="Test",
            message="Test message",
            buttons=buttons,
        )
        assert request.buttons == buttons

    def test_prompt_request_with_secure_flag(self) -> None:
        """Test PromptRequest with secure flag."""
        request = PromptRequest(
            title="Test",
            message="Enter password",
            secure=True,
        )
        assert request.secure is True

    def test_prompt_request_with_style(self) -> None:
        """Test PromptRequest with style."""
        request = PromptRequest(
            title="Test",
            message="Test message",
            style="warning",
        )
        assert request.style == "warning"

    def test_prompt_request_with_file_options(self) -> None:
        """Test PromptRequest with file selection options."""
        request = PromptRequest(
            title="Test",
            message="Select files",
            allowed_types=["py", "txt"],
            multiple_files=True,
        )
        assert request.allowed_types == ["py", "txt"]
        assert request.multiple_files is True

    def test_prompt_request_with_notification_options(self) -> None:
        """Test PromptRequest with notification options."""
        request = PromptRequest(
            title="Test",
            message="Test message",
            level=NotificationLevel.ERROR,
            sound=False,
        )
        assert request.level == NotificationLevel.ERROR
        assert request.sound is False

    def test_prompt_request_all_fields(self) -> None:
        """Test PromptRequest with all fields."""
        request = PromptRequest(
            title="Complete Test",
            message="Test message with all fields",
            detail="Detailed information",
            default="default_value",
            placeholder="Placeholder text",
            choices=["A", "B", "C"],
            buttons=["OK", "Cancel"],
            secure=True,
            style="danger",
            allowed_types=["txt"],
            multiple_files=False,
            level=NotificationLevel.WARNING,
            sound=True,
        )
        assert request.title == "Complete Test"
        assert request.message == "Test message with all fields"
        assert request.detail == "Detailed information"
        assert request.default == "default_value"
        assert request.placeholder == "Placeholder text"
        assert len(request.choices) == 3
        assert len(request.buttons) == 2
        assert request.secure is True
        assert request.style == "danger"
        assert request.allowed_types == ["txt"]
        assert request.multiple_files is False
        assert request.level == NotificationLevel.WARNING
        assert request.sound is True
