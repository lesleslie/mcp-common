"""Unified prompting and notification adapter for MCP servers.

This module provides a cross-platform interface for user interaction with automatic
backend selection:
- macOS: Native dialogs via PyObjC (NSAlert, NSUserNotification)
- Fallback: Terminal UI via prompt-toolkit

Example:
    >>> # Factory function (recommended)
    >>> from mcp_common.prompting import create_prompt_adapter
    >>> adapter = create_prompt_adapter()  # Auto-detects best backend
    >>> await adapter.notify("Build complete!")
    >>>
    >>> # Direct class instantiation
    >>> from mcp_common.prompting import PromptAdapter, PromptAdapterSettings
    >>> adapter = PromptAdapter()
    >>> await adapter.notify("Hello!")
"""

from mcp_common.prompting.adapter import PromptAdapter
from mcp_common.prompting.base import PromptBackend
from mcp_common.prompting.exceptions import (
    BackendUnavailableError,
    PromptAdapterError,
)
from mcp_common.prompting.factory import create_prompt_adapter, list_available_backends
from mcp_common.prompting.models import (
    ButtonConfig,
    DialogResult,
    NotificationLevel,
    PromptAdapterSettings,
    PromptConfig,  # Backward compatibility alias
    PromptStyle,
)

__all__ = [
    # Wrapper class (new)
    "PromptAdapter",
    # Abstract interface
    "PromptBackend",
    # Factory
    "create_prompt_adapter",
    "list_available_backends",
    # Models (new naming)
    "PromptAdapterSettings",
    # Models (backward compatibility)
    "PromptConfig",
    "DialogResult",
    "ButtonConfig",
    "PromptStyle",
    "NotificationLevel",
    # Exceptions
    "PromptAdapterError",
    "BackendUnavailableError",
]
