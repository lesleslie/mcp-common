"""PromptAdapter wrapper class for direct instantiation.

This module provides a convenient wrapper class for users who prefer
class-based instantiation over factory functions.
"""

from typing import TYPE_CHECKING

from mcp_common.prompting.factory import create_prompt_adapter
from mcp_common.prompting.models import (
    DialogResult,
    NotificationLevel,
    PromptAdapterSettings,
)

if TYPE_CHECKING:
    from pathlib import Path


class PromptAdapter:
    """Convenient wrapper class for direct instantiation.

    Provides a simpler API for users who prefer class instantiation
    over factory functions. Internally delegates to create_prompt_adapter().

    Example:
        >>> # Direct instantiation
        >>> adapter = PromptAdapter()
        >>>
        >>> # With settings
        >>> settings = PromptAdapterSettings(backend="pyobjc")
        >>> adapter = PromptAdapter(settings=settings)
        >>>
        >>> # Use like any backend
        >>> await adapter.notify("Hello!")
    """

    def __init__(
        self,
        backend: str = "auto",
        settings: PromptAdapterSettings | None = None,
    ) -> None:
        """Initialize prompt adapter.

        Args:
            backend: Backend preference (auto, pyobjc, prompt-toolkit)
            settings: Optional settings (uses PromptAdapterSettings.from_settings() if None)
        """
        self._backend = create_prompt_adapter(backend=backend, config=settings)

    # Delegate all PromptBackend methods to the internal backend

    async def alert(
        self,
        title: str,
        message: str,
        detail: str | None = None,
        buttons: list[str] | None = None,
        default_button: str | None = None,
        style: str = "info",
    ) -> DialogResult:
        """Display an alert dialog with optional buttons."""
        return await self._backend.alert(
            title=title,
            message=message,
            detail=detail,
            buttons=buttons,
            default_button=default_button,
            style=style,
        )

    async def confirm(
        self,
        title: str,
        message: str,
        default: bool = False,
        yes_label: str = "Yes",
        no_label: str = "No",
    ) -> bool:
        """Display a confirmation dialog (Yes/No)."""
        return await self._backend.confirm(
            title=title,
            message=message,
            default=default,
            yes_label=yes_label,
            no_label=no_label,
        )

    async def prompt_text(
        self,
        title: str,
        message: str,
        default: str = "",
        placeholder: str = "",
        secure: bool = False,
    ) -> str | None:
        """Prompt user for text input."""
        return await self._backend.prompt_text(
            title=title,
            message=message,
            default=default,
            placeholder=placeholder,
            secure=secure,
        )

    async def prompt_choice(
        self,
        title: str,
        message: str,
        choices: list[str],
        default: str | None = None,
    ) -> str | None:
        """Prompt user to select from a list of choices."""
        return await self._backend.prompt_choice(
            title=title,
            message=message,
            choices=choices,
            default=default,
        )

    async def notify(
        self,
        title: str,
        message: str,
        level: NotificationLevel = NotificationLevel.INFO,
        sound: bool = True,
    ) -> bool:
        """Send a system notification."""
        return await self._backend.notify(
            title=title,
            message=message,
            level=level,
            sound=sound,
        )

    async def select_file(
        self,
        title: str,
        allowed_types: list[str] | None = None,
        multiple: bool = False,
    ) -> "list[Path] | None":
        """Display file selection dialog."""
        return await self._backend.select_file(
            title=title,
            allowed_types=allowed_types,
            multiple=multiple,
        )

    async def select_directory(self, title: str) -> "Path | None":
        """Display directory selection dialog."""
        return await self._backend.select_directory(title=title)

    async def initialize(self) -> None:
        """Initialize backend resources."""
        await self._backend.initialize()

    async def shutdown(self) -> None:
        """Cleanup backend resources."""
        await self._backend.shutdown()

    def is_available(self) -> bool:
        """Check if backend is available."""
        return self._backend.is_available()

    @property
    def backend_name(self) -> str:
        """Get backend name."""
        return self._backend.backend_name

    async def __aenter__(self) -> "PromptAdapter":
        """Context manager entry."""
        await self.initialize()
        return self

    async def __aexit__(self, *args) -> None:
        """Context manager exit."""
        await self.shutdown()
