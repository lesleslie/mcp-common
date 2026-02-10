"""Tests for prompting adapter exceptions."""

from __future__ import annotations

import pytest

from mcp_common.prompting.exceptions import (
    BackendUnavailableError,
    DialogDisplayError,
    NotificationError,
    PromptAdapterError,
    UserCancelledError,
    ValidationError,
)
from mcp_common.prompting.models import NotificationLevel


@pytest.mark.unit
class TestPromptAdapterError:
    """Tests for base PromptAdapterError exception."""

    def test_prompt_adapter_error_is_base_exception(self) -> None:
        """Test PromptAdapterError is the base for all prompting exceptions."""
        error = PromptAdapterError("Base error")
        assert isinstance(error, Exception)
        assert str(error) == "Base error"

    def test_prompt_adapter_error_with_backend(self) -> None:
        """Test PromptAdapterError with backend context."""
        error = PromptAdapterError(message="Test error", backend="pyobjc")
        assert str(error) == "[pyobjc] Test error"
        assert error.backend == "pyobjc"

    def test_prompt_adapter_error_without_backend(self) -> None:
        """Test PromptAdapterError without backend context."""
        error = PromptAdapterError(message="Test error", backend=None)
        assert str(error) == "Test error"
        assert error.backend is None

    def test_all_exceptions_inherit_from_base(self) -> None:
        """Test all custom exceptions inherit from PromptAdapterError."""
        exceptions = [
            BackendUnavailableError("test", "test"),
            DialogDisplayError("test", "alert"),
            NotificationError("test", "Test"),
            UserCancelledError("test"),
            ValidationError("test", "field", "value", "reason"),
        ]

        for exc in exceptions:
            assert isinstance(exc, PromptAdapterError)


@pytest.mark.unit
class TestBackendUnavailableError:
    """Tests for BackendUnavailableError exception."""

    def test_basic_backend_unavailable_error(self) -> None:
        """Test basic backend unavailable error."""
        error = BackendUnavailableError(backend="pyobjc")
        assert error.backend == "pyobjc"
        assert error.reason is None
        assert error.install_hint is None
        assert "pyobjc" in str(error)

    def test_backend_unavailable_with_reason(self) -> None:
        """Test backend unavailable error with reason."""
        error = BackendUnavailableError(
            backend="pyobjc",
            reason="Package not installed",
        )
        assert error.backend == "pyobjc"
        assert error.reason == "Package not installed"
        assert "Package not installed" in str(error)

    def test_backend_unavailable_with_install_hint(self) -> None:
        """Test backend unavailable error with install hint."""
        error = BackendUnavailableError(
            backend="pyobjc",
            reason="Package not installed",
            install_hint="pip install 'mcp-common[macos-prompts]'",
        )
        assert error.backend == "pyobjc"
        assert error.reason == "Package not installed"
        assert error.install_hint == "pip install 'mcp-common[macos-prompts]'"
        assert "pip install" in str(error)

    def test_backend_unavailable_all_fields(self) -> None:
        """Test backend unavailable error with all fields."""
        error = BackendUnavailableError(
            backend="prompt-toolkit",
            reason="Not installed",
            install_hint="pip install 'mcp-common[terminal-prompts]'",
        )
        assert "prompt-toolkit" in str(error)
        assert error.reason == "Not installed"
        assert error.install_hint == "pip install 'mcp-common[terminal-prompts]'"


@pytest.mark.unit
class TestDialogDisplayError:
    """Tests for DialogDisplayError exception."""

    def test_basic_dialog_display_error(self) -> None:
        """Test basic dialog display error."""
        error = DialogDisplayError(backend="pyobjc", dialog_type="alert")
        assert error.backend == "pyobjc"
        assert error.dialog_type == "alert"
        assert error.reason is None
        assert "alert" in str(error)

    def test_dialog_display_error_with_reason(self) -> None:
        """Test dialog display error with reason."""
        error = DialogDisplayError(
            backend="pyobjc",
            dialog_type="confirm",
            reason="Main thread not available",
        )
        assert error.backend == "pyobjc"
        assert error.dialog_type == "confirm"
        assert error.reason == "Main thread not available"
        assert "Main thread not available" in str(error)

    def test_dialog_display_error_all_types(self) -> None:
        """Test dialog display error for different dialog types."""
        dialog_types = ["alert", "confirm", "prompt_text", "prompt_choice"]

        for dialog_type in dialog_types:
            error = DialogDisplayError(
                backend="pyobjc",
                dialog_type=dialog_type,
                reason="Test failure",
            )
            assert error.dialog_type == dialog_type
            assert dialog_type in str(error)


