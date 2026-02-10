"""Tests for prompt-toolkit backend."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch

import pytest

from mcp_common.backends.toolkit import PromptToolkitBackend
from mcp_common.prompting.exceptions import BackendUnavailableError, DialogDisplayError
from mcp_common.prompting.models import DialogResult, NotificationLevel, PromptAdapterSettings, PromptConfig


@pytest.mark.unit
class TestPromptToolkitBackend:
    """Tests for PromptToolkitBackend."""

    def test_backend_initialization(self) -> None:
        """Test backend initializes with config."""
        config = PromptAdapterSettings(timeout=30)
        backend = PromptToolkitBackend(config=config)
        assert backend.config == config
        assert backend.backend_name == "prompt-toolkit"

    def test_backend_name_property(self) -> None:
        """Test backend_name property."""
        backend = PromptToolkitBackend(config=PromptAdapterSettings())
        assert backend.backend_name == "prompt-toolkit"

    def test_is_available_static(self) -> None:
        """Test is_available_static method."""
        # prompt-toolkit should be available in test environment
        assert PromptToolkitBackend.is_available_static() is True

    def test_is_available_instance(self) -> None:
        """Test is_available instance method."""
        backend = PromptToolkitBackend(config=PromptAdapterSettings())
        assert backend.is_available() is True

    def test_unavailable_error_when_not_installed(self) -> None:
        """Test error when prompt-toolkit is not installed."""
        with patch(
            "mcp_common.backends.toolkit.PROMPT_TOOLKIT_AVAILABLE",
            False,
        ):
            with pytest.raises(BackendUnavailableError) as exc_info:
                PromptToolkitBackend(config=PromptAdapterSettings())

            error = exc_info.value
            assert error.backend == "prompt-toolkit"
            assert "install" in str(error).lower()


@pytest.mark.unit
class TestPromptToolkitBackendAlert:
    """Tests for alert method."""

    @pytest.mark.asyncio
    async def test_alert_basic(self) -> None:
        """Test basic alert dialog."""
        backend = PromptToolkitBackend(config=PromptAdapterSettings())

        with patch("builtins.input", return_value=""):
            with patch("builtins.print"):
                result = await backend.alert(
                    title="Test Title",
                    message="Test message",
                )

                assert isinstance(result, DialogResult)
                assert result.button_clicked == "OK"
                assert result.cancelled is False

    @pytest.mark.asyncio
    async def test_alert_with_buttons(self) -> None:
        """Test alert with custom buttons."""
        backend = PromptToolkitBackend(config=PromptAdapterSettings())

        with patch("mcp_common.backends.toolkit.prompt") as mock_prompt:
            # Simulate user selecting "Cancel" (option 2)
            mock_prompt.return_value = "2"
            result = await backend.alert(
                title="Confirm",
                message="Are you sure?",
                buttons=["OK", "Cancel"],
            )

            assert result.button_clicked == "Cancel"
            assert result.cancelled is False

    @pytest.mark.asyncio
    async def test_alert_with_detail(self) -> None:
        """Test alert with detail text."""
        backend = PromptToolkitBackend(config=PromptAdapterSettings())

        with patch("builtins.input", return_value=""):
            with patch("builtins.print"):
                result = await backend.alert(
                    title="Error",
                    message="Something went wrong",
                    detail="Detailed error information",
                )

                assert result.button_clicked == "OK"
                assert result.cancelled is False

    @pytest.mark.asyncio
    async def test_alert_cancelled(self) -> None:
        """Test alert when user cancels."""
        backend = PromptToolkitBackend(config=PromptAdapterSettings())

        with patch("builtins.input", side_effect=KeyboardInterrupt()):
            with patch("builtins.print"):
                result = await backend.alert(
                    title="Test",
                    message="Test message",
                )

                assert result.cancelled is True

    @pytest.mark.asyncio
    async def test_alert_handles_exception(self) -> None:
        """Test alert method handles exceptions gracefully."""
        backend = PromptToolkitBackend(config=PromptAdapterSettings())

        # Mock prompt_choice to raise an exception
        with patch.object(backend, "prompt_choice", side_effect=Exception("Unexpected error")):
            with pytest.raises(DialogDisplayError) as exc_info:
                await backend.alert(
                    title="Test",
                    message="Test message",
                    buttons=["OK", "Cancel"],
                )

            assert exc_info.value.backend == "prompt-toolkit"
            assert exc_info.value.dialog_type == "alert"


@pytest.mark.unit
class TestPromptToolkitBackendConfirm:
    """Tests for confirm method."""

    @pytest.mark.asyncio
    async def test_confirm_yes(self) -> None:
        """Test confirm dialog returns True."""
        backend = PromptToolkitBackend(config=PromptAdapterSettings())

        with patch("mcp_common.backends.toolkit.confirm") as mock_confirm:
            with patch("builtins.print"):
                mock_confirm.return_value = True
                result = await backend.confirm(
                    title="Confirm",
                    message="Do you want to continue?",
                )

                assert result is True

    @pytest.mark.asyncio
    async def test_confirm_no(self) -> None:
        """Test confirm dialog returns False."""
        backend = PromptToolkitBackend(config=PromptAdapterSettings())

        with patch("mcp_common.backends.toolkit.confirm") as mock_confirm:
            with patch("builtins.print"):
                mock_confirm.return_value = False
                result = await backend.confirm(
                    title="Confirm",
                    message="Do you want to continue?",
                )

                assert result is False

    @pytest.mark.asyncio
    async def test_confirm_with_custom_labels(self) -> None:
        """Test confirm with custom button labels."""
        backend = PromptToolkitBackend(config=PromptAdapterSettings())

        with patch("mcp_common.backends.toolkit.confirm") as mock_confirm:
            with patch("builtins.print"):
                mock_confirm.return_value = True
                result = await backend.confirm(
                    title="Deploy",
                    message="Deploy to production?",
                    yes_label="Deploy",
                    no_label="Cancel",
                )

                assert result is True

    @pytest.mark.asyncio
    async def test_confirm_with_default_true(self) -> None:
        """Test confirm with default True."""
        backend = PromptToolkitBackend(config=PromptAdapterSettings())

        with patch("mcp_common.backends.toolkit.confirm") as mock_confirm:
            with patch("builtins.print"):
                mock_confirm.return_value = True
                result = await backend.confirm(
                    title="Confirm",
                    message="Continue?",
                    default=True,
                )

                assert result is True

    @pytest.mark.asyncio
    async def test_confirm_handles_exception(self) -> None:
        """Test confirm method handles exceptions gracefully."""
        backend = PromptToolkitBackend(config=PromptAdapterSettings())

        with patch("mcp_common.backends.toolkit.confirm", side_effect=Exception("Unexpected error")):
            # Should return False (safe default) on exception
            result = await backend.confirm(
                title="Test",
                message="Test message",
            )

            # Should return False (safe default)
            assert result is False


@pytest.mark.unit
class TestPromptToolkitBackendPromptText:
    """Tests for prompt_text method."""

    @pytest.mark.asyncio
    async def test_prompt_text_basic(self) -> None:
        """Test basic text prompt."""
        backend = PromptToolkitBackend(config=PromptAdapterSettings())

        with patch("mcp_common.backends.toolkit.prompt") as mock_prompt:
            mock_prompt.return_value = "Hello World"
            result = await backend.prompt_text(
                title="Input",
                message="Enter text:",
            )

            assert result == "Hello World"

    @pytest.mark.asyncio
    async def test_prompt_text_with_default(self) -> None:
        """Test text prompt with default value."""
        backend = PromptToolkitBackend(config=PromptAdapterSettings())

        with patch("mcp_common.backends.toolkit.prompt") as mock_prompt:
            mock_prompt.return_value = "default_value"
            result = await backend.prompt_text(
                title="Input",
                message="Enter text:",
                default="default_value",
            )

            assert result == "default_value"

    @pytest.mark.asyncio
    async def test_prompt_text_cancelled(self) -> None:
        """Test text prompt when cancelled."""
        backend = PromptToolkitBackend(config=PromptAdapterSettings())

        with patch("mcp_common.backends.toolkit.prompt") as mock_prompt:
            # Simulate Ctrl+C
            mock_prompt.side_effect = KeyboardInterrupt()
            result = await backend.prompt_text(
                title="Input",
                message="Enter text:",
            )

            assert result is None

    @pytest.mark.asyncio
    async def test_prompt_text_secure(self) -> None:
        """Test secure text prompt (password)."""
        backend = PromptToolkitBackend(config=PromptAdapterSettings())

        with patch("mcp_common.backends.toolkit.prompt") as mock_prompt:
            mock_prompt.return_value = "secret_password"
            result = await backend.prompt_text(
                title="Password",
                message="Enter password:",
                secure=True,
            )

            assert result == "secret_password"


@pytest.mark.unit
class TestPromptToolkitBackendPromptChoice:
    """Tests for prompt_choice method."""

    @pytest.mark.asyncio
    async def test_prompt_choice_basic(self) -> None:
        """Test basic choice prompt."""
        backend = PromptToolkitBackend(config=PromptAdapterSettings())

        with patch("mcp_common.backends.toolkit.prompt") as mock_prompt:
            with patch("builtins.print"):
                # Simulate user selecting "Option B" by entering "2"
                mock_prompt.return_value = "2"
                result = await backend.prompt_choice(
                    title="Select",
                    message="Choose an option:",
                    choices=["Option A", "Option B", "Option C"],
                )

                assert result == "Option B"

    @pytest.mark.asyncio
    async def test_prompt_choice_with_default(self) -> None:
        """Test choice prompt with default selection."""
        backend = PromptToolkitBackend(config=PromptAdapterSettings())

        with patch("mcp_common.backends.toolkit.prompt") as mock_prompt:
            with patch("builtins.print"):
                # Empty input should return default
                mock_prompt.return_value = ""
                result = await backend.prompt_choice(
                    title="Select",
                    message="Choose:",
                    choices=["A", "B", "C"],
                    default="B",
                )

                assert result == "B"

    @pytest.mark.asyncio
    async def test_prompt_choice_cancelled(self) -> None:
        """Test choice prompt when cancelled."""
        backend = PromptToolkitBackend(config=PromptAdapterSettings())

        with patch("mcp_common.backends.toolkit.prompt") as mock_prompt:
            with patch("builtins.print"):
                # Simulate Ctrl+C
                mock_prompt.side_effect = KeyboardInterrupt()
                result = await backend.prompt_choice(
                    title="Select",
                    message="Choose:",
                    choices=["A", "B"],
                )

                assert result is None


@pytest.mark.unit
class TestPromptToolkitBackendNotify:
    """Tests for notify method."""

    @pytest.mark.asyncio
    async def test_notify_info(self) -> None:
        """Test info notification."""
        backend = PromptToolkitBackend(config=PromptAdapterSettings())

        with patch("builtins.print") as mock_print:
            result = await backend.notify(
                title="Info",
                message="Information message",
                level=NotificationLevel.INFO,
            )

            assert result is True
            mock_print.assert_called_once()
            args = mock_print.call_args[0][0]
            assert "Info" in args
            assert "Information message" in args

    @pytest.mark.asyncio
    async def test_notify_warning(self) -> None:
        """Test warning notification."""
        backend = PromptToolkitBackend(config=PromptAdapterSettings())

        with patch("builtins.print") as mock_print:
            result = await backend.notify(
                title="Warning",
                message="Warning message",
                level=NotificationLevel.WARNING,
            )

            assert result is True
            args = mock_print.call_args[0][0]
            assert "⚠" in args or "Warning" in args

    @pytest.mark.asyncio
    async def test_notify_error(self) -> None:
        """Test error notification."""
        backend = PromptToolkitBackend(config=PromptAdapterSettings())

        with patch("builtins.print") as mock_print:
            result = await backend.notify(
                title="Error",
                message="Error message",
                level=NotificationLevel.ERROR,
            )

            assert result is True
            args = mock_print.call_args[0][0]
            assert "Error" in args

    @pytest.mark.asyncio
    async def test_notify_success(self) -> None:
        """Test success notification."""
        backend = PromptToolkitBackend(config=PromptAdapterSettings())

        with patch("builtins.print") as mock_print:
            result = await backend.notify(
                title="Success",
                message="Operation completed",
                level=NotificationLevel.SUCCESS,
            )

            assert result is True
            args = mock_print.call_args[0][0]
            assert "Success" in args or "✓" in args or "✅" in args


@pytest.mark.unit
class TestPromptToolkitBackendFileSelection:
    """Tests for file and directory selection methods."""

    @pytest.mark.asyncio
    async def test_select_file_single(self) -> None:
        """Test single file selection."""
        backend = PromptToolkitBackend(config=PromptAdapterSettings())

        with patch("mcp_common.backends.toolkit.prompt") as mock_prompt:
            mock_prompt.return_value = "/path/to/file.txt"
            result = await backend.select_file(
                title="Select File",
                allowed_types=["txt", "md"],
                multiple=False,
            )

            assert result is not None
            assert len(result) == 1
            assert str(result[0]) == "/path/to/file.txt"

    @pytest.mark.asyncio
    async def test_select_file_multiple(self) -> None:
        """Test multiple file selection."""
        backend = PromptToolkitBackend(config=PromptAdapterSettings())

        with patch("mcp_common.backends.toolkit.prompt") as mock_prompt:
            # Simulate comma-separated paths
            mock_prompt.return_value = "/path/file1.txt, /path/file2.txt"
            result = await backend.select_file(
                title="Select Files",
                allowed_types=None,
                multiple=True,
            )

            assert result is not None
            assert len(result) == 2
            assert str(result[0]) == "/path/file1.txt"
            assert str(result[1]) == "/path/file2.txt"

    @pytest.mark.asyncio
    async def test_select_file_cancelled(self) -> None:
        """Test file selection when cancelled."""
        backend = PromptToolkitBackend(config=PromptAdapterSettings())

        with patch("mcp_common.backends.toolkit.prompt") as mock_prompt:
            mock_prompt.side_effect = KeyboardInterrupt()
            result = await backend.select_file(
                title="Select File",
            )

            assert result is None

    @pytest.mark.asyncio
    async def test_select_directory(self) -> None:
        """Test directory selection."""
        backend = PromptToolkitBackend(config=PromptAdapterSettings())

        with patch("mcp_common.backends.toolkit.prompt") as mock_prompt:
            mock_prompt.return_value = "/path/to/directory"
            result = await backend.select_directory(
                title="Select Directory",
            )

            assert result is not None
            assert str(result) == "/path/to/directory"

    @pytest.mark.asyncio
    async def test_select_directory_cancelled(self) -> None:
        """Test directory selection when cancelled."""
        backend = PromptToolkitBackend(config=PromptAdapterSettings())

        with patch("mcp_common.backends.toolkit.prompt") as mock_prompt:
            mock_prompt.side_effect = KeyboardInterrupt()
            result = await backend.select_directory(
                title="Select Directory",
            )

            assert result is None


@pytest.mark.unit
class TestPromptToolkitBackendErrorHandling:
    """Tests for error handling in prompt-toolkit backend."""

    @pytest.mark.asyncio
    async def test_confirm_handles_exception(self) -> None:
        """Test confirm method handles exceptions gracefully."""
        backend = PromptToolkitBackend(config=PromptAdapterSettings())

        with patch("mcp_common.backends.toolkit.confirm", side_effect=Exception("Unexpected error")):
            # Should return False (safe default) on exception
            result = await backend.confirm(
                title="Test",
                message="Test message",
            )

            # Should return False (safe default)
            assert result is False
