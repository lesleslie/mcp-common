"""Factory function for creating prompt adapters with automatic backend detection."""

import sys
from typing import TYPE_CHECKING, Literal

from mcp_common.prompting.base import PromptBackend
from mcp_common.prompting.exceptions import BackendUnavailableError
from mcp_common.prompting.models import PromptAdapterSettings, PromptConfig

if TYPE_CHECKING:
    from mcp_common.backends.pyobjc import PyObjCPromptBackend
    from mcp_common.backends.toolkit import PromptToolkitBackend


def create_prompt_adapter(
    backend: Literal["auto", "pyobjc", "prompt-toolkit"] = "auto",
    config: PromptAdapterSettings | None = None,
) -> PromptBackend:
    """Create a prompt adapter with automatic backend detection.

    This factory function creates the appropriate backend based on the
    specified backend preference or automatic detection.

    Args:
        backend: Backend preference
            - "auto": Automatically detect best available backend
            - "pyobjc": Force PyObjC backend (macOS only)
            - "prompt-toolkit": Force prompt-toolkit backend (cross-platform)
        config: Optional configuration (if None, loads from Oneiric/settings)

    Returns:
        Configured prompt backend instance

    Raises:
        BackendUnavailableError: If requested backend is not available

    Example:
        >>> # Auto-detect best backend
        >>> adapter = create_prompt_adapter()
        >>> await adapter.notify("Hello!")
        >>>
        >>> # Force specific backend
        >>> macos_adapter = create_prompt_adapter(backend="pyobjc")
        >>> tui_adapter = create_prompt_adapter(backend="prompt-toolkit")
    """
    if config is None:
        config = PromptAdapterSettings()

    # Resolve backend selection
    selected_backend = _resolve_backend(backend, config)

    # Import and instantiate the selected backend
    adapter = None
    if selected_backend == "pyobjc":
        try:
            from mcp_common.backends.pyobjc import PyObjCPromptBackend

            adapter = PyObjCPromptBackend(config)
        except ImportError as e:
            raise BackendUnavailableError(
                backend="pyobjc",
                reason="PyObjC is not installed",
                install_hint="Install with: pip install 'mcp-common[macos-prompts]'",
            ) from e
        except Exception as e:
            raise BackendUnavailableError(
                backend="pyobjc",
                reason=f"Failed to initialize PyObjC: {e}",
                install_hint="Ensure you're on macOS and have PyObjC installed",
            ) from e

    elif selected_backend == "prompt-toolkit":
        try:
            from mcp_common.backends.toolkit import PromptToolkitBackend

            adapter = PromptToolkitBackend(config)
        except ImportError as e:
            raise BackendUnavailableError(
                backend="prompt-toolkit",
                reason="prompt-toolkit is not installed",
                install_hint="Install with: pip install 'mcp-common[terminal-prompts]'",
            ) from e
        except Exception as e:
            raise BackendUnavailableError(
                backend="prompt-toolkit",
                reason=f"Failed to initialize prompt-toolkit: {e}",
                install_hint="Ensure prompt-toolkit>=3.0 is installed",
            ) from e

    else:
        raise BackendUnavailableError(
            backend=selected_backend, reason=f"Unknown backend: {selected_backend}"
        )

    # Initialize the adapter and return it
    # Note: initialize() is synchronous for both backends, so we can't easily call it here
    # Users should call await adapter.initialize() explicitly or use context manager
    return adapter


def _resolve_backend(
    preference: str, config: PromptAdapterSettings
) -> Literal["pyobjc", "prompt-toolkit"]:
    """Resolve backend selection based on preference and availability.

    Args:
        preference: User's backend preference
        config: Configuration object

    Returns:
        Resolved backend name

    Raises:
        BackendUnavailableError: If no suitable backend is available
    """
    # If specific backend requested, use it (will error if unavailable)
    if preference in ("pyobjc", "prompt-toolkit"):
        return preference

    # Auto-detect: Try PyObjC on macOS, fallback to prompt-toolkit
    if sys.platform == "darwin":
        # Try PyObjC first on macOS
        try:
            from mcp_common.backends.pyobjc import PyObjCPromptBackend

            # Quick availability check
            if PyObjCPromptBackend.is_available_static():
                return "pyobjc"
        except ImportError:
            pass  # Fall through to prompt-toolkit

    # Fallback to prompt-toolkit (cross-platform)
    try:
        from mcp_common.backends.toolkit import PromptToolkitBackend

        if PromptToolkitBackend.is_available_static():
            return "prompt-toolkit"
    except ImportError:
        pass

    # No backend available
    raise BackendUnavailableError(
        backend="auto",
        reason="No suitable prompting backend is available",
        install_hint=(
            "Install with:\n"
            "  pip install 'mcp-common[macos-prompts]'  # macOS native\n"
            "  pip install 'mcp-common[terminal-prompts]'  # Terminal UI\n"
            "  pip install 'mcp-common[all-prompts]'  # Everything"
        ),
    )


def list_available_backends() -> list[str]:
    """List all available backends on the current platform.

    Returns:
        List of available backend names

    Example:
        >>> available = list_available_backends()
        >>> print(f"Available backends: {', '.join(available)}")
    """
    available = []

    # Check PyObjC
    try:
        from mcp_common.backends.pyobjc import PyObjCPromptBackend

        if PyObjCPromptBackend.is_available_static():
            available.append("pyobjc")
    except ImportError:
        pass

    # Check prompt-toolkit
    try:
        from mcp_common.backends.toolkit import PromptToolkitBackend

        if PromptToolkitBackend.is_available_static():
            available.append("prompt-toolkit")
    except ImportError:
        pass

    return available


__all__ = ["create_prompt_adapter", "list_available_backends"]