@pytest.mark.unit
class TestNotificationError:
    """Tests for NotificationError exception."""

    def test_basic_notification_error(self) -> None:
        """Test basic notification error."""
        error = NotificationError(
            backend="pyobjc",
            title="Test Notification",
        )
        assert error.backend == "pyobjc"
        assert error.title == "Test Notification"
        assert error.reason is None
        assert error.level == NotificationLevel.INFO
        assert "Test Notification" in str(error)

    def test_notification_error_with_reason(self) -> None:
        """Test notification error with reason."""
        error = NotificationError(
            backend="pyobjc",
            title="Test",
            reason="Notification Center not available",
        )
        assert error.reason == "Notification Center not available"
        assert "Notification Center not available" in str(error)

    def test_notification_error_with_level(self) -> None:
        """Test notification error with level."""
        error = NotificationError(
            backend="pyobjc",
            title="Error Notification",
            level=NotificationLevel.ERROR,
        )
        assert error.level == NotificationLevel.ERROR
        assert error.title == "Error Notification"

    def test_notification_error_all_levels(self) -> None:
        """Test notification error for all levels."""
        levels = [
            NotificationLevel.INFO,
            NotificationLevel.WARNING,
            NotificationLevel.ERROR,
            NotificationLevel.SUCCESS,
        ]

        for level in levels:
            error = NotificationError(
                backend="pyobjc",
                title=f"{level.value.title()} Notification",
                level=level,
            )
            assert error.level == level

    def test_notification_error_all_fields(self) -> None:
        """Test notification error with all fields."""
        error = NotificationError(
            backend="prompt-toolkit",
            title="Warning",
            reason="Terminal not available",
            level=NotificationLevel.WARNING,
        )
        assert error.backend == "prompt-toolkit"
        assert error.title == "Warning"
        assert error.reason == "Terminal not available"
        assert error.level == NotificationLevel.WARNING


@pytest.mark.unit
class TestUserCancelledError:
    """Tests for UserCancelledError exception."""

    def test_basic_user_cancelled_error(self) -> None:
        """Test basic user cancelled error."""
        error = UserCancelledError(backend="pyobjc")
        assert error.backend == "pyobjc"
        assert error.prompt_type == "prompt"
        assert "prompt" in str(error)

    def test_user_cancelled_with_custom_prompt_type(self) -> None:
        """Test user cancelled error with custom prompt type."""
        error = UserCancelledError(backend="pyobjc", prompt_type="text")
        assert error.backend == "pyobjc"
        assert error.prompt_type == "text"
        assert "text" in str(error)

    def test_user_cancelled_all_prompt_types(self) -> None:
        """Test user cancelled error for different prompt types."""
        prompt_types = ["text", "choice", "file", "directory"]

        for prompt_type in prompt_types:
            error = UserCancelledError(
                backend="pyobjc",
                prompt_type=prompt_type,
            )
            assert error.prompt_type == prompt_type
            assert prompt_type in str(error)


@pytest.mark.unit
class TestValidationError:
    """Tests for ValidationError exception."""

    def test_basic_validation_error(self) -> None:
        """Test basic validation error."""
        error = ValidationError(
            backend="pyobjc",
            field="email",
            value="invalid",
            reason="Invalid email format",
        )
        assert error.backend == "pyobjc"
        assert error.field == "email"
        assert error.value == "invalid"
        assert error.reason == "Invalid email format"
        assert "email" in str(error)

    def test_validation_error_all_fields(self) -> None:
        """Test validation error with all fields."""
        error = ValidationError(
            backend="prompt-toolkit",
            field="age",
            value="-5",
            reason="Age must be positive",
        )
        assert error.backend == "prompt-toolkit"
        assert error.field == "age"
        assert error.value == "-5"
        assert error.reason == "Age must be positive"
        assert "age" in str(error)

    def test_validation_error_different_fields(self) -> None:
        """Test validation error for different field types."""
        test_cases = [
            ("username", "", "Username is required"),
            ("port", "99999", "Port out of range"),
            ("url", "not-a-url", "Invalid URL format"),
        ]

        for field, value, reason in test_cases:
            error = ValidationError(
                backend="pyobjc",
                field=field,
                value=value,
                reason=reason,
            )
            assert error.field == field
            assert error.value == value
            assert error.reason == reason


@pytest.mark.unit
class TestExceptionUsagePatterns:
    """Tests for realistic exception usage patterns."""

    def test_raise_backend_unavailable_error(self) -> None:
        """Test raising backend unavailable error."""
        with pytest.raises(BackendUnavailableError) as exc_info:
            raise BackendUnavailableError(
                backend="pyobjc",
                reason="Not on macOS",
                install_hint="Use on macOS only",
            )

        error = exc_info.value
        assert error.backend == "pyobjc"
        assert "Not on macOS" in str(error)

    def test_raise_dialog_display_error(self) -> None:
        """Test raising dialog display error."""
        with pytest.raises(DialogDisplayError) as exc_info:
            raise DialogDisplayError(
                backend="pyobjc",
                dialog_type="alert",
                reason="GUI not available",
            )

        error = exc_info.value
        assert error.dialog_type == "alert"
        assert "GUI not available" in str(error)

    def test_raise_notification_error(self) -> None:
        """Test raising notification error."""
        with pytest.raises(NotificationError) as exc_info:
            raise NotificationError(
                backend="pyobjc",
                title="Test",
                reason="Failed to send",
            )

        error = exc_info.value
        assert error.title == "Test"
        assert "Failed to send" in str(error)

    def test_exception_catching_hierarchy(self) -> None:
        """Test catching exceptions using base class."""

        def raise_backend_error() -> None:
            raise BackendUnavailableError(
                backend="pyobjc",
                reason="Test",
            )

        # Can catch as specific type
        with pytest.raises(BackendUnavailableError):
            raise_backend_error()

        # Can catch as base type
        with pytest.raises(PromptAdapterError):
            raise_backend_error()

    @pytest.mark.asyncio
    async def test_user_cancelled_is_control_flow(self) -> None:
        """Test UserCancelledError can be used for control flow."""

        async def mock_prompt(backend: str) -> str | None:
            """Simulate user cancelling."""
            try:
                raise UserCancelledError(backend=backend, prompt_type="text")
            except UserCancelledError as e:
                # Handle cancellation gracefully
                return None

        result = await mock_prompt("pyobjc")
        assert result is None
