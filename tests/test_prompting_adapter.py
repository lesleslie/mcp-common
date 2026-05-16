"""Tests for PromptAdapter wrapper class."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from mcp_common.prompting.adapter import PromptAdapter
from mcp_common.prompting.models import (
    DialogResult,
    NotificationLevel,
    PromptAdapterSettings,
)


class TestPromptAdapterInitialization:
    """Test PromptAdapter initialization."""

    def test_init_default_backend(self) -> None:
        """Test initialization with default backend."""
        with patch("mcp_common.prompting.adapter.create_prompt_adapter") as mock_factory:
            mock_backend = AsyncMock()
            mock_factory.return_value = mock_backend

            adapter = PromptAdapter()

            assert adapter._backend is mock_backend
            mock_factory.assert_called_once_with(backend="auto", config=None)

    def test_init_with_backend_name(self) -> None:
        """Test initialization with specific backend name."""
        with patch("mcp_common.prompting.adapter.create_prompt_adapter") as mock_factory:
            mock_backend = AsyncMock()
            mock_factory.return_value = mock_backend

            adapter = PromptAdapter(backend="pyobjc")

            mock_factory.assert_called_once_with(backend="pyobjc", config=None)

    def test_init_with_settings(self) -> None:
        """Test initialization with custom settings."""
        with patch("mcp_common.prompting.adapter.create_prompt_adapter") as mock_factory:
            mock_backend = AsyncMock()
            mock_factory.return_value = mock_backend
            settings = PromptAdapterSettings(backend="prompt-toolkit")

            adapter = PromptAdapter(settings=settings)

            mock_factory.assert_called_once_with(backend="auto", config=settings)


class TestPromptAdapterDelegation:
    """Test method delegation to backend."""

    @pytest.fixture
    def mock_backend(self):
        """Create mock backend."""
        return AsyncMock()

    @pytest.fixture
    def adapter(self, mock_backend):
        """Create PromptAdapter with mocked backend."""
        with patch(
            "mcp_common.prompting.adapter.create_prompt_adapter",
            return_value=mock_backend,
        ):
            return PromptAdapter()

    @pytest.mark.asyncio
    async def test_alert_delegation(self, adapter, mock_backend) -> None:
        """Test alert method delegation."""
        mock_backend.alert.return_value = DialogResult(button_clicked="OK")

        result = await adapter.alert(
            title="Test",
            message="Message",
            detail="Detail",
            buttons=["OK", "Cancel"],
            default_button="OK",
            style="warning",
        )

        assert result.button_clicked == "OK"
        mock_backend.alert.assert_called_once_with(
            title="Test",
            message="Message",
            detail="Detail",
            buttons=["OK", "Cancel"],
            default_button="OK",
            style="warning",
        )

    @pytest.mark.asyncio
    async def test_confirm_delegation(self, adapter, mock_backend) -> None:
        """Test confirm method delegation."""
        mock_backend.confirm.return_value = True

        result = await adapter.confirm(
            title="Confirm",
            message="Are you sure?",
            default=False,
            yes_label="Yes",
            no_label="No",
        )

        assert result is True
        mock_backend.confirm.assert_called_once_with(
            title="Confirm",
            message="Are you sure?",
            default=False,
            yes_label="Yes",
            no_label="No",
        )

    @pytest.mark.asyncio
    async def test_prompt_text_delegation(self, adapter, mock_backend) -> None:
        """Test prompt_text method delegation."""
        mock_backend.prompt_text.return_value = "user input"

        result = await adapter.prompt_text(
            title="Input",
            message="Enter text",
            default="default",
            placeholder="placeholder",
            secure=True,
        )

        assert result == "user input"
        mock_backend.prompt_text.assert_called_once_with(
            title="Input",
            message="Enter text",
            default="default",
            placeholder="placeholder",
            secure=True,
        )

    @pytest.mark.asyncio
    async def test_prompt_choice_delegation(self, adapter, mock_backend) -> None:
        """Test prompt_choice method delegation."""
        mock_backend.prompt_choice.return_value = "option1"

        result = await adapter.prompt_choice(
            title="Choose",
            message="Pick one",
            choices=["option1", "option2"],
            default="option1",
        )

        assert result == "option1"
        mock_backend.prompt_choice.assert_called_once_with(
            title="Choose",
            message="Pick one",
            choices=["option1", "option2"],
            default="option1",
        )

    @pytest.mark.asyncio
    async def test_notify_delegation(self, adapter, mock_backend) -> None:
        """Test notify method delegation."""
        mock_backend.notify.return_value = True

        result = await adapter.notify(
            title="Notification",
            message="Hello",
            level=NotificationLevel.WARNING,
            sound=False,
        )

        assert result is True
        mock_backend.notify.assert_called_once_with(
            title="Notification",
            message="Hello",
            level=NotificationLevel.WARNING,
            sound=False,
        )

    @pytest.mark.asyncio
    async def test_select_file_delegation(self, adapter, mock_backend) -> None:
        """Test select_file method delegation."""
        from pathlib import Path

        mock_backend.select_file.return_value = [Path("/tmp/file.txt")]

        result = await adapter.select_file(
            title="Select File",
            allowed_types=[".txt", ".pdf"],
            multiple=True,
        )

        assert result == [Path("/tmp/file.txt")]
        mock_backend.select_file.assert_called_once_with(
            title="Select File",
            allowed_types=[".txt", ".pdf"],
            multiple=True,
        )

    @pytest.mark.asyncio
    async def test_select_directory_delegation(self, adapter, mock_backend) -> None:
        """Test select_directory method delegation."""
        from pathlib import Path

        mock_backend.select_directory.return_value = Path("/home/user")

        result = await adapter.select_directory(title="Select Folder")

        assert result == Path("/home/user")
        mock_backend.select_directory.assert_called_once_with(title="Select Folder")

    @pytest.mark.asyncio
    async def test_initialize_delegation(self, adapter, mock_backend) -> None:
        """Test initialize method delegation."""
        mock_backend.initialize.return_value = None

        await adapter.initialize()

        mock_backend.initialize.assert_called_once()

    @pytest.mark.asyncio
    async def test_shutdown_delegation(self, adapter, mock_backend) -> None:
        """Test shutdown method delegation."""
        mock_backend.shutdown.return_value = None

        await adapter.shutdown()

        mock_backend.shutdown.assert_called_once()

    def test_is_available_delegation(self, adapter, mock_backend) -> None:
        """Test is_available method delegation."""
        # is_available is a synchronous method, so mock it properly
        mock_backend.is_available = MagicMock(return_value=True)

        result = adapter.is_available()

        assert result is True
        mock_backend.is_available.assert_called_once()

    def test_backend_name_property(self, adapter, mock_backend) -> None:
        """Test backend_name property delegation."""
        mock_backend.backend_name = "test-backend"

        result = adapter.backend_name

        assert result == "test-backend"


class TestPromptAdapterContextManager:
    """Test context manager functionality."""

    @pytest.fixture
    def mock_backend(self):
        """Create mock backend."""
        return AsyncMock()

    @pytest.fixture
    def adapter(self, mock_backend):
        """Create PromptAdapter with mocked backend."""
        with patch(
            "mcp_common.prompting.adapter.create_prompt_adapter",
            return_value=mock_backend,
        ):
            return PromptAdapter()

    @pytest.mark.asyncio
    async def test_context_manager_aenter(self, adapter, mock_backend) -> None:
        """Test async context manager entry."""
        mock_backend.initialize.return_value = None

        result = await adapter.__aenter__()

        assert result is adapter
        mock_backend.initialize.assert_called_once()

    @pytest.mark.asyncio
    async def test_context_manager_aexit(self, adapter, mock_backend) -> None:
        """Test async context manager exit."""
        mock_backend.shutdown.return_value = None

        await adapter.__aexit__(None, None, None)

        mock_backend.shutdown.assert_called_once()

    @pytest.mark.asyncio
    async def test_context_manager_full_flow(self) -> None:
        """Test full async context manager flow."""
        mock_backend = AsyncMock()
        with patch(
            "mcp_common.prompting.adapter.create_prompt_adapter",
            return_value=mock_backend,
        ):
            adapter = PromptAdapter()

            async with adapter as ctx:
                assert ctx is adapter

            mock_backend.initialize.assert_called_once()
            mock_backend.shutdown.assert_called_once()

    @pytest.mark.asyncio
    async def test_context_manager_error_handling(self) -> None:
        """Test that shutdown is called even on error."""
        mock_backend = AsyncMock()
        with patch(
            "mcp_common.prompting.adapter.create_prompt_adapter",
            return_value=mock_backend,
        ):
            adapter = PromptAdapter()

            try:
                async with adapter:
                    raise ValueError("Test error")
            except ValueError:
                pass

            mock_backend.initialize.assert_called_once()
            mock_backend.shutdown.assert_called_once()
