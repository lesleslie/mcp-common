"""Tests for prompting adapter factory and backend detection."""

from __future__ import annotations

from unittest.mock import Mock, patch

import pytest

from mcp_common.prompting import PromptBackend
from mcp_common.prompting.exceptions import BackendUnavailableError
from mcp_common.prompting.factory import create_prompt_adapter, _resolve_backend
from mcp_common.prompting.models import PromptAdapterSettings, PromptConfig


@pytest.mark.unit
class TestResolveBackend:
    """Tests for _resolve_backend function."""

    def test_resolve_backend_pyobjc_explicit(self) -> None:
        """Test explicit pyobjc backend selection."""
        backend = _resolve_backend("pyobjc", PromptAdapterSettings())
        assert backend == "pyobjc"

    def test_resolve_backend_prompt_toolkit_explicit(self) -> None:
        """Test explicit prompt-toolkit backend selection."""
        backend = _resolve_backend("prompt-toolkit", PromptAdapterSettings())
        assert backend == "prompt-toolkit"

    @patch("sys.platform", "darwin")
    def test_resolve_backend_auto_on_macos_with_pyobjc(self) -> None:
        """Test auto-detection on macOS when PyObjC is available."""
        # Mock PyObjC availability
        with patch(
            "mcp_common.backends.pyobjc.PyObjCPromptBackend.is_available_static",
            return_value=True,
        ):
            backend = _resolve_backend("auto", PromptAdapterSettings())
            assert backend == "pyobjc"

    @patch("sys.platform", "darwin")
    def test_resolve_backend_auto_on_macos_without_pyobjc(self) -> None:
        """Test auto-detection on macOS when PyObjC is not available."""
        # Mock PyObjC unavailability
        with patch(
            "mcp_common.backends.pyobjc.PyObjCPromptBackend.is_available_static",
            return_value=False,
        ):
            backend = _resolve_backend("auto", PromptAdapterSettings())
            assert backend == "prompt-toolkit"

    @patch("sys.platform", "linux")
    def test_resolve_backend_auto_on_linux(self) -> None:
        """Test auto-detection on Linux."""
        backend = _resolve_backend("auto", PromptAdapterSettings())
        assert backend == "prompt-toolkit"

    @patch("sys.platform", "win32")
    def test_resolve_backend_auto_on_windows(self) -> None:
        """Test auto-detection on Windows."""
        backend = _resolve_backend("auto", PromptAdapterSettings())
        assert backend == "prompt-toolkit"


@pytest.mark.unit
class TestCreatePromptAdapter:
    """Tests for create_prompt_adapter factory function."""

    def test_create_adapter_with_default_config(self) -> None:
        """Test creating adapter with default config."""
        # This will use prompt-toolkit (always available in tests)
        adapter = create_prompt_adapter()
        assert isinstance(adapter, PromptBackend)
        assert adapter.backend_name in ("pyobjc", "prompt-toolkit")

    def test_create_adapter_with_custom_config(self) -> None:
        """Test creating adapter with custom config."""
        config = PromptAdapterSettings(timeout=30, backend="prompt-toolkit")
        adapter = create_prompt_adapter(config=config)
        assert isinstance(adapter, PromptBackend)

    def test_create_adapter_prompt_toolkit_backend(self) -> None:
        """Test creating prompt-toolkit backend explicitly."""
        adapter = create_prompt_adapter(backend="prompt-toolkit")
        assert isinstance(adapter, PromptBackend)
        assert adapter.backend_name == "prompt-toolkit"

    def test_create_adapter_invalid_backend(self) -> None:
        """Test creating adapter with invalid backend raises error."""
        # Mock backend detection to return invalid value
        with patch(
            "mcp_common.prompting.factory._resolve_backend",
            return_value="invalid_backend",
        ):
            with pytest.raises(BackendUnavailableError):
                create_prompt_adapter(backend="auto")

    @patch("sys.platform", "darwin")
    def test_create_adapter_auto_on_macos(self) -> None:
        """Test auto backend on macOS."""
        # On macOS, should prefer PyObjC if available
        with patch(
            "mcp_common.backends.pyobjc.PyObjCPromptBackend.is_available_static",
            return_value=True,
        ):
            adapter = create_prompt_adapter(backend="auto")
            assert isinstance(adapter, PromptBackend)
            assert adapter.backend_name == "pyobjc"

    @patch("sys.platform", "linux")
    def test_create_adapter_auto_on_linux(self) -> None:
        """Test auto backend on Linux."""
        adapter = create_prompt_adapter(backend="auto")
        assert isinstance(adapter, PromptBackend)
        assert adapter.backend_name == "prompt-toolkit"

    def test_create_adapter_config_passed_to_backend(self) -> None:
        """Test that config is passed to backend instance."""
        config = PromptAdapterSettings(timeout=60, tui_theme="dark")
        adapter = create_prompt_adapter(backend="prompt-toolkit", config=config)
        assert adapter.config.timeout == 60
        assert adapter.config.tui_theme == "dark"


@pytest.mark.unit
class TestBackendAvailability:
    """Tests for backend availability detection."""

    def test_prompt_toolkit_always_available(self) -> None:
        """Test prompt-toolkit backend is always available (installed with mcp-common[terminal-prompts])."""
        # In test environment, prompt-toolkit should be available
        adapter = create_prompt_adapter(backend="prompt-toolkit")
        assert adapter.is_available() is True

    @patch("sys.platform", "linux")
    def test_pyobjc_not_available_on_linux(self) -> None:
        """Test PyObjC backend is not available on Linux."""
        with pytest.raises(BackendUnavailableError) as exc_info:
            create_prompt_adapter(backend="pyobjc")

        error = exc_info.value
        assert error.backend == "pyobjc"
        assert "install" in str(error).lower()

    @patch("sys.platform", "win32")
    def test_pyobjc_not_available_on_windows(self) -> None:
        """Test PyObjC backend is not available on Windows."""
        with pytest.raises(BackendUnavailableError) as exc_info:
            create_prompt_adapter(backend="pyobjc")

        error = exc_info.value
        assert error.backend == "pyobjc"


@pytest.mark.unit
class TestFactoryErrorHandling:
    """Tests for factory error handling."""

    def test_error_on_unavailable_backend(self) -> None:
        """Test error when requested backend is unavailable."""
        # Mock an unavailable backend
        with patch(
            "mcp_common.prompting.factory._resolve_backend",
            return_value="pyobjc",  # Not available in test env
        ):
            with patch(
                "mcp_common.backends.pyobjc.PyObjCPromptBackend.is_available_static",
                return_value=False,
            ):
                with pytest.raises(BackendUnavailableError):
                    create_prompt_adapter(backend="pyobjc")

    def test_error_message_has_install_hint(self) -> None:
        """Test that BackendUnavailableError includes install hint."""
        try:
            create_prompt_adapter(backend="pyobjc")
        except BackendUnavailableError as e:
            assert e.backend == "pyobjc"
            # Check that pip install appears somewhere in the error
            error_str = str(e).lower()
            assert "pip install" in error_str
        else:
            # If PyObjC is available, this test passes
            pass


@pytest.mark.unit
class TestAdapterInterface:
    """Tests that created adapters conform to PromptBackend interface."""

    def test_adapter_has_backend_name_property(self) -> None:
        """Test adapter has backend_name property."""
        adapter = create_prompt_adapter(backend="prompt-toolkit")
        assert hasattr(adapter, "backend_name")
        assert isinstance(adapter.backend_name, str)

    def test_adapter_has_is_available_method(self) -> None:
        """Test adapter has is_available method."""
        adapter = create_prompt_adapter(backend="prompt-toolkit")
        assert hasattr(adapter, "is_available")
        assert callable(adapter.is_available)

    def test_adapter_has_all_required_methods(self) -> None:
        """Test adapter has all required PromptBackend methods."""
        adapter = create_prompt_adapter(backend="prompt-toolkit")

        required_methods = [
            "alert",
            "confirm",
            "prompt_text",
            "prompt_choice",
            "notify",
            "select_file",
            "select_directory",
        ]

        for method_name in required_methods:
            assert hasattr(adapter, method_name)
            assert callable(getattr(adapter, method_name))
